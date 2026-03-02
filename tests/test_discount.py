"""
Gaia v0.6 — DiscountConfig unit tests.

Tests the Ramsey discounting framework: discount_factor, rate_at_year,
carbon_price_at_year, scarcity_factor, and Ramsey auto-computation.

Spec Section 9.1 tests 1–8:
    1. discount_factor(0) == 1.0 for any rate
    2. Constant rate: discount_factor(10) ≈ 1/(1.023)^10
    3. Declining schedule: rate changes at correct year thresholds
    4. carbon_price_at_year(0) == 80.0; carbon_price_at_year(10) ≈ 107.51
    5. scarcity_factor(50) ≈ 1.02^50 ≈ 2.692 at 2%/yr
    6. __post_init__ computes rate_schedule = delta + eta*g when None
    7. Green Book schedule: verify rates at year 30, 31, 75, 76
    8. DISCOUNT_CENTRAL.rate_schedule ≈ 0.023; all four profiles exist
"""

import math
import pytest

from gaia.models import DiscountConfig
from gaia.discount import (
    DISCOUNT_MARKET,
    DISCOUNT_CENTRAL,
    DISCOUNT_ENVIRONMENTAL,
    DISCOUNT_GREEN_BOOK,
    OAK_VALLEY_DISCOUNT,
    COSTA_BRAVA_OAK_DISCOUNT,
    COSTA_BRAVA_POSIDONIA_DISCOUNT,
)


# ── Test 1: discount_factor(0) == 1.0 ─────────────────────────────────────────


def test_discount_factor_year_zero_constant_rate():
    """discount_factor(0) == 1.0 for a constant rate."""
    dc = DiscountConfig(rate_schedule=0.041)
    assert dc.discount_factor(0) == 1.0


def test_discount_factor_year_zero_declining_schedule():
    """discount_factor(0) == 1.0 for a declining rate schedule."""
    assert DISCOUNT_GREEN_BOOK.discount_factor(0) == 1.0


def test_discount_factor_year_zero_zero_rate():
    """discount_factor(0) == 1.0 even at zero rate."""
    dc = DiscountConfig(rate_schedule=0.0)
    assert dc.discount_factor(0) == 1.0


# ── Test 2: Constant rate discount_factor ─────────────────────────────────────


def test_discount_factor_constant_rate_year_10():
    """discount_factor(10) ≈ 1/(1.023)^10 for DISCOUNT_CENTRAL."""
    expected = 1.0 / (1.023 ** 10)
    assert DISCOUNT_CENTRAL.discount_factor(10) == pytest.approx(expected, rel=1e-9)


def test_discount_factor_constant_rate_year_1():
    """discount_factor(1) == 1/(1+r)."""
    dc = DiscountConfig(rate_schedule=0.05)
    assert dc.discount_factor(1) == pytest.approx(1.0 / 1.05, rel=1e-9)


def test_discount_factor_monotone_decreasing():
    """discount_factor is monotone decreasing with year (positive rate)."""
    dc = DISCOUNT_CENTRAL
    for t in range(1, 20):
        assert dc.discount_factor(t) < dc.discount_factor(t - 1)


# ── Test 3: Declining schedule rate thresholds ─────────────────────────────────


def test_rate_at_year_green_book_before_31():
    """Green Book rate = 3.5% for years 0 to 30."""
    dc = DISCOUNT_GREEN_BOOK
    assert dc.rate_at_year(0) == pytest.approx(0.035)
    assert dc.rate_at_year(30) == pytest.approx(0.035)


def test_rate_at_year_green_book_at_31():
    """Green Book rate switches to 3.0% at year 31."""
    dc = DISCOUNT_GREEN_BOOK
    assert dc.rate_at_year(31) == pytest.approx(0.030)
    assert dc.rate_at_year(75) == pytest.approx(0.030)


def test_rate_at_year_green_book_at_76():
    """Green Book rate switches to 2.5% at year 76."""
    dc = DISCOUNT_GREEN_BOOK
    assert dc.rate_at_year(76) == pytest.approx(0.025)
    assert dc.rate_at_year(125) == pytest.approx(0.025)


def test_declining_schedule_discount_factor_year_31():
    """Discount factor at year 31 compounds at two different rates."""
    dc = DISCOUNT_GREEN_BOOK
    # Years 1–30: 3.5%; year 31: 3.0%
    expected = (1.0 / 1.035) ** 30 / 1.030
    assert dc.discount_factor(31) == pytest.approx(expected, rel=1e-9)


# ── Test 4: Carbon price ───────────────────────────────────────────────────────


def test_carbon_price_at_year_zero():
    """carbon_price_at_year(0) == carbon_price_current for all profiles."""
    for dc in [DISCOUNT_MARKET, DISCOUNT_CENTRAL, DISCOUNT_ENVIRONMENTAL]:
        assert dc.carbon_price_at_year(0) == pytest.approx(dc.carbon_price_current)


def test_carbon_price_at_year_10_central():
    """carbon_price_at_year(10) ≈ 80 × 1.03^10 ≈ 107.51 for CENTRAL."""
    expected = 80.0 * (1.03 ** 10)
    assert DISCOUNT_CENTRAL.carbon_price_at_year(10) == pytest.approx(expected, rel=1e-9)


def test_carbon_price_grows_monotonically():
    """Carbon price increases every year (positive growth rate)."""
    dc = DISCOUNT_CENTRAL
    for t in range(0, 20):
        assert dc.carbon_price_at_year(t + 1) > dc.carbon_price_at_year(t)


# ── Test 5: Scarcity factor ────────────────────────────────────────────────────


def test_scarcity_factor_50yr_at_2pct():
    """scarcity_factor(50) ≈ 1.02^50 ≈ 2.6916 at 2%/yr."""
    expected = 1.02 ** 50
    assert DISCOUNT_CENTRAL.scarcity_factor(50) == pytest.approx(expected, rel=1e-9)


def test_scarcity_factor_year_zero():
    """scarcity_factor(0) == 1.0 always."""
    for dc in [DISCOUNT_MARKET, DISCOUNT_CENTRAL, DISCOUNT_ENVIRONMENTAL]:
        assert dc.scarcity_factor(0) == pytest.approx(1.0)


def test_scarcity_factor_zero_rate():
    """scarcity_factor == 1.0 at all years when scarcity_rate=0."""
    dc = DISCOUNT_MARKET  # scarcity_rate=0.0
    assert dc.scarcity_factor(0) == pytest.approx(1.0)
    assert dc.scarcity_factor(50) == pytest.approx(1.0)
    assert dc.scarcity_factor(100) == pytest.approx(1.0)


def test_scarcity_factor_monotone_increasing():
    """scarcity_factor increases with year (positive scarcity_rate)."""
    dc = DISCOUNT_CENTRAL
    for t in range(0, 20):
        assert dc.scarcity_factor(t + 1) > dc.scarcity_factor(t)


# ── Test 6: Ramsey auto-computation ───────────────────────────────────────────


def test_ramsey_auto_rate_when_none():
    """DiscountConfig with rate_schedule=None computes δ + η × g."""
    dc = DiscountConfig(delta=0.005, eta=1.35, g=0.013, rate_schedule=None)
    expected_rate = 0.005 + 1.35 * 0.013  # = 0.02255
    assert isinstance(dc.rate_schedule, float)
    assert dc.rate_schedule == pytest.approx(expected_rate, rel=1e-12)


def test_ramsey_auto_rate_used_in_discount_factor():
    """Auto-computed Ramsey rate is used by discount_factor."""
    dc = DiscountConfig(delta=0.005, eta=1.35, g=0.013, rate_schedule=None)
    computed_rate = 0.005 + 1.35 * 0.013
    expected_df = 1.0 / (1.0 + computed_rate) ** 5
    assert dc.discount_factor(5) == pytest.approx(expected_df, rel=1e-12)


def test_ramsey_default_config():
    """Default DiscountConfig() uses Ramsey auto-computation."""
    dc = DiscountConfig()
    # delta=0.005, eta=1.35, g=0.013 → r = 0.02255
    expected = 0.005 + 1.35 * 0.013
    assert dc.rate_schedule == pytest.approx(expected, rel=1e-12)


# ── Test 7: Green Book declining discount factor ───────────────────────────────


def test_green_book_discount_factor_year_30():
    """Year 30 discount factor compounds at 3.5%."""
    dc = DISCOUNT_GREEN_BOOK
    expected = (1.0 / 1.035) ** 30
    assert dc.discount_factor(30) == pytest.approx(expected, rel=1e-9)


def test_green_book_discount_factor_declining_below_constant():
    """Green Book NPV at year 80 > constant-rate NPV (rates decline)."""
    dc_green = DISCOUNT_GREEN_BOOK
    dc_constant = DiscountConfig(rate_schedule=0.035, scarcity_rate=0.0,
                                  horizon_years=125)
    # Green Book gives higher discount factor (smaller discount) for distant years
    assert dc_green.discount_factor(80) > dc_constant.discount_factor(80)


# ── Test 8: Preconfigured profiles ────────────────────────────────────────────


def test_discount_central_rate_is_023():
    """DISCOUNT_CENTRAL has rate_schedule ≈ 0.023."""
    assert DISCOUNT_CENTRAL.rate_schedule == pytest.approx(0.023)


def test_all_four_standard_profiles_exist():
    """All four standard discount profiles are importable DiscountConfig instances."""
    for profile in [
        DISCOUNT_MARKET,
        DISCOUNT_CENTRAL,
        DISCOUNT_ENVIRONMENTAL,
        DISCOUNT_GREEN_BOOK,
    ]:
        assert isinstance(profile, DiscountConfig)


def test_standard_profiles_rate_ordering():
    """Market rate > Central rate > Environmental rate (ordering)."""
    market_rate = DISCOUNT_MARKET.rate_at_year(0)
    central_rate = DISCOUNT_CENTRAL.rate_at_year(0)
    env_rate = DISCOUNT_ENVIRONMENTAL.rate_at_year(0)
    assert market_rate > central_rate > env_rate


def test_market_no_scarcity():
    """DISCOUNT_MARKET has no scarcity adjustment (scarcity_rate=0.0)."""
    assert DISCOUNT_MARKET.scarcity_rate == pytest.approx(0.0)


def test_environmental_high_scarcity():
    """DISCOUNT_ENVIRONMENTAL has higher scarcity than DISCOUNT_CENTRAL."""
    assert DISCOUNT_ENVIRONMENTAL.scarcity_rate > DISCOUNT_CENTRAL.scarcity_rate


# ── Per-case profiles ──────────────────────────────────────────────────────────


def test_per_case_profiles_are_discount_configs():
    """Per-case profiles exist and are DiscountConfig instances."""
    for profile in [
        OAK_VALLEY_DISCOUNT,
        COSTA_BRAVA_OAK_DISCOUNT,
        COSTA_BRAVA_POSIDONIA_DISCOUNT,
    ]:
        assert isinstance(profile, DiscountConfig)


def test_oak_valley_discount_horizon():
    """OAK_VALLEY_DISCOUNT has 100yr horizon."""
    assert OAK_VALLEY_DISCOUNT.horizon_years == 100


def test_costa_brava_oak_productive_years():
    """COSTA_BRAVA_OAK_DISCOUNT has 200yr productive lifespan (holm oak longevity)."""
    assert COSTA_BRAVA_OAK_DISCOUNT.remaining_productive_years == 200


def test_costa_brava_oak_higher_scarcity():
    """COSTA_BRAVA_OAK_DISCOUNT has higher scarcity than OAK_VALLEY_DISCOUNT."""
    assert COSTA_BRAVA_OAK_DISCOUNT.scarcity_rate > OAK_VALLEY_DISCOUNT.scarcity_rate


def test_posidonia_discount_declining_schedule():
    """COSTA_BRAVA_POSIDONIA_DISCOUNT has a declining rate schedule (list)."""
    dc = COSTA_BRAVA_POSIDONIA_DISCOUNT
    assert isinstance(dc.rate_schedule, list)


def test_posidonia_discount_rates_at_thresholds():
    """POSIDONIA_DISCOUNT declining rates: 2.3% → 1.8% → 1.4%."""
    dc = COSTA_BRAVA_POSIDONIA_DISCOUNT
    assert dc.rate_at_year(0) == pytest.approx(0.023)
    assert dc.rate_at_year(30) == pytest.approx(0.023)
    assert dc.rate_at_year(31) == pytest.approx(0.018)
    assert dc.rate_at_year(100) == pytest.approx(0.018)
    assert dc.rate_at_year(101) == pytest.approx(0.014)


def test_posidonia_discount_horizon_200yr():
    """COSTA_BRAVA_POSIDONIA_DISCOUNT has 200yr analysis horizon."""
    assert COSTA_BRAVA_POSIDONIA_DISCOUNT.horizon_years == 200


def test_posidonia_discount_highest_scarcity():
    """POSIDONIA_DISCOUNT has highest scarcity of all per-case profiles."""
    assert (
        COSTA_BRAVA_POSIDONIA_DISCOUNT.scarcity_rate
        > COSTA_BRAVA_OAK_DISCOUNT.scarcity_rate
        > OAK_VALLEY_DISCOUNT.scarcity_rate
    )
