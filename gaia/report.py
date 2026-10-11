"""
Gaia — Text report generation.

Produces plain-text reports from simulation results.
No dependencies — pure string formatting with the standard library only.

Step 6.3 (E3): this module only formats. Every figure it prints is a field
of SimulationResult / RestorationResult (or of the objects they hold), and
gaia.serialization writes the same fields, so the text and JSON outputs
cannot disagree.

v0.1: format_report()           — externality report from run_extraction()
v0.2: format_restoration_report() — restoration report from run_restoration()
v0.3: Cascade breakdown (direct vs propagated damage, trophic amplification,
      keystone threshold warnings) added to externality report.
v0.4: Resilience Assessment, Carbon Accounting sections in extraction report;
      Maturation Timeline, Carbon Recovery sections in restoration report.
v0.5: Substrate Impact Assessment in extraction report;
      Substrate Restoration Ceiling in restoration report.
v0.6: NPV Analysis section in extraction report;
      Investment Analysis (NPV), Carbon Credit Breakeven sections in
      restoration report.
Step 3.7: Restoration Cost Ratio and Destroy-then-Restore Penalty replace
      the prevention-advantage sections.
v0.7: Price Decomposition section in extraction report
      (endogenous pricing with scarcity and demand multipliers).
"""

from gaia.carbon import carbon_price_label
from gaia.models import (
    Agent,
    Ecosystem,
    RestorationCost,
    RestorationResult,
    Resource,
    SimulationResult,
)

# Report width (characters)
_WIDTH: int = 63
_DOUBLE_LINE: str = "=" * _WIDTH
_SINGLE_LINE: str = "-" * _WIDTH


def _recovery_years_text(years: float) -> str:
    """Substrate recovery time for the report (inf: never recovers)."""
    if years == float("inf"):
        return f"{'never':>10} (no substrate formation)"
    return f"{years:>10,.0f} years"


def _rate_schedule_text(discount) -> str:
    """The configured discount rate schedule, e.g. "2.3%" or
    "4.0% (years 0-29), 3.0% (years 30+)"."""
    schedule = discount.rate_schedule
    if isinstance(schedule, (int, float)):
        return f"{float(schedule):.1%}"
    parts: list = []
    for i, (year, rate) in enumerate(schedule):
        if i + 1 < len(schedule):
            parts.append(f"{rate:.1%} (years {year}-{schedule[i + 1][0] - 1})")
        else:
            parts.append(f"{rate:.1%} (years {year}+)")
    return ", ".join(parts)


def _horizon_sensitivity_lines(by_horizon: dict) -> list:
    """Lines showing a headline PV at each sensitivity horizon."""
    if not by_horizon:
        return []
    lines: list = ["    Horizon sensitivity (\u20ac PV):"]
    for horizon, value in by_horizon.items():
        label: str = f"{horizon}-year horizon:"
        if value is None:
            lines.append(f"      {label:<34} {'n/a (does not converge)':>16}")
        else:
            lines.append(f"      {label:<34} \u20ac{value:>14,.0f}")
    return lines


# Shown at the top of every extraction report that used endogenous pricing.
_PRICING_BANNER: list = [
    "  \u26a0  EXPERIMENTAL: endogenous pricing (--with-pricing) is quarantined",
    "     (decision D4, C8). Every price below is certified convergent, but the",
    "     formulation counts upstream value once per dependent agent, prices",
    "     the whole loss at the end-state scarcity price, and most anchors are",
    "     placeholders. Do not use these figures as estimates.",
]


def format_report(result: SimulationResult) -> str:
    """
    Format a SimulationResult into a human-readable plain-text externality report.

    Monetary units are explicit on every line: "€/yr" is a yearly flow,
    "€ (PV)" a present value at year 0, "€ (one-off)" an undiscounted
    one-off amount. Flows and stocks are never added or compared.

    The report shows:
        - Resource state and depletion
        - One-off private revenue from extraction
        - Per-agent annual externality (€/yr) with descriptions
        - Annual externality (€/yr) and its present value (€ PV)
        - Net social cost = PV of externality − revenue
          (positive = society loses more than the extractor gains)
        - v0.4: Resilience Assessment, Carbon Accounting
        - v0.5: Substrate Impact Assessment
        - v0.6: NPV Analysis (100-year horizon with Ramsey discounting)
        - v0.7: Price Decomposition (endogenous pricing)

    Args:
        result: A completed SimulationResult from run_extraction().

    Returns:
        A multi-line string suitable for printing to stdout.
    """
    ecosystem: Ecosystem = result.ecosystem
    resource: Resource = ecosystem.resource
    agents: list = ecosystem.agents

    final_depletion: float = (
        result.total_units_extracted / resource.total_units
        if resource.total_units > 0 else 0.0
    )

    # Per-agent annual cost (€/yr) at the final depletion level
    if result.steps:
        final_agent_costs: list = result.steps[-1].agent_annual_costs
        final_direct_damages: list = result.steps[-1].agent_direct_damages
        final_cascade_damages: list = result.steps[-1].agent_cascade_damages
    else:
        final_agent_costs = [0.0] * len(agents)
        final_direct_damages = []
        final_cascade_damages = []

    # v0.3: Check if cascade data is present (non-empty direct_damages list)
    has_cascade_data: bool = len(final_direct_damages) > 0

    lines: list = []

    # Header
    lines.append(_DOUBLE_LINE)
    title: str = f"GAIA \u2014 Externality Report: {ecosystem.name}"
    lines.append(f"  {title}")
    lines.append(_DOUBLE_LINE)
    lines.append("")
    if ecosystem.pricing is not None:
        lines.extend(_PRICING_BANNER)
        lines.append("")

    # Resource state
    lines.append(
        f"  {'Resource:':<18} {resource.total_units:>10,} units  ({resource.name})"
    )
    lines.append(
        f"  {'Area:':<18} {resource.area_ha:>10,.1f} ha     "
        f"({resource.units_per_ha:,.1f} units/ha)"
    )
    lines.append(
        f"  {'Safe Threshold:':<18} {resource.safe_threshold_units:>10,} units  "
        f"({resource.safe_threshold_ratio:.1%})"
    )
    lines.append(
        f"  {'Units Extracted:':<18} {result.total_units_extracted:>10,}"
    )
    lines.append(
        f"  {'Depletion:':<18} {final_depletion:>10.1%}"
    )
    lines.append(
        f"  {'Ecosystem Health:':<18} {result.final_ecosystem_health:>10.1%}"
    )
    lines.append("")

    # Private gains
    lines.append("  \u2500\u2500 Private Gains \u2500" + "\u2500" * 46)
    lines.append(
        f"  {'Revenue:':<40} {result.revenue:>14,.2f}\u20ac (one-off)"
    )
    lines.append("")

    # Externalized costs (yearly flows)
    lines.append("  \u2500\u2500 Annual Externalized Costs \u2500" + "\u2500" * 34)

    agent: Agent
    for i, agent in enumerate(agents):
        cost: float = final_agent_costs[i] if i < len(final_agent_costs) else 0.0
        lines.append(
            f"  {agent.name + ':':<40} {cost:>14,.2f}\u20ac/yr"
        )
        lines.append(f"    \u2192 {agent.description}")

        # v0.3: Cascade breakdown (only when cascade data is present)
        if has_cascade_data and i < len(final_cascade_damages):
            if final_cascade_damages[i] > 1e-6:
                lines.append(
                    f"    \u2192 Direct: \u20ac{result.agent_direct_annual_costs[i]:,.0f}/yr | "
                    f"Cascade: \u20ac{result.agent_cascade_annual_costs[i]:,.0f}/yr"
                )

            # Show trophic amplification for consumers
            if agent.trophic_level >= 1:
                # The raw amplification factor (not capped damage)
                amp: float = result.agent_trophic_amplification[i]
                level_names = {
                    1: "primary consumer",
                    2: "secondary consumer",
                    3: "tertiary consumer",
                }
                level_name = level_names.get(agent.trophic_level, "consumer")
                lines.append(
                    f"    \u2192 Trophic amplification: {amp:.1f}\u00d7 ({level_name})"
                )

    lines.append("")

    # v0.3: Keystone threshold crossings
    if has_cascade_data:
        # Collect all keystone crossings across all steps
        keystone_crossings: dict = {}  # agent_name -> first step number
        for s in result.steps:
            for kname in s.keystone_triggered:
                if kname not in keystone_crossings:
                    keystone_crossings[kname] = s.step
        if keystone_crossings:
            lines.append(
                "  \u2500\u2500 Keystone Threshold Crossings \u2500" + "\u2500" * 31
            )
            for kname, kstep in sorted(keystone_crossings.items(), key=lambda x: x[1]):
                depletion_at_cross: float = kstep / resource.total_units
                lines.append(
                    f"  \u26a0 {kname}: crossed at step {kstep:,} "
                    f"({depletion_at_cross:.0%} depletion)"
                )
            lines.append("")

    # Totals: the annual flow, its present value, and the net social cost
    lines.append(
        f"  {'ANNUAL EXTERNALITY:':<40} {result.annual_externality:>14,.2f}\u20ac/yr"
    )
    lines.append(
        f"  {'PV OF EXTERNALITY:':<40} {result.pv_externality:>14,.2f}\u20ac (PV)"
    )
    if result.extraction_npv is not None:
        lines.append(
            f"    (services and carbon over "
            f"{result.extraction_npv.horizon} years; see NPV Analysis)"
        )
    lines.extend(_horizon_sensitivity_lines(result.pv_externality_by_horizon))
    lines.append(f"  {_SINGLE_LINE}")

    # Net social cost: PV of externality - one-off revenue
    # Positive = society loses more than the extractor gains
    net: float = result.net_social_cost
    net_label: str = "NET SOCIAL COST (PV \u2212 revenue):"
    lines.append(
        f"  {net_label:<40} {net:>14,.2f}\u20ac (PV)"
    )
    if result.discount_is_default:
        lines.append(
            "    (no DiscountConfig on the resource: default central profile used)"
        )

    # v0.4: Resilience Assessment
    if result.steps and result.steps[-1].resilience_zone != "green":
        lines.append("")
        lines.append("  \u2500\u2500 Resilience Assessment \u2500" + "\u2500" * 38)
        final_step = result.steps[-1]
        zone_label = final_step.resilience_zone.upper()
        zone_symbol = {
            "green": "\u2705", "yellow": "\u26a0", "red": "\u26a0\u26a0"
        }.get(final_step.resilience_zone, "")
        zone_desc = {
            "green": "Ecosystem likely resilient",
            "yellow": "Resilience uncertain",
            "red": "Resilience likely compromised",
        }.get(final_step.resilience_zone, "")
        lines.append(
            f"  Current zone:          {zone_symbol} {zone_label} \u2014 {zone_desc}"
        )
        lines.append(
            f"  Model confidence:      {final_step.model_confidence:.0%}"
        )

        # Zone transitions
        transitions: list = []
        prev_zone: str = "green"
        for s in result.steps:
            if s.resilience_zone != prev_zone:
                depl_pct = s.depletion_ratio * 100
                transitions.append(
                    f"{prev_zone.title()} \u2192 {s.resilience_zone.title()} "
                    f"at step {s.step:,} ({depl_pct:.0f}% depletion)"
                )
                prev_zone = s.resilience_zone
        if transitions:
            lines.append("  Zone transitions:")
            for t in transitions:
                lines.append(f"    {t}")

        # Irreversibility warning
        if final_step.irreversibility_warning:
            irrev_step = None
            for s in result.steps:
                if s.irreversibility_warning:
                    irrev_step = s.step
                    break
            if irrev_step is not None:
                depl_pct = irrev_step / resource.total_units * 100
                lines.append("")
                lines.append(
                    f"  \u26a0 IRREVERSIBILITY WARNING at step {irrev_step:,} "
                    f"({depl_pct:.0f}% depletion)"
                )
                lines.append(
                    "    Ecosystem damage may be partially irreversible."
                )

    # v0.4: Carbon Accounting — every figure comes from extraction_npv
    # (gaia.carbon), so the text and the JSON output agree
    npv_c = result.extraction_npv
    if (resource.carbon_profile is not None and result.total_units_extracted > 0
            and npv_c is not None):
        lines.append("")
        lines.append("  \u2500\u2500 Carbon Accounting \u2500" + "\u2500" * 42)
        lines.append(
            f"  {'Carbon released (biomass+soil):':<40} "
            f"{npv_c.carbon_released_t:>10,.0f} t CO\u2082"
        )
        lines.append(
            f"  {'Future absorption lost:':<40} "
            f"{npv_c.carbon_absorption_lost_t_yr:>10,.1f} t CO\u2082/yr"
        )
        lines.append(
            f"  {'Carbon price (year 0):':<40} "
            f"{npv_c.carbon_price:>10,.2f}\u20ac/t CO\u2082"
        )
        lines.append(
            f"  {'Carbon externality (release):':<40} "
            f"{npv_c.carbon_release:>14,.2f}\u20ac (one-off)"
        )
        lines.append(
            f"  {'Carbon externality (absorption lost):':<40} "
            f"{npv_c.carbon_foregone:>14,.2f}\u20ac (PV)"
        )

    # v0.4: Heuristic band on the annual externality (not a statistical
    # interval; see SimulationResult.annual_externality_band)
    if result.annual_externality_band is not None:
        lower, upper = result.annual_externality_band
        lines.append("")
        lines.append(
            "  \u2500\u2500 Externality Band (heuristic) \u2500" + "\u2500" * 31
        )
        lines.append(
            f"  {'Annual Externality:':<40} {result.annual_externality:>14,.2f}\u20ac/yr"
        )
        lines.append(
            f"  Band at {result.final_model_confidence:.0%} confidence:"
            f"      {lower:>12,.2f}\u20ac/yr \u2014 {upper:>12,.2f}\u20ac/yr"
        )
        lines.append(
            "    (heuristic: \u00b1(1 \u2212 confidence); not a statistical interval)"
        )

    # v0.5: Substrate Impact Assessment
    if resource.substrate is not None and result.steps:
        final_step = result.steps[-1]
        if final_step.k_fraction < 1.0:
            lines.append("")
            lines.append(
                "  \u2500\u2500 Substrate Impact Assessment \u2500" + "\u2500" * 31
            )
            sub = resource.substrate
            lines.append(
                f"  {'Substrate type:':<40} {sub.substrate_type}"
            )
            if sub.soil_depth_cm is not None:
                # Compute soil lost from substrate erosion trajectory
                soil_lost_pct: float = (1.0 - final_step.k_fraction) * 100
                lines.append(
                    f"  {'Pristine soil depth:':<40} {sub.soil_depth_cm:>10.1f} cm"
                )
                lines.append(
                    f"  {'Capacity lost:':<40} {soil_lost_pct:>10.1f}%"
                )
            if sub.sediment_stability is not None:
                stability_lost_pct: float = (1.0 - final_step.k_fraction) * 100
                lines.append(
                    f"  {'Pristine stability:':<40} {sub.sediment_stability:>10.2f}"
                )
                lines.append(
                    f"  {'Capacity lost:':<40} {stability_lost_pct:>10.1f}%"
                )
            lines.append("")
            lines.append(
                f"  {'Pristine K:':<40} {resource.total_units:>10,} units"
            )
            lines.append(
                f"  {'Current K:':<40} {final_step.effective_k:>10,} units"
            )
            capacity_lost: int = resource.total_units - final_step.effective_k
            lines.append(
                f"  {'Capacity lost permanently:':<40} {capacity_lost:>10,} units"
            )

            # Recovery time of the substrate state the extraction ended in
            # (the same state a restoration starts from)
            if result.substrate_recovery_years is not None:
                lines.append(
                    f"  {'Years to pristine substrate:':<40} "
                    f"{_recovery_years_text(result.substrate_recovery_years)}"
                )

    # v0.6: NPV Analysis
    if result.extraction_npv is not None:
        npv = result.extraction_npv
        discount = result.discount
        lines.append("")
        lines.append(
            f"  \u2500\u2500 NPV Analysis ({npv.horizon}-year horizon) \u2500"
            + "\u2500" * 28
        )
        if discount is not None:
            lines.append("")
            lines.append(f"  Discount rate: {_rate_schedule_text(discount)}")
            lines.append(
                f"  Ramsey components (reference): "
                f"\u03b4={discount.delta:.1%}, "
                f"\u03b7={discount.eta:.2f}, "
                f"g={discount.g:.1%}"
            )
            lines.append(
                f"  Scarcity uplift: {discount.scarcity_rate:.1%}/yr "
                f"on ecosystem services"
            )
            lines.append(
                f"  Carbon price: \u20ac{discount.carbon_price_current:,.0f}/t "
                f"growing at {discount.carbon_price_growth:.1%}/yr"
            )
            lines.append(f"    ({carbon_price_label(discount)})")

        lines.append("")
        lines.append("  Externality present value (\u20ac PV at year 0):")
        lines.append(
            f"    {'Ecosystem services (annual flow):':<36} "
            f"\u20ac{npv.direct:>14,.0f}"
        )
        lines.append(
            f"    {'Carbon released (one-off):':<36} "
            f"\u20ac{npv.carbon_release:>14,.0f}"
        )
        lines.append(
            f"    {'Absorption lost (annual flow):':<36} "
            f"\u20ac{npv.carbon_foregone:>14,.0f}"
        )
        lines.append(f"    {'':=<36} {'':=>15}")
        lines.append(
            f"    {'Total extraction PV:':<36} "
            f"\u20ac{npv.total:>14,.0f}"
        )
        if npv.substrate_unrecoverable > 0.0:
            lines.append(
                f"    {'of which unrecoverable (substrate):':<36} "
                f"\u20ac{npv.substrate_unrecoverable:>14,.0f}"
            )
            lines.append(
                "      (part of the services PV that restoration cannot recover; not added)"
            )

    # v0.7: Price Decomposition
    if result.steps:
        final_step = result.steps[-1]
        if final_step.price_result is not None:
            pr = final_step.price_result
            lines.append("")
            lines.append(
                "  \u2500\u2500 Price Decomposition (v0.7 endogenous, EXPERIMENTAL) \u2500"
                + "\u2500" * 7
            )
            method: str = (
                "row/column sum bound" if pr.convergence_check == "norm_bound"
                else f"direct iteration, {pr.iterations} iterations"
            )
            lines.append(
                f"  Convergence: certified, \u03c1(S\u00b7W) <= "
                f"{pr.spectral_radius_bound:.4f} < 1 ({method})"
            )
            lines.append("  EXPERIMENTAL: not an estimate (see banner above)")
            lines.append("")
            lines.append(
                f"  {'Agent':<24} {'Price':>12} "
                f"{'Scarcity':>10} {'Demand':>10}"
            )
            lines.append(f"  {_SINGLE_LINE}")
            for agent_name in pr.prices:
                price_val: float = pr.prices[agent_name]
                scarcity_m: float = pr.scarcity_multipliers.get(agent_name, 1.0)
                demand_m: float = pr.demand_multipliers.get(agent_name, 1.0)
                lines.append(
                    f"  {agent_name:<24} "
                    f"\u20ac{price_val:>10,.0f}/yr "
                    f"{scarcity_m:>10.2f}x "
                    f"{demand_m:>10.2f}x"
                )

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)


def format_restoration_report(result: RestorationResult) -> str:
    """
    Format a RestorationResult into a human-readable plain-text restoration report.

    The report shows:
        - Resource state and restoration target
        - Restoration cost breakdown (planting + maintenance, one-off €)
        - Per-agent recovered service values (€/yr)
        - Annual recovered ecosystem value (€/yr)
        - Net restoration value (€ PV: PV of benefits minus PV of costs)
        - Restoration cost ratio (an input-price ratio)
        - v0.4: Maturation Timeline, Carbon Recovery
        - v0.5: Substrate Restoration Ceiling
        - v0.6: Investment Analysis (NPV), Carbon Credit Breakeven
        - Step 3.7: Destroy-then-Restore Penalty (€ PV and per € of
                foregone revenue)

    Args:
        result: A completed RestorationResult from run_restoration().

    Returns:
        A multi-line string suitable for printing to stdout.
    """
    ecosystem: Ecosystem = result.ecosystem
    resource: Resource = ecosystem.resource
    agents: list = ecosystem.agents
    cost: RestorationCost = result.restoration_cost

    restoration_ratio: float = (
        result.total_units_restored / resource.total_units
        if resource.total_units > 0 else 0.0
    )

    # Per-agent service values from the final step
    if result.steps:
        final_service_values: list = result.steps[-1].agent_service_values
    else:
        final_service_values = [0.0] * len(agents)

    lines: list = []

    # Header
    lines.append(_DOUBLE_LINE)
    title: str = f"GAIA \u2014 Restoration Report: {ecosystem.name}"
    lines.append(f"  {title}")
    lines.append(_DOUBLE_LINE)
    lines.append("")

    # Resource state
    lines.append(
        f"  {'Resource:':<28} {resource.total_units:>10,} units  ({resource.name})"
    )
    lines.append(
        f"  {'Area:':<28} {resource.area_ha:>10,.1f} ha"
    )
    lines.append(
        f"  {'Units Lost (start):':<28} {result.units_lost:>10,}"
    )
    lines.append(
        f"  {'Units Restored:':<28} {result.total_units_restored:>10,}"
    )
    lines.append(
        f"  {'Restoration Coverage:':<28} {restoration_ratio:>10.1%}  of total capacity"
    )
    lines.append(
        f"  {'Depletion:':<28} {result.depletion_before:>10.1%}  \u2192 "
        f"{result.depletion_after:.1%}"
    )
    lines.append(
        f"  {'Ecosystem Health:':<28} {result.initial_ecosystem_health:>10.1%}  \u2192 "
        f"{result.final_ecosystem_health:.1%}  (at maturity)"
    )
    lines.append("")

    # Restoration cost breakdown
    lines.append("  \u2500\u2500 Restoration Costs \u2500" + "\u2500" * 42)
    lines.append(
        f"  {'Planting cost/unit:':<40} {cost.planting_cost_per_unit:>10,.2f}\u20ac"
    )
    lines.append(
        f"  {'Maintenance/unit/year:':<40} {cost.annual_maintenance_per_unit:>10,.2f}\u20ac/yr"
    )
    lines.append(
        f"  {'Maintenance years:':<40} {cost.maintenance_years:>10}"
    )
    lines.append(
        f"  {'Total cost/unit:':<40} {cost.total_cost_per_unit:>10,.2f}\u20ac"
    )
    lines.append(
        f"  {'TOTAL RESTORATION COST:':<40} {result.total_restoration_cost:>14,.2f}\u20ac (one-off)"
    )
    lines.append("")

    # Recovered ecosystem services (yearly flows at full maturity)
    lines.append("  \u2500\u2500 Recovered Ecosystem Services \u2500" + "\u2500" * 31)

    agent: Agent
    for i, agent in enumerate(agents):
        svc: float = final_service_values[i] if i < len(final_service_values) else 0.0
        lines.append(
            f"  {agent.name + ':':<40} {svc:>14,.2f}\u20ac/yr"
        )
        lines.append(f"    \u2192 {agent.description}")

    lines.append("")

    # Totals
    lines.append(
        f"  {'Damage reversal (upper bound):':<40} "
        f"{result.annual_damage_reversal:>14,.2f}\u20ac/yr"
    )
    lines.append(
        "    (annual externality before \u2212 after restoring, same damage model)"
    )
    lines.append(
        f"  {'ANNUAL RECOVERED VALUE:':<40} {result.annual_recovered_value:>14,.2f}\u20ac/yr"
    )
    lines.append(f"  {_SINGLE_LINE}")
    lines.append(
        f"  {'NET RESTORATION VALUE:':<40} {result.net_restoration_pv:>14,.2f}\u20ac (PV)"
    )
    lines.append(
        "    (PV of recovered services and carbon \u2212 PV of restoration costs)"
    )
    lines.extend(_horizon_sensitivity_lines(result.net_restoration_pv_by_horizon))
    lines.append("")

    # Restoration cost ratio: an input-price ratio, not a finding
    lines.append("  \u2500\u2500 Restoration Cost Ratio \u2500" + "\u2500" * 37)
    if result.restoration_cost_ratio is not None:
        lines.append(
            f"  {'(Revenue + restoration cost) / revenue:':<40} "
            f"{result.restoration_cost_ratio:>10.2f}"
        )
    else:
        lines.append(
            f"  {'(Revenue + restoration cost) / revenue:':<40} {'n/a':>10}"
        )
    lines.append(
        "    (= 1 + restoration cost per unit / unit value: a ratio of two"
    )
    lines.append(
        "     input prices, no ecology; see Destroy-then-Restore Penalty)"
    )

    # v0.4: Maturation Timeline
    if result.maturation_timeline:
        lines.append("")
        lines.append("  \u2500\u2500 Maturation Timeline \u2500" + "\u2500" * 40)
        lines.append(
            f"  {'Years to first services:':<40} "
            f"{result.years_to_pioneer:>10.0f} years"
        )
        lines.append(
            f"  {'Years to 50% service recovery:':<40} "
            f"{result.years_to_50pct:>10.0f} years"
        )
        lines.append(
            f"  {'Years to 90% service recovery:':<40} "
            f"{result.years_to_90pct:>10.0f} years"
        )

        lines.append("")
        lines.append("  \u2500\u2500 Maturation Gap \u2500" + "\u2500" * 45)
        lines.append(
            f"  {'Lost services during maturation:':<40} "
            f"{result.maturation_gap_pv:>14,.2f}\u20ac (PV)"
        )
        lines.append(
            "  (discounted services not delivered while succession proceeds,"
        )
        lines.append(
            f"   over the {result.restoration_npv.horizon}-year NPV horizon)"
            if result.restoration_npv is not None else
            "   over the NPV horizon)"
        )

    # v0.4: Carbon Recovery
    if (result.maturation_timeline
            and ecosystem.resource.carbon_profile is not None):
        lines.append("")
        lines.append("  \u2500\u2500 Carbon Recovery \u2500" + "\u2500" * 44)
        final_mat = result.maturation_timeline[-1]
        co2_label = "Cumulative CO\u2082 absorbed:"
        lines.append(
            f"  {co2_label:<40} "
            f"{final_mat.cumulative_carbon_absorbed:>10,.0f} t CO\u2082"
        )
        lines.append(
            f"  {'Over':<5} {len(result.maturation_timeline)} years of maturation"
        )

    # v0.5: Substrate Restoration Ceiling
    if resource.substrate is not None and result.substrate_ceiling < 1.0:
        lines.append("")
        lines.append(
            "  \u2500\u2500 Substrate Restoration Ceiling \u2500" + "\u2500" * 29
        )
        ceiling_pct: float = result.substrate_ceiling * 100
        lines.append(
            f"  {'Max recoverable services:':<40} {ceiling_pct:>10.1f}% of pristine"
        )
        lines.append(
            "  Biological restoration capped at substrate ceiling."
        )
        if result.substrate_recovery_years > 0:
            lines.append(
                f"  {'Substrate recovery time:':<40} "
                f"{_recovery_years_text(result.substrate_recovery_years)}"
            )


    # v0.6: Investment Analysis (NPV)
    if result.restoration_npv is not None:
        rnpv = result.restoration_npv
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Investment Analysis (NPV, {rnpv.horizon}-year) \u2500"
            + "\u2500" * 24
        )
        lines.append(
            f"  {'Restoration cost (PV):':<40} "
            f"\u20ac{rnpv.cost:>14,.0f}"
        )
        lines.append(
            f"  {'Service recovery (PV):':<40} "
            f"\u20ac{rnpv.service_benefits:>14,.0f}"
        )
        lines.append(
            f"  {'Carbon absorption (PV):':<40} "
            f"\u20ac{rnpv.carbon_benefits:>14,.0f}"
        )
        lines.append(
            f"  {'Total benefits (PV):':<40} "
            f"\u20ac{rnpv.total_benefits:>14,.0f}"
        )
        lines.append(f"  {_SINGLE_LINE}")
        lines.append(
            f"  {'Net Present Value:':<40} "
            f"\u20ac{rnpv.net_present_value:>14,.0f}"
        )
        lines.append(
            f"  {'ROI (benefits / cost):':<40} "
            f"{rnpv.roi:>14.2f}x"
        )
        if rnpv.carbon_payback_years is not None:
            lines.append(
                f"  {'Carbon payback:':<40} "
                f"{rnpv.carbon_payback_years:>14} years"
            )
        else:
            lines.append(
                f"  {'Carbon payback:':<40} "
                f"{'N/A':>14}"
            )

    # v0.6: Carbon Credit Breakeven
    if result.carbon_breakeven is not None:
        cb = result.carbon_breakeven
        lines.append("")
        lines.append(
            "  \u2500\u2500 Carbon Credit Breakeven \u2500" + "\u2500" * 36
        )
        lines.append(
            f"  {'Breakeven price:':<40} "
            f"\u20ac{cb.breakeven_price:>12,.2f}/t CO\u2082"
        )
        lines.append(
            f"  {'Carbon price (year 0):':<40} "
            f"\u20ac{cb.current_price:>12,.2f}/t CO\u2082"
        )
        lines.append(
            f"  {'Gap to current:':<40} "
            f"\u20ac{cb.gap_to_current:>12,.2f}/t CO\u2082"
        )
        profitable_label: str = "Yes" if cb.profitable_at_current else "No"
        lines.append(
            f"  {'Profitable at current price:':<40} "
            f"{profitable_label:>14}"
        )
        if cb.projected_breakeven_year is not None:
            lines.append(
                f"  {'Projected breakeven year:':<40} "
                f"{cb.projected_breakeven_year:>14}"
            )
        else:
            lines.append(
                f"  {'Projected breakeven year:':<40} "
                f"{'N/A':>14}"
            )

    # Step 3.7: Destroy-then-restore penalty
    if result.destroy_then_restore_penalty is not None:
        pen = result.destroy_then_restore_penalty
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Destroy-then-Restore Penalty (\u20ac PV, "
            f"{pen.horizon}-year) \u2500" + "\u2500" * 14
        )
        lines.append(
            "  Social cost of cutting these units and restoring them, over"
        )
        lines.append("  not cutting them:")
        for label, value in (
            ("Restoration cost:", pen.restoration_cost),
            ("Maturation gap (temporary):", pen.maturation_gap),
            ("Substrate loss (permanent):", pen.substrate_loss),
            ("Recovery shortfall (permanent):", pen.recovery_shortfall),
            ("Carbon not recovered:", pen.carbon_not_recovered),
        ):
            lines.append(f"    {label:<38} \u20ac{value:>14,.0f}")
        lines.append(f"    {'':=<38} {'':=>15}")
        lines.append(
            f"    {'Penalty:':<38} \u20ac{pen.total:>14,.0f}"
        )
        lines.append(
            f"    {'Foregone revenue (PV of not cutting):':<38} "
            f"\u20ac{pen.foregone_revenue:>14,.0f}"
        )
        if pen.ratio is not None:
            ratio_label: str = "Penalty per \u20ac of foregone revenue:"
            lines.append(f"    {ratio_label:<38} {pen.ratio:>15.2f}")

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)
