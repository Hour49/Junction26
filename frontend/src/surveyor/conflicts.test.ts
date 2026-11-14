import { describe, expect, it } from 'vitest';
import type { ConflictEntry } from '../api';
import { projectReview } from '../api/fixtures';
import {
  cardState,
  conflictCount,
  inUseIndex,
  letter,
  progressText,
  ruleIndex,
  subLine,
  workspaceDrawing,
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

  it('letter gives A, B, C', () => {
    expect([0, 1, 2].map(letter)).toEqual(['A', 'B', 'C']);
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

  it('workspaceDrawing is the first drawing with quantities, else the first, else none', () => {
    expect(workspaceDrawing(projectReview.drawings)).toBe('adeefbbcc17559fc');
    const empty = projectReview.drawings.map((d) => ({ ...d, quantities: 0 }));
    expect(workspaceDrawing(empty)).toBe('adeefbbcc17559fc');
    expect(workspaceDrawing([])).toBeNull();
  });
});
