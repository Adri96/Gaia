"""
Gaia — model constants for trophic amplification and interaction cascades.

The single home of these numbers: gaia.propagation, gaia.validation,
gaia.report and the Cython loop (which receives them as arguments from
gaia.simulation) all read them from here, so the engines and the text report
cannot drift apart.

Every constant carries a source, or an explicit PLACEHOLDER flag when the
value is a modelling choice with no calibration behind it, and a one-line
rationale. Step 5 builds parameter provenance on these flags.
"""

# ── Trophic amplification (Foundation F3) ──────────────────────────────────────
# factor(L) = (1 / TROPHIC_TRANSFER_EFFICIENCY) ** (TROPHIC_AMPLIFICATION_EXPONENT * L)
# for trophic level L >= 1, i.e. 1.6× / 2.6× / 4.2× for L = 1 / 2 / 3.

# PLACEHOLDER. Midpoint of the 5–20% energy transfer efficiency between
# trophic levels (the textbook range following Lindeman 1942; from memory —
# verify in Step 8). The midpoint itself is a choice, not a measurement.
TROPHIC_TRANSFER_EFFICIENCY: float = 0.15

# PLACEHOLDER. No source: damps the raw pyramid ratio (1/0.15)**L = 6.7×, 44×,
# 296× to 1.6–4.2× so a single-resource model stays in a plausible range.
TROPHIC_AMPLIFICATION_EXPONENT: float = 0.25

# ── Keystone cascades (Foundation F6) ─────────────────────────────────────────

# PLACEHOLDER. No source: once a keystone agent's health falls below its
# threshold, its outgoing edge strengths are multiplied by this factor (a
# regime shift), capped at MAX_EDGE_STRENGTH.
KEYSTONE_EDGE_MULTIPLIER: float = 2.0

# PLACEHOLDER. Default Agent.keystone_threshold (health below which the
# keystone cascade triggers); every shipped keystone agent sets its own.
DEFAULT_KEYSTONE_THRESHOLD: float = 0.3

# ── Interaction-edge limits (Step 3.8, S2) ────────────────────────────────────

# Structural, not a calibration: an edge transfers at most all of its
# source's damage.
MAX_EDGE_STRENGTH: float = 1.0

# Structural, not a calibration: the cascade pressure on an agent,
# sum(strength × source damage) over its incoming edges, is a fraction of
# the service still standing and must not exceed 1. Validation rejects an
# ecosystem whose incoming strengths, keystone multipliers included, sum
# above this.
MAX_INCOMING_EDGE_STRENGTH: float = 1.0

# PLACEHOLDER. Level suggested by the audit (TOP_PRIORITIES_REPORT §9 Step
# 3.8): health below this at the safe-threshold depletion means the curves or
# edges put heavy damage inside the "safe" zone, so validation warns.
THRESHOLD_HEALTH_WARNING_LEVEL: float = 0.8

# PLACEHOLDER. Strength multiplier for recovery cascades in
# propagate_interactions(recovery_mode=True), weaker than damage cascades
# (entropy asymmetry). Unused by run_restoration since Step 3.3.
RECOVERY_CASCADE_FACTOR: float = 0.5
