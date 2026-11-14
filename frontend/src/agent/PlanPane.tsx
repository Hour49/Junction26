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
