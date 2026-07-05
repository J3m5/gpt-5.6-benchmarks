import { selectedGeneBenchPoints } from "../data";
import type { MetricKey } from "../types";
import { byId, query } from "../utils/dom";
import { formatCost, formatLatency, formatPercent, integerFormatter } from "../utils/format";

type SortKey = "model" | "effort" | MetricKey;
type SortDirection = "asc" | "desc";

interface GeneBenchTableConfig {
  selectedConfigurationIds: ReadonlySet<string>;
}

export interface GeneBenchTable {
  render: () => void;
}

const sortNames: Record<SortKey, string> = {
  model: "model",
  effort: "reasoning effort",
  score: "score",
  tokens: "tokens",
  latency: "latency",
  cost: "API cost",
};

function sortKeyFor(value: string | undefined): SortKey {
  switch (value) {
    case "model":
    case "effort":
    case "score":
    case "tokens":
    case "latency":
    case "cost":
      return value;
    case undefined:
      throw new RangeError("Missing table sort key");
    default:
      throw new RangeError(`Unsupported table sort key: ${value}`);
  }
}

export function createGeneBenchTable({
  selectedConfigurationIds,
}: GeneBenchTableConfig): GeneBenchTable {
  const tableBody = byId("data-table-body", HTMLTableSectionElement);
  const sortStatus = byId("sort-status", HTMLParagraphElement);
  const tableSort: { key: SortKey; direction: SortDirection } = {
    key: "score",
    direction: "desc",
  };

  function render(): void {
    const direction = tableSort.direction === "asc" ? 1 : -1;
    const points = selectedGeneBenchPoints(selectedConfigurationIds).toSorted((a, b) => {
      const aValue = tableSort.key === "model" ? a.group.model : a[tableSort.key];
      const bValue = tableSort.key === "model" ? b.group.model : b[tableSort.key];
      const comparison =
        typeof aValue === "string" && typeof bValue === "string"
          ? aValue.localeCompare(bValue)
          : Number(aValue) - Number(bValue);
      return comparison * direction || b.score - a.score;
    });

    tableBody.replaceChildren();
    points.forEach(({ group, effort, score, tokens, latency, cost }) => {
      const row = document.createElement("tr");
      row.dataset.configurationId = `${group.model}|${effort}`;
      row.dataset.score = String(score);
      row.dataset.tokens = String(tokens);
      row.dataset.latency = String(latency);
      row.dataset.cost = String(cost);
      row.innerHTML = `
        <td>
          <span class="model-cell">
            <span class="model-dot" style="--model-color:${group.color}" aria-hidden="true"></span>
            ${group.model}
          </span>
        </td>
        <td class="effort-cell">${effort}</td>
        <td class="numeric">${formatPercent(score)}</td>
        <td class="numeric">${integerFormatter.format(tokens)}</td>
        <td class="numeric">${formatLatency(latency)}</td>
        <td class="numeric">${formatCost(cost)}</td>
      `;
      tableBody.appendChild(row);
    });

    sortStatus.textContent = `Sorted by ${sortNames[tableSort.key]}, ${tableSort.direction === "asc" ? "ascending" : "descending"}`;

    document.querySelectorAll<HTMLTableCellElement>("th[data-sort-key]").forEach((header) => {
      const active = header.dataset.sortKey === tableSort.key;
      header.setAttribute(
        "aria-sort",
        active ? (tableSort.direction === "asc" ? "ascending" : "descending") : "none",
      );
      query(header, ".sort-indicator", HTMLSpanElement).textContent = active
        ? tableSort.direction === "asc"
          ? "\u2191"
          : "\u2193"
        : "\u2195";
    });
  }

  document.querySelectorAll<HTMLButtonElement>(".sort-button").forEach((button) => {
    button.addEventListener("click", () => {
      const key = sortKeyFor(button.dataset.sortKey);
      if (tableSort.key === key) {
        tableSort.direction = tableSort.direction === "asc" ? "desc" : "asc";
      } else {
        tableSort.key = key;
        tableSort.direction = ["model", "effort"].includes(key) ? "asc" : "desc";
      }
      render();
    });
  });

  return { render };
}
