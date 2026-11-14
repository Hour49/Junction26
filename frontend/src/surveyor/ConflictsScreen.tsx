import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getDrawing,
  getProject,
  getProjectReview,
  postReview,
  type ProjectReview,
  type ProjectView,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { routeHref } from '../shell/route';
import { ConflictCard, type DrawingLoad } from './ConflictCard';
import { conflictCount, keyOf, progressText, subLine, workspaceDrawing } from './conflicts';
import './conflicts.css';

type Load = { project: ProjectView; review: ProjectReview } | { error: unknown } | null;

/** Screen 3, "Settle the conflicts" (docs/specs/frontend/conflicts.md), at #/p/<pid>/conflicts. */
export function ConflictsScreen({ projectId }: { projectId: string }) {
  const [load, setLoad] = useState<Load>(null);
  const [attempt, setAttempt] = useState(0);
  const [drawings, setDrawings] = useState<Record<string, DrawingLoad>>({});
  const asked = useRef(new Set<string>());

  useEffect(() => {
    const abort = new AbortController();
    const opts = { signal: abort.signal };
    Promise.all([getProject(projectId, opts), getProjectReview(projectId, opts)]).then(
      ([project, review]) => {
        setLoad({ project, review });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, attempt]);

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

  const again = () => {
    setLoad(null);
    setAttempt((n) => n + 1);
  };

  if (load === null)
    return (
      <div className="v-page v-page--narrow cf">
        <Loading label="Loading the conflicts…" />
      </div>
    );
  if ('error' in load)
    return (
      <div className="v-page v-page--narrow cf">
        <ErrorView error={load.error} onRetry={again} />
      </div>
    );

  const { project, review } = load;
  const { conflicts } = review;
  const k = conflicts.length;
  const ready = review.drawings.length;
  const locked = conflicts.some((c) => c.needs_person);
  const target = workspaceDrawing(review.drawings);

  async function edit(
    drawingId: string,
    quantity: string,
    e: { action: 'settle'; value: number } | { action: 'reset' },
  ) {
    await postReview(drawingId, { quantity, ...e }, { project: projectId });
    // the server's project review is the one source of the cards (it lists a storey twin once)
    const fresh = await getProjectReview(projectId);
    setLoad((l) => (l && 'project' in l ? { ...l, review: fresh } : l));
  }

  return (
    <div className="v-page v-page--narrow cf">
      <div className="cf-head">
        <div>
          <p className="cf-head-kicker">
            {project.name} · {ready} drawing{ready === 1 ? '' : 's'} ready
          </p>
          <h1>{conflictCount(k)}</h1>
          <p className="cf-sub">{subLine(conflicts)}</p>
        </div>
        {target !== null &&
          (locked ? (
            <div className="cf-open">
              <button type="button" className="cf-open-btn" disabled aria-describedby="cf-locked">
                Open the workspace
              </button>
              <p id="cf-locked" className="cf-locked">
                Settle the conflicts that need you first.
              </p>
            </div>
          ) : (
            <a
              className="cf-open-btn"
              href={routeHref({
                name: 'workspace',
                projectId,
                drawingId: target,
                role: 'engineer',
                query: new URLSearchParams(),
              })}
            >
              Open the workspace
            </a>
          ))}
      </div>

      {(project.state === 'queued' || project.state === 'running') && (
        <p className="cf-state">
          Still reading the drawings: these are the conflicts so far.{' '}
          <button type="button" className="cf-btn" onClick={again}>
            Check again
          </button>
        </p>
      )}
      {project.state === 'failed' && (
        <p className="cf-state">Reading stopped: {String(project.error)}.</p>
      )}

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
          <span>{progressText(conflicts)}</span>
        </div>
      )}

      {conflicts.map((c, i) => (
        <ConflictCard
          // remount when the server's state changes, so the card's mode starts over
          key={`${keyOf(c)} ${String(c.needs_person)} ${String(c.settled?.value)}`}
          entry={c}
          index={i}
          total={k}
          projectId={projectId}
          drawing={drawings[c.drawing_id]}
          onNeedDrawing={(retry) => {
            needDrawing(c.drawing_id, retry);
          }}
          onEdit={(e) => edit(c.drawing_id, c.quantity, e)}
        />
      ))}
    </div>
  );
}
