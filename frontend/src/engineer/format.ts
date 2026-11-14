// The engineer screen's own words and numbers; values and times use the shared formatValue/formatTime.
import { formatValue, type AnswerView, type Row } from '../api';

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

// The status pill's tooltip (engineer.md "Status tooltips").
const STATUS_TIPS: Record<Row['status'], string> = {
  signed: 'A surveyor checked this value and signed it off.',
  agree: 'Two independent methods measured this and got the same value.',
  conflict:
    'Two methods measured different values; the checks below say which one is kept and why.',
  estimate: 'Measured with an estimated scale or method; treat it as approximate.',
  edited: 'A surveyor changed this value in review.',
  single: 'Only one method measured this; there is no second check.',
};

export function statusTip(status: Row['status']): string {
  return STATUS_TIPS[status];
}

const KINDS: Record<string, string> = {
  pdf_vector: 'PDF vector',
  pdf_scan: 'PDF scan',
  png_plan: 'PNG plan',
  jpeg_plan: 'JPEG plan',
  photo_plan: 'photo of a plan',
  ifc: 'IFC model',
  dxf: 'DXF',
  svg: 'SVG',
};

/** A drawing kind in words; other ids as sent (engineer.md Open point 8: local until a shared one). */
export function kindName(kind: string | null | undefined): string {
  return kind ? (KINDS[kind] ?? kind) : 'unknown kind';
}

export type Grade = 'High' | 'Medium' | 'Low';

const LEVEL_WORD = { high: 'High', medium: 'Medium', low: 'Low' } as const;

/** The backend's confidence level (#233, Bogdan #14 c6879176847); null without one, no score rule (EN-82). */
export function gradeOf(a: { level?: AnswerView['level'] }): Grade | null {
  return a.level ? LEVEL_WORD[a.level.level] : null;
}

/** `ProjectAnswer.total_level` in words (CH-42). */
export const levelWord = (level: keyof typeof LEVEL_WORD): Grade => LEVEL_WORD[level];

/** EN-88/CH-44: "about 180 m², <why the value is an estimate>" for a measured number with `quantity.estimate`;
 * for a count only the caveat ("Counted by …"): a count is whole, never "about" (Bogdan c6881747518); else null. */
export function estimateLine(a: AnswerView): string | null {
  const why = a.quantity?.estimate;
  if (!why || typeof a.answer !== 'number') return null;
  if (a.unit === 'count') return why.charAt(0).toUpperCase() + why.slice(1);
  const n = Math.round(a.answer);
  // "about 0 m²" says nothing: a measure that rounds to 0 is shown as it is
  if (n === 0) return `${formatValue(a.answer, a.unit)}, ${why}`;
  // a whole number: formatValue's two decimals would claim a precision the estimate has not
  return `about ${formatValue(n, a.unit).replace(/\.00 /, ' ')}, ${why}`;
}
