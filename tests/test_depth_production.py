"""
Step 8g.1: the depth → primary production function of a marine primary
producer (gaia.production, DEPTH_MODEL), its hyperparameters in the case
file, the project depth (--depth-m) and its Monte Carlo links. Step 8g.7:
every depth is valued, the site's depth limit conditioned on lying below
the meadow.
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


@pytest.mark.parametrize("bad", [(-1.0, -1.0), (-5.0, 10.0), (20.0, 10.0), (float("nan"), 10.0),
                                 (5.0, float("inf"))])
def test_only_an_impossible_depth_is_rejected(bad):
    """Step 8g.7: a negative depth, a reversed band or a non-number."""
    with pytest.raises(ValueError, match="project depth must be >= 0 m"):
        load_case("posidonia").with_project_depth(*bad)


def test_a_case_without_a_depth_function_rejects_a_depth():
    with pytest.raises(ValueError, match="no depth-dependent production function"):
        with_project_depth(load_case("forest").document, 10.0, 10.0)


def test_deeper_meadows_are_worth_less_and_never_zero():
    case = load_case("posidonia")
    depths = [1, 5, 10, 15, 20, 25, 28, 29, 29.9, 30, 32, 35, 37, 38, 39, 40, 41, 42, 43, 44, 50, 60]
    nets = [_meadow_entry(case.with_project_depth(z, z))["value"] for z in depths]
    assert all(a > b > 0.0 for a, b in zip(nets, nets[1:]))


# ── Step 8g.7: the site's depth limit, conditioned on the meadow ─────────────

GRID = [(0.5, 0.5), (5.0, 5.0), (15.0, 15.0), (25.0, 25.0), (29.0, 29.0), (30.0, 30.0), (35.0, 35.0),
        (39.0, 39.0), (43.0, 43.0), (30.0, 40.0), (0.0, 44.0), (45.0, 45.0)]


def _site(case):
    return _meadow_entry(case)["production_function"]["parameters"]["depth.site_depth_limit"]


@pytest.mark.parametrize("depth", GRID)
def test_every_depth_is_valued_with_every_agent_positive(depth):
    """The owner's rule: a meadow at 30-44 m (real Catalan meadows live
    there) is valued, every agent > €0 under every dive input, and the
    Monte Carlo runs with no draw at €0."""
    from gaia.uncertainty import run_uncertainty

    at = load_case("posidonia").with_project_depth(*depth)
    for kwargs in (dict(site_intensity="none"), dict(site_share=0.0), dict(area_ha=50.0, site_intensity="none"),
                   {}):
        eco = at.build_ecosystem(**kwargs)
        assert all(a.dependency_weight * a.annual_value(1.0) > 0.0 for a in eco.agents), (depth, kwargs)
    entry = _meadow_entry(at)
    assert net_range(entry["production_function"], 35.0)[0] > 0.0
    assert at.ledger_check() == []
    u = run_uncertainty(at, 10, draws=40, seed=3, tornado=False, normative=False,
                        build_kwargs=dict(area_ha=50.0, site_intensity="none"))
    assert all(block["draws_at_or_below_zero"] == 0 and block["net"]["min"] > 0.0
               for block in u.production.values())
    assert u.summary["pv_externality"]["p5"] > 0.0


@pytest.mark.parametrize("z", [0.5, 5.0, 15.0, 25.0, 27.9, 28.0])
def test_a_shallow_meadow_keeps_the_regional_depth_limit(z):
    """Above 28 m (the range's low end, 30 m, less the 2 m margin) the
    condition rules nothing out: the site's limit is the regional one."""
    site = _site(load_case("posidonia").with_project_depth(z, z))
    assert site["value"] == 40.0 and site["range"] == (30.0, 44.0) and "truncated_below" not in site
    assert site["coupled"] is True


@pytest.mark.parametrize("z", [28.5, 30.0, 35.0, 38.0, 39.0, 40.0])
def test_a_deep_meadow_truncates_the_depth_limit_below_it(z):
    """The documented triangular (30, 40, 44) conditioned on lying deeper
    than the meadow + 2 m: its support starts there, its central value is
    the conditional mode."""
    from gaia.production import central
    from gaia.uncertainty import dist_cdf, dist_quantile

    at = load_case("posidonia").with_project_depth(z, z)
    site = _site(at)
    floor = z + 2.0
    assert site["truncated_below"] == floor and site["range"] == (30.0, 44.0)
    assert central(_meadow_entry(at)["production_function"])["depth.site_depth_limit"] == max(40.0, floor)
    # the exact conditional distribution: P(z_max <= x | z_max > floor)
    f = dist_cdf("triangular", 30.0, 40.0, 44.0, floor)
    for q in (0.0, 0.1, 0.5, 0.9, 1.0):
        x = dist_quantile("triangular", 30.0, 40.0, 44.0, q, floor)
        assert floor <= x <= 44.0
        assert (dist_cdf("triangular", 30.0, 40.0, 44.0, x) - f) / (1.0 - f) == pytest.approx(q, abs=1e-9)


@pytest.mark.parametrize("z", [40.5, 42.0, 43.0, 44.0, 50.0])
def test_beyond_the_deepest_limits_the_depth_limit_is_extended(z):
    """Within two margins of the deepest limit documented (44 m) or below
    it, the site's limit is taken between z + 2 and z + 4 m (triangular,
    mode at z + 2): continuous with the truncated triangle at 40 m."""
    site = _site(load_case("posidonia").with_project_depth(z, z))
    assert site["range"] == (z + 2.0, z + 4.0) and site["value"] == z + 2.0
    assert site["distribution"] == "triangular" and site["status"] == "inferred" and site["coupled"]
    assert "truncated_below" not in site


def test_the_extension_is_continuous_at_its_threshold():
    from gaia.uncertainty import dist_quantile

    at40 = _site(load_case("posidonia").with_project_depth(40.0, 40.0))
    at40e = _site(load_case("posidonia").with_project_depth(40.0 + 1e-9, 40.0 + 1e-9))
    for q in (0.05, 0.5, 0.95):
        a = dist_quantile(at40["distribution"], *at40["range"][:1], at40["value"], at40["range"][1], q,
                          at40["truncated_below"])
        b = dist_quantile("triangular", at40e["range"][0], at40e["value"], at40e["range"][1], q)
        assert a == pytest.approx(b, abs=1e-6)


def test_the_site_limit_and_the_regional_one_are_drawn_together():
    """Comonotone: the site's limit is the regional draw conditioned, so it
    is never shallower than the regional draw, always deeper than the
    meadow + 2 m; above 28 m the two are the same draw."""
    from gaia.uncertainty import _draw_all, production_entries, production_sampled

    rng = random.Random(1)
    for z, same in ((20.0, True), (35.0, False), (43.0, False)):
        at = load_case("posidonia").with_project_depth(z, z)
        sampled = production_sampled(at, production_entries(at))
        names = {s.name.split("].", 1)[1]: s.name for s in sampled if s.name.startswith(f"production[{MEADOW}]")}
        for _ in range(300):
            v = _draw_all(sampled, rng)
            regional, site = v[names["depth.depth_limit"]], v[names["depth.site_depth_limit"]]
            assert site >= z + 2.0 and site >= regional - 1e-12
            if same:
                assert site == pytest.approx(regional, rel=1e-12)


def test_the_regional_production_keeps_the_regional_depth_limit():
    """The €35 netted out is regional: its scale divides by the production at
    15 m with the regional limit, whatever the site's."""
    from gaia.production import central, npp_over

    at = load_case("posidonia").with_project_depth(40.0, 40.0)
    spec = _meadow_entry(at)["production_function"]
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    assert npp_over(spec["depth"], central(spec), "regional") == pytest.approx(
        depth_npp(15.0, p, k, z_max, z_ref), rel=1e-12)
    assert central(spec)["npp_dry_weight"] == pytest.approx(depth_npp(40.0, p, k, z_max, z_ref, 42.0), rel=1e-12)
    assert net_of_scale(spec) == pytest.approx(
        depth_npp(40.0, p, k, z_max, z_ref, 42.0) / depth_npp(15.0, p, k, z_max, z_ref), rel=1e-12)


def test_the_margin_is_sourced_and_fixed():
    raw = next(e for e in load_case("posidonia").document["service_ledger"]
               if "production_function" in e)["production_function"]["depth_production"]["depth_limit_margin"]
    assert raw["value"] == 2.0 and raw["status"] == "inferred" and raw["distribution"] == "fixed"
    assert "doi:10.3354/meps151043" in raw["source"] and "from 3 to 15 m depth" in raw["source"]


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


def test_cli_values_a_deep_meadow(capsys):
    """Step 8g.7: 30, 35 and 40 m (rejected before) are valued."""
    for depth in ("30", "35", "40", "30-40"):
        assert main(["run", "posidonia", "--area-ha", "50", "--dive-intensity", "none", "--depth-m", depth,
                     "--format", "json", "--summary-only"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert all(v > 0.0 for v in out["summary"]["agent_externality_eur_yr"].values())
        block = out["production_functions"][MEADOW]["depth_production"]
        assert block["site_depth_limit"]["support"][0] >= float(depth.split("-")[-1]) + 2.0
    assert main(["run", "posidonia", "--depth-m", "35"]) == 0
    text = capsys.readouterr().out
    assert "the site's depth limit 40 m, 37–44 m in the uncertainty analysis" in " ".join(text.split())


def test_cli_rejects_an_impossible_depth_in_plain_words(capsys):
    for bad in ("deep", "20-10", "1-2-3", "-1"):
        assert main(["run", "posidonia", "--depth-m", bad]) == 2
        assert "--depth-m" in capsys.readouterr().err


def test_help_explains_the_depth_input(capsys):
    assert main(["run", "posidonia", "--help"]) == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "--depth-m" in help_text and "Default: 15 m (the regional mean depth)" in help_text
    assert "Any depth is valued" in help_text and "at least 2 m below the deepest depth given" in help_text


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
        a = rng.uniform(0.0, 50.0)
        b = rng.choice([a, rng.uniform(a, 50.0)])
        at = case.with_project_depth(a, b)
        entries = production_entries(at)
        doc = copy.deepcopy(at.document)
        for e in entries:
            spec = at.service_ledger[e.index]["production_function"]
            for name, p in spec["parameters"].items():
                if p.get("range") and p["distribution"] != "fixed":
                    low, high = p["range"]
                    low = max(low, p.get("truncated_below") or low)
                    _set_at_path(doc, f"$.service_ledger[{e.index}].production_function.{spec['paths'][name]}",
                                 rng.choice([low, high, rng.uniform(low, high)]))
        produced = _rederive_production(doc, entries)
        assert all(net > 0.0 for _, net in produced.values())
        case_from_dict(doc)
        assert not math.isnan(sum(n for _, n in produced.values()))


# ── Step 8g.8: the €35 net_of scales with depth (the owner's answer 1) ───────


@pytest.mark.parametrize("depth", [(5.0, 5.0), (25.0, 25.0), (35.0, 35.0), (43.0, 43.0), (30.0, 40.0)])
def test_the_scaled_net_of_is_the_same_rule_in_the_point_estimate_and_every_draw(depth):
    """At a project depth the €35 subtracted is 35 × NPP(project, the site's
    limit) / NPP(15 m, the regional limit): in the point estimate at the
    central hyperparameters, in every Monte Carlo draw at that draw's (the
    factor moves with the chain, so the net value never reaches €0)."""
    from gaia.uncertainty import (
        _draw_all,
        _rederive_production,
        _with_values,
        production_entries,
        production_sampled,
    )

    at = load_case("posidonia").with_project_depth(*depth)
    entry = _meadow_entry(at)
    spec = entry["production_function"]
    p, k, z_max, z_ref = _hyper(load_case("posidonia"))
    site = central(spec)["depth.site_depth_limit"]
    expected = mean_depth_npp(*depth, p, k, z_max, z_ref, site) / depth_npp(15.0, p, k, z_max, z_ref)
    assert entry["gross"] - entry["value"] == pytest.approx(35.0 * expected, rel=1e-12)
    entries = production_entries(at)
    sampled = production_sampled(at, entries)
    by_name = {s.name: s for s in sampled}
    rng = random.Random(11)
    scales = []
    for _ in range(25):
        doc = _with_values(at.document, _draw_all(sampled, rng), by_name, {})
        produced = _rederive_production(doc, entries)
        drawn = case_from_dict(doc)
        d_entry = _meadow_entry(drawn)
        d_spec = d_entry["production_function"]
        v = central(d_spec)
        scale = mean_depth_npp(*depth, v["depth.npp_at_reference_depth"], v["depth.decline_rate"],
                               v["depth.depth_limit"], z_ref, v["depth.site_depth_limit"]) / depth_npp(
            15.0, v["depth.npp_at_reference_depth"], v["depth.decline_rate"], v["depth.depth_limit"], z_ref)
        assert net_of_scale(d_spec) == pytest.approx(scale, rel=1e-12)
        gross, net = produced[MEADOW]
        assert gross - net == pytest.approx(35.0 * scale, rel=1e-9) and net > 0.0
        scales.append(scale)
    assert max(scales) > min(scales)   # recomputed in each draw, not a fixed factor


def test_the_regional_run_and_the_base_depth_subtract_exactly_35():
    """The owner's answers 1 and 2: scaled from the 15 m base; at 15 m, and
    in the regional run, exactly the booked €35."""
    for case in (load_case("posidonia"), load_case("posidonia").with_project_depth(15.0, 15.0)):
        entry = _meadow_entry(case)
        assert entry["gross"] - entry["value"] == pytest.approx(35.0, rel=1e-12)


# ── Step 8g.9: the epiphytes' production follows depth, the roots' does not ──

EPIPHYTES = "Epiphytes & Algae"


def _epiphyte_entry(case):
    return next(e for e in case.service_ledger if e["agent"] == EPIPHYTES and e["production_function"] is not None)


def test_the_epiphytes_share_the_plants_light_field():
    """Their depth function borrows the plant's decline rate and depth
    limit (identical, so the Monte Carlo draws them once) and is scaled from
    the regional mean depth, where their value is unchanged."""
    case = load_case("posidonia")
    epi = _epiphyte_entry(case)["production_function"]
    meadow = _meadow_entry(case)["production_function"]
    for name in ("depth.decline_rate", "depth.depth_limit"):
        a, b = epi["parameters"][name], meadow["parameters"][name]
        assert (a["value"], a["range"], a["distribution"]) == (b["value"], b["range"], b["distribution"])
        assert a["status"] == "inferred" and a["source"].startswith("Inferred")
    assert "doi:10.1023/A:1003557303904" in epi["parameters"]["depth.decline_rate"]["source"]
    assert epi["depth"]["reference_depth_m"] == 15.0 and epi["depth"]["regional"]["bands"] == [(15.0, 15.0, 1.0)]
    assert _epiphyte_entry(case)["value"] == pytest.approx(82.19699951512872, rel=1e-12)
    assert central(epi)["npp_carbon"] == pytest.approx(22.8209, rel=1e-12)


@pytest.mark.parametrize("depth", GRID + [(50.0, 50.0)])
def test_the_epiphytes_food_scales_with_the_plants_production(depth):
    case = load_case("posidonia")
    at = case.with_project_depth(*depth)
    scale = net_of_scale(_meadow_entry(at)["production_function"])
    epi = _epiphyte_entry(at)
    assert epi["value"] == pytest.approx(82.19699951512872 * scale, rel=1e-9)
    assert epi["value"] > 0.0 and net_range(epi["production_function"])[0] > 0.0
    # the roots do not depend on depth
    roots = {k: v for k, v in central(_meadow_entry(at)["production_function"]).items() if k.startswith("roots.")}
    assert roots == {k: v for k, v in central(_meadow_entry(case)["production_function"]).items()
                     if k.startswith("roots.")}
    eco = at.build_ecosystem(site_intensity="none")
    agent = next(a for a in eco.agents if a.name == EPIPHYTES)
    assert agent.dependency_weight * agent.annual_value(1.0) > 0.0


def test_deeper_epiphytes_are_worth_less_and_never_zero():
    case = load_case("posidonia")
    values = [_epiphyte_entry(case.with_project_depth(z, z))["value"] for z in (1, 5, 15, 25, 30, 35, 40, 43, 50)]
    assert all(a > b > 0.0 for a, b in zip(values, values[1:]))


# ── Step 8g.10: the site's own depth limit (--depth-limit-m) ─────────────────


def test_a_given_site_limit_replaces_the_regional_one():
    """One depth: fixed; the curve keeps P_ref and k and reaches zero there;
    the €35's basis keeps the regional limit; every agent > €0."""
    from gaia.production import deepest_allowed

    case = load_case("posidonia")
    at = case.with_project_depth(10.0, 10.0, depth_limit=(15.0, 15.0))
    spec = _meadow_entry(at)["production_function"]
    site = spec["parameters"]["depth.site_depth_limit"]
    assert (site["value"], site["distribution"], site["status"]) == (15.0, "fixed", "user-supplied")
    assert deepest_allowed(spec) == 15.0
    p, k, z_max, z_ref = _hyper(case)
    npp = depth_npp(10.0, p, k, z_max, z_ref, 15.0)
    assert central(spec)["npp_dry_weight"] == pytest.approx(npp, rel=1e-12)
    assert npp < depth_npp(10.0, p, k, z_max, z_ref)      # a turbid site produces less
    scale = npp / depth_npp(15.0, p, k, z_max, z_ref)
    assert net_of_scale(spec) == pytest.approx(scale, rel=1e-12)
    assert _epiphyte_entry(at)["value"] == pytest.approx(82.19699951512872 * scale, rel=1e-9)
    eco = at.build_ecosystem(area_ha=50.0, site_intensity="none")
    assert all(a.dependency_weight * a.annual_value(1.0) > 0.0 for a in eco.agents)


@pytest.mark.parametrize("limit, depth", [((15.0, 15.0), (14.9, 14.9)), ((8.0, 8.0), (5.0, 5.0)),
                                          ((3.0, 3.0), (0.0, 2.0)), ((13.0, 17.0), (12.0, 12.0)),
                                          ((13.0, 17.0), (16.0, 16.0)), ((44.0, 50.0), (45.0, 45.0)),
                                          ((20.0, 30.0), (5.0, 15.0))])
def test_every_depth_above_a_given_limit_is_valued(limit, depth):
    from gaia.uncertainty import run_uncertainty

    at = load_case("posidonia").with_project_depth(*depth, depth_limit=limit)
    site = _site(at)
    low, high = site.get("range") or (site["value"], site["value"])
    assert depth[1] < low <= high == limit[1]
    if limit[0] < limit[1]:
        # a range is truncated below the meadow (+ the margin, or half-way)
        assert low == max(limit[0], depth[1] + min(2.0, (limit[1] - depth[1]) / 2.0))
        assert site["distribution"] == "uniform" and not site["coupled"]
    for entry in at.service_ledger:
        if entry["production_function"] is not None:
            assert entry["value"] > 0.0
            booked = 35.0 if entry["net_of"] else 0.0
            assert net_range(entry["production_function"], booked)[0] > 0.0
    eco = at.build_ecosystem(site_intensity="none")
    assert all(a.dependency_weight * a.annual_value(1.0) > 0.0 for a in eco.agents)
    u = run_uncertainty(at, 10, draws=30, seed=2, tornado=False, normative=False,
                        build_kwargs=dict(site_intensity="none"))
    assert all(b["draws_at_or_below_zero"] == 0 for b in u.production.values())


@pytest.mark.parametrize("limit, depth", [((15.0, 15.0), (15.0, 15.0)), ((15.0, 15.0), (10.0, 20.0)),
                                          ((13.0, 17.0), (17.0, 17.0)), ((30.0, 30.0), (35.0, 35.0))])
def test_a_depth_at_or_below_the_given_limit_is_rejected(limit, depth):
    with pytest.raises(ValueError, match="at or below the site's depth limit given"):
        load_case("posidonia").with_project_depth(*depth, depth_limit=limit)


@pytest.mark.parametrize("limit", [(0.0, 0.0), (20.0, 10.0), (-5.0, 10.0), (float("nan"), 10.0)])
def test_an_impossible_site_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="site's depth limit must be > 0 m"):
        load_case("posidonia").with_project_depth(5.0, 5.0, depth_limit=limit)


def test_cli_site_depth_limit(capsys):
    argv = ["run", "posidonia", "--area-ha", "50", "--dive-intensity", "none"]
    assert main([*argv, "--depth-limit-m", "15", "--depth-m", "10", "--format", "json", "--summary-only"]) == 0
    out = json.loads(capsys.readouterr().out)
    block = out["production_functions"][MEADOW]["depth_production"]
    assert block["site_depth_limit"]["value"] == 15.0 and block["deepest_allowed_m"] == 15.0
    assert all(v > 0.0 for v in out["summary"]["agent_externality_eur_yr"].values())
    assert main([*argv, "--depth-limit-m", "13-17", "--depth-m", "12"]) == 0
    assert "the site's depth limit 15.5 m, given, 14–17 m in the uncertainty analysis" in " ".join(
        capsys.readouterr().out.split())
    # without --depth-m, the regional mean depth (15 m)
    assert main([*argv, "--depth-limit-m", "20", "--format", "json", "--summary-only"]) == 0
    block = json.loads(capsys.readouterr().out)["production_functions"][MEADOW]["depth_production"]
    assert block["depth_bands"] == [{"from_m": 15.0, "to_m": 15.0, "share": 1.0}]
    assert main([*argv, "--depth-limit-m", "15"]) == 1
    err = capsys.readouterr().err
    assert "at or below the site's depth limit given" in err and "regional mean depth, 15 m" in err
    assert main([*argv, "--depth-limit-m", "30", "--depth-m", "35"]) == 1
    assert "Give a depth shallower than 30 m" in capsys.readouterr().err
    assert main(["run", "posidonia", "--help"]) == 0
    assert "--depth-limit-m" in capsys.readouterr().out
