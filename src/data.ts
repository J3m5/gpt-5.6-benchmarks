import benchmarkData from "../data/benchmarks.json";

import { estimateOutputTokenCost } from "./api-cost";
import { compareReasoningEfforts } from "./chart-series";
import type {
  ApiPricingRow,
  BenchmarkGroup,
  ScatterPoint,
  TerminalItem,
  VisiblePoint,
} from "./types";

const familyColors: Record<string, string> = {
  "GPT-5.6 Sol": "#292b2f",
  "GPT-5.6 Terra": "#3478d4",
  "GPT-5.6 Luna": "#188b62",
  "GPT-5.5": "#d85f8c",
  "GPT-5.4": "#7d5db3",
  "GPT-5.2": "#b36b2e",
};

const terminalColors: Record<string, string> = {
  "GPT-5.6 Sol Ultra": "#17181a",
  "GPT-5.6 Sol": "#4b4e54",
  "Claude Mythos 5": "#a6532d",
  "Claude Fable 5": "#cf7747",
  "GPT-5.6 Terra": "#3478d4",
  "GPT-5.5": "#d85f8c",
  "GPT-5.6 Luna": "#188b62",
  "Claude Opus 4.8": "#e3a078",
  "Gemini 3.1 Pro Preview": "#7256c8",
};

export const groups: BenchmarkGroup[] = [
  ...benchmarkData.geneBench
    .reduce((byModel, row) => {
      if (!byModel.has(row.model)) {
        byModel.set(row.model, {
          model: row.model,
          color: familyColors[row.model] ?? "#656970",
          values: [],
        });
      }
      byModel.get(row.model)?.values.push({
        effort: row.effort,
        score: row.scorePercent,
        tokens: row.outputTokens,
        latency: row.latencyMinutes,
        cost: row.apiCostUsd,
      });
      return byModel;
    }, new Map<string, BenchmarkGroup>())
    .values(),
];

const shortFamilyNames: Record<string, string> = {
  "GPT-5.6 Sol": "Sol",
  "GPT-5.6 Terra": "Terra",
  "GPT-5.6 Luna": "Luna",
  "GPT-5.5": "GPT-5.5",
  "GPT-5.4": "GPT-5.4",
};

export const geneScatterPoints: ScatterPoint[] = groups.flatMap((group) =>
  group.values.map((value) => ({
    id: `${group.model}|${value.effort}`,
    family: group.model,
    effort: value.effort,
    cost: value.cost,
    latency: value.latency,
    tokens: value.tokens,
    score: value.score,
    color: group.color,
    selectionGroup: group.model,
    selectionLabel: `${group.model} / ${value.effort}`,
    label: `${shortFamilyNames[group.model]} / ${value.effort}`,
    shape: "circle" as const,
  })),
);

const familyOrder = ["GPT-5.6 Sol", "GPT-5.6 Terra", "GPT-5.6 Luna", "GPT-5.5", "GPT-5.4"];

export const exploitGymPoints: ScatterPoint[] = benchmarkData.exploitGym
  .map((row) => ({
    id: `${row.model}|${row.duration}|${row.effort}`,
    selectionId: `${row.model}|${row.effort}`,
    family: row.model,
    duration: row.duration,
    effort: row.effort,
    cost: row.apiCostUsd,
    latency: row.latencyMinutes,
    tokens: row.outputTokens,
    score: row.scorePercent,
    color: familyColors[row.model] ?? "#656970",
    selectionGroup: row.model,
    selectionLabel: `${row.model} / ${row.effort}`,
    label: `${shortFamilyNames[row.model]} / ${row.effort}`,
    shape: "circle" as const,
  }))
  .toSorted(
    (a, b) =>
      familyOrder.indexOf(a.family) - familyOrder.indexOf(b.family) ||
      a.duration.localeCompare(b.duration) ||
      compareReasoningEfforts(a.effort, b.effort),
  );

const geneBenchProFamilyOrder = [
  "GPT-5.2",
  "GPT-5.4",
  "GPT-5.5",
  "GPT-5.6 Luna",
  "GPT-5.6 Terra",
  "GPT-5.6 Sol",
];

const apiOutputPricing = new Map(
  benchmarkData.apiPricing.models.map((row) => [row.model, row.outputUsdPerMillionTokens]),
);

export const apiPricingRows: ApiPricingRow[] = benchmarkData.apiPricing.models;
export const apiPricingSources = benchmarkData.apiPricing.sources;

export function apiOutputPriceFor(model: string): number {
  const price = apiOutputPricing.get(model);
  if (price === undefined) {
    throw new RangeError(`Missing API output pricing for ${model}`);
  }
  return price;
}

export const geneBenchProScalingPoints: ScatterPoint[] = benchmarkData.geneBenchProScaling
  .map((row) => {
    const outputPrice = apiOutputPriceFor(row.model);
    return {
      id: `${row.model}|${row.reasoning}`,
      family: row.model,
      effort: row.reasoning,
      cost: estimateOutputTokenCost(
        row.meanNonmaskedSollen,
        outputPrice,
        benchmarkData.apiPricing.unitTokens,
      ),
      tokens: row.meanNonmaskedSollen,
      reasoningBudget: row.reasoningBudget,
      validCompletedSamples: row.validCompletedSamples,
      score: row.passratePercent,
      color: familyColors[row.model] ?? "#656970",
      selectionGroup: row.model,
      selectionLabel: `${row.model} / ${row.reasoning}`,
      label: `${shortFamilyNames[row.model] ?? row.model.replace("GPT-", "")} / ${row.reasoning}`,
      shape: "circle" as const,
    };
  })
  .toSorted(
    (a, b) =>
      geneBenchProFamilyOrder.indexOf(a.family) - geneBenchProFamilyOrder.indexOf(b.family) ||
      compareReasoningEfforts(a.effort, b.effort),
  );

export const terminalData: TerminalItem[] = benchmarkData.terminalBench.map((row) => ({
  model: row.model,
  reasoning: row.reasoning,
  score: row.scoreFraction * 100,
  sourceLabel: row.scoreLabel,
  color: terminalColors[row.model] ?? "#656970",
}));

export function visibleGeneBenchPoints(selectedModels: ReadonlySet<string>): VisiblePoint[] {
  return groups
    .filter((group) => selectedModels.has(group.model))
    .flatMap((group) => group.values.map((value) => ({ group, ...value })));
}
