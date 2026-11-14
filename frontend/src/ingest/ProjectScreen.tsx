import { useCallback } from 'react';
import { errorText, formatTime, getProject, type FileStatus, type ProjectView } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import {
  PROJECT_STATE_LABEL,
  STATE_LABEL,
  formatCost,
  formatMs,
  formatSize,
  isFinished,
  plural,
  progressOf,
} from './ingest';
import { StageStrip } from './StageStrip';
import { usePoll } from './usePoll';
import './ingest.css';

const live = (p: ProjectView) => p.state === 'queued' || p.state === 'running';

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
      <button type="button" className="btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

export function StateBadge({ state }: { state: FileStatus['state'] }) {
  const { word, icon } = STATE_LABEL[state];
  return (
    <span className={`badge st-${state}`}>
      <span aria-hidden="true">{icon}</span> {word}
    </span>
  );
}

/** Route `#/p/<project_id>`: the ingest followed live, file by file, with one link per drawing. */
export function ProjectScreen({ projectId }: { projectId: string }) {
  const load = useCallback((signal: AbortSignal) => getProject(projectId, { signal }), [projectId]);
  const { data: project, error, failedAt, retry } = usePoll(load, live);

  if (project === null) {
    return (
      <div className="ingest">
        {error !== null ? (
          <ErrorView error={error} onRetry={retry} />
        ) : (
          <Loading label="Loading project…" />
        )}
      </div>
    );
  }

  const { done, total } = progressOf(project.files);
  // While ingest runs an empty list is not a verdict yet (R1-1-4).
  const waiting = live(project);
  const WAITING = 'Waiting for the files…';
  return (
    <div className="ingest">
      <header className="ingest-head">
        <div>
          <h1>{project.name}</h1>
          <p className="ingest-state">{PROJECT_STATE_LABEL[project.state] ?? project.state}</p>
          {project.state === 'failed' && project.error && (
            <p className="ingest-error">{project.error}</p>
          )}
          <p>
            Started <time dateTime={project.created_at}>{formatTime(project.created_at)}</time> ·
            Cost: {formatCost(project.cost_usd)}
          </p>
        </div>
        {!(waiting && total === 0) && (
          <div className="ingest-progress">
            <progress value={done} max={total} aria-label="Files finished" />
            <span>
              {done} of {plural(total, 'file')} finished
            </span>
          </div>
        )}
      </header>
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      <StageStrip files={project.files} />
      <div className="ingest-cols">
        <section aria-label="Drawings" className="ingest-drawings">
          <h2>Drawings</h2>
          {project.drawings.length === 0 ? (
            <p>
              {waiting ? WAITING : 'No drawings: nothing in this upload could be read as a plan.'}
            </p>
          ) : (
            <ul>
              {project.drawings.map((d) => (
                <li key={d.drawing_id} className="card">
                  <b className="path">{d.file}</b>
                  <span>
                    <StateBadge state={d.state} /> {d.kind ?? 'not identified'}
                    {d.route && ` · ${d.route} route`}
                  </span>
                  {d.other_renderings.length > 0 && (
                    <span>also: {d.other_renderings.map((r) => r.file).join(', ')}</span>
                  )}
                  <a className="btn" href={`#/p/${projectId}/d/${d.drawing_id}/engineer`}>
                    Open
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-label="Files" className="ingest-files">
          <h2>Files</h2>
          {project.files.length === 0 ? (
            <p>{waiting ? WAITING : 'This upload has no files.'}</p>
          ) : (
            <ul>
              {project.files.map((f) => (
                <li key={f.id}>
                  <a href={`#/p/${projectId}/f/${f.id}`}>
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
      </div>
    </div>
  );
}
