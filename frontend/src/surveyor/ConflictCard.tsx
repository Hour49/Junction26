import { Fragment, useEffect, useId, useRef, useState } from 'react';
import {
  ApiError,
  errorText,
  formatValue,
  methodName,
  resolverModel,
  resolverName,
  type ConflictEntry,
  type DrawingView,
} from '../api';
import { SourceFigure, type Place, type Source } from '../viewer/SourceFigure';
import { Tip } from '@/components/ui/tip';
import { REVIEW_TIPS } from '../shell/tips-review';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  cardState,
  inUseIndex,
  newSuggestions,
  parseAnswer,
  ruleIndex,
  whyText,
  type Answer,
} from './conflicts';

/** A drawing for the source figure: loading (undefined), loaded, or failed. */
export type DrawingLoad = DrawingView | { error: unknown } | undefined;

interface Props {
  entry: ConflictEntry;
  index: number;
  total: number;
  drawingName: string; // the drawing's plain name (drawingLabel, #224)
  focused?: boolean; // the card an issue link named (`?d=&q=`, CF-29)
  drawing: DrawingLoad;
  /** Asks the screen for the drawing (it fetches each drawing once); `retry` asks again after an error. */
  onNeedDrawing: (retry?: boolean) => void;
  /** Sends the edit and reloads the review; rejects with the POST's error. */
  onEdit: (edit: ({ action: 'settle' } & Answer) | { action: 'unsettle' }) => Promise<void>;
}

type Mode = 'idle' | 'choosing' | 'saving';

const SIGNED = 'This value is signed off. Undo the sign-off in the surveyor workspace first.';

const UNIT: Record<string, string> = { m2: 'm²', m3: 'm³', m: 'm', ft: 'ft', ft2: 'ft²' };

/** One source: the drawing's page of the marks, with each value's marks (#221 `value_marks`) as its places, then
 * the model's marks when its answer is shown (`who`, #252 RS-11). */
function sourceOf(c: ConflictEntry, d: DrawingView, name: string, who: string | null): Source {
  const { values } = c.conflict;
  // a backend before #221 sends no value_marks: the drawing without outlines, never a crash
  const marks = (c.conflict.value_marks as typeof c.conflict.value_marks | undefined) ?? [];
  const at = marks.flat()[0]?.page ?? values.find((v) => v.page)?.page ?? 1;
  const place = (label: string, m: { page: number; box: NonNullable<Place['box']> }): Place => {
    const here = m.page === at;
    return {
      label: `${label}${here ? '' : `, on page ${String(m.page)}`}`,
      box: here ? m.box : null,
    };
  };
  return {
    name,
    page: d.pages.find((p) => p.page === at) ?? d.pages[0] ?? null,
    // a mark label may be a method id: methodName gives its words and leaves any other label as is
    places: [
      ...marks.flatMap((list, i) =>
        list.map((m) => place(`Variant ${String(i + 1)}: ${methodName(m.label)}`, m)),
      ),
      ...(who ? (c.resolved?.marks ?? []).map((m) => place(`${who}: ${m.label}`, m)) : []),
    ],
  };
}

// the label in sentence case: the title of an entry from a backend before #226 (which has no `title`)
const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// the pill's words and its Badge variant
const PILL = {
  open: ['Needs you', 'warn'],
  rule: ['Settled by rule', 'ok'],
  picked: ['', 'accent'], // words from `resolved.by`
  yours: ['Your choice', 'accent'],
} as const;

/** The card's buttons: the demo's 44 px pills (conflicts.md "Demo parity"). */
export const BTN =
  'v-press px-5 text-base font-semibold disabled:bg-secondary disabled:text-muted-foreground disabled:opacity-100';
/** Modify, the demo's .btn-soft: accent text on the soft accent (CF-47). */
export const SOFT = 'cf-soft bg-accent text-primary hover:bg-accent hover:text-primary';

/** One conflict of the project (conflicts.md "Field map", "States"). */
export function ConflictCard({
  entry: c,
  index,
  total,
  drawingName,
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
  const ownInput = useRef<HTMLInputElement>(null);
  const chips = newSuggestions(c);
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
  // the model's answer, shown while its pick is in use or while it could not tell (#252)
  const r = c.resolved;
  const shown =
    r && (state === 'picked' || (r.verdict === 'cannot_tell' && state === 'open')) ? r : null;
  const who = shown
    ? shown.verdict === 'picked'
      ? `Picked by ${resolverName(shown.by)}`
      : `${resolverName(shown.by)} could not tell`
    : null;
  useEffect(() => {
    if (drawing === undefined) onNeedDrawing();
  }, [drawing, onNeedDrawing]);

  const choosing = mode === 'choosing' && !signed;
  const [pillWords, pillClass] = signed
    ? [`Signed off by ${signed.by}`, 'ok' as const]
    : mode === 'choosing' && state !== 'open'
      ? ['Choosing', 'secondary' as const]
      : state === 'picked'
        ? [who ?? '', PILL.picked[1]]
        : PILL[state];
  const tip = signed
    ? 'Undo the sign-off in the surveyor workspace to change it.'
    : mode === 'choosing' && state !== 'open'
      ? 'Tap the right value, or Cancel.'
      : state === 'open'
        ? 'The rules could not decide. Pick a value before you open the workspace.'
        : state === 'rule'
          ? `A rule settled this: ${String(c.conflict.resolution?.rule)}. Modify it if you disagree.`
          : state === 'picked'
            ? `${resolverName(r?.by ?? '')} picked this value. Modify it if you disagree.`
            : 'You picked this value; it overrides the rule.';
  const kicker =
    state === 'open'
      ? 'needs you'
      : state === 'rule'
        ? 'settled by a rule'
        : state === 'picked'
          ? `picked by ${resolverName(r?.by ?? '')}`
          : null;

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
    void send({ action: 'settle', ...v }, 'choosing');
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
            ? c.settled?.note
              ? `You answered: “${c.settled.note}”.`
              : inUse < 0
                ? `Your answer: ${formatValue(c.settled?.value ?? 0, unit)}.` // typed here or in the workspace
                : `You kept variant ${String(inUse + 1)}${rule >= 0 && rule !== inUse ? ", over the rule's choice" : ''}.`
            : state === 'picked'
              ? 'You can change it.'
              : inUse < 0 && state === 'rule'
                ? `In use: ${formatValue(value, unit)}.` // a recount in the workspace: neither variant
                : '';

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
            <Tip text={REVIEW_TIPS.conflictKicker} wrap>
              <span>
                Conflict {index + 1} of {total} · {kicker ?? 'settled by you'}
              </span>
            </Tip>
          </p>
          <h2 id={`${id}-t`} ref={title} tabIndex={focused ? -1 : undefined}>
            {c.title || sentence(c.label)}
          </h2>
          <p className="cf-file">{drawingName}</p>
        </div>
        <Tip text={tip} className="flex-none">
          <Badge
            variant={pillClass}
            className="cf-pill flex-none px-2.5 py-[5px] text-xs font-semibold data-[variant=secondary]:text-text-2"
            tabIndex={0}
          >
            {pillWords}
          </Badge>
        </Tip>
      </div>

      {drawing === undefined ? (
        <p role="status" className="cf-loading">
          Loading the drawing…
        </p>
      ) : 'error' in drawing ? (
        <div role="alert" className="cf-error">
          <p>{errorText(drawing.error).detail}</p>
          <Button
            variant="secondary"
            size="pill"
            className={BTN}
            onClick={() => {
              onNeedDrawing(true);
            }}
          >
            Retry
          </Button>
        </div>
      ) : (
        <SourceFigure
          sources={[sourceOf(c, drawing, drawingName, shown?.verdict === 'picked' ? who : null)]}
          label={`Source of conflict ${String(index + 1)}`}
          defaultOpen={focused || undefined}
        />
      )}

      <div className="cf-tiles">
        {values.map((v, i) => {
          const locked = busy || !!signed || mode !== 'choosing';
          const tile = (
            <button
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
              disabled={locked}
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
          );
          // a disabled button gets no hover: the tip sits on a focusable wrapper then (ui-tooltips P1)
          return locked && (!!signed || busy) ? (
            <Tip key={i} text={REVIEW_TIPS.choiceLocked} wrap className="flex">
              {tile}
            </Tip>
          ) : (
            <Fragment key={i}>{tile}</Fragment>
          );
        })}
      </div>

      {shown && who && (
        <p className="cf-resolved">
          <strong title={resolverModel(shown.by)}>{who}</strong> <span>{shown.reason}</span>
        </p>
      )}

      {choosing && (
        <form
          className="cf-own"
          onSubmit={(e) => {
            e.preventDefault();
            submitTyped();
          }}
        >
          <label htmlFor={`${id}-own`}>Or type your own answer</label>
          {chips.length > 0 && (
            <div className="cf-chips">
              {chips.map((x) => (
                <Button
                  key={x}
                  variant="secondary"
                  className="h-auto min-h-10 rounded-full px-3.5 py-[9px] text-left text-sm font-normal whitespace-normal hover:bg-accent max-[600px]:min-h-11"
                  onClick={() => {
                    setTyped(x); // fills the box; "Use my answer" sends it
                    ownInput.current?.focus();
                  }}
                >
                  {x}
                </Button>
              ))}
            </div>
          )}
          <div className="cf-own-row">
            <span className="cf-own-field">
              <Input
                className="h-auto min-h-11 flex-1 rounded-none border-0 bg-transparent px-0 text-[15px] text-foreground shadow-none focus-visible:ring-0 md:text-[15px] max-[600px]:text-base"
                ref={ownInput}
                id={`${id}-own`}
                autoComplete="off"
                maxLength={280}
                value={typed}
                disabled={busy}
                aria-describedby={typedError === null ? undefined : `${id}-own-err`}
                onChange={(e) => {
                  setTyped(e.target.value);
                }}
              />
              {unit && UNIT[unit] && <span>{UNIT[unit]}</span>}
            </span>
            <Button type="submit" size="pill" className={BTN} disabled={busy}>
              Use my answer
            </Button>
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
        {whyText(c) ? (
          <p>{whyText(c)}</p>
        ) : why.length > 0 ? (
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
            <Button
              size="pill"
              className={`${BTN} ${SOFT}`}
              onClick={() => {
                setMode('choosing');
              }}
            >
              Modify
            </Button>
          )}
          {/* no "use the rule's value" when the value kept is the rule's (R4-B11) */}
          {!signed &&
            state === 'yours' &&
            mode === 'idle' &&
            c.conflict.resolution &&
            c.conflict.resolution.value !== c.value && (
              <Button variant="secondary" size="pill" className={BTN} onClick={useRule}>
                Use the rule&apos;s value
              </Button>
            )}
          {!signed &&
            state === 'yours' &&
            mode === 'idle' &&
            !c.conflict.resolution &&
            r?.verdict === 'picked' && (
              <Button variant="secondary" size="pill" className={BTN} onClick={useRule}>
                Use {resolverName(r.by)}&apos;s pick
              </Button>
            )}
          {state !== 'open' && mode === 'choosing' && (
            <Button
              variant="secondary"
              size="pill"
              className={BTN}
              onClick={() => {
                setMode('idle');
              }}
            >
              Cancel
            </Button>
          )}
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
