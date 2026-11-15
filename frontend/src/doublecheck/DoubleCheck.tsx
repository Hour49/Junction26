import { LockTip } from '../shell/LockTip';
import { Tip } from '@/components/ui/tip';
import { REVIEW_TIPS } from '../shell/tips-review';
import { useEffect, useId, useState } from 'react';
import {
  ApiError,
  askQuestion,
  errorText,
  formatTime,
  formatValue,
  getDrawing,
  postReview,
  postSignoff,
  readerName,
  type AnswerView,
  type Edit,
  type SignOffRequest,
  type Takeoff,
} from '../api';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import { pageFlagged, patch, requestLine, stateOf, toViewer } from './check';
import { checkOf, type Disputed } from './types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

/** A pill button, 44 px tall; full width in a narrow window. */
const BTN =
  'min-h-11 px-[18px] text-base active:scale-[0.97] motion-reduce:active:scale-100 max-[760px]:flex-[1_1_100%]';
const PRIMARY = 'hover:bg-accent-strong';
const ERROR = 'm-0 text-danger';
const HINT = 'm-0 text-[13px] text-muted-foreground';
const ASK = 'm-0 text-[17px] font-semibold';
const BUTTONS = 'flex flex-wrap items-center gap-2';
const PILL = 'self-start px-2.5 py-[5px] text-xs font-semibold';
/** The panel; its layout follows its own width, not the window's (DC-19). */
const PANEL =
  '@container flex flex-col gap-4 rounded-2xl bg-warn-soft p-5 font-sans text-foreground';

interface Props {
  answer: AnswerView;
  projectId: string;
  drawingId: string;
  onChanged: (answer: AnswerView) => void;
}

type Mode = 'ask' | 'fixing' | 'confirm';
type Credit = { credit: string | null } | { error: unknown } | null;

const NAME_KEY = 'countersign.surveyorName'; // the surveyor workspace's key: one name for both

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}
function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, signing still works
  }
}

const SIGNED_ALREADY =
  'Someone signed this off already. Undo the sign-off in the surveyor workspace to change it.';

/** "2 doors" / "1 door" / "52.27 m²". */
function valueWords(a: AnswerView): string {
  const value = typeof a.answer === 'number' ? a.answer : 0;
  const noun = a.unit === 'count' ? a.quantity?.noun : null;
  if (!noun) return formatValue(value, a.unit);
  // shortcut: the backend's noun is plural ("doors"); a plain trailing s is dropped for 1
  return `${formatValue(value, a.unit)} ${value === 1 ? noun.replace(/s$/, '') : noun}`;
}

/** Bogdan's double-check state on one answer (docs/specs/frontend/double-check.md). */
export function DoubleCheck({ answer, projectId, drawingId, onChanged }: Props) {
  const id = useId();
  const [live, setLive] = useState({ from: answer, answer });
  if (live.from !== answer) setLive({ from: answer, answer }); // a new answer from the card wins
  const a = live.answer;
  const state = stateOf(a);
  const check = checkOf(a);
  const [mode, setMode] = useState<Mode>('ask');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState<string | null>(null); // a failed re-ask after the sign-off
  const [edited, setEdited] = useState(false);
  const [kept, setKept] = useState(false);
  const [name, setName] = useState(savedName);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [credit, setCredit] = useState<Credit>(null);
  const [creditTry, setCreditTry] = useState(0);
  const needs = state === 'needs';

  useEffect(() => {
    if (!needs) return;
    const abort = new AbortController();
    getDrawing(drawingId, { project: projectId, signal: abort.signal }).then(
      (d) => {
        setCredit({ credit: d.credit });
      },
      (e: unknown) => {
        if (!abort.signal.aborted) setCredit({ error: e });
      },
    );
    return () => {
      abort.abort();
    };
  }, [needs, drawingId, projectId, creditTry]);

  if (state === 'hidden' || a.quantity === null) return null;
  const row = a.quantity;
  const key = row.key;
  const isCount = a.unit === 'count';
  const workspace = (
    <a
      className="font-semibold text-primary"
      href={routeHref({
        name: 'workspace',
        projectId,
        drawingId,
        role: 'surveyor',
        query: new URLSearchParams({ q: key }),
      })}
    >
      Open in the surveyor workspace
    </a>
  );

  function show(next: AnswerView) {
    setLive({ from: answer, answer: next });
    onChanged(next);
  }
  async function reask() {
    setRefresh(null);
    try {
      show(
        await askQuestion({ question: a.question, drawing_id: drawingId, project_id: projectId }),
      );
    } catch (e) {
      setRefresh(errorText(e).detail);
    }
  }
  async function run(call: () => Promise<Takeoff>, after: (t: Takeoff) => Promise<void> | void) {
    setBusy(true);
    setError(null);
    try {
      await after(await call());
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(SIGNED_ALREADY);
        await reask();
      } else setError(errorText(e).detail);
    } finally {
      setBusy(false);
    }
  }
  const rowOf = (t: Takeoff) => t.quantities.find((q) => q.key === key) ?? null;
  function edit(e: Omit<Edit, 'quantity'>) {
    void run(
      () => postReview(drawingId, { quantity: key, ...e }, { project: projectId }),
      (t) => {
        const next = rowOf(t);
        if (next) show(patch(a, next));
        setEdited(true);
      },
    );
  }
  function confirm() {
    const by = name.trim();
    saveName(by);
    void run(
      // settle: true settles the current value and signs it off in one call (#121); undo defaults to false
      () =>
        postSignoff(drawingId, { quantity: key, by, settle: true } as SignOffRequest, {
          project: projectId,
        }),
      async (t) => {
        const next = rowOf(t);
        if (next) show(patch(a, next));
        setMode('ask');
        await reask();
      },
    );
  }

  if (state === 'checked') {
    const s = row.signed;
    return (
      <section className={cn(PANEL, 'gap-2 bg-ok-soft')} aria-label="Double-check">
        <Tip text={REVIEW_TIPS.checkedByPerson} wrap>
          <Badge className={cn(PILL, 'bg-card text-ok')}>Checked by a person</Badge>
        </Tip>
        {s && (
          <p className={ASK}>
            Checked by {s.by}, {formatTime(s.at)}
          </p>
        )}
        {refresh !== null && (
          <p role="alert" className={ERROR}>
            Checked. The answer could not be refreshed: {refresh}{' '}
            <Button variant="secondary" size="pill" className={BTN} onClick={() => void reask()}>
              Retry
            </Button>
          </p>
        )}
        {error !== null && (
          <p role="alert" className={ERROR}>
            {error}
          </p>
        )}
        {workspace}
      </section>
    );
  }

  if (!check) return null;
  const fixing = mode === 'fixing';
  const markOf = (d: Disputed) => a.marks.find((m) => m.id === d.mark_id) ?? null;
  const addable = isCount ? check.disputed.filter((d) => d.mark_id === null) : [];
  const placeName = (d: Disputed) => {
    if (d.mark_id === null) return `Not counted, page ${String(d.page)}`;
    const m = markOf(d);
    return m
      ? `Mark ${m.n === null ? (m.label ?? m.id) : String(m.n)}`
      : 'Not located on the drawing';
  };

  return (
    <section className={PANEL} aria-label="Double-check">
      <div className="flex flex-col items-start gap-1.5">
        <Tip text={fixing ? REVIEW_TIPS.fixing : REVIEW_TIPS.doubleCheck} wrap>
          <Badge className={cn(PILL, fixing ? 'bg-accent text-primary' : 'bg-card text-warn')}>
            {fixing ? 'Fixing' : 'Please double-check'}
          </Badge>
        </Tip>
        <p className={ASK}>{requestLine(a, check)}</p>
        {/* on a flagged page the generic rule ("counts once") says nothing; the card's level text says why */}
        {!pageFlagged(a) && <p className="dc-reason m-0 text-sm text-text-2">{check.reason}</p>}
      </div>

      {/* one column in a narrow panel (the answer card's side column, phones): the card's own plan shows the marks */}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 @min-[680px]:grid-cols-[minmax(0,1fr)_320px]">
        <div className="hidden min-w-0 overflow-hidden rounded-[var(--v-radius)] bg-card @min-[680px]:block">
          {credit !== null && 'error' in credit && (
            <div role="alert" className={ERROR}>
              {errorText(credit.error).detail}{' '}
              <Button
                variant="secondary"
                size="pill"
                className={BTN}
                onClick={() => {
                  setCredit(null);
                  setCreditTry((n) => n + 1);
                }}
              >
                Retry
              </Button>
            </div>
          )}
          <PageViewer
            file={a.file}
            pages={a.pages}
            marks={a.marks}
            credit={credit !== null && 'credit' in credit ? credit.credit : null}
            unit={a.unit}
            disputed={toViewer(check.disputed)}
            selected={selected}
            highlighted={hover}
            onSelect={setSelected}
            onHover={setHover}
            fixMode={fixing && isCount}
            onAddMark={
              fixing && isCount && !busy
                ? (box, page) => {
                    edit({ action: 'add', page, box });
                  }
                : undefined
            }
          />
        </div>
        <ul className="m-0 flex list-none flex-col gap-2 p-0" aria-label="Places to double-check">
          {check.disputed.map((d, i) => {
            const m = markOf(d);
            const out = m !== null && (m.state === 'rejected' || m.state === 'excluded');
            const label = placeName(d);
            return (
              <li key={i} className="flex flex-col gap-1.5">
                <button
                  type="button"
                  className="flex min-h-11 cursor-pointer flex-col items-start gap-0.5 rounded-[14px] border border-border bg-card px-3 py-2.5 text-left text-sm text-foreground [overflow-wrap:anywhere] disabled:cursor-not-allowed disabled:text-muted-foreground aria-[current=true]:border-2 aria-[current=true]:border-primary aria-[current=true]:bg-accent aria-[current=true]:px-[11px] aria-[current=true]:py-[9px]"
                  disabled={busy}
                  aria-current={m !== null && m.id === selected ? 'true' : undefined}
                  onMouseEnter={() => {
                    setHover(m?.id ?? null);
                  }}
                  onMouseLeave={() => {
                    setHover(null);
                  }}
                  onFocus={() => {
                    setHover(m?.id ?? null);
                  }}
                  onBlur={() => {
                    setHover(null);
                  }}
                  onClick={() => {
                    setSelected(m?.id ?? null);
                  }}
                >
                  <strong className="text-warn">{label}</strong>
                  <span>{d.why}</span>
                  {Object.entries(d.readers).map(([reader, says]) => (
                    <small key={reader} className="dc-reader block text-xs text-muted-foreground">
                      {readerName(reader)}: {says}
                    </small>
                  ))}
                </button>
                {fixing && m !== null && (
                  <Button
                    variant="secondary"
                    size="pill"
                    className={BTN}
                    disabled={busy}
                    onClick={() => {
                      edit({ action: out ? 'restore' : 'reject', mark: m.id });
                    }}
                  >
                    {out ? 'Restore' : 'Reject'} {label.toLowerCase()}
                  </Button>
                )}
                {fixing && d.mark_id === null && isCount && (
                  <Button
                    variant="secondary"
                    size="pill"
                    className={BTN}
                    disabled={busy}
                    onClick={() => {
                      edit({ action: 'add', page: d.page, box: d.box as Edit['box'] });
                    }}
                  >
                    Add it here: page {d.page}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {fixing && (
        <p className="m-0 text-[15px] tabular-nums">
          <span>Value now:</span> <strong className="text-xl">{valueWords(a)}</strong>
        </p>
      )}

      {mode === 'confirm' ? (
        <div className="flex flex-col gap-2.5">
          <p className={ASK}>Sign off {valueWords(a)} as</p>
          <label className="grid gap-1">
            Signing as
            <Input
              type="text"
              className="h-11 rounded-xl bg-card px-3 text-base md:text-base"
              maxLength={100}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </label>
          <div className={BUTTONS}>
            <Button
              size="pill"
              className={cn(BTN, PRIMARY)}
              disabled={busy || name.trim() === ''}
              onClick={confirm}
            >
              Confirm
            </Button>
            <Button
              variant="secondary"
              size="pill"
              className={BTN}
              disabled={busy}
              onClick={() => {
                setMode('ask');
              }}
            >
              Back
            </Button>
          </div>
        </div>
      ) : (
        <div className={BUTTONS}>
          {fixing ? (
            <>
              <Button
                size="pill"
                className={cn(BTN, PRIMARY)}
                disabled={busy}
                onClick={() => {
                  setMode('confirm');
                }}
              >
                Done fixing
              </Button>
              <Button
                variant="secondary"
                size="pill"
                className={BTN}
                disabled={busy}
                onClick={() => {
                  setMode('ask');
                  setKept(edited);
                }}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <LockTip text={REVIEW_TIPS.looksRight} locked={busy}>
                <Button
                  size="pill"
                  className={cn(BTN, PRIMARY)}
                  disabled={busy}
                  onClick={() => {
                    setMode('confirm');
                  }}
                >
                  Looks right
                </Button>
              </LockTip>
              <LockTip text={REVIEW_TIPS.fixIt} locked={busy}>
                <Button
                  variant="secondary"
                  size="pill"
                  className={BTN}
                  disabled={busy}
                  onClick={() => {
                    setMode('fixing');
                    setKept(false);
                  }}
                >
                  Fix it
                </Button>
              </LockTip>
            </>
          )}
          {fixing && addable.length > 0 && (
            <Button
              variant="secondary"
              size="pill"
              className={BTN}
              disabled={busy}
              aria-describedby={`${id}-add`}
              onClick={() => {
                const d = addable[0];
                if (d) edit({ action: 'add', page: d.page, box: d.box as Edit['box'] });
              }}
            >
              Add one
            </Button>
          )}
          {fixing && addable.length > 0 && (
            <span id={`${id}-add`} className={HINT}>
              Adds a mark where a reader saw one that was not counted.
            </span>
          )}
        </div>
      )}

      {kept && mode === 'ask' && (
        <p className={HINT}>
          <span>Your edits are kept; Reset in the surveyor workspace undoes them.</span> {workspace}
        </p>
      )}
      {busy && (
        <p role="status" className={HINT}>
          Saving…
        </p>
      )}
      {error !== null && (
        <p role="alert" className={ERROR}>
          {error}
        </p>
      )}
    </section>
  );
}
