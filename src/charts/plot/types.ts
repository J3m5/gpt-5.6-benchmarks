export type PlotScaleKind = "linear" | "log";

export interface PlotMargins {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface PlotAxisModel {
  scale: PlotScaleKind;
  domain: readonly [number, number];
  ticks?: number | readonly number[];
  interval?: number;
  label: string;
  formatTick: (value: number) => string;
}

export interface PlotBarAxisModel {
  scale: PlotScaleKind;
  domain?: readonly [number, number];
  ticks?: number | readonly number[];
  baseline?: number;
  nice?: boolean | number;
  zero?: boolean;
  label: string;
  formatTick: (value: number) => string;
}

export interface PlotScatterPoint<T> {
  datum: T;
  id: string;
  family: string;
  metric: string;
  effort: string;
  x: number;
  y: number;
  color: string;
  label: string;
  shape: "circle" | "diamond" | "square";
  labelDx: number;
  labelDy: number;
  ariaLabel: string;
  tip: string;
}

export interface PlotReferenceLine {
  id: string;
  label: string;
  x1: number;
  x2: number;
  y: number;
  color: string;
  ariaLabel: string;
}

export interface PlotFamilySeries<T> {
  family: string;
  color: string;
  points: readonly PlotScatterPoint<T>[];
}

export interface PlotScatterModel<T> {
  id: string;
  metric: string;
  width: number;
  height: number;
  margins: PlotMargins;
  titleId: string;
  descriptionId: string;
  title: string;
  description: string;
  xAxis: PlotAxisModel;
  yAxis: PlotAxisModel;
  points: readonly PlotScatterPoint<T>[];
  familySeries: readonly PlotFamilySeries<T>[];
  referenceLines: readonly PlotReferenceLine[];
  quadrantX: number;
  quadrantY: number;
  showQuadrants: boolean;
  showLabels: boolean;
  showFamilyLines: boolean;
  pareto: boolean;
}

export interface PlotBarItem<T> {
  datum: T;
  id: string;
  family: string;
  metric: string;
  effort: string;
  value: number;
  color: string;
  categoryLabel: string;
  valueLabel: string;
  ariaLabel: string;
  tip: string;
}

export interface PlotBarModel<T> {
  id: string;
  metric: string;
  width: number;
  height: number;
  margins: PlotMargins;
  titleId: string;
  descriptionId: string;
  title: string;
  description: string;
  valueAxis: PlotBarAxisModel;
  items: readonly PlotBarItem<T>[];
}

export interface BenchmarkPlotRenderer<M> {
  render: (model: M) => void;
  resize: () => void;
}
