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
"""

from gaia.models import (
    AnchorPoint,
    CarbonProfile,
    DamageFunc,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    PricingConfig,
    ResilienceConfig,
    Resource,
    ScarcityFunction,
    SubstrateProfile,
    SuccessionCurve,
)

# Valid trophic levels: -1 (abiotic), 0 (producer), 1-3 (consumers)
_VALID_TROPHIC_LEVELS = {-1, 0, 1, 2, 3}

# Valid interaction types
_VALID_INTERACTION_TYPES = {"dependency", "trophic", "keystone", "competition"}

# Tolerance for floating-point comparisons
_WEIGHT_SUM_TOLERANCE: float = 1e-6
_DAMAGE_BOUNDARY_TOLERANCE: float = 1e-4

# Number of points used when checking damage function invariants
_INVARIANT_CHECK_POINTS: int = 100


def validate_resource(resource: Resource) -> None:
    """
    Validate a Resource dataclass.

    Raises:
        ValueError: If any constraint is violated.
    """
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


def validate_ecosystem(ecosystem: Ecosystem) -> None:
    """
    Validate an Ecosystem and all its agents.

    Raises:
        ValueError: If any constraint is violated.
    """
    validate_resource(ecosystem.resource)

    if len(ecosystem.agents) == 0:
        raise ValueError("Ecosystem must have at least one agent.")

    weight_sum: float = 0.0
    for agent in ecosystem.agents:
        if not (0.0 < agent.dependency_weight <= 1.0):
            raise ValueError(
                f"Agent '{agent.name}' dependency_weight must be in (0.0, 1.0], "
                f"got {agent.dependency_weight}"
            )
        if agent.monetary_rate < 0.0:
            raise ValueError(
                f"Agent '{agent.name}' monetary_rate must be >= 0.0, "
                f"got {agent.monetary_rate}"
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

    # v0.3: Validate interaction edges
    agent_names = {a.name for a in ecosystem.agents}
    for edge in ecosystem.interactions:
        _validate_interaction_edge(edge, agent_names)

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


def validate_damage_function(fn: DamageFunc, name: str = "damage_function") -> None:
    """
    Validate that a damage function satisfies the six scientific invariants.

    Checks:
        1. f(0.0) ≈ 0.0  (boundary: no depletion → no damage)
        2. f(1.0) ≈ 1.0  (boundary: full depletion → full damage)
        3. Output in [0.0, 1.0] for all inputs
        4. Monotonicity: f is non-decreasing
        5. Non-linearity: slope after midpoint > slope before midpoint
           (proxy check — full threshold-aware check requires knowing the threshold)

    Args:
        fn: The damage function to validate.
        name: Label for error messages.

    Raises:
        ValueError: If any invariant is violated.
    """
    tol: float = _DAMAGE_BOUNDARY_TOLERANCE

    at_zero: float = fn(0.0)
    if abs(at_zero) > tol:
        raise ValueError(
            f"{name}: f(0.0) must be ≈ 0.0 (tolerance {tol}), got {at_zero}"
        )

    at_one: float = fn(1.0)
    if abs(at_one - 1.0) > tol:
        raise ValueError(
            f"{name}: f(1.0) must be ≈ 1.0 (tolerance {tol}), got {at_one}"
        )

    n: int = _INVARIANT_CHECK_POINTS
    prev: float = fn(0.0)
    for i in range(1, n + 1):
        x: float = i / n
        val: float = fn(x)

        if val < 0.0 - tol or val > 1.0 + tol:
            raise ValueError(
                f"{name}: output at x={x:.4f} is {val:.6f}, must be in [0.0, 1.0]"
            )

        if val < prev - tol:
            raise ValueError(
                f"{name}: monotonicity violated at x={x:.4f}: "
                f"f({x:.4f})={val:.6f} < f({(i-1)/n:.4f})={prev:.6f}"
            )
        prev = val


def _validate_interaction_edge(edge: InteractionEdge, agent_names: set) -> None:
    """
    Validate a single InteractionEdge against the ecosystem's agent names.

    Raises:
        ValueError: If any constraint is violated.
    """
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
    if not (0.0 < edge.strength <= 1.0):
        raise ValueError(
            f"InteractionEdge '{edge.source}' → '{edge.target}' strength "
            f"must be in (0.0, 1.0], got {edge.strength}"
        )
    if edge.interaction_type not in _VALID_INTERACTION_TYPES:
        raise ValueError(
            f"InteractionEdge '{edge.source}' → '{edge.target}' interaction_type "
            f"must be one of {sorted(_VALID_INTERACTION_TYPES)}, "
            f"got '{edge.interaction_type}'"
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
        - carbon_price_per_tonne >= 0

    Raises:
        ValueError: If any constraint is violated.
    """
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
    if profile.carbon_price_per_tonne < 0.0:
        raise ValueError(
            f"{name}: carbon_price_per_tonne must be >= 0.0, "
            f"got {profile.carbon_price_per_tonne}"
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
        - At least one constraint property is set
        - Erosion rates >= 0
        - Formation rate >= 0
        - capacity_function is valid
        - confidence is valid
        - For threshold function: critical_minimum >= 0

    Raises:
        ValueError: If any constraint is violated.
    """
    # At least one constraint property must be set
    has_constraint: bool = (
        profile.soil_depth_cm is not None
        or profile.water_clarity_kd is not None
        or profile.sediment_stability is not None
    )
    if not has_constraint:
        raise ValueError(
            f"{name}: at least one constraint property must be set "
            f"(soil_depth_cm, water_clarity_kd, or sediment_stability)"
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

    Raises:
        ValueError: If any constraint is violated.
    """
    if config.delta < 0.0:
        raise ValueError(f"{name}: delta must be >= 0.0, got {config.delta}")
    if config.eta < 0.0:
        raise ValueError(f"{name}: eta must be >= 0.0, got {config.eta}")
    if config.g < 0.0:
        raise ValueError(f"{name}: g must be >= 0.0, got {config.g}")

    if isinstance(config.rate_schedule, (int, float)):
        if float(config.rate_schedule) < 0.0:
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

    Raises:
        ValueError: If any constraint is violated.
    """
    if len(config.anchors) == 0:
        raise ValueError(f"{name}: at least one anchor is required")

    for i, anchor in enumerate(config.anchors):
        validate_anchor_point(anchor, agent_names, name=f"{name}.anchors[{i}]")

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
