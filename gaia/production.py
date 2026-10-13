"""
Gaia — production functions: from primary production to what people eat
(Step 8e.6, 8f; PROJECT_DEFINITION.md, "Core Valuation Principles", (d), (e)).

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
"inferred"), "range": [low, high]}}, "producers": [{"name"*, "description"*,
"parameters"*: {...}}], "comparison": {"metric"*, "unit"*, "rows"*:
[{"ecosystem"*, "value" | "low" and "high", "source"*, "note"}]}}.

``parameters`` holds the eight links of the chain (``PARAMETERS``), the
first three of them for the main producer. ``producers`` (Step 8f.2,
optional) adds other primary producers whose production enters the same
food web (for Posidonia: the roots, and the epiphytes on the leaves), each
with ``npp_dry_weight`` and ``carbon_fraction``, or ``npp_carbon``, and its
own ``food_web_share``. Their parameters are named ``<name>.<parameter>``
(e.g. "roots.npp_dry_weight") in the parsed form. Parsing checks that the
entry's ``gross`` is the chain's result. No third-party dependencies.
"""

import math
import re
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

# the parameter sets an additional producer may give
PRODUCER_PARAMETERS: Tuple[Tuple[str, ...], ...] = (
    ("npp_dry_weight", "carbon_fraction", "food_web_share"),
    ("npp_carbon", "food_web_share"),
)

STATUSES: Tuple[str, ...] = ("verified", "derived", "secondary", "inferred")

# parameters that must lie in (0, 1]
_FRACTIONS = ("carbon_fraction", "food_web_share", "transfer_efficiency", "sustainable_catch_share")

_PRODUCER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_DEFAULT_PRODUCER = "the plant"


def _producer_names(values: Dict[str, float]) -> List[str]:
    """Names of the additional producers in ``values``, in order."""
    return list(dict.fromkeys(k.split(".", 1)[0] for k in values if "." in k))


def producer_carbon(values: Dict[str, float]) -> List[Tuple[str, float, float]]:
    """[(producer, net primary production in g C/m²/yr, share entering the
    food web)], the main producer ("") first."""
    out = [("", values["npp_dry_weight"] * values["carbon_fraction"], values["food_web_share"])]
    for name in _producer_names(values):
        if f"{name}.npp_carbon" in values:
            carbon = values[f"{name}.npp_carbon"]
        else:
            carbon = values[f"{name}.npp_dry_weight"] * values[f"{name}.carbon_fraction"]
        out.append((name, carbon, values[f"{name}.food_web_share"]))
    return out


def chain(values: Dict[str, float], producer: str = _DEFAULT_PRODUCER) -> List[Tuple[str, float, str]]:
    """The steps of the chain, [(what, value, unit)], the last one in €/ha/yr."""
    producers = producer_carbon(values)
    steps: List[Tuple[str, float, str]] = []
    if len(producers) == 1:
        steps.append(("net primary production", values["npp_dry_weight"], "g DW/m²/yr"))
        steps.append(("net primary production, carbon", producers[0][1], "g C/m²/yr"))
    else:
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
    (additional producers' parameters as "<name>.<parameter>")."""
    return {name: p["value"] for name, p in spec["parameters"].items()}


def gross_range(spec: Dict[str, Any]) -> Tuple[float, float]:
    """(lowest, highest) gross value over the parameters' ranges (each
    parameter at its value without a range). The chain rises with every
    parameter but the catch's trophic level (a transfer efficiency is at
    most 1), so the ends are the corners where every link is at its least
    and at its most favourable end."""
    params = spec["parameters"]

    def end(favourable: bool) -> Dict[str, float]:
        out = {}
        for name, p in params.items():
            low, high = p["range"] if p.get("range") else (p["value"], p["value"])
            rising = name != "catch_trophic_level"
            out[name] = high if favourable == rising else low
        return out

    return gross_value(end(False)), gross_value(end(True))


def parse_production_function(raw: Any, path: str) -> Dict[str, Any]:
    """Validate a ledger entry's ``production_function`` block (see the
    module docstring); returns it with numbers as floats, the parameters
    flat ({name: parameter}, additional producers' as "<name>.<parameter>")
    and each parameter's JSON path relative to the block (``paths``).

    Raises:
        ValueError: Naming the JSON path of the first problem.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected an object")
    unknown = set(raw) - {"model", "producer", "parameters", "producers", "comparison"}
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
    params = _parse_parameters(params_raw, PARAMETERS, f"{path}.parameters")
    paths = {name: f"parameters.{name}" for name in params}
    producers: List[Dict[str, Any]] = []
    producers_raw = raw.get("producers", [])
    if not isinstance(producers_raw, list):
        raise ValueError(f"{path}.producers: expected a list")
    for i, prod in enumerate(producers_raw):
        ppath = f"{path}.producers[{i}]"
        if not isinstance(prod, dict) or set(prod) - {"name", "description", "parameters"}:
            raise ValueError(f"{ppath}: expected an object with name, description and parameters")
        name = prod.get("name")
        if not isinstance(name, str) or not _PRODUCER_NAME.match(name):
            raise ValueError(f"{ppath}.name: lower-case letters, digits and _, got {name!r}")
        if any(p["name"] == name for p in producers):
            raise ValueError(f"{ppath}.name: {name!r} is listed twice")
        if not isinstance(prod.get("description"), str) or not prod["description"]:
            raise ValueError(f"{ppath}.description: required, a non-empty string")
        given = prod.get("parameters")
        if not isinstance(given, dict):
            raise ValueError(f"{ppath}.parameters: expected an object")
        expected = next((s for s in PRODUCER_PARAMETERS if set(s) == set(given)), None)
        if expected is None:
            raise ValueError(
                f"{ppath}.parameters: give " + " or ".join(", ".join(s) for s in PRODUCER_PARAMETERS)
                + f", got {', '.join(sorted(given)) or 'none'}"
            )
        parsed = _parse_parameters(given, expected, f"{ppath}.parameters")
        for key, p in parsed.items():
            params[f"{name}.{key}"] = p
            paths[f"{name}.{key}"] = f"producers[{i}].parameters.{key}"
        producers.append({"name": name, "description": prod["description"]})
    spec: Dict[str, Any] = {"model": MODEL, "producer": producer, "parameters": params,
                            "producers": producers, "paths": paths, "comparison": None}
    if "comparison" in raw:
        spec["comparison"] = _parse_comparison(raw["comparison"], f"{path}.comparison")
    return spec


def _parse_parameters(raw: Dict[str, Any], names: Tuple[str, ...], path: str) -> Dict[str, Dict[str, Any]]:
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
            if name == "catch_trophic_level" and low < 1.0:
                raise ValueError(f"{ppath}.range: a trophic level is >= 1")
            out["range"] = (low, high)
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
    npp = f"NPP {_num(producers[0][1])} g C/m²/yr ({_num(values['npp_dry_weight'])} g dry weight)"
    if len(producers) > 1:
        others = " + ".join(f"{name.replace('_', ' ')} {_num(c)}" for name, c, _ in producers[1:])
        npp += f" + {others} = {_num(sum(c for _, c, _ in producers))} g C/m²/yr"
    return (
        f"Primary production → food: {npp} "
        f"→ {_num(web)} kg C/ha/yr into the food web (not buried) → {_num(fish)} kg fish and "
        f"invertebrates/ha/yr (trophic level {p['catch_trophic_level']['value']:g}) → {_num(catch)} kg/ha/yr "
        f"sustainable catch × €{p['first_sale_price']['value']:.2f}/kg = €{_num(gross)}/ha/yr; minus "
        f"€{_num(counted)} already counted ({counted_in}) = €{_num(net)}/ha/yr"
    )


def production_block(spec: Dict[str, Any], gross: float, counted: float, net: float,
                     net_of: List[str]) -> Dict[str, Any]:
    """The JSON form of a production function: its parameters, its chain,
    the gross value, what was subtracted, the net value, the comparison."""
    low, high = gross_range(spec)
    return {
        "model": spec["model"],
        "producer": spec["producer"],
        "parameters": {
            name: dict(p, range=list(p["range"]) if p.get("range") else None)
            for name, p in spec["parameters"].items()
        },
        "producers": [dict(p) for p in spec["producers"]],
        "chain": [{"step": what, "value": value, "unit": unit}
                  for what, value, unit in chain(central(spec), spec["producer"])],
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
