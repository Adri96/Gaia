"""
Gaia v0.6 -- Discount & NPV module unit tests.

Tests the discount mechanics, NPV calculations, carbon breakeven analysis,
and the destroy-then-restore penalty. Covers eight categories:

    1. DiscountConfig mechanics (Ramsey rate, discount factor, declining schedule,
       carbon price growth, scarcity factor)
    2. Preconfigured discount profiles (market, central, environmental, green book)
    3. compute_extraction_npv (components, carbon, substrate, totals)
    4. compute_restoration_npv (costs, benefits, succession, carbon payback)
    5. compute_carbon_breakeven (no-carbon, positive, monotonicity)
    6. restoration_cost_ratio and compute_destroy_then_restore_penalty
    7. Edge cases (zero horizon, zero discount rate, high discount rate)
    8. One year convention (flows at the end of years 1..H)
"""

import math
import pytest

from gaia.models import (
    CarbonBreakeven,
    CarbonProfile,
    DiscountConfig,
    DestroyThenRestorePenalty,
    ExtractionNPV,
    RestorationNPV,
    SuccessionCurve,
)
from gaia.discount import (
    compute_carbon_breakeven,
    compute_destroy_then_restore_penalty,
    compute_extraction_npv,
    compute_restoration_npv,
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    DISCOUNT_MARKET,
    restoration_cost_ratio,
)
from gaia.succession import succession_service


# ── Test fixtures ─────────────────────────────────────────────────────────────


def _carbon_profile(**kwargs) -> CarbonProfile:
    """Standard carbon profile fixture for tests."""
    defaults = dict(
        stored_carbon_tonnes=2.5,
        annual_absorption_tonnes=0.025,
        soil_carbon_tonnes=1.8,
        soil_release_fraction=0.3,
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

    @pytest.mark.parametrize("profile", [
        DISCOUNT_MARKET, DISCOUNT_CENTRAL, DISCOUNT_ENVIRONMENTAL, DISCOUNT_GREEN_BOOK,
    ])
    def test_profiles_converge(self, profile):
        """Every built-in profile passes validation: scarcity and carbon price
        growth below the discount rate in every year of the horizon (C3)."""
        from gaia.validation import validate_discount_config
        validate_discount_config(profile)

    def test_discount_environmental_scarcity_below_rate(self):
        assert DISCOUNT_ENVIRONMENTAL.scarcity_rate == 0.01
        assert DISCOUNT_ENVIRONMENTAL.scarcity_rate < DISCOUNT_ENVIRONMENTAL.rate_schedule

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
            annual_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
            substrate_ceiling=0.85,
        )

        assert result.direct >= 0.0
        assert result.carbon_release >= 0.0
        assert result.carbon_foregone >= 0.0
        assert result.substrate_unrecoverable >= 0.0
        assert result.total >= 0.0

    def test_extraction_npv_with_no_carbon(self):
        """Carbon components are 0 when no carbon_profile is provided."""
        config = _default_discount()

        result = compute_extraction_npv(
            annual_externality=1000.0,
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
            annual_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
        )

        assert result.carbon_release > 0.0
        assert result.carbon_foregone > 0.0

    def test_extraction_npv_with_substrate(self):
        """Unrecoverable share > 0 when substrate_ceiling < 1.0, inside direct.

        Substrate model: the direct loss is already permanent, so substrate
        only marks the part restoration can never recover — it does not
        change the total (no double counting, C5).
        """
        config = _default_discount()

        result = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
            substrate_ceiling=0.85,
        )
        intact = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        assert result.substrate_unrecoverable == pytest.approx(0.15 * result.direct)
        assert result.total == intact.total

    def test_extraction_npv_no_substrate_damage_at_full_ceiling(self):
        """Substrate damage = 0 when substrate_ceiling = 1.0 (no permanent loss)."""
        config = _default_discount()

        result = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
            substrate_ceiling=1.0,
        )

        assert result.substrate_unrecoverable == 0.0

    def test_extraction_npv_total_is_sum(self):
        """total == direct + carbon_release + carbon_foregone (substrate not added)."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=10,
            substrate_ceiling=0.85,
        )

        expected_total = (
            result.direct
            + result.carbon_release
            + result.carbon_foregone
        )
        assert abs(result.total - expected_total) < 1e-6

    def test_extraction_npv_horizon_stored(self):
        """The horizon attribute should reflect the config's horizon_years."""
        config = _default_discount(horizon_years=50)

        result = compute_extraction_npv(
            annual_externality=1000.0,
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


# ── 6. restoration_cost_ratio and destroy-then-restore penalty ────────────


class TestDestroyThenRestorePenalty:
    """Tests for restoration_cost_ratio and compute_destroy_then_restore_penalty."""

    @staticmethod
    def _penalty(**kwargs):
        args = dict(
            foregone_revenue=100000.0, restoration_cost_pv=60000.0,
            annual_damage_reversal=6000.0, annual_recovered_potential=5000.0,
            discount=_default_discount(), succession_curve=_succession_curve(),
            carbon_profile=_carbon_profile(), units=100, substrate_ceiling=0.85,
        )
        args.update(kwargs)
        return compute_destroy_then_restore_penalty(**args)

    def test_restoration_cost_ratio_is_input_price_ratio(self):
        """(revenue + cost) / revenue = 1 + cost per unit / unit value."""
        k, unit_value, cost_per_unit = 400, 60.0, 305.0
        ratio = restoration_cost_ratio(k * unit_value, k * cost_per_unit)
        assert ratio == pytest.approx(1 + cost_per_unit / unit_value, rel=1e-12)

    def test_restoration_cost_ratio_none_without_revenue(self):
        assert restoration_cost_ratio(0.0, 5000.0) is None
        assert restoration_cost_ratio(-1.0, 5000.0) is None

    def test_components_sum_to_total(self):
        pen = self._penalty()
        assert isinstance(pen, DestroyThenRestorePenalty)
        assert pen.total == pytest.approx(
            pen.restoration_cost + pen.maturation_gap + pen.substrate_loss
            + pen.recovery_shortfall + pen.carbon_not_recovered, rel=1e-12)
        assert pen.ratio == pytest.approx(pen.total / 100000.0, rel=1e-12)
        assert pen.foregone_revenue == 100000.0
        assert pen.horizon == 100

    def test_penalty_at_least_restoration_cost(self):
        pen = self._penalty()
        assert pen.total >= pen.restoration_cost
        bare = self._penalty(annual_damage_reversal=0.0, annual_recovered_potential=0.0,
                             carbon_profile=None)
        assert bare.total == pytest.approx(bare.restoration_cost, rel=1e-12)

    def test_monotone_in_maturation_time(self):
        """Slower succession (longer delay, later climax) → larger penalty."""
        totals = [
            self._penalty(succession_curve=_succession_curve(
                maturation_delay=delay, climax_approach_year=climax)).total
            for delay, climax in ((0.0, 40.0), (2.0, 60.0), (5.0, 90.0), (10.0, 120.0))
        ]
        assert all(a < b for a, b in zip(totals, totals[1:])), totals

    def test_instant_recovery_has_no_maturation_gap(self):
        pen = self._penalty(succession_curve=None)
        assert pen.maturation_gap == 0.0

    def test_shortfalls_counted_once(self):
        """gap + substrate + shortfall = Σ_t (reversal − delivered(t)): each year's
        unrecovered service once (substrate only lowers the ceiling)."""
        config = _default_discount()
        curve = _succession_curve()
        pen = self._penalty(carbon_profile=None, restoration_cost_pv=0.0)
        expected = sum(
            (6000.0 - 5000.0 * min(succession_service(curve, float(t)), 0.85))
            * config.discount_factor(t) * config.scarcity_factor(t)
            for t in range(1, config.horizon_years + 1)
        )
        assert pen.total == pytest.approx(expected, rel=1e-12)

    def test_substrate_loss_zero_at_full_ceiling(self):
        pen = self._penalty(substrate_ceiling=1.0)
        assert pen.substrate_loss == 0.0
        assert self._penalty(substrate_ceiling=0.7).substrate_loss > 0.0

    def test_carbon_not_recovered_is_release_plus_absorption_shortfall(self):
        from gaia.carbon import compute_carbon_release, pv_absorption, pv_carbon_release
        config = _default_discount()
        carbon = _carbon_profile()
        curve = _succession_curve()
        pen = self._penalty()
        expected = pv_carbon_release(compute_carbon_release(carbon, 100), config) + \
            pv_absorption(100 * carbon.annual_absorption_tonnes, config, curve, 0.85,
                          shortfall=True)
        assert pen.carbon_not_recovered == pytest.approx(expected, rel=1e-12)

    def test_ratio_none_without_revenue(self):
        pen = self._penalty(foregone_revenue=0.0)
        assert pen.ratio is None
        assert pen.total > 0.0


# ── 7. Edge cases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge-case tests for discount and NPV computations."""

    def test_zero_horizon(self):
        """NPV should be close to 0 for future flows when horizon=0."""
        config = _default_discount(horizon_years=0)

        result = compute_extraction_npv(
            annual_externality=1000.0,
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
            annual_externality=100.0,
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
            annual_externality=1000.0,
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
            annual_externality=0.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        assert result.direct == 0.0
        assert result.substrate_unrecoverable == 0.0

    def test_zero_units_extracted(self):
        """Zero units extracted should produce zero carbon components."""
        config = _default_discount()
        carbon = _carbon_profile()

        result = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=carbon,
            units_extracted=0,
        )

        assert result.carbon_release == 0.0
        assert result.carbon_foregone == 0.0

    def test_single_year_horizon(self):
        """Horizon of 1 year: only the year-1 flow contributes, discounted once."""
        config = _default_discount(horizon_years=1)

        result = compute_extraction_npv(
            annual_externality=1000.0,
            discount=config,
            carbon_profile=None,
            units_extracted=10,
        )

        expected = 1000.0 * config.discount_factor(1) * config.scarcity_factor(1)
        assert result.direct == pytest.approx(expected, rel=1e-12)

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


# ── 8. One year convention (C3 / S7 off-by-one) ──────────────────────────────


class TestYearConvention:
    """Every yearly flow is valued at the end of years t = 1..H (gaia.discount)."""

    def test_direct_pv_is_end_of_year_annuity(self):
        config = DiscountConfig(rate_schedule=0.04, scarcity_rate=0.01,
                                horizon_years=30)
        q = 1.01 / 1.04
        result = compute_extraction_npv(1000.0, config, None, 0)
        assert result.direct == pytest.approx(
            1000.0 * q * (1 - q ** 30) / (1 - q), rel=1e-12)

    def test_immediate_restoration_matches_extraction_years(self):
        """Without succession, restored services cover the same years as the loss."""
        config = _default_discount()
        restored = compute_restoration_npv(0.0, 0.0, 0, 1000.0, config,
                                           None, None, 0)
        lost = compute_extraction_npv(1000.0, config, None, 0)
        assert restored.service_benefits == pytest.approx(lost.direct, rel=1e-12)

    def test_maturation_timeline_and_npv_share_years(self):
        """Delivered (NPV) + gap (timeline) = the capped mature flow every year 1..H."""
        from gaia.succession import compute_maturation_gap, compute_maturation_timeline
        config = _default_discount()
        curve = _succession_curve()
        ceiling = 0.8
        npv = compute_restoration_npv(0.0, 0.0, 0, 5000.0, config, curve,
                                      None, 0, substrate_ceiling=ceiling)
        timeline = compute_maturation_timeline(curve, 5000.0, config.horizon_years,
                                               0, substrate_ceiling=ceiling)
        assert [s.year for s in timeline] == list(range(1, config.horizon_years + 1))
        gap = compute_maturation_gap(timeline, 5000.0 * ceiling, config)
        mature = compute_extraction_npv(5000.0 * ceiling, config, None, 0).direct
        assert npv.service_benefits + gap == pytest.approx(mature, rel=1e-12)

    def test_carbon_payback_matches_carbon_module(self):
        """Payback year t counts the absorption of years 1..t, as in gaia.carbon."""
        from gaia.carbon import compute_carbon_payback_period
        config = _default_discount()
        curve = _succession_curve()
        # Release = 100 units × 0.025 t = 2.5 t, recaptured by absorption
        profile = CarbonProfile(stored_carbon_tonnes=0.025,
                                annual_absorption_tonnes=0.025,
                                soil_carbon_tonnes=0.0, soil_release_fraction=0.0)
        npv = compute_restoration_npv(0.0, 0.0, 0, 0.0, config, curve, profile,
                                      100, carbon_released=2.5)
        expected = compute_carbon_payback_period(profile, 100, 100, curve)
        assert npv.carbon_payback_years == int(expected)
