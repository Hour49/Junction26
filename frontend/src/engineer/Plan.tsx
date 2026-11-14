import type { ComponentProps, ReactNode } from 'react';
import type { DrawingView, ProjectView } from '../api';
import { routeLabel } from '../ingest/ingest';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import { kindName } from './format';

/** Where the drawing sits in its project (GET /api/projects/{id}); null until it arrives or if it fails. */
export interface Place {
  meta: string;
  pos: string | null;
  prev: string | null;
  next: string | null;
  also: { file: string; href: string }[];
  /** The upload's file id, for the "Original file" picture. */
  originalId: string | null;
}

const engineer = (projectId: string, drawingId: string) =>
  routeHref({
    name: 'workspace',
    projectId,
    drawingId,
    role: 'engineer',
    query: new URLSearchParams(),
  });

export function placeOf(
  project: ProjectView,
  drawing: DrawingView,
  projectId: string,
): Place | null {
  const list = project.drawings;
  const i = list.findIndex((d) => d.drawing_id === drawing.id);
  const self = list[i];
  if (!self) return null;
  const n = list.length;
  const at = (j: number) => list[(j + n) % n];
  const near = (j: number) => {
    const d = at(j);
    return n > 1 && d ? engineer(projectId, d.drawing_id) : null;
  };
  const file = project.files.find(
    (f) => f.drawing_id === drawing.id && f.path === drawing.reader.source,
  );
  return {
    meta: `${kindName(self.kind)} · ${self.route ? routeLabel(self.route) : 'not routed'}`,
    pos: n > 1 ? `${String(i + 1)} / ${String(n)}` : null,
    prev: near(i - 1),
    next: near(i + 1),
    also: self.other_renderings
      .filter((o) => o.drawing_id !== drawing.id)
      .map((o) => ({ file: o.file, href: engineer(projectId, o.drawing_id) })),
    originalId: file?.id ?? null,
  };
}

const Chevron = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
    <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/** The position and previous/next drawing links as a row, where there is no plan to put them on
 * (a building model, a refusal): every drawing kind can step through the project (EN-56). */
export function DrawingNav({ place }: { place: Place | null }) {
  if (!place?.pos) return null;
  return (
    <nav className="en-drawnav" aria-label="Drawings">
      {place.prev && (
        <a className="en-nav" href={place.prev} aria-label="Previous drawing">
          <Chevron d="M15 5l-7 7 7 7" />
        </a>
      )}
      <span className="en-pos" aria-live="polite">
        {place.pos}
      </span>
      {place.next && (
        <a className="en-nav" href={place.next} aria-label="Next drawing">
          <Chevron d="M9 5l7 7-7 7" />
        </a>
      )}
    </nav>
  );
}

/** The page viewer with this screen's drawing position, arrows and overlay around it. */
export function Plan(props: {
  viewer: ComponentProps<typeof PageViewer>;
  place: Place | null;
  overlay?: ReactNode;
}) {
  const { viewer, place, overlay } = props;
  // Kind · route only: the viewer's page line prints page 1's storey and scale itself (orch, no doubles).
  return (
    <div className="en-plan">
      {place && (place.pos || place.also.length > 0) && (
        <div className="en-place">
          {place.also.length > 0 && (
            <span className="en-also">
              Also as{' '}
              {place.also.map((o, i) => (
                <span key={o.href}>
                  {i > 0 && ', '}
                  <a href={o.href}>{o.file}</a>
                </span>
              ))}
            </span>
          )}
          {place.pos && (
            <span className="en-pos" aria-live="polite">
              {place.pos}
            </span>
          )}
        </div>
      )}
      <div className="en-planbox">
        <PageViewer {...viewer} meta={place?.meta} />
        {place?.prev && (
          <a className="en-nav en-nav--prev" href={place.prev} aria-label="Previous drawing">
            <Chevron d="M15 5l-7 7 7 7" />
          </a>
        )}
        {place?.next && (
          <a className="en-nav en-nav--next" href={place.next} aria-label="Next drawing">
            <Chevron d="M9 5l7 7-7 7" />
          </a>
        )}
        {overlay}
      </div>
    </div>
  );
}
