# Gaia — Externality Computation Framework

## Purpose

Gaia is a Python library for simulating and quantifying externalities in economic activities — the hidden costs that private actors impose on society, ecosystems, and the environment when extracting or exploiting shared resources, and the hidden _value_ generated when those resources are preserved or restored.

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

For Gaia, the principle is this: **extraction does not just remove a resource — it changes the conditions for everything that depended on that resource, which changes the conditions for everything that depended on _them_, and so on.** The damage propagates through the network of ecological relationships. This is why a step-by-step simulation that propagates consequences through agents is not a convenience — it is a scientific necessity. Static calculations cannot capture coevolutionary cascades.

---

## Verification & Scientific Validation Strategy

Gaia's credibility depends entirely on the quality of its inputs. A perfectly engineered simulation with arbitrary parameters is just a fancy opinion. Every parameter must be traceable to a source, and the scientific model itself must withstand scrutiny from domain experts.

### The Core Principle

**Every parameter must be traceable to a source.** Where does the safe threshold come from? What study? What dataset? What's the confidence interval? If a number cannot be justified, it must be explicitly marked as a placeholder and flagged in the output.

### Two-Track Validation

Gaia requires validation on two separate tracks that must not be confused:

**Track 1 — Scientific validation.** Are the foundations correct? Are we oversimplifying anything dangerously? Is there a principle we're missing? Are the damage curve shapes ecologically defensible? This is reviewed by ecologists and environmental scientists who can judge whether the _model structure_ reflects how ecosystems actually behave.

**Track 2 — Data calibration.** Are the specific numbers right? Is 30% a defensible safe extraction threshold for a temperate deciduous forest? What's the monetary value of carbon sequestration per hectare per year in this region? What data sources back these numbers? This is reviewed by domain experts with access to field data, published studies, and regional ecological assessments.

---

## Critical Modelling Assumption: Damage Function Calibration Regime

The interaction propagation engine uses a **single-pass** algorithm: damage from a source agent is added to its direct neighbours, but does not compound further through the chain. Given edges A→B and B→C, A's contribution to B's damage does not propagate onward to C.

This design is only ecologically valid under a specific calibration assumption that **the builder of every ecosystem case must resolve explicitly**:

### Option A — Empirically-calibrated damage functions (recommended)

Damage functions are fitted to real-world field observations: e.g., the observed decline in predator populations as a function of measured deforestation rates.

**What empirical data already encodes:** a field-measured relationship between resource depletion and agent damage includes all indirect effects along the trophic chain. The observer does not decompose "direct habitat loss" from "loss mediated via prey collapse" — the measurement is the total outcome across all pathways.

In this case, single-pass propagation is **correct by construction**. Adding cascade contributions from interaction edges on top of empirically-calibrated functions would double-count the indirect effects already embedded in the data. Under this regime, interaction edges serve a narrower purpose: they capture **structural network effects** that aggregate damage functions cannot represent — chiefly the **keystone species collapse**, a non-linear regime shift triggered when a specific agent crosses a health threshold regardless of the global depletion ratio.

### Option B — First-principles or lab-calibrated damage functions

Damage functions are derived theoretically or from controlled experiments that isolate only the direct dependency on the primary resource, excluding indirect pathways.

In this case, single-pass propagation **systematically underestimates cascade damage** in chains longer than one hop. The computed externality is a **structural lower bound** of the true damage. This is not corrected by running more simulation steps: each step recomputes all damage functions fresh from the current depletion ratio — there is no accumulation of cascade state across steps.

### The risk of mixing calibrations

The most dangerous scenario is an ecosystem where some damage functions are empirically calibrated and others are theoretical. Empirically-calibrated agents already carry their indirect damage; theoretical agents do not — yet both receive identical cascade treatment. The combined output has no coherent interpretation.

**Recommendation:** Decide which calibration regime applies to the entire ecosystem before building it, document the choice in the case file, and apply it consistently across all agents.

### Relationship to endogenous pricing

Note that the pricing engine (`gaia/pricing.py`) uses a full Leontief-Hannon matrix inverse — `V = (I − S·W)⁻¹ · A` — which implicitly captures all infinite-hop chains. This is intentional and not an inconsistency: market prices compound through supply chains by nature, regardless of how damage functions are calibrated. The asymmetry between single-pass damage propagation and full-matrix price propagation is a deliberate modelling choice.

---

## Mathematical Framework

These are the modeling decisions we make to turn the scientific foundations into computable outputs. They are not laws of nature — they are tools we chose because they best serve the goal of making externalities visible and actionable. **If a mathematical choice proves inadequate, it can be replaced. The science above cannot.**

### 11. Dual-Lens Symmetry — Every Cost Is Also an Investment Opportunity

This is a mathematical property of the model, not a guarantee from nature. If removing one unit of resource past the safe extraction threshold imposes €X in externality costs, then our model computes that restoring that unit _recovers_ €X in ecosystem services (subject to the entropy asymmetry from Foundation #2 — the recovery is slower and costlier than the destruction).

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

Externalities are path-dependent. The cost of cutting the 3,001st tree depends on the state of the ecosystem _after_ the first 3,000 were cut. A static formula cannot capture this — only a step-by-step simulation can.

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

| Agent Type             | What They Depend On                        | Example Damage                   | Example Recovery                       |
| ---------------------- | ------------------------------------------ | -------------------------------- | -------------------------------------- |
| **Human Communities**  | Air quality, water, recreation, livelihood | Health costs, lost income        | Restored livelihoods, cleaner water    |
| **Animal Populations** | Habitat, food, breeding grounds            | Population decline, species loss | Habitat recovery, population rebound   |
| **Vegetation & Flora** | Canopy, microclimate, soil stability       | Soil erosion, secondary die-off  | Soil stabilization, pollination return |
| **General Biosphere**  | Carbon sequestration, water cycle, climate | Carbon release, watershed damage | Carbon capture, watershed restoration  |

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

Gaia is a **measurement tool with a dual lens**. It quantifies the cost of destruction _and_ the value of restoration. It produces numbers, not moral judgments.

But the numbers tell a clear story: intact ecosystems generate enormous economic value that is currently invisible. Destroying them creates private profit at social cost. Restoring them creates social value at private cost — but the investment case is often compelling when the true numbers are visible.

The goal is to make externalities impossible to ignore and restoration impossible to overlook — not by moralizing, but by counting.

**If we can understand which actions harm the environment, we can also understand which ones will yield economic returns for everyone.**

---

## Roadmap

### ✅ v0.1 — Foundation (complete)

- [x] Define core abstractions and data model (`Resource`, `Agent`, `Ecosystem`, `SimulationResult`, `SimulationStep`)
- [x] Define scientific foundations (thermodynamics, trophic cascades, carrying capacity, resilience, succession, nutrient cycles, coevolution)
- [x] Define mathematical framework (dual-lens, monetary convergence, simulation methodology)
- [x] Implement non-linear damage functions: logistic, exponential, piecewise — each validated against 6 scientific invariants (boundary conditions, monotonicity, output range, nonlinearity, convexity, threshold shift)
- [x] Implement keystone species criticality weights (dependency_weight per agent, sums to 1.0, validated)
- [x] Build simulation engine — extraction mode: step-by-step propagation through agent network, per-step costs, cumulative costs, ecosystem health index
- [x] Implement input validation with clear error messages
- [x] Externality report generation with per-agent breakdown (format_report)
- [x] Implement Oak Valley Forest case (4 agents, logistic damage, calibrated parameters)
- [x] Implement Costa Brava Holm Oak Forest case (11 agents: mycorrhizal network, soil microbiome, canopy trees, understory, pollinators, forest birds, mammals, raptors, watershed, carbon/climate with exponential damage, human communities)
- [x] Implement Costa Brava Posidonia Meadow case (11 marine agents: seagrass, coralligenous reef, epiphytes, invertebrates, fish, megafauna, seabirds, coastal protection, water quality, blue carbon with exponential damage, human communities) — with marine economics inversion (one-time revenue vs annual recurring externality)
- [x] Full test suite: 375 tests covering all damage functions, models, validation, simulation, all three case scenarios, succession curves, carbon accounting, resilience zones, and end-to-end maturation integration
- [x] CLI for all three cases with configurable parameters

### ✅ v0.2 — Restoration Mode (complete)

- [x] Implement recovery functions with entropy asymmetry: `logistic_recovery` (inflection at 0.60, steepness 7.0 — shallower and slower than logistic damage at steepness 12.0) and `linear_recovery` (slope ≤ 1.0 encodes entropy cost; `f(1.0) = slope`, not 1.0)
- [x] Add `RestorationCost` dataclass (planting + annual maintenance × years)
- [x] Add `RestorationStep` and `RestorationResult` dataclasses
- [x] Extend simulation engine with `run_restoration()` — recovery ratio propagation, per-agent service value recovery, cumulative service value tracking, prevention advantage computation
- [x] Restoration report generation (`format_restoration_report`) with cost breakdown, per-agent recovered service values, net restoration value, and prevention advantage ratio
- [x] Add `--mode restore` CLI flag to all three cases
- [x] Implement `run_forest_restoration()`, `run_costa_brava_restoration()`, `run_posidonia_restoration()` convenience functions with ecologically-calibrated default costs
- [x] Prevention advantage ratios validated against ecological reality:
    - Oak Valley Forest: **2.50×** (temperate, faster recovery)
    - Costa Brava Holm Oak: **6.08×** (Mediterranean drought stress, mycorrhizal network delays)
    - Costa Brava Posidonia: **81.00×** (1-6 cm/year growth, specialist diving restoration at €200k/ha vs €2.5k/ha one-time revenue)

### ✅ v0.3 — Trophic Cascades & Interaction Networks (complete)

- [x] Implement trophic cascade amplification (damage multipliers by trophic level — primary consumers, secondary consumers, apex predators each amplify damage from lower levels)
- [x] Agent interaction matrix via `InteractionEdge` — directional edges between agents with interaction type (`trophic`, `mutualistic`, `competitive`) and strength
- [x] `propagation.py` module — `propagate_damage()` computes effective damage as direct damage plus cascading indirect damage through the interaction network
- [x] Trophic levels assigned per agent (1=producer, 2=primary consumer, etc.) with level-based amplification
- [x] Keystone species mechanics — agents with `is_keystone=True` and `keystone_threshold` trigger cascade amplification when their health drops below threshold
- [x] Extended `SimulationStep` to track both `direct_damage` and `cascaded_damage` per agent per step
- [x] Updated all three case files with interaction edges reflecting real ecological relationships
- [x] Reports show cascade breakdown: direct vs cascaded costs, trophic amplification factors

### ✅ v0.4 — Succession, Maturation Curves & Resilience Zones (complete)

- [x] Implement succession-based maturation curves (pioneer → intermediate → climax): three-phase model with configurable phase durations and service fractions — `SuccessionCurve` dataclass, `succession.py` module with `succession_service()`, `get_succession_phase()`, `compute_maturation_timeline()`, `compute_maturation_gap()`, `find_years_to_threshold()`
- [x] Maturation delay: configurable dead period at restoration start where replanted units provide zero ecosystem services (per-ecosystem: 2yr forest, 3yr Mediterranean, 5yr Posidonia)
- [x] Implement double carbon externality: `carbon.py` module with `compute_carbon_release()` (biomass + soil fraction), `compute_absorption_foregone()`, `compute_carbon_cost()`, `compute_annual_absorption()`, `compute_carbon_payback_period()` — monetized at configurable carbon price per tonne
- [x] Implement resilience zones: `resilience.py` module with `compute_resilience_zone()` (green/yellow/red classification), confidence interpolation, `compute_confidence_band()`, irreversibility warnings — flags when model confidence degrades past configured thresholds
- [x] Extended `models.py` with 5 new dataclasses: `SuccessionCurve`, `CarbonProfile`, `ResilienceConfig`, `MaturationStep`, `RestorationConfig`
- [x] Extended `Resource` (carbon_profile, resilience), `Agent` (succession_curve), `SimulationStep` (resilience_zone, model_confidence, irreversibility_warning), `RestorationResult` (maturation_timeline, years_to_pioneer/50pct/90pct, total_maturation_gap)
- [x] Extended `simulation.py`: Phase 4 resilience zone tagging in `run_extraction`, optional maturation pass in `run_restoration`
- [x] Extended `report.py`: Resilience Assessment section, Carbon Accounting section, Confidence Band section (extraction); Maturation Timeline, Maturation Gap, Carbon Recovery sections (restoration)
- [x] Extended `validation.py`: `validate_succession_curve`, `validate_carbon_profile`, `validate_resilience_config`
- [x] All three case files updated with ecosystem-specific parameters:
    - Oak Valley Forest: 8/25/60yr succession, 0.8 tCO₂/tree, 10% warning zone
    - Costa Brava: 12/35/80yr succession, 0.5 tCO₂/tree, 12% warning zone
    - Posidonia: 20/50/120yr succession, 130 tCO₂/ha + 2600 tCO₂ soil, 15% warning zone
- [x] `--time-horizon` CLI flag added to all three cases
- [x] 375 tests pass (320 existing + 55 new across 4 test files: test_succession.py, test_carbon.py, test_resilience.py, test_maturation.py)
- [x] Full backward compatibility — all v0.4 features are opt-in via Optional fields defaulting to None

### ✅ v0.5 — Physical Substrate & Derived Carrying Capacity (complete)

- [x] Add `SubstrateProfile` dataclass — physical substrate properties (substrate_type, soil_depth_cm, water_availability_mm_yr, water_clarity_kd, sediment_stability, erosion rates, formation rate, capacity function, confidence)
- [x] Add `SubstrateState` dataclass — mutable current state tracking current vs pristine substrate values, capacity_fraction, years_to_recover
- [x] New `substrate.py` module — capacity functions (linear, threshold, logistic), substrate degradation with nonlinear erosion interpolation (alpha exponent), substrate recovery, recovery year estimation
- [x] Three capacity functions encoding distinct ecological dynamics:
    - **Linear:** capacity = current/pristine (Oak Valley temperate forest)
    - **Threshold:** cliff-edge below critical minimum with residual fraction (Costa Brava holm oak — below ~8cm soil, K drops to near-zero)
    - **Logistic:** smooth S-curve for light-limited marine systems (Posidonia matte integrity)
- [x] Derive carrying capacity K from substrate state — `effective_K = total_units × capacity_fraction` — K is no longer fixed but degrades as substrate erodes
- [x] Phase 3.5 substrate degradation in `run_extraction()` — vegetation cover loss exposes substrate to erosion; erosion reduces capacity_fraction; tracked per simulation step (substrate_erosion, effective_k, k_fraction)
- [x] Substrate ceiling in `run_restoration()` — biological restoration capped at substrate capacity; enhanced prevention advantage including permanent capacity loss NPV
- [x] Substrate Impact Assessment section in extraction reports — substrate type, pristine values, capacity lost, pristine K vs current K, years to pristine substrate recovery
- [x] Substrate Restoration Ceiling section in restoration reports — max recoverable services, substrate recovery time, enhanced prevention advantage
- [x] Extended `validation.py` with `validate_substrate_profile()` — validates substrate properties, erosion/formation rates, capacity function type, confidence level
- [x] Calibrated substrate profiles for all three cases:
    - Oak Valley Forest: terrestrial_soil, 45cm depth, linear capacity, 15.0/0.5 t/ha/yr erosion, 0.8 t/ha/yr formation
    - Costa Brava Holm Oak: terrestrial_soil, 30cm depth, threshold capacity (8cm critical minimum), 25.0/1.0 t/ha/yr erosion, 0.4 t/ha/yr formation
    - Costa Brava Posidonia: marine_matte, logistic capacity, sediment_stability=0.85, 5.0/0.0 erosion, 1.0 mm/yr formation, alpha=3.0
- [x] 433 tests pass (375 existing + 58 new across test_substrate.py and test_substrate_cases.py)
- [x] Full backward compatibility — all v0.5 features are opt-in via Optional fields defaulting to None; no substrate = v0.4 behavior exactly

### ✅ v0.6 — NPV, Discounting & Carbon Credit Breakeven (complete)

The bridge between ecological modeling (v0.1–v0.5) and economic decision-making (v0.7–v0.8). Transforms Gaia's outputs from "this is the damage" into "this is the investment case."

Full specification: `V06_SPEC.md`

- [x] Add `DiscountConfig` dataclass — Ramsey-based discount rate (r = δ + η × g) with configurable pure time preference (δ), utility elasticity (η), and growth rate (g); supports constant rate and declining schedule (list of (year, rate) tuples); includes scarcity uplift rate, carbon price trajectory, and analysis horizon. Methods: `rate_at_year()`, `discount_factor()`, `carbon_price_at_year()`, `scarcity_factor()`
- [x] Add preconfigured discount profiles: `DISCOUNT_MARKET` (Nordhaus-adjacent, 4.1%), `DISCOUNT_CENTRAL` (Drupp et al. consensus, 2.3%), `DISCOUNT_ENVIRONMENTAL` (Stern-adjacent, 1.4%), `DISCOUNT_GREEN_BOOK` (UK Treasury declining 3.5%→2.5%)
- [x] Add `ExtractionNPV` dataclass — NPV breakdown: direct ecosystem service loss, carbon release, foregone absorption, substrate damage, total; all with scarcity uplift and rising carbon prices
- [x] Add `RestorationNPV` dataclass — investment case: discounted costs, recovering service benefits (scarcity-adjusted), carbon absorption benefits (at rising prices), net present value, ROI, carbon payback period
- [x] Add `CarbonBreakeven` dataclass — at what carbon price does restoration become privately profitable purely from carbon credit revenue? Includes breakeven price, gap to current EU ETS, projected breakeven year at carbon price growth rate
- [x] Add `PreventionAdvantageV06` dataclass — NPV-adjusted prevention advantage: simple (v0.2), with carbon, with substrate, full (all-inclusive); scarcity uplift and rising carbon prices make PA *increase* over time
- [x] Implement `compute_extraction_npv()` — discount stream of extraction externalities: direct costs with scarcity uplift, carbon release at current price, foregone absorption with rising prices, permanent substrate loss as NPV of perpetual services gap
- [x] Implement `compute_restoration_npv()` — discount restoration investment case: costs (planting + maintenance schedule), recovering services (succession × substrate ceiling × scarcity), carbon absorption (succession × rising prices), ROI
- [x] Implement `compute_carbon_breakeven()` — find carbon price where restoration NPV = 0 from carbon alone; solve breakeven_price = npv_cost / npv_absorption_per_euro; project when rising market prices reach breakeven
- [x] Implement scarcity uplift: `ecosystem_value_at_t = base_value × (1 + scarcity_rate)^t` — mathematically equivalent to reduced discount rate for environmental flows (default 2%/yr, per Drupp & Hänsel 2021)
- [x] Extend `Resource` with optional `DiscountConfig`; extend `SimulationStep` with discount_factor_at_step, npv_externality, carbon_price_used; extend `SimulationResult` with extraction_npv; extend `RestorationResult` with restoration_npv, carbon_breakeven, prevention_advantage_v06
- [x] NPV sections in extraction and restoration reports (only when DiscountConfig is provided): NPV Analysis (Ramsey components, scarcity uplift, extraction NPV breakdown), Investment Analysis (restoration NPV costs vs benefits, ROI), Carbon Breakeven (breakeven price, current price, projected year), Prevention Advantage v0.6 (simple/carbon/substrate/full PA)
- [x] Per-case discount configurations:
    - Oak Valley Forest: central profile (2.3%, 2% scarcity, 100yr horizon)
    - Costa Brava Holm Oak: central profile (2.3%, 2.5% scarcity for Mediterranean fragility, 100yr)
    - Costa Brava Posidonia: declining schedule (2.3%→1.8%→1.4%, 3% scarcity for marine irreversibility, 200yr horizon)
- [x] New `gaia/discount.py` module with preconfigured profiles and NPV computation functions
- [x] Extended `gaia/validation.py` with `validate_discount_config()` — validates rate >= 0, schedule sorted, horizon > 0, carbon price >= 0
- [x] 483 tests pass (433 existing + 50 new in tests/test_discount.py)
- [x] Full backward compatibility — no DiscountConfig = identical v0.5 behavior; all 433 existing tests pass unchanged

### ✅ v0.7 — Endogenous Pricing (Equilibrium-Derived Monetary Values) (complete)

Full specification: `V07_SPEC.md`

- [x] Replace static monetary_rate per agent with derived prices that emerge from the interaction matrix and ecosystem state — prices are no longer manually calibrated but computed from ecological structure
- [x] Implement Leontief-Hannon value system: V = (I − S·W)⁻¹ · A where V is the value vector, S is the diagonal scarcity matrix, W is the edge-strength matrix (transposed interaction matrix), and A is the anchor vector. Solved via Gaussian elimination with partial pivoting. All matrix operations in pure Python (no numpy) for Cython compatibility.
- [x] Scarcity functions: `compute_scarcity(health, scarcity_fn)` — two types:
    - **smooth**: `min(max_multiplier, 1.0 / health^α)` — as health drops toward zero, price rises sharply
    - **threshold**: quadratic rise below critical health threshold, capped at max_multiplier
- [x] Add `ScarcityFunction` dataclass — function_type ("smooth"/"threshold"), alpha, threshold, max_multiplier
- [x] Add `AnchorPoint` dataclass — agent_name, anchor_value, source, confidence, description
- [x] Add `PricingConfig` dataclass — anchors list, per-agent scarcity_functions dict, default_scarcity, convergence_tolerance, max_iterations, fallback_to_static
- [x] Add `PriceResult` dataclass — prices dict, scarcity_multipliers, demand_multipliers, anchor_contributions, spectral_radius, converged, iterations
- [x] Spectral radius validation via power iteration — verifies Hawkins-Simon condition (spectral radius of S·W < 1.0) for unique positive solution; binary search scarcity capping when condition is not met
- [x] Demand aggregation from v0.3 interaction matrix: agents with many high-strength incoming edges automatically receive higher prices — keystone species emerge as the most valuable purely from network centrality
- [x] Dynamic per-step pricing in `run_extraction()` — prices recomputed at each simulation step as ecosystem health changes. A pristine mycorrhizal network has a modest price; at 30% health it becomes enormously valuable because everything depends on it and it's scarce.
- [x] Extend `Ecosystem` with optional `PricingConfig`; extend `SimulationStep` with agent_prices list and price_result
- [x] Price decomposition in reports: per-agent price table showing price, scarcity multiplier, demand multiplier, and anchor contribution — user can see WHY each service is priced the way it is
- [x] Calibrated anchor points for all three cases:
    - Oak Valley Forest: 1 anchor (General Biosphere/Carbon at €80k — EU ETS × 1,000 tCO₂/yr); all agents smooth α=1.0, max_multiplier=50.0
    - Costa Brava Holm Oak: 2 anchors (Carbon €136k, Watershed €250k); 11 per-agent scarcity functions including threshold for Watershed at 0.4 critical health
    - Costa Brava Posidonia: 3 anchors (Blue Carbon €136k, Tourism €500k, Fishing €75k); 11 per-agent scarcity functions including thresholds for Coastal Protection and Water Quality at 0.3 critical health
- [x] Pricing is opt-in via `with_pricing=True` parameter in case builder functions — default `False` for backward compatibility
- [x] New `gaia/pricing.py` module with matrix math (pure Python), scarcity functions, and Leontief solver
- [x] Extended `gaia/validation.py` with `validate_scarcity_function()`, `validate_anchor_point()`, `validate_pricing_config()`
- [x] 510 tests pass (483 existing + 27 new in tests/test_pricing.py)
- [x] Full backward compatibility — no PricingConfig = identical v0.6 behavior; all 483 existing tests pass unchanged

### 🔲 v0.8 — Performance & Generalization

- Add Cython-optimized simulation loop (drop-in replacement, same API) — critical now that v0.7 adds a matrix solve per simulation step
- Generalize framework for additional resource types (water bodies, fisheries, agricultural soil, air quality)
- Keystone species uncertainty bounds — criticality weights with confidence intervals, Monte Carlo propagation of uncertainty into externality estimates
- Pluggable case template system — structured template for adding new ecosystems without writing Python

### ✅ v0.8.1 — I/O Flexibility (complete)

Full specification: `V081_SPEC.md`

- [x] Rename `--cut`/`--destroy` to mode-agnostic `--units` across all 4 cases (deprecated aliases preserved with `DeprecationWarning`)
- [x] Rename `--tree-value`/`--revenue` to consistent `--unit-value` across all 4 cases (deprecated aliases preserved)
- [x] Add warnings when restoration-only params (`--planting-cost`, `--maintenance-cost`, `--maintenance-years`, `--time-horizon`) are passed in extraction mode
- [x] Add `--with-pricing` flag to enable v0.7 endogenous pricing from CLI
- [x] Add `--format text|json` flag (default: `text`) for output format selection
- [x] Add `--output FILE` flag to write output to file instead of stdout
- [x] Add `--summary-only` flag to omit per-step data from JSON output
- [x] New `gaia/serialization.py` module — `simulation_result_to_dict()`, `restoration_result_to_dict()`, `to_json()` with stable, documented JSON schema
- [x] New `gaia/cli.py` module — shared CLI argument definitions (`add_common_arguments`, `add_restoration_arguments`, `warn_unused_restoration_args`, `output_result`)
- [x] Refactored `main()` in all 4 case files to decompose build → simulate → format pipeline for JSON support
- [x] JSON schema includes: ecosystem metadata, agent list, interaction edges, per-step data, NPV analysis, carbon breakeven, prevention advantage, endogenous pricing, and optional annotations (Posidonia marine note)
- [x] 579 tests pass (510 existing + 30 serialization + 21 CLI + 18 new across existing test files)
- [x] Full backward compatibility — all deprecated flags work, default text output unchanged, all 510 existing tests pass unmodified

### 🔲 v1.0 — UI (very big effort)

- Add a UI that allows users to set the model's parameters and see the output from the JSON visually (what would happen to this ecosystem if I do X?)
- Create a set of common images in isometric 3D view thanks to SVG (trees, plants, common animals, common fishes, mountains)
- We will show the ecosystem start and end after the actions applied by the user in a isometric square with out isometric SVGs. We will be able to know the end state thanks to the output JSON

---

## License

TBD

## Contributing

TBD
