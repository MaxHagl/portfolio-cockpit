"""Portfolio optimizer using Monte Carlo + risk-adjusted return objective.

Pipeline:
1. Build universe: all cached ETF candidates + long-history indices
2. Align returns matrix on common business-day index
3. Generate bootstrap return paths once (shared across all candidate portfolios)
4. Sample N random portfolios (sparse Dirichlet, cardinality K≤8, min weight 5%)
5. For each portfolio: compute wealth → terminal/maxDD/CVaR/TU → risk score → Sharpe-like
6. Rank by Sharpe-like, output top-10 + scatter (return vs risk) + baseline comparison

Output: data/portfolio-optimization.json
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mc_data import TRADING_DAYS_PER_YEAR, load_holdings_meta, to_business_day_returns
from mc_engines.bootstrap import select_block_length_multi, stationary_bootstrap_paths
from mc_riskscore import composite_risk_score, risk_band, sharpe_like

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
SEED = 20260617
HORIZON_YEARS = 15
HORIZON_DAYS = HORIZON_YEARS * TRADING_DAYS_PER_YEAR

import os as _os
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)

PATHS = int(_os.environ.get("MC_OPT_PATHS", "10000"))
N_PORTFOLIOS = int(_os.environ.get("MC_OPT_N_PORTFOLIOS", "50000"))
MAX_CARDINALITY = int(_os.environ.get("MC_OPT_CARDINALITY", "8"))
MIN_WEIGHT = float(_os.environ.get("MC_OPT_MIN_WEIGHT", "0.05"))


def load_universe() -> tuple[pd.DataFrame, dict]:
    """Load all available cached candidates into aligned returns matrix.

    Returns: (df of daily simple returns, metadata dict)
    """
    # Get all cache files (excluding index/macro/manifest)
    candidates = []
    for f in CACHE.glob("*.json"):
        name = f.stem
        if name.startswith("_") or name == "manifest":
            continue
        try:
            raw = json.loads(f.read_text())
            if raw.get("source") != "yahoo" or len(raw.get("points", [])) < 250:
                continue
            candidates.append((name, raw["points"]))
        except Exception:
            continue

    # Load metadata for labels
    holdings_meta = load_holdings_meta()
    holding_ids = {h["id"] for h in holdings_meta["holdings"]}

    # Build series
    series_by_id = {}
    asset_meta = {}
    for hid, pts in candidates:
        idx = pd.to_datetime([p["t"] for p in pts], unit="ms", utc=True).tz_localize(None).normalize()
        vals = [p["c"] for p in pts]
        prices = pd.Series(vals, index=idx, name=hid)
        prices = prices[~prices.index.duplicated(keep="last")].sort_index()
        rets = to_business_day_returns(prices)
        if len(rets) < 250:
            continue
        series_by_id[hid] = rets
        asset_meta[hid] = {
            "id": hid,
            "isHolding": hid in holding_ids,
            "nDays": int(len(rets)),
            "firstDate": str(rets.index.min().date()),
            "lastDate": str(rets.index.max().date()),
        }

    # Align on inner-join window
    df = pd.concat(series_by_id.values(), axis=1, join="inner").dropna(how="any")
    df.columns = list(series_by_id.keys())
    meta = {
        "nAssets": int(df.shape[1]),
        "windowStart": str(df.index.min().date()),
        "windowEnd": str(df.index.max().date()),
        "windowDays": int(len(df)),
        "windowYears": float((df.index.max() - df.index.min()).days / 365.25),
        "perAsset": asset_meta,
    }
    return df, meta


def sample_sparse_portfolios(
    n_samples: int,
    n_assets: int,
    max_k: int,
    min_weight: float,
    seed: int,
) -> np.ndarray:
    """Generate (n_samples, n_assets) weight matrix.

    Each row: K ≤ max_k non-zero weights summing to 1, each >= min_weight.
    """
    rng = np.random.default_rng(seed)
    weights = np.zeros((n_samples, n_assets), dtype=np.float32)
    for i in range(n_samples):
        k = int(rng.integers(2, max_k + 1))
        subset = rng.choice(n_assets, size=k, replace=False)
        # Dirichlet with concentration tuned for diversity
        alpha = np.ones(k)
        w = rng.dirichlet(alpha)
        # Enforce minimum: if any below min, redistribute
        if w.min() < min_weight:
            w = np.maximum(w, min_weight)
            w = w / w.sum()
        weights[i, subset] = w.astype(np.float32)
    return weights


def score_portfolios_batched(
    weights: np.ndarray,
    paths: np.ndarray,
    starting_eur: float,
    horizon_years: float,
    batch_size: int = 32,
) -> np.ndarray:
    """For each row of weights, compute risk score + objective.

    Returns recarray with columns: terminal_med, ann_ret_med, max_dd_med,
        risk_score, sharpe_like, vol_med, tu_frac, p10_terminal
    """
    N = weights.shape[0]
    P, T, A = paths.shape
    daily_ann_factor = np.sqrt(TRADING_DAYS_PER_YEAR)

    result = np.zeros(N, dtype=[
        ("terminal_med", "f4"), ("ann_ret_med", "f4"),
        ("max_dd_med", "f4"), ("risk_score", "f4"),
        ("sharpe_like", "f4"), ("vol_med", "f4"),
        ("p10_terminal", "f4"), ("p90_terminal", "f4"),
        ("vol_comp", "f4"), ("dd_comp", "f4"),
        ("cvar_comp", "f4"), ("tu_comp", "f4"),
    ])

    for start in range(0, N, batch_size):
        end = min(start + batch_size, N)
        B = end - start
        w_batch = weights[start:end]  # (B, A)
        # Portfolio returns (B, P, T) = einsum('ba,pta->bpt', w_batch, paths)
        port_rets = np.einsum("ba,pta->bpt", w_batch, paths)
        # Wealth (B, P, T+1)
        wealth = np.empty((B, P, T + 1), dtype=np.float32)
        wealth[:, :, 0] = starting_eur
        wealth[:, :, 1:] = starting_eur * np.cumprod(1 + port_rets, axis=2)

        terminal = wealth[:, :, -1]  # (B, P)
        # Max DD per (batch, path)
        peak = np.maximum.accumulate(wealth, axis=2)
        dd = wealth / peak - 1
        max_dd = dd.min(axis=2)  # (B, P)
        # Time underwater
        underwater = (dd < -0.001).sum(axis=2)  # (B, P)
        # Realized vol per path
        log_rets = np.log(np.maximum(wealth[:, :, 1:], 1e-9) / np.maximum(wealth[:, :, :-1], 1e-9))
        ann_vol = log_rets.std(axis=2) * daily_ann_factor  # (B, P)
        # Ann return
        terminal_safe = np.maximum(terminal, 1.0)
        multiple = terminal_safe / starting_eur
        ann_ret = multiple ** (1.0 / horizon_years) - 1  # (B, P)

        for j in range(B):
            risk = composite_risk_score(
                terminal[j], max_dd[j], ann_vol[j], underwater[j],
                starting_eur, horizon_years,
            )
            med_ret = float(np.median(ann_ret[j]))
            result[start + j]["terminal_med"] = float(np.median(terminal[j]))
            result[start + j]["ann_ret_med"] = med_ret
            result[start + j]["max_dd_med"] = float(np.median(max_dd[j]))
            result[start + j]["vol_med"] = float(np.median(ann_vol[j]))
            result[start + j]["risk_score"] = risk["score"]
            result[start + j]["sharpe_like"] = sharpe_like(med_ret, risk["score"])
            result[start + j]["p10_terminal"] = float(np.quantile(terminal[j], 0.10))
            result[start + j]["p90_terminal"] = float(np.quantile(terminal[j], 0.90))
            result[start + j]["vol_comp"] = risk["components"]["vol"]
            result[start + j]["dd_comp"] = risk["components"]["dd"]
            result[start + j]["cvar_comp"] = risk["components"]["cvar"]
            result[start + j]["tu_comp"] = risk["components"]["tu"]
    return result


def main():
    t_start = time.time()
    print("=== Portfolio Optimizer (MC-based) ===\n")

    print("Loading universe...")
    df, universe_meta = load_universe()
    print(f"  Universe: {universe_meta['nAssets']} assets, {universe_meta['windowStart']} → {universe_meta['windowEnd']} ({universe_meta['windowYears']:.1f}y, {universe_meta['windowDays']} days)")
    asset_order = list(df.columns)
    print(f"  Assets: {asset_order}\n")

    print(f"Generating {PATHS} bootstrap paths × {HORIZON_DAYS} days × {len(asset_order)} assets...")
    t = time.time()
    block_len = select_block_length_multi(df)
    paths = stationary_bootstrap_paths(df, PATHS, HORIZON_DAYS, block_len, seed=SEED)
    print(f"  Paths: {paths.shape} ({paths.nbytes/1e9:.1f}GB), bl={block_len}, {time.time()-t:.1f}s\n")

    print(f"Sampling {N_PORTFOLIOS} random portfolios (K≤{MAX_CARDINALITY}, min weight {MIN_WEIGHT*100:.0f}%)...")
    t = time.time()
    weights = sample_sparse_portfolios(N_PORTFOLIOS, len(asset_order), MAX_CARDINALITY, MIN_WEIGHT, seed=SEED + 1)
    print(f"  Weights: {weights.shape}, {time.time()-t:.1f}s\n")

    # Add baseline as an explicit portfolio to compare
    meta = load_holdings_meta()
    baseline_w_dict = meta["baseline"]["weights"]
    starting_eur = meta["totalEur"]
    baseline_w = np.array([baseline_w_dict.get(a, 0) for a in asset_order], dtype=np.float32)
    weights = np.vstack([baseline_w[np.newaxis, :], weights])  # baseline as row 0
    N_TOTAL = weights.shape[0]
    print(f"  Total portfolios (with baseline): {N_TOTAL}\n")

    print(f"Scoring portfolios (batched)...")
    t = time.time()
    results = score_portfolios_batched(weights, paths, starting_eur, HORIZON_YEARS, batch_size=64)
    print(f"  Scored {N_TOTAL} portfolios in {time.time()-t:.1f}s ({(time.time()-t)*1000/N_TOTAL:.1f}ms each)\n")

    # Rank by Sharpe-like
    rank_idx = np.argsort(-results["sharpe_like"])
    baseline_idx = 0
    baseline_rank = int(np.where(rank_idx == baseline_idx)[0][0]) + 1
    print(f"Baseline rank: {baseline_rank} / {N_TOTAL}")
    print(f"  Baseline: Sharpe-like={results[baseline_idx]['sharpe_like']:.2f}, risk={results[baseline_idx]['risk_score']:.1f}, median_ret={results[baseline_idx]['ann_ret_med']*100:+.2f}%")

    top_n = 10
    top_idx = rank_idx[:top_n]
    print(f"\nTop {top_n}:")
    print(f"{'rank':4s}  {'sharpe':>6s}  {'risk':>5s}  {'ret':>7s}  {'median_term':>11s}  composition")
    for r, idx in enumerate(top_idx, 1):
        w = weights[idx]
        nonzero = [(asset_order[i], float(w[i])) for i in range(len(asset_order)) if w[i] > 0.01]
        nonzero.sort(key=lambda x: -x[1])
        comp = " / ".join(f"{a} {w*100:.0f}%" for a, w in nonzero)
        print(f"{r:4d}  {results[idx]['sharpe_like']:6.2f}  {results[idx]['risk_score']:5.1f}  {results[idx]['ann_ret_med']*100:+6.2f}%  €{results[idx]['terminal_med']:11,.0f}  {comp}")

    # Build output
    top_portfolios = []
    for r, idx in enumerate(top_idx, 1):
        w = weights[idx]
        weights_dict = {asset_order[i]: float(w[i]) for i in range(len(asset_order)) if w[i] > 1e-4}
        top_portfolios.append({
            "rank": r,
            "weights": weights_dict,
            "sharpeLike": float(results[idx]["sharpe_like"]),
            "riskScore": float(results[idx]["risk_score"]),
            "riskBand": risk_band(results[idx]["risk_score"]),
            "riskComponents": {
                "vol": float(results[idx]["vol_comp"]),
                "dd": float(results[idx]["dd_comp"]),
                "cvar": float(results[idx]["cvar_comp"]),
                "tu": float(results[idx]["tu_comp"]),
            },
            "medianTerminal": float(results[idx]["terminal_med"]),
            "p10Terminal": float(results[idx]["p10_terminal"]),
            "p90Terminal": float(results[idx]["p90_terminal"]),
            "medianAnnReturn": float(results[idx]["ann_ret_med"]),
            "medianMaxDrawdown": float(results[idx]["max_dd_med"]),
            "medianAnnVol": float(results[idx]["vol_med"]),
        })

    # Scatter data: for ALL portfolios, just risk + return + sharpe + terminal
    scatter = []
    # Subsample for JSON size: take 5000 random + always include top 100
    sample_idx = np.concatenate([rank_idx[:100], np.random.default_rng(SEED).choice(N_TOTAL, size=min(5000, N_TOTAL), replace=False)])
    sample_idx = np.unique(sample_idx)
    for idx in sample_idx:
        scatter.append({
            "risk": float(results[idx]["risk_score"]),
            "return": float(results[idx]["ann_ret_med"]),
            "sharpe": float(results[idx]["sharpe_like"]),
            "terminal": float(results[idx]["terminal_med"]),
        })

    # Asset usage frequency in top portfolios
    top_500 = rank_idx[:500]
    asset_usage = {a: 0 for a in asset_order}
    asset_avg_weight = {a: 0.0 for a in asset_order}
    for idx in top_500:
        w = weights[idx]
        for i, a in enumerate(asset_order):
            if w[i] > 0.01:
                asset_usage[a] += 1
                asset_avg_weight[a] += float(w[i])
    for a in asset_order:
        if asset_usage[a] > 0:
            asset_avg_weight[a] /= asset_usage[a]
    asset_ranking = sorted(
        [{"id": a, "frequencyInTop500": asset_usage[a], "avgWeightWhenIncluded": asset_avg_weight[a]} for a in asset_order],
        key=lambda x: -x["frequencyInTop500"],
    )

    baseline_summary = {
        "rank": baseline_rank,
        "sharpeLike": float(results[0]["sharpe_like"]),
        "riskScore": float(results[0]["risk_score"]),
        "riskBand": risk_band(results[0]["risk_score"]),
        "medianTerminal": float(results[0]["terminal_med"]),
        "medianAnnReturn": float(results[0]["ann_ret_med"]),
        "medianMaxDrawdown": float(results[0]["max_dd_med"]),
        "weights": {a: float(baseline_w[i]) for i, a in enumerate(asset_order) if baseline_w[i] > 1e-4},
    }

    elapsed = time.time() - t_start

    output = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "computeSeconds": elapsed,
        "inputs": {
            "startingEur": starting_eur,
            "horizonYears": HORIZON_YEARS,
            "paths": PATHS,
            "nPortfoliosSampled": N_PORTFOLIOS,
            "nPortfoliosTotal": N_TOTAL,
            "maxCardinality": MAX_CARDINALITY,
            "minWeight": MIN_WEIGHT,
            "objectiveFunction": "Sharpe-like = median_ann_return / risk_score × 100",
            "blockLength": int(block_len),
        },
        "universe": universe_meta,
        "baseline": baseline_summary,
        "topPortfolios": top_portfolios,
        "scatter": scatter,
        "assetRanking": asset_ranking,
    }

    out_path = ROOT / "data" / "portfolio-optimization.json"
    out_path.write_text(json.dumps(output, indent=1, default=str))
    print(f"\n✓ Wrote {out_path.name} ({out_path.stat().st_size/1e6:.1f} MB)")
    print(f"Total elapsed: {elapsed/60:.1f} min")


if __name__ == "__main__":
    main()
