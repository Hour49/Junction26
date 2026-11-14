import { useCallback, useEffect, useRef, useState } from 'react';
import {
  askProject,
  getDrawing,
  getProject,
  type ProjectAnswer,
  type ProjectView,
  type Suggestion,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { AnswerCard, type Turn } from './AnswerCard';
import { ChatAnswer } from './ChatAnswer';
import { AskBox } from './AskBox';
import { Suggestions } from './DrawingHeader';
import { askable, followUps, starters } from './projectAsk';
import './engineer.css';

type ChatTurn =
  | { id: number; question: string; status: 'pending' }
  | { id: number; question: string; status: 'error'; error: unknown }
  | { id: number; question: string; status: 'done'; ask: ProjectAnswer };

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; project: ProjectView };

/** The project-wide chat at #/p/<pid>/chat (docs/specs/frontend/chat.md): empty until asked, no drawing shown.
 * `query`: `ask` is asked on open (chat.md "Opening with a question"). */
export function ProjectChat({ projectId, query }: { projectId: string; query?: URLSearchParams }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const nextId = useRef(1);
  const pending = useRef(false);
  const thread = useRef<HTMLElement>(null);
  // The drawings' own suggestions, for the starter and follow-up chips; not blocking, failures leave fewer (or none).
  const [lists, setLists] = useState<Suggestion[][]>([]);
  const openAsk = query?.get('ask')?.trim() ?? '';

  const send = useCallback(
    (id: number, question: string) => {
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
    },
    [projectId],
  );
  const ask = useCallback(
    (question: string) => {
      if (pending.current) return;
      const id = nextId.current++;
      setTurns((ts) => [...ts, { id, question, status: 'pending' }]);
      send(id, question);
    },
    [send],
  );

  useEffect(() => {
    const abort = new AbortController();
    getProject(projectId, { signal: abort.signal }).then(
      (project) => {
        if (abort.signal.aborted) return; // StrictMode's first run: only the live load asks
        setLoad({ state: 'ready', project });
        if (openAsk && askable(project.drawings).length > 0) ask(openAsk);
        void Promise.allSettled(
          askable(project.drawings).map((d) =>
            getDrawing(d.drawing_id, { project: projectId, signal: abort.signal }),
          ),
        ).then((rs) => {
          if (abort.signal.aborted) return;
          setLists(rs.map((r) => (r.status === 'fulfilled' ? r.value.suggestions : [])));
        });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, openAsk, ask]);

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
          <ChatAnswer
            ask={turn.ask}
            project={project}
            projectId={projectId}
            pack={query?.get('pack') ?? null}
          />
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
        onChanged={() => undefined} // only refusal, pending and error turns come here: no DoubleCheck
      />
    );
  };

  const box = (
    <AskBox file="the project's drawings" busy={busy || n === 0} asked={turns.length} onAsk={ask} />
  );
  const chips = starters(lists);
  // CH-36: hidden while the newest turn is a refusal (its own chips are the choice then).
  const newest = turns.at(-1);
  const refusedLast =
    newest?.status === 'done' && newest.ask.parts.every((p) => p.answer.refusal !== null);
  const next = refusedLast
    ? []
    : followUps(
        lists,
        turns.map((t) => t.question),
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
      <h1 className="en-sr">{project.name}</h1>
      <section className="en-thread" aria-label="Chat" ref={thread}>
        {turns.map(card)}
      </section>
      {next.length > 0 && (
        <Suggestions items={next} busy={busy} onAsk={ask} label="Follow-up questions" />
      )}
      {box}
    </div>
  );
}
