# Gaia v0.4 — Specification: Succession, Maturation Curves & Resilience Zones

## Overview

v0.4 is the version where **time becomes real**. In v0.2, restoration recovery is a function of how many units you replant — plant 50% of the trees and you recover some fraction of services. But it doesn't model *when* those services actually come back. A sapling planted today doesn't filter water tomorrow. A replanted Posidonia rhizome doesn't protect the coastline next year.

v0.4 introduces three mechanisms that make restoration honest about time:

1. **Succession-based maturation curves** — ecosystem services return in phases (pioneer → intermediate → climax), not as a smooth logistic
2. **Maturation delay** — a configurable dead period where replanted units provide zero services while the pioneer phase establishes
3. **Double carbon externality** — cutting a tree releases stored carbon AND removes future absorption capacity; both are costs

Plus one mechanism that makes extraction honest about uncertainty:

4. **Resilience zones** — a three-zone system around the safe threshold that flags when model confidence degrades

**Scientific foundations used:** Ecological Succession & Climax State (F8), Nutrient Cycles & Carbon Cycle (F9), Resilience (F7), plus all foundations from v0.1–v0.3.

---

## What Changes from v0.3

### Conceptual shift

In v0.2/v0.3, the restoration simulation answers: "If you replant X units, how much service value do you recover?"

In v0.4, it answers: "If you replant X units, how much service value do you recover **and when**?" The answer includes a time profile showing that year 1 gives you almost nothing, year 5 gives you a little, and full service recovery takes decades.

The extraction simulation also changes. Instead of a single threshold with a sharp damage curve, v0.4 adds uncertainty bands around the threshold — acknowledging that we don't actually know exactly where the tipping point is.

### What stays the same

- All v0.1/v0.2/v0.3 data structures (extended, not replaced)
- Damage functions, trophic amplification, interaction propagation (unchanged)
- Extraction mode simulation loop (extended with resilience zone tagging)
- CLI interface (extended with time horizon parameter)
- All v0.1/v0.2/v0.3 tests must continue to pass

---

## Part 1: Succession-Based Maturation Curves

### The Science (Foundation F8)

Ecosystems restore through succession — a sequence of phases where each creates the conditions for the next:

1. **Pioneer phase** (years 0–Y₁): Annual plants, r-strategy colonizers. Low biomass, high growth rate. Ecosystem services near-zero — soil barely stabilizing, no canopy, no microclimate, minimal carbon sequestration.

2. **Intermediate phase** (years Y₁–Y₂): Shrubs and perennial plants establish. Soil stabilizes, microclimate develops. Services accelerate — some water filtration, some carbon uptake, partial habitat value. The ecosystem is functional but far from climax.

3. **Climax phase** (years Y₂–Y₃+): Long-lived K-strategy species dominate. Gross primary productivity is high, net productivity approaches zero (all energy goes to maintenance). Maximum complexity, maximum ecosystem services. This is the state that was destroyed.

### The Problem with v0.2's Recovery

v0.2 uses `logistic_recovery(inflection=0.60, steepness=7.0)` — a function of **restoration ratio** (how many units replanted), not of **time**. It says "replant 60% of the trees and you get about half the services back." But it doesn't say when. A forest replanted to 100% today doesn't provide 100% services — it provides ~0% services today and recovers over decades.

The `linear_recovery(slope)` partially captures this by capping at `f(1.0) = slope < 1.0` — acknowledging that full replanting doesn't mean full recovery. But it doesn't model the time profile.

### The Solution: SuccessionCurve

A new function type that maps **years since restoration** to **service capacity fraction**:

```python
@dataclass
class SuccessionCurve:
    """Three-phase succession maturation curve.
    
    Maps years since restoration to service capacity (0.0 to 1.0).
    Encodes the ecological reality that restoration follows
    pioneer → intermediate → climax phases.
    """
    pioneer_end_year: float      # when pioneer phase ends (Y₁)
    intermediate_end_year: float # when intermediate phase ends (Y₂)
    climax_approach_year: float  # when services reach ~95% of climax (Y₃)
    
    pioneer_service: float       # max service fraction during pioneer (e.g. 0.05)
    intermediate_service: float  # max service fraction during intermediate (e.g. 0.40)
    # climax service is always 1.0 by definition
    
    maturation_delay: float      # years of zero service at the start (dead zone)
```

**The curve shape:**

```
Service Capacity
  1.0 │                                          ━━━━━━━━━━━━━━
      │                                      ╱
      │                                   ╱
  0.4 │                     ┄┄┄┄┄┄┄╱
      │                  ╱
      │               ╱
  0.05│     ┄┄┄┄┄╱
      │          
  0.0 │━━━━━│
      └────────────────────────────────────────────── Years
      0    delay  Y₁          Y₂                Y₃
       ↑         ↑             ↑                  ↑
    Dead zone  Pioneer    Intermediate         Climax
    (zero      ends       ends                 approaches
    service)
```

**Implementation:**

```python
def succession_service(self, years: float) -> float:
    """Compute service capacity at a given year since restoration."""
    if years < self.maturation_delay:
        return 0.0
    
    effective_years = years - self.maturation_delay
    
    if effective_years <= self.pioneer_end_year:
        # Pioneer phase: linear ramp from 0 to pioneer_service
        t = effective_years / self.pioneer_end_year
        return self.pioneer_service * t
    
    if effective_years <= self.intermediate_end_year:
        # Intermediate phase: accelerating growth from pioneer_service to intermediate_service
        t = (effective_years - self.pioneer_end_year) / (self.intermediate_end_year - self.pioneer_end_year)
        # Use a smoothstep for the acceleration
        t_smooth = t * t * (3 - 2 * t)  # Hermite smoothstep
        return self.pioneer_service + (self.intermediate_service - self.pioneer_service) * t_smooth
    
    # Climax approach: decelerating growth from intermediate_service to 1.0
    t = (effective_years - self.intermediate_end_year) / (self.climax_approach_year - self.intermediate_end_year)
    t = min(1.0, t)
    # Use a decelerating curve (square root shape)
    t_decel = 1.0 - (1.0 - t) ** 2
    return self.intermediate_service + (1.0 - self.intermediate_service) * t_decel
```

**Why smoothstep for intermediate, square-root for climax:**
- Pioneer → intermediate transition: services accelerate as soil stabilizes and microclimate develops. Smoothstep captures this acceleration.
- Intermediate → climax transition: services decelerate as the ecosystem approaches its maximum. The last 10% of recovery takes as long as the first 50%. Square-root shape captures this diminishing returns behavior.

### Preconfigured Succession Curves

| Ecosystem | Delay | Pioneer End | Intermediate End | Climax ~95% | Pioneer Svc | Intermediate Svc |
|---|---|---|---|---|---|---|
| Oak Valley (temperate) | 2 yr | 8 yr | 25 yr | 60 yr | 0.05 | 0.35 |
| Costa Brava Holm Oak | 3 yr | 12 yr | 35 yr | 80 yr | 0.03 | 0.30 |
| Costa Brava Posidonia | 5 yr | 20 yr | 50 yr | 120 yr | 0.02 | 0.25 |

**Rationale (with literature sources):**

- **Oak Valley** is the fastest. Temperate deciduous forests with good soil and rainfall establish pioneer phase quickly (2yr delay), reach intermediate services in ~25 years (canopy closure), and approach climax in ~60 years. Based on literature: temperate deciduous forests reach canopy closure in 20–30 years and structural maturity in 60–100 years. Value: **medium confidence** (temperate succession is well-studied).

- **Costa Brava Holm Oak** is slower. Mediterranean drought stress, fire risk, and thin soils delay everything. Pioneer takes longer to establish (3yr delay), intermediate phase is extended (35yr) because holm oak is a slow-growing species — EUFORGEN notes coppice rotation cycles of 30–40 years with "slow growth rate" explicitly noted. Pulido et al. (2001) show holm oak forests have poor natural regeneration and very slow diameter growth. Q. ilex is classified as a "late-successional species" (del Campo et al. 2008). After coppicing, canopy closure (97% crown cover) is achieved at ~40 years (Sferlazza et al. 2018, Plot A4). From bare ground (not coppice regrowth), succession would take longer — the spec's 80yr climax approach is reasonable for full ecosystem function including soil recovery. Note: holm oak coppice recovery (where root systems persist) is MUCH faster than de novo planting; these timelines assume degraded sites requiring full replanting. Value: **medium confidence** — the coppice literature is solid but full-succession-from-bare-ground data for holm oak is sparse.

- **Costa Brava Posidonia** is dramatically slower. Marbà et al. (1996) measured rhizome growth at **1–6 cm/yr** across 29 Spanish meadows. Branching occurs on average every 30 years (Coastal Wiki). The Coastal Wiki reports that models estimate 600 years to cover 66% of available space in the Mediterranean. Transplantation studies show encouraging short-term results: the Sicily study (2021, Water) achieved natural density (332 shoots/m²) after 12 years on a 20m² patch, and the Concordia shipwreck restoration showed ~80% survival after 2 years. However, these are small patches in favorable conditions — ecosystem-scale functional recovery (wave attenuation, full biodiversity, carbon sequestration at natural rates) requires a continuous dense canopy that takes far longer. The spec's 120yr climax approach may actually be **optimistic** for large-scale destruction — centuries is more realistic based on the colonization models. Value: **low–medium confidence** (individual patch recovery is well-documented; ecosystem-scale functional recovery data is limited because no large-scale restoration has been monitored long enough).

**All succession timeline values should be treated as working estimates** pending ecological review. The succession curve shape and timelines are the most important parameters for the ecologist to validate — they drive the maturation gap, which drives the economic case.

### Agent-Specific Succession Curves

Different agents within the same ecosystem recover at different rates. An agent can optionally carry its own `SuccessionCurve` that overrides the ecosystem default:

```python
@dataclass
class Agent:
    # --- existing fields ---
    ...
    
    # --- new field ---
    succession_curve: Optional[SuccessionCurve] = None  # None → use ecosystem default
```

**Examples where agent-specific curves matter:**

- **Pollinators & Insects** recover faster than canopy trees — insects have r-strategy reproduction and can recolonize once wildflowers establish (by intermediate phase). Their succession curve might have `pioneer_service=0.10, intermediate_service=0.60`.

- **Raptors & Apex Predators** recover much slower — they need the full trophic pyramid rebuilt before prey populations can sustain them. Their curve might have `pioneer_service=0.01, intermediate_service=0.15, climax_approach_year=100`.

- **Carbon & Climate** has a unique shape — carbon sequestration begins as soon as living biomass exists (even pioneer grasses absorb CO₂), but the rate increases with biomass. `pioneer_service=0.10` (some sequestration immediately), `intermediate_service=0.50`.

- **Coastal Protection** (Posidonia) requires dense meadow to attenuate waves — sparse pioneer rhizomes provide almost no wave reduction. `pioneer_service=0.01, intermediate_service=0.20` — most protection comes only at near-climax density.

---

## Part 2: Restoration Simulation with Time

### The New Restoration Loop

v0.2's restoration loop steps through units replanted. v0.4 adds a time dimension:

```python
@dataclass
class RestorationConfig:
    """Configuration for time-aware restoration simulation."""
    units_to_restore: int
    planting_schedule: str          # "immediate" or "phased"
    planting_years: int             # if phased: how many years to spread planting over
    time_horizon_years: int         # how many years to simulate post-restoration
    succession_curve: SuccessionCurve  # ecosystem-level default
```

The simulation now has **two passes**:

**Pass 1: Planting pass** (same as v0.2)
Steps through units being replanted, computing recovery ratio and v0.3 cascade propagation at each step. This determines *how much* service capacity is eventually recovered.

**Pass 2: Maturation pass** (NEW)
For each year in the time horizon, compute the actual service delivery based on where each planted unit is in its succession curve. Units planted earlier are further along than units planted later.

```python
@dataclass
class MaturationStep:
    """One year of the maturation timeline."""
    year: int
    succession_phase: str          # "delay", "pioneer", "intermediate", "climax"
    service_fraction: float        # 0.0 to 1.0 — what fraction of max recovered services are delivered this year
    annual_service_value: float    # € — actual service value delivered this year
    cumulative_service_value: float  # € — total services delivered from year 0 to this year
    annual_carbon_absorbed: float  # tonnes CO₂ — carbon absorbed this year (Part 3)
    cumulative_carbon_absorbed: float  # tonnes CO₂ — total carbon absorbed so far
```

```python
@dataclass 
class RestorationResult:
    # --- existing fields (preserved) ---
    steps: list                    # List[RestorationStep] — planting pass results
    total_cost: float
    total_recovered_value: float   # max recoverable (at climax)
    prevention_advantage: float
    
    # --- new fields ---
    maturation_timeline: list      # List[MaturationStep] — year-by-year service recovery
    years_to_pioneer: float        # when services first become non-zero
    years_to_50pct: float          # when 50% of recoverable services are delivered
    years_to_90pct: float          # when 90% of recoverable services are delivered
    total_maturation_gap: float    # € — total externality that persists during maturation
                                   # (services lost between planting and full recovery)
```

### The Maturation Gap

The **maturation gap** is the most important new metric v0.4 introduces. It quantifies the externality damage that continues to accumulate *after* restoration begins, *during* the decades it takes for services to recover.

```
Ecosystem Services
  max │━━━━━━━━━━━━━━━━━━━━━━┓                    ╱━━━━━━
      │                       ┃                ╱
      │                       ┃             ╱
      │                       ┃          ╱
      │                       ┃       ╱
      │     ████████████████  ┃    ╱       Maturation gap
      │     ████████████████  ┃ ╱          (ongoing damage
      │     ████████████████  ╋            during recovery)
      │     ████████████████╱ ┃
      │     ██████████╱       ┃
  0   │━━━━━━━━━╱━━━━━━━━━━━━━┛
      └──────────────────────────────────────── Years
          cut    restore          50%        climax
                 begins         recovered
```

The shaded area is the maturation gap — **the accumulated cost of not having services during the decades between restoration and climax**. This is the cost that "cut now, replant later" advocates systematically ignore.

```
maturation_gap = Σ over years [ (max_service_value - actual_service_value_this_year) ]
```

This replaces v0.2's crude "prevention advantage" ratio with a much more precise number: the actual monetary cost of waiting for succession to complete.

### Backward Compatibility

When `RestorationConfig.time_horizon_years = 0` or `succession_curve` is not provided, the simulation falls back to v0.2 behavior — planting pass only, no maturation timeline. The existing `prevention_advantage` field is still computed.

**All existing restoration tests must pass without modification.**

---

## Part 3: Double Carbon Externality

### The Science (Foundation F9)

Cutting a tree has two carbon costs:

1. **Release cost**: The CO₂ stored in the tree's biomass and the soil beneath it is released to the atmosphere.
2. **Absorption cost**: The CO₂ that tree would have continued to absorb over its remaining lifetime is no longer being captured. This is a present cost of a future service permanently lost.

Together, the cost of cutting one tree is:

```
carbon_externality = carbon_released + NPV(future_absorption_foregone)
```

For Posidonia the dynamic is identical but more extreme: the seagrass stores carbon in both living tissue AND in the sediment matte beneath, which has accumulated over millennia. Destroying Posidonia releases centuries of stored carbon.

### Data Model

```python
@dataclass
class CarbonProfile:
    """Carbon accounting parameters for a resource unit."""
    stored_carbon_tonnes: float     # tonnes CO₂ stored per unit (tree or hectare)
    annual_absorption_tonnes: float # tonnes CO₂ absorbed per unit per year at climax
    soil_carbon_tonnes: float       # tonnes CO₂ stored in soil beneath each unit
    soil_release_fraction: float    # fraction of soil carbon released on extraction (0.0–1.0)
                                    # not all soil carbon is released — some remains in deeper layers
    carbon_price_per_tonne: float   # € per tonne CO₂ (default: EU ETS price)
    absorption_maturation_curve: Optional[SuccessionCurve] = None
                                    # how carbon absorption ramps up during succession
                                    # (a sapling absorbs far less than a mature tree)
```

**Integrated into Resource:**

```python
@dataclass
class Resource:
    # --- existing fields ---
    name: str
    total_units: int
    unit_label: str
    safe_threshold: float
    revenue_per_unit: float
    
    # --- new field ---
    carbon_profile: Optional[CarbonProfile] = None  # None → no carbon accounting
```

### Preconfigured Carbon Profiles

| Parameter | Oak Valley | Costa Brava Holm Oak | Costa Brava Posidonia |
|---|---|---|---|
| Stored carbon (t CO₂/unit) | 0.8 t/tree | 0.5 t/tree | 130 t/ha |
| Annual absorption (t CO₂/unit/yr) | 0.022 t/tree/yr | 0.018 t/tree/yr | 5.9 t/ha/yr (fixation) |
| Soil carbon (t CO₂/unit) | 0.3 t/tree | 0.35 t/tree | 2,600 t/ha |
| Soil release fraction | 0.25 | 0.25 | 0.05 |
| Carbon price (€/t CO₂) | 80.0 | 80.0 | 80.0 |
| **Confidence** | medium | medium | medium–high |

**Rationale (with literature sources):**

- **Holm oak per-tree stored carbon (0.5 t CO₂/tree):** Sferlazza et al. (2018, iForest) measured a mature 40-year holm oak coppice stand in Sicily at ~246 Mg C/ha aboveground with ~1,800 stems/ha, giving ~0.14 t C/tree = ~0.5 t CO₂/tree for aboveground biomass. This aligns with Ruiz-Peinado et al. (2012) biomass equations for Mediterranean hardwoods. Value: **medium confidence**.
- **Holm oak annual absorption (0.018 t CO₂/tree/yr):** Derived from aboveground carbon accumulation over 40-year rotation: ~246 Mg C/ha ÷ 40yr ÷ ~1,800 stems/ha × 3.67 (C→CO₂ ratio) ≈ 0.012 t CO₂/tree/yr for aboveground only, increased to 0.018 to include belowground and soil accumulation. Note: a tourism website (Almodovar) claims "5 tonnes CO₂/year" per adult holm oak — this appears to be a per-hectare misquote and should be disregarded. Value: **medium confidence**.
- **Holm oak soil carbon (0.35 t CO₂/tree):** González et al. (2012, Eur J For Res) measured soil organic carbon stocks (top 10cm) in holm oak stands across mainland Spain at 1.4–17.9 kg C/m², with dense forests averaging 7.6 kg C/m² = 76 Mg C/ha = ~279 t CO₂/ha. At ~800 trees/ha for dense forest, ~0.35 t CO₂/tree. Value: **medium confidence**.
- **Holm oak soil release fraction (0.25):** Sferlazza et al. (2018) found soil carbon stock did NOT vary significantly with coppicing in holm oak systems — the belowground root biomass (root:shoot ratio = 1.0 for holm oak, far higher than other oaks) persists after cutting and protects soil carbon. Reduced from 0.40 to 0.25 to reflect this stability. Value: **low confidence** — depends heavily on disturbance type (coppicing vs. complete clearing with soil disruption would differ greatly).
- **Posidonia stored carbon (130 t CO₂/ha):** This represents living biomass + recent dead sheaths. The value 35 t/ha in the original spec was the carbon (not CO₂) figure from some sources; converting: Pergent-Martini et al. (2021) report total fixation of ~1.3 Mg C/ha/yr and total above+belowground living biomass of approximately 35 Mg C/ha = ~130 t CO₂/ha. Value: **medium confidence**.
- **Posidonia annual absorption (5.9 t CO₂/ha/yr fixation):** Pergent-Martini et al. (2021, Marine Environmental Research) synthesized ~100 measurements across the Mediterranean and found total carbon fixation of 1,302 g C/m²/yr = ~1.3 Mg C/ha/yr in blades, but the more commonly cited integrative value at 15m depth is 1.62 Mg C/ha/yr (Monnier et al. 2020, Corsica) = **5.9 t CO₂/ha/yr total fixation**. IMPORTANT: Only 27–30% of this is permanently sequestered in the matte (~1.6–1.8 t CO₂/ha/yr). The 5.9 figure is gross fixation; for "absorption lost" in the double externality calculation, use 1.7 t CO₂/ha/yr as the long-term sequestration rate. The original "15× Amazon" comparison was misleading — corrected below. Value: **medium–high confidence** (well-studied).
- **Posidonia matte carbon (2,600 t CO₂/ha):** Monnier et al. (2020) measured 711 Mg C/ha of organic carbon trapped in matte (mean thickness 210 cm) in Corsica = **2,607 t CO₂/ha**. This is carbon accumulated over ~1,580 years (confirmed by radiocarbon dating). The original spec's 150 t/ha dramatically underestimated this — it was off by ~17×. This is one of the most important corrections: destruction of Posidonia matte releases millennia of stored carbon. Value: **medium–high confidence**.
- **Posidonia soil release fraction (0.05):** Reduced from 0.20 to 0.05. The matte structure is extremely stable when intact — most carbon is deep and anaerobic. However, physical destruction (trawling, anchoring, dredging) exposes matte to oxidation. The 0.05 represents a conservative estimate that only the top layers (~5%) are oxidized on disturbance. The total release is still catastrophic: 0.05 × 2,600 = 130 t CO₂/ha released. For severe mechanical destruction, release fraction could be higher (0.10–0.20) — this is an area of active research. Value: **low confidence** — highly dependent on disturbance type.
- **Carbon price at €80/tonne:** EU ETS prices in 2025 fluctuated between €60–84/t CO₂ (EC Autumn 2025 forecast). €80 is within range. BNEF forecasts ~€149/t by 2030. We use €80 as a conservative present-day anchor. This is a configurable parameter — the same anchor that v0.7's endogenous pricing system will use. Value: **high confidence** (observed market price).

**Correction on the "15× Amazon" claim:** The original spec stated Posidonia absorbs 3.5 t CO₂/ha/yr, described as "15× Amazon per hectare." This comparison is misleading. The correct comparison is: Posidonia *sequesters* (permanently buries) ~1.7 t CO₂/ha/yr, while tropical forests sequester ~2–4 t CO₂/ha/yr net. Where Posidonia is truly exceptional is not absorption rate but **storage duration** — the matte preserves carbon for millennia vs. centuries for forest soils. The correct way to frame this: Posidonia meadows store 2,600 t CO₂/ha, roughly 5–10× the total carbon stock of a mature Mediterranean forest stand (~280–520 t CO₂/ha total).

### Carbon in the Simulation

**Extraction mode:**

At each extraction step, compute:

```python
carbon_released = stored_carbon + (soil_carbon * soil_release_fraction)
absorption_lost_per_year = annual_absorption * years_remaining_estimate
carbon_cost = (carbon_released + absorption_lost_per_year) * carbon_price

# years_remaining_estimate: how many productive years this unit would have had
# For trees: average remaining lifespan (e.g. 80 years for holm oak)
# For Posidonia: effectively infinite (meadows persist for millennia)
# This is discounted to present value in v0.6
```

The carbon cost is added to the existing externality calculation as a separate line item, not replacing the Carbon & Climate agent's contribution but supplementing it with precise per-unit accounting.

**Restoration mode:**

During the maturation timeline, each year computes:

```python
absorbed_this_year = units_restored * annual_absorption * succession_service_fraction(year)
```

A pioneer sapling absorbs a fraction of what a mature tree absorbs. The succession curve applies to absorption rate too. The cumulative absorption over the maturation timeline represents the carbon recovery — which can be compared against the release to show the **carbon payback period** (how many years of absorption it takes to recapture the carbon that was released).

### Report Changes (Carbon)

```
  ── Carbon Accounting ───────────────────────────────────
  Carbon released (biomass):            4,000 tonnes CO₂
  Carbon released (soil):              1,600 tonnes CO₂
  Total carbon released:               5,600 tonnes CO₂
  
  Future absorption foregone:          1,100 tonnes CO₂/yr
  (over est. 80 remaining productive years)
  
  Carbon externality (release):          €448,000
  Carbon externality (foregone):         €176,000/yr
  
  Carbon payback period:                   ~51 years
  (years of restored absorption to recapture released carbon)
```

---

## Part 4: Resilience Zones

### The Science (Foundation F7)

Resilience is a system property. We cannot predict in advance whether an ecosystem will be resilient to a specific disturbance. The safe extraction threshold is our best estimate of where resilience holds — but it's an estimate, not a law of nature.

Foundation F7 says: "Current science cannot reliably determine whether an ecosystem will be resilient to a specific disturbance before it occurs."

This means Gaia should not pretend its threshold is precise. There's a zone of uncertainty around it.

### The Model: Three Zones

```
Ecosystem Health
  1.0 │━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      │  GREEN ZONE                    
      │  Ecosystem very likely resilient.
      │  Extraction cost is modest.
      │  Model confidence: HIGH
      │
  T+W │┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
      │  YELLOW ZONE (width W)        ⚠ WARNING
      │  Resilience uncertain.
      │  Model confidence: DEGRADED
      │  Damage estimates carry ±uncertainty
      │
  T   │═══════════════════════════════════════════════ Threshold
      │  RED ZONE                      ⚠⚠ CRITICAL
      │  Resilience likely compromised.
      │  Model confidence: LOW
      │  Potential irreversibility flagged
      │
  0.0 │━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      └───────────────────────────────────────── Extraction
```

Where:
- `T` = safe extraction threshold (the existing `safe_threshold` parameter)
- `W` = warning zone width (configurable, default 0.10 — i.e. the yellow zone starts 10 percentage points before the threshold)

### Data Model

```python
@dataclass
class ResilienceConfig:
    """Resilience zone configuration for uncertainty flagging."""
    warning_zone_width: float = 0.10  # fraction of total resource
                                       # yellow zone starts at threshold + width
    confidence_green: float = 0.90     # model confidence in green zone (90%)
    confidence_yellow: float = 0.60    # model confidence in yellow zone (60%)
    confidence_red: float = 0.30       # model confidence in red zone (30%)
    irreversibility_flag_ratio: float = 0.50  # flag irreversibility warning when depletion > this
```

**Integrated into Resource:**

```python
@dataclass
class Resource:
    # --- existing fields ---
    ...
    
    # --- new field ---
    resilience: Optional[ResilienceConfig] = None  # None → no resilience flagging
```

### Zone Computation

At each simulation step:

```python
remaining_fraction = 1.0 - depletion_ratio
threshold = resource.safe_threshold
warning_start = threshold + resource.resilience.warning_zone_width

if remaining_fraction > warning_start:
    zone = "green"
    confidence = resilience.confidence_green
elif remaining_fraction > threshold:
    zone = "yellow"
    # Linearly interpolate confidence from green to yellow across the warning zone
    t = (warning_start - remaining_fraction) / resilience.warning_zone_width
    confidence = resilience.confidence_green - t * (resilience.confidence_green - resilience.confidence_yellow)
else:
    zone = "red"
    # Linearly interpolate from yellow to red based on how far past threshold
    t = min(1.0, (threshold - remaining_fraction) / threshold)
    confidence = resilience.confidence_yellow - t * (resilience.confidence_yellow - resilience.confidence_red)
```

### SimulationStep Changes

```python
@dataclass
class SimulationStep:
    # --- existing fields ---
    ...
    
    # --- new fields ---
    resilience_zone: str             # "green", "yellow", "red"
    model_confidence: float          # 0.0–1.0
    irreversibility_warning: bool    # True if depletion > irreversibility_flag_ratio
```

### Report Changes (Resilience)

```
  ── Resilience Assessment ──────────────────────────────
  Current zone:          ⚠ YELLOW — Resilience uncertain
  Model confidence:      67%
  
  Zone transitions during extraction:
    Green → Yellow at step 2,000 (20% depletion)
    Yellow → Red at step 3,000 (30% depletion, threshold)
  
  ⚠ IRREVERSIBILITY WARNING at step 5,000 (50% depletion)
    Ecosystem damage may be partially irreversible.
    Restoration estimates carry significant uncertainty.
```

### Confidence-Adjusted Costs

v0.4 does NOT change the externality numbers based on confidence — the reported costs remain point estimates. Instead, it adds **confidence bands**:

```
  Total Externality:                    €5,750,000
  Confidence band (67%):               €3,800,000 — €7,700,000
```

The band is computed as `cost × (1 ± (1 - confidence))` — a simple heuristic that widens as confidence drops. This is not a statistical confidence interval — it's a rough indication that the model's precision degrades in the yellow and red zones. True uncertainty quantification (Monte Carlo) is deferred to v0.8.

---

## Preconfigured Resilience Configurations

| Ecosystem | Warning Width | Irreversibility Flag |
|---|---|---|
| Oak Valley (temperate) | 0.10 | 0.60 |
| Costa Brava Holm Oak | 0.12 | 0.50 |
| Costa Brava Posidonia | 0.15 | 0.40 |

**Rationale:**

- **Oak Valley** has a narrow warning zone (10%) because temperate forests are relatively resilient and the threshold is less uncertain.
- **Costa Brava Holm Oak** has a slightly wider warning zone (12%) because Mediterranean drought adds unpredictability — fire risk makes the true tipping point harder to know.
- **Costa Brava Posidonia** has the widest warning zone (15%) and the earliest irreversibility flag (40%) because the 1–6 cm/year growth rate means that beyond moderate degradation, recovery timelines become effectively infinite. The line between "very long recovery" and "functionally irreversible" is genuinely blurry for Posidonia.

---

## Project Structure Changes

```
gaia/
├── __init__.py
├── models.py              # Extended: CarbonProfile, SuccessionCurve, ResilienceConfig,
│                          #           MaturationStep, RestorationConfig
│                          # Extended: Resource + carbon_profile, resilience
│                          # Extended: Agent + succession_curve
│                          # Extended: SimulationStep + resilience fields
│                          # Extended: RestorationResult + maturation timeline
├── damage.py              # Unchanged
├── recovery.py            # Unchanged (v0.2 recovery still used for planting pass)
├── succession.py          # NEW: SuccessionCurve evaluation, maturation timeline computation
├── carbon.py              # NEW: CarbonProfile accounting, release + absorption calculations
├── resilience.py          # NEW: Zone computation, confidence interpolation, warning generation
├── propagation.py         # Unchanged
├── simulation.py          # Extended: maturation pass, carbon tracking, resilience zone tagging
├── validation.py          # Extended: validate succession curves, carbon profiles, resilience config
├── report.py              # Extended: maturation timeline, carbon accounting, resilience assessment
└── cases/
    ├── __init__.py
    ├── forest.py          # Extended: succession curve, carbon profile, resilience config
    ├── costa_brava.py     # Extended: succession curve, carbon profile, resilience config
    └── posidonia.py       # Extended: succession curve, carbon profile, resilience config

tests/
├── test_succession.py     # NEW: succession curve evaluation, phase transitions, agent-specific curves
├── test_carbon.py         # NEW: carbon release, absorption, payback period
├── test_resilience.py     # NEW: zone computation, confidence interpolation, warnings
├── test_maturation.py     # NEW: maturation timeline, maturation gap, time-to-X% metrics
├── test_simulation.py     # Extended: full extraction+restoration with all v0.4 features
├── test_forest.py         # Extended: time-aware restoration
├── test_costa_brava.py    # Extended: time-aware restoration + carbon + resilience
├── test_posidonia.py      # Extended: time-aware restoration + carbon + resilience
├── test_damage.py         # Unchanged
├── test_models.py         # Extended: new dataclasses
├── test_validation.py     # Extended: new validation rules
├── test_propagation.py    # Unchanged
├── test_recovery.py       # Unchanged
└── test_restoration.py    # Extended: backward compat with no succession curve
```

---

## Testing Strategy

### test_succession.py — Succession Curve (NEW)

| Test | What it checks | Foundation |
|---|---|---|
| `test_zero_service_during_delay` | Service = 0.0 for all years < maturation_delay | F8 — pioneer establishment |
| `test_pioneer_phase_low_service` | Service ≤ pioneer_service during pioneer years | F8 |
| `test_intermediate_phase_accelerating` | Service increases faster during intermediate than pioneer | F8 — each phase creates conditions for next |
| `test_climax_approaches_one` | Service ≥ 0.95 at climax_approach_year | F8 — climax = max services |
| `test_monotonically_increasing` | Service at year N+1 ≥ service at year N for all N | Physical — services don't decrease during recovery |
| `test_continuous_at_phase_boundaries` | No discontinuity at pioneer→intermediate and intermediate→climax transitions | Mathematical — smooth curve |
| `test_service_bounded_zero_one` | 0.0 ≤ service ≤ 1.0 for all years | Physical constraint |
| `test_agent_specific_curve_overrides_ecosystem` | Agent with custom curve uses it; agent without uses ecosystem default | Structural |
| `test_oak_valley_faster_than_costa_brava` | Same year → Oak Valley has higher service fraction than Costa Brava | Mediterranean = slower recovery |
| `test_posidonia_slowest_of_all` | Posidonia climax_approach_year > Costa Brava > Oak Valley | Marine = slowest |

### test_carbon.py — Carbon Accounting (NEW)

| Test | What it checks | Foundation |
|---|---|---|
| `test_release_includes_biomass_and_soil` | Total release = stored + (soil × release_fraction) | F9 |
| `test_soil_release_fraction_bounded` | soil_release_fraction ∈ [0.0, 1.0] | Physical |
| `test_absorption_scales_with_succession` | Year 5 absorbs less than year 50 (succession curve applied) | F8 + F9 |
| `test_carbon_payback_period_positive` | Payback > 0 for all cases | Thermodynamic — restoration always takes time |
| `test_posidonia_carbon_payback_longest` | Posidonia payback >> forest payback | Marine growth rate |
| `test_zero_carbon_profile_no_carbon_output` | When carbon_profile is None, no carbon fields in output | Backward compat |
| `test_double_externality_larger_than_release_only` | Release + foregone > release alone | F9 — double cost |
| `test_carbon_cost_at_configured_price` | Cost = tonnes × price_per_tonne exactly | Mathematical |

### test_resilience.py — Resilience Zones (NEW)

| Test | What it checks | Foundation |
|---|---|---|
| `test_green_zone_above_warning` | Zone = "green" when remaining > threshold + warning_width | F7 |
| `test_yellow_zone_between_warning_and_threshold` | Zone = "yellow" in the warning band | F7 |
| `test_red_zone_below_threshold` | Zone = "red" when remaining < threshold | F7 |
| `test_confidence_decreases_green_to_red` | Confidence monotonically decreases as depletion increases | F7 — uncertainty grows |
| `test_confidence_continuous_at_boundaries` | No discontinuity at green→yellow and yellow→red transitions | Mathematical |
| `test_irreversibility_warning_triggered` | Warning = True when depletion > irreversibility_flag_ratio | F7 |
| `test_no_resilience_config_no_zones` | When resilience is None, no zone fields in output | Backward compat |
| `test_posidonia_wider_warning_than_forest` | Posidonia warning_width > Costa Brava > Oak Valley | More fragile = more uncertainty |

### test_maturation.py — Maturation Timeline (NEW)

| Test | What it checks |
|---|---|
| `test_maturation_gap_positive` | Gap > 0 for all restoration scenarios |
| `test_maturation_gap_increases_with_damage` | More extraction → larger maturation gap |
| `test_years_to_50pct_before_years_to_90pct` | Timeline metrics are ordered correctly |
| `test_cumulative_service_monotonically_increasing` | Each year adds non-negative service value |
| `test_posidonia_maturation_gap_enormous` | Posidonia gap >> forest gap (quantifies the 81× prevention advantage more precisely) |
| `test_no_time_horizon_falls_back_to_v02` | time_horizon_years=0 → v0.2 behavior exactly |
| `test_phased_vs_immediate_planting` | Phased planting over 10 years has larger gap than immediate (later plantings mature later) |

### Ecological Plausibility Tests

| Test | What it checks |
|---|---|
| `test_forest_25yr_recovery_partial` | At year 25, forest service recovery is ~35% (intermediate phase) |
| `test_posidonia_50yr_recovery_minimal` | At year 50, Posidonia service recovery is ~25% (still intermediate) |
| `test_carbon_payback_forest_under_100yr` | Forest carbon payback < 100 years (trees absorb enough) |
| `test_carbon_payback_posidonia_over_100yr` | Posidonia carbon payback > 100 years (growth rate too slow) |
| `test_maturation_gap_dominates_restoration_cost` | For all cases, maturation gap > direct restoration cost (the waiting is more expensive than the planting) |

---

## Report Changes Summary

### Extraction Report Additions

```
  ── Resilience Assessment ──────────────────────────────
  Current zone: ⚠ YELLOW — Resilience uncertain
  Model confidence: 67%
  Zone transitions: Green→Yellow at step X, Yellow→Red at step Y
  
  ── Carbon Accounting ──────────────────────────────────
  Carbon released (biomass + soil): X,XXX tonnes CO₂
  Future absorption foregone: XXX tonnes CO₂/yr
  Carbon externality (total): €XXX,XXX
  
  ── Externality with Confidence Band ───────────────────
  Total Externality: €X,XXX,XXX
  Confidence band: €X,XXX,XXX — €X,XXX,XXX
```

### Restoration Report Additions

```
  ── Maturation Timeline ────────────────────────────────
  Years to first services:        3 years (pioneer establishment)
  Years to 50% service recovery:  32 years
  Years to 90% service recovery:  68 years
  
  ── Maturation Gap ─────────────────────────────────────
  Total lost services during maturation: €X,XXX,XXX
  (accumulated externality while waiting for succession)
  
  This cost is IN ADDITION to restoration costs.
  True prevention advantage: restoration_cost + maturation_gap
  
  ── Carbon Recovery ────────────────────────────────────
  Carbon payback period: ~51 years
  Net carbon at year 30: -X,XXX tonnes (still negative)
  Net carbon at year 80: +X,XXX tonnes (payback achieved)
```

---

## Definition of Done

v0.4 is complete when:

1. **All v0.1/v0.2/v0.3 tests still pass.** No regressions.
2. **Succession curves produce ecologically plausible shapes** — monotonically increasing, S-shaped overall, with clear phase boundaries and configurable timelines.
3. **Maturation timelines show dramatically different recovery speeds** across the three cases: Oak Valley (decades), Costa Brava (many decades), Posidonia (century+).
4. **The maturation gap is larger than the direct restoration cost** for all three cases — confirming that the waiting is more expensive than the planting.
5. **Double carbon externality works** — extraction reports show both release and foregone absorption, with a total carbon cost per step.
6. **Carbon payback period is computed** — restoration reports show how many years of replanted absorption it takes to offset released carbon.
7. **Resilience zones are visible in extraction reports** — green/yellow/red transitions flagged at the correct extraction steps, with confidence bands on the total externality.
8. **Backward compatibility preserved** — ecosystems with no SuccessionCurve, no CarbonProfile, and no ResilienceConfig produce identical output to v0.3.
9. **Running Costa Brava Posidonia restoration with time horizon** shows that after 50 years, services are still only ~25% recovered — making the case for prevention even more dramatically than v0.2's 81× ratio.
10. **`pytest tests/ -v` — all green.**

---

## Parameter Documentation

All new parameters carry the same documentation standard as v0.3:

- **Value** — the number used
- **Source** — literature reference where available (see individual rationale sections), "working estimate" otherwise
- **Confidence** — varies per parameter (see carbon profile and succession curve rationale sections for per-parameter confidence ratings)
- **Note** — what the ecologist should evaluate

### Key Literature References

- **Sferlazza et al. (2018)** — iForest 11: 344-351. Carbon stocks in five pools for holm oak coppice, Sicily. Source for holm oak per-tree carbon, soil carbon stability, root:shoot ratio.
- **González et al. (2012)** — Eur J For Res 131: 1653-1667. Soil carbon stocks across 103 Quercus ilex stands in mainland Spain.
- **Pergent-Martini et al. (2021)** — Marine Environmental Research 165. Carbon fixation and sequestration synthesis across ~100 Mediterranean Posidonia measurements. Source for fixation rate, sequestration rate.
- **Monnier et al. (2020)** — Vie et Milieu 70. Posidonia matte carbon in Corsica. Source for 711 Mg C/ha matte stock, 1,580 years accumulation (radiocarbon confirmed).
- **Marbà et al. (1996)** — Marine Ecology Progress Series 137: 203-213. Growth and population dynamics of Posidonia across 29 Spanish meadows. Source for 1-6 cm/yr rhizome growth rate.
- **Bacci et al. (2025)** — Restoration Ecology. Long-term response of P. oceanica transplantation at 10 and 14 years.
- **Coastal Wiki: Posidonia oceanica entry** — 600 years to cover 66% of available space (numerical model). 30-year average branching interval.
- **EU ETS price data** — EC Autumn 2025 forecast: €60-80/t range in 2025. BNEF forecast: ~€149/t by 2030.

### Parameter Sensitivity

The **succession curve timelines** are the most important parameters for ecological review. They determine the shape of the maturation gap, which in turn determines the true cost of "cut now, replant later." Getting the pioneer/intermediate/climax transition years wrong by even a decade dramatically changes the economic story.

The **Posidonia matte carbon stock** (2,600 t CO₂/ha) is the single most consequential parameter correction from the literature review. The original estimate of 150 t/ha was off by ~17×. This means the carbon externality of Posidonia destruction is far larger than originally specified — matte destruction releases millennia of stored carbon, and this is the core of the economic case for Posidonia protection.

The **carbon profiles** now have literature backing for most parameters, but the **soil release fractions** remain the least certain — they depend heavily on the type and intensity of disturbance (coppicing vs. clear-cutting vs. mechanical destruction), and there is limited experimental data on carbon release from disturbed Posidonia matte at ecosystem scale.

The **resilience zone widths** are inherently uncertain — that's the point. The ecologist should validate whether the widths feel right: "is it reasonable that 10% below the threshold we're still uncertain about resilience?"
