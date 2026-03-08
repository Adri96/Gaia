"""
Gaia v0.8.1 — JSON serialization for simulation results.

Converts SimulationResult and RestorationResult dataclasses to
JSON-serializable dicts. Omits non-serializable fields (callables,
config objects) and includes only output data.

Produces a stable, documented JSON schema with version field.
Pure stdlib — no numpy or third-party dependencies.
"""

import json
from typing import Any, Dict, List, Optional

from gaia.models import (
    CarbonBreakeven,
    ExtractionNPV,
    MaturationStep,
    PreventionAdvantageV06,
    PriceResult,
    RestorationNPV,
    RestorationResult,
    RestorationStep,
    SimulationResult,
    SimulationStep,
)

GAIA_VERSION = "0.8.1"


# ── Internal helpers ──────────────────────────────────────────────────────────


def _agent_metadata(agents: list) -> List[Dict[str, Any]]:
    """Serialize agent metadata (no callables)."""
    return [
        {
            "name": a.name,
            "dependency_weight": a.dependency_weight,
            "monetary_rate": a.monetary_rate,
            "description": a.description,
            "trophic_level": a.trophic_level,
            "is_keystone": a.is_keystone,
            "keystone_threshold": a.keystone_threshold if a.is_keystone else None,
        }
        for a in agents
    ]


def _resource_metadata(resource) -> Dict[str, Any]:
    """Serialize resource metadata (no substrate/discount internals)."""
    d: Dict[str, Any] = {
        "name": resource.name,
        "total_units": resource.total_units,
        "safe_threshold_ratio": resource.safe_threshold_ratio,
        "safe_threshold_units": resource.safe_threshold_units,
        "unit_value": resource.unit_value,
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
        cp = resource.carbon_profile
        d["carbon_stored_per_unit"] = cp.stored_carbon_tonnes
        d["carbon_absorption_per_unit_yr"] = cp.annual_absorption_tonnes
        d["carbon_price_per_tonne"] = cp.carbon_price_per_tonne
    return d


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
        "marginal_cost": round(step.marginal_cost, 2),
        "cumulative_cost": round(step.cumulative_cost, 2),
        "private_revenue": round(step.private_revenue, 2),
        "ecosystem_health": round(step.ecosystem_health, 6),
    }
    # Per-agent breakdown
    if step.agent_damages:
        d["agent_damages"] = {
            agents[i].name: round(step.agent_damages[i], 6)
            for i in range(min(n, len(step.agent_damages)))
        }
    if step.agent_costs:
        d["agent_costs"] = {
            agents[i].name: round(step.agent_costs[i], 2)
            for i in range(min(n, len(step.agent_costs)))
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
    # Discount (v0.6)
    if step.discount_factor_at_step != 1.0:
        d["discount_factor"] = round(step.discount_factor_at_step, 6)
        d["npv_externality"] = round(step.npv_externality, 2)
    if step.carbon_price_used > 0:
        d["carbon_price_used"] = round(step.carbon_price_used, 2)
    # Pricing (v0.7)
    if step.agent_prices:
        d["agent_prices"] = {
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
        "marginal_service_value": round(step.marginal_service_value, 2),
        "cumulative_service_value": round(step.cumulative_service_value, 2),
        "restoration_cost_so_far": round(step.restoration_cost_so_far, 2),
        "ecosystem_health": round(step.ecosystem_health, 6),
        "agent_recoveries": {
            agents[i].name: round(step.agent_recoveries[i], 6)
            for i in range(min(n, len(step.agent_recoveries)))
        },
        "agent_service_values": {
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
        "annual_service_value": round(step.annual_service_value, 2),
        "cumulative_service_value": round(step.cumulative_service_value, 2),
        "annual_carbon_absorbed": round(step.annual_carbon_absorbed, 4),
        "cumulative_carbon_absorbed": round(step.cumulative_carbon_absorbed, 4),
    }


def _extraction_npv_to_dict(npv: ExtractionNPV) -> Dict[str, Any]:
    """Convert ExtractionNPV to dict."""
    return {
        "direct": round(npv.direct, 2),
        "carbon_release": round(npv.carbon_release, 2),
        "carbon_foregone": round(npv.carbon_foregone, 2),
        "substrate_damage": round(npv.substrate_damage, 2),
        "total": round(npv.total, 2),
        "horizon": npv.horizon,
    }


def _restoration_npv_to_dict(npv: RestorationNPV) -> Dict[str, Any]:
    """Convert RestorationNPV to dict."""
    return {
        "cost": round(npv.cost, 2),
        "service_benefits": round(npv.service_benefits, 2),
        "carbon_benefits": round(npv.carbon_benefits, 2),
        "total_benefits": round(npv.total_benefits, 2),
        "net_present_value": round(npv.net_present_value, 2),
        "roi": round(npv.roi, 4),
        "carbon_payback_years": npv.carbon_payback_years,
        "horizon": npv.horizon,
    }


def _carbon_breakeven_to_dict(cb: CarbonBreakeven) -> Dict[str, Any]:
    """Convert CarbonBreakeven to dict."""
    return {
        "breakeven_price": round(cb.breakeven_price, 2),
        "current_price": round(cb.current_price, 2),
        "gap_to_current": round(cb.gap_to_current, 2),
        "profitable_at_current": cb.profitable_at_current,
        "projected_breakeven_year": cb.projected_breakeven_year,
    }


def _prevention_advantage_v06_to_dict(pa: PreventionAdvantageV06) -> Dict[str, Any]:
    """Convert PreventionAdvantageV06 to dict."""
    return {
        "pa_simple": round(pa.pa_simple, 4),
        "pa_with_carbon": round(pa.pa_with_carbon, 4),
        "pa_with_substrate": round(pa.pa_with_substrate, 4),
        "pa_full": round(pa.pa_full, 4),
        "npv_prevention_cost": round(pa.npv_prevention_cost, 2),
        "npv_restoration_total": round(pa.npv_restoration_total, 2),
    }


def _price_result_to_dict(pr: PriceResult) -> Dict[str, Any]:
    """Convert PriceResult to dict."""
    return {
        "prices": {k: round(v, 2) for k, v in pr.prices.items()},
        "scarcity_multipliers": {
            k: round(v, 4) for k, v in pr.scarcity_multipliers.items()
        },
        "demand_multipliers": {
            k: round(v, 4) for k, v in pr.demand_multipliers.items()
        },
        "spectral_radius": round(pr.spectral_radius, 6),
        "converged": pr.converged,
        "iterations": pr.iterations,
    }


# ── Public API ────────────────────────────────────────────────────────────────


def simulation_result_to_dict(
    result: SimulationResult,
    include_steps: bool = True,
) -> Dict[str, Any]:
    """Convert a SimulationResult to a JSON-serializable dict.

    Args:
        result: Completed SimulationResult from run_extraction().
        include_steps: If True (default), include per-step data array.

    Returns:
        A dict ready for json.dumps().
    """
    eco = result.ecosystem
    agents = eco.agents

    d: Dict[str, Any] = {
        "gaia_version": GAIA_VERSION,
        "mode": "extraction",
        "ecosystem": {
            "name": eco.name,
            "resource": _resource_metadata(eco.resource),
            "agents": _agent_metadata(agents),
            "interactions": _interaction_metadata(eco.interactions),
            "has_pricing": eco.pricing is not None,
        },
        "summary": {
            "total_units_extracted": result.total_units_extracted,
            "total_private_revenue": round(result.total_private_revenue, 2),
            "total_externality_cost": round(result.total_externality_cost, 2),
            "net_social_cost": round(result.net_social_cost, 2),
            "final_ecosystem_health": round(result.final_ecosystem_health, 6),
            "num_steps": len(result.steps),
        },
    }

    if include_steps:
        d["steps"] = [
            _simulation_step_to_dict(s, agents) for s in result.steps
        ]

    # NPV analysis (v0.6)
    if result.extraction_npv is not None:
        d["npv_analysis"] = _extraction_npv_to_dict(result.extraction_npv)

    # Final price decomposition (v0.7)
    if result.steps and result.steps[-1].price_result is not None:
        d["pricing"] = _price_result_to_dict(result.steps[-1].price_result)

    return d


def restoration_result_to_dict(
    result: RestorationResult,
    include_steps: bool = True,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert a RestorationResult to a JSON-serializable dict.

    Args:
        result: Completed RestorationResult from run_restoration().
        include_steps: If True (default), include per-step data array.
        notes: Optional list of annotation strings (e.g. marine annual note).

    Returns:
        A dict ready for json.dumps().
    """
    eco = result.ecosystem
    agents = eco.agents

    d: Dict[str, Any] = {
        "gaia_version": GAIA_VERSION,
        "mode": "restoration",
        "ecosystem": {
            "name": eco.name,
            "resource": _resource_metadata(eco.resource),
            "agents": _agent_metadata(agents),
            "interactions": _interaction_metadata(eco.interactions),
        },
        "restoration_cost": {
            "planting_cost_per_unit": result.restoration_cost.planting_cost_per_unit,
            "annual_maintenance_per_unit": (
                result.restoration_cost.annual_maintenance_per_unit
            ),
            "maintenance_years": result.restoration_cost.maintenance_years,
            "total_cost_per_unit": result.restoration_cost.total_cost_per_unit,
        },
        "summary": {
            "total_units_restored": result.total_units_restored,
            "total_restoration_cost": round(result.total_restoration_cost, 2),
            "total_recovered_value": round(result.total_recovered_value, 2),
            "net_restoration_value": round(result.net_restoration_value, 2),
            "prevention_advantage": round(result.prevention_advantage, 4),
            "final_ecosystem_health": round(result.final_ecosystem_health, 6),
            "num_steps": len(result.steps),
        },
    }

    if include_steps:
        d["steps"] = [
            _restoration_step_to_dict(s, agents) for s in result.steps
        ]

    # Maturation timeline (v0.4)
    if result.maturation_timeline:
        d["maturation"] = {
            "years_to_pioneer": result.years_to_pioneer,
            "years_to_50pct": result.years_to_50pct,
            "years_to_90pct": result.years_to_90pct,
            "total_maturation_gap": round(result.total_maturation_gap, 2),
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
            "prevention_advantage_with_substrate": round(
                result.prevention_advantage_with_substrate, 4,
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

    # Prevention advantage v0.6
    if result.prevention_advantage_v06 is not None:
        d["prevention_advantage_v06"] = _prevention_advantage_v06_to_dict(
            result.prevention_advantage_v06,
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
) -> str:
    """Convert a SimulationResult or RestorationResult to a JSON string.

    Args:
        result: SimulationResult or RestorationResult.
        include_steps: Include per-step data (default True).
        indent: JSON indentation level (default 2).
        notes: Optional annotation strings for the output.

    Returns:
        JSON string.

    Raises:
        TypeError: If result is not a supported type.
    """
    if isinstance(result, SimulationResult):
        d = simulation_result_to_dict(result, include_steps=include_steps)
        if notes:
            d["notes"] = notes
    elif isinstance(result, RestorationResult):
        d = restoration_result_to_dict(
            result, include_steps=include_steps, notes=notes,
        )
    else:
        raise TypeError(
            f"Expected SimulationResult or RestorationResult, "
            f"got {type(result).__name__}"
        )
    return json.dumps(d, indent=indent, ensure_ascii=False)
