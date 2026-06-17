"""Regime-switching engine via 2-state Gaussian HMM.

Fits a 2-state HMM (bull/bear) on equal-weight portfolio returns.
Bootstraps by simulating Markov chain through states + sampling return rows
from days assigned to current regime via Viterbi decode.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def fit_2state_hmm(returns_df: pd.DataFrame):
    """Fit 2-state Gaussian HMM on equal-weighted portfolio returns.

    Returns: (hmm_model, viterbi_states, diagnostics_dict)
    """
    from hmmlearn import hmm
    port_rets = returns_df.mean(axis=1).values.reshape(-1, 1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = hmm.GaussianHMM(n_components=2, covariance_type="full",
                                 n_iter=200, random_state=42)
        model.fit(port_rets)
    states = model.predict(port_rets)

    # Sort states: 0=bear (lower mean), 1=bull (higher mean)
    means = model.means_.flatten()
    if means[0] > means[1]:
        # Swap
        states = 1 - states
        means = means[::-1]
        covars = model.covars_[::-1]
        trans = model.transmat_[::-1][:, ::-1]
        startprob = model.startprob_[::-1]
    else:
        covars = model.covars_
        trans = model.transmat_
        startprob = model.startprob_

    diag = {
        "transitionMatrix": trans.tolist(),
        "startProb": startprob.tolist(),
        "bearMeanDaily": float(means[0]),
        "bullMeanDaily": float(means[1]),
        "bearVolDaily": float(np.sqrt(covars[0][0, 0])),
        "bullVolDaily": float(np.sqrt(covars[1][0, 0])),
        "stationaryDist": _stationary_distribution(trans).tolist(),
        "bearFraction": float(np.mean(states == 0)),
    }
    return states, trans, diag


def _stationary_distribution(P: np.ndarray) -> np.ndarray:
    """Compute stationary distribution of 2x2 transition matrix."""
    # Eigenvector at eigenvalue 1
    vals, vecs = np.linalg.eig(P.T)
    idx = np.argmin(np.abs(vals - 1))
    pi = np.real(vecs[:, idx])
    pi = pi / pi.sum()
    return np.abs(pi)


def regime_switch_paths(
    returns_df: pd.DataFrame,
    n_paths: int,
    horizon_days: int,
    seed: int,
    chunk_size: int = 2000,
):
    """Generate paths via regime-switching bootstrap.

    1. Fit HMM, get state assignments via Viterbi
    2. For each path: simulate state sequence via Markov chain
    3. At each step, sample a row from historical days in that state

    Returns: (paths_array, diagnostics)
    """
    states, trans, diag = fit_2state_hmm(returns_df)
    R = returns_df.values  # (T, A)
    T, A = R.shape

    bear_idx = np.where(states == 0)[0]
    bull_idx = np.where(states == 1)[0]
    state_idx = [bear_idx, bull_idx]

    rng = np.random.default_rng(seed)
    out = np.empty((n_paths, horizon_days, A), dtype=np.float32)

    pi_stationary = _stationary_distribution(trans)

    for start in range(0, n_paths, chunk_size):
        n = min(chunk_size, n_paths - start)

        # Initial state from stationary distribution
        cur_state = rng.choice(2, size=n, p=pi_stationary)

        for t in range(horizon_days):
            # For each path, sample a row from current state's day pool
            for s in range(2):
                mask = cur_state == s
                if not np.any(mask):
                    continue
                m = mask.sum()
                pool = state_idx[s]
                sample = rng.choice(pool, size=m)
                out[start:start + n][mask, t, :] = R[sample]

            # Transition to next state
            if t < horizon_days - 1:
                rand = rng.random(n)
                cur_state = np.where(
                    rand < trans[cur_state, 1],
                    1,
                    np.where(rand < (trans[cur_state, 0] + trans[cur_state, 1]),
                             cur_state,  # keep
                             cur_state)
                )
                # Simpler: for each path, sample new state from P[cur_state]
                # Use trans[cur_state] as 2x prob vector
                trans_row = trans[cur_state]  # (n, 2)
                new_state = (rng.random(n) >= trans_row[:, 0]).astype(int)
                cur_state = new_state

    return out, diag


if __name__ == "__main__":
    # Smoke test
    rng = np.random.default_rng(42)
    fake = pd.DataFrame(rng.normal(0.0005, 0.012, (500, 3)), columns=["A", "B", "C"])
    paths, diag = regime_switch_paths(fake, n_paths=500, horizon_days=252, seed=42)
    print(f"Paths shape: {paths.shape}")
    print(f"Bear mean daily: {diag['bearMeanDaily']:+.5f}")
    print(f"Bull mean daily: {diag['bullMeanDaily']:+.5f}")
    print(f"Bear vol daily: {diag['bearVolDaily']:.5f}")
    print(f"Bull vol daily: {diag['bullVolDaily']:.5f}")
    print(f"Stationary distribution: bear={diag['stationaryDist'][0]:.2f}, bull={diag['stationaryDist'][1]:.2f}")
