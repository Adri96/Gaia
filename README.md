# Gaia — Externality Computation Framework

> **Profits are privatized, but externalities are socialized.**
>
> Gaia makes those externalities visible, measurable, and expressible in monetary terms — in both directions.

Gaia is a Python library for simulating and quantifying the hidden costs that private actors impose on ecosystems and society when extracting shared natural resources — and the hidden *value* generated when those resources are preserved or restored.

---

## What Problem Does Gaia Solve?

When a timber company cuts 5,000 trees, its accounts show a clear profit. What does not appear in any account is the cost borne by everyone else: degraded water quality for surrounding communities, collapsed habitats for animal populations, disrupted pollination networks, and tonnes of CO₂ released from a forest that no longer exists to absorb it.

Gaia computes those costs. It simulates resource extraction step by step, propagates damage through every dependent agent in the ecosystem, and produces a **total externality bill** alongside the private revenue — giving decision-makers the full economic picture.

The same model runs in reverse: Gaia can compute the social return on a reforestation investment, the net present value of keeping a forest intact, and the irrecoverable gap between "cut now, replant later" versus "don't cut."

---

## Scientific Foundations

Gaia is grounded in established science, not invented mechanics. The key principles:

- **Thermodynamic irreversibility** — destruction is cheap; restoration fights entropy and always costs more.
- **Trophic cascade amplification** — damage to primary producers (trees, plants) amplifies up the food chain. A 10% reduction in forest biomass causes a disproportionately larger reduction in animal populations.
- **Carrying capacity dynamics** — ecosystems tolerate modest extraction, then collapse non-linearly past the safe threshold. This is modeled as an S-curve (logistic) damage function.
- **Coevolutionary propagation** — extraction doesn't just remove a resource; it changes conditions for everything that depended on it. This is why Gaia simulates step by step rather than calculating a static formula.

The damage functions are not arbitrary — they encode these principles mathematically and are tested against six scientific invariants on every run.

---

## Project Structure

```
Gaia/
├── gaia/                      # Core library
│   ├── __init__.py
│   ├── models.py              # Data model: Resource, Agent, Ecosystem, SimulationResult, RestorationResult,
│   │                          #   SuccessionCurve, CarbonProfile, ResilienceConfig, MaturationStep (v0.4)
│   ├── damage.py              # Damage function library (logistic, exponential, piecewise)
│   ├── recovery.py            # Recovery function library (logistic_recovery, linear_recovery)
│   ├── propagation.py         # Trophic cascade amplification and interaction propagation (v0.3)
│   ├── succession.py          # Succession curve evaluation and maturation timeline (v0.4)
│   ├── carbon.py              # Double carbon externality: release + foregone absorption (v0.4)
│   ├── resilience.py          # Resilience zones, confidence interpolation, confidence bands (v0.4)
│   ├── validation.py          # Input validation with scientific constraints
│   ├── simulation.py          # Simulation engine (extraction + restoration modes)
│   ├── report.py              # Plain-text report formatter (externality + restoration reports)
│   └── cases/
│       ├── __init__.py
│       ├── forest.py          # Oak Valley Forest — temperate deforestation/restoration (CLI + API)
│       ├── costa_brava.py     # Costa Brava Holm Oak Forest — Mediterranean deforestation/restoration (CLI + API)
│       └── posidonia.py       # Costa Brava Posidonia Meadow — marine seagrass destruction/restoration (CLI + API)
├── tests/
│   ├── __init__.py
│   ├── test_damage.py         # Mathematical property tests for all damage functions
│   ├── test_models.py         # Data model unit tests
│   ├── test_validation.py     # Validation logic tests
│   ├── test_simulation.py     # Simulation engine tests
│   ├── test_forest.py         # End-to-end Oak Valley Forest case tests
│   ├── test_costa_brava.py    # End-to-end Costa Brava forest case tests
│   ├── test_posidonia.py      # End-to-end Posidonia marine case tests
│   ├── test_recovery.py       # Mathematical property tests for all recovery functions
│   ├── test_restoration.py    # Restoration engine correctness and economic claim tests
│   ├── test_succession.py     # Succession curve evaluation, maturation timeline, maturation gap (v0.4)
│   ├── test_carbon.py         # Carbon release, double externality, payback period (v0.4)
│   ├── test_resilience.py     # Resilience zone computation, confidence interpolation (v0.4)
│   └── test_maturation.py     # End-to-end integration tests for v0.4 maturation + resilience
├── PROJECT_DEFINITION.md      # Scientific foundations and architecture vision
├── ROADMAP.md                 # Version roadmap and verification strategy
├── V01_SPEC.md                # Detailed v0.1 specification
└── V04_SPEC.md                # Detailed v0.4 specification
```

### Key modules

| Module | Responsibility |
|---|---|
| `gaia/models.py` | All data containers: `Resource`, `Agent`, `Ecosystem`, `SimulationStep`, `SimulationResult`, `RestorationCost`, `RestorationStep`, `RestorationResult`, plus v0.4: `SuccessionCurve`, `CarbonProfile`, `ResilienceConfig`, `MaturationStep`, `RestorationConfig` |
| `gaia/damage.py` | Damage function factories — each returns a `float → float` callable |
| `gaia/recovery.py` | Recovery function factories — `logistic_recovery`, `linear_recovery`; slower than damage, encoding entropy asymmetry |
| `gaia/propagation.py` | Trophic cascade amplification and interaction propagation (v0.3) |
| `gaia/succession.py` | Succession curve evaluation (pioneer → intermediate → climax), maturation timeline, maturation gap (v0.4) |
| `gaia/carbon.py` | Double carbon externality: release + foregone absorption, monetized cost, payback period (v0.4) |
| `gaia/resilience.py` | Resilience zone computation (green/yellow/red), confidence interpolation, confidence bands (v0.4) |
| `gaia/simulation.py` | `run_extraction(ecosystem, units)` — extraction loop with resilience tagging; `run_restoration(ecosystem, units, cost, fns, succession_curve, time_horizon)` — restoration loop with optional maturation pass |
| `gaia/report.py` | `format_report(result)` — externality report with resilience assessment, carbon accounting, and confidence bands; `format_restoration_report(result)` — restoration report with maturation timeline, maturation gap, and carbon recovery |
| `gaia/cases/forest.py` | Oak Valley Forest — temperate forest, 4 agents, 8/25/60yr succession |
| `gaia/cases/costa_brava.py` | Costa Brava Holm Oak Forest — Mediterranean forest, 11 agents, 12/35/80yr succession |
| `gaia/cases/posidonia.py` | Costa Brava Posidonia Meadow — marine seagrass, 11 agents, 20/50/120yr succession |

---

## Running the Project

### Prerequisites

Python 3.9+ with no third-party dependencies required (stdlib only). For tests, install pytest:

```bash
pip install pytest
```

### CLI — Forest Deforestation Case

```bash
# Default: 10,000-tree forest, 30% safe threshold, cut 5,000 trees
python -m gaia.cases.forest

# Custom parameters
python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000

# All options
python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000 --tree-value 100.0
```

Sample output (v0.4 — with resilience assessment, carbon accounting, and confidence band):

```
═══════════════════════════════════════════════════════════════
  GAIA — Externality Report: Oak Valley Forest
═══════════════════════════════════════════════════════════════
  Resource:               1,000 units  (Oak Valley Forest)
  Safe Threshold:           300 units  (30.0%)
  Units Extracted:          700
  Depletion:              70.0%
  Ecosystem Health:        1.4%
  ── Private Gains ─────────────────────────────────────────────
  Revenue:                                      70,000.00€
  ── Externalized Costs ────────────────────────────────────────
  Human Communities:                           150,000.00€
    → Direct: €145,854 | Cascade: €4,146
  Animal Populations:                          350,100.00€
    → Trophic amplification: 1.6× (primary consumer)
  Vegetation & Flora:                          145,854.36€
  General Biosphere:                           534,653.46€
  TOTAL EXTERNALITY:                         1,180,607.82€
  NET SOCIAL COST:                          -1,110,607.82€

  ── Resilience Assessment ───────────────────────────────────────
  Current zone:          ⚠⚠ RED — Resilience likely compromised
  Model confidence:      43%
  Zone transitions:
    Green → Yellow at step 201 (20% depletion)
    Yellow → Red at step 300 (30% depletion)
  ⚠ IRREVERSIBILITY WARNING at step 601 (60% depletion)

  ── Carbon Accounting ───────────────────────────────────────────
  Carbon released (biomass+soil):                 612 t CO₂
  Future absorption foregone:                    15.4 t CO₂/yr
  Carbon externality (release):                 49,000.00€
  Carbon externality (foregone):                 1,232.00€/yr

  ── Externality with Confidence Band ─────────────────────────────
  Total Externality:                         1,180,607.82€
  Confidence band (43%):          505,974.78€ — 1,855,240.85€
═══════════════════════════════════════════════════════════════
```

The report now includes **resilience zones** (green/yellow/red), **carbon accounting** (release + foregone absorption), and **confidence bands** that widen as model confidence degrades.

#### Restoration mode

```bash
# Restore 5,000 trees (default costs: €50 planting + €10/yr × 10 yr = €150/tree)
python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000 --mode restore

# With maturation timeline (v0.4): simulate 60 years of succession
python -m gaia.cases.forest --cut 500 --mode restore --time-horizon 60

# Custom restoration costs
python -m gaia.cases.forest --cut 5000 --mode restore \
  --planting-cost 60.0 --maintenance-cost 12.0 --maintenance-years 10
```

Sample restoration output (v0.4 — with maturation timeline, maturation gap, and carbon recovery):

```
═══════════════════════════════════════════════════════════════
  GAIA — Restoration Report: Oak Valley Forest
═══════════════════════════════════════════════════════════════
  Resource:                         1,000 units  (Oak Valley Forest)
  Units Restored:                     500
  Restoration Coverage:             50.0%  of total capacity
  Final Ecosystem Health:          100.0%
  ── Restoration Costs ───────────────────────────────────────────
  TOTAL RESTORATION COST:                       75,000.00€
  ── Recovered Ecosystem Services ────────────────────────────────
  TOTAL RECOVERED VALUE:                     1,199,950.00€
  NET RESTORATION VALUE:                     1,124,950.00€
  ── Prevention vs Restoration ───────────────────────────────────
  Prevention is 2.50× cheaper than destroy‑then‑restore.

  ── Maturation Timeline ─────────────────────────────────────────
  Years to first services:                          2 years
  Years to 50% service recovery:                   31 years
  Years to 90% service recovery:                   48 years

  ── Maturation Gap ──────────────────────────────────────────────
  Lost services during maturation:          36,581,553.26€
  (accumulated externality while waiting for succession)
  This cost is IN ADDITION to restoration costs.

  ── Carbon Recovery ─────────────────────────────────────────────
  Cumulative CO₂ absorbed:                        325 t CO₂
  Over  60 years of maturation
═══════════════════════════════════════════════════════════════
```

The restoration report now reveals the **hidden temporal cost**: while the direct planting costs €75,000, the ecosystem loses **€36.6M in services** during the decades it takes for the succession to reach maturity. The `--time-horizon` flag enables this time-aware analysis.

### Python API — Extraction

```python
from gaia.cases.forest import build_forest_ecosystem
from gaia.simulation import run_extraction
from gaia.report import format_report

# Build and run
ecosystem = build_forest_ecosystem(
    total_trees=10_000,
    safe_threshold_ratio=0.3,
    tree_value=100.0,
)
result = run_extraction(ecosystem, units_to_extract=5_000)

# Inspect results
print(f"Revenue:     €{result.total_private_revenue:,.2f}")
print(f"Externality: €{result.total_externality_cost:,.2f}")
print(f"Net cost:    €{result.net_social_cost:,.2f}")
print(f"Health:      {result.final_ecosystem_health:.1%}")

# Per-step data
for step in result.steps:
    print(step.units_extracted, step.marginal_cost, step.ecosystem_health)

# Full formatted report
print(format_report(result))
```

### Convenience wrapper — Extraction

```python
from gaia.cases.forest import run_forest

report = run_forest(
    total_trees=10_000,
    safe_threshold_ratio=0.3,
    trees_cut=5_000,
    tree_value=100.0,
)
print(report)
```

### Python API — Restoration

```python
from gaia.cases.forest import build_forest_ecosystem
from gaia.models import RestorationCost
from gaia.recovery import logistic_recovery
from gaia.simulation import run_restoration
from gaia.report import format_restoration_report

ecosystem = build_forest_ecosystem(total_trees=10_000, safe_threshold_ratio=0.3)
cost = RestorationCost(
    planting_cost_per_unit=50.0,
    annual_maintenance_per_unit=10.0,
    maintenance_years=10,
)
# One recovery function per agent (same order as ecosystem.agents)
recovery_fns = [logistic_recovery(threshold=0.3) for _ in ecosystem.agents]
result = run_restoration(ecosystem, units_to_restore=5_000, restoration_cost=cost,
                         recovery_functions=recovery_fns)

print(f"Restoration cost:   €{result.total_restoration_cost:,.2f}")
print(f"Recovered value:    €{result.total_recovered_value:,.2f}")
print(f"Net value:          €{result.net_restoration_value:,.2f}")
print(f"Prevention advantage: {result.prevention_advantage:.2f}×")

print(format_restoration_report(result))
```

### Convenience wrapper — Restoration

```python
from gaia.cases.forest import run_forest_restoration

report = run_forest_restoration(
    total_trees=10_000,
    safe_threshold_ratio=0.3,
    trees_to_restore=5_000,
    planting_cost_per_tree=50.0,
    annual_maintenance_per_tree=10.0,
    maintenance_years=10,
)
print(report)
```

### CLI — Costa Brava Holm Oak Forest

A Mediterranean forest ecosystem with **11 agents** spanning the full biological web: the underground mycorrhizal network (the invisible foundation everything else depends on), understory shrubs and aromatic plants, pollinators, birds, mammals, apex raptors (all four European vulture species nest in Catalonia), the watershed, carbon cycle, and the Costa Brava's coastal tourism economy.

What makes this case different from the generic forest: the safe threshold is **25%** instead of 30% — Mediterranean forests are more fragile. Summer drought is the defining constraint, regeneration is slower, and fire risk creates positive feedback loops once canopy cover is lost. The mycorrhizal fungi carry the highest dependency weight (0.13) because they are the underground infrastructure that conditions tree regeneration, soil nutrient cycling, and water access for all remaining trees.

```bash
# At the safe threshold — where damage begins accelerating
python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 2500

# Past the threshold (40% extraction)
python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 4000

# Heavy extraction (60%)
python -m gaia.cases.costa_brava --trees 10000 --threshold 0.25 --cut 6000

# Default run (40% extraction)
python -m gaia.cases.costa_brava
```

At 40% extraction: €240,000 in timber revenue vs **€1,980,000 in annual social costs**. Ecosystem health: 42.5%.

#### Restoration mode

```bash
# Restore 4,000 trees (default costs: €80 planting + €15/yr × 15 yr = €305/tree)
# Mediterranean premium: drought-hardy saplings, irrigation, fire management
python -m gaia.cases.costa_brava --cut 4000 --mode restore
```

Mediterranean forest restoration is harder than temperate: holm oak grows at max 0.5 m/yr, summer drought requires irrigation during establishment, and the mycorrhizal network must re-establish before full ecosystem function returns. Prevention advantage: **6.08×** — every euro saved by not cutting saves six in future restoration costs.

### CLI — Costa Brava Posidonia Meadow

*Posidonia oceanica* is a seagrass that forms the foundation of Mediterranean coastal ecosystems. It absorbs **15× more CO₂ per hectare than the Amazon rainforest**, stores carbon in its sediment matte for millennia, filters bathing water, nurseries fish (the Medes Islands MPA proved fish biomass reaches 80× higher inside protected meadows), and physically protects Costa Brava beaches from erosion through wave attenuation and leaf-litter cushions. It grows at 1–6 cm per year — any significant destruction is effectively irreversible on a human timescale.

This case has **11 agents**: the meadow itself, coralligenous reefs and red coral (centuries-old biogenic habitats), epiphytic algae, marine invertebrates, fish populations, marine megafauna (dolphins, sea turtles), seabirds including the Mediterranean-endemic Audouin's gull, coastal protection, water quality, blue carbon, and human communities whose tourism economy depends on all of the above.

**The marine economics are inverted from the forest case.** Private revenue from Posidonia destruction (coastal development, marina construction, trawling permits) is a **one-time gain**. Ecosystem service losses are **annual recurring costs** — every year the meadow is gone, the losses compound. The report flags this explicitly: at 40% destruction, the one-time revenue of €5M is fully offset by annual ecosystem losses within **1.3 years**, after which society loses ~€4M every year, indefinitely.

```bash
# At the safe threshold (20% = 1,000 ha destroyed)
python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 1000

# Past the threshold (40% = 2,000 ha, representative of a major marina project)
python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 2000

# Heavy destruction (60% = 3,000 ha, catastrophic loss)
python -m gaia.cases.posidonia --hectares 5000 --threshold 0.20 --destroy 3000

# Default run (40% destruction)
python -m gaia.cases.posidonia
```

At 40% destruction: €5,000,000 one-time revenue vs **€3,973,869/year** in recurring social costs. The one-time gain is erased in 1.3 years. Ecosystem health: 32%.

#### Restoration mode

```bash
# Restore 2,000 ha (default costs: €50,000 planting + €5,000/yr × 30 yr = €200,000/ha)
# Specialist diving teams, substrate preparation, decades of monitoring
python -m gaia.cases.posidonia --destroy 2000 --mode restore
```

Posidonia restoration is among the most expensive ecological interventions known. The default cost of **€200,000/ha** reflects specialist diving teams, substrate preparation, donor material collection, and 30 years of active monitoring — because Posidonia grows at only 1–6 cm/year. Prevention advantage: **81.00×** — the cost of not destroying 2,000 ha of Posidonia (€5M foregone revenue) is 81 times cheaper than destroying it and trying to restore it (€400M in restoration costs).

---

## Running the Tests

```bash
# All tests
pytest

# With verbose output
pytest -v

# Specific test file
pytest tests/test_damage.py -v
pytest tests/test_forest.py -v

# Run by test name pattern
pytest -k "monotonicity" -v
```

The test suite has **375 tests** covering:

- **Mathematical invariants** — all damage functions are tested for boundary conditions (`f(0)≈0`, `f(1)≈1`), monotonicity, output range, non-linearity at the threshold, and convexity in the post-threshold zone. These run across 3 function types × 5 threshold values.
- **Recovery invariants** — all recovery functions are tested for the same boundary conditions plus the entropy asymmetry invariant: recovery must be slower than equivalent damage at every point.
- **Ecological plausibility** — all three case scenarios verify their economic story: externality < revenue at safe extraction, externality > revenue past the threshold (or the marine inversion equivalent for Posidonia).
- **Restoration engine** — cost accumulation, service value monotonicity, prevention advantage arithmetic, validation (rejects over-planting, wrong number of recovery functions).
- **Simulation correctness** — marginal cost accumulation, health index calculation, step counting, both extraction and restoration modes.
- **Succession curves (v0.4)** — monotonicity, continuity at phase boundaries, bounded output [0,1], phase identification (delay/pioneer/intermediate/climax), maturation timeline length, cumulative service monotonicity, maturation gap positivity, cross-ecosystem comparisons.
- **Carbon accounting (v0.4)** — release includes biomass+soil fraction, scales linearly with units, double externality (release+foregone) exceeds release-only, payback period comparisons, annual absorption scaling.
- **Resilience zones (v0.4)** — zone identification (green/yellow/red), confidence monotonically decreasing, continuous at boundaries, irreversibility warning triggers, wider warning zone comparisons, confidence band symmetry and widening.
- **Maturation integration (v0.4)** — end-to-end tests through `run_extraction` and `run_restoration`: resilience tagging in extraction, maturation timeline in restoration, backward compatibility when v0.4 features are not configured.
- **Validation** — invalid inputs are rejected with clear error messages (including new v0.4 validators for SuccessionCurve, CarbonProfile, ResilienceConfig).

---

## How to Add a New Case (More Agents / Resources)

A "case" is just an `Ecosystem` object. You assemble it from `Resource` and `Agent` dataclasses, pick a damage function for each agent, and hand it to `run_extraction`.

### Step 1: Define your resource

```python
from gaia.models import Resource

resource = Resource(
    name="Amazon Rainforest Section A",
    total_units=50_000,          # e.g. hectares
    safe_threshold_ratio=0.15,   # 15% can be safely extracted
    unit_value=2_000.0,          # revenue per hectare
)
```

### Step 2: Pick damage functions

Three options are available in `gaia.damage`:

```python
from gaia.damage import logistic_damage, exponential_damage, piecewise_damage

# S-curve: low damage before threshold, rapid acceleration above it (recommended)
fn = logistic_damage(threshold=0.15, steepness=12.0)

# Continuous exponential growth
fn = exponential_damage(threshold=0.15, base=2.0)

# Two-segment linear (simplest, useful for unknown-shape thresholds)
fn = piecewise_damage(threshold=0.15)
```

All three satisfy the same six scientific invariants. Choose based on the shape that best fits your ecosystem's known response dynamics.

### Step 3: Define your agents

```python
from gaia.models import Agent

agents = [
    Agent(
        name="Indigenous Communities",
        dependency_weight=0.25,         # fraction of total ecosystem dependency
        damage_function=logistic_damage(threshold=0.15, steepness=10.0),
        monetary_rate=800_000.0,        # max social cost if fully depleted (€)
        description="Subsistence livelihoods, cultural sites, medicinal plants",
    ),
    Agent(
        name="Jaguar Population",
        dependency_weight=0.35,
        damage_function=logistic_damage(threshold=0.15, steepness=14.0),
        monetary_rate=1_500_000.0,
        description="Apex predator habitat, keystone species for prey regulation",
    ),
    Agent(
        name="Watershed Network",
        dependency_weight=0.40,
        damage_function=logistic_damage(threshold=0.15, steepness=12.0),
        monetary_rate=2_000_000.0,
        description="Regional freshwater supply, flood regulation, soil retention",
    ),
]
```

The `dependency_weight` values across all agents **must sum to 1.0**. The cost formula is:

```
cost_per_agent = damage × dependency_weight × monetary_rate
```

So the effective maximum externality for an agent at full depletion is `weight × monetary_rate`.

### Step 4: Build and run

```python
from gaia.models import Ecosystem
from gaia.simulation import run_extraction
from gaia.report import format_report

ecosystem = Ecosystem(
    name="Amazon Rainforest Section A",
    resource=resource,
    agents=agents,
)

result = run_extraction(ecosystem, units_to_extract=10_000)
print(format_report(result))
```

### Packaging as a reusable case

Follow the pattern in `gaia/cases/forest.py`: create a `build_<case>_ecosystem()` function with documented parameters, a `run_<case>()` convenience wrapper, and a `main()` CLI entry point. Add the module to `gaia/cases/`.

---

## Damage Functions — Choosing the Right One

| Function | Shape | Best For |
|---|---|---|
| `logistic_damage` | S-curve — slow, then sharp knee, then plateau | Ecosystems with clear carrying capacity dynamics (recommended default) |
| `exponential_damage` | Continuously accelerating | Resources where even small extraction has growing consequences |
| `piecewise_damage` | Two linear segments with slope change at threshold | When you know the threshold precisely but not the exact curve shape |

All three satisfy these invariants:
1. `f(0.0) ≈ 0.0` — no depletion, no damage
2. `f(1.0) ≈ 1.0` — full depletion, full damage
3. Monotonically non-decreasing — more extraction never produces less damage
4. Non-linear at the threshold — local slope accelerates past the threshold
5. Convex just past the threshold — damage is accelerating, not yet saturating
6. More total damage occurs past the threshold than before it

---

## Current Status (v0.4)

**What works:**
- Damage function library: logistic, exponential, piecewise — all validated against 6 scientific invariants
- Recovery function library: `logistic_recovery` (entropy asymmetry encoded — slower S-curve than damage), `linear_recovery` (slope < 1.0 encodes irreversibility)
- Step-by-step extraction simulation with per-agent cost breakdown
- Step-by-step restoration simulation with per-agent service value recovery
- Ecosystem Health Index (0.0–1.0)
- Plain-text externality report and restoration investment report
- Prevention advantage ratio — quantifies how much cheaper preservation is vs. destroy-then-restore
- **v0.3: Trophic cascade amplification** — damage propagates through the interaction network; trophic levels amplify impact; keystone species collapse triggers cascading damage
- **v0.4: Succession-based maturation curves** — ecosystem services return through pioneer → intermediate → climax phases with configurable maturation delay
- **v0.4: Double carbon externality** — CO₂ released from extraction + future absorption capacity permanently lost; monetized at configurable carbon price
- **v0.4: Resilience zones** — three-zone system (green/yellow/red) around the safe threshold with interpolated model confidence and irreversibility warnings
- **v0.4: Confidence bands** — externality estimates widen as model confidence degrades, reflecting real epistemic uncertainty
- **v0.4: Maturation timeline** — year-by-year service recovery, carbon absorption, maturation gap (lost services during succession)
- Three ready-to-run cases, both extraction and restoration modes:
  - **Oak Valley Forest** — temperate forest, 4 agents, 8/25/60yr succession; prevention advantage **2.50×**
  - **Costa Brava Holm Oak Forest** — Mediterranean forest, 11 agents, 12/35/80yr succession; prevention advantage **6.08×**
  - **Costa Brava Posidonia Meadow** — marine seagrass, 11 agents, 20/50/120yr succession, inverted economics; prevention advantage **81.00×**
- 375 tests, all passing

**What's coming (v0.5+):**
- Physical substrate model and derived carrying capacity (v0.5)
- NPV / time-horizon analysis for multi-year investment decisions (v0.6)
- Endogenous pricing — prices derived from interaction network + scarcity (v0.7)

See `PROJECT_DEFINITION.md` for the full roadmap.

---

## Parameter Documentation Standard

All monetary rates and weights in the codebase are currently marked `[PLACEHOLDER]` — they are designed to be plausible but are not calibrated against published studies. Each case file documents its parameters in a table:

| Parameter | Value | Unit | Source | Confidence |
|---|---|---|---|---|
| `total_units` | configurable | trees | Placeholder | Low |
| `safe_threshold_ratio` | 0.3 | ratio | Placeholder | Low |
| `unit_value` | 100.0 | €/tree | Placeholder | Low |

As the project matures, parameters will be replaced with values sourced from peer-reviewed literature or official environmental valuation studies, with confidence levels updated accordingly.

---

## License

TBD
