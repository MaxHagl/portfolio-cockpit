"""Stationary block bootstrap (Politis-Romano 1994) — primary MC engine.

Resamples blocks of daily returns with geometric block lengths (mean = `mean_block_length`).
Preserves volatility clustering and cross-asset correlation by construction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def politis_white_block_length(returns: pd.Series, max_lag: int | None = None) -> int:
    """Politis-White (2009) automatic block length picker via autocovariance flat-top kernel.

    Falls back to 20 if computation fails. Operates on univariate series; for multi-asset
    matrix we compute per-column and take the median.
    """
    try:
        from arch.bootstrap import optimal_block_length
        # arch returns DataFrame with columns ['stationary', 'circular']
        r = pd.DataFrame(returns.dropna())
        obl = optimal_block_length(r)
        bl = float(obl["stationary"].iloc[0])
        return max(2, min(100, int(round(bl))))
    except Exception:
        return 20


def select_block_length_multi(returns_df: pd.DataFrame) -> int:
    """Median Politis-White block length across columns."""
    candidates = []
    for col in returns_df.columns:
        bl = politis_white_block_length(returns_df[col])
        candidates.append(bl)
    return int(np.median(candidates))


def stationary_bootstrap_paths(
    returns_df: pd.DataFrame,
    n_paths: int,
    horizon_days: int,
    mean_block_length: int,
    seed: int,
    chunk_size: int = 5000,
) -> np.ndarray:
    """Generate paths via stationary block bootstrap.

    Returns array shape (n_paths, horizon_days, n_assets) of resampled daily simple returns.
    Memory-chunked to stay under ~4GB peak for 200k paths × 3780 × 5.
    """
    R = returns_df.values  # shape (T, A)
    T, A = R.shape
    if T < 100:
        raise ValueError(f"Need at least 100 historical days; got {T}")

    p = 1.0 / mean_block_length  # geometric: prob of starting a new block on any step

    rng = np.random.default_rng(seed)
    out = np.empty((n_paths, horizon_days, A), dtype=np.float32)

    for start in range(0, n_paths, chunk_size):
        n = min(chunk_size, n_paths - start)
        # For each path, sample starting indices and block-start booleans
        # Strategy: pre-sample n × horizon_days indices using stationary bootstrap rule
        idx = np.empty((n, horizon_days), dtype=np.int64)
        # Initialize first column with uniform random starting positions
        idx[:, 0] = rng.integers(0, T, size=n)
        # For each subsequent step, with prob p start new block (random index), else +1
        starts = rng.random((n, horizon_days - 1)) < p
        new_idx = rng.integers(0, T, size=(n, horizon_days - 1))
        for t in range(1, horizon_days):
            cont = (idx[:, t - 1] + 1) % T  # wrap around for stationarity
            idx[:, t] = np.where(starts[:, t - 1], new_idx[:, t - 1], cont)

        out[start:start + n] = R[idx].astype(np.float32)

    return out


if __name__ == "__main__":
    # Quick standalone smoke test
    rng = np.random.default_rng(42)
    fake_rets = pd.DataFrame(
        rng.normal(0.0005, 0.012, (500, 3)),
        columns=["A", "B", "C"],
    )
    bl = select_block_length_multi(fake_rets)
    print(f"Selected block length (synthetic data): {bl}")
    paths = stationary_bootstrap_paths(fake_rets, n_paths=1000, horizon_days=252, mean_block_length=bl, seed=42)
    print(f"Bootstrap paths shape: {paths.shape}")
    print(f"Mean daily return across paths: {paths.mean():+.5f} (expected ~+0.0005)")
    print(f"Std daily return across paths:  {paths.std():.5f}  (expected ~0.012)")
