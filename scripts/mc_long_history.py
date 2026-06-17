"""Stitched long-history index returns for bear-market-extension engine.

Maps each holding to a primary index + fallback for pre-history. Stitches the
two together at the breakpoint date. Result: ~26y returns matrix covering
2000-2026 including dotcom, GFC, COVID. Allows realistic P(loss) estimates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mc_data import load_index, to_business_day_returns

# (primary_index, primary_start_date, fallback_index)
LONG_HISTORY_MAP = {
    "VWCE":   ("URTH", "2012-06-01", "SPX"),
    "SWDA":   ("URTH", "2012-06-01", "SPX"),
    "BGF":    ("IXN",  "2001-11-27", "NDX"),
    "XDWT":   ("IXN",  "2001-11-27", "NDX"),
    "A3DRHJ": ("EEM",  "2003-04-15", "SPX"),
}


def build_long_history_matrix(start_date: str = "2000-01-03") -> pd.DataFrame:
    """Build stitched return matrix from start_date to today.

    For each holding, splice fallback index pre-breakpoint + primary index post.
    """
    cols = {}
    for holding_id, (primary, breakpoint, fallback) in LONG_HISTORY_MAP.items():
        primary_rets = to_business_day_returns(load_index(primary))
        fallback_rets = to_business_day_returns(load_index(fallback))

        bp_ts = pd.Timestamp(breakpoint)
        pre = fallback_rets.loc[fallback_rets.index < bp_ts]
        post = primary_rets.loc[primary_rets.index >= bp_ts]

        stitched = pd.concat([pre, post]).sort_index()
        # Remove dup dates (keep first)
        stitched = stitched[~stitched.index.duplicated(keep="first")]
        stitched = stitched.loc[stitched.index >= pd.Timestamp(start_date)]
        cols[holding_id] = stitched.rename(holding_id)

    df = pd.concat(cols.values(), axis=1, join="outer").dropna(how="any")
    return df


if __name__ == "__main__":
    df = build_long_history_matrix()
    print(f"Long-history matrix: {df.shape}")
    print(f"Date range: {df.index.min().date()} → {df.index.max().date()}")
    print(f"Span: {(df.index.max() - df.index.min()).days / 365.25:.1f}y\n")
    print("Per-asset stats (annualized):")
    for col in df.columns:
        r = df[col]
        print(f"  {col:10s}  μ_ann={r.mean()*252:+.3f}  σ_ann={r.std()*np.sqrt(252):.3f}  "
              f"min_day={r.min():+.3f}  max_day={r.max():+.3f}")
    print("\nCorrelation matrix:")
    print(df.corr().round(3))
