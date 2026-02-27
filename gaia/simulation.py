"""
Gaia v0.1 — Simulation engine.

The simulation extracts units one at a time, computing externality costs at each
step using each agent's damage function. The damage function returns TOTAL damage
at the current depletion level (not marginal). Marginal cost is derived by
differencing consecutive total costs.

All code in this module is Cython-compatible:
    - No dynamic attributes
    - No **kwargs
    - All inner loop variables are primitive floats and ints
    - No third-party dependencies
"""

from gaia.models import Agent, Ecosystem, SimulationResult, SimulationStep
from gaia.validation import validate_ecosystem, validate_extraction


def run_extraction(ecosystem: Ecosystem, units_to_extract: int) -> SimulationResult:
    """
    Simulate extracting `units_to_extract` units from the ecosystem.

    At each step, the current depletion ratio is computed and each agent's
    damage function is evaluated to get the TOTAL externality cost at that
    depletion level. Marginal cost per step is the difference from the
    previous step's total.

    Algorithm (per step):
        depletion_ratio  = units_extracted / total_units
        damage[i]        = agent[i].damage_function(depletion_ratio)
        cost[i]          = damage[i] * agent[i].dependency_weight * agent[i].monetary_rate
        total_cost       = sum(cost[i] for all i)
        marginal_cost    = total_cost - total_cost_at_previous_step
        ecosystem_health = 1.0 - sum(agent[i].dependency_weight * damage[i] for all i)

    Args:
        ecosystem: The Ecosystem to simulate against.
        units_to_extract: Number of units to extract (>= 0, <= total_units).

    Returns:
        SimulationResult with all steps recorded.

    Raises:
        ValueError: If inputs fail validation.
    """
    validate_ecosystem(ecosystem)
    validate_extraction(ecosystem, units_to_extract)

    resource = ecosystem.resource
    agents: list = ecosystem.agents
    n_agents: int = len(agents)
    total_units: int = resource.total_units
    unit_value: float = resource.unit_value

    steps: list = []

    # Handle zero-extraction case: return empty result immediately
    if units_to_extract == 0:
        return SimulationResult(
            ecosystem=ecosystem,
            steps=steps,
            total_units_extracted=0,
            total_private_revenue=0.0,
            total_externality_cost=0.0,
            net_social_cost=0.0,
            final_ecosystem_health=1.0,
        )

    previous_total_cost: float = 0.0

    for step in range(1, units_to_extract + 1):
        units_extracted: int = step
        depletion_ratio: float = units_extracted / total_units

        # Evaluate each agent's damage at the current depletion level
        agent_damages: list = []
        agent_costs: list = []
        step_total_cost: float = 0.0
        health_sum: float = 0.0

        agent: Agent
        for agent in agents:
            damage: float = agent.damage_function(depletion_ratio)
            cost: float = damage * agent.dependency_weight * agent.monetary_rate
            agent_damages.append(damage)
            agent_costs.append(cost)
            step_total_cost += cost
            health_sum += agent.dependency_weight * damage

        marginal_cost: float = step_total_cost - previous_total_cost
        ecosystem_health: float = 1.0 - health_sum
        # Clamp health to [0, 1] to guard against floating-point overshoot
        if ecosystem_health < 0.0:
            ecosystem_health = 0.0
        elif ecosystem_health > 1.0:
            ecosystem_health = 1.0

        private_revenue: float = units_extracted * unit_value

        steps.append(SimulationStep(
            step=step,
            units_extracted=units_extracted,
            depletion_ratio=depletion_ratio,
            agent_damages=agent_damages,
            agent_costs=agent_costs,
            marginal_cost=marginal_cost,
            cumulative_cost=step_total_cost,
            private_revenue=private_revenue,
            ecosystem_health=ecosystem_health,
        ))

        previous_total_cost = step_total_cost

    final_step: SimulationStep = steps[-1]
    total_externality: float = final_step.cumulative_cost
    total_revenue: float = final_step.private_revenue

    return SimulationResult(
        ecosystem=ecosystem,
        steps=steps,
        total_units_extracted=units_to_extract,
        total_private_revenue=total_revenue,
        total_externality_cost=total_externality,
        net_social_cost=total_revenue - total_externality,
        final_ecosystem_health=final_step.ecosystem_health,
    )
