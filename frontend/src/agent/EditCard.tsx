import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { decideProposal, errorText, getDrawing, type PageView } from '../api';
import { PageFrame } from '../viewer/PageFrame';
import '../viewer/viewer.css';
import {
  areaChange,
  centreOf,
  changeLines,
  extentOf,
  pointsOf,
  zoomFor,
  type Evidence,
  type Point,
  type Proposal,
} from './agent';
import { LawSection } from './LawSection';

type PageLoad =
  { state: 'loading' } | { state: 'error'; error: unknown } | { state: 'ready'; page: PageView };

const NOTE = 'Proposed from the drawn geometry. Structure, services and permits are not checked.';

/** The legend's swatch: the same stroke, dash and fill as on the plan (colour never alone). */
function Swatch({
  kind,
  hatch,
}: {
  kind: 'existing' | 'removed' | 'added' | 'room';
  hatch: string;
}) {
  return (
    <svg className="ag-swatch" viewBox="0 0 24 14" width="24" height="14" aria-hidden="true">
      {kind === 'existing' && <rect x="1" y="5" width="22" height="4" className="ag-existing" />}
      {kind === 'removed' && <rect x="1" y="2" width="22" height="10" className="ag-removed" />}
      {kind === 'added' && <rect x="1" y="5" width="22" height="4" className="ag-added" />}
      {kind === 'room' && (
        <rect x="1" y="1" width="22" height="12" className="ag-room" fill={`url(#${hatch}-key)`} />
      )}
    </svg>
  );
}

function Overlay({ p, hatch }: { p: Proposal; hatch: string }) {
  const line = { vectorEffect: 'non-scaling-stroke' } as const;
  return (
    <>
      <svg
        className="vw-overlay ag-overlay"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          {/* In page fractions: the overlay's own units (stretched with the page, like the viewer's hatch). */}
          <pattern id={`${hatch}-plan`} width="0.012" height="0.012" patternUnits="userSpaceOnUse">
            <line
              x1="0"
              y1="0.012"
              x2="0.012"
              y2="0"
              className="ag-hatchline"
              strokeWidth="1.5"
              {...line}
            />
          </pattern>
        </defs>
        {p.rooms.map((r) => (
          <polygon
            key={r.id}
            className="ag-room"
            points={pointsOf(r.polygon)}
            fill={`url(#${hatch}-plan)`}
            {...line}
          />
        ))}
        {p.removed.map((g) => (
          <polygon key={g.id} className="ag-removed" points={pointsOf(g.polygon)} {...line} />
        ))}
        {p.added.map((g) => (
          <polygon key={g.id} className="ag-added" points={pointsOf(g.polygon)} {...line} />
        ))}
      </svg>
      {p.rooms.map((r) => {
        // Under the room, not over it, and kept off the page edge.
        const x = Math.min(Math.max(centreOf(r.polygon)[0], 0.1), 0.9);
        const y = Math.max(...r.polygon.map((q) => q[1]));
        return (
          <span
            key={r.id}
            className="ag-badge"
            style={{ left: `${String(x * 100)}%`, top: `${String(y * 100)}%` }}
          >
            {r.label} · {areaChange(r)}
          </span>
        );
      })}
    </>
  );
}

/** The plan with the proposal drawn on it (AC-32): Before hides the overlay. */
/** Where a law finding's subject is (LC-15): its ev mark, else the proposal's room by id (`subject_ref`) or by
 * the name in its label. */
export function placeOf(
  p: Proposal,
  evidence: Evidence[],
  subject: string,
  ev?: string | null,
  ref?: string | null,
): Point[] | null {
  const mark = ev ? evidence.find((e) => e.id === ev) : undefined;
  if (mark) {
    const [x0, y0, x1, y1] = mark.box;
    return [
      [x0, y0],
      [x1, y0],
      [x1, y1],
      [x0, y1],
    ];
  }
  const room =
    p.rooms.find((r) => ref && r.id === ref) ??
    p.rooms.find((r) => r.label === subject) ??
    p.rooms.find((r) => r.label.includes(subject));
  return room ? room.polygon : null;
}

function EditPlan({ p, projectId, hot }: { p: Proposal; projectId: string; hot: Point[] | null }) {
  const fig = useRef<HTMLElement>(null);
  // LC-15: a picked subject may be far below the plan (phone): bring the plan into view.
  useEffect(() => {
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches; // robust-8
    if (hot)
      fig.current?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  }, [hot]);
  const [load, setLoad] = useState<PageLoad>({ state: 'loading' });
  const [after, setAfter] = useState(true);
  const hatch = `ag-hatch-${useId().replace(/[^\w-]/g, '')}`;
  const box = useRef<HTMLDivElement>(null);
  const extent = extentOf(p);
  const zoom = zoomFor(extent);
  // Centre the change in the plan box once the page frame has its size.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.scrollLeft = ((extent[0] + extent[2]) / 2) * el.scrollWidth - el.clientWidth / 2;
    el.scrollTop = ((extent[1] + extent[3]) / 2) * el.scrollHeight - el.clientHeight / 2;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once the page is ready
  }, [load.state]);
  useEffect(() => {
    const abort = new AbortController();
    getDrawing(p.drawing_id, { project: projectId, signal: abort.signal }).then(
      (d) => {
        const page = d.pages.find((pg) => pg.page === p.page);
        setLoad(
          page
            ? { state: 'ready', page }
            : { state: 'error', error: new Error(`no page ${String(p.page)}`) },
        );
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', error });
      },
    );
    return () => {
      abort.abort();
    };
  }, [p.drawing_id, p.page, projectId]);

  return (
    <figure className="ag-plan" aria-label="Proposed plan" ref={fig}>
      {/* The legend's hatch, in px. */}
      <svg width="0" height="0" className="ag-defs" aria-hidden="true">
        <defs>
          <pattern
            id={`${hatch}-key`}
            width="8"
            height="8"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="8" className="ag-hatchline" strokeWidth="3" />
          </pattern>
        </defs>
      </svg>
      <div className="v-segmented ag-toggle" role="group" aria-label="Show the plan">
        <button
          type="button"
          aria-pressed={!after}
          onClick={() => {
            setAfter(false);
          }}
        >
          Before
        </button>
        <button
          type="button"
          aria-pressed={after}
          onClick={() => {
            setAfter(true);
          }}
        >
          After
        </button>
      </div>
      {load.state === 'loading' && <p className="en-pending">Loading the plan…</p>}
      {load.state === 'error' && (
        <p className="en-warn" role="alert">
          The plan could not be shown: {errorText(load.error).detail}
        </p>
      )}
      {load.state === 'ready' && (
        <div className="ag-planbox" ref={box}>
          <PageFrame
            zoom={zoom}
            url={load.page.url}
            width={load.page.width}
            height={load.page.height}
            alt={`Page ${String(p.page)}, ${after ? 'with the proposed change' : 'as drawn'}`}
            page={p.page}
          >
            {after && <Overlay p={p} hatch={hatch} />}
            {hot && (
              <svg
                className="vw-overlay ag-overlay"
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <polygon
                  className="ag-hot"
                  points={pointsOf(hot)}
                  vectorEffect="non-scaling-stroke"
                />
              </svg>
            )}
          </PageFrame>
        </div>
      )}
      <figcaption className="ag-legend">
        <span>
          <Swatch kind="existing" hatch={hatch} /> Existing
        </span>
        <span>
          <Swatch kind="removed" hatch={hatch} /> Demolished (yellow, dashed)
        </span>
        <span>
          <Swatch kind="added" hatch={hatch} /> New (red, solid)
        </span>
        <span>
          <Swatch kind="room" hatch={hatch} /> Changed room (hatched)
        </span>
      </figcaption>
    </figure>
  );
}

/** An edit proposal (AC-32): plan with overlay, change list, unknowns, flags, the honesty note, Accept/Reject. */
export function EditCard(props: {
  proposal: Proposal;
  projectId: string;
  chatId: string;
  /** The turn's sources: a law finding's `ev` mark is one of them (LC-15). */
  evidence?: Evidence[];
  onDecided?: (p: Proposal) => void;
}) {
  const { projectId, chatId, onDecided } = props;
  const [p, setP] = useState(props.proposal);
  const [hot, setHot] = useState<Point[] | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // robust-7: the pressed button goes away with the decision; focus moves to the status that replaces it.
  const decided = useRef(false);
  const decide = (action: 'accept' | 'reject') => {
    setSending(true);
    setError(null);
    decideProposal(projectId, chatId, p.proposal_id, action).then(
      (next) => {
        setSending(false);
        decided.current = true;
        setP(next);
        onDecided?.(next);
      },
      (e: unknown) => {
        setSending(false);
        setError(e);
      },
    );
  };
  return (
    <div className="ag-edit">
      <EditPlan p={p} projectId={projectId} hot={hot} />
      <div className="ag-side">
        <h4 className="en-label">Changes</h4>
        <ul className="ag-changes">
          {changeLines(p).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <LawSection
          law={p.law}
          onPick={(subject, ev, ref) => {
            setHot(placeOf(p, props.evidence ?? [], subject, ev, ref));
          }}
        />
        {p.unknowns.length > 0 && (
          <>
            <h4 className="en-label">Not known</h4>
            <ul className="ag-unknowns">
              {p.unknowns.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          </>
        )}
        {p.flags.length > 0 && (
          <>
            <h4 className="en-label">Before building</h4>
            <ul className="ag-flags">
              {p.flags.map((f) => (
                <li key={f.code}>{f.text}</li>
              ))}
            </ul>
          </>
        )}
        <p className="en-small">{NOTE}</p>
        {p.state === 'proposed' ? (
          <div className="ag-decide">
            <button
              type="button"
              className="v-btn v-press"
              disabled={sending}
              onClick={() => {
                decide('accept');
              }}
            >
              Accept
            </button>
            <button
              type="button"
              className="v-btn v-btn--secondary v-press"
              disabled={sending}
              onClick={() => {
                decide('reject');
              }}
            >
              Reject
            </button>
          </div>
        ) : (
          <p
            className={`v-pill ag-decided${p.state === 'accepted' ? ' v-pill--ok' : ''}`}
            role="status"
            tabIndex={-1}
            ref={(el) => {
              if (el && decided.current) {
                decided.current = false;
                el.focus();
              }
            }}
          >
            {p.state === 'accepted' ? 'Accepted' : 'Rejected'}
          </p>
        )}
        {error !== null && (
          <p className="en-warn" role="alert">
            Could not save the decision: {errorText(error).detail}
          </p>
        )}
      </div>
    </div>
  );
}
