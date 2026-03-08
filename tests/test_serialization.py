"""
Tests for Gaia v0.8.1 JSON serialization.

Validates that SimulationResult and RestorationResult convert
to valid, predictable JSON without callables or non-serializable objects.
"""

import json

import pytest

from gaia.cases.forest import build_forest_ecosystem
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
        assert "total_private_revenue" in s
        assert "total_externality_cost" in s
        assert "net_social_cost" in s
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
        assert "monetary_rate" in agent
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
        assert "direct" in npv
        assert "carbon_release" in npv
        assert "total" in npv
        assert "horizon" in npv

    def test_pricing_present_when_enabled(self):
        result, _ = _run_extraction(with_pricing=True)
        d = simulation_result_to_dict(result)
        assert "pricing" in d
        assert "prices" in d["pricing"]
        assert "converged" in d["pricing"]

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
        assert "total_restoration_cost" in s
        assert "total_recovered_value" in s
        assert "net_restoration_value" in s
        assert "prevention_advantage" in s
        assert "final_ecosystem_health" in s

    def test_restoration_cost_included(self):
        result, _ = _run_restoration()
        d = restoration_result_to_dict(result)
        rc = d["restoration_cost"]
        assert rc["planting_cost_per_unit"] == 50.0
        assert rc["annual_maintenance_per_unit"] == 10.0
        assert rc["maintenance_years"] == 10
        assert "total_cost_per_unit" in rc

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
        assert isinstance(step["agent_service_values"], dict)

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
