"""Parametric Monte Carlo via multivariate Student-t with Ledoit-Wolf shrunk covariance.

Captures fat tails (via degrees of freedom) and cross-asset correlation (via shrunk Σ).
Used as a sanity check vs the bootstrap engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fit_mv_student_t(returns_df: pd.DataFrame, min_nu: float = 3.0, max_nu: float = 30.0):
    """Fit multivariate Student-t via method of moments (univariate ν from kurtosis).

    Returns:
        mu: (A,) mean vector
        Sigma: (A,A) Ledoit-Wolf shrunk covariance
        nu: degrees of freedom (median across assets, clamped)
    """
    from sklearn.covariance import LedoitWolf
    R = returns_df.values
    mu = R.mean(axis=0)

    lw = LedoitWolf().fit(R)
    Sigma = lw.covariance_

    # Estimate ν per asset from excess kurtosis: for t-dist, ex_kurt = 6/(ν-4) for ν>4
    nus = []
    for j in range(R.shape[1]):
        ex_kurt = pd.Series(R[:, j]).kurt()
        if ex_kurt > 0.5:
            nu = 6.0 / ex_kurt + 4.0
        else:
            nu = max_nu
        nus.append(np.clip(nu, min_nu, max_nu))
    nu = float(np.median(nus))
    return mu, Sigma, nu


def sample_mv_student_t(
    mu: np.ndarray,
    Sigma: np.ndarray,
    nu: float,
    n_paths: int,
    horizon_days: int,
    seed: int,
    chunk_size: int = 5000,
) -> np.ndarray:
    """Sample multivariate Student-t paths.

    Standard construction: X = mu + L Z / sqrt(W/nu)
    where L L' = Sigma, Z ~ N(0,I), W ~ chi²(nu).
    """
    A = len(mu)
    L = np.linalg.cholesky(Sigma)
    rng = np.random.default_rng(seed)
    out = np.empty((n_paths, horizon_days, A), dtype=np.float32)
    for start in range(0, n_paths, chunk_size):
        n = min(chunk_size, n_paths - start)
        Z = rng.standard_normal((n, horizon_days, A))
        W = rng.chisquare(nu, size=(n, horizon_days, 1))
        scale = np.sqrt(W / nu)
        T = Z / scale
        # apply Cholesky: shape (n, T, A) @ L.T → (n, T, A)
        path = T @ L.T + mu
        out[start:start + n] = path.astype(np.float32)
    return out


def parametric_t_paths(
    returns_df: pd.DataFrame,
    n_paths: int,
    horizon_days: int,
    seed: int,
    chunk_size: int = 5000,
) -> tuple[np.ndarray, dict]:
    """End-to-end: fit MV-t and sample paths."""
    mu, Sigma, nu = fit_mv_student_t(returns_df)
    paths = sample_mv_student_t(mu, Sigma, nu, n_paths, horizon_days, seed, chunk_size)
    diag = {
        "mu_daily": mu.tolist(),
        "sigma_daily_diag": np.sqrt(np.diag(Sigma)).tolist(),
        "nu": nu,
        "correlation": (Sigma / np.outer(np.sqrt(np.diag(Sigma)), np.sqrt(np.diag(Sigma)))).tolist(),
    }
    return paths, diag


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    fake_rets = pd.DataFrame(
        rng.standard_t(df=5, size=(500, 3)) * 0.012 + 0.0005,
        columns=["A", "B", "C"],
    )
    paths, diag = parametric_t_paths(fake_rets, n_paths=1000, horizon_days=252, seed=42)
    print(f"Paths shape: {paths.shape}")
    print(f"Fitted ν: {diag['nu']:.2f} (expected ~5)")
    print(f"Mean path return: {paths.mean():+.5f}  expected ~+0.0005")
    print(f"Std path return: {paths.std():.5f}   expected ~0.012")
