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
        kind: "triangular" or "uniform".
        documented: True when the range comes from the document, False
            when it was set by the confidence (DEFAULT_RELATIVE_SPREAD).
        confidence: The parameter's confidence.
    """

    name: str
    path: str
    value: float
    low: float
    high: float
    kind: str
    documented: bool
    confidence: str

    def quantile(self, q: float) -> float:
        """The q-quantile (0..1) of this parameter's distribution."""
        a, b, c = self.low, self.high, self.value
        if b <= a:
            return a
        if self.kind == "uniform":
            return a + q * (b - a)
        f = (c - a) / (b - a)
        if q < f:
            return a + math.sqrt(q * (b - a) * (c - a))
        return b - math.sqrt((1.0 - q) * (b - a) * (b - c))

    def draw(self, rng: random.Random) -> float:
        if self.high <= self.low:
            return self.low
        if self.kind == "uniform":
            return rng.uniform(self.low, self.high)
        return rng.triangular(self.low, self.high, self.value)


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


def _not_sampled(params: Sequence[Param], sampled: Sequence[Sampled],
                 paths: Dict[str, str]) -> Dict[str, List[str]]:
    taken = {s.name for s in sampled}
    reasons: Dict[str, List[str]] = {}
    for p in params:
        if p.name in taken:
            continue
        if p.name.startswith(("discount.", "carbon_price.")):
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
    sampled = sampled_parameters(params, case.param_paths)
    by_name = {s.name: s for s in sampled}
    weight_paths = {
        name: path for name, path in case.param_paths.items()
        if name.endswith(".dependency_weight")
    }
    weight_paths = weight_paths if any(n in by_name for n in weight_paths) else {}

    def build_case(values: Dict[str, float]):
        doc = _with_values(case.document, values, by_name, weight_paths)
        return case_from_dict(doc, origin=case.origin)

    rng = random.Random(seed)
    samples: Dict[str, List[float]] = {h: [] for h, _ in HEADLINES}
    redraws = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", CalibrationWarning)
        base = evaluate(case)
        while len(samples["net_social_cost"]) < draws:
            values = {s.name: s.draw(rng) for s in sampled}
            try:
                row = evaluate(build_case(values))
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

        summary: Dict[str, Dict[str, float]] = {}
        for key, values_ in samples.items():
            ordered = sorted(values_)
            summary[key] = {f"p{p}": _percentile(ordered, p) for p in PERCENTILES}
            summary[key]["mean"] = sum(ordered) / len(ordered)

        rows: List[Dict[str, Any]] = []
        if tornado:
            for s in sampled:
                lo_v, hi_v = s.quantile(0.05), s.quantile(0.95)
                try:
                    lo = evaluate(build_case({s.name: lo_v}))
                    hi = evaluate(build_case({s.name: hi_v}))
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
        not_sampled=_not_sampled(params, sampled, case.param_paths),
    )


# ── Output ───────────────────────────────────────────────────────────────────

METHOD: str = (
    "Monte Carlo over the case's recorded parameters (gaia.uncertainty): each "
    "sampled from its documented range, or from a range set by its confidence "
    "(high ±10%, medium ±25%, low ×/÷2, placeholder ×/÷3), triangular with the "
    "documented value as mode unless stated; normative choices (discounting, "
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
            {"name": s.name, "value": s.value, "low": s.low, "high": s.high,
             "distribution": s.kind, "range_from": "document" if s.documented else f"confidence ({s.confidence})"}
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
        f"  {u.draws:,} draws, seed {u.seed}, {len(u.sampled)} parameters sampled"
        f" ({u.redraws} redraws rejected by validation)",
        f"  {'':<28} {'P5':>11} {'P50':>11} {'P95':>11} {'base':>11}",
    ]
    for key, label in labels.items():
        s = u.summary[key]
        lines.append(
            f"  {label:<28} {_short(s['p5']):>11} {_short(s['p50']):>11} "
            f"{_short(s['p95']):>11} {_short(u.base[key]):>11}"
        )
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
