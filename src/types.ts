export type MetricKey = "score" | "tokens" | "latency" | "cost";
export type ResourceKey = Exclude<MetricKey, "score">;

export interface BenchmarkValue {
  effort: string;
  score: number;
  tokens: number;
  latency: number;
  cost: number;
}

export interface BenchmarkGroup {
  model: string;
  color: string;
  values: BenchmarkValue[];
}

export interface VisiblePoint extends BenchmarkValue {
  group: BenchmarkGroup;
}

export interface ScatterPoint {
  id: string;
  selectionId?: string;
  family: string;
  duration?: string;
  effort: string;
  cost?: number;
  latency?: number;
  tokens: number;
  reasoningBudget?: number;
  validCompletedSamples?: number;
  score: number;
  color: string;
  selectionGroup: string;
  selectionLabel: string;
  label: string;
  shape: "circle" | "square";
}

export interface TerminalItem {
  model: string;
  reasoning: string;
  score: number;
  sourceLabel: string;
  color: string;
}

export interface ExploitBenchSeriesPoint {
  model: string;
  effort: string;
  outputTokens: number;
  score: number;
  sourceLabel: string;
  color: string;
}

export interface ExploitBenchComparisonPoint {
  model: string;
  outputTokens: number;
  score: number;
  shape: "diamond" | "square";
  color: string;
}

export interface ExploitBenchReferenceLine {
  model: string;
  detail: string;
  xStart: number;
  xEnd: number;
  score: number;
  color: string;
}

export interface ApiPricingTier {
  thresholdTokens: number;
  inputUsdPerMillionTokens: number;
  cachedInputUsdPerMillionTokens: number;
  outputUsdPerMillionTokens: number;
}

export interface ApiPricingRow {
  model: string;
  provider: string;
  inputUsdPerMillionTokens: number;
  cachedInputUsdPerMillionTokens: number;
  cacheWriteUsdPerMillionTokens: number | null;
  cacheWriteTtlMinutes: number | null;
  outputUsdPerMillionTokens: number;
  longContextPricing: ApiPricingTier | null;
  pricingModel: string | null;
}

export interface PointOffset {
  dx?: number;
  dy?: number;
}

export type MetricLabelOffsets = Partial<Record<ResourceKey, Record<string, PointOffset>>>;

export interface PointerCoordinates {
  clientX: number;
  clientY: number;
}
