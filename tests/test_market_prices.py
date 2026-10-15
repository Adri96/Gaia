"""
Step 8h.4: market prices are depth-independent and anchor every chain.

The owner's decision: "the sale price of fish does not depend on the depth
at which it was caught, and that should anchor the prices of the rest".
Depth (and the site's depth limit) changes only quantities (NPP → consumer
production → kg caught); the € per kg is one sourced anchor in the case
file ($.market_prices), referenced by every production-function chain.
"""

import copy

import pytest

from gaia.cases import load_case
from gaia.ecosystem_io import case_from_dict
from gaia.production import MARKET_PRICE_PARAMETERS, central, chain, parse_market_prices

ANCHOR = "white_fish_first_sale_catalonia_2014"
CHAINS = ("Posidonia Meadow", "Epiphytes & Algae")
DEPTHS = [None, ((5.0, 5.0), None), ((15.0, 15.0), None), ((35.0, 35.0), None), ((30.0, 40.0), None),
          ((10.0, 10.0), (15.0, 15.0)), ((12.0, 12.0), (13.0, 17.0)), ((50.0, 50.0), None)]


def _chains(case):
    return {e["agent"]: e for e in case.service_ledger if e["production_function"] is not None}


def _at(case, depth):
    return case if depth is None else case.with_project_depth(*depth[0], depth_limit=depth[1])


def test_one_sourced_price_anchors_every_chain():
    """The case declares the price once; both chains reference it (no copy
    typed into a chain) and take its value, source and status."""
    case = load_case("posidonia")
    doc = case.document
    anchor = parse_market_prices(doc["market_prices"])[ANCHOR]
    assert anchor["value"] == pytest.approx(41_056_589 / 8_034_993, rel=1e-12)
    assert anchor["status"] == "verified" and "ge3m-4jgm" in anchor["source"] and anchor["unit"] == "€/kg"
    assert anchor.get("distribution", "fixed") == "fixed"
    raw = [e["production_function"]["parameters"]["first_sale_price"]
           for e in doc["service_ledger"] if "production_function" in e]
    assert raw == [{"market_price": ANCHOR}] * len(CHAINS)
    for entry in _chains(case).values():
        p = entry["production_function"]["parameters"]["first_sale_price"]
        assert p["market_price"] == ANCHOR and p["value"] == anchor["value"] and p["source"] == anchor["source"]
        assert entry["production_function"]["paths"]["first_sale_price"] == f"$.market_prices.{ANCHOR}"
    assert set(_chains(case)) == set(CHAINS)


@pytest.mark.parametrize("depth", DEPTHS)
def test_the_price_is_the_same_at_every_depth_and_in_every_chain(depth):
    """Only quantities move with depth: the € per kg of every chain is the
    anchor's, at 5, 15, 35 m, a band, a site's limit, beyond 44 m."""
    case = load_case("posidonia")
    anchor = parse_market_prices(case.document["market_prices"])[ANCHOR]["value"]
    at = _at(case, depth)
    for entry in _chains(at).values():
        values = central(entry["production_function"])
        assert values["first_sale_price"] == anchor
        steps = {what: v for what, v, _ in chain(values)}
        caught, euros = steps["sustainable catch"], steps["food value at first-sale prices"]
        assert euros / caught == pytest.approx(anchor, rel=1e-12)
        gross = entry["gross"] if entry["gross"] is not None else entry["value"]
        assert gross == pytest.approx(caught * anchor, rel=1e-9)


def test_depth_moves_quantities_not_prices():
    """From 5 to 35 m the kg caught fall with the production; the € per kg
    does not, and the euros fall in exactly the same proportion as the kg."""
    case = load_case("posidonia")
    rows = []
    for z in (5.0, 15.0, 35.0):
        for agent, entry in _chains(case.with_project_depth(z, z)).items():
            steps = {what: v for what, v, _ in chain(central(entry["production_function"]))}
            rows.append((agent, z, steps["sustainable catch"], steps["food value at first-sale prices"]))
    for agent in CHAINS:
        mine = [r for r in rows if r[0] == agent]
        assert mine[0][2] > mine[1][2] > mine[2][2] > 0.0
        prices = {round(euros / kg, 12) for _, _, kg, euros in mine}
        assert len(prices) == 1


def test_the_fisheries_agents_do_not_depend_on_depth():
    """Fish Populations and Marine Invertebrates (Campagne et al. 2015, the
    commercial catch) stay depth-independent (the owner's decision): their
    ledger values and agent values are the same at every depth."""
    case = load_case("posidonia")
    names = ("Fish Populations", "Marine Invertebrates")

    def values(c):
        ledger = {e["agent"]: e["value"] for e in c.service_ledger if e["agent"] in names}
        eco = c.build_ecosystem(site_intensity="none")
        agents = {a.name: a.dependency_weight * a.annual_value(1.0) for a in eco.agents if a.name in names}
        return ledger, agents

    base = values(case)
    for depth in DEPTHS[1:]:
        assert values(_at(case, depth)) == base


def test_a_price_typed_into_a_chain_is_rejected():
    """With market prices declared, a chain may not carry its own price:
    nothing can drift from the anchor; an unknown anchor is rejected too."""
    doc = copy.deepcopy(load_case("posidonia").document)
    entry = next(e for e in doc["service_ledger"] if "production_function" in e)
    entry["production_function"]["parameters"]["first_sale_price"] = dict(
        parse_market_prices(doc["market_prices"])[ANCHOR])
    with pytest.raises(ValueError, match="references one"):
        case_from_dict(doc)
    entry["production_function"]["parameters"]["first_sale_price"] = {"market_price": "no_such_price"}
    with pytest.raises(ValueError, match="unknown market price 'no_such_price'"):
        case_from_dict(doc)
    entry["production_function"]["parameters"]["first_sale_price"] = {"market_price": ANCHOR}
    entry["production_function"]["parameters"]["transfer_efficiency"] = {"market_price": ANCHOR}
    with pytest.raises(ValueError, match="only a price"):
        case_from_dict(doc)
    assert MARKET_PRICE_PARAMETERS == ("first_sale_price",)


def test_a_sampled_anchor_is_drawn_once_for_every_chain():
    """Were the price uncertain, the Monte Carlo would draw the anchor itself
    (its document path), so every chain takes the same price in a draw."""
    from gaia.uncertainty import production_entries, production_sampled

    doc = copy.deepcopy(load_case("posidonia").document)
    anchor = doc["market_prices"][ANCHOR]
    anchor.update(range=[5.0, 6.0], distribution="triangular")
    case = case_from_dict(doc)
    sampled = [s for s in production_sampled(case, production_entries(case)) if s.name.endswith("first_sale_price")]
    assert [s.path for s in sampled] == [f"$.market_prices.{ANCHOR}"] * len(CHAINS)
    assert not sampled[0].same_as and all(s.same_as == sampled[0].name for s in sampled[1:])


def test_the_price_is_fixed_in_every_monte_carlo_draw():
    from gaia.uncertainty import run_uncertainty

    case = load_case("posidonia").with_project_depth(35.0, 35.0)
    u = run_uncertainty(case, 10, draws=20, seed=4, tornado=False, normative=False,
                        build_kwargs=dict(site_intensity="none"))
    names = {s.name for s in u.sampled}
    assert not any(n.endswith("first_sale_price") for n in names)
    assert all(b["draws_at_or_below_zero"] == 0 for b in u.production.values())


# ── Steps 8i.2 / 8i.4: one anchor, which prices the observed catch too ──────

FISHERIES = ("Fish Populations", "Marine Invertebrates")
FISH_SERVICE = "Commercial fisheries: meadow-associated fish"
INVERTEBRATE_SERVICE = "Commercial fisheries: meadow-associated invertebrates (sea urchin, cuttlefish)"
VALID_DEPTHS = DEPTHS + [((41.0, 41.0), None), ((42.5, 42.5), None), ((43.0, 43.0), None), ((44.0, 44.0), None),
                         ((0.0, 0.0), None), ((0.0, 44.0), None), ((43.0, 43.0), (44.0, 44.0))]


def test_the_white_fish_price_is_the_one_anchor():
    """Step 8i.2 (the owner's decision): no catch-weighted price; the
    white-fish price is the only market price declared."""
    doc = load_case("posidonia").document
    assert set(doc["market_prices"]) == {ANCHOR}
    assert "8i.2" in doc["market_prices"][ANCHOR]["note"]


def test_the_observed_catch_is_priced_at_the_anchor():
    """Step 8i.4 (the owner's decision): Campagne et al.'s catch, 242,551 kg
    over 27,220 ha (§3.2.4), is valued at the single anchor, the white-fish
    price (no per-group prices), split 14/16 fish and 2/16 invertebrates.
    The € are derived (priced_catch: quantity × anchor × share) and parsing
    checks them; the Step 8i.3 flag is gone."""
    case = load_case("posidonia")
    doc = case.document
    kg_ha = 242_551 / 27_220
    white = 41_056_589 / 8_034_993
    ledger = {e["service"]: e for e in case.service_ledger}
    for service, share in ((FISH_SERVICE, 14 / 16), (INVERTEBRATE_SERVICE, 2 / 16)):
        entry = ledger[service]
        assert entry["value"] == pytest.approx(kg_ha * white * share, rel=1e-12)
        assert entry["priced_catch"]["market_price"] == ANCHOR and entry["share"] == pytest.approx(share)
    total = ledger[FISH_SERVICE]["value"] + ledger[INVERTEBRATE_SERVICE]["value"]
    assert total == pytest.approx(kg_ha * white, rel=1e-12) and round(total, 2) == 45.53
    assert (round(ledger[FISH_SERVICE]["value"], 3), round(ledger[INVERTEBRATE_SERVICE]["value"], 3)) == (39.840, 5.691)
    # the meadow is net of exactly that total at the regional depth (15 m)
    meadow = next(e for e in case.service_ledger if e["net_of"])
    assert meadow["gross"] - meadow["value"] == pytest.approx(total, rel=1e-12)
    for name in FISHERIES:
        entry = next(e for e in doc["service_ledger"] if e["agent"] == name)
        agent = next(a for a in doc["agents"] if a["name"] == name)
        for note in (entry["note"], agent["annual_value_per_ha"]["note"]):
            assert "Step 8i.4" in note and "PRICE BASIS FLAGGED" not in note
    # a typed value off the derived one is rejected
    bad = copy.deepcopy(doc)
    next(e for e in bad["service_ledger"] if e["service"] == FISH_SERVICE)["value"] = 30.625
    with pytest.raises(ValueError, match="observed catch × its market price × its share"):
        case_from_dict(bad)
    bad = copy.deepcopy(doc)
    next(e for e in bad["service_ledger"] if e["service"] == FISH_SERVICE)["priced_catch"]["market_price"] = "sete"
    with pytest.raises(ValueError, match="unknown market price"):
        case_from_dict(bad)


def test_without_the_conditioning_the_anchor_priced_catch_would_be_rejected():
    """Why Step 8i.5 comes with 8i.4: every link at its least favourable end
    at once gives EUR 38.83 gross, below the EUR 45.53 netted out; that
    corner (7.6 kg/ha/yr at 15 m) is below the observed catch, so it is
    ruled out by the conditioning. Without it parsing rejects the case
    (the validation is not weakened)."""
    doc = copy.deepcopy(load_case("posidonia").document)
    del next(e for e in doc["service_ledger"] if e.get("net_of"))["production_function"]["catch_floor"]
    with pytest.raises(ValueError, match="could bring the agent to €0"):
        case_from_dict(doc)


@pytest.mark.parametrize("depth", VALID_DEPTHS)
def test_every_agent_is_positive_at_every_valid_depth(depth):
    """Every agent, the fisheries agents and the meadow net of their catch
    included, carries a positive value at every valid depth and site limit
    (Core Valuation Principles (b))."""
    at = _at(load_case("posidonia"), depth)
    assert all(e["value"] > 0.0 for e in at.service_ledger)
    eco = at.build_ecosystem(site_intensity="none")
    values = {a.name: a.dependency_weight * a.annual_value(1.0) for a in eco.agents}
    assert all(v > 0.0 for v in values.values())
    assert all(values[name] > 0.0 for name in FISHERIES)
