# Gaia — State of the Project & Top Priorities

**Date:** 2026-10-11
**Scope:** Full audit of the repository at commit `703c0b0` plus uncommitted work (LICENSE, README license line, `AMAZON_LITERATURE_REVIEW.md`).
**Method:** Three independent audits (scientific/mathematical soundness, software engineering, documentation/roadmap), each running its own probe scripts against the code. The most important findings were then reproduced a second time independently. No repository files were modified during the audit.

> **Legend for findings**
> - ✅ **Verified twice**: reproduced independently, outside the audit that found it.
> - 🔬 **Audit-reproduced**: reproduced by the audit with a probe script and numbers, not re-checked a second time.
> - 📄 **By inspection**: found by reading the code or docs.

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Where the project stands](#2-where-the-project-stands)
3. [What is genuinely good](#3-what-is-genuinely-good)
4. [Critical findings: the model](#4-critical-findings-the-model)
5. [Significant findings: the model](#5-significant-findings-the-model)
6. [Engineering findings](#6-engineering-findings)
7. [Documentation & honesty of claims](#7-documentation--honesty-of-claims)
8. [Decisions you need to make first](#8-decisions-you-need-to-make-first)
9. [Next steps: detailed plan](#9-next-steps-detailed-plan)
10. [Suggested order & effort summary](#10-suggested-order--effort-summary)
11. [Appendix A: Version status table](#appendix-a-version-status-table)
12. [Appendix B: Full findings index](#appendix-b-full-findings-index)
13. [Appendix C: How to reproduce the key findings](#appendix-c-how-to-reproduce-the-key-findings)

---

## 1. Executive summary

Gaia is **well-built software sitting on economics that don't yet add up.**

The code is clean, dependency-free, well documented, and passes all 579 tests in about 22 seconds. The scientific framing in `PROJECT_DEFINITION.md` is thoughtful and unusually self-aware.

However, several core calculations are **wrong in ways that make the headline euro figures indefensible**. These are structural errors in the model's logic, not merely "parameters awaiting calibration":

- **Restoring 1 tree or 1,000 trees recovers exactly the same value** (€1,199,950). ✅
- **The same rate is treated as a one-off total in one module and as a yearly flow in another.** This makes the maturation gap and NPVs internally inconsistent, e.g. €1.2M recovered next to a €36.6M maturation gap. ✅
- **Results depend on the arbitrary size of the resource.** Cutting 50% of a forest costs €1,007,931 whether the forest has 100 trees or 100,000, while revenue scales. The core verdict (externality > revenue?) flips with the `--trees` argument. ✅
- **The Amazon carbon stock is 10× too low** because of a trees/ha mismatch. ✅
- **Carbon is counted two or three times** in several cases. 🔬
- **The v0.7 pricing engine** can report convergence on a system that diverges, and it jumps between incompatible scales. 🔬
- **The 579 tests do not catch any of this.** Several deliberate perturbations of headline constants pass the full suite. 🔬

There is also a process pattern. **Eight feature versions shipped in about 17 days (2026-02-27 → 2026-03-16)**, each adding a layer on top of placeholder parameters, while the two validation tracks defined in `PROJECT_DEFINITION.md` (scientific review, data calibration) have not started. The next roadmap item is a UI (v1.0), which would add a presentation layer on top of numbers that aren't right yet.

**Recommendation:** freeze new features. Spend the next iteration cycle making the existing outputs *correct* (model fixes) and *honest* (provenance and caveats in every output). Then redefine v1.0 as **"one credible, fully-sourced case reviewed by an external ecologist"** rather than a UI. The codebase is clean enough that this is realistic: the critical model fixes are an estimated 1–2 weeks of focused work.

---

## 2. Where the project stands

| Item | State |
|---|---|
| Last commit | `703c0b0` "Fix cython implementation", **2026-03-16** (~7 months idle) |
| Commits | 32 (2026-01-06 → 2026-03-16) |
| Library code | ~8,000 lines across 16 modules + 4 case files |
| Tests | 579 passing, ~22s with Cython (~50s without); 84% branch coverage |
| Dependencies | None at runtime (stdlib only); optional Cython extension |
| Latest version | v0.8.1 (I/O flexibility); v0.8 "Performance & Generalization" partly done (Cython loop exists) |
| Uncommitted | `LICENSE` (MIT, dated 2025, different e-mail from commits), README `License: TBD → MIT`, `gaia/cases/definitions/AMAZON_LITERATURE_REVIEW.md` |
| Where you left off | The Amazon literature review (2026-03-23). It is the first real parameter-by-parameter check against literature. **None of its four recommended corrections have been applied to the code.** |
| Next roadmap item | v1.0 — UI with isometric SVG visualizer ("very big effort") |

---

## 3. What is genuinely good

These are real strengths worth preserving through the refactor:

- **Code readability and discipline.** Typed dataclasses, consistent clamping, clear `ValueError` messages, frozen dataclasses for NPV results, no hidden magic.
- **Zero runtime dependencies.** Verified: no numpy/scipy imports anywhere in `gaia/`.
- **Correct mathematical building blocks.**
  - The damage function families (logistic, exponential, piecewise) are mathematically sound and well documented.
  - Gaussian elimination in `pricing.py` is correct.
  - Discount factors (Ramsey, declining schedule compounding) are correct.
  - Static extraction totals are monotonic, non-negative and continuous.
- **Cython/Python agreement on shipped cases.** On forest, Costa Brava, Amazon and a synthetic case, results are identical to ~1e-16. Posidonia and pricing correctly fall back to Python. 🔬
- **Optional features degrade cleanly.** An ecosystem without a given feature runs exactly as it did before that feature existed.
- **Scientific self-awareness.**
  - The note on single-pass propagation versus calibration regime (`PROJECT_DEFINITION.md` §"Critical Modelling Assumption", `propagation.py:73-95`) is excellent and rare.
  - The case files mark placeholders (40 `[PLACEHOLDER]` markers).
  - The Amazon literature review is candid about what is and isn't validated.
- **v0.8.1 I/O is fully implemented as specified.** Verified: `--units`, `--unit-value`, deprecation aliases, restoration-arg warnings, `--format json`, `--summary-only`, `--with-pricing`, `--output`.

---

## 4. Critical findings: the model

These make current monetary outputs wrong or indefensible. They are ordered by how much they contaminate other results.

### C1. Restoration value does not depend on how much you restore ✅

**Where:** `gaia/simulation.py:644`

```python
recovery_ratio: float = units_restored / units_to_restore
```

The recovery ratio is measured against the *restoration target*, not against the resource. The final step is therefore always `1.0`: full recovery of every agent's maximum value, and final ecosystem health is always 100%. The restoration run also has no concept of the *starting* state (how degraded the ecosystem was before restoring).

**Evidence** (forest, 1,000 trees, `--mode restore --time-horizon 60`):

| Units restored | Total recovered value | Maturation gap |
|---|---|---|
| 1 | €1,199,950 | €36,581,553 |
| 500 | €1,199,950 | €36,581,553 |
| 1,000 | €1,199,950 | €36,581,553 |

The ROI for restoring a single tree comes out as ~493,077×. Also, restoring 500 trees "recovers" €1.20M, while *cutting* those same 500 trees caused only €1.008M of damage. That violates the project's own Foundation #2 (entropy asymmetry: restoration recovers less, more slowly) and #11 (dual-lens symmetry).

**Impact:** Every restoration-mode number is wrong: recovered value, net restoration value, maturation gap, ROI, restoration NPV, carbon breakeven, and every "prevention advantage" variant.

### C2. One-off totals and yearly flows are mixed ✅

**Where:**
- `gaia/models.py:534` defines `monetary_rate` as *"Total monetary cost (€) at maximum damage"*, a **one-off total**.
- `gaia/discount.py:112` says *"We treat total_externality as the annual service value lost"*, a **yearly flow**.
- `gaia/succession.py:180-200` (`compute_maturation_gap`) treats `max_recovered_value` as *"maximum annual service value"* and sums it, undiscounted, over every year of the horizon.
- `gaia/simulation.py:767` passes `total_recovered` (computed from the one-off total) into that annual-flow function.

**Evidence:** The README's own headline example shows €1,199,950 "recovered value" alongside €36,581,553 "lost services during maturation". The gap is Σ over 60 years of (1.2M − 1.2M·s(y)) with an average gap fraction of 0.508, i.e. ~30.5 "years" of a number that was defined as a one-off total. In the same report, "NET RESTORATION VALUE = 1.2M − 75k" subtracts a one-off cost from that number as though it were a one-off value. **One of these two lines must be wrong; currently both are presented as true.**

**Cases disagree with each other too:**
- The Posidonia docstring says forest externalities are "one-time costs".
- Amazon and Costa Brava reason in €/ha/yr (yearly flows).
- Private revenue is always one-off, yet it is compared directly against externality totals that elsewhere are treated as yearly.

**Impact:** All NPVs, ROI, maturation gaps, prevention-advantage figures and "externality vs. revenue" comparisons.

### C3. NPV can diverge, so the arbitrary horizon decides the answer 🔬 (validation gap ✅)

**Where:** `gaia/discount.py:110-116` multiplies a yearly flow by a discount factor and a scarcity growth factor for every year of the horizon. `gaia/validation.py` (~line 513) only checks `scarcity_rate >= 0`. It **does not check that scarcity growth is below the discount rate.**

**Evidence:**
- Forest default: r ≈ 2.3%, scarcity 2% → net ~0.3%. NPV is €88.8M on €1.0M undiscounted ("Discount effect: 8706.3%").
- Under the built-in ENVIRONMENTAL profile (r 1.4% < scarcity 3%), the direct-loss multiple grows without bound:

| Horizon | Multiple of undiscounted loss |
|---|---|
| 50 yr | 75× |
| 100 yr | 240× |
| 200 yr | 1,388× |
| 500 yr | 158,994× |

- Amazon (r 2.3%, s 3%) and Posidonia (s 3%, 200-yr horizon) both sit in this divergent regime. Posidonia NPV is €4.98B on €5.75M.

**Impact:** NPV results are an artifact of the chosen horizon, not of the ecosystem.

### C4. Results depend on the arbitrary size of the resource ✅

**Where:** Agent `monetary_rate` values are fixed euro totals, unrelated to `total_units`. Revenue is `units × unit_value`.

**Evidence** (cut 50% of the forest):

| `--trees` | Revenue | Total externality | Externality per tree |
|---|---|---|---|
| 100 | €5,000 | €1,007,931 | €20,159 |
| 1,000 | €50,000 | €1,007,931 | €2,016 |
| 100,000 | €5,000,000 | €1,007,931 | €20 |

**Impact:** The main conclusion Gaia exists to produce (whether the externality is bigger than private profit) depends on a CLI argument that should be irrelevant to it.

### C5. Carbon is counted two or three times 🔬

**Where and how:**
- **Forest:** the "General Biosphere" agent is described as *"Carbon release, watershed degradation, climate impact"* (`forest.py:236-237`), contributing ~€416k at a 50% cut. The carbon module then adds carbon release (~€350k) and foregone absorption on top, in the report and the NPV.
- **Costa Brava ("Carbon & Climate" agent) and Posidonia ("Blue Carbon" agent):** the same overlap.
- **Amazon:**
  - The Canopy pricing anchor includes a "carbon stock" component of ~€5.08M/yr (stock ÷ 100, undiscounted). The NPV then capitalises it again: 8.4M × ~142.9 ≈ €1.2B.
  - That exceeds the value of the entire carbon stock (6.35 Mt × €80 ≈ €508M), and carbon release is then added a third time.
- **Substrate is double counted too:**
  - In `discount.py`, `pa_full` adds `npv_substrate` on top of a maturation gap that is already capped at `min(sfrac, substrate_ceiling)`.
  - The extraction NPV adds substrate loss on top of a direct loss that is already assumed permanent.

### C6. The Amazon carbon stock is 10× too low ✅

**Where:** `gaia/cases/amazon_forest.py:112-120`, and the spec `gaia/cases/definitions/AMAZON_FOREST.md:287`.

The per-tree carbon is derived assuming **400 trees/ha** (`173 MgC/ha × 3.67 / 400 = 1.587 tCO₂/tree`). But the case uses **400,000 trees over 10,000 ha = 40 trees/ha**, and its own docstring says so (`amazon_forest.py:258`: *"~40 trees/ha × 10,000 ha"*). The spec line says `initial_population=400_000  # ~400 trees/ha`, so the arithmetic slip is in the spec itself.

**Effect:**
- Modelled stock is ~634,800 tCO₂ instead of ~6.35 Mt (~63 instead of ~635 tCO₂/ha).
- Annual absorption and soil carbon are low by the same factor.

The literature review flags the density issue (`AMAZON_LITERATURE_REVIEW.md:58`) but calls it a "modelling abstraction". It is a real bug.

### C7. Soil erosion conversion is 10× too small ✅

**Where:** `gaia/substrate.py:31` (and duplicated in `simulation.py`).

```python
_T_HA_TO_MM_FACTOR: float = 10.0 / _BULK_DENSITY_KG_M3  # ≈ 0.00769 mm per t/ha
```

1 t/ha = 0.1 kg/m². At 1,300 kg/m³ that is 7.69e-5 m = **0.0769 mm**, not 0.00769 mm. Erosion depth and the resulting capacity loss are underestimated 10×. Recovery years happen to be unaffected because the same factor appears in both directions and cancels.

### C8. The v0.7 pricing engine is unsafe 🔬

**Where:** `gaia/pricing.py:376` (`compute_spectral_radius`) and `:485-670` (`solve_prices`). Wired in at `simulation.py:437` behind `--with-pricing`, which disables Cython.

1. **Wrong convergence check.** The spectral radius is estimated with 20 power iterations and a Rayleigh quotient, which can *underestimate* for non-symmetric matrices. For Posidonia at health 0.2 it estimates ρ = 0.714; the true value (numpy) is **1.099**. The solver reports `converged=True` and solves a system whose geometric series diverges. Negative prices are then silently clamped to 0.
2. **Scale-switching fallback.** When ρ ≥ 1, it falls back to static `monetary_rate`, which is on a different scale (one-off total) from the anchors (€/yr). This creates huge discontinuities:
   - **Amazon (4,000 trees):** €496.7M at 15.35% depletion, then **€1.75M one tree later**. That is a marginal cost of −€494.9M (ρ 0.9990 → 1.0002).
   - **Posidonia:** €6.37M at 30% depletion vs €5.51M at 40%. Cutting more costs less.
   - **Costa Brava:** a ~100× jump between 30% and 40%.
3. **Unanchored agents get a price of €0.** In the forest case, 3 of 4 agents have no anchor and are priced at zero. Cost at 30% depletion is €7.7k with pricing vs €324k static.
4. **Conceptual problems.**
   - `V = S·W·V + S·A` adds the value of what an agent depends on into that agent's own price; summing across agents then counts upstream value more than once.
   - Pricing the whole lost quantity at the *end-state* scarcity price (capped at 50×) overstates welfare loss. The textbook measure integrates the marginal price over the lost quantity.

### C9. "Prevention advantage" is just a ratio of inputs ✅

**Where:** `gaia/simulation.py:720`

```python
prevention_advantage = (foregone_revenue + total_cost) / foregone_revenue
# == 1 + restoration_cost_per_unit / unit_value
```

- Forest: 1 + 150/100 = **2.50**
- Costa Brava: 1 + 305/60 = **6.08**
- Posidonia: 1 + 200,000/2,500 = **81**

These are ratios of two hand-chosen input prices. They contain no ecology and no externality, and are always > 1 by construction. Yet the README presents them as findings "validated against ecological reality" and says "every euro saved … saves six".

---

## 5. Significant findings: the model

### S1. The "simulation" reduces to a formula 🔬

**Where:** `gaia/simulation.py:400-471`

`cumulative_cost` at each step depends only on the current depletion ratio, so the step loop is equivalent to evaluating a static function at each point (finite differences). There is no state that carries over between steps: no hysteresis, no accumulated cascade, no time. Substrate degradation assumes extraction happens in exactly one year.

`PROJECT_DEFINITION.md` §13 ("Simulation Over Calculation") argues that path dependence is the reason Gaia simulates. **The current engine does not deliver that.** This is a strategic question (§8, Decision D5), not necessarily a bug, but the claim and the code must agree.

### S2. Propagation contradicts its own calibration rule, and saturates 🔬

- Every agent's damage is a function of the *same* depletion ratio, and the interaction cascade adds on top. Per the project's own rule (`propagation.py:76-86`, PROJECT_DEFINITION "Option A/B"), that double counts unless damage curves are fitted to field data. They are identical placeholder logistics.
- **No case file documents its calibration regime (Option A or B),** although the README calls this "the most consequential modelling decision".
- **Amazon:** incoming edge strengths into Canopy total 1.40 (2.1 once keystones trigger), so damage caps at 1.0 everywhere:
  - Health is already 0.64 at the "safe" 20% threshold.
  - Health is 0.003 at 40% depletion.
  - Cutting from 50% to 100% has **zero marginal cost**.
- **Trophic amplification** `(1/0.15)^(0.25·L)` uses a constant the code itself labels `PLACEHOLDER`. It is also applied in restoration, so consumers recover 1.6–4.2× *faster* than producers, which is ecologically backwards.

### S3. Calibration is mostly reverse-engineered or invented 🔬📄

- **Forest:** rates were tuned so that externality < revenue at 30% and > revenue at 50% (`forest.py:30`). The headline conclusion is built into the inputs.
- **Posidonia:** agent impacts are labelled "User spec / Low" confidence.
- **Amazon:** all 11 agents share `monetary_rate = 8,400,000`, so the per-agent split is purely the dependency weights.
- **Amazon "validation" tests:** `test_amazon_externality_exceeds_revenue_at_all_levels` compares an €8.4M/yr flow with €1.50/tree one-off revenue. It passes by construction. The commit message itself says *"internal consistency rather than real-world prediction"*.
- **The "six scientific invariants"** (monotone, convex, f(0)=0, f(1)=1, …) are mathematical shape properties that hold by construction for the normalised curve families. They test the parameterisation, not ecology.

### S4. The Amazon code doesn't match its own literature review 📄

| Review says | Code says |
|---|---|
| Density bug (see C6) | Unchanged |
| Net sink 0.62 tC/ha/yr is a "historic peak"; use ~0.30–0.40 (Brienen 2015: ~0.24) | Still 0.62 (`amazon_forest.py:114`) |
| "20 yr to 80% biomass" should be ~70% | Comment still says 80% (`amazon_forest.py:98`) |
| `soil_carbon` naming is misleading | Unchanged |

Further issues with the Amazon work:
- The review's sources are of mixed quality: Wikipedia, worldrainforests.com, "ScienceDirect 2023" with no author, "Phil Trans R Soc B" with no author. Some citations look unverified and must be checked before they are relied on.
- "Validated (within range)" for €840/ha/yr against a $410–$5,264/ha/yr range is weak: a 13× range barely constrains anything.
- The Lovejoy–Nobre 20–25% tipping point is a **basin-scale** threshold being applied to a 100 km² patch, a scale mismatch.
- The test file's docstring promises targets (mycorrhizal/apex price ratio > 20:1, prevention advantage > 100×) that no test checks.

Values that **do** match literature: 173 MgC/ha biomass, 0.015 t/ha/yr intact-forest erosion, the Drupp et al. discount parameters.

### S5. Posidonia contradicts itself 🔬

The carbon profile absorbs 5.9 tCO₂/ha/yr, but the pricing anchor in the same file uses 1.7. Both values exist in the literature; the inconsistency is the problem. The overall ~€1,166/ha/yr falls within the literature range, but that range (Campagne 2015 ~€280–510/ha/yr up to Costanza's much higher figures) is too wide to constrain it.

### S6. The carbon price is a market price, not a social cost 📄

€80/t is roughly the EU ETS price. An *externality* tool should use the **social cost of carbon** (US EPA 2023 / Rennert et al. 2022: ~$185–190/tCO₂). The current choice probably understates carbon damages 2–3×. Separately, carbon price growth (3%) exceeds the discount rate (2.3%), which is the same divergence issue as C3.

### S7. Minor model issues 🔬📄

- The "Confidence band (51%)" is `cost × (1 ± (1 − conf))`, a heuristic presented as if it were a statistical interval.
- `compute_carbon_cost.total_cost` adds a stock (release) to a one-year flow (`carbon.py`, ~line 113).
- Off-by-one: the maturation timeline runs over years 1..H while the NPV loops over years 0..H−1.
- Stale comment "75% at year 0" (`discount.py:186`).
- For the same cut, the extraction and restoration reports give different substrate recovery times (2 vs 5 years).
- When `rate = impact / weight` (Posidonia), the dependency weight has no effect on cost.

---

## 6. Engineering findings

### E1. Tests don't protect the outputs 🔬

- **Mutation probe:** 8 headline constants were perturbed one at a time in a clean clone. **4 of 8 passed the entire suite:**
  - logistic inflection 0.15 → 0.20 (moves the Amazon externality ~4%)
  - trophic transfer efficiency 0.15 → 0.18
  - extraction erosion time doubled
  - restoration substrate degradation years 1 → 3

  Capping NPV years at 20 instead of 50 also went undetected. The perturbations that were caught were caught by only 1–2 unit tests each.
- **No golden/snapshot tests** of case outputs (total externality, NPV, final health, recovered value).
- **Case tests mostly restate configuration** ("has 11 agents", "mycorrhizal has the highest weight") or check loose inequalities.
- `test_no_interactions_identical_to_v02` never actually compares against v0.2 output.
- **No system-level property tests**, for example:
  - scale invariance
  - recovered ≤ lost
  - finite NPV
  - monotonic total cost under pricing
  - no double counting

  Each of these would have caught a critical finding above.
- **Coverage** (branch): 84% overall.

  | Module | Coverage |
  |---|---|
  | `validation.py` | 67% |
  | `substrate.py` | 75% |
  | `costa_brava.py`, `amazon_forest.py` | 41% (CLI never exercised) |
  | `pricing.py` | 82% |
  | `cli.py` | 84% |
  | `report.py`, `serialization.py` | 87% |

- **Which engine is tested depends on whether the `.so` is built.** With Cython present, parts of the pure-Python extraction loop never run (`simulation.py:412, 428-430`).

### E2. Two simulation engines, no test comparing them ✅ (divergences 🔬)

- **No test references Cython** (verified). The last two commits had to fix the `.pyx` by hand.
- **The engines choose substrate behaviour differently:**
  - Cython decides by the `substrate_type` *string* (`simulation.py:124`).
  - Python decides by *which profile fields are set* (`substrate.py:92-174`).
  - `substrate_type` is never validated (any string is accepted).
- **Reproduced divergences on non-shipped configs:**
  - Posidonia relabelled `substrate_type="terrestrial_soil"`: extraction NPV **€10.03bn (Cython) vs €5.17bn (Python)**; final `k_fraction` 0.0 vs 0.999.
  - Soil with `capacity_function="logistic"`: Cython `k_fraction` 0.0, Python 1.0. Python's `_capacity_logistic` silently returns 1.0 for soil (`substrate.py:147-174`).
- **Fragile dispatch.** Cython identifies damage functions by reading closure variable names (`simulation.py:64-98`). Renaming a local variable in `damage.py` silently drops back to Python.
- **Limited speedup.**
  - Measured gains: forest 2.2×, Costa Brava 3.0×, Amazon at 320k steps 6.8s → 2.5s.
  - The `.pyx` uses Python `list`s, not C arrays (its docstring claims otherwise).
  - The truly slow path is pricing: ~0.9 ms/step, so the default Amazon run with `--with-pricing` takes ~70s. That path *always* forces the Python loop.
- **No check for a stale `.so`.** Nothing detects a compiled extension that is out of date with the `.pyx`.

### E3. Calculations live in the report formatter 🔬

`gaia/report.py` recomputes domain values:
- trophic amplification with hard-coded constants (`report.py:141`; the same 0.15/0.25 also appears in `propagation.py:22` and the `.pyx`)
- carbon cost with a hard-coded `remaining_years=80` (`report.py:247-251`)
- substrate recovery, by back-calculating soil depth from `k_fraction` (`report.py:327-336`), which is wrong for threshold/logistic capacity

**Consequence:** the text report shows figures (e.g. carbon externality) that do not exist in `SimulationResult` or the JSON output. **Text and JSON disagree.**

### E4. Structure of `simulation.py` 📄

- `run_extraction` (~260 lines) and `run_restoration` (~300 lines) are long functions where each version (v0.3–v0.7) is an `if has_X:` phase.
- Restoration carries three different "prevention advantage" figures (simple, with substrate, v0.6).
- Result-building is duplicated between the Cython and Python paths (`simulation.py:260-298` vs `537-564`).
- `_T_HA_TO_MM_FACTOR` is copied from `substrate.py`.
- Restoration re-simulates substrate damage assuming one year of extraction (`simulation.py:738`), so an extraction run cannot be chained into a restoration run.
- Inconsistent design: damage functions live on `Agent`, but recovery functions are passed as a separate parallel list.

### E5. Dead fields from version layering 🔬

Defined but never set or never used:
- `SimulationStep.discount_factor_at_step`, `npv_externality`, `carbon_price_used` (`models.py:642-644`), though `serialization.py:136-140` checks for them
- `RestorationConfig` (`models.py:461`)
- `RestorationResult.substrate_recovery_cost`
- `Agent.succession_curve` (validated but never used)
- `water_availability_mm_yr`

### E6. Copy-paste across case files 📄

Each of the four case files carries ~180–220 lines of near-identical plumbing (`run_X`, `run_X_restoration`, `_parse_args`, `main`). The Costa Brava and Amazon `main()` functions differ by two identifiers. `cli.handle_deprecated_alias` is dead code: it is imported at `forest.py:45` but never called, and each case re-implements the alias handling inline.

### E7. No data-driven input 📄

Commit `4596e78` ("Refactor input to the program") added JSON *output* only. There is no `from_dict`/`load`, no schema and no ecosystem file format. Ecosystems are Python code with closures, so a non-programmer cannot define one. This is a stated v0.8 goal ("pluggable case template system").

### E8. Robustness ✅🔬

- **JSON can be invalid.** `serialization.py:439` calls `json.dumps(...)` without `allow_nan=False` ✅. With `formation_rate=0`, which validation accepts, the output contains `"substrate_recovery_years": Infinity`, which strict parsers reject.
- **The damage-function invariants never run at runtime.** `validate_damage_function` (`validation.py:162`) is only called from tests ✅. The README says the invariants are checked "on every run". Its docstring promises six checks but it implements four.
- **NaN and infinity are accepted.** They pass the `monetary_rate < 0` check (`validation.py:99`). An infinite rate yields an infinite cost; a NaN-returning damage function is accepted silently.
- **Damage factories don't validate their parameters:**
  - `exponential_damage(base=1)` and `logistic_damage(steepness=0)` raise `ZeroDivisionError`.
  - `exponential_damage(threshold=1.0)` raises `OverflowError`.

### E9. Packaging & hygiene ✅📄

- Only `setup.py`: no `pyproject.toml`, no requirements file, no CI, no lint/type-check config. Cython is not declared as a build dependency.
- No `console_scripts` entry point. `python -m gaia.cli --help` prints nothing; `python -m gaia` fails.
- **Version strings disagree:**

  | Location | Says |
  |---|---|
  | `gaia/__init__.py` comment | v0.5 |
  | `simulation.py` header | v0.7 |
  | `setup.py` | 0.8.0 |
  | `serialization.GAIA_VERSION`, CLI | 0.8.1 |

- `import gaia` exposes nothing: no `__all__`, no `__version__`.
- **mypy:** 32 errors in 9 files (mostly implicit `Optional`, a `result` variable reused for two types in each case `main()`, `pricing.py:339` reusing the name `row`).
- **pyflakes:** 69 issues (39 unused imports, 26 f-strings without placeholders, 4 unused variables, e.g. `forest.py:182`).
- **LICENSE** says 2025 (first commit 2026-01-06), with a different e-mail from the commits. `PROJECT_DEFINITION.md` still says "License: TBD".

### E10. CLI UX 🔬

- `warn_unused_restoration_args` substring-matches `sys.argv` (`cli.py:113-120`), so it misbehaves when `main(argv)` is called from code.
- Python warnings print the source line to end users.
- Only `ValueError` is caught. A bad `--output` path shows a raw traceback.
- **Amazon's default `--format json` writes ~169 MB to stdout** (per-step data for 80,000 steps).

---

## 7. Documentation & honesty of claims

### D1. README is stuck at v0.7 📄

- It says "Current Status (v0.7)", "510 tests" (actual 579), and "three ready-to-run cases" (four exist; Amazon is never mentioned).
- "What's coming (v0.8)" lists Cython, which already exists.
- The project tree omits `cli.py`, `serialization.py`, `cy/`, `cases/amazon_forest.py`, `cases/definitions/`, `setup.py` and several test files, and places the spec files at the repo root (they moved to `version_specs/`).
- CLI examples use the deprecated `--cut`/`--destroy`/`--tree-value` flags, which now print warnings.
- **Headline numbers for two cases are wrong when re-run:**

  | Case | README says | Code produces |
  |---|---|---|
  | Costa Brava | €1.98M, health 42.5% | €2.91M, health 14.4% |
  | Posidonia | €3.97M/yr, health 32%, "erased in 1.3 years" | €5.51M, health 4.6%, ~2 years |

- `PROJECT_DEFINITION.md` "Project Structure" describes a `gaia/core/`, `gaia/reports/` layout that never existed.
- There is no spec file for v0.2 and no spec for v0.8.

### D2. Caveats are buried; confidence is up front 📄

- The only explicit disclosure that parameters are illustrative/uncalibrated is the "Parameter Documentation Standard" section at **line 683 of 699**. It sits below "grounded in established science, not invented mechanics" and the €36.6M headline output.
- The commit framing "internal consistency rather than real-world prediction" appears nowhere in the README.
- **Outputs (text and JSON) never flag placeholder parameters.** That violates the project's own core principle: *"If a number cannot be justified, it must be explicitly marked as a placeholder and flagged in the output."*

### D3. Claims that go beyond "uncalibrated" 📄

- "Prevention advantage validated against ecological reality": it is an input-price ratio (C9).
- "Tested against six scientific invariants on every run": they are shape properties, and they run only in tests (S3, E8).
- `V07_RATIONALE.md`'s "no more manual monetary rate calibration": anchors, scarcity α, max multipliers and edge strengths are all hand-set.
- "Simulation over calculation" / coevolutionary cascades: the engine is path-independent (S1).

### D4. No definition of "done", no named user 📄

`PROJECT_DEFINITION.md` targets "decision-makers" without naming a concrete user (policymakers? courts? companies? NGOs? researchers?), and has no definition of a first useful release. The only milestone after v0.8 is a UI.

---

## 8. Decisions you need to make first

These are **your** calls. The fixes in §9 depend on them. Each has a recommendation.

### D1 — What does a monetary rate *mean*? (blocks C1–C5)

| Option | Meaning | Pros | Cons |
|---|---|---|---|
| **A. Yearly flow (recommended)** | `rate` = € per year of service lost at full damage | Matches how the ecosystem-services literature reports values (ESVD, TEEB, Costanza: €/ha/yr); Amazon & Costa Brava already reason this way; NPV becomes the natural way to get a one-off present value | Requires restating forest/Posidonia rates; the headline becomes "annual loss" + "present value" |
| B. One-off total | `rate` = total € at full damage | Closer to current forest wording | Has no natural link to the literature; NPV/maturation-gap logic must be rewritten to avoid treating it as a flow |

**Recommendation: A.** Then compare private revenue (one-off) against the *present value* of the externality stream, never against the annual flow.

### D2 — How are rates scaled? (blocks C4)

**Recommendation:** rates are **per hectare per year** (or per unit per year). Add `area_ha` to `Resource`; total agent value = rate × area. This makes the result invariant to how finely you discretise the resource (trees vs hectares), and lets literature values (€/ha/yr) plug in directly.

### D3 — Who owns carbon? (blocks C5)

**Recommendation:** `carbon.py` is the **single owner** of carbon value: physical tonnes × social cost of carbon. No agent and no pricing anchor may include carbon. Rename "General Biosphere" / "Carbon & Climate" / "Blue Carbon" agents to their non-carbon services (watershed, climate regulation other than CO₂, coastal protection, …), or remove them.

### D4 — What happens to v0.7 endogenous pricing? (blocks C8)

| Option | Effort | Notes |
|---|---|---|
| **Quarantine now, fix later (recommended)** | Small | Mark `--with-pricing` as experimental, hide from README headline, make it fail loudly instead of falling back |
| Fix properly now | Medium–large | Exact convergence check, no scale-switching fallback, all agents anchored, integrate marginal price, revisit `V = SWV + SA` double counting |
| Remove | Small | Loses a distinctive idea; can be restored from git |

### D5 — Should Gaia actually be path-dependent? (S1)

| Option | Notes |
|---|---|
| **Make it path-dependent (recommended long-term)** | Add state that carries over between steps: hysteresis after keystone collapse, substrate erosion that accumulates over real time (extraction rate in units/year), recovery that depends on prior damage. This is what justifies the step-by-step design. |
| Drop the claim | Keep the formula-like engine, rewrite §13 of PROJECT_DEFINITION and the README to say so honestly. Much simpler; the loop can then be replaced by direct evaluation. |

You don't need to resolve D5 before the critical fixes, but resolve it before redesigning the engine (Step 7).

> **Decided (owner, 2026-10-12): option B now, option A a firm commitment after v1.0**, staged A1 → A2 → A3 (`version_specs/V09_SPEC.md` §4). Implemented in Step 8a: `PROJECT_DEFINITION.md` §13 rewritten, direct evaluation with lazy per-step data, no number changed.

### D6 — Who is the first user, and what is v1.0?

**Recommendation:** pick one concrete user (e.g. *an NGO or journalist assessing a specific deforestation concession*, or *a researcher comparing restoration vs. protection*). Redefine **v1.0 = one credible case**: every parameter sourced, sensitivity analysis, external ecologist and environmental-economist review. Move the UI to v1.x.

### D7 — Keep Cython?

**Recommendation:** keep it, but only behind a parity test (Step 2). Re-evaluate after Step 7. If the engine is simplified (D5 option B) or the hot path becomes pricing, Cython may not be worth its maintenance cost.

> **Decided (owner, 2026-10-12): dropped**, following D5 option B (the per-unit loop it compiled is gone). Removed in Step 8a with its build configuration, CI matrix entries, parity tests and stale-build guard; `docs/ENGINE_PROFILE.md` keeps the measurements as a historical note.

---

## 9. Next steps: detailed plan

The plan is ordered so that every model fix lands on top of a safety net, which makes each numerical change **visible and intentional** rather than silent.

---

### Step 0 — Housekeeping (≈ ½ day)

**Goal:** a clean, committed baseline to iterate from.

**Tasks:**
1. Fix `LICENSE`: year (2026, or "2025–2026" if work predates the repo) and the intended e-mail. Commit with the README license line. Update the `License: TBD` line in `PROJECT_DEFINITION.md` to MIT.
2. Commit `AMAZON_LITERATURE_REVIEW.md`, adding a header note: *"Draft — citations not yet verified; see TOP_PRIORITIES_REPORT.md §S4."*
3. Commit this report.
4. Single source of truth for the version: add `__version__ = "0.8.1"` to `gaia/__init__.py`, and have `setup.py`, `serialization.GAIA_VERSION` and the CLI read it. Remove the stale "v0.5"/"v0.7" header comments.
5. Tag the current state (`git tag v0.8.1-pre-audit`) so that later comparisons of numbers have a fixed reference.

**Done when:** `git status` is clean and every version string agrees.

---

### Step 1 — Safety net: snapshot tests (≈ ½–1 day)

**Goal:** freeze *current* behaviour, so every later fix shows up as an explicit, reviewed change to expected numbers.

**Tasks:**
1. Create `tests/test_golden.py`. For each case (forest, costa_brava, posidonia, amazon_forest) × mode (extract, restore) × pricing (off, and on where applicable), record:
   - total externality, revenue, net social cost, final health, final zone
   - NPV components (direct, carbon release, carbon foregone, substrate, total)
   - recovered value, maturation gap, years to 50%/90%, prevention-advantage figures
   - per-agent costs
2. Store expected values in `tests/golden/*.json`, generated by a small script (`scripts/regen_golden.py`) that you run deliberately. Compare with `rel=1e-9`.
3. Use smaller resource sizes for Amazon in the snapshots (e.g. 4,000 trees) to keep the suite fast.
4. Add a `--summary-only` JSON snapshot test so the JSON schema is pinned too.

**Done when:** each of the 4 perturbations that previously passed the suite (logistic inflection, trophic efficiency, erosion time, substrate degradation years) now fails at least one golden test. Re-run the mutation probe to confirm.

**Workflow rule from here on:** any PR that changes golden values must say *why* in the commit message, e.g. "C1 fix: recovered value now scales with units restored; forest restore golden values updated."

---

### Step 2 — Safety net: engine parity & properties (≈ 1 day)

**Goal:** guarantee Cython and Python agree, and encode the scientific/economic properties the model *must* satisfy.

**Tasks:**
1. **Parity test** `tests/test_engine_parity.py`:
   - Parametrize over all 4 cases plus edge configs: every damage-function type, keystones on/off, each `substrate_type`, each `capacity_function` (including soil + logistic).
   - Run with the Cython path and with the Python path forced (add a `_force_python=True` hook or monkeypatch `_HAS_CYTHON`), and compare every step's outputs at `rel=1e-12`.
   - Skip cleanly when the `.so` isn't built.
2. **Fix the known divergences:**
   - Validate `substrate_type` against an `Enum`.
   - Make both engines dispatch on the same rule.
   - Make Python's `_capacity_logistic` handle soil, or reject the combination in validation.
3. **Stale-build guard:** embed a hash of the `.pyx` source in the compiled module, and fall back to Python (with a warning) if it doesn't match the current `.pyx`.
4. **Property tests** `tests/test_properties.py`. Write them now. **Mark the ones that currently fail as `xfail(strict=True, reason="C#")`** so they document the bugs and automatically flag when fixed:

| Property | Catches | Expected now |
|---|---|---|
| Scale invariance: same *fraction* cut on 2× resource (same area) → same per-ha externality | C4 | xfail |
| Restoring k units recovers ≤ the cost of cutting those k units | C1 | xfail |
| Recovered value is monotonic non-decreasing in units restored, and strictly less for fewer units | C1 | xfail |
| NPV is finite and bounded as horizon → ∞ for any valid config | C3 | xfail |
| Total cost is monotonic non-decreasing in depletion, **with pricing on** | C8 | xfail |
| Removing the carbon profile changes total by exactly the carbon line items (no hidden carbon) | C5 | xfail |
| Text report figures == JSON figures | E3 | xfail |
| JSON output parses with a strict parser (`allow_nan=False`) | E8 | xfail |

Optionally add `hypothesis` as a *test-only* dependency for random config generation. It doesn't affect the stdlib-only runtime promise.

**Done when:** parity tests pass, the 8 property tests exist, and the failing ones are `xfail(strict=True)`.

---

### Step 3 — Fix the model core (≈ 1–2 weeks) — *the most important step*

Do these in order: each later fix assumes the earlier ones. After each sub-step, the corresponding `xfail` should flip to pass and golden files are regenerated deliberately.

#### 3.1 Unit semantics: yearly flow (per decision D1)

1. In `models.py`, rename or clarify the field. For example, `annual_service_value` (€/yr at full damage), keeping `monetary_rate` as a deprecated alias for one release. Update its docstring.
2. Extraction outputs now produce, explicitly labelled:
   - `annual_externality` (€/yr lost at the end state)
   - `pv_externality` (present value of that stream, from `discount.py`)
   - `revenue` (one-off)
   - `net_social_cost = pv_externality − revenue` (both one-off amounts)
3. If no `DiscountConfig` is supplied, use a documented default (e.g. a Drupp et al. consensus schedule), or refuse to report a net social cost, rather than comparing a flow to a stock.
4. `succession.compute_maturation_gap`: discount each year's gap (it is currently undiscounted), and make it operate on an annual flow, which it already assumes.
5. `report.py` / `serialization.py`: every monetary field carries its unit in the label/key, e.g. `"€/yr"` vs `"€ (PV, 2026)"`.
6. Restate the forest and Posidonia rates as annual values. The Amazon and Costa Brava docs already argue in €/ha/yr.

**Acceptance:** no place in the code adds or compares a flow and a stock. A reviewer can tick each monetary field in the JSON schema as "flow" or "stock".

#### 3.2 Scale-normalised rates (per decision D2)

1. Add `area_ha: float` to `Resource` (required). Units per hectare is then derived (`total_units / area_ha`).
2. Agent value: `rate_per_ha_per_year × area_ha`.
3. Remove the "tuned so externality < revenue at 30%" calibration in `forest.py:30`. Rates must come from literature or be flagged as placeholders (Step 5), never be back-solved to produce an outcome.

**Acceptance:** the scale-invariance property passes. Changing `--trees` while keeping `area_ha` fixed changes the per-tree numbers but not the per-ha externality.

#### 3.3 Restoration from a real starting state (fixes C1)

1. `run_restoration` takes the *starting* state: either `initial_units_present` or, preferably, the `SimulationResult` of a prior extraction, enabling true **extraction → restoration chaining**. This also removes the "assume one year of extraction" hack at `simulation.py:738`.
2. Track the resource state: `depletion_before = 1 − present/total`; after restoring k units, `depletion_after = depletion_before − k/total`.
3. `recovered_value = cost(depletion_before) − cost(depletion_after)`, evaluated with **recovery functions that are bounded by the damage function** (Foundation #2: recovery ≤ damage reversal), then scaled by the succession curve over time.
4. Health after restoration is the damage-model health at `depletion_after`, not 100%.
5. Remove trophic amplification from the restoration path, or *invert* it so higher trophic levels recover slower. Amplifying recovery for consumers contradicts the trophic logic (S2).

**Acceptance:** "restoring k ≤ lost ≤ cutting k", monotonicity in k, and "restoring 1 tree ≠ restoring 1,000 trees" all pass. The README's 1.2M vs 36.6M inconsistency disappears.

#### 3.4 Single owner of carbon (fixes C5, per decision D3)

1. Remove carbon from agent descriptions, rates and pricing anchors (forest "General Biosphere", Costa Brava "Carbon & Climate", Posidonia "Blue Carbon", Amazon Canopy "carbon stock" anchor).
2. `carbon.py` computes release (one-off, stock) and foregone absorption (annual flow → PV). The NPV and reports use those values only.
3. Switch the default carbon price to a **social cost of carbon** (~$185–190/tCO₂, EPA 2023 / Rennert et al. 2022, converted to €). Keep the market price as an optional "private/ETS" view, clearly labelled.
4. Fix substrate double counting: in `pa_full`, and in the extraction NPV where substrate is added on top of an already-permanent direct loss. Substrate should *reduce the restoration ceiling*, or *add a separate permanent flow*, never both.

**Acceptance:** the "no hidden carbon" property passes. The Amazon capitalised carbon value can never exceed stock × SCC.

#### 3.5 The two 10× errors (fixes C6, C7)

1. `substrate.py:31`: `_T_HA_TO_MM_FACTOR = 100.0 / _BULK_DENSITY_KG_M3` (0.0769 mm per t/ha). Delete the duplicate in `simulation.py` and import the one in `substrate.py`. Add a unit test: 13 t/ha at 1,300 kg/m³ → 1.0 mm.
2. Amazon density: decide the real density. Literature for trees ≥10 cm DBH in Amazonian terra firme is commonly ~400–600 stems/ha.
   - Either use 4,000,000 trees on 10,000 ha (~400/ha),
   - or keep 400,000 trees and set `area_ha = 1,000`.
   - Fix `AMAZON_FOREST.md:287`.

   Add a test asserting `stored_carbon_per_tree × trees_per_ha ≈ 173 × 3.67 tCO₂/ha` (±10%).

#### 3.6 NPV hygiene (fixes C3)

1. In `validate_discount_config`: **reject** configs where scarcity growth ≥ the discount rate at any point on the schedule. Also reject `carbon_price_growth ≥ discount rate` unless an explicit terminal value is given.
2. Alternatively, apply the scarcity uplift only for a bounded period, or follow Drupp/Gollier-style relative-price formulations with a declining discount rate. Document the choice.
3. Fix the off-by-one (timeline years 1..H vs NPV 0..H−1): pick one convention and use it everywhere.
4. Report horizon sensitivity: NPV at H = 50/100/200 next to the headline, so readers can see whether the horizon is driving the result.

**Acceptance:** the "finite NPV" property passes. The ENVIRONMENTAL profile no longer diverges (fix the profile, or have validation reject it).

#### 3.7 Rename and rethink "prevention advantage" (fixes C9)

1. Rename the current figure to **`restoration_cost_ratio`** = (foregone revenue + restoration cost) / foregone revenue, and describe it honestly as an input-price ratio.
2. Define a meaningful **`destroy_then_restore_penalty`**: PV of (restoration cost + discounted maturation gap + PV of permanent substrate loss + carbon not recovered), relative to the PV of not cutting. This uses only quantities fixed in 3.1–3.5.
3. Remove the three parallel "prevention advantage" variants in `simulation.py` (simple, with substrate, v0.6) and replace them with these two clearly-defined metrics.

#### 3.8 Propagation sanity (S2)

1. Cap the sum of incoming edge strengths per agent (e.g. ≤ 1.0 in total), or normalise them. Add validation that warns when health at the safe threshold drops below a configurable level (e.g. < 0.8), because that signals over-strong edges.
2. **Document the calibration regime (Option A or B) in every case file header**, as PROJECT_DEFINITION requires. Under Option A (empirically calibrated), restrict interaction edges to keystone/regime-shift effects only.
3. Move trophic and keystone constants into one module (`gaia/constants.py`), each with a source or a `PLACEHOLDER` flag (Step 5).

---

### Step 4 — Quarantine endogenous pricing (≈ ½ day now; 3–5 days to fix properly later)

**Now (per decision D4):**
1. Mark `--with-pricing` as **experimental** in help text, README and every output that uses it (banner and JSON flag).
2. Replace power iteration with a **guaranteed bound**. `S·W` is non-negative, so the Collatz–Wielandt / Perron–Frobenius bounds apply:
   - ρ ≤ min(max row sum, max column sum).
   - If that upper bound is < 1, the Neumann series converges, guaranteed. Otherwise either refuse, or check convergence directly by iterating `V_{k+1} = S·W·V_k + S·A` and testing that the residual decreases.

   This stays stdlib-only.
3. **Remove the scale-switching fallback.** If the system doesn't converge, raise an error or mark the step as `pricing_failed`; never silently substitute static one-off rates.
4. Require every agent to be anchored when pricing is on, or raise a validation error.

**Later (proper fix):**
- Revisit `V = S·W·V + S·A`. Either price only *direct* service value per agent and use the network for scarcity propagation, or report only the system total, so upstream value isn't counted again per agent.
- Integrate the marginal scarcity price over the lost quantity (area under the inverse demand curve) instead of pricing everything at the end-state price.
- Add a continuity property test: cost(d + ε) − cost(d) ≥ 0 and bounded.

---

### Step 5 — Honest outputs: provenance & caveats (≈ 2–3 days)

**Goal:** implement the project's own rule: *every number traceable to a source, placeholders flagged in the output.*

**Tasks:**
1. **Parameter provenance object.** Introduce, for example:
   ```python
   @dataclass(frozen=True)
   class Param:
       value: float
       unit: str                 # "€/ha/yr", "tCO2/tree", ...
       source: str | None        # citation or None
       confidence: str           # "high" | "medium" | "low" | "placeholder"
       note: str = ""
   ```
   Use it in case definitions (it can be unwrapped to `float` before the hot loop, so there is no Cython impact).
2. **Calibration status in every output.**
   - Text report: a banner at the top, *"ILLUSTRATIVE — N of M parameters are placeholders; results are not real-world estimates"*, plus a "Parameter provenance" section listing the placeholders.
   - JSON: a top-level `calibration` block (`n_params`, `n_placeholder`, list of placeholders, calibration regime A/B).
3. **README rewrite of the framing.**
   - Move the "illustrative / uncalibrated" disclaimer to the top, right under the tagline.
   - Replace "grounded in established science, not invented mechanics" with something accurate, e.g. *"model structure inspired by established ecological principles; parameters are currently illustrative"*.
   - Remove "validated against ecological reality" and "tested against six invariants on every run" (or make the latter true by calling `validate_damage_function` inside `validate_ecosystem`).
4. **README refresh.** v0.8.1 status, the real test count (or no count, since it rots), the Amazon case, `--units`/`--unit-value` flags, re-run all example outputs (ideally generated by a script, so they can't drift again), correct project tree, Cython marked done.
5. Update `PROJECT_DEFINITION.md`: correct "Project Structure", mark the Cython part of v0.8 done, add the new v1.0 definition (Step 8).

**Done when:** a reader who sees *only* an output file (text or JSON) can tell which numbers are placeholders.

---

### Step 6 — Engineering cleanup (≈ 3–4 days, can be interleaved)

Ordered by value/effort:

1. **Packaging & CI (½ day).**
   - Add `pyproject.toml`: build-system with optional Cython, `console_scripts = gaia = gaia.cli:main`, ruff and mypy config.
   - Add a GitHub Actions matrix: Python 3.9–3.12 × {with Cython, without Cython}, running pytest + ruff + mypy.
   - Make `python -m gaia` work.
2. **Robustness (½ day).**
   - `json.dumps(..., allow_nan=False)`, serialising infinities as `null` plus a reason field.
   - `math.isfinite` checks in validation.
   - Parameter checks in damage factories (`base > 1`, `steepness > 0`, `threshold < 1`).
   - Call `validate_damage_function` from `validate_ecosystem` and implement all six promised checks.
3. **Move calculations out of `report.py` (1–2 days).** Everything the text report shows must come from `SimulationResult`/`RestorationResult`, so text and JSON can't disagree (flips the E3 property test). Put the trophic/keystone/capacity constants in `gaia/constants.py`.
4. **Delete dead fields and code (½ day).** The `SimulationStep` NPV fields, `RestorationConfig`, `substrate_recovery_cost`, `Agent.succession_curve` (or wire it in), `water_availability_mm_yr`, `cli.handle_deprecated_alias` (or use it everywhere).
5. **Lint & types (½ day).** Fix the 69 pyflakes and 32 mypy findings, then enforce both in CI.
6. **CLI UX (½ day).**
   - Parse warnings from the parsed `argparse` namespace instead of substring-matching `sys.argv`.
   - Catch `OSError` for `--output`.
   - Use clean warning formatting (no source lines).
   - Make JSON default to `--summary-only` when steps > 10,000 (or add `--steps-every N` downsampling).
7. **Split the god-functions.** Refactor `run_extraction`/`run_restoration` into explicit phases (`_compute_damage`, `_propagate`, `_substrate`, `_carbon`, `_npv`, `_build_result`) shared by both engines. This is easier *after* Step 3, since the restoration logic changes anyway.

---

### Step 7 — Data-driven ecosystems & engine decisions (≈ 1–2 weeks, after Steps 3–5)

1. **Ecosystem file format** (JSON first; YAML optional via a tiny parser or an optional dependency):
   ```yaml
   resource: {name: "Oak Valley", area_ha: 100, total_units: 40000, safe_threshold: 0.3}
   agents:
     - name: Watershed
       damage: {type: logistic, steepness: 10, inflection: 0.3}
       annual_service_value_per_ha: {value: 450, unit: "€/ha/yr", source: "...", confidence: low}
   interactions: [...]
   carbon: {...}
   discount: {profile: drupp_2018}
   calibration_regime: A
   ```
   Add `ecosystem_from_dict` / `ecosystem_to_dict` with round-trip tests.
2. **One generic CLI:** `gaia run case.json --mode restore --units 500 --format json`. The four case modules become four data files plus thin compatibility wrappers (keeping the deprecated entry points for one release).
3. **Decide D5 (path dependence).** If you choose a path-dependent engine, define the state variables and time semantics (extraction rate in units/year, hysteresis rules) in a `V09_SPEC.md` before coding.
4. **Decide D7 (Cython)** with profiling data from the new engine. If pricing becomes the hot path, optimise the solver (warm-start iteration, sparse edges) before investing more in the `.pyx`.

---

### Step 8 — Credibility milestone: the new v1.0 (≈ 3–6 weeks, mostly research)

**Goal:** one case that you could put in front of an ecologist and an environmental economist without embarrassment.

1. **Pick the case.** Amazon is the natural choice, since the literature review exists. It is also the hardest (scale issues, tipping points). Posidonia is a strong alternative: smaller scope, good Mediterranean literature (Campagne et al. 2015, Vassallo et al.), and closer to you if you're in Catalonia.
2. **Finish the literature review properly.**
   - Replace Wikipedia, worldrainforests.com and authorless citations with primary sources (DOI for every number).
   - Apply the four corrections.
   - Resolve the basin-vs-patch tipping-point scale problem: either model a basin-scale aggregate, or use patch-scale degradation thresholds from fragmentation literature (e.g. the BDFFP / Laurance et al. edge-effect studies).
3. **Cross-check against independent benchmarks.** Compare per-hectare values with the Ecosystem Services Valuation Database (ESVD) and TEEB for the same biome. Report where Gaia's output falls within those distributions.
4. **Uncertainty and sensitivity analysis** (this is the "Monte Carlo" item already in v0.8). Give each parameter a distribution (from its `Param.confidence`/range), run Monte Carlo, and report P5/P50/P95 instead of a single number. Add a tornado chart of the parameters that drive the result. This replaces the heuristic "confidence band" (S7).
5. **External review (Track 1 & Track 2 from PROJECT_DEFINITION).** Write a 4–6 page methods note (model structure, unit semantics, calibration regime, sources, limitations) and send it to at least one ecologist and one environmental economist. Track their comments as issues.
6. **Name the user and the question.** For example: *"For an NGO evaluating a proposed 8,000 ha clearing concession in Pará: what is the present value of the externality vs. the concession's revenue, with uncertainty bounds?"* Shape the output format around that question.

**Done when:**
- Every parameter of the chosen case has a DOI-backed source or is explicitly flagged.
- Results are reported with uncertainty bounds.
- At least one external expert has reviewed the methods note.
- All property tests pass with no `xfail`.

---

### Step 9 — Afterwards

- **UI** (old v1.0 → v1.x). When it comes, have it display the provenance and uncertainty bands from Step 5/8 prominently. A visual tool showing single precise euro numbers would undo the honesty work.
- **Generalisation** to other resource types (fisheries, water bodies, agricultural soil, air quality), only once one terrestrial case and the data format are stable.
- **Revisit endogenous pricing** with the proper fix (Step 4 "later").

---

## 10. Suggested order & effort summary

| # | Step | Effort | Fixes | Blocked by |
|---|---|---|---|---|
| 0 | Housekeeping | ½ day | LICENSE, versions, commit pending work | — |
| 1 | Snapshot tests | ½–1 day | E1 | 0 |
| 2 | Parity + property tests | 1 day | E2, documents C1/C3/C4/C5/C8/E3/E8 | 1 |
| — | **Decisions D1–D4** | 1 conversation | — | — |
| 3.1 | Unit semantics (flow) | 2–3 days | C2 | 2, D1 |
| 3.2 | Per-ha rates | 1 day | C4 | 3.1, D2 |
| 3.3 | Restoration from real state | 2–3 days | C1 | 3.1, 3.2 |
| 3.4 | Single carbon owner + SCC | 1–2 days | C5, S6 | 3.1, D3 |
| 3.5 | The two 10× errors | ½ day | C6, C7 | 2 (can be done early) |
| 3.6 | NPV hygiene | 1 day | C3 | 3.1 |
| 3.7 | Prevention-advantage rework | ½ day | C9 | 3.3, 3.6 |
| 3.8 | Propagation sanity | 1 day | S2 | 2 |
| 4 | Quarantine pricing | ½ day | C8 (containment) | 2, D4 |
| 5 | Honest outputs & docs | 2–3 days | D1–D3, S3 framing | 3 |
| 6 | Engineering cleanup | 3–4 days | E3–E10 | can interleave |
| 7 | Data-driven ecosystems, D5/D7 | 1–2 weeks | E6, E7, S1 | 3, 5 |
| 8 | Credible v1.0 case | 3–6 weeks | S3, S4, S5, D4 | 3, 5 |

**Fast wins you could do in the first session:** Step 0, Step 3.5 (two one-line bug fixes plus tests), JSON `allow_nan=False`, and the README disclaimer move. All are small, all are clearly correct, and none depend on the D1–D4 decisions.

---

## Appendix A: Version status table

| Version | Spec | Implemented | Tested | Notes |
|---|---|---|---|---|
| v0.1 Foundation | `V01_SPEC.md` | Yes | Yes | |
| v0.2 Restoration | **none** | Yes | Yes | C1 lives here |
| v0.3 Cascades | `V03_SPEC.md` | Yes (`propagation.py`) | Yes | Single-pass; saturation issue S2 |
| v0.4 Succession/carbon/resilience | `V04_SPEC.md` | Yes | Yes | Maturation gap C2 |
| v0.5 Substrate | `V05_SPEC.md` | Yes | Yes | 10× erosion bug C7; only spec with a "Known Limitations" section |
| v0.6 NPV/discounting | `V06_SPEC.md` | Yes | Yes | Divergence C3 |
| v0.7 Endogenous pricing | `V07_SPEC.md` + rationale | Opt-in, extraction only | Yes | C8; disables Cython; restoration ignores it |
| v0.8 Perf & generalisation | **none** | Partly (Cython loop) | **No parity test** | Generalisation, Monte Carlo, templates not started |
| v0.8.1 I/O | `V081_SPEC.md` | Yes (verified) | Yes (30 serialization + 21 CLI) | |
| v1.0 UI | One paragraph in roadmap | No | — | Recommend renaming to v1.x |

---

## Appendix B: Full findings index

| ID | Severity | Finding | Location | Status |
|---|---|---|---|---|
| C1 | Critical | Restoration value independent of units restored | `simulation.py:644` | ✅ |
| C2 | Critical | One-off totals and yearly flows mixed | `models.py:534`, `discount.py:112`, `succession.py:180-200`, `simulation.py:767` | ✅ |
| C3 | Critical | NPV diverges when scarcity ≥ discount rate; not validated | `discount.py:110-116`, `validation.py:~513` | 🔬 (validation gap ✅) |
| C4 | Critical | Results depend on resource size | agent `monetary_rate` design | ✅ |
| C5 | Critical | Carbon counted 2–3×; substrate double counted | case files, `discount.py` | 🔬 |
| C6 | Critical | Amazon carbon 10× low (40 vs 400 trees/ha) | `amazon_forest.py:112-120`, `AMAZON_FOREST.md:287` | ✅ |
| C7 | Critical | Erosion conversion 10× low | `substrate.py:31` | ✅ |
| C8 | Critical | Pricing: wrong convergence check, scale-switching fallback, €0 unanchored agents | `pricing.py:376, 485-670` | 🔬 |
| C9 | Critical (claims) | Prevention advantage is an input ratio | `simulation.py:720` | ✅ |
| S1 | Significant | Engine is path-independent ("simulation" = formula) | `simulation.py:400-471` | 🔬 |
| S2 | Significant | Propagation double counts and saturates; trophic amplification in restoration | `propagation.py`, Amazon case | 🔬 |
| S3 | Significant | Calibration reverse-engineered; invariants are shape-only | `forest.py:30`, tests | 🔬📄 |
| S4 | Significant | Amazon code ignores its literature review; weak sources; scale mismatch | `amazon_forest.py`, review | 📄 |
| S5 | Significant | Posidonia absorption 5.9 vs 1.7 tCO₂/ha/yr in same file | `posidonia.py` | 🔬 |
| S6 | Significant | Carbon priced at ETS (€80) not social cost (~$185–190) | case files | 📄 |
| S7 | Minor | Heuristic confidence band, carbon stock+flow sum, off-by-one, stale comments | various | 🔬📄 |
| E1 | Critical (eng.) | Tests miss 4/8 headline perturbations; no golden or property tests | `tests/` | 🔬 |
| E2 | Critical (eng.) | No Cython/Python parity test; divergences on substrate configs | `simulation.py:64-124`, `substrate.py:92-174` | ✅ / 🔬 |
| E3 | Significant | Domain logic in `report.py`; text ≠ JSON | `report.py:141, 247-251, 327-336` | 🔬 |
| E4 | Significant | Long functions, three PA variants, duplicated result builders | `simulation.py` | 📄 |
| E5 | Minor | Dead fields | `models.py:461, 642-644` | 🔬 |
| E6 | Significant | ~200 lines of plumbing duplicated × 4 | `gaia/cases/*.py` | 📄 |
| E7 | Significant | No data-driven ecosystem input | — | 📄 |
| E8 | Significant | JSON `Infinity`; NaN/inf pass validation; invariants not run at runtime | `serialization.py:439`, `validation.py:99,162` | ✅ / 🔬 |
| E9 | Minor | No pyproject/CI; version strings disagree; mypy 32, pyflakes 69 | repo root | ✅ / 🔬 |
| E10 | Minor | CLI argv matching, tracebacks, 169 MB JSON | `cli.py:113-120` | 🔬 |
| D1 | Significant | README frozen at v0.7; wrong Costa Brava & Posidonia numbers | `README.md` | 📄 |
| D2 | Significant | Uncalibrated disclaimer at line 683/699; outputs don't flag placeholders | `README.md`, `report.py` | 📄 |
| D3 | Significant | Over-claims ("validated", "every run", "no manual calibration") | README, `V07_RATIONALE.md` | 📄 |
| D4 | Significant | No named user or definition of done | `PROJECT_DEFINITION.md` | 📄 |

---

## Appendix C: How to reproduce the key findings

```bash
# Full suite (expects 579 passed)
python3 -m pytest -q

# C1 — restoration value identical for 1, 500, 1000 units
for u in 1 500 1000; do
  python3 -m gaia.cases.forest --trees 1000 --units $u --mode restore --time-horizon 60 \
    | grep -E "TOTAL RECOVERED|Lost services"
done

# C4 — same externality regardless of forest size (50% cut)
for t in 100 1000 100000; do
  python3 -m gaia.cases.forest --trees $t --units $((t/2)) | grep -E "Revenue|TOTAL EXTERNALITY"
done

# C6 — Amazon density mismatch
grep -n "400 trees/ha\|total_trees: int\|10,000 ha" gaia/cases/amazon_forest.py

# C7 — erosion factor (should be ~0.0769 mm per t/ha)
python3 -c "print(0.1/1300*1000, 'mm per t/ha (correct)'); import gaia.substrate as s; print(s._T_HA_TO_MM_FACTOR, '(code)')"

# E2 — no test exercises the Cython path explicitly
grep -rln -i "cython\|_HAS_CYTHON" tests/

# E8 — invariants never run outside tests; JSON allows NaN/Infinity
grep -rn "validate_damage_function" gaia/ | grep -v "def "
grep -n "json.dumps" gaia/serialization.py
```

The audits' probe scripts (parity, sweeps, mutation probe, pricing discontinuities) were written to the session scratchpad and are not part of the repo. They can be recreated from the descriptions above when implementing Steps 1–2.
