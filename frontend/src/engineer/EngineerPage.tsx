import { useEffect, useRef, useState } from 'react';
import { askQuestion, getDrawing, type DrawingView } from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { PageViewer } from '../viewer/PageViewer';
import { AnswerCard, type Turn } from './AnswerCard';
import { AskBox } from './AskBox';
import { DrawingHeader } from './DrawingHeader';
import './engineer.css';

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; drawing: DrawingView };

/** The engineer workspace (docs/specs/frontend/engineer.md). The shell mounts it keyed by route path, so a
 * new drawing starts an empty thread. `query` is not used in v1. */
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
  const thread = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const abort = new AbortController();
    getDrawing(drawingId, { project: projectId, signal: abort.signal }).then(
      (drawing) => {
        setLoad({ state: 'ready', drawing });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [drawingId, projectId]);

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

  function send(id: number, question: string) {
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
  return (
    <div className="en-page">
      <DrawingHeader
        drawing={drawing}
        busy={busy}
        folded={turns.some((t) => t.status === 'done')}
        onAsk={ask}
      />
      {turns.length === 0 && (
        <>
          {drawing.pages.length > 0 && (
            <PageViewer
              file={drawing.file}
              pages={drawing.pages}
              marks={[]}
              credit={drawing.credit}
            />
          )}
          <p className="en-empty">Ask a question about this drawing.</p>
        </>
      )}
      <div className="en-thread" ref={thread}>
        {turns.map((turn) => (
          <AnswerCard
            key={turn.id}
            turn={turn}
            projectId={projectId}
            file={drawing.file}
            credit={drawing.credit}
            busy={busy}
            onAsk={ask}
            onRetry={retry}
          />
        ))}
      </div>
      <AskBox busy={busy} asked={turns.length} onAsk={ask} />
    </div>
  );
}
