# Gaia — Externality Computation Framework

## Purpose

Gaia is a Python library for simulating and quantifying externalities in economic activities — the hidden costs that private actors impose on society, ecosystems, and the environment when extracting or exploiting shared resources, and the hidden *value* generated when those resources are preserved or restored.

The core thesis is simple: **profits are privatized, but externalities are socialized.** Gaia exists to make those externalities visible, measurable, and expressible in monetary terms — in both directions. It computes the **cost of destruction** and the **value of restoration**, giving decision-makers a complete picture of the true economics at play.

---

## Scientific Foundations

These are observable truths about how natural systems behave. They are drawn from thermodynamics, ecology, population biology, and systems science. Gaia does not invent them — it respects them. **If the code contradicts a scientific foundation, the code is wrong.**

### 1. The Laws of Thermodynamics Constrain All Economic Activity

The economy is not a closed loop — it is an **open system** embedded within the environment. It takes energy (solar, chemical, kinetic) and materials from nature, and returns waste and heat. This is not a metaphor; it is the thermodynamic classification of the economic system.

Two laws govern everything:

**First law — Conservation of energy and matter.** Energy and matter cannot be created or destroyed, only transformed. When we "produce" something economically, we are transforming energy and materials from one form to another. Nothing comes from nothing. Every extraction has a source; every waste product goes somewhere.

**Second law — Entropy never decreases in an isolated system.** The quality of available energy degrades with every transformation. No process is 100% efficient; useful energy is always partly lost as heat. All energy transformations are **irreversible** — you cannot un-burn a fuel, un-release CO₂, or un-degrade a watershed.

These two laws together mean that: (a) material economic production cannot expand indefinitely, because it depends on finite energy and materials; (b) every economic transformation generates waste and disorder that the environment must absorb; and (c) **destruction of ordered systems is thermodynamically easy, while restoration requires fighting entropy and is always more expensive.**

If thermodynamics didn't apply, Gaia would not need to exist.

### 2. Entropy Asymmetry — Destruction Is Cheaper Than Restoration

A living ecosystem — a forest, a coral reef, a wetland — is a **supremely ordered system**. A living plant takes energy from its environment to preserve order, which is to say, life. This order took decades or centuries of energy input to self-organize.

Destroying that order is fast and cheap — it merely accelerates the natural tendency toward entropy. Restoring it means reversing entropy locally, and that always costs energy, time, and money.

You can fell a 50-year-old oak in an afternoon. Growing one back takes decades of sustained energy input, water, nutrients, and favorable conditions. This is not a metaphor — it is the second law of thermodynamics applied to biology.

The asymmetry has three observable consequences:

- **Damage is immediate; recovery is gradual.** Ecosystem services drop sharply upon extraction and return slowly upon restoration.
- **Restoration has direct costs.** Rebuilding a complex system requires sustained investment — planting, maintaining, protecting, irrigating. Each of these is an energy transformation with efficiency losses.
- **Maturation delay.** A restored resource does not immediately provide ecosystem services at full capacity. A sapling is not a mature tree. During the entire maturation window, the ecosystem operates at reduced capacity and the externality damage persists.

The empirical consequence: **prevention is always cheaper than restoration.** This is not an opinion — it is a thermodynamic inevitability.

### 3. Primary Productivity Is the Base of All Ecosystem Value

Plants are autotrophs — they capture solar energy through photosynthesis (at 2–6% efficiency) and convert it into biomass. This **primary productivity** is the energetic foundation of the entire ecosystem. Every animal, every fungus, every decomposer ultimately depends on the energy that plants capture.

This matters because living organisms are organized in a **trophic pyramid**: producers (plants) at the base, then primary consumers (herbivores), then secondary consumers (carnivores), then tertiary consumers (apex predators). At each level, energy transfer is inefficient — only 5–20% of the energy from one level reaches the next (the product of consumption efficiency, assimilation efficiency, and production efficiency: E = EC × EA × EP = T/P).

The consequence for Gaia is profound: **damage to primary producers amplifies as it cascades up the trophic pyramid.** A 10% reduction in forest biomass does not cause a 10% reduction in the animal populations that depend on it — it causes a much larger reduction, because each trophic level already operates on a fraction of the energy from below. Destroying the base of the pyramid disproportionately collapses everything above it.

Gaia must model this amplification. Agents higher in the trophic chain must show greater sensitivity to resource depletion than agents at the base.

### 4. Carrying Capacity and Population Dynamics

Every ecosystem has a **carrying capacity** (K) — the maximum population of a given species that the environment can sustain indefinitely. This is not a theoretical construct; it is an observable limit determined by available energy, nutrients, space, and the web of interactions with other species.

Population growth follows one of two broad strategies:

- **R-strategy (exponential):** rapid reproduction, small individuals, short lives. Growth follows Nt = (1+r)^t · N₀. These populations tend to overshoot carrying capacity, then crash. They are the pioneers — first to colonize, first to collapse.
- **K-strategy (logistic):** slower reproduction, larger individuals, longer lives. Growth follows Nt = Nt₋₁ · (1 + r · (K − Nt₋₁)/K). These populations approach carrying capacity gradually and stabilize. Trees, elephants, humans.

The safe extraction threshold in Gaia is directly related to carrying capacity. When extraction pushes a population below K, the logistic dynamics tell us how recovery will behave — and how populations of different strategies (R vs K) will respond differently to the same disturbance. R-strategy species may rebound fast but overshoot; K-strategy species (like mature hardwood trees) recover slowly but stably.

### 5. Ecosystems Are Networks of Interdependent Agents

An ecosystem is a system composed of living organisms (biota) and their abiotic environment, plus all the interactions between them. It is not a monolith — it is a network of distinct populations, each with their own dependency on shared resources and their own response to disturbance.

When a forest is degraded, the damage does not affect a single abstract "environment." It propagates differently through each dependent agent: animals lose habitat, humans lose water quality, vegetation loses microclimate stability, the atmosphere loses a carbon sink. These are distinct, measurable, empirically observable impacts.

**Population interactions create complex dynamics.** Species compete for resources, prey on each other, and depend on each other in ways that produce oscillating, sometimes chaotic behavior. The classic predator-prey model shows populations that oscillate in coupled cycles — disturbing one disturbs both. Competing species may coexist in stable equilibrium, or a small perturbation may drive one to extinction. These interactions mean that removing one species can have unpredictable cascading effects through the network.

Gaia models each agent independently because that is how ecosystems actually work — but it must also model the interactions between agents, because that is where the cascading damage occurs.

### 6. Keystone Species and Functional Roles

Not all species contribute equally to ecosystem function. In every ecosystem, a subset of species performs **essential functions** — energy capture, decomposition, pollination, seed dispersal, nutrient cycling. These are **keystone species**. Bees are keystone pollinators; certain fungi are keystone decomposers.

Removing a keystone species causes damage disproportionate to its biomass or population size, because it disrupts a function that many other species depend on. Conversely, species that appear "redundant" may serve as **ecological equivalents** — backup performers of the same function — or as **genetic reserves** that enable adaptation to future changes.

It is extremely difficult to identify which species are keystone before they are removed. This uncertainty is itself a scientific fact that Gaia must respect: the model should assign **criticality weights** to agents, but acknowledge that these weights carry significant uncertainty, especially for less-studied ecosystems.

### 7. Resilience Is a System Property

An ecosystem has **resilience** when, in the face of disturbance, it tends to maintain its functional integrity. A resilient forest recovers its primary productivity after a storm; a non-resilient one collapses into a different state.

Critical properties of resilience:

- **It belongs to the system, not to individual components.** A forest's resilience cannot be deduced from studying individual trees.
- **It depends on the type and intensity of disturbance.** An ecosystem may resist fire but not pollution, or tolerate moderate logging but collapse under intensive clearing.
- **It is extremely difficult to predict in advance.** Current science cannot reliably determine whether an ecosystem will be resilient to a specific disturbance before it occurs. After the disturbance, it is trivial to observe.
- **Biodiversity contributes to resilience.** While the relationship is not simple or linear, the scientific consensus holds that species diversity promotes ecosystem resilience — in part because functional redundancy among species provides backup when keystone species are lost.

For Gaia, resilience defines the zone of uncertainty around the safe extraction threshold. Below the threshold, the ecosystem is likely resilient. Above it, we enter a zone where resilience may hold or may fail — and we cannot know in advance which. Gaia must flag this uncertainty rather than pretending precision.

### 8. Ecological Succession and the Climax State

Ecosystems are not static. They evolve through a process of **succession** — a sequence of changes in species composition over time that converges toward a **climax state**. Each stage creates the conditions that enable the next:

1. **Pioneer phase:** annual plants (r-strategy) colonize rapidly. Low biomass, high growth.
2. **Intermediate phase:** shrubs and perennial plants establish. Soil stabilizes, microclimate develops.
3. **Climax phase:** long-lived K-strategy species (hardwood trees) dominate. Gross primary productivity is high, but net primary productivity approaches zero — all energy produced is used for maintenance, not growth. Biomass stabilizes.

At climax, the ecosystem is in dynamic equilibrium: it no longer "grows" in the sense of accumulating new biomass, but sustains maximum complexity and maximum ecosystem services.

This has two critical implications for Gaia:

- **Restoration follows succession, not a linear ramp.** A replanted forest does not jump to climax. It must pass through pioneer → intermediate → climax phases over decades. Ecosystem services increase non-linearly along this path — near-zero at first, then accelerating, then plateauing. Our maturation curves must follow a succession model.
- **Destroying a climax ecosystem means resetting the succession clock.** The externality cost is not just the current damage — it is the decades of succession required to return to the climax state that provided full ecosystem services.

### 9. Nutrient Cycles and the Carbon Cycle

Nutrients are chemical elements that organisms absorb to maintain and expand their functions. They circulate through ecosystems in **biogeochemical cycles** that operate at planetary scale, involving both living organisms and abiotic processes.

The **carbon cycle** is the most directly relevant to Gaia:

- **Slow cycle (geological):** carbon circulates between the lithosphere, oceans, and atmosphere over millions of years through sedimentation, rock formation, and volcanic activity. Fossil fuels are carbon stored in the lithosphere by this slow cycle.
- **Fast cycle (biological):** carbon flows between the land surface, oceans, and atmosphere through photosynthesis, respiration, and chemical equilibria. In its natural state, flows in and out are roughly balanced.

Human activity has disrupted this balance by burning fossil fuels — transferring carbon from the slow geological cycle into the fast atmospheric cycle at an unprecedented rate. Deforestation compounds this by both releasing stored carbon AND removing the photosynthetic capacity that would reabsorb it.

For Gaia, this means cutting a tree has a **double carbon externality**: the CO₂ released from the tree itself, plus the CO₂ that tree would have continued to absorb over its remaining lifetime. The restoration model must account for this: a replanted tree doesn't just need to grow — it needs to grow enough to recapture the released carbon AND compensate for the absorption capacity that was lost during the maturation period.

### 10. Coevolution — Every Change Propagates

When one species evolves or changes, it changes the conditions for every species in its ecological niche. This is **coevolution** — a process where species continuously adapt to each other and to the conditions they collectively create.

The most dramatic example: early photosynthetic bacteria transformed Earth's atmosphere from CO₂-rich to oxygen-rich, which was toxic to most existing life — but enabled the emergence of all aerobic life that exists today. Those pioneering organisms created the conditions for everything that followed, and are now largely extinct.

For Gaia, the principle is this: **extraction does not just remove a resource — it changes the conditions for everything that depended on that resource, which changes the conditions for everything that depended on *them*, and so on.** The damage propagates through the network of ecological relationships. This is why a step-by-step simulation that propagates consequences through agents is not a convenience — it is a scientific necessity. Static calculations cannot capture coevolutionary cascades.

---

## Mathematical Framework

These are the modeling decisions we make to turn the scientific foundations into computable outputs. They are not laws of nature — they are tools we chose because they best serve the goal of making externalities visible and actionable. **If a mathematical choice proves inadequate, it can be replaced. The science above cannot.**

### 11. Dual-Lens Symmetry — Every Cost Is Also an Investment Opportunity

This is a mathematical property of the model, not a guarantee from nature. If removing one unit of resource past the safe extraction threshold imposes €X in externality costs, then our model computes that restoring that unit *recovers* €X in ecosystem services (subject to the entropy asymmetry from Foundation #2 — the recovery is slower and costlier than the destruction).

In reality, some ecosystem damage is irreversible — species go extinct, soil erodes past recovery, tipping points are crossed with no return (see Foundation #7 on resilience). The dual-lens symmetry is a useful approximation that holds within bounds, and Gaia should flag when those bounds are likely exceeded.

Within its valid range, this symmetry makes Gaia not only a tool for accountability but an **investment map**. It can answer:

- "What is the social return on investment of replanting 500 trees?" (factoring in restoration costs and maturation delay)
- "What is the net present value of preserving this forest intact over 30 years?"
- "At what carbon credit price does restoration become privately profitable, not just socially beneficial?"

Both lenses — cost and opportunity — emerge from the same underlying math. The model runs in both directions.

### 12. Monetary Convergence

Nature does not price things in euros. We do.

Each agent in the model tracks damage in its own native metric — biodiversity indices, carbon tonnes, health outcomes, water quality measures. But ultimately, **all damage converges to a single currency**. This is not because money is the only measure of value — it is because money is the only measure that enters the economic equations where extraction decisions are actually made. To change the decisions, the externality must speak the language of the decision-maker.

This is an economic modeling choice, and it carries known limitations: some forms of value resist monetization (cultural significance, intrinsic worth of a species, spiritual connection to land). Gaia acknowledges this by always preserving the per-agent native metrics alongside the monetary aggregation. The currency figure is the headline; the decomposition is the full story.

The aggregation into a single Ecosystem Health Index (0.0–1.0) and a total monetary externality provides both.

### 13. Simulation Over Calculation

Externalities are path-dependent. The cost of cutting the 3,001st tree depends on the state of the ecosystem *after* the first 3,000 were cut. A static formula cannot capture this — only a step-by-step simulation can.

This is a methodological choice about how to compute quantities that depend on sequence and accumulation. Gaia simulates extraction (and restoration) as a sequence of discrete events, propagating consequences through the agent network at each step. This captures cascading effects, threshold crossings, and the compounding nature of ecosystem degradation that a closed-form equation would miss.

The simulation approach also enables scenario comparison: "What if we stop cutting at tree 2,000 instead of 5,000?" — questions that require replaying the sequence with different parameters.

---

## The Problem

When an economic actor extracts value from a shared natural resource (e.g. cutting trees from a forest), the direct profit is easy to calculate. What is systematically ignored is the cascading damage to the ecosystem and the communities that depend on it.

Equally ignored is the inverse: the enormous economic value generated by intact ecosystems — value that appears nowhere on a balance sheet but that society depends on every day.

Gaia makes both sides of this equation computable.

---

## What Gaia Does

1. **Models ecosystems as networks of dependent agents.** A forest is not just trees — it is people, animals, vegetation, microorganisms, watersheds, and climate systems. Each agent type has its own dependency on the resource and its own damage function.

2. **Simulates extraction and restoration over time.** Gaia runs step-by-step simulations in both directions: progressive extraction (deforestation) and progressive restoration (reforestation), tracking consequences through the agent network at each step.

3. **Computes non-linear externality costs.** Each agent's damage follows a non-linear curve calibrated around a **safe extraction threshold**. Below the threshold, costs are modest. Above it, they accelerate sharply.

4. **Models restoration with entropy asymmetry.** Restoration is not the mirror of destruction. Gaia accounts for direct restoration costs, maturation delays, and the accumulated externality damage during the recovery window. It computes the true cost of "cut now, replant later" versus "don't cut."

5. **Aggregates into a single ecosystem health metric.** While each agent tracks its own health independently, Gaia rolls these up into a normalized Ecosystem Health Index (0.0 = collapsed, 1.0 = pristine) for quick assessment.

6. **Translates everything into currency.** Every form of damage and every form of recovered value is converted to monetary terms, producing both an externality bill and a restoration investment case.

---

## First Case: Forest Deforestation & Reforestation

The initial implementation models a forest ecosystem with the following agents:

| Agent Type | What They Depend On | Example Damage | Example Recovery |
|---|---|---|---|
| **Human Communities** | Air quality, water, recreation, livelihood | Health costs, lost income | Restored livelihoods, cleaner water |
| **Animal Populations** | Habitat, food, breeding grounds | Population decline, species loss | Habitat recovery, population rebound |
| **Vegetation & Flora** | Canopy, microclimate, soil stability | Soil erosion, secondary die-off | Soil stabilization, pollination return |
| **General Biosphere** | Carbon sequestration, water cycle, climate | Carbon release, watershed damage | Carbon capture, watershed restoration |

Each agent has:
- A **dependency weight** on the resource (how much they rely on it).
- A **damage function** that maps resource depletion to agent-specific harm (non-linear, with a knee at the safe threshold).
- A **recovery function** that maps restoration progress to recovered services (slower than damage, reflecting entropy asymmetry).
- A **maturation curve** that defines how long a restored unit takes to reach full ecosystem service capacity.
- A **monetary conversion factor** that translates both damage and recovery into currency.

### The Asymmetric Curves

```
Ecosystem Service Level
   1.0 │━━━━━━━━━╲
       │          ╲
       │           ╲                      ╱ · · · · · · ·
       │            ╲                 ╱ ·
       │             ╲            ╱ ·
       │              ╲       ╱ ·          ── Restoration (slow, costly)
       │               ╲  ╱ ·
       │                ╳·
       │             ╱· ╲
       │          ╱·    ╲
       │       ╱·        ╲
       │    ╱·             ╲               ── Destruction (fast, cheap)
       │ ╱·                 ╲
   0.0 │·                    ╲━━━━━━━━━
       └──────────────────────────────── Time
                    ▲
               Intervention
               Point
```

Destruction drops ecosystem services rapidly. Restoration climbs back slowly, with real costs at every step and a long maturation tail. The gap between the two curves represents the **irrecoverable cost of the entropy asymmetry** — the social damage that accumulates while waiting for recovery.

---

## Architecture

Gaia is designed as a **pure Python library** using typed dataclasses, fully compatible with **Cython compilation** for performance-critical simulation loops.

### Core Abstractions

```
Resource            — The shared natural asset being extracted (e.g. a forest of N trees).
Agent               — An entity that depends on the resource (e.g. a human community, animal population).
DamageFunction      — A callable that maps depletion ratio → damage ratio (non-linear, convex).
RecoveryFunction    — A callable that maps restoration ratio → recovered service ratio (slower than damage).
MaturationCurve     — A time function: years since restoration → service capacity (0.0 to 1.0).
MonetaryConverter   — Translates agent-specific damage/recovery into currency.
RestorationCost     — The direct cost of restoring one unit of resource (planting, maintenance, etc.).
Ecosystem           — A collection of agents bound to a resource.
Simulation          — Steps through extraction or restoration events, propagates consequences.
ExternalityReport   — Destruction mode: per-step and cumulative externality costs.
InvestmentReport    — Restoration mode: per-step social returns, ROI, net present value.
```

### Design Constraints (Cython Compatibility)

- All data containers are **typed dataclasses** with primitive or array fields.
- No dynamic attribute creation, no `**kwargs` in hot paths.
- Damage and recovery functions are simple callables with `float → float` signatures.
- Simulation loops use only basic arithmetic and array indexing.
- No third-party dependencies in the core computation module (NumPy is optional, not required).

### Project Structure

```
gaia/
├── core/
│   ├── resource.py          # Resource dataclass
│   ├── agent.py             # Agent dataclass and registry
│   ├── damage.py            # Damage function library (logistic, exponential, custom)
│   ├── recovery.py          # Recovery functions and maturation curves
│   ├── monetary.py          # Monetary conversion logic
│   ├── ecosystem.py         # Ecosystem container
│   └── simulation.py        # Simulation engine (extraction + restoration modes)
├── cases/
│   └── forest.py            # Forest case (preconfigured agents, parameters)
├── reports/
│   ├── externality_report.py  # Destruction report generation
│   └── investment_report.py   # Restoration investment report
├── cy/
│   └── simulation_cy.pyx   # Cython-optimized simulation loop (optional, drop-in)
├── setup.py                 # Build configuration (includes Cython extension)
└── README.md
```

---

## Output Examples

### Destruction Report

```
═══════════════════════════════════════════════════════════════
  GAIA — Externality Report: Oak Valley Forest
═══════════════════════════════════════════════════════════════

  Resource:          10,000 trees
  Safe Threshold:    3,000 trees (30.0%)
  Trees Cut:         5,000
  Depletion:         50.0%

  ── Private Gains ──────────────────────────────────────────
  Timber Revenue:                              €500,000.00

  ── Externalized Costs ─────────────────────────────────────
  Human Communities:                           €187,320.00
    → Health costs, water treatment, lost recreation
  Animal Populations:                          €312,750.00
    → Habitat loss, population decline (est. 3 species critical)
  Vegetation & Flora:                          €145,200.00
    → Soil erosion, pollination network disruption
  General Biosphere:                           €428,900.00
    → Carbon release (est. 12,400 tonnes CO₂), watershed damage

  TOTAL EXTERNALITY:                         €1,074,170.00
  ───────────────────────────────────────────────────────────
  NET SOCIAL COST:                            −€574,170.00
  ═══════════════════════════════════════════════════════════
```

### Restoration Investment Report

```
═══════════════════════════════════════════════════════════════
  GAIA — Restoration Investment Report: Oak Valley Forest
═══════════════════════════════════════════════════════════════

  Current State:     5,000 trees remaining (50.0%)
  Restoration Goal:  7,000 trees (safe threshold)
  Trees to Plant:    2,000

  ── Restoration Costs ──────────────────────────────────────
  Planting & Nursery:                           €94,000.00
  Maintenance (10 yr):                          €62,000.00
  Protection & Monitoring:                      €28,000.00
  TOTAL RESTORATION COST:                      €184,000.00

  ── Recovered Ecosystem Services (30-year horizon) ─────────
  Human Communities:                           €187,320.00
    → Restored water quality, air quality, recreation
  Animal Populations:                          €312,750.00
    → Habitat recovery, population stabilization
  Vegetation & Flora:                          €145,200.00
    → Soil restabilization, pollination network repair
  General Biosphere:                           €428,900.00
    → Carbon sequestration (est. 8,200 tonnes CO₂ over 30 yr)

  TOTAL RECOVERED VALUE (30 yr):             €1,074,170.00
  NET PRESENT VALUE (3% discount):             €612,400.00
  ───────────────────────────────────────────────────────────
  SOCIAL ROI:                                       3.3x
  PAYBACK PERIOD:                               ~8 years

  ── Prevention vs. Restoration ─────────────────────────────
  Cost of NOT having cut 2,000 trees:          €200,000.00
    (foregone timber revenue)
  Cost of cutting and restoring:               €384,000.00
    (timber revenue returned + restoration cost)
  Irrecoverable gap (maturation damage):       €461,770.00
    (externality damage during 30-year recovery)
  ───────────────────────────────────────────────────────────
  PREVENTION ADVANTAGE:                     4.6x cheaper
  ═══════════════════════════════════════════════════════════
```

---

## Philosophy

Gaia is a **measurement tool with a dual lens**. It quantifies the cost of destruction *and* the value of restoration. It produces numbers, not moral judgments.

But the numbers tell a clear story: intact ecosystems generate enormous economic value that is currently invisible. Destroying them creates private profit at social cost. Restoring them creates social value at private cost — but the investment case is often compelling when the true numbers are visible.

The goal is to make externalities impossible to ignore and restoration impossible to overlook — not by moralizing, but by counting.

**If we can understand which actions harm the environment, we can also understand which ones will yield economic returns for everyone.**

---

## Roadmap

- [x] Define core abstractions and data model
- [x] Define scientific foundations (thermodynamics, trophic cascades, carrying capacity, resilience, succession, nutrient cycles, coevolution)
- [x] Define mathematical framework (dual-lens, monetary convergence, simulation methodology)
- [ ] Implement non-linear damage functions (logistic, exponential, piecewise)
- [ ] Implement trophic cascade amplification (damage multipliers by trophic level)
- [ ] Implement carrying capacity (K) and R/K-strategy population dynamics
- [ ] Implement recovery functions with entropy asymmetry
- [ ] Implement succession-based maturation curves (pioneer → intermediate → climax)
- [ ] Implement keystone species criticality weights with uncertainty bounds
- [ ] Implement resilience zones and threshold uncertainty flagging
- [ ] Implement double carbon externality (release + lost absorption capacity)
- [ ] Build simulation engine with extraction and restoration modes
- [ ] Implement forest deforestation/reforestation case with calibrated parameters
- [ ] Add Cython-optimized simulation loop
- [ ] Externality report generation with per-agent breakdown
- [ ] Restoration investment report with NPV, ROI, payback period
- [ ] Prevention-vs-restoration comparison output
- [ ] Generalize framework for additional resource types (water, fisheries, soil, air)
- [ ] Pluggable monetary conversion models (region-specific, time-discounted)

---

## License

TBD

## Contributing

TBD
