"""EUR-hedged share class scenarios.

For USD-denominated holdings (BGF, XDWT, A3DRHJ — assume 65% USD exposure each),
subtract EUR/USD daily return + hedging cost (~30 bps/yr) from those columns.

Approximate model: hedged_return = unhedged_return - (eur_usd_return * usd_exposure)
                                   - hedging_cost_daily * usd_exposure

This isolates equity risk from FX risk for the USD-heavy holdings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mc_data import load_index, to_business_day_returns

TRADING_DAYS_PER_YEAR = 252
HEDGING_COST_ANNUAL = 0.0030  # 30 bps per year carry cost
USD_EXPOSURE_BY_HOLDING = {
    "VWCE":   0.62,  # FTSE All-World — 62% US
    "SWDA":   0.70,  # MSCI World — 70% US
    "BGF":    0.70,  # Next Gen Tech — heavy US
    "XDWT":   0.85,  # MSCI World IT — 85% US
    "A3DRHJ": 0.00,  # EM — minimal USD exposure (BRL, INR, TWD, KRW etc.)
}


def hedge_paths(
    paths: np.ndarray,
    asset_order: list[str],
    eurusd_paths: np.ndarray,
) -> np.ndarray:
    """Apply EUR-hedge overlay to paths.

    paths: (P, T, A)
    eurusd_paths: (P, T) — daily EUR/USD returns (positive = EUR strengthens)
    Returns: hedged paths same shape.
    """
    P, T, A = paths.shape
    out = paths.copy()
    daily_hedge_cost = HEDGING_COST_ANNUAL / TRADING_DAYS_PER_YEAR
    for i, hid in enumerate(asset_order):
        exposure = USD_EXPOSURE_BY_HOLDING.get(hid, 0)
        if exposure > 0:
            # Hedged return = unhedged - FX impact - hedging cost
            # Unhedged USD return in EUR terms = USD_return - EUR_USD_return
            # Hedging removes the EUR_USD term, but costs ~30bps/yr
            # Net adjustment: ADD back the EUR_USD that hedging cancels, then SUBTRACT cost
            out[:, :, i] += eurusd_paths[:, :] * exposure - daily_hedge_cost * exposure
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    paths = rng.normal(0.0005, 0.012, (1000, 252, 5)).astype(np.float32)
    fx = rng.normal(0, 0.005, (1000, 252)).astype(np.float32)
    asset_order = ["VWCE", "SWDA", "BGF", "XDWT", "A3DRHJ"]
    hedged = hedge_paths(paths, asset_order, fx)
    print(f"Unhedged: mean {paths.mean():+.5f}, std {paths.std():.5f}")
    print(f"Hedged:   mean {hedged.mean():+.5f}, std {hedged.std():.5f}")
