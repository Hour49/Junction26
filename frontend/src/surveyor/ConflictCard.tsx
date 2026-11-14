import { useEffect, useId, useState } from 'react';
import {
  ApiError,
  errorText,
  formatValue,
  methodName,
  type ConflictEntry,
  type DrawingView,
} from '../api';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import { cardState, inUseIndex, letter, ruleIndex } from './conflicts';

/** A drawing for the evidence: loading (undefined), loaded, or failed. */
export type DrawingLoad = DrawingView | { error: unknown } | undefined;

interface Props {
  entry: ConflictEntry;
  index: number;
  total: number;
  projectId: string;
  drawing: DrawingLoad;
  /** Asks the screen for the drawing (it fetches each drawing once); `retry` asks again after an error. */
  onNeedDrawing: (retry?: boolean) => void;
  /** Sends the edit and reloads the review; rejects with the POST's error. */
  onEdit: (edit: { action: 'settle'; value: number } | { action: 'unsettle' }) => Promise<void>;
}

type Mode = 'idle' | 'choosing' | 'saving';

const SIGNED = 'This value is signed off. Undo the sign-off in the surveyor workspace first.';

const PILL = {
  open: ['Needs you', 'cf-warn'],
  rule: ['Settled by rule', 'cf-ok'],
  yours: ['Your choice', 'cf-accent'],
} as const;

/** One conflict of the project (conflicts.md "Field map", "States"). */
export function ConflictCard({
  entry: c,
  index,
  total,
  projectId,
  drawing,
  onNeedDrawing,
  onEdit,
}: Props) {
  const id = useId();
  const state = cardState(c);
  const signed = c.signed;
  const [mode, setMode] = useState<Mode>(state === 'open' ? 'choosing' : 'idle');
  // The server's state changed (a reload after an edit): the mode starts over, the open details stay.
  const serverState = `${String(c.needs_person)} ${String(c.settled?.value)} ${String(c.signed?.at)}`;
  const [seen, setSeen] = useState(serverState);
  if (seen !== serverState) {
    setSeen(serverState);
    setMode(state === 'open' ? 'choosing' : 'idle');
  }
  const [error, setError] = useState<unknown>(null);
  const [open, setOpen] = useState(false);
  const values = c.conflict.values;
  const unit = values[0]?.unit ?? null;
  const rule = ruleIndex(c);
  const inUse = inUseIndex(c);
  const value = c.value;
  const evidenceOpen = open || (state === 'open' && !signed);
  useEffect(() => {
    if (evidenceOpen && drawing === undefined) onNeedDrawing();
  }, [evidenceOpen, drawing, onNeedDrawing]);

  const choosing = mode === 'choosing' && !signed;
  const [pillWords, pillClass] = signed
    ? [`Signed off by ${signed.by}`, 'cf-ok']
    : mode === 'choosing' && state !== 'open'
      ? ['Choosing', 'cf-muted']
      : PILL[state];
  const tip = signed
    ? 'Undo the sign-off in the surveyor workspace to change it.'
    : mode === 'choosing' && state !== 'open'
      ? 'Tap the right value, or Cancel.'
      : state === 'open'
        ? 'The rules could not decide. Pick a value before you open the workspace.'
        : state === 'rule'
          ? `A rule settled this: ${String(c.conflict.resolution?.rule)}. Modify it if you disagree.`
          : 'You picked this value; it overrides the rule.';
  const kicker = state === 'open' ? 'needs you' : state === 'rule' ? 'settled by a rule' : null;

  async function send(edit: Parameters<Props['onEdit']>[0], back: Mode) {
    setMode('saving');
    setError(null);
    try {
      await onEdit(edit);
      // only if the reload did not already reset the mode (same server state)
      setMode((m) => (m === 'saving' ? (state === 'open' ? 'choosing' : 'idle') : m));
    } catch (e) {
      setError(e);
      setMode(back);
    }
  }
  function pick(i: number) {
    const v = values[i];
    if (!v) return;
    if (i === inUse && state !== 'open')
      setMode('idle'); // already in use: just leave choosing
    else void send({ action: 'settle', value: v.value }, 'choosing');
  }
  function useRule() {
    void send({ action: 'unsettle' }, 'idle'); // drops the settled value only (no confirm: nothing else is lost)
  }

  const action =
    mode === 'saving'
      ? 'Saving…'
      : signed
        ? ''
        : choosing
          ? 'Tap the right value.'
          : state === 'yours'
            ? inUse < 0
              ? `You settled it at ${formatValue(c.settled?.value ?? 0, unit)} in the surveyor workspace.`
              : `You kept ${letter(inUse)}${rule >= 0 && rule !== inUse ? ", over the rule's choice" : ''}.`
            : inUse < 0 && state === 'rule'
              ? `In use: ${formatValue(value, unit)}.` // a recount in the workspace: neither variant
              : '';
  const surveyorHref = routeHref({
    name: 'workspace',
    projectId,
    drawingId: c.drawing_id,
    role: 'surveyor',
    query: new URLSearchParams({ q: c.quantity }),
  });
  const why = [c.conflict.resolution?.rule, c.conflict.note, c.conflict.derived].filter(
    (x): x is string => !!x,
  );
  const busy = mode === 'saving';
  const loaded = drawing && !('error' in drawing) ? drawing : null;

  return (
    <article className="cf-card" aria-labelledby={`${id}-t`}>
      <div className="cf-card-top">
        <div className="cf-card-head">
          <p className="cf-kicker">
            Conflict {index + 1} of {total} · {kicker ?? 'settled by you'}
          </p>
          <h2 id={`${id}-t`}>{c.label}</h2>
          <p className="cf-file">{c.file}</p>
        </div>
        <span className="cf-pill-wrap">
          <span className={`cf-pill ${pillClass}`} tabIndex={0} aria-describedby={`${id}-tip`}>
            {pillWords}
          </span>
          <span role="tooltip" id={`${id}-tip`} className="cf-tip">
            {tip}
          </span>
        </span>
      </div>

      <div className="cf-tiles">
        {values.map((v, i) => (
          <button
            key={i}
            type="button"
            className="cf-tile"
            aria-label={[
              `${letter(i)}: ${formatValue(v.value, v.unit ?? null)}`,
              methodName(v.method),
              v.page ? `page ${String(v.page)}` : null,
              i === rule ? "the rule's choice" : null,
              i === inUse ? 'in use' : null,
            ]
              .filter(Boolean)
              .join(', ')}
            aria-pressed={i === inUse}
            disabled={busy || !!signed || mode !== 'choosing'}
            onClick={() => {
              pick(i);
            }}
          >
            <span className="cf-tile-kicker">
              {letter(i)}
              {i === rule ? " · the rule's choice" : ''}
            </span>
            <span className="cf-tile-value">{formatValue(v.value, v.unit ?? null)}</span>
            <span className="cf-tile-source">
              {methodName(v.method)}
              {v.page ? `, page ${String(v.page)}` : ''}
            </span>
            {i === inUse && <span className="cf-badge">in use</span>}
          </button>
        ))}
      </div>

      <details className="cf-why">
        <summary>
          {rule >= 0 ? `Why the rule chose ${letter(rule)}` : 'Why no rule decides'}
        </summary>
        {why.length > 0 ? (
          <ul>
            {why.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        ) : (
          <p>No rule decides between these methods. Both readings are on the drawing.</p>
        )}
      </details>

      <details className="cf-evidence" open={evidenceOpen}>
        <summary
          onClick={(e) => {
            e.preventDefault();
            setOpen(!evidenceOpen);
          }}
        >
          Where each value was read
        </summary>
        {evidenceOpen &&
          (drawing === undefined ? (
            <p role="status">Loading the drawing…</p>
          ) : 'error' in drawing ? (
            <div role="alert" className="cf-error">
              <p>{errorText(drawing.error).detail}</p>
              <button
                type="button"
                onClick={() => {
                  onNeedDrawing(true);
                }}
              >
                Retry
              </button>
            </div>
          ) : (
            loaded && (
              <>
                <PageViewer
                  file={loaded.file}
                  pages={loaded.pages}
                  credit={loaded.credit}
                  marks={[]}
                  unit={unit}
                  conflict={c.conflict}
                />
                {values.map((v, i) =>
                  v.box ? null : <p key={i}>{letter(i)}: not located on the page.</p>,
                )}
              </>
            )
          ))}
      </details>

      <div className="cf-actions">
        <p className="cf-action-text">{action}</p>
        <div className="cf-buttons">
          {!signed && state !== 'open' && mode === 'idle' && (
            <button
              type="button"
              className="cf-btn"
              onClick={() => {
                setMode('choosing');
              }}
            >
              {state === 'rule' ? 'Modify' : 'Change'}
            </button>
          )}
          {!signed && state === 'yours' && mode === 'idle' && c.conflict.resolution && (
            <button type="button" className="cf-btn" onClick={useRule}>
              Use the rule&apos;s value
            </button>
          )}
          {state !== 'open' && mode === 'choosing' && (
            <button
              type="button"
              className="cf-btn"
              onClick={() => {
                setMode('idle');
              }}
            >
              Cancel
            </button>
          )}
          <a className="cf-link" href={surveyorHref}>
            Open in the surveyor workspace
          </a>
        </div>
      </div>
      {error !== null && (
        <p role="alert" className="cf-error">
          {error instanceof ApiError && error.status === 409 ? SIGNED : errorText(error).detail}
        </p>
      )}
    </article>
  );
}
