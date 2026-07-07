import { describe, expect, it } from "vitest";

import {
  prepareGeneBenchProBar,
  prepareGeneBenchProScatter,
  type GeneBenchProBarMetric,
} from "../src/charts/gene-bench-pro-plot-model";
import { geneBenchProScalingPoints } from "../src/data";

function prepare(overrides: Partial<Parameters<typeof prepareGeneBenchProScatter>[0]> = {}) {
  return prepareGeneBenchProScatter({
    selectedPoints: geneBenchProScalingPoints,
    metricKey: "tokens",
    scale: "log",
    pareto: false,
    showLabels: true,
    showFamilyLines: true,
    width: 700,
    ...overrides,
  });
}

describe("GeneBench-Pro Plot scatter preparation", () => {
  it("prepares all scaling points and family lines on the default token scale", () => {
    const model = prepare();

    expect(model.width).toBe(900);
    expect(model.height).toBe(560);
    expect(model.margins.right).toBe(128);
    expect(model.points).toHaveLength(33);
    expect(model.familySeries).toHaveLength(6);
    expect(model.xAxis.scale).toBe("log");
    expect(model.xAxis.label).toBe("Tokens used (logarithmic scale)");
    expect(model.points[0]?.tip).toContain("Output-token price:");
  });

  it("prepares estimated cost on a linear scale", () => {
    const model = prepare({ metricKey: "cost", scale: "linear" });

    expect(model.points).toHaveLength(33);
    expect(model.xAxis.scale).toBe("linear");
    expect(model.xAxis.label).toBe("Estimated API cost (USD, linear scale)");
    expect(model.points.every((point) => point.x === point.datum.cost)).toBe(true);
    expect(model.points[0]?.ariaLabel).toContain("estimated api cost");
  });

  it("uses metric-specific fallbacks for an empty selection", () => {
    const tokens = prepare({ selectedPoints: [], scale: "linear" });
    const cost = prepare({ selectedPoints: [], metricKey: "cost" });

    expect(tokens.xAxis.domain).toEqual([0, 120000]);
    expect(tokens.xAxis.ticks).toEqual([0, 20000, 40000, 60000, 80000, 100000, 120000]);
    expect(cost.xAxis.domain).toEqual([0.005, 2]);
    expect(cost.xAxis.ticks).toEqual([0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2]);
    expect(tokens.yAxis.domain).toEqual([0, 30]);
  });

  it("applies the two-percent Pareto tolerance", () => {
    const model = prepare({ pareto: true });
    const ids = new Set(model.points.map((point) => point.id));

    expect(model.points).toHaveLength(7);
    expect(ids.has("GPT-5.6 Terra|low")).toBe(false);
    expect(ids.has("GPT-5.6 Sol|low")).toBe(true);
  });
});

describe("GeneBench-Pro Plot bar preparation", () => {
  const allIds = new Set(geneBenchProScalingPoints.map((point) => point.id));

  it.each(["score", "tokens", "cost"] as GeneBenchProBarMetric[])(
    "sorts %s ascending and lets Plot infer the value axis",
    (metricKey) => {
      const model = prepareGeneBenchProBar({
        selectedIds: allIds,
        metricKey,
        containerWidth: 900,
      });
      const values = model.items.map((item) => item.value);

      expect(model.items).toHaveLength(33);
      expect(values).toEqual(values.toSorted((first, second) => first - second));
      expect(model.valueAxis.domain).toBeUndefined();
      expect(model.valueAxis.ticks).toBeUndefined();
    },
  );

  it("uses the shared configuration selection", () => {
    const selectedIds = new Set(
      geneBenchProScalingPoints
        .filter((point) => point.family !== "GPT-5.6 Sol")
        .map((point) => point.id),
    );
    const model = prepareGeneBenchProBar({
      selectedIds,
      metricKey: "score",
      containerWidth: 900,
    });

    expect(model.items).toHaveLength(27);
    expect(model.items.every((item) => item.family !== "GPT-5.6 Sol")).toBe(true);
  });
});
