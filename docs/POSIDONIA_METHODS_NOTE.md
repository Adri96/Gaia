# Valuing the loss of *Posidonia oceanica* meadows on the Catalan coast with Gaia: methods note

*Gaia v1.0 candidate case (Step 8.5 of `TOP_PRIORITIES_REPORT.md`). Draft for external review by an ecologist (Track 1: is the model structure defensible?) and an environmental economist (Track 2: are the values and their treatment defensible?). The parameter-by-parameter sources are in `docs/POSIDONIA_LITERATURE_REVIEW.md`. Figures below come from the case file `gaia/cases/data/posidonia.json` at the commit this note ships with. Every number can be reproduced with the commands in §9.*

---

## 1. The question

**User:** a Catalan coastal authority or marine NGO reviewing the environmental impact assessment of a port or marina expansion that would destroy part of a *P. oceanica* meadow. *P. oceanica* beds are a priority habitat (1120\*) under the EU Habitats Directive.

**Question:** if the project destroys *N* hectares of the Catalan *Posidonia* stock, what is the present value of the ecosystem services and carbon lost? How does it compare with the project's private gain, and with what uncertainty? Which inputs drive the answer?

The reference resource is the regional stock: 4,582 ha of *P. oceanica* mapped by the Generalitat de Catalunya in 2025, as reported. The default project destroys an illustrative 50 ha (1.1%) for a private gain of €2,500/ha (a placeholder; the user enters the project's own figure). Gaia answers with:

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

**Money.** At depletion D:
- annual externality = Σ_i effective_i(D) · w_i · v_i · area;
- ecosystem health = 1 − Σ_i w_i · effective_i(D).

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
| Carbon released | € one-off at year 0 | ha × top-metre matte carbon (1,199 tCO₂/ha) × fraction lost (0.63) × the social cost of carbon (€166.35/t: US EPA 2023, $190 for 2020 emissions at 2%, at the ECB 2020 rate) |
| Carbon burial lost | € PV | ha × 0.953 tCO₂/ha/yr × SCC(t), growing 1.3%/yr (EPA path) × DF(t) |
| Private gain | € one-off | Compared with the PV only, never with the €/yr flow |
| Net social cost | € PV | PV of externality − private gain; positive means society loses more than the project gains |

Carbon is valued only by the carbon module (decision D3): no agent value contains climate regulation.

## 4. Calibration regime and what the curves are

The ten damage curves are the same normalised logistic. Its inflection is at 32% loss, just past the 20% "safe threshold", and its steepness is 12. **No study relates the fraction of a Posidonia meadow lost to the fraction of each service lost.** The curves are therefore placeholders, read as each agent's direct dependency on the meadow, and the edges add the indirect part (calibration regime B). Two consequences matter for the question:

1. **At small losses the curve charges less than the average value of a hectare.** The normalised logistic starts with slope ≈ 0.25. With cascades and trophic amplification, the default run charges €126 per hectare lost per year, against an average of €285/ha/yr. That is 44% of what a linear benefit transfer (hectares × average value) would charge. The ratio grows with the loss: €153/ha/yr at 200 ha, €385 at the 20% "threshold", €610 at 44%. Reviewers should judge whether a convex, threshold-shaped response is the right prior for a seagrass meadow. The alternative is a linear one (each hectare delivers its own services), possibly with fragmentation effects. Both figures are reported.
2. **Health at the "safe" threshold is 0.67, and Gaia warns** (CalibrationWarning). No source supports calling the loss of 20% of a priority habitat safe. The warning is left in place rather than tuned away.

Single-pass cascades cut chains longer than one hop. Under regime B, the cascade part is therefore a structural lower bound.

## 5. Parameters and sources

A Posidonia extraction run records 59 parameters (69 with restoration). The literature review gives every one of them, with value, range, source and mapping. In summary:

**Service values (final services only).** These come from the primary *P. oceanica* valuation of Campagne et al. (2015, *Mar. Pollut. Bull.* 97:391–400, Table 2, € 2014/ha/yr):

| Service | €/ha/yr | Range |
|---|---|---|
| Coastal protection (damage cost avoided) | 188 | — |
| Water purification (benefit transfer) | 60 | — |
| Fisheries (production function) | 35 | 27–74; the upper end is derived from Jackson et al. 2015 |
| Bioindicator and knowledge | 1.83 | — |
| **Total** | **284.83** | |

The meadow, coralligenous, epiphytes and invertebrates are intermediate services: their value reaches people through the final services. A separate value would count it twice (Boyd & Banzhaf 2007; Fisher et al. 2009), so they carry no euro value. Megafauna and seabirds also carry none, because no per-hectare non-use estimate tied to *Posidonia* was found. All six keep their health weights and their edges. **Tourism, recreation and non-use values are not valued, so the services figure is a lower bound.**

**Carbon.**

| Parameter | Value | Source | Range |
|---|---|---|---|
| Burial | 0.953 tCO₂/ha/yr (26 g C/m²/yr) | Mazarrasa et al. 2017, Balearic Islands | 0.28–3.09 (Pergent-Martini et al. 2021) |
| Top-metre matte stock | 1,199 tCO₂/ha (327 t C/ha) | Monnier et al. 2022, the French Label Bas-Carbone default | 741–1,844 (Leduc et al. 2023) |
| Fraction lost on conversion | 0.63 | Pendleton et al. 2012 | 0.25–1.0 |
| Biomass | none counted separately | the leaves are negligible next to the matte | — |

On the fraction lost: the IPCC (2013) Wetlands Supplement treats excavation for port, harbour and marina construction as emitting the top-metre soil carbon (0.96).

**Unsourced, flagged.**
- The damage curves, threshold and steepness.
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
  - zero values;
  - the user's inputs: area, hectares destroyed, private gain;
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
| Annual externality (services), €/yr | 6,325 | 1,099 | 7,468 | 25,898 |
| PV services lost (200 yr) | 0.59 M | 0.10 M | 0.70 M | 2.42 M |
| PV carbon released (one-off) | 6.28 M | 3.63 M | 6.49 M | 10.01 M |
| PV carbon burial lost | 0.95 M | 0.59 M | 1.33 M | 2.52 M |
| **PV of externality** | **7.83 M** | **5.62 M** | **8.78 M** | **12.78 M** |
| **Net social cost** (− €125,000 private gain) | **7.70 M** | **5.49 M** | **8.66 M** | **12.65 M** |

*1,000 draws, seed 20261012. Base is the run at the documented values. P50 lies above base because several ranges are right-skewed (burial, release fraction, fisheries).*

**Drivers** (swing in net social cost between each parameter's P5 and P95):

| Parameter | Swing |
|---|---|
| Carbon release fraction | €5.1 M |
| Matte carbon stock | €4.0 M |
| Burial rate | €2.0 M |
| Curve steepness | €1.5 M |
| Safe threshold | €1.2 M |
| Coastal-protection value | €0.34 M |

The fisheries and water-quality values and the edge strengths each swing it by less than €0.15 M.

**Normative choices** (net social cost, base parameters):

| Choice | Net social cost |
|---|---|
| Market/ETS carbon price (€80/t) | €3.95 M |
| EPA SC-CO₂ at a 2.5% near-term rate ($120/t) | €5.04 M |
| EPA SC-CO₂ at a 1.5% near-term rate ($340/t) | €13.41 M |
| 2.0% constant discount rate | €7.57 M |
| No relative price change | €7.42 M |
| 100-year horizon | €7.10 M |

**Benchmarks** (per hectare per year):
- Gaia's service value at full damage, €285/ha/yr (€443 with carbon burial at the SCC), sits inside Campagne et al.'s 284–514 €/ha/yr (including carbon), as constructed.
- The Mediterranean seagrass meta-regression of Stamatiadou et al. (2025) has a basin mean of 8,712 Int$2020/ha/yr, about 20× higher. It includes recreation and tourism.
- The global syntheses for coastal systems and seagrass (de Groot et al. 2012; Costanza et al. 2014) are about 65× higher, mostly a transferred nutrient-cycling value.

**Reading.**
1. The externality of the default project is dominated by the carbon released from the matte, about €126,000 per hectare destroyed at the SCC. The PV of the valued services is about €11,800 per hectare charged.
2. The net social cost is positive across the P5–P95 range and under every normative choice tested. It is about 30–110 times the default private gain (ETS carbon price: 32×; P5: 44×; P95: 101×). To break even, a project would need a private gain of about €80,000 (ETS carbon price) to €270,000 per hectare: the PV of the externality per hectare, which is €112,000 at P5 and €256,000 at P95.
3. That conclusion rests mostly on the carbon terms, and their dominant uncertainty, the fraction of matte carbon released, depends on what the project physically does to the matte: excavation, burial under fill, or later erosion. The user's environmental impact assessment can resolve it far better than the literature can.

**Restoration** of the same 50 ha (`--mode restore --units 50 --time-horizon 200`, €200,000/ha including maintenance):
- net restoration value −€7.75 M (PV);
- only about €0.12 M of benefits within 200 years, because recolonisation is slow;
- the carbon breakeven price is far above any credible carbon price.

Destroying and then restoring is therefore much worse than not destroying: the destroy-then-restore penalty is €15.6 M in PV, about 125 times the foregone gain.

## 8. Limitations

1. **Static engine; no path dependence.** The timing of the works, the possibility of phased destruction, hysteresis after keystone collapse, and slower restoration after a delay are not represented. Option A (time axis and real-time substrate erosion → relaxation and keystone hysteresis → damage-dependent recovery) is a **committed milestone after v1.0** (`version_specs/V09_SPEC.md`). The data format is reserved for it (schema 2, `dynamics` block).
2. **Lower-bound valuation.** Tourism, recreation and non-use values are not valued. The total value of the services is at the bottom of the published range (§7).
3. **Unfitted response curves and edges** (§4). These are the main structural uncertainty for the services part, and they are outside the Monte Carlo bounds.
4. **Benefit transfer.** The service values come from French Mediterranean meadows (2014 euros, no price-year adjustment), the carbon stocks from Corsica, and the burial rate from the Balearic Islands. No Catalan primary data are used.
5. **Scale and space.** The resource is the regional stock, treated as one homogeneous meadow. Depth, shoot density, wave exposure and distance to beaches, which all change a hectare's services and carbon, are not represented. The default 50 ha is illustrative.
6. **Carbon fate** (§5, §7): the release fraction is a global assumption range.
7. **Currency.** The SCC is in 2020 euros and the services in 2014 euros, and the two are not harmonised; the benchmarks are not converted at all.
8. **Not varied:** the model-wide trophic and keystone constants, and the health weights.
9. **EXPERIMENTAL endogenous pricing** is quarantined and excluded.
10. **Restoration** evidence for *P. oceanica* is thin and mostly negative.

## 9. Reproducing the figures

```bash
gaia run posidonia                                   # deterministic run, benchmarks
gaia run posidonia --uncertainty                     # + Monte Carlo (1,000 draws, seed 20261012)
gaia run posidonia --uncertainty --format json --summary-only
gaia run posidonia --units N --unit-value G --uncertainty   # the user's project
gaia run posidonia --mode restore --units 50 --time-horizon 200
```

Every output lists every parameter with its source, confidence and, where documented, its range. Look in the text report's *Parameter Provenance* section, or in the JSON `calibration` block.

## 10. Questions for the reviewers

**Ecologist (Track 1).**
- Is a convex, threshold-shaped response to the fraction of meadow lost a defensible prior, or should small losses be linear per hectare?
- Is the agent and edge structure right? Are the six intermediate agents and the 15 edges the relevant ones?
- Which edges matter most, and is there evidence for their strengths?
- Is natural recolonisation (Kendrick et al. 2005) the right basis for the succession curve after transplanting?
- Which matte-loss fraction applies to a port or marina footprint (excavated vs. buried vs. exposed)?

**Environmental economist (Track 2).**
- Is final-services accounting with zero euro value on intermediate agents the right way to avoid double counting here?
- Is Campagne et al.'s per-hectare value transferable to Catalonia?
- Which recreation or non-use study should fill the main gap?
- Is the SCC-based carbon valuation with a one-off release at year 0 appropriate for an EIA? So are the normative settings: a declining 2.3% → 1.4% schedule, 1%/yr relative price change, 200-year horizon.
- Is treating the normative choices as sensitivities rather than distributions the right presentation for a decision-maker?
