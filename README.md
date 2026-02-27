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
│   ├── models.py              # Data model: Resource, Agent, Ecosystem, SimulationResult
│   ├── damage.py              # Damage function library (logistic, exponential, piecewise)
│   ├── validation.py          # Input validation with scientific constraints
│   ├── simulation.py          # Simulation engine
│   ├── report.py              # Plain-text report formatter
│   └── cases/
│       ├── __init__.py
│       ├── forest.py          # Oak Valley Forest — temperate deforestation (CLI + API)
│       ├── costa_brava.py     # Costa Brava Holm Oak Forest — Mediterranean deforestation (CLI + API)
│       └── posidonia.py       # Costa Brava Posidonia Meadow — marine seagrass destruction (CLI + API)
├── tests/
│   ├── __init__.py
│   ├── test_damage.py         # Mathematical property tests for all damage functions
│   ├── test_models.py         # Data model unit tests
│   ├── test_validation.py     # Validation logic tests
│   ├── test_simulation.py     # Simulation engine tests
│   └── test_forest.py         # End-to-end forest case tests
├── PROJECT_DEFINITION.md      # Scientific foundations and architecture vision
├── ROADMAP.md                 # Version roadmap and verification strategy
└── V01_SPEC.md                # Detailed v0.1 specification
```

### Key modules

| Module | Responsibility |
|---|---|
| `gaia/models.py` | All data containers: `Resource`, `Agent`, `Ecosystem`, `SimulationStep`, `SimulationResult` |
| `gaia/damage.py` | Damage function factories — each returns a `float → float` callable |
| `gaia/simulation.py` | `run_extraction(ecosystem, units)` — the simulation loop |
| `gaia/report.py` | `format_report(result)` — human-readable output |
| `gaia/cases/forest.py` | Oak Valley Forest — temperate forest, 4 agents |
| `gaia/cases/costa_brava.py` | Costa Brava Holm Oak Forest — Mediterranean forest, 11 agents |
| `gaia/cases/posidonia.py` | Costa Brava Posidonia Meadow — marine seagrass, 11 agents |

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

Sample output:

```
═══════════════════════════════════════════════════════════════
  GAIA — Externality Report: Oak Valley Forest
═══════════════════════════════════════════════════════════════
  Resource:              10,000 units  (Oak Valley Forest)
  Safe Threshold:         3,000 units  (30.0%)
  Units Extracted:        5,000
  Depletion:              50.0%
  Ecosystem Health:       24.4%
  ── Private Gains ─────────────────────────────────────────────
  Revenue:                                     500,000.00€
  ── Externalized Costs ────────────────────────────────────────
  Human Communities:                           113,460.80€
  Animal Populations:                          264,817.51€
  Vegetation & Flora:                          113,460.80€
  General Biosphere:                           415,909.48€
  TOTAL EXTERNALITY:                           907,648.60€
  NET SOCIAL COST:                            -407,648.60€
═══════════════════════════════════════════════════════════════
```

Cutting 5,000 trees yields €500,000 in private revenue — but imposes over €907,000 in social costs. The net social cost is **-€407,648**: a net loss for society.

### Python API

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

### Convenience wrapper

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

The test suite has 196 tests covering:

- **Mathematical invariants** — all damage functions are tested for boundary conditions (`f(0)≈0`, `f(1)≈1`), monotonicity, output range, non-linearity at the threshold, and convexity in the post-threshold zone. These run across 3 function types × 5 threshold values.
- **Ecological plausibility** — the forest case verifies the economic story: externality < revenue at safe extraction, externality > revenue past the threshold.
- **Simulation correctness** — marginal cost accumulation, health index calculation, step counting.
- **Validation** — invalid inputs are rejected with clear error messages.

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

## Current Status (v0.1)

**What works:**
- Damage function library with three function types, all scientifically validated
- Step-by-step extraction simulation with per-agent cost breakdown
- Ecosystem Health Index (0.0–1.0)
- Plain-text externality report
- Three ready-to-run cases:
  - **Oak Valley Forest** — temperate forest, 4 agents, generic baseline
  - **Costa Brava Holm Oak Forest** — Mediterranean forest, 11 agents, scientifically grounded
  - **Costa Brava Posidonia Meadow** — marine seagrass, 11 agents, inverted economics (annual recurring losses vs one-time gain)
- 196 tests, all passing

**What's coming (v0.2+):**
- Restoration simulation (inverse of extraction)
- Entropy asymmetry modeling (restoration is slower and costlier than destruction)
- Succession-based maturation curves (pioneer → intermediate → climax)
- Double carbon externality (release + lost absorption capacity)
- Trophic cascade amplification (damage multipliers by trophic level)
- Resilience zones and threshold uncertainty flagging
- Restoration investment report with NPV, ROI, and payback period

See `ROADMAP.md` for the full plan.

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
