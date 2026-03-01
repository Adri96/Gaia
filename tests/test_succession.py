"""
Tests for gaia.succession — Succession curve evaluation and maturation timeline.

Covers the succession_service() curve function, phase identification,
maturation timeline, maturation gap, and years_to_threshold.
"""

import pytest

from gaia.models import CarbonProfile, SuccessionCurve
from gaia.succession import (
    compute_maturation_gap,
    compute_maturation_timeline,
    find_years_to_threshold,
    get_succession_phase,
    succession_service,
)


# ── Test fixtures ──────────────────────────────────────────────────────────────

# Oak Valley Forest succession curve
_FOREST = SuccessionCurve(
    pioneer_end_year=8.0,
    intermediate_end_year=25.0,
    climax_approach_year=60.0,
    pioneer_service=0.05,
    intermediate_service=0.35,
    maturation_delay=2.0,
)

# Costa Brava (slower)
_CB = SuccessionCurve(
    pioneer_end_year=12.0,
    intermediate_end_year=35.0,
    climax_approach_year=80.0,
    pioneer_service=0.03,
    intermediate_service=0.30,
    maturation_delay=3.0,
)

# Posidonia (slowest)
_POSIDONIA = SuccessionCurve(
    pioneer_end_year=20.0,
    intermediate_end_year=50.0,
    climax_approach_year=120.0,
    pioneer_service=0.02,
    intermediate_service=0.25,
    maturation_delay=5.0,
)

_CARBON = CarbonProfile(
    stored_carbon_tonnes=0.8,
    annual_absorption_tonnes=0.022,
    soil_carbon_tonnes=0.3,
    soil_release_fraction=0.25,
    carbon_price_per_tonne=80.0,
)


# ── Tests: succession_service ──────────────────────────────────────────────────


class TestSuccessionService:
    """Tests for the succession_service() curve function."""

    def test_zero_service_during_delay(self):
        """During the maturation delay period, service must be exactly 0."""
        assert succession_service(_FOREST, 0.0) == 0.0
        assert succession_service(_FOREST, 1.0) == 0.0
        assert succession_service(_FOREST, 1.9) == 0.0

    def test_pioneer_phase_capped(self):
        """At the end of pioneer phase, service should be at pioneer_service."""
        # End of delay + end of pioneer
        year = _FOREST.maturation_delay + _FOREST.pioneer_end_year
        svc = succession_service(_FOREST, year)
        assert abs(svc - _FOREST.pioneer_service) < 1e-6

    def test_intermediate_phase_end(self):
        """At the end of intermediate phase, service should be at intermediate_service."""
        year = _FOREST.maturation_delay + _FOREST.intermediate_end_year
        svc = succession_service(_FOREST, year)
        assert abs(svc - _FOREST.intermediate_service) < 1e-6

    def test_climax_approaches_one(self):
        """At the climax approach year, service should be near 1.0."""
        year = _FOREST.maturation_delay + _FOREST.climax_approach_year
        svc = succession_service(_FOREST, year)
        assert svc > 0.95
        assert svc <= 1.0

    def test_monotonically_increasing(self):
        """Succession service must be monotonically non-decreasing."""
        max_year = _FOREST.maturation_delay + _FOREST.climax_approach_year + 10
        prev = 0.0
        step = 0.5
        year = 0.0
        while year <= max_year:
            svc = succession_service(_FOREST, year)
            assert svc >= prev - 1e-10, (
                f"Monotonicity violated at year {year}: "
                f"{svc} < {prev}"
            )
            prev = svc
            year += step

    def test_continuous_at_phase_boundaries(self):
        """No discontinuities at phase boundary transitions."""
        # Delay -> Pioneer
        boundary = _FOREST.maturation_delay
        before = succession_service(_FOREST, boundary - 0.01)
        after = succession_service(_FOREST, boundary + 0.01)
        assert abs(after - before) < 0.01

        # Pioneer -> Intermediate
        boundary = _FOREST.maturation_delay + _FOREST.pioneer_end_year
        before = succession_service(_FOREST, boundary - 0.01)
        after = succession_service(_FOREST, boundary + 0.01)
        assert abs(after - before) < 0.01

        # Intermediate -> Climax
        boundary = _FOREST.maturation_delay + _FOREST.intermediate_end_year
        before = succession_service(_FOREST, boundary - 0.01)
        after = succession_service(_FOREST, boundary + 0.01)
        assert abs(after - before) < 0.01

    def test_bounded_zero_to_one(self):
        """All outputs must be in [0, 1]."""
        for year_x10 in range(0, 1000):
            year = year_x10 / 10.0
            svc = succession_service(_FOREST, year)
            assert 0.0 <= svc <= 1.0 + 1e-10

    def test_oak_valley_faster_than_costa_brava(self):
        """Forest should deliver more services at year 30 than Costa Brava."""
        forest_svc = succession_service(_FOREST, 30.0)
        cb_svc = succession_service(_CB, 30.0)
        assert forest_svc > cb_svc

    def test_posidonia_slowest(self):
        """Posidonia should deliver least services at year 30."""
        forest_svc = succession_service(_FOREST, 30.0)
        pos_svc = succession_service(_POSIDONIA, 30.0)
        assert forest_svc > pos_svc


# ── Tests: get_succession_phase ────────────────────────────────────────────────


class TestGetSuccessionPhase:
    """Tests for phase identification."""

    def test_delay_phase(self):
        assert get_succession_phase(_FOREST, 0.0) == "delay"
        assert get_succession_phase(_FOREST, 1.5) == "delay"

    def test_pioneer_phase(self):
        assert get_succession_phase(_FOREST, 2.5) == "pioneer"
        assert get_succession_phase(_FOREST, 9.0) == "pioneer"

    def test_intermediate_phase(self):
        assert get_succession_phase(_FOREST, 11.0) == "intermediate"

    def test_climax_phase(self):
        assert get_succession_phase(_FOREST, 30.0) == "climax"
        assert get_succession_phase(_FOREST, 100.0) == "climax"


# ── Tests: find_years_to_threshold ─────────────────────────────────────────────


class TestFindYearsToThreshold:
    """Tests for milestone year computation."""

    def test_years_to_50pct_less_than_90pct(self):
        y50 = find_years_to_threshold(_FOREST, 0.50)
        y90 = find_years_to_threshold(_FOREST, 0.90)
        assert y50 < y90

    def test_posidonia_slower_than_forest(self):
        forest_50 = find_years_to_threshold(_FOREST, 0.50)
        posidonia_50 = find_years_to_threshold(_POSIDONIA, 0.50)
        assert posidonia_50 > forest_50


# ── Tests: maturation timeline ─────────────────────────────────────────────────


class TestMaturationTimeline:
    """Tests for the maturation timeline generation."""

    def test_timeline_length(self):
        """Timeline should have one step per year."""
        tl = compute_maturation_timeline(_FOREST, 1000.0, 60, 100)
        assert len(tl) == 60

    def test_cumulative_service_monotonic(self):
        """Cumulative service value must be monotonically non-decreasing."""
        tl = compute_maturation_timeline(_FOREST, 1000.0, 60, 100)
        for i in range(1, len(tl)):
            assert tl[i].cumulative_service_value >= tl[i - 1].cumulative_service_value

    def test_carbon_absorption_with_profile(self):
        """With carbon profile, carbon absorption should be computed."""
        tl = compute_maturation_timeline(_FOREST, 1000.0, 60, 100, _CARBON)
        assert tl[-1].cumulative_carbon_absorbed > 0

    def test_carbon_absorption_without_profile(self):
        """Without carbon profile, carbon absorption should be zero."""
        tl = compute_maturation_timeline(_FOREST, 1000.0, 60, 100, None)
        assert tl[-1].cumulative_carbon_absorbed == 0.0


# ── Tests: maturation gap ──────────────────────────────────────────────────────


class TestMaturationGap:
    """Tests for the maturation gap computation."""

    def test_gap_positive(self):
        """Maturation gap must be > 0 for any non-zero succession curve."""
        tl = compute_maturation_timeline(_FOREST, 100_000.0, 60, 100)
        gap = compute_maturation_gap(tl, 100_000.0)
        assert gap > 0

    def test_posidonia_gap_larger_than_forest(self):
        """Posidonia maturation gap should be much larger than forest."""
        tl_f = compute_maturation_timeline(_FOREST, 100_000.0, 60, 100)
        gap_f = compute_maturation_gap(tl_f, 100_000.0)

        tl_p = compute_maturation_timeline(_POSIDONIA, 100_000.0, 120, 100)
        gap_p = compute_maturation_gap(tl_p, 100_000.0)

        assert gap_p > gap_f
