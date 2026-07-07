import { selectedGeneBenchPoints } from "../data";
import type { BenchmarkGroup, MetricKey, ResourceKey, ScatterPoint, VisiblePoint } from "../types";
import {
  formatAxisCost,
  formatAxisNumber,
  formatCost,
  formatLatency,
  formatPercent,
  integerFormatter,
} from "../utils/format";
import type { PlotBarModel, PlotScaleKind, PlotScatterModel } from "./plot/types";
import {
  prepareResourceScoreScatter,
  resourceValue,
  type ResourceScatterMetric,
} from "./resource-score-plot-model";

interface BarMetric {
  key: MetricKey;
  axis: string;
  formatTick: (value: number) => string;
  formatValue: (value: number) => string;
}

export interface PrepareGeneBenchScatterOptions {
  selectedIds: ReadonlySet<string>;
  metricKey: ResourceKey;
  scale: PlotScaleKind;
  pareto: boolean;
  showLabels: boolean;
  showFamilyLines: boolean;
  width: number;
}

export interface PrepareGeneBenchBarOptions {
  selectedIds: ReadonlySet<string>;
  metricKey: MetricKey;
  containerWidth: number;
}

const scatterMetrics: Record<ResourceKey, ResourceScatterMetric> = {
  cost: {
    key: "cost",
    label: "API cost",
    paretoComparative: "a lower API cost",
    axisLabels: {
      linear: "API cost (USD, linear scale)",
      log: "API cost (USD, logarithmic scale)",
    },
    formatAxis: formatAxisCost,
    formatValue: formatCost,
    fallbacks: {
      linear: { min: 0, max: 2.5, ticks: [0, 0.5, 1, 1.5, 2, 2.5] },
      log: { min: 0.01, max: 2.5, ticks: [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2] },
    },
  },
  latency: {
    key: "latency",
    label: "Latency",
    paretoComparative: "lower latency",
    axisLabels: {
      linear: "Latency (minutes, linear scale)",
      log: "Latency (minutes, logarithmic scale)",
    },
    formatAxis: formatAxisNumber,
    formatValue: formatLatency,
    fallbacks: {
      linear: { min: 0, max: 20, ticks: [0, 5, 10, 15, 20] },
      log: { min: 0.3, max: 20, ticks: [0.5, 1, 2, 5, 10, 20] },
    },
  },
  tokens: {
    key: "tokens",
    label: "Output tokens",
    paretoComparative: "fewer output tokens",
    axisLabels: {
      linear: "Output tokens (linear scale)",
      log: "Output tokens (logarithmic scale)",
    },
    formatAxis: formatAxisNumber,
    formatValue: (value) => integerFormatter.format(value),
    fallbacks: {
      linear: {
        min: 0,
        max: 100000,
        ticks: [0, 20000, 40000, 60000, 80000, 100000],
      },
      log: {
        min: 500,
        max: 100000,
        ticks: [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000],
      },
    },
  },
};

const barMetrics: Record<MetricKey, BarMetric> = {
  score: {
    key: "score",
    axis: "Score",
    formatTick: (value) => `${value}%`,
    formatValue: (value) => `${Number.isInteger(value) ? value : String(value).replace(/0$/, "")}%`,
  },
  tokens: {
    key: "tokens",
    axis: "Output tokens",
    formatTick: (value) => (value === 0 ? "0" : `${value / 1000}k`),
    formatValue: (value) => integerFormatter.format(value),
  },
  latency: {
    key: "latency",
    axis: "Latency (minutes)",
    formatTick: (value) => `${value}`,
    formatValue: (value) => `${value.toFixed(2)} min`,
  },
  cost: {
    key: "cost",
    axis: "API cost (USD)",
    formatTick: (value) => `$${value.toFixed(1)}`,
    formatValue: (value) => `$${value.toFixed(2)}`,
  },
};

function scatterTip(point: ScatterPoint): string {
  return `${point.family}\nReasoning effort: ${point.effort}\nScore: ${formatPercent(point.score)}\nAPI cost: ${formatCost(resourceValue(point, "cost"))}\nLatency: ${formatLatency(resourceValue(point, "latency"))}\nOutput tokens: ${integerFormatter.format(resourceValue(point, "tokens"))}`;
}

export function prepareGeneBenchScatter(
  allPoints: readonly ScatterPoint[],
  options: PrepareGeneBenchScatterOptions,
): PlotScatterModel<ScatterPoint> {
  const selected = allPoints.filter((point) => options.selectedIds.has(point.id));
  return prepareResourceScoreScatter(
    {
      id: "gene-scatter",
      titleId: "gene-scatter-svg-title",
      descriptionId: "gene-scatter-description",
      benchmarkName: "GeneBench v1",
      scoreDisplayName: "score",
      scoreMetricLabel: "pass@1 score",
      yAxisLabel: "Score",
      yMax: 35,
      yStep: 5,
      metrics: scatterMetrics,
      getLabelOffset: (point) => ({
        dy: point.id === "GPT-5.6 Terra|none" ? -10 : 4,
      }),
      getTip: scatterTip,
    },
    {
      ...options,
      selectedPoints: selected,
    },
  );
}

function barTip(group: BenchmarkGroup, effort: string, value: number, metric: BarMetric): string {
  return `${group.model}\nReasoning effort: ${effort}\n${metric.axis}: ${metric.formatValue(value)}`;
}

export function prepareGeneBenchBar(
  options: PrepareGeneBenchBarOptions,
): PlotBarModel<VisiblePoint> {
  const metric = barMetrics[options.metricKey];
  const points = selectedGeneBenchPoints(options.selectedIds).toSorted(
    (first, second) =>
      first[metric.key] - second[metric.key] ||
      first.group.model.localeCompare(second.group.model) ||
      first.effort.localeCompare(second.effort),
  );
  const baseMargins = { top: 54, right: 28, bottom: 158, left: 68 };
  const itemWidth = 55;
  const contentWidth = baseMargins.left + points.length * itemWidth + baseMargins.right;
  const width = Math.max(options.containerWidth, contentWidth);
  const extraWidth = width - contentWidth;

  return {
    id: "chart",
    metric: metric.key,
    width,
    height: 650,
    margins: {
      ...baseMargins,
      left: baseMargins.left + extraWidth / 2,
      right: baseMargins.right + extraWidth / 2,
    },
    titleId: "chart-title",
    descriptionId: "chart-description",
    title: `GeneBench v1 ${metric.axis.toLowerCase()} by model and reasoning effort`,
    description: `Bar chart sorted by ${metric.axis.toLowerCase()} in ascending order. Each horizontal-axis category represents one model and reasoning effort level.`,
    valueAxis: {
      scale: "linear",
      label: metric.axis,
      formatTick: metric.formatTick,
    },
    items: points.map((point) => {
      const value = point[metric.key];
      const id = `${point.group.model}|${point.effort}`;
      return {
        datum: point,
        id,
        family: point.group.model,
        metric: metric.key,
        effort: point.effort,
        value,
        color: point.group.color,
        categoryLabel: `${point.group.model} / ${point.effort}`,
        valueLabel: metric.formatValue(value),
        ariaLabel: `${point.group.model}, effort ${point.effort}, ${metric.axis} ${metric.formatValue(value)}`,
        tip: barTip(point.group, point.effort, value, metric),
      };
    }),
  };
}

export function geneBenchScatterAxisLabel(metricKey: ResourceKey, scale: PlotScaleKind): string {
  return scatterMetrics[metricKey].axisLabels[scale];
}
