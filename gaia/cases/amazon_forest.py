"""
Gaia v0.7 — Central Amazon Old-Growth Lowland Rainforest case.

Tropical forest ecosystem with 11 agents spanning the full trophic web:
from mycorrhizal fungi (the nutrient gateway on depleted Oxisol) to
apex predators (jaguars, harpy eagles) and the aquatic river system.

Scientific context:
    The Amazon represents the world's highest-productivity terrestrial
    ecosystem on one of its most nutrient-depleted soils — a paradox that
    makes it uniquely interesting for Gaia's substrate-dependent modeling.

    The forest's survival depends entirely on rapid nutrient recycling
    through mycorrhizal networks; destroy the biological layer and the
    laterite substrate cannot support recovery. The destruction:recovery
    ratio (~3000:1 for cultivated land) is the most extreme in any Gaia case.

    Mycorrhizal Fungi are the KEYSTONE agent — 60% of the basin sits on
    P-depleted Oxisols where phosphorus limitation is the primary constraint
    on productivity (Nature 2022, AFEX experiment). Without mycorrhizae,
    the forest literally cannot access the nutrients it needs.

    The Amazon also features atmospheric moisture feedback: intact forest
    generates its own rainfall via "flying rivers." This dual feedback
    (substrate + moisture) produces a sharper degradation spiral than
    any Mediterranean case. This is captured indirectly via the substrate
    threshold function and high erosion asymmetry.

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    | Parameter                     | Value         | Unit    | Source        | Confidence |
    |-------------------------------|---------------|---------|---------------|------------|
    | total_units                   | 400,000       | trees   | Spec §2       | Medium     |
    | safe_threshold_ratio          | 0.20          | ratio   | Spec §6       | Medium     |
    | unit_value                    | 1.50 €/tree   | €/tree  | Calibrated    | Low        |
    | Canopy Trees weight           | 0.15          | ratio   | Spec §3       | Medium     |
    | Understory weight             | 0.08          | ratio   | Spec §3       | Medium     |
    | Mycorrhizal Fungi weight      | 0.15          | ratio   | Spec §3       | Medium     |
    | Soil Decomposers weight       | 0.10          | ratio   | Spec §3       | Medium     |
    | Pollinators weight            | 0.09          | ratio   | Spec §3       | Medium     |
    | Seed Dispersers weight        | 0.08          | ratio   | Spec §3       | Medium     |
    | Herbivores weight             | 0.07          | ratio   | Spec §3       | Medium     |
    | Mesopredators weight          | 0.05          | ratio   | Spec §3       | Medium     |
    | Apex Predators weight         | 0.03          | ratio   | Spec §3       | Medium     |
    | Aquatic System weight         | 0.10          | ratio   | Spec §3       | Medium     |
    | Epiphytes & Bromeliads weight | 0.10          | ratio   | Spec §3       | Medium     |
    | logistic steepness            | 12.0          | –       | Placeholder   | Low        |
    | dependency weight sum         | 1.00          | –       | Verified ✓    | High       |

Monetary rate calibration:
    Rates are set so that sum(weight × rate) ≈ €8,400,000 (total effective
    max externality for 10,000 ha at ~€840/ha/yr from spec §8 meta-analysis).

    Full destruction (400,000 trees @ €1.50 = €600k revenue) imposes ≈€8.4M in
    externalities. Ratio: 14× — every euro of timber revenue costs society ~€14.
    This is much higher than Costa Brava (5.8×), reflecting the Amazon's extreme
    ecosystem service value and the futility of extractive economics on Oxisol.

Dependency weights sum: 0.15+0.08+0.15+0.10+0.09+0.08+0.07+0.05+0.03+0.10+0.10 = 1.00 ✓

CLI usage:
    python -m gaia.cases.amazon_forest
    python -m gaia.cases.amazon_forest --trees 400000 --threshold 0.20 --cut 80000
    python -m gaia.cases.amazon_forest --trees 400000 --threshold 0.20 --cut 80000 --mode restore
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

# ── Succession curve ───────────────────────────────────────────────────────────
# Amazon secondary forest: fast initial cover (2-3 yr), 20 yr to 80% biomass,
# 66 yr to 90% (Poorter 2016). Faster than Mediterranean but slower to full
# climax than temperate deciduous forest.
# [PLACEHOLDER — pending calibration against Poorter 2016 and Nature Comms 2021]
_AMAZON_SUCCESSION = SuccessionCurve(
    pioneer_end_year=5.0,
    intermediate_end_year=20.0,
    climax_approach_year=66.0,
    pioneer_service=0.05,
    intermediate_service=0.40,
    maturation_delay=2.0,
)

# ── Carbon profile (per tree) ─────────────────────────────────────────────────
# From spec §2: 173 Mg C/ha total biomass (above + below), ~400 trees/ha.
# Per tree: 173 × 3.67 / 400 ≈ 1.587 t CO₂ stored per tree.
# Annual absorption: 0.62 t C/ha/yr × 3.67 / 400 ≈ 0.0057 t CO₂/tree/yr.
# Soil carbon: ~40 t C/ha in roots → 40 × 3.67 / 400 ≈ 0.367 t CO₂/tree.
# [PLACEHOLDER — pending calibration against eddy covariance data]
_AMAZON_CARBON = CarbonProfile(
    stored_carbon_tonnes=1.587,
    annual_absorption_tonnes=0.006,
    soil_carbon_tonnes=0.367,
    soil_release_fraction=0.30,
    carbon_price_per_tonne=80.0,
)

# ── Resilience configuration ──────────────────────────────────────────────────
# Amazon tipping point at 20-25% deforestation (Lovejoy & Nobre 2018).
# Narrower safe zone than Mediterranean; crossing = catastrophic.
_AMAZON_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.10,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.50,
)

# ── Substrate profile ─────────────────────────────────────────────────────────
# Tropical Oxisol (Ferralsol): world's most nutrient-depleted soil.
# Threshold capacity function: organic recycling layer must remain intact.
# Below critical minimum, laterite exposure → near-permanent degradation.
# Erosion asymmetry is extreme: 90 t/ha/yr (cultivated) vs 0.015 t/ha/yr (intact).
# From spec §4: destruction:recovery ratio ~3000:1.
# [PLACEHOLDER — pending calibration against RUSLE data for Central Amazon]
_AMAZON_SUBSTRATE = SubstrateProfile(
    substrate_type="terrestrial_soil",
    soil_depth_cm=20.0,
    water_availability_mm_yr=2200.0,
    erosion_rate_unprotected=90.0,    # t/ha/yr — extreme for bare tropical slope
    erosion_rate_protected=0.015,     # t/ha/yr — intact forest, negligible erosion
    formation_rate=0.4,               # t/ha/yr — organic layer rebuilding
    capacity_function="threshold",
    erosion_alpha=2.5,                # Higher than Mediterranean: sharper response
    critical_minimum=5.0,             # cm — below this, laterite exposed
    residual_fraction=0.02,           # near-zero: laterite cannot support forest
    confidence="medium",
)

# ── Discount configuration ────────────────────────────────────────────────────
# Ramsey formula: r = 0.005 + 1.35 × 0.013 ≈ 0.023
_AMAZON_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.03,  # Higher: Amazon under acute deforestation pressure
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
)

# ── v0.7: Amazon pricing configuration ────────────────────────────────────────
# From spec §8: 5 anchors, total ~€8.4M/yr for 10,000 ha
_AMAZON_PRICING = PricingConfig(
    anchors=[
        AnchorPoint(
            agent_name="Canopy Trees",
            anchor_value=5_080_000.0,
            source="Carbon stock protection: 6.35M t CO₂ × €80/t ÷ 100 yr amortized",
            confidence="high",
            description="Carbon stock: €5.08M/yr (amortized stock protection)",
        ),
        AnchorPoint(
            agent_name="Canopy Trees",
            anchor_value=880_000.0,
            source="Carbon sequestration: 11 Mg C/ha × 10,000 ha × 3.67 × €80/t × 0.027",
            confidence="high",
            description="Carbon sequestration: €880k/yr",
        ),
        AnchorPoint(
            agent_name="Canopy Trees",
            anchor_value=1_500_000.0,
            source="Rainfall recycling service: $15-20/ha/yr × 10,000 ha + downwind agricultural value",
            confidence="medium",
            description="Water cycling / rainfall: €1.5M/yr",
        ),
        AnchorPoint(
            agent_name="Aquatic System",
            anchor_value=200_000.0,
            source="Fisheries: river fish catch value for 10,000 ha watershed",
            confidence="medium",
            description="Fisheries: €200k/yr",
        ),
        AnchorPoint(
            agent_name="Pollinators",
            anchor_value=410_000.0,
            source="Biodiversity/habitat: $410/ha/yr meta-analysis (Brouwer et al. 2022)",
            confidence="medium",
            description="Biodiversity/habitat: €410k/yr",
        ),
    ],
    scarcity_functions={
        "Canopy Trees": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Understory": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Mycorrhizal Fungi": ScarcityFunction(
            "smooth", alpha=2.5, max_multiplier=50.0,
            description="HIGHEST: non-substitutable nutrient gateway on P-depleted Oxisol",
        ),
        "Soil Decomposers": ScarcityFunction(
            "smooth", alpha=2.0, max_multiplier=50.0,
            description="Tropical nutrient cycling — termites process ~30% dead wood",
        ),
        "Pollinators": ScarcityFunction(
            "smooth", alpha=2.0, max_multiplier=50.0,
            description=">90% of tropical tree species require animal pollination",
        ),
        "Seed Dispersers": ScarcityFunction("smooth", alpha=1.5, max_multiplier=50.0),
        "Herbivores": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Mesopredators": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Apex Predators": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Aquatic System": ScarcityFunction(
            "threshold", threshold=0.30, max_multiplier=50.0,
            description="Aquatic collapse threshold: below 30% health, spawning fails",
        ),
        "Epiphytes & Bromeliads": ScarcityFunction("smooth", alpha=1.5, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)

# Shared steepness for all logistic agents.
# 12.0 gives a clear S-curve with an observable knee at the threshold.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS: float = 12.0


def build_amazon_ecosystem(
    total_trees: int = 400_000,
    safe_threshold_ratio: float = 0.20,
    tree_value: float = 1.50,
    with_pricing: bool = False,
) -> Ecosystem:
    """
    Build the Central Amazon Rainforest ecosystem with 11 agents.

    The ecosystem spans the full tropical trophic web: mycorrhizal nutrient
    network, soil decomposers, canopy and understory vegetation, pollinators,
    seed dispersers, herbivores, mesopredators, apex predators, aquatic system,
    and epiphytes/bromeliads.

    Args:
        total_trees: Total number of trees in the forest. Default 400,000
            (~40 trees/ha × 10,000 ha). [Spec §2]
        safe_threshold_ratio: Fraction extractable before ecosystem stress
            accelerates. Default 0.20 — the Lovejoy-Nobre Amazon tipping point.
            [Spec §6, Medium]
        tree_value: Revenue per tree in euros. Default 1.50 — selective logging
            on a per-tree basis; low value per unit but massive unit count.
            [Calibrated, Low]
        with_pricing: If True, attach v0.7 endogenous pricing configuration.

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    resource = Resource(
        name="Central Amazon Old-Growth Lowland Forest",
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        carbon_profile=_AMAZON_CARBON,
        resilience=_AMAZON_RESILIENCE,
        substrate=_AMAZON_SUBSTRATE,
        discount=_AMAZON_DISCOUNT,
    )

    t = safe_threshold_ratio  # shorthand for threshold argument

    agents = [
        # ── Vegetation ──────────────────────────────────────────────────────
        Agent(
            name="Canopy Trees",
            dependency_weight=0.15,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Emergent + canopy layer (400+ species/ha) — primary biomass, carbon stock, rainfall recycling",
            trophic_level=0,
        ),
        Agent(
            name="Understory",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Sub-canopy trees, palms, ferns, epiphytes — shade-tolerant reproduction, microclimate regulation",
            trophic_level=0,
        ),
        # ── Underground infrastructure ──────────────────────────────────────
        Agent(
            name="Mycorrhizal Fungi",
            dependency_weight=0.15,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Arbuscular + ectomycorrhizae — KEYSTONE nutrient gateway on P-depleted Oxisol, non-substitutable",
            trophic_level=0,
            is_keystone=True,
            keystone_threshold=0.25,
        ),
        Agent(
            name="Soil Decomposers",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Termites, fungi, bacteria, dung beetles — organic matter breakdown, nutrient return",
            trophic_level=-1,
        ),
        # ── Invertebrates & Mutualists ──────────────────────────────────────
        Agent(
            name="Pollinators",
            dependency_weight=0.09,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Bees, butterflies, hummingbirds, bats — reproduction for 90%+ of canopy species",
            trophic_level=1,
            is_keystone=True,
            keystone_threshold=0.35,
        ),
        Agent(
            name="Seed Dispersers",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Monkeys, toucans, agoutis, tapirs — forest regeneration, genetic connectivity",
            trophic_level=1,
        ),
        # ── Consumers ───────────────────────────────────────────────────────
        Agent(
            name="Herbivores",
            dependency_weight=0.07,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Capybaras, sloths, leafcutter ants, insects — energy transfer, population dynamics",
            trophic_level=1,
        ),
        Agent(
            name="Mesopredators",
            dependency_weight=0.05,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Snakes (boa, anaconda), caimans, ocelots, anteaters — mid-trophic regulation",
            trophic_level=2,
        ),
        Agent(
            name="Apex Predators",
            dependency_weight=0.03,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Jaguars, harpy eagles — top-down population control, KEYSTONE trophic role",
            trophic_level=3,
        ),
        # ── Aquatic & Epiphyte systems ──────────────────────────────────────
        Agent(
            name="Aquatic System",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="River fish (3,000+ species), river dolphins, aquatic plants — nutrient transport, fisheries",
            trophic_level=-1,
        ),
        Agent(
            name="Epiphytes & Bromeliads",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_400_000.0,
            description="Orchids, bromeliads, lichens (~25,000 species) — water retention, microhabitat creation",
            trophic_level=0,
        ),
    ]

    # ── Interaction edges ───────────────────────────────────────────────────
    # Derived from spec §3 interaction matrix, selecting edges with strength ≥ 0.10.
    # Reading: (source, target, strength) — "source's damage propagates to target"
    interactions = [
        # Mycorrhizal network is the nutrient gateway — backbone of the system
        InteractionEdge("Mycorrhizal Fungi", "Canopy Trees", 0.40, "keystone",
            "Mycorrhizal collapse cuts phosphorus supply to canopy on P-depleted Oxisol"),
        InteractionEdge("Mycorrhizal Fungi", "Understory", 0.25, "dependency",
            "Understory loses mycorrhizal nutrient access"),

        # Canopy Trees support nearly everything
        InteractionEdge("Canopy Trees", "Understory", 0.30, "dependency",
            "Canopy loss removes shade → understory heat/drought stress"),
        InteractionEdge("Canopy Trees", "Epiphytes & Bromeliads", 0.35, "dependency",
            "Epiphytes lose structural substrate when canopy trees fall"),
        InteractionEdge("Canopy Trees", "Herbivores", 0.25, "dependency",
            "Canopy loss reduces food and habitat for herbivores"),
        InteractionEdge("Canopy Trees", "Soil Decomposers", 0.20, "dependency",
            "Less litter input reduces decomposer substrate"),
        InteractionEdge("Canopy Trees", "Mycorrhizal Fungi", 0.15, "dependency",
            "Trees provide carbon to mycorrhizal partners"),
        InteractionEdge("Canopy Trees", "Pollinators", 0.30, "dependency",
            "Canopy flowering loss reduces pollinator food sources"),
        InteractionEdge("Canopy Trees", "Seed Dispersers", 0.20, "dependency",
            "Fewer fruiting trees reduce disperser food"),
        InteractionEdge("Canopy Trees", "Aquatic System", 0.15, "dependency",
            "Canopy loss reduces riparian shade and leaf litter input to streams"),
        InteractionEdge("Canopy Trees", "Mesopredators", 0.10, "dependency",
            "Canopy loss reduces habitat for arboreal mesopredators"),

        # Understory → consumers and epiphytes
        InteractionEdge("Understory", "Herbivores", 0.15, "dependency",
            "Understory vegetation is primary herbivore food source"),
        InteractionEdge("Understory", "Epiphytes & Bromeliads", 0.20, "dependency",
            "Understory structural support for lower-level epiphytes"),
        InteractionEdge("Understory", "Pollinators", 0.15, "dependency",
            "Understory flowering provides pollinator resources"),
        InteractionEdge("Understory", "Mycorrhizal Fungi", 0.10, "dependency",
            "Understory plants contribute to mycorrhizal network"),
        InteractionEdge("Understory", "Soil Decomposers", 0.15, "dependency",
            "Understory litter feeds decomposer community"),

        # Soil Decomposers → nutrient cycling
        InteractionEdge("Soil Decomposers", "Canopy Trees", 0.15, "dependency",
            "Decomposer decline reduces nutrient availability for trees"),
        InteractionEdge("Soil Decomposers", "Understory", 0.10, "dependency",
            "Reduced decomposition limits understory nutrient access"),
        InteractionEdge("Soil Decomposers", "Mycorrhizal Fungi", 0.20, "dependency",
            "Decomposers feed mycorrhizal nutrient pool"),

        # Pollinator → vegetation reproduction
        InteractionEdge("Pollinators", "Canopy Trees", 0.30, "keystone",
            "Pollinator loss blocks reproduction for 90%+ of canopy species"),
        InteractionEdge("Pollinators", "Understory", 0.15, "keystone",
            "Pollinator loss collapses understory plant reproduction"),
        InteractionEdge("Pollinators", "Epiphytes & Bromeliads", 0.10, "dependency",
            "Some epiphyte reproduction depends on specialist pollinators"),

        # Seed Dispersers → forest regeneration
        InteractionEdge("Seed Dispersers", "Canopy Trees", 0.20, "dependency",
            "Loss of dispersers reduces tree recruitment and genetic connectivity"),
        InteractionEdge("Seed Dispersers", "Understory", 0.10, "dependency",
            "Understory seed dispersal decline"),
        InteractionEdge("Seed Dispersers", "Mesopredators", 0.10, "trophic",
            "Seed dispersers are prey for some mesopredators"),

        # Trophic chain: Herbivores → predators
        InteractionEdge("Herbivores", "Mesopredators", 0.30, "trophic",
            "Herbivore decline starves mid-level predators"),
        InteractionEdge("Herbivores", "Apex Predators", 0.35, "trophic",
            "Large herbivore decline starves apex predators (jaguar prey)"),
        InteractionEdge("Herbivores", "Aquatic System", 0.10, "dependency",
            "Riparian herbivore activity affects aquatic nutrient input"),

        # Mesopredators → Apex Predators
        InteractionEdge("Mesopredators", "Apex Predators", 0.30, "trophic",
            "Mesopredator decline reduces prey for harpy eagles and jaguars"),
        InteractionEdge("Mesopredators", "Aquatic System", 0.10, "dependency",
            "Caiman and aquatic mesopredator population dynamics"),

        # Aquatic System → various
        InteractionEdge("Aquatic System", "Canopy Trees", 0.15, "dependency",
            "Riparian nutrient transport supports floodplain forest"),
        InteractionEdge("Aquatic System", "Mesopredators", 0.10, "dependency",
            "Aquatic system decline reduces food for aquatic mesopredators"),

        # Epiphytes → canopy microhabitat
        InteractionEdge("Epiphytes & Bromeliads", "Canopy Trees", 0.20, "dependency",
            "Epiphytes contribute to canopy water retention and microhabitat"),
        InteractionEdge("Epiphytes & Bromeliads", "Understory", 0.15, "dependency",
            "Bromeliad water reservoirs support understory moisture"),
    ]

    return Ecosystem(
        name="Central Amazon Old-Growth Lowland Forest",
        resource=resource,
        agents=agents,
        interactions=interactions,
        pricing=_AMAZON_PRICING if with_pricing else None,
    )


def run_amazon(
    total_trees: int = 400_000,
    safe_threshold_ratio: float = 0.20,
    trees_cut: int = 80_000,
    tree_value: float = 1.50,
) -> str:
    """
    Run the Amazon Forest deforestation simulation and return the report.

    Default trees_cut=80,000 — cutting 20% of the forest (at the Lovejoy-Nobre
    tipping point threshold) to illustrate tipping point dynamics.

    Args:
        total_trees: Total number of trees in the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_cut: Number of trees to cut (extract).
        tree_value: Revenue per tree in euros.

    Returns:
        Formatted text report string.
    """
    ecosystem = build_amazon_ecosystem(
        total_trees=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        tree_value=tree_value,
    )
    result = run_extraction(ecosystem, trees_cut)
    return format_report(result)


def run_amazon_restoration(
    total_trees: int = 400_000,
    safe_threshold_ratio: float = 0.20,
    trees_to_restore: int = 80_000,
    tree_value: float = 1.50,
    planting_cost_per_tree: float = 5.0,
    annual_maintenance_per_tree: float = 1.0,
    maintenance_years: int = 20,
    time_horizon_years: int = 0,
) -> str:
    """
    Run the Amazon Forest restoration simulation and return the report.

    v0.4: When time_horizon_years > 0, produces maturation timeline using
    the Amazon succession curve.

    Args:
        total_trees: Total carrying capacity of the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_to_restore: Number of trees to replant (restore).
        tree_value: Revenue per tree in euros.
        planting_cost_per_tree: Direct cost per tree planted. Default €5.0
            (lower than temperate due to rapid tropical growth).
        annual_maintenance_per_tree: Annual maintenance cost per tree.
        maintenance_years: Number of years of maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).

    Returns:
        Formatted text restoration report string.
    """
    ecosystem = build_amazon_ecosystem(
        total_trees=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        tree_value=tree_value,
    )
    cost = RestorationCost(
        planting_cost_per_unit=planting_cost_per_tree,
        annual_maintenance_per_unit=annual_maintenance_per_tree,
        maintenance_years=maintenance_years,
    )
    recovery_fns = [
        logistic_recovery(threshold=safe_threshold_ratio)
        for _ in ecosystem.agents
    ]
    result = run_restoration(
        ecosystem, trees_to_restore, cost, recovery_fns,
        succession_curve=_AMAZON_SUCCESSION if time_horizon_years > 0 else None,
        time_horizon_years=time_horizon_years,
    )
    return format_restoration_report(result)


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.8.1 — Central Amazon Rainforest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (20%):\n"
            "  python -m gaia.cases.amazon_forest --trees 400000 --threshold 0.20 --units 80000\n\n"
            "  # Extraction — past threshold (40%):\n"
            "  python -m gaia.cases.amazon_forest --trees 400000 --threshold 0.20 --units 160000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.amazon_forest --trees 400000 --units 80000 --mode restore\n\n"
            "  # JSON output:\n"
            "  python -m gaia.cases.amazon_forest --units 80000 --format json\n"
        ),
    )
    parser.add_argument(
        "--trees",
        type=int,
        default=400_000,
        metavar="N",
        help="Total number of trees in the forest (default: 400000)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        metavar="RATIO",
        help="Safe extraction threshold ratio, 0.0 < threshold < 1.0 (default: 0.20)",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=80_000,
        metavar="N",
        help="Number of units to extract or restore (default: 80000)",
    )
    # Deprecated alias for --units
    parser.add_argument(
        "--cut", type=int, default=None, metavar="N",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--unit-value",
        type=float,
        default=1.50,
        metavar="EUROS",
        help="Revenue per unit extracted in euros (default: 1.50)",
    )
    # Deprecated alias for --unit-value
    parser.add_argument(
        "--tree-value", type=float, default=None, metavar="EUROS",
        help=argparse.SUPPRESS,
    )
    add_common_arguments(parser)
    add_restoration_arguments(
        parser,
        planting_cost_default=5.0,
        maintenance_cost_default=1.0,
        maintenance_years_default=20,
    )
    args = parser.parse_args(argv)
    # Resolve deprecated aliases
    if args.cut is not None:
        warnings.warn(
            "--cut is deprecated, use --units instead",
            DeprecationWarning,
            stacklevel=2,
        )
        args.units = args.cut
    if args.tree_value is not None:
        warnings.warn(
            "--tree-value is deprecated, use --unit-value instead",
            DeprecationWarning,
            stacklevel=2,
        )
        args.unit_value = args.tree_value
    return args


def main(argv: list = None) -> None:
    args = _parse_args(argv)
    warn_unused_restoration_args(args)
    try:
        ecosystem = build_amazon_ecosystem(
            total_trees=args.trees,
            safe_threshold_ratio=args.threshold,
            tree_value=args.unit_value,
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
                    _AMAZON_SUCCESSION if args.time_horizon > 0 else None
                ),
                time_horizon_years=args.time_horizon,
            )
            text_report = format_restoration_report(result)
        else:
            result = run_extraction(ecosystem, args.units)
            text_report = format_report(result)
        output_result(text_report, result, args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
