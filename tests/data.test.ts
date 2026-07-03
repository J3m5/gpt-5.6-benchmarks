import { describe, expect, it } from "vitest";

import benchmarkData from "../data/benchmarks.json";
import {
  apiOutputPriceFor,
  apiPricingRows,
  exploitGymPoints,
  geneBenchProScalingPoints,
  geneScatterPoints,
  groups,
  terminalData,
  visibleGeneBenchPoints,
} from "../src/data";

describe("benchmark UI projections", () => {
  it("preserves the committed benchmark counts", () => {
    expect(geneScatterPoints).toHaveLength(22);
    expect(exploitGymPoints.filter((point) => point.duration === "2h")).toHaveLength(17);
    expect(exploitGymPoints.filter((point) => point.duration === "6h")).toHaveLength(15);
    expect(terminalData).toHaveLength(9);
    expect(benchmarkData.geneBenchProScaling).toHaveLength(33);
    expect(benchmarkData.geneBenchProMaxReasoning).toHaveLength(18);
    expect(geneBenchProScalingPoints).toHaveLength(33);
    expect(geneBenchProScalingPoints.every((point) => point.tokens > 0)).toBe(true);
    expect(geneBenchProScalingPoints.every((point) => (point.cost ?? 0) > 0)).toBe(true);
  });

  it("projects snapshotted output-token pricing into GeneBench-Pro costs", () => {
    const scalingModels = new Set(benchmarkData.geneBenchProScaling.map((row) => row.model));
    expect(
      benchmarkData.apiPricing.models
        .filter((row) => scalingModels.has(row.model))
        .map((row) => [row.model, row.outputUsdPerMillionTokens]),
    ).toEqual([
      ["GPT-5.6 Sol", 30],
      ["GPT-5.6 Terra", 15],
      ["GPT-5.6 Luna", 6],
      ["GPT-5.5", 30],
      ["GPT-5.4", 15],
      ["GPT-5.2", 14],
    ]);
    expect(apiOutputPriceFor("GPT-5.6 Sol")).toBe(30);
    expect(
      geneBenchProScalingPoints.find((point) => point.id === "GPT-5.6 Sol|max")?.cost,
    ).toBeCloseTo(0.9950489224806199, 12);
  });

  it("covers every chart model with complete standard API pricing", () => {
    const chartModels = new Set([
      ...benchmarkData.geneBench.map((row) => row.model),
      ...benchmarkData.exploitGym.map((row) => row.model),
      ...benchmarkData.terminalBench.map((row) => row.model),
      ...benchmarkData.geneBenchProScaling.map((row) => row.model),
    ]);

    expect(new Set(apiPricingRows.map((row) => row.model))).toEqual(chartModels);
    expect(
      apiPricingRows.every(
        (row) =>
          row.inputUsdPerMillionTokens > 0 &&
          row.cachedInputUsdPerMillionTokens > 0 &&
          row.outputUsdPerMillionTokens > 0,
      ),
    ).toBe(true);
    expect(apiPricingRows.find((row) => row.model === "GPT-5.6 Sol Ultra")?.pricingModel).toBe(
      "GPT-5.6 Sol",
    );
    expect(
      apiPricingRows.find((row) => row.model === "Claude Mythos 5")?.cacheWriteUsdPerMillionTokens,
    ).toBe(12.5);
    expect(
      apiPricingRows.find((row) => row.model === "Gemini 3.1 Pro Preview")?.longContextPricing,
    ).toEqual({
      thresholdTokens: 200_000,
      inputUsdPerMillionTokens: 4,
      cachedInputUsdPerMillionTokens: 0.4,
      outputUsdPerMillionTokens: 18,
    });
  });

  it("uses one ExploitGym selection identity per model and effort", () => {
    expect(new Set(exploitGymPoints.map((point) => point.selectionId)).size).toBe(17);
  });

  it("projects only selected GeneBench model families", () => {
    const selectedModel = groups[0]?.model;
    expect(selectedModel).toBeDefined();

    const points = visibleGeneBenchPoints(new Set(selectedModel ? [selectedModel] : []));

    expect(points.length).toBeGreaterThan(0);
    expect(points.every((point) => point.group.model === selectedModel)).toBe(true);
  });
});
