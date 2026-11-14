import { useCallback, useEffect, useRef, useState } from 'react';
import {
  drawingLabel,
  errorText,
  getDrawing,
  getProject,
  getProjectReview,
  postReview,
  type ProjectReview,
} from '../api';
import { ConflictCard, type DrawingLoad } from './ConflictCard';
import { conflictCount, keyOf, ordered, progressText, subLine, type Answer } from './conflicts';
import './conflicts.css';

type Load = { review: ProjectReview } | { error: unknown } | null;
export interface ConflictCounts {
  total: number;
  needsPerson: number;
}

/** The project's conflicts, embedded under the finished ingest (conflicts.md "Demo parity", CF-35..44). */
export function ConflictsList({
  projectId,
  query,
  onCounts,
}: {
  projectId: string;
  query?: URLSearchParams; // the host route's query: `d` + `q` from an issue link focus a card
  onCounts?: (counts: ConflictCounts) => void; // after every load; the host locks its chat button on it
}) {
  const focusKey =
    query?.get('d') && query.get('q')
      ? `${String(query.get('d'))} ${String(query.get('q'))}`
      : null;
  const [load, setLoad] = useState<Load>(null);
  const [attempt, setAttempt] = useState(0);
  const [drawings, setDrawings] = useState<Record<string, DrawingLoad>>({});
  const [names, setNames] = useState<Record<string, string>>({});
  const asked = useRef(new Set<string>());
  const report = useRef(onCounts);
  useEffect(() => {
    report.current = onCounts; // the latest host callback, without reloading when it changes
  });

  const show = useCallback((review: ProjectReview) => {
    setLoad({ review });
    const { conflicts } = review;
    report.current?.({
      total: conflicts.length,
      needsPerson: conflicts.filter((c) => c.needs_person).length,
    });
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    getProjectReview(projectId, { signal: abort.signal }).then(show, (error: unknown) => {
      if (!abort.signal.aborted) setLoad({ error });
    });
    return () => {
      abort.abort();
    };
  }, [projectId, attempt, show]);

  // the drawings' plain names (#224) live on the project; without them a card shows the file name
  useEffect(() => {
    const abort = new AbortController();
    getProject(projectId, { signal: abort.signal }).then(
      (p) => {
        setNames(Object.fromEntries(p.drawings.map((d) => [d.drawing_id, drawingLabel(d)])));
      },
      () => undefined, // names are a nicety: the list works without them
    );
    return () => {
      abort.abort();
    };
  }, [projectId]);

  const needDrawing = useCallback(
    (drawingId: string, retry = false) => {
      if (asked.current.has(drawingId) && !retry) return;
      asked.current.add(drawingId);
      setDrawings((d) => ({ ...d, [drawingId]: undefined }));
      getDrawing(drawingId, { project: projectId }).then(
        (view) => {
          setDrawings((d) => ({ ...d, [drawingId]: view }));
        },
        (error: unknown) => {
          setDrawings((d) => ({ ...d, [drawingId]: { error } }));
        },
      );
    },
    [projectId],
  );

  async function edit(
    drawingId: string,
    quantity: string,
    e: ({ action: 'settle' } & Answer) | { action: 'unsettle' },
  ) {
    await postReview(drawingId, { quantity, ...e }, { project: projectId });
    // the server's project review is the one source of the cards (it lists a storey twin once)
    show(await getProjectReview(projectId));
  }

  let body;
  if (load === null)
    body = (
      <p role="status" className="cf-sub">
        Loading the conflicts…
      </p>
    );
  else if ('error' in load)
    body = (
      <div role="alert" className="cf-error">
        <p>{errorText(load.error).detail}</p>
        <button
          type="button"
          className="cf-btn"
          onClick={() => {
            setLoad(null);
            setAttempt((n) => n + 1);
          }}
        >
          Retry
        </button>
      </div>
    );
  else {
    const conflicts = ordered(load.review.conflicts);
    const k = conflicts.length;
    body = (
      <>
        <div className="cf-head">
          <h2>{conflictCount(k)}</h2>
          <p className="cf-sub">{subLine(conflicts)}</p>
        </div>
        {k > 0 && (
          <div className="cf-progress">
            <div
              className={`cf-segs${k > 12 ? ' cf-joined' : ''}`}
              role="progressbar"
              aria-label="Conflicts settled"
              aria-valuemin={0}
              aria-valuemax={k}
              aria-valuenow={conflicts.filter((c) => !c.needs_person).length}
            >
              {conflicts.map((c) => (
                <span key={keyOf(c)} className={`cf-seg${c.needs_person ? '' : ' cf-on'}`} />
              ))}
            </div>
            <span role="status">{progressText(conflicts)}</span>
          </div>
        )}
        {conflicts.map((c, i) => (
          <ConflictCard
            // stable: a reload keeps the card (its open Why, its figure); the card resets its own mode
            key={keyOf(c)}
            entry={c}
            index={i}
            total={k}
            drawingName={names[c.drawing_id] ?? drawingLabel(c)}
            focused={keyOf(c) === focusKey}
            drawing={drawings[c.drawing_id]}
            onNeedDrawing={(retry) => {
              needDrawing(c.drawing_id, retry);
            }}
            onEdit={(e) => edit(c.drawing_id, c.quantity, e)}
          />
        ))}
      </>
    );
  }
  return (
    <section id="conflicts" className="cf" aria-label="Conflicts" tabIndex={-1}>
      {body}
    </section>
  );
}

/** The old #/p/<pid>/conflicts route until fe-shared sends it to Ingest: just the list. */
export function ConflictsScreen({
  projectId,
  query,
}: {
  projectId: string;
  query?: URLSearchParams;
}) {
  return (
    <div className="v-page v-page--narrow">
      <ConflictsList projectId={projectId} query={query} />
    </div>
  );
}
