"""EUR/USD currency overlay for portfolio paths.

Adjusts wealth paths to reflect EUR-investor view when underlying assets are USD-denominated.
Samples FX paths from historical EUR/USD daily returns and applies to USD portion of portfolio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mc_engines.bootstrap import select_block_length_multi, stationary_bootstrap_paths


def sample_fx_paths(
    eurusd_returns: pd.Series,
    n_paths: int,
    horizon_days: int,
    seed: int,
) -> np.ndarray:
    """Bootstrap EUR/USD return paths."""
    df = pd.DataFrame({"EURUSD": eurusd_returns.dropna()})
    bl = select_block_length_multi(df)
    paths = stationary_bootstrap_paths(df, n_paths=n_paths, horizon_days=horizon_days,
                                        mean_block_length=bl, seed=seed)
    return paths[:, :, 0]  # (n_paths, horizon_days)


def apply_fx_overlay(
    wealth_nominal: np.ndarray,
    fx_paths: np.ndarray,
    usd_exposure: float,
) -> np.ndarray:
    """Apply FX shock to USD-denominated portion of wealth.

    For each path, USD portion's EUR value moves with EUR/USD (rising EURUSD = EUR stronger, USD weaker).
    Adjustment: new_wealth = wealth × (1 - usd_exposure + usd_exposure × fx_cumulative)
    where fx_cumulative = product(1 - r_EURUSD) reflects USD strengthening (EUR weakening).

    Note: EURUSD return = % change in USD/EUR. A positive return means EUR appreciates, USD depreciates.
    Holdings of USD-denominated assets are worth less in EUR when EUR strengthens.
    """
    P, H = fx_paths.shape
    # Cumulative USD-from-EUR-perspective return: subtract EURUSD return
    fx_cumulative = np.cumprod(1 - fx_paths, axis=1)
    # USD portion of wealth × FX adjustment + EUR portion stays as is
    eur_portion_factor = 1 - usd_exposure
    usd_portion_factor = usd_exposure * fx_cumulative
    multiplier = eur_portion_factor + usd_portion_factor
    # Align lengths: wealth has H+1 cols (incl. day 0), fx has H cols
    if wealth_nominal.shape[1] == H + 1:
        mult_padded = np.column_stack([np.ones(P), multiplier])
    else:
        mult_padded = multiplier
    return wealth_nominal * mult_padded
