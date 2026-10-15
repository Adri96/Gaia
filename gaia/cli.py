"""
Gaia — the ``gaia`` command and its shared CLI utilities.

``gaia run <case | file.json> [options]`` (``run_main``) loads a case
document (gaia.cases.load_case), builds its parser with the case's defaults
(``build_case_parser``) and runs it (``run_case``). ``main`` is the ``gaia``
console script and ``python -m gaia``; it also forwards the deprecated
``gaia <case> [options]`` to the case's compatibility wrapper, which runs
the same code with the 0.9 flags (``LegacyCLI``). The rest is shared
argument definitions, deprecation handling and output routing (text vs
JSON).
"""

import argparse
import contextlib
import dataclasses
import functools
import sys
import warnings
from typing import Any, Callable, Dict, Iterator, List, Optional

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
        flags.append(option_string or self.option_strings[0])
        namespace.explicit_flags = flags
        dests = list(getattr(namespace, "explicit_dests", []))
        dests.append(self.dest)
        namespace.explicit_dests = dests


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be an integer >= 1, got {value}")
    return value


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments common to all case CLIs.

    Adds: --version, --mode, --format, --output, --with-pricing, --summary-only,
    --steps-every, --area-ha, --resource-name, --carbon-price,
    --carbon-release-fraction, --carbon-release-half-life.
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
            "extraction only (default: disabled). A few anchored agents "
            "determine every price; the others are derived through the "
            "placeholder edges and add no independent information. A step "
            "whose price system cannot be certified convergent stops the run "
            "with an error (no fallback values). Not an estimate"
        ),
    )
    parser.add_argument(
        "--area-ha",
        type=float,
        default=None,
        metavar="HA",
        help=(
            "Area of the reference resource in hectares (default: the case's; "
            "for a case counted in units, the number of units divided by its "
            "reference density). For a case counted in hectares (e.g. "
            "posidonia) it is the reference resource itself — e.g. the "
            "specific meadow a project affects instead of the regional stock — "
            "and sets the number of units (a case with site-restricted values, "
            "e.g. posidonia's diving value, then requires their inputs: "
            "--dive-intensity and/or --dive-site-share, as with --total-units). Agent values are €/ha/yr, so holding "
            "the area fixed while changing the number of units changes per-unit "
            "figures but not the per-ha externality"
        ),
    )
    parser.add_argument(
        "--resource-name",
        type=str,
        default=None,
        metavar="NAME",
        help=(
            "Name of the reference resource in the outputs, e.g. the meadow "
            "the project affects (default: the case's)"
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
        "--carbon-release-fraction",
        type=float,
        default=None,
        metavar="F",
        help=(
            "Project input: fraction (0-1) of the soil carbon stock the "
            "project releases, which depends on what it does to the soil or "
            "matte (default: the case's). Recommended for "
            "Posidonia matte: 0.96 if excavated or dredged (IPCC 2013), 0.25-1.0 "
            "(central 0.63) if left exposed (or use --matte-fate); see "
            "docs/POSIDONIA_LITERATURE_REVIEW.md §4"
        ),
    )
    parser.add_argument(
        "--carbon-release-half-life",
        type=float,
        default=None,
        metavar="YEARS",
        help=(
            "Project input: half-life of the release in years; 0 releases it all "
            "at extraction, a positive value spreads it as a negative "
            "exponential, each year valued at that year's carbon price and "
            "discounted (default: the case's). Recommended for Posidonia "
            "matte: 0 if excavated, about 10 (3-27) if left exposed; or use --matte-fate"
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


def add_fate_argument(parser: argparse.ArgumentParser, case) -> None:
    """Add ``--<subject>-fate`` (e.g. ``--matte-fate``) for a case whose
    carbon block defines release fates (Step 8d.2): a preset of
    --carbon-release-fraction and --carbon-release-half-life, explained in
    plain words in the help."""
    spec = getattr(case, "release_fates", None)
    if spec is None:
        return
    subject, default = spec["subject"], spec["default"]
    lines = []
    for name, fate in spec["fates"].items():
        half = fate["release_half_life_years"]
        timing = "all at once" if half == 0 else f"half-life {half:g} yr"
        lines.append(
            f"'{name}'{' (default)' if name == default else ''}: {fate['description']} "
            f"Releases {fate['soil_release_fraction']:g} of the {subject}'s carbon, {timing} "
            f"[{fate['basis']}]"
        )
    parser.add_argument(
        f"--{subject}-fate",
        dest="carbon_fate",
        choices=list(spec["fates"]),
        default=None,
        metavar="{" + ",".join(spec["fates"]) + "}",
        help=(
            f"Project input: what the project does to the {subject}, which sets how "
            f"much of its carbon is released and how fast (a preset of "
            f"--carbon-release-fraction and --carbon-release-half-life, which still "
            f"override it). " + " ".join(lines)
        ).replace("%", "%%"),
    )


def add_site_argument(parser: argparse.ArgumentParser, case) -> None:
    """Add ``--<input>`` (e.g. ``--dive-site-share``) for a case with
    site-restricted agent values (Step 8d.4)."""
    agents = getattr(case, "site_restricted_agents", [])
    if not agents:
        return
    share = case.default_site_share
    parser.add_argument(
        f"--{case.site_input}",
        dest="site_share",
        type=float,
        default=None,
        metavar="F",
        help=(
            f"Project input: the share (0-1) of the affected resource within reach "
            f"of {case.sites}. The site-restricted value of {', '.join(agents)} applies only "
            f"there (its other services apply everywhere, so the agent never falls to €0): "
            f"1 if the project affects only resource at or next to {case.sites}, 0 if it is "
            f"far from any (default {share:.4g}, the regional share, i.e. the expected "
            f"value for a site of unknown location; 1 when --{case.intensity_input or 'intensity'} "
            f"is given alone)"
        ).replace("%", "%%"),
    )
    add_intensity_argument(parser, case)


def add_intensity_argument(parser: argparse.ArgumentParser, case) -> None:
    """Add ``--<activity>-intensity`` (e.g. ``--dive-intensity``) for a case
    whose site-restricted agents define intensity levels (Step 8e.2),
    explained in plain words in the help."""
    levels = getattr(case, "intensity_levels", None)
    if not levels:
        return
    default = case.default_site_intensity
    unit = case.site_intensity_unit
    near = sum(a.weight * a.site_value for a in case.agents if a.site_share is not None)
    lines = []
    for name, level in levels.items():
        lines.append(
            f"'{name}': {level['description']} [{level['value']:,.0f} {unit}: about "
            f"€{near * level['value'] / default:,.0f}/ha/yr near the {case.sites}]"
        )
    parser.add_argument(
        f"--{case.intensity_input}",
        dest="site_intensity",
        choices=list(levels),
        default=None,
        metavar="{" + ",".join(levels) + "}",
        help=(
            f"Project input: how intensely the affected resource near {case.sites} is used, "
            f"in {unit}. It sets the value per hectare near the {case.sites} (the documented "
            f"value × level / default; 'none' zeroes that service only, never an agent); "
            f"--{case.site_input} sets the share of the affected "
            f"resource near them (1 when only --{case.intensity_input} is given). Default: "
            f"the regional average, {default:,.1f} {unit} (about €{near:,.0f}/ha/yr near the "
            f"{case.sites}). Levels: " + " ".join(lines)
        ).replace("%", "%%"),
    )


def parse_depth(text: str):
    """``--depth-m``: one depth ("12") or a range ("5-20"), in metres;
    returns (from_m, to_m)."""
    parts = text.replace("–", "-").split("-")
    try:
        if len(parts) == 1:
            value = float(parts[0])
            depths = (value, value)
        elif len(parts) == 2:
            depths = (float(parts[0]), float(parts[1]))
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"a depth in metres (e.g. 12) or a range (e.g. 5-20), got {text!r}") from None
    if not all(d == d and d >= 0 for d in depths) or depths[0] > depths[1]:
        raise argparse.ArgumentTypeError(f"depths are >= 0 m and a range is low-high, got {text!r}")
    return depths


def add_depth_argument(parser: argparse.ArgumentParser, case) -> None:
    """Add ``--depth-m`` for a case with a depth-dependent production
    function (Step 8g.1), explained in plain words in the help."""
    block = getattr(case, "depth_production", None)
    if not block:
        return
    table = ", ".join(f"{v:,.0f} at {z} m" for z, v in block["npp_at_depth"].items())
    unit = block["unit"].replace("DW", "dry weight")
    limit = block["hyperparameters"]["depth_limit"]
    margin = block["depth_limit_margin"]["value"]
    span = f", {limit['range'][0]:g}-{limit['range'][1]:g} m in the uncertainty analysis" if limit.get("range") else ""
    deepest = (limit.get("range") or [limit["value"], limit["value"]])[1]
    beyond = (f". Beyond {deepest:g} m, the deepest limit documented, the value is an extrapolation: "
              f"still computed (> €0), with a warning")
    # Step 8i.1: a depth whose implied site limit (+ the margin) passes it
    implied = (f"{beyond}; also from {deepest - margin:g} m down (exclusive), whose implied site limit "
               f"(+ {margin:g} m) passes it")
    parser.add_argument(
        "--depth-m",
        dest="depth_m",
        type=parse_depth,
        default=None,
        metavar="M or LOW-HIGH",
        help=(
            f"Project input: the water depth of the affected {block['agent']}, in metres: one "
            f"depth (e.g. 12) or a range (e.g. 5-20: spread evenly over it). "
            f"Its primary production, and so the food it supports, falls with depth as light fades: "
            f"about {table} {unit}. Default: {block['depth_label']}. Any depth is valued: production "
            f"reaches zero at the depth limit ({limit['value']:g} m{span}), and a meadow that lives at "
            f"the depth given proves its site's limit lies deeper, so the limit is taken at least "
            f"{margin:g} m below the deepest depth given (never valued at €0){implied}"
        ).replace("%", "%%"),
    )
    parser.add_argument(
        "--depth-limit-m",
        dest="depth_limit_m",
        type=parse_depth,
        default=None,
        metavar="M or LOW-HIGH",
        help=(
            f"Project input: the site's own depth limit, where the {block['agent']} ends (its "
            f"production reaches zero), in metres: one depth (e.g. 15) or a range (e.g. 13-17). "
            f"Water clarity varies: meadows end at about 15 m in turbid water (Medes Islands) and "
            f"reach 44 m in the clearest. It replaces the regional limit ({limit['value']:g} m{span}); "
            f"the depth given with --depth-m (default: {block['depth_label']}) must be shallower{beyond}"
        ).replace("%", "%%"),
    )


def apply_depth(case, args: argparse.Namespace):
    """The case at the project's depth (``--depth-m``) and the site's depth
    limit (``--depth-limit-m``, Step 8g.10; without ``--depth-m`` at the
    regional mean depth), or the case itself.

    Raises:
        ValueError: A site's depth limit without a project depth when the
            regional depth is a distribution, not a mean.
    """
    depth = getattr(args, "depth_m", None)
    limit = getattr(args, "depth_limit_m", None)
    if depth is None and limit is None:
        return case
    if depth is not None:
        return case.with_project_depth(*depth, depth_limit=limit)
    bands = case.depth_production["regional_depth"]["bands"]
    if len(bands) != 1 or bands[0]["from_m"] != bands[0]["to_m"]:
        raise ValueError("--depth-limit-m needs the meadow's depth too: give --depth-m")
    try:
        return case.with_project_depth(bands[0]["from_m"], bands[0]["to_m"], depth_limit=limit)
    except ValueError as exc:
        raise ValueError(f"{exc} (without --depth-m the meadow is taken at the regional mean depth, "
                         f"{bands[0]['from_m']:g} m)") from None


SIZE_DESTS: tuple = ("area_ha", "total_units")
"""The options that set the size of the reference resource: --area-ha,
--total-units and a legacy case's own flag for it (Posidonia's
--hectares)."""


def require_site_input(case, args: argparse.Namespace) -> None:
    """A project run must state the diving input (Steps 8e.3, 8g.5).

    With --area-ha, --total-units or (the legacy) --hectares the user sets
    the size of a specific project resource (e.g. the meadow a project
    affects), whose site share and intensity the regional averages do not
    describe; a case with site-restricted values (Posidonia: the meadow's
    diving value) then needs --<site>-share and/or --<activity>-intensity.
    The default regional run keeps its defaults.

    Raises:
        ValueError: With a plain message, when neither is given.
    """
    if not getattr(case, "site_restricted_agents", []):
        return
    given = [f for f, d in zip(getattr(args, "explicit_flags", []), getattr(args, "explicit_dests", []))
             if d in SIZE_DESTS]
    if getattr(args, "area_ha", None) is not None:
        given.insert(0, "--area-ha")
    if not given:
        return
    if getattr(args, "site_share", None) is not None or getattr(args, "site_intensity", None) is not None:
        return
    intensity = case.intensity_input
    levels = case.intensity_levels or {}
    site = case.sites[:-1] if case.sites.endswith("s") else case.sites
    options = (
        f"--{intensity} {{{','.join(levels)}}} (how intensely the resource near the "
        f"{case.sites} is used) and/or " if intensity else ""
    )
    nothing = f"--{intensity} none" if "none" in levels else f"--{case.site_input} 0"
    flag = given[0]
    raise ValueError(
        f"with {flag} (a specific project site), the {case.sites} input is required: "
        f"{options}--{case.site_input} F (the share, 0 to 1, of the affected resource "
        f"within reach of {case.sites}). If no {site} is within reach, give {nothing}. "
        f"Without {flag} the run uses the regional averages."
    )


def add_uncertainty_arguments(parser: argparse.ArgumentParser) -> None:
    """Add --uncertainty [N] and --seed (Step 8.4, gaia.uncertainty)."""
    from gaia.uncertainty import DEFAULT_DRAWS, DEFAULT_SEED

    parser.add_argument(
        "--uncertainty",
        type=_positive_int,
        nargs="?",
        const=DEFAULT_DRAWS,
        default=None,
        metavar="N",
        help=(
            f"[extract mode] Monte Carlo over the case's parameter ranges: "
            f"P5/P50/P95 of the headline numbers, a sensitivity ranking and the "
            f"normative choices (N draws, default {DEFAULT_DRAWS:,} when given "
            f"without N; about 4 s per 1,000 draws for Posidonia, 4 min for the "
            f"default 80,000-tree Amazon run)"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        metavar="S",
        help=f"[with --uncertainty] Seed of the random generator (default {DEFAULT_SEED})",
    )


def _uncertainty(case, args: argparse.Namespace, labels: Optional[Dict[str, str]]):
    """The Monte Carlo of an extraction run (None unless --uncertainty)."""
    draws = getattr(args, "uncertainty", None)
    if draws is None:
        return None
    if args.mode != "extract":
        warnings.warn("--uncertainty applies to extraction only. Ignored in restore mode.",
                      UserWarning, stacklevel=2)
        return None
    if args.with_pricing:
        raise ValueError("--uncertainty cannot be combined with --with-pricing (EXPERIMENTAL)")
    if draws < 2:
        raise ValueError(f"--uncertainty needs at least 2 draws, got {draws}")
    from gaia.uncertainty import run_uncertainty

    overrides: Dict[str, Any] = {
        "total_units": args.total_units, "unit_value": args.unit_value,
        "area_ha": args.area_ha, "labels": labels,
        "resource_name": getattr(args, "resource_name", None),
        "carbon_release_fraction": getattr(args, "carbon_release_fraction", None),
        "carbon_release_half_life": getattr(args, "carbon_release_half_life", None),
        "carbon_fate": getattr(args, "carbon_fate", None),
        "site_share": getattr(args, "site_share", None),
        "site_intensity": getattr(args, "site_intensity", None),
    }
    if args.threshold != case.safe_threshold_ratio.value:
        overrides["safe_threshold_ratio"] = args.threshold
    return run_uncertainty(
        case, args.units, build_kwargs=overrides,
        prepare=lambda eco: apply_carbon_price_view(eco, args.carbon_price),
        draws=draws, seed=args.seed,
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
    extra: Optional[Dict[str, Any]] = None,
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
        extra: Optional top-level JSON blocks (benchmarks, uncertainty).

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
            extra=extra,
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


# ── Running a case ────────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class LegacyCLI:
    """The 0.9 command line of a case module (deprecated, for one release).

    Attributes:
        case: The case name, e.g. "forest".
        total_units_flag: The flag for the number of units, e.g. "--trees".
        total_units_help: Its help text.
        units_alias: Deprecated alias of --units, e.g. "--cut".
        unit_value_alias: Deprecated alias of --unit-value, e.g. "--tree-value".
        labels: Provenance labels of user-supplied values
            (gaia.ecosystem_io.DEFAULT_LABELS keys), as in 0.9.
    """

    case: str
    total_units_flag: str
    total_units_help: str
    units_alias: str
    unit_value_alias: str
    labels: Dict[str, str]


def build_case_parser(case, prog: str, legacy: Optional[LegacyCLI] = None) -> argparse.ArgumentParser:
    """The argument parser of a case, with the case's defaults.

    Args:
        case: A gaia.ecosystem_io.Case.
        prog: Program name shown in usage, e.g. "gaia run forest".
        legacy: The 0.9 flags of a compatibility wrapper (``--trees`` /
            ``--hectares`` and the deprecated aliases), or None for
            ``gaia run`` (``--total-units``).
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=f"Gaia {__version__} — {case.name}: externality (extract) and restoration (restore) simulation",
        epilog=(
            f"Case document: {case.origin}. Run 'gaia --help' for the shipped cases."
            if legacy is None else
            f"Deprecated: use 'gaia run {legacy.case}' (same options; "
            f"{legacy.total_units_flag} is --total-units). Removed in Gaia 0.11."
        ),
    )
    total = case.total_units.value
    if legacy is None:
        parser.add_argument(
            "--total-units", action=_RecordFlag, type=int, default=total, metavar="N",
            help=(
                f"Total number of units ({case.unit}) in the reference resource "
                f"(default: {total})"
                + (f"; a project's own size, so it then requires --{case.intensity_input or case.site_input} "
                   f"and/or --{case.site_input} (the {case.sites} input)" if case.site_restricted_agents else "")
            ),
        )
    else:
        parser.add_argument(
            legacy.total_units_flag, dest="total_units", action=_RecordFlag, type=int, default=total, metavar="N",
            help=f"{legacy.total_units_help} (default: {total})"
            + (f"; it then requires --{case.intensity_input or case.site_input} and/or --{case.site_input}"
               if case.site_restricted_agents else ""),
        )
    parser.add_argument(
        "--threshold", type=float, default=case.safe_threshold_ratio.value, metavar="RATIO",
        help=(
            f"Safe extraction threshold ratio, 0.0 < threshold < 1.0 "
            f"(default: {case.safe_threshold_ratio.value:g})"
        ),
    )
    parser.add_argument(
        "--units", type=int, default=case.default_units, metavar="N",
        help=f"Number of units to extract or restore (default: {case.default_units})",
    )
    parser.add_argument(
        "--unit-value", type=float, default=case.unit_value.value, metavar="EUROS",
        help=f"Revenue per unit extracted in euros, one-off (default: {case.unit_value.value:g})",
    )
    if legacy is not None:
        parser.add_argument(legacy.units_alias, dest="units_alias", type=int, default=None,
                            metavar="N", help=argparse.SUPPRESS)
        parser.add_argument(legacy.unit_value_alias, dest="unit_value_alias", type=float,
                            default=None, metavar="EUROS", help=argparse.SUPPRESS)
    add_common_arguments(parser)
    add_fate_argument(parser, case)
    add_site_argument(parser, case)
    add_depth_argument(parser, case)
    add_uncertainty_arguments(parser)
    defaults = case.restoration_defaults()
    add_restoration_arguments(
        parser,
        planting_cost_default=defaults["planting_cost_per_unit"],
        maintenance_cost_default=defaults["annual_maintenance_per_unit"],
        maintenance_years_default=defaults["maintenance_years"],
    )
    return parser


def parse_case_args(
    case,
    argv: Optional[List[str]] = None,
    legacy: Optional[LegacyCLI] = None,
    prog: Optional[str] = None,
) -> argparse.Namespace:
    """Parse a case command line (see build_case_parser); resolves the
    deprecated aliases of a legacy command line with a FutureWarning."""
    if prog is None:
        prog = f"gaia {legacy.case}" if legacy is not None else "gaia run"
    args = build_case_parser(case, prog, legacy).parse_args(argv)
    if legacy is not None:
        handle_deprecated_alias(args, "units_alias", "units", legacy.units_alias, "--units")
        handle_deprecated_alias(args, "unit_value_alias", "unit_value", legacy.unit_value_alias, "--unit-value")
    return args


def run_case(case, args: argparse.Namespace, labels: Optional[Dict[str, str]] = None) -> None:
    """Build the case's ecosystem from parsed arguments, run it, output it.

    Raises:
        SystemExit: (status 1, "Error: ..." on stderr) on a ValueError.
    """
    from gaia.simulation import run_extraction, run_restoration

    warn_unused_restoration_args(args)
    drop_pricing_in_restore_mode(args)
    try:
        case = apply_depth(case, args)
        # Step 8h.2: beyond the deepest documented depth limit, valued with a warning
        depth_warnings = case.depth_warnings() if hasattr(case, "depth_warnings") else []
        for message in depth_warnings:
            from gaia.production import DepthExtrapolationWarning

            warnings.warn(message, DepthExtrapolationWarning, stacklevel=2)
        ecosystem = case.build_ecosystem(
            total_units=args.total_units,
            safe_threshold_ratio=args.threshold,
            unit_value=args.unit_value,
            with_pricing=args.with_pricing,
            area_ha=args.area_ha,
            labels=labels,
            resource_name=getattr(args, "resource_name", None),
            carbon_release_fraction=getattr(args, "carbon_release_fraction", None),
            carbon_release_half_life=getattr(args, "carbon_release_half_life", None),
            carbon_fate=getattr(args, "carbon_fate", None),
            site_share=getattr(args, "site_share", None),
            site_intensity=getattr(args, "site_intensity", None),
        )
        require_site_input(case, args)
        apply_carbon_price_view(ecosystem, args.carbon_price)
        result: Any
        if args.mode == "restore":
            cost = case.restoration_cost(
                planting_cost_per_unit=args.planting_cost,
                annual_maintenance_per_unit=args.maintenance_cost,
                maintenance_years=args.maintenance_years,
            )
            ecosystem.provenance.extend(case.restoration_provenance(cost, args.time_horizon > 0))
            result = run_restoration(
                ecosystem, args.units, cost, case.recovery_functions(ecosystem),
                units_lost=args.units_lost,
                succession_curve=case.succession_curve if args.time_horizon > 0 else None,
                time_horizon_years=args.time_horizon,
            )
        else:
            result = run_extraction(ecosystem, args.units)
        from gaia.uncertainty import format_uncertainty, uncertainty_to_dict

        uncertainty = _uncertainty(case, args, labels)
        text_report = case.report(result, appendix=format_uncertainty(uncertainty))
        extra = {
            # Step 8e.6: the primary production → food → € chains
            "production_functions": case.production_functions() or None,
            "benchmarks": case.benchmark_block(result),
            "uncertainty": uncertainty_to_dict(uncertainty),
            # Step 8h.2: the depth extrapolation warnings, also on stderr
            "warnings": list(depth_warnings) or None,
        }
        output_result(text_report, result, args, notes=list(case.json_notes) or None,
                      extra=extra)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


@cli_entry
def case_main(
    case,
    argv: Optional[List[str]] = None,
    legacy: Optional[LegacyCLI] = None,
    prog: Optional[str] = None,
) -> None:
    """Run a case from a command line (``gaia run`` or a legacy wrapper).

    A legacy command line warns (FutureWarning) that it is deprecated.
    """
    if legacy is not None:
        warnings.warn(
            f"'gaia {legacy.case}' and 'python -m gaia.cases.{legacy.case}' are "
            f"deprecated and will be removed in Gaia 0.11; use 'gaia run "
            f"{legacy.case}' (same options; {legacy.total_units_flag} is --total-units)",
            FutureWarning,
            stacklevel=2,
        )
    args = parse_case_args(case, argv, legacy, prog)
    run_case(case, args, legacy.labels if legacy is not None else None)


# ── The ``gaia`` command ──────────────────────────────────────────────────────

_RUN_USAGE = (
    "usage: gaia run <case | file.json> [options]\n"
    "       gaia run <case | file.json> --help\n"
)


def _usage() -> str:
    from gaia.cases import CASE_ALIASES, CASE_NAMES

    aliases = ", ".join(f"{a} = {n}" for a, n in CASE_ALIASES.items())
    return (
        _RUN_USAGE
        + "       gaia --version\n"
        "\n"
        f"Cases: {', '.join(CASE_NAMES)} (aliases: {aliases}),\n"
        "or the path of a case document (JSON; see gaia/ecosystem_io.py).\n"
        "\n"
        "Deprecated (removed in Gaia 0.11): gaia <case> [options] and\n"
        "python -m gaia.cases.<case> [options], with the 0.9 flags.\n"
    )


def _exit_status(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return 1


def run_main(argv: Optional[List[str]] = None) -> int:
    """``gaia run <case | file.json> [options]``. Returns the exit status
    (2 for a missing or unknown case, as argparse does)."""
    from gaia.cases import load_case

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_usage(), end="")
        return 0 if args else 2
    spec = args[0]
    try:
        case = load_case(spec)
    except ValueError as exc:
        print(_RUN_USAGE, end="", file=sys.stderr)
        print(f"gaia run: error: {exc}", file=sys.stderr)
        return 2
    try:
        case_main(case, args[1:], prog=f"gaia run {spec}")
    except SystemExit as exc:
        return _exit_status(exc)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point of ``gaia`` and ``python -m gaia``.

    ``gaia run <case | file.json> [options]`` runs a case. The deprecated
    ``gaia <case> [options]`` forwards to the compatibility wrapper
    ``gaia.cases.<case>.main``. Returns the exit status (0 on success; 2
    for an unknown command or case, as argparse does).
    """
    import importlib

    from gaia.cases import resolve_case_name

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_usage(), end="")
        return 0 if args else 2
    if args[0] == "--version":
        print(f"Gaia {__version__}")
        return 0
    if args[0] == "run":
        return run_main(args[1:])
    name = resolve_case_name(args[0])
    if name is None:
        print(_usage(), end="", file=sys.stderr)
        print(f"gaia: error: unknown command or case {args[0]!r}", file=sys.stderr)
        return 2
    module = importlib.import_module(f"gaia.cases.{name}")
    try:
        module.main(args[1:])
    except SystemExit as exc:
        return _exit_status(exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
