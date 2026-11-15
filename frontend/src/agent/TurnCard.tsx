import { useState, type MouseEvent } from 'react';
import type { DrawingView, ProjectView } from '../api';
import { ChatAnswer, RefusedLine } from '../engineer/ChatAnswer';
import { routeHref } from '../shell/route';
import {
  blocksOf,
  inlineOf,
  splitCites,
  type ChatTurn,
  levelsByDrawing,
  type Evidence,
  type Proposal,
} from './agent';
import { EditCard } from './EditCard';
import { IssueAsk, type IssueReply } from './IssueAsk';
import './agent.css';

/** "Show it": the drawing in the engineer workspace at that place (engineer.md `?page=&box=`), keeping the
 * chat's country (`pack`, smoke-2) as an answer's Show it does. */
export function showHref(projectId: string, e: Evidence, pack: string | null = null): string {
  const query = new URLSearchParams({ page: String(e.page), box: e.box.join(',') });
  if (pack) query.set('pack', pack);
  return routeHref({
    name: 'workspace',
    projectId,
    drawingId: e.drawing_id,
    role: 'engineer',
    query,
  });
}

/** With the plan beside the chat, a source link shows its place there instead of leaving the chat (chat-ux #1);
 * a modified click still opens the workspace. */
const show = (e: Evidence, onShow?: (e: Evidence) => void) =>
  onShow &&
  ((ev: MouseEvent) => {
    if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    ev.preventDefault();
    onShow(e);
  });

/** "Bagno 1.01 · Drawn plan 1, page 1"; the server may leave the label or the drawing's name out. */
const where = (e: Evidence) =>
  `${e.label ?? 'Place'} · ${e.name ?? 'the drawing'}, page ${String(e.page)}`;

/** The turn's text (answers-1): paragraphs, lists, bold and http(s) links from the model's Markdown, as React
 * text (no HTML is ever parsed), with `[n]` source links. */
function Text({
  turn,
  projectId,
  pack,
  onShow,
}: {
  turn: ChatTurn;
  projectId: string;
  pack: string | null;
  onShow?: (e: Evidence) => void;
}) {
  const byN = new Map(turn.evidence.map((e) => [e.n, e]));
  const cites = (s: string) =>
    splitCites(s, [...byN.keys()]).map((part, i) => {
      if (typeof part === 'string') return part;
      const e = byN.get(part) as Evidence;
      return (
        <a
          key={i}
          className="ag-cite"
          href={showHref(projectId, e, pack)}
          aria-label={`Source ${String(part)}: ${where(e)}`}
          onClick={show(e, onShow)}
        >
          [{part}]
        </a>
      );
    });
  const line = (s: string) =>
    inlineOf(s).map((x, i) =>
      x.kind === 'a' ? (
        <a key={i} href={x.href} target="_blank" rel="noopener noreferrer">
          {x.text}
        </a>
      ) : x.kind === 'b' ? (
        <b key={i}>{cites(x.text)}</b>
      ) : x.kind === 'em' ? (
        <em key={i}>{cites(x.text)}</em>
      ) : (
        <span key={i}>{cites(x.text)}</span>
      ),
    );
  return (
    <div className="ag-text">
      {blocksOf(turn.text).map((b, i) => {
        if (b.kind === 'p')
          return (
            <p key={i}>
              {b.lines.map((l, j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  {line(l)}
                </span>
              ))}
            </p>
          );
        const List = b.kind;
        return (
          <List key={i} start={b.start}>
            {b.lines.map((l, j) => (
              <li key={j}>{line(l)}</li>
            ))}
          </List>
        );
      })}
    </div>
  );
}

const OPTIONS_LABEL = 'Try one of these instead';

const HEADLINE: Partial<Record<ChatTurn['kind'], string>> = {
  dont_know: "I don't know.",
  conflict: 'The sources disagree.',
};

/** One agent reply (AC-31): text with `[n]` source links, sources, the steps disclosure, and per kind the
 * refusal look, the conflict headline or the edit card (AC-32); option chips on any kind (needs_input's question,
 * or other questions to try after a dont_know). */
export function TurnCard(props: {
  turn: ChatTurn;
  projectId: string;
  /** For the pipeline's own answers (ChatAnswer): the project's drawings and the chat's rule pack. */
  project: ProjectView;
  pack: string | null;
  busy: boolean;
  onAsk: (message: string) => void;
  onDecided?: (p: Proposal) => void;
  /** Set when the plan is beside the chat: `[n]` and "Show it" show the place there. */
  onShow?: (e: Evidence) => void;
  /** The drawing an answer card shows (on open and on each switch): the chat opens it in the Files pane. */
  onReference?: (drawingId: string) => void;
  /** ask_issue (decision 0018): the person's answer to the issue, sent as the next turn. */
  onIssueAnswer?: (message: string, reply: IssueReply) => void;
  /** ask_issue: a later turn exists, so the issue is answered. */
  closed?: boolean;
  /** The drawings as read, by id: the asked issue's page. */
  drawings?: Record<string, DrawingView> | null;
}) {
  const { turn, projectId, project, pack, busy, onAsk } = props;
  // The ask chat's card for each answer some drawing answered. Its References number drawings and carry each
  // drawing's confidence (P5); the text's [n] number the marks and link to them (Tudor's smoke 3).
  const levels = levelsByDrawing(turn.evidence);
  const answers = turn.answers.filter((a) => a.parts.some((p) => p.answer.refusal === null));
  // K7: an answer no drawing answered has no card; its drawings are still named with what each lacks (the card
  // names the refused ones of the answers above)
  const refused = turn.answers.filter((a) => !answers.includes(a));
  const headline = HEADLINE[turn.kind];
  const options = turn.options ?? [];
  // Tudor's smoke (1): an edit's sources are its change: Show it and [n] show the card's own After plan.
  const [reveal, setReveal] = useState(0);
  const onShow =
    turn.kind === 'edit' && turn.edit
      ? () => {
          setReveal((n) => n + 1);
        }
      : props.onShow;
  return (
    <div className={`v-card ag-card ag-card--${turn.kind}`}>
      {headline && (
        <p className="ag-headline">
          <b>{headline}</b>
        </p>
      )}
      <Text turn={turn} projectId={projectId} pack={pack} onShow={onShow} />
      {answers.map((a, i) => (
        <ChatAnswer
          key={i}
          ask={a}
          project={project}
          projectId={projectId}
          pack={pack}
          levels={levels}
          onReference={props.onReference}
        />
      ))}
      {refused.map((a, i) => (
        <RefusedLine
          key={i}
          parts={a.parts}
          project={project}
          question={refused.length > 1 ? a.question : undefined}
        />
      ))}
      {turn.kind === 'ask_issue' && turn.issue && (
        <IssueAsk
          turn={turn}
          projectId={projectId}
          drawing={turn.issue.drawing_id ? props.drawings?.[turn.issue.drawing_id] : undefined}
          file={project.files.find((f) => f.id === turn.issue?.file_id)}
          busy={busy}
          closed={props.closed ?? false}
          onAnswer={(message, reply) => props.onIssueAnswer?.(message, reply)}
        />
      )}
      {turn.kind !== 'needs_input' && turn.kind !== 'ask_issue' && options.length > 0 && (
        <p className="en-small">{OPTIONS_LABEL}</p>
      )}
      {turn.kind !== 'ask_issue' && options.length > 0 && (
        <div
          className="en-suggest"
          role="group"
          aria-label={turn.kind === 'needs_input' ? 'Choose one' : OPTIONS_LABEL}
        >
          {options.map((o) => (
            <button
              key={o.label}
              type="button"
              className="en-chip v-press"
              title={o.message}
              disabled={busy}
              onClick={() => {
                onAsk(o.message);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
      {turn.kind === 'edit' && turn.edit && (
        <EditCard
          proposal={turn.edit}
          projectId={projectId}
          chatId={turn.chat_id}
          evidence={turn.evidence}
          onDecided={props.onDecided}
          reveal={reveal}
        />
      )}
    </div>
  );
}
