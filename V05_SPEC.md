# Gaia v0.5 — Specification: Physical Substrate & Derived Carrying Capacity

## Overview

v0.5 is the version where **the ground becomes real**. In v0.1–v0.4, carrying capacity (K) is a fixed number: 10,000 trees, 1,000 hectares. It doesn't change, degrade, or constrain what the ecosystem can become. But in reality, carrying capacity is not a constant — it is an emergent property of the physical substrate. Soil depth determines how many trees a hillside can support. Water clarity determines how deep Posidonia can grow. Rainfall determines whether a Mediterranean forest can exist at all.

v0.5 introduces the physical layer beneath the biology:

1. **Substrate profiles** — measurable physical properties (soil depth, water clarity, sediment stability) that constrain what an ecosystem can support
2. **Derived carrying capacity** — K computed from substrate state, not manually set; K degrades when substrate degrades
3. **Substrate degradation feedback** — extraction doesn't just damage agents, it damages the ground they stand on; degraded substrate lowers K, which amplifies damage in a vicious cycle
4. **Substrate recovery constraints** — some substrate damage is effectively irreversible on human timescales (soil formation: ~0.1 mm/yr; matte reformation: centuries)

**Scientific foundations used:** Carrying Capacity (F4 deepened), Resilience (F7 deepened), plus all foundations from v0.1–v0.4.

**The core insight:** Ecosystems don't just lose species when degraded — they lose the capacity to support species. A deforested Mediterranean hillside doesn't just lack trees; it lacks the soil to grow trees. A destroyed Posidonia meadow doesn't just lack seagrass; it lacks the stable substrate and clear water for seagrass to establish. This is the mechanism behind irreversibility, and v0.5 models it explicitly.

---

## What Changes from v0.4

### Conceptual shift

In v0.1–v0.4, the ecosystem's carrying capacity is an input parameter. You configure `total_units: 10000` and the model never questions whether the land could actually support 10,000 trees. Carrying capacity is treated as a fixed ceiling — damage reduces health below K, but K itself is immutable.

In v0.5, carrying capacity becomes a **derived, dynamic quantity**. The model asks: given this soil depth, this rainfall, this water clarity — what K does the substrate actually support? And critically: when extraction damages the substrate, K drops, which means the ecosystem's "ceiling" moves downward even as health deteriorates.

This creates the **degradation spiral** that makes ecosystem destruction so much worse than naive models suggest: extraction → substrate damage → lower K → same absolute damage = higher proportional damage → accelerated agent stress → more substrate exposure → more substrate damage.

### What stays the same

- All v0.1/v0.2/v0.3/v0.4 data structures (extended, not replaced)
- Damage functions, trophic amplification, interaction propagation (unchanged)
- Succession curves, carbon externality, resilience zones (unchanged)
- All previous tests must continue to pass

### Backward compatibility

When no `SubstrateProfile` is configured, K remains a fixed input as before. All v0.1–v0.4 behavior is preserved exactly. Substrate modeling is opt-in.

---

## Part 1: Physical Substrate Profiles

### The Science

Every ecosystem sits on a physical substrate that constrains what can live there. The substrate is not biological — it is geophysical. But it determines the biological carrying capacity absolutely:

**Terrestrial (forests):**
- **Soil depth** determines root volume, water retention, and nutrient availability. Mediterranean soils on limestone often have only 10–50 cm of productive soil overlying rock. Once lost to erosion, soil formation occurs at ~0.3–1.0 t/ha/yr (equivalent to ~0.02–0.08 mm/yr assuming bulk density ~1,300 kg/m³). A 30 cm soil profile took thousands of years to form. (Source: PNAS, Montgomery 2007: geological erosion rates ~0.3 mm/yr under natural conditions; ESDAC JRC: soil formation 0.3–1.4 t/ha/yr in Europe.)
- **Water availability** (precipitation + groundwater) sets the fundamental limit on biomass. Mediterranean climates are defined by summer drought (580 mm mean annual rainfall at Prades, NE Spain; 450–600 mm across much of coastal Catalonia). Below ~350 mm/yr, forests cannot establish; holm oak requires ~400+ mm/yr.
- **Slope and aspect** determine insolation, erosion susceptibility, and microclimate. South-facing Mediterranean slopes lose soil faster and support lower density stands.

**Marine (Posidonia):**
- **Water clarity** (light attenuation, Kd) sets the lower depth limit absolutely. Posidonia requires ~10% of surface irradiance to photosynthesize. In clear oligotrophic Mediterranean waters, this allows growth to 35–45 m depth. In turbid coastal waters, the limit may be 10–15 m. Eutrophication or sediment plumes shrink the habitable zone. (Source: EUSeaMap light thresholds; Duarte 1991; Pergent et al. 1995; strongsealife.eu: "surface to approximately 30–35 meters, reaching beyond 40 m in particularly clear waters.")
- **Sediment stability** determines whether rhizomes can anchor. Posidonia grows on sand, dead matte, or rock — but not on unstable mobile sediment or in areas with wave orbital velocities >38–42 cm/s. (Source: Infantes et al. 2009, Botanica Marina.)
- **Matte integrity** — the matte (interlaced roots, rhizomes, and trapped sediment) is itself a substrate. Posidonia grows ON its own historical matte. Destroying the matte removes the physical platform for recolonization. Matte formation rate: rhizome growth 1–6 cm/yr horizontal, vertical accretion ~1 mm/yr (derived from Monnier et al. 2020: 210 cm over ~1,580 years).

### Data Model

```python
@dataclass
class SubstrateProfile:
    """Physical substrate properties that constrain carrying capacity.
    
    Each property is a measurable geophysical quantity with units.
    The substrate profile is ecosystem-specific — terrestrial and marine
    profiles use different properties.
    """
    # Identifier
    substrate_type: str  # "terrestrial_soil", "marine_sediment", "marine_matte"
    
    # Primary constraint properties (at least one required)
    soil_depth_cm: float | None = None          # Terrestrial: productive soil depth
    water_availability_mm_yr: float | None = None  # Terrestrial: effective annual precipitation
    water_clarity_kd: float | None = None       # Marine: diffuse attenuation coefficient (m⁻¹)
    sediment_stability: float | None = None     # Marine: 0.0 (mobile) to 1.0 (rock/consolidated matte)
    
    # Degradation rates (how fast substrate degrades when exposed)
    erosion_rate_unprotected: float = 0.0  # t/ha/yr or mm/yr when vegetation removed
    erosion_rate_protected: float = 0.0    # t/ha/yr or mm/yr under intact vegetation
    
    # Recovery rates (how fast substrate recovers — typically very slow)
    formation_rate: float = 0.0  # t/ha/yr or mm/yr of new substrate formation
    
    # Derived capacity function (see Part 2)
    # Maps substrate state → carrying capacity fraction (0.0 to 1.0)
    capacity_function: str = "linear"  # "linear", "threshold", "logistic"
    
    # Confidence
    confidence: str = "medium"  # "low", "medium", "high"
```

### Preconfigured Substrate Profiles

#### Oak Valley Forest (Temperate Deciduous)

```python
OAK_VALLEY_SUBSTRATE = SubstrateProfile(
    substrate_type="terrestrial_soil",
    soil_depth_cm=45.0,              # Moderate temperate forest soil
    water_availability_mm_yr=800.0,  # Adequate for deciduous forest
    erosion_rate_unprotected=15.0,   # t/ha/yr — moderate for temperate slopes
    erosion_rate_protected=0.5,      # t/ha/yr — intact forest floor
    formation_rate=0.8,              # t/ha/yr — temperate soil formation
    capacity_function="linear",
    confidence="medium"
)
```

**Rationale:** Temperate deciduous forests on moderate slopes. Soil erosion under forest cover is minimal (~0.5 t/ha/yr per PNAS Montgomery 2007), but rises dramatically when exposed (~10–25 t/ha/yr per ESDAC European data for deforested moderate slopes). Soil formation ~0.3–1.4 t/ha/yr across Europe (JRC ESDAC). We use 0.8 as a central value for productive temperate conditions. Confidence: medium (well-studied systems, but site-specific variation is high).

#### Costa Brava Holm Oak Forest

```python
HOLM_OAK_SUBSTRATE = SubstrateProfile(
    substrate_type="terrestrial_soil",
    soil_depth_cm=30.0,               # Shallow Mediterranean soil on limestone
    water_availability_mm_yr=550.0,   # Mediterranean: 450-650 mm typical Costa Brava
    erosion_rate_unprotected=25.0,    # t/ha/yr — high for Mediterranean slopes
    erosion_rate_protected=1.0,       # t/ha/yr — holm oak roots stabilize well
    formation_rate=0.4,               # t/ha/yr — slow in Mediterranean conditions
    capacity_function="threshold",    # Below minimum soil depth → K collapses
    confidence="medium"
)
```

**Rationale:**
- **Soil depth 30 cm:** Mediterranean holm oak forests on limestone karst typically have shallow soils. González et al. (2012) measured across 103 Q. ilex stands in Spain and found highly variable soil depths, but 20–40 cm is typical on rocky slopes. Sferlazza et al. (2018) Sicily study found productive coppice on shallow soils.
- **Water availability 550 mm/yr:** Costa Brava receives ~550–650 mm/yr (data from Prades experiment at 580 mm; broader Catalonia coastal belt ~500–700 mm). This is adequate for holm oak but near the drought stress threshold.
- **Erosion unprotected 25 t/ha/yr:** Spain has some of the highest erosion rates in Europe. RUSLE2015 data from JRC puts the national mean at 4.0 t/ha/yr (including forest cover), but deforested Mediterranean slopes regularly lose 20–40 t/ha/yr in individual storms (ESDAC: "Losses of 20 to 40 t/ha in individual storms that may happen once every two or three years are measured regularly in Europe"). Catalonia specifically cited as exceeding the critical 12 t/ha/yr threshold. 25 t/ha/yr for bare Mediterranean slope is conservative. **CRITICAL NOTE:** In 9 of Spain's 17 regions, erosion exceeds 12 t/ha/yr. Some Catalonian areas exceed 25 t/ha/yr.
- **Erosion protected 1.0 t/ha/yr:** Holm oak's extraordinary 1:1 root-to-shoot ratio (Sferlazza 2018) provides excellent soil stabilization. Under intact holm oak forest, erosion is minimal. Copernicus/SOIL preprint: forested Mediterranean slopes ~5 t/ha/yr by ¹³⁷Cs method, but this includes some disturbed forest; pristine dense holm oak likely ~1 t/ha/yr.
- **Formation rate 0.4 t/ha/yr:** Mediterranean soils form very slowly. Limestone weathering is slow; hot dry summers limit biological activity; frequent fires mineralize organic matter. 0.4 t/ha/yr is at the low end of the European range (0.3–1.4 per ESDAC) but appropriate for Mediterranean conditions. This means ~0.03 mm/yr — a destroyed 30 cm soil profile would take ~10,000 years to reform from bedrock.
- **Threshold capacity function:** Below a critical soil depth (~8–10 cm), holm oak simply cannot establish — roots cannot penetrate sufficiently into limestone cracks, water retention is nil. This creates a cliff-edge: above the threshold, K scales roughly linearly with soil depth; below it, K drops to near-zero. This is the irreversibility mechanism.

**Confidence: medium.** Erosion rates are well-studied at the European scale (JRC RUSLE2015) but highly site-specific locally. The 25 t/ha/yr unprotected rate is within the range of Mediterranean plot studies but could be higher on steep slopes or lower on flat terrain.

#### Costa Brava Posidonia Meadow

```python
POSIDONIA_SUBSTRATE = SubstrateProfile(
    substrate_type="marine_matte",
    soil_depth_cm=None,                # Not applicable
    water_availability_mm_yr=None,     # Not applicable
    water_clarity_kd=0.06,             # m⁻¹ — clear oligotrophic Mediterranean
    sediment_stability=0.85,           # High — consolidated matte substrate
    erosion_rate_unprotected=5.0,      # mm/yr matte erosion when exposed
    erosion_rate_protected=0.0,        # Intact meadow accretes, not erodes
    formation_rate=1.0,                # mm/yr vertical matte accretion
    capacity_function="logistic",      # Light attenuation creates smooth depth gradient
    confidence="low-medium"
)
```

**Rationale:**
- **Water clarity Kd=0.06 m⁻¹:** Oligotrophic Mediterranean waters off Costa Brava. At Kd=0.06, 10% surface light reaches ~38 m depth (ln(0.10)/0.06 ≈ 38 m), consistent with observed Posidonia depth limits of 35–45 m in clear waters. Coastal wiki and Pergent et al.: depth extends to 40–48 m in particularly clear waters. More turbid coastal waters (Kd=0.10–0.15) would limit depth to 15–23 m.
- **Sediment stability 0.85:** Consolidated matte is extremely stable — it has been forming for centuries to millennia. Score of 0.85 (out of 1.0, where 1.0 = bedrock) reflects that matte, while stable, can be mechanically disrupted by trawling, anchoring, or storm surge in shallow areas. Infantes et al. (2009) showed Posidonia absent where near-bottom orbital velocity exceeds 38–42 cm/s.
- **Matte erosion 5 mm/yr when exposed:** When Posidonia dies and the matte surface is exposed to currents, the organic-sediment matrix gradually erodes. This is a rough estimate — exposed matte in anchoring scars shows visible degradation over years-to-decades. No precise literature figure exists for bulk matte erosion rate. Confidence: low.
- **Matte formation 1.0 mm/yr:** Derived from Monnier et al. (2020): 210 cm matte thickness accumulated over ~1,580 years ≈ 1.3 mm/yr. We round down to 1.0 mm/yr as a conservative estimate that accounts for periods of slower accretion. This is consistent with vertical rhizome growth rates (orthotropic rhizome elongation ~8.8 mm/yr per Marbà et al. 1996), minus compaction and decomposition.
- **Logistic capacity function:** Light attenuation with depth is exponential (Beer-Lambert law), so the relationship between water clarity and habitable area is smooth but nonlinear. A small change in Kd near the depth limit produces a large change in habitable area; a small change in already-clear water has minimal effect. This maps naturally to a logistic.

**Confidence: low-medium.** Posidonia depth limits are well-documented. Matte erosion rates are poorly quantified — this is an active research gap. Light attenuation values vary seasonally and with coastal development.

---

## Part 2: Derived Carrying Capacity

### The Core Mechanism

Currently, carrying capacity is a fixed input:
```python
resource = Resource(name="Holm Oak Forest", total_units=1800, ...)
```

With substrate modeling, K becomes a function of substrate state:

```python
K_current = K_pristine × substrate_capacity_fraction(substrate_state)
```

Where `substrate_capacity_fraction` maps the current substrate quality to a fraction [0.0, 1.0] of the pristine carrying capacity.

### Capacity Functions

Three options, selected per-profile:

**Linear:**
```
capacity = substrate_state / substrate_pristine

Example: soil at 20cm, pristine was 30cm → capacity = 0.67
K_current = 1800 × 0.67 = 1200 trees
```

Use for: systems where capacity degrades proportionally to substrate. Simple, interpretable, appropriate when no hard thresholds exist.

**Threshold:**
```
if substrate_state < critical_minimum:
    capacity = substrate_state / critical_minimum × residual_fraction
else:
    capacity = critical_minimum_capacity + (1 - critical_minimum_capacity) × 
               (substrate_state - critical_minimum) / (substrate_pristine - critical_minimum)

Example: soil at 5cm, critical minimum 8cm → capacity ≈ 0.03
         soil at 20cm, critical minimum 8cm, pristine 30cm → capacity ≈ 0.60
```

Use for: holm oak forest on limestone, where below a minimum soil depth, trees simply cannot establish roots. This captures the irreversibility cliff.

**Logistic:**
```
capacity = 1.0 / (1.0 + exp(-steepness × (substrate_state - inflection)))

Normalized so capacity(pristine) ≈ 1.0 and capacity(0) ≈ 0.0
```

Use for: Posidonia meadows where the relationship between water clarity and habitable depth follows Beer-Lambert exponential attenuation. The inflection point corresponds to the depth/clarity combination where ~50% of potential habitat is accessible.

### Data Model

```python
@dataclass
class SubstrateState:
    """Current state of the physical substrate.
    
    Tracks how substrate has degraded from its pristine condition
    and computes the derived carrying capacity.
    """
    profile: SubstrateProfile
    
    # Current substrate values (initialized to pristine)
    current_soil_depth_cm: float | None = None
    current_water_clarity_kd: float | None = None
    current_sediment_stability: float | None = None
    
    # Pristine reference values (set at initialization)
    pristine_soil_depth_cm: float | None = None
    pristine_water_clarity_kd: float | None = None
    pristine_sediment_stability: float | None = None
    
    # Computed
    capacity_fraction: float = 1.0  # 0.0 to 1.0
    years_to_recover: float = 0.0   # Estimated years to return to pristine substrate
    
    def compute_capacity(self) -> float:
        """Compute K fraction from current substrate state."""
        ...
    
    def degrade(self, vegetation_cover: float, years: float = 1.0) -> None:
        """Apply substrate degradation based on current vegetation cover.
        
        vegetation_cover: 0.0 (bare) to 1.0 (fully vegetated)
        Erosion rate interpolates between protected and unprotected rates.
        """
        ...
    
    def recover(self, years: float = 1.0) -> None:
        """Apply substrate recovery at the formation rate.
        Never exceeds pristine values.
        """
        ...
```

### Integration with Resource

```python
@dataclass  
class Resource:
    # Existing fields (unchanged)
    name: str
    total_units: int
    safe_threshold: float
    unit_revenue: float
    # ...
    
    # NEW: optional substrate
    substrate: SubstrateProfile | None = None
    substrate_state: SubstrateState | None = None
    
    @property
    def effective_carrying_capacity(self) -> int:
        """K adjusted for substrate degradation.
        
        If no substrate profile: returns total_units (backward compatible).
        If substrate profile: returns total_units × capacity_fraction.
        """
        if self.substrate_state is None:
            return self.total_units
        return int(self.total_units * self.substrate_state.capacity_fraction)
```

---

## Part 3: The Degradation Spiral

### How It Works

The key innovation of v0.5 is the **feedback loop** between extraction, substrate degradation, and carrying capacity:

```
Step 1: Extract 100 trees from 1,800 → health = 1700/1800 = 0.944
        → vegetation cover drops → erosion rate increases
        → soil depth decreases slightly

Step 2: Substrate degradation → K drops from 1800 to 1790
        → same 1700 trees, but now health = 1700/1790 = 0.950... 
        wait — that looks BETTER?
```

**IMPORTANT SUBTLETY:** The health ratio (population/K) can *improve* when K drops — the denominator shrinks. This is technically correct: a population closer to its (now-lower) carrying capacity is under less competitive stress. But it hides a crucial fact: **the ecosystem has permanently lost capacity**. The 1,790-tree forest is not equivalent to the 1,800-tree forest — it provides fewer services, supports fewer organisms, and stores less carbon.

The degradation spiral manifests not in the health ratio but in the **absolute service capacity** and the **ceiling on recovery**:

```
Before extraction:  K = 1800, population = 1800, max services = 100%
After extraction:   K = 1750 (soil loss), population = 1200
                    Even if population recovers fully: max services = 1750/1800 = 97.2%
                    The 2.8% is PERMANENTLY LOST until soil reforms (centuries)
```

After severe deforestation with soil loss:
```
K = 800 (severe soil erosion), population = 200
Even full recovery only reaches 800/1800 = 44.4% of original services
Soil recovery to 1800 capacity: ~3,000–10,000 years
```

### Substrate Degradation per Simulation Step

At each extraction step, after computing biological damage:

```python
def compute_substrate_degradation(ecosystem, extraction_step):
    """Apply substrate degradation based on current vegetation cover."""
    
    resource = ecosystem.resource
    if resource.substrate_state is None:
        return  # No substrate modeling — backward compatible
    
    # Vegetation cover proxied by remaining population fraction
    vegetation_cover = resource.remaining_units / resource.total_units
    
    # Interpolate erosion rate between protected and unprotected
    profile = resource.substrate_state.profile
    erosion_rate = (
        vegetation_cover * profile.erosion_rate_protected +
        (1 - vegetation_cover) * profile.erosion_rate_unprotected
    )
    
    # Apply degradation (per-step, not per-year — steps may represent
    # different time intervals depending on extraction speed)
    resource.substrate_state.degrade(
        vegetation_cover=vegetation_cover,
        years=extraction_step.time_delta_years  # configurable
    )
    
    # Recompute K
    resource.substrate_state.compute_capacity()
    
    # Update effective K in resource
    # (This feeds back into damage calculations for the next step)
```

### Erosion Rate Interpolation

The erosion rate is NOT binary (protected vs. unprotected). It follows a nonlinear curve where the first trees removed matter much less than the last:

```
effective_erosion = E_protected + (E_unprotected - E_protected) × (1 - cover)^α

Where α > 1 (typically α = 2.0) reflects that:
- 90% cover → nearly fully protected (canopy closure, root mat intact)
- 50% cover → substantially exposed (gaps in canopy, rain reaches soil)
- 10% cover → nearly fully exposed (isolated trees, no continuous protection)
```

This nonlinearity is critical: Mediterranean holm oak forest maintains near-full soil protection down to ~40–50% canopy cover (dense understory of Buxus, Phillyrea compensates), but protection collapses rapidly below ~30% cover. The exponent α = 2.0 captures this pattern.

For Posidonia, the equivalent is more binary: a continuous meadow stabilizes sediment; a fragmented meadow does not. α ≈ 3.0 reflects the steeper transition.

---

## Part 4: Substrate-Aware Restoration

### The Problem

v0.2 and v0.4 model restoration as "plant trees → wait → services recover." But if the soil has eroded, planting trees on bedrock doesn't work. The substrate constrains what restoration can achieve.

### Restoration Ceiling

With substrate modeling, restoration has a **ceiling** set by the current substrate state:

```
max_recoverable = K_current / K_pristine × 100%

If K has dropped from 1800 to 1200 (soil loss), then even perfect
biological restoration only recovers 66.7% of original services.

The remaining 33.3% requires substrate restoration — which operates
on geological timescales.
```

### Substrate Restoration Costs

Substrate restoration is fundamentally different from biological restoration:

**Soil:**
- Natural reformation: 0.4 t/ha/yr (holm oak substrate) → centuries to millennia
- Engineered soil import: possible but extremely expensive (~€50–200/m³ for quality topsoil, and Mediterranean sites often have access constraints)
- Erosion control (terracing, revegetation of pioneer species): can halt further loss but doesn't restore depth
- Typical approach: stabilize → revegetate with pioneers → wait decades for soil accumulation under pioneer cover

**Posidonia matte:**
- Natural reformation: ~1 mm/yr vertical accretion → millennia for meters of matte
- No engineered equivalent — matte is a biogenic structure that can only be built by living Posidonia
- Transplantation onto dead matte is possible (Bacci et al. 2025; Sicily 12-year study reached natural density on 20 m² patches) but ecosystem-scale matte recovery takes centuries
- Water clarity restoration requires addressing pollution sources — achievable in years-to-decades if political will exists

### Data Model Changes to Restoration

```python
@dataclass
class RestorationResult:
    # Existing fields from v0.2/v0.4 (unchanged)
    total_restoration_cost: float
    service_recovery_fraction: float
    # ... maturation timeline, carbon payback, etc.
    
    # NEW: substrate-constrained fields
    substrate_ceiling: float          # Max recoverable fraction (K_current/K_pristine)
    biological_recovery: float        # Recovery within current K ceiling
    substrate_recovery_years: float   # Years for substrate to return to pristine
    substrate_recovery_cost: float    # Cost of substrate stabilization (not full recovery)
    
    # NEW: the real prevention advantage
    prevention_advantage_with_substrate: float  # Includes substrate loss cost
```

### The Real Prevention Advantage

In v0.2, the prevention advantage ratio was:
```
PA = restoration_cost / prevention_cost
```

In v0.5, the ratio includes the substrate loss — the permanently reduced ceiling:
```
PA_v05 = (restoration_cost + NPV_of_permanent_capacity_loss) / prevention_cost
```

The `NPV_of_permanent_capacity_loss` is the discounted value of ecosystem services that can never be recovered because the substrate is degraded. For severe deforestation with soil loss, this term dominates the calculation and can be orders of magnitude larger than the biological restoration cost.

**Hypothesis: With substrate modeling, the prevention advantage for Posidonia jumps from 81× (v0.2) to >>100×.** Because matte recovery takes millennia, the permanent capacity loss is enormous. The economic case for prevention becomes overwhelming.

---

## Part 5: Substrate-Specific Externality in Reports

### New Report Section: "Substrate Impact"

The externality report gains a new section that quantifies substrate damage:

```
═══════════════════════════════════════════════════
SUBSTRATE IMPACT ASSESSMENT
═══════════════════════════════════════════════════

Physical substrate:     Mediterranean soil (limestone karst)
Pristine soil depth:    30.0 cm
Current soil depth:     22.3 cm (25.7% lost)
Erosion rate:           18.4 t/ha/yr (accelerating)

Carrying capacity:
  Pristine K:           1,800 trees
  Current K:            1,340 trees (74.4% of pristine)
  Capacity lost:        460 trees permanently
  
Substrate recovery:
  At current formation rate (0.4 t/ha/yr):
    Years to pristine:  ~480 years
  With erosion control:
    Years to pristine:  ~320 years (halved erosion)

Permanent capacity loss (at current substrate state):
  Max recoverable services: 74.4% of pristine
  Annual service value lost permanently: €XXX/yr
  NPV of permanent loss (50yr horizon): €XXX
```

### Updated Prevention Advantage

```
═══════════════════════════════════════════════════
PREVENTION ADVANTAGE (v0.5 — with substrate)
═══════════════════════════════════════════════════

Prevention cost (not cutting):     €XXX/yr foregone revenue
Restoration cost (biological):     €XXX total
Substrate loss (permanent):        €XXX NPV over 50yr
Total restoration + substrate:     €XXX

Prevention advantage:    XX.X× (biological only, as in v0.2)
Prevention advantage:    XX.X× (including substrate loss)

⚠ SUBSTRATE WARNING: 25.7% of soil depth permanently lost.
  Full ecosystem recovery requires ~480 years of soil formation.
  Biological restoration alone recovers at most 74.4% of services.
```

---

## Part 6: Sensitivity — Which Substrate Properties Matter Most

Not all substrate properties are equally important. A sensitivity analysis should reveal:

**For holm oak forest:**
- **Soil depth** is the dominant constraint in shallow Mediterranean soils. A 20% reduction in soil depth produces a larger externality increase than a 20% change in any other parameter. This is because soil loss is effectively irreversible.
- **Water availability** matters at the margins — near the 400 mm/yr threshold for holm oak establishment, small changes in rainfall (e.g., from climate change) could shift the system from "degraded forest" to "no forest possible."
- **Erosion rate unprotected** determines how fast the degradation spiral operates. Higher values = faster irreversibility.

**For Posidonia:**
- **Water clarity (Kd)** is the primary control on habitable area. A change from Kd=0.06 to Kd=0.10 (coastal development, runoff) reduces habitable depth from ~38 m to ~23 m — a ~40% loss of potential habitat area.
- **Matte integrity** determines whether transplantation is possible. Destroyed matte on a large scale means no platform for recolonization.
- **Sediment stability** matters in shallow areas where wave energy can rip out young transplants.

### Implementation

The simulation should automatically compute sensitivity for substrate parameters:

```python
def substrate_sensitivity_analysis(ecosystem, parameter, variation=0.20):
    """Run simulation with ±20% variation on a substrate parameter.
    
    Returns: (externality_at_-20%, externality_at_baseline, externality_at_+20%)
    """
    ...
```

This tells users: "Your externality estimate is most sensitive to soil erosion rate — a 20% increase in erosion produces a 35% increase in total externality. Better erosion data would significantly improve estimate precision."

---

## Preconfigured Substrate Configurations Summary

| Parameter | Oak Valley | Holm Oak | Posidonia | Unit |
|---|---|---|---|---|
| Substrate type | terrestrial_soil | terrestrial_soil | marine_matte | — |
| Soil depth (pristine) | 45 | 30 | N/A | cm |
| Water availability | 800 | 550 | N/A | mm/yr |
| Water clarity (Kd) | N/A | N/A | 0.06 | m⁻¹ |
| Sediment stability | N/A | N/A | 0.85 | 0–1 |
| Erosion unprotected | 15 | 25 | 5 | t/ha/yr or mm/yr |
| Erosion protected | 0.5 | 1.0 | 0.0 | t/ha/yr or mm/yr |
| Formation rate | 0.8 | 0.4 | 1.0 | t/ha/yr or mm/yr |
| Capacity function | linear | threshold | logistic | — |
| Confidence | medium | medium | low-medium | — |

---

## Testing Strategy

### Ecological Plausibility Checks

These tests encode real-world expectations that the model must satisfy:

1. **Substrate-K relationship is monotonic:** More soil → higher K, always. More water clarity → larger habitable area, always. No inversions.

2. **Degradation spiral operates:** Running the same extraction scenario with and without substrate modeling must show that substrate-aware extraction produces *higher* total externality. The difference is the substrate cost.

3. **Holm oak irreversibility threshold:** With threshold capacity function, extracting trees below the soil critical minimum (~8 cm soil depth remaining) must show K dropping to near-zero. This is the "point of no return" — even replanting cannot restore the forest because there's no soil for trees.

4. **Posidonia depth limit responds to clarity:** Increasing Kd from 0.06 to 0.12 (turbidity doubling) must reduce K by roughly 30–50% (habitable depth shrinks from ~38 m to ~19 m, reducing area dramatically in typical Mediterranean shelf geometry).

5. **Erosion rates are physically consistent:**
   - 25 t/ha/yr on bare Mediterranean slope → ~1.9 mm/yr soil loss (at bulk density ~1,300 kg/m³)
   - 30 cm soil completely eroded in ~158 years of continuous bare exposure
   - This is consistent with Mediterranean degradation timescales (centuries for full desertification)

6. **Formation rates are physically consistent:**
   - Holm oak: 0.4 t/ha/yr → ~0.03 mm/yr → 30 cm soil in ~10,000 years from bedrock
   - Posidonia: 1.0 mm/yr matte → 2 m matte in ~2,000 years
   - Both consistent with literature (Monnier 2020: 210 cm in 1,580 yr; Montgomery 2007: soil formation 0.3–1.4 t/ha/yr)

7. **Prevention advantage increases with substrate:**
   - PA(v0.2, holm oak) was ~6× (biological restoration only)
   - PA(v0.5, holm oak) must be >6× (substrate loss adds permanent cost)
   - PA(v0.2, Posidonia) was ~81× 
   - PA(v0.5, Posidonia) must be >>81× (matte loss is millennia-scale)

8. **Restoration ceiling is binding:** After severe extraction with substrate loss, restoration simulation must show that biological recovery plateaus below 100% — the substrate ceiling prevents full recovery.

### Backward Compatibility Tests

9. **No substrate = v0.4 behavior:** All v0.1–v0.4 tests must pass unchanged when no `SubstrateProfile` is configured.

10. **Pristine substrate = unchanged K:** When substrate is at pristine values, `effective_carrying_capacity` must equal `total_units` exactly.

### Edge Cases

11. **Zero soil depth:** K = 0, no extraction possible, total externality = maximum.

12. **Substrate degradation beyond zero:** Soil depth cannot go negative. Erosion stops when substrate is fully depleted.

13. **Substrate recovery beyond pristine:** Formation cannot exceed pristine values. Substrate capped at initial conditions.

14. **Mixed depletion-recovery:** Partial extraction → some substrate loss → replanting → substrate slowly recovers while biological restoration proceeds. The model must handle both directions simultaneously.

---

## Data Model Changes Summary

### New Dataclasses

| Dataclass | Purpose |
|---|---|
| `SubstrateProfile` | Physical substrate properties and rates |
| `SubstrateState` | Current substrate condition and derived capacity |

### Extended Dataclasses

| Dataclass | New Fields |
|---|---|
| `Resource` | `+substrate: SubstrateProfile \| None`, `+substrate_state: SubstrateState \| None`, `+effective_carrying_capacity: int` (property) |
| `SimulationStep` | `+substrate_erosion: float`, `+effective_k: int`, `+k_fraction: float` |
| `RestorationResult` | `+substrate_ceiling: float`, `+substrate_recovery_years: float`, `+prevention_advantage_with_substrate: float` |

### New Report Sections

| Section | Content |
|---|---|
| Substrate Impact | Soil/substrate state, erosion rate, K trajectory |
| Capacity Ceiling | Max recoverable services, permanent loss |
| Updated Prevention Advantage | PA including substrate cost |
| Sensitivity Analysis | Which substrate parameters matter most |

---

## Definition of Done

1. All v0.1/v0.2/v0.3/v0.4 tests pass (backward compatibility)
2. `SubstrateProfile` and `SubstrateState` dataclasses implemented with all three capacity functions
3. `Resource.effective_carrying_capacity` returns derived K when substrate configured, `total_units` otherwise
4. Extraction simulation degrades substrate based on vegetation cover
5. Degradation spiral is observable: substrate-aware simulation produces higher externality than v0.4 for same extraction
6. Holm oak irreversibility threshold works: K drops to near-zero below critical soil depth
7. Posidonia depth limit responds to water clarity changes
8. Erosion and formation rates are physically consistent (tests 5–6)
9. Restoration ceiling is binding: biological recovery cannot exceed `K_current/K_pristine`
10. Prevention advantage increases with substrate modeling for all three cases
11. Report includes substrate impact section
12. Sensitivity analysis runs for substrate parameters
13. All preconfigured profiles (Oak Valley, Holm Oak, Posidonia) produce ecologically plausible results

---

## Key Literature Sources

| Reference | Used For | Confidence |
|---|---|---|
| Montgomery (2007), PNAS | Soil erosion vs. formation rates globally | High |
| ESDAC/JRC RUSLE2015 (Panagos et al. 2015) | European soil erosion modeling, Spain erosion rates | High |
| Sferlazza et al. (2018), iForest 11: 344-351 | Holm oak carbon stocks, root-to-shoot ratios, Sicily | Medium |
| González et al. (2012), Eur J For Res 131 | Soil carbon across 103 Q. ilex stands, Spain | Medium |
| Monnier et al. (2020), Vie et Milieu 70 | Posidonia matte thickness, radiocarbon dating, Corsica | Medium-High |
| Marbà et al. (1996), MEPS 137: 203-213 | Posidonia rhizome growth dynamics, 29 Spanish meadows | High |
| Infantes et al. (2009), Botanica Marina | Wave energy and upper depth limit of Posidonia | Medium |
| Pergent et al. (1995) | Posidonia depth distribution and light requirements | High |
| Duarte (1991) | Seagrass depth limits and light | High |
| ESDAC European Commission | Mediterranean storm erosion (20-40 t/ha per event) | High |
| Gracia & Retana (1996) | Holm oak stand density variability, NE Spain | Medium |
| Puéchabon State Forest data | Holm oak coppice density: ~6,000 stems/ha (~4,000 stools/ha) | Medium |

---

## Open Questions & Known Limitations

### Unit consistency for marine substrates

Terrestrial erosion is naturally measured in t/ha/yr and soil depth in cm. Marine substrate degradation (matte erosion, sediment resuspension) doesn't map cleanly to these units. The current spec uses mm/yr for both matte accretion and erosion, but this conflates several distinct processes (surface oxidation, mechanical erosion, compaction). A future version may need separate rates for different degradation mechanisms.

### Spatial heterogeneity

Real substrates are not uniform. A hillside has variable soil depth. A meadow spans a depth gradient. The current model assumes a single representative value for each substrate property. This is adequate for ecosystem-level externality estimation but cannot capture patch-level dynamics. Spatial modeling is deferred to future versions.

### Climate change interaction

v0.5 does not model how climate change affects substrate. In reality:
- Decreased rainfall → reduced soil formation, increased erosion during intense events
- Sea level rise → shifts Posidonia depth distribution
- Ocean warming → may affect matte decomposition rates
- Increased storm intensity → accelerated erosion events

These are real and important but beyond v0.5 scope. The substrate framework established here provides the scaffolding to model them later.

### Holm oak density: stems vs. stools vs. trees

The literature reports very different density figures depending on what's counted:
- **Stems per hectare:** ~1,500–6,000 (coppice stands have many stems per stool)
- **Stools (genetic individuals) per hectare:** ~400–4,000 (high variability by site)
- **"Trees" (mature canopy individuals):** ~40 (dehesa) to ~800 (dense mature forest)

For Gaia's purposes, the Costa Brava holm oak case uses 1,800 as "management units" — roughly equivalent to stools in a mature coppice that has been abandoned for 40+ years (Sferlazza 2018: ~1,800 stems/ha in 40-year coppice). The substrate model's K = 1,800 represents the carrying capacity for this density class, not for all possible management regimes. This should be documented clearly in the case configuration.

### Sensitivity analysis as automatic vs. manual

The spec proposes automatic sensitivity analysis for substrate parameters. This requires running the full simulation 2N additional times (±variation for each of N parameters). For current case sizes this is trivial, but if simulation complexity grows (v0.3 cascade propagation, v0.4 succession curves), it could become expensive. Consider making sensitivity analysis an explicit opt-in command rather than automatic.
