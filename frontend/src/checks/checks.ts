// Pure parts of the Checks screen (docs/specs/frontend/checks.md).
import { formatValue, type MarkView } from '../api';
import { plural } from '../ingest/ingest';
import type { Tone } from '../viewer/PageViewer';
import type {
  Box,
  CheckResult,
  CheckStatus,
  DrawingChecks,
  ProjectChecks,
  RuleCheck,
  RulePack,
  RuleStatus,
} from './types';

import { fileName } from '../advanced/advanced';
import type { ProjectView } from '../api';

/**
 * This project's name for a checked drawing (drawings are shared between projects, CK-9): its file here (one
 * source with Advanced), else the payload's `file`, which #142 states is this project's path too.
 */
export function drawingName(
  project: ProjectView,
  d: Pick<DrawingChecks, 'drawing_id' | 'file'>,
): string {
  const own = fileName(project, d.drawing_id);
  return own === d.drawing_id ? d.file : own;
}

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

/**
 * One RuleCheck's status: from its results when it has any; else its own (`cannot_tell` when nothing could be read,
 * e.g. a scan offline); null when it does not apply (`not_applicable`).
 */
export function ruleCheckStatus(rc: RuleCheck): CheckStatus | null {
  return checkStatusOf(rc.results) ?? (rc.status === 'not_applicable' ? null : rc.status);
}

export interface RuleRow {
  id: string;
  title: string;
  ref: string;
  pass: number;
  fail: number;
  cannot_tell: number;
  /** Drawings where the rule cannot tell without any result (nothing read there): no place to count. */
  blind: number;
  /** Worst over its RuleChecks (`ruleCheckStatus`); `not_applicable` when none applies, never pass or fail. */
  status: RuleStatus;
}

/** One row per rule: places passed / failed / cannot tell over all drawings; pack order, unknown rules after. */
export function ruleSummary(checks: ProjectChecks, pack: RulePack | null): RuleRow[] {
  const seen = new Map<
    string,
    { rule: RuleCheck; results: CheckResult[]; statuses: CheckStatus[]; blind: number }
  >();
  for (const d of checks.drawings)
    for (const rule of d.rules) {
      const entry = seen.get(rule.rule_id) ?? { rule, results: [], statuses: [], blind: 0 };
      if (!rule.results.length && rule.status === 'cannot_tell') entry.blind += 1;
      entry.results.push(...rule.results);
      const status = ruleCheckStatus(rule);
      if (status) entry.statuses.push(status);
      seen.set(rule.rule_id, entry);
    }
  const order = [
    ...(pack?.rules.map((r) => r.id) ?? []).filter((id) => seen.has(id)),
    ...[...seen.keys()].filter((id) => !pack?.rules.some((r) => r.id === id)),
  ];
  return order.map((id) => {
    const { rule, results, statuses, blind } = seen.get(id) ?? {
      rule: null,
      results: [],
      statuses: [],
      blind: 0,
    };
    const count = (s: CheckStatus) => results.filter((r) => r.status === s).length;
    return {
      id,
      title: rule?.title ?? id,
      ref: rule?.clause.ref ?? '',
      pass: count('pass'),
      fail: count('fail'),
      cannot_tell: count('cannot_tell'),
      blind,
      status: checkStatusOf(statuses.map((status) => ({ status }))) ?? 'not_applicable',
    };
  });
}

/** Rules by status (CK-4, as the conflicts screen's checks row); a rule that does not apply is not counted. */
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

/**
 * A drawing's failed results, then its cannot-tell ones, each in rule order then result order. A rule that cannot
 * tell without any result (nothing read) is one entry with `result: null`, in the cannot-tell group.
 */
export function drawingResults(
  d: DrawingChecks,
): { rule: RuleCheck; result: CheckResult | null }[] {
  type Item = { rule: RuleCheck; result: CheckResult | null; status: CheckStatus };
  const all = d.rules.flatMap((rule): Item[] => {
    if (rule.results.length)
      return rule.results.map((result) => ({ rule, result, status: result.status }));
    return rule.status === 'cannot_tell' ? [{ rule, result: null, status: 'cannot_tell' }] : [];
  });
  return [
    ...all.filter((x) => x.status === 'fail'),
    ...all.filter((x) => x.status === 'cannot_tell'),
  ].map(({ rule, result }) => ({ rule, result }));
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
    const subject = m.role === 'subject';
    // the takeoff MarkView.id when the mark is one; a check-only mark gets a stable id of its own
    const id = m.mark_id ?? `${result.id}:${String(i)}`;
    marks.push({
      id,
      n: subject ? ++n : null,
      state: 'counted',
      label: m.label ?? null,
      ref: m.ref ?? null,
      page: m.page,
      box: m.box,
      polygon: m.polygon ?? null,
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
  return m ? { page: m.page, box: m.box } : null;
}
