"""
Golden snapshot support: scenario definitions, snapshotting and comparison.

Shared by ``tests/test_golden.py`` (which compares) and
``scripts/regen_golden.py`` (which regenerates ``tests/golden/*.json``).

Each scenario runs a case CLI ``main(argv)`` exactly as a user would, with
``--format json --summary-only``. The case module's ``output_result`` is
wrapped so that both the raw result object (full float precision) and the
printed JSON summary are captured from the same run.

Snapshot layout (one JSON file per scenario):
    scenario   — case name and CLI argv
    agents     — agent names, in model order
    result     — every scalar/nested field of the result object except
                 the ecosystem and the per-step / per-year arrays
    per_agent  — final per-agent cost (extract) or service value (restore)
    steps      — ~11 evenly sampled steps, every field
    step_sums  — sum over ALL steps of every numeric step field
    maturation — sampled maturation timeline + per-field sums (restore only)
    cli_summary_json — parsed ``--summary-only`` JSON, version normalised
"""

import contextlib
import dataclasses
import importlib
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REL_TOL = 1e-9
ABS_TOL = 1e-12
STEP_SAMPLES = 11
VERSION_PLACEHOLDER = "<gaia_version>"

# name → (case, argv). Amazon and the pricing runs use small resources so
# the suite stays fast. The default restoration runs include a maturation
# horizon so the timeline, years-to-50%/90% and maturation gap are pinned.
SCENARIOS: Dict[str, Tuple[str, List[str]]] = {
    "forest__extract": ("forest", ["--trees", "10000", "--units", "5000"]),
    "forest__extract_pricing": (
        "forest", ["--trees", "2000", "--units", "1000", "--with-pricing"],
    ),
    "forest__restore": (
        "forest",
        ["--mode", "restore", "--trees", "10000", "--units", "5000",
         "--time-horizon", "100"],
    ),
    "costa_brava__extract": (
        "costa_brava", ["--trees", "10000", "--units", "4000"],
    ),
    "costa_brava__extract_pricing": (
        "costa_brava", ["--trees", "2000", "--units", "800", "--with-pricing"],
    ),
    "costa_brava__restore": (
        "costa_brava",
        ["--mode", "restore", "--trees", "10000", "--units", "4000",
         "--time-horizon", "100"],
    ),
    # 90% destroyed: substrate recovery (~51 yr) exceeds the 50-year cap on
    # the permanent-loss term, which no default-sized scenario reaches.
    "costa_brava__restore_severe": (
        "costa_brava",
        ["--mode", "restore", "--trees", "1000", "--units", "900"],
    ),
    "posidonia__extract": (
        "posidonia", ["--hectares", "5000", "--units", "2000"],
    ),
    "posidonia__extract_pricing": (
        "posidonia", ["--hectares", "1000", "--units", "400", "--with-pricing"],
    ),
    "posidonia__restore": (
        "posidonia",
        ["--mode", "restore", "--hectares", "5000", "--units", "2000",
         "--time-horizon", "100"],
    ),
    "amazon_forest__extract": (
        "amazon_forest", ["--trees", "4000", "--units", "800"],
    ),
    "amazon_forest__extract_pricing": (
        "amazon_forest", ["--trees", "4000", "--units", "800", "--with-pricing"],
    ),
    "amazon_forest__restore": (
        "amazon_forest",
        ["--mode", "restore", "--trees", "4000", "--units", "800",
         "--time-horizon", "100"],
    ),
}

CASES = sorted({case for case, _ in SCENARIOS.values()})

_SKIP_RESULT_FIELDS = {"ecosystem", "steps", "maturation_timeline"}


# ── Normalisation ─────────────────────────────────────────────────────────────


def normalise(obj: Any) -> Any:
    """Convert a result object tree into plain, strict-JSON-safe data.

    Dataclasses become dicts, tuples become lists, callables are dropped and
    non-finite floats become the strings "inf", "-inf" or "nan".
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            if callable(value):
                continue
            out[f.name] = normalise(value)
        return out
    if isinstance(obj, dict):
        return {str(k): normalise(v) for k, v in obj.items() if not callable(v)}
    if isinstance(obj, (list, tuple)):
        return [normalise(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj):
            return "nan"
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        return obj
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    raise TypeError(f"Cannot snapshot value of type {type(obj).__name__}")


def _sample_indices(n: int, samples: int = STEP_SAMPLES) -> List[int]:
    if n <= samples:
        return list(range(n))
    return sorted({round(i * (n - 1) / (samples - 1)) for i in range(samples)})


def _numeric_sums(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum every numeric field (scalars and per-agent lists) over all records."""
    sums: Dict[str, Any] = {}
    for rec in records:
        for key, value in rec.items():
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (int, float)):
                sums[key] = sums.get(key, 0.0) + value
            elif isinstance(value, list) and value and all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in value
            ):
                acc = sums.setdefault(key, [0.0] * len(value))
                if isinstance(acc, list) and len(acc) == len(value):
                    sums[key] = [a + v for a, v in zip(acc, value)]
    return {k: normalise(v) for k, v in sorted(sums.items())}


# ── Running scenarios ─────────────────────────────────────────────────────────


@contextlib.contextmanager
def forced_python_engine():
    """Temporarily disable the Cython fast path."""
    import gaia.simulation as sim
    saved = sim._HAS_CYTHON
    sim._HAS_CYTHON = False
    try:
        yield
    finally:
        sim._HAS_CYTHON = saved


def run_scenario(name: str) -> Tuple[Any, Dict[str, Any]]:
    """Run one scenario via its case CLI; return (result_obj, summary_json)."""
    case, argv = SCENARIOS[name]
    module = importlib.import_module(f"gaia.cases.{case}")
    original = getattr(module, "output_result", None)
    if original is None:
        raise RuntimeError(
            f"gaia.cases.{case} has no output_result; update golden_support"
        )
    captured: Dict[str, Any] = {}

    def _capture(text_report, result_obj, *args, **kwargs):
        captured["result"] = result_obj
        return original(text_report, result_obj, *args, **kwargs)

    module.output_result = _capture
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            module.main(list(argv) + ["--format", "json", "--summary-only"])
    finally:
        module.output_result = original
    if "result" not in captured:
        raise RuntimeError(f"Scenario {name} produced no result")
    return captured["result"], json.loads(buf.getvalue())


def build_snapshot(name: str) -> Dict[str, Any]:
    """Run a scenario and build its golden snapshot dict."""
    case, argv = SCENARIOS[name]
    result, summary = run_scenario(name)
    agents = [a.name for a in result.ecosystem.agents]

    result_fields = {
        f.name: normalise(getattr(result, f.name))
        for f in dataclasses.fields(result)
        if f.name not in _SKIP_RESULT_FIELDS
    }

    steps = [normalise(s) for s in result.steps]
    per_agent: Dict[str, Any] = {}
    if steps:
        last = steps[-1]
        values = last.get("agent_annual_costs", last.get("agent_service_values", []))
        per_agent = dict(zip(agents, values))

    snapshot: Dict[str, Any] = {
        "scenario": {"name": name, "case": case, "argv": list(argv)},
        "agents": agents,
        "result": result_fields,
        "per_agent": per_agent,
        "steps": [steps[i] for i in _sample_indices(len(steps))],
        "step_sums": _numeric_sums(steps),
    }

    timeline = [normalise(m) for m in getattr(result, "maturation_timeline", [])]
    if timeline:
        snapshot["maturation"] = {
            "samples": [timeline[i] for i in _sample_indices(len(timeline))],
            "sums": _numeric_sums(timeline),
        }

    if "gaia_version" in summary:
        summary["gaia_version"] = VERSION_PLACEHOLDER
    snapshot["cli_summary_json"] = normalise(summary)
    return snapshot


# ── File I/O ──────────────────────────────────────────────────────────────────


def golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def dumps(snapshot: Dict[str, Any]) -> str:
    """Stable, diff-friendly serialisation (sorted keys, shortest float repr)."""
    return json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False) + "\n"


def load_golden(name: str) -> Dict[str, Any]:
    with golden_path(name).open(encoding="utf-8") as f:
        return json.load(f)


# ── Comparison ────────────────────────────────────────────────────────────────


def compare(
    expected: Any,
    actual: Any,
    path: str = "$",
    rel: float = REL_TOL,
    abs_tol: float = ABS_TOL,
    diffs: Optional[List[str]] = None,
) -> List[str]:
    """Recursively compare two snapshot trees; return human-readable diffs.

    Floats (and int/float pairs) match within ``rel``; everything else must
    match exactly, including dict key sets and list lengths.
    """
    if diffs is None:
        diffs = []
    num = (int, float)
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is not actual:
            diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
    elif isinstance(expected, num) and isinstance(actual, num):
        if isinstance(expected, int) and isinstance(actual, int):
            if expected != actual:
                diffs.append(f"{path}: expected {expected}, got {actual}")
        elif not math.isclose(expected, actual, rel_tol=rel, abs_tol=abs_tol):
            diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
    elif isinstance(expected, dict) and isinstance(actual, dict):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing:
            diffs.append(f"{path}: missing keys {missing}")
        if extra:
            diffs.append(f"{path}: unexpected keys {extra}")
        for key in sorted(set(expected) & set(actual)):
            compare(expected[key], actual[key], f"{path}.{key}", rel, abs_tol, diffs)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append(
                f"{path}: expected length {len(expected)}, got {len(actual)}"
            )
        for i, (e, a) in enumerate(zip(expected, actual)):
            compare(e, a, f"{path}[{i}]", rel, abs_tol, diffs)
    elif expected != actual:
        diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
    return diffs
