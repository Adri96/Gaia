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

A Posidonia extraction run records 60 parameters (70 with restoration): 26 sourced (22 by DOI or arXiv id, 4 by an official URL) and 44 flagged (34 placeholders, 10 owner weights). The literature review gives every one of them, with value, range, source and mapping. In summary:

**Service values: the service ledger (Step 8c.2).** Every agent carries euros, and each final service is counted once, owned by one agent. Intermediate agents get a sourced share of a final service moved from another agent, so the total is unchanged (Boyd & Banzhaf 2007; Fisher et al. 2009). € /ha/yr at full damage:

| Agent | Final service | €/ha/yr | Source (method) |
|---|---|---|---|
| Coastal Protection | protection from coastal erosion | 188 | Campagne et al. 2015 (damage cost avoided) |
| Water Quality | water purification | 60 | Campagne et al. 2015 (benefit transfer) |
| Fish Populations | fisheries, fish species (14/16 of 35) | 30.63 | Campagne et al. 2015 (production function); range up to 74 × 14/16, from Jackson et al. 2015 |
| Marine Invertebrates | fisheries, sea urchin and cuttlefish (2/16 of 35) | 4.38 | Campagne et al. 2015 (moved from fish; share by species count) |
| Human Communities | bioindicator use (3/3.5 of 1.5) and knowledge (0.33) | 1.62 | Campagne et al. 2015; PREI weights, Gobert et al. 2009 |
| Epiphytes & Algae | bioindicator use, epiphyte metric (0.5/3.5 of 1.5) | 0.21 | Gobert et al. 2009 (moved from Human Communities) |
| Posidonia Meadow | recreational diving: the meadow's amenity | 454.52 | Zunino et al. 2020, −€34.71 per dive for total loss × ~60,000 Medes dives/yr ÷ 4,582 ha (transfer from Italian divers) |
| Coralligenous & Red Coral | recreational diving: coralligenous | 18.95 | Rodrigues et al. 2016, −€60 per dive for gorgonian extinction (Medes) × 60,000 ÷ 190,000 ha of mapped seabed |
| Marine Megafauna | non-use: protecting marine mammals | 30.18 | Börger et al. 2014 (UK choice experiment, £30.32/household/yr for 5 years), annualised, × Catalan households ÷ 190,000 ha, half of a bundled attribute |
| Seabirds | non-use: protecting seabirds | 30.18 | the other half |
| **Total** | | **818.66** | |

Services of the meadow itself are spread over the meadow area. Services of the wider seascape (coralligenous diving, the non-use values of mobile species) are spread evenly over the mapped Catalan seabed to 50 m (~190,000 ha), an attribution assumption that the owner accepted as **provisional** (Step 8d.3; labelled so in the provenance). The recreation and non-use entries are low-confidence benefit transfers with wide ranges (literature review §2). **Beach tourism and the meadow's own existence value are still not valued, so the total is a lower bound.**

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
| `buried` | The matte is covered by fill (breakwaters, reclaimed land). Kept without oxygen, it probably keeps most of its carbon. | 0.125 | 10 yr | **inferred, no source**: the midpoint of the inferred 0–0.25 range; the half-life is the exposed default |

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
| Annual externality (services), €/yr | 40,933 | 37,892 | 52,975 | 77,138 |
| PV services lost (200 yr) | 3.83 M | 3.55 M | 4.96 M | 7.22 M |
| PV carbon released (10-yr half-life) | 5.56 M | 3.02 M | 5.59 M | 9.12 M |
| PV carbon burial lost | 0.95 M | 0.57 M | 1.37 M | 2.57 M |
| **PV of externality** | **10.35 M** | **8.73 M** | **12.31 M** | **15.98 M** |
| **Net social cost** (− €125,000 private gain) | **10.22 M** | **8.61 M** | **12.19 M** | **15.85 M** |

*1,000 draws, seed 20261012. Base is the run at the documented values. P50 lies above base because several ranges are right-skewed: the meadow's diving value, burial, the non-use values, the release fraction. The base annual externality is exactly 50 ha × €818.66/ha/yr, because below the threshold small losses are priced linearly (§4).*

**Drivers** (swing in net social cost between each parameter's P5 and P95):

| Parameter | Swing |
|---|---|
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
| Market/ETS carbon price (€80/t) | €6.84 M |
| EPA SC-CO₂ at a 2.5% near-term rate ($120/t) | €7.82 M |
| EPA SC-CO₂ at a 1.5% near-term rate ($340/t) | €15.36 M |
| 2.0% constant discount rate | €10.03 M |
| No relative price change | €8.41 M |
| 100-year horizon | €8.50 M |

**Benchmarks** (per hectare per year):
- Gaia's service value at full damage is €819/ha/yr (€977 with carbon burial at the SCC). That is about 2.9× Campagne et al.'s non-carbon services, because the ledger adds recreation and non-use values to theirs.
- The Mediterranean seagrass meta-regression of Stamatiadou et al. (2025) has a basin mean of 8,712 Int$2020/ha/yr, about 11× higher. It includes recreation and tourism.
- The global syntheses for coastal systems and seagrass (de Groot et al. 2012; Costanza et al. 2014) are about 35× higher, mostly a transferred nutrient-cycling value.

**Reading.**
1. Carbon and services now weigh about the same for the default project. Per hectare destroyed:
   - the release costs about €111,000 in PV (SCC, 10-year half-life);
   - the services charged cost about €77,000 in PV;
   - the foregone burial costs about €19,000 in PV.
2. The net social cost is positive across the P5–P95 range and under every normative choice tested. It is about 55–125 times the default private gain (ETS carbon price: 55×; P5: 69×; P95: 127×). To break even, a project would need a private gain of about €140,000 (ETS carbon price) to €320,000 per hectare: the PV of the externality per hectare, which is €175,000 at P5 and €320,000 at P95.
3. That conclusion rests on two uncertain terms:
   - the fraction and timing of the matte carbon release, which the user's environmental impact assessment can resolve (`--matte-fate`): excavated matte (0.96, at once) raises the release to about €191,000 per hectare;
   - the meadow's diving value, a benefit transfer that a Catalan valuation should replace.

**Restoration** of the same 50 ha (`--mode restore --units 50 --time-horizon 200`, €200,000/ha including maintenance):
- net restoration value −€7.51 M (PV);
- only about €0.36 M of benefits within 200 years, because recolonisation is slow;
- the carbon breakeven price is far above any credible carbon price.

Destroying and then restoring is therefore much worse than not destroying: the destroy-then-restore penalty is €17.9 M in PV, about 143 times the foregone gain.

## 8. Limitations

1. **Static engine; no path dependence.** The timing of the works, the possibility of phased destruction, hysteresis after keystone collapse, and slower restoration after a delay are not represented. Option A (time axis and real-time substrate erosion → relaxation and keystone hysteresis → damage-dependent recovery) is a **committed milestone after v1.0** (`version_specs/V09_SPEC.md`). The data format is reserved for it (schema 2, `dynamics` block).
2. **Lower-bound valuation.** Beach tourism and the meadow's own existence value are not valued. The recreation and non-use values in the ledger are benefit transfers (Italian and UK studies, the Medes Islands' dive counts, an attribution rule for seascape services). The total value of the services sits in the lower part of the published range (§7).
3. **Unfitted response curves and edges** (§4). These are the main structural uncertainty for the services part, and they are outside the Monte Carlo bounds.
4. **Benefit transfer.** The service values come from French Mediterranean meadows (2014 euros, no price-year adjustment), the carbon stocks from Corsica, and the burial rate from the Balearic Islands. No Catalan primary data are used.
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
