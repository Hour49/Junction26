import { useState } from 'react';
import { formatValue, type ProjectAnswer, type ProjectView } from '../api';
import { routeLabel } from '../ingest/ingest';
import { routeHref } from '../shell/route';
import { StatusPill, SURE_TIP } from './AnswerCard';
import { kindName } from './format';
import { Plan } from './Plan';
import { orderParts } from './projectAsk';

const Sure = () => (
  <span className="en-sure v-pill v-pill--ok" title={SURE_TIP}>
    Sure<span className="en-sr">. {SURE_TIP}</span>
  </span>
);

const Chevron = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path d={d} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
  </svg>
);

/** A project answer from one or more drawings (chat.md "Demo parity", CH-30..CH-35): the lead line, the current
 * reference drawn large with arrows on its sides, the rows per drawing and the numbered references. */
export function ChatAnswer(props: {
  ask: ProjectAnswer;
  project: ProjectView;
  projectId: string;
  pack: string | null;
}) {
  const { ask, project, projectId, pack } = props;
  const parts = orderParts(ask.parts, project.files);
  // Only parts with a page can be drawn; a building model is listed as "no preview".
  const drawn = parts.filter((p) => p.answer.pages.length > 0);
  const [at, setAt] = useState(0);
  const current = drawn[at];
  const step = (by: number) => {
    setAt((i) => (i + by + drawn.length) % drawn.length);
  };
  // That drawing opens answering this question (EN-72), in the chat's rule pack (QA R4b-1).
  const query = new URLSearchParams(pack ? { ask: ask.question, pack } : { ask: ask.question });
  const label = parts[0]?.answer.quantity?.label;
  const value = (p: (typeof parts)[number]) =>
    typeof p.answer.answer === 'number'
      ? formatValue(p.answer.answer, p.answer.unit)
      : (p.answer.answer ?? '');
  const about = (drawingId: string) => {
    const d = project.drawings.find((x) => x.drawing_id === drawingId);
    return d ? `${kindName(d.kind)} · ${routeLabel(d.route)}` : null;
  };

  return (
    <>
      {label && <p className="en-small">{label.charAt(0).toUpperCase() + label.slice(1)}</p>}
      {ask.total !== null ? (
        <p className="en-lead">
          <strong className="en-value" data-testid="answer-value">
            {formatValue(ask.total, ask.total_unit)}
          </strong>
          {ask.total_sure && <Sure />} <span className="en-muted">{ask.total_note}</span>
        </p>
      ) : (
        // The backend's sentence already says how many drawings answered.
        <p className="en-lead">{ask.total_note}</p>
      )}
      <div className="v-card en-chatcard">
        {current && (
          <figure
            className="en-chatfig"
            aria-label={`Reference ${String(at + 1)} of ${String(drawn.length)}`}
          >
            <Plan
              place={null}
              viewer={{
                file: current.name,
                pages: current.answer.pages,
                marks: current.answer.marks,
                credit: null,
                unit: current.answer.unit,
                legend: current.answer.proof.legend,
              }}
              overlay={
                drawn.length > 1 && (
                  <>
                    <button
                      type="button"
                      className="en-nav en-nav--prev v-press"
                      aria-label="Previous reference"
                      onClick={() => {
                        step(-1);
                      }}
                    >
                      <Chevron d="M15 6l-6 6 6 6" />
                    </button>
                    <button
                      type="button"
                      className="en-nav en-nav--next v-press"
                      aria-label="Next reference"
                      onClick={() => {
                        step(1);
                      }}
                    >
                      <Chevron d="M9 6l6 6-6 6" />
                    </button>
                  </>
                )
              }
            />
          </figure>
        )}
        <div className="en-side">
          <ul className="en-parts" aria-label="Per drawing">
            {parts.map((p) => (
              <li key={p.drawing_id}>
                <span>
                  <span className="en-part-name en-mono">{p.name}</span>: {value(p)}
                </span>
                <span className="en-pills">
                  {p.answer.quantity && <StatusPill status={p.answer.quantity.status} />}
                  {p.answer.line.sure === true && <Sure />}
                </span>
                <a
                  href={routeHref({
                    name: 'workspace',
                    projectId,
                    drawingId: p.drawing_id,
                    role: 'engineer',
                    query,
                  })}
                >
                  Show it on {p.name}
                </a>
              </li>
            ))}
          </ul>
          <div className="en-crefsbox">
            <span className="en-label">References</span>
            <ol className="en-crefs" aria-label="References">
              {parts.map((p, n) => {
                const k = drawn.indexOf(p);
                const sub = about(p.drawing_id);
                const body = (
                  <>
                    <span className="en-cnum">{n + 1}</span>
                    <span className="en-crefbody">
                      <span className="en-mono en-crefname">{p.name}</span>
                      <span className="en-muted">
                        {sub}
                        {k < 0 && `${sub ? ' · ' : ''}no preview`}
                      </span>
                    </span>
                  </>
                );
                return (
                  <li key={p.drawing_id}>
                    {k < 0 ? (
                      <span className="en-cref">{body}</span>
                    ) : (
                      <button
                        type="button"
                        className="en-cref v-press"
                        aria-pressed={k === at}
                        onClick={() => {
                          setAt(k);
                        }}
                      >
                        {body}
                      </button>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </>
  );
}
