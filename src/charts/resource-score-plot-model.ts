import {
  createLinearScale,
  createLinearValueScale,
  createLogScale,
  paretoFrontier,
} from "../chart-math";
import { buildFamilyLineRuns } from "../chart-series";
import type { PointOffset, ResourceKey, ScatterPoint } from "../types";
import { formatAxisPercent, formatPercent } from "../utils/format";
import type {
  PlotAxisModel,
  PlotMargins,
  PlotScaleKind,
  PlotScatterModel,
  PlotScatterPoint,
} from "./plot/types";

export interface ResourceScatterFallback {
  min: number;
  max: number;
  ticks: number[];
}

export interface ResourceScatterMetric {
  key: ResourceKey;
  label: string;
  axisLabels: Record<PlotScaleKind, string>;
  paretoComparative: string;
  formatAxis: (value: number) => string;
  formatValue: (value: number) => string;
  fallbacks: Record<PlotScaleKind, ResourceScatterFallback>;
}

export interface ResourceScatterDefinition {
  id: string;
  titleId: string;
  descriptionId: string;
  benchmarkName: string;
  scoreDisplayName: string;
  scoreMetricLabel: string;
  yAxisLabel: string;
  yMax: number;
  yStep: number;
  metrics: Partial<Record<ResourceKey, ResourceScatterMetric>>;
  margins?: PlotMargins;
  paretoResourceTolerance?: number;
  getLabelOffset?: (point: ScatterPoint, metric: ResourceKey, index: number) => PointOffset;
  getTip: (point: ScatterPoint) => string;
}

export interface PrepareResourceScatterOptions {
  selectedPoints: readonly ScatterPoint[];
  metricKey: ResourceKey;
  scale: PlotScaleKind;
  pareto: boolean;
  showLabels: boolean;
  showFamilyLines: boolean;
  width: number;
}

export function resourceValue(point: ScatterPoint, key: ResourceKey): number {
  const value = point[key];
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new RangeError(`Missing or invalid ${key} value for ${point.id}`);
  }
  return value;
}

function percentTickInterval(domainMax: number): number {
  if (domainMax <= 40) return 5;
  if (domainMax <= 80) return 10;
  return 20;
}

function resourceAxis(
  metric: ResourceScatterMetric,
  scale: PlotScaleKind,
  values: number[],
): PlotAxisModel {
  const fallback = metric.fallbacks[scale];
  const calculated =
    scale === "log"
      ? createLogScale(values, fallback.min, fallback.max, fallback.ticks)
      : createLinearValueScale(values, fallback.min, fallback.max, fallback.ticks);
  return {
    scale,
    domain: [calculated.min, calculated.max],
    ticks: values.length === 0 || scale === "log" ? calculated.ticks : 6,
    label: metric.axisLabels[scale],
    formatTick: metric.formatAxis,
  };
}

export function prepareResourceScoreScatter(
  definition: ResourceScatterDefinition,
  options: PrepareResourceScatterOptions,
): PlotScatterModel<ScatterPoint> {
  const metric = definition.metrics[options.metricKey];
  if (!metric) {
    throw new RangeError(
      `${definition.benchmarkName} does not support the ${options.metricKey} resource metric`,
    );
  }
  const selected = [...options.selectedPoints];
  const visible = options.pareto
    ? paretoFrontier(
        selected.filter((point) => point.score > 0),
        (point) => point.score,
        (point) => resourceValue(point, metric.key),
        definition.paretoResourceTolerance,
      )
    : selected;
  const xAxis = resourceAxis(
    metric,
    options.scale,
    visible.map((point) => resourceValue(point, metric.key)),
  );
  const calculatedY = createLinearScale(
    visible.map((point) => point.score),
    definition.yMax,
    definition.yStep,
  );
  const yAxis: PlotAxisModel = {
    scale: "linear",
    domain: [calculatedY.min, calculatedY.max],
    ticks: visible.length === 0 ? calculatedY.ticks : undefined,
    interval: visible.length === 0 ? undefined : percentTickInterval(calculatedY.max),
    label: definition.yAxisLabel,
    formatTick: formatAxisPercent,
  };
  const points: PlotScatterPoint<ScatterPoint>[] = visible.map((point, index) => {
    const offset = definition.getLabelOffset?.(point, metric.key, index);
    const value = resourceValue(point, metric.key);
    return {
      datum: point,
      id: point.id,
      family: point.family,
      metric: metric.key,
      effort: point.effort,
      x: value,
      y: point.score,
      color: point.color,
      label: point.label,
      shape: point.shape,
      labelDx: offset?.dx ?? 10,
      labelDy: offset?.dy ?? 4,
      ariaLabel: `${point.family}, reasoning effort ${point.effort}, ${metric.label.toLowerCase()} ${metric.formatValue(value)}, ${definition.scoreMetricLabel} ${formatPercent(point.score)}`,
      tip: definition.getTip(point),
    };
  });
  const pointIds = new Set(points.map((point) => point.id));
  if (pointIds.size !== points.length) {
    throw new Error(`${definition.benchmarkName} scatter point identifiers must be unique`);
  }
  const familySeries = buildFamilyLineRuns(points, {
    continuityPoints: options.pareto ? selected : undefined,
  }).map((run) => ({
    family: run.family,
    color: run.points[0]?.color ?? "#656970",
    points: run.points,
  }));
  const quadrantX =
    options.scale === "log"
      ? Math.sqrt(xAxis.domain[0] * xAxis.domain[1])
      : (xAxis.domain[0] + xAxis.domain[1]) / 2;
  const quadrantY = (yAxis.domain[0] + yAxis.domain[1]) / 2;
  const paretoDescription = !options.pareto
    ? ""
    : definition.paretoResourceTolerance
      ? ` Pareto mode shows selected configurations with a score above zero that are not dominated by a higher-scoring configuration whose ${metric.label.toLowerCase()} is lower or within ${formatPercent(definition.paretoResourceTolerance * 100)}.`
      : ` Pareto mode shows selected configurations with a score above zero that are not strictly dominated by a configuration with ${metric.paretoComparative} and a higher score.`;

  return {
    id: definition.id,
    metric: metric.key,
    width: Math.max(options.width, 900),
    height: 560,
    margins: definition.margins ?? { top: 38, right: 70, bottom: 68, left: 70 },
    titleId: definition.titleId,
    descriptionId: definition.descriptionId,
    title: `${definition.benchmarkName} ${metric.label} and ${definition.scoreDisplayName}`,
    description: `Scatter plot with ${metric.label.toLowerCase()} on a ${options.scale} horizontal axis and ${definition.scoreMetricLabel} on the vertical axis. The upper-left green quadrant highlights lower resource use and higher scores; the lower-right gray quadrant shows the opposite combination. Axes adjust to the visible points.${paretoDescription}`,
    xAxis,
    yAxis,
    points,
    familySeries,
    referenceLines: [],
    quadrantX,
    quadrantY,
    showQuadrants: true,
    showLabels: options.showLabels,
    showFamilyLines: options.showFamilyLines,
    pareto: options.pareto,
  };
}
