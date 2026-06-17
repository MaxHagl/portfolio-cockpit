import type { ScenarioResult } from "@/lib/monteCarlo";
import { fmtEur, fmtPct } from "@/lib/monteCarlo";

interface Props {
  scenarios: Record<string, ScenarioResult>;
  startingEur: number;
}

export default function ScenarioComparison({ scenarios, startingEur }: Props) {
  const entries = Object.entries(scenarios);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-zinc-800">
            <th className="py-2 pr-3">Scenario</th>
            <th className="py-2 pr-3 text-right">Median term.</th>
            <th className="py-2 pr-3 text-right">p10 term.</th>
            <th className="py-2 pr-3 text-right">p90 term.</th>
            <th className="py-2 pr-3 text-right">Median ann. ret.</th>
            <th className="py-2 pr-3 text-right">Median max DD</th>
            <th className="py-2 pr-3 text-right">P(loss)</th>
            <th className="py-2 pr-3 text-right">P(≥3×)</th>
            <th className="py-2 pr-3 text-right">ES-5%</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, sc]) => (
            <tr key={key} className="border-b border-zinc-900">
              <td className="py-2 pr-3">
                <div className="font-medium">{sc.label}</div>
                <div className="text-xs text-muted">
                  {Object.entries(sc.weights).map(([a, w]) => `${a} ${(w*100).toFixed(0)}%`).join(" / ")}
                </div>
              </td>
              <td className="py-2 pr-3 text-right tabular-nums font-medium">{fmtEur(sc.terminal.median)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(sc.terminal.p10)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(sc.terminal.p90)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.annReturn.median, 2)}</td>
              <td className="py-2 pr-3 text-right tabular-nums text-rose-400">{fmtPct(sc.maxDrawdown.median, 1)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.probabilities.loss, 1)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.probabilities.ge3x || 0, 1)}</td>
              <td className="py-2 pr-3 text-right tabular-nums text-rose-400">{fmtEur(sc.terminal.expectedShortfall5)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted mt-2">ES-5% = expected shortfall (mean terminal wealth in worst 5% of paths). All metrics over {scenarios.baseline ? "15-year" : ""} horizon.</p>
    </div>
  );
}
