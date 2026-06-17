import { notFound } from "next/navigation";
import Link from "next/link";
import { getHolding, getPeers, holdingsData } from "@/lib/data";
import RiskUpsideBlock from "@/components/RiskUpsideBlock";
import PriceChart from "@/components/PriceChart";
import PeerCard from "@/components/PeerCard";
import CopyButton from "@/components/CopyButton";

export function generateStaticParams() {
  return holdingsData.holdings.map((h) => ({ id: h.id }));
}

export default async function HoldingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const h = getHolding(id);
  if (!h) notFound();
  const peers = getPeers(h.id);
  const sleeve = holdingsData.sleeves[h.sleeve];
  const eur = (n: number) => n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted">
        <Link href="/" className="hover:text-ink">Dashboard</Link>
        <span>/</span>
        <span className="text-ink">{h.shortName}</span>
      </div>

      <div className="card">
        <div className="flex flex-wrap items-start gap-4 justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-semibold">{h.shortName}</h1>
              <span className="chip" style={{ color: sleeve.color, borderColor: sleeve.color+"55" }}>{sleeve.label}</span>
              <span className="chip">{h.type}</span>
            </div>
            <div className="text-muted text-sm mt-1">{h.name}</div>
          </div>
          <div className="flex flex-wrap gap-1">
            <CopyButton value={h.wkn} label={`WKN ${h.wkn}`} />
            <CopyButton value={h.isin} label={`ISIN ${h.isin}`} />
            {h.links?.justETF && <a className="chip hover:bg-line" target="_blank" rel="noreferrer" href={h.links.justETF}>justETF ↗</a>}
            {h.links?.fund && <a className="chip hover:bg-line" target="_blank" rel="noreferrer" href={h.links.fund}>Fund page ↗</a>}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5 text-sm">
          <div className="card-sub"><div className="text-xs text-muted">Position</div><div className="text-lg font-semibold tabular-nums">{eur(h.eur)}</div></div>
          <div className="card-sub"><div className="text-xs text-muted">Weight</div><div className="text-lg font-semibold tabular-nums">{(h.weight*100).toFixed(1)}%</div></div>
          <div className="card-sub"><div className="text-xs text-muted">TER</div><div className="text-lg font-semibold tabular-nums">{(h.ter*100).toFixed(2)}%</div></div>
          <div className="card-sub"><div className="text-xs text-muted">Sleeve</div><div className="text-lg font-semibold" style={{ color: sleeve.color }}>{sleeve.label}</div></div>
        </div>

        <p className="mt-5 text-ink/90 leading-relaxed">{h.thesis}</p>
      </div>

      <div className="card">
        <div className="h-section">Risk &amp; upside</div>
        <RiskUpsideBlock risk={h.risk} upside={h.upside} />
      </div>

      <div className="card">
        <div className="h-section">Price history</div>
        <PriceChart symbols={[h.id]} colors={{ [h.id]: sleeve.color }} />
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="h-section !mb-0">See peers</div>
            <div className="text-sm text-muted">Curated alternatives I'd consider for the {sleeve.label.toLowerCase()} slot. Pick, compare, swap.</div>
          </div>
          <Link href="/sandbox" className="btn">Open sandbox →</Link>
        </div>
        <div className="space-y-3">
          {peers.length === 0 && <div className="text-muted text-sm">No curated peers yet for this holding.</div>}
          {peers.map((p) => <PeerCard key={p.id} peer={p} current={h} />)}
        </div>
      </div>
    </div>
  );
}
