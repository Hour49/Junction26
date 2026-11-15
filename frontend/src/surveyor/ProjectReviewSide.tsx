import { useEffect, useId, useState } from 'react';
import {
  ApiError,
  drawingLabel,
  formatValue,
  getProjectReview,
  type ConflictEntry,
  type ProjectReview,
} from '../api';
import { routeHref } from '../shell/route';
import './surveyor.css';
import { Button } from '@/components/ui/button';
import { TOOL } from './ui';

interface Props {
  projectId: string;
  drawingId: string;
  /** Bump to fetch the review again (after an edit or a sign-off). */
  reload?: number;
  /** Drawing id → plain name (#224), from the workspace's one project GET; absent: the file name. */
  names?: Record<string, string>;
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
export function ProjectReviewSide({ projectId, drawingId, reload = 0, names = {} }: Props) {
  const nameOf = (d: { drawing_id: string; file: string }) =>
    names[d.drawing_id] ?? drawingLabel(d);
  const [load, setLoad] = useState<Load>(null);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState(false); // K3: on a phone the lists fold, so the drawing comes first
  const bodyId = useId();

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
            </>
          ) : (
            <p>{String(error)}</p>
          )}
          <Button
            variant="secondary"
            className={TOOL}
            onClick={() => {
              setLoad(null);
              setAttempt((n) => n + 1);
            }}
          >
            Retry
          </Button>
        </div>
      </aside>
    );
  }

  const { drawings, conflicts } = load.review;
  return (
    <aside className="sv-side" data-open={open}>
      {/* shown only at <= 640 px (surveyor.css); wider screens always show the lists */}
      <button
        type="button"
        className="sv-side-toggle"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => {
          setOpen((o) => !o);
        }}
      >
        Drawings ({drawings.length}) · Conflicts ({conflicts.length})
        <span className="sv-side-caret" aria-hidden="true">
          {open ? '▴' : '▾'}
        </span>
      </button>
      <div className="sv-side-body" id={bodyId}>
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
                  {nameOf(d)}
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
        {conflicts.length > 0 && (
          <a
            className="sv-settle"
            href={routeHref({ name: 'project', projectId, query: new URLSearchParams() })}
          >
            Settle the conflicts
          </a>
        )}
        <ul aria-labelledby="sv-conflicts">
          {conflicts.map((c) => (
            <li key={`${c.drawing_id} ${c.quantity}`}>
              <a href={surveyorHref(projectId, c.drawing_id, c.quantity)}>{c.label}</a>
              <small>{nameOf(c)}</small>
              <small>
                {c.conflict.values.map((v) => formatValue(v.value, v.unit ?? null)).join(' vs ')} ·{' '}
                {conflictState(c)}
              </small>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
