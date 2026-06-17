"""Filtered Historical Simulation (FHS).

Per-asset GARCH(1,1) fit → standardize residuals → bootstrap them as iid →
re-impose simulated GARCH vol → reconstruct returns. Captures realistic
volatility regimes (clustering, persistence) while still being non-parametric in tails.

Cross-asset correlation preserved by bootstrapping the SAME date-row's
standardized residuals jointly (per-row resampling).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def fit_garch_filters(returns_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Fit GARCH(1,1) per asset, return standardized residuals matrix and final-day vols.

    Returns:
        std_resid: (T, A) standardized residuals
        last_var: (A,) conditional variance at end of sample (initial state for simulation)
        diagnostics: per-asset GARCH params
    """
    from arch import arch_model
    R = returns_df.values
    T, A = R.shape
    std_resid = np.zeros_like(R)
    last_var = np.zeros(A)
    diag = []
    for j in range(A):
        col = returns_df.columns[j] if isinstance(returns_df, pd.DataFrame) else f"asset_{j}"
        rj = R[:, j] * 100.0  # arch package convention: returns in percent
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            am = arch_model(rj, vol="GARCH", p=1, q=1, mean="Constant", dist="normal", rescale=False)
            res = am.fit(disp="off", show_warning=False)
        cond_vol = res.conditional_volatility / 100.0  # back to fractional
        mean_r = res.params["mu"] / 100.0
        std_resid[:, j] = (R[:, j] - mean_r) / cond_vol
        last_var[j] = (cond_vol[-1]) ** 2
        params = res.params.to_dict()
        diag.append({
            "asset": col,
            "mu": mean_r,
            "omega": params.get("omega", float("nan")) / 10000.0,  # percent² → fraction²
            "alpha": params.get("alpha[1]", float("nan")),
            "beta": params.get("beta[1]", float("nan")),
            "persistence": params.get("alpha[1]", 0) + params.get("beta[1]", 0),
        })
    return std_resid, last_var, diag


def fhs_paths(
    returns_df: pd.DataFrame,
    n_paths: int,
    horizon_days: int,
    seed: int,
    chunk_size: int = 5000,
) -> tuple[np.ndarray, list[dict]]:
    """Filtered Historical Simulation paths.

    1. Fit GARCH(1,1) per asset
    2. Compute standardized residuals
    3. For each path: starting from last conditional variance, sample joint
       residual rows (preserve cross-correlation), simulate GARCH vol forward,
       reconstruct returns = mu + vol * residual
    """
    std_resid, last_var, diag = fit_garch_filters(returns_df)
    T, A = std_resid.shape

    means = np.array([d["mu"] for d in diag])
    omegas = np.array([d["omega"] for d in diag])
    alphas = np.array([d["alpha"] for d in diag])
    betas = np.array([d["beta"] for d in diag])

    rng = np.random.default_rng(seed)
    out = np.empty((n_paths, horizon_days, A), dtype=np.float32)

    for start in range(0, n_paths, chunk_size):
        n = min(chunk_size, n_paths - start)
        # Sample T-indexed rows for residuals (joint across assets)
        idx = rng.integers(0, T, size=(n, horizon_days))
        resid = std_resid[idx]  # (n, horizon_days, A)

        # Forward-simulate GARCH variance per path per asset (vectorized over path)
        var = np.tile(last_var, (n, 1))  # (n, A)
        # Need last innovation to feed alpha term; use 0 as warm-start (after burn-in this stabilizes)
        last_eps_sq = np.zeros((n, A))
        path = np.empty((n, horizon_days, A), dtype=np.float32)
        for t in range(horizon_days):
            var = omegas + alphas * last_eps_sq + betas * var
            vol = np.sqrt(var)
            ret = means + vol * resid[:, t, :]
            path[:, t, :] = ret.astype(np.float32)
            last_eps_sq = (vol * resid[:, t, :]) ** 2

        out[start:start + n] = path

    return out, diag


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    fake_rets = pd.DataFrame(
        rng.standard_t(df=6, size=(500, 3)) * 0.012 + 0.0005,
        columns=["A", "B", "C"],
    )
    paths, diag = fhs_paths(fake_rets, n_paths=500, horizon_days=252, seed=42)
    print(f"Paths shape: {paths.shape}")
    for d in diag:
        print(f"  {d['asset']}  μ={d['mu']:+.5f}  ω={d['omega']:.2e}  α={d['alpha']:.3f}  β={d['beta']:.3f}  persist={d['persistence']:.3f}")
    print(f"Mean path return: {paths.mean():+.5f}")
    print(f"Std path return:  {paths.std():.5f}")
