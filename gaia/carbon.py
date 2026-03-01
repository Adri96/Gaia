"""
Gaia v0.4 — Carbon accounting module.

Implements the double carbon externality (Foundation F9):
    1. Release cost: CO₂ stored in biomass and soil is released on extraction
    2. Absorption cost: future CO₂ absorption capacity is permanently lost

Also computes carbon absorption during the maturation timeline and
the carbon payback period (years of restored absorption to recapture
the released carbon).

All functions use primitive types for Cython compatibility.
No third-party dependencies.

Scientific foundations used: F9 (Nutrient Cycles & Carbon Cycle).
"""

from gaia.models import CarbonProfile, SuccessionCurve
from gaia.succession import succession_service


def compute_carbon_release(
    profile: CarbonProfile,
    units_extracted: int,
) -> float:
    """Compute total CO₂ released from extracting resources.

    release = units × (stored_carbon + soil_carbon × soil_release_fraction)

    Args:
        profile: CarbonProfile for the resource.
        units_extracted: Number of units extracted.

    Returns:
        Total tonnes CO₂ released.
    """
    per_unit: float = (
        profile.stored_carbon_tonnes
        + profile.soil_carbon_tonnes * profile.soil_release_fraction
    )
    return per_unit * units_extracted


def compute_absorption_foregone(
    profile: CarbonProfile,
    units_extracted: int,
    remaining_years: float,
) -> float:
    """Compute total CO₂ absorption capacity lost.

    foregone = units × annual_absorption × remaining_years

    Args:
        profile: CarbonProfile for the resource.
        units_extracted: Number of units extracted.
        remaining_years: Estimated productive years remaining for each unit.

    Returns:
        Total tonnes CO₂ absorption foregone.
    """
    return (
        profile.annual_absorption_tonnes
        * units_extracted
        * remaining_years
    )


def compute_carbon_cost(
    profile: CarbonProfile,
    units_extracted: int,
    remaining_years: float,
) -> dict:
    """Compute the monetized double carbon externality.

    Returns a breakdown dict with:
        - release_tonnes: CO₂ released (biomass + soil)
        - foregone_tonnes_per_year: CO₂ absorption lost per year
        - foregone_total_tonnes: total foregone over remaining_years
        - release_cost: € cost of released CO₂
        - foregone_cost_per_year: € annual cost of foregone absorption
        - total_cost: € total carbon externality

    Args:
        profile: CarbonProfile for the resource.
        units_extracted: Number of units extracted.
        remaining_years: Estimated productive years remaining.

    Returns:
        Dict with carbon cost breakdown.
    """
    release: float = compute_carbon_release(profile, units_extracted)
    foregone_per_year: float = profile.annual_absorption_tonnes * units_extracted
    foregone_total: float = compute_absorption_foregone(
        profile, units_extracted, remaining_years
    )

    release_cost: float = release * profile.carbon_price_per_tonne
    foregone_cost_per_year: float = foregone_per_year * profile.carbon_price_per_tonne

    return {
        "release_tonnes": release,
        "foregone_tonnes_per_year": foregone_per_year,
        "foregone_total_tonnes": foregone_total,
        "release_cost": release_cost,
        "foregone_cost_per_year": foregone_cost_per_year,
        "total_cost": release_cost + foregone_cost_per_year,
    }


def compute_annual_absorption(
    profile: CarbonProfile,
    units_restored: int,
    service_fraction: float,
) -> float:
    """Compute CO₂ absorbed in a single year during maturation.

    A pioneer sapling absorbs far less than a mature tree; the succession
    curve's service fraction scales the absorption rate.

    absorbed = units × annual_absorption × service_fraction

    Args:
        profile: CarbonProfile for the resource.
        units_restored: Number of units restored.
        service_fraction: Current succession service fraction (0.0 to 1.0).

    Returns:
        Tonnes CO₂ absorbed this year.
    """
    return (
        profile.annual_absorption_tonnes
        * units_restored
        * service_fraction
    )


def compute_carbon_payback_period(
    profile: CarbonProfile,
    units_extracted: int,
    units_restored: int,
    succession_curve: SuccessionCurve,
    max_years: int = 500,
) -> float:
    """Compute the carbon payback period.

    How many years of restored absorption it takes to recapture
    the carbon that was released on extraction.

    Scans year by year, applying the succession curve to the absorption
    rate, until cumulative absorption >= total release.

    Args:
        profile: CarbonProfile for the resource.
        units_extracted: Number of units originally extracted.
        units_restored: Number of units restored.
        succession_curve: SuccessionCurve controlling absorption ramp-up.
        max_years: Maximum years to scan (returns max_years if never reached).

    Returns:
        Years until carbon payback. Returns max_years if not reached.
    """
    total_release: float = compute_carbon_release(profile, units_extracted)
    if total_release <= 0.0:
        return 0.0

    cumulative: float = 0.0
    for year in range(1, max_years + 1):
        svc_fraction: float = succession_service(succession_curve, float(year))
        absorbed: float = compute_annual_absorption(
            profile, units_restored, svc_fraction
        )
        cumulative += absorbed
        if cumulative >= total_release:
            return float(year)

    return float(max_years)
