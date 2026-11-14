// A proposal's services follow-up (docs/specs/backend/services-follow.md "API"), typed from the OpenAPI schema,
// and the pure helpers of its tabs.
import type { components } from '../../api/schema';
import type { Point } from '../agent';

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
