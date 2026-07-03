export const integerFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

export function formatCost(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function formatEstimatedCost(value: number): string {
  const decimals = value < 1 ? 3 : 2;
  return `$${value.toFixed(decimals).replace(/\.?0+$/, "")}`;
}

export function formatPercent(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

export function formatLatency(value: number): string {
  return `${value.toFixed(value < 10 ? 2 : 1)} min`;
}

export function formatAxisCost(value: number): string {
  const decimals = value < 0.1 ? 3 : value < 1 ? 2 : value < 10 ? 1 : 0;
  const formatted = value.toFixed(decimals);
  return `$${decimals > 0 ? formatted.replace(/\.?0+$/, "") : formatted}`;
}

export function formatAxisPercent(value: number): string {
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

export function formatAxisNumber(value: number): string {
  if (value >= 1000000) {
    return `${Number((value / 1000000).toPrecision(3))}M`;
  }
  if (value >= 1000) {
    return `${Number((value / 1000).toPrecision(3))}k`;
  }
  return `${Number(value.toPrecision(3))}`;
}
