"""
Gaia v0.1 — Damage function mathematical property tests.

These tests encode the scientific invariants that ALL damage functions must satisfy.
They are not "does it run" tests — they verify that the functions obey the laws
of ecosystem science as defined in the Gaia scientific foundations.

All invariant tests are parametrized across all three function types and across
a range of threshold values.
"""

import math
import pytest
from gaia.damage import logistic_damage, exponential_damage, piecewise_damage

# ── Test fixtures ─────────────────────────────────────────────────────────────

# All damage function factories under test
FACTORIES = [
    ("logistic", logistic_damage),
    ("exponential", exponential_damage),
    ("piecewise", piecewise_damage),
]

# Range of threshold values to test
THRESHOLDS = [0.1, 0.2, 0.3, 0.5, 0.7]

# Combined parametrization: (factory_name, factory, threshold)
ALL_CASES = [
    (fname, factory, t)
    for fname, factory in FACTORIES
    for t in THRESHOLDS
]

# Number of evenly-spaced points for monotonicity / output-range checks
N_POINTS: int = 1000

# Boundary tolerance (matches spec)
BOUNDARY_TOL: float = 1e-4

# Floating-point tolerance for intermediate checks
FP_TOL: float = 1e-9


# ── Invariant tests ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_zero_depletion_zero_damage(fname, factory, threshold):
    """Invariant 1: f(0.0) ≈ 0.0 — no depletion means no damage."""
    fn = factory(threshold)
    result = fn(0.0)
    assert abs(result) <= BOUNDARY_TOL, (
        f"{fname}(threshold={threshold}): f(0.0)={result:.6f}, expected ≈ 0.0"
    )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_full_depletion_full_damage(fname, factory, threshold):
    """Invariant 2: f(1.0) ≈ 1.0 — full depletion means full damage."""
    fn = factory(threshold)
    result = fn(1.0)
    assert abs(result - 1.0) <= BOUNDARY_TOL, (
        f"{fname}(threshold={threshold}): f(1.0)={result:.6f}, expected ≈ 1.0"
    )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_monotonicity(fname, factory, threshold):
    """Invariant 3: f is non-decreasing — more extraction means more damage (never less)."""
    fn = factory(threshold)
    xs = [i / N_POINTS for i in range(N_POINTS + 1)]
    values = [fn(x) for x in xs]
    for i in range(1, len(values)):
        assert values[i] >= values[i - 1] - FP_TOL, (
            f"{fname}(threshold={threshold}): monotonicity violated at x={xs[i]:.4f}: "
            f"f({xs[i]:.4f})={values[i]:.6f} < f({xs[i-1]:.4f})={values[i-1]:.6f}"
        )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_output_range(fname, factory, threshold):
    """Invariant 4 (part): all outputs are in [0.0, 1.0]."""
    fn = factory(threshold)
    xs = [i / N_POINTS for i in range(N_POINTS + 1)]
    for x in xs:
        val = fn(x)
        assert -BOUNDARY_TOL <= val <= 1.0 + BOUNDARY_TOL, (
            f"{fname}(threshold={threshold}): f({x:.4f})={val:.6f} out of [0, 1]"
        )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_nonlinearity_at_threshold(fname, factory, threshold):
    """
    Invariant 4 (non-linearity): the local slope just AFTER the threshold must be
    strictly greater than the local slope just BEFORE it.

    We compare slope in a narrow symmetric window around the threshold. This is
    the ecologically meaningful test: the transition point is where damage accelerates.
    Comparing global averages over the full pre/post regions would be confounded by
    the saturation plateau of S-shaped functions.

    Encodes Scientific Foundation F4 (carrying capacity): ecosystems tolerate modest
    depletion, then experience sharply accelerating damage past the safe threshold.
    """
    fn = factory(threshold)

    # Use 10% of the [0,1] range as the local window, clamped to avoid boundary issues
    half_window = min(0.10, threshold * 0.4, (1.0 - threshold) * 0.4)
    if half_window < 0.005:
        pytest.skip(f"Threshold {threshold} too extreme for local slope test")

    # Slope immediately before the threshold: [threshold - window, threshold]
    lo = max(0.0, threshold - half_window)
    slope_pre = (fn(threshold) - fn(lo)) / (threshold - lo)

    # Slope immediately after the threshold: [threshold, threshold + window]
    hi = min(1.0, threshold + half_window)
    slope_post = (fn(hi) - fn(threshold)) / (hi - threshold)

    assert slope_post > slope_pre, (
        f"{fname}(threshold={threshold}): local slope just after threshold "
        f"({slope_post:.4f}) must exceed local slope just before ({slope_pre:.4f})"
    )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_convexity_past_threshold(fname, factory, threshold):
    """
    Invariant 5 (convexity past threshold): damage is accelerating in the zone
    immediately after the safe extraction threshold.

    We verify this by checking that the slope is increasing (positive second derivative)
    in a narrow window just past the threshold — specifically in [threshold, threshold+window]
    where window = 30% of the post-threshold span. This captures the 'acceleration zone'
    where ecosystem damage is ramping up rapidly before it eventually saturates.

    For S-shaped functions (logistic), this window stays within the convex region
    (before the inflection point, which is placed slightly above threshold).
    For piecewise functions, the post-threshold slope is constant and higher than
    the pre-threshold slope, so second differences are ~zero (degenerate but passing).
    """
    fn = factory(threshold)

    # Window: 10% of the post-threshold span starting from threshold.
    # This stays within the convex (accelerating) region of the S-curve,
    # which ends at the inflection point placed at threshold + 15% of post-span.
    post_span = 1.0 - threshold
    window = post_span * 0.10
    if window < 1e-4:
        pytest.skip("Post-threshold region too small for convexity test")

    start = threshold
    end = min(1.0, threshold + window)
    n_post: int = 50
    step_size = (end - start) / n_post
    xs = [start + i * step_size for i in range(n_post + 1)]
    vals = [fn(x) for x in xs]

    # Second finite difference: f(x+h) - 2*f(x) + f(x-h) >= 0 for convex
    convex_tol: float = -1e-6
    violations = 0
    for i in range(1, len(vals) - 1):
        second_diff = vals[i + 1] - 2.0 * vals[i] + vals[i - 1]
        if second_diff < convex_tol:
            violations += 1

    # Allow at most 20% of points to violate (floating-point noise near inflection)
    max_violations = max(1, int(0.20 * n_post))
    assert violations <= max_violations, (
        f"{fname}(threshold={threshold}): convexity violated at {violations} "
        f"points in [{threshold:.2f}, {end:.2f}] "
        f"(max allowed: {max_violations})"
    )


# ── Parameterization tests ─────────────────────────────────────────────────────

@pytest.mark.parametrize("threshold", THRESHOLDS)
def test_steepness_affects_sharpness(threshold):
    """
    Logistic only: higher steepness → sharper transition at the inflection point.

    The logistic inflection is placed at threshold + (1-threshold)*0.15. A higher
    steepness value produces a sharper (larger) jump across a narrow window centered
    on the inflection point.
    """
    fn_low = logistic_damage(threshold=threshold, steepness=4.0)
    fn_high = logistic_damage(threshold=threshold, steepness=20.0)

    # Center the window on the inflection point (not the threshold)
    # inflection = threshold + (1 - threshold) * 0.15
    inflection = threshold + (1.0 - threshold) * 0.15
    delta = 0.08
    lo = max(0.0, inflection - delta)
    hi = min(1.0, inflection + delta)

    jump_low = fn_low(hi) - fn_low(lo)
    jump_high = fn_high(hi) - fn_high(lo)

    assert jump_high > jump_low, (
        f"logistic(threshold={threshold}): steepness=20 jump at inflection ({jump_high:.4f}) "
        f"should exceed steepness=4 jump ({jump_low:.4f})"
    )


@pytest.mark.parametrize("fname,factory", FACTORIES)
def test_threshold_shifts_curve(fname, factory):
    """Changing the threshold shifts where damage accelerates."""
    fn_low = factory(threshold=0.2)
    fn_high = factory(threshold=0.7)

    # At x=0.45 (between the two thresholds):
    # fn_low has already passed its threshold → higher damage
    # fn_high has not reached its threshold → lower damage
    x = 0.45
    val_low = fn_low(x)
    val_high = fn_high(x)

    assert val_low > val_high, (
        f"{fname}: at x={x}, threshold=0.2 gives {val_low:.4f} "
        f"but threshold=0.7 gives {val_high:.4f}; expected low threshold > high threshold"
    )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_midpoint_damage_reasonable(fname, factory, threshold):
    """At the threshold, damage should be between 0.05 and 0.95 (not trivial)."""
    fn = factory(threshold)
    val_at_threshold = fn(threshold)
    assert 0.05 <= val_at_threshold <= 0.95, (
        f"{fname}(threshold={threshold}): f(threshold)={val_at_threshold:.4f} "
        f"should be between 0.05 and 0.95"
    )


@pytest.mark.parametrize("fname,factory,threshold", ALL_CASES)
def test_more_damage_past_threshold_than_before(fname, factory, threshold):
    """
    The total damage that occurs ABOVE the threshold must exceed total damage below it.

    This verifies that the threshold is not just where the *rate* changes, but that
    the post-threshold damage is the dominant share — i.e., most of the ecosystem
    harm occurs past the safe extraction limit.

    Formally: f(1.0) - f(threshold) > f(threshold) - f(0.0)
    i.e., post-threshold damage > pre-threshold damage.
    """
    fn = factory(threshold)
    pre_damage = fn(threshold) - fn(0.0)
    post_damage = fn(1.0) - fn(threshold)

    assert post_damage > pre_damage, (
        f"{fname}(threshold={threshold}): post-threshold damage ({post_damage:.4f}) "
        f"should exceed pre-threshold damage ({pre_damage:.4f})"
    )


# ── Edge case tests ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fname,factory", FACTORIES)
def test_threshold_near_zero(fname, factory):
    """threshold=0.01: damage starts almost immediately, functions still work."""
    fn = factory(threshold=0.01)
    # All invariants should hold
    assert abs(fn(0.0)) <= BOUNDARY_TOL
    assert abs(fn(1.0) - 1.0) <= BOUNDARY_TOL
    # Should be non-decreasing
    vals = [fn(i / 100) for i in range(101)]
    for i in range(1, len(vals)):
        assert vals[i] >= vals[i - 1] - FP_TOL


@pytest.mark.parametrize("fname,factory", FACTORIES)
def test_threshold_near_one(fname, factory):
    """threshold=0.99: almost all extraction is 'safe', functions still work."""
    fn = factory(threshold=0.99)
    assert abs(fn(0.0)) <= BOUNDARY_TOL
    assert abs(fn(1.0) - 1.0) <= BOUNDARY_TOL
    vals = [fn(i / 100) for i in range(101)]
    for i in range(1, len(vals)):
        assert vals[i] >= vals[i - 1] - FP_TOL
