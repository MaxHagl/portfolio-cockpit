import { mc, isStale, fmtEur, fmtPct } from "@/lib/monteCarlo";
import FanChart from "@/components/mc/FanChart";
import TerminalWealthHistogram from "@/components/mc/TerminalWealthHistogram";
import DrawdownHistogram from "@/components/mc/DrawdownHistogram";
import ScenarioComparison from "@/components/mc/ScenarioComparison";
import ProbabilityTable from "@/components/mc/ProbabilityTable";
import StressTable from "@/components/mc/StressTable";
import MethodologyPanel from "@/components/mc/MethodologyPanel";

export default function TodayTab() {
  const baseline = mc.engines.bootstrap.scenarios.baseline;
  const startingEur = mc.inputs.startingEur;
  const horizon = mc.inputs.horizonYears;
  const stale = isStale();

  const bootMedian = mc.engines.bootstrap.scenarios.baseline.terminal.median;
  const tMedian = mc.engines.parametricT.scenarios.baseline.terminal.median;
  const fhsMedian = mc.engines.fhs.scenarios.baseline.terminal.median;

  return (
    <div className="space-y-6">
      {stale && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
          ⚠ Weights or data are stale (weights changed since MC ran, or output &gt;30 days old).
          Re-run: <code className="text-amber-300">npm run monte-carlo</code>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Callout label="Median terminal" value={fmtEur(baseline.terminal.median)} sub={`${(baseline.terminal.median / startingEur).toFixed(1)}x start`} />
        <Callout label="p10 / p90 terminal" value={`${fmtEur(baseline.terminal.p10)}`} sub={`p90 ${fmtEur(baseline.terminal.p90)}`} />
        <Callout label="Median ann. return" value={fmtPct(baseline.annReturn.median, 2)} sub={`p10 ${fmtPct(baseline.annReturn.p10, 2)}`} />
        <Callout label="P(loss at horizon)" value={fmtPct(baseline.probabilities.loss, 1)} sub="nominal" tone={baseline.probabilities.loss > 0.1 ? "warn" : "ok"} />
        <Callout label="P(≥3× money)" value={fmtPct(baseline.probabilities.ge3x || 0, 1)} sub="" tone="ok" />
        <Callout label="Worst-5% (ES)" value={fmtEur(baseline.terminal.expectedShortfall5)} sub={`${(baseline.terminal.expectedShortfall5 / startingEur).toFixed(2)}x`} tone="warn" />
      </div>

      <div className="card">
        <div className="h-section">Wealth trajectory — bootstrap engine</div>
        <FanChart fan={baseline.fanChart!} samples={baseline.samplePaths} startingEur={startingEur} horizonYears={horizon} />
        <p className="text-xs text-muted mt-2">
          Block bootstrap of historical daily returns. Block length {mc.inputs.blockLengthBootstrap}d preserves vol clustering.
        </p>
      </div>

      <div className="card">
        <div className="h-section">Scenario comparison — bootstrap engine</div>
        <ScenarioComparison scenarios={mc.engines.bootstrap.scenarios} startingEur={startingEur} />
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card">
          <div className="h-section">Terminal wealth distribution</div>
          <TerminalWealthHistogram hist={baseline.terminalHistogram!} startingEur={startingEur} />
        </div>
        <div className="card">
          <div className="h-section">Max drawdown distribution</div>
          <DrawdownHistogram hist={baseline.maxDdHistogram!} />
        </div>
      </div>

      <div className="card">
        <div className="h-section">Probabilities &amp; goal targets — baseline</div>
        <ProbabilityTable scenario={baseline} />
      </div>

      <div className="card">
        <div className="h-section">Engine convergence — median terminal wealth, baseline</div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="card-sub">
            <div className="text-xs text-muted">Bootstrap</div>
            <div className="text-xl font-semibold tabular-nums">{fmtEur(bootMedian)}</div>
          </div>
          <div className="card-sub">
            <div className="text-xs text-muted">Parametric t</div>
            <div className="text-xl font-semibold tabular-nums">{fmtEur(tMedian)}</div>
            <div className="text-xs text-muted">ν = {mc.engines.parametricT.nu?.toFixed(1)}</div>
          </div>
          <div className="card-sub">
            <div className="text-xs text-muted">FHS-GARCH</div>
            <div className="text-xl font-semibold tabular-nums">{fmtEur(fhsMedian)}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="h-section">Rebalancing frequency sensitivity</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted border-b border-zinc-800">
              <th className="py-2 pr-3">Frequency</th>
              <th className="py-2 pr-3 text-right">Median terminal</th>
              <th className="py-2 pr-3 text-right">p10 terminal</th>
              <th className="py-2 pr-3 text-right">Median max DD</th>
              <th className="py-2 pr-3 text-right">P(loss)</th>
            </tr></thead>
            <tbody>
              {Object.entries(mc.rebalancingSensitivity.baseline).map(([freq, sc]) => (
                <tr key={freq} className="border-b border-zinc-900">
                  <td className="py-2 pr-3 font-medium">{freq}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(sc.terminal.median)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(sc.terminal.p10)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums text-rose-400">{fmtPct(sc.maxDrawdown.median, 1)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.probabilities.loss, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        <div className="card">
          <div className="h-section">After Vorabpauschale</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.taxModeling.baselinePosttax.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median terminal · vs pre-tax {fmtEur(baseline.terminal.median)}
          </div>
        </div>
        <div className="card">
          <div className="h-section">Real (2% inflation)</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.realReturns.baseline2pct.terminal.median)}</div>
        </div>
        <div className="card">
          <div className="h-section">EUR/USD overlay</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.currencyOverlay.baseline.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            FX adds {fmtPct(mc.currencyOverlay.fxVolContribution, 1)} to terminal std
          </div>
        </div>
      </div>

      <div className="card">
        <div className="h-section">Historical stress replays</div>
        <StressTable stress={mc.stress} startingEur={startingEur} />
      </div>

      <div className="card">
        <MethodologyPanel mc={mc} />
      </div>
    </div>
  );
}

function Callout({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: "warn" | "ok" }) {
  const color = tone === "warn" ? "text-rose-400" : tone === "ok" ? "text-emerald-400" : "text-zinc-100";
  return (
    <div className="card-sub">
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-xl font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}
