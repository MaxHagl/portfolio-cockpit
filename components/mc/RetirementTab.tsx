import { retirementMC } from "@/lib/monteCarloV2";
import { fmtEur, fmtPct } from "@/lib/monteCarlo";
import FanChart from "@/components/mc/FanChart";

const mc = retirementMC;

export default function RetirementTab() {
  const startingEur = 21302;
  const horizon = mc.inputs.horizonYears;
  const strategies = mc.strategies;

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="h-section">Setup</div>
        <p className="text-sm text-zinc-300">
          15y accumulation with €{mc.inputs.accumulationMonthly}/mo DCA + {fmtPct(mc.inputs.accumulationGrowth, 0)}/yr salary growth.
          Years 15-30: decumulation phase, {fmtPct(mc.inputs.inflationRate, 0)} inflation-indexed withdrawal.
          {mc.inputs.pathsRetirement.toLocaleString()} paths over 30 years via long-history bootstrap (2000-2026 pool).
        </p>
      </div>

      <div className="card">
        <div className="h-section">Strategy comparison — withdrawal sustainability</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Strategy</th>
                <th className="py-2 pr-3 text-right">Year-15 wealth (median)</th>
                <th className="py-2 pr-3 text-right">P(depleted by yr 30)</th>
                <th className="py-2 pr-3 text-right">Median years to depletion</th>
                <th className="py-2 pr-3 text-right">Median terminal (posttax)</th>
                <th className="py-2 pr-3 text-right">Total tax paid</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(strategies).map(([key, s]) => {
                const depl = s.pDepletedYear30;
                const toneCls = depl > 0.5 ? "text-rose-400" : depl > 0.2 ? "text-amber-400" : "text-emerald-400";
                return (
                  <tr key={key} className="border-b border-zinc-900">
                    <td className="py-2 pr-3">
                      <div className="font-medium">{s.label}</div>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(s.year15Wealth.median)}</td>
                    <td className={`py-2 pr-3 text-right tabular-nums font-medium ${toneCls}`}>{fmtPct(depl, 1)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {s.medianYearsToDepletion !== null ? `${s.medianYearsToDepletion.toFixed(1)}y` : <span className="text-emerald-400">survives</span>}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(s.terminalPosttax.median)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-xs">{fmtEur(s.totalTaxPaid)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4% rule fan chart */}
      {strategies.fourPctRule && (
        <div className="card">
          <div className="h-section">4% rule — 30y wealth trajectory</div>
          <FanChart
            fan={strategies.fourPctRule.fanChart}
            samples={strategies.fourPctRule.samplePaths}
            startingEur={startingEur}
            horizonYears={30}
          />
          <p className="text-xs text-muted mt-2">
            Vertical line at year 15 = withdrawal phase begins.
            P(depleted): {fmtPct(strategies.fourPctRule.pDepletedYear30, 1)}
          </p>
        </div>
      )}

      {/* €1500/mo */}
      {strategies.fixed1500 && (
        <div className="card">
          <div className="h-section">€1500/mo real (inflation-indexed) — 30y trajectory</div>
          <FanChart
            fan={strategies.fixed1500.fanChart}
            samples={strategies.fixed1500.samplePaths}
            startingEur={startingEur}
            horizonYears={30}
          />
        </div>
      )}

      <div className="card text-sm text-zinc-300">
        <div className="h-section">Reality check</div>
        <p>
          With only €50/mo DCA over 15y, year-15 wealth median ≈ €{Math.round(strategies.fourPctRule?.year15Wealth.median / 1000)}k.
          The 4% rule on this base gives ~€{Math.round((strategies.fourPctRule?.year15Wealth.median * 0.04) / 12)}/mo withdrawal —
          modest but sustainable. Fixed €1500-5000/mo withdrawals deplete because the base is too small.
        </p>
        <p className="mt-2 text-zinc-400">
          To sustain €1500/mo real lifelong from this portfolio, you'd need year-15 wealth ≈ €450k. At current DCA rate that means
          either much higher monthly contributions (€200-500/mo + growth) or extending accumulation to 20-25y.
        </p>
      </div>
    </div>
  );
}
