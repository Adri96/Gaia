# Gaia v0.7 — Specification: Endogenous Pricing (Equilibrium-Derived Monetary Values)

## Overview

v0.7 is the version where prices become outputs instead of inputs. In v0.1–v0.6, every agent has a `monetary_rate` — a static number calibrated by hand from published studies, expert estimates, and regional data. These numbers are defensible, but they're judgment calls. Someone decided "mycorrhizal fungi are worth €400k max" and "watershed services are worth €500k max."

v0.7 replaces this with a system where prices **emerge from ecological structure**. The interaction matrix from v0.3 already contains the demand signal — which agents depend on which, and how strongly. The health state already contains the scarcity signal — degraded services are scarce and therefore expensive. Combining these gives a solvable system of equations where prices are computed, not assumed.

The theoretical foundation is the Leontief input-output model (1930s), extended to ecological systems by Hannon (1973, 1976, 2001) and further developed by Costanza (1980, 1991), Klauer (2000), and others who showed that ecosystem "prices" can be derived from the duality of quantities and values in material/energy flow networks.

**Scientific foundations used:** All foundations from v0.1–v0.6, plus the ecosystem pricing literature (Hannon, Costanza, Klauer) and input-output economics (Leontief, Cumberland, Ayres-Kneese).

---

## The Core Insight

Price = f(scarcity, demand). After v0.3, Gaia has both signals:

**Scarcity = health level.** A healthy watershed is abundant and cheap. A degraded watershed is scarce and expensive. The simulation already tracks health per agent at every step — we just need to map health to scarcity.

**Demand = interaction edges pointing at an agent.** How many other agents depend on this service, and how strongly? The interaction matrix from v0.3 encodes exactly this. An agent with many high-strength incoming edges (like mycorrhizal fungi, which canopy trees, understory, and soil all depend on) has high demand. An agent with few or weak incoming edges has low demand.

The system of equations:

```
value_i = anchor_i + scarcity(health_i) × Σⱼ(edge_strength_ji × value_j)
```

This is N equations in N unknowns. At a fixed ecosystem state, the scarcity terms are constants, making the system linear. It's solvable as a matrix inversion:

```
V = (I − S·W)⁻¹ · A
```

Where:
- **V** is the value vector (€ per agent)
- **I** is the identity matrix
- **S** is the diagonal scarcity matrix (scarcity_i on the diagonal)
- **W** is the weighted interaction matrix (transposed: W_ij = edge_strength from j to i)
- **A** is the anchor vector (external price anchors, zero for non-anchored agents)

This is structurally identical to the Leontief inverse `(I − A)⁻¹ · d` from input-output economics, where A is the matrix of technical coefficients and d is final demand. The Leontief inverse has been used in economics since the 1930s and in ecology since Hannon (1973).

---

## What Changes from v0.6

### Conceptual shift

In v0.1–v0.6, the cost computation is:

```
for each agent:
    cost = effective_damage[agent] × agent.dependency_weight × agent.monetary_rate
                                                                 ^^^^^^^^^^^^^^^^^^
                                                                 static, calibrated by hand
```

In v0.7, this becomes:

```
# Solve price system at current ecosystem state
price_vector = solve_prices(agent_healths, interaction_matrix, anchors)

for each agent:
    cost = effective_damage[agent] × agent.dependency_weight × price_vector[agent]
                                                                ^^^^^^^^^^^^^^^^^^
                                                                dynamic, derived from structure
```

The price vector is recomputed at each simulation step. As the ecosystem degrades, prices change — scarcer services become more expensive, and this propagates through the dependency network.

### What stays the same

- All dataclasses from v0.1–v0.6 (extended, not replaced)
- Damage functions, recovery functions (unchanged)
- Trophic amplification, interaction propagation (unchanged)
- Substrate model, succession curves (unchanged)
- NPV framework from v0.6 (extended to use dynamic prices)
- Report format (extended with price decomposition)
- CLI interface (extended with pricing mode flag)
- All v0.1–v0.6 tests must continue to pass

### What's new

1. **Scarcity functions** — map agent health to price multiplier (smooth and threshold variants)
2. **Anchor points** — external market prices that ground the system in real €-values
3. **Price solver** — matrix inversion at each simulation step
4. **Price decomposition** — per-agent breakdown showing WHY a service is priced the way it is
5. **Integration with v0.6 NPV** — endogenous prices feed into time-horizon projections

---

## Data Model

### ScarcityFunction (new)

Maps agent health (0.0–1.0) to a scarcity multiplier (≥ 1.0). Two variants, matching v0.5's substrate capacity function pattern:

```python
@dataclass
class ScarcityFunction:
    function_type: str          # "smooth" or "threshold"
    alpha: float                # elasticity parameter (smooth), or pre-threshold multiplier
    threshold: float            # health threshold below which price explodes (threshold type)
    max_multiplier: float       # cap to prevent infinity (default: 50.0)
    description: str            # e.g. "Smooth scarcity: price rises as 1/health^α"
```

**Smooth scarcity** (default):

```
scarcity(health) = min(max_multiplier, 1.0 / health^α)
```

When health = 1.0 (pristine), scarcity = 1.0 (no markup). When health = 0.5, scarcity = 2^α. When health approaches 0, scarcity approaches max_multiplier (capped to prevent division by zero).

The exponent α controls how aggressively prices rise with degradation:
- α = 0.5: gentle — 50% degradation → 1.4× price
- α = 1.0: linear — 50% degradation → 2× price (default)
- α = 2.0: aggressive — 50% degradation → 4× price

**Threshold scarcity** (for critical natural capital):

```
scarcity(health) = 
    1.0                                          if health > threshold
    1.0 + (max_multiplier - 1.0) × ((threshold - health) / threshold)^2   if health ≤ threshold
```

This models ecosystem services that are cheap when abundant but whose value explodes once they cross a critical threshold — matching the "critical natural capital" concept from Farley (2008) and DesRoches (2019). Above the threshold, scarcity = 1.0 (service is abundant, marginal value is low). Below the threshold, price rises quadratically toward max_multiplier.

This parallels v0.5's threshold substrate capacity function, which models carrying capacity that collapses below a critical soil depth. The economic analog: clean water is nearly free when watersheds are healthy, but replacement cost (desalination, treatment) is enormous once natural purification capacity degrades past a critical point.

**Constraints:**
- `function_type` must be `"smooth"` or `"threshold"`
- `alpha > 0.0` (smooth type)
- `0.0 < threshold < 1.0` (threshold type)
- `max_multiplier >= 1.0` (default: 50.0)

**Ecological justification for max_multiplier = 50.0:**

Costanza et al. (1997) showed that demand curves for many ecosystem services approach infinity as quantity approaches zero — the service becomes non-substitutable. However, in practice, infinite prices are computationally useless. The cap of 50× means that a near-totally-destroyed service is priced at 50× its pristine value. This is conservative: municipal water treatment (the replacement cost for watershed services) can be 100–500× the cost of natural water purification. But 50× is sufficient to demonstrate the economic case for prevention, and users can adjust it per ecosystem.

**Confidence:** HIGH for the functional forms (well-established in environmental economics). MEDIUM for specific α values (need calibration per ecosystem). The smooth form with α = 1.0 is the simplest defensible choice — it says "half the service, double the price."

### AnchorPoint (new)

An external market price that grounds the relative price system in absolute €-values.

```python
@dataclass
class AnchorPoint:
    agent_name: str             # name of the agent this anchors
    anchor_value: float         # €-value at pristine health (annual flow value)
    source: str                 # e.g. "EU ETS carbon price × annual sequestration"
    confidence: str             # "high", "medium", "low"
    description: str            # e.g. "Carbon: €80/t × 1.7 t/ha/yr × 1000 ha"
```

**Constraints:**
- `agent_name` must match an agent in the ecosystem
- `anchor_value > 0.0`
- At least one anchor per ecosystem is required for endogenous pricing
- Multiple anchors are allowed (the system is over-determined but still solvable — additional anchors improve robustness)

### PricingConfig (new)

Top-level configuration for endogenous pricing.

```python
@dataclass
class PricingConfig:
    anchors: list               # List[AnchorPoint] — at least one required
    scarcity_functions: dict    # Dict[str, ScarcityFunction] — per-agent, keyed by agent name
    default_scarcity: ScarcityFunction  # fallback for agents without explicit scarcity function
    convergence_tolerance: float  # for iterative solver if needed (default: 1e-6)
    max_iterations: int         # cap on iterative solve (default: 100)
    fallback_to_static: bool    # if True, use monetary_rate when solve fails (default: True)
```

**Defaults:**
- `default_scarcity = ScarcityFunction("smooth", alpha=1.0, threshold=0.3, max_multiplier=50.0)`
- `convergence_tolerance = 1e-6`
- `max_iterations = 100`
- `fallback_to_static = True`

### Agent (extended)

No new fields on Agent itself. The `monetary_rate` field remains as the static fallback. When `PricingConfig` is provided, the dynamic price replaces `monetary_rate` in cost calculations. When `PricingConfig` is absent, behavior is identical to v0.6.

### PriceResult (new)

Output of the price solver at a given ecosystem state.

```python
@dataclass
class PriceResult:
    prices: dict                # Dict[str, float] — computed price per agent
    scarcity_multipliers: dict  # Dict[str, float] — scarcity(health) per agent
    demand_multipliers: dict    # Dict[str, float] — network centrality contribution per agent
    anchor_contributions: dict  # Dict[str, float] — how much of price comes from anchor vs network
    spectral_radius: float      # spectral radius of S·W — must be < 1.0 for convergence
    converged: bool             # whether the solve converged
    iterations: int             # number of iterations (if iterative solver used)
```

### SimulationStep (extended)

```python
@dataclass
class SimulationStep:
    # --- all existing fields from v0.6 ---
    ...

    # --- new fields for v0.7 ---
    agent_prices: list          # per-agent dynamic price at this step (None if no PricingConfig)
    price_result: PriceResult   # full price decomposition (None if no PricingConfig)
```

---

## The Price Solver

### Mathematical Formulation

At each simulation step, the ecosystem is in some state where each agent has a health level h_i ∈ (0, 1]. The price system is:

```
V = (I − S·W)⁻¹ · A
```

Where:

**S** (scarcity matrix): N×N diagonal matrix where S_ii = scarcity(h_i) for each agent. This is computed from the agent's current health and its assigned scarcity function.

**W** (weighted interaction matrix): N×N matrix derived from v0.3's interaction edges. W_ij = edge_strength from agent j to agent i (note: transposed from the propagation direction). This captures "how much does agent i's value increase because agent j depends on it?"

Important: the interaction edges in v0.3 are defined as "damage to source propagates to target." For pricing, we need the reverse: "value flows from the depended-upon service to the depending agent." So W is the transpose of the damage propagation matrix. If agent A depends on agent B (edge from B to A), then B's value increases because A needs it — so W has an entry in the row for B, column for A.

**A** (anchor vector): N×1 vector where A_i = anchor_value for anchored agents, 0 for non-anchored agents.

### Construction of W from Interaction Edges

For each `InteractionEdge(source, target, strength, type, description)`:
- In damage propagation (v0.3): damage flows source → target
- In value attribution (v0.7): value flows target → source (the source is valuable BECAUSE the target depends on it)

Therefore:
```python
W[source_idx, target_idx] = strength
# i.e., W_ij represents how much value flows to agent i because agent j depends on it
```

This means agents with many outgoing damage edges (many things depend on them) accumulate high value — which is exactly the keystone species effect we want.

### Convergence Conditions

The Leontief system `V = (I − S·W)⁻¹ · A` has a unique positive solution if and only if the spectral radius of `S·W` is strictly less than 1.0. This is the **Hawkins-Simon condition** (1949), proven equivalent to the spectral radius condition by Wood & O'Neill (2002).

For Gaia's interaction matrices, convergence is guaranteed when:

1. All edge strengths are in (0, 1.0) — enforced by v0.3's validation
2. The product S·W has all entries < 1.0 — guaranteed when scarcity multipliers are moderate and the interaction graph is not too dense

**When might convergence fail?**

At extreme degradation (health near 0), scarcity multipliers can be large (up to max_multiplier = 50). If an agent with scarcity = 50× also has many strong incoming dependency edges, the product S·W can have spectral radius ≥ 1.0, meaning the system diverges — prices go to infinity.

This is actually **ecologically correct**: it means the ecosystem has degraded past the point where its services can be meaningfully priced. Below a certain health threshold, the ecosystem is functionally destroyed and its services are non-substitutable (Farley 2008). However, for computational purposes, we need to handle this gracefully.

**Fallback strategy:**

```python
def solve_prices(healths, interactions, anchors, config):
    S = build_scarcity_matrix(healths, config)
    W = build_value_matrix(interactions)
    A = build_anchor_vector(anchors)

    SW = S @ W
    spectral_radius = max(abs(np.linalg.eigvals(SW)))

    if spectral_radius >= 1.0:
        if config.fallback_to_static:
            # Use monetary_rate values — v0.6 behavior
            return PriceResult(converged=False, ...)
        else:
            # Cap scarcity multipliers and retry
            S_capped = cap_scarcity(S, target_spectral_radius=0.95)
            V = np.linalg.solve(np.eye(N) - S_capped @ W, A)
            return PriceResult(converged=True, capped=True, ...)

    V = np.linalg.solve(np.eye(N) - SW, A)
    return PriceResult(prices=dict(zip(agent_names, V)), converged=True, ...)
```

### Computational Cost

Matrix inversion is O(N³). For Gaia's ecosystems:
- Oak Valley: N = 4 → trivial
- Costa Brava forests: N = 11 → trivial
- Costa Brava Posidonia: N = 11 → trivial

Even with N = 100 agents (future generalization), the solve takes microseconds. The matrix solve adds negligible overhead to the simulation loop. Cython optimization (v0.8) is not needed for the price solver itself.

For very large N (>1000 agents, future consideration), the Neumann series approximation `(I − S·W)⁻¹ ≈ I + SW + (SW)² + ...` converges in ~10 terms when spectral radius < 0.9, and is more efficient than full inversion. This is deferred to v0.8.

### Alternative: Iterative Solver

For cases where the direct solve is numerically unstable (near-singular matrix), an iterative approach is available:

```python
V = A.copy()
for iteration in range(max_iterations):
    V_new = A + S @ W @ V
    if np.max(np.abs(V_new - V)) < tolerance:
        break
    V = V_new
```

This converges when spectral radius < 1.0 and is equivalent to the Neumann series expansion. Each iteration adds one more "round" of indirect value propagation. The number of iterations needed equals the effective depth of the dependency network.

---

## Scarcity Function Calibration

### Per-Agent Scarcity Assignment

Different ecosystem services have fundamentally different scarcity economics. The scarcity function should match the service type:

**Smooth scarcity (α = 1.0)** — default for most biological agents:
- Canopy trees, understory, fish populations, mammals, birds
- Rationale: degradation reduces service proportionally; marginal value rises smoothly

**Smooth scarcity (α = 1.5–2.0)** — for services with limited substitutability:
- Mycorrhizal fungi (no artificial substitute)
- Pollinators (limited substitutability — artificial pollination costs 100–1000× natural)
- Posidonia meadow (no substitute for coastal protection + nursery + carbon functions)
- Rationale: higher α captures the economic reality that these services become disproportionately expensive when degraded because there's no technological replacement

**Threshold scarcity** — for services with a clear critical threshold:
- Watershed & water cycle (threshold = 0.4): water purification services collapse below ~40% forest cover, requiring expensive municipal treatment
- Coastal protection (threshold = 0.3): wave attenuation provided by seagrass requires minimum meadow density; below this, beach erosion accelerates nonlinearly
- Blue carbon (threshold = 0.3): below minimum Posidonia coverage, matte decomposition releases stored carbon faster than living meadow can sequester — net carbon source
- Rationale: these services exhibit critical thresholds documented in the ecological literature where the service relationship shifts from "working" to "collapsed"

### Preconfigured Scarcity Assignments

**Costa Brava Holm Oak Forest:**

| Agent | Scarcity Type | Parameters | Rationale |
|---|---|---|---|
| Canopy Trees | smooth | α=1.0 | Standard biological service |
| Understory & Matorral | smooth | α=1.0 | Standard biological service |
| Mycorrhizal Fungi | smooth | α=2.0 | Non-substitutable; no artificial equivalent |
| Soil Microbiome | smooth | α=1.5 | Partially substitutable (fertilizers), but poorly |
| Pollinators & Insects | smooth | α=2.0 | Limited substitutability (hand pollination: ~$5,000/ha/yr) |
| Forest Birds | smooth | α=0.8 | Culturally valued but functionally somewhat redundant |
| Forest Mammals | smooth | α=0.8 | As above |
| Raptors & Apex Predators | smooth | α=0.5 | Iconic but ecologically replaceable top-down control |
| Watershed & Water Cycle | threshold | threshold=0.4, max=30 | Municipal water treatment cost = replacement anchor |
| Carbon & Climate | smooth | α=1.0 | EU ETS provides substitution price (carbon credits) |
| Human Communities | smooth | α=1.0 | Anchored externally |

**Costa Brava Posidonia Meadow:**

| Agent | Scarcity Type | Parameters | Rationale |
|---|---|---|---|
| Posidonia Meadow | smooth | α=2.0 | Foundation species; non-substitutable; millennium-scale recovery |
| Coralligenous & Red Coral | smooth | α=1.5 | Biogenic habitat; century-scale recovery |
| Epiphytes & Algae | smooth | α=0.8 | Faster recovery, some redundancy |
| Marine Invertebrates | smooth | α=1.0 | Standard biological service |
| Fish Populations | smooth | α=1.0 | Standard; anchored to fishing revenue |
| Marine Megafauna | smooth | α=0.5 | Iconic but low functional contribution |
| Seabirds | smooth | α=0.5 | As above |
| Coastal Protection | threshold | threshold=0.3, max=40 | Beach nourishment cost = replacement |
| Water Quality | threshold | threshold=0.3, max=30 | Turbidity collapse threshold |
| Blue Carbon | smooth | α=1.0 | EU ETS pricing provides substitution |
| Human Communities | smooth | α=1.0 | Anchored externally |

**Oak Valley Forest (minimal):**

| Agent | Scarcity Type | Parameters |
|---|---|---|
| Human Communities | smooth | α=1.0 |
| Animal Populations | smooth | α=1.0 |
| Vegetation & Flora | smooth | α=1.0 |
| General Biosphere | smooth | α=1.0 |

**Confidence for scarcity parameters:** MEDIUM. The functional forms are well-established, but the specific α values need calibration against observed replacement costs and willingness-to-pay studies. The choices above are defensible first approximations.

---

## Anchor Points: Grounding Prices in Reality

### The Anchor Problem

The price system produces **relative** prices — "mycorrhizal fungi are 3× more valuable than understory flora." To get absolute €-values, at least one agent must be anchored to an observable market price. This is the numéraire in general equilibrium theory.

Good anchors share three properties:
1. **Observable market price** — the value can be looked up, not estimated
2. **Annual flow** — the anchor represents a recurring service value, not a stock
3. **Clearly attributable** — the market price maps cleanly to one agent

### Preconfigured Anchors

**Costa Brava Holm Oak Forest:**

| Anchor | Agent | Value | Source | Confidence |
|---|---|---|---|---|
| Carbon | Carbon & Climate | €136,000/yr | EU ETS €80/t × 1.7 t CO₂/ha/yr × 1,000 ha area | HIGH — observed market price |
| Watershed | Watershed & Water Cycle | €250,000/yr | Municipal water treatment cost avoided: ~€2.50/m³ × 100,000 m³/yr recharge | MEDIUM — estimated recharge volume |

Calculation notes:
- Carbon anchor uses v0.6's €80/t current EU ETS price and the holm oak absorption rate validated in v0.4 (1.7 t CO₂/ha/yr). For 1,000 ha: 1,700 t/yr × €80/t = €136,000/yr.
- Watershed anchor uses Catalonia's water price (~€2.50–2.70/m³ from INE 2020 data, updated with 2024 inflation adjustments). The recharge volume (100,000 m³/yr for a 1,000 ha Mediterranean forest) is estimated from hydrological studies.

**Costa Brava Posidonia Meadow:**

| Anchor | Agent | Value | Source | Confidence |
|---|---|---|---|---|
| Carbon | Blue Carbon | €136,000/yr | EU ETS €80/t × 1.7 t CO₂/ha/yr × 1,000 ha | HIGH |
| Tourism | Human Communities | €500,000/yr | Costa Brava tourism revenue attributable to coastal water quality per ~5 km of coastline | MEDIUM |
| Fishing | Fish Populations | €75,000/yr | Artisanal catch value: ~15 boats × €5,000/yr/boat | MEDIUM — estimated from Catalan fleet data |

Calculation notes:
- Tourism anchor: Costa Brava received 8.5 million visitors in 2024 generating billions in revenue. A conservative estimate of €500,000/yr attributable to water quality for a 5 km stretch of coast is derived from willingness-to-pay studies for Mediterranean beach water quality.
- Fishing anchor: Mediterranean artisanal fleet in Catalonia comprises ~630 vessels (7.4% of Spain's 8,548-vessel fleet). Attributing proportional revenue for a local area with ~15 boats and average per-boat income of ~€5,000/yr from artisanal catch in Posidonia-dependent species.

**Oak Valley Forest (simplified):**

| Anchor | Agent | Value | Source | Confidence |
|---|---|---|---|---|
| Carbon | General Biosphere | €80,000/yr | €80/t × estimated 1,000 t CO₂/yr sequestration | MEDIUM |

### Multiple Anchors: Over-Determination

When multiple agents are anchored, the system is over-determined. This is desirable — it provides redundancy and cross-validation. If the prices derived from the carbon anchor are consistent with prices derived from the water treatment anchor, confidence increases. If they diverge significantly, it signals that either the anchors or the interaction strengths need recalibration.

Implementation: all anchors contribute additively to the anchor vector A. Each anchored agent has A_i = anchor_value; non-anchored agents have A_i = 0. The matrix solve distributes these anchor values through the dependency network.

---

## Integration with v0.6 NPV Framework

### Two Layers of Scarcity

As discussed and agreed, v0.7's endogenous pricing and v0.6's scarcity_rate operate at different levels:

**v0.7 (within-simulation scarcity):** Computes the price vector at each simulation step based on the live ecosystem state. When mycorrhizal health drops from 0.8 to 0.4, its price jumps because it's scarcer and everything depends on it. This is **local, state-dependent scarcity**.

**v0.6 (cross-temporal scarcity):** Adjusts prices when projecting into the future for NPV calculations. The scarcity_rate (default 2%/yr) captures the macro-trend that ecosystem services globally are becoming scarcer relative to manufactured goods (Drupp & Hänsel 2021: relative price change ~2–4%/yr). This is **global, time-dependent scarcity**.

### NPV with Endogenous Pricing

When both v0.7 PricingConfig and v0.6 DiscountConfig are provided, the NPV calculation uses:

```
NPV_service_i = Σₜ [endogenous_price_i(t) × (1 + scarcity_rate)^t × discount_factor(t)]
```

Where:
- `endogenous_price_i(t)` is the v0.7 price at simulation step t (state-dependent)
- `(1 + scarcity_rate)^t` is the v0.6 global scarcity uplift (time-dependent)
- `discount_factor(t)` is the v0.6 discount factor (time-dependent)

When only v0.6 DiscountConfig is provided (no PricingConfig), the system uses static `monetary_rate` with scarcity uplift — exactly v0.6 behavior. Full backward compatibility.

### Effect on Prevention Advantage

The prevention advantage (PA) is expected to increase significantly with endogenous pricing because:

1. Degradation raises endogenous prices (scarcity effect), compounding the damage cost
2. The interaction network amplifies price increases for keystone species (everything depends on mycorrhizal fungi → fungi price rises → total externality rises)
3. Restoration of a degraded ecosystem starts with high prices (high externality) that decrease as the ecosystem recovers — the early years of the damage gap are more expensive

Hypothesis: PA for Posidonia with endogenous pricing will exceed 200× (vs. 81× in v0.2, vs. already-elevated NPV-adjusted PA in v0.6). This should be validated by running the simulation with and without PricingConfig.

---

## Report Enhancements

### Price Decomposition Section (new)

When PricingConfig is active, the report gains a price decomposition:

```
  ── Endogenous Price Analysis ──────────────────────────────

  Pricing Mode: Endogenous (2 anchors: Carbon €136,000/yr, Watershed €250,000/yr)
  Spectral Radius: 0.72 (well-conditioned)

  Agent                          Price        Scarcity  Demand   Anchor
  ─────────────────────────────────────────────────────────────────────
  Mycorrhizal Fungi              €412,500     2.5×      3.3×     —
    → Price driven by: HIGH scarcity (health 0.40) × HIGH demand (3 dependents)
    → Largest contributor: Canopy Trees dependency (strength 0.35)
  Canopy Trees                   €285,000     1.5×      1.9×     —
    → Price driven by: MODERATE scarcity × MODERATE demand
  Watershed & Water Cycle        €312,000     4.2×      1.0×     €250,000
    → Price driven by: HIGH scarcity (below threshold 0.4) × anchored
  Carbon & Climate               €168,000     1.2×      1.0×     €136,000
    → Price driven by: LOW scarcity × anchored (EU ETS)
  ...

  Total Ecosystem Value:         €2,845,000/yr (endogenous)
  cf. Static Valuation:          €1,950,000/yr (v0.6 monetary_rate)
  Endogenous Premium:            +45.9% — reflects scarcity and network effects
```

### Price Sensitivity Section (optional)

When requested (e.g., via a `sensitivity=True` flag), the report includes:

```
  ── Anchor Sensitivity Analysis ────────────────────────────

  Carbon anchor ±20%:
    €64/t:  Total ecosystem value = €2,410,000 (−15.3%)
    €96/t:  Total ecosystem value = €3,280,000 (+15.3%)

  Watershed anchor ±20%:
    €200k:  Total ecosystem value = €2,650,000 (−6.9%)
    €300k:  Total ecosystem value = €3,040,000 (+6.9%)

  → Carbon anchor dominates total valuation. Better carbon price data
    would most improve accuracy.
```

### Integration with Existing Report Sections

The externality report's cost breakdown uses endogenous prices:

```
  ── Externalized Costs ─────────────────────────────────────

  Mycorrhizal Fungi:                            €412,500.00
    → Endogenous price: €412,500 (scarcity 2.5× × demand 3.3×)
    → cf. Static rate: €400,000 (+3.1% from endogenous)
```

---

## Cultural & Non-Ecological Value: v0.8 Enhancement

As agreed, services with no ecological demand signal (cultural/spiritual value, aesthetic beauty, existence value) are deferred to v0.8. In v0.7:

- Cultural value agents (if any exist) use the static `monetary_rate` fallback
- The price system ignores agents with no incoming interaction edges AND no anchor point — they receive `monetary_rate` as their price
- v0.8 will introduce a `cultural_weight` mechanism to handle these cases

This is the right choice because endogenous pricing's strength is in services with clear ecological demand signals. Forcing cultural values through the same framework would be scientifically questionable.

---

## Project Structure Changes

```
gaia/
├── __init__.py
├── models.py              # Extended: PricingConfig, AnchorPoint, ScarcityFunction,
│                          # PriceResult. SimulationStep + price fields.
├── damage.py              # Unchanged
├── recovery.py            # Unchanged
├── propagation.py         # Unchanged
├── substrate.py           # Unchanged
├── succession.py          # Unchanged
├── discount.py            # Unchanged (v0.6)
├── pricing.py             # NEW: scarcity functions, price solver, matrix construction,
│                          # price decomposition, convergence checks
├── simulation.py          # Extended: price solve per step when PricingConfig provided
├── validation.py          # Extended: validate PricingConfig, anchors, scarcity params
├── report.py              # Extended: price decomposition section, sensitivity analysis
└── cases/
    ├── __init__.py
    ├── forest.py          # Extended: anchor points, scarcity functions
    ├── costa_brava.py     # Extended: anchor points, scarcity functions
    └── posidonia.py       # Extended: anchor points, scarcity functions

tests/
├── __init__.py
├── test_pricing.py        # NEW: scarcity functions, solver, convergence, decomposition
├── test_simulation.py     # Extended: pricing integration tests
├── test_forest.py         # Extended: endogenous pricing in Oak Valley
├── test_costa_brava.py    # Extended: endogenous pricing in Mediterranean forest
├── test_posidonia.py      # Extended: endogenous pricing in marine ecosystem
└── ... (all existing test files unchanged)
```

---

## Testing Strategy

### test_pricing.py — Price Solver Engine (NEW)

#### Scarcity function tests

| Test | What it checks | Foundation |
|---|---|---|
| `test_smooth_scarcity_pristine` | health=1.0 → scarcity=1.0 | Boundary condition |
| `test_smooth_scarcity_degraded` | health=0.5, α=1.0 → scarcity=2.0 | Mathematical definition |
| `test_smooth_scarcity_alpha_effect` | Higher α → higher scarcity at same health | Elasticity parameter |
| `test_smooth_scarcity_capped` | health→0 → scarcity=max_multiplier | Prevents infinity |
| `test_threshold_scarcity_above` | health > threshold → scarcity=1.0 | Above threshold = abundant |
| `test_threshold_scarcity_below` | health < threshold → scarcity > 1.0 | Below threshold = scarce |
| `test_threshold_scarcity_at_zero` | health=0 → scarcity=max_multiplier | Fully collapsed service |
| `test_scarcity_monotonic` | Lower health → higher or equal scarcity (both types) | Economic axiom |

#### Matrix construction tests

| Test | What it checks |
|---|---|
| `test_W_matrix_from_interactions` | Interaction edges correctly transposed into value matrix |
| `test_W_matrix_empty_interactions` | No interactions → W is zero matrix |
| `test_anchor_vector_construction` | Anchored agents get anchor_value, others get 0 |
| `test_S_matrix_from_healths` | Diagonal scarcity matrix correctly built |

#### Solver tests

| Test | What it checks |
|---|---|
| `test_solve_trivial` | Single anchored agent, no interactions → price = anchor_value |
| `test_solve_two_agents` | Agent A depends on Agent B → B's price > its anchor |
| `test_solve_prices_positive` | All computed prices are > 0 |
| `test_solve_reproduces_anchor` | Anchored agent's price ≥ anchor_value |
| `test_spectral_radius_check` | Solver detects spectral radius ≥ 1.0 |
| `test_fallback_on_divergence` | When spectral radius ≥ 1.0 and fallback=True → uses monetary_rate |
| `test_solve_deterministic` | Same inputs → same outputs |
| `test_iterative_equals_direct` | Iterative solver matches direct matrix inversion |

#### Price dynamics tests

| Test | What it checks | Foundation |
|---|---|---|
| `test_degradation_increases_prices` | Lower health → higher total ecosystem value | Scarcity economics |
| `test_keystone_highest_price` | Agent with most incoming edges has highest price | Network centrality |
| `test_price_propagation` | Degrading one agent raises prices of its dependents | Demand propagation |
| `test_pristine_vs_degraded_ratio` | At 50% health, total value > pristine total (scarcity premium) | Counter-intuitive but correct |

### test_simulation.py — Extended Integration Tests

| Test | What it checks |
|---|---|
| `test_backward_compat_no_pricing` | No PricingConfig → identical to v0.6 output |
| `test_pricing_increases_extraction_cost` | Total externality with pricing > without (at moderate degradation) |
| `test_price_vector_changes_per_step` | Agent prices change across simulation steps |
| `test_npv_with_endogenous_prices` | NPV calculation uses dynamic prices + scarcity_rate |

### Ecological Plausibility Tests

| Test | What it checks |
|---|---|
| `test_mycorrhizal_most_expensive` | At 30% extraction, mycorrhizal fungi have highest price in holm oak case | F6 — keystone species centrality |
| `test_posidonia_price_dominates` | In marine case, Posidonia meadow has highest price | F6 — foundation species |
| `test_apex_predator_cheapest_biotic` | Raptors/megafauna have lowest prices among biotic agents | Low demand (few dependents) |
| `test_threshold_scarcity_watershed` | When watershed health crosses 0.4, its price jumps discontinuously | Critical natural capital |
| `test_total_value_increases_then_plateau` | As degradation progresses: total value first rises (scarcity premium), then plateaus (max_multiplier cap) | Scarcity economics with cap |
| `test_prevention_advantage_higher_with_pricing` | PA with endogenous pricing > PA with static pricing | Dynamic prices amplify damage cost |

### Edge Case Tests

| Test | What it checks |
|---|---|
| `test_all_agents_anchored` | Every agent has an anchor → prices dominated by anchors, network effects additive |
| `test_single_anchor` | Only one anchor → all prices relative to it |
| `test_zero_health_agent` | Agent at health=0 → price=max_multiplier × base | Cap prevents explosion |
| `test_disconnected_agent_no_anchor` | Agent with no interactions AND no anchor → fallback to monetary_rate |
| `test_very_dense_graph` | All-to-all interactions → spectral radius check catches potential divergence |
| `test_pricing_with_substrate_damage` | v0.5 substrate degradation + v0.7 pricing → permanent capacity loss reflected in prices |

---

## Definition of Done

v0.7 is complete when:

1. **All v0.1–v0.6 tests still pass.** No regressions.
2. **All new pricing tests pass** — scarcity functions, solver, convergence, price dynamics.
3. **All three cases work with endogenous pricing** — Oak Valley (1 anchor), Costa Brava forest (2 anchors), Posidonia (3 anchors).
4. **The report shows price decomposition** — per-agent price breakdown showing scarcity multiplier, demand multiplier, and anchor contribution.
5. **Backward compatibility is preserved** — ecosystems with no PricingConfig produce identical output to v0.6.
6. **Running the Costa Brava forest at 50% extraction** shows measurably higher total externality with endogenous pricing than with static monetary_rate.
7. **Mycorrhizal fungi and Posidonia meadow automatically emerge as the most expensive agents** without manual weighting — purely from network centrality.
8. **NPV calculations correctly integrate** endogenous prices (v0.7) with scarcity uplift (v0.6) and discount factors (v0.6).
9. **Spectral radius is checked** at each step; divergence is handled gracefully with fallback or capping.
10. **`pytest tests/ -v` — all green.**

---

## Parameter Documentation

### Scarcity Function Parameters

| Parameter | Value | Source | Confidence | Review Notes |
|---|---|---|---|---|
| α (default) | 1.0 | Economic theory: iso-elastic demand | MEDIUM | Should be calibrated against replacement cost data per service |
| α (mycorrhizal) | 2.0 | No technological substitute; implied by extreme restoration cost | LOW | Ecologist should evaluate if 2.0 overstates non-substitutability |
| α (pollinators) | 2.0 | Hand pollination costs 100-1000× (Garibaldi et al. 2013) | MEDIUM | Well-documented replacement cost |
| α (Posidonia) | 2.0 | Millennium-scale recovery; €200k/ha restoration cost | MEDIUM | Restoration cost data supports high α |
| threshold (watershed) | 0.4 | Forest cover/water purification threshold studies | MEDIUM | Region-specific; 40% may be too high for Mediterranean |
| threshold (coastal) | 0.3 | Seagrass density/wave attenuation studies | MEDIUM | Empirical data exists for Posidonia wave attenuation |
| max_multiplier | 50.0 | Conservative cap; real ratios can be 100-500× | HIGH for the concept | Value is a design choice, not empirical |

### Anchor Point Parameters

| Anchor | Value | Source | Confidence |
|---|---|---|---|
| EU ETS carbon price | €80/t CO₂ | Trading Economics, Feb 2026: €70-81/t | HIGH — observed market |
| Catalonia water price | ~€2.50/m³ | INE Spain 2020: €2.66/m³ in Catalonia; 2024 increases ~15% | HIGH — observed market |
| Costa Brava tourism (per 5km) | ~€500,000/yr | Derived: 8.5M visitors/yr (2024) × share attributable to water quality | MEDIUM — substantial estimation |
| Artisanal fishing (15 boats) | ~€75,000/yr | Spanish fleet data: 8,548 vessels, $2.1B total landings (2023) | MEDIUM — proportional estimate |

### Interaction Matrix (used for W)

All interaction edge strengths from v0.3 are used unchanged. They were calibrated as ecological dependency strengths but serve double duty as economic demand weights. The ecologist reviewer should evaluate whether economic demand is well-approximated by ecological dependency strength, or whether a separate "economic weight" per edge is needed.

---

## Open Questions for Future Versions

1. **Endogenous scarcity rate for v0.6:** Currently v0.6's scarcity_rate is a static 2%/yr parameter. In principle, v0.7 could compute the scarcity rate endogenously from the simulation's own ecosystem decline trajectory — if the model shows services declining at 3%/yr in the simulation, use 3%/yr as the scarcity rate for NPV projections. This creates a closed feedback loop and is deferred to v0.8.

2. **Cultural value (v0.8):** As agreed, services with cultural/spiritual/existence value but no ecological demand signal need a separate mechanism. Options include a `cultural_weight` field or treating them as additional anchor points with willingness-to-pay values.

3. **Price path dependence:** In the current formulation, prices at step t depend only on the ecosystem state at step t (health levels). They don't account for the *rate* of degradation — a slowly degrading forest might command different prices than one facing sudden destruction, because markets can adapt to gradual change but not to shocks. This is an extension for v0.8.

4. **Multi-ecosystem interactions:** When two ecosystems (forest + marine) share agents or services, prices in one should influence the other. This is deferred to the generalization phase (v0.8).

5. **Empirical validation:** The ultimate test of endogenous pricing is whether the computed prices match observed market values (where available) and willingness-to-pay studies (where market values don't exist). This requires running v0.7 on real Mediterranean ecosystem data and comparing outputs to the ESVD database (de Groot et al. 2012, 2024: 9,400+ value estimates across 15 biomes).

---

## Scientific Literature Sources

### Ecosystem Pricing & Input-Output Theory

- **Leontief, W. (1936).** "Quantitative input and output relations in the economic systems of the United States." *Review of Economics and Statistics*, 18(3), 105-125. — Original input-output framework.
- **Leontief, W. (1970).** "Environmental repercussions and the economic structure: An input-output approach." *Review of Economics and Statistics*, 52, 262-271. — Extension to environmental externalities.
- **Hannon, B. (1973).** "The structure of ecosystems." *Journal of Theoretical Biology*, 41, 535-546. — First application of input-output analysis to ecological systems.
- **Hannon, B. (1976).** "Marginal product pricing in the ecosystem." *Journal of Theoretical Biology*, 56, 253-267. — Ecosystem prices derived from energy flow networks.
- **Hannon, B. (2001).** "Ecological pricing and economic efficiency." *Ecological Economics*, 36(1), 19-30. — Combined economic-ecological price framework.
- **Costanza, R. (1980).** "Embodied energy and economic valuation." *Science*, 210, 1219-1224. — Energy-based ecosystem valuation.
- **Costanza, R. et al. (1997).** "The value of the world's ecosystem services and natural capital." *Nature*, 387, 253-260. — Global valuation synthesis; demand curves approaching infinity for non-substitutable services.
- **Klauer, B. (2000).** "Ecosystem prices: activity analysis applied to ecosystems." *Ecological Economics*, 33(3), 473-495. — Koopmans activity analysis applied to ecosystem pricing; algorithm for price calculation.

### Scarcity & Substitutability

- **Farley, J. (2008).** "The role of prices in conserving critical natural capital." *Conservation Biology*, 22(6), 1399-1408. — Critical natural capital: below threshold, economic valuation becomes meaningless.
- **DesRoches, C.T. (2019).** "On the concept of critical natural capital." — Historical analysis of non-substitutability in ecosystem services.
- **Drupp, M.A. & Hänsel, M.C. (2021).** "Relative price changes of ecosystem services: Evidence from Germany." *Environmental & Resource Economics*, 87(3), 833-880. — Relative price change 2-4%/yr for ecosystem services.
- **Drupp, M.A. (2018).** "Limits to substitution between ecosystem services and manufactured goods and implications for social discounting." *Environmental & Resource Economics*, 69(1), 135-158.
- **Baumgärtner, S. et al. (2015).** Income elasticity of WTP ~0.6; natural capital uplift ~40%.
- **Gollier, C. (2010).** Differentiated discount rates for ecosystem services due to limited substitutability.

### Convergence & Matrix Theory

- **Hawkins, D. & Simon, H.A. (1949).** "Note: Some conditions of macroeconomic stability." *Econometrica*, 17(3/4), 245-248. — Conditions for positive Leontief inverse.
- **Wood, R.J. & O'Neill, M.J. (2002).** "Using the spectral radius to determine whether a Leontief system has a unique positive solution." *Asia Pacific Journal of Operational Research*, 19, 233-247. — Spectral radius condition equivalent to Hawkins-Simon.

### Valuation Databases

- **de Groot, R. et al. (2012).** "Global estimates of the value of ecosystems and their services in monetary units." *Ecosystem Services*, 1, 50-61. — 9,400+ value estimates across biomes.
- **Brander, L. et al. (2024).** "Economic values for ecosystem services: A global synthesis." *Ecosystem Services*, 65. — Updated ESVD with standardized Int$/ha/yr values.

### Anchor Price Sources

- **EU ETS:** Trading Economics, Feb 2026: €70-81/t CO₂.
- **Spanish water:** INE Spain 2020 via Statista: Catalonia €2.66/m³; 2024 increases 15-33% (ATL, Barcelona).
- **Costa Brava tourism:** 8.5M visitors in 2024 season (Costa Brava Girona Tourism Board).
- **Spanish fishing fleet:** USDA FAS Spain Seafood Report 2024: 8,548 vessels, $2.1B landing value; Catalonia 7.4% of fleet.
- **Spain tourism overall:** WTTC 2024: €248.7B contribution to GDP, 15.6% of economy.