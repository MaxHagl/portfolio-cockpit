#!/usr/bin/env python3
"""Prefetch macro series from FRED for Monte Carlo overlays.

Fetches EUR Area HICP (Harmonized Index of Consumer Prices) for stochastic
inflation modeling. Writes to .cache/_macro_<id>.json in the standard
{symbol, source, points: [{t, c}]} format.
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as crq

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

sess = crq.Session(impersonate="chrome120")

# FRED series:
# CP0000EZ19M086NEST = Euro Area HICP (19 countries, monthly, NSA, 2015=100), back to 1996-01
SERIES = [
    ("HICP_EUR", "CP0000EZ19M086NEST", "Euro Area HICP — stochastic inflation source"),
]


def fetch_fred_csv(series_id: str) -> list[dict]:
    """Pull from FRED's public CSV endpoint (no API key needed)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = sess.get(url, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"FRED {series_id}: HTTP {r.status_code}")
    rows = r.text.strip().split("\n")
    if len(rows) < 10:
        raise RuntimeError(f"FRED {series_id}: response too short ({len(rows)} rows)")
    # Skip header
    pts = []
    for row in rows[1:]:
        parts = row.split(",")
        if len(parts) < 2:
            continue
        date_str, val_str = parts[0], parts[1]
        if val_str in (".", "", "NA"):
            continue
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            ts_ms = int(dt.timestamp() * 1000)
            val = float(val_str)
            pts.append({"t": ts_ms, "c": val})
        except (ValueError, OverflowError):
            continue
    return pts


def main():
    for cache_id, fred_id, desc in SERIES:
        try:
            pts = fetch_fred_csv(fred_id)
            source = "fred"
            note = None
        except Exception as e:
            pts = []
            source = "unavailable"
            note = f"fetch error: {e}"

        result = {"symbol": cache_id, "source": source, "points": pts}
        if note:
            result["note"] = note

        out = CACHE / f"_macro_{cache_id}.json"
        out.write_text(json.dumps(result))

        if pts:
            from datetime import datetime
            d0 = datetime.fromtimestamp(pts[0]["t"] / 1000).strftime("%Y-%m-%d")
            d1 = datetime.fromtimestamp(pts[-1]["t"] / 1000).strftime("%Y-%m-%d")
            span_yrs = (pts[-1]["t"] - pts[0]["t"]) / (1000 * 365.25 * 86400)
            print(f"{cache_id:10s} ({fred_id:30s}) {source:11s} pts={len(pts):4d}  {d0} → {d1}  ({span_yrs:5.1f}y)  {desc}")
        else:
            print(f"{cache_id:10s} ({fred_id:30s}) {source:11s} FAILED  {note}")

        time.sleep(0.5)


if __name__ == "__main__":
    main()
