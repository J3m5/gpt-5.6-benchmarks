import { selectedGeneBenchPoints } from "../data";
import type { BenchmarkGroup, MetricKey } from "../types";
import type { TooltipController } from "../ui/tooltip";
import { byId, gridStyles, svgNode } from "../utils/dom";
import { integerFormatter } from "../utils/format";

interface BarMetric {
  key: MetricKey;
  axis: string;
  max: number;
  step: number;
  formatTick: (value: number) => string;
  formatValue: (value: number) => string;
}

interface GeneBenchBarChartConfig {
  selectedConfigurationIds: ReadonlySet<string>;
  tooltip: TooltipController;
}

export interface GeneBenchBarChart {
  render: (metricKey: MetricKey) => void;
}

const metrics: Record<MetricKey, BarMetric> = {
  score: {
    key: "score",
    axis: "Score",
    max: 35,
    step: 5,
    formatTick: (value) => `${value}%`,
    formatValue: (value) => `${Number.isInteger(value) ? value : String(value).replace(/0$/, "")}%`,
  },
  tokens: {
    key: "tokens",
    axis: "Output tokens",
    max: 60000,
    step: 10000,
    formatTick: (value) => (value === 0 ? "0" : `${value / 1000}k`),
    formatValue: (value) => integerFormatter.format(value),
  },
  latency: {
    key: "latency",
    axis: "Latency (minutes)",
    max: 15,
    step: 2.5,
    formatTick: (value) => `${value}`,
    formatValue: (value) => `${value.toFixed(2)} min`,
  },
  cost: {
    key: "cost",
    axis: "API cost (USD)",
    max: 2,
    step: 0.5,
    formatTick: (value) => `$${value.toFixed(1)}`,
    formatValue: (value) => `$${value.toFixed(2)}`,
  },
};

function metricFor(value: string): BarMetric {
  switch (value) {
    case "score":
      return metrics.score;
    case "tokens":
      return metrics.tokens;
    case "latency":
      return metrics.latency;
    case "cost":
      return metrics.cost;
    default:
      throw new RangeError(`Unsupported metric: ${value}`);
  }
}

function tooltipContent(
  group: BenchmarkGroup,
  effort: string,
  value: number,
  metric: BarMetric,
): string {
  return `<strong>${group.model}</strong>Reasoning effort: ${effort}<br>${metric.axis}: ${metric.formatValue(value)}`;
}

export function createGeneBenchBarChart({
  selectedConfigurationIds,
  tooltip,
}: GeneBenchBarChartConfig): GeneBenchBarChart {
  const svg = byId("chart", SVGSVGElement);
  const scrollContainer = byId("chart-scroll", HTMLDivElement);

  function render(metricKey: MetricKey): void {
    const metric = metricFor(metricKey);
    const points = selectedGeneBenchPoints(selectedConfigurationIds).toSorted(
      (a, b) => a[metric.key] - b[metric.key] || a.group.model.localeCompare(b.group.model),
    );
    const margins = { top: 54, right: 28, bottom: 158, left: 68 };
    const chartHeight = 650;
    const plotHeight = chartHeight - margins.top - margins.bottom;
    const itemWidth = 55;
    const contentWidth = margins.left + points.length * itemWidth + margins.right;
    const width = Math.max(scrollContainer.clientWidth, contentWidth);
    const extraWidth = width - contentWidth;
    const xOffset = Math.max(0, extraWidth / 2);
    const plotBottom = margins.top + plotHeight;
    const maxValue = metric.max;

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${chartHeight}`);
    svg.style.width = `${width}px`;
    svg.append(
      svgNode(
        "title",
        { id: "chart-title" },
        `GeneBench v1 ${metric.axis.toLowerCase()} by model and reasoning effort`,
      ),
      svgNode(
        "desc",
        { id: "chart-description" },
        `Bar chart sorted by ${metric.axis.toLowerCase()} in ascending order. Each horizontal-axis category represents one model and reasoning effort level.`,
      ),
    );

    for (let tick = 0; tick <= maxValue + metric.step / 10; tick += metric.step) {
      const y = plotBottom - (tick / maxValue) * plotHeight;
      const gridStyle = tick === 0 ? gridStyles.axis : gridStyles.minor;
      svg.append(
        svgNode("line", {
          x1: margins.left,
          x2: width - margins.right,
          y1: y,
          y2: y,
          stroke: gridStyle.stroke,
          "stroke-width": gridStyle.width,
          "data-grid-line": tick === 0 ? "axis" : "minor",
        }),
        svgNode(
          "text",
          {
            x: margins.left - 14,
            y: y + 4,
            fill: "#656970",
            "font-size": 12,
            "font-variant-numeric": "tabular-nums",
            "text-anchor": "end",
          },
          metric.formatTick(tick),
        ),
      );
    }

    svg.appendChild(
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
        metric.axis,
      ),
    );

    points.forEach(({ group, effort, ...values }, index) => {
      const value = values[metric.key];
      const x = margins.left + index * itemWidth + itemWidth / 2 + xOffset;
      const barHeight = (value / maxValue) * plotHeight;
      const y = plotBottom - barHeight;
      const bar = svgNode("rect", {
        x: x - 15,
        y,
        width: 30,
        height: barHeight,
        rx: 2,
        fill: group.color,
        tabindex: 0,
        role: "graphics-symbol",
        "data-configuration-id": `${group.model}|${effort}`,
        "data-metric": metric.key,
        "data-value": value,
        "aria-label": `${group.model}, effort ${effort}, ${metric.axis} ${metric.formatValue(value)}`,
      });
      const showTooltip = (coordinates: { clientX: number; clientY: number }): void => {
        tooltip.show(coordinates, tooltipContent(group, effort, value, metric));
      };

      bar.addEventListener("pointerenter", showTooltip);
      bar.addEventListener("pointermove", showTooltip);
      bar.addEventListener("pointerleave", tooltip.hide);
      bar.addEventListener("focus", () => {
        const rect = bar.getBoundingClientRect();
        showTooltip({
          clientX: rect.left + rect.width / 2,
          clientY: rect.top,
        });
      });
      bar.addEventListener("blur", tooltip.hide);

      svg.append(
        bar,
        svgNode(
          "text",
          {
            x,
            y: y - 9,
            fill: "#34363a",
            "font-size": 11,
            "font-weight": 650,
            "font-variant-numeric": "tabular-nums",
            "text-anchor": "middle",
          },
          metric.formatValue(value),
        ),
        svgNode(
          "text",
          {
            x,
            y: plotBottom + 24,
            fill: group.color,
            "font-size": 11,
            "font-weight": 650,
            "text-anchor": "end",
            transform: `rotate(-48 ${x} ${plotBottom + 24})`,
          },
          `${group.model} / ${effort}`,
        ),
      );
    });
  }

  scrollContainer.addEventListener("scroll", tooltip.hide);

  return { render };
}
