import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { Issue } from '../api';
import { projectIssues } from '../api/fixtures';
import { issueRoute } from '../surveyor/issueLinks';
import {
  counts,
  filterIssues,
  issueMarks,
  issueTones,
  kindOf,
  numbered,
  placeOf,
  routeOf,
} from './issues';
import { DRAWING_B, DRAWING_IFC, PID, issues } from './testing';

const byId = (id: string) => {
  const found = issues.find((i) => i.id === id);
  if (!found) throw new Error(id);
  return found;
};
const query = (href: string) => new URLSearchParams(href.split('?')[1] ?? '');
const linksOf = (issue: Issue, pack: string | null = null) =>
  Object.fromEntries(routeOf(issue, PID, pack).map((l) => [l.label, l.href]));

describe('issues.ts', () => {
  it('IS-2 numbered keeps the API order and gives n = 1-based position', () => {
    expect(numbered(issues).map((r) => [r.n, r.issue.id])).toEqual(
      issues.map((i, k) => [k + 1, i.id]),
    );
  });

  it('IS-3 placeOf: file, floor, page or the whole drawing or not on a drawing', () => {
    expect(placeOf(byId('i-conflict'))).toBe('plans/flat-b.pdf · floor 1 · page 1');
    expect(placeOf({ ...byId('i-conflict'), floor: null, page: 2 })).toBe(
      'plans/flat-b.pdf · floor not stated · page 2',
    );
    expect(placeOf(byId('i-ifc'))).toBe('model/house.ifc · floor Ground floor · the whole drawing');
    expect(placeOf(byId('i-aside'))).toBe('photos/site.jpg · floor not stated · not on a drawing');
  });

  it('IS-4 counts by state, zero states left out', () => {
    expect(counts(issues)).toBe('3 open · 1 settled · 1 signed off');
    expect(counts(issues.filter((i) => i.state === 'open'))).toBe('3 open');
    expect(counts([])).toBe('');
  });

  it('IS-5 filterIssues keeps the original n', () => {
    const rows = filterIssues(numbered(issues), { kind: 'set_aside', state: '' });
    expect(rows.map((r) => [r.n, r.issue.id])).toEqual([[5, 'i-aside']]);
    expect(filterIssues(numbered(issues), { kind: '', state: 'open' }).map((r) => r.n)).toEqual([
      1, 2, 3,
    ]);
    expect(filterIssues(numbered(issues), { kind: 'set_aside', state: 'open' })).toEqual([]);
  });

  it('IS-8 issueMarks: located issues of that drawing only, from the issue alone', () => {
    const marks = issueMarks(numbered(issues), DRAWING_B);
    expect(marks.map((m) => [m.id, m.n])).toEqual([
      ['i-check', 1],
      ['i-conflict', 2],
    ]);
    expect(marks[0]).toEqual({
      id: 'i-check',
      n: 1,
      page: 1,
      box: byId('i-check').box,
      polygon: byId('i-check').polygon,
      label: 'Fails a code rule',
      state: 'counted',
      value: null,
      reason: null,
      ref: null,
      room_type: null,
    });
    expect(marks[1]?.polygon).toBeNull();
    expect(issueMarks(numbered(issues), DRAWING_IFC)).toEqual([]);
    // fe-golden: the plan words a mark by its severity, not "counted" (viewer.md tones)
    expect(issueTones(numbered(issues), DRAWING_B)).toEqual({
      'i-check': 'fail',
      'i-conflict': 'needs_person',
    });
  });

  it('IS-11 routeOf: the settling screen per kind, Open the drawing for located ones, pack kept', () => {
    const conflict = linksOf(byId('i-conflict'));
    // one source for the two kinds that land on fe-surveyor's / the ask screens
    expect(conflict.Settle).toBe(issueRoute(byId('i-conflict'), PID, null));
    expect(query(must(conflict.Settle)).get('q')).toBe('area:room|name=1.01');
    // a conflict already settled or signed off: same route, a neutral word, nothing left to settle
    for (const state of ['settled', 'signed_off'] as const) {
      const done = linksOf({ ...byId('i-conflict'), state });
      expect(done.Settle).toBeUndefined();
      expect(done['See the conflict']).toBe(conflict.Settle);
    }
    const open = must(conflict['Open the drawing']);
    expect(open.startsWith(`#/p/${PID}/d/${DRAWING_B}/engineer?`)).toBe(true);
    expect(query(open).get('page')).toBe('1');
    expect(query(open).get('box')).toBe('0.1,0.2,0.3,0.4');

    expect(linksOf(byId('i-refused'))['Ask again']).toBe(issueRoute(byId('i-refused'), PID, null));
    expect(query(must(linksOf(byId('i-refused'))['Ask again'])).get('ask')).toBe(
      'How many saunas are there?',
    );
    expect(Object.keys(linksOf(byId('i-refused')))).toEqual(['Ask again']);
    // the ask route asks on open (EN-72, CH-14), so the word says so in every state
    expect(Object.keys(linksOf({ ...byId('i-refused'), state: 'settled' }))).toEqual(['Ask again']);

    expect(linksOf(byId('i-aside'))).toEqual({ 'Why it was set aside': `#/p/${PID}/f/f7` });

    const flag = linksOf(byId('i-ifc'));
    expect(flag['Open in the surveyor']).toBe(`#/p/${PID}/d/${DRAWING_IFC}/surveyor`);
    expect(flag['Open the drawing']).toBeUndefined(); // page null: not located

    const check = linksOf(byId('i-check'), 'fi');
    expect(query(must(check['Open in the surveyor'])).get('q')).toBe('door');
    expect(check['See the check']).toBe(`#/p/${PID}/checks?pack=fi`);
    for (const href of Object.values(check)) expect(query(href).get('pack')).toBe('fi');
  });

  describe('unrelated_file (file-triage.md)', () => {
    const base = projectIssues.issues[0];
    if (!base) throw new Error('project_issues.json has no issue');
    const unrelated: Issue = {
      ...base,
      kind: 'unrelated_file',
      severity: 'note',
      state: 'open',
      drawing_id: null,
      page: null,
      box: null,
      polygon: null,
      mark_id: null,
      file_id: 'f3',
      reason: 'unrelated',
      links: { ...base.links, trace: `/api/projects/${PID}/files/f3/trace` },
    };

    it('FT-15 kind word, place, and one link to the trace: Make a call, then See the call', () => {
      expect(kindOf('unrelated_file')).toEqual({ word: 'Not a floor plan', icon: '▭' });
      expect(placeOf(unrelated)).toContain('not on a drawing');
      expect(linksOf(unrelated)).toEqual({ 'Make a call': `#/p/${PID}/f/f3` });
      expect(linksOf({ ...unrelated, state: 'settled' })).toEqual({
        'See the call': `#/p/${PID}/f/f3`,
      });
      expect(linksOf(unrelated, 'fi')).toEqual({ 'Make a call': `#/p/${PID}/f/f3?pack=fi` });
    });

    it('FT-16 n is the position in the list as loaded; a state change leaves the order, Issue.id is the reference', () => {
      const before = numbered([...issues, unrelated]);
      const after = numbered([...issues, { ...unrelated, state: 'settled' }]);
      expect(after.map((r) => [r.n, r.issue.id])).toEqual(before.map((r) => [r.n, r.issue.id]));
    });
  });

  it('IS-15 kindOf: an unknown kind is its raw id with no icon', () => {
    expect(kindOf('conflict')).toEqual({ word: 'Conflict', icon: '⇄' });
    expect(kindOf('double_check').word).toBe('Double-check');
    expect(kindOf('new_kind')).toEqual({ word: 'new_kind', icon: '' });
  });

  it('IS-18 issues.css: no colour literal; the sticky plan sits under the header', () => {
    const css = readFileSync('src/issues/issues.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    expect(css).toContain('top: var(--v-header-h');
  });
});

function must<T>(value: T | undefined): T {
  if (value === undefined) throw new Error('expected a value');
  return value;
}
