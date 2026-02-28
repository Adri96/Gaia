"""
Gaia v0.3 — Core data models.

All models are typed dataclasses with primitive fields.
No inheritance, no dynamic attributes, no **kwargs.
All models are Cython-compatible.

v0.2 additions: RestorationCost, RestorationStep, RestorationResult
v0.3 additions: Agent trophic fields, InteractionEdge, Ecosystem interactions,
                SimulationStep cascade fields
"""

from dataclasses import dataclass, field
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

    # v0.3: Trophic cascade fields (defaults preserve v0.1/v0.2 behavior)
    trophic_level: int = -1             # -1=abiotic, 0=producer, 1-3=consumers
    is_keystone: bool = False           # if True, collapse amplifies outgoing edges
    keystone_threshold: float = 0.3     # health below this triggers keystone cascade


@dataclass
class InteractionEdge:
    """
    A directed dependency between two agents.

    "When agent source is damaged, agent target suffers additional damage."

    Attributes:
        source: Name of the agent whose damage propagates.
        target: Name of the agent that receives the propagated damage.
        strength: How much of source's damage transfers to target (0.0 to 1.0).
        interaction_type: Category of interaction — one of:
            "dependency", "trophic", "keystone", "competition".
        description: Human-readable explanation of the interaction.
    """

    source: str
    target: str
    strength: float
    interaction_type: str
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

    # v0.3: Agent interaction edges (empty list preserves v0.1/v0.2 behavior)
    interactions: list = field(default_factory=list)  # List[InteractionEdge]


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
    agent_damages: list   # List[float] — effective (post-propagation) damage ratios
    agent_costs: list     # List[float]
    marginal_cost: float
    cumulative_cost: float
    private_revenue: float
    ecosystem_health: float

    # v0.3: Cascade breakdown fields (empty lists preserve v0.1/v0.2 behavior)
    agent_direct_damages: list = field(default_factory=list)    # pre-propagation damage ratios
    agent_cascade_damages: list = field(default_factory=list)   # additional damage from interactions
    keystone_triggered: list = field(default_factory=list)      # agent names whose keystone threshold crossed


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


# ── v0.2: Restoration models ───────────────────────────────────────────────────


@dataclass
class RestorationCost:
    """
    The direct costs of restoring one unit of resource.

    These are the private costs borne by whoever is doing the restoration —
    distinct from the ecosystem service value that restoration recovers
    (which is a social benefit).

    Cost formula per unit restored:
        total_cost_per_unit = planting_cost_per_unit
                            + (annual_maintenance_per_unit * maintenance_years)

    Attributes:
        planting_cost_per_unit: One-time cost to plant/establish one unit (€/unit).
            For forests: nursery + labour + planting. For Posidonia: transplanting.
            [PLACEHOLDER — pending calibration per ecosystem]
        annual_maintenance_per_unit: Recurring cost per unit per year during
            the maturation period (€/unit/year). Includes watering, protection,
            monitoring, replanting of failures.
            [PLACEHOLDER — pending calibration per ecosystem]
        maintenance_years: How many years of active maintenance are required
            before the restored unit can be considered self-sustaining.
            For forests: ~10 years. For Posidonia: ~20+ years.
            [PLACEHOLDER — pending calibration per ecosystem]
    """

    planting_cost_per_unit: float
    annual_maintenance_per_unit: float
    maintenance_years: int

    @property
    def total_cost_per_unit(self) -> float:
        """Total cost to restore and maintain one unit through maturation."""
        return self.planting_cost_per_unit + (
            self.annual_maintenance_per_unit * self.maintenance_years
        )


@dataclass
class RestorationStep:
    """
    The state of the restoration simulation at one point in time
    (after replanting N units total).

    Mirrors SimulationStep but for the restoration direction.

    Attributes:
        step: Which restoration step this is (1-indexed).
        units_restored: Cumulative units replanted so far (equals step).
        recovery_ratio: units_restored / total_units_destroyed.
            Represents the fraction of the damage that has been addressed.
        agent_recoveries: Recovered service ratio per agent (0.0 to 1.0).
        agent_service_values: Recovered € service value per agent.
        marginal_service_value: Value recovered by THIS unit only.
        cumulative_service_value: Total recovered service value at this point.
        restoration_cost_so_far: Total restoration cost incurred so far (€).
        ecosystem_health: Weighted health recovery index (0.0 to 1.0).
    """

    step: int
    units_restored: int
    recovery_ratio: float
    agent_recoveries: list    # List[float]
    agent_service_values: list  # List[float]
    marginal_service_value: float
    cumulative_service_value: float
    restoration_cost_so_far: float
    ecosystem_health: float


@dataclass
class RestorationResult:
    """
    The complete output of a restoration simulation run.

    Attributes:
        ecosystem: The ecosystem being restored.
        restoration_cost: The RestorationCost parameters used.
        steps: All RestorationStep records.
        total_units_restored: How many units were replanted.
        total_restoration_cost: Total direct cost of restoration (€).
        total_recovered_value: Total ecosystem service value recovered (€).
        net_restoration_value: total_recovered_value - total_restoration_cost.
            Positive = restoration generates net social value.
        prevention_advantage: How many times cheaper prevention is vs.
            destruction + restoration. Computed as:
            (foregone_revenue + total_restoration_cost) / foregone_revenue
            A ratio > 1.0 means restoration costs more than prevention.
            [NOTE: this is a simplified ratio without time-discounting.
             Full NPV analysis is a v0.5 feature.]
        final_ecosystem_health: Ecosystem health after all restoration.
    """

    ecosystem: Ecosystem
    restoration_cost: RestorationCost
    steps: list                  # List[RestorationStep]
    total_units_restored: int
    total_restoration_cost: float
    total_recovered_value: float
    net_restoration_value: float
    prevention_advantage: float
    final_ecosystem_health: float
