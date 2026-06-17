import type { StressEpisode } from "@/lib/monteCarlo";
import { fmtEur, fmtPct } from "@/lib/monteCarlo";

interface Props {
  stress: Record<string, StressEpisode>;
  startingEur: number;
}

const EPISODE_LABEL: Record<string, string> = {
  dotcom2000: "Dotcom collapse (2000–2007)",
  gfc2008: "Global Financial Crisis (2007–2013)",
  covid2020: "COVID crash (2020–2021)",
};

export default function StressTable({ stress, startingEur }: Props) {
  const entries = Object.entries(stress);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-zinc-800">
            <th className="py-2 pr-3">Episode</th>
            <th className="py-2 pr-3 text-right">Peak drawdown</th>
            <th className="py-2 pr-3 text-right">Days to trough</th>
            <th className="py-2 pr-3 text-right">Days to recover</th>
            <th className="py-2 pr-3 text-right">Trough wealth</th>
            <th className="py-2 pr-3 text-right">Terminal wealth</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, ep]) => (
            <tr key={key} className="border-b border-zinc-900">
              <td className="py-2 pr-3">
                <div className="font-medium">{EPISODE_LABEL[key] ?? ep.description}</div>
                {ep.available && ep.windowStart && (
                  <div className="text-xs text-muted">{ep.windowStart} → {ep.windowEnd}</div>
                )}
              </td>
              {ep.available ? (
                <>
                  <td className="py-2 pr-3 text-right tabular-nums text-rose-400 font-medium">{fmtPct(ep.peakDrawdown!, 1)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{ep.daysToTrough}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{ep.daysToRecover ?? <span className="text-rose-400">never (in window)</span>}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(ep.troughEur!)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(ep.terminalEur!)}</td>
                </>
              ) : (
                <td colSpan={5} className="py-2 text-xs text-muted">{ep.note ?? "data unavailable"}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted mt-2">
        Replay using index proxies (SPX / NDX / EEM / URTH) mapped to current weights and applied to today's €{startingEur.toLocaleString("de-DE")} starting wealth.
        Labelled as analog — not historical actuals (BGF/A3DRHJ etc. didn't exist).
      </p>
    </div>
  );
}
