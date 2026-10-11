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
    | reference area          | 40            | ha         | Placeholder  | Low        |
    | tree density            | 250           | trees/ha   | Placeholder  | Low        |
    | safe_threshold_ratio    | configurable  | ratio      | Placeholder  | Low        |
    | unit_value              | 100.0 €/tree  | €/tree     | Placeholder  | Low        |
    | annual_value_per_ha     | 2,848         | €/ha/yr    | de Groot 2012| Low        |
    |   (every agent)         |               |            |              |            |
    | logistic steepness      | 12.0          | dimensionless | Placeholder | Low      |
    | dependency weights      | 0.20/0.30/... | ratio      | Placeholder  | Low        |

Agent values are yearly flows per hectare (decisions D1, D2): every agent
uses the biome-level value below, and the dependency weights split it, so
sum(weight × value) = €2,848/ha/yr × area_ha at full damage
(€113,920/yr for the 40 ha reference forest).

The value is the order of magnitude of global meta-analyses for temperate
forests: de Groot et al. (2012), Ecosystem Services 1:50-61, Int$3,013/ha/yr
(2007 price level); Costanza et al. (2014), Global Environmental Change
26:152-158, $3,137/ha/yr (2007) — both figures to be re-checked against the
papers in Step 8. It is used at face value as €; currency and price-year
conversion, and a site-specific value, are pending (Step 8).
Carbon is valued only by gaia.carbon (decision D3), so the climate-regulation
service is taken out of the biome total: de Groot et al. (2012, supporting
material, Table 8.1, temperate forests) put it at Int$152/ha/yr, hence
€3,000 − €152 = €2,848/ha/yr. Rates are never tuned to produce an outcome
(an earlier version was back-solved so that externality < revenue at 30% and
> revenue at 50%).

Dependency weight sum: 0.20 + 0.30 + 0.15 + 0.35 = 1.00

Calibration regime: B, direct effects only (CalibrationRegime.DIRECT_ONLY;
PROJECT_DEFINITION.md, "Critical Modelling Assumption"):
    The four damage curves are the same placeholder logistic (steepness 12,
    inflection just past the safe threshold), not fitted to field data on
    total impact, so Option A — curves that already embed the indirect
    pathways — cannot be claimed. The curves are read as each agent's direct
    dependency on the forest, and the two interaction edges add the indirect
    part. B is what an uncalibrated curve implies, not a claim of lab or
    first-principles calibration. Incoming strengths are at most 0.20,
    within the in-degree cap of 1.0 (Step 3.8).

    Health at the 30% safe threshold is below 0.8 (≈0.73), so validation
    issues a CalibrationWarning. That is honest and has nothing to do with
    the edges (≈0.75 without them): the logistic alone puts ~21% direct
    damage at the threshold and trophic amplification multiplies it for
    Animal Populations. Fixing it means calibrating the curves (Step 8), not
    tuning parameters to silence the warning.

CLI usage:
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000 --mode restore
    python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000 --mode restore --time-horizon 60
    python -m gaia.cases.forest --trees 10000 --units 5000 --units-lost 8000 --mode restore
    python -m gaia.cases.forest --trees 10000 --units 5000 --format json
"""

import argparse
import sys
from typing import List, Optional, Union

from gaia.cli import (
    add_common_arguments,
    add_restoration_arguments,
    apply_carbon_price_view,
    drop_pricing_in_restore_mode,
    handle_deprecated_alias,
    output_result,
    warn_unused_restoration_args,
)
from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    AnchorPoint,
    CalibrationRegime,
    CarbonProfile,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    PricingConfig,
    ResilienceConfig,
    Resource,
    RestorationCost,
    RestorationResult,
    ScarcityFunction,
    SimulationResult,
    SubstrateProfile,
    SuccessionCurve,
)
from gaia.pricing import anchor_every_agent, scale_anchors
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

# ── Reference area ───────────────────────────────────────────────────────────
# [PLACEHOLDER] 10,000 trees on 40 ha = 250 trees/ha, so the per-tree carbon
# below gives ~200 t CO₂/ha in biomass and ~5.5 t CO₂/ha/yr absorption —
# plausible for a mature temperate deciduous stand. Without an explicit area,
# a forest of N trees covers N / FOREST_TREES_PER_HA hectares.
FOREST_TOTAL_TREES: int = 10_000
FOREST_AREA_HA: float = 40.0
FOREST_TREES_PER_HA: float = FOREST_TOTAL_TREES / FOREST_AREA_HA

# € / ha / yr of service lost at full damage, every agent (see module
# docstring): the de Groot (2012) temperate-forest total without its climate
# regulation (carbon) component, €3,000 − €152 [PLACEHOLDER].
_FOREST_VALUE_PER_HA_YR: float = 3_000.0 - 152.0


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
    # (mean annual precipitation ~800 mm/yr; not used by the model)
    erosion_rate_unprotected=15.0,   # t/ha/yr — moderate for temperate forest
    erosion_rate_protected=0.5,      # t/ha/yr — minimal under full canopy
    formation_rate=0.8,              # t/ha/yr — ~0.06 mm/yr
    capacity_function="linear",
    erosion_alpha=2.0,
    confidence="medium",
)

# v0.6: Oak Valley discount configuration
# Ramsey formula: r = 0.005 + 1.35 × 0.013 ≈ 0.023. Carbon price: the
# DiscountConfig default, the social cost of carbon (gaia.carbon).
_OAK_VALLEY_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    horizon_years=100,
)

# v0.7: Oak Valley pricing configuration (EXPERIMENTAL, decision D4). Anchor
# values are €/yr for the FOREST_AREA_HA reference forest and are scaled with
# area_ha by the builder. Only the water supply anchor is documented; the
# builder anchors every other agent at its own direct annual service value,
# annual_value_per_ha × area_ha (gaia.pricing.anchor_every_agent) [PLACEHOLDER].
_OAK_VALLEY_PRICING = PricingConfig(
    anchors=[
        # The former carbon anchor (€80/t × 1,000 t/yr) is gone: carbon is
        # valued only by gaia.carbon (decision D3).
        AnchorPoint(
            agent_name="Watershed & Local Climate",
            anchor_value=7_640.0,
            source="de Groot et al. 2012, temperate forests, (fresh) water supply Int$191/ha/yr × 40 ha",
            confidence="low",
            description="Water supply: €191/ha/yr × 40 ha [PLACEHOLDER]",
        ),
    ],
    scarcity_functions={
        "Human Communities": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Animal Populations": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Vegetation & Flora": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Watershed & Local Climate": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)


def build_forest_ecosystem(
    total_trees: int = FOREST_TOTAL_TREES,
    safe_threshold_ratio: float = 0.3,
    tree_value: float = 100.0,
    with_pricing: bool = False,
    area_ha: Optional[float] = None,
) -> Ecosystem:
    """
    Build the Oak Valley Forest ecosystem with the four standard agents.

    Args:
        total_trees: Total number of trees in the forest. [PLACEHOLDER]
        safe_threshold_ratio: Fraction that can be safely extracted. [PLACEHOLDER]
        tree_value: Revenue per tree in euros. [PLACEHOLDER]
        with_pricing: If True, enable the EXPERIMENTAL v0.7 endogenous
            pricing (every agent anchored). Default False.
        area_ha: Forest area in hectares. Default: total_trees at the
            reference density (FOREST_TREES_PER_HA). Hold it fixed to vary
            the number of trees without changing the per-ha result.

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    if area_ha is None:
        area_ha = total_trees / FOREST_TREES_PER_HA
    resource = Resource(
        name="Oak Valley Forest",
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        area_ha=area_ha,
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

    agents = [
        Agent(
            name="Human Communities",
            dependency_weight=0.20,
            # Separate function instance per agent (same parameters, same closure)
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            annual_value_per_ha=_FOREST_VALUE_PER_HA_YR,
            # [PLACEHOLDER — health costs, water treatment, lost recreation]
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
            annual_value_per_ha=_FOREST_VALUE_PER_HA_YR,
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
            annual_value_per_ha=_FOREST_VALUE_PER_HA_YR,
            # [PLACEHOLDER — soil erosion, pollination network disruption]
            description="Soil erosion, pollination network disruption",
            # v0.3: Producer — the forest vegetation itself
            trophic_level=0,
        ),
        Agent(
            name="Watershed & Local Climate",
            dependency_weight=0.35,
            damage_function=logistic_damage(
                threshold=safe_threshold_ratio, steepness=steepness
            ),
            annual_value_per_ha=_FOREST_VALUE_PER_HA_YR,
            # [PLACEHOLDER — watershed, local climate; formerly "General
            # Biosphere", whose carbon component is now valued by gaia.carbon]
            description="Watershed degradation, loss of local cooling and humidity regulation",
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
        calibration_regime=CalibrationRegime.DIRECT_ONLY,
        pricing=(
            anchor_every_agent(
                scale_anchors(_OAK_VALLEY_PRICING, area_ha / FOREST_AREA_HA), agents, area_ha
            )
            if with_pricing else None
        ),
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
    units_lost: Optional[int] = None,
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
        tree_value: Revenue per tree in euros (the foregone revenue).
        planting_cost_per_tree: Direct cost per tree planted.
        annual_maintenance_per_tree: Annual maintenance cost per tree.
        maintenance_years: Number of years of maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).
        units_lost: Units missing before restoring (default: the units
            restored, i.e. restore what was cut).

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
        units_lost=units_lost,
    )
    return format_restoration_report(result)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.8.1 — Oak Valley Forest externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction mode (default):\n"
            "  python -m gaia.cases.forest --trees 10000 --threshold 0.3 --units 5000\n\n"
            "  # Restoration mode (replant the 5000 trees that were cut):\n"
            "  python -m gaia.cases.forest --trees 10000 --units 5000 --mode restore\n\n"
            "  # Replant 5000 of 8000 trees lost:\n"
            "  python -m gaia.cases.forest --trees 10000 --units 5000 --units-lost 8000 --mode restore\n\n"
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
    handle_deprecated_alias(args, "cut", "units", "--cut", "--units")
    handle_deprecated_alias(args, "tree_value", "unit_value", "--tree-value", "--unit-value")
    return args


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    warn_unused_restoration_args(args)
    drop_pricing_in_restore_mode(args)
    try:
        ecosystem = build_forest_ecosystem(
            total_trees=args.trees,
            safe_threshold_ratio=args.threshold,
            tree_value=args.unit_value,
            with_pricing=args.with_pricing,
            area_ha=args.area_ha,
        )
        apply_carbon_price_view(ecosystem, args.carbon_price)
        result: Union[SimulationResult, RestorationResult]
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
            restored = run_restoration(
                ecosystem, args.units, cost, recovery_fns,
                units_lost=args.units_lost,
                succession_curve=(
                    _FOREST_SUCCESSION if args.time_horizon > 0 else None
                ),
                time_horizon_years=args.time_horizon,
            )
            text_report = format_restoration_report(restored)
            result = restored
        else:
            extracted = run_extraction(ecosystem, args.units)
            text_report = format_report(extracted)
            result = extracted
        output_result(text_report, result, args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
