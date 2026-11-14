import { useEffect, useId, useRef, useState } from 'react';
import {
  errorText,
  evidenceUrl,
  formatTime,
  formatValue,
  methodName,
  previewUrl,
  readerName,
  type AnswerView,
  type MarkView,
  type Reader,
  type Row,
} from '../api';
import { routeHref } from '../shell/route';
import { ChecksPanel } from './ChecksPanel';
import { MARKER, Suggestions } from './DrawingHeader';
import {
  formatCost,
  formatLatency,
  formatScore,
  GRADE_TIP,
  gradeOf,
  statusTip,
  statusWord,
  type Grade,
} from './format';
import { ModelProof } from './ModelProof';
import { Plan, type Place } from './Plan';

export type Turn =
  | { id: number; question: string; status: 'pending' }
  | { id: number; question: string; status: 'done'; answer: AnswerView }
  | { id: number; question: string; status: 'error'; error: unknown };

function sign(m: MarkView): string {
  if (m.state === 'rejected') return '×';
  if (m.state === 'excluded' || m.n === null) return '–';
  return m.state === 'added' ? `+${String(m.n)}` : String(m.n);
}

/** The viewer's words for a mark that is not simply counted. */
function stateWords(m: MarkView): string | null {
  if (m.state === 'rejected') return 'rejected by a surveyor';
  if (m.state === 'added') return 'added by a surveyor';
  if (m.state === 'excluded') return `left out by the rule${m.reason ? `: ${m.reason}` : ''}`;
  return null;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** How a misspelt question was read: the explanation's first sentence when it starts with "read '"
 * (backend #80), capitalised: "Read 'mnay' as 'many'". Shown on the card, since the typo reader can turn a
 * real word into another question (R2-2-1). */
function readAs(explanation: string | null): string | null {
  if (!explanation?.startsWith("read '")) return null;
  return cap(explanation.split('; ')[0] ?? explanation);
}

function cameFrom(r: Reader): string {
  // `none`: no second count ran for this drawing.
  const second =
    r.second_counter === 'none'
      ? 'no second count'
      : `second count by ${readerName(r.second_counter)}`;
  return `${readerName(r.extractor)} read ${r.source ?? 'no file'} (${r.route ?? 'no'} route), ${second}`;
}

function MarkList(props: {
  marks: MarkView[];
  unit: string | null;
  selected: string | null;
  onHover: (id: string | null) => void;
}) {
  const { marks, unit, selected, onHover } = props;
  const sum = unit !== 'count' && unit !== null;
  return (
    <ol className="en-marks">
      {marks.map((m) => {
        const words = stateWords(m);
        const counts = m.state === 'counted' || m.state === 'added';
        const leave = () => {
          onHover(null);
        };
        const enter = () => {
          onHover(m.id);
        };
        return (
          <li
            key={m.id}
            tabIndex={0}
            aria-selected={m.id === selected}
            onMouseEnter={enter}
            onMouseLeave={leave}
            onFocus={enter}
            onBlur={leave}
          >
            <span className="en-sign">{sign(m)}</span> {m.label ?? 'item'}
            {sum && counts && m.value !== null && ` ${formatValue(m.value, unit)}`}
            {words && ` ${words}`}
          </li>
        );
      })}
    </ol>
  );
}

// Golden's certified gate (backend #98): plan-level, on held-out CubiCasa test plans, 95% bound.
const SURE_TIP =
  'Certified: on held-out test plans, at least 96% of the plans marked sure had every sure answer exact';

const TONE: Record<Row['status'], string> = {
  signed: ' v-pill--ok',
  agree: ' v-pill--ok',
  conflict: ' v-pill--warn',
  estimate: ' v-pill--warn',
  edited: ' v-pill--warn',
  single: '',
};

/** The status in words, with its explanation as a tooltip on hover and focus. */
function StatusPill({ status }: { status: Row['status'] }) {
  const id = useId();
  const [tip, setTip] = useState(false);
  const show = () => {
    setTip(true);
  };
  const hide = () => {
    setTip(false);
  };
  return (
    <span className="en-pillwrap">
      <span
        className={`v-pill${TONE[status]} en-pill`}
        tabIndex={0}
        aria-describedby={id}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        {statusWord(status)}
      </span>
      <span role="tooltip" id={id} className="en-tip" hidden={!tip}>
        {statusTip(status)}
      </span>
    </span>
  );
}

const GRADE_TONE: Record<Grade, string> = {
  High: ' v-pill--ok',
  Medium: ' v-pill--warn',
  Low: ' v-pill--danger',
};
const STEPS: Record<Grade, number> = { High: 3, Medium: 2, Low: 1 };

type RefKind = 'original' | 'proof' | 'second';
interface Ref {
  kind: RefKind;
  what: string;
  file: string;
  where: string | null;
  /** The overlay's picture; null: a plain row. */
  src: string | null;
  alt: string;
}

function markRange(marks: MarkView[]): string {
  const ns = marks.flatMap((m) => (m.n === null ? [] : [m.n]));
  const pages = [...new Set(marks.map((m) => m.page))].sort((x, y) => x - y);
  if (ns.length === 0) return 'no marks';
  const p = `${pages.length > 1 ? 'Pages' : 'Page'} ${pages.join(', ')}`;
  const lo = Math.min(...ns);
  const hi = Math.max(...ns);
  return `${p} · ${lo === hi ? `mark ${String(lo)}` : `marks ${String(lo)}–${String(hi)}`}`;
}

function secondText(a: AnswerView): string {
  const row = a.quantity;
  if (row?.conflict) {
    return row.conflict.values
      .map((v) => `${formatValue(v.value, v.unit ?? row.unit)} by ${methodName(v.method)}`)
      .join('; ');
  }
  if (row?.second)
    return `${methodName(row.second.method)}: ${formatValue(row.second.value, row.unit)}`;
  return 'no second count';
}

function refsOf(a: AnswerView, projectId: string, place: Place | null): Ref[] {
  const refs: Ref[] = [];
  const source = a.reader.source;
  if (source) {
    const id = place?.originalId ?? null;
    refs.push({
      kind: 'original',
      what: 'Original file',
      file: source,
      where: cameFrom(a.reader),
      src: id && previewUrl(projectId, id),
      alt: `The original file ${source} as uploaded`,
    });
  }
  if (a.pages.length > 0) {
    refs.push({
      kind: 'proof',
      what: 'Proof drawn by the server',
      file: a.file,
      where: markRange(a.marks),
      // The server's picture still prints the old probability line: only without a score.
      src:
        a.confidence === null
          ? evidenceUrl(a.drawing_id, a.question, { project: projectId })
          : null,
      alt: `The server's proof on ${a.file} for "${a.question}"`,
    });
  }
  // No picture: the second method has values, not positions (#14 c6874945888).
  refs.push({
    kind: 'second',
    what: 'Second count',
    file: secondText(a),
    where: null,
    src: null,
    alt: '',
  });
  return refs;
}

/** The opened reference over the plan; Esc or Close closes it. */
function Overlay(props: { refItem: Ref; n: number; onClose: () => void }) {
  const { refItem: r, n, onClose } = props;
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    close.current?.focus();
  }, [r.kind]);
  return (
    <div
      className="en-overlay"
      role="dialog"
      aria-label={`${r.what}: ${r.file}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div className="en-overlay-bar">
        <span className="en-tag">{n}</span>
        <span className="en-ref-text">
          <span className="en-mono">{r.file}</span>
          {r.where && <span className="en-ref-where">{r.where}</span>}
        </span>
        <button
          ref={close}
          type="button"
          className="en-close v-press"
          aria-label="Close the original"
          onClick={onClose}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" />
          </svg>
        </button>
      </div>
      <img src={r.src ?? ''} alt={r.alt} />
    </div>
  );
}

function References(props: {
  refs: Ref[];
  open: RefKind | null;
  chips: React.RefObject<Partial<Record<RefKind, HTMLButtonElement | null>>>;
  onOpen: (k: RefKind) => void;
}) {
  const { refs, open, chips, onOpen } = props;
  return (
    <div className="en-refs">
      <h4 className="en-label">References</h4>
      <ol>
        {refs.map((r, i) => {
          const body = (
            <>
              <span className="en-tag">{i + 1}</span>
              <span className="en-ref-text">
                <span className="en-ref-what">{r.what}</span>
                <span className="en-mono">{r.file}</span>
                {r.where && <span className="en-ref-where">{r.where}</span>}
              </span>
            </>
          );
          return (
            <li key={r.kind}>
              {r.src ? (
                <button
                  ref={(el) => {
                    chips.current[r.kind] = el;
                  }}
                  type="button"
                  className="en-ref v-press"
                  aria-pressed={open === r.kind}
                  onClick={() => {
                    onOpen(r.kind);
                  }}
                >
                  {body}
                </button>
              ) : (
                <div className="en-ref">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Answer(props: {
  a: AnswerView;
  projectId: string;
  credit: string | null;
  place: Place | null;
}) {
  const { a, projectId, credit, place } = props;
  const [selected, setSelected] = useState<string | null>(null);
  const [hot, setHot] = useState<string | null>(null);
  const [open, setOpen] = useState<RefKind | null>(null);
  const chips = useRef<Partial<Record<RefKind, HTMLButtonElement | null>>>({});
  const row = a.quantity;
  // A raw model choice score (board #14), never shown as a probability.
  const score = a.confidence;
  const value = typeof a.answer === 'number' ? formatValue(a.answer, a.unit) : (a.answer ?? '');
  const surveyor =
    row &&
    routeHref({
      name: 'workspace',
      projectId,
      drawingId: a.drawing_id,
      role: 'surveyor',
      query: new URLSearchParams({ q: row.key }),
    });
  const refs = refsOf(a, projectId, place);
  const opened = refs.findIndex((r) => r.kind === open);
  const openRef = refs[opened];
  const close = () => {
    const k = open;
    setOpen(null);
    if (k) chips.current[k]?.focus();
  };
  const overlay = openRef && <Overlay refItem={openRef} n={opened + 1} onClose={close} />;
  // Row.noun ("doors"); null for areas and where the backend has none: then the label sentence.
  const noun = typeof a.answer === 'number' ? (row?.noun ?? null) : null;
  // Bogdan's coming field (#14 c6875035654), shape not final: only its reason, no mock.
  const check = (a as unknown as { check?: { reason?: string } | null }).check?.reason;
  const grade = gradeOf(a);
  return (
    <>
      <p className="en-sentence">
        {noun && typeof a.answer === 'number' ? (
          <>
            {a.answer === 1 ? 'There is ' : 'There are '}
            <strong>{value}</strong> {noun}.
          </>
        ) : (
          <>
            {row && `${cap(row.label)}: `}
            <strong>{value}</strong>.
          </>
        )}
        {row && ` ${cap(row.rule.text)}.`}
      </p>
      <div className="v-card en-card">
        <figure className="en-left" aria-label="Drawing">
          {a.pages.length > 0 ? (
            <Plan
              place={place}
              overlay={overlay}
              viewer={{
                file: a.file,
                pages: a.pages,
                marks: a.marks,
                credit,
                unit: a.unit,
                legend: a.proof.legend,
                conflict: row?.conflict ?? null,
                selected,
                highlighted: hot,
                onSelect: setSelected,
                onHover: setHot,
              }}
            />
          ) : (
            <div className="en-planbox">
              {a.proof.kind === 'model' && <ModelProof proof={a.proof} />}
              {overlay}
            </div>
          )}
          {a.marks.length > 0 && (
            <MarkList marks={a.marks} unit={a.unit} selected={selected} onHover={setHot} />
          )}
          {a.proof.arithmetic && <p className="en-arith">{a.proof.arithmetic}</p>}
        </figure>
        <div className="en-side">
          <div className="en-value-row">
            <span className="en-value" data-testid="answer-value">
              {value}
            </span>
            {noun && <span className="en-noun">{noun}</span>}
            {a.line.sure === true && (
              <span className="en-sure v-pill v-pill--ok" title={SURE_TIP}>
                Sure<span className="en-sr">. {SURE_TIP}</span>
              </span>
            )}
          </div>
          {check && (
            <p className="en-check" role="status" data-pending="AnswerView.check">
              {check}
            </p>
          )}
          {row?.signed && (
            <p className="en-verified">
              Verified by {row.signed.by}, {formatTime(row.signed.at)}
            </p>
          )}
          {grade && (
            <div className="en-grade">
              <div className="en-labelrow">
                <h4 className="en-label">Grade</h4>
                <span className={`v-pill${GRADE_TONE[grade]}`} title={GRADE_TIP}>
                  {grade}
                </span>
              </div>
              <span className="en-bar" aria-hidden="true">
                {[1, 2, 3].map((s) => (
                  <span key={s} className={s <= STEPS[grade] ? 'en-step en-step--on' : 'en-step'} />
                ))}
              </span>
              <p className="en-small">{GRADE_TIP}</p>
            </div>
          )}
          {row && (
            <div className="en-checks">
              <div className="en-labelrow">
                <h4 className="en-label">Checks</h4>
                <StatusPill status={row.status} />
              </div>
              <ChecksPanel row={row} />
            </div>
          )}
          {score && (
            <p className="en-score">
              Second reader's score {formatScore(score.score)} (not a probability)
            </p>
          )}
          {row && (
            <p className="en-rule">
              Counting rule: {row.rule.text} <span className="en-small">{row.rule.id}</span>
            </p>
          )}
          <References
            refs={refs}
            open={open}
            chips={chips}
            onOpen={(k) => {
              setOpen(k);
            }}
          />
        </div>
        {/* Inline: jsdom applies no stylesheet, so the tests can see the alignment rule. */}
        <footer className="en-foot" style={{ alignItems: 'baseline' }}>
          <span>Drawing {a.file}</span>
          <span>Cost {formatCost(a.cost_usd)}</span>
          <span>Time {formatLatency(a.latency_s)}</span>
          <details className="en-details">
            <summary style={MARKER}>Details</summary>
            {row && <p>Query: {row.label || row.key}</p>}
            <p>Method: {a.method}</p>
            {score && <p>Signal: {score.signal}</p>}
            {a.explanation && <p>How: {a.explanation}</p>}
          </details>
          {/* The server's picture still prints the old probability line: only without a score. */}
          {a.confidence === null && (
            <a
              href={evidenceUrl(a.drawing_id, a.question, { project: projectId })}
              target="_blank"
              rel="noopener"
            >
              Picture of this answer
            </a>
          )}
          {surveyor && <a href={surveyor}>Send to surveyor</a>}
        </footer>
      </div>
    </>
  );
}

function ErrorTurn({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { detail, code } = errorText(error);
  return (
    <div className="v-card en-error" role="alert">
      <p>The question could not be answered: {detail}</p>
      <p className="en-small">code: {code}</p>
      <button type="button" className="en-chip v-press" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

/** One question of the thread with its pending line, answer, refusal or error. */
export function AnswerCard(props: {
  turn: Turn;
  projectId: string;
  file: string;
  credit: string | null;
  place: Place | null;
  busy: boolean;
  onAsk: (question: string) => void;
  onRetry: (turn: Turn) => void;
}) {
  const { turn, projectId, file, credit, place, busy, onAsk, onRetry } = props;
  const question = turn.status === 'done' ? turn.answer.question : turn.question;
  const note = turn.status === 'done' ? readAs(turn.answer.explanation) : null;
  const refusal = turn.status === 'done' ? turn.answer.refusal : null;
  return (
    <article className="en-turn" aria-label={question}>
      <p className="en-bubble">{question}</p>
      {note && <p className="en-readas">{note}</p>}
      {turn.status === 'pending' && (
        <p className="en-pending" role="status">
          Reading {file}…
        </p>
      )}
      {turn.status === 'error' && (
        <ErrorTurn
          error={turn.error}
          onRetry={() => {
            onRetry(turn);
          }}
        />
      )}
      {refusal && (
        <div className="v-card en-refusal">
          <p>
            <b>I can't answer that from this drawing.</b>
          </p>
          <p>{refusal.text}</p>
          <Suggestions
            items={refusal.can_answer}
            busy={busy}
            onAsk={onAsk}
            label="Questions this drawing can answer"
          />
        </div>
      )}
      {turn.status === 'done' && !refusal && (
        <Answer a={turn.answer} projectId={projectId} credit={credit} place={place} />
      )}
    </article>
  );
}
