import { describe, expect, it } from 'vitest';
import { formatCost, formatLatency, formatScore, statusWord } from './format';

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
