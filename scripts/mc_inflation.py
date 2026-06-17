"""Stochastic inflation modeling via HICP bootstrap.

Loads Euro Area HICP monthly index, computes m/m %, block-bootstraps to produce
(n_paths, horizon_days+1) daily deflator arrays. Daily deflator interpolates
between monthly HICP changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
TRADING_DAYS_PER_MONTH = 21


def load_hicp() -> pd.Series:
    """Load HICP monthly index from cache."""
    p = CACHE / "_macro_HICP_EUR.json"
    raw = json.loads(p.read_text())
    pts = raw["points"]
    idx = pd.to_datetime([x["t"] for x in pts], unit="ms")
    vals = [x["c"] for x in pts]
    s = pd.Series(vals, index=idx, name="HICP_EUR")
    return s.sort_index()


def hicp_monthly_returns() -> np.ndarray:
    """Monthly % change in HICP (inflation rate)."""
    s = load_hicp()
    rets = s.pct_change().dropna().values
    return rets


def bootstrap_inflation_paths(
    n_paths: int,
    horizon_days: int,
    seed: int,
    block_months: int = 6,
) -> np.ndarray:
    """Sample monthly inflation rates, expand to daily deflator array.

    Returns (n_paths, horizon_days + 1) cumulative deflator paths.
    deflator[p, t] = product(1 + monthly_inflation) up to day t (interpolated daily).
    """
    monthly_rets = hicp_monthly_returns()
    T_months = (horizon_days + TRADING_DAYS_PER_MONTH - 1) // TRADING_DAYS_PER_MONTH

    rng = np.random.default_rng(seed)
    # Stationary bootstrap on monthly returns
    p_prob = 1.0 / block_months
    M = len(monthly_rets)

    idx = np.empty((n_paths, T_months), dtype=np.int64)
    idx[:, 0] = rng.integers(0, M, size=n_paths)
    starts = rng.random((n_paths, T_months - 1)) < p_prob
    new_idx = rng.integers(0, M, size=(n_paths, T_months - 1))
    for t in range(1, T_months):
        cont = (idx[:, t - 1] + 1) % M
        idx[:, t] = np.where(starts[:, t - 1], new_idx[:, t - 1], cont)

    monthly_sampled = monthly_rets[idx]  # (n_paths, T_months)
    monthly_cum = np.cumprod(1 + monthly_sampled, axis=1)  # (n_paths, T_months)

    # Expand to daily: each month's deflator repeats over 21 trading days
    daily = monthly_cum.repeat(TRADING_DAYS_PER_MONTH, axis=1)  # (n_paths, T_months * 21)
    # Trim to horizon_days
    daily = daily[:, :horizon_days]
    # Prepend day-0 deflator of 1.0
    out = np.column_stack([np.ones(n_paths), daily])  # (n_paths, horizon_days + 1)
    return out


def diagnostics(paths: np.ndarray, horizon_years: float) -> dict:
    """Distribution of 15y geometric-mean inflation."""
    terminal_deflator = paths[:, -1]
    ann_inflation = terminal_deflator ** (1 / horizon_years) - 1
    return {
        "median15yAnnInflation": float(np.median(ann_inflation)),
        "mean15yAnnInflation": float(np.mean(ann_inflation)),
        "p5": float(np.quantile(ann_inflation, 0.05)),
        "p95": float(np.quantile(ann_inflation, 0.95)),
        "p99": float(np.quantile(ann_inflation, 0.99)),
    }


if __name__ == "__main__":
    monthly_rets = hicp_monthly_returns()
    print(f"HICP monthly returns: n={len(monthly_rets)}, mean={monthly_rets.mean()*12*100:.2f}%/yr")

    paths = bootstrap_inflation_paths(n_paths=10000, horizon_days=15*252, seed=42)
    print(f"Inflation paths shape: {paths.shape}")
    diag = diagnostics(paths, 15)
    print(f"15y geo-mean inflation:")
    print(f"  median: {diag['median15yAnnInflation']*100:+.2f}%")
    print(f"  mean:   {diag['mean15yAnnInflation']*100:+.2f}%")
    print(f"  p5:     {diag['p5']*100:+.2f}%")
    print(f"  p95:    {diag['p95']*100:+.2f}%")
    print(f"  p99:    {diag['p99']*100:+.2f}%")
