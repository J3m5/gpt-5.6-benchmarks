import { createExploitGymResourceChart } from "./charts/exploit-gym-resource";
import { createExploitBenchBarChart } from "./charts/exploit-bench-bar";
import { createExploitBenchChart } from "./charts/exploit-bench";
import { createExploitGymBarChart } from "./charts/exploit-gym-bar";
import { createGeneBenchBarChart } from "./charts/gene-bench-bar";
import { createGeneBenchProBarChart } from "./charts/gene-bench-pro-bar";
import { createGeneBenchProScalingChart } from "./charts/gene-bench-pro-scaling";
import { createGeneBenchResourceChart } from "./charts/gene-bench-resource";
import { createTerminalBenchChart } from "./charts/terminal-bench";
import { createExploitGymDurationControl } from "./controls/exploit-gym-duration";
import { createExploitBenchWorkspace } from "./exploit-bench/workspace";
import { createExploitGymWorkspace } from "./exploit-gym/workspace";
import { createGeneBenchProWorkspace } from "./gene-bench-pro/workspace";
import { createGeneBenchWorkspace } from "./gene-bench/workspace";
import { renderApiPricingTable } from "./table/api-pricing-table";
import { createExploitBenchTable } from "./table/exploit-bench-table";
import { createExploitGymTable } from "./table/exploit-gym-table";
import { createGeneBenchProTable } from "./table/gene-bench-pro-table";
import { createGeneBenchTable } from "./table/gene-bench-table";
import { createTerminalBenchTable } from "./table/terminal-bench-table";
import { createTerminalBenchWorkspace } from "./terminal-bench/workspace";

renderApiPricingTable();

let exploitGymDuration = "2h";
let refreshGeneBenchWorkspace = (): void => {};
let refreshGeneBenchProWorkspace = (): void => {};
let refreshExploitBenchWorkspace = (): void => {};
let refreshExploitGymWorkspace = (): void => {};

const geneBenchResourceChart = createGeneBenchResourceChart(() => {
  refreshGeneBenchWorkspace();
});
const geneBenchBarChart = createGeneBenchBarChart({
  selectedConfigurationIds: geneBenchResourceChart.selectedIds,
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
const geneBenchProScalingChart = createGeneBenchProScalingChart(() => {
  refreshGeneBenchProWorkspace();
});
const geneBenchProBarChart = createGeneBenchProBarChart({
  selectedConfigurationIds: geneBenchProScalingChart.selectedIds,
});
const geneBenchProTable = createGeneBenchProTable({
  selectedConfigurationIds: geneBenchProScalingChart.selectedIds,
});
const geneBenchProWorkspace = createGeneBenchProWorkspace({
  barChart: geneBenchProBarChart,
  resourceChart: geneBenchProScalingChart,
  table: geneBenchProTable,
});
refreshGeneBenchProWorkspace = geneBenchProWorkspace.refresh;
const exploitBenchChart = createExploitBenchChart(() => {
  refreshExploitBenchWorkspace();
});
const exploitBenchBarChart = createExploitBenchBarChart({
  selectedConfigurationIds: exploitBenchChart.selectedIds,
});
const exploitBenchTable = createExploitBenchTable({
  selectedConfigurationIds: exploitBenchChart.selectedIds,
});
const exploitBenchWorkspace = createExploitBenchWorkspace({
  barChart: exploitBenchBarChart,
  scatterChart: exploitBenchChart,
  table: exploitBenchTable,
});
refreshExploitBenchWorkspace = exploitBenchWorkspace.refresh;
const activeExploitGymDuration = (): string => exploitGymDuration;
const exploitGymResourceChart = createExploitGymResourceChart(activeExploitGymDuration, () => {
  refreshExploitGymWorkspace();
});
const exploitGymBarChart = createExploitGymBarChart({
  activeDuration: activeExploitGymDuration,
  selectedConfigurationIds: exploitGymResourceChart.selectedIds,
});
const exploitGymTable = createExploitGymTable({
  activeDuration: activeExploitGymDuration,
  selectedConfigurationIds: exploitGymResourceChart.selectedIds,
});
const exploitGymWorkspace = createExploitGymWorkspace({
  activeDuration: activeExploitGymDuration,
  barChart: exploitGymBarChart,
  resourceChart: exploitGymResourceChart,
  table: exploitGymTable,
});
refreshExploitGymWorkspace = exploitGymWorkspace.refresh;
const terminalBenchChart = createTerminalBenchChart();
const terminalBenchTable = createTerminalBenchTable();
const terminalBenchWorkspace = createTerminalBenchWorkspace({
  chart: terminalBenchChart,
  table: terminalBenchTable,
});

createExploitGymDurationControl((duration) => {
  exploitGymDuration = duration;
  exploitGymResourceChart.refreshVisibility();
  exploitGymWorkspace.refresh();
});

terminalBenchWorkspace.refresh();
exploitBenchWorkspace.refresh();

window.addEventListener("resize", () => {
  geneBenchWorkspace.resize();
  geneBenchProWorkspace.resize();
  exploitBenchWorkspace.resize();
  exploitGymWorkspace.resize();
  terminalBenchWorkspace.resize();
});
