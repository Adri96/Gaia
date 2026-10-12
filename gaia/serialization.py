"""
Gaia v0.8.1 — JSON serialization for simulation results.

Converts SimulationResult and RestorationResult dataclasses to
JSON-serializable dicts. Omits non-serializable fields (callables,
config objects) and includes only output data.

Produces a stable, documented JSON schema with version field.
Pure stdlib — no numpy or third-party dependencies.

Every monetary key carries its unit as a suffix (decision D1):
    *_eur_yr   — a yearly flow (€ per year)
    *_eur_per_ha_yr — a yearly flow per hectare (€/ha/yr)
    *_eur_pv   — a present value at year 0 (€, discounted stock)
    *_eur      — an undiscounted one-off amount (€) or an undiscounted sum
    *_eur_per_t — a price per tonne of CO₂
Ratios carry no currency suffix (e.g. ``restoration_cost_ratio``, ``roi``).
A parameter in the ``calibration`` block states its unit in a sibling
``"unit"`` string next to its ``"value"``.

Every output starts with a ``calibration`` block (Step 5): the headline
statement, the calibration regime, counts per confidence level and every
recorded parameter with value, unit, source, confidence and note.

The output is strict JSON (``allow_nan=False``): a non-finite number (±inf,
NaN) is written as ``null`` and a sibling key ``<key>_null_reason`` says why,
e.g. ``"substrate_recovery_years": null`` with
``"substrate_recovery_years_null_reason": "never: ..."`` when the substrate
has no formation rate. A non-finite number inside a list becomes ``null``
with no reason key.
"""

import json
import math
from typing import Any, Dict, List, Optional

from gaia import __version__
from gaia.provenance import Confidence
from gaia.models import (
    CarbonBreakeven,
    ExtractionNPV,
    DestroyThenRestorePenalty,
    MaturationStep,
    PriceResult,
    RestorationNPV,
    RestorationResult,
    RestorationStep,
    SimulationResult,
    SimulationStep,
)

GAIA_VERSION = __version__


# ── Internal helpers ──────────────────────────────────────────────────────────


def _by_horizon(name: str, by_horizon: dict) -> Dict[str, Any]:
    """Horizon sensitivity as ``{name}_h{H}_eur_pv`` keys (None → null)."""
    return {
        f"{name}_h{horizon}_eur_pv": (
            round(value, 2) if value is not None else None
        )
        for horizon, value in by_horizon.items()
    }


def _agent_metadata(
    agents: list, area_ha: float, trophic_amplification: Optional[list] = None,
) -> List[Dict[str, Any]]:
    """Serialize agent metadata (no callables).

    ``trophic_amplification`` (SimulationResult.agent_trophic_amplification)
    adds each agent's amplification factor.
    """
    out: List[Dict[str, Any]] = []
    for i, a in enumerate(agents):
        d: Dict[str, Any] = {
            "name": a.name,
            "dependency_weight": a.dependency_weight,
            "annual_value_eur_per_ha_yr": a.annual_value_per_ha,
            "annual_value_eur_yr": a.annual_value(area_ha),
            "description": a.description,
            "trophic_level": a.trophic_level,
            "is_keystone": a.is_keystone,
            "keystone_threshold": a.keystone_threshold if a.is_keystone else None,
        }
        if trophic_amplification:
            d["trophic_amplification"] = round(trophic_amplification[i], 6)
        out.append(d)
    return out


def _by_agent(agents: list, values: list, digits: int = 2) -> Dict[str, float]:
    """{agent name: rounded value} for a per-agent list."""
    return {a.name: round(v, digits) for a, v in zip(agents, values)}


CONFIDENCE_BAND_METHOD: str = (
    "HEURISTIC, not a statistical interval: annual externality x "
    "(1 +/- (1 - model confidence)), the confidence set by the resilience "
    "zone (gaia.resilience.compute_confidence_band). A Monte Carlo interval "
    "is pending (Step 8)."
)


def _confidence_band(result: SimulationResult) -> Optional[Dict[str, Any]]:
    """The heuristic band on the annual externality (None when not defined)."""
    if result.annual_externality_band is None:
        return None
    low, high = result.annual_externality_band
    return {
        "low_eur_yr": round(low, 2),
        "high_eur_yr": round(high, 2),
        "model_confidence": round(result.final_model_confidence, 4),
        "heuristic": True,
        "method": CONFIDENCE_BAND_METHOD,
    }


def _discount_to_dict(discount, is_default: bool) -> Dict[str, Any]:
    """The DiscountConfig the present values used, as configured."""
    schedule = discount.rate_schedule
    return {
        "rate_schedule": (
            float(schedule) if isinstance(schedule, (int, float))
            else [[year, rate] for year, rate in schedule]
        ),
        "delta": discount.delta,
        "eta": discount.eta,
        "g": discount.g,
        "scarcity_rate": discount.scarcity_rate,
        "carbon_price_eur_per_t": round(discount.carbon_price_current, 2),
        "carbon_price_growth": discount.carbon_price_growth,
        "horizon_years": discount.horizon_years,
        "is_default": is_default,
    }


def _extraction_substrate(result: SimulationResult) -> Optional[Dict[str, Any]]:
    """End-of-extraction substrate state (None without a substrate profile)."""
    if result.substrate_recovery_years is None or not result.steps:
        return None
    final = result.steps[-1]
    return {
        "k_fraction": round(final.k_fraction, 6),
        "effective_k": final.effective_k,
        "capacity_lost_units": result.ecosystem.resource.total_units - final.effective_k,
        "substrate_recovery_years": round(result.substrate_recovery_years, 2),
    }


def _resource_metadata(resource) -> Dict[str, Any]:
    """Serialize resource metadata (no substrate/discount internals)."""
    d: Dict[str, Any] = {
        "name": resource.name,
        "total_units": resource.total_units,
        "safe_threshold_ratio": resource.safe_threshold_ratio,
        "safe_threshold_units": resource.safe_threshold_units,
        "unit_value_eur": resource.unit_value,
        "area_ha": resource.area_ha,
        "units_per_ha": resource.units_per_ha,
        "has_carbon_profile": resource.carbon_profile is not None,
        "has_substrate": resource.substrate is not None,
        "has_discount": resource.discount is not None,
    }
    if resource.substrate is not None:
        d["substrate_type"] = resource.substrate.substrate_type
    if resource.discount is not None:
        d["discount_rate"] = resource.discount.rate_at_year(0)
        d["discount_horizon_years"] = resource.discount.horizon_years
    if resource.carbon_profile is not None:
        from gaia.carbon import carbon_price_label
        from gaia.discount import DEFAULT_DISCOUNT
        cp = resource.carbon_profile
        discount = resource.discount if resource.discount is not None else DEFAULT_DISCOUNT
        d["carbon_stored_per_unit"] = cp.stored_carbon_tonnes
        d["carbon_absorption_per_unit_yr"] = cp.annual_absorption_tonnes
        d["carbon_price_eur_per_t"] = round(discount.carbon_price_current, 2)
        d["carbon_price_growth"] = discount.carbon_price_growth
        d["carbon_price_basis"] = carbon_price_label(discount)
    return d


def _calibration_to_dict(calibration) -> Dict[str, Any]:
    """The "calibration" block (Step 5): what a reader must know first."""
    if calibration is None:
        return {
            "status": "illustrative",
            "statement": (
                "ILLUSTRATIVE: no calibration status recorded. Results are "
                "not real-world estimates."
            ),
        }
    return {
        "status": calibration.status,
        "statement": calibration.headline,
        "calibration_regime": calibration.calibration_regime,
        "calibration_regime_meaning": calibration.regime_meaning,
        "ecosystem_provenance_recorded": calibration.ecosystem_documented,
        "n_params": calibration.n_params,
        "n_placeholder": calibration.n_placeholder,
        "n_low": calibration.n_low,
        "n_medium": calibration.count(Confidence.MEDIUM),
        "n_high": calibration.count(Confidence.HIGH),
        "n_user_supplied": calibration.count(Confidence.USER),
        "parameters": [
            {
                "name": p.name,
                "value": p.value,
                "unit": p.unit,
                "source": p.source,
                "confidence": p.confidence.value,
                "note": p.note,
            }
            for p in calibration.params
        ],
    }


def _calibration_regime(ecosystem) -> Optional[str]:
    """Ecosystem.calibration_regime as "A" / "B" (None when undeclared)."""
    regime = ecosystem.calibration_regime
    return regime.value if regime is not None else None


def _interaction_metadata(interactions: list) -> List[Dict[str, Any]]:
    """Serialize interaction edges."""
    return [
        {
            "source": e.source,
            "target": e.target,
            "strength": e.strength,
            "interaction_type": e.interaction_type,
            "description": e.description,
        }
        for e in interactions
    ]


def _simulation_step_to_dict(step: SimulationStep, agents: list) -> Dict[str, Any]:
    """Convert one SimulationStep to a dict."""
    n = len(agents)
    d: Dict[str, Any] = {
        "step": step.step,
        "units_extracted": step.units_extracted,
        "depletion_ratio": round(step.depletion_ratio, 6),
        "marginal_externality_eur_yr": round(step.marginal_annual_externality, 2),
        "externality_eur_yr": round(step.annual_externality, 2),
        "revenue_eur": round(step.revenue, 2),
        "ecosystem_health": round(step.ecosystem_health, 6),
    }
    # Per-agent breakdown
    if step.agent_damages:
        d["agent_damages"] = {
            agents[i].name: round(step.agent_damages[i], 6)
            for i in range(min(n, len(step.agent_damages)))
        }
    if step.agent_annual_costs:
        d["agent_externality_eur_yr"] = {
            agents[i].name: round(step.agent_annual_costs[i], 2)
            for i in range(min(n, len(step.agent_annual_costs)))
        }
    # Cascade data (v0.3)
    if step.agent_direct_damages:
        d["agent_direct_damages"] = {
            agents[i].name: round(step.agent_direct_damages[i], 6)
            for i in range(min(n, len(step.agent_direct_damages)))
        }
    if step.agent_cascade_damages:
        d["agent_cascade_damages"] = {
            agents[i].name: round(step.agent_cascade_damages[i], 6)
            for i in range(min(n, len(step.agent_cascade_damages)))
        }
    if step.keystone_triggered:
        d["keystone_triggered"] = list(step.keystone_triggered)
    # Resilience (v0.4)
    d["resilience_zone"] = step.resilience_zone
    d["model_confidence"] = round(step.model_confidence, 4)
    if step.irreversibility_warning:
        d["irreversibility_warning"] = True
    # Substrate (v0.5)
    if step.substrate_erosion > 0 or step.k_fraction < 1.0:
        d["substrate_erosion"] = round(step.substrate_erosion, 6)
        d["effective_k"] = step.effective_k
        d["k_fraction"] = round(step.k_fraction, 6)
    # Pricing (v0.7): agent prices are €/yr at full damage
    if step.agent_prices:
        d["agent_prices_eur_yr"] = {
            agents[i].name: round(step.agent_prices[i], 2)
            for i in range(min(n, len(step.agent_prices)))
        }
    return d


def _restoration_step_to_dict(
    step: RestorationStep, agents: list,
) -> Dict[str, Any]:
    """Convert one RestorationStep to a dict."""
    n = len(agents)
    return {
        "step": step.step,
        "units_restored": step.units_restored,
        "recovery_ratio": round(step.recovery_ratio, 6),
        "depletion_ratio": round(step.depletion_ratio, 6),
        "marginal_service_value_eur_yr": round(step.marginal_service_value, 2),
        "service_value_eur_yr": round(step.cumulative_service_value, 2),
        "restoration_cost_so_far_eur": round(step.restoration_cost_so_far, 2),
        "ecosystem_health": round(step.ecosystem_health, 6),
        "agent_recoveries": {
            agents[i].name: round(step.agent_recoveries[i], 6)
            for i in range(min(n, len(step.agent_recoveries)))
        },
        "agent_service_value_eur_yr": {
            agents[i].name: round(step.agent_service_values[i], 2)
            for i in range(min(n, len(step.agent_service_values)))
        },
    }


def _maturation_step_to_dict(step: MaturationStep) -> Dict[str, Any]:
    """Convert one MaturationStep to a dict."""
    return {
        "year": step.year,
        "succession_phase": step.succession_phase,
        "service_fraction": round(step.service_fraction, 6),
        "annual_service_value_eur_yr": round(step.annual_service_value, 2),
        "cumulative_service_value_eur": round(step.cumulative_service_value, 2),
        "annual_carbon_absorbed": round(step.annual_carbon_absorbed, 4),
        "cumulative_carbon_absorbed": round(step.cumulative_carbon_absorbed, 4),
    }


def _extraction_npv_to_dict(npv: ExtractionNPV) -> Dict[str, Any]:
    """Convert ExtractionNPV to dict."""
    return {
        "services_eur_pv": round(npv.direct, 2),
        "carbon_release_eur_pv": round(npv.carbon_release, 2),
        "carbon_foregone_eur_pv": round(npv.carbon_foregone, 2),
        "carbon_released_tco2": round(npv.carbon_released_t, 4),
        "carbon_absorption_lost_tco2_yr": round(npv.carbon_absorption_lost_t_yr, 4),
        "carbon_price_eur_per_t": round(npv.carbon_price, 2),
        "substrate_unrecoverable_eur_pv": round(npv.substrate_unrecoverable, 2),
        "total_eur_pv": round(npv.total, 2),
        "horizon_years": npv.horizon,
    }


def _restoration_npv_to_dict(npv: RestorationNPV) -> Dict[str, Any]:
    """Convert RestorationNPV to dict."""
    return {
        "cost_eur_pv": round(npv.cost, 2),
        "service_benefits_eur_pv": round(npv.service_benefits, 2),
        "carbon_benefits_eur_pv": round(npv.carbon_benefits, 2),
        "total_benefits_eur_pv": round(npv.total_benefits, 2),
        "net_present_value_eur_pv": round(npv.net_present_value, 2),
        "roi": round(npv.roi, 4),
        "carbon_payback_years": npv.carbon_payback_years,
        "horizon_years": npv.horizon,
    }


def _carbon_breakeven_to_dict(cb: CarbonBreakeven) -> Dict[str, Any]:
    """Convert CarbonBreakeven to dict."""
    return {
        "breakeven_price_eur_per_t": round(cb.breakeven_price, 2),
        "current_price_eur_per_t": round(cb.current_price, 2),
        "gap_to_current_eur_per_t": round(cb.gap_to_current, 2),
        "profitable_at_current": cb.profitable_at_current,
        "projected_breakeven_year": cb.projected_breakeven_year,
    }


def _penalty_to_dict(pen: DestroyThenRestorePenalty) -> Dict[str, Any]:
    """Convert DestroyThenRestorePenalty to dict."""
    return {
        "restoration_cost_eur_pv": round(pen.restoration_cost, 2),
        "maturation_gap_eur_pv": round(pen.maturation_gap, 2),
        "substrate_loss_eur_pv": round(pen.substrate_loss, 2),
        "recovery_shortfall_eur_pv": round(pen.recovery_shortfall, 2),
        "carbon_not_recovered_eur_pv": round(pen.carbon_not_recovered, 2),
        "total_eur_pv": round(pen.total, 2),
        "foregone_revenue_eur": round(pen.foregone_revenue, 2),
        "penalty_ratio": round(pen.ratio, 4) if pen.ratio is not None else None,
        "horizon_years": pen.horizon,
    }


def _price_result_to_dict(pr: PriceResult) -> Dict[str, Any]:
    """Convert PriceResult to dict."""
    return {
        "prices_eur_yr": {k: round(v, 2) for k, v in pr.prices.items()},
        "scarcity_multipliers": {
            k: round(v, 4) for k, v in pr.scarcity_multipliers.items()
        },
        "demand_multipliers": {
            k: round(v, 4) for k, v in pr.demand_multipliers.items()
        },
        "spectral_radius_bound": round(pr.spectral_radius_bound, 6),
        "convergence_check": pr.convergence_check,
        "iterations": pr.iterations,
    }


PRICING_EXPERIMENTAL_NOTE: str = (
    "EXPERIMENTAL (decision D4, C8): endogenous pricing is quarantined. "
    "Every price is certified convergent (a run that cannot be certified "
    "fails instead of falling back to static values), but the formulation "
    "counts upstream value once per dependent agent and prices the whole "
    "loss at the end-state scarcity price, and most shipped anchors are "
    "placeholders. Do not use these figures as estimates."
)


def _pricing_to_dict(result: SimulationResult) -> Dict[str, Any]:
    """The "pricing" block of an extraction that ran with pricing on."""
    d: Dict[str, Any] = {
        "experimental": True,
        "status": "converged",
        "note": PRICING_EXPERIMENTAL_NOTE,
    }
    if result.steps:
        d.update(_price_result_to_dict(result.steps[-1].price_result))
    return d


# ── Strict JSON: non-finite numbers ───────────────────────────────────────────

# Why a key can be non-finite; other keys get a generic reason.
_NULL_REASONS: Dict[str, str] = {
    "substrate_recovery_years": (
        "never: the substrate does not recover (formation rate 0), so the "
        "substrate damage is permanent"
    ),
}


def _nonfinite_reason(key: str, value: float) -> str:
    if key in _NULL_REASONS and value == math.inf:
        return _NULL_REASONS[key]
    return f"non-finite value ({value!r}) cannot be represented in JSON"


def _strict(obj: Any) -> Any:
    """Copy of ``obj`` with every non-finite float replaced by None.

    In a dict, ``key: inf`` becomes ``key: None`` plus
    ``key_null_reason: <why>`` (see the module docstring).
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(value, float) and not math.isfinite(value):
                out[key] = None
                out[f"{key}_null_reason"] = _nonfinite_reason(key, value)
            else:
                out[key] = _strict(value)
        return out
    if isinstance(obj, list):
        return [
            None if isinstance(v, float) and not math.isfinite(v) else _strict(v)
            for v in obj
        ]
    return obj


# ── Public API ────────────────────────────────────────────────────────────────


def _sampled(steps, every: int) -> list:
    """Every ``every``-th step (steps every, 2·every, ...) plus the last one.

    Only those steps are evaluated (the engine's step sequences are lazy).
    """
    if every <= 1:
        return list(steps)
    n: int = len(steps)
    indices: list = list(range(every - 1, n, every))
    if n and (not indices or indices[-1] != n - 1):
        indices.append(n - 1)
    return [steps[i] for i in indices]


def _validate_steps_every(steps_every: int) -> None:
    if isinstance(steps_every, bool) or not isinstance(steps_every, int) or steps_every < 1:
        raise ValueError(f"steps_every must be an integer >= 1, got {steps_every!r}")


def simulation_result_to_dict(
    result: SimulationResult,
    include_steps: bool = True,
    steps_every: int = 1,
) -> Dict[str, Any]:
    """Convert a SimulationResult to a JSON-serializable dict.

    Args:
        result: Completed SimulationResult from run_extraction().
        include_steps: If True (default), include per-step data array.
        steps_every: Include every Nth step and the last (default 1: all);
            the output then carries "steps_every": N.

    Returns:
        A dict ready for json.dumps().
    """
    eco = result.ecosystem
    agents = eco.agents

    d: Dict[str, Any] = {
        "gaia_version": GAIA_VERSION,
        "mode": "extraction",
        "calibration": _calibration_to_dict(result.calibration),
        "ecosystem": {
            "name": eco.name,
            "resource": _resource_metadata(eco.resource),
            "agents": _agent_metadata(
                agents, eco.resource.area_ha, result.agent_trophic_amplification,
            ),
            "interactions": _interaction_metadata(eco.interactions),
            "calibration_regime": _calibration_regime(eco),
            "has_pricing": eco.pricing is not None,
        },
        "summary": {
            "total_units_extracted": result.total_units_extracted,
            "revenue_eur": round(result.revenue, 2),
            "annual_externality_eur_yr": round(result.annual_externality, 2),
            "pv_externality_eur_pv": round(result.pv_externality, 2),
            "net_social_cost_eur_pv": round(result.net_social_cost, 2),
            **_by_horizon("pv_externality", result.pv_externality_by_horizon),
            "discount_is_default": result.discount_is_default,
            "final_ecosystem_health": round(result.final_ecosystem_health, 6),
            "num_steps": len(result.steps),
            "annual_externality_band": _confidence_band(result),
        },
    }
    if result.steps:
        d["summary"]["agent_externality_eur_yr"] = _by_agent(
            agents, result.steps[-1].agent_annual_costs,
        )
    if result.agent_direct_annual_costs:
        d["summary"]["agent_direct_externality_eur_yr"] = _by_agent(
            agents, result.agent_direct_annual_costs,
        )
        d["summary"]["agent_cascade_externality_eur_yr"] = _by_agent(
            agents, result.agent_cascade_annual_costs,
        )

    _validate_steps_every(steps_every)
    if include_steps:
        d["steps_every"] = steps_every
        d["steps"] = [
            _simulation_step_to_dict(s, agents)
            for s in _sampled(result.steps, steps_every)
        ]

    substrate = _extraction_substrate(result)
    if substrate is not None:
        d["substrate"] = substrate

    # NPV analysis (v0.6), with the discounting it used
    if result.extraction_npv is not None:
        d["npv_analysis"] = _extraction_npv_to_dict(result.extraction_npv)
        if result.discount is not None:
            d["npv_analysis"]["discount"] = _discount_to_dict(
                result.discount, result.discount_is_default,
            )

    # Final price decomposition (v0.7, experimental)
    if eco.pricing is not None:
        d["pricing"] = _pricing_to_dict(result)

    return d


def restoration_result_to_dict(
    result: RestorationResult,
    include_steps: bool = True,
    notes: Optional[List[str]] = None,
    steps_every: int = 1,
) -> Dict[str, Any]:
    """Convert a RestorationResult to a JSON-serializable dict.

    Args:
        result: Completed RestorationResult from run_restoration().
        include_steps: If True (default), include per-step data array.
        steps_every: Include every Nth step and the last (default 1: all).
        notes: Optional list of annotation strings (e.g. marine annual note).

    Returns:
        A dict ready for json.dumps().
    """
    eco = result.ecosystem
    agents = eco.agents

    d: Dict[str, Any] = {
        "gaia_version": GAIA_VERSION,
        "mode": "restoration",
        "calibration": _calibration_to_dict(result.calibration),
        "ecosystem": {
            "name": eco.name,
            "resource": _resource_metadata(eco.resource),
            "agents": _agent_metadata(agents, eco.resource.area_ha),
            "interactions": _interaction_metadata(eco.interactions),
            "calibration_regime": _calibration_regime(eco),
        },
        "restoration_cost": {
            "planting_cost_per_unit_eur": (
                result.restoration_cost.planting_cost_per_unit
            ),
            "annual_maintenance_per_unit_eur_yr": (
                result.restoration_cost.annual_maintenance_per_unit
            ),
            "maintenance_years": result.restoration_cost.maintenance_years,
            "total_cost_per_unit_eur": result.restoration_cost.total_cost_per_unit,
        },
        "summary": {
            "total_units_restored": result.total_units_restored,
            "units_lost": result.units_lost,
            "depletion_before": round(result.depletion_before, 6),
            "depletion_after": round(result.depletion_after, 6),
            "initial_ecosystem_health": round(result.initial_ecosystem_health, 6),
            "total_restoration_cost_eur": round(result.total_restoration_cost, 2),
            "annual_damage_reversal_eur_yr": round(result.annual_damage_reversal, 2),
            "annual_recovered_value_eur_yr": round(result.annual_recovered_value, 2),
            "net_restoration_value_eur_pv": round(result.net_restoration_pv, 2),
            **_by_horizon(
                "net_restoration_value", result.net_restoration_pv_by_horizon,
            ),
            "restoration_cost_ratio": (
                round(result.restoration_cost_ratio, 4)
                if result.restoration_cost_ratio is not None else None
            ),
            "final_ecosystem_health": round(result.final_ecosystem_health, 6),
            "num_steps": len(result.steps),
        },
    }

    if result.steps:
        d["summary"]["agent_service_value_eur_yr"] = _by_agent(
            agents, result.steps[-1].agent_service_values,
        )

    _validate_steps_every(steps_every)
    if include_steps:
        d["steps_every"] = steps_every
        d["steps"] = [
            _restoration_step_to_dict(s, agents)
            for s in _sampled(result.steps, steps_every)
        ]

    # Maturation timeline (v0.4)
    if result.maturation_timeline:
        d["maturation"] = {
            "years_to_pioneer": result.years_to_pioneer,
            "years_to_50pct": result.years_to_50pct,
            "years_to_90pct": result.years_to_90pct,
            "maturation_gap_eur_pv": round(result.maturation_gap_pv, 2),
            "timeline": [
                _maturation_step_to_dict(ms)
                for ms in result.maturation_timeline
            ],
        }

    # Substrate ceiling (v0.5)
    if result.substrate_ceiling < 1.0:
        d["substrate"] = {
            "substrate_ceiling": round(result.substrate_ceiling, 6),
            "substrate_recovery_years": round(
                result.substrate_recovery_years, 2,
            ),
        }

    # NPV analysis (v0.6)
    if result.restoration_npv is not None:
        d["npv_analysis"] = _restoration_npv_to_dict(result.restoration_npv)

    # Carbon breakeven (v0.6)
    if result.carbon_breakeven is not None:
        d["carbon_breakeven"] = _carbon_breakeven_to_dict(
            result.carbon_breakeven,
        )

    # Destroy-then-restore penalty (Step 3.7)
    if result.destroy_then_restore_penalty is not None:
        d["destroy_then_restore_penalty"] = _penalty_to_dict(
            result.destroy_then_restore_penalty,
        )

    # Notes (e.g. Posidonia annual externality warning)
    if notes:
        d["notes"] = notes

    return d


def to_json(
    result,
    include_steps: bool = True,
    indent: int = 2,
    notes: Optional[List[str]] = None,
    steps_every: int = 1,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Convert a SimulationResult or RestorationResult to a JSON string.

    Args:
        result: SimulationResult or RestorationResult.
        include_steps: Include per-step data (default True).
        indent: JSON indentation level (default 2).
        notes: Optional annotation strings for the output.
        steps_every: Include every Nth step and the last (default 1: all).
        extra: Optional top-level blocks to add (e.g. "benchmarks",
            "uncertainty"); None values are left out.

    Returns:
        JSON string: strict JSON, non-finite numbers as null plus a
        ``<key>_null_reason`` (see the module docstring).

    Raises:
        TypeError: If result is not a supported type.
    """
    if isinstance(result, SimulationResult):
        d = simulation_result_to_dict(
            result, include_steps=include_steps, steps_every=steps_every,
        )
        if notes:
            d["notes"] = notes
    elif isinstance(result, RestorationResult):
        d = restoration_result_to_dict(
            result, include_steps=include_steps, notes=notes,
            steps_every=steps_every,
        )
    else:
        raise TypeError(
            f"Expected SimulationResult or RestorationResult, "
            f"got {type(result).__name__}"
        )
    for key, block in (extra or {}).items():
        if block is not None:
            d[key] = block
    return json.dumps(_strict(d), indent=indent, ensure_ascii=False, allow_nan=False)
