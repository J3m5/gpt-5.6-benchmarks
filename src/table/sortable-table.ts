import { byId, query } from "../utils/dom";

type SortDirection = "asc" | "desc";
type SortValue = number | string;

export interface SortableColumn<T> {
  key: string;
  label: string;
  value: (row: T) => SortValue;
  initialDirection: SortDirection;
}

interface SortableTableOptions<T, K extends string> {
  rootId: string;
  bodyId: string;
  statusId: string;
  columns: readonly (SortableColumn<T> & { key: K })[];
  defaultSort: { key: K; direction: SortDirection };
  getRows: () => readonly T[];
  renderRow: (row: T) => HTMLTableRowElement;
  tieBreaker?: (first: T, second: T) => number;
}

export interface SortableTable {
  render: () => void;
}

export function createSortableTable<T, K extends string>({
  rootId,
  bodyId,
  statusId,
  columns,
  defaultSort,
  getRows,
  renderRow,
  tieBreaker,
}: SortableTableOptions<T, K>): SortableTable {
  const root = byId(rootId, HTMLDivElement);
  const tableBody = byId(bodyId, HTMLTableSectionElement);
  const sortStatus = byId(statusId, HTMLParagraphElement);
  const tableSort = { ...defaultSort };

  function columnFor(value: string | undefined): SortableColumn<T> & { key: K } {
    const column = columns.find((candidate) => candidate.key === value);
    if (column) {
      return column;
    }
    throw new RangeError(`Unsupported table sort key: ${value ?? "missing"}`);
  }

  function render(): void {
    const direction = tableSort.direction === "asc" ? 1 : -1;
    const column = columnFor(tableSort.key);
    const rows = [...getRows()].toSorted((first, second) => {
      const firstValue = column.value(first);
      const secondValue = column.value(second);
      const comparison =
        typeof firstValue === "string" && typeof secondValue === "string"
          ? firstValue.localeCompare(secondValue)
          : Number(firstValue) - Number(secondValue);
      const directedComparison = comparison * direction;
      return directedComparison !== 0 ? directedComparison : (tieBreaker?.(first, second) ?? 0);
    });

    tableBody.replaceChildren(...rows.map(renderRow));
    sortStatus.textContent = `Sorted by ${column.label}, ${tableSort.direction === "asc" ? "ascending" : "descending"}`;

    root.querySelectorAll<HTMLTableCellElement>("th[data-sort-key]").forEach((header) => {
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

  root.querySelectorAll<HTMLButtonElement>(".sort-button").forEach((button) => {
    button.addEventListener("click", () => {
      const column = columnFor(button.dataset.sortKey);
      const key = column.key;
      if (tableSort.key === key) {
        tableSort.direction = tableSort.direction === "asc" ? "desc" : "asc";
      } else {
        tableSort.key = key;
        tableSort.direction = column.initialDirection;
      }
      render();
    });
  });

  return { render };
}
