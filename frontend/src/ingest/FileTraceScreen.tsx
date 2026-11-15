import { Fragment, useCallback, useEffect, useState } from 'react';
import { getTakeoff, getTrace, type FileTrace } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { parseRoute, useHash } from '../shell/route';
import {
  formatCost,
  kindLabel,
  routeLabel,
  formatMs,
  formatSize,
  isFinished,
  nameParts,
  plural,
} from './ingest';
import { BeforeAfter } from './BeforeAfter';
import { StaleNote, StateBadge, TitleRow } from './ProjectScreen';
import { TriageCard } from './TriageCard';
import { usePoll } from './usePoll';
import { ModelCard } from '../model3d/ModelView';
import { PAGE, PANEL, SUMMARY, TAP } from './ui';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS } from '../shell/tips-ingest';
import { Decisions, TraceTimeline } from '../advanced/TraceTimeline';
import { disagreements, keyCounts, readWith, type Disagreement } from '../advanced/trace';
import { calledNotADrawing } from '../advanced/advanced';

/** The file page as the demo's (files.js traceScreen): mono 28 px path (22 px on a phone), hairline facts (IN-83). */
const FILE_PAGE = cn(
  'v-page v-page--narrow',
  PAGE,
  '[&_h1]:font-mono! [&_h1]:text-[28px]! [&_h1]:leading-[1.2]! max-[720px]:[&_h1]:text-[22px]!',
);
/** The hairline grid: 1 px gaps on the fill colour; an odd last fact spans the row, so no empty cell shows. It spans
 * the explicit columns only (`col-span-full`): a `col-span-2` in the phone's one column made an implicit `auto` column
 * that a long path widened, squeezing the real one to a letter per line (QA ifc-r1 row 20). */
const FACTS = cn(
  PANEL,
  'ingest-facts m-0 grid grid-cols-2 gap-px overflow-hidden bg-muted p-0 [&>div:last-child:nth-child(odd)]:col-span-full max-[720px]:grid-cols-1 max-[720px]:p-0 [&>div]:flex [&>div]:min-w-0 [&>div]:flex-col [&>div]:gap-0.5 [&>div]:bg-card [&>div]:px-5 [&>div]:py-3.5 [&_dt]:text-xs [&_dt]:font-medium [&_dt]:text-muted-foreground [&_dd]:m-0 [&_dd]:text-[15px] [&_dd]:font-semibold [&_dd]:[overflow-wrap:anywhere]',
);

const live = (t: FileTrace) => !isFinished(t.file);

/** The facts that hold a path: a line may break after each of its separators (`nameParts`, IN-121). */
const PATH_FACTS = new Set(['Read from', 'Group']);

function withBreaks(text: string) {
  return nameParts(text).map((p, i) => (
    <Fragment key={String(i)}>
      {i > 0 && <wbr />}
      {p}
    </Fragment>
  ));
}

/** The values of the file's conflicts (AD-107): its drawing's takeoff, once, only when the second count disagreed. */
function useConflicts(projectId: string, trace: FileTrace | null): Disagreement[] | null {
  const drawingId = trace?.file.drawing_id ?? null;
  const conflicts = trace?.second_count?.conflicts ?? 0;
  const [rows, setRows] = useState<Disagreement[] | null>(null);
  useEffect(() => {
    if (!drawingId || conflicts === 0) return;
    const controller = new AbortController();
    getTakeoff(drawingId, { project: projectId, signal: controller.signal }).then(
      (t) => {
        setRows(disagreements(t));
      },
      () => undefined, // the counts stay; the values are an extra
    );
    return () => {
      controller.abort();
    };
  }, [projectId, drawingId, conflicts]);
  return rows;
}

/** Route `#/p/<project_id>/f/<file_id>`: one file through every stage. */
export function FileTraceScreen({ projectId, fileId }: { projectId: string; fileId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => getTrace(projectId, fileId, { signal }),
    [projectId, fileId],
  );
  const { data: trace, error, failedAt, retry, set } = usePoll(load, live);
  const conflicts = useConflicts(projectId, trace);
  const from = parseRoute(useHash()).query.get('from');
  // Back where the person came from: the linking screen adds `?from=` (IN-79); an old link goes to Documents.
  const [backHref, backLabel] =
    from === 'ingest'
      ? [`#/p/${projectId}`, 'Back to Ingest']
      : from === 'advanced'
        ? [`#/p/${projectId}?view=advanced`, 'Back to Ingest']
        : [`#/p/${projectId}/documents`, 'Back to Documents'];
  const back = (
    <a className={cn(TAP, 'self-start text-[13px] text-muted-foreground')} href={backHref}>
      {backLabel}
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
  const counts = keyCounts(file.takeoff);
  const facts: [string, string | null | undefined][] = [
    ['Kind', kindLabel(file.kind)],
    ['Size', formatSize(file.size)],
    [
      'Route',
      file.route
        ? readWith(file)
          ? `read with ${readWith(file) ?? ''} (${routeLabel(file.route)})`
          : routeLabel(file.route)
        : null,
    ],
    ['Read from', file.source],
    ['Group', file.group],
    ['sha256', file.sha256?.slice(0, 12)],
    ['Time', formatMs(file.ms)],
    // no paid call, no line (AD-122): "$0.00" is not a fact worth a row
    ['Cost', file.cost_usd > 0 ? formatCost(file.cost_usd) : null],
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
      {file.drawing_id && calledNotADrawing(file) && (
        // QA R4-A9: read only because the sheet-kind step warns; no drawing ready (API.md `not_a_drawing`)
        <p className="text-muted-foreground">
          The sheet-kind step called this not a drawing: it was read, but it is not counted as a
          drawing ready.
        </p>
      )}
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
              <dd title={label === 'sha256' ? (file.sha256 ?? undefined) : undefined}>
                {PATH_FACTS.has(label) ? withBreaks(value) : value}
              </dd>
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
      <Decisions trace={trace} conflicts={conflicts} />
      <TraceTimeline stages={stages} />
      {file.normalised && file.drawing_id && (
        <BeforeAfter
          projectId={projectId}
          fileId={fileId}
          path={file.path}
          drawingId={file.drawing_id}
          normalised={file.normalised}
        />
      )}
      {takeoff.length > 0 && (
        <section aria-label="What it ends as" className={cn(PANEL, 'tl-ends block')}>
          <details className="ingest-takeoff">
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
          {counts.length > 0 && (
            <ul className="tl-counts" aria-label="Key counts">
              {counts.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          {file.drawing_id && (
            <a className="tl-link" href={`#/p/${projectId}/d/${file.drawing_id}/engineer`}>
              See these on the drawing
            </a>
          )}
        </section>
      )}
    </div>
  );
}
