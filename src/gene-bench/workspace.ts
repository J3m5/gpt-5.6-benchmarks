import type { GeneBenchBarChart } from "../charts/gene-bench-bar";
import type { ResourceScoreChart } from "../charts/resource-score";
import type { GeneBenchTable } from "../table/gene-bench-table";
import type { MetricKey, ResourceKey } from "../types";
import { byId, query } from "../utils/dom";

type GeneBenchViewKind = "bar" | "scatter" | "table";

interface GeneBenchView {
  id: string;
  kind: GeneBenchViewKind;
  metric?: MetricKey;
}

interface GeneBenchWorkspaceConfig {
  barChart: GeneBenchBarChart;
  resourceChart: ResourceScoreChart;
  table: GeneBenchTable;
}

export interface GeneBenchWorkspace {
  refresh: () => void;
  resize: () => void;
}

const views: GeneBenchView[] = [
  { id: "scatter-cost", kind: "scatter", metric: "cost" },
  { id: "scatter-latency", kind: "scatter", metric: "latency" },
  { id: "scatter-tokens", kind: "scatter", metric: "tokens" },
  { id: "bar-score", kind: "bar", metric: "score" },
  { id: "bar-cost", kind: "bar", metric: "cost" },
  { id: "bar-latency", kind: "bar", metric: "latency" },
  { id: "bar-tokens", kind: "bar", metric: "tokens" },
  { id: "table", kind: "table" },
];

const barDescriptions: Record<MetricKey, string> = {
  score: "Pass@1 score \u00b7 ascending",
  cost: "API cost (USD) \u00b7 ascending",
  latency: "Latency (minutes) \u00b7 ascending",
  tokens: "Output tokens \u00b7 ascending",
};

function viewFor(id: string | undefined): GeneBenchView {
  const view = views.find((candidate) => candidate.id === id);
  if (!view) {
    throw new RangeError(`Unsupported GeneBench view: ${id}`);
  }
  return view;
}

function resourceMetricFor(view: GeneBenchView): ResourceKey {
  const metric = view.metric;
  if (metric === "cost" || metric === "latency" || metric === "tokens") {
    return metric;
  }
  throw new Error(`GeneBench scatter view ${view.id} has no resource metric`);
}

export function createGeneBenchWorkspace({
  barChart,
  resourceChart,
  table,
}: GeneBenchWorkspaceConfig): GeneBenchWorkspace {
  const tabList = byId("gene-view-tabs", HTMLDivElement);
  const tabs = Array.from(tabList.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
  const scatterPanel = byId("gene-scatter-panel", HTMLDivElement);
  const barPanel = byId("gene-bars-panel", HTMLDivElement);
  const tablePanel = byId("gene-table-panel", HTMLDivElement);
  const scatterControls = byId("gene-scatter-controls", HTMLDivElement);
  const quadrantLegend = byId("gene-quadrant-legend", HTMLSpanElement);
  const metricDescription = byId("gene-workspace-metric", HTMLParagraphElement);
  const count = byId("gene-workspace-count", HTMLDivElement);
  let activeView = viewFor("scatter-cost");

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

    if (scatterActive) {
      resourceChart.setMetric(resourceMetricFor(activeView));
      return;
    }

    if (barActive) {
      const metric = activeView.metric;
      if (!metric) {
        throw new Error(`GeneBench bar view ${activeView.id} has no metric`);
      }
      barChart.render(metric);
      metricDescription.textContent = barDescriptions[metric];
      count.textContent = `${selectedCount()} configuration${selectedCount() === 1 ? "" : "s"}`;
      return;
    }

    table.render();
    metricDescription.textContent = "All benchmark metrics \u00b7 sortable table";
    count.textContent = `${selectedCount()} row${selectedCount() === 1 ? "" : "s"}`;
  }

  function activate(tab: HTMLButtonElement, focus: boolean): void {
    activeView = viewFor(tab.dataset.geneView);
    tabs.forEach((candidate) => {
      const active = candidate === tab;
      candidate.setAttribute("aria-selected", String(active));
      candidate.tabIndex = active ? 0 : -1;
    });
    const activePanel =
      activeView.kind === "scatter"
        ? scatterPanel
        : activeView.kind === "bar"
          ? barPanel
          : tablePanel;
    activePanel.setAttribute("aria-labelledby", tab.id);
    renderActiveView();
    if (focus) {
      tab.focus();
      tab.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      activate(tab, false);
    });
    tab.addEventListener("keydown", (event) => {
      let targetIndex: number | undefined;
      switch (event.key) {
        case "ArrowLeft":
          targetIndex = (index - 1 + tabs.length) % tabs.length;
          break;
        case "ArrowRight":
          targetIndex = (index + 1) % tabs.length;
          break;
        case "Home":
          targetIndex = 0;
          break;
        case "End":
          targetIndex = tabs.length - 1;
          break;
        default:
          return;
      }
      event.preventDefault();
      const target = tabs[targetIndex];
      if (target) {
        activate(target, true);
      }
    });
  });

  const initialTab = query(tabList, '[role="tab"][aria-selected="true"]', HTMLButtonElement);
  activate(initialTab, false);

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
