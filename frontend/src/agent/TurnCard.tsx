import { routeHref } from '../shell/route';
import {
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

/** "Show it": the drawing in the engineer workspace at that place (engineer.md `?page=&box=`). */
export function showHref(projectId: string, e: Evidence): string {
  return routeHref({
    name: 'workspace',
    projectId,
    drawingId: e.drawing_id,
    role: 'engineer',
    query: new URLSearchParams({ page: String(e.page), box: e.box.join(',') }),
  });
}

const LEVEL_TONE: Record<Level['level'], string> = {
  high: ' v-pill--ok',
  medium: ' v-pill--warn',
  low: ' v-pill--danger',
};

/** "Confidence: High" with the level's text as its tooltip (ADR 0011, Bogdan 16:53). */
function Confidence({ level }: { level: Level }) {
  return (
    <span className={`v-pill${LEVEL_TONE[level.level]}`} title={level.text}>
      Confidence: {LEVEL_WORD[level.level]}
      <span className="en-sr">. {level.text}</span>
    </span>
  );
}

function Text({ turn, projectId }: { turn: ChatTurn; projectId: string }) {
  const byN = new Map(turn.evidence.map((e) => [e.n, e]));
  return (
    <p className="ag-text">
      {splitCites(turn.text, [...byN.keys()]).map((part, i) => {
        if (typeof part === 'string') return part;
        const e = byN.get(part) as Evidence;
        return (
          <a
            key={i}
            className="ag-cite"
            href={showHref(projectId, e)}
            aria-label={`Source ${String(part)}: ${e.label}, ${e.name}, page ${String(e.page)}`}
          >
            [{part}]
          </a>
        );
      })}
    </p>
  );
}

function Sources({ turn, projectId }: { turn: ChatTurn; projectId: string }) {
  return (
    <ol className="ag-sources" aria-label="Sources">
      {turn.evidence.map((e) => (
        <li key={e.id}>
          <span className="en-tag">{e.n}</span>
          <span>
            {e.label} · {e.name}, page {e.page}
          </span>
          {e.level && <Confidence level={e.level} />}
          <a href={showHref(projectId, e)}>Show it</a>
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

const HEADLINE: Partial<Record<ChatTurn['kind'], string>> = {
  dont_know: "I don't know.",
  conflict: 'The sources disagree.',
};

/** One agent reply (AC-31): text with `[n]` source links, sources, the steps disclosure, and per kind the
 * refusal look, the conflict headline, option chips (needs_input) or the edit card (AC-32). */
export function TurnCard(props: {
  turn: ChatTurn;
  projectId: string;
  busy: boolean;
  onAsk: (message: string) => void;
  onDecided?: (p: Proposal) => void;
}) {
  const { turn, projectId, busy, onAsk } = props;
  const headline = HEADLINE[turn.kind];
  return (
    <div className={`v-card ag-card ag-card--${turn.kind}`}>
      {headline && (
        <p className="ag-headline">
          <b>{headline}</b>
        </p>
      )}
      <Text turn={turn} projectId={projectId} />
      {turn.kind === 'needs_input' && turn.options && (
        <div className="en-suggest" role="group" aria-label="Choose one">
          {turn.options.map((o) => (
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
          onDecided={props.onDecided}
        />
      )}
      {turn.evidence.length > 0 && <Sources turn={turn} projectId={projectId} />}
      <Steps turn={turn} />
    </div>
  );
}
