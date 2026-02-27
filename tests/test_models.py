"""
Gaia v0.1 — Data model construction and constraint tests.

Tests that the dataclasses can be created with valid parameters, that derived
properties are correctly computed, and that fields have the expected types.
"""

import pytest
from gaia.damage import logistic_damage
from gaia.models import Agent, Ecosystem, Resource, SimulationStep


# ── Resource ───────────────────────────────────────────────────────────────────

def test_resource_creation():
    """Resource can be created with valid parameters."""
    r = Resource(
        name="Test Forest",
        total_units=10_000,
        safe_threshold_ratio=0.3,
        unit_value=100.0,
    )
    assert r.name == "Test Forest"
    assert r.total_units == 10_000
    assert r.safe_threshold_ratio == 0.3
    assert r.unit_value == 100.0


def test_resource_safe_threshold_units():
    """Derived safe_threshold_units is correctly computed as int(total * ratio)."""
    r = Resource(name="F", total_units=10_000, safe_threshold_ratio=0.3, unit_value=0.0)
    assert r.safe_threshold_units == 3_000

    r2 = Resource(name="F", total_units=7_500, safe_threshold_ratio=0.4, unit_value=0.0)
    assert r2.safe_threshold_units == 3_000  # int(7500 * 0.4) = 3000

    r3 = Resource(name="F", total_units=1, safe_threshold_ratio=0.5, unit_value=0.0)
    assert r3.safe_threshold_units == 0  # int(1 * 0.5) = 0


def test_resource_safe_threshold_units_floors_correctly():
    """safe_threshold_units uses int() (floor division) not round()."""
    r = Resource(name="F", total_units=10_001, safe_threshold_ratio=0.3, unit_value=0.0)
    # 10001 * 0.3 = 3000.3 → int → 3000
    assert r.safe_threshold_units == 3_000


# ── Agent ──────────────────────────────────────────────────────────────────────

def test_agent_creation():
    """Agent can be created with valid parameters."""
    fn = logistic_damage(threshold=0.3)
    agent = Agent(
        name="Test Agent",
        dependency_weight=0.5,
        damage_function=fn,
        monetary_rate=100_000.0,
        description="A test agent",
    )
    assert agent.name == "Test Agent"
    assert agent.dependency_weight == 0.5
    assert agent.monetary_rate == 100_000.0
    assert agent.description == "A test agent"
    assert callable(agent.damage_function)


def test_agent_damage_function_is_callable():
    """The stored damage_function is callable and returns a float."""
    fn = logistic_damage(threshold=0.3)
    agent = Agent(
        name="A",
        dependency_weight=1.0,
        damage_function=fn,
        monetary_rate=1.0,
        description="",
    )
    result = agent.damage_function(0.5)
    assert isinstance(result, float)


# ── Ecosystem ──────────────────────────────────────────────────────────────────

def _make_ecosystem(n_agents: int = 2, weights: list = None) -> Ecosystem:
    """Helper: build a simple ecosystem with n equal-weight agents."""
    if weights is None:
        weights = [1.0 / n_agents] * n_agents

    resource = Resource(
        name="Test Forest",
        total_units=1_000,
        safe_threshold_ratio=0.3,
        unit_value=50.0,
    )
    agents = [
        Agent(
            name=f"Agent {i}",
            dependency_weight=weights[i],
            damage_function=logistic_damage(threshold=0.3),
            monetary_rate=10_000.0,
            description=f"Test agent {i}",
        )
        for i in range(n_agents)
    ]
    return Ecosystem(name="Test Ecosystem", resource=resource, agents=agents)


def test_ecosystem_creation():
    """Ecosystem can be created with a resource and agents."""
    eco = _make_ecosystem(2)
    assert eco.name == "Test Ecosystem"
    assert isinstance(eco.resource, Resource)
    assert len(eco.agents) == 2


def test_ecosystem_weights_sum():
    """Dependency weights across all agents sum to 1.0."""
    eco = _make_ecosystem(4, weights=[0.25, 0.25, 0.25, 0.25])
    total = sum(a.dependency_weight for a in eco.agents)
    assert abs(total - 1.0) < 1e-9


def test_ecosystem_agents_list_type():
    """Ecosystem.agents is a plain list (Cython compat)."""
    eco = _make_ecosystem(3)
    assert isinstance(eco.agents, list)


# ── SimulationStep ─────────────────────────────────────────────────────────────

def test_simulation_step_fields():
    """SimulationStep stores all expected fields with correct types."""
    step = SimulationStep(
        step=1,
        units_extracted=1,
        depletion_ratio=0.001,
        agent_damages=[0.01, 0.02],
        agent_costs=[100.0, 200.0],
        marginal_cost=300.0,
        cumulative_cost=300.0,
        private_revenue=100.0,
        ecosystem_health=0.98,
    )
    assert step.step == 1
    assert step.units_extracted == 1
    assert isinstance(step.depletion_ratio, float)
    assert isinstance(step.agent_damages, list)
    assert isinstance(step.agent_costs, list)
    assert isinstance(step.marginal_cost, float)
    assert isinstance(step.cumulative_cost, float)
    assert isinstance(step.private_revenue, float)
    assert isinstance(step.ecosystem_health, float)
    assert len(step.agent_damages) == 2
    assert len(step.agent_costs) == 2
