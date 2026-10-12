"""
Gaia v0.1 — Input validation tests.

Verifies that validation raises descriptive errors on bad inputs and
passes cleanly on valid inputs. Validation failures must never silently default.
"""

import dataclasses

import pytest
from gaia.cases import forest as forest_case
from gaia.damage import logistic_damage
from gaia.models import (
    Agent,
    DiscountConfig,
    Ecosystem,
    InteractionEdge,
    Resource,
    RestorationCost,
)
from gaia.recovery import logistic_recovery
from gaia.simulation import run_extraction, run_restoration
from gaia.validation import (
    validate_damage_function,
    validate_discount_config,
    validate_ecosystem,
    validate_extraction,
    validate_resource,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resource(**kwargs) -> Resource:
    defaults = dict(
        name="Forest",
        area_ha=100.0,
        total_units=10_000,
        safe_threshold_ratio=0.3,
        unit_value=100.0,
    )
    defaults.update(kwargs)
    return Resource(**defaults)


def _agent(weight: float = 1.0) -> Agent:
    return Agent(
        name="Agent",
        dependency_weight=weight,
        damage_function=logistic_damage(threshold=0.3),
        annual_value_per_ha=100_000.0,
        description="Test agent",
    )


def _ecosystem(weights: list = None) -> Ecosystem:
    if weights is None:
        weights = [0.5, 0.5]
    agents = [_agent(w) for w in weights]
    return Ecosystem(
        name="Test Eco",
        resource=_resource(),
        agents=agents,
    )


# ── Resource validation ────────────────────────────────────────────────────────

def test_valid_resource_passes():
    """Valid resource should not raise."""
    validate_resource(_resource())


def test_reject_zero_total_units():
    """total_units=0 must be rejected."""
    with pytest.raises(ValueError, match="total_units"):
        validate_resource(_resource(total_units=0))


def test_reject_negative_total_units():
    """total_units=-1 must be rejected."""
    with pytest.raises(ValueError, match="total_units"):
        validate_resource(_resource(total_units=-1))


@pytest.mark.parametrize("area", [0.0, -5.0, float("inf"), float("nan"), None])
def test_reject_invalid_area_ha(area):
    """area_ha must be a finite number of hectares > 0 (decision D2)."""
    with pytest.raises(ValueError, match="area_ha"):
        validate_resource(_resource(area_ha=area))


def test_resource_requires_area_ha():
    """area_ha has no default: every resource states its area."""
    with pytest.raises(TypeError, match="area_ha"):
        Resource(name="F", total_units=10, safe_threshold_ratio=0.3, unit_value=1.0)


def test_reject_threshold_zero():
    """safe_threshold_ratio=0.0 must be rejected (exclusive lower bound)."""
    with pytest.raises(ValueError, match="safe_threshold_ratio"):
        validate_resource(_resource(safe_threshold_ratio=0.0))


def test_reject_threshold_one():
    """safe_threshold_ratio=1.0 must be rejected (exclusive upper bound)."""
    with pytest.raises(ValueError, match="safe_threshold_ratio"):
        validate_resource(_resource(safe_threshold_ratio=1.0))


def test_reject_threshold_above_one():
    """safe_threshold_ratio=1.5 must be rejected."""
    with pytest.raises(ValueError, match="safe_threshold_ratio"):
        validate_resource(_resource(safe_threshold_ratio=1.5))


def test_reject_negative_unit_value():
    """unit_value=-10 must be rejected."""
    with pytest.raises(ValueError, match="unit_value"):
        validate_resource(_resource(unit_value=-10.0))


def test_zero_unit_value_is_valid():
    """unit_value=0.0 is allowed (public/commons resource with no private revenue)."""
    validate_resource(_resource(unit_value=0.0))


# ── Ecosystem validation ───────────────────────────────────────────────────────

def test_valid_ecosystem_passes():
    """Valid ecosystem should not raise."""
    validate_ecosystem(_ecosystem([0.5, 0.5]))


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_reject_invalid_agent_annual_value(value):
    """Agent annual values must be finite and >= 0 (€/yr at full damage)."""
    eco = _ecosystem([1.0])
    eco.agents[0].annual_value_per_ha = value
    with pytest.raises(ValueError, match="annual_value_per_ha"):
        validate_ecosystem(eco)


def test_reject_weights_not_summing_to_one():
    """Agents with weights summing to 0.8 must be rejected."""
    with pytest.raises(ValueError, match="sum"):
        eco = _ecosystem([0.4, 0.4])  # sum = 0.8
        validate_ecosystem(eco)


def test_reject_weights_over_one():
    """Agents with weights summing to 1.2 must be rejected."""
    with pytest.raises(ValueError, match="sum"):
        eco = _ecosystem([0.6, 0.6])  # sum = 1.2
        validate_ecosystem(eco)


def test_single_agent_weight_one_passes():
    """Single agent with weight 1.0 should pass."""
    eco = Ecosystem(
        name="Eco",
        resource=_resource(),
        agents=[_agent(1.0)],
    )
    validate_ecosystem(eco)


def test_reject_empty_agents():
    """Ecosystem with no agents must be rejected."""
    eco = Ecosystem(name="Eco", resource=_resource(), agents=[])
    with pytest.raises(ValueError, match="agent"):
        validate_ecosystem(eco)


# ── Extraction validation ──────────────────────────────────────────────────────

def test_valid_extraction_passes():
    """Extracting a valid amount should not raise."""
    eco = _ecosystem()
    validate_extraction(eco, 5_000)


def test_zero_extraction_passes():
    """Extracting 0 units is valid."""
    eco = _ecosystem()
    validate_extraction(eco, 0)


def test_reject_extract_more_than_total():
    """Extracting 15,000 from 10,000 must be rejected."""
    eco = _ecosystem()
    with pytest.raises(ValueError, match="exceed"):
        validate_extraction(eco, 15_000)


def test_reject_negative_extraction():
    """Extracting -100 units must be rejected."""
    eco = _ecosystem()
    with pytest.raises(ValueError, match="0"):
        validate_extraction(eco, -100)


def test_extract_exactly_total_passes():
    """Extracting exactly total_units is allowed (edge case)."""
    eco = _ecosystem()
    validate_extraction(eco, 10_000)


# ── Damage function validation ─────────────────────────────────────────────────

def test_valid_damage_function_passes():
    """A valid logistic damage function should pass."""
    fn = logistic_damage(threshold=0.3)
    validate_damage_function(fn)


def test_reject_bad_damage_function_above_one():
    """A damage function that returns > 1.0 must be rejected."""
    def bad_fn(x: float) -> float:
        return x * 2.0  # returns values > 1.0 for x > 0.5

    with pytest.raises(ValueError):
        validate_damage_function(bad_fn, name="bad_fn")


def test_reject_non_monotone_damage_function():
    """A damage function that decreases must be rejected."""
    def decreasing_fn(x: float) -> float:
        return 1.0 - x  # monotonically decreasing

    with pytest.raises(ValueError):
        validate_damage_function(decreasing_fn, name="decreasing_fn")


def test_reject_damage_function_wrong_at_zero():
    """A damage function where f(0) != 0 must be rejected."""
    def starts_at_half(x: float) -> float:
        return 0.5 + x * 0.5  # f(0) = 0.5, f(1) = 1.0

    with pytest.raises(ValueError, match="0.0"):
        validate_damage_function(starts_at_half, name="starts_at_half")


# ── v0.3: Trophic level validation ───────────────────────────────────────────

def test_reject_invalid_trophic_level():
    """trophic_level=5 must be rejected."""
    agent = Agent(
        name="A",
        dependency_weight=1.0,
        damage_function=logistic_damage(threshold=0.3),
        annual_value_per_ha=1.0,
        description="",
        trophic_level=5,
    )
    eco = Ecosystem(name="E", resource=_resource(), agents=[agent])
    with pytest.raises(ValueError, match="trophic_level"):
        validate_ecosystem(eco)


def test_reject_invalid_keystone_threshold():
    """Keystone agent with threshold=0.0 must be rejected."""
    agent = Agent(
        name="A",
        dependency_weight=1.0,
        damage_function=logistic_damage(threshold=0.3),
        annual_value_per_ha=1.0,
        description="",
        is_keystone=True,
        keystone_threshold=0.0,
    )
    eco = Ecosystem(name="E", resource=_resource(), agents=[agent])
    with pytest.raises(ValueError, match="keystone_threshold"):
        validate_ecosystem(eco)


# ── v0.3: Interaction edge validation ─────────────────────────────────────────

def test_reject_edge_self_loop():
    """An edge with source == target must be rejected."""
    edge = InteractionEdge("Agent", "Agent", 0.3, "dependency", "self")
    eco = Ecosystem(
        name="E",
        resource=_resource(),
        agents=[_agent(1.0)],
        interactions=[edge],
    )
    with pytest.raises(ValueError, match="self-loop"):
        validate_ecosystem(eco)


def test_reject_edge_missing_source():
    """Edge with a source not in the ecosystem must be rejected."""
    edge = InteractionEdge("NonExistent", "Agent", 0.3, "dependency", "x")
    eco = Ecosystem(
        name="E",
        resource=_resource(),
        agents=[_agent(1.0)],
        interactions=[edge],
    )
    with pytest.raises(ValueError, match="source"):
        validate_ecosystem(eco)


def test_reject_edge_bad_strength():
    """Edge with strength=0 must be rejected."""
    agents = [_agent(0.5), _agent(0.5)]
    agents[0] = Agent(
        name="A", dependency_weight=0.5,
        damage_function=logistic_damage(0.3),
        annual_value_per_ha=1.0, description="",
    )
    agents[1] = Agent(
        name="B", dependency_weight=0.5,
        damage_function=logistic_damage(0.3),
        annual_value_per_ha=1.0, description="",
    )
    edge = InteractionEdge("A", "B", 0.0, "dependency", "bad")
    eco = Ecosystem(
        name="E",
        resource=_resource(),
        agents=agents,
        interactions=[edge],
    )
    with pytest.raises(ValueError, match="strength"):
        validate_ecosystem(eco)


def test_reject_edge_bad_interaction_type():
    """Edge with invalid interaction_type must be rejected."""
    agents = [
        Agent(name="A", dependency_weight=0.5,
              damage_function=logistic_damage(0.3),
              annual_value_per_ha=1.0, description=""),
        Agent(name="B", dependency_weight=0.5,
              damage_function=logistic_damage(0.3),
              annual_value_per_ha=1.0, description=""),
    ]
    edge = InteractionEdge("A", "B", 0.3, "invalid_type", "bad")
    eco = Ecosystem(
        name="E", resource=_resource(), agents=agents,
        interactions=[edge],
    )
    with pytest.raises(ValueError, match="interaction_type"):
        validate_ecosystem(eco)


# ── DiscountConfig convergence (C3) ────────────────────────────────────────────

def _discount(**kwargs) -> DiscountConfig:
    defaults = dict(rate_schedule=0.03, scarcity_rate=0.01, horizon_years=100,
                    carbon_price_current=100.0, carbon_price_growth=0.01)
    defaults.update(kwargs)
    return DiscountConfig(**defaults)


def test_discount_below_rate_passes():
    validate_discount_config(_discount(scarcity_rate=0.0299, carbon_price_growth=0.0299))


@pytest.mark.parametrize("scarcity", [0.03, 0.05])
def test_reject_scarcity_at_or_above_constant_rate(scarcity):
    with pytest.raises(ValueError, match=r"scarcity_rate \(\d\.\d\d%/yr\) must be below "
                                         r"the discount rate \(3\.00%/yr\)"):
        validate_discount_config(_discount(scarcity_rate=scarcity))


@pytest.mark.parametrize("growth", [0.03, 0.04])
def test_reject_carbon_growth_at_or_above_constant_rate(growth):
    with pytest.raises(ValueError, match=r"carbon_price_growth .* must be below "
                                         r"the discount rate \(3\.00%/yr\)"):
        validate_discount_config(_discount(carbon_price_growth=growth))


def test_reject_zero_rate_with_zero_growth():
    """An undiscounted permanent flow grows linearly with the horizon."""
    with pytest.raises(ValueError, match="scarcity_rate"):
        validate_discount_config(_discount(rate_schedule=0.0, scarcity_rate=0.0,
                                           carbon_price_growth=0.0))


def test_reject_scarcity_above_a_schedule_segment_within_horizon():
    """The offending segment and its years are named in the message."""
    config = _discount(rate_schedule=[(0, 0.03), (31, 0.02), (101, 0.01)],
                       scarcity_rate=0.015, horizon_years=200)
    with pytest.raises(ValueError, match=r"segment for years 101-200 \(1\.00%/yr\)"):
        validate_discount_config(config)


def test_reject_carbon_growth_above_a_schedule_segment_within_horizon():
    config = _discount(rate_schedule=[(0, 0.03), (31, 0.012)],
                       carbon_price_growth=0.013, horizon_years=100)
    with pytest.raises(ValueError, match=r"carbon_price_growth .* segment for "
                                         r"years 31-100 \(1\.20%/yr\)"):
        validate_discount_config(config)


def test_schedule_segment_after_horizon_is_not_checked():
    """Documented choice: segments starting after the horizon are never used."""
    config = _discount(rate_schedule=[(0, 0.03), (101, 0.005)],
                       scarcity_rate=0.01, horizon_years=100)
    validate_discount_config(config)
    with pytest.raises(ValueError, match="years 101-101"):
        validate_discount_config(dataclasses.replace(config, horizon_years=101))


def test_first_segment_covers_years_before_its_threshold():
    config = _discount(rate_schedule=[(5, 0.005), (50, 0.03)], scarcity_rate=0.01)
    with pytest.raises(ValueError, match="years 1-49"):
        validate_discount_config(config)


_DIVERGENT = DiscountConfig(rate_schedule=0.014, scarcity_rate=0.03)


def test_run_extraction_rejects_divergent_discount():
    eco = _ecosystem()
    eco.resource = dataclasses.replace(eco.resource, discount=_DIVERGENT)
    with pytest.raises(ValueError, match="scarcity_rate"):
        run_extraction(eco, 10)


def test_run_restoration_rejects_divergent_discount():
    eco = _ecosystem()
    eco.resource = dataclasses.replace(eco.resource, discount=_DIVERGENT)
    cost = RestorationCost(50.0, 10.0, 10)
    recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    with pytest.raises(ValueError, match="scarcity_rate"):
        run_restoration(eco, 10, cost, recovery, units_lost=10)


def test_default_discount_is_validated(monkeypatch):
    """A resource without a DiscountConfig runs on DEFAULT_DISCOUNT, validated too."""
    import gaia.discount
    monkeypatch.setattr(gaia.discount, "DEFAULT_DISCOUNT", _DIVERGENT)
    with pytest.raises(ValueError, match="scarcity_rate"):
        run_extraction(_ecosystem(), 10)


@pytest.mark.parametrize("mode", ["extract", "restore"])
def test_cli_rejects_divergent_discount(tmp_path, capsys, mode):
    """A case document with a divergent discount fails cleanly in gaia run."""
    import json

    from gaia.cases import case_data_path
    from gaia.cli import main

    doc = json.loads(case_data_path("forest").read_text(encoding="utf-8"))
    doc["discount"]["rate_schedule"] = 0.014
    doc["discount"]["scarcity_rate"] = 0.03
    path = tmp_path / "divergent.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["run", str(path), "--mode", mode, "--total-units", "100", "--units", "10",
                 "--carbon-price", "ets"]) == 1
    assert "scarcity_rate (3.00%/yr) must be below" in capsys.readouterr().err


# ── Step 6.2 (E8): NaN / inf, factory parameters, damage invariants at run time ─

_NONFINITE = [float("nan"), float("inf"), float("-inf")]


@pytest.mark.parametrize("value", _NONFINITE)
@pytest.mark.parametrize("field", ["unit_value", "area_ha"])
def test_reject_nonfinite_resource_fields(field, value):
    with pytest.raises(ValueError, match=f"{field}"):
        validate_resource(_resource(**{field: value}))


@pytest.mark.parametrize("value", _NONFINITE)
def test_reject_nonfinite_agent_value(value):
    eco = _ecosystem()
    eco.agents[0] = dataclasses.replace(eco.agents[0], annual_value_per_ha=value)
    with pytest.raises(ValueError, match="annual_value_per_ha"):
        validate_ecosystem(eco)


@pytest.mark.parametrize("value", _NONFINITE)
@pytest.mark.parametrize("field", [
    "delta", "eta", "g", "rate_schedule", "scarcity_rate",
    "carbon_price_current", "carbon_price_growth",
])
def test_reject_nonfinite_discount_params(field, value):
    with pytest.raises(ValueError, match="finite"):
        validate_discount_config(DiscountConfig(**{field: value}))


def test_reject_nonfinite_rate_schedule_entry():
    with pytest.raises(ValueError, match="finite"):
        validate_discount_config(DiscountConfig(rate_schedule=[(0, 0.04), (30, float("nan"))]))


@pytest.mark.parametrize("value", _NONFINITE)
def test_reject_nonfinite_edge_strength(value):
    eco = _ecosystem()
    eco.interactions = [InteractionEdge(eco.agents[0].name, eco.agents[1].name,
                                        value, "dependency", "")]
    with pytest.raises(ValueError, match="strength"):
        validate_ecosystem(eco)


@pytest.mark.parametrize("field", ["erosion_rate_unprotected", "formation_rate"])
def test_reject_nonfinite_substrate_rates(field):
    from gaia.validation import validate_substrate_profile
    profile = dataclasses.replace(forest_case.build_forest_ecosystem().resource.substrate, **{field: float("inf")})
    with pytest.raises(ValueError, match=field):
        validate_substrate_profile(profile)


@pytest.mark.parametrize("field", ["stored_carbon_tonnes", "annual_absorption_tonnes"])
def test_reject_nonfinite_carbon_profile(field):
    from gaia.validation import validate_carbon_profile
    profile = dataclasses.replace(forest_case.build_forest_ecosystem().resource.carbon_profile, **{field: float("nan")})
    with pytest.raises(ValueError, match=field):
        validate_carbon_profile(profile)


@pytest.mark.parametrize("kwargs", [
    dict(planting_cost_per_unit=float("nan")),
    dict(annual_maintenance_per_unit=float("inf")),
    dict(planting_cost_per_unit=-1.0),
    dict(maintenance_years=-1),
    dict(maintenance_years=2.5),
])
def test_reject_bad_restoration_cost(kwargs):
    fields = dict(planting_cost_per_unit=50.0, annual_maintenance_per_unit=10.0,
                  maintenance_years=10)
    fields.update(kwargs)
    eco = forest_case.build_forest_ecosystem(total_trees=100)
    recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    with pytest.raises(ValueError, match="RestorationCost"):
        run_restoration(eco, 10, RestorationCost(**fields), recovery)


@pytest.mark.parametrize("factory, kwargs", [
    ("logistic_damage", dict(threshold=0.3, steepness=0.0)),
    ("logistic_damage", dict(threshold=0.3, steepness=float("nan"))),
    ("logistic_damage", dict(threshold=1.0)),
    ("logistic_damage", dict(threshold=0.0)),
    ("exponential_damage", dict(threshold=0.3, base=1.0)),
    ("exponential_damage", dict(threshold=0.3, base=0.5)),
    ("exponential_damage", dict(threshold=1.0)),
    ("exponential_damage", dict(threshold=0.999999, base=1e6)),
    ("piecewise_damage", dict(threshold=0.3, pre_slope_ratio=0.3)),
    ("piecewise_damage", dict(threshold=0.3, pre_slope_ratio=-0.1)),
    ("piecewise_damage", dict(threshold=float("nan"))),
])
def test_damage_factories_reject_bad_parameters(factory, kwargs):
    """ValueError, not ZeroDivisionError / OverflowError (E8)."""
    import gaia.damage
    with pytest.raises(ValueError):
        getattr(gaia.damage, factory)(**kwargs)


@pytest.mark.parametrize("factory, kwargs", [
    ("logistic_recovery", dict(threshold=0.3, steepness=0.0)),
    ("logistic_recovery", dict(threshold=1.5)),
    ("linear_recovery", dict(slope=float("nan"))),
    ("linear_recovery", dict(slope=1.5)),
])
def test_recovery_factories_reject_bad_parameters(factory, kwargs):
    import gaia.recovery
    with pytest.raises(ValueError):
        getattr(gaia.recovery, factory)(**kwargs)


def test_damage_factories_record_their_threshold():
    from gaia.damage import exponential_damage, piecewise_damage
    for fn in (logistic_damage(0.3), exponential_damage(0.25), piecewise_damage(0.4)):
        assert fn.threshold in (0.3, 0.25, 0.4)


@pytest.mark.parametrize("bad_fn, match", [
    (lambda x: float("nan"), "finite"),
    (lambda x: 0.5 * x, "1.0"),
    (lambda x: x ** 0.5, "accelerate"),            # concave: never accelerates
    (lambda x: x, "accelerate"),                   # linear: no knee
])
def test_validate_ecosystem_runs_damage_invariants(bad_fn, match):
    """validate_ecosystem (hence every run) checks the damage invariants."""
    eco = _ecosystem([1.0])
    eco.agents[0] = dataclasses.replace(eco.agents[0], damage_function=bad_fn)
    with pytest.raises(ValueError, match=match):
        validate_ecosystem(eco)
    with pytest.raises(ValueError, match=match):
        run_extraction(eco, 10)


def test_damage_invariant_uses_function_threshold():
    """A curve whose knee is at its own threshold passes even when the
    resource threshold differs (agents may have their own thresholds)."""
    eco = _ecosystem([1.0])
    eco.agents[0] = dataclasses.replace(eco.agents[0],
                                        damage_function=logistic_damage(threshold=0.7))
    validate_ecosystem(eco, threshold_health_warning=None)


def test_damage_invariant_convexity_past_threshold():
    """Invariant 6: a curve that saturates right after its threshold fails."""
    def concave_past_threshold(x):
        return 0.1 * x / 0.3 if x <= 0.3 else 0.1 + 0.9 * ((x - 0.3) / 0.7) ** 0.5
    with pytest.raises(ValueError, match="convex"):
        validate_damage_function(concave_past_threshold, threshold=0.3)


def test_run_restoration_validates_succession_curve():
    """The succession curve passed to run_restoration is validated (it was
    only checked on the removed Agent.succession_curve field)."""
    bad = dataclasses.replace(forest_case.CASE.succession_curve, pioneer_end_year=-1.0)
    eco = forest_case.build_forest_ecosystem(total_trees=100)
    recovery = [logistic_recovery(threshold=0.3) for _ in eco.agents]
    with pytest.raises(ValueError, match="pioneer_end_year"):
        run_restoration(eco, 10, RestorationCost(50.0, 10.0, 10), recovery,
                        succession_curve=bad, time_horizon_years=10)
