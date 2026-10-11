"""
The example outputs in README.md are generated from the code
(scripts/gen_readme_examples.py) and must not drift (audit finding D1).
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_readme_examples", ROOT / "scripts" / "gen_readme_examples.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_examples_match_the_code():
    gen = _generator()
    current = gen.README.read_text(encoding="utf-8")
    assert gen.regenerate(current) == current, (
        "README.md examples are stale: run python3 scripts/gen_readme_examples.py"
    )


def test_readme_has_generated_blocks_for_every_kind():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.count("<!-- BEGIN:example ") == text.count("<!-- END:example -->") >= 4
    assert 'table="cases"' in text and 'json="' in text and 'until="' in text


def test_readme_disclaimer_is_under_the_tagline():
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    first_section = next(i for i, line in enumerate(lines) if line.startswith("## "))
    head = "\n".join(lines[:first_section])
    assert "illustrative and uncalibrated" in head
    assert "not real-world estimates" in head
