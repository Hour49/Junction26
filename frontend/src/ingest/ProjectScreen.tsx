import { useCallback, useState, type ReactNode } from 'react';
import { errorText, formatTime, getProject, type FileStatus, type ProjectView } from '../api';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { parseRoute, useHash } from '../shell/route';
import { PROJECT_STATE_LABEL, STATE_LABEL, keepPolling, sizeText, uploadedKey } from './ingest';
import { ChatRow, DoneLine, IngestFinished, type ConflictCounts } from './IngestFinished';
import { ProgressCard } from './ProgressCard';
import { usePoll } from './usePoll';
import './ingest.css';

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
    <div className="ingest-stale" role="alert">
      <p>{`Not updating since ${formatTime(failedAt ?? '')}: ${detail} (${code})`}</p>
      <button type="button" className="v-btn v-btn--secondary v-press" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

const TONE: Record<FileStatus['state'], string> = {
  queued: '',
  running: 'v-pill--accent',
  ready: 'v-pill--ok',
  flagged: 'v-pill--warn',
  text_only: '',
  set_aside: 'v-pill--danger',
};

export function StateBadge({ state }: { state: FileStatus['state'] }) {
  const { word, icon } = STATE_LABEL[state];
  return (
    <span className={`badge v-pill ${TONE[state]}`}>
      <span aria-hidden="true">{icon}</span> {word}
    </span>
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
    <header className={stack ? 'ingest-head ingest-head--stack' : 'ingest-head'}>
      <div>
        <p className={ok ? 'ingest-eyebrow ok' : 'ingest-eyebrow'}>
          {/* a word gets the accent dot; a badge (the trace) is its own marker */}
          {typeof eyebrow === 'string' && <span aria-hidden="true" className="ingest-dot" />}
          {eyebrow}
        </p>
        <h1 className="v-title path">{title}</h1>
      </div>
      {children}
    </header>
  );
}

/** A done project with no drawings: every file and skipped entry with why it was not read (IN-72). */
function NothingRead({ projectId, project }: { projectId: string; project: ProjectView }) {
  const paths = new Set(project.files.map((f) => f.path));
  const why = [
    ...project.files.map((f) => ({ path: f.path, reason: f.reason })),
    ...project.skipped.filter((s) => !paths.has(s.path)),
  ];
  return (
    <section aria-label="Nothing read" className="v-card ingest-nothing">
      <h2 className="v-h2">Nothing could be read from this upload</h2>
      {why.length > 0 && (
        <ul>
          {why.map((w) => (
            <li key={w.path}>
              <b className="path">{w.path}</b>
              {w.reason && <span className="reason">{w.reason}</span>}
            </li>
          ))}
        </ul>
      )}
      <a href={`#/p/${projectId}/documents`}>Every file is listed in Documents.</a>
    </section>
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
      <div className="v-page v-page--narrow ingest">
        {error !== null ? (
          <ErrorView error={error} onRetry={retry} />
        ) : (
          <Loading label="Loading project…" />
        )}
      </div>
    );
  }

  const base = `#/p/${projectId}`;
  // An upload with nothing readable ends plainly, not "Ready" with a 0% ring (IN-72, R4-a-7).
  const nothingRead = project.state === 'done' && project.drawings.length === 0;
  return (
    <div className="v-page v-page--narrow ingest">
      <TitleRow
        eyebrow={PROJECT_STATE_LABEL[project.state] ?? project.state}
        title={project.name}
        ok={project.state === 'done'}
        stack
      >
        <div role="group" aria-label="View" className="v-segmented">
          <a href={base} aria-current={advanced ? undefined : 'page'}>
            Simple
          </a>
          <a href={`${base}?view=advanced`} aria-current={advanced ? 'page' : undefined}>
            Advanced
          </a>
        </div>
      </TitleRow>
      {sent && (
        <p role="status" aria-label="Upload received" className="ingest-received">
          {`Uploaded: ${sent.name}, ${sizeText(sent.bytes)}, received by the server. `}
          {project.files.length > 0
            ? `${String(project.files.length)} ${project.files.length === 1 ? 'file' : 'files'} found.`
            : 'Unpacking…'}
        </p>
      )}
      {project.state === 'failed' && project.error && (
        <p className="ingest-error">{project.error}</p>
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
