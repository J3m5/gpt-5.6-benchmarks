import { describe, expect, it } from "vitest";

import { prepareGeneBenchBar, prepareGeneBenchScatter } from "../src/charts/gene-bench-plot-model";
import { groupLabelOffsets } from "../src/charts/plot/label-groups";
import { geneScatterPoints } from "../src/data";
import type { MetricKey, ResourceKey } from "../src/types";

const allIds = new Set(geneScatterPoints.map((point) => point.id));
const resourceMetrics: ResourceKey[] = ["cost", "latency", "tokens"];
const barMetrics: MetricKey[] = ["score", "cost", "latency", "tokens"];

describe("GeneBench Plot scatter preparation", () => {
  it.each(resourceMetrics)(
    "prepares linear and log scales for %s with Plot-managed tick density",
    (metricKey) => {
      for (const scale of ["linear", "log"] as const) {
        const model = prepareGeneBenchScatter(geneScatterPoints, {
          selectedIds: allIds,
          metricKey,
          scale,
          pareto: false,
          showLabels: true,
          showFamilyLines: true,
          width: 700,
        });

        expect(model.width).toBe(900);
        expect(model.height).toBe(560);
        expect(model.points).toHaveLength(22);
        expect(model.xAxis.scale).toBe(scale);
        expect(scale === "log" ? Array.isArray(model.xAxis.ticks) : model.xAxis.ticks === 6).toBe(
          true,
        );
        expect(model.yAxis.ticks).toBeUndefined();
        expect(model.yAxis.interval).toBe(5);
        expect(model.quadrantY).toBe((model.yAxis.domain[0] + model.yAxis.domain[1]) / 2);
        expect(model.familySeries).toHaveLength(4);
      }
    },
  );

  it("uses fallbacks for an empty selection", () => {
    const model = prepareGeneBenchScatter(geneScatterPoints, {
      selectedIds: new Set(),
      metricKey: "cost",
      scale: "linear",
      pareto: false,
      showLabels: true,
      showFamilyLines: true,
      width: 900,
    });

    expect(model.points).toEqual([]);
    expect(model.xAxis.domain).toEqual([0, 2.5]);
    expect(model.xAxis.ticks).toEqual([0, 0.5, 1, 1.5, 2, 2.5]);
    expect(model.yAxis.domain).toEqual([0, 35]);
    expect(model.yAxis.interval).toBeUndefined();
    expect(model.familySeries).toEqual([]);
  });

  it("builds the Pareto frontier and bridges selected intermediate efforts", () => {
    const model = prepareGeneBenchScatter(geneScatterPoints, {
      selectedIds: allIds,
      metricKey: "cost",
      scale: "log",
      pareto: true,
      showLabels: true,
      showFamilyLines: true,
      width: 900,
    });
    const terraRuns = model.familySeries
      .filter((series) => series.family === "GPT-5.6 Terra")
      .map((series) => series.points.map((point) => point.id));

    expect(model.points.length).toBeLessThan(22);
    expect(
      terraRuns.some((ids) =>
        ids.some(
          (id, index) => id === "GPT-5.6 Terra|low" && ids[index + 1] === "GPT-5.6 Terra|max",
        ),
      ),
    ).toBe(true);
  });
});

describe("GeneBench Plot bar preparation", () => {
  it.each(barMetrics)("sorts %s ascending and lets Plot infer the value axis", (metricKey) => {
    const model = prepareGeneBenchBar({
      selectedIds: allIds,
      metricKey,
      containerWidth: 800,
    });
    const values = model.items.map((item) => item.value);

    expect(model.height).toBe(650);
    expect(model.items).toHaveLength(22);
    expect(values).toEqual(values.toSorted((first, second) => first - second));
    expect(model.valueAxis.domain).toBeUndefined();
    expect(model.valueAxis.ticks).toBeUndefined();
  });
});

describe("Plot label offsets", () => {
  it("groups pixel offsets without converting them to data units", () => {
    const groups = groupLabelOffsets([
      { id: "a", labelDx: 10, labelDy: 4 },
      { id: "b", labelDx: 10, labelDy: -10 },
      { id: "c", labelDx: 10, labelDy: 4 },
    ]);

    expect(groups).toEqual([
      {
        dx: 10,
        dy: 4,
        points: [
          { id: "a", labelDx: 10, labelDy: 4 },
          { id: "c", labelDx: 10, labelDy: 4 },
        ],
      },
      {
        dx: 10,
        dy: -10,
        points: [{ id: "b", labelDx: 10, labelDy: -10 }],
      },
    ]);
  });
});
