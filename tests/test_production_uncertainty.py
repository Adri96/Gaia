"""
Step 8f.3: the Monte Carlo of a production function samples each link of
the chain on its own and recomputes gross − net_of in every draw, instead
of sampling the agent's value as one aggregate between the ends of every
link at once (gaia.uncertainty, gaia.production). Generic over case files;
no draw may bring the agent to €0 (PROJECT_DEFINITION.md, Core Valuation
Principles (b)).
"""

import copy
import json

import pytest

from gaia.cases import load_case
from gaia.cli import main
from gaia.ecosystem_io import case_from_dict
from gaia.production import central, gross_range, gross_value, parse_production_function
from gaia.uncertainty import (
    InvariantError,
    Sampled,
    _rederive_production,
    _set_at_path,
    production_entries,
    run_uncertainty,
    uncertainty_to_dict,
)

MEADOW = "Posidonia Meadow"
LINKS = {
    "npp_dry_weight": "lognormal",
    "food_web_share": "triangular",
    "transfer_efficiency": "triangular",
    "catch_trophic_level": "triangular",
    "sustainable_catch_share": "triangular",
    "roots.npp_dry_weight": "uniform",
    "roots.food_web_share": "uniform",
    "epiphytes.npp_carbon": "lognormal",
    "epiphytes.food_web_share": "triangular",
}


def _run(case=None, draws=300, seed=11, **kwargs):
    return run_uncertainty(case or load_case("posidonia"), 50, draws=draws, seed=seed,
                           tornado=False, normative=False, **kwargs)


@pytest.fixture(scope="module")
def mc():
    return _run()


def _food(doc):
    return next(e for e in doc["service_ledger"] if "production_function" in e)


def test_each_link_is_sampled_on_its_own(mc):
    sampled = {s.name: s for s in mc.sampled if s.name.startswith(f"production[{MEADOW}].")}
    assert {n.split("].", 1)[1]: s.kind for n, s in sampled.items()} == LINKS
    for s in sampled.values():
        assert s.documented and s.low < s.high
    # the fixed links (no range, or "fixed") are not sampled
    assert not any(n.endswith((".carbon_fraction", ".wet_weight_per_carbon", ".first_sale_price"))
                   for n in sampled)
    # the meadow's value is not sampled as one aggregate: it is derived
    assert f"agent[{MEADOW}].annual_value_per_ha" not in {s.name for s in mc.sampled}
    derived = [r for r in mc.not_sampled if r.startswith("derived in each draw")]
    assert mc.not_sampled[derived[0]] == [f"agent[{MEADOW}].annual_value_per_ha"]
    assert mc.production[MEADOW]["links"] == list(LINKS)


def test_each_draw_recomputes_gross_minus_net_of():
    case = load_case("posidonia")
    entries = production_entries(case)
    (entry,) = entries
    doc = copy.deepcopy(case.document)
    base = central(case.service_ledger[entry.index]["production_function"])
    path = f"$.service_ledger[{entry.index}].production_function.parameters.transfer_efficiency"
    _set_at_path(doc, path, 0.2)
    _set_at_path(doc, f"$.service_ledger[{entry.index}].production_function.producers[1].parameters.npp_carbon", 30.0)
    produced = _rederive_production(doc, entries)
    gross = gross_value(dict(base, transfer_efficiency=0.2, **{"epiphytes.npp_carbon": 30.0}))
    assert produced[MEADOW] == pytest.approx((gross, gross - 35.0), rel=1e-12)
    food = _food(doc)
    assert (food["gross"], food["value"]) == pytest.approx((gross, gross - 35.0), rel=1e-12)
    meadow = case_from_dict(doc).build_ecosystem().agents[entry.agent_index]
    assert meadow.dependency_weight * meadow.annual_value_per_ha == pytest.approx(gross - 35.0, rel=1e-9)
    # the services it is net of keep their booked values
    assert sum(e["value"] for e in doc["service_ledger"] if e["service"] in food["net_of"]) == pytest.approx(35.0)


def test_draws_are_reproducible(mc):
    again = _run()
    assert again.production == mc.production and again.summary == mc.summary
    other = _run(seed=12)
    assert other.production[MEADOW]["net"] != mc.production[MEADOW]["net"]


def test_no_draw_is_at_or_below_zero(mc):
    block = mc.production[MEADOW]
    assert block["draws_at_or_below_zero"] == 0
    # the provable floor: every link at its least favourable end at once
    spec = load_case("posidonia").service_ledger[production_entries(load_case("posidonia"))[0].index]["production_function"]
    floor = gross_range(spec)[0] - 35.0
    assert floor > 0.0 and block["net"]["min"] >= floor
    assert block["net"]["p5"] < block["base"]["net"] < block["net"]["p95"]
    # the per-link sampling no longer reaches the corner: P5 is far above it
    assert block["net"]["p5"] > 4 * floor


def test_parse_rejects_a_chain_that_could_reach_zero():
    doc = copy.deepcopy(load_case("posidonia").document)
    _food(doc)["production_function"]["parameters"]["transfer_efficiency"]["range"] = [0.03, 0.218]
    with pytest.raises(ValueError, match="could bring the agent to €0.*Core Valuation Principles"):
        case_from_dict(doc)


def test_a_draw_at_zero_stops_the_run_and_is_never_redrawn():
    """InvariantError is not a ValueError, so the Monte Carlo cannot treat it
    as a validation failure and draw again (nor clip it)."""
    assert not issubclass(InvariantError, ValueError)
    case = load_case("posidonia")
    entries = production_entries(case)
    doc = copy.deepcopy(case.document)
    pf = _food(doc)["production_function"]
    pf["parameters"]["npp_dry_weight"].update(value=1.0, range=[0.5, 989.3])
    pf["producers"][1]["parameters"]["npp_carbon"].update(value=0.1, range=[0.05, 45.6])
    with pytest.raises(InvariantError, match="Core Valuation Principles"):
        _rederive_production(doc, entries)


def test_lognormal_stays_in_its_range_with_its_median_at_the_value():
    import random

    s = Sampled(name="x", path="$.x", value=22.8, low=11.4, high=45.6, kind="lognormal",
                documented=True, confidence="secondary")
    assert s.quantile(0.5) == pytest.approx(22.8, rel=1e-9)
    assert s.low <= s.quantile(0.0) < s.quantile(0.05) < s.quantile(0.95) < s.quantile(1.0) <= s.high
    rng = random.Random(1)
    draws = [s.draw(rng) for _ in range(2000)]
    assert min(draws) >= s.low and max(draws) <= s.high
    skewed = Sampled(name="y", path="$.y", value=476.0, low=238.0, high=989.3, kind="lognormal",
                     documented=True, confidence="verified")
    assert 238.0 <= skewed.quantile(0.01) < 476.0 < skewed.quantile(0.99) <= 989.3


def test_generic_without_net_of():
    """Any case file: a production function booked whole (no net_of)."""
    doc = copy.deepcopy(load_case("posidonia").document)
    food = _food(doc)
    del food["net_of"]
    gross = food["gross"]
    food["value"] = gross
    meadow = next(a for a in doc["agents"] if a["name"] == MEADOW)
    weight = meadow["dependency_weight"]
    spec = parse_production_function(food["production_function"], "pf")
    low, high = gross_range(spec)
    meadow["annual_value_per_ha"]["value"] = gross / weight
    meadow["annual_value_per_ha"]["range"] = [low / weight, high / weight]
    u = _run(case_from_dict(doc), draws=50, seed=3)
    block = u.production[MEADOW]
    assert block["base"] == {"gross": pytest.approx(gross), "net": pytest.approx(gross)}
    assert block["net"] == block["gross"] and block["net"]["min"] >= low


def test_text_and_json_report_the_production_draws(capsys):
    assert main(["run", "posidonia", "--uncertainty", "40", "--seed", "2"]) == 0
    out = capsys.readouterr().out
    assert "Posidonia Meadow, food from primary production" in out and "draws at or below €0: 0" in out
    assert main(["run", "posidonia", "--uncertainty", "40", "--seed", "2", "--format", "json",
                 "--summary-only"]) == 0
    block = json.loads(capsys.readouterr().out)["uncertainty"]["production_functions"][MEADOW]
    assert block["unit"] == "€/ha/yr" and block["draws_at_or_below_zero"] == 0
    assert 0.0 < block["net"]["p5"] < block["net"]["p50"] < block["net"]["p95"]
    assert block["links_sampled"] == list(LINKS)


def test_json_block_without_production_functions():
    u = run_uncertainty(load_case("forest"), 300, build_kwargs={"total_units": 1000},
                        draws=5, seed=3, tornado=False, normative=False)
    assert u.production == {} and uncertainty_to_dict(u)["production_functions"] is None
