import fs from "node:fs/promises";
import path from "node:path";
import type { PriceSeries, PricePoint } from "./types";

const CACHE_DIR = path.join(process.cwd(), ".cache");

const liveMemo = new Map<string, { at: number; series: PriceSeries }>();
const LIVE_TTL_MS = 15 * 60 * 1000;

async function fetchYahooLive(symbol: string): Promise<PriceSeries> {
  const memo = liveMemo.get(symbol);
  if (memo && Date.now() - memo.at < LIVE_TTL_MS) return memo.series;

  const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5y&interval=1d`;
  try {
    const r = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json" },
      cache: "no-store",
    });
    if (!r.ok) throw new Error(`yahoo ${r.status}`);
    const j = await r.json() as any;
    const res = j?.chart?.result?.[0];
    const ts: number[] | undefined = res?.timestamp;
    const closes: (number | null)[] | undefined = res?.indicators?.adjclose?.[0]?.adjclose
      ?? res?.indicators?.quote?.[0]?.close;
    if (!ts || !closes || ts.length === 0) throw new Error("no points");
    const points: PricePoint[] = [];
    for (let i = 0; i < ts.length; i++) {
      const c = closes[i];
      if (c == null || Number.isNaN(c)) continue;
      points.push({ t: ts[i] * 1000, c: Number(c) });
    }
    if (points.length < 30) throw new Error("too few points");
    const series: PriceSeries = { symbol, source: "yahoo", points };
    liveMemo.set(symbol, { at: Date.now(), series });
    return series;
  } catch (e: any) {
    return {
      symbol,
      source: "unavailable",
      points: [],
      note: `Live Yahoo fetch failed: ${e?.message ?? e}. Try a different symbol or run 'python scripts/prefetch.py'.`,
    };
  }
}

export async function getPriceSeries(idOrSymbol: string, yahooFallback?: string): Promise<PriceSeries> {
  const id = idOrSymbol.replace(/[^a-zA-Z0-9_.-]/g, "");
  try {
    const f = path.join(CACHE_DIR, `${id}.json`);
    const data = JSON.parse(await fs.readFile(f, "utf8")) as PriceSeries;
    if (data.points?.length > 0) return { ...data, source: data.source ?? "cache" };
  } catch {}
  const liveSym = (yahooFallback ?? id).replace(/[^a-zA-Z0-9_.-]/g, "");
  return fetchYahooLive(liveSym);
}
