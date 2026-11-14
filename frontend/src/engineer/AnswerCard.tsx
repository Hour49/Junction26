import { useState } from 'react';
import {
  errorText,
  evidenceUrl,
  formatTime,
  formatValue,
  type AnswerView,
  type MarkView,
  type Reader,
} from '../api';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import { ChecksPanel } from './ChecksPanel';
import { Suggestions } from './DrawingHeader';
import { formatCost, formatLatency, formatScore } from './format';
import { ModelProof } from './ModelProof';

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

/** How a misspelt question was read: the explanation's first sentence when it starts with "read '"
 * (backend #80), capitalised: "Read 'mnay' as 'many'". Shown on the card, since the typo reader can turn a
 * real word into another question (R2-2-1). */
function readAs(explanation: string | null): string | null {
  if (!explanation?.startsWith("read '")) return null;
  const note = explanation.split('; ')[0] ?? explanation;
  return `R${note.slice(1)}`;
}

function cameFrom(r: Reader): string {
  // `none`: no second count ran for this drawing.
  const second =
    r.second_counter === 'none' ? 'no second count' : `second count by ${r.second_counter}`;
  return `${r.extractor ?? 'nothing'} read ${r.source ?? 'no file'} (${r.route ?? 'no'} route), ${second}`;
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

function Answer(props: {
  a: AnswerView;
  projectId: string;
  credit: string | null;
  busy: boolean;
  onAsk: (q: string) => void;
}) {
  const { a, projectId, credit, busy, onAsk } = props;
  const [selected, setSelected] = useState<string | null>(null);
  const [hot, setHot] = useState<string | null>(null);
  if (a.refusal) {
    return (
      <div className="en-refusal">
        <p>
          <b>I can't answer that from this drawing.</b> {a.refusal.text}
        </p>
        <p className="en-small">code: {a.refusal.code}</p>
        <Suggestions items={a.refusal.can_answer} busy={busy} onAsk={onAsk} />
      </div>
    );
  }
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
  return (
    <div className="en-card">
      <div className="en-proof">
        {a.pages.length > 0 ? (
          <PageViewer
            file={a.file}
            pages={a.pages}
            marks={a.marks}
            credit={credit}
            unit={a.unit}
            legend={a.proof.legend}
            conflict={row?.conflict ?? null}
            selected={selected}
            highlighted={hot}
            onSelect={setSelected}
            onHover={setHot}
          />
        ) : (
          a.proof.kind === 'model' && <ModelProof proof={a.proof} />
        )}
        {a.marks.length > 0 && (
          <MarkList marks={a.marks} unit={a.unit} selected={selected} onHover={setHot} />
        )}
        {a.proof.arithmetic && <p className="en-arith">{a.proof.arithmetic}</p>}
      </div>
      <div className="en-side">
        {row && <h3 className="en-title">{row.label}</h3>}
        <p className="en-value" data-testid="answer-value">
          {value}
        </p>
        {row?.signed && (
          <p className="en-verified">
            Verified by {row.signed.by}, {formatTime(row.signed.at)}
          </p>
        )}
        {score && (
          <p className="en-score">
            Second reader's score {formatScore(score.score)} (not a probability)
          </p>
        )}
        {row && (
          <>
            <p className="en-rule">Counting rule: {row.rule.text}</p>
            <ChecksPanel row={row} />
          </>
        )}
        <h4>Where this came from</h4>
        <p className="en-small">{cameFrom(a.reader)}</p>
      </div>
      {/* Inline: jsdom applies no stylesheet, so the tests can see the alignment rule. */}
      <footer className="en-foot" style={{ alignItems: 'baseline' }}>
        <span>Drawing {a.file}</span>
        <span>Cost {formatCost(a.cost_usd)}</span>
        <span>Time {formatLatency(a.latency_s)}</span>
        <details className="en-details">
          <summary>Details</summary>
          {row && <p>Query: {row.key}</p>}
          <p>Method: {a.method}</p>
          {score && <p>Signal: {score.signal}</p>}
          {a.explanation && <p>How: {a.explanation}</p>}
        </details>
        {/* The server's picture still prints the old probability line: only without a score. */}
        {a.confidence === null && (
          <a href={evidenceUrl(a.drawing_id, a.question)} target="_blank" rel="noopener">
            Picture of this answer
          </a>
        )}
        {surveyor && <a href={surveyor}>Send to surveyor</a>}
      </footer>
    </div>
  );
}

function ErrorTurn({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { detail, code } = errorText(error);
  return (
    <div className="en-error" role="alert">
      <p>The question could not be answered: {detail}</p>
      <p className="en-small">code: {code}</p>
      <button type="button" onClick={onRetry}>
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
  busy: boolean;
  onAsk: (question: string) => void;
  onRetry: (turn: Turn) => void;
}) {
  const { turn, projectId, file, credit, busy, onAsk, onRetry } = props;
  const question = turn.status === 'done' ? turn.answer.question : turn.question;
  const note = turn.status === 'done' ? readAs(turn.answer.explanation) : null;
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
      {turn.status === 'done' && (
        <Answer a={turn.answer} projectId={projectId} credit={credit} busy={busy} onAsk={onAsk} />
      )}
    </article>
  );
}
