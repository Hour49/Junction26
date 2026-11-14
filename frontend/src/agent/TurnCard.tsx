import { useState, type MouseEvent } from 'react';
import type { ProjectView } from '../api';
import { ChatAnswer } from '../engineer/ChatAnswer';
import { routeHref } from '../shell/route';
import {
  blocksOf,
  inlineOf,
  LEVEL_WORD,
  splitCites,
  stepsSummary,
  type ChatTurn,
  type Evidence,
  type Level,
  type Proposal,
} from './agent';
import { EditCard } from './EditCard';
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

const LEVEL_TONE: Record<Level['level'], string> = {
  high: ' v-pill--ok',
  medium: ' v-pill--warn',
  low: ' v-pill--danger',
};

/** "Confidence: High" with the level's text as its tooltip (ADR 0011, Bogdan 16:53). */
function Confidence({ level }: { level: Level }) {
  return (
    <span className={`v-pill${LEVEL_TONE[level.level]}`} title={level.text ?? undefined}>
      Confidence: {LEVEL_WORD[level.level]}
      {level.text && <span className="en-sr">. {level.text}</span>}
    </span>
  );
}

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

function Sources({
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
  return (
    <ol className="ag-sources" aria-label="Sources">
      {turn.evidence.map((e) => (
        <li key={e.id}>
          <span className="en-tag">{e.n}</span>
          <span>{where(e)}</span>
          {e.level && <Confidence level={e.level} />}
          <a href={showHref(projectId, e, pack)} onClick={show(e, onShow)}>
            Show it
          </a>
        </li>
      ))}
    </ol>
  );
}

function Steps({ turn }: { turn: ChatTurn }) {
  if (turn.steps.length === 0) return null;
  return (
    <details className="ag-steps">
      <summary>{stepsSummary(turn)}</summary>
      <ol>
        {turn.steps.map((s) => (
          <li key={s.n} className={s.status === 'error' ? 'ag-step--error' : undefined}>
            {s.label}
            {s.status === 'error' && <span className="ag-errmark"> · failed</span>}
          </li>
        ))}
      </ol>
    </details>
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
}) {
  const { turn, projectId, project, pack, busy, onAsk } = props;
  // The ask chat's card for each answer some drawing answered. Its References number drawings, so the Sources list
  // stays: the text's [n] number the marks (Tudor's smoke 3).
  const answers = turn.answers.filter((a) => a.parts.some((p) => p.answer.refusal === null));
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
        <ChatAnswer key={i} ask={a} project={project} projectId={projectId} pack={pack} />
      ))}
      {turn.kind !== 'needs_input' && options.length > 0 && (
        <p className="en-small">{OPTIONS_LABEL}</p>
      )}
      {options.length > 0 && (
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
      {turn.evidence.length > 0 && (
        <Sources turn={turn} projectId={projectId} pack={pack} onShow={onShow} />
      )}
      <Steps turn={turn} />
    </div>
  );
}
