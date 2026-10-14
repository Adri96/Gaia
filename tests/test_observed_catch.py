"""
Step 8i.5: the meadow's chain never produces less than the observed catch.

The owner's decision: a meadow that is fished for 8.91 kg/ha/yr (Campagne
et al. 2015, §3.2.4: 242,551 kg of 16 species sold at the Sète auction in
2010, over 27,220 ha of meadow) proves its food web supports at least that
much, and the commercial catch of 16 species is never the whole of it. So
link combinations whose sustainable catch at the regional depth (15 m) is
not above the observed catch / its largest commercial share (0.9, a
minimal margin, inferred) are inconsistent with the observation: the Monte
Carlo rejects them (and reports how many), and parsing searches the chain's
lowest value over the same conditioned space (gaia.production,
``catch_floor``).
"""

import copy
import random

import pytest

from gaia.cases import load_case
from gaia.ecosystem_io import case_from_dict
from gaia.production import (
    CatchFloorRejection,
    catch_floor_kg,
    central,
    chain,
    check_catch_floor,
    gross_value,
    net_range,
    parse_observed_catches,
    regional_catch,
)
from gaia.uncertainty import (
    _draw_all,
    _rederive_production,
    _with_values,
    production_entries,
    production_sampled,
    run_uncertainty,
    uncertainty_to_dict,
)

MEADOW = "Posidonia Meadow"
OBSERVED = "campagne_2015_sete_2010"
OBSERVED_KG = 242_551 / 27_220


def _meadow(case):
    return next(e for e in case.service_ledger if e["net_of"])


def _floor(doc):
    return next(e for e in doc["service_ledger"] if e.get("net_of"))["production_function"]["catch_floor"]


def test_the_observed_catch_is_a_sourced_fixed_quantity():
    doc = load_case("posidonia").document
    catch = parse_observed_catches(doc["observed_catches"])[OBSERVED]
    assert catch["value"] == pytest.approx(OBSERVED_KG, rel=1e-12) == pytest.approx(8.91, abs=0.005)
    assert catch["unit"] == "kg/ha/yr" and catch["distribution"] == "fixed"
    assert "242,551 kg" in catch["source"] and "27,220 ha" in catch["source"]
    assert "10.1016/j.marpolbul.2015.05.061" in catch["source"]
    with pytest.raises(ValueError, match="fixed, not sampled"):
        bad = copy.deepcopy(doc["observed_catches"])
        bad[OBSERVED].update(range=[8.0, 10.0], distribution="uniform")
        parse_observed_catches(bad)


def test_the_floor_is_the_observed_catch_over_its_largest_commercial_share():
    spec = _meadow(load_case("posidonia"))["production_function"]
    floor = spec["catch_floor"]
    share = floor["commercial_share"]
    assert share["value"] == 0.9 and share["status"] == "inferred" and share["distribution"] == "fixed"
    assert catch_floor_kg(spec) == pytest.approx(OBSERVED_KG / 0.9, rel=1e-12)
    # the central chain is well above it: 61.2 kg/ha/yr at 15 m, ~6.9 x the observed catch
    kg = regional_catch(spec)
    assert kg == pytest.approx(chain(central(spec))[-2][1], rel=1e-12)
    assert kg == pytest.approx(61.156, abs=0.01) and kg > 6 * OBSERVED_KG


def test_a_share_of_one_or_more_is_rejected():
    doc = copy.deepcopy(load_case("posidonia").document)
    _floor(doc)["commercial_share"]["value"] = 1.0
    with pytest.raises(ValueError, match="commercial_share.*never the whole"):
        case_from_dict(doc)
    doc = copy.deepcopy(load_case("posidonia").document)
    _floor(doc)["observed_catch"] = "nowhere"
    with pytest.raises(ValueError, match="unknown observed catch"):
        case_from_dict(doc)


def test_the_lowest_value_is_searched_in_the_conditioned_space():
    """Every link at its least favourable end at once gives 7.6 kg/ha/yr at
    15 m, below the observed catch: inconsistent with it, so the regional
    lowest is the floor's (gross = 9.90 kg x EUR 5.11)."""
    case = load_case("posidonia")
    entry = _meadow(case)
    spec = entry["production_function"]
    booked = entry["gross"] - entry["value"]
    price = central(spec)["first_sale_price"]
    unconditioned = dict(spec, catch_floor=None)
    assert net_range(unconditioned, 0.0)[0] / price == pytest.approx(7.60, abs=0.01)
    low, high = net_range(spec, booked)
    assert low == pytest.approx(OBSERVED_KG / 0.9 * price - booked, rel=1e-9) and low > 0.0
    assert high == net_range(unconditioned, booked)[1]


def _draws(case, n, seed):
    entries = production_entries(case)
    sampled = production_sampled(case, entries)
    by_name = {s.name: s for s in sampled}
    rng = random.Random(seed)
    accepted, rejected = [], 0
    for _ in range(n):
        doc = _with_values(case.document, _draw_all(sampled, rng), by_name, {})
        try:
            produced = _rederive_production(doc, entries)
        except CatchFloorRejection:
            rejected += 1
            continue
        spec = case_from_dict(doc).service_ledger[entries[0].index]["production_function"]
        accepted.append((regional_catch(spec), produced))
    return accepted, rejected


def test_no_accepted_draw_is_below_the_floor():
    """The documented case: the per-link draws never come near the floor
    (no draw rejected in 400), every one above it and every agent > EUR 0."""
    case = load_case("posidonia")
    floor = catch_floor_kg(_meadow(case)["production_function"])
    accepted, rejected = _draws(case, 400, 20261012)
    assert rejected == 0 and len(accepted) == 400
    assert all(kg > floor for kg, _ in accepted)
    assert all(net > 0.0 for _, produced in accepted for _, net in produced.values())


def test_draws_below_the_floor_are_rejected_and_counted_reproducibly():
    """A floor raised to 44.5 kg/ha/yr (a share of 0.2) cuts into the
    draws: those below it are rejected and drawn again, the run is
    reproducible with its seed and every accepted draw lies above it."""
    doc = copy.deepcopy(load_case("posidonia").document)
    _floor(doc)["commercial_share"]["value"] = 0.2
    case = case_from_dict(doc)
    spec = _meadow(case)["production_function"]
    floor = catch_floor_kg(spec)
    assert floor == pytest.approx(OBSERVED_KG / 0.2, rel=1e-12) and floor < regional_catch(spec)
    accepted, rejected = _draws(case, 200, 5)
    assert rejected > 0 and all(kg > floor for kg, _ in accepted)
    u = run_uncertainty(case, 50, draws=60, seed=5, tornado=False, normative=False)
    again = run_uncertainty(case, 50, draws=60, seed=5, tornado=False, normative=False)
    assert u.catch_floor_rejections > 0 and u.catch_floor_rejections == again.catch_floor_rejections
    assert u.summary == again.summary and u.production == again.production
    price = central(spec)["first_sale_price"]
    # no project depth: the meadow's gross is its regional chain
    assert u.production[MEADOW]["gross"]["min"] > floor * price
    assert uncertainty_to_dict(u)["draws_rejected_below_observed_catch"] == u.catch_floor_rejections


def test_check_catch_floor():
    spec = _meadow(load_case("posidonia"))["production_function"]
    check_catch_floor(spec)
    values = dict(central(spec), transfer_efficiency=0.03)
    assert gross_value(values) < catch_floor_kg(spec) * values["first_sale_price"]  # type: ignore[operator]
    with pytest.raises(CatchFloorRejection, match="inconsistent with the observed catch"):
        check_catch_floor(spec, values)


# ── Step 8i.4: the catch priced at the anchor, every agent > €0 ──────────────

PRICE = 41_056_589 / 8_034_993
CATCH_EUR = OBSERVED_KG * PRICE
DEPTHS = [((z, z), None) for z in (0.5, 5.0, 15.0, 30.0, 35.0, 40.0, 43.0, 50.0)] + [
    ((0.0, 44.0), None), ((30.0, 40.0), None), ((5.0, 15.0), None),
    ((10.0, 10.0), (15.0, 15.0)), ((12.0, 12.0), (13.0, 17.0)), ((43.0, 43.0), (44.0, 44.0)),
    ((0.5, 0.5), (1.0, 1.0)), ((30.0, 30.0), (35.0, 35.0))]


def test_the_fisheries_euros_are_the_observed_kg_at_the_anchor():
    case = load_case("posidonia")
    fisheries = [e for e in case.service_ledger if e["priced_catch"] is not None]
    assert {e["agent"] for e in fisheries} == {"Fish Populations", "Marine Invertebrates"}
    assert sum(e["value"] for e in fisheries) == pytest.approx(CATCH_EUR, rel=1e-12)
    assert all(e["value"] == pytest.approx(OBSERVED_KG * PRICE * e["share"], rel=1e-12) for e in fisheries)
    meadow = _meadow(case)
    # net_of equals the fisheries total at 15 m (the regional base) ...
    assert meadow["gross"] - meadow["value"] == pytest.approx(CATCH_EUR, rel=1e-12)
    # ... so the point-estimate total is the meadow's gross: only the split moves
    assert meadow["value"] + sum(e["value"] for e in fisheries) == pytest.approx(meadow["gross"], rel=1e-12)
    # and the meadow's regional lowest value is 1/0.9 - 1 of the catch
    assert net_range(meadow["production_function"], CATCH_EUR)[0] == pytest.approx(CATCH_EUR / 9, rel=1e-9)


@pytest.mark.parametrize("depth", DEPTHS)
def test_every_agent_is_positive_at_every_depth_and_in_every_draw(depth):
    (a, b), limit = depth
    at = load_case("posidonia").with_project_depth(a, b, depth_limit=limit)
    meadow = _meadow(at)
    booked = sum(e["value"] for e in at.service_ledger if e["service"] in meadow["net_of"])
    assert booked == pytest.approx(CATCH_EUR, rel=1e-12)
    assert net_range(meadow["production_function"], booked)[0] > 0.0
    assert all(e["value"] > 0.0 for e in at.service_ledger)
    for kwargs in (dict(site_intensity="none"), dict(site_share=0.0), {}):
        eco = at.build_ecosystem(**kwargs)
        assert all(x.dependency_weight * x.annual_value(1.0) > 0.0 for x in eco.agents), kwargs
    u = run_uncertainty(at, 10, draws=30, seed=7, tornado=False, normative=False,
                        build_kwargs=dict(site_intensity="none"))
    assert all(block["draws_at_or_below_zero"] == 0 and block["net"]["min"] > 0.0
               for block in u.production.values())
