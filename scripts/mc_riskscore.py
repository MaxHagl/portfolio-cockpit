"""Composite risk score 0-100 for portfolio MC results.

Components (weighted):
- 30% Annualized realized volatility (0-30% maps to 0-100)
- 30% Median max drawdown (0-70% absolute maps to 0-100)
- 20% CVaR-5% terminal loss vs starting wealth (0-50% loss maps to 0-100)
- 20% Time underwater fraction (0-100% maps to 0-100)

Each component clamped to [0, 100]. Composite is weighted sum, clamped [0, 100].

Score interpretation:
- 0-20: Very conservative (mostly cash/bonds)
- 20-40: Conservative balanced
- 40-60: Moderate (typical 60/40)
- 60-80: Aggressive equity
- 80-100: Extreme (single-stock or concentrated tech)

Mathematical: monotonic in each component, additive in components — easy to
attribute "this portfolio is risky because of X" via the individual sub-scores.
"""
from __future__ import annotations

import numpy as np


THRESHOLDS = {
    "vol_max":      0.30,   # 30% annualized vol = 100 on this axis
    "dd_max":       0.70,   # 70% max DD = 100
    "cvar_max":     0.50,   # 50% loss in CVaR-5% = 100
    "tu_max":       1.00,   # 100% time underwater = 100
}

WEIGHTS = {
    "vol":   0.30,
    "dd":    0.30,
    "cvar":  0.20,
    "tu":    0.20,
}


def composite_risk_score(
    terminal: np.ndarray,
    max_drawdown: np.ndarray,
    ann_vol: np.ndarray,
    time_underwater_days: np.ndarray,
    starting_eur: float,
    horizon_years: float,
) -> dict:
    """Compute composite risk score 0-100 from per-path metrics arrays.

    Returns dict with:
      score: overall 0-100
      components: {vol, dd, cvar, tu} each 0-100
      details: raw values for transparency
    """
    # Volatility: median annualized realized vol across paths
    vol_median = float(np.median(ann_vol))
    vol_norm = min(100.0, max(0.0, vol_median / THRESHOLDS["vol_max"] * 100))

    # Drawdown: median absolute max drawdown
    dd_median = float(abs(np.median(max_drawdown)))
    dd_norm = min(100.0, dd_median / THRESHOLDS["dd_max"] * 100)

    # CVaR-5%: expected loss in worst 5% of terminal outcomes, as fraction of starting wealth
    cutoff = max(1, int(0.05 * len(terminal)))
    worst5_mean = float(np.mean(np.sort(terminal)[:cutoff]))
    cvar_loss_frac = max(0.0, (starting_eur - worst5_mean) / starting_eur)
    cvar_norm = min(100.0, cvar_loss_frac / THRESHOLDS["cvar_max"] * 100)

    # Time underwater: fraction of horizon spent below running peak
    total_days = horizon_years * 252
    tu_frac = float(np.median(time_underwater_days)) / total_days
    tu_norm = min(100.0, tu_frac / THRESHOLDS["tu_max"] * 100)

    components = {"vol": vol_norm, "dd": dd_norm, "cvar": cvar_norm, "tu": tu_norm}
    score = sum(WEIGHTS[k] * components[k] for k in WEIGHTS)
    score = min(100.0, max(0.0, score))

    return {
        "score": round(score, 1),
        "components": {k: round(v, 1) for k, v in components.items()},
        "details": {
            "annVolMedian": vol_median,
            "maxDdMedian": -dd_median,
            "cvar5LossFrac": cvar_loss_frac,
            "timeUnderwaterFrac": tu_frac,
            "expectedShortfall5Eur": worst5_mean,
        },
        "weights": WEIGHTS,
        "thresholds": THRESHOLDS,
    }


def risk_band(score: float) -> str:
    """Map numeric score to qualitative label."""
    if score < 20: return "very conservative"
    if score < 40: return "conservative"
    if score < 60: return "moderate"
    if score < 80: return "aggressive"
    return "extreme"


def sharpe_like(median_ann_return: float, risk_score: float) -> float:
    """Custom Sharpe-like = return / risk_score.

    Avoids divide-by-zero with min risk of 1.0.
    """
    return median_ann_return / max(1.0, risk_score) * 100


if __name__ == "__main__":
    # Sanity test
    rng = np.random.default_rng(42)
    n = 5000
    starting = 21302
    # Pretend: terminal ~lognormal centered around 100k, vol ~15%, max DD ~30%
    terminal = rng.lognormal(mean=np.log(100000), sigma=0.6, size=n)
    max_dd = -rng.uniform(0.10, 0.50, size=n)
    ann_vol = rng.normal(0.15, 0.02, size=n)
    tu_days = rng.uniform(400, 1500, size=n)

    result = composite_risk_score(terminal, max_dd, ann_vol, tu_days, starting, 15)
    print(f"Risk score: {result['score']}")
    print(f"Band: {risk_band(result['score'])}")
    print(f"Components: {result['components']}")
    print(f"Sharpe-like (with 8% median return): {sharpe_like(0.08, result['score']):.2f}")
