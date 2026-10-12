"""
Tests for the shipped case files and ``gaia run`` (Step 7.2, E6): the four
cases are JSON documents in gaia/cases/data, loaded by gaia.cases.load_case.

The golden snapshots (tests/test_golden.py) prove that the files reproduce
the 0.9.0 code-defined cases exactly; these tests cover the registry, the
files themselves, packaging and running a file of your own.
"""

import json
import re
from pathlib import Path

import pytest

from gaia.cases import CASE_ALIASES, CASE_NAMES, DATA_DIR, case_data_path, load_case
from gaia.cli import main
from gaia.ecosystem_io import dumps, ecosystem_from_dict, ecosystem_to_dict, read_json

ROOT = Path(__file__).resolve().parent.parent


def test_registry_matches_the_data_directory():
    assert sorted(p.stem for p in DATA_DIR.glob("*.json")) == sorted(CASE_NAMES)
    for alias, name in CASE_ALIASES.items():
        assert load_case(alias) is load_case(name)


@pytest.mark.parametrize("name", CASE_NAMES)
def test_case_files_are_canonically_formatted(name):
    """2-space JSON, UTF-8 kept, so diffs of the data files stay readable."""
    path = case_data_path(name)
    assert path.read_text(encoding="utf-8") == dumps(read_json(path))


@pytest.mark.parametrize("name", CASE_NAMES)
def test_case_files_validate_and_round_trip(name):
    case = load_case(name)
    data = read_json(case_data_path(name))
    eco = ecosystem_from_dict(data)  # validate_ecosystem included
    assert eco.name == case.name
    assert ecosystem_to_dict(ecosystem_from_dict(ecosystem_to_dict(eco))) == ecosystem_to_dict(eco)
    names = [p.name for p in eco.provenance]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("name,units,total", [
    ("forest", 5000, 10000), ("costa_brava", 4000, 10000),
    # Posidonia since Step 8.2: the Catalan stock (4,582 ha) and an
    # illustrative 50 ha project (the 0.9 defaults were 5,000 and 2,000)
    ("posidonia", 50, 4582), ("amazon_forest", 80000, 400000),
])
def test_run_defaults_are_the_0_9_cli_defaults(name, units, total):
    case = load_case(name)
    assert case.default_units == units
    assert case.total_units.value == total


def test_builds_are_independent():
    case = load_case("forest")
    first = case.build_ecosystem()
    first.agents[0].dependency_weight = 0.9
    first.interactions[0].strength = 0.9
    first.provenance.clear()
    second = case.build_ecosystem()
    assert second.agents[0].dependency_weight == 0.2
    assert second.interactions[0].strength == 0.2
    assert second.provenance


def test_package_data_includes_the_case_files():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cases/data/*.json"' in text
    assert '"cases/definitions/*.md"' in text


def _readme_case_example() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"<!-- case-file-example -->\n```json\n(.*?)\n```", readme, re.DOTALL)
    assert match, "README case-file example not found"
    return json.loads(match.group(1))


def test_readme_case_example_runs(tmp_path, capsys):
    path = tmp_path / "valley.json"
    path.write_text(json.dumps(_readme_case_example()), encoding="utf-8")
    assert main(["run", str(path), "--format", "json", "--summary-only"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["ecosystem"]["name"] == "Valley Watershed"
    assert d["summary"]["total_units_extracted"] == 100
    assert d["ecosystem"]["resource"]["area_ha"] == 500.0
    names = [p["name"] for p in d["calibration"]["parameters"]]
    assert "resource.unit_value" in names and "agents.annual_value_per_ha" in names
    assert main(["run", str(path), "--mode", "restore", "--units", "50"]) == 0
    assert "Valley Watershed" in capsys.readouterr().out


def test_gaia_run_reports_a_bad_file(tmp_path, capsys):
    path = tmp_path / "bad.json"
    doc = _readme_case_example()
    doc["agents"][1]["damage"] = "logistc"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["run", str(path)]) == 2
    err = capsys.readouterr().err
    assert "bad.json: $.agents[1].damage: unknown damage curve 'logistc'" in err
    assert main(["run", str(tmp_path / "missing.json")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_gaia_run_help_shows_case_defaults(capsys):
    assert main(["run", "posidonia", "--help"]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert out.startswith("usage: gaia run posidonia")
    assert "--total-units N Total number of units (ha) in the resource (default: 4582)" in out
    assert "(default: 50)" in out  # --units
    assert "(default: 50000.0)" in out  # --planting-cost from the file


def test_case_notes_keep_the_derivations():
    notes = (DATA_DIR.parent / "definitions" / "CASE_NOTES.md").read_text(encoding="utf-8")
    for heading in ("Oak Valley Forest", "Costa Brava Holm Oak Forest",
                    "Posidonia oceanica meadows of Catalonia", "Central Amazon"):
        assert f"## {heading}" in notes
    assert "--cut" not in notes
