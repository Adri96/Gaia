#!/usr/bin/env python3
"""
Regenerate the example outputs in README.md from the code, so they cannot
drift (audit finding D1).

Every generated block sits between markers:

    <!-- BEGIN:example name="forest-extract" cmd="gaia forest" -->
    ...generated...
    <!-- END:example -->

Attributes of the BEGIN marker:
    cmd    — a ``gaia <case> [args]`` command; its stdout is the block
             (warnings, printed on stderr, are not part of it).
    json   — with a ``--format json`` cmd: comma-separated dotted paths;
             only those keys are shown (e.g. "calibration.statement,summary").
    until  — optional text: keep the output up to (not including) the first
             line that contains it (an excerpt; the block says so).
    table  — "cases": a Markdown table of the four cases' default runs.

Usage:
    python3 scripts/gen_readme_examples.py           # rewrite README.md
    python3 scripts/gen_readme_examples.py --check   # exit 1 if it is stale
"""

import argparse
import contextlib
import io
import json
import re
import shlex
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
sys.path.insert(0, str(ROOT))

_BLOCK = re.compile(
    r"(<!-- BEGIN:example (?P<attrs>[^>]*?) -->\n)(?P<body>.*?)(<!-- END:example -->)",
    re.DOTALL,
)
_ATTR = re.compile(r'(\w+)="([^"]*)"')

# Case → (gaia command, label) for the cases table: each case's default run.
TABLE_CASES = [
    ("forest", "Oak Valley Forest (temperate)"),
    ("costa_brava", "Costa Brava Holm Oak Forest (Mediterranean)"),
    ("posidonia", "Costa Brava Posidonia Meadow (marine)"),
    ("amazon_forest", "Central Amazon (tropical)"),
]


def run_gaia(command: str) -> str:
    """stdout of ``gaia <case> [args]``, run in-process."""
    from gaia.cli import main

    args = shlex.split(command)
    if not args or args[0] != "gaia":
        raise ValueError(f"cmd must start with 'gaia': {command!r}")
    buf = io.StringIO()
    with warnings.catch_warnings(), contextlib.redirect_stdout(buf):
        warnings.simplefilter("ignore")
        status = main(args[1:])
    if status:
        raise RuntimeError(f"{command!r} exited with status {status}")
    return buf.getvalue().rstrip("\n")


def _select(data: Dict[str, Any], paths: List[str]) -> Dict[str, Any]:
    """The keys at the dotted ``paths`` of ``data``, nested as in ``data``."""
    out: Dict[str, Any] = {}
    for path in paths:
        keys = path.split(".")
        src: Any = data
        dst = out
        for key in keys[:-1]:
            src = src[key]
            dst = dst.setdefault(key, {})
        dst[keys[-1]] = src[keys[-1]]
    return out


def _cases_table() -> str:
    rows = [
        "| Case (default run) | Extracted | Revenue (€, one-off) | Annual externality (€/yr) "
        "| PV of externality (€ PV) | Health after | Placeholder or low-confidence parameters |",
        "|---|---|---|---|---|---|---|",
    ]
    for case, label in TABLE_CASES:
        d = json.loads(run_gaia(f"gaia {case} --format json --summary-only"))
        s = d["summary"]
        res = d["ecosystem"]["resource"]
        cal = d["calibration"]
        depletion = s["total_units_extracted"] / res["total_units"]
        rows.append(
            f"| {label}: `gaia {case}` "
            f"| {s['total_units_extracted']:,} of {res['total_units']:,} ({depletion:.0%}) "
            f"| {s['revenue_eur']:,.0f} "
            f"| {s['annual_externality_eur_yr']:,.0f} "
            f"| {s['pv_externality_eur_pv']:,.0f} "
            f"| {s['final_ecosystem_health']:.1%} "
            f"| {cal['n_placeholder'] + cal['n_low']} of {cal['n_params']} |"
        )
    return "\n".join(rows)


def render(attrs: Dict[str, str]) -> str:
    """The generated body of one block (without the markers)."""
    if attrs.get("table") == "cases":
        return _cases_table() + "\n"
    command = attrs["cmd"]
    output = run_gaia(command)
    if "json" in attrs:
        paths = [p.strip() for p in attrs["json"].split(",") if p.strip()]
        output = json.dumps(_select(json.loads(output), paths), indent=2, ensure_ascii=False)
        return f"`$ {command}` (excerpt):\n\n```json\n{output}\n```\n"
    if "until" in attrs:
        kept = []
        for line in output.splitlines():
            if attrs["until"] in line:
                break
            kept.append(line)
        else:
            raise RuntimeError(f"{command!r}: no line contains {attrs['until']!r}")
        output = "\n".join(kept).rstrip() + f"\n  [... excerpt: the output continues with {attrs['until']!r}]"
    return f"```text\n$ {command}\n{output}\n```\n"


def regenerate(text: str) -> str:
    """README text with every block regenerated."""
    def _sub(match: "re.Match[str]") -> str:
        attrs = dict(_ATTR.findall(match.group("attrs")))
        return match.group(1) + render(attrs) + match.group(4)

    new, count = _BLOCK.subn(_sub, text)
    if count == 0:
        raise RuntimeError("README.md has no <!-- BEGIN:example ... --> blocks")
    return new


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 if README.md differs from the regenerated examples",
    )
    args = parser.parse_args(argv)
    current = README.read_text(encoding="utf-8")
    fresh = regenerate(current)
    if args.check:
        if fresh != current:
            print("README.md examples are stale: run python3 scripts/gen_readme_examples.py")
            return 1
        print("README.md examples are up to date")
        return 0
    if fresh != current:
        README.write_text(fresh, encoding="utf-8")
        print("UPDATED   README.md")
    else:
        print("OK        README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
