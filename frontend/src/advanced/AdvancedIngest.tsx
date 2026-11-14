import { useEffect, useState, type JSX } from 'react';
import type { FileStatus, ProjectView } from '../api';
import { STEPS, formatCost, formatMs, isFinished, stepOf } from '../ingest/ingest';
import {
  STATUS_WORD,
  STEP_VIEW,
  currentStep,
  defaultStep,
  elapsedMs,
  pairsOf,
  planCounts,
  quantityCount,
  stepLines,
  stepStatus,
} from './advanced';
import { useDrawingData } from './useDrawingData';
import { useProjectTrace } from './useProjectTrace';
import { CheckPairs, FileStrip, PlanMarks, ReadyList, RouteLanes } from './visuals';
import './advanced.css';

interface Stat {
  label: string;
  value: string;
}

const STEP_VIEW_FIRST = { heading: '', visual: 'files', explain: '' } as const;

const NOW_WORD = {
  working: 'Now',
  waiting: 'Waiting',
  done: 'Done',
  none: 'No file got here',
} as const;

/** Screens 9-12: the pipeline step by step (docs/specs/frontend/advanced-ingest.md). */
export function AdvancedIngest({
  projectId,
  project,
}: {
  projectId: string;
  project: ProjectView;
}): JSX.Element {
  const [picked, setPicked] = useState<number | null>(null);
  const step = picked ?? defaultStep(project);
  const view = STEP_VIEW[step - 1] ?? STEP_VIEW_FIRST;
  // A clock for Elapsed (now - started_at): ticks once a second; render itself stays pure.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, []);
  const current = currentStep(project);
  const isCurrent = current === step;
  const { traces, failed, retry } = useProjectTrace(projectId, project.files);
  const data = useDrawingData(
    project.drawings,
    view.visual === 'plan' || view.visual === 'pairs',
    view.visual === 'ready' || view.visual === 'lanes',
  );

  const working: FileStatus | null =
    project.files.find((f) => !isFinished(f) && stepOf(f.stage ?? null) === step) ?? null;
  const lines = stepLines(project.files, traces, step);
  const status = stepStatus(project, step).status;
  const takeoffs = [...data.takeoffs.values()];
  const pairs = pairsOf(takeoffs, project);

  const elapsed = (): Stat => {
    const ms = elapsedMs(project, now);
    return { label: 'Elapsed', value: ms === null ? '–' : formatMs(ms) };
  };
  const stats = (): Stat[] => {
    const files = project.files;
    const setAside = files.filter((f) => f.state === 'set_aside').length;
    const dash = (n: number | null) => (n === null ? '–' : String(n));
    switch (view.visual) {
      case 'files':
        return [
          elapsed(),
          {
            label: 'Files opened',
            value: `${String(files.filter((f) => f.stage != null).length)} / ${String(files.length)}`,
          },
          { label: 'Set aside', value: String(setAside) },
          { label: 'Cost', value: formatCost(project.cost_usd) },
        ];
      case 'lanes': {
        const routed = (r: (string | null | undefined)[]) =>
          String(files.filter((f) => r.includes(f.route)).length);
        return [
          elapsed(),
          { label: 'Exact geometry', value: routed(['bim', 'cad', 'vector']) },
          { label: 'From the image', value: routed(['raster']) },
          { label: 'Set aside', value: String(setAside) },
        ];
      }
      case 'plan': {
        const c = planCounts(project);
        const expected = project.expected_drawings;
        const ready = project.drawings.filter((d) => isFinished(d)).length;
        return [
          { label: 'Rooms', value: dash(c.room) },
          { label: 'Doors', value: dash(c.door) },
          { label: 'Windows', value: dash(c.window) },
          {
            label: 'Drawings ready',
            value: expected === null ? String(ready) : `${String(ready)} / ${String(expected)}`,
          },
        ];
      }
      case 'pairs': {
        if (takeoffs.length) {
          const agree = pairs.filter((p) => p.row.status === 'agree').length;
          const conflicts = pairs.filter((p) => p.row.status === 'conflict').length;
          return [
            elapsed(),
            { label: 'Measured twice', value: String(pairs.length) },
            { label: 'Agree', value: String(agree) },
            { label: 'Conflicts', value: String(conflicts) },
          ];
        }
        // Before any takeoff is loaded: the traces' second counts; "…" while loading, "–" when none ran.
        const counts = [...traces.values()].flatMap((t) => t.second_count ?? []);
        const sum = (f: (c: { measured: number; conflicts: number }) => number) =>
          counts.length ? String(counts.reduce((n, c) => n + f(c), 0)) : traces.size ? '–' : '…';
        return [
          elapsed(),
          { label: 'Measured twice', value: sum((c) => c.measured) },
          { label: 'Agree', value: sum((c) => c.measured - c.conflicts) },
          { label: 'Conflicts', value: sum((c) => c.conflicts) },
        ];
      }
      case 'ready':
        return [
          elapsed(),
          { label: 'Drawings', value: String(project.drawings.length) },
          { label: 'Questions ready', value: String(quantityCount(project)) },
          { label: 'Cost', value: formatCost(project.cost_usd) },
        ];
    }
  };

  const takeoffFailed = (id: string) => data.failed.has(`takeoff:${id}`);
  const visual = () => {
    switch (view.visual) {
      case 'files':
        return <FileStrip projectId={projectId} project={project} working={working} />;
      case 'lanes':
        return (
          <RouteLanes
            projectId={projectId}
            project={project}
            working={working}
            views={data.views}
          />
        );
      case 'plan':
        return (
          <PlanMarks
            projectId={projectId}
            project={project}
            takeoffs={data.takeoffs}
            failed={takeoffFailed}
            onRetry={(id) => {
              data.retry('takeoff', id);
            }}
            sweep={step === 5 && status === 'working'}
            showNormalised={step === 4}
          />
        );
      case 'pairs':
        return <CheckPairs projectId={projectId} pairs={pairs} />;
      case 'ready':
        return <ReadyList projectId={projectId} project={project} views={data.views} />;
    }
  };
  const live = lines.at(-1);

  return (
    <div className="adv">
      <nav aria-label="Steps" className="adv-rail">
        {STEPS.map((s, i) => {
          const k = i + 1;
          const st = stepStatus(project, k);
          return (
            <button
              key={s.name}
              type="button"
              className={`adv-step ${st.status}`}
              aria-pressed={k === step}
              aria-current={k === current ? 'step' : undefined}
              onClick={() => {
                setPicked(k);
              }}
            >
              <span className="adv-ring" aria-hidden="true">
                {st.status === 'done' ? '✓' : st.status === 'none' ? '–' : ''}
              </span>
              <span>{s.name}</span>
              <span className="adv-sr">, {STATUS_WORD[st.status]}</span>
              {st.setAside > 0 && (
                <span className="adv-aside">
                  <span className="adv-sr"> · </span>
                  {st.setAside} set aside
                </span>
              )}
            </button>
          );
        })}
      </nav>
      <section className="adv-panel" aria-label={view.heading}>
        <div className="adv-body">
          {visual()}
          <div className="adv-text">
            <span className="adv-now">
              {isCurrent && <span className="adv-spin" aria-hidden="true" />}
              {isCurrent ? 'Now' : NOW_WORD[status]}
            </span>
            <h2>{view.heading}</h2>
            <p>{view.explain}</p>
            <p className="adv-live" aria-live={isCurrent ? 'polite' : undefined}>
              {live ? `${live.path}: ${live.what}` : 'Nothing yet.'}
            </p>
            <ol className="adv-log" aria-label="Log" tabIndex={0}>
              {step === 1 &&
                project.skipped.map((s) => (
                  <li key={`skip-${s.path}`}>
                    Skip {s.path} {s.reason}
                  </li>
                ))}
              {lines.map((l) => (
                <li key={l.key} className={l.failure ? 'failed' : undefined}>
                  {l.text}
                  {l.cost > 0 && ` · ${formatCost(l.cost)}`}
                  {l.failure && (
                    <>
                      {' '}
                      <span aria-hidden="true">✕</span> Failed: {l.failure}
                    </>
                  )}
                </li>
              ))}
              {failed && (
                <li className="failed">
                  The trace did not load.{' '}
                  <button type="button" onClick={retry}>
                    Retry
                  </button>
                </li>
              )}
              {!lines.length && !failed && (
                <li>
                  {traces.size || !project.files.some((f) => f.stage)
                    ? 'Nothing yet.'
                    : 'Loading the trace…'}
                </li>
              )}
            </ol>
          </div>
        </div>
        <dl className="adv-stats">
          {stats().map((s) => (
            <div key={s.label}>
              <dt>{s.label}</dt>
              <dd>{s.value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
