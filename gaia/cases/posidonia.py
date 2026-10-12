"""
Costa Brava Posidonia Meadow — compatibility wrapper (deprecated, removed in Gaia 0.11).

The case is the data file ``gaia/cases/data/posidonia.json`` (derivations:
``gaia/cases/definitions/CASE_NOTES.md``); run it with ``gaia run posidonia``
or ``gaia.cases.load_case("posidonia")``. This module keeps the 0.9 API for
one release: ``build_posidonia_ecosystem``, ``run_posidonia``, ``run_posidonia_restoration``,
the ``POSIDONIA_AREA_HA`` constant and ``main`` (``python -m gaia.cases.posidonia``
and ``gaia posidonia``, with the 0.9 flags: --hectares for --total-units,
deprecated --destroy / --revenue). Defaults come from the data file.
"""

from typing import List, Optional

from gaia.cases import load_case
from gaia.cli import LegacyCLI, case_main
from gaia.models import Ecosystem

CASE = load_case("posidonia")
POSIDONIA_AREA_HA: float = CASE.area_ha

_LEGACY = LegacyCLI(
    case="posidonia",
    total_units_flag="--hectares",
    total_units_help="Total hectares of Posidonia meadow",
    units_alias="--destroy",
    unit_value_alias="--revenue",
    labels={"unit_value": "--unit-value / revenue_per_hectare", "total_units": "--hectares / total_hectares"},
)


def build_posidonia_ecosystem(
    total_hectares: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    revenue_per_hectare: Optional[float] = None,
    with_pricing: bool = False,
    area_ha: Optional[float] = None,
) -> Ecosystem:
    """The Costa Brava Posidonia Meadow ecosystem (``CASE.build_ecosystem``); None = the data
    file's value.

    The unit is the hectare: ``area_ha``, if given, is the reference
    resource (e.g. the meadow a project affects) and sets the number of
    hectares; an explicit ``total_hectares`` must then equal it (ValueError
    otherwise)."""
    return CASE.build_ecosystem(
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
        area_ha=area_ha,
        with_pricing=with_pricing,
        labels=_LEGACY.labels,
    )


def run_posidonia(
    total_hectares: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    hectares_destroyed: Optional[int] = None,
    revenue_per_hectare: Optional[float] = None,
) -> str:
    """Text report of an extraction of ``hectares_destroyed`` units (default: the
    data file's run.units)."""
    return CASE.report(CASE.run_extraction(
        hectares_destroyed,
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
        labels=_LEGACY.labels,
    ))


def run_posidonia_restoration(
    total_hectares: Optional[int] = None,
    safe_threshold_ratio: Optional[float] = None,
    hectares_to_restore: Optional[int] = None,
    revenue_per_hectare: Optional[float] = None,
    planting_cost_per_hectare: Optional[float] = None,
    annual_maintenance_per_hectare: Optional[float] = None,
    maintenance_years: Optional[int] = None,
    time_horizon_years: int = 0,
    units_lost: Optional[int] = None,
) -> str:
    """Text report of a restoration of ``hectares_to_restore`` units (default: the
    data file's run.units) with the data file's restoration defaults; a
    maturation timeline when ``time_horizon_years`` > 0."""
    return CASE.report(CASE.run_restoration(
        hectares_to_restore,
        units_lost=units_lost,
        time_horizon_years=time_horizon_years,
        planting_cost_per_unit=planting_cost_per_hectare,
        annual_maintenance_per_unit=annual_maintenance_per_hectare,
        maintenance_years=maintenance_years,
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
        labels=_LEGACY.labels,
    ))


def main(argv: Optional[List[str]] = None) -> None:
    """``python -m gaia.cases.posidonia`` / ``gaia posidonia`` (deprecated)."""
    case_main(CASE, argv, legacy=_LEGACY)


if __name__ == "__main__":
    main()
