import { byId, query } from "../utils/dom";

export interface ConfigurationSelectItem {
  color: string;
  group: string;
  id: string;
  label: string;
}

interface ConfigurationSelectConfig {
  id: string;
  items: ConfigurationSelectItem[];
  triggerId: string;
  summaryId: string;
  dialogLabel: string;
  groupSelection?: boolean;
  showItemSwatches?: boolean;
  isAvailable: (item: ConfigurationSelectItem) => boolean;
  onChange: () => void;
}

export interface ConfigurationSelect {
  close: (options?: { restoreFocus?: boolean }) => void;
  refresh: () => void;
  reposition: () => void;
  selectedIds: ReadonlySet<string>;
}

export function createConfigurationSelect({
  id,
  items,
  triggerId,
  summaryId,
  dialogLabel,
  groupSelection = false,
  showItemSwatches = true,
  isAvailable,
  onChange,
}: ConfigurationSelectConfig): ConfigurationSelect {
  const trigger = byId(triggerId, HTMLButtonElement);
  const summary = byId(summaryId, HTMLSpanElement);
  const selectedIds = new Set(items.map((item) => item.id));
  const inputs = new Map<string, HTMLInputElement>();
  const groupInputs = new Map<string, HTMLInputElement>();
  const panel = document.createElement("div");

  panel.className = "multi-select-panel";
  panel.id = `${id}-selection-panel`;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", dialogLabel);
  panel.hidden = true;
  panel.innerHTML = `
    <div class="selection-list"></div>
    <div class="selection-actions">
      <button class="selection-action" data-action="clear" type="button">Clear</button>
      <button class="selection-action" data-action="all" type="button">Select all</button>
    </div>
  `;
  document.body.appendChild(panel);
  trigger.setAttribute("aria-controls", panel.id);

  const selectionList = query(panel, ".selection-list", HTMLDivElement);
  const clearButton = query(panel, '[data-action="clear"]', HTMLButtonElement);
  const selectAllButton = query(panel, '[data-action="all"]', HTMLButtonElement);
  const groupedItems = new Map<string, ConfigurationSelectItem[]>();
  items.forEach((item) => {
    const groupItems = groupedItems.get(item.group) ?? [];
    groupItems.push(item);
    groupedItems.set(item.group, groupItems);
  });

  groupedItems.forEach((groupItems, groupName) => {
    const section = document.createElement("section");
    section.className = "selection-group";
    section.setAttribute("aria-label", groupName);

    if (groupSelection) {
      const groupLabel = document.createElement("label");
      const groupInput = document.createElement("input");
      const groupText = document.createElement("span");

      groupLabel.className = "selection-group-control";
      groupLabel.style.setProperty("--option-color", groupItems[0]?.color ?? "#656970");
      groupInput.type = "checkbox";
      groupInput.dataset.selectionGroupToggle = groupName;
      groupInput.setAttribute("aria-label", `${groupName} configurations`);
      groupText.textContent = groupName;
      groupLabel.append(groupInput, groupText);
      section.appendChild(groupLabel);
      groupInputs.set(groupName, groupInput);

      groupInput.addEventListener("change", () => {
        groupItems.filter(isAvailable).forEach((item) => {
          if (groupInput.checked) {
            selectedIds.add(item.id);
          } else {
            selectedIds.delete(item.id);
          }
        });
        refresh();
        onChange();
      });
    } else {
      const title = document.createElement("h3");
      title.className = "selection-group-title";
      title.textContent = groupName;
      section.appendChild(title);
    }

    groupItems.forEach((item) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("span");

      label.className = "selection-option";
      label.classList.toggle("without-swatch", !showItemSwatches);
      label.style.setProperty("--option-color", item.color);
      input.type = "checkbox";
      input.value = item.id;
      input.checked = true;
      input.setAttribute(
        "aria-label",
        item.label.startsWith(item.group)
          ? item.label
          : `${item.group}, reasoning effort ${item.label}`,
      );
      text.textContent = item.label;
      label.appendChild(input);
      if (showItemSwatches) {
        const swatch = document.createElement("span");
        swatch.className = "swatch";
        swatch.setAttribute("aria-hidden", "true");
        label.appendChild(swatch);
      }
      label.appendChild(text);
      inputs.set(item.id, input);
      input.addEventListener("change", () => {
        if (input.checked) {
          selectedIds.add(item.id);
        } else {
          selectedIds.delete(item.id);
        }
        refresh();
        onChange();
      });
      section.appendChild(label);
    });
    selectionList.appendChild(section);
  });

  function refresh(): void {
    const availableItems = items.filter(isAvailable);
    items.forEach((item) => {
      const input = inputs.get(item.id);
      if (!input) {
        throw new Error(`Missing selection input for ${item.id}`);
      }
      const available = isAvailable(item);
      input.disabled = !available;
      input.checked = selectedIds.has(item.id);
      input.closest(".selection-option")?.classList.toggle("is-disabled", !available);
    });
    groupedItems.forEach((groupItems, groupName) => {
      const groupInput = groupInputs.get(groupName);
      if (!groupInput) {
        return;
      }
      const availableGroupItems = groupItems.filter(isAvailable);
      const selectedGroupCount = availableGroupItems.filter((item) =>
        selectedIds.has(item.id),
      ).length;
      groupInput.disabled = availableGroupItems.length === 0;
      groupInput
        .closest(".selection-group-control")
        ?.classList.toggle("is-disabled", groupInput.disabled);
      groupInput.checked =
        availableGroupItems.length > 0 && selectedGroupCount === availableGroupItems.length;
      groupInput.indeterminate =
        selectedGroupCount > 0 && selectedGroupCount < availableGroupItems.length;
    });
    const selectedAvailableCount = availableItems.filter((item) => selectedIds.has(item.id)).length;
    summary.textContent = `${selectedAvailableCount} / ${availableItems.length} models/efforts`;
    clearButton.disabled = selectedIds.size === 0;
    selectAllButton.disabled = selectedIds.size === items.length;
  }

  function positionPanel(): void {
    const margin = 12;
    const gap = 6;
    const triggerRect = trigger.getBoundingClientRect();
    const width = Math.min(360, window.innerWidth - margin * 2);

    panel.style.width = `${width}px`;
    panel.style.maxHeight = `${Math.min(520, window.innerHeight - margin * 2)}px`;

    const panelHeight = panel.getBoundingClientRect().height;
    const left = Math.max(margin, Math.min(triggerRect.left, window.innerWidth - width - margin));
    let top = triggerRect.bottom + gap;

    if (top + panelHeight > window.innerHeight - margin) {
      const above = triggerRect.top - panelHeight - gap;
      top = above >= margin ? above : Math.max(margin, window.innerHeight - panelHeight - margin);
    }

    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function open(): void {
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    positionPanel();
  }

  function close({ restoreFocus = false }: { restoreFocus?: boolean } = {}): void {
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) {
      trigger.focus();
    }
  }

  trigger.addEventListener("click", () => {
    if (panel.hidden) {
      open();
    } else {
      close();
    }
  });
  clearButton.addEventListener("click", () => {
    selectedIds.clear();
    refresh();
    onChange();
  });
  selectAllButton.addEventListener("click", () => {
    items.forEach((item) => {
      selectedIds.add(item.id);
    });
    refresh();
    onChange();
  });
  document.addEventListener("pointerdown", (event) => {
    const { target } = event;
    if (
      target instanceof Node &&
      !panel.hidden &&
      !panel.contains(target) &&
      !trigger.contains(target)
    ) {
      close();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      close({ restoreFocus: true });
    }
  });
  window.addEventListener(
    "scroll",
    (event) => {
      const { target } = event;
      if (!panel.hidden && (!(target instanceof Node) || !panel.contains(target))) {
        positionPanel();
      }
    },
    true,
  );

  refresh();

  return {
    close,
    refresh,
    reposition() {
      if (!panel.hidden) {
        positionPanel();
      }
    },
    selectedIds,
  };
}
