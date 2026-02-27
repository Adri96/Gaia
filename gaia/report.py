"""
Gaia v0.1 — Text report generation.

Produces a plain-text externality report from a SimulationResult.
No dependencies — pure string formatting with the standard library only.
"""

from gaia.models import Agent, Ecosystem, Resource, SimulationResult

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
