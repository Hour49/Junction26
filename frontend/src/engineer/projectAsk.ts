// The project chat's helpers (docs/specs/frontend/chat.md); the ask itself is `askProject` in src/api/client.ts.
import type { ProjectView, Suggestion } from '../api';

type Entry = ProjectView['drawings'][number];

/** The drawings a question can go to: read ones (`ready`, or `flagged` for something a person should see). */
export function askable(drawings: Entry[]): Entry[] {
  return drawings.filter((d) => d.state === 'ready' || d.state === 'flagged');
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
