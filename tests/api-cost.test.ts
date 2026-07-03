import { describe, expect, it } from "vitest";

import { estimateOutputTokenCost } from "../src/api-cost";

describe("API output cost estimation", () => {
  it("converts generated tokens and a per-million rate to USD", () => {
    expect(estimateOutputTokenCost(33_168.297416020665, 30, 1_000_000)).toBeCloseTo(
      0.9950489224806199,
      12,
    );
  });

  it("rejects invalid pricing inputs", () => {
    expect(() => estimateOutputTokenCost(-1, 30, 1_000_000)).toThrow(RangeError);
    expect(() => estimateOutputTokenCost(1000, 0, 1_000_000)).toThrow(RangeError);
    expect(() => estimateOutputTokenCost(1000, 30, 0)).toThrow(RangeError);
  });
});
