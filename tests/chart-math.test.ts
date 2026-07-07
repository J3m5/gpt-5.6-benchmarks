import { describe, expect, it } from "vitest";

import {
  createLinearScale,
  createLinearValueScale,
  createLogScale,
  paretoFrontier,
  ticksBetween,
} from "../src/chart-math";

describe("chart scales", () => {
  it("uses deterministic fallback domains for an empty selection", () => {
    expect(createLinearScale([], 40, 10)).toEqual({
      min: 0,
      max: 40,
      ticks: [0, 10, 20, 30, 40],
    });
    expect(createLogScale([], 0.1, 100, [0.1, 1, 10, 100])).toEqual({
      min: 0.1,
      max: 100,
      ticks: [0.1, 1, 10, 100],
    });
  });

  it("pads visible values while keeping percentage scores bounded", () => {
    const scale = createLinearScale([12, 18, 22], 40, 10);

    expect(scale.min).toBeLessThan(12);
    expect(scale.max).toBeGreaterThanOrEqual(22);
    expect(scale.min).toBeGreaterThanOrEqual(0);
    expect(scale.max).toBeLessThanOrEqual(100);
  });

  it("ends a percentage domain at the first nice tick covering the highest score", () => {
    const scale = createLinearScale([0.5, 14.4, 28.733850129198967], 30, 5);

    expect(scale.max).toBe(30);
    expect(scale.ticks.at(-1)).toBe(30);
    expect(scale.ticks).not.toContain(35);
  });

  it("ends a linear resource domain at the first nice tick covering the data", () => {
    const scale = createLinearValueScale(
      [1000, 50000, 120000],
      0,
      120000,
      [0, 20000, 40000, 60000, 80000, 100000, 120000],
    );

    expect(scale.min).toBeLessThanOrEqual(1000);
    expect(scale.max).toBe(120000);
    expect(scale.ticks.at(-1)).toBe(scale.max);

    const costScale = createLinearValueScale([0.12, 1.89], 0, 2.5, [0, 0.5, 1, 1.5, 2, 2.5]);
    expect(costScale.max).toBe(2);
    expect(costScale.ticks).toEqual([0, 0.5, 1, 1.5, 2]);
  });

  it("creates stable decimal ticks", () => {
    expect(ticksBetween(0, 0.3, 0.1)).toEqual([0, 0.1, 0.2, 0.3]);
  });
});

describe("Pareto frontier", () => {
  it("removes only points dominated by both a higher score and lower resource use", () => {
    const points = [
      { id: "best-cost", score: 15, cost: 1 },
      { id: "best-score", score: 25, cost: 3 },
      { id: "dominated", score: 10, cost: 4 },
      { id: "same-score", score: 25, cost: 5 },
    ];

    expect(
      paretoFrontier(
        points,
        (point) => point.score,
        (point) => point.cost,
      ).map((point) => point.id),
    ).toEqual(["best-cost", "best-score", "same-score"]);
  });

  it("can treat small resource differences as equivalent", () => {
    const points = [
      { id: "terra-low", score: 6.52885443583118, tokens: 5509.23608957795 },
      { id: "sol-low", score: 14.444444444444441, tokens: 5600.19293712317 },
    ];
    const frontier = (tolerance: number) =>
      paretoFrontier(
        points,
        (point) => point.score,
        (point) => point.tokens,
        tolerance,
      ).map((point) => point.id);

    expect(frontier(0)).toEqual(["terra-low", "sol-low"]);
    expect(frontier(0.02)).toEqual(["sol-low"]);
  });
});
