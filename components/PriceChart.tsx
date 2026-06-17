"use client";
import { useEffect, useMemo, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import type { PriceSeries } from "@/lib/types";

type RangeKey = "1Y" | "3Y" | "5Y";

function fmtDate(t: number) {
  const d = new Date(t);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}`;
}

export default function PriceChart({ symbols, colors }: { symbols: string[]; colors?: Record<string,string> }) {
  const [series, setSeries] = useState<Record<string, PriceSeries>>({});
  const [range, setRange] = useState<RangeKey>("5Y");
  const [loading, setLoading] = useState(true);
  const [rebased, setRebased] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all(symbols.map(async (s) => {
      const r = await fetch(`/api/prices/${encodeURIComponent(s)}`);
      return [s, await r.json() as PriceSeries] as const;
    })).then((entries) => {
      if (cancelled) return;
      const obj: Record<string, PriceSeries> = {};
      for (const [s, p] of entries) obj[s] = p;
      setSeries(obj);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbols.join("|")]);

  const data = useMemo(() => {
    const now = Date.now();
    const years = range === "1Y" ? 1 : range === "3Y" ? 3 : 5;
    const from = now - years * 365 * 86400_000;

    const filtered: Record<string, { t: number; c: number }[]> = {};
    for (const s of symbols) {
      const pts = series[s]?.points ?? [];
      const f = pts.filter((p) => p.t >= from);
      filtered[s] = f;
    }
    const base: Record<string, number> = {};
    for (const s of symbols) base[s] = filtered[s][0]?.c ?? 1;

    const dateSet = new Set<number>();
    for (const s of symbols) for (const p of filtered[s]) dateSet.add(p.t);
    const dates = [...dateSet].sort((a,b)=>a-b);

    const map: Record<string, Record<string, number>> = {};
    for (const s of symbols) {
      map[s] = {};
      for (const p of filtered[s]) map[s][p.t] = p.c;
    }

    const out: any[] = [];
    const lastVal: Record<string, number> = {};
    for (const t of dates) {
      const row: any = { t };
      for (const s of symbols) {
        const v = map[s][t];
        if (v != null) lastVal[s] = v;
        const cur = lastVal[s];
        if (cur != null) row[s] = rebased ? (cur / base[s]) * 100 : cur;
      }
      out.push(row);
    }
    return out;
  }, [series, range, rebased, symbols.join("|")]);

  const palette = ["#6ee7b7", "#a78bfa", "#fbbf24", "#f87171", "#60a5fa", "#34d399"];
  const colorFor = (s: string, i: number) => colors?.[s] ?? palette[i % palette.length];

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex gap-1">
          {(["1Y","3Y","5Y"] as RangeKey[]).map((r) => (
            <button key={r} onClick={()=>setRange(r)} className={`btn ${range===r ? "border-accent text-accent" : ""}`}>{r}</button>
          ))}
        </div>
        <label className="text-xs text-muted flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={rebased} onChange={(e)=>setRebased(e.target.checked)} /> rebase to 100
        </label>
      </div>
      <div className="h-72">
        {loading ? (
          <div className="h-full flex items-center justify-center text-muted text-sm">loading price history…</div>
        ) : (
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#262b34" strokeDasharray="3 3" />
              <XAxis dataKey="t" tickFormatter={fmtDate} stroke="#8a93a3" fontSize={11} />
              <YAxis stroke="#8a93a3" fontSize={11} domain={["auto","auto"]} />
              <Tooltip
                labelFormatter={(t)=>fmtDate(Number(t))}
                formatter={(v: any, n: any) => [typeof v === "number" ? v.toFixed(2) : v, n]}
                contentStyle={{ background:"#13161b", border:"1px solid #262b34", borderRadius:8, fontSize:12 }}
              />
              {symbols.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {symbols.map((s, i) => (
                <Line key={s} type="monotone" dataKey={s} stroke={colorFor(s, i)} dot={false} strokeWidth={2} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {Object.values(series).some((s)=>s?.source==="unavailable") && (
        <div className="mt-2 text-xs text-warn">⚠ Some symbols have no public price history — chart skips them.</div>
      )}
      {Object.values(series).some((s)=>s?.source==="boerse-frankfurt") && (
        <div className="mt-2 text-xs text-muted">Some fund history sourced from boerse-frankfurt fallback.</div>
      )}
    </div>
  );
}
