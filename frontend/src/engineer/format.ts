// The engineer screen's own words and numbers; values and times use the shared formatValue/formatTime.
import type { AnswerView, Row } from '../api';

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

/** Bogdan's rule (#14 c6874945888): the Sure check, else the second reader's score; none without a score. */
export function gradeOf(a: AnswerView): Grade | null {
  if (a.line.sure === true) return 'High';
  if (!a.confidence) return null;
  return a.confidence.score >= 0.8 ? 'Medium' : 'Low';
}

export const GRADE_TIP = "From the Sure check and the second reader's score (0.8 or more: Medium).";
