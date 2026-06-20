import Link from "next/link";
import type { Holding, HoldingsFile } from "@/lib/types";
import CopyButton from "./CopyButton";

export default function HoldingsTable({ data }: { data: HoldingsFile }) {
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Fund</th>
          <th>Identifiers</th>
          <th>Sleeve</th>
          <th className="text-right">€</th>
          <th className="text-right">Weight</th>
          <th className="text-right">TER</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {data.holdings.map((h: Holding) => {
          const sl = data.sleeves[h.sleeve];
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
