import { describe, expect, it } from "vitest";

import {
  buildFamilyLineRuns,
  compareReasoningEfforts,
  REASONING_EFFORT_ORDER,
} from "../src/chart-series";

interface TestPoint {
  effort: string;
  family: string;
  id: string;
}

const point = (family: string, effort: string): TestPoint => ({
  effort,
  family,
  id: `${family}|${effort}`,
});

describe("reasoning effort order", () => {
  it("keeps the canonical effort progression in one place", () => {
    expect(REASONING_EFFORT_ORDER).toEqual(["none", "low", "medium", "high", "xhigh", "max"]);
    expect(["max", "low", "none"].toSorted(compareReasoningEfforts)).toEqual([
      "none",
      "low",
      "max",
    ]);
  });

  it("sorts unknown efforts deterministically after canonical efforts", () => {
    expect(["custom-z", "low", "custom-a"].toSorted(compareReasoningEfforts)).toEqual([
      "low",
      "custom-a",
      "custom-z",
    ]);
  });
});

describe("family line runs", () => {
  it("groups shuffled points and returns deterministic family and effort order", () => {
    const runs = buildFamilyLineRuns([
      point("Zulu", "medium"),
      point("Alpha", "high"),
      point("Zulu", "low"),
      point("Alpha", "medium"),
    ]);

    expect(runs.map((run) => [run.family, run.points.map((item) => item.effort)])).toEqual([
      ["Alpha", ["medium", "high"]],
      ["Zulu", ["low", "medium"]],
    ]);
  });

  it("splits at missing efforts and discards singleton runs", () => {
    const runs = buildFamilyLineRuns([
      point("Model", "none"),
      point("Model", "low"),
      point("Model", "high"),
      point("Model", "xhigh"),
      point("Model", "max"),
    ]);

    expect(runs.map((run) => run.points.map((item) => item.effort))).toEqual([
      ["none", "low"],
      ["high", "xhigh", "max"],
    ]);
  });

  it("bridges efforts removed after selection while preserving canonical order", () => {
    const selectedPoints = [
      point("Model", "low"),
      point("Model", "medium"),
      point("Model", "high"),
      point("Model", "xhigh"),
      point("Model", "max"),
    ];
    const runs = buildFamilyLineRuns([point("Model", "max"), point("Model", "low")], {
      continuityPoints: selectedPoints,
    });

    expect(runs.map((run) => run.points.map((item) => item.effort))).toEqual([["low", "max"]]);
  });

  it("does not bridge an effort absent from the selected configurations", () => {
    const runs = buildFamilyLineRuns([point("Model", "low"), point("Model", "max")], {
      continuityPoints: [
        point("Model", "low"),
        point("Model", "medium"),
        point("Model", "xhigh"),
        point("Model", "max"),
      ],
    });

    expect(runs).toEqual([]);
  });

  it("omits families with only one visible point", () => {
    expect(buildFamilyLineRuns([point("Alpha", "low"), point("Beta", "high")])).toEqual([]);
  });

  it("leaves unknown efforts out of line runs", () => {
    const runs = buildFamilyLineRuns([
      point("Model", "none"),
      point("Model", "low"),
      point("Model", "adaptive"),
      point("Model", "medium"),
    ]);

    expect(runs).toHaveLength(1);
    expect(runs[0]?.points.map((item) => item.effort)).toEqual(["none", "low", "medium"]);
  });
});
