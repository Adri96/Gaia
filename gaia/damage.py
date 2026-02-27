"""
Gaia v0.1 — Damage function library.

All damage functions are factories that accept configuration parameters and
return a DamageFunc: a callable (depletion_ratio: float) -> (damage_ratio: float).

Scientific invariants that every damage function must satisfy:
    1. f(0.0) ≈ 0.0  (no depletion → no damage)
    2. f(1.0) ≈ 1.0  (full depletion → full damage)
    3. Monotonicity: f(a) <= f(b) for all a < b
    4. Non-linearity: avg slope in (threshold, 1.0] > avg slope in [0.0, threshold)
    5. Convexity past threshold: second finite difference is positive post-threshold

All functions are float -> float in the hot path — Cython-compatible.
"""

import math
from typing import Callable

DamageFunc = Callable[[float], float]


def logistic_damage(threshold: float, steepness: float = 12.0) -> DamageFunc:
    """
    Logistic (sigmoid) damage function — the primary and most ecologically grounded option.

    Produces an S-curve where damage is low before the threshold, accelerates sharply
    around it, and saturates toward 1.0. This shape reflects carrying capacity dynamics
    (Scientific Foundation F4): ecosystems tolerate modest depletion, then collapse
    non-linearly past the safe extraction threshold.

    The inflection point (maximum slope, point of maximum acceleration) is placed
    slightly above the safe threshold — specifically at:
        inflection = threshold + (1 - threshold) * 0.15

    This ensures the post-threshold region begins in the convex (accelerating) part
    of the S-curve, so damage is clearly accelerating for a meaningful range past the
    safe extraction limit, before eventually saturating toward 1.0.

    Formula:
        inflection = threshold + (1 - threshold) * 0.15
        raw(x) = 1 / (1 + exp(-steepness * (x - inflection)))
        f(x)   = (raw(x) - raw(0)) / (raw(1) - raw(0))

    Normalization ensures exact boundary conditions: f(0.0) = 0.0, f(1.0) = 1.0.

    Args:
        threshold: Safe extraction ratio. Damage begins accelerating above this point.
                   The inflection is placed just above it for scientific accuracy.
        steepness: Sharpness of the S-curve transition. Higher = sharper knee.
                   Default 12.0 gives a clear but not extreme inflection.
                   [PLACEHOLDER — pending scientific calibration]

    Returns:
        DamageFunc mapping depletion_ratio in [0, 1] to damage_ratio in [0, 1].
    """
    # Place the inflection 15% into the post-threshold range so that the
    # post-threshold region starts in the convex (still-accelerating) part
    # of the S-curve. This encodes that damage accelerates starting just past
    # the safe threshold and peaks slightly above it.
    inflection: float = threshold + (1.0 - threshold) * 0.15

    # Pre-compute normalization anchors at construction time (not in hot path)
    raw_0: float = 1.0 / (1.0 + math.exp(-steepness * (0.0 - inflection)))
    raw_1: float = 1.0 / (1.0 + math.exp(-steepness * (1.0 - inflection)))
    span: float = raw_1 - raw_0

    def _logistic(depletion_ratio: float) -> float:
        raw: float = 1.0 / (1.0 + math.exp(-steepness * (depletion_ratio - inflection)))
        return (raw - raw_0) / span

    return _logistic


def exponential_damage(threshold: float, base: float = 2.0) -> DamageFunc:
    """
    Exponential damage function.

    Damage grows exponentially — slow at first, accelerating continuously.
    The threshold parameter shifts the parameterization so that the acceleration
    becomes prominent around the threshold region.

    Formula (before normalization):
        raw(x) = base^(x / (1 - threshold)) - 1   for x in [0, 1]

    Normalization ensures f(0.0) = 0.0, f(1.0) = 1.0.

    Args:
        threshold: Influences where in [0, 1] the curve is shaped to accelerate.
                   Higher threshold → slower initial growth, faster post-threshold growth.
                   [PLACEHOLDER — pending scientific calibration]
        base: Exponential base. Must be > 1. Default 2.0.
              [PLACEHOLDER — pending scientific calibration]

    Returns:
        DamageFunc mapping depletion_ratio in [0, 1] to damage_ratio in [0, 1].
    """
    # Scale exponent so that the curve shape respects the threshold region.
    # We stretch the x-axis by 1/(1-threshold) so that at x=threshold the
    # exponent is threshold/(1-threshold), which gives a shallow early curve
    # and a steep post-threshold curve.
    scale: float = 1.0 / max(1.0 - threshold, 1e-9)

    # Normalization: raw(0) = base^0 - 1 = 0 (exact), raw(1) = base^scale - 1
    raw_1: float = (base ** scale) - 1.0

    def _exponential(depletion_ratio: float) -> float:
        raw: float = (base ** (depletion_ratio * scale)) - 1.0
        return raw / raw_1

    return _exponential


def piecewise_damage(threshold: float, pre_slope_ratio: float = None) -> DamageFunc:
    """
    Piecewise linear damage function with two segments.

    Two linear segments with different slopes:
        - Below threshold: gentle slope covering `pre_slope_ratio` of total damage.
        - Above threshold: steep slope covering `1 - pre_slope_ratio` of total damage.

    This is the simplest function that satisfies all invariants. Useful for testing
    and for cases where the exact curve shape is unknown but the threshold is
    well-established.

    Formula:
        if x <= threshold:
            f(x) = (pre_slope_ratio / threshold) * x
        else:
            f(x) = pre_slope_ratio + ((1 - pre_slope_ratio) / (1 - threshold)) * (x - threshold)

    Exact boundary conditions by construction: f(0.0) = 0.0, f(1.0) = 1.0.

    The `pre_slope_ratio` is constrained to be less than `threshold` to guarantee
    that the post-threshold slope always exceeds the pre-threshold slope — i.e.,
    damage always accelerates past the safe extraction limit. This is a mathematical
    encoding of Scientific Foundation F4 (carrying capacity).

    Args:
        threshold: Depletion ratio where the slope changes. Must be in (0.0, 1.0).
        pre_slope_ratio: Fraction of total damage (0.0 to 1.0) that occurs before
                         the threshold. Defaults to min(0.2, threshold * 0.5), which
                         guarantees post_slope > pre_slope for all threshold values.
                         [PLACEHOLDER — pending scientific calibration]

    Returns:
        DamageFunc mapping depletion_ratio in [0, 1] to damage_ratio in [0, 1].
    """
    # Default pre_slope_ratio: constrained to threshold * 0.5 so that the post-threshold
    # slope always exceeds the pre-threshold slope for any valid threshold value.
    # Mathematical proof: post_slope > pre_slope iff (1-r)/(1-t) > r/t iff t > r.
    # Setting r = min(0.2, t/2) ensures t > r always holds.
    if pre_slope_ratio is None:
        pre_slope_ratio = min(0.2, threshold * 0.5)

    # Pre-compute slopes at construction time
    pre_slope: float = pre_slope_ratio / max(threshold, 1e-9)
    post_slope: float = (1.0 - pre_slope_ratio) / max(1.0 - threshold, 1e-9)

    def _piecewise(depletion_ratio: float) -> float:
        if depletion_ratio <= threshold:
            return pre_slope * depletion_ratio
        else:
            return pre_slope_ratio + post_slope * (depletion_ratio - threshold)

    return _piecewise
