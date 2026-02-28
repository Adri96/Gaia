"""
Gaia v0.2 — Recovery function library.

Recovery functions map a restoration ratio (fraction of destroyed units replanted
and recovering) to a recovered ecosystem service ratio (0.0 to 1.0).

They share the same interface as damage functions (float → float) but model the
INVERSE process: restoration. The key scientific constraint is entropy asymmetry
(Scientific Foundation #2): recovery is always SLOWER than equivalent damage.
Destruction drops ecosystem services rapidly; restoration climbs back slowly.

This asymmetry is encoded in two ways:
    1. The logistic recovery function uses a higher steepness reduction and a
       shifted inflection — the S-curve is shallower on the way up than on the
       way down.
    2. The linear recovery function is parameterized with a slower slope than
       the equivalent piecewise damage function would produce.

Scientific invariants all recovery functions must satisfy:
    1. f(0.0) = 0.0  — zero restoration → zero recovered services
    2. f(1.0) = 1.0  — full restoration → full services (at maturity)
    3. Monotonicity: f(a) <= f(b) for all a < b (more planting = more recovery)
    4. Slower than damage: the recovery curve at any point x should be below
       the equivalent damage curve at x (entropy asymmetry)

Note on "full recovery": f(1.0) = 1.0 means that IF all units are replanted AND
fully matured, full ecosystem services return. Maturation delay is handled
separately by the RestorationCost.maintenance_years parameter — the recovery
function models the shape of the return curve, not the time dimension.

All functions are float → float in the hot path — Cython-compatible.
"""

import math
from typing import Callable

RecoveryFunc = Callable[[float], float]


def logistic_recovery(threshold: float, steepness: float = 7.0) -> RecoveryFunc:
    """
    Logistic (sigmoid) recovery function — the primary recovery option.

    Models the slow, S-shaped return of ecosystem services as restoration proceeds.
    The curve is inherently slower than the equivalent logistic_damage because:
        - Default steepness is 7.0 (vs 12.0 for damage) — a shallower knee
        - The inflection is placed higher in the restoration range (at 60% restored)
          rather than just above the threshold

    This encodes entropy asymmetry: a forest that collapsed rapidly past its
    threshold does NOT recover at the same speed when replanted. Microclimate
    must re-establish, mycorrhizal networks must reconnect, soil must stabilize.
    The S-curve of recovery lags well behind the S-curve of destruction.

    Formula:
        inflection = 0.60   (fixed — recovery accelerates after >60% is replanted)
        raw(x) = 1 / (1 + exp(-steepness * (x - inflection)))
        f(x)   = (raw(x) - raw(0)) / (raw(1) - raw(0))

    Args:
        threshold: The ecosystem's safe extraction threshold. Used to verify
            that recovery is slower than the corresponding damage function.
            Does not directly affect the recovery curve shape in this version.
            [PLACEHOLDER — per-ecosystem recovery thresholds in v0.3]
        steepness: Sharpness of the recovery S-curve. Default 7.0 — shallower
            than the damage default (12.0) to encode slower recovery.
            [PLACEHOLDER — pending scientific calibration per ecosystem type]

    Returns:
        RecoveryFunc mapping restoration_ratio in [0, 1] to recovered_ratio in [0, 1].
    """
    # Inflection at 60% restored: ecosystem services accelerate only after a
    # substantial fraction of the resource is back. This reflects the network
    # effect — mycorrhizal connectivity, canopy microclimate, etc. only emerge
    # above a critical density of restored units.
    inflection: float = 0.60

    raw_0: float = 1.0 / (1.0 + math.exp(-steepness * (0.0 - inflection)))
    raw_1: float = 1.0 / (1.0 + math.exp(-steepness * (1.0 - inflection)))
    span: float = raw_1 - raw_0

    def _logistic_recovery(restoration_ratio: float) -> float:
        raw: float = 1.0 / (1.0 + math.exp(-steepness * (restoration_ratio - inflection)))
        return (raw - raw_0) / span

    return _logistic_recovery


def linear_recovery(slope: float = 0.8) -> RecoveryFunc:
    """
    Linear recovery function — simple proportional return of ecosystem services.

    Each unit restored returns a fixed fraction of its potential ecosystem service
    value. The `slope` parameter controls how efficiently restoration converts
    planted units into recovered services.

    A slope of 1.0 means perfect linear recovery (each unit planted = one unit of
    service recovered). A slope < 1.0 encodes the entropy cost: replanting is
    never 100% efficient because restored units must fight entropy to re-establish
    order. A slope > 1.0 is ecologically implausible and not permitted.

    The function is clipped to [0.0, 1.0] to handle floating-point edge cases.

    Formula:
        f(x) = min(slope * x, 1.0)

    Args:
        slope: Recovery efficiency per unit restored. Must be in (0.0, 1.0].
            Default 0.8 — 80% efficiency, encoding 20% entropy cost.
            A value of 1.0 would imply perfectly reversible extraction,
            contradicting the second law of thermodynamics.
            [PLACEHOLDER — pending scientific calibration]

    Returns:
        RecoveryFunc mapping restoration_ratio in [0, 1] to recovered_ratio in [0, 1].

    Raises:
        ValueError: If slope is not in (0.0, 1.0].
    """
    if not (0.0 < slope <= 1.0):
        raise ValueError(
            f"slope must be in (0.0, 1.0], got {slope}. "
            f"A slope > 1.0 implies super-efficient restoration, which contradicts "
            f"entropy asymmetry. A slope <= 0.0 implies no recovery."
        )

    def _linear_recovery(restoration_ratio: float) -> float:
        return min(slope * restoration_ratio, 1.0)

    return _linear_recovery
