import type { PointerCoordinates } from "../types";
import { byId } from "../utils/dom";

export interface TooltipController {
  hide: () => void;
  show: (coordinates: PointerCoordinates, content: string) => void;
}

export function createTooltip(): TooltipController {
  const element = byId("tooltip", HTMLDivElement);

  return {
    hide() {
      element.classList.remove("visible");
      element.setAttribute("aria-hidden", "true");
    },
    show(coordinates, content) {
      element.innerHTML = content;
      element.style.left = `${coordinates.clientX}px`;
      element.style.top = `${coordinates.clientY}px`;
      element.classList.add("visible");
      element.setAttribute("aria-hidden", "false");
    },
  };
}
