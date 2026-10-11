"""
Tests for Gaia v0.8.1 JSON serialization.

Validates that SimulationResult and RestorationResult convert
to valid, predictable JSON without callables or non-serializable objects.
"""

import json

import pytest

from gaia.cases.forest import _FOREST_SUCCESSION, build_forest_ecosystem
from gaia.models import RestorationCost
from gaia.recovery import logistic_recovery
from gaia.serialization import (
    GAIA_VERSION,
    restoration_result_to_dict,
    simulation_result_to_dict,
    to_json,
)
from gaia.simulation import run_extraction, run_restoration


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_extraction(n_trees=100, n_cut=50, with_pricing=False):
    eco = build_forest_ecosystem(
        total_trees=n_trees, safe_threshold_ratio=0.3,
        with_pricing=with_pricing,
    )
    return run_extraction(eco, n_cut), eco


def _run_restoration(n_trees=100, n_restore=50):
    eco = build_forest_ecosystem(
        total_trees=n_trees, safe_threshold_ratio=0.3,
    )
    cost = RestorationCost(50.0, 10.0, 10)
    fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    return run_restoration(eco, n_restore, cost, fns), eco


# ── Extraction JSON ──────────────────────────────────────────────────────────


class TestExtractionSerialization:
    def test_roundtrip_valid_json(self):
        result, _ = _run_extraction()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_version_and_mode(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        assert d["gaia_version"] == GAIA_VERSION
        assert d["mode"] == "extraction"

    def test_summary_fields(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        s = d["summary"]
        assert s["total_units_extracted"] == 50
        assert s["revenue_eur"] == round(result.revenue, 2)
        assert s["annual_externality_eur_yr"] == round(result.annual_externality, 2)
        assert s["pv_externality_eur_pv"] == round(result.pv_externality, 2)
        assert s["net_social_cost_eur_pv"] == round(result.net_social_cost, 2)
        assert s["discount_is_default"] is False
        assert "final_ecosystem_health" in s
        assert s["num_steps"] == 50

    def test_steps_included_by_default(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        assert "steps" in d
        assert len(d["steps"]) == 50

    def test_steps_omitted_when_requested(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result, include_steps=False)
        assert "steps" not in d
        assert d["summary"]["num_steps"] == 50

    def test_ecosystem_metadata(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        eco = d["ecosystem"]
        assert eco["name"] == "Oak Valley Forest"
        assert eco["resource"]["total_units"] == 100
        assert eco["resource"]["safe_threshold_ratio"] == 0.3
        assert len(eco["agents"]) == 4
        assert len(eco["interactions"]) == 2

    def test_agent_metadata_no_callables(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        agent = d["ecosystem"]["agents"][0]
        assert "name" in agent
        assert "dependency_weight" in agent
        assert "annual_value_eur_yr" in agent
        assert "damage_function" not in agent

    def test_step_agent_damages_as_dict(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        step = d["steps"][0]
        assert isinstance(step["agent_damages"], dict)
        assert "Human Communities" in step["agent_damages"]

    def test_npv_present(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        assert "npv_analysis" in d
        npv = d["npv_analysis"]
        assert "services_eur_pv" in npv
        assert "carbon_release_eur_pv" in npv
        assert npv["total_eur_pv"] == d["summary"]["pv_externality_eur_pv"]
        assert "horizon_years" in npv

    def test_pricing_present_when_enabled(self):
        result, _ = _run_extraction(with_pricing=True)
        d = simulation_result_to_dict(result)
        assert "pricing" in d
        assert "prices_eur_yr" in d["pricing"]
        assert d["pricing"]["experimental"] is True
        assert d["pricing"]["spectral_radius_bound"] < 1.0

    def test_pricing_absent_when_disabled(self):
        result, _ = _run_extraction(with_pricing=False)
        d = simulation_result_to_dict(result)
        assert "pricing" not in d

    def test_no_function_references_in_json(self):
        result, _ = _run_extraction()
        json_str = to_json(result)
        assert "function" not in json_str.lower() or "damage_function" not in json_str
        assert "<built-in" not in json_str
        assert "lambda" not in json_str

    def test_resource_carbon_metadata(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        res = d["ecosystem"]["resource"]
        assert res["has_carbon_profile"] is True
        assert "carbon_stored_per_unit" in res

    def test_resource_substrate_metadata(self):
        result, _ = _run_extraction()
        d = simulation_result_to_dict(result)
        res = d["ecosystem"]["resource"]
        assert res["has_substrate"] is True
        assert res["substrate_type"] == "terrestrial_soil"


# ── Restoration JSON ─────────────────────────────────────────────────────────


class TestRestorationSerialization:
    def test_roundtrip_valid_json(self):
        result, _ = _run_restoration()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_version_and_mode(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        assert d["gaia_version"] == GAIA_VERSION
        assert d["mode"] == "restoration"

    def test_summary_fields(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        s = d["summary"]
        assert s["total_units_restored"] == 50
        assert "total_restoration_cost_eur" in s
        assert "annual_recovered_value_eur_yr" in s
        assert s["net_restoration_value_eur_pv"] == round(result.net_restoration_pv, 2)
        assert s["restoration_cost_ratio"] == round(result.restoration_cost_ratio, 4)
        pen = d["destroy_then_restore_penalty"]
        assert pen["total_eur_pv"] == round(
            result.destroy_then_restore_penalty.total, 2)
        assert pen["penalty_ratio"] == round(
            result.destroy_then_restore_penalty.ratio, 4)
        assert "final_ecosystem_health" in s

    def test_restoration_cost_included(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        rc = d["restoration_cost"]
        assert rc["planting_cost_per_unit_eur"] == 50.0
        assert rc["annual_maintenance_per_unit_eur_yr"] == 10.0
        assert rc["maintenance_years"] == 10
        assert "total_cost_per_unit_eur" in rc

    def test_steps_included_by_default(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        assert "steps" in d
        assert len(d["steps"]) == 50

    def test_steps_omitted_when_requested(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result, include_steps=False)
        assert "steps" not in d

    def test_step_agent_data_as_dicts(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        step = d["steps"][0]
        assert isinstance(step["agent_recoveries"], dict)
        assert isinstance(step["agent_service_value_eur_yr"], dict)

    def test_notes_included_when_provided(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(
            result, notes=["Test note about marine costs"],
        )
        assert "notes" in d
        assert d["notes"] == ["Test note about marine costs"]

    def test_notes_absent_when_not_provided(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        assert "notes" not in d


# ── to_json convenience function ─────────────────────────────────────────────


class TestToJson:
    def test_extraction_result(self):
        result, _ = _run_extraction()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert parsed["mode"] == "extraction"

    def test_restoration_result(self):
        result, _ = _run_restoration()
        json_str = to_json(result)
        parsed = json.loads(json_str)
        assert parsed["mode"] == "restoration"

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError, match="Expected SimulationResult"):
            to_json({"not": "a result"})

    def test_include_steps_false(self):
        result, _ = _run_extraction()
        json_str = to_json(result, include_steps=False)
        parsed = json.loads(json_str)
        assert "steps" not in parsed

    def test_notes_on_extraction(self):
        result, _ = _run_extraction()
        json_str = to_json(result, notes=["A note"])
        parsed = json.loads(json_str)
        assert parsed["notes"] == ["A note"]

    def test_notes_on_restoration(self):
        result, _ = _run_restoration()
        json_str = to_json(result, notes=["Marine note"])
        parsed = json.loads(json_str)
        assert parsed["notes"] == ["Marine note"]

    def test_custom_indent(self):
        result, _ = _run_extraction()
        json_str = to_json(result, indent=4, include_steps=False)
        # 4-space indent means lines start with "    "
        lines = json_str.split("\n")
        indented = [l for l in lines if l.startswith("    ")]
        assert len(indented) > 0


# ── Every monetary key carries its unit ──────────────────────────────────────

# Numeric JSON keys that are not money (counts, ratios, physical quantities,
# years). Every other numeric key must end in a unit suffix.
_NON_MONETARY_KEYS = {
    # resource / agents / interactions
    "total_units", "safe_threshold_ratio", "safe_threshold_units",
    "area_ha", "units_per_ha", "discount_rate", "discount_horizon_years",
    "carbon_stored_per_unit", "carbon_absorption_per_unit_yr",
    "carbon_price_growth", "carbon_released_tco2", "carbon_absorption_lost_tco2_yr",
    "dependency_weight", "trophic_level", "keystone_threshold", "strength",
    # extraction summary and steps
    "total_units_extracted", "final_ecosystem_health", "num_steps", "step",
    "units_extracted", "depletion_ratio", "ecosystem_health", "agent_damages",
    "agent_direct_damages", "agent_cascade_damages", "model_confidence",
    "substrate_erosion", "effective_k", "k_fraction",
    # restoration
    "total_units_restored", "units_restored", "recovery_ratio",
    "units_lost", "depletion_before", "depletion_after",
    "initial_ecosystem_health",
    "agent_recoveries", "maintenance_years", "year", "service_fraction",
    "annual_carbon_absorbed", "cumulative_carbon_absorbed",
    "years_to_pioneer", "years_to_50pct", "years_to_90pct",
    "substrate_ceiling", "substrate_recovery_years", "carbon_payback_years",
    "projected_breakeven_year", "horizon_years",
    # ratios
    "restoration_cost_ratio", "penalty_ratio", "roi",
    # pricing decomposition
    "scarcity_multipliers", "demand_multipliers", "spectral_radius_bound", "iterations",
    # Step 6.3: trophic factors, extraction substrate, discounting used
    "trophic_amplification", "capacity_lost_units",
    "rate_schedule", "delta", "eta", "g", "scarcity_rate",
}
_UNIT_SUFFIXES = ("_eur_yr", "_eur_per_ha_yr", "_eur_pv", "_eur", "_eur_per_t")


def _numeric_keys(obj, key, agent_names, out):
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(key)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            # Per-agent maps are keyed by agent name: keep the parent key
            _numeric_keys(v, key if k in agent_names else k, agent_names, out)
    elif isinstance(obj, list):
        for v in obj:
            _numeric_keys(v, key, agent_names, out)
    return out


@pytest.mark.parametrize("make", [
    lambda: _run_extraction()[0],
    lambda: _run_extraction(with_pricing=True)[0],
    lambda: _run_restoration()[0],
])
def test_every_monetary_key_has_unit_suffix(make):
    result = make()
    d = json.loads(to_json(result, include_steps=True))
    names = {a.name for a in result.ecosystem.agents}
    keys = _numeric_keys(d, None, names, set())
    unlabelled = sorted(
        k for k in keys
        if k not in _NON_MONETARY_KEYS and not k.endswith(_UNIT_SUFFIXES)
    )
    assert not unlabelled, f"numeric keys without a unit or allow-list entry: {unlabelled}"


def test_restoration_with_maturation_keys_have_units():
    eco = build_forest_ecosystem(total_trees=100, safe_threshold_ratio=0.3)
    cost = RestorationCost(50.0, 10.0, 10)
    fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    result = run_restoration(eco, 50, cost, fns,
                             succession_curve=_FOREST_SUCCESSION, time_horizon_years=30)
    d = json.loads(to_json(result, include_steps=True))
    assert "maturation_gap_eur_pv" in d["maturation"]
    names = {a.name for a in eco.agents}
    keys = _numeric_keys(d, None, names, set())
    unlabelled = sorted(
        k for k in keys
        if k not in _NON_MONETARY_KEYS and not k.endswith(_UNIT_SUFFIXES)
    )
    assert not unlabelled, unlabelled


# ── Strict JSON (E8) ──────────────────────────────────────────────────────────


def test_nonfinite_values_are_null_with_reason():
    import dataclasses
    eco = build_forest_ecosystem(total_trees=100)
    eco.resource = dataclasses.replace(
        eco.resource,
        substrate=dataclasses.replace(eco.resource.substrate, formation_rate=0.0),
    )
    cost = RestorationCost(planting_cost_per_unit=50.0,
                           annual_maintenance_per_unit=10.0, maintenance_years=10)
    result = run_restoration(eco, 50, cost,
                             [logistic_recovery(threshold=0.3) for _ in eco.agents])
    assert result.substrate_recovery_years == float("inf")

    def reject(name):
        raise ValueError(name)

    d = json.loads(to_json(result), parse_constant=reject)
    sub = d["substrate"]
    assert sub["substrate_recovery_years"] is None
    assert sub["substrate_recovery_years_null_reason"].startswith("never")


def test_strict_generic_reason_and_lists():
    from gaia.serialization import _strict
    out = _strict({"a": float("nan"), "b": [1.0, float("-inf")], "c": {"d": float("inf")}})
    assert out["a"] is None and "non-finite" in out["a_null_reason"]
    assert out["b"] == [1.0, None]
    assert out["c"]["d"] is None and "d_null_reason" in out["c"]
