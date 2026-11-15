import type { CSSProperties } from 'react';
import type { FileTrace, StageTrace } from '../api';
import { STAGE_LABEL, formatCost, formatMs, plural } from '../ingest/ingest';
import { INGEST_TIPS, STAGE_TIPS } from '../shell/tips-ingest';
import {
  PHASE,
  decisions,
  foundLine,
  sideBySide,
  stageSpans,
  stepSpans,
  stepsOf,
  type Disagreement,
  type Span,
  type Step,
  type Tone,
} from './trace';
import './trace.css';
import { Tip } from '@/components/ui/tip';

const spanStyle = (s: Span) =>
  ({
    '--l': `${(100 * s.left).toFixed(2)}%`,
    '--w': `${(100 * s.width).toFixed(2)}%`,
  }) as CSSProperties;

function Track({ span, className }: { span: Span | null; className: string }) {
  if (!span) return null;
  return (
    <span className="tl-track" aria-hidden="true">
      <span className={`tl-span ${className}`} style={spanStyle(span)} />
    </span>
  );
}

const STEP_ICON = {
  done: { icon: '✓', word: 'done' },
  failed: { icon: '✕', word: 'failed' },
  skipped: { icon: '–', word: 'skipped' },
} as const;

function StepRow({ step, span }: { step: Step; span: Span | null }) {
  const state = STEP_ICON[step.state];
  const found = foundLine(step.found);
  return (
    <li className={`tl-step ${step.state}`}>
      <span className="tl-step-icon" role="img" aria-label={state.word}>
        {state.icon}
      </span>
      <span className="tl-step-label">{step.label}</span>
      <span className="tl-ms">
        {step.state === 'skipped' ? 'skipped' : formatMs(step.ms)}
        {step.cost_usd > 0 && ` · ${formatCost(step.cost_usd)}`}
      </span>
      <Track span={step.state === 'skipped' ? null : span} className="step" />
      {(step.did || found) && <p className="tl-step-did">{step.did || found}</p>}
    </li>
  );
}

/** Steps on one shared axis, one row each: steps that ran at the same time overlap on it. */
export function StepList({
  steps,
  ms = 0,
  label,
}: {
  steps: readonly Step[];
  ms?: number;
  label: string;
}) {
  const spans = stepSpans(steps, ms);
  return (
    <ol className="tl-steps" aria-label={label}>
      {steps.map((step, i) => (
        <StepRow key={`${step.id}-${String(i)}`} step={step} span={spans[i] ?? null} />
      ))}
    </ol>
  );
}

function StageRow({ s, span }: { s: StageTrace; span: Span | null }) {
  const steps = stepsOf(s);
  const together = sideBySide(steps);
  const label = STAGE_LABEL[s.stage];
  return (
    <li className={s.failure ? 'tl-stage failed' : 'tl-stage'}>
      <span className="tl-icon" role="img" aria-label={s.failure ? 'failed' : 'done'}>
        {s.failure ? '✕' : '✓'}
      </span>
      <div className="tl-body">
        <div className="tl-head">
          <Tip text={STAGE_TIPS[s.stage]} wrap className="justify-self-start">
            <b>{label}</b>
          </Tip>
          <span className="tl-ms">{formatMs(s.ms)}</span>
        </div>
        <Track span={span} className={`phase-${PHASE[s.stage]}`} />
        <p>{s.stage === 'cache' ? `Cached: ${s.did}` : s.did}</p>
        {s.stage === 'cache' && (
          <p className="output">the stages below are from the first ingest of this content</p>
        )}
        {s.output && s.output !== s.did && <p className="output">{s.output}</p>}
        {s.cost_usd > 0 && <p>Cost: {formatCost(s.cost_usd)}</p>}
        {s.failure && <p className="tl-failure">Failed: {s.failure}</p>}
        {steps.length > 0 && (
          <>
            <p className="tl-steps-note">
              {plural(steps.length, 'step')} inside {label}
              {together > 1 && `, up to ${String(together)} side by side`}
            </p>
            <StepList steps={steps} ms={s.ms} label={`Steps of ${label}`} />
          </>
        )}
      </div>
    </li>
  );
}

/** Every stage of one file on its time axis, with the steps that ran inside each (AD-101..AD-104). */
export function TraceTimeline({ stages }: { stages: readonly StageTrace[] }) {
  const spans = stageSpans(stages);
  const total = stages.reduce((sum, s) => sum + s.ms, 0);
  return (
    <section className="tl-card" aria-label="Stages">
      <div className="tl-title">
        <Tip text={INGEST_TIPS.stages}>
          <h2>How it was read: {plural(stages.length, 'stage')}</h2>
        </Tip>
        {total > 0 && <span className="tl-ms">{formatMs(total)} in all</span>}
      </div>
      {stages.length === 0 ? (
        <p>No stages yet.</p>
      ) : (
        <ol className="ingest-trace tl-list">
          {stages.map((s, i) => (
            <StageRow key={String(i)} s={s} span={spans[i] ?? null} />
          ))}
        </ol>
      )}
    </section>
  );
}

const TONE: Record<Tone, { icon: string; word: string }> = {
  ok: { icon: '✓', word: 'good' },
  warn: { icon: '!', word: 'needs a look' },
  bad: { icon: '✕', word: 'failed' },
  info: { icon: 'i', word: 'note' },
};

/** The decisions on the file's way, said where they happened (AD-105..AD-108). */
export function Decisions({
  trace,
  conflicts,
}: {
  trace: FileTrace;
  conflicts: readonly Disagreement[] | null;
}) {
  const list = decisions(trace, conflicts);
  return (
    <section className="tl-card" aria-label="Decisions">
      <div className="tl-title">
        <h2>Decisions on the way</h2>
      </div>
      <ol className="tl-decisions">
        {list.map((d) => (
          <li key={d.key} className={`tl-dec ${d.tone}`}>
            <span className="tl-dec-icon" role="img" aria-label={TONE[d.tone].word}>
              {TONE[d.tone].icon}
            </span>
            <div>
              <span className="tl-where">{d.where}</span>
              <b>{d.title}</b>
              {d.lines.map((l, i) => (
                <p key={String(i)}>{l}</p>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
