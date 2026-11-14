import { describe, expect, it } from 'vitest';
import { answer, answerArea, answerRefused } from '../api/fixtures';
import { patch, requestLine, stateOf, toViewer } from './check';
import {
  asking,
  check,
  doubtM2,
  doubtUnmarked,
  reasked,
  takeoffWithDoor,
  withCheck,
} from './testing';

describe('check.ts', () => {
  it('stateOf: hidden without a check, a row or a number; checked once signed; else needs', () => {
    expect(stateOf(answer)).toBe('hidden'); // no check field (until Bogdan's PR)
    expect(stateOf(withCheck(answer, null))).toBe('hidden');
    expect(stateOf(withCheck(answerRefused, check))).toBe('hidden');
    expect(stateOf(withCheck({ ...answer, quantity: null }, check))).toBe('hidden');
    expect(stateOf(asking)).toBe('needs');
    expect(stateOf(reasked)).toBe('checked');
  });

  it('requestLine counts the disputes with the row noun; rooms for areas; none: this value', () => {
    expect(requestLine(asking, check)).toBe(
      "Please double-check: we're not sure about 1 of these doors.",
    );
    const two = { ...check, disputed: [doubtM2, doubtUnmarked] };
    expect(requestLine(asking, two)).toBe(
      "Please double-check: we're not sure about 2 of these doors.",
    );
    const area = withCheck(
      { ...answerArea, quantity: answerArea.quantity && { ...answerArea.quantity, noun: null } },
      check,
    );
    expect(requestLine(area, check)).toBe(
      "Please double-check: we're not sure about 1 of these rooms.",
    );
    expect(requestLine(asking, { ...check, disputed: [] })).toBe('Please double-check this value.');
  });

  it('toViewer: a mark item names its mark, an unmarked one its page and box', () => {
    expect(toViewer([doubtM2, doubtUnmarked])).toEqual([
      { markId: 'm2', page: 1, why: doubtM2.why },
      { page: 1, box: doubtUnmarked.box, why: doubtUnmarked.why },
    ]);
  });

  it("patch takes the row's value, row and marks, and keeps the check", () => {
    const row = takeoffWithDoor({ value: 1 }).quantities.find((q) => q.key === 'door');
    if (!row) throw new Error('no door row');
    const next = patch(asking, row);
    expect(next.answer).toBe(1);
    expect(next.quantity).toBe(row);
    expect(next.marks).toBe(row.marks);
    expect((next as { check?: unknown }).check).toEqual(check);
  });
});
