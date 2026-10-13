"""
Gaia — production functions: from primary production to what people eat
(Step 8e.6, 8f, 8g; PROJECT_DEFINITION.md, "Core Valuation Principles", (d), (e)).

Where no stated-preference value exists, a foundation species is valued
through the food its primary production supports. The "trophic_transfer"
model follows the energy from the primary producers to the catch:

    Σ over the producers:
      NPP (g dry weight/m²/yr) × carbon_fraction   (or NPP in g C/m²/yr)
        × food_web_share                    → g C/m²/yr entering the food web
      (the share not buried: carbon has one owner, decision D3; the
      buried part is valued by gaia.carbon)
    × 10                                    → kg C/ha/yr entering the food web
    × transfer_efficiency^(catch_trophic_level − 1)
                                            → kg C/ha/yr of consumer production
    × wet_weight_per_carbon                 → kg (wet)/ha/yr of fish produced
    × sustainable_catch_share               → kg/ha/yr that can be caught
    × first_sale_price                      → €/ha/yr

(the primary-production-required relation of Pauly & Christensen 1995,
inverted, with a sustainable exploitation rate). The result is the GROSS
value of the food supported; the service ledger books it net of the catch
already counted in other entries (``net_of``), so nothing is counted twice.

A ledger entry carries the model as ``production_function``:
{"model": "trophic_transfer", "producer": "<the main producer, e.g. the
plant's leaves and rhizomes>", "parameters": {<name>: {"value"*, "unit"*,
"label"*, "source"*, "status"* ("verified" | "derived" | "secondary" |
"inferred"), "range": [low, high], "distribution", "distribution_basis"}},
"producers": [{"name"*, "description"*,
"parameters"*: {...}}], "depth_production": {...}, "comparison":
{"metric"*, "unit"*, "rows"*: [{"ecosystem"*, "value" | "low" and "high",
"source"*, "note"}]}}.

``parameters`` holds the links of the chain: the main producer's NPP
(``npp_dry_weight`` and ``carbon_fraction``, or ``npp_carbon``) and
``food_web_share``, then the five links from the food web to the catch
(``CHAIN_PARAMETERS``). ``producers`` (Step 8f.2, optional) adds other
primary producers whose production enters the same food web (for
Posidonia: the roots), each with ``npp_dry_weight`` and
``carbon_fraction``, or ``npp_carbon``, and its own ``food_web_share``.
Their parameters are named ``<name>.<parameter>`` (e.g.
"roots.npp_dry_weight") in the parsed form. Parsing checks that the entry's
``gross`` is the chain's result.

Depth → primary production (Step 8g.1). A marine primary producer
(seagrass, macroalgae) lives on light, and light falls with depth
(Beer–Lambert, I(z) = I0·e^(−Kd·z)). Below light saturation net production
is gross photosynthesis, proportional to the light, minus a respiration
that does not depend on it, so it falls exponentially and reaches zero at
the compensation depth, where photosynthesis only pays for respiration.
One shape, ``DEPTH_MODEL`` ("light_limited_exponential"):

    NPP(z) = P_ref · (e^(−k·z) − e^(−k·z_max)) / (e^(−k·z_ref) − e^(−k·z_max)),
             0 <= z < z_max

with three hyperparameters per species (``DEPTH_PARAMETERS``):
``npp_at_reference_depth`` (P_ref, the production at the reference depth
z_ref, in the unit of the NPP it replaces), ``decline_rate`` (k, 1/m; it is
the light attenuation coefficient Kd when production is light-limited
throughout) and ``depth_limit`` (z_max, m, where production reaches zero;
a project depth is valued at any depth, its site's depth limit lying below
it, see below). NPP(z) declines
monotonically and is convex, so the production at a mean depth is below the
mean production over the depths around it. The block:

    "depth_production": {"model"*: "light_limited_exponential",
      "output"*: the producer parameter it replaces ("npp_dry_weight" or
        "npp_carbon"; that parameter is then absent from "parameters"),
      "reference_depth_m"*: z_ref,
      "parameters"*: {npp_at_reference_depth, decline_rate, depth_limit},
        each a parameter as above,
      "depth_limit_margin"*: a parameter (fixed, m): the least depth between
        a living meadow and its site's depth limit (Step 8g.7, below),
      "regional_depth"*: the depth of the reference resource, either
        {"distribution": [{"from_m", "to_m", "share"}, ...], "source"*,
        "status"*, "note"} (production averaged over each band, weighted by
        its share of the area) or {"mean_m", "source"*, "status"*, "note"},
      "project_depth": the depth of the affected resource, {"from_m",
        "to_m", "source", "depth_limit"} (a single depth has from_m = to_m;
        "depth_limit", the site's depth limit, a parameter with optional
        "truncated_below" and "coupled", derived when absent; set by
        ``with_project_depth``, e.g. ``gaia run ... --depth-m``),
      "data": [{"site"*, "depth_m"*, "value"*, "source"*, "status"*}],
        the measurements the hyperparameters were fitted to,
      "fit": free text, how they were fitted}

The main producer's NPP is then derived: the production averaged over the
project's depth (or, without one, over the regional depth distribution).
Each hyperparameter is a link the Monte Carlo samples; every draw
recomputes the NPP, the chain and the net value.

The site's depth limit at a project depth (Step 8g.7). Any project depth
>= 0 is valued, never rejected: a meadow that lives at depth z proves that
its site's depth limit lies deeper than z. So the project's production
uses the site's depth limit z_site, the documented (regional) depth limit
conditioned on lying deeper than the project's deepest depth plus
``depth_limit_margin`` (``site_depth_limit``: the documented distribution
truncated below that floor, its central value the conditional mode,
max(z_max, floor); within two margins of the range's deepest value, or
below it, extended to [floor, floor + margin], triangular with its mode at
the floor). The Monte Carlo draws z_site comonotone with z_max (the same
uniform draw through the conditioned distribution: above the floor they
are the same draw). The site's curve keeps the regional light-driven term
(P_ref and k, normalised at z_ref with the regional z_max) and reaches zero
at z_site:

    NPP_site(z) = P_ref · (e^(−k·z) − e^(−k·z_site)) / (e^(−k·z_ref) − e^(−k·z_max)),

the regional curve when z_site = z_max, defined for any z_site > 0. The
regional production (the basis of what an entry is net of, below) keeps
the regional z_max.

Net of what is already counted, at a project depth (Step 8g.1). The
services an entry is net of (for Posidonia, the commercial catch of
Campagne et al. 2015, €35/ha/yr) are regional values per hectare of the
reference resource, i.e. at the regional depth. At a project depth the part
of them the hectare's own production supports scales with that production:
the entry subtracts ``net_of_scale`` × their booked values, where the scale
is NPP(project) / NPP(regional) (1 without a project depth, so the regional
run subtracts exactly the booked values). The net value is then
NPP(project) × (food per unit of NPP − booked / NPP(regional)) + the other
producers' food, positive at every depth whenever the regional
chain's lowest value exceeds what it is net of (parsing checks it).

Market prices anchor every chain (Step 8h.4, the owner's decision). The
€/kg (or € per unit of any consumable) a chain applies is a market price:
the sale price of fish does not depend on the depth at which it was caught,
so depth (and the site's depth limit) changes only QUANTITIES (NPP →
consumer production → catch, in kg) and never the price. A case declares
its sourced prices once, at the top level,

    "market_prices": {"<name>": {"value"*, "unit"*, "label"*, "source"*,
      "status"*, "distribution", "distribution_basis", "range", "note"}}

and every chain's price parameter (``MARKET_PRICE_PARAMETERS``) references
one, ``{"market_price": "<name>"}``: the same anchor for every chain that
values the same catch (for Posidonia the meadow's and the epiphytes'). A
case that declares market prices may not type a price into a chain, so no
chain can drift from the anchor; the parsed parameter carries the anchor's
name (``market_price``) and its document path is the anchor's, so a
sampled price would be drawn once for every chain. ``with_project_depth``
never touches it.

Uncertainty (Step 8f.3): each link has its own distribution for the Monte
Carlo (gaia.uncertainty), which samples the links one by one and recomputes
the chain, the gross and the net value in every draw: "triangular" (the
default with a range; mode at the value), "uniform", "lognormal" (median at
the value, the range read as its central 95% and truncated at the range
ends) or "fixed" (the default without a range: not sampled), with an
optional "distribution_basis" saying why. Every distribution stays inside
the documented range, so the chain's lowest value is ``net_range``'s low
end, and parsing of the ledger requires it to be > 0 (no draw can bring the
agent to €0). No third-party dependencies.
"""

import copy
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

MODEL = "trophic_transfer"

# the links from the food web to the catch, in chain order; every one is required
CHAIN_PARAMETERS: Tuple[str, ...] = (
    "transfer_efficiency",
    "catch_trophic_level",
    "wet_weight_per_carbon",
    "sustainable_catch_share",
    "first_sale_price",
)

# the parameter sets a producer may give (the main one and each additional one)
PRODUCER_PARAMETERS: Tuple[Tuple[str, ...], ...] = (
    ("npp_dry_weight", "carbon_fraction", "food_web_share"),
    ("npp_carbon", "food_web_share"),
)

# the main producer's NPP given in dry weight, then the chain (the full set
# of a production function whose main producer is given in dry weight)
PARAMETERS: Tuple[str, ...] = PRODUCER_PARAMETERS[0] + CHAIN_PARAMETERS

STATUSES: Tuple[str, ...] = ("verified", "derived", "secondary", "inferred")

DISTRIBUTIONS: Tuple[str, ...] = ("triangular", "uniform", "lognormal", "fixed")
"""How the Monte Carlo samples a link (Step 8f.3; see the module docstring)."""

MARKET_PRICE_PARAMETERS: Tuple[str, ...] = ("first_sale_price",)
"""Chain parameters that are market prices (€ per unit of what people
consume): taken from the case's ``market_prices`` anchors (Step 8h.4)."""

_MARKET_PRICE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

DEPTH_MODEL = "light_limited_exponential"
DEPTH_PARAMETERS: Tuple[str, ...] = ("npp_at_reference_depth", "decline_rate", "depth_limit")
DEPTH_PREFIX = "depth."
"""Prefix of the depth hyperparameters in the parsed parameters
("depth.decline_rate"); "depth" is not a producer name."""

SITE_LIMIT = "site_depth_limit"
"""The site's depth limit at a project depth (Step 8g.7), a parsed parameter
("depth.site_depth_limit") stored in the project depth
(``project_depth.depth_limit``)."""

DEPTH_SHARED: Tuple[str, ...] = tuple(DEPTH_PREFIX + n for n in ("decline_rate", "depth_limit", SITE_LIMIT))
"""The depth function's shape: one light field, drawn once by the Monte
Carlo for every production function that documents it identically."""

USER_STATUS = "user-supplied"
"""The status of a site's depth limit given by the project (Step 8g.10)."""

DEPTH_GRID = 41
"""Points per depth-shape hyperparameter (decline rate, depth limit) when
the lowest and highest value of a chain is searched (``net_range``)."""

# parameters that must lie in (0, 1]
_FRACTIONS = ("carbon_fraction", "food_web_share", "transfer_efficiency", "sustainable_catch_share")

_PRODUCER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_DEFAULT_PRODUCER = "the plant"


# ── Depth → primary production (Step 8g.1) ───────────────────────────────────


def depth_npp(depth: float, npp_at_reference_depth: float, decline_rate: float,
              depth_limit: float, reference_depth: float, site_limit: Optional[float] = None) -> float:
    """Net primary production at ``depth`` (m) of a marine primary producer
    (``DEPTH_MODEL``; see the module docstring), in the unit of
    ``npp_at_reference_depth``. With ``site_limit`` (Step 8g.7), the
    production of a site whose own depth limit it is: the regional curve's
    light-driven term (P_ref, k, normalised with the regional depth limit)
    with the site's limit where its production reaches zero.

    Raises:
        ValueError: For a depth < 0 or at or below the depth limit (where
            production is zero: such a resource is not valued, never at €0),
            or for hyperparameters out of their domain.
    """
    limit = _limit(npp_at_reference_depth, decline_rate, depth_limit, reference_depth, site_limit)
    if not (math.isfinite(depth) and 0.0 <= depth < limit):
        raise ValueError(
            f"depth {depth:g} m is outside the producer's depth range [0, {limit:g}) m: "
            f"production reaches zero at its depth limit, {limit:g} m"
        )
    return npp_at_reference_depth * _shape(depth, decline_rate, limit) / _shape(
        reference_depth, decline_rate, depth_limit)


def mean_depth_npp(from_m: float, to_m: float, npp_at_reference_depth: float, decline_rate: float,
                   depth_limit: float, reference_depth: float, site_limit: Optional[float] = None) -> float:
    """The mean of ``depth_npp`` over the depths [from_m, to_m] (uniform
    over the band; exact, the integral of the exponential): the production
    per unit area of a resource spread evenly over that band. A band of zero
    width is the production at that depth."""
    if from_m == to_m:
        return depth_npp(from_m, npp_at_reference_depth, decline_rate, depth_limit, reference_depth, site_limit)
    if not 0.0 <= from_m < to_m:
        raise ValueError(f"a depth band needs 0 <= from_m < to_m, got [{from_m:g}, {to_m:g}]")
    depth_npp(from_m, npp_at_reference_depth, decline_rate, depth_limit, reference_depth, site_limit)
    limit = depth_limit if site_limit is None else site_limit
    if not to_m < limit:
        raise ValueError(
            f"depth {to_m:g} m is outside the producer's depth range [0, {limit:g}) m: "
            f"production reaches zero at its depth limit, {limit:g} m"
        )
    k = decline_rate
    mean_exp = (math.exp(-k * from_m) - math.exp(-k * to_m)) / (k * (to_m - from_m))
    shape = mean_exp - math.exp(-k * limit)
    return npp_at_reference_depth * shape / _shape(reference_depth, k, depth_limit)


def profile_npp(bands: Sequence[Tuple[float, float, float]], npp_at_reference_depth: float,
                decline_rate: float, depth_limit: float, reference_depth: float,
                site_limit: Optional[float] = None) -> float:
    """The area-weighted mean production over depth bands [(from_m, to_m,
    share)], the shares summing to 1."""
    return sum(share * mean_depth_npp(a, b, npp_at_reference_depth, decline_rate, depth_limit,
                                      reference_depth, site_limit)
               for a, b, share in bands)


def _limit(p_ref: float, k: float, depth_limit: float, reference_depth: float,
           site_limit: Optional[float]) -> float:
    _check_shape(p_ref, k, depth_limit, reference_depth)
    if site_limit is None:
        return depth_limit
    if not (math.isfinite(site_limit) and site_limit > 0.0):
        raise ValueError(f"depth production: a site's depth limit is > 0 m, got {site_limit!r}")
    return site_limit


def _shape(depth: float, k: float, depth_limit: float) -> float:
    return math.exp(-k * depth) - math.exp(-k * depth_limit)


def _check_shape(p_ref: float, k: float, depth_limit: float, reference_depth: float) -> None:
    if not (p_ref > 0.0 and k > 0.0 and 0.0 <= reference_depth < depth_limit
            and all(math.isfinite(x) for x in (p_ref, k, depth_limit, reference_depth))):
        raise ValueError(
            f"depth production: needs npp_at_reference_depth > 0, decline_rate > 0 and "
            f"0 <= reference depth < depth_limit, got {p_ref!r}, {k!r}, {reference_depth!r}, {depth_limit!r}"
        )


def _depth_values(values: Dict[str, float]) -> Tuple[float, float, float]:
    return (values[DEPTH_PREFIX + "npp_at_reference_depth"], values[DEPTH_PREFIX + "decline_rate"],
            values[DEPTH_PREFIX + "depth_limit"])


def depth_bands(depth: Dict[str, Any], which: str) -> List[Tuple[float, float, float]]:
    """The bands [(from_m, to_m, share)] of a parsed depth block's
    "regional" or "project" depth (a single depth is a band of zero width)."""
    spec = depth[which]
    return [(float(a), float(b), float(w)) for a, b, w in spec["bands"]]


def npp_over(depth: Dict[str, Any], values: Dict[str, float], which: str) -> float:
    """The production of a parsed depth block at its "regional" or
    "project" depth, at the hyperparameter ``values`` (at the project
    depth, with the site's depth limit, Step 8g.7)."""
    p_ref, k, z_max = _depth_values(values)
    site = values.get(DEPTH_PREFIX + SITE_LIMIT) if which == "project" else None
    return profile_npp(depth_bands(depth, which), p_ref, k, z_max, depth["reference_depth_m"], site)


def deepest_allowed(spec: Dict[str, Any]) -> Optional[float]:
    """The depth (m) a project depth must stay shallower than: the deepest
    depth limit the project gave for its site (``--depth-limit-m``, Step
    8g.10); None otherwise (any depth is valued: the site's depth limit is
    conditioned to lie below it, Step 8g.7) or without a depth model."""
    site = spec["parameters"].get(DEPTH_PREFIX + SITE_LIMIT) if spec.get("depth") is not None else None
    if site is None or site["status"] != USER_STATUS:
        return None
    return _support(site)[1]


class DepthExtrapolationWarning(UserWarning):
    """A project depth, or a site's depth limit given, beyond the deepest
    depth limit documented for the producer (Step 8h.2): still valued
    (> €0), but the depth function is extrapolated there."""


def deepest_documented(spec: Dict[str, Any]) -> Optional[float]:
    """The deepest depth limit documented for a production function's
    producer (m): the upper end of its regional ``depth_limit`` (its range,
    else its value; for Posidonia 44 m, the deepest meadows); None without a
    depth model."""
    if spec.get("depth") is None:
        return None
    return _support(spec["parameters"][DEPTH_PREFIX + "depth_limit"])[1]


def extrapolation_warnings(spec: Dict[str, Any], who: str = "") -> List[str]:
    """Plain-words warnings (Step 8h.2) when the project's depth (its
    deepest end for a band) or a site's depth limit given by the project
    (``--depth-limit-m``, its deepest end for a range) lies beyond the
    deepest depth limit documented (``deepest_documented``). Never a
    rejection: the value is computed and positive, but it extrapolates the
    depth function beyond the range its sources document. Empty otherwise
    (and without a project depth)."""
    depth = spec.get("depth")
    if depth is None or depth["project"] is None:
        return []
    documented = deepest_documented(spec)
    assert documented is not None
    limit = spec["parameters"][DEPTH_PREFIX + "depth_limit"]
    low, high = _support(limit)
    span = f"{low:g}-{high:g} m" if low < high else f"{high:g} m"
    who = who or f"the {spec['producer']}"
    basis = f"the deepest depth limit documented for {who}, {documented:g} m (its documented depth limit: {span})"
    tail = ("Gaia still values it (every agent > €0), but the depth function is extrapolated beyond "
            "its documented range: treat the value as an extrapolation")
    out = []
    a, b, _ = depth["project"]["bands"][0]
    deepest = max(z for _, z, _ in depth["project"]["bands"])
    if deepest > documented:
        given = f"{a:g} m" if a == b else f"{a:g}-{b:g} m (its deep end, {deepest:g} m)"
        out.append(f"The project depth {given} lies beyond {basis}. {tail}.")
    site = spec["parameters"].get(DEPTH_PREFIX + SITE_LIMIT)
    if site is not None and site["status"] == USER_STATUS:
        top = _support(site)[1]
        if top > documented:
            given = f"{top:g} m" if _support(site)[0] == top else f"{top:g} m at its deepest"
            out.append(f"The site's depth limit given (--depth-limit-m, {given}) lies beyond {basis}. {tail}.")
    return out


def _support(p: Dict[str, Any]) -> Tuple[float, float]:
    """(lowest, highest) value a parameter can take: its range, raised to
    the value it is truncated below (Step 8g.7); its value without a range."""
    if not p.get("range"):
        return p["value"], p["value"]
    low, high = p["range"]
    floor = p.get("truncated_below")
    return (max(low, floor) if floor is not None else low), high


def _central(p: Dict[str, Any]) -> float:
    """A parameter's central value: its value, raised to the value its
    distribution is truncated below (the conditional mode of a triangular
    one; Step 8g.7)."""
    floor = p.get("truncated_below")
    return max(p["value"], floor) if floor is not None else p["value"]


def net_of_scale(spec: Dict[str, Any], values: Optional[Dict[str, float]] = None) -> float:
    """NPP(project depth) / NPP(regional depth): the factor on the services
    the entry is net of (see the module docstring); 1 without a depth model
    or a project depth."""
    depth = spec.get("depth")
    if depth is None or depth["project"] is None:
        return 1.0
    values = central(spec) if values is None else values
    return npp_over(depth, values, "project") / npp_over(depth, values, "regional")


def net_value(spec: Dict[str, Any], gross: float, booked: float) -> float:
    """The entry's net value: gross − net_of_scale × the booked values of
    the services it is net of."""
    return gross - net_of_scale(spec) * booked


# ── The chain ────────────────────────────────────────────────────────────────


def _producer_names(values: Dict[str, float]) -> List[str]:
    """Names of the additional producers in ``values``, in order."""
    return list(dict.fromkeys(k.split(".", 1)[0] for k in values
                              if "." in k and not k.startswith(DEPTH_PREFIX)))


def _carbon(values: Dict[str, float], prefix: str = "") -> float:
    if f"{prefix}npp_carbon" in values:
        return values[f"{prefix}npp_carbon"]
    return values[f"{prefix}npp_dry_weight"] * values[f"{prefix}carbon_fraction"]


def producer_carbon(values: Dict[str, float]) -> List[Tuple[str, float, float]]:
    """[(producer, net primary production in g C/m²/yr, share entering the
    food web)], the main producer ("") first."""
    out = [("", _carbon(values), values["food_web_share"])]
    for name in _producer_names(values):
        out.append((name, _carbon(values, f"{name}."), values[f"{name}.food_web_share"]))
    return out


def chain(values: Dict[str, float], producer: str = _DEFAULT_PRODUCER) -> List[Tuple[str, float, str]]:
    """The steps of the chain, [(what, value, unit)], the last one in €/ha/yr."""
    producers = producer_carbon(values)
    steps: List[Tuple[str, float, str]] = []
    dry = "npp_dry_weight" in values
    if len(producers) == 1:
        if dry:
            steps.append(("net primary production", values["npp_dry_weight"], "g DW/m²/yr"))
        steps.append(("net primary production, carbon", producers[0][1], "g C/m²/yr"))
    else:
        if dry:
            steps.append((f"net primary production, {producer}", values["npp_dry_weight"], "g DW/m²/yr"))
        steps.append((f"net primary production, {producer}, carbon", producers[0][1], "g C/m²/yr"))
        for name, carbon, _ in producers[1:]:
            steps.append((f"net primary production, {name.replace('_', ' ')}, carbon", carbon, "g C/m²/yr"))
        steps.append(("net primary production, all producers, carbon",
                      sum(c for _, c, _ in producers), "g C/m²/yr"))
    web = 10.0 * sum(c * share for _, c, share in producers)
    levels = values["catch_trophic_level"] - 1.0
    consumers_c = web * values["transfer_efficiency"] ** levels
    fish = consumers_c * values["wet_weight_per_carbon"]
    catch = fish * values["sustainable_catch_share"]
    euros = catch * values["first_sale_price"]
    steps.extend([
        ("entering the food web (not buried)", web, "kg C/ha/yr"),
        (f"consumer production at trophic level {values['catch_trophic_level']:g}", consumers_c, "kg C/ha/yr"),
        ("fish and invertebrates produced", fish, "kg/ha/yr"),
        ("sustainable catch", catch, "kg/ha/yr"),
        ("food value at first-sale prices", euros, "€/ha/yr"),
    ])
    return steps


def gross_value(values: Dict[str, float]) -> float:
    """€/ha/yr of food supported (the chain's last step)."""
    return chain(values)[-1][1]


def central(spec: Dict[str, Any]) -> Dict[str, float]:
    """{parameter: documented value} of a parsed production function
    (additional producers' parameters as "<name>.<parameter>", the depth
    hyperparameters as "depth.<parameter>"; a NPP derived from the depth
    model at its documented hyperparameters)."""
    return {name: _central(p) for name, p in spec["parameters"].items()}


def _with_depth_npp(spec: Dict[str, Any], values: Dict[str, float], which: str = "") -> Dict[str, float]:
    """``values`` with the main producer's NPP derived from the depth model
    at their hyperparameters (at the project depth, else the regional one;
    ``which`` forces one)."""
    depth = spec.get("depth")
    if depth is None:
        return values
    which = which or ("project" if depth["project"] is not None else "regional")
    return dict(values, **{depth["output"]: npp_over(depth, values, which)})


def _ends(spec: Dict[str, Any], favourable: bool) -> Dict[str, float]:
    """Every link at its least (or most) favourable end. The chain rises
    with every link but the catch's trophic level (a transfer efficiency is
    at most 1), and with the production at the reference depth."""
    out = {}
    for name, p in spec["parameters"].items():
        low, high = _support(p)
        rising = name != "catch_trophic_level"
        out[name] = high if favourable == rising else low
    return out


def _shape_grid(spec: Dict[str, Any]) -> List[Tuple[float, float, Optional[float]]]:
    """(decline_rate, depth_limit, the site's depth limit or None) triples
    spanning their ranges (with the ends), the shape of the depth function
    being monotone in neither of the first two. The production at the
    project depth, and so the net value, is monotone in the site's limit
    (Step 8g.7): a site's limit coupled to the regional one follows it
    (comonotone, as the Monte Carlo draws it); another is taken at its two
    ends."""
    from gaia.uncertainty import dist_cdf, dist_quantile

    def axis(p: Dict[str, Any]) -> List[float]:
        low, high = _support(p)
        if low == high:
            return [low]
        return [low + (high - low) * i / (DEPTH_GRID - 1) for i in range(DEPTH_GRID)]

    params = spec["parameters"]
    regional = params[DEPTH_PREFIX + "depth_limit"]
    site = params.get(DEPTH_PREFIX + SITE_LIMIT)
    pairs: List[Tuple[float, Optional[float]]]
    if site is None:
        pairs = [(z, None) for z in axis(regional)]
    elif site.get("coupled") and regional.get("range") and site.get("range"):
        low, high = regional["range"]
        pairs = [(z, dist_quantile(site["distribution"], site["range"][0], site["value"], site["range"][1],
                                   dist_cdf(regional["distribution"], low, regional["value"], high, z),
                                   site.get("truncated_below")))
                 for z in axis(regional)]
    else:
        pairs = [(z, s) for z in axis(regional) for s in sorted(set(_support(site)))]
    return [(k, z, s) for k in axis(params[DEPTH_PREFIX + "decline_rate"]) for z, s in pairs]


def net_range(spec: Dict[str, Any], booked: float = 0.0) -> Tuple[float, float]:
    """(lowest, highest) net value (gross − net_of_scale × ``booked``) over
    the links' ranges (each link at its value without a range): every link
    of the chain at its least or most favourable end at once and, with a
    depth model, the depth function's shape searched over a grid of its
    decline rate and depth limit (``DEPTH_GRID`` points each, with the
    ends). With ``booked`` = 0 it is the gross range."""
    lows, highs = _ends(spec, False), _ends(spec, True)
    depth = spec.get("depth")
    if depth is None:
        return gross_value(lows) - booked, gross_value(highs) - booked
    lowest, highest = math.inf, -math.inf
    for k, z_max, z_site in _shape_grid(spec):
        for values, keep in ((lows, min), (highs, max)):
            v = dict(values, **{DEPTH_PREFIX + "decline_rate": k, DEPTH_PREFIX + "depth_limit": z_max})
            if z_site is not None:
                v[DEPTH_PREFIX + SITE_LIMIT] = z_site
            v = _with_depth_npp(spec, v)
            scale = 1.0
            if depth["project"] is not None and booked:
                scale = npp_over(depth, v, "project") / npp_over(depth, v, "regional")
            net = gross_value(v) - scale * booked
            if keep is min:
                lowest = min(lowest, net)
            else:
                highest = max(highest, net)
    return lowest, highest


def gross_range(spec: Dict[str, Any]) -> Tuple[float, float]:
    """(lowest, highest) gross value over the parameters' ranges (see
    ``net_range``)."""
    return net_range(spec, 0.0)


# ── Parsing ──────────────────────────────────────────────────────────────────


def parse_market_prices(raw: Any, path: str = "$.market_prices") -> Dict[str, Dict[str, Any]]:
    """Validate a case's ``market_prices`` block (Step 8h.4; see the module
    docstring): {name: price}, each a sourced parameter (value > 0, unit,
    label, source, status, optional distribution and range) with an
    optional free-text ``note``. Returns the raw prices (without the note),
    ready to stand in for a chain's price parameter.

    Raises:
        ValueError: Naming the JSON path of the first problem.
    """
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{path}: an object of named market prices, at least one")
    out: Dict[str, Dict[str, Any]] = {}
    for name, price in raw.items():
        ppath = f"{path}.{name}"
        if not _MARKET_PRICE_NAME.match(name):
            raise ValueError(f"{ppath}: a market price's name is lower-case letters, digits and _")
        if not isinstance(price, dict):
            raise ValueError(f"{ppath}: expected an object")
        if not isinstance(price.get("note", ""), str):
            raise ValueError(f"{ppath}.note: a string")
        body = {k: v for k, v in price.items() if k != "note"}
        _parse_parameters({MARKET_PRICE_PARAMETERS[0]: body}, MARKET_PRICE_PARAMETERS[:1], path)
        out[name] = body
    return out


def _is_price_reference(p: Any) -> bool:
    return isinstance(p, dict) and set(p) == {"market_price"}


def parameter_path(spec: Dict[str, Any], name: str, entry_path: str) -> str:
    """The document path of a parsed production function's parameter
    ``name``, the function being at ``entry_path`` (e.g.
    "$.service_ledger[3].production_function"): a market price's is its
    anchor's (Step 8h.4), shared by every chain that references it."""
    path = spec["paths"][name]
    return path if path.startswith("$") else f"{entry_path}.{path}"


def parse_production_function(raw: Any, path: str,
                              market_prices: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Validate a ledger entry's ``production_function`` block (see the
    module docstring); returns it with numbers as floats, the parameters
    flat ({name: parameter}, additional producers' as "<name>.<parameter>",
    the depth hyperparameters as "depth.<parameter>"), each parameter's JSON
    path relative to the block (``paths``; a market price's is its anchor's,
    absolute) and the depth model (``depth``, or None). ``market_prices``:
    the case's anchors (``parse_market_prices``; Step 8h.4), which a price
    parameter references as {"market_price": "<name>"}; when given, a price
    typed into the chain is rejected.

    Raises:
        ValueError: Naming the JSON path of the first problem.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object")
    unknown = set(raw) - {"model", "producer", "parameters", "producers", "depth_production", "comparison"}
    if unknown:
        raise ValueError(f"{path}: unknown key {sorted(unknown)[0]!r}")
    if raw.get("model") != MODEL:
        raise ValueError(f"{path}.model: expected {MODEL!r}, got {raw.get('model')!r}")
    producer = raw.get("producer", _DEFAULT_PRODUCER)
    if not isinstance(producer, str) or not producer:
        raise ValueError(f"{path}.producer: a non-empty string")
    params_raw = raw.get("parameters")
    if not isinstance(params_raw, dict):
        raise ValueError(f"{path}.parameters: expected an object")
    # Step 8h.4: a market price is a case-level anchor, the same for every chain
    anchors: Dict[str, str] = {}
    params_raw = dict(params_raw)
    for name, p in list(params_raw.items()):
        if _is_price_reference(p):
            if name not in MARKET_PRICE_PARAMETERS:
                raise ValueError(f"{path}.parameters.{name}: only a price ({', '.join(MARKET_PRICE_PARAMETERS)}) "
                                 f"references a market price")
            anchor = p["market_price"]
            if not isinstance(anchor, str) or not market_prices or anchor not in market_prices:
                raise ValueError(f"{path}.parameters.{name}: unknown market price {anchor!r} (declare it in "
                                 f"$.market_prices)")
            params_raw[name] = market_prices[anchor]
            anchors[name] = anchor
        elif name in MARKET_PRICE_PARAMETERS and market_prices:
            raise ValueError(
                f"{path}.parameters.{name}: the case declares its market prices ($.market_prices), so the chain "
                f"references one ({{\"market_price\": \"<name>\"}}): one sourced price anchors every chain, "
                f"whatever the depth (Step 8h.4)")
    depth: Optional[Dict[str, Any]] = None
    derived_output = ""
    if "depth_production" in raw:
        depth = _parse_depth(raw["depth_production"], f"{path}.depth_production")
        derived_output = depth["output"]
        if derived_output in params_raw:
            raise ValueError(
                f"{path}.parameters.{derived_output}: derived from depth_production, so not given here"
            )
    given = set(params_raw) | ({derived_output} if derived_output else set())
    main = next((s for s in PRODUCER_PARAMETERS if set(s) | set(CHAIN_PARAMETERS) == given), None)
    if main is None:
        missing = [n for n in PARAMETERS if n not in given]
        extra = [n for n in given if n not in PARAMETERS + PRODUCER_PARAMETERS[1]]
        if extra:
            raise ValueError(f"{path}.parameters: unknown parameter {extra[0]!r}")
        raise ValueError(
            f"{path}.parameters: missing {missing[0]!r} (required: the main producer's "
            + " or ".join(", ".join(s) for s in PRODUCER_PARAMETERS)
            + f", and {', '.join(CHAIN_PARAMETERS)})"
        )
    names = tuple(n for n in main + CHAIN_PARAMETERS if n != derived_output)
    params = _parse_parameters(params_raw, names, f"{path}.parameters")
    paths = {name: f"parameters.{name}" for name in params}
    for name, anchor in anchors.items():
        params[name]["market_price"] = anchor
        paths[name] = f"$.market_prices.{anchor}"
    producers: List[Dict[str, Any]] = []
    producers_raw = raw.get("producers", [])
    if not isinstance(producers_raw, list):
        raise ValueError(f"{path}.producers: expected a list")
    for i, prod in enumerate(producers_raw):
        ppath = f"{path}.producers[{i}]"
        if not isinstance(prod, dict) or set(prod) - {"name", "description", "parameters"}:
            raise ValueError(f"{ppath}: expected an object with name, description and parameters")
        name = prod.get("name")
        if not isinstance(name, str) or not _PRODUCER_NAME.match(name) or name == "depth":
            raise ValueError(f"{ppath}.name: lower-case letters, digits and _ (not 'depth'), got {name!r}")
        if any(p["name"] == name for p in producers):
            raise ValueError(f"{ppath}.name: {name!r} is listed twice")
        if not isinstance(prod.get("description"), str) or not prod["description"]:
            raise ValueError(f"{ppath}.description: required, a non-empty string")
        given_p = prod.get("parameters")
        if not isinstance(given_p, dict):
            raise ValueError(f"{ppath}.parameters: expected an object")
        expected = next((s for s in PRODUCER_PARAMETERS if set(s) == set(given_p)), None)
        if expected is None:
            raise ValueError(
                f"{ppath}.parameters: give " + " or ".join(", ".join(s) for s in PRODUCER_PARAMETERS)
                + f", got {', '.join(sorted(given_p)) or 'none'}"
            )
        parsed = _parse_parameters(given_p, expected, f"{ppath}.parameters")
        for key, p in parsed.items():
            params[f"{name}.{key}"] = p
            paths[f"{name}.{key}"] = f"producers[{i}].parameters.{key}"
        producers.append({"name": name, "description": prod["description"]})
    if depth is not None and derived_output:
        for key, p in depth.pop("parameters").items():
            params[DEPTH_PREFIX + key] = p
            paths[DEPTH_PREFIX + key] = f"depth_production.parameters.{key}"
        site = depth.pop("site")
        if site is not None:
            params[DEPTH_PREFIX + SITE_LIMIT] = site
            paths[DEPTH_PREFIX + SITE_LIMIT] = "depth_production.project_depth.depth_limit"
        values = {k: _central(p) for k, p in params.items()}
        which = "project" if depth["project"] is not None else "regional"
        npp = npp_over(depth, values, which)
        params[derived_output] = {
            "value": npp,
            "unit": params[DEPTH_PREFIX + "npp_at_reference_depth"]["unit"],
            "label": f"net primary production of the {producer} at {depth_label(depth)}, "
                     f"from its depth function",
            "source": f"derived: depth_production ({DEPTH_MODEL}) averaged over {depth_label(depth)}; "
                      f"its hyperparameters: {params[DEPTH_PREFIX + 'npp_at_reference_depth']['source']}",
            "status": "derived",
            "distribution": "fixed",
            "distribution_basis": "derived in every draw from the depth function's sampled hyperparameters",
        }
        # keep the chain's order: the derived NPP first
        params = dict([(derived_output, params.pop(derived_output))] + list(params.items()))
    spec: Dict[str, Any] = {"model": MODEL, "producer": producer, "parameters": params,
                            "producers": producers, "paths": paths, "comparison": None,
                            "depth": depth}
    if "comparison" in raw:
        spec["comparison"] = _parse_comparison(raw["comparison"], f"{path}.comparison")
    return spec


def depth_label(depth: Dict[str, Any]) -> str:
    """Words for the depth the NPP is taken at: "12 m (project)",
    "10–20 m (project)" or the regional basis."""
    if depth["project"] is not None:
        a, b, _ = depth["project"]["bands"][0]
        return (f"{a:g} m" if a == b else f"{a:g}–{b:g} m") + " (the project's depth)"
    regional = depth["regional"]
    if regional["kind"] == "mean":
        return f"{regional['bands'][0][0]:g} m (the regional mean depth)"
    a = min(b[0] for b in regional["bands"])
    b = max(b[1] for b in regional["bands"])
    return f"the regional depth distribution ({a:g}–{b:g} m, area-weighted)"


def _parse_depth(raw: Any, path: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object")
    allowed = {"model", "output", "reference_depth_m", "parameters", "depth_limit_margin", "regional_depth",
               "project_depth", "data", "fit", "description"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{path}: unknown key {sorted(unknown)[0]!r}")
    if raw.get("model") != DEPTH_MODEL:
        raise ValueError(f"{path}.model: expected {DEPTH_MODEL!r}, got {raw.get('model')!r}")
    output = raw.get("output")
    if output not in ("npp_dry_weight", "npp_carbon"):
        raise ValueError(f"{path}.output: 'npp_dry_weight' or 'npp_carbon', got {output!r}")
    z_ref = raw.get("reference_depth_m")
    if isinstance(z_ref, bool) or not isinstance(z_ref, (int, float)) or not (math.isfinite(z_ref) and z_ref >= 0):
        raise ValueError(f"{path}.reference_depth_m: a depth >= 0 in m, got {z_ref!r}")
    params_raw = raw.get("parameters")
    if not isinstance(params_raw, dict):
        raise ValueError(f"{path}.parameters: expected an object")
    params = _parse_parameters(params_raw, DEPTH_PARAMETERS, f"{path}.parameters")
    z_ref = float(z_ref)
    shallowest_limit = params["depth_limit"]["range"][0] if params["depth_limit"].get("range") \
        else params["depth_limit"]["value"]
    if not z_ref < shallowest_limit:
        raise ValueError(
            f"{path}.reference_depth_m: must be shallower than the depth limit's low end, "
            f"{shallowest_limit:g} m, got {z_ref:g}"
        )
    margin = _parse_parameters({"depth_limit_margin": raw.get("depth_limit_margin")}, ("depth_limit_margin",),
                               path)["depth_limit_margin"]
    if margin["distribution"] != "fixed":
        raise ValueError(f"{path}.depth_limit_margin: a fixed number of metres, not sampled")
    regional = _parse_depth_spec(raw.get("regional_depth"), f"{path}.regional_depth", shallowest_limit,
                                 regional=True)
    project = None
    site = None
    if raw.get("project_depth") is not None:
        project = _parse_depth_spec(raw["project_depth"], f"{path}.project_depth", math.inf, regional=False)
        deepest = max(b for _, b, _ in project["bands"])
        site_raw = raw["project_depth"].get("depth_limit")
        if site_raw is None:
            site_raw = site_depth_limit(params["depth_limit"], margin["value"], deepest)
        site = _parse_site_limit(site_raw, f"{path}.project_depth", deepest)
    data = []
    for i, row in enumerate(_list_of(raw.get("data", []), f"{path}.data")):
        rpath = f"{path}.data[{i}]"
        if not isinstance(row, dict) or set(row) - {"site", "depth_m", "value", "source", "status", "note"}:
            raise ValueError(f"{rpath}: expected site, depth_m, value, source, status, note")
        for key in ("site", "source", "status"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"{rpath}.{key}: required, a non-empty string")
        if row["status"] not in STATUSES:
            raise ValueError(f"{rpath}.status: expected one of {list(STATUSES)}, got {row['status']!r}")
        data.append({"site": row["site"], "depth_m": _positive(row.get("depth_m"), f"{rpath}.depth_m"),
                     "value": _positive(row.get("value"), f"{rpath}.value"), "source": row["source"],
                     "status": row["status"], "note": row.get("note", "")})
    for key in ("fit", "description"):
        if not isinstance(raw.get(key, ""), str):
            raise ValueError(f"{path}.{key}: a string")
    return {"model": DEPTH_MODEL, "output": output, "reference_depth_m": z_ref, "parameters": params,
            "margin": margin, "regional": regional, "project": project, "site": site, "data": data,
            "fit": raw.get("fit", ""), "description": raw.get("description", "")}


def _parse_site_limit(raw: Any, path: str, deepest: float) -> Dict[str, Any]:
    """The site's depth limit at a project depth (``project_depth.depth_limit``,
    a parameter with an optional ``truncated_below`` and ``coupled``; Step
    8g.7): it must lie below the project's deepest depth in every draw."""
    if not isinstance(raw, dict):
        raise ValueError(f"{path}.depth_limit: expected an object")
    rest = {k: v for k, v in raw.items() if k not in ("truncated_below", "coupled")}
    site = _parse_parameters({"depth_limit": rest}, ("depth_limit",), path,
                             STATUSES + (USER_STATUS,))["depth_limit"]
    if "truncated_below" in raw:
        floor = _positive(raw["truncated_below"], f"{path}.depth_limit.truncated_below")
        if not (site.get("range") and site["range"][0] < floor < site["range"][1]):
            raise ValueError(f"{path}.depth_limit.truncated_below: must lie inside the range")
        site["truncated_below"] = floor
    coupled = raw.get("coupled", False)
    if not isinstance(coupled, bool):
        raise ValueError(f"{path}.depth_limit.coupled: true or false")
    site["coupled"] = coupled
    if not _support(site)[0] > deepest:
        raise ValueError(
            f"{path}.depth_limit: the site's depth limit ({_support(site)[0]:g} m at its shallowest) must lie "
            f"below the project's deepest depth, {deepest:g} m (production reaches zero at the depth limit; "
            f"a resource there is not valued, never at €0)"
        )
    return site


def site_depth_limit(documented: Dict[str, Any], margin: float, deepest: float) -> Dict[str, Any]:
    """The site's depth limit at a project whose deepest depth is ``deepest``
    (Step 8g.7), as a raw parameter (``project_depth.depth_limit``): the
    documented (regional) depth limit conditioned on the evidence that the
    meadow lives at that depth, so its limit lies deeper by at least the
    ``margin`` (``depth_limit_margin``): z_site > deepest + margin.

    - floor = deepest + margin at or above the range's low end: unchanged;
    - inside the range, up to its high end less the margin: the documented
      distribution truncated below the floor (``truncated_below``; its
      central value the conditional mode, max(value, floor));
    - deeper (the project lies within two margins of the deepest limit
      documented, or below it): the distribution would be narrower than the
      margin or empty, so it is extended: triangular from the floor (its
      mode) to the floor + the margin, continuing the truncated triangle's
      shape (inferred: beyond the deepest meadows documented).

    When the documented limit is sampled, the site's limit takes the same
    draw through its own distribution (``coupled``: comonotone)."""
    low, high = documented["range"] if documented.get("range") else (documented["value"], documented["value"])
    floor = deepest + margin
    sampled = documented["distribution"] != "fixed" and low < high
    out: Dict[str, Any] = {k: documented[k] for k in ("value", "unit", "label", "source", "status",
                                                       "distribution", "distribution_basis")}
    if documented.get("range"):
        out["range"] = [low, high]
    out["label"] = "depth limit of the site (where the plant's net production reaches zero), at the project's depth"
    where = f"a meadow at {deepest:g} m proves its site's depth limit lies deeper; with the margin, below {floor:g} m"
    if floor <= low:
        out["source"] = f"The regional depth limit ({where}, which every value of the range already does). " \
                        + documented["source"]
    elif floor <= high - margin:
        out["truncated_below"] = floor
        out["source"] = f"The regional depth limit conditioned on the project's depth ({where}): its distribution " \
                        f"truncated below {floor:g} m. " + documented["source"]
        out["distribution_basis"] = f"The regional distribution truncated below {floor:g} m (conditioned on the " \
                                    f"meadow at {deepest:g} m). " + documented["distribution_basis"]
    else:
        out.update(value=floor, range=[floor, floor + margin], distribution="triangular", status="inferred")
        out["source"] = (
            f"The regional depth limit ({documented['value']:g} m, {low:g}-{high:g} m) extended ({where}): within "
            f"two margins of its deepest value or below it, the truncated distribution would be narrower than "
            f"the margin, so the site's limit is taken between {floor:g} and {floor + margin:g} m (inferred, beyond "
            f"the deepest limits documented). " + documented["source"]
        )
        out["distribution_basis"] = (
            f"Triangular, mode at {floor:g} m (the floor), {margin:g} m wide: the shape of the regional triangle "
            f"truncated near its deepest value, continued below it"
        )
    out["coupled"] = sampled
    return out


def given_site_depth_limit(low: float, high: float, margin: float, deepest: float,
                           source: str = "user-supplied (--depth-limit-m)") -> Dict[str, Any]:
    """The site's depth limit given by the project (Step 8g.10, e.g.
    ``--depth-limit-m``: water clarity varies, from about 15 m at the Medes
    Islands to 44 m in the clearest waters), one depth (low = high: fixed)
    or a range (uniform), as a raw parameter (``project_depth.depth_limit``).
    It replaces the regional depth limit at the project's site, conditioned
    like it (Step 8g.7) on lying below the meadow: a range is truncated
    below the deepest depth + the margin, or + half the distance to its
    deepest end when that is closer (it is the user's statement: never
    extended beyond it).

    Raises:
        ValueError: For a limit <= 0 or a reversed range, or a project depth
            at or below the deepest limit given (a meadow cannot live where
            its production is zero).
    """
    if not (math.isfinite(low) and math.isfinite(high) and 0.0 < low <= high):
        raise ValueError(f"the site's depth limit must be > 0 m (one depth or a range low-high), "
                         f"got {low:g}-{high:g}")
    given = f"{low:g} m" if low == high else f"{low:g}-{high:g} m"
    if not deepest < high:
        raise ValueError(
            f"a depth of {deepest:g} m is at or below the site's depth limit given ({given}, "
            f"--depth-limit-m), where the meadow's production reaches zero: a meadow cannot live there. "
            f"Give a depth shallower than {high:g} m, or the site's own deeper limit"
        )
    out: Dict[str, Any] = {
        "unit": "m",
        "label": "depth limit of the site (where the plant's net production reaches zero), given by the project",
        "source": f"{source}: {given}, the site's own lower limit (it replaces the regional 30-44 m)",
        "status": USER_STATUS,
    }
    if low == high:
        out.update(value=high, distribution="fixed",
                   distribution_basis="One depth given: not sampled")
        return out
    floor = max(low, deepest + min(margin, (high - deepest) / 2.0))
    out.update(value=(floor + high) / 2.0, range=[floor, high], distribution="uniform",
               distribution_basis=(
                   "Uniform over the range given" + (
                       f", truncated below {floor:g} m (a meadow at {deepest:g} m proves the limit lies deeper)"
                       if floor > low else "")))
    return out


def _parse_depth_spec(raw: Any, path: str, shallowest_limit: float, regional: bool) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object")
    bands: List[Tuple[float, float, float]] = []
    if regional:
        allowed = {"distribution", "mean_m", "source", "status", "note"}
        if set(raw) - allowed:
            raise ValueError(f"{path}: unknown key {sorted(set(raw) - allowed)[0]!r}")
        for key in ("source", "status"):
            if not isinstance(raw.get(key), str) or not raw[key]:
                raise ValueError(f"{path}.{key}: required, a non-empty string")
        if raw["status"] not in STATUSES:
            raise ValueError(f"{path}.status: expected one of {list(STATUSES)}, got {raw['status']!r}")
        if ("distribution" in raw) == ("mean_m" in raw):
            raise ValueError(f"{path}: give distribution (depth bands) or mean_m, not both")
        if "mean_m" in raw:
            z = _positive(raw["mean_m"], f"{path}.mean_m")
            bands = [(z, z, 1.0)]
            kind = "mean"
        else:
            rows = _list_of(raw["distribution"], f"{path}.distribution")
            if not rows:
                raise ValueError(f"{path}.distribution: at least one band")
            for i, row in enumerate(rows):
                bpath = f"{path}.distribution[{i}]"
                if not isinstance(row, dict) or set(row) != {"from_m", "to_m", "share"}:
                    raise ValueError(f"{bpath}: expected from_m, to_m and share")
                a = _non_negative(row["from_m"], f"{bpath}.from_m")
                b = _positive(row["to_m"], f"{bpath}.to_m")
                share = _positive(row["share"], f"{bpath}.share")
                if not a < b:
                    raise ValueError(f"{bpath}: from_m must be < to_m")
                bands.append((a, b, share))
            total = sum(s for _, _, s in bands)
            if not math.isclose(total, 1.0, rel_tol=1e-9):
                raise ValueError(f"{path}.distribution: the shares must sum to 1, got {total:.6g}")
            kind = "distribution"
    else:
        if set(raw) - {"from_m", "to_m", "source", "depth_limit"}:
            raise ValueError(f"{path}: expected from_m, to_m, source and depth_limit")
        a = _non_negative(raw.get("from_m"), f"{path}.from_m")
        b = _non_negative(raw.get("to_m"), f"{path}.to_m")
        if not a <= b:
            raise ValueError(f"{path}: from_m must be <= to_m")
        bands = [(a, b, 1.0)]
        kind = "project"
    deepest = max(b for _, b, _ in bands)
    if not deepest < shallowest_limit:
        raise ValueError(
            f"{path}: {deepest:g} m is not shallower than the depth limit's low end, {shallowest_limit:g} m "
            f"(production reaches zero at the depth limit; a resource there is not valued, never at €0)"
        )
    out = {"kind": kind, "bands": bands, "source": raw.get("source", ""),
           "status": raw.get("status", ""), "note": raw.get("note", "")}
    return out


def _list_of(raw: Any, path: str) -> list:
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a list")
    return raw


def _parse_parameters(raw: Dict[str, Any], names: Tuple[str, ...], path: str,
                      statuses: Tuple[str, ...] = STATUSES) -> Dict[str, Dict[str, Any]]:
    missing = [n for n in names if n not in raw]
    if missing:
        raise ValueError(f"{path}: missing {missing[0]!r} (required: {', '.join(names)})")
    extra = [n for n in raw if n not in names]
    if extra:
        raise ValueError(f"{path}: unknown parameter {extra[0]!r}")
    params: Dict[str, Dict[str, Any]] = {}
    for name in names:
        ppath = f"{path}.{name}"
        p = raw[name]
        if not isinstance(p, dict):
            raise ValueError(f"{ppath}: expected an object")
        bad = set(p) - {"value", "unit", "label", "source", "status", "range", "distribution",
                        "distribution_basis"}
        if bad:
            raise ValueError(f"{ppath}: unknown key {sorted(bad)[0]!r}")
        for key in ("unit", "label", "source", "status"):
            if not isinstance(p.get(key), str) or not p[key]:
                raise ValueError(f"{ppath}.{key}: required, a non-empty string")
        if p["status"] not in statuses:
            raise ValueError(f"{ppath}.status: expected one of {list(statuses)}, got {p['status']!r}")
        value = _positive(p.get("value"), f"{ppath}.value")
        out: Dict[str, Any] = {k: p[k] for k in ("unit", "label", "source", "status")}
        out["value"] = value
        if name in _FRACTIONS and value > 1.0:
            raise ValueError(f"{ppath}.value: a share, must be in (0, 1], got {value}")
        if name == "catch_trophic_level" and value < 1.0:
            raise ValueError(f"{ppath}.value: a trophic level is >= 1, got {value}")
        if "range" in p:
            r = p["range"]
            if not (isinstance(r, list) and len(r) == 2):
                raise ValueError(f"{ppath}.range: expected [low, high]")
            low, high = (_positive(x, f"{ppath}.range") for x in r)
            if not low <= value <= high:
                raise ValueError(f"{ppath}.range: must contain the value {value}, got [{low}, {high}]")
            if name in _FRACTIONS and high > 1.0:
                raise ValueError(f"{ppath}.range: a share, must be in (0, 1]")
            if name == "catch_trophic_level" and low < 1.0:
                raise ValueError(f"{ppath}.range: a trophic level is >= 1")
            out["range"] = (low, high)
        distribution = p.get("distribution", "triangular" if "range" in out else "fixed")
        if distribution not in DISTRIBUTIONS:
            raise ValueError(f"{ppath}.distribution: expected one of {list(DISTRIBUTIONS)}, got {distribution!r}")
        if distribution != "fixed" and ("range" not in out or out["range"][0] == out["range"][1]):
            raise ValueError(f"{ppath}.distribution: {distribution!r} needs a range [low, high] with low < high")
        out["distribution"] = distribution
        basis = p.get("distribution_basis", "")
        if not isinstance(basis, str):
            raise ValueError(f"{ppath}.distribution_basis: a string")
        out["distribution_basis"] = basis
        params[name] = out
    return params


def _parse_comparison(raw: Any, path: str) -> Dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - {"metric", "unit", "rows", "note"}:
        raise ValueError(f"{path}: expected an object with metric, unit, rows and an optional note")
    for key in ("metric", "unit"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise ValueError(f"{path}.{key}: required, a non-empty string")
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise ValueError(f"{path}.rows: a non-empty list")
    rows = []
    for i, row in enumerate(rows_raw):
        rpath = f"{path}.rows[{i}]"
        if not isinstance(row, dict) or set(row) - {"ecosystem", "value", "low", "high", "source", "note"}:
            raise ValueError(f"{rpath}: expected ecosystem, value or low and high, source, note")
        for key in ("ecosystem", "source"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"{rpath}.{key}: required, a non-empty string")
        out: Dict[str, Any] = {"ecosystem": row["ecosystem"], "source": row["source"], "note": row.get("note", "")}
        if "value" in row:
            out["low"] = out["high"] = _positive(row["value"], f"{rpath}.value")
        elif "low" in row and "high" in row:
            out["low"] = _positive(row["low"], f"{rpath}.low")
            out["high"] = _positive(row["high"], f"{rpath}.high")
            if out["low"] > out["high"]:
                raise ValueError(f"{rpath}: low is above high")
        else:
            raise ValueError(f"{rpath}: give value, or low and high")
        rows.append(out)
    return {"metric": raw["metric"], "unit": raw["unit"], "rows": rows, "note": raw.get("note", "")}


def _positive(raw: Any, path: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw <= 0:
        raise ValueError(f"{path}: expected a finite number > 0, got {raw!r}")
    return float(raw)


def _non_negative(raw: Any, path: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0:
        raise ValueError(f"{path}: expected a finite number >= 0, got {raw!r}")
    return float(raw)


# ── A project depth (Step 8g.1) ──────────────────────────────────────────────


def with_project_depth(document: Dict[str, Any], from_m: float, to_m: float,
                       source: str = "user-supplied (--depth-m)",
                       depth_limit: Optional[Tuple[float, float]] = None,
                       limit_source: str = "user-supplied (--depth-limit-m)") -> Dict[str, Any]:
    """A copy of a case document whose depth-dependent production functions
    are taken at the project depth [from_m, to_m] (a single depth when
    from_m = to_m): each such ledger entry's gross and net value (net of
    ``net_of_scale`` × the services it is net of), and its owner's
    annual_value_per_ha and range, are recomputed. Any depth >= 0 is valued:
    a meadow that lives there proves its site's depth limit lies deeper, so
    the site's depth limit is the regional one conditioned on it
    (``site_depth_limit``, Step 8g.7), or the site's own limit when the
    project gives it (``depth_limit``, one depth (low, low) or a range (low,
    high); ``given_site_depth_limit``, Step 8g.10).

    Raises:
        ValueError: Without a depth-dependent production function, for a
            negative depth, or for a depth at or below the site's depth limit
            given.
    """
    if not (math.isfinite(from_m) and math.isfinite(to_m) and 0.0 <= from_m <= to_m):
        raise ValueError(f"the project depth must be >= 0 m (a single depth or a range low-high), "
                         f"got {from_m:g}-{to_m:g}")
    doc = copy.deepcopy(document)
    ledger = doc.get("service_ledger", [])
    booked = {e["service"]: e["value"] for e in ledger}
    prices = parse_market_prices(doc["market_prices"]) if doc.get("market_prices") is not None else None
    found = False
    for i, entry in enumerate(ledger):
        raw = entry.get("production_function")
        if not isinstance(raw, dict) or "depth_production" not in raw:
            continue
        found = True
        path = f"$.service_ledger[{i}].production_function"
        old = parse_production_function(raw, path, prices)
        depth = old["depth"]
        if depth_limit is None:
            site = site_depth_limit(old["parameters"][DEPTH_PREFIX + "depth_limit"], depth["margin"]["value"],
                                    float(to_m))
        else:
            site = given_site_depth_limit(float(depth_limit[0]), float(depth_limit[1]), depth["margin"]["value"],
                                          float(to_m), limit_source)
        raw["depth_production"]["project_depth"] = {"from_m": float(from_m), "to_m": float(to_m), "source": source,
                                                    "depth_limit": site}
        new = parse_production_function(raw, path, prices)
        counted = sum(booked[s] for s in entry.get("net_of", []))
        gross = gross_value(central(new))
        net = gross - net_of_scale(new) * counted
        lo_old, hi_old = net_range(old, counted)
        lo_new, hi_new = net_range(new, counted)
        old_net = entry["value"]
        if "gross" in entry:
            entry["gross"] = gross
        entry["value"] = net
        _shift_agent(doc, entry["agent"], net - old_net, lo_new - lo_old, hi_new - hi_old,
                     f"At the project's depth ({depth_label(new['depth'])}): {entry['service'].split(':')[0]} "
                     f"€{net:,.2f}/ha/yr net (gross €{gross:,.2f}).")
    if not found:
        raise ValueError("the case has no depth-dependent production function, so a depth cannot be set")
    return doc


def _shift_agent(doc: Dict[str, Any], agent: str, delta: float, d_low: float, d_high: float, note: str) -> None:
    a = next(x for x in doc["agents"] if x["name"] == agent)
    weight = a["dependency_weight"]
    w = float(weight["value"] if isinstance(weight, dict) else weight)
    value = a["annual_value_per_ha"]
    if isinstance(value, dict):
        value["value"] = value["value"] + delta / w
        if value.get("range"):
            value["range"] = [value["range"][0] + d_low / w, value["range"][1] + d_high / w]
        value["note"] = (value.get("note", "") + " " + note).strip()
    else:
        a["annual_value_per_ha"] = value + delta / w
    # an EXPERIMENTAL pricing anchor is the agent's value over the reference area
    pricing = doc.get("pricing") or {}
    area = pricing.get("reference_area_ha")
    for anchor in pricing.get("anchors", []):
        if anchor.get("agent_name") == agent and area:
            anchor["anchor_value"] = anchor["anchor_value"] + delta / w * area


# ── Output ───────────────────────────────────────────────────────────────────


def _num(value: float) -> str:
    """A compact number for the report: 3 significant figures, thousands
    separators."""
    if value >= 100:
        return f"{value:,.0f}"
    if value >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def chain_text(spec: Dict[str, Any], gross: float, counted: float, net: float, counted_in: str) -> str:
    """The NPP → € chain in one line of words (for the report's agent line)."""
    values = central(spec)
    producers = producer_carbon(values)
    steps = chain(values)
    web, _, fish, catch, _ = (v for _, v, _ in steps[-5:])
    p = spec["parameters"]
    if "npp_dry_weight" in values:
        npp = f"NPP {_num(producers[0][1])} g C/m²/yr ({_num(values['npp_dry_weight'])} g dry weight)"
    else:
        npp = f"NPP {_num(producers[0][1])} g C/m²/yr"
    if spec.get("depth") is not None:
        npp += f" at {depth_label(spec['depth'])}"
    if len(producers) > 1:
        others = " + ".join(f"{name.replace('_', ' ')} {_num(c)}" for name, c, _ in producers[1:])
        npp += f" + {others} = {_num(sum(c for _, c, _ in producers))} g C/m²/yr"
    tail = (f"; minus €{_num(counted)} already counted ({counted_in}) = €{_num(net)}/ha/yr"
            if counted else "")
    return (
        f"Primary production → food: {npp} "
        f"→ {_num(web)} kg C/ha/yr into the food web (not buried) → {_num(fish)} kg fish and "
        f"invertebrates/ha/yr (trophic level {p['catch_trophic_level']['value']:g}) → {_num(catch)} kg/ha/yr "
        f"sustainable catch × €{p['first_sale_price']['value']:.2f}/kg = €{_num(gross)}/ha/yr{tail}"
    )


DEPTH_TABLE_M: Tuple[float, ...] = (5.0, 10.0, 15.0, 20.0, 25.0, 30.0)
"""Depths at which the report and the JSON show the depth function."""


def depth_block(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The JSON form of a production function's depth model (None without
    one): the formula, the hyperparameters, the depth used and the NPP it
    gives, and the function at ``DEPTH_TABLE_M`` (central hyperparameters;
    depths at or below the depth limit omitted)."""
    depth = spec.get("depth")
    if depth is None:
        return None
    values = central(spec)
    p_ref, k, z_max = _depth_values(values)
    z_ref = depth["reference_depth_m"]
    which = "project" if depth["project"] is not None else "regional"
    site = spec["parameters"].get(DEPTH_PREFIX + SITE_LIMIT)
    site_block = None
    if site is not None:
        site_block = {key: (list(v) if key == "range" and v else v) for key, v in site.items()}
        site_block.update(value=_central(site), support=list(_support(site)))
    return {
        "model": DEPTH_MODEL,
        "formula": "NPP(z) = P_ref · (e^(−k·z) − e^(−k·z_max)) / (e^(−k·z_ref) − e^(−k·z_max))",
        "output": depth["output"],
        "unit": spec["parameters"][DEPTH_PREFIX + "npp_at_reference_depth"]["unit"],
        "reference_depth_m": z_ref,
        "hyperparameters": {
            name: {k_: (list(v) if k_ == "range" and v else v) for k_, v in spec["parameters"][DEPTH_PREFIX + name].items()}
            for name in DEPTH_PARAMETERS
        },
        "depth_used": which,
        "depth_label": depth_label(depth),
        "depth_bands": [{"from_m": a, "to_m": b, "share": s} for a, b, s in depth[which]["bands"]],
        "regional_depth": {"bands": [{"from_m": a, "to_m": b, "share": s} for a, b, s in depth["regional"]["bands"]],
                           "source": depth["regional"]["source"], "status": depth["regional"]["status"]},
        "npp": values[depth["output"]],
        "npp_regional": npp_over(depth, values, "regional"),
        "net_of_scale": net_of_scale(spec),
        "deepest_allowed_m": deepest_allowed(spec),
        "depth_limit_margin": dict(depth["margin"]),
        "site_depth_limit": site_block,
        "npp_at_depth": {f"{z:g}": depth_npp(z, p_ref, k, z_max, z_ref) for z in DEPTH_TABLE_M if z < z_max},
        "data": [dict(row) for row in depth["data"]],
        "fit": depth["fit"],
    }


def production_block(spec: Dict[str, Any], gross: float, counted: float, net: float,
                     net_of: List[str]) -> Dict[str, Any]:
    """The JSON form of a production function: its parameters, its chain,
    the gross value, what was subtracted, the net value, the depth model,
    the comparison."""
    low, high = gross_range(spec)
    return {
        "model": spec["model"],
        "producer": spec["producer"],
        "parameters": {
            name: dict(p, range=list(p["range"]) if p.get("range") else None)
            for name, p in spec["parameters"].items()
        },
        "producers": [dict(p) for p in spec["producers"]],
        "depth_production": depth_block(spec),
        "chain": [{"step": what, "value": value, "unit": unit}
                  for what, value, unit in chain(central(spec), spec["producer"])],
        "gross_eur_per_ha_yr": gross,
        "gross_range_eur_per_ha_yr": [low, high],
        "net_of": list(net_of),
        "already_counted_eur_per_ha_yr": counted,
        "net_eur_per_ha_yr": net,
        "comparison": spec["comparison"],
    }


def format_depth(block: Dict[str, Any]) -> List[str]:
    """Report lines of a production function's depth model."""
    h = block["hyperparameters"]
    unit = block["unit"]
    site = block.get("site_depth_limit")
    site_text = ""
    if site is not None:
        low, high = site["support"]
        span = f", {low:g}–{high:g} m in the uncertainty analysis" if low < high else ""
        given = ", given" if site["status"] == USER_STATUS else ""
        site_text = f"; the site's depth limit {site['value']:g} m{given}{span}"
    lines = [
        f"    Depth → production ({block['model']}): {block['formula']}",
        f"      P_ref = {_num(h['npp_at_reference_depth']['value'])} {unit} at z_ref = "
        f"{block['reference_depth_m']:g} m; k = {h['decline_rate']['value']:.4f}/m; z_max = "
        f"{h['depth_limit']['value']:g} m",
        "      " + "   ".join(f"{z} m: {_num(v)}" for z, v in block["npp_at_depth"].items()) + f" {unit}",
        f"      Taken at {block['depth_label']}: {_num(block['npp'])} {unit}"
        + (f" (regional {_num(block['npp_regional'])}; what it is net of × {block['net_of_scale']:.3f}{site_text})"
           if block["depth_used"] == "project" else ""),
    ]
    return lines


def format_comparison(comparison: Dict[str, Any]) -> List[str]:
    """Report lines of the productivity comparison table."""
    lines = [f"  {comparison['metric'].capitalize()}, {comparison['unit']}:"]
    for row in comparison["rows"]:
        value = _num(row["low"]) if row["low"] == row["high"] else f"{_num(row['low'])}–{_num(row['high'])}"
        lines.append(f"    {row['ecosystem'] + ':':<58} {value:>11}")
    return lines
