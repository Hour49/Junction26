import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { getModel, type DrawingView, type Highlight, type MarkView } from '../api';
import { ModelDialog } from '../model3d/ModelDialog';
import { PageViewer } from '../viewer/PageViewer';
import {
  roomAt,
  roomName,
  roomsOf,
  type Box,
  type ModelRoom,
  type Selection,
  type View,
} from './agent';

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

/** W1 (look-check, board #404): the pane is narrow and its viewer has no zoom buttons, so it never zooms. A box
 * focus makes PageViewer zoom in on a small place, cutting the plan off at both sides; here the page opens whole,
 * fitted to the pane's width, with the marks drawn. A source picked by [n] is outlined (a polygon does not zoom). */
export function paneFocus(
  view: View | null,
  focus: Box | null,
): { page: number; polygon?: [number, number][] } | null {
  if (!view) return null;
  if (!focus) return { page: view.page };
  const [x0, y0, x1, y1] = focus;
  return {
    page: view.page,
    polygon: [
      [x0, y0],
      [x1, y0],
      [x1, y1],
      [x0, y1],
    ],
  };
}

/** One file of the list beside the chat, as the pane needs it. */
export interface PaneFile {
  drawing_id: string;
  label: string;
  /** Its 3D model (model-3d.md "More places"): its file and what to highlight. */
  model: { fileId: string; highlight: readonly Highlight[] } | null;
  /** The pen can draw on it (canDraw). */
  drawable: boolean;
}

/** A pick box no wider than the viewer's click box (`pickBox`, 0.03 of the page) is a click: a room. */
const CLICK_W = 0.031;

/** What the user drew on, as the server's Selection without its id, and the chip's words. */
export function selectionOf(
  d: { drawing_id: string; name: string },
  page: number,
  box: Box,
  rooms: ModelRoom[] = [],
): { sel: Omit<Selection, 'id'>; chip: string } {
  const where = `${d.name}, page ${String(page)}`;
  if (box[2] - box[0] > CLICK_W)
    return {
      sel: { kind: 'region', drawing_id: d.drawing_id, page, box },
      chip: `Area on ${where}`,
    };
  const room = roomAt(rooms, page, [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]);
  // No room under the click: the box alone, the server resolves the room under it (AC-12, AC-21).
  if (!room)
    return { sel: { kind: 'room', drawing_id: d.drawing_id, page, box }, chip: `Room on ${where}` };
  return {
    sel: { kind: 'room', drawing_id: d.drawing_id, page, ref: room.id, box },
    chip: `Room ${roomName(room)}`, // edits-9: with its number
  };
}

function FileRow(props: {
  projectId: string;
  file: PaneFile;
  open: boolean;
  drawing: DrawingView | null | undefined;
  view: View | null;
  focus: Box | null;
  /** Bumped by "Show it"/[n] on this file: it scrolls into view. */
  reveal: number;
  drawMode: boolean;
  onToggle: () => void;
  onPick: (sel: Omit<Selection, 'id'>, chip: string) => void;
}) {
  const { projectId, file, open, drawing, focus, reveal, onToggle, onPick } = props;
  const { drawing_id: drawingId, label, model } = file;
  const [open3d, setOpen3d] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const row = useRef<HTMLLIElement>(null);
  const view = props.view?.drawing_id === drawingId ? props.view : null;
  const drawing_ = open && props.drawMode && file.drawable;
  // Room ids for clicks, once the pen is on this file; without the model a click still goes as a point.
  const [rooms, setRooms] = useState<ModelRoom[] | null>(null);
  useEffect(() => {
    if (!drawing_ || rooms !== null) return;
    const abort = new AbortController();
    getModel(drawingId, { signal: abort.signal }).then(
      (m) => {
        setRooms(roomsOf(m));
      },
      () => {
        if (!abort.signal.aborted) setRooms([]);
      },
    );
    return () => {
      abort.abort();
    };
  }, [drawing_, rooms, drawingId]);
  useEffect(() => {
    if (reveal > 0) row.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [reveal]);
  const bodyId = `ag-file-${drawingId}`;
  return (
    <li ref={row} className="flex flex-col gap-2 border-b border-border pb-2 last:border-b-0">
      <div className="flex items-center gap-2">
        <h3 className="m-0 min-w-0 flex-1">
          <Button
            type="button"
            variant="ghost"
            className="h-auto w-full justify-start px-2 py-2 text-left text-[15px] font-semibold whitespace-normal"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={onToggle}
          >
            <span aria-hidden="true" className="text-muted-foreground">
              {open ? '▾' : '▸'}
            </span>
            {label}
          </Button>
        </h3>
      </div>
      {open && (
        <div id={bodyId} className="relative flex flex-col gap-2">
          {view?.caption && <p className="m-0 text-[15px] text-muted-foreground">{view.caption}</p>}
          {drawing_ && (
            <p className="m-0 text-sm font-semibold">Click a room or drag a rectangle.</p>
          )}
          <div className={drawing_ ? 'ag-pane-view ag-drawing' : 'ag-pane-view'}>
            {drawing ? (
              <PageViewer
                bare
                file={drawing.file}
                pages={drawing.pages}
                marks={view ? viewMarks(view) : []}
                focus={paneFocus(view, focus)}
                fixMode={drawing_}
                onAddMark={
                  drawing_
                    ? (box, page) => {
                        const { sel, chip } = selectionOf(
                          { drawing_id: drawingId, name: label },
                          page,
                          box,
                          rooms ?? [],
                        );
                        onPick(sel, chip);
                      }
                    : undefined
                }
              />
            ) : drawing === null ? (
              <p className="text-muted-foreground">This plan could not be loaded.</p>
            ) : (
              <p className="text-muted-foreground">Loading the plan…</p>
            )}
          </div>
          {model && (
            <Button
              ref={opener}
              type="button"
              variant="secondary"
              size="pill-icon"
              className="absolute top-2 right-2 z-10 shadow-sm"
              aria-label={`View in 3D: ${label}`}
              onClick={() => {
                setOpen3d(true);
              }}
            >
              3D
            </Button>
          )}
          {model && open3d && (
            <ModelDialog
              projectId={projectId}
              fileId={model.fileId}
              label={label}
              highlight={model.highlight}
              onClose={() => {
                setOpen3d(false);
                opener.current?.focus();
              }}
            />
          )}
        </div>
      )}
    </li>
  );
}

/** The files beside the chat (ui-bugs 2): the project's askable drawings by name; a name opens its plan under it
 * and closes it again, several at once. The newest turn's place opens its file with the marks drawn; with the pen
 * on, a click or a drag on an open drawable plan becomes a selection. */
export function PlanPane(props: {
  projectId: string;
  files: PaneFile[];
  open: readonly string[];
  /** The askable drawings as read, by id; undefined while they load, a missing id: not read. */
  drawn: Record<string, DrawingView> | null;
  view: View | null;
  focus: Box | null;
  reveal: { drawingId: string; n: number } | null;
  drawMode: boolean;
  onToggle: (drawingId: string) => void;
  onPick: (sel: Omit<Selection, 'id'>, chip: string) => void;
  /** Set when the pane is a sheet over the chat (chat-ux #9): a Close button in its head. */
  onClose?: () => void;
}) {
  const { files, drawn, reveal } = props;
  return (
    <aside className="ag-pane" aria-label="Plan">
      <div className="flex items-center justify-between gap-3">
        <h2 className="m-0 text-[17px] font-semibold">Files</h2>
        {props.onClose && (
          <Button type="button" variant="secondary" size="pill-sm" onClick={props.onClose}>
            Close
          </Button>
        )}
      </div>
      <ul className="ag-files m-0 flex min-h-0 flex-1 list-none flex-col gap-2 overflow-auto p-0">
        {files.map((f) => (
          <FileRow
            key={f.drawing_id}
            projectId={props.projectId}
            file={f}
            open={props.open.includes(f.drawing_id)}
            drawing={drawn ? (drawn[f.drawing_id] ?? null) : undefined}
            view={props.view}
            focus={props.focus}
            reveal={reveal?.drawingId === f.drawing_id ? reveal.n : 0}
            drawMode={props.drawMode}
            onToggle={() => {
              props.onToggle(f.drawing_id);
            }}
            onPick={props.onPick}
          />
        ))}
      </ul>
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
