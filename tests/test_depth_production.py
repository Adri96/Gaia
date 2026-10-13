"""
Step 8g.1: the depth → primary production function of a marine primary
producer (gaia.production, DEPTH_MODEL), its hyperparameters in the case
file, the project depth (--depth-m) and its Monte Carlo links.
"""

import copy
import json
import math
import random
import sys
from pathlib import Path

import pytest

from gaia.cases import load_case
from gaia.cli import main
from gaia.ecosystem_io import case_from_dict
from gaia.production import (
    DEPTH_MODEL,
    central,
    depth_npp,
    gross_value,
    mean_depth_npp,
    net_of_scale,
    net_range,
    parse_production_function,
    profile_npp,
    with_project_depth,
)

ROOT = Path(__file__).resolve().parent.parent
MEADOW = "Posidonia Meadow"


def _meadow_entry(case):
    return next(e for e in case.service_ledger if e["agent"] == MEADOW and e["production_function"] is not None)


def _hyper(case):
    params = _meadow_entry(case)["production_function"]["parameters"]
    return (params["depth.npp_at_reference_depth"]["value"], params["depth.decline_rate"]["value"],
            params["depth.depth_limit"]["value"], 10.0)


# ── The function ─────────────────────────────────────────────────────────────


def test_production_declines_monotonically_and_is_convex():
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    depths = [z / 10 for z in range(0, int(z_max * 10))]
    values = [depth_npp(z, p, k, z_max, z_ref) for z in depths]
    assert all(a > b > 0.0 for a, b in zip(values, values[1:]))
    # convex: the production at a mean depth is below the mean production
    assert all(c - b > b - a for a, b, c in zip(values, values[1:], values[2:]))
    assert depth_npp(15.0, p, k, z_max, z_ref) < mean_depth_npp(0.0, 30.0, p, k, z_max, z_ref)
    assert depth_npp(z_ref, p, k, z_max, z_ref) == pytest.approx(p, rel=1e-12)


def test_production_is_zero_at_the_depth_limit_and_a_deeper_input_is_rejected():
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    assert depth_npp(z_max - 1e-9, p, k, z_max, z_ref) == pytest.approx(0.0, abs=1e-6)
    for bad in (z_max, z_max + 5.0, -1.0, float("nan")):
        with pytest.raises(ValueError, match="depth limit"):
            depth_npp(bad, p, k, z_max, z_ref)
    with pytest.raises(ValueError, match="depth limit"):
        mean_depth_npp(10.0, z_max, p, k, z_max, z_ref)


def test_band_mean_is_the_integral_of_the_function():
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    n = 20_000
    numeric = sum(depth_npp(5.0 + 20.0 * (i + 0.5) / n, p, k, z_max, z_ref) for i in range(n)) / n
    assert mean_depth_npp(5.0, 25.0, p, k, z_max, z_ref) == pytest.approx(numeric, rel=1e-6)
    assert profile_npp([(5.0, 10.0, 0.25), (10.0, 25.0, 0.75)], p, k, z_max, z_ref) == pytest.approx(
        0.25 * mean_depth_npp(5.0, 10.0, p, k, z_max, z_ref) + 0.75 * mean_depth_npp(10.0, 25.0, p, k, z_max, z_ref))


def test_posidonia_production_at_depth():
    """The fitted function at the depths the report and the docs quote."""
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    expected = {5: 769.5, 10: 498.8, 15: 317.6, 20: 196.3, 25: 115.1, 30: 60.7}
    for z, v in expected.items():
        assert depth_npp(z, p, k, z_max, z_ref) == pytest.approx(v, abs=0.05)


# ── The case file ────────────────────────────────────────────────────────────


def test_hyperparameters_are_the_fit_of_the_data_in_the_case_file():
    """scripts/fit_depth_production.py reproduces the case file's
    hyperparameters and ranges from the measurements it lists."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import fit_depth_production
    finally:
        sys.path.pop(0)
    assert fit_depth_production.main(["posidonia", "--check"]) == 0
    doc = load_case("posidonia").document
    (_, depth, result), = fit_depth_production.fits_of(doc)
    assert depth["model"] == DEPTH_MODEL and result["n"] == 6
    assert sorted(row["depth_m"] for row in depth["data"]) == [4.0, 5.0, 5.0, 10.0, 13.0, 20.0]
    assert all(row["status"] == "verified" and "doi:" in row["source"] for row in depth["data"])
    # the Medes 13 m figure, blades 219 + sheaths 37 + rhizomes 15
    assert next(r for r in depth["data"] if r["depth_m"] == 13.0)["value"] == 271.0
    assert abs(result["correlation"]) < 0.2


def test_every_hyperparameter_is_sourced_and_flagged():
    params = _meadow_entry(load_case("posidonia"))["production_function"]["parameters"]
    for name in ("npp_at_reference_depth", "decline_rate", "depth_limit"):
        p = params[f"depth.{name}"]
        assert p["status"] in ("derived", "inferred") and p["distribution"] != "fixed"
        assert p["range"][0] < p["value"] < p["range"][1] and p["distribution_basis"]
    assert params["depth.depth_limit"]["range"] == (30.0, 44.0)
    assert "doi:10.1016/j.marpolbul.2009.06.012" in params["depth.depth_limit"]["source"]


def test_a_case_file_supplies_the_hyperparameters_of_another_producer():
    """Generic: a macroalga, say, whose production in carbon is given by its
    own hyperparameters only (the shape is shared)."""
    raw = copy.deepcopy(load_case("posidonia").document)
    pf = next(e for e in raw["service_ledger"] if "production_function" in e)["production_function"]
    pf = copy.deepcopy(pf)
    del pf["parameters"]["carbon_fraction"]
    depth = pf["depth_production"]
    depth["output"] = "npp_carbon"
    hyper = depth["parameters"]
    hyper["npp_at_reference_depth"].update(value=200.0, range=[100.0, 400.0], unit="g C/m²/yr")
    hyper["decline_rate"].update(value=0.15, range=[0.1, 0.2])
    hyper["depth_limit"].update(value=25.0, range=[20.0, 30.0])
    depth["regional_depth"] = {"distribution": [{"from_m": 0.0, "to_m": 5.0, "share": 0.5},
                                                {"from_m": 5.0, "to_m": 15.0, "share": 0.5}],
                               "source": "test", "status": "inferred"}
    spec = parse_production_function(pf, "pf")
    v = central(spec)
    assert v["npp_carbon"] == pytest.approx(
        profile_npp([(0.0, 5.0, 0.5), (5.0, 15.0, 0.5)], 200.0, 0.15, 25.0, 10.0), rel=1e-12)
    assert gross_value(v) > 0.0
    # a regional band at or below the shallowest depth limit is rejected
    depth["regional_depth"]["distribution"][1]["to_m"] = 20.0
    with pytest.raises(ValueError, match="depth limit"):
        parse_production_function(pf, "pf")
    # the NPP it derives cannot also be given
    depth["regional_depth"]["distribution"][1]["to_m"] = 15.0
    pf["parameters"]["npp_carbon"] = dict(hyper["npp_at_reference_depth"])
    with pytest.raises(ValueError, match="derived from depth_production"):
        parse_production_function(pf, "pf")


# ── A project depth ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("depth", [(0.5, 0.5), (5.0, 5.0), (15.0, 15.0), (25.0, 25.0), (29.9, 29.9),
                                   (2.0, 28.0), (10.0, 20.0)])
def test_project_depth_values_the_meadow_at_that_depth(depth):
    case = load_case("posidonia")
    at = case.with_project_depth(*depth)
    entry = _meadow_entry(at)
    spec = entry["production_function"]
    p, k, z_max, z_ref = _hyper(case)
    assert central(spec)["npp_dry_weight"] == pytest.approx(mean_depth_npp(*depth, p, k, z_max, z_ref), rel=1e-12)
    scale = net_of_scale(spec)
    assert scale == pytest.approx(central(spec)["npp_dry_weight"] / mean_depth_npp(15.0, 15.0, p, k, z_max, z_ref))
    assert entry["value"] == pytest.approx(entry["gross"] - 35.0 * scale, rel=1e-12)
    low, _ = net_range(spec, 35.0)
    assert entry["value"] > low > 0.0
    weight = next(a.weight for a in at.agents if a.name == MEADOW)
    eco = at.build_ecosystem(site_intensity="none")
    meadow = next(a for a in eco.agents if a.name == MEADOW)
    assert meadow.dependency_weight * meadow.annual_value_per_ha == pytest.approx(entry["value"], rel=1e-9)
    assert meadow.annual_value_per_ha * weight > 0.0
    assert at.ledger_check() == []


def test_the_regional_run_subtracts_exactly_the_booked_catch():
    """Owner's decision (PR #10, question 3): the fixed €35, no coupling."""
    entry = _meadow_entry(load_case("posidonia"))
    assert net_of_scale(entry["production_function"]) == 1.0
    assert entry["gross"] - entry["value"] == pytest.approx(35.0, rel=1e-12)


@pytest.mark.parametrize("bad", [(30.0, 30.0), (35.0, 35.0), (10.0, 31.0), (-1.0, -1.0), (45.0, 45.0)])
def test_a_depth_at_or_below_the_depth_limit_is_rejected(bad):
    with pytest.raises(ValueError, match="depth"):
        load_case("posidonia").with_project_depth(*bad)


def test_a_case_without_a_depth_function_rejects_a_depth():
    with pytest.raises(ValueError, match="no depth-dependent production function"):
        with_project_depth(load_case("forest").document, 10.0, 10.0)


def test_deeper_meadows_are_worth_less_and_never_zero():
    case = load_case("posidonia")
    nets = [_meadow_entry(case.with_project_depth(z, z))["value"] for z in (1, 5, 10, 15, 20, 25, 29.9)]
    assert all(a > b > 0.0 for a, b in zip(nets, nets[1:]))


# ── The command line ─────────────────────────────────────────────────────────


def test_cli_depth_input_is_shown_in_text_and_json(capsys):
    assert main(["run", "posidonia", "--depth-m", "25", "--format", "json", "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    block = out["production_functions"][MEADOW]["depth_production"]
    assert block["depth_used"] == "project" and block["depth_label"].startswith("25 m")
    assert block["npp"] == pytest.approx(115.07, abs=0.01)
    assert set(block["npp_at_depth"]) == {"5", "10", "15", "20", "25", "30"}
    assert main(["run", "posidonia", "--depth-m", "5-20"]) == 0
    text = capsys.readouterr().out
    assert "Taken at 5–20 m (the project's depth)" in text
    meadow_line = " ".join(text[text.index("Posidonia Meadow:"):text.index("Coralligenous & Red Coral:")].split())
    assert "at 5–20 m (the project's depth)" in meadow_line


def test_cli_rejects_a_depth_beyond_the_limit_in_plain_words(capsys):
    assert main(["run", "posidonia", "--depth-m", "35"]) == 1
    err = capsys.readouterr().err
    assert "depth limit" in err and "not value an agent at €0" in err
    for bad in ("deep", "20-10", "1-2-3"):
        assert main(["run", "posidonia", "--depth-m", bad]) == 2
        assert "--depth-m" in capsys.readouterr().err


def test_help_explains_the_depth_input(capsys):
    assert main(["run", "posidonia", "--help"]) == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "--depth-m" in help_text and "Default: 15 m (the regional mean depth)" in help_text
    assert "shallower than 30 m" in help_text


# ── Monte Carlo ──────────────────────────────────────────────────────────────


def test_hyperparameters_are_sampled_links_reproducibly():
    from gaia.uncertainty import run_uncertainty

    case = load_case("posidonia").with_project_depth(20.0, 20.0)
    runs = [run_uncertainty(case, 20, draws=60, seed=5, tornado=False, normative=False) for _ in range(2)]
    links = runs[0].production[MEADOW]["links"]
    assert {"depth.npp_at_reference_depth", "depth.decline_rate", "depth.depth_limit"} <= set(links)
    assert runs[0].production == runs[1].production
    block = runs[0].production[MEADOW]
    assert block["draws_at_or_below_zero"] == 0 and block["net"]["min"] > 0.0


def test_random_depths_and_draws_never_reach_zero():
    """A seeded property test: random project depths, then hyperparameters
    and links drawn anywhere in their ranges, never bring the meadow to €0."""
    from gaia.uncertainty import _rederive_production, _set_at_path, production_entries

    rng = random.Random(8)
    case = load_case("posidonia")
    for _ in range(30):
        a = rng.uniform(0.0, 29.9)
        b = rng.choice([a, rng.uniform(a, 29.9)])
        at = case.with_project_depth(a, b)
        entries = production_entries(at)
        doc = copy.deepcopy(at.document)
        for e in entries:
            spec = at.service_ledger[e.index]["production_function"]
            for name, p in spec["parameters"].items():
                if p.get("range") and p["distribution"] != "fixed":
                    _set_at_path(doc, f"$.service_ledger[{e.index}].production_function.{spec['paths'][name]}",
                                 rng.choice([p["range"][0], p["range"][1], rng.uniform(*p["range"])]))
        produced = _rederive_production(doc, entries)
        assert all(net > 0.0 for _, net in produced.values())
        case_from_dict(doc)
        assert not math.isnan(sum(n for _, n in produced.values()))
