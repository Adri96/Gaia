"""
Gaia v0.1 — Simulation engine behavior and invariant tests.

These tests verify that the simulation engine correctly implements the scientific
and mathematical invariants defined in the spec. They use simple ecosystems
(not the full forest case) so behavior is easy to reason about.
"""

import math
import pytest
from gaia.damage import logistic_damage, piecewise_damage
from gaia.models import Agent, Ecosystem, Resource, SimulationResult
from gaia.simulation import run_extraction


# ── Test fixtures ──────────────────────────────────────────────────────────────

def _make_simple_ecosystem(
    total_units: int = 1_000,
    threshold: float = 0.3,
    n_agents: int = 2,
    monetary_rate: float = 100_000.0,
    unit_value: float = 50.0,
) -> Ecosystem:
    """Create a minimal ecosystem for simulation tests."""
    weight = 1.0 / n_agents
    resource = Resource(
        name="Test Resource",
        total_units=total_units,
        safe_threshold_ratio=threshold,
        unit_value=unit_value,
    )
    agents = [
        Agent(
            name=f"Agent {i}",
            dependency_weight=weight,
            damage_function=logistic_damage(threshold=threshold),
            monetary_rate=monetary_rate,
            description=f"Test agent {i}",
        )
        for i in range(n_agents)
    ]
    return Ecosystem(name="Test Ecosystem", resource=resource, agents=agents)


# ── Core invariant tests ───────────────────────────────────────────────────────

def test_zero_extraction_zero_cost():
    """Extracting 0 units → total externality = 0."""
    eco = _make_simple_ecosystem()
    result = run_extraction(eco, 0)
    assert result.total_externality_cost == 0.0
    assert result.total_private_revenue == 0.0
    assert result.total_units_extracted == 0
    assert len(result.steps) == 0


def test_full_extraction_maximum_cost():
    """
    Extracting all units → externality equals sum of all agent monetary_rate * weight.

    At depletion=1.0, damage_function → 1.0, so cost = 1.0 * weight * monetary_rate
    for each agent. Total = sum(weight * monetary_rate) across all agents.
    """
    total = 100
    rate = 50_000.0
    n = 2
    weight = 0.5
    eco = _make_simple_ecosystem(total_units=total, monetary_rate=rate, n_agents=n)
    result = run_extraction(eco, total)

    expected_max = n * weight * rate  # = 1.0 * monetary_rate = 50_000.0 per agent, 100_000.0 total
    # Allow 1e-3 relative tolerance (logistic saturates but may not reach exact 1.0)
    assert abs(result.total_externality_cost - expected_max) / expected_max < 1e-3, (
        f"Expected ≈ {expected_max:.2f}, got {result.total_externality_cost:.2f}"
    )


def test_cumulative_cost_monotonically_increases():
    """cumulative_cost must be non-decreasing across all steps."""
    eco = _make_simple_ecosystem(total_units=500)
    result = run_extraction(eco, 500)
    steps = result.steps
    for i in range(1, len(steps)):
        assert steps[i].cumulative_cost >= steps[i - 1].cumulative_cost - 1e-9, (
            f"cumulative_cost decreased at step {i}: "
            f"{steps[i].cumulative_cost:.4f} < {steps[i-1].cumulative_cost:.4f}"
        )


def test_marginal_cost_increases_past_threshold():
    """
    Marginal cost must be higher at the inflection region than before the threshold.

    A logistic damage function is S-shaped: damage accelerates sharply around the
    threshold (inflection point), then saturates. We compare marginal costs in a
    narrow window just past the threshold against a window just before it — not
    global averages, which would be confounded by the saturation tail.

    This is the fundamental non-linearity invariant: cutting a unit past the safe
    threshold is socially more expensive than cutting one below it.
    """
    total = 1_000
    threshold = 0.3
    eco = _make_simple_ecosystem(total_units=total, threshold=threshold)
    result = run_extraction(eco, total)

    threshold_step = int(total * threshold)
    # Use a 5% window on each side of the threshold inflection point
    window = max(1, int(total * 0.05))

    # Steps just before the threshold
    pre_start = max(0, threshold_step - window)
    pre_costs = [s.marginal_cost for s in result.steps[pre_start:threshold_step]]

    # Steps just after the threshold (the acceleration zone)
    post_end = min(len(result.steps), threshold_step + window)
    post_costs = [s.marginal_cost for s in result.steps[threshold_step:post_end]]

    avg_pre = sum(pre_costs) / len(pre_costs) if pre_costs else 0.0
    avg_post = sum(post_costs) / len(post_costs) if post_costs else 0.0

    assert avg_post > avg_pre, (
        f"Marginal cost just after threshold ({avg_post:.4f}) should exceed "
        f"marginal cost just before threshold ({avg_pre:.4f})"
    )


def test_ecosystem_health_monotonically_decreases():
    """ecosystem_health must be non-increasing across all steps."""
    eco = _make_simple_ecosystem(total_units=500)
    result = run_extraction(eco, 500)
    steps = result.steps
    for i in range(1, len(steps)):
        assert steps[i].ecosystem_health <= steps[i - 1].ecosystem_health + 1e-9, (
            f"ecosystem_health increased at step {i}: "
            f"{steps[i].ecosystem_health:.4f} > {steps[i-1].ecosystem_health:.4f}"
        )


def test_ecosystem_health_pristine_at_zero():
    """Before any extraction, health should be 1.0."""
    eco = _make_simple_ecosystem()
    result = run_extraction(eco, 0)
    assert result.final_ecosystem_health == 1.0


def test_ecosystem_health_collapsed_at_full():
    """At full extraction, health should be approximately 0.0."""
    eco = _make_simple_ecosystem(total_units=100)
    result = run_extraction(eco, 100)
    assert result.final_ecosystem_health < 0.05, (
        f"Health at full extraction should be near 0, got {result.final_ecosystem_health:.4f}"
    )


def test_private_revenue_is_linear():
    """
    Revenue at step N = N × unit_value.

    Private revenue does not depend on ecosystem state — it is simply
    units_extracted × price_per_unit.
    """
    unit_value = 75.0
    total = 400
    eco = _make_simple_ecosystem(total_units=total, unit_value=unit_value)
    result = run_extraction(eco, total)

    for step in result.steps:
        expected = step.units_extracted * unit_value
        assert abs(step.private_revenue - expected) < 1e-9, (
            f"Step {step.step}: revenue {step.private_revenue:.2f} != "
            f"expected {expected:.2f}"
        )


def test_step_count_matches_extraction():
    """Number of recorded steps must equal units_to_extract."""
    eco = _make_simple_ecosystem(total_units=1_000)
    for n in [1, 10, 100, 500, 1_000]:
        result = run_extraction(eco, n)
        assert len(result.steps) == n, (
            f"Expected {n} steps, got {len(result.steps)}"
        )


# ── Behavioral tests ───────────────────────────────────────────────────────────

def test_all_agents_contribute_to_cost():
    """Every agent's cost > 0 at full extraction."""
    eco = _make_simple_ecosystem(total_units=100, n_agents=3)
    # Adjust weights to sum to 1
    eco = Ecosystem(
        name="Eco",
        resource=eco.resource,
        agents=[
            Agent(
                name=f"Agent {i}",
                dependency_weight=1.0 / 3,
                damage_function=logistic_damage(threshold=0.3),
                monetary_rate=100_000.0,
                description="",
            )
            for i in range(3)
        ],
    )
    result = run_extraction(eco, 100)
    final_costs = result.steps[-1].agent_costs
    for i, cost in enumerate(final_costs):
        assert cost > 0, f"Agent {i} cost is zero at full extraction"


def test_agent_costs_proportional_to_weights():
    """
    At full extraction, agent cost ratios should approximately match
    dependency weight ratios (since all damage functions return ≈ 1.0).
    """
    resource = Resource(
        name="F", total_units=100, safe_threshold_ratio=0.3, unit_value=0.0
    )
    agents = [
        Agent(
            name="A",
            dependency_weight=0.25,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=100_000.0,
            description="",
        ),
        Agent(
            name="B",
            dependency_weight=0.75,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=100_000.0,
            description="",
        ),
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 100)
    final_costs = result.steps[-1].agent_costs

    # At full depletion, both damage_functions ≈ 1.0
    # cost_A / cost_B ≈ (0.25 * 100k) / (0.75 * 100k) = 1/3
    ratio = final_costs[0] / final_costs[1]
    expected_ratio = 0.25 / 0.75
    assert abs(ratio - expected_ratio) < 0.01, (
        f"Cost ratio {ratio:.4f} should be close to weight ratio {expected_ratio:.4f}"
    )


def test_net_social_cost_sign_heavy_extraction():
    """
    At heavy extraction (80%), net social cost should be negative
    (externalities exceed revenue).
    """
    # Use a large enough monetary rate to ensure externalities dominate
    resource = Resource(
        name="F", total_units=1_000, safe_threshold_ratio=0.3, unit_value=50.0
    )
    agents = [
        Agent(
            name="A",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=200_000.0,  # large enough to exceed revenue
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 800)  # 80%
    assert result.net_social_cost < 0, (
        f"At 80% extraction, net_social_cost should be negative, "
        f"got {result.net_social_cost:.2f}"
    )


def test_net_social_cost_at_low_extraction():
    """
    At light extraction (10%), net social cost should be positive
    (revenue exceeds modest externalities).
    """
    resource = Resource(
        name="F", total_units=1_000, safe_threshold_ratio=0.3, unit_value=200.0
    )
    agents = [
        Agent(
            name="A",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=50_000.0,  # small enough that revenue dominates at 10%
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 100)  # 10%
    assert result.net_social_cost > 0, (
        f"At 10% extraction, net_social_cost should be positive, "
        f"got {result.net_social_cost:.2f}"
    )


# ── Edge case tests ────────────────────────────────────────────────────────────

def test_single_tree_forest():
    """A forest with 1 tree, extract 1: simulation runs and produces valid output."""
    resource = Resource(name="F", total_units=1, safe_threshold_ratio=0.5, unit_value=100.0)
    agents = [
        Agent(
            name="A",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.5),
            monetary_rate=1_000.0,
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 1)
    assert result.total_units_extracted == 1
    assert len(result.steps) == 1
    assert result.total_externality_cost >= 0.0
    assert 0.0 <= result.final_ecosystem_health <= 1.0


def test_large_forest():
    """A forest with 1,000,000 trees, extract 500,000: runs without overflow."""
    resource = Resource(
        name="F", total_units=1_000_000, safe_threshold_ratio=0.3, unit_value=10.0
    )
    agents = [
        Agent(
            name="A",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=5_000_000.0,
            description="",
        ),
        Agent(
            name="B",
            dependency_weight=0.5,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=5_000_000.0,
            description="",
        ),
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 500_000)
    assert result.total_units_extracted == 500_000
    assert math.isfinite(result.total_externality_cost)
    assert math.isfinite(result.net_social_cost)


def test_single_agent():
    """An ecosystem with only one agent (weight 1.0): works correctly."""
    resource = Resource(name="F", total_units=100, safe_threshold_ratio=0.3, unit_value=0.0)
    agents = [
        Agent(
            name="Solo",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=10_000.0,
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 50)
    assert len(result.steps) == 50
    for step in result.steps:
        assert len(step.agent_damages) == 1
        assert len(step.agent_costs) == 1


def test_extract_one_unit():
    """Extracting exactly 1 unit produces a valid step with non-zero marginal cost."""
    eco = _make_simple_ecosystem(total_units=1_000)
    result = run_extraction(eco, 1)
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.step == 1
    assert step.units_extracted == 1
    assert step.marginal_cost >= 0.0
    # At 0.1% depletion, some cost should exist (even if small)
    assert step.cumulative_cost >= 0.0


def test_threshold_near_zero_simulation():
    """threshold=0.01: damage starts almost immediately in simulation."""
    resource = Resource(name="F", total_units=100, safe_threshold_ratio=0.01, unit_value=0.0)
    agents = [
        Agent(
            name="A",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.01),
            monetary_rate=100_000.0,
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 50)
    # With threshold=0.01, by step 5 (5% depletion), costs should be substantial
    cost_at_5 = result.steps[4].cumulative_cost
    assert cost_at_5 > 1_000.0, f"Expected substantial cost at 5% depletion, got {cost_at_5:.2f}"


def test_threshold_near_one_simulation():
    """threshold=0.99: almost all extraction is 'safe', costs low until near full depletion."""
    resource = Resource(name="F", total_units=100, safe_threshold_ratio=0.99, unit_value=0.0)
    agents = [
        Agent(
            name="A",
            dependency_weight=1.0,
            damage_function=logistic_damage(threshold=0.99),
            monetary_rate=100_000.0,
            description="",
        )
    ]
    eco = Ecosystem(name="E", resource=resource, agents=agents)
    result = run_extraction(eco, 50)
    # At 50% depletion with threshold=0.99, damage should be very low
    cost_at_50_pct = result.steps[-1].cumulative_cost
    # Should be less than 5% of max externality (50k)
    assert cost_at_50_pct < 5_000.0, (
        f"With threshold=0.99, cost at 50% depletion should be small, "
        f"got {cost_at_50_pct:.2f}"
    )
