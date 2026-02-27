"""
Gaia v0.1 — Preconfigured Oak Valley Forest deforestation case.

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
"""

import argparse
import sys

from gaia.damage import logistic_damage
from gaia.models import Agent, Ecosystem, Resource
from gaia.report import format_report
from gaia.simulation import run_extraction


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
        ),
    ]

    return Ecosystem(
        name="Oak Valley Forest",
        resource=resource,
        agents=agents,
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


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.1 — Oak Valley Forest externality simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000"
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
        help="Number of trees to cut (default: 5000)",
    )
    parser.add_argument(
        "--tree-value",
        type=float,
        default=100.0,
        metavar="EUROS",
        help="Revenue per tree in euros (default: 100.0)",
    )
    return parser.parse_args(argv)


def main(argv: list = None) -> None:
    args = _parse_args(argv)
    try:
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
