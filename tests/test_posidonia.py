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
    """Step 8c.2: weight × value per hectare is the agent's share of the
    service ledger: every agent carries euros, the total is unchanged where
    services were split (fisheries, bioindicator use)."""
    eco = build_posidonia_ecosystem()
    # the value per hectare of the reference resource (× site_share, Step 8d.4)
    per_ha = {a.name: a.dependency_weight * a.annual_value(1.0) for a in eco.agents}
    assert per_ha["Coastal Protection"] == pytest.approx(188.0, rel=1e-12)
    assert per_ha["Water Quality"] == pytest.approx(60.0, rel=1e-12)
    # Campagne et al.'s fisheries (35) split 14/16 fish, 2/16 invertebrates
    assert per_ha["Fish Populations"] + per_ha["Marine Invertebrates"] == pytest.approx(35.0, rel=1e-12)
    assert per_ha["Marine Invertebrates"] == pytest.approx(35.0 * 2 / 16, rel=1e-12)
    # bioindicator (1.5) + knowledge (0.33), the PREI epiphyte share moved
    assert per_ha["Human Communities"] + per_ha["Epiphytes & Algae"] == pytest.approx(1.83, rel=1e-12)
    assert per_ha["Epiphytes & Algae"] == pytest.approx(1.5 * 0.5 / 3.5, rel=1e-12)
    assert per_ha["Posidonia Meadow"] == pytest.approx(34.71 * 60_000 / 4582, rel=1e-12)
    assert per_ha["Coralligenous & Red Coral"] == pytest.approx(60.0 * 60_000 / 190_000, rel=1e-12)
    assert per_ha["Marine Megafauna"] == pytest.approx(per_ha["Seabirds"], rel=1e-12)
    assert all(v > 0.0 for v in per_ha.values())
    assert sum(per_ha.values()) == pytest.approx(818.6635785921815, rel=1e-12)


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


# ── Step 8c.4: the reference resource is an input ────────────────────────────

def test_reference_resource_defaults_to_the_catalan_stock():
    """Without an input the reference resource is the regional stock."""
    from gaia.cases import load_case

    eco = load_case("posidonia").build_ecosystem()
    assert eco.resource.total_units == 4582
    assert eco.resource.area_ha == 4582.0


def test_reference_resource_can_be_the_affected_meadow():
    """--area-ha (and --resource-name) set the specific meadow a project
    affects: it becomes the stock whose depletion the curves see, recorded
    as user-supplied."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    eco = case.build_ecosystem(area_ha=300.0, resource_name="Meadow of the bay")
    assert eco.resource.total_units == 300
    assert eco.resource.area_ha == 300.0
    assert eco.resource.name == "Meadow of the bay"
    area = next(p for p in eco.provenance if p.name == "resource.area_ha")
    assert area.confidence.value == "user-supplied"
    assert "--area-ha" in area.source
    # the same depletion of a smaller stock is reached with fewer hectares
    small = run_extraction(eco, 60)
    assert small.steps[-1].depletion_ratio == pytest.approx(0.2)


def test_reference_resource_rejects_fractional_or_conflicting_areas():
    from gaia.cases import load_case

    case = load_case("posidonia")
    with pytest.raises(ValueError, match="whole number of hectares"):
        case.build_ecosystem(area_ha=300.5)
    with pytest.raises(ValueError, match="must equal the number of units"):
        case.build_ecosystem(total_units=200, area_ha=300.0)
    # repeating the same figure is fine
    assert case.build_ecosystem(total_units=300, area_ha=300.0).resource.total_units == 300


def test_reference_resource_cli(capsys):
    """gaia run posidonia --area-ha N --resource-name NAME."""
    import json

    from gaia.cli import main

    assert main(["run", "posidonia", "--area-ha", "300", "--resource-name",
                 "Meadow of the bay", "--units", "30", "--format", "json",
                 "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    resource = out["ecosystem"]["resource"]
    assert resource["total_units"] == 300
    assert resource["name"] == "Meadow of the bay"


# ── Step 8c.3: small losses priced linearly ──────────────────────────────────

def _average_value_per_ha(eco):
    return sum(a.dependency_weight * a.annual_value(1.0) for a in eco.agents)


@pytest.mark.parametrize("reference_ha", [4582, 300])
@pytest.mark.parametrize("fraction", [0.001, 0.05, 0.19])
def test_small_losses_cost_their_average_value(reference_ha, fraction):
    """Below the safe threshold each hectare lost costs exactly its average
    value (slope 1, linear benefit transfer), whatever the reference."""
    from gaia.cases import load_case

    eco = load_case("posidonia").build_ecosystem(area_ha=float(reference_ha))
    assert eco.damage_model == "area_loss"
    k = max(1, int(fraction * reference_ha))
    result = run_extraction(eco, k)
    avg = _average_value_per_ha(eco)
    assert result.annual_externality == pytest.approx(k * avg, rel=1e-12)
    assert result.steps[0].marginal_annual_externality == pytest.approx(avg, rel=1e-12)
    assert result.steps[-1].marginal_annual_externality == pytest.approx(avg, rel=1e-9)


def test_threshold_behaviour_is_kept_past_the_threshold():
    """Past the threshold the remaining meadow degrades: the hectares just
    past it cost several times their average value (later ones less, once
    the remaining meadow is mostly degraded), and the loss exceeds the
    linear transfer."""
    from gaia.cases import load_case

    eco = load_case("posidonia").build_ecosystem()
    avg = _average_value_per_ha(eco)
    n = eco.resource.total_units
    result = run_extraction(eco, int(0.6 * n))
    t_units = int(eco.resource.safe_threshold_ratio * n)
    marginal = [s.marginal_annual_externality for s in result.steps]
    assert marginal[t_units - 1] == pytest.approx(avg, rel=1e-9)
    assert marginal[t_units + 50] > 1.5 * avg
    assert result.annual_externality > 1.5 * len(result.steps) * avg


def test_area_loss_rejects_curves_that_are_not_flat_at_small_losses():
    import copy

    from gaia.cases import load_case
    from gaia.ecosystem_io import case_from_dict

    doc = copy.deepcopy(load_case("posidonia").document)
    doc["damage_curves"]["threshold_logistic"]["type"] = "logistic"
    with pytest.raises(ValueError, match="flat at small losses"):
        run_extraction(case_from_dict(doc).build_ecosystem(), 10)


def test_damage_model_round_trips():
    from gaia.cases import load_case
    from gaia.ecosystem_io import ecosystem_from_dict, ecosystem_to_dict

    eco = load_case("posidonia").build_ecosystem()
    doc = ecosystem_to_dict(eco)
    assert doc["damage_model"] == "area_loss"
    again = ecosystem_from_dict(doc)
    assert again.damage_model == "area_loss"
    assert run_extraction(again, 1200).annual_externality == run_extraction(
        eco, 1200).annual_externality


# ── Step 8c.2: the service ledger ────────────────────────────────────────────

def test_service_ledger_counts_each_service_once_and_prices_every_agent():
    """Each final service appears exactly once and belongs to one agent;
    every agent's value is > 0 and is exactly its ledger services."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    ledger = case.service_ledger
    services = [e["service"] for e in ledger]
    assert len(services) == len(set(services))
    # a split service is never also counted whole, and its shares add to 1
    parents = {e["split_of"] for e in ledger if e["split_of"]}
    assert not parents & set(services)
    for parent in parents:
        assert sum(e["share"] for e in ledger if e["split_of"] == parent) == pytest.approx(1.0)
    by_agent = case.ledger_by_agent()
    regional = case.ledger_by_agent(regional=True)
    eco = case.build_ecosystem()
    assert set(by_agent) == {a.name for a in eco.agents}
    for a in eco.agents:
        assert a.annual_value_per_ha > 0.0 and a.annual_value(1.0) > 0.0
        # per hectare near the sites for a site-restricted agent (Step 8d.4)
        assert a.dependency_weight * a.annual_value_per_ha == pytest.approx(by_agent[a.name], rel=1e-12)
        # per hectare of the reference resource, as the run uses it
        assert a.dependency_weight * a.annual_value(1.0) == pytest.approx(regional[a.name], rel=1e-12)
    assert sum(regional.values()) == pytest.approx(818.6635785921815, rel=1e-12)
    assert case.ledger_check() == []
    # every agent stays > 0 at any project share above 0, and only the
    # site-restricted agent depends on it
    for share in (1.0, 0.5, 1e-3):
        eco_s = case.build_ecosystem(site_share=share)
        for a, b in zip(eco.agents, eco_s.agents):
            assert b.annual_value(1.0) > 0.0
            if a.name not in case.site_restricted_agents:
                assert b.annual_value(1.0) == a.annual_value(1.0)
    for e in ledger:
        assert e["source"] and e["method"]
        assert "doi:" in e["source"] or "Idescat" in e["source"]


def test_service_ledger_rejects_double_counting():
    import copy

    from gaia.cases import load_case
    from gaia.ecosystem_io import case_from_dict

    doc = copy.deepcopy(load_case("posidonia").document)
    doc["service_ledger"].append(dict(doc["service_ledger"][0], agent="Seabirds"))
    with pytest.raises(ValueError, match="counted once"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    whole = dict(doc["service_ledger"][0], service="Commercial fisheries contribution (35 EUR/ha/yr)")
    doc["service_ledger"].append(whole)
    with pytest.raises(ValueError, match="counted whole"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    doc["service_ledger"][2]["share"] = 0.95
    with pytest.raises(ValueError, match="add up to"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    doc["service_ledger"][0]["value"] = 0.0
    with pytest.raises(ValueError, match="must be > 0"):
        case_from_dict(doc)


def test_ledger_check_finds_an_unbooked_value():
    import copy

    from gaia.cases import load_case
    from gaia.ecosystem_io import case_from_dict

    doc = copy.deepcopy(load_case("posidonia").document)
    doc["agents"][0]["annual_value_per_ha"]["value"] *= 2
    problems = case_from_dict(doc).ledger_check()
    assert len(problems) == 1 and problems[0].startswith("Posidonia Meadow")


# ── Step 8d.4: the meadow's diving value only near dive sites ────────────────

def test_diving_value_applies_only_near_dive_sites():
    """Dives divided over the meadow within reach of dive sites (142.35 ha),
    times the share of the affected meadow near dive sites: the regional
    default gives back the former regional average."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    assert case.site_restricted_agents == ["Posidonia Meadow"]
    assert case.sites == "dive sites" and case.site_input == "dive-site-share"
    near = 34.71 * 60_000 / 142.35
    assert case.default_site_share == pytest.approx(142.35 / 4582, rel=1e-12)
    entry = next(e for e in case.service_ledger if e["agent"] == "Posidonia Meadow")
    assert entry["site_restricted"] and entry["value"] == pytest.approx(near, rel=1e-12)
    assert not any(e["site_restricted"] for e in case.service_ledger if e is not entry)

    def meadow(eco):
        a = next(a for a in eco.agents if a.name == "Posidonia Meadow")
        return a.dependency_weight * a.annual_value(1.0)

    assert meadow(case.build_ecosystem()) == pytest.approx(34.71 * 60_000 / 4582, rel=1e-12)
    assert meadow(case.build_ecosystem(site_share=1.0)) == pytest.approx(near, rel=1e-12)
    assert meadow(case.build_ecosystem(site_share=0.0)) == 0.0
    # a project at a dive site: 50 ha below the threshold cost 50 × the
    # ledger total with the meadow's near-site value
    others = sum(case.ledger_by_agent().values()) - near
    result = run_extraction(case.build_ecosystem(site_share=1.0), 50)
    assert result.annual_externality == pytest.approx(50 * (others + near), rel=1e-12)
    result = run_extraction(case.build_ecosystem(site_share=0.0), 50)
    assert result.annual_externality == pytest.approx(50 * others, rel=1e-12)


def test_site_share_is_a_recorded_project_input():
    from gaia.cases import load_case
    from gaia.provenance import Confidence
    from gaia.uncertainty import run_uncertainty

    case = load_case("posidonia")
    default = {p.name: p for p in case.build_ecosystem().provenance}
    share = default["agent[Posidonia Meadow].site_share"]
    assert share.confidence is Confidence.LOW and "Natura 2000" in share.source
    assert share.distribution == "fixed"
    given = {p.name: p for p in case.build_ecosystem(site_share=1.0).provenance}
    assert given["agent[Posidonia Meadow].site_share"].confidence is Confidence.USER
    assert "--dive-site-share" in given["agent[Posidonia Meadow].site_share"].source
    res = run_uncertainty(case, 50, build_kwargs={"site_share": 1.0}, draws=4,
                          tornado=False, normative=False)
    names = {s.name for s in res.sampled}
    assert "agent[Posidonia Meadow].site_share" not in names
    assert "agent[Posidonia Meadow].annual_value_per_ha" in names
    with pytest.raises(ValueError, match="site share must be in"):
        case.build_ecosystem(site_share=1.5)
    with pytest.raises(ValueError, match="no site-restricted agent"):
        load_case("forest").build_ecosystem(site_share=0.5)


def test_site_share_scales_the_meadow_anchor():
    from gaia.cases import load_case

    case = load_case("posidonia")

    def anchor(eco):
        return next(a.anchor_value for a in eco.pricing.anchors if a.agent_name == "Posidonia Meadow")

    base = anchor(case.build_ecosystem(with_pricing=True))
    near = anchor(case.build_ecosystem(with_pricing=True, site_share=1.0))
    assert near == pytest.approx(base * 4582 / 142.35, rel=1e-12)


def test_dive_site_share_cli(capsys):
    import json

    from gaia.cli import main

    assert main(["run", "posidonia", "--dive-site-share", "1", "--format", "json",
                 "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    meadow = next(a for a in out["ecosystem"]["agents"] if a["name"] == "Posidonia Meadow")
    assert meadow["site_share"] == 1.0 and meadow["sites"] == "dive sites"
    assert main(["run", "posidonia", "--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--dive-site-share F" in text and "within reach of dive sites" in text
    assert main(["run", "forest", "--dive-site-share", "1"]) == 2


def test_ledger_rejects_a_site_mismatch():
    import copy

    from gaia.cases import load_case
    from gaia.ecosystem_io import case_from_dict

    doc = copy.deepcopy(load_case("posidonia").document)
    entry = next(e for e in doc["service_ledger"] if e["agent"] == "Posidonia Meadow")
    entry["site_restricted"] = False
    with pytest.raises(ValueError, match="site_restricted: must be true"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    del next(a for a in doc["agents"] if a["name"] == "Posidonia Meadow")["sites"]
    with pytest.raises(ValueError, match="give both sites and site_share"):
        case_from_dict(doc)


# ── Step 8e.2: dive-activity intensity presets ───────────────────────────────

WTP_PER_DIVE = 34.71
LEVELS = {"none": 0.0, "low": 14_000 / 211.45, "medium": 40_000 / 70.61, "high": 60_000 / 10.75}


def _meadow_per_ha(eco):
    a = next(a for a in eco.agents if a.name == "Posidonia Meadow")
    return a.dependency_weight * a.annual_value(1.0)


def test_dive_intensity_levels_are_sourced_and_ordered():
    """none < low < medium < high dives per hectare of meadow near dive
    sites per year, each from a site count over its Natura 2000 meadow; the
    default is the Costa Brava average, between low and medium."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    levels = case.intensity_levels
    assert list(levels) == list(LEVELS)
    for name, value in LEVELS.items():
        assert levels[name]["value"] == pytest.approx(value, rel=1e-12)
        assert levels[name]["description"] and levels[name]["basis"]
    assert case.default_site_intensity == pytest.approx(60_000 / 142.35, rel=1e-12)
    assert LEVELS["low"] < case.default_site_intensity < LEVELS["medium"]
    assert case.intensity_input == "dive-intensity"
    assert case.site_intensity_unit == "dives/ha/yr"
    assert "doi:10.1002/aqc.3918" in levels["medium"]["basis"]
    assert "FR9101482" in levels["low"]["basis"] and "IT1332674" in levels["medium"]["basis"]
    assert "ES5120016" in levels["high"]["basis"]
    assert levels["low"]["confidence"] == "low" and "grey literature" in levels["low"]["basis"]


def test_default_run_is_unchanged_by_the_intensity():
    from gaia.cases import load_case

    case = load_case("posidonia")
    eco = case.build_ecosystem()
    assert _meadow_per_ha(eco) == pytest.approx(WTP_PER_DIVE * 60_000 / 4582, rel=1e-12)
    assert run_extraction(eco, 50).annual_externality == pytest.approx(
        50 * 818.6635785921815, rel=1e-12)


@pytest.mark.parametrize("level", list(LEVELS))
def test_intensity_sets_the_value_near_dive_sites_and_share_the_part_near_them(level):
    """Value per hectare of the affected meadow = WTP per dive × the level's
    dives per hectare near dive sites × the share near them (1 when only
    the intensity is given)."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    near = WTP_PER_DIVE * LEVELS[level]
    assert _meadow_per_ha(case.build_ecosystem(site_intensity=level)) == pytest.approx(near, rel=1e-12, abs=1e-12)
    assert _meadow_per_ha(case.build_ecosystem(site_intensity=level, site_share=0.25)) == pytest.approx(
        0.25 * near, rel=1e-12, abs=1e-12)
    others = sum(case.ledger_by_agent().values()) - WTP_PER_DIVE * 60_000 / 142.35
    result = run_extraction(case.build_ecosystem(site_intensity=level), 50)
    assert result.annual_externality == pytest.approx(50 * (others + near), rel=1e-12)


def test_intensity_never_counts_a_service_twice_and_none_zeroes_only_diving():
    """Only the meadow's diving value moves with the intensity; every other
    agent keeps its value (> 0). 'none' zeroes the meadow's diving service,
    its only ledger entry, so the meadow agent alone is at 0 (flagged in
    the docs: the meadow's other services are owned by other agents)."""
    from gaia.cases import load_case

    case = load_case("posidonia")
    base = case.build_ecosystem()
    for level in LEVELS:
        eco = case.build_ecosystem(site_intensity=level)
        for a, b in zip(base.agents, eco.agents):
            if a.name in case.site_restricted_agents:
                assert (b.annual_value(1.0) == 0.0) is (level == "none")
            else:
                assert b.annual_value(1.0) == a.annual_value(1.0) > 0.0
    assert case.ledger_check() == []
    meadow_entries = [e for e in case.service_ledger if e["agent"] == "Posidonia Meadow"]
    assert len(meadow_entries) == 1 and meadow_entries[0]["site_restricted"]


def test_intensity_is_a_recorded_project_input_not_sampled():
    from gaia.cases import load_case
    from gaia.provenance import Confidence
    from gaia.uncertainty import run_uncertainty

    case = load_case("posidonia")
    default = {p.name: p for p in case.build_ecosystem().provenance}
    intensity = default["agent[Posidonia Meadow].site_intensity"]
    assert intensity.confidence is Confidence.LOW and intensity.distribution == "fixed"
    assert intensity.unit == "dives/ha/yr"
    given = {p.name: p for p in case.build_ecosystem(site_intensity="high").provenance}
    p = given["agent[Posidonia Meadow].site_intensity"]
    assert p.confidence is Confidence.USER and p.value == pytest.approx(LEVELS["high"])
    assert "--dive-intensity high" in p.source and "Medes" in p.source
    share = given["agent[Posidonia Meadow].site_share"]
    assert share.confidence is Confidence.USER and share.value == 1.0
    assert "without --dive-site-share" in share.source
    both = {p.name: p for p in case.build_ecosystem(site_intensity="low", site_share=0.5).provenance}
    assert both["agent[Posidonia Meadow].site_share"].value == 0.5
    assert "--dive-site-share" in both["agent[Posidonia Meadow].site_share"].source
    res = run_uncertainty(case, 50, build_kwargs={"site_intensity": "medium"}, draws=4,
                          tornado=False, normative=False)
    names = {s.name for s in res.sampled}
    assert "agent[Posidonia Meadow].site_intensity" not in names
    assert "agent[Posidonia Meadow].annual_value_per_ha" in names
    with pytest.raises(ValueError, match="unknown dive-intensity level"):
        case.build_ecosystem(site_intensity="extreme")
    with pytest.raises(ValueError, match="no site intensity levels"):
        load_case("forest").build_ecosystem(site_intensity="low")


def test_intensity_scales_the_meadow_anchor():
    from gaia.cases import load_case

    case = load_case("posidonia")

    def anchor(eco):
        return next(a.anchor_value for a in eco.pricing.anchors if a.agent_name == "Posidonia Meadow")

    base = anchor(case.build_ecosystem(with_pricing=True))
    high = anchor(case.build_ecosystem(with_pricing=True, site_intensity="high", site_share=0.1))
    assert high == pytest.approx(base * 0.1 * 4582 / 142.35 * LEVELS["high"] / (60_000 / 142.35), rel=1e-12)
    with pytest.raises(ValueError, match="anchor of Posidonia Meadow > 0"):
        case.build_ecosystem(with_pricing=True, site_intensity="none")


def test_dive_intensity_cli(capsys):
    import json

    from gaia.cli import main

    assert main(["run", "posidonia", "--dive-intensity", "low", "--format", "json",
                 "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    params = {p["name"]: p for p in out["calibration"]["parameters"]}
    assert params["agent[Posidonia Meadow].site_intensity"]["confidence"] == "user-supplied"
    assert main(["run", "posidonia", "--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--dive-intensity {none,low,medium,high}" in text
    assert "dives/ha/yr" in text and "Portofino" in text and "Medes" in text
    assert main(["run", "posidonia", "--dive-intensity", "extreme"]) == 2
    assert main(["run", "forest", "--dive-intensity", "low"]) == 2


def test_intensity_document_errors():
    import copy

    from gaia.cases import load_case
    from gaia.ecosystem_io import case_from_dict

    def meadow(doc):
        return next(a for a in doc["agents"] if a["name"] == "Posidonia Meadow")

    doc = copy.deepcopy(load_case("posidonia").document)
    del meadow(doc)["site_intensity"]
    with pytest.raises(ValueError, match="needs site_intensity"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    meadow(doc)["site_intensity_levels"]["low"]["value"] = -1.0
    with pytest.raises(ValueError, match="must be >= 0"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    m = meadow(doc)
    for key in ("sites", "site_share"):
        del m[key]
    for e in doc["service_ledger"]:
        e.pop("site_restricted", None)
    with pytest.raises(ValueError, match="needs sites and site_share"):
        case_from_dict(doc)


# ── Step 8d.1: every case prices small losses linearly ──────────────────────

@pytest.mark.parametrize("case", ["forest", "costa_brava", "amazon_forest"])
def test_other_cases_price_small_losses_linearly(case):
    """Below the safe threshold the annual externality is exactly the area
    lost × the per-hectare value at full damage, and each unit lost costs
    its average value; past it the remaining forest degrades and units cost
    more."""
    from gaia.cases import load_case

    eco = load_case(case).build_ecosystem()
    assert eco.damage_model == "area_loss"
    n, area = eco.resource.total_units, eco.resource.area_ha
    full = sum(a.dependency_weight * a.annual_value(area) for a in eco.agents)
    k = int(0.5 * eco.resource.safe_threshold_ratio * n)
    result = run_extraction(eco, k)
    assert result.annual_externality == pytest.approx(full * k / n, rel=1e-12)
    assert result.steps[-1].marginal_annual_externality == pytest.approx(full / n, rel=1e-9)
    past = run_extraction(eco, int((eco.resource.safe_threshold_ratio + 0.1) * n))
    assert past.annual_externality > full * past.steps[-1].units_extracted / n
