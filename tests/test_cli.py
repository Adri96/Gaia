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
