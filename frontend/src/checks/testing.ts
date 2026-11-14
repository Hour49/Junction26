// Hand-made #142 fixtures (synthetic rooms and doors; no partner data, no design mock values).
// The four-rule case is the conflicts screen's CF-30 fixture, so both screens can be checked for the same numbers.
import { project } from '../api/fixtures';
import { must } from '../ingest/testing';
import { checkStatusOf } from './checks';
import type {
  CheckResult,
  Clause,
  DrawingChecks,
  ProjectChecks,
  RuleCheck,
  RulePack,
} from './types';

export const NOTE = 'A pre-check of a few rules, not a compliance certificate.';
export const D1 = must(project.drawings[0]).drawing_id;
export const D2 = must(project.drawings[1]).drawing_id;

const clause = (n: number): Clause => ({
  ref: `Decree 1/2000 § ${String(n)}`,
  url: `https://example.org/decree#s${String(n)}`,
  quote: `Säännös ${String(n)}.`,
  quote_en: `Clause ${String(n)}.`,
});

export const pack: RulePack = {
  id: 'fi',
  country: 'FI',
  country_name: 'Finland',
  name: 'Finnish building rules (pre-check)',
  law: 'Decree 1/2000',
  version: '2026-11',
  note: NOTE,
  rules: ['R1', 'R2', 'R3', 'R4'].map((id, i) => ({
    id,
    title: `Rule ${id}`,
    op: '>=',
    comparison: '>=',
    comparison_text: 'at least',
    limit: 0.8,
    unit: 'm',
    applies_to: ['door'],
    clause: clause(i + 1),
  })),
};

export function result(
  id: string,
  rule: string,
  status: CheckResult['status'],
  over: Partial<CheckResult> = {},
): CheckResult {
  return {
    id,
    rule_id: rule,
    status,
    subject: { kind: 'element', ref: `door-${id}`, label: `Door ${id}` },
    value: status === 'cannot_tell' ? null : status === 'pass' ? 0.9 : 0.75,
    limit: 0.8,
    unit: 'm',
    comparison: '>=',
    comparison_text: 'at least',
    why: `Why ${id}.`,
    mark_id: `m-${id}`,
    marks: [
      {
        page: 1,
        box: [0.1, 0.1, 0.2, 0.2],
        polygon: null,
        ref: null,
        label: `Door ${id}`,
        role: 'subject',
      },
      {
        page: 1,
        box: [0.3, 0.3, 0.4, 0.4],
        polygon: null,
        ref: null,
        label: 'Bedroom',
        role: 'counted',
      },
    ],
    quantity: 'door',
    ...over,
  };
}

const ruleCheck = (id: string, n: number, results: CheckResult[]): RuleCheck => ({
  rule_id: id,
  title: `Rule ${id}`,
  status: checkStatusOf(results) ?? 'pass',
  why: '',
  clause: clause(n),
  results,
});

const drawingChecks = (drawing_id: string, rules: RuleCheck[]): DrawingChecks => ({
  drawing_id,
  pack: 'fi',
  note: NOTE,
  status: checkStatusOf(rules.flatMap((r) => r.results)) ?? 'pass',
  rules,
});

/** CF-30: R1 passes on both, R2 passes on D1 and fails on D2, R3 passes and cannot tell, R4 has no results. */
export const checks: ProjectChecks = {
  project_id: project.id,
  pack: 'fi',
  note: NOTE,
  drawings: [
    drawingChecks(D1, [
      ruleCheck('R1', 1, [result('a', 'R1', 'pass')]),
      ruleCheck('R2', 2, [result('b', 'R2', 'pass')]),
      ruleCheck('R3', 3, [result('c', 'R3', 'pass'), result('d', 'R3', 'cannot_tell')]),
      ruleCheck('R4', 4, []),
    ]),
    drawingChecks(D2, [
      ruleCheck('R1', 1, [result('e', 'R1', 'pass')]),
      ruleCheck('R2', 2, [result('f', 'R2', 'fail')]),
    ]),
  ],
};
