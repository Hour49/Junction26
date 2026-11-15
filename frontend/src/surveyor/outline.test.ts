// R4-B8: "Add a missed one" refuses a click outside the plan, when the takeoff knows where the plan's rooms are.
import { describe, expect, it } from 'vitest';
import type { MarkView, Takeoff } from '../api';
import { onPlan } from './outline';

const mark = (box: [number, number, number, number], polygon = false, page = 1) =>
  ({
    id: 'm',
    n: 1,
    page,
    box,
    polygon: polygon ? [[box[0], box[1]]] : null,
  }) as unknown as MarkView;
const takeoffOf = (...marks: MarkView[]) =>
  ({ quantities: [{ key: 'k', marks }] }) as unknown as Takeoff;

describe('onPlan', () => {
  const t = takeoffOf(
    mark([0.2, 0.2, 0.5, 0.5], true),
    mark([0.5, 0.3, 0.8, 0.6], true),
    mark([0.3, 0.18, 0.4, 0.19]),
  );
  it('a click inside the rooms and marks, or within 3% of them, is on the plan', () => {
    expect(onPlan(t, 1, [0.6, 0.4, 0.62, 0.42])).toBe(true);
    expect(onPlan(t, 1, [0.82, 0.62, 0.83, 0.63])).toBe(true); // a window on the outer wall
  });
  it('a click well outside them is not', () => {
    expect(onPlan(t, 1, [0.3, 0.8, 0.33, 0.83])).toBe(false);
    expect(onPlan(t, 1, [0.9, 0.1, 0.93, 0.13])).toBe(false);
  });
  it('without a room outline on that page the plan is unknown: every click counts', () => {
    expect(onPlan(takeoffOf(mark([0.2, 0.2, 0.3, 0.3])), 1, [0.9, 0.9, 0.95, 0.95])).toBe(true);
    expect(onPlan(t, 2, [0.9, 0.9, 0.95, 0.95])).toBe(true);
  });
});
