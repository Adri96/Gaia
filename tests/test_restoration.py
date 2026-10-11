"""
Gaia v0.2 — Restoration simulation tests.

These tests verify the run_restoration() engine and the core economic claim of v0.2:
    - Recovered service value increases monotonically with units restored
    - Total restoration cost increases monotonically
    - Prevention is cheaper than destroy + restore (prevention_advantage > 1.0)
    - Net restoration value is positive (restoration generates net social value)
    - Partial restoration recovers partial services (not all-or-nothing)
    - Full restoration approaches maximum service recovery
    - Step 3.3: restoration starts from a real state (an extraction result)
      and recovers at most the reversal of the damage
"""

import dataclasses

import pytest
from gaia.cases.forest import build_forest_ecosystem
from gaia.models import RestorationCost
from gaia.recovery import logistic_recovery, linear_recovery
from gaia.simulation import run_extraction, run_restoration


# ── Fixtures ─────────────────────────────────────────────────────────────────────

TOTAL_TREES = 10_000
THRESHOLD = 0.3
TREE_VALUE = 100.0

# Plausible forest restoration costs [PLACEHOLDER]
# €50/tree planting + €10/tree/year × 10 years = €150/tree total
RESTORATION_COST = RestorationCost(
    planting_cost_per_unit=50.0,
    annual_maintenance_per_unit=10.0,
    maintenance_years=10,
)


def _make_ecosystem():
    return build_forest_ecosystem(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        tree_value=TREE_VALUE,
    )


def _make_recovery_fns(eco, factory=None, **kwargs):
    """One recovery function per agent, same function for all."""
    if factory is None:
        factory = logistic_recovery
        kwargs = {"threshold": THRESHOLD}
    return [factory(**kwargs) for _ in eco.agents]


# ── RestorationCost model ────────────────────────────────────────────────────────

def test_restoration_cost_total_per_unit():
    """total_cost_per_unit = planting + (annual_maintenance * years)."""
    cost = RestorationCost(
        planting_cost_per_unit=50.0,
        annual_maintenance_per_unit=10.0,
        maintenance_years=10,
    )
    assert cost.total_cost_per_unit == 150.0


def test_restoration_cost_no_maintenance():
    """Zero maintenance years: total cost = planting cost only."""
    cost = RestorationCost(
        planting_cost_per_unit=80.0,
        annual_maintenance_per_unit=20.0,
        maintenance_years=0,
    )
    assert cost.total_cost_per_unit == 80.0


# ── Basic engine correctness ─────────────────────────────────────────────────────

def test_restoration_step_count():
    """Number of steps equals units_to_restore."""
    eco = _make_ecosystem()
    result = run_restoration(eco, 3_000, RESTORATION_COST, _make_recovery_fns(eco))
    assert len(result.steps) == 3_000
    assert result.steps[0].step == 1
    assert result.steps[-1].step == 3_000


def test_restoration_units_restored():
    """total_units_restored is recorded correctly."""
    eco = _make_ecosystem()
    result = run_restoration(eco, 2_500, RESTORATION_COST, _make_recovery_fns(eco))
    assert result.total_units_restored == 2_500


def test_restoration_cost_accumulation():
    """Total restoration cost = units_restored × cost_per_unit."""
    eco = _make_ecosystem()
    n = 1_000
    result = run_restoration(eco, n, RESTORATION_COST, _make_recovery_fns(eco))
    expected_cost = n * RESTORATION_COST.total_cost_per_unit
    assert abs(result.total_restoration_cost - expected_cost) < 1e-6, (
        f"Expected cost {expected_cost:.2f}, got {result.total_restoration_cost:.2f}"
    )


def test_restoration_cost_monotone():
    """restoration_cost_so_far increases with every step."""
    eco = _make_ecosystem()
    result = run_restoration(eco, 500, RESTORATION_COST, _make_recovery_fns(eco))
    costs = [s.restoration_cost_so_far for s in result.steps]
    for i in range(1, len(costs)):
        assert costs[i] > costs[i - 1], (
            f"Restoration cost should increase at step {i + 1}"
        )


# ── Recovered service value ──────────────────────────────────────────────────────

def test_recovered_value_monotone():
    """Cumulative recovered service value increases with every step."""
    eco = _make_ecosystem()
    result = run_restoration(eco, 1_000, RESTORATION_COST, _make_recovery_fns(eco))
    values = [s.cumulative_service_value for s in result.steps]
    for i in range(1, len(values)):
        assert values[i] >= values[i - 1] - 1e-9, (
            f"Recovered service value should not decrease at step {i + 1}"
        )


def test_recovered_value_positive():
    """Total recovered service value is always positive."""
    eco = _make_ecosystem()
    result = run_restoration(eco, 5_000, RESTORATION_COST, _make_recovery_fns(eco))
    assert result.annual_recovered_value > 0


def test_full_restoration_recovers_near_max():
    """
    Restoring all units approaches the maximum possible service recovery.

    With logistic_recovery, f(1.0) ≈ 1.0, so full restoration recovers
    approximately 100% of ecosystem services (modulo the function's boundary
    tolerance).
    """
    eco = _make_ecosystem()
    result = run_restoration(
        eco, TOTAL_TREES, RESTORATION_COST, _make_recovery_fns(eco)
    )
    # Maximum possible recovery = sum(weight * rate) ≈ total_max_externality
    # At full restoration, should be near the theoretical maximum
    assert result.final_ecosystem_health > 0.95, (
        f"Full restoration should recover >95% ecosystem health, "
        f"got {result.final_ecosystem_health:.1%}"
    )


def test_partial_restoration_partial_recovery():
    """
    At the midpoint of a restoration run, ecosystem health is non-trivially > 0.

    This verifies that restoration is not all-or-nothing — partial planting
    produces partial recovery. We compare ecosystem health at the halfway step
    of two runs with different totals:

    - half-run (5,000 trees lost and restored): at step 2,500,
      recovery_ratio=0.5 and depletion 0.5 → 0.25
    - full-run (10,000 trees lost and restored): at step 2,500,
      recovery_ratio=0.25 and depletion 1.0 → 0.75 → less health

    Each run starts from the state its own extraction left (units lost =
    units restored), so the half-run starts healthier and recovers faster.
    """
    eco = _make_ecosystem()
    fns = _make_recovery_fns(eco)
    result_half = run_restoration(eco, TOTAL_TREES // 2, RESTORATION_COST, fns)
    result_full = run_restoration(eco, TOTAL_TREES, RESTORATION_COST, fns)

    # At the same absolute step (2,500 trees planted), the half-run is at
    # recovery_ratio=0.5 and the full-run is at recovery_ratio=0.25.
    # Logistic recovery: f(0.5) >> f(0.25), so health_half > health_full at this step.
    midpoint_idx = (TOTAL_TREES // 2) // 2 - 1  # step 2500 → index 2499
    health_half_at_mid = result_half.steps[midpoint_idx].ecosystem_health
    health_full_at_mid = result_full.steps[midpoint_idx].ecosystem_health

    assert health_half_at_mid > health_full_at_mid, (
        f"At step {midpoint_idx + 1}: half-run health ({health_half_at_mid:.4f}) "
        f"should exceed full-run health ({health_full_at_mid:.4f}) — "
        f"50%-ratio recovery > 25%-ratio recovery"
    )


# ── Net restoration value ────────────────────────────────────────────────────────

def test_net_restoration_value_positive():
    """
    Net restoration value (recovered - cost) is positive.

    This is the core social investment claim: restoring an ecosystem costs less
    than the ecosystem services it recovers. Society gains more than it spends.
    """
    eco = _make_ecosystem()
    result = run_restoration(eco, 5_000, RESTORATION_COST, _make_recovery_fns(eco))
    assert result.net_restoration_pv > 0, (
        f"Net restoration value should be positive (restoration is a social good). "
        f"Got recovered={result.annual_recovered_value:.2f}, "
        f"cost={result.total_restoration_cost:.2f}, "
        f"net={result.net_restoration_pv:.2f}"
    )


# ── Prevention advantage ─────────────────────────────────────────────────────────

def test_prevention_advantage_greater_than_one():
    """
    Prevention advantage > 1.0: it is always cheaper to not cut than to cut and restore.

    prevention_advantage = (foregone_revenue + restoration_cost) / foregone_revenue
    If restoration_cost > 0, the ratio is always > 1.0.
    The advantage grows with the cost of restoration.
    """
    eco = _make_ecosystem()
    result = run_restoration(eco, 5_000, RESTORATION_COST, _make_recovery_fns(eco))
    assert result.prevention_advantage > 1.0, (
        f"Prevention advantage should be > 1.0, got {result.prevention_advantage:.2f}"
    )


def test_prevention_advantage_increases_with_restoration_cost():
    """
    Higher restoration cost → higher prevention advantage.

    If replanting costs more, it becomes relatively even cheaper to have
    prevented the destruction in the first place.
    """
    eco = _make_ecosystem()
    fns = _make_recovery_fns(eco)

    cheap_cost = RestorationCost(
        planting_cost_per_unit=20.0,
        annual_maintenance_per_unit=5.0,
        maintenance_years=5,
    )
    expensive_cost = RestorationCost(
        planting_cost_per_unit=100.0,
        annual_maintenance_per_unit=30.0,
        maintenance_years=20,
    )

    result_cheap = run_restoration(eco, 3_000, cheap_cost, fns)
    result_expensive = run_restoration(eco, 3_000, expensive_cost, fns)

    assert result_expensive.prevention_advantage > result_cheap.prevention_advantage, (
        f"Expensive restoration ({result_expensive.prevention_advantage:.2f}×) "
        f"should have higher prevention advantage than cheap ({result_cheap.prevention_advantage:.2f}×)"
    )


def test_prevention_advantage_numeric():
    """
    Verify the prevention advantage formula with known values.

    With 5,000 trees at €100/tree (€500k foregone revenue) and €150/tree
    restoration cost (€750k total): advantage = (500k + 750k) / 500k = 2.5×
    """
    eco = _make_ecosystem()
    fns = _make_recovery_fns(eco)
    result = run_restoration(eco, 5_000, RESTORATION_COST, fns)

    foregone_revenue = 5_000 * TREE_VALUE  # 500,000
    expected_advantage = (foregone_revenue + result.total_restoration_cost) / foregone_revenue
    assert abs(result.prevention_advantage - expected_advantage) < 1e-6


# ── Validation ───────────────────────────────────────────────────────────────────

def test_restoration_rejects_zero_units():
    """Restoring 0 units is not a valid restoration."""
    eco = _make_ecosystem()
    with pytest.raises(ValueError):
        run_restoration(eco, 0, RESTORATION_COST, _make_recovery_fns(eco))


def test_restoration_rejects_too_many_units():
    """Cannot restore more units than the ecosystem's total capacity."""
    eco = _make_ecosystem()
    with pytest.raises(ValueError):
        run_restoration(eco, TOTAL_TREES + 1, RESTORATION_COST, _make_recovery_fns(eco))


def test_restoration_rejects_wrong_number_of_recovery_functions():
    """recovery_functions must have one entry per agent."""
    eco = _make_ecosystem()
    with pytest.raises(ValueError, match="recovery_functions"):
        run_restoration(eco, 1_000, RESTORATION_COST, [logistic_recovery(threshold=THRESHOLD)])


# ── Recovery function variants ───────────────────────────────────────────────────

def test_restoration_with_linear_recovery():
    """run_restoration works with linear_recovery functions."""
    eco = _make_ecosystem()
    fns = [linear_recovery(slope=0.8) for _ in eco.agents]
    result = run_restoration(eco, 3_000, RESTORATION_COST, fns)
    assert result.annual_recovered_value > 0
    assert result.total_restoration_cost > 0
    # Net restoration value is a PV (benefits − costs), never the annual
    # recovered flow minus the one-off cost
    assert result.net_restoration_pv == result.restoration_npv.net_present_value


def test_logistic_recovery_slower_than_linear():
    """
    Logistic recovery with inflection at 60% recovers less service at 30% progress
    than linear recovery with slope=1.0.

    The logistic curve is still in its slow early phase at 30% restoration
    (below the inflection at 60%), while linear recovery has already delivered
    30% of services. This confirms the entropy asymmetry encoding.
    """
    eco = _make_ecosystem()
    logistic_fns = _make_recovery_fns(eco, logistic_recovery, threshold=THRESHOLD)
    linear_fns = [linear_recovery(slope=1.0) for _ in eco.agents]

    # Compare at 30% of the restoration journey
    restore_n = 3_000
    result_logistic = run_restoration(eco, restore_n, RESTORATION_COST, logistic_fns)
    result_linear = run_restoration(eco, restore_n, RESTORATION_COST, linear_fns)

    # At 30% restoration (step 900 = 30% of 3000):
    step_idx = 900 - 1  # 0-indexed
    logistic_at_30 = result_logistic.steps[step_idx].cumulative_service_value
    linear_at_30 = result_linear.steps[step_idx].cumulative_service_value

    assert logistic_at_30 < linear_at_30, (
        f"Logistic recovery at 30% progress ({logistic_at_30:.2f}) should recover "
        f"less than linear at 30% ({linear_at_30:.2f}) — entropy asymmetry"
    )


# ── Step 3.3: restoration from a real starting state (C1) ────────────────────

SMALL_TREES = 1_000


def _small():
    eco = build_forest_ecosystem(
        total_trees=SMALL_TREES, safe_threshold_ratio=THRESHOLD, tree_value=TREE_VALUE,
    )
    return eco, _make_recovery_fns(eco)


def test_chaining_from_extraction_result():
    """A restoration chained from an extraction starts from its end state."""
    eco, fns = _small()
    cut = run_extraction(eco, 800)
    result = run_restoration(eco, 300, RESTORATION_COST, fns, starting_state=cut)

    assert result.units_lost == 800
    assert result.depletion_before == pytest.approx(0.8)
    assert result.depletion_after == pytest.approx(0.5)
    assert result.initial_ecosystem_health == cut.final_ecosystem_health
    assert result.steps[-1].depletion_ratio == pytest.approx(0.5)
    # Upper bound = externality before − after, same damage model
    after = run_extraction(eco, 500)
    assert result.annual_damage_reversal == pytest.approx(
        cut.annual_externality - after.annual_externality, rel=1e-12)
    assert result.substrate_ceiling == cut.steps[-1].k_fraction

    # units_lost derives the same state as chaining
    same = run_restoration(eco, 300, RESTORATION_COST, fns, units_lost=800)
    assert same.annual_recovered_value == result.annual_recovered_value
    assert same.final_ecosystem_health == result.final_ecosystem_health
    assert same.substrate_recovery_years == result.substrate_recovery_years


def test_default_starting_state_restores_what_was_cut():
    eco, fns = _small()
    default = run_restoration(eco, 400, RESTORATION_COST, fns)
    chained = run_restoration(eco, 400, RESTORATION_COST, fns,
                              starting_state=run_extraction(eco, 400))
    assert default.units_lost == 400
    assert default.annual_recovered_value == chained.annual_recovered_value


@pytest.mark.parametrize("kwargs", [
    {"units_lost": 299},
    {"units_lost": 0},
])
def test_restoring_more_than_missing_rejected(kwargs):
    eco, fns = _small()
    with pytest.raises(ValueError, match="cannot exceed the units missing"):
        run_restoration(eco, 300, RESTORATION_COST, fns, **kwargs)


def test_restoring_more_than_missing_rejected_when_chained():
    eco, fns = _small()
    cut = run_extraction(eco, 100)
    with pytest.raises(ValueError, match="cannot exceed the units missing"):
        run_restoration(eco, 101, RESTORATION_COST, fns, starting_state=cut)


def test_starting_state_arguments_validated():
    eco, fns = _small()
    cut = run_extraction(eco, 100)
    with pytest.raises(ValueError, match="not both"):
        run_restoration(eco, 50, RESTORATION_COST, fns,
                        starting_state=cut, units_lost=100)
    other, _ = _small()
    with pytest.raises(ValueError, match="ecosystem being restored"):
        run_restoration(other, 50, RESTORATION_COST, fns, starting_state=cut)
    with pytest.raises(ValueError, match="units_lost"):
        run_restoration(eco, 50, RESTORATION_COST, fns, units_lost=SMALL_TREES + 1)


def test_final_health_below_one_when_degraded_and_efficiency_below_one():
    """Replanting every lost unit at 80% efficiency leaves 20% of the damage."""
    eco, _ = _small()
    fns = [linear_recovery(slope=0.8) for _ in eco.agents]
    cut = run_extraction(eco, 600)
    result = run_restoration(eco, 600, RESTORATION_COST, fns, starting_state=cut)

    assert result.depletion_after == 0.0
    assert cut.final_ecosystem_health < result.final_ecosystem_health < 1.0
    # The substrate ceiling of the starting state caps recovery at maturity
    ceiling = result.substrate_ceiling
    assert ceiling == cut.steps[-1].k_fraction < 1.0
    assert result.annual_recovered_value == pytest.approx(
        0.8 * ceiling * result.annual_damage_reversal, rel=1e-12)
    expected_health = 1.0 - (1.0 - 0.8 * ceiling) * (1.0 - cut.final_ecosystem_health)
    assert result.final_ecosystem_health == pytest.approx(expected_health, rel=1e-9)


def test_full_efficiency_health_is_damage_model_health_at_depletion_after():
    """With efficiency 1 and an intact substrate, health after restoring is the
    extraction's health there."""
    eco, _ = _small()
    eco.resource = dataclasses.replace(eco.resource, substrate=None)
    fns = [lambda r: 1.0 for _ in eco.agents]
    result = run_restoration(eco, 300, RESTORATION_COST, fns, units_lost=700)
    reference = run_extraction(eco, 400)
    assert result.final_ecosystem_health == pytest.approx(
        reference.final_ecosystem_health, rel=1e-12)
    assert result.annual_recovered_value == pytest.approx(
        result.annual_damage_reversal, rel=1e-12)


def test_recovered_value_strictly_monotonic_in_units_restored():
    eco, fns = _small()
    cut = run_extraction(eco, 1_000)
    values = [
        run_restoration(eco, k, RESTORATION_COST, fns,
                        starting_state=cut).annual_recovered_value
        for k in (1, 10, 100, 400, 700, 1_000)
    ]
    assert all(a < b for a, b in zip(values, values[1:])), values
    # And every cost-of-cutting bound holds along the way
    for k, v in zip((1, 10, 100, 400, 700, 1_000), values):
        reversal = cut.annual_externality - (
            run_extraction(eco, 1_000 - k).annual_externality)
        assert v <= reversal * (1 + 1e-12)


def test_downstream_values_scale_with_recovered_value():
    """Maturation gap and service PV follow the recovered value (C1 / C2)."""
    from gaia.cases.forest import _FOREST_SUCCESSION
    eco, fns = _small()
    cut = run_extraction(eco, 1_000)
    small = run_restoration(eco, 500, RESTORATION_COST, fns, starting_state=cut,
                            succession_curve=_FOREST_SUCCESSION, time_horizon_years=60)
    full = run_restoration(eco, 1_000, RESTORATION_COST, fns, starting_state=cut,
                           succession_curve=_FOREST_SUCCESSION, time_horizon_years=60)
    ratio = small.annual_recovered_value / full.annual_recovered_value
    assert ratio < 0.5
    assert small.maturation_gap_pv == pytest.approx(ratio * full.maturation_gap_pv, rel=1e-9)
    assert small.restoration_npv.service_benefits == pytest.approx(
        ratio * full.restoration_npv.service_benefits, rel=1e-9)


def test_recovery_not_trophically_amplified():
    """Each agent regains at most what it lost — consumers do not recover faster."""
    eco, fns = _small()
    cut = run_extraction(eco, 500)
    result = run_restoration(eco, 500, RESTORATION_COST, fns, starting_state=cut)
    for recovered, lost in zip(result.steps[-1].agent_service_values,
                               cut.steps[-1].agent_annual_costs):
        assert recovered == pytest.approx(lost * result.substrate_ceiling, rel=1e-12)
    assert result.annual_recovered_value <= cut.annual_externality


def test_substrate_caps_recovery_once():
    """Substrate model: the ceiling caps the mature value and health, and the
    yearly streams deliver min(s(t), ceiling) of the biological recovery —
    the permanent shortfall is not counted again in the maturation gap."""
    from gaia.cases.forest import _FOREST_SUCCESSION
    from gaia.succession import succession_service
    eco, fns = _small()
    intact = dataclasses.replace(eco.resource, substrate=None)
    cut = run_extraction(eco, 1_000)
    with_soil = run_restoration(eco, 1_000, RESTORATION_COST, fns, starting_state=cut,
                                succession_curve=_FOREST_SUCCESSION, time_horizon_years=60)
    eco_intact, _ = _small()
    eco_intact.resource = intact
    no_soil = run_restoration(eco_intact, 1_000, RESTORATION_COST, fns,
                              succession_curve=_FOREST_SUCCESSION, time_horizon_years=60)
    c = with_soil.substrate_ceiling
    assert 0.0 < c < 1.0
    assert with_soil.annual_recovered_value == pytest.approx(
        c * no_soil.annual_recovered_value, rel=1e-12)
    for a, b in zip(with_soil.maturation_timeline, no_soil.maturation_timeline):
        s = succession_service(_FOREST_SUCCESSION, float(a.year))
        assert a.annual_service_value == pytest.approx(
            no_soil.annual_recovered_value * min(s, c), rel=1e-12)
        # gap against the capped mature value is never negative
        assert a.annual_service_value <= with_soil.annual_recovered_value * (1 + 1e-12)


def test_recovery_efficiency_outside_unit_interval_rejected():
    eco, _ = _small()
    fns = [lambda r: 1.5 * r for _ in eco.agents]
    with pytest.raises(ValueError, match=r"efficiency must be in \[0, 1\]"):
        run_restoration(eco, 100, RESTORATION_COST, fns)
