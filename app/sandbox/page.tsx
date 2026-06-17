"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, Legend } from "recharts";
import holdings from "@/data/holdings.json";
import peers from "@/data/peers.json";
import candidates from "@/data/candidates.json";
import { alignSeries, blend } from "@/lib/portfolio";
import type { PriceSeries } from "@/lib/types";
import MetricDelta from "@/components/MetricDelta";

type Sleeve = "core"|"tech"|"em";
type Inst = { id: string; name: string; ter: number; sleeve: Sleeve; type: string; isin: string; wkn: string; yahoo: string; sourceHoldingId?: string; custom?: boolean };

function instOfHolding(h: any): Inst {
  return { id: h.id, name: h.shortName, ter: h.ter, sleeve: h.sleeve, type: h.type, isin: h.isin, wkn: h.wkn, yahoo: h.yahoo };
}
function instOfPeer(p: any, forHoldingId: string, sleeve: Inst["sleeve"]): Inst {
  return { id: p.id, name: p.id, ter: p.ter, sleeve, type: p.type, isin: p.isin, wkn: p.wkn, yahoo: p.yahoo, sourceHoldingId: forHoldingId };
}

function fmtPct(n: number) { return `${(n*100).toFixed(2)}%`; }
function fmtDate(t:number){const d=new Date(t);return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,"0")}`}

export default function Sandbox() {
  const search = useSearchParams();
  const swapParam = search.get("swap"); // "<holdingId>:<peerId>"

  const baselineHoldings = holdings.holdings.map(instOfHolding);

  const [insts, setInsts] = useState<Inst[]>(baselineHoldings);
  const [weights, setWeights] = useState<Record<string, number>>(() => {
    const w: Record<string, number> = {};
    for (const h of holdings.holdings) w[h.id] = h.weight;
    return w;
  });

  // Honour ?swap=
  useEffect(() => {
    if (!swapParam) return;
    const [hid, pid] = swapParam.split(":");
    if (!hid || !pid) return;
    const peerList = (peers as any)[hid] ?? [];
    const peer = peerList.find((p: any) => p.id === pid);
    if (!peer) return;
    const h = holdings.holdings.find((x) => x.id === hid);
    if (!h) return;
    setInsts((prev) => {
      if (prev.find((i) => i.id === pid)) return prev;
      return [...prev, instOfPeer(peer, hid, h.sleeve as any)];
    });
    setWeights((prev) => {
      const half = (prev[hid] ?? h.weight) / 2;
      return { ...prev, [hid]: half, [pid]: half };
    });
  }, [swapParam]);

  // Fetch prices for all instruments
  const [series, setSeries] = useState<Record<string, PriceSeries>>({});
  useEffect(() => {
    let cancelled = false;
    const need = insts.filter((i) => !series[i.id]);
    if (need.length === 0) return;
    Promise.all(need.map(async (i) => {
      const qs = i.yahoo && i.yahoo !== i.id ? `?yahoo=${encodeURIComponent(i.yahoo)}` : "";
      const r = await fetch(`/api/prices/${encodeURIComponent(i.id)}${qs}`);
      return [i.id, await r.json() as PriceSeries] as const;
    })).then((entries) => {
      if (cancelled) return;
      setSeries((prev) => {
        const next = { ...prev };
        for (const [id, s] of entries) next[id] = s;
        return next;
      });
    });
    return () => { cancelled = true; };
  }, [insts]);

  // Build aligned returns + run baseline + current
  const aligned = useMemo(() => {
    const seriesBySymbol: Record<string, any[]> = {};
    for (const i of insts) {
      const s = series[i.id];
      if (s?.points?.length) seriesBySymbol[i.id] = s.points;
    }
    return alignSeries(seriesBySymbol);
  }, [insts, series]);

  const baselineWeights: Record<string, number> = useMemo(() => {
    const w: Record<string, number> = {};
    for (const h of holdings.holdings) w[h.id] = h.weight;
    return w;
  }, []);

  const totalCurrent = Object.values(weights).reduce((a,b)=>a+(b||0),0);
  const normCurrent: Record<string, number> = totalCurrent > 0
    ? Object.fromEntries(Object.entries(weights).map(([k,v])=>[k,(v||0)/totalCurrent]))
    : {};

  const baselineMetrics = useMemo(()=>blend(aligned, baselineWeights), [aligned, baselineWeights]);
  const currentMetrics = useMemo(()=>blend(aligned, normCurrent), [aligned, normCurrent]);

  const blendedTerCurrent = insts.reduce((a, i) => a + (normCurrent[i.id] ?? 0) * i.ter, 0);
  const blendedTerBaseline = holdings.holdings.reduce((a, h) => a + h.weight * h.ter, 0);

  const sleeveMix = (wmap: Record<string, number>) => {
    const t = { core: 0, tech: 0, em: 0 } as Record<string, number>;
    for (const i of insts) t[i.sleeve] = (t[i.sleeve] ?? 0) + (wmap[i.id] ?? 0);
    return t;
  };
  const sleeveCurrent = sleeveMix(normCurrent);
  const sleeveBaseline = sleeveMix(baselineWeights);

  const equityCmp = useMemo(() => {
    const a = baselineMetrics.equity;
    const b = currentMetrics.equity;
    const len = Math.min(a.length, b.length);
    const out: any[] = [];
    for (let i = 0; i < len; i++) out.push({ t: a[i].t, baseline: a[i].v*100, current: b[i].v*100 });
    return out;
  }, [baselineMetrics, currentMetrics]);

  const reset = () => {
    setInsts(baselineHoldings);
    const w: Record<string, number> = {};
    for (const h of holdings.holdings) w[h.id] = h.weight;
    setWeights(w);
  };

  const removeInst = (id: string) => {
    setInsts((prev) => prev.filter((i) => i.id !== id));
    setWeights((prev) => { const n = { ...prev }; delete n[id]; return n; });
  };

  const addCandidate = (c: { id: string; yahoo: string; name: string; sleeve: Sleeve; ter: number; isin?: string; wkn?: string }, initialWeightPct = 5) => {
    const id = c.id;
    if (insts.find((i) => i.id === id)) return;
    const inst: Inst = {
      id,
      name: c.name,
      ter: c.ter,
      sleeve: c.sleeve,
      type: "ETF",
      isin: c.isin ?? "",
      wkn: c.wkn ?? "",
      yahoo: c.yahoo,
      custom: true,
    };
    setInsts((prev) => [...prev, inst]);
    setWeights((prev) => ({ ...prev, [id]: initialWeightPct / 100 }));
  };

  const justETFUrl = (x: { isin?: string; wkn?: string; name?: string; yahoo?: string; id?: string }): string => {
    if (x.isin) return `https://www.justetf.com/en/etf-profile.html?isin=${encodeURIComponent(x.isin)}`;
    if (x.wkn)  return `https://www.justetf.com/en/etf-profile.html?wkn=${encodeURIComponent(x.wkn)}`;
    return `https://www.justetf.com/en/search.html?query=${encodeURIComponent(x.name || x.yahoo || x.id || "")}`;
  };

  const exportConfig = () => {
    const cfg = {
      version: 1,
      savedAt: new Date().toISOString(),
      instruments: insts.map(({ id, name, ter, sleeve, type, isin, wkn, yahoo, sourceHoldingId, custom }) => ({
        id, name, ter, sleeve, type, isin, wkn, yahoo, sourceHoldingId, custom: !!custom,
      })),
      weights,
    };
    const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const stamp = new Date().toISOString().slice(0, 10);
    a.download = `sandbox-${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const importConfig = async (file: File) => {
    try {
      const text = await file.text();
      const cfg = JSON.parse(text);
      if (!Array.isArray(cfg.instruments) || typeof cfg.weights !== "object") throw new Error("Bad config");
      const loaded: Inst[] = cfg.instruments.map((i: any) => ({
        id: i.id, name: i.name ?? i.id, ter: Number(i.ter) || 0, sleeve: (i.sleeve as Sleeve) ?? "core",
        type: i.type ?? "ETF", isin: i.isin ?? "", wkn: i.wkn ?? "", yahoo: i.yahoo ?? i.id,
        sourceHoldingId: i.sourceHoldingId, custom: !!i.custom,
      }));
      setInsts(loaded);
      setWeights(cfg.weights);
    } catch (e: any) {
      alert(`Could not load config: ${e?.message ?? e}`);
    }
  };

  const [sleeveFilter, setSleeveFilter] = useState<"all" | Sleeve>("all");
  const [addForm, setAddForm] = useState({ symbol: "", name: "", sleeve: "core" as Sleeve, ter: "0.30", weight: "5" });

  type Resolved = { yahoo: string; name: string; isin?: string; wkn?: string; currency?: string; exchange?: string; type?: string; source: string };
  const [lookup, setLookup] = useState({ query: "", sleeve: "core" as Sleeve, ter: "0.30", weight: "5" });
  const [lookupStatus, setLookupStatus] = useState<{ state: "idle" | "loading" | "ok" | "err"; resolved?: Resolved; message?: string }>({ state: "idle" });

  const doLookup = async () => {
    const q = lookup.query.trim();
    if (!q) return;
    setLookupStatus({ state: "loading" });
    try {
      const r = await fetch(`/api/resolve?q=${encodeURIComponent(q)}`);
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setLookupStatus({ state: "err", message: j?.error ?? `Lookup failed (${r.status})` });
        return;
      }
      const resolved = await r.json() as Resolved;
      setLookupStatus({ state: "ok", resolved });
    } catch (e: any) {
      setLookupStatus({ state: "err", message: e?.message ?? "Network error" });
    }
  };

  const commitLookup = () => {
    if (lookupStatus.state !== "ok" || !lookupStatus.resolved) return;
    const r = lookupStatus.resolved;
    if (insts.find((i) => i.id === r.yahoo)) {
      setLookupStatus({ state: "err", message: "Already in mix" });
      return;
    }
    const ter = Math.max(0, parseFloat(lookup.ter) / 100) || 0;
    const w = Math.max(0, parseFloat(lookup.weight) / 100) || 0;
    const inst: Inst = {
      id: r.yahoo,
      name: r.name,
      ter,
      sleeve: lookup.sleeve,
      type: r.type ?? "ETF",
      isin: r.isin ?? "",
      wkn: r.wkn ?? "",
      yahoo: r.yahoo,
      custom: true,
    };
    setInsts((prev) => [...prev, inst]);
    setWeights((prev) => ({ ...prev, [r.yahoo]: w }));
    setLookup({ query: "", sleeve: lookup.sleeve, ter: "0.30", weight: "5" });
    setLookupStatus({ state: "idle" });
  };
  const addInst = () => {
    const sym = addForm.symbol.trim();
    if (!sym) return;
    const id = sym.toUpperCase().replace(/[^A-Z0-9_.-]/g, "");
    if (insts.find((i) => i.id === id)) return;
    const ter = Math.max(0, parseFloat(addForm.ter) / 100) || 0;
    const w = Math.max(0, parseFloat(addForm.weight) / 100) || 0;
    const inst: Inst = {
      id,
      name: addForm.name.trim() || sym,
      ter,
      sleeve: addForm.sleeve,
      type: "ETF",
      isin: "",
      wkn: "",
      yahoo: sym,
      custom: true,
    };
    setInsts((prev) => [...prev, inst]);
    setWeights((prev) => ({ ...prev, [id]: w }));
    setAddForm({ symbol: "", name: "", sleeve: addForm.sleeve, ter: "0.30", weight: "5" });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Sandbox</h1>
          <p className="text-muted text-sm mt-1">Adjust weights; swap in peers from any holding page. Backtest compares your mix vs the baseline 68/20/12.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button className="btn" onClick={exportConfig}>↓ Save config</button>
          <label className="btn cursor-pointer">
            ↑ Load config
            <input type="file" accept="application/json,.json" className="hidden"
              onChange={(e)=>{ const f = e.target.files?.[0]; if (f) importConfig(f); e.currentTarget.value=""; }} />
          </label>
          <button className="btn" onClick={reset}>Reset to baseline</button>
          <Link href="/" className="btn">Back to dashboard</Link>
        </div>
      </div>

      <div className="card">
        <div className="h-section">Mix</div>
        <div className="space-y-3">
          {insts.map((i) => {
            const w = weights[i.id] ?? 0;
            const isBaseline = !!holdings.holdings.find((h)=>h.id===i.id);
            const s = series[i.id];
            const noHistory = s && s.source === "unavailable";
            return (
              <div key={i.id} className="grid grid-cols-12 gap-3 items-center">
                <div className="col-span-3">
                  <div className="font-medium flex items-center gap-2">
                    {i.id}
                    {i.custom && <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-300">custom</span>}
                    {!isBaseline && i.sourceHoldingId && <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">peer</span>}
                    {noHistory && <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-900/40 text-rose-300" title={s?.note ?? "No price history"}>no data</span>}
                  </div>
                  <div className="text-xs text-muted line-clamp-1">{i.name}{i.sourceHoldingId ? ` (peer of ${i.sourceHoldingId})` : ""} · TER {(i.ter*100).toFixed(2)}%</div>
                </div>
                <div className="col-span-6 flex items-center gap-3">
                  <input type="range" min={0} max={1} step={0.005} value={w}
                    onChange={(e)=>setWeights((p)=>({ ...p, [i.id]: parseFloat(e.target.value) }))}
                    className="w-full" />
                </div>
                <div className="col-span-1 text-right tabular-nums text-sm">{(w*100).toFixed(1)}%</div>
                <div className="col-span-2 flex justify-end gap-1">
                  <a
                    href={justETFUrl(i)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn"
                    title={i.isin ? `justETF · ISIN ${i.isin}` : i.wkn ? `justETF · WKN ${i.wkn}` : "justETF search"}
                  >ⓘ</a>
                  <button className="btn" title={isBaseline ? "Remove from current mix (baseline unchanged)" : "Remove"} onClick={()=>removeInst(i.id)}>✕</button>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 text-xs text-muted">
          Weights are auto-normalized to 100% for the backtest. Total entered: <span className="tabular-nums text-ink">{(totalCurrent*100).toFixed(1)}%</span>
        </div>

        <div className="mt-5 pt-4 border-t border-zinc-800">
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <div className="text-xs uppercase tracking-wide text-muted">Add from catalog</div>
            <div className="flex items-center gap-2">
              <label className="text-[11px] text-muted">Sleeve</label>
              <select
                className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={sleeveFilter}
                onChange={(e)=>setSleeveFilter(e.target.value as any)}
              >
                <option value="all">All sleeves</option>
                <option value="core">Core</option>
                <option value="tech">Tech</option>
                <option value="em">EM</option>
              </select>
            </div>
          </div>

          {(candidates as any).groups
            ?.map((g: any) => ({ ...g, items: g.items.filter((c: any) => sleeveFilter === "all" || c.sleeve === sleeveFilter) }))
            .filter((g: any) => g.items.length > 0)
            .map((g: any) => (
              <div key={g.label} className="mb-4 last:mb-0">
                <div className="text-[11px] uppercase tracking-wide text-muted/70 mb-2">{g.label}</div>
                <div className="flex flex-wrap gap-2">
                  {g.items.map((c: any) => {
                    const already = !!insts.find((i) => i.id === c.id);
                    return (
                      <div
                        key={c.id}
                        className={`relative text-left px-3 py-2 rounded border text-xs leading-tight transition
                          ${already
                            ? "bg-zinc-900/40 border-zinc-800 text-zinc-500"
                            : "bg-zinc-900 border-zinc-700 hover:border-emerald-600 hover:bg-emerald-950/30 text-zinc-100"}`}
                      >
                        <button
                          disabled={already}
                          onClick={() => addCandidate(c)}
                          title={c.note ?? ""}
                          className={`text-left ${already ? "cursor-not-allowed" : "cursor-pointer"}`}
                        >
                          <div className="flex items-center gap-2 pr-6">
                            <span className="text-emerald-400 font-bold">{already ? "✓" : "+"}</span>
                            <span className="font-medium">{c.id}</span>
                            <span className="text-[10px] text-muted">TER {(c.ter*100).toFixed(2)}%</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded
                              ${c.sleeve === "core" ? "bg-blue-900/40 text-blue-300"
                                : c.sleeve === "tech" ? "bg-violet-900/40 text-violet-300"
                                : "bg-orange-900/40 text-orange-300"}`}>{c.sleeve}</span>
                          </div>
                          <div className="text-muted mt-0.5 max-w-[260px] line-clamp-2">{c.name}</div>
                        </button>
                        <a
                          href={justETFUrl(c)}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e)=>e.stopPropagation()}
                          title={`justETF · ${c.isin ?? c.wkn ?? c.name}`}
                          className="absolute top-1.5 right-1.5 text-[11px] text-zinc-400 hover:text-emerald-300 px-1.5 py-0.5 rounded hover:bg-zinc-800"
                        >ⓘ</a>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
        </div>

        <div className="mt-5 pt-4 border-t border-zinc-800">
          <div className="text-xs uppercase tracking-wide text-muted mb-2">Lookup by WKN / ISIN / ticker / name</div>
          <div className="grid grid-cols-12 gap-2 items-end">
            <div className="col-span-4">
              <label className="text-[11px] text-muted">Query</label>
              <input
                className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                placeholder="e.g. A2PKXG, IE00BK5BQT80, AAPL, SAP"
                value={lookup.query}
                onChange={(e)=>setLookup((p)=>({...p, query: e.target.value}))}
                onKeyDown={(e)=>{ if (e.key === "Enter") doLookup(); }}
              />
            </div>
            <div className="col-span-2">
              <label className="text-[11px] text-muted">Sleeve</label>
              <select
                className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={lookup.sleeve}
                onChange={(e)=>setLookup((p)=>({...p, sleeve: e.target.value as Sleeve}))}
              >
                <option value="core">core</option>
                <option value="tech">tech</option>
                <option value="em">em</option>
              </select>
            </div>
            <div className="col-span-1">
              <label className="text-[11px] text-muted">TER %</label>
              <input type="number" step="0.01" min="0" className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={lookup.ter} onChange={(e)=>setLookup((p)=>({...p, ter: e.target.value}))} />
            </div>
            <div className="col-span-1">
              <label className="text-[11px] text-muted">Wt %</label>
              <input type="number" step="0.5" min="0" max="100" className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={lookup.weight} onChange={(e)=>setLookup((p)=>({...p, weight: e.target.value}))} />
            </div>
            <div className="col-span-2">
              <button className="btn w-full" onClick={doLookup} disabled={!lookup.query.trim() || lookupStatus.state === "loading"}>
                {lookupStatus.state === "loading" ? "Looking up…" : "🔍 Resolve"}
              </button>
            </div>
            <div className="col-span-2">
              <button className="btn w-full" onClick={commitLookup} disabled={lookupStatus.state !== "ok"}>
                + Add to mix
              </button>
            </div>
          </div>
          {lookupStatus.state === "ok" && lookupStatus.resolved && (
            <div className="mt-2 p-2 rounded bg-emerald-950/30 border border-emerald-900 text-xs">
              <div><span className="text-emerald-300 font-medium">Resolved:</span> {lookupStatus.resolved.yahoo} · {lookupStatus.resolved.name}</div>
              <div className="text-muted mt-0.5">
                {lookupStatus.resolved.exchange ?? "?"} · {lookupStatus.resolved.currency ?? "?"} · {lookupStatus.resolved.type ?? "?"}
                {lookupStatus.resolved.isin && ` · ISIN ${lookupStatus.resolved.isin}`}
                {lookupStatus.resolved.wkn && ` · WKN ${lookupStatus.resolved.wkn}`}
                {` · via ${lookupStatus.resolved.source}`}
              </div>
            </div>
          )}
          {lookupStatus.state === "err" && (
            <div className="mt-2 p-2 rounded bg-rose-950/30 border border-rose-900 text-xs text-rose-300">
              {lookupStatus.message ?? "Lookup failed"}
            </div>
          )}
          <div className="text-[11px] text-muted mt-2">
            Resolves WKN/ISIN via OpenFIGI, picks the EUR/Xetra listing when available, and verifies a Yahoo chart endpoint exists before adding. 5y price history fetched live on add.
          </div>
        </div>

        <div className="mt-5 pt-4 border-t border-zinc-800">
          <div className="text-xs uppercase tracking-wide text-muted mb-2">Add instrument (manual Yahoo symbol)</div>
          <div className="grid grid-cols-12 gap-2 items-end">
            <div className="col-span-3">
              <label className="text-[11px] text-muted">Yahoo symbol</label>
              <input className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm" placeholder="e.g. FUSD.L"
                value={addForm.symbol} onChange={(e)=>setAddForm((p)=>({...p, symbol: e.target.value}))} />
            </div>
            <div className="col-span-3">
              <label className="text-[11px] text-muted">Label</label>
              <input className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm" placeholder="e.g. Fidelity US Quality Income"
                value={addForm.name} onChange={(e)=>setAddForm((p)=>({...p, name: e.target.value}))} />
            </div>
            <div className="col-span-2">
              <label className="text-[11px] text-muted">Sleeve</label>
              <select className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={addForm.sleeve} onChange={(e)=>setAddForm((p)=>({...p, sleeve: e.target.value as Sleeve}))}>
                <option value="core">core</option>
                <option value="tech">tech</option>
                <option value="em">em</option>
              </select>
            </div>
            <div className="col-span-1">
              <label className="text-[11px] text-muted">TER %</label>
              <input type="number" step="0.01" min="0" className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={addForm.ter} onChange={(e)=>setAddForm((p)=>({...p, ter: e.target.value}))} />
            </div>
            <div className="col-span-1">
              <label className="text-[11px] text-muted">Wt %</label>
              <input type="number" step="0.5" min="0" max="100" className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                value={addForm.weight} onChange={(e)=>setAddForm((p)=>({...p, weight: e.target.value}))} />
            </div>
            <div className="col-span-2">
              <button className="btn w-full" onClick={addInst} disabled={!addForm.symbol.trim()}>+ Add</button>
            </div>
          </div>
          <div className="text-[11px] text-muted mt-2">
            Symbol uses the Yahoo Finance ticker (e.g. <code>FUSD.L</code>, <code>VHYL.DE</code>, <code>WQDV.L</code>). Prices are fetched live (5y daily). Funds without Yahoo coverage will show "no data".
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-3">
        <MetricDelta label="Backtested ann. return" value={currentMetrics.annReturn} baseline={baselineMetrics.annReturn} fmt={fmtPct} betterWhen="higher" />
        <MetricDelta label="Annualized vol" value={currentMetrics.annVol} baseline={baselineMetrics.annVol} fmt={fmtPct} betterWhen="lower" />
        <MetricDelta label="Max drawdown" value={currentMetrics.maxDrawdown} baseline={baselineMetrics.maxDrawdown} fmt={fmtPct} betterWhen="higher" />
        <MetricDelta label="Blended TER" value={blendedTerCurrent} baseline={blendedTerBaseline} fmt={fmtPct} betterWhen="lower" />
        <MetricDelta label="Core %" value={sleeveCurrent.core} baseline={sleeveBaseline.core} fmt={fmtPct} betterWhen="higher" />
        <MetricDelta label="Tech %" value={sleeveCurrent.tech} baseline={sleeveBaseline.tech} fmt={fmtPct} betterWhen="higher" />
      </div>

      <div className="card">
        <div className="h-section">Equity curve — current vs baseline (rebased to 100)</div>
        <div className="h-80">
          {equityCmp.length === 0 ? (
            <div className="h-full flex items-center justify-center text-muted text-sm">Loading backtest…</div>
          ) : (
            <ResponsiveContainer>
              <LineChart data={equityCmp}>
                <CartesianGrid stroke="#262b34" strokeDasharray="3 3" />
                <XAxis dataKey="t" tickFormatter={fmtDate} stroke="#8a93a3" fontSize={11} />
                <YAxis stroke="#8a93a3" fontSize={11} />
                <Tooltip labelFormatter={(t)=>fmtDate(Number(t))} formatter={(v:any,n:any)=>[Number(v).toFixed(1), n]}
                  contentStyle={{ background:"#13161b", border:"1px solid #262b34", borderRadius:8, fontSize:12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="baseline" stroke="#8a93a3" dot={false} strokeWidth={2} isAnimationActive={false} />
                <Line type="monotone" dataKey="current" stroke="#6ee7b7" dot={false} strokeWidth={2} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="text-xs text-muted mt-3">
          Backtest period: {currentMetrics.years.toFixed(1)} years of aligned daily data. Fund-only positions (BGF, A3DRHJ) may have shorter history, which truncates the window. Past returns are not predictions.
        </div>
      </div>
    </div>
  );
}
