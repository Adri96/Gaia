# Engine profile: pure Python vs Cython (decision D7)

Step 7.4 of `TOP_PRIORITIES_REPORT.md`: should Gaia keep its optional Cython extraction loop? Measured on 2026-10-12 at the Step 7 code (no model change since 0.9.0), with `scripts/profile_engine.py` (rerun it to reproduce: `python3 setup.py build_ext --inplace && python3 scripts/profile_engine.py --hotspots`).

Machine: Python 3.10.4, arm64 macOS (Apple silicon), Cython 3 extension built in place. Times are wall-clock seconds for a whole in-process run (building the ecosystem, the step loop, result building, NPVs; no output formatting), best of 3. Restoration runs include the extraction they start from (`--units-lost` = `--units`). Pricing (EXPERIMENTAL) runs stay below each case's convergence limit. The sweep extracts every unit of a 100,000-unit resource (steps of 0.001%).

## Results

| Run | Case | Mode | Units (of total) | Python (s) | Cython (s) | Python / Cython |
|---|---|---|---|---|---|---|
| default | forest | extract | 5,000 of 10,000 | 0.044 | 0.018 | 2.5× |
| default | forest | restore | 5,000 of 10,000 | 0.066 | 0.038 | 1.7× |
| default | costa_brava | extract | 4,000 of 10,000 | 0.063 | 0.019 | 3.3× |
| default | costa_brava | restore | 4,000 of 10,000 | 0.098 | 0.052 | 1.9× |
| default | posidonia | extract | 2,000 of 5,000 | 0.060 | 0.035 | 1.7× |
| default | posidonia | restore | 2,000 of 5,000 | 0.116 | 0.097 | 1.2× |
| default | amazon_forest | extract | 80,000 of 400,000 | 1.534 | 0.609 | 2.5× |
| default | amazon_forest | restore | 80,000 of 400,000 | 2.357 | 1.436 | 1.6× |
| pricing | forest | extract | 5,000 of 10,000 | 0.342 | 0.341 | 1.0× |
| pricing | costa_brava | extract | 3,000 of 10,000 | 2.209 | 2.226 | 1.0× |
| pricing | posidonia | extract | 1,500 of 5,000 | 0.904 | 0.896 | 1.0× |
| pricing | amazon_forest | extract | 8,000 of 40,000 | 6.041 | 6.036 | 1.0× |
| sweep | forest | extract | 100,000 of 100,000 | 0.978 | 0.531 | 1.8× |
| sweep | costa_brava | extract | 100,000 of 100,000 | 1.764 | 0.766 | 2.3× |
| sweep | posidonia | extract | 100,000 of 100,000 | 1.873 | 0.818 | 2.3× |
| sweep | amazon_forest | extract | 100,000 of 100,000 | 2.027 | 0.813 | 2.5× |

## Hotspots

### cProfile: sweep amazon_forest, Python loop

```text
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
   100001    1.160    0.000    1.195    0.000 gaia/propagation.py:93(propagate_interactions)
   100000    0.315    0.000    0.743    0.000 gaia/simulation.py:327(_compute_damage)
   100000    0.202    0.000    0.233    0.000 gaia/simulation.py:404(_annual_costs)
  1101716    0.193    0.000    0.230    0.000 gaia/damage.py:133(_logistic)
   300000    0.114    0.000    0.146    0.000 gaia/substrate.py:138(_capacity_threshold)
  1100011    0.110    0.000    0.165    0.000 gaia/propagation.py:51(compute_trophic_amplification)
        1    0.105    0.105    2.857    2.857 gaia/simulation.py:447(_python_steps)
   100000    0.095    0.000    0.157    0.000 gaia/simulation.py:187(_make_step)
```

### cProfile: sweep amazon_forest, Cython loop

```text
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.437    0.437    0.725    0.725 gaia/simulation.py:292(_cython_steps)
   100000    0.076    0.000    0.279    0.000 gaia/simulation.py:187(_make_step)
   100000    0.035    0.000    0.045    0.000 gaia/substrate.py:138(_capacity_threshold)
   100000    0.028    0.000    0.103    0.000 gaia/substrate.py:259(apply_erosion)
   100000    0.021    0.000    0.066    0.000 gaia/substrate.py:94(compute_capacity_fraction)
   200001    0.019    0.000    0.019    0.000 gaia/substrate.py:34(is_terrestrial)
        1    0.015    0.015    0.118    0.118 gaia/simulation.py:768(_replay_substrate)
        1    0.012    0.012    0.857    0.857 gaia/simulation.py:655(run_extraction)
```

### cProfile: pricing amazon_forest

```text
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    96000    5.989    0.000    6.406    0.000 gaia/pricing.py:367(solve_linear_system)
     8000    0.727    0.000    0.733    0.000 gaia/pricing.py:306(matrix_multiply)
 13912015    0.296    0.000    0.296    0.000 {method 'append' of 'list' objects}
    31667    0.235    0.000    0.236    0.000 gaia/pricing.py:344(matrix_vector_multiply)
     8000    0.235    0.000    8.149    0.001 gaia/pricing.py:661(solve_prices)
  7480034    0.144    0.000    0.144    0.000 {built-in method builtins.abs}
     8000    0.109    0.000    0.132    0.000 gaia/pricing.py:479(spectral_radius_bound)
     8000    0.072    0.000    0.077    0.000 gaia/pricing.py:645(_matrix_subtract)
```

## Follow-up: the pricing solver (same numbers, fewer solves)

Done after the measurements above, on the same machine (Python loop; Cython never runs pricing):

- **One elimination for n + 1 right-hand sides.** `solve_prices` solved `(I − S·W) x = b` once for the prices and once per column of the inverse (for the demand multipliers), repeating the same Gaussian elimination n + 1 times. `gaia.pricing.solve_linear_systems` eliminates once with every right-hand side appended to the augmented matrix: the pivots depend on the matrix only and each column goes through exactly the operations a separate solve applies, so the results are **bit-for-bit identical** (checked against the previous code on 6,000 random health states of the four cases — prices, multipliers, certificates and error messages — and 2,000 random systems; the golden pricing snapshots pass unchanged on both engines).
  The inverse's columns are still computed: its row sums could come from a single solve against a vector of ones, but in floating point that is not the same number as summing the columns, so it would change the reported demand multipliers.
- **S·W by row scaling.** S is diagonal, so `S·W` is row *i* of W times `S[i][i]`: the same numbers as the dense O(n³) product, whose other terms are `0.0 × w`.
- **Not done**, because they would change reported numbers: a warm start of the convergence certificate (it would change `iterations` and `spectral_radius_bound`), and skipping zero entries during elimination (it can flip the sign of exact zeros, so bit-identity is not guaranteed).

| Case | Units (of total) | Before (s) | After (s) | Speed-up | After, ms per unit |
|---|---|---|---|---|---|
| forest | 5,000 of 10,000 | 0.342 | 0.239 | 1.4× | 0.05 |
| costa_brava | 3,000 of 10,000 | 2.209 | 0.662 | 3.3× | 0.22 |
| posidonia | 1,500 of 5,000 | 0.904 | 0.335 | 2.7× | 0.22 |
| amazon_forest | 8,000 of 40,000 | 6.041 | 1.881 | 3.2× | 0.24 |

### cProfile: pricing amazon_forest, after the follow-up

```text
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     8000    1.212    0.000    1.273    0.000 gaia/pricing.py:393(solve_linear_systems)
    31667    0.235    0.000    0.235    0.000 gaia/pricing.py:344(matrix_vector_multiply)
     8000    0.198    0.000    2.371    0.000 gaia/pricing.py:701(solve_prices)
     8000    0.109    0.000    0.131    0.000 gaia/pricing.py:519(spectral_radius_bound)
     8000    0.072    0.000    0.077    0.000 gaia/pricing.py:685(_matrix_subtract)
     8001    0.065    0.000    0.065    0.000 gaia/propagation.py:93(propagate_interactions)
     8000    0.060    0.000    0.083    0.000 gaia/pricing.py:222(build_value_matrix)
    88000    0.060    0.000    0.060    0.000 gaia/pricing.py:782(<listcomp>)
```

The solve now takes about half of a pricing run, against four fifths before.

## Reading

1. **The compiled loop buys 1.2–3.3× on a whole run, never more.** The Python loop already costs only ~20 µs per unit for the largest case (Amazon: 11 agents, 34 edges), about 40% of it in `propagate_interactions`. With Cython the loop itself is cheap, and the rest of the run — turning each step into a `SimulationStep`, replaying the substrate, the NPVs, and for restoration the restoration steps and maturation timeline, all Python — dominates: Cython makes extraction 1.7–3.3× faster, restoration only 1.2–1.9×.
2. **Absolute times are small.** Every default run takes at most 2.4 s in pure Python (Amazon restoration, 80,000 units) and at most 0.12 s for the three other cases; a full-depletion sweep of 100,000 units takes ~2 s. Nothing in the current CLI or tests is slow enough to need compilation (the whole suite with the Python loop forced takes about a minute on this machine, against half a minute with Cython).
3. **Pricing was the slow path, and Cython never runs it** (before the follow-up above). The `.pyx` has no price solver, so `--with-pricing` always uses the Python loop: 0.07 ms per unit for the 4-agent forest, 0.6–0.75 ms for the 10–11-agent cases, 6 s for 8,000 Amazon units. Three quarters of that time is `solve_linear_system`, called 12 times per step for 11 agents: once for the prices and once per column of `(I − S·W)⁻¹`, only to take that inverse's row sums (the demand multipliers). Those row sums are one more solve, `(I − S·W)⁻¹ · 1`, so a single LU factorisation reused for two right-hand sides would cut the solver time by roughly 10× and a whole pricing run by about 3×. Warm-starting the convergence certificate from the previous step and skipping zero entries of the sparse `W` would add to that.
4. **Maintenance cost.** The extension doubles the engine (the `.pyx` mirrors the Python phases), needs the parity test, a stale-build guard, and a CI matrix twice as large.

## Recommendation

- **Keep the Cython loop for now**: it is parity-tested, it costs nothing at run time when absent, and removing it changes no output.
- **Do not extend it.** Any engine change (decision D5, `version_specs/V09_SPEC.md`) should be written in Python only.
- **Drop it with either D5 option.** Option A (path dependence) steps by year, so the loop shrinks from up to 80,000 iterations to at most a few hundred; option B (drop the claim) evaluates the static function directly. Either way the loop the extension compiles disappears.
- **Pricing: optimise its solver, not the `.pyx`.** The redundant solves are gone (1.4–3.3× on the pricing runs, identical numbers, see the follow-up); a warm start and sparse elimination are the next steps if pricing is ever un-quarantined, at the cost of re-checking the golden pricing snapshots.
