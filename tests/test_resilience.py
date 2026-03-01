"""
Tests for gaia.resilience — Resilience zone computation.

Covers zone identification, confidence interpolation, irreversibility
warning, and confidence band calculation.
"""

import pytest

from gaia.models import ResilienceConfig
from gaia.resilience import compute_confidence_band, compute_resilience_zone


# ── Test fixtures ──────────────────────────────────────────────────────────────

_CONFIG = ResilienceConfig(
    warning_zone_width=0.10,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.50,
)

# threshold=0.30 means 30% can be extracted → 70% must remain
# safe_remaining = 0.70
# warning_start = 0.70 + 0.10 = 0.80
# green: remaining > 0.80
# yellow: 0.70 < remaining <= 0.80
# red: remaining <= 0.70
_THRESHOLD = 0.30


# ── Tests: zone computation ───────────────────────────────────────────────────


class TestComputeResilienceZone:
    """Tests for compute_resilience_zone."""

    def test_green_zone_above_warning(self):
        """Well above the threshold → green zone."""
        zone, confidence, irrev = compute_resilience_zone(
            0.90, _THRESHOLD, _CONFIG
        )
        assert zone == "green"
        assert confidence == pytest.approx(0.90)
        assert irrev is False

    def test_yellow_zone_between_warning_and_threshold(self):
        """Between warning and threshold → yellow zone."""
        zone, confidence, irrev = compute_resilience_zone(
            0.75, _THRESHOLD, _CONFIG
        )
        assert zone == "yellow"
        assert 0.60 <= confidence <= 0.90

    def test_red_zone_below_threshold(self):
        """Below the safe threshold → red zone."""
        zone, confidence, irrev = compute_resilience_zone(
            0.60, _THRESHOLD, _CONFIG
        )
        assert zone == "red"
        assert confidence <= 0.60

    def test_confidence_monotonically_decreasing(self):
        """Confidence must decrease as remaining fraction decreases."""
        confidences = []
        for remaining_x100 in range(95, 40, -5):
            remaining = remaining_x100 / 100.0
            _, conf, _ = compute_resilience_zone(remaining, _THRESHOLD, _CONFIG)
            confidences.append(conf)
        for i in range(1, len(confidences)):
            assert confidences[i] <= confidences[i - 1] + 1e-6, (
                f"Confidence not decreasing at step {i}: "
                f"{confidences[i]} > {confidences[i - 1]}"
            )

    def test_continuous_at_zone_boundaries(self):
        """No jumps in confidence at green→yellow and yellow→red boundaries."""
        # Green→Yellow boundary at remaining=0.80
        _, conf_before, _ = compute_resilience_zone(0.801, _THRESHOLD, _CONFIG)
        _, conf_after, _ = compute_resilience_zone(0.799, _THRESHOLD, _CONFIG)
        assert abs(conf_before - conf_after) < 0.05

        # Yellow→Red boundary at remaining=0.70
        _, conf_before, _ = compute_resilience_zone(0.701, _THRESHOLD, _CONFIG)
        _, conf_after, _ = compute_resilience_zone(0.699, _THRESHOLD, _CONFIG)
        assert abs(conf_before - conf_after) < 0.05

    def test_irreversibility_warning_triggered(self):
        """Irreversibility warning at configured depletion ratio."""
        # irreversibility_flag_ratio=0.50, depletion > 0.50 → remaining < 0.50
        _, _, irrev = compute_resilience_zone(0.49, _THRESHOLD, _CONFIG)
        assert irrev is True

    def test_no_irreversibility_below_flag(self):
        """No irreversibility warning when depletion below flag ratio."""
        _, _, irrev = compute_resilience_zone(0.60, _THRESHOLD, _CONFIG)
        assert irrev is False


# ── Tests: wider warning zone ─────────────────────────────────────────────────


class TestWiderWarningZone:
    """Posidonia-like wider warning zone (0.15)."""

    def test_posidonia_wider_warning_than_forest(self):
        """Wider warning zone → yellow zone starts earlier."""
        posidonia_config = ResilienceConfig(
            warning_zone_width=0.15,
            irreversibility_flag_ratio=0.40,
        )
        # threshold=0.20, safe_remaining=0.80, warning_start=0.95
        zone_p, _, _ = compute_resilience_zone(0.92, 0.20, posidonia_config)

        # Same remaining with forest config
        zone_f, _, _ = compute_resilience_zone(0.92, 0.30, _CONFIG)

        # Posidonia should be in yellow, forest should be in green
        assert zone_p == "yellow"
        assert zone_f == "green"


# ── Tests: confidence band ────────────────────────────────────────────────────


class TestConfidenceBand:
    """Tests for compute_confidence_band."""

    def test_band_at_full_confidence(self):
        """At 100% confidence, band should be [cost, cost]."""
        lower, upper = compute_confidence_band(1000.0, 1.0)
        assert lower == pytest.approx(1000.0)
        assert upper == pytest.approx(1000.0)

    def test_band_widens_with_lower_confidence(self):
        """Lower confidence → wider band."""
        lower_90, upper_90 = compute_confidence_band(1000.0, 0.90)
        lower_60, upper_60 = compute_confidence_band(1000.0, 0.60)
        width_90 = upper_90 - lower_90
        width_60 = upper_60 - lower_60
        assert width_60 > width_90

    def test_band_symmetric(self):
        """Band should be symmetric around the cost."""
        lower, upper = compute_confidence_band(1000.0, 0.80)
        mid = (lower + upper) / 2.0
        assert mid == pytest.approx(1000.0)
