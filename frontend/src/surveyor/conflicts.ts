// The conflicts screen's pure parts (docs/specs/frontend/conflicts.md "Field map").
import type { CheckStatus, ConflictEntry, DrawingReview, ProjectChecks } from '../api';

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

const RANK: Record<CheckStatus, number> = { pass: 0, cannot_tell: 1, fail: 2 };

/** Rules counted across every drawing: failed if any result fails, else cannot tell if any can't, else passed. */
export function ruleCounts(checks: ProjectChecks): {
  passed: number;
  failed: number;
  cannot: number;
} {
  const worst = new Map<string, CheckStatus>();
  for (const d of checks.drawings)
    for (const rule of d.rules)
      for (const r of rule.results) {
        const was = worst.get(rule.rule_id);
        if (was === undefined || RANK[r.status] > RANK[was]) worst.set(rule.rule_id, r.status);
      }
  const n = (s: CheckStatus) => [...worst.values()].filter((v) => v === s).length;
  return { passed: n('pass'), failed: n('fail'), cannot: n('cannot_tell') };
}

/** "1 rule passed", "1 failed", "1 cannot tell": zero parts left out, the noun on the first part only. */
export function countParts(
  c: ReturnType<typeof ruleCounts>,
): { kind: CheckStatus; text: string }[] {
  const parts = [
    { kind: 'pass' as const, n: c.passed, word: 'passed' },
    { kind: 'fail' as const, n: c.failed, word: 'failed' },
    { kind: 'cannot_tell' as const, n: c.cannot, word: 'cannot tell' },
  ].filter((p) => p.n > 0);
  return parts.map((p, i) => ({
    kind: p.kind,
    text:
      i === 0 ? `${String(p.n)} rule${p.n === 1 ? '' : 's'} ${p.word}` : `${String(p.n)} ${p.word}`,
  }));
}
