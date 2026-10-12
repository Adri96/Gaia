#!/usr/bin/env python3
"""
Profile the simulation engine: pure Python vs the Cython extraction loop
(decision D7, TOP_PRIORITIES_REPORT.md Step 7.4).

Runs each shipped case in-process (no CLI, no output formatting) and prints
a Markdown table of wall-clock times (best of --repeat runs):

    default      the case's default run (gaia run <case>), extract and
                 restore (restore: --units-lost = --units, the default)
    pricing      EXPERIMENTAL --with-pricing, extract only, below each
                 case's convergence limit (pricing always uses the Python
                 loop: the Cython loop has no price solver)
    sweep        full depletion (every unit) of a 100,000-unit resource,
                 fine steps (1 unit = 0.001%), extract

Usage:
    python3 scripts/profile_engine.py              # everything (minutes)
    python3 scripts/profile_engine.py --quick      # smaller sizes
    python3 scripts/profile_engine.py --hotspots   # cProfile of the slowest runs
"""

import argparse
import contextlib
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

import gaia.simulation as sim  # noqa: E402
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


@contextlib.contextmanager
def engine(name: str):
    saved = sim._HAS_CYTHON
    sim._HAS_CYTHON = saved if name == "cython" else False
    try:
        yield
    finally:
        sim._HAS_CYTHON = saved


def best_of(fn, repeat: int) -> float:
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


def runs(quick: bool):
    """(label, case, mode, total units, units, with_pricing)."""
    scale = 10 if quick else 1
    for name in CASE_NAMES:
        case = load_case(name)
        total = case.total_units.value // scale
        units = case.default_units // scale
        yield ("default", name, "extract", total, units, False)
        yield ("default", name, "restore", total, units, False)
    for name in CASE_NAMES:
        total, units = PRICING[name]
        yield ("pricing", name, "extract", total // scale, units // scale, True)
    for name in CASE_NAMES:
        n = SWEEP_UNITS // scale
        yield ("sweep", name, "extract", n, n, False)


def run_once(name: str, mode: str, total: int, units: int, with_pricing: bool):
    case = load_case(name)
    if mode == "extract":
        return case.run_extraction(units, total_units=total, with_pricing=with_pricing)
    return case.run_restoration(units, total_units=total)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--quick", action="store_true", help="1/10 of the sizes")
    parser.add_argument("--repeat", type=int, default=3, help="best of N (default 3)")
    parser.add_argument("--hotspots", action="store_true", help="cProfile the slowest runs")
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")

    if not sim._HAS_CYTHON:
        print("The Cython extension is not built or is stale: "
              "python3 setup.py build_ext --inplace", file=sys.stderr)
        return 1

    print(f"Python {platform.python_version()} on {platform.machine()} "
          f"({platform.system()}), best of {args.repeat}\n")
    print("| Run | Case | Mode | Units (of total) | Python (s) | Cython (s) | Python / Cython |")
    print("|---|---|---|---|---|---|---|")
    for label, name, mode, total, units, with_pricing in runs(args.quick):
        times = {}
        for eng in ("python", "cython"):
            with engine(eng):
                times[eng] = best_of(functools.partial(run_once, name, mode, total, units, with_pricing), args.repeat)
        ratio = times["python"] / times["cython"]
        print(f"| {label} | {name} | {mode} | {units:,} of {total:,} "
              f"| {times['python']:.3f} | {times['cython']:.3f} | {ratio:.1f}× |")
        sys.stdout.flush()

    if args.hotspots:
        scale = 10 if args.quick else 1
        for title, eng, call in (
            ("sweep amazon_forest, Python loop", "python",
             lambda: run_once("amazon_forest", "extract", SWEEP_UNITS // scale, SWEEP_UNITS // scale, False)),
            ("sweep amazon_forest, Cython loop", "cython",
             lambda: run_once("amazon_forest", "extract", SWEEP_UNITS // scale, SWEEP_UNITS // scale, False)),
            ("pricing amazon_forest", "python",
             lambda: run_once("amazon_forest", "extract", *(n // scale for n in PRICING["amazon_forest"]), True)),
        ):
            profiler = cProfile.Profile()
            with engine(eng):
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
