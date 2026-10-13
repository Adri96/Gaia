# Valuing the loss of *Posidonia oceanica* meadows on the Catalan coast with Gaia: methods note

*Gaia v1.0 candidate case (Step 8.5 of `TOP_PRIORITIES_REPORT.md`). Draft for external review by an ecologist (Track 1: is the model structure defensible?) and an environmental economist (Track 2: are the values and their treatment defensible?). The parameter-by-parameter sources are in `docs/POSIDONIA_LITERATURE_REVIEW.md`. Figures below come from the case file `gaia/cases/data/posidonia.json` at the commit this note ships with. Every number can be reproduced with the commands in §9.*

---

## 1. The question

**User:** a Catalan coastal authority or marine NGO reviewing the environmental impact assessment of a port or marina expansion that would destroy part of a *P. oceanica* meadow. *P. oceanica* beds are a priority habitat (1120\*) under the EU Habitats Directive.

**Question:** if the project destroys *N* hectares of the Catalan *Posidonia* stock, what is the present value of the ecosystem services and carbon lost? How does it compare with the project's private gain, and with what uncertainty? Which inputs drive the answer?

The reference resource is, by default, the regional stock: 4,582 ha of *P. oceanica* mapped by the Generalitat de Catalunya in 2025, as reported. The user can replace it with the specific meadow the project affects (`--area-ha N --resource-name NAME`, or the case file's `resource` block). The default project destroys an illustrative 50 ha (1.1%) for a private gain of €2,500/ha (a placeholder; the user enters the project's own figure). Gaia answers with:

- one deterministic run: `gaia run posidonia --units N --unit-value G`;
- a Monte Carlo over the parameter ranges: `--uncertainty`.

## 2. Model structure

**Resource and depletion.** The meadow is divided into hectares (units). Destroying *k* of *N* units gives the depletion D = k/N.

**Agents.** Ten agents depend on the meadow:
- the meadow itself, a keystone foundation species;
- coralligenous reefs, epiphytes and algae, invertebrates, fish, marine megafauna and seabirds;
- three human-facing services: coastal protection, water quality and "human communities" (cultural services).

Each agent *i* has:
- a dependency weight w_i (its share of ecosystem health);
- a damage curve f_i(D) in [0, 1];
- a trophic level, which amplifies direct damage for consumers by (1/0.15)^(0.25·level), i.e. 1.6×, 2.6× and 4.1× at levels 1–3;
- a yearly value at full damage v_i (€/ha/yr).

**Cascades.** Fifteen directed edges carry damage between agents in a single pass. The pressure on agent *i* is p_i = Σ_j s_ji · d_j (sum over the edges into *i*, with d_j the source's direct damage). It acts on the service still standing:

  effective_i = direct_i + (1 − direct_i) · p_i

The meadow is a keystone: while its health is below 0.3, the strengths of its outgoing edges double. Validation caps each agent's incoming strengths at 1 (keystone boost included), so damage stays in [0, 1].

**Damage model: the area lost plus the degradation of what remains (Step 8c.3).** The case declares `"damage_model": "area_loss"`. The hectares lost take their own services, a linear benefit transfer. The curves, amplification and cascades above describe the degradation g_i(D) of the meadow that **remains**:

  damage_i(D) = D + (1 − D) · g_i(D)

The degradation curve is zero up to the safe threshold, so damage_i has slope exactly 1 at small losses: the marginal hectare costs its average value.

**Money.** At depletion D:
- annual externality = Σ_i damage_i(D) · w_i · v_i · area;
- ecosystem health = 1 − Σ_i w_i · damage_i(D).

**A static function, evaluated directly.** Every quantity above depends on D alone, so the cost of the 51st hectare is the difference between the function at 51 and at 50 hectares (decision D5, option B).

Time enters in three places only:
- discounting of the yearly flows;
- the succession curve after restoration;
- the substrate (matte) ceiling on what restoration can recover.

The order and timing of actions do not matter. A path-dependent engine is a committed roadmap item after v1.0 (§8): a time axis with extraction schedules, substrate erosion over real time, keystone hysteresis, and damage-dependent recovery.

**Restoration.** Restoration retraces the extraction's damage path in reverse:

  recovered value = recovery efficiency × damage reversed × substrate ceiling

The succession curve spreads that value over time.

## 3. Unit semantics

| Quantity | Unit | Treatment |
|---|---|---|
| Agent values, annual externality | €/yr (a flow) | Lost every year the meadow is gone; the loss is treated as permanent over the horizon (natural recolonisation leaves "limited cover after a century", Kendrick et al. 2005) |
| Present value of the externality | € PV at year 0 | Σ_{t=1}^{200} flow × DF(t) × (1 + 1%)^t. DF uses 2.3%/yr for years 0–30, 1.8% to year 100 and 1.4% after; the 1%/yr relative price change of ecosystem services is the scarcity uplift (Drupp et al. 2018, 2024). Reported at 50, 100 and 200 years. |
| Carbon released | € PV | ha × top-metre matte carbon (1,199 tCO₂/ha) × fraction lost (0.63), released as a negative exponential with a 10-year half-life: the share released in year t is valued at the social cost of carbon of year t (€166.35/t in year 0: US EPA 2023, $190 for 2020 emissions at 2%, at the ECB 2020 rate) and discounted. Both the fraction and the half-life are project inputs; a half-life of 0 releases everything at year 0 (excavation) |
| Carbon burial lost | € PV | ha × 0.953 tCO₂/ha/yr × SCC(t), growing 1.3%/yr (EPA path) × DF(t) |
| Private gain | € one-off | Compared with the PV only, never with the €/yr flow |
| Net social cost | € PV | PV of externality − private gain; positive means society loses more than the project gains |

Carbon is valued only by the carbon module (decision D3): no agent value contains climate regulation.

## 4. Calibration regime and what the curves are

The ten degradation curves are the same `threshold_logistic`: zero up to the 20% "safe threshold", then a logistic with its inflection at 32% loss and steepness 12. **No study relates the fraction of a Posidonia meadow lost to the degradation of the rest.** The curves are therefore placeholders: each agent's direct degradation, with the edges adding the indirect part (calibration regime B). Two consequences matter for the question:

1. **Small losses are priced linearly (the owner's decision, Step 8c.3).** Below the threshold the annual externality is exactly N ha × the per-hectare total of the service ledger (§5), whatever the reference resource and the curve parameters. Before Step 8c the plain logistic (initial slope ≈ 0.25) charged 44% of that. Past the threshold the remaining meadow degrades. The hectares just beyond it cost 3–4 times their average value, and once most of what remains is degraded, further hectares cost little. Reviewers should judge whether this "linear, then collapse of the remainder" shape is the right prior for a seagrass meadow, and where the threshold of a given meadow lies.
2. **No CalibrationWarning.** Health at the threshold is 1 − t by construction (the lost area's services are gone). The check therefore looks at the remaining meadow, which does not degrade before the threshold. The 20% threshold is still unsourced; it marks where degradation of the remainder starts. It does not make a 20% loss "safe", because that loss still costs 20% of the services.

Single-pass cascades cut chains longer than one hop. Under regime B, the cascade part is therefore a structural lower bound.

## 5. Parameters and sources

A Posidonia extraction run records 63 parameters (73 with restoration; one more since Step 8e.6, the meadow's value on every hectare, `low`): 28 sourced (22 by DOI or arXiv id, 6 by an official URL) and 44 flagged (34 placeholders, 10 owner weights). The literature review gives every one of them, with value, range, source and mapping. In summary:

**Service values: the service ledger (Step 8c.2).** Every agent carries euros under any input, and each final service is counted once, owned by one agent (PROJECT_DEFINITION.md, Core Valuation Principles). Since Step 8e.7 this is a validated invariant: an agent whose value on every hectare is not > 0, or whose Monte Carlo range reaches 0, is rejected, and a test runs every case under every preset and flag. Intermediate agents get a sourced share of a final service moved from another agent, so the total is unchanged (Boyd & Banzhaf 2007; Fisher et al. 2009); a value that overlaps services counted elsewhere is booked net of them (`net_of`, Step 8e.6). € /ha/yr at full damage:

| Agent | Final service | €/ha/yr | Source (method) |
|---|---|---|---|
| Coastal Protection | protection from coastal erosion | 188 | Campagne et al. 2015 (damage cost avoided) |
| Water Quality | water purification | 60 | Campagne et al. 2015 (benefit transfer) |
| Fish Populations | fisheries, fish species (14/16 of 35) | 30.63 | Campagne et al. 2015 (production function); range up to 74 × 14/16, from Jackson et al. 2015 |
| Marine Invertebrates | fisheries, sea urchin and cuttlefish (2/16 of 35) | 4.38 | Campagne et al. 2015 (moved from fish; share by species count) |
| Human Communities | bioindicator use (3/3.5 of 1.5) and knowledge (0.33) | 1.62 | Campagne et al. 2015; PREI weights, Gobert et al. 2009 |
| Epiphytes & Algae | bioindicator use, epiphyte metric (0.5/3.5 of 1.5) | 0.21 | Gobert et al. 2009 (moved from Human Communities) |
| Posidonia Meadow | **food from primary production**, on every hectare: the fish and invertebrates its production supports, net of the commercial catch above | 474.48 (509.48 − 35) | production function (below): NPP of the plant 160, its roots 7 and its leaf epiphytes 23 g C/m²/yr → the part not buried into the food web → 14.3% transfer per level (Western Mediterranean food-web models) to trophic level 3.1 → ×9 wet weight → 46.5% sustainable catch → €5.11/kg (literature review §2b) |
| Posidonia Meadow | recreational diving: the meadow's amenity, **only near dive sites** | 454.52 at the regional share | Zunino et al. 2020, −€34.71 per dive for total loss × ~60,000 Medes dives/yr ÷ 142.35 ha of meadow within reach of dive sites (EEA Natura 2000 forms) = €14,630/ha/yr near dive sites, × the share of the affected meadow near dive sites (default 0.0311, the regional share; `--dive-site-share`) |
| Coralligenous & Red Coral | recreational diving: coralligenous | 18.95 | Rodrigues et al. 2016, −€60 per dive for gorgonian extinction (Medes) × 60,000 ÷ 190,000 ha of mapped seabed |
| Marine Megafauna | non-use: protecting marine mammals | 30.18 | Börger et al. 2014 (UK choice experiment, £30.32/household/yr for 5 years), annualised, × Catalan households ÷ 190,000 ha, half of a bundled attribute |
| Seabirds | non-use: protecting seabirds | 30.18 | the other half |
| **Total** | | **1,293.15** | |

**The meadow's own value, from its primary production (Step 8e.6).** The owner's rule is that no agent may ever be at €0, and that where no willingness-to-pay value exists, value comes from what people consume. *P. oceanica* is one of the most productive habitats of the sea: per hectare, seagrass meadows fix carbon on the scale of coral reefs and intensive cropland (gross primary production 1,903 g C/m²/yr against 1,720 for coral reefs and 2,182 for an irrigated two-crop wheat–maize field; 997 measured over 12 years in a Corsican *P. oceanica* meadow; 68 for the bare sediment around it; tropical rainforest 3,000–4,000). The chain, each link sourced (literature review §2b):

| Link | Value | Result per hectare a year | Status |
|---|---|---|---|
| Net primary production of the plant (blades, sheaths, rhizomes; Pergent et al. 1994; range up to the Catalan 989, Cebrián et al. 1997) | 476 g DW/m²/yr | | verified |
| × carbon content (Duarte 1990) | 33.6% | 160 g C/m² | verified |
| × share eaten, decomposed or exported, not buried (Mateo & Romero 1997, Medes) | 74% | 118.4 g C/m² into the food web | verified |
| + roots (Step 8f.2): 17 g DW/m²/yr (Mateo & Romero 1997, Medes) × 40.9% C, × 4% decomposed within the year (the rest is buried in the matte; 0.00015/d, Mateo 1995 via Cebrián et al. 1997) | 6.95 g C/m² | 0.28 g C/m² into the food web | derived / verified / secondary |
| + leaf epiphytes (Step 8f.2): 1.9 mol C/m²/yr (Bay 1984, Corsica, via Champenois & Borges 2021), none buried | 22.8 g C/m² | 22.8 g C/m² into the food web | secondary / inferred |
| = all producers, × 10 kg/ha per g/m² | 190 g C/m² | 1,415 kg C into the food web | |
| × transfer efficiency^(3.1 − 1) (median of five Western Mediterranean Ecopath models, Sánchez-Zulueta et al. 2023, = the north-western Mediterranean model; temperate models average 14.25%, Coll et al. 2008; Francour 1997 with FishBase) | 14.3% per level (12.2–21.8%) | 23.8 kg C of consumers | derived; trophic level derived |
| × wet weight per carbon (Pauly & Christensen 1995, cited by Chen et al. 2022) | 9 | 214 kg of fish and invertebrates | secondary |
| × sustainable share (Zhou et al. 2012: F_MSY = 0.87 M) | 46.5% | 99.7 kg caught | derived / inferred |
| × first-sale price, Catalan white fish 2014 (Generalitat) | €5.11/kg | **€509.48 gross** | verified |
| − commercial catch already booked to fish and invertebrates (Campagne et al. 2015) | −€35.00 | **€474.48 net** | — |

The gross value counts every fish and invertebrate the meadow's own production can sustain at a sustainable catch, by any fisher, wherever it is caught (the nursery spillover included); the prey in between are trophic steps, not valued again. The ledger books it net of the commercial catch, and parsing enforces the subtraction. Carbon is not counted twice: the chain uses only the production that is not buried, producer by producer (roots: 4%; the rest goes to the matte), and `gaia.carbon` values the buried part (D3). The epiphytes' food is not counted twice either: the Epiphytes & Algae agent owns the epiphyte metric of the bioindicator service (monitoring, a cultural service), not food. The report shows the chain, and the matte's carbon (an attribution, not added), on the meadow's line, and compares the productivity figures in a "Primary Production" section. Over the ends of every link's range the net value runs from €31.41 to €2,993/ha/yr. The transfer efficiency is the median of five Western Mediterranean Ecopath models since Step 8f.1 (the global median, 11.8%, before: €249.74 net); the roots and leaf epiphytes are producers since Step 8f.2 (€391.29 net before; of the €509.48 gross, the roots give €1.00 and the epiphytes €82.20). No willingness-to-pay value for the meadow's existence was found (literature review §2), so none is added.

Services of the meadow itself are spread over the meadow area. Services of the wider seascape (coralligenous diving, the non-use values of mobile species) are spread evenly over the mapped Catalan seabed to 50 m (~190,000 ha), an attribution assumption that the owner accepted as **provisional** (Step 8d.3; labelled so in the provenance). The recreation and non-use entries are low-confidence benefit transfers with wide ranges (literature review §2).

**The diving value applies only near dive sites (Step 8d.4).** The meadow within reach of dive sites is estimated at 142.35 ha, the *P. oceanica* cover of the Costa Brava's five coastal Natura 2000 sites (Cap de Creus, Montgrí–Medes–Baix Ter, Litoral del Baix Empordà, Cadiretes, L'Albera; EEA Standard Data Forms), a flagged proxy. The Medes dives are divided over it (€14,630/ha/yr), and the user states the share of the affected meadow near dive sites (`--dive-site-share`). The default, the regional share 0.0311, reproduces the former regional average of the diving value. For the default 50 ha (1,000 draws, seed 20261012; Step 8f.2 numbers):

| `--dive-site-share` | Annual externality | PV of externality (P5 / P50 / P95) |
|---|---|---|
| 0.0311 (default, location unknown) | €64,657 | €12.57 M (12.09 / 17.27 / 23.94) |
| 1 (a project at a dive site) | €773,438 | €78.90 M (63.70 / 109.43 / 177.29) |
| 0 (far from any dive site) | €41,932 | €10.44 M (9.33 / 14.19 / 20.72) |

At a dive site the meadow's diving value dominates everything else; far from one, carbon does, and the meadow still carries its own €474.48/ha/yr.

**How much the meadow is dived (Step 8e.2).** The value near dive sites is stated at the Costa Brava's average intensity, 421.5 dives per hectare of meadow a year (the Medes dives over the 142.35 ha). A project states the intensity at its meadow with `--dive-intensity`; the intensity sets the value per hectare near the dive sites (€34.71 per dive × dives/ha/yr) and `--dive-site-share` the part of the affected meadow near them (1 when the intensity is given alone). In plain words:

| `--dive-intensity` | What it means | Dives per ha of meadow a year | €/ha/yr near dive sites | Basis |
|---|---|---|---|---|
| `none` | No dive site within reach of the meadow | 0 | 0 (the diving service only; the meadow keeps its €474.48 on every hectare) | by definition |
| `low` | Light use, like the Banyuls-Cerbère reserve (France): ~14,000 dives a year over 211 ha of meadow | 66 | 2,298 | Lloret 2006, conference slides (grey literature, `low`) |
| (default) | The Costa Brava average | 421.5 | 14,630 | Medes dives over the Costa Brava's 142.35 ha |
| `medium` | Busy, like Portofino (Liguria): up to 40,000 dives a year over 71 ha | 566 | 19,663 | Betti et al. 2023 (abstract, `low`) |
| `high` | Intense, like the Medes Islands: ~60,000 dives a year over 10.75 ha | 5,581 | 193,730 | press report of the park's study (`low`) |

Meadow areas are the *P. oceanica* cover of each site's Natura 2000 form. For the default 50 ha with the intensity alone (share 1; 1,000 draws, seed 20261012):

| `--dive-intensity` | Annual externality | PV of externality, base (P5 / P50 / P95) |
|---|---|---|
| `none` | €41,932 | €10.44 M (9.33 / 14.19 / 20.72) |
| `low` | €156,838 | €21.19 M (20.27 / 29.76 / 41.43) |
| `medium` | €1,025,078 | €102.46 M (81.22 / 141.80 / 232.73) |
| `high` | €9,728,443 | €917.04 M (677.46 / 1,280.36 / 2,153.44) |
| `high`, `--dive-site-share 0.1` (5 of the 50 ha at the site) | €1,010,583 | €101.10 M (80.21 / 139.90 / 229.50) |

The intensity is a density: `high` fits only a small meadow at a heavily dived site, so a larger project should state the share near the site. `none` zeroes the diving service, never an agent: the meadow keeps its own value on every hectare (€474.48/ha/yr, the food its production supports; Step 8e.6), and every other agent keeps its value. **Beach tourism and the meadow's own existence value are still not valued, so the total is a lower bound.**

**Carbon.**

| Parameter | Value | Source | Range |
|---|---|---|---|
| Burial | 0.953 tCO₂/ha/yr (26 g C/m²/yr) | Mazarrasa et al. 2017, Balearic Islands | 0.28–3.09 (Pergent-Martini et al. 2021) |
| Top-metre matte stock | 1,199 tCO₂/ha (327 t C/ha) | Monnier et al. 2022, the French Label Bas-Carbone default | 741–1,844 (Leduc et al. 2023) |
| Fraction lost on conversion (project input) | 0.63 | Pendleton et al. 2012 | 0.25–1.0 |
| Release half-life (project input) | 10 yr | Pendleton et al. 2012 (5–10 yr); seagrass evidence 3–50 yr (Arias-Ortiz et al. 2018; Macreadie et al. 2015; Serrano et al. 2016) | 0–27 yr |
| Biomass | none counted separately | the leaves are negligible next to the matte | — |

On the fraction lost and its timing, which depend on what the project does to the matte (literature review §4, "Release over time versus re-absorption"). The user states it with `--matte-fate` (Step 8d.2), a preset of `--carbon-release-fraction` and `--carbon-release-half-life`, which still override it:

| `--matte-fate` | What happens to the matte, in plain words | Fraction released | Half-life | Basis |
|---|---|---|---|---|
| `exposed` (default) | The meadow dies but its matte stays in place, uncovered (shading, turbidity, anchoring, scour). Open to oxygen, the dead matte erodes and its carbon escapes over years to decades. | 0.63 (range 0.25–1.0) | 10 yr (range 0–27) | Pendleton et al. 2012 (sourced); the 10-yr central half-life is inferred |
| `excavated` | The matte is dug out or dredged (port basins, channels, docks). The carbon-rich soil is removed and broken up, so nearly all its carbon goes in the year of the works. | 0.96 | 0 (at once) | IPCC (2013) Wetlands Supplement, Tier 1 for port excavation (sourced) |
| `buried` | The matte is covered by fill (breakwaters, reclaimed land). Kept without oxygen, it probably keeps most of its carbon. | 0.125 | 10 yr | **inferred, no source**: the midpoint of the inferred 0–0.25 range; the half-life is the exposed default. Kept as it is by the owner (Step 8e.1) |

The default stays "exposed" (the owner's decision, Step 8d.2). A fate other than the default is recorded as a user-supplied project input, with its basis, and is held fixed in the Monte Carlo.

Re-absorption is not modelled in the extraction view. On the footprint the conversion is permanent. Around it, natural recolonisation over centuries would re-absorb about 8% of the PV of the foregone burial, about 1.5% of the release.

**Unsourced, flagged.**
- The degradation curve, threshold and steepness.
- The 15 edge strengths. Several links are documented qualitatively, e.g. wave height falls ~50% over ~1 km of meadow (Infantes et al. 2012), but none has a published strength.
- The keystone threshold.
- The owner's health weights.
- The project's gain per hectare.
- The model-wide trophic and keystone constants.
- The matte erosion parameters.

**Restoration.**
- Planting cost: €50,000/ha. That is of the order of the median marine restoration cost (Bayraktarov et al. 2016), not a Posidonia survey.
- Succession, from an agent-based model of natural recolonisation (Kendrick et al. 2005):
  - 100 years to 10% of the service;
  - 400 years to 67%;
  - 600 years to approach maturity.
- Transplant survival is low: 38% median for seagrass, 0–31% on disturbed substrate.

## 6. Uncertainty method

Each recorded parameter that can change an extraction result is sampled:

- **Distribution.** The parameter's documented range is used where the review gives one, otherwise a range set by its confidence (high ±10%, medium ±25%, low ×/÷2, placeholder ×/÷3). The distribution is triangular with the documented value as its mode, or uniform where the review sees no reason to prefer the documented value: threshold 0.1–0.3, steepness 6–18, keystone threshold 0.15–0.45.
- **Constraints.** Ratios are kept in [0, 1]. A draw that fails the model's validation (e.g. edges above the in-degree cap) is redrawn and counted.
- **Not sampled:**
  - the health weights: they are fixed, because weight × value is the sourced euro figure;
  - the user's inputs: the reference area, hectares destroyed and private gain, plus the carbon release fraction and half-life when the user enters them;
  - the model-wide constants;
  - the normative choices: discount schedule, scarcity, horizon, carbon price. These are value judgements, not unknowns with a distribution, and are reported as separate sensitivities.
- **A project meadow must state its diving (Step 8e.3).** With `--area-ha` (a specific meadow) the run requires `--dive-intensity` and/or `--dive-site-share` and stops with a plain error otherwise; the regional averages are the default only for the regional run.
- **Mechanics.** Each draw sets the sampled values in a copy of the case file, which is re-parsed with full validation and run. The generator is seeded (default 20261012). 1,000 draws take about 4 s.
- **Sensitivity ranking.** One parameter at a time is set to its own P5 and P95 while the others stay at their documented values; the swing in net social cost is reported.

This replaces the former heuristic band, which multiplied the externality by 1 ± (1 − a zone-based "confidence").

**Caveats a reviewer should weigh:**
- Most ranges are judgements; the review says which.
- The parameters are sampled independently. The soil carbon stock and the burial rate, for instance, are plausibly correlated.
- P5–P95 describe parameter uncertainty within this model structure, not structural uncertainty. The curve shape (§4) and the unvalued services (§5) are not inside the bounds.

## 7. Results for the default question (50 of 4,582 ha, private gain €2,500/ha)

| Quantity | Base | P5 | P50 | P95 |
|---|---|---|---|---|
| Annual externality (services), €/yr | 64,657 | 62,885 | 106,988 | 172,022 |
| PV services lost (200 yr) | 6.05 M | 5.89 M | 10.01 M | 16.10 M |
| PV carbon released (10-yr half-life) | 5.56 M | 3.09 M | 5.54 M | 9.00 M |
| PV carbon burial lost | 0.95 M | 0.57 M | 1.35 M | 2.57 M |
| **PV of externality** | **12.57 M** | **12.09 M** | **17.27 M** | **23.94 M** |
| **Net social cost** (− €125,000 private gain) | **12.44 M** | **11.96 M** | **17.15 M** | **23.81 M** |

*1,000 draws, seed 20261012 (Step 8f.2; before it 12.18 M, P5–P95 11.46–20.60 M; before Step 8f.1 11.51 M, 10.30–17.67 M; before Step 8e.6 10.35 M, 8.73–15.98 M). Base is the run at the documented values. P50 lies above base because several ranges are right-skewed: the meadow's diving and food values, burial, the non-use values, the release fraction. The base annual externality is exactly 50 ha × €1,293.15/ha/yr, because below the threshold small losses are priced linearly (§4).*

**Drivers** (swing in net social cost between each parameter's P5 and P95):

| Parameter | Swing |
|---|---|
| The meadow's food value (production function, sampled as one aggregate between the ends of every link) | €9.8 M |
| Carbon release fraction | €4.5 M |
| The meadow's diving value | €3.5 M |
| Matte carbon stock | €3.5 M |
| Burial rate | €2.0 M |
| Release half-life | €1.0 M |
| Coastal-protection value | €0.91 M |
| Water-quality value | €0.29 M |
| Megafauna, seabird non-use values | €0.26 M each |

The fisheries, coralligenous and invertebrate values each swing it by less than €0.15 M. The curve steepness and the safe threshold no longer matter for a project below the threshold.

**Normative choices** (net social cost, base parameters):

| Choice | Net social cost |
|---|---|
| Market/ETS carbon price (€80/t) | €9.06 M |
| EPA SC-CO₂ at a 2.5% near-term rate ($120/t) | €10.04 M |
| EPA SC-CO₂ at a 1.5% near-term rate ($340/t) | €17.58 M |
| 2.0% constant discount rate | €12.09 M |
| No relative price change | €9.58 M |
| 100-year horizon | €9.95 M |

**Benchmarks** (per hectare per year):
- Gaia's service value at full damage is €1,293/ha/yr (€1,452 with carbon burial at the SCC). That is about 4.6× Campagne et al.'s non-carbon services, because the ledger adds recreation, non-use values and the meadow's food production beyond the commercial catch to theirs.
- The Mediterranean seagrass meta-regression of Stamatiadou et al. (2025) has a basin mean of 8,712 Int$2020/ha/yr, about 7× higher. It includes recreation and tourism.
- The global syntheses for coastal systems and seagrass (de Groot et al. 2012; Costanza et al. 2014) are about 22× higher, mostly a transferred nutrient-cycling value.

**Reading.**
1. Carbon and services now weigh about the same for the default project. Per hectare destroyed:
   - the release costs about €111,000 in PV (SCC, 10-year half-life);
   - the services charged cost about €121,000 in PV;
   - the foregone burial costs about €19,000 in PV.
2. The net social cost is positive across the P5–P95 range and under every normative choice tested. It is about 72–191 times the default private gain (ETS carbon price: 72×; P5: 96×; P95: 191×). To break even, a project would need a private gain of about €184,000 (ETS carbon price) to €479,000 per hectare: the PV of the externality per hectare, which is €242,000 at P5 and €479,000 at P95.
3. That conclusion rests on two uncertain terms:
   - the fraction and timing of the matte carbon release, which the user's environmental impact assessment can resolve (`--matte-fate`): excavated matte (0.96, at once) raises the release to about €191,000 per hectare;
   - the meadow's diving value, a benefit transfer that a Catalan valuation should replace, and which since Step 8d.4 applies only near dive sites: the user's `--dive-site-share` and `--dive-intensity` decide whether the diving service is €0 or the largest term (the meadow agent itself never falls to €0: it keeps its food value).

**Restoration** of the same 50 ha (`--mode restore --units 50 --time-horizon 200`, €200,000/ha including maintenance):
- net restoration value −€7.35 M (PV);
- only about €0.53 M of benefits within 200 years, because recolonisation is slow;
- the carbon breakeven price is far above any credible carbon price.

Destroying and then restoring is therefore much worse than not destroying: the destroy-then-restore penalty is €19.9 M in PV, about 159 times the foregone gain.

## 8. Limitations

1. **Static engine; no path dependence.** The timing of the works, the possibility of phased destruction, hysteresis after keystone collapse, and slower restoration after a delay are not represented. Option A (time axis and real-time substrate erosion → relaxation and keystone hysteresis → damage-dependent recovery) is a **committed milestone after v1.0** (`version_specs/V09_SPEC.md`). The data format is reserved for it (schema 2, `dynamics` block).
2. **Lower-bound valuation.** Beach tourism and the meadow's own existence value are not valued. The recreation and non-use values in the ledger are benefit transfers (Italian and UK studies, the Medes Islands' dive counts, an attribution rule for seascape services). The total value of the services sits in the lower part of the published range (§7).
3. **Unfitted response curves and edges** (§4). These are the main structural uncertainty for the services part, and they are outside the Monte Carlo bounds.
4. **Benefit transfer, with no income or price-year adjustment (a known limitation, the owner's decision, Step 8d.5).** The service values come from French Mediterranean meadows (Campagne et al., € 2014), Italian divers (Zunino et al., € 2016–17), Medes Islands divers (Rodrigues et al.) and UK households (Börger et al., £ 2013, converted at the 2013 ECB rate); the carbon stocks come from Corsica and the burial rate from the Balearic Islands. No Catalan primary data are used for the values. Every transfer is a **unit-value transfer at face value**:
   - **no income adjustment**: willingness to pay is not scaled for the difference in income per head between the study population and Catalonia (no income elasticity is applied), so the transfer error from income differences is in the values unknown in size and sign;
   - **no price-year adjustment**: values are used in their own price year (2013–2017), not inflated to a common year, so in current euros they are understated by the general inflation since then, while the SCC is in 2020 euros (limitation 7).
   The owner chose not to adjust for now. The Monte Carlo ranges do not include these transfer errors.
5. **Scale and space.** The resource is the regional stock, treated as one homogeneous meadow. Depth, shoot density, wave exposure and distance to beaches, which all change a hectare's services and carbon, are not represented. The default 50 ha is illustrative.
6. **Carbon fate** (§5, §7): the release fraction and its half-life are project inputs; the defaults (0.63, 10 years) are a global assumption range and an inferred central half-life for matte left exposed. No Mediterranean measurement of the release rate from exposed *P. oceanica* matte was found.
7. **Currency.** The SCC is in 2020 euros and the services in 2014 euros, and the two are not harmonised; the benchmarks are not converted at all.
8. **Not varied:** the model-wide trophic and keystone constants, and the health weights.
9. **EXPERIMENTAL endogenous pricing** is quarantined and excluded. Since Step 8c.6 three sourced anchors (meadow, fisheries, coastal protection) determine every price through the network. The other seven prices are derived through placeholder edge strengths, labelled as such, and are not estimates.
10. **Restoration** evidence for *P. oceanica* is thin and mostly negative.

## 9. Reproducing the figures

```bash
gaia run posidonia                                   # deterministic run, benchmarks
gaia run posidonia --uncertainty                     # + Monte Carlo (1,000 draws, seed 20261012)
gaia run posidonia --uncertainty --format json --summary-only
gaia run posidonia --units N --unit-value G --uncertainty   # the user's project
gaia run posidonia --units N --unit-value G --area-ha M --resource-name "…" \
    --dive-intensity low --dive-site-share 0.2 \
    --matte-fate excavated                           # an excavated footprint in a meadow of M ha
gaia run posidonia --mode restore --units 50 --time-horizon 200
```

Every output lists every parameter with its source, confidence and, where documented, its range. Look in the text report's *Parameter Provenance* section, or in the JSON `calibration` block.

## 10. Questions for the reviewers

**Ecologist (Track 1).**
- Small losses are now priced linearly and the remaining meadow degrades past a threshold. Is that a defensible prior, and where would the threshold of a real meadow lie (fragmentation, patch size)?
- Is the agent and edge structure right? Are the six intermediate agents and the 15 edges the relevant ones?
- Which edges matter most, and is there evidence for their strengths?
- Is natural recolonisation (Kendrick et al. 2005) the right basis for the succession curve after transplanting?
- Which matte-loss fraction and half-life apply to a port or marina footprint (excavated vs. buried vs. exposed)? Is 10 years a defensible central half-life for matte left exposed?

**Environmental economist (Track 2).**
- Is the service ledger (each final service counted once, intermediate agents owning sourced shares moved from other agents, seascape services spread over the mapped seabed, a provisional assumption) the right way to price every agent without double counting?
- Is Campagne et al.'s per-hectare value transferable to Catalonia?
- Are the diving and non-use benefit transfers (Zunino et al. 2020, Rodrigues et al. 2016, Börger et al. 2014) acceptable, and which study should replace them or fill the remaining gaps (beach tourism, the meadow's existence value)?
- Is the SCC-based carbon valuation, with the release spread over time by a half-life and each year valued at that year's SCC, appropriate for an EIA? So are the normative settings: a declining 2.3% → 1.4% schedule, 1%/yr relative price change, 200-year horizon.
- Is treating the normative choices as sensitivities rather than distributions the right presentation for a decision-maker?
