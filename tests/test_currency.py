"""
Step 8g.6: international dollars are converted to euros at Spain's PPP for
household consumption (World Bank PA.NUS.PRVT.PP), in one place
(gaia.currency), and no case file carries an Int$ value without it.
"""

import copy
import re

import pytest

from gaia.cases import CASE_NAMES, load_case
from gaia.currency import (
    EUR_PER_INT_DOLLAR,
    check_converted,
    conversion_note,
    eur_per_int_dollar,
    int_dollars_to_eur,
)
from gaia.ecosystem_io import case_from_dict

# a text that says a number is (or was) in international or US dollars
_DOLLARS = re.compile(r"Int\.?\s?\$|international \$|international dollar|\$\s?2007|2007\s?\$|\$/ha", re.I)
_NUMBERS = ("value", "anchor_value", "low", "high", "central")


def test_the_factors_are_the_world_bank_series():
    """PA.NUS.PRVT.PP, Spain (read from the World Bank API, 13 October 2026)."""
    assert EUR_PER_INT_DOLLAR == {2007: 0.808165, 2020: 0.686508}
    assert int_dollars_to_eur(3220, 2007) == pytest.approx(2602.2913, rel=1e-12)
    assert eur_per_int_dollar(2020) == 0.686508
    with pytest.raises(ValueError, match="no PPP factor recorded for price year 1999"):
        eur_per_int_dollar(1999)


def test_check_converted_holds_the_value_to_the_factor():
    block = {"currency": "Int$", "price_year": 2007, "amounts": {"value": 2861}}
    converted = check_converted(block, "$.x.converted_from", {"value": 2861 * 0.808165})
    assert converted["factor"] == 0.808165 and converted["amounts"] == {"value": 2861.0}
    assert "0.808165" in conversion_note(converted) and "PA.NUS.PRVT.PP" in conversion_note(converted)
    with pytest.raises(ValueError, match="but the file gives 2861"):
        check_converted(block, "$.x.converted_from", {"value": 2861})        # used at face value
    with pytest.raises(ValueError, match="only 'Int\\$' is converted"):
        check_converted(dict(block, currency="US$"), "$.x", {"value": 1.0})
    with pytest.raises(ValueError, match="not a field of this object"):
        check_converted(dict(block, amounts={"high": 1}), "$.x", {"value": 1.0})


def _objects(node, path="$"):
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _objects(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _objects(value, f"{path}[{i}]")


@pytest.mark.parametrize("name", CASE_NAMES)
def test_no_case_file_carries_an_int_dollar_value_without_the_conversion(name):
    """Every number whose object speaks of international (or US) dollars
    carries ``converted_from`` and is its amount × the PPP factor (parsing
    checks the product); no unit is in dollars."""
    doc = load_case(name).document
    found = 0
    for path, obj in _objects(doc):
        if not any(isinstance(obj.get(k), (int, float)) and not isinstance(obj.get(k), bool) for k in _NUMBERS):
            continue
        assert "$" not in str(obj.get("unit", "")), f"{name} {path}: unit {obj.get('unit')!r}"
        text = " ".join(str(obj.get(k, "")) for k in ("source", "note", "unit", "description", "name"))
        if _DOLLARS.search(text):
            assert "converted_from" in obj, f"{name} {path}: an Int$ value at face value"
            found += 1
    if name in ("forest", "costa_brava", "amazon_forest", "posidonia"):
        assert found > 0


@pytest.mark.parametrize("name", ["forest", "costa_brava", "amazon_forest"])
def test_a_value_at_face_value_is_rejected(name):
    doc = copy.deepcopy(load_case(name).document)
    value = doc["agent_defaults"]["annual_value_per_ha"]
    value["value"] = value["converted_from"]["amounts"]["value"]
    with pytest.raises(ValueError, match="convert at the recorded PPP factor"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case(name).document)
    anchor = doc["pricing"]["anchors"][0]
    anchor["anchor_value"] = anchor["converted_from"]["amounts"]["anchor_value"]
    with pytest.raises(ValueError, match="anchors\\[0\\].converted_from"):
        case_from_dict(doc)


def test_the_converted_values():
    """Forest: Int$(3,013 − 152); Costa Brava: Int$(1,588 − 7); Amazon:
    Int$(5,264 − 2,044) (de Groot et al. 2012, Table 2), × 0.808165."""
    expected = {"forest": 2861, "costa_brava": 1581, "amazon_forest": 3220}
    for name, amount in expected.items():
        param = {p.name: p for p in load_case(name).buckets["agent_values"]}["agents.annual_value_per_ha"]
        assert param.value == pytest.approx(amount * 0.808165, rel=1e-12)
        assert "PA.NUS.PRVT.PP" in param.note and "0.808165" in param.note
    bench = {b["name"].split(",")[0]: b for b in load_case("posidonia").benchmarks}
    assert bench["Stamatiadou et al. 2025"]["central"] == pytest.approx(8712 * 0.686508, rel=1e-12)
    assert bench["de Groot et al. 2012 (ESVD/TEEB)"]["central"] == pytest.approx(28917 * 0.808165, rel=1e-12)
    assert all("PPP" in b["unit"] for b in bench.values() if "Campagne" not in b["name"])


def test_a_monte_carlo_draw_drops_the_conversion_record():
    """A draw is not the converted figure: the perturbed copy is still valid."""
    from gaia.uncertainty import run_uncertainty

    u = run_uncertainty(load_case("forest"), 300, build_kwargs={"total_units": 1000},
                        draws=5, seed=3, tornado=False, normative=False)
    assert u.redraws == 0
