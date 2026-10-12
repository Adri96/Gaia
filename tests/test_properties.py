"""
Scientific and economic properties the model must satisfy.

Each test encodes one property from TOP_PRIORITIES_REPORT.md §9 Step 2.
Properties the current model violates are marked
``xfail(strict=True, reason="C#: ...")``: they document the bug, and the
strict marker makes the suite fail as soon as a fix makes them pass, so the
fixing commit must remove the marker.

The properties are written for the model as it should behave after the
owner's decisions D1 (monetary rates are yearly flows) and D2 (rates are
€/ha/yr, ``Resource.area_ha`` required). Where the API does not exist yet,
the helpers in the first section stand in for it; the steps that add the API
(3.3 restoration from a starting state) should update those helpers rather
than the tests.
"""

import dataclasses
import json
import math
import re

import pytest

from gaia.cases.amazon_forest import AMAZON_TREES_PER_HA, build_amazon_ecosystem
from gaia.cases.costa_brava import COSTA_BRAVA_TREES_PER_HA, build_costa_brava_ecosystem
from gaia.cases import load_case
from gaia.cases.forest import (
    FOREST_TREES_PER_HA,
    build_forest_ecosystem,
)
from gaia.cases.posidonia import build_posidonia_ecosystem
from gaia.discount import (
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    DISCOUNT_MARKET,
    compute_extraction_npv,
)
from gaia.carbon import SOCIAL_COST_OF_CARBON_EUR
from gaia.models import RestorationCost
from gaia.pricing import PricingConvergenceError
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.serialization import to_json
from gaia.simulation import run_extraction, run_restoration
from gaia.validation import validate_discount_config

_FOREST_SUCCESSION = load_case("forest").succession_curve


# ── Helpers (update these as the API gains area_ha / starting states) ────────

# case → (builder, keyword for the number of units, units per hectare)
# Units per hectare is the case's reference density, used to give each
# resource an area. Posidonia's unit is the hectare itself.
CASES = {
    "forest": (build_forest_ecosystem, "total_trees", FOREST_TREES_PER_HA),
    "costa_brava": (build_costa_brava_ecosystem, "total_trees", COSTA_BRAVA_TREES_PER_HA),
    "posidonia": (build_posidonia_ecosystem, "total_hectares", 1.0),
    "amazon_forest": (build_amazon_ecosystem, "total_trees", AMAZON_TREES_PER_HA),
}
TREE_CASES = ["forest", "costa_brava", "amazon_forest"]


def build(case, total_units, area_ha=None, with_pricing=False):
    """Build a shipped case with ``total_units`` units over ``area_ha`` hectares.

    ``area_ha`` defaults to the case's reference density and is passed to the
    builder, which sets ``Resource.area_ha`` and scales any pricing anchors.
    """
    builder, units_kw, density = CASES[case]
    if area_ha is None:
        area_ha = total_units / density
    eco = builder(**{units_kw: total_units}, with_pricing=with_pricing,
                  area_ha=area_ha)
    assert eco.resource.area_ha == area_ha
    return eco, area_ha


def per_ha(value, area_ha):
    return value / area_ha


def annual_externality(result):
    """Yearly service flow lost at the end state (€/yr, decision D1)."""
    return result.annual_externality


def recovered_after_cut(total_units, units_cut, units_restored):
    """Forest: cut ``units_cut`` from pristine, then restore ``units_restored``.

    The extraction result is chained into the restoration as its starting
    state (Step 3.3).
    """
    eco, _ = build("forest", total_units)
    cut = run_extraction(eco, units_cut)
    cost = RestorationCost(
        planting_cost_per_unit=50.0,
        annual_maintenance_per_unit=10.0,
        maintenance_years=10,
    )
    recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    return run_restoration(
        eco, units_restored, cost, recovery,
        succession_curve=_FOREST_SUCCESSION, time_horizon_years=60,
        starting_state=cut,
    )


# ── 1. Scale invariance (C4, D2) ─────────────────────────────────────────────


@pytest.mark.parametrize("case", TREE_CASES)
def test_scale_invariance_finer_units_same_area(case):
    """Same area, same fraction cut, 2× as many units → same per-ha externality."""
    coarse, area = build(case, 1000)
    fine, _ = build(case, 2000, area_ha=area)
    a = per_ha(annual_externality(run_extraction(coarse, 500)), area)
    b = per_ha(annual_externality(run_extraction(fine, 1000)), area)
    assert b == pytest.approx(a, rel=1e-9)


@pytest.mark.parametrize("case", list(CASES))
def test_scale_invariance_per_ha_externality_independent_of_extent(case):
    """Same density and fraction cut on a resource twice the size → same per-ha externality."""
    small, small_area = build(case, 1000)
    large, large_area = build(case, 2000)
    assert large_area == pytest.approx(2 * small_area)
    a = per_ha(annual_externality(run_extraction(small, 500)), small_area)
    b = per_ha(annual_externality(run_extraction(large, 1000)), large_area)
    assert b == pytest.approx(a, rel=1e-9)


# ── 2–3. Restoration is bounded and monotonic in k (C1) ──────────────────────


@pytest.mark.parametrize("k", [100, 500])
def test_restoring_k_recovers_at_most_cost_of_cutting_k(k):
    eco, _ = build("forest", 1000)
    cut = annual_externality(run_extraction(eco, k))
    recovered = recovered_after_cut(1000, units_cut=k, units_restored=k)
    assert recovered.annual_recovered_value <= cut


def test_recovered_value_strictly_increasing_in_units_restored():
    values = [
        recovered_after_cut(1000, units_cut=1000, units_restored=k).annual_recovered_value
        for k in (1, 250, 500, 1000)
    ]
    assert all(a < b for a, b in zip(values, values[1:])), values


# ── 4. NPV converges as the horizon grows (C3) ───────────────────────────────

DISCOUNT_CONFIGS = {
    "market": DISCOUNT_MARKET,
    "central": DISCOUNT_CENTRAL,
    "environmental": DISCOUNT_ENVIRONMENTAL,
    "green_book": DISCOUNT_GREEN_BOOK,
    **{f"case_{c}": build(c, 100)[0].resource.discount for c in CASES},
}


def _npv_at(discount, horizon):
    config = dataclasses.replace(discount, horizon_years=horizon)
    return compute_extraction_npv(1.0, config, None, 0).total


@pytest.mark.parametrize("name", list(DISCOUNT_CONFIGS))
def test_npv_bounded_as_horizon_grows(name):
    """Every built-in config is valid and its NPV converges in the horizon.

    Validation checks the schedule segments in force within a config's own
    horizon, so the config is validated again at the longest horizon used.
    Doubling a 1,000-year horizon may add at most 10% (the slowest valid
    built-in, r − s ≈ 0.3%, adds ~5%).
    """
    discount = DISCOUNT_CONFIGS[name]
    validate_discount_config(discount)
    validate_discount_config(dataclasses.replace(discount, horizon_years=2000))
    npv_1000 = _npv_at(discount, 1000)
    npv_2000 = _npv_at(discount, 2000)
    assert math.isfinite(npv_2000)
    assert npv_2000 <= 1.10 * npv_1000, (npv_1000, npv_2000)


# ── 5. With endogenous pricing: monotone and continuous where it succeeds,
#       explicit failure where it cannot (C8, Step 4) ─────────────────────────


def priced_costs(case, total_units):
    """Annual externality per step with pricing on, and the failing step.

    Returns the costs of every step up to the first one whose price system
    cannot be certified convergent, and that step (None if all succeed).
    """
    eco, _ = build(case, total_units, with_pricing=True)
    try:
        steps = run_extraction(eco, total_units).steps
        return [s.annual_externality for s in steps], None
    except PricingConvergenceError as exc:
        failed = exc.step
    steps = run_extraction(eco, failed - 1).steps if failed > 1 else []
    return [s.annual_externality for s in steps], failed


@pytest.mark.parametrize("case", list(CASES))
def test_cost_monotonic_where_pricing_succeeds_failure_explicit(case):
    """Where pricing succeeds, cost never decreases with depletion; where it
    cannot, every run fails with PricingConvergenceError — never a silent
    fallback to another scale (the old drop at ρ = 1)."""
    costs, failed = priced_costs(case, 200)
    assert all(math.isfinite(c) and c >= 0.0 for c in costs)
    drops = [
        (i + 1, costs[i - 1], costs[i])
        for i in range(1, len(costs))
        if costs[i] < costs[i - 1] - 1e-9 * abs(costs[i - 1])
    ]
    assert not drops, f"cost decreases at (step, before, after): {drops[:3]}"

    if failed is not None:
        eco, _ = build(case, 200, with_pricing=True)
        for units in sorted({failed, (failed + 200) // 2, 200}):
            with pytest.raises(PricingConvergenceError) as info:
                run_extraction(eco, units)
            assert info.value.step == failed


@pytest.mark.parametrize("case", list(CASES))
def test_cost_continuous_where_pricing_succeeds(case):
    """cost(d + ε) − cost(d) >= 0 and shrinks with ε: refining the depletion
    grid 10× (per-ha cost is the same at the same depletion, D2) shrinks the
    largest increment, which a jump would not."""
    density = CASES[case][2]
    coarse = [c / (100 / density) for c in priced_costs(case, 100)[0]]
    fine = [c / (1000 / density) for c in priced_costs(case, 1000)[0]]
    k = len(coarse)
    assert k >= 10 and len(fine) >= 10 * k
    for j in range(1, k + 1):
        assert fine[10 * j - 1] == pytest.approx(coarse[j - 1], rel=1e-9)

    def increments(costs):
        return [b - a for a, b in zip([0.0] + costs[:-1], costs)]

    coarse_inc = increments(coarse)
    fine_inc = increments(fine[:10 * k])
    assert min(fine_inc) >= -1e-9 * max(fine)
    assert max(fine_inc) <= 0.5 * max(coarse_inc), (max(fine_inc), max(coarse_inc))


# ── 6. No hidden carbon (C5, D3) ─────────────────────────────────────────────

_CARBON_WORDS = re.compile(r"carbon|co2|co₂", re.IGNORECASE)


@pytest.mark.parametrize("case", list(CASES))
def test_no_hidden_carbon(case):
    """Removing the carbon profile removes exactly the carbon line items.

    Carbon must be valued only by gaia.carbon: no agent or pricing anchor
    may describe a carbon component, and the extraction totals without a
    carbon profile must differ only by the carbon NPV lines.
    """
    eco, _ = build(case, 1000, with_pricing=True)
    hidden = [a.name for a in eco.agents
              if _CARBON_WORDS.search(f"{a.name} {a.description}")]
    hidden += [f"anchor:{p.agent_name}" for p in eco.pricing.anchors
               if _CARBON_WORDS.search(f"{p.source} {p.description}")]
    assert not hidden, f"carbon valued outside gaia.carbon: {hidden}"

    with_carbon, _ = build(case, 1000)
    without_carbon, _ = build(case, 1000)
    without_carbon.resource = dataclasses.replace(
        without_carbon.resource, carbon_profile=None)
    a = run_extraction(with_carbon, 500)
    b = run_extraction(without_carbon, 500)
    carbon_lines = a.extraction_npv.carbon_release + a.extraction_npv.carbon_foregone
    assert a.extraction_npv.total - b.extraction_npv.total == pytest.approx(
        carbon_lines, rel=1e-12)
    assert annual_externality(a) == annual_externality(b)


# ── 6b. Carbon value is bounded by the carbon at stake (C5, D3) ─────────────


def _carbon_at_stake(eco, units):
    """Release + PV of the foregone absorption of ``units``, at the SCC.

    Computed independently of gaia.carbon: tonnes from the carbon profile,
    priced at SOCIAL_COST_OF_CARBON_EUR growing at the DiscountConfig's rate,
    over the years t = 1..H of every stream (gaia.discount's convention).
    """
    cp = eco.resource.carbon_profile
    discount = eco.resource.discount
    assert discount.carbon_price_current == SOCIAL_COST_OF_CARBON_EUR
    release = units * (cp.stored_carbon_tonnes
                       + cp.soil_carbon_tonnes * cp.soil_release_fraction)
    absorption = units * cp.annual_absorption_tonnes
    # The release: at year 0, or spread by its half-life (Step 8c.5), the
    # share released during year t valued at the price of year t
    if cp.release_half_life_years == 0.0:
        release_eur = release * SOCIAL_COST_OF_CARBON_EUR
    else:
        lam = math.log(2.0) / cp.release_half_life_years
        release_eur = sum(
            release * (math.exp(-lam * t) - math.exp(-lam * (t + 1)))
            * SOCIAL_COST_OF_CARBON_EUR * (1 + discount.carbon_price_growth) ** t
            * discount.discount_factor(t)
            for t in range(discount.horizon_years)
        )
        assert release_eur < release * SOCIAL_COST_OF_CARBON_EUR
    foregone = sum(
        absorption * SOCIAL_COST_OF_CARBON_EUR
        * (1 + discount.carbon_price_growth) ** t * discount.discount_factor(t)
        for t in range(1, discount.horizon_years + 1)
    )
    return release_eur, foregone


@pytest.mark.parametrize("succession", [True, False], ids=["succession", "instant"])
@pytest.mark.parametrize("case", list(CASES))
def test_capitalised_carbon_never_exceeds_carbon_at_stake(case, succession):
    """No NPV capitalises more carbon than (release + PV of foregone absorption).

    Extraction carries exactly the carbon at stake; a restoration of k ≤ lost
    units recovers at most the foregone absorption of the units lost (and
    nothing is counted through agents or anchors, see test 6).
    """
    eco, _ = build(case, 1000)
    lost = 500
    cut = run_extraction(eco, lost)
    release_eur, foregone_eur = _carbon_at_stake(eco, lost)
    npv = cut.extraction_npv
    assert npv.carbon_release == pytest.approx(release_eur, rel=1e-12)
    assert npv.carbon_foregone == pytest.approx(foregone_eur, rel=1e-9)
    assert npv.carbon_release + npv.carbon_foregone <= (
        release_eur + foregone_eur) * (1 + 1e-12)

    cost = RestorationCost(planting_cost_per_unit=50.0,
                           annual_maintenance_per_unit=10.0, maintenance_years=10)
    curve = _FOREST_SUCCESSION if succession else None
    for k in (100, lost):
        recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        restored = run_restoration(eco, k, cost, recovery, succession_curve=curve,
                                   time_horizon_years=60 if succession else 0,
                                   starting_state=cut)
        assert restored.restoration_npv.carbon_benefits <= foregone_eur * (1 + 1e-12)


def test_amazon_carbon_release_at_most_stock_times_scc():
    """Amazon: the capitalised release never exceeds the stock × SCC (C5)."""
    eco, area = build("amazon_forest", 4000)
    cp = eco.resource.carbon_profile
    stock_t = 4000 * (cp.stored_carbon_tonnes + cp.soil_carbon_tonnes)
    for units in (800, 4000):
        npv = run_extraction(eco, units).extraction_npv
        assert npv.carbon_release <= stock_t * SOCIAL_COST_OF_CARBON_EUR
    # Biomass alone is ~635 t CO₂/ha (173 Mg C/ha × 3.67): ~€106k/ha at the SCC
    biomass_per_ha = cp.stored_carbon_tonnes * AMAZON_TREES_PER_HA
    assert biomass_per_ha * SOCIAL_COST_OF_CARBON_EUR == pytest.approx(105_600, rel=0.01)


# ── 7. Text report and JSON agree (E3) ───────────────────────────────────────

_EURO = re.compile(r"€\s*(-?[\d,]+(?:\.\d+)?)|(-?[\d,]+(?:\.\d+)?)€")


def _json_numbers(obj, out):
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _json_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _json_numbers(v, out)
    return out


def _json_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _json_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _json_strings(v, out)
    return out


def _text_only_figures(result, text, include_steps):
    """€ figures of the text that are neither a JSON number nor quoted in a
    JSON string (literature figures in the Parameter Provenance notes are
    quoted verbatim in the JSON "calibration" block)."""
    parsed = json.loads(to_json(result, include_steps=include_steps))
    numbers = _json_numbers(parsed, [])
    quoted = " ".join(_json_strings(parsed, []))
    missing = []
    for match in _EURO.finditer(text):
        if match.group(0) in quoted:
            continue
        figure_text = match.group(1) or match.group(2)
        decimals = len(figure_text.split(".")[1]) if "." in figure_text else 0
        figure = float(figure_text.replace(",", ""))
        tol = 0.5 * 10 ** -decimals + 1e-9 * abs(figure)
        if not any(abs(v - figure) <= tol for v in numbers):
            missing.append(match.group(0))
    return missing


@pytest.mark.parametrize("include_steps", [True, False], ids=["steps", "summary_only"])
@pytest.mark.parametrize("case", list(CASES))
def test_text_report_figures_exist_in_json(case, include_steps):
    """Every € figure printed in the text report is a value of the JSON output."""
    eco, _ = build(case, 1000)
    result = run_extraction(eco, 500)
    missing = _text_only_figures(result, format_report(result), include_steps)
    assert not missing, f"text-only figures: {missing}"


@pytest.mark.parametrize("include_steps", [True, False], ids=["steps", "summary_only"])
@pytest.mark.parametrize("case", list(CASES))
def test_restoration_text_report_figures_exist_in_json(case, include_steps):
    """Same for the restoration report (partial restoration with maturation)."""
    eco, _ = build(case, 1000)
    cost = RestorationCost(planting_cost_per_unit=50.0,
                           annual_maintenance_per_unit=10.0, maintenance_years=10)
    recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    result = run_restoration(eco, 400, cost, recovery, units_lost=700,
                             succession_curve=_FOREST_SUCCESSION, time_horizon_years=60)
    missing = _text_only_figures(result, format_restoration_report(result), include_steps)
    assert not missing, f"text-only figures: {missing}"


# ── 8. JSON output is strict JSON (E8) ───────────────────────────────────────


def _reject_constant(name):
    raise ValueError(f"non-standard JSON constant {name}")


def _strict_json_cases():
    def extraction(case):
        return lambda: run_extraction(build(case, 1000)[0], 500)

    def restoration_no_soil_formation():
        eco, _ = build("forest", 1000)
        eco.resource = dataclasses.replace(
            eco.resource,
            substrate=dataclasses.replace(eco.resource.substrate, formation_rate=0.0),
        )
        cost = RestorationCost(planting_cost_per_unit=50.0,
                               annual_maintenance_per_unit=10.0, maintenance_years=10)
        recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
        return run_restoration(eco, 500, cost, recovery)

    params = [pytest.param(extraction(c), id=f"{c}_extract") for c in CASES]
    params.append(pytest.param(
        lambda: recovered_after_cut(1000, 500, 500), id="forest_restore"))
    params.append(pytest.param(
        restoration_no_soil_formation, id="forest_restore_zero_formation"))
    return params


@pytest.mark.parametrize("make_result", _strict_json_cases())
def test_json_output_is_strict(make_result):
    text = to_json(make_result(), include_steps=True)
    json.loads(text, parse_constant=_reject_constant)


@pytest.mark.parametrize("with_pricing", [False, True], ids=["static", "pricing"])
@pytest.mark.parametrize("case", list(CASES))
def test_direct_plus_cascade_is_agent_cost(case, with_pricing):
    """The result's direct/cascade split adds up to each agent's final cost,
    at the rate actually used (endogenous prices included)."""
    eco, _ = build(case, 1000, with_pricing=with_pricing)
    result = run_extraction(eco, 150)
    final = result.steps[-1].agent_annual_costs
    for d, c, total in zip(result.agent_direct_annual_costs,
                           result.agent_cascade_annual_costs, final):
        assert d + c == pytest.approx(total, rel=1e-12, abs=1e-9)
