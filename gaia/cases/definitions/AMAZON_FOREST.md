# Gaia v0.7+ Amazon Rainforest Case — Research Compendium

## 1. Case Overview

**Ecosystem:** Central Amazon old-growth lowland rainforest (terra firme)
**Reference area:** 10,000 hectares (~100 km²) of intact lowland forest
**Location archetype:** Central Amazon basin, south of Manaus (Amazonas state, Brazil)
**Biome:** Tropical moist broadleaf forest on Oxisol/Ferralsol substrate
**Extraction scenario:** Selective logging + progressive deforestation for cattle ranching

This case represents the world's highest-productivity terrestrial ecosystem on one of its most nutrient-depleted soils — a paradox that makes the Amazon uniquely interesting for Gaia's substrate-dependent modeling. The forest's survival depends entirely on rapid nutrient recycling through mycorrhizal networks; destroy the biological layer and the substrate cannot support recovery.

---

## 2. Productivity & Carbon Parameters

### Net Primary Productivity (NPP)

| Parameter | Value | Source |
|---|---|---|
| GPP (old-growth, Central Amazon) | 28.5 Mg C ha⁻¹ yr⁻¹ | ScienceDirect 2024 (eddy covariance) |
| NPP (total) | ~10-12 Mg C ha⁻¹ yr⁻¹ | Malhi 2012 (biometric) |
| Carbon Use Efficiency (CUE) | 0.30-0.40 | Malhi 2012 (tropical forest range) |
| NPP allocation: canopy | 34 ± 6% | PMC/Phil Trans R Soc B |
| NPP allocation: wood | 39 ± 10% | PMC/Phil Trans R Soc B |
| NPP allocation: fine roots | 27 ± 11% | PMC/Phil Trans R Soc B |

### Carbon Stocks

| Parameter | Value | Source |
|---|---|---|
| Aboveground biomass (AGB) | 174 Mg ha⁻¹ (range 143-356) | Saatchi 2007; Wikipedia; various |
| AGB carbon density | 83.5 Mg C ha⁻¹ | Planet/Forest Carbon Diligence |
| Total biomass (above + below) | 173 ± 12 Mg C ha⁻¹ | Phil Trans R Soc B (227 plots) |
| Aboveground carbon (per ha) | ~180 t C | Various |
| Root system carbon (per ha) | ~40 t C | Various |
| Net carbon accumulation (old-growth, historical) | 0.62 ± 0.37 t C ha⁻¹ yr⁻¹ | Wikipedia (1975-1996 data) |
| Total Amazon carbon stock | ~100 billion t C (vegetation) | Various |

### For 10,000 ha reference area

| Parameter | Calculation | Value |
|---|---|---|
| Standing carbon stock | 173 × 10,000 | 1,730,000 Mg C |
| Annual NPP | 11 × 10,000 | 110,000 Mg C yr⁻¹ |
| CO₂ equivalent of stock | 1,730,000 × 3.67 | ~6,350,000 t CO₂ |

**Key insight:** Amazon NPP (~11 Mg C ha⁻¹ yr⁻¹) is roughly 6-7× higher than Mediterranean holm oak (~1.7 Mg C ha⁻¹ yr⁻¹), making the carbon anchor dramatically larger.

---

## 3. Trophic Structure & Interaction Matrix

### Agent Design (11 agents)

The Amazon case requires more agents than Mediterranean cases to capture the trophic complexity. We propose 11 agents organized by functional role:

| Agent | Trophic Level | Role | Gaia Function |
|---|---|---|---|
| **Canopy Trees** | Producer | Emergent + canopy layer (400+ species/ha) | Primary biomass, carbon stock, rainfall recycling |
| **Understory** | Producer | Sub-canopy trees, palms, ferns, epiphytes | Shade-tolerant reproduction, microclimate regulation |
| **Mycorrhizal Fungi** | Decomposer/Mutualist | Arbuscular mycorrhizae (AMF) + ectomycorrhizae | Nutrient cycling, phosphorus mobilization — KEYSTONE |
| **Soil Decomposers** | Decomposer | Termites, fungi, bacteria, dung beetles | Organic matter breakdown, nutrient return |
| **Pollinators** | Mutualist | Bees, butterflies, hummingbirds, bats | Reproduction for 90%+ of canopy species |
| **Seed Dispersers** | Primary Consumer / Mutualist | Monkeys (spider, howler), toucans, agoutis, tapirs | Forest regeneration, genetic connectivity |
| **Herbivores** | Primary Consumer | Capybaras, sloths, leafcutter ants, insects | Energy transfer, population dynamics |
| **Mesopredators** | Secondary Consumer | Snakes (boa, anaconda), caimans, ocelots, anteaters | Mid-trophic regulation |
| **Apex Predators** | Tertiary Consumer | Jaguars, harpy eagles | Top-down population control — KEYSTONE |
| **Aquatic System** | Mixed | River fish (3,000+ species), river dolphins, aquatic plants | Nutrient transport, fisheries service |
| **Epiphytes & Bromeliads** | Producer / Habitat | Orchids, bromeliads, lichens (~25,000 species) | Water retention, microhabitat creation |

### Interaction Matrix (edge strengths)

This encodes "how much agent j depends on agent i" — the demand structure for v0.7 pricing.

```
                  CnTr  Undr  Myco  SDec  Poll  Seed  Herb  Meso  Apex  Aqua  Epip
Canopy Trees      0.00  0.30  0.15  0.20  0.05  0.10  0.25  0.05  0.02  0.10  0.35
Understory        0.25  0.00  0.10  0.15  0.05  0.08  0.15  0.03  0.01  0.05  0.20
Mycorrhizal       0.40  0.25  0.00  0.15  0.00  0.00  0.00  0.00  0.00  0.00  0.05
Soil Decomposers  0.15  0.10  0.20  0.00  0.00  0.00  0.05  0.00  0.00  0.05  0.05
Pollinators       0.30  0.15  0.00  0.00  0.00  0.05  0.00  0.05  0.00  0.00  0.10
Seed Dispersers   0.20  0.10  0.00  0.00  0.00  0.00  0.00  0.10  0.05  0.05  0.00
Herbivores        0.10  0.05  0.00  0.00  0.00  0.00  0.00  0.30  0.35  0.10  0.00
Mesopredators     0.03  0.02  0.00  0.00  0.00  0.00  0.00  0.00  0.30  0.10  0.00
Apex Predators    0.01  0.01  0.00  0.00  0.00  0.00  0.00  0.00  0.00  0.05  0.00
Aquatic System    0.15  0.05  0.00  0.05  0.00  0.00  0.05  0.10  0.05  0.00  0.00
Epiphytes         0.20  0.15  0.05  0.05  0.03  0.00  0.00  0.00  0.00  0.00  0.00
```

**Reading:** Row = dependency source, Column = dependent agent. "Mycorrhizal → Canopy Trees = 0.40" means canopy trees have 40% dependency on mycorrhizal fungi.

**Keystone predictions:** Under v0.7 endogenous pricing, mycorrhizal fungi should emerge as the most expensive agent (highest network centrality as the nutrient gateway), followed by canopy trees (highest demand from all consumers). Apex predators should be cheapest (few dependents, small population).

---

## 4. Substrate Model (v0.5 integration)

### Soil Type: Tropical Oxisol (Ferralsol)

The Amazon presents a **unique substrate paradox**: the world's most productive terrestrial ecosystem grows on one of the world's most nutrient-depleted soils.

| Parameter | Value | Source |
|---|---|---|
| Soil order | Oxisol (USDA) / Ferralsol (FAO) | Frontiers/Holzman 2008 |
| Coverage | >50% of tropical forests on Oxisols/Ultisols | Frontiers/Holzman 2008 |
| pH | Acidic (4.0-5.5) | Various |
| Available phosphorus | Extremely low (P-limited) | Nature 2022 (AFEX experiment) |
| Dominant minerals | Aluminum oxide, iron oxide (laterite) | Mongabay/worldrainforests |
| Organic matter layer | Thin but critical (~20 cm) | Various |
| Nutrient source | 95%+ from decomposition recycling, NOT rock weathering | ATTO project |
| Soil formation rate | Extremely slow (tropical weathering exhausted) | Implied by age |
| Soil depth to laterite | Variable, often <1m to hardpan | Various |

### Substrate Capacity Function: THRESHOLD type

The Amazon substrate has a critical property: nearly all nutrients are held in the biological layer, not the mineral soil. Once the organic recycling layer is destroyed, the laterite substrate cannot support forest regeneration.

**Proposed function:** Threshold with steep cliff

```
capacity(substrate_health) = {
    1.0                                          if health > 0.25  (organic layer intact)
    1.0 × ((health - 0.05) / 0.20)²             if 0.05 < health ≤ 0.25  (quadratic collapse)
    0.0                                          if health ≤ 0.05  (laterite exposed, irreversible)
}
```

**Rationale:** Unlike Mediterranean soils that degrade gradually, Amazon Oxisols have a binary quality — forest or wasteland. The thin organic recycling layer either functions or it doesn't. Once exposed laterite bakes in tropical sun, it can form hardpan (laterite crust) that is essentially permanent.

### Erosion Parameters

| Parameter | Value | Source |
|---|---|---|
| Intact forest erosion | 0.015 Mg ha⁻¹ yr⁻¹ (1960 baseline) | ScienceDirect 2023 (RUSLE) |
| Current average (with deforestation) | 0.117 Mg ha⁻¹ yr⁻¹ | ScienceDirect 2023 |
| Erosion increase from deforestation | 600%+ (basin average) | ScienceDirect 2023 |
| Deforested slope erosion | 10× intact forest | Various/wifitalents |
| Tropical cultivated slope | 90 t ha⁻¹ yr⁻¹ (Ivory Coast analog) | worldrainforests.com |
| Bare tropical slope | 138 t ha⁻¹ yr⁻¹ (Ivory Coast analog) | worldrainforests.com |
| **Destruction:recovery ratio** | **>3000:1** (90 vs 0.015 t/ha/yr for cultivated vs intact) | Calculated |

**Key insight for Gaia:** The Amazon destruction:recovery ratio (~3000:1 for cultivated land) dwarfs even the Mediterranean (62:1). This is the ultimate substrate asymmetry — and it should produce the most extreme prevention advantage ratio in any Gaia case.

### Soil Formation

| Parameter | Value | Notes |
|---|---|---|
| Mineral soil formation | Negligible — Oxisol is fully weathered | No fresh mineral input |
| Organic layer rebuilding | 2-3 years for initial vegetation cover | Mongabay (restoration data) |
| Functional soil recovery | 6-10 years (with forest regrowth) | Various restoration studies |
| Full organic layer recovery | 20-40 years | Implied by biomass recovery timelines |

---

## 5. Water Cycle Parameters (Critical for Amazon)

The Amazon is unique among our cases because water cycling IS a primary ecosystem service, not just a secondary effect.

| Parameter | Value | Source |
|---|---|---|
| Average annual rainfall | 2,200 mm yr⁻¹ | ScienceDirect (Espinoza 2009) |
| Evapotranspiration return | 54% of precipitation | ScienceDirect (Malhi 2002) |
| Moisture recycling rate | 50-80% stays in ecosystem | coolgeography.co.uk |
| Water molecule recycling | Up to 7 times before leaving basin | Brown University |
| Transpiration contribution to dry-season rain | Up to 70% | ResearchGate/Staal |
| "Flying rivers" moisture volume | Greater than Amazon River discharge | Yale E360 |
| Amazon discharge to Atlantic | 175,000 m³/s (1/5 of global) | coolgeography.co.uk |
| Deforestation ET reduction | 15% in southern Amazon already | wifitalents |
| Dry season lengthening | 4-5 weeks since 1979 (eastern/southern) | WEF |

### Water Cycling as Ecosystem Service

The Amazon's "flying rivers" concept is critical: the forest transpires so much water that it generates its own rainfall. This creates a **positive feedback loop** that Gaia should model:

- Intact forest → high ET → moisture recycling → rainfall → forest persistence
- Deforestation → reduced ET → less recycling → drought → more tree death → further ET reduction

**This is the degradation spiral on steroids.** Unlike Mediterranean cases where substrate degradation is the primary feedback, in the Amazon the atmospheric moisture feedback amplifies substrate degradation.

### Water Anchor for v0.7 Pricing

| Service | Value | Calculation |
|---|---|---|
| Rainfall recycling (10,000 ha) | ~€2M/yr | Based on agricultural losses of $9/ha/yr for 220,000 ha downwind area affected |
| Freshwater regulation | ~€500k/yr | Water treatment cost avoidance |

---

## 6. Deforestation & Degradation Data

### Current Status (2024-2025)

| Parameter | Value | Source |
|---|---|---|
| Total Amazon forest lost | ~17% deforested + 17% degraded | WEF / multiple |
| Tipping point threshold | 20-25% deforestation | Lovejoy & Nobre 2018 |
| Brazilian Amazon loss (2024) | 954,126 ha (deforestation) | MAAP #229 |
| Fire impact (2024) | 2.8 million ha (record) | MAAP #229 |
| Combined loss (2024) | 4.5 million ha (record) | MAAP #229 |
| Deforestation trend (2022-2024) | Roughly halved under Lula | sustainabilitybynumbers |
| Global warming threshold for accelerated decline | 2.3°C | PNAS 2025 |
| Fire-driven forest loss share | 60% of 2024 loss | Mongabay |
| Primary driver | Cattle ranching (80%) | Various |

### Degradation Beyond Clear-Cutting

A major finding from the literature: **degradation (fire, edge effects, logging, drought) now equals or exceeds deforestation in carbon emissions.** Lapola et al. (Science 2023) found 38% of remaining Amazon forests show some form of degradation, emitting up to 0.2 Pg C yr⁻¹.

For Gaia modeling, this means extraction should include not just "tree removal" but also fire and edge-effect degradation.

---

## 7. Recovery Timelines (Restoration Data)

| Recovery Metric | Timeline | Source |
|---|---|---|
| Initial vegetation cover | 2-3 years | Mongabay |
| Soil function (basic) | 2-3 years | Mongabay (expert quote) |
| Carbon capture to 80% capacity | 20 years | Mongabay / Peugeot-ONF project |
| 20-year biomass recovery (average) | 122 Mg ha⁻¹ | PubMed (Poorter 2016) |
| 20-year carbon uptake rate | 3.05 Mg C ha⁻¹ yr⁻¹ | PubMed (Poorter 2016) |
| Secondary forest vs old-growth uptake | 11× faster in secondary | PubMed (Poorter 2016) |
| Species diversity recovery | 25-60 years | EDF / Science study |
| 90% biomass recovery (median) | 66 years | PubMed (Poorter 2016) |
| Full old-growth equivalence | 100+ years | EDF / various |
| Secondary forest carbon offset of deforestation | <10% | Eos/Lancaster 2022 |
| Regional variation: west Amazon regrowth rate | 3.0 ± 1.0 Mg C ha⁻¹ yr⁻¹ | Nature Comms 2021 |
| Regional variation: east Amazon regrowth rate | 1.3 ± 0.3 Mg C ha⁻¹ yr⁻¹ | Nature Comms 2021 |

### 20-year Recovery Benchmarks (for Gaia validation)

After 20 years of regeneration, successful sites should achieve (Nature/Comms Earth 2024):
- Basal area: ≥14 m² ha⁻¹
- Tree species: ≥34 per 100 individuals
- Aboveground biomass: ≥123 Mg ha⁻¹

### Disturbance Effects on Recovery

Fire and repeated deforestation reduce regrowth rates by 8-55% (Nature Comms 2021). This maps directly to Gaia's substrate degradation reducing carrying capacity.

---

## 8. Economic Valuation & Anchor Prices

### Ecosystem Service Values (Meta-Analysis)

| Service | Value (USD/ha/yr) | Source |
|---|---|---|
| Total ecosystem services (mean) | ~$410 | Brouwer et al. 2022 (PLOS ONE meta-analysis) |
| Spatially explicit (high-value areas, 12% of forest) | $57 - $737 | Nature Sustainability 2018 |
| Provisioning services (logging, NTFP) | $20-50 | ADS/Strassburg review |
| Rainfall impact of loss | $10-20 | ADS/Strassburg review |
| Carbon (capitalized, at $30/t CO₂) | ~$14,000/ha | ADS/Strassburg review |
| REDD+ reference price | $10/t CO₂ | CPI/PUC-RIO 2025 |
| LEAF Coalition credit (Pará deal) | $15/credit (~$180M for 12M credits) | Trellis/Amazon 2025 |
| Agroforestry alternative | $300-700/ha/yr | WEF |

### Anchor Points for v0.7 Endogenous Pricing

For the 10,000 ha reference area:

| Anchor | Annual Value | Calculation | Confidence |
|---|---|---|---|
| **Carbon sequestration** | €880,000/yr | 11 Mg C/ha × 10,000 ha × 3.67 → 403,700 t CO₂ × €80/t (EU ETS) × 0.027 (net uptake fraction) | HIGH |
| **Carbon stock protection** | €5,080,000/yr | 6.35M t CO₂ stock × €80/t ÷ 100 yr amortized | HIGH |
| **Water cycling / rainfall** | €1,500,000/yr | Rainfall recycling service: $15-20/ha/yr × 10,000 ha + downwind agricultural value | MEDIUM |
| **Biodiversity / habitat** | €410,000/yr | $410/ha/yr meta-analysis mean (conservative, only local values) | MEDIUM |
| **REDD+ avoided deforestation** | €540,000/yr | 54 t CO₂/ha × 10,000 ha × $10/t CO₂ × 1% annual deforestation risk | MEDIUM |

**Total annual ecosystem service value: ~€8.4M/yr for 10,000 ha** (~€840/ha/yr)

**Note on carbon anchor:** The Amazon is unusual because **stock protection** dominates over **annual sequestration**. Each hectare stores ~635 t CO₂. At EU ETS prices (€80/t), that's €50,800/ha in stored carbon value. The annual sequestration flow is much smaller because old-growth forests are near carbon equilibrium (net uptake only ~0.62 t C/ha/yr historically). The value comes from NOT releasing the stock.

This creates an interesting pricing dynamic for v0.7: the "price of destruction" is front-loaded (releasing stock), while the "price of prevention" accumulates (protecting ongoing services).

---

## 9. Gaia Model Configuration

### EcosystemConfig

```python
AmazonRainforest = EcosystemConfig(
    name="Central Amazon Old-Growth Lowland Forest",
    area_hectares=10000,
    initial_population=400_000,  # ~400 trees/ha is typical for Amazon
    carrying_capacity=None,  # DERIVED from substrate in v0.5+
    threshold=0.20,  # Amazon tipping point (Lovejoy & Nobre)
    monetary_rate=840.0,  # €/ha/yr baseline (from meta-analysis)
    # v0.5 substrate
    substrate_type="tropical_oxisol",
    substrate_capacity_function="threshold",
    substrate_threshold=0.25,
    substrate_max_capacity=400_000,
    # v0.7 pricing
    pricing_config=PricingConfig(
        anchors=[
            AnchorPoint("canopy_trees", 5_080_000, "carbon_stock_protection", "HIGH"),
            AnchorPoint("canopy_trees", 880_000, "carbon_sequestration", "HIGH"),
            AnchorPoint("canopy_trees", 1_500_000, "water_cycling", "MEDIUM"),
            AnchorPoint("aquatic_system", 200_000, "fisheries", "MEDIUM"),
            AnchorPoint("pollinators", 410_000, "biodiversity_habitat", "MEDIUM"),
        ],
        scarcity_functions={
            "canopy_trees": ScarcityFunction("smooth", alpha=1.0),
            "understory": ScarcityFunction("smooth", alpha=1.0),
            "mycorrhizal_fungi": ScarcityFunction("smooth", alpha=2.5),  # HIGHEST: non-substitutable
            "soil_decomposers": ScarcityFunction("smooth", alpha=2.0),
            "pollinators": ScarcityFunction("smooth", alpha=2.0),
            "seed_dispersers": ScarcityFunction("smooth", alpha=1.5),
            "herbivores": ScarcityFunction("smooth", alpha=1.0),
            "mesopredators": ScarcityFunction("smooth", alpha=1.0),
            "apex_predators": ScarcityFunction("smooth", alpha=1.0),
            "aquatic_system": ScarcityFunction("threshold", threshold=0.30),
            "epiphytes": ScarcityFunction("smooth", alpha=1.5),
        }
    )
)
```

### Scarcity Rationale

- **Mycorrhizal fungi α=2.5** (highest): In the Amazon, AMF are THE bottleneck. 60% of the basin sits on P-depleted Oxisols where phosphorus limitation is the primary constraint on productivity (Nature 2022, AFEX experiment). Without mycorrhizae, the forest literally cannot access the nutrients it needs. There is NO artificial substitute.

- **Soil decomposers α=2.0**: Tropical nutrient cycling depends on rapid decomposition. Without decomposers, the thin organic layer cannot be recycled. Termites alone process ~30% of dead wood.

- **Pollinators α=2.0**: >90% of tropical tree species require animal pollination. Loss of pollinators would prevent canopy reproduction — ecosystem collapse within one tree generation.

- **Aquatic system threshold=0.30**: Amazon rivers have documented collapse thresholds. Below certain flow levels, fish spawning fails, dolphin populations crash, and the aquatic food web collapses. This mirrors the "flying rivers" threshold.

---

## 10. Ecological Plausibility Tests

### Expected Model Behaviors

1. **Mycorrhizal fungi emerge as most expensive agent** — highest network centrality (all producers depend on them), highest scarcity alpha, non-substitutable
2. **Canopy trees are second most expensive** — largest carbon anchor, most demanded by consumers
3. **Apex predators are cheapest** — few dependents, low network centrality
4. **Degradation spiral is faster than Mediterranean cases** — due to dual feedback (substrate + atmospheric moisture)
5. **Prevention advantage ratio should exceed Mediterranean cases** — stock protection value + moisture recycling feedback
6. **At 20% extraction, tipping point dynamics should emerge** — crossing the Lovejoy-Nobre threshold triggers nonlinear price increases
7. **Aquatic system shows threshold pricing** — below 30% health, scarcity multiplier spikes
8. **Recovery is faster in absolute terms but slower relative to destruction** — 3 Mg C/ha/yr recovery vs 173 Mg C/ha stock = 58 years to full recovery vs instantaneous destruction

### Numerical Checks

| Test | Expected Range | Rationale |
|---|---|---|
| Total externality at 50% extraction | €50M - €200M | Higher than any Mediterranean case due to carbon stock |
| Prevention advantage at 30% extraction | >100× | Extreme asymmetry: stock release + moisture feedback |
| Mycorrhizal price / Apex predator price | >20:1 | Network centrality ratio |
| Price increase from pristine → 25% degraded | 3-5× | Approaching tipping point |
| Price increase from 25% → 30% degraded | >10× | Past tipping point — nonlinear scarcity |

---

## 11. Comparison with Existing Cases

| Feature | Oak Valley | Costa Brava Holm Oak | Costa Brava Posidonia | **Amazon** |
|---|---|---|---|---|
| Area (ha) | 100 | 1,000 | 1,000 | **10,000** |
| Population | 10,000 trees | 1,800 trees | 1,000 ha meadow | **400,000 trees** |
| NPP (Mg C/ha/yr) | ~1.7 | ~1.7 | ~3.0 | **~11** |
| Carbon stock (t CO₂/ha) | ~200 | ~200 | ~400 | **~635** |
| Substrate type | Terrestrial soil | Terrestrial soil | Marine matte | **Tropical Oxisol** |
| Capacity function | Linear | Linear | Logistic | **Threshold** |
| Destruction:recovery | 62:1 | 62:1 | ~1000:1 | **~3000:1** |
| Tipping point (%) | 30% | 25% | 20% | **20%** |
| Key interaction | Mycorrhizal | Mycorrhizal | Posidonia meadow | **Mycorrhizal + Water** |
| Agents | 4-6 | 6-8 | 5-7 | **11** |
| Annual service value (€/ha) | ~€100 | ~€60 | ~€2,500 | **~€840** |
| Unique dynamics | Basic | Succession | Marine substrate | **Moisture feedback, tipping point** |

---

## 12. Key Scientific References

### Productivity & Carbon
- ScienceDirect 2024: "Ecosystem carbon fluxes are tree size-dependent in an Amazonian old-growth forest" — GPP = 28.46 MgC ha⁻² yr⁻¹
- Malhi 2012: "The productivity, metabolism and carbon cycle of tropical forest vegetation" — CUE 0.30-0.40
- Phil Trans R Soc B (PMC/3179639): NPP allocation in tropical forests — 34/39/27% canopy/wood/roots
- Nature Comms 2024: "Contrasting carbon cycle along tropical forest aridity gradients" — Amazon vs West Africa

### Substrate & Nutrients
- Nature 2022 (Cunha et al.): "Direct evidence for phosphorus limitation on Amazon forest productivity" — AFEX experiment
- Frontiers 2021: "Tradeoffs and Synergies in Tropical Forest Root Traits" — >50% on Oxisols/Ultisols
- ATTO project (2024): "Highly productive ecosystems on nutrient-depleted soils" — P-limitation confirmed
- Scientific Reports 2017: "Nutrient-cycling mechanisms other than direct absorption from soil"

### Water Cycle
- MAAP #232 (2025): "The Amazon Tipping Point – Importance of Flying Rivers"
- ScienceDirect 2024: "Evapotranspiration in the Amazon Basin" — 54% ET return
- Nature 2025 (Qin et al.): "Impact of Amazonian deforestation on precipitation reverses between seasons"
- Yale E360: "Rivers in the Sky" — vegetation recycles 48 mi³/day, Amazon = 10%

### Deforestation & Tipping Point
- Nature 2024 (Flores et al.): "Critical transitions in the Amazon forest system" — 10-47% exposed by 2050
- PNAS 2025: "Amazon forest faces severe decline" — 2.3°C threshold
- Science 2023 (Lapola et al.): "The drivers and impacts of Amazon forest degradation" — 38% degraded
- MAAP #229 (2025): 2024 deforestation data — 954k ha deforested + 2.8M ha fire impact

### Recovery
- PubMed/Poorter 2016: "Biomass resilience of Neotropical secondary forests" — median 66 yr to 90%
- Nature Comms 2021: Secondary forest carbon sink — 3.0 vs 1.3 Mg C/ha/yr (west vs east)
- Comms Earth Environ 2024: Recovery benchmarks — 14 m²/ha basal area at 20 years

### Economic Valuation
- PLOS ONE 2022 (Brouwer et al.): Meta-analysis — mean $410/ha/yr ecosystem services
- Nature Sustainability 2018: Spatially explicit valuation — $57-737/ha/yr
- CPI/PUC-RIO 2025: JREDD+ reference — $10/t CO₂, 54 t CO₂/ha stock

### Soil Erosion
- ScienceDirect 2023: RUSLE analysis — 600% erosion increase over 60 years, 0.015→0.117 Mg/ha/yr
- worldrainforests.com: Tropical erosion comparison — forested 0.03 vs cultivated 90 t/ha/yr

---

## 13. Open Questions for Implementation

1. **Moisture feedback mechanism:** Should Gaia model the atmospheric moisture recycling explicitly, or can it be captured as an amplification factor on the degradation spiral? Recommend: amplification factor (α_moisture = 1.5) on degradation rate when forest health drops below 80%.

2. **Fire as extraction mode:** Amazon degradation is driven as much by fire as by logging. Should fire be a separate extraction type with different substrate impact? Recommend: model as "degradation extraction" with substrate damage multiplier of 0.7 (less than clear-cut but still significant).

3. **Tipping point dynamics:** The 20-25% threshold creates a sharp nonlinearity. Should this be modeled as a separate mechanism or can the threshold scarcity function capture it? Recommend: threshold scarcity function on canopy trees with additional "cascade multiplier" when total health < 0.25.

4. **Scale considerations:** 10,000 ha is tiny relative to the Amazon basin (420M ha). The flying rivers effect operates at basin scale. For the reference area, we should note that our externality calculations are conservative because they don't capture the full cascading effects on downwind regions.

5. **Carbon stock vs flow:** Unlike Mediterranean cases where annual service flow dominates, the Amazon case is dominated by the stored carbon stock. The v0.7 pricing system should handle this via the carbon stock protection anchor, but we should verify the NPV calculations handle one-time stock release correctly.