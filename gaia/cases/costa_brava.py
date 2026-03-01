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

    Carbon & Climate uses an exponential (not logistic) damage function
    because CO₂ release does not stabilize: unlike biological populations,
    atmospheric carbon accumulates continuously and has no "plateau."

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    | Parameter                     | Value         | Unit    | Source        | Confidence |
    |-------------------------------|---------------|---------|---------------|------------|
    | total_units                   | configurable  | trees   | Placeholder   | Low        |
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
    | Carbon & Climate weight       | 0.10          | ratio   | User spec      | Medium     |
    | Human Communities weight      | 0.06          | ratio   | User spec      | Medium     |
    | Canopy Trees monetary_rate    | 2,500,000 €   | €       | Calibrated     | Low        |
    | Understory monetary_rate      | 1,875,000 €   | €       | Calibrated     | Low        |
    | Mycorrhizal monetary_rate     | 3,077,000 €   | €       | Calibrated     | Low        |
    | Soil Microbiome monetary_rate | 3,500,000 €   | €       | Calibrated     | Low        |
    | Pollinators monetary_rate     | 3,500,000 €   | €       | Calibrated     | Low        |
    | Forest Birds monetary_rate    | 2,500,000 €   | €       | Calibrated     | Low        |
    | Forest Mammals monetary_rate  | 2,571,000 €   | €       | Calibrated     | Low        |
    | Raptors monetary_rate         | 3,000,000 €   | €       | Calibrated     | Low        |
    | Watershed monetary_rate       | 4,167,000 €   | €       | Calibrated     | Low        |
    | Carbon & Climate monetary_rate| 4,500,000 €   | €       | Calibrated     | Low        |
    | Human Communities monetary_rate| 8,333,000 €  | €       | Calibrated     | Low        |
    | logistic steepness            | 12.0          | –       | Placeholder   | Low        |
    | exponential base (carbon)     | 2.0           | –       | Placeholder   | Low        |
    | dependency weight sum         | 1.00          | –       | Verified ✓    | High       |

Monetary rate calibration:
    Rates are set so that sum(weight × rate) ≈ €3,500,000 (total effective max externality).
    This ensures:
        externality < revenue at safe threshold (25%):
            logistic_damage(0.25) ≈ 0.10 → 0.10 × €3.5M ≈ €350k < €375k revenue (6,250 trees × €60)
        externality > revenue at 50% depletion:
            logistic_damage(0.50) ≈ 0.76 → 0.76 × €3.5M ≈ €2.66M >> €300k revenue (5,000 trees × €60)

    Full destruction (10,000 trees @ €60 = €600k revenue) imposes ≈€3.5M in externalities.
    Ratio: 5.8× — every euro of timber revenue costs society ~€5.80. [User spec ✓]

Dependency weights sum: 0.12+0.08+0.13+0.10+0.10+0.08+0.07+0.04+0.12+0.10+0.06 = 1.00 ✓

CLI usage:
    python -m gaia.cases.costa_brava
    python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 4000
    python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 4000 --mode restore
"""

import argparse
import sys

from gaia.damage import exponential_damage, logistic_damage
from gaia.models import (
    Agent,
    CarbonProfile,
    Ecosystem,
    InteractionEdge,
    ResilienceConfig,
    RestorationCost,
    Resource,
    SuccessionCurve,
)
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

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
    carbon_price_per_tonne=80.0,
)

# v0.4: Costa Brava resilience configuration
_CB_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.12,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.50,
)

# Shared steepness for all logistic agents.
# 12.0 gives a clear S-curve with an observable knee at the threshold.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS: float = 12.0


def build_costa_brava_ecosystem(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.25,
    tree_value: float = 60.0,
) -> Ecosystem:
    """
    Build the Costa Brava Holm Oak Forest ecosystem with 11 agents.

    The ecosystem spans the full dependency web: underground mycorrhizal network,
    soil microbiome, understory vegetation, pollinators, birds, mammals, raptors,
    watershed, carbon cycle, and local human communities.

    Args:
        total_trees: Total number of trees in the forest. [PLACEHOLDER]
        safe_threshold_ratio: Fraction extractable before ecosystem stress accelerates.
            Default 0.25 — lower than temperate forests due to Mediterranean drought
            stress, slower regeneration, and fire feedback loops. [User spec, Medium]
        tree_value: Revenue per tree in euros. Default 60.0 — holm oak is less
            commercially valuable than northern timber species. Cork harvest would
            use a different economic model (no felling). [User spec, Medium]

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    resource = Resource(
        name="Costa Brava Holm Oak Forest",
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        carbon_profile=_CB_CARBON,
        resilience=_CB_RESILIENCE,
    )

    t = safe_threshold_ratio  # shorthand for threshold argument

    agents = [
        # ── Underground infrastructure ──────────────────────────────────────
        Agent(
            name="Mycorrhizal Fungi",
            dependency_weight=0.13,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_077_000.0,
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
            monetary_rate=3_500_000.0,
            description="Soil microbiome and biocrusts — nitrogen fixation, carbon storage, erosion prevention",
            # v0.3: Abiotic process agent
            trophic_level=-1,
        ),
        # ── Vegetation ──────────────────────────────────────────────────────
        Agent(
            name="Canopy Trees",
            dependency_weight=0.12,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=2_500_000.0,
            description="Remaining canopy trees — self-reinforcing decline from microclimate loss and network fragmentation",
            # v0.3: Producer — the resource itself
            trophic_level=0,
        ),
        Agent(
            name="Understory & Matorral",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=1_875_000.0,
            description="Understory shrubs and aromatic plants — microclimate collapse and biodiversity loss",
            # v0.3: Secondary producer
            trophic_level=0,
        ),
        # ── Invertebrates ───────────────────────────────────────────────────
        Agent(
            name="Pollinators & Insects",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_500_000.0,
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
            monetary_rate=2_500_000.0,
            description="Nesting and migratory stopover habitat — seed dispersal, insect control, ecotourism",
            # v0.3: Primary consumer (insects + seeds)
            trophic_level=1,
        ),
        Agent(
            name="Forest Mammals",
            dependency_weight=0.07,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=2_571_000.0,
            description="Habitat displacement — predator-prey disruption, human-wildlife conflict, crop damage",
            # v0.3: Primary consumer — herbivores and omnivores
            trophic_level=1,
        ),
        Agent(
            name="Raptors & Apex Predators",
            dependency_weight=0.04,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_000_000.0,
            description="Apex trophic control — carrion processing, extreme K-strategy vulnerability, trophic cascade trigger",
            # v0.3: Tertiary consumer — apex predator
            trophic_level=3,
        ),
        # ── Physical systems ────────────────────────────────────────────────
        Agent(
            name="Watershed & Water Cycle",
            dependency_weight=0.12,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=4_167_000.0,
            description="Aquifer recharge, flood control, drought buffering — Costa Brava water and tourism supply",
            # v0.3: Abiotic process
            trophic_level=-1,
        ),
        Agent(
            name="Carbon & Climate",
            dependency_weight=0.10,
            damage_function=exponential_damage(threshold=t, base=2.0),
            monetary_rate=4_500_000.0,
            description="CO₂ release, lost sequestration, fire risk amplification — exponential accumulation, no plateau",
            # v0.3: Abiotic process
            trophic_level=-1,
        ),
        # ── Human systems ───────────────────────────────────────────────────
        Agent(
            name="Human Communities",
            dependency_weight=0.06,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_333_000.0,
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

        # Carbon depends on living biomass
        InteractionEdge("Canopy Trees", "Carbon & Climate", 0.35, "dependency",
            "Tree loss directly reduces carbon sequestration capacity"),

        # Human communities depend on multiple services
        InteractionEdge("Watershed & Water Cycle", "Human Communities", 0.25, "dependency",
            "Water quality decline affects human health and tourism"),
        InteractionEdge("Carbon & Climate", "Human Communities", 0.10, "dependency",
            "Climate regulation loss increases fire risk and heat stress"),
    ]

    return Ecosystem(
        name="Costa Brava Holm Oak Forest",
        resource=resource,
        agents=agents,
        interactions=interactions,
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
    )
    return format_restoration_report(result)


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.2 — Costa Brava Holm Oak Forest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (25%):\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 2500\n\n"
            "  # Extraction — past threshold (40%):\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 4000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 4000 --mode restore\n"
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
        "--cut",
        type=int,
        default=4_000,
        metavar="N",
        help="Number of trees to cut/restore (default: 4000)",
    )
    parser.add_argument(
        "--tree-value",
        type=float,
        default=60.0,
        metavar="EUROS",
        help="Revenue per tree in euros (default: 60.0)",
    )
    parser.add_argument(
        "--mode",
        choices=["extract", "restore"],
        default="extract",
        help="Simulation mode: 'extract' (default) or 'restore'",
    )
    parser.add_argument(
        "--planting-cost",
        type=float,
        default=80.0,
        metavar="EUROS",
        help="[restore mode] Planting cost per tree in euros (default: 80.0)",
    )
    parser.add_argument(
        "--maintenance-cost",
        type=float,
        default=15.0,
        metavar="EUROS",
        help="[restore mode] Annual maintenance cost per tree in euros (default: 15.0)",
    )
    parser.add_argument(
        "--maintenance-years",
        type=int,
        default=15,
        metavar="N",
        help="[restore mode] Number of maintenance years (default: 15)",
    )
    parser.add_argument(
        "--time-horizon",
        type=int,
        default=0,
        metavar="YEARS",
        help="[restore mode] Years of maturation to simulate, v0.4 (default: 0=skip)",
    )
    return parser.parse_args(argv)


def main(argv: list = None) -> None:
    args = _parse_args(argv)
    try:
        if args.mode == "restore":
            report = run_costa_brava_restoration(
                total_trees=args.trees,
                safe_threshold_ratio=args.threshold,
                trees_to_restore=args.cut,
                tree_value=args.tree_value,
                planting_cost_per_tree=args.planting_cost,
                annual_maintenance_per_tree=args.maintenance_cost,
                maintenance_years=args.maintenance_years,
                time_horizon_years=args.time_horizon,
            )
        else:
            report = run_costa_brava(
                total_trees=args.trees,
                safe_threshold_ratio=args.threshold,
                trees_cut=args.cut,
                tree_value=args.tree_value,
            )
        print(report)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
