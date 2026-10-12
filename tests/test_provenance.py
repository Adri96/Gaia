"""
Tests for parameter provenance and the calibration status of every output
(Step 5, findings D2/S3): a reader who sees only an output file can tell
which numbers are placeholders.
"""

import contextlib
import io
import json
import math

import pytest

from gaia.cases import amazon_forest, costa_brava, forest, load_case, posidonia
from gaia.models import Agent, Ecosystem, Resource, RestorationCost
from gaia.damage import logistic_damage
from gaia.provenance import (
    Confidence,
    Param,
    calibration_status,
    group_flagged,
    named,
    unwrap,
    user_or_default,
)
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.serialization import to_json
from gaia.simulation import run_extraction, run_restoration

BUILDERS = {
    "forest": (forest.build_forest_ecosystem, "total_trees", 2000),
    "costa_brava": (costa_brava.build_costa_brava_ecosystem, "total_trees", 2000),
    "posidonia": (posidonia.build_posidonia_ecosystem, "total_hectares", 1000),
    "amazon_forest": (amazon_forest.build_amazon_ecosystem, "total_trees", 4000),
}
def _build(case, **kwargs):
    builder, size_arg, size = BUILDERS[case]
    return builder(**{size_arg: size}, **kwargs)


def _run_cli(case, argv):
    """``gaia run <case>``, the 0.9 size flags mapped to --total-units."""
    from gaia.cli import case_main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        case_main(load_case(case), ["--total-units" if a in ("--trees", "--hectares") else a for a in argv])
    return buf.getvalue()


# ── Param ─────────────────────────────────────────────────────────────────────


def test_param_converts_confidence_and_value():
    p = Param(3, "€/ha/yr", "a source", "medium")
    assert p.confidence is Confidence.MEDIUM
    assert isinstance(p.value, float) and p.value == 3.0


@pytest.mark.parametrize("value", [math.nan, math.inf, "1", True])
def test_param_rejects_non_finite_or_non_numeric(value):
    with pytest.raises(ValueError):
        Param(value, "x", None, Confidence.PLACEHOLDER)


@pytest.mark.parametrize("confidence", [Confidence.HIGH, Confidence.MEDIUM])
def test_high_and_medium_need_a_source(confidence):
    with pytest.raises(ValueError, match="needs a source"):
        Param(1.0, "x", None, confidence)


def test_unknown_confidence_rejected():
    with pytest.raises(ValueError):
        Param(1.0, "x", None, "certain")


def test_named_and_unwrap():
    params = {"a": Param(1.0, "x", None, Confidence.LOW), "b": Param(2.0, "y", None, Confidence.LOW)}
    assert unwrap(params) == {"a": 1.0, "b": 2.0}
    assert [p.name for p in named("carbon", params)] == ["carbon.a", "carbon.b"]


def test_user_or_default():
    default = Param(100.0, "€/tree", None, Confidence.PLACEHOLDER, name="resource.unit_value")
    assert user_or_default(default, 100, "--unit-value") is default
    user = user_or_default(default, 120.0, "--unit-value")
    assert user.confidence is Confidence.USER
    assert user.value == 120.0 and user.name == "resource.unit_value"
    assert "--unit-value" in user.source


# ── Case provenance matches the model ─────────────────────────────────────────


def _model_value(eco, name):
    """The model's value for a provenance name (None if not resolvable)."""
    resource = eco.resource
    head, _, field = name.partition(".")
    if head == "resource":
        return getattr(resource, field)
    if head == "carbon":
        return getattr(resource.carbon_profile, field)
    if head == "substrate":
        return getattr(resource.substrate, field)
    if head == "discount":
        if field.startswith("rate_schedule[year "):
            year = int(field[len("rate_schedule[year "):-1])
            return dict(resource.discount.rate_schedule)[year]
        return getattr(resource.discount, field)
    if head == "agents":
        values = {getattr(a, field) for a in eco.agents}
        assert len(values) == 1, f"{name}: agents differ"
        return values.pop()
    if head.startswith("agent["):
        agent_name, attr = name[len("agent["):].split("].")
        return getattr(next(a for a in eco.agents if a.name == agent_name), attr)
    if head.startswith("edge["):
        src, tgt = name[len("edge["):name.index("]")].split(" → ")
        return next(
            e.strength for e in eco.interactions if e.source == src and e.target == tgt
        )
    return None


@pytest.mark.parametrize("with_pricing", [False, True])
@pytest.mark.parametrize("case", list(BUILDERS))
def test_every_recorded_value_is_the_value_the_model_uses(case, with_pricing):
    eco = _build(case, with_pricing=with_pricing)
    names = [p.name for p in eco.provenance]
    assert all(names), "every Param must be named"
    assert len(names) == len(set(names)), "duplicate provenance names"
    checked = 0
    for p in eco.provenance:
        model = _model_value(eco, p.name)
        if model is None:
            continue
        assert float(model) == p.value, p.name
        checked += 1
    # every agent value, weight and edge is covered
    assert checked >= 2 * len(eco.agents) + len(eco.interactions)
    assert {f"edge[{e.source} → {e.target}].strength" for e in eco.interactions} <= set(names)
    assert {f"agent[{a.name}].dependency_weight" for a in eco.agents} <= set(names)


@pytest.mark.parametrize("case", list(BUILDERS))
def test_case_records_the_parameter_families(case):
    names = {p.name.split(".")[0].split("[")[0] for p in _build(case).provenance}
    assert {"resource", "agent", "edge", "carbon", "substrate", "discount", "damage"} <= names


@pytest.mark.parametrize("case", list(BUILDERS))
def test_pricing_anchors_recorded_only_with_pricing(case):
    without = {p.name for p in _build(case).provenance}
    assert not any(n.startswith("pricing.") for n in without)
    eco = _build(case, with_pricing=True)
    anchors = [p for p in eco.provenance if p.name.startswith("pricing.anchor[")]
    assert len(anchors) == len(eco.agents)
    # derived (Step 4) anchors are placeholders; none claims more than low
    assert all(p.confidence in (Confidence.LOW, Confidence.PLACEHOLDER) for p in anchors)
    assert any(p.confidence is Confidence.PLACEHOLDER for p in anchors)


def test_known_flags_are_honest():
    """Items the audit singled out are flagged, with the reason in the note."""
    def param(case, name, **kw):
        return next(p for p in _build(case, **kw).provenance if p.name == name)

    for case in ("forest", "costa_brava"):
        p = param(case, "agents.annual_value_per_ha")
        assert p.confidence is Confidence.LOW and "memory" in p.note
    scarcity = param("forest", "discount.scarcity_rate")
    assert scarcity.value == 0.02 and scarcity.confidence is Confidence.LOW
    assert "Drupp" in scarcity.note
    absorption = param("posidonia", "carbon.annual_absorption_tonnes")
    assert "doi:10.1002/lno.10510" in absorption.source and "S5" in absorption.note
    release = param("posidonia", "carbon.soil_release_fraction")
    assert release.confidence is Confidence.LOW and "project input" in release.note
    assert "0.96" in release.note  # excavation (IPCC 2013), Step 8c.5
    assert param("amazon_forest", "resource.safe_threshold_ratio").confidence is Confidence.LOW
    assert "scale" in param("amazon_forest", "resource.safe_threshold_ratio").note
    for case in BUILDERS:
        assert param(case, "damage.logistic_steepness").confidence is Confidence.PLACEHOLDER
    retuned = [
        p for case in ("costa_brava", "amazon_forest") for p in _build(case).provenance
        if "in-degree cap" in p.note
    ]
    assert len(retuned) == 3 + 12
    assert all(p.confidence is Confidence.PLACEHOLDER for p in retuned)


def test_scc_year0_is_flagged():
    status = run_extraction(_build("forest"), 100).calibration
    scc = next(p for p in status.params if p.name == "carbon_price.year0")
    assert scc.value == pytest.approx(166.35, abs=0.01)
    assert "2020" in scc.note and "$215" in scc.note


# ── Calibration status ────────────────────────────────────────────────────────


def test_status_counts_and_headline():
    status = run_extraction(_build("costa_brava"), 500).calibration
    assert status.n_params == len(status.params)
    assert status.n_placeholder + status.n_low == len(status.flagged)
    assert status.calibration_regime == "B"
    assert status.status == "illustrative"
    assert status.headline.startswith(
        f"ILLUSTRATIVE: {status.n_placeholder + status.n_low} of {status.n_params} "
        f"recorded parameters are placeholders ({status.n_placeholder}) or "
        f"low-confidence ({status.n_low})"
    )
    assert "not real-world estimates" in status.headline


def test_group_flagged_covers_every_flagged_param():
    status = run_extraction(_build("amazon_forest"), 800).calibration
    grouped = [p for _, params in group_flagged(status) for p in params]
    assert sorted(p.name for p in grouped) == sorted(p.name for p in status.flagged)


def test_ecosystem_without_provenance():
    resource = Resource(name="R", total_units=100, safe_threshold_ratio=0.3,
                        unit_value=1.0, area_ha=1.0)
    agent = Agent(name="A", dependency_weight=1.0,
                  damage_function=logistic_damage(threshold=0.3),
                  annual_value_per_ha=10.0, description="d")
    eco = Ecosystem(name="E", resource=resource, agents=[agent])
    status = run_extraction(eco, 50).calibration
    assert not status.ecosystem_documented
    assert status.status == "illustrative"
    assert "records no parameter provenance" in status.headline
    text = format_report(run_extraction(eco, 50))
    assert text.splitlines()[1].startswith("  ILLUSTRATIVE")


def test_ets_view_and_user_values_are_reported():
    out = _run_cli("forest", ["--trees", "1000", "--units", "500", "--unit-value", "150",
                              "--carbon-price", "ets", "--format", "json", "--summary-only"])
    cal = json.loads(out)["calibration"]
    params = {p["name"]: p for p in cal["parameters"]}
    assert params["resource.unit_value"]["confidence"] == "user-supplied"
    assert params["resource.unit_value"]["value"] == 150.0
    assert params["carbon_price.year0"]["value"] == 80.0
    assert params["carbon_price.year0"]["confidence"] == "low"
    assert cal["n_user_supplied"] == 1
    assert "1 user-supplied" in cal["statement"]


def test_area_given_is_user_supplied():
    eco = forest.build_forest_ecosystem(total_trees=1000, area_ha=10.0)
    area = next(p for p in eco.provenance if p.name == "resource.area_ha")
    assert area.confidence is Confidence.USER
    derived = forest.build_forest_ecosystem(total_trees=1000)
    area = next(p for p in derived.provenance if p.name == "resource.area_ha")
    assert area.confidence is Confidence.PLACEHOLDER and area.value == 4.0


# ── Every output carries it ───────────────────────────────────────────────────


@pytest.mark.parametrize("mode_args", [
    [], ["--mode", "restore"], ["--mode", "restore", "--time-horizon", "30"],
])
@pytest.mark.parametrize("case", list(BUILDERS))
def test_text_report_starts_with_banner_and_ends_with_provenance(case, mode_args):
    size_flag = "--hectares" if case == "posidonia" else "--trees"
    _, _, size = BUILDERS[case]
    text = _run_cli(case, [size_flag, str(size), "--units", str(size // 5), *mode_args])
    lines = text.splitlines()
    assert lines[0].startswith("=")
    assert lines[1].startswith("  ILLUSTRATIVE: ")
    assert "Results are not real-world estimates." in " ".join(" ".join(lines[1:6]).split())
    assert "Parameter Provenance" in text
    section = text[text.index("Parameter Provenance"):]
    assert "Calibration regime: B" in section
    assert "[placeholder]" in section


@pytest.mark.parametrize("summary_only", [True, False])
@pytest.mark.parametrize("mode_args", [[], ["--mode", "restore", "--time-horizon", "30"]])
@pytest.mark.parametrize("case", list(BUILDERS))
def test_json_calibration_block(case, mode_args, summary_only):
    size_flag = "--hectares" if case == "posidonia" else "--trees"
    _, _, size = BUILDERS[case]
    argv = [size_flag, str(size), "--units", str(size // 5), *mode_args, "--format", "json"]
    if summary_only:
        argv.append("--summary-only")
    d = json.loads(_run_cli(case, argv))
    assert list(d)[:3] == ["gaia_version", "mode", "calibration"]
    cal = d["calibration"]
    assert cal["status"] == "illustrative"
    assert cal["calibration_regime"] == "B"
    assert cal["n_params"] == len(cal["parameters"])
    counts = {c.value: 0 for c in Confidence}
    for p in cal["parameters"]:
        assert {"name", "value", "unit", "source", "confidence", "note"} <= set(p)
        assert set(p) <= {"name", "value", "unit", "source", "confidence", "note",
                          "range", "distribution"}  # range: Step 8.4, when documented
        if "range" in p:
            assert p["range"][0] <= p["value"] <= p["range"][1]
        counts[p["confidence"]] += 1
    assert counts["placeholder"] == cal["n_placeholder"] > 0
    assert counts["low"] == cal["n_low"]
    assert counts["medium"] == cal["n_medium"]
    names = {p["name"] for p in cal["parameters"]}
    restore = bool(mode_args)
    assert ("restoration.planting_cost_per_unit" in names) == restore
    assert ("succession.climax_approach_year" in names) == restore


def test_restoration_without_maturation_has_no_succession_params():
    out = _run_cli("forest", ["--trees", "1000", "--units", "200", "--mode", "restore",
                              "--format", "json", "--summary-only"])
    names = {p["name"] for p in json.loads(out)["calibration"]["parameters"]}
    assert "restoration.planting_cost_per_unit" in names
    assert not any(n.startswith("succession.") for n in names)


def test_library_restoration_and_to_json_carry_calibration():
    eco = _build("forest")
    cost = RestorationCost(50.0, 10.0, 10)
    fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    result = run_restoration(eco, 200, cost, fns)
    assert result.calibration is not None
    assert format_restoration_report(result).splitlines()[1].startswith("  ILLUSTRATIVE")
    assert "calibration" in json.loads(to_json(result, include_steps=False))
    assert forest.run_forest(total_trees=1000, trees_cut=100).splitlines()[1].startswith(
        "  ILLUSTRATIVE")


def test_calibration_status_direct():
    eco = _build("posidonia")
    status = calibration_status(eco, eco.resource.discount)
    assert status.ecosystem_documented
    assert status.params[-len(eco.provenance):] == tuple(eco.provenance)
