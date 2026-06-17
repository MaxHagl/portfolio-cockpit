import mcData from "@/data/monte-carlo.json";
import { holdingsData } from "@/lib/data";

export interface QuantileSummary {
  mean: number;
  median: number;
  std: number;
  p5: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  expectedShortfall5: number;
  expectedShortfall1: number;
}

export interface FanChart {
  ts: number[];
  p5: number[];
  p10: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p90: number[];
  p95: number[];
}

export interface SamplePath {
  quantile: number;
  weekly: number[];
}

export interface Histogram {
  binEdges: number[];
  counts: number[];
}

export interface ScenarioResult {
  label: string;
  weights: Record<string, number>;
  terminal: QuantileSummary;
  annReturn: QuantileSummary;
  maxDrawdown: QuantileSummary;
  annVol: QuantileSummary;
  timeUnderwaterDays: QuantileSummary;
  probabilities: Record<string, number>;
  goalProbabilities: Record<string, number>;
  fanChart?: FanChart;
  samplePaths?: SamplePath[];
  terminalHistogram?: Histogram;
  annReturnHistogram?: Histogram;
  maxDdHistogram?: Histogram;
}

export interface EngineResult {
  scenarios: Record<string, ScenarioResult>;
  method: string;
  nu?: number;
  garch?: Array<Record<string, number | string>>;
}

export interface StressEpisode {
  description: string;
  available: boolean;
  windowStart?: string;
  windowEnd?: string;
  peakDrawdown?: number;
  daysToTrough?: number;
  daysToRecover?: number | null;
  terminalEur?: number;
  peakEur?: number;
  troughEur?: number;
  note?: string;
}

export interface MonteCarloOutput {
  schemaVersion: number;
  generatedAt: string;
  seed: number;
  computeSeconds: number;
  inputs: {
    weightsHash: string;
    weights: Record<string, number>;
    startingEur: number;
    horizonYears: number;
    tradingDaysPerYear: number;
    pathsBootstrap: number;
    pathsParametricT: number;
    pathsFhs: number;
    pathsCv: number;
    blockLengthBootstrap: number;
    terAnnualByAsset: Record<string, number>;
    weightedTerAnnual: number;
    rebalancingCanonical: string;
    inflationRate: number;
    usdExposure: number;
  };
  history: {
    augmentedWindow: { start: string; end: string; days: number; years: number };
    nativeWindow: { start: string; end: string; days: number; years: number };
    augmentation: Record<string, {
      proxyId: string;
      eurConvert: boolean;
      lag: number;
      alphaAnnualized: number;
      beta: number;
      residSigmaAnnualized: number;
      r2: number;
      nOverlap: number;
      overlapStart: string;
      overlapEnd: string;
    }>;
  };
  engines: {
    bootstrap: EngineResult;
    parametricT: EngineResult;
    fhs: EngineResult;
    crossValidation: { windowStudies: Array<{ window_start: string; window_end: string; window_days: number; blockLength: number; medianTerminalMultiple: number; p5TerminalMultiple: number; p95TerminalMultiple: number; medianMaxDrawdown: number }> };
  };
  rebalancingSensitivity: { baseline: Record<string, ScenarioResult> };
  taxModeling: { baselinePosttax: ScenarioResult };
  realReturns: { baseline2pct: ScenarioResult };
  currencyOverlay: { baseline: ScenarioResult; fxVolContribution: number };
  stress: Record<string, StressEpisode>;
  diagnostics: {
    perAssetStats: Record<string, any>;
    correlationAugmented: Record<string, Record<string, number>>;
    correlationNative: Record<string, Record<string, number>>;
  };
}

export const mc = mcData as unknown as MonteCarloOutput;

export function isStale(): boolean {
  // Compare current holdings.baseline.weights to mc.inputs.weights
  const current = holdingsData.baseline.weights;
  const stored = mc.inputs.weights;
  const keys = new Set([...Object.keys(current), ...Object.keys(stored)]);
  for (const k of keys) {
    const a = current[k] || 0;
    const b = stored[k] || 0;
    if (Math.abs(a - b) > 0.001) return true;
  }
  // Also stale if >30 days old
  const generated = new Date(mc.generatedAt).getTime();
  const ageDays = (Date.now() - generated) / (1000 * 60 * 60 * 24);
  return ageDays > 30;
}

export function fmtEur(n: number): string {
  return n.toLocaleString("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export function fmtPct(n: number, decimals: number = 1): string {
  return `${(n * 100).toFixed(decimals)}%`;
}

export function fmtMultiplier(n: number): string {
  return `${n.toFixed(2)}x`;
}
