#!/usr/bin/env python3
"""
Regenerate (or check) the golden snapshot files in tests/golden/.

Golden files freeze current model outputs. Regenerate them deliberately,
and explain in the commit message which numbers changed and why. A file
is rewritten only when its snapshot differs from the stored one beyond the
comparison tolerance (tests/golden_support.py: rel 1e-9), so float noise in
the last digit (another libm, a compiler's fused multiply-add) never
rewrites it.

Usage:
    python3 scripts/regen_golden.py                    # regenerate all
    python3 scripts/regen_golden.py forest posidonia   # only these cases
    python3 scripts/regen_golden.py forest__restore    # only this scenario
    python3 scripts/regen_golden.py --check            # compare, write nothing
    python3 scripts/regen_golden.py --list             # list scenarios
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.golden_support import (  # noqa: E402
    CASES,
    GOLDEN_DIR,
    SCENARIOS,
    build_snapshot,
    compare,
    dumps,
    golden_path,
    load_golden,
)


def _select(targets):
    if not targets:
        return list(SCENARIOS)
    selected = []
    for t in targets:
        if t in SCENARIOS:
            selected.append(t)
        elif t in CASES:
            selected.extend(n for n, (c, _) in SCENARIOS.items() if c == t)
        else:
            raise SystemExit(
                f"Unknown case or scenario {t!r}. "
                f"Cases: {', '.join(CASES)}. Use --list for scenarios."
            )
    return list(dict.fromkeys(selected))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", metavar="CASE_OR_SCENARIO")
    parser.add_argument("--check", action="store_true",
                        help="Compare against existing files; write nothing")
    parser.add_argument("--list", action="store_true", help="List scenarios")
    args = parser.parse_args(argv)

    if args.list:
        for name, (case, cli) in SCENARIOS.items():
            print(f"{name:34s} {case:14s} {' '.join(cli)}")
        return 0

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name in _select(args.targets):
        snapshot = build_snapshot(name)
        path = golden_path(name)
        if args.check:
            if not path.exists():
                print(f"MISSING  {name}")
                failures += 1
                continue
            diffs = compare(load_golden(name), snapshot)
            print(f"{'OK      ' if not diffs else 'DIFF    '} {name}")
            for d in diffs[:20]:
                print(f"    {d}")
            failures += bool(diffs)
            continue
        if path.exists() and not compare(load_golden(name), snapshot):
            # Same numbers within the comparison tolerance: keep the file
            # byte for byte, so last-digit float noise never churns it.
            print(f"{'unchanged':9s} {path.relative_to(ROOT)}")
            continue
        status = "UPDATED" if path.exists() else "new"
        path.write_text(dumps(snapshot), encoding="utf-8")
        print(f"{status:9s} {path.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
