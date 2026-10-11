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

from gaia.carbon import compute_carbon_release, pv_absorption, pv_carbon_release
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


# Every profile prices carbon at the social cost of carbon (DiscountConfig's
# default: gaia.carbon.SOCIAL_COST_OF_CARBON_EUR growing at SCC_GROWTH_RATE,
# 1.3%/yr — below each profile's discount rate). The EU ETS price is only
# available as the market/ETS view, gaia.carbon.with_carbon_price_view.

DISCOUNT_MARKET = DiscountConfig(
    delta=0.015, eta=2.0, g=0.013,
    rate_schedule=0.041,
    scarcity_rate=0.0,
)
"""Conservative / market-aligned (Nordhaus-adjacent). 4.1%, no scarcity."""

DISCOUNT_CENTRAL = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
)
"""Central / consensus (Drupp et al. 2018). 2.3%, 2% scarcity uplift."""

DISCOUNT_ENVIRONMENTAL = DiscountConfig(
    delta=0.001, eta=1.0, g=0.013,
    rate_schedule=0.014,
    scarcity_rate=0.03,
)
"""Environmental / Stern-adjacent. 1.4%, 3% scarcity uplift."""

DISCOUNT_GREEN_BOOK = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[(0, 0.035), (31, 0.030), (76, 0.025)],
    scarcity_rate=0.02,
    horizon_years=125,
)
"""UK Green Book declining schedule. 3.5% -> 3.0% -> 2.5%."""

DEFAULT_DISCOUNT = DISCOUNT_CENTRAL
"""Profile used when a Resource has no DiscountConfig.

Present values are always reported (one-off revenue is only ever compared
with the PV of the yearly externality flow, decision D1), so a resource
without its own configuration falls back to the central Drupp et al. (2018)
consensus profile: 2.3% discount rate, 2% scarcity uplift, 100-year horizon.
Its scarcity growth is below the discount rate, so the PV converges as the
horizon grows.
"""


# ── NPV computation functions ────────────────────────────────────────────────


def compute_extraction_npv(
    annual_externality: float,
    discount: DiscountConfig,
    carbon_profile: Optional[CarbonProfile],
    units_extracted: int,
    substrate_ceiling: float = 1.0,
) -> ExtractionNPV:
    """Discount extraction externality stream to present value.

    The extraction happens at year 0. We then project the annual cost
    streams into the future over the analysis horizon.

    Components:
        direct: Annual ecosystem service loss projected over horizon,
            discounted with scarcity uplift.
        carbon_release: One-time carbon release at year 0, valued at the
            year-0 carbon price (gaia.carbon).
        carbon_foregone: The extracted units' absorption, lost every year
            of the horizon (like the direct loss), valued at the growing
            carbon price and discounted (gaia.carbon).
        substrate_damage: Permanent capacity loss as perpetual annuity.

    Carbon is valued by gaia.carbon alone, at the DiscountConfig's carbon
    price (the social cost of carbon unless the market/ETS view is chosen).

    Args:
        annual_externality: Ecosystem service value lost per year at the
            end state of the extraction (€/yr, a flow).
        discount: DiscountConfig with rate schedule and scarcity parameters.
        carbon_profile: Optional carbon accounting parameters.
        units_extracted: Number of units that were extracted.
        substrate_ceiling: Max recoverable fraction (1.0 = no permanent loss).

    Returns:
        ExtractionNPV with all NPV components.
    """
    horizon: int = discount.horizon_years

    # Direct ecosystem service loss: the annual flow, every year of the horizon
    npv_direct: float = 0.0
    for year in range(horizon):
        df: float = discount.discount_factor(year)
        sf: float = discount.scarcity_factor(year)
        npv_direct += annual_externality * df * sf

    # Carbon (gaia.carbon): release (stock) and foregone absorption (flow → PV)
    release_t: float = 0.0
    absorption_lost_t_yr: float = 0.0
    if carbon_profile is not None and units_extracted > 0:
        release_t = compute_carbon_release(carbon_profile, units_extracted)
        absorption_lost_t_yr = (
            units_extracted * carbon_profile.annual_absorption_tonnes
        )
    npv_carbon_release: float = pv_carbon_release(release_t, discount)
    npv_carbon_foregone: float = pv_absorption(absorption_lost_t_yr, discount)

    # Substrate damage: permanent capacity loss as annuity
    npv_substrate: float = 0.0
    if substrate_ceiling < 1.0:
        permanent_gap: float = 1.0 - substrate_ceiling
        annual_loss: float = annual_externality * permanent_gap
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
        carbon_released_t=release_t,
        carbon_absorption_lost_t_yr=absorption_lost_t_yr,
        carbon_price=discount.carbon_price_at_year(0),
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

    # Carbon absorption benefits (gaia.carbon): the restored units' absorption
    # ramps up along the succession curve, capped by the substrate ceiling
    npv_carbon: float = 0.0
    if carbon_profile is not None and units_restored > 0:
        npv_carbon = pv_absorption(
            units_restored * carbon_profile.annual_absorption_tonnes,
            discount, succession_curve, substrate_ceiling,
        )

    # Carbon payback period (undiscounted)
    carbon_payback_years: Optional[int] = None
    if carbon_profile is not None and carbon_released > 0.0 and units_restored > 0:
        cumulative: float = 0.0
        annual_abs_full: float = (
            units_restored * carbon_profile.annual_absorption_tonnes
        )
        for year in range(horizon):
            if succession_curve is not None:
                sfrac: float = succession_service(succession_curve, float(year))
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
        npv_absorption_per_euro = pv_absorption(
            units_restored * carbon_profile.annual_absorption_tonnes,
            discount, succession_curve, substrate_ceiling, priced=False,
        )

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

    # Carbon externality NPV (gaia.carbon): the release, plus the absorption
    # not delivered while the replanted units mature (and never, above the
    # substrate ceiling)
    npv_carbon: float = 0.0
    if carbon_profile is not None and units > 0:
        npv_carbon = pv_carbon_release(
            compute_carbon_release(carbon_profile, units), discount
        ) + pv_absorption(
            units * carbon_profile.annual_absorption_tonnes,
            discount, succession_curve, substrate_ceiling, shortfall=True,
        )

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
