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
