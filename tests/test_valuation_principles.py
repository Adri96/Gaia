"""
The Core Valuation Principles (PROJECT_DEFINITION.md), (b): every agent in
every case always carries a positive euro value, under any input, preset or
flag. An agent at €0 is a defect, never a documented exception (Step 8e.7).

These tests hold the rule as an invariant:
    - every shipped case, built under every CLI preset and flag, gives every
      agent a value > 0, and every agent a cost > 0 once a unit is lost
      (extraction) or a recovered value > 0 (restoration);
    - the same for random combinations of the numeric inputs (a seeded
      property test);
    - no Monte Carlo draw can bring an agent to €0 (the low end of every
      agent-value range is > 0);
    - validation and case parsing reject an agent at €0, citing the rule.
"""

import copy
import itertools
import random
import warnings

import pytest

from gaia.cases import CASE_NAMES, load_case
from gaia.ecosystem_io import case_from_dict
from gaia.models import Agent
from gaia.simulation import run_extraction
from gaia.uncertainty import sampled_parameters
from gaia.validation import validate_ecosystem

RULE = "Core Valuation Principles"


def _assert_every_agent_positive(eco, label: str) -> None:
    for a in eco.agents:
        assert a.annual_value_per_ha > 0.0, f"{label}: {a.name} has no value on every hectare"
        assert a.annual_value(eco.resource.area_ha) > 0.0, f"{label}: {a.name} is at €0"


def _assert_every_cost_positive(eco, units: int, label: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_extraction(eco, units)
    costs = result.steps[-1].agent_annual_costs
    zero = [a.name for a, c in zip(eco.agents, costs) if not c > 0.0]
    assert not zero, f"{label}: {zero} cost €0 for {units} unit(s) lost"


def _grid(case):
    """Every combination of the case's presets and flags that changes an
    agent's value or the resource: site share and intensity (Posidonia's
    --dive-site-share, --dive-intensity), the release fate (--matte-fate),
    the reference resource (--area-ha / --total-units), the threshold, the
    unit value and EXPERIMENTAL pricing."""
    total = int(case.total_units.value)
    if case.unit == "ha":
        sizes = [dict(), dict(area_ha=50.0), dict(area_ha=300.0), dict(area_ha=float(total))]
    else:
        sizes = [dict(), dict(total_units=max(total // 100, 100)), dict(area_ha=case.area_ha * 2)]
    shares = [None] + ([0.0, 0.5, 1.0] if case.site_restricted_agents else [])
    levels = [None] + list(case.intensity_levels or {})
    fates = [None] + list(case.release_fates["fates"] if case.release_fates else [])
    thresholds = [None, 0.05, 0.6]
    for size, share, level, fate, threshold, pricing in itertools.product(
            sizes, shares, levels, fates, thresholds, (False, True)):
        kwargs = dict(size, site_share=share, site_intensity=level, carbon_fate=fate,
                      safe_threshold_ratio=threshold, with_pricing=pricing)
        yield {k: v for k, v in kwargs.items() if v is not None or k == "with_pricing"}


@pytest.mark.parametrize("name", CASE_NAMES)
def test_every_agent_is_positive_under_every_preset_and_flag(name):
    """The invariant over the full grid of presets and flags: every agent
    carries a value > 0 and costs > 0 as soon as one unit is lost."""
    case = load_case(name)
    n = 0
    for kwargs in _grid(case):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            eco = case.build_ecosystem(**kwargs)
        label = f"{name} {kwargs}"
        _assert_every_agent_positive(eco, label)
        units = 1 if kwargs["with_pricing"] else max(1, eco.resource.total_units // 50)
        _assert_every_cost_positive(eco, units, label)
        n += 1
    assert n >= 18


def test_dive_intensity_none_zeroes_a_service_never_an_agent():
    """The case the rule was written for: no dive site within reach."""
    case = load_case("posidonia")
    for kwargs in (dict(site_intensity="none"), dict(site_share=0.0),
                   dict(site_intensity="none", site_share=0.0, area_ha=300.0)):
        eco = case.build_ecosystem(**kwargs)
        _assert_every_agent_positive(eco, str(kwargs))
        meadow = next(a for a in eco.agents if a.name == "Posidonia Meadow")
        assert meadow.site_value_per_ha * meadow.site_share == 0.0      # the diving service
        assert meadow.dependency_weight * meadow.annual_value(1.0) > 200.0   # the meadow


@pytest.mark.parametrize("argv", [
    ["--dive-intensity", "none"],
    ["--dive-site-share", "0"],
    ["--area-ha", "300", "--units", "30", "--dive-intensity", "none"],
    ["--dive-intensity", "none", "--matte-fate", "excavated", "--with-pricing"],
    ["--mode", "restore", "--dive-intensity", "none", "--units", "10"],
])
def test_cli_never_reports_an_agent_at_zero(argv, capsys):
    import json

    from gaia.cli import main

    assert main(["run", "posidonia", *argv, "--format", "json", "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    summary = out["summary"]
    per_agent = summary.get("agent_externality_eur_yr") or summary.get("agent_service_value_eur_yr")
    values = per_agent.values() if isinstance(per_agent, dict) else per_agent
    assert all(v > 0.0 for v in values), per_agent
    for agent in out["ecosystem"]["agents"]:
        assert agent["annual_value_eur_yr"] > 0.0, agent["name"]


@pytest.mark.parametrize("name", CASE_NAMES)
def test_restoration_recovers_a_positive_value_for_every_agent(name):
    case = load_case(name)
    kwargs = dict(site_intensity="none") if case.intensity_levels else {}
    result = case.run_restoration(units=max(1, int(case.total_units.value) // 100), **kwargs)
    assert all(v > 0.0 for v in result.steps[-1].agent_service_values)


def test_random_inputs_never_bring_an_agent_to_zero():
    """A seeded property test: random reference sizes, thresholds, unit
    values, losses, site shares, intensities and fates, in every case."""
    rng = random.Random(20261013)
    cases = {name: load_case(name) for name in CASE_NAMES}
    for _ in range(200):
        name = rng.choice(CASE_NAMES)
        case = cases[name]
        total = int(case.total_units.value)
        kwargs = dict(
            safe_threshold_ratio=rng.uniform(0.02, 0.9),
            unit_value=rng.uniform(0.01, 10_000.0),
        )
        if case.unit == "ha":
            kwargs["area_ha"] = float(rng.randint(1, 3 * total))
        else:
            kwargs["total_units"] = rng.randint(10, 3 * total)
        if case.site_restricted_agents:
            if rng.random() < 0.7:
                kwargs["site_share"] = rng.choice([0.0, 1.0, rng.random()])
            if rng.random() < 0.7:
                kwargs["site_intensity"] = rng.choice(list(case.intensity_levels))
        if case.release_fates and rng.random() < 0.5:
            kwargs["carbon_fate"] = rng.choice(list(case.release_fates["fates"]))
        eco = case.build_ecosystem(**kwargs)
        label = f"{name} {kwargs}"
        _assert_every_agent_positive(eco, label)
        # up to the whole resource, capped to keep the suite fast
        units = rng.randint(1, min(eco.resource.total_units, 5_000))
        _assert_every_cost_positive(eco, units, label)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_no_monte_carlo_draw_can_bring_an_agent_to_zero(name):
    """Every sampled agent value has a range whose low end is > 0, and the
    case built with every agent value at its low end still prices every
    agent above €0."""
    case = load_case(name)
    params = [p for bucket in case.buckets.values() for p in bucket]
    sampled = {s.name: s for s in sampled_parameters(params, case.param_paths)}
    values = {n: s for n, s in sampled.items() if n.endswith("annual_value_per_ha")}
    assert values, f"{name}: no agent value is sampled"
    doc = copy.deepcopy(case.document)
    from gaia.uncertainty import _set_at_path

    for s in values.values():
        assert s.low > 0.0, f"{s.name}: range reaches {s.low}"
        _set_at_path(doc, s.path, s.low)
    low = case_from_dict(doc)
    for kwargs in ({}, dict(site_intensity="none") if case.intensity_levels else {}):
        _assert_every_agent_positive(low.build_ecosystem(**kwargs), f"{name} at the low ends {kwargs}")


def test_validation_rejects_an_agent_at_zero():
    eco = load_case("posidonia").build_ecosystem()
    meadow = eco.agents[0]
    for bad in (0.0, -1.0):
        agents = [Agent(**{**meadow.__dict__, "annual_value_per_ha": bad})] + eco.agents[1:]
        eco.agents = agents
        with pytest.raises(ValueError, match=RULE):
            validate_ecosystem(eco)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_parsing_rejects_an_agent_at_zero(name):
    case = load_case(name)
    doc = copy.deepcopy(case.document)
    agent = doc["agents"][0]
    if "annual_value_per_ha" in agent:
        target = agent["annual_value_per_ha"]
    else:
        target = doc["agent_defaults"]["annual_value_per_ha"]
    if isinstance(target, dict):
        target["value"] = 0.0
        target.pop("range", None)
        target.pop("relative_range", None)
    elif "annual_value_per_ha" in agent:
        agent["annual_value_per_ha"] = 0.0
    else:
        doc["agent_defaults"]["annual_value_per_ha"] = 0.0
    with pytest.raises(ValueError, match=RULE):
        case_from_dict(doc)


def test_parsing_rejects_a_range_reaching_zero_and_an_agent_without_an_everywhere_service():
    doc = copy.deepcopy(load_case("posidonia").document)
    meadow = next(a for a in doc["agents"] if a["name"] == "Posidonia Meadow")
    meadow["annual_value_per_ha"]["range"][0] = 0.0
    with pytest.raises(ValueError, match="low end of its range must be > 0"):
        case_from_dict(doc)
    # the meadow with its diving service only (the state before Step 8e.6)
    doc = copy.deepcopy(load_case("posidonia").document)
    doc["service_ledger"] = [e for e in doc["service_ledger"] if "production_function" not in e]
    with pytest.raises(ValueError, match="owns no service that applies on every hectare"):
        case_from_dict(doc)
