import { useCallback, useEffect, useRef, useState } from 'react';
import {
  chatTurn,
  errorText,
  getDrawing,
  getProject,
  type ProjectView,
  type Suggestion,
} from '../api';
import { AskBox } from '../engineer/AskBox';
import { Suggestions } from '../engineer/DrawingHeader';
import { askable, starters } from '../engineer/projectAsk';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import type { ChatTurn, Selection } from './agent';
import { PlanPointer } from './PlanPointer';
import { TurnCard } from './TurnCard';
import '../engineer/engineer.css';

type Sent = { id: number; message: string; chips: string[] };
type Row =
  | (Sent & { status: 'pending' })
  | (Sent & { status: 'error'; error: unknown; selection: Selection[] })
  | (Sent & { status: 'done'; turn: ChatTurn });

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; project: ProjectView };

type Pointed = { sel: Selection; chip: string };

/** The agent chat thread (AC-30): one turn pending at a time, `chat_id` kept from the first turn, selections from
 * "Point at the plan" go with the next message and are cleared after it (AC-33). */
export function AgentChat({ projectId }: { projectId: string }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [rows, setRows] = useState<Row[]>([]);
  const [chips, setChips] = useState<Suggestion[]>([]);
  const [pointed, setPointed] = useState<Pointed[]>([]);
  const [pointing, setPointing] = useState(false);
  const chatId = useRef<string | undefined>(undefined);
  const nextId = useRef(1);
  const nextSel = useRef(1);
  const pending = useRef(false);
  const thread = useRef<HTMLElement>(null);

  const send = useCallback(
    (row: Sent, selection: Selection[]) => {
      pending.current = true;
      const settle = (r: Row) => {
        pending.current = false;
        setRows((rs) => rs.map((x) => (x.id === r.id ? r : x)));
      };
      chatTurn(projectId, {
        ...(chatId.current ? { chat_id: chatId.current } : {}),
        message: row.message,
        ...(selection.length ? { selection } : {}),
      }).then(
        (turn) => {
          chatId.current = turn.chat_id;
          settle({ ...row, status: 'done', turn });
        },
        (error: unknown) => {
          settle({ ...row, status: 'error', error, selection });
        },
      );
    },
    [projectId],
  );

  const ask = (message: string) => {
    if (pending.current) return;
    const row: Sent = { id: nextId.current++, message, chips: pointed.map((p) => p.chip) };
    setRows((rs) => [...rs, { ...row, status: 'pending' }]);
    send(
      row,
      pointed.map((p) => p.sel),
    );
    setPointed([]);
    setPointing(false);
  };

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

  const last = rows.at(-1);
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
  const plans = askable(project.drawings).map((d) => ({ drawing_id: d.drawing_id, name: d.name }));
  const busy = rows.some((r) => r.status === 'pending');

  const row = (r: Row) => (
    <article key={r.id} className="en-turn" aria-label={r.message}>
      <p className="en-bubble">
        {r.chips.length > 0 && <span className="ag-bubble-sel">{r.chips.join(' · ')}</span>}
        {r.message}
      </p>
      {r.status === 'pending' && (
        <p className="en-pending" role="status">
          Working on it…
        </p>
      )}
      {r.status === 'error' && (
        <div className="v-card en-error" role="alert">
          <p>The message could not be answered: {errorText(r.error).detail}</p>
          <p className="en-small">code: {errorText(r.error).code}</p>
          <button
            type="button"
            className="en-chip v-press"
            disabled={busy}
            onClick={() => {
              if (pending.current) return;
              setRows((rs) => rs.map((x) => (x.id === r.id ? { ...r, status: 'pending' } : x)));
              send(r, r.selection);
            }}
          >
            Try again
          </button>
        </div>
      )}
      {r.status === 'done' && (
        <TurnCard turn={r.turn} projectId={projectId} busy={busy} onAsk={ask} />
      )}
    </article>
  );

  const pointer = pointing && (
    <PlanPointer
      projectId={projectId}
      plans={plans}
      onAdd={(sel, chip) => {
        setPointed((ps) => [
          ...ps,
          { sel: { ...sel, id: `sel_${String(nextSel.current++)}` }, chip },
        ]);
      }}
      onClose={() => {
        setPointing(false);
      }}
    />
  );

  const bar = (
    <div className="ag-bar">
      <div className="ag-selrow">
        <button
          type="button"
          className="en-chip v-press"
          aria-expanded={pointing}
          disabled={plans.length === 0}
          onClick={() => {
            setPointing((p) => !p);
          }}
        >
          Point at the plan
        </button>
        {pointed.map((p) => (
          <span key={p.sel.id} className="ag-selchip">
            {p.chip}
            <button
              type="button"
              aria-label={`Remove ${p.chip}`}
              onClick={() => {
                setPointed((ps) => ps.filter((x) => x.sel.id !== p.sel.id));
              }}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <AskBox
        file="the project's drawings"
        busy={busy || plans.length === 0}
        asked={rows.length}
        onAsk={ask}
      />
    </div>
  );

  if (rows.length === 0) {
    return (
      <div className="en-page en-chat en-chat--empty">
        <h1 className="en-chat-title">{project.name}</h1>
        {pointer}
        {bar}
        {plans.length === 0 ? (
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
        {rows.map(row)}
      </section>
      {pointer}
      {bar}
    </div>
  );
}
