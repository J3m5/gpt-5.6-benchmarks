import type { TerminalBenchChart } from "../charts/terminal-bench";
import type { TerminalBenchTable } from "../table/terminal-bench-table";
import { byId } from "../utils/dom";
import { createTabList } from "../workspace/tab-list";

type ViewKind = "score" | "table";

interface WorkspaceConfig {
  chart: TerminalBenchChart;
  table: TerminalBenchTable;
}

export interface TerminalBenchWorkspace {
  refresh: () => void;
  resize: () => void;
}

function viewFor(id: string): ViewKind {
  if (id === "score" || id === "table") {
    return id;
  }
  throw new RangeError(`Unsupported TerminalBench view: ${id}`);
}

export function createTerminalBenchWorkspace({
  chart,
  table,
}: WorkspaceConfig): TerminalBenchWorkspace {
  const chartPanel = byId("terminalbench-chart-panel", HTMLDivElement);
  const tablePanel = byId("terminalbench-table-panel", HTMLDivElement);
  const metric = byId("terminalbench-metric", HTMLParagraphElement);
  const count = byId("terminalbench-count", HTMLDivElement);
  let activeView = viewFor("score");

  function renderActiveView(): void {
    const chartActive = activeView === "score";
    chartPanel.hidden = !chartActive;
    tablePanel.hidden = activeView !== "table";

    if (chartActive) {
      chart.render();
      metric.textContent = "Coding \u00b7 sorted by score (descending) \u00b7 50\u2013100% axis";
      count.textContent = "9 models";
      return;
    }

    table.render();
    metric.textContent = "Coding \u00b7 sortable table";
    count.textContent = "9 rows";
  }

  function activate(viewId: string, tab: HTMLButtonElement): void {
    activeView = viewFor(viewId);
    const activePanel = activeView === "score" ? chartPanel : tablePanel;
    activePanel.setAttribute("aria-labelledby", tab.id);
    renderActiveView();
  }

  createTabList({
    tabListId: "terminalbench-view-tabs",
    viewAttribute: "data-terminalbench-view",
    onActivate: activate,
  });

  return {
    refresh: renderActiveView,
    resize() {
      if (activeView === "score") {
        chart.render();
      }
    },
  };
}
