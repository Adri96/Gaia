"""
Gaia — Simulation engine: a static damage function, evaluated directly.

Every per-step quantity of an extraction depends only on the depletion
ratio k / N at that step (decision D5, option B; PROJECT_DEFINITION.md §13):
the damage functions, trophic amplification, single-pass cascade, keystone
boost, annual externality, health and resilience zone are evaluated at the
requested depletion, with nothing carried over from earlier steps. The one
exception is the substrate, whose erosion is integrated over the steps (the
whole extraction spread over one year); that Riemann sum is kept as it was,
so its numbers do not change.

So run_extraction and run_restoration do not loop over units. They evaluate
the final state (and the step before it, for the marginal cost), and return
their steps as lazy sequences (ExtractionSteps, RestorationSteps): a step is
computed when it is indexed or iterated, with the same arithmetic the former
per-unit loop used, so every number is bit-for-bit what that loop produced.
Time enters only through discounting, the succession curve and the substrate
ceiling. A path-dependent engine (option A: a time axis, relaxation,
keystone hysteresis, damage-dependent recovery) is a committed roadmap
milestone after v1.0 (version_specs/V09_SPEC.md §4); it would read an
optional schema-2 ``dynamics`` block and leave this static engine as the
no-``dynamics`` path.

Damage/recovery functions return TOTAL value at the current depletion/
recovery level (not marginal). Marginal values are differences of
consecutive totals.

v0.2: Added run_restoration() — the inverse of run_extraction().
v0.3: Trophic amplification and interaction propagation.
v0.4: Resilience zone tagging in extraction, maturation pass in restoration.
v0.5: Substrate degradation in extraction, substrate ceiling in restoration.
v0.6: NPV computation on SimulationResult and RestorationResult.
v0.7: Per-step price solver when PricingConfig present (EXPERIMENTAL).
Step 3.3: run_restoration starts from a real state (an extraction result) and
      retraces its damage path in reverse; recovery functions are efficiencies
      bounded by the damage reversal.
Step 8 (D5 option B, D7): direct evaluation replaces the per-unit loop; the
      optional Cython loop is gone.

Monetary semantics (decision D1): agent values and externalities are yearly
flows (€/yr); revenue and restoration costs are one-off amounts (€). The two
are compared only through present values (gaia.discount), which are always
computed — with gaia.discount.DEFAULT_DISCOUNT when a resource has no
DiscountConfig.
"""

from collections.abc import Sequence
from typing import Dict, Iterator, List, Optional

from gaia.carbon import compute_carbon_release
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
from gaia.propagation import (
    area_loss_damages,
    compute_trophic_amplification,
    propagate_interactions,
    trophic_amplification_factor,
)
from gaia.provenance import calibration_status
from gaia.resilience import compute_resilience_zone
from gaia.substrate import (
    apply_erosion,
    compute_capacity_fraction,
    compute_substrate_recovery_years,
    create_substrate_state,
    degrade_substrate,
)
from gaia.succession import compute_maturation_timeline, find_years_to_threshold
from gaia.validation import (
    validate_discount_config,
    validate_ecosystem,
    validate_extraction,
    validate_restoration_cost,
    validate_succession_curve,
)


# ── Extraction: the static function, phase by phase ─────────────────────────


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


def _resilience(resource, depletion_ratio: float) -> tuple:
    """Phase 4 (v0.4): resilience zone → (zone, confidence, irreversibility)."""
    if resource.resilience is None:
        return "green", 1.0, False
    return compute_resilience_zone(
        1.0 - depletion_ratio, resource.safe_threshold_ratio, resource.resilience,
    )


def _replay_substrate(profile, erosions) -> Optional[SubstrateState]:
    """Substrate state after applying the per-step ``erosions`` to a pristine
    profile (None without a profile)."""
    if profile is None:
        return None
    state: SubstrateState = create_substrate_state(profile)
    for erosion in erosions:
        apply_erosion(state, erosion)
    return state


class ExtractionSteps(Sequence):
    """The steps of an extraction, evaluated when they are asked for.

    ``steps[k - 1]`` is the SimulationStep after k units extracted. Every
    field but the substrate ones is a function of the depletion k / N alone
    (the static damage function), so a step is computed directly from k; its
    marginal cost is its annual externality minus that of step k − 1,
    evaluated the same way. Iterating evaluates the steps in order and
    reuses each total as the next step's "previous", with exactly the
    arithmetic of the former per-unit loop.

    The substrate is the only quantity carried from step to step: the
    extraction is spread evenly over one year and the erosion of each step
    applied in turn (a Riemann sum whose value depends on the number of
    units). That trajectory — one scalar update per unit — is computed once,
    on construction, and gives each step's ``substrate_erosion``,
    ``effective_k`` and ``k_fraction``.

    EXPERIMENTAL pricing keeps its contract of stopping at the first step
    whose price system cannot be certified: with a PricingConfig every step
    is solved on construction (PricingConvergenceError at the first
    failure), and the price results are kept for the steps.

    A step is a new SimulationStep each time it is computed; the last few
    are cached, so repeated ``steps[-1]`` returns the same object.
    """

    _CACHE_SIZE: int = 8

    def __init__(self, ecosystem: Ecosystem, units_to_extract: int) -> None:
        resource = ecosystem.resource
        agents: list = ecosystem.agents
        self._ecosystem: Ecosystem = ecosystem
        self._resource = resource
        self._units: int = units_to_extract
        self._total_units: int = resource.total_units
        self._damage_functions: list = [a.damage_function for a in agents]
        self._trophic_levels: list = [a.trophic_level for a in agents]
        self._has_trophic: bool = any(lvl >= 1 for lvl in self._trophic_levels)
        self._weights: list = [a.dependency_weight for a in agents]
        # Agent annual values (€/yr at full damage) = €/ha/yr × area (decision D2)
        self._annual_values: list = [a.annual_value(resource.area_ha) for a in agents]
        self._network: dict = _interaction_arrays(ecosystem)
        self._area_loss: bool = ecosystem.damage_model == "area_loss"
        self._pricing: Optional[PricingConfig] = ecosystem.pricing
        self._cache: Dict[int, SimulationStep] = {}

        # v0.5 substrate: the whole extraction takes one year, spread evenly
        # over the steps (the Riemann sum of the former loop, kept as is)
        self._erosion: List[float] = []
        self._effective_k: List[int] = []
        self._k_fraction: List[float] = []
        if resource.substrate is not None and units_to_extract > 0:
            state: SubstrateState = create_substrate_state(resource.substrate)
            years_per_step: float = 1.0 / units_to_extract
            for step in range(1, units_to_extract + 1):
                cover: float = (self._total_units - step) / self._total_units
                erosion: float = degrade_substrate(state, cover, years=years_per_step)
                k_fraction: float = compute_capacity_fraction(state)
                self._erosion.append(erosion)
                self._k_fraction.append(k_fraction)
                self._effective_k.append(int(self._total_units * k_fraction))

        # EXPERIMENTAL pricing: certify every step, in order (see above)
        self._prices: List[tuple] = []
        if self._pricing is not None:
            for step in range(1, units_to_extract + 1):
                _, effective, _, _ = self._damages(step)
                self._prices.append(_price(
                    ecosystem, self._pricing, self._network["agent_names"],
                    effective, step,
                ))

    # ── The static function at one step ──────────────────────────────────

    def _damages(self, step: int) -> tuple:
        """(direct, effective, cascade, keystone names) at ``step`` units.

        Under the "area_loss" damage model the curves, amplification and
        cascades give the degradation of the remaining resource, and the
        area lost is added (gaia.propagation.area_loss_damages): direct and
        effective damage are D + (1 − D) × their degradation, so the
        cascade part is (1 − D) × the cascade degradation.
        """
        depletion_ratio: float = step / self._total_units
        direct = _compute_damage(
            self._damage_functions, self._trophic_levels, self._has_trophic,
            depletion_ratio,
        )
        effective, cascade, keystone = _propagate(self._network, direct)
        if self._area_loss:
            remaining: float = 1.0 - depletion_ratio
            direct = area_loss_damages(depletion_ratio, direct)
            effective = area_loss_damages(depletion_ratio, effective)
            cascade = [remaining * c for c in cascade]
        return direct, effective, cascade, keystone

    def _rates(self, step: int) -> list:
        """The €/yr rate of each agent at ``step``: endogenous prices or static values."""
        if self._pricing is not None:
            return self._prices[step - 1][1]
        return self._annual_values

    def _total(self, step: int) -> float:
        """Annual externality (€/yr) at ``step`` units; 0 before the first."""
        if step <= 0:
            return 0.0
        _, effective, _, _ = self._damages(step)
        return _annual_costs(effective, self._weights, self._rates(step))[1]

    def _compute(self, step: int, previous_total: float) -> SimulationStep:
        """The SimulationStep after ``step`` units, given the previous total."""
        resource = self._resource
        depletion_ratio: float = step / self._total_units
        direct, effective, cascade, keystone = self._damages(step)
        price_result = None
        prices: list = []
        if self._pricing is not None:
            price_result, prices = self._prices[step - 1]
        costs, total, health = _annual_costs(effective, self._weights, self._rates(step))
        if self._erosion:
            erosion: float = self._erosion[step - 1]
            effective_k: int = self._effective_k[step - 1]
            k_fraction: float = self._k_fraction[step - 1]
        else:
            erosion, effective_k, k_fraction = 0.0, self._total_units, 1.0
        zone, confidence, irreversible = _resilience(resource, depletion_ratio)
        return SimulationStep(
            step=step,
            units_extracted=step,
            depletion_ratio=depletion_ratio,
            agent_damages=effective,
            agent_annual_costs=costs,
            marginal_annual_externality=total - previous_total,
            annual_externality=total,
            revenue=step * resource.unit_value,
            ecosystem_health=health,
            agent_direct_damages=direct,
            agent_cascade_damages=cascade,
            keystone_triggered=keystone,
            resilience_zone=zone,
            model_confidence=confidence,
            irreversibility_warning=irreversible,
            substrate_erosion=erosion,
            effective_k=effective_k,
            k_fraction=k_fraction,
            agent_prices=prices,
            price_result=price_result,
        )

    def _step(self, step: int) -> SimulationStep:
        cached = self._cache.get(step)
        if cached is None:
            cached = self._compute(step, self._total(step - 1))
            if len(self._cache) >= self._CACHE_SIZE:
                self._cache.clear()
            self._cache[step] = cached
        return cached

    # ── Sequence protocol ────────────────────────────────────────────────

    def __len__(self) -> int:
        return self._units

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self._step(i + 1) for i in range(*index.indices(self._units))]
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"step indices must be integers or slices, not {type(index).__name__}")
        if index < 0:
            index += self._units
        if not 0 <= index < self._units:
            raise IndexError("step index out of range")
        return self._step(index + 1)

    def __iter__(self) -> Iterator[SimulationStep]:
        previous_total: float = 0.0
        for step in range(1, self._units + 1):
            current = self._compute(step, previous_total)
            previous_total = current.annual_externality
            yield current

    def __repr__(self) -> str:
        return f"<ExtractionSteps: {self._units} steps of {self._ecosystem.name!r}>"

    def agent_damages(self, step: int) -> list:
        """Effective damage per agent after ``step`` units (1..len), without
        building the whole step (restoration reads only these)."""
        cached = self._cache.get(step)
        if cached is not None:
            return cached.agent_damages
        return self._damages(step)[1]

    # ── Scans the report needs, without building every step ─────────────

    def keystone_crossings(self) -> Dict[str, int]:
        """{keystone agent: first step at which it crossed its threshold}.

        The trigger depends only on the keystone's own direct damage (and
        needs at least one edge), so only those damages are evaluated.
        """
        crossings: Dict[str, int] = {}
        if not self._network["edge_sources"]:
            return crossings
        agents: list = self._ecosystem.agents
        keystones: list = [i for i, a in enumerate(agents) if a.is_keystone]
        for step in range(1, self._units + 1):
            if len(crossings) == len(keystones):
                break
            depletion_ratio: float = step / self._total_units
            for i in keystones:
                name: str = agents[i].name
                if name in crossings:
                    continue
                raw: float = self._damage_functions[i](depletion_ratio)
                direct: float = (
                    compute_trophic_amplification(raw, self._trophic_levels[i])
                    if self._has_trophic else raw
                )
                if 1.0 - direct < agents[i].keystone_threshold:
                    crossings[name] = step
        return crossings

    def zone_transitions(self) -> List[tuple]:
        """[(from zone, to zone, step)] as the depletion rises, starting green."""
        transitions: List[tuple] = []
        previous: str = "green"
        for step in range(1, self._units + 1):
            zone: str = _resilience(self._resource, step / self._total_units)[0]
            if zone != previous:
                transitions.append((previous, zone, step))
                previous = zone
        return transitions

    def first_irreversible_step(self) -> Optional[int]:
        """The first step flagged irreversible, or None."""
        for step in range(1, self._units + 1):
            if _resilience(self._resource, step / self._total_units)[2]:
                return step
        return None

    def substrate_end_state(self) -> Optional[SubstrateState]:
        """A fresh copy of the substrate state after the last step (None
        without a substrate profile), by replaying the per-step erosion."""
        return _replay_substrate(self._resource.substrate, self._erosion)


def keystone_crossings(steps) -> Dict[str, int]:
    """{keystone agent: first step at which it crossed its threshold}, for
    the steps of an extraction (ExtractionSteps: only the keystone damages
    are evaluated; any other sequence of SimulationStep is scanned)."""
    if isinstance(steps, ExtractionSteps):
        return steps.keystone_crossings()
    crossings: Dict[str, int] = {}
    for s in steps:
        for name in s.keystone_triggered:
            crossings.setdefault(name, s.step)
    return crossings


def zone_transitions(steps) -> List[tuple]:
    """[(from zone, to zone, step)] over the steps of an extraction, from green."""
    if isinstance(steps, ExtractionSteps):
        return steps.zone_transitions()
    transitions: List[tuple] = []
    previous: str = "green"
    for s in steps:
        if s.resilience_zone != previous:
            transitions.append((previous, s.resilience_zone, s.step))
            previous = s.resilience_zone
    return transitions


def first_irreversible_step(steps) -> Optional[int]:
    """The first step of an extraction flagged irreversible, or None."""
    if isinstance(steps, ExtractionSteps):
        return steps.first_irreversible_step()
    for s in steps:
        if s.irreversibility_warning:
            return s.step
    return None


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
    ecosystem: Ecosystem, steps: ExtractionSteps, units_to_extract: int
) -> SimulationResult:
    """Assemble a SimulationResult from the final step of the extraction.

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

    extraction_npv, by_horizon = _npv(
        resource, discount, annual_externality, units_to_extract, substrate_ceiling,
    )

    substrate_years: Optional[float] = None
    end_state: Optional[SubstrateState] = steps.substrate_end_state()
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
        final_model_confidence=confidence,
        substrate_recovery_years=substrate_years,
        calibration=calibration_status(ecosystem, discount),
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
    Extract `units_to_extract` units from the ecosystem.

    The static damage function (decision D5, option B) is evaluated at
    depletion k / N for the final step k = units_to_extract (and k − 1, for
    the marginal cost); the other steps are evaluated only if asked for
    (``result.steps``, an ExtractionSteps). At step k:
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
                               * annual_value_per_ha[i] * site_share[i] * area_ha
            annual_externality = sum(cost[i])
            marginal         = annual_externality - previous annual_externality
            ecosystem_health = 1.0 - sum(weight[i] * effective_damage[i])

    v0.4 additions:
        Phase 4 — Resilience zone tagging:
            If resource.resilience is configured, compute zone/confidence/warning.

    Substrate (v0.5): the one quantity integrated over the steps; see
    ExtractionSteps.

    When ecosystem.interactions is empty and all trophic_levels are -1,
    this reduces to the v0.2 algorithm exactly.

    Args:
        ecosystem: The Ecosystem to simulate against.
        units_to_extract: Number of units to extract (>= 0, <= total_units).

    Returns:
        SimulationResult; its ``steps`` evaluate every step on request.

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
    return _extraction_result(
        ecosystem, ExtractionSteps(ecosystem, units_to_extract), units_to_extract,
    )


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


def substrate_after_extraction(extraction: SimulationResult) -> Optional[SubstrateState]:
    """Substrate state at the end of an extraction (None without a substrate).

    Replays the extraction's per-step erosion on a pristine substrate, so the
    state is exactly the one the extraction ended in (a fresh copy each call).
    """
    steps = extraction.steps
    if isinstance(steps, ExtractionSteps):
        return steps.substrate_end_state()
    return _replay_substrate(
        extraction.ecosystem.resource.substrate, [s.substrate_erosion for s in steps],
    )


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


def _damages_at(start: SimulationResult, units_extracted: int) -> list:
    """Effective damages of the starting extraction after ``units_extracted``
    units (no damage at 0)."""
    if units_extracted <= 0:
        return [0.0] * len(start.ecosystem.agents)
    steps = start.steps
    if isinstance(steps, ExtractionSteps):
        return steps.agent_damages(units_extracted)
    return steps[units_extracted - 1].agent_damages


class RestorationSteps(Sequence):
    """The steps of a restoration, evaluated when they are asked for.

    ``steps[j - 1]`` is the RestorationStep after j units replanted. It
    depends only on j: the starting state's damage at m / N and at
    (m − j) / N (both from the static damage function) and the recovery
    efficiencies at j / m (see run_restoration). Its marginal service value
    is its total minus that of step j − 1. Iterating evaluates the steps in
    order with exactly the arithmetic of the former per-unit loop.

    The recovery functions are user callables whose efficiency must lie in
    [0, 1]: every ratio j / m used by the restoration is checked on
    construction (ValueError at the first violation), as the former loop
    did, although only the steps asked for are built.
    """

    _CACHE_SIZE: int = 8

    def __init__(
        self,
        ecosystem: Ecosystem,
        start: SimulationResult,
        units_to_restore: int,
        recovery_functions: list,
        substrate_ceiling: float,
        cost_per_unit: float,
    ) -> None:
        agents: list = ecosystem.agents
        resource = ecosystem.resource
        self._agents: list = agents
        self._start: SimulationResult = start
        self._units: int = units_to_restore
        self._total_units: int = resource.total_units
        self._missing: int = start.total_units_extracted
        self._recovery_functions: list = recovery_functions
        self._substrate_ceiling: float = substrate_ceiling
        self._cost_per_unit: float = cost_per_unit
        self._annual_values: list = [a.annual_value(resource.area_ha) for a in agents]
        self._weights: list = [a.dependency_weight for a in agents]
        self._damages_before: list = _damages_at(start, self._missing)
        self._cache: Dict[int, RestorationStep] = {}
        for step in range(1, units_to_restore + 1):
            ratio: float = step / self._missing
            for i in range(len(agents)):
                _recovery_efficiency(recovery_functions[i], agents[i].name, ratio)

    def _service(self, step: int) -> tuple:
        """(recoveries, reversals, service values, total, potential, health)
        after ``step`` units replanted."""
        agents: list = self._agents
        weights: list = self._weights
        annual_values: list = self._annual_values
        damages_before: list = self._damages_before
        damages_now: list = _damages_at(self._start, self._missing - step)
        recovery_ratio: float = step / self._missing

        recoveries: list = []
        reversals: list = []
        service_values: list = []
        total_service: float = 0.0
        potential: float = 0.0
        health_sum: float = 0.0
        for i in range(len(agents)):
            efficiency: float = _recovery_efficiency(
                self._recovery_functions[i], agents[i].name, recovery_ratio,
            )
            reversal: float = damages_before[i] - damages_now[i]
            if reversal < 0.0:
                reversal = 0.0
            biological: float = efficiency * reversal
            recovered: float = biological * self._substrate_ceiling
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
        return recoveries, reversals, service_values, total_service, potential, health

    def _total(self, step: int) -> float:
        """Annual service value recovered (€/yr) after ``step`` units; 0 at 0."""
        if step <= 0:
            return 0.0
        return self._service(step)[3]

    def _compute(self, step: int, previous_total: float) -> RestorationStep:
        recoveries, _, service_values, total, _, health = self._service(step)
        return RestorationStep(
            step=step,
            units_restored=step,
            recovery_ratio=step / self._missing,
            depletion_ratio=(self._missing - step) / self._total_units,
            agent_recoveries=recoveries,
            agent_service_values=service_values,
            marginal_service_value=total - previous_total,
            cumulative_service_value=total,
            restoration_cost_so_far=step * self._cost_per_unit,
            ecosystem_health=health,
        )

    def _step(self, step: int) -> RestorationStep:
        cached = self._cache.get(step)
        if cached is None:
            cached = self._compute(step, self._total(step - 1))
            if len(self._cache) >= self._CACHE_SIZE:
                self._cache.clear()
            self._cache[step] = cached
        return cached

    def final_reversals_and_potential(self) -> tuple:
        """The last step's per-agent damage reversals and its biological
        recovery before the substrate cap (€/yr)."""
        _, reversals, _, _, potential, _ = self._service(self._units)
        return reversals, potential

    def __len__(self) -> int:
        return self._units

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self._step(i + 1) for i in range(*index.indices(self._units))]
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"step indices must be integers or slices, not {type(index).__name__}")
        if index < 0:
            index += self._units
        if not 0 <= index < self._units:
            raise IndexError("step index out of range")
        return self._step(index + 1)

    def __iter__(self) -> Iterator[RestorationStep]:
        previous_total: float = 0.0
        for step in range(1, self._units + 1):
            current = self._compute(step, previous_total)
            previous_total = current.cumulative_service_value
            yield current

    def __repr__(self) -> str:
        return f"<RestorationSteps: {self._units} steps>"


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
        they lost; amplifying recovery as well made them recover 1.6–4.1×
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

    Like extraction, restoration evaluates its final step directly; the
    other steps are computed if asked for (``result.steps``, a
    RestorationSteps). The damages come from the starting state's static
    damage function.

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

    steps = RestorationSteps(
        ecosystem, start, units_to_restore, recovery_functions,
        substrate_ceiling, restoration_cost.total_cost_per_unit,
    )
    reversals, annual_recovered_potential = steps.final_reversals_and_potential()
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

    discount = _resolve_discount(resource)
    npv_result, net_pv_by_horizon, breakeven, penalty = _restoration_money(
        ecosystem, restoration_cost, units_to_restore, total_cost,
        annual_recovered_potential, annual_damage_reversal,
        succession_curve, substrate_ceiling, discount,
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
        calibration=calibration_status(ecosystem, discount),
    )
