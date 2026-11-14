import type { CSSProperties, ReactNode } from 'react';
import type { ProjectView } from '../api';
import {
  STEPS,
  activeStep,
  elapsedMs,
  formatMs,
  isLive,
  percentDone,
  progressOf,
  stepFiles,
} from './ingest';
import { MUTED, PANEL } from './ui';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';
import { INGEST_TIPS } from '../shell/tips-ingest';

const ICON = { done: '✓', working: '◌', waiting: '○' } as const;
/** Each step row and its icon by state (the demo's .step look). */
const ROW = { done: '', working: 'bg-accent', waiting: 'text-muted-foreground' } as const;
const DOT = {
  done: 'bg-primary text-card',
  working: 'bg-accent text-primary',
  waiting: 'border-[1.5px] border-border',
} as const;
/** The stats' hairline grid (the demo's .stats): 1 px gaps on the fill colour, edge to edge across the card. */
const STATS =
  'ingest-stats m-0 -mx-6 grid grid-cols-4 gap-px border-y border-muted bg-muted p-0 max-[720px]:-mx-5 max-[720px]:grid-cols-2 [&>div]:flex [&>div]:flex-col [&>div]:gap-0.5 [&>div]:bg-card [&>div]:px-5 [&>div]:py-3.5 [&_dt]:text-xs [&_dt]:font-medium [&_dt]:text-muted-foreground [&_dd]:m-0 [&_dd]:text-xl [&_dd]:font-semibold [&_dd]:tracking-[-0.01em] [&_dd]:tabular-nums';

/** Screen 2's card: the step, a ring with the share of files finished, the stats and the steps. */
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
  const step = activeStep(files);
  const percent = percentDone(files);
  const { done, total } = progressOf(files);
  const elapsed = elapsedMs(project, now);
  const expected = project.expected_drawings;
  const ready = String(project.drawings.length);
  const status = (i: number) =>
    state === 'done' || i < step ? 'done' : i === step ? 'working' : 'waiting';
  return (
    <Card role="region" aria-label="Progress" className={PANEL}>
      <div className="flex items-center justify-between gap-4">
        <div>
          {state !== 'failed' && (
            <p className="v-caption">
              {state === 'done'
                ? `All ${String(STEPS.length)} steps done`
                : `Step ${String(step)} of ${String(STEPS.length)}`}
            </p>
          )}
          <h2 className="v-h2 mt-1!">
            {state === 'done' ? 'Ready' : state === 'failed' ? 'Stopped' : STEPS[step - 1]?.name}
          </h2>
        </div>
        <div
          className="relative grid size-24 flex-none place-items-center text-xl font-bold before:absolute before:inset-0 before:rounded-full before:bg-[conic-gradient(var(--v-accent)_calc(var(--p)*1%),var(--v-fill)_0)] before:[mask:radial-gradient(farthest-side,transparent_80%,var(--v-text)_81%)] before:content-['']"
          role="img"
          aria-label={`${String(percent)} percent done`}
          style={{ '--p': percent } as CSSProperties}
        >
          <span aria-hidden="true">{percent}%</span>
        </div>
      </div>
      {actions}
      <dl className={STATS}>
        <div>
          <dt>Elapsed</dt>
          <dd>{elapsed === null ? '—' : formatMs(elapsed)}</dd>
        </div>
        <div>
          <dt>
            <Tip text={INGEST_TIPS.filesThrough} wrap>
              <span>Files through</span>
            </Tip>
          </dt>
          <dd>{live && total === 0 ? '—' : `${String(done)} / ${String(total)}`}</dd>
        </div>
        <div>
          <dt>
            <Tip text={INGEST_TIPS.drawingsReady} wrap>
              <span>Drawings ready</span>
            </Tip>
          </dt>
          <dd>{expected === null ? ready : `${ready} / ${String(expected)}`}</dd>
        </div>
        <div>
          {/* the demo's 4th stat (IN-86) */}
          <dt>
            <Tip text={INGEST_TIPS.setAside} wrap>
              <span>Set aside</span>
            </Tip>
          </dt>
          <dd>{files.filter((f) => f.state === 'set_aside').length}</dd>
        </div>
      </dl>
      {state !== 'failed' && (
        <ol className="grid gap-0.5" aria-label="Steps">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const st = status(n);
            // Index has no file stage, so no file bar
            const bar = st === 'working' && s.stages.length ? stepFiles(files, n) : null;
            return (
              <li
                key={s.name}
                className={cn(
                  'grid min-h-10 grid-cols-[28px_1fr] items-center gap-x-3 gap-y-1 rounded-[14px] px-3.5 py-1.5',
                  ROW[st],
                )}
              >
                <span
                  className={cn('grid size-6 place-items-center rounded-full text-[13px]', DOT[st])}
                  role="img"
                  aria-label={st}
                >
                  {ICON[st]}
                </span>
                {/* the hint on hover too, not only while the step runs (ui-tooltips P2) */}
                <Tip text={s.hint} wrap className="justify-self-start">
                  <span className={cn('ingest-step-name', st === 'working' && 'font-semibold')}>
                    {s.name}
                  </span>
                </Tip>
                {st === 'working' && <span className={cn('col-start-2', MUTED)}>{s.hint}</span>}
                {bar && bar.through > 0 && (
                  // no "0 / 0 files" before any file reached the step (IN-71)
                  <span className={cn('col-start-2 flex items-center gap-3', MUTED)}>
                    <progress
                      className="h-1.5 flex-1 accent-primary"
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
      )}
      {footer}
    </Card>
  );
}
