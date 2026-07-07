import { describe, expect, it } from "vitest";

import { prepareTerminalBenchBar } from "../src/charts/terminal-bench-plot-model";

describe("TerminalBench Plot bar preparation", () => {
  it("prepares nine vertical bars sorted by score descending", () => {
    const model = prepareTerminalBenchBar({ containerWidth: 700 });
    const scores = model.items.map((item) => item.value);

    expect(model.items).toHaveLength(9);
    expect(model.width).toBe(780);
    expect(model.height).toBe(560);
    expect(scores).toEqual(scores.toSorted((first, second) => second - first));
    expect(model.items[0]?.categoryLabel).toContain("ma_ultra");
    expect(model.items.every((item) => item.tip.includes("Reasoning:"))).toBe(true);
  });

  it("keeps the source score domain and explicit ticks", () => {
    const model = prepareTerminalBenchBar({ containerWidth: 1000 });

    expect(model.width).toBe(1000);
    expect(model.valueAxis.domain).toEqual([50, 100]);
    expect(model.valueAxis.ticks).toEqual([50, 75, 100]);
    expect(model.valueAxis.formatTick(75)).toBe("75%");
  });
});
