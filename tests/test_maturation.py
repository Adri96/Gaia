"""
Tests for v0.4 maturation integration — end-to-end tests for the succession
maturation pass integrated into run_restoration and the resilience zone
tagging in run_extraction.

These tests verify that the new v0.4 features work correctly when used
through the simulation engine, not just as standalone modules.
"""

import pytest

from gaia.cases.forest import build_forest_ecosystem
from gaia.models import RestorationCost, SuccessionCurve
from gaia.recovery import logistic_recovery
from gaia.simulation import run_extraction, run_restoration


# ── Test fixtures ──────────────────────────────────────────────────────────────

_FOREST_SUCCESSION = SuccessionCurve(
    pioneer_end_year=8.0,
    intermediate_end_year=25.0,
    climax_approach_year=60.0,
    pioneer_service=0.05,
    intermediate_service=0.35,
    maturation_delay=2.0,
)

_COST = RestorationCost(
    planting_cost_per_unit=50.0,
    annual_maintenance_per_unit=10.0,
    maintenance_years=10,
)


def _make_ecosystem(total_trees=1000, threshold=0.3):
    """Build a small forest ecosystem for testing."""
    return build_forest_ecosystem(
        total_trees=total_trees,
        safe_threshold_ratio=threshold,
    )


# ── Tests: restoration with maturation ─────────────────────────────────────────


class TestRestorationWithMaturation:
    """Tests for run_restoration with succession_curve and time_horizon_years."""

    def test_maturation_timeline_produced(self):
        """When succession_curve + time_horizon > 0, maturation timeline should be produced."""
        eco = _make_ecosystem()
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(
            eco, 500, _COST, recovery_fns,
            succession_curve=_FOREST_SUCCESSION,
            time_horizon_years=60,
        )
        assert len(result.maturation_timeline) == 60
        assert result.years_to_50pct > 0
        assert result.years_to_90pct > result.years_to_50pct
        assert result.total_maturation_gap > 0

    def test_no_maturation_without_succession(self):
        """Without succession_curve, maturation fields should be empty/zero."""
        eco = _make_ecosystem()
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, _COST, recovery_fns)
        assert result.maturation_timeline == []
        assert result.years_to_pioneer == 0.0
        assert result.years_to_50pct == 0.0
        assert result.total_maturation_gap == 0.0

    def test_no_maturation_with_zero_horizon(self):
        """With time_horizon_years=0, maturation pass should be skipped."""
        eco = _make_ecosystem()
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(
            eco, 500, _COST, recovery_fns,
            succession_curve=_FOREST_SUCCESSION,
            time_horizon_years=0,
        )
        assert result.maturation_timeline == []

    def test_maturation_gap_positive(self):
        """Maturation gap must be positive (services lost while waiting)."""
        eco = _make_ecosystem()
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(
            eco, 500, _COST, recovery_fns,
            succession_curve=_FOREST_SUCCESSION,
            time_horizon_years=60,
        )
        assert result.total_maturation_gap > 0

    def test_cumulative_service_monotonic(self):
        """Cumulative service in the timeline must be monotonically non-decreasing."""
        eco = _make_ecosystem()
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(
            eco, 500, _COST, recovery_fns,
            succession_curve=_FOREST_SUCCESSION,
            time_horizon_years=60,
        )
        for i in range(1, len(result.maturation_timeline)):
            assert (result.maturation_timeline[i].cumulative_service_value
                    >= result.maturation_timeline[i - 1].cumulative_service_value)


# ── Tests: extraction with resilience zones ────────────────────────────────────


class TestExtractionWithResilience:
    """Tests for run_extraction with resilience config (auto-enabled via build_forest_ecosystem)."""

    def test_resilience_zone_defaults_to_green(self):
        """First extraction step should be in green zone."""
        eco = _make_ecosystem(total_trees=1000)
        result = run_extraction(eco, 100)
        assert result.steps[0].resilience_zone == "green"

    def test_zone_transitions_occur(self):
        """Extracting enough should cause zone transitions."""
        eco = _make_ecosystem(total_trees=1000)
        result = run_extraction(eco, 900)
        zones = [s.resilience_zone for s in result.steps]
        unique_zones = set(zones)
        # Should have at least green and one other zone
        assert len(unique_zones) >= 2

    def test_red_zone_at_high_depletion(self):
        """At very high depletion → should be in red zone."""
        eco = _make_ecosystem(total_trees=1000)
        result = run_extraction(eco, 900)
        final_zone = result.steps[-1].resilience_zone
        assert final_zone == "red"

    def test_irreversibility_warning_at_high_depletion(self):
        """Irreversibility warning should trigger at configured ratio."""
        eco = _make_ecosystem(total_trees=1000)
        result = run_extraction(eco, 800)
        # irreversibility_flag_ratio=0.60, extracting 800/1000=0.80 depletion > 0.60
        assert result.steps[-1].irreversibility_warning is True

    def test_model_confidence_decreases(self):
        """Model confidence should decrease with higher depletion."""
        eco = _make_ecosystem(total_trees=1000)
        result = run_extraction(eco, 900)
        first_confidence = result.steps[0].model_confidence
        last_confidence = result.steps[-1].model_confidence
        assert last_confidence < first_confidence

    def test_backward_compat_no_resilience(self):
        """Ecosystem without resilience config → default green/1.0/False."""
        from gaia.models import Agent, Ecosystem, Resource
        from gaia.damage import logistic_damage
        resource = Resource(
            name="Test", total_units=100,
            safe_threshold_ratio=0.3, unit_value=10.0,
        )
        agents = [Agent(
            name="A", dependency_weight=1.0,
            damage_function=logistic_damage(0.3, 12.0),
            monetary_rate=1000.0, description="Test",
        )]
        eco = Ecosystem(name="Test", resource=resource, agents=agents)
        result = run_extraction(eco, 50)
        for step in result.steps:
            assert step.resilience_zone == "green"
            assert step.model_confidence == 1.0
            assert step.irreversibility_warning is False
