"""
Tests for gaia.carbon — Carbon accounting module.

Covers carbon release, absorption foregone, monetized carbon cost,
annual absorption during maturation, and carbon payback period.
"""

import pytest

from gaia.carbon import (
    compute_annual_absorption,
    compute_carbon_cost,
    compute_carbon_payback_period,
    compute_carbon_release,
    compute_absorption_foregone,
)
from gaia.models import CarbonProfile, SuccessionCurve


# ── Test fixtures ──────────────────────────────────────────────────────────────

_FOREST_CARBON = CarbonProfile(
    stored_carbon_tonnes=0.8,
    annual_absorption_tonnes=0.022,
    soil_carbon_tonnes=0.3,
    soil_release_fraction=0.25,
    carbon_price_per_tonne=80.0,
)

_POSIDONIA_CARBON = CarbonProfile(
    stored_carbon_tonnes=130.0,
    annual_absorption_tonnes=5.9,
    soil_carbon_tonnes=2600.0,
    soil_release_fraction=0.05,
    carbon_price_per_tonne=80.0,
)

_FOREST_SUCCESSION = SuccessionCurve(
    pioneer_end_year=8.0,
    intermediate_end_year=25.0,
    climax_approach_year=60.0,
    pioneer_service=0.05,
    intermediate_service=0.35,
    maturation_delay=2.0,
)

_POSIDONIA_SUCCESSION = SuccessionCurve(
    pioneer_end_year=20.0,
    intermediate_end_year=50.0,
    climax_approach_year=120.0,
    pioneer_service=0.02,
    intermediate_service=0.25,
    maturation_delay=5.0,
)


# ── Tests: carbon release ─────────────────────────────────────────────────────


class TestCarbonRelease:
    """Tests for compute_carbon_release."""

    def test_includes_biomass_and_soil(self):
        """Release should include both stored carbon and soil carbon fraction."""
        release = compute_carbon_release(_FOREST_CARBON, 1)
        expected = 0.8 + 0.3 * 0.25  # 0.875
        assert abs(release - expected) < 1e-6

    def test_scales_with_units(self):
        """Release should scale linearly with units extracted."""
        r1 = compute_carbon_release(_FOREST_CARBON, 1)
        r100 = compute_carbon_release(_FOREST_CARBON, 100)
        assert abs(r100 - r1 * 100) < 1e-4

    def test_soil_release_fraction_bounded(self):
        """Only a fraction of soil carbon is released."""
        release_per_unit = compute_carbon_release(_FOREST_CARBON, 1)
        total_stored = 0.8 + 0.3  # biomass + all soil
        assert release_per_unit < total_stored


# ── Tests: absorption foregone ─────────────────────────────────────────────────


class TestAbsorptionForegone:
    """Tests for compute_absorption_foregone."""

    def test_scales_with_years(self):
        """Foregone absorption scales linearly with remaining years."""
        f10 = compute_absorption_foregone(_FOREST_CARBON, 1, 10.0)
        f100 = compute_absorption_foregone(_FOREST_CARBON, 1, 100.0)
        assert abs(f100 - f10 * 10) < 1e-6


# ── Tests: carbon cost ─────────────────────────────────────────────────────────


class TestCarbonCost:
    """Tests for compute_carbon_cost."""

    def test_cost_equals_tonnes_times_price(self):
        """Release cost = release tonnes × price exactly."""
        result = compute_carbon_cost(_FOREST_CARBON, 100, 80.0)
        release = compute_carbon_release(_FOREST_CARBON, 100)
        expected_cost = release * 80.0
        assert abs(result["release_cost"] - expected_cost) < 1e-4

    def test_double_externality_greater_than_release_only(self):
        """Total cost (release + foregone) should exceed release cost alone."""
        result = compute_carbon_cost(_FOREST_CARBON, 100, 80.0)
        assert result["total_cost"] > result["release_cost"]

    def test_zero_units(self):
        """Zero extraction should give zero cost."""
        result = compute_carbon_cost(_FOREST_CARBON, 0, 80.0)
        assert result["release_cost"] == 0.0
        assert result["foregone_cost_per_year"] == 0.0


# ── Tests: annual absorption ──────────────────────────────────────────────────


class TestAnnualAbsorption:
    """Tests for compute_annual_absorption."""

    def test_scales_with_service_fraction(self):
        """Absorption at half service = half of max absorption."""
        full = compute_annual_absorption(_FOREST_CARBON, 100, 1.0)
        half = compute_annual_absorption(_FOREST_CARBON, 100, 0.5)
        assert abs(half - full * 0.5) < 1e-6

    def test_zero_service_zero_absorption(self):
        """During delay period (service=0), absorption should be zero."""
        absorbed = compute_annual_absorption(_FOREST_CARBON, 100, 0.0)
        assert absorbed == 0.0


# ── Tests: carbon payback period ───────────────────────────────────────────────


class TestCarbonPaybackPeriod:
    """Tests for compute_carbon_payback_period."""

    def test_payback_always_positive(self):
        """Payback period should be > 0 for any extraction."""
        period = compute_carbon_payback_period(
            _FOREST_CARBON, 100, 100, _FOREST_SUCCESSION
        )
        assert period > 0

    def test_posidonia_payback_longer_than_forest(self):
        """Posidonia has much more stored carbon — payback should be longer."""
        forest_payback = compute_carbon_payback_period(
            _FOREST_CARBON, 100, 100, _FOREST_SUCCESSION
        )
        posidonia_payback = compute_carbon_payback_period(
            _POSIDONIA_CARBON, 100, 100, _POSIDONIA_SUCCESSION
        )
        assert posidonia_payback > forest_payback

    def test_zero_release_zero_payback(self):
        """Zero stored carbon → instant payback."""
        zero_profile = CarbonProfile(
            stored_carbon_tonnes=0.0,
            annual_absorption_tonnes=0.022,
            soil_carbon_tonnes=0.0,
            soil_release_fraction=0.0,
            carbon_price_per_tonne=80.0,
        )
        period = compute_carbon_payback_period(
            zero_profile, 100, 100, _FOREST_SUCCESSION
        )
        assert period == 0.0
