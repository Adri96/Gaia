#!/usr/bin/env python3
"""
Fit the depth → primary production hyperparameters of a case's production
functions (Step 8g.1; gaia.production, DEPTH_MODEL) to the measurements
listed in the case file (``depth_production.data``), and print them with
their uncertainty.

The model is NPP(z) = P_ref · (e^(−k·z) − e^(−k·z_max)) / (e^(−k·z_ref) −
e^(−k·z_max)). The depth limit z_max and the reference depth z_ref are taken
from the case file (z_max from the literature: the data do not reach it);
P_ref and k are fitted by least squares on the logarithm of production
(site-to-site variation is multiplicative): for a given k the best ln P_ref is
the mean of ln(observed / shape), and k minimises the residual sum of
squares (golden-section search). Standard errors and the correlation come
from the Jacobian, σ² = SSE / (n − 2).

The ranges written in the case file:
    P_ref: the 95% prediction interval of a site's production at z_ref,
           ×/÷ exp(1.96 · sqrt(σ² + se(ln P_ref)²)) (an unknown meadow
           varies like the measured sites around the curve), lognormal;
    k:     k ± 1.96 se(k), triangular with its mode at the fit.

Usage:
    python3 scripts/fit_depth_production.py posidonia          # print the fit
    python3 scripts/fit_depth_production.py posidonia --check  # and compare with the file

No third-party dependencies.
"""

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

Z95 = 1.959963984540054


def _shape(z: float, k: float, z_max: float) -> float:
    return math.exp(-k * z) - math.exp(-k * z_max)


def _dlog_shape(z: float, k: float, z_max: float) -> float:
    """d ln(e^(−kz) − e^(−k z_max)) / dk."""
    return (-z * math.exp(-k * z) + z_max * math.exp(-k * z_max)) / _shape(z, k, z_max)


def fit(depths: Sequence[float], values: Sequence[float], z_ref: float, z_max: float) -> Dict[str, float]:
    """Least-squares fit of ln P_ref and k (see the module docstring)."""
    n = len(depths)
    if n < 3:
        raise ValueError("at least 3 measurements are needed to fit 2 hyperparameters")
    logs = [math.log(v) for v in values]

    def best_log_p(k: float) -> float:
        return sum(y - math.log(_shape(z, k, z_max) / _shape(z_ref, k, z_max))
                   for z, y in zip(depths, logs)) / n

    def sse(k: float) -> float:
        lp = best_log_p(k)
        return sum((lp + math.log(_shape(z, k, z_max) / _shape(z_ref, k, z_max)) - y) ** 2
                   for z, y in zip(depths, logs))

    a, b = 1e-6, 1.0
    g = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - g * (b - a), a + g * (b - a)
    for _ in range(200):
        if sse(c) < sse(d):
            b = d
        else:
            a = c
        c, d = b - g * (b - a), a + g * (b - a)
    k = (a + b) / 2.0
    lp = best_log_p(k)
    s2 = sse(k) / (n - 2)
    # Jacobian of the residuals with respect to (ln P_ref, k)
    rows = [(1.0, _dlog_shape(z, k, z_max) - _dlog_shape(z_ref, k, z_max)) for z in depths]
    a11 = sum(r[0] * r[0] for r in rows)
    a12 = sum(r[0] * r[1] for r in rows)
    a22 = sum(r[1] * r[1] for r in rows)
    det = a11 * a22 - a12 * a12
    var_lp, var_k, cov = s2 * a22 / det, s2 * a11 / det, -s2 * a12 / det
    se_lp, se_k = math.sqrt(var_lp), math.sqrt(var_k)
    s_pred = math.sqrt(s2 + var_lp)
    return {
        "n": n, "npp_at_reference_depth": math.exp(lp), "decline_rate": k,
        "se_log_npp_at_reference_depth": se_lp, "se_decline_rate": se_k,
        "correlation": cov / (se_lp * se_k), "residual_sd_log": math.sqrt(s2),
        "prediction_sd_log": s_pred,
        "npp_range": (math.exp(lp - Z95 * s_pred), math.exp(lp + Z95 * s_pred)),
        "decline_rate_range": (k - Z95 * se_k, k + Z95 * se_k),
    }


def fits_of(document: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], Dict[str, float]]]:
    """[(ledger service, its depth_production block, the fit)] of a case
    document; a block without data (its shape borrowed from another
    producer's fit, e.g. the leaf epiphytes', Step 8g.9) is skipped."""
    out = []
    for entry in document.get("service_ledger", []):
        pf = entry.get("production_function") or {}
        depth = pf.get("depth_production")
        if not depth or not depth.get("data"):
            continue
        data = depth["data"]
        result = fit([row["depth_m"] for row in data], [row["value"] for row in data],
                     float(depth["reference_depth_m"]), float(depth["parameters"]["depth_limit"]["value"]))
        out.append((entry["service"], depth, result))
    return out


def main(argv=None) -> int:
    from gaia.cases import resolve_case_name
    from gaia.ecosystem_io import read_json

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("case")
    parser.add_argument("--check", action="store_true",
                        help="Fail unless the case file's hyperparameters and ranges are the fit's (rel 1e-6)")
    args = parser.parse_args(argv)
    name = resolve_case_name(args.case) or args.case
    path = ROOT / "gaia" / "cases" / "data" / f"{name}.json"
    document = read_json(path)
    failures = 0
    for service, depth, r in fits_of(document):
        params = depth["parameters"]
        print(f"{service}")
        print(f"  {r['n']} measurements; z_ref = {depth['reference_depth_m']} m, "
              f"z_max = {params['depth_limit']['value']} m (from the literature)")
        print(f"  P_ref = {r['npp_at_reference_depth']:.4f} (se of ln {r['se_log_npp_at_reference_depth']:.4f}); "
              f"95% prediction interval {r['npp_range'][0]:.4f}-{r['npp_range'][1]:.4f}")
        print(f"  k = {r['decline_rate']:.6f}/m (se {r['se_decline_rate']:.6f}); "
              f"range {r['decline_rate_range'][0]:.6f}-{r['decline_rate_range'][1]:.6f}")
        print(f"  correlation(ln P_ref, k) = {r['correlation']:.3f}; residual sd of ln = "
              f"{r['residual_sd_log']:.4f}; prediction sd = {r['prediction_sd_log']:.4f}")
        if args.check:
            pairs = [
                (params["npp_at_reference_depth"]["value"], r["npp_at_reference_depth"]),
                (params["npp_at_reference_depth"]["range"][0], r["npp_range"][0]),
                (params["npp_at_reference_depth"]["range"][1], r["npp_range"][1]),
                (params["decline_rate"]["value"], r["decline_rate"]),
                (params["decline_rate"]["range"][0], r["decline_rate_range"][0]),
                (params["decline_rate"]["range"][1], r["decline_rate_range"][1]),
            ]
            bad = [(a, b) for a, b in pairs if not math.isclose(a, b, rel_tol=1e-6)]
            print("  check: " + ("OK" if not bad else f"DIFF {bad}"))
            failures += bool(bad)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
