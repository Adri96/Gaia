# Posidonia oceanica (Catalan coast): literature review of every parameter

Step 8.2 of `TOP_PRIORITIES_REPORT.md`, for the v1.0 case `gaia/cases/data/posidonia.json` (decision D6). For each parameter of the case this review gives its value, the source, the range, how the source maps to the parameter, and the confidence recorded in the case file's provenance, which every Gaia output prints.

## How the sources were checked

- **Metadata.** Every DOI below was resolved through the Crossref API (title, authors, journal, year, volume, pages). One DOI first tried for Campagne et al. (2015), 10.1016/j.ecoser.2015.02.002, turned out to belong to a different paper (Kleisner et al. 2015); the correct one is below. **No DOI here was typed from memory.**
- **Numbers.** Each number was read from the source itself, never from a secondary summary unless stated:
  - the abstract (Crossref, OpenAlex or the publisher page);
  - the full text where it was openly available: Campagne et al. 2015, Pendleton et al. 2012, Costanza et al. 2014, the Drupp et al. working paper and arXiv paper, the IPCC Wetlands Supplement chapter 4, the US EPA SC-GHG report;
  - official documents: the French Label Bas-Carbone Posidonia method, the ECB exchange-rate series.
- **What is flagged.** Where a value could not be checked it stays in the case and is flagged (`placeholder`, or `low` with the reason in its note). Secondary figures are labelled as such.
- **Confidence levels** follow `gaia/provenance.py`:
  - `medium`: a published value for this or a comparable system, citation checked;
  - `low`: an order of magnitude, a judgement with a stated rationale, or a source not specific to the system;
  - `placeholder`: no source.

## Summary

69 parameters are recorded for a Posidonia run (with restoration). They split as follows:

| Status | Count | Parameters |
|---|---|---|
| Sourced, DOI (or arXiv id) checked | 21 | the four final-service values; the six zero-value agents (final-services accounting); absorption, soil stock, release fraction; substrate formation; discount rate and scarcity; planting cost; four succession parameters |
| Sourced, official URL checked | 4 | resource area (Generalitat map, as reported); biomass carbon (Label Bas-Carbone method); carbon price and its growth (US EPA 2023, ECB rate) |
| Flagged `low`, no source | 10 | the ten dependency weights (owner specification) |
| Flagged `placeholder` | 34 | private gain per ha; safe threshold; damage steepness; keystone threshold; 15 edge strengths; 4 substrate parameters; the declining discount steps and horizon; maintenance cost and years; recovery steepness; two succession parameters; the three model-wide trophic/keystone constants |

Of the 25 sourced parameters, 11 are `medium` and 14 `low`. They are `low` either because the source is global or a congener rather than *P. oceanica* in Catalonia, or because it is a modelling choice backed by a methodological reference.

The case remains **illustrative** by Gaia's own rule (`CalibrationStatus.status`), because placeholders remain. What changed is that every money figure and every carbon figure now has a checked source and a range. What is still unsourced is the ecological structure: the response curves, the edges and the threshold. That structure can be argued about but not looked up; Track 1 review is for exactly that.

## 1. The reference resource

| Parameter | Value | Source | Range / notes | Confidence |
|---|---|---|---|---|
| `resource.area_ha` (= `total_units`) | 4,582 ha | Generalitat de Catalunya, *Mapa d'hàbitats marins de Catalunya*, presented 29 May 2025 (Hipermapa). P. oceanica covers 4,582 ha, 2.4% of ~190,000 ha mapped down to 50 m. Figure as reported by Ara (29 May 2025, <https://en.ara.cat/society/from-portbou-to-alcanar-this-is-the-catalan-seabed_1_5395705.html>); 3Cat and Ecoticias give the same figures. | The whole Catalan stock. The map's breakdown by coast (how much is Costa Brava) and the dataset itself were not available to this review, and the Govern's press-release PDF returned HTTP 403. The former 5,000 ha exceeded the entire Catalan stock. | medium |
| `resource.unit_value` | €2,500/ha | none | Project-specific: the private gain per hectare destroyed. The user sets it (`--unit-value`) for the project assessed. | placeholder |
| `resource.safe_threshold_ratio` | 0.20 | none | No ecological or regulatory source supports a "safe" loss of 20% of a priority habitat (Habitats Directive 1120\*). It also sets the inflection of every damage curve (§3). | placeholder |
| run default `units` | 50 ha | none | An illustrative project size, about 1.1% of the stock; the user sets N. | — |

Context, not a parameter:
- **Regional decline.** Telesca et al. (2015), *Sci. Rep.* 5:12505, doi:10.1038/srep12505, map 1,224,707 ha of known *P. oceanica* and estimate a 34% regression over the last 50 years.
- **Anchoring loss rate.** The Label Bas-Carbone method takes 0.29%/yr as its default regression rate under anchoring, from Telesca et al.'s 9% for France over 1980–2011.

## 2. Agent values: final ecosystem services

**Mapping.** Gaia's cost for agent *i* is damage × weight × `annual_value_per_ha` × area. Each agent's `annual_value_per_ha` is therefore set to (service value per ha) / weight. This makes weight × value the sourced €/ha/yr. The owner's weights keep their role in the health index.

**Why only final services carry euros.** Ecosystem-service accounting values a benefit once, where people receive it (Boyd & Banzhaf 2007, *Ecological Economics* 63:616–626, doi:10.1016/j.ecolecon.2007.01.002; Fisher, Turner & Morling 2009, *Ecological Economics* 68:643–653, doi:10.1016/j.ecolecon.2008.09.014). The meadow, epiphytes and invertebrates produce the fisheries, the coastal protection and the water quality. A separate euro value on them would count the same benefit twice. In Gaia they keep their health weights and their edges, so their damage still raises the damage of the final services.

**Primary valuation.** Campagne, Salles, Boissery & Deter (2015), "The seagrass *Posidonia oceanica*: ecosystem services identification and economic evaluation of goods and benefits", *Marine Pollution Bulletin* 97:391–400, doi:10.1016/j.marpolbul.2015.05.061. Table 2, € 2014/ha/yr, French Mediterranean meadows (read from the article). The paper:
- identifies 25 services, of which 14 could be valued;
- totals 284–514 €/ha/yr including carbon;
- states that the figure is an undervaluation, mainly because tourism and most cultural services could not be valued.

| Agent | €/ha/yr at full damage (weight × value) | Source and mapping | Range | Confidence |
|---|---|---|---|---|
| Coastal Protection | 188 | Campagne et al. 2015: "protection from coastal erosion" (damage cost avoided, 160,000 € per protected km in the Mediterranean, 2001 data inflated to 2014). Covers three services: wave attenuation, beach-cast banquettes, matte stabilisation. Physical basis: wave height falls ~50% over ~1 km of meadow (Infantes et al. 2012, *MEPS* 456:63–72, doi:10.3354/meps09754). | single estimate; ×/÷2 in the Monte Carlo (judgement) | medium |
| Water Quality | 60 | Campagne et al. 2015: "wastewater treatment" (benefit transfer of the French water-protection tax, 0.19 €/m³, one third attributed to coastal systems after Costanza et al. 1997) | single, crude estimate; ×/÷2 (judgement) | medium |
| Fish Populations | 35 | Campagne et al. 2015: "fishery contribution", 27–35 €/ha/yr (production function; upper end used) | 27–74. The 74 is **derived here, not published**: Jackson et al. (2015), *Conservation Biology* 29:899–909, doi:10.1111/cobi.12436, attribute €58–91 million/yr of Mediterranean commercial landings to seagrass. Divided by the known *P. oceanica* area (1,224,707 ha, Telesca et al. 2015) that is €47–74/ha/yr, an overestimate per hectare of *P. oceanica* because other seagrasses also contribute. | medium |
| Human Communities | 1.83 | Campagne et al. 2015: bioindicator use 1.5 + knowledge contribution 0.33 | **tourism, recreation and non-use NOT valued** | medium |
| Posidonia Meadow, Epiphytes & Algae, Marine Invertebrates | 0 | Intermediate services (Boyd & Banzhaf 2007; Fisher et al. 2009) | — | low |
| Coralligenous & Red Coral | 0 | A neighbouring habitat affected through sedimentation; its own values (diving, coral) are not part of a Posidonia valuation | — | low |
| Marine Megafauna, Seabirds | 0 | Non-use and wildlife-watching values: no per-hectare estimate tied to Posidonia was found | — | low |

**Total:** €284.83/ha/yr at full damage, excluding carbon (valued separately, §4). The former owner-specified values totalled €1,066/ha/yr (no source).

**Searched for but not used:**
- **Divers' willingness to pay.** Zunino et al. (2020), *Front. Mar. Sci.* 6:823, doi:10.3389/fmars.2019.00823: Italian divers' WTP per dive falls by €18 for a 50% loss of P. oceanica cover and by €34 for a total loss. These are values per dive, not per hectare; converting them needs dive counts per hectare, which are not available.
- **Recreational fisheries.** Jackson et al. (2015) attribute €112 million/yr of Mediterranean recreational-fisheries **expenditure** to seagrass. Expenditure is not a welfare measure.
- **Emergy (supply-side) values.** Vassallo et al. (2013), *Mar. Pollut. Bull.* 75:157–167, doi:10.1016/j.marpolbul.2013.07.044: 172 €/m²/yr as quoted by Campagne et al., 99% of it from sediment retention. Rigo et al. (2021), *Diversity* 13:499, doi:10.3390/d13100499. These measure the resources nature invests, not what people would pay, so they are not comparable with the values above. They are kept as a benchmark only (§10).

## 3. Damage curves, health weights, cascade network

| Parameter | Value | Source | Notes | Confidence |
|---|---|---|---|---|
| `agent[*].dependency_weight` (10) | 0.044–0.154, sum 1 | owner specification (weights / 0.91 after the Blue Carbon agent was removed) | Health shares. They also scale each agent's euros, but weight × value is fixed to the sourced service value, so the euros do not depend on them. Held fixed in the Monte Carlo. | low |
| `damage.logistic_steepness` | 12 | none | The same logistic for all ten agents, inflection at 32% loss. **No Posidonia study relates the fraction of meadow lost to the fraction of each service lost**: the curve cannot be fitted (calibration regime B). | placeholder |
| `agent[Posidonia Meadow].keystone_threshold` | 0.3 (health) | none | Below it the meadow's outgoing edges double. | placeholder |
| 15 `edge[…].strength` | 0.15–0.40 | none | Several links are documented qualitatively: meadow → wave attenuation (Infantes et al. 2012); seagrass → fisheries via juvenile residency (Jackson et al. 2015); meadow loss → carbon erosion in exposed shallow areas (Salinas et al. 2020). Their strengths are not. | placeholder |
| trophic levels | 0–3 | structural choice (consumers: invertebrates 1, fish and seabirds 2, megafauna 3) | Model-wide constants: transfer efficiency 0.15 and amplification exponent 0.25 (placeholders in `gaia/constants.py`). Lindeman (1942), *Ecology* 23:399–417, doi:10.2307/1930126, and Pauly & Christensen (1995), *Nature* 374:255–257, doi:10.1038/374255a0, are the classic references for trophic transfer; their metadata were checked, but no transfer-efficiency figure was read from them for this review. | placeholder |

**What the placeholders do to the answer.** At small losses, which is the user's question (a project destroying ~1% of the stock), the normalised logistic starts with a slope of about 0.25. Each hectare destroyed therefore costs about a quarter of its average per-hectare value before cascades. A linear benefit transfer, the method of Campagne et al. and of most impact assessments, would charge the full value. The Monte Carlo varies steepness and threshold, and the methods note shows both figures.

**CalibrationWarning (health 0.67 at the 20% threshold).** This review leaves it in place. The warning fires because the placeholder curves put heavy damage inside the "safe" zone. No source supports moving the threshold or the curves to a value that would silence it, and no source supports calling a 20% loss of a priority habitat safe. The warning therefore stays as an honest signal.

## 4. Carbon (finding S5 resolved)

Carbon is valued only by `gaia.carbon` (decision D3):
- the release, at year 0: area destroyed × (biomass + soil stock × release fraction);
- the lost burial, a yearly flow at the social cost of carbon.

S5 was that the case used two different absorption rates. It now uses one sourced rate with its range.

| Parameter | Value | Source and mapping | Range | Confidence |
|---|---|---|---|---|
| `carbon.annual_absorption_tonnes` | 0.953 tCO₂/ha/yr | Mazarrasa et al. (2017), *Limnology and Oceanography* 62:1436–1450, doi:10.1002/lno.10510: organic-carbon burial **26 ± 6 g C/m²/yr** in Balearic *P. oceanica* since 1900 (²¹⁰Pb), the nearest region with direct measurements; × 44/12 | 0.28–3.09 tCO₂/ha/yr = 7.7–84.4 g C/m²/yr, the depth range of mean sequestration in a large Corsican meadow (Pergent-Martini et al. 2021, *Mar. Environ. Res.* 165:105236, doi:10.1016/j.marenvres.2020.105236). Campagne et al. quote 6–175 g C/m²/yr from Pergent et al. (2012, grey literature, not checked). The former value, the IPCC (2013) Wetlands Supplement Table 4.12 seagrass factor of 0.434 t C/ha/yr (95% CI 0.2–0.7, n = 6, from Mateo & Romero 1997 and Serrano et al. 2012), applies to re-established meadows and lies inside the range. | medium |
| `carbon.soil_carbon_tonnes` | 1,199 tCO₂/ha | Monnier et al. (2022), *Sci. Total Environ.* 838:155864, doi:10.1016/j.scitotenv.2022.155864: 327 ± 150 t Corg/ha (mean ± SE, 39 matte cores, eastern Corsica). Adopted as the Tier 1 default for **1 m of matte** by the French Label Bas-Carbone method (below); × 44/12 | 741–1,844 tCO₂/ha = 20.2–50.3 kg Corg/m² in the first metre of matte, Calvi Bay (Leduc et al. 2023, *Mar. Environ. Res.* 183:105847, doi:10.1016/j.marenvres.2022.105847). For scale: the IPCC (2013) global Tier 1 seagrass soil stock is 108 t C/ha to 1 m (Table 4.11); Balearic meadows hold 6.1 ± 1.4 kg C/m² in the top 30 cm alone (Mazarrasa et al. 2017); the global mean to 20 cm is 15.4 Mg C/ha, with the largest stocks in Mediterranean *P. oceanica* (Kennedy et al. 2022, *Global Biogeochem. Cycles* 36:e2022GB007481, doi:10.1029/2022gb007481). | medium |
| `carbon.soil_release_fraction` | 0.63 | Pendleton et al. (2012), *PLoS ONE* 7:e43542, doi:10.1371/journal.pone.0043542 (full text): **25–100% of near-surface (top-metre) carbon lost upon conversion, central 63%** | 0.25–1.0. The fraction depends on what the project does. The IPCC (2013) Wetlands Supplement (ch. 4, read) treats "excavation to enable port, harbour and marina construction" as extraction and emits the top-metre soil carbon in that year, minus 4% refractory, i.e. 0.96. The Label Bas-Carbone method models anchoring damage as a gradual loss, 10.7% of the top metre over 10 years (after Mateo et al. 2019, LIFE Blue Natura, not checked). Burial under fill may keep much of the carbon. Salinas et al. (2020), *Glob. Change Biol.* 26:4772–4784, doi:10.1111/gcb.15204, found soil carbon eroded after seagrass loss in shallow, exposed areas (4.5 → 0.5 kg Corg/m², top 50 cm) but not in deeper ones. | low |
| `carbon.stored_carbon_tonnes` (living biomass) | 0 | Label Bas-Carbone method (below), §7: the carbon in the leaves is "négligeable comparé au carbone stocké et séquestré dans la matte" | Living rhizomes and roots lie inside the top-metre matte stock, so a separate biomass term would double count. No *P. oceanica* leaf-biomass carbon figure was checked. | low |

**Label Bas-Carbone method.** Ministère de la Transition écologique, *Méthode de protection des herbiers de posidonie éligibles pour l'obtention du Label Bas-Carbone*, approved by decision of 21 March 2023 (NOR ENER2305073S), <https://aida.ineris.fr/sites/aida/files/2023-04/Dec20230321_1.pdf> (read). The method is described in Comte et al. (2024), *Mar. Pollut. Bull.* 198:115822, doi:10.1016/j.marpolbul.2023.115822.

**Release per hectare destroyed:** 1,199 × 0.63 = 755 tCO₂ (formerly 260). At the social cost of carbon (€166/t) that is about €126,000 per hectare, one-off. It is the largest single term of the externality, and its release fraction is the least certain input. The Monte Carlo confirms both points.

## 5. Substrate (matte)

Substrate damage only lowers the restoration ceiling and the substrate recovery time. It adds nothing to the extraction PV (Step 3.4).

| Parameter | Value | Source | Notes | Confidence |
|---|---|---|---|---|
| `substrate.formation_rate` | 1 mm/yr | Serrano et al. (2016), *Biogeosciences* 13:4581–4594, doi:10.5194/bg-13-4581-2016: soil accumulation 1.2–2.0 mm/yr in meadows of the congener *P. sinuosa* (Australia) | Rounded down. No *P. oceanica* matte accretion rate was checked: Mateo et al. (1997), *ECSS* 44:103–110, doi:10.1006/ecss.1996.0116 (metadata checked; no abstract available). | low |
| `sediment_stability`, `erosion_rate_unprotected`, `erosion_rate_protected`, `erosion_alpha` | 0.85, 5, 0, 3 | none | Matte erosion after loss depends on exposure (Salinas et al. 2020). | placeholder |

## 6. Restoration, recovery and succession

| Parameter | Value | Source | Notes | Confidence |
|---|---|---|---|---|
| `restoration.planting_cost_per_unit` | €50,000/ha | Bayraktarov et al. (2016), *Ecol. Appl.* 26:1055–1074, doi:10.1890/15-1077 | Median reported cost of marine coastal restoration ~US$80,000/ha (2010); real costs likely 2–4× higher; seagrass among the most expensive habitats. The value is an order of magnitude, not a Posidonia cost survey. A planting guide by Red Eléctrica de España cites US$383,672/ha for seagrass from the same paper; **not checked** against it. The paper's dataset (Dryad, doi:10.5061/dryad.rc0jn) requires login. | low |
| `restoration.annual_maintenance_per_unit`, `maintenance_years` | €5,000/ha/yr, 30 yr | none | | placeholder |
| `recovery.logistic_steepness` | 7 | none | Transplant survival is low: median 38% for seagrass (Bayraktarov et al. 2016); 0–31% after 40–48 months on substrate disturbed by infrastructure works (Castejón-Silvo & Terrados 2021, *Mar. Environ. Res.* 170:105406, doi:10.1016/j.marenvres.2021.105406). Restoration evidence is inconsistent (Pansini et al. 2022, *Sci. Total Environ.* 851:158320, doi:10.1016/j.scitotenv.2022.158320). | placeholder |
| `succession.pioneer_end_year` | 100 yr | Kendrick, Marbà & Duarte (2005), *ECSS* 65:717–725, doi:10.1016/j.ecss.2005.07.007 (abstract): agent-based model of *P. oceanica* colonisation, "limited cover after a century of growth" | Natural recolonisation. Transplanting may be faster but is unproven at scale. Rhizomes extend only centimetres a year; *P. oceanica* sits at the slow end of the 1.2–574 cm/yr range across seagrass species (Marbà & Duarte 1998, *MEPS* 174:269–280, doi:10.3354/meps174269). | low |
| `succession.pioneer_service` | 0.10 | interpretation of "limited cover" | Not a number from the paper. | placeholder |
| `succession.intermediate_end_year` | 400 yr | Kendrick et al. 2005: growth accelerates after 100 years and plateaus after 400 | A model result, not a field series. | low |
| `succession.intermediate_service` | 0.67 | Kendrick et al. 2005: two-thirds of the landscape occupied after 600 years | Cover read as service. | low |
| `succession.climax_approach_year` | 600 yr | Kendrick et al. 2005: the simulated span | Beyond the 200-year horizon. | low |
| `succession.maturation_delay` | 5 yr | none | | placeholder |

Former values: 20 / 50 / 120 years and 2% / 25% service. Natural recolonisation is several times slower than that.

## 7. Discounting and the price of carbon (normative)

| Parameter | Value | Source | Notes | Confidence |
|---|---|---|---|---|
| `discount.rate_schedule[year 0]` | 2.3%/yr | Drupp, Freeman, Groom & Nesje (2018), *AEJ: Economic Policy* 10(4):109–134, doi:10.1257/pol.20160240. Table 1 of the working-paper version (Grantham WP 172, 2015, read): mean recommended SDR 2.27%, median 2.0% | The survey's Ramsey components (δ median 0.5%, mean 1.1%; η mean 1.35, median 1.0; growth mean 1.70%, median 1.60%) do not add up to the recommended rate; experts mostly do not follow the Ramsey rule. The former reference g = 1.3% had no source. The case's reference components are now the survey medians (δ 0.5%, η 1.0, g 1.6%), and the rate is the mean SDR. | medium |
| `discount.rate_schedule[year 31]`, `[year 101]` | 1.8%, 1.4% | none | The declining steps are a normative choice. | placeholder |
| `discount.scarcity_rate` | 1%/yr | Drupp, Turk, Groom & Heckenhahn (2024), arXiv:2308.04400v3 (read): §1, "The Netherlands consider a general default relative price change of 1 percent per annum for ecosystem services"; Table 10, aggregate 1.66% (95% CI 1.40–1.92), regulating 1.71, cultural 1.91, forest 1.28 | 1.66% exceeds the schedule's long-term 1.4%, so the 200-year PV would diverge. 1% is kept. | medium |
| `discount.horizon_years` | 200 | none | The outputs also report 50, 100 and 200 years. | placeholder |
| `carbon_price.year0` (model-wide) | €166.35/tCO₂ | US EPA (2023), *Report on the Social Cost of Greenhouse Gases*, Table ES.1 (read): $190 for 2020 emissions at a 2.0% near-term rate ($120 at 2.5%, $340 at 1.5%), <https://www.epa.gov/system/files/documents/2023-12/epa_scghg_2023_report_final.pdf>. Converted at the ECB 2020 average of 1.1422 USD/EUR (ECB data API, read: 1.1421961). See also Rennert et al. (2022), *Nature* 610:687–692, doi:10.1038/s41586-022-05224-9. | | medium |
| `carbon_price.growth` | 1.3%/yr | the same EPA table: $410 for 2080 emissions at 2.0% (read) | | medium |

These are value judgements as much as facts. The uncertainty analysis therefore does not sample them; it reports them as sensitivities (`docs/POSIDONIA_METHODS_NOTE.md`).

## 8. Out of scope: EXPERIMENTAL pricing

The quarantined endogenous pricing (decision D4) keeps the two anchors it had. Both are `low`, with sources in the case file. The six agents without a euro value get their former owner-specified impacts as PLACEHOLDER anchors, because pricing requires a positive anchor for every agent. Pricing is not part of the v1.0 output.

## 9. What was searched for and not found

- **A Posidonia damage-response curve.** No study relating the fraction of a meadow lost to the fraction of each service lost.
- **Interaction strengths.** None for the case's 15 edges.
- **Tourism, recreation and non-use values per hectare of P. oceanica.** No direct study found. The Mediterranean meta-regression of Stamatiadou et al. (2025) includes recreation (§10).
- **The Costa Brava share of the Catalan stock.** Not found; the Generalitat's dataset was not downloaded.
- **P. oceanica-specific figures** for matte accretion, leaf-biomass carbon and transplanting cost.
- **The "80× fish biomass in the Medes Islands" claim** in the former case notes. No source found; the claim is removed. García-Rubies, Hereu & Zabala (2013), *PLoS ONE* 8:e73922, doi:10.1371/journal.pone.0073922, report instead that exploited fish in the Medes no-take reserve took 25–35 years to reach carrying-capacity biomass, with limited spillover.
- **Grey literature cited by the sources but not read:** Pergent et al. (2012, IUCN/RAC-SPA), Boudouresque et al. (2012, RAC/SPA), Mateo et al. (2019, LIFE Blue Natura), González-Correa et al. (2005, *JEMBE* 320:65–76, doi:10.1016/j.jembe.2004.12.032, metadata only).

## 10. Benchmarks: where Gaia's per-hectare values fall (Step 8.3)

The case file lists published per-hectare values (`run.benchmarks`). Every extraction report and JSON output (`"benchmarks"`) compares Gaia's figures with them (`gaia/benchmarks.py`). Values are shown in their own currency and price year, unconverted: this is an order-of-magnitude check, not a test.

Gaia's figures for the default run (50 of 4,582 ha destroyed):

| Gaia figure | €/ha/yr |
|---|---|
| Service value of one hectare at full damage, carbon excluded | 284.83 |
| … plus its carbon burial at the year-0 social cost of carbon (0.953 tCO₂ × €166.35) | 443.41 |
| What the run actually charges per hectare lost (annual externality / 50 ha) | 126.49 |

Linear benefit transfer for the 50 ha: 50 × 284.83 = €14,242/yr, against Gaia's €6,325/yr.

| Benchmark | Value | Includes | Gaia vs benchmark |
|---|---|---|---|
| Campagne et al. 2015, *P. oceanica*, carbon excluded | 277–285 €2014/ha/yr | 5 goods and benefits | within (by construction: the case's values come from it) |
| Campagne et al. 2015, carbon included | 284–514 €2014/ha/yr | + carbon at €35/t | within (Gaia with burial: 443) |
| Stamatiadou, Mazaris & Katsanevakis 2025, *Ecosystem Services* 72:101704, doi:10.1016/j.ecoser.2025.101704: Mediterranean seagrass meta-regression (ESVD-style, 17 studies, 91 observations) | basin mean 8,712 Int$2020/ha/yr; countries 1,588–95,767 | 8 services incl. recreation/tourism, climate regulation | below: the mean is ~20× Gaia |
| de Groot et al. 2012, *Ecosystem Services* 1:50–61, doi:10.1016/j.ecoser.2012.07.005 (the ESVD/TEEB database), coastal systems, as tabulated by Costanza et al. 2014 Table 4 | total of means 28,917 Int$2007/ha/yr (totals of minima–maxima 26,167–42,063) | all coastal systems, not seagrass alone | below: ~65× |
| Costanza et al. 2014, *Global Environmental Change* 26:152–158, doi:10.1016/j.gloenvcha.2014.04.002, Table 3: seagrass/algae beds | 28,916 $2007/ha/yr | 26,223 of it nutrient cycling | below: ~65× |
| Vassallo et al. 2013 (emergy, supply side) | 172 €/m²/yr = 1.72 million €/ha/yr | resources invested by nature, not willingness to pay | not comparable; not in the output |

### Reading the benchmarks

1. **Gaia sits at the bottom of the published range, and deliberately so.** It uses the one primary *P. oceanica*-specific valuation, which values five goods and benefits and leaves tourism, recreation and non-use values out. The Mediterranean meta-regression is about 20× higher. It includes recreation and tourism, and it scales with GDP per capita (Spain sits between the basin's extremes; its country value was not in the abstract read). The global syntheses are 65× higher, mostly because of a nutrient-cycling value transferred from estuaries. Applying it to a Mediterranean meadow would be a large benefit-transfer leap.
2. **The gap is in services that are not valued, not in the services that are.** For coastal protection, water purification and fisheries, Gaia uses the published Posidonia figures. A user who needs a central rather than a lower-bound estimate would need a recreation and non-use valuation for Catalan meadows. The methods note lists this as the main open data need.
3. **The damage curves charge less than a linear transfer.** At the user's scale (a few percent of the stock), each hectare lost is charged €126/ha/yr in services, 44% of its average value. The rest of the gap comes from the placeholder logistic's initial slope (0.25) and the cascades. A linear benefit transfer charges 100%. Both figures are reported, and the Monte Carlo varies the curve parameters (§3).
4. **Carbon dominates.** The one-off release costs about €126,000 per hectare at the social cost of carbon. That is roughly ten times the present value of the services the run charges per hectare: about €11,800, over 200 years with scarcity uplift, or €26,700 at the full per-hectare value. No benchmark above includes it, because they value flows only.
