# Gaia v0.1 — Specification

## Overview

v0.1 is the core loop: extract trees from a forest, compute non-linear externality costs per agent, produce a text report. The simplest possible thing that embodies the Gaia thesis and produces meaningful, testable output.

**Scientific foundations used:** Thermodynamics (F1), Entropy Asymmetry (F2), Carrying Capacity (F4), Independent Agents (F5).

---

## Data Models

All models are typed dataclasses with primitive fields. No inheritance, no dynamic attributes, no `**kwargs`. Every field has an explicit type annotation. All models are Cython-compatible.

### Resource

The shared natural asset being extracted.

```python
@dataclass
class Resource:
    name: str                    # e.g. "Oak Valley Forest"
    total_units: int             # e.g. 10000 (total trees)
    safe_threshold_ratio: float  # e.g. 0.3 (30% can be safely extracted)
    unit_value: float            # e.g. 100.0 (€ per unit extracted — private revenue)
```

**Constraints:**
- `total_units > 0`
- `0.0 < safe_threshold_ratio < 1.0`
- `unit_value >= 0.0`

**Derived properties:**
- `safe_threshold_units = int(total_units * safe_threshold_ratio)` — the absolute number of units that can be extracted before damage accelerates.

### Agent

An entity that depends on the resource and suffers when it is depleted.

```python
@dataclass
class Agent:
    name: str                    # e.g. "Animal Populations"
    dependency_weight: float     # e.g. 0.30 (this agent's share of total ecosystem damage)
    damage_function: DamageFunc  # callable: (depletion_ratio: float) -> damage_ratio: float
    monetary_rate: float         # e.g. 500000.0 (€ total cost at maximum damage for this agent)
    description: str             # e.g. "Habitat loss, population decline, species loss"
```

**Constraints:**
- `0.0 < dependency_weight <= 1.0`
- `monetary_rate >= 0.0`
- All `dependency_weight` values across agents in an ecosystem should sum to 1.0.

**How monetary cost is computed:**
```
agent_cost = damage_function(depletion_ratio) * dependency_weight * monetary_rate
```

The `damage_function` outputs a ratio from 0.0 to 1.0. Multiplied by `dependency_weight` and `monetary_rate`, this produces the agent's externality cost in euros at the current depletion level.

### Ecosystem

A resource bound to a list of agents.

```python
@dataclass
class Ecosystem:
    name: str                    # e.g. "Oak Valley Forest Ecosystem"
    resource: Resource
    agents: list                 # List[Agent] — typed as list for Cython compat
```

**Constraints:**
- `len(agents) > 0`
- Sum of all `agent.dependency_weight` must equal 1.0 (within floating-point tolerance of 1e-6).

### SimulationStep

The state of the simulation at one point in time (after extracting N units).

```python
@dataclass
class SimulationStep:
    step: int                    # which unit was extracted (1-indexed)
    units_extracted: int         # cumulative units extracted so far
    depletion_ratio: float       # units_extracted / total_units
    agent_damages: list          # List[float] — damage ratio per agent (0.0 to 1.0)
    agent_costs: list            # List[float] — € cost per agent at this step
    marginal_cost: float         # total externality cost of THIS unit (not cumulative)
    cumulative_cost: float       # total externality cost so far
    private_revenue: float       # cumulative revenue from extraction
    ecosystem_health: float      # 0.0 (collapsed) to 1.0 (pristine)
```

### SimulationResult

The complete output of a simulation run.

```python
@dataclass
class SimulationResult:
    ecosystem: Ecosystem
    steps: list                  # List[SimulationStep]
    total_units_extracted: int
    total_private_revenue: float
    total_externality_cost: float
    net_social_cost: float       # total_private_revenue - total_externality_cost
    final_ecosystem_health: float
```

---

## Damage Functions

Damage functions are the mathematical heart of Gaia. They map a depletion ratio (0.0 = pristine, 1.0 = fully depleted) to a damage ratio (0.0 = no damage, 1.0 = maximum damage).

### Type Signature

```python
DamageFunc = Callable[[float], float]
```

Input: `depletion_ratio` (float, 0.0 to 1.0)
Output: `damage_ratio` (float, 0.0 to 1.0)

### Scientific Invariants (must hold for ALL damage functions)

These invariants encode the scientific foundations. They are not negotiable.

1. **Boundary: no depletion → no damage.** `f(0.0) ≈ 0.0` (within tolerance of 1e-4).
2. **Boundary: full depletion → full damage.** `f(1.0) ≈ 1.0` (within tolerance of 1e-4).
3. **Monotonicity.** If `a < b`, then `f(a) <= f(b)`. More extraction always means more damage (or equal — never less).
4. **Non-linearity with threshold.** The rate of damage increase is higher after the safe threshold than before it. Formally: the average slope in `[threshold, 1.0]` must be greater than the average slope in `[0.0, threshold]`.
5. **Convexity past threshold.** The second derivative is positive in the region past the safe threshold — damage accelerates.

### Provided Functions

All are factory functions that take a `threshold` parameter and return a `DamageFunc`.

#### Logistic (primary, recommended)

The default and most ecologically grounded damage function. Produces an S-curve where damage is low before the threshold, accelerates sharply around it, and saturates toward 1.0.

```python
def logistic_damage(threshold: float, steepness: float = 12.0) -> DamageFunc:
    """
    Logistic damage function.
    
    Args:
        threshold: depletion ratio where damage accelerates (0.0 to 1.0)
        steepness: how sharp the transition is (higher = sharper knee)
    
    Returns:
        DamageFunc that maps depletion_ratio -> damage_ratio
    """
```

The underlying formula:

```
raw(x) = 1 / (1 + exp(-steepness * (x - threshold)))
```

Normalized so that `f(0.0) = 0.0` and `f(1.0) = 1.0`:

```
f(x) = (raw(x) - raw(0)) / (raw(1) - raw(0))
```

The `steepness` parameter controls how sharp the knee is. Higher values make the transition more abrupt. Default of 12.0 gives a clear but not extreme S-curve.

#### Exponential

Damage grows exponentially — slow at first, fast later. No explicit threshold parameter in the formula, but the threshold affects where the curve "feels" like it accelerates due to normalization.

```python
def exponential_damage(threshold: float, base: float = 2.0) -> DamageFunc:
    """
    Exponential damage function.
    
    The threshold influences the curve shape through parameterization
    to ensure damage acceleration aligns with the threshold region.
    """
```

#### Piecewise Linear

Two linear segments with different slopes — gentle before the threshold, steep after. The simplest possible function that satisfies the invariants. Useful for testing and for cases where the exact curve shape is unknown but the threshold is well-established.

```python
def piecewise_damage(threshold: float, pre_slope_ratio: float = 0.2) -> DamageFunc:
    """
    Piecewise linear damage function.
    
    Args:
        threshold: depletion ratio where slope changes
        pre_slope_ratio: fraction of total damage that occurs before the threshold.
                         e.g. 0.2 means 20% of damage happens in the first `threshold`
                         fraction of extraction, and 80% happens after.
    """
```

---

## Simulation Engine

The simulation is a simple loop that extracts one unit per step and records the consequences.

### Algorithm

```
Input: ecosystem (Ecosystem), units_to_extract (int)
Output: SimulationResult

validate inputs
initialize cumulative_cost = 0.0
initialize steps = []

for step in 1..units_to_extract:
    depletion_ratio = step / ecosystem.resource.total_units
    
    agent_damages = []
    agent_costs = []
    step_cost = 0.0
    
    for agent in ecosystem.agents:
        damage = agent.damage_function(depletion_ratio)
        cost = damage * agent.dependency_weight * agent.monetary_rate
        agent_damages.append(damage)
        agent_costs.append(cost)
        step_cost += cost
    
    marginal_cost = step_cost - cumulative_cost_at_previous_step
    cumulative_cost = step_cost  (note: cost is cumulative by construction — 
                                   damage_function(depletion) gives total damage 
                                   AT this depletion level, not incremental)
    
    Actually — IMPORTANT CLARIFICATION:
    The damage function returns TOTAL damage at a depletion level, not marginal.
    So agent_cost at step N is the TOTAL cost given N units extracted.
    Marginal cost = total_cost_at_step_N - total_cost_at_step_(N-1).
    
    ecosystem_health = 1.0 - weighted_average(agent_damages)
    
    record SimulationStep
    
return SimulationResult
```

### Key Design Decision: Total vs. Marginal

The damage function returns **total damage at a given depletion level**, not the marginal damage of one additional unit. This is correct because:

- It matches the scientific model: ecosystem health is a function of current state, not of the last action taken.
- Marginal cost is derived by differencing: `marginal_cost[n] = total_cost[n] - total_cost[n-1]`.
- This avoids accumulation errors from summing small increments.

### Ecosystem Health Index

```
ecosystem_health = 1.0 - sum(agent.dependency_weight * agent.damage_function(depletion_ratio) 
                              for agent in ecosystem.agents)
```

A weighted average of agent damages, subtracted from 1.0. Ranges from 1.0 (pristine) to 0.0 (fully collapsed).

### Input Validation

The simulation must validate before running:

- `units_to_extract >= 0`
- `units_to_extract <= ecosystem.resource.total_units`
- All agent dependency weights sum to 1.0 (within tolerance)
- All agent damage functions satisfy the invariants (boundary checks at 0.0 and 1.0)

Validation failures raise descriptive exceptions, not silent defaults.

---

## Report Generation

A plain-text report that summarizes the simulation result. No dependencies — just string formatting.

### Format

```
═══════════════════════════════════════════════════════════════
  GAIA — Externality Report: {ecosystem.name}
═══════════════════════════════════════════════════════════════

  Resource:          {resource.total_units:,} {resource.name}
  Safe Threshold:    {safe_threshold_units:,} units ({safe_threshold_ratio:.1%})
  Units Extracted:   {total_units_extracted:,}
  Depletion:         {final_depletion:.1%}
  Ecosystem Health:  {final_ecosystem_health:.1%}

  ── Private Gains ──────────────────────────────────────────
  Revenue:                                     {total_revenue:>14,.2f}€

  ── Externalized Costs ─────────────────────────────────────
  {for each agent:}
  {agent.name}:                                {agent_cost:>14,.2f}€
    → {agent.description}

  TOTAL EXTERNALITY:                           {total_externality:>14,.2f}€
  ───────────────────────────────────────────────────────────
  NET SOCIAL COST:                             {net_social_cost:>14,.2f}€
  ═══════════════════════════════════════════════════════════
```

The `NET SOCIAL COST` is `total_revenue - total_externality`. Positive means society gained; negative means society lost.

---

## Preconfigured Case: Forest

The `gaia/cases/forest.py` module provides a ready-to-run forest deforestation scenario with placeholder parameters.

### Default Parameters

```python
resource = Resource(
    name="Oak Valley Forest",
    total_units=10_000,
    safe_threshold_ratio=0.3,
    unit_value=100.0,             # €100 per tree (timber revenue)
)

agents = [
    Agent(
        name="Human Communities",
        dependency_weight=0.20,
        damage_function=logistic_damage(threshold=0.3, steepness=12.0),
        monetary_rate=400_000.0,  # €400k total at max damage
        description="Health costs, water treatment, lost recreation",
    ),
    Agent(
        name="Animal Populations",
        dependency_weight=0.30,
        damage_function=logistic_damage(threshold=0.3, steepness=12.0),
        monetary_rate=600_000.0,  # €600k total at max damage
        description="Habitat loss, population decline, species loss",
    ),
    Agent(
        name="Vegetation & Flora",
        dependency_weight=0.15,
        damage_function=logistic_damage(threshold=0.3, steepness=12.0),
        monetary_rate=300_000.0,  # €300k total at max damage
        description="Soil erosion, pollination network disruption",
    ),
    Agent(
        name="General Biosphere",
        dependency_weight=0.35,
        damage_function=logistic_damage(threshold=0.3, steepness=12.0),
        monetary_rate=700_000.0,  # €700k total at max damage
        description="Carbon release, watershed degradation, climate impact",
    ),
]
# Total max externality: €2,000,000
# Dependency weights sum: 0.20 + 0.30 + 0.15 + 0.35 = 1.00
```

### Parameter Sources

All v0.1 parameters are **placeholders**. They are designed to be in a plausible ballpark for a medium-sized temperate forest, but are not calibrated against specific studies.

| Parameter | Value | Source | Confidence |
|---|---|---|---|
| Total trees | 10,000 | Placeholder | Low — illustrative |
| Safe threshold | 30% | Placeholder — informed by general ecology literature on sustainable yield | Low |
| Timber value per tree | €100 | Placeholder — rough European market rate | Low |
| Agent monetary rates | €300k–€700k | Placeholder — scaled to produce total externality ~2× timber revenue at 50% depletion | Low |
| Damage function steepness | 12.0 | Placeholder — chosen for clear S-curve visualization | Low |
| Dependency weights | 0.15–0.35 | Placeholder — biosphere weighted highest | Low |

**All parameters are pending scientific review.** See GAIA_ROADMAP.md, Verification & Scientific Validation Strategy.

---

## Project Structure

```
gaia/
├── __init__.py
├── models.py              # Resource, Agent, Ecosystem, SimulationStep, SimulationResult
├── damage.py              # Damage function factories (logistic, exponential, piecewise)
├── simulation.py          # Simulation engine (run_extraction)
├── report.py              # Text report generation (format_report)
├── validation.py          # Input validation (validate_ecosystem, validate_damage_function)
└── cases/
    ├── __init__.py
    └── forest.py          # Preconfigured Oak Valley Forest case + CLI entry point

tests/
├── __init__.py
├── test_damage.py         # Damage function mathematical properties
├── test_models.py         # Dataclass construction and constraints
├── test_simulation.py     # Simulation engine behavior and invariants
├── test_validation.py     # Input validation catches bad inputs
└── test_forest.py         # End-to-end forest case scenarios
```

---

## Testing Strategy

Tests encode the scientific invariants and behavioral guarantees that must always hold. They are not "does it run" tests — they are "does it obey the laws of nature" tests. If a future change breaks these, something is fundamentally wrong.

All tests use `pytest`. No third-party test dependencies beyond pytest itself.

### test_damage.py — Damage Function Mathematical Properties

These tests apply to ALL damage functions (logistic, exponential, piecewise). They are parameterized across all function types and a range of threshold values.

#### Invariant tests (must hold for every damage function)

| Test | What it checks | Foundation |
|---|---|---|
| `test_zero_depletion_zero_damage` | `f(0.0) ≈ 0.0` (tolerance 1e-4) | Boundary condition |
| `test_full_depletion_full_damage` | `f(1.0) ≈ 1.0` (tolerance 1e-4) | Boundary condition |
| `test_monotonicity` | For 1000 evenly spaced points in [0, 1], `f(x[i]) <= f(x[i+1])` | More extraction → more damage |
| `test_output_range` | For all points, `0.0 <= f(x) <= 1.0` | Damage is a ratio |
| `test_nonlinearity_at_threshold` | Average slope after threshold > average slope before threshold | F4 — non-linear damage |
| `test_convexity_past_threshold` | Second finite difference is positive in the post-threshold region | F1 — accelerating damage |

#### Parameterization tests

| Test | What it checks |
|---|---|
| `test_steepness_affects_sharpness` | Higher steepness → sharper transition (logistic only) |
| `test_threshold_shifts_curve` | Changing threshold shifts the inflection point accordingly |
| `test_different_thresholds` | Run all invariant tests across thresholds [0.1, 0.2, 0.3, 0.5, 0.7] |

### test_models.py — Dataclass Construction and Constraints

| Test | What it checks |
|---|---|
| `test_resource_creation` | Resource can be created with valid parameters |
| `test_resource_safe_threshold_units` | Derived `safe_threshold_units` is correctly computed |
| `test_agent_creation` | Agent can be created with valid parameters |
| `test_ecosystem_creation` | Ecosystem can be created with resource + agents |
| `test_ecosystem_weights_sum` | Dependency weights across all agents sum to 1.0 |
| `test_simulation_step_fields` | SimulationStep stores all expected fields with correct types |

### test_validation.py — Input Validation

| Test | What it checks |
|---|---|
| `test_reject_zero_total_units` | `total_units=0` raises ValueError |
| `test_reject_negative_total_units` | `total_units=-1` raises ValueError |
| `test_reject_threshold_zero` | `safe_threshold_ratio=0.0` raises ValueError |
| `test_reject_threshold_one` | `safe_threshold_ratio=1.0` raises ValueError |
| `test_reject_threshold_above_one` | `safe_threshold_ratio=1.5` raises ValueError |
| `test_reject_negative_unit_value` | `unit_value=-10` raises ValueError |
| `test_reject_weights_not_summing_to_one` | Agents with weights summing to 0.8 raises ValueError |
| `test_reject_extract_more_than_total` | Extracting 15,000 from 10,000 raises ValueError |
| `test_reject_negative_extraction` | Extracting -100 raises ValueError |
| `test_reject_bad_damage_function` | A damage function that returns > 1.0 is rejected |

### test_simulation.py — Simulation Engine Behavior

These tests use a simple preconfigured ecosystem (not necessarily the forest case).

#### Core invariant tests

| Test | What it checks | Foundation |
|---|---|---|
| `test_zero_extraction_zero_cost` | Extracting 0 units → total externality = 0 | Baseline |
| `test_full_extraction_maximum_cost` | Extracting all units → externality equals sum of all agent `monetary_rate * weight` | Boundary |
| `test_cumulative_cost_monotonically_increases` | `steps[i].cumulative_cost <= steps[i+1].cumulative_cost` for all i | More extraction → more damage |
| `test_marginal_cost_increases_past_threshold` | Average marginal cost in post-threshold steps > average in pre-threshold steps | F4 — non-linearity |
| `test_ecosystem_health_monotonically_decreases` | `steps[i].ecosystem_health >= steps[i+1].ecosystem_health` for all i | Health degrades with extraction |
| `test_ecosystem_health_pristine_at_zero` | Health = 1.0 before any extraction | Boundary |
| `test_ecosystem_health_collapsed_at_full` | Health ≈ 0.0 at full extraction | Boundary |
| `test_private_revenue_is_linear` | Revenue at step N = N × unit_value (revenue doesn't depend on ecosystem state) | Revenue is private, not affected by externalities |
| `test_step_count_matches_extraction` | Number of steps == units_to_extract | Structural |

#### Behavioral tests

| Test | What it checks |
|---|---|
| `test_all_agents_contribute_to_cost` | Every agent's cost > 0 at full extraction |
| `test_agent_costs_proportional_to_weights` | At full extraction, agent cost ratios match dependency weight ratios |
| `test_net_social_cost_sign` | At heavy extraction (80%), net social cost is negative (externalities exceed revenue) |
| `test_net_social_cost_at_low_extraction` | At light extraction (10%), net social cost is positive (revenue exceeds externalities) |

### test_forest.py — End-to-End Forest Case

These tests run the preconfigured Oak Valley Forest case and check for ecological plausibility. They are sanity checks, not precise assertions.

| Test | What it checks |
|---|---|
| `test_forest_at_threshold` | Cutting exactly 3,000 trees (30%): externality < revenue. The forest economy is sustainable at the threshold. |
| `test_forest_past_threshold` | Cutting 5,000 trees (50%): externality > revenue. The social cost exceeds private gain. |
| `test_forest_heavy_extraction` | Cutting 8,000 trees (80%): externality >> revenue (at least 3× timber revenue). The damage is catastrophic relative to the gain. |
| `test_forest_marginal_cost_curve_shape` | Marginal costs at steps 1000, 3000, 5000, 7000 form an accelerating sequence. The curve has the right shape. |
| `test_forest_report_generates` | The report function produces a non-empty string containing key fields (ecosystem name, total externality, net social cost). |
| `test_forest_report_contains_all_agents` | The report mentions all four agent names. |

### Edge Case Tests (spread across test files)

| Test | What it checks |
|---|---|
| `test_single_tree_forest` | A forest with 1 tree, extract 1: the simulation runs and produces valid output |
| `test_large_forest` | A forest with 1,000,000 trees, extract 500,000: runs in reasonable time, no overflow |
| `test_single_agent` | An ecosystem with only one agent (weight 1.0): works correctly |
| `test_extract_one_unit` | Extracting exactly 1 unit: produces valid step with non-zero marginal cost |
| `test_threshold_near_zero` | `safe_threshold_ratio=0.01`: damage starts almost immediately, functions still work |
| `test_threshold_near_one` | `safe_threshold_ratio=0.99`: almost all extraction is "safe", functions still work |

---

## CLI Entry Point

The forest case is runnable from the command line:

```bash
python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000
```

Optional arguments:
- `--trees` (default: 10000) — total trees in the forest
- `--threshold` (default: 0.3) — safe extraction threshold ratio
- `--cut` (default: 5000) — number of trees to extract
- `--tree-value` (default: 100.0) — revenue per tree in €

Output: the externality report printed to stdout.

---

## Definition of Done

v0.1 is complete when:

1. All tests pass (`pytest tests/ -v` — green).
2. The forest CLI produces a correct report where externalities are modest below the threshold and accelerate sharply above it.
3. All code uses typed dataclasses with explicit annotations.
4. No third-party dependencies in core (only standard library + pytest for testing).
5. The code structure is ready for Cython compilation (no dynamic attributes, no complex inheritance, `float → float` function signatures in the hot path).
6. All parameters in the forest case are documented with source and confidence level.
