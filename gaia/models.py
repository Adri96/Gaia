"""
Gaia v0.1 — Core data models.

All models are typed dataclasses with primitive fields.
No inheritance, no dynamic attributes, no **kwargs.
All models are Cython-compatible.
"""

from dataclasses import dataclass
from typing import Callable, List

# Type alias for damage functions: depletion_ratio -> damage_ratio
DamageFunc = Callable[[float], float]


@dataclass
class Resource:
    """
    The shared natural asset being extracted.

    Attributes:
        name: Human-readable name, e.g. "Oak Valley Forest"
        total_units: Total number of extractable units, e.g. 10000 trees
        safe_threshold_ratio: Fraction of total_units that can be safely extracted
                              before damage accelerates sharply. Must be in (0.0, 1.0).
        unit_value: Revenue per unit extracted, in euros. e.g. 100.0 €/tree.

    Derived:
        safe_threshold_units: Absolute number of units at the safe threshold.
    """

    name: str
    total_units: int
    safe_threshold_ratio: float
    unit_value: float

    @property
    def safe_threshold_units(self) -> int:
        """Absolute number of units that can be extracted at the safe threshold."""
        return int(self.total_units * self.safe_threshold_ratio)


@dataclass
class Agent:
    """
    An entity that depends on the resource and suffers when it is depleted.

    Monetary cost at depletion level d:
        cost = damage_function(d) * dependency_weight * monetary_rate

    Attributes:
        name: Human-readable name, e.g. "Animal Populations"
        dependency_weight: This agent's share of total ecosystem damage. Must be in (0, 1].
                           All agents in an ecosystem must sum to 1.0.
        damage_function: Callable (depletion_ratio: float) -> damage_ratio: float
        monetary_rate: Total monetary cost (€) at maximum damage (damage_ratio = 1.0).
        description: Short description of what damage means for this agent.
    """

    name: str
    dependency_weight: float
    damage_function: DamageFunc
    monetary_rate: float
    description: str


@dataclass
class Ecosystem:
    """
    A resource bound to a list of agents.

    Attributes:
        name: Human-readable name, e.g. "Oak Valley Forest Ecosystem"
        resource: The shared natural asset.
        agents: List of Agent instances dependent on the resource.
                Typed as list (not List[Agent]) for Cython compatibility.
    """

    name: str
    resource: Resource
    agents: list  # List[Agent] — typed as list for Cython compat


@dataclass
class SimulationStep:
    """
    The state of the simulation at one point in time (after extracting N units total).

    Attributes:
        step: Which extraction step this is (1-indexed).
        units_extracted: Cumulative units extracted so far (equals step).
        depletion_ratio: units_extracted / total_units.
        agent_damages: Damage ratio per agent at this depletion level (0.0 to 1.0).
        agent_costs: Total € cost per agent at this depletion level.
        marginal_cost: Externality cost of THIS unit only (total cost minus previous total).
        cumulative_cost: Total externality cost at this depletion level.
        private_revenue: Cumulative revenue from extraction so far.
        ecosystem_health: Weighted average health index (0.0 = collapsed, 1.0 = pristine).
    """

    step: int
    units_extracted: int
    depletion_ratio: float
    agent_damages: list   # List[float]
    agent_costs: list     # List[float]
    marginal_cost: float
    cumulative_cost: float
    private_revenue: float
    ecosystem_health: float


@dataclass
class SimulationResult:
    """
    The complete output of a simulation run.

    Attributes:
        ecosystem: The ecosystem that was simulated.
        steps: All SimulationStep records produced during the run.
        total_units_extracted: How many units were extracted.
        total_private_revenue: Sum of all unit revenues.
        total_externality_cost: Total externality cost at the final depletion level.
        net_social_cost: total_private_revenue - total_externality_cost.
                         Positive = society gained; negative = society lost.
        final_ecosystem_health: Ecosystem health at the end of the simulation.
    """

    ecosystem: Ecosystem
    steps: list               # List[SimulationStep]
    total_units_extracted: int
    total_private_revenue: float
    total_externality_cost: float
    net_social_cost: float
    final_ecosystem_health: float
