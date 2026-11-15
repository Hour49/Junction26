import type { CSSProperties, ReactNode } from 'react';
import type { ProjectView } from '../api';
import {
  STEPS,
  activeStep,
  elapsedMs,
  formatCost,
  formatMs,
  isLive,
  percentDone,
  progressOf,
  stepFiles,
} from './ingest';
import {
  PIPELINE_TIPS,
  busySteps,
  headlineStep,
  projectPhase,
  routeSummary,
  thingsFound,
} from './pipeline';
import { RouteLanes } from './RouteLanes';
import { PANEL } from './ui';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS } from '../shell/tips-ingest';

const ICON = { done: '✓', working: '◌', waiting: '○' } as const;
const DOT = {
  done: 'bg-primary text-card',
  working: 'bg-accent text-primary ring-2 ring-primary',
  waiting: 'border-[1.5px] border-border bg-card text-muted-foreground',
} as const;
/** The stats' hairline grid: 1 px gaps on the fill colour, edge to edge across the card (4 by 2, 2 by 4 at 390). */
const STATS =
  'ingest-stats m-0 -mx-6 grid grid-cols-4 gap-px border-y border-muted bg-muted p-0 max-[720px]:-mx-5 max-[720px]:grid-cols-2 [&>div]:flex [&>div]:flex-col [&>div]:gap-0.5 [&>div]:bg-card [&>div]:px-5 [&>div]:py-3 [&_dt]:text-xs [&_dt]:font-medium [&_dt]:text-muted-foreground [&_dd]:m-0 [&_dd]:text-xl [&_dd]:font-semibold [&_dd]:tracking-[-0.01em] [&_dd]:tabular-nums';

function Stat({ label, tip, children }: { label: string; tip?: string; children: ReactNode }) {
  return (
    <div>
      <dt>
        {tip ? (
          <Tip text={tip} wrap>
            <span>{label}</span>
          </Tip>
        ) : (
          label
        )}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Index's row while it runs: what the last phase is doing (`index_steps`), else its hint. */
function IndexSteps({ project }: { project: ProjectView }) {
  const steps = project.index_steps;
  if (steps.length === 0) return null;
  return (
    <ul
      aria-label="Last phase"
      className="col-start-2 grid gap-0.5 text-[13px] text-muted-foreground"
    >
      {steps.map((s) => (
        <li key={s.id}>
          <span className={cn(s.state === 'failed' ? 'text-danger' : 'text-text-2')}>
            {s.label}
          </span>
          {s.did && `: ${s.did}`}
        </li>
      ))}
    </ul>
  );
}

/** Screen 2's card (ingest.md "Pipeline view v5"): where the ingest is, live totals, the steps beside the files
 * moving through them by route, and once done what was read. */
/** `now`: browser time of the last poll, so Elapsed moves with each answer. */
/** `footer`: the finished screen's done line, the card's last row (ingest.md v3). */
/** `actions`: the chat row, right under "Ready" so it is seen without scrolling (IN-88). */
export function ProgressCard({
  project,
  now,
  footer,
  actions,
}: {
  project: ProjectView;
  now: number;
  footer?: ReactNode;
  actions?: ReactNode;
}) {
  const { files, state } = project;
  const live = isLive(project);
  // v5: the step named is where most files are read now; every step a file is in now is working
  const index = live && projectPhase(project) === 'index';
  const step = live ? headlineStep(project) : activeStep(files);
  const low = index ? STEPS.length : activeStep(files);
  const busy = busySteps(files);
  const percent = percentDone(files);
  const { done, total } = progressOf(files);
  const elapsed = elapsedMs(project, now);
  const expected = project.expected_drawings;
  const ready = String(project.drawings.length);
  const status = (i: number) =>
    state === 'done' || i < low
      ? 'done'
      : i === low || i === step || (!index && busy.has(i))
        ? 'working'
        : 'waiting';
  const conflicts = project.conflicts_open;
  return (
    <Card role="region" aria-label="Progress" className={cn(PANEL, 'grid gap-5')}>
      <div className="flex items-center justify-between gap-4">
        <div className="grid gap-1">
          {state !== 'failed' && (
            <p className="v-caption">
              {state === 'done'
                ? `All ${String(STEPS.length)} steps done`
                : `Step ${String(step)} of ${String(STEPS.length)}`}
            </p>
          )}
          <h2 className="v-h2 m-0!">
            {state === 'done' ? 'Ready' : state === 'failed' ? 'Stopped' : STEPS[step - 1]?.name}
          </h2>
          {state === 'done' && (
            <p className="ingest-summary text-[15px] text-text-2">{routeSummary(files)}</p>
          )}
        </div>
        {state !== 'failed' && (
          <div
            className="relative grid size-20 flex-none place-items-center text-lg font-bold before:absolute before:inset-0 before:rounded-full before:bg-[conic-gradient(var(--v-accent)_calc(var(--p)*1%),var(--v-fill)_0)] before:[mask:radial-gradient(farthest-side,transparent_80%,var(--v-text)_81%)] before:content-[''] motion-safe:before:transition-all"
            role="img"
            aria-label={`${String(percent)} percent done`}
            style={{ '--p': percent } as CSSProperties}
          >
            <span aria-hidden="true">{percent}%</span>
          </div>
        )}
      </div>
      {actions}
      <dl className={STATS}>
        <Stat label="Elapsed">{elapsed === null ? '—' : formatMs(elapsed)}</Stat>
        <Stat label="Files through" tip={INGEST_TIPS.filesThrough}>
          {live && total === 0 ? '—' : `${String(done)} / ${String(total)}`}
        </Stat>
        <Stat label="Drawings ready" tip={INGEST_TIPS.drawingsReady}>
          {expected === null ? ready : `${ready} / ${String(expected)}`}
        </Stat>
        <Stat label="Things found" tip={PIPELINE_TIPS.thingsFound}>
          {live && done === 0 ? '—' : thingsFound(files)}
        </Stat>
        <Stat label="Conflicts" tip={PIPELINE_TIPS.conflicts}>
          {/* the server counts them once the project is done; null until then */}
          {conflicts == null ? '—' : conflicts}
        </Stat>
        <Stat label="Flagged" tip={PIPELINE_TIPS.flagged}>
          {files.filter((f) => f.state === 'flagged').length}
        </Stat>
        {/* the demo's stat (IN-86) */}
        <Stat label="Set aside" tip={INGEST_TIPS.setAside}>
          {files.filter((f) => f.state === 'set_aside').length}
        </Stat>
        <Stat label="Cost" tip={PIPELINE_TIPS.cost}>
          {formatCost(project.cost_usd)}
        </Stat>
      </dl>
      {state !== 'failed' && (
        <div className="grid items-start gap-6 min-[720px]:grid-cols-[200px_1fr]">
          <ol
            className={cn(
              "relative grid gap-0.5 before:absolute before:top-5 before:bottom-5 before:left-[23px] before:w-px before:bg-border before:content-['']",
              // done on a phone: the nine ticks in two columns, so the lanes come up sooner
              state === 'done' &&
                'max-[720px]:grid-cols-2 max-[720px]:before:hidden [&_.ingest-step-name]:whitespace-nowrap',
            )}
            aria-label="Steps"
          >
            {STEPS.map((s, i) => {
              const n = i + 1;
              const st = status(n);
              // Index has no file stage, so no file bar
              const bar = st === 'working' && s.stages.length ? stepFiles(files, n) : null;
              return (
                <li
                  key={s.name}
                  className={cn(
                    'relative grid min-h-9 grid-cols-[24px_1fr] items-center gap-x-3 gap-y-1 rounded-[12px] px-3 py-1',
                    st === 'working' && 'bg-accent/60',
                    st === 'waiting' && 'text-muted-foreground',
                  )}
                >
                  <span
                    className={cn(
                      'z-[1] grid size-6 place-items-center rounded-full text-[12px]',
                      DOT[st],
                    )}
                    role="img"
                    aria-label={st}
                  >
                    {ICON[st]}
                  </span>
                  {/* the hint on hover too, not only while the step runs (ui-tooltips P2) */}
                  <Tip text={s.hint} wrap className="justify-self-start">
                    <span
                      className={cn(
                        'ingest-step-name text-sm',
                        st === 'working' && 'font-semibold',
                      )}
                    >
                      {s.name}
                    </span>
                  </Tip>
                  {st === 'working' && n === step && (
                    // the hint on the step named above only: several can be working at once
                    <span className="col-start-2 text-[13px] text-muted-foreground">{s.hint}</span>
                  )}
                  {st === 'working' && !s.stages.length && <IndexSteps project={project} />}
                  {bar && bar.through > 0 && (
                    // no "0 / 0 files" before any file reached the step (IN-71)
                    <span className="col-start-2 flex items-center gap-2 text-[13px] text-muted-foreground">
                      <progress
                        className="h-1.5 min-w-0 flex-1 accent-primary"
                        value={bar.passed}
                        max={bar.through}
                        aria-hidden="true"
                      />
                      {`${String(bar.passed)} / ${String(bar.through)} files`}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          <RouteLanes projectId={project.id} project={project} />
        </div>
      )}
      {footer}
    </Card>
  );
}
