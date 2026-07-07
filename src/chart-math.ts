export interface ChartScale {
  min: number;
  max: number;
  ticks: number[];
}

function cleanNumber(value: number): number {
  return Number(value.toPrecision(12));
}

function niceStep(range: number, targetIntervals = 6): number {
  const roughStep = range / targetIntervals;
  if (!(roughStep > 0)) {
    return 1;
  }

  const power = 10 ** Math.floor(Math.log10(roughStep));
  const error = roughStep / power;
  const factor =
    error >= Math.sqrt(50) ? 10 : error >= Math.sqrt(10) ? 5 : error >= Math.sqrt(2) ? 2 : 1;

  return factor * power;
}

export function ticksBetween(min: number, max: number, step: number): number[] {
  const ticks: number[] = [];
  const first = Math.ceil((min - step * 1e-9) / step) * step;

  for (let value = first; value <= max + step * 1e-9; value += step) {
    ticks.push(cleanNumber(value));
  }

  return ticks;
}

export function createLinearScale(
  values: number[],
  fallbackMax: number,
  fallbackStep: number,
): ChartScale {
  if (values.length === 0) {
    return {
      min: 0,
      max: fallbackMax,
      ticks: ticksBetween(0, fallbackMax, fallbackStep),
    };
  }

  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const dataRange = dataMax - dataMin;
  const padding = dataRange > 0 ? dataRange * 0.12 : Math.max(Math.abs(dataMax) * 0.08, 1);
  const paddedMin = Math.max(0, dataMin - padding);
  const paddedMax = Math.min(100, dataMax + padding);
  const step = niceStep(paddedMax - paddedMin);
  let min = Math.max(0, Math.floor(paddedMin / step) * step);
  let max = Math.min(100, Math.ceil(dataMax / step) * step);

  if (max <= min) {
    min = Math.max(0, min - step);
    max = Math.min(100, max + step);
  }

  return {
    min: cleanNumber(min),
    max: cleanNumber(max),
    ticks: ticksBetween(min, max, step),
  };
}

export function createLinearValueScale(
  values: number[],
  fallbackMin: number,
  fallbackMax: number,
  fallbackTicks: number[],
): ChartScale {
  if (values.length === 0) {
    return {
      min: fallbackMin,
      max: fallbackMax,
      ticks: fallbackTicks,
    };
  }

  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const dataRange = dataMax - dataMin;
  const padding = dataRange > 0 ? dataRange * 0.08 : Math.max(Math.abs(dataMax) * 0.08, 1);
  const paddedMin = Math.max(0, dataMin - padding);
  const paddedMax = dataMax + padding;
  const step = niceStep(paddedMax - paddedMin);
  let min = Math.max(0, Math.floor(paddedMin / step) * step);
  let max = Math.ceil(dataMax / step) * step;

  if (max <= min) {
    min = Math.max(0, min - step);
    max += step;
  }

  return {
    min: cleanNumber(min),
    max: cleanNumber(max),
    ticks: ticksBetween(min, max, step),
  };
}

export function createLogScale(
  values: number[],
  fallbackMin: number,
  fallbackMax: number,
  fallbackTicks: number[],
): ChartScale {
  if (values.length === 0) {
    return {
      min: fallbackMin,
      max: fallbackMax,
      ticks: fallbackTicks,
    };
  }

  const logarithms = values.map((value) => Math.log10(value));
  const dataMin = Math.min(...logarithms);
  const dataMax = Math.max(...logarithms);
  const dataRange = dataMax - dataMin;
  const padding = dataRange > 0 ? Math.max(dataRange * 0.1, 0.04) : 0.3;
  const minLog = dataMin - padding;
  const maxLog = dataMax + padding;
  const ticks: number[] = [];

  for (let exponent = Math.floor(minLog) - 1; exponent <= Math.ceil(maxLog) + 1; exponent += 1) {
    [1, 2, 5].forEach((factor) => {
      const value = factor * 10 ** exponent;
      const logarithm = Math.log10(value);
      if (logarithm >= minLog - 1e-9 && logarithm <= maxLog + 1e-9) {
        ticks.push(cleanNumber(value));
      }
    });
  }

  if (ticks.length < 3) {
    const step = niceStep(maxLog - minLog, 4);
    ticks.splice(
      0,
      ticks.length,
      ...ticksBetween(minLog, maxLog, step).map((value) => cleanNumber(10 ** value)),
    );
  }

  return {
    min: 10 ** minLog,
    max: 10 ** maxLog,
    ticks,
  };
}

export function paretoFrontier<T>(
  points: T[],
  score: (point: T) => number,
  resource: (point: T) => number,
  resourceToleranceRatio = 0,
): T[] {
  if (resourceToleranceRatio < 0) {
    throw new RangeError("Pareto resource tolerance must not be negative");
  }

  return points.filter(
    (candidate) =>
      !points.some(
        (other) =>
          score(other) > score(candidate) &&
          resource(other) < resource(candidate) * (1 + resourceToleranceRatio),
      ),
  );
}
