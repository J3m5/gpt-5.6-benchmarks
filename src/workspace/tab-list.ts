import { byId, query } from "../utils/dom";

interface TabListOptions {
  tabListId: string;
  viewAttribute: string;
  onActivate: (viewId: string, tab: HTMLButtonElement) => void;
}

function viewIdFor(tab: HTMLButtonElement, attribute: string): string {
  const viewId = tab.getAttribute(attribute);
  if (!viewId) {
    throw new RangeError(`Missing ${attribute} on tab #${tab.id}`);
  }
  return viewId;
}

export function createTabList({ tabListId, viewAttribute, onActivate }: TabListOptions): void {
  const tabList = byId(tabListId, HTMLDivElement);
  const tabs = Array.from(tabList.querySelectorAll<HTMLButtonElement>('[role="tab"]'));

  function activate(tab: HTMLButtonElement, focus: boolean): void {
    tabs.forEach((candidate) => {
      const active = candidate === tab;
      candidate.setAttribute("aria-selected", String(active));
      candidate.tabIndex = active ? 0 : -1;
    });
    onActivate(viewIdFor(tab, viewAttribute), tab);
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

  activate(query(tabList, '[role="tab"][aria-selected="true"]', HTMLButtonElement), false);
}
