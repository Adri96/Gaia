# Gaia v0.3 — Specification: Trophic Cascades & Agent Interactions

## Overview

v0.3 is the version where agents stop being independent. In v0.1 and v0.2, each agent computes damage (or recovery) solely from the depletion ratio — they don't affect each other. In reality, ecosystem damage cascades: killing trees kills fungi, which kills soil, which kills more trees. A pollinator crash collapses plant reproduction. An apex predator loss triggers herbivore explosion that destroys vegetation.

v0.3 introduces two mechanisms that make agents interact:

1. **Trophic levels with energy amplification** — damage to producers amplifies up the trophic pyramid
2. **Agent interaction edges** — directed dependencies where one agent's damage directly increases another's

Together these transform Gaia from a collection of independent damage curves into a network that exhibits cascading failures — which is how real ecosystems behave.

**Scientific foundations used:** Primary Productivity & Trophic Pyramids (F3), Keystone Species (F6), Coevolution (F10), plus all foundations from v0.1/v0.2.

---

## What Changes from v0.2

### Conceptual shift

In v0.1/v0.2, the simulation loop is:

```
for each step:
    depletion_ratio = step / total_units
    for each agent:
        agent_damage = agent.damage_function(depletion_ratio)  # independent
```

In v0.3, the loop becomes:

```
for each step:
    depletion_ratio = step / total_units
    for each agent:
        direct_damage = agent.damage_function(depletion_ratio)  # from resource loss
    
    propagated_damage = propagate(direct_damages, interaction_matrix, trophic_levels)
    
    for each agent:
        effective_damage = min(1.0, propagated_damage[agent])  # capped at total collapse
```

The key addition is the **propagation pass** — a single round where damage flows through agent-to-agent connections after the direct damage from resource loss is computed.

### What stays the same

- Resource, Ecosystem, SimulationStep, SimulationResult dataclasses (extended, not replaced)
- Damage functions (`float → float` — unchanged)
- Recovery functions (unchanged)
- Monetary conversion (unchanged)
- Report format (extended with cascade breakdown)
- CLI interface (unchanged)
- All v0.1/v0.2 tests must continue to pass

---

## Data Model Changes

### Agent (extended)

```python
@dataclass
class Agent:
    # --- existing fields (unchanged) ---
    name: str
    dependency_weight: float
    damage_function: DamageFunc
    monetary_rate: float
    description: str
    
    # --- new fields for v0.3 ---
    trophic_level: int              # 0 = producer, 1 = primary consumer, 2 = secondary, 3 = tertiary
                                    # -1 = abiotic service (watershed, carbon, etc.) — not in trophic chain
    is_keystone: bool               # if True, collapse triggers amplified cascade
    keystone_threshold: float       # health below this triggers keystone cascade (e.g. 0.3)
```

**Constraints:**
- `trophic_level` must be -1, 0, 1, 2, or 3
- `0.0 < keystone_threshold < 1.0`
- If `is_keystone` is False, `keystone_threshold` is ignored

**Defaults for backward compatibility:**
- `trophic_level = -1` (no trophic interactions — v0.1/v0.2 behavior)
- `is_keystone = False`
- `keystone_threshold = 0.3`

### InteractionEdge (new)

A directed dependency between two agents. "When agent A is damaged, agent B suffers additional damage."

```python
@dataclass
class InteractionEdge:
    source: str             # name of the agent whose damage propagates
    target: str             # name of the agent that receives the propagated damage
    strength: float         # 0.0 to 1.0 — how much of source's damage transfers to target
    interaction_type: str   # "dependency", "trophic", "keystone", "competition"
    description: str        # e.g. "Pollinator loss reduces vegetation reproduction"
```

**Constraints:**
- `0.0 < strength <= 1.0`
- `source` and `target` must be names of agents in the ecosystem
- `source != target` (no self-loops)
- `interaction_type` must be one of: `"dependency"`, `"trophic"`, `"keystone"`, `"competition"`

### Ecosystem (extended)

```python
@dataclass
class Ecosystem:
    # --- existing fields ---
    name: str
    resource: Resource
    agents: list            # List[Agent]
    
    # --- new field ---
    interactions: list      # List[InteractionEdge] — can be empty for v0.1/v0.2 compat
```

**Default for backward compatibility:**
- `interactions = []` — no interactions, v0.1/v0.2 behavior preserved

---

## Trophic Amplification

### The Science (Foundation F3)

Energy transfer between trophic levels is 5–20% efficient. When primary producers lose 10% of biomass, primary consumers don't lose 10% — they lose more, because they were already operating on a fraction of the energy from below.

### The Model

Each agent with a `trophic_level >= 0` receives an **amplification factor** on damage from resource loss:

```
trophic_amplification[level] = (1 / transfer_efficiency) ^ level
```

With a default `transfer_efficiency = 0.15` (15%, middle of the 5–20% range):

| Trophic Level | Example | Amplification Factor |
|---|---|---|
| 0 — Producer | Canopy trees, Posidonia, understory | 1.0× (baseline) |
| 1 — Primary consumer | Herbivores, pollinators, sea urchins | 1.5× |
| 2 — Secondary consumer | Small predators, insectivorous birds | 2.25× |
| 3 — Tertiary consumer | Apex predators, raptors, grouper | 3.375× |
| -1 — Abiotic service | Watershed, carbon, coastal protection | 1.0× (no amplification) |

**Important:** the amplification factor is applied to the *direct damage from resource loss*, not to the interaction edges. It represents the ecological reality that higher trophic levels are inherently more sensitive to changes at the base.

### Implementation

```python
def compute_trophic_amplification(
    direct_damage: float, 
    trophic_level: int, 
    transfer_efficiency: float = 0.15
) -> float:
    if trophic_level <= 0:  # producers and abiotic services
        return direct_damage
    amplification = (1.0 / transfer_efficiency) ** (trophic_level * 0.25)
    # Note: we use trophic_level * 0.25 as exponent, not trophic_level directly.
    # Full (1/0.15)^3 = ~296× at level 3, which is too extreme.
    # The 0.25 scaling gives a realistic 1.5×–3.4× range.
    # ? — needs validation from ecologist
    return min(1.0, direct_damage * amplification)
```

**The amplification exponent scaling factor (0.25) is a placeholder.** The raw trophic pyramid math gives amplification factors that are too extreme for a single-resource model (a 10% tree loss causing a 300% amplification at the apex predator level doesn't make sense when the apex predator has other food sources). The scaling factor tames this to a realistic range. It needs ecological validation.

---

## Agent Interaction Propagation

### The Model

After direct damage (with trophic amplification) is computed for all agents, a **single propagation pass** runs through all interaction edges:

```
for each edge in ecosystem.interactions:
    source_damage = effective_damage[edge.source]
    additional_damage = source_damage * edge.strength
    effective_damage[edge.target] += additional_damage
    effective_damage[edge.target] = min(1.0, effective_damage[edge.target])
```

### Why single-pass, not iterative convergence

Iterative propagation (run edges until nothing changes) would model true cascading feedback loops — but it introduces convergence problems, potential oscillation, and computational cost. For v0.3, a single pass is sufficient because:

1. The primary cascade direction is clear: producers → consumers → apex. Feedback loops (apex → producers via trophic control) are real but second-order effects that v0.4's population dynamics will handle better.
2. Single-pass is deterministic, fast, and testable.
3. The interaction strengths already encode the *effective* propagation — they don't need to compound over multiple rounds.

**v0.4 may revisit this** when dynamic population state makes iterative propagation necessary.

### Keystone Cascade

When an agent with `is_keystone = True` drops below `keystone_threshold` health, ALL its outgoing interaction edges have their strength doubled (capped at 1.0). This models the disproportionate damage caused by keystone species loss.

```python
def apply_keystone_effect(agent, agent_health, interactions):
    if agent.is_keystone and agent_health < agent.keystone_threshold:
        for edge in interactions:
            if edge.source == agent.name:
                edge.effective_strength = min(1.0, edge.strength * 2.0)
```

The doubling factor is a placeholder. The scientific foundation (F6) says keystone loss causes "damage disproportionate to biomass" — but the exact multiplier is ecosystem-specific and uncertain. This is explicitly flagged for ecological review.

---

## Simulation Engine Changes

### Extraction Mode (`run_extraction`)

The simulation loop changes from:

```
# v0.2 (current)
for step in 1..units_to_extract:
    depletion_ratio = step / total_units
    for agent in agents:
        damage = agent.damage_function(depletion_ratio)
        cost = damage * agent.dependency_weight * agent.monetary_rate
```

To:

```
# v0.3
for step in 1..units_to_extract:
    depletion_ratio = step / total_units
    
    # Phase 1: Direct damage from resource loss
    direct_damages = {}
    for agent in agents:
        raw_damage = agent.damage_function(depletion_ratio)
        direct_damages[agent.name] = compute_trophic_amplification(
            raw_damage, agent.trophic_level, transfer_efficiency
        )
    
    # Phase 2: Interaction propagation (single pass)
    effective_damages = dict(direct_damages)  # copy
    
    # Apply keystone effects first
    for agent in agents:
        agent_health = 1.0 - direct_damages[agent.name]
        apply_keystone_effect(agent, agent_health, interactions)
    
    for edge in interactions:
        source_damage = effective_damages[edge.source]
        additional = source_damage * edge.effective_strength
        effective_damages[edge.target] = min(1.0, 
            effective_damages[edge.target] + additional)
    
    # Phase 3: Compute costs from effective (propagated) damages
    for agent in agents:
        cost = effective_damages[agent.name] * agent.dependency_weight * agent.monetary_rate
```

### Restoration Mode (`run_restoration`)

Same two-phase structure, but using recovery functions. Interaction edges work in reverse during restoration — but at reduced strength (entropy asymmetry applies to cascades too). A restoring producer propagates recovery to consumers, but at `strength * 0.5` (recovery cascades are weaker than damage cascades).

```
recovery_cascade_factor = 0.5  # recovery propagates at half the strength of damage
```

### Backward Compatibility

When `ecosystem.interactions` is empty and all agents have `trophic_level = -1`:
- Phase 2 is a no-op (no edges to propagate)
- Trophic amplification returns 1.0× for all agents
- Result is identical to v0.2

**All existing tests must pass without modification.**

---

## SimulationStep Changes

```python
@dataclass
class SimulationStep:
    # --- existing fields ---
    step: int
    units_extracted: int
    depletion_ratio: float
    agent_damages: list          # effective (post-propagation) damage ratios
    agent_costs: list
    marginal_cost: float
    cumulative_cost: float
    private_revenue: float
    ecosystem_health: float
    
    # --- new fields ---
    agent_direct_damages: list   # pre-propagation damage ratios (from resource loss only)
    agent_cascade_damages: list  # additional damage from interactions (effective - direct)
    keystone_triggered: list     # list of agent names whose keystone threshold was crossed this step
```

The new fields enable the report to show: "Animal Populations suffered 0.45 direct damage from habitat loss + 0.12 additional damage from mycorrhizal network collapse = 0.57 total effective damage."

---

## Report Changes

The externality report gains a cascade breakdown section:

```
  ── Externalized Costs ─────────────────────────────────────
  Mycorrhizal Fungi:                            €156,000.00
    → Direct: €120,000 | Cascade: €36,000 (from canopy loss)
    ⚠ KEYSTONE THRESHOLD CROSSED at 45% depletion
  Animal Populations:                           €312,750.00
    → Direct: €234,500 | Cascade: €78,250 (from fungi collapse + vegetation loss)
    → Trophic amplification: 1.5× (primary consumer)
  Raptors & Apex Predators:                     €148,200.00
    → Direct: €42,000 | Cascade: €106,200 (from prey population collapse)
    → Trophic amplification: 3.4× (tertiary consumer)
```

When keystone thresholds are crossed, the report flags the step at which it happened and the additional cascade damage it caused.

---

## Preconfigured Cases: Interaction Edges

### Costa Brava Holm Oak Forest (11 agents)

Trophic level assignments:

| Agent | Trophic Level | Keystone? | Rationale |
|---|---|---|---|
| Canopy Trees | 0 (producer) | No | The resource itself |
| Understory & Matorral | 0 (producer) | No | Secondary producer |
| Mycorrhizal Fungi | 0 (producer) | **Yes** (threshold: 0.3) | Underground infrastructure — keystone decomposer/symbiont |
| Soil Microbiome | -1 (abiotic service) | No | Abiotic process agent |
| Pollinators & Insects | 1 (primary consumer) | **Yes** (threshold: 0.4) | Keystone functional group |
| Forest Birds | 1 (primary consumer) | No | Primary consumer (insects + seeds) |
| Forest Mammals | 1 (primary consumer) | No | Herbivores and omnivores |
| Raptors & Apex Predators | 3 (tertiary consumer) | No | Apex — population too small to be keystone |
| Watershed & Water Cycle | -1 (abiotic service) | No | Abiotic process |
| Carbon & Climate | -1 (abiotic service) | No | Abiotic process |
| Human Communities | -1 (abiotic service) | No | External beneficiary |

Key interaction edges:

```python
interactions = [
    # Mycorrhizal network is the backbone — its collapse cascades everywhere
    InteractionEdge("Mycorrhizal Fungi", "Canopy Trees", 0.35, "keystone",
        "Mycorrhizal collapse cuts nutrient/water supply to remaining trees"),
    InteractionEdge("Mycorrhizal Fungi", "Understory & Matorral", 0.25, "dependency",
        "Understory plants lose mycorrhizal nutrient access"),
    InteractionEdge("Mycorrhizal Fungi", "Soil Microbiome", 0.30, "dependency",
        "Mycorrhizal network supports bacterial communities and nutrient cycling"),
    
    # Pollinator collapse hits vegetation reproduction
    InteractionEdge("Pollinators & Insects", "Understory & Matorral", 0.30, "keystone",
        "Pollinator loss collapses plant reproduction"),
    InteractionEdge("Pollinators & Insects", "Forest Birds", 0.20, "trophic",
        "Insect decline reduces food for insectivorous birds"),
    
    # Canopy loss affects microclimate-dependent agents
    InteractionEdge("Canopy Trees", "Understory & Matorral", 0.25, "dependency",
        "Canopy loss removes shade → understory heat/drought stress"),
    InteractionEdge("Canopy Trees", "Soil Microbiome", 0.20, "dependency",
        "Canopy loss exposes soil to UV and drying → biocrust collapse"),
    InteractionEdge("Canopy Trees", "Watershed & Water Cycle", 0.30, "dependency",
        "Root loss reduces water infiltration and aquifer recharge"),
    
    # Prey-predator chain
    InteractionEdge("Forest Mammals", "Raptors & Apex Predators", 0.30, "trophic",
        "Prey decline starves apex predators"),
    InteractionEdge("Forest Birds", "Raptors & Apex Predators", 0.20, "trophic",
        "Bird decline reduces prey for raptors"),
    
    # Vegetation → herbivore dependency
    InteractionEdge("Understory & Matorral", "Forest Mammals", 0.25, "dependency",
        "Vegetation loss reduces food and cover for herbivores"),
    InteractionEdge("Understory & Matorral", "Pollinators & Insects", 0.20, "dependency",
        "Understory flowering loss reduces pollinator food sources"),
    
    # Soil → everything
    InteractionEdge("Soil Microbiome", "Canopy Trees", 0.15, "dependency",
        "Soil health decline reduces tree nutrient availability"),
    InteractionEdge("Soil Microbiome", "Watershed & Water Cycle", 0.20, "dependency",
        "Soil degradation reduces water retention capacity"),
    
    # Carbon depends on living biomass
    InteractionEdge("Canopy Trees", "Carbon & Climate", 0.35, "dependency",
        "Tree loss directly reduces carbon sequestration capacity"),
    
    # Human communities depend on multiple services
    InteractionEdge("Watershed & Water Cycle", "Human Communities", 0.25, "dependency",
        "Water quality decline affects human health and tourism"),
    InteractionEdge("Carbon & Climate", "Human Communities", 0.10, "dependency",
        "Climate regulation loss increases fire risk and heat stress"),
]
```

### Costa Brava Posidonia Meadow (11 agents)

Trophic level assignments:

| Agent | Trophic Level | Keystone? | Rationale |
|---|---|---|---|
| Posidonia Meadow | 0 (producer) | **Yes** (threshold: 0.3) | THE foundation species — everything depends on it |
| Coralligenous & Red Coral | 0 (producer) | No | Biogenic habitat builder, but not trophically a producer |
| Epiphytes & Algae | 0 (producer) | No | Primary producer |
| Marine Invertebrates | 1 (primary consumer) | No | Grazers and filter feeders |
| Fish Populations | 2 (secondary consumer) | No | Mixed trophic — some herbivorous, most predatory |
| Marine Megafauna | 3 (tertiary consumer) | No | Apex — dolphins, turtles |
| Seabirds | 2 (secondary consumer) | No | Fish-dependent predators |
| Coastal Protection | -1 (abiotic service) | No | Physical process |
| Water Quality | -1 (abiotic service) | No | Filtration process |
| Blue Carbon | -1 (abiotic service) | No | Chemical process |
| Human Communities | -1 (abiotic service) | No | External beneficiary |

Key interaction edges:

```python
interactions = [
    # Posidonia is the marine keystone — its collapse is catastrophic
    InteractionEdge("Posidonia Meadow", "Epiphytes & Algae", 0.40, "keystone",
        "Posidonia leaf loss removes substrate for 400+ epiphyte species"),
    InteractionEdge("Posidonia Meadow", "Fish Populations", 0.35, "keystone",
        "Meadow loss destroys nursery habitat — recruitment failure"),
    InteractionEdge("Posidonia Meadow", "Marine Invertebrates", 0.30, "keystone",
        "Meadow loss removes habitat for sessile invertebrates"),
    InteractionEdge("Posidonia Meadow", "Coastal Protection", 0.45, "dependency",
        "Meadow loss eliminates wave attenuation and beach protection"),
    InteractionEdge("Posidonia Meadow", "Water Quality", 0.40, "dependency",
        "Meadow loss eliminates water filtration — turbidity feedback loop"),
    InteractionEdge("Posidonia Meadow", "Blue Carbon", 0.40, "dependency",
        "Meadow loss releases stored carbon AND removes sequestration capacity"),
    InteractionEdge("Posidonia Meadow", "Coralligenous & Red Coral", 0.25, "dependency",
        "Turbidity from meadow loss smothers coralligenous formations"),
    
    # Fish → predator chain
    InteractionEdge("Fish Populations", "Marine Megafauna", 0.35, "trophic",
        "Fish collapse starves dolphins and deprives turtles of foraging"),
    InteractionEdge("Fish Populations", "Seabirds", 0.30, "trophic",
        "Fish collapse causes seabird breeding failure"),
    
    # Invertebrate cascades
    InteractionEdge("Marine Invertebrates", "Fish Populations", 0.20, "trophic",
        "Invertebrate decline reduces food for bottom-feeding fish"),
    InteractionEdge("Marine Invertebrates", "Water Quality", 0.15, "dependency",
        "Sponge decline reduces water filtration capacity"),
    
    # Coralligenous → biodiversity
    InteractionEdge("Coralligenous & Red Coral", "Fish Populations", 0.20, "dependency",
        "Reef habitat loss reduces shelter and breeding sites for reef fish"),
    InteractionEdge("Coralligenous & Red Coral", "Marine Invertebrates", 0.20, "dependency",
        "Reef loss removes substrate for sessile invertebrates"),
    
    # Human community dependencies
    InteractionEdge("Fish Populations", "Human Communities", 0.25, "dependency",
        "Fisheries collapse destroys artisanal fishing livelihoods"),
    InteractionEdge("Coastal Protection", "Human Communities", 0.30, "dependency",
        "Beach erosion devastates tourism economy"),
    InteractionEdge("Water Quality", "Human Communities", 0.20, "dependency",
        "Poor water quality closes beaches and harms tourism"),
]
```

### Oak Valley Forest (4 agents — minimal upgrade)

The Oak Valley case gets minimal trophic assignments to remain a simple test case:

| Agent | Trophic Level | Keystone? |
|---|---|---|
| Human Communities | -1 | No |
| Animal Populations | 1 | No |
| Vegetation & Flora | 0 | No |
| General Biosphere | -1 | No |

Two interaction edges:

```python
interactions = [
    InteractionEdge("Vegetation & Flora", "Animal Populations", 0.20, "dependency",
        "Vegetation loss reduces food and habitat for animals"),
    InteractionEdge("Animal Populations", "Human Communities", 0.10, "dependency",
        "Wildlife decline reduces ecosystem health indicators"),
]
```

This keeps Oak Valley as a simple case for testing while demonstrating that interactions work.

---

## Project Structure Changes

```
gaia/
├── __init__.py
├── models.py              # Extended: Agent + trophic_level, is_keystone, keystone_threshold
│                          # New: InteractionEdge
│                          # Extended: Ecosystem + interactions
│                          # Extended: SimulationStep + cascade fields
├── damage.py              # Unchanged
├── recovery.py            # Unchanged
├── propagation.py         # NEW: trophic amplification, interaction propagation, keystone effects
├── simulation.py          # Extended: two-phase extraction/restoration with propagation
├── validation.py          # Extended: validate interactions, trophic levels, edge references
├── report.py              # Extended: cascade breakdown in report
└── cases/
    ├── __init__.py
    ├── forest.py          # Extended: minimal interactions
    ├── costa_brava.py     # Extended: full trophic assignments + 17 interaction edges
    └── posidonia.py       # Extended: full trophic assignments + 16 interaction edges

tests/
├── __init__.py
├── test_damage.py         # Unchanged (must still pass)
├── test_models.py         # Extended: new fields, InteractionEdge construction
├── test_validation.py     # Extended: interaction validation tests
├── test_simulation.py     # Extended: propagation behavior tests
├── test_propagation.py    # NEW: trophic amplification, interaction propagation, keystone effects
├── test_recovery.py       # Unchanged (must still pass)
├── test_restoration.py    # Extended: restoration with interactions
├── test_forest.py         # Extended: interactions in Oak Valley
├── test_costa_brava.py    # Extended: cascade behavior in Mediterranean forest
└── test_posidonia.py      # Extended: cascade behavior in marine ecosystem
```

---

## Testing Strategy

### test_propagation.py — Propagation Engine (NEW)

#### Trophic amplification tests

| Test | What it checks | Foundation |
|---|---|---|
| `test_producer_no_amplification` | Trophic level 0 → amplification = 1.0× | F3 |
| `test_primary_consumer_amplified` | Trophic level 1 → amplification > 1.0× | F3 |
| `test_amplification_increases_with_level` | Level 1 < level 2 < level 3 amplification | F3 — energy loss per level |
| `test_abiotic_no_amplification` | Trophic level -1 → amplification = 1.0× | Abiotic agents aren't in the pyramid |
| `test_amplification_capped_at_one` | Even with high amplification, damage ≤ 1.0 | Physical constraint |
| `test_zero_damage_no_amplification` | 0.0 damage × any amplification = 0.0 | Mathematical |

#### Interaction propagation tests

| Test | What it checks |
|---|---|
| `test_no_interactions_no_propagation` | Empty interactions list → effective = direct |
| `test_single_edge_propagation` | Source damage × strength adds to target |
| `test_propagation_capped_at_one` | Multiple edges pushing target past 1.0 → capped |
| `test_multiple_incoming_edges` | Target with two sources accumulates both |
| `test_edge_strength_zero_no_effect` | Strength 0.0 edge doesn't propagate (validation should reject, but test boundary) |
| `test_cascade_chain_single_pass` | A→B→C: A's damage reaches B but NOT C in single pass |
| `test_propagation_order_independence` | Result is the same regardless of edge ordering |

#### Keystone tests

| Test | What it checks | Foundation |
|---|---|---|
| `test_keystone_not_triggered_above_threshold` | Agent health > threshold → normal strength | F6 |
| `test_keystone_triggered_below_threshold` | Agent health < threshold → doubled strength | F6 |
| `test_keystone_trigger_step` | Report correctly identifies the step where keystone crossed | F6 |
| `test_non_keystone_no_doubling` | Non-keystone agent below threshold → no effect | Structural |
| `test_keystone_doubled_capped_at_one` | Doubled strength ≤ 1.0 | Physical constraint |

### test_simulation.py — Extended Simulation Tests

#### Core invariant tests (extended)

| Test | What it checks |
|---|---|
| `test_effective_damage_gte_direct_damage` | For all agents with incoming edges, effective ≥ direct |
| `test_cascade_increases_total_externality` | Total cost with interactions > total cost without (same ecosystem, interactions toggled) |
| `test_backward_compat_no_interactions` | Ecosystem with empty interactions produces identical results to v0.2 |
| `test_trophic_amplification_increases_apex_cost` | Apex predator cost is disproportionately higher than its direct damage would predict |

#### Ecological plausibility tests

| Test | What it checks |
|---|---|
| `test_forest_mycorrhizal_keystone_cascade` | When mycorrhizal fungi cross keystone threshold, canopy trees and understory show increased damage in subsequent steps |
| `test_posidonia_meadow_keystone_cascade` | When Posidonia crosses keystone threshold, ALL marine agents show increased damage |
| `test_apex_predator_most_sensitive` | At moderate extraction, raptors/megafauna show highest damage ratio relative to their direct damage |
| `test_producer_damage_cascades_up_not_down` | Damaging a consumer does NOT increase producer damage (no reverse trophic cascade in v0.3) |

### test_costa_brava.py / test_posidonia.py — Extended Case Tests

| Test | What it checks |
|---|---|
| `test_cascade_total_exceeds_independent` | Same extraction level produces higher total externality with interactions than v0.2 baseline |
| `test_keystone_threshold_crossing_visible_in_report` | Report string contains keystone warning |
| `test_restoration_cascade_recovery` | Restoration with interactions: restoring keystone agents first yields faster ecosystem recovery |
| `test_marine_cascade_amplification` | In Posidonia case, total externality with cascades is at least 30% higher than without at 50% depletion |

### Edge Case Tests

| Test | What it checks |
|---|---|
| `test_all_agents_keystone` | Ecosystem where every agent is keystone — doesn't crash, produces valid output |
| `test_circular_dependency` | A→B and B→A edges: single pass handles this without infinite loop |
| `test_disconnected_agent` | Agent with no incoming or outgoing edges: behaves like v0.2 |
| `test_very_high_total_edge_strength` | Multiple edges pushing total strength well past 1.0: all damages capped properly |

---

## Definition of Done

v0.3 is complete when:

1. **All v0.1 and v0.2 tests still pass.** No regressions.
2. **All new propagation tests pass** — trophic amplification, interaction propagation, keystone effects.
3. **All three cases work with interactions** — Oak Valley (minimal), Costa Brava forest (full), Posidonia (full).
4. **The report shows cascade breakdown** — direct vs. propagated damage per agent, keystone threshold warnings.
5. **Backward compatibility is preserved** — ecosystems with no interactions produce identical output to v0.2.
6. **Running the Costa Brava forest at 50% extraction** shows measurably higher total externality than v0.2 (cascades add real cost).
7. **Running the Posidonia case at 50% depletion** triggers the Posidonia keystone cascade and shows a dramatic increase in total externality compared to v0.2.
8. **`pytest tests/ -v` — all green.**

---

## Parameter Documentation

All new parameters (trophic levels, interaction strengths, keystone thresholds, amplification scaling) are **placeholders** pending ecological review. Every parameter carries:

- **Value** — the number used
- **Source** — "placeholder" for all v0.3 parameters
- **Confidence** — "low" for all v0.3 parameters
- **Note** — what the ecologist reviewer should specifically evaluate

The interaction edges are the most uncertain part of v0.3. Their structure (which agents affect which) is grounded in ecology, but their strength values (0.10–0.45) are approximations. The ecologist reviewer should focus on: (a) are any edges missing? (b) are any edges wrong (pointing the wrong direction)? (c) are the relative strengths in the right ballpark?
