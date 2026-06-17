import { holdingsData } from "./data";

export interface LookThroughPosition {
  ticker: string;
  name: string;
  weight: number;
  eur: number;
  breakdown: { holdingId: string; holdingShortName: string; contribution: number }[];
}

export function lookThroughPositions(): LookThroughPosition[] {
  const agg = new Map<string, LookThroughPosition>();
  for (const h of holdingsData.holdings) {
    if (!h.topHoldings) continue;
    for (const s of h.topHoldings) {
      const contribution = h.weight * s.weight;
      const existing = agg.get(s.ticker);
      if (existing) {
        existing.weight += contribution;
        existing.eur += contribution * holdingsData.totalEur;
        existing.breakdown.push({ holdingId: h.id, holdingShortName: h.shortName, contribution });
      } else {
        agg.set(s.ticker, {
          ticker: s.ticker,
          name: s.name,
          weight: contribution,
          eur: contribution * holdingsData.totalEur,
          breakdown: [{ holdingId: h.id, holdingShortName: h.shortName, contribution }],
        });
      }
    }
  }
  return Array.from(agg.values()).sort((a, b) => b.weight - a.weight);
}

export function topHoldingsCoverage(): { fundsWithData: number; totalFunds: number; asOfDates: string[] } {
  const total = holdingsData.holdings.length;
  const withData = holdingsData.holdings.filter((h) => h.topHoldings && h.topHoldings.length > 0).length;
  const dates = Array.from(
    new Set(
      holdingsData.holdings
        .map((h) => h.topHoldingsAsOf)
        .filter((d): d is string => Boolean(d))
    )
  );
  return { fundsWithData: withData, totalFunds: total, asOfDates: dates };
}

export interface LookThroughCountry {
  code: string;
  name: string;
  weight: number;
  eur: number;
  breakdown: { holdingId: string; holdingShortName: string; contribution: number }[];
}

export function lookThroughCountries(): LookThroughCountry[] {
  const agg = new Map<string, LookThroughCountry>();
  for (const h of holdingsData.holdings) {
    if (!h.countryWeights) continue;
    for (const c of h.countryWeights) {
      const contribution = h.weight * c.weight;
      const existing = agg.get(c.code);
      if (existing) {
        existing.weight += contribution;
        existing.eur += contribution * holdingsData.totalEur;
        existing.breakdown.push({ holdingId: h.id, holdingShortName: h.shortName, contribution });
      } else {
        agg.set(c.code, {
          code: c.code,
          name: c.name,
          weight: contribution,
          eur: contribution * holdingsData.totalEur,
          breakdown: [{ holdingId: h.id, holdingShortName: h.shortName, contribution }],
        });
      }
    }
  }
  return Array.from(agg.values()).sort((a, b) => b.weight - a.weight);
}

export function countryWeightsCoverage(): { fundsWithData: number; totalFunds: number; asOfDates: string[] } {
  const total = holdingsData.holdings.length;
  const withData = holdingsData.holdings.filter((h) => h.countryWeights && h.countryWeights.length > 0).length;
  const dates = Array.from(
    new Set(
      holdingsData.holdings
        .map((h) => h.countryWeightsAsOf)
        .filter((d): d is string => Boolean(d))
    )
  );
  return { fundsWithData: withData, totalFunds: total, asOfDates: dates };
}
