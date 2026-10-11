"""
Gaia v0.7 — Input validation.

Validation functions raise descriptive ValueError on bad inputs.
They never silently default — bad input must be caught early.

v0.3: Added validation for trophic levels, keystone thresholds,
      and interaction edges.
v0.4: Added validation for SuccessionCurve, CarbonProfile, ResilienceConfig.
v0.5: Added validation for SubstrateProfile.
v0.6: Added validation for DiscountConfig.
v0.7: Added validation for ScarcityFunction, AnchorPoint, PricingConfig.
Step 3.8: Incoming edge-strength cap, calibration regime, and a
      CalibrationWarning when health at the safe threshold is low.
"""

import dataclasses
import math
import warnings
from typing import Optional

from gaia.constants import (
    MAX_EDGE_STRENGTH,
    MAX_INCOMING_EDGE_STRENGTH,
    THRESHOLD_HEALTH_WARNING_LEVEL,
)
from gaia.models import (
    AnchorPoint,
    CalibrationRegime,
    CarbonProfile,
    DamageFunc,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    PricingConfig,
    ResilienceConfig,
    Resource,
    RestorationCost,
    ScarcityFunction,
    SubstrateProfile,
    SubstrateType,
    SuccessionCurve,
)
from gaia.propagation import ecosystem_health_at, worst_case_incoming_strengths

# Valid trophic levels: -1 (abiotic), 0 (producer), 1-3 (consumers)
_VALID_TROPHIC_LEVELS = {-1, 0, 1, 2, 3}

# Valid interaction types
_VALID_INTERACTION_TYPES = {"dependency", "trophic", "keystone", "competition"}

# Tolerance for floating-point comparisons
_WEIGHT_SUM_TOLERANCE: float = 1e-6
_DAMAGE_BOUNDARY_TOLERANCE: float = 1e-4

# Number of points used when checking damage function invariants
_INVARIANT_CHECK_POINTS: int = 100
# Invariant 6 (convexity just past the threshold), as in tests/test_damage.py
_CONVEXITY_WINDOW: float = 0.10          # fraction of the post-threshold span
_CONVEXITY_CHECK_POINTS: int = 50
_CONVEXITY_TOLERANCE: float = 1e-6
_CONVEXITY_MAX_VIOLATIONS: float = 0.20  # fraction of points allowed to fail


class CalibrationWarning(UserWarning):
    """A valid ecosystem whose parameters look miscalibrated (Step 3.8)."""


def _require_finite(obj, name: str) -> None:
    """ValueError if any numeric field of the dataclass ``obj`` is NaN or ±inf.

    NaN slips through every ordered comparison (``nan < 0`` is False), and
    an infinite rate or area yields infinite costs, so every validator calls
    this before its range checks. Booleans, strings, None and nested
    objects are skipped (nested dataclasses have their own validator).
    """
    for f in dataclasses.fields(obj):
        value = getattr(obj, f.name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if not math.isfinite(value):
            raise ValueError(f"{name}.{f.name} must be a finite number, got {value!r}")


def validate_resource(resource: Resource) -> None:
    """
    Validate a Resource dataclass.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(resource, "Resource")
    if resource.total_units <= 0:
        raise ValueError(
            f"Resource.total_units must be > 0, got {resource.total_units}"
        )
    if not (0.0 < resource.safe_threshold_ratio < 1.0):
        raise ValueError(
            f"Resource.safe_threshold_ratio must be in (0.0, 1.0), "
            f"got {resource.safe_threshold_ratio}"
        )
    if resource.unit_value < 0.0:
        raise ValueError(
            f"Resource.unit_value must be >= 0.0, got {resource.unit_value}"
        )
    if not (
        isinstance(resource.area_ha, (int, float))
        and math.isfinite(resource.area_ha)
        and resource.area_ha > 0.0
    ):
        raise ValueError(
            f"Resource.area_ha must be a finite number of hectares > 0, "
            f"got {resource.area_ha!r}"
        )

    # v0.4: Validate optional carbon profile and resilience config
    if resource.carbon_profile is not None:
        validate_carbon_profile(resource.carbon_profile)
    if resource.resilience is not None:
        validate_resilience_config(resource.resilience)

    # v0.5: Validate optional substrate profile
    if resource.substrate is not None:
        validate_substrate_profile(resource.substrate)

    # v0.6: Validate optional discount config
    if resource.discount is not None:
        validate_discount_config(resource.discount)


def validate_ecosystem(
    ecosystem: Ecosystem,
    threshold_health_warning: Optional[float] = THRESHOLD_HEALTH_WARNING_LEVEL,
) -> None:
    """
    Validate an Ecosystem and all its agents.

    Args:
        ecosystem: The ecosystem to validate.
        threshold_health_warning: Warn (CalibrationWarning) when ecosystem
            health at the safe-threshold depletion is below this level, in
            (0, 1]; None disables the check. See check_threshold_health.

    Raises:
        ValueError: If any constraint is violated.
    """
    validate_resource(ecosystem.resource)

    if len(ecosystem.agents) == 0:
        raise ValueError("Ecosystem must have at least one agent.")

    weight_sum: float = 0.0
    for agent in ecosystem.agents:
        _require_finite(agent, f"Agent '{agent.name}'")
        if not (0.0 < agent.dependency_weight <= 1.0):
            raise ValueError(
                f"Agent '{agent.name}' dependency_weight must be in (0.0, 1.0], "
                f"got {agent.dependency_weight}"
            )
        if not (
            math.isfinite(agent.annual_value_per_ha)
            and agent.annual_value_per_ha >= 0.0
        ):
            raise ValueError(
                f"Agent '{agent.name}' annual_value_per_ha must be finite and "
                f">= 0.0 (€/ha/yr at full damage), got {agent.annual_value_per_ha}"
            )
        weight_sum += agent.dependency_weight

    if abs(weight_sum - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"Agent dependency_weights must sum to 1.0, "
            f"got {weight_sum:.6f} (tolerance: {_WEIGHT_SUM_TOLERANCE})"
        )

    # v0.3: Validate trophic levels and keystone thresholds
    for agent in ecosystem.agents:
        if agent.trophic_level not in _VALID_TROPHIC_LEVELS:
            raise ValueError(
                f"Agent '{agent.name}' trophic_level must be one of "
                f"{sorted(_VALID_TROPHIC_LEVELS)}, got {agent.trophic_level}"
            )
        if agent.is_keystone:
            if not (0.0 < agent.keystone_threshold < 1.0):
                raise ValueError(
                    f"Agent '{agent.name}' keystone_threshold must be in (0.0, 1.0), "
                    f"got {agent.keystone_threshold}"
                )

    # Damage functions: the six invariants, at the resource's safe threshold
    threshold: float = ecosystem.resource.safe_threshold_ratio
    for agent in ecosystem.agents:
        validate_damage_function(
            agent.damage_function,
            name=f"Agent '{agent.name}' damage_function",
            threshold=threshold,
        )

    # v0.3: Validate interaction edges
    agent_names = {a.name for a in ecosystem.agents}
    for edge in ecosystem.interactions:
        _validate_interaction_edge(edge, agent_names)
    _validate_incoming_edge_strengths(ecosystem)
    _validate_calibration_regime(ecosystem)

    # v0.4: Validate agent-specific succession curves
    for agent in ecosystem.agents:
        if agent.succession_curve is not None:
            validate_succession_curve(
                agent.succession_curve,
                name=f"Agent '{agent.name}' succession_curve",
            )

    # v0.7: Validate optional pricing config
    if ecosystem.pricing is not None:
        validate_pricing_config(ecosystem.pricing, agent_names)

    if threshold_health_warning is not None:
        check_threshold_health(ecosystem, threshold_health_warning)


def validate_extraction(ecosystem: Ecosystem, units_to_extract: int) -> None:
    """
    Validate extraction parameters.

    Raises:
        ValueError: If units_to_extract is out of range.
    """
    if units_to_extract < 0:
        raise ValueError(
            f"units_to_extract must be >= 0, got {units_to_extract}"
        )
    if units_to_extract > ecosystem.resource.total_units:
        raise ValueError(
            f"units_to_extract ({units_to_extract}) exceeds "
            f"resource.total_units ({ecosystem.resource.total_units})"
        )


def validate_damage_function(
    fn: DamageFunc,
    name: str = "damage_function",
    threshold: Optional[float] = None,
) -> None:
    """
    Validate that a damage function satisfies the six scientific invariants
    listed in gaia.damage:

        1. f(0.0) ≈ 0.0  (no depletion → no damage)
        2. f(1.0) ≈ 1.0  (full depletion → full damage)
        3. Finite output in [0.0, 1.0] (within tolerance)
        4. Monotonicity: f is non-decreasing
        5. Non-linearity (Foundation F4): the slope over [t, t + h] exceeds
           the slope over [t − h, t], h = min(0.1, 0.4 t, 0.4 (1 − t))
        6. Convexity just past the threshold: second finite differences
           >= -1e-6 over [t, t + 10% of (1 − t)], at most 20% of the points
           excepted (floating-point noise near a logistic inflection)

    1-4 are sampled at _INVARIANT_CHECK_POINTS + 1 evenly spaced points; 6
    at 51. The threshold t is the function's own ``threshold`` attribute
    (set by the gaia.damage factories), else ``threshold``, else 0.5.
    About 150 evaluations per function: negligible next to a run.

    validate_ecosystem calls this for every agent (with the resource's
    safe_threshold_ratio as the fallback), so the invariants hold on every
    run.

    Args:
        fn: The damage function to validate.
        name: Label for error messages.
        threshold: Safe threshold for invariants 5 and 6 when ``fn`` does
            not carry its own.

    Raises:
        ValueError: If any invariant is violated.
    """
    tol: float = _DAMAGE_BOUNDARY_TOLERANCE
    own = getattr(fn, "threshold", None)
    t: float = own if isinstance(own, float) else (0.5 if threshold is None else threshold)

    def evaluate(x: float) -> float:
        val = fn(x)
        if not (isinstance(val, (int, float)) and math.isfinite(val)):
            raise ValueError(f"{name}: output at x={x:.4f} is {val!r}, must be a finite number")
        return float(val)

    n: int = _INVARIANT_CHECK_POINTS
    values: list = [evaluate(i / n) for i in range(n + 1)]

    if abs(values[0]) > tol:
        raise ValueError(
            f"{name}: f(0.0) must be ≈ 0.0 (tolerance {tol}), got {values[0]}"
        )
    if abs(values[-1] - 1.0) > tol:
        raise ValueError(
            f"{name}: f(1.0) must be ≈ 1.0 (tolerance {tol}), got {values[-1]}"
        )
    for i in range(1, n + 1):
        x: float = i / n
        val: float = values[i]
        if val < 0.0 - tol or val > 1.0 + tol:
            raise ValueError(
                f"{name}: output at x={x:.4f} is {val:.6f}, must be in [0.0, 1.0]"
            )
        if val < values[i - 1] - tol:
            raise ValueError(
                f"{name}: monotonicity violated at x={x:.4f}: "
                f"f({x:.4f})={val:.6f} < f({(i-1)/n:.4f})={values[i - 1]:.6f}"
            )

    h: float = min(0.10, 0.4 * t, 0.4 * (1.0 - t))
    at_t: float = evaluate(t)
    slope_before: float = (at_t - evaluate(t - h)) / h
    slope_after: float = (evaluate(t + h) - at_t) / h
    if not slope_after > slope_before + 1e-9 * max(1.0, abs(slope_before)):
        raise ValueError(
            f"{name}: damage must accelerate at the threshold: slope "
            f"{slope_after:.6f} over [{t:g}, {t + h:g}] must exceed slope "
            f"{slope_before:.6f} over [{t - h:g}, {t:g}] (Foundation F4)"
        )

    window: float = (1.0 - t) * _CONVEXITY_WINDOW
    m: int = _CONVEXITY_CHECK_POINTS
    post: list = [evaluate(t + window * i / m) for i in range(m + 1)]
    violations: int = sum(
        1 for i in range(1, m)
        if post[i + 1] - 2.0 * post[i] + post[i - 1] < -_CONVEXITY_TOLERANCE
    )
    if violations > max(1, int(_CONVEXITY_MAX_VIOLATIONS * m)):
        raise ValueError(
            f"{name}: damage must be convex (accelerating) just past the threshold: "
            f"second differences are negative at {violations} of {m - 1} points "
            f"in [{t:g}, {t + window:g}]"
        )


def _validate_interaction_edge(edge: InteractionEdge, agent_names: set) -> None:
    """
    Validate a single InteractionEdge against the ecosystem's agent names.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(edge, f"InteractionEdge '{edge.source}' → '{edge.target}'")
    if edge.source not in agent_names:
        raise ValueError(
            f"InteractionEdge source '{edge.source}' is not an agent in the ecosystem. "
            f"Available agents: {sorted(agent_names)}"
        )
    if edge.target not in agent_names:
        raise ValueError(
            f"InteractionEdge target '{edge.target}' is not an agent in the ecosystem. "
            f"Available agents: {sorted(agent_names)}"
        )
    if edge.source == edge.target:
        raise ValueError(
            f"InteractionEdge cannot be a self-loop: "
            f"source and target are both '{edge.source}'"
        )
    if not (0.0 < edge.strength <= MAX_EDGE_STRENGTH):
        raise ValueError(
            f"InteractionEdge '{edge.source}' → '{edge.target}' strength "
            f"must be in (0.0, {MAX_EDGE_STRENGTH}], got {edge.strength}"
        )
    if edge.interaction_type not in _VALID_INTERACTION_TYPES:
        raise ValueError(
            f"InteractionEdge '{edge.source}' → '{edge.target}' interaction_type "
            f"must be one of {sorted(_VALID_INTERACTION_TYPES)}, "
            f"got '{edge.interaction_type}'"
        )


def _validate_incoming_edge_strengths(ecosystem: Ecosystem) -> None:
    """
    Reject an agent whose incoming edge strengths sum above
    MAX_INCOMING_EDGE_STRENGTH (S2). Edges from keystone agents count at
    their boosted strength (× KEYSTONE_EDGE_MULTIPLIER, capped at 1): the
    boost fires exactly when the source collapses, which is when an
    over-strong in-degree would saturate the target. Nothing is rescaled
    silently: the case must bring its edges within the cap.

    Raises:
        ValueError: If any agent's worst-case incoming strength exceeds the cap.
    """
    totals: dict = worst_case_incoming_strengths(
        ecosystem.agents, ecosystem.interactions
    )
    for target, total in totals.items():
        if total > MAX_INCOMING_EDGE_STRENGTH + _WEIGHT_SUM_TOLERANCE:
            keystones = {a.name for a in ecosystem.agents if a.is_keystone}
            edges = ", ".join(
                f"{e.source} {e.strength:g}" + (" (keystone ×)" if e.source in keystones else "")
                for e in ecosystem.interactions if e.target == target
            )
            raise ValueError(
                f"Incoming interaction strengths into '{target}' sum to "
                f"{total:.3f} counting keystone boosts, above the cap of "
                f"{MAX_INCOMING_EDGE_STRENGTH} (edges: {edges}). Scale them "
                f"down: a larger in-degree saturates the target's damage."
            )


def _validate_calibration_regime(ecosystem: Ecosystem) -> None:
    """
    Check Ecosystem.calibration_regime (PROJECT_DEFINITION, Option A / B).

    It must be a CalibrationRegime, and is required when there are
    interaction edges. Under Option A (EMPIRICAL) the damage curves already
    embed indirect effects, so only keystone edges from keystone agents
    (regime shifts) are allowed.

    Raises:
        ValueError: If the regime is missing, of the wrong type, or the
            edges contradict it.
    """
    regime = ecosystem.calibration_regime
    if regime is not None and not isinstance(regime, CalibrationRegime):
        raise ValueError(
            f"Ecosystem '{ecosystem.name}' calibration_regime must be a "
            f"CalibrationRegime (EMPIRICAL = 'A' or DIRECT_ONLY = 'B'), "
            f"got {regime!r}"
        )
    if regime is None:
        if ecosystem.interactions:
            raise ValueError(
                f"Ecosystem '{ecosystem.name}' has interaction edges but no "
                f"calibration_regime: declare CalibrationRegime.EMPIRICAL ('A', "
                f"curves fitted to total observed impact) or "
                f"CalibrationRegime.DIRECT_ONLY ('B', curves are direct effects "
                f"only), since it decides whether cascades double count."
            )
        return
    if regime is CalibrationRegime.EMPIRICAL:
        keystones = {a.name for a in ecosystem.agents if a.is_keystone}
        for edge in ecosystem.interactions:
            if edge.interaction_type != "keystone" or edge.source not in keystones:
                raise ValueError(
                    f"Ecosystem '{ecosystem.name}' is calibration regime A "
                    f"(empirical curves already include indirect effects), so "
                    f"only 'keystone' edges from keystone agents are allowed; "
                    f"got '{edge.source}' → '{edge.target}' "
                    f"({edge.interaction_type})"
                )


def check_threshold_health(
    ecosystem: Ecosystem,
    min_health: float = THRESHOLD_HEALTH_WARNING_LEVEL,
) -> float:
    """
    Ecosystem health at the safe-threshold depletion, warning when it is low.

    A single evaluation of the extraction step at
    depletion = resource.safe_threshold_ratio (no simulation run). Health
    below ``min_health`` there means the model puts heavy damage inside the
    "safe" zone — over-strong interaction edges or over-steep damage curves —
    so a CalibrationWarning is issued.

    Args:
        ecosystem: A validated ecosystem.
        min_health: Warning level, in (0, 1].

    Returns:
        The health at the safe threshold.

    Raises:
        ValueError: If min_health is not in (0, 1].
    """
    if not (isinstance(min_health, (int, float)) and 0.0 < min_health <= 1.0):
        raise ValueError(
            f"threshold health warning level must be in (0.0, 1.0], got {min_health!r}"
        )
    threshold: float = ecosystem.resource.safe_threshold_ratio
    health: float = ecosystem_health_at(ecosystem, threshold)
    if health < min_health:
        warnings.warn(
            f"{ecosystem.name}: ecosystem health at the safe threshold "
            f"({threshold:.0%} depletion) is {health:.2f}, below {min_health:.2f}. "
            f"The damage curves or interaction edges put heavy damage inside "
            f"the 'safe' zone (over-steep curves or over-strong edges).",
            CalibrationWarning,
            stacklevel=1,
        )
    return health


def validate_restoration_cost(cost: RestorationCost, name: str = "RestorationCost") -> None:
    """
    Validate a RestorationCost: finite, non-negative costs and an integer
    number of maintenance years >= 0.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(cost, name)
    if cost.planting_cost_per_unit < 0.0:
        raise ValueError(
            f"{name}: planting_cost_per_unit must be >= 0.0, got {cost.planting_cost_per_unit}"
        )
    if cost.annual_maintenance_per_unit < 0.0:
        raise ValueError(
            f"{name}: annual_maintenance_per_unit must be >= 0.0, "
            f"got {cost.annual_maintenance_per_unit}"
        )
    if (isinstance(cost.maintenance_years, bool) or not isinstance(cost.maintenance_years, int)
            or cost.maintenance_years < 0):
        raise ValueError(
            f"{name}: maintenance_years must be an integer >= 0, got {cost.maintenance_years!r}"
        )


# ── v0.4: New validation functions ─────────────────────────────────────────────


def validate_succession_curve(
    curve: SuccessionCurve,
    name: str = "SuccessionCurve",
) -> None:
    """
    Validate a SuccessionCurve dataclass.

    Checks:
        - Phase years are ordered: pioneer_end < intermediate_end < climax_approach
        - Service values in [0.0, 1.0) and ordered: pioneer < intermediate
        - Maturation delay >= 0
        - All year values > 0

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(curve, name)
    if curve.maturation_delay < 0.0:
        raise ValueError(
            f"{name}: maturation_delay must be >= 0.0, got {curve.maturation_delay}"
        )
    if curve.pioneer_end_year <= 0.0:
        raise ValueError(
            f"{name}: pioneer_end_year must be > 0.0, got {curve.pioneer_end_year}"
        )
    if curve.intermediate_end_year <= curve.pioneer_end_year:
        raise ValueError(
            f"{name}: intermediate_end_year ({curve.intermediate_end_year}) "
            f"must be > pioneer_end_year ({curve.pioneer_end_year})"
        )
    if curve.climax_approach_year <= curve.intermediate_end_year:
        raise ValueError(
            f"{name}: climax_approach_year ({curve.climax_approach_year}) "
            f"must be > intermediate_end_year ({curve.intermediate_end_year})"
        )
    if not (0.0 <= curve.pioneer_service < 1.0):
        raise ValueError(
            f"{name}: pioneer_service must be in [0.0, 1.0), "
            f"got {curve.pioneer_service}"
        )
    if not (0.0 <= curve.intermediate_service < 1.0):
        raise ValueError(
            f"{name}: intermediate_service must be in [0.0, 1.0), "
            f"got {curve.intermediate_service}"
        )
    if curve.intermediate_service <= curve.pioneer_service:
        raise ValueError(
            f"{name}: intermediate_service ({curve.intermediate_service}) "
            f"must be > pioneer_service ({curve.pioneer_service})"
        )


def validate_carbon_profile(
    profile: CarbonProfile,
    name: str = "CarbonProfile",
) -> None:
    """
    Validate a CarbonProfile dataclass.

    Checks:
        - All tonnage values >= 0
        - soil_release_fraction in [0.0, 1.0]

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(profile, name)
    if profile.stored_carbon_tonnes < 0.0:
        raise ValueError(
            f"{name}: stored_carbon_tonnes must be >= 0.0, "
            f"got {profile.stored_carbon_tonnes}"
        )
    if profile.annual_absorption_tonnes < 0.0:
        raise ValueError(
            f"{name}: annual_absorption_tonnes must be >= 0.0, "
            f"got {profile.annual_absorption_tonnes}"
        )
    if profile.soil_carbon_tonnes < 0.0:
        raise ValueError(
            f"{name}: soil_carbon_tonnes must be >= 0.0, "
            f"got {profile.soil_carbon_tonnes}"
        )
    if not (0.0 <= profile.soil_release_fraction <= 1.0):
        raise ValueError(
            f"{name}: soil_release_fraction must be in [0.0, 1.0], "
            f"got {profile.soil_release_fraction}"
        )


def validate_resilience_config(
    config: ResilienceConfig,
    name: str = "ResilienceConfig",
) -> None:
    """
    Validate a ResilienceConfig dataclass.

    Checks:
        - warning_zone_width > 0
        - Confidence values in [0.0, 1.0] and descending: green > yellow > red
        - irreversibility_flag_ratio in (0.0, 1.0]

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(config, name)
    if config.warning_zone_width <= 0.0:
        raise ValueError(
            f"{name}: warning_zone_width must be > 0.0, "
            f"got {config.warning_zone_width}"
        )
    for field_name, val in [
        ("confidence_green", config.confidence_green),
        ("confidence_yellow", config.confidence_yellow),
        ("confidence_red", config.confidence_red),
    ]:
        if not (0.0 <= val <= 1.0):
            raise ValueError(
                f"{name}: {field_name} must be in [0.0, 1.0], got {val}"
            )
    if not (config.confidence_green > config.confidence_yellow > config.confidence_red):
        raise ValueError(
            f"{name}: confidence values must be descending "
            f"(green > yellow > red), got "
            f"green={config.confidence_green}, "
            f"yellow={config.confidence_yellow}, "
            f"red={config.confidence_red}"
        )
    if not (0.0 < config.irreversibility_flag_ratio <= 1.0):
        raise ValueError(
            f"{name}: irreversibility_flag_ratio must be in (0.0, 1.0], "
            f"got {config.irreversibility_flag_ratio}"
        )


# ── v0.5: Substrate validation ───────────────────────────────────────────────

# Valid capacity function types
_VALID_CAPACITY_FUNCTIONS = {"linear", "threshold", "logistic"}

# Valid confidence levels
_VALID_CONFIDENCE_LEVELS = {"low", "low-medium", "medium", "medium-high", "high"}


def validate_substrate_profile(
    profile: SubstrateProfile,
    name: str = "SubstrateProfile",
) -> None:
    """
    Validate a SubstrateProfile dataclass.

    Checks:
        - substrate_type is a SubstrateType value
        - The state variable selected by substrate_type is set
          (terrestrial: soil_depth_cm; marine: sediment_stability), and
          the other medium's properties are not
        - Erosion rates >= 0
        - Formation rate >= 0
        - capacity_function is valid (threshold is terrestrial-only)
        - confidence is valid
        - For threshold function: critical_minimum >= 0

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(profile, name)
    try:
        substrate_type = SubstrateType(profile.substrate_type)
    except ValueError:
        raise ValueError(
            f"{name}: substrate_type must be one of "
            f"{[t.value for t in SubstrateType]}, got {profile.substrate_type!r}"
        ) from None

    if substrate_type.is_terrestrial:
        if profile.soil_depth_cm is None:
            raise ValueError(
                f"{name}: substrate_type '{substrate_type.value}' requires soil_depth_cm"
            )
        if profile.sediment_stability is not None or profile.water_clarity_kd is not None:
            raise ValueError(
                f"{name}: substrate_type '{substrate_type.value}' must not set "
                f"marine properties (sediment_stability, water_clarity_kd)"
            )
    else:
        if profile.sediment_stability is None:
            raise ValueError(
                f"{name}: substrate_type '{substrate_type.value}' requires "
                f"sediment_stability"
            )
        if profile.soil_depth_cm is not None:
            raise ValueError(
                f"{name}: substrate_type '{substrate_type.value}' must not set "
                f"soil_depth_cm"
            )

    # Validate constraint property values when set
    if profile.soil_depth_cm is not None and profile.soil_depth_cm < 0.0:
        raise ValueError(
            f"{name}: soil_depth_cm must be >= 0.0, got {profile.soil_depth_cm}"
        )
    if profile.water_availability_mm_yr is not None and profile.water_availability_mm_yr < 0.0:
        raise ValueError(
            f"{name}: water_availability_mm_yr must be >= 0.0, "
            f"got {profile.water_availability_mm_yr}"
        )
    if profile.water_clarity_kd is not None and profile.water_clarity_kd < 0.0:
        raise ValueError(
            f"{name}: water_clarity_kd must be >= 0.0, got {profile.water_clarity_kd}"
        )
    if profile.sediment_stability is not None:
        if not (0.0 <= profile.sediment_stability <= 1.0):
            raise ValueError(
                f"{name}: sediment_stability must be in [0.0, 1.0], "
                f"got {profile.sediment_stability}"
            )

    # Erosion and formation rates
    if profile.erosion_rate_unprotected < 0.0:
        raise ValueError(
            f"{name}: erosion_rate_unprotected must be >= 0.0, "
            f"got {profile.erosion_rate_unprotected}"
        )
    if profile.erosion_rate_protected < 0.0:
        raise ValueError(
            f"{name}: erosion_rate_protected must be >= 0.0, "
            f"got {profile.erosion_rate_protected}"
        )
    if profile.formation_rate < 0.0:
        raise ValueError(
            f"{name}: formation_rate must be >= 0.0, got {profile.formation_rate}"
        )

    # Capacity function
    if profile.capacity_function not in _VALID_CAPACITY_FUNCTIONS:
        raise ValueError(
            f"{name}: capacity_function must be one of "
            f"{sorted(_VALID_CAPACITY_FUNCTIONS)}, got '{profile.capacity_function}'"
        )

    # Threshold-specific validation
    if profile.capacity_function == "threshold":
        if not substrate_type.is_terrestrial:
            raise ValueError(
                f"{name}: capacity_function 'threshold' is defined on soil depth "
                f"(critical_minimum in cm) and is not supported for "
                f"substrate_type '{substrate_type.value}'"
            )
        if profile.critical_minimum < 0.0:
            raise ValueError(
                f"{name}: critical_minimum must be >= 0.0, "
                f"got {profile.critical_minimum}"
            )
        if not (0.0 <= profile.residual_fraction <= 1.0):
            raise ValueError(
                f"{name}: residual_fraction must be in [0.0, 1.0], "
                f"got {profile.residual_fraction}"
            )

    # Erosion alpha
    if profile.erosion_alpha <= 0.0:
        raise ValueError(
            f"{name}: erosion_alpha must be > 0.0, got {profile.erosion_alpha}"
        )

    # Confidence
    if profile.confidence not in _VALID_CONFIDENCE_LEVELS:
        raise ValueError(
            f"{name}: confidence must be one of "
            f"{sorted(_VALID_CONFIDENCE_LEVELS)}, got '{profile.confidence}'"
        )


# ── v0.6: Discount validation ───────────────────────────────────────────────


def validate_discount_config(
    config: DiscountConfig,
    name: str = "DiscountConfig",
) -> None:
    """Validate a DiscountConfig dataclass.

    Checks:
        - delta >= 0
        - eta >= 0
        - g >= 0
        - rate_schedule: if float, >= 0; if list, sorted ascending, each rate >= 0
        - scarcity_rate >= 0
        - horizon_years > 0
        - carbon_price_current >= 0
        - carbon_price_growth >= 0
        - convergence (C3): scarcity_rate and carbon_price_growth are each
          strictly below the discount rate in every year of the horizon
          (1..horizon_years); for a declining schedule, below the rate of
          every segment in force within the horizon (see
          _rate_segments_in_horizon). Otherwise the present value of a
          permanent flow grows without bound as the horizon grows, and the
          arbitrary horizon decides the answer.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(config, name)
    if config.delta < 0.0:
        raise ValueError(f"{name}: delta must be >= 0.0, got {config.delta}")
    if config.eta < 0.0:
        raise ValueError(f"{name}: eta must be >= 0.0, got {config.eta}")
    if config.g < 0.0:
        raise ValueError(f"{name}: g must be >= 0.0, got {config.g}")

    if isinstance(config.rate_schedule, (int, float)):
        if not math.isfinite(config.rate_schedule) or float(config.rate_schedule) < 0.0:
            raise ValueError(
                f"{name}: rate_schedule must be >= 0.0, got {config.rate_schedule}"
            )
    elif isinstance(config.rate_schedule, list):
        if len(config.rate_schedule) == 0:
            raise ValueError(f"{name}: rate_schedule list must not be empty")
        prev_year: int = -1
        for i, entry in enumerate(config.rate_schedule):
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                raise ValueError(
                    f"{name}: rate_schedule entry {i} must be (year, rate) tuple"
                )
            year_val, rate_val = entry
            if not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in entry
            ):
                raise ValueError(
                    f"{name}: rate_schedule entry {i} must be finite numbers, got {entry!r}"
                )
            if year_val <= prev_year:
                raise ValueError(
                    f"{name}: rate_schedule years must be ascending, "
                    f"got year {year_val} after {prev_year}"
                )
            if rate_val < 0.0:
                raise ValueError(
                    f"{name}: rate_schedule rate at year {year_val} must be >= 0.0, "
                    f"got {rate_val}"
                )
            prev_year = year_val
    else:
        raise ValueError(
            f"{name}: rate_schedule must be a float or list of (year, rate) tuples"
        )

    if config.scarcity_rate < 0.0:
        raise ValueError(
            f"{name}: scarcity_rate must be >= 0.0, got {config.scarcity_rate}"
        )
    if config.horizon_years <= 0:
        raise ValueError(
            f"{name}: horizon_years must be > 0, got {config.horizon_years}"
        )
    if config.carbon_price_current < 0.0:
        raise ValueError(
            f"{name}: carbon_price_current must be >= 0.0, "
            f"got {config.carbon_price_current}"
        )
    if config.carbon_price_growth < 0.0:
        raise ValueError(
            f"{name}: carbon_price_growth must be >= 0.0, "
            f"got {config.carbon_price_growth}"
        )

    # C3: every growing value stream must be discounted faster than it grows
    for start, end, rate in _rate_segments_in_horizon(config):
        where: str = (
            f"the discount rate ({rate:.2%}/yr)"
            if isinstance(config.rate_schedule, (int, float))
            else f"the discount rate of the schedule segment for years "
                 f"{start}-{end} ({rate:.2%}/yr)"
        )
        if config.scarcity_rate >= rate:
            raise ValueError(
                f"{name}: scarcity_rate ({config.scarcity_rate:.2%}/yr) must be "
                f"below {where}. Ecosystem services would gain value faster "
                f"than they are discounted, so their present value would grow "
                f"without bound with the horizon."
            )
        if config.carbon_price_growth >= rate:
            raise ValueError(
                f"{name}: carbon_price_growth ({config.carbon_price_growth:.2%}/yr) "
                f"must be below {where}. Carbon would gain value faster than it "
                f"is discounted, so its present value would grow without bound "
                f"with the horizon."
            )


def _rate_segments_in_horizon(config: DiscountConfig) -> list:
    """Discount-rate segments in force during the horizon, as (start, end, rate).

    Flows fall in years 1..horizon_years (gaia.discount's convention), and the
    discount factor of year t compounds the rates of years 1..t, so these are
    the years whose rates matter. A constant rate is one segment. For a
    declining schedule, every segment that applies to at least one of those
    years is returned (the first segment also covers years before its
    threshold, as DiscountConfig.rate_at_year does); segments starting after
    the horizon are never used and are not returned. The last segment in force
    is the one that would apply forever if the horizon were extended.
    """
    horizon: int = config.horizon_years
    if isinstance(config.rate_schedule, (int, float)):
        return [(1, horizon, float(config.rate_schedule))]
    schedule: list = config.rate_schedule
    segments: list = []
    for i, (threshold, rate) in enumerate(schedule):
        start: int = 1 if i == 0 else max(int(threshold), 1)
        end: int = (
            int(schedule[i + 1][0]) - 1 if i + 1 < len(schedule) else horizon
        )
        end = min(end, horizon)
        if start <= end:
            segments.append((start, end, float(rate)))
    return segments


# ── v0.7: Pricing validation ────────────────────────────────────────────────

_VALID_SCARCITY_TYPES = {"smooth", "threshold"}
_VALID_ANCHOR_CONFIDENCE = {"high", "medium", "low"}


def validate_scarcity_function(
    fn: ScarcityFunction,
    name: str = "ScarcityFunction",
) -> None:
    """Validate a ScarcityFunction dataclass.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(fn, name)
    if fn.function_type not in _VALID_SCARCITY_TYPES:
        raise ValueError(
            f"{name}: function_type must be one of "
            f"{sorted(_VALID_SCARCITY_TYPES)}, got '{fn.function_type}'"
        )
    if fn.function_type == "smooth":
        if fn.alpha <= 0.0:
            raise ValueError(
                f"{name}: alpha must be > 0.0 for smooth type, got {fn.alpha}"
            )
    if fn.function_type == "threshold":
        if not (0.0 < fn.threshold < 1.0):
            raise ValueError(
                f"{name}: threshold must be in (0.0, 1.0) for threshold type, "
                f"got {fn.threshold}"
            )
    if fn.max_multiplier < 1.0:
        raise ValueError(
            f"{name}: max_multiplier must be >= 1.0, got {fn.max_multiplier}"
        )


def validate_anchor_point(
    anchor: AnchorPoint,
    agent_names: set,
    name: str = "AnchorPoint",
) -> None:
    """Validate an AnchorPoint against available agents.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(anchor, name)
    if anchor.agent_name not in agent_names:
        raise ValueError(
            f"{name}: agent_name '{anchor.agent_name}' is not an agent. "
            f"Available: {sorted(agent_names)}"
        )
    if anchor.anchor_value <= 0.0:
        raise ValueError(
            f"{name}: anchor_value must be > 0.0, got {anchor.anchor_value}"
        )
    if anchor.confidence not in _VALID_ANCHOR_CONFIDENCE:
        raise ValueError(
            f"{name}: confidence must be one of "
            f"{sorted(_VALID_ANCHOR_CONFIDENCE)}, got '{anchor.confidence}'"
        )


def validate_pricing_config(
    config: PricingConfig,
    agent_names: set,
    name: str = "PricingConfig",
) -> None:
    """Validate a PricingConfig dataclass.

    Every agent must be anchored (Step 4, C8): an unanchored agent used to
    be priced at €0. gaia.pricing.anchor_every_agent gives the remaining
    agents a PLACEHOLDER anchor at their own direct annual service value.

    Raises:
        ValueError: If any constraint is violated.
    """
    _require_finite(config, name)
    if len(config.anchors) == 0:
        raise ValueError(f"{name}: at least one anchor is required")

    for i, anchor in enumerate(config.anchors):
        validate_anchor_point(anchor, agent_names, name=f"{name}.anchors[{i}]")

    unanchored = sorted(set(agent_names) - {a.agent_name for a in config.anchors})
    if unanchored:
        raise ValueError(
            f"{name}: every agent must be anchored when pricing is on; no "
            f"anchor for {unanchored}. Add an AnchorPoint for each (e.g. "
            f"gaia.pricing.anchor_every_agent: the agent's own annual value)."
        )

    for agent_key, scarcity_fn in config.scarcity_functions.items():
        if agent_key not in agent_names:
            raise ValueError(
                f"{name}: scarcity_functions key '{agent_key}' is not an agent. "
                f"Available: {sorted(agent_names)}"
            )
        validate_scarcity_function(
            scarcity_fn, name=f"{name}.scarcity_functions['{agent_key}']"
        )

    validate_scarcity_function(config.default_scarcity, name=f"{name}.default_scarcity")

    if config.convergence_tolerance <= 0.0:
        raise ValueError(
            f"{name}: convergence_tolerance must be > 0.0, "
            f"got {config.convergence_tolerance}"
        )
    if config.max_iterations <= 0:
        raise ValueError(
            f"{name}: max_iterations must be > 0, got {config.max_iterations}"
        )
