"""
Gaia v0.1 — Costa Brava Posidonia Meadow destruction case.

Marine ecosystem with 10 agents spanning the full web of biological and
physical dependencies: from the Posidonia meadow itself as foundation species,
through coralligenous reefs, fish nurseries, and apex megafauna, to the
coastal protection and tourism economy of the Costa Brava.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MONETARY SEMANTICS — ONE-OFF REVENUE vs YEARLY LOSSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

As in every Gaia case, agent values are YEARLY FLOWS and revenue is ONE-OFF:

    Private revenue:    ONE-TIME gain from coastal development, marina
                        construction, or trawling permits that destroy
                        Posidonia (modeled as €2,500/ha destroyed).

    Externality costs:  ANNUAL RECURRING losses — every year the meadow
                        is gone, the ecosystem services are absent.

The report shows the annual loss (€/yr) and its present value over the
200-year horizon (€ PV); the net social cost compares the one-off revenue
with that present value, never with the annual figure.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scientific context:
    Posidonia oceanica is one of the most biodiverse and carbon-rich ecosystems
    on Earth: it stores carbon in its sediment matte for millennia (valued by
    gaia.carbon through the carbon profile below). Growth rate: 1-6 cm/year
    horizontal — any significant destruction is irreversible on human timescales.

    34% of Mediterranean Posidonia has been lost in the last 50 years. The Costa
    Brava is already under pressure from tourism infrastructure, boat anchoring,
    and residual trawling. The 20% safe threshold is lower than the forest (25%)
    because recovery is orders of magnitude slower and the ecosystem is already
    stressed.

    The Medes Islands MPA is the proof-of-concept: protected since 1983, fish
    biomass is 80× higher inside the reserve than outside. The science works —
    protection produces measurable, quantifiable recovery.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    Summary only. The gaia.provenance.Param objects in this module are the
    authoritative provenance and what every output reports (Step 5). Where
    they differ from the table, the Params apply: an owner specification
    or 'Spec' entry with no cited source is 'low', not 'Medium'.

Agent values are yearly flows per hectare (decisions D1, D2). They restate
the user-specified maximum annual impact of each agent for the 5,000 ha
reference meadow per hectare and per unit of dependency weight:
    annual_value_per_ha = max_annual_impact / (dependency_weight × 5,000 ha)
so that weight × annual_value_per_ha × area_ha = max_annual_impact at 5,000 ha.

The Blue Carbon agent (weight 0.09, €500,000/yr) was carbon only and is
removed: carbon is valued by gaia.carbon alone (decision D3). The remaining
weights are renormalised by 1/0.91 (to sum to 1) and their per-ha values
scaled by 0.91, so weight × value — each agent's maximum annual impact — is
unchanged. The table lists the original weights and values.

    | Parameter                       | Max Impact | Weight | €/ha/yr    | Source       | Confidence |
    |---------------------------------|------------|--------|------------|--------------|------------|
    | total_units (= area, ha)        | –          | –      | –          | User spec    | Low        |
    | safe_threshold_ratio            | –          | –      | 0.20       | User spec    | Medium     |
    | unit_value (revenue/ha)         | –          | –      | 2,500 €    | User spec    | Low        |
    | Posidonia Meadow                | €800,000   | 0.10   | 1,600.0    | User spec    | Low        |
    | Coralligenous & Red Coral       | €600,000   | 0.10   | 1,200.0    | User spec    | Low        |
    | Epiphytes & Algae               | €250,000   | 0.07   | 714.2      | User spec    | Low        |
    | Marine Invertebrates            | €350,000   | 0.09   | 777.8      | User spec    | Low        |
    | Fish Populations                | €700,000   | 0.14   | 1,000.0    | User spec    | Low        |
    | Marine Megafauna                | €200,000   | 0.04   | 1,000.0    | User spec    | Low        |
    | Seabirds                        | €180,000   | 0.05   | 720.0      | User spec    | Low        |
    | Coastal Protection              | €900,000   | 0.13   | 1,384.6    | User spec    | Low        |
    | Water Quality                   | €650,000   | 0.11   | 1,181.8    | User spec    | Low        |
    | Human Communities               | €700,000   | 0.08   | 1,750.0    | User spec    | Low        |
    | logistic steepness              | –          | –      | 12.0       | Placeholder  | Low        |
    | dependency weight sum           | –          | 1.00   | –          | Verified ✓   | High       |

Total at full damage: sum(weight × annual_value_per_ha) = €1,066/ha/yr
    (€5,330,000/yr for 5,000 ha; €1,166/ha/yr before the €500,000/yr Blue
    Carbon agent was removed) [User spec, PLACEHOLDER].

For scale, global meta-analyses value seagrass / coastal systems far higher:
Costanza et al. (2014), Global Environmental Change 26:152-158, $28,916/ha/yr
for seagrass/algae beds; de Groot et al. (2012), Ecosystem Services 1:50-61,
Int$28,917/ha/yr for coastal systems (2007 price levels). A Posidonia-
specific valuation is pending (Step 8). Both totals include climate
regulation (Int$479/ha/yr for coastal systems in de Groot 2012), which
gaia.carbon values separately.

An earlier version of this docstring claimed the rates were set so that the
externality stays below revenue at the 20% threshold "at annual scale" (a
flow compared with a one-off amount, and contradicted by its own numbers);
rates are never tuned to produce an outcome.

Dependency weights sum: (0.10+0.10+0.07+0.09+0.14+0.04+0.05+0.13+0.11+0.08) / 0.91 = 1.00 ✓

Calibration regime: B, direct effects only (CalibrationRegime.DIRECT_ONLY;
PROJECT_DEFINITION.md, "Critical Modelling Assumption"):
    All 10 damage curves are the same placeholder logistic (steepness 12,
    inflection just past the 20% threshold), not fitted to field data on
    total impact (the agent impacts are a user specification), so Option A —
    curves that already embed the indirect pathways — cannot be claimed. The
    curves are read as each agent's direct dependency on the meadow, and the
    15 interaction edges add the indirect part; single-pass propagation makes
    the result a structural lower bound for chains longer than one hop. B is
    what an uncalibrated curve implies, not a claim of lab or
    first-principles calibration.

    In-degree cap (Step 3.8, S2): every agent's incoming strengths sum to at
    most 0.80 with the Posidonia keystone boost (Coastal Protection), within
    the cap of 1.0, so no edge was changed.

    Health at the safe threshold is below 0.8, so validation issues a
    CalibrationWarning. That is honest: the logistic alone puts ~17% direct
    damage at the threshold, trophic amplification multiplies it for
    consumers, and fixing it means calibrating the curves (Step 8), not
    tuning edges to silence the warning.

CLI usage:
    python -m gaia.cases.posidonia
    python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 1500
    python -m gaia.cases.posidonia --hectares 5000 --units 1500 --mode restore
    python -m gaia.cases.posidonia --units 1500 --format json
"""

import argparse
import sys
from typing import List, Optional, Union

from gaia.cli import (
    add_common_arguments,
    add_restoration_arguments,
    apply_carbon_price_view,
    cli_entry,
    drop_pricing_in_restore_mode,
    handle_deprecated_alias,
    output_result,
    warn_unused_restoration_args,
)
from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    AnchorPoint,
    CalibrationRegime,
    CarbonProfile,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    PricingConfig,
    ResilienceConfig,
    Resource,
    RestorationCost,
    RestorationResult,
    ScarcityFunction,
    SimulationResult,
    SubstrateProfile,
    SuccessionCurve,
)
from gaia.pricing import anchor_every_agent, scale_anchors
from gaia.provenance import (
    IDENTICAL_CURVES_NOTE,
    RAMSEY_SOURCE,
    HORIZON_NOTE,
    Confidence,
    Param,
    anchor_params,
    edge_params,
    keystone_params,
    named,
    restoration_params,
    unwrap,
    user_or_default,
    weight_params,
)
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

# Parameter provenance (Step 5): every value below is a gaia.provenance.Param
# (value, unit, source, confidence, note); the model receives param.value and
# every output lists the provenance (Ecosystem.provenance).

# v0.4: Posidonia succession curve
# Extremely slow — 1-6 cm/year horizontal growth, decades to re-establish.
# [PLACEHOLDER — pending calibration against Mediterranean seagrass studies]
_SUCCESSION_NOTE = "Pending calibration against Mediterranean seagrass studies."
_SUCCESSION_P = {
    "pioneer_end_year": Param(20.0, "years", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
    "intermediate_end_year": Param(50.0, "years", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
    "climax_approach_year": Param(120.0, "years", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
    "pioneer_service": Param(0.02, "fraction", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
    "intermediate_service": Param(0.25, "fraction", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
    "maturation_delay": Param(5.0, "years", None, Confidence.PLACEHOLDER, _SUCCESSION_NOTE),
}
_POSIDONIA_SUCCESSION = SuccessionCurve(**unwrap(_SUCCESSION_P))

# v0.4: Posidonia carbon profile (per hectare)
# Blue carbon — millennia of stored matte carbon.
# Absorption (S5: the one value used for Posidonia): the IPCC 2013 Wetlands
# Supplement Tier 1 seagrass carbon accumulation rate, 0.43 t C/ha/yr (based
# on Posidonia oceanica cores) × 44/12 = 1.58 t CO₂/ha/yr. Alternatives:
# the European Posidonia median, 0.31 t C/ha/yr = 1.13 t CO₂/ha/yr
# (Krause-Jensen et al. 2026, ETC-BE working paper, 43 cores); the former
# 5.9 t CO₂/ha/yr (1.6 t C/ha/yr) is near the older global seagrass mean of
# Duarte et al. (2013), 1.38 t C/ha/yr, which later syntheses revised down.
# [PLACEHOLDER — stocks pending calibration against IPCC Blue Carbon data]
_CARBON_NOTE = "Stocks pending calibration against IPCC Blue Carbon data."
_CARBON_P = {
    "stored_carbon_tonnes": Param(130.0, "tCO2/ha", None, Confidence.PLACEHOLDER, _CARBON_NOTE),
    "annual_absorption_tonnes": Param(
        0.43 * 44.0 / 12.0, "tCO2/ha/yr",
        "IPCC (2013) Wetlands Supplement, Tier 1 seagrass carbon accumulation "
        "rate 0.43 t C/ha/yr (Posidonia oceanica cores) × 44/12",
        Confidence.MEDIUM,
        "A global Tier 1 default, not a Costa Brava measurement. Alternative: "
        "European Posidonia median 0.31 t C/ha/yr (Krause-Jensen et al. 2026, "
        "ETC-BE working paper for the EEA), not verified.",
    ),
    "soil_carbon_tonnes": Param(2600.0, "tCO2/ha", None, Confidence.PLACEHOLDER, _CARBON_NOTE),
    "soil_release_fraction": Param(0.05, "fraction", None, Confidence.PLACEHOLDER, _CARBON_NOTE),
}
_POSIDONIA_CARBON = CarbonProfile(**unwrap(_CARBON_P))

# v0.4: Posidonia resilience configuration
# Widest warning zone — Posidonia is most fragile.
_POSIDONIA_RESILIENCE = ResilienceConfig(
    warning_zone_width=0.15,
    confidence_green=0.90,
    confidence_yellow=0.60,
    confidence_red=0.30,
    irreversibility_flag_ratio=0.40,
)

# v0.5: Posidonia substrate profile
# Marine matte — sediment stability constrains capacity. Water clarity (pristine
# light attenuation Kd ≈ 0.06 m⁻¹) is not modelled.
# Logistic capacity function: light-limited S-curve (Kd attenuation).
# [PLACEHOLDER — pending calibration against EMODnet and IFREMER data]
_MATTE_NOTE = "Pending calibration against EMODnet and IFREMER data."
_SUBSTRATE_P = {
    # pristine matte integrity
    "sediment_stability": Param(0.85, "0-1 scale", None, Confidence.PLACEHOLDER, _MATTE_NOTE),
    # matte degradation rate
    "erosion_rate_unprotected": Param(5.0, "arbitrary units/yr", None, Confidence.PLACEHOLDER, _MATTE_NOTE),
    # no erosion under intact meadow
    "erosion_rate_protected": Param(0.0, "arbitrary units/yr", None, Confidence.PLACEHOLDER, _MATTE_NOTE),
    # Posidonia matte accretion
    "formation_rate": Param(1.0, "mm/yr", None, Confidence.PLACEHOLDER, _MATTE_NOTE),
    # steeper nonlinearity for marine systems
    "erosion_alpha": Param(3.0, "exponent", None, Confidence.PLACEHOLDER, _MATTE_NOTE),
}
_POSIDONIA_SUBSTRATE = SubstrateProfile(
    substrate_type="marine_matte",
    capacity_function="logistic",
    confidence="low-medium",
    **unwrap(_SUBSTRATE_P),
)

# v0.6: Posidonia discount configuration
# Declining rate schedule: near-term 2.3%, mid-term 1.8%, long-term 1.4%.
# Carbon price: the DiscountConfig default, the social cost of carbon.
# Scarcity: 1%/yr, the Dutch government default relative price change for
# ecosystem services (Drupp et al. 2024, §1; see gaia.discount). It was 3%
# ("Posidonia declining 34%+ since 1960s"), above every rate of the
# schedule, so the PV grew without bound with the horizon (C3). The
# aggregate estimate of Drupp et al. (1.66%/yr) is above the long-term
# 1.4%, which the schedule reaches within the 200-year horizon.
_STEP_NOTE = "Step of the declining schedule; no cited source for the value or the year."
_DISCOUNT_P = {
    "rate_schedule[year 0]": Param(0.023, "1/yr", RAMSEY_SOURCE, Confidence.MEDIUM),
    "rate_schedule[year 31]": Param(0.018, "1/yr", None, Confidence.PLACEHOLDER, _STEP_NOTE),
    "rate_schedule[year 101]": Param(0.014, "1/yr", None, Confidence.PLACEHOLDER, _STEP_NOTE),
    "scarcity_rate": Param(
        0.01, "1/yr",
        "Drupp, Turk, Groom & Heckenhahn (2024), arXiv:2308.04400v3, §1: Dutch "
        "government default relative price change for ecosystem services",
        Confidence.MEDIUM,
        "Chosen below the paper's aggregate estimate (1.66%/yr), which exceeds "
        "the schedule's long-term 1.4% and would make the PV diverge.",
    ),
    # Longer horizon for marine ecosystems
    "horizon_years": Param(200, "years", None, Confidence.PLACEHOLDER, HORIZON_NOTE),
}
_POSIDONIA_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[
        (0, _DISCOUNT_P["rate_schedule[year 0]"].value),
        (31, _DISCOUNT_P["rate_schedule[year 31]"].value),
        (101, _DISCOUNT_P["rate_schedule[year 101]"].value),
    ],
    scarcity_rate=_DISCOUNT_P["scarcity_rate"].value,
    horizon_years=int(_DISCOUNT_P["horizon_years"].value),
)

# Restoration cost defaults (CLI and run_posidonia_restoration): specialist
# diving cost and annual monitoring per hectare [PLACEHOLDER]
_RESTORATION_NOTE = "No cost survey behind it."
_RESTORATION_P = {
    "planting_cost_per_unit": Param(50_000.0, "€/ha", None, Confidence.PLACEHOLDER, _RESTORATION_NOTE),
    "annual_maintenance_per_unit": Param(5_000.0, "€/ha/yr", None, Confidence.PLACEHOLDER, _RESTORATION_NOTE),
    "maintenance_years": Param(30, "years", None, Confidence.PLACEHOLDER, _RESTORATION_NOTE),
}

# ── Reference area ───────────────────────────────────────────────────────────
# Posidonia's unit is the hectare: area_ha always equals total_hectares.
POSIDONIA_AREA_HA: float = 5_000.0

# v0.7: Posidonia pricing configuration (EXPERIMENTAL, decision D4). Anchor
# values are €/yr for the POSIDONIA_AREA_HA reference meadow and are scaled
# with area_ha by the builder. The former Blue Carbon anchor (€80/t × 1.7 t
# CO₂/ha/yr × 1,000 ha) is gone: carbon is valued only by gaia.carbon
# (decision D3). Only the tourism and fishing anchors are documented; the
# builder anchors every other agent at its own direct annual service value,
# annual_value_per_ha × area_ha (gaia.pricing.anchor_every_agent) [PLACEHOLDER].
_POSIDONIA_PRICING = PricingConfig(
    anchors=[
        AnchorPoint(
            agent_name="Human Communities",
            anchor_value=500000.0,
            source="Costa Brava tourism revenue attributable to coastal water quality per ~5 km",
            # was "medium"; no cited source for the figure
            confidence="low",
            description="Tourism: attributable water quality value for ~5 km coastline",
        ),
        AnchorPoint(
            agent_name="Fish Populations",
            anchor_value=75000.0,
            source="Artisanal catch value: ~15 boats × €5,000/yr/boat",
            # was "medium"; no cited source for the boat count or the catch value
            confidence="low",
            description="Fishing: 15 artisanal boats × €5,000/yr",
        ),
    ],
    scarcity_functions={
        "Posidonia Meadow": ScarcityFunction("smooth", alpha=2.0, max_multiplier=50.0, description="Foundation species; millennium-scale recovery"),
        "Coralligenous & Red Coral": ScarcityFunction("smooth", alpha=1.5, max_multiplier=50.0, description="Biogenic habitat; century-scale recovery"),
        "Epiphytes & Algae": ScarcityFunction("smooth", alpha=0.8, max_multiplier=50.0),
        "Marine Invertebrates": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Fish Populations": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
        "Marine Megafauna": ScarcityFunction("smooth", alpha=0.5, max_multiplier=50.0),
        "Seabirds": ScarcityFunction("smooth", alpha=0.5, max_multiplier=50.0),
        "Coastal Protection": ScarcityFunction("threshold", threshold=0.3, max_multiplier=40.0, description="Beach nourishment cost replacement"),
        "Water Quality": ScarcityFunction("threshold", threshold=0.3, max_multiplier=30.0, description="Turbidity collapse threshold"),
        "Human Communities": ScarcityFunction("smooth", alpha=1.0, max_multiplier=50.0),
    },
    default_scarcity=ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0),
)

# Shared steepness for all logistic agents.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS_P = Param(
    12.0, "dimensionless", None, Confidence.PLACEHOLDER, IDENTICAL_CURVES_NOTE,
    name="damage.logistic_steepness",
)
_STEEPNESS: float = _STEEPNESS_P.value

# Sum of the user-specified weights without the removed Blue Carbon agent
# (1 − 0.09). Weights are divided by it and per-ha values multiplied by it,
# which keeps every agent's weight × value (its maximum annual impact).
_WEIGHT_RENORM: float = 0.91

_OWNER_SPEC = "owner specification (case docstring), no external source"
_AREA = Param(
    POSIDONIA_AREA_HA, "ha", _OWNER_SPEC, Confidence.LOW,
    "Plausible extent for a major Costa Brava stretch; needs GIS "
    "verification (EMODnet Posidonia maps).",
    name="resource.area_ha",
)
_UNIT_VALUE = Param(
    2_500.0, "€/ha", _OWNER_SPEC, Confidence.LOW,
    "Private gain per hectare destroyed (coastal development, marinas, "
    "trawling permits), one-off; not the value of Posidonia.",
    name="resource.unit_value",
)
_THRESHOLD = Param(
    0.20, "ratio", _OWNER_SPEC, Confidence.LOW,
    "Safe destruction threshold, lower than forest for slow recovery "
    "(stated rationale, no cited source); also the inflection of every "
    "damage curve.",
    name="resource.safe_threshold_ratio",
)

# Per-agent € / ha / yr at full damage: the owner-specified maximum annual
# impact for 5,000 ha restated per ha and per unit of weight, × 0.91 after
# the Blue Carbon agent was removed (module docstring).
_VALUE_SOURCE = (
    "owner specification of each agent's maximum annual impact for 5,000 ha "
    "(case docstring table), no external source"
)
_VALUE_NOTE = (
    "Global meta-analyses value seagrass and coastal systems ~25× higher "
    "(Costanza et al. 2014: $28,916/ha/yr; de Groot et al. 2012: "
    "Int$28,917/ha/yr, both incl. climate regulation); a Posidonia-specific "
    "valuation is pending (Step 8)."
)
_VALUES_P = {
    name: Param(value, "€/ha/yr", _VALUE_SOURCE, Confidence.LOW, _VALUE_NOTE,
                name=f"agent[{name}].annual_value_per_ha")
    for name, value in [
        ("Posidonia Meadow", 1_600.0 * _WEIGHT_RENORM),
        ("Coralligenous & Red Coral", 1_200.0 * _WEIGHT_RENORM),
        ("Epiphytes & Algae", 714.2 * _WEIGHT_RENORM),
        ("Marine Invertebrates", 777.8 * _WEIGHT_RENORM),
        ("Fish Populations", 1_000.0 * _WEIGHT_RENORM),
        ("Marine Megafauna", 1_000.0 * _WEIGHT_RENORM),
        ("Seabirds", 720.0 * _WEIGHT_RENORM),
        ("Coastal Protection", 1_384.6 * _WEIGHT_RENORM),
        ("Water Quality", 1_181.8 * _WEIGHT_RENORM),
        ("Human Communities", 1_750.0 * _WEIGHT_RENORM),
    ]
}

# Annual externality note appended to the report to flag the time-flow asymmetry.
_ANNUAL_NOTE: str = (
    "\n  ⚠  MARINE EXTERNALITY NOTE: the per-agent costs are ANNUAL (€/yr) — they\n"
    "     recur every year the damage persists. Posidonia recovers at 1-6 cm/year;\n"
    "     damage is effectively permanent on human timescales. The net social\n"
    "     cost compares the one-off revenue with the PV of these annual losses."
)


def build_posidonia_ecosystem(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = _THRESHOLD.value,
    revenue_per_hectare: float = _UNIT_VALUE.value,
    with_pricing: bool = False,
    area_ha: Optional[float] = None,
) -> Ecosystem:
    """
    Build the Costa Brava Posidonia Meadow ecosystem with 10 agents.

    The ecosystem spans the full marine dependency web: seagrass foundation,
    coralligenous reefs, epiphytes, invertebrates, fish, megafauna, seabirds,
    coastal protection, water quality, and human coastal communities. Carbon
    (the meadow's blue carbon) is valued by gaia.carbon, not by an agent.

    Args:
        total_hectares: Total hectares of Posidonia meadow. Default 5,000 ha —
            a plausible estimate for a major Costa Brava coastal stretch.
            [User spec, needs GIS verification from EMODnet Posidonia maps]
        safe_threshold_ratio: Fraction destructible before cascading decline.
            Default 0.20 — lower than forest (0.25) because Posidonia growth
            is 1-6 cm/year and recovery takes decades. Mediterranean already
            lost 34% in 50 years. [User spec, Medium confidence]
        revenue_per_hectare: Private gain per hectare destroyed. Represents the
            economic value extracted by activities that destroy Posidonia:
            coastal development, marina construction, trawling permits.
            NOT the value of Posidonia itself. [User spec, Low confidence]
        with_pricing: If True, attach the EXPERIMENTAL v0.7 endogenous pricing
            configuration (every agent anchored).
        area_ha: Must equal total_hectares if given — the unit is the
            hectare, so the area is not an independent parameter.

    Returns:
        A fully configured Ecosystem ready for simulation.

    Raises:
        ValueError: If area_ha differs from total_hectares.
    """
    if area_ha is None:
        area_ha = float(total_hectares)
    elif area_ha != total_hectares:
        raise ValueError(
            f"Posidonia's unit is the hectare: area_ha ({area_ha}) must equal "
            f"total_hectares ({total_hectares})"
        )
    resource = Resource(
        name="Costa Brava Posidonia Meadow",
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
        area_ha=area_ha,
        carbon_profile=_POSIDONIA_CARBON,
        resilience=_POSIDONIA_RESILIENCE,
        substrate=_POSIDONIA_SUBSTRATE,
        discount=_POSIDONIA_DISCOUNT,
    )

    t = safe_threshold_ratio  # shorthand

    agents = [
        # ── Foundation species ──────────────────────────────────────────────
        Agent(
            name="Posidonia Meadow",
            dependency_weight=0.10 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Posidonia Meadow"].value,
            description="Posidonia meadow integrity — self-reinforcing fragmentation and turbidity feedback loop",
            # v0.3: Producer, KEYSTONE foundation species
            trophic_level=0,
            is_keystone=True,
            keystone_threshold=0.3,
        ),
        # ── Biogenic habitat builders ───────────────────────────────────────
        Agent(
            name="Coralligenous & Red Coral",
            dependency_weight=0.10 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Coralligenous & Red Coral"].value,
            description="Coralligenous reefs and red coral — centuries-old biogenic habitat, irreplaceable on human timescales",
            # v0.3: Producer (biogenic)
            trophic_level=0,
        ),
        # ── Primary producers ───────────────────────────────────────────────
        Agent(
            name="Epiphytes & Algae",
            dependency_weight=0.07 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Epiphytes & Algae"].value,
            description="Epiphytic algae and plant community — primary productivity, oxygen production, food web base",
            # v0.3: Producer
            trophic_level=0,
        ),
        # ── Invertebrates ───────────────────────────────────────────────────
        Agent(
            name="Marine Invertebrates",
            dependency_weight=0.09 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Marine Invertebrates"].value,
            description="Sponges, urchins, octopus, lobsters, shellfish — filter feeders, grazers, urchin barren risk",
            # v0.3: Primary consumer
            trophic_level=1,
        ),
        # ── Fish ────────────────────────────────────────────────────────────
        Agent(
            name="Fish Populations",
            dependency_weight=0.14 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Fish Populations"].value,
            description="Fish nursery and feeding habitat — artisanal fisheries, grouper apex predator, Medes Islands model",
            # v0.3: Secondary consumer
            trophic_level=2,
        ),
        # ── Megafauna ───────────────────────────────────────────────────────
        Agent(
            name="Marine Megafauna",
            dependency_weight=0.04 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Marine Megafauna"].value,
            description="Dolphins, sea turtles, cetaceans — apex indicators, ecotourism, extreme K-strategy vulnerability",
            # v0.3: Tertiary consumer — apex marine predator
            trophic_level=3,
        ),
        # ── Seabirds ────────────────────────────────────────────────────────
        Agent(
            name="Seabirds",
            dependency_weight=0.05 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Seabirds"].value,
            description="Seabirds and coastal birds — fish-dependent breeders, Audouin's gull, migratory corridor",
            # v0.3: Secondary consumer (fish-dependent)
            trophic_level=2,
        ),
        # ── Physical ecosystem services ─────────────────────────────────────
        Agent(
            name="Coastal Protection",
            dependency_weight=0.13 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Coastal Protection"].value,
            description="Wave attenuation, beach erosion prevention, sediment stabilization — Costa Brava beach economy",
            # v0.3: Abiotic service
            trophic_level=-1,
        ),
        Agent(
            name="Water Quality",
            dependency_weight=0.11 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Water Quality"].value,
            description="Nutrient filtration, pathogen reduction, bathing water standards — direct tourism dependency",
            # v0.3: Abiotic service
            trophic_level=-1,
        ),
        # ── Human systems ───────────────────────────────────────────────────
        Agent(
            name="Human Communities",
            dependency_weight=0.08 / _WEIGHT_RENORM,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            annual_value_per_ha=_VALUES_P["Human Communities"].value,
            description="Dive/beach tourism economy, artisanal fishing, coastal property — perception threshold sensitive",
            # v0.3: External beneficiary
            trophic_level=-1,
        ),
    ]

    # v0.3: Full marine trophic web with 15 interaction edges
    interactions = [
        # Posidonia keystone cascade — foundation collapse cascades everywhere
        InteractionEdge("Posidonia Meadow", "Coralligenous & Red Coral", 0.30, "keystone",
            "Posidonia loss \u2192 sedimentation \u2192 coralligenous suffocation"),
        InteractionEdge("Posidonia Meadow", "Epiphytes & Algae", 0.35, "keystone",
            "Substrate loss collapses epiphytic community"),
        InteractionEdge("Posidonia Meadow", "Coastal Protection", 0.40, "keystone",
            "Meadow loss directly removes wave attenuation and beach protection"),
        InteractionEdge("Posidonia Meadow", "Water Quality", 0.30, "dependency",
            "Lost filtration capacity \u2192 turbidity and eutrophication"),

        # Coralligenous provides habitat for invertebrates and fish
        InteractionEdge("Coralligenous & Red Coral", "Marine Invertebrates", 0.25, "dependency",
            "Reef habitat loss displaces invertebrate communities"),
        InteractionEdge("Coralligenous & Red Coral", "Fish Populations", 0.20, "dependency",
            "Reef nursery loss reduces fish recruitment"),

        # Epiphytes are base of the food web
        InteractionEdge("Epiphytes & Algae", "Marine Invertebrates", 0.20, "trophic",
            "Primary productivity loss reduces grazer food supply"),

        # Trophic chain: invertebrates → fish → megafauna/seabirds
        InteractionEdge("Marine Invertebrates", "Fish Populations", 0.25, "trophic",
            "Invertebrate decline reduces fish food supply"),
        InteractionEdge("Fish Populations", "Marine Megafauna", 0.35, "trophic",
            "Fish decline starves apex marine predators"),
        InteractionEdge("Fish Populations", "Seabirds", 0.30, "trophic",
            "Fish decline causes breeding failure in seabird colonies"),

        # Invertebrate filtration supports water quality
        InteractionEdge("Marine Invertebrates", "Water Quality", 0.15, "dependency",
            "Filter feeder loss reduces water purification capacity"),

        # Water quality feeds back to coralligenous
        InteractionEdge("Water Quality", "Coralligenous & Red Coral", 0.15, "dependency",
            "Degraded water quality stresses sensitive coral formations"),

        # Human communities depend on multiple services
        InteractionEdge("Coastal Protection", "Human Communities", 0.25, "dependency",
            "Beach erosion destroys tourism infrastructure and economy"),
        InteractionEdge("Fish Populations", "Human Communities", 0.20, "dependency",
            "Fish decline collapses artisanal fishing economy"),
        InteractionEdge("Water Quality", "Human Communities", 0.15, "dependency",
            "Degraded water quality triggers beach closures and tourism loss"),
    ]

    pricing = (
        anchor_every_agent(
            scale_anchors(_POSIDONIA_PRICING, area_ha / POSIDONIA_AREA_HA), agents, area_ha
        )
        if with_pricing else None
    )
    provenance = [
        user_or_default(_AREA, area_ha, "--hectares / total_hectares"),
        user_or_default(_UNIT_VALUE, revenue_per_hectare, "--unit-value / revenue_per_hectare"),
        user_or_default(_THRESHOLD, safe_threshold_ratio, "--threshold"),
        *_VALUES_P.values(),
        *weight_params(
            agents, _OWNER_SPEC, Confidence.LOW,
            "Owner-specified weights renormalised by 1/0.91 after the Blue "
            "Carbon agent was removed.",
        ),
        _STEEPNESS_P,
        *keystone_params(agents, None, Confidence.PLACEHOLDER),
        *edge_params(interactions, None, Confidence.PLACEHOLDER),
        *named("carbon", _CARBON_P),
        *named("substrate", _SUBSTRATE_P),
        *named("discount", _DISCOUNT_P),
        *(anchor_params(pricing) if pricing is not None else []),
    ]
    return Ecosystem(
        name="Costa Brava Posidonia Meadow",
        resource=resource,
        agents=agents,
        interactions=interactions,
        calibration_regime=CalibrationRegime.DIRECT_ONLY,
        pricing=pricing,
        provenance=provenance,
    )


def run_posidonia(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_destroyed: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
) -> str:
    """
    Run the Costa Brava Posidonia destruction simulation and return the report.

    Default hectares_destroyed=2,000 — 40% of the meadow, well past the 20%
    safe threshold, representative of a major coastal development project.

    NOTE: per-agent externality costs in the report are ANNUAL (€/yr); the
    net social cost compares the one-off revenue with their present value.

    Args:
        total_hectares: Total hectares of Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_destroyed: Hectares of meadow destroyed (extracted).
        revenue_per_hectare: One-time private revenue per hectare destroyed.

    Returns:
        Formatted text report string with marine economics note appended.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    result = run_extraction(ecosystem, hectares_destroyed)
    return format_report(result) + _ANNUAL_NOTE


def run_posidonia_restoration(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_to_restore: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
    planting_cost_per_hectare: float = 50_000.0,
    annual_maintenance_per_hectare: float = 5_000.0,
    maintenance_years: int = 30,
    time_horizon_years: int = 0,
    units_lost: Optional[int] = None,
) -> str:
    """
    Run the Costa Brava Posidonia Meadow restoration simulation and return the report.

    v0.4: When time_horizon_years > 0, produces maturation timeline using
    the Posidonia succession curve (slowest of all ecosystems).

    Args:
        total_hectares: Total carrying capacity of the Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_to_restore: Hectares of meadow to actively restore.
        revenue_per_hectare: One-time private revenue per hectare.
        planting_cost_per_hectare: Specialist diving cost per hectare.
        annual_maintenance_per_hectare: Annual monitoring cost per hectare.
        maintenance_years: Years of active maintenance required.
        time_horizon_years: Years to simulate maturation (0 = skip, v0.4).
        units_lost: Units missing before restoring (default: the units
            restored, i.e. restore what was cut).

    Returns:
        Formatted text restoration report string with marine economics note.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    cost = RestorationCost(
        planting_cost_per_unit=planting_cost_per_hectare,
        annual_maintenance_per_unit=annual_maintenance_per_hectare,
        maintenance_years=maintenance_years,
    )
    ecosystem.provenance.extend(restoration_params(
        cost, _RESTORATION_P, _SUCCESSION_P if time_horizon_years > 0 else None,
    ))
    recovery_fns = [
        logistic_recovery(threshold=safe_threshold_ratio)
        for _ in ecosystem.agents
    ]
    result = run_restoration(
        ecosystem, hectares_to_restore, cost, recovery_fns,
        succession_curve=_POSIDONIA_SUCCESSION if time_horizon_years > 0 else None,
        time_horizon_years=time_horizon_years,
        units_lost=units_lost,
    )
    return format_restoration_report(result) + _ANNUAL_NOTE


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.9.0 — Costa Brava Posidonia Meadow externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (20% = 1,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 1000\n\n"
            "  # Extraction — past threshold (40% = 2,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --units 2000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --units 2000 --mode restore\n\n"
            "  # JSON output:\n"
            "  python -m gaia.cases.posidonia --units 2000 --format json\n"
        ),
    )
    parser.add_argument(
        "--hectares",
        type=int,
        default=5_000,
        metavar="N",
        help="Total hectares of Posidonia meadow (default: 5000)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=_THRESHOLD.value,
        metavar="RATIO",
        help="Safe destruction threshold ratio, 0.0 < threshold < 1.0 (default: 0.20)",
    )
    parser.add_argument(
        "--units",
        type=int,
        default=2_000,
        metavar="N",
        help="Hectares to destroy or restore (default: 2000)",
    )
    # Deprecated alias for --units
    parser.add_argument(
        "--destroy", type=int, default=None, metavar="N",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--unit-value",
        type=float,
        default=_UNIT_VALUE.value,
        metavar="EUROS",
        help="One-time revenue per hectare destroyed in euros (default: 2500.0)",
    )
    # Deprecated alias for --unit-value
    parser.add_argument(
        "--revenue", type=float, default=None, metavar="EUROS",
        help=argparse.SUPPRESS,
    )
    add_common_arguments(parser)
    add_restoration_arguments(
        parser,
        planting_cost_default=_RESTORATION_P["planting_cost_per_unit"].value,
        maintenance_cost_default=_RESTORATION_P["annual_maintenance_per_unit"].value,
        maintenance_years_default=int(_RESTORATION_P["maintenance_years"].value),
    )
    args = parser.parse_args(argv)
    # Resolve deprecated aliases
    handle_deprecated_alias(args, "destroy", "units", "--destroy", "--units")
    handle_deprecated_alias(args, "revenue", "unit_value", "--revenue", "--unit-value")
    return args


# Posidonia marine annual note for JSON output
_POSIDONIA_NOTES = [
    "Marine externality costs are ANNUAL (€/yr) — they recur every year the "
    "damage persists. Posidonia recovers at 1-6 cm/year; damage is effectively "
    "permanent on human timescales. The net social cost compares the one-off "
    "revenue with the present value of these annual losses."
]


@cli_entry
def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    warn_unused_restoration_args(args)
    drop_pricing_in_restore_mode(args)
    try:
        ecosystem = build_posidonia_ecosystem(
            total_hectares=args.hectares,
            safe_threshold_ratio=args.threshold,
            revenue_per_hectare=args.unit_value,
            with_pricing=args.with_pricing,
            area_ha=args.area_ha,
        )
        apply_carbon_price_view(ecosystem, args.carbon_price)
        result: Union[SimulationResult, RestorationResult]
        if args.mode == "restore":
            cost = RestorationCost(
                planting_cost_per_unit=args.planting_cost,
                annual_maintenance_per_unit=args.maintenance_cost,
                maintenance_years=args.maintenance_years,
            )
            ecosystem.provenance.extend(restoration_params(
                cost, _RESTORATION_P,
                _SUCCESSION_P if args.time_horizon > 0 else None,
            ))
            recovery_fns = [
                logistic_recovery(threshold=args.threshold)
                for _ in ecosystem.agents
            ]
            restored = run_restoration(
                ecosystem, args.units, cost, recovery_fns,
                units_lost=args.units_lost,
                succession_curve=(
                    _POSIDONIA_SUCCESSION if args.time_horizon > 0 else None
                ),
                time_horizon_years=args.time_horizon,
            )
            text_report = format_restoration_report(restored) + _ANNUAL_NOTE
            result = restored
        else:
            extracted = run_extraction(ecosystem, args.units)
            text_report = format_report(extracted) + _ANNUAL_NOTE
            result = extracted
        output_result(text_report, result, args, notes=_POSIDONIA_NOTES)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
