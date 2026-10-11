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
import math
import os
import warnings
from pathlib import Path
from typing import Callable, List, Optional

from gaia.carbon import compute_carbon_release
from gaia.damage import evaluate_kernel
from gaia.models import (
    Agent,
    Ecosystem,
    RestorationCost,
    RestorationResult,
    RestorationStep,
    SimulationResult,
    SimulationStep,
    SubstrateState,
    SuccessionCurve,
)
from gaia.propagation import compute_trophic_amplification, propagate_interactions
from gaia.resilience import compute_resilience_zone
from gaia.substrate import (
    _T_HA_TO_MM_FACTOR,
    apply_erosion,
    compute_capacity_fraction,
    compute_substrate_recovery_years,
    create_substrate_state,
    degrade_substrate,
    is_marine,
)
from gaia.succession import (
    compute_maturation_gap,
    compute_maturation_timeline,
    find_years_to_threshold,
)
from gaia.validation import validate_ecosystem, validate_extraction

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
            from gaia.cy import simulation_cy as module
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


def _run_extraction_cython(
    ecosystem: Ecosystem, units_to_extract: int
) -> SimulationResult:
    """Run extraction using the Cython-optimized inner loop.

    Extracts all parameters from Python objects into flat lists/primitives,
    calls the C-typed loop, then wraps results back into SimulationStep
    dataclasses.
    """
    resource = ecosystem.resource
    agents = ecosystem.agents
    n_agents = len(agents)
    total_units = resource.total_units
    unit_value = resource.unit_value

    # Build name-to-index lookup for converting keystone indices back to names
    agent_names = [a.name for a in agents]

    # Pre-extract all per-agent arrays
    damage_params = [_extract_damage_params(a.damage_function) for a in agents]
    dep_weights = [a.dependency_weight for a in agents]
    annual_values = [a.annual_value(resource.area_ha) for a in agents]
    trophic_levels = [a.trophic_level for a in agents]
    is_keystone = [a.is_keystone for a in agents]
    keystone_thresholds = [a.keystone_threshold for a in agents]

    # Pre-extract per-edge arrays (convert names to indices)
    interactions = ecosystem.interactions
    name_to_idx = {name: i for i, name in enumerate(agent_names)}
    edge_src_idx = [name_to_idx[e.source] for e in interactions]
    edge_tgt_idx = [name_to_idx[e.target] for e in interactions]
    edge_strengths = [e.strength for e in interactions]
    n_edges = len(interactions)

    has_trophic = any(lvl >= 1 for lvl in trophic_levels)
    has_interactions = n_edges > 0
    has_resilience = resource.resilience is not None
    has_substrate = resource.substrate is not None

    # Resilience config
    r = resource.resilience
    res_warning = r.warning_zone_width if r else 0.0
    res_conf_green = r.confidence_green if r else 0.9
    res_conf_yellow = r.confidence_yellow if r else 0.6
    res_conf_red = r.confidence_red if r else 0.3
    res_irrev = r.irreversibility_flag_ratio if r else 0.5

    # Substrate config
    sub = resource.substrate
    sub_is_marine = bool(sub is not None and is_marine(sub))
    sub_depth = sub.soil_depth_cm if sub and sub.soil_depth_cm else 0.0
    sub_stability = sub.sediment_stability if sub and sub.sediment_stability else 0.0
    sub_erosion_unp = sub.erosion_rate_unprotected if sub else 0.0
    sub_erosion_pro = sub.erosion_rate_protected if sub else 0.0
    sub_formation = sub.formation_rate if sub else 0.0
    sub_alpha = sub.erosion_alpha if sub else 2.0
    sub_critical = sub.critical_minimum if sub else 0.0
    sub_residual = sub.residual_fraction if sub else 0.05
    sub_cap_fn = sub.capacity_function if sub else "linear"

    # Call the Cython loop
    raw_steps = extraction_loop_cy(
        n_agents=n_agents,
        n_edges=n_edges,
        total_units=total_units,
        units_to_extract=units_to_extract,
        unit_value=unit_value,
        safe_threshold_ratio=resource.safe_threshold_ratio,
        damage_params=damage_params,
        dep_weights=dep_weights,
        annual_values=annual_values,
        trophic_levels=trophic_levels,
        is_keystone=is_keystone,
        keystone_thresholds=keystone_thresholds,
        edge_src_idx=edge_src_idx,
        edge_tgt_idx=edge_tgt_idx,
        edge_strengths=edge_strengths,
        has_trophic=has_trophic,
        has_interactions=has_interactions,
        has_resilience=has_resilience,
        has_substrate=has_substrate,
        substrate_is_marine=sub_is_marine,
        resilience_warning_width=res_warning,
        resilience_conf_green=res_conf_green,
        resilience_conf_yellow=res_conf_yellow,
        resilience_conf_red=res_conf_red,
        resilience_irreversibility_ratio=res_irrev,
        substrate_soil_depth_cm=sub_depth,
        substrate_sediment_stability=sub_stability,
        substrate_erosion_unprotected=sub_erosion_unp,
        substrate_erosion_protected=sub_erosion_pro,
        substrate_formation_rate=sub_formation,
        substrate_erosion_alpha=sub_alpha,
        substrate_critical_minimum=sub_critical,
        substrate_residual_fraction=sub_residual,
        substrate_capacity_function=sub_cap_fn,
        substrate_t_ha_to_mm_factor=_T_HA_TO_MM_FACTOR,
    )

    # Convert raw tuples into SimulationStep dataclasses
    steps = []
    for raw in raw_steps:
        (step, units_extracted, depletion_ratio,
         effective_damages, agent_annual_costs, marginal_annual_externality,
         annual_externality, revenue, ecosystem_health,
         direct_damages, cascade_damages, keystone_triggered_indices,
         zone, confidence, irreversibility,
         substrate_erosion, effective_k, k_fraction) = raw

        # Convert keystone indices back to agent names
        keystone_names = [agent_names[idx] for idx in keystone_triggered_indices]

        steps.append(SimulationStep(
            step=step,
            units_extracted=units_extracted,
            depletion_ratio=depletion_ratio,
            agent_damages=effective_damages,
            agent_annual_costs=agent_annual_costs,
            marginal_annual_externality=marginal_annual_externality,
            annual_externality=annual_externality,
            revenue=revenue,
            ecosystem_health=ecosystem_health,
            agent_direct_damages=direct_damages,
            agent_cascade_damages=cascade_damages,
            keystone_triggered=keystone_names,
            resilience_zone=zone,
            model_confidence=confidence,
            irreversibility_warning=irreversibility,
            substrate_erosion=substrate_erosion,
            effective_k=effective_k,
            k_fraction=k_fraction,
            agent_prices=[],
            price_result=None,
        ))

    return _extraction_result(ecosystem, steps, units_to_extract)


def _extraction_result(
    ecosystem: Ecosystem, steps: list, units_to_extract: int
) -> SimulationResult:
    """Assemble a SimulationResult from the extraction steps (both engines).

    The annual externality (€/yr) is the final step's flow. Its present value,
    plus the carbon and substrate streams, comes from compute_extraction_npv
    with the resource's DiscountConfig, or DEFAULT_DISCOUNT when it has none,
    so revenue (one-off) is only ever compared with a present value.
    """
    from gaia.discount import DEFAULT_DISCOUNT, compute_extraction_npv

    resource = ecosystem.resource
    discount = resource.discount if resource.discount is not None else DEFAULT_DISCOUNT

    if steps:
        final_step: SimulationStep = steps[-1]
        annual_externality: float = final_step.annual_externality
        revenue: float = final_step.revenue
        health: float = final_step.ecosystem_health
        substrate_ceiling: float = (
            final_step.k_fraction if resource.substrate is not None else 1.0
        )
    else:
        annual_externality = 0.0
        revenue = 0.0
        health = 1.0
        substrate_ceiling = 1.0

    extraction_npv = compute_extraction_npv(
        annual_externality=annual_externality,
        discount=discount,
        carbon_profile=resource.carbon_profile,
        units_extracted=units_to_extract,
        substrate_ceiling=substrate_ceiling,
    )

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
            effective_damage[i] = direct_damage[i] + cascade_damage[i]

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
    """
    validate_ecosystem(ecosystem)
    validate_extraction(ecosystem, units_to_extract)

    # v0.8: Dispatch to Cython fast path when available and compatible
    if _can_use_cython(ecosystem) and units_to_extract > 0:
        return _run_extraction_cython(ecosystem, units_to_extract)

    resource = ecosystem.resource
    agents: list = ecosystem.agents
    n_agents: int = len(agents)
    total_units: int = resource.total_units
    unit_value: float = resource.unit_value

    steps: list = []

    # Handle zero-extraction case: return empty result immediately
    if units_to_extract == 0:
        return _extraction_result(ecosystem, steps, 0)

    # v0.3: Pre-extract interaction metadata for the loop
    agent_names: list = [a.name for a in agents]
    agent_trophic_levels: list = [a.trophic_level for a in agents]
    agent_is_keystone: list = [a.is_keystone for a in agents]
    agent_keystone_thresholds: list = [a.keystone_threshold for a in agents]

    interactions: list = ecosystem.interactions
    edge_sources: list = [e.source for e in interactions]
    edge_targets: list = [e.target for e in interactions]
    edge_strengths: list = [e.strength for e in interactions]

    # Short-circuit flags: skip phases when not needed
    has_trophic: bool = any(lvl >= 1 for lvl in agent_trophic_levels)
    has_interactions: bool = len(interactions) > 0
    has_resilience: bool = resource.resilience is not None

    # Agent annual values (€/yr at full damage) = €/ha/yr × area (decision D2)
    annual_values: list = [a.annual_value(resource.area_ha) for a in agents]

    # v0.7: Pre-extract pricing metadata
    has_pricing: bool = ecosystem.pricing is not None
    static_prices: dict = {}
    if has_pricing:
        static_prices = {agent_names[i]: annual_values[i] for i in range(n_agents)}

    # v0.5: Initialize substrate state if profile is configured
    has_substrate: bool = resource.substrate is not None
    substrate_state: Optional[SubstrateState] = None
    time_per_step: float = 0.0
    if has_substrate:
        substrate_state = create_substrate_state(resource.substrate)
        # Default: total extraction takes ~1 year
        time_per_step = 1.0 / units_to_extract if units_to_extract > 0 else 0.0

    previous_total_cost: float = 0.0

    for step in range(1, units_to_extract + 1):
        units_extracted: int = step
        depletion_ratio: float = units_extracted / total_units

        # Phase 1: Direct damage with trophic amplification
        direct_damages: list = []
        for i in range(n_agents):
            raw_damage: float = agents[i].damage_function(depletion_ratio)
            if has_trophic:
                amplified: float = compute_trophic_amplification(
                    raw_damage, agent_trophic_levels[i]
                )
                direct_damages.append(amplified)
            else:
                direct_damages.append(raw_damage)

        # Phase 2: Interaction propagation
        if has_interactions:
            effective_damages, cascade_damages, keystone_triggered = (
                propagate_interactions(
                    agent_names=agent_names,
                    direct_damages=direct_damages,
                    edge_sources=edge_sources,
                    edge_targets=edge_targets,
                    edge_strengths=edge_strengths,
                    agent_is_keystone=agent_is_keystone,
                    agent_keystone_thresholds=agent_keystone_thresholds,
                )
            )
        else:
            effective_damages = direct_damages
            cascade_damages = [0.0] * n_agents
            keystone_triggered = []

        # Phase 3: Compute costs from effective damages
        # v0.7: Solve endogenous prices when PricingConfig is present
        step_price_result = None
        step_agent_prices: list = []

        if has_pricing:
            from gaia.pricing import solve_prices
            # Agent health = 1.0 - effective_damage
            agent_healths_dict: dict = {}
            for i in range(n_agents):
                h: float = 1.0 - effective_damages[i]
                if h < 0.0:
                    h = 0.0
                elif h > 1.0:
                    h = 1.0
                agent_healths_dict[agent_names[i]] = h

            step_price_result = solve_prices(
                agent_names=agent_names,
                agent_healths=agent_healths_dict,
                interactions=interactions,
                pricing=ecosystem.pricing,
                static_prices=static_prices,
            )
            step_agent_prices = [
                step_price_result.prices.get(agent_names[i], annual_values[i])
                for i in range(n_agents)
            ]

        agent_costs: list = []
        step_total_cost: float = 0.0
        health_sum: float = 0.0

        for i in range(n_agents):
            # v0.7: Use dynamic price (€/yr) if available, else the static annual value
            rate: float = (
                step_agent_prices[i] if has_pricing and step_agent_prices
                else annual_values[i]
            )
            cost: float = effective_damages[i] * agents[i].dependency_weight * rate
            agent_costs.append(cost)
            step_total_cost += cost
            health_sum += agents[i].dependency_weight * effective_damages[i]

        marginal_cost: float = step_total_cost - previous_total_cost
        ecosystem_health: float = 1.0 - health_sum
        # Clamp health to [0, 1] to guard against floating-point overshoot
        if ecosystem_health < 0.0:
            ecosystem_health = 0.0
        elif ecosystem_health > 1.0:
            ecosystem_health = 1.0

        private_revenue: float = units_extracted * unit_value

        # Phase 3.5: Substrate degradation (v0.5)
        step_substrate_erosion: float = 0.0
        step_effective_k: int = total_units
        step_k_fraction: float = 1.0
        if has_substrate and substrate_state is not None:
            vegetation_cover: float = (total_units - units_extracted) / total_units
            step_substrate_erosion = degrade_substrate(
                substrate_state, vegetation_cover, years=time_per_step
            )
            step_k_fraction = compute_capacity_fraction(substrate_state)
            step_effective_k = int(total_units * step_k_fraction)

        # Phase 4: Resilience zone tagging (v0.4)
        step_zone: str = "green"
        step_confidence: float = 1.0
        step_irreversibility: bool = False
        if has_resilience:
            remaining_frac: float = 1.0 - depletion_ratio
            step_zone, step_confidence, step_irreversibility = (
                compute_resilience_zone(
                    remaining_frac,
                    resource.safe_threshold_ratio,
                    resource.resilience,
                )
            )

        steps.append(SimulationStep(
            step=step,
            units_extracted=units_extracted,
            depletion_ratio=depletion_ratio,
            agent_damages=effective_damages,
            agent_annual_costs=agent_costs,
            marginal_annual_externality=marginal_cost,
            annual_externality=step_total_cost,
            revenue=private_revenue,
            ecosystem_health=ecosystem_health,
            agent_direct_damages=direct_damages,
            agent_cascade_damages=cascade_damages,
            keystone_triggered=keystone_triggered,
            resilience_zone=step_zone,
            model_confidence=step_confidence,
            irreversibility_warning=step_irreversibility,
            substrate_erosion=step_substrate_erosion,
            effective_k=step_effective_k,
            k_fraction=step_k_fraction,
            agent_prices=step_agent_prices,
            price_result=step_price_result,
        ))

        previous_total_cost = step_total_cost

    return _extraction_result(ecosystem, steps, units_to_extract)


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


def _substrate_after(extraction: SimulationResult) -> Optional[SubstrateState]:
    """Substrate state at the end of an extraction (None without a substrate).

    Replays the extraction's per-step erosion on a pristine substrate, so the
    state is exactly the one the extraction ended in, whichever engine ran it.
    """
    profile = extraction.ecosystem.resource.substrate
    if profile is None:
        return None
    state: SubstrateState = create_substrate_state(profile)
    for step in extraction.steps:
        apply_erosion(state, step.substrate_erosion)
    return state


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
            recovered[i] = efficiency_i × reversal[i]
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

    Time and money:
        The succession curve spreads annual_recovered_value over time
        (maturation timeline and gap); the substrate ceiling of the starting
        state caps the service fraction in the present values as before.
        Present values (net restoration value, maturation gap, investment
        NPV) use the resource's DiscountConfig, or DEFAULT_DISCOUNT when it
        has none. Foregone revenue and carbon released refer to the k units
        restored (cut, then replanted).

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

    agents: list = ecosystem.agents
    cost_per_unit: float = restoration_cost.total_cost_per_unit
    annual_values: list = [a.annual_value(resource.area_ha) for a in agents]
    weights: list = [a.dependency_weight for a in agents]

    start_step: SimulationStep = start.steps[missing - 1]
    damages_before: list = start_step.agent_damages
    no_damage: list = [0.0] * n_agents

    steps: list = []
    previous_total_service: float = 0.0
    reversals: list = []

    for step in range(1, units_to_restore + 1):
        units_restored: int = step
        still_missing: int = missing - units_restored
        recovery_ratio: float = units_restored / missing
        damages_now: list = (
            start.steps[still_missing - 1].agent_damages
            if still_missing > 0 else no_damage
        )

        recoveries: list = []
        reversals = []
        agent_service_values: list = []
        step_total_service: float = 0.0
        health_sum: float = 0.0

        for i in range(n_agents):
            efficiency: float = recovery_functions[i](recovery_ratio)
            if not (-_RECOVERY_TOLERANCE <= efficiency <= 1.0 + _RECOVERY_TOLERANCE):
                raise ValueError(
                    f"Recovery function for agent '{agents[i].name}' returned "
                    f"{efficiency} at recovery ratio {recovery_ratio}; recovery "
                    f"efficiency must be in [0, 1] (recovery cannot exceed the "
                    f"reversal of the damage)."
                )
            if efficiency < 0.0:
                efficiency = 0.0
            elif efficiency > 1.0:
                efficiency = 1.0

            reversal: float = damages_before[i] - damages_now[i]
            if reversal < 0.0:
                reversal = 0.0
            recovered: float = efficiency * reversal
            service_value: float = recovered * weights[i] * annual_values[i]

            reversals.append(reversal)
            recoveries.append(recovered)
            agent_service_values.append(service_value)
            step_total_service += service_value
            health_sum += weights[i] * (damages_before[i] - recovered)

        marginal_value: float = step_total_service - previous_total_service
        ecosystem_health: float = 1.0 - health_sum
        if ecosystem_health < 0.0:
            ecosystem_health = 0.0
        elif ecosystem_health > 1.0:
            ecosystem_health = 1.0

        steps.append(RestorationStep(
            step=step,
            units_restored=units_restored,
            recovery_ratio=recovery_ratio,
            depletion_ratio=still_missing / total_units,
            agent_recoveries=recoveries,
            agent_service_values=agent_service_values,
            marginal_service_value=marginal_value,
            cumulative_service_value=step_total_service,
            restoration_cost_so_far=step * cost_per_unit,
            ecosystem_health=ecosystem_health,
        ))

        previous_total_service = step_total_service

    final_step: RestorationStep = steps[-1]
    annual_recovered: float = final_step.cumulative_service_value  # €/yr
    annual_damage_reversal: float = 0.0
    for i in range(n_agents):
        annual_damage_reversal += reversals[i] * weights[i] * annual_values[i]
    total_cost: float = final_step.restoration_cost_so_far  # €, one-off

    from gaia.discount import (
        DEFAULT_DISCOUNT,
        compute_carbon_breakeven,
        compute_prevention_advantage_v06,
        compute_restoration_npv,
    )
    discount = (
        resource.discount if resource.discount is not None else DEFAULT_DISCOUNT
    )

    # Prevention advantage: how many times cheaper it would have been to not
    # destroy the units vs. destroying them and then restoring them.
    # foregone_revenue = the private revenue earned by cutting the restored units
    foregone_revenue: float = units_to_restore * resource.unit_value
    if foregone_revenue > 0.0:
        prevention_advantage: float = (foregone_revenue + total_cost) / foregone_revenue
    else:
        prevention_advantage = 1.0

    # v0.5: Substrate ceiling (from the starting state) and enhanced PA
    substrate_ceiling: float = 1.0
    substrate_recovery_yrs: float = 0.0
    prevention_advantage_with_substrate: float = prevention_advantage
    sub_state: Optional[SubstrateState] = _substrate_after(start)
    if sub_state is not None:
        substrate_ceiling = start_step.k_fraction
        substrate_recovery_yrs = compute_substrate_recovery_years(sub_state)

        # Enhanced prevention advantage including permanent capacity loss:
        # the annual flow lost (€/yr) summed, undiscounted, over the
        # substrate recovery time (capped at 50 years) — a one-off €.
        # TODO(3.7): undiscounted; replaced by destroy_then_restore_penalty.
        if substrate_ceiling < 1.0 and foregone_revenue > 0.0:
            permanent_loss_fraction: float = 1.0 - substrate_ceiling
            # Annual recovered service value at maturity (€/yr)
            annual_lost_value: float = annual_recovered * permanent_loss_fraction
            # Cap at 50 years for NPV calculation (avoid infinite values)
            npv_years: float = min(substrate_recovery_yrs, 50.0)
            permanent_loss_npv: float = annual_lost_value * npv_years
            prevention_advantage_with_substrate = (
                (foregone_revenue + total_cost + permanent_loss_npv)
                / foregone_revenue
            )

    # v0.4: Maturation pass — produce year-by-year timeline if succession curve provided
    maturation_timeline: list = []
    years_to_pioneer: float = 0.0
    years_to_50pct: float = 0.0
    years_to_90pct: float = 0.0
    maturation_gap_pv: float = 0.0

    if succession_curve is not None and time_horizon_years > 0:
        maturation_timeline = compute_maturation_timeline(
            succession_curve=succession_curve,
            max_recovered_value=annual_recovered,
            time_horizon_years=time_horizon_years,
            units_restored=units_to_restore,
            carbon_profile=ecosystem.resource.carbon_profile,
        )
        maturation_gap_pv = compute_maturation_gap(
            maturation_timeline, annual_recovered, discount
        )
        # Compute milestone years
        years_to_pioneer = find_years_to_threshold(succession_curve, 0.001)
        years_to_50pct = find_years_to_threshold(succession_curve, 0.50)
        years_to_90pct = find_years_to_threshold(succession_curve, 0.90)

    # v0.6: NPV computations (DEFAULT_DISCOUNT when no DiscountConfig)
    # Total maintenance cost (total across all units)
    maintenance_total_per_year: float = (
        restoration_cost.annual_maintenance_per_unit * units_to_restore
    )

    # Carbon released during prior extraction
    carbon_released: float = 0.0
    if ecosystem.resource.carbon_profile is not None:
        carbon_released = compute_carbon_release(
            ecosystem.resource.carbon_profile, units_to_restore
        )

    restoration_npv_result = compute_restoration_npv(
        restoration_cost_total=total_cost,
        maintenance_cost_per_year=maintenance_total_per_year,
        maintenance_years=restoration_cost.maintenance_years,
        max_recovered_value=annual_recovered,
        discount=discount,
        succession_curve=succession_curve,
        carbon_profile=ecosystem.resource.carbon_profile,
        units_restored=units_to_restore,
        substrate_ceiling=substrate_ceiling,
        carbon_released=carbon_released,
    )

    carbon_breakeven_result = compute_carbon_breakeven(
        restoration_cost_total=total_cost,
        maintenance_cost_per_year=maintenance_total_per_year,
        maintenance_years=restoration_cost.maintenance_years,
        discount=discount,
        succession_curve=succession_curve,
        carbon_profile=ecosystem.resource.carbon_profile,
        units_restored=units_to_restore,
        substrate_ceiling=substrate_ceiling,
    )

    pa_v06_result = compute_prevention_advantage_v06(
        foregone_revenue=foregone_revenue,
        restoration_cost_total=total_cost,
        maintenance_cost_per_year=maintenance_total_per_year,
        maintenance_years=restoration_cost.maintenance_years,
        discount=discount,
        max_recovered_value=annual_recovered,
        succession_curve=succession_curve,
        carbon_profile=ecosystem.resource.carbon_profile,
        units=units_to_restore,
        substrate_ceiling=substrate_ceiling,
        carbon_released=carbon_released,
        pa_simple=prevention_advantage,
    )

    return RestorationResult(
        ecosystem=ecosystem,
        restoration_cost=restoration_cost,
        steps=steps,
        total_units_restored=units_to_restore,
        total_restoration_cost=total_cost,
        annual_recovered_value=annual_recovered,
        net_restoration_pv=restoration_npv_result.net_present_value,
        prevention_advantage=prevention_advantage,
        final_ecosystem_health=final_step.ecosystem_health,
        maturation_timeline=maturation_timeline,
        years_to_pioneer=years_to_pioneer,
        years_to_50pct=years_to_50pct,
        years_to_90pct=years_to_90pct,
        maturation_gap_pv=maturation_gap_pv,
        substrate_ceiling=substrate_ceiling,
        substrate_recovery_years=substrate_recovery_yrs,
        prevention_advantage_with_substrate=prevention_advantage_with_substrate,
        restoration_npv=restoration_npv_result,
        carbon_breakeven=carbon_breakeven_result,
        prevention_advantage_v06=pa_v06_result,
        units_lost=missing,
        depletion_before=missing / total_units,
        depletion_after=(missing - units_to_restore) / total_units,
        initial_ecosystem_health=start_step.ecosystem_health,
        annual_damage_reversal=annual_damage_reversal,
    )
