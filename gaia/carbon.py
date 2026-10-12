"""
Gaia — Carbon accounting: the single owner of carbon value (decision D3).

Implements the double carbon externality (Foundation F9):
    1. Release: CO₂ stored in biomass and soil is released on extraction —
       a one-off stock, valued at the carbon price of the year of release.
    2. Foregone absorption: the absorption capacity of the extracted units
       is lost — an annual flow, valued year by year at the (growing)
       carbon price and discounted to a present value.

No agent rate and no pricing anchor may contain carbon: every euro of
carbon value in Gaia's present values comes from this module.

Carbon price. The default is the social cost of carbon (SCC), not a market
price: an externality tool values the damage a tonne of CO₂ does, not what
an emission allowance trades at. The EU ETS price survives only as an
optional, clearly labelled "market/ETS" view (``with_carbon_price_view``).

Also computes carbon absorption during the maturation timeline and the
carbon payback period (years of restored absorption to recapture the
released carbon).

No third-party dependencies.

Scientific foundations used: F9 (Nutrient Cycles & Carbon Cycle).
"""

import dataclasses
import math
from typing import Optional

from gaia.models import CarbonProfile, DiscountConfig, SuccessionCurve
from gaia.succession import succession_service


# ── Carbon price ─────────────────────────────────────────────────────────────

SCC_USD_2020_PER_T: float = 190.0
"""US EPA (2023) central social cost of CO₂ for emissions in 2020: $190/tCO₂
in 2020 dollars, at the 2.0% near-term Ramsey discount rate. EPA, "Report on
the Social Cost of Greenhouse Gases: Estimates Incorporating Recent
Scientific Advances" (Nov 2023), Table ES.1; Rennert et al. (2022), Nature
610:687-692. EPA's own trajectory puts emissions in 2026 at ~$215; the
headline 2020 value is used as the year-0 price (a conservative anchor)."""

USD_PER_EUR_2020: float = 1.1422
"""ECB euro foreign exchange reference rate, US dollar, 2020 annual average
(USD per EUR). Converts the 2020-dollar SCC into 2020 euros."""

SOCIAL_COST_OF_CARBON_EUR: float = SCC_USD_2020_PER_T / USD_PER_EUR_2020
"""Default carbon price, € (2020) per tonne CO₂: $190 / 1.1422 ≈ €166.35."""

SCC_GROWTH_RATE: float = 0.013
"""Real annual growth of the SCC, from the same EPA table (2.0% column):
$190 for 2020 emissions → $410 for 2080 emissions, (410/190)^(1/60) − 1 =
1.29%/yr. The trajectory decelerates (1.6%/yr over 2020-2050, 1.2%/yr over
2030-2080); the 60-year average is used. It is below the discount rate of
every built-in DiscountConfig (lowest: 1.4%), so carbon present values
converge as the horizon grows."""

ETS_CARBON_PRICE_EUR: float = 80.0
"""Market/ETS view only: EU Emissions Trading System allowance price,
~€80/tCO₂ (2023-2024 average order of magnitude). A private, market price —
never the default for valuing an externality."""

CARBON_PRICE_VIEWS: tuple = ("scc", "ets")
"""Names accepted by with_carbon_price_view (and the --carbon-price flag)."""


def with_carbon_price_view(discount: DiscountConfig, view: str) -> DiscountConfig:
    """Return ``discount`` with the carbon price of the named view.

    ``"scc"`` (default view): the social cost of carbon,
    SOCIAL_COST_OF_CARBON_EUR. ``"ets"``: the market/ETS view,
    ETS_CARBON_PRICE_EUR. Only the year-0 price changes; the growth rate of
    ``discount`` is kept, so the two views differ only in level.

    Raises:
        ValueError: If ``view`` is not one of CARBON_PRICE_VIEWS.
    """
    if view == "scc":
        price: float = SOCIAL_COST_OF_CARBON_EUR
    elif view == "ets":
        price = ETS_CARBON_PRICE_EUR
    else:
        raise ValueError(
            f"carbon price view must be one of {CARBON_PRICE_VIEWS}, got {view!r}"
        )
    return dataclasses.replace(discount, carbon_price_current=price)


def carbon_price_label(discount: DiscountConfig) -> str:
    """Name of the carbon price a DiscountConfig uses, for reports."""
    if discount.carbon_price_current == SOCIAL_COST_OF_CARBON_EUR:
        return "social cost of carbon, US EPA 2023"
    if discount.carbon_price_current == ETS_CARBON_PRICE_EUR:
        return "market/ETS view, not a social cost"
    return "user-supplied"


# ── Physical quantities (tonnes CO₂) ─────────────────────────────────────────


def compute_carbon_release(
    profile: CarbonProfile,
    units_extracted: int,
) -> float:
    """Compute total CO₂ released from extracting resources (a stock).

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


# ── Monetary values (€) ──────────────────────────────────────────────────────


def release_schedule(half_life_years: float, horizon_years: int) -> list:
    """Share of a carbon release that happens during each year 0..H−1.

    A half-life of 0 releases everything at once, in year 0 (``[1.0]``).
    A positive half-life releases it as a negative exponential decay of the
    exposed stock (the profile Pendleton et al. 2012 describe for converted
    coastal soils): the share e^(−λt) − e^(−λ(t+1)) during year t, with
    λ = ln 2 / half-life. The tail released after the horizon,
    e^(−λH), is left out, like every stream beyond the horizon.

    Raises:
        ValueError: If the half-life is negative or not finite.
    """
    if not (math.isfinite(half_life_years) and half_life_years >= 0.0):
        raise ValueError(
            f"release half-life must be a finite number of years >= 0, got {half_life_years!r}"
        )
    if half_life_years == 0.0:
        return [1.0]
    lam: float = math.log(2.0) / half_life_years
    return [math.exp(-lam * t) - math.exp(-lam * (t + 1)) for t in range(horizon_years)]


def pv_carbon_release(
    release_tonnes: float,
    discount: DiscountConfig,
    half_life_years: float = 0.0,
) -> float:
    """Present value of a carbon release (€).

    With a half-life of 0 (the default) the release happens at extraction
    and is valued at the carbon price of year 0, undiscounted. With a
    positive half-life the share released during year t
    (release_schedule) is valued at the carbon price of year t and
    discounted to year 0:

        PV = Σ_{t=0}^{H−1} release × share(t) × price(t) × df(t)

    Each year's tranche is valued at the start of its year, so the PV is
    continuous as the half-life tends to 0. Time enters only through
    discounting (the static engine, decision D5 option B).
    """
    if release_tonnes == 0.0:
        return 0.0
    if half_life_years == 0.0:
        return release_tonnes * discount.carbon_price_at_year(0)
    pv: float = 0.0
    for year, share in enumerate(release_schedule(half_life_years, discount.horizon_years)):
        pv += release_tonnes * share * discount.carbon_price_at_year(year) * discount.discount_factor(year)
    return pv


def _absorption_fraction(
    year: int,
    succession_curve: Optional[SuccessionCurve],
    substrate_ceiling: float,
) -> float:
    """Fraction of mature absorption delivered in ``year``: min(s(t), ceiling)."""
    if succession_curve is not None:
        sfrac: float = succession_service(succession_curve, float(year))
    else:
        sfrac = 1.0
    return min(sfrac, substrate_ceiling)


def pv_absorption(
    annual_tonnes: float,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve] = None,
    substrate_ceiling: float = 1.0,
    shortfall: bool = False,
    priced: bool = True,
) -> float:
    """Present value of an annual CO₂ absorption flow (€ PV).

        PV = Σ_{t=1}^{H} annual_tonnes × f(t) × price(t) × df(t)

    with f(t) = min(s(t), substrate_ceiling), s(t) the succession service
    fraction (1 without a curve), or f(t) = 1 − min(s(t), substrate_ceiling)
    when ``shortfall`` is True (absorption not yet — or never — recovered).
    The year convention (a flow valued at the end of each year t = 1..H) is
    the one of every stream in gaia.discount, so carbon and services cover
    the same years.

    Extraction's foregone absorption is ``pv_absorption(units × absorption,
    discount)``: f = 1 every year of the horizon, like the direct service
    loss, which is also permanent in the extraction view.

    Args:
        annual_tonnes: Mature absorption of the units concerned (t CO₂/yr).
        discount: DiscountConfig (horizon, discount factors, carbon price).
        succession_curve: Optional ramp-up of absorption after restoration.
        substrate_ceiling: Max recoverable fraction (substrate damage).
        shortfall: Value 1 − f(t) instead of f(t).
        priced: If False, price(t) = 1: discounted tonnes per €/t, as used
            by the carbon breakeven.

    Returns:
        Present value in € (or discounted tonnes if ``priced`` is False).
    """
    pv: float = 0.0
    if annual_tonnes == 0.0:
        return pv
    for year in range(1, discount.horizon_years + 1):
        frac: float = _absorption_fraction(year, succession_curve, substrate_ceiling)
        if shortfall:
            frac = 1.0 - frac
        price: float = discount.carbon_price_at_year(year) if priced else 1.0
        pv += annual_tonnes * frac * price * discount.discount_factor(year)
    return pv


def compute_carbon_cost(
    profile: CarbonProfile,
    units_extracted: int,
    discount: DiscountConfig,
) -> dict:
    """Monetize the double carbon externality of an extraction.

    The release is a stock valued at year 0; the foregone absorption is an
    annual flow, reported both in tonnes per year and as a present value.
    Only the two stocks (release and the PV of the flow) are added.

    Returns a breakdown dict with:
        - release_tonnes: t CO₂ released (biomass + soil), a stock
        - foregone_tonnes_per_year: t CO₂/yr of absorption lost, a flow
        - release_cost_eur: € value of the release (one-off, year-0 price)
        - foregone_cost_pv_eur: € PV of the foregone absorption flow
        - total_cost_pv_eur: release_cost_eur + foregone_cost_pv_eur

    Args:
        profile: CarbonProfile for the resource.
        units_extracted: Number of units extracted.
        discount: DiscountConfig with the carbon price and horizon.

    Returns:
        Dict with carbon cost breakdown.
    """
    release: float = compute_carbon_release(profile, units_extracted)
    foregone_per_year: float = profile.annual_absorption_tonnes * units_extracted
    release_cost: float = pv_carbon_release(release, discount, profile.release_half_life_years)
    foregone_pv: float = pv_absorption(foregone_per_year, discount)
    return {
        "release_tonnes": release,
        "foregone_tonnes_per_year": foregone_per_year,
        "release_cost_eur": release_cost,
        "foregone_cost_pv_eur": foregone_pv,
        "total_cost_pv_eur": release_cost + foregone_pv,
    }


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
