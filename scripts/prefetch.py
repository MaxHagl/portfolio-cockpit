#!/usr/bin/env python3
"""Prefetch 5y daily price history for every holding and peer.
Writes JSON to .cache/<id>.json keyed by the instrument id (not yahoo symbol),
so the Next.js API route can serve it without hitting Yahoo at request time.
"""
import json
import os
import sys
import time
from pathlib import Path

from curl_cffi import requests as crq
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

holdings = json.loads((ROOT / "data" / "holdings.json").read_text())
peers = json.loads((ROOT / "data" / "peers.json").read_text())

sess = crq.Session(impersonate="chrome120")


def search_yahoo_for_isin(isin: str) -> str | None:
    try:
        r = sess.get(
            f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}&newsCount=0",
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        for q in r.json().get("quotes", []):
            sym = q.get("symbol")
            if sym:
                return sym
    except Exception:
        return None
    return None


def fetch(instrument_id: str, yahoo_sym: str, isin: str) -> tuple[str, list[dict], str | None]:
    """Return (source, points, note)."""
    tried = []
    candidates = [yahoo_sym]
    for sym in candidates:
        if not sym:
            continue
        tried.append(sym)
        try:
            h = yf.Ticker(sym, session=sess).history(period="5y", interval="1d", auto_adjust=True)
            if len(h) >= 30:
                pts = [{"t": int(idx.timestamp() * 1000), "c": float(row["Close"])}
                       for idx, row in h.iterrows() if row["Close"] == row["Close"]]
                return "yahoo", pts, None
        except Exception:
            pass
    # Fallback: ISIN search
    sym = search_yahoo_for_isin(isin)
    if sym and sym not in tried:
        tried.append(sym)
        try:
            h = yf.Ticker(sym, session=sess).history(period="5y", interval="1d", auto_adjust=True)
            if len(h) >= 30:
                pts = [{"t": int(idx.timestamp() * 1000), "c": float(row["Close"])}
                       for idx, row in h.iterrows() if row["Close"] == row["Close"]]
                return "yahoo", pts, f"resolved via ISIN search → {sym}"
        except Exception:
            pass
    return "unavailable", [], f"no price history for ISIN {isin} (tried: {', '.join(tried)})"


def main():
    targets: list[tuple[str, str, str]] = []
    for h in holdings["holdings"]:
        targets.append((h["id"], h["yahoo"], h["isin"]))
    for hid, plist in peers.items():
        for p in plist:
            targets.append((p["id"], p["yahoo"], p["isin"]))

    seen = set()
    results = {}
    for instrument_id, yahoo, isin in targets:
        if instrument_id in seen:
            continue
        seen.add(instrument_id)
        source, pts, note = fetch(instrument_id, yahoo, isin)
        results[instrument_id] = {"symbol": instrument_id, "source": source, "points": pts}
        if note:
            results[instrument_id]["note"] = note
        out = CACHE / f"{instrument_id}.json"
        out.write_text(json.dumps(results[instrument_id]))
        msg = f"{instrument_id:14s} src={source:11s} pts={len(pts):4d}"
        if note:
            msg += f"  {note}"
        print(msg)
        time.sleep(0.6)

    (CACHE / "_manifest.json").write_text(json.dumps({
        "generated": int(time.time()),
        "count": len(results),
    }))
    print(f"\nWrote {len(results)} series → {CACHE}")


if __name__ == "__main__":
    main()
