# Posidonia oceanica (Catalan coast): literature review of every parameter

Step 8.2 of `TOP_PRIORITIES_REPORT.md` (revised in Step 8c with the owner's answers: the service ledger, linear pricing of small losses, the reference resource and the carbon release as inputs), for the v1.0 case `gaia/cases/data/posidonia.json` (decision D6). For each parameter of the case this review gives its value, the source, the range, how the source maps to the parameter, and the confidence recorded in the case file's provenance, which every Gaia output prints.

## How the sources were checked

- **Metadata.** Every DOI below was resolved through the Crossref API (title, authors, journal, year, volume, pages). One DOI first tried for Campagne et al. (2015), 10.1016/j.ecoser.2015.02.002, turned out to belong to a different paper (Kleisner et al. 2015); the correct one is below. **No DOI here was typed from memory.**
- **Numbers.** Each number was read from the source itself, never from a secondary summary unless stated:
  - the abstract (Crossref, OpenAlex or the publisher page);
  - the full text where it was openly available: Campagne et al. 2015, Pendleton et al. 2012, Costanza et al. 2014, the Drupp et al. working paper and arXiv paper, the IPCC Wetlands Supplement chapter 4, the US EPA SC-GHG report, and in Step 8c Börger et al. 2014, Gobert et al. 2009 and Zunino et al. 2020;
  - official documents and data: the French Label Bas-Carbone Posidonia method, the ECB exchange-rate series (USD 2020, GBP 2013), Idescat's 2021 household count, the Generalitat's fisheries statistics (open data);
  - press reports, labelled as such, for the Medes Islands' annual dives (Ràdio Capital 2026, Ara 2015);
  - in Step 8d.4, the EEA's Natura 2000 Standard Data Forms (habitat 1120\* cover per site, queried from the EEA's Natura 2000 service) and a University of Barcelona monitoring report (the Medes Islands meadow) for the meadow near dive sites;
  - in Step 8e.2, for the dive-activity intensity levels: the abstract of Betti et al. 2023 (metadata checked on Crossref), the slides of Lloret's 2006 conference talk (read, grey literature), a 2025 press interview with the director of the Cabrera National Park, and the Natura 2000 forms of four more sites (same EEA service).
- **What is flagged.** Where a value could not be checked it stays in the case and is flagged (`placeholder`, or `low` with the reason in its note). Secondary figures are labelled as such.
- **Confidence levels** follow `gaia/provenance.py`:
  - `medium`: a published value for this or a comparable system, citation checked;
  - `low`: an order of magnitude, a judgement with a stated rationale, or a source not specific to the system;
  - `placeholder`: no source.

## Summary

72 parameters are recorded for a Posidonia run with restoration (62 for an extraction). They split as follows:

| Status | Count | Parameters |
|---|---|---|
| Sourced, DOI (or arXiv id) checked | 22 | the ten agent values (the service ledger, §2); absorption, soil stock, release fraction, release half-life; substrate formation; discount rate and scarcity; planting cost; four succession parameters |
| Sourced, official URL checked | 6 | resource area (Generalitat map, as reported); the share of meadow near dive sites (EEA Natura 2000 forms, Step 8d.4); the diving intensity near dive sites (Medes dives, as reported, over the same Natura 2000 meadow, Step 8e.2); biomass carbon (Label Bas-Carbone method); carbon price and its growth (US EPA 2023, ECB rate) |
| Flagged `low`, no source | 10 | the ten dependency weights (owner specification) |
| Flagged `placeholder` | 34 | private gain per ha; safe threshold; degradation-curve steepness; keystone threshold; 15 edge strengths; 4 substrate parameters; the declining discount steps and horizon; maintenance cost and years; recovery steepness; two succession parameters; the three model-wide trophic/keystone constants |

Of the 28 sourced parameters, 11 are `medium` and 17 `low`. (With EXPERIMENTAL pricing, 3 sourced anchors and 7 derived prices are added, the latter flagged `placeholder`; §8.) They are `low` either because the source is global or a congener rather than *P. oceanica* in Catalonia, or because it is a modelling choice backed by a methodological reference.

The case remains **illustrative** by Gaia's own rule (`CalibrationStatus.status`), because placeholders remain. What changed is that every money figure and every carbon figure now has a checked source and a range. What is still unsourced is the ecological structure: the response curves, the edges and the threshold. That structure can be argued about but not looked up; Track 1 review is for exactly that.

## 1. The reference resource

| Parameter | Value | Source | Range / notes | Confidence |
|---|---|---|---|---|
| `resource.area_ha` (= `total_units`), the default reference resource | 4,582 ha | Generalitat de Catalunya, *Mapa d'hàbitats marins de Catalunya*, presented 29 May 2025 (Hipermapa). P. oceanica covers 4,582 ha, 2.4% of ~190,000 ha mapped down to 50 m. Figure as reported by Ara (29 May 2025, <https://en.ara.cat/society/from-portbou-to-alcanar-this-is-the-catalan-seabed_1_5395705.html>); 3Cat and Ecoticias give the same figures. | The whole Catalan stock. The map's breakdown by coast (how much is Costa Brava) and the dataset itself were not available to this review, and the Govern's press-release PDF returned HTTP 403. The former 5,000 ha exceeded the entire Catalan stock. | medium |
| `resource.unit_value` | €2,500/ha | none | Project-specific: the private gain per hectare destroyed. The user sets it (`--unit-value`) for the project assessed. | placeholder |
| `resource.safe_threshold_ratio` | 0.20 | none | No ecological or regulatory source supports a "safe" loss of 20% of a priority habitat (Habitats Directive 1120\*). It also sets the inflection of every damage curve (§3). | placeholder |
| run default `units` | 50 ha | none | An illustrative project size, about 1.1% of the stock; the user sets N. | — |

**The reference resource is an input (Step 8c.4).** The regional stock is the default; a user assessing one project enters the specific meadow it affects (`--area-ha N --resource-name NAME`, or the case file's `resource.total_units`/`area_ha` and `resource.name`). Both are recorded as user-supplied. Since Step 8e.3 (the owner's answer) a run with `--area-ha` must also state the diving input, `--dive-intensity` and/or `--dive-site-share` (`--dive-intensity none` if no dive site is within reach); without it the run stops with a plain error, because the regional averages describe a meadow of unknown location, not a named one. The default regional run keeps its defaults. The choice changes the depletion fraction N_destroyed / N_reference, so it matters only past the safe threshold: below it every hectare costs its average value whatever the reference (Step 8c.3, §3).

Context, not a parameter:
- **Regional decline.** Telesca et al. (2015), *Sci. Rep.* 5:12505, doi:10.1038/srep12505, map 1,224,707 ha of known *P. oceanica* and estimate a 34% regression over the last 50 years.
- **Anchoring loss rate.** The Label Bas-Carbone method takes 0.29%/yr as its default regression rate under anchoring, from Telesca et al.'s 9% for France over 1980–2011.

## 2. Agent values: the service ledger (Step 8c.2)

**Mapping.** Gaia's cost for agent *i* is damage × weight × (`annual_value_per_ha` + `site_value_per_ha` × site share) × area. `annual_value_per_ha` is the value on every hectare; `site_value_per_ha` (Step 8e.6) the value of a service enjoyed only near some sites, per hectare near them (for Posidonia only the meadow's diving amenity). Each is set to (its services per ha) / weight, which makes weight × value the sourced €/ha/yr. The owner's weights keep their role in the health index.

**The owner's rule (Step 8c.2).** Every agent must cost money, and double counting must still be avoided rigorously. Ecosystem-service accounting values a benefit once, where people receive it: the **final** services (Boyd & Banzhaf 2007, *Ecological Economics* 63:616–626, doi:10.1016/j.ecolecon.2007.01.002; Fisher, Turner & Morling 2009, *Ecological Economics* 68:643–653, doi:10.1016/j.ecolecon.2008.09.014). The case file therefore carries an explicit **service ledger** (`service_ledger`):
- each final service appears **exactly once**, with its €/ha/yr, its method, its source and its benefit-transfer method;
- each service is assigned to **exactly one** agent: the one that is its best owner;
- where an agent is intermediate and has no final service of its own, it gets a **sourced share of a final service moved from another agent**. The total is unchanged, and the split and its source are recorded (`split_of`, `share`, `share_source`);
- where a value overlaps services counted elsewhere, it is booked **net of them** (Step 8e.6): `gross`, `net_of` (the entries it would count again) and value = gross − their values. The meadow's food production (§2b) is net of the commercial catch booked to Fish Populations and Marine Invertebrates, which keep their own entries.

Parsing rejects a service listed twice, a service also counted through its shares, shares adding up to more than 1, a value ≤ 0, a net value that is not gross minus the services it is net of, and an agent that owns no service applying on every hectare. A test checks the shipped case: no service counted twice, every agent's value > 0, and each agent's weight × value equal to the sum of its ledger entries (`Case.ledger_check()`).

**No agent at €0, a hard invariant (Step 8e.7; PROJECT_DEFINITION.md, Core Valuation Principles (b)).** Every agent's value on every hectare (`annual_value_per_ha`) must be > 0, and so must the low end of its Monte Carlo range: `gaia.validation.validate_ecosystem` and case parsing reject anything else, citing the rule. No input scales that part (`--dive-intensity` and `--dive-site-share` scale only `site_value_per_ha`), so no preset, flag or draw can bring an agent to €0. `tests/test_valuation_principles.py` builds every case under every combination of presets and flags (site share, dive intensity, matte fate, reference area, threshold, pricing), plus 200 seeded random combinations, and checks that every agent carries a value > 0 and costs > 0 once a unit is lost.

**The seascape rule.** Some services belong to the wider seascape rather than to the meadow hectare itself: diving on coralligenous reefs, and the non-use values of mobile species. Their regional value is spread evenly over the **mapped Catalan seabed to 50 m, ~190,000 ha** (the Generalitat's 2025 map, §1), so a meadow hectare carries the average seascape share. This is an attribution assumption, not a source: no study links these services to a hectare of meadow, and meadows are probably above average. **The owner accepted it as a provisional assumption (Step 8d.3)**, so it is no longer an open question; it is labelled PROVISIONAL in the provenance of the three agents and in their ledger entries, and would be replaced by an area-weighted link to nearby reefs if one could be sourced. Services of the meadow itself are spread over the meadow area (4,582 ha).

**The ledger** (€/ha/yr at full damage; carbon excluded, §4):

| Agent | Final service | €/ha/yr | Method | Source | Transfer | Confidence |
|---|---|---|---|---|---|---|
| Coastal Protection | Protection from coastal erosion (wave attenuation, banquettes, matte) | 188.00 | damage cost avoided | Campagne et al. 2015, Table 2 | French Mediterranean → Catalonia, unit value, € 2014 | medium |
| Water Quality | Water purification (wastewater treatment) | 60.00 | benefit transfer of the French water-protection tax (⅓ to coastal systems) | Campagne et al. 2015, Table 2 | as above | medium |
| Fish Populations | Commercial fisheries: meadow-associated fish | 30.625 | production function at auction prices; **14/16 of 35** | Campagne et al. 2015, Table 2 and §3.2.4 | as above | medium |
| Marine Invertebrates | Commercial fisheries: meadow-associated invertebrates (sea urchin *Paracentrotus lividus*, cuttlefish *Sepia officinalis*) | 4.375 | **2/16 of 35**, moved from Fish Populations | Campagne et al. 2015 §3.2.4: 2 of the 16 species sold | as above; share by species count (assumption) | low |
| Human Communities | Bioindicator use: shoot, leaf and lower-limit metrics | 1.286 | market prices (monitoring); **3/3.5 of 1.5** | Campagne et al. 2015; Gobert et al. 2009 | as above | medium |
| Epiphytes & Algae | Bioindicator use: epiphyte metric (E/L ratio) | 0.214 | **0.5/3.5 of 1.5**, moved from Human Communities | Gobert et al. (2009), *Mar. Pollut. Bull.* 58:1727–1733, doi:10.1016/j.marpolbul.2009.06.012 (full text): PREI EQR′ = (N density + N leaf surface + N(E/L) + N lower limit)/3.5, with N(E/L) = [1 − E/L] × 0.5 | as above | low |
| Human Communities | Knowledge contribution (research funding) | 0.33 | market prices (EU LIFE funding per ha) | Campagne et al. 2015, Table 2 | EU average → Catalonia | medium |
| Posidonia Meadow | **Food from primary production** (Step 8e.6): the fish and invertebrates its production supports, **net of the commercial catch** above (`net_of`), on every hectare | **249.74** (284.74 gross − 35.00) | production function: net primary production → food web → trophic transfer → sustainable catch → first-sale price (§2b) | Pergent et al. 1994; Duarte 1990; Mateo & Romero 1997; Coll et al. 2008; Francour 1997 with FishBase; Pauly & Christensen 1995; Zhou et al. 2012; Generalitat fisheries statistics (§2b) | Mediterranean and global trophic parameters → Catalonia; Catalan prices, € 2014 | low |
| Posidonia Meadow | Recreational diving: the meadow's amenity **near dive sites** (Step 8d.4) | 454.52 at the regional share (14,630.14 per ha near dive sites × 0.0311) | choice experiment: €34.71 per dive for a total loss of *P. oceanica* cover × 60,000 Medes Islands dives/yr ÷ **142.35 ha of meadow within reach of dive sites**, × the share of the affected meadow near dive sites | Zunino et al. (2020), *Front. Mar. Sci.* 6:823, doi:10.3389/fmars.2019.00823 (abstract and full text, Table 3); dives: Ràdio Capital (26 May 2026, the Parc Natural / SUBMON study: "prop de 60.000 immersions anuals"), cap raised from 60,000 to ~77,000 in 2015 (Ara, 19 June 2015) | Italian divers → Medes dives, unit value, no income adjustment, € 2016–17 | low |
| Coralligenous & Red Coral | Recreational diving: coralligenous seascape | 18.95 | choice experiment: €60 per dive for the local extinction of gorgonians × 60,000 dives ÷ 190,000 ha (seascape rule) | Rodrigues et al. (2016), *Environ. Resource Econ.* 63:289–311, doi:10.1007/s10640-015-9935-8 (abstract, UAB research portal) | none for the value (Catalan, Medes Islands); seascape attribution (assumption) | low |
| Marine Megafauna | Non-use: protection of marine megafauna | 30.18 | choice experiment: UK households pay £30.32/yr for 5 years to protect porpoises, seals and seabirds on 50% of the Dogger Bank, annualised at 2.3% (£3.26/yr), at 0.84926 £/€ (€3.84), × 2,989,357 Catalan households ÷ 190,000 ha, **half** of the bundled attribute | Börger et al. (2014), *Ecol. Econ.* 108:229–241, doi:10.1016/j.ecolecon.2014.10.006 (full text, open access); households: Idescat, *Households by size* 2021 (INE census); ECB 2013 average rate | UK → Catalonia, unit value, no income adjustment; a 50%-protection scenario read as the value at full damage (lower in scope) | low |
| Seabirds | Non-use: protection of seabirds | 30.18 | the other half of the same attribute | as above | as above | low |
| **Total** | | **1,068.40** | | | | |

The total was €284.83/ha/yr before Step 8c.2, when only Campagne et al.'s services carried euros, and €818.66 before Step 8e.6 added the meadow's food production.

**Notes on each choice:**
- **Splits (total unchanged).**
  - The fisheries contribution (35 €/ha/yr) is split 14/16 fish, 2/16 invertebrates. That is the species count of Campagne et al.'s list of meadow-associated species sold at the Sète auction. Equal value per species is an assumption. The upper end of the invertebrates' range, 25.4%, is the cephalopod and other-invertebrate share of Catalan white-fish, cephalopod and other-invertebrate first-sale value in 2014 (Generalitat open data, *Estadístiques de pesca per grups biològics*, dataset ge3m-4jgm: €13.65 M + €0.34 M against €41.06 M). It is a proxy, not specific to the meadow.
  - The bioindicator value (1.5 €/ha/yr) is split by the PREI's own weights. The epiphyte/leaf biomass metric carries at most 0.5 of 3.5.
- **The meadow's own services.** The meadow is the keystone, but its regulating services are already booked under Coastal Protection and Water Quality, and the commercial catch it supports under the fish and invertebrates. It has two final services of its own. The first, on every hectare, is the **food its primary production supports beyond that commercial catch** (Step 8e.6, §2b). The second is the underwater amenity, which Campagne et al. list as unvalued ("Visit of *P. oceanica* meadows: snorkelling and submarine vision boat"), only near dive sites. Two caveats on the amenity:
  - Every Medes dive is assumed to include meadow, which biases the value up.
  - Dives at the other Costa Brava sites are not counted: no annual count was found for Cap de Creus or any other site, which biases the value down.

  The range is 214–1,294 €/ha/yr at the regional share (6,874–41,651 per ha near dive sites): €18.12/dive (the 50%-loss value, i.e. half the dives over meadow) × 54,000 dives, to €77/dive (latent class 1) × 77,000 dives.
- **Only near dive sites (Step 8d.4, the owner's decision).** Until Step 8d the diving value was spread over the whole Catalan stock, as if every hectare were dived. It now applies only to meadow within reach of dive sites:
  - **The meadow within reach of dive sites: 142.35 ha** (flagged as a proxy, `low`). It is the *P. oceanica* (habitat 1120\*) cover recorded in the Natura 2000 Standard Data Forms of the five coastal sites of the Costa Brava, which hold its best-known dive sites: Cap de Creus (ES5120007) 64.14 ha, El Montgrí–Les Medes–El Baix Ter (ES5120016) 10.75 ha, Litoral del Baix Empordà (ES5120015) 24.10 ha, Massís de les Cadiretes (ES5120013) 42.36 ha, L'Albera (ES5120014) 1.00 ha. Source: European Environment Agency, Natura 2000 forms last updated December 2014, read from the EEA's Natura 2000 service (<https://bio.discomap.eea.europa.eu/arcgis/rest/services/Bio/Natura2000_Dyna_WM/MapServer/13>; site pages <https://natura2000.eea.europa.eu/Natura2000/SDF.aspx?site=ES5120007> etc.), queried 12 October 2026. Cross-check: the meadow of the Medes Islands alone covers 8.8 ha (Romero, Pérez & Renom 2001, *Seguimiento de la pradera de Posidonia oceanica de las islas Medes. Ejercicio 2001*, Universitat de Barcelona, <http://hdl.handle.net/2445/25506>, read), consistent with the 10.75 ha of the Montgrí–Medes site. Why it is a proxy: a site boundary is not the reach of a dive site; dive sites other than the Medes Islands and Cap de Creus are assumed, not verified, to lie in these sites; and the 2014 forms and the 2025 regional map (4,582 ha) differ in date and method. No park or official figure for "meadow within reach of dive sites" was found.
  - **Dives divided over that area**: €34.71 × 60,000 ÷ 142.35 ha = **€14,630 per hectare of meadow near dive sites per year**.
  - **A project input**, `--dive-site-share F` (`site_share` in the case file, recorded as user-supplied): the share of the affected meadow within reach of dive sites. 1 for a project at a dive site, 0 far from any. The default is the regional share, 142.35 / 4,582 = 0.0311, the expected share for a meadow of unknown location; it gives back exactly the former regional average (454.52 €/ha/yr), so the default run does not change.
  - The Monte Carlo samples the near-site value (its range above) and holds the share fixed: for the regional default the uncertainty of the 142.35 ha cancels out; for a project at a dive site it does not and is not inside the bounds (a stated limitation).
  - **No double counting.** The meadow's diving value and the coralligenous diving value stay different attributes of the same dives (next point); the coralligenous value keeps the provisional seascape rule. Restricting one entry moves no value to any other agent, and every agent stays > 0 at any share above 0 (tests).
- **Dive-activity intensity (Step 8e.2, the owner's answer).** The near-site value above is stated at the Costa Brava's average diving intensity: 60,000 Medes dives ÷ 142.35 ha = **421.5 dives per hectare of meadow near dive sites per year** (`site_intensity`, recorded with its sources, `low`, held fixed in the Monte Carlo). A project states how much its meadow is dived with `--dive-intensity {none,low,medium,high}` (`site_intensity_levels`). Each level is the annual dives of a real Mediterranean dive area divided by the *P. oceanica* (habitat 1120) cover of the Natura 2000 site that contains it, the same method as the default:

  | Level | Reference site | Dives a year | Meadow (Natura 2000 site, EEA form) | Dives/ha/yr | €/ha/yr near dive sites (× €34.71) | Source of the dives, confidence |
  |---|---|---|---|---|---|---|
  | `none` | no dive site within reach | 0 | — | 0 | 0 | by definition |
  | `low` | Banyuls-Cerbère marine reserve and the Côte Vermeille (France) | 14,000 (24 dive centres) | 211.45 ha, FR9101482 *Posidonies de la côte des Albères* | 66.2 | 2,298 | Lloret (2006), *Recerca i gestió a dos espais costaners i marins fronterers: Cervera-Banyuls i Cap de Creus*, conference slides, Institució Catalana d'Història Natural, slide 10 (<https://ichn.iec.cat/wp-content/uploads/2024/01/ponencia-J_Lloret-cap-de-Creus-ICHN-2006.pdf>, read). **Grey literature, `low`** |
  | `medium` | Portofino MPA (Liguria), "one of the main scuba diving destinations in Europe" | up to 40,000 | 70.61 ha, IT1332674 *Fondali Monte Portofino* | 566.5 | 19,663 | Betti et al. (2023), *Aquatic Conservation* 33(2):191–201, doi:10.1002/aqc.3918 (abstract: "up to 40,000 dives per year concentrated along 6.5 km of coast"; metadata checked on Crossref). `low`: "up to" makes it an upper figure, and a transfer from Liguria |
  | default | Costa Brava average | 60,000 (Medes only) | 142.35 ha, five Costa Brava sites | 421.5 | 14,630 | as §2 above (press report of the park's study); `low` |
  | `high` | Medes Islands (L'Estartit) | about 60,000 | 10.75 ha, ES5120016 *El Montgrí-Les Medes-El Baix Ter* | 5,581 | 193,730 | press report of the Parc Natural / SUBMON study (as above); `low`. Over the 8.8 ha Medes meadow of Romero et al. (2001): 6,818 |

  Cross-checks, not used as levels: Cap de Creus, 70,000 dives a year from 20 centres (Lloret 2006, same slide) over 64.14 ha (ES5120007) = 1,091 dives/ha/yr, between `medium` and `high`; the Cabrera National Park (Balearic Islands), 2,500 divers under 230 diving permits in the park's latest figures (dives not reported; the park's director, interviewed in *Menorca – Es Diari*, 7 December 2025, <https://www.menorca.info/balears/noticias/2025/12/07/2524879/evolucion-cabrera-sido-positiva-todos-ecosistemas.html>, read) over 5,154.86 ha (ES0000083): about 0.5 divers per hectare a year, far below `low`, a strictly limited national park. The levels are roughly a factor of 9 apart (66, 566, 5,581), and the default lies between `low` and `medium`. No carrying-capacity study giving dives per hectare of meadow for a Mediterranean MPA was found; no annual dive count was found for Port-Cros either.

  **How intensity and share combine.** Intensity sets the value per hectare of meadow near the dive sites (€34.71 × dives/ha/yr); the share (`--dive-site-share`) says what part of the affected meadow lies near them. The meadow's value per hectare of the affected meadow is €34.71 × intensity × share. Without either input the run uses the regional average intensity and the regional share, which gives back exactly the former 454.52 €/ha/yr: **the default run does not change**. With `--dive-intensity` alone the share is 1 (the intensity describes the affected meadow as a whole); with `--dive-site-share` alone the intensity is the regional average (as since Step 8d.4). The intensity is a density: a site's dives are spread over its meadow, so `high` fits only a small meadow at a heavily dived site (the Medes meadow is 10.75 ha); a project that destroys 50 ha of which 5 ha lie at such a site should give `--dive-intensity high --dive-site-share 0.1`, not `high` alone.

  **`none` zeroes the diving service, never an agent.** With `none` (or `--dive-site-share 0`) the meadow keeps its own value on every hectare, the food its primary production supports (€249.74/ha/yr, §2b), and every other agent keeps its value. Before Step 8e.6 the diving service was the meadow's only ledger entry, so `none` left the meadow agent at €0; that was flagged as an exception, and the owner rejected it: no agent may ever be at €0 (PROJECT_DEFINITION.md, Core Valuation Principles).

  **Uncertainty.** The level is a project input, recorded as user-supplied with its basis and held fixed; the Monte Carlo keeps the meadow value's own relative range (×0.47 to ×2.85 of the documented value, from the per-dive WTP and the dive counts) at any level. The uncertainty of each level's dive count and meadow area is not inside the bounds (as for the 142.35 ha).
- **Two diving values, one dive.** The meadow's value (Zunino et al.) and the coralligenous's value (Rodrigues et al.) are different attributes of the same dives. Zunino et al.'s own model estimates both habitats as separate, additive attributes (coralligenous total loss −€108, *P. oceanica* −€34). Adding a Catalan coralligenous value to an Italian meadow value assumes the same additivity across studies.
- **Non-use values.** These are the weakest entries: a transfer from a North Sea study, a protection scenario read as the value of the species, an equal split of a bundled attribute, and the seascape attribution. They are flagged `low`, with a ×0.33–×3 range. Börger et al.'s 25%-protection value (£24.02) gives 23.9 €/ha/yr each.
- **Benefit transfer: no income or price-year adjustment (a known limitation, Step 8d.5).** Every value above is transferred as a unit value at face value: willingness to pay from French, Italian and UK populations is not scaled to Catalan income per head (no income elasticity), and values stay in their own price year (€ 2014–2017, £ 2013 converted at the 2013 rate) without inflation to a common year. The owner decided not to adjust for now; it is recorded as a limitation (methods note §8) and is not inside the Monte Carlo ranges.
- **Still not valued:**
  - beach tourism (the meadow's role in keeping beaches and clear water for tourists);
  - the meadow's own non-use (existence) value (no usable willingness-to-pay study found, §2b);
  - recreational fishing as welfare;
  - the non-use value of the coralligenous.

  The ledger total therefore remains a lower bound, though a much smaller gap than before (§10).

**Searched for but not used:**
- **A willingness-to-pay value for the meadow's existence** (Step 8e.6, after the production function, as the owner asked). None usable was found. Gatt, Deidun & Briguglio (2024), *Quantifying the economic value of marine ecosystems: a preliminary valuation from the Maltese Islands*, BEING SEA-EU abstract booklet, University of Malta, p. 296 (abstract read at <https://um.edu.mt/library/oar/handle/123456789/126984>): a contingent valuation of 11 Maltese coastal sites in which *P. oceanica* "generated higher values" than sandbanks and caves, but the abstract gives no figures, per visit or per hectare. Zunino et al. (2020) value divers' use, already in the ledger. Searches of Spanish, Balearic, French, Italian, Greek, Maltese and Croatian work found no household non-use value for the meadow; a review of marine valuations notes that non-use values remain the least estimated (Pacifico, Mulazzani & Malorgio 2025, *Front. Mar. Sci.* 11:1501812, doi:10.3389/fmars.2024.1501812, read). No transfer from a non-Mediterranean seagrass non-use study was made: none with a household figure was found and read in this step.
- **Recreational fisheries.** Jackson et al. (2015), *Conservation Biology* 29:899–909, doi:10.1111/cobi.12436, attribute €112 million/yr of Mediterranean recreational-fisheries **expenditure** to seagrass. Expenditure is not a welfare measure.
- **A Mediterranean or Catalan stated-preference value for megafauna, seabirds or the meadow's existence.** Only pilot or per-visit studies were found: Stithou & Scarpa (2012) on Zakynthos (loggerhead turtle and monk seal, per visit), and Kontogianni et al. (2012) on Lesvos (monk seal, payment frequency unknown). Both are reported in Lew (2015), *Front. Mar. Sci.* 2:96, doi:10.3389/fmars.2015.00096. Ressurreição et al. (2011, doi:10.1016/j.ecolecon.2010.11.009; 2012, doi:10.1016/j.biocon.2011.10.026) value species loss by taxon in the Azores and two other European seas; their WTP figures could not be read (no abstract or open full text reachable).
- **The per-service breakdown of the Mediterranean meta-regression** (Stamatiadou et al. 2025). The article was not accessible beyond its abstract.
- **Emergy (supply-side) values.** Vassallo et al. (2013), *Mar. Pollut. Bull.* 75:157–167, doi:10.1016/j.marpolbul.2013.07.044 (172 €/m²/yr as quoted by Campagne et al., 99% of it sediment retention), and Rigo et al. (2021), *Diversity* 13:499, doi:10.3390/d13100499. They measure what nature invests, not what people would pay, so they are kept as a benchmark only (§10).

## 2b. The meadow's own value: primary production → food → € (Step 8e.6)

**Why.** The owner's rule: every agent carries a positive value under any input, and, where no willingness-to-pay evidence exists, value is derived from what people consume (PROJECT_DEFINITION.md, Core Valuation Principles (b), (d)). The meadow is a foundation species of very high productivity; its production feeds a food web that ends in fish and invertebrates people eat. This **production function** values that food at Catalan first-sale prices. It applies to **every hectare** of meadow, whether or not anyone dives there.

**The chain** (`service_ledger`, `production_function`, computed by `gaia/production.py`; parsing checks that the chain gives the entry's gross value):

| Link | Value (range) | Result | Source | Status |
|---|---|---|---|---|
| Net primary production of the plant: leaf blades, sheaths, rhizomes | 476 (238–714) g DW/m²/yr | 476 g DW/m²/yr | Pergent, Romero, Pergent-Martini, Mateo & Boudouresque (1994), *Mar. Ecol. Prog. Ser.* 106:139–146, doi:10.3354/meps106139 (abstract): blades 167–530, sheaths 51–142, rhizomes 20–42 g DW/m²/yr, Ischia; value = sum of the midpoints | verified (abstract) |
| Carbon content of dry weight | 33.6% | 159.9 g C/m²/yr | Duarte (1990), *Mar. Ecol. Prog. Ser.* 67:201–207, doi:10.3354/meps067201 (abstract): seagrass leaves 33.6 ± 0.31% C | verified (abstract) |
| Share eaten, decomposed or exported (not buried in the matte) | 74% (71–83.2%) | 1,183.5 kg C/ha/yr | Mateo & Romero (1997), *Mar. Ecol. Prog. Ser.* 151:43–53, doi:10.3354/meps151043 (abstract): 26% buried, **Medes Islands**; range: Pergent et al. 1994 (29% buried); Cebrián, Duarte, Marbà & Enríquez (1997), *Mar. Ecol. Prog. Ser.* 155:29–44, doi:10.3354/meps155029 (abstract): 16.8% neither consumed nor decomposed in the first year, **Cala Jonquet, Cap de Creus** | verified (abstracts) |
| Trophic transfer efficiency per level | 11.8% (10–14.25%) | | Coll, Libralato, Tudela, Palomera & Pranovi (2008), *PLoS ONE* 3:e3881, doi:10.1371/journal.pone.0003881 (full text): median of a compilation of ecosystem models 11.8%; temperate models mean 14.25%; 10% nominal | verified (full text) |
| Mean trophic level of the catch | 3.1 (3.1–3.5) | 13.3 kg C/ha/yr of consumer production | Francour (1997), *Marine Ecology* 18:157–173, doi:10.1111/j.1439-0485.1997.tb00434.x (abstract): Port-Cros meadow fish dominated by *Symphodus ocellatus*, *S. tinca*, *Diplodus annularis*, *Sarpa salpa*; FishBase trophic levels 3.5, 3.3, 3.6, 2.0 (mean 3.1); 3.5 = median of 13 meadow species with the main targets | derived (species choice a judgement) |
| Wet weight per unit of carbon | ×9 | 119.8 kg/ha/yr of fish and invertebrates produced | Pauly & Christensen (1995), *Nature* 374:255–257, doi:10.1038/374255a0, as cited by Chen et al. (2022), *Front. Mar. Sci.* 9:863611, doi:10.3389/fmars.2022.863611 | **secondary** (primary not read) |
| Share caught sustainably (exploitation rate at MSY) | 46.5% (42.5–50%) | 55.7 kg/ha/yr | Zhou, Yin, Thorson, Smith & Fuller (2012), *Can. J. Fish. Aquat. Sci.* 69:1292–1301, doi:10.1139/f2012-060 (abstract): F_MSY = 0.87 M for teleosts; E = F/(F + M) = 0.465 | derived; that catch = E × production is the steady-state relation, **inferred** |
| First-sale price, Catalan bony white fish, 2014 | €5.11/kg | **€284.74/ha/yr gross** | Generalitat de Catalunya, *Estadístiques de pesca per grups biològics* (open data ge3m-4jgm, queried): €41,056,589 for 8,034,993 kg | verified (queried) |
| minus the commercial catch already in the ledger | −€35.00 | **€249.74/ha/yr** | Fish Populations 30.625 + Marine Invertebrates 4.375 (Campagne et al. 2015) | — |

Over the ends of every link's range the gross value runs from €35.10 to €766.98/ha/yr, the net from €0.10 to €731.98 (the Monte Carlo range of the meadow's value on every hectare). The low end, with every link at its least favourable value, is about the commercial catch already counted, as it should be if Campagne et al.'s catch were all the meadow supports.

**What it includes, and what it leaves out.** The gross value is every fish and invertebrate the meadow's own production can sustain at a sustainable catch, whoever catches it and wherever: commercial, artisanal and recreational fishers, and fish that grow up in the meadow and are caught elsewhere (the nursery spillover). The prey in between (small invertebrates, non-commercial fish) are the trophic steps, not valued again. It is conservative in three ways: roots and the epiphytes' own production are left out (no verified figure was read), the catch is valued at first-sale, not retail, prices, and only the sustainable share of production is valued.

**No double counting.**
- *Commercial fisheries*: the meadow's value is net of the €35 booked to Fish Populations and Marine Invertebrates (`net_of`; parsing enforces value = gross − €35). Those agents keep their entries.
- *Carbon*: the chain uses only the production that is not buried; the buried part is what `gaia.carbon` values (decision D3, single owner of carbon).
- *Coastal protection*: it values the physical role of the leaves and banquettes on the beach, not their food value. The exported leaves feed beach and deep-water food webs and protect the shore at the same time; these are joint products of the same biomass, not one benefit counted twice.
- *Diving and non-use values*: they are not consumption.

**Carbon shown, not added.** The text report prints the matte's carbon stock (1,199 tCO2/ha) and burial (0.95 tCO2/ha/yr) on the meadow's line, as an attribution to the foundation species (`carbon_attribution`). The euros stay in the Carbon Accounting section and are counted once (decision D3).

**Productivity, compared.** Gross primary production of whole communities, g C/m²/yr, the measure that is comparable across sources:

| Ecosystem | GPP | Source |
|---|---|---|
| *P. oceanica* meadow, Corsica, 12-year mean | 997 | Champenois & Borges (2021), *Limnol. Oceanogr.* 66:2126–2140, doi:10.1002/lno.11724 (abstract): 83 ± 16 mol O2/m²/yr, at a photosynthetic quotient of 1 (as Koopmans et al. 2020, *Front. Mar. Sci.* 7:118, doi:10.3389/fmars.2020.00118) |
| Seagrass meadows, global average | 1,903 | Duarte, Middelburg & Caraco (2005), *Biogeosciences* 2:1–8, doi:10.5194/bg-2-1-2005, Table 3 (full text) |
| Coral reefs | 1,720 | same, from Gattuso et al. 1998 |
| Mangroves / salt marshes / macroalgal beds | 2,087 / 3,595 / 3,702 | same |
| Lowland moist tropical forest | 3,000–4,000 | Malhi (2012), *J. Ecol.* 100:65–75, doi:10.1111/j.1365-2745.2011.01916.x (abstract) |
| Intensive cropland (irrigated wheat–maize, two crops a year, North China Plain) | 2,182 | Zhang et al. (2020), *Biogeosciences* 17:2245–2262, doi:10.5194/bg-17-2245-2020 (abstract) |
| Unvegetated coastal sediments | 67.9 | Duarte et al. (2005), Table 3 |

Per hectare, seagrass meadows fix carbon on the scale of coral reefs and intensively farmed land; the Corsican *P. oceanica* meadow fixes about half the seagrass average and 15 times the bare sediment around it. The chain starts from the plant's net production alone (160 g C/m²/yr), which is not comparable with these community figures.

**Not reached.** The Catalan production figures of Cebrián et al. (1997, Cala Jonquet) and the Port-Cros Ecopath models (Valls et al. 2012, doi:10.3354/meps09701; Prato et al. 2014, doi:10.3354/meps10988), which would give a *P. oceanica*-specific transfer efficiency, are behind bot checks on the publisher and repository sites; only their abstracts were read.

## 3. Damage curves, health weights, cascade network

| Parameter | Value | Source | Notes | Confidence |
|---|---|---|---|---|
| `agent[*].dependency_weight` (10) | 0.044–0.154, sum 1 | owner specification (weights / 0.91 after the Blue Carbon agent was removed) | Health shares. They also scale each agent's euros, but weight × value is fixed to the sourced service value, so the euros do not depend on them. Held fixed in the Monte Carlo. | low |
| `damage.threshold_logistic_steepness` | 12 | none | Since Step 8c.3 the degradation of the remaining meadow past the threshold: zero up to it, then a logistic with its inflection at 32% loss, the same for all ten agents. **No Posidonia study relates the fraction of meadow lost to the degradation of the rest**: the curve cannot be fitted (calibration regime B). | placeholder |
| `agent[Posidonia Meadow].keystone_threshold` | 0.3 (health) | none | Below it the meadow's outgoing edges double. | placeholder |
| 15 `edge[…].strength` | 0.15–0.40 | none | Several links are documented qualitatively: meadow → wave attenuation (Infantes et al. 2012); seagrass → fisheries via juvenile residency (Jackson et al. 2015); meadow loss → carbon erosion in exposed shallow areas (Salinas et al. 2020). Their strengths are not. | placeholder |
| trophic levels | 0–3 | structural choice (consumers: invertebrates 1, fish and seabirds 2, megafauna 3) | Model-wide constants: transfer efficiency 0.15 and amplification exponent 0.25 (placeholders in `gaia/constants.py`). Lindeman (1942), *Ecology* 23:399–417, doi:10.2307/1930126, and Pauly & Christensen (1995), *Nature* 374:255–257, doi:10.1038/374255a0, are the classic references for trophic transfer; their metadata were checked, but no transfer-efficiency figure was read from them for this review. | placeholder |

**Small losses are priced linearly (Step 8c.3, the owner's decision).** Until Step 8c the normalised logistic started with a slope of about 0.25, so each hectare destroyed cost about a quarter of its average per-hectare value before cascades (44% with them). The case now uses the `area_loss` damage model: an agent's damage at depletion D is D + (1 − D) × degradation(D). The hectares lost take their own services, which is a linear benefit transfer (Campagne et al.'s method and that of most impact assessments). The curve, trophic amplification and cascades describe the degradation of the meadow that remains. The curve is zero up to the safe threshold, so:
- below the threshold, a project's annual externality is exactly hectares × the per-hectare total of the service ledger (§2), whatever the reference resource and the curve parameters;
- above it, the remaining meadow degrades: the hectares just past the threshold cost 3–4 times their average value, and the response saturates once little is left.

The parametrisation was chosen because it is the cleanest one that gives a slope of exactly 1 and keeps the former threshold and steepness parameters (and their Monte Carlo ranges) with the same meaning. A logistic with its tangent removed would have to be renormalised and can leave [0, 1]. A Hill curve would add a new parameter. It is declared per case (`damage_model` in the case file); since Step 8d.1 (the owner's answer) the three other cases use it too, Costa Brava's fire agent with a `threshold_exponential` curve, and none of the four shipped cases issues a CalibrationWarning any more.

**CalibrationWarning: resolved by the model, explained.** Under `area_loss` the health at the threshold t is at most 1 − t by construction, so the warning now checks the health of the remaining meadow at the threshold, which is 1.0. The 20% threshold is still unsourced: it now marks where the remaining meadow starts to degrade, and a 20% loss still costs 20% of the services.

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
| `carbon.release_half_life_years` | 10 yr | Pendleton et al. (2012), as above (full text): at a converted site the release "likely follows a negative exponential curve with time", with "a half-life on the order of 5–10 years" (their ref. 29, a cleared mangrove) | 0–27 yr: see "Release over time" below. A project input (`--carbon-release-half-life`); 0 for excavated matte. | low |
| `carbon.stored_carbon_tonnes` (living biomass) | 0 | Label Bas-Carbone method (below), §7: the carbon in the leaves is "négligeable comparé au carbone stocké et séquestré dans la matte" | Living rhizomes and roots lie inside the top-metre matte stock, so a separate biomass term would double count. No *P. oceanica* leaf-biomass carbon figure was checked. | low |

**Label Bas-Carbone method.** Ministère de la Transition écologique, *Méthode de protection des herbiers de posidonie éligibles pour l'obtention du Label Bas-Carbone*, approved by decision of 21 March 2023 (NOR ENER2305073S), <https://aida.ineris.fr/sites/aida/files/2023-04/Dec20230321_1.pdf> (read). The method is described in Comte et al. (2024), *Mar. Pollut. Bull.* 198:115822, doi:10.1016/j.marpolbul.2023.115822.

**Release per hectare destroyed:** 1,199 × 0.63 = 755 tCO₂ (formerly 260). At the social cost of carbon (€166/t) that would be about €126,000 per hectare if all of it were released at once; released with a 10-year half-life it is €111,000 in PV. It is the largest single term of the externality, and its release fraction is the least certain input. The Monte Carlo confirms both points.

### Release over time versus re-absorption (Step 8c.5)

The owner asked how much carbon is released per unit time after the meadow and its matte are lost, how much is re-absorbed as the meadow recolonises, and which defaults to use. Both the release fraction and its time profile are now **project inputs** (`--carbon-release-fraction`, `--carbon-release-half-life`). They are recorded as user-supplied and held fixed in the Monte Carlo.

**Release per unit time. Sourced:**
- **Excavated or dredged matte.** The IPCC (2013) Wetlands Supplement, ch. 4 (read), treats "excavation to enable port, harbour and marina construction" as extraction: the top-metre soil carbon is emitted in the year of extraction, minus 4% refractory.
- **Exposed matte, general.** Pendleton et al. (2012, full text) expect a negative exponential release with "a half-life on the order of 5–10 years". That figure comes from mangroves (their ref. 29), not seagrass.
- **Exposed matte, seagrass evidence:**
  - Arias-Ortiz et al. (2018), *Nature Climate Change* 8:338–344, doi:10.1038/s41558-018-0096-y (abstract, institutional repository): after the 2010/11 heatwave damaged 36% of Shark Bay's seagrass, "between 2 and 9 Tg CO₂ could have been released to the atmosphere during the following three years". They assumed 10–50% of the soil stock was exposed to oxic conditions.
  - Macreadie et al. (2015), *Proc. R. Soc. B* 282:20151537, doi:10.1098/rspb.2015.1537 (abstract): soil carbon stocks were 72% lower in a seagrass ecosystem disturbed 50 years earlier.
  - Serrano et al. (2016), *Sci. Rep.* 6:23193, doi:10.1038/srep23193 (abstract): 4.8 of 6.4 kg Corg/m² in the top 50 cm were lost under moorings deployed from the 1930s (*Posidonia* spp., Western Australia).
  - Marbà et al. (2015), *J. Ecol.* 103:296–302, doi:10.1111/1365-2745.12370 (abstract): the upper sediments eroded where vegetation did not return after loss.
  - Salinas et al. (2020) found the erosion in shallow, exposed areas only (§4 table).
  - The Label Bas-Carbone method takes 10.7% of the top metre over 10 years for anchoring damage, which is a partial loss.

**Re-absorption over time. Sourced:**
- Burial needs the meadow. Marbà et al. (2015) found sediment accumulation coincided with the presence of vegetation. After replanting *P. australis*, burial rates rose with the age of the restored sites and "18 years after planting … were similar to that in continuously vegetated meadows (26.4 ± 0.8 gCorg m⁻² year⁻¹)".
- Macreadie et al. (2015): areas that recovered from disturbance held 35% less carbon than undisturbed ones, but more than twice as much as disturbed ones.
- *P. oceanica* recolonises naturally over centuries: limited cover after 100 years (Kendrick et al. 2005, §6).

**Inferred here, not sourced:**
- The 10-year default half-life. It is the upper end of Pendleton et al.'s order of magnitude, consistent with the three-year release at Shark Bay.
- The upper end of the range, 27 years. It is the half-life that would leave 28% of the stock after 50 years (Macreadie et al.), so a bound only if the decay were exponential.
- Buried matte. No source gives a release fraction for matte covered by fill; anoxic burial probably preserves much of it.
- Re-absorption on the footprint. A port or marina footprint is a permanent conversion, so nothing is re-absorbed there.
- Re-absorption around the footprint under natural recolonisation. With the case's succession curve, re-absorption would recover about 8% of the PV of the foregone burial (€1,600 of €19,000 per hectare at the SCC). That is about 1.5% of the release's PV, so the extraction view keeps the foregone burial permanent. Replanting is the restoration mode's question.

**Recommended inputs:**

| What the project does to the matte | `--carbon-release-fraction` | `--carbon-release-half-life` | Re-absorption | Basis |
|---|---|---|---|---|
| Excavated or dredged (basins, channels) | 0.96 | 0 | none on the footprint | IPCC 2013 (sourced) |
| Left exposed in place (meadow killed by shading, turbidity, anchoring, scour) | 0.63 (range 0.25–1.0) | 10 yr (range 0–27) | about 8% of the foregone burial's PV under natural recolonisation (not modelled) | Pendleton 2012 range; time profile sourced as bracketed above, the 10-yr central inferred |
| Buried under fill (breakwaters, reclaimed land) | low, 0–0.25 (preset 0.125) | — (preset 10 yr) | none | inferred, no source |

The case default is the "exposed" row, because the fate is unknown until the user enters it; the owner confirmed it (Step 8d.2, no numeric change). Since Step 8d.2 the three rows are a preset, `--matte-fate {exposed,excavated,buried}` (`carbon.release_fates` in the case file), explained in plain words in `--help`:
- **exposed**: the meadow dies but its matte stays in place, uncovered; open to oxygen, the dead matte erodes and its carbon escapes over years to decades;
- **excavated**: the matte is dug out or dredged; nearly all its carbon goes in the year of the works;
- **buried**: the matte is covered by fill and kept without oxygen, which probably preserves most of its carbon. The preset uses 0.125, the midpoint of the inferred 0–0.25 range, with the exposed half-life; both are labelled **inferred** (confidence `placeholder`). The owner kept this preset as it is, labelled inferred (Step 8e.1), so it is no longer an open question.

`--carbon-release-fraction` and `--carbon-release-half-life` still override the preset. A fate other than the default is recorded as user-supplied, with its basis.

PV of the release per hectare destroyed at the SCC (central discount schedule):

| Fate | PV per ha |
|---|---|
| Excavated (0.96, immediate) | €191,000 |
| Exposed, immediate (0.63, half-life 0) | €126,000 |
| Exposed, half-life 5 / 10 / 27 yr | €118,000 / €111,000 / €97,000 |

Time enters only through discounting: the SCC grows at 1.3%/yr, below the 2.3% discount rate. This is consistent with the static engine. The path-dependent option A is not used.

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

The quarantined endogenous pricing (decision D4) solves V = S·W·V + S·A. Here S is the diagonal of scarcity multipliers, W[target][source] holds the edge strengths, and A holds the anchors.

**Since Step 8c.6 a few anchors determine every price.**
- **The condition.** An agent without an anchor must be reachable from an anchored one along edges of positive strength (source → target). Under that condition, and with ρ(S·W) < 1 (certified at every step), the solution V = Σ_k (S·W)^k S·A is unique and strictly positive.
- **Derived prices.** An unanchored agent's price is derived: V_i = S_i Σ_j W_ij V_j.
- **Why Step 4 required every agent to be anchored.** It was the simplest sufficient condition: in the forest case an unanchored agent with nothing anchored upstream had been priced at €0 (C8.3). Reachability is the exact condition.
- **The Posidonia anchors.** The case anchors three agents with their service-ledger values:
  - Fish Populations: auction prices, a market price;
  - Coastal Protection: damage cost avoided, a market cost;
  - the Posidonia Meadow, which must be anchored because it is the only agent with no incoming edge. Its anchor is a stated-preference value, because the meadow has no market price.
- **The other seven prices are derived**, and they are labelled as derived in the text, the JSON (`derived_prices`) and the provenance (`pricing.derived[…]`, placeholder). The former PLACEHOLDER anchors are gone.
- **The other three cases (Step 8d.6)** also price from a few sourced anchors, market-based values from de Groot et al. (2012), *Ecosystem Services* 1:50–61, doi:10.1016/j.ecoser.2012.07.005, Table 2 (read in full; Int$/ha/yr, 2007 price level, used as € like their agent values), whose Table 1 shows how they were valued: food 118 of 133 estimates at direct market prices, water 32 of 38 market or cost-based, pollination 2 of 3 production-function values:
  - forest (temperate forest): Watershed & Local Climate, water 191; Vegetation & Flora, food 299. Both roots, both sourced;
  - costa_brava (woodlands): Mycorrhizal Fungi (the only root), food 52 (wild mushrooms are the fruiting bodies of mycorrhizal fungi); Pollinators & Insects, pollination 31;
  - amazon_forest (tropical forest, no root): Canopy Trees, food 200; Pollinators, pollination 30; Aquatic System, water 27.

  No placeholder anchor is left anywhere (`anchor_every_agent: false` in all four files): every root has a sourced anchor, so reachability makes the former placeholders unnecessary.

**What derived prices rest on.** They carry no information of their own. Doubling an anchor doubles every price it reaches. Each derived price moves one for one with the placeholder edge strengths and with the hand-set scarcity multipliers. They also add each upstream anchor again into every agent downstream, which is the double counting of C8.4.

At 30% depletion of a 1,000-ha meadow, for instance, the derived price of Marine Megafauna reaches €1.8 billion/yr: scarcity at its 50× cap, times a network multiplier of about 290. Pricing therefore stays EXPERIMENTAL, quarantined (certified convergence, explicit failure, no fallback) and outside the v1.0 output.

## 9. What was searched for and not found

- **A Posidonia damage-response curve.** No study relating the fraction of a meadow lost to the fraction of each service lost.
- **Interaction strengths.** None for the case's 15 edges.
- **Tourism and non-use values per hectare of P. oceanica.** No direct study found. Since Step 8c.2 recreation (diving) and the non-use values of megafauna and seabirds are in the ledger through benefit transfer (§2). Beach tourism and the meadow's own existence value are still missing (no usable willingness-to-pay study, §2b); since Step 8e.6 the meadow carries its own value through a production function instead. The Mediterranean meta-regression of Stamatiadou et al. (2025) includes recreation (§10).
- **The Costa Brava share of the Catalan stock.** Not found; the Generalitat's dataset was not downloaded.
- **P. oceanica-specific figures** for matte accretion, leaf-biomass carbon and transplanting cost.
- **The "80× fish biomass in the Medes Islands" claim** in the former case notes. No source found; the claim is removed. García-Rubies, Hereu & Zabala (2013), *PLoS ONE* 8:e73922, doi:10.1371/journal.pone.0073922, report instead that exploited fish in the Medes no-take reserve took 25–35 years to reach carrying-capacity biomass, with limited spillover.
- **Grey literature cited by the sources but not read:** Pergent et al. (2012, IUCN/RAC-SPA), Boudouresque et al. (2012, RAC/SPA), Mateo et al. (2019, LIFE Blue Natura), González-Correa et al. (2005, *JEMBE* 320:65–76, doi:10.1016/j.jembe.2004.12.032, metadata only).

## 10. Benchmarks: where Gaia's per-hectare values fall (Step 8.3)

The case file lists published per-hectare values (`run.benchmarks`). Every extraction report and JSON output (`"benchmarks"`) compares Gaia's figures with them (`gaia/benchmarks.py`). Values are shown in their own currency and price year, unconverted: this is an order-of-magnitude check, not a test.

Gaia's figures for the default run (50 of 4,582 ha destroyed):

| Gaia figure | €/ha/yr |
|---|---|
| Service value of one hectare at full damage (the service ledger, §2), carbon excluded | 1,068.40 |
| … plus its carbon burial at the year-0 social cost of carbon (0.953 tCO₂ × €166.35) | 1,226.99 |
| What the run actually charges per hectare lost (annual externality / 50 ha) | 1,068.40 |

Since Step 8c.3 small losses are priced linearly, so the run charges exactly the linear benefit transfer: 50 × 1,068.40 = €53,420/yr (€40,933 before Step 8e.6 added the meadow's food production). Before Step 8c it charged €6,325/yr, 44% of the then €14,242/yr transfer of €284.83/ha/yr.

| Benchmark | Value | Includes | Gaia vs benchmark |
|---|---|---|---|
| Campagne et al. 2015, *P. oceanica*, carbon excluded | 277–285 €2014/ha/yr | 5 goods and benefits | above (×3.75): the ledger adds recreation, non-use values and the meadow's food production beyond the commercial catch to the services it takes from Campagne et al. |
| Campagne et al. 2015, carbon included | 284–514 €2014/ha/yr | + carbon at €35/t | above (Gaia with burial at the SCC: 1,227) |
| Stamatiadou, Mazaris & Katsanevakis 2025, *Ecosystem Services* 72:101704, doi:10.1016/j.ecoser.2025.101704: Mediterranean seagrass meta-regression (ESVD-style, 17 studies, 91 observations) | basin mean 8,712 Int$2020/ha/yr; countries 1,588–95,767 | 8 services incl. recreation/tourism, climate regulation | below: the mean is ~8× Gaia |
| de Groot et al. 2012, *Ecosystem Services* 1:50–61, doi:10.1016/j.ecoser.2012.07.005 (the ESVD/TEEB database), coastal systems, as tabulated by Costanza et al. 2014 Table 4 | total of means 28,917 Int$2007/ha/yr (totals of minima–maxima 26,167–42,063) | all coastal systems, not seagrass alone | below: ~27× |
| Costanza et al. 2014, *Global Environmental Change* 26:152–158, doi:10.1016/j.gloenvcha.2014.04.002, Table 3: seagrass/algae beds | 28,916 $2007/ha/yr | 26,223 of it nutrient cycling | below: ~27× |
| Vassallo et al. 2013 (emergy, supply side) | 172 €/m²/yr = 1.72 million €/ha/yr | resources invested by nature, not willingness to pay | not comparable; not in the output |

### Reading the benchmarks

1. **Gaia sits low in the published range, now inside its lower part rather than at its floor.** Before Step 8c.2 it used only the primary *P. oceanica* valuation (Campagne et al.), which leaves out tourism, recreation and non-use values. The service ledger adds recreational diving and the non-use values of megafauna and seabirds, which nearly triples the per-hectare value (€285 → €819), and since Step 8e.6 the food the meadow's primary production supports beyond the commercial catch (€819 → €1,068). The Mediterranean meta-regression is about 8× higher (central over Gaia, 7.1 with carbon burial). It includes recreation and tourism and scales with GDP per capita; Spain's country value was not in the abstract read. The global syntheses are about 27× higher, mostly because of a nutrient-cycling value transferred from estuaries. Applying that to a Mediterranean meadow would be a large benefit-transfer leap.
2. **The remaining gap is in services that are still not valued.** These are beach tourism and the meadow's own existence value. For coastal protection, water purification and fisheries, Gaia uses the published Posidonia figures, and for the meadow's own food production a production function (§2b). The new recreation and non-use entries are benefit transfers with low confidence (§2). A Catalan stated-preference study of the meadow itself remains the main open data need.
3. **Small losses are now charged their average value** (§3). The run's per-hectare charge equals the ledger total, so the realised loss and the linear transfer coincide. Past the safe threshold, the remaining meadow degrades and the charge per hectare rises.
4. **Carbon still dominates, less than before.** The release costs about €111,000 per hectare in PV at the SCC, with the 10-year half-life (§4). The PV of the services charged per hectare is about €100,000 (over 200 years with scarcity uplift), and the foregone burial €19,000. No benchmark above includes the release, because they value flows only.
