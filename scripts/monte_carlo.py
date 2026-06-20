"""Monte Carlo orchestrator — produces data/monte-carlo.json.

Run via: npm run monte-carlo  (or directly: .venv/bin/python scripts/monte_carlo.py)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mc_data import (
    TRADING_DAYS_PER_YEAR,
    load_holdings_meta,
    load_index,
    summarize_series,
    to_business_day_returns,
)
from mc_proxies import build_augmented_matrix
from mc_engines.bootstrap import (
    select_block_length_multi,
    stationary_bootstrap_paths,
)
from mc_engines.parametric_t import parametric_t_paths
from mc_engines.fhs import fhs_paths
from mc_engines.cross_validation import expanding_window_studies
from mc_metrics import (
    apply_inflation,
    fan_chart,
    goal_probabilities,
    histogram,
    probability_callouts,
    quantile_summary,
    sample_paths,
    simulate_portfolio_wealth,
    compute_path_metrics,
)
from mc_tax import apply_vorabpauschale
from mc_fx import apply_fx_overlay, sample_fx_paths
from mc_stress import run_stress_replay
from mc_riskscore import composite_risk_score, risk_band, sharpe_like


ROOT = Path(__file__).resolve().parent.parent
SEED = 20260617
HORIZON_YEARS = 15
HORIZON_DAYS = HORIZON_YEARS * TRADING_DAYS_PER_YEAR

# Path budgets — overridable via env vars for profiling vs full runs
import os as _os
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)
PATHS_BOOTSTRAP   = int(_os.environ.get("MC_PATHS_BOOTSTRAP", "50000"))
PATHS_PARAMETRIC  = int(_os.environ.get("MC_PATHS_PARAMETRIC", "25000"))
PATHS_FHS         = int(_os.environ.get("MC_PATHS_FHS", "10000"))
PATHS_CV          = int(_os.environ.get("MC_PATHS_CV", "3000"))

# Inflation assumption
INFLATION_RATE = 0.02

# Goal-based targets (EUR)
GOAL_TARGETS = [21302, 30000, 50000, 75000, 100000, 150000, 200000, 300000, 500000]


def weights_hash(weights: dict[str, float]) -> str:
    """SHA-256 hash of weights dict, sorted by key."""
    canonical = json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def build_scenarios(baseline_weights: dict[str, float], asset_order: list[str]) -> dict:
    """Define the 5 comparison scenarios. Returns dict of {key: (label, weights_array)}.

    weights_array is np.ndarray of len(asset_order) — zero-padded for missing keys.
    """
    def to_array(w_dict: dict[str, float]) -> np.ndarray:
        return np.array([w_dict.get(a, 0.0) for a in asset_order])

    return {
        "baseline":    {"label": "Current baseline portfolio", "weights": to_array(baseline_weights)},
        "vwceOnly":    {"label": "100% VWCE (do-nothing-fancy)", "weights": to_array({"VWCE": 1.0})},
        "equalWeight": {"label": f"Equal-weight ({100/len(asset_order):.1f}% each)", "weights": to_array({a: 1.0/len(asset_order) for a in asset_order})},
        "techOnly":    {"label": "Tech only (100% BGF)",         "weights": to_array({"BGF": 1.0})},
        "councilFix":  {"label": "Cheap-passive (VWCE 70 / IUSA 15 / JREM 15)", "weights": to_array({"VWCE": 0.70, "IUSA": 0.15, "JREM": 0.15})},
    }


def per_asset_ters(asset_order: list[str], meta: dict) -> np.ndarray:
    ter_map = {h["id"]: h["ter"] for h in meta["holdings"]}
    return np.array([ter_map.get(a, 0.0) for a in asset_order])


def run_scenario_metrics(
    paths: np.ndarray,
    weights: np.ndarray,
    starting_eur: float,
    ter_annual: np.ndarray,
    rebalance: str = "quarterly",
) -> dict:
    """Full per-scenario distributional output."""
    wealth = simulate_portfolio_wealth(paths, weights, starting_eur, ter_annual, rebalance)
    metrics = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)

    return {
        "wealth": wealth,
        "metrics": metrics,
    }


def metrics_to_dict(metrics: dict, wealth: np.ndarray, weights: np.ndarray, label: str,
                    asset_order: list[str], starting_eur: float, full: bool = True) -> dict:
    """Convert metrics to JSON-shaped dict.

    full=True: include fan chart, sample paths, histograms (primary scenarios)
    full=False: only summary stats (for sensitivity variants)
    """
    risk = composite_risk_score(
        metrics["terminal"], metrics["maxDrawdown"], metrics["annVol"],
        metrics["timeUnderwaterDays"], starting_eur, HORIZON_YEARS
    )
    out = {
        "label": label,
        "weights": {a: float(w) for a, w in zip(asset_order, weights) if w > 1e-6},
        "terminal": quantile_summary(metrics["terminal"]),
        "annReturn": quantile_summary(metrics["annReturn"]),
        "maxDrawdown": quantile_summary(metrics["maxDrawdown"]),
        "annVol": quantile_summary(metrics["annVol"]),
        "timeUnderwaterDays": quantile_summary(metrics["timeUnderwaterDays"]),
        "probabilities": probability_callouts(metrics, starting_eur),
        "goalProbabilities": goal_probabilities(metrics, GOAL_TARGETS),
        "riskScore": risk["score"],
        "riskBand": risk_band(risk["score"]),
        "riskComponents": risk["components"],
        "sharpeLike": sharpe_like(float(np.median(metrics["annReturn"])), risk["score"]),
    }
    if full:
        out["fanChart"] = fan_chart(wealth, step_days=21)
        out["samplePaths"] = sample_paths(wealth, n_samples=50, step_days=21)
        out["terminalHistogram"] = histogram(metrics["terminal"], bins=60, log_x=True)
        out["annReturnHistogram"] = histogram(metrics["annReturn"], bins=60)
        out["maxDdHistogram"] = histogram(metrics["maxDrawdown"], bins=40)
    return out


def main():
    t_start = time.time()
    print("=== Monte Carlo Portfolio Analysis ===")
    print(f"Seed: {SEED}, Horizon: {HORIZON_YEARS}y, Daily steps: {HORIZON_DAYS}")
    print()

    meta = load_holdings_meta()
    baseline_w = meta["baseline"]["weights"]
    starting_eur = meta["totalEur"]

    print(f"Loading + augmenting returns matrix...")
    t = time.time()
    native_df, augmented_df, fits = build_augmented_matrix()
    asset_order = list(augmented_df.columns)
    print(f"  Native:    {native_df.shape}, {native_df.index.min().date()} → {native_df.index.max().date()}")
    print(f"  Augmented: {augmented_df.shape}, {augmented_df.index.min().date()} → {augmented_df.index.max().date()}")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    ter_annual = per_asset_ters(asset_order, meta)
    print(f"  TER (annual): {dict(zip(asset_order, ter_annual.round(4)))}")
    weighted_ter = float(sum(baseline_w.get(a, 0) * ter_annual[i] for i, a in enumerate(asset_order)))
    print(f"  Blended baseline TER: {weighted_ter*100:.3f}%/yr")

    scenarios = build_scenarios(baseline_w, asset_order)
    print(f"\nScenarios: {list(scenarios.keys())}\n")

    # ─────── Engine 1: Stationary Block Bootstrap (PRIMARY) ───────
    print("Engine 1/4: Stationary block bootstrap")
    t = time.time()
    block_length = select_block_length_multi(augmented_df)
    print(f"  Selected block length: {block_length} days")
    print(f"  Generating {PATHS_BOOTSTRAP} paths × {HORIZON_DAYS} days × {len(asset_order)} assets...")
    boot_paths = stationary_bootstrap_paths(augmented_df, PATHS_BOOTSTRAP, HORIZON_DAYS,
                                             block_length, seed=SEED, chunk_size=5000)
    print(f"  Bootstrap paths shape: {boot_paths.shape}  (~{boot_paths.nbytes / 1e9:.1f}GB)")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    print("  Running scenarios...")
    bootstrap_results = {}
    for sc_key, sc in scenarios.items():
        t_sc = time.time()
        wealth = simulate_portfolio_wealth(boot_paths, sc["weights"], starting_eur, ter_annual, "quarterly")
        metrics = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)
        bootstrap_results[sc_key] = metrics_to_dict(metrics, wealth, sc["weights"], sc["label"], asset_order, starting_eur)
        print(f"    {sc_key:13s}: median_terminal=€{bootstrap_results[sc_key]['terminal']['median']:,.0f}  "
              f"median_ann={bootstrap_results[sc_key]['annReturn']['median']*100:+.2f}%  "
              f"P(loss)={bootstrap_results[sc_key]['probabilities']['loss']*100:.1f}%  "
              f"({time.time()-t_sc:.1f}s)")

    # ─────── Tax modeling on baseline (Vorabpauschale) ───────
    print("\n  Tax modeling (Vorabpauschale)...")
    baseline_wealth_pretax = simulate_portfolio_wealth(boot_paths, scenarios["baseline"]["weights"],
                                                       starting_eur, ter_annual, "quarterly")
    baseline_wealth_posttax = apply_vorabpauschale(baseline_wealth_pretax, starting_eur,
                                                    horizon_years=HORIZON_YEARS)
    posttax_metrics = compute_path_metrics(baseline_wealth_posttax, starting_eur, HORIZON_YEARS)
    posttax_summary = metrics_to_dict(posttax_metrics, baseline_wealth_posttax, scenarios["baseline"]["weights"],
                                       "Baseline AFTER Vorabpauschale", asset_order, starting_eur, full=False)
    print(f"    median terminal after-tax: €{posttax_summary['terminal']['median']:,.0f}  "
          f"vs pre-tax: €{bootstrap_results['baseline']['terminal']['median']:,.0f}")

    # ─────── Real returns (inflation-adjusted) ───────
    print("\n  Real returns (2% inflation)...")
    real_wealth = apply_inflation(baseline_wealth_pretax, INFLATION_RATE, HORIZON_YEARS)
    real_metrics = compute_path_metrics(real_wealth, starting_eur, HORIZON_YEARS)
    real_summary = metrics_to_dict(real_metrics, real_wealth, scenarios["baseline"]["weights"],
                                    "Baseline (real, 2% inflation)", asset_order, starting_eur, full=False)
    print(f"    median real terminal: €{real_summary['terminal']['median']:,.0f}  "
          f"P(real loss)={real_summary['probabilities']['loss']*100:.1f}%")

    # ─────── Currency overlay (EUR/USD on baseline) ───────
    print("\n  EUR/USD currency overlay...")
    eurusd_rets = to_business_day_returns(load_index("EURUSD"))
    fx_paths = sample_fx_paths(eurusd_rets, n_paths=PATHS_BOOTSTRAP, horizon_days=HORIZON_DAYS, seed=SEED + 1)
    # Estimate USD exposure: ~65% of portfolio is USD assets
    USD_EXPOSURE = 0.65
    fx_wealth = apply_fx_overlay(baseline_wealth_pretax, fx_paths, USD_EXPOSURE)
    fx_metrics = compute_path_metrics(fx_wealth, starting_eur, HORIZON_YEARS)
    fx_summary = metrics_to_dict(fx_metrics, fx_wealth, scenarios["baseline"]["weights"],
                                  "Baseline + FX overlay (65% USD)", asset_order, starting_eur, full=False)
    # FX vol contribution: ratio of std of FX-adjusted terminal to std without FX
    nofx_terminal = baseline_wealth_pretax[:, -1]
    fx_terminal = fx_wealth[:, -1]
    fx_vol_contribution = float((np.std(fx_terminal) - np.std(nofx_terminal)) / np.std(nofx_terminal))
    print(f"    median FX-adjusted terminal: €{fx_summary['terminal']['median']:,.0f}  "
          f"FX adds {fx_vol_contribution*100:+.1f}% to terminal std")

    # ─────── Rebalancing sensitivity (baseline) ───────
    print("\n  Rebalancing sensitivity...")
    rebal_results = {}
    for rebal in ["daily", "monthly", "quarterly", "annual", "never"]:
        wealth_r = simulate_portfolio_wealth(boot_paths, scenarios["baseline"]["weights"], starting_eur, ter_annual, rebal)
        metrics_r = compute_path_metrics(wealth_r, starting_eur, HORIZON_YEARS)
        rebal_results[rebal] = metrics_to_dict(metrics_r, wealth_r, scenarios["baseline"]["weights"],
                                                f"Baseline rebalance={rebal}", asset_order, starting_eur, full=False)
        print(f"    {rebal:10s}: median=€{rebal_results[rebal]['terminal']['median']:,.0f}  "
              f"max_dd_med={rebal_results[rebal]['maxDrawdown']['median']*100:+.1f}%")

    del boot_paths  # free memory before next engine
    bootstrap_elapsed = time.time() - t
    print(f"  Bootstrap engine total: {bootstrap_elapsed:.1f}s\n")

    # ─────── Engine 2: Parametric Student-t ───────
    print("Engine 2/4: Parametric multivariate Student-t")
    t = time.time()
    print(f"  Generating {PATHS_PARAMETRIC} paths...")
    t_paths, t_diag = parametric_t_paths(augmented_df, PATHS_PARAMETRIC, HORIZON_DAYS, seed=SEED + 2)
    print(f"  Fitted ν: {t_diag['nu']:.2f}")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    parametric_results = {}
    for sc_key, sc in scenarios.items():
        wealth = simulate_portfolio_wealth(t_paths, sc["weights"], starting_eur, ter_annual, "quarterly")
        metrics = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)
        parametric_results[sc_key] = metrics_to_dict(metrics, wealth, sc["weights"], sc["label"], asset_order, starting_eur)
        print(f"    {sc_key:13s}: median_terminal=€{parametric_results[sc_key]['terminal']['median']:,.0f}")
    del t_paths

    # ─────── Engine 3: Filtered Historical Simulation (GARCH) ───────
    print("\nEngine 3/4: FHS with GARCH(1,1)")
    t = time.time()
    print(f"  Generating {PATHS_FHS} paths (GARCH fitting is slow)...")
    fhs_path_arr, garch_diag = fhs_paths(augmented_df, PATHS_FHS, HORIZON_DAYS, seed=SEED + 3, chunk_size=2000)
    print(f"  GARCH diagnostics:")
    for d in garch_diag:
        print(f"    {d['asset']:10s} α={d['alpha']:.3f} β={d['beta']:.3f} persist={d['persistence']:.3f}")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    fhs_results = {}
    for sc_key, sc in scenarios.items():
        wealth = simulate_portfolio_wealth(fhs_path_arr, sc["weights"], starting_eur, ter_annual, "quarterly")
        metrics = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)
        fhs_results[sc_key] = metrics_to_dict(metrics, wealth, sc["weights"], sc["label"], asset_order, starting_eur)
        print(f"    {sc_key:13s}: median_terminal=€{fhs_results[sc_key]['terminal']['median']:,.0f}")
    del fhs_path_arr

    # ─────── Engine 4: Expanding-window cross-validation ───────
    print("\nEngine 4/4: Expanding-window cross-validation")
    t = time.time()
    cv_studies = expanding_window_studies(augmented_df, n_paths=PATHS_CV,
                                           horizon_days=HORIZON_DAYS, seed=SEED + 4, n_windows=5)
    print(f"  Window studies ({len(cv_studies)}):")
    for s in cv_studies:
        print(f"    {s['window_start']} → {s['window_end']}  bl={s['blockLength']}  "
              f"med_term_mult={s['medianTerminalMultiple']:.2f}  med_max_dd={s['medianMaxDrawdown']*100:.1f}%")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    # ─────── Stress replays ───────
    print("\nStress replays (deterministic)...")
    t = time.time()
    stress_results = run_stress_replay(baseline_w, starting_eur)
    for k, v in stress_results.items():
        if v.get("available"):
            print(f"  {k:13s}: peak DD {v['peakDrawdown']*100:+.1f}%  trough €{v['troughEur']:,.0f}  "
                  f"recover {v.get('daysToRecover') or 'never'}d")
    print(f"  Elapsed: {time.time()-t:.1f}s")

    # ─────── Diagnostics ───────
    print("\nDiagnostics...")
    per_asset_stats = {}
    for col in augmented_df.columns:
        diag = summarize_series(augmented_df[col])
        diag["nativeStats"] = summarize_series(native_df[col]) if col in native_df.columns else None
        per_asset_stats[col] = diag

    correlation_aug = augmented_df.corr().round(4).to_dict()
    correlation_native = native_df.corr().round(4).to_dict()

    proxy_fits_dict = {}
    for hid, f in fits.items():
        proxy_fits_dict[hid] = {
            "proxyId": f.proxy_id,
            "eurConvert": getattr(f, "eur_convert", False),
            "lag": getattr(f, "lag", 0),
            "alphaAnnualized": f.alpha_daily * TRADING_DAYS_PER_YEAR,
            "beta": f.beta,
            "residSigmaAnnualized": f.resid_std * np.sqrt(TRADING_DAYS_PER_YEAR),
            "r2": f.r2,
            "nOverlap": f.n_overlap,
            "overlapStart": f.overlap_start,
            "overlapEnd": f.overlap_end,
            "nativeStart": f.native_start,
            "nativeEnd": f.native_end,
        }

    # ─────── Assemble final JSON ───────
    print("\nAssembling output JSON...")
    elapsed_total = time.time() - t_start

    output = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "computeSeconds": elapsed_total,
        "inputs": {
            "weightsHash": weights_hash(baseline_w),
            "weights": baseline_w,
            "startingEur": starting_eur,
            "horizonYears": HORIZON_YEARS,
            "tradingDaysPerYear": TRADING_DAYS_PER_YEAR,
            "pathsBootstrap": PATHS_BOOTSTRAP,
            "pathsParametricT": PATHS_PARAMETRIC,
            "pathsFhs": PATHS_FHS,
            "pathsCv": PATHS_CV,
            "blockLengthBootstrap": int(block_length),
            "terAnnualByAsset": dict(zip(asset_order, ter_annual.tolist())),
            "weightedTerAnnual": weighted_ter,
            "rebalancingCanonical": "quarterly",
            "inflationRate": INFLATION_RATE,
            "usdExposure": USD_EXPOSURE,
        },
        "history": {
            "augmentedWindow": {
                "start": str(augmented_df.index.min().date()),
                "end": str(augmented_df.index.max().date()),
                "days": len(augmented_df),
                "years": (augmented_df.index.max() - augmented_df.index.min()).days / 365.25,
            },
            "nativeWindow": {
                "start": str(native_df.index.min().date()),
                "end": str(native_df.index.max().date()),
                "days": len(native_df),
                "years": (native_df.index.max() - native_df.index.min()).days / 365.25,
            },
            "augmentation": proxy_fits_dict,
        },
        "engines": {
            "bootstrap": {"scenarios": bootstrap_results, "method": "stationary block bootstrap (Politis-Romano)"},
            "parametricT": {
                "scenarios": parametric_results,
                "method": "multivariate Student-t with Ledoit-Wolf shrunk covariance",
                "nu": t_diag["nu"],
            },
            "fhs": {
                "scenarios": fhs_results,
                "method": "filtered historical simulation, GARCH(1,1) per asset",
                "garch": garch_diag,
            },
            "crossValidation": {"windowStudies": cv_studies},
        },
        "rebalancingSensitivity": {"baseline": rebal_results},
        "taxModeling": {"baselinePosttax": posttax_summary},
        "realReturns": {"baseline2pct": real_summary},
        "currencyOverlay": {
            "baseline": fx_summary,
            "fxVolContribution": fx_vol_contribution,
        },
        "stress": stress_results,
        "diagnostics": {
            "perAssetStats": per_asset_stats,
            "correlationAugmented": correlation_aug,
            "correlationNative": correlation_native,
        },
    }

    out_path = ROOT / "data" / "monte-carlo.json"
    out_path.write_text(json.dumps(output, indent=1, default=str))
    size_mb = out_path.stat().st_size / 1e6
    print(f"\n✓ Wrote {out_path} ({size_mb:.1f} MB)")
    print(f"Total elapsed: {elapsed_total/60:.1f} min")


if __name__ == "__main__":
    main()
