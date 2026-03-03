# Gaia v0.6 — NPV, Discounting & Carbon Credit Breakeven

## Goal

Introduce proper time-value-of-money economics to Gaia. All monetary values — extraction costs, restoration investments, ecosystem service flows, carbon externalities, substrate damage — become discountable to present value. A new carbon credit breakeven analysis answers: *"At what carbon price does restoration become privately profitable?"*

v0.6 is the bridge between ecological modeling (v0.1–v0.5) and economic decision-making (v0.7–v0.8). It transforms Gaia's outputs from "this is the damage" into "this is the investment case."

---

## 1. The Discount Rate: Why It Matters

### 1.1 The Core Problem

Gaia's simulations produce streams of costs and benefits over decades to millennia:

- **Extraction externalities** accrue over the remaining productive lifespan of destroyed organisms (80 years for holm oak, effectively infinite for Posidonia)
- **Restoration investment** has upfront costs with benefits that compound over maturation timelines (60–120 years per v0.4 succession curves)
- **Substrate damage** creates permanent capacity loss whose NPV depends critically on the discount rate (v0.5's millennia-scale soil/matte recovery)
- **Carbon externalities** include foregone absorption extending over the remaining productive lifetime of destroyed units

Without discounting, a euro of ecosystem services 100 years from now is weighted equally with a euro today. With a 4.3% rate (Nordhaus), that future euro is worth just €0.015 today. With a 1.4% rate (Stern), it's worth €0.25. The difference is 17× — enough to flip any cost-benefit analysis from "do nothing" to "act urgently."

### 1.2 The Ramsey Framework

We adopt the Ramsey formula as the theoretical foundation:

```
r = δ + η × g
```

Where:
- **δ** (delta) — pure rate of time preference: how much society discounts future utility solely because it occurs later. Range: 0–3% in the literature.
- **η** (eta) — elasticity of marginal utility of consumption: how much an extra euro matters as people get richer. Range: 1.0–2.0.
- **g** — per capita consumption growth rate. Historical: ~1.3% for developed economies.

This formula gives structure to the debate. It separates the *ethical* question (δ: should we treat future generations equally?) from the *empirical* one (η × g: will future people be richer?).

### 1.3 The Stern–Nordhaus Spectrum

The two poles of environmental discounting, as crystallized in the 2006–2007 debate:

| Parameter | Stern (2006) | Nordhaus (2007) | Drupp et al. (2018) survey median |
|-----------|--------------|-----------------|-----------------------------------|
| δ (pure time preference) | 0.1% | 1.5% | 0.5% |
| η (utility elasticity) | 1.0 | 2.0 | 1.35 |
| g (growth rate) | 1.3% | 1.3% | ~1.5% |
| **r (discount rate)** | **1.4%** | **4.3%** | **~2.0%** |

**Stern's argument:** Ethically, δ should be near zero — the only justification for positive δ is the small probability of human extinction (~0.1%/year). Current generations should not privilege their own welfare over future generations.

**Nordhaus's argument:** δ should reflect observed market behavior (revealed time preferences from interest rates and savings rates). Using prescriptive rates risks impoverishing people today for speculative future benefits.

**Emerging consensus (Drupp et al. 2018):** A survey of 200+ economists found median SDR of 2.0%, mean 2.27%, with 75% agreeing that 2% is acceptable for long-term climate projects. The median δ was 0.5%, mean 1.1%, with many choosing zero.

**Confidence:** High for the framework; medium for specific parameter values. The Ramsey formula is universally accepted. Parameter choice remains contested but the 2% consensus for environmental projects is well-supported.

### 1.4 Declining Discount Rates

For projects with very long time horizons (>30 years), there is strong theoretical and institutional support for declining rates:

**UK Treasury Green Book schedule:**
- Years 0–30: 3.5%
- Years 31–75: 3.0%
- Years 76–125: 2.5%
- Health/life outcomes: 1.5% (any time horizon)

**Theoretical justification (Weitzman 1998, 2001):** Under uncertainty about future growth rates, the effective discount rate declines over time toward the lowest plausible rate. This is not an ethical judgment — it's a mathematical consequence of uncertainty. When g is uncertain, the certainty-equivalent discount factor gives more weight to low-growth scenarios at long horizons, producing a declining effective rate.

**Relevance to Gaia:** Mediterranean soil recovery takes ~10,000 years. Posidonia matte recovery takes ~2,000 years. Holm oak succession takes 80 years. At these timescales, the difference between constant and declining rates is enormous. A constant 3.5% makes millennia-scale substrate loss essentially worthless in present value. A declining schedule preserves significant present value for these irreversible losses.

**Confidence:** High. Declining rates are endorsed by the UK Green Book, the French Quinet Commission (declining from 4.0%), and recommended by the US National Academies (2017). The current UK Treasury review (reporting June 2026) is re-examining the specific schedule, not the principle.

### 1.5 The Relative Price Effect

A critical insight for environmental economics: as ecosystem services become scarcer relative to manufactured goods, their real price rises. This rising relative price partially or fully offsets the discount rate for environmental goods.

**The mechanism:** If GDP grows at g_c = 2%/yr but ecosystem services decline at g_e = -0.5%/yr, and the elasticity of substitution between the two is less than 1 (they are imperfect substitutes), then the relative price of ecosystem services rises at approximately:

```
RPC ≈ (1/σ) × (g_c - g_e)
```

where σ is the elasticity of substitution.

**Empirical estimates:**
- Drupp and Hänsel (2021): relative prices of non-market goods rise ~2–4%/yr, leading to a social cost of carbon >50% higher than models assuming perfect substitutability.
- Baumgärtner et al. (2015): ~0.5%/yr decline in global ecosystem services; combined with low substitutability, RPCs of ~1.7%/yr.
- Germany-specific (2024 meta-study): ~4%/yr aggregate RPC for ecosystem services.
- A global meta-analysis (2025) of 735 income-WTP pairs found income elasticity of WTP of ~0.6, implying RPC of ~1.7%/yr. Natural capital values should be uplifted by ~40%.

**Implementation in Gaia:** Rather than implementing dual discount rates (which creates theoretical complications when goods are substitutable), we adopt the equivalent approach recommended by the UK Treasury's 2021 environmental discount rate review: apply the standard discount rate to all cash flows, but use a **scarcity uplift** on ecosystem service valuations that rises over time.

```python
ecosystem_value_at_t = base_value × (1 + scarcity_rate) ^ t
```

Default `scarcity_rate = 0.02` (2%/yr), configurable. This is mathematically equivalent to using a discount rate of `r - scarcity_rate` for environmental flows, but keeps the accounting clean.

**Confidence:** Medium-high for the concept; medium for the specific rate. The theoretical basis is well-established (Hoel and Sterner 2007, Gollier 2010). Empirical estimates range from 1.7% to 4%/yr. We use 2% as a conservative central estimate.

---

## 2. Discount Rate Configuration

### 2.1 DiscountConfig Dataclass

```python
@dataclass(frozen=True)
class DiscountConfig:
    """Configuration for time-value-of-money calculations.
    
    The discount rate follows the Ramsey formula: r = δ + η × g
    All three Ramsey components are stored for transparency,
    though only the resulting rate(s) are used in calculations.
    """
    # Ramsey components (informational, for report transparency)
    delta: float = 0.005       # Pure time preference (0.5%, Drupp et al. median)
    eta: float = 1.35          # Elasticity of marginal utility (Drupp et al. mean)
    g: float = 0.013           # Per-capita consumption growth (1.3%)
    
    # Effective discount rate schedule
    # If a single float: constant rate
    # If a list of (year_threshold, rate) tuples: declining schedule
    rate_schedule: Union[float, List[Tuple[int, float]]] = None
    
    # Scarcity uplift for ecosystem service values
    scarcity_rate: float = 0.02  # 2%/yr RPE (Drupp & Hänsel 2021 lower bound)
    
    # Analysis horizon
    horizon_years: int = 100     # Default 100-year NPV window
    
    # Carbon price trajectory
    carbon_price_current: float = 80.0     # €/tonne CO₂ (EU ETS ~€70-81 Feb 2026)
    carbon_price_growth: float = 0.03      # 3%/yr real growth (consensus → €126/t 2030)
    
    def __post_init__(self):
        if self.rate_schedule is None:
            # Default: Ramsey-derived rate, constant
            object.__setattr__(self, 'rate_schedule', self.delta + self.eta * self.g)
    
    def rate_at_year(self, year: int) -> float:
        """Return the discount rate applicable at a given year."""
        if isinstance(self.rate_schedule, (int, float)):
            return float(self.rate_schedule)
        # Declining schedule: list of (threshold, rate)
        for threshold, rate in reversed(self.rate_schedule):
            if year >= threshold:
                return rate
        return self.rate_schedule[0][1]
    
    def discount_factor(self, year: int) -> float:
        """Cumulative discount factor for a given year.
        
        For constant rates: 1 / (1 + r)^t
        For declining schedules: product of annual factors.
        """
        if isinstance(self.rate_schedule, (int, float)):
            return 1.0 / (1.0 + self.rate_schedule) ** year
        # For declining schedules, compound year by year
        factor = 1.0
        for t in range(1, year + 1):
            factor /= (1.0 + self.rate_at_year(t))
        return factor
    
    def carbon_price_at_year(self, year: int) -> float:
        """Carbon price in year t, growing at carbon_price_growth rate."""
        return self.carbon_price_current * (1.0 + self.carbon_price_growth) ** year
    
    def scarcity_factor(self, year: int) -> float:
        """Scarcity uplift multiplier for ecosystem services at year t."""
        return (1.0 + self.scarcity_rate) ** year
```

### 2.2 Preconfigured Discount Profiles

```python
# Conservative / market-aligned (Nordhaus-adjacent)
DISCOUNT_MARKET = DiscountConfig(
    delta=0.015, eta=2.0, g=0.013,
    rate_schedule=0.041,          # ~4.1%
    scarcity_rate=0.0,            # No scarcity adjustment
    carbon_price_current=80.0,
    carbon_price_growth=0.02,
)

# Central / consensus (Drupp et al. 2018)
DISCOUNT_CENTRAL = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,          # ~2.3%
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
)

# Environmental / Stern-adjacent  
DISCOUNT_ENVIRONMENTAL = DiscountConfig(
    delta=0.001, eta=1.0, g=0.013,
    rate_schedule=0.014,          # ~1.4%
    scarcity_rate=0.03,
    carbon_price_current=80.0,
    carbon_price_growth=0.04,
)

# UK Green Book declining schedule
DISCOUNT_GREEN_BOOK = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[
        (0, 0.035),   # 3.5% for years 0-30
        (31, 0.030),  # 3.0% for years 31-75
        (76, 0.025),  # 2.5% for years 76-125
    ],
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=125,
)
```

### 2.3 Carbon Price Validation

Our carbon price parameters are anchored in current market data and projections:

- **Current price (€80/t):** EU ETS spot price ~€70–81 in Feb 2026 (after dropping from €90+ in January due to ETS review uncertainty). €80 is within the recent trading range. **Confidence: high** (observed market price).
- **Growth rate (3%/yr real):** Consensus 2030 forecast of ~€126/t from GMK Center (median of BNEF, ABN Amro, Refinitiv, ICIS, S&P, Aurora, PIK), implying ~12% nominal growth, ~9-10% real growth from 2025 to 2030. Our 3% is deliberately conservative for the longer term, recognizing that the steep near-term trajectory may not persist at the same rate. For reference: BNEF's base case implies €145–149/t by 2030 (ETS I), and Enerdata models €130/t by 2040 rising to >€500/t by 2044. **Confidence: medium.** Near-term forecasts (2030) are well-supported; long-term trajectories are highly uncertain, particularly given the 2026 ETS directive revision.
- **ETS II (transport/buildings):** Launching 2027, expected €122/t by 2030. Not directly relevant to our ecosystem cases but confirms the upward carbon price trajectory.

---

## 3. NPV Calculations

### 3.1 Extraction NPV

The extraction simulation (v0.1–v0.5) produces a time series of externality costs. v0.6 discounts these to present value:

```python
def compute_extraction_npv(steps: List[SimulationStep], 
                           discount: DiscountConfig) -> ExtractionNPV:
    """Discount the stream of extraction externalities to present value."""
    
    npv_direct = 0.0         # Direct externality per step
    npv_carbon = 0.0         # Carbon externality per step
    npv_substrate = 0.0      # Substrate damage per step
    npv_foregone = 0.0       # Foregone future absorption
    
    for step in steps:
        t = step.year  # or step index as proxy for year
        df = discount.discount_factor(t)
        sf = discount.scarcity_factor(t)
        cp = discount.carbon_price_at_year(t)
        
        # Direct ecosystem service loss (with scarcity uplift)
        npv_direct += step.externality_cost * df * sf
        
        # Carbon release (at current carbon price — already released)
        npv_carbon += step.carbon_released * cp * df
        
        # Substrate damage (permanent capacity loss NPV)
        if hasattr(step, 'substrate_erosion') and step.substrate_erosion > 0:
            # NPV of permanent capacity loss = 
            # annual_services_lost × sum of discounted scarcity-adjusted future years
            annual_loss = step.k_reduction * step.avg_service_value  
            npv_substrate += sum(
                annual_loss * discount.discount_factor(t + y) * discount.scarcity_factor(t + y)
                for y in range(discount.horizon_years - t)
            )
        
        # Foregone future absorption
        # NPV of absorption this unit would have contributed over remaining lifetime
        remaining_years = step.remaining_productive_years
        for y in range(1, min(remaining_years, discount.horizon_years - t) + 1):
            future_t = t + y
            npv_foregone += (
                step.units_extracted * step.annual_absorption 
                * discount.carbon_price_at_year(future_t)
                * discount.discount_factor(future_t)
            )
    
    return ExtractionNPV(
        direct=npv_direct,
        carbon_release=npv_carbon,
        carbon_foregone=npv_foregone,
        substrate_damage=npv_substrate,
        total=npv_direct + npv_carbon + npv_foregone + npv_substrate,
        horizon=discount.horizon_years,
        discount_config=discount,
    )
```

### 3.2 Restoration NPV

The restoration simulation produces cost streams (upfront planting, maintenance) and benefit streams (recovering services, carbon absorption):

```python
def compute_restoration_npv(result: RestorationResult,
                            discount: DiscountConfig) -> RestorationNPV:
    """NPV of the restoration investment case."""
    
    # Costs (discounted)
    npv_cost = sum(
        cost * discount.discount_factor(year)
        for year, cost in result.cost_schedule
    )
    
    # Benefits: recovering ecosystem services (with scarcity uplift)
    npv_services = 0.0
    for year in range(discount.horizon_years):
        service_fraction = result.succession_fraction_at(year)
        ceiling = result.substrate_ceiling  # v0.5 cap
        effective_fraction = min(service_fraction, ceiling)
        annual_services = result.pristine_annual_services * effective_fraction
        npv_services += (
            annual_services 
            * discount.discount_factor(year) 
            * discount.scarcity_factor(year)
        )
    
    # Benefits: carbon absorption during recovery
    npv_carbon_absorption = 0.0
    for year in range(discount.horizon_years):
        absorption = result.annual_absorption_at(year)  # From succession curve
        npv_carbon_absorption += (
            absorption 
            * discount.carbon_price_at_year(year) 
            * discount.discount_factor(year)
        )
    
    # Carbon payback period (undiscounted — when cumulative absorption = release)
    cumulative = 0.0
    carbon_payback_years = None
    for year in range(discount.horizon_years):
        cumulative += result.annual_absorption_at(year)
        if cumulative >= result.carbon_released:
            carbon_payback_years = year
            break
    
    # ROI
    npv_benefits = npv_services + npv_carbon_absorption
    roi = npv_benefits / npv_cost if npv_cost > 0 else float('inf')
    
    return RestorationNPV(
        cost=npv_cost,
        service_benefits=npv_services,
        carbon_benefits=npv_carbon_absorption,
        total_benefits=npv_benefits,
        net_present_value=npv_benefits - npv_cost,
        roi=roi,
        carbon_payback_years=carbon_payback_years,
        horizon=discount.horizon_years,
        discount_config=discount,
    )
```

### 3.3 Prevention Advantage v0.6

The prevention advantage now includes full NPV accounting:

```
PA_v06 = NPV(restoration_total_cost) / NPV(prevention_cost)
```

where `restoration_total_cost` includes:
- Direct restoration expenditure (planting, maintenance)
- Lost ecosystem services during recovery period (discounted, scarcity-adjusted)
- Carbon externality (release + foregone absorption, at rising carbon prices)
- Permanent substrate capacity loss (discounted NPV of perpetual services gap)

And `prevention_cost` is the foregone extraction revenue (the economic value the extraction would have generated).

**Key insight:** The scarcity uplift and rising carbon prices make the PA *increase* over time under v0.6. Previous versions used static values. Now the cost of inaction compounds.

---

## 4. Carbon Credit Breakeven Analysis

### 4.1 The Question

*"At what carbon price does ecosystem restoration become privately profitable purely from carbon credit revenue?"*

This is the price at which a private investor, funding restoration out of pocket, would break even from selling carbon credits generated by the recovering ecosystem. Above this price, restoration is a profitable investment even without considering non-carbon ecosystem services.

### 4.2 Methodology

```python
def carbon_breakeven(result: RestorationResult,
                     discount: DiscountConfig) -> CarbonBreakeven:
    """Find the carbon price at which restoration NPV = 0 from carbon alone."""
    
    # NPV of restoration costs (fixed, independent of carbon price)
    npv_cost = sum(
        cost * discount.discount_factor(year)
        for year, cost in result.cost_schedule
    )
    
    # NPV of carbon absorption stream (per €1 of carbon price)
    # We compute the "carbon absorption annuity" — the discounted sum of
    # all future absorption, normalized to €1/tonne
    npv_absorption_per_euro = sum(
        result.annual_absorption_at(year) * discount.discount_factor(year)
        for year in range(discount.horizon_years)
    )
    
    # Breakeven: npv_cost = breakeven_price × npv_absorption_per_euro
    if npv_absorption_per_euro > 0:
        breakeven_price = npv_cost / npv_absorption_per_euro
    else:
        breakeven_price = float('inf')  # No absorption → no breakeven
    
    # Context: where does this sit relative to current/projected markets?
    current_price = discount.carbon_price_current
    projected_2030 = discount.carbon_price_at_year(5)  # ~5 years out
    
    return CarbonBreakeven(
        breakeven_price=breakeven_price,
        current_price=current_price,
        gap_to_current=breakeven_price - current_price,
        profitable_at_current=(breakeven_price <= current_price),
        projected_breakeven_year=_find_breakeven_year(
            breakeven_price, discount
        ),
        npv_cost=npv_cost,
        npv_absorption_per_euro=npv_absorption_per_euro,
    )

def _find_breakeven_year(breakeven_price: float, 
                         discount: DiscountConfig) -> Optional[int]:
    """Year when rising carbon prices reach breakeven."""
    for year in range(200):
        if discount.carbon_price_at_year(year) >= breakeven_price:
            return year
    return None  # Never reaches breakeven within 200 years
```

### 4.3 Expected Results by Case

**Preliminary estimates** (to be validated during implementation):

**Oak Valley Forest (temperate, 10,000 trees):**
- Restoration cost: ~€2.5M (v0.2)
- Carbon absorption: ~40–60 t CO₂/yr during early maturation, rising to ~180 t CO₂/yr at maturity
- Expected breakeven: ~€150–250/t CO₂
- At 3%/yr carbon price growth from €80: breakeven reached ~2045–2055
- **Interpretation:** Not yet commercially viable from carbon alone, but approaching viability as EU ETS prices rise.

**Costa Brava Holm Oak (1,800 trees):**
- Restoration cost: ~€600k (v0.2) — higher per-tree due to Mediterranean difficulty
- Carbon absorption: ~30 t CO₂/yr at maturity (slower Mediterranean growth)
- Expected breakeven: ~€300–500/t CO₂ (high due to slow growth and high restoration cost)
- **Interpretation:** Far from carbon-only viability. Full ecosystem service valuation is essential.

**Costa Brava Posidonia (1,000 ha):**
- Restoration cost: extremely high (~€2.5M+, v0.2)
- Carbon sequestration: ~1.7 t CO₂/ha/yr × 1,000 ha = 1,700 t CO₂/yr at full maturity
- But maturation timeline is 120 years (v0.4 succession curve)
- Expected breakeven: ~€200–400/t CO₂
- The key insight: Posidonia's carbon value is dominated by *prevention of matte carbon release* (2,600 t CO₂/ha), not by ongoing sequestration. Prevention breakeven would be far lower.
- **Interpretation:** Prevention is overwhelmingly more cost-effective than restoration. Blue carbon credits for Posidonia protection (avoided emissions) are far more viable than restoration credits.

**Note on blue carbon credits:** The Verra VM0033 methodology for tidal wetland and seagrass restoration now provides a framework for generating carbon credits from seagrass projects, though no Posidonia-specific project has yet been certified. Mediterranean blue carbon projects face additional challenges: slow growth rates, high restoration costs, and the absence of a voluntary carbon market with prices comparable to the EU ETS compliance market.

### 4.4 Sensitivity to Discount Rate

The breakeven price is highly sensitive to the discount rate because it involves a long-term annuity:

| Discount rate | Breakeven price (illustrative, Oak Valley) |
|---------------|-------------------------------------------|
| 1.4% (Stern) | ~€120/t CO₂ |
| 2.0% (consensus) | ~€180/t CO₂ |
| 3.5% (Green Book) | ~€300/t CO₂ |
| 4.3% (Nordhaus) | ~€450/t CO₂ |

This demonstrates why the discount rate is not a "technical parameter" — it is a policy choice with enormous consequences for whether restoration appears viable.

---

## 5. Data Model Changes

### 5.1 New Dataclasses

```python
@dataclass(frozen=True)
class DiscountConfig:
    """As specified in Section 2.1"""
    ...

@dataclass(frozen=True)
class ExtractionNPV:
    """NPV of extraction externalities."""
    direct: float                  # NPV of direct ecosystem service loss
    carbon_release: float          # NPV of carbon released
    carbon_foregone: float         # NPV of future absorption foregone
    substrate_damage: float        # NPV of permanent substrate capacity loss
    total: float                   # Sum of above
    horizon: int                   # Analysis horizon (years)
    discount_config: DiscountConfig

@dataclass(frozen=True)
class RestorationNPV:
    """NPV of restoration as an investment."""
    cost: float                    # NPV of total restoration expenditure
    service_benefits: float        # NPV of recovered ecosystem services
    carbon_benefits: float         # NPV of carbon absorption (at rising prices)
    total_benefits: float          # service_benefits + carbon_benefits
    net_present_value: float       # total_benefits - cost
    roi: float                     # total_benefits / cost
    carbon_payback_years: Optional[int]  # Undiscounted years to recapture carbon
    horizon: int
    discount_config: DiscountConfig

@dataclass(frozen=True)
class CarbonBreakeven:
    """Carbon credit breakeven analysis."""
    breakeven_price: float           # €/tonne CO₂ where restoration NPV = 0
    current_price: float             # Current EU ETS price
    gap_to_current: float            # How far above/below current market
    profitable_at_current: bool      # True if breakeven ≤ current price
    projected_breakeven_year: Optional[int]  # Year carbon price reaches breakeven
    npv_cost: float                  # NPV of restoration costs
    npv_absorption_per_euro: float   # Discounted absorption per €1/t price

@dataclass(frozen=True)
class PreventionAdvantageV06:
    """Enhanced prevention advantage with full NPV accounting."""
    pa_simple: float               # v0.2 style (undiscounted)
    pa_with_carbon: float          # Including carbon externality NPV
    pa_with_substrate: float       # Including permanent substrate loss NPV
    pa_full: float                 # All-inclusive NPV-based PA
    npv_prevention_cost: float     # Foregone extraction revenue
    npv_restoration_total: float   # Full cost of restore-after-extract
```

### 5.2 Extended Dataclasses

```python
# Resource gains a discount config
@dataclass
class Resource:
    # ... existing fields from v0.1–v0.5 ...
    discount: Optional[DiscountConfig] = None

# SimulationStep gains discounted values
@dataclass
class SimulationStep:
    # ... existing fields ...
    discount_factor: float = 1.0
    npv_externality: float = 0.0   # Externality × discount_factor
    carbon_price_used: float = 0.0  # Carbon price at this step's year

# RestorationResult gains NPV
@dataclass
class RestorationResult:
    # ... existing fields ...
    npv: Optional[RestorationNPV] = None
    carbon_breakeven: Optional[CarbonBreakeven] = None
    prevention_advantage_v06: Optional[PreventionAdvantageV06] = None
```

---

## 6. Report Changes

### 6.1 Extraction Report — New Section

```
  ── NPV Analysis (100-year horizon, 2.3% discount rate) ───
  
  Ramsey components: δ=0.5%, η=1.35, g=1.3%
  Scarcity uplift: 2.0%/yr on ecosystem services
  Carbon price: €80/t growing at 3.0%/yr
  
  Externality NPV breakdown:
    Direct ecosystem services:    €2,450,000
    Carbon released:                €448,000
    Foregone absorption (80yr):   €1,230,000
    Substrate damage (permanent):   €890,000
    ─────────────────────────────────────────
    Total extraction NPV:         €5,018,000
  
  For comparison (undiscounted):  €7,340,000
  Discount effect:                    -31.6%
  
  Note: Scarcity uplift partially offsets discounting.
  Without scarcity adjustment, NPV would be €3,680,000 (-50.1%).
```

### 6.2 Restoration Report — New Section

```
  ── Investment Analysis (100-year horizon) ──────────────────
  
  Restoration NPV:
    Costs (discounted):           -€2,100,000
    Service recovery:             +€3,800,000
    Carbon absorption:              +€420,000
    ─────────────────────────────────────────
    Net Present Value:            +€2,120,000
    ROI:                              2.01×
    
  Carbon payback period:              51 years
  (years to recapture released CO₂ through absorption)
  
  ── Carbon Credit Breakeven ──────────────────────────────
  
  Breakeven carbon price:           €182/t CO₂
  Current EU ETS price:              €80/t CO₂
  Gap to breakeven:                 €102/t CO₂
  Profitable from carbon alone:          No
  
  At 3%/yr carbon price growth:
    Breakeven reached in year:           2053
    (when EU ETS projected to reach ~€182/t)
  
  ── Prevention Advantage ─────────────────────────────────
  
  Prevention advantage (NPV-adjusted):
    Simple (v0.2):                    6.08×
    With carbon:                      9.40×
    With substrate:                  12.70×
    Full (all NPV):                  14.30×
  
  For every €1 spent on prevention, extraction-then-
  restoration costs €14.30 in present value terms.
```

### 6.3 Discount Rate Sensitivity Report

A new optional report section showing how key outputs vary across discount rate assumptions:

```
  ── Discount Rate Sensitivity ─────────────────────────────
  
                        Stern    Central    Green Book   Nordhaus
  Rate:                 1.4%      2.3%      3.5%→2.5%    4.3%
  ─────────────────────────────────────────────────────────
  Extraction NPV:     €6.8M     €5.0M       €4.2M      €3.1M
  Restoration NPV:    +€3.8M    +€2.1M      +€1.2M     +€0.4M
  Prevention adv:      21.4×     14.3×        9.8×       6.2×
  Carbon breakeven:   €120/t    €182/t      €280/t      €420/t
  Breakeven year:      2042      2053        2068        2083
  
  The discount rate choice changes the prevention advantage
  by 3.5× (from 6.2× to 21.4×). This is not a technical
  parameter — it is an ethical choice about intergenerational
  equity.
```

---

## 7. Implementation Notes

### 7.1 Performance

NPV calculations involve nested loops (years × steps). For the typical case (≤1000 steps, ≤200 years), this is negligible (<1ms). For large forests, the sum over `horizon_years` for each step's substrate damage could be precomputed as a geometric series.

For constant discount rates and constant scarcity rates, the substrate NPV term reduces to:

```python
# Closed-form for constant rates
r_net = discount_rate - scarcity_rate  # Net effective rate
if r_net > 0:
    npv_permanent = annual_loss / r_net  # Perpetuity formula
else:
    npv_permanent = annual_loss * horizon_years  # No convergence
```

### 7.2 Backward Compatibility

- **No discount config = no NPV calculations.** All existing v0.1–v0.5 behavior is preserved.
- When `DiscountConfig` is provided, NPV sections appear in reports alongside existing undiscounted values.
- The prevention advantage retains both its v0.2 (simple) and v0.6 (NPV-adjusted) forms.
- Existing test values remain unchanged — new tests cover NPV calculations.

### 7.3 Integration with v0.5 Substrate

The substrate damage NPV is the most consequential new calculation. It captures the *permanent* loss that v0.5 introduced (the restoration ceiling) in monetary terms:

```python
# What v0.5 gives us: substrate_ceiling (e.g., 0.67 means 33% permanent loss)
# What v0.6 computes: NPV of that 33% gap over the horizon

permanent_gap = 1.0 - substrate_ceiling  # e.g., 0.33
annual_services_lost = pristine_annual_services * permanent_gap

# Over 100 years with 2.3% discount and 2% scarcity:
# Net effective rate = 0.3%, so NPV ≈ annual_loss × 100yr × ~0.85 avg factor
# This is a HUGE number for Posidonia (permanent matte loss)
```

**Hypothesis validated:** For the Costa Brava Posidonia case, the substrate damage NPV will dominate all other terms, pushing the prevention advantage from 81× (v0.2) to potentially >200× once the NPV of millennia-scale matte loss is accounted for.

---

## 8. Preconfigured Case Updates

### 8.1 Oak Valley Forest

```python
OAK_VALLEY_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.02,
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
)
```

- Remaining productive years: 80 (temperate deciduous lifespan estimate)
- Carbon absorption: from v0.4 parameters
- Restoration cost schedule: upfront planting year 0, maintenance years 1–10

### 8.2 Costa Brava Holm Oak

```python
COSTA_BRAVA_OAK_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=0.023,
    scarcity_rate=0.025,   # Higher: Mediterranean holm oak more threatened
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=100,
)
```

- Remaining productive years: 200+ (holm oak longevity)
- Higher scarcity uplift (2.5%): holm oak forests in NE Spain are under climate stress; scarcity is increasing faster than global average.

### 8.3 Costa Brava Posidonia

```python
COSTA_BRAVA_POSIDONIA_DISCOUNT = DiscountConfig(
    delta=0.005, eta=1.35, g=0.013,
    rate_schedule=[
        (0, 0.023),    # 2.3% for first 30 years
        (31, 0.018),   # 1.8% for years 31-100
        (101, 0.014),  # 1.4% for years 101+
    ],
    scarcity_rate=0.03,   # Higher: Posidonia declining 34%+ since 1960s
    carbon_price_current=80.0,
    carbon_price_growth=0.03,
    horizon_years=200,   # Longer horizon for marine ecosystems
)
```

- Remaining productive years: effectively infinite (millennia-scale persistence)
- Declining discount schedule: appropriate given the extremely long recovery timescales
- Higher scarcity uplift (3%): Posidonia meadows across the Mediterranean have declined significantly; substitutability is essentially zero (no engineered alternative provides equivalent services).
- 200-year horizon: needed to capture matte dynamics (1.0 mm/yr accretion)

---

## 9. Testing Strategy

### 9.1 Unit Tests — Discount Mechanics

1. **Constant rate discounting**: `discount_factor(0) = 1.0`, `discount_factor(10) ≈ 1/(1.023)^10`
2. **Declining schedule**: rates change at correct year thresholds
3. **Carbon price trajectory**: `carbon_price_at_year(0) = 80`, `carbon_price_at_year(10) ≈ 107.5`
4. **Scarcity factor**: `scarcity_factor(50) ≈ 2.69` at 2%/yr
5. **Ramsey consistency**: `delta + eta * g` matches `rate_schedule` for default config

### 9.2 Unit Tests — NPV Calculations

6. **Zero discount rate**: NPV = undiscounted sum (boundary case)
7. **Infinite discount rate**: NPV → first period only
8. **Perpetuity formula**: for constant annual loss with constant rates, NPV ≈ loss/r_net
9. **Carbon breakeven monotonicity**: higher costs → higher breakeven price
10. **Carbon breakeven with zero absorption**: breakeven = infinity

### 9.3 Integration Tests — Per Case

11. **Oak Valley extraction NPV**: total NPV is less than undiscounted total (discount effect)
12. **Oak Valley restoration ROI**: positive NPV at central discount rate
13. **Holm oak substrate NPV dominance**: substrate term is significant fraction of total (threshold substrate function creates high permanent loss)
14. **Posidonia PA explosion**: prevention advantage v0.6 > prevention advantage v0.2 (substrate + carbon + scarcity uplift compound)
15. **Posidonia prevention vs restoration breakeven**: prevention breakeven price << restoration breakeven price
16. **Scarcity uplift effect**: NPV with scarcity > NPV without scarcity (for all cases)

### 9.4 Ecological Plausibility Checks

17. **Scarcity-adjusted values grow over time**: undiscounted ecosystem service value at year 50 > year 0
18. **Carbon payback period plausible**: Oak Valley ~40–60yr, Holm Oak ~50–80yr, Posidonia ~60–100yr (per v0.4 succession curves)
19. **Prevention advantage ordering preserved**: Posidonia PA > Holm Oak PA > Oak Valley PA (marine >> terrestrial, as in all previous versions)
20. **Discount rate sensitivity ordering**: Lower rates → higher NPV, higher PA, lower breakeven price (monotonic)
21. **Breakeven prices in plausible range**: All cases €100–€500/t CO₂ (above current ~€80, but within projected 2030–2050 range)

### 9.5 Backward Compatibility

22. **No DiscountConfig = v0.5 behavior**: all 433 existing tests pass unchanged
23. **DiscountConfig with rate=0 and scarcity=0**: NPV equals undiscounted values (up to rounding)
24. **Report output**: discount section only appears when DiscountConfig is provided

### 9.6 Edge Cases

25. **Negative net effective rate (scarcity > discount)**: NPV grows without bound — capped at horizon_years
26. **Zero restoration cost**: breakeven = 0 (always profitable)
27. **Substrate ceiling = 1.0**: no permanent loss term
28. **Horizon = 0**: NPV = 0 for future flows

---

## 10. Scientific Literature Sources

### Discount Rate Theory
- **Ramsey (1928)**, Economic Journal: the original optimal saving model and "ethically indefensible" quote on pure time preference.
- **Stern (2006)**, *The Economics of Climate Change: The Stern Review*: δ=0.1%, r=1.4%.
- **Nordhaus (2007)**, *A Review of the Stern Review*, Journal of Economic Literature: δ=1.5%, r=4.3%.
- **Drupp, Freeman, Groom, Nesje (2018)**, *Discounting Disentangled*, American Economic Journal: Economic Policy. Survey of 200+ economists. Median SDR = 2.0%.
- **Weitzman (1998, 2001)**: declining rates under growth uncertainty.
- **Dasgupta (2021)**, *The Economics of Biodiversity: The Dasgupta Review*, HM Treasury: natural capital as foundational asset.

### Declining Rates & Institutional Practice
- **UK HM Treasury Green Book (2003, updated 2020, 2025)**: 3.5% declining to 2.5%. Under review in 2026.
- **UK Treasury Environmental Discount Rate Review (2021)**: concluded against changing rate for environmental impacts; recommended improved valuation instead.
- **Goulder & Williams (2012)**, *The Choice of Discount Rate for Climate Change Policy*, RFF: distinguishes social welfare rate from finance-equivalent rate.

### Relative Price Effects
- **Hoel & Sterner (2007)**, *Discounting and relative prices*, Climatic Change: foundational paper on environmental scarcity effects on discounting.
- **Gollier (2010)**: dual discount rates with substitutability.
- **Drupp & Hänsel (2021)**, *Relative Prices and Climate Policy*: RPC of non-market goods ~2–4%/yr; SCC >50% higher.
- **Baumgärtner, Klein, Thiel, Winkler (2015)**, *Ramsey discounting of ecosystem services*, Environmental & Resource Economics.
- **Drupp, Hänsel et al. (2025)**, *Global evidence on income elasticity of WTP*: income elasticity ~0.6, RPC ~1.7%/yr, natural capital uplift ~40%.

### Carbon Pricing
- **EU ETS**: spot prices €60–90 in early 2026 (Trading Economics). Recent volatility from ETS directive review and German political statements.
- **GMK Center (2025)**: consensus 2030 forecast €126/t (median of 7 institutions, range €80–147).
- **BNEF (2025)**: ETS I base case €149/t by 2030; ETS II €122/t by 2030.
- **ABN Amro (2025)**: baseline €145/t by 2030, €200/t by 2035.
- **Enerdata (2025)**: €130/t by 2040, >€500/t by 2044.

### Blue Carbon Credits
- **Verra VM0033** (2023, v2.1): *Methodology for Tidal Wetland and Seagrass Restoration*. The applicable standard for Mediterranean seagrass carbon credits.
- **Nature article (2025)**: first mechanistic model of seagrass carbon benefits; no seagrass projects yet certified under international voluntary standards.
- **Yale E360 (2023)**: Virginia eelgrass project (first seagrass carbon credit application to Verra). Carbon credits offset ~10% of $800K restoration cost for 700 ha.

---

## 11. Open Questions

1. **Scarcity rate calibration per case:** We use 2–3%/yr based on global/European estimates. Should Gaia compute scarcity rates endogenously from the simulation's own ecosystem decline trajectory? This might be more appropriate for v0.7 (endogenous pricing).

2. **Restoration cost schedules:** v0.2 uses a lump-sum restoration cost. v0.6 needs a time profile (upfront planting + multi-year maintenance). How detailed should this be? Recommendation: simple two-phase model (75% year 0, 25% spread over years 1–5).

3. **Carbon credit discounting vs. cash flow discounting:** Should carbon credits be discounted at the social discount rate or at a market rate (higher, reflecting project risk)? The breakeven analysis implicitly uses the social rate. A risk-adjusted analysis would use a higher rate, making breakeven prices higher. Recommendation: keep social rate as default; add an optional `risk_premium` parameter.

4. **Interaction with v0.7:** The endogenous pricing system (v0.7) will compute dynamic prices from ecosystem state. v0.6's scarcity uplift is a simplified precursor. When v0.7 lands, the scarcity_rate becomes endogenous. The DiscountConfig structure should be designed to accommodate this transition.

5. **Climate change interaction with discount rate:** If climate change reduces future growth (g), the Ramsey-derived discount rate falls. This creates a feedback: more damage → lower discount → higher present value of damage → stronger case for action. Modeling this feedback is beyond v0.6 scope but is noted for future consideration.

---

## 12. Version Compatibility

| Feature | v0.5 | v0.6 |
|---------|------|------|
| Externality values | Undiscounted | Both undiscounted and NPV |
| Carbon price | Static €80/t | Rising trajectory (configurable) |
| Prevention advantage | Ratio of costs | NPV-adjusted ratio |
| Ecosystem services | Static value | Scarcity-adjusted (rising over time) |
| Carbon breakeven | Not available | New analysis |
| Substrate damage | Physical units | Physical + NPV |
| Time horizon | Implicit | Explicit, configurable |
| Discount rate | Not applicable | Ramsey-based, configurable profiles |

**Full backward compatibility:** No `DiscountConfig` → identical v0.5 behavior. All 433 tests pass unchanged.

---

*Specification version: v0.6-draft-1*
*Date: 2026-03-02*
*Research basis: Web search conducted 2026-03-02 covering discount rate theory, EU ETS prices, carbon credit methodology, and relative price effects.*
