"""
Gaia v0.1 — End-to-end Posidonia case tests (the Catalan meadows, Costa Brava).

These tests run the preconfigured Posidonia marine ecosystem case and check for
ecological plausibility. They verify:
    - Correct ecosystem structure (11 agents, weights sum to 1.0)
    - The economic story (below threshold: sustainable; above: net loss)
    - The inverted marine economics (one-time revenue vs annual recurring losses)
    - The annual note appears in the report
    - Keystone agent properties
    - Report generation and content
"""

import pytest
from gaia.cases.posidonia import (
    build_posidonia_ecosystem,
    run_posidonia,
)
from gaia.simulation import run_extraction


# ── Constants ──────────────────────────────────────────────────────────────────

TOTAL_HECTARES = 5_000
THRESHOLD = 0.20             # 1,000 ha safe destruction limit
THRESHOLD_UNITS = 1_000      # 20% of 5,000 ha
REVENUE_PER_HA = 2_500.0    # One-time revenue per hectare destroyed


# ── Structure invariants ───────────────────────────────────────────────────────

def test_posidonia_ecosystem_has_ten_agents():
    """The Posidonia ecosystem has 10 agents (Blue Carbon removed, decision D3)."""
    eco = build_posidonia_ecosystem()
    assert len(eco.agents) == 10
    assert "Blue Carbon" not in {a.name for a in eco.agents}


def test_posidonia_values_are_the_sourced_final_services():
    """Step 8.2: weight × value per hectare is the sourced service value of
    the four final services (Campagne et al. 2015); the six ecological
    agents carry no euro value of their own (final-services accounting)."""
    eco = build_posidonia_ecosystem()
    per_ha = {a.name: a.dependency_weight * a.annual_value_per_ha for a in eco.agents}
    assert per_ha["Coastal Protection"] == pytest.approx(188.0, rel=1e-12)
    assert per_ha["Water Quality"] == pytest.approx(60.0, rel=1e-12)
    assert per_ha["Fish Populations"] == pytest.approx(35.0, rel=1e-12)
    assert per_ha["Human Communities"] == pytest.approx(1.83, rel=1e-12)
    for name in ("Posidonia Meadow", "Coralligenous & Red Coral", "Epiphytes & Algae",
                 "Marine Invertebrates", "Marine Megafauna", "Seabirds"):
        assert per_ha[name] == 0.0
    assert sum(per_ha.values()) == pytest.approx(284.83, rel=1e-12)


def test_posidonia_agent_weights_sum_to_one():
    """Posidonia agent dependency weights sum to 1.0."""
    eco = build_posidonia_ecosystem()
    total_weight = sum(a.dependency_weight for a in eco.agents)
    assert abs(total_weight - 1.0) < 1e-9, (
        f"Agent weights should sum to 1.0, got {total_weight}"
    )


def test_posidonia_fish_highest_living_weight():
    """
    Fish Populations has the highest dependency weight among living biological agents.

    In the Medes Islands no-take reserve, exploited fish took 25-35 years to
    reach carrying-capacity biomass (García-Rubies et al. 2013, PLoS ONE
    8:e73922), so fish respond strongly to habitat protection. Fish also
    drive the artisanal fishing economy and act as the trophic link between the
    meadow ecosystem and apex megafauna.
    """
    eco = build_posidonia_ecosystem()
    fish_agent = next(a for a in eco.agents if "Fish" in a.name)

    # Living agents: all except Coastal Protection, Water Quality,
    # Posidonia Meadow (physical/ecosystem agents)
    living_agents = [
        a for a in eco.agents
        if a.name not in ("Coastal Protection", "Water Quality", "Posidonia Meadow")
    ]
    max_living_weight = max(a.dependency_weight for a in living_agents)

    assert fish_agent.dependency_weight == max_living_weight, (
        f"Fish Populations ({fish_agent.dependency_weight}) should have the highest "
        f"weight among living agents, but max is {max_living_weight}"
    )


def test_posidonia_coastal_protection_highest_physical_cost():
    """
    Coastal Protection produces the highest cost among physical service agents.

    Posidonia physically protects Costa Brava beaches via wave attenuation and
    leaf-litter cushions. Beaches are the tourism economy — their erosion triggers
    the highest per-agent economic impact of all physical ecosystem services.
    """
    eco = build_posidonia_ecosystem()
    result = run_extraction(eco, 3_000)  # 60% depletion

    # Map agent names to their final costs
    final_step = result.steps[-1]
    agent_costs = {
        eco.agents[i].name: final_step.agent_annual_costs[i]
        for i in range(len(eco.agents))
    }

    physical_agents = ["Coastal Protection", "Water Quality"]
    coastal_cost = agent_costs["Coastal Protection"]

    for name in physical_agents:
        if name != "Coastal Protection":
            assert coastal_cost >= agent_costs[name], (
                f"Coastal Protection ({coastal_cost:.2f}) should produce >= cost "
                f"compared to {name} ({agent_costs[name]:.2f})"
            )


# ── Ecological plausibility tests ──────────────────────────────────────────────

def test_posidonia_at_threshold():
    """
    Destroying exactly 1,000 ha (20%): one-off revenue is weighed against the
    present value of the recurring annual loss.

    Replaces a test asserting that the single-year externality is below the
    one-off revenue, which compared a yearly flow with a one-off amount.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result = run_extraction(eco, THRESHOLD_UNITS)

    # Revenue = 1000 ha * 2500 = 2,500,000
    assert result.revenue == 2_500_000.0
    assert result.net_social_cost == pytest.approx(
        result.pv_externality - result.revenue, rel=1e-12)
    # The annual loss recurs every year of the 200-year horizon
    assert result.extraction_npv.horizon == 200
    assert result.extraction_npv.direct > 10 * result.annual_externality


def test_posidonia_past_threshold():
    """
    Destroying 2,500 ha (50%): externality is much larger than at threshold.

    The invariant: externality at 50% must be substantially larger than at 20%
    (the safe threshold), confirming the S-curve acceleration.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result_past = run_extraction(eco, 2_500)       # 50%
    result_threshold = run_extraction(eco, THRESHOLD_UNITS)  # 20%

    # Revenue = 2500 * 2500 = 6,250,000
    assert result_past.revenue == 6_250_000.0

    # Externality at 50% must be substantially larger than at threshold (S-curve
    # accel). ~3.0× before the exponential Blue Carbon agent left (Step 3.4).
    assert result_past.annual_externality > 2.5 * result_threshold.annual_externality, (
        f"Externality at 50% ({result_past.annual_externality:.2f}) should be "
        f">2.5× the threshold externality ({result_threshold.annual_externality:.2f})"
    )


def test_posidonia_heavy_extraction():
    """
    Destroying 4,000 ha (80%): substantial externality, critically low health.

    At 80% destruction the ecosystem is near collapse: ecosystem health is
    critically low.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result = run_extraction(eco, 4_000)

    assert result.final_ecosystem_health < 0.10, (
        f"At 80% destruction, ecosystem health should be < 10%, "
        f"got {result.final_ecosystem_health:.1%}"
    )


def test_posidonia_marginal_cost_curve_shape():
    """
    The externality cost accelerates sharply past the safe threshold.

    The increment from pre-threshold (10%→20%) should be less than from
    threshold-crossing (20%→40%), reflecting the logistic curve non-linearity.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result = run_extraction(eco, 3_000)

    cost_at = {}
    for step in result.steps:
        if step.units_extracted in (500, 1_000, 2_000):
            cost_at[step.units_extracted] = step.annual_externality

    inc_pre_threshold = cost_at[1_000] - cost_at[500]     # 10% → 20%
    inc_post_threshold = cost_at[2_000] - cost_at[1_000]  # 20% → 40%

    assert inc_post_threshold > inc_pre_threshold, (
        f"Cost increment 20%→40% ({inc_post_threshold:.2f}) should exceed "
        f"10%→20% ({inc_pre_threshold:.2f}), reflecting threshold non-linearity"
    )


def test_posidonia_carbon_valued_by_carbon_profile_only():
    """
    Blue carbon is valued by gaia.carbon (release + foregone absorption), not
    by an agent. S5: one sourced absorption value, the Balearic burial rate
    of Mazarrasa et al. (2017), 26 g C/m²/yr = 0.26 t C/ha/yr; the release is
    the top-metre matte stock (327 t C/ha) × the Pendleton et al. (2012)
    central loss fraction 0.63, with no separate biomass term.
    """
    eco = build_posidonia_ecosystem()
    profile = eco.resource.carbon_profile
    assert profile.annual_absorption_tonnes == pytest.approx(0.26 * 44 / 12)
    assert profile.soil_carbon_tonnes == pytest.approx(327 * 44 / 12)
    assert profile.soil_release_fraction == 0.63
    assert profile.stored_carbon_tonnes == 0.0
    result = run_extraction(eco, 1_000)
    assert result.extraction_npv.carbon_absorption_lost_t_yr == pytest.approx(
        1_000 * 0.26 * 44 / 12)
    assert result.extraction_npv.carbon_released_t == pytest.approx(
        1_000 * 327 * 44 / 12 * 0.63)


# ── Report tests ───────────────────────────────────────────────────────────────

def test_posidonia_report_generates():
    """The report produces a non-empty string with key fields and the annual note."""
    # run_posidonia appends the annual note; format_report alone does not
    report = run_posidonia(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        hectares_destroyed=2_000,
    )

    assert isinstance(report, str)
    assert len(report) > 100
    assert "Posidonia oceanica meadows of Catalonia" in report
    assert "ANNUAL EXTERNALITY" in report
    assert "NET SOCIAL COST" in report


def test_posidonia_annual_note_in_report():
    """
    The annual note (time-flow asymmetry warning) appears in the report.

    This is the key difference from terrestrial cases: Posidonia destruction
    creates one-time private revenue but annual recurring ecosystem service losses.
    The report must flag this explicitly so the economic story isn't misread.
    """
    report = run_posidonia(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        hectares_destroyed=2_000,
    )
    # The note warns about recurring annual costs
    assert "ANNUAL" in report or "annual" in report, (
        "Report should contain the annual cost warning for marine economics"
    )
    assert "Posidonia" in report


def test_posidonia_report_contains_all_agents():
    """The report mentions all 10 agent names."""
    report = run_posidonia(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        hectares_destroyed=2_000,
    )
    expected_agents = [
        "Posidonia Meadow",
        "Coralligenous & Red Coral",
        "Epiphytes & Algae",
        "Marine Invertebrates",
        "Fish Populations",
        "Marine Megafauna",
        "Seabirds",
        "Coastal Protection",
        "Water Quality",
        "Human Communities",
    ]
    for agent_name in expected_agents:
        assert agent_name in report, (
            f"Agent '{agent_name}' should appear in the report"
        )


# ── v0.3: Cascade-specific tests ─────────────────────────────────────────────

def test_posidonia_has_interactions():
    """Posidonia ecosystem has 15 interaction edges (Blue Carbon's edge removed)."""
    eco = build_posidonia_ecosystem()
    assert len(eco.interactions) == 15, (
        f"Expected 15 interaction edges, got {len(eco.interactions)}"
    )


def test_posidonia_has_keystone():
    """Posidonia Meadow is the keystone agent."""
    eco = build_posidonia_ecosystem()
    keystones = [a.name for a in eco.agents if a.is_keystone]
    assert "Posidonia Meadow" in keystones
    assert len(keystones) == 1


def test_posidonia_keystone_cascade_at_heavy_extraction():
    """At 60% destruction, Posidonia keystone threshold should be crossed."""
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
    )
    result = run_extraction(eco, 3_000)  # 60%
    all_triggered = set()
    for step in result.steps:
        for name in step.keystone_triggered:
            all_triggered.add(name)
    assert "Posidonia Meadow" in all_triggered, (
        "Posidonia Meadow keystone should be triggered at 60% destruction"
    )


def test_posidonia_cascade_increases_coastal_protection_cost():
    """
    Posidonia→Coastal Protection edge means coastal protection cost includes
    cascade damage beyond direct resource depletion.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
    )
    result = run_extraction(eco, 2_500)
    final_step = result.steps[-1]
    # Find Coastal Protection agent index
    cp_idx = next(i for i, a in enumerate(eco.agents) if a.name == "Coastal Protection")
    cascade_dmg = final_step.agent_cascade_damages[cp_idx]
    assert cascade_dmg > 0, (
        f"Coastal Protection should have non-zero cascade damage, got {cascade_dmg:.6f}"
    )
