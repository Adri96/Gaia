# Gaia — Version Roadmap

This document breaks the Gaia vision into buildable, incremental versions. Each version produces a working, usable tool that delivers real value. The full scientific foundations and mathematical framework are defined in GAIA.md — this document defines *what we build and when*.

The guiding principle: **each version should run, produce meaningful output, and be testable.** No version is a "setup" version — every release does something useful.

---

## v0.1 — The Core Loop

**Goal:** A working simulation that cuts trees from a forest, computes non-linear externality costs per agent, and produces a text report. The simplest possible thing that embodies the Gaia thesis.

**Scientific foundations used:** Thermodynamics (F1), Entropy Asymmetry (F2), Carrying Capacity (F4), Independent Agents (F5).

### What we build

- **Resource dataclass** — a forest with N total trees and a safe extraction threshold (expressed as a fraction of N).
- **Agent dataclass** — a named entity with a dependency weight, a damage function, and a monetary conversion rate. No inter-agent interactions yet.
- **Damage functions** — a library of `float → float` callables. The primary one is a **logistic curve** calibrated around the safe threshold: low damage below threshold, accelerating damage above it. Also include exponential and piecewise-linear as alternatives.
- **Ecosystem dataclass** — a Resource bound to a list of Agents.
- **Simulation engine** — a loop that extracts one unit (tree) per step. At each step, it computes the current depletion ratio, evaluates each agent's damage function, converts to monetary cost, and records the result.
- **Externality report** — a plain-text summary showing: resource state, private gains (revenue per tree × trees cut), per-agent externality costs, total externality, and net social cost.

### Preconfigured case: Forest

Four agents, each with a logistic damage function and a flat monetary rate:

| Agent | Dependency Weight | Monetary Rate | Notes |
|---|---|---|---|
| Human Communities | 0.20 | Configurable (€/unit damage) | Health, water, recreation |
| Animal Populations | 0.30 | Configurable (€/unit damage) | Habitat, biodiversity |
| Vegetation & Flora | 0.15 | Configurable (€/unit damage) | Soil, pollination |
| General Biosphere | 0.35 | Configurable (€/unit damage) | Carbon, watershed, climate |

### Technical constraints

- Pure Python, typed dataclasses, all fields with explicit types.
- All functions are `float → float` — no complex objects in the hot path.
- Cython-ready structure: no dynamic attributes, no `**kwargs`, no inheritance in core computation.
- Zero third-party dependencies in core (standard library only).
- Tests with `pytest`.

### What this version does NOT include

- No restoration mode.
- No maturation curves.
- No inter-agent damage propagation.
- No trophic cascade amplification.
- No Cython compilation (just Cython-compatible structure).
- No NPV, discounting, or time-based economics.

### Definition of done

Running `python -m gaia.cases.forest --trees 10000 --threshold 0.3 --cut 5000` produces a correct externality report where costs are modest up to 3,000 trees and accelerate sharply after.

---

## v0.2 — Restoration Mode & Entropy Asymmetry

**Goal:** Run the simulation in reverse — model reforestation as an investment with real costs, maturation delays, and a comparison to prevention.

**New scientific foundations used:** Ecological Succession (F8).

### What we build

- **Recovery functions** — `float → float` callables that map restoration ratio to recovered ecosystem services. Same interface as damage functions, but with a shallower curve (slower recovery than damage).
- **Maturation curves** — simple time functions: `years_since_planting → service_capacity (0.0 to 1.0)`. First implementation: a **logistic growth curve** parameterized with years-to-50% and years-to-90% capacity. Later versions will use succession-based models.
- **Restoration cost dataclass** — per-unit cost of planting, plus annual maintenance cost and duration.
- **Restoration simulation mode** — given a degraded ecosystem, simulate planting trees over time, applying maturation curves to compute when ecosystem services actually recover.
- **Investment report** — total restoration cost, recovered ecosystem services over a time horizon, simple ROI (no discounting yet), payback period, and the **prevention vs. restoration comparison** ("not cutting would have cost €X; cutting and restoring costs €Y; prevention advantage: Z×").

### Definition of done

Running a restoration scenario on the degraded Oak Valley Forest from v0.1 produces an investment report showing that prevention is significantly cheaper than restoration, with a quantified ratio.

---

## v0.3 — Trophic Cascades & Agent Interactions

**Goal:** Agents are no longer independent. Damage to primary producers (trees) amplifies through the trophic pyramid, and keystone agent loss triggers cascading failures.

**New scientific foundations used:** Primary Productivity & Trophic Pyramids (F3), Keystone Species (F6), Coevolution (F10).

### What we build

- **Trophic level assignment** — each agent gets a trophic level (producer, primary consumer, secondary consumer, tertiary consumer). Agents higher in the pyramid have an **amplification factor** on damage from levels below.
- **Agent interaction matrix** — a simple NxN matrix defining how damage to agent A propagates to agent B. Sparse — most entries are zero. This captures dependencies like "pollinator loss → vegetation reproduction collapse."
- **Keystone criticality weights** — agents can be flagged as keystone with a criticality multiplier. When a keystone agent's health drops below a threshold, it triggers additional damage to dependent agents.
- **Propagation in simulation loop** — after computing direct damage per step, run a propagation pass that applies trophic amplification and interaction effects. One propagation round per step (no iterative convergence yet).

### Definition of done

A simulation where removing trees (producers) causes disproportionately larger damage to animal populations (consumers) than to the biosphere agent, reflecting trophic amplification. Removing a keystone pollinator agent triggers measurable cascading damage to vegetation.

---

## v0.4 — Population Dynamics & Resilience

**Goal:** Agents respond dynamically to extraction using real population models. The system flags when it enters uncertain resilience zones.

**New scientific foundations used:** Carrying Capacity with R/K dynamics (F4 deepened), Resilience (F7).

### What we build

- **R/K population dynamics per agent** — animal agents follow logistic population models with species-appropriate r values and carrying capacities. R-strategy agents (insects, small mammals) rebound quickly but may overshoot. K-strategy agents (large mammals, hardwood trees) recover slowly but stably.
- **Dynamic damage functions** — damage is no longer a static function of depletion ratio. It incorporates the current population state of each agent, so the same extraction at different times produces different costs (path dependence becomes real, not just structural).
- **Resilience zones** — define three zones around the safe threshold:
  - **Green zone** (below threshold): ecosystem is very likely resilient. Extraction cost is modest.
  - **Yellow zone** (near threshold): resilience is uncertain. Gaia flags this with a warning and a confidence range on damage estimates.
  - **Red zone** (well past threshold): ecosystem resilience is likely compromised. Damage estimates carry high uncertainty, and Gaia flags potential irreversibility.
- **Succession-based maturation** — replace the simple logistic maturation curve from v0.2 with a three-phase succession model: pioneer (fast growth, minimal services) → intermediate (moderate growth, partial services) → climax (slow growth, full services).

### Definition of done

Running identical extraction scenarios produces different outcomes depending on the order and timing of extraction (true path dependence). The report includes resilience zone warnings when extraction enters the yellow zone.

---

## v0.5 — Carbon Cycle & Financial Economics

**Goal:** Model the double carbon externality properly, and add real financial tools (NPV, discounting, carbon credit pricing).

**New scientific foundations used:** Nutrient Cycles & Carbon Cycle (F9).

### What we build

- **Double carbon externality** — when a tree is cut, the externality includes: (a) CO₂ released from the tree, and (b) the net present value of CO₂ that tree would have absorbed over its remaining expected lifetime. Both are converted to monetary terms using a configurable carbon price.
- **Carbon accounting per step** — the simulation tracks cumulative carbon released and cumulative absorption capacity lost, separate from other externality costs.
- **NPV and discounting** — all monetary values can be expressed in net present value using a configurable discount rate. Both the destruction report and the restoration investment report use proper time-value-of-money calculations.
- **Carbon credit breakeven analysis** — "At what carbon price does restoration become privately profitable?" Gaia can compute the carbon credit price at which the restoration ROI crosses 1.0x.
- **Cython optimization** — the simulation loop (extraction, damage computation, propagation, carbon accounting) is implemented as a `.pyx` module that can be compiled with Cython for performance. Pure Python remains the default; Cython is a drop-in accelerator.

### Definition of done

A forest simulation produces a report that includes carbon-specific externality costs, NPV-adjusted figures, and a carbon credit breakeven price. The Cython-compiled version runs at least 5× faster than pure Python on a 100,000-tree forest simulation.

---

## Future versions (unscoped)

These are directions we know we want to explore, but haven't scoped into specific deliverables yet:

- **Generalization beyond forests** — water systems, fisheries, soil, air quality. The core framework (Resource, Agent, Ecosystem, Simulation) should already support this by v0.3; what's needed is calibrated cases with real data.
- **Region-specific monetary conversion** — externality costs vary dramatically by geography (a tree in the Amazon vs. suburban Europe). Pluggable converters per region.
- **Multi-resource ecosystems** — an ecosystem that depends on multiple resources simultaneously (forest + watershed + soil), where extracting one affects the others.
- **Uncertainty quantification** — Monte Carlo simulation across parameter ranges to produce confidence intervals on externality estimates, not just point values.
- **Visualization** — charts showing the extraction curve, per-agent damage over time, restoration trajectories, and resilience zone maps.
- **Data integration** — connect to real ecological datasets for calibration (forest inventories, biodiversity databases, carbon flux measurements).

---

## Verification & Scientific Validation Strategy

Gaia's credibility depends entirely on the quality of its inputs. A perfectly engineered simulation with arbitrary parameters is just a fancy opinion. Every parameter must be traceable to a source, and the scientific model itself must withstand scrutiny from domain experts.

### The Core Principle

**Every parameter must be traceable to a source.** Where does the safe threshold come from? What study? What dataset? What's the confidence interval? If a number cannot be justified, it must be explicitly marked as a placeholder and flagged in the output.

### Two-Track Validation

Gaia requires validation on two separate tracks that must not be confused:

**Track 1 — Scientific validation.** Are the foundations correct? Are we oversimplifying anything dangerously? Is there a principle we're missing? Are the damage curve shapes ecologically defensible? This is reviewed by ecologists and environmental scientists who can judge whether the *model structure* reflects how ecosystems actually behave.

**Track 2 — Data calibration.** Are the specific numbers right? Is 30% a defensible safe extraction threshold for a temperate deciduous forest? What's the monetary value of carbon sequestration per hectare per year in this region? What data sources back these numbers? This is reviewed by domain experts with access to field data, published studies, and regional ecological assessments.

### Validation Process Per Version

Each version goes through the same cycle:

1. **Build with placeholders.** We implement the engine with parameter values that are in the right ballpark but explicitly marked as uncalibrated. The code works; the numbers are approximate.

2. **Review package.** We prepare two deliverables for the scientific reviewer:
   - The **GAIA.md scientific foundations** — do these hold up? What's wrong, oversimplified, or missing?
   - The **preconfigured case with its parameters** — are the thresholds, damage curves, and monetary rates in the right universe? What would you change, and what data sources would you point us to?

3. **Expert review.** The reviewer critiques the running model, not an abstract spec. They interact with actual outputs: "this externality cost for 5,000 trees cut from a 10,000-tree temperate forest — does this number feel right? Too high? Too low? By how much?"

4. **Calibration update.** We incorporate feedback, update parameters, document the sources, and tag the version as calibrated for the specific case.

5. **Sensitivity analysis.** For each calibrated case, we run the simulation across a range of parameter values to understand which inputs the output is most sensitive to. This tells us where better data matters most.

### Parameter Documentation Standard

Every configurable parameter in Gaia must carry:

- **Value** — the number used.
- **Unit** — what the number measures.
- **Source** — where it comes from (study, dataset, expert estimate, or "placeholder").
- **Confidence** — how reliable the source is (published peer-reviewed, grey literature, expert opinion, rough estimate).
- **Sensitivity** — how much the final output changes if this parameter is varied by ±20% (computed automatically by the sensitivity analysis).

This metadata is stored alongside the parameter, not in a separate document. When Gaia produces a report, any number flagged as "placeholder" or "low confidence" should be visible in the output so that users know where the uncertainty lives.

### Validation Milestones

| Version | What gets validated | Who validates |
|---|---|---|
| **v0.1** | Scientific foundations (GAIA.md), damage curve shapes, forest case parameter ranges | Ecologist reviewer |
| **v0.2** | Restoration cost assumptions, maturation curve shape, succession timeline plausibility | Ecologist + forestry data |
| **v0.3** | Trophic amplification factors, interaction matrix structure, keystone criticality assumptions | Ecologist reviewer |
| **v0.4** | R/K parameters per species, resilience zone boundaries, population model behavior | Ecologist + population biology data |
| **v0.5** | Carbon flux numbers, absorption capacity estimates, carbon credit pricing assumptions | Ecologist + climate/carbon data |

### What We Build vs. What We Validate

The engineering team (us) builds the engine — the structure, the algorithms, the simulation loop, the report generation. We ensure the code is correct, fast, and extensible.

The scientific reviewer validates the model — the foundations, the parameter values, the curve shapes, the ecological plausibility of outputs. They ensure the numbers are credible.

These are separate responsibilities. The code can be ready before the calibration is done. We build first with placeholders, then calibrate with expert input. This keeps both tracks moving in parallel without blocking each other.

---

## Version summary

| Version | Core Feature | Foundations Used | Complexity |
|---|---|---|---|
| **v0.1** | Extraction simulation + externality report | F1, F2, F4, F5 | Low — buildable in a few sessions |
| **v0.2** | Restoration mode + prevention comparison | + F8 | Medium — adds time dimension |
| **v0.3** | Trophic cascades + agent interactions | + F3, F6, F10 | Medium — adds agent coupling |
| **v0.4** | Population dynamics + resilience zones | + F4 deep, F7 | High — dynamic state per agent |
| **v0.5** | Carbon cycle + financial economics + Cython | + F9 | High — adds carbon + NPV + perf |

Each version builds on the previous one. No version requires rewriting what came before — only extending it.
