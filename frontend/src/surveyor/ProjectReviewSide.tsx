import { useEffect, useState } from 'react';
import {
  ApiError,
  formatValue,
  getProjectReview,
  type ConflictEntry,
  type ProjectReview,
} from '../api';
import { routeHref } from '../shell/route';
import './surveyor.css';

interface Props {
  projectId: string;
  drawingId: string;
  /** Bump to fetch the review again (after an edit or a sign-off). */
  reload?: number;
}

type Load = { review: ProjectReview } | { error: unknown } | null;

const surveyorHref = (projectId: string, drawingId: string, key?: string) =>
  routeHref({
    name: 'workspace',
    projectId,
    drawingId,
    role: 'surveyor',
    query: new URLSearchParams(key === undefined ? {} : { q: key }),
  });

function conflictState(c: ConflictEntry): string {
  if (c.needs_person) return 'needs you';
  return c.settled ? 'settled' : 'decided by rule';
}

/** The surveyor's side panel: the project's drawings with what is left to review, and its conflicts. */
export function ProjectReviewSide({ projectId, drawingId, reload = 0 }: Props) {
  const [load, setLoad] = useState<Load>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const abort = new AbortController();
    void getProjectReview(projectId, { signal: abort.signal }).then(
      (review) => {
        setLoad({ review });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [projectId, attempt, reload]);

  if (load === null)
    return (
      <aside className="sv-side">
        <p role="status">Loading drawings…</p>
      </aside>
    );
  if ('error' in load) {
    const { error } = load;
    return (
      <aside className="sv-side">
        <div role="alert">
          <p>The project's drawings could not be loaded.</p>
          {error instanceof ApiError ? (
            <>
              <p>{error.detail}</p>
              <p>code: {error.code}</p>
            </>
          ) : (
            <p>{String(error)}</p>
          )}
          <button
            type="button"
            onClick={() => {
              setLoad(null);
              setAttempt((n) => n + 1);
            }}
          >
            Retry
          </button>
        </div>
      </aside>
    );
  }

  const { drawings, conflicts } = load.review;
  return (
    <aside className="sv-side">
      <h2 id="sv-drawings">Drawings ({drawings.length})</h2>
      <ul aria-labelledby="sv-drawings">
        {drawings.map((d) => {
          const isCurrent = d.drawing_id === drawingId;
          return (
            <li key={d.drawing_id} className={isCurrent ? 'sv-current' : undefined}>
              <a
                href={surveyorHref(projectId, d.drawing_id)}
                aria-current={isCurrent ? 'page' : undefined}
              >
                {d.file}
              </a>
              <small>
                {[
                  d.to_review > 0 ? `${String(d.to_review)} to review` : null,
                  d.quantities === 0
                    ? 'nothing counted'
                    : `${String(d.signed)} of ${String(d.quantities)} signed off`,
                  isCurrent ? 'current' : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </small>
            </li>
          );
        })}
      </ul>
      <h2 id="sv-conflicts">Conflicts ({conflicts.length})</h2>
      <ul aria-labelledby="sv-conflicts">
        {conflicts.map((c) => (
          <li key={`${c.drawing_id} ${c.quantity}`}>
            <a href={surveyorHref(projectId, c.drawing_id, c.quantity)}>{c.label}</a>
            <small>{c.file}</small>
            <small>
              {c.conflict.values.map((v) => formatValue(v.value, v.unit ?? null)).join(' vs ')} ·{' '}
              {conflictState(c)}
            </small>
          </li>
        ))}
      </ul>
    </aside>
  );
}
