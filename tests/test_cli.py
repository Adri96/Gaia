"""
Tests for Gaia v0.8.1 CLI argument parsing and output format selection.

Tests cover:
- New --units flag replaces --cut/--destroy
- Deprecated aliases still work with warnings
- --format json produces valid JSON
- --unit-value replaces --tree-value/--revenue
- --with-pricing enables endogenous pricing
- --summary-only omits per-step data
- Warnings for restoration-only params in extraction mode
"""

import json
import warnings

import pytest

from gaia.cases.forest import _parse_args as forest_parse
from gaia.cases.forest import main as forest_main
from gaia.cases.posidonia import _parse_args as posidonia_parse
from gaia.cases.posidonia import main as posidonia_main


# ── Forest CLI Argument Parsing ──────────────────────────────────────────────


class TestForestParseArgs:
    def test_defaults(self):
        args = forest_parse([])
        assert args.trees == 10_000
        assert args.threshold == 0.3
        assert args.units == 5_000
        assert args.unit_value == 100.0
        assert args.mode == "extract"
        assert args.output_format == "text"
        assert args.with_pricing is False
        assert args.summary_only is False
        assert args.output is None

    def test_units_flag(self):
        args = forest_parse(["--units", "3000"])
        assert args.units == 3000

    def test_unit_value_flag(self):
        args = forest_parse(["--unit-value", "75.0"])
        assert args.unit_value == 75.0

    def test_deprecated_cut_flag(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            args = forest_parse(["--cut", "3000"])
            assert args.units == 3000
            assert any("--cut is deprecated" in str(x.message) for x in w)

    def test_deprecated_tree_value_flag(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            args = forest_parse(["--tree-value", "75.0"])
            assert args.unit_value == 75.0
            assert any("--tree-value is deprecated" in str(x.message) for x in w)

    def test_format_json(self):
        args = forest_parse(["--format", "json"])
        assert args.output_format == "json"

    def test_with_pricing(self):
        args = forest_parse(["--with-pricing"])
        assert args.with_pricing is True

    def test_summary_only(self):
        args = forest_parse(["--summary-only"])
        assert args.summary_only is True

    def test_output_flag(self):
        args = forest_parse(["--output", "out.json"])
        assert args.output == "out.json"

    def test_mode_restore(self):
        args = forest_parse(["--mode", "restore"])
        assert args.mode == "restore"

    def test_restoration_args(self):
        args = forest_parse([
            "--mode", "restore",
            "--planting-cost", "75.0",
            "--maintenance-cost", "12.0",
            "--maintenance-years", "8",
            "--time-horizon", "30",
        ])
        assert args.planting_cost == 75.0
        assert args.maintenance_cost == 12.0
        assert args.maintenance_years == 8
        assert args.time_horizon == 30


# ── Posidonia CLI Argument Parsing ───────────────────────────────────────────


class TestPosidoniaParsArgs:
    def test_defaults(self):
        args = posidonia_parse([])
        assert args.hectares == 5_000
        assert args.threshold == 0.20
        assert args.units == 2_000
        assert args.unit_value == 2_500.0

    def test_deprecated_destroy_flag(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            args = posidonia_parse(["--destroy", "1500"])
            assert args.units == 1500
            assert any("--destroy is deprecated" in str(x.message) for x in w)

    def test_deprecated_revenue_flag(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            args = posidonia_parse(["--revenue", "3000.0"])
            assert args.unit_value == 3000.0
            assert any("--revenue is deprecated" in str(x.message) for x in w)


# ── Forest CLI JSON Output ───────────────────────────────────────────────────


class TestForestMainJson:
    def test_extraction_json(self, capsys):
        forest_main(["--trees", "100", "--units", "50", "--format", "json"])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["mode"] == "extraction"
        assert parsed["summary"]["total_units_extracted"] == 50
        assert "steps" in parsed

    def test_restoration_json(self, capsys):
        forest_main([
            "--trees", "100", "--units", "50",
            "--mode", "restore", "--format", "json",
        ])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["mode"] == "restoration"
        assert parsed["summary"]["total_units_restored"] == 50

    def test_summary_only_json(self, capsys):
        forest_main([
            "--trees", "100", "--units", "50",
            "--format", "json", "--summary-only",
        ])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "steps" not in parsed
        assert parsed["summary"]["num_steps"] == 50

    def test_text_output_unchanged(self, capsys):
        forest_main(["--trees", "100", "--units", "50"])
        captured = capsys.readouterr()
        # Text output should contain the report header
        assert "GAIA" in captured.out
        assert "Externality Report" in captured.out

    def test_with_pricing_json(self, capsys):
        forest_main([
            "--trees", "100", "--units", "50",
            "--format", "json", "--with-pricing",
        ])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["ecosystem"]["has_pricing"] is True
        assert "pricing" in parsed

    def test_output_to_file(self, tmp_path, capsys):
        outfile = str(tmp_path / "out.json")
        forest_main([
            "--trees", "100", "--units", "50",
            "--format", "json", "--output", outfile,
        ])
        # stdout should be empty
        captured = capsys.readouterr()
        assert captured.out == ""
        # File should contain valid JSON
        with open(outfile) as f:
            parsed = json.loads(f.read())
        assert parsed["mode"] == "extraction"


# ── Posidonia CLI JSON Output ────────────────────────────────────────────────


class TestPosidoniMainJson:
    def test_extraction_json_with_notes(self, capsys):
        posidonia_main([
            "--hectares", "100", "--units", "50", "--format", "json",
        ])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["mode"] == "extraction"
        assert "notes" in parsed
        assert len(parsed["notes"]) > 0
        assert "ANNUAL" in parsed["notes"][0]


# ── Version: single source of truth ──────────────────────────────────────────


class TestVersion:
    def test_serialization_uses_package_version(self):
        import gaia
        from gaia.serialization import GAIA_VERSION
        assert GAIA_VERSION == gaia.__version__

    def test_setup_reads_package_version(self):
        import pathlib
        import subprocess
        import sys

        import gaia
        root = pathlib.Path(gaia.__file__).resolve().parent.parent
        out = subprocess.run(
            [sys.executable, "setup.py", "--version"],
            cwd=root, capture_output=True, text=True, check=True,
        )
        assert out.stdout.strip().splitlines()[-1] == gaia.__version__

    def test_cli_version_flag(self, capsys):
        import gaia
        with pytest.raises(SystemExit) as exc:
            forest_parse(["--version"])
        assert exc.value.code == 0
        assert capsys.readouterr().out.strip() == f"Gaia {gaia.__version__}"


# ── --area-ha: scale invariance (Step 3.2 acceptance) ────────────────────────


def _json_run(main, argv, capsys):
    main(argv + ["--format", "json", "--summary-only"])
    return json.loads(capsys.readouterr().out)


class TestAreaHa:
    def test_default_is_none(self):
        assert forest_parse([]).area_ha is None

    def test_trees_vary_area_fixed_per_ha_externality_unchanged(self, capsys):
        """Changing --trees with --area-ha fixed changes per-tree figures, not per-ha ones."""
        a = _json_run(forest_main, ["--trees", "1000", "--units", "500",
                                    "--area-ha", "40"], capsys)
        b = _json_run(forest_main, ["--trees", "4000", "--units", "2000",
                                    "--area-ha", "40"], capsys)
        for d in (a, b):
            assert d["ecosystem"]["resource"]["area_ha"] == 40.0
        ext_a = a["summary"]["annual_externality_eur_yr"]
        ext_b = b["summary"]["annual_externality_eur_yr"]
        assert ext_a / 40.0 == pytest.approx(ext_b / 40.0, rel=1e-6)
        assert ext_a / 500 == pytest.approx(4 * ext_b / 2000, rel=1e-6)

    def test_area_scales_externality(self, capsys):
        """Doubling the area at the same density doubles the annual externality."""
        a = _json_run(forest_main, ["--trees", "1000", "--units", "500"], capsys)
        b = _json_run(forest_main, ["--trees", "2000", "--units", "1000"], capsys)
        assert b["ecosystem"]["resource"]["area_ha"] == 2 * a["ecosystem"]["resource"]["area_ha"]
        assert b["summary"]["annual_externality_eur_yr"] == pytest.approx(
            2 * a["summary"]["annual_externality_eur_yr"], rel=1e-6)

    def test_posidonia_area_must_equal_hectares(self, capsys):
        with pytest.raises(SystemExit):
            posidonia_main(["--hectares", "1000", "--units", "100", "--area-ha", "500"])
        assert "area_ha" in capsys.readouterr().err
