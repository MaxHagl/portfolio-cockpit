import type { HoldingsFile } from "@/lib/types";

export default function SleeveBar({ data }: { data: HoldingsFile }) {
  const totals: Record<string, number> = { core: 0, tech: 0, em: 0 };
  for (const h of data.holdings) totals[h.sleeve] = (totals[h.sleeve] ?? 0) + h.weight;
  const order: Array<"core"|"tech"|"em"> = ["core","tech","em"];
  return (
    <div>
      <div className="flex w-full h-3 rounded-full overflow-hidden border border-line">
        {order.map((s) => (
          <div key={s} style={{ width: `${(totals[s]||0)*100}%`, background: data.sleeves[s].color }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3 mt-3 text-sm">
        {order.map((s) => (
          <div key={s} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: data.sleeves[s].color }} />
            <span className="text-muted">{data.sleeves[s].label}</span>
            <span className="font-medium tabular-nums">{((totals[s]||0)*100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
