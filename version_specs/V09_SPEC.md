# V0.9 Spec — Path dependence (decision D5)

**Status: proposal — pending owner decision D5.** Nothing in this document is implemented. It sets out the two options of `TOP_PRIORITIES_REPORT.md` §8 D5 so the owner can choose, as Step 7.3 of that report asks. Decision D7 (keep Cython?) depends on the choice; its profiling data are in `docs/ENGINE_PROFILE.md` and summarised in §5.

---

## 1. Where the engine stands (finding S1)

`PROJECT_DEFINITION.md` §13 ("Simulation Over Calculation") argues that Gaia simulates because externalities are path-dependent. The engine does not deliver that:

| Quantity | What it depends on today |
|---|---|
| Direct damage of agent *i* at step *k* | `f_i(k / N)`, the current depletion only |
| Cascade damage | one pass over the edges from the current direct damage; no memory |
| Keystone boost | on while the keystone's current health is below its threshold, off as soon as it is above |
| Annual externality, health | functions of the current depletion only |
| Substrate | the only carried state: erosion is integrated over the steps, but the whole extraction is assumed to take one year (`years_per_step = 1 / units`), and erosion stops when it ends |
| Restoration | retraces the extraction's damage path in reverse (efficiency × damage reversed × substrate ceiling); no time passes between the cut and the replanting |
| Present values | the final annual loss treated as permanent from year 1, discounted |

So the per-unit loop evaluates a static function at successive points: the cost of the 3,001st tree is the same whatever happened before. Time enters only through discounting and the succession curve.

---

## 2. Option A — make Gaia path-dependent

Add state that carries over between time steps, so the order and timing of actions change the result. The report recommends this long-term.

### 2.1 Time semantics

- **The step is a year, not a unit.** A run is a *schedule* of actions over years, `t = 1..H`: extraction at a rate `r(t)` (units/year) and, optionally, restoration at `q(t)` (units/year) later on. The current "extract *n* units" becomes "extract *n* units in year 1"; "extract 8,000 ha over a 10-year concession" becomes `r(t) = 800` for `t = 1..10`.
- Flows are yearly (decision D1): the externality of year *t* is computed from that year's state, and the PV is `Σ_t flow(t) × discount_factor(t) × scarcity(t)` over the actual flow series, instead of "final annual loss × annuity".
- An optional sub-step (`time_step_years < 1`) is allowed for numerical accuracy; results must converge as it shrinks (a property test).

### 2.2 State variables

| Symbol | Meaning | Unit |
|---|---|---|
| `N(t)`, `D(t)` | standing units, depletion = (N₀ − N(t)) / N₀ | units, ratio |
| `D_max(t)` | the highest depletion reached so far | ratio |
| `d_i(t)` | effective damage of agent *i* (health `1 − d_i`): a state, no longer a function of `D` | ratio |
| `S(t)` | substrate: soil depth (cm) or matte stability (0–1), as today | cm or 0–1 |
| `K(t)` | capacity fraction from `S(t)` (existing capacity functions) | ratio |
| `collapsed_k(t)`, `t_k` | keystone latch and the year it closed | bool, year |
| `T_i(t)` | years agent *i* has spent beyond its collapse threshold (exposure) | years |

### 2.3 Dynamics, per year

1. **Equilibrium damage.** The existing curves become equilibrium responses: `d*_i(t) = amplify(f_i(D(t)))` plus the cascade computed from the *previous* year's damages `d(t−1)`, `d*_i = direct_i + (1 − direct_i) × pressure_i(d(t−1))`. A chain of *n* hops then propagates over *n* years instead of being cut at one hop (the S2 lower-bound caveat disappears over time). The in-degree cap still guarantees `d ∈ [0, 1]`.
2. **Relaxation with asymmetric speed.** `d_i(t) = d_i(t−1) + (d*_i − d_i(t−1)) × (1 − e^(−Δt/τ))` with `τ = τ_damage` when damage rises (fast, ~1 year: destruction is quick) and `τ = τ_recovery` when it falls (slow, from the succession curve; × `m_collapse` after a collapse). This replaces the separate succession pass: maturation becomes the recovery branch of the same state.
3. **Keystone hysteresis.** When a keystone's health falls below its threshold `θ_k`, the latch closes: its outgoing edges stay boosted until health rises above `θ_k + Δ_k`, a hysteresis band (a new parameter). This is the two-threshold (hysteresis) representation of alternative stable states in Scheffer, Carpenter, Foley, Folke & Walker (2001), "Catastrophic shifts in ecosystems", *Nature* 413(6856):591–596, doi:10.1038/35098000: when the response curve is folded, a system that collapsed at the bifurcation point F₂ does not switch back when conditions are restored to those before the collapse, but only beyond a second point F₁ (p. 591 and Fig. 2a; checked against the article). On the recovery branch the equilibrium curves are therefore shifted, `f_i^rec(D) = f_i(D + δ_k)`: recovery needs the resource restored below the depletion at which it collapsed. The paper is a review of the mechanism (lakes, coral reefs, oceans, forests, arid lands); it gives no values for `Δ_k` or `δ_k`, which stay placeholders. It also stresses that the degree of hysteresis varies strongly even within one kind of ecosystem, so a case may need `Δ_k = δ_k = 0`.
4. **Substrate over real time.** `S(t) = S(t−1) − E(cover(t)) × Δt + F × Δt`, with `cover(t) = N(t) / N₀`, `E` the existing erosion interpolation and `F` the profile's formation rate. Bare ground keeps eroding every year it stays bare, so restoring after 20 years recovers less than restoring after 2 (today both are identical). `K(t)` caps both `N(t)` regrowth and recovered health.
5. **Recovery that depends on prior damage.** The recovery efficiency of a restoration in year *t* is the current one × `K(t)` (substrate, item 4) × `(1 − λ × min(1, T_i / T_ref))` for agents that spent time collapsed (`λ`, `T_ref` new parameters), and `τ_recovery × m_collapse` after a keystone collapse (item 2).

**Nesting property.** With `τ_damage, τ_recovery → 0`, `Δ_k, δ_k, λ → 0`, one extraction year and no time between extraction and restoration, the dynamics reduce exactly to today's static engine. This is the bridge for the tests (§2.6): the static limit must reproduce the golden snapshots.

### 2.4 Data format

The schema-1 format (`gaia/ecosystem_io.py`) was designed so that dynamics can be added without breaking existing files:

- A new optional top-level block, read only by a reader of schema 2:

  ```json
  "dynamics": {
    "time_step_years": 1,
    "damage_response_years": {"value": 1, "unit": "years", "confidence": "placeholder"},
    "recovery_response": "succession",
    "keystone_hysteresis_band": {"value": 0.1, "unit": "health", "confidence": "placeholder"},
    "recovery_shift": 0.05,
    "collapse_recovery_multiplier": 2.0,
    "exposure_penalty": {"lambda": 0.3, "reference_years": 20}
  }
  ```

  and, in `run`, a schedule: `"schedule": [{"from_year": 1, "to_year": 10, "extract_per_year": 800}, {"from_year": 21, "to_year": 30, "restore_per_year": 400}]`.
- **Schema bump.** A document with `dynamics` is `"gaia_schema": 2`, because its results differ from what a schema-1 reader would compute; a schema-1 reader rejects it with a clear message (unknown key / unsupported version) instead of silently ignoring the block. A schema-2 reader accepts schema-1 documents unchanged: no `dynamics` block means the static engine, so every existing file keeps its results.
- Every new parameter takes the usual `{value, unit, source, confidence, note}` provenance and is listed in the calibration status. All of them start as placeholders.

### 2.5 Cython

The current `.pyx` is the per-unit extraction loop. A yearly loop has at most a few hundred iterations (`H ≤ 200`) of ~10 agents and ~35 edges, so it needs no compilation: the Amazon default run would go from 80,000 iterations to 100. Option A therefore makes the Cython extension unnecessary, and keeping it would mean porting new dynamics to a second engine for no speed gain. **With A, drop Cython** (and the parity test), keeping the static engine in Python for the static limit.

### 2.6 Golden and property tests

- The static engine stays as the no-`dynamics` path, so the 14 golden snapshots stay as they are.
- New golden scenarios for the dynamic engine (each case: a concession schedule, a clear-cut restored after 2 and after 20 years, a keystone collapse and recovery).
- New property tests: the static limit equals the static engine; results converge as `time_step_years` shrinks; slower restoration after a clear-cut never recovers more (substrate); the recovery path lies above the damage path after a keystone collapse (hysteresis); flows are yearly and the PV is the discounted sum of the actual flows.
- The text and JSON outputs gain a yearly time series; the D1 unit rules (flows vs one-off) carry over.

### 2.7 Effort and risks

| Part | Estimate |
|---|---|
| Final spec (equations, defaults, edge cases) | 2–3 days |
| Dynamic engine (state, relaxation, hysteresis, substrate in time, schedules) | 1.5–2 weeks |
| Outputs, JSON, report, schema 2, CLI `--schedule` | 3–5 days |
| Tests (static limit, properties, goldens) | 3–4 days |
| **Total** | **≈ 3–4 weeks**, plus calibration research for the new parameters (Step 8) |

Risks: at least six new parameters (τ's, Δ, δ, λ, T_ref, m), all placeholders until Step 8, which worsens the calibration counts every output reports; harder to explain and review; endogenous pricing (quarantined, D4) would stay static-only.

---

## 3. Option B — drop the claim

Keep the formula-like engine and say so.

- **Documentation**: rewrite `PROJECT_DEFINITION.md` §13 to state that Gaia evaluates a static damage function of depletion and that time enters through discounting, succession and the substrate ceiling. The README already describes the engine as path-independent.
- **Engine**: replace the per-unit loop by direct evaluation. The summary needs only the final state, the marginal cost at the last unit and the substrate state. Per-step data are evaluated on request at the points JSON asks for (`--steps-every`), and the golden `step_sums` by evaluating every point (the same arithmetic, so snapshots stay exact). The substrate's per-step Riemann sum, which today depends on the number of units because the extraction is spread over one year, would be kept as is for exactness (or replaced by a quadrature in a separate, documented golden change).
- **Cython**: the loop it compiles disappears; **drop Cython** (D7).
- **Data format**: no change.
- **Golden tests**: unchanged by construction; parity tests are deleted with the extension.

| Part | Estimate |
|---|---|
| §13 and README wording | ½ day |
| Direct evaluation, lazy per-step data | 1–2 days |
| Remove the extension, CI matrix, parity tests | ½ day |
| **Total** | **≈ 2–4 days** |

What it gives up: the timing of actions never matters (a 10-year concession costs the same as a one-year clear-cut with the same final depletion, apart from discounting the revenue), and restoration is never harder for having waited.

---

## 4. Recommendation

**Option B now, with Option A as a later milestone, staged.** Reasons:

1. Every parameter Option A adds starts as a placeholder, while the priority set by the report is credibility: one case with sourced parameters and uncertainty bounds (Step 8, decision D6). Dynamics on uncalibrated curves would add precision-looking behaviour without evidence.
2. B makes the claim and the code agree immediately, at low cost, and removes the second engine.
3. The format already leaves room for A (schema 2 with a `dynamics` block), so B closes no door.

If the first user's question (D6) is about timing — a concession phased over years, or the cost of delaying restoration — start Option A with its cheapest, best-grounded part: **A1**, the time axis and substrate erosion over real time (§2.1, §2.3 item 4; ≈ 1.5 weeks). Then **A2**, relaxation and keystone hysteresis (items 1–3), and **A3**, recovery that depends on prior damage (item 5), only once the curves are calibrated.

**Owner decision needed:** A, B, or B-then-A1. Until then the engine stays as it is, and `PROJECT_DEFINITION.md` §13 keeps its "describes an aim, not the implementation" note.

---

## 5. Decision D7 (Cython) — summary of the profile

From `docs/ENGINE_PROFILE.md` (`scripts/profile_engine.py`; Python 3.10, arm64 macOS):

- The compiled loop speeds up a whole run by **1.2–3.3×**, never more: the per-unit Python loop costs only ~20 µs per unit for the largest case, and result building, NPVs and restoration (all Python) take the rest. The largest default run (Amazon extraction, 80,000 units) takes 1.5 s in Python and 0.6 s with Cython; the other cases take at most 0.12 s in Python.
- **Pricing never uses Cython** (the loop has no price solver) and was the slowest path: 0.07–0.75 ms per unit, three quarters of it in n + 1 dense linear solves per step (12 for 11 agents), each repeating the same elimination. A follow-up does that elimination once for all right-hand sides, with bit-identical results: 0.05–0.24 ms per unit, 1.4–3.3× faster.
- **Recommendation: keep Cython for now** (it is parity-tested and costs little while the engine is unchanged), **do not extend it**, and **drop it with either D5 option** (both remove the per-unit loop it compiles). If pricing is ever un-quarantined, keep optimising its solver (warm start, sparse edges, at the cost of re-checking the golden pricing snapshots), not the `.pyx`.
