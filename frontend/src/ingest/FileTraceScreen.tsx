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
import { MUTED, PAGE, PANEL, SUMMARY, TAP } from './ui';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS, STAGE_TIPS } from '../shell/tips-ingest';

/** The file page as the demo's (files.js traceScreen): mono 28 px path (22 px on a phone), hairline facts (IN-83). */
const FILE_PAGE = cn(
  'v-page v-page--narrow',
  PAGE,
  '[&_h1]:font-mono! [&_h1]:text-[28px]! [&_h1]:leading-[1.2]! max-[720px]:[&_h1]:text-[22px]!',
);
/** The hairline grid: 1 px gaps on the fill colour. */
const FACTS = cn(
  PANEL,
  'ingest-facts m-0 grid grid-cols-2 gap-px overflow-hidden bg-muted p-0 max-[720px]:grid-cols-1 max-[720px]:p-0 [&>div]:flex [&>div]:flex-col [&>div]:gap-0.5 [&>div]:bg-card [&>div]:px-5 [&>div]:py-3.5 [&_dt]:text-xs [&_dt]:font-medium [&_dt]:text-muted-foreground [&_dd]:m-0 [&_dd]:text-[15px] [&_dd]:font-semibold [&_dd]:[overflow-wrap:anywhere]',
);

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
    <a
      className={cn(TAP, 'self-start text-[13px] text-muted-foreground')}
      href={`#/p/${projectId}/documents`}
    >
      Back to Documents
    </a>
  );

  if (trace === null) {
    return (
      <div className={FILE_PAGE}>
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
    <div className={FILE_PAGE}>
      {back}
      {error !== null && <StaleNote error={error} failedAt={failedAt} onRetry={retry} />}
      <TitleRow eyebrow={<StateBadge state={file.state} />} title={file.path}>
        {file.drawing_id && (
          <Tip text={INGEST_TIPS.openDrawing}>
            <Button asChild size="pill" className="no-underline hover:text-primary-foreground">
              <a href={`#/p/${projectId}/d/${file.drawing_id}/engineer`}>Open the drawing</a>
            </Button>
          </Tip>
        )}
      </TitleRow>
      {file.reason && <p>{file.reason}</p>}
      {file.reused && (
        <p>
          <Tip text={INGEST_TIPS.reused} wrap>
            <span>reused: read before, not recomputed</span>
          </Tip>
        </p>
      )}
      <dl className={FACTS}>
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
      <Card role="region" aria-label="Stages" className={cn(PANEL, 'block')}>
        {stages.length === 0 ? (
          <p>No stages yet.</p>
        ) : (
          // folded: the demo's file page shows no stages, and nothing is lost (IN-83)
          <details>
            <Tip text={INGEST_TIPS.stages}>
              <summary className={cn(SUMMARY, 'font-semibold')}>
                How it was read: {plural(stages.length, 'stage')}
              </summary>
            </Tip>
            <ol className="ingest-trace">
              {stages.map((s, i) => (
                <li
                  key={String(i)}
                  className={cn(
                    'grid grid-cols-[28px_1fr_auto] items-center gap-x-3 gap-y-0.5 py-3 [&+li]:border-t [&+li]:border-border [&>p]:col-[2/-1]',
                    s.failure && 'failed',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-6 place-items-center rounded-full text-[13px] text-card',
                      s.failure ? 'bg-danger' : 'bg-primary',
                    )}
                    role="img"
                    aria-label={s.failure ? 'failed' : 'done'}
                  >
                    {s.failure ? '✕' : '✓'}
                  </span>
                  <Tip text={STAGE_TIPS[s.stage]} wrap className="justify-self-start">
                    <b>{STAGE_LABEL[s.stage]}</b>
                  </Tip>
                  <span className={MUTED}>{formatMs(s.ms)}</span>
                  <p>{s.stage === 'cache' ? `Cached: ${s.did}` : s.did}</p>
                  {s.stage === 'cache' && (
                    <p className={cn('output', MUTED)}>
                      the stages below are from the first ingest of this content
                    </p>
                  )}
                  {s.output && s.output !== s.did && (
                    <p className={cn('output', MUTED)}>{s.output}</p>
                  )}
                  {s.cost_usd > 0 && <p>Cost: {formatCost(s.cost_usd)}</p>}
                  {s.failure && <p className="font-semibold text-danger">Failed: {s.failure}</p>}
                </li>
              ))}
            </ol>
          </details>
        )}
      </Card>
      {takeoff.length > 0 && (
        <details className={cn(PANEL, 'ingest-takeoff block')}>
          <Tip text={INGEST_TIPS.endsAs}>
            <summary className={SUMMARY}>
              What it ends as: {plural(takeoff.length, 'quantity', 'quantities')}
            </summary>
          </Tip>
          <dl className="mt-2 mb-0 grid grid-cols-[minmax(0,1fr)_auto] [&>div]:contents">
            {takeoff.map(([key, value]) => (
              <div key={key}>
                <dt className="[overflow-wrap:anywhere]">{key}</dt>
                <dd className="m-0 text-right">{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
