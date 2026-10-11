"""
Tests for gaia.carbon — Carbon accounting module.

Covers the carbon price (social cost of carbon, market/ETS view), carbon
release, carbon present values, monetized carbon cost, annual absorption
during maturation, and carbon payback period.
"""

import dataclasses

import pytest

from gaia.carbon import (
    ETS_CARBON_PRICE_EUR,
    SCC_GROWTH_RATE,
    SCC_USD_2020_PER_T,
    SOCIAL_COST_OF_CARBON_EUR,
    USD_PER_EUR_2020,
    compute_annual_absorption,
    compute_carbon_cost,
    compute_carbon_payback_period,
    compute_carbon_release,
    pv_absorption,
    pv_carbon_release,
    with_carbon_price_view,
)
from gaia.discount import (
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    DISCOUNT_MARKET,
)
from gaia.models import CarbonProfile, DiscountConfig, SuccessionCurve


# ── Test fixtures ──────────────────────────────────────────────────────────────

_FOREST_CARBON = CarbonProfile(
    stored_carbon_tonnes=0.8,
    annual_absorption_tonnes=0.022,
    soil_carbon_tonnes=0.3,
    soil_release_fraction=0.25,
)

_POSIDONIA_CARBON = CarbonProfile(
    stored_carbon_tonnes=130.0,
    annual_absorption_tonnes=1.58,
    soil_carbon_tonnes=2600.0,
    soil_release_fraction=0.05,
)

_FOREST_SUCCESSION = SuccessionCurve(
    pioneer_end_year=8.0,
    intermediate_end_year=25.0,
    climax_approach_year=60.0,
    pioneer_service=0.05,
    intermediate_service=0.35,
    maturation_delay=2.0,
)

_POSIDONIA_SUCCESSION = SuccessionCurve(
    pioneer_end_year=20.0,
    intermediate_end_year=50.0,
    climax_approach_year=120.0,
    pioneer_service=0.02,
    intermediate_service=0.25,
    maturation_delay=5.0,
)


# ── Tests: carbon price ───────────────────────────────────────────────────────


class TestCarbonPrice:
    """The default carbon price is the social cost of carbon (decision D3)."""

    def test_scc_is_epa_central_estimate_in_euros(self):
        assert SCC_USD_2020_PER_T == 190.0
        assert USD_PER_EUR_2020 == 1.1422
        assert SOCIAL_COST_OF_CARBON_EUR == pytest.approx(190.0 / 1.1422)
        assert SOCIAL_COST_OF_CARBON_EUR == pytest.approx(166.35, abs=0.01)

    def test_scc_growth_matches_epa_trajectory(self):
        """$190 (2020) → $410 (2080) at the 2% near-term rate: ~1.29%/yr."""
        assert SCC_GROWTH_RATE == pytest.approx((410 / 190) ** (1 / 60) - 1, abs=5e-4)

    def test_default_discount_config_uses_scc(self):
        config = DiscountConfig()
        assert config.carbon_price_current == SOCIAL_COST_OF_CARBON_EUR
        assert config.carbon_price_growth == SCC_GROWTH_RATE

    @pytest.mark.parametrize("profile", [
        DISCOUNT_MARKET, DISCOUNT_CENTRAL, DISCOUNT_ENVIRONMENTAL, DISCOUNT_GREEN_BOOK,
    ])
    def test_builtin_profiles_use_scc_growing_slower_than_discount(self, profile):
        assert profile.carbon_price_current == SOCIAL_COST_OF_CARBON_EUR
        min_rate = min(profile.rate_at_year(t) for t in range(profile.horizon_years))
        assert profile.carbon_price_growth < min_rate

    def test_explicit_price_is_kept(self):
        config = DiscountConfig(carbon_price_current=120.0, carbon_price_growth=0.0)
        assert config.carbon_price_current == 120.0
        assert config.carbon_price_growth == 0.0

    def test_ets_view_is_optional_and_labelled(self):
        ets = with_carbon_price_view(DISCOUNT_CENTRAL, "ets")
        assert ets.carbon_price_current == ETS_CARBON_PRICE_EUR == 80.0
        assert ets.carbon_price_growth == DISCOUNT_CENTRAL.carbon_price_growth
        scc = with_carbon_price_view(ets, "scc")
        assert scc.carbon_price_current == SOCIAL_COST_OF_CARBON_EUR

    def test_unknown_view_rejected(self):
        with pytest.raises(ValueError, match="carbon price view"):
            with_carbon_price_view(DISCOUNT_CENTRAL, "market")


# ── Tests: carbon release ─────────────────────────────────────────────────────


class TestCarbonRelease:
    """Tests for compute_carbon_release."""

    def test_includes_biomass_and_soil(self):
        """Release should include both stored carbon and soil carbon fraction."""
        release = compute_carbon_release(_FOREST_CARBON, 1)
        expected = 0.8 + 0.3 * 0.25  # 0.875
        assert abs(release - expected) < 1e-6

    def test_scales_with_units(self):
        """Release should scale linearly with units extracted."""
        r1 = compute_carbon_release(_FOREST_CARBON, 1)
        r100 = compute_carbon_release(_FOREST_CARBON, 100)
        assert abs(r100 - r1 * 100) < 1e-4

    def test_soil_release_fraction_bounded(self):
        """Only a fraction of soil carbon is released."""
        release_per_unit = compute_carbon_release(_FOREST_CARBON, 1)
        total_stored = 0.8 + 0.3  # biomass + all soil
        assert release_per_unit < total_stored




# ── Tests: carbon present values ──────────────────────────────────────────────


class TestCarbonPresentValues:
    """Release is a stock at the year-0 price; absorption a flow → PV."""

    def test_release_valued_at_year0_price(self):
        assert pv_carbon_release(10.0, DISCOUNT_CENTRAL) == pytest.approx(
            10.0 * SOCIAL_COST_OF_CARBON_EUR)

    def test_absorption_pv_closed_form(self):
        """Constant flow, constant rates: a growing annuity over t = 1..H."""
        config = DiscountConfig(rate_schedule=0.05, carbon_price_current=100.0,
                                carbon_price_growth=0.01, horizon_years=30)
        q = 1.01 / 1.05
        expected = 2.0 * 100.0 * q * (1 - q ** 30) / (1 - q)
        assert pv_absorption(2.0, config) == pytest.approx(expected, rel=1e-12)

    def test_absorption_and_shortfall_sum_to_full_flow(self):
        full = pv_absorption(3.0, DISCOUNT_CENTRAL)
        got = pv_absorption(3.0, DISCOUNT_CENTRAL, _FOREST_SUCCESSION, 0.8)
        missing = pv_absorption(3.0, DISCOUNT_CENTRAL, _FOREST_SUCCESSION, 0.8,
                                shortfall=True)
        assert got + missing == pytest.approx(full, rel=1e-12)
        assert 0.0 < got < full

    def test_unpriced_absorption_is_discounted_tonnes(self):
        config = dataclasses.replace(DISCOUNT_CENTRAL, carbon_price_growth=0.0)
        priced = pv_absorption(1.0, config)
        tonnes = pv_absorption(1.0, config, priced=False)
        assert priced == pytest.approx(tonnes * config.carbon_price_current)

    def test_absorption_pv_converges_with_horizon(self):
        """SCC growth < discount rate: doubling a long horizon adds little."""
        pv_500 = pv_absorption(
            1.0, dataclasses.replace(DISCOUNT_CENTRAL, horizon_years=500))
        pv_1000 = pv_absorption(
            1.0, dataclasses.replace(DISCOUNT_CENTRAL, horizon_years=1000))
        assert pv_1000 < 1.01 * pv_500


# ── Tests: carbon cost ─────────────────────────────────────────────────────────


class TestCarbonCost:
    """Tests for compute_carbon_cost (S7: a stock is never added to a flow)."""

    def test_cost_equals_tonnes_times_price(self):
        """Release cost = release tonnes × year-0 price exactly."""
        result = compute_carbon_cost(_FOREST_CARBON, 100, DISCOUNT_CENTRAL)
        release = compute_carbon_release(_FOREST_CARBON, 100)
        expected_cost = release * DISCOUNT_CENTRAL.carbon_price_current
        assert abs(result["release_cost_eur"] - expected_cost) < 1e-4

    def test_total_adds_two_present_values(self):
        """The total is release (stock) + PV of foregone absorption (stock)."""
        result = compute_carbon_cost(_FOREST_CARBON, 100, DISCOUNT_CENTRAL)
        assert result["foregone_cost_pv_eur"] == pytest.approx(
            pv_absorption(100 * 0.022, DISCOUNT_CENTRAL))
        assert result["total_cost_pv_eur"] == pytest.approx(
            result["release_cost_eur"] + result["foregone_cost_pv_eur"])
        assert "total_cost" not in result
        assert "foregone_cost_per_year" not in result

    def test_zero_units(self):
        """Zero extraction should give zero cost."""
        result = compute_carbon_cost(_FOREST_CARBON, 0, DISCOUNT_CENTRAL)
        assert result["release_cost_eur"] == 0.0
        assert result["foregone_cost_pv_eur"] == 0.0


# ── Tests: annual absorption ──────────────────────────────────────────────────


class TestAnnualAbsorption:
    """Tests for compute_annual_absorption."""

    def test_scales_with_service_fraction(self):
        """Absorption at half service = half of max absorption."""
        full = compute_annual_absorption(_FOREST_CARBON, 100, 1.0)
        half = compute_annual_absorption(_FOREST_CARBON, 100, 0.5)
        assert abs(half - full * 0.5) < 1e-6

    def test_zero_service_zero_absorption(self):
        """During delay period (service=0), absorption should be zero."""
        absorbed = compute_annual_absorption(_FOREST_CARBON, 100, 0.0)
        assert absorbed == 0.0


# ── Tests: carbon payback period ───────────────────────────────────────────────


class TestCarbonPaybackPeriod:
    """Tests for compute_carbon_payback_period."""

    def test_payback_always_positive(self):
        """Payback period should be > 0 for any extraction."""
        period = compute_carbon_payback_period(
            _FOREST_CARBON, 100, 100, _FOREST_SUCCESSION
        )
        assert period > 0

    def test_posidonia_payback_longer_than_forest(self):
        """Posidonia has much more stored carbon — payback should be longer."""
        forest_payback = compute_carbon_payback_period(
            _FOREST_CARBON, 100, 100, _FOREST_SUCCESSION
        )
        posidonia_payback = compute_carbon_payback_period(
            _POSIDONIA_CARBON, 100, 100, _POSIDONIA_SUCCESSION
        )
        assert posidonia_payback > forest_payback

    def test_zero_release_zero_payback(self):
        """Zero stored carbon → instant payback."""
        zero_profile = CarbonProfile(
            stored_carbon_tonnes=0.0,
            annual_absorption_tonnes=0.022,
            soil_carbon_tonnes=0.0,
            soil_release_fraction=0.0,
        )
        period = compute_carbon_payback_period(
            zero_profile, 100, 100, _FOREST_SUCCESSION
        )
        assert period == 0.0
