"""
Gaia — independent benchmarks for a case's per-hectare values (Step 8.3).

A case document may list published per-hectare values for the same
ecosystem (``run.benchmarks``: name, low, high, unit, source, optional central,
note and ``includes_carbon``). For an extraction result, ``benchmark_comparison``
reports where Gaia's own per-hectare figures fall among them:

    full_damage      Σ weight × annual_value_per_ha: the yearly service value
                     of one hectare at full damage (carbon excluded; carbon
                     is valued by gaia.carbon)
    with_burial      full_damage + the hectare's yearly carbon burial at the
                     year-0 carbon price (for benchmarks that include
                     climate regulation)
    realised_per_ha  the run's annual externality / hectares lost: what the
                     damage curves and cascades actually charge per hectare
    linear_transfer  hectares lost × full_damage: the plain benefit transfer
                     most impact assessments would use

Benchmarks in international dollars are converted to euros at Spain's PPP
for their price year (Step 8g.6, gaia.currency; the case file records it,
``converted_from``); the others are in their own currency and price year.
No price-year adjustment: the comparison is an order of magnitude
("below", "within", "above" and the ratio of the benchmark midpoint to
Gaia's figure), not a test.

No third-party dependencies.
"""

import textwrap
from typing import Any, Dict, List, Optional, Sequence

from gaia.models import SimulationResult


def _position(value: float, low: float, high: float) -> str:
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "within"


def benchmark_comparison(result: Any, benchmarks: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Gaia's per-hectare figures for ``result`` against ``benchmarks``.

    Returns None for a restoration result or when there are no benchmarks.
    """
    if not benchmarks or not isinstance(result, SimulationResult):
        return None
    eco = result.ecosystem
    resource = eco.resource
    full: float = sum(a.dependency_weight * a.annual_value(1.0) for a in eco.agents)
    burial: float = 0.0
    if resource.carbon_profile is not None and result.discount is not None:
        burial = (
            resource.carbon_profile.annual_absorption_tonnes * resource.units_per_ha
            * result.discount.carbon_price_at_year(0)
        )
    ha_lost: float = result.total_units_extracted / resource.units_per_ha
    realised: float = result.annual_externality / ha_lost if ha_lost > 0 else 0.0
    rows: List[Dict[str, Any]] = []
    for b in benchmarks:
        gaia_value = full + burial if b.get("includes_carbon") else full
        mid = b["central"] if b.get("central") is not None else (b["low"] + b["high"]) / 2.0
        rows.append({
            "name": b["name"],
            "low": b["low"],
            "high": b["high"],
            "central": b.get("central"),
            "unit": b["unit"],
            "source": b["source"],
            "note": b.get("note", ""),
            "includes_carbon": bool(b.get("includes_carbon", False)),
            "gaia_value_eur_per_ha_yr": round(gaia_value, 2),
            "position": _position(gaia_value, b["low"], b["high"]),
            "benchmark_central_over_gaia": round(mid / gaia_value, 2) if gaia_value > 0 else None,
        })
    return {
        "full_damage_eur_per_ha_yr": round(full, 2),
        "carbon_burial_eur_per_ha_yr": round(burial, 2),
        "full_damage_with_burial_eur_per_ha_yr": round(full + burial, 2),
        "hectares_lost": round(ha_lost, 4),
        "realised_loss_eur_per_ha_yr": round(realised, 2),
        "linear_transfer_eur_yr": round(full * ha_lost, 2),
        "annual_externality_eur_yr": round(result.annual_externality, 2),
        "method": (
            "Benchmarks in international dollars converted to euros at Spain's PPP for "
            "their price year (gaia.currency); the others in their own currency and "
            "price year; no price-year adjustment: an order-of-magnitude comparison. "
            "Gaia's carbon release (a stock, released at once or over time) is not in "
            "any per-hectare yearly figure."
        ),
        "benchmarks": rows,
    }


def _wrap_line(text: str) -> List[str]:
    return textwrap.wrap(text, width=65, initial_indent="    ", subsequent_indent="      ")


def format_benchmarks(block: Optional[Dict[str, Any]]) -> str:
    """The text section for a benchmark_comparison block ("" when None)."""
    if not block:
        return ""
    lines: List[str] = [
        "",
        "  ── Benchmarks (per hectare, Step 8.3) ─" + "─" * 25,
        f"  {'Service value at full damage:':<40} {block['full_damage_eur_per_ha_yr']:>12,.2f}€/ha/yr",
        f"  {'  + carbon burial at the carbon price:':<40} {block['full_damage_with_burial_eur_per_ha_yr']:>12,.2f}€/ha/yr",
        f"  {'Charged per hectare lost (this run):':<40} {block['realised_loss_eur_per_ha_yr']:>12,.2f}€/ha/yr",
        f"  {'Linear benefit transfer (ha × value):':<40} {block['linear_transfer_eur_yr']:>12,.2f}€/yr"
        f"  (Gaia: {block['annual_externality_eur_yr']:,.2f}€/yr)",
        "  Published values (Int$ converted to € at PPP; own price year):",
    ]
    for row in block["benchmarks"]:
        ratio = row["benchmark_central_over_gaia"]
        rel = f"{row['position']}" + (f", central value {ratio:,.1f}× Gaia" if ratio is not None else "")
        span = (f"{row['low']:,.0f}" if row["low"] == row["high"]
                else f"{row['low']:,.0f}–{row['high']:,.0f}")
        if row["central"] is not None and row["low"] != row["high"]:
            span += f" (central {row['central']:,.0f})"
        lines.extend(_wrap_line(f"{row['name']}: {span} {row['unit']}"))
        lines.extend(_wrap_line(f"  → Gaia {row['gaia_value_eur_per_ha_yr']:,.0f}€/ha/yr is {rel}"))
    return "\n".join(lines) + "\n"
