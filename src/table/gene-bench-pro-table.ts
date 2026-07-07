import { geneBenchProScalingPoints } from "../data";
import type { ScatterPoint } from "../types";
import { formatEstimatedCost, formatPercent, integerFormatter } from "../utils/format";
import { createSortableTable, type SortableColumn } from "./sortable-table";

type SortKey = "model" | "effort" | "score" | "tokens" | "cost";

interface GeneBenchProTableConfig {
  selectedConfigurationIds: ReadonlySet<string>;
}

export interface GeneBenchProTable {
  render: () => void;
}

function cost(point: ScatterPoint): number {
  if (typeof point.cost !== "number") {
    throw new RangeError(`Missing estimated cost for ${point.id}`);
  }
  return point.cost;
}

function renderRow(point: ScatterPoint) {
  const row = document.createElement("tr");
  row.dataset.configurationId = point.id;
  row.dataset.score = String(point.score);
  row.dataset.tokens = String(point.tokens);
  row.dataset.cost = String(cost(point));
  row.innerHTML = `
    <td>
      <span class="model-cell">
        <span class="model-dot" style="--model-color:${point.color}" aria-hidden="true"></span>
        ${point.family}
      </span>
    </td>
    <td class="effort-cell">${point.effort}</td>
    <td class="numeric">${formatPercent(point.score)}</td>
    <td class="numeric">${integerFormatter.format(point.tokens)}</td>
    <td class="numeric">${formatEstimatedCost(cost(point))}</td>
  `;
  return row;
}

export function createGeneBenchProTable({
  selectedConfigurationIds,
}: GeneBenchProTableConfig): GeneBenchProTable {
  const columns: (SortableColumn<ScatterPoint> & { key: SortKey })[] = [
    {
      key: "model",
      label: "model",
      value: (point) => point.family,
      initialDirection: "asc",
    },
    {
      key: "effort",
      label: "reasoning",
      value: (point) => point.effort,
      initialDirection: "asc",
    },
    {
      key: "score",
      label: "passrate",
      value: (point) => point.score,
      initialDirection: "desc",
    },
    {
      key: "tokens",
      label: "tokens used",
      value: (point) => point.tokens,
      initialDirection: "desc",
    },
    {
      key: "cost",
      label: "estimated API cost",
      value: cost,
      initialDirection: "desc",
    },
  ];

  return createSortableTable({
    rootId: "genebench-pro-table-panel",
    bodyId: "genebench-pro-table-body",
    statusId: "genebench-pro-sort-status",
    columns,
    defaultSort: { key: "score", direction: "desc" },
    getRows: () =>
      geneBenchProScalingPoints.filter((point) => selectedConfigurationIds.has(point.id)),
    renderRow,
    tieBreaker: (first, second) => second.score - first.score,
  });
}
