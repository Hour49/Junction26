import { type KeyboardEvent, type ReactNode, useEffect, useRef } from 'react';
import type { DrawingView, MarkView } from '../api';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import type { Box, View } from './agent';

/** The view's marks as the viewer's: numbered as the turn's sources `[n]`, outlined as counted places. */
export const viewMarks = (v: View): MarkView[] =>
  v.marks.map((m) => ({
    id: `n${String(m.n)}`,
    n: m.n,
    page: v.page,
    box: m.box,
    polygon: m.polygon ?? null,
    label: m.label,
    reason: null,
    ref: null,
    state: 'counted',
    value: null,
  }));

/** The plan beside the chat (chat-ux #1, contract A): the drawing the newest turn points at, its marks drawn and
 * the place in view; before any place, the project's first drawing. Several drawings: a switcher. */
export function PlanPane(props: {
  projectId: string;
  pack: string | null;
  drawings: { drawing_id: string; label: string }[];
  drawingId: string;
  /** undefined while the drawings load; null: this one could not be read. */
  drawing: DrawingView | null | undefined;
  view: View | null;
  focus: Box | null;
  onDrawing: (drawingId: string) => void;
  /** Set when the pane is a sheet over the chat (chat-ux #9): a Close button in its head. */
  onClose?: () => void;
}) {
  const { projectId, pack, drawings, drawingId, drawing, focus, onDrawing } = props;
  // A view on another drawing than the shown one (the user switched) is not drawn.
  const view = props.view?.drawing_id === drawingId ? props.view : null;
  const label = drawings.find((d) => d.drawing_id === drawingId)?.label ?? drawing?.file ?? '';
  const query = new URLSearchParams(pack ? { pack } : {});
  if (view) {
    query.set('page', String(view.page));
    query.set('box', (focus ?? view.box).join(','));
  }
  return (
    <aside className="ag-pane" aria-label="Plan">
      <div className="ag-pane-head">
        <h2 className="ag-pane-name">{label}</h2>
        <a
          className="ag-pane-open"
          href={routeHref({ name: 'workspace', projectId, drawingId, role: 'engineer', query })}
        >
          Open in workspace
        </a>
        {props.onClose && (
          <button type="button" className="en-chip v-press ag-pane-close" onClick={props.onClose}>
            Close
          </button>
        )}
      </div>
      {drawings.length > 1 && (
        <div className="ag-pane-pick" role="group" aria-label="Drawings">
          {drawings.map((d) => (
            <button
              key={d.drawing_id}
              type="button"
              className="en-chip v-press"
              aria-pressed={d.drawing_id === drawingId}
              onClick={() => {
                onDrawing(d.drawing_id);
              }}
            >
              {d.label}
            </button>
          ))}
        </div>
      )}
      {view?.caption && <p className="ag-pane-caption">{view.caption}</p>}
      <div className="ag-pane-view">
        {drawing ? (
          <PageViewer
            bare
            file={drawing.file}
            pages={drawing.pages}
            marks={view ? viewMarks(view) : []}
            focus={view ? { page: view.page, box: focus ?? view.box } : null}
          />
        ) : drawing === null ? (
          <p className="en-muted">This plan could not be loaded.</p>
        ) : (
          <p className="en-muted">Loading the plan…</p>
        )}
      </div>
    </aside>
  );
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/** The plan as a full-screen sheet over the chat under 1200 px (chat-ux #9): focus moves into it and Tab keeps it
 * there (the chat behind is out of sight), Escape closes it except inside the viewer (which uses Escape to clear a
 * tip or a drag), and focus goes back where it was. */
export function PlanSheet({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(() => {
    const back = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    box.current?.focus();
    return () => {
      back?.focus();
    };
  }, []);
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (e.key === 'Escape') {
      if (!target.closest('.vw')) close.current();
      return;
    }
    if (e.key !== 'Tab' || !box.current) return;
    const all = [...box.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const first = all[0];
    const last = all.at(-1);
    if (!first || !last) return;
    // From the last control forward, or from the first (or the sheet itself) back: wrap around.
    if (!e.shiftKey && (target === last || target === box.current)) {
      e.preventDefault();
      first.focus();
    } else if (e.shiftKey && (target === first || target === box.current)) {
      e.preventDefault();
      last.focus();
    }
  };
  return (
    <div
      className="ag-sheet"
      role="dialog"
      aria-modal="true"
      aria-label="The plan"
      tabIndex={-1}
      ref={box}
      onKeyDown={onKeyDown}
    >
      {children}
    </div>
  );
}
