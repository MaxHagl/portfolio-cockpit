import type { PricePoint } from "./types";

export interface AlignedReturns {
  dates: number[];
  symbols: string[];
  returns: number[][];
}

function toDateKey(t: number): string {
  const d = new Date(t);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}-${String(d.getUTCDate()).padStart(2,"0")}`;
}

export function alignSeries(seriesBySymbol: Record<string, PricePoint[]>): AlignedReturns {
  const symbols = Object.keys(seriesBySymbol).filter((s) => seriesBySymbol[s].length > 0);
  if (symbols.length === 0) return { dates: [], symbols: [], returns: [] };

  const maps: Record<string, Map<string, number>> = {};
  for (const s of symbols) {
    maps[s] = new Map();
    for (const p of seriesBySymbol[s]) maps[s].set(toDateKey(p.t), p.c);
  }

  const allKeysSet = new Set<string>();
  for (const s of symbols) for (const k of maps[s].keys()) allKeysSet.add(k);
  const allKeys = [...allKeysSet].sort();

  const ffilled: Record<string, number[]> = {};
  for (const s of symbols) {
    const arr: number[] = [];
    let last = NaN;
    for (const k of allKeys) {
      const v = maps[s].get(k);
      if (v != null) last = v;
      arr.push(last);
    }
    ffilled[s] = arr;
  }

  let firstValid = 0;
  while (firstValid < allKeys.length && symbols.some((s) => !Number.isFinite(ffilled[s][firstValid]))) firstValid++;
  const dates = allKeys.slice(firstValid).map((k) => Date.parse(k + "T00:00:00Z"));

  const returns: number[][] = symbols.map(() => []);
  for (let i = firstValid + 1; i < allKeys.length; i++) {
    for (let s = 0; s < symbols.length; s++) {
      const prev = ffilled[symbols[s]][i-1];
      const cur = ffilled[symbols[s]][i];
      returns[s].push(prev > 0 ? cur/prev - 1 : 0);
    }
  }
  return { dates: dates.slice(1), symbols, returns };
}

export interface BlendedMetrics {
  cumReturn: number;
  annReturn: number;
  annVol: number;
  maxDrawdown: number;
  years: number;
  equity: { t: number; v: number }[];
}

export function blend(aligned: AlignedReturns, weightsBySymbol: Record<string, number>): BlendedMetrics {
  if (aligned.dates.length === 0) return { cumReturn: 0, annReturn: 0, annVol: 0, maxDrawdown: 0, years: 0, equity: [] };
  const w = aligned.symbols.map((s) => weightsBySymbol[s] ?? 0);
  const totalW = w.reduce((a,b)=>a+b,0);
  const wn = totalW > 0 ? w.map((x)=>x/totalW) : w;

  const n = aligned.dates.length;
  const dailyR: number[] = new Array(n);
  for (let i = 0; i < n; i++) {
    let r = 0;
    for (let s = 0; s < aligned.symbols.length; s++) r += wn[s] * aligned.returns[s][i];
    dailyR[i] = r;
  }

  const equity: { t: number; v: number }[] = [];
  let v = 1;
  let peak = 1;
  let mdd = 0;
  for (let i = 0; i < n; i++) {
    v *= (1 + dailyR[i]);
    equity.push({ t: aligned.dates[i], v });
    if (v > peak) peak = v;
    const dd = v/peak - 1;
    if (dd < mdd) mdd = dd;
  }

  const mean = dailyR.reduce((a,b)=>a+b,0) / n;
  const varD = dailyR.reduce((a,b)=>a+(b-mean)*(b-mean),0) / Math.max(1, n-1);
  const annVol = Math.sqrt(varD) * Math.sqrt(252);
  const years = n / 252;
  const cumReturn = v - 1;
  const annReturn = years > 0 ? Math.pow(v, 1/years) - 1 : 0;
  return { cumReturn, annReturn, annVol, maxDrawdown: mdd, years, equity };
}
