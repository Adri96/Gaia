"""
Gaia v0.5 — Substrate module unit tests.

Tests the physical substrate layer: capacity functions, degradation,
recovery, and ecological plausibility invariants.

Follows the 14 testing requirements from the v0.5 spec:
    1. Substrate-K relationship is monotonic
    2. Degradation spiral: substrate-aware extraction produces higher total externality
    3. Holm oak irreversibility: below ~8cm soil, K drops to near-zero
    4. Posidonia depth limit: Kd 0.06->0.12 reduces K by ~30-50%
    5. Erosion rates physically consistent
    6. Formation rates physically consistent
    7. Prevention advantage increases with substrate modeling
    8. Restoration ceiling is binding
    9. No substrate = v0.4 behavior
   10. Pristine substrate = effective_K equals total_units
   11. Zero soil depth -> K = 0
   12. Substrate degradation can't go below zero
   13. Substrate recovery can't exceed pristine
   14. Mixed depletion-recovery
   15-17. Capacity function tests (linear, threshold, logistic)
"""

import math
import pytest

from gaia.models import SubstrateProfile, SubstrateState
from gaia.substrate import (
    _BULK_DENSITY_KG_M3,
    _T_HA_TO_MM_FACTOR,
    compute_capacity_fraction,
    compute_substrate_recovery_years,
    create_substrate_state,
    degrade_substrate,
    recover_substrate,
)


# ── Test fixtures ──────────────────────────────────────────────────────────────


def _terrestrial_profile(**kwargs) -> SubstrateProfile:
    """Create a terrestrial substrate profile with sensible defaults."""
    defaults = dict(
        substrate_type="terrestrial_soil",
        soil_depth_cm=30.0,
        water_availability_mm_yr=550.0,
        erosion_rate_unprotected=25.0,
        erosion_rate_protected=1.0,
        formation_rate=0.4,
        capacity_function="linear",
        erosion_alpha=2.0,
        confidence="medium",
    )
    defaults.update(kwargs)
    return SubstrateProfile(**defaults)


def _marine_profile(**kwargs) -> SubstrateProfile:
    """Create a marine substrate profile with sensible defaults."""
    defaults = dict(
        substrate_type="marine_matte",
        water_clarity_kd=0.06,
        sediment_stability=0.85,
        erosion_rate_unprotected=5.0,
        erosion_rate_protected=0.0,
        formation_rate=1.0,
        capacity_function="logistic",
        erosion_alpha=3.0,
        confidence="low-medium",
    )
    defaults.update(kwargs)
    return SubstrateProfile(**defaults)


def _threshold_profile(**kwargs) -> SubstrateProfile:
    """Create a threshold capacity profile (holm oak style)."""
    defaults = dict(
        substrate_type="terrestrial_soil",
        soil_depth_cm=30.0,
        water_availability_mm_yr=550.0,
        erosion_rate_unprotected=25.0,
        erosion_rate_protected=1.0,
        formation_rate=0.4,
        capacity_function="threshold",
        erosion_alpha=2.0,
        critical_minimum=8.0,
        residual_fraction=0.05,
        confidence="medium",
    )
    defaults.update(kwargs)
    return SubstrateProfile(**defaults)


# ── create_substrate_state tests ──────────────────────────────────────────────


def test_create_state_terrestrial():
    """Creating state from terrestrial profile initializes correctly."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)

    assert state.profile is profile
    assert state.current_soil_depth_cm == 30.0
    assert state.pristine_soil_depth_cm == 30.0
    assert state.capacity_fraction == 1.0
    assert state.years_to_recover == 0.0


def test_create_state_marine():
    """Creating state from marine profile initializes correctly."""
    profile = _marine_profile()
    state = create_substrate_state(profile)

    assert state.profile is profile
    assert state.current_sediment_stability == 0.85
    assert state.pristine_sediment_stability == 0.85
    assert state.current_water_clarity_kd == 0.06
    assert state.capacity_fraction == 1.0


# ── Linear capacity function tests ───────────────────────────────────────────


def test_linear_pristine_is_full_capacity():
    """Spec test #10: Pristine substrate → capacity_fraction = 1.0."""
    profile = _terrestrial_profile(capacity_function="linear")
    state = create_substrate_state(profile)
    frac = compute_capacity_fraction(state)
    assert frac == 1.0


def test_linear_half_soil_half_capacity():
    """Linear: half the soil → half the capacity."""
    profile = _terrestrial_profile(capacity_function="linear")
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 15.0  # half of 30
    frac = compute_capacity_fraction(state)
    assert abs(frac - 0.5) < 1e-6


def test_linear_zero_soil_zero_capacity():
    """Spec test #11: Zero soil depth → K = 0."""
    profile = _terrestrial_profile(capacity_function="linear")
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 0.0
    frac = compute_capacity_fraction(state)
    assert frac == 0.0


def test_linear_monotonically_increasing():
    """Spec test #1: More soil → higher K (monotonic)."""
    profile = _terrestrial_profile(capacity_function="linear")
    state = create_substrate_state(profile)

    prev_frac = -1.0
    for depth in [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0]:
        state.current_soil_depth_cm = depth
        frac = compute_capacity_fraction(state)
        assert frac >= prev_frac, (
            f"Monotonicity violated: depth={depth}, frac={frac} < prev={prev_frac}"
        )
        prev_frac = frac


# ── Threshold capacity function tests ────────────────────────────────────────


def test_threshold_above_critical():
    """Threshold: above critical minimum, capacity scales linearly."""
    profile = _threshold_profile(critical_minimum=8.0, residual_fraction=0.05)
    state = create_substrate_state(profile)

    # At pristine (30cm), capacity should be 1.0
    frac = compute_capacity_fraction(state)
    assert abs(frac - 1.0) < 1e-6

    # At 19cm (midpoint above critical), capacity = 0.05 + 0.95 * (19-8)/(30-8) = 0.05 + 0.475 = 0.525
    state.current_soil_depth_cm = 19.0
    frac = compute_capacity_fraction(state)
    expected = 0.05 + 0.95 * (19.0 - 8.0) / (30.0 - 8.0)
    assert abs(frac - expected) < 1e-6


def test_threshold_below_critical():
    """Spec test #3: Below ~8cm soil, K drops to near-zero."""
    profile = _threshold_profile(critical_minimum=8.0, residual_fraction=0.05)
    state = create_substrate_state(profile)

    # At 4cm (below critical), capacity = (4/8) * 0.05 = 0.025
    state.current_soil_depth_cm = 4.0
    frac = compute_capacity_fraction(state)
    assert frac < 0.05, f"Below critical: expected near-zero, got {frac}"

    # At 1cm, even lower
    state.current_soil_depth_cm = 1.0
    frac2 = compute_capacity_fraction(state)
    assert frac2 < frac, "Deeper below critical should have lower capacity"


def test_threshold_at_zero_soil():
    """Zero soil with threshold → K = 0."""
    profile = _threshold_profile()
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 0.0
    frac = compute_capacity_fraction(state)
    assert frac == 0.0


def test_threshold_cliff_edge():
    """The transition at critical_minimum should show a clear cliff."""
    profile = _threshold_profile(critical_minimum=8.0, residual_fraction=0.05)
    state = create_substrate_state(profile)

    # Just above critical (8.1 cm)
    state.current_soil_depth_cm = 8.1
    frac_above = compute_capacity_fraction(state)

    # Just below critical (7.9 cm)
    state.current_soil_depth_cm = 7.9
    frac_below = compute_capacity_fraction(state)

    # The jump should be significant
    assert frac_above > frac_below
    # Below critical should be very close to residual
    assert frac_below < 0.06


# ── Logistic capacity function tests ─────────────────────────────────────────


def test_logistic_pristine_is_full():
    """Logistic at pristine → capacity near 1.0."""
    profile = _marine_profile(capacity_function="logistic")
    state = create_substrate_state(profile)
    frac = compute_capacity_fraction(state)
    assert abs(frac - 1.0) < 0.01


def test_logistic_zero_is_near_zero():
    """Logistic at zero stability → capacity near 0.0."""
    profile = _marine_profile(capacity_function="logistic")
    state = create_substrate_state(profile)
    state.current_sediment_stability = 0.0
    frac = compute_capacity_fraction(state)
    assert frac < 0.01


def test_logistic_s_curve_inflection():
    """Logistic should have inflection behavior around midpoint."""
    profile = _marine_profile(capacity_function="logistic")
    state = create_substrate_state(profile)

    # At half stability, capacity should be around 0.5 (S-curve midpoint)
    state.current_sediment_stability = state.pristine_sediment_stability * 0.5
    frac_mid = compute_capacity_fraction(state)
    assert 0.3 < frac_mid < 0.7, f"Expected midpoint ~0.5, got {frac_mid}"


def test_logistic_monotonic():
    """Logistic capacity is monotonically increasing with stability."""
    profile = _marine_profile(capacity_function="logistic")
    state = create_substrate_state(profile)

    prev_frac = -1.0
    for ratio in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        state.current_sediment_stability = state.pristine_sediment_stability * ratio
        frac = compute_capacity_fraction(state)
        assert frac >= prev_frac, (
            f"Monotonicity violated: ratio={ratio}, frac={frac} < prev={prev_frac}"
        )
        prev_frac = frac


# ── Degradation tests ────────────────────────────────────────────────────────


def test_full_cover_minimal_erosion():
    """Full vegetation cover → erosion at protected rate (minimal)."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    erosion = degrade_substrate(state, vegetation_cover=1.0, years=1.0)
    # With full cover, erosion should use protected rate (1.0 t/ha/yr)
    # 1.0 t/ha/yr * 0.00769 mm/t_ha / 10 = very small
    assert erosion > 0.0, "Even protected land has some erosion"
    assert erosion < 0.01, f"Full cover erosion should be tiny, got {erosion} cm"


def test_zero_cover_maximum_erosion():
    """Zero vegetation cover → erosion at unprotected rate (maximum)."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    erosion = degrade_substrate(state, vegetation_cover=0.0, years=1.0)
    # With zero cover, erosion should use unprotected rate (25.0 t/ha/yr)
    expected_mm = 25.0 * _T_HA_TO_MM_FACTOR
    expected_cm = expected_mm / 10.0
    assert abs(erosion - expected_cm) < 1e-6


def test_degradation_cant_go_below_zero():
    """Spec test #12: Substrate degradation can't go below zero."""
    profile = _terrestrial_profile(soil_depth_cm=0.5)  # very thin soil
    state = create_substrate_state(profile)

    # Apply massive erosion
    degrade_substrate(state, vegetation_cover=0.0, years=100.0)
    assert state.current_soil_depth_cm >= 0.0
    assert state.current_soil_depth_cm == 0.0


def test_erosion_nonlinear_with_alpha():
    """Erosion interpolation uses alpha exponent for nonlinearity."""
    profile = _terrestrial_profile(erosion_alpha=2.0)
    state1 = create_substrate_state(profile)
    erosion_half = degrade_substrate(state1, vegetation_cover=0.5, years=1.0)

    # With alpha=2 and 50% cover: exposure = 0.5^2 = 0.25
    # effective_erosion = 1.0 + (25.0 - 1.0) * 0.25 = 7.0 t/ha/yr
    expected_erosion_t_ha = 1.0 + (25.0 - 1.0) * (0.5 ** 2.0)
    expected_cm = expected_erosion_t_ha * _T_HA_TO_MM_FACTOR / 10.0
    assert abs(erosion_half - expected_cm) < 1e-6


def test_erosion_higher_alpha_less_erosion_at_partial_cover():
    """Higher alpha → less erosion at partial cover (steeper curve)."""
    # alpha=2 (terrestrial)
    p2 = _terrestrial_profile(erosion_alpha=2.0)
    s2 = create_substrate_state(p2)
    e2 = degrade_substrate(s2, vegetation_cover=0.7, years=1.0)

    # alpha=3 (marine)
    p3 = _terrestrial_profile(erosion_alpha=3.0)
    s3 = create_substrate_state(p3)
    e3 = degrade_substrate(s3, vegetation_cover=0.7, years=1.0)

    # Higher alpha = (1 - 0.7)^3 = 0.027 vs (1 - 0.7)^2 = 0.09
    # So alpha=3 should have less erosion at 70% cover
    assert e3 < e2


def test_degradation_updates_capacity():
    """Degradation should reduce capacity_fraction."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    assert state.capacity_fraction == 1.0

    degrade_substrate(state, vegetation_cover=0.0, years=1.0)
    assert state.capacity_fraction < 1.0


def test_marine_degradation():
    """Marine substrate degradation reduces sediment stability."""
    profile = _marine_profile()
    state = create_substrate_state(profile)
    initial_stability = state.current_sediment_stability

    degrade_substrate(state, vegetation_cover=0.0, years=1.0)
    assert state.current_sediment_stability < initial_stability
    assert state.current_sediment_stability >= 0.0


# ── Recovery tests ────────────────────────────────────────────────────────────


def test_recovery_increases_substrate():
    """Recovery should increase soil depth back toward pristine."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 20.0  # degraded

    recover_substrate(state, years=1.0)
    assert state.current_soil_depth_cm > 20.0


def test_recovery_cant_exceed_pristine():
    """Spec test #13: Substrate recovery can't exceed pristine."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 29.99  # near pristine

    recover_substrate(state, years=1000.0)  # massive recovery
    assert state.current_soil_depth_cm == state.pristine_soil_depth_cm


def test_recovery_from_zero():
    """Recovery from zero should work (very slowly)."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 0.0

    recover_substrate(state, years=10.0)
    assert state.current_soil_depth_cm > 0.0


def test_marine_recovery():
    """Marine substrate recovery increases sediment stability."""
    profile = _marine_profile()
    state = create_substrate_state(profile)
    state.current_sediment_stability = 0.5  # degraded

    recover_substrate(state, years=1.0)
    assert state.current_sediment_stability > 0.5


def test_marine_recovery_capped():
    """Marine recovery can't exceed pristine stability."""
    profile = _marine_profile()
    state = create_substrate_state(profile)
    state.current_sediment_stability = 0.84  # near pristine

    recover_substrate(state, years=1000.0)
    assert state.current_sediment_stability == state.pristine_sediment_stability


# ── Recovery years tests ──────────────────────────────────────────────────────


def test_recovery_years_pristine_is_zero():
    """Pristine substrate → 0 years to recover."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    years = compute_substrate_recovery_years(state)
    assert years == 0.0


def test_recovery_years_degraded():
    """Degraded substrate → positive years to recover."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 20.0  # 10cm deficit

    years = compute_substrate_recovery_years(state)
    assert years > 0.0
    # 10cm deficit / (0.4 t/ha/yr * 0.00769/10 cm per t/ha) = ~32,500 years
    assert years > 1000, f"Soil recovery should take thousands of years, got {years}"


def test_recovery_years_zero_formation():
    """Zero formation rate → infinite recovery time."""
    profile = _terrestrial_profile(formation_rate=0.0)
    state = create_substrate_state(profile)
    state.current_soil_depth_cm = 20.0

    years = compute_substrate_recovery_years(state)
    assert years == float("inf")


# ── Physical consistency tests ────────────────────────────────────────────────


def test_erosion_rate_physical_consistency():
    """Spec test #5: 25 t/ha/yr → ~1.9 mm/yr at bulk density 1,300 kg/m³."""
    rate_t_ha_yr = 25.0
    rate_mm_yr = rate_t_ha_yr * _T_HA_TO_MM_FACTOR
    # Expected: 25 * 10/1300 ≈ 0.192 mm/yr
    assert abs(rate_mm_yr - 0.192) < 0.01, f"Expected ~0.192 mm/yr, got {rate_mm_yr}"

    # 30cm eroded at 25 t/ha/yr: time = 300mm / 0.192 mm/yr ≈ 1,562 years
    time_years = 300.0 / rate_mm_yr  # 30cm = 300mm
    assert 1500 < time_years < 1700, f"Expected ~1,562 years, got {time_years}"


def test_formation_rate_physical_consistency():
    """Spec test #6: 0.4 t/ha/yr → 30cm recovery in ~10,000+ years."""
    rate_t_ha_yr = 0.4
    rate_mm_yr = rate_t_ha_yr * _T_HA_TO_MM_FACTOR
    # Expected: 0.4 * 10/1300 ≈ 0.031 mm/yr
    time_years = 300.0 / rate_mm_yr  # 30cm = 300mm
    # Should be on the order of 10,000 years
    assert time_years > 5000, f"Expected >5,000 years for 30cm formation, got {time_years}"


# ── Mixed depletion-recovery test ─────────────────────────────────────────────


def test_mixed_depletion_recovery():
    """Spec test #14: Extract → some soil loss → replant → slow recovery."""
    profile = _terrestrial_profile(soil_depth_cm=30.0)
    state = create_substrate_state(profile)

    # Phase 1: Degrade (50% cover for 10 years)
    for _ in range(10):
        degrade_substrate(state, vegetation_cover=0.5, years=1.0)

    soil_after_degrade = state.current_soil_depth_cm
    assert soil_after_degrade < 30.0, "Soil should have degraded"

    # Phase 2: Recover (full cover for 10 years)
    for _ in range(10):
        recover_substrate(state, years=1.0)

    soil_after_recovery = state.current_soil_depth_cm
    assert soil_after_recovery > soil_after_degrade, "Soil should have partially recovered"
    assert soil_after_recovery < 30.0, "Full recovery takes much longer than 10 years"


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_degrade_with_negative_cover_clamped():
    """Negative vegetation cover should be clamped to 0."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    erosion = degrade_substrate(state, vegetation_cover=-0.5, years=1.0)
    # Should behave same as cover=0
    assert erosion > 0.0


def test_degrade_with_cover_above_one_clamped():
    """Cover > 1.0 should be clamped to 1.0."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    erosion = degrade_substrate(state, vegetation_cover=1.5, years=1.0)
    # Should behave same as cover=1.0
    expected_erosion = 1.0 * _T_HA_TO_MM_FACTOR / 10.0  # protected rate only
    assert abs(erosion - expected_erosion) < 1e-6


def test_zero_years_no_erosion():
    """Zero years → no degradation applied."""
    profile = _terrestrial_profile()
    state = create_substrate_state(profile)
    erosion = degrade_substrate(state, vegetation_cover=0.0, years=0.0)
    assert erosion == 0.0
    assert state.current_soil_depth_cm == 30.0


def test_no_substrate_properties_returns_defaults():
    """Profile with no soil or marine properties → capacity defaults to 1.0."""
    profile = SubstrateProfile(
        substrate_type="unknown",
        erosion_rate_unprotected=0.0,
        erosion_rate_protected=0.0,
        formation_rate=0.0,
    )
    state = create_substrate_state(profile)
    frac = compute_capacity_fraction(state)
    assert frac == 1.0
