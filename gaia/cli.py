"""
Gaia v0.8.1 — Shared CLI utilities.

Provides common argument definitions used across all case files,
deprecation handling, and output routing (text vs JSON).
"""

import argparse
import sys
import warnings
from typing import List, Optional

from gaia import __version__


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments common to all case CLIs.

    Adds: --version, --mode, --format, --output, --with-pricing, --summary-only,
    --area-ha, --carbon-price.
    """
    parser.add_argument(
        "--version",
        action="version",
        version=f"Gaia {__version__}",
    )
    parser.add_argument(
        "--mode",
        choices=["extract", "restore"],
        default="extract",
        help="Simulation mode: 'extract' (default) or 'restore'",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format: 'text' (default) or 'json'",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--with-pricing",
        action="store_true",
        default=False,
        help="Enable v0.7 endogenous pricing (default: disabled)",
    )
    parser.add_argument(
        "--area-ha",
        type=float,
        default=None,
        metavar="HA",
        help=(
            "Area of the resource in hectares (default: the number of units "
            "divided by the case's reference density). Agent values are "
            "€/ha/yr, so holding the area fixed while changing the number of "
            "units changes per-unit figures but not the per-ha externality"
        ),
    )
    parser.add_argument(
        "--carbon-price",
        choices=["scc", "ets"],
        default="scc",
        help=(
            "Carbon price: 'scc' (default), the social cost of carbon "
            "(US EPA 2023, ~€166/t CO₂); 'ets', the market/ETS view "
            "(EU ETS, €80/t), a private price that understates the damage"
        ),
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        default=False,
        help="[json format] Omit per-step data from JSON output",
    )


def add_restoration_arguments(
    parser: argparse.ArgumentParser,
    planting_cost_default: float = 50.0,
    maintenance_cost_default: float = 10.0,
    maintenance_years_default: int = 10,
) -> None:
    """Add restoration-specific arguments with case-specific defaults.

    Adds: --units-lost, --planting-cost, --maintenance-cost,
    --maintenance-years, --time-horizon.
    """
    parser.add_argument(
        "--units-lost",
        type=int,
        default=None,
        metavar="N",
        help=(
            "[restore mode] Units missing before restoring: the starting "
            "state is the pristine resource with N units extracted. "
            "--units (the units restored) may not exceed it "
            "(default: same as --units, i.e. restore what was cut)"
        ),
    )
    parser.add_argument(
        "--planting-cost",
        type=float,
        default=planting_cost_default,
        metavar="EUROS",
        help=(
            f"[restore mode] Planting cost per unit in euros "
            f"(default: {planting_cost_default})"
        ),
    )
    parser.add_argument(
        "--maintenance-cost",
        type=float,
        default=maintenance_cost_default,
        metavar="EUROS",
        help=(
            f"[restore mode] Annual maintenance cost per unit in euros "
            f"(default: {maintenance_cost_default})"
        ),
    )
    parser.add_argument(
        "--maintenance-years",
        type=int,
        default=maintenance_years_default,
        metavar="N",
        help=(
            f"[restore mode] Number of maintenance years "
            f"(default: {maintenance_years_default})"
        ),
    )
    parser.add_argument(
        "--time-horizon",
        type=int,
        default=0,
        metavar="YEARS",
        help="[restore mode] Years of maturation to simulate (default: 0=skip)",
    )


def apply_carbon_price_view(ecosystem, view: str) -> None:
    """Set the carbon price of ``ecosystem`` to the named view, in place.

    ``"scc"`` leaves the ecosystem unchanged (every shipped DiscountConfig
    already uses the social cost of carbon). ``"ets"`` replaces the
    resource's DiscountConfig (or DEFAULT_DISCOUNT) by a copy priced at the
    market/ETS view (gaia.carbon.with_carbon_price_view).
    """
    if view == "scc":
        return
    import dataclasses

    from gaia.carbon import with_carbon_price_view
    from gaia.discount import DEFAULT_DISCOUNT

    resource = ecosystem.resource
    discount = resource.discount if resource.discount is not None else DEFAULT_DISCOUNT
    ecosystem.resource = dataclasses.replace(
        resource, discount=with_carbon_price_view(discount, view)
    )


def handle_deprecated_alias(
    args: argparse.Namespace,
    old_attr: str,
    new_attr: str,
    old_flag: str,
) -> None:
    """Resolve a deprecated CLI alias.

    If the old attribute was explicitly set (is not None), copy its value
    to the new attribute and emit a deprecation warning.
    """
    old_val = getattr(args, old_attr, None)
    if old_val is not None:
        warnings.warn(
            f"{old_flag} is deprecated, use --units instead",
            DeprecationWarning,
            stacklevel=3,
        )
        setattr(args, new_attr, old_val)


def warn_unused_restoration_args(args: argparse.Namespace) -> None:
    """Emit warnings when restoration-only args are passed in extraction mode."""
    if args.mode != "extract":
        return
    restoration_flags = [
        "--units-lost",
        "--planting-cost",
        "--maintenance-cost",
        "--maintenance-years",
        "--time-horizon",
    ]
    argv_str = " ".join(sys.argv)
    for flag in restoration_flags:
        if flag in argv_str:
            warnings.warn(
                f"{flag} is only used in restore mode (--mode restore). "
                f"Ignored in extraction mode.",
                UserWarning,
                stacklevel=2,
            )


def output_result(
    text_report: str,
    result_obj,
    args: argparse.Namespace,
    notes: Optional[List[str]] = None,
) -> None:
    """Output the result in the requested format.

    Args:
        text_report: Pre-formatted text report string.
        result_obj: SimulationResult or RestorationResult.
        args: Parsed CLI arguments (needs output_format, output, summary_only).
        notes: Optional annotation strings for JSON output.
    """
    if args.output_format == "json":
        from gaia.serialization import to_json
        output = to_json(
            result_obj,
            include_steps=not args.summary_only,
            notes=notes,
        )
    else:
        output = text_report

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
    else:
        print(output)
