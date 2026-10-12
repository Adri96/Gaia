"""
Gaia — the ecosystem file format (Step 7, finding E7): JSON, schema 1.

An ecosystem — or a whole case: the ecosystem plus its restoration defaults
and run defaults — is a JSON document. The four shipped cases are such files
(gaia/cases/data/*.json), run with ``gaia run <case | file.json>``.

    ecosystem_from_dict(data)      -> Ecosystem   (validated)
    ecosystem_to_dict(ecosystem)   -> dict        (canonical form)
    load_ecosystem(path) / save_ecosystem(ecosystem, path)
    case_from_dict(data) / load_case_file(path) -> Case

A document (every key below is optional unless marked *required*):

    gaia_schema         *required*, 1
    name                *required*, the ecosystem name
    description         free text (not used by the model)
    calibration_regime  "A" | "B" | null (gaia.models.CalibrationRegime)
    resource            *required*: name, unit, total_units*, unit_value*,
                        safe_threshold_ratio*, and the area as area_ha or
                        units_per_ha (see below)
    provenance_defaults provenance shared by many parameters (see below)
    agent_defaults      annual_value_per_ha and damage (a curve name) for
                        every agent that does not set its own
    damage_curves       named damage curves: {name: curve}
    agents              *required*, a non-empty list: name*, description,
                        dependency_weight*, annual_value_per_ha, damage (a
                        curve name or an inline curve), trophic_level,
                        is_keystone, keystone_threshold
    interactions        list: source*, target*, strength*, type, description
    carbon              gaia.models.CarbonProfile fields (all four required)
    resilience          gaia.models.ResilienceConfig fields
    substrate           gaia.models.SubstrateProfile fields (substrate_type*)
    discount            gaia.models.DiscountConfig fields; rate_schedule is a
                        number or a list of {from_year, rate}; "profile"
                        starts from a gaia.discount profile (market, central,
                        environmental, green_book)
    pricing             EXPERIMENTAL (decision D4): enabled, reference_area_ha,
                        anchor_every_agent, anchors, scarcity_functions,
                        default_scarcity, convergence_tolerance, max_iterations
    restoration         restoration cost defaults: planting_cost_per_unit*,
                        annual_maintenance_per_unit*, maintenance_years*
    recovery            the recovery curve of every agent:
                        {type: logistic, steepness} | {type: linear, slope}
    succession          gaia.models.SuccessionCurve fields (all required)
    run                 run defaults: units (the default --units), report_note
                        (appended to the text report), json_notes (list)

Curves: {"type": "logistic", "steepness": 12}, {"type": "exponential",
"base": 2} or {"type": "piecewise", "pre_slope_ratio": 0.1}, each with an
optional "threshold" (default: the resource's safe threshold, so a
--threshold override moves every curve that does not set its own).

The resource area: "area_ha" (a fixed area), or "units_per_ha" (a reference
density: area = total_units / units_per_ha, so changing the number of units
changes the area). With "unit": "ha" each unit is one hectare and the area
always equals total_units. "unit" is otherwise the plural unit name, as in
"trees/ha".

Provenance (Step 5): every numeric parameter is either a bare number or an
object {"value", "unit", "source", "confidence", "note"} (value, unit and
confidence required), which becomes a gaia.provenance.Param, reported in
every output's calibration block. A bare number is reported only when a
``provenance_defaults`` entry matches its name: keys are parameter names with
"[*]" for any agent or edge, e.g. "agent[*].dependency_weight" or
"edge[*].strength", values are the same objects without "value". An inline
object always wins. Parameter names follow the document:

    resource.<field>                 resource fields
    agents.annual_value_per_ha       agent_defaults.annual_value_per_ha
    agent[<name>].<field>            agent fields
    damage.<curve>_<param>           damage_curves.<curve>.<param>
    agent[<name>].damage.<param>     an agent's inline curve
    edge[<source> → <target>].strength
    carbon.<field>, resilience.<field>, substrate.<field>, discount.<field>
    discount.rate_schedule[year <from_year>]
    restoration.<field>, recovery.<type>_<param>, succession.<field>

and parameters are reported in that order (resource area, unit value and
threshold first; agents by field, then curves, keystone thresholds and
edges). Pricing anchors carry their own source and confidence.

Errors are ValueErrors naming the JSON path, e.g.
``$.agents[3].damage: unknown damage curve 'logistc' (defined: logistic)``;
unknown keys, duplicate keys and NaN/Infinity are rejected. A future
"dynamics" block (path-dependent engine, decision D5) would come with
schema 2; schema-1 documents stay valid.

No third-party dependencies.
"""

import dataclasses
import json
import math
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from gaia.constants import DEFAULT_KEYSTONE_THRESHOLD
from gaia.damage import (
    KERNEL_EXPONENTIAL,
    KERNEL_LOGISTIC,
    KERNEL_PIECEWISE,
    exponential_damage,
    logistic_damage,
    piecewise_damage,
)
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
    ScarcityFunction,
    SubstrateProfile,
    SuccessionCurve,
)
from gaia.provenance import Confidence, Param, anchor_params, area_param, user_or_default
from gaia.recovery import linear_recovery, logistic_recovery

SCHEMA_VERSION: int = 1

# Provenance labels of values given through the API or the CLI (the
# "user-supplied (...)" source of the Param that replaces the file's).
DEFAULT_LABELS: Dict[str, str] = {
    "total_units": "--total-units / total_units",
    "unit_value": "--unit-value / unit_value",
    "safe_threshold_ratio": "--threshold",
    "area_ha": "--area-ha / area_ha",
}

_TOP_LEVEL = (
    "gaia_schema", "name", "description", "calibration_regime", "resource",
    "provenance_defaults", "agent_defaults", "damage_curves", "agents",
    "interactions", "carbon", "resilience", "substrate", "discount", "pricing",
    "restoration", "recovery", "succession", "run",
)

_DAMAGE_FACTORIES: Dict[str, Tuple[Callable[..., Any], Tuple[str, ...]]] = {
    "logistic": (logistic_damage, ("steepness",)),
    "exponential": (exponential_damage, ("base",)),
    "piecewise": (piecewise_damage, ("pre_slope_ratio",)),
}
_RECOVERY_FACTORIES: Dict[str, Tuple[Callable[..., Any], Tuple[str, ...]]] = {
    "logistic": (logistic_recovery, ("steepness",)),
    "linear": (linear_recovery, ("slope",)),
}

_CARBON_FIELDS = (
    "stored_carbon_tonnes", "annual_absorption_tonnes", "soil_carbon_tonnes",
    "soil_release_fraction",
)
_RESILIENCE_FIELDS = (
    "warning_zone_width", "confidence_green", "confidence_yellow", "confidence_red",
    "irreversibility_flag_ratio",
)
_SUBSTRATE_NUMBERS = (
    "soil_depth_cm", "sediment_stability", "erosion_rate_unprotected",
    "erosion_rate_protected", "formation_rate", "erosion_alpha", "critical_minimum",
    "residual_fraction",
)
_SUBSTRATE_STRINGS = ("substrate_type", "capacity_function", "confidence")
_SUCCESSION_FIELDS = (
    "pioneer_end_year", "intermediate_end_year", "climax_approach_year",
    "pioneer_service", "intermediate_service", "maturation_delay",
)
_RESTORATION_FIELDS = ("planting_cost_per_unit", "annual_maintenance_per_unit", "maintenance_years")
_DISCOUNT_PROFILES = ("market", "central", "environmental", "green_book")

# Provenance buckets, in reporting order (after the resource parameters).
_BUCKETS = (
    "agent_values", "agent_weights", "damage", "keystone", "edges",
    "carbon", "resilience", "substrate", "discount",
)
_BRACKETS = re.compile(r"\[[^\]]*\]")


# ── Reading helpers ───────────────────────────────────────────────────────────


def _key(path: str, key: str) -> str:
    """JSON path of ``key`` under ``path``: $.a.b, or $.a["Canopy Trees"]."""
    return f"{path}.{key}" if key.isidentifier() else f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return type(value).__name__


def _object(data: Any, path: str, required: Sequence[str] = (), optional: Sequence[str] = ()) -> dict:
    """``data`` as a dict with only the allowed keys and every required one."""
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected an object, got {_kind(data)}")
    allowed = list(required) + list(optional)
    for key in data:
        if key not in allowed:
            raise ValueError(f"{path}: unknown key {key!r} (allowed: {', '.join(allowed)})")
    for key in required:
        if key not in data:
            raise ValueError(f"{_key(path, key)}: required")
    return data


def _string(value: Any, path: str, nullable: bool = False) -> Optional[str]:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{path}: expected a string, got {_kind(value)}")
    return value


def _str(value: Any, path: str) -> str:
    out = _string(value, path)
    assert out is not None
    return out


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path}: expected true or false, got {_kind(value)}")
    return value


def _plain_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}: expected a number, got {_kind(value)}")
    if not math.isfinite(value):
        raise ValueError(f"{path}: must be finite, got {value}")
    return value


def _plain_int(value: Any, path: str) -> int:
    number = _plain_number(value, path)
    if number != int(number):
        raise ValueError(f"{path}: expected an integer, got {number}")
    return int(number)


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a list, got {_kind(value)}")
    return value


@dataclass(frozen=True)
class Quantity:
    """A parsed numeric parameter: its value and, if recorded, its Param."""

    value: Any  # float, or int for integer fields
    param: Optional[Param] = None


class _Reader:
    """Parses numbers with their provenance (bare or {value, unit, ...})."""

    def __init__(self, defaults: Dict[str, Dict[str, Any]]) -> None:
        self.defaults = defaults
        self.used: set = set()

    def quantity(self, raw: Any, path: str, name: str, integer: bool = False) -> Quantity:
        param: Optional[Param]
        pattern = _BRACKETS.sub("[*]", name)
        key = name if name in self.defaults else pattern if pattern in self.defaults else None
        if key is not None:
            self.used.add(key)
        if isinstance(raw, dict):
            obj = _object(raw, path, ("value", "unit", "confidence"), ("source", "note"))
            value = _plain_number(obj["value"], _key(path, "value"))
            param = _make_param(value, obj, path, name)
        else:
            value = _plain_number(raw, path)
            param = None
            if key is not None:
                template_path = f"$.provenance_defaults[{json.dumps(key, ensure_ascii=False)}]"
                param = _make_param(value, self.defaults[key], template_path, name)
        if integer:
            if value != int(value):
                raise ValueError(f"{path}: expected an integer, got {value}")
            return Quantity(int(value), param)
        return Quantity(float(value), param)

    def number(self, raw: Any, path: str, name: str, bucket: List[Param], integer: bool = False) -> Any:
        """The value of a parameter; its Param (if any) is appended to ``bucket``."""
        q = self.quantity(raw, path, name, integer)
        if q.param is not None:
            bucket.append(q.param)
        return q.value


def _make_param(value: float, obj: dict, path: str, name: str) -> Param:
    unit = _str(obj["unit"], _key(path, "unit"))
    source = _string(obj.get("source"), _key(path, "source"), nullable=True)
    confidence = _str(obj["confidence"], _key(path, "confidence"))
    note = _string(obj.get("note", ""), _key(path, "note"))
    valid = [c.value for c in Confidence]
    if confidence not in valid:
        raise ValueError(
            f"{_key(path, 'confidence')}: {confidence!r} is not one of {', '.join(valid)}"
        )
    try:
        return Param(value, unit, source, Confidence(confidence), note or "", name=name)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None


# ── The parsed document ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Curve:
    """A damage or recovery curve: its type, parameters and optional threshold."""

    kind: str
    params: Tuple[Tuple[str, float], ...]
    threshold: Optional[float]
    path: str


@dataclass(frozen=True)
class _AgentSpec:
    name: str
    description: str
    weight: float
    value: float
    curve: _Curve
    trophic_level: int
    is_keystone: bool
    keystone_threshold: float


@dataclass(frozen=True)
class _PricingSpec:
    config: PricingConfig
    enabled: bool
    reference_area_ha: Optional[float]
    anchor_every_agent: bool


@dataclass(frozen=True)
class Case:
    """A parsed case document: an ecosystem with its restoration and run
    defaults, from which ecosystems are built (``build_ecosystem``).

    Attributes:
        name: The ecosystem name.
        description: Free text from the document.
        origin: Where the document came from (a case name or a path).
        resource_name, unit: Resource name; plural unit name ("trees") or
            "ha" (each unit is one hectare).
        total_units, unit_value, safe_threshold_ratio: Resource Quantities.
        area: The fixed area (area_ha) or None.
        density: The reference density (units_per_ha) or None.
        calibration_regime: CalibrationRegime or None.
        units: Default number of units of a run (run.units).
        report_note: Text appended to the text report.
        json_notes: Notes added to the JSON output.
    """

    name: str
    description: str
    origin: str
    resource_name: str
    unit: str
    total_units: Quantity
    unit_value: Quantity
    safe_threshold_ratio: Quantity
    area: Optional[Quantity]
    density: Optional[Quantity]
    calibration_regime: Optional[CalibrationRegime]
    agents: Tuple[_AgentSpec, ...]
    interactions: Tuple[Tuple[str, str, float, str, str], ...]
    buckets: Dict[str, Tuple[Param, ...]]
    carbon: Optional[Dict[str, float]]
    resilience: Optional[Dict[str, float]]
    substrate: Optional[Dict[str, Any]]
    discount: Optional[Dict[str, Any]]
    pricing: Optional[_PricingSpec]
    restoration: Optional[Dict[str, Quantity]]
    recovery: Optional[_Curve]
    recovery_params: Tuple[Param, ...]
    succession: Optional[Dict[str, float]]
    succession_params: Tuple[Param, ...]
    units: Optional[int]
    report_note: str = ""
    json_notes: Tuple[str, ...] = field(default_factory=tuple)

    # ── Defaults ──────────────────────────────────────────────────────────────

    @property
    def area_ha(self) -> float:
        """The reference area (ha) at the document's number of units."""
        if self.unit == "ha":
            return float(self.total_units.value)
        if self.density is not None:
            return self.total_units.value / self.density.value
        assert self.area is not None
        return self.area.value

    @property
    def units_per_ha(self) -> float:
        """The reference density (units/ha)."""
        if self.density is not None:
            return self.density.value
        return self.total_units.value / self.area_ha

    @property
    def default_units(self) -> int:
        """Default number of units extracted or restored: run.units, or the
        safe threshold's worth of units when the document sets none."""
        if self.units is not None:
            return self.units
        return int(self.total_units.value * self.safe_threshold_ratio.value)

    def restoration_defaults(self) -> Dict[str, Any]:
        """RestorationCost keyword defaults: the document's, or 50 / 10 / 10."""
        if self.restoration is None:
            return {"planting_cost_per_unit": 50.0, "annual_maintenance_per_unit": 10.0,
                    "maintenance_years": 10}
        return {key: q.value for key, q in self.restoration.items()}

    @property
    def succession_curve(self) -> Optional[SuccessionCurve]:
        """The succession curve (a new object), or None."""
        return SuccessionCurve(**self.succession) if self.succession is not None else None

    # ── Building ──────────────────────────────────────────────────────────────

    def build_ecosystem(
        self,
        total_units: Optional[int] = None,
        safe_threshold_ratio: Optional[float] = None,
        unit_value: Optional[float] = None,
        area_ha: Optional[float] = None,
        with_pricing: Optional[bool] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Ecosystem:
        """Build the Ecosystem (new objects each call).

        Args:
            total_units, safe_threshold_ratio, unit_value, area_ha: Override
                the document's value; a different value is recorded as
                user-supplied (gaia.provenance.user_or_default).
            with_pricing: Attach the EXPERIMENTAL pricing configuration
                (default: the document's pricing.enabled).
            labels: How the user sets each value, for the user-supplied
                provenance (default DEFAULT_LABELS).

        Raises:
            ValueError: With unit "ha", if area_ha differs from total_units;
                with pricing requested and no pricing block.
        """
        lab = dict(DEFAULT_LABELS, **(labels or {}))
        total, total_param = _override(self.total_units, total_units, lab["total_units"])
        threshold, threshold_param = _override(
            self.safe_threshold_ratio, safe_threshold_ratio, lab["safe_threshold_ratio"]
        )
        value, value_param = _override(self.unit_value, unit_value, lab["unit_value"])
        area, a_param = self._area(total, area_ha, lab)

        agents = [
            Agent(
                name=a.name,
                dependency_weight=a.weight,
                damage_function=_build_curve(a.curve, threshold, _DAMAGE_FACTORIES),
                annual_value_per_ha=a.value,
                description=a.description,
                trophic_level=a.trophic_level,
                is_keystone=a.is_keystone,
                keystone_threshold=a.keystone_threshold,
            )
            for a in self.agents
        ]
        interactions = [InteractionEdge(*edge) for edge in self.interactions]
        resource = Resource(
            name=self.resource_name,
            total_units=total,
            safe_threshold_ratio=threshold,
            unit_value=value,
            area_ha=area,
            carbon_profile=CarbonProfile(**self.carbon) if self.carbon is not None else None,
            resilience=ResilienceConfig(**self.resilience) if self.resilience is not None else None,
            substrate=SubstrateProfile(**self.substrate) if self.substrate is not None else None,
            discount=_discount_config(self.discount) if self.discount is not None else None,
        )
        if with_pricing is None:
            with_pricing = self.pricing is not None and self.pricing.enabled
        pricing = None
        if with_pricing:
            if self.pricing is None:
                raise ValueError(f"{self.name}: the document has no pricing block")
            pricing = self._pricing(agents, area)

        provenance = [p for p in (total_param, a_param, value_param, threshold_param) if p is not None]
        for bucket in _BUCKETS:
            provenance.extend(self.buckets.get(bucket, ()))
        if pricing is not None:
            provenance.extend(anchor_params(pricing))
        return Ecosystem(
            name=self.name,
            resource=resource,
            agents=agents,
            interactions=interactions,
            pricing=pricing,
            calibration_regime=self.calibration_regime,
            provenance=provenance,
        )

    def _area(self, total: int, area_ha: Optional[float], lab: Dict[str, str]) -> Tuple[float, Optional[Param]]:
        if self.unit == "ha":
            if area_ha is not None and area_ha != total:
                raise ValueError(
                    f"{self.resource_name}: the unit is the hectare, so area_ha "
                    f"({area_ha}) must equal the number of units ({total})"
                )
            area = float(total)
            param = self.area.param if self.area is not None else None
            return area, user_or_default(param, area, lab["total_units"]) if param else None
        if self.density is not None:
            derived = total / self.density.value
            given = area_ha is not None and area_ha != derived
            area = derived if area_ha is None else area_ha
            if not given and self.density.param is None:
                return area, None
            density = self.density.param or Param(self.density.value, f"{self.unit}/ha", None, Confidence.PLACEHOLDER)
            return area, area_param(area, given, density, self.unit)
        assert self.area is not None
        area = self.area.value if area_ha is None else area_ha
        param = self.area.param
        return area, user_or_default(param, area, lab["area_ha"]) if param else None

    def _pricing(self, agents: list, area: float) -> PricingConfig:
        assert self.pricing is not None
        spec = self.pricing
        config = dataclasses.replace(
            spec.config,
            anchors=[dataclasses.replace(a) for a in spec.config.anchors],
            scarcity_functions={k: dataclasses.replace(v) for k, v in spec.config.scarcity_functions.items()},
            default_scarcity=dataclasses.replace(spec.config.default_scarcity),
        )
        if spec.reference_area_ha is not None:
            from gaia.pricing import scale_anchors
            config = scale_anchors(config, area / spec.reference_area_ha)
        if spec.anchor_every_agent:
            from gaia.pricing import anchor_every_agent
            config = anchor_every_agent(config, agents, area)
        return config

    # ── Restoration ───────────────────────────────────────────────────────────

    def restoration_cost(
        self,
        planting_cost_per_unit: Optional[float] = None,
        annual_maintenance_per_unit: Optional[float] = None,
        maintenance_years: Optional[int] = None,
    ) -> RestorationCost:
        """The RestorationCost: the document's defaults unless overridden."""
        d = self.restoration_defaults()
        return RestorationCost(
            planting_cost_per_unit=d["planting_cost_per_unit"] if planting_cost_per_unit is None else planting_cost_per_unit,
            annual_maintenance_per_unit=(
                d["annual_maintenance_per_unit"] if annual_maintenance_per_unit is None
                else annual_maintenance_per_unit
            ),
            maintenance_years=d["maintenance_years"] if maintenance_years is None else maintenance_years,
        )

    def restoration_provenance(self, cost: RestorationCost, with_succession: bool) -> List[Param]:
        """Provenance of a restoration run: costs (user-supplied when they
        differ from the document's), the recovery curve and, with a
        maturation timeline, the succession curve."""
        flags = {
            "planting_cost_per_unit": "--planting-cost",
            "annual_maintenance_per_unit": "--maintenance-cost",
            "maintenance_years": "--maintenance-years",
        }
        out: List[Param] = []
        for key, q in (self.restoration or {}).items():
            if q.param is not None:
                out.append(user_or_default(q.param, getattr(cost, key), flags[key]))
        out.extend(self.recovery_params)
        if with_succession:
            out.extend(self.succession_params)
        return out

    def recovery_functions(self, ecosystem: Ecosystem) -> list:
        """One recovery function per agent (gaia.recovery), at the
        ecosystem's safe threshold."""
        curve = self.recovery or _Curve("logistic", (), None, "$.recovery")
        threshold = ecosystem.resource.safe_threshold_ratio
        return [_build_curve(curve, threshold, _RECOVERY_FACTORIES) for _ in ecosystem.agents]

    # ── Running ───────────────────────────────────────────────────────────────

    def run_extraction(self, units: Optional[int] = None, **overrides: Any):
        """run_extraction on the built ecosystem (``overrides``: the
        build_ecosystem arguments); ``units`` defaults to default_units."""
        from gaia.simulation import run_extraction

        ecosystem = self.build_ecosystem(**overrides)
        return run_extraction(ecosystem, self.default_units if units is None else units)

    def run_restoration(
        self,
        units: Optional[int] = None,
        units_lost: Optional[int] = None,
        time_horizon_years: int = 0,
        planting_cost_per_unit: Optional[float] = None,
        annual_maintenance_per_unit: Optional[float] = None,
        maintenance_years: Optional[int] = None,
        **overrides: Any,
    ):
        """run_restoration on the built ecosystem with the document's
        restoration defaults, recovery curve and (when
        ``time_horizon_years`` > 0) succession curve; the restoration
        provenance is added to the ecosystem's, as the CLI does."""
        from gaia.simulation import run_restoration

        ecosystem = self.build_ecosystem(**overrides)
        cost = self.restoration_cost(planting_cost_per_unit, annual_maintenance_per_unit, maintenance_years)
        ecosystem.provenance.extend(self.restoration_provenance(cost, time_horizon_years > 0))
        return run_restoration(
            ecosystem, self.default_units if units is None else units, cost,
            self.recovery_functions(ecosystem),
            succession_curve=self.succession_curve if time_horizon_years > 0 else None,
            time_horizon_years=time_horizon_years,
            units_lost=units_lost,
        )

    def report(self, result: Any) -> str:
        """The text report of a result of this case (with run.report_note)."""
        from gaia.report import format_report, format_restoration_report
        from gaia.models import RestorationResult

        if isinstance(result, RestorationResult):
            return format_restoration_report(result) + self.report_note
        return format_report(result) + self.report_note


def _discount_config(fields: Dict[str, Any]) -> DiscountConfig:
    schedule = fields.get("rate_schedule")
    if isinstance(schedule, list):
        fields = dict(fields, rate_schedule=list(schedule))
    return DiscountConfig(**fields)


def _override(q: Quantity, given: Any, label: str) -> Tuple[Any, Optional[Param]]:
    """(value, Param) of a resource parameter, ``given`` replacing the file's."""
    value = q.value if given is None else given
    if q.param is None:
        return value, None
    return value, user_or_default(q.param, value, label)


def _build_curve(curve: _Curve, threshold: float, factories: Dict[str, Tuple[Callable[..., Any], Tuple[str, ...]]]):
    factory, _ = factories[curve.kind]
    kwargs: Dict[str, Any] = dict(curve.params)
    if curve.kind != "linear":
        kwargs["threshold"] = threshold if curve.threshold is None else curve.threshold
    try:
        return factory(**kwargs)
    except ValueError as exc:
        raise ValueError(f"{curve.path}: {exc}") from None


# ── Parsing ───────────────────────────────────────────────────────────────────


def case_from_dict(data: Any, origin: str = "<dict>") -> Case:
    """Parse and validate a case document (see the module docstring).

    Raises:
        ValueError: Naming the JSON path of the first problem.
    """
    doc = _object(data, "$", ("gaia_schema", "name", "resource", "agents"), _TOP_LEVEL[1:])
    version = doc["gaia_schema"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(f"$.gaia_schema: expected an integer, got {_kind(version)}")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"$.gaia_schema: unsupported schema version {version} "
            f"(this Gaia reads version {SCHEMA_VERSION})"
        )
    name = _str(doc["name"], "$.name")
    description = _str(doc.get("description", ""), "$.description")

    regime_raw = doc.get("calibration_regime")
    regime = None
    if regime_raw is not None:
        valid = [r.value for r in CalibrationRegime]
        if regime_raw not in valid:
            raise ValueError(f"$.calibration_regime: expected one of {valid} or null, got {regime_raw!r}")
        regime = CalibrationRegime(regime_raw)

    reader = _Reader(_parse_provenance_defaults(doc.get("provenance_defaults", {})))
    buckets: Dict[str, List[Param]] = {b: [] for b in _BUCKETS}

    res = _parse_resource(doc["resource"], reader, name)
    curves = _parse_curves(doc.get("damage_curves", {}), reader, buckets["damage"])
    agents = _parse_agents(doc, reader, curves, buckets)
    names = [a.name for a in agents]
    interactions = _parse_interactions(doc.get("interactions", []), reader, set(names), buckets["edges"])

    carbon = resilience = substrate = discount = None
    if doc.get("carbon") is not None:
        obj = _object(doc["carbon"], "$.carbon", _CARBON_FIELDS)
        carbon = {k: reader.number(obj[k], _key("$.carbon", k), f"carbon.{k}", buckets["carbon"]) for k in _CARBON_FIELDS}
    if doc.get("resilience") is not None:
        obj = _object(doc["resilience"], "$.resilience", (), _RESILIENCE_FIELDS)
        resilience = {
            k: reader.number(obj[k], _key("$.resilience", k), f"resilience.{k}", buckets["resilience"])
            for k in _RESILIENCE_FIELDS if k in obj
        }
    if doc.get("substrate") is not None:
        substrate = _parse_substrate(doc["substrate"], reader, buckets["substrate"])
    if doc.get("discount") is not None:
        discount = _parse_discount(doc["discount"], reader, buckets["discount"])

    pricing = _parse_pricing(doc["pricing"], set(names)) if doc.get("pricing") is not None else None

    restoration = None
    if doc.get("restoration") is not None:
        obj = _object(doc["restoration"], "$.restoration", _RESTORATION_FIELDS)
        restoration = {
            k: reader.quantity(obj[k], _key("$.restoration", k), f"restoration.{k}",
                               integer=(k == "maintenance_years"))
            for k in _RESTORATION_FIELDS
        }
    recovery_params: List[Param] = []
    recovery = None
    if doc.get("recovery") is not None:
        recovery = _parse_curve(doc["recovery"], "$.recovery", reader, "recovery", recovery_params,
                                _RECOVERY_FACTORIES, prefix_type=True)
    succession_params: List[Param] = []
    succession = None
    if doc.get("succession") is not None:
        obj = _object(doc["succession"], "$.succession", _SUCCESSION_FIELDS)
        succession = {
            k: reader.number(obj[k], _key("$.succession", k), f"succession.{k}", succession_params)
            for k in _SUCCESSION_FIELDS
        }

    run = _object(doc.get("run", {}), "$.run", (), ("units", "report_note", "json_notes"))
    units = _plain_int(run["units"], "$.run.units") if "units" in run else None
    report_note = _str(run.get("report_note", ""), "$.run.report_note")
    notes = tuple(_str(n, f"$.run.json_notes[{i}]") for i, n in enumerate(_list(run.get("json_notes", []), "$.run.json_notes")))

    unused = sorted(set(reader.defaults) - reader.used)
    if unused:
        raise ValueError(
            f"$.provenance_defaults[{json.dumps(unused[0], ensure_ascii=False)}]: matches no parameter"
        )

    case = Case(
        name=name,
        description=description,
        origin=origin,
        resource_name=res["name"],
        unit=res["unit"],
        total_units=res["total_units"],
        unit_value=res["unit_value"],
        safe_threshold_ratio=res["safe_threshold_ratio"],
        area=res["area"],
        density=res["density"],
        calibration_regime=regime,
        agents=tuple(agents),
        interactions=tuple(interactions),
        buckets={k: tuple(v) for k, v in buckets.items()},
        carbon=carbon,
        resilience=resilience,
        substrate=substrate,
        discount=discount,
        pricing=pricing,
        restoration=restoration,
        recovery=recovery,
        recovery_params=tuple(recovery_params),
        succession=succession,
        succession_params=tuple(succession_params),
        units=units,
        report_note=report_note,
        json_notes=notes,
    )
    # A trial build checks what only building can: curve parameters at the
    # document's threshold, the area, the pricing block.
    case.recovery_functions(case.build_ecosystem(with_pricing=pricing is not None))
    return case


def _parse_provenance_defaults(raw: Any) -> Dict[str, Dict[str, Any]]:
    obj = _object(raw, "$.provenance_defaults", (), tuple(raw) if isinstance(raw, dict) else ())
    out: Dict[str, Dict[str, Any]] = {}
    for key, template in obj.items():
        path = f"$.provenance_defaults[{json.dumps(key, ensure_ascii=False)}]"
        tmpl = _object(template, path, ("unit", "confidence"), ("source", "note"))
        _make_param(0.0, tmpl, path, key)  # validates the template
        out[key] = tmpl
    return out


def _parse_resource(raw: Any, reader: _Reader, doc_name: str) -> Dict[str, Any]:
    path = "$.resource"
    obj = _object(
        raw, path, ("total_units", "unit_value", "safe_threshold_ratio"),
        ("name", "unit", "area_ha", "units_per_ha"),
    )
    unit = _str(obj.get("unit", "units"), _key(path, "unit"))
    total = reader.quantity(obj["total_units"], _key(path, "total_units"), "resource.total_units", integer=True)
    area = density = None
    if "area_ha" in obj:
        area = reader.quantity(obj["area_ha"], _key(path, "area_ha"), "resource.area_ha")
    if "units_per_ha" in obj:
        density = reader.quantity(obj["units_per_ha"], _key(path, "units_per_ha"), "resource.units_per_ha")
    if unit == "ha":
        if density is not None:
            raise ValueError(f"{path}.units_per_ha: not allowed with unit 'ha' (each unit is one hectare)")
        if area is not None and area.value != total.value:
            raise ValueError(
                f"{path}.area_ha: with unit 'ha' it must equal total_units "
                f"({area.value:g} != {total.value})"
            )
    elif (area is None) == (density is None):
        raise ValueError(f"{path}: give exactly one of area_ha and units_per_ha")
    for q, key in ((area, "area_ha"), (density, "units_per_ha")):
        if q is not None and q.value <= 0:
            raise ValueError(f"{_key(path, key)}: must be > 0, got {q.value}")
    return {
        "name": _str(obj.get("name", doc_name), _key(path, "name")),
        "unit": unit,
        "total_units": total,
        "unit_value": reader.quantity(obj["unit_value"], _key(path, "unit_value"), "resource.unit_value"),
        "safe_threshold_ratio": reader.quantity(
            obj["safe_threshold_ratio"], _key(path, "safe_threshold_ratio"), "resource.safe_threshold_ratio"
        ),
        "area": area,
        "density": density,
    }


def _parse_curve(
    raw: Any,
    path: str,
    reader: _Reader,
    prefix: str,
    bucket: List[Param],
    factories: Dict[str, Tuple[Callable[..., Any], Tuple[str, ...]]],
    prefix_type: bool = False,
) -> _Curve:
    """A curve object. Parameter names: ``<prefix>_<param>`` (named damage
    curves: prefix "damage.<curve>"), ``<prefix>.<type>_<param>``
    (recovery) or ``<prefix>.<param>`` (inline agent curves)."""
    if not isinstance(raw, dict) or "type" not in raw:
        raise ValueError(f"{path}: expected a curve object with a 'type' ({', '.join(factories)})")
    kind = raw["type"]
    if kind not in factories:
        raise ValueError(f"{_key(path, 'type')}: unknown curve type {kind!r} (expected one of {', '.join(factories)})")
    _, param_names = factories[kind]
    with_threshold = kind != "linear"
    obj = _object(raw, path, ("type",), (("threshold",) if with_threshold else ()) + param_names)

    def name_of(param: str) -> str:
        if prefix_type:
            return f"{prefix}.{kind}_{param}"
        if prefix.startswith("damage."):
            return f"{prefix}_{param}"
        return f"{prefix}.{param}"

    params = tuple(
        (p, reader.number(obj[p], _key(path, p), name_of(p), bucket)) for p in param_names if p in obj
    )
    threshold = None
    if "threshold" in obj:
        threshold = reader.number(obj["threshold"], _key(path, "threshold"), name_of("threshold"), bucket)
    return _Curve(kind, params, threshold, path)


def _parse_curves(raw: Any, reader: _Reader, bucket: List[Param]) -> Dict[str, _Curve]:
    obj = _object(raw, "$.damage_curves", (), tuple(raw) if isinstance(raw, dict) else ())
    return {
        name: _parse_curve(spec, _key("$.damage_curves", name), reader, f"damage.{name}", bucket, _DAMAGE_FACTORIES)
        for name, spec in obj.items()
    }


def _parse_agents(doc: dict, reader: _Reader, curves: Dict[str, _Curve], buckets: Dict[str, List[Param]]) -> List[_AgentSpec]:
    defaults = _object(doc.get("agent_defaults", {}), "$.agent_defaults", (), ("annual_value_per_ha", "damage"))
    default_value = None
    if "annual_value_per_ha" in defaults:
        default_value = reader.number(
            defaults["annual_value_per_ha"], "$.agent_defaults.annual_value_per_ha",
            "agents.annual_value_per_ha", buckets["agent_values"],
        )
    default_curve = None
    if "damage" in defaults:
        default_curve = _curve_ref(defaults["damage"], "$.agent_defaults.damage", curves)

    raw_agents = _list(doc["agents"], "$.agents")
    if not raw_agents:
        raise ValueError("$.agents: at least one agent is required")
    objs = []
    seen: set = set()
    for i, raw in enumerate(raw_agents):
        path = f"$.agents[{i}]"
        obj = _object(
            raw, path, ("name", "dependency_weight"),
            ("description", "annual_value_per_ha", "damage", "trophic_level", "is_keystone", "keystone_threshold"),
        )
        name = _str(obj["name"], _key(path, "name"))
        if name in seen:
            raise ValueError(f"{_key(path, 'name')}: duplicate agent name {name!r}")
        seen.add(name)
        objs.append((path, name, obj))

    # Parameters are read field by field across agents (the reporting order).
    values: Dict[str, float] = {}
    for path, name, obj in objs:
        if "annual_value_per_ha" in obj:
            values[name] = reader.number(
                obj["annual_value_per_ha"], _key(path, "annual_value_per_ha"),
                f"agent[{name}].annual_value_per_ha", buckets["agent_values"],
            )
        elif default_value is not None:
            values[name] = default_value
        else:
            raise ValueError(f"{_key(path, 'annual_value_per_ha')}: required (no agent_defaults value)")
    weights = {
        name: reader.number(obj["dependency_weight"], _key(path, "dependency_weight"),
                            f"agent[{name}].dependency_weight", buckets["agent_weights"])
        for path, name, obj in objs
    }
    agent_curves: Dict[str, _Curve] = {}
    for path, name, obj in objs:
        if "damage" in obj:
            raw_curve = obj["damage"]
            if isinstance(raw_curve, str):
                agent_curves[name] = _curve_ref(raw_curve, _key(path, "damage"), curves)
            else:
                agent_curves[name] = _parse_curve(
                    raw_curve, _key(path, "damage"), reader, f"agent[{name}].damage",
                    buckets["damage"], _DAMAGE_FACTORIES,
                )
        elif default_curve is not None:
            agent_curves[name] = default_curve
        else:
            raise ValueError(f"{_key(path, 'damage')}: required (no agent_defaults damage curve)")
    keystone: Dict[str, float] = {}
    for path, name, obj in objs:
        keystone[name] = (
            reader.number(obj["keystone_threshold"], _key(path, "keystone_threshold"),
                          f"agent[{name}].keystone_threshold", buckets["keystone"])
            if "keystone_threshold" in obj else DEFAULT_KEYSTONE_THRESHOLD
        )
    return [
        _AgentSpec(
            name=name,
            description=_str(obj.get("description", ""), _key(path, "description")),
            weight=weights[name],
            value=values[name],
            curve=agent_curves[name],
            trophic_level=_plain_int(obj.get("trophic_level", -1), _key(path, "trophic_level")),
            is_keystone=_bool(obj.get("is_keystone", False), _key(path, "is_keystone")),
            keystone_threshold=keystone[name],
        )
        for path, name, obj in objs
    ]


def _curve_ref(raw: Any, path: str, curves: Dict[str, _Curve]) -> _Curve:
    name = _str(raw, path)
    if name not in curves:
        defined = ", ".join(curves) or "none"
        raise ValueError(f"{path}: unknown damage curve {name!r} (defined: {defined})")
    return curves[name]


def _parse_interactions(raw: Any, reader: _Reader, names: set, bucket: List[Param]) -> List[Tuple[str, str, float, str, str]]:
    out = []
    for i, item in enumerate(_list(raw, "$.interactions")):
        path = f"$.interactions[{i}]"
        obj = _object(item, path, ("source", "target", "strength"), ("type", "description"))
        ends = []
        for end in ("source", "target"):
            agent = _str(obj[end], _key(path, end))
            if agent not in names:
                raise ValueError(f"{_key(path, end)}: unknown agent {agent!r}")
            ends.append(agent)
        strength = reader.number(obj["strength"], _key(path, "strength"), f"edge[{ends[0]} → {ends[1]}].strength", bucket)
        out.append((
            ends[0], ends[1], strength,
            _str(obj.get("type", "dependency"), _key(path, "type")),
            _str(obj.get("description", ""), _key(path, "description")),
        ))
    return out


def _parse_substrate(raw: Any, reader: _Reader, bucket: List[Param]) -> Dict[str, Any]:
    path = "$.substrate"
    obj = _object(raw, path, ("substrate_type",), _SUBSTRATE_STRINGS[1:] + _SUBSTRATE_NUMBERS)
    out: Dict[str, Any] = {k: _str(obj[k], _key(path, k)) for k in _SUBSTRATE_STRINGS if k in obj}
    for k in _SUBSTRATE_NUMBERS:
        if k in obj and obj[k] is not None:
            out[k] = reader.number(obj[k], _key(path, k), f"substrate.{k}", bucket)
    # Keyword order of SubstrateProfile does not matter; field order does
    # not either (Params are already collected in the document's order).
    return out


def _parse_discount(raw: Any, reader: _Reader, bucket: List[Param]) -> Dict[str, Any]:
    path = "$.discount"
    numbers = ("delta", "eta", "g")
    obj = _object(
        raw, path, (),
        ("profile",) + numbers + ("rate_schedule", "scarcity_rate", "horizon_years",
                                  "carbon_price_current", "carbon_price_growth"),
    )
    out: Dict[str, Any] = {}
    if "profile" in obj:
        profile = _str(obj["profile"], _key(path, "profile"))
        if profile not in _DISCOUNT_PROFILES:
            raise ValueError(f"{_key(path, 'profile')}: unknown profile {profile!r} (expected one of {', '.join(_DISCOUNT_PROFILES)})")
        from gaia import discount as discount_module
        base = getattr(discount_module, f"DISCOUNT_{profile.upper()}")
        out = {f.name: getattr(base, f.name) for f in dataclasses.fields(base)}
    for k in numbers:
        if k in obj:
            out[k] = reader.number(obj[k], _key(path, k), f"discount.{k}", bucket)
    if "rate_schedule" in obj:
        schedule = obj["rate_schedule"]
        if isinstance(schedule, list):
            entries = []
            for i, item in enumerate(schedule):
                ipath = f"{path}.rate_schedule[{i}]"
                entry = _object(item, ipath, ("from_year", "rate"))
                year = _plain_int(entry["from_year"], _key(ipath, "from_year"))
                rate = reader.number(entry["rate"], _key(ipath, "rate"), f"discount.rate_schedule[year {year}]", bucket)
                entries.append((year, rate))
            if not entries:
                raise ValueError(f"{path}.rate_schedule: an empty schedule")
            out["rate_schedule"] = entries
        else:
            out["rate_schedule"] = reader.number(schedule, _key(path, "rate_schedule"), "discount.rate_schedule", bucket)
    elif "profile" not in obj:
        out["rate_schedule"] = None
    if "scarcity_rate" in obj:
        out["scarcity_rate"] = reader.number(obj["scarcity_rate"], _key(path, "scarcity_rate"), "discount.scarcity_rate", bucket)
    if "horizon_years" in obj:
        out["horizon_years"] = reader.number(
            obj["horizon_years"], _key(path, "horizon_years"), "discount.horizon_years", bucket, integer=True,
        )
    for k in ("carbon_price_current", "carbon_price_growth"):
        if k in obj:
            out[k] = reader.number(obj[k], _key(path, k), f"discount.{k}", bucket)
    return out


def _parse_scarcity(raw: Any, path: str) -> ScarcityFunction:
    obj = _object(raw, path, ("type",), ("alpha", "threshold", "max_multiplier", "description"))
    kwargs: Dict[str, Any] = {"function_type": _str(obj["type"], _key(path, "type"))}
    for k in ("alpha", "threshold", "max_multiplier"):
        if k in obj:
            kwargs[k] = float(_plain_number(obj[k], _key(path, k)))
    if "description" in obj:
        kwargs["description"] = _str(obj["description"], _key(path, "description"))
    return ScarcityFunction(**kwargs)


def _parse_pricing(raw: Any, names: set) -> _PricingSpec:
    path = "$.pricing"
    obj = _object(
        raw, path, ("anchors",),
        ("enabled", "reference_area_ha", "anchor_every_agent", "scarcity_functions",
         "default_scarcity", "convergence_tolerance", "max_iterations"),
    )
    anchors = []
    for i, item in enumerate(_list(obj["anchors"], _key(path, "anchors"))):
        ipath = f"{path}.anchors[{i}]"
        a = _object(item, ipath, ("agent_name", "anchor_value", "source", "confidence"), ("description",))
        agent = _str(a["agent_name"], _key(ipath, "agent_name"))
        if agent not in names:
            raise ValueError(f"{_key(ipath, 'agent_name')}: unknown agent {agent!r}")
        anchors.append(AnchorPoint(
            agent_name=agent,
            anchor_value=float(_plain_number(a["anchor_value"], _key(ipath, "anchor_value"))),
            source=_str(a["source"], _key(ipath, "source")),
            confidence=_str(a["confidence"], _key(ipath, "confidence")),
            description=_str(a.get("description", ""), _key(ipath, "description")),
        ))
    scarcity = {}
    raw_sf = obj.get("scarcity_functions", {})
    sf_obj = _object(raw_sf, _key(path, "scarcity_functions"), (), tuple(raw_sf) if isinstance(raw_sf, dict) else ())
    for agent, spec in sf_obj.items():
        spath = _key(_key(path, "scarcity_functions"), agent)
        if agent not in names:
            raise ValueError(f"{spath}: unknown agent {agent!r}")
        scarcity[agent] = _parse_scarcity(spec, spath)
    kwargs: Dict[str, Any] = {"anchors": anchors, "scarcity_functions": scarcity}
    if "default_scarcity" in obj:
        kwargs["default_scarcity"] = _parse_scarcity(obj["default_scarcity"], _key(path, "default_scarcity"))
    if "convergence_tolerance" in obj:
        kwargs["convergence_tolerance"] = float(_plain_number(obj["convergence_tolerance"], _key(path, "convergence_tolerance")))
    if "max_iterations" in obj:
        kwargs["max_iterations"] = _plain_int(obj["max_iterations"], _key(path, "max_iterations"))
    reference = None
    if "reference_area_ha" in obj:
        reference = float(_plain_number(obj["reference_area_ha"], _key(path, "reference_area_ha")))
        if reference <= 0:
            raise ValueError(f"{path}.reference_area_ha: must be > 0, got {reference}")
    return _PricingSpec(
        config=PricingConfig(**kwargs),
        enabled=_bool(obj.get("enabled", False), _key(path, "enabled")),
        reference_area_ha=reference,
        anchor_every_agent=_bool(obj.get("anchor_every_agent", True), _key(path, "anchor_every_agent")),
    )


# ── Loading and saving ────────────────────────────────────────────────────────


def _no_duplicates(pairs: List[Tuple[str, Any]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed (strict JSON: numbers must be finite)")


def read_json(path: Union[str, Path]) -> Any:
    """Strict JSON from ``path``: no duplicate keys, no NaN/Infinity.

    Raises:
        ValueError: Prefixed with the path (json.JSONDecodeError is one).
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None


def load_case_file(path: Union[str, Path]) -> Case:
    """Parse the case document at ``path``.

    Raises:
        ValueError: Prefixed with the path.
    """
    data = read_json(path)
    try:
        return case_from_dict(data, origin=str(path))
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None


def ecosystem_from_dict(
    data: Any,
    with_pricing: Optional[bool] = None,
    validate: bool = True,
) -> Ecosystem:
    """Build an Ecosystem from a document (see the module docstring).

    Args:
        data: The parsed JSON document.
        with_pricing: Attach the EXPERIMENTAL pricing block (default: its
            "enabled" flag).
        validate: Also run gaia.validation.validate_ecosystem
            (CalibrationWarning is left to the simulation run).

    Raises:
        ValueError: Naming the JSON path of the first problem, or from
            validate_ecosystem.
    """
    eco = case_from_dict(data).build_ecosystem(with_pricing=with_pricing)
    if validate:
        _validate(eco)
    return eco


def _validate(eco: Ecosystem) -> None:
    from gaia.validation import CalibrationWarning, validate_ecosystem

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", CalibrationWarning)
        validate_ecosystem(eco)


def load_ecosystem(path: Union[str, Path], with_pricing: Optional[bool] = None) -> Ecosystem:
    """The validated Ecosystem of the document at ``path``.

    Raises:
        ValueError: Prefixed with the path.
    """
    data = read_json(path)
    try:
        return ecosystem_from_dict(data, with_pricing=with_pricing)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None


def dumps(data: Any) -> str:
    """The document as text: 2-space indent, UTF-8 kept, strict numbers."""
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def save_ecosystem(ecosystem: Ecosystem, path: Union[str, Path]) -> None:
    """Write ``ecosystem_to_dict(ecosystem)`` to ``path``."""
    Path(path).write_text(dumps(ecosystem_to_dict(ecosystem)), encoding="utf-8")


# ── Writing ───────────────────────────────────────────────────────────────────


def _param_obj(p: Param, integer: bool = False) -> Dict[str, Any]:
    value: Any = int(p.value) if integer and p.value == int(p.value) else p.value
    out: Dict[str, Any] = {"value": value, "unit": p.unit}
    if p.source is not None:
        out["source"] = p.source
    out["confidence"] = p.confidence.value
    if p.note:
        out["note"] = p.note
    return out


def _metadata(p: Param) -> Tuple[str, Optional[str], str, str]:
    return (p.unit, p.source, p.confidence.value, p.note)


def _template(meta: Tuple[str, Optional[str], str, str]) -> Dict[str, Any]:
    unit, source, confidence, note = meta
    out: Dict[str, Any] = {"unit": unit}
    if source is not None:
        out["source"] = source
    out["confidence"] = confidence
    if note:
        out["note"] = note
    return out


def _curve_spec(fn: Any, agent: str) -> Tuple[str, Tuple[Tuple[str, float], ...], float]:
    """(type, params, threshold) of a gaia.damage factory function."""
    kernel = getattr(fn, "kernel", None)
    threshold = getattr(fn, "threshold", None)
    if kernel is None or threshold is None:
        raise ValueError(
            f"agent {agent!r}: its damage function is not from gaia.damage, so it "
            f"cannot be written to a file"
        )
    kind = kernel[0]
    if kind == KERNEL_LOGISTIC:
        spec: Tuple[str, Tuple[Tuple[str, float], ...]] = ("logistic", (("steepness", kernel[4]),))
    elif kind == KERNEL_EXPONENTIAL:
        spec = ("exponential", (("base", kernel[3]),))
    elif kind == KERNEL_PIECEWISE:
        spec = ("piecewise", (("pre_slope_ratio", kernel[4]),))
    else:
        raise ValueError(f"agent {agent!r}: unknown damage kernel {kind!r}")
    rebuilt = _DAMAGE_FACTORIES[spec[0]][0](threshold=threshold, **dict(spec[1]))
    if tuple(rebuilt.kernel) != tuple(kernel):
        raise ValueError(f"agent {agent!r}: its damage function cannot be rebuilt exactly")
    return spec[0], spec[1], threshold


def ecosystem_to_dict(ecosystem: Ecosystem) -> Dict[str, Any]:
    """The canonical document of ``ecosystem`` (schema 1).

    ``ecosystem_from_dict`` of the result gives an ecosystem with the same
    results and provenance (re-collected in the documented order). Agents
    sharing a damage curve share a named curve; provenance shared by most
    agent weights, keystone thresholds or edges goes to provenance_defaults.
    Restoration and run defaults are not part of an Ecosystem, so they are
    not written; pricing is written only when attached (enabled, anchors
    as attached). The carbon price is written only when it is not the
    social cost of carbon default.

    Raises:
        ValueError: For a damage function not built by gaia.damage, or a
            provenance parameter that has no place in the document (e.g.
            restoration parameters added for a run).
    """
    from gaia.carbon import SCC_GROWTH_RATE, SOCIAL_COST_OF_CARBON_EUR

    resource = ecosystem.resource
    params: Dict[str, Param] = {}
    for p in ecosystem.provenance:
        if p.name.startswith("pricing."):
            continue  # regenerated from the anchors
        if p.name in params:
            raise ValueError(f"duplicate provenance parameter {p.name!r}")
        params[p.name] = p
    placed: set = set()

    def num(value: Any, name: str, integer: bool = False) -> Any:
        p = params.get(name)
        if p is None:
            return value
        if float(p.value) != float(value):
            raise ValueError(f"provenance parameter {name!r} is {p.value}, but the field is {value}")
        placed.add(name)
        return _param_obj(p, integer)

    doc: Dict[str, Any] = {"gaia_schema": SCHEMA_VERSION, "name": ecosystem.name}
    regime = ecosystem.calibration_regime
    doc["calibration_regime"] = None if regime is None else CalibrationRegime(regime).value
    res: Dict[str, Any] = {}
    if resource.name != ecosystem.name:
        res["name"] = resource.name
    res["total_units"] = num(resource.total_units, "resource.total_units", integer=True)
    res["area_ha"] = num(resource.area_ha, "resource.area_ha")
    res["unit_value"] = num(resource.unit_value, "resource.unit_value")
    res["safe_threshold_ratio"] = num(resource.safe_threshold_ratio, "resource.safe_threshold_ratio")
    doc["resource"] = res

    agents = ecosystem.agents
    # provenance_defaults for list fields (most common metadata, >= 2 uses)
    pattern_fields = {
        "agent[*].annual_value_per_ha": [f"agent[{a.name}].annual_value_per_ha" for a in agents],
        "agent[*].dependency_weight": [f"agent[{a.name}].dependency_weight" for a in agents],
        "agent[*].keystone_threshold": [
            f"agent[{a.name}].keystone_threshold" for a in agents
            if a.is_keystone or a.keystone_threshold != DEFAULT_KEYSTONE_THRESHOLD
            or f"agent[{a.name}].keystone_threshold" in params
        ],
        "edge[*].strength": [f"edge[{e.source} → {e.target}].strength" for e in ecosystem.interactions],
    }
    shared_value = params.get("agents.annual_value_per_ha")
    if shared_value is None:
        values = {a.annual_value_per_ha for a in agents}
        own = any(f"agent[{a.name}].annual_value_per_ha" in params for a in agents)
        shared_raw: Optional[float] = values.pop() if len(values) == 1 and not own else None
    else:
        shared_raw = shared_value.value
    if shared_raw is not None:
        pattern_fields["agent[*].annual_value_per_ha"] = [
            f"agent[{a.name}].annual_value_per_ha" for a in agents if a.annual_value_per_ha != shared_raw
        ]
    templates: Dict[str, Tuple[str, Optional[str], str, str]] = {}
    for pattern, names in pattern_fields.items():
        if not names or any(n not in params for n in names):
            continue
        meta, count = Counter(_metadata(params[n]) for n in names).most_common(1)[0]
        if count >= 2:
            templates[pattern] = meta

    def listed(value: Any, name: str) -> Any:
        """A list-field number: bare when its Param matches the template."""
        p = params.get(name)
        pattern = _BRACKETS.sub("[*]", name)
        if p is not None and pattern in templates and _metadata(p) == templates[pattern]:
            if float(p.value) != float(value):
                raise ValueError(f"provenance parameter {name!r} is {p.value}, but the field is {value}")
            placed.add(name)
            return value
        return num(value, name)

    if templates:
        doc["provenance_defaults"] = {k: _template(v) for k, v in templates.items()}

    # Damage curves: one named curve per distinct (type, params, threshold).
    specs = [_curve_spec(a.damage_function, a.name) for a in agents]
    inline = {a.name for a in agents if any(n.startswith(f"agent[{a.name}].damage.") for n in params)}
    distinct: List[tuple] = []
    for a, spec in zip(agents, specs):
        if a.name not in inline and spec not in distinct:
            distinct.append(spec)

    def matches_named(spec: tuple) -> bool:
        kind, cparams, _ = spec
        found = [params[f"damage.{kind}_{p}"].value == v for p, v in cparams if f"damage.{kind}_{p}" in params]
        return bool(found) and all(found)

    # Each type's first curve is named after the type ("logistic"), others
    # "<type>_2", ...; a curve whose values match "damage.<type>_*" Params
    # takes the bare name.
    curve_names: Dict[tuple, str] = {}
    for kind in dict.fromkeys(spec[0] for spec in distinct):
        of_kind = [spec for spec in distinct if spec[0] == kind]
        preferred = next((spec for spec in of_kind if matches_named(spec)), of_kind[0])
        others = [spec for spec in of_kind if spec != preferred]
        curve_names[preferred] = kind
        for n, spec in enumerate(others, start=2):
            curve_names[spec] = f"{kind}_{n}"
    curves: Dict[str, Dict[str, Any]] = {}
    for spec in distinct:
        kind, cparams, threshold = spec
        name = curve_names[spec]
        curve: Dict[str, Any] = {"type": kind}
        if threshold != resource.safe_threshold_ratio:
            curve["threshold"] = num(threshold, f"damage.{name}_threshold")
        for pname, pvalue in cparams:
            curve[pname] = num(pvalue, f"damage.{name}_{pname}")
        curves[name] = curve

    agent_defaults: Dict[str, Any] = {}
    if shared_raw is not None:
        agent_defaults["annual_value_per_ha"] = num(shared_raw, "agents.annual_value_per_ha")
    usage = Counter(curve_names[s] for a, s in zip(agents, specs) if a.name not in inline)
    default_curve = usage.most_common(1)[0][0] if usage else None
    if default_curve is not None and usage[default_curve] >= 2:
        agent_defaults["damage"] = default_curve
    else:
        default_curve = None
    if agent_defaults:
        doc["agent_defaults"] = agent_defaults
    if curves:
        doc["damage_curves"] = curves

    out_agents = []
    for a, (kind, cparams, threshold) in zip(agents, specs):
        item: Dict[str, Any] = {"name": a.name, "description": a.description}
        item["dependency_weight"] = listed(a.dependency_weight, f"agent[{a.name}].dependency_weight")
        if shared_raw is None or a.annual_value_per_ha != shared_raw:
            item["annual_value_per_ha"] = listed(a.annual_value_per_ha, f"agent[{a.name}].annual_value_per_ha")
        if a.name in inline:
            curve = {"type": kind}
            if threshold != resource.safe_threshold_ratio or f"agent[{a.name}].damage.threshold" in params:
                curve["threshold"] = num(threshold, f"agent[{a.name}].damage.threshold")
            for pname, pvalue in cparams:
                curve[pname] = num(pvalue, f"agent[{a.name}].damage.{pname}")
            item["damage"] = curve
        elif curve_names[(kind, cparams, threshold)] != default_curve:
            item["damage"] = curve_names[(kind, cparams, threshold)]
        item["trophic_level"] = a.trophic_level
        if a.is_keystone:
            item["is_keystone"] = True
        kname = f"agent[{a.name}].keystone_threshold"
        if kname in pattern_fields["agent[*].keystone_threshold"]:
            item["keystone_threshold"] = listed(a.keystone_threshold, kname)
        out_agents.append(item)
    doc["agents"] = out_agents
    if ecosystem.interactions:
        doc["interactions"] = [
            {
                "source": e.source,
                "target": e.target,
                "strength": listed(e.strength, f"edge[{e.source} → {e.target}].strength"),
                "type": e.interaction_type,
                "description": e.description,
            }
            for e in ecosystem.interactions
        ]

    if resource.carbon_profile is not None:
        cp = resource.carbon_profile
        doc["carbon"] = {k: num(getattr(cp, k), f"carbon.{k}") for k in _CARBON_FIELDS}
    if resource.resilience is not None:
        rc = resource.resilience
        doc["resilience"] = {k: num(getattr(rc, k), f"resilience.{k}") for k in _RESILIENCE_FIELDS}
    if resource.substrate is not None:
        sp = resource.substrate
        sub: Dict[str, Any] = {k: str(getattr(sp, k)) for k in _SUBSTRATE_STRINGS}
        for k in _SUBSTRATE_NUMBERS:
            value = getattr(sp, k)
            if value is not None:
                sub[k] = num(value, f"substrate.{k}")
        doc["substrate"] = sub
    if resource.discount is not None:
        dc = resource.discount
        disc: Dict[str, Any] = {k: num(getattr(dc, k), f"discount.{k}") for k in ("delta", "eta", "g")}
        if isinstance(dc.rate_schedule, (int, float)):
            disc["rate_schedule"] = num(dc.rate_schedule, "discount.rate_schedule")
        else:
            disc["rate_schedule"] = [
                {"from_year": year, "rate": num(rate, f"discount.rate_schedule[year {year}]")}
                for year, rate in dc.rate_schedule
            ]
        disc["scarcity_rate"] = num(dc.scarcity_rate, "discount.scarcity_rate")
        disc["horizon_years"] = num(dc.horizon_years, "discount.horizon_years", integer=True)
        if dc.carbon_price_current != SOCIAL_COST_OF_CARBON_EUR or "discount.carbon_price_current" in params:
            disc["carbon_price_current"] = num(dc.carbon_price_current, "discount.carbon_price_current")
        if dc.carbon_price_growth != SCC_GROWTH_RATE or "discount.carbon_price_growth" in params:
            disc["carbon_price_growth"] = num(dc.carbon_price_growth, "discount.carbon_price_growth")
        doc["discount"] = disc
    if ecosystem.pricing is not None:
        doc["pricing"] = _pricing_to_dict(ecosystem.pricing)

    unplaced = [n for n in params if n not in placed]
    if unplaced:
        raise ValueError(
            f"provenance parameter {unplaced[0]!r} has no place in an ecosystem document"
        )
    return doc


def _scarcity_to_dict(sf: ScarcityFunction) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "type": sf.function_type, "alpha": sf.alpha, "threshold": sf.threshold,
        "max_multiplier": sf.max_multiplier,
    }
    if sf.description:
        out["description"] = sf.description
    return out


def _pricing_to_dict(pricing: PricingConfig) -> Dict[str, Any]:
    return {
        "enabled": True,
        "anchor_every_agent": False,
        "anchors": [
            {
                "agent_name": a.agent_name,
                "anchor_value": a.anchor_value,
                "source": a.source,
                "confidence": a.confidence,
                "description": a.description,
            }
            for a in pricing.anchors
        ],
        "scarcity_functions": {k: _scarcity_to_dict(v) for k, v in pricing.scarcity_functions.items()},
        "default_scarcity": _scarcity_to_dict(pricing.default_scarcity),
        "convergence_tolerance": pricing.convergence_tolerance,
        "max_iterations": pricing.max_iterations,
    }
