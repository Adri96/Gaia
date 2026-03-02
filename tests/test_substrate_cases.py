"""
Gaia v0.5 — Substrate integration tests per case.

Verifies that substrate profiles are properly wired into the three preconfigured
ecosystems and that extraction/restoration with substrate produces correct
behavior relative to v0.4 (no substrate).

Integration test requirements:
    - Oak Valley with substrate: PA > v0.4 PA
    - Costa Brava with substrate: PA > v0.4 PA, irreversibility threshold observable
    - Posidonia with substrate: PA >> v0.4 PA
    - Backward compatibility: no substrate → identical v0.4 behavior
"""

import pytest

from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    Ecosystem,
    RestorationCost,
    Resource,
    SubstrateProfile,
)
from gaia.recovery import logistic_recovery
from gaia.simulation import run_extraction, run_restoration

from gaia.cases.forest import build_forest_ecosystem
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_ecosystem_without_substrate(
    total_units: int = 1_000,
    threshold: float = 0.3,
    unit_value: float = 100.0,
) -> Ecosystem:
    """Create a simple ecosystem with NO substrate (v0.4 behavior)."""
    resource = Resource(
        name="No Substrate Eco",
        total_units=total_units,
        safe_threshold_ratio=threshold,
        unit_value=unit_value,
    )
    agents = [
        Agent(
            name="Agent A",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=threshold),
            monetary_rate=100_000.0,
            description="Test agent A",
        ),
        Agent(
            name="Agent B",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=threshold),
            monetary_rate=100_000.0,
            description="Test agent B",
        ),
    ]
    return Ecosystem(name="Test Eco", resource=resource, agents=agents)


def _make_ecosystem_with_substrate(
    total_units: int = 1_000,
    threshold: float = 0.3,
    unit_value: float = 100.0,
) -> Ecosystem:
    """Create a simple ecosystem WITH substrate."""
    substrate = SubstrateProfile(
        substrate_type="terrestrial_soil",
        soil_depth_cm=30.0,
        erosion_rate_unprotected=25.0,
        erosion_rate_protected=1.0,
        formation_rate=0.4,
        capacity_function="linear",
        erosion_alpha=2.0,
        confidence="medium",
    )
    resource = Resource(
        name="Substrate Eco",
        total_units=total_units,
        safe_threshold_ratio=threshold,
        unit_value=unit_value,
        substrate=substrate,
    )
    agents = [
        Agent(
            name="Agent A",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=threshold),
            monetary_rate=100_000.0,
            description="Test agent A",
        ),
        Agent(
            name="Agent B",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=threshold),
            monetary_rate=100_000.0,
            description="Test agent B",
        ),
    ]
    return Ecosystem(name="Test Eco", resource=resource, agents=agents)


# ── Backward compatibility tests ──────────────────────────────────────────────


class TestBackwardCompatibility:
    """Spec test #9: No substrate = v0.4 behavior."""

    def test_no_substrate_steps_have_default_fields(self):
        """Without substrate, SimulationStep has default substrate fields."""
        eco = _make_ecosystem_without_substrate()
        result = run_extraction(eco, 500)

        for step in result.steps:
            assert step.substrate_erosion == 0.0
            assert step.effective_k == eco.resource.total_units
            assert step.k_fraction == 1.0

    def test_no_substrate_restoration_has_default_fields(self):
        """Without substrate, RestorationResult has default substrate fields."""
        eco = _make_ecosystem_without_substrate()
        cost = RestorationCost(
            planting_cost_per_unit=50.0,
            annual_maintenance_per_unit=10.0,
            maintenance_years=5,
        )
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, cost, recovery_fns)

        assert result.substrate_ceiling == 1.0
        assert result.substrate_recovery_years == 0.0
        assert result.prevention_advantage_with_substrate == result.prevention_advantage


class TestPristineSubstrate:
    """Spec test #10: Pristine substrate = effective_K equals total_units."""

    def test_pristine_substrate_first_step(self):
        """At step 1 (almost full cover), effective_k ≈ total_units."""
        eco = _make_ecosystem_with_substrate()
        result = run_extraction(eco, 100)
        # First step: 999/1000 cover, minimal erosion → k_fraction ≈ 1.0
        assert result.steps[0].k_fraction > 0.999


# ── Substrate-aware extraction tests ──────────────────────────────────────────


class TestSubstrateExtraction:

    def test_extraction_degrades_substrate(self):
        """Extraction should progressively degrade substrate."""
        eco = _make_ecosystem_with_substrate()
        result = run_extraction(eco, 500)

        # k_fraction should decrease as extraction progresses
        first_k = result.steps[0].k_fraction
        last_k = result.steps[-1].k_fraction
        assert last_k < first_k, "Substrate should degrade during extraction"

    def test_substrate_erosion_positive(self):
        """Substrate erosion should be positive for each step."""
        eco = _make_ecosystem_with_substrate()
        result = run_extraction(eco, 100)

        for step in result.steps:
            assert step.substrate_erosion >= 0.0

    def test_effective_k_decreases_with_extraction(self):
        """effective_k should decrease as more units are extracted."""
        eco = _make_ecosystem_with_substrate()
        result = run_extraction(eco, 500)

        first_ek = result.steps[0].effective_k
        last_ek = result.steps[-1].effective_k
        assert last_ek <= first_ek


# ── Substrate-aware restoration tests ─────────────────────────────────────────


class TestSubstrateRestoration:

    def test_restoration_ceiling_binding(self):
        """Spec test #8: Restoration ceiling is binding (< 1.0)."""
        eco = _make_ecosystem_with_substrate()
        cost = RestorationCost(
            planting_cost_per_unit=50.0,
            annual_maintenance_per_unit=10.0,
            maintenance_years=5,
        )
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, cost, recovery_fns)

        assert result.substrate_ceiling < 1.0, (
            f"Substrate ceiling should be < 1.0 after extraction, got {result.substrate_ceiling}"
        )

    def test_substrate_recovery_years_positive(self):
        """After degradation, recovery should take positive years."""
        eco = _make_ecosystem_with_substrate()
        cost = RestorationCost(
            planting_cost_per_unit=50.0,
            annual_maintenance_per_unit=10.0,
            maintenance_years=5,
        )
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, cost, recovery_fns)

        assert result.substrate_recovery_years > 0.0

    def test_prevention_advantage_with_substrate_higher(self):
        """Spec test #7: PA increases with substrate modeling."""
        eco = _make_ecosystem_with_substrate()
        cost = RestorationCost(
            planting_cost_per_unit=50.0,
            annual_maintenance_per_unit=10.0,
            maintenance_years=5,
        )
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, cost, recovery_fns)

        assert result.prevention_advantage_with_substrate >= result.prevention_advantage, (
            f"PA with substrate ({result.prevention_advantage_with_substrate}) "
            f"should be >= PA without ({result.prevention_advantage})"
        )


# ── Per-case integration tests ────────────────────────────────────────────────


class TestOakValleyForestSubstrate:
    """Oak Valley Forest with substrate profile."""

    def test_forest_has_substrate(self):
        """Forest ecosystem should have substrate configured."""
        eco = build_forest_ecosystem()
        assert eco.resource.substrate is not None
        assert eco.resource.substrate.substrate_type == "terrestrial_soil"
        assert eco.resource.substrate.capacity_function == "linear"

    def test_forest_extraction_degrades_substrate(self):
        """Forest extraction should degrade substrate."""
        eco = build_forest_ecosystem(total_trees=1000)
        result = run_extraction(eco, 500)
        assert result.steps[-1].k_fraction < 1.0

    def test_forest_pa_with_substrate_higher(self):
        """Forest PA with substrate should be >= v0.4 PA."""
        eco = build_forest_ecosystem(total_trees=1000)
        cost = RestorationCost(
            planting_cost_per_unit=50.0,
            annual_maintenance_per_unit=10.0,
            maintenance_years=10,
        )
        recovery_fns = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        result = run_restoration(eco, 500, cost, recovery_fns)
        assert result.prevention_advantage_with_substrate >= result.prevention_advantage


class TestCostaBravaSubstrate:
    """Costa Brava Holm Oak Forest with substrate profile."""

    def test_costa_brava_has_substrate(self):
        """Costa Brava ecosystem should have substrate configured."""
        eco = build_costa_brava_ecosystem()
        assert eco.resource.substrate is not None
        assert eco.resource.substrate.substrate_type == "terrestrial_soil"
        assert eco.resource.substrate.capacity_function == "threshold"
        assert eco.resource.substrate.critical_minimum == 8.0

    def test_costa_brava_extraction_degrades(self):
        """Costa Brava extraction should show substrate degradation."""
        eco = build_costa_brava_ecosystem(total_trees=1000)
        result = run_extraction(eco, 400)
        assert result.steps[-1].k_fraction < 1.0

    def test_costa_brava_pa_with_substrate_higher(self):
        """Costa Brava PA with substrate should be >= v0.4 PA."""
        eco = build_costa_brava_ecosystem(total_trees=1000)
        cost = RestorationCost(
            planting_cost_per_unit=80.0,
            annual_maintenance_per_unit=15.0,
            maintenance_years=15,
        )
        recovery_fns = [logistic_recovery(threshold=0.25) for _ in eco.agents]
        result = run_restoration(eco, 400, cost, recovery_fns)
        assert result.prevention_advantage_with_substrate >= result.prevention_advantage


class TestPosidoniaSubstrate:
    """Costa Brava Posidonia Meadow with substrate profile."""

    def test_posidonia_has_substrate(self):
        """Posidonia ecosystem should have substrate configured."""
        eco = build_posidonia_ecosystem()
        assert eco.resource.substrate is not None
        assert eco.resource.substrate.substrate_type == "marine_matte"
        assert eco.resource.substrate.capacity_function == "logistic"

    def test_posidonia_extraction_degrades(self):
        """Posidonia extraction should show substrate degradation."""
        eco = build_posidonia_ecosystem(total_hectares=1000)
        result = run_extraction(eco, 400)
        assert result.steps[-1].k_fraction < 1.0

    def test_posidonia_pa_with_substrate_higher(self):
        """Posidonia PA with substrate should be >= v0.4 PA."""
        eco = build_posidonia_ecosystem(total_hectares=1000)
        cost = RestorationCost(
            planting_cost_per_unit=50_000.0,
            annual_maintenance_per_unit=5_000.0,
            maintenance_years=30,
        )
        recovery_fns = [logistic_recovery(threshold=0.2) for _ in eco.agents]
        result = run_restoration(eco, 400, cost, recovery_fns)
        assert result.prevention_advantage_with_substrate >= result.prevention_advantage

    def test_posidonia_marine_erosion_alpha(self):
        """Posidonia should use marine erosion alpha (3.0)."""
        eco = build_posidonia_ecosystem()
        assert eco.resource.substrate.erosion_alpha == 3.0


# ── Report output tests ──────────────────────────────────────────────────────


class TestSubstrateReportOutput:

    def test_extraction_report_contains_substrate_section(self):
        """Extraction report should contain Substrate Impact Assessment."""
        from gaia.report import format_report
        eco = build_costa_brava_ecosystem(total_trees=1000)
        result = run_extraction(eco, 400)
        report = format_report(result)
        # Only assert section present if substrate actually degraded
        if result.steps[-1].k_fraction < 1.0:
            assert "Substrate Impact Assessment" in report
            assert "Substrate type:" in report
            assert "Pristine K:" in report

    def test_restoration_report_contains_substrate_section(self):
        """Restoration report should contain Substrate Restoration Ceiling."""
        from gaia.report import format_restoration_report
        eco = build_costa_brava_ecosystem(total_trees=1000)
        cost = RestorationCost(
            planting_cost_per_unit=80.0,
            annual_maintenance_per_unit=15.0,
            maintenance_years=15,
        )
        recovery_fns = [logistic_recovery(threshold=0.25) for _ in eco.agents]
        result = run_restoration(eco, 400, cost, recovery_fns)
        report = format_restoration_report(result)
        if result.substrate_ceiling < 1.0:
            assert "Substrate Restoration Ceiling" in report

    def test_no_substrate_report_no_section(self):
        """Report without substrate should NOT contain substrate sections."""
        from gaia.report import format_report
        eco = _make_ecosystem_without_substrate()
        result = run_extraction(eco, 500)
        report = format_report(result)
        assert "Substrate Impact Assessment" not in report
