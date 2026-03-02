"""
Gaia v0.5 — Physical substrate computation.

Models the physical substrate beneath ecosystems: soil depth for terrestrial
systems, water clarity and matte integrity for marine systems. Substrate state
constrains carrying capacity and degrades when vegetation cover is lost.

Scientific basis:
    - Soil formation: 0.3–1.4 t/ha/yr (ESDAC JRC, Montgomery 2007)
    - Mediterranean erosion: 20–40 t/ha/yr on bare slopes (ESDAC)
    - Posidonia matte accretion: ~1 mm/yr (Monnier et al. 2020)
    - Bulk density for t/ha -> mm conversion: ~1,300 kg/m³

All code is Cython-compatible:
    - No dynamic attributes
    - No **kwargs
    - Primitive floats and ints in hot paths
    - No third-party dependencies
"""

import math
from typing import Optional

from gaia.models import SubstrateProfile, SubstrateState

# Bulk density for soil t/ha/yr → mm/yr conversion
# 1 t/ha = 10,000 kg / (10,000 m² * depth_m * bulk_density_kg_m3)
# Simplified: depth_mm_lost = rate_t_ha_yr / (bulk_density_kg_m3 / 10.0)
# At 1,300 kg/m³: 1 t/ha/yr ≈ 0.077 mm/yr
_BULK_DENSITY_KG_M3: float = 1300.0
_T_HA_TO_MM_FACTOR: float = 10.0 / _BULK_DENSITY_KG_M3  # ≈ 0.00769 mm per t/ha


def create_substrate_state(profile: SubstrateProfile) -> SubstrateState:
    """Create an initial SubstrateState from a SubstrateProfile.

    Sets all current values to pristine (profile) values.
    Capacity fraction starts at 1.0.

    Args:
        profile: The SubstrateProfile defining physical properties.

    Returns:
        A SubstrateState initialized to pristine condition.
    """
    return SubstrateState(
        profile=profile,
        current_soil_depth_cm=profile.soil_depth_cm,
        current_water_clarity_kd=profile.water_clarity_kd,
        current_sediment_stability=profile.sediment_stability,
        pristine_soil_depth_cm=profile.soil_depth_cm,
        pristine_water_clarity_kd=profile.water_clarity_kd,
        pristine_sediment_stability=profile.sediment_stability,
        capacity_fraction=1.0,
        years_to_recover=0.0,
    )


def compute_capacity_fraction(state: SubstrateState) -> float:
    """Compute carrying capacity fraction from current substrate state.

    Dispatches to linear, threshold, or logistic capacity function
    based on the profile configuration.

    Args:
        state: Current substrate state.

    Returns:
        Capacity fraction in [0.0, 1.0]. Updates state.capacity_fraction in place.
    """
    fn_type: str = state.profile.capacity_function

    if fn_type == "linear":
        frac = _capacity_linear(state)
    elif fn_type == "threshold":
        frac = _capacity_threshold(state)
    elif fn_type == "logistic":
        frac = _capacity_logistic(state)
    else:
        frac = _capacity_linear(state)

    # Clamp to [0.0, 1.0]
    if frac < 0.0:
        frac = 0.0
    elif frac > 1.0:
        frac = 1.0

    state.capacity_fraction = frac
    return frac


def _capacity_linear(state: SubstrateState) -> float:
    """Linear capacity: capacity = current / pristine.

    Use for systems where capacity degrades proportionally to substrate.
    """
    if state.current_soil_depth_cm is not None and state.pristine_soil_depth_cm is not None:
        if state.pristine_soil_depth_cm <= 0.0:
            return 0.0
        return state.current_soil_depth_cm / state.pristine_soil_depth_cm

    if (state.current_sediment_stability is not None
            and state.pristine_sediment_stability is not None):
        if state.pristine_sediment_stability <= 0.0:
            return 0.0
        return state.current_sediment_stability / state.pristine_sediment_stability

    return 1.0


def _capacity_threshold(state: SubstrateState) -> float:
    """Threshold capacity: cliff-edge below critical minimum.

    Below critical_minimum, capacity drops sharply to residual_fraction.
    Above critical_minimum, capacity scales linearly from residual up to 1.0.

    Use for holm oak on limestone — below ~8cm soil, trees cannot establish.
    """
    profile = state.profile
    critical: float = profile.critical_minimum
    residual: float = profile.residual_fraction

    if state.current_soil_depth_cm is not None and state.pristine_soil_depth_cm is not None:
        current: float = state.current_soil_depth_cm
        pristine: float = state.pristine_soil_depth_cm

        if pristine <= 0.0:
            return 0.0

        if current <= 0.0:
            return 0.0

        if current < critical:
            # Below critical minimum: steep drop toward zero
            if critical <= 0.0:
                return 0.0
            return (current / critical) * residual

        # Above critical minimum: linear from residual to 1.0
        if pristine <= critical:
            return 1.0
        return residual + (1.0 - residual) * (current - critical) / (pristine - critical)

    return 1.0


def _capacity_logistic(state: SubstrateState) -> float:
    """Logistic capacity: smooth S-curve for light-limited marine systems.

    For Posidonia: water clarity (Kd) determines habitable depth via
    Beer-Lambert law. The relationship between clarity and habitable area
    is smooth but nonlinear.

    Uses sediment_stability as primary metric for marine substrates.
    """
    if (state.current_sediment_stability is not None
            and state.pristine_sediment_stability is not None):
        if state.pristine_sediment_stability <= 0.0:
            return 0.0

        ratio: float = state.current_sediment_stability / state.pristine_sediment_stability

        # Logistic with inflection at 0.5, steepness 10
        steepness: float = 10.0
        inflection: float = 0.5
        raw: float = 1.0 / (1.0 + math.exp(-steepness * (ratio - inflection)))
        raw_at_0: float = 1.0 / (1.0 + math.exp(-steepness * (0.0 - inflection)))
        raw_at_1: float = 1.0 / (1.0 + math.exp(-steepness * (1.0 - inflection)))
        span: float = raw_at_1 - raw_at_0
        if span <= 0.0:
            return ratio
        return (raw - raw_at_0) / span

    return 1.0


def degrade_substrate(
    state: SubstrateState,
    vegetation_cover: float,
    years: float = 1.0,
) -> float:
    """Apply substrate degradation based on current vegetation cover.

    Erosion rate interpolates nonlinearly between protected and unprotected
    rates using the erosion_alpha exponent:
        effective_erosion = E_protected + (E_unprotected - E_protected) * (1 - cover)^alpha

    Args:
        state: Current substrate state (modified in place).
        vegetation_cover: Fraction of vegetation remaining, 0.0 (bare) to 1.0 (full).
        years: Time period to apply degradation over (default 1.0 year).

    Returns:
        Amount of erosion applied (in substrate-native units).
    """
    profile = state.profile
    alpha: float = profile.erosion_alpha

    # Clamp vegetation cover
    if vegetation_cover < 0.0:
        vegetation_cover = 0.0
    elif vegetation_cover > 1.0:
        vegetation_cover = 1.0

    # Compute effective erosion rate (nonlinear interpolation)
    bare_fraction: float = 1.0 - vegetation_cover
    if bare_fraction < 0.0:
        bare_fraction = 0.0

    exposure: float = bare_fraction ** alpha
    effective_erosion: float = (
        profile.erosion_rate_protected
        + (profile.erosion_rate_unprotected - profile.erosion_rate_protected) * exposure
    )

    # Apply erosion over time period
    erosion_amount: float = effective_erosion * years

    # Apply to the appropriate substrate property
    if state.current_soil_depth_cm is not None:
        # Convert t/ha/yr to mm/yr, then to cm
        erosion_mm: float = erosion_amount * _T_HA_TO_MM_FACTOR
        erosion_cm: float = erosion_mm / 10.0
        state.current_soil_depth_cm -= erosion_cm
        if state.current_soil_depth_cm < 0.0:
            state.current_soil_depth_cm = 0.0
        # Recompute capacity
        compute_capacity_fraction(state)
        return erosion_cm

    if state.current_sediment_stability is not None:
        # Marine: erosion_rate is in mm/yr, applied as fraction of stability
        # 5 mm/yr matte erosion on 0.85 stability -> gradual reduction
        # Normalize: treat erosion_rate as direct stability reduction per year
        # (scaled so that at full erosion rate, stability drops meaningfully)
        if state.pristine_sediment_stability is not None and state.pristine_sediment_stability > 0:
            # Erosion rate in mm/yr -> fraction of pristine stability lost per year
            stability_loss: float = (erosion_amount / 100.0)  # ~5mm/yr -> 0.05/yr
            state.current_sediment_stability -= stability_loss
            if state.current_sediment_stability < 0.0:
                state.current_sediment_stability = 0.0
        compute_capacity_fraction(state)
        return erosion_amount

    return 0.0


def recover_substrate(state: SubstrateState, years: float = 1.0) -> None:
    """Apply substrate recovery at the formation rate.

    Recovery is very slow — soil forms at 0.3–1.4 t/ha/yr,
    Posidonia matte accretes at ~1 mm/yr.

    Args:
        state: Current substrate state (modified in place).
        years: Time period to apply recovery over.
    """
    profile = state.profile
    recovery_amount: float = profile.formation_rate * years

    if state.current_soil_depth_cm is not None and state.pristine_soil_depth_cm is not None:
        # Convert t/ha/yr to cm
        recovery_mm: float = recovery_amount * _T_HA_TO_MM_FACTOR
        recovery_cm: float = recovery_mm / 10.0
        state.current_soil_depth_cm += recovery_cm
        if state.current_soil_depth_cm > state.pristine_soil_depth_cm:
            state.current_soil_depth_cm = state.pristine_soil_depth_cm
        compute_capacity_fraction(state)
        return

    if (state.current_sediment_stability is not None
            and state.pristine_sediment_stability is not None):
        # Marine: formation_rate in mm/yr -> stability recovery
        stability_gain: float = (recovery_amount / 100.0)
        state.current_sediment_stability += stability_gain
        if state.current_sediment_stability > state.pristine_sediment_stability:
            state.current_sediment_stability = state.pristine_sediment_stability
        compute_capacity_fraction(state)


def compute_substrate_recovery_years(state: SubstrateState) -> float:
    """Estimate years to return substrate to pristine condition.

    Based on the deficit between current and pristine state divided
    by the formation rate. For severely degraded substrates, this can
    be centuries to millennia.

    Args:
        state: Current substrate state.

    Returns:
        Estimated years to full substrate recovery. 0.0 if already pristine.
    """
    profile = state.profile

    if profile.formation_rate <= 0.0:
        # No natural recovery possible
        if state.current_soil_depth_cm is not None and state.pristine_soil_depth_cm is not None:
            if state.current_soil_depth_cm < state.pristine_soil_depth_cm:
                return float("inf")
        if (state.current_sediment_stability is not None
                and state.pristine_sediment_stability is not None):
            if state.current_sediment_stability < state.pristine_sediment_stability:
                return float("inf")
        return 0.0

    if state.current_soil_depth_cm is not None and state.pristine_soil_depth_cm is not None:
        deficit_cm: float = state.pristine_soil_depth_cm - state.current_soil_depth_cm
        if deficit_cm <= 0.0:
            state.years_to_recover = 0.0
            return 0.0
        # formation_rate is in t/ha/yr -> convert to cm/yr
        formation_cm_yr: float = profile.formation_rate * _T_HA_TO_MM_FACTOR / 10.0
        if formation_cm_yr <= 0.0:
            state.years_to_recover = float("inf")
            return float("inf")
        years: float = deficit_cm / formation_cm_yr
        state.years_to_recover = years
        return years

    if (state.current_sediment_stability is not None
            and state.pristine_sediment_stability is not None):
        deficit: float = state.pristine_sediment_stability - state.current_sediment_stability
        if deficit <= 0.0:
            state.years_to_recover = 0.0
            return 0.0
        # formation_rate in mm/yr -> stability gain per year
        formation_per_yr: float = profile.formation_rate / 100.0
        if formation_per_yr <= 0.0:
            state.years_to_recover = float("inf")
            return float("inf")
        years = deficit / formation_per_yr
        state.years_to_recover = years
        return years

    state.years_to_recover = 0.0
    return 0.0
