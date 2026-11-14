import { useEffect, useState } from 'react';
import { errorText, getDrawing, getModel, type DrawingView } from '../api';
import { PageViewer } from '../viewer/PageViewer';
import { roomAt, roomName, roomsOf, type Box, type ModelRoom, type Selection } from './agent';

export interface PlanChoice {
  drawing_id: string;
  name: string;
}

/** A pick box no wider than the viewer's click box (`pickBox`, 0.03 of the page) is a click: a room. */
const CLICK_W = 0.031;

/** What the user pointed at, as the server's Selection without its id, and the chip's words. */
export function selectionOf(
  d: PlanChoice,
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

type Load =
  | { state: 'loading' }
  | { state: 'error'; error: unknown }
  | { state: 'ready'; drawing: DrawingView; rooms: ModelRoom[] };

function Picker(props: {
  plan: PlanChoice;
  projectId: string;
  onPick: (page: number, box: Box, rooms: ModelRoom[]) => void;
}) {
  const { plan, projectId, onPick } = props;
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  useEffect(() => {
    const abort = new AbortController();
    const opts = { signal: abort.signal };
    Promise.all([
      getDrawing(plan.drawing_id, { ...opts, project: projectId }),
      // Room ids for clicks; without the model a click still goes as a point.
      getModel(plan.drawing_id, opts).then(roomsOf, () => []),
    ]).then(
      ([drawing, rooms]) => {
        setLoad({ state: 'ready', drawing, rooms });
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [plan.drawing_id, projectId]);
  if (load.state === 'loading') return <p className="en-pending">Loading {plan.name}…</p>;
  if (load.state === 'error')
    return (
      <p className="en-warn" role="alert">
        {plan.name} could not be loaded: {errorText(load.error).detail}
      </p>
    );
  const d = load.drawing;
  return (
    <PageViewer
      file={d.file}
      pages={d.pages}
      marks={[]}
      credit={d.credit}
      fixMode
      onAddMark={(box, page) => {
        onPick(page, box, load.rooms);
      }}
    />
  );
}

/** "Point at the plan" (AC-33): choose a plan, then click a room or drag a rectangle on its page. */
export function PlanPointer(props: {
  projectId: string;
  plans: PlanChoice[];
  onAdd: (sel: Omit<Selection, 'id'>, chip: string) => void;
  onClose: () => void;
}) {
  const { projectId, plans, onAdd, onClose } = props;
  const [plan, setPlan] = useState<PlanChoice | null>(
    plans.length === 1 ? (plans[0] ?? null) : null,
  );
  return (
    <section
      className="v-card ag-pointer"
      aria-label="Point at the plan"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div className="en-labelrow">
        <h4 className="en-label">
          {plan ? `Click a room or drag a rectangle on ${plan.name}` : 'Which plan?'}
        </h4>
        <button type="button" className="v-btn v-btn--secondary v-press" onClick={onClose}>
          Done
        </button>
      </div>
      {plan === null ? (
        <div className="en-suggest" role="group" aria-label="Plans">
          {plans.length === 0 && (
            <p className="en-empty">No plan in this project can be pointed at.</p>
          )}
          {plans.map((p) => (
            <button
              key={p.drawing_id}
              type="button"
              className="en-chip v-press"
              onClick={() => {
                setPlan(p);
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
      ) : (
        <Picker
          plan={plan}
          projectId={projectId}
          onPick={(page, box, rooms) => {
            const { sel, chip } = selectionOf(plan, page, box, rooms);
            onAdd(sel, chip);
          }}
        />
      )}
    </section>
  );
}
