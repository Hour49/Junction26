import { useState } from 'react';
import { drawingLabel, formatValue, type ProjectAnswer, type ProjectView } from '../api';
import { routeLabel } from '../ingest/ingest';
import { routeHref } from '../shell/route';
import { GRADE_TONE, StatusPill } from './AnswerCard';
import { ResolverLines } from './Resolver';
import { estimateLine, gradeOf, kindName, levelWord, type Grade } from './format';
import { Plan } from './Plan';
import { orderParts } from './projectAsk';

/** "<Level> confidence" (CH-42), the backend's sentence as its tooltip when there is one. */
const LevelPill = ({ grade, text }: { grade: Grade; text?: string }) => (
  <span className={`v-pill${GRADE_TONE[grade]}`} title={text}>
    {grade} confidence
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
  // "2 doors" (EN-68's noun), as the demo's "11 doors"
  const noun = (n: string | null | undefined) => (n ? ` ${n}` : '');
  const value = (p: (typeof parts)[number]) =>
    typeof p.answer.answer === 'number'
      ? formatValue(p.answer.answer, p.answer.unit) + noun(p.answer.quantity?.noun)
      : (p.answer.answer ?? '');
  // CH-40: a drawing by its plain name (#224), else its file name; files keep their path
  const labelOf = (p: (typeof parts)[number]) =>
    drawingLabel(project.drawings.find((d) => d.drawing_id === p.drawing_id) ?? { file: p.name });
  const about = (drawingId: string) => {
    const d = project.drawings.find((x) => x.drawing_id === drawingId);
    return d ? `${kindName(d.kind)} · ${routeLabel(d.route)}` : null;
  };

  return (
    <>
      {ask.total !== null ? (
        // The demo's lead: the value only (CH-39); total_note is never shown, it can name refused drawings.
        <p className="en-lead">
          <strong className="en-value" data-testid="answer-value">
            {formatValue(ask.total, ask.total_unit) + noun(parts[0]?.answer.quantity?.noun)}
          </strong>
          {ask.total_level && (
            <>
              {' '}
              <LevelPill grade={levelWord(ask.total_level)} />
            </>
          )}
        </p>
      ) : (
        // The backend's sentence already says how many drawings answered; the refused ones are left out (#221).
        <p className="en-lead en-lead--why">{ask.why_no_total ?? ask.total_note}</p>
      )}
      <div className="v-card en-chatcard">
        {current && (
          <figure
            className="en-chatfig"
            aria-label={`Reference ${String(at + 1)} of ${String(drawn.length)}`}
          >
            {/* the viewer is bare (no name of its own): the demo's mono file name above the image */}
            <span className="en-chatname">{labelOf(current)}</span>
            <Plan
              place={null}
              viewer={{
                bare: true,
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
                  <span className="en-part-name">{labelOf(p)}</span>: <strong>{value(p)}</strong>
                </span>
                {/* one pill, as the demo: a sign-off, else the level, else the status (CH-42) */}
                {p.answer.quantity?.status === 'signed' ? (
                  <span className="v-pill v-pill--ok">Signed off</span>
                ) : gradeOf(p.answer) ? (
                  <LevelPill grade={gradeOf(p.answer) as Grade} text={p.answer.level?.text} />
                ) : (
                  p.answer.quantity && <StatusPill status={p.answer.quantity.status} />
                )}
                <a
                  className="en-show"
                  href={routeHref({
                    name: 'workspace',
                    projectId,
                    drawingId: p.drawing_id,
                    role: 'engineer',
                    query,
                  })}
                >
                  Show it on {labelOf(p)}
                </a>
                {estimateLine(p.answer) && <p className="en-estimate">{estimateLine(p.answer)}</p>}
                {/* CH-43: why, under the value, as a refusal gives its reason */}
                {(p.answer.check?.reason ?? p.answer.level?.text) && (
                  <p className="en-why">{p.answer.check?.reason ?? p.answer.level?.text}</p>
                )}
                <ResolverLines a={p.answer} />
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
                      <span className="en-crefname">{labelOf(p)}</span>
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
