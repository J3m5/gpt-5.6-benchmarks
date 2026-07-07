import { terminalData } from "../data";
import type { TerminalItem } from "../types";
import { createSortableTable, type SortableColumn } from "./sortable-table";

type SortKey = "model" | "reasoning" | "score";

export interface TerminalBenchTable {
  render: () => void;
}

function renderRow(item: TerminalItem): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.dataset.model = item.model;
  row.dataset.reasoning = item.reasoning;
  row.dataset.score = String(item.score);
  row.innerHTML = `
    <td>
      <span class="model-cell">
        <span class="model-dot" style="--model-color:${item.color}" aria-hidden="true"></span>
        ${item.model}
      </span>
    </td>
    <td class="effort-cell">${item.reasoning}</td>
    <td class="numeric">${item.sourceLabel}</td>
  `;
  return row;
}

export function createTerminalBenchTable(): TerminalBenchTable {
  const columns: (SortableColumn<TerminalItem> & { key: SortKey })[] = [
    {
      key: "model",
      label: "model",
      value: (item) => item.model,
      initialDirection: "asc",
    },
    {
      key: "reasoning",
      label: "source reasoning",
      value: (item) => item.reasoning,
      initialDirection: "asc",
    },
    {
      key: "score",
      label: "score",
      value: (item) => item.score,
      initialDirection: "desc",
    },
  ];

  return createSortableTable({
    rootId: "terminalbench-table-panel",
    bodyId: "terminalbench-table-body",
    statusId: "terminalbench-sort-status",
    columns,
    defaultSort: { key: "score", direction: "desc" },
    getRows: () => terminalData,
    renderRow,
    tieBreaker: (first, second) =>
      second.score - first.score || first.model.localeCompare(second.model),
  });
}
