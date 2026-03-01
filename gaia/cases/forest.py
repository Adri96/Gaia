"""
Gaia v0.4 — Preconfigured Oak Valley Forest deforestation and restoration case.

Provides a ready-to-run forest ecosystem with four agents, all using logistic
damage functions calibrated around the safe extraction threshold.

All parameters are PLACEHOLDERS pending scientific review. They are designed
to be in a plausible ballpark for a medium-sized temperate deciduous forest,
but are not calibrated against specific published studies.

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    | Parameter               | Value         | Unit       | Source       | Confidence |
    |-------------------------|---------------|------------|--------------|------------|
    | total_units             | configurable  | trees      | Placeholder  | Low        |
    | safe_threshold_ratio    | configurable  | ratio      | Placeholder  | Low        |
    | unit_value              | 100.0 €/tree  | €/tree     | Placeholder  | Low        |
    | Human monetary_rate     | 750,000 €     | €          | Placeholder  | Low        |
    | Animal monetary_rate    | 1,167,000 €   | €          | Placeholder  | Low        |
    | Vegetation monetary_rate| 1,000,000 €   | €          | Placeholder  | Low        |
    | Biosphere monetary_rate | 1,571,000 €   | €          | Placeholder  | Low        |
    | logistic steepness      | 12.0          | dimensionless | Placeholder | Low      |
    | dependency weights      | 0.20/0.30/... | ratio      | Placeholder  | Low        |

Total effective max externality sum(weight × rate) ≈ €1,200,000
Monetary rates calibrated so that:
    - externality < revenue at safe threshold (30%): 21.5% × €1.2M ≈ €258k < €300k revenue
    - externality > revenue at 50% depletion: 75.6% × €1.2M ≈ €907k > €500k revenue
Dependency weight sum: 0.20 + 0.30 + 0.15 + 0.35 = 1.00

CLI usage:
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000 --mode restore
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000 --mode restore --time-horizon 60
"""

import argparse
import sys

from gaia.damage import logistic_damage
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


# v0.4: Oak Valley Forest succession curve
# [PLACEHOLDER — pending calibration against temperate oak succession studies]
_FOREST_SUCCESSION = SuccessionCurve(
    pioneer_end_year=8.0,
    intermediate_end_year=25.0,
    climax_approach_year=60.0,
    pioneer_service=0.05,
    intermediate_service=0.35,
    maturation_delay=2.0,
)

# v0.4: Oak Valley carbon profile (per tree)
# [PLACEHOLDER — pending calibration against IPCC forest carbon data]
_FOREST_CARBON = CarbonProfile(
    stored_carbon_tonnes=0.8,
    annual_absorption_tonnes=0.022,
    soil_carbon_tonnes=0.3,
    soil_release_fraction=0.25,
    carbon_price_per_tonne=80.0,
)

# v0.4: Oak Valley resilience configuration
_FOREST_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.10,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.60,
)


def build_forest_ecosystem(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.3,
    tree_value: float = 100.0,
) -> Ecosystem:
    """
    Build the Oak Valley Forest ecosystem with the four standard agents.

    Args:
        total_trees: Total number of trees in the forest. [PLACEHOLDER]
        safe_threshold_ratio: Fraction that can be safely extracted. [PLACEHOLDER]
        tree_value: Revenue per tree in euros. [PLACEHOLDER]

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    resource = Resource(
        name="Oak Valley Forest",
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        carbon_profile=_FOREST_CARBON,
        resilience=_FOREST_RESILIENCE,
    )

    # Logistic damage functions centered at the safe extraction threshold.
    # Steepness of 12.0 gives a clear S-curve with an observable knee.
    # All thresholds match the resource threshold (agents degrade together).
    # [PLACEHOLDER — each agent may have a different threshold in future versions]
    steepness: float = 12.0
    fn_logistic = logistic_damage(threshold=safe_threshold_ratio, steepness=steepness)

    agents = [
        Agent(
            name="Human Communities",
            dependency_weight=0.20,
            # Separate function instance per agent (same parameters, same closure)
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            monetary_rate=750_000.0,
            # Effective max contribution (weight × rate): 0.20 × €750k = €150k
            # [PLACEHOLDER — health costs, water treatment, lost recreation]
            # Calibration: sum(weight × rate) ≈ €1.2M, ensuring:
            #   externality < revenue at safe threshold (30%), and
            #   externality > revenue at 50% depletion.
            description="Health costs, water treatment, lost recreation",
            # v0.3: External beneficiary — not in trophic chain
            trophic_level=-1,
        ),
        Agent(
            name="Animal Populations",
            dependency_weight=0.30,
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            monetary_rate=1_167_000.0,
            # Effective max: 0.30 × €1,167k = €350k
            # [PLACEHOLDER — habitat, biodiversity, species loss valuation]
            description="Habitat loss, population decline, species loss",
            # v0.3: Primary consumer — herbivores, omnivores
            trophic_level=1,
        ),
        Agent(
            name="Vegetation & Flora",
            dependency_weight=0.15,
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            monetary_rate=1_000_000.0,
            # Effective max: 0.15 × €1,000k = €150k
            # [PLACEHOLDER — soil erosion, pollination network disruption]
            description="Soil erosion, pollination network disruption",
            # v0.3: Producer — the forest vegetation itself
            trophic_level=0,
        ),
        Agent(
            name="General Biosphere",
            dependency_weight=0.35,
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            monetary_rate=1_571_000.0,
            # Effective max: 0.35 × €1,571k = €550k
            # [PLACEHOLDER — carbon release, watershed, climate impact]
            description="Carbon release, watershed degradation, climate impact",
            # v0.3: Abiotic service — not in trophic chain
            trophic_level=-1,
        ),
    ]

    # v0.3: Minimal interaction edges for the simple forest case
    interactions = [
        InteractionEdge(
            "Vegetation & Flora", "Animal Populations", 0.20, "dependency",
            "Vegetation loss reduces food and habitat for animals",
        ),
        InteractionEdge(
            "Animal Populations", "Human Communities", 0.10, "dependency",
            "Wildlife decline reduces ecosystem health indicators",
        ),
    ]

    return Ecosystem(
        name="Oak Valley Forest",
        resource=resource,
        agents=agents,
        interactions=interactions,
    )


def run_forest(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.3,
    trees_cut: int = 5_000,
    tree_value: float = 100.0,
) -> str:
    """
    Run the Oak Valley Forest deforestation simulation and return the report.

    Args:
        total_trees: Total number of trees in the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_cut: Number of trees to cut (extract).
        tree_value: Revenue per tree in euros.

    Returns:
        Formatted text report string.
    """
    ecosystem = build_forest_ecosystem(
        total_trees=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        tree_value=tree_value,
    )
    result = run_extraction(ecosystem, trees_cut)
    return format_report(result)


def run_forest_restoration(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.3,
    trees_to_restore: int = 5_000,
    tree_value: float = 100.0,
    planting_cost_per_tree: float = 50.0,
    annual_maintenance_per_tree: float = 10.0,
    maintenance_years: int = 10,
    time_horizon_years: int = 0,
) -> str:
    """
    Run the Oak Valley Forest restoration simulation and return the report.

    Models replanting from a degraded state. Default restores 5,000 trees —
    half the forest — using logistic recovery functions (slower than logistic
    damage, encoding the entropy asymmetry of destruction vs. restoration).

    v0.4: When time_horizon_years > 0, produces maturation timeline using
    the Oak Valley succession curve.

    Args:
        total_trees: Total carrying capacity of the forest.
        safe_threshold_ratio: Safe extraction threshold ratio.
        trees_to_restore: Number of trees to replant (restore).
        tree_value: Revenue per tree in euros (used for prevention_advantage).
        planting_cost_per_tree: Direct cost per tree planted.
        annual_maintenance_per_tree: Annual maintenance cost per tree.
        maintenance_years: Number of years of maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).

    Returns:
        Formatted text restoration report string.
    """
    ecosystem = build_forest_ecosystem(
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
        succession_curve=_FOREST_SUCCESSION if time_horizon_years > 0 else None,
        time_horizon_years=time_horizon_years,
    )
    return format_restoration_report(result)


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.2 — Oak Valley Forest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction mode (default):\n"
            "  python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000 --mode restore\n"
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
        default=0.3,
        metavar="RATIO",
        help="Safe extraction threshold ratio, 0.0 < threshold < 1.0 (default: 0.3)",
    )
    parser.add_argument(
        "--cut",
        type=int,
        default=5_000,
        metavar="N",
        help="Number of trees to cut/restore (default: 5000)",
    )
    parser.add_argument(
        "--tree-value",
        type=float,
        default=100.0,
        metavar="EUROS",
        help="Revenue per tree in euros (default: 100.0)",
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
        default=50.0,
        metavar="EUROS",
        help="[restore mode] Planting cost per tree in euros (default: 50.0)",
    )
    parser.add_argument(
        "--maintenance-cost",
        type=float,
        default=10.0,
        metavar="EUROS",
        help="[restore mode] Annual maintenance cost per tree in euros (default: 10.0)",
    )
    parser.add_argument(
        "--maintenance-years",
        type=int,
        default=10,
        metavar="N",
        help="[restore mode] Number of maintenance years (default: 10)",
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
            report = run_forest_restoration(
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
            report = run_forest(
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
