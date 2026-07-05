import { createExploitGymResourceChart } from "./charts/exploit-gym-resource";
import { createExploitBenchChart } from "./charts/exploit-bench";
import { createGeneBenchBarChart } from "./charts/gene-bench-bar";
import { createGeneBenchProScalingChart } from "./charts/gene-bench-pro-scaling";
import { createGeneBenchResourceChart } from "./charts/gene-bench-resource";
import { createTerminalBenchChart } from "./charts/terminal-bench";
import { createExploitGymDurationControl } from "./controls/exploit-gym-duration";
import { createGeneBenchWorkspace } from "./gene-bench/workspace";
import { renderApiPricingTable } from "./table/api-pricing-table";
import { createGeneBenchTable } from "./table/gene-bench-table";
import { createTooltip } from "./ui/tooltip";

renderApiPricingTable();

const tooltip = createTooltip();
let exploitGymDuration = "2h";
let refreshGeneBenchWorkspace = (): void => {};

const geneBenchResourceChart = createGeneBenchResourceChart(tooltip, () => {
  refreshGeneBenchWorkspace();
});
const geneBenchBarChart = createGeneBenchBarChart({
  selectedConfigurationIds: geneBenchResourceChart.selectedIds,
  tooltip,
});
const geneBenchTable = createGeneBenchTable({
  selectedConfigurationIds: geneBenchResourceChart.selectedIds,
});
const geneBenchWorkspace = createGeneBenchWorkspace({
  barChart: geneBenchBarChart,
  resourceChart: geneBenchResourceChart,
  table: geneBenchTable,
});
refreshGeneBenchWorkspace = geneBenchWorkspace.refresh;
const geneBenchProScalingChart = createGeneBenchProScalingChart(tooltip);
const exploitBenchChart = createExploitBenchChart(tooltip);
const exploitGymResourceChart = createExploitGymResourceChart(() => exploitGymDuration, tooltip);
const terminalBenchChart = createTerminalBenchChart(tooltip);

createExploitGymDurationControl((duration) => {
  exploitGymDuration = duration;
  exploitGymResourceChart.refreshVisibility();
});

terminalBenchChart.render();
exploitBenchChart.render();

window.addEventListener("resize", () => {
  geneBenchWorkspace.resize();
  geneBenchProScalingChart.resize();
  exploitBenchChart.resize();
  exploitGymResourceChart.resize();
  terminalBenchChart.render();
});
