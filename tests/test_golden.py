"""
Golden snapshot tests: freeze current model outputs for every shipped case.

Any change to a case's numbers fails here. If the change is intended,
regenerate with ``python3 scripts/regen_golden.py [case|scenario]`` and say
in the commit message which numbers changed and why.

Values are compared at rel=1e-9. The stored files were written by the
former Cython loop, whose build fused a few multiply-adds: five values of
the extraction snapshots differ from the (only) Python engine in their last
digit, well inside the tolerance (see scripts/regen_golden.py).
"""

import pytest

from tests.golden_support import (
    SCENARIOS,
    build_snapshot,
    compare,
    golden_path,
    load_golden,
)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_golden_snapshot(name):
    path = golden_path(name)
    assert path.exists(), (
        f"Missing {path}; run: python3 scripts/regen_golden.py {name}"
    )
    diffs = compare(load_golden(name), build_snapshot(name))
    if diffs:
        shown = "\n  ".join(diffs[:30])
        more = f"\n  ... and {len(diffs) - 30} more" if len(diffs) > 30 else ""
        pytest.fail(
            f"{name}: {len(diffs)} value(s) differ from golden:\n  {shown}{more}\n"
            f"If intended: python3 scripts/regen_golden.py {name}"
        )


def test_compare_detects_small_relative_change():
    assert compare({"x": 1.0}, {"x": 1.0 + 1e-12}) == []
    assert compare({"x": 1.0}, {"x": 1.0 + 1e-8}) != []
    assert compare({"x": [1, 2]}, {"x": [1, 2, 3]}) != []
    assert compare({"x": 1}, {"y": 1}) != []
    assert compare({"x": True}, {"x": 1}) != []
