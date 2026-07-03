import { geneScatterPoints } from "../data";
import type { MetricLabelOffsets } from "../types";
import type { TooltipController } from "../ui/tooltip";
import { byId } from "../utils/dom";
import { createResourceScoreChart, type ResourceScoreChart } from "./resource-score";

const metricLabelOffsets: MetricLabelOffsets = {
  cost: {
    "GPT-5.6 Terra|none": { dy: -10 },
  },
  latency: {
    "GPT-5.6 Terra|none": { dy: -10 },
  },
  tokens: {
    "GPT-5.6 Terra|none": { dy: -10 },
  },
};

export function createGeneBenchResourceChart(
  selectedModels: ReadonlySet<string>,
  tooltip: TooltipController,
): ResourceScoreChart {
  const logScaleToggle = byId("gene-scatter-log-toggle", HTMLInputElement);
  const chart = createResourceScoreChart(
    {
      id: "gene-scatter",
      points: geneScatterPoints,
      svgId: "gene-scatter",
      scrollId: "gene-scatter-scroll",
      countId: "scatter-count",
      triggerId: "scatter-selection-trigger",
      summaryId: "scatter-selection-summary",
      paretoId: "pareto-toggle",
      pointLabelsToggleId: "gene-scatter-labels-toggle",
      familyLinesToggleId: "gene-scatter-family-lines-toggle",
      metricSelectId: "gene-scatter-metric-select",
      getMetricOverride: () => ({
        scale: logScaleToggle.checked ? "log" : "linear",
      }),
      headingId: "gene-scatter-title",
      metricDescriptionId: "gene-scatter-metric",
      selectionDialogLabel: "Select GeneBench configurations",
      selectionGroupsAreSelectable: true,
      selectionItemLabel: (point) => point.effort,
      showSelectionItemSwatches: false,
      pointIsAvailable: (point) => selectedModels.has(point.family),
      xFallbacks: {
        cost: {
          min: 0.01,
          max: 2.5,
          ticks: [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2],
        },
        latency: {
          min: 0.3,
          max: 20,
          ticks: [0.5, 1, 2, 5, 10, 20],
        },
        tokens: {
          min: 500,
          max: 100000,
          ticks: [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000],
        },
      },
      xScaleFallbacks: {
        cost: {
          linear: {
            min: 0,
            max: 2.5,
            ticks: [0, 0.5, 1, 1.5, 2, 2.5],
          },
        },
        latency: {
          linear: {
            min: 0,
            max: 20,
            ticks: [0, 5, 10, 15, 20],
          },
        },
        tokens: {
          linear: {
            min: 0,
            max: 100000,
            ticks: [0, 20000, 40000, 60000, 80000, 100000],
          },
        },
      },
      yMax: 35,
      yStep: 5,
      yAxisTitle: "Score",
      scoreTooltipLabel: "Score",
      benchmarkName: "GeneBench v1",
      scoreDisplayName: "score",
      scoreMetricLabel: "pass@1 score",
      metricLabelOffsets,
      svgTitleId: "gene-scatter-svg-title",
      svgDescriptionId: "gene-scatter-description",
    },
    tooltip,
  );
  logScaleToggle.addEventListener("change", chart.render);
  return chart;
}
