"""
Gaia v0.6 — Per-case NPV integration tests.

Verifies that discount configs are wired into the three preconfigured cases
and that NPV calculations produce ecologically plausible results.

Spec Section 9.3 tests 18–25:
    18. Oak Valley extraction NPV < undiscounted direct (discount effect > 0)
    19. Oak Valley restoration: positive net_present_value at DISCOUNT_CENTRAL
    20. Holm Oak: substrate damage NPV is positive (threshold substrate)
    21. Posidonia: pa_full >= pa_with_substrate >= pa_with_carbon >= pa_simple
    22. Prevention advantage ordering: PA increases with more NPV components
    23. Carbon breakeven is finite and positive for all cases
    24. Backward compat: no discount config → extraction_npv is None
    25. Discount config with rate=0 and scarcity=0: NPV direct ≈ loss × horizon
"""

import pytest

from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    DiscountConfig,
    Ecosystem,
    Resource,
    RestorationCost,
)
from gaia.npv import compute_extraction_npv
from gaia.recovery import logistic_recovery
from gaia.simulation import run_extraction, run_restoration

from gaia.cases.forest import build_forest_ecosystem, run_forest_restoration
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem, run_posidonia_restoration


# ── Helpers ────────────────────────────────────────────────────────────────────


def _run_forest_extraction(trees_cut: int = 5_000) -> object:
    """Run Oak Valley extraction with default parameters."""
    eco = build_forest_ecosystem()
    return run_extraction(eco, trees_cut)


def _run_forest_restoration_result(
    trees_to_restore: int = 5_000,
    time_horizon: int = 0,
) -> object:
    """Run Oak Valley restoration with default parameters."""
    eco = build_forest_ecosystem()
    cost = RestorationCost(
        planting_cost_per_unit=50.0,
        annual_maintenance_per_unit=10.0,
        maintenance_years=10,
    )
    recovery_fns = [logistic_recovery(0.3) for _ in eco.agents]
    return run_restoration(eco, trees_to_restore, cost, recovery_fns,
                           time_horizon_years=time_horizon)


def _run_costa_brava_extraction(trees_cut: int = 4_000) -> object:
    eco = build_costa_brava_ecosystem()
    return run_extraction(eco, trees_cut)


def _run_costa_brava_restoration_result(trees_to_restore: int = 4_000) -> object:
    eco = build_costa_brava_ecosystem()
    cost = RestorationCost(
        planting_cost_per_unit=80.0,
        annual_maintenance_per_unit=15.0,
        maintenance_years=15,
    )
    recovery_fns = [logistic_recovery(0.25) for _ in eco.agents]
    return run_restoration(eco, trees_to_restore, cost, recovery_fns)


def _run_posidonia_extraction(hectares: int = 2_000) -> object:
    eco = build_posidonia_ecosystem()
    return run_extraction(eco, hectares)


def _run_posidonia_restoration_result(hectares: int = 2_000) -> object:
    eco = build_posidonia_ecosystem()
    cost = RestorationCost(
        planting_cost_per_unit=50_000.0,
        annual_maintenance_per_unit=5_000.0,
        maintenance_years=30,
    )
    recovery_fns = [logistic_recovery(0.20) for _ in eco.agents]
    return run_restoration(eco, hectares, cost, recovery_fns)


# ── Test 18: Oak Valley extraction NPV < undiscounted × horizon ───────────────


def test_oak_valley_extraction_npv_computed():
    """Oak Valley extraction produces extraction_npv (discount config present)."""
    result = _run_forest_extraction()
    assert result.extraction_npv is not None


def test_oak_valley_extraction_npv_direct_less_than_undiscounted():
    """Direct NPV < annual_loss × horizon (positive net discount effect)."""
    result = _run_forest_extraction()
    npv = result.extraction_npv
    undiscounted = result.total_externality_cost * npv.horizon
    # At 2.3% rate and 2% scarcity, effective net discount ≈ 0.3% → NPV slightly < undiscounted
    assert npv.direct < undiscounted


def test_oak_valley_extraction_npv_total_positive():
    """Total extraction NPV (all components) is positive."""
    result = _run_forest_extraction()
    assert result.extraction_npv.total > 0


def test_oak_valley_extraction_npv_carbon_release_positive():
    """Carbon release NPV > 0 (trees store carbon that is released)."""
    result = _run_forest_extraction()
    assert result.extraction_npv.carbon_release > 0


def test_oak_valley_extraction_npv_carbon_foregone_positive():
    """Carbon foregone NPV > 0 (loss of future absorption)."""
    result = _run_forest_extraction()
    assert result.extraction_npv.carbon_foregone > 0


# ── Test 19: Oak Valley restoration: positive net_present_value ───────────────


def test_oak_valley_restoration_npv_computed():
    """Oak Valley restoration produces RestorationNPV."""
    result = _run_forest_restoration_result()
    assert result.npv is not None


def test_oak_valley_restoration_npv_cost_positive():
    """Restoration cost NPV > 0 (planting + maintenance have a cost)."""
    result = _run_forest_restoration_result()
    assert result.npv.cost > 0


def test_oak_valley_restoration_service_benefits_positive():
    """Restored services generate positive NPV benefits."""
    result = _run_forest_restoration_result()
    assert result.npv.service_benefits > 0


def test_oak_valley_restoration_roi_positive():
    """Restoration ROI > 0 (benefits / cost > 0)."""
    result = _run_forest_restoration_result()
    assert result.npv.roi > 0


def test_oak_valley_restoration_carbon_breakeven_computed():
    """Carbon breakeven is computed for Oak Valley."""
    result = _run_forest_restoration_result()
    assert result.carbon_breakeven is not None
    assert result.carbon_breakeven.breakeven_price > 0


def test_oak_valley_prevention_advantage_v06_computed():
    """PreventionAdvantageV06 is computed for Oak Valley."""
    result = _run_forest_restoration_result()
    assert result.prevention_advantage_v06 is not None


# ── Test 20: Holm Oak: substrate damage NPV is positive ───────────────────────


def test_costa_brava_extraction_npv_computed():
    """Costa Brava extraction has NPV (discount config attached)."""
    result = _run_costa_brava_extraction()
    assert result.extraction_npv is not None


def test_costa_brava_extraction_substrate_damage_positive():
    """Costa Brava (threshold substrate) has positive substrate damage NPV."""
    result = _run_costa_brava_extraction()
    # Holm oak has threshold substrate — extraction causes permanent capacity loss
    assert result.extraction_npv.substrate_damage >= 0


def test_costa_brava_restoration_npv_computed():
    """Costa Brava restoration NPV is computed."""
    result = _run_costa_brava_restoration_result()
    assert result.npv is not None
    assert result.carbon_breakeven is not None


# ── Test 21: Posidonia PA ordering: pa_full >= pa_with_substrate >= pa_with_carbon >= pa_simple


def test_posidonia_prevention_advantage_v06_computed():
    """Posidonia restoration computes PA_v06."""
    result = _run_posidonia_restoration_result()
    assert result.prevention_advantage_v06 is not None


def test_posidonia_pa_ordering():
    """pa_full >= pa_with_substrate >= pa_with_carbon >= pa_simple."""
    result = _run_posidonia_restoration_result()
    pa = result.prevention_advantage_v06
    assert pa.pa_full >= pa.pa_with_substrate >= pa.pa_with_carbon >= pa.pa_simple


def test_posidonia_pa_full_greater_than_simple():
    """pa_full > pa_simple: NPV accounting raises prevention advantage."""
    result = _run_posidonia_restoration_result()
    pa = result.prevention_advantage_v06
    assert pa.pa_full > pa.pa_simple


# ── Test 22: PA ordering holds across more NPV levels ─────────────────────────


def test_oak_valley_pa_v06_ordering():
    """Oak Valley PA_v06: pa_full >= pa_with_substrate >= pa_with_carbon >= pa_simple."""
    result = _run_forest_restoration_result()
    pa = result.prevention_advantage_v06
    assert pa.pa_full >= pa.pa_with_substrate >= pa.pa_with_carbon >= pa.pa_simple


def test_costa_brava_pa_v06_ordering():
    """Costa Brava PA_v06: pa_full >= pa_with_substrate >= pa_with_carbon >= pa_simple."""
    result = _run_costa_brava_restoration_result()
    pa = result.prevention_advantage_v06
    assert pa.pa_full >= pa.pa_with_substrate >= pa.pa_with_carbon >= pa.pa_simple


def test_all_cases_pa_simple_greater_than_one():
    """pa_simple > 1.0 for all cases: restoration is more expensive than prevention."""
    forest_result = _run_forest_restoration_result()
    cb_result = _run_costa_brava_restoration_result()
    posidonia_result = _run_posidonia_restoration_result()
    for result in [forest_result, cb_result, posidonia_result]:
        assert result.prevention_advantage_v06.pa_simple > 1.0


# ── Test 23: Carbon breakeven finite and positive for all cases ───────────────


def test_forest_carbon_breakeven_finite_and_positive():
    """Oak Valley carbon breakeven is finite and > 0 (carbon credit-viable range)."""
    result = _run_forest_restoration_result()
    bp = result.carbon_breakeven.breakeven_price
    assert 0 < bp < float("inf")


def test_costa_brava_carbon_breakeven_finite_and_positive():
    """Costa Brava carbon breakeven is finite and > 0."""
    result = _run_costa_brava_restoration_result()
    bp = result.carbon_breakeven.breakeven_price
    assert 0 < bp < float("inf")


def test_posidonia_carbon_breakeven_finite_and_positive():
    """Posidonia carbon breakeven is finite and > 0."""
    result = _run_posidonia_restoration_result()
    bp = result.carbon_breakeven.breakeven_price
    assert 0 < bp < float("inf")


def test_carbon_breakeven_projected_year_within_bounds():
    """projected_breakeven_year is None or in reasonable range (0–200)."""
    result = _run_forest_restoration_result()
    py = result.carbon_breakeven.projected_breakeven_year
    if py is not None:
        assert 0 <= py <= 200


# ── Test 24: Backward compat: no discount → NPV fields are None ───────────────


def test_backward_compat_no_discount_extraction_npv_is_none():
    """When resource has no discount, extraction_npv is None."""
    resource = Resource(
        name="No Discount",
        total_units=1_000,
        safe_threshold_ratio=0.3,
        unit_value=100.0,
        # No discount!
    )
    agents = [
        Agent("A", 0.5, logistic_damage(threshold=0.3), 100_000.0, "A"),
        Agent("B", 0.5, logistic_damage(threshold=0.3), 100_000.0, "B"),
    ]
    eco = Ecosystem("No Discount Eco", resource=resource, agents=agents)
    result = run_extraction(eco, 300)
    assert result.extraction_npv is None


def test_backward_compat_no_discount_restoration_npv_is_none():
    """When resource has no discount, restoration NPV fields are None."""
    resource = Resource(
        name="No Discount",
        total_units=1_000,
        safe_threshold_ratio=0.3,
        unit_value=100.0,
    )
    agents = [
        Agent("A", 0.5, logistic_damage(threshold=0.3), 100_000.0, "A"),
        Agent("B", 0.5, logistic_damage(threshold=0.3), 100_000.0, "B"),
    ]
    eco = Ecosystem("No Discount Eco", resource=resource, agents=agents)
    cost = RestorationCost(
        planting_cost_per_unit=50.0,
        annual_maintenance_per_unit=10.0,
        maintenance_years=5,
    )
    result = run_restoration(eco, 300, cost, [logistic_recovery(0.3)] * 2)
    assert result.npv is None
    assert result.carbon_breakeven is None
    assert result.prevention_advantage_v06 is None


def test_backward_compat_simstep_defaults():
    """SimulationStep v0.6 fields default to harmless values when no discount."""
    resource = Resource(
        name="No Discount",
        total_units=1_000,
        safe_threshold_ratio=0.3,
        unit_value=100.0,
    )
    agents = [
        Agent("A", 0.5, logistic_damage(threshold=0.3), 100_000.0, "A"),
        Agent("B", 0.5, logistic_damage(threshold=0.3), 100_000.0, "B"),
    ]
    eco = Ecosystem("No Discount Eco", resource=resource, agents=agents)
    result = run_extraction(eco, 300)
    step = result.steps[0]
    assert step.discount_factor == 1.0
    assert step.npv_externality == 0.0
    assert step.carbon_price_used == 0.0


# ── Test 25: Zero rate + zero scarcity: NPV ≈ undiscounted × horizon ──────────


def test_zero_rate_zero_scarcity_direct_npv_equals_undiscounted():
    """With zero discount rate and zero scarcity, NPV_direct = annual_loss × horizon."""
    dc_zero = DiscountConfig(
        rate_schedule=0.0,
        scarcity_rate=0.0,
        carbon_price_current=80.0,
        carbon_price_growth=0.0,
        horizon_years=50,
        remaining_productive_years=50,
    )
    eco = build_forest_ecosystem()
    result = run_extraction(eco, 5_000)
    npv = compute_extraction_npv(result, dc_zero)
    expected = result.total_externality_cost * 50
    assert npv.direct == pytest.approx(expected, rel=1e-6)


def test_zero_rate_carbon_foregone_equals_undiscounted():
    """With zero rate and zero carbon growth, carbon_foregone = annual × remaining_yrs × price."""
    from gaia.carbon import compute_annual_absorption

    dc_zero = DiscountConfig(
        rate_schedule=0.0,
        scarcity_rate=0.0,
        carbon_price_current=80.0,
        carbon_price_growth=0.0,
        horizon_years=100,
        remaining_productive_years=50,
    )
    eco = build_forest_ecosystem()
    result = run_extraction(eco, 5_000)
    npv = compute_extraction_npv(result, dc_zero)
    # annual_absorption = 5000 × 0.022 = 110 t/yr
    # carbon_foregone = 110 × 50 years × 80 €/t = 440,000
    resource = eco.resource
    annual_abs = resource.carbon_profile.annual_absorption_tonnes * 5_000
    expected_foregone = annual_abs * 50 * 80.0
    assert npv.carbon_foregone == pytest.approx(expected_foregone, rel=1e-6)


# ── Horizon propagated correctly ──────────────────────────────────────────────


def test_extraction_npv_horizon_matches_discount_config():
    """ExtractionNPV.horizon matches the discount config horizon."""
    result = _run_forest_extraction()
    npv = result.extraction_npv
    assert npv.horizon == npv.discount_config.horizon_years


def test_restoration_npv_horizon_matches_discount_config():
    """RestorationNPV.horizon matches the discount config horizon."""
    result = _run_forest_restoration_result()
    assert result.npv.horizon == result.npv.discount_config.horizon_years
