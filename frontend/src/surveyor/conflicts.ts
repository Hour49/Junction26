// The conflicts screen's pure parts (docs/specs/frontend/conflicts.md "Field map").
import type { CheckStatus, ConflictEntry, DrawingReview, ProjectChecks } from '../api';
import { ruleCounts, ruleSummary } from '../checks/checks';

export type CardState = 'open' | 'rule' | 'yours';

/** needs_person → open; a settled value → yours; else a rule chose. */
export function cardState(c: ConflictEntry): CardState {
  if (c.needs_person) return 'open';
  return c.settled ? 'yours' : 'rule';
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

export const letter = (i: number) => String.fromCharCode(65 + i);

export const keyOf = (c: ConflictEntry) => `${c.drawing_id} ${c.quantity}`;

export function conflictCount(k: number): string {
  if (k === 0) return 'No conflicts found';
  return `${String(k)} conflict${k === 1 ? '' : 's'} found`;
}

export function subLine(conflicts: ConflictEntry[]): string {
  if (conflicts.length === 0) return 'Both methods agree wherever two of them measured.';
  const n = (s: ReturnType<typeof cardState>) => conflicts.filter((c) => cardState(c) === s).length;
  const [r, y, p] = [n('rule'), n('yours'), n('open')];
  return [
    r ? `${String(r)} settled by a rule` : null,
    y ? `${String(y)} settled by you` : null,
    p ? `${String(p)} need${p === 1 ? 's' : ''} you` : null,
  ]
    .filter(Boolean)
    .map((s) => `${String(s)}.`)
    .join(' ');
}

export function progressText(conflicts: ConflictEntry[]): string {
  const s = conflicts.filter((c) => !c.needs_person).length;
  return `${String(s)} of ${String(conflicts.length)} settled`;
}

/** The drawing "Open the workspace" goes to: the first with quantities, else the first. */
export function workspaceDrawing(drawings: DrawingReview[]): string | null {
  return (drawings.find((d) => d.quantities > 0) ?? drawings[0])?.drawing_id ?? null;
}

/** Rules by status, counted exactly as the checks screen (src/checks/checks.ts: a rule that cannot tell with no
 * results is cannot tell; one that does not apply is not counted), so both screens agree on the same data. */
export const ruleCountsOf = (checks: ProjectChecks) => ruleCounts(ruleSummary(checks, null));

/** "1 rule passed", "1 failed", "1 cannot tell": zero parts left out, the noun on the first part only. */
export function countParts(
  c: ReturnType<typeof ruleCountsOf>,
): { kind: CheckStatus; text: string }[] {
  const parts = [
    { kind: 'pass' as const, n: c.passed, word: 'passed' },
    { kind: 'fail' as const, n: c.failed, word: 'failed' },
    { kind: 'cannot_tell' as const, n: c.cannotTell, word: 'cannot tell' },
  ].filter((p) => p.n > 0);
  return parts.map((p, i) => ({
    kind: p.kind,
    text:
      i === 0 ? `${String(p.n)} rule${p.n === 1 ? '' : 's'} ${p.word}` : `${String(p.n)} ${p.word}`,
  }));
}
