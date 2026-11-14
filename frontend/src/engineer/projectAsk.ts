// The project chat's helpers (docs/specs/frontend/chat.md); the ask itself is `askProject` in src/api/client.ts.
import type { DrawingView, ProjectAnswer, ProjectView, Suggestion } from '../api';

type Entry = ProjectView['drawings'][number];

/** The drawings a question can go to: read ones (`ready`, or `flagged` for something a person should see). */
export function askable(drawings: Entry[]): Entry[] {
  return drawings.filter((d) => d.state === 'ready' || d.state === 'flagged');
}

/** Whether the pen can draw on this drawing (ui-bugs 1): not a scan or photo, and read with pages to draw on.
 * TODO(board #404): use the backend's drawable field once DrawingEntry has it (scale, outlines, walls). */
export function canDraw(entry: Entry, drawing: DrawingView | null | undefined): boolean {
  return entry.route !== 'raster' && (drawing?.pages.length ?? 0) > 0;
}

// A door count, a room area, a window count first (Tudor 12:45: "like the chatgpt ui"), then the rest in order.
const STARTER_RANK = ['door', 'area', 'window'];
const kind = (s: Suggestion) => s.quantity.split(/[:|]/)[0] ?? '';
const rank = (s: Suggestion) => {
  const i = STARTER_RANK.indexOf(kind(s));
  return i < 0 ? STARTER_RANK.length : i;
};

/** The first question of each kind ("door", "area", …), a door count, an area and a window count first. */
function firstPerKind(all: Suggestion[]): Suggestion[] {
  const seen = new Set<string>();
  const firsts = all.filter((s) => !seen.has(kind(s)) && seen.add(kind(s)));
  return firsts.sort((a, b) => rank(a) - rank(b));
}

/** Up to three starter questions from the drawings' own suggestions (never invented): the first question of
 * each kind ("door", "area", …), a door count, an area and a window count first. */
export function starters(lists: Suggestion[][]): Suggestion[] {
  return firstPerKind(lists.flat()).slice(0, 3);
}

/** CH-36: up to three questions not asked yet, from the same suggestions: the starters' order, then the rest in
 * drawing order; one chip per question text. */
export function followUps(lists: Suggestion[][], asked: string[]): Suggestion[] {
  const done = new Set(asked.map((q) => q.trim()));
  const firsts = firstPerKind(lists.flat());
  const seen = new Set<string>();
  return [...firsts, ...lists.flat().filter((s) => !firsts.includes(s))]
    .filter((s) => !done.has(s.question.trim()) && !seen.has(s.question) && seen.add(s.question))
    .slice(0, 3);
}

type Part = ProjectAnswer['parts'][number];

/** CH-30: the answering parts, sheets that are not floor plans first (the file's triage class), each group in the
 * API's order; no triage counts as a floor plan. */
export function orderParts(parts: Part[], files: ProjectView['files']): Part[] {
  const answering = parts.filter((p) => p.answer.refusal === null);
  const notPlan = (p: Part) => {
    const c = files.find((f) => f.drawing_id === p.drawing_id)?.triage?.class;
    return c === 'other_drawing' || c === 'not_drawing';
  };
  return [...answering.filter(notPlan), ...answering.filter((p) => !notPlan(p))];
}
