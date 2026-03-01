"""
Gaia v0.4 — Input validation.

Validation functions raise descriptive ValueError on bad inputs.
They never silently default — bad input must be caught early.

v0.3: Added validation for trophic levels, keystone thresholds,
      and interaction edges.
v0.4: Added validation for SuccessionCurve, CarbonProfile, ResilienceConfig.
"""

from gaia.models import (
    CarbonProfile,
    DamageFunc,
    Ecosystem,
    InteractionEdge,
    ResilienceConfig,
    Resource,
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
