import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import {
  chatTurn,
  drawingLabel,
  errorText,
  getDrawing,
  getProject,
  type DrawingView,
  type ProjectView,
  type Suggestion,
} from '../api';
import { AskBox } from '../engineer/AskBox';
import { Suggestions } from '../engineer/DrawingHeader';
import { usePhotoAdd } from '../engineer/photoAdd';
import { askable, followUps, starters } from '../engineer/projectAsk';
import { ErrorView } from '../shell/ErrorView';
import { useInfo } from '../shell/info';
import { Loading } from '../shell/Loading';
import {
  evidenceView,
  unionBox,
  viewOf,
  type Box,
  type ChatTurn,
  type Evidence,
  type Selection,
  type View,
} from './agent';
import { LiveSteps } from './LiveSteps';
import { canShow3d, paneHighlight } from '../model3d/model3d';
import { PlanPane, PlanSheet } from './PlanPane';
import { PlanPointer } from './PlanPointer';
import { LIVE_START, liveStep, streamTurn, type Live } from './stream';
import { TurnCard } from './TurnCard';
import { WhatIRead } from './WhatIRead';
import '../engineer/engineer.css';

type Sent = { id: number; message: string; chips: string[] };
type Row =
  | (Sent & { status: 'pending'; live?: Live })
  | (Sent & { status: 'error'; error: unknown; selection: Selection[] })
  | (Sent & { status: 'done'; turn: ChatTurn });

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; project: ProjectView };

type Pointed = { sel: Selection; chip: string };
type Done = Extract<Row, { status: 'done' }>;
type Kept = { chatId?: string; rows: Done[] };

// answers-5: "Show it" leaves the chat route; the thread comes back from here (this tab only).
const keyOf = (projectId: string) => `agent-chat:${projectId}`;
function kept(projectId: string): Kept {
  try {
    const raw = sessionStorage.getItem(keyOf(projectId));
    if (raw) return JSON.parse(raw) as Kept;
  } catch {
    // no storage (private mode) or a bad value: start empty
  }
  return { rows: [] };
}

/** What the plan beside the chat shows: a drawing, the turn's view on it (null: the page alone), a source to focus. */
type Shown = { drawingId: string; view: View | null; focus: Box | null };

const WIDE = '(min-width: 1200px)'; // room for the 820 px chat column and the plan beside it

/** True while the window is wide enough for the plan beside the chat; false where there is no matchMedia. */
function useWide(): boolean {
  const query = () => typeof window.matchMedia === 'function' && window.matchMedia(WIDE).matches;
  const [wide, setWide] = useState(query);
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia(WIDE);
    const on = () => {
      setWide(mq.matches);
    };
    mq.addEventListener('change', on);
    return () => {
      mq.removeEventListener('change', on);
    };
  }, []);
  return wide;
}

/** The newest kept turn's view, so a thread restored after "Show it" opens the plan where it was. */
function lastShown(rows: Done[]): Shown | null {
  const view = rows
    .map((r) => viewOf(r.turn))
    .filter((v): v is View => v !== null)
    .at(-1);
  return view ? { drawingId: view.drawing_id, view, focus: null } : null;
}

/** The agent chat thread (AC-30): one turn pending at a time, `chat_id` kept from the first turn, selections from
 * "Point at the plan" go with the next message and are cleared after it (AC-33). As the project chat: `?ask=` is
 * sent on open, starter chips when empty, follow-up chips after a turn (chat.md). */
export function AgentChat({ projectId, query }: { projectId: string; query?: URLSearchParams }) {
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [start] = useState(() => kept(projectId));
  const [rows, setRows] = useState<Row[]>(start.rows);
  // The drawings' own suggestions, for the starter and follow-up chips; failures leave fewer (or none).
  const [lists, setLists] = useState<Suggestion[][]>([]);
  // The askable drawings as read (pages for the plan beside the chat), by id; null until they have come.
  const [drawn, setDrawn] = useState<Record<string, DrawingView> | null>(null);
  const wide = useWide();
  const [shown, setShown] = useState<Shown | null>(() => lastShown(start.rows));
  // Under 1200 px the plan opens as a full-screen sheet over the chat (chat-ux #9).
  const [sheet, setSheet] = useState(false);
  // Widening closes the sheet (the pane shows instead), so narrowing again does not bring it back unasked.
  const [wasWide, setWasWide] = useState(wide);
  if (wide !== wasWide) {
    setWasWide(wide);
    if (wide) setSheet(false);
  }
  const openAsk = query?.get('ask')?.trim() ?? '';
  const pack = query?.get('pack') ?? null;
  // Read at send time: a new country must not re-run the open effect (it would ask ?ask= again).
  const packNow = useRef(pack);
  useEffect(() => {
    packNow.current = pack;
  }, [pack]);
  // chat-ux #2: the stream route only where /api/info says the server has it (contract C); read at send time.
  const { info } = useInfo();
  const streams = useRef(false);
  useEffect(() => {
    streams.current = info?.chat?.stream === true;
  }, [info]);
  const [pointed, setPointed] = useState<Pointed[]>([]);
  const [pointing, setPointing] = useState(false);
  const chatId = useRef<string | undefined>(start.chatId);
  const nextId = useRef(Math.max(0, ...start.rows.map((r) => r.id)) + 1);
  const nextSel = useRef(1);
  const pending = useRef(false);
  const thread = useRef<HTMLElement>(null);
  const photo = usePhotoAdd(projectId, (project) => {
    setLoad({ state: 'ready', project });
  });

  const send = useCallback(
    (row: Sent, selection: Selection[]) => {
      pending.current = true;
      const settle = (r: Row) => {
        pending.current = false;
        setRows((rs) => rs.map((x) => (x.id === r.id ? r : x)));
      };
      const body = {
        ...(chatId.current ? { chat_id: chatId.current } : {}),
        message: row.message,
        ...(selection.length ? { selection } : {}),
        ...(packNow.current ? { pack: packNow.current } : {}), // LC-11: the country picker's rule pack, as the checks screen sends it
      };
      // chat-ux #2: the stream route with its live steps where the server has it, else the sync route (contract C)
      const turn = streams.current
        ? streamTurn(projectId, body, (e) => {
            // A new chat's id is known from the first event: a failure later still continues this chat.
            if (e.type === 'turn') chatId.current = e.chat_id;
            // show_on_plan's view moves the plan while the turn runs; the answer's view has the last word.
            if (e.type === 'view')
              setShown({ drawingId: e.view.drawing_id, view: e.view, focus: null });
            setRows((rs) =>
              rs.map((x) =>
                x.id === row.id && x.status === 'pending'
                  ? { ...x, live: liveStep(x.live ?? LIVE_START, e) }
                  : x,
              ),
            );
          })
        : chatTurn(projectId, body);
      turn.then(
        (turn) => {
          chatId.current = turn.chat_id;
          settle({ ...row, status: 'done', turn });
          // Every turn with a place moves the plan (contract A); one without leaves it where it is.
          const view = viewOf(turn);
          if (view) setShown({ drawingId: view.drawing_id, view, focus: null });
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
        if (abort.signal.aborted) return; // StrictMode's first run: only the live load asks
        setLoad({ state: 'ready', project });
        // Back from "Show it" keeps ?ask=: a kept thread that asked it already is not asked again.
        const asked = start.rows.some((r) => r.message === openAsk);
        if (openAsk && !asked && askable(project.drawings).length > 0) {
          const row: Sent = { id: nextId.current++, message: openAsk, chips: [] };
          setRows([{ ...row, status: 'pending' }]);
          send(row, []);
        }
        const ids = askable(project.drawings).map((d) => d.drawing_id);
        void Promise.allSettled(
          askable(project.drawings).map((d) =>
            getDrawing(d.drawing_id, { project: projectId, signal: abort.signal }),
          ),
        ).then((rs) => {
          if (abort.signal.aborted) return;
          setLists(rs.map((r) => (r.status === 'fulfilled' ? r.value.suggestions : [])));
          const read: Record<string, DrawingView> = {};
          rs.forEach((r, i) => {
            const id = ids[i];
            if (r.status === 'fulfilled' && id) read[id] = r.value;
          });
          setDrawn(read);
        });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start is the mount's kept thread
  }, [projectId, openAsk, send]);

  useEffect(() => {
    const done = rows.filter((r): r is Done => r.status === 'done');
    if (done.length === 0) return;
    try {
      sessionStorage.setItem(
        keyOf(projectId),
        JSON.stringify({ chatId: chatId.current, rows: done } satisfies Kept),
      );
    } catch {
      // full or blocked storage: the thread just isn't kept
    }
  }, [rows, projectId]);

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
  const chips = starters(lists);
  // Hidden while the newest turn offers its own chips or does not know (CH-36's rule for a refusal).
  const newest = rows.at(-1);
  const ownChoice =
    newest?.status === 'done' &&
    (newest.turn.kind === 'dont_know' || (newest.turn.options ?? []).length > 0);
  // #369: the answer's own next questions (the server's), at most 3, before the drawings' generic ones.
  const own =
    newest?.status === 'done' && !newest.turn.options?.length
      ? ((newest.turn.next as ChatTurn['next'] | undefined) ?? []).slice(0, 3)
      : [];
  const next = ownChoice
    ? []
    : followUps(
        lists,
        rows.map((r) => r.message),
      );

  // [n] and "Show it" focus that source: in the turn's view when it is one of its marks, else on its own page.
  const showSource = (turn: ChatTurn) => (e: Evidence) => {
    const v = viewOf(turn);
    const inView =
      v?.drawing_id === e.drawing_id && v.page === e.page && v.marks.some((m) => m.n === e.n);
    setShown(
      inView
        ? { drawingId: v.drawing_id, view: v, focus: unionBox([e.box]) }
        : { drawingId: e.drawing_id, view: evidenceView(e), focus: null },
    );
    if (!wide) setSheet(true);
  };
  const paneId = shown?.drawingId ?? plans[0]?.drawing_id;
  // model-3d.md "More places": the shown drawing's 3D model, its newest answer's elements highlighted
  const modelFile = project.files.find((f) => f.drawing_id === paneId && canShow3d(f.model_3d));
  const model =
    modelFile && paneId
      ? {
          fileId: modelFile.id,
          highlight: paneHighlight(
            rows.flatMap((r) => (r.status === 'done' ? [r.turn] : [])),
            paneId,
          ),
        }
      : null;
  const plan = paneId && (
    <PlanPane
      projectId={projectId}
      pack={pack}
      drawings={askable(project.drawings).map((d) => ({
        drawing_id: d.drawing_id,
        label: drawingLabel(d),
      }))}
      drawingId={paneId}
      drawing={drawn ? (drawn[paneId] ?? null) : undefined}
      view={shown?.view ?? null}
      focus={shown?.focus ?? null}
      model={model}
      onDrawing={(id) => {
        setShown((s) => ({ drawingId: id, view: s?.view ?? null, focus: null }));
      }}
      onClose={
        wide
          ? undefined
          : () => {
              setSheet(false);
            }
      }
    />
  );
  const pane = wide && plan;
  // The plan beside the chat (chat-ux #1) where the window has room for it.
  // Narrower: the same plan as a sheet over the chat, while it is open.
  const split = (chat: ReactNode) =>
    pane ? (
      <div className="ag-split">
        {chat}
        {pane}
      </div>
    ) : (
      <>
        {chat}
        {sheet && plan && (
          <PlanSheet
            onClose={() => {
              setSheet(false);
            }}
          >
            {plan}
          </PlanSheet>
        )}
      </>
    );

  const row = (r: Row) => (
    <article key={r.id} className="en-turn" aria-label={r.message}>
      <p className="en-bubble">
        {r.chips.length > 0 && <span className="ag-bubble-sel">{r.chips.join(' · ')}</span>}
        {r.message}
      </p>
      {r.status === 'pending' && <LiveSteps live={r.live} />}
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
        <TurnCard
          turn={r.turn}
          projectId={projectId}
          project={project}
          pack={pack}
          busy={busy}
          onAsk={ask}
          onShow={plan ? showSource(r.turn) : undefined}
          onDecided={(edit) => {
            // Kept with the thread, so a restored card shows the decision, not Accept again.
            setRows((rs) =>
              rs.map((x) =>
                x.id === r.id && x.status === 'done' ? { ...x, turn: { ...x.turn, edit } } : x,
              ),
            );
          }}
        />
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
        {!wide && plan && (
          <button
            type="button"
            className="en-chip v-press"
            aria-expanded={sheet}
            onClick={() => {
              setSheet(true);
            }}
          >
            Show the plan
          </button>
        )}
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
        onAttach={photo.attach}
        short="the drawings"
        attaching={photo.attaching}
      />
    </div>
  );

  if (rows.length === 0) {
    return split(
      <div className="en-page en-chat en-chat--empty">
        <h1 className="en-chat-title">{project.name}</h1>
        <WhatIRead project={project} />
        {photo.line}
        {pointer}
        {bar}
        {plans.length === 0 ? (
          <p className="en-empty">No drawing in this project can be asked yet.</p>
        ) : (
          chips.length > 0 && <Suggestions items={chips} busy={busy} onAsk={ask} />
        )}
      </div>,
    );
  }
  return split(
    <div className="en-page en-chat">
      <h1 className="en-sr">{project.name}</h1>
      {photo.line}
      <section className="en-thread" aria-label="Chat" ref={thread}>
        {rows.map(row)}
      </section>
      {own.length > 0 ? (
        <div className="en-suggest" role="group" aria-label="Follow-up questions">
          {own.map((o) => (
            <button
              key={o.message}
              type="button"
              className="en-chip v-press"
              title={o.message}
              disabled={busy}
              onClick={() => {
                ask(o.message);
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      ) : (
        next.length > 0 && (
          <Suggestions items={next} busy={busy} onAsk={ask} label="Follow-up questions" />
        )
      )}
      {pointer}
      {bar}
    </div>,
  );
}
