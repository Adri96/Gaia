"""
Gaia v0.6 -- Discount mechanics, NPV calculations, carbon breakeven.

Implements proper time-value-of-money economics for Gaia. All monetary values
become discountable to present value using Ramsey-based discount rates.

All functions use primitive types for Cython compatibility.
No third-party dependencies.

Scientific foundations:
    - Ramsey (1928): r = delta + eta * g
    - Stern (2006) vs Nordhaus (2007) debate on delta
    - Drupp et al. (2018): median SDR 2.0% from 200+ economists
    - Weitzman (1998, 2001): declining rates under growth uncertainty
    - Drupp & Hansel (2021): relative price effect ~2-4%/yr
    - UK HM Treasury Green Book: declining schedule 3.5% -> 2.5%
"""

from typing import Optional

from gaia.models import (
    CarbonBreakeven,
    CarbonProfile,
    DiscountConfig,
    ExtractionNPV,
    PreventionAdvantageV06,
    RestorationNPV,
    SuccessionCurve,
)
from gaia.succession import succession_service


# ── Preconfigured discount profiles ──────────────────────────────────────────


DISCOUNT_MARKET = DiscountConfig(
    delta=0.015, eta=2.0, g=0.013,
    rate_schedule=0.041,
    scarcity_rate=0.0,
    carbon_price_current=80.0,
    carbon_price_growth=0.02,
)
"""Conservative / market-aligned (Nordhaus-adjacent). 4.1%, no scarcity."""

DISCOUNT_CENTRAL = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
)
"""Central / consensus (Drupp et al. 2018). 2.3%, 2% scarcity uplift."""

DISCOUNT_ENVIRONMENTAL = DiscountConfig(
    delta=0.001, eta=1.0, g=0.013,
    rate_schedule=0.014,
    scarcity_rate=0.03,
    carbon_price_current=80.0,
    carbon_price_growth=0.04,
)
"""Environmental / Stern-adjacent. 1.4%, 3% scarcity uplift."""

DISCOUNT_GREEN_BOOK = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[(0, 0.035), (31, 0.030), (76, 0.025)],
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=125,
)
"""UK Green Book declining schedule. 3.5% -> 3.0% -> 2.5%."""


# ── NPV computation functions ────────────────────────────────────────────────


def compute_extraction_npv(
    total_externality: float,
    discount: DiscountConfig,
    carbon_profile: Optional[CarbonProfile],
    units_extracted: int,
    substrate_ceiling: float = 1.0,
    remaining_productive_years: int = 80,
) -> ExtractionNPV:
    """Discount extraction externality stream to present value.

    The extraction happens at year 0. We then project the annual cost
    streams into the future over the analysis horizon.

    Components:
        direct: Annual ecosystem service loss projected over horizon,
            discounted with scarcity uplift.
        carbon_release: One-time carbon release at year 0.
        carbon_foregone: Future absorption capacity lost, valued at rising
            carbon prices, discounted.
        substrate_damage: Permanent capacity loss as perpetual annuity.

    Args:
        total_externality: Total undiscounted externality cost from extraction.
        discount: DiscountConfig with rate schedule and scarcity parameters.
        carbon_profile: Optional carbon accounting parameters.
        units_extracted: Number of units that were extracted.
        substrate_ceiling: Max recoverable fraction (1.0 = no permanent loss).
        remaining_productive_years: Productive lifespan of destroyed units.

    Returns:
        ExtractionNPV with all NPV components.
    """
    horizon: int = discount.horizon_years

    # Direct ecosystem service loss: annual recurring cost
    # We treat total_externality as the annual service value lost
    npv_direct: float = 0.0
    for year in range(horizon):
        df: float = discount.discount_factor(year)
        sf: float = discount.scarcity_factor(year)
        npv_direct += total_externality * df * sf

    # Carbon release: one-time at year 0
    npv_carbon_release: float = 0.0
    if carbon_profile is not None and units_extracted > 0:
        total_release: float = units_extracted * (
            carbon_profile.stored_carbon_tonnes
            + carbon_profile.soil_carbon_tonnes * carbon_profile.soil_release_fraction
        )
        npv_carbon_release = total_release * discount.carbon_price_at_year(0)

    # Foregone absorption: annual stream over remaining productive years
    npv_carbon_foregone: float = 0.0
    if carbon_profile is not None and units_extracted > 0:
        annual_absorption: float = (
            units_extracted * carbon_profile.annual_absorption_tonnes
        )
        years_to_project: int = min(remaining_productive_years, horizon)
        for year in range(1, years_to_project + 1):
            cp: float = discount.carbon_price_at_year(year)
            df = discount.discount_factor(year)
            npv_carbon_foregone += annual_absorption * cp * df

    # Substrate damage: permanent capacity loss as annuity
    npv_substrate: float = 0.0
    if substrate_ceiling < 1.0:
        permanent_gap: float = 1.0 - substrate_ceiling
        annual_loss: float = total_externality * permanent_gap
        # Net effective rate for substrate annuity
        for year in range(horizon):
            df = discount.discount_factor(year)
            sf = discount.scarcity_factor(year)
            npv_substrate += annual_loss * df * sf

    total: float = npv_direct + npv_carbon_release + npv_carbon_foregone + npv_substrate

    return ExtractionNPV(
        direct=npv_direct,
        carbon_release=npv_carbon_release,
        carbon_foregone=npv_carbon_foregone,
        substrate_damage=npv_substrate,
        total=total,
        horizon=horizon,
    )


def compute_restoration_npv(
    restoration_cost_total: float,
    maintenance_cost_per_year: float,
    maintenance_years: int,
    max_recovered_value: float,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve],
    carbon_profile: Optional[CarbonProfile],
    units_restored: int,
    substrate_ceiling: float = 1.0,
    carbon_released: float = 0.0,
) -> RestorationNPV:
    """NPV of restoration as an investment.

    Costs: planting (year 0) + annual maintenance (years 1..N), discounted.
    Benefits: service recovery over succession curve, discounted with scarcity.
    Carbon: absorption over succession at rising carbon prices, discounted.

    Args:
        restoration_cost_total: Total upfront restoration cost.
        maintenance_cost_per_year: Annual maintenance cost (total, not per-unit).
        maintenance_years: Number of maintenance years.
        max_recovered_value: Full annual service value at 100% recovery.
        discount: DiscountConfig.
        succession_curve: Optional succession curve for service recovery timeline.
        carbon_profile: Optional carbon profile for absorption calculations.
        units_restored: Number of units being restored.
        substrate_ceiling: Max recoverable fraction.
        carbon_released: Total CO2 released during prior extraction.

    Returns:
        RestorationNPV with costs, benefits, ROI.
    """
    horizon: int = discount.horizon_years

    # Costs (discounted)
    # Planting: assume 75% at year 0, 25% spread over years 1-5
    planting_cost: float = restoration_cost_total - (
        maintenance_cost_per_year * maintenance_years
    )
    if planting_cost < 0.0:
        planting_cost = 0.0

    npv_cost: float = planting_cost  # Year 0, no discounting
    for year in range(1, maintenance_years + 1):
        df: float = discount.discount_factor(year)
        npv_cost += maintenance_cost_per_year * df

    # Service benefits: recovery over succession curve
    npv_services: float = 0.0
    for year in range(horizon):
        if succession_curve is not None:
            service_fraction: float = succession_service(succession_curve, float(year))
        else:
            # Without succession curve, assume immediate full recovery
            service_fraction = 1.0

        effective_fraction: float = min(service_fraction, substrate_ceiling)
        annual_services: float = max_recovered_value * effective_fraction
        df = discount.discount_factor(year)
        sf: float = discount.scarcity_factor(year)
        npv_services += annual_services * df * sf

    # Carbon absorption benefits
    npv_carbon: float = 0.0
    if carbon_profile is not None and units_restored > 0:
        annual_absorption_full: float = (
            units_restored * carbon_profile.annual_absorption_tonnes
        )
        for year in range(horizon):
            if succession_curve is not None:
                sfrac: float = succession_service(succession_curve, float(year))
            else:
                sfrac = 1.0
            effective_sfrac: float = min(sfrac, substrate_ceiling)
            absorption: float = annual_absorption_full * effective_sfrac
            cp: float = discount.carbon_price_at_year(year)
            df = discount.discount_factor(year)
            npv_carbon += absorption * cp * df

    # Carbon payback period (undiscounted)
    carbon_payback_years: Optional[int] = None
    if carbon_profile is not None and carbon_released > 0.0 and units_restored > 0:
        cumulative: float = 0.0
        annual_abs_full: float = (
            units_restored * carbon_profile.annual_absorption_tonnes
        )
        for year in range(horizon):
            if succession_curve is not None:
                sfrac = succession_service(succession_curve, float(year))
            else:
                sfrac = 1.0
            cumulative += annual_abs_full * min(sfrac, substrate_ceiling)
            if cumulative >= carbon_released:
                carbon_payback_years = year + 1
                break

    npv_benefits: float = npv_services + npv_carbon
    roi: float = npv_benefits / npv_cost if npv_cost > 0.0 else float('inf')

    return RestorationNPV(
        cost=npv_cost,
        service_benefits=npv_services,
        carbon_benefits=npv_carbon,
        total_benefits=npv_benefits,
        net_present_value=npv_benefits - npv_cost,
        roi=roi,
        carbon_payback_years=carbon_payback_years,
        horizon=horizon,
    )


def compute_carbon_breakeven(
    restoration_cost_total: float,
    maintenance_cost_per_year: float,
    maintenance_years: int,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve],
    carbon_profile: Optional[CarbonProfile],
    units_restored: int,
    substrate_ceiling: float = 1.0,
) -> CarbonBreakeven:
    """Find the carbon price where restoration NPV = 0 from carbon alone.

    Method: breakeven_price = NPV_cost / NPV_absorption_per_euro_per_tonne.

    Args:
        restoration_cost_total: Total restoration cost.
        maintenance_cost_per_year: Annual maintenance cost (total).
        maintenance_years: Number of maintenance years.
        discount: DiscountConfig.
        succession_curve: Optional succession curve.
        carbon_profile: Optional carbon profile.
        units_restored: Number of units.
        substrate_ceiling: Max recoverable fraction.

    Returns:
        CarbonBreakeven analysis.
    """
    horizon: int = discount.horizon_years

    # NPV of restoration costs (independent of carbon price)
    planting_cost: float = restoration_cost_total - (
        maintenance_cost_per_year * maintenance_years
    )
    if planting_cost < 0.0:
        planting_cost = 0.0

    npv_cost: float = planting_cost
    for year in range(1, maintenance_years + 1):
        df: float = discount.discount_factor(year)
        npv_cost += maintenance_cost_per_year * df

    # NPV of absorption stream per euro/tonne carbon price
    npv_absorption_per_euro: float = 0.0
    if carbon_profile is not None and units_restored > 0:
        annual_abs_full: float = (
            units_restored * carbon_profile.annual_absorption_tonnes
        )
        for year in range(horizon):
            if succession_curve is not None:
                sfrac: float = succession_service(succession_curve, float(year))
            else:
                sfrac = 1.0
            effective_sfrac: float = min(sfrac, substrate_ceiling)
            absorption: float = annual_abs_full * effective_sfrac
            df = discount.discount_factor(year)
            npv_absorption_per_euro += absorption * df

    # Breakeven calculation
    if npv_absorption_per_euro > 0.0:
        breakeven_price: float = npv_cost / npv_absorption_per_euro
    else:
        breakeven_price = float('inf')

    current_price: float = discount.carbon_price_current
    gap: float = breakeven_price - current_price
    profitable: bool = breakeven_price <= current_price

    projected_year: Optional[int] = _find_breakeven_year(breakeven_price, discount)

    return CarbonBreakeven(
        breakeven_price=breakeven_price,
        current_price=current_price,
        gap_to_current=gap,
        profitable_at_current=profitable,
        projected_breakeven_year=projected_year,
        npv_cost=npv_cost,
        npv_absorption_per_euro=npv_absorption_per_euro,
    )


def _find_breakeven_year(
    breakeven_price: float,
    discount: DiscountConfig,
    max_years: int = 200,
) -> Optional[int]:
    """Year when rising carbon prices reach breakeven."""
    if breakeven_price == float('inf'):
        return None
    for year in range(max_years):
        if discount.carbon_price_at_year(year) >= breakeven_price:
            return year
    return None


def compute_prevention_advantage_v06(
    foregone_revenue: float,
    restoration_cost_total: float,
    maintenance_cost_per_year: float,
    maintenance_years: int,
    discount: DiscountConfig,
    max_recovered_value: float,
    succession_curve: Optional[SuccessionCurve],
    carbon_profile: Optional[CarbonProfile],
    units: int,
    substrate_ceiling: float = 1.0,
    carbon_released: float = 0.0,
    pa_simple: float = 1.0,
) -> PreventionAdvantageV06:
    """Enhanced prevention advantage with full NPV accounting.

    PA = NPV(total_cost_of_restore_after_extract) / foregone_revenue

    Components layered incrementally:
        pa_simple: v0.2-style undiscounted PA (passed in).
        pa_with_carbon: + carbon externality NPV.
        pa_with_substrate: + permanent substrate loss NPV.
        pa_full: all-inclusive NPV-based PA.

    Args:
        foregone_revenue: Revenue that was earned by extraction.
        restoration_cost_total: Total restoration cost.
        maintenance_cost_per_year: Annual maintenance cost (total).
        maintenance_years: Number of maintenance years.
        discount: DiscountConfig.
        max_recovered_value: Full annual service value at 100% recovery.
        succession_curve: Optional succession curve.
        carbon_profile: Optional carbon profile.
        units: Number of units extracted/restored.
        substrate_ceiling: Max recoverable fraction.
        carbon_released: Total CO2 released.
        pa_simple: The v0.2-style PA (undiscounted).

    Returns:
        PreventionAdvantageV06.
    """
    horizon: int = discount.horizon_years

    if foregone_revenue <= 0.0:
        return PreventionAdvantageV06(
            pa_simple=pa_simple,
            pa_with_carbon=pa_simple,
            pa_with_substrate=pa_simple,
            pa_full=pa_simple,
            npv_prevention_cost=0.0,
            npv_restoration_total=0.0,
        )

    # NPV of restoration costs
    planting_cost: float = restoration_cost_total - (
        maintenance_cost_per_year * maintenance_years
    )
    if planting_cost < 0.0:
        planting_cost = 0.0
    npv_restoration_cost: float = planting_cost
    for year in range(1, maintenance_years + 1):
        df: float = discount.discount_factor(year)
        npv_restoration_cost += maintenance_cost_per_year * df

    # NPV of maturation gap (lost services during recovery)
    npv_maturation_gap: float = 0.0
    for year in range(horizon):
        if succession_curve is not None:
            sfrac: float = succession_service(succession_curve, float(year))
        else:
            sfrac = 1.0
        effective: float = min(sfrac, substrate_ceiling)
        gap_fraction: float = 1.0 - effective
        annual_gap: float = max_recovered_value * gap_fraction
        df = discount.discount_factor(year)
        sf: float = discount.scarcity_factor(year)
        npv_maturation_gap += annual_gap * df * sf

    # Carbon externality NPV
    npv_carbon: float = 0.0
    if carbon_profile is not None and units > 0:
        # Release cost
        total_release: float = units * (
            carbon_profile.stored_carbon_tonnes
            + carbon_profile.soil_carbon_tonnes * carbon_profile.soil_release_fraction
        )
        npv_carbon += total_release * discount.carbon_price_at_year(0)

        # Foregone absorption during recovery
        annual_abs: float = units * carbon_profile.annual_absorption_tonnes
        for year in range(1, min(horizon, 80) + 1):
            if succession_curve is not None:
                sfrac = succession_service(succession_curve, float(year))
            else:
                sfrac = 1.0
            foregone_frac: float = 1.0 - min(sfrac, substrate_ceiling)
            cp: float = discount.carbon_price_at_year(year)
            df = discount.discount_factor(year)
            npv_carbon += annual_abs * foregone_frac * cp * df

    # Substrate permanent loss NPV
    npv_substrate: float = 0.0
    if substrate_ceiling < 1.0:
        permanent_gap: float = 1.0 - substrate_ceiling
        annual_loss: float = max_recovered_value * permanent_gap
        for year in range(horizon):
            df = discount.discount_factor(year)
            sf = discount.scarcity_factor(year)
            npv_substrate += annual_loss * df * sf

    # Build layered PAs
    npv_total_restore: float = (
        npv_restoration_cost + npv_maturation_gap + npv_carbon + npv_substrate
    )

    pa_with_carbon: float = (
        (foregone_revenue + npv_restoration_cost + npv_maturation_gap + npv_carbon)
        / foregone_revenue
    )
    pa_with_substrate: float = (
        (foregone_revenue + npv_restoration_cost + npv_maturation_gap + npv_substrate)
        / foregone_revenue
    )
    pa_full: float = (foregone_revenue + npv_total_restore) / foregone_revenue

    return PreventionAdvantageV06(
        pa_simple=pa_simple,
        pa_with_carbon=pa_with_carbon,
        pa_with_substrate=pa_with_substrate,
        pa_full=pa_full,
        npv_prevention_cost=foregone_revenue,
        npv_restoration_total=npv_total_restore,
    )
