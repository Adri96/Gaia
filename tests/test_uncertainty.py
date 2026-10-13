"""
Step 8.4 (S7): parameter uncertainty — Monte Carlo, sensitivity ranking and
normative scenarios (gaia.uncertainty), generic over case documents.
"""

import json
import random
import warnings

import pytest

from gaia.cases import load_case
from gaia.cli import main
from gaia.provenance import Confidence, Param
from gaia.uncertainty import (
    DEFAULT_RELATIVE_SPREAD,
    HEADLINES,
    Sampled,
    _set_at_path,
    run_uncertainty,
    sampled_parameters,
    uncertainty_to_dict,
)


@pytest.fixture(scope="module")
def posidonia_mc():
    return run_uncertainty(load_case("posidonia"), 50, draws=200, seed=7)


def test_reproducible_with_a_seed(posidonia_mc):
    again = run_uncertainty(load_case("posidonia"), 50, draws=200, seed=7,
                            tornado=False, normative=False)
    assert again.summary == posidonia_mc.summary
    other = run_uncertainty(load_case("posidonia"), 50, draws=200, seed=8,
                            tornado=False, normative=False)
    assert other.summary != posidonia_mc.summary


def test_percentiles_are_ordered_and_bracket_the_base(posidonia_mc):
    for key, _ in HEADLINES:
        s = posidonia_mc.summary[key]
        assert s["p5"] <= s["p50"] <= s["p95"]
    nsc = posidonia_mc.summary["net_social_cost"]
    assert nsc["p5"] < posidonia_mc.base["net_social_cost"] < nsc["p95"]
    assert posidonia_mc.draws == 200


def test_base_is_the_ordinary_run(posidonia_mc):
    result = load_case("posidonia").run_extraction(50)
    assert posidonia_mc.base["pv_externality"] == result.pv_externality
    assert posidonia_mc.base["net_social_cost"] == result.net_social_cost


def test_what_is_sampled(posidonia_mc):
    names = {s.name for s in posidonia_mc.sampled}
    # documented ranges, carbon first among the drivers
    assert {"carbon.soil_release_fraction", "carbon.soil_carbon_tonnes",
            "carbon.annual_absorption_tonnes", "damage.threshold_logistic_steepness",
            "resource.safe_threshold_ratio"} <= names
    # never: normative, project inputs, irrelevant to extraction, fixed, zeros
    for prefix in ("discount.", "carbon_price.", "restoration.", "succession.",
                   "substrate.", "recovery.", "model."):
        assert not any(n.startswith(prefix) for n in names)
    assert not names & {"resource.unit_value", "resource.area_ha"}
    assert not any(n.endswith("dependency_weight") for n in names)  # fixed in the file
    # every agent carries a ledger value (Step 8c.2), so every one is sampled,
    # the meadow's through the links of its production function (Step 8f.3),
    # the epiphytes' through theirs (Step 8g.2)
    assert {f"agent[{n}].annual_value_per_ha" for n in (
        "Coralligenous & Red Coral",
        "Marine Invertebrates", "Marine Megafauna", "Seabirds")} <= names
    assert "agent[Posidonia Meadow].annual_value_per_ha" not in names
    assert "agent[Epiphytes & Algae].annual_value_per_ha" not in names
    assert "production[Posidonia Meadow].transfer_efficiency" in names
    assert "production[Epiphytes & Algae].depth.npp_at_reference_depth" in names
    release = next(s for s in posidonia_mc.sampled if s.name == "carbon.soil_release_fraction")
    assert (release.low, release.value, release.high, release.documented) == (0.25, 0.63, 1.0, True)
    reasons = posidonia_mc.not_sampled
    assert "discount.rate_schedule[year 0]" in reasons["normative (reported as a sensitivity)"]


# Step 8f.3: the meadow's food value is sampled link by link, so no single
# aggregate between the ends of every link at once leads the ranking
TOP_DRIVER = "carbon.soil_release_fraction"


def test_tornado_ranks_the_top_driver_first(posidonia_mc):
    assert posidonia_mc.tornado[0]["name"] == TOP_DRIVER
    names = [r["name"] for r in posidonia_mc.tornado]
    assert "agent[Posidonia Meadow].annual_value_per_ha" not in names
    # the transfer efficiency is the production function's largest driver
    links = [n for n in names if n.startswith("production[Posidonia Meadow].")]
    assert links[0] == "production[Posidonia Meadow].transfer_efficiency"
    swings = [r["swing"] for r in posidonia_mc.tornado]
    assert swings == sorted(swings, reverse=True)


def test_normative_scenarios(posidonia_mc):
    rows = {r["name"]: r for r in posidonia_mc.normative}
    base = posidonia_mc.base["net_social_cost"]
    assert rows["carbon_price_ets"]["net_social_cost"] < base
    assert rows["carbon_price_scc_1_5pct"]["net_social_cost"] > base
    assert rows["horizon_100"]["net_social_cost"] < base


def test_triangular_quantiles():
    s = Sampled("x", "$.x", value=2.0, low=1.0, high=5.0, kind="triangular",
                documented=True, confidence="low")
    assert s.quantile(0.0) == 1.0 and s.quantile(1.0) == pytest.approx(5.0)
    assert s.quantile(0.25) == pytest.approx(2.0)  # F(mode) = (2-1)/(5-1)
    u = Sampled("x", "$.x", value=2.0, low=1.0, high=5.0, kind="uniform",
                documented=True, confidence="low")
    assert u.quantile(0.5) == 3.0
    rng = random.Random(1)
    assert all(1.0 <= s.draw(rng) <= 5.0 for _ in range(1000))


def test_default_spread_by_confidence_and_clipping():
    params = [
        Param(10.0, "€/ha/yr", "s", Confidence.MEDIUM, name="a"),
        Param(0.6, "fraction", None, Confidence.PLACEHOLDER, name="b"),
        Param(0.2, "ratio", None, Confidence.PLACEHOLDER, name="resource.safe_threshold_ratio"),
        Param(5.0, "x", None, Confidence.PLACEHOLDER, name="c", distribution="fixed"),
        Param(0.0, "x", None, Confidence.LOW, name="d"),
        Param(0.02, "1/yr", "s", Confidence.MEDIUM, name="discount.scarcity_rate"),
    ]
    paths = {p.name: f"$.{p.name}" for p in params}
    got = {s.name: s for s in sampled_parameters(params, paths)}
    assert set(got) == {"a", "b", "resource.safe_threshold_ratio"}
    f_low, f_high = DEFAULT_RELATIVE_SPREAD[Confidence.MEDIUM]
    assert (got["a"].low, got["a"].high) == (10.0 * f_low, 10.0 * f_high)
    assert got["b"].high == 1.0  # a fraction stays <= 1
    assert 0.0 < got["resource.safe_threshold_ratio"].low


def test_set_at_path():
    doc = {"a": [{"x": 1.0}, {"x": {"value": 2.0, "unit": "u"}}], "b": 3.0}
    _set_at_path(doc, "$.a[0].x", 9.0)
    _set_at_path(doc, "$.a[1].x", 8.0)
    _set_at_path(doc, "$.b", 7.0)
    assert doc == {"a": [{"x": 9.0}, {"x": {"value": 8.0, "unit": "u"}}], "b": 7.0}
    with pytest.raises(ValueError):
        _set_at_path(doc, "a.b", 1.0)


def test_generic_on_a_case_without_ranges():
    """Forest documents no ranges: confidence sets them, and the sampled
    weights are renormalised so every draw validates."""
    u = run_uncertainty(load_case("forest"), 300, build_kwargs={"total_units": 1000},
                        draws=30, seed=3, tornado=False, normative=False)
    assert any(s.name.endswith("dependency_weight") for s in u.sampled)
    assert all(not s.documented for s in u.sampled)
    assert u.summary["pv_externality"]["p5"] < u.summary["pv_externality"]["p95"]


def test_json_block(posidonia_mc):
    d = uncertainty_to_dict(posidonia_mc)
    assert d["draws"] == 200 and d["seed"] == 7
    assert set(d["headlines"]["net_social_cost"]) == {"unit", "base", "p5", "p50", "p95", "mean"}
    assert d["tornado_net_social_cost"][0]["name"] == TOP_DRIVER
    assert uncertainty_to_dict(None) is None
    json.dumps(d, allow_nan=False)


def test_cli_text_and_json(capsys):
    assert main(["run", "posidonia", "--uncertainty", "20", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "Uncertainty (Monte Carlo" in out and "20 draws, seed 1" in out
    assert out.index("Uncertainty (Monte Carlo") < out.index("MARINE EXTERNALITY NOTE")
    assert main(["run", "posidonia", "--uncertainty", "20", "--format", "json",
                 "--summary-only"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["uncertainty"]["draws"] == 20
    assert main(["run", "posidonia", "--format", "json", "--summary-only"]) == 0
    assert "uncertainty" not in json.loads(capsys.readouterr().out)


def test_cli_restore_and_pricing(capsys):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert main(["run", "posidonia", "--mode", "restore", "--units", "10",
                     "--uncertainty", "5"]) == 0
    assert any("extraction only" in str(x.message) for x in w)
    capsys.readouterr()
    assert main(["run", "posidonia", "--with-pricing", "--units", "10",
                 "--uncertainty", "5"]) == 1
    assert "--with-pricing" in capsys.readouterr().err


def test_cli_threshold_override_is_held_fixed():
    """A user-supplied threshold is an input of the question, not sampled."""
    from gaia.cli import _uncertainty, build_case_parser

    case = load_case("posidonia")
    args = build_case_parser(case, "gaia run posidonia").parse_args(
        ["--threshold", "0.25", "--uncertainty", "5"])
    u = _uncertainty(case, args, None)
    assert "resource.safe_threshold_ratio" not in {s.name for s in u.sampled}


@pytest.mark.parametrize("change,message", [
    ({"range": [0.7, 1.0]}, "outside its range"),
    ({"range": [0.25, 1.0], "relative_range": [0.5, 2.0]}, "either range or relative_range"),
    ({"relative_range": [1.5, 2.0]}, "must contain 1"),
    ({"range": [0.25]}, r"expected \[low, high\]"),
    ({"distribution": "normal"}, "distribution must be one of"),
])
def test_parameter_ranges_are_validated_on_load(change, message):
    import copy

    from gaia.cases import case_data_path
    from gaia.ecosystem_io import case_from_dict, read_json

    doc = copy.deepcopy(read_json(case_data_path("posidonia")))
    release = doc["carbon"]["soil_release_fraction"]
    release.pop("range", None)
    release.update(change)
    with pytest.raises(ValueError, match=message):
        case_from_dict(doc)


def test_ranges_round_trip_through_a_saved_ecosystem():
    from gaia.ecosystem_io import ecosystem_from_dict, ecosystem_to_dict

    eco = load_case("posidonia").build_ecosystem()
    d = ecosystem_to_dict(eco)
    assert d["carbon"]["soil_release_fraction"]["range"] == [0.25, 1.0]
    assert d["provenance_defaults"]["edge[*].strength"]["relative_range"] == [0.5, 1.5]
    assert d["provenance_defaults"]["agent[*].dependency_weight"]["distribution"] == "fixed"
    again = {p.name: p for p in ecosystem_from_dict(d).provenance}
    for p in eco.provenance:
        assert again[p.name].bounds == p.bounds and again[p.name].distribution == p.distribution


# ── Step 8e.4: every shipped case's Monte Carlo accepts its draws ────────────

@pytest.mark.parametrize("name", ["forest", "costa_brava", "posidonia", "amazon_forest"])
def test_monte_carlo_accepts_draws_for_every_case(name):
    """Every shipped case gives valid P5/P50/P95: its draws pass
    validation (costa_brava and amazon_forest rejected every draw before
    Step 8e.4, their edges sitting at the in-degree cap), and no drawn
    value is rescaled to the cap."""
    from gaia.ecosystem_io import case_from_dict
    from gaia.uncertainty import _with_values

    case = load_case(name)
    params = case.build_ecosystem().provenance
    sampled = sampled_parameters(params, case.param_paths)
    by_name = {s.name: s for s in sampled}
    weights = {n: p for n, p in case.param_paths.items() if n.endswith(".dependency_weight")}
    weights = weights if any(n in by_name for n in weights) else {}
    rng = random.Random(20261012)
    rejected = 0
    for _ in range(300):
        values = {s.name: s.draw(rng) for s in sampled}
        try:
            built = case_from_dict(_with_values(case.document, values, by_name, weights)).build_ecosystem()
        except ValueError:
            rejected += 1
            continue
        for s in sampled:  # the drawn value is the value used (no rescaling)
            if s.name.startswith("edge["):
                source, target = s.name[5:-len("].strength")].split(" → ")
                edge = next(e for e in built.interactions if e.source == source and e.target == target)
                assert edge.strength == pytest.approx(values[s.name], rel=1e-12)
    # Posidonia keeps its documented x0.5-x1.5 edges, which can breach the
    # cap for its most connected agent; the others never do
    assert rejected <= (30 if name == "posidonia" else 0)
    units = case.default_units if name != "amazon_forest" else 800
    kwargs = {"total_units": 4000} if name == "amazon_forest" else {}
    res = run_uncertainty(case, units, build_kwargs=kwargs, draws=12, tornado=False, normative=False)
    assert res.draws == 12
    for key, _ in HEADLINES:
        s = res.summary[key]
        assert s["p5"] <= s["p50"] <= s["p95"]
    assert res.summary["pv_externality"]["p95"] > res.summary["pv_externality"]["p5"] > 0


@pytest.mark.parametrize("name", ["costa_brava", "amazon_forest"])
def test_edges_into_capped_agents_rise_only_to_the_cap(name):
    """Step 8e.4: an edge's documented upper factor keeps the worst-case
    in-degree of its target within the cap (x0.5 to x1.5 otherwise)."""
    from gaia.validation import worst_case_incoming_strengths

    case = load_case(name)
    eco = case.build_ecosystem()
    worst = worst_case_incoming_strengths(eco.agents, eco.interactions)
    sampled = {s.name: s for s in sampled_parameters(eco.provenance, case.param_paths)}
    for e in eco.interactions:
        s = sampled[f"edge[{e.source} → {e.target}].strength"]
        assert s.low == pytest.approx(0.5 * e.strength)
        assert s.high <= 1.5 * e.strength + 1e-12
        assert worst[e.target] * s.high / e.strength <= 1.0 + 1e-9
    for p in eco.provenance:
        if p.name.endswith(".keystone_threshold"):
            assert p.distribution == "uniform" and p.bounds == pytest.approx((p.value - 0.15, p.value + 0.15))
