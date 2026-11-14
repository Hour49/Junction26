import { describe, expect, it } from 'vitest';
import type { ConflictEntry } from '../api';
import { projectReview } from '../api/fixtures';
import {
  cardState,
  conflictCount,
  inUseIndex,
  ordered,
  parseAnswer,
  progressText,
  ruleIndex,
  subLine,
} from './conflicts';

const base = projectReview.conflicts[0] as ConflictEntry;
const needs: ConflictEntry = {
  ...base,
  needs_person: true,
  conflict: { ...base.conflict, resolution: null },
};
const yours: ConflictEntry = {
  ...base,
  settled: { value: 22.401, at: '2026-11-14T01:30:00Z' },
  value: 22.401,
};

describe('conflicts.ts', () => {
  it('cardState keys on needs_person, then settled, else the rule', () => {
    expect(cardState(base)).toBe('rule');
    expect(cardState(needs)).toBe('open');
    expect(cardState(yours)).toBe('yours');
  });

  it('ruleIndex is the first value equal to the resolution; none without one', () => {
    expect(ruleIndex(base)).toBe(1);
    expect(ruleIndex(needs)).toBe(-1);
  });

  it('inUseIndex follows the row value; none matching or needing a person is -1', () => {
    expect(inUseIndex(base)).toBe(1);
    expect(inUseIndex(yours)).toBe(0);
    expect(
      inUseIndex({ ...base, settled: { value: 7, at: '2026-11-14T01:30:00Z' }, value: 7 }),
    ).toBe(-1);
    expect(inUseIndex(needs)).toBe(-1);
  });

  it('CF-37 ordered: a rule could decide first, then the rest, each in the server order', () => {
    const r = { ...base, quantity: 'r' };
    expect(ordered([needs, base, yours, r]).map((c) => c.quantity)).toEqual([
      base.quantity,
      yours.quantity,
      'r',
      needs.quantity,
    ]);
  });

  it('CF-41 parseAnswer: numbers with a dot or comma; counts whole; else the line to show', () => {
    expect(parseAnswer(' 25,5 ', 'm2')).toBe(25.5);
    expect(parseAnswer('.5', 'm2')).toBe(0.5);
    for (const bad of ['', 'abc', '0', '-3', '1e3', '12 m2'])
      expect(parseAnswer(bad, 'm2')).toBe('Type a number, like 12.5.');
    expect(parseAnswer('12', 'count')).toBe(12);
    expect(parseAnswer('0', 'count')).toBe(0);
    for (const bad of ['2.5', '-1', ''])
      expect(parseAnswer(bad, 'count')).toBe('Type a whole number, like 12.');
  });

  it('conflictCount, subLine and progressText count the states', () => {
    expect(conflictCount(0)).toBe('No conflicts found');
    expect(conflictCount(1)).toBe('1 conflict found');
    expect(conflictCount(3)).toBe('3 conflicts found');
    expect(subLine([base])).toBe('1 settled by a rule.');
    expect(subLine([base, yours, needs])).toBe(
      '1 settled by a rule. 1 settled by you. 1 needs you.',
    );
    expect(subLine([needs, needs])).toBe('2 need you.');
    expect(subLine([])).toBe('Both methods agree wherever two of them measured.');
    expect(progressText([base, yours, needs])).toBe('2 of 3 settled');
  });
});
