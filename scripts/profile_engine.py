#!/usr/bin/env python3
"""
Profile the simulation engine (docs/ENGINE_PROFILE.md).

Since decision D5 (option B) the engine evaluates the static damage function
directly: a run computes its final state, and the per-step data are
evaluated only when asked for. This script runs each shipped case in-process
(no CLI, no output formatting) and prints a Markdown table of wall-clock
times (best of --repeat runs):

    summary      the run as the CLI's summary needs it (final state, NPVs,
                 the substrate trajectory)
    all steps    the same run, then every step evaluated once (what the
                 former per-unit loop always did, and what the golden
                 snapshots and --steps-every 1 still do)

for these runs:

    default      the case's default run (gaia run <case>), extract and
                 restore (restore: --units-lost = --units, the default)
    pricing      EXPERIMENTAL --with-pricing, extract only, below each
                 case's convergence limit (pricing certifies every step)
    sweep        full depletion (every unit) of a 100,000-unit resource,
                 fine steps (1 unit = 0.001%), extract

Usage:
    python3 scripts/profile_engine.py              # everything (about a minute)
    python3 scripts/profile_engine.py --quick      # smaller sizes
    python3 scripts/profile_engine.py --hotspots   # cProfile of the slowest runs
    python3 scripts/profile_engine.py --smoke      # tiny sizes, one repeat (a test runs it)
"""

import argparse
import cProfile
import functools
import io
import platform
import pstats
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gaia.cases import CASE_NAMES, load_case  # noqa: E402

# Pricing runs: (total units, units) below the depletion at which the price
# system stops converging (Costa Brava ~32.6%, Posidonia ~35.4%, Amazon
# ~22.3%; tests/golden_support.py).
PRICING = {
    "forest": (10_000, 5_000),
    "costa_brava": (10_000, 3_000),
    "posidonia": (5_000, 1_500),
    "amazon_forest": (40_000, 8_000),
}
SWEEP_UNITS = 100_000


def best_of(fn, repeat: int) -> float:
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


def runs(scale: int):
    """(label, case, mode, total units, units, with_pricing), sizes / scale."""
    for name in CASE_NAMES:
        case = load_case(name)
        total = max(case.total_units.value // scale, 2)
        units = max(case.default_units // scale, 1)
        yield ("default", name, "extract", total, units, False)
        yield ("default", name, "restore", total, units, False)
    for name in CASE_NAMES:
        total, units = PRICING[name]
        yield ("pricing", name, "extract", max(total // scale, 2), max(units // scale, 1), True)
    for name in CASE_NAMES:
        n = max(SWEEP_UNITS // scale, 2)
        yield ("sweep", name, "extract", n, n, False)


def run_once(name: str, mode: str, total: int, units: int, with_pricing: bool,
             all_steps: bool = False):
    case = load_case(name)
    if mode == "extract":
        result = case.run_extraction(units, total_units=total, with_pricing=with_pricing)
    else:
        result = case.run_restoration(units, total_units=total)
    if all_steps:
        for _ in result.steps:
            pass
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--quick", action="store_true", help="1/10 of the sizes")
    parser.add_argument("--smoke", action="store_true",
                        help="1/1000 of the sizes and one repeat: checks the script runs")
    parser.add_argument("--repeat", type=int, default=3, help="best of N (default 3)")
    parser.add_argument("--hotspots", action="store_true", help="cProfile the slowest runs")
    args = parser.parse_args(argv)
    if args.smoke:
        args.repeat = 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _profile(args)


def _profile(args: argparse.Namespace) -> int:
    scale = 1000 if args.smoke else 10 if args.quick else 1
    print(f"Python {platform.python_version()} on {platform.machine()} "
          f"({platform.system()}), best of {args.repeat}\n")
    print("| Run | Case | Mode | Units (of total) | Summary (s) | All steps (s) |")
    print("|---|---|---|---|---|---|")
    for label, name, mode, total, units, with_pricing in runs(scale):
        call = functools.partial(run_once, name, mode, total, units, with_pricing)
        summary = best_of(call, args.repeat)
        every = best_of(functools.partial(call, all_steps=True), args.repeat)
        print(f"| {label} | {name} | {mode} | {units:,} of {total:,} "
              f"| {summary:.3f} | {every:.3f} |")
        sys.stdout.flush()

    if args.hotspots:
        sweep = max(SWEEP_UNITS // scale, 2)
        p_total, p_units = (max(n // scale, k) for n, k in zip(PRICING["amazon_forest"], (2, 1)))
        for title, call in (
            ("sweep amazon_forest, summary",
             lambda: run_once("amazon_forest", "extract", sweep, sweep, False)),
            ("sweep amazon_forest, all steps",
             lambda: run_once("amazon_forest", "extract", sweep, sweep, False, True)),
            ("pricing amazon_forest",
             lambda: run_once("amazon_forest", "extract", p_total, p_units, True)),
        ):
            profiler = cProfile.Profile()
            profiler.runcall(call)
            out = io.StringIO()
            pstats.Stats(profiler, stream=out).sort_stats("tottime").print_stats(8)
            print(f"\n### Hotspots: {title}\n\n```text")
            lines = out.getvalue().splitlines()
            start = next(i for i, line in enumerate(lines) if "ncalls" in line)
            print("\n".join(line.rstrip() for line in lines[start:start + 9]))
            print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
