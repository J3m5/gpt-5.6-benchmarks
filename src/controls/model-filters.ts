import type { BenchmarkGroup } from "../types";
import { byId, query } from "../utils/dom";

interface ModelFiltersConfig {
  groups: BenchmarkGroup[];
  selectedModels: Set<string>;
  onChange: () => void;
}

export function createModelFilters({ groups, selectedModels, onChange }: ModelFiltersConfig): void {
  const container = byId("filters", HTMLDivElement);

  groups.forEach((group) => {
    const label = document.createElement("label");
    label.className = "filter";
    label.style.setProperty("--filter-color", group.color);
    label.innerHTML = `
      <input type="checkbox" value="${group.model}" checked>
      <span class="check" aria-hidden="true"></span>
      <span class="swatch" aria-hidden="true"></span>
      <span>${group.model}</span>
    `;

    const input = query(label, "input", HTMLInputElement);
    input.addEventListener("change", () => {
      if (input.checked) {
        selectedModels.add(group.model);
      } else if (selectedModels.size > 1) {
        selectedModels.delete(group.model);
      } else {
        input.checked = true;
      }
      onChange();
    });
    container.appendChild(label);
  });
}
