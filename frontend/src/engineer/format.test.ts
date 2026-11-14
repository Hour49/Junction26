import { describe, expect, it } from 'vitest';
import { estimateLine, formatCost, formatLatency, formatScore, statusWord } from './format';
import { answer, answerArea } from '../api/fixtures';

describe('engineer format', () => {
  it('EN-25 cost, latency and score', () => {
    expect(formatCost(0)).toBe('$0');
    expect(formatCost(0.0004)).toBe('$0.0004');
    expect(formatCost(0.123)).toBe('$0.12');
    expect(formatLatency(0.0001622)).toBe('0.2 ms');
    expect(formatLatency(0.002)).toBe('2.0 ms');
    expect(formatLatency(1.25)).toBe('1.25 s');
    expect(formatScore(0.87)).toBe('0.87');
  });

  it('EN-31 status words', () => {
    expect(statusWord('signed')).toBe('Verified');
    expect(statusWord('conflict')).toBe('Methods disagree');
    expect(statusWord('estimate')).toBe('Estimate');
    expect(statusWord('edited')).toBe('Changed in review');
    expect(statusWord('agree')).toBe('Two methods agree');
    expect(statusWord('single')).toBe('One method');
  });
});

it('EN-88 estimateLine: rounded value, unit and the API sentence; a count gets the caveat alone; null without an estimate', () => {
  const q = answerArea.quantity as NonNullable<typeof answerArea.quantity>;
  const est = {
    ...answerArea,
    answer: 179.6,
    quantity: { ...q, estimate: 'the scale estimated from the doors' },
  };
  expect(estimateLine(est)).toBe('about 180 m², the scale estimated from the doors');
  // a count is counted, not estimated: the caveat alone, no "about", no number repeated
  expect(
    estimateLine({
      ...est,
      answer: 12,
      unit: 'count',
      quantity: { ...q, estimate: 'read from a page flagged at upload: x' },
    }),
  ).toBe('Read from a page flagged at upload: x');
  expect(estimateLine(answerArea)).toBeNull();
  expect(estimateLine(answer)).toBeNull();
});
