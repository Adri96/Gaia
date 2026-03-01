"""
Gaia v0.4 — Text report generation.

Produces plain-text reports from simulation results.
No dependencies — pure string formatting with the standard library only.

v0.1: format_report()           — externality report from run_extraction()
v0.2: format_restoration_report() — restoration report from run_restoration()
v0.3: Cascade breakdown (direct vs propagated damage, trophic amplification,
      keystone threshold warnings) added to externality report.
v0.4: Resilience Assessment, Carbon Accounting sections in extraction report;
      Maturation Timeline, Carbon Recovery sections in restoration report.
"""

from gaia.carbon import compute_carbon_cost, compute_carbon_payback_period
from gaia.models import Agent, Ecosystem, RestorationResult, Resource, SimulationResult
from gaia.resilience import compute_confidence_band

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

    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)
