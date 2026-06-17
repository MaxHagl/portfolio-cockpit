"""Data loading and alignment for Monte Carlo.

Reads price JSONs from .cache/ produced by prefetch.py + prefetch_indices.py,
returns aligned daily simple-return DataFrames suitable for bootstrap/parametric MC.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"

TRADING_DAYS_PER_YEAR = 252


def _load_json_series(path: Path, name: str) -> pd.Series:
    """Read {points: [{t: ms, c: float}]} → pd.Series indexed by date."""
    raw = json.loads(path.read_text())
    pts = raw.get("points", [])
    if not pts:
        return pd.Series(dtype=float, name=name)
    idx = pd.to_datetime([p["t"] for p in pts], unit="ms", utc=True).tz_localize(None).normalize()
    vals = [p["c"] for p in pts]
    s = pd.Series(vals, index=idx, name=name)
    # Drop duplicates (keep last)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def load_holding(holding_id: str) -> pd.Series:
    """Load .cache/<holding_id>.json."""
    return _load_json_series(CACHE / f"{holding_id}.json", holding_id)


def load_index(index_id: str) -> pd.Series:
    """Load .cache/_index_<index_id>.json."""
    return _load_json_series(CACHE / f"_index_{index_id}.json", index_id)


def load_holdings_meta() -> dict:
    """Load data/holdings.json."""
    return json.loads((ROOT / "data" / "holdings.json").read_text())


def _clean_price_spikes(prices: pd.Series, window: int = 5, threshold: float = 0.18) -> pd.Series:
    """Detect and remove erroneous price spikes via rolling-median outlier filter.

    For each price, compare to median of surrounding window. If deviation > threshold,
    mark as NaN and forward-fill. Catches Yahoo's occasional one-day bad ticks.
    """
    rolling_med = prices.rolling(window=window, center=True, min_periods=2).median()
    deviation = (prices - rolling_med).abs() / rolling_med
    mask = deviation > threshold
    cleaned = prices.copy()
    cleaned[mask] = float("nan")
    cleaned = cleaned.ffill().bfill()
    return cleaned


def to_business_day_returns(
    prices: pd.Series,
    robust_cap: float = 0.20,
    clean_spikes: bool = True,
) -> pd.Series:
    """Reindex to business days, forward-fill, optionally remove price spikes,
    compute simple daily returns, and cap |returns| at robust_cap as final safety net.

    Two-stage cleaning:
    1. Rolling-median price spike filter (catches one-day data errors at source)
    2. Final return-magnitude cap (safety against missed spikes)

    20% daily move is plausible only in 1987/2020-scale crashes — beyond that is data error
    for a diversified ETF.
    """
    if len(prices) == 0:
        return pd.Series(dtype=float)
    bidx = pd.bdate_range(prices.index.min(), prices.index.max())
    p = prices.reindex(bidx).ffill().dropna()
    if clean_spikes:
        p = _clean_price_spikes(p)
    rets = p.pct_change().dropna()
    mask = rets.abs() <= robust_cap
    rets = rets[mask]
    rets.name = prices.name
    return rets


def align_returns(returns_by_id: dict[str, pd.Series], how: str = "outer") -> pd.DataFrame:
    """Align multiple return series to a common index.

    how="outer" preserves all dates (NaN where missing — used for augmentation pool).
    how="inner" intersects to all-overlap (used for regression).
    """
    if not returns_by_id:
        return pd.DataFrame()
    df = pd.concat(returns_by_id.values(), axis=1, join=how)
    df.columns = list(returns_by_id.keys())
    return df


def summarize_series(returns: pd.Series) -> dict:
    """Per-series diagnostics: mean/vol/skew/kurt + date range."""
    r = returns.dropna()
    return {
        "n": int(len(r)),
        "start": str(r.index.min().date()) if len(r) else None,
        "end": str(r.index.max().date()) if len(r) else None,
        "meanDaily": float(r.mean()) if len(r) else 0.0,
        "stdDaily": float(r.std()) if len(r) else 0.0,
        "meanAnnualized": float(r.mean() * TRADING_DAYS_PER_YEAR) if len(r) else 0.0,
        "volAnnualized": float(r.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(r) else 0.0,
        "skew": float(r.skew()) if len(r) > 2 else 0.0,
        "kurtosisExcess": float(r.kurtosis()) if len(r) > 3 else 0.0,
        "minDaily": float(r.min()) if len(r) else 0.0,
        "maxDaily": float(r.max()) if len(r) else 0.0,
    }


def load_eurusd_returns() -> pd.Series:
    """Load EUR/USD returns. Note: EURUSD=X is USD per 1 EUR; rising = EUR stronger."""
    s = load_index("EURUSD")
    return to_business_day_returns(s)


if __name__ == "__main__":
    # Sanity check
    meta = load_holdings_meta()
    series_by_id = {}
    for h in meta["holdings"]:
        hid = h["id"]
        s = load_holding(hid)
        rets = to_business_day_returns(s)
        series_by_id[hid] = rets
        diag = summarize_series(rets)
        print(f"{hid:10s} n={diag['n']:5d}  {diag['start']} → {diag['end']}  "
              f"μ_ann={diag['meanAnnualized']:+.3f}  σ_ann={diag['volAnnualized']:.3f}  "
              f"skew={diag['skew']:+.2f}  exKurt={diag['kurtosisExcess']:+.2f}")

    df_inner = align_returns(series_by_id, how="inner")
    df_outer = align_returns(series_by_id, how="outer")
    print(f"\nAligned (inner): {df_inner.shape}, {df_inner.index.min().date()} → {df_inner.index.max().date()}")
    print(f"Aligned (outer): {df_outer.shape}, {df_outer.index.min().date()} → {df_outer.index.max().date()}")

    print("\nIndex availability:")
    for idx_id in ["SPX", "NDX", "IXN", "EEM", "URTH", "STOXX600", "EUNA", "EURUSD", "XDWD"]:
        s = load_index(idx_id)
        rets = to_business_day_returns(s)
        if len(rets):
            print(f"  _index_{idx_id:10s} n={len(rets):6d}  {rets.index.min().date()} → {rets.index.max().date()}")
        else:
            print(f"  _index_{idx_id:10s} EMPTY")
