export function estimateOutputTokenCost(
  outputTokens: number,
  outputUsdPerUnit: number,
  unitTokens: number,
): number {
  if (!Number.isFinite(outputTokens) || outputTokens < 0) {
    throw new RangeError("Output tokens must be a finite non-negative number");
  }
  if (!Number.isFinite(outputUsdPerUnit) || outputUsdPerUnit <= 0) {
    throw new RangeError("Output token price must be a finite positive number");
  }
  if (!Number.isFinite(unitTokens) || unitTokens <= 0) {
    throw new RangeError("Pricing unit must be a finite positive number");
  }
  return (outputTokens * outputUsdPerUnit) / unitTokens;
}
