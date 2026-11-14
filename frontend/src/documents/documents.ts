// Pure helpers of the Documents tab (docs/specs/frontend/documents.md).
import { previewUrl, type DrawingView, type FileStatus, type Issue } from '../api';
import { SEVERITIES, SEVERITY_LABEL, numbered, type Row } from '../issues/issues';
import type { Source } from '../viewer/SourceFigure';

/** The issues Documents lists: conflicts left out (answered on Ingest), grouped by severity, in the API's order
 * within a group; `n` = the position in this list (Issue.id is the reference, not `n`). */
export function documentIssues(issues: readonly Issue[]): Row[] {
  const shown = issues.filter((i) => i.kind !== 'conflict');
  return numbered(SEVERITIES.flatMap((s) => shown.filter((i) => i.severity === s)));
}

/** Documents lets a person answer it: never a conflict; a note only when it is an `unrelated_file` (the call). */
export const isAnswerable = (i: Issue) =>
  i.kind !== 'conflict' && (i.kind === 'unrelated_file' || i.severity !== 'note');

/** The one count rule (DOC-12): answerable, still open, not answered, notes excluded. Badge and done line use it. */
export const needsYou = (issues: readonly Issue[], answers: ReadonlyMap<string, string>) =>
  issues.filter(
    (i) => isAnswerable(i) && i.severity !== 'note' && i.state === 'open' && !answers.has(i.id),
  ).length;

export function pillOf(
  issue: Issue,
  answered: boolean,
): { word: string; tone: '' | 'warn' | 'ok' } {
  if (isAnswerable(issue) && (answered || issue.state !== 'open'))
    return { word: 'Answered', tone: 'ok' };
  if (issue.severity === 'note') return { word: 'Note', tone: '' };
  return { word: SEVERITY_LABEL[issue.severity], tone: 'warn' };
}

// API.md "…/preview.png": images and a PDF's first page; 404 for any other file
const PREVIEWABLE = new Set([
  'png_plan',
  'jpeg_plan',
  'photo_plan',
  'photo',
  'pdf_vector',
  'pdf_scan',
  'pdf_text',
]);

/** The issue's one source for `SourceFigure`, or null when there is nothing to show. */
export function issueSource(
  issue: Issue,
  projectId: string,
  drawing: DrawingView | null | undefined,
  file?: Pick<FileStatus, 'kind'>,
): Source | null {
  if (issue.drawing_id) {
    const page =
      issue.page !== null ? (drawing?.pages.find((p) => p.page === issue.page) ?? null) : null;
    const located = issue.box || issue.polygon;
    return {
      name: issue.file,
      page,
      places: located ? [{ label: issue.why, box: issue.box, polygon: issue.polygon }] : [],
    };
  }
  if (!issue.file_id || !PREVIEWABLE.has(file?.kind ?? '')) return null;
  return {
    name: issue.file,
    page: null,
    image: previewUrl(projectId, issue.file_id, 400),
    places: [],
  };
}

/** A file row's reason (DOC-17, as the demo): only a set-aside file's, its trailing technical parenthetical cut. */
export function shortReason(f: Pick<FileStatus, 'state' | 'reason'>): string | null {
  if (f.state !== 'set_aside') return null;
  return f.reason.replace(/\s*\([^()]*\)\s*$/, '') || null;
}
