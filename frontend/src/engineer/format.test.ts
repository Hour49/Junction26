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

it('EN-88 estimateLine: about the rounded measure and the API sentence; a count only the caveat; null without', () => {
  const q = answerArea.quantity as NonNullable<typeof answerArea.quantity>;
  const est = {
    ...answerArea,
    answer: 179.6,
    quantity: { ...q, estimate: 'the scale estimated from the doors' },
  };
  expect(estimateLine(est)).toBe('about 180 m², the scale estimated from the doors');
  // a count is a whole number: never "about"; the row shows it, the line is the caveat (Bogdan c6881747518)
  const carbon = 'counted by Gemini Carbon, an AI reader: check its marks on the plan';
  const count = {
    ...est,
    answer: 19,
    unit: 'count' as const,
    quantity: { ...q, estimate: carbon },
  };
  expect(estimateLine(count)).toBe(
    'Counted by Gemini Carbon, an AI reader: check its marks on the plan',
  );
  expect(estimateLine({ ...count, answer: 0 })).toBe(
    'Counted by Gemini Carbon, an AI reader: check its marks on the plan',
  );
  // a measure that rounds to 0 is not "about 0 m²": the value as it is
  expect(estimateLine({ ...est, answer: 0.3 })).toBe('0.30 m², the scale estimated from the doors');
  expect(estimateLine(answerArea)).toBeNull();
  expect(estimateLine(answer)).toBeNull();
});
