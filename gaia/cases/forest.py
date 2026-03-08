"""
Gaia v0.8.1 — Preconfigured Oak Valley Forest deforestation and restoration case.

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
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000 --mode restore
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000 --mode restore --time-horizon 60
    python -m gaia.cases.forest --trees 10000 --units 5000 --format json
"""

import argparse
import sys
import warnings

from gaia.cli import (
    add_common_arguments,
    add_restoration_arguments,
    handle_deprecated_alias,
    output_result,
    warn_unused_restoration_args,
)
from gaia.damage import logistic_damage
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

# v0.5: Oak Valley Forest substrate profile
# Temperate forest soil — deep, moderate erosion, slow formation.
# [PLACEHOLDER — pending calibration against regional soil survey data]
_OAK_VALLEY_SUBSTRATE = SubstrateProfile(
    substrate_type="terrestrial_soil",
    soil_depth_cm=45.0,
    water_availability_mm_yr=800.0,
    erosion_rate_unprotected=15.0,   # t/ha/yr — moderate for temperate forest
    erosion_rate_protected=0.5,      # t/ha/yr — minimal under full canopy
    formation_rate=0.8,              # t/ha/yr — ~0.06 mm/yr
    capacity_function="linear",
    erosion_alpha=2.0,
    confidence="medium",
)

# v0.6: Oak Valley discount configuration
# Ramsey formula: r = 0.005 + 1.35 × 0.013 ≈ 0.023
_OAK_VALLEY_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
)

# v0.7: Oak Valley pricing configuration
_OAK_VALLEY_PRICING = PricingConfig(
    anchors=[
        AnchorPoint(
            agent_name="General Biosphere",
            anchor_value=80000.0,
            source="EU ETS carbon price × estimated 1,000 t CO₂/yr sequestration",
            confidence="medium",
            description="Carbon: €80/t × 1,000 t CO₂/yr",
        ),
    ],
    scarcity_functions={
        "Human Communities": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Animal Populations": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Vegetation & Flora": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "General Biosphere": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)


def build_forest_ecosystem(
    total_trees: int = 10_000,
    safe_threshold_ratio: float = 0.3,
    tree_value: float = 100.0,
    with_pricing: bool = False,
) -> Ecosystem:
    """
    Build the Oak Valley Forest ecosystem with the four standard agents.

    Args:
        total_trees: Total number of trees in the forest. [PLACEHOLDER]
        safe_threshold_ratio: Fraction that can be safely extracted. [PLACEHOLDER]
        tree_value: Revenue per tree in euros. [PLACEHOLDER]
        with_pricing: If True, enable v0.7 endogenous pricing. Default False
            for backward compatibility with v0.1-v0.6 tests.

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
        substrate=_OAK_VALLEY_SUBSTRATE,
        discount=_OAK_VALLEY_DISCOUNT,
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
        pricing=_OAK_VALLEY_PRICING if with_pricing else None,
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
        description="Gaia v0.8.1 — Oak Valley Forest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction mode (default):\n"
            "  python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.forest --trees 10000 --units 5000 --mode restore\n\n"
            "  # JSON output:\n"
            "  python -m gaia.cases.forest --units 5000 --format json\n"
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
        "--units",
        type=int,
        default=5_000,
        metavar="N",
        help="Number of units to extract or restore (default: 5000)",
    )
    # Deprecated alias for --units
    parser.add_argument(
        "--cut", type=int, default=None, metavar="N",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--unit-value",
        type=float,
        default=100.0,
        metavar="EUROS",
        help="Revenue per unit extracted in euros (default: 100.0)",
    )
    # Deprecated alias for --unit-value
    parser.add_argument(
        "--tree-value", type=float, default=None, metavar="EUROS",
        help=argparse.SUPPRESS,
    )
    add_common_arguments(parser)
    add_restoration_arguments(
        parser,
        planting_cost_default=50.0,
        maintenance_cost_default=10.0,
        maintenance_years_default=10,
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
        ecosystem = build_forest_ecosystem(
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
                    _FOREST_SUCCESSION if args.time_horizon > 0 else None
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
