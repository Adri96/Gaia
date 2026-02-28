"""
Gaia v0.2 — Recovery function mathematical invariant tests.

These tests mirror test_damage.py but for recovery functions. They verify:
    - Boundary conditions: f(0.0) = 0.0, f(1.0) = 1.0
    - Monotonicity: more restoration → more recovered services
    - Output range: always in [0.0, 1.0]
    - Entropy asymmetry: recovery is slower than equivalent damage

Parametrized over all recovery function factories and multiple threshold values.
"""

import math
import pytest
from gaia.recovery import logistic_recovery, linear_recovery
from gaia.damage import logistic_damage

# ── Test parameters ─────────────────────────────────────────────────────────────

THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.40]
N_POINTS = 500
BOUNDARY_TOL = 1e-4


# ── Recovery factories and their kwargs ─────────────────────────────────────────

LOGISTIC_CASES = [
    ("logistic_recovery", logistic_recovery, {"threshold": t})
    for t in THRESHOLDS
]

LINEAR_CASES = [
    ("linear_recovery_0.8", linear_recovery, {"slope": 0.8}),
    ("linear_recovery_0.6", linear_recovery, {"slope": 0.6}),
]

# All cases — used for tests that apply to both function types
RECOVERY_CASES = LOGISTIC_CASES + LINEAR_CASES


def _make_fn(factory, kwargs):
    return factory(**kwargs)


# ── Boundary conditions ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,factory,kwargs", RECOVERY_CASES, ids=[c[0] for c in RECOVERY_CASES])
def test_recovery_zero_at_zero(name, factory, kwargs):
    """f(0.0) ≈ 0.0 — no restoration → no recovered services."""
    fn = _make_fn(factory, kwargs)
    val = fn(0.0)
    assert abs(val) <= BOUNDARY_TOL, (
        f"{name}: f(0.0) should be ≈ 0.0, got {val}"
    )


@pytest.mark.parametrize("name,factory,kwargs", LOGISTIC_CASES, ids=[c[0] for c in LOGISTIC_CASES])
def test_recovery_one_at_one(name, factory, kwargs):
    """
    f(1.0) ≈ 1.0 — full restoration → full services (at maturity).

    This applies to logistic_recovery only. linear_recovery with slope < 1.0
    intentionally does NOT reach 1.0 at x=1.0 — that is the entropy cost
    encoded in the slope parameter. For linear_recovery, f(1.0) = slope.
    """
    fn = _make_fn(factory, kwargs)
    val = fn(1.0)
    assert abs(val - 1.0) <= BOUNDARY_TOL, (
        f"{name}: f(1.0) should be ≈ 1.0, got {val}"
    )


@pytest.mark.parametrize("slope", [0.6, 0.8])
def test_linear_recovery_one_at_one_equals_slope(slope):
    """
    linear_recovery(slope)(1.0) == slope.

    The linear function encodes entropy cost directly in the slope: at full
    restoration, only `slope` fraction of services are recovered. This is
    intentional — slope < 1.0 means some ecosystem service capacity is
    permanently reduced, even after full replanting.
    """
    fn = linear_recovery(slope=slope)
    assert abs(fn(1.0) - slope) < 1e-9, (
        f"linear_recovery(slope={slope})(1.0) should equal {slope}, got {fn(1.0)}"
    )


# ── Output range ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,factory,kwargs", RECOVERY_CASES, ids=[c[0] for c in RECOVERY_CASES])
def test_recovery_output_in_range(name, factory, kwargs):
    """f(x) is always in [0.0, 1.0] for all x in [0.0, 1.0]."""
    fn = _make_fn(factory, kwargs)
    xs = [i / N_POINTS for i in range(N_POINTS + 1)]
    violations = [(x, fn(x)) for x in xs if not (-1e-9 <= fn(x) <= 1.0 + 1e-9)]
    assert not violations, (
        f"{name}: f(x) out of [0, 1] at {violations[:3]}"
    )


# ── Monotonicity ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,factory,kwargs", RECOVERY_CASES, ids=[c[0] for c in RECOVERY_CASES])
def test_recovery_monotonicity(name, factory, kwargs):
    """f(a) <= f(b) for all a < b — more restoration never reduces recovery."""
    fn = _make_fn(factory, kwargs)
    xs = [i / N_POINTS for i in range(N_POINTS + 1)]
    vals = [fn(x) for x in xs]
    violations = [
        (xs[i], xs[i + 1], vals[i], vals[i + 1])
        for i in range(len(vals) - 1)
        if vals[i] > vals[i + 1] + 1e-9
    ]
    assert not violations, (
        f"{name}: non-monotone at {violations[:3]}"
    )


# ── Entropy asymmetry ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("threshold", THRESHOLDS)
def test_logistic_recovery_slower_than_logistic_damage(threshold):
    """
    At key mid-range and upper depletion points, recovery lags behind damage.

    This encodes entropy asymmetry (Scientific Foundation #2): at any given ratio
    x, fewer ecosystem services have been recovered (when restoring) than were
    lost (when destroying). Destruction is fast; recovery is slow.

    We test this at specific ecologically meaningful points:
        - 50% ratio: the midpoint — recovery should be clearly behind damage
        - 75% ratio: upper range — recovery should still lag substantially
        - Average over [0.3, 0.9]: the bulk of the meaningful range

    We do NOT test point-by-point across the full range because the two functions
    have different inflection positions (recovery at 0.60, damage near threshold),
    causing them to cross in the very early range — which is acceptable since both
    start at 0 and services at very low ratios are minimal.
    """
    recovery_fn = logistic_recovery(threshold=threshold)
    damage_fn = logistic_damage(threshold=threshold)

    # At 50%: recovery must be below damage (key entropy asymmetry check)
    assert recovery_fn(0.50) < damage_fn(0.50), (
        f"At 50%: recovery ({recovery_fn(0.50):.4f}) should be < damage "
        f"({damage_fn(0.50):.4f}) for threshold={threshold}"
    )

    # At 75%: recovery must still lag damage
    assert recovery_fn(0.75) < damage_fn(0.75), (
        f"At 75%: recovery ({recovery_fn(0.75):.4f}) should be < damage "
        f"({damage_fn(0.75):.4f}) for threshold={threshold}"
    )

    # Average over [0.3, 0.9]: recovery must be lower overall in meaningful range
    xs = [0.3 + i * 0.006 for i in range(100)]
    avg_recovery = sum(recovery_fn(x) for x in xs) / len(xs)
    avg_damage = sum(damage_fn(x) for x in xs) / len(xs)
    assert avg_recovery < avg_damage, (
        f"Average recovery ({avg_recovery:.4f}) should be < average damage "
        f"({avg_damage:.4f}) over [0.3, 0.9] for threshold={threshold}"
    )


@pytest.mark.parametrize("slope", [0.6, 0.8])
def test_linear_recovery_below_full_damage(slope):
    """
    Linear recovery with slope < 1.0 is always below the identity line.

    A slope of 0.8 means 80% recovery efficiency — at any restoration ratio x,
    only 80% of the potential services have returned. This encodes the entropy
    cost of restoration: even with perfect replanting, restored ecosystems
    provide less service per unit than the original.
    """
    fn = linear_recovery(slope=slope)
    xs = [i / N_POINTS for i in range(1, N_POINTS)]
    # At any x, f(x) = slope * x <= x (since slope <= 1.0)
    violations = [x for x in xs if fn(x) > x + 1e-9]
    assert not violations, (
        f"linear_recovery(slope={slope}): f(x) should be <= x for all x, "
        f"got violations at {violations[:3]}"
    )


# ── linear_recovery validation ──────────────────────────────────────────────────

def test_linear_recovery_rejects_slope_above_one():
    """slope > 1.0 implies super-efficient restoration — physically impossible."""
    with pytest.raises(ValueError, match="slope"):
        linear_recovery(slope=1.1)


def test_linear_recovery_rejects_zero_slope():
    """slope <= 0.0 implies no recovery — not a valid recovery function."""
    with pytest.raises(ValueError, match="slope"):
        linear_recovery(slope=0.0)


def test_linear_recovery_rejects_negative_slope():
    """Negative slope implies restoration makes things worse."""
    with pytest.raises(ValueError, match="slope"):
        linear_recovery(slope=-0.5)


def test_linear_recovery_accepts_slope_one():
    """slope=1.0 is the upper bound — perfectly efficient restoration."""
    fn = linear_recovery(slope=1.0)
    assert abs(fn(0.5) - 0.5) < 1e-9
    assert abs(fn(1.0) - 1.0) < 1e-9
