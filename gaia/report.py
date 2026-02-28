"""
Gaia v0.1/v0.2 — Text report generation.

Produces plain-text reports from simulation results.
No dependencies — pure string formatting with the standard library only.

v0.1: format_report()           — externality report from run_extraction()
v0.2: format_restoration_report() — restoration report from run_restoration()
"""

from gaia.models import Agent, Ecosystem, RestorationResult, Resource, SimulationResult

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
    else:
        final_agent_costs = [0.0] * len(agents)

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
    lines.append(f"  {_DOUBLE_LINE}")

    return "\n".join(lines)
