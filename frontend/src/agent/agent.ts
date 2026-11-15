// The agent chat's turn (decision 0013, docs/specs/agent-chat.md §3), typed from the OpenAPI schema, and its pure helpers.
import type { components } from '../api/schema';

type Schemas = components['schemas'];

export type Box = [number, number, number, number];
export type Point = [number, number];

// The law check of a proposal (docs/specs/plan-edit-law-check.md §2.3, LC-3): rule-pack findings before vs after,
// the AI's server-checked notes, the related clauses.
export type LawCheck = Schemas['LawCheck'];
export type Finding = Schemas['Finding'];
export type AiFinding = Schemas['AiFinding'];
export type LawChange = Finding['change'];
/** `law`: null when no country was picked (LC-14). */
export type Proposal = Schemas['Proposal'];
/** `answers`: the exact POST /ask results the turn rests on ([] otherwise); the chat shows them as the ask chat does. */
export type ChatTurn = Schemas['ChatTurn'];
/** `pack`: the route's `?pack=` (LC-11). */
export type ChatRequest = Schemas['ChatRequest'];
export type Evidence = Schemas['ChatEvidence'];
/** ADR 0011 confidence level of an ask_drawings answer part. */
export type Level = Schemas['app__core__agent__model__Level'];
export type Step = Schemas['Step'];
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

export type Block = { kind: 'p' | 'ul' | 'ol'; lines: string[]; start?: number };
export type Inline =
  { kind: 'text' | 'b' | 'em'; text: string } | { kind: 'a'; text: string; href: string };

/** The model's text as paragraphs and "- " / "1. " lists (answers-1); headings and quote marks dropped. */
export function blocksOf(text: string): Block[] {
  const out: Block[] = [];
  let blank = true; // a blank line ends the block
  for (const raw of text.split('\n')) {
    const line = raw.replace(/^\s*(#{1,6}\s+|>\s?)+/, '').trimEnd();
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line)?.[1];
    const [, n, ol] = /^\s*(\d+)[.)]\s+(.*)$/.exec(line) ?? [];
    const [kind, body]: [Block['kind'], string] =
      ul !== undefined ? ['ul', ul] : ol !== undefined ? ['ol', ol] : ['p', line.trim()];
    const last = out.at(-1);
    if (!body) blank = true;
    else if (last?.kind !== kind || (blank && kind === 'p')) {
      out.push({ kind, lines: [body], ...(n ? { start: Number(n) } : {}) });
      blank = false;
    } else last.lines.push(body);
  }
  return out;
}

/** A line's **bold** and *italic* / _italic_ runs (lawai-4; `_` only at word edges, so snake_case stays) and
 * [text](url) links (http(s) only, else the text); backticks and stray ** dropped. */
export function inlineOf(line: string): Inline[] {
  const out: Inline[] = [];
  const re =
    /\*\*(.+?)\*\*|\*(?![\s*])([^*]+?)(?<!\s)\*|(?<!\w)_(?![\s_])([^_]+?)(?<!\s)_(?!\w)|\[([^\]]+)\]\(([^)\s]+)\)/g;
  const plain = (s: string) => s.replace(/`|\*\*/g, '');
  let at = 0;
  for (const m of line.matchAll(re)) {
    if (m.index > at) out.push({ kind: 'text', text: plain(line.slice(at, m.index)) });
    const [, bold, star, under, label, href] = m;
    if (bold !== undefined) out.push({ kind: 'b', text: plain(bold) });
    else if ((star ?? under) !== undefined)
      out.push({ kind: 'em', text: plain(star ?? under ?? '') });
    else if (href && /^https?:\/\//.test(href))
      out.push({ kind: 'a', text: plain(label ?? href), href });
    else out.push({ kind: 'text', text: plain(label ?? '') });
    at = m.index + m[0].length;
  }
  if (at < line.length) out.push({ kind: 'text', text: plain(line.slice(at)) });
  return out.filter((x) => x.text);
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

/** The confidence of each drawing the turn cites, for the References cards (P5). Sources are marks, references
 * are drawings, so they are matched by drawing id; several marks on one drawing give the lowest level. */
export function levelsByDrawing(evidence: Evidence[]): Map<string, Level> {
  const rank: Record<Level['level'], number> = { low: 0, medium: 1, high: 2 };
  const out = new Map<string, Level>();
  for (const e of evidence) {
    if (!e.level) continue;
    const have = out.get(e.drawing_id);
    if (!have || rank[e.level.level] < rank[have.level]) out.set(e.drawing_id, e.level);
  }
  return out;
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

/** The overlay's room badges, grouped where they would land on each other (rerun-lawcheck-1: a box cut from a
 * room's bottom edge puts both badges under that edge). Each group sits under its first room's lowest point, at
 * its centre x kept off the page edge; its badges stack below one another. */
export function badgeGroups(rooms: RoomChange[]): { x: number; y: number; rooms: RoomChange[] }[] {
  const groups: { x: number; y: number; rooms: RoomChange[] }[] = [];
  for (const r of rooms) {
    const x = Math.min(Math.max(centreOf(r.polygon)[0], 0.1), 0.9);
    const y = Math.max(...r.polygon.map((q) => q[1]));
    // shortcut: "near" is in page fractions (a badge is up to 220 px wide); measure the badges if this misfires
    const near = groups.find((g) => Math.abs(g.x - x) < 0.5 && Math.abs(g.y - y) < 0.05);
    if (near) near.rooms.push(r);
    else groups.push({ x, y, rooms: [r] });
  }
  return groups;
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
  attrs?: Record<string, unknown>;
}

/** The room as the plan writes it, name and number ("Bagno 1.01"), as the server's plan tools name it. */
export function roomName(r: ModelRoom): string {
  const name = r.label ?? r.type;
  const n = r.attrs?.number;
  return (typeof n === 'string' || typeof n === 'number') && !name.includes(String(n))
    ? `${name} ${String(n)}`
    : name;
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

/** A place on the plan the turn wants on screen (`.agents/chat/contract.md` A): every mark is also in `evidence`. */
export interface ViewMark {
  n: number;
  label: string | null;
  box: Box;
  polygon?: Point[] | null; // optional in the server's schema (#319)
}
/** `ChatTurn.view` (contract A): the drawing page to open, its marks, the box to focus and the server's caption. */
export interface View {
  drawing_id: string;
  name: string | null;
  page: number;
  box: Box;
  marks: ViewMark[];
  caption?: string | null; // optional in the server's schema (#319)
  source: 'show_on_plan' | 'evidence';
}

const MARGIN = 0.02; // page fractions around the marks' union, as the server's view box

/** The union of boxes with a margin, clamped to the page. */
export function unionBox(boxes: Box[]): Box {
  const c = (v: number) => Math.min(Math.max(v, 0), 1);
  return [
    c(Math.min(...boxes.map((b) => b[0])) - MARGIN),
    c(Math.min(...boxes.map((b) => b[1])) - MARGIN),
    c(Math.max(...boxes.map((b) => b[2])) + MARGIN),
    c(Math.max(...boxes.map((b) => b[3])) + MARGIN),
  ];
}

/** The plan the turn shows: the server's `view`; from a server without it, contract A's "evidence" rule (the page
 * of `[1]`, every evidence item on that drawing and page); null with no evidence. */
export function viewOf(turn: ChatTurn): View | null {
  const sent = (turn as ChatTurn & { view?: View | null }).view;
  if (sent !== undefined) return sent;
  const first = turn.evidence[0];
  if (!first) return null;
  const here = turn.evidence.filter(
    (e) => e.drawing_id === first.drawing_id && e.page === first.page,
  );
  return {
    drawing_id: first.drawing_id,
    name: first.name,
    page: first.page,
    box: unionBox(here.map((e) => e.box)),
    marks: here.map((e) => ({ n: e.n, label: e.label, box: e.box, polygon: null })),
    caption: null,
    source: 'evidence',
  };
}

/** One source's place as a view of its own, for a `[n]` that is not on the shown page. */
export function evidenceView(e: Evidence): View {
  return {
    drawing_id: e.drawing_id,
    name: e.name,
    page: e.page,
    box: unionBox([e.box]),
    marks: [{ n: e.n, label: e.label, box: e.box, polygon: null }],
    caption: null,
    source: 'evidence',
  };
}
