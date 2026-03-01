"""
Gaia v0.4 — Resilience zone computation.

Implements the three-zone resilience model (Foundation F7):
    - Green zone: ecosystem very likely resilient, high model confidence
    - Yellow zone: resilience uncertain, degraded confidence
    - Red zone: resilience likely compromised, low confidence

Confidence interpolates linearly within zones:
    - Green: fixed at confidence_green
    - Yellow: linearly from confidence_green to confidence_yellow
    - Red: linearly from confidence_yellow to confidence_red

All functions use primitive types for Cython compatibility.
No third-party dependencies.

Scientific foundations used: F7 (Resilience Is a System Property).
"""

from gaia.models import ResilienceConfig


def compute_resilience_zone(
    remaining_fraction: float,
    threshold: float,
    config: ResilienceConfig,
) -> tuple:
    """Compute the resilience zone, confidence, and irreversibility warning.

    Zones:
        Green:  remaining_fraction > threshold + warning_zone_width
        Yellow: threshold < remaining_fraction <= threshold + warning_zone_width
        Red:    remaining_fraction <= threshold

    Args:
        remaining_fraction: Fraction of resource remaining (1.0 - depletion_ratio).
        threshold: The safe extraction threshold (resource.safe_threshold_ratio).
            NOTE: this is the fraction that should REMAIN, not be extracted.
            A threshold of 0.30 means 30% must remain (70% can be extracted).
            The resource is at risk when remaining_fraction < (1 - threshold).
            HOWEVER, in the spec the threshold represents the fraction that can
            be extracted, so we convert: safe_remaining = 1.0 - threshold.
        config: ResilienceConfig with zone widths and confidence values.

    Returns:
        Tuple of (zone: str, confidence: float, irreversibility_warning: bool).
    """
    # Convert extraction threshold to remaining threshold
    # threshold=0.30 means 30% can be extracted safely, so 70% must remain
    safe_remaining: float = 1.0 - threshold
    warning_start: float = safe_remaining + config.warning_zone_width
    depletion_ratio: float = 1.0 - remaining_fraction

    if remaining_fraction > warning_start:
        zone: str = "green"
        confidence: float = config.confidence_green
    elif remaining_fraction > safe_remaining:
        zone = "yellow"
        # Linearly interpolate confidence from green to yellow across warning zone
        if config.warning_zone_width > 0.0:
            t: float = (warning_start - remaining_fraction) / config.warning_zone_width
            confidence = config.confidence_green - t * (
                config.confidence_green - config.confidence_yellow
            )
        else:
            confidence = config.confidence_yellow
    else:
        zone = "red"
        # Linearly interpolate from yellow to red based on how far past threshold
        if safe_remaining > 0.0:
            t = min(1.0, (safe_remaining - remaining_fraction) / safe_remaining)
            confidence = config.confidence_yellow - t * (
                config.confidence_yellow - config.confidence_red
            )
        else:
            confidence = config.confidence_red

    irreversibility: bool = depletion_ratio > config.irreversibility_flag_ratio

    return (zone, confidence, irreversibility)


def compute_confidence_band(
    cost: float,
    confidence: float,
) -> tuple:
    """Compute confidence-adjusted cost band.

    band = cost × (1 ± (1 - confidence))

    This is a simple heuristic, not a statistical confidence interval.
    It widens as confidence drops, indicating that the model's precision
    degrades in yellow and red zones.

    Args:
        cost: Point estimate of the externality cost (€).
        confidence: Model confidence (0.0 to 1.0).

    Returns:
        Tuple of (lower_bound, upper_bound) in €.
    """
    uncertainty: float = 1.0 - confidence
    lower: float = cost * (1.0 - uncertainty)
    upper: float = cost * (1.0 + uncertainty)
    return (lower, upper)
