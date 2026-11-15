import { Fragment, useRef, useState } from 'react';
import { drawingLabel, type ProjectAnswer, type ProjectView } from '../api';
import { routeLabel } from '../ingest/ingest';
import { GRADE_TONE, PartialTag, StatusPill, TipIf, WhyToggle } from './AnswerCard';
import { ResolverLines } from './Resolver';
import { estimateLine, gradeOf, kindName, levelWord, shownValue, type Grade } from './format';
import { Plan } from './Plan';
import { PlanSheet } from '../agent/PlanPane';
import { PageViewer } from '../viewer/PageViewer';
import { orderParts } from './projectAsk';
import { ModelDialog } from '../model3d/ModelDialog';
import { canShow3d } from '../model3d/model3d';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

type Part = ProjectAnswer['parts'][number];
type RefusalCode = NonNullable<Part['answer']['refusal']>['code'];

/** K7: what a refused drawing lacks, by refusal code (the backend's LACKS, singular). */
const LACKS: Record<RefusalCode, string> = {
  'no-reader': 'gives no reliable number for it',
  'no-scale': 'has no scale',
  'not-in-drawing': "doesn't show it",
  'not-read': "wasn't read for it",
  'unsupported-question': "can't answer this question",
  'no-drawing': 'has no drawing model',
};
/** More refused drawings than this are grouped by reason ("Has no scale: A, B, C."). */
const GROUP_ABOVE = 3;

/** K7: the drawings that refused, named with what each lacks, in the API's order; none, nothing. Used under a
 * project answer (ChatAnswer) and under the project chat's refusal when every drawing refuses (ProjectChat).
 * `question` names the ask the line belongs to, for a turn that holds several. */
export function RefusedLine(props: { parts: Part[]; project: ProjectView; question?: string }) {
  const refused = props.parts.flatMap((p) =>
    p.answer.refusal ? [{ p, code: p.answer.refusal.code }] : [],
  );
  if (refused.length === 0) return null;
  const name = (p: Part) => (
    <span className="en-part-name">
      {drawingLabel(
        props.project.drawings.find((d) => d.drawing_id === p.drawing_id) ?? { file: p.name },
      )}
    </span>
  );
  const asked = props.question ? `“${props.question}” — ` : '';
  if (refused.length <= GROUP_ABOVE)
    return (
      <p className="en-refused" data-testid="refused-drawings">
        {asked}Not used:{' '}
        {refused.map(({ p, code }, n) => (
          <span key={p.drawing_id}>
            {n > 0 && '; '}
            {name(p)} {LACKS[code]}
          </span>
        ))}
        .
      </p>
    );
  const groups = new Map<RefusalCode, Part[]>();
  for (const { p, code } of refused) groups.set(code, [...(groups.get(code) ?? []), p]);
  return (
    <p className="en-refused" data-testid="refused-drawings">
      {asked}Not used.
      {[...groups].map(([code, ps]) => (
        <span key={code}>
          {' '}
          {LACKS[code].charAt(0).toUpperCase() + LACKS[code].slice(1)}:{' '}
          {ps.map((p, n) => (
            <Fragment key={p.drawing_id}>
              {n > 0 && ', '}
              {name(p)}
            </Fragment>
          ))}
          .
        </span>
      ))}
    </p>
  );
}

/** "<Level> confidence" (CH-42), the backend's sentence as its tooltip (the shared Tip) when there is one. */
const LevelPill = ({ grade, text }: { grade: Grade; text?: string }) => (
  <TipIf text={text}>
    <span className={`v-pill${GRADE_TONE[grade]}`}>{grade} confidence</span>
  </TipIf>
);

/** A project answer from one or more drawings (chat.md "Demo parity", CH-30..CH-35; ui-bugs 4-9): the lead line,
 * the chosen reference drawn large with the numbered references under it, and that one drawing's card beside it. */
const viewerOf = (p: { name: string; answer: ProjectAnswer['parts'][number]['answer'] }) => ({
  file: p.name,
  pages: p.answer.pages,
  marks: p.answer.marks,
  credit: null,
  unit: p.answer.unit,
  legend: p.answer.proof.legend,
});

export function ChatAnswer(props: {
  ask: ProjectAnswer;
  project: ProjectView;
  projectId: string;
  pack: string | null;
}) {
  const { ask, project, projectId } = props;
  const parts = orderParts(ask.parts, project.files);
  // The reference shown: the first with a page; a building model (no page) shows "No preview" when chosen.
  const [at, setAt] = useState(() =>
    Math.max(
      0,
      parts.findIndex((p) => p.answer.pages.length > 0),
    ),
  );
  // model-3d.md part 2: the part whose 3D view is open, and the button that opened it (focus goes back)
  const [model, setModel] = useState<(typeof parts)[number] | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const current = parts[Math.min(at, parts.length - 1)];
  // phone grade: the shown reference in the full viewer (zoom, legend), over the chat
  const [big, setBig] = useState(false);
  const enlarge = useRef<HTMLButtonElement | null>(null);
  const closeBig = () => {
    setBig(false);
    enlarge.current?.focus();
  };
  const has3d = (p: (typeof parts)[number]) => canShow3d(p.model_3d) && Boolean(p.model_file_id);
  // W3 (look-check #404): the button only when the SHOWN drawing has a model; an IFC file is its own model,
  // a 2D drawing's model is the building's (another file), so it says so
  const model3d = current && has3d(current) ? current : undefined;
  const ownModel =
    model3d && project.drawings.find((d) => d.drawing_id === model3d.drawing_id)?.kind === 'ifc';
  // "2 doors" (EN-68's noun), as the demo's "11 doors"
  const noun = (n: string | null | undefined) => (n ? ` ${n}` : '');
  // The value the server shows (`answer`: an estimated area in whole m², #294), as the answer card says it (CH-48).
  const value = (p: (typeof parts)[number]) =>
    typeof p.answer.answer === 'number'
      ? shownValue(p.answer.answer, p.answer.unit, Boolean(p.answer.quantity?.estimate)) +
        noun(p.answer.quantity?.noun)
      : (p.answer.answer ?? '');
  // The total is in whole m² when a part in it is an estimate (the backend's _total), so it reads as they do.
  const estimated = parts.some((p) => p.answer.refusal === null && p.answer.quantity?.estimate);
  // CH-40: a drawing by its plain name (#224), else its file name; files keep their path
  const labelOf = (p: (typeof parts)[number]) =>
    drawingLabel(project.drawings.find((d) => d.drawing_id === p.drawing_id) ?? { file: p.name });
  // ui-bugs 7: why a value was refused or flagged stays on screen; the confidence sentence is behind "Why?"
  // CH-50: methods that disagree say which value was kept and why (their pill says it is below)
  const reason = (p: (typeof parts)[number]) =>
    p.answer.check?.reason ??
    (p.answer.quantity?.status === 'conflict' ? (p.answer.explanation ?? undefined) : undefined);
  // CH-46: the reason already says it is an estimate and why (the backend quotes it): one line, not two
  const estimate = (p: (typeof parts)[number]) => {
    const e = p.answer.quantity?.estimate;
    return e && reason(p)?.includes(e) ? null : estimateLine(p.answer);
  };
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
            {shownValue(ask.total, ask.total_unit, estimated) +
              noun(parts[0]?.answer.quantity?.noun)}
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
        <figure
          className="en-chatfig"
          aria-label={`Reference ${String(at + 1)} of ${String(parts.length)}`}
        >
          {current && (
            <>
              {/* the viewer is bare (no name of its own): the name above the image, the 3D button at its right */}
              <div className="en-chathead">
                <span className="en-chatname">{labelOf(current)}</span>
                {model3d && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          className="size-11 rounded-full text-xs font-bold"
                          aria-label={
                            ownModel
                              ? `View in 3D: ${labelOf(model3d)}`
                              : 'View the building model in 3D'
                          }
                          onClick={(e) => {
                            opener.current = e.currentTarget;
                            setModel(model3d);
                          }}
                        >
                          3D
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {ownModel ? 'Open the 3D model' : 'Open the building model in 3D'}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
              {current.answer.pages.length > 0 ? (
                <>
                  {/* phone grade: a tap on the image (not a mark) opens the full viewer with its zoom */}
                  <div
                    className="en-chatthumb"
                    onClick={(e) => {
                      if (!(e.target as HTMLElement).closest('button')) setBig(true);
                    }}
                  >
                    <Plan place={null} viewer={{ ...viewerOf(current), bare: true }} />
                  </div>
                  <Button
                    ref={enlarge}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="en-enlarge min-h-11"
                    onClick={() => {
                      setBig(true);
                    }}
                  >
                    Enlarge the plan
                  </Button>
                  {big && (
                    <PlanSheet onClose={closeBig}>
                      <div className="flex min-w-0 flex-1 flex-col overflow-auto overscroll-contain">
                        <div className="flex justify-end p-2">
                          <Button
                            type="button"
                            variant="outline"
                            className="min-h-11"
                            onClick={closeBig}
                          >
                            Close
                          </Button>
                        </div>
                        <PageViewer {...viewerOf(current)} />
                      </div>
                    </PlanSheet>
                  )}
                </>
              ) : model3d ? (
                // R4-F6: a building model has no page; its evidence is the 3D view, so the box opens it
                <div className="en-nopreview">
                  <Button
                    type="button"
                    className="min-h-11"
                    onClick={(e) => {
                      opener.current = e.currentTarget;
                      setModel(model3d);
                    }}
                  >
                    {typeof model3d.answer.answer === 'number'
                      ? `See the ${value(model3d)} in 3D`
                      : 'See it in 3D'}
                  </Button>
                </div>
              ) : (
                <p className="en-nopreview">No preview for this file</p>
              )}
            </>
          )}
          <div className="en-side">
            {/* ui-bugs 6: only the card of the drawing shown; W2: right under its image, no half-empty column */}
            <ul className="en-parts" aria-label="Per drawing">
              {current && (
                <li key={current.drawing_id}>
                  <span>
                    <span className="en-part-name">{labelOf(current)}</span>:{' '}
                    <strong>{value(current)}</strong>
                  </span>
                  {/* CH-49: a room total that may leave rooms out; the explanation names them */}
                  <PartialTag a={current.answer} />
                  {/* one pill, as the demo: a sign-off, else the level, else the status (CH-42) */}
                  {current.answer.quantity?.status === 'signed' ? (
                    <span className="v-pill v-pill--ok">Signed off</span>
                  ) : gradeOf(current.answer) ? (
                    <LevelPill
                      grade={gradeOf(current.answer) as Grade}
                      text={current.answer.level?.text}
                    />
                  ) : (
                    current.answer.quantity && (
                      <StatusPill status={current.answer.quantity.status} />
                    )
                  )}
                  {estimate(current) && <p className="en-estimate">{estimate(current)}</p>}
                  {/* CH-43: why a value was refused or flagged, under the value */}
                  {reason(current) && <p className="en-why">{reason(current)}</p>}
                  <WhyToggle text={current.answer.level?.text} />
                  <ResolverLines a={current.answer} />
                </li>
              )}
            </ul>
          </div>
          <div className="en-crefsbox">
            <span className="en-label">References</span>
            <ol className="en-crefs" aria-label="References">
              {parts.map((p, n) => {
                const sub = about(p.drawing_id);
                return (
                  <li key={p.drawing_id}>
                    <button
                      type="button"
                      className="en-cref v-press"
                      aria-pressed={n === at}
                      onClick={() => {
                        setAt(n);
                      }}
                    >
                      <span className="en-cnum">{n + 1}</span>
                      <span className="en-crefbody">
                        <span className="en-crefname">{labelOf(p)}</span>
                        <span className="en-muted">
                          {sub}
                          {p.answer.pages.length === 0 && `${sub ? ' · ' : ''}no preview`}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
        </figure>
      </div>
      {/* K7: orderParts keeps only the answering drawings; the refused ones are named here */}
      <RefusedLine parts={ask.parts} project={project} />
      {model?.model_file_id && (
        <ModelDialog
          projectId={projectId}
          fileId={model.model_file_id}
          label={labelOf(model)}
          highlight={model.highlight ?? []}
          onClose={() => {
            setModel(null);
            opener.current?.focus();
          }}
        />
      )}
    </>
  );
}
