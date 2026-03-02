"""
Gaia v0.6 — NPV computation functions.

Converts Gaia's undiscounted externality and restoration values into
present-value terms using the Ramsey discounting framework.

All functions are pure (no side effects), Cython-compatible:
    - No **kwargs
    - No dynamic attributes
    - All loop variables are primitive floats and ints
    - No third-party dependencies

The key economic interpretation:
    - Extraction externalities are ONGOING annual costs (service losses accrue
      every year until restoration). Their NPV is an annuity discounted at
      (r - scarcity_rate) over the horizon.
    - Carbon release is a ONE-TIME cost at t=0 (already emitted). No discounting.
    - Foregone absorption is a rising ANNUAL cost over the productive lifespan,
      priced at the rising carbon schedule.
    - Substrate damage is a PERMANENT annual loss whose NPV is a perpetuity
      (capped at the analysis horizon).

v0.6: Initial implementation.
"""

from typing import Optional

from gaia.carbon import compute_carbon_release
from gaia.models import (
    CarbonBreakeven,
    DiscountConfig,
    ExtractionNPV,
    PreventionAdvantageV06,
    RestorationNPV,
    RestorationResult,
    SimulationResult,
    SuccessionCurve,
)
from gaia.succession import succession_service


# ── Private helpers ────────────────────────────────────────────────────────────


def _annuity_factor(
    discount: DiscountConfig,
    start_year: int,
    end_year: int,
    scarcity: bool = True,
) -> float:
    """Sum of discount × (optional scarcity) factors over [start_year, end_year].

    Used to compute the present value of a constant annual flow:
        NPV_annuity = annual_flow × _annuity_factor(discount, 1, horizon)

    Args:
        discount: DiscountConfig to use.
        start_year: First year to include (inclusive).
        end_year: Last year to include (inclusive).
        scarcity: If True, multiply each year's factor by scarcity_factor(t).

    Returns:
        Sum of discount_factor(t) × scarcity_factor(t) for t in [start, end].
    """
    total: float = 0.0
    for t in range(start_year, end_year + 1):
        df: float = discount.discount_factor(t)
        if scarcity:
            df = df * discount.scarcity_factor(t)
        total += df
    return total


def _find_breakeven_year(
    breakeven_price: float,
    discount: DiscountConfig,
) -> Optional[int]:
    """First year when the rising carbon price reaches breakeven_price.

    Scans years 0..199. Returns None if breakeven is never reached.
    """
    for year in range(200):
        if discount.carbon_price_at_year(year) >= breakeven_price:
            return year
    return None


def _service_fraction_at_year(
    year: int,
    maturation_timeline: list,
    succession_curve: Optional[SuccessionCurve],
) -> float:
    """Service fraction at a given year, using timeline then succession curve.

    Checks maturation_timeline first (year-indexed). Falls back to succession_service().
    Falls back to 1.0 (immediate full recovery) if neither is available.
    """
    # Fast path: timeline lookup (O(1) if list is year-ordered, O(n) otherwise)
    for step in maturation_timeline:
        if step.year == year:
            return step.service_fraction
    if succession_curve is not None:
        return succession_service(succession_curve, year)
    return 1.0


def _absorption_at_year(
    year: int,
    units_restored: int,
    maturation_timeline: list,
    succession_curve: Optional[SuccessionCurve],
    annual_absorption_per_unit: float,
) -> float:
    """Annual carbon absorption at a given year (in tonnes CO₂).

    Uses maturation timeline if available (total tonnes already computed per year),
    otherwise derives from succession curve × per-unit absorption rate,
    otherwise uses constant per-unit rate (full immediate absorption).
    """
    for step in maturation_timeline:
        if step.year == year:
            return step.annual_carbon_absorbed
    svc_frac: float
    if succession_curve is not None:
        svc_frac = succession_service(succession_curve, year)
    else:
        svc_frac = 1.0
    return annual_absorption_per_unit * units_restored * svc_frac


# ── Public computation functions ───────────────────────────────────────────────


def compute_extraction_npv(
    result: SimulationResult,
    discount: DiscountConfig,
) -> ExtractionNPV:
    """Compute the NPV of extraction externalities.

    The extraction is treated as instantaneous at t=0. The externalities
    then generate ongoing annual costs (ecosystem service losses) which are
    discounted over the analysis horizon.

    Four NPV components:

    1. npv_direct — PV of annual ecosystem service losses:
       annual_loss × Σ[t=1..H] scarcity_factor(t) × discount_factor(t)

    2. npv_carbon_release — one-time carbon release at t=0:
       release_tonnes × carbon_price_at_year(0)   (discount_factor(0) = 1.0)

    3. npv_carbon_foregone — PV of foregone annual absorption:
       annual_absorption × Σ[t=1..min(remaining_yrs,H)] carbon_price(t) × discount_factor(t)

    4. npv_substrate — PV of permanent capacity loss (if v0.5 substrate present):
       annual_substrate_loss × Σ[t=1..H] scarcity_factor(t) × discount_factor(t)
       using closed-form perpetuity when r_net = rate - scarcity_rate > 0.

    Args:
        result: SimulationResult from run_extraction().
        discount: DiscountConfig with rate, scarcity, carbon price trajectory.

    Returns:
        ExtractionNPV with four components and total.
    """
    resource = result.ecosystem.resource
    units: int = result.total_units_extracted
    horizon: int = discount.horizon_years
    annual_loss: float = result.total_externality_cost

    # ── Component 1: Direct externality annuity ────────────────────────────
    npv_direct: float = annual_loss * _annuity_factor(
        discount, 1, horizon, scarcity=True
    )

    # ── Component 2: Carbon release (immediate, t=0) ───────────────────────
    npv_carbon_release: float = 0.0
    npv_carbon_foregone: float = 0.0
    if resource.carbon_profile is not None and units > 0:
        release_tonnes: float = compute_carbon_release(resource.carbon_profile, units)
        npv_carbon_release = release_tonnes * discount.carbon_price_at_year(0)

        # ── Component 3: Foregone absorption (future stream) ──────────────
        annual_absorption: float = (
            resource.carbon_profile.annual_absorption_tonnes * units
        )
        productive_years: int = min(
            discount.remaining_productive_years, horizon
        )
        for y in range(1, productive_years + 1):
            npv_carbon_foregone += (
                annual_absorption
                * discount.carbon_price_at_year(y)
                * discount.discount_factor(y)
            )

    # ── Component 4: Permanent substrate capacity loss ─────────────────────
    npv_substrate: float = 0.0
    if resource.substrate is not None and result.steps:
        k_fraction_final: float = result.steps[-1].k_fraction
        permanent_loss: float = 1.0 - k_fraction_final
        if permanent_loss > 1e-9:
            annual_substrate_loss: float = annual_loss * permanent_loss
            # Closed-form perpetuity for constant rates (fast)
            if isinstance(discount.rate_schedule, (int, float)):
                r_net: float = float(discount.rate_schedule) - discount.scarcity_rate
                if r_net > 1e-6:
                    # Perpetuity capped at horizon
                    annuity: float = _annuity_factor(
                        discount, 1, horizon, scarcity=True
                    )
                    npv_substrate = annual_substrate_loss * annuity
                else:
                    # Net rate ≈ 0 or negative: cap at horizon years
                    npv_substrate = annual_substrate_loss * float(horizon)
            else:
                # Declining schedule: sum numerically
                npv_substrate = annual_substrate_loss * _annuity_factor(
                    discount, 1, horizon, scarcity=True
                )

    total: float = (
        npv_direct + npv_carbon_release + npv_carbon_foregone + npv_substrate
    )

    return ExtractionNPV(
        direct=npv_direct,
        carbon_release=npv_carbon_release,
        carbon_foregone=npv_carbon_foregone,
        substrate_damage=npv_substrate,
        total=total,
        horizon=horizon,
        discount_config=discount,
    )


def compute_restoration_npv(
    result: RestorationResult,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve] = None,
) -> RestorationNPV:
    """Compute the NPV of restoration as an investment.

    Costs are discounted from their scheduled payment years.
    Benefits (service recovery + carbon absorption) are discounted from
    each future year's value, scarcity-adjusted.

    Cost schedule: planting at t=0; maintenance at t=1..maintenance_years.
    Service benefits: from maturation_timeline if available, else succession_curve,
    else flat (immediate full recovery). Each year's value is scarcity-adjusted.
    Carbon benefits: from maturation_timeline annual_carbon_absorbed per year,
    priced at rising carbon price.

    Args:
        result: RestorationResult from run_restoration().
        discount: DiscountConfig with rate, scarcity, carbon price trajectory.
        succession_curve: Optional SuccessionCurve for benefit recovery profile
            (used when maturation_timeline is absent).

    Returns:
        RestorationNPV with costs, service benefits, carbon benefits, NPV, ROI.
    """
    resource = result.ecosystem.resource
    units: int = result.total_units_restored
    horizon: int = discount.horizon_years
    rc = result.restoration_cost
    substrate_ceiling: float = result.substrate_ceiling

    # ── Costs: planting at t=0, maintenance at t=1..maintenance_years ─────
    npv_cost: float = units * rc.planting_cost_per_unit  # year 0: no discount
    for y in range(1, rc.maintenance_years + 1):
        npv_cost += (
            units
            * rc.annual_maintenance_per_unit
            * discount.discount_factor(y)
        )

    # ── Service benefits: year-by-year recovery ───────────────────────────
    npv_services: float = 0.0
    max_services: float = result.total_recovered_value
    timeline: list = result.maturation_timeline
    for year in range(1, horizon + 1):
        svc_frac: float = _service_fraction_at_year(
            year, timeline, succession_curve
        )
        effective_frac: float = min(svc_frac, substrate_ceiling)
        annual_svc: float = max_services * effective_frac
        npv_services += (
            annual_svc
            * discount.discount_factor(year)
            * discount.scarcity_factor(year)
        )

    # ── Carbon absorption benefits ─────────────────────────────────────────
    npv_carbon: float = 0.0
    annual_per_unit: float = 0.0
    if resource.carbon_profile is not None:
        annual_per_unit = resource.carbon_profile.annual_absorption_tonnes
        for year in range(1, horizon + 1):
            absorption_yr: float = _absorption_at_year(
                year, units, timeline, succession_curve, annual_per_unit
            )
            npv_carbon += (
                absorption_yr
                * discount.carbon_price_at_year(year)
                * discount.discount_factor(year)
            )

    # ── Carbon payback period (undiscounted) ──────────────────────────────
    carbon_payback: Optional[int] = None
    if resource.carbon_profile is not None and units > 0:
        carbon_released: float = compute_carbon_release(resource.carbon_profile, units)
        cumulative_absorption: float = 0.0
        for year in range(1, 501):  # scan up to 500yr
            cumulative_absorption += _absorption_at_year(
                year, units, timeline, succession_curve, annual_per_unit
            )
            if cumulative_absorption >= carbon_released:
                carbon_payback = year
                break

    total_benefits: float = npv_services + npv_carbon
    roi: float = total_benefits / npv_cost if npv_cost > 1e-9 else 0.0

    return RestorationNPV(
        cost=npv_cost,
        service_benefits=npv_services,
        carbon_benefits=npv_carbon,
        total_benefits=total_benefits,
        net_present_value=total_benefits - npv_cost,
        roi=roi,
        carbon_payback_years=carbon_payback,
        horizon=horizon,
        discount_config=discount,
    )


def carbon_breakeven(
    result: RestorationResult,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve] = None,
) -> CarbonBreakeven:
    """Find the carbon price at which restoration NPV = 0 from carbon credits alone.

    Computes:
        breakeven_price = npv_cost / npv_absorption_per_euro

    Where npv_absorption_per_euro is the discounted sum of all future absorption
    normalized to €1/tonne carbon price (i.e., with carbon_price = 1.0 everywhere).

    Args:
        result: RestorationResult from run_restoration().
        discount: DiscountConfig with rate schedule and horizon.
        succession_curve: Optional SuccessionCurve for absorption profile.

    Returns:
        CarbonBreakeven with breakeven_price, market gap, and projected breakeven year.
    """
    resource = result.ecosystem.resource
    units: int = result.total_units_restored
    horizon: int = discount.horizon_years
    rc = result.restoration_cost

    # Same cost schedule as compute_restoration_npv
    npv_cost: float = units * rc.planting_cost_per_unit
    for y in range(1, rc.maintenance_years + 1):
        npv_cost += (
            units
            * rc.annual_maintenance_per_unit
            * discount.discount_factor(y)
        )

    # NPV of absorption normalized to €1/tonne (with rising carbon price = 1.0)
    # Note: carbon price trajectory is NOT applied here; we want absorption per €1
    # so we can solve for the breakeven price analytically.
    npv_absorption_per_euro: float = 0.0
    annual_per_unit: float = 0.0
    if resource.carbon_profile is not None:
        annual_per_unit = resource.carbon_profile.annual_absorption_tonnes
        timeline: list = result.maturation_timeline
        for year in range(1, horizon + 1):
            absorption_yr: float = _absorption_at_year(
                year, units, timeline, succession_curve, annual_per_unit
            )
            npv_absorption_per_euro += (
                absorption_yr * discount.discount_factor(year)
            )

    # Breakeven price: cost = breakeven × absorption_annuity
    if npv_absorption_per_euro > 1e-9:
        breakeven_price: float = npv_cost / npv_absorption_per_euro
    else:
        breakeven_price = float("inf")

    current_price: float = discount.carbon_price_current
    gap: float = breakeven_price - current_price
    profitable: bool = breakeven_price <= current_price

    projected_year: Optional[int] = None
    if breakeven_price < float("inf"):
        projected_year = _find_breakeven_year(breakeven_price, discount)

    return CarbonBreakeven(
        breakeven_price=breakeven_price,
        current_price=current_price,
        gap_to_current=gap,
        profitable_at_current=profitable,
        projected_breakeven_year=projected_year,
        npv_cost=npv_cost,
        npv_absorption_per_euro=npv_absorption_per_euro,
    )


def compute_prevention_advantage_v06(
    restoration_result: RestorationResult,
    discount: DiscountConfig,
    succession_curve: Optional[SuccessionCurve] = None,
) -> PreventionAdvantageV06:
    """Compute the prevention advantage at four levels of NPV sophistication.

    All inputs are derived from the restoration result and its ecosystem resource,
    treating `units_to_restore` as a proxy for the number of units that were
    extracted (and subsequently restored).

    Levels:
        pa_simple:         v0.2-style (undiscounted restoration cost / foregone revenue)
        pa_with_carbon:    + NPV of carbon externality (release + foregone absorption)
        pa_with_substrate: + NPV of permanent substrate capacity loss
        pa_full:           + NPV of maturation gap (services lost during recovery)

    The prevention cost is the foregone extraction revenue (opportunity cost
    of not extracting), treated as occurring at t=0 (no discounting needed).

    Args:
        restoration_result: RestorationResult from run_restoration().
        discount: DiscountConfig to use.
        succession_curve: Optional SuccessionCurve for service recovery profile.

    Returns:
        PreventionAdvantageV06 with four PA metrics.
    """
    resource = restoration_result.ecosystem.resource
    units: int = restoration_result.total_units_restored
    unit_value: float = resource.unit_value
    horizon: int = discount.horizon_years

    # NPV of prevention cost = foregone revenue (immediate, t=0, no discounting)
    npv_prevention_cost: float = units * unit_value

    # pa_simple: existing v0.2/v0.5 ratio
    pa_simple: float = restoration_result.prevention_advantage

    # Get (or reuse) the restoration NPV
    restore_npv: RestorationNPV
    if restoration_result.npv is not None:
        restore_npv = restoration_result.npv
    else:
        restore_npv = compute_restoration_npv(
            restoration_result, discount, succession_curve
        )

    # pa_with_carbon: restoration cost NPV + carbon externality NPV
    # Carbon externality = release at t=0 + foregone absorption stream
    carbon_ext_npv: float = 0.0
    if resource.carbon_profile is not None:
        release_tonnes: float = compute_carbon_release(
            resource.carbon_profile, units
        )
        carbon_ext_npv = release_tonnes * discount.carbon_price_at_year(0)
        annual_absorption: float = (
            resource.carbon_profile.annual_absorption_tonnes * units
        )
        productive_yrs: int = min(
            discount.remaining_productive_years, horizon
        )
        for y in range(1, productive_yrs + 1):
            carbon_ext_npv += (
                annual_absorption
                * discount.carbon_price_at_year(y)
                * discount.discount_factor(y)
            )

    total_with_carbon: float = restore_npv.cost + carbon_ext_npv
    pa_with_carbon: float = (
        (npv_prevention_cost + total_with_carbon) / npv_prevention_cost
        if npv_prevention_cost > 1e-9 else 1.0
    )

    # pa_with_substrate: add NPV of permanent capacity loss
    # Uses substrate_ceiling from v0.5 (already computed in run_restoration)
    substrate_npv: float = 0.0
    if resource.substrate is not None:
        permanent_loss: float = 1.0 - restoration_result.substrate_ceiling
        if permanent_loss > 1e-9:
            # Annual service value permanently lost
            annual_substrate_loss: float = (
                restoration_result.total_recovered_value * permanent_loss
            )
            substrate_npv = annual_substrate_loss * _annuity_factor(
                discount, 1, horizon, scarcity=True
            )

    total_with_substrate: float = total_with_carbon + substrate_npv
    pa_with_substrate: float = (
        (npv_prevention_cost + total_with_substrate) / npv_prevention_cost
        if npv_prevention_cost > 1e-9 else 1.0
    )

    # pa_full: also add the maturation gap NPV
    # Maturation gap = services lost during recovery period. Approximate its
    # NPV by discounting to the mid-point of the recovery window.
    maturation_gap: float = restoration_result.total_maturation_gap
    maturation_gap_npv: float = 0.0
    if maturation_gap > 1e-9:
        yrs_to_90: float = restoration_result.years_to_90pct
        if yrs_to_90 > 0:
            mid_year: int = max(1, int(yrs_to_90 / 2))
            maturation_gap_npv = maturation_gap * discount.discount_factor(mid_year)
        else:
            maturation_gap_npv = maturation_gap

    npv_restoration_total: float = total_with_substrate + maturation_gap_npv
    pa_full: float = (
        (npv_prevention_cost + npv_restoration_total) / npv_prevention_cost
        if npv_prevention_cost > 1e-9 else 1.0
    )

    return PreventionAdvantageV06(
        pa_simple=pa_simple,
        pa_with_carbon=pa_with_carbon,
        pa_with_substrate=pa_with_substrate,
        pa_full=pa_full,
        npv_prevention_cost=npv_prevention_cost,
        npv_restoration_total=npv_restoration_total,
    )
