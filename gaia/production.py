"""
Gaia — production functions: from primary production to what people eat
(Step 8e.6; PROJECT_DEFINITION.md, "Core Valuation Principles", (d), (e)).

Where no stated-preference value exists, a foundation species is valued
through the food its primary production supports. The "trophic_transfer"
model follows the energy from the plant to the catch:

    NPP (g dry weight/m²/yr)
      × carbon_fraction                       → g C/m²/yr
      × 10                                    → kg C/ha/yr
      × food_web_share                        → kg C/ha/yr entering the food web
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
{"model": "trophic_transfer", "parameters": {<name>: {"value"*, "unit"*,
"label"*, "source"*, "status"* ("verified" | "derived" | "secondary" |
"inferred"), "range": [low, high]}}, "comparison": {"metric"*, "unit"*,
"rows"*: [{"ecosystem"*, "value" | "low" and "high", "source"*,
"note"}]}}. Parsing checks that the entry's ``gross`` is the chain's
result. No third-party dependencies.
"""

import itertools
import math
from typing import Any, Dict, List, Tuple

MODEL = "trophic_transfer"

# (name, what it does in the chain) in chain order; every one is required
PARAMETERS: Tuple[str, ...] = (
    "npp_dry_weight",
    "carbon_fraction",
    "food_web_share",
    "transfer_efficiency",
    "catch_trophic_level",
    "wet_weight_per_carbon",
    "sustainable_catch_share",
    "first_sale_price",
)

STATUSES: Tuple[str, ...] = ("verified", "derived", "secondary", "inferred")

# parameters that must lie in (0, 1]
_FRACTIONS = ("carbon_fraction", "food_web_share", "transfer_efficiency", "sustainable_catch_share")


def chain(values: Dict[str, float]) -> List[Tuple[str, float, str]]:
    """The steps of the chain, [(what, value, unit)], the last one in €/ha/yr."""
    npp_c = values["npp_dry_weight"] * values["carbon_fraction"]
    web = npp_c * 10.0 * values["food_web_share"]
    steps = values["catch_trophic_level"] - 1.0
    consumers_c = web * values["transfer_efficiency"] ** steps
    fish = consumers_c * values["wet_weight_per_carbon"]
    catch = fish * values["sustainable_catch_share"]
    euros = catch * values["first_sale_price"]
    return [
        ("net primary production", values["npp_dry_weight"], "g DW/m²/yr"),
        ("net primary production, carbon", npp_c, "g C/m²/yr"),
        ("entering the food web", web, "kg C/ha/yr"),
        (f"consumer production at trophic level {values['catch_trophic_level']:g}", consumers_c, "kg C/ha/yr"),
        ("fish and invertebrates produced", fish, "kg/ha/yr"),
        ("sustainable catch", catch, "kg/ha/yr"),
        ("food value at first-sale prices", euros, "€/ha/yr"),
    ]


def gross_value(values: Dict[str, float]) -> float:
    """€/ha/yr of food supported (the chain's last step)."""
    return chain(values)[-1][1]


def central(spec: Dict[str, Any]) -> Dict[str, float]:
    """{parameter: documented value} of a parsed production function."""
    return {name: p["value"] for name, p in spec["parameters"].items()}


def gross_range(spec: Dict[str, Any]) -> Tuple[float, float]:
    """(lowest, highest) gross value over every combination of the
    parameters' range ends (each parameter at its value without a range)."""
    params = spec["parameters"]
    choices = [p["range"] if p.get("range") else (p["value"],) for p in (params[n] for n in PARAMETERS)]
    results = [gross_value(dict(zip(PARAMETERS, combo))) for combo in itertools.product(*choices)]
    return min(results), max(results)


def parse_production_function(raw: Any, path: str) -> Dict[str, Any]:
    """Validate a ledger entry's ``production_function`` block (see the
    module docstring); returns it with numbers as floats.

    Raises:
        ValueError: Naming the JSON path of the first problem.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object")
    unknown = set(raw) - {"model", "parameters", "comparison"}
    if unknown:
        raise ValueError(f"{path}: unknown key {sorted(unknown)[0]!r}")
    if raw.get("model") != MODEL:
        raise ValueError(f"{path}.model: expected {MODEL!r}, got {raw.get('model')!r}")
    params_raw = raw.get("parameters")
    if not isinstance(params_raw, dict):
        raise ValueError(f"{path}.parameters: expected an object")
    missing = [n for n in PARAMETERS if n not in params_raw]
    if missing:
        raise ValueError(f"{path}.parameters: missing {missing[0]!r} (required: {', '.join(PARAMETERS)})")
    extra = [n for n in params_raw if n not in PARAMETERS]
    if extra:
        raise ValueError(f"{path}.parameters: unknown parameter {extra[0]!r}")
    params: Dict[str, Dict[str, Any]] = {}
    for name in PARAMETERS:
        ppath = f"{path}.parameters.{name}"
        p = params_raw[name]
        if not isinstance(p, dict):
            raise ValueError(f"{ppath}: expected an object")
        bad = set(p) - {"value", "unit", "label", "source", "status", "range"}
        if bad:
            raise ValueError(f"{ppath}: unknown key {sorted(bad)[0]!r}")
        for key in ("unit", "label", "source", "status"):
            if not isinstance(p.get(key), str) or not p[key]:
                raise ValueError(f"{ppath}.{key}: required, a non-empty string")
        if p["status"] not in STATUSES:
            raise ValueError(f"{ppath}.status: expected one of {list(STATUSES)}, got {p['status']!r}")
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
            out["range"] = (low, high)
        params[name] = out
    spec: Dict[str, Any] = {"model": MODEL, "parameters": params, "comparison": None}
    if "comparison" in raw:
        spec["comparison"] = _parse_comparison(raw["comparison"], f"{path}.comparison")
    return spec


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
    steps = chain(central(spec))
    npp_dw, npp_c, web, _, fish, catch, euros = (v for _, v, _ in steps)
    p = spec["parameters"]
    return (
        f"Primary production → food: NPP {_num(npp_c)} g C/m²/yr ({_num(npp_dw)} g dry weight) "
        f"→ {_num(web)} kg C/ha/yr into the food web → {_num(fish)} kg fish and invertebrates/ha/yr "
        f"(trophic level {p['catch_trophic_level']['value']:g}) → {_num(catch)} kg/ha/yr sustainable catch "
        f"× €{p['first_sale_price']['value']:.2f}/kg = €{_num(gross)}/ha/yr; minus €{_num(counted)} "
        f"already counted ({counted_in}) = €{_num(net)}/ha/yr"
    )


def production_block(spec: Dict[str, Any], gross: float, counted: float, net: float,
                     net_of: List[str]) -> Dict[str, Any]:
    """The JSON form of a production function: its parameters, its chain,
    the gross value, what was subtracted, the net value, the comparison."""
    low, high = gross_range(spec)
    return {
        "model": spec["model"],
        "parameters": {
            name: dict(p, range=list(p["range"]) if p.get("range") else None)
            for name, p in spec["parameters"].items()
        },
        "chain": [{"step": what, "value": value, "unit": unit} for what, value, unit in chain(central(spec))],
        "gross_eur_per_ha_yr": gross,
        "gross_range_eur_per_ha_yr": [low, high],
        "net_of": list(net_of),
        "already_counted_eur_per_ha_yr": counted,
        "net_eur_per_ha_yr": net,
        "comparison": spec["comparison"],
    }


def format_comparison(comparison: Dict[str, Any]) -> List[str]:
    """Report lines of the productivity comparison table."""
    lines = [f"  {comparison['metric'].capitalize()}, {comparison['unit']}:"]
    for row in comparison["rows"]:
        value = _num(row["low"]) if row["low"] == row["high"] else f"{_num(row['low'])}–{_num(row['high'])}"
        lines.append(f"    {row['ecosystem'] + ':':<58} {value:>11}")
    return lines
