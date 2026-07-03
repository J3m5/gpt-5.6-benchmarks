export const REASONING_EFFORT_ORDER = ["none", "low", "medium", "high", "xhigh", "max"] as const;

interface FamilySeriesPoint {
  effort: string;
  family: string;
  id: string;
}

export interface FamilyLineRun<T extends FamilySeriesPoint> {
  family: string;
  points: T[];
}

export interface FamilyLineRunOptions {
  continuityPoints?: readonly FamilySeriesPoint[];
}

const effortRanks = new Map<string, number>(
  REASONING_EFFORT_ORDER.map((effort, index) => [effort, index]),
);

function hasAllIntermediateRanks(
  ranks: ReadonlySet<number> | undefined,
  start: number,
  end: number,
): boolean {
  if (!ranks || end <= start + 1) {
    return false;
  }
  for (let rank = start + 1; rank < end; rank += 1) {
    if (!ranks.has(rank)) {
      return false;
    }
  }
  return true;
}

export function compareReasoningEfforts(first: string, second: string): number {
  const firstRank = effortRanks.get(first);
  const secondRank = effortRanks.get(second);

  if (firstRank === undefined && secondRank === undefined) {
    return first.localeCompare(second);
  }
  if (firstRank === undefined) {
    return 1;
  }
  if (secondRank === undefined) {
    return -1;
  }
  return firstRank - secondRank;
}

export function buildFamilyLineRuns<T extends FamilySeriesPoint>(
  points: readonly T[],
  options: FamilyLineRunOptions = {},
): FamilyLineRun<T>[] {
  const groupedPoints = new Map<string, T[]>();
  const continuityRanks = new Map<string, Set<number>>();

  (options.continuityPoints ?? points).forEach((point) => {
    const rank = effortRanks.get(point.effort);
    if (rank === undefined) {
      return;
    }
    const familyRanks = continuityRanks.get(point.family) ?? new Set<number>();
    familyRanks.add(rank);
    continuityRanks.set(point.family, familyRanks);
  });

  points.forEach((point) => {
    if (!effortRanks.has(point.effort)) {
      return;
    }
    const familyPoints = groupedPoints.get(point.family) ?? [];
    familyPoints.push(point);
    groupedPoints.set(point.family, familyPoints);
  });

  const runs: FamilyLineRun<T>[] = [];
  [...groupedPoints.entries()]
    .toSorted(([firstFamily], [secondFamily]) => firstFamily.localeCompare(secondFamily))
    .forEach(([family, familyPoints]) => {
      const orderedPoints = familyPoints.toSorted(
        (first, second) =>
          compareReasoningEfforts(first.effort, second.effort) || first.id.localeCompare(second.id),
      );
      let currentRun: T[] = [];
      let previousRank: number | undefined;

      orderedPoints.forEach((point) => {
        const rank = effortRanks.get(point.effort);
        if (rank === undefined) {
          return;
        }
        const intermediateEffortsWereSelected =
          previousRank !== undefined &&
          hasAllIntermediateRanks(continuityRanks.get(family), previousRank, rank);
        if (
          previousRank === undefined ||
          rank === previousRank + 1 ||
          intermediateEffortsWereSelected
        ) {
          currentRun.push(point);
        } else {
          if (currentRun.length >= 2) {
            runs.push({ family, points: currentRun });
          }
          currentRun = [point];
        }
        previousRank = rank;
      });

      if (currentRun.length >= 2) {
        runs.push({ family, points: currentRun });
      }
    });

  return runs;
}
