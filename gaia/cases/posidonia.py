"""
Gaia v0.1 — Costa Brava Posidonia Meadow destruction case.

Marine ecosystem with 11 agents spanning the full web of biological and
physical dependencies: from the Posidonia meadow itself as foundation species,
through coralligenous reefs, fish nurseries, and apex megafauna, to the
coastal protection and tourism economy of the Costa Brava.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: MARINE EXTERNALITY ECONOMICS — TIME-FLOW ASYMMETRY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In the forest case, private revenue is ongoing (per-tree timber income) and
externalities are one-time costs. Here the economics are INVERTED:

    Private revenue:    ONE-TIME gain from coastal development, marina
                        construction, or trawling permits that destroy
                        Posidonia (modeled as €2,500/ha destroyed).

    Externality costs:  ANNUAL RECURRING losses — every year the meadow
                        is gone, the ecosystem services are absent. The
                        report shows the annual cost rate; the true social
                        cost compounds every year the damage persists.

Payback arithmetic (at default parameters, full destruction):
    One-time revenue:   5,000 ha × €2,500 = €12,500,000
    Annual externality: ~€5,830,000/yr at full damage
    Payback period:     ~2.1 years — after that, society loses €5.8M/yr
                        every year, forever (Posidonia growth: 1-6 cm/year).

Over 10 years: €58.3M lost vs €12.5M gained (ratio: 4.7× against destruction).
Over 30 years: €174.9M lost vs €12.5M gained (ratio: 14× against destruction).

The simulation reports ANNUAL externality costs. A note in the output flags
this explicitly. NPV analysis over time horizons is a v0.5 feature.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scientific context:
    Posidonia oceanica is one of the most biodiverse and carbon-rich ecosystems
    on Earth. It absorbs 15× more CO₂ per hectare than the Amazon rainforest and
    stores carbon in its sediment matte for millennia. Growth rate: 1-6 cm/year
    horizontal — any significant destruction is irreversible on human timescales.

    34% of Mediterranean Posidonia has been lost in the last 50 years. The Costa
    Brava is already under pressure from tourism infrastructure, boat anchoring,
    and residual trawling. The 20% safe threshold is lower than the forest (25%)
    because recovery is orders of magnitude slower and the ecosystem is already
    stressed.

    The Medes Islands MPA is the proof-of-concept: protected since 1983, fish
    biomass is 80× higher inside the reserve than outside. The science works —
    protection produces measurable, quantifiable recovery.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

Monetary rates are back-calculated from user-specified max monetary impacts:
    rate = max_monetary_impact / dependency_weight
so that effective_max_per_agent = weight × rate = max_monetary_impact exactly.

    | Parameter                       | Max Impact | Weight | Rate (€)   | Source       | Confidence |
    |---------------------------------|------------|--------|------------|--------------|------------|
    | total_units                     | –          | –      | –          | User spec    | Low        |
    | safe_threshold_ratio            | –          | –      | 0.20       | User spec    | Medium     |
    | unit_value (revenue/ha)         | –          | –      | 2,500      | User spec    | Low        |
    | Posidonia Meadow                | €800,000   | 0.10   | 8,000,000  | User spec    | Low        |
    | Coralligenous & Red Coral       | €600,000   | 0.10   | 6,000,000  | User spec    | Low        |
    | Epiphytes & Algae               | €250,000   | 0.07   | 3,571,000  | User spec    | Low        |
    | Marine Invertebrates            | €350,000   | 0.09   | 3,889,000  | User spec    | Low        |
    | Fish Populations                | €700,000   | 0.14   | 5,000,000  | User spec    | Low        |
    | Marine Megafauna                | €200,000   | 0.04   | 5,000,000  | User spec    | Low        |
    | Seabirds                        | €180,000   | 0.05   | 3,600,000  | User spec    | Low        |
    | Coastal Protection              | €900,000   | 0.13   | 6,923,000  | User spec    | Low        |
    | Water Quality                   | €650,000   | 0.11   | 5,909,000  | User spec    | Low        |
    | Blue Carbon                     | €500,000   | 0.09   | 5,556,000  | User spec    | Low        |
    | Human Communities               | €700,000   | 0.08   | 8,750,000  | User spec    | Low        |
    | logistic steepness              | –          | –      | 12.0       | Placeholder  | Low        |
    | exponential base (carbon)       | –          | –      | 2.0        | Placeholder  | Low        |
    | dependency weight sum           | –          | 1.00   | –          | Verified ✓   | High       |

Total max externality (annual): sum(weight × rate)
    = 800k + 600k + 250k + 350k + 700k + 200k + 180k + 900k + 650k + 500k + 700k
    = €5,830,000/year [User spec ✓]

vs one-time revenue at full destruction: 5,000 ha × €2,500 = €12,500,000
Annual payback period: ~2.1 years [User spec ✓]

Calibration: rates ensure externality < revenue at 20% threshold (at annual scale):
    logistic_damage(0.20) ≈ 0.068 → 0.068 × €5,830,000 ≈ €396k/yr < €250k one-time
    NOTE: Even at threshold, 1.6 years of annual losses exceed the one-time gain.
    The crossover is near-immediate for marine ecosystems. [User spec ✓]

Dependency weights sum: 0.10+0.10+0.07+0.09+0.14+0.04+0.05+0.13+0.11+0.09+0.08 = 1.00 ✓

CLI usage:
    python -m gaia.cases.posidonia
    python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 1500
    python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 1500 --mode restore
"""

import argparse
import sys

from gaia.damage import exponential_damage, logistic_damage
from gaia.models import Agent, Ecosystem, RestorationCost, Resource
from gaia.recovery import logistic_recovery
from gaia.report import format_report, format_restoration_report
from gaia.simulation import run_extraction, run_restoration

# Shared steepness for all logistic agents.
# [PLACEHOLDER — per-agent steepness could be differentiated once calibrated]
_STEEPNESS: float = 12.0

# Annual externality note appended to the report to flag the time-flow asymmetry.
_ANNUAL_NOTE: str = (
    "\n  ⚠  MARINE EXTERNALITY NOTE: these costs are ANNUAL — they recur every year\n"
    "     the damage persists. Posidonia recovers at 1-6 cm/year; damage is\n"
    "     effectively permanent on human timescales. The one-time private revenue\n"
    "     is offset within ~2 years of annual ecosystem service losses."
)


def build_posidonia_ecosystem(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    revenue_per_hectare: float = 2_500.0,
) -> Ecosystem:
    """
    Build the Costa Brava Posidonia Meadow ecosystem with 11 agents.

    The ecosystem spans the full marine dependency web: seagrass foundation,
    coralligenous reefs, epiphytes, invertebrates, fish, megafauna, seabirds,
    coastal protection, water quality, blue carbon, and human coastal communities.

    Args:
        total_hectares: Total hectares of Posidonia meadow. Default 5,000 ha —
            a plausible estimate for a major Costa Brava coastal stretch.
            [User spec, needs GIS verification from EMODnet Posidonia maps]
        safe_threshold_ratio: Fraction destructible before cascading decline.
            Default 0.20 — lower than forest (0.25) because Posidonia growth
            is 1-6 cm/year and recovery takes decades. Mediterranean already
            lost 34% in 50 years. [User spec, Medium confidence]
        revenue_per_hectare: Private gain per hectare destroyed. Represents the
            economic value extracted by activities that destroy Posidonia:
            coastal development, marina construction, trawling permits.
            NOT the value of Posidonia itself. [User spec, Low confidence]

    Returns:
        A fully configured Ecosystem ready for simulation.
    """
    resource = Resource(
        name="Costa Brava Posidonia Meadow",
        total_units=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        unit_value=revenue_per_hectare,
    )

    t = safe_threshold_ratio  # shorthand

    agents = [
        # ── Foundation species ──────────────────────────────────────────────
        Agent(
            name="Posidonia Meadow",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_000_000.0,
            # Effective max (annual): 0.10 × €8,000k = €800k/yr [User spec]
            # Remaining meadow depends on network connectivity for vegetative
            # reproduction (rhizome growth: 1-6 cm/yr). Fragmentation → reduced
            # sediment trapping → increased turbidity → light reduction → further
            # die-off. Self-reinforcing collapse. Recovery after bomb damage in
            # Villefranche: 40+ years, still incomplete. [User spec, Medium]
            description="Posidonia meadow integrity — self-reinforcing fragmentation and turbidity feedback loop",
        ),
        # ── Biogenic habitat builders ───────────────────────────────────────
        Agent(
            name="Coralligenous & Red Coral",
            dependency_weight=0.10,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=6_000_000.0,
            # Effective max (annual): 0.10 × €6,000k = €600k/yr [User spec]
            # KEYSTONE HABITAT BUILDER. Coralligenous formations (coralline algae
            # biogenic reefs) take centuries to form. Red coral (Corallium rubrum)
            # grows 0.2-0.6 mm/yr basal diameter; 98% of Costa Brava colonies are
            # juvenile due to historical overharvesting. Posidonia loss → sedimentation
            # → suffocation. Dive tourism at Medes Islands = 70% of GDP for some
            # villages. Irreplaceable on human timescales. [User spec, Medium]
            description="Coralligenous reefs and red coral — centuries-old biogenic habitat, irreplaceable on human timescales",
        ),
        # ── Primary producers ───────────────────────────────────────────────
        Agent(
            name="Epiphytes & Algae",
            dependency_weight=0.07,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_571_000.0,
            # Effective max (annual): 0.07 × €3,571k ≈ €250k/yr [User spec]
            # 400+ plant/algae species grow on Posidonia leaves. Loss of substrate
            # → epiphyte collapse. Nutrient imbalance from lost filtration → algal
            # blooms (eutrophication) replace diverse community with monoculture.
            # Oxygen production and food web foundation degraded. [User spec, Medium]
            description="Epiphytic algae and plant community — primary productivity, oxygen production, food web base",
        ),
        # ── Invertebrates ───────────────────────────────────────────────────
        Agent(
            name="Marine Invertebrates",
            dependency_weight=0.09,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_889_000.0,
            # Effective max (annual): 0.09 × €3,889k ≈ €350k/yr [User spec]
            # Sea urchins, starfish, sponges, nudibranchs, octopuses, lobsters,
            # sea cucumbers, mussels. Sponges filter enormous water volumes.
            # Risk: sea urchin population explosion without predators → overgrazing
            # → algal/barren desert ("urchin barrens"). Lobster and octopus lose
            # shelter; fisheries collapse. [User spec, Medium]
            description="Sponges, urchins, octopus, lobsters, shellfish — filter feeders, grazers, urchin barren risk",
        ),
        # ── Fish ────────────────────────────────────────────────────────────
        Agent(
            name="Fish Populations",
            dependency_weight=0.14,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_000_000.0,
            # Effective max (annual): 0.14 × €5,000k = €700k/yr [User spec]
            # HIGHEST LIVING AGENT WEIGHT. Posidonia meadows = critical nursery
            # for juvenile fish. Species: grouper (Epinephelus marginatus — Medes
            # Islands flagship), sea bass, gilthead bream, dentex, scorpionfish,
            # red mullet, sardine, seahorses. Medes Islands MPA proved: fish
            # biomass 80× higher inside reserve than outside. Loss of nursery →
            # recruitment failure → population collapse. 24 artisanal boats at
            # L'Estartit depend on the Medes buffer zone. [User spec, Medium]
            description="Fish nursery and feeding habitat — artisanal fisheries, grouper apex predator, Medes Islands model",
        ),
        # ── Megafauna ───────────────────────────────────────────────────────
        Agent(
            name="Marine Megafauna",
            dependency_weight=0.04,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_000_000.0,
            # Effective max (annual): 0.04 × €5,000k = €200k/yr [User spec]
            # Bottlenose dolphins, loggerhead sea turtles (Caretta caretta), Risso's
            # dolphins, occasional fin whales. Mediterranean monk seal: functionally
            # extinct in western Mediterranean. Extreme K-strategy: slow reproduction,
            # threshold-sensitive. Fish crash → dolphin displacement or starvation.
            # [User spec, Medium]
            description="Dolphins, sea turtles, cetaceans — apex indicators, ecotourism, extreme K-strategy vulnerability",
        ),
        # ── Seabirds ────────────────────────────────────────────────────────
        Agent(
            name="Seabirds",
            dependency_weight=0.05,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=3_600_000.0,
            # Effective max (annual): 0.05 × €3,600k = €180k/yr [User spec]
            # 189 species in Montgrí-Medes Natural Park alone. Key species:
            # Audouin's gull (breeds Mediterranean only — globally vulnerable),
            # European shag, yellow-legged gull, peregrine falcon, Bonelli's eagle.
            # Fish depletion → breeding failure → colony abandonment. [User spec, Medium]
            description="Seabirds and coastal birds — fish-dependent breeders, Audouin's gull, migratory corridor",
        ),
        # ── Physical ecosystem services ─────────────────────────────────────
        Agent(
            name="Coastal Protection",
            dependency_weight=0.13,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=6_923_000.0,
            # Effective max (annual): 0.13 × €6,923k ≈ €900k/yr [User spec]
            # HIGHEST WEIGHT PHYSICAL AGENT. Posidonia meadows attenuate wave energy
            # before it reaches shore. Leaf litter forms beach cushions up to 4m high.
            # Root/rhizome mats stabilize seabed. 1 km of Posidonia produces 125 kg/m
            # of beach-protecting litter/year. Without it: accelerated erosion, storm
            # damage, need for artificial replenishment (which itself destroys more
            # Posidonia — death spiral). Costa Brava has dozens of beaches that depend
            # on this. Wave attenuation has a density threshold — sparse meadow provides
            # almost no protection. [User spec, Medium]
            description="Wave attenuation, beach erosion prevention, sediment stabilization — Costa Brava beach economy",
        ),
        Agent(
            name="Water Quality",
            dependency_weight=0.11,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=5_909_000.0,
            # Effective max (annual): 0.11 × €5,909k ≈ €650k/yr [User spec]
            # Posidonia absorbs nutrients, traps particles, reduces pathogenic bacteria,
            # sequesters heavy metals and radioactive contaminants in rhizomes. Virtuous
            # cycle when healthy → vicious when degraded. Italian studies: bioremediation
            # = 34-40% of total Posidonia service value. Bathing quality decline →
            # beach closures → tourism devastation. [User spec, Medium]
            description="Nutrient filtration, pathogen reduction, bathing water standards — direct tourism dependency",
        ),
        # ── Carbon ──────────────────────────────────────────────────────────
        Agent(
            name="Blue Carbon",
            dependency_weight=0.09,
            # Exponential (not logistic) — CO₂ release does not plateau.
            # Posidonia absorbs 15× more CO₂/ha than Amazon rainforest.
            # Carbon stored in sediment matte for millennia; decomposition
            # accelerates once exposed. Double externality: release + lost
            # future sequestration. [User spec]
            damage_function=exponential_damage(threshold=t, base=2.0),
            monetary_rate=5_556_000.0,
            # Effective max (annual): 0.09 × €5,556k ≈ €500k/yr [User spec]
            # Social cost of carbon release, lost sequestration, EU ETS exposure.
            # Conservative — real values may be much higher as carbon markets mature.
            # Mediterranean blue carbon: 100-1,500M €/yr basin-wide. [User spec, Medium]
            description="Blue carbon — 15× Amazon CO₂ rate, millennia of stored matte carbon, exponential release",
        ),
        # ── Human systems ───────────────────────────────────────────────────
        Agent(
            name="Human Communities",
            dependency_weight=0.08,
            damage_function=logistic_damage(threshold=t, steepness=_STEEPNESS),
            monetary_rate=8_750_000.0,
            # Effective max (annual): 0.08 × €8,750k = €700k/yr [User spec]
            # Dive tourism (Medes Islands = 70% of GDP for some villages). Beach
            # tourism (Costa Brava = one of Europe's top destinations). Artisanal
            # fishing (24 boats at L'Estartit). Snorkeling, glass-bottom boats,
            # eco-tourism. Tourism = 79% of Mediterranean blue economy jobs.
            # Tourism has a perception threshold — once beaches visibly degrade
            # or water quality drops, visitors leave fast. [User spec, Medium]
            description="Dive/beach tourism economy, artisanal fishing, coastal property — perception threshold sensitive",
        ),
    ]

    return Ecosystem(
        name="Costa Brava Posidonia Meadow",
        resource=resource,
        agents=agents,
    )


def run_posidonia(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_destroyed: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
) -> str:
    """
    Run the Costa Brava Posidonia destruction simulation and return the report.

    Default hectares_destroyed=2,000 — 40% of the meadow, well past the 20%
    safe threshold, representative of a major coastal development project.

    NOTE: externality costs in the report are ANNUAL rates. The one-time
    private revenue must be compared against recurring annual losses to
    understand the true social cost over time.

    Args:
        total_hectares: Total hectares of Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_destroyed: Hectares of meadow destroyed (extracted).
        revenue_per_hectare: One-time private revenue per hectare destroyed.

    Returns:
        Formatted text report string with marine economics note appended.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    result = run_extraction(ecosystem, hectares_destroyed)
    return format_report(result) + _ANNUAL_NOTE


def run_posidonia_restoration(
    total_hectares: int = 5_000,
    safe_threshold_ratio: float = 0.20,
    hectares_to_restore: int = 2_000,
    revenue_per_hectare: float = 2_500.0,
    planting_cost_per_hectare: float = 50_000.0,
    annual_maintenance_per_hectare: float = 5_000.0,
    maintenance_years: int = 30,
) -> str:
    """
    Run the Costa Brava Posidonia Meadow restoration simulation and return the report.

    Posidonia restoration is among the most expensive and uncertain ecological
    restoration efforts known. The prevention advantage ratio is extremely high
    because:
    - Posidonia grows at 1-6 cm/year horizontal expansion rate
    - Transplanting requires specialist diving teams
    - Establishment takes 5-10 years before any ecosystem service recovery
    - Survival rates in transplanting projects: 30-60%
    - The logistic recovery inflection at 60% restoration means services only
      meaningfully recover after most of the meadow is re-established

    Default costs (per hectare):
        Planting: €50,000/ha — specialist diving, substrate preparation,
                  donor material collection, monitoring
        Maintenance: €5,000/ha/year for 30 years — storm damage repair,
                     invasive species control, turbidity monitoring
        Total: €50,000 + (€5,000 × 30) = €200,000/ha

    For comparison: one-time destruction revenue is €2,500/ha.
    Prevention advantage ≈ (€2,500 + €200,000) / €2,500 ≈ 81×

    NOTE: The logistic recovery function here models ecosystem SERVICE recovery,
    not meadow area recovery. Even with 100% area replanted, services ramp up
    slowly as the meadow matures.

    Args:
        total_hectares: Total carrying capacity of the Posidonia meadow.
        safe_threshold_ratio: Safe destruction threshold ratio.
        hectares_to_restore: Hectares of meadow to actively restore.
        revenue_per_hectare: One-time private revenue per hectare (for prevention_advantage).
        planting_cost_per_hectare: Specialist diving and transplanting cost per hectare.
        annual_maintenance_per_hectare: Annual monitoring and repair cost per hectare.
        maintenance_years: Years of active maintenance before self-sustaining.

    Returns:
        Formatted text restoration report string with marine economics note appended.
    """
    ecosystem = build_posidonia_ecosystem(
        total_hectares=total_hectares,
        safe_threshold_ratio=safe_threshold_ratio,
        revenue_per_hectare=revenue_per_hectare,
    )
    cost = RestorationCost(
        planting_cost_per_unit=planting_cost_per_hectare,
        annual_maintenance_per_unit=annual_maintenance_per_hectare,
        maintenance_years=maintenance_years,
    )
    recovery_fns = [
        logistic_recovery(threshold=safe_threshold_ratio)
        for _ in ecosystem.agents
    ]
    result = run_restoration(ecosystem, hectares_to_restore, cost, recovery_fns)
    return format_restoration_report(result) + _ANNUAL_NOTE


def _parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gaia v0.2 — Costa Brava Posidonia Meadow externality and restoration simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Extraction — at safe threshold (20% = 1,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 1000\n\n"
            "  # Extraction — past threshold (40% = 2,000 ha):\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 2000\n\n"
            "  # Restoration mode:\n"
            "  python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 2000 --mode restore\n"
        ),
    )
    parser.add_argument(
        "--hectares",
        type=int,
        default=5_000,
        metavar="N",
        help="Total hectares of Posidonia meadow (default: 5000)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        metavar="RATIO",
        help="Safe destruction threshold ratio, 0.0 < threshold < 1.0 (default: 0.20)",
    )
    parser.add_argument(
        "--destroy",
        type=int,
        default=2_000,
        metavar="N",
        help="Hectares of Posidonia to destroy/restore (default: 2000)",
    )
    parser.add_argument(
        "--revenue",
        type=float,
        default=2_500.0,
        metavar="EUROS",
        help="One-time revenue per hectare destroyed in euros (default: 2500.0)",
    )
    parser.add_argument(
        "--mode",
        choices=["extract", "restore"],
        default="extract",
        help="Simulation mode: 'extract' (default) or 'restore'",
    )
    parser.add_argument(
        "--planting-cost",
        type=float,
        default=50_000.0,
        metavar="EUROS",
        help="[restore mode] Planting/transplanting cost per hectare in euros (default: 50000.0)",
    )
    parser.add_argument(
        "--maintenance-cost",
        type=float,
        default=5_000.0,
        metavar="EUROS",
        help="[restore mode] Annual maintenance cost per hectare in euros (default: 5000.0)",
    )
    parser.add_argument(
        "--maintenance-years",
        type=int,
        default=30,
        metavar="N",
        help="[restore mode] Number of maintenance years (default: 30)",
    )
    return parser.parse_args(argv)


def main(argv: list = None) -> None:
    args = _parse_args(argv)
    try:
        if args.mode == "restore":
            report = run_posidonia_restoration(
                total_hectares=args.hectares,
                safe_threshold_ratio=args.threshold,
                hectares_to_restore=args.destroy,
                revenue_per_hectare=args.revenue,
                planting_cost_per_hectare=args.planting_cost,
                annual_maintenance_per_hectare=args.maintenance_cost,
                maintenance_years=args.maintenance_years,
            )
        else:
            report = run_posidonia(
                total_hectares=args.hectares,
                safe_threshold_ratio=args.threshold,
                hectares_destroyed=args.destroy,
                revenue_per_hectare=args.revenue,
            )
        print(report)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
