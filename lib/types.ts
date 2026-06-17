export type Sleeve = "core" | "tech" | "em";

export interface FundTopHolding {
  ticker: string;
  name: string;
  weight: number;
}

export interface FundCountryWeight {
  code: string;
  name: string;
  weight: number;
}

export interface FundIndustryWeight {
  industry: string;
  sector: string;
  weight: number;
}

export interface Holding {
  id: string;
  name: string;
  shortName: string;
  wkn: string;
  isin: string;
  yahoo: string;
  ter: number;
  sleeve: Sleeve;
  type: string;
  eur: number;
  weight: number;
  thesis: string;
  risk: string[];
  upside: string[];
  links: Record<string, string>;
  topHoldings?: FundTopHolding[];
  topHoldingsAsOf?: string;
  countryWeights?: FundCountryWeight[];
  countryWeightsAsOf?: string;
  industryWeights?: FundIndustryWeight[];
  industryWeightsAsOf?: string;
}

export interface Peer {
  id: string;
  name: string;
  wkn: string;
  isin: string;
  yahoo: string;
  ter: number;
  type: string;
  thesis: string;
  vsCurrent: { feeDelta: number; overlap: number };
  whyPick: string[];
  whyNot: string[];
}

export interface SleeveMeta { label: string; color: string }

export interface HoldingsFile {
  totalEur: number;
  baseline: { label: string; weights: Record<string, number> };
  holdings: Holding[];
  sleeves: Record<Sleeve, SleeveMeta>;
}

export type PeersFile = Record<string, Peer[]>;

export interface PricePoint { t: number; c: number }
export interface PriceSeries { symbol: string; source: "yahoo" | "boerse-frankfurt" | "cache" | "unavailable"; points: PricePoint[]; note?: string }
