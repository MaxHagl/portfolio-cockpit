"use client";
import { useState } from "react";
import Link from "next/link";
import type { Peer, Holding } from "@/lib/types";
import CopyButton from "./CopyButton";
import PriceChart from "./PriceChart";

function pctSigned(n: number) { const v = n*100; return `${v>=0?"+":""}${v.toFixed(2)}%`; }

export default function PeerCard({ peer, current }: { peer: Peer; current: Holding }) {
  const [open, setOpen] = useState(false);
  const feeDelta = peer.vsCurrent.feeDelta;
  const feeColor = feeDelta < 0 ? "text-accent" : feeDelta > 0 ? "text-danger" : "text-muted";
  const overlap = peer.vsCurrent.overlap;

  return (
    <div className="card-sub">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-medium">{peer.id} <span className="text-muted font-normal">— {peer.type}</span></div>
          <div className="text-xs text-muted line-clamp-2">{peer.name}</div>
        </div>
        <div className="flex gap-1 flex-wrap">
          <CopyButton value={peer.wkn} label={`WKN ${peer.wkn}`} />
          <CopyButton value={peer.isin} label={`ISIN ${peer.isin}`} />
          <a className="chip hover:bg-line" target="_blank" rel="noreferrer" href={`https://www.justetf.com/en/etf-profile.html?isin=${peer.isin}`}>justETF ↗</a>
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-2 mt-3 text-xs">
        <div className="card-sub !p-2"><div className="text-muted">TER</div><div className="font-medium tabular-nums">{(peer.ter*100).toFixed(2)}%</div></div>
        <div className="card-sub !p-2"><div className="text-muted">Fee vs {current.shortName}</div><div className={`font-medium tabular-nums ${feeColor}`}>{pctSigned(feeDelta)}</div></div>
        <div className="card-sub !p-2"><div className="text-muted">Overlap</div><div className="font-medium tabular-nums">{(overlap*100).toFixed(0)}%</div></div>
      </div>

      <p className="text-sm mt-3 text-ink/90">{peer.thesis}</p>

      <div className="grid md:grid-cols-2 gap-3 mt-3">
        <div>
          <div className="h-section text-accent">Why pick</div>
          <ul className="space-y-1 text-sm">{peer.whyPick.map((x,i)=><li key={i} className="flex gap-2"><span className="text-accent">+</span><span>{x}</span></li>)}</ul>
        </div>
        <div>
          <div className="h-section text-danger">Why not</div>
          <ul className="space-y-1 text-sm">{peer.whyNot.map((x,i)=><li key={i} className="flex gap-2"><span className="text-danger">−</span><span>{x}</span></li>)}</ul>
        </div>
      </div>

      <div className="flex gap-2 mt-3 flex-wrap">
        <button className="btn" onClick={()=>setOpen((v)=>!v)}>{open ? "Hide" : "Compare"} chart vs {current.shortName}</button>
        <Link className="btn-accent" href={`/sandbox?swap=${current.id}:${peer.id}`}>Swap into sandbox →</Link>
      </div>

      {open && (
        <div className="mt-3">
          <PriceChart symbols={[current.id, peer.id]} colors={{ [current.id]: "#6ee7b7", [peer.id]: "#a78bfa" }} />
        </div>
      )}
    </div>
  );
}
