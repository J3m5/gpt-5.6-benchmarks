import { apiOutputPriceFor, geneBenchProScalingPoints } from "../data";
import type { ResourceKey, ScatterPoint } from "../types";
import {
  formatAxisCost,
  formatAxisNumber,
  formatEstimatedCost,
  formatPercent,
  integerFormatter,
} from "../utils/format";
import type { PlotBarModel, PlotScaleKind, PlotScatterModel } from "./plot/types";
import {
  prepareResourceScoreScatter,
  type ResourceScatterMetric,
} from "./resource-score-plot-model";

const metrics: Partial<Record<ResourceKey, ResourceScatterMetric>> = {
  cost: {
    key: "cost",
    label: "Estimated API cost",
    axisLabels: {
      linear: "Estimated API cost (USD, linear scale)",
      log: "Estimated API cost (USD, logarithmic scale)",
    },
    paretoComparative: "a lower estimated API cost",
    formatAxis: formatAxisCost,
    formatValue: formatEstimatedCost,
    fallbacks: {
      linear: {
        min: 0,
        max: 1.2,
        ticks: [0, 0.2, 0.4, 0.6, 0.8, 1, 1.2],
      },
      log: {
        min: 0.005,
        max: 2,
        ticks: [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2],
      },
    },
  },
  tokens: {
    key: "tokens",
    label: "Tokens used",
    axisLabels: {
      linear: "Tokens used (linear scale)",
      log: "Tokens used (logarithmic scale)",
    },
    paretoComparative: "fewer tokens used",
    formatAxis: formatAxisNumber,
    formatValue: (value) => integerFormatter.format(value),
    fallbacks: {
      linear: {
        min: 0,
        max: 120000,
        ticks: [0, 20000, 40000, 60000, 80000, 100000, 120000],
      },
      log: {
        min: 500,
        max: 200000,
        ticks: [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000],
      },
    },
  },
};

export type GeneBenchProBarMetric = "score" | "tokens" | "cost";

interface BarMetric {
  key: GeneBenchProBarMetric;
  axis: string;
  formatTick: (value: number) => string;
  formatValue: (value: number) => string;
}

const barMetrics: Record<GeneBenchProBarMetric, BarMetric> = {
  score: {
    key: "score",
    axis: "Passrate",
    formatTick: (value) => `${value}%`,
    formatValue: formatPercent,
  },
  tokens: {
    key: "tokens",
    axis: "Tokens used",
    formatTick: formatAxisNumber,
    formatValue: (value) => integerFormatter.format(value),
  },
  cost: {
    key: "cost",
    axis: "Estimated API cost (USD)",
    formatTick: formatAxisCost,
    formatValue: formatEstimatedCost,
  },
};

function tip(point: ScatterPoint): string {
  return `${point.family}\nReasoning: ${point.effort}\nTokens used: ${integerFormatter.format(point.tokens)}\nOutput-token price: $${apiOutputPriceFor(point.family).toFixed(2)} / 1M\nEstimated API cost: ${formatEstimatedCost(point.cost ?? 0)}\nPassrate: ${formatPercent(point.score)}`;
}

export interface PrepareGeneBenchProScatterOptions {
  selectedPoints: readonly ScatterPoint[];
  metricKey: ResourceKey;
  scale: PlotScaleKind;
  pareto: boolean;
  showLabels: boolean;
  showFamilyLines: boolean;
  width: number;
}

export function prepareGeneBenchProScatter(
  options: PrepareGeneBenchProScatterOptions,
): PlotScatterModel<ScatterPoint> {
  return prepareResourceScoreScatter(
    {
      id: "genebench-pro-scaling",
      titleId: "genebench-pro-scaling-svg-title",
      descriptionId: "genebench-pro-scaling-description",
      benchmarkName: "GeneBench-Pro",
      scoreDisplayName: "passrate",
      scoreMetricLabel: "passrate",
      yAxisLabel: "Passrate",
      yMax: 30,
      yStep: 5,
      metrics,
      margins: { top: 38, right: 128, bottom: 68, left: 70 },
      paretoResourceTolerance: 0.02,
      getTip: tip,
    },
    options,
  );
}

export interface PrepareGeneBenchProBarOptions {
  selectedIds: ReadonlySet<string>;
  metricKey: GeneBenchProBarMetric;
  containerWidth: number;
}

export function prepareGeneBenchProBar({
  selectedIds,
  metricKey,
  containerWidth,
}: PrepareGeneBenchProBarOptions): PlotBarModel<ScatterPoint> {
  const metric = barMetrics[metricKey];
  const points = geneBenchProScalingPoints
    .filter((point) => selectedIds.has(point.id))
    .toSorted(
      (first, second) =>
        Number(first[metric.key]) - Number(second[metric.key]) ||
        first.family.localeCompare(second.family) ||
        first.effort.localeCompare(second.effort),
    );
  const baseMargins = { top: 54, right: 28, bottom: 158, left: 68 };
  const itemWidth = 55;
  const contentWidth = baseMargins.left + points.length * itemWidth + baseMargins.right;
  const width = Math.max(containerWidth, contentWidth);
  const extraWidth = width - contentWidth;

  return {
    id: "genebench-pro-bars",
    metric: metric.key,
    width,
    height: 650,
    margins: {
      ...baseMargins,
      left: baseMargins.left + extraWidth / 2,
      right: baseMargins.right + extraWidth / 2,
    },
    titleId: "genebench-pro-bars-title",
    descriptionId: "genebench-pro-bars-description",
    title: `GeneBench-Pro ${metric.axis.toLowerCase()} by model and reasoning`,
    description: `Vertical bar chart sorted by ${metric.axis.toLowerCase()} in ascending order.`,
    valueAxis: {
      scale: "linear",
      label: metric.axis,
      formatTick: metric.formatTick,
    },
    items: points.map((point) => {
      const value = Number(point[metric.key]);
      return {
        datum: point,
        id: point.id,
        family: point.family,
        metric: metric.key,
        effort: point.effort,
        value,
        color: point.color,
        categoryLabel: point.label,
        valueLabel: metric.formatValue(value),
        ariaLabel: `${point.family}, reasoning ${point.effort}, ${metric.axis.toLowerCase()} ${metric.formatValue(value)}`,
        tip: `${point.family}\nReasoning: ${point.effort}\n${metric.axis}: ${metric.formatValue(value)}`,
      };
    }),
  };
}

export function geneBenchProAxisLabel(metricKey: ResourceKey, scale: PlotScaleKind): string {
  const metric = metrics[metricKey];
  if (!metric) {
    throw new RangeError(`GeneBench-Pro does not support the ${metricKey} resource metric`);
  }
  return metric.axisLabels[scale];
}
