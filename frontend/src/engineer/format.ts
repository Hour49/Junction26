// The engineer screen's own words and numbers; values and times use the shared formatValue/formatTime.
import type { Row } from '../api';

export function formatCost(usd: number): string {
  if (usd === 0) return '$0';
  return `$${usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2)}`;
}

export function formatLatency(seconds: number): string {
  return seconds < 1 ? `${(seconds * 1000).toFixed(1)} ms` : `${seconds.toFixed(2)} s`;
}

// A raw model choice score, never a percent: it is not a probability.
export function formatScore(score: number): string {
  return score.toFixed(2);
}

const STATUS_WORDS: Record<Row['status'], string> = {
  signed: 'Verified',
  conflict: 'Methods disagree',
  estimate: 'Estimate',
  edited: 'Changed in review',
  agree: 'Two methods agree',
  single: 'One method',
};

export function statusWord(status: Row['status']): string {
  return STATUS_WORDS[status];
}
