#!/usr/bin/env python3
"""Prefetch maximum-history price series for benchmark indices used by Monte Carlo:
- proxy regressions for short-history active funds (BGF, A3DRHJ)
- stress replays of 2000/2008/2020
- EUR/USD overlay

Writes JSON to .cache/_index_<id>.json (underscore prefix isolates from holdings prefetch).
Format identical to prefetch.py: {symbol, source, points: [{t, c}]}.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as crq
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

sess = crq.Session(impersonate="chrome120")

# (cache_id, yahoo_symbol, description)
INDICES = [
    # Long-history equity benchmarks (stress replay + tech proxy)
    ("SPX",     "^GSPC",     "S&P 500 (back to 1927)"),
    ("NDX",     "^IXIC",     "Nasdaq Composite (back to 1971)"),
    ("IXN",     "IXN",       "iShares Global Tech ETF (back to ~2001) — BGF proxy"),
    ("EEM",     "EEM",       "iShares MSCI EM ETF (back to 2003) — A3DRHJ proxy + stress"),
    ("URTH",    "URTH",      "iShares MSCI World ETF (back to 2012) — VWCE/SWDA proxy"),
    ("STOXX600","^STOXX",    "STOXX Europe 600 (back to 1986) — EUR equity benchmark"),

    # EUR aggregate bond proxy for 60/40 scenario
    ("EUNA",    "EUNA.DE",   "iShares Core EUR Govt Bond ETF — 60/40 bond sleeve"),
    ("AGGH",    "AGGH.DE",   "iShares Global Agg Bond EUR Hedged — alt bond proxy"),

    # Currency
    ("EURUSD",  "EURUSD=X",  "EUR/USD spot (back to ~2003)"),

    # Long-history MSCI World proxies (free-float indices)
    ("XDWD",    "XDWD.DE",   "Xtrackers MSCI World — long history"),
]


def fetch_max(yahoo_sym: str) -> tuple[str, list[dict], str | None]:
    """Fetch max history daily prices."""
    try:
        t = yf.Ticker(yahoo_sym, session=sess)
        h = t.history(period="max", interval="1d", auto_adjust=True)
        if len(h) >= 100:
            pts = [
                {"t": int(idx.timestamp() * 1000), "c": float(row["Close"])}
                for idx, row in h.iterrows()
                if row["Close"] == row["Close"]  # NaN filter
            ]
            return "yahoo", pts, None
    except Exception as e:
        return "unavailable", [], f"fetch error: {e}"
    return "unavailable", [], f"insufficient history (<100 pts)"


def main():
    results = {}
    for cache_id, yahoo, desc in INDICES:
        source, pts, note = fetch_max(yahoo)
        results[cache_id] = {"symbol": cache_id, "source": source, "points": pts}
        if note:
            results[cache_id]["note"] = note

        out = CACHE / f"_index_{cache_id}.json"
        out.write_text(json.dumps(results[cache_id]))

        if pts:
            first = pts[0]["t"] / 1000
            last = pts[-1]["t"] / 1000
            span_yrs = (last - first) / (365.25 * 86400)
            from datetime import datetime
            d0 = datetime.utcfromtimestamp(first).strftime("%Y-%m-%d")
            d1 = datetime.utcfromtimestamp(last).strftime("%Y-%m-%d")
            print(f"{cache_id:10s} ({yahoo:14s}) {source:11s} pts={len(pts):5d}  {d0} → {d1}  ({span_yrs:5.1f}y)  {desc}")
        else:
            print(f"{cache_id:10s} ({yahoo:14s}) {source:11s} pts=    0  ── FAILED ──  {note}")

        time.sleep(0.8)

    (CACHE / "_indices_manifest.json").write_text(json.dumps({
        "generated": int(time.time()),
        "indices": [
            {"id": cid, "yahoo": yah, "description": desc,
             "points": len(results[cid]["points"]),
             "source": results[cid]["source"]}
            for cid, yah, desc in INDICES
        ],
    }, indent=2))
    ok = sum(1 for r in results.values() if r["source"] == "yahoo")
    print(f"\nWrote {ok}/{len(INDICES)} index series → {CACHE}/_index_*.json")


if __name__ == "__main__":
    main()
