// Pure view data for the workspaces screen (docs/specs/frontend/account.md): list lines, stats and history.
import {
  formatValue,
  type AskedQuestion,
  type ProjectQuestions,
  type ProjectReview,
  type ProjectSummary,
  type ProjectView,
  type Row,
  type Takeoff,
} from '../api';
import { formatMs, formatSize, plural, progressOf } from '../ingest/ingest';

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
}

/** The questions asked, oldest first: a project-chat question asks every drawing and logs one line each, all
 * sharing `project_ask` (Bogdan #135), so those lines are one ask; a line without it is its own. */
export function asks(questions: ProjectQuestions): AskedQuestion[][] {
  const groups = new Map<string, AskedQuestion[]>();
  // The log is newest first: walk it oldest first so same-second asks keep the order they were asked in.
  [...questions.questions].reverse().forEach((q, i) => {
    const key = q.project_ask ? `ask ${q.project_ask}` : `line ${String(i)}`;
    groups.set(key, [...(groups.get(key) ?? []), q]);
  });
  return [...groups.values()];
}

/** A room keyed under its number and its name is two rows but one disagreement, and one sign-off signs both (#131,
 * Bogdan #14 c6875696292): rows of one drawing sharing `conflict` and `marks` are one entry; others are their own. */
export function disagreements(takeoffs: Takeoff[]): { file: string; rows: Row[] }[] {
  const groups = new Map<string, { file: string; rows: Row[] }>();
  for (const t of takeoffs) {
    for (const row of t.quantities) {
      const key = `${t.drawing_id} ${row.conflict ? JSON.stringify([row.conflict, row.marks]) : row.key}`;
      const group = groups.get(key);
      if (group) group.rows.push(row);
      else groups.set(key, { file: t.file, rows: [row] });
    }
  }
  return [...groups.values()];
}

/** Files, Drawings, Questions, To review, Signed off; a stat whose source is missing reads "–". `takeoffs`: every
 * review drawing's, or null while any is missing. */
export function workspaceStats(
  project: ProjectView,
  review: ProjectReview | null,
  questions: ProjectQuestions | null = null,
  takeoffs: Takeoff[] | null = null,
): Stat[] {
  const entries = review && takeoffs ? disagreements(takeoffs) : null;
  const sum = (pick: (d: ProjectReview['drawings'][number]) => number) =>
    review ? review.drawings.reduce((n, d) => n + pick(d), 0) : 0;
  return [
    { label: 'Files', value: String(project.files.length) },
    { label: 'Drawings', value: String(project.drawings.length) },
    { label: 'Questions', value: questions ? String(asks(questions).length) : '–' },
    { label: 'To review', value: review ? String(sum((d) => d.to_review)) : '–' },
    {
      label: 'Signed off',
      value: entries
        ? `${String(entries.filter((e) => e.rows.some((r) => r.signed)).length)} of ${String(entries.length)}`
        : '–',
    },
  ];
}

export type EventKind =
  'upload' | 'reading' | 'done' | 'failed' | 'rule' | 'needs' | 'settled' | 'signed' | 'asked';

export interface HistoryEvent {
  kind: EventKind;
  at: string;
  /** `HH:MM`, UTC. */
  time: string;
  glyph: string;
  title: string;
  detail: string;
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
  'asked',
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
  asked: '?',
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
  questions: ProjectQuestions | null = null,
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
        title: `Settled by a rule: ${c.label}`,
        detail: `${c.file} · kept ${formatValue(resolution.value, unit)} · ${resolution.rule}`,
      });
    }
  }
  for (const { file, rows } of disagreements(takeoffs)) {
    const q = rows.find((r) => r.signed);
    if (!q?.signed) continue;
    // The longest label is the printed-name one ("area of room (name Küche · 1.01)").
    const label = rows.reduce((a, r) => (r.label.length > a.length ? r.label : a), q.label);
    events.push({
      kind: 'signed',
      at: q.signed.at,
      title: `Signed off: ${label}`,
      detail: `${file} · ${formatValue(q.signed.value, q.unit)} · by ${q.signed.by}`,
    });
  }
  const fileOf = (id: string) => project.drawings.find((d) => d.drawing_id === id)?.file ?? id;
  for (const lines of questions ? asks(questions) : []) {
    const [q] = lines;
    if (!q) continue;
    if (q.project_ask) {
      const n = lines.filter((l) => !l.refused && l.answer !== null).length;
      events.push({
        kind: 'asked',
        at: lines.reduce((at, l) => (l.at < at ? l.at : at), q.at),
        title: `Asked: ${q.question}`,
        detail: n
          ? // The backend logs no line for a drawing it skipped (unscaled IFC); the ask still went to it.
            `answered on ${String(n)} of ${plural(Math.max(lines.length, project.drawings.length), 'drawing')}`
          : 'not answered',
      });
      continue;
    }
    const said = q.refused
      ? 'not answered'
      : q.answer === null
        ? 'no answer'
        : typeof q.answer === 'number'
          ? formatValue(q.answer, q.unit)
          : q.answer;
    events.push({
      kind: 'asked',
      at: q.at,
      title: `Asked: ${q.question}`,
      detail: `${fileOf(q.drawing_id)} · ${said}`,
    });
  }
  return events
    .map((e, i) => ({ e, i, ms: new Date(e.at).getTime() }))
    .sort((a, b) => a.ms - b.ms || ORDER.indexOf(a.e.kind) - ORDER.indexOf(b.e.kind) || a.i - b.i)
    .map(({ e }) => ({ ...e, time: hhmm(e.at), glyph: GLYPH[e.kind] }));
}
