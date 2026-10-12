# Case notes

The derivations behind the four shipped cases, moved verbatim from the
docstrings of the 0.9.0 case modules (`gaia/cases/<case>.py`) when the
cases became data files (`gaia/cases/data/<case>.json`, Step 7). The
parameter values, sources and confidence levels are in the JSON files,
and every output lists them; where a summary table below differs from
them, the JSON applies. Command lines are now `gaia run <case>`, with
`--total-units` for `--trees` / `--hectares`.

## Oak Valley Forest (`forest`)

```text
Provides a ready-to-run forest ecosystem with four agents, all using logistic
damage functions calibrated around the safe extraction threshold.

All parameters are PLACEHOLDERS pending scientific review. They are designed
to be in a plausible ballpark for a medium-sized temperate deciduous forest,
but are not calibrated against specific published studies.

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    Summary only. The gaia.provenance.Param objects in this module are the
    authoritative provenance and what every output reports (Step 5). Where
    they differ from the table, the Params apply: an owner specification
    or 'Spec' entry with no cited source is 'low', not 'Medium'.

    | Parameter               | Value         | Unit       | Source       | Confidence |
    |-------------------------|---------------|------------|--------------|------------|
    | total_units             | configurable  | trees      | Placeholder  | Low        |
    | reference area          | 40            | ha         | Placeholder  | Low        |
    | tree density            | 250           | trees/ha   | Placeholder  | Low        |
    | safe_threshold_ratio    | configurable  | ratio      | Placeholder  | Low        |
    | unit_value              | 100.0 €/tree  | €/tree     | Placeholder  | Low        |
    | annual_value_per_ha     | 2,848         | €/ha/yr    | de Groot 2012| Low        |
    |   (every agent)         |               |            |              |            |
    | logistic steepness      | 12.0          | dimensionless | Placeholder | Low      |
    | dependency weights      | 0.20/0.30/... | ratio      | Placeholder  | Low        |

Agent values are yearly flows per hectare (decisions D1, D2): every agent
uses the biome-level value below, and the dependency weights split it, so
sum(weight × value) = €2,848/ha/yr × area_ha at full damage
(€113,920/yr for the 40 ha reference forest).

The value is the order of magnitude of global meta-analyses for temperate
forests: de Groot et al. (2012), Ecosystem Services 1:50-61, Int$3,013/ha/yr
(2007 price level); Costanza et al. (2014), Global Environmental Change
26:152-158, $3,137/ha/yr (2007) — both figures to be re-checked against the
papers in Step 8. It is used at face value as €; currency and price-year
conversion, and a site-specific value, are pending (Step 8).
Carbon is valued only by gaia.carbon (decision D3), so the climate-regulation
service is taken out of the biome total: de Groot et al. (2012, supporting
material, Table 8.1, temperate forests) put it at Int$152/ha/yr, hence
€3,000 − €152 = €2,848/ha/yr. Rates are never tuned to produce an outcome
(an earlier version was back-solved so that externality < revenue at 30% and
> revenue at 50%).

Dependency weight sum: 0.20 + 0.30 + 0.15 + 0.35 = 1.00

Calibration regime: B, direct effects only (CalibrationRegime.DIRECT_ONLY;
PROJECT_DEFINITION.md, "Critical Modelling Assumption"):
    The four damage curves are the same placeholder logistic (steepness 12,
    inflection just past the safe threshold), not fitted to field data on
    total impact, so Option A — curves that already embed the indirect
    pathways — cannot be claimed. The curves are read as each agent's direct
    dependency on the forest, and the two interaction edges add the indirect
    part. B is what an uncalibrated curve implies, not a claim of lab or
    first-principles calibration. Incoming strengths are at most 0.20,
    within the in-degree cap of 1.0 (Step 3.8).

    Health at the 30% safe threshold is below 0.8 (≈0.73), so validation
    issues a CalibrationWarning. That is honest and has nothing to do with
    the edges (≈0.75 without them): the logistic alone puts ~21% direct
    damage at the threshold and trophic amplification multiplies it for
    Animal Populations. Fixing it means calibrating the curves (Step 8), not
    tuning parameters to silence the warning.
```

## Costa Brava Holm Oak Forest (`costa_brava`)

```text
Mediterranean forest ecosystem with 11 agents spanning the full web of
biological and physical dependencies: from the mycorrhizal underground
network to apex raptors and the coastal tourism economy.

Scientific context:
    Mediterranean forests operate under fundamentally different constraints
    than temperate ones. Summer drought is the defining limiting factor;
    regeneration is slower; fire risk creates positive feedback loops once
    canopy cover is lost. The safe extraction threshold (25%) is lower than
    a temperate forest (30%) for these reasons.

    The mycorrhizal network is modeled as a KEYSTONE agent — it is the
    underground infrastructure that conditions tree regeneration, soil
    nutrient cycling, and water acquisition. Its collapse cascades into
    every other biological agent.

    Fire & Microclimate Regulation uses an exponential (not logistic) damage
    function: once the canopy opens, drier and hotter stands burn more often
    and every fire opens the canopy further, a positive feedback with no
    "plateau." (The agent was "Carbon & Climate"; its carbon component is
    now valued by gaia.carbon alone, decision D3.)

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    Summary only. The gaia.provenance.Param objects in this module are the
    authoritative provenance and what every output reports (Step 5). Where
    they differ from the table, the Params apply: an owner specification
    or 'Spec' entry with no cited source is 'low', not 'Medium'.

    | Parameter                     | Value         | Unit    | Source        | Confidence |
    |-------------------------------|---------------|---------|---------------|------------|
    | total_units                   | configurable  | trees   | Placeholder   | Low        |
    | reference area                | 100           | ha      | Placeholder   | Low        |
    | tree density                  | 100           | trees/ha| Placeholder   | Low        |
    | safe_threshold_ratio          | 0.25          | ratio   | User spec      | Medium     |
    | unit_value                    | 60.0 €/tree   | €/tree  | User spec      | Medium     |
    | Canopy Trees weight           | 0.12          | ratio   | User spec      | Medium     |
    | Understory & Matorral weight  | 0.08          | ratio   | User spec      | Medium     |
    | Mycorrhizal Fungi weight      | 0.13          | ratio   | User spec      | Medium     |
    | Soil Microbiome weight        | 0.10          | ratio   | User spec      | Medium     |
    | Pollinators & Insects weight  | 0.10          | ratio   | User spec      | Medium     |
    | Forest Birds weight           | 0.08          | ratio   | User spec      | Medium     |
    | Forest Mammals weight         | 0.07          | ratio   | User spec      | Medium     |
    | Raptors & Apex Predators wt   | 0.04          | ratio   | User spec      | Medium     |
    | Watershed & Water Cycle wt    | 0.12          | ratio   | User spec      | Medium     |
    | Fire & Microclimate weight    | 0.10          | ratio   | User spec      | Medium     |
    | Human Communities weight      | 0.06          | ratio   | User spec      | Medium     |
    | annual_value_per_ha (all)     | 1,593         | €/ha/yr | de Groot 2012 | Low        |
    | logistic steepness            | 12.0          | –       | Placeholder   | Low        |
    | exponential base (fire)       | 2.0           | –       | Placeholder   | Low        |
    | dependency weight sum         | 1.00          | –       | Verified ✓    | High       |

Agent values (decisions D1, D2):
    Every agent uses the same yearly value per hectare and the dependency
    weights split it, so sum(weight × value) = €1,593/ha/yr × area_ha at full
    damage (€159,300/yr for the 100 ha reference forest).

    €1,600/ha/yr [PLACEHOLDER] is the global mean for woodlands in de Groot
    et al. (2012), Ecosystem Services 1:50-61 (Int$1,588/ha/yr, 2007 price
    level; figure to be checked against the paper in Step 8), used at face value
    as €; a Mediterranean holm-oak valuation and
    currency/price-year conversion are pending (Step 8). Carbon is valued
    only by gaia.carbon (decision D3), so the climate-regulation service is
    taken out of the total: Int$7/ha/yr for woodlands in de Groot et al.
    (2012, supporting material, Table 9.1; a single estimate), hence
    €1,600 − €7 = €1,593/ha/yr. The renamed Fire & Microclimate Regulation
    agent keeps its 0.10 share of that non-carbon total; Soil Microbiome's
    description no longer lists carbon storage — soil carbon is valued by
    gaia.carbon through soil_carbon_tonnes × soil_release_fraction, and the
    agent's value, a share of the non-carbon total, never contained it.

    An earlier version back-solved per-agent rates so that externality <
    revenue at 25% and > revenue at 50% ("calibrated", €3.5M in total);
    rates are never tuned to produce an outcome.

Dependency weights sum: 0.12+0.08+0.13+0.10+0.10+0.08+0.07+0.04+0.12+0.10+0.06 = 1.00 ✓

Calibration regime: B, direct effects only (CalibrationRegime.DIRECT_ONLY;
PROJECT_DEFINITION.md, "Critical Modelling Assumption"):
    Ten damage curves are the same placeholder logistic (steepness 12,
    inflection just past the 25% threshold) and Fire & Microclimate uses a
    placeholder exponential; none is fitted to field data on total impact,
    so Option A — curves that already embed the indirect pathways — cannot
    be claimed. The curves are read as each agent's direct dependency on the
    canopy, and the 17 interaction edges add the indirect part; single-pass
    propagation makes the result a structural lower bound for chains longer
    than one hop. B is what an uncalibrated curve implies, not a claim of
    lab or first-principles calibration.

    In-degree cap (Step 3.8, S2): the strengths into Understory & Matorral
    summed to 0.80, and to 1.35 once the Mycorrhizal and Pollinator keystone
    boosts fire, above the cap of 1.0. Its three incoming edges are divided
    by 1.35 (rounded down to 3 decimals) [PLACEHOLDER] — a mechanical
    rescaling that keeps their ratios, not a fit to any outcome.

    Health at the safe threshold is below 0.8, so validation issues a
    CalibrationWarning. That is honest: the logistic alone puts ~20% direct
    damage at the threshold, trophic amplification multiplies it for
    consumers, and fixing it means calibrating the curves (Step 8), not
    tuning edges to silence the warning.
```

## Posidonia oceanica meadows of Catalonia (`posidonia`)

The v1.0 case (decision D6). Since Step 8.2 every parameter is sourced or
flagged; the full review, with the value, range and mapping of each
parameter and a DOI or stable URL for every source, is
`docs/POSIDONIA_LITERATURE_REVIEW.md`, and the method is described in
`docs/POSIDONIA_METHODS_NOTE.md`. This section keeps the derivations.

**Reference resource.** The Catalan *P. oceanica* stock, 4,582 ha (the
Generalitat's 2025 marine habitat map, as reported); the unit is the
hectare, so 4,582 units. The default run destroys an illustrative 50 ha
(about 1.1% of the stock), the scale of a port or marina project (the
proposed first user, `PROJECT_DEFINITION.md` v1.0). Before Step 8 the case
used 5,000 ha, more than the whole Catalan stock, and 2,000 ha destroyed.

**Monetary semantics.** As in every case: agent values are yearly flows,
revenue is one-off (€2,500/ha, a project-specific placeholder the user
replaces with `--unit-value`), and they meet only through present values.

**Agent values: final services only (Step 8.2).** The euro values sit on
the four final services that a primary *P. oceanica* valuation measured
(Campagne et al. 2015, Table 2, € 2014/ha/yr): coastal protection 188,
water purification (wastewater treatment) 60, fisheries 35 (range 27–74,
the upper end derived from Jackson et al. 2015), and the cultural services
they could value, 1.83 (bioindicator use 1.5 + knowledge 0.33). Total
€284.83/ha/yr at full damage. Each is entered as
`annual_value_per_ha = service value / dependency_weight`, so that
weight × value is the sourced figure and the owner's weights keep their
role in the health index. The six ecological agents (the meadow itself,
coralligenous, epiphytes, invertebrates, megafauna, seabirds) carry no euro
value of their own: they are intermediate services whose value reaches
people through the final ones (Boyd & Banzhaf 2007; Fisher et al. 2009), or
non-use values for which no per-hectare estimate tied to *Posidonia* was
found. They keep their health weights and their edges, so their damage
still raises the damage of the final services. **The total is a lower
bound**: tourism, recreation and non-use values are not valued (Campagne et
al. say the same of their own figure). Before Step 8.2 the agent values
restated an owner specification (€1,066/ha/yr in total, no source).

**Carbon (S5, Step 8.2a).** Valued only by `gaia.carbon`:
- absorption 0.953 tCO₂/ha/yr, i.e. 26 g C/m²/yr of burial in Balearic
  meadows (Mazarrasa et al. 2017); range 0.28–3.09;
- release = 1,199 tCO₂/ha in the top metre of matte (327 t C/ha, Monnier
  et al. 2022, the French Label Bas-Carbone default) × 0.63 lost on
  conversion (Pendleton et al. 2012, range 0.25–1.0);
- no separate biomass term: leaves are negligible next to the matte, and
  living rhizomes lie inside it.

So 755 tCO₂ is released per hectare destroyed. The fraction depends on
what the project does to the matte (excavated, buried, or eroded later),
and it is the largest single source of uncertainty in the case.

**Damage curves, threshold, edges, keystone.** Unchanged placeholders:
- the same logistic for every agent (steepness 12, inflection at 32%,
  just past the 20% "safe" threshold), with nothing to fit it to;
- 15 hand-set edges; the links are documented (e.g. wave attenuation by
  the meadow, Infantes et al. 2012), their strengths are not;
- a keystone threshold of 0.3.

Calibration regime B: the curves are read as each agent's direct
dependency on the meadow, and the edges add the indirect part (a
structural lower bound for chains longer than one hop). In-degree cap:
every agent's incoming strengths sum to at most 0.80 with the keystone
boost, so no edge was changed.

**CalibrationWarning (health 0.67 at the 20% threshold) remains.** No
source supports a threshold-shaped response of Posidonia services to the
fraction of meadow lost, and none supports a "safe" loss of 20% of a
priority habitat. Fixing the warning would mean tuning placeholders to
silence it. The warning is the honest signal that 20% is not safe. For
small losses, which is the user's question, the curve gives each hectare
about a quarter of its average per-hectare value (initial slope 0.25).
That is why the review reports, next to Gaia's figure, the linear
benefit transfer (N ha × €284.83/ha/yr).

**Restoration and succession.**
- Planting cost €50,000/ha: of the order of the median marine
  restoration cost (Bayraktarov et al. 2016), low confidence.
- Maintenance: placeholders.
- Succession from an agent-based model of natural recolonisation
  (Kendrick et al. 2005): limited cover after a century, a plateau after
  400 years, two-thirds cover after 600, so restoration recovers little
  within the 200-year horizon.
- Transplant survival is low: 38% median for seagrass, 0–31% on disturbed
  substrate.

**Discounting.** 2.3% (the mean social discount rate recommended by ~200
experts, Drupp et al. 2018), declining to 1.8% and 1.4% (placeholders,
normative). Scarcity uplift 1%/yr, the Dutch default reported by Drupp et
al. 2024, whose own aggregate estimate (1.66%) would make the 200-year PV
diverge. The uncertainty analysis treats these as normative sensitivities,
not as random parameters.

**EXPERIMENTAL pricing.** Pricing requires a positive anchor for every
agent. The six agents without a euro value get their former
owner-specified impacts as PLACEHOLDER anchors. Pricing is quarantined and
is not part of the v1.0 output.

**Context.**
- *P. oceanica* meadows regressed by an estimated 34% in the last 50 years
  across the Mediterranean (Telesca et al. 2015).
- Exploited fish in the Medes Islands no-take reserve took 25–35 years to
  reach carrying-capacity biomass (García-Rubies et al. 2013). An earlier
  version of these notes claimed "80× higher fish biomass inside the
  reserve". No source was found for it, so it is removed.

## Central Amazon Old-Growth Lowland Forest (`amazon_forest`)

```text
Tropical forest ecosystem with 11 agents spanning the full trophic web:
from mycorrhizal fungi (the nutrient gateway on depleted Oxisol) to
apex predators (jaguars, harpy eagles) and the aquatic river system.

Scientific context:
    The Amazon represents the world's highest-productivity terrestrial
    ecosystem on one of its most nutrient-depleted soils — a paradox that
    makes it uniquely interesting for Gaia's substrate-dependent modeling.

    The forest's survival depends entirely on rapid nutrient recycling
    through mycorrhizal networks; destroy the biological layer and the
    laterite substrate cannot support recovery. The destruction:recovery
    ratio (~3000:1 for cultivated land) is the most extreme in any Gaia case.

    Mycorrhizal Fungi are the KEYSTONE agent — 60% of the basin sits on
    P-depleted Oxisols where phosphorus limitation is the primary constraint
    on productivity (Nature 2022, AFEX experiment). Without mycorrhizae,
    the forest literally cannot access the nutrients it needs.

    The Amazon also features atmospheric moisture feedback: intact forest
    generates its own rainfall via "flying rivers." This dual feedback
    (substrate + moisture) produces a sharper degradation spiral than
    any Mediterranean case. This is captured indirectly via the substrate
    threshold function and high erosion asymmetry.

Parameter documentation (per ROADMAP.md Verification & Scientific Validation Strategy):

    Summary only. The gaia.provenance.Param objects in this module are the
    authoritative provenance and what every output reports (Step 5). Where
    they differ from the table, the Params apply: an owner specification
    or 'Spec' entry with no cited source is 'low', not 'Medium'.

    | Parameter                     | Value         | Unit    | Source        | Confidence |
    |-------------------------------|---------------|---------|---------------|------------|
    | total_units                   | 400,000       | trees   | Spec §2       | Medium     |
    | reference area                | 1,000         | ha      | Spec §1       | Medium     |
    | tree density                  | 400           | trees/ha| Spec §2       | Medium     |
    | safe_threshold_ratio          | 0.20          | ratio   | Spec §6       | Medium     |
    | unit_value                    | 1.50 €/tree   | €/tree  | Calibrated    | Low        |
    | Canopy Trees weight           | 0.15          | ratio   | Spec §3       | Medium     |
    | Understory weight             | 0.08          | ratio   | Spec §3       | Medium     |
    | Mycorrhizal Fungi weight      | 0.15          | ratio   | Spec §3       | Medium     |
    | Soil Decomposers weight       | 0.10          | ratio   | Spec §3       | Medium     |
    | Pollinators weight            | 0.09          | ratio   | Spec §3       | Medium     |
    | Seed Dispersers weight        | 0.08          | ratio   | Spec §3       | Medium     |
    | Herbivores weight             | 0.07          | ratio   | Spec §3       | Medium     |
    | Mesopredators weight          | 0.05          | ratio   | Spec §3       | Medium     |
    | Apex Predators weight         | 0.03          | ratio   | Spec §3       | Medium     |
    | Aquatic System weight         | 0.10          | ratio   | Spec §3       | Medium     |
    | Epiphytes & Bromeliads weight | 0.10          | ratio   | Spec §3       | Medium     |
    | logistic steepness            | 12.0          | –       | Placeholder   | Low        |
    | dependency weight sum         | 1.00          | –       | Verified ✓    | High       |

Agent values (decisions D1, D2):
    Every agent uses €580/ha/yr and the dependency weights split it, so
    sum(weight × value) = €580/ha/yr × area_ha at full damage (€580,000/yr
    for the 1,000 ha reference area) [PLACEHOLDER].

    €580/ha/yr is the sum of the non-carbon spec §8 anchors for 1,000 ha:
    water cycling €150k + fisheries €20k + biodiversity/habitat €410k =
    €580k/yr. Carbon is valued only by gaia.carbon (decision D3), so the
    carbon anchors (stock protection €508k, sequestration €88k, REDD+) are
    gone. The former €840/ha/yr had no derivation of its own (the anchors,
    carbon included, summed to ~€1,160/ha/yr), so the agent value was
    brought to the documented anchors, not the reverse — see
    definitions/AMAZON_FOREST.md §8. For scale, de Groot et
    al. (2012) report a global tropical-forest mean of Int$5,264/ha/yr
    (2007), of which climate regulation is Int$2,044.

    Revenue (€1.50/tree) is one-off; it is compared with the present value of
    the yearly externality, never with the €/yr figure.

Dependency weights sum: 0.15+0.08+0.15+0.10+0.09+0.08+0.07+0.05+0.03+0.10+0.10 = 1.00 ✓

Calibration regime: B, direct effects only (CalibrationRegime.DIRECT_ONLY;
PROJECT_DEFINITION.md, "Critical Modelling Assumption"):
    All 11 damage curves are the same placeholder logistic (steepness 12,
    inflection just past the 20% threshold), not fitted to field data on
    total impact, so Option A — curves that already embed the indirect
    pathways — cannot be claimed. The curves are read as each agent's direct
    dependency on the canopy, and the 34 interaction edges add the indirect
    part; single-pass propagation makes the result a structural lower bound
    for chains longer than one hop. B is what an uncalibrated curve implies,
    not a claim of lab or first-principles calibration.

    In-degree cap (Step 3.8, S2): the spec §3 strengths into Canopy Trees
    summed to 1.40 (2.10 once the Mycorrhizal and Pollinator keystone
    boosts fire) and into Understory to 1.05 (1.45), above the cap of 1.0;
    with the former additive cascade, damage saturated (health 0.003 at 40%
    depletion, zero marginal cost from 50% to 100%). Every edge into those
    two agents is divided by the same factor (2.10, 1.45; rounded down to 3
    decimals) [PLACEHOLDER] — a mechanical rescaling that keeps their
    ratios, not a fit to any outcome.

    Health at the safe threshold is below 0.8, so validation issues a
    CalibrationWarning. That is honest: the logistic alone puts ~17% direct
    damage at the threshold, trophic amplification multiplies it for
    consumers, and fixing it means calibrating the curves (Step 8), not
    tuning edges to silence the warning.
```
