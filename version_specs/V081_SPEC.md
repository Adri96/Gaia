# Gaia v0.8.1 — I/O Flexibility

## Overview

v0.8.1 improves CLI ergonomics and adds structured JSON output for programmatic consumption. All changes are backward-compatible: existing CLI invocations continue to work via deprecated aliases, and the default output format remains human-readable text.

---

## Part 1: CLI Input Parameter Improvements

### 1.1 `--units` replaces `--cut` / `--destroy`

The `--cut` flag (forest cases) and `--destroy` flag (posidonia) implied destruction even in restoration mode. Replaced with mode-agnostic `--units`:

| Case | Old flag | New flag | Default |
|------|----------|----------|---------|
| forest | `--cut` | `--units` | 5,000 |
| costa_brava | `--cut` | `--units` | 4,000 |
| posidonia | `--destroy` | `--units` | 2,000 |
| amazon_forest | `--cut` | `--units` | 80,000 |

**Backward compatibility**: `--cut` and `--destroy` are still accepted as hidden aliases. When used, they emit a `DeprecationWarning` to stderr and work identically to `--units`.

### 1.2 `--unit-value` replaces `--tree-value` / `--revenue`

Consistent naming across all cases for the per-unit private revenue parameter:

| Case | Old flag | New flag | Default |
|------|----------|----------|---------|
| forest | `--tree-value` | `--unit-value` | 100.0 |
| costa_brava | `--tree-value` | `--unit-value` | 60.0 |
| posidonia | `--revenue` | `--unit-value` | 2,500.0 |
| amazon_forest | `--tree-value` | `--unit-value` | 1.50 |

**Backward compatibility**: Old flags are hidden aliases with `DeprecationWarning`.

### 1.3 Warnings for mode-irrelevant parameters

Restoration-only parameters (`--planting-cost`, `--maintenance-cost`, `--maintenance-years`, `--time-horizon`) now emit a `UserWarning` to stderr when passed in extraction mode:

```
--planting-cost is only used in restore mode (--mode restore). Ignored in extraction mode.
```

### 1.4 New flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--format` | `text`, `json` | `text` | Output format |
| `--output FILE` | file path | stdout | Write output to file |
| `--with-pricing` | flag | disabled | Enable v0.7 endogenous pricing |
| `--summary-only` | flag | disabled | Omit per-step data from JSON |

### 1.5 Migration guide

```bash
# Old (still works, with deprecation warning):
python -m gaia.cases.forest --trees 10000 --cut 5000 --tree-value 100

# New:
python -m gaia.cases.forest --trees 10000 --units 5000 --unit-value 100

# JSON output:
python -m gaia.cases.forest --units 5000 --format json

# JSON to file:
python -m gaia.cases.forest --units 5000 --format json --output result.json

# With pricing:
python -m gaia.cases.forest --units 5000 --format json --with-pricing

# Summary only (no per-step data):
python -m gaia.cases.forest --units 5000 --format json --summary-only
```

---

## Part 2: JSON Output Schema

### 2.1 Top-level structure

Every JSON output contains:

```json
{
  "gaia_version": "0.8.1",
  "mode": "extraction" | "restoration",
  "ecosystem": { ... },
  "summary": { ... },
  "steps": [ ... ],
  ...optional sections...
}
```

### 2.2 Extraction mode schema

```json
{
  "gaia_version": "string — Gaia version that produced this output",
  "mode": "extraction",

  "ecosystem": {
    "name": "string — ecosystem name",
    "resource": {
      "name": "string",
      "total_units": "int — total extractable units",
      "safe_threshold_ratio": "float — 0.0 to 1.0",
      "safe_threshold_units": "int — total_units * safe_threshold_ratio",
      "unit_value": "float — revenue per unit extracted (euros)",
      "has_carbon_profile": "bool",
      "has_substrate": "bool",
      "has_discount": "bool",
      "substrate_type": "string — only if has_substrate",
      "discount_rate": "float — only if has_discount",
      "discount_horizon_years": "int — only if has_discount",
      "carbon_stored_per_unit": "float — only if has_carbon_profile",
      "carbon_absorption_per_unit_yr": "float — only if has_carbon_profile",
      "carbon_price_per_tonne": "float — only if has_carbon_profile"
    },
    "agents": [
      {
        "name": "string",
        "dependency_weight": "float — 0.0 to 1.0, all agents sum to 1.0",
        "monetary_rate": "float — max cost at full damage (euros)",
        "description": "string",
        "trophic_level": "int — -1=abiotic, 0=producer, 1-3=consumers",
        "is_keystone": "bool",
        "keystone_threshold": "float | null — only if is_keystone"
      }
    ],
    "interactions": [
      {
        "source": "string — agent name",
        "target": "string — agent name",
        "strength": "float — 0.0 to 1.0",
        "interaction_type": "string — dependency/trophic/keystone/competition",
        "description": "string"
      }
    ],
    "has_pricing": "bool — whether endogenous pricing was enabled"
  },

  "summary": {
    "total_units_extracted": "int",
    "total_private_revenue": "float — euros",
    "total_externality_cost": "float — euros",
    "net_social_cost": "float — revenue minus externality (negative = society lost)",
    "final_ecosystem_health": "float — 0.0 (collapsed) to 1.0 (pristine)",
    "num_steps": "int — number of simulation steps"
  },

  "steps": [
    {
      "step": "int — 1-indexed",
      "units_extracted": "int — cumulative",
      "depletion_ratio": "float",
      "marginal_cost": "float — externality of this unit only",
      "cumulative_cost": "float — total externality so far",
      "private_revenue": "float — cumulative revenue",
      "ecosystem_health": "float — 0.0 to 1.0",
      "agent_damages": { "agent_name": "float 0.0-1.0" },
      "agent_costs": { "agent_name": "float euros" },
      "resilience_zone": "string — green/yellow/red",
      "model_confidence": "float — 0.0 to 1.0",

      "— optional per-step fields (present when applicable) —": "",
      "agent_direct_damages": { "agent_name": "float" },
      "agent_cascade_damages": { "agent_name": "float" },
      "keystone_triggered": ["string — agent names"],
      "irreversibility_warning": "bool",
      "substrate_erosion": "float",
      "effective_k": "int",
      "k_fraction": "float",
      "discount_factor": "float",
      "npv_externality": "float",
      "carbon_price_used": "float",
      "agent_prices": { "agent_name": "float euros" }
    }
  ],

  "npv_analysis": {
    "direct": "float — NPV of direct ecosystem service loss",
    "carbon_release": "float — NPV of carbon released",
    "carbon_foregone": "float — NPV of future absorption lost",
    "substrate_damage": "float — NPV of permanent substrate loss",
    "total": "float — sum of all components",
    "horizon": "int — analysis horizon in years"
  },

  "pricing": {
    "prices": { "agent_name": "float euros" },
    "scarcity_multipliers": { "agent_name": "float" },
    "demand_multipliers": { "agent_name": "float" },
    "spectral_radius": "float — must be < 1.0",
    "converged": "bool",
    "iterations": "int"
  },

  "notes": ["string — optional annotations (e.g. marine annual externality warning)"]
}
```

### 2.3 Restoration mode schema

```json
{
  "gaia_version": "string",
  "mode": "restoration",
  "ecosystem": { "...same as extraction..." },

  "restoration_cost": {
    "planting_cost_per_unit": "float — euros",
    "annual_maintenance_per_unit": "float — euros/year",
    "maintenance_years": "int",
    "total_cost_per_unit": "float — planting + (annual * years)"
  },

  "summary": {
    "total_units_restored": "int",
    "total_restoration_cost": "float — euros",
    "total_recovered_value": "float — ecosystem service value recovered",
    "net_restoration_value": "float — recovered minus cost",
    "prevention_advantage": "float — how many times cheaper prevention is",
    "final_ecosystem_health": "float — 0.0 to 1.0",
    "num_steps": "int"
  },

  "steps": [
    {
      "step": "int — 1-indexed",
      "units_restored": "int — cumulative",
      "recovery_ratio": "float",
      "marginal_service_value": "float",
      "cumulative_service_value": "float",
      "restoration_cost_so_far": "float",
      "ecosystem_health": "float",
      "agent_recoveries": { "agent_name": "float 0.0-1.0" },
      "agent_service_values": { "agent_name": "float euros" }
    }
  ],

  "maturation": {
    "years_to_pioneer": "float",
    "years_to_50pct": "float",
    "years_to_90pct": "float",
    "total_maturation_gap": "float — euros lost during succession",
    "timeline": [
      {
        "year": "int",
        "succession_phase": "string — delay/pioneer/intermediate/climax",
        "service_fraction": "float — 0.0 to 1.0",
        "annual_service_value": "float",
        "cumulative_service_value": "float",
        "annual_carbon_absorbed": "float — tonnes CO2",
        "cumulative_carbon_absorbed": "float — tonnes CO2"
      }
    ]
  },

  "substrate": {
    "substrate_ceiling": "float — max recoverable fraction",
    "substrate_recovery_years": "float",
    "prevention_advantage_with_substrate": "float"
  },

  "npv_analysis": {
    "cost": "float — NPV of restoration expenditure",
    "service_benefits": "float — NPV of recovered services",
    "carbon_benefits": "float — NPV of carbon absorption",
    "total_benefits": "float — service + carbon",
    "net_present_value": "float — benefits minus cost",
    "roi": "float — total_benefits / cost",
    "carbon_payback_years": "int | null",
    "horizon": "int"
  },

  "carbon_breakeven": {
    "breakeven_price": "float — euros/tonne where restoration NPV = 0",
    "current_price": "float — current EU ETS price",
    "gap_to_current": "float — breakeven minus current",
    "profitable_at_current": "bool",
    "projected_breakeven_year": "int | null"
  },

  "prevention_advantage_v06": {
    "pa_simple": "float — v0.2-style undiscounted",
    "pa_with_carbon": "float — including carbon NPV",
    "pa_with_substrate": "float — including substrate loss",
    "pa_full": "float — all-inclusive NPV-based",
    "npv_prevention_cost": "float — foregone revenue",
    "npv_restoration_total": "float — full restore-after-extract cost"
  },

  "notes": ["string"]
}
```

### 2.4 Optional sections

Sections are only present when the corresponding feature is configured:

| Section | Present when |
|---------|-------------|
| `npv_analysis` | `DiscountConfig` is set on the resource |
| `pricing` | `PricingConfig` is set and `--with-pricing` is used |
| `maturation` | Restoration with `time_horizon > 0` and succession curve |
| `substrate` | `substrate_ceiling < 1.0` (substrate has degraded) |
| `carbon_breakeven` | Restoration with carbon profile |
| `prevention_advantage_v06` | Restoration with discount config |
| `notes` | Case-specific annotations (e.g. Posidonia marine note) |
| `steps` | Default included; omitted with `--summary-only` |

### 2.5 Precision

| Data type | Decimal places | Example |
|-----------|---------------|---------|
| Currency (euros) | 2 | `1074170.00` |
| Ratios (0-1) | 6 | `0.500000` |
| Multipliers | 4 | `1.2345` |
| Carbon (tonnes) | 4 | `12.4000` |

---

## Part 3: Implementation

### New files
- `gaia/serialization.py` — JSON serialization (pure stdlib, no numpy)
- `gaia/cli.py` — Shared CLI argument definitions and output routing
- `tests/test_serialization.py` — 30 serialization tests
- `tests/test_cli.py` — 21 CLI tests
- `version_specs/V081_SPEC.md` — This document

### Modified files
- `gaia/cases/forest.py` — CLI refactor
- `gaia/cases/costa_brava.py` — CLI refactor
- `gaia/cases/posidonia.py` — CLI refactor + `--destroy`/`--revenue` rename
- `gaia/cases/amazon_forest.py` — CLI refactor

### Test results
- 579 tests pass (510 existing + 30 serialization + 21 CLI + 18 new in existing files)
- All existing tests unchanged — full backward compatibility
