# Amazon Rainforest Parameters: Peer-Reviewed Literature Review

> **Draft — citations not yet verified; see TOP_PRIORITIES_REPORT.md §S4.**

Compiled: 2026-03-23
Purpose: Scientific validation of Gaia Amazon case parameters against published literature.

---

## 1. Carbon Stocks (Aboveground + Belowground Biomass)

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Total biomass carbon (above + below) | 173 +/- 12 Mg C/ha | Phil Trans R Soc B (227 plots, Central Amazon) | HIGH |
| Aboveground live biomass (AGB) | 174 Mg/ha (range 143-356) | Saatchi et al. 2007, Global Change Biology | HIGH |
| AGB carbon density | 83.5 Mg C/ha | Planet/Forest Carbon Diligence (remote sensing) | HIGH |
| AGB range (seasonal/transitional forest, basin edges) | 100-200 Mg/ha | Saatchi et al. 2007 | HIGH |
| AGB range (western Amazonia lowlands) | 150-300 Mg/ha | Saatchi et al. 2007 | HIGH |
| Benchmark tropical carbon map (pan-tropical) | Spatially explicit at 1 km | Saatchi et al. 2011, PNAS | HIGH |
| Total Amazon basin carbon | ~100 billion t C (vegetation) | Multiple sources | MEDIUM |

### Key Studies

**Saatchi et al. 2011 (PNAS):** "Benchmark map of forest carbon stocks in tropical regions across three continents." Used 4,079 in situ inventory plots + satellite LiDAR + optical/microwave imagery at 1 km resolution. Most widely cited benchmark for tropical forest carbon.

**Saatchi et al. 2007 (Global Change Biology):** "Distribution of aboveground live biomass in the Amazon basin." Average forest biomass of 177 Mg C/ha across the basin.

**Avitabile et al. 2016 (Global Change Biology):** Integrated pan-tropical biomass map combining multiple reference datasets. Frequently cross-validated against Saatchi maps.

### Current Gaia Value Assessment

**Gaia uses: 173 Mg C/ha total biomass (above + below).** This aligns well with the Phil Trans R Soc B 227-plot estimate of 173 +/- 12 Mg C/ha. The value is DEFENSIBLE and well within the range of published estimates. No change recommended.

---

## 2. Tree Density (stems/ha, DBH >= 10 cm)

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Amazon-wide range (1-degree grid cells) | 400-750 trees/ha | Amazon Tree Diversity Network (ATDN) | HIGH |
| Full observed range | 250-850 trees/ha | ATDN, 2,046 plots | HIGH |
| Central Amazon terra firme (specific study) | 613 stems/ha (3 ha sample) | de Oliveira & Mori 1999, Biodiversity & Conservation | HIGH |
| Western vs Eastern Amazon difference | Western ~150 stems/ha denser | ATDN spatial model | MEDIUM |
| Typical lowland terra firme | ~400-600 stems/ha | RAINFOR network consensus | HIGH |

### Key Studies

**ter Steege et al. (ATDN):** "A spatial model of tree alpha-diversity and tree density for the Amazon." Published map of tree density across Amazonia showing geographic gradients.

**de Oliveira & Mori 1999:** "A Central Amazonian terra firme forest. I. High tree species richness on poor soils." Sampled 1,916 trees >= 10 cm DBH across 3 hectares, yielding ~613 stems/ha.

**RAINFOR Network:** 188 plots averaging 1.2 ha each, providing long-term inventory data across the Amazon basin.

### Current Gaia Value Assessment

**Gaia uses: 400 trees/ha (400,000 trees / 10,000 ha = 40 trees/ha).** WAIT -- the code comment says "~40 trees/ha x 10,000 ha" in the docstring for build_amazon_ecosystem, but the literature consistently shows 400-600 trees/ha for terra firme Amazon (DBH >= 10 cm). This is a factor of 10 discrepancy.

**IMPORTANT NOTE:** The 400,000 total units for 10,000 ha yields only 40 trees/ha, which is an order of magnitude lower than field inventory data (400-600 trees/ha). If trees are meant to represent actual stems >= 10 cm DBH, the correct value would be ~4,000,000-6,000,000 trees for 10,000 ha. However, this may be an intentional modeling abstraction where each "tree unit" represents a cluster of ~10 actual trees, which is a legitimate simplification. The per-tree carbon values (1.587 t CO2/tree) would need to be interpreted accordingly. The AMAZON_FOREST.md doc confirms the calculation at line 112: "173 Mg C/ha total biomass, ~400 trees/ha" -- this suggests the code originally intended 400 trees/ha but the 10,000 ha scaling was applied differently. The total_trees=400,000 with 10,000 ha yields 40/ha, not 400/ha. **This should be flagged for review.**

---

## 3. Amazon Tipping Point (Deforestation Threshold)

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Deforestation tipping point | 20-25% | Lovejoy & Nobre 2018, Science Advances | HIGH |
| Climate tipping element threshold | Global warming > 1.5 C | Armstrong McKay et al. 2022, Science | HIGH |
| Accelerated decline temperature threshold | > 2.3 C warming | PNAS 2025 | HIGH |
| Current deforestation | ~17% cleared | Multiple sources (2024-2025) | HIGH |
| Current degradation (fire, edge, logging) | ~17% additional degraded | Lapola et al. 2023, Science | HIGH |
| Combined stress (deforestation + degradation) | ~34% of original forest | Multiple sources | HIGH |
| Time to tipping (if trends continue) | < 30 years | Staal et al. 2020 | MEDIUM |

### Key Studies

**Lovejoy & Nobre 2018 (Science Advances):** "Amazon Tipping Point." Estimated 20-25% deforestation threshold considering synergistic effects of climate change, drought, and wildfire. This revised earlier estimates (Nepstad et al.) downward from ~40%, recognizing that climate change + fire create compounding effects.

**Staal et al. 2020 (Environmental Research Letters):** "Feedback between drought and deforestation in the Amazon." Modeled the moisture recycling feedback loop showing catastrophic tipping could occur within 30 years. Supported the 20-25% range.

**Armstrong McKay et al. 2022 (Science):** "Exceeding 1.5 C global warming could trigger multiple climate tipping points." Identified the Amazon as a "global core tipping element." The Amazon tipping point interacts with other Earth system tipping elements.

**Flores et al. 2024 (Nature):** "Critical transitions in the Amazon forest system." Found 10-47% of Amazon forest exposed to potential critical transition by 2050.

### Current Gaia Value Assessment

**Gaia uses: safe_threshold_ratio = 0.20 (20%).** This is at the lower bound of the Lovejoy-Nobre range (20-25%). Given that synergistic effects (fire, climate warming, degradation) push the effective threshold lower, 20% is a defensible and appropriately conservative choice. No change recommended.

---

## 4. Soil Erosion Rates

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Intact Amazon forest (1960 baseline, RUSLE) | 0.015 t/ha/yr | ScienceDirect 2023 (RUSLE, 60-year analysis) | HIGH |
| Current basin average (with deforestation) | 0.117 t/ha/yr | ScienceDirect 2023 | HIGH |
| Erosion increase from deforestation | > 600% (basin average) | ScienceDirect 2023 | HIGH |
| Tropical forested slope (Ivory Coast) | 0.03 t/ha/yr | worldrainforests.com (field measurement) | MEDIUM |
| Tropical cultivated slope (Ivory Coast) | 90 t/ha/yr | worldrainforests.com (field measurement) | MEDIUM |
| Bare tropical slope (Ivory Coast) | 138 t/ha/yr | worldrainforests.com (field measurement) | MEDIUM |
| Global cropland vs forest erosion ratio | 77x higher in croplands | Borrelli et al. 2017, Nature Comms | HIGH |
| Global forest average erosion | 0.16 Mg/ha/yr | Borrelli et al. 2017 | HIGH |
| Peruvian Amazon sub-basin (cultivated) | 3.87-4.55 t/ha/yr | MDPI 2024 (RUSLE, Neshuya basin) | MEDIUM |
| Deforestation erosion increase (meta-analysis) | +47% | Meta-analysis of 21st century studies | HIGH |

### Key Studies

**ScienceDirect 2023:** "Soil erosion assessment in the Amazon basin in the last 60 years of deforestation." RUSLE analysis showing 600%+ increase from 0.015 to 0.117 Mg/ha/yr basin-wide.

**Flores et al. 2019 (Plant and Soil):** "Soil erosion as a resilience drain in disturbed tropical forests." Documented that erosion rates mirror tree cover loss, and soil erosion prevents forest recovery when substrate is degraded.

**Ivory Coast analog data (worldrainforests.com):** Field measurements showing 0.03 t/ha/yr (forested) vs 90 t/ha/yr (cultivated) -- a 3,000:1 ratio that Gaia uses.

### Current Gaia Value Assessment

**Gaia uses: erosion_rate_protected = 0.015 t/ha/yr, erosion_rate_unprotected = 90 t/ha/yr.**

- The 0.015 value matches the ScienceDirect 2023 RUSLE baseline exactly. WELL SUPPORTED.
- The 90 t/ha/yr value comes from Ivory Coast tropical cultivated slope data. This is a reasonable analog for worst-case Amazon deforested land, though it may be conservative for some Amazonian settings. The Neshuya basin RUSLE data (3.87-4.55 t/ha/yr) represents a less extreme scenario with mixed land use.
- The destruction:recovery ratio of ~3,000:1 (90/0.015) is supported by the data.
- **Note:** The 90 t/ha/yr figure represents extreme cultivated tropical slopes. A more moderate value for typical Amazon deforested-to-pasture conversion might be 10-50 t/ha/yr. The 90 t/ha/yr represents a plausible upper bound. Consider adding a moderate scenario (e.g., 20-30 t/ha/yr for pasture conversion).

---

## 5. Secondary Forest Recovery Timeline

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Median time to 90% biomass recovery | 66 years | Poorter et al. 2016, Nature | HIGH |
| 20-year biomass recovery (absolute) | 122 Mg/ha | Poorter et al. 2016, Nature | HIGH |
| 20-year carbon uptake rate | 3.05 Mg C/ha/yr | Poorter et al. 2016, Nature | HIGH |
| Secondary vs old-growth uptake ratio | 11x faster in secondary | Poorter et al. 2016, Nature | HIGH |
| Initial vegetation cover | 2-3 years | Mongabay (restoration reports) | MEDIUM |
| Species diversity recovery | 25-60 years | EDF / Science studies | MEDIUM |
| Full old-growth equivalence | 100+ years | Multiple sources | MEDIUM |
| West Amazon regrowth rate | 3.0 +/- 1.0 Mg C/ha/yr | Heinrich et al. 2021, Nature Comms | HIGH |
| East Amazon regrowth rate | 1.3 +/- 0.3 Mg C/ha/yr | Heinrich et al. 2021, Nature Comms | HIGH |
| Fire/repeat deforestation recovery reduction | -8% to -55% | Heinrich et al. 2021, Nature Comms | HIGH |
| 20-year recovery benchmarks | >= 123 Mg/ha AGB, >= 14 m2/ha basal area | Comms Earth Environ 2024 | MEDIUM |

### Estimating 80% Recovery Timeline

Poorter 2016 reports 90% recovery at 66 years (median). While the paper does not explicitly state the 80% recovery time, we can estimate it. Given that:
- 20-year recovery averages 122 Mg/ha
- Old-growth averages ~174 Mg/ha (Saatchi 2007)
- 122/174 = ~70% at 20 years
- 90% at 66 years

Interpolating on the Poorter succession curve: **80% recovery is approximately 30-40 years** (based on the logarithmic/asymptotic shape of the recovery curve). The Gaia code comment states "20 yr to 80% biomass" (line 98) which may be slightly optimistic given that Poorter shows ~70% at 20 years. However, the Gaia succession curve's intermediate_service=0.40 at 20 years is well below 80%, so the model may handle this differently than the comment suggests.

### Key Studies

**Poorter et al. 2016 (Nature):** "Biomass resilience of Neotropical secondary forests." Landmark study analyzing 45 forest sites and ~1,500 plots across the Neotropics. Found median 66-year recovery to 90% and that secondary forests sequester carbon 11x faster than old-growth.

**Rozendaal et al. 2019 (Nature Ecology & Evolution):** "Biodiversity recovery of Neotropical secondary forests." Complementary study to Poorter showing that species diversity recovers slower than biomass, with functional composition shifting during succession.

**Heinrich et al. 2021 (Nature Communications):** "Large carbon sink potential of secondary forests in the Brazilian Amazon." Showed strong geographic variation (west 3.0 vs east 1.3 Mg C/ha/yr) and that repeated disturbance reduces regrowth by 8-55%.

### Current Gaia Value Assessment

**Gaia uses: pioneer_end=5yr, intermediate_end=20yr, climax_approach=66yr.**

- The 66-year climax approach matches Poorter 2016's 90% recovery exactly. WELL SUPPORTED.
- The 5-year pioneer end is reasonable (2-3 year initial cover + 2-3 year pioneer establishment).
- The 20-year intermediate end aligns with the ~70% biomass recovery at 20 years.
- **Note:** The code comment says "20 yr to 80% biomass" but Poorter data suggests ~70% at 20 years. The comment should be corrected to "20 yr to ~70% biomass."

---

## 6. Carbon Sequestration Rate (Intact Forest)

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Net biomass C sink (1990s, per ha) | 0.37 Mg C/ha/yr | Brienen et al. 2015, Nature (RAINFOR) | HIGH |
| Net biomass C sink (2000s, per ha) | 0.24 Mg C/ha/yr | Brienen et al. 2015, Nature (RAINFOR) | HIGH |
| Decline over the decade | ~30% decrease | Brienen et al. 2015, Nature | HIGH |
| Total Amazon sink (1990s) | 0.54 Pg C/yr (CI 0.45-0.63) | Brienen et al. 2015, Nature | HIGH |
| Total Amazon sink (2000s) | 0.38 Pg C/yr (CI 0.28-0.49) | Brienen et al. 2015, Nature | HIGH |
| Pre-2005 drought sink | ~0.5 t C/ha/yr (76% of plots) | RAINFOR, Carbon Brief | HIGH |
| Historical net accumulation (1975-1996) | 0.62 +/- 0.37 t C/ha/yr | Wikipedia (historical RAINFOR) | MEDIUM |
| Amazon-wide annual absorption | ~430 Mt C/yr | Phillips & Brienen 2017 | HIGH |
| GPP (old-growth, Central Amazon) | 28.5 Mg C/ha/yr | ScienceDirect 2024 (eddy covariance) | HIGH |
| NPP (total) | ~10-12 Mg C/ha/yr | Malhi 2012 (biometric) | HIGH |

### Key Studies

**Brienen et al. 2015 (Nature):** "Long-term decline of the Amazon carbon sink." Landmark study using 321 RAINFOR plots. Found per-hectare net biomass increment declined from 0.37 to 0.24 Mg C/ha/yr between the 1990s and 2000s. The decline was driven by increasing tree mortality rates (not decreasing growth). Based on tracking 200,000 individual trees over 30 years.

**Phillips & Brienen 2017 (Carbon Balance and Management):** "Carbon uptake by mature Amazon forests has mitigated Amazon nations' carbon emissions." Estimated Amazon-wide biomass carbon sink of 0.43 Pg C/yr (CI 0.21-0.67) between 1980-2010.

### Current Gaia Value Assessment

**Gaia uses: annual_absorption_tonnes = 0.006 t CO2/tree/yr.** The code derives this from "0.62 t C/ha/yr x 3.67 / 400 = 0.0057 t CO2/tree/yr."

The 0.62 t C/ha/yr base value is from historical (1975-1996) data. Brienen 2015 shows this declined to:
- 0.37 Mg C/ha/yr in the 1990s
- 0.24 Mg C/ha/yr in the 2000s

**RECOMMENDATION:** The 0.62 value is the historical peak. A more current and defensible value would be 0.30-0.40 Mg C/ha/yr, reflecting the documented decline. However, using the historical value is justifiable if the model represents pre-disturbance conditions.

**Important distinction:** The NET sink (0.24-0.62 Mg C/ha/yr) is the balance of growth minus mortality. The GROSS productivity (NPP ~10-12 Mg C/ha/yr) is much higher but is offset by respiration and decomposition. For modeling ecosystem service value, the net sink is the correct metric for "additional carbon removed from atmosphere."

---

## 7. Ecosystem Service Valuation

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Tropical forest total (mean) | 5,264 Int$/ha/yr | de Groot et al. 2012, Ecosystem Services | HIGH |
| Tropical forest total (with all services) | up to ~20,851 Int$/ha/yr | de Groot et al. 2012 (including high estimates) | MEDIUM |
| Amazon ecosystem services (meta-analysis mean) | ~$410/ha/yr | Brouwer et al. 2022, PLOS ONE | HIGH |
| Spatially explicit (high-value areas, 12% of forest) | $57-$737/ha/yr | Nature Sustainability 2018 | MEDIUM |
| Amazon-specific estimate | $1,175/ha/yr | Torras (assessment) | MEDIUM |
| Costanza tropical forest (1994 values) | $2,007/ha/yr | Costanza et al. 1997 (updated 2014) | MEDIUM |
| Carbon capitalized (at $30/t CO2) | ~$14,000/ha (one-time) | Strassburg review | HIGH |
| Provisioning services only | $20-50/ha/yr | Strassburg review | MEDIUM |
| REDD+ reference price | $10/t CO2 | CPI/PUC-RIO 2025 | HIGH |

### Key Studies

**de Groot et al. 2012 (Ecosystem Services):** "Global estimates of the value of ecosystems and their services in monetary units." Screened 320+ publications, 1,350 value estimates. Found tropical forest mean total value of 5,264 Int$/ha/yr (2007 international dollars). Based on 96 tropical forest studies. This is the most comprehensive meta-analysis of ecosystem service values.

**Costanza et al. 2014 (Global Environmental Change):** "Changes in the global value of ecosystem services." Updated the seminal 1997 analysis. Tropical forest values increased relative to 1997 estimates due to better accounting of regulating services.

**Brouwer et al. 2022 (PLOS ONE):** Amazon-specific meta-analysis finding mean ~$410/ha/yr, which is lower than de Groot's global tropical forest figure because it focuses on locally captured values rather than global externalities.

### Current Gaia Value Assessment

**Gaia uses: ~EUR 840/ha/yr (EUR 8.4M for 10,000 ha).** This is composed of:
- Carbon stock protection: EUR 5.08M/yr
- Carbon sequestration: EUR 880k/yr
- Water cycling: EUR 1.5M/yr
- Fisheries: EUR 200k/yr
- Biodiversity/habitat: EUR 410k/yr

The EUR 840/ha/yr total is well within the range of published estimates:
- Below de Groot 2012 ($5,264) -- conservative
- Above Brouwer 2022 ($410) -- accounts for global externalities
- Near Torras ($1,175) and Costanza ($2,007)

The carbon stock protection anchor (EUR 508/ha/yr) dominates because old-growth Amazon has massive stored carbon (~635 t CO2/ha) whose release would be a one-time catastrophic emission. **This is the correct approach for Amazon forests where stock protection value exceeds flow value.**

---

## 8. Soil Carbon (Oxisol)

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| SOC under oxisol, Central Amazonia (0-100 cm) | 90-195 Mg C/ha | Quesada et al. / SciELO (Central Amazon transects) | HIGH |
| SOC under mature forest, SW Amazon (0-100 cm) | 96 Mg C/ha | Pinheiro et al. 2017, Geoderma Regional | HIGH |
| SOC under pasture (0-100 cm) | 79.7 Mg C/ha | Pinheiro et al. 2017 | HIGH |
| SOC under rubber plantation (0-100 cm) | 56.3 Mg C/ha | Pinheiro et al. 2017 | MEDIUM |
| SOC loss from soybean cultivation | -30% (-8.1 Mg C/ha) | ScienceDirect (land use change study) | HIGH |
| Stable C fraction (mineral-associated, top 1m) | > 85% of total SOC | Multiple sources | HIGH |
| Mean age of stabilized SOC | Centuries to millennia | Multiple sources | HIGH |
| Top 10 cm contribution | ~30% of total SOC | Multiple sources | MEDIUM |

### Key Insight

The SOC values (90-195 Mg C/ha to 1m depth) are substantial but highly variable across the basin. The critical finding is that >85% of the SOC in the top 1m is mineral-associated and very stable, with mean ages of centuries to millennia. This means that while forest loss primarily affects the labile fraction in the top 10-20 cm, the deeper stabilized carbon is relatively resistant to land-use change on short timescales.

### Current Gaia Value Assessment

**Gaia uses: soil_carbon_tonnes = 0.367 t CO2/tree (derived from ~40 t C/ha in roots x 3.67 / 400 trees).**

The "40 t C/ha in roots" appears to be a ROOT carbon estimate, not total SOC. The total SOC (0-100 cm) is much higher at 90-195 Mg C/ha. However, root carbon specifically is typically 20-30% of AGB, which for AGB of ~174 Mg/ha (at ~0.48 C fraction) would be ~17-25 Mg C/ha in roots alone.

**RECOMMENDATION:** The parameter naming is slightly confusing. The "soil_carbon_tonnes" represents root system carbon, not total soil organic carbon. The model documentation should clarify this distinction. If the model intends to capture soil C release from deforestation, the relevant pool is the labile fraction of SOC (top 20 cm) plus root decomposition, which could be 40-60 Mg C/ha.

---

## 9. Mycorrhizal Dependency

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Plant species forming mycorrhizal associations | ~80% of all plant species globally | Multiple reviews | HIGH |
| Tropical lowland trees with AM associations | Nearly 100% form some AM association | Multiple tropical studies | HIGH |
| AM fungi phosphorus contribution | Up to 80% of plant P uptake | Nottingham et al. / Multiple | HIGH |
| Amazon forests on P-depleted Oxisols/Ultisols | > 50% of tropical forests | Frontiers 2021 | HIGH |
| AFEX: P addition effect on fine root productivity | +29% in first 2 years | Cunha et al. 2022, Nature | HIGH |
| AFEX: P addition effect on canopy productivity | +19% in first 2 years | Cunha et al. 2022, Nature | HIGH |
| AFEX: NPP response to P addition | ONLY phosphorus increased productivity | Cunha et al. 2022, Nature | HIGH |
| AFEX: N or cation addition effect | No significant productivity increase | Cunha et al. 2022, Nature | HIGH |

### Key Studies

**Cunha et al. 2022 (Nature):** "Direct evidence for phosphorus limitation on Amazon forest productivity." The AFEX (Amazon Fertilization Experiment) at Cueiras Reserve, ~70 km north of Manaus. Fully factorial design with N, P, and cation additions on 50x50m plots. Found that ONLY phosphorus increased net primary productivity. This is the strongest direct evidence that AM fungi (which mobilize P) are the critical nutrient gateway in Amazon forests.

**AFEX Experimental Design:**
- Location: Central Amazonia, Cueiras Reserve
- N treatment: 125 kg N/ha/yr
- P treatment: 50 kg P/ha/yr
- Cation treatment: 50 kg KCl/ha/yr + 160 kg dolomitic limestone/ha/yr
- Strong P responses both above (+19% canopy) and below ground (+29% fine roots)

### Current Gaia Value Assessment

**Gaia uses: Mycorrhizal Fungi as KEYSTONE agent with weight 0.15 and scarcity alpha 2.5 (highest).**

This is strongly supported by the AFEX evidence. The AFEX experiment provides direct experimental proof that phosphorus is THE limiting nutrient in Central Amazon, and mycorrhizal fungi are THE biological mechanism for P acquisition. The description "non-substitutable nutrient gateway on P-depleted Oxisol" is scientifically accurate.

**On the specific question of "what percentage of Amazon trees depend on mycorrhizal networks":** Effectively 100% of tropical lowland forest trees form mycorrhizal associations. The vast majority are arbuscular mycorrhizal (AM), with a small fraction being ectomycorrhizal (ECM). In lowland Amazonia, AM associations dominate overwhelmingly. The dependency is obligate on P-depleted soils -- without the fungal network, trees cannot access sufficient phosphorus.

---

## 10. Pollinator Dependency

### Published Values

| Parameter | Value | Study | Confidence |
|---|---|---|---|
| Tropical community animal-pollinated species | 94% (mean) | Ollerton et al. 2011, Oikos | HIGH |
| Tropical lowland forest animal-pollinated | > 98% of flowering species | Various tropical ecology reviews | HIGH |
| Temperate community animal-pollinated (comparison) | 78% (mean) | Ollerton et al. 2011, Oikos | HIGH |
| Global flowering plants animal-pollinated | 85-87.5% (of ~352,000 species) | Ollerton et al. 2011, Oikos | HIGH |
| Updated global estimate | ~90% of flowering plants | National Science Review 2023 | HIGH |
| Self-incompatibility in tropical trees | Common -- reinforces pollinator dependency | Bawa 1990, multiple studies | HIGH |

### Key Studies

**Ollerton et al. 2011 (Oikos):** "How many flowering plants are pollinated by animals?" Community-level surveys showing the proportion rises from 78% (temperate mean) to 94% (tropical mean). This is the most cited study on pollination dependency percentages.

**National Science Review 2023:** "New calculations indicate that 90% of flowering plant species are animal-pollinated." Updated Ollerton's global figure upward.

**Bawa & colleagues:** Documented that many tropical tree species have self-incompatibility systems, making animal pollination obligate rather than optional.

### Current Gaia Value Assessment

**Gaia uses: ">90% of tropical tree species require animal pollination" in descriptions and alpha=2.0 for Pollinators scarcity.**

This is well supported by Ollerton 2011 (94% for tropical communities) and other sources showing >98% for lowland tropical forests. The ">90%" statement is conservative and defensible. The scarcity alpha of 2.0 is appropriate -- high but below mycorrhizal fungi (2.5), reflecting that while pollinator loss would be catastrophic for reproduction, existing mature trees would persist for decades even without pollinators (unlike the immediate nutrient limitation from mycorrhizal loss).

---

## Summary: Parameter Validation Status

| Parameter | Gaia Current Value | Literature Value | Status |
|---|---|---|---|
| Total biomass carbon | 173 Mg C/ha | 173 +/- 12 Mg C/ha | VALIDATED |
| Tree density | 40 trees/ha (as modeled) | 400-600 trees/ha (field) | NEEDS REVIEW (see note) |
| Tipping point threshold | 20% | 20-25% | VALIDATED (conservative end) |
| Erosion (intact) | 0.015 t/ha/yr | 0.015 t/ha/yr | VALIDATED |
| Erosion (unprotected) | 90 t/ha/yr | 90 t/ha/yr (Ivory Coast analog) | VALIDATED (upper bound) |
| Recovery to 90% biomass | 66 years | 66 years (median) | VALIDATED |
| Carbon sequestration (net) | 0.62 t C/ha/yr | 0.24-0.62 (declining) | PARTIALLY VALIDATED (historic peak) |
| Ecosystem service value | EUR 840/ha/yr | $410-$5,264/ha/yr | VALIDATED (within range) |
| Soil carbon (roots) | ~40 t C/ha | SOC: 90-195 Mg C/ha total | NEEDS CLARIFICATION |
| Mycorrhizal dependency | KEYSTONE agent | ~100% of trees, AFEX confirms | VALIDATED |
| Pollinator dependency | >90% | 94-98% | VALIDATED |

### Priority Corrections

1. **Tree density discrepancy:** The 40 trees/ha modeling abstraction vs 400-600 trees/ha reality should be documented explicitly as a modeling choice, not a scientific estimate.

2. **Carbon sequestration rate:** Consider updating from 0.62 to 0.30-0.40 Mg C/ha/yr to reflect the documented decline (Brienen 2015), or document that 0.62 represents pre-disturbance baseline conditions.

3. **Succession curve comment:** Line 98 says "20 yr to 80% biomass" but Poorter 2016 shows ~70% at 20 years. The comment should be corrected.

4. **Soil carbon naming:** Clarify that "soil_carbon_tonnes" in CarbonProfile represents root carbon, not total SOC.
