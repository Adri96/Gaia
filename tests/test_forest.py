"""
Gaia v0.1 — End-to-end forest case tests.

These tests run the preconfigured Oak Valley Forest case and check for
ecological plausibility. They are sanity checks verifying:
    - Revenue arithmetic and the PV-based net social cost
    - The correct curve shape (accelerating marginal cost)
    - Report generation and content
"""

import pytest
from gaia.cases.forest import build_forest_ecosystem, run_forest
from gaia.report import format_report
from gaia.simulation import run_extraction


# ── Fixtures ───────────────────────────────────────────────────────────────────

TOTAL_TREES = 10_000
THRESHOLD = 0.3          # 3,000 safe extraction limit
THRESHOLD_UNITS = 3_000


# ── Ecological plausibility tests ──────────────────────────────────────────────

def test_forest_at_threshold():
    """
    Cutting exactly 3,000 trees (30%) costs far less per year than cutting 80%.

    Replaces a test that the annual externality is within 0.5–1.5× the one-off
    revenue at the threshold: that compared a yearly flow with a one-off amount
    and encoded the back-solved calibration of the old rates.
    """
    eco = build_forest_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, THRESHOLD_UNITS)

    # Revenue = 3000 * 100 = 300,000
    assert result.revenue == 300_000.0

    # Externality at threshold should be MUCH less than at heavy extraction
    result_heavy = run_extraction(eco, 8_000)
    assert result.annual_externality < 0.5 * result_heavy.annual_externality, (
        f"Externality at threshold ({result.annual_externality:.0f}) should be "
        f"<50% of heavy extraction ({result_heavy.annual_externality:.0f})"
    )


def test_forest_past_threshold():
    """
    Cutting 5,000 trees (50%): the net social cost weighs the one-off revenue
    against the present value of the yearly externality stream.

    Replaces a test that the net social cost is negative at 50%, which held
    only because the old rates were tuned to produce it.
    """
    eco = build_forest_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 5_000)

    # Revenue = 5000 * 100 = 500,000
    assert result.revenue == 500_000.0
    npv = result.extraction_npv
    assert result.pv_externality == pytest.approx(
        npv.direct + npv.carbon_release + npv.carbon_foregone,
        rel=1e-12,
    )
    assert result.net_social_cost == pytest.approx(
        result.pv_externality - result.revenue, rel=1e-12)


def test_forest_heavy_extraction():
    """
    Cutting 8,000 trees (80%): the ecosystem is severely degraded.

    At 80% depletion, the logistic damage function is in its high-damage
    saturation region and ecosystem health is critically low.
    """
    eco = build_forest_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 8_000)

    # Revenue = 8000 * 100 = 800,000
    assert result.revenue == 800_000.0

    # Ecosystem health should be critically low (less than 10%)
    assert result.final_ecosystem_health < 0.10, (
        f"At 80% extraction, ecosystem health should be critically low (<10%), "
        f"got {result.final_ecosystem_health:.1%}"
    )


def test_forest_marginal_cost_curve_shape():
    """
    The cost curve has the correct non-linear shape around the threshold.

    The logistic damage function is S-shaped: damage is low and slow before the
    threshold, then accelerates sharply at the threshold (inflection point), then
    saturates toward a plateau.

    We verify the critical property: the increment from 1k→3k (pre-threshold)
    is less than the increment from 3k→5k (threshold crossing), which represents
    the core non-linearity of the Gaia model.

    Note: 5k→7k may be less than 3k→5k because the logistic saturates past the
    inflection. The meaningful test is the acceleration at the threshold crossing.
    """
    eco = build_forest_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 8_000)

    # Cumulative cost at each milestone
    cost_at = {}
    for step in result.steps:
        if step.units_extracted in (1_000, 3_000, 5_000, 7_000):
            cost_at[step.units_extracted] = step.annual_externality

    # Incremental cost in the pre-threshold region (1k to 3k) should be less
    # than in the threshold-crossing region (3k to 5k)
    inc_1k_3k = cost_at[3_000] - cost_at[1_000]
    inc_3k_5k = cost_at[5_000] - cost_at[3_000]

    assert inc_3k_5k > inc_1k_3k, (
        f"Cost from 3k→5k ({inc_3k_5k:.2f}) should exceed 1k→3k ({inc_1k_3k:.2f}), "
        f"reflecting non-linear damage acceleration at the threshold"
    )

    # Also verify cumulative cost is substantially higher past threshold
    # At 5000 trees (50%), cumulative cost should be much higher than at 1000 trees (10%)
    assert cost_at[5_000] > 5.0 * cost_at[1_000], (
        f"Cost at 5k ({cost_at[5_000]:.2f}) should be >> cost at 1k ({cost_at[1_000]:.2f})"
    )


# ── Report tests ───────────────────────────────────────────────────────────────

def test_forest_report_generates():
    """The report function produces a non-empty string containing key fields."""
    eco = build_forest_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 5_000)
    report = format_report(result)

    assert isinstance(report, str)
    assert len(report) > 100, "Report should be a multi-line non-trivial string"

    # Key fields must appear in the report
    assert "Oak Valley Forest" in report
    assert "ANNUAL EXTERNALITY" in report
    assert "NET SOCIAL COST" in report


def test_forest_report_contains_all_agents():
    """The report mentions all four agent names."""
    report = run_forest(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        trees_cut=5_000,
    )
    assert "Human Communities" in report
    assert "Animal Populations" in report
    assert "Vegetation & Flora" in report
    assert "Watershed & Local Climate" in report


def test_forest_report_contains_revenue():
    """The report includes revenue in the correct ballpark."""
    report = run_forest(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        trees_cut=5_000,
        tree_value=100.0,
    )
    # Revenue = 5000 * 100 = 500,000; expect "500,000" in the report
    assert "500,000" in report


def test_forest_report_via_run_forest():
    """run_forest() convenience function returns a valid non-empty report."""
    report = run_forest(
        total_trees=5_000,
        safe_threshold_ratio=0.25,
        trees_cut=2_000,
        tree_value=80.0,
    )
    assert isinstance(report, str)
    assert len(report) > 50


# ── End-to-end CLI validation ─────────────────────────────────────────────────

def test_forest_cli_default_scenario():
    """Default scenario: 10k trees, 30% threshold, 5k cut produces a valid result."""
    eco = build_forest_ecosystem(
        total_trees=10_000, safe_threshold_ratio=0.3, tree_value=100.0
    )
    result = run_extraction(eco, 5_000)

    assert result.total_units_extracted == 5_000
    assert result.revenue == 500_000.0
    assert result.annual_externality > 0
    assert len(result.steps) == 5_000
    assert result.steps[0].step == 1
    assert result.steps[-1].step == 5_000


def test_forest_ecosystem_has_four_agents():
    """The forest ecosystem always has exactly four agents."""
    eco = build_forest_ecosystem()
    assert len(eco.agents) == 4


def test_forest_agent_weights_sum_to_one():
    """Forest agent dependency weights sum to 1.0."""
    eco = build_forest_ecosystem()
    total_weight = sum(a.dependency_weight for a in eco.agents)
    assert abs(total_weight - 1.0) < 1e-9


def test_forest_watershed_largest_share_of_value():
    """Watershed & Local Climate carries the largest share of the annual value.

    Every agent uses the same €/ha/yr biome value, so the split is decided
    by the dependency weights (Watershed & Local Climate: 0.35).
    """
    eco = build_forest_ecosystem()
    area = eco.resource.area_ha
    share = {a.name: a.dependency_weight * a.annual_value(area) for a in eco.agents}
    assert max(share, key=share.get) == "Watershed & Local Climate"


def test_forest_value_is_per_hectare():
    """Full-damage value = €2,312.16/ha/yr × area; the default area follows the trees.

    Int$3,013/ha/yr (de Groot et al. 2012, Table 2, temperate forest) minus
    its Int$152 climate regulation component, valued by gaia.carbon instead
    (decision D3), converted at Spain's 2007 PPP (Step 8g.6, gaia.currency).
    """
    from gaia.currency import int_dollars_to_eur

    from gaia.cases.forest import FOREST_AREA_HA, FOREST_TOTAL_TREES

    eco = build_forest_ecosystem()
    assert eco.resource.area_ha == FOREST_AREA_HA
    total = sum(a.dependency_weight * a.annual_value(FOREST_AREA_HA) for a in eco.agents)
    assert total == pytest.approx(int_dollars_to_eur(3_013 - 152, 2007) * FOREST_AREA_HA, rel=1e-12)
    assert int_dollars_to_eur(3_013 - 152, 2007) == pytest.approx(2_312.16, abs=0.005)
    assert build_forest_ecosystem(total_trees=2 * FOREST_TOTAL_TREES).resource.area_ha == (
        2 * FOREST_AREA_HA)
    assert build_forest_ecosystem(total_trees=500, area_ha=40.0).resource.area_ha == 40.0
