# cython: boundscheck=False, wraparound=False, cdivision=True
# cython: language_level=3
"""
Gaia v0.8 — Cython-optimized extraction simulation inner loop.

Drop-in replacement for the hot path in simulation.run_extraction().
The public function extraction_loop_cy() computes all simulation steps
with C-level typing, eliminating Python object overhead in the inner loop.

Performance profile of the pure-Python version (Amazon, 80K steps):
    propagate_interactions:  35% (dict rebuild per call, string lookups)
    main loop overhead:      40% (SimulationStep creation, list.append)
    damage functions:         9% (closure calls with math.exp)
    trophic amplification:    4% (880K function calls)
    substrate:               10% (attribute access, dispatch)
    ---
    Total: 5.2M function calls in ~2.1s

This module eliminates the function call overhead by:
    1. Pre-computing all indices (int arrays, not string dicts)
    2. Inlining trophic amplification (factors precomputed by the caller)
    3. Inlining interaction propagation (no per-step dict rebuild)
    4. Using C-level math (libc.math.exp instead of Python math.exp)
    5. Using typed memoryviews / C arrays for hot-path data

Usage from simulation.py: see simulation._load_cython_loop(), which only
uses this module when PYX_SOURCE_SHA256 matches the current .pyx source.

Build with ``python3 setup.py build_ext --inplace``: setup.py supplies the
GAIA_PYX_SHA256 compile-time constant (SHA-256 of this file).
"""

from libc.math cimport exp, pow

# SHA-256 of the .pyx source this module was compiled from (stale-build guard)
PYX_SOURCE_SHA256 = GAIA_PYX_SHA256


def extraction_loop_cy(
    int n_agents,
    int n_edges,
    int total_units,
    int units_to_extract,
    double unit_value,
    double safe_threshold_ratio,
    # Per-agent flat arrays (length n_agents):
    list damage_params,       # list of (kind, param1, param2, param3) tuples
    list dep_weights,         # dependency_weight per agent
    list annual_values,       # €/yr lost at full damage per agent (€/ha/yr × area_ha)
    list trophic_levels,      # trophic_level per agent (int)
    list trophic_amp_factors, # propagation.trophic_amplification_factor per agent
    list is_keystone,         # bool per agent
    list keystone_thresholds, # float per agent
    # Per-edge flat arrays (length n_edges):
    list edge_src_idx,        # int index of source agent
    list edge_tgt_idx,        # int index of target agent
    list edge_strengths,      # float strength [0, 1]
    # Keystone boost (gaia.constants, passed so the values have one source):
    double keystone_edge_multiplier,
    double max_edge_strength,
    # Feature flags:
    bint has_trophic,
    bint has_interactions,
    bint has_resilience,
    bint has_substrate,
    bint substrate_is_marine,
    # Resilience config (only used if has_resilience):
    double resilience_warning_width,
    double resilience_conf_green,
    double resilience_conf_yellow,
    double resilience_conf_red,
    double resilience_irreversibility_ratio,
    # Substrate config (only used if has_substrate). Terrestrial profiles
    # track soil depth (cm, erosion in t/ha/yr); marine profiles track
    # sediment stability (0-1, erosion in mm/yr):
    double substrate_soil_depth_cm,
    double substrate_sediment_stability,
    double substrate_erosion_unprotected,
    double substrate_erosion_protected,
    double substrate_formation_rate,
    double substrate_erosion_alpha,
    double substrate_critical_minimum,
    double substrate_residual_fraction,
    str substrate_capacity_function,
    double substrate_t_ha_to_mm_factor,
):
    """
    Cython-optimized extraction simulation inner loop.

    Computes all N steps of the extraction simulation with C-typed
    variables, returning a list of tuples containing the per-step data.
    The caller (simulation.py) converts these tuples into SimulationStep
    dataclasses.

    Returns:
        List of tuples, one per step:
        (step, units_extracted, depletion_ratio,
         effective_damages, agent_annual_costs, marginal_annual_externality,
         annual_externality, revenue, ecosystem_health,
         direct_damages, cascade_damages, keystone_triggered,
         zone, confidence, irreversibility_warning,
         substrate_erosion, effective_k, k_fraction)
    """
    # C-level declarations for the hot loop
    cdef int step, i, e, src_idx, tgt_idx
    cdef int units_extracted
    cdef double depletion_ratio, raw_damage, amplified
    cdef double amplification_factor
    cdef double step_total_cost, health_sum, marginal_cost, ecosystem_health
    cdef double private_revenue, cost, rate
    cdef double previous_total_cost = 0.0
    cdef double agent_health, doubled, additional, source_damage, headroom
    cdef double bare_fraction, exposure, effective_erosion, erosion_amount
    cdef double erosion_mm, erosion_cm
    cdef double remaining_frac, threshold_lower, threshold_upper
    cdef double zone_position, conf
    cdef double weight

    # Resilience zone variables (must be at function scope for Cython)
    cdef str zone
    cdef double confidence
    cdef bint irreversibility

    # Substrate state (mutable, C-level). One variable is tracked, chosen by
    # substrate_is_marine — the same rule as gaia.substrate.is_terrestrial().
    cdef double current_level
    cdef double pristine_level
    if substrate_is_marine:
        current_level = substrate_sediment_stability
    else:
        current_level = substrate_soil_depth_cm
    pristine_level = current_level
    cdef double time_per_step = 0.0
    cdef double step_substrate_erosion, step_k_fraction
    cdef int step_effective_k
    cdef double vegetation_cover

    # Capacity variables
    cdef double critical, residual, frac

    if has_substrate and units_to_extract > 0:
        time_per_step = 1.0 / <double>units_to_extract

    # Pre-extract damage function parameters into C arrays
    # Each damage function is represented as (kind, p1, p2, p3):
    #   logistic:    (0, inflection, raw_0, span, steepness)  -> we use 5 params
    #   exponential: (1, scale, raw_1, base, 0)
    #   piecewise:   (2, threshold, pre_slope, post_slope, pre_slope_ratio)
    cdef int n_dmg = n_agents
    cdef list dmg_kind = [0] * n_dmg
    cdef list dmg_p1 = [0.0] * n_dmg
    cdef list dmg_p2 = [0.0] * n_dmg
    cdef list dmg_p3 = [0.0] * n_dmg
    cdef list dmg_p4 = [0.0] * n_dmg

    for i in range(n_dmg):
        params = damage_params[i]
        dmg_kind[i] = <int>params[0]
        dmg_p1[i] = <double>params[1]
        dmg_p2[i] = <double>params[2]
        dmg_p3[i] = <double>params[3]
        dmg_p4[i] = <double>params[4]

    # Pre-extract per-agent arrays to C-level
    cdef list c_dep_weights = [<double>dep_weights[i] for i in range(n_agents)]
    cdef list c_annual_values = [<double>annual_values[i] for i in range(n_agents)]
    cdef list c_trophic = [<int>trophic_levels[i] for i in range(n_agents)]
    cdef list c_is_keystone = [<bint>is_keystone[i] for i in range(n_agents)]
    cdef list c_ks_thresholds = [<double>keystone_thresholds[i] for i in range(n_agents)]

    # Pre-extract per-edge arrays
    cdef list c_edge_src = [<int>edge_src_idx[i] for i in range(n_edges)]
    cdef list c_edge_tgt = [<int>edge_tgt_idx[i] for i in range(n_edges)]
    cdef list c_edge_str = [<double>edge_strengths[i] for i in range(n_edges)]

    # Trophic amplification factors per agent, computed by the caller with
    # gaia.propagation.trophic_amplification_factor (constants in gaia.constants)
    cdef list trophic_amp = [<double>trophic_amp_factors[i] for i in range(n_agents)]

    # Output accumulator
    cdef list result_steps = []

    # Reusable per-step arrays (allocated once, reused each iteration)
    cdef list direct_damages
    cdef list effective_damages
    cdef list cascade_damages
    cdef list agent_costs
    cdef list keystone_triggered
    cdef list eff_strengths
    cdef list pressure

    # Damage function variables
    cdef double inflection, raw_0, span, steepness
    cdef double scale, raw_1, base_val
    cdef double threshold_pw, pre_slope, post_slope, pre_slope_ratio

    for step in range(1, units_to_extract + 1):
        units_extracted = step
        depletion_ratio = <double>units_extracted / <double>total_units

        # ── Phase 1: Direct damage with trophic amplification ──────────
        direct_damages = [0.0] * n_agents
        for i in range(n_agents):
            # Inline damage function evaluation
            if dmg_kind[i] == 0:
                # Logistic: 1/(1+exp(-steepness*(x-inflection))), normalized
                inflection = dmg_p1[i]
                raw_0 = dmg_p2[i]
                span = dmg_p3[i]
                steepness = dmg_p4[i]
                raw_damage = 1.0 / (1.0 + exp(-steepness * (depletion_ratio - inflection)))
                raw_damage = (raw_damage - raw_0) / span
            elif dmg_kind[i] == 1:
                # Exponential: (base^(x*scale) - 1) / (base^scale - 1)
                scale = dmg_p1[i]
                raw_1 = dmg_p2[i]
                base_val = dmg_p3[i]
                raw_damage = (pow(base_val, depletion_ratio * scale) - 1.0) / raw_1
            else:
                # Piecewise: two linear segments
                threshold_pw = dmg_p1[i]
                pre_slope = dmg_p2[i]
                post_slope = dmg_p3[i]
                pre_slope_ratio = dmg_p4[i]
                if depletion_ratio <= threshold_pw:
                    raw_damage = pre_slope * depletion_ratio
                else:
                    raw_damage = pre_slope_ratio + post_slope * (depletion_ratio - threshold_pw)

            # Inline trophic amplification
            if has_trophic and c_trophic[i] >= 1:
                amplified = raw_damage * trophic_amp[i]
                if amplified > 1.0:
                    amplified = 1.0
                direct_damages[i] = amplified
            else:
                direct_damages[i] = raw_damage

        # ── Phase 2: Interaction propagation (inlined) ─────────────────
        if has_interactions:
            effective_damages = list(direct_damages)
            cascade_damages = [0.0] * n_agents
            keystone_triggered = []

            # Compute effective edge strengths with keystone boost
            eff_strengths = list(c_edge_str)
            for i in range(n_agents):
                if c_is_keystone[i]:
                    agent_health = 1.0 - direct_damages[i]
                    if agent_health < c_ks_thresholds[i]:
                        keystone_triggered.append(i)
                        for e in range(n_edges):
                            if c_edge_src[e] == i:
                                doubled = c_edge_str[e] * keystone_edge_multiplier
                                if doubled > max_edge_strength:
                                    doubled = max_edge_strength
                                eff_strengths[e] = doubled

            # Single-pass propagation: cascade pressure from frozen direct damages
            pressure = [0.0] * n_agents
            for e in range(n_edges):
                src_idx = c_edge_src[e]
                tgt_idx = c_edge_tgt[e]
                source_damage = direct_damages[src_idx]
                # Separate statements: a fused multiply-add would round
                # differently from the Python engine
                additional = source_damage * <double>eff_strengths[e]
                pressure[tgt_idx] = <double>pressure[tgt_idx] + additional

            # Pressure acts on the service still standing (see
            # gaia.propagation.propagate_interactions); the clamp guards rounding
            for i in range(n_agents):
                headroom = (1.0 - <double>direct_damages[i]) * <double>pressure[i]
                additional = <double>direct_damages[i] + headroom
                if additional > 1.0:
                    additional = 1.0
                effective_damages[i] = additional
                cascade_damages[i] = additional - <double>direct_damages[i]
                if cascade_damages[i] < 0.0:
                    cascade_damages[i] = 0.0
        else:
            effective_damages = list(direct_damages)
            cascade_damages = [0.0] * n_agents
            keystone_triggered = []

        # ── Phase 3: Annual cost computation (€/yr) ────────────────────
        agent_costs = [0.0] * n_agents
        step_total_cost = 0.0
        health_sum = 0.0

        for i in range(n_agents):
            rate = c_annual_values[i]
            weight = c_dep_weights[i]
            cost = effective_damages[i] * weight * rate
            agent_costs[i] = cost
            step_total_cost = step_total_cost + cost
            health_sum = health_sum + weight * effective_damages[i]

        marginal_cost = step_total_cost - previous_total_cost
        ecosystem_health = 1.0 - health_sum
        if ecosystem_health < 0.0:
            ecosystem_health = 0.0
        elif ecosystem_health > 1.0:
            ecosystem_health = 1.0

        private_revenue = <double>units_extracted * unit_value

        # ── Phase 3.5: Substrate degradation (inlined) ─────────────────
        step_substrate_erosion = 0.0
        step_effective_k = total_units
        step_k_fraction = 1.0

        if has_substrate:
            vegetation_cover = (<double>total_units - <double>units_extracted) / <double>total_units
            if vegetation_cover < 0.0:
                vegetation_cover = 0.0
            elif vegetation_cover > 1.0:
                vegetation_cover = 1.0

            bare_fraction = 1.0 - vegetation_cover
            if bare_fraction < 0.0:
                bare_fraction = 0.0
            exposure = pow(bare_fraction, substrate_erosion_alpha)
            effective_erosion = (
                substrate_erosion_protected
                + (substrate_erosion_unprotected - substrate_erosion_protected) * exposure
            )
            erosion_amount = effective_erosion * time_per_step
            if substrate_is_marine:
                # Marine: erosion in mm/yr, 100 mm ≡ full stability
                if pristine_level > 0.0:
                    current_level = current_level - erosion_amount / 100.0
                    if current_level < 0.0:
                        current_level = 0.0
                step_substrate_erosion = erosion_amount
            else:
                erosion_mm = erosion_amount * substrate_t_ha_to_mm_factor
                erosion_cm = erosion_mm / 10.0
                current_level = current_level - erosion_cm
                if current_level < 0.0:
                    current_level = 0.0
                step_substrate_erosion = erosion_cm

            # Inline capacity fraction computation (threshold is terrestrial-only,
            # enforced by validation)
            if substrate_capacity_function == "linear":
                if pristine_level <= 0.0:
                    step_k_fraction = 0.0
                else:
                    step_k_fraction = current_level / pristine_level
            elif substrate_capacity_function == "threshold":
                critical = substrate_critical_minimum
                residual = substrate_residual_fraction
                if pristine_level <= 0.0:
                    step_k_fraction = 0.0
                elif current_level <= 0.0:
                    step_k_fraction = 0.0
                elif current_level < critical:
                    if critical <= 0.0:
                        step_k_fraction = 0.0
                    else:
                        step_k_fraction = (current_level / critical) * residual
                else:
                    if pristine_level <= critical:
                        step_k_fraction = 1.0
                    else:
                        step_k_fraction = residual + (1.0 - residual) * (current_level - critical) / (pristine_level - critical)
            elif substrate_capacity_function == "logistic":
                if pristine_level <= 0.0:
                    step_k_fraction = 0.0
                else:
                    frac = current_level / pristine_level
                    steepness = 10.0
                    inflection = 0.5
                    raw_damage = 1.0 / (1.0 + exp(-steepness * (frac - inflection)))
                    raw_0 = 1.0 / (1.0 + exp(-steepness * (0.0 - inflection)))
                    raw_1 = 1.0 / (1.0 + exp(-steepness * (1.0 - inflection)))
                    span = raw_1 - raw_0
                    if span <= 0.0:
                        step_k_fraction = frac
                    else:
                        step_k_fraction = (raw_damage - raw_0) / span
            else:
                if pristine_level <= 0.0:
                    step_k_fraction = 0.0
                else:
                    step_k_fraction = current_level / pristine_level

            if step_k_fraction < 0.0:
                step_k_fraction = 0.0
            elif step_k_fraction > 1.0:
                step_k_fraction = 1.0

            step_effective_k = <int>(<double>total_units * step_k_fraction)

        # ── Phase 4: Resilience zone tagging (inlined) ─────────────────
        zone = "green"
        confidence = 1.0
        irreversibility = False

        if has_resilience:
            remaining_frac = 1.0 - depletion_ratio
            # Convert extraction threshold to remaining threshold:
            # safe_threshold_ratio=0.30 means 30% can be extracted, so 70% must remain
            threshold_lower = 1.0 - safe_threshold_ratio  # safe_remaining
            threshold_upper = threshold_lower + resilience_warning_width  # warning_start

            if remaining_frac > threshold_upper:
                zone = "green"
                confidence = resilience_conf_green
            elif remaining_frac > threshold_lower:
                zone = "yellow"
                # Linearly interpolate confidence from green to yellow across warning zone
                if resilience_warning_width > 0.0:
                    zone_position = (threshold_upper - remaining_frac) / resilience_warning_width
                    confidence = resilience_conf_green - zone_position * (resilience_conf_green - resilience_conf_yellow)
                else:
                    confidence = resilience_conf_yellow
            else:
                zone = "red"
                # Linearly interpolate from yellow to red based on how far past threshold
                if threshold_lower > 0.0:
                    zone_position = (threshold_lower - remaining_frac) / threshold_lower
                    if zone_position > 1.0:
                        zone_position = 1.0
                    confidence = resilience_conf_yellow - zone_position * (resilience_conf_yellow - resilience_conf_red)
                else:
                    confidence = resilience_conf_red

            # Irreversibility: depletion_ratio > irreversibility_flag_ratio
            irreversibility = depletion_ratio > resilience_irreversibility_ratio

        # ── Record step ────────────────────────────────────────────────
        # Convert keystone_triggered from indices back to be handled by caller
        result_steps.append((
            step,
            units_extracted,
            depletion_ratio,
            effective_damages,
            agent_costs,
            marginal_cost,
            step_total_cost,
            private_revenue,
            ecosystem_health,
            direct_damages,
            cascade_damages,
            keystone_triggered,  # list of int indices
            zone,
            confidence,
            irreversibility,
            step_substrate_erosion,
            step_effective_k,
            step_k_fraction,
        ))

        previous_total_cost = step_total_cost

    return result_steps
