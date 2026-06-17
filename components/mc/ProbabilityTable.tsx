import type { ScenarioResult } from "@/lib/monteCarlo";
import { fmtPct, fmtEur } from "@/lib/monteCarlo";

interface Props { scenario: ScenarioResult }

export default function ProbabilityTable({ scenario }: Props) {
  const p = scenario.probabilities;
  const g = scenario.goalProbabilities;

  const wealthTargets = Object.entries(g).sort(([a], [b]) => parseInt(a) - parseInt(b));

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div>
        <div className="text-xs text-muted mb-2">Outcome probabilities</div>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-zinc-900">
            <tr><td className="py-1.5">P(any loss at horizon)</td><td className="text-right tabular-nums font-medium">{fmtPct(p.loss, 2)}</td></tr>
            <tr><td className="py-1.5">P(≥1.5×)</td><td className="text-right tabular-nums">{fmtPct(p.ge1_5x, 2)}</td></tr>
            <tr><td className="py-1.5">P(≥2×)</td><td className="text-right tabular-nums">{fmtPct(p.ge2x, 2)}</td></tr>
            <tr><td className="py-1.5">P(≥3×)</td><td className="text-right tabular-nums">{fmtPct(p.ge3x, 2)}</td></tr>
            <tr><td className="py-1.5">P(≥5×)</td><td className="text-right tabular-nums">{fmtPct(p.ge5x, 2)}</td></tr>
            <tr><td className="py-1.5">P(≥10×)</td><td className="text-right tabular-nums">{fmtPct(p.ge10x, 2)}</td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <div className="text-xs text-muted mb-2">Drawdown probabilities</div>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-zinc-900">
            <tr><td className="py-1.5">P(max DD worse than -10%)</td><td className="text-right tabular-nums">{fmtPct(p.ddWorseThan10, 2)}</td></tr>
            <tr><td className="py-1.5">P(max DD worse than -20%)</td><td className="text-right tabular-nums">{fmtPct(p.ddWorseThan20, 2)}</td></tr>
            <tr><td className="py-1.5">P(max DD worse than -30%)</td><td className="text-right tabular-nums">{fmtPct(p.ddWorseThan30, 2)}</td></tr>
            <tr><td className="py-1.5">P(max DD worse than -40%)</td><td className="text-right tabular-nums text-rose-400">{fmtPct(p.ddWorseThan40, 2)}</td></tr>
            <tr><td className="py-1.5">P(max DD worse than -50%)</td><td className="text-right tabular-nums text-rose-400">{fmtPct(p.ddWorseThan50, 2)}</td></tr>
            <tr><td className="py-1.5">P(max DD worse than -60%)</td><td className="text-right tabular-nums text-rose-400">{fmtPct(p.ddWorseThan60, 2)}</td></tr>
          </tbody>
        </table>
      </div>
      <div className="md:col-span-2">
        <div className="text-xs text-muted mb-2">Goal-based: P(terminal wealth ≥ target)</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted border-b border-zinc-800">
              <th className="py-1.5 text-left">Target</th>
              <th className="py-1.5 text-right">Probability</th>
              <th className="py-1.5 text-left text-xs">Visual</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900">
            {wealthTargets.map(([target, prob]) => (
              <tr key={target}>
                <td className="py-1.5">{fmtEur(parseInt(target))}</td>
                <td className="py-1.5 text-right tabular-nums font-medium">{fmtPct(prob, 1)}</td>
                <td className="py-1.5">
                  <div className="bg-zinc-900 rounded h-2 w-full">
                    <div className="bg-blue-500 h-2 rounded" style={{ width: `${prob*100}%` }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
