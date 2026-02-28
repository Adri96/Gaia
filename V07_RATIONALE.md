# v0.7 — Endogenous Pricing: Design Rationale

## The question that started this

> In the end, the price is just an equilibrium point for offer and demand. I'm not sure if we could, with the ecosystem information, "solve" a certain system of unknowns to find the right price value for each thing.

In v0.1–v0.6, every agent has a `monetary_rate` — a static number we calibrate by hand from published studies, expert estimates, and regional data. It works, but it's a judgment call. Someone decided "mycorrhizal fungi are worth €400k max" and "watershed services are worth €500k max." These numbers are defensible but they're inputs, not outputs.

The insight is that the interaction matrix from v0.3 already contains the economic structure needed to _derive_ prices instead of imposing them.

## Why it works

Price = f(scarcity, demand). After v0.3, Gaia has both signals:

**Scarcity = health level.** A healthy watershed is abundant and cheap. A degraded watershed is scarce and expensive. The simulation already tracks health per agent at every step — we just need to map health to scarcity.

**Demand = interaction edges pointing at an agent.** How many other agents depend on this service, and how strongly? The interaction matrix encodes exactly this. An agent with many high-strength incoming edges (like mycorrhizal fungi, which canopy trees, understory, and soil all depend on) has high demand. An agent with few or weak incoming edges has low demand.

Combine them:

```
price_i = base_anchor_i × scarcity(health_i) × Σⱼ(edge_strength_ji × price_j)
```

This is a system of N equations in N unknowns. It's linear at a fixed ecosystem state. It's solvable as a matrix inversion: `V = (I − S·W)⁻¹ · A`.

## What this buys us

1. **No more manual monetary rate calibration.** Prices are computed from ecological structure. The ecologist reviewer only validates the interaction graph (edges, strengths, trophic levels) — not hundreds of monetary values.

2. **Prices are dynamic.** They change as the ecosystem degrades. A pristine mycorrhizal network has a modest price. At 30% health, it becomes enormously valuable — everything depends on it and it's scarce. This is economically correct: we don't value clean air until it's gone.

3. **Keystone species are automatically the most expensive.** No need for special weighting — their high price emerges from network centrality (many dependents × high edge strengths). The math discovers what the ecologist would tell you.

4. **The model becomes more honest.** Currently we say "this forest's externality is €3.5M" and the number comes from calibrated rates. With endogenous pricing we'd say "this forest's externality is €3.5M and here's why: the mycorrhizal network alone accounts for €1.2M because 4 agents depend on it at strength 0.25–0.35 and its health is at 0.4 (scarcity multiplier 2.5×)." The price decomposition tells a story.

## The anchor problem

The system produces _relative_ prices — "mycorrhizal network is 3× more valuable than understory flora." To get absolute €-values, you need at least one external anchor: a service where the real monetary value is known from market data.

Good anchors (observable market prices):

- **Carbon:** EU ETS price (~€80/tonne CO₂) → anchors the Carbon & Climate agent
- **Water treatment:** municipal cost per m³ → anchors the Watershed agent
- **Tourism revenue:** regional data per km of beach or per visitor → anchors Human Communities
- **Fishing revenue:** artisanal catch value → anchors Fish Populations (marine case)

Only 1–2 anchors per ecosystem. Everything else floats relative to them.

## Why v0.7 and not earlier

The endogenous pricing system requires:

- v0.3's interaction matrix (the demand structure)
- v0.5's substrate model (physical constraints on supply)
- v0.6's NPV framework (time-horizon for price dynamics)

Without the interaction graph, there's no demand signal to solve for. It has to come after v0.3.

## Open questions for the ecologist

- Is the scarcity function `1/health^α` reasonable, or should scarcity be stepwise (cheap until a threshold, then expensive)?
- Are there ecosystem services where demand is NOT well-captured by interaction edges? (e.g., cultural/spiritual value of a forest — no agent "depends" on it in the ecological sense, but humans value it)
- Should the system allow negative prices? (An invasive species or algal bloom might have negative value — its removal is the service)

## Summary

v0.7 turns Gaia from a tool where you input prices into one where prices emerge from structure. The interaction matrix is simultaneously an ecological dependency graph and an economic demand system. The math is clean, the implementation is a matrix solve per step, and the result is more defensible, more dynamic, and more transparent than static calibration.
