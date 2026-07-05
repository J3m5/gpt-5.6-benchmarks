import {
  createLinearScale,
  createLinearValueScale,
  createLogScale,
  paretoFrontier,
} from "../chart-math";
import { buildFamilyLineRuns } from "../chart-series";
import {
  createConfigurationSelect,
  type ConfigurationSelectItem,
} from "../controls/configuration-select";
import type { MetricLabelOffsets, PointOffset, ResourceKey, ScatterPoint } from "../types";
import type { TooltipController } from "../ui/tooltip";
import { byId, gridStyles, svgNode } from "../utils/dom";
import {
  formatAxisCost,
  formatAxisNumber,
  formatAxisPercent,
  formatCost,
  formatLatency,
  formatPercent,
  integerFormatter,
} from "../utils/format";

type ScaleKind = "linear" | "log";

interface ResourceMetric {
  key: ResourceKey;
  label: string;
  axisTitle: string;
  axisTitles: Record<ScaleKind, string>;
  paretoComparative: string;
  scale: ScaleKind;
  formatAxis: (value: number) => string;
  formatValue: (value: number) => string;
}

type ResourceMetricOverride = Partial<Omit<ResourceMetric, "key">>;

interface ScaleFallback {
  min: number;
  max: number;
  ticks: number[];
}

export interface ResourceChartConfig {
  id: string;
  points: ScatterPoint[];
  svgId: string;
  scrollId: string;
  countId: string;
  triggerId: string;
  summaryId: string;
  paretoId: string;
  pointLabelsToggleId?: string;
  familyLinesToggleId?: string;
  metricSelectId?: string;
  metricKey?: ResourceKey;
  onSelectionChange?: (selectedIds: ReadonlySet<string>) => void;
  metricOverrides?: Partial<Record<ResourceKey, ResourceMetricOverride>>;
  getMetricOverride?: (key: ResourceKey) => ResourceMetricOverride;
  headingId: string;
  headingText?: string;
  metricDescriptionId: string;
  selectionDialogLabel: string;
  selectionGroupsAreSelectable?: boolean;
  selectionItemLabel?: (point: ScatterPoint) => string;
  showSelectionItemSwatches?: boolean;
  pointIsAvailable?: (point: ScatterPoint) => boolean;
  pointIsDisplayed?: (point: ScatterPoint) => boolean;
  countSuffix?: () => string;
  rightMargin?: number;
  showDurationInTooltip?: boolean;
  xFallbacks: Partial<Record<ResourceKey, ScaleFallback>>;
  xScaleFallbacks?: Partial<Record<ResourceKey, Partial<Record<ScaleKind, ScaleFallback>>>>;
  yMax: number;
  yStep: number;
  yAxisTitle: string;
  scoreTooltipLabel: string;
  benchmarkName: string;
  scoreDisplayName: string;
  scoreMetricLabel: string;
  paretoResourceTolerance?: number;
  metricLabelOffsets?: MetricLabelOffsets;
  showPointLabels?: boolean;
  getTooltipContent?: (point: ScatterPoint) => string;
  getPointOffset?: (point: ScatterPoint) => PointOffset;
  getLabelOffset?: (point: ScatterPoint, index: number) => PointOffset;
  svgTitleId: string;
  svgDescriptionId: string;
}

export interface ResourceScoreChart {
  refreshVisibility: () => void;
  render: () => void;
  resize: () => void;
  selectedIds: ReadonlySet<string>;
  setMetric: (key: ResourceKey) => void;
}

const scatterXMetrics: Record<ResourceKey, ResourceMetric> = {
  cost: {
    key: "cost",
    label: "API cost",
    axisTitle: "API cost (USD, logarithmic scale)",
    axisTitles: {
      linear: "API cost (USD, linear scale)",
      log: "API cost (USD, logarithmic scale)",
    },
    paretoComparative: "a lower API cost",
    scale: "log",
    formatAxis: formatAxisCost,
    formatValue: formatCost,
  },
  latency: {
    key: "latency",
    label: "Latency",
    axisTitle: "Latency (minutes, logarithmic scale)",
    axisTitles: {
      linear: "Latency (minutes, linear scale)",
      log: "Latency (minutes, logarithmic scale)",
    },
    paretoComparative: "lower latency",
    scale: "log",
    formatAxis: formatAxisNumber,
    formatValue: formatLatency,
  },
  tokens: {
    key: "tokens",
    label: "Output tokens",
    axisTitle: "Output tokens (logarithmic scale)",
    axisTitles: {
      linear: "Output tokens (linear scale)",
      log: "Output tokens (logarithmic scale)",
    },
    paretoComparative: "fewer output tokens",
    scale: "log",
    formatAxis: formatAxisNumber,
    formatValue: (value) => integerFormatter.format(value),
  },
};

function resourceMetricFor(
  value: string,
  overrides?: Partial<Record<ResourceKey, ResourceMetricOverride>>,
): ResourceMetric {
  let metric: ResourceMetric;
  switch (value) {
    case "cost":
      metric = scatterXMetrics.cost;
      break;
    case "latency":
      metric = scatterXMetrics.latency;
      break;
    case "tokens":
      metric = scatterXMetrics.tokens;
      break;
    default:
      throw new RangeError(`Unsupported resource metric: ${value}`);
  }
  return { ...metric, ...overrides?.[metric.key] };
}

function resourceValue(point: ScatterPoint, key: ResourceKey): number {
  const value = point[key];
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new RangeError(`Missing or invalid ${key} value for ${point.id}`);
  }
  return value;
}

function selectionIdFor(point: ScatterPoint): string {
  return point.selectionId ?? point.id;
}

export function createResourceScoreChart(
  config: ResourceChartConfig,
  tooltip: TooltipController,
): ResourceScoreChart {
  const svg = byId(config.svgId, SVGSVGElement);
  const scrollContainer = byId(config.scrollId, HTMLDivElement);
  const count = byId(config.countId, HTMLDivElement);
  const paretoToggle = byId(config.paretoId, HTMLInputElement);
  const pointLabelsToggle = config.pointLabelsToggleId
    ? byId(config.pointLabelsToggleId, HTMLInputElement)
    : undefined;
  const familyLinesToggle = config.familyLinesToggleId
    ? byId(config.familyLinesToggleId, HTMLInputElement)
    : undefined;
  const metricSelect = config.metricSelectId
    ? byId(config.metricSelectId, HTMLSelectElement)
    : undefined;
  const heading = byId(config.headingId, HTMLHeadingElement);
  const metricDescription = byId(config.metricDescriptionId, HTMLParagraphElement);
  let activeMetricKey = config.metricKey;
  const xMetric = (): ResourceMetric => {
    const key = metricSelect?.value ?? activeMetricKey;
    if (!key) {
      throw new Error(`Resource chart ${config.id} has no horizontal metric`);
    }
    const metric = resourceMetricFor(key, config.metricOverrides);
    const override = config.getMetricOverride?.(metric.key);
    const merged = {
      ...metric,
      ...override,
    };
    return {
      ...merged,
      axisTitle: override?.axisTitle ?? merged.axisTitles[merged.scale],
    };
  };
  const selectionItems = [
    ...new Map(
      config.points.map((point) => [
        selectionIdFor(point),
        { ...point, id: selectionIdFor(point) },
      ]),
    ).values(),
  ];

  function pointIsAvailable(point: ScatterPoint): boolean {
    return config.pointIsAvailable ? config.pointIsAvailable(point) : true;
  }

  function pointIsDisplayed(point: ScatterPoint): boolean {
    return config.pointIsDisplayed ? config.pointIsDisplayed(point) : true;
  }

  function selectionItemIsAvailable(item: ConfigurationSelectItem): boolean {
    return config.points.some(
      (point) =>
        selectionIdFor(point) === item.id && pointIsAvailable(point) && pointIsDisplayed(point),
    );
  }

  const configurationSelect = createConfigurationSelect({
    id: config.id,
    items: selectionItems.map((item) => ({
      color: item.color,
      group: item.selectionGroup,
      id: item.id,
      label: config.selectionItemLabel?.(item) ?? item.selectionLabel,
    })),
    triggerId: config.triggerId,
    summaryId: config.summaryId,
    dialogLabel: config.selectionDialogLabel,
    groupSelection: config.selectionGroupsAreSelectable,
    showItemSwatches: config.showSelectionItemSwatches,
    isAvailable: selectionItemIsAvailable,
    onChange() {
      render();
      config.onSelectionChange?.(configurationSelect.selectedIds);
    },
  });

  function selectedPoints(): ScatterPoint[] {
    return config.points.filter(
      (point) =>
        configurationSelect.selectedIds.has(selectionIdFor(point)) &&
        pointIsAvailable(point) &&
        pointIsDisplayed(point),
    );
  }

  function activePoints(selected: ScatterPoint[]): ScatterPoint[] {
    if (!paretoToggle.checked) {
      return selected;
    }

    const positiveScorePoints = selected.filter((point) => point.score > 0);
    const metric = xMetric();

    return paretoFrontier(
      positiveScorePoints,
      (point) => point.score,
      (point) => resourceValue(point, metric.key),
      config.paretoResourceTolerance,
    );
  }

  function showPointTooltip(
    coordinates: { clientX: number; clientY: number },
    point: ScatterPoint,
  ): void {
    if (config.getTooltipContent) {
      tooltip.show(coordinates, config.getTooltipContent(point));
      return;
    }
    const duration =
      config.showDurationInTooltip && point.duration ? `Time limit: ${point.duration}<br>` : "";
    tooltip.show(
      coordinates,
      `<strong>${point.family}</strong>${duration}Reasoning effort: ${point.effort}<br>${config.scoreTooltipLabel}: ${formatPercent(point.score)}<br>API cost: ${formatCost(resourceValue(point, "cost"))}<br>Latency: ${formatLatency(resourceValue(point, "latency"))}<br>Output tokens: ${integerFormatter.format(resourceValue(point, "tokens"))}`,
    );
  }

  function render(): void {
    const selected = selectedPoints();
    const points = activePoints(selected);
    const metric = xMetric();
    const fallback =
      config.xScaleFallbacks?.[metric.key]?.[metric.scale] ?? config.xFallbacks[metric.key];
    if (!fallback) {
      throw new Error(`Resource chart ${config.id} has no fallback for ${metric.key}`);
    }
    const width = Math.max(scrollContainer.clientWidth, 900);
    const chartHeight = 560;
    const margins = { top: 38, right: config.rightMargin ?? 128, bottom: 68, left: 70 };
    const plotWidth = width - margins.left - margins.right;
    const plotHeight = chartHeight - margins.top - margins.bottom;
    const plotBottom = margins.top + plotHeight;
    const resourceValues = points.map((point) => resourceValue(point, metric.key));
    const xScale =
      metric.scale === "log"
        ? createLogScale(resourceValues, fallback.min, fallback.max, fallback.ticks)
        : createLinearValueScale(resourceValues, fallback.min, fallback.max, fallback.ticks);
    const yScale = createLinearScale(
      points.map((point) => point.score),
      config.yMax,
      config.yStep,
    );
    const yRange = yScale.max - yScale.min;
    const xMidpoint =
      metric.scale === "log" ? Math.sqrt(xScale.min * xScale.max) : (xScale.min + xScale.max) / 2;
    const yMidpoint = (yScale.min + yScale.max) / 2;
    const plotMidX = margins.left + plotWidth / 2;
    const plotMidY = margins.top + plotHeight / 2;
    const xPosition = (value: number): number => {
      const ratio =
        metric.scale === "log"
          ? (Math.log10(value) - Math.log10(xScale.min)) /
            (Math.log10(xScale.max) - Math.log10(xScale.min))
          : (value - xScale.min) / (xScale.max - xScale.min);
      return margins.left + ratio * plotWidth;
    };
    const yPosition = (value: number): number =>
      plotBottom - ((value - yScale.min) / yRange) * plotHeight;
    const positionedPoints = points.map((point, index) => {
      const positionOffset = config.getPointOffset?.(point) ?? {};
      return {
        ...point,
        index,
        x: xPosition(resourceValue(point, metric.key)) + (positionOffset.dx ?? 0),
        y: yPosition(point.score) + (positionOffset.dy ?? 0),
      };
    });

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${chartHeight}`);
    svg.style.width = `${width}px`;
    svg.dataset.xMin = String(xScale.min);
    svg.dataset.xMax = String(xScale.max);
    svg.dataset.yMin = String(yScale.min);
    svg.dataset.yMax = String(yScale.max);
    svg.dataset.quadrantX = String(xMidpoint);
    svg.dataset.quadrantY = String(yMidpoint);
    svg.dataset.xMetric = metric.key;
    svg.dataset.xScale = metric.scale;
    const pointLabelsAreVisible = pointLabelsToggle?.checked ?? config.showPointLabels !== false;
    const familyLinesAreVisible = familyLinesToggle?.checked ?? false;
    svg.dataset.pointLabels = String(pointLabelsAreVisible);
    svg.dataset.familyLines = String(familyLinesAreVisible);
    heading.textContent =
      config.headingText ??
      `${config.benchmarkName}: ${metric.label} vs. ${config.scoreDisplayName}`;
    metricDescription.textContent = `${metric.axisTitle} \u00b7 ${config.scoreMetricLabel}`;
    const paretoDescription = !paretoToggle.checked
      ? ""
      : config.paretoResourceTolerance
        ? ` Pareto mode shows selected configurations with a score above zero that are not dominated by a higher-scoring configuration whose ${metric.label.toLowerCase()} is lower or within ${formatPercent(config.paretoResourceTolerance * 100)}.`
        : ` Pareto mode shows selected configurations with a score above zero that are not strictly dominated by a configuration with ${metric.paretoComparative} and a higher score.`;
    svg.append(
      svgNode(
        "title",
        { id: config.svgTitleId },
        `${config.benchmarkName} ${metric.label} and ${config.scoreDisplayName}`,
      ),
      svgNode(
        "desc",
        { id: config.svgDescriptionId },
        `Scatter plot with ${metric.label.toLowerCase()} on a ${metric.scale} horizontal axis and ${config.scoreMetricLabel} on the vertical axis. The upper-left green quadrant highlights lower resource use and higher scores; the lower-right gray quadrant shows the opposite combination. Axes adjust to the visible points.${paretoDescription}`,
      ),
      svgNode("rect", {
        x: margins.left,
        y: margins.top,
        width: plotWidth / 2,
        height: plotHeight / 2,
        fill: "#e2f7e4",
        "data-quadrant": "attractive",
        "aria-hidden": "true",
      }),
      svgNode("rect", {
        x: plotMidX,
        y: plotMidY,
        width: plotWidth / 2,
        height: plotHeight / 2,
        fill: "#f7f7f7",
        "data-quadrant": "opposite",
        "aria-hidden": "true",
      }),
    );

    yScale.ticks.forEach((tick) => {
      const y = yPosition(tick);
      const gridStyle = tick === yScale.min ? gridStyles.axis : gridStyles.minor;
      svg.append(
        svgNode("line", {
          x1: margins.left,
          x2: width - margins.right,
          y1: y,
          y2: y,
          stroke: gridStyle.stroke,
          "stroke-width": gridStyle.width,
          "data-grid-line": tick === yScale.min ? "axis" : "minor",
        }),
        svgNode(
          "text",
          {
            x: margins.left - 14,
            y: y + 4,
            fill: "#656970",
            "font-size": 12,
            "text-anchor": "end",
            "data-axis": "y",
            "data-value": tick,
          },
          formatAxisPercent(tick),
        ),
      );
    });

    xScale.ticks.forEach((tick) => {
      const x = xPosition(tick);
      svg.append(
        svgNode("line", {
          x1: x,
          x2: x,
          y1: margins.top,
          y2: plotBottom,
          stroke: gridStyles.minor.stroke,
          "stroke-width": gridStyles.minor.width,
          "data-grid-line": "minor",
        }),
        svgNode(
          "text",
          {
            x,
            y: plotBottom + 25,
            fill: "#656970",
            "font-size": 12,
            "font-variant-numeric": "tabular-nums",
            "text-anchor": "middle",
            "data-axis": "x",
            "data-value": tick,
          },
          metric.formatAxis(tick),
        ),
      );
    });

    svg.append(
      svgNode(
        "text",
        {
          x: 20,
          y: margins.top + plotHeight / 2,
          fill: "#34363a",
          "font-size": 13,
          "font-weight": 650,
          "text-anchor": "middle",
          transform: `rotate(-90 20 ${margins.top + plotHeight / 2})`,
        },
        config.yAxisTitle,
      ),
      svgNode(
        "text",
        {
          x: margins.left + plotWidth / 2,
          y: chartHeight - 10,
          fill: "#34363a",
          "font-size": 13,
          "font-weight": 650,
          "text-anchor": "middle",
        },
        metric.axisTitle,
      ),
    );

    if (familyLinesAreVisible) {
      buildFamilyLineRuns(positionedPoints, {
        continuityPoints: paretoToggle.checked ? selected : undefined,
      }).forEach((run) => {
        const color = run.points[0]?.color;
        if (!color) {
          return;
        }
        svg.append(
          svgNode("polyline", {
            points: run.points.map((point) => `${point.x},${point.y}`).join(" "),
            fill: "none",
            stroke: color,
            "stroke-width": 1.25,
            "stroke-opacity": 0.45,
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
            "pointer-events": "none",
            "aria-hidden": "true",
            "data-family-line": run.family,
            "data-point-ids": JSON.stringify(run.points.map((point) => point.id)),
          }),
        );
      });
    }

    positionedPoints.forEach((point) => {
      const override =
        config.metricLabelOffsets?.[metric.key]?.[point.id] ??
        config.getLabelOffset?.(point, point.index) ??
        {};
      const dx = override.dx ?? 10;
      const dy = override.dy ?? 4;
      const commonAttributes = {
        fill: point.color,
        "data-point-id": point.id,
        tabindex: 0,
        role: "graphics-symbol",
        "aria-label": `${point.family}, reasoning effort ${point.effort}, ${metric.label.toLowerCase()} ${metric.formatValue(resourceValue(point, metric.key))}, ${config.scoreMetricLabel} ${formatPercent(point.score)}`,
      };
      const symbol =
        point.shape === "square"
          ? svgNode("rect", {
              ...commonAttributes,
              x: point.x - 5,
              y: point.y - 5,
              width: 10,
              height: 10,
              rx: 2,
            })
          : svgNode("circle", {
              ...commonAttributes,
              cx: point.x,
              cy: point.y,
              r: 6,
            });

      symbol.addEventListener("pointerenter", (event) => {
        if (event instanceof PointerEvent) {
          showPointTooltip(event, point);
        }
      });
      symbol.addEventListener("pointermove", (event) => {
        if (event instanceof PointerEvent) {
          showPointTooltip(event, point);
        }
      });
      symbol.addEventListener("pointerleave", tooltip.hide);
      symbol.addEventListener("focus", () => {
        const rect = symbol.getBoundingClientRect();
        showPointTooltip(
          {
            clientX: rect.left + rect.width / 2,
            clientY: rect.top,
          },
          point,
        );
      });
      symbol.addEventListener("blur", tooltip.hide);

      svg.append(symbol);
      if (pointLabelsAreVisible) {
        svg.append(
          svgNode(
            "text",
            {
              x: point.x + dx,
              y: point.y + dy,
              fill: "#34363a",
              "font-size": 10,
              "font-weight": 400,
              "text-anchor": "start",
              "data-point-label": point.id,
              "pointer-events": "none",
              style: "paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round",
            },
            point.label,
          ),
        );
      }
    });

    count.textContent = `${points.length} point${points.length === 1 ? "" : "s"}${config.countSuffix ? ` \u00b7 ${config.countSuffix()}` : ""}${paretoToggle.checked ? " \u00b7 Pareto" : ""}`;
  }

  paretoToggle.addEventListener("change", render);
  pointLabelsToggle?.addEventListener("change", render);
  familyLinesToggle?.addEventListener("change", render);
  metricSelect?.addEventListener("change", render);
  scrollContainer.addEventListener("scroll", tooltip.hide);

  render();

  return {
    render,
    selectedIds: configurationSelect.selectedIds,
    setMetric(key) {
      activeMetricKey = key;
      if (metricSelect) {
        metricSelect.value = key;
      }
      render();
    },
    resize() {
      render();
      configurationSelect.reposition();
    },
    refreshVisibility() {
      configurationSelect.refresh();
      render();
    },
  };
}
