// Pure view data for the workspaces screen (docs/specs/frontend/account.md): list lines, stats and history.
import {
  formatValue,
  type ProjectReview,
  type ProjectSummary,
  type ProjectView,
  type Takeoff,
} from '../api';
import { formatMs, formatSize, plural, progressOf } from '../ingest/ingest';
import { questionsOf } from './pending';

export function workspaceKind(p: Pick<ProjectSummary, 'files' | 'drawings'>): string {
  const kind = p.files === 1 ? 'Single file' : 'Archive';
  return `${kind} · ${plural(p.files, 'file')} · ${plural(p.drawings, 'drawing')}`;
}

export type PillTone = 'accent' | 'ok' | 'danger';

export function workspacePill(state: string): { word: string; tone: PillTone } {
  if (state === 'done') return { word: 'Ready', tone: 'ok' };
  if (state === 'failed') return { word: 'Failed', tone: 'danger' };
  return { word: 'Reading', tone: 'accent' };
}

export interface Stat {
  label: string;
  value: string;
  /** The API field this value stands in for while it is mocked (`data-pending`). */
  pending?: string;
}

/** Files, Drawings, Questions, To review, Signed off; the review's read "–" while it is missing. */
export function workspaceStats(project: ProjectView, review: ProjectReview | null): Stat[] {
  const sum = (pick: (d: ProjectReview['drawings'][number]) => number) =>
    review ? review.drawings.reduce((n, d) => n + pick(d), 0) : 0;
  const questions = questionsOf(null, review);
  return [
    { label: 'Files', value: String(project.files.length) },
    { label: 'Drawings', value: String(project.drawings.length) },
    questions
      ? {
          label: 'Questions',
          value: String(questions.n),
          ...(questions.pending && { pending: 'GET /api/projects/{id}/questions' }),
        }
      : { label: 'Questions', value: '–' },
    { label: 'To review', value: review ? String(sum((d) => d.to_review)) : '–' },
    {
      label: 'Signed off',
      value: review
        ? `${String(sum((d) => d.signed))} of ${String(sum((d) => d.quantities))}`
        : '–',
    },
  ];
}

export type EventKind =
  'upload' | 'reading' | 'done' | 'failed' | 'rule' | 'needs' | 'settled' | 'signed';

export interface HistoryEvent {
  kind: EventKind;
  at: string;
  /** `HH:MM`, UTC. */
  time: string;
  glyph: string;
  title: string;
  detail: string;
  /** The API field the time stands in for while it is mocked (`data-pending`). */
  pending?: string;
}

// The table order of account.md "History": the tie-break for equal times.
const ORDER: EventKind[] = [
  'upload',
  'reading',
  'done',
  'failed',
  'rule',
  'needs',
  'settled',
  'signed',
];
const GLYPH: Record<EventKind, string> = {
  upload: '↑',
  reading: '…',
  done: '✓',
  failed: '!',
  rule: '⇄',
  needs: '!',
  settled: '✔',
  signed: '✔',
};

function hhmm(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? '' : at.toISOString().slice(11, 16);
}

/** One event per fact, oldest first. */
export function historyEvents(
  project: ProjectView,
  review: ProjectReview | null,
  takeoffs: Takeoff[],
): HistoryEvent[] {
  const events: Omit<HistoryEvent, 'time' | 'glyph'>[] = [];
  const at = project.created_at;
  // Rule decisions and open conflicts come out of the analysis: they share its end time.
  const end = project.finished_at ?? at;
  const size = project.files.reduce((n, f) => n + f.size, 0);
  events.push({
    kind: 'upload',
    at,
    title: `Uploaded ${project.name}`,
    detail: `${plural(project.files.length, 'file')} · ${formatSize(size)}`,
  });
  if (project.state === 'done') {
    const c = project.counts ?? {};
    const counts = (
      [
        ['ready', 'ready'],
        ['flagged', 'flagged'],
        ['set_aside', 'set aside'],
        ['text_only', 'text only'],
      ] as const
    )
      .filter(([key]) => c[key])
      .map(([key, word]) => `${String(c[key])} ${word}`)
      .join(', ');
    const parts = [plural(project.drawings.length, 'drawing'), counts, formatMs(project.ms)];
    events.push({
      kind: 'done',
      at: end,
      title: 'Analysis done',
      detail: parts.filter(Boolean).join(' · '),
    });
  } else if (project.state === 'failed') {
    events.push({ kind: 'failed', at, title: 'Ingest failed', detail: project.error ?? '' });
  } else {
    const { done, total } = progressOf(project.files);
    events.push({
      kind: 'reading',
      at,
      title: 'Reading the drawings',
      detail: `${String(done)} of ${String(total)} files`,
    });
  }
  for (const c of review?.conflicts ?? []) {
    const unit = c.conflict.values[0]?.unit ?? null;
    const resolution = c.conflict.resolution;
    if (c.settled) {
      events.push({
        kind: 'settled',
        at: c.settled.at,
        title: `Conflict settled: ${c.label}`,
        detail: `${c.file} · kept ${formatValue(c.settled.value, unit)}`,
      });
    } else if (c.needs_person) {
      events.push({
        kind: 'needs',
        at: end,
        title: `Conflict waiting for you: ${c.label}`,
        detail: `${c.file} · ${c.conflict.values.map((v) => formatValue(v.value, v.unit ?? null)).join(' vs ')}`,
      });
    } else if (resolution) {
      events.push({
        kind: 'rule',
        at: end,
        title: `Decided by rule: ${c.label}`,
        detail: `${c.file} · kept ${formatValue(resolution.value, unit)} · ${resolution.rule}`,
      });
    }
  }
  for (const t of takeoffs) {
    for (const q of t.quantities) {
      if (!q.signed) continue;
      events.push({
        kind: 'signed',
        at: q.signed.at,
        title: `Signed off: ${q.label}`,
        detail: `${t.file} · ${formatValue(q.signed.value, q.unit)} · by ${q.signed.by}`,
      });
    }
  }
  return events
    .map((e, i) => ({ e, i, ms: new Date(e.at).getTime() }))
    .sort((a, b) => a.ms - b.ms || ORDER.indexOf(a.e.kind) - ORDER.indexOf(b.e.kind) || a.i - b.i)
    .map(({ e }) => ({ ...e, time: hhmm(e.at), glyph: GLYPH[e.kind] }));
}
