import { useCallback, type ReactNode } from 'react';
import { errorText, formatTime, getProject, type FileStatus } from '../api';
import { AdvancedIngest } from '../advanced/AdvancedIngest';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { parseRoute, useHash } from '../shell/route';
import {
  PROJECT_STATE_LABEL,
  STATE_LABEL,
  formatMs,
  formatSize,
  isFinished,
  isLive as live,
} from './ingest';
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
export function TitleRow({
  eyebrow,
  title,
  children,
}: {
  eyebrow: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="ingest-head">
      <div>
        <p className="ingest-eyebrow">
          <span aria-hidden="true" className="ingest-dot" />
          {eyebrow}
        </p>
        <h1 className="v-title path">{title}</h1>
      </div>
      {children}
    </header>
  );
}

/** Route `#/p/<project_id>`: the ingest followed live (Simple), or step by step (`?view=advanced`). */
export function ProjectScreen({ projectId }: { projectId: string }) {
  const load = useCallback((signal: AbortSignal) => getProject(projectId, { signal }), [projectId]);
  const { data: project, at, error, failedAt, retry } = usePoll(load, live);
  const advanced = parseRoute(useHash()).query.get('view') === 'advanced';

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

  // While ingest runs an empty list is not a verdict yet (R1-1-4).
  const waiting = live(project);
  const WAITING = 'Waiting for the files…';
  const base = `#/p/${projectId}`;
  return (
    <div className="v-page v-page--narrow ingest">
      <TitleRow eyebrow={PROJECT_STATE_LABEL[project.state] ?? project.state} title={project.name}>
        <div role="group" aria-label="View" className="v-segmented">
          <a href={base} aria-current={advanced ? undefined : 'page'}>
            Simple
          </a>
          <a href={`${base}?view=advanced`} aria-current={advanced ? 'page' : undefined}>
            Advanced
          </a>
        </div>
      </TitleRow>
      {project.state === 'failed' && project.error && (
        <p className="ingest-error">{project.error}</p>
      )}
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      {advanced ? (
        <AdvancedIngest projectId={projectId} project={project} />
      ) : (
        <>
          <ProgressCard project={project} now={at} />
          {project.state === 'done' && (
            <p className="ingest-next">
              <a className="v-btn v-press" href={`${base}/conflicts`}>
                Settle the conflicts
              </a>
            </p>
          )}
          <section aria-label="Drawings" className="ingest-drawings">
            <h2 className="v-h3">Drawings</h2>
            {project.drawings.length === 0 ? (
              <p>
                {waiting ? WAITING : 'No drawings: nothing in this upload could be read as a plan.'}
              </p>
            ) : (
              <ul>
                {project.drawings.map((d) => (
                  <li key={d.drawing_id} className="v-card">
                    <b className="path">{d.file}</b>
                    <span>
                      <StateBadge state={d.state} /> {d.kind ?? 'not identified'}
                      {d.route && ` · ${d.route} route`}
                    </span>
                    {d.other_renderings.length > 0 && (
                      <span>also: {d.other_renderings.map((r) => r.file).join(', ')}</span>
                    )}
                    <a
                      className="v-btn v-btn--secondary v-press"
                      href={`${base}/d/${d.drawing_id}/engineer`}
                    >
                      Open
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Files" className="ingest-files">
            <h2 className="v-h3">Files</h2>
            {project.files.length === 0 ? (
              <p>{waiting ? WAITING : 'This upload has no files.'}</p>
            ) : (
              <ul className="v-card">
                {project.files.map((f) => (
                  <li key={f.id}>
                    <a href={`${base}/f/${f.id}`}>
                      <b className="path">{f.path}</b>
                      <span>
                        <StateBadge state={f.state} /> {f.kind ?? 'not identified'} ·{' '}
                        {formatSize(f.size)}
                        {isFinished(f) && ` · ${formatMs(f.ms)}`}
                        {f.reused && ' · reused'}
                      </span>
                      {f.reason && <span className="reason">{f.reason}</span>}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
