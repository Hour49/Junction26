import { useCallback } from 'react';
import { getTrace, type FileTrace } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import {
  STAGE_LABEL,
  formatCost,
  kindLabel,
  routeLabel,
  formatMs,
  formatSize,
  isFinished,
  plural,
} from './ingest';
import { BeforeAfter } from './BeforeAfter';
import { StaleNote, StateBadge, TitleRow } from './ProjectScreen';
import { TriageCard } from './TriageCard';
import { usePoll } from './usePoll';
import { ModelCard } from '../model3d/ModelView';
import './ingest.css';

const live = (t: FileTrace) => !isFinished(t.file);

/** Route `#/p/<project_id>/f/<file_id>`: one file through every stage. */
export function FileTraceScreen({ projectId, fileId }: { projectId: string; fileId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => getTrace(projectId, fileId, { signal }),
    [projectId, fileId],
  );
  const { data: trace, error, failedAt, retry, set } = usePoll(load, live);
  const back = (
    // the file rows are on Documents now (ingest.md v3, IN-79)
    <a className="ingest-back" href={`#/p/${projectId}/documents`}>
      Back to Documents
    </a>
  );

  if (trace === null) {
    return (
      <div className="v-page v-page--narrow ingest">
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
    ['Kind', kindLabel(file.kind)],
    ['Size', formatSize(file.size)],
    ['Route', file.route ? routeLabel(file.route) : null],
    ['Read from', file.source],
    ['Group', file.group],
    ['sha256', file.sha256?.slice(0, 12)],
    ['Time', formatMs(file.ms)],
    ['Cost', formatCost(file.cost_usd)],
  ];
  return (
    <div className="v-page v-page--narrow ingest ingest-file">
      {back}
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      <TitleRow eyebrow={<StateBadge state={file.state} />} title={file.path}>
        {file.drawing_id && (
          <a className="v-btn v-press" href={`#/p/${projectId}/d/${file.drawing_id}/engineer`}>
            Open the drawing
          </a>
        )}
      </TitleRow>
      {file.reason && <p className="reason">{file.reason}</p>}
      {file.reused && <p>reused: read before, not recomputed</p>}
      <dl className="v-card ingest-facts">
        {facts.map(([label, value]) =>
          value ? (
            <div key={label}>
              <dt>{label}</dt>
              <dd title={label === 'sha256' ? (file.sha256 ?? undefined) : undefined}>{value}</dd>
            </div>
          ) : null,
        )}
      </dl>
      <ModelCard projectId={projectId} file={file} />
      <TriageCard
        projectId={projectId}
        file={file}
        onFile={(next) => {
          set({ ...trace, file: next });
          if (!isFinished(next)) retry(); // read again as a plan: follow it until it is finished
        }}
      />
      {file.normalised && file.drawing_id && (
        <BeforeAfter
          projectId={projectId}
          fileId={fileId}
          path={file.path}
          drawingId={file.drawing_id}
          normalised={file.normalised}
        />
      )}
      <section aria-label="Stages" className="v-card">
        {stages.length === 0 ? (
          <p>No stages yet.</p>
        ) : (
          // folded: the demo's file page shows no stages, and nothing is lost (IN-83)
          <details className="ingest-stages">
            <summary>How it was read: {plural(stages.length, 'stage')}</summary>
            <ol className="ingest-trace">
              {stages.map((s, i) => (
                <li key={String(i)} className={s.failure ? 'failed' : undefined}>
                  <span
                    className="ingest-step-icon"
                    role="img"
                    aria-label={s.failure ? 'failed' : 'done'}
                  >
                    {s.failure ? '✕' : '✓'}
                  </span>
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
                  {s.failure && <p className="ingest-error">Failed: {s.failure}</p>}
                </li>
              ))}
            </ol>
          </details>
        )}
      </section>
      {takeoff.length > 0 && (
        <details className="v-card ingest-takeoff">
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
