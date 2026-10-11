"""
Gaia v0.3 — Trophic amplification and agent interaction propagation.

This module implements the two cascade mechanisms introduced in v0.3:

1. Trophic amplification — higher trophic levels are more sensitive to
   resource loss (Foundation F3: energy transfer efficiency 5-20%).

2. Interaction propagation — a single-pass propagation of damage through
   agent-to-agent edges, with keystone species amplification (Foundation F6).

Step 3.8 (S2): validation caps each agent's incoming edge strengths,
keystone multipliers included, at MAX_INCOMING_EDGE_STRENGTH = 1.

The constants live in gaia.constants. All propagation functions use
primitive types (float, int, list, dict) for Cython compatibility; the
ecosystem-level helpers at the end are for validation, not the hot loop.
No third-party dependencies.

Scientific foundations used: F3 (Trophic Pyramids), F6 (Keystone Species), F10 (Coevolution).
"""

from gaia.constants import (
    KEYSTONE_EDGE_MULTIPLIER,
    MAX_EDGE_STRENGTH,
    RECOVERY_CASCADE_FACTOR,
    TROPHIC_AMPLIFICATION_EXPONENT,
    TROPHIC_TRANSFER_EFFICIENCY,
)


def trophic_amplification_factor(
    trophic_level: int,
    transfer_efficiency: float = TROPHIC_TRANSFER_EFFICIENCY,
) -> float:
    """
    Trophic amplification factor for an agent: 1.0 for producers and abiotic
    services (level <= 0), else
        (1 / transfer_efficiency) ** (TROPHIC_AMPLIFICATION_EXPONENT * level)
    i.e. 1.6× / 2.6× / 4.2× for levels 1 / 2 / 3 at the default efficiency.
    Both engines and the text report use this one function.
    """
    if trophic_level <= 0:
        return 1.0
    return (1.0 / transfer_efficiency) ** (trophic_level * TROPHIC_AMPLIFICATION_EXPONENT)


def compute_trophic_amplification(
    direct_damage: float,
    trophic_level: int,
    transfer_efficiency: float = TROPHIC_TRANSFER_EFFICIENCY,
) -> float:
    """
    Apply trophic energy pyramid amplification to direct damage.

    Higher trophic levels are inherently more sensitive to changes at the base
    because energy transfer between levels is only 5-20% efficient.

    Amplified damage = direct_damage × trophic_amplification_factor(level),
    capped at 1.0. The constants (both PLACEHOLDER) are documented in
    gaia.constants.

    Args:
        direct_damage: Raw damage from the agent's damage function (0.0 to 1.0).
        trophic_level: -1=abiotic, 0=producer, 1-3=consumers.
        transfer_efficiency: Energy transfer efficiency between levels.

    Returns:
        Amplified damage, capped at 1.0.
    """
    if trophic_level <= 0:
        # Producers and abiotic services: no amplification
        return direct_damage
    amplification: float = trophic_amplification_factor(trophic_level, transfer_efficiency)
    result: float = direct_damage * amplification
    if result > 1.0:
        return 1.0
    return result


def keystone_boosted_strength(strength: float) -> float:
    """Strength of an edge whose keystone source has crossed its threshold:
    strength × KEYSTONE_EDGE_MULTIPLIER, capped at MAX_EDGE_STRENGTH."""
    boosted: float = strength * KEYSTONE_EDGE_MULTIPLIER
    if boosted > MAX_EDGE_STRENGTH:
        return MAX_EDGE_STRENGTH
    return boosted


def propagate_interactions(
    agent_names: list,
    direct_damages: list,
    edge_sources: list,
    edge_targets: list,
    edge_strengths: list,
    agent_is_keystone: list,
    agent_keystone_thresholds: list,
    recovery_mode: bool = False,
    recovery_cascade_factor: float = RECOVERY_CASCADE_FACTOR,
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

    CALIBRATION ASSUMPTION — critical for correct use:
    The chain non-propagation is only ecologically valid if damage_function
    values are calibrated from real-world empirical observations. Field data
    already embeds indirect effects: an observed predator population decline
    measured against deforestation rate implicitly captures the full chain
    (trees → prey → predator). Adding full multi-hop cascade propagation on
    top of empirically-calibrated damage functions would double-count those
    indirect effects.

    If, instead, damage functions are calibrated from first-principles or
    controlled lab studies that isolate only the direct dependency on the
    resource, then this single-pass propagation underestimates cascade damage
    in chains longer than one hop (e.g. A→B→C: A's contribution to B's
    degradation never reaches C).

    The builder of each ecosystem case is responsible for choosing one
    interpretation and applying it consistently across all agents. Mixing
    empirical functions for some agents with theoretical functions for others
    will produce incoherent results. Each Ecosystem declares its choice in
    calibration_regime (gaia.models.CalibrationRegime); this trade-off is
    documented in PROJECT_DEFINITION.md and V03_SPEC.md.

    Keystone effect: when a keystone agent's health (1 - direct_damage) drops
    below its keystone_threshold, ALL its outgoing edges are boosted to
    keystone_boosted_strength() (× KEYSTONE_EDGE_MULTIPLIER, capped at 1.0).

    Args:
        agent_names: List of agent name strings, in ecosystem order.
        direct_damages: Direct damage per agent (post-trophic-amplification).
        edge_sources: Source agent name per edge.
        edge_targets: Target agent name per edge.
        edge_strengths: Base strength per edge (0.0 to 1.0).
        agent_is_keystone: Boolean per agent — is this a keystone species?
        agent_keystone_thresholds: Keystone threshold per agent.
        recovery_mode: If True, multiply edge strengths by recovery_cascade_factor.
            Not used by run_restoration since Step 3.3, which reverses the
            extraction's effective damage instead of propagating recoveries.
        recovery_cascade_factor: Strength multiplier for recovery cascades.
            Default RECOVERY_CASCADE_FACTOR (gaia.constants). [PLACEHOLDER]

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
                # Boost outgoing edge strengths for this keystone agent
                for e in range(n_edges):
                    if edge_sources[e] == agent_names[i]:
                        effective_strengths[e] = keystone_boosted_strength(
                            edge_strengths[e]
                        )

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


# ── Ecosystem-level helpers (validation; not used by the hot loops) ─────────


def worst_case_incoming_strengths(agents: list, interactions: list) -> dict:
    """
    Sum of incoming edge strengths per target agent, at their worst case:
    an edge whose source is a keystone agent counts at
    keystone_boosted_strength(), because the boost applies exactly when the
    source is collapsing and the cascade matters most.

    Returns:
        {target agent name: summed strength}, for agents with incoming edges.
    """
    keystones: set = {a.name for a in agents if a.is_keystone}
    totals: dict = {}
    for edge in interactions:
        strength: float = (
            keystone_boosted_strength(edge.strength)
            if edge.source in keystones else edge.strength
        )
        totals[edge.target] = totals.get(edge.target, 0.0) + strength
    return totals


def effective_damages_at(ecosystem, depletion_ratio: float) -> list:
    """
    Every agent's effective damage at one depletion ratio — the same
    computation as one step of the extraction loop (damage function, trophic
    amplification, interaction propagation), without running the loop.
    """
    agents: list = ecosystem.agents
    direct: list = [
        compute_trophic_amplification(a.damage_function(depletion_ratio), a.trophic_level)
        for a in agents
    ]
    interactions: list = ecosystem.interactions
    if not interactions:
        return direct
    effective, _, _ = propagate_interactions(
        agent_names=[a.name for a in agents],
        direct_damages=direct,
        edge_sources=[e.source for e in interactions],
        edge_targets=[e.target for e in interactions],
        edge_strengths=[e.strength for e in interactions],
        agent_is_keystone=[a.is_keystone for a in agents],
        agent_keystone_thresholds=[a.keystone_threshold for a in agents],
    )
    return effective


def ecosystem_health_at(ecosystem, depletion_ratio: float) -> float:
    """Ecosystem health, 1 − Σ weight × effective damage clamped to [0, 1],
    at one depletion ratio (as in the extraction loop)."""
    damages: list = effective_damages_at(ecosystem, depletion_ratio)
    health: float = 1.0 - sum(
        a.dependency_weight * d for a, d in zip(ecosystem.agents, damages)
    )
    if health < 0.0:
        return 0.0
    if health > 1.0:
        return 1.0
    return health
