"""
Step 3.8 (S2) — propagation sanity.

    - In-degree cap: an agent's incoming edge strengths, keystone boosts
      included, must sum to at most MAX_INCOMING_EDGE_STRENGTH; validation
      rejects anything above (nothing is rescaled silently).
    - Calibration regime (Option A / B) declared on every ecosystem with
      edges, validated, and carried in the JSON output.
    - CalibrationWarning when ecosystem health at the safe threshold is low.
    - Trophic and keystone constants have one source (gaia.constants).
"""

import json
import warnings

import pytest

import gaia.propagation as propagation
from gaia import constants
from gaia.cases.amazon_forest import build_amazon_ecosystem
from gaia.cases.costa_brava import build_costa_brava_ecosystem
from gaia.cases.forest import build_forest_ecosystem
from gaia.cases.posidonia import build_posidonia_ecosystem
from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    CalibrationRegime,
    Ecosystem,
    InteractionEdge,
    Resource,
    RestorationCost,
)
from gaia.propagation import (
    ecosystem_health_at,
    keystone_boosted_strength,
    trophic_amplification_factor,
    worst_case_incoming_strengths,
)
from gaia.recovery import logistic_recovery
from gaia.report import format_report
from gaia.serialization import to_json
from gaia.simulation import run_extraction, run_restoration
from gaia.validation import (
    CalibrationWarning,
    check_threshold_health,
    validate_ecosystem,
)

SHIPPED = {
    "forest": build_forest_ecosystem,
    "costa_brava": build_costa_brava_ecosystem,
    "posidonia": build_posidonia_ecosystem,
    "amazon_forest": build_amazon_ecosystem,
}


def _eco(edges=(), regime=CalibrationRegime.DIRECT_ONLY, keystone_a=False,
         curve_threshold=0.32, safe_threshold=0.3, total_units=100):
    """Three agents (A producer, B, C); curves gentle enough that health at
    the safe threshold is 0.82 without edges."""
    agents = [
        Agent(name=name, dependency_weight=w,
              damage_function=logistic_damage(threshold=curve_threshold),
              annual_value_per_ha=1_000.0, description=name,
              is_keystone=(keystone_a and name == "A"), keystone_threshold=0.6)
        for name, w in (("A", 0.4), ("B", 0.3), ("C", 0.3))
    ]
    return Ecosystem(
        name="Toy",
        resource=Resource(name="Toy", total_units=total_units,
                          safe_threshold_ratio=safe_threshold,
                          unit_value=1.0, area_ha=10.0),
        agents=agents,
        interactions=[
            InteractionEdge(s, t, k, kind, f"{s}->{t}") for s, t, k, kind in edges
        ],
        calibration_regime=regime,
    )


def _quiet_validate(eco):
    validate_ecosystem(eco, threshold_health_warning=None)


# ── In-degree cap ─────────────────────────────────────────────────────────────


def test_cap_accepts_incoming_sum_at_cap():
    _quiet_validate(_eco([("A", "C", 0.6, "dependency"), ("B", "C", 0.4, "dependency")]))


def test_cap_rejects_incoming_sum_above_cap():
    eco = _eco([("A", "C", 0.6, "dependency"), ("B", "C", 0.5, "dependency")])
    with pytest.raises(ValueError, match=r"into 'C' sum to 1\.100.*cap of 1\.0"):
        _quiet_validate(eco)


def test_cap_counts_keystone_boost():
    """A keystone source counts at its boosted strength (0.4 → 0.8)."""
    edges = [("A", "C", 0.4, "keystone"), ("B", "C", 0.3, "dependency")]
    _quiet_validate(_eco(edges, keystone_a=False))
    with pytest.raises(ValueError, match=r"into 'C' sum to 1\.100"):
        _quiet_validate(_eco(edges, keystone_a=True))


def test_keystone_boost_is_capped_at_max_edge_strength():
    assert keystone_boosted_strength(0.7) == constants.MAX_EDGE_STRENGTH
    _quiet_validate(_eco([("A", "C", 0.7, "keystone")], keystone_a=True))
    with pytest.raises(ValueError, match="into 'C'"):
        _quiet_validate(_eco([("A", "C", 0.7, "keystone"), ("B", "C", 0.1, "dependency")],
                             keystone_a=True))


def test_over_cap_ecosystem_is_not_run():
    """No silent clamping or rescaling: the simulation refuses to run."""
    eco = _eco([("A", "C", 0.6, "dependency"), ("B", "C", 0.5, "dependency")])
    with pytest.raises(ValueError, match="into 'C'"):
        run_extraction(eco, 10)


@pytest.mark.parametrize("case", list(SHIPPED))
def test_shipped_cases_within_cap(case):
    eco = SHIPPED[case]()
    totals = worst_case_incoming_strengths(eco.agents, eco.interactions)
    assert max(totals.values()) <= constants.MAX_INCOMING_EDGE_STRENGTH


# ── Calibration regime ────────────────────────────────────────────────────────


def test_regime_required_when_there_are_edges():
    eco = _eco([("A", "B", 0.3, "dependency")], regime=None)
    with pytest.raises(ValueError, match="no calibration_regime"):
        _quiet_validate(eco)


def test_regime_optional_without_edges():
    _quiet_validate(_eco(regime=None))


def test_regime_must_be_enum_member():
    eco = _eco([("A", "B", 0.3, "dependency")], regime="B")
    with pytest.raises(ValueError, match="must be a CalibrationRegime"):
        _quiet_validate(eco)


def test_option_a_rejects_non_keystone_edges():
    eco = _eco([("A", "B", 0.3, "dependency")], regime=CalibrationRegime.EMPIRICAL,
               keystone_a=True)
    with pytest.raises(ValueError, match="regime A"):
        _quiet_validate(eco)


def test_option_a_rejects_keystone_edge_from_non_keystone_agent():
    eco = _eco([("A", "B", 0.3, "keystone")], regime=CalibrationRegime.EMPIRICAL)
    with pytest.raises(ValueError, match="regime A"):
        _quiet_validate(eco)


def test_option_a_accepts_keystone_edges_from_keystone_agents():
    _quiet_validate(_eco([("A", "B", 0.3, "keystone"), ("A", "C", 0.2, "keystone")],
                         regime=CalibrationRegime.EMPIRICAL, keystone_a=True))


@pytest.mark.parametrize("case", list(SHIPPED))
def test_shipped_cases_declare_option_b(case):
    """Placeholder curves are not fitted to field data, so none can claim A."""
    assert SHIPPED[case]().calibration_regime is CalibrationRegime.DIRECT_ONLY


def test_regime_serialized_in_extraction_json():
    eco = build_forest_ecosystem(total_trees=100)
    d = json.loads(to_json(run_extraction(eco, 40), include_steps=False))
    assert d["ecosystem"]["calibration_regime"] == "B"


def test_regime_serialized_in_restoration_json():
    eco = build_forest_ecosystem(total_trees=100)
    result = run_restoration(eco, 40, RestorationCost(50.0, 10.0, 10),
                             [logistic_recovery(threshold=0.3) for _ in eco.agents])
    d = json.loads(to_json(result, include_steps=False))
    assert d["ecosystem"]["calibration_regime"] == "B"


def test_undeclared_regime_serialized_as_null():
    d = json.loads(to_json(run_extraction(_eco(regime=None), 10), include_steps=False))
    assert d["ecosystem"]["calibration_regime"] is None


# ── Health at the safe threshold ──────────────────────────────────────────────


@pytest.mark.parametrize("case,units_kw", [
    ("forest", "total_trees"), ("costa_brava", "total_trees"),
    ("posidonia", "total_hectares"), ("amazon_forest", "total_trees"),
])
def test_health_at_matches_extraction_step(case, units_kw):
    """The single evaluation equals the extraction step at that depletion."""
    eco = SHIPPED[case](**{units_kw: 400})
    units = round(eco.resource.safe_threshold_ratio * 400)
    step = run_extraction(eco, units).steps[-1]
    assert ecosystem_health_at(eco, step.depletion_ratio) == pytest.approx(
        step.ecosystem_health, rel=1e-12)


def test_threshold_warning_silent_for_healthy_ecosystem():
    eco = _eco()
    with warnings.catch_warnings():
        warnings.simplefilter("error", CalibrationWarning)
        validate_ecosystem(eco)
    assert check_threshold_health(eco) == pytest.approx(0.817, abs=1e-3)


def test_threshold_warning_fires_for_over_strong_edges():
    """Within the cap, but strong enough to push health below 0.8."""
    eco = _eco([("A", "B", 1.0, "dependency"), ("A", "C", 1.0, "dependency")])
    with pytest.warns(CalibrationWarning, match=r"Toy: ecosystem health at the safe "
                                                r"threshold \(30% depletion\) is 0\.\d\d, below 0\.80"):
        validate_ecosystem(eco)


def test_threshold_warning_fires_for_over_steep_curves():
    with pytest.warns(CalibrationWarning, match="safe threshold"):
        validate_ecosystem(_eco(curve_threshold=0.2))


def test_threshold_warning_level_is_configurable():
    eco = _eco()
    with pytest.warns(CalibrationWarning, match="below 0.95"):
        validate_ecosystem(eco, threshold_health_warning=0.95)
    over = _eco([("A", "B", 1.0, "dependency"), ("A", "C", 1.0, "dependency")])
    with warnings.catch_warnings():
        warnings.simplefilter("error", CalibrationWarning)
        validate_ecosystem(over, threshold_health_warning=0.5)
        validate_ecosystem(over, threshold_health_warning=None)


@pytest.mark.parametrize("level", [0.0, -0.1, 1.5, "0.8"])
def test_threshold_warning_rejects_bad_level(level):
    with pytest.raises(ValueError, match="threshold health warning level"):
        check_threshold_health(_eco(), level)


@pytest.mark.parametrize("case", list(SHIPPED))
def test_shipped_cases_warn_because_of_their_curves(case):
    """Every shipped case warns, and would still warn without any edge: the
    placeholder logistic puts 17–21% direct damage at the safe threshold
    (plus trophic amplification). The warning is honest; fixing it means
    calibrating the curves (Step 8), not tuning edges."""
    eco = SHIPPED[case]()
    with pytest.warns(CalibrationWarning, match="safe threshold"):
        validate_ecosystem(eco)
    eco.interactions = []
    assert ecosystem_health_at(eco, eco.resource.safe_threshold_ratio) < (
        constants.THRESHOLD_HEALTH_WARNING_LEVEL)


# ── One source for the constants ──────────────────────────────────────────────


def test_trophic_factor_reads_constants():
    for level in (1, 2, 3):
        assert trophic_amplification_factor(level) == (
            (1.0 / constants.TROPHIC_TRANSFER_EFFICIENCY)
            ** (level * constants.TROPHIC_AMPLIFICATION_EXPONENT)
        )
    assert trophic_amplification_factor(0) == trophic_amplification_factor(-1) == 1.0


def test_report_trophic_factor_comes_from_propagation(monkeypatch):
    """The report prints the factor the engine used (stored on the result,
    Step 6.3), which comes from gaia.propagation."""
    eco = build_forest_ecosystem(total_trees=100)
    result = run_extraction(eco, 40)
    assert "Trophic amplification: 1.6×" in format_report(result)
    monkeypatch.setattr(propagation, "TROPHIC_AMPLIFICATION_EXPONENT", 0.5)
    rerun = run_extraction(eco, 40)
    assert "Trophic amplification: 2.6×" in format_report(rerun)
    assert "Trophic amplification: 1.6×" in format_report(result)


def test_engine_reads_the_keystone_multiplier(monkeypatch):
    """The engine takes the keystone multiplier from gaia.constants (through
    gaia.propagation), so changing it changes the result."""
    def run():
        eco = _eco([("A", "B", 0.5, "keystone")], keystone_a=True, total_units=50)
        return sum(s.annual_externality for s in run_extraction(eco, 50).steps)

    base = run()
    monkeypatch.setattr(propagation, "KEYSTONE_EDGE_MULTIPLIER", 1.0)
    assert run() < base
