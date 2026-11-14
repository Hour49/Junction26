import { useEffect, useRef, useState } from 'react';
import {
  askProject,
  formatValue,
  getDrawing,
  getProject,
  type ProjectAnswer,
  type ProjectView,
  type Suggestion,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { routeHref } from '../shell/route';
import { AnswerCard, SURE_TIP, type Turn } from './AnswerCard';
import { AskBox } from './AskBox';
import { Suggestions } from './DrawingHeader';
import { askable, starters } from './projectAsk';
import './engineer.css';

type ChatTurn =
  | { id: number; question: string; status: 'pending' }
  | { id: number; question: string; status: 'error'; error: unknown }
  | { id: number; question: string; status: 'done'; ask: ProjectAnswer };

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; project: ProjectView };

/** The total, then one line per answering drawing with a link to show it (chat.md). */
function PartsCard({ ask, projectId }: { ask: ProjectAnswer; projectId: string }) {
  const answering = ask.parts.filter((p) => p.answer.refusal === null);
  const label = answering[0]?.answer.quantity?.label;
  return (
    <div className="v-card en-chatcard">
      {label && <p className="en-small">{label.charAt(0).toUpperCase() + label.slice(1)}</p>}
      {ask.total !== null && (
        <p className="en-value-row">
          <span className="en-value" data-testid="answer-value">
            {formatValue(ask.total, ask.total_unit)}
          </span>
          {ask.total_sure && (
            <span className="en-sure v-pill v-pill--ok" title={SURE_TIP}>
              Sure<span className="en-sr">. {SURE_TIP}</span>
            </span>
          )}
        </p>
      )}
      {ask.total_note && <p className="en-small">{ask.total_note}</p>}
      <ul className="en-parts">
        {answering.map((p) => (
          <li key={p.drawing_id}>
            <span>
              <span className="en-part-name en-mono">{p.name}</span>:{' '}
              {typeof p.answer.answer === 'number'
                ? formatValue(p.answer.answer, p.answer.unit)
                : (p.answer.answer ?? '')}
            </span>{' '}
            <a
              href={routeHref({
                name: 'workspace',
                projectId,
                drawingId: p.drawing_id,
                role: 'engineer',
                query: new URLSearchParams(),
              })}
            >
              Show it on {p.name}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The project-wide chat at #/p/<pid>/chat (docs/specs/frontend/chat.md): empty until asked, no drawing shown. */
export function ProjectChat({ projectId }: { projectId: string }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const nextId = useRef(1);
  const pending = useRef(false);
  const thread = useRef<HTMLElement>(null);
  // Starter chips from the drawings' own suggestions; not blocking, failures leave fewer (or none).
  const [chips, setChips] = useState<Suggestion[]>([]);

  useEffect(() => {
    const abort = new AbortController();
    getProject(projectId, { signal: abort.signal }).then(
      (project) => {
        setLoad({ state: 'ready', project });
        void Promise.allSettled(
          askable(project.drawings).map((d) =>
            getDrawing(d.drawing_id, { project: projectId, signal: abort.signal }),
          ),
        ).then((rs) => {
          if (abort.signal.aborted) return;
          setChips(starters(rs.map((r) => (r.status === 'fulfilled' ? r.value.suggestions : []))));
        });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId]);

  const last = turns.at(-1);
  const lastKey = last ? `${String(last.id)}:${last.status}` : '';
  useEffect(() => {
    if (lastKey) thread.current?.lastElementChild?.scrollIntoView({ block: 'start' });
  }, [lastKey]);

  if (load.state === 'loading') return <Loading label="Loading the project…" />;
  if (load.state === 'error') {
    return (
      <div className="en-page">
        <ErrorView error={load.error} />
        <a href={`#/p/${projectId}`}>Back to the project</a>
      </div>
    );
  }
  const { project } = load;
  const n = askable(project.drawings).length;

  function send(id: number, question: string) {
    pending.current = true;
    const settle = (t: ChatTurn) => {
      pending.current = false;
      setTurns((ts) => ts.map((x) => (x.id === id ? t : x)));
    };
    askProject(projectId, question).then(
      (ask) => {
        settle({ id, question, status: 'done', ask });
      },
      (error: unknown) => {
        settle({ id, question, status: 'error', error });
      },
    );
  }
  function ask(question: string) {
    if (pending.current) return;
    const id = nextId.current++;
    setTurns((ts) => [...ts, { id, question, status: 'pending' }]);
    send(id, question);
  }
  function retry(turn: Turn) {
    if (pending.current) return;
    setTurns((ts) =>
      ts.map((t) => (t.id === turn.id ? { id: t.id, question: t.question, status: 'pending' } : t)),
    );
    send(turn.id, turn.question);
  }

  const busy = turns.some((t) => t.status === 'pending');
  const card = (turn: ChatTurn) => {
    if (turn.status === 'done' && turn.ask.parts.some((p) => p.answer.refusal === null)) {
      return (
        <article key={turn.id} className="en-turn" aria-label={turn.ask.question}>
          <p className="en-bubble">{turn.ask.question}</p>
          <PartsCard ask={turn.ask} projectId={projectId} />
        </article>
      );
    }
    // pending, error, or refused by every drawing: the engineer's turn (the first refusal speaks for all)
    const refused = turn.status === 'done' ? turn.ask.parts[0] : undefined;
    if (turn.status === 'done' && !refused) return null; // no parts only for a project without drawings, never asked
    const shown: Turn =
      turn.status === 'done'
        ? {
            id: turn.id,
            question: turn.question,
            status: 'done',
            answer: (refused as NonNullable<typeof refused>).answer,
          }
        : turn;
    return (
      <AnswerCard
        key={turn.id}
        turn={shown}
        projectId={projectId}
        file={`${String(n)} drawings`}
        credit={null}
        place={null}
        busy={busy}
        onAsk={ask}
        onRetry={retry}
        refusalFrom="these drawings"
      />
    );
  };

  const box = (
    <AskBox file="the project's drawings" busy={busy || n === 0} asked={turns.length} onAsk={ask} />
  );
  // Empty (Tudor 12:45): the heading, the bar in the upper middle and the starter chips under it.
  if (turns.length === 0) {
    return (
      <div className="en-page en-chat en-chat--empty">
        <h1 className="en-chat-title">{project.name}</h1>
        {box}
        {n === 0 ? (
          <p className="en-empty">No drawing in this project can be asked yet.</p>
        ) : (
          chips.length > 0 && <Suggestions items={chips} busy={busy} onAsk={ask} />
        )}
      </div>
    );
  }
  return (
    <div className="en-page en-chat">
      <h1 className="en-chat-title">{project.name}</h1>
      <section className="en-thread" aria-label="Chat" ref={thread}>
        {turns.map(card)}
      </section>
      {box}
    </div>
  );
}
