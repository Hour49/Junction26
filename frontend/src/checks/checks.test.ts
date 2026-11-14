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
import { checks, pack, result } from './testing';

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
    expect(rows.map((r) => r.status)).toEqual(['pass', 'fail', 'cannot_tell', null, 'fail']);
    expect(rows[0]?.ref).toBe('Decree 1/2000 § 1');
    expect(ruleSummary(checks, null).map((r) => r.id)).toEqual(['R1', 'R2', 'R3', 'R4']);
  });

  it('CK-4 rules counted by their worst result; no result not counted; same numbers as CF-30', () => {
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
    expect(drawingResults(d).map((r) => r.result.id)).toEqual(['w', 'x', 'v']);
    expect(drawingResults(d)[0]?.rule.rule_id).toBe('R2');
  });

  it('CK-8 valueText: null reads "not measured", never 0 or the limit', () => {
    expect(valueText(null, 'm')).toBe('not measured');
    expect(valueText(0.75, 'm')).toContain('0.75');
  });

  it('CK-11 viewerMarks: result.mark_id for the first subject (else result:index), subjects numbered and toned, counted marks counted', () => {
    const r = result('f', 'R2', 'fail');
    const { marks, tones } = viewerMarks({
      ...r,
      marks: [...r.marks, { ...must(r.marks[0]), label: 'Door 2' }],
    });
    expect(marks.map((m) => [m.id, m.n, m.state, m.value])).toEqual([
      ['m-f', 1, 'counted', null],
      ['f:1', null, 'counted', null],
      ['f:2', 2, 'counted', null],
    ]);
    expect(tones).toEqual({ 'm-f': 'fail', 'f:1': 'counted', 'f:2': 'fail' });
    // one subject: it carries the result's value
    expect(viewerMarks(r).marks[0]?.value).toBe(0.75);
    // a polygon-only mark gets its box from the polygon
    const poly = viewerMarks({
      ...r,
      marks: [
        {
          ...must(r.marks[0]),
          box: null,
          polygon: [
            [0.1, 0.2],
            [0.5, 0.2],
            [0.5, 0.6],
          ],
        },
      ],
    });
    expect(poly.marks[0]?.box).toEqual([0.1, 0.2, 0.5, 0.6]);
  });

  it("focusOf: the first subject mark's page and box; null without marks", () => {
    expect(focusOf(result('f', 'R2', 'fail'))).toEqual({ page: 1, box: [0.1, 0.1, 0.2, 0.2] });
    expect(focusOf({ ...result('f', 'R2', 'fail'), marks: [] })).toBeNull();
  });

  it('CK-8 limitLine: "<value> measured, limit …"; a null value reads "not measured, limit …" (no double word)', () => {
    expect(limitLine(result('f', 'R2', 'fail'))).toBe('0.75 m measured, limit at least 0.80 m');
    expect(limitLine(result('d', 'R3', 'cannot_tell'))).toBe('not measured, limit at least 0.80 m');
  });
});
