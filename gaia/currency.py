"""
Gaia — international dollars to euros, in one place (Step 8g.6).

Benefit-transfer values from the ESVD / TEEB syntheses (de Groot et al.
2012; Costanza et al. 2014) and from meta-analyses standardised the same way
(Stamatiadou et al. 2025) are in international dollars (Int$): US dollars
with the purchasing power a dollar has in the United States, so they convert
to a country's currency at its purchasing-power-parity rate, not at the
market exchange rate (de Groot et al. 2012, footnote 5). Gaia's euro figures
are for its Catalan user, so every Int$ value is converted at Spain's PPP
conversion factor for household final consumption, the "private
consumption" series de Groot et al. used: World Bank, World Development
Indicators, PA.NUS.PRVT.PP ("PPP conversion factor, households and NPISHs
final consumption expenditure, LCU per international $"), for the value's
own price year. No income adjustment and no inflation to a later price year
(the owner's decision for benefit transfers, Step 8d.5): only the currency
changes.

A case file records a converted number with ``converted_from``:

    {"currency": "Int$", "price_year": 2007, "amounts": {"value": 2861}}

on the object that carries it (a parameter, a pricing anchor:
``"anchor_value"``, a benchmark: ``"low"``, ``"high"``, ``"central"``).
Parsing checks that each field equals its amount × ``eur_per_int_dollar``
(``check_converted``), so the factor cannot diverge between files, and the
provenance carries the conversion (``conversion_note``).

No third-party dependencies.
"""

import math
from typing import Any, Dict, Mapping

CURRENCY = "Int$"
"""The only foreign currency converted here."""

PPP_SERIES = "PA.NUS.PRVT.PP"
PPP_COUNTRY = "Spain"

EUR_PER_INT_DOLLAR: Dict[int, float] = {
    2007: 0.808165,
    2020: 0.686508,
}
"""€ per international $ by price year: the World Bank's PPP conversion
factor for household final consumption (PA.NUS.PRVT.PP), Spain,
https://api.worldbank.org/v2/country/ESP/indicator/PA.NUS.PRVT.PP?date=<year>&format=json
(read 13 October 2026; the series last updated 8 October 2026)."""

SOURCE: str = (
    "World Bank, World Development Indicators, PPP conversion factor, households and NPISHs "
    f"final consumption expenditure (LCU per international $), {PPP_SERIES}, {PPP_COUNTRY} "
    "(api.worldbank.org, read 13 October 2026)"
)

_TOLERANCE = 1e-9


def eur_per_int_dollar(price_year: int) -> float:
    """€ per Int$ at Spain's PPP for household consumption, ``price_year``.

    Raises:
        ValueError: For a price year without a recorded factor.
    """
    if price_year not in EUR_PER_INT_DOLLAR:
        raise ValueError(
            f"no PPP factor recorded for price year {price_year!r} (recorded: "
            f"{', '.join(str(y) for y in sorted(EUR_PER_INT_DOLLAR))}; gaia.currency)"
        )
    return EUR_PER_INT_DOLLAR[price_year]


def int_dollars_to_eur(amount: float, price_year: int) -> float:
    """``amount`` Int$ of ``price_year`` in euros of the same year."""
    return amount * eur_per_int_dollar(price_year)


def check_converted(raw: Any, path: str, fields: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate a ``converted_from`` block against the converted ``fields``
    ({field: the number the file gives}); returns it parsed.

    Raises:
        ValueError: Naming the JSON path, for a malformed block, an unknown
            currency or price year, an amount for a field not given, or a
            field that is not its amount × the factor.
    """
    if not isinstance(raw, dict) or set(raw) != {"currency", "price_year", "amounts"}:
        raise ValueError(f"{path}: expected {{currency, price_year, amounts}}")
    if raw["currency"] != CURRENCY:
        raise ValueError(f"{path}.currency: only {CURRENCY!r} is converted, got {raw['currency']!r}")
    year = raw["price_year"]
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError(f"{path}.price_year: an integer year, got {year!r}")
    factor = eur_per_int_dollar(year)
    amounts = raw["amounts"]
    if not isinstance(amounts, dict) or not amounts:
        raise ValueError(f"{path}.amounts: {{field: amount in {CURRENCY}}}, at least one")
    out: Dict[str, float] = {}
    for name, amount in amounts.items():
        if name not in fields:
            raise ValueError(f"{path}.amounts.{name}: not a field of this object")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
            raise ValueError(f"{path}.amounts.{name}: a number, got {amount!r}")
        expected = amount * factor
        given = fields[name]
        if not (isinstance(given, (int, float)) and math.isclose(given, expected, rel_tol=_TOLERANCE)):
            raise ValueError(
                f"{path}.amounts.{name}: {CURRENCY}{amount:,g} ({year}) × {factor} €/{CURRENCY} = "
                f"{expected:.6f}, but the file gives {given!r} (gaia.currency: convert at the recorded PPP factor)"
            )
        out[name] = float(amount)
    return {"currency": CURRENCY, "price_year": year, "factor": factor, "amounts": out}


def conversion_note(converted: Dict[str, Any]) -> str:
    """Words for the provenance: the amounts, the factor and its source."""
    amounts = ", ".join(f"{name} {CURRENCY}{amount:,g}" for name, amount in converted["amounts"].items())
    return (
        f"Converted from {CURRENCY} ({converted['price_year']} prices: {amounts}) at "
        f"{converted['factor']} € per {CURRENCY}, the PPP factor for household consumption, "
        f"{PPP_COUNTRY} {converted['price_year']} ({PPP_SERIES}, World Bank); no income or price-year adjustment"
    )
