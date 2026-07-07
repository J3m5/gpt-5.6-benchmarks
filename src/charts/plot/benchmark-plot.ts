import {
  axisX,
  axisY,
  barY,
  dot,
  gridX,
  gridY,
  line,
  plot,
  rect,
  ruleY,
  text,
} from "@observablehq/plot";
import type { Markish } from "@observablehq/plot";

import { byId } from "../../utils/dom";
import type { BenchmarkPlotRenderer, PlotBarModel, PlotScatterModel } from "./types";
import { groupLabelOffsets } from "./label-groups";

const svgNamespace = "http://www.w3.org/2000/svg";

interface PlotRendererOptions {
  containerId: string;
}

interface PlotRootModel {
  id: string;
  width: number;
  height: number;
  titleId: string;
  descriptionId: string;
  title: string;
  description: string;
}

function svgElement<K extends keyof SVGElementTagNameMap>(
  document: Document,
  name: K,
): SVGElementTagNameMap[K] {
  return document.createElementNS(svgNamespace, name);
}

function decorateRoot(svg: SVGSVGElement, model: PlotRootModel): void {
  svg.id = model.id;
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", `${model.titleId} ${model.descriptionId}`);
  svg.setAttribute("viewBox", `0 0 ${model.width} ${model.height}`);
  svg.style.width = `${model.width}px`;
  svg.style.height = `${model.height}px`;

  const title = svgElement(document, "title");
  title.id = model.titleId;
  title.textContent = model.title;
  const description = svgElement(document, "desc");
  description.id = model.descriptionId;
  description.textContent = model.description;
  svg.prepend(title, description);
}

function replacePlot(container: HTMLElement, svg: SVGSVGElement): void {
  container.replaceChildren(svg);
}

function gridMarks(
  xAxis: PlotScatterModel<unknown>["xAxis"],
  yAxis: PlotScatterModel<unknown>["yAxis"],
  yMinimum: number,
): Markish[] {
  const marks: Markish[] = [];
  const xTicks = xAxis.ticks;
  const yTicks = yAxis.ticks;
  const gridOptions = {
    stroke: "#eef0f2",
    strokeWidth: 0.65,
    strokeOpacity: 1,
    className: "benchmark-grid-minor",
    ariaHidden: "true",
    pointerEvents: "none",
  };
  marks.push(
    xTicks === undefined
      ? gridX({
          ...(xAxis.interval === undefined ? {} : { interval: xAxis.interval }),
          ...gridOptions,
        })
      : Array.isArray(xTicks) || typeof xTicks !== "number"
        ? gridX(xTicks, gridOptions)
        : gridX({ ticks: xTicks, ...gridOptions }),
  );
  const yGrid =
    Array.isArray(yTicks) || (yTicks !== undefined && typeof yTicks !== "number")
      ? gridY(
          [...yTicks].filter((tick) => tick !== yMinimum),
          gridOptions,
        )
      : gridY({
          ...(yTicks === undefined ? {} : { ticks: yTicks }),
          ...(yAxis.interval === undefined ? {} : { interval: yAxis.interval }),
          ...gridOptions,
        });
  marks.push(
    yGrid,
    ruleY([yMinimum], {
      stroke: "#d4d7dc",
      strokeWidth: 0.9,
      strokeOpacity: 1,
      className: "benchmark-grid-axis",
      ariaHidden: "true",
      pointerEvents: "none",
    }),
  );
  return marks;
}

function scatterMarks<T>(model: PlotScatterModel<T>): Markish[] {
  const marks: Markish[] = [];
  if (model.showQuadrants) {
    marks.push(
      rect(
        [
          {
            x1: model.xAxis.domain[0],
            x2: model.quadrantX,
            y1: model.quadrantY,
            y2: model.yAxis.domain[1],
          },
        ],
        {
          x1: "x1",
          x2: "x2",
          y1: "y1",
          y2: "y2",
          fill: "#e2f7e4",
          stroke: "none",
          className: "benchmark-quadrant-attractive",
          ariaHidden: "true",
          pointerEvents: "none",
        },
      ),
      rect(
        [
          {
            x1: model.quadrantX,
            x2: model.xAxis.domain[1],
            y1: model.yAxis.domain[0],
            y2: model.quadrantY,
          },
        ],
        {
          x1: "x1",
          x2: "x2",
          y1: "y1",
          y2: "y2",
          fill: "#f7f7f7",
          stroke: "none",
          className: "benchmark-quadrant-opposite",
          ariaHidden: "true",
          pointerEvents: "none",
        },
      ),
    );
  }
  marks.push(
    ...gridMarks(model.xAxis, model.yAxis, model.yAxis.domain[0]),
    axisX({
      ...(model.xAxis.ticks === undefined ? {} : { ticks: model.xAxis.ticks }),
      ...(model.xAxis.interval === undefined ? {} : { interval: model.xAxis.interval }),
      tickFormat: model.xAxis.formatTick,
      label: model.xAxis.label,
      labelAnchor: "center",
      labelArrow: "none",
      tickSize: 0,
      tickPadding: 12,
    }),
    axisY({
      ...(model.yAxis.ticks === undefined ? {} : { ticks: model.yAxis.ticks }),
      ...(model.yAxis.interval === undefined ? {} : { interval: model.yAxis.interval }),
      tickFormat: model.yAxis.formatTick,
      label: model.yAxis.label,
      labelAnchor: "center",
      labelArrow: "none",
      tickSize: 0,
      tickPadding: 10,
    }),
  );

  if (model.referenceLines.length > 0) {
    marks.push(
      ruleY(model.referenceLines, {
        x1: "x1",
        x2: "x2",
        y: "y",
        stroke: "color",
        strokeWidth: 1.5,
        strokeDasharray: "2 7",
        strokeLinecap: "round",
        ariaLabel: "ariaLabel",
        className: "benchmark-reference-line",
        pointerEvents: "none",
      }),
      text(model.referenceLines, {
        x: "x2",
        y: "y",
        text: "label",
        dy: -8,
        fill: "color",
        fontSize: 11,
        fontWeight: 650,
        textAnchor: "end",
        className: "benchmark-reference-label",
        pointerEvents: "none",
        ariaHidden: "true",
      }),
    );
  }

  if (model.showFamilyLines) {
    model.familySeries.forEach((series) => {
      marks.push(
        line(series.points, {
          x: "x",
          y: "y",
          z: null,
          stroke: series.color,
          strokeWidth: 1.25,
          strokeOpacity: 0.45,
          strokeLinecap: "round",
          strokeLinejoin: "round",
          className: "benchmark-family-line",
          pointerEvents: "none",
          ariaHidden: "true",
        }),
      );
    });
  }

  marks.push(
    dot(model.points, {
      x: "x",
      y: "y",
      r: 6,
      fill: "color",
      stroke: "none",
      symbol: (point: PlotScatterModel<T>["points"][number]) => point.shape,
      ariaLabel: "ariaLabel",
      title: "tip",
      tip: true,
      className: "benchmark-point",
      sort: null,
    }),
  );

  if (model.showLabels) {
    groupLabelOffsets(model.points).forEach((group) => {
      marks.push(
        text(group.points, {
          x: "x",
          y: "y",
          text: "label",
          dx: group.dx,
          dy: group.dy,
          fill: "#34363a",
          stroke: "#fff",
          strokeWidth: 4,
          strokeLinejoin: "round",
          paintOrder: "stroke",
          fontSize: 10,
          fontWeight: 400,
          textAnchor: "start",
          className: "benchmark-point-label",
          ariaLabel: "id",
          pointerEvents: "none",
          ariaHidden: "true",
        }),
      );
    });
  }
  return marks;
}

function chartSvg(chart: ReturnType<typeof plot>): SVGSVGElement {
  if (!(chart instanceof SVGSVGElement)) {
    throw new TypeError("Observable Plot returned a non-SVG chart");
  }
  return chart;
}

export function createPlotScatterRenderer<T>({
  containerId,
}: PlotRendererOptions): BenchmarkPlotRenderer<PlotScatterModel<T>> {
  const container = byId(containerId, HTMLDivElement);
  let lastModel: PlotScatterModel<T> | undefined;

  function render(model: PlotScatterModel<T>): void {
    lastModel = model;
    const svg = chartSvg(
      plot({
        width: model.width,
        height: model.height,
        marginTop: model.margins.top,
        marginRight: model.margins.right,
        marginBottom: model.margins.bottom,
        marginLeft: model.margins.left,
        x: {
          type: model.xAxis.scale,
          domain: model.xAxis.domain,
          axis: null,
          nice: false,
        },
        y: {
          type: model.yAxis.scale,
          domain: model.yAxis.domain,
          axis: null,
          nice: false,
        },
        marks: scatterMarks(model),
      }),
    );
    svg.classList.add("benchmark-scatter-chart", "benchmark-plot");
    decorateRoot(svg, model);
    svg.dataset.xMin = String(model.xAxis.domain[0]);
    svg.dataset.xMax = String(model.xAxis.domain[1]);
    svg.dataset.yMin = String(model.yAxis.domain[0]);
    svg.dataset.yMax = String(model.yAxis.domain[1]);
    if (Array.isArray(model.xAxis.ticks)) {
      svg.dataset.xTicks = JSON.stringify(model.xAxis.ticks);
    }
    if (Array.isArray(model.yAxis.ticks)) {
      svg.dataset.yTicks = JSON.stringify(model.yAxis.ticks);
    }
    svg.dataset.quadrantX = String(model.quadrantX);
    svg.dataset.quadrantY = String(model.quadrantY);
    svg.dataset.xMetric = model.metric;
    svg.dataset.xScale = model.xAxis.scale;
    svg.dataset.pointLabels = String(model.showLabels);
    svg.dataset.familyLines = String(model.showFamilyLines);
    svg.dataset.pareto = String(model.pareto);
    replacePlot(container, svg);
  }

  return {
    render,
    resize() {
      if (lastModel) {
        render(lastModel);
      }
    },
  };
}

function barTickOptions(ticks: PlotBarModel<unknown>["valueAxis"]["ticks"]) {
  return ticks === undefined ? { ticks: 5 } : { ticks };
}

function barGridMarks<T>(model: PlotBarModel<T>, baseline: number): Markish[] {
  const ticks = model.valueAxis.ticks;
  const gridOptions = {
    stroke: "#eef0f2",
    strokeWidth: 0.65,
    strokeOpacity: 1,
    className: "benchmark-grid-minor",
    ariaHidden: "true",
    pointerEvents: "none",
  };
  const grid =
    Array.isArray(ticks) || (ticks !== undefined && typeof ticks !== "number")
      ? gridY(
          [...ticks].filter((tick) => tick !== baseline),
          gridOptions,
        )
      : gridY({
          ...gridOptions,
          ...barTickOptions(ticks),
        });

  return [
    grid,
    ruleY([baseline], {
      stroke: "#d4d7dc",
      strokeWidth: 0.9,
      strokeOpacity: 1,
      className: "benchmark-grid-axis",
      ariaHidden: "true",
      pointerEvents: "none",
    }),
  ];
}

function barMarks<T>(model: PlotBarModel<T>): Markish[] {
  const baseline = model.valueAxis.baseline ?? model.valueAxis.domain?.[0] ?? 0;
  return [
    ...barGridMarks(model, baseline),
    axisY({
      ...barTickOptions(model.valueAxis.ticks),
      tickFormat: model.valueAxis.formatTick,
      label: model.valueAxis.label,
      labelAnchor: "center",
      labelArrow: "none",
      tickSize: 0,
      tickPadding: 10,
    }),
    barY(model.items, {
      x: "categoryLabel",
      y1: baseline,
      y2: "value",
      insetLeft: 4,
      insetRight: 4,
      fill: "color",
      stroke: "none",
      rx: 2,
      ariaLabel: "ariaLabel",
      title: "tip",
      tip: "x",
      className: "benchmark-bar",
    }),
    text(model.items, {
      x: "categoryLabel",
      y: "value",
      text: "valueLabel",
      dy: -9,
      fill: "#34363a",
      fontSize: 11,
      fontWeight: 650,
      textAnchor: "middle",
      className: "benchmark-bar-value",
      pointerEvents: "none",
      ariaHidden: "true",
    }),
    text(model.items, {
      x: "categoryLabel",
      y: baseline,
      text: "categoryLabel",
      dy: 24,
      fill: "color",
      fontSize: 11,
      fontWeight: 650,
      textAnchor: "end",
      rotate: -48,
      className: "benchmark-bar-category",
      pointerEvents: "none",
      ariaHidden: "true",
    }),
  ];
}

export function createPlotBarRenderer<T>({
  containerId,
}: PlotRendererOptions): BenchmarkPlotRenderer<PlotBarModel<T>> {
  const container = byId(containerId, HTMLDivElement);
  let lastModel: PlotBarModel<T> | undefined;

  function render(model: PlotBarModel<T>): void {
    lastModel = model;
    const svg = chartSvg(
      plot({
        width: model.width,
        height: model.height,
        marginTop: model.margins.top,
        marginRight: model.margins.right,
        marginBottom: model.margins.bottom,
        marginLeft: model.margins.left,
        x: {
          type: "band",
          domain: model.items.map((item) => item.categoryLabel),
          axis: null,
          padding: 0.2,
        },
        y: {
          type: model.valueAxis.scale,
          domain: model.valueAxis.domain,
          axis: null,
          nice: model.valueAxis.nice ?? model.valueAxis.domain === undefined,
          zero: model.valueAxis.zero ?? model.valueAxis.domain === undefined,
        },
        marks: barMarks(model),
      }),
    );
    svg.classList.add("benchmark-plot", "benchmark-bar-chart");
    decorateRoot(svg, model);
    if (model.valueAxis.domain) {
      svg.dataset.yMin = String(model.valueAxis.domain[0]);
      svg.dataset.yMax = String(model.valueAxis.domain[1]);
    }
    if (Array.isArray(model.valueAxis.ticks)) {
      svg.dataset.yTicks = JSON.stringify(model.valueAxis.ticks);
    }
    svg.dataset.metric = model.metric;
    replacePlot(container, svg);
  }

  return {
    render,
    resize() {
      if (lastModel) {
        render(lastModel);
      }
    },
  };
}
