import accumulationData from "@/data/monte-carlo-accumulation.json";
import retirementData from "@/data/monte-carlo-retirement.json";
import type { QuantileSummary, FanChart, Histogram, SamplePath } from "@/lib/monteCarlo";

export interface DcaScenario {
  label: string;
  weights: Record<string, number>;
  terminal: QuantileSummary;
  annReturn: QuantileSummary;
  maxDrawdown: QuantileSummary;
  annVol: QuantileSummary;
  timeUnderwaterDays: QuantileSummary;
  probabilities: Record<string, number>;
  goalProbabilities: Record<string, number>;
  totalContributed?: number;
  totalContributedQ?: QuantileSummary;
  fanChart?: FanChart;
  samplePaths?: SamplePath[];
  terminalHistogram?: Histogram;
  maxDdHistogram?: Histogram;
}

export interface AccumulationOutput {
  schemaVersion: number;
  generatedAt: string;
  seed: number;
  inputs: {
    weightsHash: string;
    weights: Record<string, number>;
    startingEur: number;
    horizonYears: number;
    pathsBootstrap: number;
    pathsLongHistory: number;
    pathsRegime: number;
    pathsInflation: number;
    terAnnualByAsset: Record<string, number>;
  };
  dcaSweep: Record<string, DcaScenario>;
  salaryGrowth: DcaScenario;
  brokerFees: Record<string, {
    label: string;
    feeEurPerContribution: number;
    totalContributedNet: number;
    medianTerminal: number;
  }>;
  esgScreen: DcaScenario;
  jumpDiffusion: DcaScenario;
  hedged: DcaScenario;
  drawdownBuy: DcaScenario;
  longHistory: {
    scenarios: Record<string, DcaScenario>;
    meta: { windowStart: string; windowEnd: string; windowYears: number; blockLength: number };
  };
  regimeSwitching: {
    result: DcaScenario;
    diagnostics: {
      transitionMatrix: number[][];
      startProb: number[];
      bearMeanDaily: number;
      bullMeanDaily: number;
      bearVolDaily: number;
      bullVolDaily: number;
      stationaryDist: number[];
      bearFraction: number;
    };
  };
  stochasticInflation: {
    result: DcaScenario;
    diagnostics: {
      median15yAnnInflation: number;
      mean15yAnnInflation: number;
      p5: number;
      p95: number;
      p99: number;
    };
  };
}

export interface WithdrawalStrategy {
  label: string;
  fanChart: FanChart;
  samplePaths: SamplePath[];
  terminalPretax: QuantileSummary;
  terminalPosttax: QuantileSummary;
  year15Wealth: QuantileSummary;
  pDepletedYear30: number;
  medianYearsToDepletion: number | null;
  totalTaxPaid: number;
  withdrawalStartDay: number;
}

export interface RetirementOutput {
  schemaVersion: number;
  generatedAt: string;
  seed: number;
  inputs: {
    weightsHash: string;
    horizonYears: number;
    withdrawalStartYear: number;
    accumulationMonthly: number;
    accumulationGrowth: number;
    inflationRate: number;
    pathsRetirement: number;
    engine: string;
  };
  windowMeta: { windowStart: string; windowEnd: string; windowYears: number; blockLength: number };
  strategies: Record<string, WithdrawalStrategy>;
}

export const accumulationMC = accumulationData as unknown as AccumulationOutput;
export const retirementMC = retirementData as unknown as RetirementOutput;
