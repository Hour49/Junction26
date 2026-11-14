// The agent chat's turn (decision 0013, docs/specs/agent-chat.md §3), typed from the OpenAPI schema, and its pure helpers.
import type { components } from '../api/schema';

type Schemas = components['schemas'];

export type Box = [number, number, number, number];
export type Point = [number, number];

export type ChatTurn = Schemas['ChatTurn'];
export type ChatRequest = Schemas['ChatRequest'];
export type Evidence = Schemas['ChatEvidence'];
/** ADR 0011 confidence level of an ask_drawings answer part. */
export type Level = Schemas['app__core__agent__model__Level'];
export type Step = Schemas['Step'];
export type Proposal = Schemas['Proposal'];
export type GeomItem = Schemas['Item'];
/** `area_before_m2` 0: a room the edit places (propose_room), or a new part of a split room. */
export type RoomChange = Schemas['RoomChange'];
export type Selection = Schemas['Selection'];

/** The text cut into plain runs and `[n]` citations of a source the turn lists; other brackets stay text. */
export function splitCites(text: string, ns: number[]): (string | number)[] {
  const out: (string | number)[] = [];
  for (const part of text.split(/(\[\d+\])/)) {
    const n = /^\[(\d+)\]$/.exec(part)?.[1];
    const prev = out.length - 1;
    if (n !== undefined && ns.includes(Number(n))) out.push(Number(n));
    else if (typeof out[prev] === 'string') out[prev] += part;
    else if (part) out.push(part);
  }
  return out;
}

const two = (v: number) => v.toFixed(2);

/** "+0.52 m²" / "−1.20 m²" / "±0.00 m²". */
export function signedArea(d: number): string {
  const r = Math.round(d * 100) / 100;
  if (r === 0) return '±0.00 m²';
  return `${r > 0 ? '+' : '−'}${two(Math.abs(r))} m²`;
}

/** "24.04 → 24.56 m²", or "new, 3.40 m²" for a room that did not exist. */
export function areaChange(r: RoomChange): string {
  if (r.area_before_m2 === 0) return `new, ${two(r.area_after_m2)} m²`;
  return `${two(r.area_before_m2)} → ${two(r.area_after_m2)} m²`;
}

/** One line per removed and added item and per room, rooms with the difference (AC-32 change list). */
export function changeLines(p: Proposal): string[] {
  return [
    ...p.removed.map((g) => `Removed: ${g.label}`),
    ...p.added.map((g) => `New: ${g.label}`),
    ...p.rooms.map((r) =>
      r.area_before_m2 === 0
        ? `${r.label}: ${areaChange(r)}`
        : `${r.label}: ${areaChange(r)} (${signedArea(r.area_after_m2 - r.area_before_m2)})`,
    ),
  ];
}

/** "2 steps · 1.2 s · $0.01" (AC-31 disclosure). */
export function stepsSummary(t: ChatTurn): string {
  const n = t.steps.length;
  const cost = t.cost_usd === 0 ? '$0' : t.cost_usd < 0.01 ? '<$0.01' : `$${t.cost_usd.toFixed(2)}`;
  return `${String(n)} ${n === 1 ? 'step' : 'steps'} · ${t.latency_s.toFixed(1)} s · ${cost}`;
}

/** Points of a page-fraction polygon for an SVG `points` attribute. */
export const pointsOf = (poly: Point[]) =>
  poly.map(([x, y]) => `${String(x)},${String(y)}`).join(' ');

/** The centre of a polygon's bounding box, for its badge. */
export function centreOf(poly: Point[]): Point {
  const xs = poly.map((p) => p[0]);
  const ys = poly.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

/** The bounding box of every polygon the proposal draws, in page fractions. */
export function extentOf(p: Proposal): Box {
  const pts = [...p.removed, ...p.added, ...p.rooms].flatMap((g) => g.polygon);
  if (pts.length === 0) return [0, 0, 1, 1];
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

/** The viewer zoom (1, 2 or 4) that shows a change of this extent big enough on a whole sheet. */
export function zoomFor([x0, y0, x1, y1]: Box): 1 | 2 | 4 {
  const side = Math.max(x1 - x0, y1 - y0);
  return side <= 0.2 ? 4 : side <= 0.45 ? 2 : 1;
}

/** A room of the drawing model (`GET /api/drawings/{id}/model`, extraction_v1): its id is the plan tools' room id. */
export interface ModelRoom {
  id: string;
  type: string;
  label?: string | null;
  page: number;
  polygon?: Point[] | null;
  box: number[];
}

/** The rooms of an extraction_v1 document; none when it has no `rooms` list. */
export function roomsOf(model: Record<string, unknown>): ModelRoom[] {
  return Array.isArray(model.rooms) ? (model.rooms as ModelRoom[]) : [];
}

/** Even-odd ray cast: is the point inside the polygon. */
export function inPolygon([x, y]: Point, poly: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i] as Point;
    const [xj, yj] = poly[j] as Point;
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The room under a point of a page: its polygon, or its box when it has no polygon. */
export function roomAt(rooms: ModelRoom[], page: number, pt: Point): ModelRoom | undefined {
  return rooms.find((r) => {
    if (r.page !== page) return false;
    if (r.polygon) return inPolygon(pt, r.polygon);
    const [x0 = 1, y0 = 1, x1 = 0, y1 = 0] = r.box;
    return pt[0] >= x0 && pt[0] <= x1 && pt[1] >= y0 && pt[1] <= y1;
  });
}

export const LEVEL_WORD: Record<Level['level'], string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};
