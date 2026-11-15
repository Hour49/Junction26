import { Fragment, useCallback, useState, type ReactNode } from 'react';
import { errorText, formatTime, getProject, type FileStatus, type ProjectView } from '../api';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { parseRoute, useHash } from '../shell/route';
import {
  PROJECT_STATE_LABEL,
  STATE_LABEL,
  isLive,
  keepPolling,
  nameParts,
  plural,
  sizeText,
  uploadedKey,
} from './ingest';
import { ChatRow, DoneLine, IngestFinished, type ConflictCounts } from './IngestFinished';
import { readDrawings } from './pipeline';
import { ProgressCard } from './ProgressCard';
import { usePoll } from './usePoll';
import { MUTED, PAGE, PANEL, TAP } from './ui';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS, STATE_TIPS } from '../shell/tips-ingest';

/** Shown when a poll fails after data arrived: the data stays, labelled as stale. */
export function StaleNote({
  error,
  failedAt,
  onRetry,
}: {
  error: unknown;
  failedAt: string | null;
  onRetry: () => void;
}) {
  const { detail, code } = errorText(error);
  return (
    <Alert className="flex flex-wrap items-center gap-3 rounded-xl border-0 bg-warn-soft px-3 py-2 text-[length:inherit] text-warn">
      <p>{`Not updating since ${formatTime(failedAt ?? '')}: ${detail} (${code})`}</p>
      <Button variant="secondary" size="pill" className="font-medium" onClick={onRetry}>
        Retry
      </Button>
    </Alert>
  );
}

const TONE = {
  queued: 'secondary',
  running: 'accent',
  ready: 'ok',
  flagged: 'warn',
  text_only: 'secondary',
  set_aside: 'danger',
} as const satisfies Record<FileStatus['state'], string>;

export function StateBadge({ state }: { state: FileStatus['state'] }) {
  const { word, icon } = STATE_LABEL[state];
  return (
    <Tip text={STATE_TIPS[state]} wrap>
      <Badge
        variant={TONE[state]}
        className={cn(
          'gap-1.5 px-[11px] py-[5px] text-xs',
          TONE[state] === 'secondary' && 'text-text-2',
        )}
      >
        <span aria-hidden="true">{icon}</span> {word}
      </Badge>
    </Tip>
  );
}

/** The title row of screen 2 and the trace: state eyebrow over the `h1`, an action on the right. */
/** `ok`: the eyebrow in the ok colour (a finished analysis); `stack`: `children` on their own row under the `h1`. */
export function TitleRow({
  eyebrow,
  title,
  children,
  ok = false,
  stack = false,
}: {
  eyebrow: ReactNode;
  title: string;
  children?: ReactNode;
  ok?: boolean;
  stack?: boolean;
}) {
  return (
    <header
      className={cn(
        'ingest-head flex flex-wrap justify-between gap-4 max-[720px]:flex-col max-[720px]:items-stretch',
        stack ? 'flex-col items-start' : 'items-end',
      )}
    >
      <div>
        <p
          className={cn(
            'ingest-eyebrow flex items-center gap-2 text-sm font-semibold',
            ok ? 'text-ok' : 'text-primary',
          )}
        >
          {/* a word gets the accent dot; a badge (the trace) is its own marker */}
          {typeof eyebrow === 'string' && (
            <span aria-hidden="true" className="ingest-dot size-2 rounded-full bg-current" />
          )}
          {eyebrow}
        </p>
        {/* a long upload or file name shows 3 lines at most; the heading's name and its title stay whole (IN-114).
            It wraps after its own separators first; `anywhere` only for a part too long for a line (IN-121) */}
        <h1 className="v-title mt-1! line-clamp-3 [overflow-wrap:anywhere]" title={title}>
          {nameParts(title).map((part, i) => (
            <Fragment key={`${String(i)}:${part}`}>
              {i > 0 && <wbr />}
              {part}
            </Fragment>
          ))}
        </h1>
      </div>
      {children}
    </header>
  );
}

/** A reason this many entries or more share is one row with a few example paths (IN-128, QA R4-G4). */
const GROUP_AT = 4;
const EXAMPLES = 3;
/** Rows the "Nothing read" card lists; the entries past them are counted, with the link to Documents. */
export const NOTHING_ROWS = 12;

type WhyRow = { reason: string | null; paths: string[] };

/** Each entry its own row, but a reason shared by `GROUP_AT` or more entries one row for all of them. */
export function whyRows(why: readonly { path: string; reason?: string | null }[]): WhyRow[] {
  const byReason = new Map<string, string[]>();
  for (const w of why) {
    const paths = byReason.get(w.reason ?? '');
    if (paths) paths.push(w.path);
    else byReason.set(w.reason ?? '', [w.path]);
  }
  return [...byReason].flatMap(([reason, paths]) =>
    paths.length >= GROUP_AT
      ? [{ reason: reason || null, paths }]
      : paths.map((p) => ({ reason: reason || null, paths: [p] })),
  );
}

/** A done project with no drawings: every file and skipped entry with why it was not read (IN-72), entries with
 * the same reason grouped and the rows capped (IN-128). */
function NothingRead({ projectId, project }: { projectId: string; project: ProjectView }) {
  const paths = new Set(project.files.map((f) => f.path));
  const why = [
    ...project.files.map((f) => ({ path: f.path, reason: f.reason })),
    ...project.skipped.filter((s) => !paths.has(s.path)),
  ];
  const rows = whyRows(why);
  const shown = rows.slice(0, NOTHING_ROWS);
  const more = rows.slice(NOTHING_ROWS).reduce((n, r) => n + r.paths.length, 0);
  return (
    <Card role="region" aria-label="Nothing read" className={cn(PANEL, 'grid gap-4')}>
      <h2 className="v-h2">Nothing could be read from this upload</h2>
      {why.length === 0 && <p>There were no files in it.</p>}
      {why.length > 0 && (
        <ul className="grid gap-3">
          {shown.map((w) =>
            w.paths.length === 1 ? (
              <li key={w.paths[0]} className="grid gap-1 [overflow-wrap:anywhere]">
                <b>{w.paths[0]}</b>
                {w.reason && <span className={MUTED}>{w.reason}</span>}
              </li>
            ) : (
              <li key={`group:${w.reason ?? ''}`} className="grid gap-1 [overflow-wrap:anywhere]">
                <b>{plural(w.paths.length, 'file')}</b>
                {w.reason && <span className={MUTED}>{w.reason}</span>}
                <span className={MUTED}>
                  {`For example: ${w.paths.slice(0, EXAMPLES).join(', ')}`}
                </span>
              </li>
            ),
          )}
        </ul>
      )}
      {more > 0 && <p>{`And ${plural(more, 'more file')}.`}</p>}
      {project.files.some((f) => f.kind === 'dxf' && f.state === 'set_aside') && (
        // with no drawing at all, a DXF was set aside for want of a page to place it on
        <p>
          A DXF is read with the PDF or PNG of the same name: put both in one .zip and upload that.
        </p>
      )}
      <a href={`#/p/${projectId}/documents`}>Every file is listed in Documents.</a>
    </Card>
  );
}

/** What UploadBox kept of this tab's upload (Bogdan 2026-11-15): its name and size; null for the sample or another
 * tab. */
function uploaded(projectId: string): { name: string; bytes: number } | null {
  try {
    const raw = sessionStorage.getItem(uploadedKey(projectId));
    return raw ? (JSON.parse(raw) as { name: string; bytes: number }) : null;
  } catch {
    return null;
  }
}

/** A long name cut in the middle, so its start and its extension both show (IN-114). */
export function shortName(name: string, max = 60): string {
  if (name.length <= max) return name;
  const tail = Math.floor(max / 3);
  return `${name.slice(0, max - tail - 1)}…${name.slice(-tail)}`;
}

/** Route `#/p/<project_id>`: the ingest followed live (Simple), or step by step (`?view=advanced`). */
export function ProjectScreen({ projectId }: { projectId: string }) {
  const load = useCallback((signal: AbortSignal) => getProject(projectId, { signal }), [projectId]);
  const { data: project, at, error, failedAt, retry } = usePoll(load, keepPolling);
  const { query } = parseRoute(useHash());
  const advanced = query.get('view') === 'advanced';
  // the conflicts list's last counts, for the done line inside the card (IN-76)
  const [counts, setCounts] = useState<ConflictCounts | null>(null);
  const [sent] = useState(() => uploaded(projectId));

  if (project === null) {
    return (
      <div className={cn('v-page v-page--narrow', PAGE)}>
        {error !== null ? (
          <ErrorView error={error} onRetry={retry} />
        ) : (
          <Loading label="Loading project…" />
        )}
      </div>
    );
  }

  const base = `#/p/${projectId}`;
  // An upload with nothing readable ends plainly, not "Ready" with a 0% ring (IN-72, R4-a-7); so does one whose
  // drawings were all on a route with no reader (IN-116)
  const nothingRead = project.state === 'done' && readDrawings(project).length === 0;
  return (
    <div className={cn('v-page v-page--narrow', PAGE)}>
      <TitleRow
        eyebrow={PROJECT_STATE_LABEL[project.state] ?? project.state}
        title={project.name}
        ok={project.state === 'done'}
        stack
      >
        <Tip text={INGEST_TIPS.view}>
          <div role="group" aria-label="View" className="v-segmented">
            <a href={base} aria-current={advanced ? undefined : 'page'}>
              Simple
            </a>
            <a href={`${base}?view=advanced`} aria-current={advanced ? 'page' : undefined}>
              Advanced
            </a>
          </div>
        </Tip>
      </TitleRow>
      {sent && (
        <p role="status" aria-label="Upload received" className="text-text-2">
          Uploaded: <span title={sent.name}>{shortName(sent.name)}</span>
          {`, ${sizeText(sent.bytes)}, received by the server. `}
          {project.files.length > 0
            ? `${String(project.files.length)} ${project.files.length === 1 ? 'file' : 'files'} found.`
            : // finished with no files (an empty zip): said plainly, not "Unpacking…" (IN-115)
              isLive(project)
              ? 'Unpacking…'
              : project.state === 'done'
                ? 'No files found in it.'
                : 'Nothing was unpacked.'}
        </p>
      )}
      {project.state === 'failed' && project.error && (
        <p className="font-semibold text-danger">{project.error}</p>
      )}
      {project.state === 'failed' && (
        // stopped for good: the server does not resume it, so say how to go on
        <p className="flex flex-wrap gap-x-4">
          <a className={TAP} href="#/">
            Upload again
          </a>
          {project.drawings.length > 0 && (
            <a className={TAP} href={`${base}/documents`}>
              See what was read in Documents
            </a>
          )}
        </p>
      )}
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      {advanced ? (
        <AdvancedIngest projectId={projectId} project={project} />
      ) : nothingRead ? (
        <NothingRead projectId={projectId} project={project} />
      ) : (
        // the drawings and files are on Documents now (ingest.md v3); here the card (chat row under "Ready",
        // IN-88), then once done the conflicts
        <>
          <ProgressCard
            project={project}
            now={at}
            conflicts={counts}
            actions={<ChatRow projectId={projectId} project={project} counts={counts} />}
            footer={<DoneLine projectId={projectId} project={project} counts={counts} />}
          />
          <IngestFinished
            projectId={projectId}
            project={project}
            query={query}
            onCounts={setCounts}
            withChatRow={false}
          />
        </>
      )}
    </div>
  );
}
