// File triage words and rules (docs/specs/frontend/file-triage.md "Words", decision 0010).
import type { FileStatus, Triage } from '../api';
import { ApiError, errorText } from '../api/errors';
import { formatTime } from '../api/format';

type Verdict = NonNullable<Triage['verdict']>;

export const CLASS_LABEL: Record<Triage['class'], string> = {
  floor_plan: 'a floor plan',
  other_drawing: 'another kind of drawing',
  not_drawing: 'not a drawing',
};

const label = (icon: string, word: string, sentence: string) => ({
  word,
  pill: `${icon} ${word}`,
  sentence,
});

export const VERDICT_LABEL: Record<
  Verdict | 'none',
  { word: string; pill: string; sentence: string }
> = {
  related: label('✓', 'Related', 'Related to this project'),
  unrelated: label('✕', 'Not related', 'Not related to this project'),
  unsure: label('?', 'Unsure', 'Unsure whether it belongs to this project'),
  none: label('–', 'Not judged', 'Not judged'),
};

export const verdictOf = (t: Pick<Triage, 'verdict'>) => VERDICT_LABEL[t.verdict ?? 'none'];

/** A file triage looked at and set aside as not a floor plan. */
export const isNotPlan = (f: FileStatus) => !!f.triage && f.triage.class !== 'floor_plan';

/** Any non-plan, described or not (#183 lifted the 422 `no-description`; its line stays for older servers). */
export const canCall = isNotPlan;

/** Reserved route, built (#166): a set-aside non-plan nobody had read as a plan yet; no undo. */
export const canReadAsPlan = (f: FileStatus) =>
  isNotPlan(f) && !f.triage?.read_as_plan && f.state === 'set_aside';

export const readLine = (r: { by: string; at: string }) =>
  `${r.by} had it read as a floor plan, ${formatTime(r.at)}`;

export const planChance = (p: number) => `${String(Math.round(100 * p))} %`;

/** The card heading (FT-24): the sheet model's words when it set the file aside (#251), else the class words. */
export function notPlanLine(t: Triage): string {
  const s = t.sheet;
  if (s?.decision !== 'set_aside') return `Not a floor plan: ${CLASS_LABEL[t.class]}`;
  const more = [s.title, s.sheet_number].filter(Boolean).join(', ');
  return `Not a floor plan: ${s.kind_words}${more ? ` (${more})` : ''}`;
}

// the backend's SHEET_PLAN_KINDS (app/core/ingest/model.py)
const SHEET_PLAN_KINDS = new Set(['architectural_floor_plan', 'multi_view_sheet']);

/** FT-25: "Looks like: <kind_words>" for a sheet the model doubts (read anyway) of a non-plan kind; else null. */
export function looksLike(t: Triage): string | null {
  const s = t.sheet;
  return s?.decision === 'doubt' && !SHEET_PLAN_KINDS.has(s.kind)
    ? `Looks like: ${s.kind_words}`
    : null;
}

/** The class words with what the sheet looks like (FT-25); a non-plan's per FT-24. */
export function classLine(t: Triage): string {
  const hint = looksLike(t);
  const line = t.class === 'floor_plan' ? 'A floor plan' : notPlanLine(t);
  return hint ? `${line} · ${hint}` : line;
}

export function rowLine(t: Triage): string {
  const subject = t.sheet?.decision === 'set_aside' ? null : t.description?.subject;
  return `${classLine(t)}${subject ? ` · ${subject}` : ''}`;
}

/** "Related to this project: Ana’s call, <time>. The judge said: Not related."; null with no call. */
export function callLine(t: Triage): string | null {
  const call = t.overruled;
  if (!call) return null;
  const judge = t.relevance ? ` The judge said: ${VERDICT_LABEL[t.relevance.verdict].word}.` : '';
  return `${VERDICT_LABEL[call.verdict].sentence}: ${call.by}’s call, ${formatTime(call.at)}.${judge}`;
}

export function callError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : '';
  if (code === 'not-allowed')
    return 'The project is still being read: a call can be made once it is done.';
  if (code === 'no-description')
    return 'This file was not described, so there is nothing to judge or overrule.';
  const { detail } = errorText(error);
  if (code === 'not-found') return `This file is no longer in the project. (${detail})`;
  return detail;
}

export function readError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : '';
  if (code === 'not-allowed')
    return 'The project is still being read, or this file is being read again already.';
  if (code === 'not-triaged')
    return 'Triage did not set this file aside, so there is nothing to read again.';
  return errorText(error).detail;
}
