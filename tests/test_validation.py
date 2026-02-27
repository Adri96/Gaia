"""
Gaia v0.1 — Input validation tests.

Verifies that validation raises descriptive errors on bad inputs and
passes cleanly on valid inputs. Validation failures must never silently default.
"""

import pytest
from gaia.damage import logistic_damage
from gaia.models import Agent, Ecosystem, Resource
from gaia.validation import (
    validate_damage_function,
    validate_ecosystem,
    validate_extraction,
    validate_resource,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resource(**kwargs) -> Resource:
    defaults = dict(
        name="Forest",
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
        monetary_rate=100_000.0,
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
