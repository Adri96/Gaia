"""
Gaia — parameter uncertainty: Monte Carlo and a sensitivity ranking (Step 8.4).

Replaces the heuristic band ``cost × (1 ± (1 − confidence))`` (finding S7)
with a propagation of each parameter's own uncertainty, for any case
document (gaia.ecosystem_io). Only extraction runs are analysed.

Which parameters are sampled. Every parameter the document records with
provenance, except:
    - user-supplied values, and the inputs of the question asked:
      ``resource.total_units``, ``resource.area_ha`` and
      ``resource.unit_value`` (the project's own figures);
    - normative choices, ``discount.*`` and the carbon price: they are
      value judgements, not unknowns with a distribution. They are reported
      as sensitivities instead (``NORMATIVE_SCENARIOS``);
    - parameters that cannot change an extraction result: ``restoration.*``,
      ``recovery.*``, ``succession.*``, ``substrate.*``;
    - parameters marked ``"distribution": "fixed"``, and zeros without an
      explicit range;
    - model-wide constants (gaia.constants): they are not in the document.
      This is a limitation, stated in every output.

The distribution of a parameter:
    - its documented range (``"range": [low, high]`` or
      ``"relative_range": [f_low, f_high]``, factors of the value), else a
      range set by its confidence (``DEFAULT_RELATIVE_SPREAD``: high ±10%,
      medium ±25%, low ×/÷2, placeholder ×/÷3);
    - triangular with the documented value as its mode (the default), or
      uniform (``"distribution": "uniform"``);
    - clipped to [0, 1] for ratios, fractions, shares and health
      thresholds (and kept inside (0, 1) where 0 or 1 is invalid).

Production functions (Step 8f.3). An agent whose value is derived from a
production function (gaia.production; a service-ledger entry with a
``production_function``) is not sampled as one aggregate between the ends
of its range: every link of the chain is sampled on its own, from its own
range and distribution (triangular, uniform, or lognormal truncated to the
range; "fixed" links are not sampled), and each draw recomputes the chain,
the gross value, the net value (gross − the services it is net of, at
their booked values) and the agent's value (its documented value + the
change of the net value / its documented weight). Parsing guarantees that
the chain's lowest value exceeds what it is net of, so no draw can bring
the agent to €0; a draw that did would stop the run (``InvariantError``),
never be clipped or redrawn. A link from the food web to the catch that two
production functions of the case document identically (Posidonia: the
meadow's and the epiphytes', Step 8g.2) is one quantity of one food web: it
is drawn once and both chains take that draw (``Sampled.same_as``). The draws of each production function are
summarised (P5 / P50 / P95 of the gross and net €/ha/yr).

Each draw sets every sampled parameter at its JSON path in a copy of the
document, re-parses it (gaia.ecosystem_io.case_from_dict, with the same
validation as any case file) and runs the extraction. Dependency weights
that were sampled are renormalised to sum to 1. A draw that fails
validation (e.g. edges above the in-degree cap) is redrawn, and the number
of redraws is reported. The random generator is seeded, so results are
reproducible.

Outputs: P5 / P50 / P95 (and mean) of the annual externality, its present
value, the carbon and service parts, and the net social cost; a tornado
ranking (each sampled parameter at its own P5 and P95, the others at their
documented values; ranked by the swing of the net social cost); and the
normative sensitivities.

No third-party dependencies (random, statistics from the standard library).
"""

import copy
import dataclasses
import math
import random
import re
import statistics
import textwrap
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from gaia.provenance import Confidence, Param

DEFAULT_DRAWS: int = 1000
DEFAULT_SEED: int = 20261012

DEFAULT_RELATIVE_SPREAD: Dict[Confidence, Tuple[float, float]] = {
    Confidence.HIGH: (0.9, 1.1),
    Confidence.MEDIUM: (0.75, 1.25),
    Confidence.LOW: (0.5, 2.0),
    Confidence.PLACEHOLDER: (1.0 / 3.0, 3.0),
}
"""Relative range (factors of the value) of a parameter without a
documented range, by confidence. A judgement, stated in every output."""

EXCLUDED_PREFIXES: Tuple[str, ...] = (
    "discount.", "restoration.", "recovery.", "succession.", "substrate.",
    "carbon_price.", "model.",
)
PROJECT_INPUTS: Tuple[str, ...] = (
    "resource.total_units", "resource.area_ha", "resource.unit_value",
)
_UNIT_INTERVAL_UNITS = ("ratio", "fraction", "share", "health", "0-1 scale",
                        "fraction of source damage")
_OPEN_INTERVAL_NAMES = re.compile(r"(safe_threshold_ratio|keystone_threshold)$")
_EPS = 1e-6

HEADLINES: Tuple[Tuple[str, str], ...] = (
    ("annual_externality", "€/yr"),
    ("pv_services", "€ PV"),
    ("pv_carbon_release", "€ PV"),
    ("pv_carbon_foregone", "€ PV"),
    ("pv_externality", "€ PV"),
    ("net_social_cost", "€ PV"),
)
"""Result quantities summarised (name, unit)."""

PERCENTILES: Tuple[int, ...] = (5, 50, 95)


# ── Sampled parameters ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Sampled:
    """A parameter the Monte Carlo varies.

    Attributes:
        name: Parameter name (gaia.provenance naming).
        path: JSON path of its number in the case document.
        value: The documented value (the mode).
        low, high: The range sampled.
        kind: "triangular", "uniform" or "lognormal" (median at the value,
            the range read as its central 95%, truncated at the range
            ends; Step 8f.3, production-function links).
        documented: True when the range comes from the document, False
            when it was set by the confidence (DEFAULT_RELATIVE_SPREAD).
        confidence: The parameter's confidence.
        same_as: The name of another sampled parameter whose draw this one
            takes (Step 8g.2: a link from the food web to the catch that
            two production functions document identically is one
            quantity, drawn once); "" when drawn on its own.
    """

    name: str
    path: str
    value: float
    low: float
    high: float
    kind: str
    documented: bool
    confidence: str
    same_as: str = ""

    def quantile(self, q: float) -> float:
        """The q-quantile (0..1) of this parameter's distribution."""
        a, b, c = self.low, self.high, self.value
        if b <= a:
            return a
        if self.kind == "uniform":
            return a + q * (b - a)
        if self.kind == "lognormal":
            mu = math.log(c)
            sigma = max(math.log(b / c), math.log(c / a)) / _Z95
            normal = statistics.NormalDist()
            fa = normal.cdf((math.log(a) - mu) / sigma)
            fb = normal.cdf((math.log(b) - mu) / sigma)
            p = min(max(fa + q * (fb - fa), 1e-15), 1.0 - 1e-15)
            return min(max(math.exp(mu + sigma * normal.inv_cdf(p)), a), b)
        f = (c - a) / (b - a)
        if q < f:
            return a + math.sqrt(q * (b - a) * (c - a))
        return b - math.sqrt((1.0 - q) * (b - a) * (b - c))

    def draw(self, rng: random.Random) -> float:
        if self.high <= self.low:
            return self.low
        if self.kind == "uniform":
            return rng.uniform(self.low, self.high)
        if self.kind == "lognormal":
            return self.quantile(rng.random())
        return rng.triangular(self.low, self.high, self.value)


_Z95 = statistics.NormalDist().inv_cdf(0.975)


class InvariantError(RuntimeError):
    """A Monte Carlo draw broke the Core Valuation Principles (an agent at
    €0). Never caught as a validation failure: the run stops."""


def _clip(name: str, unit: str, low: float, high: float) -> Tuple[float, float]:
    if unit in _UNIT_INTERVAL_UNITS or _OPEN_INTERVAL_NAMES.search(name):
        lo_bound = _EPS if _OPEN_INTERVAL_NAMES.search(name) else 0.0
        hi_bound = 1.0 - _EPS if _OPEN_INTERVAL_NAMES.search(name) else 1.0
        return max(low, lo_bound), min(high, hi_bound)
    return low, high


def sampled_parameters(params: Sequence[Param], paths: Dict[str, str]) -> List[Sampled]:
    """The parameters a Monte Carlo varies, with their distributions (see
    the module docstring for the rules)."""
    out: List[Sampled] = []
    for p in params:
        if p.name not in paths or p.confidence == Confidence.USER:
            continue
        if p.name in PROJECT_INPUTS or p.name.startswith(EXCLUDED_PREFIXES):
            continue
        if p.distribution == "fixed":
            continue
        bounds = p.bounds
        documented = bounds is not None
        if bounds is None:
            if p.value == 0.0:
                continue
            f_low, f_high = DEFAULT_RELATIVE_SPREAD[p.confidence]
            bounds = (p.value * f_low, p.value * f_high)
        low, high = _clip(p.name, p.unit, *sorted(bounds))
        if high <= low:
            continue
        out.append(Sampled(
            name=p.name, path=paths[p.name], value=min(max(p.value, low), high),
            low=low, high=high,
            kind="uniform" if p.distribution == "uniform" else "triangular",
            documented=documented, confidence=p.confidence.value,
        ))
    return out


# ── Production functions (Step 8f.3) ─────────────────────────────────────────


@dataclass(frozen=True)
class _ProductionEntry:
    """A service-ledger entry whose value a production function derives."""

    index: int            # its position in $.service_ledger
    agent: str
    agent_index: int      # its owner's position in $.agents
    field: str            # the agent field it feeds: annual_value_per_ha or site_value_per_ha
    weight: float         # the owner's documented dependency weight
    net: float            # the documented net value (€/ha/yr)
    agent_value: float    # the owner's documented value in ``field``


def production_entries(case) -> List[_ProductionEntry]:
    """The case's service-ledger entries derived from a production function."""
    doc = case.document
    if doc is None:
        return []
    agents = [a.get("name") for a in doc.get("agents", [])]
    out: List[_ProductionEntry] = []
    for i, entry in enumerate(case.service_ledger):
        if entry["production_function"] is None:
            continue
        field_ = "site_value_per_ha" if entry["site_restricted"] else "annual_value_per_ha"
        j = agents.index(entry["agent"])
        raw = doc["agents"][j].get(field_)
        if raw is None:
            raise ValueError(
                f"uncertainty: agent {entry['agent']!r} owns a production function but sets no {field_}"
            )
        weight = next(a.weight for a in case.agents if a.name == entry["agent"])
        out.append(_ProductionEntry(
            index=i, agent=entry["agent"], agent_index=j, field=field_, weight=weight,
            net=entry["value"], agent_value=float(raw["value"] if isinstance(raw, dict) else raw),
        ))
    return out


def production_sampled(case, entries: Sequence[_ProductionEntry]) -> List[Sampled]:
    """Each sampled link of each production function, with its own range
    and distribution (named "production[<agent>].<link>"). A link from the
    food web to the catch (gaia.production.CHAIN_PARAMETERS) that an
    earlier production function of the case documents identically (value,
    range, distribution) is the same quantity of the same food web: it
    takes that link's draw (``same_as``, Step 8g.2)."""
    from gaia.production import CHAIN_PARAMETERS

    out: List[Sampled] = []
    first: Dict[Tuple[str, float, float, float, str], str] = {}
    for e in entries:
        spec = case.service_ledger[e.index]["production_function"]
        for name, p in spec["parameters"].items():
            if p["distribution"] == "fixed" or not p.get("range"):
                continue
            low, high = p["range"]
            full = f"production[{e.agent}].{name}"
            same_as = ""
            if name in CHAIN_PARAMETERS:
                key = (name, p["value"], low, high, p["distribution"])
                same_as = first.setdefault(key, full)
                same_as = "" if same_as == full else same_as
            out.append(Sampled(
                name=full,
                path=f"$.service_ledger[{e.index}].production_function.{spec['paths'][name]}",
                value=p["value"], low=low, high=high, kind=p["distribution"],
                documented=True, confidence=p["status"], same_as=same_as,
            ))
    return out


def _draw_all(sampled: Sequence[Sampled], rng: random.Random) -> Dict[str, float]:
    """One draw of every sampled parameter (a ``same_as`` one takes the
    draw of the parameter it names)."""
    values: Dict[str, float] = {}
    for s in sampled:
        values[s.name] = values[s.same_as] if s.same_as else s.draw(rng)
    return values


def _with_aliases(values: Dict[str, float], sampled: Sequence[Sampled]) -> Dict[str, float]:
    """``values`` with each ``same_as`` parameter set like the one it names."""
    out = dict(values)
    for s in sampled:
        if s.same_as and s.same_as in out:
            out[s.name] = out[s.same_as]
    return out


def _rederive_production(doc: Dict[str, Any], entries: Sequence[_ProductionEntry]) -> Dict[str, Tuple[float, float]]:
    """Recompute, in a perturbed copy of the document, each production
    function's gross and net value and its owner's value; returns
    {agent: (gross, net)}.

    Raises:
        InvariantError: A net value <= 0 (an agent at €0).
    """
    from gaia.production import central, gross_value, net_value, parse_production_function

    ledger = doc["service_ledger"]
    booked = {e["service"]: e["value"] for e in ledger}
    out: Dict[str, Tuple[float, float]] = {}
    for e in entries:
        entry = ledger[e.index]
        spec = parse_production_function(entry["production_function"], f"$.service_ledger[{e.index}].production_function")
        gross = gross_value(central(spec))
        net = net_value(spec, gross, sum(booked[s] for s in entry.get("net_of", [])))
        if not net > 0.0:
            raise InvariantError(
                f"uncertainty: a draw of {e.agent}'s production function gives {net:.6g} €/ha/yr net: "
                f"an agent at €0 (PROJECT_DEFINITION.md, Core Valuation Principles (b)); fix the model or the ranges"
            )
        if "gross" in entry:
            entry["gross"] = gross
        entry["value"] = net
        _set_at_path(doc, f"$.agents[{e.agent_index}].{e.field}", e.agent_value + (net - e.net) / e.weight)
        out[e.agent] = (gross, net)
    return out


# ── Document surgery ─────────────────────────────────────────────────────────

_TOKEN = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


def _set_at_path(doc: Any, path: str, value: float) -> None:
    """Set the number at JSON path ``path`` ("$.agents[3].x") in ``doc``;
    a {value, ...} object gets its "value" set."""
    if not path.startswith("$"):
        raise ValueError(f"not a document path: {path!r}")
    tokens = [(m.group(1), m.group(2)) for m in _TOKEN.finditer(path[1:])]
    if "".join(f".{k}" if k else f"[{i}]" for k, i in tokens) != path[1:]:
        raise ValueError(f"unsupported document path: {path!r}")
    node = doc
    for key, index in tokens[:-1]:
        node = node[key] if key is not None else node[int(index)]
    key, index = tokens[-1]
    target = node[key] if key is not None else node[int(index)]
    if isinstance(target, dict):
        target["value"] = value
        # a draw is no longer the figure converted from another currency
        # (Step 8g.6, gaia.currency)
        target.pop("converted_from", None)
    elif key is not None:
        node[key] = value
    else:
        node[int(index)] = value


def _with_values(document: Dict[str, Any], values: Dict[str, float],
                 sampled: Dict[str, Sampled], weight_paths: Dict[str, str]) -> Dict[str, Any]:
    doc = copy.deepcopy(document)
    for name, value in values.items():
        _set_at_path(doc, sampled[name].path, value)
    if any(name in weight_paths for name in values):
        _renormalise_weights(doc, weight_paths)
    return doc


def _get_at_path(doc: Any, path: str) -> float:
    node = doc
    for m in _TOKEN.finditer(path[1:]):
        node = node[m.group(1)] if m.group(1) is not None else node[int(m.group(2))]
    return float(node["value"] if isinstance(node, dict) else node)


def _renormalise_weights(doc: Dict[str, Any], weight_paths: Dict[str, str]) -> None:
    total = sum(_get_at_path(doc, path) for path in weight_paths.values())
    for path in weight_paths.values():
        _set_at_path(doc, path, _get_at_path(doc, path) / total)


# ── Running ──────────────────────────────────────────────────────────────────


def _headlines(result) -> Dict[str, float]:
    npv = result.extraction_npv
    return {
        "annual_externality": result.annual_externality,
        "pv_services": npv.direct,
        "pv_carbon_release": npv.carbon_release,
        "pv_carbon_foregone": npv.carbon_foregone,
        "pv_externality": result.pv_externality,
        "net_social_cost": result.net_social_cost,
    }


def _percentile(sorted_values: List[float], p: float) -> float:
    """Linear-interpolation percentile (p in 0..100) of sorted values."""
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * p / 100.0
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_values[int(k)]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


@dataclass
class UncertaintyResult:
    """Monte Carlo summary of an extraction (see the module docstring).

    Attributes:
        draws: Number of successful draws.
        seed: Seed of the random generator.
        redraws: Draws rejected by validation and drawn again.
        base: Headline values at the documented parameter values.
        summary: {headline: {"p5", "p50", "p95", "mean"}}.
        sampled: The parameters varied.
        tornado: Rows {name, low_value, high_value, net_social_cost_low,
            net_social_cost_high, pv_externality_low, pv_externality_high,
            swing}, by decreasing swing of the net social cost.
        normative: Rows {name, description, pv_externality, net_social_cost}.
        not_sampled: Parameters left out and why, {reason: [names]}.
        production: {agent: summary of its production function's draws}
            (Step 8f.3): "service", "links" (the names sampled), "base"
            {"gross", "net"}, "gross" and "net" {"p5", "p50", "p95",
            "mean", "min", "max"} in €/ha/yr, "draws_at_or_below_zero".
    """

    draws: int
    seed: int
    redraws: int
    base: Dict[str, float]
    summary: Dict[str, Dict[str, float]]
    sampled: List[Sampled]
    tornado: List[Dict[str, Any]] = field(default_factory=list)
    normative: List[Dict[str, Any]] = field(default_factory=list)
    not_sampled: Dict[str, List[str]] = field(default_factory=dict)
    production: Dict[str, Dict[str, Any]] = field(default_factory=dict)


_DERIVED = "derived in each draw from its production function, whose links are sampled one by one"


def _not_sampled(params: Sequence[Param], sampled: Sequence[Sampled],
                 paths: Dict[str, str], derived: Sequence[str] = ()) -> Dict[str, List[str]]:
    taken = {s.name for s in sampled}
    reasons: Dict[str, List[str]] = {}
    for p in params:
        if p.name in taken:
            continue
        if p.name in derived:
            why = _DERIVED
        elif p.name.startswith(("discount.", "carbon_price.")):
            why = "normative (reported as a sensitivity)"
        elif p.name.startswith("model."):
            why = "model-wide constant (not in the document; not varied)"
        elif p.name in PROJECT_INPUTS or p.confidence == Confidence.USER:
            why = "input of the question (set by the user)"
        elif p.name.startswith(EXCLUDED_PREFIXES):
            why = "cannot change an extraction result"
        elif p.name not in paths:
            why = "not in the document"
        else:
            why = "fixed (distribution 'fixed', or zero without a range)"
        reasons.setdefault(why, []).append(p.name)
    return reasons


NORMATIVE_SCENARIOS: Tuple[Tuple[str, str], ...] = (
    ("carbon_price_ets", "carbon price: market/ETS view (€80/t) instead of the social cost"),
    ("carbon_price_scc_2_5pct", "carbon price: US EPA (2023) SC-CO2 at a 2.5% near-term rate ($120/t, 2020)"),
    ("carbon_price_scc_1_5pct", "carbon price: US EPA (2023) SC-CO2 at a 1.5% near-term rate ($340/t, 2020)"),
    ("discount_2pct_constant", "discount rate: 2.0% constant (the median expert recommendation, Drupp et al. 2018)"),
    ("scarcity_zero", "no relative price change of ecosystem services (scarcity 0%)"),
    ("horizon_100", "100-year horizon"),
)
"""Value judgements, evaluated one at a time at the documented parameter
values (not sampled)."""


def _normative_discount(name: str, discount):
    """The DiscountConfig of a normative scenario."""
    from gaia.carbon import ETS_CARBON_PRICE_EUR, USD_PER_EUR_2020

    if name == "carbon_price_ets":
        return dataclasses.replace(discount, carbon_price_current=ETS_CARBON_PRICE_EUR)
    if name == "carbon_price_scc_2_5pct":
        return dataclasses.replace(discount, carbon_price_current=120.0 / USD_PER_EUR_2020)
    if name == "carbon_price_scc_1_5pct":
        return dataclasses.replace(discount, carbon_price_current=340.0 / USD_PER_EUR_2020)
    if name == "discount_2pct_constant":
        return dataclasses.replace(discount, rate_schedule=0.02)
    if name == "scarcity_zero":
        return dataclasses.replace(discount, scarcity_rate=0.0)
    if name == "horizon_100":
        return dataclasses.replace(discount, horizon_years=100)
    raise ValueError(f"unknown normative scenario {name!r}")


def run_uncertainty(
    case,
    units: int,
    build_kwargs: Optional[Dict[str, Any]] = None,
    prepare: Optional[Callable[[Any], None]] = None,
    draws: int = DEFAULT_DRAWS,
    seed: int = DEFAULT_SEED,
    tornado: bool = True,
    normative: bool = True,
) -> UncertaintyResult:
    """Monte Carlo of an extraction of ``units`` units of ``case``.

    Args:
        case: A gaia.ecosystem_io.Case (with its document).
        units: Units extracted.
        build_kwargs: Case.build_ecosystem overrides (the user's inputs,
            held fixed in every draw).
        prepare: Called on each built ecosystem before the run (e.g. the
            --carbon-price view).
        draws: Number of successful draws (>= 2).
        seed: Seed of the random generator.
        tornado: Also compute the one-at-a-time ranking.
        normative: Also compute the normative sensitivities.

    Raises:
        ValueError: Without a document, for draws < 2, or when validation
            rejects too many draws (more than 10 per draw asked).
    """
    from gaia.ecosystem_io import case_from_dict
    from gaia.simulation import _resolve_discount, run_extraction
    from gaia.validation import CalibrationWarning

    if case.document is None:
        raise ValueError("the case has no document to perturb (build it with case_from_dict)")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 2:
        raise ValueError(f"draws must be an integer >= 2, got {draws!r}")
    kwargs = dict(build_kwargs or {})

    def evaluate(c, discount_scenario: Optional[str] = None) -> Dict[str, float]:
        eco = c.build_ecosystem(**kwargs)
        if prepare is not None:
            prepare(eco)
        if discount_scenario is not None:
            discount = _normative_discount(discount_scenario, _resolve_discount(eco.resource))
            eco.resource = dataclasses.replace(eco.resource, discount=discount)
        return _headlines(run_extraction(eco, units))

    base_eco = case.build_ecosystem(**kwargs)
    params = list(base_eco.provenance)
    # Step 8f.3: an agent value derived from a production function is not
    # sampled as one aggregate; its links are, one by one
    entries = production_entries(case)
    derived = [f"agent[{e.agent}].{e.field}" for e in entries]
    sampled = [s for s in sampled_parameters(params, case.param_paths) if s.name not in derived]
    sampled += production_sampled(case, entries)
    by_name = {s.name: s for s in sampled}
    weight_paths = {
        name: path for name, path in case.param_paths.items()
        if name.endswith(".dependency_weight")
    }
    weight_paths = weight_paths if any(n in by_name for n in weight_paths) else {}

    def build_case(values: Dict[str, float]):
        doc = _with_values(case.document, values, by_name, weight_paths)
        produced = _rederive_production(doc, entries) if entries else {}
        return case_from_dict(doc, origin=case.origin), produced

    rng = random.Random(seed)
    samples: Dict[str, List[float]] = {h: [] for h, _ in HEADLINES}
    produced_draws: Dict[str, List[Tuple[float, float]]] = {e.agent: [] for e in entries}
    redraws = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", CalibrationWarning)
        base = evaluate(case)
        while len(samples["net_social_cost"]) < draws:
            values = _draw_all(sampled, rng)
            try:
                drawn, produced = build_case(values)
                row = evaluate(drawn)
            except ValueError:
                redraws += 1
                if redraws > 10 * draws:
                    raise ValueError(
                        f"uncertainty: {redraws} draws rejected by validation; "
                        f"the parameter ranges are inconsistent"
                    ) from None
                continue
            for key, value in row.items():
                samples[key].append(value)
            for agent, pair in produced.items():
                produced_draws[agent].append(pair)

        summary: Dict[str, Dict[str, float]] = {}
        for key, values_ in samples.items():
            ordered = sorted(values_)
            summary[key] = {f"p{p}": _percentile(ordered, p) for p in PERCENTILES}
            summary[key]["mean"] = sum(ordered) / len(ordered)
        production = _production_summary(case, entries, sampled, produced_draws)

        rows: List[Dict[str, Any]] = []
        if tornado:
            for s in sampled:
                if s.same_as:
                    continue
                lo_v, hi_v = s.quantile(0.05), s.quantile(0.95)
                try:
                    lo = evaluate(build_case(_with_aliases({s.name: lo_v}, sampled))[0])
                    hi = evaluate(build_case(_with_aliases({s.name: hi_v}, sampled))[0])
                except ValueError:
                    continue
                rows.append({
                    "name": s.name,
                    "low_value": lo_v,
                    "high_value": hi_v,
                    "net_social_cost_low": lo["net_social_cost"],
                    "net_social_cost_high": hi["net_social_cost"],
                    "pv_externality_low": lo["pv_externality"],
                    "pv_externality_high": hi["pv_externality"],
                    "swing": abs(hi["net_social_cost"] - lo["net_social_cost"]),
                })
            rows.sort(key=lambda r: (-r["swing"], r["name"]))

        norm_rows: List[Dict[str, Any]] = []
        if normative:
            for name, description in NORMATIVE_SCENARIOS:
                try:
                    row = evaluate(case, discount_scenario=name)
                except ValueError as exc:
                    norm_rows.append({"name": name, "description": description,
                                      "pv_externality": None, "net_social_cost": None,
                                      "error": str(exc)})
                    continue
                norm_rows.append({"name": name, "description": description,
                                  "pv_externality": row["pv_externality"],
                                  "net_social_cost": row["net_social_cost"]})

    return UncertaintyResult(
        draws=draws, seed=seed, redraws=redraws, base=base, summary=summary,
        sampled=sampled, tornado=rows, normative=norm_rows,
        not_sampled=_not_sampled(params, sampled, case.param_paths, derived),
        production=production,
    )


def _summarise(values: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(values)
    out = {f"p{p}": _percentile(ordered, p) for p in PERCENTILES}
    out.update(mean=sum(ordered) / len(ordered), min=ordered[0], max=ordered[-1])
    return out


def _production_summary(case, entries: Sequence[_ProductionEntry], sampled: Sequence[Sampled],
                        produced: Dict[str, List[Tuple[float, float]]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        entry = case.service_ledger[e.index]
        pairs = produced[e.agent]
        prefix = f"production[{e.agent}]."
        out[e.agent] = {
            "service": entry["service"],
            "links": [s.name[len(prefix):] for s in sampled if s.name.startswith(prefix)],
            "base": {"gross": entry["gross"] if entry["gross"] is not None else entry["value"],
                     "net": entry["value"]},
            "gross": _summarise([g for g, _ in pairs]),
            "net": _summarise([n for _, n in pairs]),
            "draws_at_or_below_zero": sum(1 for _, n in pairs if not n > 0.0),
        }
    return out


# ── Output ───────────────────────────────────────────────────────────────────

METHOD: str = (
    "Monte Carlo over the case's recorded parameters (gaia.uncertainty): each "
    "sampled from its documented range, or from a range set by its confidence "
    "(high ±10%, medium ±25%, low ×/÷2, placeholder ×/÷3), triangular with the "
    "documented value as mode unless stated; a value derived from a "
    "production function is not sampled as one aggregate: each link of the "
    "chain is sampled from its own range and distribution and every draw "
    "recomputes the chain and the net value (Step 8f.3); normative choices (discounting, "
    "carbon price) are sensitivities, not sampled; model-wide constants are "
    "not varied. P5/P50/P95 of the draws; tornado: one parameter at a time at "
    "its own P5 and P95, the others at their documented values. Replaces the "
    "former heuristic band (finding S7)."
)


def uncertainty_to_dict(u: Optional[UncertaintyResult], top: int = 15) -> Optional[Dict[str, Any]]:
    """The JSON "uncertainty" block (None when there is no analysis)."""
    if u is None:
        return None
    units = dict(HEADLINES)
    return {
        "method": METHOD,
        "draws": u.draws,
        "seed": u.seed,
        "redraws_rejected_by_validation": u.redraws,
        "headlines": {
            key: {
                "unit": units[key],
                "base": round(u.base[key], 2),
                **{k: round(v, 2) for k, v in u.summary[key].items()},
            }
            for key in u.summary
        },
        "sampled_parameters": [
            dict({"name": s.name, "value": s.value, "low": s.low, "high": s.high,
                  "distribution": s.kind,
                  "range_from": "document" if s.documented else f"confidence ({s.confidence})"},
                 **({"same_draw_as": s.same_as} if s.same_as else {}))
            for s in u.sampled
        ],
        "tornado_net_social_cost": [
            {k: (round(v, 6) if k in ("low_value", "high_value") else round(v, 2)) if isinstance(v, float) else v
             for k, v in row.items()}
            for row in u.tornado[:top]
        ],
        "normative_sensitivities": [
            {k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()}
            for row in u.normative
        ],
        "not_sampled": u.not_sampled,
        "production_functions": {
            agent: {
                "service": block["service"],
                "unit": "€/ha/yr",
                "links_sampled": block["links"],
                "base": {k: round(v, 2) for k, v in block["base"].items()},
                "gross": {k: round(v, 2) for k, v in block["gross"].items()},
                "net": {k: round(v, 2) for k, v in block["net"].items()},
                "draws_at_or_below_zero": block["draws_at_or_below_zero"],
            }
            for agent, block in u.production.items()
        } or None,
    }


def format_uncertainty(u: Optional[UncertaintyResult], top: int = 10) -> str:
    """The text report section ("" when there is no analysis)."""
    if u is None:
        return ""
    labels = {
        "annual_externality": "Annual externality (€/yr)",
        "pv_services": "  PV services",
        "pv_carbon_release": "  PV carbon released",
        "pv_carbon_foregone": "  PV absorption lost",
        "pv_externality": "PV of externality",
        "net_social_cost": "NET SOCIAL COST (PV)",
    }
    lines: List[str] = [
        "",
        "  ── Uncertainty (Monte Carlo, Step 8.4) ─" + "─" * 23,
        f"  {u.draws:,} draws, seed {u.seed}, {sum(1 for s in u.sampled if not s.same_as)} parameters sampled"
        f" ({u.redraws} redraws rejected by validation)",
        f"  {'':<28} {'P5':>11} {'P50':>11} {'P95':>11} {'base':>11}",
    ]
    for key, label in labels.items():
        s = u.summary[key]
        lines.append(
            f"  {label:<28} {_short(s['p5']):>11} {_short(s['p50']):>11} "
            f"{_short(s['p95']):>11} {_short(u.base[key]):>11}"
        )
    for agent, block in u.production.items():
        lines.append("")
        lines.extend(textwrap.wrap(
            f"{agent}, {block['service'].split(':')[0].lower()} (€/ha/yr; each of its "
            f"{len(block['links'])} uncertain links sampled from its own distribution, the chain recomputed):",
            width=65, initial_indent="  ", subsequent_indent="  "))
        lines.append(f"  {'':<28} {'P5':>11} {'P50':>11} {'P95':>11} {'base':>11}")
        for key, label in (("gross", "  gross"), ("net", "  net (the agent's value)")):
            s = block[key]
            cells = [s["p5"], s["p50"], s["p95"], block["base"][key]]
            lines.append(f"  {label:<28} " + " ".join(f"{f'€{v:,.0f}':>11}" for v in cells))
        lines.append(f"    lowest draw €{block['net']['min']:,.2f} net; draws at or below €0: "
                     f"{block['draws_at_or_below_zero']}")
    if u.tornado:
        lines.append("")
        lines.append("  Sensitivity (net social cost, each parameter at its P5 / P95):")
        for row in u.tornado[:top]:
            lines.append(
                f"    {_short(row['swing']):>9}  {row['name']}"
                f"  [{row['low_value']:.4g} → {row['high_value']:.4g}]"
            )
    if u.normative:
        lines.append("")
        lines.append("  Normative choices (not sampled; net social cost, PV):")
        for row in u.normative:
            lines.append(f"    {_short(row['net_social_cost']) if row['net_social_cost'] is not None else 'n/a':>11}  {row['description']}")
    lines.append("")
    lines.extend(textwrap.wrap(
        "Not varied: model-wide constants (trophic, keystone), the project "
        "inputs, and parameters marked fixed (list: JSON \"uncertainty\"). "
        "The bounds are only as good as the parameter ranges, most of which "
        "are judgements (for Posidonia: docs/POSIDONIA_METHODS_NOTE.md).",
        width=65, initial_indent="  ", subsequent_indent="  ",
    ))
    return "\n".join(lines) + "\n"


def _short(value: float) -> str:
    """€ with k/M/bn suffix for the table."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1e9:
        return f"{sign}€{v / 1e9:,.2f}bn"
    if v >= 1e6:
        return f"{sign}€{v / 1e6:,.2f}M"
    if v >= 1e3:
        return f"{sign}€{v / 1e3:,.1f}k"
    return f"{sign}€{v:,.0f}"
