import { accumulationMC } from "@/lib/monteCarloV2";
import { fmtEur, fmtPct } from "@/lib/monteCarlo";
import FanChart from "@/components/mc/FanChart";
import TerminalWealthHistogram from "@/components/mc/TerminalWealthHistogram";

const mc = accumulationMC;

export default function AccumulationTab() {
  const startingEur = mc.inputs.startingEur;
  const horizon = mc.inputs.horizonYears;

  const dca50 = mc.dcaSweep["eur50"];
  const dca500 = mc.dcaSweep["eur500"];
  const lh50 = mc.longHistory.scenarios["eur50"];

  return (
    <div className="space-y-6">
      {/* DCA Sweep */}
      <div className="card">
        <div className="h-section">DCA contribution sweep — baseline portfolio</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Monthly</th>
                <th className="py-2 pr-3 text-right">Total contributed</th>
                <th className="py-2 pr-3 text-right">Median terminal</th>
                <th className="py-2 pr-3 text-right">p10 / p90</th>
                <th className="py-2 pr-3 text-right">Median ann ret.</th>
                <th className="py-2 pr-3 text-right">P(loss)</th>
                <th className="py-2 pr-3 text-right">Median max DD</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(mc.dcaSweep).map(([key, sc]) => {
                const monthly = parseInt(key.replace("eur", ""));
                return (
                  <tr key={key} className="border-b border-zinc-900">
                    <td className="py-2 pr-3 font-medium">€{monthly}/mo</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{sc.totalContributed ? fmtEur(sc.totalContributed) : "—"}</td>
                    <td className="py-2 pr-3 text-right tabular-nums font-medium">{fmtEur(sc.terminal.median)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-xs">{fmtEur(sc.terminal.p10)} / {fmtEur(sc.terminal.p90)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.annReturn.median, 2)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtPct(sc.probabilities.loss, 2)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-rose-400">{fmtPct(sc.maxDrawdown.median, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* €50 DCA fan chart */}
      <div className="card">
        <div className="h-section">Wealth trajectory — €50/mo DCA (your default)</div>
        {dca50.fanChart && (
          <FanChart fan={dca50.fanChart} samples={dca50.samplePaths} startingEur={startingEur} horizonYears={horizon} />
        )}
      </div>

      {/* Long-history reality check */}
      <div className="card">
        <div className="h-section">Long-history reality check (2000-2026 incl. dotcom + GFC)</div>
        <p className="text-xs text-muted mb-3">
          Re-runs the simulation on 26.5y bootstrap pool covering dotcom collapse, GFC, COVID.
          P(loss) becomes realistic vs v1's bull-only sample.
        </p>
        <div className="grid md:grid-cols-3 gap-3">
          {Object.entries(mc.longHistory.scenarios).map(([key, sc]) => {
            const monthly = parseInt(key.replace("eur", ""));
            return (
              <div key={key} className="card-sub">
                <div className="text-xs text-muted">€{monthly}/mo DCA</div>
                <div className="text-xl font-semibold tabular-nums">{fmtEur(sc.terminal.median)}</div>
                <div className="text-xs text-muted mt-0.5">P(loss): <span className="text-rose-400">{fmtPct(sc.probabilities.loss, 1)}</span> · Max DD: <span className="text-rose-400">{fmtPct(sc.maxDrawdown.median, 0)}</span></div>
              </div>
            );
          })}
        </div>
        {lh50.fanChart && (
          <div className="mt-4">
            <div className="text-xs text-muted mb-1">€50/mo DCA — fan chart on long-history pool:</div>
            <FanChart fan={lh50.fanChart} samples={lh50.samplePaths} startingEur={startingEur} horizonYears={horizon} />
          </div>
        )}
      </div>

      {/* Regime + stochastic inflation + jumps */}
      <div className="grid md:grid-cols-3 gap-5">
        <div className="card">
          <div className="h-section">Regime-switching HMM</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.regimeSwitching.result.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median · π_bear={fmtPct(mc.regimeSwitching.diagnostics.stationaryDist[0], 0)} ·
            {" "}bear vol {(mc.regimeSwitching.diagnostics.bearVolDaily * Math.sqrt(252) * 100).toFixed(1)}%/yr ·
            {" "}P(loss) {fmtPct(mc.regimeSwitching.result.probabilities.loss, 1)}
          </div>
        </div>
        <div className="card">
          <div className="h-section">Stochastic inflation (€50 DCA real)</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.stochasticInflation.result.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            15y geo-mean: median {fmtPct(mc.stochasticInflation.diagnostics.median15yAnnInflation, 1)} ·
            p95 {fmtPct(mc.stochasticInflation.diagnostics.p95, 1)} ·
            P(real loss) {fmtPct(mc.stochasticInflation.result.probabilities.loss, 1)}
          </div>
        </div>
        <div className="card">
          <div className="h-section">Jump-diffusion overlay</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.jumpDiffusion.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median terminal · 3 crashes/yr Poisson · median max DD: <span className="text-rose-400">{fmtPct(mc.jumpDiffusion.maxDrawdown.median, 0)}</span>
          </div>
        </div>
      </div>

      {/* Hedged + drawdown buy + ESG */}
      <div className="grid md:grid-cols-3 gap-5">
        <div className="card">
          <div className="h-section">EUR-hedged USD assets</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.hedged.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median · +30 bps hedging cost · removes FX vol from BGF/XDWT/SWDA/VWCE USD portions
          </div>
        </div>
        <div className="card">
          <div className="h-section">Drawdown-buy overlay (2× DCA on -20% DD)</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.drawdownBuy.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median · vs base €50/mo {fmtEur(dca50.terminal.median)} (delta {fmtEur(mc.drawdownBuy.terminal.median - dca50.terminal.median)})
          </div>
        </div>
        <div className="card">
          <div className="h-section">ESG screen (-10bps drag)</div>
          <div className="text-2xl font-semibold tabular-nums">{fmtEur(mc.esgScreen.terminal.median)}</div>
          <div className="text-xs text-muted mt-1">
            median · vs base {fmtEur(dca50.terminal.median)} (drag {fmtEur(dca50.terminal.median - mc.esgScreen.terminal.median)})
          </div>
        </div>
      </div>

      {/* Broker fees */}
      <div className="card">
        <div className="h-section">Broker fee impact — €50/mo Sparplan over 15y</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-zinc-800">
                <th className="py-2 pr-3">Broker</th>
                <th className="py-2 pr-3 text-right">Fee/contrib.</th>
                <th className="py-2 pr-3 text-right">Net total contributed</th>
                <th className="py-2 pr-3 text-right">Median terminal</th>
                <th className="py-2 pr-3 text-right">Drag vs €0 broker</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(mc.brokerFees).map(([key, b]) => {
                const trMed = mc.brokerFees["tradeRepublic"].medianTerminal;
                return (
                  <tr key={key} className="border-b border-zinc-900">
                    <td className="py-2 pr-3 font-medium">{key}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">€{b.feeEurPerContribution.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(b.totalContributedNet)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{fmtEur(b.medianTerminal)}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-xs">{fmtEur(b.medianTerminal - trMed)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
