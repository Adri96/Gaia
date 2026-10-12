# Changelog

## Unreleased — data-driven ecosystems (Step 7)

Step 7 of `TOP_PRIORITIES_REPORT.md` (findings E6, E7). **No output number changes**: the golden snapshots are untouched, which proves that the case files reproduce the 0.9.0 code-defined cases exactly; text and JSON output of the 0.9 command lines are byte-identical.

### Added

- **Case file format** (`gaia/ecosystem_io.py`, E7): JSON, `"gaia_schema": 1`, stdlib only. `ecosystem_from_dict` / `ecosystem_to_dict`, `load_ecosystem` / `save_ecosystem`, `case_from_dict` / `load_case_file`. It covers everything the four cases use (resource with `area_ha`, a reference density or hectare units; agents, shared or inline damage curves, `annual_value_per_ha`; interactions and keystones; carbon, resilience, substrate, discount schedules or profiles; EXPERIMENTAL pricing; restoration costs, recovery and succession; `calibration_regime`). Every number is bare or `{value, unit, source, confidence, note}`, which becomes a `gaia.provenance.Param`; `provenance_defaults` covers repeated list items. Validation on load names the JSON path and rejects unknown keys, duplicate keys and NaN/Infinity. Round trips (ecosystem → dict → ecosystem, dict → ecosystem → dict) are exact and tested.
- **`gaia run <case | file.json> [options]`** (E6): one CLI for shipped cases and your own files, with `--total-units` for the resource size and every 0.9 option; `gaia run <case> --help` shows the case's defaults. `gaia.cases.load_case(name_or_path)` returns a `Case` with `build_ecosystem(...)`, `run_extraction(...)`, `run_restoration(...)` and `report(result)`.
- The four cases as data files, `gaia/cases/data/{forest,costa_brava,posidonia,amazon_forest}.json`, shipped in the wheel and sdist. The derivations from the former module docstrings are in `gaia/cases/definitions/CASE_NOTES.md`.
- README: *Writing your own case*, with a complete example file that a test runs.
- `version_specs/V09_SPEC.md`: **proposal, pending owner decision D5** (path dependence). Option A (a path-dependent engine: yearly time steps with extraction rates, relaxation, keystone hysteresis, substrate erosion over real time, recovery that depends on prior damage; a `dynamics` block in schema 2) and option B (drop the claim, evaluate the static function directly), with effects on Cython, golden tests and the format, effort estimates and a recommendation (B now, A staged later). Nothing is implemented.
- `docs/ENGINE_PROFILE.md` and `scripts/profile_engine.py` (decision D7): pure Python vs Cython on the four cases, extract and restore, with and without pricing, and a 100,000-unit full-depletion sweep. The compiled loop gains 1.2–3.3× on a whole run; pricing never uses it and spends three quarters of its time in n + 1 linear solves per step, where two would do. Recommendation: keep Cython for now, do not extend it, drop it with either D5 option, and optimise the pricing solver before any `.pyx` work. `--smoke` (tiny sizes) is run by a test, with and without the extension.

### Changed

- `python -m gaia ... --help` printed `usage: __main__.py`; the program name is now `gaia run <case>` (or `gaia <case>` for the legacy form).
- The `run_*` library wrappers took literal defaults (e.g. `tree_value=100.0`) that could drift from the case's `Param` values; every default now comes from the data file.
- `gaia --help` lists the cases and the deprecated forms; an unknown command or case exits with status 2.
- EXPERIMENTAL pricing is 1.4–3.3× faster with bit-identical results: `solve_prices` runs one Gaussian elimination for the prices and the columns of `(I − S·W)⁻¹` (`gaia.pricing.solve_linear_systems`) instead of n + 1, and computes `S·W` by row scaling.

### Deprecated (removed in 0.11)

- `gaia <case> [options]` and `python -m gaia.cases.<case> [options]`, with the 0.9 flags (`--trees` / `--hectares`, and the `--cut`, `--destroy`, `--tree-value`, `--revenue` aliases). They run the same code and print the same output, plus a `FutureWarning` on stderr.
- The case modules `gaia.cases.forest`, `costa_brava`, `posidonia`, `amazon_forest`: `build_<case>_ecosystem`, `run_<case>`, `run_<case>_restoration`, the reference-size constants and `main` remain as thin wrappers over the case files.

### Removed

- The duplicated per-case plumbing (four copies of `run_X`, `run_X_restoration`, `_parse_args` and `main`) and the private module constants (`_FOREST_SUCCESSION`, `_OAK_VALLEY_SUBSTRATE`, ...): use `load_case(name)` and the built ecosystem. `gaia.cli.CASES` (now `gaia.cases.CASE_NAMES` / `CASE_ALIASES`). The provenance helpers only the case modules used: `weight_params`, `keystone_params`, `edge_params`, `restoration_params`, `IDENTICAL_CURVES_NOTE`.

### Migration

| 0.9 | Now |
|---|---|
| `gaia forest --trees 10000 --units 5000` | `gaia run forest --total-units 10000 --units 5000` |
| `gaia posidonia --hectares 5000` | `gaia run posidonia --total-units 5000` |
| `--cut N`, `--destroy N` / `--tree-value E`, `--revenue E` | `--units N` / `--unit-value E` |
| `build_forest_ecosystem(total_trees=N, tree_value=V)` | `load_case("forest").build_ecosystem(total_units=N, unit_value=V)` |
| `run_forest(...)` (text) | `case.report(case.run_extraction(units, ...))` |
| `gaia.cases.forest._FOREST_SUCCESSION` | `load_case("forest").succession_curve` |
| An ecosystem in Python | still works; `save_ecosystem(eco, "case.json")` writes it as a file |

One difference between the two command lines: the `source` of a user-supplied value names the flag that set it, `user-supplied (--unit-value / unit_value)` with `gaia run` where the legacy form says `(--unit-value / tree_value)`; for Posidonia `(--total-units / total_units)` instead of `(--hectares / total_hectares)`.

## 0.9.0 — audit fixes (2026-10-12)

The fixes from the 2026-10 audit (`TOP_PRIORITIES_REPORT.md`, Steps 0–6), on branch `audit-fixes` after tag `v0.8.1-pre-audit`. The commit messages record every changed number and the reason for it. The changes break the API, CLI and JSON (see *Migration* below), hence the minor-version bump.

**Results are illustrative.** Every output now says how many of its parameters are placeholders or low-confidence. The numbers test the model's internal consistency, not the world.

### Fixed

- **Restoration value did not depend on how much was restored** (C1). Restoration now starts from a real degraded state and retraces that extraction's damage path in reverse. Recovered value = recovery efficiency × damage reversed × substrate ceiling, so it never exceeds the damage reversed. Trophic amplification of recovery, which made consumers recover 1.6–4.1× faster, and the 0.5× recovery cascade are gone (`9037b8a`).
- **One-off totals and yearly flows were mixed** (C2). Agent values are yearly flows, while revenue and restoration costs are one-off. The two are compared only through the present value of the flow. Every monetary line and JSON key carries its unit (`6a3feea`).
- **Results depended on the arbitrary size of the resource** (C4). Agent values are €/ha/yr × `area_ha`, so results are invariant to how finely the resource is divided into units (`c791b6c`).
- **NPVs could diverge** (C3). Validation rejects any configuration whose scarcity rate or carbon-price growth is not strictly below the discount rate. The case scarcity rates were brought within the empirical range: Costa Brava and Amazon 1.28%, Posidonia and the environmental profile 1%. One year convention (flows at the end of years 1..H) replaces the old off-by-one (`9d3eea1`).
- **Carbon was counted two or three times** (C5). `gaia/carbon.py` is the single owner of carbon value. The carbon agents and carbon anchors were removed or renamed to their non-carbon services, and the substrate loss is counted once, as a reduced restoration ceiling (`4a26845`, `c429a9c`).
- **Amazon carbon stock 10× too low** (C6): the reference area is now 1,000 ha (400 trees/ha) (`97508b9`).
- **Soil erosion conversion 10× too small** (C7): 1 t/ha = 0.0769 mm at 1,300 kg/m³ (`2a389c3`).
- **Unsafe endogenous pricing** (C8): convergence is certified at each step; there is no silent fallback to static values, and every agent is anchored (`aa17792`).
- **Cascades saturated** (S2). Incoming edge strengths are capped at 1.0 per agent, keystone boosts included (12 Amazon and 3 Costa Brava edges were rescaled mechanically). The cascade acts on the service still standing, `effective = direct + (1 − direct) × pressure`. Amazon's marginal cost from 50% to 100% depletion is no longer zero (`2beaaee`, `4c7816d`).
- **Posidonia carbon contradicted itself** (S5): one absorption value is used, the IPCC (2013) Tier 1 seagrass rate (`4a26845`).
- **The Cython and Python engines diverged** on substrate types and marine matte. A parity test now compares every step and field at a relative tolerance of 1e-12, and a stale extension is detected and not used (`6d0baa1`).
- **The text report computed figures the JSON did not have** (E3). The report now only formats result fields, so text and JSON cannot disagree (`7fd0bbb`).
- **JSON allowed NaN/Infinity, and inputs were not checked for finiteness** (E8). Output is now strict JSON, and every numeric input must be finite (`bce41d1`).
- **CLI**: the warning about unused restoration flags now reads the parsed arguments, not `sys.argv`. An `--output` write error is a clean message. The default Amazon JSON drops from ~169 MB to 16 KB (`61c1dd7`).

### Changed

- **Monetary semantics** (decisions D1, D2): `annual_value_per_ha` is the € per hectare per year of service lost at full damage, and `Resource.area_ha` is required. `net_social_cost = pv_externality − revenue`, so positive means society loses (the sign is flipped from before).
- **Carbon price** (D3): the social cost of carbon, US EPA (2023) $190/t (2020 emissions) converted at the ECB 2020 rate to €166.35/t, growing 1.3%/yr. €80 (EU ETS) survives only as the labelled market/ETS view (`--carbon-price ets`).
- **"Prevention advantage" is replaced** (C9): `restoration_cost_ratio` = 1 + restoration cost per unit / unit value, described as an input-price ratio, and `destroy_then_restore_penalty` = the PV cost of cutting and restoring over not cutting, split into restoration cost, maturation gap, substrate loss, recovery shortfall and carbon not recovered (`f9f3c65`).
- **Calibration regime**: `Ecosystem.calibration_regime` (A empirical / B direct effects only) is required when there are edges, and all four cases declare B. A `CalibrationWarning` fires when health at the safe threshold is below 0.8; it fires for every shipped case (`2beaaee`).
- **Model constants** (trophic, keystone, edge limits) live in `gaia/constants.py`, each with a source or a PLACEHOLDER flag (`2beaaee`).
- **Endogenous pricing is quarantined** (D4): `--with-pricing` is labelled EXPERIMENTAL in help, text and JSON. It raises `PricingConvergenceError` when a step cannot be certified, and it is ignored, with a warning, in restore mode (`aa17792`).
- **Agent values**: the forest and Costa Brava values, previously back-solved to produce an outcome, are global biome means per hectare (de Groot 2012, Costanza 2014, low confidence). Posidonia's are restated per hectare. Amazon's are brought to its documented non-carbon anchors (`c791b6c`, `4a26845`).
- **Damage-curve invariants** (six shape properties) are checked on every run, for every agent, by `validate_ecosystem` (`bce41d1`).
- **Maturation gap**: a discounted PV over the discount horizon, measured against the substrate-capped mature value (`6a3feea`, `c429a9c`, `f9f3c65`).
- **Confidence band**: renamed the externality band and labelled HEURISTIC (`7fd0bbb`).
- **Deprecated flag aliases** (`--cut`, `--destroy`, `--tree-value`, `--revenue`) warn with `FutureWarning` (`61c1dd7`).
- **Engine refactor**: `run_extraction` and `run_restoration` are split into phases, with no behaviour change (`d4d1da7`).
- **README and `PROJECT_DEFINITION.md`** describe the model as it is: illustrative, with a path-independent engine (open decision D5), and a proposed v1.0 of one credible case pending decision D6. README examples are generated from the code. The version specs carry "superseded in part" notes.

### Removed

- `Agent.monetary_rate` (raises, pointing to `annual_value_per_ha`), `CarbonProfile.carbon_price_per_tonne`, `Agent.succession_curve`, `RestorationConfig`, `SubstrateProfile.water_availability_mm_yr` / `water_clarity_kd`, and `SubstrateState`'s water-clarity and `years_to_recover` fields (`6a3feea`, `4a26845`, `3867e7b`).
- `RestorationResult.prevention_advantage`, `prevention_advantage_with_substrate`, `prevention_advantage_v06`, `substrate_recovery_cost`, `extraction_npv`; `PreventionAdvantageV06` and `compute_prevention_advantage_v06` (`f9f3c65`, `3867e7b`).
- `SimulationStep.discount_factor_at_step`, `npv_externality`, `carbon_price_used` (`3867e7b`).
- `PricingConfig.fallback_to_static`, the scarcity-scaling fallback, and `solve_prices(static_prices=)`; the power-iteration spectral-radius estimate (`aa17792`).
- `propagate_interactions(recovery_mode=, recovery_cascade_factor=)` and `RECOVERY_CASCADE_FACTOR` (`3867e7b`).
- The carbon agents and anchors: Forest "General Biosphere" became "Watershed & Local Climate", Costa Brava "Carbon & Climate" became "Fire & Microclimate Regulation", and Posidonia "Blue Carbon" was removed, with the other weights renormalised (`4a26845`).

### Added

- **Safety net**: golden snapshots of every case × extraction / pricing / restoration scenario (`scripts/regen_golden.py`, `--check`), Cython/Python parity tests, and property tests (`b40e1c0`, `6d0baa1`).
- **Horizon sensitivity**: PV at 50, 100 and 200 years in every output (`9d3eea1`).
- **Restoration**: `run_restoration(starting_state=, units_lost=)` and `--units-lost` on every case; `annual_damage_reversal`, `depletion_before` / `depletion_after` and `initial_ecosystem_health` in the results (`9037b8a`).
- **`--area-ha`** and **`--carbon-price {scc,ets}`** on every case (`c791b6c`, `4a26845`).
- **Parameter provenance and calibration status** (Step 5): `gaia.provenance.Param(value, unit, source, confidence, note)` for every meaningful parameter of the four cases, and `Ecosystem.provenance`. Every result has a `calibration` status: the text reports open with an `ILLUSTRATIVE: N of M recorded parameters are placeholders (p) or low-confidence (l)` banner and end with a Parameter Provenance section, and the JSON has a top-level `calibration` block (`8e349ee`).
- **Packaging**: `pyproject.toml`; a `gaia <case> [args]` command and `python -m gaia`; Cython optional at build time; a CI matrix (Python 3.9–3.12 × Cython / pure Python, golden check, README check, ruff, mypy) (`5974aca`, `d4ea31f`).
- **`--steps-every N`** for JSON, which is summary-only by default above 10,000 steps (`61c1dd7`).
- **`scripts/gen_readme_examples.py`** (`--check`): the README examples are regenerated from the code, and a test fails when they drift (`b0cb831`).
- **`LICENSE`**, and a single version source in `gaia/__init__.py` (`9a007e9`).

### Migration (API, CLI and JSON users)

**Python API**

| Before | Now |
|---|---|
| `Agent(monetary_rate=X)` (€ total at full damage) | `Agent(annual_value_per_ha=v)` in €/ha/yr. The yearly total is `v × Resource.area_ha` (`Agent.annual_value(area_ha)`). Passing `monetary_rate=` raises `TypeError` |
| `Resource(...)` | `Resource(..., area_ha=...)` is required (finite, > 0) |
| `Ecosystem(..., interactions=[...])` | Also `calibration_regime=CalibrationRegime.DIRECT_ONLY` (or `EMPIRICAL`), required when there are edges. Each agent's incoming strengths must sum to ≤ 1.0, keystone boosts included |
| `SimulationResult.total_private_revenue` | `revenue` (€, one-off) |
| `SimulationResult.total_externality_cost` | `annual_externality` (€/yr) and `pv_externality` (€ PV) |
| `SimulationResult.net_social_cost` = revenue − externality | `net_social_cost` = `pv_externality − revenue` (sign flipped) |
| `SimulationStep.agent_costs`, `marginal_cost`, `cumulative_cost`, `private_revenue` | `agent_annual_costs`, `marginal_annual_externality`, `annual_externality` (€/yr), `revenue` (€, cumulative) |
| `RestorationResult.total_recovered_value`, `net_restoration_value`, `total_maturation_gap` | `annual_recovered_value` (€/yr), `net_restoration_pv` (€ PV), `maturation_gap_pv` (€ PV) |
| `RestorationResult.prevention_advantage*` | `restoration_cost_ratio` (input-price ratio) and `destroy_then_restore_penalty` (`.total`, `.ratio`, components) |
| `run_restoration(eco, k, cost, fns)` restored k units from an unspecified state | It restores k of `units_lost` units (default k) cut from the pristine resource, or starts from `starting_state=` |
| `CarbonProfile(carbon_price_per_tonne=...)` | Removed. The price is `DiscountConfig.carbon_price_current` (default: the SCC); `gaia.carbon.with_carbon_price_view(discount, "ets")` gives the market view |
| A `DiscountConfig` with scarcity ≥ discount rate | Rejected (`ValueError`) |
| `--with-pricing` / `PricingConfig` falling back to static values | `PricingConvergenceError` (a `ValueError`) at the first step that cannot be certified. Every agent needs an anchor (`gaia.pricing.anchor_every_agent`) |
| — | `result.calibration` (`CalibrationStatus`) and `Ecosystem.provenance` (list of `Param`) |

**CLI**

- Use `gaia <case>` (or `python -m gaia <case>`). `python -m gaia.cases.<case>` still works.
- `--cut` / `--destroy` → `--units`; `--tree-value` / `--revenue` → `--unit-value`. The old names still work, with a `FutureWarning`.
- In restore mode, `--units-lost N` sets the starting state (default: `--units`).
- New flags: `--area-ha`, `--carbon-price {scc,ets}`, `--steps-every N`. JSON with more than 10,000 steps is summary-only unless `--steps-every` is given.
- `--with-pricing` can now fail with `Error: ...` and exit status 1. It is ignored, with a warning, in restore mode.
- Text reports start with the `ILLUSTRATIVE` banner, so the title is no longer the first line.

**JSON**

- New top-level `calibration` block (right after `mode`). Strict JSON: a non-finite number is `null` plus `<key>_null_reason`.
- Every money key carries a unit suffix (`_eur_yr`, `_eur_pv`, `_eur`, `_eur_per_ha_yr`, `_eur_per_t`). Renamed keys:
  - `summary.total_private_revenue` → `revenue_eur`
  - `summary.total_externality_cost` → `annual_externality_eur_yr`, plus `pv_externality_eur_pv` and `pv_externality_h{50,100,200}_eur_pv`
  - `summary.net_social_cost` → `net_social_cost_eur_pv` (new definition and sign)
  - restoration `summary.total_recovered_value` / `net_restoration_value` / `total_restoration_cost` → `annual_recovered_value_eur_yr` / `net_restoration_value_eur_pv` / `total_restoration_cost_eur`
  - `npv_analysis.{direct,carbon_release,carbon_foregone,total,horizon}` → `services_eur_pv`, `carbon_release_eur_pv`, `carbon_foregone_eur_pv`, `total_eur_pv`, `horizon_years`; `substrate_damage` → `substrate_unrecoverable_eur_pv` (not added to the total)
  - restoration `npv_analysis.{cost,service_benefits,carbon_benefits,total_benefits,net_present_value}` → the same names with `_eur_pv`; `carbon_breakeven.*_price` → `*_price_eur_per_t`; `maturation.total_maturation_gap` → `maturation_gap_eur_pv`
  - steps: `marginal_cost` / `cumulative_cost` / `private_revenue` → `marginal_externality_eur_yr` / `externality_eur_yr` / `revenue_eur`
  - `ecosystem.agents[].monetary_rate` → `annual_value_eur_per_ha_yr` and `annual_value_eur_yr`; `ecosystem.resource.unit_value` → `unit_value_eur`; `carbon_price_per_tonne` → `carbon_price_eur_per_t` (+ `carbon_price_basis`, `carbon_price_growth`)
  - pricing: `spectral_radius` / `converged` → `spectral_radius_bound` / `convergence_check`, plus `experimental: true`, `status` and `note`; `prices` → `prices_eur_yr`
- Removed keys: `prevention_advantage`, `prevention_advantage_v06`, `substrate.prevention_advantage_with_substrate`, and the per-step discount fields.
- Added keys: `ecosystem.calibration_regime`; `area_ha` and `units_per_ha`; `destroy_then_restore_penalty`; `restoration_cost_ratio`; the per-agent direct/cascade split; `annual_externality_band` (heuristic); the extraction `substrate` block; `npv_analysis.discount`; the carbon tonnes; `units_lost`, `depletion_before` / `depletion_after`, `initial_ecosystem_health` and `annual_damage_reversal_eur_yr`; `steps_every`.

## 0.8.1 and earlier

See `version_specs/` (V01–V081) and the roadmap in `PROJECT_DEFINITION.md`. Those documents describe each version as built; their notes say what the audit fixes changed.
