"""
Gaia v0.6 -- Discount & NPV module unit tests.

Tests the discount mechanics, NPV calculations, carbon breakeven analysis,
and enhanced prevention advantage. Covers seven categories:

    1. DiscountConfig mechanics (Ramsey rate, discount factor, declining schedule,
       carbon price growth, scarcity factor)
    2. Preconfigured discount profiles (market, central, environmental, green book)
    3. compute_extraction_npv (components, carbon, substrate, totals)
    4. compute_restoration_npv (costs, benefits, succession, carbon payback)
    5. compute_carbon_breakeven (no-carbon, positive, monotonicity)
    6. compute_prevention_advantage_v06 (layered PAs, zero revenue)
    7. Edge cases (zero horizon, zero discount rate, high discount rate)
"""

import math
import pytest

from gaia.models import (
    CarbonBreakeven,
    CarbonProfile,
    DiscountConfig,
    ExtractionNPV,
    PreventionAdvantageV06,
    RestorationNPV,
    SuccessionCurve,
)
from gaia.discount import (
    compute_carbon_breakeven,
    compute_extraction_npv,
    compute_prevention_advantage_v06,
    compute_restoration_npv,
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    DISCOUNT_MARKET,
)


# ── Test fixtures ─────────────────────────────────────────────────────────────


def _carbon_profile(**kwargs) -> CarbonProfile:
    """Standard carbon profile fixture for tests."""
    defaults = dict(
        stored_carbon_tonnes=2.5,
        annual_absorption_tonnes=0.025,
        soil_carbon_tonnes=1.8,
        soil_release_fraction=0.3,
        carbon_price_per_tonne=80.0,
    )
    defaults.update(kwargs)
    return CarbonProfile(**defaults)


def _succession_curve(**kwargs) -> SuccessionCurve:
    """Standard succession curve fixture for tests."""
    defaults = dict(
        pioneer_end_year=5.0,
        intermediate_end_year=25.0,
        climax_approach_year=60.0,
        pioneer_service=0.05,
        intermediate_service=0.40,
        maturation_delay=2.0,
    )
    defaults.update(kwargs)
    return SuccessionCurve(**defaults)


def _default_discount(**kwargs) -> DiscountConfig:
    """Standard discount config fixture (central-like defaults)."""
    defaults = dict(
        delta=0.005,
        eta=1.35,
        g=0.013,
        scarcity_rate=0.02,
        horizon_years=100,
        carbon_price_current=80.0,
        carbon_price_growth=0.03,
    )
    defaults.update(kwargs)
    return DiscountConfig(**defaults)


# ── 1. DiscountConfig mechanics ──────────────────────────────────────────────


class TestDiscountConfigMechanics:
    """Tests for DiscountConfig rate computation, discount factors, and prices."""

    def test_default_rate_from_ramsey(self):
        """Default config computes rate = delta + eta * g = 0.005 + 1.35 * 0.013."""
        config = _default_discount()
        expected_rate = 0.005 + 1.35 * 0.013  # 0.02255
        assert isinstance(config.rate_schedule, float)
        assert abs(config.rate_schedule - expected_rate) < 1e-10

    def test_constant_rate_discount_factor(self):
        """discount_factor(0)=1.0, discount_factor(10) = 1/(1+r)^10."""
        config = _default_discount()
        rate = config.rate_schedule

        assert config.discount_factor(0) == 1.0

        expected_df_10 = 1.0 / (1.0 + rate) ** 10
        actual_df_10 = config.discount_factor(10)
        assert abs(actual_df_10 - expected_df_10) < 1e-10

    def test_declining_schedule_rate_at_year(self):
        """Declining schedule returns the correct rate for each threshold band."""
        schedule = [(0, 0.035), (31, 0.030), (76, 0.025)]
        config = DiscountConfig(rate_schedule=schedule)

        # Year 0-30: first band
        assert config.rate_at_year(0) == 0.035
        assert config.rate_at_year(15) == 0.035
        assert config.rate_at_year(30) == 0.035

        # Year 31-75: second band
        assert config.rate_at_year(31) == 0.030
        assert config.rate_at_year(50) == 0.030
        assert config.rate_at_year(75) == 0.030

        # Year 76+: third band
        assert config.rate_at_year(76) == 0.025
        assert config.rate_at_year(100) == 0.025
        assert config.rate_at_year(200) == 0.025

    def test_declining_schedule_discount_factor(self):
        """Declining schedule discount factor is the product of annual factors."""
        schedule = [(0, 0.035), (31, 0.030), (76, 0.025)]
        config = DiscountConfig(rate_schedule=schedule)

        # Manually compute the product of annual factors for year 35
        expected_factor = 1.0
        for t in range(1, 36):
            rate = config.rate_at_year(t)
            expected_factor /= (1.0 + rate)

        actual_factor = config.discount_factor(35)
        assert abs(actual_factor - expected_factor) < 1e-10

    def test_carbon_price_at_year_0(self):
        """Carbon price at year 0 equals carbon_price_current."""
        config = _default_discount(carbon_price_current=80.0)
        assert config.carbon_price_at_year(0) == 80.0

    def test_carbon_price_at_year_10(self):
        """Carbon price at year 10 = 80 * 1.03^10."""
        config = _default_discount(carbon_price_current=80.0, carbon_price_growth=0.03)
        expected = 80.0 * (1.03 ** 10)
        actual = config.carbon_price_at_year(10)
        assert abs(actual - expected) < 1e-6
        # Sanity: should be approximately 107.5
        assert abs(actual - 107.5) < 1.0

    def test_scarcity_factor_at_year_0(self):
        """Scarcity factor at year 0 equals 1.0."""
        config = _default_discount(scarcity_rate=0.02)
        assert config.scarcity_factor(0) == 1.0

    def test_scarcity_factor_at_year_50(self):
        """Scarcity factor at year 50 = (1.02)^50."""
        config = _default_discount(scarcity_rate=0.02)
        expected = (1.02) ** 50  # approximately 2.69
        actual = config.scarcity_factor(50)
        assert abs(actual - expected) < 1e-6
        assert abs(actual - 2.69) < 0.02


# ── 2. Preconfigured profiles ───────────────────────────────────────────────


class TestPreconfiguredProfiles:
    """Tests for the four preconfigured discount profiles."""

    def test_discount_market(self):
        """DISCOUNT_MARKET has rate approximately 0.041."""
        assert isinstance(DISCOUNT_MARKET.rate_schedule, float)
        assert abs(DISCOUNT_MARKET.rate_schedule - 0.041) < 1e-6

    def test_discount_central(self):
        """DISCOUNT_CENTRAL has rate approximately 0.023."""
        assert isinstance(DISCOUNT_CENTRAL.rate_schedule, float)
        assert abs(DISCOUNT_CENTRAL.rate_schedule - 0.023) < 1e-6

    def test_discount_environmental(self):
        """DISCOUNT_ENVIRONMENTAL has rate approximately 0.014."""
        assert isinstance(DISCOUNT_ENVIRONMENTAL.rate_schedule, float)
        assert abs(DISCOUNT_ENVIRONMENTAL.rate_schedule - 0.014) < 1e-6

    def test_discount_green_book(self):
        """DISCOUNT_GREEN_BOOK has declining schedule, not a single float."""
        assert isinstance(DISCOUNT_GREEN_BOOK.rate_schedule, list)
        # Should have three tiers: 3.5%, 3.0%, 2.5%
        assert len(DISCOUNT_GREEN_BOOK.rate_schedule) == 3
        assert DISCOUNT_GREEN_BOOK.rate_schedule[0] == (0, 0.035)
        assert DISCOUNT_GREEN_BOOK.rate_schedule[1] == (31, 0.030)
        assert DISCOUNT_GREEN_BOOK.rate_schedule[2] == (76, 0.025)


# ── 3. compute_extraction_npv ────────────────────────────────────────────────


class TestComputeExtractionNPV:
    """Tests for extraction NPV calculation."""

    def test_extraction_npv_components_positive(self):
        """All NPV components should be >= 0."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
            substrate_ceiling=0.85,
        )

        assert result.direct >= 0.0
        assert result.carbon_release >= 0.0
        assert result.carbon_foregone >= 0.0
        assert result.substrate_damage >= 0.0
        assert result.total >= 0.0

    def test_extraction_npv_with_no_carbon(self):
        """Carbon components are 0 when no carbon_profile is provided."""
        config = _default_discount()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        assert result.carbon_release == 0.0
        assert result.carbon_foregone == 0.0
        # Direct should still be positive
        assert result.direct > 0.0

    def test_extraction_npv_with_carbon(self):
        """Carbon release and carbon foregone should be > 0 with carbon profile."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
        )

        assert result.carbon_release > 0.0
        assert result.carbon_foregone > 0.0

    def test_extraction_npv_with_substrate(self):
        """Substrate damage > 0 when substrate_ceiling < 1.0."""
        config = _default_discount()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
            substrate_ceiling=0.85,
        )

        assert result.substrate_damage > 0.0

    def test_extraction_npv_no_substrate_damage_at_full_ceiling(self):
        """Substrate damage = 0 when substrate_ceiling = 1.0 (no permanent loss)."""
        config = _default_discount()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
            substrate_ceiling=1.0,
        )

        assert result.substrate_damage == 0.0

    def test_extraction_npv_total_is_sum(self):
        """total == direct + carbon_release + carbon_foregone + substrate_damage."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
            substrate_ceiling=0.85,
        )

        expected_total = (
            result.direct
            + result.carbon_release
            + result.carbon_foregone
            + result.substrate_damage
        )
        assert abs(result.total - expected_total) < 1e-6

    def test_extraction_npv_horizon_stored(self):
        """The horizon attribute should reflect the config's horizon_years."""
        config = _default_discount(horizon_years=50)

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        assert result.horizon == 50


# ── 4. compute_restoration_npv ───────────────────────────────────────────────


class TestComputeRestorationNPV:
    """Tests for restoration NPV calculation."""

    def test_restoration_npv_positive_roi(self):
        """ROI should be > 0 for reasonable restoration parameters."""
        config = _default_discount()
        succession = _succession_curve()
        carbon = _carbon_profile()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=succession,
            carbon_profile=carbon,
            units_restored=100,
            substrate_ceiling=1.0,
            carbon_released=500.0,
        )

        assert result.roi > 0.0

    def test_restoration_npv_cost_positive(self):
        """NPV of restoration cost should be > 0."""
        config = _default_discount()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        assert result.cost > 0.0

    def test_restoration_npv_with_succession(self):
        """Benefits should be lower with slow succession curve vs no succession."""
        config = _default_discount()

        # Without succession: immediate full recovery
        result_immediate = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        # With succession: delayed recovery
        succession = _succession_curve()
        result_succession = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=succession,
            carbon_profile=None,
            units_restored=100,
        )

        assert result_immediate.service_benefits > result_succession.service_benefits

    def test_carbon_payback_exists(self):
        """carbon_payback_years should be an int when carbon profile and release present."""
        config = _default_discount()
        succession = _succession_curve()
        carbon = _carbon_profile()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=succession,
            carbon_profile=carbon,
            units_restored=100,
            carbon_released=5.0,  # small amount so payback is achievable
        )

        assert result.carbon_payback_years is not None
        assert isinstance(result.carbon_payback_years, int)
        assert result.carbon_payback_years > 0

    def test_carbon_payback_none_without_release(self):
        """carbon_payback_years should be None when carbon_released is 0."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=carbon,
            units_restored=100,
            carbon_released=0.0,
        )

        assert result.carbon_payback_years is None

    def test_restoration_npv_total_benefits_is_sum(self):
        """total_benefits == service_benefits + carbon_benefits."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=succession,
            carbon_profile=carbon,
            units_restored=100,
        )

        assert abs(result.total_benefits - (result.service_benefits + result.carbon_benefits)) < 1e-6

    def test_restoration_npv_net_present_value(self):
        """net_present_value == total_benefits - cost."""
        config = _default_discount()

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        assert abs(result.net_present_value - (result.total_benefits - result.cost)) < 1e-6


# ── 5. compute_carbon_breakeven ──────────────────────────────────────────────


class TestComputeCarbonBreakeven:
    """Tests for carbon breakeven analysis."""

    def test_breakeven_with_no_carbon(self):
        """Breakeven price = inf when no carbon profile provided."""
        config = _default_discount()

        result = compute_carbon_breakeven(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        assert result.breakeven_price == float("inf")
        assert result.profitable_at_current is False

    def test_breakeven_positive(self):
        """Breakeven price should be > 0 with carbon profile."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        result = compute_carbon_breakeven(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            succession_curve=succession,
            carbon_profile=carbon,
            units_restored=100,
        )

        assert result.breakeven_price > 0.0
        assert result.breakeven_price < float("inf")

    def test_breakeven_above_current(self):
        """gap_to_current > 0 when restoration is not yet carbon-viable."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        # High restoration cost relative to tiny carbon absorption
        result = compute_carbon_breakeven(
            restoration_cost_total=500000.0,
            maintenance_cost_per_year=5000.0,
            maintenance_years=10,
            discount=config,
            succession_curve=succession,
            carbon_profile=carbon,
            units_restored=10,
        )

        assert result.gap_to_current > 0.0
        assert result.profitable_at_current is False

    def test_breakeven_monotonic(self):
        """Higher restoration cost should produce higher breakeven price."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        breakeven_prices = []
        for cost in [10000.0, 50000.0, 100000.0, 500000.0]:
            result = compute_carbon_breakeven(
                restoration_cost_total=cost,
                maintenance_cost_per_year=1000.0,
                maintenance_years=10,
                discount=config,
                succession_curve=succession,
                carbon_profile=carbon,
                units_restored=100,
            )
            breakeven_prices.append(result.breakeven_price)

        for i in range(1, len(breakeven_prices)):
            assert breakeven_prices[i] >= breakeven_prices[i - 1], (
                f"Monotonicity violated: cost index {i}, "
                f"breakeven {breakeven_prices[i]} < {breakeven_prices[i-1]}"
            )

    def test_breakeven_npv_cost_positive(self):
        """npv_cost should be positive for non-zero restoration costs."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_carbon_breakeven(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            succession_curve=None,
            carbon_profile=carbon,
            units_restored=100,
        )

        assert result.npv_cost > 0.0

    def test_breakeven_current_price_from_config(self):
        """current_price should reflect the discount config's carbon_price_current."""
        config = _default_discount(carbon_price_current=120.0)
        carbon = _carbon_profile()

        result = compute_carbon_breakeven(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            succession_curve=None,
            carbon_profile=carbon,
            units_restored=100,
        )

        assert result.current_price == 120.0


# ── 6. compute_prevention_advantage_v06 ─────────────────────────────────────


class TestComputePreventionAdvantageV06:
    """Tests for the enhanced prevention advantage with full NPV accounting."""

    def test_pa_full_greater_than_simple(self):
        """pa_full >= pa_simple always (NPV adds costs, never removes them)."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        result = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=carbon,
            units=100,
            substrate_ceiling=0.85,
            carbon_released=500.0,
            pa_simple=3.5,
        )

        assert result.pa_full >= result.pa_simple

    def test_pa_with_carbon_greater_than_without_carbon(self):
        """pa_full with carbon > pa_full without carbon (carbon adds to damage cost)."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        # PA with carbon
        result_with = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=carbon,
            units=100,
            substrate_ceiling=1.0,
            carbon_released=500.0,
            pa_simple=3.5,
        )

        # PA without carbon
        result_without = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=None,
            units=100,
            substrate_ceiling=1.0,
            carbon_released=0.0,
            pa_simple=3.5,
        )

        # Adding carbon externality increases total NPV cost
        assert result_with.pa_with_carbon > 1.0
        assert result_with.pa_full >= result_without.pa_full

    def test_pa_with_substrate_greater_than_simple(self):
        """pa_with_substrate >= pa_simple when substrate_ceiling < 1.0."""
        config = _default_discount()
        succession = _succession_curve()

        result = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=None,
            units=100,
            substrate_ceiling=0.85,
            pa_simple=3.5,
        )

        assert result.pa_with_substrate >= result.pa_simple

    def test_pa_zero_revenue(self):
        """Returns simple PA for all variants when foregone_revenue <= 0."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        result = compute_prevention_advantage_v06(
            foregone_revenue=0.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=carbon,
            units=100,
            substrate_ceiling=0.85,
            carbon_released=500.0,
            pa_simple=3.5,
        )

        assert result.pa_simple == 3.5
        assert result.pa_with_carbon == 3.5
        assert result.pa_with_substrate == 3.5
        assert result.pa_full == 3.5
        assert result.npv_prevention_cost == 0.0
        assert result.npv_restoration_total == 0.0

    def test_pa_negative_revenue(self):
        """Negative foregone_revenue also returns simple PA for all variants."""
        config = _default_discount()

        result = compute_prevention_advantage_v06(
            foregone_revenue=-5000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=None,
            carbon_profile=None,
            units=100,
            pa_simple=2.0,
        )

        assert result.pa_simple == 2.0
        assert result.pa_with_carbon == 2.0
        assert result.pa_with_substrate == 2.0
        assert result.pa_full == 2.0

    def test_pa_full_includes_all_components(self):
        """pa_full should be >= pa_with_carbon and pa_with_substrate individually."""
        config = _default_discount()
        carbon = _carbon_profile()
        succession = _succession_curve()

        result = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=succession,
            carbon_profile=carbon,
            units=100,
            substrate_ceiling=0.85,
            carbon_released=500.0,
            pa_simple=3.5,
        )

        assert result.pa_full >= result.pa_with_carbon
        assert result.pa_full >= result.pa_with_substrate

    def test_pa_npv_prevention_cost_equals_revenue(self):
        """npv_prevention_cost should equal foregone_revenue when revenue > 0."""
        config = _default_discount()

        result = compute_prevention_advantage_v06(
            foregone_revenue=100000.0,
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            discount=config,
            max_recovered_value=5000.0,
            succession_curve=None,
            carbon_profile=None,
            units=100,
            pa_simple=3.5,
        )

        assert result.npv_prevention_cost == 100000.0


# ── 7. Edge cases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge-case tests for discount and NPV computations."""

    def test_zero_horizon(self):
        """NPV should be close to 0 for future flows when horizon=0."""
        config = _default_discount(horizon_years=0)

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        # With horizon_years=0, range(0) produces no iterations for direct
        assert result.direct == 0.0
        assert result.total == 0.0

    def test_zero_horizon_restoration(self):
        """Restoration NPV with zero horizon: services should be 0."""
        config = _default_discount(horizon_years=0)

        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=2000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        assert result.service_benefits == 0.0

    def test_zero_discount_rate(self):
        """NPV with zero discount rate should approximate undiscounted sum."""
        config = DiscountConfig(
            rate_schedule=0.0,
            scarcity_rate=0.0,
            horizon_years=10,
            carbon_price_current=80.0,
            carbon_price_growth=0.0,
        )

        result = compute_extraction_npv(
            total_externality=100.0,
            discount=config,
            carbon_profile=None,
            units_extracted=1,
        )

        # With rate=0 and scarcity=0 over 10 years: direct = 100 * 10 = 1000
        assert abs(result.direct - 1000.0) < 1e-6

    def test_very_high_discount_rate(self):
        """NPV should be very low with a very high discount rate."""
        config = DiscountConfig(
            rate_schedule=1.0,  # 100% discount rate
            scarcity_rate=0.0,
            horizon_years=100,
            carbon_price_current=80.0,
            carbon_price_growth=0.0,
        )

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        # At 100% discount rate, year 0 factor=1, year 1 factor=0.5,
        # year 2 factor=0.25, etc. Geometric sum = 1000 * (1 - 0.5^100) / (1 - 0.5) ~ 2000
        # But the point is this should be much less than undiscounted (1000 * 100 = 100,000)
        assert result.direct < 2100.0
        assert result.direct > 0.0

    def test_zero_externality(self):
        """Zero total_externality should produce zero direct and substrate NPV."""
        config = _default_discount()

        result = compute_extraction_npv(
            total_externality=0.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        assert result.direct == 0.0
        assert result.substrate_damage == 0.0

    def test_zero_units_extracted(self):
        """Zero units extracted should produce zero carbon components."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=0,
        )

        assert result.carbon_release == 0.0
        assert result.carbon_foregone == 0.0

    def test_single_year_horizon(self):
        """Horizon of 1 year: only year 0 contributes to direct NPV."""
        config = _default_discount(horizon_years=1)

        result = compute_extraction_npv(
            total_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        # Only year 0 in range(1): factor=1.0, scarcity=1.0
        assert abs(result.direct - 1000.0) < 1e-6

    def test_carbon_price_growth_zero(self):
        """With zero carbon price growth, carbon price stays constant."""
        config = DiscountConfig(
            rate_schedule=0.0,
            scarcity_rate=0.0,
            horizon_years=50,
            carbon_price_current=80.0,
            carbon_price_growth=0.0,
        )

        for year in [0, 10, 25, 50]:
            assert config.carbon_price_at_year(year) == 80.0

    def test_scarcity_rate_zero(self):
        """With zero scarcity rate, scarcity factor stays at 1.0."""
        config = DiscountConfig(
            rate_schedule=0.02,
            scarcity_rate=0.0,
            horizon_years=100,
        )

        for year in [0, 10, 50, 100]:
            assert config.scarcity_factor(year) == 1.0

    def test_planting_cost_floor_at_zero(self):
        """If maintenance cost * years > total cost, planting cost floors at 0."""
        config = _default_discount()

        # maintenance_cost * years = 10000 * 10 = 100,000 > restoration_cost = 50,000
        result = compute_restoration_npv(
            restoration_cost_total=50000.0,
            maintenance_cost_per_year=10000.0,
            maintenance_years=10,
            max_recovered_value=5000.0,
            discount=config,
            succession_curve=None,
            carbon_profile=None,
            units_restored=100,
        )

        # Cost should still be positive (from discounted maintenance)
        assert result.cost > 0.0

    def test_green_book_declining_factors(self):
        """Green Book declining schedule: later years get higher discount factors
        (lower rates mean less discounting)."""
        config = DISCOUNT_GREEN_BOOK

        # Compare discount factor growth at different schedule regimes
        # In the first regime (3.5%), factors decrease faster than in the third (2.5%)
        df_30 = config.discount_factor(30)
        df_31 = config.discount_factor(31)
        ratio_early = df_31 / df_30  # 1 / (1 + 0.030) after transition

        df_75 = config.discount_factor(75)
        df_76 = config.discount_factor(76)
        ratio_late = df_76 / df_75  # 1 / (1 + 0.025) after transition

        # The late regime (2.5%) should discount less per year than mid regime (3.0%)
        assert ratio_late > ratio_early
