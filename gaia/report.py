"""
Gaia v0.6 — Text report generation.

Produces plain-text reports from simulation results.
No dependencies — pure string formatting with the standard library only.

v0.1: format_report()           — externality report from run_extraction()
v0.2: format_restoration_report() — restoration report from run_restoration()
v0.3: Cascade breakdown (direct vs propagated damage, trophic amplification,
      keystone threshold warnings) added to externality report.
v0.4: Resilience Assessment, Carbon Accounting sections in extraction report;
      Maturation Timeline, Carbon Recovery sections in restoration report.
v0.5: Substrate Impact Assessment in extraction report;
      Substrate Restoration Ceiling in restoration report.
v0.6: NPV Analysis in extraction report; Investment Analysis, Carbon Credit
      Breakeven, Prevention Advantage (NPV) in restoration report.
      New: format_sensitivity_report() for discount rate comparison.
"""

from typing import List, Optional

from gaia.carbon import compute_carbon_cost, compute_carbon_payback_period
from gaia.discount import (
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    DISCOUNT_MARKET,
)
from gaia.models import (
    Agent,
    DiscountConfig,
    Ecosystem,
    ExtractionNPV,
    RestorationResult,
    Resource,
    SimulationResult,
)
from gaia.npv import compute_extraction_npv, compute_restoration_npv
from gaia.resilience import compute_confidence_band
from gaia.substrate import compute_substrate_recovery_years, create_substrate_state

# Report width (characters)
_WIDTH: int = 63
_DOUBLE_LINE: str = "═" * _WIDTH
_SINGLE_LINE: str = "─" * _WIDTH


def format_report(result: SimulationResult) -> str:
    """
    Format a SimulationResult into a human-readable plain-text externality report.

    The report shows:
        - Resource state and depletion
        - Private revenue from extraction
        - Per-agent externality costs with descriptions
        - Total externality cost
        - Net social cost (positive = society gained, negative = society lost)

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

    # Compute per-agent final costs from the last step
    # agent_costs[i] is the total cost at the final depletion level
    if result.steps:
        final_agent_costs: list = result.steps[-1].agent_costs
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

    # Resource state
    lines.append(
        f"  {'Resource:':<18} {resource.total_units:>10,} units  ({resource.name})"
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
    lines.append(f"  \u2500\u2500 Private Gains \u2500" + "\u2500" * 46)
    lines.append(
        f"  {'Revenue:':<40} {result.total_private_revenue:>14,.2f}\u20ac"
    )
    lines.append("")

    # Externalized costs
    lines.append(f"  \u2500\u2500 Externalized Costs \u2500" + "\u2500" * 41)

    agent: Agent
    for i, agent in enumerate(agents):
        cost: float = final_agent_costs[i] if i < len(final_agent_costs) else 0.0
        lines.append(
            f"  {agent.name + ':':<40} {cost:>14,.2f}\u20ac"
        )
        lines.append(f"    \u2192 {agent.description}")

        # v0.3: Cascade breakdown (only when cascade data is present)
        if has_cascade_data and i < len(final_cascade_damages):
            direct_dmg: float = final_direct_damages[i]
            cascade_dmg: float = final_cascade_damages[i]
            weight: float = agent.dependency_weight
            rate: float = agent.monetary_rate
            direct_cost: float = direct_dmg * weight * rate
            cascade_cost: float = cascade_dmg * weight * rate

            if cascade_dmg > 1e-6:
                lines.append(
                    f"    \u2192 Direct: \u20ac{direct_cost:,.0f} | "
                    f"Cascade: \u20ac{cascade_cost:,.0f}"
                )

            # Show trophic amplification for consumers
            if agent.trophic_level >= 1:
                # Compute the raw amplification factor (not capped damage)
                amp: float = (1.0 / 0.15) ** (agent.trophic_level * 0.25)
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
                f"  \u2500\u2500 Keystone Threshold Crossings \u2500" + "\u2500" * 31
            )
            for kname, kstep in sorted(keystone_crossings.items(), key=lambda x: x[1]):
                depletion_at_cross: float = kstep / resource.total_units
                lines.append(
                    f"  \u26a0 {kname}: crossed at step {kstep:,} "
                    f"({depletion_at_cross:.0%} depletion)"
                )
            lines.append("")

    # Totals
    lines.append(
        f"  {'TOTAL EXTERNALITY:':<40} {result.total_externality_cost:>14,.2f}\u20ac"
    )
    lines.append(f"  {_SINGLE_LINE}")

    # Net social cost: revenue - externality
    # Positive = society gained; negative = society lost (net loss)
    net: float = result.net_social_cost
    net_label: str = "NET SOCIAL COST:"
    lines.append(
        f"  {net_label:<40} {net:>14,.2f}\u20ac"
    )

    # v0.4: Resilience Assessment
    if result.steps and result.steps[-1].resilience_zone != "green":
        lines.append("")
        lines.append(f"  \u2500\u2500 Resilience Assessment \u2500" + "\u2500" * 38)
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
            lines.append(f"  Zone transitions:")
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
                    f"    Ecosystem damage may be partially irreversible."
                )

    # v0.4: Carbon Accounting
    if resource.carbon_profile is not None and result.total_units_extracted > 0:
        lines.append("")
        lines.append(f"  \u2500\u2500 Carbon Accounting \u2500" + "\u2500" * 42)
        carbon = compute_carbon_cost(
            resource.carbon_profile,
            result.total_units_extracted,
            remaining_years=80.0,  # default estimate
        )
        lines.append(
            f"  {'Carbon released (biomass+soil):':<40} "
            f"{carbon['release_tonnes']:>10,.0f} t CO\u2082"
        )
        lines.append(
            f"  {'Future absorption foregone:':<40} "
            f"{carbon['foregone_tonnes_per_year']:>10,.1f} t CO\u2082/yr"
        )
        lines.append(
            f"  {'Carbon externality (release):':<40} "
            f"{carbon['release_cost']:>14,.2f}\u20ac"
        )
        lines.append(
            f"  {'Carbon externality (foregone):':<40} "
            f"{carbon['foregone_cost_per_year']:>14,.2f}\u20ac/yr"
        )

    # v0.4: Confidence band on total externality
    if result.steps and resource.resilience is not None:
        final_confidence = result.steps[-1].model_confidence
        if final_confidence < 1.0:
            lower, upper = compute_confidence_band(
                result.total_externality_cost, final_confidence
            )
            lines.append("")
            lines.append(f"  \u2500\u2500 Externality with Confidence Band \u2500" + "\u2500" * 28)
            lines.append(
                f"  {'Total Externality:':<40} {result.total_externality_cost:>14,.2f}\u20ac"
            )
            lines.append(
                f"  Confidence band ({final_confidence:.0%}):"
                f"        {lower:>12,.2f}\u20ac \u2014 {upper:>12,.2f}\u20ac"
            )

    # v0.5: Substrate Impact Assessment
    if resource.substrate is not None and result.steps:
        final_step = result.steps[-1]
        if final_step.k_fraction < 1.0:
            lines.append("")
            lines.append(
                f"  \u2500\u2500 Substrate Impact Assessment \u2500" + "\u2500" * 31
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

            # Recovery timeline
            sub_state = create_substrate_state(sub)
            # Approximate current state from k_fraction
            if sub.soil_depth_cm is not None:
                sub_state.current_soil_depth_cm = sub.soil_depth_cm * final_step.k_fraction
            if sub.sediment_stability is not None:
                sub_state.current_sediment_stability = (
                    sub.sediment_stability * final_step.k_fraction
                )
            recovery_years: float = compute_substrate_recovery_years(sub_state)
            if recovery_years < float("inf"):
                lines.append(
                    f"  {'Years to pristine substrate:':<40} {recovery_years:>10,.0f} years"
                )
            else:
                lines.append(
                    f"  {'Years to pristine substrate:':<40} {'N/A':>10}"
                )

    # v0.6: NPV Analysis
    if result.extraction_npv is not None:
        npv: ExtractionNPV = result.extraction_npv
        dc: DiscountConfig = npv.discount_config
        lines.append("")
        rate_label: str
        if isinstance(dc.rate_schedule, (int, float)):
            rate_label = f"{float(dc.rate_schedule):.1%}"
        else:
            rates = [e[1] for e in dc.rate_schedule]
            rate_label = (
                f"{rates[0]:.1%}\u2192{rates[-1]:.1%} (declining)"
            )
        lines.append(
            f"  \u2500\u2500 NPV Analysis ({dc.horizon_years}-year horizon, "
            f"{rate_label} rate) \u2500" + "\u2500" * 3
        )
        lines.append(
            f"  Ramsey: \u03b4={dc.delta:.1%}, "
            f"\u03b7={dc.eta:.2f}, g={dc.g:.1%}"
        )
        if dc.scarcity_rate > 0:
            lines.append(
                f"  Scarcity uplift: {dc.scarcity_rate:.1%}/yr on ecosystem services"
            )
        lines.append(
            f"  Carbon price: \u20ac{dc.carbon_price_current:.0f}/t "
            f"growing at {dc.carbon_price_growth:.1%}/yr"
        )
        lines.append("")
        lines.append(f"  Externality NPV breakdown:")
        lines.append(
            f"  {'  Direct ecosystem services:':<40} "
            f"{npv.direct:>14,.0f}\u20ac"
        )
        if npv.carbon_release > 0:
            lines.append(
                f"  {'  Carbon released (immediate):':<40} "
                f"{npv.carbon_release:>14,.0f}\u20ac"
            )
        if npv.carbon_foregone > 0:
            lines.append(
                f"  {'  Foregone absorption '}"
                f"({dc.remaining_productive_years}yr):"
                f"{'':>5} {npv.carbon_foregone:>14,.0f}\u20ac"
            )
        if npv.substrate_damage > 0:
            lines.append(
                f"  {'  Substrate damage (permanent):':<40} "
                f"{npv.substrate_damage:>14,.0f}\u20ac"
            )
        _npv_sep = "  " + "\u2500" * 38
        lines.append(f"  {_npv_sep}")
        lines.append(
            f"  {'  Total extraction NPV:':<40} "
            f"{npv.total:>14,.0f}\u20ac"
        )
        lines.append("")
        undiscounted: float = result.total_externality_cost
        if undiscounted > 1e-9:
            discount_effect_pct: float = (npv.total - undiscounted) / undiscounted * 100
            lines.append(
                f"  For comparison (undiscounted): "
                f"{undiscounted:>14,.0f}\u20ac"
            )
            lines.append(
                f"  Discount effect:               "
                f"{discount_effect_pct:>13.1f}%"
            )
        if dc.scarcity_rate > 0:
            lines.append("")
            lines.append(
                f"  Note: scarcity uplift ({dc.scarcity_rate:.1%}/yr) "
                f"partially offsets discounting."
            )

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)


def format_restoration_report(result: RestorationResult) -> str:
    """
    Format a RestorationResult into a human-readable plain-text restoration report.

    The report shows:
        - Resource state and restoration target
        - Restoration cost breakdown (planting + maintenance)
        - Per-agent recovered service values
        - Total recovered ecosystem value
        - Net restoration value (recovered value minus restoration cost)
        - Prevention advantage (how much cheaper prevention is vs destroy-then-restore)

    Args:
        result: A completed RestorationResult from run_restoration().

    Returns:
        A multi-line string suitable for printing to stdout.
    """
    ecosystem: Ecosystem = result.ecosystem
    resource: Resource = ecosystem.resource
    agents: list = ecosystem.agents
    cost: object = result.restoration_cost

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
        f"  {'Units Restored:':<28} {result.total_units_restored:>10,}"
    )
    lines.append(
        f"  {'Restoration Coverage:':<28} {restoration_ratio:>10.1%}  of total capacity"
    )
    lines.append(
        f"  {'Final Ecosystem Health:':<28} {result.final_ecosystem_health:>10.1%}"
    )
    lines.append("")

    # Restoration cost breakdown
    lines.append(f"  \u2500\u2500 Restoration Costs \u2500" + "\u2500" * 42)
    lines.append(
        f"  {'Planting cost/unit:':<40} {cost.planting_cost_per_unit:>10,.2f}\u20ac"
    )
    lines.append(
        f"  {'Maintenance/unit/year:':<40} {cost.annual_maintenance_per_unit:>10,.2f}\u20ac"
    )
    lines.append(
        f"  {'Maintenance years:':<40} {cost.maintenance_years:>10}"
    )
    lines.append(
        f"  {'Total cost/unit:':<40} {cost.total_cost_per_unit:>10,.2f}\u20ac"
    )
    lines.append(
        f"  {'TOTAL RESTORATION COST:':<40} {result.total_restoration_cost:>14,.2f}\u20ac"
    )
    lines.append("")

    # Recovered ecosystem services
    lines.append(f"  \u2500\u2500 Recovered Ecosystem Services \u2500" + "\u2500" * 31)

    agent: Agent
    for i, agent in enumerate(agents):
        svc: float = final_service_values[i] if i < len(final_service_values) else 0.0
        lines.append(
            f"  {agent.name + ':':<40} {svc:>14,.2f}\u20ac"
        )
        lines.append(f"    \u2192 {agent.description}")

    lines.append("")

    # Totals
    lines.append(
        f"  {'TOTAL RECOVERED VALUE:':<40} {result.total_recovered_value:>14,.2f}\u20ac"
    )
    lines.append(f"  {_SINGLE_LINE}")
    lines.append(
        f"  {'NET RESTORATION VALUE:':<40} {result.net_restoration_value:>14,.2f}\u20ac"
    )
    lines.append("")

    # Prevention advantage
    lines.append(f"  \u2500\u2500 Prevention vs Restoration \u2500" + "\u2500" * 34)
    lines.append(
        f"  Prevention is {result.prevention_advantage:.2f}\u00d7 cheaper than "
        f"destroy\u2011then\u2011restore."
    )
    lines.append(
        f"  (Foregone revenue + restoration cost) / foregone revenue = "
        f"{result.prevention_advantage:.2f}"
    )

    # v0.4: Maturation Timeline
    if result.maturation_timeline:
        lines.append("")
        lines.append(f"  \u2500\u2500 Maturation Timeline \u2500" + "\u2500" * 40)
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
        lines.append(f"  \u2500\u2500 Maturation Gap \u2500" + "\u2500" * 45)
        lines.append(
            f"  {'Lost services during maturation:':<40} "
            f"{result.total_maturation_gap:>14,.2f}\u20ac"
        )
        lines.append(
            f"  (accumulated externality while waiting for succession)"
        )
        lines.append("")
        lines.append(
            f"  This cost is IN ADDITION to restoration costs."
        )
        lines.append(
            f"  True prevention advantage: restoration_cost + maturation_gap"
        )

    # v0.4: Carbon Recovery
    if (result.maturation_timeline
            and ecosystem.resource.carbon_profile is not None):
        lines.append("")
        lines.append(f"  \u2500\u2500 Carbon Recovery \u2500" + "\u2500" * 44)
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
            f"  \u2500\u2500 Substrate Restoration Ceiling \u2500" + "\u2500" * 29
        )
        ceiling_pct: float = result.substrate_ceiling * 100
        lines.append(
            f"  {'Max recoverable services:':<40} {ceiling_pct:>10.1f}% of pristine"
        )
        lines.append(
            f"  Biological restoration capped at substrate ceiling."
        )
        if result.substrate_recovery_years > 0:
            if result.substrate_recovery_years < float("inf"):
                lines.append(
                    f"  {'Substrate recovery time:':<40} "
                    f"{result.substrate_recovery_years:>10,.0f} years"
                )
            else:
                lines.append(
                    f"  {'Substrate recovery time:':<40} {'N/A':>10}"
                )

        # Enhanced prevention advantage (substrate, v0.5)
        if result.prevention_advantage_with_substrate > result.prevention_advantage:
            lines.append("")
            lines.append(
                f"  \u2500\u2500 Prevention Advantage (with substrate) \u2500"
                + "\u2500" * 21
            )
            lines.append(
                f"  {'Biological only:':<40} "
                f"{result.prevention_advantage:>10.2f}\u00d7"
            )
            lines.append(
                f"  {'Including substrate loss:':<40} "
                f"{result.prevention_advantage_with_substrate:>10.2f}\u00d7"
            )

    # v0.6: Investment Analysis (NPV)
    if result.npv is not None:
        npv_r = result.npv
        dc_r: DiscountConfig = npv_r.discount_config
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Investment Analysis ({dc_r.horizon_years}-year horizon) "
            + "\u2500" * 19
        )
        lines.append(f"  Restoration NPV:")
        lines.append(
            f"  {'  Costs (discounted):':<40} "
            f"{-npv_r.cost:>14,.0f}\u20ac"
        )
        lines.append(
            f"  {'  Service recovery:':<40} "
            f"{npv_r.service_benefits:>+14,.0f}\u20ac"
        )
        if npv_r.carbon_benefits > 0:
            lines.append(
                f"  {'  Carbon absorption:':<40} "
                f"{npv_r.carbon_benefits:>+14,.0f}\u20ac"
            )
        _rest_sep = "  " + "\u2500" * 38
        lines.append(f"  {_rest_sep}")
        lines.append(
            f"  {'  Net Present Value:':<40} "
            f"{npv_r.net_present_value:>+14,.0f}\u20ac"
        )
        lines.append(
            f"  {'  ROI:':<40} "
            f"{npv_r.roi:>13.2f}\u00d7"
        )
        if npv_r.carbon_payback_years is not None:
            lines.append("")
            lines.append(
                f"  {'Carbon payback period:':<40} "
                f"{npv_r.carbon_payback_years:>10} years"
            )
            lines.append(
                f"  (years to recapture released CO\u2082 through absorption)"
            )

    # v0.6: Carbon Credit Breakeven
    if result.carbon_breakeven is not None:
        cb = result.carbon_breakeven
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Carbon Credit Breakeven \u2500" + "\u2500" * 35
        )
        if cb.breakeven_price < float("inf"):
            lines.append(
                f"  {'Breakeven carbon price:':<40} "
                f"{cb.breakeven_price:>10,.0f}\u20ac/t CO\u2082"
            )
        else:
            lines.append(
                f"  {'Breakeven carbon price:':<40} "
                f"{'N/A (no absorption)':>10}"
            )
        lines.append(
            f"  {'Current EU ETS price:':<40} "
            f"{cb.current_price:>10,.0f}\u20ac/t CO\u2082"
        )
        if cb.breakeven_price < float("inf"):
            gap_sign: str = "+" if cb.gap_to_current > 0 else ""
            lines.append(
                f"  {'Gap to breakeven:':<40} "
                f"{gap_sign}{cb.gap_to_current:>9,.0f}\u20ac/t CO\u2082"
            )
        profit_label: str = "Yes \u2705" if cb.profitable_at_current else "No"
        lines.append(
            f"  {'Profitable from carbon alone:':<40} "
            f"{profit_label:>10}"
        )
        if cb.projected_breakeven_year is not None and not cb.profitable_at_current:
            lines.append("")
            lines.append(
                f"  At {result.npv.discount_config.carbon_price_growth:.1%}/yr "
                f"carbon price growth:"
                if result.npv is not None else
                f"  At current carbon growth rate:"
            )
            lines.append(
                f"  {'  Breakeven reached in year:':<40} "
                f"{cb.projected_breakeven_year}"
            )

    # v0.6: Prevention Advantage (NPV-adjusted)
    if result.prevention_advantage_v06 is not None:
        pav = result.prevention_advantage_v06
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Prevention Advantage (NPV-adjusted) \u2500" + "\u2500" * 22
        )
        lines.append(f"  Prevention advantage metrics:")
        lines.append(
            f"  {'  Simple (v0.2, undiscounted):':<40} "
            f"{pav.pa_simple:>10.2f}\u00d7"
        )
        lines.append(
            f"  {'  With carbon NPV:':<40} "
            f"{pav.pa_with_carbon:>10.2f}\u00d7"
        )
        lines.append(
            f"  {'  With substrate NPV:':<40} "
            f"{pav.pa_with_substrate:>10.2f}\u00d7"
        )
        lines.append(
            f"  {'  Full (all NPV components):':<40} "
            f"{pav.pa_full:>10.2f}\u00d7"
        )
        lines.append("")
        lines.append(
            f"  For every \u20ac1 of prevention cost, "
            f"extraction-then-restoration"
        )
        lines.append(
            f"  costs \u20ac{pav.pa_full:.2f} in present value terms."
        )

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)


def format_sensitivity_report(
    extraction_result: SimulationResult,
    restoration_result: Optional[RestorationResult] = None,
    profiles: Optional[List[DiscountConfig]] = None,
) -> str:
    """Format a discount rate sensitivity table across multiple discount profiles.

    Shows how key NPV outputs (extraction NPV, restoration NPV, prevention
    advantage, carbon breakeven) vary across different discount rate assumptions.

    Args:
        extraction_result: SimulationResult from run_extraction().
        restoration_result: Optional RestorationResult from run_restoration().
        profiles: List of DiscountConfig profiles to compare. Defaults to the
            four standard profiles [MARKET, CENTRAL, ENVIRONMENTAL, GREEN_BOOK].

    Returns:
        Multi-line string with sensitivity table.
    """
    if profiles is None:
        profiles = [
            DISCOUNT_MARKET,
            DISCOUNT_CENTRAL,
            DISCOUNT_ENVIRONMENTAL,
            DISCOUNT_GREEN_BOOK,
        ]

    resource = extraction_result.ecosystem.resource
    lines: list = []

    lines.append(_DOUBLE_LINE)
    lines.append("  GAIA \u2014 Discount Rate Sensitivity Analysis")
    lines.append(_DOUBLE_LINE)
    lines.append("")

    # Column headers
    col_width: int = 13
    header_rate: str = "  {:<24}".format("") + "".join(
        "{:>{w}}".format(_profile_label(p), w=col_width) for p in profiles
    )
    lines.append(header_rate)
    lines.append("  " + "\u2500" * (_WIDTH - 2))

    # Discount rates row
    rate_row: str = "  {:<24}".format("Rate:") + "".join(
        "{:>{w}}".format(_rate_str(p), w=col_width) for p in profiles
    )
    lines.append(rate_row)
    lines.append("  " + "\u2500" * (_WIDTH - 2))

    # Extraction NPV row
    ext_npvs: list = []
    for p in profiles:
        enp = compute_extraction_npv(extraction_result, p)
        ext_npvs.append(enp.total)
    ext_row: str = "  {:<24}".format("Extraction NPV:") + "".join(
        "{:>{w}}".format(_fmt_euro_m(v), w=col_width) for v in ext_npvs
    )
    lines.append(ext_row)

    # Restoration NPV and other metrics (if available)
    if restoration_result is not None:
        # Get succession curve from maturation timeline or from case data
        succ_curve = None  # use maturation_timeline if available

        rest_npvs: list = []
        cb_prices: list = []
        pa_fulls: list = []
        for p in profiles:
            rnp = compute_restoration_npv(restoration_result, p, succ_curve)
            rest_npvs.append(rnp.net_present_value)
            from gaia.npv import carbon_breakeven as _cb
            cb = _cb(restoration_result, p, succ_curve)
            cb_prices.append(cb.breakeven_price)
            from gaia.npv import compute_prevention_advantage_v06 as _pav
            pav = _pav(restoration_result, p, succ_curve)
            pa_fulls.append(pav.pa_full)

        rest_row: str = "  {:<24}".format("Restoration NPV:") + "".join(
            "{:>{w}}".format(_fmt_euro_m(v), w=col_width) for v in rest_npvs
        )
        lines.append(rest_row)

        pa_row: str = "  {:<24}".format("Prevention adv. (full):") + "".join(
            "{:>{w}}".format(
                f"{v:.1f}\u00d7" if v < 1000 else ">1000\u00d7", w=col_width
            ) for v in pa_fulls
        )
        lines.append(pa_row)

        cb_row: str = "  {:<24}".format("Carbon breakeven:") + "".join(
            "{:>{w}}".format(
                f"\u20ac{v:,.0f}/t" if v < float("inf") else "N/A",
                w=col_width
            ) for v in cb_prices
        )
        lines.append(cb_row)

    lines.append("  " + "\u2500" * (_WIDTH - 2))
    lines.append("")
    lines.append("  The discount rate choice is an ethical and empirical decision.")
    lines.append("  It is not a purely technical parameter.")
    lines.append(_DOUBLE_LINE)

    return "\n".join(lines)


def _profile_label(discount: DiscountConfig) -> str:
    """Short label for a discount profile."""
    if isinstance(discount.rate_schedule, (int, float)):
        return f"{float(discount.rate_schedule):.1%}"
    rates = [e[1] for e in discount.rate_schedule]
    return f"{rates[0]:.1%}\u2192{rates[-1]:.1%}"


def _rate_str(discount: DiscountConfig) -> str:
    """Rate string for sensitivity table."""
    return _profile_label(discount)


def _fmt_euro_m(value: float) -> str:
    """Format a euro value as ±X.XM€."""
    m = value / 1_000_000
    sign: str = "+" if value >= 0 else ""
    return f"{sign}{m:.1f}M\u20ac"
