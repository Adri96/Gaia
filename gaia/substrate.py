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

from gaia.models import SubstrateProfile, SubstrateState, SubstrateType

# Bulk density for soil t/ha/yr → mm/yr conversion
# 1 t/ha = 1,000 kg / 10,000 m² = 0.1 kg/m²
# depth_m = 0.1 / bulk_density_kg_m3  →  depth_mm = 100 / bulk_density_kg_m3
# At 1,300 kg/m³: 1 t/ha ≈ 0.0769 mm (13 t/ha ≈ 1 mm)
_BULK_DENSITY_KG_M3: float = 1300.0
_T_HA_TO_MM_FACTOR: float = 100.0 / _BULK_DENSITY_KG_M3  # ≈ 0.0769 mm per t/ha


def is_terrestrial(profile: SubstrateProfile) -> bool:
    """True if the profile tracks soil depth (substrate_type terrestrial_soil).

    This is the single dispatch rule for substrate behaviour, shared by the
    pure-Python functions below and the Cython extraction loop.
    """
    return profile.substrate_type == SubstrateType.TERRESTRIAL_SOIL


def is_marine(profile: SubstrateProfile) -> bool:
    """True if the profile tracks sediment stability (any marine substrate_type)."""
    return profile.substrate_type in (
        SubstrateType.MARINE_SEDIMENT, SubstrateType.MARINE_MATTE,
    )


def _substrate_ratio(state: SubstrateState) -> Optional[float]:
    """current / pristine of the state variable selected by substrate_type.

    Returns None when the type is unknown or its state variable is unset
    (only possible for profiles that bypassed validation).
    """
    profile = state.profile
    if is_terrestrial(profile):
        current = state.current_soil_depth_cm
        pristine = state.pristine_soil_depth_cm
    elif is_marine(profile):
        current = state.current_sediment_stability
        pristine = state.pristine_sediment_stability
    else:
        return None
    if current is None or pristine is None:
        return None
    if pristine <= 0.0:
        return 0.0
    return current / pristine


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
    ratio = _substrate_ratio(state)
    if ratio is None:
        return 1.0
    return ratio


def _capacity_threshold(state: SubstrateState) -> float:
    """Threshold capacity: cliff-edge below critical minimum.

    Below critical_minimum, capacity drops sharply to residual_fraction.
    Above critical_minimum, capacity scales linearly from residual up to 1.0.

    Use for holm oak on limestone — below ~8cm soil, trees cannot establish.
    Terrestrial only: validation rejects threshold for marine substrates.
    """
    profile = state.profile
    critical: float = profile.critical_minimum
    residual: float = profile.residual_fraction

    if (is_terrestrial(profile)
            and state.current_soil_depth_cm is not None
            and state.pristine_soil_depth_cm is not None):
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
    """Logistic capacity: smooth S-curve of the substrate ratio.

    Designed for light-limited marine systems (Posidonia: water clarity
    determines habitable depth via Beer-Lambert, a smooth but nonlinear
    relationship), where the ratio is sediment stability. The curve depends
    only on current/pristine, so terrestrial profiles apply it to soil depth,
    exactly as the Cython loop does.
    """
    ratio = _substrate_ratio(state)
    if ratio is None:
        return 1.0

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
    if is_terrestrial(profile) and state.current_soil_depth_cm is not None:
        # Convert t/ha/yr to mm/yr, then to cm
        erosion_mm: float = erosion_amount * _T_HA_TO_MM_FACTOR
        erosion_cm: float = erosion_mm / 10.0
        apply_erosion(state, erosion_cm)
        return erosion_cm

    if is_marine(profile) and state.current_sediment_stability is not None:
        apply_erosion(state, erosion_amount)
        return erosion_amount

    return 0.0


def apply_erosion(state: SubstrateState, erosion: float) -> None:
    """Remove an amount of substrate, in the units degrade_substrate returns.

    Terrestrial: ``erosion`` is cm of soil. Marine: mm of matte, applied as
    a loss of sediment stability (erosion / 100 per mm, so ~5 mm/yr of matte
    erosion removes 0.05 stability per year). Values are floored at 0 and the
    capacity fraction is recomputed.

    Replaying the per-step ``substrate_erosion`` of an extraction through
    this function reproduces the substrate state the extraction ended in,
    which is how a restoration inherits it (gaia.simulation).

    Args:
        state: Current substrate state (modified in place).
        erosion: Erosion amount (cm of soil, or mm of matte).
    """
    profile = state.profile
    if is_terrestrial(profile) and state.current_soil_depth_cm is not None:
        state.current_soil_depth_cm -= erosion
        if state.current_soil_depth_cm < 0.0:
            state.current_soil_depth_cm = 0.0
        compute_capacity_fraction(state)
        return

    if is_marine(profile) and state.current_sediment_stability is not None:
        if state.pristine_sediment_stability is not None and state.pristine_sediment_stability > 0:
            stability_loss: float = (erosion / 100.0)
            state.current_sediment_stability -= stability_loss
            if state.current_sediment_stability < 0.0:
                state.current_sediment_stability = 0.0
        compute_capacity_fraction(state)


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

    if (is_terrestrial(profile)
            and state.current_soil_depth_cm is not None
            and state.pristine_soil_depth_cm is not None):
        # Convert t/ha/yr to cm
        recovery_mm: float = recovery_amount * _T_HA_TO_MM_FACTOR
        recovery_cm: float = recovery_mm / 10.0
        state.current_soil_depth_cm += recovery_cm
        if state.current_soil_depth_cm > state.pristine_soil_depth_cm:
            state.current_soil_depth_cm = state.pristine_soil_depth_cm
        compute_capacity_fraction(state)
        return

    if (is_marine(profile)
            and state.current_sediment_stability is not None
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
        if (is_terrestrial(profile)
                and state.current_soil_depth_cm is not None
                and state.pristine_soil_depth_cm is not None):
            if state.current_soil_depth_cm < state.pristine_soil_depth_cm:
                return float("inf")
        if (is_marine(profile)
                and state.current_sediment_stability is not None
                and state.pristine_sediment_stability is not None):
            if state.current_sediment_stability < state.pristine_sediment_stability:
                return float("inf")
        return 0.0

    if (is_terrestrial(profile)
            and state.current_soil_depth_cm is not None
            and state.pristine_soil_depth_cm is not None):
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

    if (is_marine(profile)
            and state.current_sediment_stability is not None
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
