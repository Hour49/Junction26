// R4-B8: where the plan is, as far as the takeoff knows: no outline of the building comes from the server.
import type { Takeoff } from '../api';

type Box = [number, number, number, number];
const MARGIN = 0.03; // of the page: a door or window on the outer wall sits just outside the rooms

/** Whether a click (its box, page fractions) falls on the plan: within the extent of every mark on that page, plus
 * a margin. Known only when a room outline is on the page; otherwise every click counts. */
export function onPlan(takeoff: Takeoff, page: number, box: Box): boolean {
  const marks = takeoff.quantities.flatMap((q) => q.marks).filter((m) => m.page === page);
  if (!marks.some((m) => m.polygon)) return true;
  const boxes = marks.map((m) => m.box);
  const [x0, y0] = [Math.min(...boxes.map((b) => b[0])), Math.min(...boxes.map((b) => b[1]))];
  const [x1, y1] = [Math.max(...boxes.map((b) => b[2])), Math.max(...boxes.map((b) => b[3]))];
  const [cx, cy] = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
  return cx >= x0 - MARGIN && cx <= x1 + MARGIN && cy >= y0 - MARGIN && cy <= y1 + MARGIN;
}
