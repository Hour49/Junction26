// Hand-made fixtures in the generated #139 shapes (synthetic rooms and doors; no partner data, no design mock
// values). The four-rule case is the conflicts screen's CF-30 fixture, so both screens give the same numbers;
// Bogdan's own fixtures (project_checks.json, checks.json, info.json rule_packs) are used by the screen tests too.
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
  RuleStatus,
} from './types';

export const NOTE = 'A pre-check of a few rules, not a compliance certificate.';
export const FAIL_MEANS = "It would not meet today's rule for a new building.";
export const D1 = must(project.drawings[0]).drawing_id;
export const D2 = must(project.drawings[1]).drawing_id;
const fileOf = (did: string) => project.files.find((f) => f.drawing_id === did);

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
  fail_means: FAIL_MEANS,
  rules: ['R1', 'R2', 'R3', 'R4'].map((id, i) => ({
    id,
    title: `Rule ${id}`,
    op: 'door_width',
    applies_to: { room_types: [], not_room_types: [], element_classes: ['door'], skip_labels: [] },
    comparison: '>=',
    comparison_text: 'at least',
    limit: 0.8,
    unit: 'm',
    key: 'door',
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
    marks: [
      {
        page: 1,
        box: [0.1, 0.1, 0.2, 0.2],
        polygon: null,
        ref: null,
        label: `Door ${id}`,
        role: 'subject',
        mark_id: `m-${id}`,
        quantity: 'door',
      },
      {
        page: 1,
        box: [0.3, 0.3, 0.4, 0.4],
        polygon: null,
        ref: null,
        label: 'Bedroom',
        role: 'counted',
        mark_id: null,
        quantity: null,
      },
    ],
    quantity: 'door',
    ...over,
  };
}

export const ruleCheck = (
  id: string,
  n: number,
  results: CheckResult[],
  status: RuleStatus = checkStatusOf(results) ?? 'not_applicable',
): RuleCheck => ({ rule_id: id, title: `Rule ${id}`, status, why: '', clause: clause(n), results });

export const drawingChecks = (drawing_id: string, rules: RuleCheck[]): DrawingChecks => ({
  drawing_id,
  file: fileOf(drawing_id)?.path ?? drawing_id,
  file_id: fileOf(drawing_id)?.id ?? null,
  pack: 'fi',
  note: NOTE,
  status: checkStatusOf(rules.flatMap((r) => r.results)) ?? 'not_applicable',
  rules,
});

/** CF-30: R1 passes on both, R2 passes on D1 and fails on D2, R3 passes and cannot tell, R4 does not apply. */
export const checks: ProjectChecks = {
  project_id: project.id,
  pack: 'fi',
  note: NOTE,
  status: 'fail',
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
      ruleCheck('R4', 4, []),
    ]),
  ],
};
