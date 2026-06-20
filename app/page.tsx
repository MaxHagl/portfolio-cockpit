import { holdingsData, allocationsData } from "@/lib/data";
import HoldingsTable from "@/components/HoldingsTable";
import SleeveBar from "@/components/SleeveBar";
import AllocationDonut from "@/components/AllocationDonut";
import LookThroughTable from "@/components/LookThroughTable";
import LookThroughCountries from "@/components/LookThroughCountries";
import LookThroughThemes from "@/components/LookThroughThemes";
import Link from "next/link";

export default function Dashboard() {
  const slices = holdingsData.holdings.map((h) => ({
    id: h.id,
    label: h.shortName,
    value: h.weight,
    color: holdingsData.sleeves[h.sleeve].color,
  }));
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
  const blendedTer = holdingsData.holdings.reduce((a, h) => a + h.weight * h.ter, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Current proposal — Idea 3 updated</h1>
        <p className="text-muted text-sm mt-1">68% core / 20% tech / 12% EM. Long horizon, high-risk-tolerant. Click any holding to see comparable alternatives.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="card lg:col-span-1">
          <div className="h-section">Allocation</div>
          <AllocationDonut data={slices} totalLabel={eur(holdingsData.totalEur)} />
        </div>
        <div className="card lg:col-span-2 space-y-5">
          <div>
            <div className="h-section">Sleeve mix</div>
            <SleeveBar data={holdingsData} />
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div className="card-sub">
              <div className="text-xs text-muted">Holdings</div>
              <div className="text-xl font-semibold">{holdingsData.holdings.length}</div>
            </div>
            <div className="card-sub">
              <div className="text-xs text-muted">Blended TER</div>
              <div className="text-xl font-semibold tabular-nums">{(blendedTer*100).toFixed(2)}%</div>
            </div>
            <div className="card-sub">
              <div className="text-xs text-muted">Cash deployed</div>
              <div className="text-xl font-semibold tabular-nums">{eur(holdingsData.totalEur)}</div>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Link href="/sandbox" className="btn-accent">Open sandbox →</Link>
            <Link href="/analysis/monte-carlo" className="btn-accent">Monte Carlo analysis →</Link>
            <a className="btn" href="https://www.justetf.com/" target="_blank" rel="noreferrer">justETF</a>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="h-section">
          Holdings
          {allocationsData.returnsWindow && allocationsData.hrp && (
            <span className="ml-2 text-xs text-muted font-normal">
              HRP suggestion based on {allocationsData.returnsWindow.days} days
              ({allocationsData.returnsWindow.start} → {allocationsData.returnsWindow.end}),
              linkage: {allocationsData.linkage}
            </span>
          )}
          {!allocationsData.hrp && allocationsData.note && (
            <span className="ml-2 text-xs text-muted font-normal">{allocationsData.note}</span>
          )}
        </div>
        <HoldingsTable data={holdingsData} allocations={allocationsData} />
      </div>

      <div className="card">
        <div className="h-section">Look-through positions ≥ 1%</div>
        <LookThroughTable minWeight={0.01} />
      </div>

      <div className="card">
        <div className="h-section">Look-through countries ≥ 1%</div>
        <LookThroughCountries minWeight={0.01} />
      </div>

      <div className="card">
        <div className="h-section">Look-through themes ≥ 1%</div>
        <LookThroughThemes minWeight={0.01} />
      </div>

      <div className="card text-sm text-muted">
        <div className="h-section">How to use this site</div>
        <ol className="list-decimal pl-5 space-y-1.5">
          <li>Open a holding — read its thesis, risk, and upside; check the 5-year chart.</li>
          <li>Click <strong>See peers</strong> on the holding page to browse curated alternatives with risk-vs-upside callouts and overlap/fee deltas.</li>
          <li>From any peer, hit <strong>Swap into sandbox</strong> to substitute it for the current holding.</li>
          <li>In <Link href="/sandbox" className="text-accent">/sandbox</Link>, tweak weights and compare blended return, vol, and drawdown vs the 68/20/12 baseline.</li>
          <li>Bring your decision back to chat — happy to pressure-test it.</li>
        </ol>
      </div>
    </div>
  );
}
