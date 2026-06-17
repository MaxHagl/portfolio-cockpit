import holdings from "@/data/holdings.json";
import peers from "@/data/peers.json";
import type { HoldingsFile, PeersFile, Holding, Peer } from "./types";

export const holdingsData = holdings as HoldingsFile;
export const peersData = peers as PeersFile;

export function getHolding(id: string): Holding | undefined {
  return holdingsData.holdings.find((h) => h.id === id);
}

export function getPeers(holdingId: string): Peer[] {
  return peersData[holdingId] ?? [];
}

export function findInstrument(id: string): { kind: "holding"; h: Holding } | { kind: "peer"; p: Peer; for: string } | undefined {
  const h = getHolding(id);
  if (h) return { kind: "holding", h };
  for (const [hid, list] of Object.entries(peersData)) {
    const p = list.find((x) => x.id === id);
    if (p) return { kind: "peer", p, for: hid };
  }
  return undefined;
}

export function yahooFor(id: string): string | undefined {
  const inst = findInstrument(id);
  if (!inst) return undefined;
  return inst.kind === "holding" ? inst.h.yahoo : inst.p.yahoo;
}

export function isinFor(id: string): string | undefined {
  const inst = findInstrument(id);
  if (!inst) return undefined;
  return inst.kind === "holding" ? inst.h.isin : inst.p.isin;
}
