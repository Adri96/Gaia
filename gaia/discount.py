"""
Gaia v0.6 -- Discount mechanics, NPV calculations, carbon breakeven.

Implements proper time-value-of-money economics for Gaia. All monetary values
become discountable to present value using Ramsey-based discount rates.

All functions use primitive types for Cython compatibility.
No third-party dependencies.

Year convention (one convention everywhere in Gaia):
    The extraction (or the replanting) happens at year 0. One-off amounts
    at that moment — revenue, the carbon release, planting cost — are
    valued at year 0, undiscounted. A yearly flow is valued at the END of
    each year t = 1..H (H = DiscountConfig.horizon_years):

        PV = Σ_{t=1}^{H} flow(t) × discount_factor(t) × scarcity_factor(t)

    where flow(t) uses the succession service fraction s(t) at t years
    since restoration and the carbon price of year t. Maintenance costs
    (years 1..N), the maturation timeline (years 1..H), the maturation gap,
    carbon absorption (gaia.carbon) and the carbon payback all use the
    same years.

Convergence (C3): gaia.validation.validate_discount_config rejects any
configuration whose scarcity rate or carbon price growth is not strictly
below the discount rate in every year of the horizon, so the PV of a
permanent flow converges as the horizon grows. One approach is used for
the whole code base: a constant relative price change ("scarcity uplift")
strictly below the discount rate, taken from the empirical relative-price
literature — not a scarcity uplift above the discount rate truncated after
an arbitrary period, which would need an invented cut-off year.

Scarcity (relative price change of ecosystem services):
    Drupp, Turk, Groom & Heckenhahn (2024), "Global evidence on the income
    elasticity of willingness to pay, relative price changes and public
    natural capital values", arXiv:2308.04400v3, Table 10: relative price
    change 1.66%/yr for aggregate ecosystem services (95% CI 1.40-1.92%),
    1.28%/yr for forest ecosystem services (95% CI 0.85-1.70%), from an
    income elasticity of WTP of ~0.6 (735 estimates, 396 CV studies) times
    the growth gap between consumption and ecosystem services. The same
    paper (§1) reports the Dutch government default of 1%/yr for all
    ecosystem services (after Baumgärtner et al. 2015) and summarises
    Drupp & Hänsel (2021) as 2-4%/yr in a DICE setting.

Scientific foundations:
    - Ramsey (1928): r = delta + eta * g
    - Stern (2006) vs Nordhaus (2007) debate on delta
    - Drupp et al. (2018): median SDR 2.0% from 200+ economists
    - Weitzman (1998, 2001): declining rates under growth uncertainty
    - Drupp et al. (2024): relative price change 1.3-1.7%/yr (above)
    - UK HM Treasury Green Book: declining schedule 3.5% -> 2.5%
"""

import dataclasses
from typing import Optional

from gaia.carbon import compute_carbon_release, pv_absorption, pv_carbon_release
from gaia.models import (
    CarbonBreakeven,
    CarbonProfile,
    DestroyThenRestorePenalty,
    DiscountConfig,
    ExtractionNPV,
    RestorationNPV,
    SuccessionCurve,
)
from gaia.succession import (
    compute_maturation_gap,
    compute_maturation_timeline,
    succession_service,
)
from gaia.validation import validate_discount_config


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
"""Central / consensus (Drupp et al. 2018). 2.3%, 2% scarcity uplift.

The 2% uplift predates the relative-price evidence in the module docstring
and is above its 95% CIs (to be recalibrated in Step 8); it is below the
discount rate, so the PV converges."""

DISCOUNT_ENVIRONMENTAL = DiscountConfig(
    delta=0.001, eta=1.0, g=0.013,
    rate_schedule=0.014,
    scarcity_rate=0.01,
)
"""Environmental / Stern-adjacent. 1.4%, 1% scarcity uplift.

The discount rate is kept; the uplift was 3%, above it, so the PV grew
without bound with the horizon (C3). 1% is the Dutch government default
relative price change for ecosystem services (Drupp et al. 2024, §1). The
aggregate estimate of the same paper, 1.66%/yr, is itself above 1.4%: with
constant rates, a Stern-adjacent discount rate and the central relative
price change cannot be combined without a divergent PV."""

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


SENSITIVITY_HORIZONS: tuple = (50, 100, 200)
"""Horizons (years) at which each headline PV is also reported, so readers
can see whether the horizon drives the result."""


def horizon_variants(discount: DiscountConfig) -> dict:
    """``discount`` at each of SENSITIVITY_HORIZONS: {horizon: config or None}.

    Validation only checks the schedule segments in force within a config's
    own horizon, so a variant with a longer horizon is validated again; a
    variant that fails validation (its PV would not converge) maps to None.
    """
    variants: dict = {}
    for horizon in SENSITIVITY_HORIZONS:
        config: DiscountConfig = dataclasses.replace(discount, horizon_years=horizon)
        try:
            validate_discount_config(config)
        except ValueError:
            variants[horizon] = None
        else:
            variants[horizon] = config
    return variants


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
        substrate_unrecoverable: The part of ``direct`` that restoration
            could never recover, (1 − substrate_ceiling) of the annual
            loss over the horizon. Informational: it is already inside
            ``direct`` and is NOT added to the total.

    Substrate model: substrate damage reduces the restoration ceiling; it
    is never also a separate permanent flow. The direct loss is already
    permanent here (no recovery within the horizon), so adding a substrate
    annuity on top counted the same loss twice.

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
    for year in range(1, horizon + 1):
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

    # Substrate: the share of the (permanent) direct loss that restoration
    # could never recover. Already in npv_direct, so not added to the total.
    npv_unrecoverable: float = npv_direct * (1.0 - substrate_ceiling)

    total: float = npv_direct + npv_carbon_release + npv_carbon_foregone

    return ExtractionNPV(
        direct=npv_direct,
        carbon_release=npv_carbon_release,
        carbon_foregone=npv_carbon_foregone,
        substrate_unrecoverable=npv_unrecoverable,
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
        max_recovered_value: Biological annual service value at full
            maturity, before the substrate cap (€/yr).
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

    # Costs: planting at year 0 (undiscounted), maintenance at the end of
    # years 1..N
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
    for year in range(1, horizon + 1):
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
        for year in range(1, horizon + 1):
            if succession_curve is not None:
                sfrac: float = succession_service(succession_curve, float(year))
            else:
                sfrac = 1.0
            cumulative += annual_abs_full * min(sfrac, substrate_ceiling)
            if cumulative >= carbon_released:
                carbon_payback_years = year
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


def restoration_cost_ratio(
    foregone_revenue: float, restoration_cost_total: float,
) -> Optional[float]:
    """(foregone revenue + restoration cost) / foregone revenue.

    An input-price ratio: with revenue k × unit_value and cost k × cost per
    unit it is 1 + cost_per_unit / unit_value whatever the ecosystem does.
    It contains no ecology and no externality, and is > 1 by construction
    whenever restoration costs anything; destroy_then_restore_penalty is
    the figure that measures what destroy-then-restore costs society.
    Both amounts are one-off and undiscounted. None when the revenue is 0.
    """
    if foregone_revenue <= 0.0:
        return None
    return (foregone_revenue + restoration_cost_total) / foregone_revenue


def compute_destroy_then_restore_penalty(
    foregone_revenue: float,
    restoration_cost_pv: float,
    annual_damage_reversal: float,
    annual_recovered_potential: float,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve],
    carbon_profile: Optional[CarbonProfile],
    units: int,
    substrate_ceiling: float = 1.0,
) -> DestroyThenRestorePenalty:
    """PV cost of destroying ``units`` and restoring them, over not destroying them.

    penalty = restoration_cost + maturation_gap + substrate_loss
              + recovery_shortfall + carbon_not_recovered        (€ PV)
    ratio   = penalty / foregone_revenue

    See DestroyThenRestorePenalty for each component. Every year t = 1..H
    of the restored flow at maturity before the substrate cap (the
    "biological recovery", B) is split once:

        damage reversal D = delivered(t) + gap(t) + substrate + shortfall
        delivered(t)      = B × min(s(t), c)       (the restoration's benefit)
        gap(t)            = B × (c − min(s(t), c)) (temporary)
        substrate         = B × (1 − c)            (permanent)
        shortfall         = D − B                  (permanent)

    with s the succession service fraction (1 without a curve) and c the
    substrate ceiling, so nothing is counted twice and substrate damage
    only lowers the ceiling. Carbon: the release (year 0) plus the
    absorption shortfall 1 − min(s(t), c) of the units, from gaia.carbon.
    Uses only quantities fixed by Steps 3.1-3.6; no new constants.

    Args:
        foregone_revenue: One-off revenue of cutting the units (€): the
            present value of not cutting, the ratio's denominator.
        restoration_cost_pv: PV of planting and maintenance (€ PV,
            RestorationNPV.cost).
        annual_damage_reversal: Annual externality the cut caused that the
            restoration targets (€/yr).
        annual_recovered_potential: Restored flow at maturity before the
            substrate cap (€/yr), at most annual_damage_reversal.
        discount: DiscountConfig.
        succession_curve: Optional succession curve (None: instant recovery).
        carbon_profile: Optional carbon profile.
        units: Number of units cut and restored.
        substrate_ceiling: Max recoverable fraction.

    Returns:
        DestroyThenRestorePenalty.
    """
    horizon: int = discount.horizon_years

    # Maturation gap: the timeline over the full horizon (years 1..H)
    maturation_gap: float = 0.0
    if succession_curve is not None:
        timeline: list = compute_maturation_timeline(
            succession_curve, annual_recovered_potential, horizon, units,
            None, substrate_ceiling,
        )
        maturation_gap = compute_maturation_gap(
            timeline, annual_recovered_potential * substrate_ceiling, discount
        )

    # Permanent shortfalls: constant flows over years 1..H
    annuity: float = 0.0
    for year in range(1, horizon + 1):
        annuity += discount.discount_factor(year) * discount.scarcity_factor(year)
    substrate_loss: float = (
        annual_recovered_potential * (1.0 - substrate_ceiling) * annuity
    )
    shortfall_flow: float = annual_damage_reversal - annual_recovered_potential
    if shortfall_flow < 0.0:
        shortfall_flow = 0.0
    recovery_shortfall: float = shortfall_flow * annuity

    carbon_not_recovered: float = 0.0
    if carbon_profile is not None and units > 0:
        carbon_not_recovered = pv_carbon_release(
            compute_carbon_release(carbon_profile, units), discount
        ) + pv_absorption(
            units * carbon_profile.annual_absorption_tonnes,
            discount, succession_curve, substrate_ceiling, shortfall=True,
        )

    total: float = (
        restoration_cost_pv + maturation_gap + substrate_loss
        + recovery_shortfall + carbon_not_recovered
    )
    ratio: Optional[float] = (
        total / foregone_revenue if foregone_revenue > 0.0 else None
    )

    return DestroyThenRestorePenalty(
        restoration_cost=restoration_cost_pv,
        maturation_gap=maturation_gap,
        substrate_loss=substrate_loss,
        recovery_shortfall=recovery_shortfall,
        carbon_not_recovered=carbon_not_recovered,
        total=total,
        foregone_revenue=foregone_revenue,
        ratio=ratio,
        horizon=horizon,
    )
