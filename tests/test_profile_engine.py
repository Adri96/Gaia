"""
Smoke test of scripts/profile_engine.py (decision D7 tooling): the script
runs at tiny sizes and prints a well-formed table, with the Cython
extension and without it.
"""

import contextlib
import importlib.util
import io
import re
from pathlib import Path

import pytest

import gaia.simulation as sim

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "profile_engine.py"
ROW = re.compile(
    r"^\| (default|pricing|sweep) \| (forest|costa_brava|posidonia|amazon_forest) "
    r"\| (extract|restore) \| [\d,]+ of [\d,]+ \| (\d+\.\d{3}) \| (\d+\.\d{3}|n/a) "
    r"\| (\d+\.\d×|n/a) \|$"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("profile_engine", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("cython", [True, False])
def test_smoke_run_prints_a_well_formed_table(cython, monkeypatch):
    if cython and not sim._HAS_CYTHON:
        pytest.skip("Cython extension not built or stale")
    if not cython:
        monkeypatch.setattr(sim, "_HAS_CYTHON", False)
    before = sim._HAS_CYTHON
    script = _load_script()
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        assert script.main(["--smoke", "--hotspots"]) == 0
    lines = out.getvalue().splitlines()
    assert lines[0].startswith("Python ") and lines[0].endswith("best of 1")
    header = lines.index("| Run | Case | Mode | Units (of total) | Python (s) | Cython (s) | Python / Cython |")
    rows = []
    for line in lines[header + 2:]:
        if not line.startswith("|"):
            break
        rows.append(ROW.match(line))
    assert len(rows) == 16 and all(rows), lines[header:header + 18]
    assert {m.group(1) for m in rows} == {"default", "pricing", "sweep"}
    assert all((m.group(5) == "n/a") == (not cython) for m in rows)
    hotspots = [line for line in lines if line.startswith("### Hotspots:")]
    assert len(hotspots) == (3 if cython else 2)
    assert sim._HAS_CYTHON is before  # the script restores the engine switch
