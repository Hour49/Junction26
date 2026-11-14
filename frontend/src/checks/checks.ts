// Pure parts of the Checks screen (docs/specs/frontend/checks.md).
import { formatValue, type MarkView } from '../api';
import { plural } from '../ingest/ingest';
import type { Tone } from '../viewer/PageViewer';
import type {
  Box,
  CheckMark,
  CheckResult,
  CheckStatus,
  DrawingChecks,
  ProjectChecks,
  RuleCheck,
  RulePack,
} from './types';

// This project's name for a drawing (drawings are shared between projects): one source with Advanced (CK-9).
export { fileName } from '../advanced/advanced';

/** Word and icon per result status: status is never colour alone; "cannot tell" is its own state. */
export const STATUS_WORD: Record<CheckStatus, { icon: string; word: string }> = {
  fail: { icon: '✕', word: 'Fails' },
  cannot_tell: { icon: '?', word: 'Cannot tell' },
  pass: { icon: '✓', word: 'Passes' },
};

/** A rule's (or drawing's) status from its results: any fail, else any cannot tell, else pass; none → null. */
export function checkStatusOf(results: readonly { status: CheckStatus }[]): CheckStatus | null {
  if (results.some((r) => r.status === 'fail')) return 'fail';
  if (results.some((r) => r.status === 'cannot_tell')) return 'cannot_tell';
  return results.length ? 'pass' : null;
}

export interface RuleRow {
  id: string;
  title: string;
  ref: string;
  pass: number;
  fail: number;
  cannot_tell: number;
  status: CheckStatus | null;
}

/** One row per rule: places passed / failed / cannot tell over all drawings; pack order, unknown rules after. */
export function ruleSummary(checks: ProjectChecks, pack: RulePack | null): RuleRow[] {
  const seen = new Map<string, { rule: RuleCheck; results: CheckResult[] }>();
  for (const d of checks.drawings)
    for (const rule of d.rules) {
      const entry = seen.get(rule.rule_id) ?? { rule, results: [] };
      entry.results.push(...rule.results);
      seen.set(rule.rule_id, entry);
    }
  const order = [
    ...(pack?.rules.map((r) => r.id) ?? []).filter((id) => seen.has(id)),
    ...[...seen.keys()].filter((id) => !pack?.rules.some((r) => r.id === id)),
  ];
  return order.map((id) => {
    const { rule, results } = seen.get(id) ?? { rule: null, results: [] };
    const count = (s: CheckStatus) => results.filter((r) => r.status === s).length;
    return {
      id,
      title: rule?.title ?? id,
      ref: rule?.clause.ref ?? '',
      pass: count('pass'),
      fail: count('fail'),
      cannot_tell: count('cannot_tell'),
      status: checkStatusOf(results),
    };
  });
}

/** Rules by status (CK-4, as the conflicts screen's checks row); a rule with no result is not counted. */
export function ruleCounts(rows: readonly RuleRow[]): {
  failed: number;
  cannotTell: number;
  passed: number;
} {
  const n = (s: CheckStatus) => rows.filter((r) => r.status === s).length;
  return { failed: n('fail'), cannotTell: n('cannot_tell'), passed: n('pass') };
}

export function summaryLine(rows: readonly RuleRow[], drawings: number): string {
  const c = ruleCounts(rows);
  const failed = plural(c.failed, 'rule');
  return `${failed} failed, ${String(c.cannotTell)} cannot tell, ${String(c.passed)} passed, over ${plural(drawings, 'drawing')}`;
}

/** A drawing's failed results, then its cannot-tell results, each in rule order then result order. */
export function drawingResults(d: DrawingChecks): { rule: RuleCheck; result: CheckResult }[] {
  const all = d.rules.flatMap((rule) => rule.results.map((result) => ({ rule, result })));
  return [
    ...all.filter((x) => x.result.status === 'fail'),
    ...all.filter((x) => x.result.status === 'cannot_tell'),
  ];
}

/** The value-vs-limit line; a null value reads "not measured, limit …", never 0 and never "measured" twice. */
export function limitLine(r: CheckResult): string {
  const limit = `limit ${r.comparison_text} ${valueText(r.limit, r.unit)}`;
  return r.value === null
    ? `not measured, ${limit}`
    : `${valueText(r.value, r.unit)} measured, ${limit}`;
}

/** A measured value as text; null is "not measured", never 0 and never the limit (CK-8). */
export function valueText(value: number | null, unit: string | null): string {
  return value === null ? 'not measured' : formatValue(value, unit);
}

const boxOf = (m: CheckMark): Box | null => {
  if (m.box) return m.box;
  if (!m.polygon?.length) return null;
  const xs = m.polygon.map((p) => p[0]);
  const ys = m.polygon.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
};

/** A result's marks as viewer marks and their tones (viewer.md "Check marks as viewer marks"). */
export function viewerMarks(result: CheckResult): {
  marks: MarkView[];
  tones: Record<string, Tone>;
} {
  const subjects = result.marks.filter((m) => m.role === 'subject').length;
  let n = 0;
  const marks: MarkView[] = [];
  const tones: Record<string, Tone> = {};
  result.marks.forEach((m, i) => {
    const box = boxOf(m);
    if (!box) return; // a mark with neither box nor polygon cannot be drawn
    const subject = m.role === 'subject';
    // result.mark_id is the takeoff mark of the result's (first) subject; other marks are check-only
    const id = subject && n === 0 && result.mark_id ? result.mark_id : `${result.id}:${String(i)}`;
    marks.push({
      id,
      n: subject ? ++n : null,
      state: 'counted',
      label: m.label,
      ref: m.ref,
      page: m.page,
      box,
      polygon: m.polygon,
      value: subject && subjects === 1 ? result.value : null,
      reason: null,
    });
    tones[id] = subject ? result.status : 'counted';
  });
  return { marks, tones };
}

/** Where "Show on the drawing" jumps: the first subject mark (else the first mark); null without marks. */
export function focusOf(result: CheckResult): { page: number; box: Box | null } | null {
  const m = result.marks.find((x) => x.role === 'subject') ?? result.marks[0];
  return m ? { page: m.page, box: boxOf(m) } : null;
}
