import { byId } from "../utils/dom";
import { prepareGeneBenchProBar, type GeneBenchProBarMetric } from "./gene-bench-pro-plot-model";
import { createPlotBarRenderer } from "./plot/benchmark-plot";

interface GeneBenchProBarChartConfig {
  selectedConfigurationIds: ReadonlySet<string>;
}

export interface GeneBenchProBarChart {
  render: (metricKey: GeneBenchProBarMetric) => void;
}

export function createGeneBenchProBarChart({
  selectedConfigurationIds,
}: GeneBenchProBarChartConfig): GeneBenchProBarChart {
  const scrollContainer = byId("genebench-pro-bars-scroll", HTMLDivElement);
  const renderer = createPlotBarRenderer({
    containerId: "genebench-pro-bars-scroll",
  });

  return {
    render(metricKey) {
      renderer.render(
        prepareGeneBenchProBar({
          selectedIds: selectedConfigurationIds,
          metricKey,
          containerWidth: scrollContainer.clientWidth,
        }),
      );
    },
  };
}
