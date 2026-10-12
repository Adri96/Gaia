# Gaia — Externality Computation Framework

> **Profits are privatized, but externalities are socialized.**
>
> Gaia makes those externalities visible, measurable, and expressible in monetary terms — in both directions.

> **Status: illustrative and uncalibrated.** Gaia is a research prototype
> whose results are **not real-world estimates**. Most of its parameters are
> placeholders or low-confidence values (counts per case in the table
> below). Every output says so: the text report opens with an `ILLUSTRATIVE`
> banner and ends with a *Parameter Provenance* section, and the JSON output
> starts with a `calibration` block listing every parameter with its value,
> unit, source and confidence. The numbers on this page test the model's
> internal consistency, not the world.

Gaia is a Python library for simulating the hidden costs that private actors impose on ecosystems and society when they extract a shared natural resource, and the hidden *value* recovered when the resource is restored. It is pure Python, standard library only.

---

## What Gaia does

A timber company that cuts 5,000 trees books the revenue. The water quality, habitat, pollination and carbon storage lost by everyone else appear in no account. Gaia puts a number on them, with explicit units:

- **Extraction mode** removes units of a resource (trees, hectares of seagrass) one at a time, computes how much of each dependent agent's yearly service is lost, and reports the **yearly externality (€/yr)**, its **present value (€ PV)** including carbon, and the **net social cost** = PV of the externality − the one-off private revenue.
- **Restoration mode** starts from a degraded state, replants some of the lost units, and reports the **recovered yearly value**, the **net present value** of the restoration, the **maturation gap** while succession proceeds, and the **destroy-then-restore penalty**: what cutting and later restoring costs society compared with not cutting.

Four cases are included: a temperate forest, a Mediterranean holm-oak forest, the *Posidonia oceanica* meadows of the Catalan coast (Costa Brava) and a Central Amazon rainforest patch. Posidonia is the v1.0 case (decision D6): every parameter is sourced or flagged (`docs/POSIDONIA_LITERATURE_REVIEW.md`), its results come with Monte Carlo bounds (`--uncertainty`), and a methods note awaits external review (`docs/POSIDONIA_METHODS_NOTE.md`).

---

## Example output

These blocks are generated from the code by `scripts/gen_readme_examples.py`; a test fails when they drift.

Default run of each case (extraction):

<!-- BEGIN:example name="cases" table="cases" -->
| Case (default run) | Extracted | Revenue (€, one-off) | Annual externality (€/yr) | PV of externality (€ PV) | Health after | Placeholder or low-confidence parameters |
|---|---|---|---|---|---|---|
| Oak Valley Forest (temperate): `gaia run forest` | 5,000 of 10,000 (50%) | 500,000 | 95,050 | 10,111,613 | 16.6% | 24 of 27 |
| Costa Brava Holm Oak Forest (Mediterranean): `gaia run costa_brava` | 4,000 of 10,000 (40%) | 240,000 | 121,767 | 8,801,892 | 23.6% | 51 of 55 |
| Posidonia oceanica, Catalan coast (marine; the v1.0 case): `gaia run posidonia` | 50 of 4,582 (1%) | 125,000 | 40,933 | 10,345,456 | 98.9% | 49 of 60 |
| Central Amazon (tropical): `gaia run amazon_forest` | 80,000 of 400,000 (20%) | 120,000 | 177,757 | 38,814,713 | 69.4% | 66 of 71 |
<!-- END:example -->

The forest case in full (the same run as the first row):

<!-- BEGIN:example name="forest-extract" cmd="gaia run forest --total-units 10000 --units 5000" -->
```text
$ gaia run forest --total-units 10000 --units 5000
===============================================================
  ILLUSTRATIVE: 24 of 27 recorded parameters are placeholders
  (22) or low-confidence (2). Results are not real-world
  estimates. See "Parameter Provenance" at the end.
===============================================================
  GAIA — Externality Report: Oak Valley Forest
===============================================================

  Resource:              10,000 units  (Oak Valley Forest)
  Area:                    40.0 ha     (250.0 units/ha)
  Safe Threshold:         3,000 units  (30.0%)
  Units Extracted:        5,000
  Depletion:              50.0%
  Ecosystem Health:       16.6%

  ── Private Gains ───────────────────────────────────────────────
  Revenue:                                     500,000.00€ (one-off)

  ── Annual Externalized Costs ───────────────────────────────────
  Human Communities:                            17,788.95€/yr
    → Health costs, water treatment, lost recreation
    → Direct: €17,234/yr | Cascade: €555/yr
  Animal Populations:                           34,176.00€/yr
    → Habitat loss, population decline, species loss
    → Trophic amplification: 1.6× (primary consumer)
  Vegetation & Flora:                           12,925.45€/yr
    → Soil erosion, pollination network disruption
  Watershed & Local Climate:                    30,159.39€/yr
    → Watershed degradation, loss of local cooling and humidity regulation

  ANNUAL EXTERNALITY:                           95,049.79€/yr
  PV OF EXTERNALITY:                        10,111,612.54€ (PV)
    (services and carbon over 100 years; see NPV Analysis)
    Horizon sensitivity (€ PV):
      50-year horizon:                   €     5,860,652
      100-year horizon:                  €    10,111,613
      200-year horizon:                  €    16,677,102
  ---------------------------------------------------------------
  NET SOCIAL COST (PV − revenue):            9,611,612.54€ (PV)

  ── Resilience Assessment ───────────────────────────────────────
  Current zone:          ⚠⚠ RED — Resilience likely compromised
  Model confidence:      51%
  Zone transitions:
    Green → Yellow at step 2,001 (20% depletion)
    Yellow → Red at step 3,000 (30% depletion)

  ── Carbon Accounting ───────────────────────────────────────────
  Carbon released (biomass+soil):               4,375 t CO₂
  Future absorption lost:                       110.0 t CO₂/yr
  Carbon price (year 0):                       166.35€/t CO₂
  Carbon externality (release):                727,762.21€ (one-off)
  Carbon externality (absorption lost):      1,159,533.20€ (PV)

  ── Substrate Impact Assessment ────────────────────────────────
  Substrate type:                          terrestrial_soil
  Pristine soil depth:                           45.0 cm
  Capacity lost:                                  0.0%

  Pristine K:                                  10,000 units
  Current K:                                    9,997 units
  Capacity lost permanently:                        3 units
  Years to pristine substrate:                      2 years

  ── NPV Analysis (100-year horizon) ─────────────────────────────

  Discount rate: 2.3%
  Ramsey components (reference): δ=0.5%, η=1.35, g=1.3%
  Scarcity uplift: 2.0%/yr on ecosystem services
  Carbon price: €166/t growing at 1.3%/yr
    (social cost of carbon, US EPA 2023)

  Externality present value (€ PV at year 0):
    Ecosystem services (annual flow):    €     8,224,317
    Carbon released (one-off):           €       727,762
    Absorption lost (annual flow):       €     1,159,533
    ==================================== ===============
    Total extraction PV:                 €    10,111,613
    of which unrecoverable (substrate):  €         2,402
      (part of the services PV that restoration cannot recover; not added)

  ── Parameter Provenance ────────────────────────────────────────
  Calibration regime: B (direct effects only): damage curves are
  read as each agent's direct dependency, interaction edges add
  the indirect part.
  27 parameters recorded: 0 high, 3 medium, 2 low, 22
  placeholder, 0 user-supplied.
  Placeholders and low-confidence values (full list with sources:
  --format json, "calibration"):
    [placeholder] model.trophic_transfer_efficiency = 0.15 ratio
        Midpoint of the 5-20% energy transfer efficiency between
        trophic levels (the textbook range following Lindeman
        1942; from memory, verify). The midpoint is a choice, not
        a measurement.
    [placeholder] model.trophic_amplification_exponent = 0.25
    exponent
        No source: damps the pyramid ratio to 1.6-4.1×
        amplification for trophic levels 1-3.
    [placeholder] resource.area_ha = 40 ha
        Units / reference density of 250 trees/ha. Chosen so the
        per-tree carbon gives ~200 t CO2/ha.
    [placeholder] resource.unit_value = 100 €/tree
        Revenue per tree felled (one-off); no market source.
    [placeholder] resource.safe_threshold_ratio = 0.3 ratio
        Safe extraction threshold; also the inflection of every
        damage curve.
    [placeholder] 4 × agent[…].dependency_weight = 0.15-0.35
    share
    [placeholder] damage.logistic_steepness = 12 dimensionless
        The same placeholder curve for every agent, inflection
        just past the safe threshold; not fitted to field data
        (hence calibration regime B).
    [placeholder] 2 × edge[…].strength = 0.1-0.2 fraction of
    source damage
    [placeholder] carbon: stored_carbon_tonnes = 0.8 tCO2/tree;
    annual_absorption_tonnes = 0.022 tCO2/tree/yr;
    soil_carbon_tonnes = 0.3 tCO2/tree; soil_release_fraction =
    0.25 fraction
        Pending calibration against IPCC forest carbon data.
    [placeholder] substrate: soil_depth_cm = 45 cm;
    erosion_rate_unprotected = 15 t/ha/yr; erosion_rate_protected
    = 0.5 t/ha/yr; formation_rate = 0.8 t/ha/yr; erosion_alpha =
    2 exponent
        Pending calibration against regional soil survey data.
    [placeholder] discount.horizon_years = 100 years
        A modelling choice; the outputs also report the PV at 50,
        100 and 200 years (horizon sensitivity).
    [low] agents.annual_value_per_ha = 2,848 €/ha/yr
        Source: de Groot et al. (2012), Ecosystem Services
        1:50-61: temperate forest Int$3,013/ha/yr; Costanza et
        al. (2014), Global Environmental Change 26:152-158:
        $3,137/ha/yr (2007); minus climate regulation Int$152 (de
        Groot 2012, SM Table 8.1).
        Every agent; the dependency weights split it. Figures
        partly from memory, to be checked against the papers
        (Step 8); 2007 Int$ used as € with no currency or price-
        year conversion; a global biome mean, not a site
        valuation.
    [low] discount.scarcity_rate = 0.02 1/yr
        2% relative price change of ecosystem services. Above the
        estimates of Drupp et al. (2024), 1.28%/yr for forests
        (CI 0.85-1.70) and 1.66%/yr aggregate (CI 1.40-1.92);
        kept until Step 8. Below the discount rate, so the PV
        converges.
  ===============================================================
```
<!-- END:example -->

Restoring half of a clear-cut forest (500 of 1,000 lost trees), with a 60-year maturation timeline; the Parameter Provenance section is cut from this excerpt:

<!-- BEGIN:example name="forest-restore" cmd="gaia run forest --total-units 1000 --units 500 --units-lost 1000 --mode restore --time-horizon 60" until="── Parameter Provenance" -->
```text
$ gaia run forest --total-units 1000 --units 500 --units-lost 1000 --mode restore --time-horizon 60
===============================================================
  ILLUSTRATIVE: 34 of 37 recorded parameters are placeholders
  (32) or low-confidence (2). Results are not real-world
  estimates. See "Parameter Provenance" at the end.
===============================================================
  GAIA — Restoration Report: Oak Valley Forest
===============================================================

  Resource:                         1,000 units  (Oak Valley Forest)
  Area:                               4.0 ha
  Units Lost (start):               1,000
  Units Restored:                     500
  Restoration Coverage:             50.0%  of total capacity
  Depletion:                       100.0%  → 50.0%
  Ecosystem Health:                  0.0%  → 5.7%  (at maturity)

  ── Restoration Costs ───────────────────────────────────────────
  Planting cost/unit:                           50.00€
  Maintenance/unit/year:                        10.00€/yr
  Maintenance years:                               10
  Total cost/unit:                             150.00€
  TOTAL RESTORATION COST:                       75,000.00€ (one-off)

  ── Recovered Ecosystem Services ────────────────────────────────
  Human Communities:                               170.51€/yr
    → Health costs, water treatment, lost recreation
  Animal Populations:                                0.00€/yr
    → Habitat loss, population decline, species loss
  Vegetation & Flora:                              142.09€/yr
    → Soil erosion, pollination network disruption
  Watershed & Local Climate:                       331.55€/yr
    → Watershed degradation, loss of local cooling and humidity regulation

  Damage reversal (upper bound):                 1,887.02€/yr
    (annual externality before − after restoring, same damage model)
  ANNUAL RECOVERED VALUE:                          644.15€/yr
  ---------------------------------------------------------------
  NET RESTORATION VALUE:                        36,974.50€ (PV)
    (PV of recovered services and carbon − PV of restoration costs)
    Horizon sensitivity (€ PV):
      50-year horizon:                   €       -32,406
      100-year horizon:                  €        36,974
      200-year horizon:                  €       121,904

  ── Restoration Cost Ratio ──────────────────────────────────────
  (Revenue + restoration cost) / revenue:        2.50
    (= 1 + restoration cost per unit / unit value: a ratio of two
     input prices, no ecology; see Destroy-then-Restore Penalty)

  ── Maturation Timeline ─────────────────────────────────────────
  Years to first services:                          2 years
  Years to 50% service recovery:                   31 years
  Years to 90% service recovery:                   48 years

  ── Maturation Gap ──────────────────────────────────────────────
  Lost services during maturation:              18,598.55€ (PV)
  (discounted services not delivered while succession proceeds,
   over the 100-year NPV horizon)

  ── Carbon Recovery ─────────────────────────────────────────────
  Cumulative CO₂ absorbed:                        325 t CO₂
  Over  60 years of maturation

  ── Substrate Restoration Ceiling ──────────────────────────────
  Max recoverable services:                      99.9% of pristine
  Biological restoration capped at substrate ceiling.
  Substrate recovery time:                          7 years

  ── Investment Analysis (NPV, 100-year) ─────────────────────────
  Restoration cost (PV):                   €        69,216
  Service recovery (PV):                   €        37,138
  Carbon absorption (PV):                  €        69,053
  Total benefits (PV):                     €       106,191
  ---------------------------------------------------------------
  Net Present Value:                       €        36,974
  ROI (benefits / cost):                             1.53x
  Carbon payback:                                      71 years

  ── Carbon Credit Breakeven ─────────────────────────────────────
  Breakeven price:                         €      345.70/t CO₂
  Carbon price (year 0):                   €      166.35/t CO₂
  Gap to current:                          €      179.35/t CO₂
  Profitable at current price:                         No
  Projected breakeven year:                            57

  ── Destroy-then-Restore Penalty (€ PV, 100-year) ───────────────
  Social cost of cutting these units and restoring them, over
  not cutting them:
    Restoration cost:                      €        69,216
    Maturation gap (temporary):            €        18,599
    Substrate loss (permanent):            €            51
    Recovery shortfall (permanent):        €       107,490
    Carbon not recovered:                  €       119,677
    ====================================== ===============
    Penalty:                               €       315,032
    Foregone revenue (PV of not cutting):  €        50,000
    Penalty per € of foregone revenue:                6.30
  [... excerpt: the output continues with '── Parameter Provenance']
```
<!-- END:example -->

The JSON output starts with the calibration status:

<!-- BEGIN:example name="posidonia-json" cmd="gaia run posidonia --format json --summary-only" json="mode,calibration.status,calibration.statement,calibration.calibration_regime,calibration.n_params,calibration.n_placeholder,calibration.n_low,calibration.n_medium,summary.annual_externality_eur_yr,summary.pv_externality_eur_pv,summary.net_social_cost_eur_pv" -->
`$ gaia run posidonia --format json --summary-only` (excerpt):

```json
{
  "mode": "extraction",
  "calibration": {
    "status": "illustrative",
    "statement": "ILLUSTRATIVE: 49 of 60 recorded parameters are placeholders (29) or low-confidence (20). Results are not real-world estimates.",
    "calibration_regime": "B",
    "n_params": 60,
    "n_placeholder": 29,
    "n_low": 20,
    "n_medium": 11
  },
  "summary": {
    "annual_externality_eur_yr": 40933.18,
    "pv_externality_eur_pv": 10345455.73,
    "net_social_cost_eur_pv": 10220455.73
  }
}
```
<!-- END:example -->

---

## What the numbers mean

**Units.** Every monetary figure carries its unit, in the text report and as a JSON key suffix:

| Quantity | Unit | Text | JSON suffix |
|---|---|---|---|
| Agent value, externality, recovered value | € per year (a flow) | `€/yr` | `_eur_yr` |
| Present value of a flow (plus carbon) | € at year 0 | `€ (PV)` | `_eur_pv` |
| Revenue, restoration cost, carbon release at once | € once (a stock) | `€ (one-off)` | `_eur` |
| Agent value per hectare | € per ha per year | `€/ha/yr` | `_eur_per_ha_yr` |

A yearly flow is never added to, or compared with, a one-off amount. Revenue is compared only with the present value of the yearly externality: `net_social_cost = pv_externality − revenue` (positive: society loses more than the extractor gains).

**Agent values are €/ha/yr × area.** Each agent has an `annual_value_per_ha`, the service it would lose per hectare and per year at full damage, and the resource has a required `area_ha`. The yearly cost of an agent is `effective damage × dependency weight × annual_value_per_ha × area_ha`. Results therefore do not depend on how finely the resource is divided into units (`--area-ha` holds the area fixed while `--total-units` changes).

**Damage and cascades.** Each agent's direct damage is a curve of the depletion ratio (logistic, exponential or piecewise), amplified for consumers by a trophic factor of 1.6×, 2.6× and 4.1× at levels 1–3 (placeholder constants). Interaction edges then add cascade damage in a single pass: `effective = direct + (1 − direct) × pressure`, where `pressure` is the sum of `strength × source direct damage` over incoming edges. That is, the cascade acts only on the service still standing, so damage stays in [0, 1] without clamping. Incoming strengths are capped at 1.0 per agent (keystone boosts included). Validation rejects anything above the cap; it never rescales. Keystone agents whose health falls below their threshold double their outgoing strengths.

**Damage model.** By default (`"damage_model": "direct"`) the above is each agent's damage. A case can instead declare `"area_loss"` (Posidonia does, Step 8c.3). There, each unit lost takes its own services, so damage = `D + (1 − D) × degradation(D)`, and the curves, amplification and cascades describe the degradation of the resource that remains. Its curves must be flat at small losses: `threshold_logistic` is zero up to the safe threshold. Small losses are then priced linearly, which is a benefit transfer of the average per-hectare value, and the threshold behaviour is kept beyond them.

**Calibration regime.** Every ecosystem with edges must declare what its damage curves represent (`calibration_regime`): **A**, curves fitted to field data on total impact, in which case only keystone edges may be added; or **B**, curves that describe each agent's direct dependency only, with the edges adding the indirect part. All four cases are **B**: their curves are placeholders, so A cannot be claimed. Under B, the single-pass cascade is a structural lower bound for chains longer than one hop. The three terrestrial cases trigger a `CalibrationWarning`: health at the "safe" threshold is below 0.8, which says the placeholder curves put heavy damage inside the safe zone. Calibrating the curves fixes that warning; tuning parameters to silence it does not. Under `area_loss` the check looks at the health of the remaining resource, since health at a depletion t is at most 1 − t by construction. Posidonia's remaining meadow does not degrade before the threshold, so it does not warn.

**A static damage function, evaluated directly.** Everything per step — damage, cascade, keystone boosts, annual externality, health, resilience zone — is a function of the depletion ratio alone, so the engine evaluates it at the final depletion (and the step before, for the marginal cost) instead of looping over units; per-step data are computed only when asked for (`--steps-every`). The order and timing of actions do not matter: no hysteresis, no accumulated cascade. Time enters through discounting, the succession curve after restoration, and the substrate ceiling, whose erosion is integrated over the steps with the whole extraction spread over one year. This is decision D5, option B (`PROJECT_DEFINITION.md` §13). A path-dependent engine — a time axis with extraction schedules, substrate erosion over real time, keystone hysteresis, damage-dependent recovery — is a **committed milestone after v1.0** (option A, staged A1 → A2 → A3 in `version_specs/V09_SPEC.md`), behind an optional `dynamics` block in a schema-2 case file.

**Carbon** is valued only by `gaia/carbon.py`: no agent value and no pricing anchor contains carbon. The release of stored biomass and soil carbon is a one-off at year 0, unless the case or the user gives it a half-life. In that case it is released as a negative exponential, each year's tranche at that year's carbon price, discounted (Posidonia: 10 years by default; `--carbon-release-half-life`). `--carbon-release-fraction` sets the share of the soil stock released, a project input. The lost absorption is a yearly flow, discounted to a present value. Both are priced at the **social cost of carbon**: US EPA (2023), $190/t CO₂ for 2020 emissions (2020 USD, 2% near-term rate), converted at the ECB 2020 average rate to **€166.35/t**, growing at 1.3%/yr. The 2020 value is used as the year-0 price; EPA's path gives about $215 for 2026 emissions. `--carbon-price ets` switches to a labelled market/ETS view at €80/t, a private price that understates the damage.

**Discounting.** Flows are valued at the end of years 1..H with a Ramsey rate (2.3% in three cases; a declining 2.3% → 1.8% → 1.4% schedule over 200 years for Posidonia) and a scarcity uplift (a relative price change of ecosystem services). Validation rejects any configuration whose scarcity rate or carbon-price growth is not strictly below the discount rate, so present values converge. The forest case (and the default profile) keeps a 2% scarcity uplift, which is above the estimates of Drupp et al. (2024), 1.28%/yr for forests and 1.66%/yr in aggregate; it is flagged for recalibration. Because the horizon is a choice, every output also reports the PV at **50, 100 and 200 years** (horizon sensitivity).

**Substrate.** Extraction erodes the soil, or the matte for Posidonia, which lowers the carrying capacity. Substrate damage **reduces the restoration ceiling** (current / pristine capacity) and is counted once. Restoration can never recover more than the ceiling allows. The extraction PV already treats the service loss as permanent, so substrate adds nothing to it and is reported only as the "unrecoverable" share.

**Restoration from a starting state.** `run_restoration` starts from an extraction of `units_lost` units from the pristine resource (`--units-lost`; by default it restores what was cut) and retraces that extraction's damage path in reverse. Recovery functions are efficiencies in [0, 1], so recovered value never exceeds the damage reversed. The ceiling caps the recovered value, and the succession curve spreads it over time.

**Prevention versus destroy-then-restore.**
- `restoration_cost_ratio` = (foregone revenue + restoration cost) / foregone revenue = 1 + restoration cost per unit / unit value. It is a ratio of two input prices, with no ecology in it.
- `destroy_then_restore_penalty` is the PV cost to society of cutting k units and restoring them, compared with never cutting them: restoration cost + maturation gap (temporary) + substrate loss (permanent) + recovery shortfall (permanent, when replanting is partial) + carbon not recovered. It is reported in € PV and per € of foregone revenue.

**Uncertainty (`--uncertainty [N]`).** A seeded Monte Carlo over the case's own parameter ranges (`gaia/uncertainty.py`, any case file, extraction). A parameter is sampled from its documented `range` / `relative_range`, or from a range set by its confidence (high ±10%, medium ±25%, low ×/÷2, placeholder ×/÷3). The output gives P5/P50/P95 of the annual externality, its present value and the net social cost; a tornado ranking (each parameter at its own P5 and P95); and the normative choices as separate sensitivities (carbon price, discount rate, scarcity, horizon), which are not sampled. It replaced the former heuristic band `cost × (1 ± (1 − model confidence))` (finding S7). Model-wide constants are not varied.

**Benchmarks.** A case file may list published per-hectare values (`run.benchmarks`). An extraction report then shows where Gaia's per-hectare figures fall among them (`gaia/benchmarks.py`).

**Experimental: endogenous pricing (`--with-pricing`).** A Leontief–Hannon price system (v0.7) is **quarantined** and must not be used for estimates. Every output that uses it carries an EXPERIMENTAL banner, and the JSON has `"pricing": {"experimental": true, ...}`. Every price must be determined: each agent is anchored, or reachable from an anchored agent along the edges. Its price is then derived from upstream and labelled `(derived)`. Posidonia uses three sourced anchors; the other cases anchor every agent, with placeholder anchors where nothing is documented. Convergence is certified at each step. A step that cannot be certified stops the run with `PricingConvergenceError` instead of falling back to static values; in the shipped cases this happens at about 22–35% depletion. The formulation still counts upstream value once per dependent agent and prices the whole loss at the end-state scarcity price. Pricing applies to extraction only.

**Provenance.** Each case file records its parameters as `{value, unit, source, confidence, note}` objects, which become `gaia.provenance.Param`s. Confidence is `high`, `medium`, `low`, `placeholder`, or `user-supplied` for values given on the command line. The engines see only plain floats. Every result carries a `calibration` status that the text and JSON outputs print. The banner counts the recorded parameters at `placeholder` and `low` confidence; user-supplied values are counted separately and not assessed.

---

## Model structure

Gaia's model structure is **inspired by established ecological principles; its parameters are currently illustrative**. The principles it encodes, with what the implementation actually does:

- **Destruction is cheap, restoration is slow.** Recovery functions are efficiencies that never exceed the damage reversed, succession curves delay the recovered services, and substrate loss lowers the ceiling.
- **Trophic amplification.** Consumers lose more than producers for the same depletion. The amplification constants are placeholders.
- **Carrying-capacity thresholds.** Damage accelerates past a safe threshold (S-shaped curves). The curves are not fitted to data.
- **Interaction cascades.** Damage propagates along interaction edges in a single pass, acting on the service still standing. The engine evaluates a static function of depletion (see above): it does not simulate coevolution or accumulated cascades over time.

Six **shape properties** of every damage curve are checked on every run, for every agent, by `validate_ecosystem`: f(0) ≈ 0, f(1) ≈ 1, finite and in [0, 1], monotone, accelerating at the threshold, and convex just past it. They guarantee a well-formed curve. They are not an ecological validation: any curve of these families passes them.

---

## Installation and CLI

Python 3.9+, no runtime dependencies, no compiler needed.

```bash
pip install .            # or: pip install -e .
pip install pytest       # to run the tests
```

This installs the `gaia` command. `gaia run <case> [options]` runs a shipped case, `gaia run my_case.json [options]` a case file of your own (see *Writing your own case*); `python -m gaia run ...` is the same. The shipped cases are `forest`, `costa_brava` (alias `costa-brava`), `posidonia` and `amazon_forest` (aliases `amazon`, `amazon-forest`), stored as JSON in `gaia/cases/data/`. `gaia run <case> --help` lists every option with the case's defaults.

```bash
gaia run forest                                        # extraction, case defaults
gaia run forest --total-units 10000 --threshold 0.3 --units 5000 --unit-value 100
gaia run forest --total-units 10000 --units 5000 --area-ha 40
gaia run costa_brava --units 2500                      # at the 25% safe threshold
gaia run posidonia --units 50 --unit-value 2500 --uncertainty   # a 50 ha project, with Monte Carlo bounds
gaia run amazon --total-units 4000 --units 800         # a 10 ha patch at 400 trees/ha

gaia run forest --units 5000 --mode restore            # replant the 5,000 trees cut
gaia run forest --units 5000 --units-lost 8000 --mode restore --time-horizon 60
gaia run posidonia --units 2000 --mode restore --planting-cost 60000

gaia run forest --carbon-price ets                     # market/ETS carbon view
gaia run forest --format json --summary-only --output forest.json
gaia run amazon --format json --steps-every 1000       # every 1,000th step
gaia run costa_brava --units 600 --total-units 2000 --with-pricing   # EXPERIMENTAL
```

The 0.9 command lines — `gaia <case>` and `python -m gaia.cases.<case>`, with `--trees` / `--hectares` and the `--cut`, `--destroy`, `--tree-value`, `--revenue` aliases — still work for this release with a deprecation warning, and give the same output. They will be removed in 0.11.

| Option | Meaning |
|---|---|
| `--total-units N` | Size of the resource in units (trees; hectares for Posidonia) |
| `--units N` | Units to extract (extract mode) or to replant (restore mode) |
| `--threshold RATIO` | Safe extraction threshold, which also places the inflection of every damage curve (for Posidonia, where the remaining meadow starts to degrade) |
| `--unit-value EUROS` | One-off revenue per unit extracted |
| `--area-ha HA` | Area of the reference resource (default: units / the case's reference density). For Posidonia it is the reference resource itself, e.g. the meadow a project affects, and sets the number of hectares |
| `--resource-name NAME` | Name of the reference resource in the outputs |
| `--carbon-release-fraction F`, `--carbon-release-half-life YEARS` | Project inputs: share of the soil carbon released, and the half-life of its release (0: all at once) |
| `--matte-fate {exposed,excavated,buried}` | Posidonia: what the project does to the matte, a preset of the two inputs above (which still override it). **exposed** (default): the meadow dies but the matte stays uncovered and erodes, 0.63 released with a 10-year half-life. **excavated**: dug out or dredged, 0.96 released in the year of the works (IPCC 2013). **buried**: covered by fill and kept without oxygen, 0.125 (inferred, no source) |
| `--mode {extract,restore}` | Simulation mode |
| `--units-lost N` | [restore] Units missing at the start (default: `--units`) |
| `--planting-cost`, `--maintenance-cost`, `--maintenance-years` | [restore] Restoration costs per unit |
| `--time-horizon YEARS` | [restore] Length of the maturation timeline (0: none) |
| `--carbon-price {scc,ets}` | Social cost of carbon (default) or the market/ETS view |
| `--with-pricing` | EXPERIMENTAL endogenous pricing (extraction only) |
| `--format {text,json}`, `--output FILE` | Output format and destination |
| `--summary-only`, `--steps-every N` | JSON per-step data: none, or every Nth step. Above 10,000 steps the JSON is summary-only by default, with a warning |

JSON output is strict: a non-finite number is written as `null` with a sibling `<key>_null_reason`. Warnings, such as `CalibrationWarning`, print as one line on stderr. User-supplied values replace the case defaults and are listed as `user-supplied` in the calibration status, with the flag that set them.

### Python API

```python
from gaia.cases import load_case
from gaia.serialization import to_json

forest = load_case("forest")                 # or load_case("my_case.json")
result = forest.run_extraction(5_000, total_units=10_000, safe_threshold_ratio=0.3)

print(result.calibration.headline)                  # ILLUSTRATIVE: ...
print(f"Revenue:     €{result.revenue:,.0f} (one-off)")
print(f"Externality: €{result.annual_externality:,.0f}/yr")
print(f"PV:          €{result.pv_externality:,.0f} (PV)")
print(f"Net cost:    €{result.net_social_cost:,.0f} (PV − revenue)")
print(result.pv_externality_by_horizon)             # {50: ..., 100: ..., 200: ...}
print(forest.report(result))                        # the text report
json_text = to_json(result, include_steps=False)

# Restoration: 500 of 1,000 lost trees replanted, with the case's
# restoration costs, recovery and succession curves
restored = forest.run_restoration(500, units_lost=1_000, time_horizon_years=60,
                                  total_units=1_000)
print(f"Recovered: €{restored.annual_recovered_value:,.0f}/yr")
print(f"Net value: €{restored.net_restoration_pv:,.0f} (PV)")
print(f"Penalty:   €{restored.destroy_then_restore_penalty.total:,.0f} (PV)")

# The engine itself takes an Ecosystem
from gaia.simulation import run_extraction
ecosystem = forest.build_ecosystem(total_units=2_000, area_ha=10.0)
result = run_extraction(ecosystem, units_to_extract=500)
```

`gaia.ecosystem_io` reads and writes ecosystems: `ecosystem_from_dict` / `ecosystem_to_dict`, `load_ecosystem` / `save_ecosystem` (an ecosystem built in code can be saved as a file). `gaia.simulation.run_restoration` also accepts `starting_state=` (a `SimulationResult` of the same ecosystem), `succession_curve=` and `time_horizon_years=`. The 0.9 builders (`gaia.cases.forest.build_forest_ecosystem`, `run_forest`, ...) remain for this release as thin wrappers over the case files.

---

## The cases

| Case | Resource (default) | Agents / edges | Safe threshold | Unit value | Discount |
|---|---|---|---|---|---|
| `forest` — Oak Valley Forest, temperate | 10,000 trees on 40 ha | 4 / 2 | 30% | €100/tree | 2.3%, 2% scarcity, 100 yr |
| `costa_brava` — Holm Oak Forest, Mediterranean | 10,000 trees on 100 ha | 11 / 17 | 25% | €60/tree | 2.3%, 1.28% scarcity, 100 yr |
| `posidonia` — Posidonia oceanica, Catalan coast, marine | 4,582 ha (50 destroyed by default) | 10 / 15 | 20% | €2,500/ha | 2.3% → 1.4%, 1% scarcity, 200 yr |
| `amazon_forest` — Central Amazon old growth, tropical | 400,000 trees on 1,000 ha | 11 / 34 | 20% | €1.50/tree | 2.3%, 1.28% scarcity, 100 yr |

What the values rest on. The authoritative, per-parameter list is in each output's calibration status:

- **Forest and Costa Brava**: every agent shares a global biome mean from de Groot et al. (2012) and Costanza et al. (2014), minus climate regulation (carbon is valued separately). The figures are partly from memory and have no currency or price-year conversion: *low* confidence. The dependency weights split the biome value between agents. Both cases were once back-solved so that the externality crossed the revenue at a chosen depletion; that tuning is gone.
- **Posidonia** (the v1.0 case, Step 8):
  - **Euro values: a service ledger** (Step 8c.2). Each final service is counted once and owned by one agent, so every agent costs money without double counting. €819/ha/yr in total:
    - coastal protection, water purification, fisheries and bioindicator/knowledge (Campagne et al. 2015), with fisheries split between fish and invertebrates and the bioindicator use split with the epiphytes;
    - the meadow's diving amenity and coralligenous diving (Zunino et al. 2020; Rodrigues et al. 2016, Medes Islands);
    - the non-use values of megafauna and seabirds (Börger et al. 2014, a benefit transfer).

    Beach tourism and the meadow's own existence value are not valued, so the total is still a lower bound, ~11× below the Mediterranean seagrass meta-regression.
  - **Small losses are priced linearly** (damage model `area_loss`): below the 20% threshold each hectare costs its average value; past it the remaining meadow degrades. The reference resource is the regional stock unless the user enters the meadow a project affects (`--area-ha`).
  - **Carbon.** Burial from Balearic cores and the top-metre matte stock from Corsican cores, with a 25–100% loss on conversion released over time (half-life 10 yr). Both the fraction and the half-life are project inputs, most simply set with `--matte-fate`: the matte left **exposed** (the default: 0.63, half-life 10 yr), **excavated** (0.96, at once; IPCC 2013) or **buried** under fill (0.125, inferred). Carbon is as large as the services for the default project.
  - **Uncertainty.** Every parameter has a documented range or a flag; `--uncertainty` gives P5/P50/P95. Sources: `docs/POSIDONIA_LITERATURE_REVIEW.md`.
- **Amazon**: the agent value is the sum of the non-carbon anchors of its spec (`gaia/cases/definitions/AMAZON_FOREST.md`). Several of those anchors' sources are unverified. The 20% threshold is a basin-scale tipping point applied to a 1,000 ha patch, a known scale mismatch.
- **All cases**: placeholder damage curves (steepness 12; Posidonia's start at the threshold), placeholder edges (15 of them rescaled mechanically to the in-degree cap), placeholder substrate profiles and restoration costs.

---

## Writing your own case

A case is a JSON file (schema 1, stdlib `json`, no other dependency). This one is complete and runs with `gaia run valley.json`:

<!-- case-file-example -->
```json
{
  "gaia_schema": 1,
  "name": "Valley Watershed",
  "calibration_regime": "B",
  "resource": {
    "unit": "ha",
    "total_units": 500,
    "unit_value": {"value": 2000, "unit": "€/ha", "confidence": "placeholder",
                   "note": "One-off revenue per hectare cleared"},
    "safe_threshold_ratio": 0.15
  },
  "agent_defaults": {
    "annual_value_per_ha": {"value": 450, "unit": "€/ha/yr", "confidence": "medium",
                            "source": "Author et al. (2020), Table 3",
                            "note": "Site valuation, 2019 euros"},
    "damage": "logistic"
  },
  "damage_curves": {"logistic": {"type": "logistic", "steepness": 10}},
  "agents": [
    {"name": "Watershed", "description": "Freshwater supply", "dependency_weight": 0.6},
    {"name": "Fisheries", "description": "River fisheries", "dependency_weight": 0.4,
     "trophic_level": 2}
  ],
  "interactions": [
    {"source": "Watershed", "target": "Fisheries", "strength": 0.3, "type": "dependency",
     "description": "Flow loss reduces spawning habitat"}
  ],
  "run": {"units": 100}
}
```

- **Every number** is either bare or `{value, unit, source, confidence, note}`. The second form is recorded as the parameter's provenance and listed in every output; bare numbers are not, unless a `provenance_defaults` entry covers them (e.g. `"agent[*].dependency_weight": {"unit": "share", "confidence": "low", "source": "..."}`). A `medium` or `high` confidence needs a source.
- **The resource area**: `"unit": "ha"` makes each unit a hectare; otherwise give `area_ha` (a fixed area) or `units_per_ha` (a reference density, so the area follows `--total-units`). Agent values are €/ha/yr and are scaled by the area.
- **Curves**: `damage_curves` holds named curves shared by agents (`logistic` with `steepness`, `exponential` with `base`, `piecewise` with `pre_slope_ratio`); an agent can also give an inline curve. A curve without its own `threshold` uses the resource's safe threshold.
- **Optional blocks**: `carbon`, `resilience`, `substrate`, `discount` (or `{"profile": "central"}`), `restoration`, `recovery`, `succession`, the EXPERIMENTAL `pricing`, and `run` (default `--units`, notes). Without a `discount` block the default profile is used and flagged. The full key list is in the docstring of `gaia/ecosystem_io.py`, and the four files in `gaia/cases/data/` use every block.
- **Errors name the JSON path**, e.g. `$.agents[1].damage: unknown damage curve 'logistc' (defined: logistic)`. Unknown keys are rejected.
- Dependency weights must sum to 1.0. Each agent's incoming edge strengths must sum to at most 1.0, keystone boosts included.
- **Choose the calibration regime before writing damage curves.** Under A (curves fitted to field data on total impact), the data already embed indirect effects, so only keystone edges from keystone agents are allowed. Under B (direct dependency only), edges add the indirect part and the result is a lower bound for chains longer than one hop. Mixing the two double counts. See `PROJECT_DEFINITION.md`, "Critical Modelling Assumption".

An ecosystem built in Python (`gaia.models.Ecosystem` with `gaia.damage` curves) runs directly with `gaia.simulation.run_extraction`; `gaia.ecosystem_io.save_ecosystem(ecosystem, "valley.json")` writes it as a case file. To ship a case with Gaia, add its file to `gaia/cases/data/` and its name to `gaia.cases.CASE_NAMES`.

| Damage function | Shape | Use for |
|---|---|---|
| `logistic_damage(threshold, steepness)` | S-curve: slow, sharp knee, plateau | Carrying-capacity dynamics (the default) |
| `exponential_damage(threshold, base)` | Continuously accelerating | Self-reinforcing loss, e.g. fire feedback |
| `piecewise_damage(threshold, pre_slope_ratio)` | Two linear segments | A known threshold with an unknown curve shape |

---

## Project structure

```
Gaia/
├── gaia/
│   ├── __init__.py            # __version__ (single source)
│   ├── __main__.py            # python -m gaia → gaia.cli.main
│   ├── cli.py                 # gaia run, shared CLI options, output routing
│   ├── ecosystem_io.py        # the case file format: JSON schema 1, load / save, validation
│   ├── models.py              # Resource, Agent, Ecosystem, InteractionEdge, CalibrationRegime,
│   │                          #   results, DiscountConfig, profiles, pricing types
│   ├── provenance.py          # Param, Confidence, CalibrationStatus (parameter provenance)
│   ├── constants.py           # trophic / keystone constants and edge limits, each sourced or PLACEHOLDER
│   ├── damage.py              # damage curve factories and their six shape properties
│   ├── recovery.py            # recovery efficiency curves
│   ├── propagation.py         # trophic amplification and the single-pass cascade
│   ├── succession.py          # succession curves, maturation timeline and gap
│   ├── carbon.py              # carbon release and absorption at the social cost of carbon
│   ├── substrate.py           # soil / matte erosion, capacity, restoration ceiling
│   ├── resilience.py          # resilience zones (model confidence, irreversibility flag)
│   ├── uncertainty.py         # Monte Carlo, sensitivity ranking, normative scenarios (--uncertainty)
│   ├── benchmarks.py          # per-hectare comparison with published values (run.benchmarks)
│   ├── discount.py            # NPV, discount profiles, restoration NPV, destroy-then-restore penalty
│   ├── pricing.py             # EXPERIMENTAL endogenous pricing (quarantined)
│   ├── validation.py          # input validation, convergence and in-degree checks, shape properties
│   ├── simulation.py          # run_extraction / run_restoration (direct evaluation, lazy steps)
│   ├── report.py              # text reports (formatting only)
│   ├── serialization.py       # strict JSON output
│   └── cases/
│       ├── __init__.py        # load_case, the shipped case names
│       ├── data/              # forest.json, costa_brava.json, posidonia.json, amazon_forest.json
│       ├── forest.py, ...     # 0.9 compatibility wrappers (deprecated, removed in 0.11)
│       └── definitions/       # CASE_NOTES.md (derivations), AMAZON_FOREST.md (spec), AMAZON_LITERATURE_REVIEW.md
├── tests/                     # unit, case, golden, direct-evaluation, property, provenance and README tests
│   └── golden/                # snapshot of every case × mode (scripts/regen_golden.py)
├── scripts/
│   ├── regen_golden.py        # regenerate / --check the golden snapshots
│   ├── gen_readme_examples.py # regenerate / --check the README examples
│   └── profile_engine.py      # time the engine (docs/ENGINE_PROFILE.md)
├── version_specs/             # V01–V081 specs (historical; see the notes at their top); V09_SPEC.md (D5: option B now, A committed)
├── docs/                      # ENGINE_PROFILE.md (engine timings; the Cython decision D7, historical)
├── .github/workflows/ci.yml   # pytest on 3.9–3.12, golden, README, ruff, mypy
├── PROJECT_DEFINITION.md      # vision, foundations, roadmap
├── TOP_PRIORITIES_REPORT.md   # the 2026-10 audit and its fix plan
├── CHANGELOG.md
├── pyproject.toml             # packaging
└── LICENSE
```

---

## Tests

```bash
python -m pytest -q                         # whole suite
python scripts/regen_golden.py --check      # golden snapshots
python scripts/gen_readme_examples.py --check
ruff check gaia tests scripts && mypy
```

- **Golden snapshots**: every case × extraction / pricing / restoration scenario. A change to any output number fails until it is regenerated deliberately.
- **Direct evaluation**: the lazily evaluated steps equal, bit for bit, those of a sequential per-unit loop, on every field, for damage-curve kinds, keystones, cascades, substrates, pricing and restoration.
- **Properties**: scale invariance, restoration ≤ damage reversed, convergent NPVs, no hidden carbon, text report ⊆ JSON, strict JSON, pricing continuity or explicit failure.
- **Provenance**: every recorded value is the value the model uses, and every output carries the calibration status.
- **README**: the examples above match the code.

---

## Status

**v0.9.0: the 2026-10 audit fixes** (see `CHANGELOG.md` and `TOP_PRIORITIES_REPORT.md`).

What works: extraction and restoration for four cases with unit-consistent flows, present values and one-off amounts; €/ha/yr scaling; restoration from a real starting state; carbon at the social cost of carbon; substrate restoration ceilings; convergent discounting with horizon sensitivity; the destroy-then-restore penalty; strict JSON; parameter provenance and calibration status in every output; a direct-evaluation engine (no per-unit loop, no compiled extension); packaging and CI.

Experimental: endogenous pricing (`--with-pricing`), quarantined.

Unreleased (Step 7): cases are JSON files (`gaia run <case | file.json>`), with a documented, validated format.

Not done:
- Calibrated damage curves and edges: no case has them, Posidonia included.
- External expert review of the Posidonia methods note.
- A path-dependent engine: decided as a committed milestone after v1.0 (D5 option A, `version_specs/V09_SPEC.md`).

Unreleased (Step 8):
- The engine evaluates its static function directly; the Cython extension is gone (D5 option B, D7).
- The Posidonia v1.0 case: every parameter sourced or flagged, benchmarks, Monte Carlo bounds (`--uncertainty`), and a methods note ready for review.
- The first user and question, confirmed by the owner: a Catalan coastal authority or marine NGO reviewing the impact assessment of a port or marina expansion that destroys *N* ha of meadow (`PROJECT_DEFINITION.md`, v1.0).

---

## License

MIT, see `LICENSE`.
