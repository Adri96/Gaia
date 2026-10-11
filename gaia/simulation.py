"""
Gaia — Simulation engine.

The simulation extracts (or restores) units one at a time, computing externality
costs (or recovered service values) at each step. Damage/recovery functions return
TOTAL value at the current depletion/recovery level (not marginal). Marginal values
are derived by differencing consecutive totals.

All code in this module is Cython-compatible:
    - No dynamic attributes
    - No **kwargs
    - All inner loop variables are primitive floats and ints
    - No third-party dependencies

v0.2: Added run_restoration() — the inverse of run_extraction().
v0.3: Two-phase loops with trophic amplification and interaction propagation.
v0.4: Resilience zone tagging in extraction, maturation pass in restoration.
v0.5: Phase 3.5 substrate degradation in extraction, substrate ceiling in restoration.
v0.6: NPV computation on SimulationResult and RestorationResult when DiscountConfig present.
v0.7: Per-step price solver when PricingConfig present; dynamic prices replace
      the static agent annual values.
Step 3.3: run_restoration starts from a real state (an extraction result) and
      retraces its damage path in reverse; recovery functions are efficiencies
      bounded by the damage reversal.

Monetary semantics (decision D1): agent values and externalities are yearly
flows (€/yr); revenue and restoration costs are one-off amounts (€). The two
are compared only through present values (gaia.discount), which are always
computed — with gaia.discount.DEFAULT_DISCOUNT when a resource has no
DiscountConfig.
"""

import hashlib
import importlib
import math
import os
import warnings
from pathlib import Path
from typing import Callable, Optional

from gaia.carbon import compute_carbon_release
from gaia.damage import evaluate_kernel
from gaia.models import (
    Ecosystem,
    ExtractionNPV,
    PricingConfig,
    RestorationCost,
    RestorationResult,
    RestorationStep,
    SimulationResult,
    SimulationStep,
    SubstrateState,
    SuccessionCurve,
)
from gaia.constants import KEYSTONE_EDGE_MULTIPLIER, MAX_EDGE_STRENGTH
from gaia.propagation import (
    compute_trophic_amplification,
    propagate_interactions,
    trophic_amplification_factor,
)
from gaia.resilience import compute_confidence_band, compute_resilience_zone
from gaia.substrate import (
    _T_HA_TO_MM_FACTOR,
    apply_erosion,
    compute_capacity_fraction,
    compute_substrate_recovery_years,
    create_substrate_state,
    degrade_substrate,
    is_marine,
)
from gaia.succession import compute_maturation_timeline, find_years_to_threshold
from gaia.validation import (
    validate_discount_config,
    validate_ecosystem,
    validate_extraction,
    validate_restoration_cost,
    validate_succession_curve,
)

_PYX_PATH: Path = Path(__file__).resolve().parent / "cy" / "simulation_cy.pyx"


def _pyx_sha256(path: Path) -> str:
    """SHA-256 of a source file with normalised line endings (see setup.py)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_cython_loop(module=None, pyx_path: Path = _PYX_PATH) -> Optional[Callable]:
    """Return the compiled extraction loop, or None to use the Python loop.

    None when ``GAIA_FORCE_PYTHON=1`` is set, when the extension is not built,
    or when it is stale: the SHA-256 of the .pyx it was compiled from
    (``PYX_SOURCE_SHA256``) differs from the current ``pyx_path``. A stale
    build warns. If the .pyx is absent (installed package without sources)
    the compiled module is trusted.

    Args:
        module: The compiled module (default: import gaia.cy.simulation_cy).
        pyx_path: The .pyx source to compare against.
    """
    if os.environ.get("GAIA_FORCE_PYTHON") == "1":
        return None
    if module is None:
        try:
            module = importlib.import_module("gaia.cy.simulation_cy")
        except ImportError:
            return None
    if pyx_path.is_file():
        built = getattr(module, "PYX_SOURCE_SHA256", None)
        current = _pyx_sha256(pyx_path)
        if built != current:
            warnings.warn(
                f"Gaia's compiled extension is out of date with {pyx_path.name} "
                f"(built from {str(built)[:12]}, source is {current[:12]}); "
                f"using the pure-Python loop. Rebuild with: "
                f"python3 setup.py build_ext --inplace",
                RuntimeWarning,
                stacklevel=2,
            )
            return None
    return module.extraction_loop_cy


# v0.8: Cython-optimized simulation loop (None → pure Python)
extraction_loop_cy = _load_cython_loop()
_HAS_CYTHON = extraction_loop_cy is not None

_NO_KERNEL: tuple = (-1, 0.0, 0.0, 0.0, 0.0)
_KERNEL_PROBES: tuple = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)


def _extract_damage_params(damage_fn) -> tuple:
    """Return the Cython kernel tag ``(kind, p1, p2, p3, p4)`` of a damage function.

    Reads the ``kernel`` attribute set by the factories in gaia.damage (see
    that module for the kinds). The tag is trusted only if
    ``evaluate_kernel`` reproduces the function at a few probe points, so a
    wrapped or edited function whose tag no longer describes it cannot be
    silently mis-evaluated by the Cython loop.

    Returns kind=-1 when there is no usable tag, which signals the caller to
    use the pure-Python path.
    """
    kernel = getattr(damage_fn, "kernel", None)
    if not isinstance(kernel, tuple) or len(kernel) != 5:
        return _NO_KERNEL
    try:
        for x in _KERNEL_PROBES:
            if not math.isclose(damage_fn(x), evaluate_kernel(kernel, x),
                                rel_tol=1e-12, abs_tol=1e-15):
                return _NO_KERNEL
    except (ValueError, TypeError, ArithmeticError):
        return _NO_KERNEL
    return kernel


def _can_use_cython(ecosystem: Ecosystem) -> bool:
    """Check if the Cython fast path can be used for this ecosystem.

    The fast path is available when:
    1. The Cython extension is compiled, importable and not stale
    2. No v0.7 pricing config (pricing requires per-step Python solver)
    3. All damage functions carry a verified kernel tag

    Every validated substrate profile (terrestrial or marine) is supported.
    """
    if not _HAS_CYTHON:
        return False
    if ecosystem.pricing is not None:
        return False
    for agent in ecosystem.agents:
        kind = _extract_damage_params(agent.damage_function)[0]
        if kind == -1:
            return False
    return True


# ── Extraction ────────────────────────────────────────────────────────────────
#
# run_extraction validates, then runs the steps with one of two engines —
# _cython_steps (the compiled loop) or _python_steps (the phases below) —
# and both hand their SimulationSteps (built by _make_step) to
# _extraction_result, which computes everything that is not per-step.


def _make_step(
    step: int,
    depletion_ratio: float,
    effective_damages: list,
    agent_costs: list,
    marginal_cost: float,
    total_cost: float,
    revenue: float,
    health: float,
    direct_damages: list,
    cascade_damages: list,
    keystone_triggered: list,
    zone: str,
    confidence: float,
    irreversibility: bool,
    substrate_erosion: float,
    effective_k: int,
    k_fraction: float,
    agent_prices: list,
    price_result,
) -> SimulationStep:
    """One SimulationStep, from either engine's per-step values."""
    return SimulationStep(
        step=step,
        units_extracted=step,
        depletion_ratio=depletion_ratio,
        agent_damages=effective_damages,
        agent_annual_costs=agent_costs,
        marginal_annual_externality=marginal_cost,
        annual_externality=total_cost,
        revenue=revenue,
        ecosystem_health=health,
        agent_direct_damages=direct_damages,
        agent_cascade_damages=cascade_damages,
        keystone_triggered=keystone_triggered,
        resilience_zone=zone,
        model_confidence=confidence,
        irreversibility_warning=irreversibility,
        substrate_erosion=substrate_erosion,
        effective_k=effective_k,
        k_fraction=k_fraction,
        agent_prices=agent_prices,
        price_result=price_result,
    )


# ── Extraction engine 1: the compiled loop ───────────────────────────────────


def _cython_arguments(ecosystem: Ecosystem, units_to_extract: int) -> dict:
    """Flatten the ecosystem into the primitives and lists extraction_loop_cy takes."""
    resource = ecosystem.resource
    agents = ecosystem.agents
    trophic_levels = [a.trophic_level for a in agents]

    # Edges as agent indices
    interactions = ecosystem.interactions
    name_to_idx = {a.name: i for i, a in enumerate(agents)}

    r = resource.resilience
    sub = resource.substrate
    return dict(
        n_agents=len(agents),
        n_edges=len(interactions),
        total_units=resource.total_units,
        units_to_extract=units_to_extract,
        unit_value=resource.unit_value,
        safe_threshold_ratio=resource.safe_threshold_ratio,
        damage_params=[_extract_damage_params(a.damage_function) for a in agents],
        dep_weights=[a.dependency_weight for a in agents],
        annual_values=[a.annual_value(resource.area_ha) for a in agents],
        trophic_levels=trophic_levels,
        trophic_amp_factors=[trophic_amplification_factor(lvl) for lvl in trophic_levels],
        is_keystone=[a.is_keystone for a in agents],
        keystone_thresholds=[a.keystone_threshold for a in agents],
        edge_src_idx=[name_to_idx[e.source] for e in interactions],
        edge_tgt_idx=[name_to_idx[e.target] for e in interactions],
        edge_strengths=[e.strength for e in interactions],
        keystone_edge_multiplier=KEYSTONE_EDGE_MULTIPLIER,
        max_edge_strength=MAX_EDGE_STRENGTH,
        has_trophic=any(lvl >= 1 for lvl in trophic_levels),
        has_interactions=len(interactions) > 0,
        has_resilience=r is not None,
        has_substrate=sub is not None,
        substrate_is_marine=bool(sub is not None and is_marine(sub)),
        resilience_warning_width=r.warning_zone_width if r else 0.0,
        resilience_conf_green=r.confidence_green if r else 0.9,
        resilience_conf_yellow=r.confidence_yellow if r else 0.6,
        resilience_conf_red=r.confidence_red if r else 0.3,
        resilience_irreversibility_ratio=r.irreversibility_flag_ratio if r else 0.5,
        substrate_soil_depth_cm=sub.soil_depth_cm if sub and sub.soil_depth_cm else 0.0,
        substrate_sediment_stability=(
            sub.sediment_stability if sub and sub.sediment_stability else 0.0
        ),
        substrate_erosion_unprotected=sub.erosion_rate_unprotected if sub else 0.0,
        substrate_erosion_protected=sub.erosion_rate_protected if sub else 0.0,
        substrate_formation_rate=sub.formation_rate if sub else 0.0,
        substrate_erosion_alpha=sub.erosion_alpha if sub else 2.0,
        substrate_critical_minimum=sub.critical_minimum if sub else 0.0,
        substrate_residual_fraction=sub.residual_fraction if sub else 0.05,
        substrate_capacity_function=sub.capacity_function if sub else "linear",
        substrate_t_ha_to_mm_factor=_T_HA_TO_MM_FACTOR,
    )


def _cython_steps(ecosystem: Ecosystem, units_to_extract: int) -> list:
    """The extraction steps computed by the compiled loop.

    The loop returns one raw tuple per step; keystone crossings come back
    as agent indices and are mapped to names.
    """
    loop = extraction_loop_cy
    if loop is None:
        raise RuntimeError("the Cython extension is not available")
    agent_names = [a.name for a in ecosystem.agents]
    raw_steps = loop(**_cython_arguments(ecosystem, units_to_extract))

    steps: list = []
    for raw in raw_steps:
        (step, _units_extracted, depletion_ratio,
         effective_damages, agent_annual_costs, marginal_annual_externality,
         annual_externality, revenue, ecosystem_health,
         direct_damages, cascade_damages, keystone_triggered_indices,
         zone, confidence, irreversibility,
         substrate_erosion, effective_k, k_fraction) = raw
        steps.append(_make_step(
            step, depletion_ratio, effective_damages, agent_annual_costs,
            marginal_annual_externality, annual_externality, revenue,
            ecosystem_health, direct_damages, cascade_damages,
            [agent_names[idx] for idx in keystone_triggered_indices],
            zone, confidence, irreversibility,
            substrate_erosion, effective_k, k_fraction,
            [], None,
        ))
    return steps


# ── Extraction engine 2: the Python loop, phase by phase ─────────────────────


def _compute_damage(
    damage_functions: list,
    trophic_levels: list,
    has_trophic: bool,
    depletion_ratio: float,
) -> list:
    """Phase 1: each agent's direct damage, trophically amplified."""
    direct_damages: list = []
    for i in range(len(damage_functions)):
        raw_damage: float = damage_functions[i](depletion_ratio)
        if has_trophic:
            direct_damages.append(
                compute_trophic_amplification(raw_damage, trophic_levels[i])
            )
        else:
            direct_damages.append(raw_damage)
    return direct_damages


def _interaction_arrays(ecosystem: Ecosystem) -> dict:
    """The propagate_interactions arguments that do not change between steps."""
    agents: list = ecosystem.agents
    interactions: list = ecosystem.interactions
    return dict(
        agent_names=[a.name for a in agents],
        edge_sources=[e.source for e in interactions],
        edge_targets=[e.target for e in interactions],
        edge_strengths=[e.strength for e in interactions],
        agent_is_keystone=[a.is_keystone for a in agents],
        agent_keystone_thresholds=[a.keystone_threshold for a in agents],
    )


def _propagate(network: dict, direct_damages: list) -> tuple:
    """Phase 2: interaction propagation → (effective, cascade, keystone names).

    ``network`` comes from _interaction_arrays.
    """
    if not network["edge_sources"]:
        return direct_damages, [0.0] * len(direct_damages), []
    return propagate_interactions(direct_damages=direct_damages, **network)


def _price(
    ecosystem: Ecosystem,
    pricing: PricingConfig,
    agent_names: list,
    effective_damages: list,
    step: int,
) -> tuple:
    """Phase 3a (v0.7, EXPERIMENTAL): endogenous prices → (PriceResult, prices).

    Raises:
        PricingConvergenceError: located at ``step`` (see _pricing_failure).
    """
    from gaia.pricing import PricingConvergenceError, solve_prices

    healths: dict = {}
    for i, name in enumerate(agent_names):
        h: float = 1.0 - effective_damages[i]
        if h < 0.0:
            h = 0.0
        elif h > 1.0:
            h = 1.0
        healths[name] = h
    try:
        price_result = solve_prices(
            agent_names=agent_names,
            agent_healths=healths,
            interactions=ecosystem.interactions,
            pricing=pricing,
        )
    except PricingConvergenceError as exc:
        raise _pricing_failure(exc, step, ecosystem.resource.total_units) from exc
    return price_result, [price_result.prices[name] for name in agent_names]


def _annual_costs(effective_damages: list, weights: list, rates: list) -> tuple:
    """Phase 3b: per-agent €/yr costs, their total, and ecosystem health."""
    costs: list = []
    total: float = 0.0
    health_sum: float = 0.0
    for i in range(len(effective_damages)):
        cost: float = effective_damages[i] * weights[i] * rates[i]
        costs.append(cost)
        total += cost
        health_sum += weights[i] * effective_damages[i]
    health: float = 1.0 - health_sum
    # Clamp health to [0, 1] to guard against floating-point overshoot
    if health < 0.0:
        health = 0.0
    elif health > 1.0:
        health = 1.0
    return costs, total, health


def _substrate(
    state: Optional[SubstrateState],
    total_units: int,
    units_extracted: int,
    years: float,
) -> tuple:
    """Phase 3.5 (v0.5): erode the substrate → (erosion, effective K, K fraction)."""
    if state is None:
        return 0.0, total_units, 1.0
    vegetation_cover: float = (total_units - units_extracted) / total_units
    erosion: float = degrade_substrate(state, vegetation_cover, years=years)
    k_fraction: float = compute_capacity_fraction(state)
    return erosion, int(total_units * k_fraction), k_fraction


def _resilience(resource, depletion_ratio: float) -> tuple:
    """Phase 4 (v0.4): resilience zone → (zone, confidence, irreversibility)."""
    if resource.resilience is None:
        return "green", 1.0, False
    return compute_resilience_zone(
        1.0 - depletion_ratio, resource.safe_threshold_ratio, resource.resilience,
    )


def _python_steps(ecosystem: Ecosystem, units_to_extract: int) -> list:
    """The extraction steps computed by the Python phases (any ecosystem)."""
    resource = ecosystem.resource
    agents: list = ecosystem.agents
    total_units: int = resource.total_units

    damage_functions: list = [a.damage_function for a in agents]
    trophic_levels: list = [a.trophic_level for a in agents]
    has_trophic: bool = any(lvl >= 1 for lvl in trophic_levels)
    weights: list = [a.dependency_weight for a in agents]
    # Agent annual values (€/yr at full damage) = €/ha/yr × area (decision D2)
    annual_values: list = [a.annual_value(resource.area_ha) for a in agents]
    pricing: Optional[PricingConfig] = ecosystem.pricing
    network: dict = _interaction_arrays(ecosystem)

    # v0.5: the whole extraction takes one year, spread evenly over the steps
    substrate_state: Optional[SubstrateState] = None
    years_per_step: float = 0.0
    if resource.substrate is not None:
        substrate_state = create_substrate_state(resource.substrate)
        years_per_step = 1.0 / units_to_extract

    steps: list = []
    previous_total: float = 0.0
    for step in range(1, units_to_extract + 1):
        depletion_ratio: float = step / total_units
        direct = _compute_damage(damage_functions, trophic_levels, has_trophic, depletion_ratio)
        effective, cascade, keystone = _propagate(network, direct)

        price_result = None
        prices: list = []
        if pricing is not None:
            price_result, prices = _price(
                ecosystem, pricing, network["agent_names"], effective, step,
            )
        costs, total, health = _annual_costs(
            effective, weights, prices if pricing is not None else annual_values,
        )
        erosion, effective_k, k_fraction = _substrate(
            substrate_state, total_units, step, years_per_step,
        )
        zone, confidence, irreversible = _resilience(resource, depletion_ratio)

        steps.append(_make_step(
            step, depletion_ratio, effective, costs, total - previous_total,
            total, step * resource.unit_value, health, direct, cascade, keystone,
            zone, confidence, irreversible, erosion, effective_k, k_fraction,
            prices, price_result,
        ))
        previous_total = total
    return steps


# ── Extraction: everything that is not per-step ──────────────────────────────


def _resolve_discount(resource):
    """The resource's DiscountConfig, or DEFAULT_DISCOUNT, validated.

    Every run path that discounts (extraction, restoration, and the CLI,
    which runs them after any --carbon-price change) goes through here, so
    no present value is computed with a config that validation rejects.
    """
    from gaia.discount import DEFAULT_DISCOUNT

    discount = resource.discount if resource.discount is not None else DEFAULT_DISCOUNT
    validate_discount_config(discount)
    return discount


def _npv(
    resource, discount, annual_externality: float, units: int, substrate_ceiling: float,
) -> tuple:
    """Present value of the externality streams → (ExtractionNPV, PV by horizon).

    compute_extraction_npv with the run's DiscountConfig, then its total at
    each of SENSITIVITY_HORIZONS (None where that horizon fails validation).
    """
    from gaia.discount import compute_extraction_npv, horizon_variants

    def pv_externality(config) -> ExtractionNPV:
        return compute_extraction_npv(
            annual_externality=annual_externality,
            discount=config,
            carbon_profile=resource.carbon_profile,
            units_extracted=units,
            substrate_ceiling=substrate_ceiling,
        )

    by_horizon: dict = {
        horizon: (pv_externality(config).total if config is not None else None)
        for horizon, config in horizon_variants(discount).items()
    }
    return pv_externality(discount), by_horizon


def _cost_split(ecosystem: Ecosystem, final_step: SimulationStep) -> tuple:
    """The final step's per-agent cost → (direct part, cascade part), €/yr,
    at the rate each cost used (endogenous price or static value)."""
    agents: list = ecosystem.agents
    area_ha: float = ecosystem.resource.area_ha
    rates: list = final_step.agent_prices or [a.annual_value(area_ha) for a in agents]
    weights: list = [a.dependency_weight for a in agents]
    direct: list = [
        d * w * r for d, w, r in zip(final_step.agent_direct_damages, weights, rates)
    ]
    cascade: list = [
        c * w * r for c, w, r in zip(final_step.agent_cascade_damages, weights, rates)
    ]
    return direct, cascade


def _extraction_result(
    ecosystem: Ecosystem, steps: list, units_to_extract: int
) -> SimulationResult:
    """Assemble a SimulationResult from the extraction steps (both engines).

    The annual externality (€/yr) is the final step's flow. Its present value,
    plus the carbon and substrate streams, comes from compute_extraction_npv
    with the resource's DiscountConfig, or DEFAULT_DISCOUNT when it has none,
    so revenue (one-off) is only ever compared with a present value. The
    PV is also recomputed at each of SENSITIVITY_HORIZONS.
    """
    resource = ecosystem.resource
    discount = _resolve_discount(resource)

    annual_externality: float = 0.0
    revenue: float = 0.0
    health: float = 1.0
    substrate_ceiling: float = 1.0
    confidence: float = 1.0
    band = None
    direct_costs: list = []
    cascade_costs: list = []
    if steps:
        final_step: SimulationStep = steps[-1]
        annual_externality = final_step.annual_externality
        revenue = final_step.revenue
        health = final_step.ecosystem_health
        if resource.substrate is not None:
            substrate_ceiling = final_step.k_fraction
        direct_costs, cascade_costs = _cost_split(ecosystem, final_step)
        confidence = final_step.model_confidence
        if resource.resilience is not None and confidence < 1.0:
            band = compute_confidence_band(annual_externality, confidence)

    extraction_npv, by_horizon = _npv(
        resource, discount, annual_externality, units_to_extract, substrate_ceiling,
    )

    substrate_years: Optional[float] = None
    end_state: Optional[SubstrateState] = _replay_substrate(resource.substrate, steps)
    if end_state is not None:
        substrate_years = compute_substrate_recovery_years(end_state)

    return SimulationResult(
        ecosystem=ecosystem,
        steps=steps,
        total_units_extracted=units_to_extract,
        revenue=revenue,
        annual_externality=annual_externality,
        pv_externality=extraction_npv.total,
        net_social_cost=extraction_npv.total - revenue,
        final_ecosystem_health=health,
        extraction_npv=extraction_npv,
        discount_is_default=resource.discount is None,
        pv_externality_by_horizon=by_horizon,
        discount=discount,
        agent_direct_annual_costs=direct_costs,
        agent_cascade_annual_costs=cascade_costs,
        agent_trophic_amplification=[
            trophic_amplification_factor(a.trophic_level) for a in ecosystem.agents
        ],
        annual_externality_band=band,
        final_model_confidence=confidence,
        substrate_recovery_years=substrate_years,
    )


def _pricing_failure(exc, step: int, total_units: int):
    """The PricingConvergenceError ``exc`` located at extraction ``step``.

    No price exists at this state, so the extraction stops here: there is
    no fallback to static values (C8). The message names the last step
    whose prices were certified.
    """
    from gaia.pricing import PricingConvergenceError

    depletion: float = step / total_units
    if step > 1:
        last_ok: str = (
            f"Pricing was certified up to step {step - 1} "
            f"(depletion {(step - 1) / total_units:.2%}); extract at most "
            f"{step - 1} units, or run without --with-pricing."
        )
    else:
        last_ok = "No step could be priced; run without --with-pricing."
    return PricingConvergenceError(
        f"Endogenous pricing (EXPERIMENTAL) failed at extraction step {step} "
        f"(depletion {depletion:.2%}): {exc} No fallback price is substituted, "
        f"so this run has no valid result. {last_ok}",
        spectral_radius_bound=exc.spectral_radius_bound,
        step=step,
        depletion_ratio=depletion,
    )


def run_extraction(ecosystem: Ecosystem, units_to_extract: int) -> SimulationResult:
    """
    Simulate extracting `units_to_extract` units from the ecosystem.

    v0.3 algorithm (per step):
        Phase 1 — Direct damage with trophic amplification:
            depletion_ratio  = units_extracted / total_units
            raw_damage[i]    = agent[i].damage_function(depletion_ratio)
            direct_damage[i] = trophic_amplification(raw_damage[i], trophic_level[i])

        Phase 2 — Interaction propagation (single pass):
            Apply keystone effects, then propagate damage through edges.
            pressure[i]         = Σ strength[e] × direct_damage[source[e]]
                                  over the edges into i (<= 1, validated)
            effective_damage[i] = direct_damage[i]
                                  + (1 − direct_damage[i]) × pressure[i]
            cascade_damage[i]   = effective_damage[i] − direct_damage[i]

        Phase 3 — Annual cost computation (€/yr flows):
            cost[i]          = effective_damage[i] * weight[i]
                               * annual_value_per_ha[i] * area_ha
            annual_externality = sum(cost[i])
            marginal         = annual_externality - previous annual_externality
            ecosystem_health = 1.0 - sum(weight[i] * effective_damage[i])

    v0.4 additions:
        Phase 4 — Resilience zone tagging:
            If resource.resilience is configured, compute zone/confidence/warning.

    When ecosystem.interactions is empty and all trophic_levels are -1,
    this reduces to the v0.2 algorithm exactly.

    Args:
        ecosystem: The Ecosystem to simulate against.
        units_to_extract: Number of units to extract (>= 0, <= total_units).

    Returns:
        SimulationResult with all steps recorded.

    Raises:
        ValueError: If inputs fail validation.
        PricingConvergenceError: (a ValueError) with pricing on, at the
            first step whose price system cannot be certified convergent.
            Damage, hence scarcity, only rises with depletion, so ρ(S·W)
            never falls at later steps; no static value is ever
            substituted (C8).
    """
    validate_ecosystem(ecosystem)
    validate_extraction(ecosystem, units_to_extract)

    if units_to_extract == 0:
        steps: list = []
    elif _can_use_cython(ecosystem):
        # v0.8: the compiled loop, when built and compatible
        steps = _cython_steps(ecosystem, units_to_extract)
    else:
        steps = _python_steps(ecosystem, units_to_extract)
    return _extraction_result(ecosystem, steps, units_to_extract)


# ── Restoration ───────────────────────────────────────────────────────────────


_RECOVERY_TOLERANCE: float = 1e-9


def _resolve_starting_state(
    ecosystem: Ecosystem,
    units_to_restore: int,
    starting_state: Optional[SimulationResult],
    units_lost: Optional[int],
) -> SimulationResult:
    """Return the extraction result a restoration starts from.

    Either the given ``starting_state`` (which must come from run_extraction
    on this same ecosystem), or an extraction of ``units_lost`` units from
    the pristine resource — ``units_to_restore`` units when neither is
    given ("restore what was cut").
    """
    total_units: int = ecosystem.resource.total_units
    if starting_state is not None:
        if units_lost is not None:
            raise ValueError(
                "Pass either starting_state or units_lost, not both."
            )
        if not isinstance(starting_state, SimulationResult):
            raise ValueError(
                f"starting_state must be a SimulationResult from run_extraction, "
                f"got {type(starting_state).__name__}."
            )
        if starting_state.ecosystem is not ecosystem:
            raise ValueError(
                "starting_state must be the result of run_extraction on the "
                "ecosystem being restored."
            )
        if len(starting_state.steps) != starting_state.total_units_extracted:
            raise ValueError(
                f"starting_state has {len(starting_state.steps)} steps for "
                f"{starting_state.total_units_extracted} units extracted; the "
                f"restoration retraces every step."
            )
        return starting_state

    lost: int = units_to_restore if units_lost is None else units_lost
    if isinstance(lost, bool) or not isinstance(lost, int):
        raise ValueError(f"units_lost must be an integer, got {lost!r}.")
    if lost < 0 or lost > total_units:
        raise ValueError(
            f"units_lost must be in [0, total_units={total_units}], got {lost}."
        )
    return run_extraction(ecosystem, lost)


def _replay_substrate(profile, steps: list) -> Optional[SubstrateState]:
    """Substrate state after the per-step erosion of ``steps`` (None if no profile)."""
    if profile is None:
        return None
    state: SubstrateState = create_substrate_state(profile)
    for step in steps:
        apply_erosion(state, step.substrate_erosion)
    return state


def substrate_after_extraction(extraction: SimulationResult) -> Optional[SubstrateState]:
    """Substrate state at the end of an extraction (None without a substrate).

    Replays the extraction's per-step erosion on a pristine substrate, so the
    state is exactly the one the extraction ended in, whichever engine ran it.
    """
    return _replay_substrate(extraction.ecosystem.resource.substrate, extraction.steps)


def _recovery_efficiency(recovery_fn, agent_name: str, recovery_ratio: float) -> float:
    """A recovery function's efficiency at ``recovery_ratio``, checked to lie
    in [0, 1] (within _RECOVERY_TOLERANCE) and clamped there."""
    efficiency: float = recovery_fn(recovery_ratio)
    if not (-_RECOVERY_TOLERANCE <= efficiency <= 1.0 + _RECOVERY_TOLERANCE):
        raise ValueError(
            f"Recovery function for agent '{agent_name}' returned "
            f"{efficiency} at recovery ratio {recovery_ratio}; recovery "
            f"efficiency must be in [0, 1] (recovery cannot exceed the "
            f"reversal of the damage)."
        )
    if efficiency < 0.0:
        return 0.0
    if efficiency > 1.0:
        return 1.0
    return efficiency


def _restoration_steps(
    ecosystem: Ecosystem,
    start: SimulationResult,
    units_to_restore: int,
    recovery_functions: list,
    substrate_ceiling: float,
    cost_per_unit: float,
) -> tuple:
    """Retrace the starting state's damage path → (steps, reversals, potential).

    ``reversals`` are the final step's per-agent damage reversals and
    ``potential`` its biological recovery before the substrate cap (€/yr).
    See run_restoration for the formulas.
    """
    agents: list = ecosystem.agents
    n_agents: int = len(agents)
    resource = ecosystem.resource
    total_units: int = resource.total_units
    annual_values: list = [a.annual_value(resource.area_ha) for a in agents]
    weights: list = [a.dependency_weight for a in agents]
    missing: int = start.total_units_extracted
    damages_before: list = start.steps[missing - 1].agent_damages
    no_damage: list = [0.0] * n_agents

    steps: list = []
    previous_total_service: float = 0.0
    reversals: list = []
    potential: float = 0.0
    for step in range(1, units_to_restore + 1):
        still_missing: int = missing - step
        recovery_ratio: float = step / missing
        damages_now: list = (
            start.steps[still_missing - 1].agent_damages
            if still_missing > 0 else no_damage
        )

        recoveries: list = []
        reversals = []
        service_values: list = []
        total_service: float = 0.0
        potential = 0.0
        health_sum: float = 0.0
        for i in range(n_agents):
            efficiency: float = _recovery_efficiency(
                recovery_functions[i], agents[i].name, recovery_ratio,
            )
            reversal: float = damages_before[i] - damages_now[i]
            if reversal < 0.0:
                reversal = 0.0
            biological: float = efficiency * reversal
            recovered: float = biological * substrate_ceiling
            service_value: float = recovered * weights[i] * annual_values[i]
            potential += biological * weights[i] * annual_values[i]

            reversals.append(reversal)
            recoveries.append(recovered)
            service_values.append(service_value)
            total_service += service_value
            health_sum += weights[i] * (damages_before[i] - recovered)

        health: float = 1.0 - health_sum
        if health < 0.0:
            health = 0.0
        elif health > 1.0:
            health = 1.0

        steps.append(RestorationStep(
            step=step,
            units_restored=step,
            recovery_ratio=recovery_ratio,
            depletion_ratio=still_missing / total_units,
            agent_recoveries=recoveries,
            agent_service_values=service_values,
            marginal_service_value=total_service - previous_total_service,
            cumulative_service_value=total_service,
            restoration_cost_so_far=step * cost_per_unit,
            ecosystem_health=health,
        ))
        previous_total_service = total_service
    return steps, reversals, potential


def _maturation(
    succession_curve: Optional[SuccessionCurve],
    time_horizon_years: int,
    annual_recovered_potential: float,
    units: int,
    carbon_profile,
    substrate_ceiling: float,
) -> tuple:
    """v0.4 maturation pass → (timeline, years to pioneer / 50% / 90%).

    Empty timeline and zero milestones without a succession curve or horizon.
    """
    if succession_curve is None or time_horizon_years <= 0:
        return [], 0.0, 0.0, 0.0
    timeline: list = compute_maturation_timeline(
        succession_curve=succession_curve,
        max_recovered_value=annual_recovered_potential,
        time_horizon_years=time_horizon_years,
        units_restored=units,
        carbon_profile=carbon_profile,
        substrate_ceiling=substrate_ceiling,
    )
    return (
        timeline,
        find_years_to_threshold(succession_curve, 0.001),
        find_years_to_threshold(succession_curve, 0.50),
        find_years_to_threshold(succession_curve, 0.90),
    )


def _restoration_money(
    ecosystem: Ecosystem,
    restoration_cost: RestorationCost,
    units: int,
    total_cost: float,
    annual_recovered_potential: float,
    annual_damage_reversal: float,
    succession_curve: Optional[SuccessionCurve],
    substrate_ceiling: float,
    discount,
) -> tuple:
    """v0.6 present values → (RestorationNPV, net PV by horizon,
    CarbonBreakeven, DestroyThenRestorePenalty)."""
    from gaia.discount import (
        compute_carbon_breakeven,
        compute_destroy_then_restore_penalty,
        compute_restoration_npv,
        horizon_variants,
    )

    carbon_profile = ecosystem.resource.carbon_profile
    maintenance_per_year: float = restoration_cost.annual_maintenance_per_unit * units
    # Carbon released when the restored units were cut
    carbon_released: float = (
        compute_carbon_release(carbon_profile, units) if carbon_profile is not None else 0.0
    )

    def restoration_npv(config):
        return compute_restoration_npv(
            restoration_cost_total=total_cost,
            maintenance_cost_per_year=maintenance_per_year,
            maintenance_years=restoration_cost.maintenance_years,
            max_recovered_value=annual_recovered_potential,
            discount=config,
            succession_curve=succession_curve,
            carbon_profile=carbon_profile,
            units_restored=units,
            substrate_ceiling=substrate_ceiling,
            carbon_released=carbon_released,
        )

    npv_result = restoration_npv(discount)
    net_pv_by_horizon: dict = {
        horizon: (
            restoration_npv(config).net_present_value if config is not None else None
        )
        for horizon, config in horizon_variants(discount).items()
    }
    breakeven = compute_carbon_breakeven(
        restoration_cost_total=total_cost,
        maintenance_cost_per_year=maintenance_per_year,
        maintenance_years=restoration_cost.maintenance_years,
        discount=discount,
        succession_curve=succession_curve,
        carbon_profile=carbon_profile,
        units_restored=units,
        substrate_ceiling=substrate_ceiling,
    )
    penalty = compute_destroy_then_restore_penalty(
        # the private revenue earned by cutting the restored units: the
        # present value of not cutting them (one-off, year 0)
        foregone_revenue=units * ecosystem.resource.unit_value,
        restoration_cost_pv=npv_result.cost,
        annual_damage_reversal=annual_damage_reversal,
        annual_recovered_potential=annual_recovered_potential,
        discount=discount,
        succession_curve=succession_curve,
        carbon_profile=carbon_profile,
        units=units,
        substrate_ceiling=substrate_ceiling,
    )
    return npv_result, net_pv_by_horizon, breakeven, penalty


def run_restoration(
    ecosystem: Ecosystem,
    units_to_restore: int,
    restoration_cost: RestorationCost,
    recovery_functions: list,
    succession_curve: Optional[SuccessionCurve] = None,
    time_horizon_years: int = 0,
    starting_state: Optional[SimulationResult] = None,
    units_lost: Optional[int] = None,
) -> RestorationResult:
    """
    Simulate restoring `units_to_restore` units to a degraded ecosystem.

    Starting state:
        The restoration starts from the end state of an extraction from the
        pristine resource: ``starting_state`` (the SimulationResult of
        run_extraction on this ecosystem — extraction → restoration
        chaining), or else an extraction of ``units_lost`` units, run here.
        With neither, units_lost = units_to_restore ("restore what was
        cut"). The substrate state also comes from the starting state.

        m = units missing, N = total_units, k = units_to_restore (1 <= k <= m):
            depletion_before = m / N
            depletion_after  = (m − k) / N

    Recovered value at maturity (per restoration step j = 1..k):
        The extraction already computed every agent's effective damage
        (damage function, trophic amplification, interaction propagation)
        at depletions 1/N .. m/N, so restoring j units retraces that path:
            reversal[i]  = damage_i(m/N) − damage_i((m − j)/N)
            efficiency_i = recovery_functions[i](j / m)       in [0, 1]
            recovered[i] = efficiency_i × reversal[i] × substrate_ceiling
            service[i]   = recovered[i] × weight[i] × annual_value[i]   (€/yr)
            health       = 1 − Σ weight[i] × (damage_i(m/N) − recovered[i])
        At step k, Σ service is annual_recovered_value and Σ of
        reversal × weight × value is annual_damage_reversal, i.e.
        annual_externality(depletion_before) − annual_externality(depletion_after)
        at static agent values (endogenous prices are not applied).

        The recovery functions (gaia.recovery) map the fraction of the lost
        units replanted to the fraction of the damage reversal recovered at
        maturity: a recovery efficiency, which must lie in [0, 1], so
        recovery never exceeds the reversal of the damage (Foundation #2).
        logistic_recovery reaches 1 only when every lost unit is replanted
        (partial restoration lags the reversal); linear_recovery(slope)
        caps efficiency at its slope. With efficiency 1, health is the
        extraction's health at depletion_after.

        Trophic amplification is not applied to recovery (S2): the reversal
        is of the extraction's amplified damage, so consumers regain what
        they lost; amplifying recovery as well made them recover 1.6–4.2×
        faster than producers. Interaction cascades are reversed as part of
        the effective damage (the former 0.5× recovery cascade is gone).

    Substrate model (Step 3.4): substrate damage REDUCES THE RESTORATION
    CEILING and is never also counted as a separate permanent flow. The
    ceiling (K_current / K_pristine of the starting state) caps the recovered
    value at maturity — annual_recovered_value and health above — and, year
    by year, the delivered fraction min(s(t), ceiling) of the biological
    recovery (efficiency × reversal) in the maturation timeline, the
    maturation gap (measured against the capped mature value), the
    restoration NPV (services and carbon) and the carbon breakeven. The
    permanent shortfall (1 − ceiling) × biological recovery appears once, in
    the substrate term of the destroy-then-restore penalty. In the extraction
    NPV the direct loss is already permanent, so substrate adds nothing to
    its total.

    Time and money:
        The succession curve spreads the recovery over time (maturation
        timeline and gap), capped at the substrate ceiling.
        Present values (net restoration value, maturation gap, investment
        NPV, destroy-then-restore penalty) use the resource's
        DiscountConfig, or DEFAULT_DISCOUNT when it has none, over its
        horizon; time_horizon_years only sets the length of the reported
        maturation timeline. Foregone revenue and carbon released refer to
        the k units restored (cut, then replanted).

    Prevention vs destroy-then-restore:
        restoration_cost_ratio = (foregone revenue + restoration cost) /
        foregone revenue, an input-price ratio (1 + cost per unit /
        unit_value). destroy_then_restore_penalty is the PV cost to society
        of cutting and restoring over not cutting (restoration cost,
        maturation gap, substrate loss, recovery shortfall, carbon not
        recovered), in € and per € of foregone revenue
        (gaia.discount.compute_destroy_then_restore_penalty).

    Restoration has no Cython loop: it reads the damages from the starting
    state, which either engine may have produced.

    Args:
        ecosystem: The Ecosystem to restore.
        units_to_restore: Number of units to replant (1 <= k <= units missing).
        restoration_cost: RestorationCost parameters (planting + maintenance).
        recovery_functions: List of RecoveryFunc, one per agent, in the same
            order as ecosystem.agents. Each maps the fraction of lost units
            replanted to a recovery efficiency in [0, 1].
        succession_curve: Optional SuccessionCurve for maturation pass (v0.4).
        time_horizon_years: Years to simulate post-restoration (v0.4, 0 = skip).
        starting_state: Optional SimulationResult of run_extraction on this
            ecosystem to restore from.
        units_lost: Optional number of units missing at the start, cut from
            the pristine resource (default: units_to_restore). Not allowed
            together with starting_state.

    Returns:
        RestorationResult with all steps recorded.

    Raises:
        ValueError: If inputs are invalid, including k > units missing or a
            recovery efficiency outside [0, 1].
    """
    validate_ecosystem(ecosystem)
    validate_restoration_cost(restoration_cost)
    if succession_curve is not None:
        validate_succession_curve(succession_curve)

    n_agents: int = len(ecosystem.agents)
    if len(recovery_functions) != n_agents:
        raise ValueError(
            f"recovery_functions must have one entry per agent. "
            f"Got {len(recovery_functions)}, expected {n_agents}."
        )
    if units_to_restore < 1:
        raise ValueError(
            f"units_to_restore must be >= 1, got {units_to_restore}."
        )

    start: SimulationResult = _resolve_starting_state(
        ecosystem, units_to_restore, starting_state, units_lost
    )
    resource = ecosystem.resource
    total_units: int = resource.total_units
    missing: int = start.total_units_extracted
    if units_to_restore > missing:
        raise ValueError(
            f"units_to_restore ({units_to_restore}) cannot exceed the units "
            f"missing in the starting state ({missing} of {total_units})."
        )
    start_step: SimulationStep = start.steps[missing - 1]

    # v0.5: Substrate ceiling of the starting state (substrate model: the
    # ceiling caps what restoration can ever recover; see above)
    substrate_ceiling: float = 1.0
    substrate_recovery_yrs: float = 0.0
    sub_state: Optional[SubstrateState] = substrate_after_extraction(start)
    if sub_state is not None:
        substrate_ceiling = start_step.k_fraction
        substrate_recovery_yrs = compute_substrate_recovery_years(sub_state)

    steps, reversals, annual_recovered_potential = _restoration_steps(
        ecosystem, start, units_to_restore, recovery_functions,
        substrate_ceiling, restoration_cost.total_cost_per_unit,
    )
    final_step: RestorationStep = steps[-1]
    annual_values: list = [a.annual_value(resource.area_ha) for a in ecosystem.agents]
    annual_damage_reversal: float = 0.0
    for i in range(n_agents):
        annual_damage_reversal += (
            reversals[i] * ecosystem.agents[i].dependency_weight * annual_values[i]
        )
    total_cost: float = final_step.restoration_cost_so_far  # €, one-off

    timeline, years_to_pioneer, years_to_50pct, years_to_90pct = _maturation(
        succession_curve, time_horizon_years, annual_recovered_potential,
        units_to_restore, resource.carbon_profile, substrate_ceiling,
    )

    from gaia.discount import restoration_cost_ratio

    npv_result, net_pv_by_horizon, breakeven, penalty = _restoration_money(
        ecosystem, restoration_cost, units_to_restore, total_cost,
        annual_recovered_potential, annual_damage_reversal,
        succession_curve, substrate_ceiling, _resolve_discount(resource),
    )

    return RestorationResult(
        ecosystem=ecosystem,
        restoration_cost=restoration_cost,
        steps=steps,
        total_units_restored=units_to_restore,
        total_restoration_cost=total_cost,
        annual_recovered_value=final_step.cumulative_service_value,  # €/yr
        net_restoration_pv=npv_result.net_present_value,
        restoration_cost_ratio=restoration_cost_ratio(
            units_to_restore * resource.unit_value, total_cost,
        ),
        final_ecosystem_health=final_step.ecosystem_health,
        maturation_timeline=timeline,
        years_to_pioneer=years_to_pioneer,
        years_to_50pct=years_to_50pct,
        years_to_90pct=years_to_90pct,
        maturation_gap_pv=penalty.maturation_gap,
        substrate_ceiling=substrate_ceiling,
        substrate_recovery_years=substrate_recovery_yrs,
        restoration_npv=npv_result,
        carbon_breakeven=breakeven,
        destroy_then_restore_penalty=penalty,
        units_lost=missing,
        depletion_before=missing / total_units,
        depletion_after=(missing - units_to_restore) / total_units,
        initial_ecosystem_health=start_step.ecosystem_health,
        annual_damage_reversal=annual_damage_reversal,
        net_restoration_pv_by_horizon=net_pv_by_horizon,
    )
