import { describe, expect, it } from 'vitest';
import type { ConflictEntry } from '../api';
import { projectReview, projectReviewResolved, resolving } from '../api/fixtures';
import {
  cardState,
  conflictCount,
  inUseIndex,
  ordered,
  newSuggestions,
  parseAnswer,
  progressText,
  ruleIndex,
  subLine,
  whyText,
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

  it('CF-41 parseAnswer: a number (dot or comma, unit allowed) is a value, words are a note', () => {
    expect(parseAnswer(' 25,5 ', 'm2')).toEqual({ value: 25.5 });
    expect(parseAnswer('25.5 m²', 'm2')).toEqual({ value: 25.5 });
    expect(parseAnswer('.5', 'm2')).toEqual({ value: 0.5 });
    expect(parseAnswer('room 1.01 is the kitchen', 'm2')).toEqual({
      note: 'room 1.01 is the kitchen',
    });
    expect(parseAnswer('0', 'm2')).toBe('Type a number above 0, or a few words.');
    expect(parseAnswer('  ', 'm2')).toBe('Type a number or a few words.');
    expect(parseAnswer('12', 'count')).toEqual({ value: 12 });
    expect(parseAnswer('0', 'count')).toEqual({ value: 0 });
    expect(parseAnswer('2.5', 'count')).toBe('Type a whole number, like 12.');
    expect(parseAnswer('two are the same door', 'count')).toEqual({
      note: 'two are the same door',
    });
  });

  it('CF-51 newSuggestions keeps only what no variant says', () => {
    expect(newSuggestions({ ...base, suggestions: ['22.40 m²', '30.00 m²'] })).toEqual([]);
    expect(newSuggestions({ ...base, suggestions: ['30 m²', 'Both rooms', '25 m²'] })).toEqual([
      'Both rooms',
      '25 m²',
    ]);
    expect(newSuggestions({ ...base, suggestions: undefined as unknown as string[] })).toEqual([]);
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

  const picked = projectReviewResolved.conflicts[0] as ConflictEntry;
  const cannot = resolving.review.conflicts[0] as ConflictEntry;

  it('RS-10 / RS-12 a pick in use is its own state, before the rule; cannot_tell stays open', () => {
    expect(cardState(picked)).toBe('picked');
    expect(inUseIndex(picked)).toBe(0); // the tile at the pick, 22.401
    expect(cardState({ ...picked, settled: { value: 30, at: '2026-11-14T01:30:00Z' } })).toBe(
      'yours',
    );
    expect(cardState({ ...base, resolved: picked.resolved })).toBe('picked');
    expect(cardState(cannot)).toBe('open');
    expect(inUseIndex(cannot)).toBe(-1);
  });

  it('RS-13 subLine counts picks apart; progressText counts a pick as settled', () => {
    expect(subLine([picked])).toBe('1 picked by Carbon, check them.');
    expect(subLine([base, picked, picked, needs])).toBe(
      '1 settled by a rule. 2 picked by Carbon, check them. 1 needs you.',
    );
    expect(progressText([picked, cannot])).toBe('1 of 2 settled');
  });

  it("RS-15 whyText stops after 'No rule decides between them.' when a model answered", () => {
    const cut =
      "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by the printed room areas. No rule decides between them.";
    expect(whyText(picked)).toBe(cut);
    expect(whyText(cannot)).toBe(cut);
    expect(whyText(picked)).not.toMatch(/gemini|carbon:/);
    expect(whyText(base)).toBe(base.why);
    expect(whyText({ ...picked, why: 'A model (carbon:x) picked it.' })).toBe('');
  });
});
