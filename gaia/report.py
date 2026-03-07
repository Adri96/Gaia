"""
Gaia v0.7 — Text report generation.

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
v0.6: NPV Analysis section in extraction report;
      Investment Analysis (NPV), Carbon Credit Breakeven,
      Prevention Advantage V06 sections in restoration report.
v0.7: Price Decomposition section in extraction report
      (endogenous pricing with scarcity and demand multipliers).
"""

from gaia.carbon import compute_carbon_cost, compute_carbon_payback_period
from gaia.models import Agent, Ecosystem, RestorationResult, Resource, SimulationResult
from gaia.resilience import compute_confidence_band
from gaia.substrate import compute_substrate_recovery_years, create_substrate_state

# Report width (characters)
_WIDTH: int = 63
_DOUBLE_LINE: str = "=" * _WIDTH
_SINGLE_LINE: str = "-" * _WIDTH


def format_report(result: SimulationResult) -> str:
    """
    Format a SimulationResult into a human-readable plain-text externality report.

    The report shows:
        - Resource state and depletion
        - Private revenue from extraction
        - Per-agent externality costs with descriptions
        - Total externality cost
        - Net social cost (positive = society gained, negative = society lost)
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
        npv = result.extraction_npv
        discount = resource.discount
        lines.append("")
        lines.append(
            f"  \u2500\u2500 NPV Analysis ({npv.horizon}-year horizon"
        )
        if discount is not None:
            ramsey_rate: float = discount.delta + discount.eta * discount.g
            lines.append(
                f"     {ramsey_rate:.1%} discount rate) \u2500"
                + "\u2500" * 33
            )
            lines.append("")
            lines.append(
                f"  Ramsey components: "
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
        else:
            lines.append(f"     ) \u2500" + "\u2500" * 49)

        lines.append("")
        lines.append(f"  Externality NPV breakdown:")
        lines.append(
            f"    {'Direct ecosystem services:':<36} "
            f"\u20ac{npv.direct:>14,.0f}"
        )
        lines.append(
            f"    {'Carbon released:':<36} "
            f"\u20ac{npv.carbon_release:>14,.0f}"
        )
        lines.append(
            f"    {'Foregone absorption:':<36} "
            f"\u20ac{npv.carbon_foregone:>14,.0f}"
        )
        lines.append(
            f"    {'Substrate damage (permanent):':<36} "
            f"\u20ac{npv.substrate_damage:>14,.0f}"
        )
        lines.append(f"    {'':=<36} {'':=>15}")
        lines.append(
            f"    {'Total extraction NPV:':<36} "
            f"\u20ac{npv.total:>14,.0f}"
        )

        # Undiscounted comparison
        undiscounted_total: float = result.total_externality_cost
        if undiscounted_total > 0.0:
            discount_effect: float = (npv.total - undiscounted_total) / undiscounted_total
            lines.append("")
            lines.append(
                f"  {'For comparison (undiscounted):':<40} "
                f"\u20ac{undiscounted_total:>12,.0f}"
            )
            lines.append(
                f"  {'Discount effect:':<40} "
                f"{discount_effect:>12.1%}"
            )

    # v0.7: Price Decomposition
    if result.steps:
        final_step = result.steps[-1]
        if final_step.price_result is not None:
            pr = final_step.price_result
            lines.append("")
            lines.append(
                f"  \u2500\u2500 Price Decomposition (v0.7 endogenous) \u2500"
                + "\u2500" * 20
            )
            lines.append(
                f"  Solver: {'converged' if pr.converged else 'FAILED'}"
                f" in {pr.iterations} iterations"
                f"  (spectral radius {pr.spectral_radius:.4f})"
            )
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
                    f"\u20ac{price_val:>10,.0f} "
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
        - Restoration cost breakdown (planting + maintenance)
        - Per-agent recovered service values
        - Total recovered ecosystem value
        - Net restoration value (recovered value minus restoration cost)
        - Prevention advantage (how much cheaper prevention is vs destroy-then-restore)
        - v0.4: Maturation Timeline, Carbon Recovery
        - v0.5: Substrate Restoration Ceiling
        - v0.6: Investment Analysis (NPV), Carbon Credit Breakeven,
                Prevention Advantage V06

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

        # Enhanced prevention advantage
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
    if result.restoration_npv is not None:
        rnpv = result.restoration_npv
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Investment Analysis (NPV, {rnpv.horizon}-year) \u2500"
            + "\u2500" * 24
        )
        lines.append(
            f"  {'Restoration cost (NPV):':<40} "
            f"\u20ac{rnpv.cost:>14,.0f}"
        )
        lines.append(
            f"  {'Service recovery (NPV):':<40} "
            f"\u20ac{rnpv.service_benefits:>14,.0f}"
        )
        lines.append(
            f"  {'Carbon absorption (NPV):':<40} "
            f"\u20ac{rnpv.carbon_benefits:>14,.0f}"
        )
        lines.append(
            f"  {'Total benefits (NPV):':<40} "
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
            f"  \u2500\u2500 Carbon Credit Breakeven \u2500" + "\u2500" * 36
        )
        lines.append(
            f"  {'Breakeven price:':<40} "
            f"\u20ac{cb.breakeven_price:>12,.2f}/t CO\u2082"
        )
        lines.append(
            f"  {'Current EU ETS price:':<40} "
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

    # v0.6: Prevention Advantage V06
    if result.prevention_advantage_v06 is not None:
        pa = result.prevention_advantage_v06
        lines.append("")
        lines.append(
            f"  \u2500\u2500 Prevention Advantage (NPV-based) \u2500" + "\u2500" * 26
        )
        lines.append(
            f"  {'PA simple (undiscounted):':<40} "
            f"{pa.pa_simple:>14.2f}x"
        )
        lines.append(
            f"  {'PA with carbon:':<40} "
            f"{pa.pa_with_carbon:>14.2f}x"
        )
        lines.append(
            f"  {'PA with substrate:':<40} "
            f"{pa.pa_with_substrate:>14.2f}x"
        )
        lines.append(
            f"  {'PA full (all-inclusive NPV):':<40} "
            f"{pa.pa_full:>14.2f}x"
        )
        lines.append("")
        lines.append(
            f"  {'NPV prevention cost (revenue):':<40} "
            f"\u20ac{pa.npv_prevention_cost:>14,.0f}"
        )
        lines.append(
            f"  {'NPV restoration total:':<40} "
            f"\u20ac{pa.npv_restoration_total:>14,.0f}"
        )

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)
