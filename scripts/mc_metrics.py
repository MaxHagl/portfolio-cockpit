"""Portfolio simulation and metrics computation from MC return paths.

Takes (n_paths, horizon_days, n_assets) return paths and weights, applies TER drag
and optional rebalancing, returns wealth trajectories and distributional metrics.
"""
from __future__ import annotations

import numpy as np


TRADING_DAYS_PER_YEAR = 252


def simulate_portfolio_wealth(
    daily_paths: np.ndarray,
    weights: np.ndarray,
    starting_eur: float,
    ter_annual: np.ndarray,
    rebalance: str = "quarterly",
    cashflows: np.ndarray | None = None,
    cashflow_inflation_adj: np.ndarray | None = None,
    track_basis: bool = False,
):
    """Simulate portfolio wealth given (n_paths, horizon_days, n_assets) returns.

    Returns (n_paths, horizon_days + 1) wealth trajectories starting at starting_eur.
    If track_basis=True, returns (wealth, basis) tuple where basis is (n_paths, T+1)
    cumulative cost basis per path. Used for capital-gains tax computation.

    Rebalance options: 'daily', 'weekly' (5d), 'monthly' (21d), 'quarterly' (63d),
                       'annual' (252d), 'never'

    Cashflows:
        cashflows: optional (T+1,) array of EUR amounts per day.
                   Positive = contribution at start of day t (before return applied)
                   Negative = withdrawal at start of day t
        cashflow_inflation_adj: optional (T+1,) or (P, T+1) deflator applied to cashflows
                   (e.g., for inflation-indexed withdrawals: cashflow_t * deflator_t)
        Contributions are allocated to assets per target weights.
        Withdrawals reduce wealth proportionally across assets (basis tracks
        average-cost reduction).
    """
    P, T, A = daily_paths.shape
    daily_ter = (ter_annual / TRADING_DAYS_PER_YEAR).astype(np.float32)
    net_paths = daily_paths - daily_ter[np.newaxis, np.newaxis, :]

    has_cashflow = cashflows is not None and np.any(cashflows != 0)
    if has_cashflow:
        # Expand cashflows to (P, T+1) shape
        if cashflow_inflation_adj is not None:
            if cashflow_inflation_adj.ndim == 1:
                cf = cashflows[np.newaxis, :] * cashflow_inflation_adj[np.newaxis, :]
                cf = np.broadcast_to(cf, (P, T + 1)).copy()
            else:
                cf = cashflows[np.newaxis, :] * cashflow_inflation_adj
        else:
            cf = np.broadcast_to(cashflows[np.newaxis, :], (P, T + 1)).copy()
    else:
        cf = None

    # Fast path: no cashflows, never-rebalance — original optimized loop
    if not has_cashflow and rebalance == "never":
        wealth = np.zeros((P, T + 1), dtype=np.float64)
        wealth[:, 0] = starting_eur
        for a in range(A):
            if weights[a] == 0:
                continue
            cp = np.cumprod(1 + net_paths[:, :, a], axis=1)
            wealth[:, 1:] += starting_eur * weights[a] * cp
        if track_basis:
            basis = np.full((P, T + 1), starting_eur, dtype=np.float64)
            return wealth, basis
        return wealth

    rebal_freq = {
        "daily": 1, "weekly": 5, "monthly": 21,
        "quarterly": 63, "annual": 252, "never": None,
    }[rebalance]

    wealth = np.empty((P, T + 1), dtype=np.float64)
    wealth[:, 0] = starting_eur
    asset_w = (np.full(P, starting_eur, dtype=np.float64)[:, np.newaxis] * weights[np.newaxis, :])

    if track_basis:
        basis = np.empty((P, T + 1), dtype=np.float64)
        basis[:, 0] = starting_eur

    for t in range(T):
        # 1. Cashflow at start of day t+1 (before return applied to it)
        if has_cashflow:
            cf_t = cf[:, t + 1]
            # Positive: contribution allocated per target weights
            # Negative: withdrawal proportional to current asset weights
            pos = cf_t > 0
            neg = cf_t < 0
            if np.any(pos):
                asset_w[pos] += cf_t[pos, np.newaxis] * weights[np.newaxis, :]
                if track_basis:
                    basis[pos, t] = basis[pos, t] + cf_t[pos]
            if np.any(neg):
                current_total = asset_w[neg].sum(axis=1, keepdims=True)
                # Withdraw proportionally across assets
                withdraw_frac = (-cf_t[neg, np.newaxis]) / np.maximum(current_total, 1e-9)
                withdraw_frac = np.minimum(withdraw_frac, 1.0)
                asset_w[neg] = asset_w[neg] * (1 - withdraw_frac)
                if track_basis:
                    # Reduce basis proportionally (average-cost)
                    basis[neg, t] = basis[neg, t] * (1 - withdraw_frac[:, 0])

        # 2. Apply daily return
        asset_w = asset_w * (1 + net_paths[:, t, :])

        # 3. Record wealth
        wealth[:, t + 1] = asset_w.sum(axis=1)
        if track_basis:
            basis[:, t + 1] = basis[:, t]

        # 4. Rebalance if scheduled
        if rebal_freq is not None and (t + 1) % rebal_freq == 0 and t < T - 1:
            asset_w = wealth[:, t + 1, np.newaxis] * weights[np.newaxis, :]

    if track_basis:
        return wealth, basis
    return wealth


def compute_path_metrics(wealth: np.ndarray, starting_eur: float, horizon_years: float) -> dict:
    """Per-path metrics from wealth trajectories."""
    P, T1 = wealth.shape
    terminal = wealth[:, -1]
    multiple = terminal / starting_eur
    ann_return = multiple ** (1 / horizon_years) - 1

    # Max drawdown per path
    peak = np.maximum.accumulate(wealth, axis=1)
    dd = (wealth / peak) - 1
    max_dd = dd.min(axis=1)

    # Time underwater: days where wealth < running peak (any drawdown)
    underwater = (dd < -0.001).astype(np.int32)
    time_underwater = underwater.sum(axis=1)

    # Realized vol per path (geometric: std of log returns)
    log_rets = np.log(wealth[:, 1:] / wealth[:, :-1])
    ann_vol = log_rets.std(axis=1) * np.sqrt(TRADING_DAYS_PER_YEAR)

    return {
        "terminal": terminal,
        "multiple": multiple,
        "annReturn": ann_return,
        "annVol": ann_vol,
        "maxDrawdown": max_dd,
        "timeUnderwaterDays": time_underwater,
    }


def quantile_summary(arr: np.ndarray, quantiles: list[float] = None) -> dict:
    """Distributional summary."""
    if quantiles is None:
        quantiles = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    out = {"mean": float(np.mean(arr)), "median": float(np.median(arr)), "std": float(np.std(arr))}
    for q in quantiles:
        out[f"p{int(q*100)}"] = float(np.quantile(arr, q))
    # Expected shortfall at 5% (mean of worst 5%)
    sorted_arr = np.sort(arr)
    cutoff = max(1, int(0.05 * len(sorted_arr)))
    out["expectedShortfall5"] = float(np.mean(sorted_arr[:cutoff]))
    out["expectedShortfall1"] = float(np.mean(sorted_arr[: max(1, int(0.01 * len(sorted_arr)))]))
    return out


def fan_chart(wealth: np.ndarray, step_days: int = 21) -> dict:
    """Quantile fan chart: every step_days, emit percentiles of wealth."""
    P, T1 = wealth.shape
    t_indices = list(range(0, T1, step_days))
    if t_indices[-1] != T1 - 1:
        t_indices.append(T1 - 1)
    qs = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    out = {"ts": t_indices}
    for q in qs:
        out[f"p{int(q*100)}"] = [float(np.quantile(wealth[:, t], q)) for t in t_indices]
    return out


def sample_paths(wealth: np.ndarray, n_samples: int = 50, step_days: int = 5) -> list[dict]:
    """Pick n_samples paths spanning the terminal distribution, downsampled to step_days."""
    P, T1 = wealth.shape
    order = np.argsort(wealth[:, -1])
    pick_idx = np.linspace(0, P - 1, n_samples).astype(int)
    sample_idx = order[pick_idx]
    t_indices = list(range(0, T1, step_days))
    out = []
    for i, path_idx in enumerate(sample_idx):
        q = pick_idx[i] / P
        out.append({
            "quantile": float(q),
            "weekly": [float(wealth[path_idx, t]) for t in t_indices],
        })
    return out


def histogram(arr: np.ndarray, bins: int = 60, log_x: bool = False) -> dict:
    """Histogram for ship-ready output."""
    if log_x:
        edges = np.logspace(np.log10(max(1, arr.min())), np.log10(arr.max()), bins + 1)
    else:
        edges = np.linspace(arr.min(), arr.max(), bins + 1)
    counts, _ = np.histogram(arr, bins=edges)
    return {
        "binEdges": edges.tolist(),
        "counts": counts.tolist(),
    }


def probability_callouts(metrics: dict, starting_eur: float) -> dict:
    """Probability summary commonly needed on the page."""
    terminal = metrics["terminal"]
    multiple = metrics["multiple"]
    max_dd = metrics["maxDrawdown"]

    p = {}
    p["loss"] = float(np.mean(terminal < starting_eur))
    for k, label in [(0.5, "ge0_5x"), (1.5, "ge1_5x"), (2.0, "ge2x"), (3.0, "ge3x"), (5.0, "ge5x"), (10.0, "ge10x")]:
        p[label] = float(np.mean(multiple >= k))
    for thr in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]:
        p[f"ddWorseThan{int(thr*100)}"] = float(np.mean(max_dd <= -thr))
    return p


def goal_probabilities(metrics: dict, targets_eur: list[float]) -> dict:
    """P(terminal wealth >= target) for each target."""
    terminal = metrics["terminal"]
    return {str(int(t)): float(np.mean(terminal >= t)) for t in targets_eur}


def apply_inflation(wealth: np.ndarray, annual_inflation: float, horizon_years: float) -> np.ndarray:
    """Convert nominal wealth to real (today's EUR) terms.

    Real wealth at time t = nominal wealth / (1+pi)^(t/T * horizon_years).
    """
    T1 = wealth.shape[1]
    t = np.arange(T1) / (T1 - 1) * horizon_years
    deflator = (1 + annual_inflation) ** t
    return wealth / deflator[np.newaxis, :]
