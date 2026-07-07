import { createConfigurationSelect } from "../controls/configuration-select";
import { geneBenchProScalingPoints } from "../data";
import type { ResourceKey } from "../types";
import { byId } from "../utils/dom";
import { geneBenchProAxisLabel, prepareGeneBenchProScatter } from "./gene-bench-pro-plot-model";
import { createPlotScatterRenderer } from "./plot/benchmark-plot";
import type { PlotScaleKind } from "./plot/types";
import type { ResourceScoreChart } from "./resource-score-chart";

export function createGeneBenchProScalingChart(
  onSelectionChange: (selectedIds: ReadonlySet<string>) => void,
): ResourceScoreChart {
  const scrollContainer = byId("genebench-pro-scaling-scroll", HTMLDivElement);
  const count = byId("genebench-pro-scaling-count", HTMLDivElement);
  const metricDescription = byId("genebench-pro-scaling-metric", HTMLParagraphElement);
  const logScaleToggle = byId("genebench-pro-scaling-log-toggle", HTMLInputElement);
  const pointLabelsToggle = byId("genebench-pro-scaling-labels-toggle", HTMLInputElement);
  const familyLinesToggle = byId("genebench-pro-scaling-family-lines-toggle", HTMLInputElement);
  const paretoToggle = byId("genebench-pro-scaling-pareto-toggle", HTMLInputElement);
  const renderer = createPlotScatterRenderer({
    containerId: "genebench-pro-scaling-scroll",
  });
  let activeMetricKey: ResourceKey = "tokens";

  const configurationSelect = createConfigurationSelect({
    id: "genebench-pro-scaling",
    items: geneBenchProScalingPoints.map((point) => ({
      color: point.color,
      group: point.selectionGroup,
      id: point.id,
      label: point.effort,
    })),
    triggerId: "genebench-pro-scaling-selection-trigger",
    summaryId: "genebench-pro-scaling-selection-summary",
    dialogLabel: "Select GeneBench-Pro configurations",
    groupSelection: true,
    showItemSwatches: false,
    isAvailable: () => true,
    onChange() {
      render();
      onSelectionChange(configurationSelect.selectedIds);
    },
  });

  function scale(): PlotScaleKind {
    return logScaleToggle.checked ? "log" : "linear";
  }

  function model() {
    const selectedPoints = geneBenchProScalingPoints.filter((point) =>
      configurationSelect.selectedIds.has(point.id),
    );
    return prepareGeneBenchProScatter({
      selectedPoints,
      metricKey: activeMetricKey,
      scale: scale(),
      pareto: paretoToggle.checked,
      showLabels: pointLabelsToggle.checked,
      showFamilyLines: familyLinesToggle.checked,
      width: scrollContainer.clientWidth,
    });
  }

  function render(): void {
    const chartModel = model();
    renderer.render(chartModel);
    metricDescription.textContent = `${geneBenchProAxisLabel(activeMetricKey, chartModel.xAxis.scale)} \u00b7 passrate`;
    count.textContent = `${chartModel.points.length} point${chartModel.points.length === 1 ? "" : "s"}${paretoToggle.checked ? " \u00b7 Pareto" : ""}`;
  }

  logScaleToggle.addEventListener("change", render);
  pointLabelsToggle.addEventListener("change", render);
  familyLinesToggle.addEventListener("change", render);
  paretoToggle.addEventListener("change", render);
  render();

  return {
    render,
    selectedIds: configurationSelect.selectedIds,
    setMetric(key) {
      if (key !== "cost" && key !== "tokens") {
        throw new RangeError(`Unsupported GeneBench-Pro resource metric: ${key}`);
      }
      activeMetricKey = key;
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
