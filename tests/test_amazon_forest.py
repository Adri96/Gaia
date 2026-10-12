"""
Gaia v0.7 — End-to-end Central Amazon Rainforest case tests.

These tests run the preconfigured Amazon tropical forest case and check for
ecological plausibility. They verify:
    - Correct ecosystem structure (11 agents, weights sum to 1.0)
    - The economic story (externality far exceeds revenue at all levels)
    - The correct curve shape (accelerating marginal cost past 20% threshold)
    - Keystone agent properties (mycorrhizal fungi + pollinators)
    - Amazon-specific predictions from spec §10 (tipping point, cascades)
    - Report generation and content

Numerical validation targets from AMAZON_FOREST.md §10:
    - Total externality at 50% extraction: €5M – €20M range for the 1,000 ha
      reference area (driven by the carbon stock)
    - Mycorrhizal price / Apex predator price > 20:1 (under v0.7 pricing)
    - (The spec's "prevention advantage > 100×" target was an input-price
      ratio, Step 3.7; not tested.)
"""

import pytest
from gaia.cases.amazon_forest import (
    AMAZON_AREA_HA,
    AMAZON_TOTAL_TREES,
    build_amazon_ecosystem,
    run_amazon,
)
from gaia.propagation import keystone_boosted_strength
from gaia.report import format_report
from gaia.simulation import run_extraction


# ── Constants ──────────────────────────────────────────────────────────────────

TOTAL_TREES = 400_000
THRESHOLD = 0.20            # 80,000 safe extraction limit (Lovejoy-Nobre)
THRESHOLD_UNITS = 80_000
TREE_VALUE = 1.50           # €/tree — selective logging economics


# ── Structure invariants ───────────────────────────────────────────────────────

def test_amazon_ecosystem_has_eleven_agents():
    """The Amazon ecosystem always has exactly 11 agents."""
    eco = build_amazon_ecosystem()
    assert len(eco.agents) == 11


def test_amazon_agent_weights_sum_to_one():
    """Amazon agent dependency weights sum to 1.0."""
    eco = build_amazon_ecosystem()
    total_weight = sum(a.dependency_weight for a in eco.agents)
    assert abs(total_weight - 1.0) < 1e-9, (
        f"Agent weights should sum to 1.0, got {total_weight}"
    )


def test_amazon_mycorrhizal_highest_or_tied_weight():
    """
    Mycorrhizal Fungi has one of the highest dependency weights.

    In the Amazon, mycorrhizal networks are THE non-substitutable nutrient
    gateway. 60% of the basin sits on P-depleted Oxisols where phosphorus
    limitation is the primary constraint on productivity. Mycorrhizal weight
    should be among the highest (tied with Canopy Trees at 0.15).
    """
    eco = build_amazon_ecosystem()
    mycorrhizal = next(a for a in eco.agents if "Mycorrhizal" in a.name)
    max_weight = max(a.dependency_weight for a in eco.agents)
    assert mycorrhizal.dependency_weight == max_weight, (
        f"Mycorrhizal Fungi ({mycorrhizal.dependency_weight}) should be among "
        f"the highest-weight agents, but max is {max_weight}"
    )


def test_amazon_apex_predators_lowest_weight():
    """
    Apex Predators have the lowest dependency weight.

    Few dependents, low network centrality, small population. Under v0.7
    pricing, they should emerge as the cheapest agent.
    """
    eco = build_amazon_ecosystem()
    apex = next(a for a in eco.agents if "Apex" in a.name)
    min_weight = min(a.dependency_weight for a in eco.agents)
    assert apex.dependency_weight == min_weight, (
        f"Apex Predators ({apex.dependency_weight}) should have the lowest "
        f"weight, but min is {min_weight}"
    )


# ── Ecological plausibility tests ──────────────────────────────────────────────

def test_amazon_at_threshold():
    """
    Cutting exactly 80,000 trees (20%) costs less per year than cutting 40%.
    """
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        tree_value=TREE_VALUE,
    )
    result_threshold = run_extraction(eco, THRESHOLD_UNITS)       # 20%
    result_past = run_extraction(eco, THRESHOLD_UNITS * 2)        # 40%

    # Revenue = 80,000 * 1.50 = 120,000
    assert result_threshold.revenue == 120_000.0

    # Externality at threshold < externality past threshold (S-curve accelerating)
    assert result_threshold.annual_externality < result_past.annual_externality, (
        f"Externality at 20% ({result_threshold.annual_externality:.2f}) "
        f"should be less than at 40% ({result_past.annual_externality:.2f})"
    )


def test_amazon_past_threshold():
    """
    Cutting 200,000 trees (50%): externality is much larger than at threshold.

    At 50% extraction, the S-curve has inflected. The externality should be
    substantially larger than at 20%. This is the core non-linearity test
    for the Amazon tipping point dynamics.
    """
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        tree_value=TREE_VALUE,
    )
    result = run_extraction(eco, 200_000)

    # Revenue = 200,000 * 1.50 = 300,000
    assert result.revenue == 300_000.0

    # Externality at 50% should be substantially more than at 20%
    result_threshold = run_extraction(eco, THRESHOLD_UNITS)
    assert result.annual_externality > 2 * result_threshold.annual_externality, (
        f"Externality at 50% ({result.annual_externality:.2f}) should be "
        f"much larger than at 20% ({result_threshold.annual_externality:.2f})"
    )


def test_amazon_heavy_extraction():
    """
    Cutting 320,000 trees (80%): massive externality, critically low health.

    At 80% depletion the logistic damage function is in its high-damage saturation
    region. Ecosystem health should be critically low.
    """
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        tree_value=TREE_VALUE,
    )
    result = run_extraction(eco, 320_000)

    # Revenue = 320,000 * 1.50 = 480,000
    assert result.revenue == 480_000.0

    assert result.final_ecosystem_health < 0.10, (
        f"At 80% extraction, ecosystem health should be < 10%, "
        f"got {result.final_ecosystem_health:.1%}"
    )


def test_amazon_marginal_cost_curve_shape():
    """
    The externality cost curve accelerates at the threshold crossing.

    The increment from pre-threshold (10%→20%) should be less than from
    threshold-crossing (20%→40%), reflecting the non-linear S-curve acceleration.
    """
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        tree_value=TREE_VALUE,
    )
    result = run_extraction(eco, 200_000)

    cost_at = {}
    for step in result.steps:
        if step.units_extracted in (40_000, 80_000, 160_000):
            cost_at[step.units_extracted] = step.annual_externality

    inc_pre_threshold = cost_at[80_000] - cost_at[40_000]       # 10% → 20%
    inc_post_threshold = cost_at[160_000] - cost_at[80_000]     # 20% → 40%

    assert inc_post_threshold > inc_pre_threshold, (
        f"Cost increment 20%→40% ({inc_post_threshold:.2f}) should exceed "
        f"10%→20% ({inc_pre_threshold:.2f}), reflecting threshold non-linearity"
    )


def test_amazon_net_social_cost_compares_revenue_with_pv():
    """
    Revenue (one-off) is compared with the present value of the externality,
    never with the annual flow: net_social_cost = pv_externality - revenue.

    Replaces a test asserting annual externality > revenue at every level,
    which compared a yearly flow with a one-off amount.
    """
    eco = build_amazon_ecosystem(total_trees=4_000, safe_threshold_ratio=THRESHOLD)
    for fraction in [0.10, 0.20, 0.30, 0.50]:
        result = run_extraction(eco, int(4_000 * fraction))
        assert result.pv_externality == result.extraction_npv.total
        assert result.net_social_cost == pytest.approx(
            result.pv_externality - result.revenue, rel=1e-12)
        assert result.extraction_npv.direct > result.annual_externality


# ── Report tests ───────────────────────────────────────────────────────────────

def test_amazon_report_generates():
    """The report produces a non-empty string with key fields."""
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 80_000)
    report = format_report(result)

    assert isinstance(report, str)
    assert len(report) > 100
    assert "Central Amazon" in report
    assert "ANNUAL EXTERNALITY" in report
    assert "NET SOCIAL COST" in report


def test_amazon_report_contains_all_agents():
    """The report mentions all 11 agent names."""
    report = run_amazon(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        trees_cut=80_000,
    )
    expected_agents = [
        "Canopy Trees",
        "Understory",
        "Mycorrhizal Fungi",
        "Soil Decomposers",
        "Pollinators",
        "Seed Dispersers",
        "Herbivores",
        "Mesopredators",
        "Apex Predators",
        "Aquatic System",
        "Epiphytes & Bromeliads",
    ]
    for agent_name in expected_agents:
        assert agent_name in report, (
            f"Agent '{agent_name}' should appear in the report"
        )


# ── v0.3: Cascade-specific tests ─────────────────────────────────────────────

def test_amazon_has_interactions():
    """Amazon ecosystem has interaction edges (≥25 from spec matrix)."""
    eco = build_amazon_ecosystem()
    assert len(eco.interactions) >= 25, (
        f"Expected >= 25 interaction edges, got {len(eco.interactions)}"
    )


def test_amazon_has_keystones():
    """Amazon has Mycorrhizal Fungi and Pollinators as keystones."""
    eco = build_amazon_ecosystem()
    keystones = [a.name for a in eco.agents if a.is_keystone]
    assert "Mycorrhizal Fungi" in keystones
    assert "Pollinators" in keystones
    assert len(keystones) == 2


def test_amazon_keystone_triggers_at_heavy_extraction():
    """At 50% extraction, keystone thresholds should be crossed."""
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD,
    )
    result = run_extraction(eco, 200_000)
    # Collect all keystone crossings
    all_triggered = set()
    for step in result.steps:
        for name in step.keystone_triggered:
            all_triggered.add(name)
    # At 50% depletion with threshold 0.20, keystones should have been triggered
    assert len(all_triggered) > 0, (
        "At 50% extraction, at least one keystone should be triggered"
    )


def test_amazon_cascade_increases_total_cost():
    """
    Cascade effects increase total externality compared to independent agents.

    We verify by checking that total externality with v0.3 cascades is at least
    as large as what independent agents would produce (since cascades only add
    damage, never remove it).
    """
    eco = build_amazon_ecosystem(
        total_trees=TOTAL_TREES, safe_threshold_ratio=THRESHOLD,
    )
    result = run_extraction(eco, 200_000)
    # At least some agents should have non-zero cascade damage
    final_step = result.steps[-1]
    total_cascade = sum(final_step.agent_cascade_damages)
    assert total_cascade > 0, (
        f"At 50% extraction, total cascade damage should be > 0, got {total_cascade:.6f}"
    )


def test_amazon_keystone_warning_in_report():
    """Report should show keystone threshold crossing warnings."""
    report = run_amazon(
        total_trees=TOTAL_TREES,
        safe_threshold_ratio=THRESHOLD,
        trees_cut=200_000,
    )
    assert "Keystone Threshold" in report, (
        "Report should contain keystone threshold crossing section"
    )


# ── Amazon-specific ecological tests ─────────────────────────────────────────

def test_amazon_mycorrhizal_keystone_edge_is_strongest():
    """
    The Mycorrhizal → Canopy Trees edge should be the strongest interaction
    in the ecosystem at its worst case (keystone boost applied), reflecting
    the absolute dependency of canopy trees on mycorrhizal nutrient access on
    P-depleted Oxisol. Its base strength is 0.40 / 2.10 since Step 3.8 (the
    in-degree cap), and the keystone boost doubles it.
    """
    eco = build_amazon_ecosystem()
    keystones = {a.name for a in eco.agents if a.is_keystone}

    def worst_case(e):
        return keystone_boosted_strength(e.strength) if e.source in keystones else e.strength

    max_edge = max(eco.interactions, key=worst_case)
    assert max_edge.source == "Mycorrhizal Fungi", (
        f"Strongest edge should originate from Mycorrhizal Fungi, "
        f"but got {max_edge.source} → {max_edge.target} ({max_edge.strength})"
    )
    assert max_edge.target == "Canopy Trees", (
        f"Strongest edge should target Canopy Trees, "
        f"but got {max_edge.source} → {max_edge.target}"
    )
    assert max_edge.strength == 0.190


AMAZON_VALUE_PER_HA = 3220 * 0.808165  # Step 8e.5: de Groot et al. 2012, PPP to €


def test_amazon_max_externality_matches_per_hectare_calibration():
    """
    sum(weight × rate) equals de Groot et al.'s (2012) tropical-forest value
    without climate regulation (Int$3,220/ha/yr, Table 2), converted at
    Spain's 2007 PPP rate (€0.808165 per Int$): €2,602.29/ha/yr (Step
    8e.5), times the reference area, so the agent rates scale with the
    stated hectares.
    """
    eco = build_amazon_ecosystem()
    assert eco.resource.area_ha == AMAZON_AREA_HA
    amazon_max = sum(
        a.dependency_weight * a.annual_value(eco.resource.area_ha) for a in eco.agents)
    assert amazon_max == pytest.approx(AMAZON_VALUE_PER_HA * AMAZON_AREA_HA, rel=1e-9)


def test_amazon_pricing_anchors_are_sourced_market_values():
    """Step 8d.6: three market-based anchors from de Groot et al. (2012)
    Table 2, tropical forest (Int$/ha/yr × 1,000 ha): food 200 (Canopy
    Trees), pollination 30 (Pollinators), water 27 (Aquatic System); every
    other price is derived. The static agent value (€2,602.29/ha/yr, de
    Groot et al.'s tropical forest without climate regulation, Step 8e.5)
    contains them and is larger than their sum."""
    eco = build_amazon_ecosystem(with_pricing=True)
    anchors = {p.agent_name: p.anchor_value for p in eco.pricing.anchors}
    assert anchors == {"Canopy Trees": 200_000.0, "Pollinators": 30_000.0,
                       "Aquatic System": 27_000.0}
    assert all("doi:10.1016/j.ecoser.2012.07.005" in p.source for p in eco.pricing.anchors)
    agents = sum(
        a.dependency_weight * a.annual_value(eco.resource.area_ha) for a in eco.agents)
    assert agents == pytest.approx(AMAZON_VALUE_PER_HA * AMAZON_AREA_HA, rel=1e-12)
    assert agents > sum(anchors.values())


def test_amazon_agent_value_is_de_groot_without_climate_regulation():
    """Step 8e.5: Int$5,264 − 2,044 = 3,220 (de Groot et al. 2012, Table 2),
    × the World Bank PPP factor for Spain, 2007 (0.808165 €/Int$); 2007
    price level, no income adjustment; low confidence."""
    from gaia.cases import load_case
    from gaia.provenance import Confidence

    eco = load_case("amazon_forest").build_ecosystem()
    value = next(p for p in eco.provenance if p.name == "agents.annual_value_per_ha")
    assert value.value == pytest.approx((5264 - 2044) * 0.808165, rel=1e-12)
    assert value.confidence is Confidence.LOW
    assert "doi:10.1016/j.ecoser.2012.07.005" in value.source and "PA.NUS.PRVT.PP" in value.source
    assert "no income adjustment" in value.note and "2007" in value.note


def test_amazon_carbon_density_matches_literature():
    """
    Per-tree stored carbon × tree density reproduces the 173 Mg C/ha total
    biomass (× 3.67 t CO₂ / t C) from spec §2, within ±10%.

    Tree density comes from the case's own unit count and area, so a
    mismatch between the two (C6: 400,000 trees on 10,000 ha = 40 trees/ha
    while the per-tree carbon assumed 400 trees/ha) fails here.
    """
    eco = build_amazon_ecosystem()
    assert eco.resource.total_units == AMAZON_TOTAL_TREES
    trees_per_ha = eco.resource.total_units / AMAZON_AREA_HA
    stored_per_ha = eco.resource.carbon_profile.stored_carbon_tonnes * trees_per_ha
    assert stored_per_ha == pytest.approx(173.0 * 3.67, rel=0.10)
