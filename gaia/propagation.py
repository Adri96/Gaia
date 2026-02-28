"""
Gaia v0.3 — Trophic amplification and agent interaction propagation.

This module implements the two cascade mechanisms introduced in v0.3:

1. Trophic amplification — higher trophic levels are more sensitive to
   resource loss (Foundation F3: energy transfer efficiency 5-20%).

2. Interaction propagation — a single-pass propagation of damage through
   agent-to-agent edges, with keystone species amplification (Foundation F6).

All functions use primitive types (float, int, list, dict) for Cython compatibility.
No third-party dependencies.

Scientific foundations used: F3 (Trophic Pyramids), F6 (Keystone Species), F10 (Coevolution).
"""


def compute_trophic_amplification(
    direct_damage: float,
    trophic_level: int,
    transfer_efficiency: float = 0.15,
) -> float:
    """
    Apply trophic energy pyramid amplification to direct damage.

    Higher trophic levels are inherently more sensitive to changes at the base
    because energy transfer between levels is only 5-20% efficient.

    Amplification factor = (1 / transfer_efficiency) ^ (trophic_level * 0.25)

    The 0.25 scaling factor tames the raw trophic pyramid math to a realistic
    range (1.5x-3.4x) for a single-resource model.
    [PLACEHOLDER — scaling factor needs ecological validation]

    Args:
        direct_damage: Raw damage from the agent's damage function (0.0 to 1.0).
        trophic_level: -1=abiotic, 0=producer, 1-3=consumers.
        transfer_efficiency: Energy transfer efficiency between levels.
            Default 0.15 (15%, middle of 5-20% range). [PLACEHOLDER]

    Returns:
        Amplified damage, capped at 1.0.
    """
    if trophic_level <= 0:
        # Producers and abiotic services: no amplification
        return direct_damage
    amplification: float = (1.0 / transfer_efficiency) ** (trophic_level * 0.25)
    result: float = direct_damage * amplification
    if result > 1.0:
        return 1.0
    return result


def propagate_interactions(
    agent_names: list,
    direct_damages: list,
    edge_sources: list,
    edge_targets: list,
    edge_strengths: list,
    agent_is_keystone: list,
    agent_keystone_thresholds: list,
    recovery_mode: bool = False,
    recovery_cascade_factor: float = 0.5,
) -> tuple:
    """
    Single-pass propagation of damage through interaction edges.

    After direct damage (with trophic amplification) is computed for all agents,
    this function propagates damage through agent-to-agent edges. Each edge adds
    source_damage * strength to the target's effective damage.

    Source lookups read from the ORIGINAL direct_damages (frozen), not the
    mutating effective array. This ensures:
    - Chain non-propagation: A->B->C means A reaches B but NOT C in one pass
    - Order independence: result is the same regardless of edge ordering

    Keystone effect: when a keystone agent's health (1 - direct_damage) drops
    below its keystone_threshold, ALL its outgoing edges have strength doubled
    (capped at 1.0).

    Args:
        agent_names: List of agent name strings, in ecosystem order.
        direct_damages: Direct damage per agent (post-trophic-amplification).
        edge_sources: Source agent name per edge.
        edge_targets: Target agent name per edge.
        edge_strengths: Base strength per edge (0.0 to 1.0).
        agent_is_keystone: Boolean per agent — is this a keystone species?
        agent_keystone_thresholds: Keystone threshold per agent.
        recovery_mode: If True, multiply edge strengths by recovery_cascade_factor.
        recovery_cascade_factor: Strength multiplier for recovery cascades.
            Default 0.5 — recovery cascades are weaker than damage cascades
            (entropy asymmetry). [PLACEHOLDER]

    Returns:
        Tuple of (effective_damages, cascade_damages, keystone_triggered):
        - effective_damages: list of float — final damage per agent after propagation
        - cascade_damages: list of float — additional damage from interactions per agent
        - keystone_triggered: list of str — names of agents whose keystone threshold crossed
    """
    n_agents: int = len(agent_names)
    n_edges: int = len(edge_sources)

    # Build name-to-index lookup
    name_to_idx: dict = {}
    for i in range(n_agents):
        name_to_idx[agent_names[i]] = i

    # Initialize effective damages as a copy of direct damages
    effective: list = list(direct_damages)
    cascade: list = [0.0] * n_agents

    # No edges: short-circuit
    if n_edges == 0:
        return (effective, cascade, [])

    # Determine keystone-triggered agents and compute effective edge strengths
    keystone_triggered: list = []
    effective_strengths: list = list(edge_strengths)

    for i in range(n_agents):
        if agent_is_keystone[i]:
            agent_health: float = 1.0 - direct_damages[i]
            if agent_health < agent_keystone_thresholds[i]:
                keystone_triggered.append(agent_names[i])
                # Double outgoing edge strengths for this keystone agent
                for e in range(n_edges):
                    if edge_sources[e] == agent_names[i]:
                        doubled: float = edge_strengths[e] * 2.0
                        if doubled > 1.0:
                            doubled = 1.0
                        effective_strengths[e] = doubled

    # Apply recovery mode scaling
    if recovery_mode:
        for e in range(n_edges):
            effective_strengths[e] = effective_strengths[e] * recovery_cascade_factor

    # Single-pass propagation: read from direct_damages (frozen), write to effective
    for e in range(n_edges):
        src_idx: int = name_to_idx[edge_sources[e]]
        tgt_idx: int = name_to_idx[edge_targets[e]]
        source_damage: float = direct_damages[src_idx]
        additional: float = source_damage * effective_strengths[e]
        cascade[tgt_idx] += additional
        effective[tgt_idx] = effective[tgt_idx] + additional
        if effective[tgt_idx] > 1.0:
            effective[tgt_idx] = 1.0

    # Recompute cascade as effective - direct (accounts for capping)
    for i in range(n_agents):
        cascade[i] = effective[i] - direct_damages[i]
        if cascade[i] < 0.0:
            cascade[i] = 0.0

    return (effective, cascade, keystone_triggered)
