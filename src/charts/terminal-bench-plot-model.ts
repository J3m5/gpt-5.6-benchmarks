import { terminalData } from "../data";
import type { TerminalItem } from "../types";
import type { PlotBarModel } from "./plot/types";

export interface PrepareTerminalBenchBarOptions {
  containerWidth: number;
}

function itemTip(item: TerminalItem): string {
  return `${item.model}
Reasoning: ${item.reasoning}
Score: ${item.sourceLabel}`;
}

export function prepareTerminalBenchBar({
  containerWidth,
}: PrepareTerminalBenchBarOptions): PlotBarModel<TerminalItem> {
  const items = terminalData.toSorted(
    (first, second) => second.score - first.score || first.model.localeCompare(second.model),
  );
  const baseMargins = { top: 48, right: 28, bottom: 170, left: 68 };
  const itemWidth = 76;
  const contentWidth = baseMargins.left + items.length * itemWidth + baseMargins.right;
  const width = Math.max(containerWidth, contentWidth);
  const extraWidth = width - contentWidth;

  return {
    id: "terminal-chart",
    metric: "score",
    width,
    height: 560,
    margins: {
      ...baseMargins,
      left: baseMargins.left + extraWidth / 2,
      right: baseMargins.right + extraWidth / 2,
    },
    titleId: "terminal-chart-title",
    descriptionId: "terminal-chart-description",
    title: "TerminalBench 2.1 scores by model",
    description:
      "Vertical bar chart sorted by score in descending order, with an axis ranging from 50 to 100 percent. Each horizontal-axis category includes the model and source reasoning level.",
    valueAxis: {
      scale: "linear",
      domain: [50, 100],
      ticks: [50, 75, 100],
      label: "Score",
      formatTick: (value) => `${value}%`,
    },
    items: items.map((item) => ({
      datum: item,
      id: item.model,
      family: item.model,
      metric: "score",
      effort: item.reasoning,
      value: item.score,
      color: item.color,
      categoryLabel: `${item.model} / ${item.reasoning}`,
      valueLabel: item.sourceLabel,
      ariaLabel: `${item.model}, reasoning ${item.reasoning}, score ${item.sourceLabel}`,
      tip: itemTip(item),
    })),
  };
}
