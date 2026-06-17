"""Drawdown-buy tactical overlay.

Augments DCA contributions: when portfolio is in drawdown > threshold,
double the contribution that month. Tests whether "buy on dips" tactically
adds value over straight DCA.
"""
from __future__ import annotations

import numpy as np

DAYS_PER_MONTH = 21


def simulate_with_drawdown_buy(
    daily_paths: np.ndarray,
    weights: np.ndarray,
    starting_eur: float,
    ter_annual: np.ndarray,
    base_monthly: float,
    drawdown_threshold: float = 0.20,
    multiplier: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate baseline DCA with drawdown-buy boost.

    At each monthly contribution day, check if portfolio is in drawdown
    deeper than threshold from running peak. If so, contribute base_monthly × multiplier.

    Returns: (wealth, total_contributions_per_path)
    """
    P, T, A = daily_paths.shape
    TRADING_DAYS_PER_YEAR = 252
    daily_ter = (ter_annual / TRADING_DAYS_PER_YEAR).astype(np.float32)
    net_paths = daily_paths - daily_ter[np.newaxis, np.newaxis, :]

    wealth = np.empty((P, T + 1), dtype=np.float64)
    wealth[:, 0] = starting_eur
    asset_w = (np.full(P, starting_eur, dtype=np.float64)[:, np.newaxis] * weights[np.newaxis, :])
    running_peak = np.full(P, starting_eur, dtype=np.float64)
    total_contributed = np.zeros(P, dtype=np.float64)

    rebal_freq = 63  # quarterly
    for t in range(T):
        # Apply daily return
        asset_w = asset_w * (1 + net_paths[:, t, :])
        current_wealth = asset_w.sum(axis=1)
        running_peak = np.maximum(running_peak, current_wealth)

        # Monthly contribution
        if (t + 1) % DAYS_PER_MONTH == 0 and (t + 1) <= T:
            current_dd = current_wealth / running_peak - 1
            in_drawdown = current_dd < -drawdown_threshold
            contribution = np.where(in_drawdown, base_monthly * multiplier, base_monthly)
            asset_w += contribution[:, np.newaxis] * weights[np.newaxis, :]
            total_contributed += contribution

        wealth[:, t + 1] = asset_w.sum(axis=1)

        # Rebalance
        if (t + 1) % rebal_freq == 0 and t < T - 1:
            asset_w = wealth[:, t + 1, np.newaxis] * weights[np.newaxis, :]

    return wealth, total_contributed
