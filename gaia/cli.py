"""
Gaia — Shared CLI utilities and the ``gaia`` command.

Provides common argument definitions used across all case files,
deprecation handling, and output routing (text vs JSON), plus ``main``:
the ``gaia`` console script and ``python -m gaia``, a thin dispatcher
``gaia <case> [args]`` that forwards to the case module's ``main(argv)``.
"""

import argparse
import contextlib
import functools
import sys
import warnings
from typing import Any, Callable, Iterator, List, Optional

from gaia import __version__

# JSON output drops per-step data by default above this many steps (the
# default Amazon run has 80,000 steps, ~169 MB of JSON); --steps-every N
# includes every Nth step instead.
MAX_JSON_STEPS: int = 10_000

# The restoration-only flags, in the order add_restoration_arguments adds them
RESTORATION_FLAGS: tuple = (
    "--units-lost",
    "--planting-cost",
    "--maintenance-cost",
    "--maintenance-years",
    "--time-horizon",
)


class _RecordFlag(argparse.Action):
    """Store the value and record that the flag was given on the command line.

    The flag is appended to ``namespace.explicit_flags``, so a warning about
    an unused flag depends on the parsed arguments, not on ``sys.argv`` (it
    works when ``main(argv)`` is called from code).
    """

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        flags = list(getattr(namespace, "explicit_flags", []))
        flags.append(self.option_strings[0])
        namespace.explicit_flags = flags


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be an integer >= 1, got {value}")
    return value


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments common to all case CLIs.

    Adds: --version, --mode, --format, --output, --with-pricing, --summary-only,
    --steps-every, --area-ha, --carbon-price.
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
        help=(
            "EXPERIMENTAL, quarantined (C8): v0.7 endogenous pricing, "
            "extraction only (default: disabled). Every agent must be "
            "anchored; a step whose price system cannot be certified "
            "convergent stops the run with an error (no fallback values). "
            "Not an estimate"
        ),
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
    parser.add_argument(
        "--steps-every",
        type=_positive_int,
        default=None,
        metavar="N",
        help=(
            f"[json format] Include every Nth step (and the last) in the JSON "
            f"output; 1 = all steps. Default: all steps up to "
            f"{MAX_JSON_STEPS:,}, none (summary only, with a warning) above"
        ),
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
        action=_RecordFlag,
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
        action=_RecordFlag,
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
        action=_RecordFlag,
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
        action=_RecordFlag,
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
        action=_RecordFlag,
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
    new_flag: str,
) -> None:
    """Resolve a deprecated CLI alias (one implementation for every case).

    If the old attribute was explicitly set (is not None), copy its value
    to the new attribute and warn, naming both flags. The category is
    FutureWarning, Python's category for deprecations aimed at end users
    (DeprecationWarning is hidden by default outside ``__main__``).
    """
    old_val = getattr(args, old_attr, None)
    if old_val is not None:
        warnings.warn(
            f"{old_flag} is deprecated, use {new_flag} instead",
            FutureWarning,
            stacklevel=3,
        )
        setattr(args, new_attr, old_val)


def warn_unused_restoration_args(args: argparse.Namespace) -> None:
    """Warn for each restoration-only flag given in extraction mode.

    Reads the flags recorded in the parsed namespace (``explicit_flags``,
    see _RecordFlag), so it is correct whatever ``sys.argv`` holds.
    """
    if args.mode != "extract":
        return
    given = set(getattr(args, "explicit_flags", []))
    for flag in RESTORATION_FLAGS:
        if flag in given:
            warnings.warn(
                f"{flag} is only used in restore mode (--mode restore). "
                f"Ignored in extraction mode.",
                UserWarning,
                stacklevel=2,
            )


def drop_pricing_in_restore_mode(args: argparse.Namespace) -> None:
    """Ignore --with-pricing in restore mode, with a warning.

    Restoration values services at static agent values; endogenous prices
    would only be solved for the starting extraction and never used.
    """
    if args.mode == "restore" and args.with_pricing:
        warnings.warn(
            "--with-pricing applies to extraction only (restoration uses "
            "static agent values). Ignored in restore mode.",
            UserWarning,
            stacklevel=2,
        )
        args.with_pricing = False


def output_result(
    text_report: str,
    result_obj,
    args: argparse.Namespace,
    notes: Optional[List[str]] = None,
) -> None:
    """Output the result in the requested format.

    JSON per-step data: all steps by default; with ``--steps-every N``
    every Nth step and the last; none with ``--summary-only``, or by
    default (with a warning) when there are more than MAX_JSON_STEPS steps.

    Args:
        text_report: Pre-formatted text report string.
        result_obj: SimulationResult or RestorationResult.
        args: Parsed CLI arguments (needs output_format, output,
            summary_only; steps_every is optional).
        notes: Optional annotation strings for JSON output.

    Raises:
        SystemExit: (status 1, clean message) if ``--output`` cannot be
            written.
    """
    if args.output_format == "json":
        from gaia.serialization import to_json
        include_steps: bool = not args.summary_only
        steps_every: Optional[int] = getattr(args, "steps_every", None)
        n_steps: int = len(result_obj.steps)
        if include_steps and steps_every is None and n_steps > MAX_JSON_STEPS:
            warnings.warn(
                f"{n_steps:,} steps: per-step data omitted from the JSON output "
                f"(more than {MAX_JSON_STEPS:,}). Use --steps-every N to include "
                f"every Nth step (--steps-every 1 for all of them).",
                UserWarning,
                stacklevel=2,
            )
            include_steps = False
        output = to_json(
            result_obj,
            include_steps=include_steps,
            notes=notes,
            steps_every=steps_every or 1,
        )
    else:
        output = text_report

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
                f.write("\n")
        except OSError as exc:
            reason = exc.strerror or str(exc)
            sys.exit(f"Error: cannot write --output {args.output!r}: {reason}")
    else:
        print(output)


def _format_user_warning(message, category, filename, lineno, line=None) -> str:
    """One line per warning for CLI users: no file name, line or source."""
    return f"Warning ({category.__name__}): {message}\n"


@contextlib.contextmanager
def user_facing_warnings() -> Iterator[None]:
    """Format warnings for end users while a CLI command runs.

    Replaces ``warnings.formatwarning`` (restored on exit) so a warning
    prints as ``Warning (CalibrationWarning): ...`` without the source
    location and line. Only the case CLIs use it (via ``cli_entry``);
    library callers keep Python's default formatting. Warnings recorded by
    ``warnings.catch_warnings(record=True)`` (e.g. pytest.warns) are
    unaffected.
    """
    saved = warnings.formatwarning
    warnings.formatwarning = _format_user_warning
    try:
        yield
    finally:
        warnings.formatwarning = saved


def cli_entry(main_fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for a case's ``main(argv)``: runs it with user_facing_warnings."""

    @functools.wraps(main_fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with user_facing_warnings():
            return main_fn(*args, **kwargs)

    return wrapper


# ── The ``gaia`` command ──────────────────────────────────────────────────────

# Case name on the command line → module in gaia.cases (each has main(argv)).
CASES = {
    "forest": "forest",
    "costa_brava": "costa_brava",
    "posidonia": "posidonia",
    "amazon_forest": "amazon_forest",
}
_CASE_ALIASES = {
    "costa-brava": "costa_brava",
    "amazon": "amazon_forest",
    "amazon-forest": "amazon_forest",
}

_USAGE = (
    "usage: gaia <case> [options]\n"
    "       gaia <case> --help\n"
    "       gaia --version\n"
    "\n"
    "Cases: " + ", ".join(CASES) + "\n"
    "\n"
    "Each case takes the same options as python -m gaia.cases.<case>.\n"
)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point of ``gaia`` and ``python -m gaia``: ``gaia <case> [args]``.

    Forwards ``args`` to ``gaia.cases.<case>.main``. Returns the exit
    status (0 on success; 2 for an unknown case, as argparse does).
    """
    import importlib

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE, end="")
        return 0 if args else 2
    if args[0] == "--version":
        print(f"Gaia {__version__}")
        return 0
    name = _CASE_ALIASES.get(args[0], args[0])
    if name not in CASES:
        print(_USAGE, end="", file=sys.stderr)
        print(f"gaia: error: unknown case {args[0]!r}", file=sys.stderr)
        return 2
    module = importlib.import_module(f"gaia.cases.{CASES[name]}")
    try:
        module.main(args[1:])
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
