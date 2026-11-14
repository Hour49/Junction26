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
import { patch, requestLine, stateOf, toViewer } from './check';
import { checkOf, type Disputed } from './types';
import './doublecheck.css';

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
      className="dc-link"
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
      <section className="dc dc-checked" aria-label="Double-check">
        <span className="dc-pill dc-ok">Checked by a person</span>
        {s && (
          <p className="dc-ask">
            Checked by {s.by}, {formatTime(s.at)}
          </p>
        )}
        {refresh !== null && (
          <p role="alert" className="dc-error">
            Checked. The answer could not be refreshed: {refresh}{' '}
            <button type="button" className="dc-btn" onClick={() => void reask()}>
              Retry
            </button>
          </p>
        )}
        {error !== null && (
          <p role="alert" className="dc-error">
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
    <section className="dc" aria-label="Double-check">
      <div className="dc-top">
        <span className={`dc-pill ${fixing ? 'dc-fixing' : 'dc-warn'}`}>
          {fixing ? 'Fixing' : 'Please double-check'}
        </span>
        <p className="dc-ask">{requestLine(a, check)}</p>
        <p className="dc-reason">{check.reason}</p>
      </div>

      <div className="dc-body">
        <div className="dc-plan">
          {credit !== null && 'error' in credit && (
            <div role="alert" className="dc-error">
              {errorText(credit.error).detail}{' '}
              <button
                type="button"
                className="dc-btn"
                onClick={() => {
                  setCredit(null);
                  setCreditTry((n) => n + 1);
                }}
              >
                Retry
              </button>
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
        <ul className="dc-list" aria-label="Places to double-check">
          {check.disputed.map((d, i) => {
            const m = markOf(d);
            const out = m !== null && (m.state === 'rejected' || m.state === 'excluded');
            const label = placeName(d);
            return (
              <li key={i}>
                <button
                  type="button"
                  className="dc-place"
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
                  <strong>{label}</strong>
                  <span>{d.why}</span>
                  {Object.entries(d.readers).map(([reader, says]) => (
                    <small key={reader} className="dc-reader">
                      {readerName(reader)}: {says}
                    </small>
                  ))}
                </button>
                {fixing && m !== null && (
                  <button
                    type="button"
                    className="dc-btn"
                    disabled={busy}
                    onClick={() => {
                      edit({ action: out ? 'restore' : 'reject', mark: m.id });
                    }}
                  >
                    {out ? 'Restore' : 'Reject'} {label.toLowerCase()}
                  </button>
                )}
                {fixing && d.mark_id === null && isCount && (
                  <button
                    type="button"
                    className="dc-btn"
                    disabled={busy}
                    onClick={() => {
                      edit({ action: 'add', page: d.page, box: d.box as Edit['box'] });
                    }}
                  >
                    Add it here: page {d.page}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {fixing && (
        <p className="dc-value">
          <span>Value now:</span> <strong>{valueWords(a)}</strong>
        </p>
      )}

      {mode === 'confirm' ? (
        <div className="dc-confirm">
          <p className="dc-ask">Sign off {valueWords(a)} as</p>
          <label>
            Signing as{' '}
            <input
              type="text"
              maxLength={100}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </label>
          <div className="dc-buttons">
            <button
              type="button"
              className="dc-btn dc-primary"
              disabled={busy || name.trim() === ''}
              onClick={confirm}
            >
              Confirm
            </button>
            <button
              type="button"
              className="dc-btn"
              disabled={busy}
              onClick={() => {
                setMode('ask');
              }}
            >
              Back
            </button>
          </div>
        </div>
      ) : (
        <div className="dc-buttons">
          {fixing ? (
            <>
              <button
                type="button"
                className="dc-btn dc-primary"
                disabled={busy}
                onClick={() => {
                  setMode('confirm');
                }}
              >
                Done fixing
              </button>
              <button
                type="button"
                className="dc-btn"
                disabled={busy}
                onClick={() => {
                  setMode('ask');
                  setKept(edited);
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="dc-btn dc-primary"
                disabled={busy}
                onClick={() => {
                  setMode('confirm');
                }}
              >
                Looks right
              </button>
              <button
                type="button"
                className="dc-btn"
                disabled={busy}
                onClick={() => {
                  setMode('fixing');
                  setKept(false);
                }}
              >
                Fix it
              </button>
            </>
          )}
          {fixing && addable.length > 0 && (
            <button
              type="button"
              className="dc-btn"
              disabled={busy}
              aria-describedby={`${id}-add`}
              onClick={() => {
                const d = addable[0];
                if (d) edit({ action: 'add', page: d.page, box: d.box as Edit['box'] });
              }}
            >
              Add one
            </button>
          )}
          {fixing && addable.length > 0 && (
            <span id={`${id}-add`} className="dc-hint">
              Adds a mark where a reader saw one that was not counted.
            </span>
          )}
        </div>
      )}

      {kept && mode === 'ask' && (
        <p className="dc-kept">
          <span>Your edits are kept; Reset in the surveyor workspace undoes them.</span> {workspace}
        </p>
      )}
      {busy && (
        <p role="status" className="dc-hint">
          Saving…
        </p>
      )}
      {error !== null && (
        <p role="alert" className="dc-error">
          {error}
        </p>
      )}
    </section>
  );
}
