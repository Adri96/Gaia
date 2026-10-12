"""
Gaia v0.1 — Damage function library.

All damage functions are factories that accept configuration parameters and
return a DamageFunc: a callable (depletion_ratio: float) -> (damage_ratio: float).

Scientific invariants that every damage function must satisfy (checked at
run time by gaia.validation.validate_damage_function, from validate_ecosystem):
    1. f(0.0) ≈ 0.0  (no depletion → no damage)
    2. f(1.0) ≈ 1.0  (full depletion → full damage)
    3. Finite output in [0.0, 1.0] everywhere on [0, 1]
    4. Monotonicity: f(a) <= f(b) for all a < b
    5. Non-linearity: the local slope just after the threshold exceeds the
       local slope just before it (damage accelerates at the threshold;
       global averages would be confounded by the saturation plateau)
    6. Convexity just past the threshold: second finite differences are
       non-negative over [threshold, threshold + 10% of the post-threshold
       span] (a logistic curve is convex up to its inflection, placed 15%
       into that span, and saturates after it)

Every factory records its threshold as a ``threshold`` attribute of the
function it returns, so invariants 5 and 6 are checked at the agent's own
threshold (the resource's safe threshold for functions without one).

The factories reject parameters that would make the curve undefined or break
these invariants (ValueError), instead of failing with ZeroDivisionError or
OverflowError at the first evaluation.

All functions are float -> float.

Kernel tags:
    Every factory attaches a ``kernel`` attribute to the function it returns:
    a 5-tuple ``(kind, p1, p2, p3, p4)`` holding the pre-computed parameters.
    gaia.ecosystem_io reads it to write a curve back to a case file (and
    checks that rebuilding the curve gives the same tag).
"""

import math
from typing import Callable, Optional, Tuple

DamageFunc = Callable[[float], float]
Kernel = Tuple[int, float, float, float, float]

# Kernel kinds
KERNEL_LOGISTIC: int = 0     # (inflection, raw_0, span, steepness)
KERNEL_EXPONENTIAL: int = 1  # (scale, raw_1, base, 0.0)
KERNEL_PIECEWISE: int = 2    # (threshold, pre_slope, post_slope, pre_slope_ratio)
KERNEL_THRESHOLD_LOGISTIC: int = 3  # (inflection, raw_t, span, steepness)
KERNEL_THRESHOLD_EXPONENTIAL: int = 4  # (threshold, scale, raw_1, base)


def _require_threshold(threshold: float, factory: str) -> None:
    """ValueError unless ``threshold`` is a finite number in (0, 1)."""
    if not (isinstance(threshold, (int, float)) and math.isfinite(threshold)
            and 0.0 < threshold < 1.0):
        raise ValueError(f"{factory}: threshold must be in (0.0, 1.0), got {threshold!r}")


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

    Raises:
        ValueError: If threshold is not in (0, 1) or steepness is not a
            finite number > 0 (steepness 0 is a flat line: 0/0).
    """
    _require_threshold(threshold, "logistic_damage")
    if not (isinstance(steepness, (int, float)) and math.isfinite(steepness)
            and steepness > 0.0):
        raise ValueError(
            f"logistic_damage: steepness must be a finite number > 0, got {steepness!r}"
        )
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

    _logistic.threshold = threshold  # type: ignore[attr-defined]
    _logistic.kernel = (KERNEL_LOGISTIC, inflection, raw_0, span, steepness)  # type: ignore[attr-defined]
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

    Raises:
        ValueError: If threshold is not in (0, 1), base is not a finite
            number > 1 (base 1 is flat: 0/0), or base^(1/(1 − threshold))
            overflows a float.
    """
    _require_threshold(threshold, "exponential_damage")
    if not (isinstance(base, (int, float)) and math.isfinite(base) and base > 1.0):
        raise ValueError(f"exponential_damage: base must be a finite number > 1, got {base!r}")
    # Scale exponent so that the curve shape respects the threshold region.
    # We stretch the x-axis by 1/(1-threshold) so that at x=threshold the
    # exponent is threshold/(1-threshold), which gives a shallow early curve
    # and a steep post-threshold curve.
    scale: float = 1.0 / (1.0 - threshold)

    # Normalization: raw(0) = base^0 - 1 = 0 (exact), raw(1) = base^scale - 1
    try:
        raw_1: float = (base ** scale) - 1.0
    except OverflowError:
        raise ValueError(
            f"exponential_damage: base^(1/(1 - threshold)) = {base}^{scale:g} "
            f"overflows; lower the base or the threshold"
        ) from None

    def _exponential(depletion_ratio: float) -> float:
        raw: float = (base ** (depletion_ratio * scale)) - 1.0
        return raw / raw_1

    _exponential.threshold = threshold  # type: ignore[attr-defined]
    _exponential.kernel = (KERNEL_EXPONENTIAL, scale, raw_1, base, 0.0)  # type: ignore[attr-defined]
    return _exponential


def piecewise_damage(threshold: float, pre_slope_ratio: Optional[float] = None) -> DamageFunc:
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

    Raises:
        ValueError: If threshold is not in (0, 1) or pre_slope_ratio is not
            in [0, threshold) (otherwise damage would not accelerate past
            the threshold).
    """
    _require_threshold(threshold, "piecewise_damage")
    # Default pre_slope_ratio: constrained to threshold * 0.5 so that the post-threshold
    # slope always exceeds the pre-threshold slope for any valid threshold value.
    # Mathematical proof: post_slope > pre_slope iff (1-r)/(1-t) > r/t iff t > r.
    # Setting r = min(0.2, t/2) ensures t > r always holds.
    if pre_slope_ratio is None:
        pre_slope_ratio = min(0.2, threshold * 0.5)
    elif not (isinstance(pre_slope_ratio, (int, float)) and math.isfinite(pre_slope_ratio)
              and 0.0 <= pre_slope_ratio < threshold):
        raise ValueError(
            f"piecewise_damage: pre_slope_ratio must be in [0.0, threshold={threshold}), "
            f"got {pre_slope_ratio!r}"
        )

    # Pre-compute slopes at construction time
    pre_slope: float = pre_slope_ratio / threshold
    post_slope: float = (1.0 - pre_slope_ratio) / (1.0 - threshold)

    def _piecewise(depletion_ratio: float) -> float:
        if depletion_ratio <= threshold:
            return pre_slope * depletion_ratio
        else:
            return pre_slope_ratio + post_slope * (depletion_ratio - threshold)

    _piecewise.threshold = threshold  # type: ignore[attr-defined]
    _piecewise.kernel = (KERNEL_PIECEWISE, threshold, pre_slope, post_slope, pre_slope_ratio)  # type: ignore[attr-defined]
    return _piecewise


def threshold_logistic_damage(threshold: float, steepness: float = 12.0) -> DamageFunc:
    """
    Logistic damage that starts at the threshold: zero below it (Step 8c.3).

    The degradation curve of the "area_loss" damage model
    (gaia.propagation.area_loss_damages), where each unit lost takes its
    own services (the linear part) and this curve describes how the
    REMAINING resource degrades once depletion passes the safe threshold
    (fragmentation, loss of structure). Being exactly zero below the
    threshold, it has zero slope at small losses, so the total damage
    D + (1 − D) × degradation has slope 1 there: the marginal unit costs
    its average value, as in a linear benefit transfer.

    Formula (same inflection rule as logistic_damage):
        inflection = threshold + (1 - threshold) * 0.15
        raw(x) = 1 / (1 + exp(-steepness * (x - inflection)))
        f(x)   = 0                                   for x <= threshold
        f(x)   = (raw(x) - raw(t)) / (raw(1) - raw(t))  for x > threshold

    f(0) = 0, f(1) = 1, monotone; the slope jumps from 0 to a positive
    value at the threshold (invariant 5) and the curve is convex up to the
    inflection, beyond the convexity window (invariant 6).

    Args:
        threshold: Depletion at which degradation starts, in (0, 1).
        steepness: Sharpness of the S-curve past the threshold
            [PLACEHOLDER — pending scientific calibration].

    Raises:
        ValueError: If threshold is not in (0, 1) or steepness is not a
            finite number > 0.
    """
    _require_threshold(threshold, "threshold_logistic_damage")
    if not (isinstance(steepness, (int, float)) and math.isfinite(steepness)
            and steepness > 0.0):
        raise ValueError(
            f"threshold_logistic_damage: steepness must be a finite number > 0, "
            f"got {steepness!r}"
        )
    inflection: float = threshold + (1.0 - threshold) * 0.15
    raw_t: float = 1.0 / (1.0 + math.exp(-steepness * (threshold - inflection)))
    raw_1: float = 1.0 / (1.0 + math.exp(-steepness * (1.0 - inflection)))
    span: float = raw_1 - raw_t

    def _threshold_logistic(depletion_ratio: float) -> float:
        if depletion_ratio <= threshold:
            return 0.0
        raw: float = 1.0 / (1.0 + math.exp(-steepness * (depletion_ratio - inflection)))
        return (raw - raw_t) / span

    _threshold_logistic.threshold = threshold  # type: ignore[attr-defined]
    _threshold_logistic.kernel = (  # type: ignore[attr-defined]
        KERNEL_THRESHOLD_LOGISTIC, inflection, raw_t, span, steepness,
    )
    return _threshold_logistic


def threshold_exponential_damage(threshold: float, base: float = 2.0) -> DamageFunc:
    """
    Exponential damage that starts at the threshold: zero below it (Step 8d.1).

    The "area_loss" counterpart of exponential_damage, for an agent whose
    degradation has no plateau (Costa Brava's fire feedback): the REMAINING
    resource is untouched up to the safe threshold, then degrades
    exponentially over the post-threshold span. Being exactly zero below the
    threshold it keeps the damage D + (1 − D) × degradation at slope 1 for
    small losses (gaia.propagation.area_loss_damages).

    Formula:
        f(x) = 0                                              for x <= threshold
        f(x) = (base^((x - t) / (1 - t)) - 1) / (base - 1)    for x > threshold

    f(0) = 0, f(1) = 1, monotone and convex past the threshold, where the
    slope jumps from 0 to ln(base) / ((1 - t)(base - 1)) (invariants 5, 6).

    Args:
        threshold: Depletion at which degradation starts, in (0, 1).
        base: Exponential base, a finite number > 1
            [PLACEHOLDER — pending scientific calibration].

    Raises:
        ValueError: If threshold is not in (0, 1) or base is not a finite
            number > 1.
    """
    _require_threshold(threshold, "threshold_exponential_damage")
    if not (isinstance(base, (int, float)) and math.isfinite(base) and base > 1.0):
        raise ValueError(
            f"threshold_exponential_damage: base must be a finite number > 1, got {base!r}"
        )
    scale: float = 1.0 / (1.0 - threshold)
    raw_1: float = base - 1.0

    def _threshold_exponential(depletion_ratio: float) -> float:
        if depletion_ratio <= threshold:
            return 0.0
        return (base ** ((depletion_ratio - threshold) * scale) - 1.0) / raw_1

    _threshold_exponential.threshold = threshold  # type: ignore[attr-defined]
    _threshold_exponential.kernel = (  # type: ignore[attr-defined]
        KERNEL_THRESHOLD_EXPONENTIAL, threshold, scale, raw_1, base,
    )
    return _threshold_exponential
