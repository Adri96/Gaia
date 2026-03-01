"""
Gaia v0.4 — Core data models.

All models are typed dataclasses with primitive fields.
No inheritance, no dynamic attributes, no **kwargs.
All models are Cython-compatible.

v0.2 additions: RestorationCost, RestorationStep, RestorationResult
v0.3 additions: Agent trophic fields, InteractionEdge, Ecosystem interactions,
                SimulationStep cascade fields
v0.4 additions: SuccessionCurve, CarbonProfile, ResilienceConfig, MaturationStep,
                RestorationConfig; Resource + carbon/resilience; Agent + succession;
                SimulationStep + resilience fields; RestorationResult + maturation
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional

# Type alias for damage functions: depletion_ratio -> damage_ratio
DamageFunc = Callable[[float], float]


# ── v0.4: Succession, Carbon & Resilience models ──────────────────────────────


@dataclass
class SuccessionCurve:
    """Three-phase succession maturation curve.

    Maps years since restoration to service capacity (0.0 to 1.0).
    Encodes the ecological reality that restoration follows
    pioneer → intermediate → climax phases (Foundation F8).

    Attributes:
        pioneer_end_year: When pioneer phase ends (Y₁).
        intermediate_end_year: When intermediate phase ends (Y₂).
        climax_approach_year: When services reach ~95% of climax (Y₃).
        pioneer_service: Max service fraction during pioneer (e.g. 0.05).
        intermediate_service: Max service fraction during intermediate (e.g. 0.40).
        maturation_delay: Years of zero service at the start (dead zone).
    """

    pioneer_end_year: float
    intermediate_end_year: float
    climax_approach_year: float
    pioneer_service: float
    intermediate_service: float
    maturation_delay: float


@dataclass
class CarbonProfile:
    """Carbon accounting parameters for a resource unit.

    Attributes:
        stored_carbon_tonnes: Tonnes CO₂ stored per unit (tree or hectare).
        annual_absorption_tonnes: Tonnes CO₂ absorbed per unit per year at climax.
        soil_carbon_tonnes: Tonnes CO₂ stored in soil beneath each unit.
        soil_release_fraction: Fraction of soil carbon released on extraction (0.0–1.0).
        carbon_price_per_tonne: € per tonne CO₂ (default: EU ETS price).
    """

    stored_carbon_tonnes: float
    annual_absorption_tonnes: float
    soil_carbon_tonnes: float
    soil_release_fraction: float
    carbon_price_per_tonne: float


@dataclass
class ResilienceConfig:
    """Resilience zone configuration for uncertainty flagging.

    Three zones around the safe threshold acknowledge that we don't
    know exactly where the tipping point is (Foundation F7).

    Attributes:
        warning_zone_width: Fraction of total resource — yellow zone starts
            at threshold + width.
        confidence_green: Model confidence in the green zone (0.0–1.0).
        confidence_yellow: Model confidence in the yellow zone (0.0–1.0).
        confidence_red: Model confidence in the red zone (0.0–1.0).
        irreversibility_flag_ratio: Depletion ratio above which
            irreversibility warning is triggered.
    """

    warning_zone_width: float = 0.10
    confidence_green: float = 0.90
    confidence_yellow: float = 0.60
    confidence_red: float = 0.30
    irreversibility_flag_ratio: float = 0.50


@dataclass
class MaturationStep:
    """One year of the maturation timeline.

    Produced by the maturation pass of time-aware restoration.

    Attributes:
        year: Year since restoration began.
        succession_phase: "delay", "pioneer", "intermediate", or "climax".
        service_fraction: 0.0 to 1.0 — fraction of max recovered services delivered.
        annual_service_value: € — actual service value delivered this year.
        cumulative_service_value: € — total services from year 0 to this year.
        annual_carbon_absorbed: Tonnes CO₂ absorbed this year.
        cumulative_carbon_absorbed: Tonnes CO₂ total absorbed so far.
    """

    year: int
    succession_phase: str
    service_fraction: float
    annual_service_value: float
    cumulative_service_value: float
    annual_carbon_absorbed: float
    cumulative_carbon_absorbed: float


@dataclass
class RestorationConfig:
    """Configuration for time-aware restoration simulation.

    Attributes:
        units_to_restore: Number of units to replant.
        planting_schedule: "immediate" or "phased".
        planting_years: If phased, how many years to spread planting over.
        time_horizon_years: How many years to simulate post-restoration.
        succession_curve: Ecosystem-level default succession curve.
    """

    units_to_restore: int
    planting_schedule: str
    planting_years: int
    time_horizon_years: int
    succession_curve: SuccessionCurve


# ── Core models ────────────────────────────────────────────────────────────────


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
        carbon_profile: Optional carbon accounting parameters (v0.4).
        resilience: Optional resilience zone configuration (v0.4).

    Derived:
        safe_threshold_units: Absolute number of units at the safe threshold.
    """

    name: str
    total_units: int
    safe_threshold_ratio: float
    unit_value: float

    # v0.4: Carbon and resilience (None → no carbon/resilience accounting)
    carbon_profile: Optional[CarbonProfile] = None
    resilience: Optional[ResilienceConfig] = None

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

    # v0.4: Agent-specific succession curve (None → use ecosystem default)
    succession_curve: Optional[SuccessionCurve] = None


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

    # v0.4: Resilience zone fields (defaults preserve v0.3 behavior)
    resilience_zone: str = "green"            # "green", "yellow", or "red"
    model_confidence: float = 1.0             # 0.0–1.0
    irreversibility_warning: bool = False     # True if depletion > irreversibility_flag_ratio


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
        maturation_timeline: Year-by-year service recovery (v0.4, empty if no succession).
        years_to_pioneer: Years until services first become non-zero (v0.4).
        years_to_50pct: Years until 50% of recoverable services are delivered (v0.4).
        years_to_90pct: Years until 90% of recoverable services are delivered (v0.4).
        total_maturation_gap: € accumulated externality during maturation (v0.4).
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

    # v0.4: Maturation timeline fields (defaults preserve v0.3 behavior)
    maturation_timeline: list = field(default_factory=list)  # List[MaturationStep]
    years_to_pioneer: float = 0.0
    years_to_50pct: float = 0.0
    years_to_90pct: float = 0.0
    total_maturation_gap: float = 0.0
