"""
Oak Valley Forest — compatibility wrapper (deprecated, removed in Gaia 0.11).

The case is the data file ``gaia/cases/data/forest.json`` (derivations:
``gaia/cases/definitions/CASE_NOTES.md``); run it with ``gaia run forest``
or ``gaia.cases.load_case("forest")``. This module keeps the 0.9 API for
one release: ``build_forest_ecosystem``, ``run_forest``, ``run_forest_restoration``,
the ``FOREST_TOTAL_TREES`` / ``FOREST_AREA_HA`` / ``FOREST_TREES_PER_HA`` constants and ``main`` (``python -m gaia.cases.forest``
and ``gaia forest``, with the 0.9 flags: --trees for --total-units,
deprecated --cut / --tree-value). Defaults come from the data file.
"""

from typing import List, Optional

from gaia.cases import load_case
from gaia.cli import LegacyCLI, case_main
from gaia.models import Ecosystem

CASE = load_case("forest")
FOREST_TOTAL_TREES: int = CASE.total_units.value
FOREST_AREA_HA: float = CASE.area_ha
FOREST_TREES_PER_HA: float = CASE.units_per_ha

_LEGACY = LegacyCLI(
    case="forest",
    total_units_flag="--trees",
    total_units_help="Total number of trees in the forest",
    units_alias="--cut",
    unit_value_alias="--tree-value",
    labels={"unit_value": "--unit-value / tree_value"},
)


def build_forest_ecosystem(
    total_trees: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    tree_value: Optional[float] = None,
    with_pricing: bool = False,
    area_ha: Optional[float] = None,
) -> Ecosystem:
    """The Oak Valley Forest ecosystem (``CASE.build_ecosystem``); None = the data
    file's value.

    ``area_ha`` defaults to the number of trees at the reference density;
    hold it fixed to vary the number of trees without changing the per-ha
    result."""
    return CASE.build_ecosystem(
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        area_ha=area_ha,
        with_pricing=with_pricing,
        labels=_LEGACY.labels,
    )


def run_forest(
    total_trees: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    trees_cut: Optional[int] = None,
    tree_value: Optional[float] = None,
) -> str:
    """Text report of an extraction of ``trees_cut`` units (default: the
    data file's run.units)."""
    return CASE.report(CASE.run_extraction(
        trees_cut,
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        labels=_LEGACY.labels,
    ))


def run_forest_restoration(
    total_trees: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    trees_to_restore: Optional[int] = None,
    tree_value: Optional[float] = None,
    planting_cost_per_tree: Optional[float] = None,
    annual_maintenance_per_tree: Optional[float] = None,
    maintenance_years: Optional[int] = None,
    time_horizon_years: int = 0,
    units_lost: Optional[int] = None,
) -> str:
    """Text report of a restoration of ``trees_to_restore`` units (default: the
    data file's run.units) with the data file's restoration defaults; a
    maturation timeline when ``time_horizon_years`` > 0."""
    return CASE.report(CASE.run_restoration(
        trees_to_restore,
        units_lost=units_lost,
        time_horizon_years=time_horizon_years,
        planting_cost_per_unit=planting_cost_per_tree,
        annual_maintenance_per_unit=annual_maintenance_per_tree,
        maintenance_years=maintenance_years,
        total_units=total_trees,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=tree_value,
        labels=_LEGACY.labels,
    ))


def main(argv: Optional[List[str]] = None) -> None:
    """``python -m gaia.cases.forest`` / ``gaia forest`` (deprecated)."""
    case_main(CASE, argv, legacy=_LEGACY)


if __name__ == "__main__":
    main()
