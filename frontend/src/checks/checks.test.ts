import { describe, expect, it } from 'vitest';
import { must } from '../ingest/testing';
import {
  checkStatusOf,
  drawingResults,
  focusOf,
  limitLine,
  ruleCounts,
  ruleSummary,
  summaryLine,
  valueText,
  viewerMarks,
} from './checks';
import { checks, D1, drawingChecks, pack, result, ruleCheck } from './testing';
import type { ProjectChecks } from './types';

describe('checks.ts', () => {
  it('CK-3 ruleSummary: places per rule over all drawings, pack order, unknown rules after, empty rules marked', () => {
    const extra = {
      ...checks,
      drawings: [
        {
          ...must(checks.drawings[0]),
          rules: [
            {
              ...must(must(checks.drawings[0]).rules[0]),
              rule_id: 'R9',
              title: 'Rule R9',
              results: [result('z', 'R9', 'fail')],
            },
            ...must(checks.drawings[0]).rules,
          ],
        },
        ...checks.drawings.slice(1),
      ],
    };
    const rows = ruleSummary(extra, pack);
    expect(rows.map((r) => [r.id, r.pass, r.fail, r.cannot_tell])).toEqual([
      ['R1', 2, 0, 0],
      ['R2', 1, 1, 0],
      ['R3', 1, 0, 1],
      ['R4', 0, 0, 0],
      ['R9', 0, 1, 0],
    ]);
    // R4 has no result on any drawing (its RuleChecks say not_applicable): it does not apply, never pass or fail
    expect(rows.map((r) => r.status)).toEqual([
      'pass',
      'fail',
      'cannot_tell',
      'not_applicable',
      'fail',
    ]);
    expect(rows[0]?.ref).toBe('Decree 1/2000 § 1');
    expect(ruleSummary(checks, null).map((r) => r.id)).toEqual(['R1', 'R2', 'R3', 'R4']);
  });

  it('CK-4 rules counted by their worst result; a rule that does not apply is not counted; same numbers as CF-30', () => {
    const rows = ruleSummary(checks, pack);
    expect(ruleCounts(rows)).toEqual({ failed: 1, cannotTell: 1, passed: 1 });
    expect(summaryLine(rows, 2)).toBe('1 rule failed, 1 cannot tell, 1 passed, over 2 drawings');
    expect(checkStatusOf([])).toBeNull();
    expect(checkStatusOf([{ status: 'cannot_tell' }, { status: 'fail' }])).toBe('fail');
    expect(checkStatusOf([{ status: 'pass' }, { status: 'cannot_tell' }])).toBe('cannot_tell');
  });

  it('CK-5 drawingResults: failed first, then cannot tell, each in rule then result order; passes left out', () => {
    const d = {
      ...must(checks.drawings[0]),
      rules: [
        { ...must(must(checks.drawings[0]).rules[0]), results: [result('x', 'R1', 'cannot_tell')] },
        {
          ...must(must(checks.drawings[0]).rules[1]),
          results: [
            result('y', 'R2', 'pass'),
            result('w', 'R2', 'fail'),
            result('v', 'R2', 'cannot_tell'),
          ],
        },
      ],
    };
    expect(drawingResults(d).map((r) => r.result?.id)).toEqual(['w', 'x', 'v']);
    expect(drawingResults(d)[0]?.rule.rule_id).toBe('R2');
  });

  it('CK-8 valueText: null reads "not measured", never 0 or the limit', () => {
    expect(valueText(null, 'm')).toBe('not measured');
    expect(valueText(0.75, 'm')).toContain('0.75');
  });

  it("CK-11 viewerMarks: each mark's own mark_id (else result:index), subjects numbered and toned, counted marks counted", () => {
    const r = result('f', 'R2', 'fail');
    const { marks, tones } = viewerMarks({
      ...r,
      marks: [...r.marks, { ...must(r.marks[0]), label: 'Door 2', mark_id: null }],
    });
    expect(marks.map((m) => [m.id, m.n, m.state, m.value, m.label])).toEqual([
      ['m-f', 1, 'counted', null, 'Door f'],
      ['f:1', null, 'counted', null, 'Bedroom'],
      ['f:2', 2, 'counted', null, 'Door 2'],
    ]);
    expect(tones).toEqual({ 'm-f': 'fail', 'f:1': 'counted', 'f:2': 'fail' });
    // one subject: it carries the result's value
    expect(viewerMarks(r).marks[0]?.value).toBe(0.75);
    // optional fields left out by the API read as null, never undefined
    const bare = viewerMarks({ ...r, marks: [{ page: 1, box: [0, 0, 1, 1], role: 'subject' }] });
    expect(bare.marks[0]).toMatchObject({ id: 'f:0', label: null, ref: null, polygon: null });
  });

  it("focusOf: the first subject mark's page and box; null without marks", () => {
    expect(focusOf(result('f', 'R2', 'fail'))).toEqual({ page: 1, box: [0.1, 0.1, 0.2, 0.2] });
    expect(focusOf({ ...result('f', 'R2', 'fail'), marks: [] })).toBeNull();
  });

  it('CK-8 limitLine: "<value> measured, limit …"; a null value reads "not measured, limit …" (no double word)', () => {
    expect(limitLine(result('f', 'R2', 'fail'))).toBe('0.75 m measured, limit at least 0.80 m');
    expect(limitLine(result('d', 'R3', 'cannot_tell'))).toBe('not measured, limit at least 0.80 m');
  });

  it('rule-level status: a RuleCheck cannot_tell with no results is cannot tell (never "does not apply"); not_applicable stays apart', () => {
    const d1 = must(checks.drawings[0]);
    const blind: ProjectChecks = {
      ...checks,
      drawings: [
        drawingChecks(D1, [
          { ...ruleCheck('R1', 1, []), status: 'cannot_tell', why: 'No doors were read.' },
          ruleCheck('R4', 4, []),
        ]),
        ...checks.drawings.slice(1),
      ],
    };
    const rows = ruleSummary(blind, pack);
    expect(rows.find((r) => r.id === 'R1')?.status).toBe('cannot_tell'); // pass on D2 + cannot tell on D1, as CF-30's R3
    const onlyBlind: ProjectChecks = { ...blind, drawings: [must(blind.drawings[0])] };
    const r = ruleSummary(onlyBlind, pack);
    expect(r.map((x) => [x.id, x.status])).toEqual([
      ['R1', 'cannot_tell'],
      ['R4', 'not_applicable'],
    ]);
    expect(ruleCounts(r)).toEqual({ failed: 0, cannotTell: 1, passed: 0 });
    expect(r.map((x) => x.blind)).toEqual([1, 0]); // drawings where the rule could not be told, nothing read
    // the drawing lists the rule-level cannot tell (result null) after its failed results
    const items = drawingResults({
      ...must(onlyBlind.drawings[0]),
      rules: [
        ...must(onlyBlind.drawings[0]).rules,
        ruleCheck('R2', 2, [result('w', 'R2', 'fail')]),
      ],
    });
    expect(items.map((x) => [x.rule.rule_id, x.result?.id ?? null])).toEqual([
      ['R2', 'w'],
      ['R1', null],
    ]);
    expect(d1.rules.length).toBeGreaterThan(0);
  });
});
