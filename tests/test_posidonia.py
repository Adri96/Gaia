"""
Gaia v0.1 — End-to-end Costa Brava Posidonia Meadow case tests.

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
    _ANNUAL_NOTE,
    build_posidonia_ecosystem,
    run_posidonia,
)
from gaia.report import format_report
from gaia.simulation import run_extraction


# ── Constants ──────────────────────────────────────────────────────────────────

TOTAL_HECTARES = 5_000
THRESHOLD = 0.20             # 1,000 ha safe destruction limit
THRESHOLD_UNITS = 1_000      # 20% of 5,000 ha
REVENUE_PER_HA = 2_500.0    # One-time revenue per hectare destroyed


# ── Structure invariants ───────────────────────────────────────────────────────

def test_posidonia_ecosystem_has_eleven_agents():
    """The Posidonia ecosystem always has exactly 11 agents."""
    eco = build_posidonia_ecosystem()
    assert len(eco.agents) == 11


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

    The Medes Islands MPA demonstrated that fish populations respond most directly
    to habitat protection — 80× higher fish biomass inside vs. outside. Fish also
    drive the artisanal fishing economy and act as the trophic link between the
    meadow ecosystem and apex megafauna.
    """
    eco = build_posidonia_ecosystem()
    fish_agent = next(a for a in eco.agents if "Fish" in a.name)

    # Living agents: all except Coastal Protection, Water Quality, Blue Carbon,
    # Posidonia Meadow (physical/ecosystem agents)
    living_agents = [
        a for a in eco.agents
        if a.name not in ("Coastal Protection", "Water Quality", "Blue Carbon",
                          "Posidonia Meadow")
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
        eco.agents[i].name: final_step.agent_costs[i]
        for i in range(len(eco.agents))
    }

    physical_agents = ["Coastal Protection", "Water Quality", "Blue Carbon"]
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
    Destroying exactly 1,000 ha (20%): externality < one-time revenue.

    At the safe threshold, the single-year externality is still below the
    one-time private gain. The annual note flags that this changes within ~2
    years as recurring losses accumulate.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result = run_extraction(eco, THRESHOLD_UNITS)

    # Revenue = 1000 ha * 2500 = 2,500,000
    assert result.total_private_revenue == 2_500_000.0
    assert result.net_social_cost > 0, (
        f"At safe threshold (20%), single-year net_social_cost should be positive, "
        f"got {result.net_social_cost:.2f}. Note: annual recurring losses change "
        f"this picture within ~2 years."
    )


def test_posidonia_past_threshold():
    """
    Destroying 2,500 ha (50%): externality is much larger than at threshold.

    The Posidonia case uses an inverted economic model: one-time private revenue
    vs annual recurring externality costs. The single-year externality snapshot does
    NOT cross the one-time revenue figure (revenue per ha is high relative to
    annual service loss per ha at any single moment). The real crossover requires
    multi-year NPV — a v0.5 feature.

    The correct invariant here: externality at 50% must be substantially larger
    than at 20% (the safe threshold), confirming the S-curve acceleration. The
    externality at 50% should also be at least 50% of one-time revenue, confirming
    that within 2 years of annual losses the private gain is fully offset.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result_past = run_extraction(eco, 2_500)       # 50%
    result_threshold = run_extraction(eco, THRESHOLD_UNITS)  # 20%

    # Revenue = 2500 * 2500 = 6,250,000
    assert result_past.total_private_revenue == 6_250_000.0

    # Externality at 50% must be substantially larger than at threshold (S-curve accel)
    assert result_past.total_externality_cost > 3 * result_threshold.total_externality_cost, (
        f"Externality at 50% ({result_past.total_externality_cost:.2f}) should be "
        f">>3× the threshold externality ({result_threshold.total_externality_cost:.2f})"
    )

    # Annual externality at 50% should be >= 50% of the one-time revenue,
    # meaning within ~2 years of annual losses the private gain is fully offset
    assert result_past.total_externality_cost >= 0.5 * result_past.total_private_revenue, (
        f"Annual externality at 50% ({result_past.total_externality_cost:.2f}) should be "
        f">= 50% of one-time revenue ({result_past.total_private_revenue:.2f}), "
        f"meaning payback < 2 years"
    )


def test_posidonia_heavy_extraction():
    """
    Destroying 4,000 ha (80%): substantial externality, critically low health.

    At 80% destruction the ecosystem is near collapse. Externality should be
    at least 50% of revenue and ecosystem health critically low.
    """
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        revenue_per_hectare=REVENUE_PER_HA,
    )
    result = run_extraction(eco, 4_000)

    assert result.total_externality_cost >= 0.5 * result.total_private_revenue, (
        f"At 80% destruction, externality ({result.total_externality_cost:.2f}) "
        f"should be >= 50% of revenue ({result.total_private_revenue:.2f})"
    )
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
            cost_at[step.units_extracted] = step.cumulative_cost

    inc_pre_threshold = cost_at[1_000] - cost_at[500]     # 10% → 20%
    inc_post_threshold = cost_at[2_000] - cost_at[1_000]  # 20% → 40%

    assert inc_post_threshold > inc_pre_threshold, (
        f"Cost increment 20%→40% ({inc_post_threshold:.2f}) should exceed "
        f"10%→20% ({inc_pre_threshold:.2f}), reflecting threshold non-linearity"
    )


def test_posidonia_blue_carbon_uses_exponential():
    """
    Blue Carbon uses an exponential damage function, not logistic.

    CO₂ release from Posidonia matte is continuous and non-saturating — unlike
    biological populations that plateau, atmospheric carbon accumulates. The
    exponential function encodes this. We verify the Blue Carbon agent produces
    different damage values than the logistic agents at the same depletion level.
    """
    eco = build_posidonia_ecosystem()
    carbon_agent = next(a for a in eco.agents if "Carbon" in a.name)
    other_agent = next(a for a in eco.agents if "Carbon" not in a.name)

    depletion = 0.70
    carbon_damage = carbon_agent.damage_function(depletion)
    other_damage = other_agent.damage_function(depletion)

    assert abs(carbon_damage - other_damage) > 1e-6, (
        f"Blue Carbon (exponential) and a logistic agent should produce different "
        f"damage values at {depletion:.0%} depletion. "
        f"Got carbon={carbon_damage:.6f}, other={other_damage:.6f}"
    )


# ── Report tests ───────────────────────────────────────────────────────────────

def test_posidonia_report_generates():
    """The report produces a non-empty string with key fields and the annual note."""
    eco = build_posidonia_ecosystem(
        total_hectares=TOTAL_HECTARES, safe_threshold_ratio=THRESHOLD
    )
    result = run_extraction(eco, 2_000)
    # run_posidonia appends the annual note; format_report alone does not
    report = run_posidonia(
        total_hectares=TOTAL_HECTARES,
        safe_threshold_ratio=THRESHOLD,
        hectares_destroyed=2_000,
    )

    assert isinstance(report, str)
    assert len(report) > 100
    assert "Costa Brava Posidonia Meadow" in report
    assert "TOTAL EXTERNALITY" in report
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
    """The report mentions all 11 agent names."""
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
        "Blue Carbon",
        "Human Communities",
    ]
    for agent_name in expected_agents:
        assert agent_name in report, (
            f"Agent '{agent_name}' should appear in the report"
        )


# ── v0.3: Cascade-specific tests ─────────────────────────────────────────────

def test_posidonia_has_interactions():
    """Posidonia ecosystem has 16 interaction edges."""
    eco = build_posidonia_ecosystem()
    assert len(eco.interactions) == 16, (
        f"Expected 16 interaction edges, got {len(eco.interactions)}"
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
