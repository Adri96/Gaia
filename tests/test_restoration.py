"""
Gaia v0.2 — Restoration simulation tests.

These tests verify the run_restoration() engine and the core economic claim of v0.2:
    - Recovered service value increases monotonically with units restored
    - Total restoration cost increases monotonically
    - Prevention is cheaper than destroy + restore (prevention_advantage > 1.0)
    - Net restoration value is positive (restoration generates net social value)
    - Partial restoration recovers partial services (not all-or-nothing)
    - Full restoration approaches maximum service recovery
"""

import pytest
from gaia.cases.forest import build_forest_ecosystem
from gaia.models import RestorationCost
from gaia.recovery import logistic_recovery, linear_recovery
from gaia.simulation import run_restoration


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
    assert result.total_recovered_value > 0


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

    - half-run (5,000 trees): at step 2,500, recovery_ratio=0.5 → health > 0
    - full-run (10,000 trees): at step 2,500, recovery_ratio=0.25 → less health

    Since recovery is monotone and logistic, health at ratio=0.5 > health at
    ratio=0.25, confirming partial restoration is partial (not all-or-nothing).
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
    assert result.net_restoration_value > 0, (
        f"Net restoration value should be positive (restoration is a social good). "
        f"Got recovered={result.total_recovered_value:.2f}, "
        f"cost={result.total_restoration_cost:.2f}, "
        f"net={result.net_restoration_value:.2f}"
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
    assert result.total_recovered_value > 0
    assert result.total_restoration_cost > 0
    assert result.net_restoration_value == (
        result.total_recovered_value - result.total_restoration_cost
    )


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
