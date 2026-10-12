"""
Gaia v0.4 — Succession curve evaluation and maturation timeline.

Implements the three-phase succession maturation curve (Foundation F8):
    pioneer → intermediate → climax

Each phase uses a different interpolation:
    - Pioneer: linear ramp (slow early growth)
    - Intermediate: Hermite smoothstep (accelerating growth)
    - Climax approach: decelerating curve (diminishing returns)

A maturation_delay parameter inserts a dead zone of zero service
at the start, reflecting the time before pioneer species establish.

All functions use primitive types.
No third-party dependencies.

Scientific foundations used: F8 (Ecological Succession & Climax State).
"""

from typing import Optional

from gaia.models import CarbonProfile, DiscountConfig, MaturationStep, SuccessionCurve


def get_succession_phase(curve: SuccessionCurve, years: float) -> str:
    """Return the succession phase name at a given year since restoration.

    Args:
        curve: The SuccessionCurve parameters.
        years: Years since restoration began.

    Returns:
        One of "delay", "pioneer", "intermediate", or "climax".
    """
    if years < curve.maturation_delay:
        return "delay"
    effective: float = years - curve.maturation_delay
    if effective <= curve.pioneer_end_year:
        return "pioneer"
    if effective <= curve.intermediate_end_year:
        return "intermediate"
    return "climax"


def succession_service(curve: SuccessionCurve, years: float) -> float:
    """Compute service capacity at a given year since restoration.

    Returns a value in [0.0, 1.0] representing the fraction of maximum
    ecosystem services that the restored system delivers at this point.

    Phase interpolations:
        - Delay: 0.0 (dead zone, no services)
        - Pioneer: linear ramp from 0 to pioneer_service
        - Intermediate: Hermite smoothstep from pioneer_service to intermediate_service
        - Climax approach: decelerating (1 - (1-t)^2) from intermediate_service to 1.0

    Args:
        curve: The SuccessionCurve parameters.
        years: Years since restoration began.

    Returns:
        Service capacity fraction (0.0 to 1.0).
    """
    if years < curve.maturation_delay:
        return 0.0

    effective: float = years - curve.maturation_delay

    if effective <= curve.pioneer_end_year:
        # Pioneer phase: linear ramp from 0 to pioneer_service
        if curve.pioneer_end_year == 0.0:
            return curve.pioneer_service
        t: float = effective / curve.pioneer_end_year
        return curve.pioneer_service * t

    if effective <= curve.intermediate_end_year:
        # Intermediate phase: smoothstep from pioneer_service to intermediate_service
        span: float = curve.intermediate_end_year - curve.pioneer_end_year
        if span == 0.0:
            return curve.intermediate_service
        t = (effective - curve.pioneer_end_year) / span
        # Hermite smoothstep: t² × (3 - 2t)
        t_smooth: float = t * t * (3.0 - 2.0 * t)
        return curve.pioneer_service + (
            curve.intermediate_service - curve.pioneer_service
        ) * t_smooth

    # Climax approach: decelerating from intermediate_service to 1.0
    span = curve.climax_approach_year - curve.intermediate_end_year
    if span == 0.0:
        return 1.0
    t = (effective - curve.intermediate_end_year) / span
    if t > 1.0:
        t = 1.0
    # Decelerating curve: 1 - (1 - t)²
    t_decel: float = 1.0 - (1.0 - t) ** 2
    return curve.intermediate_service + (1.0 - curve.intermediate_service) * t_decel


def find_years_to_threshold(curve: SuccessionCurve, fraction: float) -> float:
    """Find the year when service capacity first reaches a given fraction.

    Uses a simple numerical scan with 0.1-year resolution.
    Sufficient for the reporting use case (years_to_50pct, years_to_90pct).

    Args:
        curve: The SuccessionCurve parameters.
        fraction: Target service fraction (e.g. 0.5 for 50%).

    Returns:
        Year when the fraction is first reached. Returns
        climax_approach_year + maturation_delay if never reached within range.
    """
    max_year: float = curve.climax_approach_year + curve.maturation_delay + 10.0
    step: float = 0.1
    year: float = 0.0
    while year <= max_year:
        svc: float = succession_service(curve, year)
        if svc >= fraction:
            return year
        year += step
    return curve.climax_approach_year + curve.maturation_delay


def compute_maturation_timeline(
    succession_curve: SuccessionCurve,
    max_recovered_value: float,
    time_horizon_years: int,
    units_restored: int,
    carbon_profile: Optional[CarbonProfile] = None,
    substrate_ceiling: float = 1.0,
) -> list:
    """Produce a year-by-year maturation timeline.

    For each year in the time horizon, compute the service fraction from the
    succession curve, the actual annual service value, cumulative service value,
    and (if carbon_profile is present) annual and cumulative carbon absorbed.
    Services and absorption are delivered at min(service_fraction,
    substrate_ceiling): the substrate caps what the restored units can reach.

    Args:
        succession_curve: The SuccessionCurve to evaluate.
        max_recovered_value: €/yr — biological annual service value at full
            climax, before the substrate cap.
        time_horizon_years: Number of years to simulate.
        units_restored: Number of resource units restored.
        carbon_profile: Optional CarbonProfile for carbon absorption tracking.
        substrate_ceiling: Max recoverable fraction (1.0 = no substrate cap).

    Returns:
        List of MaturationStep, one per year (year 1 to time_horizon_years).
    """
    timeline: list = []
    cumulative_service: float = 0.0
    cumulative_carbon: float = 0.0

    for year in range(1, time_horizon_years + 1):
        svc_fraction: float = succession_service(succession_curve, float(year))
        phase: str = get_succession_phase(succession_curve, float(year))

        delivered: float = min(svc_fraction, substrate_ceiling)

        annual_value: float = max_recovered_value * delivered
        cumulative_service += annual_value

        annual_carbon: float = 0.0
        if carbon_profile is not None:
            annual_carbon = (
                units_restored
                * carbon_profile.annual_absorption_tonnes
                * delivered
            )
        cumulative_carbon += annual_carbon

        timeline.append(MaturationStep(
            year=year,
            succession_phase=phase,
            service_fraction=svc_fraction,
            annual_service_value=annual_value,
            cumulative_service_value=cumulative_service,
            annual_carbon_absorbed=annual_carbon,
            cumulative_carbon_absorbed=cumulative_carbon,
        ))

    return timeline


def compute_maturation_gap(
    timeline: list,
    max_recovered_value: float,
    discount: DiscountConfig,
) -> float:
    """Present value of the maturation gap — the discounted cost of waiting.

    Each year the restored units deliver less than their mature service
    flow. That shortfall is a yearly flow; it is discounted (and given the
    scarcity uplift, like every service stream in gaia.discount) to year 0
    and summed. The mature flow is the substrate-capped one (the
    RestorationResult's annual_recovered_value), so the gap is temporary;
    the permanent substrate shortfall is not part of it:

        maturation_gap = Σ_y (max_service_value - actual_service_value_y)
                             × discount_factor(y) × scarcity_factor(y)

    over the timeline's years (1..time_horizon_years).

    Args:
        timeline: List of MaturationStep from compute_maturation_timeline.
        max_recovered_value: €/yr — annual service value at maturity
            (substrate-capped).
        discount: DiscountConfig used to bring each year's gap to year 0.

    Returns:
        Maturation gap in € (present value at year 0).
    """
    gap: float = 0.0
    for step in timeline:
        annual_gap: float = max_recovered_value - step.annual_service_value
        gap += (
            annual_gap
            * discount.discount_factor(step.year)
            * discount.scarcity_factor(step.year)
        )
    return gap
