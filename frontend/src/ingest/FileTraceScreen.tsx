import { useCallback } from 'react';
import { getTrace, type FileTrace } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { STAGE_LABEL, formatCost, formatMs, formatSize, isFinished, plural } from './ingest';
import { BeforeAfter } from './BeforeAfter';
import { StaleNote, StateBadge } from './ProjectScreen';
import { usePoll } from './usePoll';
import './ingest.css';

const live = (t: FileTrace) => !isFinished(t.file);

/** Route `#/p/<project_id>/f/<file_id>`: one file through every stage. */
export function FileTraceScreen({ projectId, fileId }: { projectId: string; fileId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => getTrace(projectId, fileId, { signal }),
    [projectId, fileId],
  );
  const { data: trace, error, failedAt, retry } = usePoll(load, live);
  const back = <a href={`#/p/${projectId}`}>Back to the project</a>;

  if (trace === null) {
    return (
      <div className="ingest">
        {back}
        {error !== null ? (
          <ErrorView error={error} onRetry={retry} />
        ) : (
          <Loading label="Loading trace…" />
        )}
      </div>
    );
  }

  const { file, stages } = trace;
  const takeoff = Object.entries(file.takeoff ?? {});
  const facts: [string, string | null | undefined][] = [
    ['Kind', file.kind ?? 'not identified'],
    ['Size', formatSize(file.size)],
    ['Route', file.route],
    ['Read from', file.source],
    ['Group', file.group],
    ['sha256', file.sha256?.slice(0, 12)],
    ['Time', formatMs(file.ms)],
    ['Cost', formatCost(file.cost_usd)],
  ];
  return (
    <div className="ingest">
      {back}
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      <header className="ingest-head">
        <div>
          <h1 className="path">{file.path}</h1>
          <p>
            <StateBadge state={file.state} /> {file.reason}
          </p>
          {file.reused && <p>reused: read before, not recomputed</p>}
        </div>
        {file.drawing_id && (
          <a className="btn primary" href={`#/p/${projectId}/d/${file.drawing_id}/engineer`}>
            Open the drawing
          </a>
        )}
      </header>
      <dl className="ingest-facts">
        {facts.map(([label, value]) =>
          value ? (
            <div key={label}>
              <dt>{label}</dt>
              <dd title={label === 'sha256' ? (file.sha256 ?? undefined) : undefined}>
                {label === 'Read from' ? `read from ${value}` : value}
              </dd>
            </div>
          ) : null,
        )}
      </dl>
      {file.normalised && file.drawing_id && (
        <BeforeAfter
          projectId={projectId}
          fileId={fileId}
          path={file.path}
          drawingId={file.drawing_id}
          normalised={file.normalised}
        />
      )}
      <section aria-label="Stages">
        <h2>Stages</h2>
        {stages.length === 0 ? (
          <p>No stages yet.</p>
        ) : (
          <ol className="ingest-trace">
            {stages.map((s, i) => (
              <li key={String(i)} className={s.failure ? 'failed' : undefined}>
                <b>{STAGE_LABEL[s.stage]}</b>
                <span className="ms">{formatMs(s.ms)}</span>
                <p>{s.stage === 'cache' ? `Cached: ${s.did}` : s.did}</p>
                {s.stage === 'cache' && (
                  <p className="output">
                    the stages below are from the first ingest of this content
                  </p>
                )}
                {s.output && s.output !== s.did && <p className="output">{s.output}</p>}
                {s.cost_usd > 0 && <p>Cost: {formatCost(s.cost_usd)}</p>}
                {s.failure && (
                  <p className="ingest-error">
                    <span aria-hidden="true">✕</span> Failed: {s.failure}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
      {takeoff.length > 0 && (
        <details className="ingest-takeoff">
          <summary>What it ends as: {plural(takeoff.length, 'quantity', 'quantities')}</summary>
          <dl>
            {takeoff.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
