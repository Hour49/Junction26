// The project chat's ask (docs/specs/frontend/chat.md), in the shape of Bogdan's coming
// POST /api/projects/{project_id}/ask (#14 c6875607088), so switching is replacing askProject's body.
import { askQuestion, type AnswerView, type ProjectView, type Suggestion } from '../api';

type Entry = ProjectView['drawings'][number];

/** One drawing's answer; `name` is the drawing's file in this project. */
export interface ProjectPart {
  drawing_id: string;
  name: string;
  answer: AnswerView;
}

/** Local type until schema.d.ts has the project ask. */
export interface ProjectAsk {
  question: string;
  /** Answering drawings first, refused after, each in drawing order. */
  parts: ProjectPart[];
  /** The single answering part's value; null when several answer (they may overlap) or none does. */
  total: number | null;
  total_note: string | null;
}

/** The drawings a question can go to: read ones (`ready`, or `flagged` for something a person should see). */
export function askable(drawings: Entry[]): Entry[] {
  return drawings.filter((d) => d.state === 'ready' || d.state === 'flagged');
}

export const OVERLAP_NOTE =
  'These drawings may show the same rooms, so the numbers are not added up.';

/** Bogdan's rule (#14 c6875696652): a total only when exactly one drawing answers (only the backend can tell
 * disjoint parts); several answering drawings are never added up. */
export function totalOf(parts: ProjectPart[]): Pick<ProjectAsk, 'total' | 'total_note'> {
  const answering = parts.filter((p) => p.answer.refusal === null);
  if (answering.length > 1) return { total: null, total_note: OVERLAP_NOTE };
  const value = answering[0]?.answer.answer;
  return { total: typeof value === 'number' ? value : null, total_note: null };
}

/** Asks the project; rejects when every request fails, or when there is no drawing to ask. */
// shortcut: fan-out per drawing, replace with the project ask when the backend has it
export async function askProject(
  projectId: string,
  drawings: Entry[],
  question: string,
): Promise<ProjectAsk> {
  if (drawings.length === 0) throw new Error('No drawing in this project can be asked yet.');
  const results = await Promise.allSettled(
    drawings.map((d) => askQuestion({ drawing_id: d.drawing_id, question, project_id: projectId })),
  );
  const parts = drawings.flatMap((d, i): ProjectPart[] => {
    const r = results[i];
    return r?.status === 'fulfilled'
      ? [{ drawing_id: d.drawing_id, name: d.file, answer: r.value }]
      : [];
  });
  if (parts.length === 0) throw (results[0] as PromiseRejectedResult).reason;
  const ordered = [
    ...parts.filter((p) => p.answer.refusal === null),
    ...parts.filter((p) => p.answer.refusal !== null),
  ];
  return { question, parts: ordered, ...totalOf(ordered) };
}

// A door count, a room area, a window count first (Tudor 12:45: "like the chatgpt ui"), then the rest in order.
const STARTER_RANK = ['door', 'area', 'window'];
const kind = (s: Suggestion) => s.quantity.split(/[:|]/)[0] ?? '';
const rank = (s: Suggestion) => {
  const i = STARTER_RANK.indexOf(kind(s));
  return i < 0 ? STARTER_RANK.length : i;
};

/** Up to three starter questions from the drawings' own suggestions (never invented): the first question of
 * each kind ("door", "area", …), a door count, an area and a window count first. */
export function starters(lists: Suggestion[][]): Suggestion[] {
  const seen = new Set<string>();
  const firsts = lists.flat().filter((s) => !seen.has(kind(s)) && seen.add(kind(s)));
  return firsts.sort((a, b) => rank(a) - rank(b)).slice(0, 3);
}
