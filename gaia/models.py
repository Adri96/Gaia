"""
Gaia v0.7 — Core data models.

All models are typed dataclasses with primitive fields.
No inheritance, no dynamic attributes, no **kwargs.
All models are Cython-compatible.

v0.2 additions: RestorationCost, RestorationStep, RestorationResult
v0.3 additions: Agent trophic fields, InteractionEdge, Ecosystem interactions,
                SimulationStep cascade fields
v0.4 additions: SuccessionCurve, CarbonProfile, ResilienceConfig, MaturationStep,
                RestorationConfig; Resource + carbon/resilience; Agent + succession;
                SimulationStep + resilience fields; RestorationResult + maturation
v0.5 additions: SubstrateProfile, SubstrateState; Resource + substrate;
                SimulationStep + substrate fields; RestorationResult + substrate ceiling
v0.6 additions: DiscountConfig, ExtractionNPV, RestorationNPV, CarbonBreakeven,
                PreventionAdvantageV06; Resource + discount;
                SimulationStep + discount fields; RestorationResult + NPV
v0.7 additions: ScarcityFunction, AnchorPoint, PricingConfig, PriceResult;
                Ecosystem + pricing; SimulationStep + price fields
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Union

# Type alias for damage functions: depletion_ratio -> damage_ratio
DamageFunc = Callable[[float], float]


# ── v0.5: Physical Substrate models ───────────────────────────────────────────


@dataclass
class SubstrateProfile:
    """Physical substrate properties that constrain carrying capacity.

    Each property is a measurable geophysical quantity with units.
    The substrate profile is ecosystem-specific — terrestrial and marine
    profiles use different properties.

    Attributes:
        substrate_type: Type of substrate — "terrestrial_soil", "marine_sediment",
            or "marine_matte".
        soil_depth_cm: Terrestrial: productive soil depth in cm.
        water_availability_mm_yr: Terrestrial: effective annual precipitation in mm/yr.
        water_clarity_kd: Marine: diffuse attenuation coefficient in m^-1.
        sediment_stability: Marine: 0.0 (mobile) to 1.0 (rock/consolidated matte).
        erosion_rate_unprotected: Erosion rate when vegetation removed (t/ha/yr or mm/yr).
        erosion_rate_protected: Erosion rate under intact vegetation (t/ha/yr or mm/yr).
        formation_rate: New substrate formation rate (t/ha/yr or mm/yr).
        capacity_function: How substrate maps to carrying capacity fraction —
            "linear", "threshold", or "logistic".
        erosion_alpha: Exponent for nonlinear erosion interpolation.
            2.0 for terrestrial (gradual transition), 3.0 for marine (steep transition).
        critical_minimum: For threshold capacity function — substrate value below which
            K drops to near-zero (e.g. 8.0 cm for holm oak on limestone).
        residual_fraction: For threshold capacity function — fraction of K remaining
            below critical minimum (e.g. 0.05 for minimal pioneer colonization).
        confidence: Data confidence level — "low", "low-medium", "medium",
            "medium-high", or "high".
    """

    substrate_type: str
    soil_depth_cm: Optional[float] = None
    water_availability_mm_yr: Optional[float] = None
    water_clarity_kd: Optional[float] = None
    sediment_stability: Optional[float] = None
    erosion_rate_unprotected: float = 0.0
    erosion_rate_protected: float = 0.0
    formation_rate: float = 0.0
    capacity_function: str = "linear"
    erosion_alpha: float = 2.0
    critical_minimum: float = 0.0
    residual_fraction: float = 0.05
    confidence: str = "medium"


@dataclass
class SubstrateState:
    """Current state of the physical substrate.

    Tracks how substrate has degraded from its pristine condition
    and computes the derived carrying capacity fraction.

    Created and managed by the simulation engine — not stored on Resource.
    Resource holds only the immutable SubstrateProfile.

    Attributes:
        profile: The SubstrateProfile defining physical properties and rates.
        current_soil_depth_cm: Current soil depth (terrestrial).
        current_water_clarity_kd: Current water clarity (marine).
        current_sediment_stability: Current sediment stability (marine).
        pristine_soil_depth_cm: Original soil depth before any degradation.
        pristine_water_clarity_kd: Original water clarity.
        pristine_sediment_stability: Original sediment stability.
        capacity_fraction: Derived carrying capacity as fraction of pristine (0.0 to 1.0).
        years_to_recover: Estimated years for substrate to return to pristine.
    """

    profile: SubstrateProfile
    current_soil_depth_cm: Optional[float] = None
    current_water_clarity_kd: Optional[float] = None
    current_sediment_stability: Optional[float] = None
    pristine_soil_depth_cm: Optional[float] = None
    pristine_water_clarity_kd: Optional[float] = None
    pristine_sediment_stability: Optional[float] = None
    capacity_fraction: float = 1.0
    years_to_recover: float = 0.0


# ── v0.6: Discount & NPV models ────────────────────────────────────────────────


@dataclass(frozen=True)
class DiscountConfig:
    """Configuration for time-value-of-money calculations.

    The discount rate follows the Ramsey formula: r = delta + eta * g.
    All three Ramsey components are stored for transparency,
    though only the resulting rate(s) are used in calculations.

    Attributes:
        delta: Pure rate of time preference (0.5% Drupp et al. median).
        eta: Elasticity of marginal utility of consumption (1.35 Drupp et al. mean).
        g: Per-capita consumption growth rate (1.3%).
        rate_schedule: Effective discount rate — either a single float (constant)
            or a list of (year_threshold, rate) tuples (declining schedule).
            If None, computed from Ramsey formula on init.
        scarcity_rate: Annual relative price change for ecosystem services (2%/yr).
        horizon_years: NPV analysis horizon in years (default 100).
        carbon_price_current: Current carbon price in euros/tonne CO2.
        carbon_price_growth: Annual real growth rate of carbon price.
    """

    delta: float = 0.005
    eta: float = 1.35
    g: float = 0.013
    rate_schedule: Union[float, list] = None  # type: ignore[assignment]
    scarcity_rate: float = 0.02
    horizon_years: int = 100
    carbon_price_current: float = 80.0
    carbon_price_growth: float = 0.03

    def __post_init__(self) -> None:
        if self.rate_schedule is None:
            object.__setattr__(self, 'rate_schedule', self.delta + self.eta * self.g)

    def rate_at_year(self, year: int) -> float:
        """Return the discount rate applicable at a given year."""
        if isinstance(self.rate_schedule, (int, float)):
            return float(self.rate_schedule)
        # Declining schedule: list of (threshold, rate) tuples
        for threshold, rate in reversed(self.rate_schedule):
            if year >= threshold:
                return rate
        return self.rate_schedule[0][1]

    def discount_factor(self, year: int) -> float:
        """Cumulative discount factor for a given year.

        For constant rates: 1 / (1 + r)^t
        For declining schedules: product of annual factors.
        """
        if isinstance(self.rate_schedule, (int, float)):
            return 1.0 / (1.0 + float(self.rate_schedule)) ** year
        # For declining schedules, compound year by year
        factor: float = 1.0
        for t in range(1, year + 1):
            factor /= (1.0 + self.rate_at_year(t))
        return factor

    def carbon_price_at_year(self, year: int) -> float:
        """Carbon price in year t, growing at carbon_price_growth rate."""
        return self.carbon_price_current * (1.0 + self.carbon_price_growth) ** year

    def scarcity_factor(self, year: int) -> float:
        """Scarcity uplift multiplier for ecosystem services at year t."""
        return (1.0 + self.scarcity_rate) ** year


@dataclass(frozen=True)
class ExtractionNPV:
    """NPV of extraction externalities.

    Attributes:
        direct: NPV of direct ecosystem service loss.
        carbon_release: NPV of carbon released at extraction.
        carbon_foregone: NPV of future absorption capacity foregone.
        substrate_damage: NPV of permanent substrate capacity loss.
        total: Sum of all components.
        horizon: Analysis horizon in years.
    """

    direct: float
    carbon_release: float
    carbon_foregone: float
    substrate_damage: float
    total: float
    horizon: int


@dataclass(frozen=True)
class RestorationNPV:
    """NPV of restoration as an investment.

    Attributes:
        cost: NPV of total restoration expenditure.
        service_benefits: NPV of recovered ecosystem services.
        carbon_benefits: NPV of carbon absorption at rising prices.
        total_benefits: service_benefits + carbon_benefits.
        net_present_value: total_benefits - cost.
        roi: total_benefits / cost.
        carbon_payback_years: Undiscounted years to recapture released carbon.
        horizon: Analysis horizon in years.
    """

    cost: float
    service_benefits: float
    carbon_benefits: float
    total_benefits: float
    net_present_value: float
    roi: float
    carbon_payback_years: Optional[int]
    horizon: int


@dataclass(frozen=True)
class CarbonBreakeven:
    """Carbon credit breakeven analysis.

    At breakeven_price, restoration NPV = 0 from carbon credits alone.

    Attributes:
        breakeven_price: Euro/tonne CO2 where restoration NPV = 0.
        current_price: Current EU ETS price.
        gap_to_current: breakeven_price - current_price.
        profitable_at_current: True if breakeven <= current price.
        projected_breakeven_year: Year when rising carbon prices reach breakeven.
        npv_cost: NPV of restoration costs.
        npv_absorption_per_euro: Discounted absorption per euro/t price.
    """

    breakeven_price: float
    current_price: float
    gap_to_current: float
    profitable_at_current: bool
    projected_breakeven_year: Optional[int]
    npv_cost: float
    npv_absorption_per_euro: float


@dataclass(frozen=True)
class PreventionAdvantageV06:
    """Enhanced prevention advantage with full NPV accounting.

    Attributes:
        pa_simple: v0.2-style undiscounted PA.
        pa_with_carbon: Including carbon externality NPV.
        pa_with_substrate: Including permanent substrate loss NPV.
        pa_full: All-inclusive NPV-based PA.
        npv_prevention_cost: Foregone extraction revenue.
        npv_restoration_total: Full cost of restore-after-extract.
    """

    pa_simple: float
    pa_with_carbon: float
    pa_with_substrate: float
    pa_full: float
    npv_prevention_cost: float
    npv_restoration_total: float


# ── v0.7: Endogenous Pricing models ───────────────────────────────────────────


@dataclass
class ScarcityFunction:
    """Maps agent health to a scarcity price multiplier.

    Two variants matching the substrate capacity function pattern:
    - smooth: scarcity = min(max_multiplier, 1.0 / health^alpha)
    - threshold: 1.0 above threshold, quadratic rise below

    Attributes:
        function_type: "smooth" or "threshold".
        alpha: Elasticity parameter (smooth), or pre-threshold multiplier.
        threshold: Health threshold below which price rises (threshold type).
        max_multiplier: Cap to prevent infinity (default 50.0).
        description: Human-readable description.
    """

    function_type: str
    alpha: float = 1.0
    threshold: float = 0.3
    max_multiplier: float = 50.0
    description: str = ""


@dataclass
class AnchorPoint:
    """External market price grounding the relative price system in absolute euros.

    Attributes:
        agent_name: Name of the agent this anchors.
        anchor_value: Euro-value at pristine health (annual flow value).
        source: Data source description.
        confidence: "high", "medium", or "low".
        description: Calculation explanation.
    """

    agent_name: str
    anchor_value: float
    source: str
    confidence: str
    description: str


@dataclass
class PricingConfig:
    """Top-level configuration for endogenous pricing.

    Attributes:
        anchors: At least one AnchorPoint required.
        scarcity_functions: Per-agent scarcity functions, keyed by agent name.
        default_scarcity: Fallback for agents without explicit scarcity function.
        convergence_tolerance: For iterative solver (default 1e-6).
        max_iterations: Cap on iterative solve (default 100).
        fallback_to_static: If True, use monetary_rate when solve fails.
    """

    anchors: list              # List[AnchorPoint]
    scarcity_functions: dict   # Dict[str, ScarcityFunction]
    default_scarcity: ScarcityFunction = field(
        default_factory=lambda: ScarcityFunction("smooth", 1.0, 0.3, 50.0)
    )
    convergence_tolerance: float = 1e-6
    max_iterations: int = 100
    fallback_to_static: bool = True


@dataclass
class PriceResult:
    """Output of the price solver at a given ecosystem state.

    Attributes:
        prices: Computed price per agent (Dict[str, float]).
        scarcity_multipliers: scarcity(health) per agent.
        demand_multipliers: Network centrality contribution per agent.
        anchor_contributions: How much of price comes from anchor vs network.
        spectral_radius: Spectral radius of S*W — must be < 1.0 for convergence.
        converged: Whether the solve converged.
        iterations: Number of iterations (if iterative solver used).
    """

    prices: dict              # Dict[str, float]
    scarcity_multipliers: dict
    demand_multipliers: dict
    anchor_contributions: dict
    spectral_radius: float
    converged: bool
    iterations: int = 0


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

    # v0.5: Physical substrate (None → fixed K, backward compatible)
    substrate: Optional[SubstrateProfile] = None

    # v0.6: Discount configuration (None → no NPV, backward compatible)
    discount: Optional[DiscountConfig] = None

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

    # v0.7: Endogenous pricing (None → use static monetary_rate, backward compatible)
    pricing: Optional[PricingConfig] = None


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

    # v0.5: Substrate degradation fields (defaults preserve v0.4 behavior)
    substrate_erosion: float = 0.0            # Erosion applied this step (mm or equivalent)
    effective_k: int = 0                      # Current effective carrying capacity
    k_fraction: float = 1.0                   # effective_k / total_units

    # v0.6: Discount fields (defaults preserve v0.5 behavior)
    discount_factor_at_step: float = 1.0      # Discount factor at this step's time
    npv_externality: float = 0.0              # Externality * discount_factor
    carbon_price_used: float = 0.0            # Carbon price at this step's year

    # v0.7: Endogenous pricing fields (defaults preserve v0.6 behavior)
    agent_prices: list = field(default_factory=list)  # Per-agent dynamic price
    price_result: Optional[PriceResult] = None        # Full price decomposition


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

    # v0.6: NPV of extraction externalities (None → no NPV, backward compatible)
    extraction_npv: Optional[ExtractionNPV] = None


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
             Full NPV analysis is a v0.6 feature.]
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

    # v0.5: Substrate-constrained restoration fields (defaults preserve v0.4 behavior)
    substrate_ceiling: float = 1.0              # Max recoverable fraction (K_current/K_pristine)
    substrate_recovery_years: float = 0.0       # Years for substrate to return to pristine
    substrate_recovery_cost: float = 0.0        # Cost of substrate stabilization
    prevention_advantage_with_substrate: float = 0.0  # PA including permanent capacity loss

    # v0.6: NPV and carbon breakeven (defaults preserve v0.5 behavior)
    extraction_npv: Optional[ExtractionNPV] = None
    restoration_npv: Optional[RestorationNPV] = None
    carbon_breakeven: Optional[CarbonBreakeven] = None
    prevention_advantage_v06: Optional[PreventionAdvantageV06] = None
