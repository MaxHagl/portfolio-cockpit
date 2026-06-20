"""Hierarchical Risk Parity allocation suggestion.

Computes HRP weights (Lopez de Prado 2016) on the current holdings using
cached daily returns. Writes data/allocations.json which the cockpit reads
to show a suggested-weight column alongside the current weights.

Run: .venv/bin/python scripts/allocations_hrp.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pypfopt.hierarchical_portfolio import HRPOpt

from mc_data import (
    align_returns,
    load_holding,
    load_holdings_meta,
    to_business_day_returns,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "allocations.json"

MIN_OVERLAP_DAYS = 250
LINKAGE = "single"


def build_returns_matrix(holding_ids: list[str]) -> pd.DataFrame:
    series = {}
    for hid in holding_ids:
        prices = load_holding(hid)
        if len(prices) == 0:
            raise SystemExit(f"No cached prices for {hid}. Run prefetch first.")
        series[hid] = to_business_day_returns(prices)
    df = align_returns(series, how="inner").dropna()
    if len(df) < MIN_OVERLAP_DAYS:
        raise SystemExit(
            f"Only {len(df)} overlapping days across {holding_ids}; need >= {MIN_OVERLAP_DAYS}"
        )
    return df


def run_hrp(returns: pd.DataFrame) -> dict[str, float]:
    hrp = HRPOpt(returns=returns)
    weights = hrp.optimize(linkage_method=LINKAGE)
    return {k: float(v) for k, v in weights.items()}


def correlation_matrix(returns: pd.DataFrame) -> list[dict]:
    corr = returns.corr()
    out = []
    for i, a in enumerate(corr.columns):
        for j, b in enumerate(corr.columns):
            if j <= i:
                continue
            out.append({"a": a, "b": b, "rho": float(corr.iloc[i, j])})
    return out


def main() -> None:
    meta = load_holdings_meta()
    holding_ids = [h["id"] for h in meta["holdings"]]
    current = {h["id"]: float(h["weight"]) for h in meta["holdings"]}

    returns = build_returns_matrix(holding_ids)
    hrp_weights = run_hrp(returns)

    deltas = {hid: hrp_weights.get(hid, 0.0) - current.get(hid, 0.0) for hid in holding_ids}

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "HRP",
        "linkage": LINKAGE,
        "paper": "Lopez de Prado (2016), Building Diversified Portfolios That Outperform OOS",
        "returnsWindow": {
            "start": str(returns.index.min().date()),
            "end": str(returns.index.max().date()),
            "days": int(len(returns)),
        },
        "current": current,
        "hrp": hrp_weights,
        "delta": deltas,
        "correlations": correlation_matrix(returns),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT}")
    print("\nCurrent vs HRP suggestion:")
    for hid in holding_ids:
        cur = current[hid]
        sug = hrp_weights.get(hid, 0.0)
        d = sug - cur
        print(f"  {hid:8s}  current {cur*100:5.1f}%  →  HRP {sug*100:5.1f}%  (Δ {d*100:+5.1f}pp)")


if __name__ == "__main__":
    main()
