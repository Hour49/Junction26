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

const ICON = { done: '✓', working: '◌', waiting: '○' } as const;

/** Screen 2's card: the step, a ring with the share of files finished, the stats and the 8 steps. */
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
    <section aria-label="Progress" className="v-card ingest-progress">
      <div className="ingest-progress-top">
        <div>
          {state !== 'failed' && (
            <p className="v-caption">
              {state === 'done' ? 'All 8 steps done' : `Step ${String(step)} of 8`}
            </p>
          )}
          <h2 className="v-h2">
            {state === 'done' ? 'Ready' : state === 'failed' ? 'Stopped' : STEPS[step - 1]?.name}
          </h2>
        </div>
        <div
          className="ingest-ring"
          role="img"
          aria-label={`${String(percent)} percent done`}
          style={{ '--p': percent } as CSSProperties}
        >
          <span aria-hidden="true">{percent}%</span>
        </div>
      </div>
      {actions}
      <dl className="ingest-stats">
        <div>
          <dt>Elapsed</dt>
          <dd>{elapsed === null ? '—' : formatMs(elapsed)}</dd>
        </div>
        <div>
          <dt>Files through</dt>
          <dd>{live && total === 0 ? '—' : `${String(done)} / ${String(total)}`}</dd>
        </div>
        <div>
          <dt>Drawings ready</dt>
          <dd>{expected === null ? ready : `${ready} / ${String(expected)}`}</dd>
        </div>
        <div>
          {/* the demo's 4th stat (IN-86) */}
          <dt>Set aside</dt>
          <dd>{files.filter((f) => f.state === 'set_aside').length}</dd>
        </div>
      </dl>
      {state !== 'failed' && (
        <ol className="ingest-steps" aria-label="Steps">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const st = status(n);
            const bar = st === 'working' ? stepFiles(files, n) : null;
            return (
              <li key={s.name} className={`ingest-step is-${st}`}>
                <span className="ingest-step-icon" role="img" aria-label={st}>
                  {ICON[st]}
                </span>
                <span className="ingest-step-name">{s.name}</span>
                {bar && <span className="ingest-step-hint">{s.hint}</span>}
                {bar && bar.through > 0 && (
                  // no "0 / 0 files" before any file reached the step (IN-71)
                  <span className="ingest-step-bar">
                    <progress value={bar.passed} max={bar.through} aria-hidden="true" />
                    {`${String(bar.passed)} / ${String(bar.through)} files`}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {footer}
    </section>
  );
}
