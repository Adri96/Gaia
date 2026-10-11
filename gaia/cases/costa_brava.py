"""
Gaia v0.1 — Costa Brava Holm Oak Forest deforestation case.

Mediterranean forest ecosystem with 11 agents spanning the full web of
biological and physical dependencies: from the mycorrhizal underground
network to apex raptors and the coastal tourism economy.

Scientific context:
    Mediterranean forests operate under fundamentally different constraints
    than temperate ones. Summer drought is the defining limiting factor;
    regeneration is slower; fire risk creates positive feedback loops once
    canopy cover is lost. The safe extraction threshold (25%) is lower than
    a temperate forest (30%) for these reasons.

    The mycorrhizal network is modeled as a KEYSTONE agent — it is the
    underground infrastructure that conditions tree regeneration, soil
    nutrient cycling, and water acquisition. Its collapse cascades into
    every other biological agent.

    Fire & Microclimate Regulation uses an exponential (not logistic) damage
    function: once the canopy opens, drier and hotter stands burn more often
    and every fire opens the canopy further, a positive feedback with no
    "plateau." (The agent was "Carbon & Climate"; its carbon component is
    now valued by gaia.carbon alone, decision D3.)

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    | Parameter                     | Value         | Unit    | Source        | Confidence |
    |-------------------------------|---------------|---------|---------------|------------|
    | total_units                   | configurable  | trees   | Placeholder   | Low        |
    | reference area                | 100           | ha      | Placeholder   | Low        |
    | tree density                  | 100           | trees/ha| Placeholder   | Low        |
    | safe_threshold_ratio          | 0.25          | ratio   | User spec      | Medium     |
    | unit_value                    | 60.0 €/tree   | €/tree  | User spec      | Medium     |
    | Canopy Trees weight           | 0.12          | ratio   | User spec      | Medium     |
    | Understory & Matorral weight  | 0.08          | ratio   | User spec      | Medium     |
    | Mycorrhizal Fungi weight      | 0.13          | ratio   | User spec      | Medium     |
    | Soil Microbiome weight        | 0.10          | ratio   | User spec      | Medium     |
    | Pollinators & Insects weight  | 0.10          | ratio   | User spec      | Medium     |
    | Forest Birds weight           | 0.08          | ratio   | User spec      | Medium     |
    | Forest Mammals weight         | 0.07          | ratio   | User spec      | Medium     |
    | Raptors & Apex Predators wt   | 0.04          | ratio   | User spec      | Medium     |
    | Watershed & Water Cycle wt    | 0.12          | ratio   | User spec      | Medium     |
    | Fire & Microclimate weight    | 0.10          | ratio   | User spec      | Medium     |
    | Human Communities weight      | 0.06          | ratio   | User spec      | Medium     |
    | annual_value_per_ha (all)     | 1,593         | €/ha/yr | de Groot 2012 | Low        |
    | logistic steepness            | 12.0          | –       | Placeholder   | Low        |
    | exponential base (fire)       | 2.0           | –       | Placeholder   | Low        |
    | dependency weight sum         | 1.00          | –       | Verified ✓    | High       |

Agent values (decisions D1, D2):
    Every agent uses the same yearly value per hectare and the dependency
    weights split it, so sum(weight × value) = €1,593/ha/yr × area_ha at full
    damage (€159,300/yr for the 100 ha reference forest).

    €1,600/ha/yr [PLACEHOLDER] is the global mean for woodlands in de Groot
    et al. (2012), Ecosystem Services 1:50-61 (Int$1,588/ha/yr, 2007 price
    level; figure to be checked against the paper in Step 8), used at face value
    as €; a Mediterranean holm-oak valuation and
    currency/price-year conversion are pending (Step 8). Carbon is valued
    only by gaia.carbon (decision D3), so the climate-regulation service is
    taken out of the total: Int$7/ha/yr for woodlands in de Groot et al.
    (2012, supporting material, Table 9.1; a single estimate), hence
    €1,600 − €7 = €1,593/ha/yr. The renamed Fire & Microclimate Regulation
    agent keeps its 0.10 share of that non-carbon total; Soil Microbiome's
    description no longer lists carbon storage — soil carbon is valued by
    gaia.carbon through soil_carbon_tonnes × soil_release_fraction, and the
    agent's value, a share of the non-carbon total, never contained it.

    An earlier version back-solved per-agent rates so that externality <
    revenue at 25% and > revenue at 50% ("calibrated", €3.5M in total);
    rates are never tuned to produce an outcome.

Dependency weights sum: 0.12+0.08+0.13+0.10+0.10+0.08+0.07+0.04+0.12+0.10+0.06 = 1.00 ✓

CLI usage:
    python -m gaia.cases.costa_brava
    python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --units 4000
    python -m gaia.cases.costa_brava --trees 10000 --units 4000 --mode restore
    python -m gaia.cases.costa_brava --units 4000 --format json
"""

import argparse
import sys
import warnings
from typing import Optional

from gaia.cli import (
    add_common_arguments,
    add_restoration_arguments,
    apply_carbon_price_view,
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
from gaia.pricing import scale_anchors
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

# ── Reference area ───────────────────────────────────────────────────────────
# [PLACEHOLDER] 10,000 trees on 100 ha = 100 trees/ha, so the per-tree
# absorption below (0.018 t CO₂/yr) gives ~1.8 t CO₂/ha/yr. Without an
# explicit area, a forest of N trees covers N / COSTA_BRAVA_TREES_PER_HA ha.
COSTA_BRAVA_TOTAL_TREES: int = 10_000
COSTA_BRAVA_AREA_HA: float = 100.0
COSTA_BRAVA_TREES_PER_HA: float = COSTA_BRAVA_TOTAL_TREES / COSTA_BRAVA_AREA_HA

# € / ha / yr of service lost at full damage, every agent (see module
# docstring): the de Groot (2012) woodland total without its climate
# regulation (carbon) component, €1,600 − €7 [PLACEHOLDER].
_CB_VALUE_PER_HA_YR: float = 1_600.0 - 7.0

# v0.4: Costa Brava Mediterranean succession curve
# Slower than temperate forest due to drought stress and fire risk.
# [PLACEHOLDER — pending calibration against Mediterranean oak succession data]
_CB_SUCCESSION = SuccessionCurve(
    pioneer_end_year=12.0,
    intermediate_end_year=35.0,
    climax_approach_year=80.0,
    pioneer_service=0.03,
    intermediate_service=0.30,
    maturation_delay=3.0,
)

# v0.4: Costa Brava carbon profile (per tree)
# [PLACEHOLDER — pending calibration against Mediterranean carbon data]
_CB_CARBON = CarbonProfile(
    stored_carbon_tonnes=0.5,
    annual_absorption_tonnes=0.018,
    soil_carbon_tonnes=0.35,
    soil_release_fraction=0.25,
)

# v0.4: Costa Brava resilience configuration
_CB_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.12,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.50,
)

# v0.5: Costa Brava Holm Oak substrate profile
# Mediterranean soil — thin, high erosion under drought, very slow formation.
# Threshold capacity function: below ~8cm soil, holm oak cannot regenerate.
# [PLACEHOLDER — pending calibration against Mediterranean soil surveys]
_HOLM_OAK_SUBSTRATE = SubstrateProfile(
    substrate_type="terrestrial_soil",
    soil_depth_cm=30.0,
    water_availability_mm_yr=550.0,
    erosion_rate_unprotected=25.0,   # t/ha/yr — high for degraded Mediterranean
    erosion_rate_protected=1.0,      # t/ha/yr — some erosion even under cover
    formation_rate=0.4,              # t/ha/yr — ~0.03 mm/yr, very slow
    capacity_function="threshold",
    erosion_alpha=2.0,
    critical_minimum=8.0,            # cm — below this, holm oak can't regenerate
    residual_fraction=0.05,          # near-zero capacity below critical minimum
    confidence="medium",
)

# v0.6: Costa Brava Holm Oak discount configuration
# Ramsey formula: r = 0.005 + 1.35 × 0.013 ≈ 0.023
_COSTA_BRAVA_OAK_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.025,  # Higher: Mediterranean holm oak more threatened
    horizon_years=100,  # carbon price: the default, social cost of carbon
)

# v0.7: Costa Brava Holm Oak pricing configuration. Anchor values are €/yr
# for the COSTA_BRAVA_AREA_HA reference forest (first written for 1,000 ha and
# restated per hectare × 100 ha); the builder scales them with area_ha.
_COSTA_BRAVA_OAK_PRICING = PricingConfig(
    anchors=[
        # The former carbon anchor (€80/t × 1.7 t/ha/yr × 100 ha) is gone:
        # carbon is valued only by gaia.carbon (decision D3).
        AnchorPoint(
            agent_name="Watershed & Water Cycle",
            anchor_value=25_000.0,
            source="Municipal water treatment cost avoided: ~€2.50/m³ × 100 m³/ha/yr × 100 ha",
            confidence="medium",
            description="Watershed: €2.50/m³ × 10,000 m³/yr recharge",
        ),
    ],
    scarcity_functions={
        "Mycorrhizal Fungi": ScarcityFunction("smooth", alpha=2.0, max_multiplier=50.0, description="Non-substitutable; no artificial equivalent"),
        "Soil Microbiome": ScarcityFunction("smooth", alpha=1.5, max_multiplier=50.0, description="Partially substitutable (fertilizers)"),
        "Canopy Trees": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Understory & Matorral": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Pollinators & Insects": ScarcityFunction("smooth", alpha=2.0, max_multiplier=50.0, description="Hand pollination ~$5,000/ha/yr replacement cost"),
        "Forest Birds": ScarcityFunction("smooth", alpha=0.8, max_multiplier=50.0),
        "Forest Mammals": ScarcityFunction("smooth", alpha=0.8, max_multiplier=50.0),
        "Raptors & Apex Predators": ScarcityFunction("smooth", alpha=0.5, max_multiplier=50.0),
        "Watershed & Water Cycle": ScarcityFunction("threshold", threshold=0.4, max_multiplier=30.0, description="Water purification collapses below ~40% forest cover"),
        "Fire & Microclimate Regulation": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Human Communities": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)

# Shared steepness for all logistic agents.
# 12.0 gives a clear S-curve with an observable knee at the threshold.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS: float = 12.0


def build_costa_brava_ecosystem(
    total_trees: int = COSTA_BRAVA_TOTAL_TREES,
    safe_threshold_ratio: float = 0.25,
    tree_value: float = 60.0,
    with_pricing: bool = False,
    area_ha: Optional[float] = None,
) -> Ecosystem:
    """
    Build the Costa Brava Holm Oak Forest ecosystem with 11 agents.

    The ecosystem spans the full dependency web: underground mycorrhizal network,
    soil microbiome, understory vegetation, pollinators, birds, mammals, raptors,
    watershed, fire and microclimate regulation, and local human communities.

    Args:
        total_trees: Total number of trees in the forest. [PLACEHOLDER]
        safe_threshold_ratio: Fraction extractable before ecosystem stress accelerates.
            Default 0.25 — lower than temperate forests due to Mediterranean drought
            stress, slower regeneration, and fire feedback loops. [User spec, Medium]
        tree_value: Revenue per tree in euros. Default 60.0 — holm oak is less
            commercially valuable than northern timber species. Cork harvest would
            use a different economic model (no felling). [User spec, Medium]
        with_pricing: If True, attach v0.7 endogenous pricing configuration.
        area_ha: Forest area in hectares. Default: total_trees at the
            reference density (COSTA_BRAVA_TREES_PER_HA).

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    if area_ha is None:
        area_ha = total_trees / COSTA_BRAVA_TREES_PER_HA
    resource = Resource(
        name="Costa Brava Holm Oak Forest",
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        area_ha=area_ha,
        carbon_profile=_CB_CARBON,
        resilience=_CB_RESILIENCE,
        substrate=_HOLM_OAK_SUBSTRATE,
        discount=_COSTA_BRAVA_OAK_DISCOUNT,
    )

    t = safe_threshold_ratio  # shorthand for threshold argument

    agents = [
        # ── Underground infrastructure ──────────────────────────────────────
        Agent(
            name="Mycorrhizal Fungi",
            dependency_weight=0.13,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Keystone underground network — nutrient/water transport, cascades to all tree regeneration",
            # v0.3: Producer-level, KEYSTONE agent
            trophic_level=0,
            is_keystone=True,
            keystone_threshold=0.3,
        ),
        Agent(
            name="Soil Microbiome",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Soil microbiome and biocrusts — nitrogen fixation, nutrient cycling, erosion prevention",
            # v0.3: Abiotic process agent
            trophic_level=-1,
        ),
        # ── Vegetation ──────────────────────────────────────────────────────
        Agent(
            name="Canopy Trees",
            dependency_weight=0.12,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Remaining canopy trees — self-reinforcing decline from microclimate loss and network fragmentation",
            # v0.3: Producer — the resource itself
            trophic_level=0,
        ),
        Agent(
            name="Understory & Matorral",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Understory shrubs and aromatic plants — microclimate collapse and biodiversity loss",
            # v0.3: Secondary producer
            trophic_level=0,
        ),
        # ── Invertebrates ───────────────────────────────────────────────────
        Agent(
            name="Pollinators & Insects",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Keystone pollination services — base of animal food web, agricultural crop dependency",
            # v0.3: Primary consumer, KEYSTONE functional group
            trophic_level=1,
            is_keystone=True,
            keystone_threshold=0.4,
        ),
        # ── Vertebrates ─────────────────────────────────────────────────────
        Agent(
            name="Forest Birds",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Nesting and migratory stopover habitat — seed dispersal, insect control, ecotourism",
            # v0.3: Primary consumer (insects + seeds)
            trophic_level=1,
        ),
        Agent(
            name="Forest Mammals",
            dependency_weight=0.07,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Habitat displacement — predator-prey disruption, human-wildlife conflict, crop damage",
            # v0.3: Primary consumer — herbivores and omnivores
            trophic_level=1,
        ),
        Agent(
            name="Raptors & Apex Predators",
            dependency_weight=0.04,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Apex trophic control — carrion processing, extreme K-strategy vulnerability, trophic cascade trigger",
            # v0.3: Tertiary consumer — apex predator
            trophic_level=3,
        ),
        # ── Physical systems ────────────────────────────────────────────────
        Agent(
            name="Watershed & Water Cycle",
            dependency_weight=0.12,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Aquifer recharge, flood control, drought buffering — Costa Brava water and tourism supply",
            # v0.3: Abiotic process
            trophic_level=-1,
        ),
        Agent(
            name="Fire & Microclimate Regulation",
            dependency_weight=0.10,
            damage_function=exponential_damage(threshold=t, base=2.0),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Fire risk amplification, loss of shade and moisture buffering — self-reinforcing, no plateau",
            # v0.3: Abiotic process
            trophic_level=-1,
        ),
        # ── Human systems ───────────────────────────────────────────────────
        Agent(
            name="Human Communities",
            dependency_weight=0.06,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_CB_VALUE_PER_HA_YR,
            description="Water, fire protection, tourism economy, traditional livelihoods — Costa Brava coastal dependency",
            # v0.3: External beneficiary
            trophic_level=-1,
        ),
    ]

    # v0.3: Full trophic web with 17 interaction edges
    interactions = [
        # Mycorrhizal network is the backbone — its collapse cascades everywhere
        InteractionEdge("Mycorrhizal Fungi", "Canopy Trees", 0.35, "keystone",
            "Mycorrhizal collapse cuts nutrient/water supply to remaining trees"),
        InteractionEdge("Mycorrhizal Fungi", "Understory & Matorral", 0.25, "dependency",
            "Understory plants lose mycorrhizal nutrient access"),
        InteractionEdge("Mycorrhizal Fungi", "Soil Microbiome", 0.30, "dependency",
            "Mycorrhizal network supports bacterial communities and nutrient cycling"),

        # Pollinator collapse hits vegetation reproduction
        InteractionEdge("Pollinators & Insects", "Understory & Matorral", 0.30, "keystone",
            "Pollinator loss collapses plant reproduction"),
        InteractionEdge("Pollinators & Insects", "Forest Birds", 0.20, "trophic",
            "Insect decline reduces food for insectivorous birds"),

        # Canopy loss affects microclimate-dependent agents
        InteractionEdge("Canopy Trees", "Understory & Matorral", 0.25, "dependency",
            "Canopy loss removes shade \u2192 understory heat/drought stress"),
        InteractionEdge("Canopy Trees", "Soil Microbiome", 0.20, "dependency",
            "Canopy loss exposes soil to UV and drying \u2192 biocrust collapse"),
        InteractionEdge("Canopy Trees", "Watershed & Water Cycle", 0.30, "dependency",
            "Root loss reduces water infiltration and aquifer recharge"),

        # Prey-predator chain
        InteractionEdge("Forest Mammals", "Raptors & Apex Predators", 0.30, "trophic",
            "Prey decline starves apex predators"),
        InteractionEdge("Forest Birds", "Raptors & Apex Predators", 0.20, "trophic",
            "Bird decline reduces prey for raptors"),

        # Vegetation → herbivore dependency
        InteractionEdge("Understory & Matorral", "Forest Mammals", 0.25, "dependency",
            "Vegetation loss reduces food and cover for herbivores"),
        InteractionEdge("Understory & Matorral", "Pollinators & Insects", 0.20, "dependency",
            "Understory flowering loss reduces pollinator food sources"),

        # Soil → everything
        InteractionEdge("Soil Microbiome", "Canopy Trees", 0.15, "dependency",
            "Soil health decline reduces tree nutrient availability"),
        InteractionEdge("Soil Microbiome", "Watershed & Water Cycle", 0.20, "dependency",
            "Soil degradation reduces water retention capacity"),

        # Fire and microclimate regulation depend on the canopy
        InteractionEdge("Canopy Trees", "Fire & Microclimate Regulation", 0.35, "dependency",
            "Canopy loss dries and heats the stand, raising fire risk"),

        # Human communities depend on multiple services
        InteractionEdge("Watershed & Water Cycle", "Human Communities", 0.25, "dependency",
            "Water quality decline affects human health and tourism"),
        InteractionEdge("Fire & Microclimate Regulation", "Human Communities", 0.10, "dependency",
            "Loss of fire and microclimate regulation increases fire risk and heat stress"),
    ]

    return Ecosystem(
        name="Costa Brava Holm Oak Forest",
        resource=resource,
        agents=agents,
        interactions=interactions,
        pricing=(
            scale_anchors(_COSTA_BRAVA_OAK_PRICING, area_ha / COSTA_BRAVA_AREA_HA)
            if with_pricing else None
        ),
    )


def run_costa_brava(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.25,
    trees_cut: int = 4_000,
    tree_value: float = 60.0,
) -> str:
    """
    Run the Costa Brava Forest deforestation simulation and return the report.

    Default trees_cut=4,000 — cutting 40% of the forest (well past the 25%
    safe threshold) to illustrate the externality crossover point.

    Args:
        total_trees: Total number of trees in the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_cut: Number of trees to cut (extract).
        tree_value: Revenue per tree in euros.

    Returns:
        Formatted text report string.
    """
    ecosystem = build_costa_brava_ecosystem(
        total_trees=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        tree_value=tree_value,
    )
    result = run_extraction(ecosystem, trees_cut)
    return format_report(result)


def run_costa_brava_restoration(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.25,
    trees_to_restore: int = 4_000,
    tree_value: float = 60.0,
    planting_cost_per_tree: float = 80.0,
    annual_maintenance_per_tree: float = 15.0,
    maintenance_years: int = 15,
    time_horizon_years: int = 0,
    units_lost: Optional[int] = None,
) -> str:
    """
    Run the Costa Brava Forest restoration simulation and return the report.

    v0.4: When time_horizon_years > 0, produces maturation timeline using
    the Costa Brava succession curve.

    Args:
        total_trees: Total carrying capacity of the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_to_restore: Number of trees to replant (restore).
        tree_value: Revenue per tree in euros.
        planting_cost_per_tree: Direct cost per tree planted.
        annual_maintenance_per_tree: Annual maintenance cost per tree.
        maintenance_years: Number of years of maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).
        units_lost: Units missing before restoring (default: the units
            restored, i.e. restore what was cut).

    Returns:
        Formatted text restoration report string.
    """
    ecosystem = build_costa_brava_ecosystem(
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
        succession_curve=_CB_SUCCESSION if time_horizon_years > 0 else None,
        time_horizon_years=time_horizon_years,
        units_lost=units_lost,
    )
    return format_restoration_report(result)


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.8.1 — Costa Brava Holm Oak Forest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (25%):\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --units 2500\n\n"
            "  # Extraction — past threshold (40%):\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --units 4000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --units 4000 --mode restore\n\n"
            "  # JSON output:\n"
            "  python -m gaia.cases.costa_brava --units 4000 --format json\n"
        ),
    )
    parser.add_argument(
        "--trees",
        type=int,
        default=10_000,
        metavar="N",
        help="Total number of trees in the forest (default: 10000)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.25,
        metavar="RATIO",
        help="Safe extraction threshold ratio, 0.0 < threshold < 1.0 (default: 0.25)",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=4_000,
        metavar="N",
        help="Number of units to extract or restore (default: 4000)",
    )
    # Deprecated alias for --units
    parser.add_argument(
        "--cut", type=int, default=None, metavar="N",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--unit-value",
        type=float,
        default=60.0,
        metavar="EUROS",
        help="Revenue per unit extracted in euros (default: 60.0)",
    )
    # Deprecated alias for --unit-value
    parser.add_argument(
        "--tree-value", type=float, default=None, metavar="EUROS",
        help=argparse.SUPPRESS,
    )
    add_common_arguments(parser)
    add_restoration_arguments(
        parser,
        planting_cost_default=80.0,
        maintenance_cost_default=15.0,
        maintenance_years_default=15,
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
        ecosystem = build_costa_brava_ecosystem(
            total_trees=args.trees,
            safe_threshold_ratio=args.threshold,
            tree_value=args.unit_value,
            with_pricing=args.with_pricing,
            area_ha=args.area_ha,
        )
        apply_carbon_price_view(ecosystem, args.carbon_price)
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
                units_lost=args.units_lost,
                succession_curve=(
                    _CB_SUCCESSION if args.time_horizon > 0 else None
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
