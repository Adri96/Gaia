"""
Gaia — parameter provenance and calibration status (Step 5, findings D2/S3).

Implements the project's own rule: every number traceable to a source, and
placeholders flagged in the output. A case file records each economically or
ecologically meaningful parameter as {value, unit, source, confidence, note}
(gaia.ecosystem_io), which becomes a ``Param``; the model receives
``param.value`` — a plain float — so the engine never sees a ``Param``.
The list is attached to ``Ecosystem.provenance``; ``calibration_status`` adds the model-wide
parameters (trophic and keystone constants, carbon price, default discount)
and every result carries the outcome in its ``calibration`` field, which the
text report and the JSON output both print.

Confidence levels (``Confidence``):
    high         — a measurement or published value for this site or system,
                   with a citation checked against the source.
    medium       — a published value for a comparable system with a checked
                   (or well-established) citation, used without site
                   adaptation.
    low          — an order of magnitude from the literature with a
                   citation that is partial, from memory or unchecked, or an
                   expert/owner judgement with a stated rationale.
    placeholder  — no source: a plausible or mechanical choice (marked
                   [PLACEHOLDER] in the case files).
    user-supplied — a value given on the command line or through the API;
                   Gaia cannot vouch for it and does not count it as
                   placeholder or low.

No third-party dependencies.
"""

import dataclasses
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Confidence(str, Enum):
    """How far a parameter value can be trusted (see the module docstring).

    A ``str`` subclass serialized as its value.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PLACEHOLDER = "placeholder"
    USER = "user-supplied"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Param:
    """A model parameter with its provenance.

    Attributes:
        value: The number the model uses.
        unit: Its unit, e.g. "€/ha/yr", "tCO2/tree", "1/yr", "ratio".
        source: Citation or origin; None when there is none (placeholder).
        confidence: A ``Confidence`` (a plain string is converted).
        note: What a reader must know before relying on the value.
        name: Dotted name of the field it sets, e.g.
            "carbon.stored_carbon_tonnes" (``named`` fills it in).
    """

    value: float
    unit: str
    source: Optional[str]
    confidence: Confidence
    note: str = ""
    name: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError(f"Param value must be a number, got {self.value!r}")
        if not math.isfinite(self.value):
            raise ValueError(f"Param {self.name!r}: value must be finite, got {self.value}")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "confidence", Confidence(self.confidence))
        if self.confidence in (Confidence.HIGH, Confidence.MEDIUM) and not self.source:
            raise ValueError(
                f"Param {self.name!r}: a {self.confidence.value}-confidence "
                f"value needs a source"
            )


def named(prefix: str, params: Dict[str, Param]) -> List[Param]:
    """Name each Param ``prefix.key`` (the key is the field it sets)."""
    return [dataclasses.replace(p, name=f"{prefix}.{key}") for key, p in params.items()]


def unwrap(params: Dict[str, Param]) -> Dict[str, float]:
    """``{field: value}`` — the plain floats the model is built from."""
    return {key: p.value for key, p in params.items()}


def user_or_default(default: Param, value: float, flag: str) -> Param:
    """``default`` if ``value`` equals it, else a user-supplied Param.

    Args:
        default: The case's documented default (with its name).
        value: The value actually used.
        flag: How a user sets it, e.g. "--unit-value / tree_value".
    """
    if float(value) == default.value:
        return default
    return Param(
        value=value,
        unit=default.unit,
        source=f"user-supplied ({flag})",
        confidence=Confidence.USER,
        note=(
            f"replaces the case default {default.value:g} {default.unit} "
            f"({default.confidence.value})"
        ),
        name=default.name,
    )


def anchor_params(pricing) -> List[Param]:
    """One Param per pricing anchor of an (EXPERIMENTAL) PricingConfig.

    Anchors whose source starts with "PLACEHOLDER" (gaia.pricing.
    anchor_every_agent) are placeholders; the others keep the confidence
    stated on the AnchorPoint.
    """
    out: List[Param] = []
    for a in pricing.anchors:
        placeholder = a.source.startswith("PLACEHOLDER")
        out.append(Param(
            a.anchor_value, "€/yr",
            None if placeholder else a.source,
            Confidence.PLACEHOLDER if placeholder else Confidence(a.confidence),
            "EXPERIMENTAL pricing (quarantined). " + (
                "No documented anchor: the agent's own direct annual value."
                if placeholder else a.description
            ),
            name=f"pricing.anchor[{a.agent_name}]",
        ))
    defaults = pricing.default_scarcity
    out.append(Param(
        defaults.max_multiplier, "×", None, Confidence.PLACEHOLDER,
        "EXPERIMENTAL pricing. Scarcity functions (α, threshold, maximum "
        "multiplier per agent) are hand-set; this is the default maximum.",
        name="pricing.default_scarcity.max_multiplier",
    ))
    return out


# ── Model-wide parameters ─────────────────────────────────────────────────────


def model_parameters(ecosystem, discount) -> List[Param]:
    """Parameters of the model itself that this run uses.

    Trophic amplification (if an agent sits at trophic level >= 1), the
    keystone multiplier (if a keystone agent has outgoing edges), the carbon
    price and its growth (if the resource has a carbon profile), and the
    default discount profile (if the resource has none).
    """
    from gaia import carbon, constants

    out: List[Param] = []
    if any(a.trophic_level >= 1 for a in ecosystem.agents):
        out.append(Param(
            constants.TROPHIC_TRANSFER_EFFICIENCY, "ratio", None, Confidence.PLACEHOLDER,
            "Midpoint of the 5-20% energy transfer efficiency between trophic "
            "levels (the textbook range following Lindeman 1942; from memory, "
            "verify). The midpoint is a choice, not a measurement.",
            name="model.trophic_transfer_efficiency",
        ))
        out.append(Param(
            constants.TROPHIC_AMPLIFICATION_EXPONENT, "exponent", None,
            Confidence.PLACEHOLDER,
            "No source: damps the pyramid ratio to 1.6-4.1× amplification for "
            "trophic levels 1-3.",
            name="model.trophic_amplification_exponent",
        ))
    keystones = {a.name for a in ecosystem.agents if a.is_keystone}
    if any(e.source in keystones for e in ecosystem.interactions):
        out.append(Param(
            constants.KEYSTONE_EDGE_MULTIPLIER, "×", None, Confidence.PLACEHOLDER,
            "No source: outgoing edge strengths of a collapsed keystone agent "
            "are multiplied by this factor.",
            name="model.keystone_edge_multiplier",
        ))
    if ecosystem.resource.carbon_profile is not None:
        out.extend(_carbon_price_params(discount, carbon))
    if ecosystem.resource.discount is None:
        out.extend(_default_discount_params())
    return out


def _carbon_price_params(discount, carbon) -> List[Param]:
    price = discount.carbon_price_current
    if price == carbon.SOCIAL_COST_OF_CARBON_EUR:
        price_param = Param(
            price, "€/tCO2",
            "US EPA (2023), Report on the Social Cost of Greenhouse Gases, "
            "Table ES.1: $190/tCO2 (2020 emissions, 2020 USD, 2% near-term "
            "rate), at the ECB 2020 average rate of 1.1422 USD/EUR",
            Confidence.MEDIUM,
            "Social cost of carbon. The 2020-emissions value is used as the "
            "year-0 price: EPA's own path gives about $215 for 2026 "
            "emissions, so year-0 carbon damage is understated by about 13%. "
            "2020 euros, no inflation adjustment.",
            name="carbon_price.year0",
        )
    elif price == carbon.ETS_CARBON_PRICE_EUR:
        price_param = Param(
            price, "€/tCO2", None, Confidence.LOW,
            "Market/ETS view (--carbon-price ets): an EU ETS allowance price "
            "of the order of 2023-2024, not tied to a cited series. A private "
            "price that understates the damage; not the default.",
            name="carbon_price.year0",
        )
    else:
        price_param = Param(
            price, "€/tCO2", "user-supplied (DiscountConfig.carbon_price_current)",
            Confidence.USER, name="carbon_price.year0",
        )
    growth = discount.carbon_price_growth
    if growth == carbon.SCC_GROWTH_RATE:
        growth_param = Param(
            growth, "1/yr",
            "US EPA (2023) Table ES.1, 2% column: $190 (2020) to $410 (2080)",
            Confidence.MEDIUM,
            "60-year average of a decelerating path (1.6%/yr in 2020-2050, "
            "1.2%/yr in 2030-2080).",
            name="carbon_price.growth",
        )
    else:
        growth_param = Param(
            growth, "1/yr", "user-supplied (DiscountConfig.carbon_price_growth)",
            Confidence.USER, name="carbon_price.growth",
        )
    return [price_param, growth_param]


def _default_discount_params() -> List[Param]:
    """DEFAULT_DISCOUNT (= DISCOUNT_CENTRAL), used when the resource has none."""
    from gaia.discount import DEFAULT_DISCOUNT

    return [
        Param(
            DEFAULT_DISCOUNT.rate_at_year(1), "1/yr", RAMSEY_SOURCE, Confidence.MEDIUM,
            "DEFAULT_DISCOUNT (DISCOUNT_CENTRAL): the resource has no "
            "DiscountConfig.",
            name="discount.rate_schedule",
        ),
        SCARCITY_2PCT_PARAM,
        Param(
            DEFAULT_DISCOUNT.horizon_years, "years", None, Confidence.PLACEHOLDER,
            HORIZON_NOTE, name="discount.horizon_years",
        ),
    ]


# DEFAULT_DISCOUNT's scarcity rate (the forest case file states the same value).
SCARCITY_2PCT_PARAM = Param(
    0.02, "1/yr", None, Confidence.LOW,
    "2% relative price change of ecosystem services. Above the estimates of "
    "Drupp et al. (2024), 1.28%/yr for forests (CI 0.85-1.70) and 1.66%/yr "
    "aggregate (CI 1.40-1.92); kept until Step 8. Below the discount rate, so "
    "the PV converges.",
    name="discount.scarcity_rate",
)

HORIZON_NOTE: str = (
    "A modelling choice; the outputs also report the PV at 50, 100 and 200 "
    "years (horizon sensitivity)."
)

RAMSEY_SOURCE: str = (
    "Ramsey r = δ + ηg with δ 0.5%, η 1.35, g 1.3% (Drupp et al. 2018 expert "
    "survey, as cited in gaia.discount)"
)


# ── Calibration status ────────────────────────────────────────────────────────

_REGIME_MEANING: Dict[str, str] = {
    "A": (
        "A (empirical): damage curves fitted to field data on total impact; "
        "only keystone edges are added"
    ),
    "B": (
        "B (direct effects only): damage curves are read as each agent's "
        "direct dependency, interaction edges add the indirect part"
    ),
}


@dataclass(frozen=True)
class CalibrationStatus:
    """How far a run's parameters are sourced (Step 5).

    Attributes:
        params: Every recorded parameter: the model-wide ones, then the
            ecosystem's (Ecosystem.provenance), in that order.
        calibration_regime: "A", "B" or None (Ecosystem.calibration_regime).
        ecosystem_documented: False when the ecosystem records no
            provenance (e.g. one built in code): its own parameters are then
            not counted at all.
    """

    params: tuple  # Tuple[Param, ...]
    calibration_regime: Optional[str]
    ecosystem_documented: bool

    def count(self, confidence: Confidence) -> int:
        """Number of parameters at ``confidence``."""
        return sum(1 for p in self.params if p.confidence == confidence)

    @property
    def n_params(self) -> int:
        return len(self.params)

    @property
    def n_placeholder(self) -> int:
        return self.count(Confidence.PLACEHOLDER)

    @property
    def n_low(self) -> int:
        return self.count(Confidence.LOW)

    @property
    def flagged(self) -> List[Param]:
        """Placeholders first, then low-confidence parameters."""
        return (
            [p for p in self.params if p.confidence == Confidence.PLACEHOLDER]
            + [p for p in self.params if p.confidence == Confidence.LOW]
        )

    @property
    def regime_meaning(self) -> Optional[str]:
        if self.calibration_regime is None:
            return None
        return _REGIME_MEANING.get(self.calibration_regime)

    @property
    def status(self) -> str:
        """ "illustrative", unless every recorded parameter is sourced at
        medium confidence or better ("sourced, not externally reviewed")."""
        if not self.ecosystem_documented or self.n_placeholder or self.n_low:
            return "illustrative"
        return "sourced, not externally reviewed"

    @property
    def headline(self) -> str:
        """One sentence for the top of every output."""
        if not self.ecosystem_documented:
            return (
                "ILLUSTRATIVE: this ecosystem records no parameter provenance, "
                "so none of its values are sourced; results are not "
                "real-world estimates."
            )
        n_flagged = self.n_placeholder + self.n_low
        text = (
            f"ILLUSTRATIVE: {n_flagged} of {self.n_params} recorded parameters "
            f"are placeholders ({self.n_placeholder}) or low-confidence "
            f"({self.n_low})"
        )
        n_user = self.count(Confidence.USER)
        if n_user:
            text += f"; {n_user} user-supplied, not assessed"
        return text + ". Results are not real-world estimates."


def calibration_status(ecosystem, discount) -> CalibrationStatus:
    """The calibration status of a run on ``ecosystem`` with ``discount``.

    Args:
        ecosystem: The simulated Ecosystem (its ``provenance`` list).
        discount: The DiscountConfig the run used (resolved, so the carbon
            price view and the default profile are reflected).
    """
    regime = ecosystem.calibration_regime
    own = list(getattr(ecosystem, "provenance", None) or [])
    return CalibrationStatus(
        params=tuple(model_parameters(ecosystem, discount) + own),
        calibration_regime=str(regime) if regime is not None else None,
        ecosystem_documented=bool(own),
    )


_BRACKETS = re.compile(r"\[[^\]]*\]")


def group_flagged(status: CalibrationStatus) -> List[Tuple[str, List[Param]]]:
    """Flagged parameters grouped for a compact listing.

    Parameters with the same confidence, source and note form one group
    when they share a name pattern (the name with any ``[...]`` collapsed,
    e.g. every edge strength) or, for names without brackets, the same
    prefix before the first dot (e.g. every "carbon." field). Groups keep
    first-appearance order. Returns (label, params) pairs; the label is the
    pattern or the prefix.
    """
    groups: Dict[tuple, List[Param]] = {}
    labels: Dict[tuple, str] = {}
    for p in status.flagged:
        pattern = _BRACKETS.sub("[…]", p.name)
        label = pattern if pattern != p.name else p.name.split(".")[0]
        key = (p.confidence, p.source, p.note, label)
        groups.setdefault(key, []).append(p)
        labels[key] = label
    return [(labels[k], v) for k, v in groups.items()]


# ── Shared case helpers ───────────────────────────────────────────────────────

def area_param(area_ha: float, given: bool, density: Param, unit: str) -> Param:
    """The resource area: user-supplied, or units / the reference density.

    Args:
        area_ha: The area used (ha).
        given: True when the caller set the area explicitly.
        density: The case's reference density Param (units/ha).
        unit: The unit counted, e.g. "trees".
    """
    if given:
        return Param(
            area_ha, "ha", "user-supplied (--area-ha / area_ha)", Confidence.USER,
            name="resource.area_ha",
        )
    note = f"Units / reference density of {density.value:g} {unit}/ha."
    if density.note:
        note += " " + density.note
    return Param(
        area_ha, "ha", density.source, density.confidence, note,
        name="resource.area_ha",
    )
