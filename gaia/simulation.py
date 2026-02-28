"""
Gaia v0.3 — Simulation engine.

The simulation extracts (or restores) units one at a time, computing externality
costs (or recovered service values) at each step. Damage/recovery functions return
TOTAL value at the current depletion/recovery level (not marginal). Marginal values
are derived by differencing consecutive totals.

All code in this module is Cython-compatible:
    - No dynamic attributes
    - No **kwargs
    - All inner loop variables are primitive floats and ints
    - No third-party dependencies

v0.2: Added run_restoration() — the inverse of run_extraction().
v0.3: Two-phase loops with trophic amplification and interaction propagation.
"""

from typing import List

from gaia.models import (
    Agent,
    Ecosystem,
    RestorationCost,
    RestorationResult,
    RestorationStep,
    SimulationResult,
    SimulationStep,
)
from gaia.propagation import compute_trophic_amplification, propagate_interactions
from gaia.recovery import RecoveryFunc
from gaia.validation import validate_ecosystem, validate_extraction


def run_extraction(ecosystem: Ecosystem, units_to_extract: int) -> SimulationResult:
    """
    Simulate extracting `units_to_extract` units from the ecosystem.

    v0.3 algorithm (per step):
        Phase 1 — Direct damage with trophic amplification:
            depletion_ratio  = units_extracted / total_units
            raw_damage[i]    = agent[i].damage_function(depletion_ratio)
            direct_damage[i] = trophic_amplification(raw_damage[i], trophic_level[i])

        Phase 2 — Interaction propagation (single pass):
            Apply keystone effects, then propagate damage through edges.
            effective_damage[i] = direct_damage[i] + cascade_damage[i]

        Phase 3 — Cost computation:
            cost[i]          = effective_damage[i] * weight[i] * rate[i]
            total_cost       = sum(cost[i])
            marginal_cost    = total_cost - previous_total_cost
            ecosystem_health = 1.0 - sum(weight[i] * effective_damage[i])

    When ecosystem.interactions is empty and all trophic_levels are -1,
    this reduces to the v0.2 algorithm exactly.

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

    # v0.3: Pre-extract interaction metadata for the loop
    agent_names: list = [a.name for a in agents]
    agent_trophic_levels: list = [a.trophic_level for a in agents]
    agent_is_keystone: list = [a.is_keystone for a in agents]
    agent_keystone_thresholds: list = [a.keystone_threshold for a in agents]

    interactions: list = ecosystem.interactions
    edge_sources: list = [e.source for e in interactions]
    edge_targets: list = [e.target for e in interactions]
    edge_strengths: list = [e.strength for e in interactions]

    # Short-circuit flags: skip v0.3 phases when not needed
    has_trophic: bool = any(lvl >= 1 for lvl in agent_trophic_levels)
    has_interactions: bool = len(interactions) > 0

    previous_total_cost: float = 0.0

    for step in range(1, units_to_extract + 1):
        units_extracted: int = step
        depletion_ratio: float = units_extracted / total_units

        # Phase 1: Direct damage with trophic amplification
        direct_damages: list = []
        for i in range(n_agents):
            raw_damage: float = agents[i].damage_function(depletion_ratio)
            if has_trophic:
                amplified: float = compute_trophic_amplification(
                    raw_damage, agent_trophic_levels[i]
                )
                direct_damages.append(amplified)
            else:
                direct_damages.append(raw_damage)

        # Phase 2: Interaction propagation
        if has_interactions:
            effective_damages, cascade_damages, keystone_triggered = (
                propagate_interactions(
                    agent_names=agent_names,
                    direct_damages=direct_damages,
                    edge_sources=edge_sources,
                    edge_targets=edge_targets,
                    edge_strengths=edge_strengths,
                    agent_is_keystone=agent_is_keystone,
                    agent_keystone_thresholds=agent_keystone_thresholds,
                )
            )
        else:
            effective_damages = direct_damages
            cascade_damages = [0.0] * n_agents
            keystone_triggered = []

        # Phase 3: Compute costs from effective damages
        agent_costs: list = []
        step_total_cost: float = 0.0
        health_sum: float = 0.0

        for i in range(n_agents):
            cost: float = (
                effective_damages[i] * agents[i].dependency_weight
                * agents[i].monetary_rate
            )
            agent_costs.append(cost)
            step_total_cost += cost
            health_sum += agents[i].dependency_weight * effective_damages[i]

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
            agent_damages=effective_damages,
            agent_costs=agent_costs,
            marginal_cost=marginal_cost,
            cumulative_cost=step_total_cost,
            private_revenue=private_revenue,
            ecosystem_health=ecosystem_health,
            agent_direct_damages=direct_damages,
            agent_cascade_damages=cascade_damages,
            keystone_triggered=keystone_triggered,
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


def run_restoration(
    ecosystem: Ecosystem,
    units_to_restore: int,
    restoration_cost: RestorationCost,
    recovery_functions: list,
) -> RestorationResult:
    """
    Simulate restoring `units_to_restore` units to the ecosystem.

    The inverse of run_extraction. At each step, the current recovery ratio is
    computed and each agent's recovery function is evaluated to get the TOTAL
    recovered ecosystem service value at that ratio. Marginal value per step is
    the difference from the previous step's total.

    v0.3: Recovery cascades propagate at reduced strength (0.5×) reflecting
    entropy asymmetry — recovery cascades are weaker than damage cascades.

    Args:
        ecosystem: The Ecosystem to restore.
        units_to_restore: Number of units to replant (>= 1, <= total_units).
        restoration_cost: RestorationCost parameters (planting + maintenance).
        recovery_functions: List of RecoveryFunc, one per agent, in the same
            order as ecosystem.agents. Each maps recovery_ratio → recovered_ratio.

    Returns:
        RestorationResult with all steps recorded.

    Raises:
        ValueError: If inputs are invalid.
    """
    validate_ecosystem(ecosystem)

    n_agents: int = len(ecosystem.agents)
    if len(recovery_functions) != n_agents:
        raise ValueError(
            f"recovery_functions must have one entry per agent. "
            f"Got {len(recovery_functions)}, expected {n_agents}."
        )
    if units_to_restore < 1:
        raise ValueError(
            f"units_to_restore must be >= 1, got {units_to_restore}."
        )
    if units_to_restore > ecosystem.resource.total_units:
        raise ValueError(
            f"units_to_restore ({units_to_restore}) cannot exceed "
            f"total_units ({ecosystem.resource.total_units})."
        )

    agents: list = ecosystem.agents
    cost_per_unit: float = restoration_cost.total_cost_per_unit

    # v0.3: Pre-extract interaction metadata
    agent_names: list = [a.name for a in agents]
    agent_trophic_levels: list = [a.trophic_level for a in agents]
    agent_is_keystone: list = [a.is_keystone for a in agents]
    agent_keystone_thresholds: list = [a.keystone_threshold for a in agents]

    interactions: list = ecosystem.interactions
    edge_sources: list = [e.source for e in interactions]
    edge_targets: list = [e.target for e in interactions]
    edge_strengths: list = [e.strength for e in interactions]

    has_trophic: bool = any(lvl >= 1 for lvl in agent_trophic_levels)
    has_interactions: bool = len(interactions) > 0

    steps: list = []
    previous_total_service: float = 0.0

    for step in range(1, units_to_restore + 1):
        units_restored: int = step
        # Recovery ratio: fraction of the destroyed resource that has been replanted
        recovery_ratio: float = units_restored / units_to_restore

        # Phase 1: Direct recovery with trophic amplification
        direct_recoveries: list = []
        for i in range(n_agents):
            recovery_fn: RecoveryFunc = recovery_functions[i]
            raw_recovery: float = recovery_fn(recovery_ratio)
            if has_trophic:
                amplified: float = compute_trophic_amplification(
                    raw_recovery, agent_trophic_levels[i]
                )
                direct_recoveries.append(amplified)
            else:
                direct_recoveries.append(raw_recovery)

        # Phase 2: Interaction propagation (recovery mode — 0.5× cascade strength)
        if has_interactions:
            effective_recoveries, _cascade, _keystone = propagate_interactions(
                agent_names=agent_names,
                direct_damages=direct_recoveries,
                edge_sources=edge_sources,
                edge_targets=edge_targets,
                edge_strengths=edge_strengths,
                agent_is_keystone=agent_is_keystone,
                agent_keystone_thresholds=agent_keystone_thresholds,
                recovery_mode=True,
            )
        else:
            effective_recoveries = direct_recoveries

        # Phase 3: Compute service values from effective recoveries
        agent_service_values: list = []
        step_total_service: float = 0.0
        health_sum: float = 0.0

        for i in range(n_agents):
            service_value: float = (
                effective_recoveries[i] * agents[i].dependency_weight
                * agents[i].monetary_rate
            )
            agent_service_values.append(service_value)
            step_total_service += service_value
            health_sum += agents[i].dependency_weight * effective_recoveries[i]

        marginal_value: float = step_total_service - previous_total_service
        ecosystem_health: float = health_sum
        if ecosystem_health < 0.0:
            ecosystem_health = 0.0
        elif ecosystem_health > 1.0:
            ecosystem_health = 1.0

        restoration_cost_so_far: float = step * cost_per_unit

        steps.append(RestorationStep(
            step=step,
            units_restored=units_restored,
            recovery_ratio=recovery_ratio,
            agent_recoveries=effective_recoveries,
            agent_service_values=agent_service_values,
            marginal_service_value=marginal_value,
            cumulative_service_value=step_total_service,
            restoration_cost_so_far=restoration_cost_so_far,
            ecosystem_health=ecosystem_health,
        ))

        previous_total_service = step_total_service

    final_step: RestorationStep = steps[-1]
    total_recovered: float = final_step.cumulative_service_value
    total_cost: float = final_step.restoration_cost_so_far

    # Prevention advantage: how many times cheaper it would have been to not
    # destroy the units vs. destroying them and then restoring them.
    # foregone_revenue = the private revenue that was earned by destroying the units
    foregone_revenue: float = units_to_restore * ecosystem.resource.unit_value
    if foregone_revenue > 0.0:
        prevention_advantage: float = (foregone_revenue + total_cost) / foregone_revenue
    else:
        prevention_advantage = 1.0

    return RestorationResult(
        ecosystem=ecosystem,
        restoration_cost=restoration_cost,
        steps=steps,
        total_units_restored=units_to_restore,
        total_restoration_cost=total_cost,
        total_recovered_value=total_recovered,
        net_restoration_value=total_recovered - total_cost,
        prevention_advantage=prevention_advantage,
        final_ecosystem_health=final_step.ecosystem_health,
    )
