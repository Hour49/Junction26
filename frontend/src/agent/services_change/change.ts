// A proposal's services change (docs/specs/backend/services-model.md SV-28, SV-30), typed from the OpenAPI
// schema, and the pure helpers of its overlay. Places are page fractions of the storey picture (SV-6).
import type { components } from '../../api/schema';
import type { Point } from '../agent';

type Schemas = components['schemas'];

export type ServicesChange = Schemas['ServicesChange'];
export type Run = Schemas['RunChange'];
export type Fact = Schemas['FactChange'];
export type Check = Schemas['app__core__services__edit__Check'];

/** "pipe length, Heating 1, DN15: 38.50 → 43.00 m"; a count without decimals. */
export function factLine(f: Fact): string {
  const what = [f.what.replace(/_/g, ' '), f.system, f.size].filter(Boolean).join(', ');
  if (f.unit === 'count') return `${what}: ${String(f.before)} → ${String(f.after)}`;
  return `${what}: ${f.before.toFixed(2)} → ${f.after.toFixed(2)} ${f.unit}`;
}

/** A check's mark and its words: passed or failed is said, not left to the mark or a colour. */
export function checkLine(c: Check): { mark: string; text: string } {
  return c.ok ? { mark: '✓', text: `Passed: ${c.text}` } : { mark: '✕', text: `Failed: ${c.text}` };
}

const NEAR = 0.002; // page fraction: the server rounds places to 4 decimals

function onSegment(p: Point, a: Point, b: Point): boolean {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const len2 = dx * dx + dy * dy;
  const t =
    len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy) <= NEAR;
}

/** A polyline's straight pieces; a single point is a piece of no length. */
function pieces(line: Point[]): [Point, Point][] {
  return line.length === 1
    ? line.map((p): [Point, Point] => [p, p])
    : line.slice(1).map((q, i) => [line[i] ?? q, q]);
}

/** Every corner and every piece's middle of `run` lies on one of `others`. */
function covered(run: Run, others: Run[]): boolean {
  const probes = [
    ...run.polyline,
    ...pieces(run.polyline).map(([p, q]): Point => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2]),
  ];
  const segs = others.flatMap((o) => pieces(o.polyline));
  return probes.length > 0 && probes.every((p) => segs.some(([a, b]) => onSegment(p, a, b)));
}

/** The runs to draw. A main split where a branch now joins it is the same pipe: removed whole, added as halves
 * that lie wholly on it and together cover it; neither the whole nor its halves are drawn as changed. A new run
 * that only starts along a removed one (a reroute) is drawn. */
export function shownRuns(c: ServicesChange): { removed: Run[]; added: Run[] } {
  const same = new Set<string>();
  for (const r of c.removed) {
    const halves = c.added.filter((a) => covered(a, [r]));
    if (halves.length > 0 && covered(r, halves)) for (const x of [r, ...halves]) same.add(x.id);
  }
  return {
    removed: c.removed.filter((r) => !same.has(r.id)),
    added: c.added.filter((a) => !same.has(a.id)),
  };
}

/** "41%": a page fraction as an SVG length on the picture. */
export const pct = (v: number) => `${String(Math.round(v * 10000) / 100)}%`;

const ZOOM_MARGIN = 0.05; // page fraction around the change: the room's walls stay in view
const ZOOM_MIN = 0.2; // the close-up is at least a fifth of the page: 5x at most, a room and its neighbours

/** The close-up (#566): a square of page fractions (so it has the picture's own shape) around the moved
 * terminals and the shown runs, with a margin, inside the page. The whole page when nothing has a place. */
export function zoomBox(
  c: ServicesChange,
  runs: { removed: Run[]; added: Run[] },
): { x: number; y: number; s: number } {
  const points = [
    ...c.moved.flatMap((m) => [m.from, m.to].filter((p): p is Point => p != null)),
    ...[...runs.removed, ...runs.added].flatMap((r) => r.polyline),
  ];
  if (points.length === 0) return { x: 0, y: 0, s: 1 };
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const s = Math.min(1, Math.max(ZOOM_MIN, x1 - x0 + 2 * ZOOM_MARGIN, y1 - y0 + 2 * ZOOM_MARGIN));
  const inside = (mid: number) => Math.min(Math.max(mid - s / 2, 0), 1 - s);
  return { x: inside((x0 + x1) / 2), y: inside((y0 + y1) / 2), s };
}
