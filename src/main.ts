import { createExploitGymResourceChart } from "./charts/exploit-gym-resource";
import { createGeneBenchBarChart } from "./charts/gene-bench-bar";
import { createGeneBenchProScalingChart } from "./charts/gene-bench-pro-scaling";
import { createGeneBenchResourceChart } from "./charts/gene-bench-resource";
import { createTerminalBenchChart } from "./charts/terminal-bench";
import { createExploitGymDurationControl } from "./controls/exploit-gym-duration";
import { createModelFilters } from "./controls/model-filters";
import { groups } from "./data";
import { renderApiPricingTable } from "./table/api-pricing-table";
import { createGeneBenchTable } from "./table/gene-bench-table";
import { createTooltip } from "./ui/tooltip";

renderApiPricingTable();

const tooltip = createTooltip();
const selectedModels = new Set(groups.map((group) => group.model));
let exploitGymDuration = "2h";

const geneBenchBarChart = createGeneBenchBarChart({
  selectedModels,
  tooltip,
});
const geneBenchTable = createGeneBenchTable({ selectedModels });
const geneBenchResourceChart = createGeneBenchResourceChart(selectedModels, tooltip);
const geneBenchProScalingChart = createGeneBenchProScalingChart(tooltip);
const exploitGymResourceChart = createExploitGymResourceChart(() => exploitGymDuration, tooltip);
const terminalBenchChart = createTerminalBenchChart(tooltip);

createModelFilters({
  groups,
  selectedModels,
  onChange() {
    geneBenchResourceChart.refreshVisibility();
    geneBenchBarChart.render();
    geneBenchTable.render();
  },
});

createExploitGymDurationControl((duration) => {
  exploitGymDuration = duration;
  exploitGymResourceChart.refreshVisibility();
});

geneBenchBarChart.render();
geneBenchTable.render();
terminalBenchChart.render();

window.addEventListener("resize", () => {
  geneBenchBarChart.render();
  geneBenchResourceChart.resize();
  geneBenchProScalingChart.resize();
  exploitGymResourceChart.resize();
  terminalBenchChart.render();
});
