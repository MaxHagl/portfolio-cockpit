import Link from "next/link";
import type { Holding, HoldingsFile, AllocationsFile } from "@/lib/types";
import CopyButton from "./CopyButton";

export default function HoldingsTable({
  data,
  allocations,
}: {
  data: HoldingsFile;
  allocations?: AllocationsFile;
}) {
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const pp = (n: number) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}pp`;

  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Fund</th>
          <th>Identifiers</th>
          <th>Sleeve</th>
          <th className="text-right">€</th>
          <th className="text-right">Weight</th>
          {allocations?.hrp && <th className="text-right" title="Hierarchical Risk Parity (Lopez de Prado 2016) suggested weight based on cached daily returns">HRP</th>}
          {allocations?.delta && <th className="text-right">Δ</th>}
          <th className="text-right">TER</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {data.holdings.map((h: Holding) => {
          const sl = data.sleeves[h.sleeve];
          const hrpW = allocations?.hrp?.[h.id];
          const delta = allocations?.delta?.[h.id];
          const deltaColor =
            delta === undefined ? "" : delta > 0.02 ? "text-emerald-400" : delta < -0.02 ? "text-rose-400" : "text-muted";
          return (
            <tr key={h.id}>
              <td>
                <div className="font-medium">{h.shortName}</div>
                <div className="text-xs text-muted line-clamp-1">{h.name}</div>
              </td>
              <td>
                <div className="flex gap-1 flex-wrap">
                  <CopyButton value={h.wkn} label={`WKN ${h.wkn}`} />
                  <CopyButton value={h.isin} label={`ISIN ${h.isin}`} />
                </div>
              </td>
              <td>
                <span className="chip" style={{ color: sl.color, borderColor: sl.color + "55" }}>{sl.label}</span>
              </td>
              <td className="text-right tabular-nums">{eur(h.eur)}</td>
              <td className="text-right tabular-nums">{pct(h.weight)}</td>
              {allocations?.hrp && (
                <td className="text-right tabular-nums">{hrpW !== undefined ? pct(hrpW) : "—"}</td>
              )}
              {allocations?.delta && (
                <td className={`text-right tabular-nums ${deltaColor}`}>{delta !== undefined ? pp(delta) : "—"}</td>
              )}
              <td className="text-right tabular-nums">{(h.ter * 100).toFixed(2)}%</td>
              <td className="text-right">
                <Link href={`/holding/${h.id}`} className="btn-accent">Open</Link>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
