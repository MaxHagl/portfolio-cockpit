"""Expanding-window cross-validation for sensitivity to history sample.

Repeatedly runs the bootstrap engine on different historical windows
(expanding or rolling) to quantify how much the result depends on which
years of data are available.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mc_engines.bootstrap import select_block_length_multi, stationary_bootstrap_paths


def expanding_window_studies(
    returns_df: pd.DataFrame,
    n_paths: int,
    horizon_days: int,
    seed: int,
    n_windows: int = 5,
    min_window_years: float = 3.0,
) -> list[dict]:
    """Run bootstrap on N expanding windows of history.

    For each window, returns the (median terminal wealth multiple, max DD median, ann return median)
    so the orchestrator can plot how the result depends on data choice.
    """
    T = len(returns_df)
    min_window_days = int(min_window_years * 252)
    if T <= min_window_days:
        # Single-window fallback
        windows = [(0, T)]
    else:
        # Equally-spaced window sizes from min to full
        sizes = np.linspace(min_window_days, T, n_windows).astype(int)
        windows = [(T - s, T) for s in sizes]  # all end at present, start earlier

    studies = []
    for (s_idx, e_idx) in windows:
        window = returns_df.iloc[s_idx:e_idx]
        bl = select_block_length_multi(window)
        paths = stationary_bootstrap_paths(window, n_paths=n_paths, horizon_days=horizon_days,
                                            mean_block_length=bl, seed=seed)
        # paths shape (P, H, A) — compute equal-weighted portfolio for summary
        port_rets = paths.mean(axis=2)  # equal-weight proxy for sensitivity
        wealth = np.cumprod(1 + port_rets, axis=1)
        terminal = wealth[:, -1]
        peak = np.maximum.accumulate(wealth, axis=1)
        dd = (wealth / peak) - 1
        max_dd = dd.min(axis=1)
        studies.append({
            "window_start": str(window.index[0].date()),
            "window_end": str(window.index[-1].date()),
            "window_days": len(window),
            "blockLength": bl,
            "medianTerminalMultiple": float(np.median(terminal)),
            "p5TerminalMultiple": float(np.quantile(terminal, 0.05)),
            "p95TerminalMultiple": float(np.quantile(terminal, 0.95)),
            "medianMaxDrawdown": float(np.median(max_dd)),
        })
    return studies


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    fake = pd.DataFrame(
        rng.normal(0.0005, 0.012, (2000, 3)),
        index=pd.bdate_range("2018-01-01", periods=2000),
        columns=["A", "B", "C"],
    )
    studies = expanding_window_studies(fake, n_paths=500, horizon_days=252, seed=42, n_windows=4)
    for s in studies:
        print(f"  {s['window_start']} → {s['window_end']} ({s['window_days']}d, bl={s['blockLength']}): "
              f"med_term={s['medianTerminalMultiple']:.3f}  med_dd={s['medianMaxDrawdown']:+.3f}")
