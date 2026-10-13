"""
Step 8.3: per-hectare benchmarks (gaia.benchmarks, run.benchmarks in a case
document) — where Gaia's per-hectare values fall among published ones.
"""

import copy
import json

import pytest

from gaia.benchmarks import benchmark_comparison, format_benchmarks
from gaia.cases import case_data_path, load_case
from gaia.ecosystem_io import case_from_dict, read_json


def _doc():
    return read_json(case_data_path("posidonia"))


def test_posidonia_comparison_figures():
    case = load_case("posidonia")
    result = case.run_extraction(50)
    block = case.benchmark_block(result)
    eco = result.ecosystem
    full = sum(a.dependency_weight * a.annual_value(1.0) for a in eco.agents)
    assert block["full_damage_eur_per_ha_yr"] == round(full, 2) == 1209.95  # the ledger (Step 8e.6: + the meadow's food production; 8f.1: TE 14.3%)
    burial = eco.resource.carbon_profile.annual_absorption_tonnes * result.discount.carbon_price_at_year(0)
    assert block["carbon_burial_eur_per_ha_yr"] == round(burial, 2)
    assert block["hectares_lost"] == 50
    assert block["realised_loss_eur_per_ha_yr"] == round(result.annual_externality / 50, 2)
    assert block["linear_transfer_eur_yr"] == round(full * 50, 2)
    rows = {r["name"].split(",")[0] + str(r["includes_carbon"]): r for r in block["benchmarks"]}
    # the ledger adds recreation and non-use values to Campagne et al.'s services
    assert rows["Campagne et al. 2015False"]["position"] == "above"
    costanza = next(r for r in block["benchmarks"] if r["name"].startswith("Costanza"))
    assert costanza["position"] == "below" and costanza["benchmark_central_over_gaia"] > 10


def test_text_and_json_carry_the_block():
    case = load_case("posidonia")
    result = case.run_extraction(50)
    assert "Benchmarks (per hectare" in case.report(result)
    from gaia.serialization import to_json
    d = json.loads(to_json(result, include_steps=False,
                           extra={"benchmarks": case.benchmark_block(result)}))
    assert d["benchmarks"]["full_damage_eur_per_ha_yr"] == 1209.95


def test_no_benchmarks_no_block():
    case = load_case("forest")
    result = case.run_extraction(100, total_units=1000)
    assert case.benchmark_block(result) is None
    assert format_benchmarks(None) == ""
    assert "Benchmarks (per hectare" not in case.report(result)


def test_restoration_has_no_block():
    case = load_case("posidonia")
    assert benchmark_comparison(case.run_restoration(10), case.benchmarks) is None


@pytest.mark.parametrize("change,message", [
    ({"low": 5.0, "high": 1.0}, "is above high"),
    ({"central": 1e9}, "outside"),
    ({"unit": 3}, "unit"),
])
def test_benchmark_entries_are_validated(change, message):
    doc = _doc()
    doc = copy.deepcopy(doc)
    doc["run"]["benchmarks"][0].update(change)
    with pytest.raises(ValueError, match=message):
        case_from_dict(doc)
