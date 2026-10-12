"""
Direct evaluation (decision D5, option B): the engine computes a step from
its depletion alone, lazily, so it must give exactly — bit for bit — what a
sequential per-unit loop gives. ``_reference_steps`` below is that loop (the
former pure-Python engine, written with the same phase functions); every
configuration compares every step field, the result fields and the
restoration built on it, with no tolerance at all.

The configurations exercise each damage-curve kind, keystones, trophic
levels, interactions, resilience, discounting and carbon, and every
substrate type × capacity function (they were the Cython parity configs).
"""

import dataclasses

import pytest

import gaia.simulation as sim
from gaia.cases.amazon_forest import build_amazon_ecosystem
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.forest import build_forest_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem
from gaia.damage import exponential_damage, logistic_damage, piecewise_damage
from gaia.models import (
    Agent,
    CalibrationRegime,
    CarbonProfile,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    ResilienceConfig,
    Resource,
    RestorationCost,
    SimulationStep,
    SubstrateProfile,
)
from gaia.recovery import logistic_recovery
from gaia.substrate import compute_capacity_fraction, create_substrate_state, degrade_substrate
from tests.golden_support import normalise


# ── Synthetic ecosystems ──────────────────────────────────────────────────────

_DAMAGE = {
    "logistic": lambda t: logistic_damage(threshold=t, steepness=12.0),
    "exponential": lambda t: exponential_damage(threshold=t, base=3.0),
    "piecewise": lambda t: piecewise_damage(threshold=t),
}
_MIXED = ["logistic", "exponential", "piecewise", "logistic"]


def _terrestrial(capacity_function: str, **overrides) -> SubstrateProfile:
    fields = dict(
        substrate_type="terrestrial_soil",
        soil_depth_cm=0.6,
        erosion_rate_unprotected=900.0,
        erosion_rate_protected=1.0,
        formation_rate=0.4,
        capacity_function=capacity_function,
        erosion_alpha=2.0,
        critical_minimum=0.3,
        residual_fraction=0.05,
    )
    fields.update(overrides)
    return SubstrateProfile(**fields)


def _marine(substrate_type: str, capacity_function: str, **overrides) -> SubstrateProfile:
    fields = dict(
        substrate_type=substrate_type,
        sediment_stability=0.85,
        erosion_rate_unprotected=60.0,
        erosion_rate_protected=0.5,
        formation_rate=1.0,
        capacity_function=capacity_function,
        erosion_alpha=3.0,
    )
    fields.update(overrides)
    return SubstrateProfile(**fields)


def _synthetic(
    damage="logistic",
    keystone=True,
    interactions=True,
    trophic=True,
    substrate=None,
    resilience=True,
    discount=False,
    total_units=400,
):
    """Four-agent ecosystem exercising every phase of the extraction loop."""
    kinds = _MIXED if damage == "mixed" else [damage] * 4
    specs = [
        # name, weight, rate, trophic level, threshold
        ("Producers", 0.4, 500_000.0, 0, 0.30),
        ("Grazers", 0.3, 300_000.0, 1, 0.25),
        ("Predators", 0.2, 200_000.0, 2, 0.20),
        ("Water", 0.1, 100_000.0, -1, 0.35),
    ]
    agents = [
        Agent(
            name=name,
            dependency_weight=weight,
            damage_function=_DAMAGE[kind](threshold),
            annual_value_per_ha=rate,
            description=name,
            trophic_level=level if trophic else -1,
            is_keystone=keystone and name == "Producers",
            keystone_threshold=0.6,
        )
        for (name, weight, rate, level, threshold), kind in zip(specs, kinds)
    ]
    edges = [
        ("Producers", "Grazers", 0.5),
        ("Producers", "Predators", 0.3),
        ("Grazers", "Predators", 0.4),
        ("Water", "Producers", 0.2),
    ]
    resource = Resource(
        area_ha=1.0,
        name="Synthetic",
        total_units=total_units,
        safe_threshold_ratio=0.3,
        unit_value=50.0,
        carbon_profile=(
            CarbonProfile(
                stored_carbon_tonnes=2.0,
                annual_absorption_tonnes=0.02,
                soil_carbon_tonnes=1.0,
                soil_release_fraction=0.3,
            )
            if discount else None
        ),
        resilience=ResilienceConfig() if resilience else None,
        substrate=substrate,
        discount=(
            DiscountConfig(rate_schedule=[(0, 0.04), (30, 0.03)], scarcity_rate=0.01)
            if discount else None
        ),
    )
    return Ecosystem(
        name="Synthetic",
        resource=resource,
        agents=agents,
        interactions=[
            InteractionEdge(s, t, k, "dependency", f"{s}->{t}")
            for s, t, k in edges
        ] if interactions else [],
        calibration_regime=CalibrationRegime.DIRECT_ONLY,
    )


# id → (ecosystem factory, units to extract)
CONFIGS = {
    # Shipped cases (extracting past the safe threshold)
    "forest": (lambda: build_forest_ecosystem(total_trees=2000), 1500),
    "forest_total": (lambda: build_forest_ecosystem(total_trees=500), 500),
    "costa_brava": (lambda: build_costa_brava_ecosystem(total_trees=2000), 1500),
    "posidonia": (lambda: build_posidonia_ecosystem(total_hectares=1000), 700),
    "amazon_forest": (lambda: build_amazon_ecosystem(total_trees=4000), 2000),
    # Damage-function kinds
    "dmg_logistic": (lambda: _synthetic("logistic"), 360),
    "dmg_exponential": (lambda: _synthetic("exponential"), 360),
    "dmg_piecewise": (lambda: _synthetic("piecewise"), 360),
    "dmg_mixed": (lambda: _synthetic("mixed"), 400),
    # Propagation variants
    "keystones_off": (lambda: _synthetic("mixed", keystone=False), 360),
    "no_interactions": (lambda: _synthetic("mixed", interactions=False), 360),
    "no_trophic": (lambda: _synthetic("mixed", trophic=False), 360),
    "bare_v02": (
        lambda: _synthetic("mixed", interactions=False, trophic=False,
                           resilience=False), 360,
    ),
    "single_step": (lambda: _synthetic("mixed"), 1),
    "discount_and_carbon": (lambda: _synthetic("mixed", discount=True), 300),
    # Substrate types × capacity functions
    "soil_linear": (lambda: _synthetic(substrate=_terrestrial("linear")), 380),
    "soil_threshold": (lambda: _synthetic(substrate=_terrestrial("threshold")), 380),
    "soil_logistic": (lambda: _synthetic(substrate=_terrestrial("logistic")), 380),
    "soil_zero_depth": (
        lambda: _synthetic(substrate=_terrestrial("linear", soil_depth_cm=0.0)), 200,
    ),
    "soil_threshold_shallow": (
        lambda: _synthetic(substrate=_terrestrial(
            "threshold", soil_depth_cm=0.2, critical_minimum=0.3)), 200,
    ),
    "sediment_linear": (
        lambda: _synthetic(substrate=_marine("marine_sediment", "linear")), 380,
    ),
    "sediment_logistic": (
        lambda: _synthetic(substrate=_marine("marine_sediment", "logistic")), 380,
    ),
    "matte_linear": (lambda: _synthetic(substrate=_marine("marine_matte", "linear")), 380),
    "matte_logistic": (
        lambda: _synthetic(substrate=_marine("marine_matte", "logistic")), 380,
    ),
    "matte_zero_stability": (
        lambda: _synthetic(substrate=_marine(
            "marine_matte", "logistic", sediment_stability=0.0)), 200,
    ),
    "substrate_with_discount": (
        lambda: _synthetic(substrate=_terrestrial("threshold"), discount=True), 300,
    ),
}


# ── The reference: a sequential per-unit loop ───────────────────────────────


def _reference_steps(ecosystem, units):
    """Every step, in order, carrying the previous total and the substrate
    state from one step to the next (the pre-D5 engine)."""
    resource = ecosystem.resource
    agents = ecosystem.agents
    total_units = resource.total_units
    damage_functions = [a.damage_function for a in agents]
    trophic_levels = [a.trophic_level for a in agents]
    has_trophic = any(lvl >= 1 for lvl in trophic_levels)
    weights = [a.dependency_weight for a in agents]
    values = [a.annual_value(resource.area_ha) for a in agents]
    network = sim._interaction_arrays(ecosystem)
    state = None
    if resource.substrate is not None:
        state = create_substrate_state(resource.substrate)
    steps = []
    previous_total = 0.0
    for step in range(1, units + 1):
        depletion = step / total_units
        direct = sim._compute_damage(damage_functions, trophic_levels, has_trophic, depletion)
        effective, cascade, keystone = sim._propagate(network, direct)
        price_result, prices = None, []
        if ecosystem.pricing is not None:
            price_result, prices = sim._price(
                ecosystem, ecosystem.pricing, network["agent_names"], effective, step)
        costs, total, health = sim._annual_costs(
            effective, weights, prices if ecosystem.pricing is not None else values)
        if state is None:
            erosion, effective_k, k_fraction = 0.0, total_units, 1.0
        else:
            erosion = degrade_substrate(state, (total_units - step) / total_units,
                                        years=1.0 / units)
            k_fraction = compute_capacity_fraction(state)
            effective_k = int(total_units * k_fraction)
        zone, confidence, irreversible = sim._resilience(resource, depletion)
        steps.append(SimulationStep(
            step=step, units_extracted=step, depletion_ratio=depletion,
            agent_damages=effective, agent_annual_costs=costs,
            marginal_annual_externality=total - previous_total,
            annual_externality=total, revenue=step * resource.unit_value,
            ecosystem_health=health, agent_direct_damages=direct,
            agent_cascade_damages=cascade, keystone_triggered=keystone,
            resilience_zone=zone, model_confidence=confidence,
            irreversibility_warning=irreversible, substrate_erosion=erosion,
            effective_k=effective_k, k_fraction=k_fraction,
            agent_prices=prices, price_result=price_result,
        ))
        previous_total = total
    return steps, state


def _same(a, b):
    """Exact equality of normalised trees (no tolerance; NaN-free)."""
    return normalise(a) == normalise(b)


@pytest.mark.parametrize("config", list(CONFIGS))
def test_direct_evaluation_equals_the_sequential_loop(config):
    factory, units = CONFIGS[config]
    ecosystem = factory()
    result = sim.run_extraction(ecosystem, units)
    reference, state = _reference_steps(ecosystem, units)

    assert len(result.steps) == units
    # iteration, indexing (in a scrambled order) and slicing agree with the loop
    assert _same(list(result.steps), reference)
    for k in sorted(range(units), key=lambda i: (i * 7919) % units):
        assert _same(result.steps[k], reference[k]), (config, k)
    assert _same(result.steps[-1], reference[-1])
    assert _same(result.steps[::max(units // 7, 1)], reference[::max(units // 7, 1)])

    # summary fields come from the final step
    final = reference[-1]
    assert result.annual_externality == final.annual_externality
    assert result.final_ecosystem_health == final.ecosystem_health
    assert result.final_model_confidence == final.model_confidence
    end = sim.substrate_after_extraction(result)
    if state is None:
        assert end is None
    else:
        assert dataclasses.asdict(end) == dataclasses.asdict(state)

    # the scans the report uses
    crossings = {}
    for s in reference:
        for name in s.keystone_triggered:
            crossings.setdefault(name, s.step)
    assert sim.keystone_crossings(result.steps) == crossings
    assert sim.keystone_crossings(reference) == crossings
    assert sim.zone_transitions(result.steps) == sim.zone_transitions(reference)
    assert (sim.first_irreversible_step(result.steps)
            == sim.first_irreversible_step(reference))


@pytest.mark.parametrize("config", ["forest", "posidonia", "dmg_mixed", "matte_logistic",
                                    "soil_threshold"])
def test_restoration_steps_equal_the_sequential_loop(config):
    """Lazy restoration steps match a loop over the reference extraction."""
    factory, units = CONFIGS[config]
    ecosystem = factory()
    restore = max(units // 2, 1)
    recovery = [logistic_recovery(threshold=0.3) for _ in ecosystem.agents]
    result = sim.run_restoration(ecosystem, restore, RestorationCost(50.0, 5.0, 10),
                                 recovery, units_lost=units)
    reference, _ = _reference_steps(ecosystem, units)
    before = reference[-1].agent_damages
    ceiling = reference[-1].k_fraction if ecosystem.resource.substrate else 1.0
    weights = [a.dependency_weight for a in ecosystem.agents]
    values = [a.annual_value(ecosystem.resource.area_ha) for a in ecosystem.agents]
    previous = 0.0
    lazy = list(result.steps)
    for j in range(1, restore + 1):
        now = reference[units - j - 1].agent_damages if units - j > 0 else [0.0] * len(before)
        total = 0.0
        for i, fn in enumerate(recovery):
            reversal = max(before[i] - now[i], 0.0)
            total += fn(j / units) * reversal * ceiling * weights[i] * values[i]
        step = lazy[j - 1]
        assert step.cumulative_service_value == total
        assert step.marginal_service_value == total - previous
        assert _same(result.steps[j - 1], step)
        previous = total
    assert result.annual_recovered_value == lazy[-1].cumulative_service_value


def test_pricing_steps_equal_the_sequential_loop():
    """EXPERIMENTAL pricing: the certified prices of every step, unchanged."""
    ecosystem = build_forest_ecosystem(total_trees=400, with_pricing=True)
    result = sim.run_extraction(ecosystem, 200)
    reference, _ = _reference_steps(ecosystem, 200)
    assert _same(list(result.steps), reference)
    assert _same(result.steps[57], reference[57])


def test_steps_are_a_read_only_sequence():
    result = sim.run_extraction(_synthetic("mixed"), 50)
    steps = result.steps
    assert isinstance(steps, sim.ExtractionSteps)
    assert len(steps) == 50 and steps[-1].step == 50 and steps[0].step == 1
    assert steps[-1] is steps[-1]  # cached
    with pytest.raises(IndexError):
        steps[50]
    with pytest.raises(IndexError):
        steps[-51]
    with pytest.raises(TypeError):
        steps["1"]
    assert list(steps[48:]) == [steps[48], steps[49]]
    assert not sim.run_extraction(_synthetic("mixed"), 0).steps


def test_restoration_checks_every_recovery_ratio():
    """A recovery function out of [0, 1] at an intermediate ratio is still
    rejected, although only the final step is built."""
    ecosystem = _synthetic("mixed")

    def bump(r):
        return 1.5 if 0.4 < r < 0.5 else r

    with pytest.raises(ValueError, match=r"efficiency must be in \[0, 1\]"):
        sim.run_restoration(ecosystem, 100, RestorationCost(50.0, 5.0, 10),
                            [bump] * len(ecosystem.agents), units_lost=100)


def test_configs_exercise_every_branch():
    """The configurations cover each curve kind, substrate type and capacity fn."""
    kinds, substrates = set(), set()
    for factory, _ in CONFIGS.values():
        eco = factory()
        kinds |= {a.damage_function.kernel[0] for a in eco.agents}
        sub = eco.resource.substrate
        if sub is not None:
            substrates.add((sub.substrate_type, sub.capacity_function))
    assert kinds == {0, 1, 2}
    assert substrates >= {
        ("terrestrial_soil", "linear"), ("terrestrial_soil", "threshold"),
        ("terrestrial_soil", "logistic"), ("marine_sediment", "linear"),
        ("marine_sediment", "logistic"), ("marine_matte", "linear"),
        ("marine_matte", "logistic"),
    }
