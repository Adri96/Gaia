"""
Gaia v0.3 — Propagation engine tests.

Tests for trophic amplification, interaction propagation, and keystone effects.
These verify the two new cascade mechanisms introduced in v0.3:
    - Trophic amplification: higher trophic levels amplify direct damage
    - Interaction propagation: single-pass damage through agent-to-agent edges
    - Keystone effects: threshold-triggered doubling of outgoing edge strengths
"""

import pytest
from gaia.propagation import compute_trophic_amplification, propagate_interactions


# ── Trophic amplification ──────────────────────────────────────────────────────

def test_trophic_abiotic_no_amplification():
    """Abiotic agents (trophic_level=-1) get no amplification."""
    damage = 0.5
    result = compute_trophic_amplification(damage, trophic_level=-1)
    assert result == damage


def test_trophic_producer_no_amplification():
    """Producers (trophic_level=0) get no amplification."""
    damage = 0.5
    result = compute_trophic_amplification(damage, trophic_level=0)
    assert result == damage


def test_trophic_level_1_amplified():
    """Primary consumers (level 1) get amplified damage."""
    damage = 0.3
    result = compute_trophic_amplification(damage, trophic_level=1)
    # (1/0.15)^(1*0.25) ≈ 1.607 → 0.3 * 1.607 ≈ 0.482
    assert result > damage
    assert result < 1.0


def test_trophic_level_2_more_than_level_1():
    """Level 2 amplification is greater than level 1."""
    damage = 0.2
    amp1 = compute_trophic_amplification(damage, trophic_level=1)
    amp2 = compute_trophic_amplification(damage, trophic_level=2)
    assert amp2 > amp1


def test_trophic_level_3_more_than_level_2():
    """Level 3 amplification is greater than level 2."""
    damage = 0.15
    amp2 = compute_trophic_amplification(damage, trophic_level=2)
    amp3 = compute_trophic_amplification(damage, trophic_level=3)
    assert amp3 > amp2


def test_trophic_amplification_capped_at_one():
    """Amplified damage never exceeds 1.0."""
    result = compute_trophic_amplification(0.8, trophic_level=3)
    assert result <= 1.0


def test_trophic_zero_damage_stays_zero():
    """Zero damage remains zero regardless of trophic level."""
    for level in [-1, 0, 1, 2, 3]:
        assert compute_trophic_amplification(0.0, trophic_level=level) == 0.0


def test_trophic_amplification_increases_with_level():
    """Amplification monotonically increases with trophic level for small damage."""
    damage = 0.1  # Small enough to avoid capping
    results = [
        compute_trophic_amplification(damage, trophic_level=level)
        for level in [0, 1, 2, 3]
    ]
    for i in range(1, len(results)):
        assert results[i] >= results[i - 1], (
            f"Level {i} amp ({results[i]:.4f}) should be >= "
            f"level {i-1} amp ({results[i-1]:.4f})"
        )


# ── Interaction propagation ────────────────────────────────────────────────────

def _make_propagation_args(
    n_agents=3,
    names=None,
    damages=None,
    edges=None,
    keystones=None,
    thresholds=None,
):
    """Helper to build propagation function arguments."""
    if names is None:
        names = [f"Agent_{i}" for i in range(n_agents)]
    if damages is None:
        damages = [0.5] * n_agents
    if keystones is None:
        keystones = [False] * n_agents
    if thresholds is None:
        thresholds = [0.3] * n_agents

    if edges is None:
        edge_sources = []
        edge_targets = []
        edge_strengths = []
    else:
        edge_sources = [e[0] for e in edges]
        edge_targets = [e[1] for e in edges]
        edge_strengths = [e[2] for e in edges]

    return dict(
        agent_names=names,
        direct_damages=damages,
        edge_sources=edge_sources,
        edge_targets=edge_targets,
        edge_strengths=edge_strengths,
        agent_is_keystone=keystones,
        agent_keystone_thresholds=thresholds,
    )


def test_propagation_no_edges_identity():
    """With no edges, effective damages equal direct damages."""
    args = _make_propagation_args(damages=[0.3, 0.5, 0.7])
    effective, cascade, triggered = propagate_interactions(**args)
    assert effective == [0.3, 0.5, 0.7]
    assert cascade == [0.0, 0.0, 0.0]
    assert triggered == []


def test_propagation_single_edge():
    """Single edge: A→B adds A's damage * strength to B."""
    args = _make_propagation_args(
        names=["A", "B"],
        damages=[0.5, 0.2],
        edges=[("A", "B", 0.3)],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # B gets: 0.2 + 0.5 * 0.3 = 0.35
    assert effective[0] == pytest.approx(0.5)  # A unchanged
    assert effective[1] == pytest.approx(0.35)
    assert cascade[0] == pytest.approx(0.0)
    assert cascade[1] == pytest.approx(0.15)


def test_propagation_cap_at_one():
    """Effective damage is capped at 1.0 even with large propagation."""
    args = _make_propagation_args(
        names=["A", "B"],
        damages=[0.9, 0.8],
        edges=[("A", "B", 0.5)],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # B gets: 0.8 + 0.9 * 0.5 = 1.25 → capped at 1.0
    assert effective[1] <= 1.0
    # Cascade is effective - direct = 1.0 - 0.8 = 0.2 (not 0.45)
    assert cascade[1] == pytest.approx(1.0 - 0.8)


def test_propagation_multiple_incoming():
    """Target receives damage from multiple sources."""
    args = _make_propagation_args(
        names=["A", "B", "C"],
        damages=[0.4, 0.6, 0.1],
        edges=[("A", "C", 0.2), ("B", "C", 0.3)],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # C gets: 0.1 + 0.4*0.2 + 0.6*0.3 = 0.1 + 0.08 + 0.18 = 0.36
    assert effective[2] == pytest.approx(0.36)
    assert cascade[2] == pytest.approx(0.26)


def test_propagation_chain_single_pass():
    """
    Chain A→B→C: A reaches B but NOT C (single-pass, frozen source lookup).

    This is the critical correctness test: we read from direct_damages (frozen),
    not from the mutating effective array. So B's increased damage from A does
    NOT propagate further to C.
    """
    args = _make_propagation_args(
        names=["A", "B", "C"],
        damages=[0.5, 0.1, 0.0],
        edges=[("A", "B", 0.4), ("B", "C", 0.5)],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # B gets: 0.1 + 0.5 * 0.4 = 0.3
    assert effective[1] == pytest.approx(0.3)
    # C gets: 0.0 + 0.1 * 0.5 = 0.05 (reads B's ORIGINAL 0.1, not 0.3)
    assert effective[2] == pytest.approx(0.05)


def test_propagation_order_independence():
    """Result is the same regardless of edge ordering."""
    edges_v1 = [("A", "C", 0.3), ("B", "C", 0.2)]
    edges_v2 = [("B", "C", 0.2), ("A", "C", 0.3)]  # reversed order

    args1 = _make_propagation_args(
        names=["A", "B", "C"],
        damages=[0.5, 0.4, 0.1],
        edges=edges_v1,
    )
    args2 = _make_propagation_args(
        names=["A", "B", "C"],
        damages=[0.5, 0.4, 0.1],
        edges=edges_v2,
    )
    effective1, _, _ = propagate_interactions(**args1)
    effective2, _, _ = propagate_interactions(**args2)
    for i in range(3):
        assert effective1[i] == pytest.approx(effective2[i])


# ── Keystone effects ───────────────────────────────────────────────────────────

def test_keystone_not_triggered_above_threshold():
    """Keystone agent above threshold: no doubling."""
    args = _make_propagation_args(
        names=["K", "T"],
        damages=[0.5, 0.2],  # K health = 0.5 > threshold 0.3
        edges=[("K", "T", 0.3)],
        keystones=[True, False],
        thresholds=[0.3, 0.3],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # T gets: 0.2 + 0.5 * 0.3 = 0.35 (normal strength)
    assert effective[1] == pytest.approx(0.35)
    assert triggered == []


def test_keystone_triggered_below_threshold():
    """Keystone agent below threshold: outgoing edge strength doubles."""
    args = _make_propagation_args(
        names=["K", "T"],
        damages=[0.8, 0.2],  # K health = 1.0 - 0.8 = 0.2 < threshold 0.3
        edges=[("K", "T", 0.3)],
        keystones=[True, False],
        thresholds=[0.3, 0.3],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # T gets: 0.2 + 0.8 * 0.6 = 0.2 + 0.48 = 0.68 (doubled: 0.3→0.6)
    assert effective[1] == pytest.approx(0.68)
    assert "K" in triggered


def test_keystone_doubled_strength_capped():
    """Doubled keystone edge strength cannot exceed 1.0."""
    args = _make_propagation_args(
        names=["K", "T"],
        damages=[0.8, 0.1],
        edges=[("K", "T", 0.7)],  # 0.7 * 2 = 1.4 → capped at 1.0
        keystones=[True, False],
        thresholds=[0.3, 0.3],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # T gets: 0.1 + 0.8 * 1.0 = 0.9 (capped strength is 1.0)
    assert effective[1] == pytest.approx(0.9)
    assert "K" in triggered


def test_non_keystone_unaffected_by_health():
    """Non-keystone agents never double edge strengths."""
    args = _make_propagation_args(
        names=["A", "B"],
        damages=[0.9, 0.1],  # A health = 0.1, but not keystone
        edges=[("A", "B", 0.3)],
        keystones=[False, False],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # B gets: 0.1 + 0.9 * 0.3 = 0.37 (normal strength, no doubling)
    assert effective[1] == pytest.approx(0.37)
    assert triggered == []


def test_keystone_only_doubles_own_edges():
    """Keystone doubling only applies to the keystone agent's outgoing edges."""
    args = _make_propagation_args(
        names=["K", "A", "B"],
        damages=[0.8, 0.6, 0.1],  # K triggered (health 0.2 < 0.3)
        edges=[
            ("K", "B", 0.2),  # This doubles: 0.2 → 0.4
            ("A", "B", 0.2),  # This stays: 0.2
        ],
        keystones=[True, False, False],
        thresholds=[0.3, 0.3, 0.3],
    )
    effective, cascade, triggered = propagate_interactions(**args)
    # B gets: 0.1 + 0.8*0.4 + 0.6*0.2 = 0.1 + 0.32 + 0.12 = 0.54
    assert effective[2] == pytest.approx(0.54)


# ── Recovery mode ──────────────────────────────────────────────────────────────

def test_recovery_mode_reduces_cascade():
    """In recovery mode, cascade strength is halved (0.5×)."""
    base_args = _make_propagation_args(
        names=["A", "B"],
        damages=[0.5, 0.2],
        edges=[("A", "B", 0.4)],
    )
    eff_normal, _, _ = propagate_interactions(**base_args)
    eff_recovery, _, _ = propagate_interactions(**base_args, recovery_mode=True)

    # Normal: B = 0.2 + 0.5 * 0.4 = 0.40
    # Recovery: B = 0.2 + 0.5 * 0.4 * 0.5 = 0.2 + 0.1 = 0.30
    assert eff_normal[1] == pytest.approx(0.40)
    assert eff_recovery[1] == pytest.approx(0.30)
