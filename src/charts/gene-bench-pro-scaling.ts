import { apiOutputPriceFor, geneBenchProScalingPoints } from "../data";
import type { TooltipController } from "../ui/tooltip";
import { byId } from "../utils/dom";
import { formatEstimatedCost, formatPercent, integerFormatter } from "../utils/format";
import { createResourceScoreChart, type ResourceScoreChart } from "./resource-score";

export function createGeneBenchProScalingChart(tooltip: TooltipController): ResourceScoreChart {
  const logScaleToggle = byId("genebench-pro-scaling-log-toggle", HTMLInputElement);
  const chart = createResourceScoreChart(
    {
      id: "genebench-pro-scaling",
      points: geneBenchProScalingPoints,
      svgId: "genebench-pro-scaling",
      scrollId: "genebench-pro-scaling-scroll",
      countId: "genebench-pro-scaling-count",
      triggerId: "genebench-pro-scaling-selection-trigger",
      summaryId: "genebench-pro-scaling-selection-summary",
      paretoId: "genebench-pro-scaling-pareto-toggle",
      pointLabelsToggleId: "genebench-pro-scaling-labels-toggle",
      familyLinesToggleId: "genebench-pro-scaling-family-lines-toggle",
      metricSelectId: "genebench-pro-scaling-metric-select",
      getMetricOverride: (key) => {
        const scale = logScaleToggle.checked ? "logarithmic" : "linear";
        return key === "cost"
          ? {
              label: "Estimated API cost",
              axisTitle: `Estimated API cost (USD, ${scale} scale)`,
              paretoComparative: "a lower estimated API cost",
              scale: logScaleToggle.checked ? "log" : "linear",
            }
          : {
              label: "Tokens used",
              axisTitle: `Tokens used (${scale} scale)`,
              paretoComparative: "fewer tokens used",
              scale: logScaleToggle.checked ? "log" : "linear",
            };
      },
      headingId: "genebench-pro-scaling-title",
      headingText: "GeneBench-Pro: Test-time compute scaling on GPT models",
      metricDescriptionId: "genebench-pro-scaling-metric",
      selectionDialogLabel: "Select GeneBench-Pro configurations",
      selectionGroupsAreSelectable: true,
      selectionItemLabel: (point) => point.effort,
      showSelectionItemSwatches: false,
      xFallbacks: {
        cost: {
          min: 0.005,
          max: 2,
          ticks: [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2],
        },
        tokens: {
          min: 0,
          max: 120000,
          ticks: [0, 20000, 40000, 60000, 80000, 100000, 120000],
        },
      },
      xScaleFallbacks: {
        cost: {
          linear: {
            min: 0,
            max: 1.2,
            ticks: [0, 0.2, 0.4, 0.6, 0.8, 1, 1.2],
          },
        },
        tokens: {
          log: {
            min: 500,
            max: 200000,
            ticks: [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000],
          },
        },
      },
      yMax: 30,
      yStep: 5,
      yAxisTitle: "Passrate",
      scoreTooltipLabel: "Passrate",
      benchmarkName: "GeneBench-Pro",
      scoreDisplayName: "passrate",
      scoreMetricLabel: "passrate",
      paretoResourceTolerance: 0.02,
      getTooltipContent: (point) =>
        `<strong>${point.family}</strong>Reasoning: ${point.effort}<br>Tokens used: ${integerFormatter.format(point.tokens)}<br>Output-token price: $${apiOutputPriceFor(point.family).toFixed(2)} / 1M<br>Estimated API cost: ${formatEstimatedCost(point.cost ?? 0)}<br>Passrate: ${formatPercent(point.score)}`,
      svgTitleId: "genebench-pro-scaling-svg-title",
      svgDescriptionId: "genebench-pro-scaling-description",
    },
    tooltip,
  );
  logScaleToggle.addEventListener("change", chart.render);
  return chart;
}
