"""Monte Carlo v2 orchestrator — accumulation + retirement realism layer.

Produces:
- data/monte-carlo-accumulation.json: DCA sweep, long-history engine, regime engine,
  stochastic inflation, hedged, drawdown buy overlay, ESG drag, jump-diffusion, broker fees
- data/monte-carlo-retirement.json: 30y horizon, 4 withdrawal strategies, cap-gains at sale,
  depletion probabilities

Run via: npm run monte-carlo-v2 (or .venv/bin/python scripts/monte_carlo_v2.py)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mc_data import TRADING_DAYS_PER_YEAR, load_holdings_meta, load_index, to_business_day_returns
from mc_proxies import build_augmented_matrix
from mc_engines.bootstrap import select_block_length_multi, stationary_bootstrap_paths
from mc_engines.long_history import long_history_bootstrap_paths
from mc_engines.regime_switch import regime_switch_paths
from mc_long_history import build_long_history_matrix
from mc_metrics import (
    compute_path_metrics, simulate_portfolio_wealth, quantile_summary,
    fan_chart, sample_paths, histogram, probability_callouts, goal_probabilities,
    apply_inflation,
)
from mc_riskscore import composite_risk_score, risk_band, sharpe_like
from mc_tax import apply_vorabpauschale
from mc_capgains import compute_realized_gain_tax, apply_lump_sum_sale_tax, estimate_vorab_paid_during_phase
from mc_cashflows import build_dca_schedule, build_withdrawal_schedule, BROKER_FEES
from mc_inflation import bootstrap_inflation_paths, diagnostics as inflation_diagnostics
from mc_fx import sample_fx_paths
from mc_hedged import hedge_paths
from mc_drawdown_overlay import simulate_with_drawdown_buy
from mc_jump_diffusion import apply_jump_overlay

ROOT = Path(__file__).resolve().parent.parent
SEED = 20260617
HORIZON_YEARS = 15
HORIZON_DAYS = HORIZON_YEARS * TRADING_DAYS_PER_YEAR
HORIZON_DAYS_30 = 30 * TRADING_DAYS_PER_YEAR
INFLATION_RATE = 0.02
GOAL_TARGETS = [21302, 50000, 100000, 200000, 500000, 1000000]

import os as _os
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)

PATHS_BOOTSTRAP   = int(_os.environ.get("MC_V2_PATHS_BOOT", "30000"))
PATHS_LONG_HIST   = int(_os.environ.get("MC_V2_PATHS_LH", "30000"))
PATHS_REGIME      = int(_os.environ.get("MC_V2_PATHS_REGIME", "10000"))
PATHS_INFLATION   = int(_os.environ.get("MC_V2_PATHS_INFL", "30000"))
PATHS_RETIREMENT  = int(_os.environ.get("MC_V2_PATHS_RET", "20000"))


def weights_hash(weights: dict) -> str:
    canonical = json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def per_asset_ters(asset_order, meta):
    ter_map = {h["id"]: h["ter"] for h in meta["holdings"]}
    return np.array([ter_map.get(a, 0.0) for a in asset_order])


def summarize(metrics, wealth, weights, label, asset_order, starting_eur, full=True, total_contributed=None, horizon_yr=HORIZON_YEARS):
    risk = composite_risk_score(
        metrics["terminal"], metrics["maxDrawdown"], metrics["annVol"],
        metrics["timeUnderwaterDays"], starting_eur, horizon_yr
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
    if total_contributed is not None:
        out["totalContributed"] = float(np.median(total_contributed))
        out["totalContributedQ"] = quantile_summary(total_contributed)
    if full:
        out["fanChart"] = fan_chart(wealth, step_days=21)
        out["samplePaths"] = sample_paths(wealth, n_samples=30, step_days=21)
        out["terminalHistogram"] = histogram(metrics["terminal"], bins=50, log_x=True)
        out["maxDdHistogram"] = histogram(metrics["maxDrawdown"], bins=40)
    return out


def main():
    t_start = time.time()
    print("=== Monte Carlo v2 — Accumulation + Retirement ===")

    meta = load_holdings_meta()
    baseline_w = meta["baseline"]["weights"]
    starting_eur = meta["totalEur"]

    print(f"Building augmented + long-history matrices...")
    _, augmented_df, fits = build_augmented_matrix()
    long_df = build_long_history_matrix()
    asset_order = list(augmented_df.columns)
    weights_baseline = np.array([baseline_w.get(a, 0) for a in asset_order])
    ter_annual = per_asset_ters(asset_order, meta)

    # ──────────────────────────────────────────────────────
    # ACCUMULATION JSON
    # ──────────────────────────────────────────────────────
    print("\n── Building accumulation JSON ──")
    accum = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "inputs": {
            "weightsHash": weights_hash(baseline_w),
            "weights": baseline_w,
            "startingEur": starting_eur,
            "horizonYears": HORIZON_YEARS,
            "pathsBootstrap": PATHS_BOOTSTRAP,
            "pathsLongHistory": PATHS_LONG_HIST,
            "pathsRegime": PATHS_REGIME,
            "pathsInflation": PATHS_INFLATION,
            "terAnnualByAsset": dict(zip(asset_order, ter_annual.tolist())),
        },
    }

    # Engine A: bootstrap on augmented matrix (for DCA sweeps + overlays)
    print("Engine A: bootstrap on augmented matrix (DCA sweep + overlays)")
    t = time.time()
    block_len = select_block_length_multi(augmented_df)
    boot_paths = stationary_bootstrap_paths(augmented_df, PATHS_BOOTSTRAP, HORIZON_DAYS,
                                             block_len, seed=SEED)
    print(f"  Paths: {boot_paths.shape}, block={block_len}, {time.time()-t:.1f}s")

    # DCA sweep
    print("\n  DCA sweep (€0/€50/€100/€200/€500/mo)...")
    dca_levels = [0, 50, 100, 200, 500]
    dca_results = {}
    for monthly in dca_levels:
        cf = build_dca_schedule(monthly, HORIZON_DAYS)
        wealth = simulate_portfolio_wealth(boot_paths, weights_baseline, starting_eur,
                                            ter_annual, "quarterly", cashflows=cf)
        m = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)
        total_contrib = np.full(boot_paths.shape[0], cf.sum())
        dca_results[f"eur{monthly}"] = summarize(m, wealth, weights_baseline,
                                                  f"DCA €{monthly}/mo", asset_order, starting_eur,
                                                  full=(monthly in [0, 50, 500]),
                                                  total_contributed=total_contrib)
        print(f"    €{monthly:4d}/mo: median terminal=€{m['terminal'].mean():,.0f}  P(loss)={(m['terminal']<starting_eur).mean()*100:.2f}%")
    accum["dcaSweep"] = dca_results

    # Salary growth: €50/mo + 3% growth
    print("\n  Salary growth scenarios (€50/mo with vs without 3% growth)...")
    cf_grow = build_dca_schedule(50, HORIZON_DAYS, salary_growth_annual=0.03)
    wealth_grow = simulate_portfolio_wealth(boot_paths, weights_baseline, starting_eur,
                                              ter_annual, "quarterly", cashflows=cf_grow)
    m_grow = compute_path_metrics(wealth_grow, starting_eur, HORIZON_YEARS)
    accum["salaryGrowth"] = summarize(m_grow, wealth_grow, weights_baseline,
                                       "DCA €50 + 3%/yr salary growth", asset_order, starting_eur,
                                       full=True, total_contributed=np.full(boot_paths.shape[0], cf_grow.sum()))

    # Broker fee scenarios
    print("\n  Broker fee scenarios (€50/mo baseline)...")
    broker_results = {}
    for broker, fee in BROKER_FEES.items():
        cf_b = build_dca_schedule(50, HORIZON_DAYS, broker_fee_per_contribution=fee)
        wealth_b = simulate_portfolio_wealth(boot_paths, weights_baseline, starting_eur,
                                              ter_annual, "quarterly", cashflows=cf_b)
        m_b = compute_path_metrics(wealth_b, starting_eur, HORIZON_YEARS)
        broker_results[broker] = {
            "label": f"{broker} (€{fee:.2f}/contribution)",
            "feeEurPerContribution": fee,
            "totalContributedNet": float(cf_b.sum()),
            "medianTerminal": float(np.median(m_b["terminal"])),
        }
        print(f"    {broker:18s} fee=€{fee:.2f}  median=€{np.median(m_b['terminal']):,.0f}")
    accum["brokerFees"] = broker_results

    # ESG drag
    print("\n  ESG screen (-10bps drag)...")
    esg_drag = np.zeros_like(ter_annual)
    for i, hid in enumerate(asset_order):
        if hid in ("VWCE", "SWDA"):
            esg_drag[i] = 0.0010
    ter_esg = ter_annual + esg_drag  # add 10bps to VWCE/SWDA only
    cf50 = build_dca_schedule(50, HORIZON_DAYS)
    wealth_esg = simulate_portfolio_wealth(boot_paths, weights_baseline, starting_eur,
                                            ter_esg, "quarterly", cashflows=cf50)
    m_esg = compute_path_metrics(wealth_esg, starting_eur, HORIZON_YEARS)
    accum["esgScreen"] = summarize(m_esg, wealth_esg, weights_baseline,
                                    "Baseline + ESG screen (-10bps on VWCE/SWDA)",
                                    asset_order, starting_eur, full=False)

    # Jump-diffusion overlay
    print("\n  Jump-diffusion overlay (3 crashes/yr, -3% avg)...")
    boot_with_jumps = apply_jump_overlay(boot_paths, seed=SEED + 1)
    wealth_jump = simulate_portfolio_wealth(boot_with_jumps, weights_baseline, starting_eur,
                                              ter_annual, "quarterly", cashflows=cf50)
    m_jump = compute_path_metrics(wealth_jump, starting_eur, HORIZON_YEARS)
    accum["jumpDiffusion"] = summarize(m_jump, wealth_jump, weights_baseline,
                                        "Baseline + jump-diffusion overlay",
                                        asset_order, starting_eur, full=True)
    print(f"    median terminal=€{np.median(m_jump['terminal']):,.0f}  median max DD={np.median(m_jump['maxDrawdown'])*100:+.1f}%")

    # Hedged scenario
    print("\n  EUR-hedged scenario (BGF + XDWT + SWDA + VWCE)...")
    eurusd_rets = to_business_day_returns(load_index("EURUSD"))
    fx_paths = sample_fx_paths(eurusd_rets, n_paths=PATHS_BOOTSTRAP, horizon_days=HORIZON_DAYS, seed=SEED + 2)
    hedged_paths = hedge_paths(boot_paths, asset_order, fx_paths)
    wealth_h = simulate_portfolio_wealth(hedged_paths, weights_baseline, starting_eur,
                                          ter_annual + 0.0030, "quarterly", cashflows=cf50)
    m_h = compute_path_metrics(wealth_h, starting_eur, HORIZON_YEARS)
    accum["hedged"] = summarize(m_h, wealth_h, weights_baseline,
                                 "Baseline + EUR-hedged (USD-asset hedge, +30bps cost)",
                                 asset_order, starting_eur, full=True)
    del hedged_paths, fx_paths

    # Drawdown buy overlay
    print("\n  Drawdown-buy tactical overlay (double DCA on -20% DD)...")
    wealth_dd, total_c = simulate_with_drawdown_buy(boot_paths, weights_baseline, starting_eur,
                                                     ter_annual, base_monthly=50,
                                                     drawdown_threshold=0.20, multiplier=2.0)
    m_dd = compute_path_metrics(wealth_dd, starting_eur, HORIZON_YEARS)
    accum["drawdownBuy"] = summarize(m_dd, wealth_dd, weights_baseline,
                                      "Baseline + 2× DCA on -20% drawdown",
                                      asset_order, starting_eur, full=False, total_contributed=total_c)

    del boot_paths

    # Engine B: long-history bootstrap (BEAR-REGIME REALITY CHECK)
    print("\nEngine B: long-history bootstrap (2000-2026 — incl. dotcom + GFC)")
    t = time.time()
    lh_paths, lh_df, lh_meta = long_history_bootstrap_paths(PATHS_LONG_HIST, HORIZON_DAYS, seed=SEED + 3)
    print(f"  Paths: {lh_paths.shape}, window {lh_meta['windowYears']:.1f}y, bl={lh_meta['blockLength']}, {time.time()-t:.1f}s")

    long_history_results = {}
    for dca in [0, 50, 500]:
        cf = build_dca_schedule(dca, HORIZON_DAYS)
        wealth = simulate_portfolio_wealth(lh_paths, weights_baseline, starting_eur,
                                            ter_annual, "quarterly", cashflows=cf)
        m = compute_path_metrics(wealth, starting_eur, HORIZON_YEARS)
        total_c_arr = np.full(lh_paths.shape[0], cf.sum())
        long_history_results[f"eur{dca}"] = summarize(m, wealth, weights_baseline,
                                                       f"Long-history DCA €{dca}/mo",
                                                       asset_order, starting_eur,
                                                       full=(dca in [0, 50]),
                                                       total_contributed=total_c_arr)
        print(f"    DCA €{dca}/mo: median=€{np.median(m['terminal']):,.0f}  P(loss)={(m['terminal']<starting_eur).mean()*100:.2f}%  median max DD={np.median(m['maxDrawdown'])*100:+.1f}%")
    accum["longHistory"] = {
        "scenarios": long_history_results,
        "meta": lh_meta,
    }
    del lh_paths

    # Engine C: regime switching
    print("\nEngine C: regime switching HMM bootstrap")
    t = time.time()
    rs_paths, rs_diag = regime_switch_paths(long_df, PATHS_REGIME, HORIZON_DAYS, seed=SEED + 4)
    print(f"  Paths: {rs_paths.shape}, bear_vol={rs_diag['bearVolDaily']:.4f}, bull_vol={rs_diag['bullVolDaily']:.4f}, π_bear={rs_diag['stationaryDist'][0]:.2f}, {time.time()-t:.1f}s")
    cf_rs = build_dca_schedule(50, HORIZON_DAYS)
    wealth_rs = simulate_portfolio_wealth(rs_paths, weights_baseline, starting_eur,
                                            ter_annual, "quarterly", cashflows=cf_rs)
    m_rs = compute_path_metrics(wealth_rs, starting_eur, HORIZON_YEARS)
    accum["regimeSwitching"] = {
        "result": summarize(m_rs, wealth_rs, weights_baseline,
                            "Regime-switching HMM (€50/mo DCA)",
                            asset_order, starting_eur, full=True),
        "diagnostics": rs_diag,
    }
    print(f"    median=€{np.median(m_rs['terminal']):,.0f}  P(loss)={(m_rs['terminal']<starting_eur).mean()*100:.2f}%  median max DD={np.median(m_rs['maxDrawdown'])*100:+.1f}%")
    del rs_paths

    # Stochastic inflation
    print("\nStochastic inflation overlay...")
    t = time.time()
    infl_paths = bootstrap_inflation_paths(PATHS_INFLATION, HORIZON_DAYS, seed=SEED + 5)
    infl_diag = inflation_diagnostics(infl_paths, HORIZON_YEARS)
    print(f"  Inflation 15y geo-mean: median={infl_diag['median15yAnnInflation']*100:.2f}%  p95={infl_diag['p95']*100:.2f}%")

    # Apply to baseline-DCA wealth (already computed for €50/mo)
    boot_paths2 = stationary_bootstrap_paths(augmented_df, PATHS_INFLATION, HORIZON_DAYS,
                                               block_len, seed=SEED)
    cf50_2 = build_dca_schedule(50, HORIZON_DAYS)
    wealth_nom = simulate_portfolio_wealth(boot_paths2, weights_baseline, starting_eur,
                                             ter_annual, "quarterly", cashflows=cf50_2)
    # Path-by-path real wealth = nominal / inflation_deflator
    wealth_real = wealth_nom / infl_paths
    m_real = compute_path_metrics(wealth_real, starting_eur, HORIZON_YEARS)
    accum["stochasticInflation"] = {
        "result": summarize(m_real, wealth_real, weights_baseline,
                             "Baseline €50/mo DCA + stochastic inflation",
                             asset_order, starting_eur, full=True),
        "diagnostics": infl_diag,
    }
    print(f"  Real terminal: median=€{np.median(m_real['terminal']):,.0f}  P(real loss)={(m_real['terminal']<starting_eur).mean()*100:.2f}%")
    del boot_paths2, wealth_nom, wealth_real, infl_paths

    out_accum_path = ROOT / "data" / "monte-carlo-accumulation.json"
    out_accum_path.write_text(json.dumps(accum, indent=1, default=str))
    size_mb = out_accum_path.stat().st_size / 1e6
    print(f"\n✓ Wrote {out_accum_path.name} ({size_mb:.1f} MB)")

    # ──────────────────────────────────────────────────────
    # RETIREMENT JSON
    # ──────────────────────────────────────────────────────
    print("\n── Building retirement JSON ──")

    # 30-year horizon: 15y accumulation (€50/mo DCA) + 15y withdrawal
    # Use long-history matrix for retirement (realistic regime exposure)
    print(f"30y horizon, {PATHS_RETIREMENT} paths via long-history bootstrap...")
    t = time.time()
    ret_paths, _, ret_meta = long_history_bootstrap_paths(PATHS_RETIREMENT, HORIZON_DAYS_30, seed=SEED + 6)
    print(f"  Paths: {ret_paths.shape}, {time.time()-t:.1f}s")

    cf_accum = build_dca_schedule(50, HORIZON_DAYS_30, salary_growth_annual=0.03)

    print("\n  Running withdrawal strategies (4 side-by-side)...")
    withdraw_strategies = {
        "fourPctRule": "4% rule (annual rebase to year-15 wealth)",
        "fixed1500":   "Fixed €1500/mo (real, inflation-indexed)",
        "fixed3000":   "Fixed €3000/mo (real)",
        "fixed5000":   "Fixed €5000/mo (real stress)",
    }
    withdrawal_results = {}

    # Pre-compute inflation path (deterministic 2% for simplicity in this run)
    days = HORIZON_DAYS_30 + 1
    deflator = np.array([(1 + INFLATION_RATE) ** (d / TRADING_DAYS_PER_YEAR) for d in range(days)])

    for strat_key, strat_label in withdraw_strategies.items():
        # First, accumulation phase only to get year-15 wealth per path
        wealth_pre = simulate_portfolio_wealth(ret_paths[:, :HORIZON_DAYS, :], weights_baseline,
                                                 starting_eur, ter_annual, "quarterly", cashflows=cf_accum[:HORIZON_DAYS + 1])
        year15_wealth = wealth_pre[:, -1].copy()

        # Build full cashflow: accumulation + withdrawal
        # For 4% rule, use median year-15 wealth as the basis (simplification)
        if strat_key == "fourPctRule":
            ref_wealth = float(np.median(year15_wealth))
            wd = build_withdrawal_schedule("fourPctRule", HORIZON_DAYS_30,
                                            withdrawal_start_day=HORIZON_DAYS,
                                            year15_wealth=ref_wealth,
                                            inflation_path=deflator)
        else:
            wd = build_withdrawal_schedule(strat_key, HORIZON_DAYS_30,
                                            withdrawal_start_day=HORIZON_DAYS,
                                            inflation_path=deflator)
        # Combine accumulation + withdrawal
        full_cf = cf_accum.copy()
        full_cf += wd

        wealth, basis = simulate_portfolio_wealth(ret_paths, weights_baseline, starting_eur,
                                                    ter_annual, "quarterly", cashflows=full_cf,
                                                    track_basis=True)
        # Depletion: paths where wealth hits zero
        depletion_day = np.argmax(wealth <= 0, axis=1)
        depletion_day[wealth.min(axis=1) > 0] = -1
        p_depleted_year30 = float(np.mean(depletion_day > 0))

        # Apply Abgeltungsteuer at sale (lump-sum at year 30)
        vorab_paid = estimate_vorab_paid_during_phase(wealth, 30, until_day=HORIZON_DAYS_30)
        terminal_pretax = wealth[:, -1].copy()
        # Tax on positive terminal as if lump-sum sale
        terminal_pretax = np.maximum(terminal_pretax, 0)
        # Cumulative basis at end (account for withdrawals)
        end_basis = basis[:, -1]
        tax = compute_realized_gain_tax(terminal_pretax, terminal_pretax, end_basis, vorab_paid)
        terminal_posttax = terminal_pretax - tax

        m = compute_path_metrics(wealth, starting_eur, 30)
        m["terminalPretax"] = terminal_pretax
        m["terminalPosttax"] = terminal_posttax

        withdrawal_results[strat_key] = {
            "label": strat_label,
            "fanChart": fan_chart(wealth, step_days=42),  # bi-monthly for 30y
            "samplePaths": sample_paths(wealth, n_samples=30, step_days=42),
            "terminalPretax": quantile_summary(terminal_pretax),
            "terminalPosttax": quantile_summary(terminal_posttax),
            "year15Wealth": quantile_summary(year15_wealth),
            "pDepletedYear30": p_depleted_year30,
            "medianYearsToDepletion": float(np.median(depletion_day[depletion_day > 0]) / TRADING_DAYS_PER_YEAR) if (depletion_day > 0).any() else None,
            "totalTaxPaid": float(np.median(tax + vorab_paid)),
            "withdrawalStartDay": HORIZON_DAYS,
        }
        print(f"  {strat_key:14s}: P(depleted)={p_depleted_year30*100:.1f}%  median terminal posttax=€{np.median(terminal_posttax):,.0f}")

    retirement = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "inputs": {
            "weightsHash": weights_hash(baseline_w),
            "horizonYears": 30,
            "withdrawalStartYear": 15,
            "accumulationMonthly": 50,
            "accumulationGrowth": 0.03,
            "inflationRate": INFLATION_RATE,
            "pathsRetirement": PATHS_RETIREMENT,
            "engine": "long-history bootstrap",
        },
        "windowMeta": ret_meta,
        "strategies": withdrawal_results,
    }
    out_ret_path = ROOT / "data" / "monte-carlo-retirement.json"
    out_ret_path.write_text(json.dumps(retirement, indent=1, default=str))
    print(f"\n✓ Wrote {out_ret_path.name} ({out_ret_path.stat().st_size/1e6:.1f} MB)")

    elapsed = time.time() - t_start
    print(f"\nTotal v2 elapsed: {elapsed/60:.1f} min")


if __name__ == "__main__":
    main()
