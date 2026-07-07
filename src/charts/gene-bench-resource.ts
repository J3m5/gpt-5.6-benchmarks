import { createConfigurationSelect } from "../controls/configuration-select";
import { geneScatterPoints } from "../data";
import type { ResourceKey } from "../types";
import { byId } from "../utils/dom";
import { geneBenchScatterAxisLabel, prepareGeneBenchScatter } from "./gene-bench-plot-model";
import { createPlotScatterRenderer } from "./plot/benchmark-plot";
import type { ResourceScoreChart } from "./resource-score-chart";

export function createGeneBenchResourceChart(
  onSelectionChange: (selectedIds: ReadonlySet<string>) => void,
): ResourceScoreChart {
  const scrollContainer = byId("gene-scatter-scroll", HTMLDivElement);
  const count = byId("gene-workspace-count", HTMLDivElement);
  const heading = byId("genebench-title", HTMLHeadingElement);
  const metricDescription = byId("gene-workspace-metric", HTMLParagraphElement);
  const logScaleToggle = byId("gene-scatter-log-toggle", HTMLInputElement);
  const pointLabelsToggle = byId("gene-scatter-labels-toggle", HTMLInputElement);
  const familyLinesToggle = byId("gene-scatter-family-lines-toggle", HTMLInputElement);
  const paretoToggle = byId("pareto-toggle", HTMLInputElement);
  const renderer = createPlotScatterRenderer({
    containerId: "gene-scatter-scroll",
  });
  let activeMetricKey: ResourceKey = "cost";

  const configurationSelect = createConfigurationSelect({
    id: "gene-scatter",
    items: geneScatterPoints.map((point) => ({
      color: point.color,
      group: point.selectionGroup,
      id: point.id,
      label: point.effort,
    })),
    triggerId: "gene-selection-trigger",
    summaryId: "gene-selection-summary",
    dialogLabel: "Select GeneBench configurations",
    groupSelection: true,
    showItemSwatches: false,
    isAvailable: () => true,
    onChange() {
      render();
      onSelectionChange(configurationSelect.selectedIds);
    },
  });

  function model() {
    const scale = logScaleToggle.checked ? "log" : "linear";
    return prepareGeneBenchScatter(geneScatterPoints, {
      selectedIds: configurationSelect.selectedIds,
      metricKey: activeMetricKey,
      scale,
      pareto: paretoToggle.checked,
      showLabels: pointLabelsToggle.checked,
      showFamilyLines: familyLinesToggle.checked,
      width: scrollContainer.clientWidth,
    });
  }

  function render(): void {
    const chartModel = model();
    renderer.render(chartModel);
    heading.textContent = "GeneBench v1";
    metricDescription.textContent = `${geneBenchScatterAxisLabel(activeMetricKey, chartModel.xAxis.scale)} \u00b7 Pass@1 score`;
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
