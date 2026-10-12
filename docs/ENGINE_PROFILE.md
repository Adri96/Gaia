# Engine profile (decision D7, historical)

**Status: historical note.** Decision D7 (keep the optional Cython extraction loop?) was settled on 2026-10-12: **dropped**, following decision D5 option B (`version_specs/V09_SPEC.md` §4). This page keeps what the decision was based on and what replaced the loop. To time the current engine: `python3 scripts/profile_engine.py [--quick] [--hotspots]`.

## What was measured before the decision (Step 7.4)

On the Step 7 code (Python 3.10.4, arm64 macOS, best of 3, whole in-process runs without output formatting), the compiled loop made a whole run **1.2–3.3× faster, never more**: the Python per-unit loop cost only ~20 µs per unit for the largest case, and the rest of a run (building each `SimulationStep`, replaying the substrate, the NPVs, restoration) was Python either way. The largest default run, the Amazon extraction (80,000 units), took 1.5 s with the Python loop and 0.6 s with Cython; the other cases at most 0.12 s. Pricing (EXPERIMENTAL) never used the extension, and its solver was optimised instead (one Gaussian elimination for the n + 1 right-hand sides, 1.4–3.3× faster, bit-identical results). The extension doubled the engine (the `.pyx` mirrored the Python phases) and needed a parity test, a stale-build guard and a CI matrix twice as large.

The recommendation then was to keep it for the moment, not extend it, and drop it with either D5 option, since both remove the per-unit loop it compiled.

## What replaced it (Step 8a)

Option B evaluates the static damage function directly: a run computes its final state (and the step before, for the marginal cost), and per-step data are computed only when they are asked for (`ExtractionSteps`, `RestorationSteps` in `gaia/simulation.py`). The substrate's per-step Riemann sum is still integrated once per run, so its numbers do not change. The new engine is bit-for-bit the old Python loop on every step and field (`tests/test_direct_evaluation.py`; the golden files are unchanged).

Measured on 2026-10-12 on the same machine, old engine (the `main` branch, pure-Python loop) and new engine run alternately in fresh processes, best of 9 (3 × 3) each, so machine load affects both alike:

| Run | Units (of total) | Old Python loop (s) | Direct evaluation (s) | Speed-up |
|---|---|---|---|---|
| amazon_forest extract (default) | 80,000 of 400,000 | 1.520 | 0.205 | 7.4× |
| amazon_forest restore (default) | 80,000 of 400,000 | 2.319 | 0.505 | 4.6× |
| posidonia extract (default) | 2,000 of 5,000 | 0.056 | 0.032 | 1.8× |
| posidonia restore (default) | 2,000 of 5,000 | 0.110 | 0.079 | 1.4× |
| forest extract (default) | 5,000 of 10,000 | 0.043 | 0.012 | 3.6× |
| costa_brava extract (default) | 4,000 of 10,000 | 0.061 | 0.012 | 5.2× |
| amazon_forest full-depletion sweep | 100,000 of 100,000 | 2.034 | 0.254 | 8.0× |

Every default run is now faster than the Cython loop was (Amazon extraction 0.2 s against 0.6 s). What remains is per-unit work that is not the damage function: the substrate trajectory (one scalar update per unit), restoration's check of every recovery ratio against [0, 1], and the present values (a loop over the horizon, 200 years for Posidonia). Evaluating every step — what the golden snapshots, `--steps-every 1` and the text report's former scans did — costs about what the old loop cost (1.3–1.8 s for a 100,000-unit sweep); the text report now scans only the quantities it needs (keystone damage, the resilience zone).

## If speed matters again

- **Option A (path dependence, committed after v1.0)** steps by year, not by unit: at most a few hundred iterations of ~10 agents and ~35 edges, so no compilation is needed there either (`version_specs/V09_SPEC.md` §2.5).
- **Pricing** (quarantined) still solves a linear system per step to certify convergence; if it is ever un-quarantined, optimise its solver (warm start, sparse edges), at the cost of re-checking the golden pricing snapshots.
- **Monte Carlo** (Step 8.4) re-runs the summary, not the steps, so its cost per draw is the "summary" time above.
