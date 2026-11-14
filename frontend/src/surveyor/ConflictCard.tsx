import { useEffect, useId, useRef, useState } from 'react';
import {
  ApiError,
  errorText,
  formatValue,
  methodName,
  type ConflictEntry,
  type DrawingView,
} from '../api';
import { routeHref } from '../shell/route';
import { SourceFigure, type Source } from '../viewer/SourceFigure';
import { cardState, inUseIndex, parseAnswer, ruleIndex } from './conflicts';

/** A drawing for the source figure: loading (undefined), loaded, or failed. */
export type DrawingLoad = DrawingView | { error: unknown } | undefined;

interface Props {
  entry: ConflictEntry;
  index: number;
  total: number;
  projectId: string;
  pack?: string | null; // carried on the card's link (conflicts.md CF-33)
  focused?: boolean; // the card an issue link named (`?d=&q=`, CF-29)
  drawing: DrawingLoad;
  /** Asks the screen for the drawing (it fetches each drawing once); `retry` asks again after an error. */
  onNeedDrawing: (retry?: boolean) => void;
  /** Sends the edit and reloads the review; rejects with the POST's error. */
  onEdit: (edit: { action: 'settle'; value: number } | { action: 'unsettle' }) => Promise<void>;
}

type Mode = 'idle' | 'choosing' | 'saving';

const SIGNED = 'This value is signed off. Undo the sign-off in the surveyor workspace first.';

const UNIT: Record<string, string> = { m2: 'm²', m3: 'm³', m: 'm', ft: 'ft', ft2: 'ft²' };

/** One source: the drawing's page of the values, one place per value so the figure's numbers are the variants. */
function sourceOf(c: ConflictEntry, d: DrawingView): Source {
  const values = c.conflict.values;
  const at = values.find((v) => v.page)?.page ?? 1;
  return {
    name: c.file,
    page: d.pages.find((p) => p.page === at) ?? d.pages[0] ?? null,
    places: values.map((v) => {
      const here = !!v.box && (v.page ?? 1) === at;
      return {
        label: `${methodName(v.method)}: ${formatValue(v.value, v.unit ?? null)}${here ? '' : ', not located on this page'}`,
        box: here ? v.box : null,
      };
    }),
  };
}

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
  pack = null,
  focused = false,
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
  const [typed, setTyped] = useState('');
  const [typedError, setTypedError] = useState<string | null>(null);
  const article = useRef<HTMLElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!focused) return;
    article.current?.scrollIntoView({ block: 'center' });
    title.current?.focus();
  }, [focused]);
  const values = c.conflict.values;
  const unit = values[0]?.unit ?? null;
  const rule = ruleIndex(c);
  const inUse = inUseIndex(c);
  const value = c.value;
  useEffect(() => {
    if (drawing === undefined) onNeedDrawing();
  }, [drawing, onNeedDrawing]);

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
  function submitTyped() {
    const v = parseAnswer(typed, unit);
    if (typeof v === 'string') {
      setTypedError(v);
      return;
    }
    setTypedError(null);
    setTyped('');
    void send({ action: 'settle', value: v }, 'choosing');
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
              ? `Your answer: ${formatValue(c.settled?.value ?? 0, unit)}.` // typed here or in the workspace
              : `You kept variant ${String(inUse + 1)}${rule >= 0 && rule !== inUse ? ", over the rule's choice" : ''}.`
            : inUse < 0 && state === 'rule'
              ? `In use: ${formatValue(value, unit)}.` // a recount in the workspace: neither variant
              : '';
  const surveyorHref = routeHref({
    name: 'workspace',
    projectId,
    drawingId: c.drawing_id,
    role: 'surveyor',
    query: new URLSearchParams(pack ? { q: c.quantity, pack } : { q: c.quantity }),
  });
  const why = [c.conflict.resolution?.rule, c.conflict.note, c.conflict.derived].filter(
    (x): x is string => !!x,
  );
  const busy = mode === 'saving';

  return (
    <article
      ref={article}
      className={`cf-card${focused ? ' cf-focused' : ''}`}
      aria-labelledby={`${id}-t`}
      aria-current={focused ? 'true' : undefined}
    >
      <div className="cf-card-top">
        <div className="cf-card-head">
          <p className="cf-kicker">
            Conflict {index + 1} of {total} · {kicker ?? 'settled by you'}
          </p>
          <h2 id={`${id}-t`} ref={title} tabIndex={focused ? -1 : undefined}>
            {c.label}
          </h2>
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

      {drawing === undefined ? (
        <p role="status" className="cf-loading">
          Loading the drawing…
        </p>
      ) : 'error' in drawing ? (
        <div role="alert" className="cf-error">
          <p>{errorText(drawing.error).detail}</p>
          <button
            type="button"
            className="cf-btn"
            onClick={() => {
              onNeedDrawing(true);
            }}
          >
            Retry
          </button>
        </div>
      ) : (
        <SourceFigure
          sources={[sourceOf(c, drawing)]}
          label={`Source of conflict ${String(index + 1)}`}
          defaultOpen={focused || undefined}
        />
      )}

      <div className="cf-tiles">
        {values.map((v, i) => (
          <button
            key={i}
            type="button"
            className="cf-tile"
            aria-label={[
              `Variant ${String(i + 1)}: ${formatValue(v.value, v.unit ?? null)}`,
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
              Variant {i + 1}
              {i === rule ? " · the rule's choice" : ''}
              {i === inUse && (
                <svg className="cf-check" viewBox="0 0 20 20" aria-hidden="true">
                  <circle cx="10" cy="10" r="10" />
                  <path d="M5.5 10.5l3 3 6-6.5" />
                </svg>
              )}
            </span>
            <span className="cf-tile-value">{formatValue(v.value, v.unit ?? null)}</span>
            <span className="cf-tile-source">
              {methodName(v.method)}
              {v.page ? `, page ${String(v.page)}` : ''}
            </span>
          </button>
        ))}
      </div>

      {choosing && (
        <form
          className="cf-own"
          onSubmit={(e) => {
            e.preventDefault();
            submitTyped();
          }}
        >
          <label htmlFor={`${id}-own`}>Or type your own answer</label>
          <div className="cf-own-row">
            <span className="cf-own-field">
              <input
                id={`${id}-own`}
                inputMode="decimal"
                autoComplete="off"
                maxLength={20}
                value={typed}
                disabled={busy}
                aria-describedby={typedError === null ? undefined : `${id}-own-err`}
                onChange={(e) => {
                  setTyped(e.target.value);
                }}
              />
              {unit && UNIT[unit] && <span>{UNIT[unit]}</span>}
            </span>
            <button type="submit" className="cf-btn cf-primary" disabled={busy}>
              Use my answer
            </button>
          </div>
          {typedError !== null && (
            <p role="alert" id={`${id}-own-err`} className="cf-error">
              {typedError}
            </p>
          )}
        </form>
      )}

      <details className="cf-why">
        <summary>
          {rule >= 0 ? `Why the rule chose variant ${String(rule + 1)}` : 'Why no rule decides'}
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
              Modify
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
