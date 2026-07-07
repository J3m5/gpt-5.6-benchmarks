import { byId } from "../utils/dom";
import { createPlotBarRenderer } from "./plot/benchmark-plot";
import { prepareTerminalBenchBar } from "./terminal-bench-plot-model";

export interface TerminalBenchChart {
  render: () => void;
}

export function createTerminalBenchChart(): TerminalBenchChart {
  const chartContainer = byId("terminal-chart-wrap", HTMLDivElement);
  const renderer = createPlotBarRenderer({
    containerId: "terminal-chart-wrap",
  });

  function render(): void {
    const style = getComputedStyle(chartContainer);
    const contentWidth =
      chartContainer.clientWidth -
      Number.parseFloat(style.paddingLeft) -
      Number.parseFloat(style.paddingRight);
    renderer.render(
      prepareTerminalBenchBar({
        containerWidth: contentWidth,
      }),
    );
  }

  return { render };
}
