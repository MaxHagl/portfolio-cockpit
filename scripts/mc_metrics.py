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
) -> np.ndarray:
    """Simulate portfolio wealth given (n_paths, horizon_days, n_assets) returns.

    Returns (n_paths, horizon_days + 1) wealth trajectories starting at starting_eur.

    Rebalance options: 'daily', 'weekly' (5d), 'monthly' (21d), 'quarterly' (63d),
                       'annual' (252d), 'never'
    """
    P, T, A = daily_paths.shape
    daily_ter = (ter_annual / TRADING_DAYS_PER_YEAR).astype(np.float32)  # (A,)

    # Subtract daily TER drag from returns. Use view-based math to avoid full copy.
    net_paths = daily_paths - daily_ter[np.newaxis, np.newaxis, :]

    if rebalance == "never":
        # Compound each asset independently, sum wealth without storing (P, T, A) tensor.
        wealth = np.zeros((P, T + 1), dtype=np.float64)
        wealth[:, 0] = starting_eur
        for a in range(A):
            if weights[a] == 0:
                continue
            cp = np.cumprod(1 + net_paths[:, :, a], axis=1)  # (P, T)
            wealth[:, 1:] += starting_eur * weights[a] * cp
        return wealth

    rebal_freq = {
        "daily": 1, "weekly": 5, "monthly": 21,
        "quarterly": 63, "annual": 252,
    }[rebalance]

    wealth = np.empty((P, T + 1), dtype=np.float64)
    wealth[:, 0] = starting_eur
    asset_w = np.full((P, A), starting_eur, dtype=np.float64) * weights[np.newaxis, :]

    for t in range(T):
        asset_w = asset_w * (1 + net_paths[:, t, :])
        wealth[:, t + 1] = asset_w.sum(axis=1)
        if (t + 1) % rebal_freq == 0 and t < T - 1:
            asset_w = wealth[:, t + 1, np.newaxis] * weights[np.newaxis, :]
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
