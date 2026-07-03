import { terminalData } from "../data";
import type { TerminalItem } from "../types";
import type { TooltipController } from "../ui/tooltip";
import { byId, gridStyles, svgNode } from "../utils/dom";

export interface TerminalBenchChart {
  render: () => void;
}

function tooltipContent(item: TerminalItem): string {
  return `<strong>${item.model}</strong>Reasoning: ${item.reasoning}<br>Score: ${item.sourceLabel}`;
}

export function createTerminalBenchChart(tooltip: TooltipController): TerminalBenchChart {
  const svg = byId("terminal-chart", SVGSVGElement);
  const chartContainer = byId("terminal-chart-wrap", HTMLDivElement);

  function render(): void {
    const width = Math.max(chartContainer.clientWidth - 36, 316);
    const mobile = width < 620;
    const margins = {
      top: 30,
      right: 62,
      bottom: 48,
      left: mobile ? 166 : 220,
    };
    const rowHeight = 52;
    const barHeight = 26;
    const plotHeight = terminalData.length * rowHeight;
    const plotWidth = Math.max(88, width - margins.left - margins.right);
    const chartHeight = margins.top + plotHeight + margins.bottom;
    const plotBottom = margins.top + plotHeight;
    const minScore = 50;
    const tickStep = 25;

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${chartHeight}`);
    svg.style.height = `${chartHeight}px`;
    svg.append(
      svgNode("title", { id: "terminal-chart-title" }, "TerminalBench 2.1 scores by model"),
      svgNode(
        "desc",
        { id: "terminal-chart-description" },
        "Horizontal bar chart sorted by score in descending order, with an axis ranging from 50 to 100 percent.",
      ),
    );

    for (let tick = minScore; tick <= 100; tick += tickStep) {
      const x = margins.left + ((tick - minScore) / (100 - minScore)) * plotWidth;
      const gridStyle = tick === minScore ? gridStyles.axis : gridStyles.minor;
      svg.append(
        svgNode("line", {
          x1: x,
          x2: x,
          y1: margins.top,
          y2: plotBottom,
          stroke: gridStyle.stroke,
          "stroke-width": gridStyle.width,
          "data-grid-line": tick === minScore ? "axis" : "minor",
        }),
        svgNode(
          "text",
          {
            x,
            y: plotBottom + 24,
            fill: "#656970",
            "font-size": 12,
            "font-variant-numeric": "tabular-nums",
            "text-anchor": "middle",
          },
          `${tick}%`,
        ),
      );
    }

    terminalData
      .toSorted((a, b) => b.score - a.score)
      .forEach((item, index) => {
        const rowY = margins.top + index * rowHeight;
        const y = rowY + (rowHeight - barHeight) / 2;
        const valueWidth = ((item.score - minScore) / (100 - minScore)) * plotWidth;
        const bar = svgNode("rect", {
          x: margins.left,
          y,
          width: valueWidth,
          height: barHeight,
          rx: 2,
          fill: item.color,
          tabindex: 0,
          role: "graphics-symbol",
          "aria-label": `${item.model}, reasoning ${item.reasoning}, score ${item.sourceLabel}`,
        });
        const showTooltip = (coordinates: { clientX: number; clientY: number }): void => {
          tooltip.show(coordinates, tooltipContent(item));
        };

        bar.addEventListener("pointerenter", showTooltip);
        bar.addEventListener("pointermove", showTooltip);
        bar.addEventListener("pointerleave", tooltip.hide);
        bar.addEventListener("focus", () => {
          const rect = bar.getBoundingClientRect();
          showTooltip({ clientX: rect.right, clientY: rect.top });
        });
        bar.addEventListener("blur", tooltip.hide);

        svg.append(
          svgNode(
            "text",
            {
              x: margins.left - 14,
              y: rowY + 21,
              fill: "#34363a",
              "font-size": mobile ? 11 : 13,
              "font-weight": 650,
              "text-anchor": "end",
            },
            item.model,
          ),
          svgNode(
            "text",
            {
              x: margins.left - 14,
              y: rowY + 37,
              fill: "#7a7e85",
              "font-size": 10,
              "font-family": "SFMono-Regular, Consolas, Liberation Mono, monospace",
              "text-anchor": "end",
            },
            `reasoning: ${item.reasoning}`,
          ),
          bar,
          svgNode(
            "text",
            {
              x: margins.left + valueWidth + 8,
              y: rowY + rowHeight / 2 + 4,
              fill: "#34363a",
              "font-size": 12,
              "font-weight": 700,
              "font-variant-numeric": "tabular-nums",
            },
            `${item.score.toFixed(1)}%`,
          ),
        );
      });

    svg.appendChild(
      svgNode(
        "text",
        {
          x: margins.left + plotWidth / 2,
          y: chartHeight - 8,
          fill: "#34363a",
          "font-size": 13,
          "font-weight": 650,
          "text-anchor": "middle",
        },
        "Score",
      ),
    );
  }

  return { render };
}
