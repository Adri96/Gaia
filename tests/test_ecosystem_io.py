"""
Tests for the ecosystem file format (gaia.ecosystem_io, Step 7.1, E7):
round trips, provenance mapping, and validation errors that name the JSON
path.
"""

import copy
import dataclasses
import json
import math

import pytest

from gaia.cases.amazon_forest import build_amazon_ecosystem
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.forest import build_forest_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem
from gaia.damage import logistic_damage
from gaia.ecosystem_io import (
    SCHEMA_VERSION,
    case_from_dict,
    ecosystem_from_dict,
    ecosystem_to_dict,
    load_ecosystem,
    read_json,
    save_ecosystem,
)
from gaia.models import RestorationCost
from gaia.provenance import calibration_status
from gaia.recovery import logistic_recovery
from gaia.serialization import to_json
from gaia.simulation import run_extraction, run_restoration

BUILDS = {
    "forest": lambda **kw: build_forest_ecosystem(total_trees=1000, **kw),
    "costa_brava": lambda **kw: build_costa_brava_ecosystem(total_trees=1000, **kw),
    "posidonia": lambda **kw: build_posidonia_ecosystem(total_hectares=1000, **kw),
    "amazon_forest": lambda **kw: build_amazon_ecosystem(total_trees=4000, **kw),
}

MINIMAL = {
    "gaia_schema": 1,
    "name": "Two-agent wood",
    "resource": {
        "unit": "trees",
        "total_units": 1000,
        "units_per_ha": 250,
        "unit_value": {"value": 80, "unit": "€/tree", "confidence": "placeholder"},
        "safe_threshold_ratio": 0.3,
    },
    "agent_defaults": {"annual_value_per_ha": 1000, "damage": "logistic"},
    "damage_curves": {"logistic": {"type": "logistic", "steepness": 12}},
    "agents": [
        {"name": "Water", "dependency_weight": 0.6},
        {"name": "Birds", "dependency_weight": 0.4, "trophic_level": 1},
    ],
}


def norm(obj):
    """Dataclass tree as comparable data: functions by kernel, numbers typed."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: norm(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if callable(obj):
        return ("fn", tuple(obj.kernel), obj.threshold)
    if isinstance(obj, dict):
        return {k: norm(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [norm(v) for v in obj]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return (type(obj).__name__, obj)
    return obj


def doc(**changes):
    d = copy.deepcopy(MINIMAL)
    d.update(changes)
    return d


# ── Round trips ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", list(BUILDS))
@pytest.mark.parametrize("with_pricing", [False, True])
def test_ecosystem_dict_ecosystem_is_identical(case, with_pricing):
    eco = BUILDS[case](with_pricing=with_pricing)
    again = ecosystem_from_dict(ecosystem_to_dict(eco))
    assert norm(again) == norm(eco)


@pytest.mark.parametrize("case", list(BUILDS))
def test_dict_ecosystem_dict_is_identical(case):
    d = ecosystem_to_dict(BUILDS[case](with_pricing=True))
    assert ecosystem_to_dict(ecosystem_from_dict(d)) == d
    assert json.loads(json.dumps(d)) == d  # plain JSON data


@pytest.mark.parametrize("case", list(BUILDS))
def test_round_trip_gives_identical_results(case):
    eco = BUILDS[case]()
    again = ecosystem_from_dict(ecosystem_to_dict(eco))
    units = eco.resource.total_units // 4
    assert to_json(run_extraction(again, units)) == to_json(run_extraction(eco, units))
    cost = RestorationCost(10.0, 1.0, 5)

    def restore(e):
        rec = [logistic_recovery(e.resource.safe_threshold_ratio) for _ in e.agents]
        return to_json(run_restoration(e, units, cost, rec), include_steps=False)

    assert restore(again) == restore(eco)


def test_user_supplied_values_survive_the_round_trip():
    eco = build_forest_ecosystem(total_trees=1000, tree_value=55.0, area_ha=7.0)
    again = ecosystem_from_dict(ecosystem_to_dict(eco))
    assert norm(again.provenance) == norm(eco.provenance)
    names = {p.name: p for p in again.provenance}
    assert names["resource.unit_value"].confidence.value == "user-supplied"
    assert names["resource.area_ha"].confidence.value == "user-supplied"


def test_save_and_load(tmp_path):
    eco = build_costa_brava_ecosystem(total_trees=500)
    path = tmp_path / "costa.json"
    save_ecosystem(eco, path)
    text = path.read_text(encoding="utf-8")
    assert "€/ha/yr" in text  # UTF-8 kept readable
    assert norm(load_ecosystem(path)) == norm(eco)


def test_canonical_form_shares_curves_and_provenance():
    d = ecosystem_to_dict(build_costa_brava_ecosystem(total_trees=1000))
    assert d["gaia_schema"] == SCHEMA_VERSION
    assert set(d["damage_curves"]) == {"threshold_logistic", "threshold_exponential"}  # Step 8d.1
    assert d["agent_defaults"]["damage"] == "threshold_logistic"
    fire = next(a for a in d["agents"] if a["name"].startswith("Fire"))
    assert fire["damage"] == "threshold_exponential"
    assert "agent[*].dependency_weight" in d["provenance_defaults"]
    retuned = [e for e in d["interactions"]
               if isinstance(e["strength"], dict) and "Step 3.8" in e["strength"]["note"]]
    assert len(retuned) == 3  # the in-degree-cap edges keep their own note
    # Step 8e.4: edges near the cap carry their own Monte Carlo range
    ranged = [e for e in d["interactions"] if isinstance(e["strength"], dict)]
    assert len(ranged) == 7 and all("relative_range" in e["strength"] for e in ranged)
    assert all("divided by 1.35" in e["strength"]["note"] for e in retuned)


def test_to_dict_rejects_a_custom_damage_function():
    eco = build_forest_ecosystem(total_trees=100)
    eco.agents[0].damage_function = lambda d: d
    with pytest.raises(ValueError, match="not from gaia.damage"):
        ecosystem_to_dict(eco)


def test_to_dict_rejects_provenance_without_a_place():
    eco = build_forest_ecosystem(total_trees=100)
    eco.provenance.append(dataclasses.replace(eco.provenance[0], name="restoration.planting_cost_per_unit"))
    with pytest.raises(ValueError, match="no place"):
        ecosystem_to_dict(eco)


# ── Documents ─────────────────────────────────────────────────────────────────


def test_minimal_document_runs():
    eco = ecosystem_from_dict(MINIMAL)
    assert eco.resource.name == "Two-agent wood"
    assert eco.resource.area_ha == 4.0
    assert [a.annual_value_per_ha for a in eco.agents] == [1000.0, 1000.0]
    # only the inline Param is recorded; the derived area has no density Param
    assert [p.name for p in eco.provenance] == ["resource.unit_value"]
    result = run_extraction(eco, 300)
    assert result.annual_externality > 0


def test_bare_numbers_record_nothing():
    d = doc()
    d["resource"]["unit_value"] = 80
    eco = ecosystem_from_dict(d)
    assert eco.provenance == []
    status = calibration_status(eco, eco.resource.discount)
    assert not status.ecosystem_documented


def test_provenance_names_and_order():
    d = doc(
        provenance_defaults={
            "agent[*].dependency_weight": {"unit": "share", "confidence": "low", "source": "a survey"},
            "edge[*].strength": {"unit": "fraction", "confidence": "placeholder"},
        },
        interactions=[{"source": "Water", "target": "Birds",
                       "strength": {"value": 0.2, "unit": "fraction", "confidence": "low",
                                    "source": "x", "note": "own"}}],
        calibration_regime="B",
    )
    d["damage_curves"]["logistic"]["steepness"] = {"value": 12, "unit": "-", "confidence": "placeholder"}
    d["agents"][1]["damage"] = {"type": "piecewise", "pre_slope_ratio": {"value": 0.1, "unit": "-", "confidence": "placeholder"}}
    eco = ecosystem_from_dict(d)
    assert [p.name for p in eco.provenance] == [
        "resource.unit_value",
        "agent[Water].dependency_weight",
        "agent[Birds].dependency_weight",
        "damage.logistic_steepness",
        "agent[Birds].damage.pre_slope_ratio",
        "edge[Water → Birds].strength",
    ]
    assert eco.provenance[1].source == "a survey"
    assert eco.provenance[-1].note == "own"  # inline wins over the template


def test_threshold_override_moves_curves_without_their_own():
    d = doc()
    d["agents"][1]["damage"] = {"type": "logistic", "threshold": 0.5}
    case = case_from_dict(d)
    eco = case.build_ecosystem(safe_threshold_ratio=0.4)
    assert eco.agents[0].damage_function.threshold == 0.4
    assert eco.agents[1].damage_function.threshold == 0.5


def test_overrides_are_user_supplied():
    case = case_from_dict(MINIMAL)
    eco = case.build_ecosystem(unit_value=99.0, labels={"unit_value": "--price"})
    (param,) = eco.provenance
    assert param.confidence.value == "user-supplied"
    assert param.source == "user-supplied (--price)"
    assert case.build_ecosystem(unit_value=80.0).provenance[0].confidence.value == "placeholder"


def test_hectare_unit_area_follows_units():
    d = doc()
    d["resource"] = {"unit": "ha", "total_units": 50, "unit_value": 10,
                     "area_ha": {"value": 50, "unit": "ha", "confidence": "low", "source": "map"},
                     "safe_threshold_ratio": 0.2}
    case = case_from_dict(d)
    eco = case.build_ecosystem(total_units=20)
    assert eco.resource.area_ha == 20.0
    assert eco.provenance[0].source == "user-supplied (--total-units / total_units)"
    with pytest.raises(ValueError, match="must equal the number of units"):
        case.build_ecosystem(total_units=20, area_ha=30.0)


def test_discount_profile_and_schedule():
    d = doc(discount={"profile": "green_book", "horizon_years": 80})
    eco = ecosystem_from_dict(d)
    assert eco.resource.discount.rate_schedule == [(0, 0.035), (31, 0.030), (76, 0.025)]
    assert eco.resource.discount.horizon_years == 80
    d = doc(discount={"rate_schedule": [{"from_year": 0, "rate": 0.03}, {"from_year": 50, "rate": 0.02}],
                      "scarcity_rate": 0.01})
    eco = ecosystem_from_dict(d)
    assert eco.resource.discount.rate_schedule == [(0, 0.03), (50, 0.02)]


def test_pricing_is_attached_only_when_enabled():
    d = doc(pricing={"reference_area_ha": 2.0, "anchors": [
        {"agent_name": "Water", "anchor_value": 500, "source": "s", "confidence": "low"}]})
    assert ecosystem_from_dict(d).pricing is None
    eco = ecosystem_from_dict(d, with_pricing=True)
    anchors = {a.agent_name: a.anchor_value for a in eco.pricing.anchors}
    assert anchors["Water"] == 1000.0  # scaled from 2 ha to 4 ha
    assert anchors["Birds"] == 4000.0  # anchored at its own direct value
    assert eco.provenance[-1].name == "pricing.default_scarcity.max_multiplier"


# ── Validation errors ─────────────────────────────────────────────────────────


def _bad(**changes):
    return doc(**changes)


def _with(path_fn):
    d = copy.deepcopy(MINIMAL)
    path_fn(d)
    return d


@pytest.mark.parametrize("data,message", [
    ("not an object", r"^\$: expected an object"),
    (_bad(colour="green"), r"^\$: unknown key 'colour'"),
    ({k: v for k, v in MINIMAL.items() if k != "agents"}, r"^\$\.agents: required"),
    (_bad(gaia_schema=2), r"unsupported schema version 2"),
    (_bad(gaia_schema="1"), r"\$\.gaia_schema: expected an integer"),
    (_bad(calibration_regime="C"), r"\$\.calibration_regime"),
    (_bad(agents=[]), r"\$\.agents: at least one agent"),
    (_with(lambda d: d["agents"][1].update(weight=1)), r"\$\.agents\[1\]: unknown key 'weight'"),
    (_with(lambda d: d["agents"][1].update(name="Water")), r"\$\.agents\[1\]\.name: duplicate agent"),
    (_with(lambda d: d["agents"][0].update(damage="logistc")),
     r"\$\.agents\[0\]\.damage: unknown damage curve 'logistc' \(defined: logistic\)"),
    (_with(lambda d: d["agents"][0].update(dependency_weight=True)),
     r"\$\.agents\[0\]\.dependency_weight: expected a number, got a boolean"),
    (_with(lambda d: d["agents"][0].update(trophic_level=1.5)), r"\$\.agents\[0\]\.trophic_level: expected an integer"),
    (_with(lambda d: d["resource"].update(area_ha=4)), r"\$\.resource: give exactly one of area_ha and units_per_ha"),
    (_with(lambda d: d["resource"].update(units_per_ha=0)), r"\$\.resource\.units_per_ha: must be > 0"),
    (_with(lambda d: d["resource"].update(total_units=10.5)), r"\$\.resource\.total_units: expected an integer"),
    (_with(lambda d: d["resource"].update(unit_value={"value": 80, "unit": "€"})),
     r"\$\.resource\.unit_value\.confidence: required"),
    (_with(lambda d: d["resource"].update(unit_value={"value": 80, "unit": "€", "confidence": "sure"})),
     r"\$\.resource\.unit_value\.confidence: 'sure' is not one of"),
    (_with(lambda d: d["resource"].update(unit_value={"value": 80, "unit": "€", "confidence": "high"})),
     r"\$\.resource\.unit_value: .*needs a source"),
    (_with(lambda d: d["damage_curves"]["logistic"].update(steepness=0)),
     r"\$\.damage_curves\.logistic: logistic_damage: steepness must be"),
    (_with(lambda d: d["damage_curves"]["logistic"].update(base=2)),
     r"\$\.damage_curves\.logistic: unknown key 'base'"),
    (_with(lambda d: d["damage_curves"].update(odd={"type": "cubic"})),
     r"\$\.damage_curves\.odd\.type: unknown curve type 'cubic'"),
    (_bad(interactions=[{"source": "Water", "target": "Fish", "strength": 0.1}]),
     r"\$\.interactions\[0\]\.target: unknown agent 'Fish'"),
    (_bad(provenance_defaults={"agent[*].weight": {"unit": "-", "confidence": "low"}}),
     r'\$\.provenance_defaults\["agent\[\*\]\.weight"\]: matches no parameter'),
    (_bad(discount={"profile": "stern"}), r"\$\.discount\.profile: unknown profile 'stern'"),
    (_bad(discount={"rate_schedule": [{"from_year": 0}]}), r"\$\.discount\.rate_schedule\[0\]\.rate: required"),
    (_bad(carbon={"stored_carbon_tonnes": 1}), r"\$\.carbon\.annual_absorption_tonnes: required"),
    (_bad(pricing={"anchors": [{"agent_name": "Fish", "anchor_value": 1, "source": "s", "confidence": "low"}]}),
     r"\$\.pricing\.anchors\[0\]\.agent_name: unknown agent 'Fish'"),
    (_bad(pricing={"anchors": [], "scarcity_functions": {"Fish Stock": {"type": "smooth"}}}),
     r'\$\.pricing\.scarcity_functions\["Fish Stock"\]: unknown agent'),
    (_bad(run={"units": "many"}), r"\$\.run\.units: expected a number"),
    (_bad(recovery={"type": "linear", "slope": 1.5}), r"\$\.recovery: slope must be in"),
])
def test_validation_errors_name_the_json_path(data, message):
    with pytest.raises(ValueError, match=message):
        case_from_dict(data)


def test_engine_validation_runs_on_load():
    d = doc()
    d["agents"][0]["dependency_weight"] = 0.9  # weights sum to 1.3
    case_from_dict(d)  # structurally valid
    with pytest.raises(ValueError, match="sum"):
        ecosystem_from_dict(d)


@pytest.mark.parametrize("text,message", [
    ('{"a": 1, "a": 2}', "duplicate key 'a'"),
    ('{"a": NaN}', "NaN is not allowed"),
    ('{"a": Infinity}', "Infinity is not allowed"),
    ('{"a": ', "Expecting value"),
])
def test_read_json_is_strict(tmp_path, text, message):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message) as exc:
        read_json(path)
    assert str(exc.value).startswith(str(path))


def test_load_errors_name_the_file(tmp_path):
    path = tmp_path / "case.json"
    path.write_text(json.dumps(_bad(colour="green")), encoding="utf-8")
    with pytest.raises(ValueError, match=r"case\.json: \$: unknown key 'colour'"):
        load_ecosystem(path)


def test_quantities_are_typed_like_the_models():
    eco = ecosystem_from_dict(doc(discount={"rate_schedule": 0.03, "scarcity_rate": 0, "horizon_years": 50.0}))
    assert isinstance(eco.resource.total_units, int)
    assert isinstance(eco.resource.unit_value, float)
    assert isinstance(eco.agents[0].dependency_weight, float)
    assert eco.resource.discount.horizon_years == 50 and isinstance(eco.resource.discount.horizon_years, int)
    assert math.isclose(eco.resource.discount.scarcity_rate, 0.0)


def test_logistic_damage_is_rebuilt_exactly():
    eco = build_forest_ecosystem(total_trees=100)
    eco.damage_model = "direct"  # a plain logistic is not flat at small losses (area_loss)
    eco.agents[0].damage_function = logistic_damage(threshold=0.45, steepness=7.5)
    again = ecosystem_from_dict(ecosystem_to_dict(eco))
    assert again.agents[0].damage_function.kernel == eco.agents[0].damage_function.kernel
    assert again.agents[0].damage_function.threshold == 0.45
