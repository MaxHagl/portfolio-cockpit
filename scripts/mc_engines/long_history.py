"""Long-history bootstrap engine — 5th engine.

Uses stitched 2000-2026 index returns instead of v1's 2014-2026 augmented matrix.
Bootstraps via the same Politis-Romano stationary block bootstrap.
Result: realistic P(loss), captures dotcom + GFC + COVID in the resampling pool.
"""
from __future__ import annotations

import pandas as pd

from mc_long_history import build_long_history_matrix
from mc_engines.bootstrap import select_block_length_multi, stationary_bootstrap_paths


def long_history_bootstrap_paths(n_paths: int, horizon_days: int, seed: int,
                                  chunk_size: int = 5000):
    """End-to-end: build long-history matrix, select block length, generate paths.

    Returns (paths, block_length, matrix_metadata)
    """
    df = build_long_history_matrix()
    block_length = select_block_length_multi(df)
    paths = stationary_bootstrap_paths(df, n_paths=n_paths, horizon_days=horizon_days,
                                        mean_block_length=block_length, seed=seed,
                                        chunk_size=chunk_size)
    meta = {
        "windowStart": str(df.index.min().date()),
        "windowEnd": str(df.index.max().date()),
        "windowDays": int(len(df)),
        "windowYears": float((df.index.max() - df.index.min()).days / 365.25),
        "blockLength": int(block_length),
        "columns": list(df.columns),
    }
    return paths, df, meta
