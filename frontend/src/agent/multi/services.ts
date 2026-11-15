// A proposal's services follow-up (docs/specs/backend/services-follow.md "API"), typed from the OpenAPI schema,
// and the pure helpers of its tabs.
import type { components } from '../../api/schema';
import type { Box, Point } from '../agent';

type Schemas = components['schemas'];

export type ServicesFollow = Schemas['ServicesFollow'];
/** One discipline of the follow-up: its model, what it says in one line, the marks near the edit, the actions. */
export type Lane = Schemas['DisciplineFollow'];
export type ServiceAction = Schemas['ServiceAction'];
export type ServiceMark = Schemas['ServiceMark'];
export type Status = ServiceAction['status'];

/** Status by icon and word, colour never alone (as the law rows). */
export const STATUS: Record<Status, { word: string; icon: string }> = {
  cut_off: { word: 'Cut off', icon: '✕' },
  needs_decision: { word: 'Needs a decision', icon: '!' },
  follows: { word: 'Follows', icon: '→' },
  stays: { word: 'Stays', icon: '=' },
};
/** Strongest first: the list's order, and the status a mark takes when two actions name it. */
const RANK: Status[] = ['cut_off', 'needs_decision', 'follows', 'stays'];

/** How a services sheet was taken to be this floor's (pics-edit-follow W1). */
export type Pairing = Schemas['Pairing'];
/** A lane's own services sheet (pics-edit-follow W2, services-follow.md SFPW-1..6; null on model and unchecked
 * lanes and always with DISCIPLINE_PICTURES off): the edit's strips and the lane's marks in THAT sheet's page
 * fractions; `marks` joins `lane.marks` and `lane.actions` by ref. */
export type LanePicture = Schemas['FollowPicture'];
export const pictureOf = (l: Lane): LanePicture | null => l.picture ?? null;

/** AC-42: how the sheet was paired, in words. */
export const PAIRED_BY: Record<Pairing['paired_by'], string> = {
  same_page: 'Same page as the plan',
  metadata: "Paired by the sheets' names",
  geometry: 'Paired by the walls',
  user: 'Paired by you',
};

/** The lane on its own sheet: each mark at its place on that sheet (marks the sheet does not place are left out).
 * A picture moves nothing and draws no new run (services-follow.md § Pictures), so no new place or path is kept. */
export function onSheet(l: Lane, pic: LanePicture): Lane {
  const placed = new Map(pic.marks.map((m) => [m.ref, m]));
  return {
    ...l,
    marks: l.marks.flatMap((m) => {
      const q = placed.get(m.ref);
      return q ? [{ ...m, line: q.line, at: q.at }] : [];
    }),
    actions: l.actions.map((a) => ({ ...a, moved_to: null, paths: [] })),
  };
}

/** The strike line through a removed strip: along its long side, from the middle of one short side to the other. */
export function strikeOf(strip: Point[]): [Point, Point] | null {
  if (strip.length < 2) return null;
  const mid = (a: Point, b: Point): Point => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const len = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const [a, b, c, d] = strip;
  if (strip.length === 4 && a && b && c && d)
    return len(a, b) < len(b, c) ? [mid(a, b), mid(c, d)] : [mid(b, c), mid(d, a)];
  const xs = strip.map((q) => q[0]);
  const ys = strip.map((q) => q[1]);
  const [x0, y0, x1, y1] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  return x1 - x0 >= y1 - y0
    ? [
        [x0, (y0 + y1) / 2],
        [x1, (y0 + y1) / 2],
      ]
    : [
        [(x0 + x1) / 2, y0],
        [(x0 + x1) / 2, y1],
      ];
}

const NOT_CHECKED: Record<Exclude<Lane['status'], 'checked'>, string> = {
  no_model: 'no model',
  not_aligned: 'not aligned',
};

/** "Ventilation". */
export const laneName = (l: Lane) => l.discipline.charAt(0).toUpperCase() + l.discipline.slice(1);

/** The actions that change something or ask for a decision: the tab's count. */
export const openCount = (l: Lane) => l.actions.filter((a) => a.status !== 'stays').length;

/** What the tab says beside the name: the count when there is one, why not when the lane was not checked. */
export function tabNote(l: Lane): string | null {
  if (l.status !== 'checked') return NOT_CHECKED[l.status];
  const n = openCount(l);
  return n > 0 ? String(n) : null;
}

/** The actions, strongest status first; the server's order within a status. */
export function ordered(actions: ServiceAction[]): ServiceAction[] {
  return [...actions].sort((a, b) => RANK.indexOf(a.status) - RANK.indexOf(b.status));
}

/** Each mark's status: of the strongest action that names it. Marks no action names are context. */
export function markStatus(l: Lane): Map<string, Status> {
  const out = new Map<string, Status>();
  for (const a of ordered(l.actions))
    for (const ref of a.refs) if (!out.has(ref)) out.set(ref, a.status);
  return out;
}

/** Where a mark is: its point, else the middle of its line. */
export function placeOfMark(m: ServiceMark): Point | null {
  if (m.at) return m.at;
  if (m.line.length === 0) return null;
  const xs = m.line.map((q) => q[0]);
  const ys = m.line.map((q) => q[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

/** The middle of everything an action draws (its marks, the new place, the proposed runs); null when nothing. */
export function placeOfAction(l: Lane, a: ServiceAction): Point | null {
  const pts = [
    ...l.marks.filter((m) => a.refs.includes(m.ref)).map(placeOfMark),
    a.moved_to ?? null,
    ...a.paths.flat(),
  ].filter((q): q is Point => q !== null);
  if (pts.length === 0) return null;
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

const RUNS = new Set(['pipe', 'duct', 'cable', 'pipe fitting', 'duct fitting', 'cable fitting']);
/** A run seen end-on or a fitting is a small dot; a terminal (fixture, outlet, damper) a bigger one. */
export const isTerminal = (m: ServiceMark) => !RUNS.has(m.kind);

/** The part of the page to look at under a lane's tab: the changed walls with the lane's terminals and what it
 * proposes (all within a few metres of the change), plus a margin, so the card can zoom to it. A run's line is
 * left out: it can cross the whole storey. Null when the lane draws nothing. */
export function focusOf(
  l: Lane,
  p: { removed: { polygon: Point[] }[]; added: { polygon: Point[] }[] },
): Box | null {
  if (l.marks.length === 0) return null;
  const pts = [
    ...[...p.removed, ...p.added].flatMap((g) => g.polygon),
    ...l.marks.flatMap((m) => (m.at ? [m.at] : [])),
    ...l.actions.flatMap((a) => [...(a.moved_to ? [a.moved_to] : []), ...a.paths.flat()]),
  ];
  if (pts.length === 0) return null;
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const [x0, y0, x1, y1] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  const pad = 0.1 * Math.max(x1 - x0, y1 - y0);
  return [x0 - pad, y0 - pad, x1 + pad, y1 + pad];
}
