"""
Gaia v0.1 — Costa Brava Posidonia Meadow destruction case.

Marine ecosystem with 11 agents spanning the full web of biological and
physical dependencies: from the Posidonia meadow itself as foundation species,
through coralligenous reefs, fish nurseries, and apex megafauna, to the
coastal protection and tourism economy of the Costa Brava.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: MARINE EXTERNALITY ECONOMICS — TIME-FLOW ASYMMETRY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In the forest case, private revenue is ongoing (per-tree timber income) and
externalities are one-time costs. Here the economics are INVERTED:

    Private revenue:    ONE-TIME gain from coastal development, marina
                        construction, or trawling permits that destroy
                        Posidonia (modeled as €2,500/ha destroyed).

    Externality costs:  ANNUAL RECURRING losses — every year the meadow
                        is gone, the ecosystem services are absent. The
                        report shows the annual cost rate; the true social
                        cost compounds every year the damage persists.

Payback arithmetic (at default parameters, full destruction):
    One-time revenue:   5,000 ha × €2,500 = €12,500,000
    Annual externality: ~€5,830,000/yr at full damage
    Payback period:     ~2.1 years — after that, society loses €5.8M/yr
                        every year, forever (Posidonia growth: 1-6 cm/year).

Over 10 years: €58.3M lost vs €12.5M gained (ratio: 4.7× against destruction).
Over 30 years: €174.9M lost vs €12.5M gained (ratio: 14× against destruction).

The simulation reports ANNUAL externality costs. A note in the output flags
this explicitly. NPV analysis over time horizons is a v0.5 feature.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scientific context:
    Posidonia oceanica is one of the most biodiverse and carbon-rich ecosystems
    on Earth. It absorbs 15× more CO₂ per hectare than the Amazon rainforest and
    stores carbon in its sediment matte for millennia. Growth rate: 1-6 cm/year
    horizontal — any significant destruction is irreversible on human timescales.

    34% of Mediterranean Posidonia has been lost in the last 50 years. The Costa
    Brava is already under pressure from tourism infrastructure, boat anchoring,
    and residual trawling. The 20% safe threshold is lower than the forest (25%)
    because recovery is orders of magnitude slower and the ecosystem is already
    stressed.

    The Medes Islands MPA is the proof-of-concept: protected since 1983, fish
    biomass is 80× higher inside the reserve than outside. The science works —
    protection produces measurable, quantifiable recovery.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

Monetary rates are back-calculated from user-specified max monetary impacts:
    rate = max_monetary_impact / dependency_weight
so that effective_max_per_agent = weight × rate = max_monetary_impact exactly.

    | Parameter                       | Max Impact | Weight | Rate (€)   | Source       | Confidence |
    |---------------------------------|------------|--------|------------|--------------|------------|
    | total_units                     | –          | –      | –          | User spec    | Low        |
    | safe_threshold_ratio            | –          | –      | 0.20       | User spec    | Medium     |
    | unit_value (revenue/ha)         | –          | –      | 2,500      | User spec    | Low        |
    | Posidonia Meadow                | €800,000   | 0.10   | 8,000,000  | User spec    | Low        |
    | Coralligenous & Red Coral       | €600,000   | 0.10   | 6,000,000  | User spec    | Low        |
    | Epiphytes & Algae               | €250,000   | 0.07   | 3,571,000  | User spec    | Low        |
    | Marine Invertebrates            | €350,000   | 0.09   | 3,889,000  | User spec    | Low        |
    | Fish Populations                | €700,000   | 0.14   | 5,000,000  | User spec    | Low        |
    | Marine Megafauna                | €200,000   | 0.04   | 5,000,000  | User spec    | Low        |
    | Seabirds                        | €180,000   | 0.05   | 3,600,000  | User spec    | Low        |
    | Coastal Protection              | €900,000   | 0.13   | 6,923,000  | User spec    | Low        |
    | Water Quality                   | €650,000   | 0.11   | 5,909,000  | User spec    | Low        |
    | Blue Carbon                     | €500,000   | 0.09   | 5,556,000  | User spec    | Low        |
    | Human Communities               | €700,000   | 0.08   | 8,750,000  | User spec    | Low        |
    | logistic steepness              | –          | –      | 12.0       | Placeholder  | Low        |
    | exponential base (carbon)       | –          | –      | 2.0        | Placeholder  | Low        |
    | dependency weight sum           | –          | 1.00   | –          | Verified ✓   | High       |

Total max externality (annual): sum(weight × rate)
    = 800k + 600k + 250k + 350k + 700k + 200k + 180k + 900k + 650k + 500k + 700k
    = €5,830,000/year [User spec ✓]

vs one-time revenue at full destruction: 5,000 ha × €2,500 = €12,500,000
Annual payback period: ~2.1 years [User spec ✓]

Calibration: rates ensure externality < revenue at 20% threshold (at annual scale):
    logistic_damage(0.20) ≈ 0.068 → 0.068 × €5,830,000 ≈ €396k/yr < €250k one-time
    NOTE: Even at threshold, 1.6 years of annual losses exceed the one-time gain.
    The crossover is near-immediate for marine ecosystems. [User spec ✓]

Dependency weights sum: 0.10+0.10+0.07+0.09+0.14+0.04+0.05+0.13+0.11+0.09+0.08 = 1.00 ✓

CLI usage:
    python -m gaia.cases.posidonia
    python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 1500
    python -m gaia.cases.posidonia --hectares 5000 --units 1500 --mode restore
    python -m gaia.cases.posidonia --units 1500 --format json
"""

import argparse
import sys
import warnings

from gaia.cli import (
    add_common_arguments,
    add_restoration_arguments,
    output_result,
    warn_unused_restoration_args,
)
from gaia.damage import exponential_damage, logistic_damage
from gaia.models import (
    Agent,
    AnchorPoint,
    CarbonProfile,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    PricingConfig,
    ResilienceConfig,
    RestorationCost,
    Resource,
    ScarcityFunction,
    SubstrateProfile,
    SuccessionCurve,
)
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

# v0.4: Posidonia succession curve
# Extremely slow — 1-6 cm/year horizontal growth, decades to re-establish.
# [PLACEHOLDER — pending calibration against Mediterranean seagrass studies]
_POSIDONIA_SUCCESSION = SuccessionCurve(
    pioneer_end_year=20.0,
    intermediate_end_year=50.0,
    climax_approach_year=120.0,
    pioneer_service=0.02,
    intermediate_service=0.25,
    maturation_delay=5.0,
)

# v0.4: Posidonia carbon profile (per hectare)
# Blue carbon — 15× Amazon CO₂ rate, millennia of stored matte carbon.
# [PLACEHOLDER — pending calibration against IPCC Blue Carbon data]
_POSIDONIA_CARBON = CarbonProfile(
    stored_carbon_tonnes=130.0,
    annual_absorption_tonnes=5.9,
    soil_carbon_tonnes=2600.0,
    soil_release_fraction=0.05,
    carbon_price_per_tonne=80.0,
)

# v0.4: Posidonia resilience configuration
# Widest warning zone — Posidonia is most fragile.
_POSIDONIA_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.15,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.40,
)

# v0.5: Posidonia substrate profile
# Marine matte — sediment stability and water clarity constrain capacity.
# Logistic capacity function: light-limited S-curve (Kd attenuation).
# [PLACEHOLDER — pending calibration against EMODnet and IFREMER data]
_POSIDONIA_SUBSTRATE = SubstrateProfile(
    substrate_type="marine_matte",
    water_clarity_kd=0.06,           # m⁻¹ — pristine light attenuation coefficient
    sediment_stability=0.85,         # 0-1 scale — pristine matte integrity
    erosion_rate_unprotected=5.0,    # arbitrary units/yr — matte degradation rate
    erosion_rate_protected=0.0,      # no erosion under intact meadow
    formation_rate=1.0,              # mm/yr — Posidonia matte accretion
    capacity_function="logistic",
    erosion_alpha=3.0,               # steeper nonlinearity for marine systems
    confidence="low-medium",
)

# v0.6: Posidonia discount configuration
# Declining rate schedule: near-term 2.3%, mid-term 1.8%, long-term 1.4%
_POSIDONIA_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[(0, 0.023), (31, 0.018), (101, 0.014)],
    scarcity_rate=0.03,  # Higher: Posidonia declining 34%+ since 1960s
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=200,  # Longer horizon for marine ecosystems
)

# v0.7: Posidonia pricing configuration
_POSIDONIA_PRICING = PricingConfig(
    anchors=[
        AnchorPoint(
            agent_name="Blue Carbon",
            anchor_value=136000.0,
            source="EU ETS €80/t × 1.7 t CO₂/ha/yr × 1,000 ha",
            confidence="high",
            description="Carbon: €80/t × 1,700 t CO₂/yr",
        ),
        AnchorPoint(
            agent_name="Human Communities",
            anchor_value=500000.0,
            source="Costa Brava tourism revenue attributable to coastal water quality per ~5 km",
            confidence="medium",
            description="Tourism: attributable water quality value for ~5 km coastline",
        ),
        AnchorPoint(
            agent_name="Fish Populations",
            anchor_value=75000.0,
            source="Artisanal catch value: ~15 boats × €5,000/yr/boat",
            confidence="medium",
            description="Fishing: 15 artisanal boats × €5,000/yr",
        ),
    ],
    scarcity_functions={
        "Posidonia Meadow": ScarcityFunction("smooth", alpha=2.0, max_multiplier=50.0, description="Foundation species; millennium-scale recovery"),
        "Coralligenous & Red Coral": ScarcityFunction("smooth", alpha=1.5, max_multiplier=50.0, description="Biogenic habitat; century-scale recovery"),
        "Epiphytes & Algae": ScarcityFunction("smooth", alpha=0.8, max_multiplier=50.0),
        "Marine Invertebrates": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Fish Populations": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Marine Megafauna": ScarcityFunction("smooth", alpha=0.5, max_multiplier=50.0),
        "Seabirds": ScarcityFunction("smooth", alpha=0.5, max_multiplier=50.0),
        "Coastal Protection": ScarcityFunction("threshold", threshold=0.3, max_multiplier=40.0, description="Beach nourishment cost replacement"),
        "Water Quality": ScarcityFunction("threshold", threshold=0.3, max_multiplier=30.0, description="Turbidity collapse threshold"),
        "Blue Carbon": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Human Communities": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)

# Shared steepness for all logistic agents.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS: float = 12.0

# Annual externality note appended to the report to flag the time-flow asymmetry.
_ANNUAL_NOTE: str = (
    "\n  ⚠  MARINE EXTERNALITY NOTE: these costs are ANNUAL — they recur every year\n"
    "     the damage persists. Posidonia recovers at 1-6 cm/year; damage is\n"
    "     effectively permanent on human timescales. The one-time private revenue\n"
    "     is offset within ~2 years of annual ecosystem service losses."
)


def build_posidonia_ecosystem(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    revenue_per_hectare: float = 2_500.0,
    with_pricing: bool = False,
) -> Ecosystem:
    """
    Build the Costa Brava Posidonia Meadow ecosystem with 11 agents.

    The ecosystem spans the full marine dependency web: seagrass foundation,
    coralligenous reefs, epiphytes, invertebrates, fish, megafauna, seabirds,
    coastal protection, water quality, blue carbon, and human coastal communities.

    Args:
        total_hectares: Total hectares of Posidonia meadow. Default 5,000 ha —
            a plausible estimate for a major Costa Brava coastal stretch.
            [User spec, needs GIS verification from EMODnet Posidonia maps]
        safe_threshold_ratio: Fraction destructible before cascading decline.
            Default 0.20 — lower than forest (0.25) because Posidonia growth
            is 1-6 cm/year and recovery takes decades. Mediterranean already
            lost 34% in 50 years. [User spec, Medium confidence]
        revenue_per_hectare: Private gain per hectare destroyed. Represents the
            economic value extracted by activities that destroy Posidonia:
            coastal development, marina construction, trawling permits.
            NOT the value of Posidonia itself. [User spec, Low confidence]

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    resource = Resource(
        name="Costa Brava Posidonia Meadow",
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
        carbon_profile=_POSIDONIA_CARBON,
        resilience=_POSIDONIA_RESILIENCE,
        substrate=_POSIDONIA_SUBSTRATE,
        discount=_POSIDONIA_DISCOUNT,
    )

    t = safe_threshold_ratio  # shorthand

    agents = [
        # ── Foundation species ──────────────────────────────────────────────
        Agent(
            name="Posidonia Meadow",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_000_000.0,
            description="Posidonia meadow integrity — self-reinforcing fragmentation and turbidity feedback loop",
            # v0.3: Producer, KEYSTONE foundation species
            trophic_level=0,
            is_keystone=True,
            keystone_threshold=0.3,
        ),
        # ── Biogenic habitat builders ───────────────────────────────────────
        Agent(
            name="Coralligenous & Red Coral",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=6_000_000.0,
            description="Coralligenous reefs and red coral — centuries-old biogenic habitat, irreplaceable on human timescales",
            # v0.3: Producer (biogenic)
            trophic_level=0,
        ),
        # ── Primary producers ───────────────────────────────────────────────
        Agent(
            name="Epiphytes & Algae",
            dependency_weight=0.07,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_571_000.0,
            description="Epiphytic algae and plant community — primary productivity, oxygen production, food web base",
            # v0.3: Producer
            trophic_level=0,
        ),
        # ── Invertebrates ───────────────────────────────────────────────────
        Agent(
            name="Marine Invertebrates",
            dependency_weight=0.09,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_889_000.0,
            description="Sponges, urchins, octopus, lobsters, shellfish — filter feeders, grazers, urchin barren risk",
            # v0.3: Primary consumer
            trophic_level=1,
        ),
        # ── Fish ────────────────────────────────────────────────────────────
        Agent(
            name="Fish Populations",
            dependency_weight=0.14,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_000_000.0,
            description="Fish nursery and feeding habitat — artisanal fisheries, grouper apex predator, Medes Islands model",
            # v0.3: Secondary consumer
            trophic_level=2,
        ),
        # ── Megafauna ───────────────────────────────────────────────────────
        Agent(
            name="Marine Megafauna",
            dependency_weight=0.04,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_000_000.0,
            description="Dolphins, sea turtles, cetaceans — apex indicators, ecotourism, extreme K-strategy vulnerability",
            # v0.3: Tertiary consumer — apex marine predator
            trophic_level=3,
        ),
        # ── Seabirds ────────────────────────────────────────────────────────
        Agent(
            name="Seabirds",
            dependency_weight=0.05,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_600_000.0,
            description="Seabirds and coastal birds — fish-dependent breeders, Audouin's gull, migratory corridor",
            # v0.3: Secondary consumer (fish-dependent)
            trophic_level=2,
        ),
        # ── Physical ecosystem services ─────────────────────────────────────
        Agent(
            name="Coastal Protection",
            dependency_weight=0.13,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=6_923_000.0,
            description="Wave attenuation, beach erosion prevention, sediment stabilization — Costa Brava beach economy",
            # v0.3: Abiotic service
            trophic_level=-1,
        ),
        Agent(
            name="Water Quality",
            dependency_weight=0.11,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_909_000.0,
            description="Nutrient filtration, pathogen reduction, bathing water standards — direct tourism dependency",
            # v0.3: Abiotic service
            trophic_level=-1,
        ),
        # ── Carbon ──────────────────────────────────────────────────────────
        Agent(
            name="Blue Carbon",
            dependency_weight=0.09,
            damage_function=exponential_damage(threshold=t, base=2.0),
            monetary_rate=5_556_000.0,
            description="Blue carbon — 15\u00d7 Amazon CO\u2082 rate, millennia of stored matte carbon, exponential release",
            # v0.3: Abiotic service
            trophic_level=-1,
        ),
        # ── Human systems ───────────────────────────────────────────────────
        Agent(
            name="Human Communities",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_750_000.0,
            description="Dive/beach tourism economy, artisanal fishing, coastal property — perception threshold sensitive",
            # v0.3: External beneficiary
            trophic_level=-1,
        ),
    ]

    # v0.3: Full marine trophic web with 16 interaction edges
    interactions = [
        # Posidonia keystone cascade — foundation collapse cascades everywhere
        InteractionEdge("Posidonia Meadow", "Coralligenous & Red Coral", 0.30, "keystone",
            "Posidonia loss \u2192 sedimentation \u2192 coralligenous suffocation"),
        InteractionEdge("Posidonia Meadow", "Epiphytes & Algae", 0.35, "keystone",
            "Substrate loss collapses epiphytic community"),
        InteractionEdge("Posidonia Meadow", "Coastal Protection", 0.40, "keystone",
            "Meadow loss directly removes wave attenuation and beach protection"),
        InteractionEdge("Posidonia Meadow", "Water Quality", 0.30, "dependency",
            "Lost filtration capacity \u2192 turbidity and eutrophication"),

        # Coralligenous provides habitat for invertebrates and fish
        InteractionEdge("Coralligenous & Red Coral", "Marine Invertebrates", 0.25, "dependency",
            "Reef habitat loss displaces invertebrate communities"),
        InteractionEdge("Coralligenous & Red Coral", "Fish Populations", 0.20, "dependency",
            "Reef nursery loss reduces fish recruitment"),

        # Epiphytes are base of the food web
        InteractionEdge("Epiphytes & Algae", "Marine Invertebrates", 0.20, "trophic",
            "Primary productivity loss reduces grazer food supply"),

        # Trophic chain: invertebrates → fish → megafauna/seabirds
        InteractionEdge("Marine Invertebrates", "Fish Populations", 0.25, "trophic",
            "Invertebrate decline reduces fish food supply"),
        InteractionEdge("Fish Populations", "Marine Megafauna", 0.35, "trophic",
            "Fish decline starves apex marine predators"),
        InteractionEdge("Fish Populations", "Seabirds", 0.30, "trophic",
            "Fish decline causes breeding failure in seabird colonies"),

        # Physical services linked to living biomass
        InteractionEdge("Posidonia Meadow", "Blue Carbon", 0.35, "dependency",
            "Meadow loss releases millennia of stored matte carbon"),

        # Invertebrate filtration supports water quality
        InteractionEdge("Marine Invertebrates", "Water Quality", 0.15, "dependency",
            "Filter feeder loss reduces water purification capacity"),

        # Water quality feeds back to coralligenous
        InteractionEdge("Water Quality", "Coralligenous & Red Coral", 0.15, "dependency",
            "Degraded water quality stresses sensitive coral formations"),

        # Human communities depend on multiple services
        InteractionEdge("Coastal Protection", "Human Communities", 0.25, "dependency",
            "Beach erosion destroys tourism infrastructure and economy"),
        InteractionEdge("Fish Populations", "Human Communities", 0.20, "dependency",
            "Fish decline collapses artisanal fishing economy"),
        InteractionEdge("Water Quality", "Human Communities", 0.15, "dependency",
            "Degraded water quality triggers beach closures and tourism loss"),
    ]

    return Ecosystem(
        name="Costa Brava Posidonia Meadow",
        resource=resource,
        agents=agents,
        interactions=interactions,
        pricing=_POSIDONIA_PRICING if with_pricing else None,
    )


def run_posidonia(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_destroyed: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
) -> str:
    """
    Run the Costa Brava Posidonia destruction simulation and return the report.

    Default hectares_destroyed=2,000 — 40% of the meadow, well past the 20%
    safe threshold, representative of a major coastal development project.

    NOTE: externality costs in the report are ANNUAL rates. The one-time
    private revenue must be compared against recurring annual losses to
    understand the true social cost over time.

    Args:
        total_hectares: Total hectares of Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_destroyed: Hectares of meadow destroyed (extracted).
        revenue_per_hectare: One-time private revenue per hectare destroyed.

    Returns:
        Formatted text report string with marine economics note appended.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    result = run_extraction(ecosystem, hectares_destroyed)
    return format_report(result) + _ANNUAL_NOTE


def run_posidonia_restoration(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_to_restore: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
    planting_cost_per_hectare: float = 50_000.0,
    annual_maintenance_per_hectare: float = 5_000.0,
    maintenance_years: int = 30,
    time_horizon_years: int = 0,
) -> str:
    """
    Run the Costa Brava Posidonia Meadow restoration simulation and return the report.

    v0.4: When time_horizon_years > 0, produces maturation timeline using
    the Posidonia succession curve (slowest of all ecosystems).

    Args:
        total_hectares: Total carrying capacity of the Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_to_restore: Hectares of meadow to actively restore.
        revenue_per_hectare: One-time private revenue per hectare.
        planting_cost_per_hectare: Specialist diving cost per hectare.
        annual_maintenance_per_hectare: Annual monitoring cost per hectare.
        maintenance_years: Years of active maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).

    Returns:
        Formatted text restoration report string with marine economics note.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    cost = RestorationCost(
        planting_cost_per_unit=planting_cost_per_hectare,
        annual_maintenance_per_unit=annual_maintenance_per_hectare,
        maintenance_years=maintenance_years,
    )
    recovery_fns = [
        logistic_recovery(threshold=safe_threshold_ratio)
        for _ in ecosystem.agents
    ]
    result = run_restoration(
        ecosystem, hectares_to_restore, cost, recovery_fns,
        succession_curve=_POSIDONIA_SUCCESSION if time_horizon_years > 0 else None,
        time_horizon_years=time_horizon_years,
    )
    return format_restoration_report(result) + _ANNUAL_NOTE


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.8.1 — Costa Brava Posidonia Meadow externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (20% = 1,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 1000\n\n"
            "  # Extraction — past threshold (40% = 2,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 2000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --units 2000 --mode restore\n\n"
            "  # JSON output:\n"
            "  python -m gaia.cases.posidonia --units 2000 --format json\n"
        ),
    )
    parser.add_argument(
        "--hectares",
        type=int,
        default=5_000,
        metavar="N",
        help="Total hectares of Posidonia meadow (default: 5000)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        metavar="RATIO",
        help="Safe destruction threshold ratio, 0.0 < threshold < 1.0 (default: 0.20)",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=2_000,
        metavar="N",
        help="Hectares to destroy or restore (default: 2000)",
    )
    # Deprecated alias for --units
    parser.add_argument(
        "--destroy", type=int, default=None, metavar="N",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--unit-value",
        type=float,
        default=2_500.0,
        metavar="EUROS",
        help="One-time revenue per hectare destroyed in euros (default: 2500.0)",
    )
    # Deprecated alias for --unit-value
    parser.add_argument(
        "--revenue", type=float, default=None, metavar="EUROS",
        help=argparse.SUPPRESS,
    )
    add_common_arguments(parser)
    add_restoration_arguments(
        parser,
        planting_cost_default=50_000.0,
        maintenance_cost_default=5_000.0,
        maintenance_years_default=30,
    )
    args = parser.parse_args(argv)
    # Resolve deprecated aliases
    if args.destroy is not None:
        warnings.warn(
            "--destroy is deprecated, use --units instead",
            DeprecationWarning,
            stacklevel=2,
        )
        args.units = args.destroy
    if args.revenue is not None:
        warnings.warn(
            "--revenue is deprecated, use --unit-value instead",
            DeprecationWarning,
            stacklevel=2,
        )
        args.unit_value = args.revenue
    return args


# Posidonia marine annual note for JSON output
_POSIDONIA_NOTES = [
    "Marine externality costs are ANNUAL — they recur every year the damage "
    "persists. Posidonia recovers at 1-6 cm/year; damage is effectively "
    "permanent on human timescales. The one-time private revenue is offset "
    "within ~2 years of annual ecosystem service losses."
]


def main(argv: list = None) -> None:
    args = _parse_args(argv)
    warn_unused_restoration_args(args)
    try:
        ecosystem = build_posidonia_ecosystem(
            total_hectares=args.hectares,
            safe_threshold_ratio=args.threshold,
            revenue_per_hectare=args.unit_value,
            with_pricing=args.with_pricing,
        )
        if args.mode == "restore":
            cost = RestorationCost(
                planting_cost_per_unit=args.planting_cost,
                annual_maintenance_per_unit=args.maintenance_cost,
                maintenance_years=args.maintenance_years,
            )
            recovery_fns = [
                logistic_recovery(threshold=args.threshold)
                for _ in ecosystem.agents
            ]
            result = run_restoration(
                ecosystem, args.units, cost, recovery_fns,
                succession_curve=(
                    _POSIDONIA_SUCCESSION if args.time_horizon > 0 else None
                ),
                time_horizon_years=args.time_horizon,
            )
            text_report = format_restoration_report(result) + _ANNUAL_NOTE
        else:
            result = run_extraction(ecosystem, args.units)
            text_report = format_report(result) + _ANNUAL_NOTE
        output_result(text_report, result, args, notes=_POSIDONIA_NOTES)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
