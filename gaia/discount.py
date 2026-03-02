"""
Gaia v0.6 — Preconfigured discount rate profiles.

Provides four standard discount profiles representing the main positions
in the environmental economics discounting debate, plus per-case profiles
for each of the three preconfigured case studies.

All profiles are DiscountConfig instances imported from gaia.models.
No computation logic is defined here — see gaia.npv for NPV functions.

References:
    DISCOUNT_MARKET:        Nordhaus (2007), r ≈ 4.1%
    DISCOUNT_CENTRAL:       Drupp et al. (2018) consensus, r ≈ 2.3%
    DISCOUNT_ENVIRONMENTAL: Stern (2006), r ≈ 1.4%
    DISCOUNT_GREEN_BOOK:    UK HM Treasury Green Book (2003, updated 2020),
                            declining 3.5% → 3.0% → 2.5%, horizon 125yr
"""

from gaia.models import DiscountConfig


# ── Standard discount profiles ─────────────────────────────────────────────────

# Conservative / market-aligned (Nordhaus-adjacent)
# δ=1.5%, η=2.0, g=1.3% → r ≈ 4.1%
# No scarcity adjustment — assumes full substitutability between market and
# ecosystem goods. Reference: Nordhaus (2007), "A Review of the Stern Review".
DISCOUNT_MARKET = DiscountConfig(
    delta=0.015,
    eta=2.0,
    g=0.013,
    rate_schedule=0.041,
    scarcity_rate=0.0,
    carbon_price_current=80.0,
    carbon_price_growth=0.02,
    horizon_years=100,
    remaining_productive_years=80,
)

# Central / consensus (Drupp et al. 2018 survey median)
# δ=0.5%, η=1.35, g=1.3% → r ≈ 2.3%
# Scarcity 2%/yr (Drupp & Hänsel 2021 lower bound).
# This is the default recommended profile for most applications.
DISCOUNT_CENTRAL = DiscountConfig(
    delta=0.005,
    eta=1.35,
    g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
    remaining_productive_years=80,
)

# Environmental / Stern-adjacent
# δ=0.1%, η=1.0, g=1.3% → r ≈ 1.4%
# Scarcity 3%/yr (higher: more weight on ecosystem scarcity).
# Reference: Stern (2006), "The Economics of Climate Change: The Stern Review".
DISCOUNT_ENVIRONMENTAL = DiscountConfig(
    delta=0.001,
    eta=1.0,
    g=0.013,
    rate_schedule=0.014,
    scarcity_rate=0.03,
    carbon_price_current=80.0,
    carbon_price_growth=0.04,
    horizon_years=100,
    remaining_productive_years=80,
)

# UK Green Book declining schedule
# Years 0–30: 3.5%, years 31–75: 3.0%, years 76–125: 2.5%.
# Reference: UK HM Treasury Green Book (2003, updated 2020).
# Under review in 2026; declining-rate principle is well-established.
DISCOUNT_GREEN_BOOK = DiscountConfig(
    delta=0.005,
    eta=1.35,
    g=0.013,
    rate_schedule=[
        (0, 0.035),    # 3.5% for years 0–30
        (31, 0.030),   # 3.0% for years 31–75
        (76, 0.025),   # 2.5% for years 76–125
    ],
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=125,
    remaining_productive_years=80,
)


# ── Per-case discount profiles ─────────────────────────────────────────────────

# Oak Valley Forest — temperate deciduous forest
# Central rate (2.3%), standard scarcity (2%/yr), 80yr productive lifespan.
# [PLACEHOLDER — pending calibration against case-specific literature]
OAK_VALLEY_DISCOUNT = DiscountConfig(
    delta=0.005,
    eta=1.35,
    g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
    remaining_productive_years=80,
)

# Costa Brava Holm Oak — Mediterranean sclerophyllous forest
# Central rate (2.3%), higher scarcity (2.5%/yr: holm oak under increasing
# climate stress in NE Spain), 200yr productive lifespan (holm oak longevity).
# [PLACEHOLDER — pending calibration against Mediterranean ecosystem studies]
COSTA_BRAVA_OAK_DISCOUNT = DiscountConfig(
    delta=0.005,
    eta=1.35,
    g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.025,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
    remaining_productive_years=200,
)

# Costa Brava Posidonia — marine seagrass meadow
# Declining schedule (2.3% → 1.8% → 1.4%): appropriate for extremely long
# recovery timescales (matte: 1mm/yr accretion over centuries).
# Highest scarcity (3%/yr: Posidonia meadows down 34%+ since 1960s;
# effectively zero substitutability).
# 200yr horizon to capture matte dynamics.
# [PLACEHOLDER — pending calibration against blue carbon / Posidonia studies]
COSTA_BRAVA_POSIDONIA_DISCOUNT = DiscountConfig(
    delta=0.005,
    eta=1.35,
    g=0.013,
    rate_schedule=[
        (0, 0.023),    # 2.3% for years 0–30
        (31, 0.018),   # 1.8% for years 31–100
        (101, 0.014),  # 1.4% for years 101+
    ],
    scarcity_rate=0.03,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=200,
    remaining_productive_years=200,
)
