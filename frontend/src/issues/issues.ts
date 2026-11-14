// Pure helpers of the issues screen (issues.md "API calls", "The marks for the plan").
import type { Issue, IssueSeverity, IssueState, MarkView } from '../api';
import type { Tone } from '../viewer/PageViewer';
import { issueRoute } from '../surveyor/issueLinks';

export interface Row {
  issue: Issue;
  /** 1-based position in the unfiltered API list: the export's `n`. */
  n: number;
}

const KIND_LABEL: Record<string, { word: string; icon: string }> = {
  conflict: { word: 'Conflict', icon: '⇄' },
  refused_answer: { word: 'Refused answer', icon: '?' },
  set_aside: { word: 'Set aside', icon: '–' },
  reading_flag: { word: 'Reading flag', icon: '!' },
  code_check_failed: { word: 'Fails a code rule', icon: '✕' },
  double_check: { word: 'Double-check', icon: '◎' },
};

/** A kind the table lacks shows its raw id and no icon (new kinds stay additive). */
export const kindOf = (kind: string) => KIND_LABEL[kind] ?? { word: kind, icon: '' };

export const SEVERITIES: readonly IssueSeverity[] = ['fails_rule', 'needs_person', 'note'];
export const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  fails_rule: 'Fails a rule',
  needs_person: 'Needs a person',
  note: 'Note',
};

export const STATES: readonly IssueState[] = ['open', 'settled', 'signed_off'];
export const STATE_LABEL: Record<IssueState, { word: string; icon: string }> = {
  open: { word: 'open', icon: '●' },
  settled: { word: 'settled', icon: '✓' },
  signed_off: { word: 'signed off', icon: '✓✓' },
};

export const numbered = (issues: readonly Issue[]): Row[] =>
  issues.map((issue, i) => ({ issue, n: i + 1 }));

export function filterIssues(rows: readonly Row[], f: { kind: string; state: string }): Row[] {
  return rows.filter(
    ({ issue }) => (!f.kind || issue.kind === f.kind) && (!f.state || issue.state === f.state),
  );
}

/** "3 open · 1 settled · 1 signed off"; states with none are left out. */
export function counts(issues: readonly Issue[]): string {
  return STATES.map(
    (s) => [issues.filter((i) => i.state === s).length, STATE_LABEL[s].word] as const,
  )
    .filter(([n]) => n > 0)
    .map(([n, word]) => `${String(n)} ${word}`)
    .join(' · ');
}

export function placeOf(issue: Issue): string {
  const floor = issue.floor ? `floor ${issue.floor}` : 'floor not stated';
  const page =
    issue.page !== null
      ? `page ${String(issue.page)}`
      : issue.drawing_id
        ? 'the whole drawing'
        : 'not on a drawing';
  return `${issue.file} · ${floor} · ${page}`;
}

/** The located issues of one drawing as numbered marks for PageViewer: the issue's data only. */
export function issueMarks(rows: readonly Row[], drawingId: string): MarkView[] {
  return rows.flatMap(({ issue, n }) =>
    issue.drawing_id === drawingId && issue.page !== null && issue.box
      ? [
          {
            id: issue.id,
            n,
            page: issue.page,
            box: issue.box,
            polygon: issue.polygon ?? null,
            label: kindOf(issue.kind).word,
            state: 'counted' as const,
            value: null,
            reason: null, // PageViewer reads a mark's reason as a rule exclusion; the why is on the row
            ref: null,
            room_type: null,
          },
        ]
      : [],
  );
}

/** Each located mark's look and words by severity (viewer.md tones): "Mark 1: …, fails the rule", never "counted". */
export function issueTones(rows: readonly Row[], drawingId: string): Record<string, Tone> {
  const tone: Record<IssueSeverity, Tone> = {
    fails_rule: 'fail',
    needs_person: 'needs_person',
    note: 'note',
  };
  const sev = new Map(rows.map((r) => [r.issue.id, r.issue.severity]));
  return Object.fromEntries(
    issueMarks(rows, drawingId).map((m) => [m.id, tone[sev.get(m.id) ?? 'note']]),
  );
}

const href = (path: string, query: Record<string, string>, pack: string | null) => {
  const q = new URLSearchParams(pack ? { ...query, pack } : query).toString();
  return `#${path}${q ? `?${q}` : ''}`;
};

/** The row's links, settling screen first; every href keeps `pack`. */
export function routeOf(
  issue: Issue,
  projectId: string,
  pack: string | null,
): { label: string; href: string }[] {
  const p = `/p/${projectId}`;
  const did = issue.drawing_id;
  const links: { label: string; href: string }[] = [];
  const settle = issueRoute(issue, projectId, pack);
  if (settle)
    links.push({ label: issue.kind === 'conflict' ? 'Settle' : 'Ask again', href: settle });
  if (issue.kind === 'set_aside' && issue.file_id)
    links.push({ label: 'Why it was set aside', href: href(`${p}/f/${issue.file_id}`, {}, pack) });
  if (did && (issue.kind === 'reading_flag' || issue.kind === 'code_check_failed')) {
    const q: Record<string, string> = issue.quantity ? { q: issue.quantity } : {};
    links.push({ label: 'Open in the surveyor', href: href(`${p}/d/${did}/surveyor`, q, pack) });
  }
  if (issue.kind === 'code_check_failed' && pack)
    links.push({ label: 'See the check', href: href(`${p}/checks`, {}, pack) });
  if (did && issue.page !== null) {
    const place: Record<string, string> = { page: String(issue.page) };
    if (issue.box) place.box = issue.box.join(',');
    links.push({ label: 'Open the drawing', href: href(`${p}/d/${did}/engineer`, place, pack) });
  }
  return links;
}
