// The conflicts screen's pure parts (docs/specs/frontend/conflicts.md "Field map").
import { isCountUnit, pickInUse, resolverName, type ConflictEntry } from '../api';

export type CardState = 'open' | 'rule' | 'picked' | 'yours';

/** needs_person → open; a settled value → yours; a model's pick in use → picked (#252); else a rule chose. */
export function cardState(c: ConflictEntry): CardState {
  if (c.needs_person) return 'open';
  if (c.settled) return 'yours';
  return pickInUse(c) ? 'picked' : 'rule';
}

/** The tile the rule chose, or -1. The server sends the same float for both, so `===` holds. */
export function ruleIndex(c: ConflictEntry): number {
  const r = c.conflict.resolution;
  return r ? c.conflict.values.findIndex((v) => v.value === r.value) : -1;
}

/** The tile in use: the one at the row's current `value`; -1 when none matches (a recount). */
export function inUseIndex(c: ConflictEntry): number {
  if (c.needs_person) return -1; // nobody chose yet: no tile is in use
  return c.conflict.values.findIndex((x) => x.value === c.value);
}

export const keyOf = (c: ConflictEntry) => `${c.drawing_id} ${c.quantity}`;

export function conflictCount(k: number): string {
  if (k === 0) return 'No conflicts found';
  return `${String(k)} conflict${k === 1 ? '' : 's'} found`;
}

/** `measured`: quantities read on the project's drawings; 0 means nothing was read, so nothing agreed (QA R2-E1). */
export function subLine(conflicts: ConflictEntry[], measured?: number): string {
  if (conflicts.length === 0)
    return measured === 0
      ? 'Nothing was measured on these drawings, so there was nothing to compare.'
      : 'Both methods agree wherever two of them measured.';
  const n = (s: ReturnType<typeof cardState>) => conflicts.filter((c) => cardState(c) === s).length;
  const [r, k, y, p] = [n('rule'), n('picked'), n('yours'), n('open')];
  const by = conflicts.find((c) => cardState(c) === 'picked')?.resolved?.by ?? 'carbon';
  return [
    r ? `${String(r)} settled by a rule` : null,
    k ? `${String(k)} picked by ${resolverName(by)}, check them` : null,
    y ? `${String(y)} settled by you` : null,
    p ? `${String(p)} need${p === 1 ? 's' : ''} you` : null,
  ]
    .filter(Boolean)
    .map((s) => `${String(s)}.`)
    .join(' ');
}

const NO_RULE = 'No rule decides between them';

/** The server's `why`, cut after "No rule decides between them." when a model answered: the rest names the model id
 * (RS-15); '' when the sentence is missing (the card then lists the rule's sentences). */
export function whyText(c: ConflictEntry): string {
  if (!c.resolved) return c.why;
  const at = c.why.indexOf(NO_RULE);
  return at < 0 ? '' : `${c.why.slice(0, at + NO_RULE.length)}.`;
}

export function progressText(conflicts: ConflictEntry[]): string {
  const s = conflicts.filter((c) => !c.needs_person).length;
  return `${String(s)} of ${String(conflicts.length)} settled`;
}

/** Cards a rule could decide first, then the rest, each in the server's order (CF-37); settling never moves a card. */
export const ordered = (conflicts: ConflictEntry[]) => [
  ...conflicts.filter((c) => c.conflict.resolution !== null),
  ...conflicts.filter((c) => c.conflict.resolution === null),
];

export type Answer = { value: number } | { note: string };

/** A typed answer (CF-41, #226): a number (unit allowed) is a value to settle, words are a note; else the line to show. */
export function parseAnswer(text: string, unit: string | null): Answer | string {
  const t = text.trim();
  if (!t) return 'Type a number or a few words.';
  const bare = t.replace(/\s*(m²|m2|m³|m3|m)$/i, '').replace(',', '.');
  if (!/^\d+(\.\d+)?$|^\.\d+$/.test(bare)) return { note: t };
  const n = Number(bare);
  if (isCountUnit(unit))
    return Number.isInteger(n) ? { value: n } : 'Type a whole number, like 12.';
  return n > 0 ? { value: n } : 'Type a number above 0, or a few words.';
}

/** The server's suggestions that say something no variant does (Tudor: no chips repeating a variant, CF-51). */
export const newSuggestions = (c: ConflictEntry): string[] =>
  ((c.suggestions as string[] | undefined) ?? []).filter((s) => {
    const n = parseFloat(s.replace(',', '.'));
    return !c.conflict.values.some((v) => Math.abs(v.value - n) < 0.005); // "22.40 m²" restates 22.401
  });
