interface LabelOffset {
  labelDx: number;
  labelDy: number;
}

export interface LabelOffsetGroup<T> {
  dx: number;
  dy: number;
  points: T[];
}

export function groupLabelOffsets<T extends LabelOffset>(
  points: readonly T[],
): LabelOffsetGroup<T>[] {
  const groups = new Map<string, LabelOffsetGroup<T>>();
  points.forEach((point) => {
    const key = `${point.labelDx}\u0000${point.labelDy}`;
    const group = groups.get(key) ?? {
      dx: point.labelDx,
      dy: point.labelDy,
      points: [],
    };
    group.points.push(point);
    groups.set(key, group);
  });
  return [...groups.values()];
}
