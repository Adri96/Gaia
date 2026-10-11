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
        assert parsed["pricing"]["experimental"] is True

    def test_with_pricing_text_banner(self, capsys):
        forest_main(["--trees", "100", "--units", "50", "--with-pricing"])
        assert "EXPERIMENTAL: endogenous pricing" in capsys.readouterr().out

    def test_with_pricing_divergent_run_fails_explicitly(self, capsys):
        """No result and exit code 1 past the convergence limit (C8)."""
        from gaia.cases.costa_brava import main as costa_brava_main

        with pytest.raises(SystemExit) as info:
            costa_brava_main([
                "--trees", "200", "--units", "100",
                "--format", "json", "--with-pricing",
            ])
        assert info.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Error: Endogenous pricing (EXPERIMENTAL) failed" in captured.err
        assert "No fallback" in captured.err

    def test_with_pricing_ignored_in_restore_mode(self, capsys):
        with pytest.warns(UserWarning, match="--with-pricing applies to extraction only"):
            forest_main([
                "--mode", "restore", "--trees", "100", "--units", "50",
                "--format", "json", "--with-pricing",
            ])
        parsed = json.loads(capsys.readouterr().out)
        assert "pricing" not in parsed

    def test_carbon_price_defaults_to_scc(self, capsys):
        forest_main(["--trees", "100", "--units", "50", "--format", "json"])
        parsed = json.loads(capsys.readouterr().out)
        resource = parsed["ecosystem"]["resource"]
        assert resource["carbon_price_eur_per_t"] == pytest.approx(166.35)
        assert resource["carbon_price_basis"].startswith("social cost of carbon")

    def test_carbon_price_ets_view(self, capsys):
        forest_main(["--trees", "100", "--units", "50", "--format", "json"])
        scc = json.loads(capsys.readouterr().out)["npv_analysis"]
        forest_main([
            "--trees", "100", "--units", "50",
            "--format", "json", "--carbon-price", "ets",
        ])
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["ecosystem"]["resource"]["carbon_price_eur_per_t"] == 80.0
        assert parsed["ecosystem"]["resource"]["carbon_price_basis"].startswith("market/ETS")
        ets = parsed["npv_analysis"]
        assert ets["carbon_release_eur_pv"] == pytest.approx(
            scc["carbon_release_eur_pv"] * 80.0 / 166.3456487, rel=1e-6)
        assert ets["services_eur_pv"] == scc["services_eur_pv"]

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


class TestUnitsLost:
    """--units-lost sets the degraded starting state of a restoration (Step 3.3)."""

    def test_default_is_none(self):
        assert forest_parse([]).units_lost is None

    def test_default_restores_what_was_cut(self, capsys):
        d = _json_run(forest_main, ["--trees", "100", "--units", "40",
                                    "--mode", "restore"], capsys)
        assert d["summary"]["units_lost"] == 40
        assert d["summary"]["depletion_before"] == 0.4
        assert d["summary"]["depletion_after"] == 0.0

    def test_partial_restoration_of_a_larger_loss(self, capsys):
        d = _json_run(forest_main, ["--trees", "100", "--units", "40",
                                    "--units-lost", "80", "--mode", "restore"], capsys)
        s = d["summary"]
        assert s["units_lost"] == 80
        assert s["depletion_before"] == 0.8
        assert s["depletion_after"] == 0.4
        assert s["initial_ecosystem_health"] < s["final_ecosystem_health"] < 1.0
        assert s["annual_recovered_value_eur_yr"] <= s["annual_damage_reversal_eur_yr"]

    def test_more_restored_than_lost_is_an_error(self, capsys):
        with pytest.raises(SystemExit):
            forest_main(["--trees", "100", "--units", "50", "--units-lost", "20",
                         "--mode", "restore"])
        assert "cannot exceed the units missing" in capsys.readouterr().err

    def test_deprecated_cut_alias_sets_units_restored(self, capsys):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            d = _json_run(forest_main, ["--trees", "100", "--cut", "30",
                                        "--units-lost", "60", "--mode", "restore"], capsys)
        assert d["summary"]["total_units_restored"] == 30
        assert d["summary"]["units_lost"] == 60

    def test_warned_in_extraction_mode(self, capsys):
        argv = ["--trees", "100", "--units", "50", "--units-lost", "60"]
        with pytest.warns(UserWarning, match="--units-lost is only used in restore mode"):
            forest_main(argv)
        capsys.readouterr()


# ── The gaia command (console script / python -m gaia) ───────────────────────


class TestGaiaCommand:
    def test_no_arguments_prints_usage(self, capsys):
        from gaia.cli import main
        assert main([]) == 2
        assert "usage: gaia <case>" in capsys.readouterr().out

    def test_version(self, capsys):
        import gaia
        from gaia.cli import main
        assert main(["--version"]) == 0
        assert capsys.readouterr().out.strip() == f"Gaia {gaia.__version__}"

    def test_dispatches_to_case(self, capsys):
        from gaia.cli import main
        assert main(["forest", "--trees", "100", "--units", "30",
                     "--format", "json", "--summary-only"]) == 0
        d = json.loads(capsys.readouterr().out)
        assert d["ecosystem"]["name"] == "Oak Valley Forest"
        assert d["summary"]["total_units_extracted"] == 30

    @pytest.mark.parametrize("alias", ["costa-brava", "amazon", "amazon-forest"])
    def test_aliases(self, alias, capsys):
        from gaia.cli import main
        assert main([alias, "--trees", "1000", "--units", "10",
                     "--format", "json", "--summary-only"]) == 0
        assert json.loads(capsys.readouterr().out)["mode"] == "extraction"

    def test_unknown_case(self, capsys):
        from gaia.cli import main
        assert main(["moon"]) == 2
        assert "unknown case 'moon'" in capsys.readouterr().err

    def test_case_error_is_exit_status_1(self, capsys):
        from gaia.cli import main
        assert main(["forest", "--trees", "100", "--units", "500"]) == 1
        assert "exceeds" in capsys.readouterr().err

    def test_python_dash_m_gaia(self):
        import subprocess
        import sys

        import gaia
        out = subprocess.run([sys.executable, "-m", "gaia", "--version"],
                             capture_output=True, text=True, check=True)
        assert out.stdout.strip() == f"Gaia {gaia.__version__}"



# ── CLI UX (Step 6.6, E10) ───────────────────────────────────────────────────


class TestUnusedRestorationArgs:
    def test_from_parsed_args_not_sys_argv(self, capsys, monkeypatch):
        """main(argv) from code: sys.argv is irrelevant, both ways."""
        monkeypatch.setattr("sys.argv", ["prog", "--planting-cost", "9", "--time-horizon", "5"])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            forest_main(["--trees", "100", "--units", "10", "--format", "json",
                         "--summary-only"])
        assert not [x for x in w if "only used in restore mode" in str(x.message)]
        capsys.readouterr()

    def test_every_flag_given_is_warned_once(self, capsys):
        argv = ["--trees", "100", "--units", "10", "--planting-cost", "50",
                "--maintenance-years", "10", "--format", "json", "--summary-only"]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            forest_main(argv)
        messages = [str(x.message) for x in w if "only used in restore mode" in str(x.message)]
        assert len(messages) == 2
        assert messages[0].startswith("--planting-cost")
        assert messages[1].startswith("--maintenance-years")
        capsys.readouterr()

    def test_value_equal_to_default_still_warned(self, capsys):
        """Explicit flags are recorded even when the value is the default."""
        args = forest_parse(["--planting-cost", "50.0"])
        assert args.explicit_flags == ["--planting-cost"]
        assert getattr(forest_parse([]), "explicit_flags", []) == []

    def test_not_warned_in_restore_mode(self, capsys):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            forest_main(["--trees", "100", "--units", "10", "--mode", "restore",
                         "--planting-cost", "20", "--format", "json", "--summary-only"])
        assert not [x for x in w if "only used in restore mode" in str(x.message)]
        capsys.readouterr()


class TestOutputErrors:
    def test_unwritable_output_is_a_clean_error(self, tmp_path, capsys):
        target = tmp_path / "missing_dir" / "out.json"
        with pytest.raises(SystemExit) as exc:
            forest_main(["--trees", "100", "--units", "10", "--output", str(target)])
        assert "cannot write --output" in str(exc.value.code)
        assert "Traceback" not in capsys.readouterr().err

    def test_gaia_command_exit_status_1(self, tmp_path, capsys):
        from gaia.cli import main
        target = tmp_path / "missing_dir" / "out.json"
        assert main(["forest", "--trees", "100", "--units", "10",
                     "--output", str(target)]) == 1
        assert "cannot write --output" in capsys.readouterr().err


class TestWarningFormat:
    def test_cli_warnings_have_no_source_line(self):
        import subprocess
        import sys
        out = subprocess.run(
            [sys.executable, "-m", "gaia", "forest", "--trees", "100", "--units", "10",
             "--format", "json", "--summary-only", "--cut", "10"],
            capture_output=True, text=True, check=True,
        )
        assert "Warning (CalibrationWarning): Oak Valley Forest" in out.stderr
        assert "Warning (FutureWarning): --cut is deprecated, use --units instead" in out.stderr
        assert "warnings.warn" not in out.stderr and ".py:" not in out.stderr

    def test_library_formatting_untouched(self):
        import gaia.cli
        before = warnings.formatwarning
        with gaia.cli.user_facing_warnings():
            assert warnings.formatwarning is not before
        assert warnings.formatwarning is before
        forest_parse([])
        assert warnings.formatwarning is before


class TestJsonSteps:
    def test_steps_every_downsamples_and_keeps_last(self, capsys):
        forest_main(["--trees", "100", "--units", "25", "--format", "json",
                     "--steps-every", "10"])
        d = json.loads(capsys.readouterr().out)
        assert d["steps_every"] == 10
        assert [s["step"] for s in d["steps"]] == [10, 20, 25]
        assert d["summary"]["num_steps"] == 25

    def test_steps_every_must_be_positive(self, capsys):
        with pytest.raises(SystemExit):
            forest_parse(["--steps-every", "0"])
        capsys.readouterr()

    def test_large_runs_default_to_summary_only(self, capsys, monkeypatch):
        import gaia.cli
        monkeypatch.setattr(gaia.cli, "MAX_JSON_STEPS", 20)
        with pytest.warns(UserWarning, match="per-step data omitted"):
            forest_main(["--trees", "100", "--units", "25", "--format", "json"])
        d = json.loads(capsys.readouterr().out)
        assert "steps" not in d
        forest_main(["--trees", "100", "--units", "25", "--format", "json",
                     "--steps-every", "1"])
        assert len(json.loads(capsys.readouterr().out)["steps"]) == 25

    def test_to_json_steps_every(self):
        from gaia.cases.forest import build_forest_ecosystem
        from gaia.serialization import to_json
        from gaia.simulation import run_extraction
        result = run_extraction(build_forest_ecosystem(total_trees=100), 30)
        d = json.loads(to_json(result, steps_every=15))
        assert [s["step"] for s in d["steps"]] == [15, 30]
        with pytest.raises(ValueError, match="steps_every"):
            to_json(result, steps_every=0)
