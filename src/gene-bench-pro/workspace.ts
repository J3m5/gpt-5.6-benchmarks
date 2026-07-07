import type { GeneBenchProBarChart } from "../charts/gene-bench-pro-bar";
import type { GeneBenchProBarMetric } from "../charts/gene-bench-pro-plot-model";
import type { ResourceScoreChart } from "../charts/resource-score-chart";
import type { GeneBenchProTable } from "../table/gene-bench-pro-table";
import type { ResourceKey } from "../types";
import { byId } from "../utils/dom";
import { createTabList } from "../workspace/tab-list";

type ViewKind = "bar" | "scatter" | "table";

interface View {
  id: string;
  kind: ViewKind;
  metric?: GeneBenchProBarMetric;
}

interface WorkspaceConfig {
  barChart: GeneBenchProBarChart;
  resourceChart: ResourceScoreChart;
  table: GeneBenchProTable;
}

export interface GeneBenchProWorkspace {
  refresh: () => void;
  resize: () => void;
}

const views: View[] = [
  { id: "scatter-tokens", kind: "scatter", metric: "tokens" },
  { id: "scatter-cost", kind: "scatter", metric: "cost" },
  { id: "bar-score", kind: "bar", metric: "score" },
  { id: "bar-tokens", kind: "bar", metric: "tokens" },
  { id: "bar-cost", kind: "bar", metric: "cost" },
  { id: "table", kind: "table" },
];

const barDescriptions: Record<GeneBenchProBarMetric, string> = {
  score: "Passrate \u00b7 ascending",
  tokens: "Tokens used \u00b7 ascending",
  cost: "Estimated API cost (USD) \u00b7 ascending",
};

function viewFor(id: string): View {
  const view = views.find((candidate) => candidate.id === id);
  if (!view) {
    throw new RangeError(`Unsupported GeneBench-Pro view: ${id}`);
  }
  return view;
}

function resourceMetric(view: View): ResourceKey {
  if (view.metric === "cost" || view.metric === "tokens") {
    return view.metric;
  }
  throw new RangeError(`GeneBench-Pro scatter view ${view.id} has no resource metric`);
}

export function createGeneBenchProWorkspace({
  barChart,
  resourceChart,
  table,
}: WorkspaceConfig): GeneBenchProWorkspace {
  const scatterPanel = byId("genebench-pro-scatter-panel", HTMLDivElement);
  const barPanel = byId("genebench-pro-bars-panel", HTMLDivElement);
  const tablePanel = byId("genebench-pro-table-panel", HTMLDivElement);
  const scatterControls = byId("genebench-pro-scatter-controls", HTMLDivElement);
  const quadrantLegend = byId("genebench-pro-quadrant-legend", HTMLSpanElement);
  const metricDescription = byId("genebench-pro-scaling-metric", HTMLParagraphElement);
  const count = byId("genebench-pro-scaling-count", HTMLDivElement);
  const costNote = byId("genebench-pro-cost-note", HTMLParagraphElement);
  let activeView = viewFor("scatter-tokens");

  function selectedCount(): number {
    return resourceChart.selectedIds.size;
  }

  function renderActiveView(): void {
    const scatterActive = activeView.kind === "scatter";
    const barActive = activeView.kind === "bar";
    scatterPanel.hidden = !scatterActive;
    barPanel.hidden = !barActive;
    tablePanel.hidden = activeView.kind !== "table";
    scatterControls.hidden = !scatterActive;
    quadrantLegend.hidden = !scatterActive;
    costNote.hidden =
      activeView.id !== "scatter-cost" &&
      activeView.id !== "bar-cost" &&
      activeView.kind !== "table";

    if (scatterActive) {
      resourceChart.setMetric(resourceMetric(activeView));
      return;
    }

    if (barActive && activeView.metric) {
      barChart.render(activeView.metric);
      metricDescription.textContent = barDescriptions[activeView.metric];
      count.textContent = `${selectedCount()} configuration${selectedCount() === 1 ? "" : "s"}`;
      return;
    }

    table.render();
    metricDescription.textContent = "All scaling metrics \u00b7 sortable table";
    count.textContent = `${selectedCount()} row${selectedCount() === 1 ? "" : "s"}`;
  }

  function activate(viewId: string, tab: HTMLButtonElement): void {
    activeView = viewFor(viewId);
    const activePanel =
      activeView.kind === "scatter"
        ? scatterPanel
        : activeView.kind === "bar"
          ? barPanel
          : tablePanel;
    activePanel.setAttribute("aria-labelledby", tab.id);
    renderActiveView();
  }

  createTabList({
    tabListId: "genebench-pro-view-tabs",
    viewAttribute: "data-genebench-pro-view",
    onActivate: activate,
  });

  return {
    refresh: renderActiveView,
    resize() {
      if (activeView.kind === "scatter") {
        resourceChart.resize();
      } else if (activeView.kind === "bar" && activeView.metric) {
        barChart.render(activeView.metric);
      }
    },
  };
}
