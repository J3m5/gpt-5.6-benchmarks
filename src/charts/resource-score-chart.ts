import type { ResourceKey } from "../types";

export interface ResourceScoreChart {
  refreshVisibility: () => void;
  render: () => void;
  resize: () => void;
  selectedIds: ReadonlySet<string>;
  setMetric: (key: ResourceKey) => void;
}
