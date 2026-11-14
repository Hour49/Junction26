import { useCallback, useEffect, useRef, useState } from 'react';
import {
  askQuestion,
  getDrawing,
  getProject,
  type AnswerView,
  type DrawingView,
  type ProjectView,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { AnswerCard, type Turn } from './AnswerCard';
import { AskBox } from './AskBox';
import { howRead, SuggestionRow } from './DrawingHeader';
import { DrawingNav, Plan, placeOf } from './Plan';
import './engineer.css';

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; drawing: DrawingView };

/** engineer.md "Opening at a question or a place": `?page=<n>&box=<x0,y0,x1,y1>` as the viewer's focus. A bad
 * page drops the place; a bad box keeps the page (null box: the viewer only switches the page). */
export function placeIn(
  query?: URLSearchParams,
): { page: number; box: number[] | null } | undefined {
  const page = Number(query?.get('page') || NaN);
  if (!Number.isInteger(page) || page < 1) return undefined;
  const box = (query?.get('box') ?? '').split(',').map((v) => (v.trim() ? Number(v) : NaN));
  const [x0 = 1, y0 = 1, x1 = 0, y1 = 0] = box;
  const ok = box.length === 4 && box.every((v) => v >= 0 && v <= 1) && x0 <= x1 && y0 <= y1;
  return { page, box: ok ? box : null };
}

/** The engineer workspace (docs/specs/frontend/engineer.md). The shell mounts it keyed by route path, so a
 * new drawing starts an empty thread. `query`: `ask` (asked on open) and `page`/`box` (the opening place). */
export function EngineerPage(props: {
  projectId: string;
  drawingId: string;
  query?: URLSearchParams;
}) {
  const { projectId, drawingId } = props;
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [turns, setTurns] = useState<Turn[]>([]);
  const nextId = useRef(1);
  const pending = useRef(false);
  const thread = useRef<HTMLElement>(null);
  // Not blocking: until it arrives, or if it fails, no position, arrows or original picture.
  const [project, setProject] = useState<ProjectView | null>(null);
  const openAsk = props.query?.get('ask')?.trim() ?? '';

  const send = useCallback(
    (id: number, question: string) => {
      pending.current = true;
      askQuestion({ drawing_id: drawingId, question, project_id: projectId }).then(
        (answer) => {
          pending.current = false;
          setTurns((ts) =>
            ts.map((t) => (t.id === id ? { id, question, status: 'done', answer } : t)),
          );
        },
        (error: unknown) => {
          pending.current = false;
          setTurns((ts) =>
            ts.map((t) => (t.id === id ? { id, question, status: 'error', error } : t)),
          );
        },
      );
    },
    [drawingId, projectId],
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
    getDrawing(drawingId, { project: projectId, signal: abort.signal }).then(
      (drawing) => {
        if (abort.signal.aborted) return; // StrictMode's first run: only the live load asks
        setLoad({ state: 'ready', drawing });
        if (openAsk) ask(openAsk);
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    getProject(projectId, { signal: abort.signal }).then(setProject, () => undefined);
    return () => {
      abort.abort();
    };
  }, [drawingId, projectId, openAsk, ask]);

  // Again when the answer arrives: the card is taller than the pending line. CSS scroll-margin keeps it
  // clear of the sticky header and ask box.
  const last = turns.at(-1);
  const lastKey = last ? `${String(last.id)}:${last.status}` : '';
  useEffect(() => {
    if (lastKey) thread.current?.lastElementChild?.scrollIntoView({ block: 'start' });
  }, [lastKey]);

  if (load.state === 'loading') return <Loading label="Loading the drawing…" />;
  if (load.state === 'error') {
    return (
      <div className="en-page">
        <ErrorView error={load.error} />
        <a href={`#/p/${projectId}`}>Back to the project</a>
      </div>
    );
  }
  const { drawing } = load;

  function retry(turn: Turn) {
    if (pending.current) return;
    setTurns((ts) =>
      ts.map((t) => (t.id === turn.id ? { id: t.id, question: t.question, status: 'pending' } : t)),
    );
    send(turn.id, turn.question);
  }

  function change(turn: Turn, answer: AnswerView) {
    setTurns((ts) =>
      ts.map((t) =>
        t.id === turn.id ? { id: t.id, question: t.question, status: 'done', answer } : t,
      ),
    );
  }

  const busy = turns.some((t) => t.status === 'pending');
  const place = project && placeOf(project, drawing, projectId);
  return (
    <div className="en-page">
      <h1 className="en-sr">{drawing.file}</h1>
      {turns.length === 0 && (
        <>
          {drawing.pages.length > 0 ? (
            <div className="v-card en-card en-card--empty">
              <figure className="en-left" aria-label="Drawing">
                <Plan
                  place={place}
                  viewer={{
                    file: drawing.file,
                    pages: drawing.pages,
                    marks: [],
                    // the asked question replaces this card at once, so its place is not shown (EN-78)
                    focus: openAsk ? undefined : placeIn(props.query),
                    credit: drawing.credit,
                  }}
                />
              </figure>
            </div>
          ) : (
            <>
              <DrawingNav place={place} />
              <p className="en-small">Building model: no sheet to draw on.</p>
            </>
          )}
          <p className="en-read">{howRead(drawing)}</p>
        </>
      )}
      <section className="en-thread" aria-label="Chat" ref={thread}>
        {turns.map((turn) => (
          <AnswerCard
            key={turn.id}
            turn={turn}
            projectId={projectId}
            file={drawing.file}
            credit={drawing.credit}
            place={place}
            busy={busy}
            onAsk={ask}
            onRetry={retry}
            onChanged={change}
          />
        ))}
      </section>
      {/* After a refusal its card already offers the questions: show them once (orch 12:20, EN-60). */}
      {!(last?.status === 'done' && last.answer.refusal) && (
        <SuggestionRow drawing={drawing} busy={busy} onAsk={ask} />
      )}
      {turns.length === 0 && <p className="en-empty">Ask a question about this drawing.</p>}
      <AskBox file={drawing.file} busy={busy} asked={turns.length} onAsk={ask} />
    </div>
  );
}
