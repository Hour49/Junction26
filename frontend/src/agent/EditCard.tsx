import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { decideProposal, errorText, getDrawing, type PageView } from '../api';
import { PageFrame } from '../viewer/PageFrame';
import '../viewer/viewer.css';
import {
  areaChange,
  badgeGroups,
  changeLines,
  extentOf,
  pointsOf,
  zoomFor,
  type Box,
  type Evidence,
  type Point,
  type Proposal,
} from './agent';
import { LawSection } from './LawSection';
import { useServiceTabs } from './multi/ServiceTabs';
import type { ServicesFollow } from './multi/services';
import { ServicesChangePlan } from './services_change/ServicesChangePlan';

/** `key`: the drawing and page it is for; another key means that page is still loading (AC-40: a tab's sheet). */
type PageLoad =
  | { state: 'loading' }
  | { state: 'error'; key: string; error: unknown }
  | { state: 'ready'; key: string; page: PageView; file: string };

const NOTE = 'Proposed from the drawn geometry. Structure, services and permits are not checked.';
// SERVICES_FOLLOW=on: the tabs above show what the change does to each services model or picture
const NOTE_NOT_FOLLOWED =
  'Proposed from the drawn geometry; no services model or picture covers it, as each tab shows. Structure, services and permits are not checked.';
const NOTE_NOT_ALIGNED =
  'Proposed from the drawn geometry; a services model or picture could not be laid on this drawing, as each tab shows. Structure, services and permits are not checked.';

/** The note with a services follow-up: what its lanes were followed through, as the tabs show them (edits R1 1b:
 * "followed through their models" while every tab said "no model"). A lane a picture checked carries `picture`. */
function followedNote(follow: ServicesFollow): string {
  const checked = follow.disciplines.filter((l) => l.status === 'checked');
  if (checked.length === 0) {
    // review-710: a lane with a model or picture that could not be laid on the sheet is "not aligned", not "no model"
    return follow.disciplines.some((l) => l.status === 'not_aligned')
      ? NOTE_NOT_ALIGNED
      : NOTE_NOT_FOLLOWED;
  }
  const pictures = checked.filter((l) => l.picture).length;
  const how =
    pictures === 0
      ? 'through their models'
      : pictures === checked.length
        ? 'on their pictures'
        : 'through their models and pictures';
  return `Proposed from the drawn geometry; services followed ${how}, as each tab shows. Structure and permits are not checked.`;
}
const SERVICES_NOTE =
  'Proposed from the services model in the IFC file. Structure, flow, pressure and permits are not checked.';

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
      {badgeGroups(p.rooms).map((g) => (
        // Under the room, not over it; badges that would overlap stack in one column.
        <span
          key={g.rooms[0]?.id}
          className="ag-badges"
          style={{ left: `${String(g.x * 100)}%`, top: `${String(g.y * 100)}%` }}
        >
          {g.rooms.map((r) => (
            <span key={r.id} className="ag-badge">
              {r.label} · {areaChange(r)}
            </span>
          ))}
        </span>
      ))}
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

/** One sheet's page in a scrolling box, centred on `extent` and zoomed to it, with `children` drawn over it in
 * that page's fractions. `label`: a panel of the All sheets view (AC-45), named so, with `open` going to its tab. */
function SheetBox({
  projectId,
  source,
  extent,
  alt,
  label,
  open,
  children,
}: {
  projectId: string;
  source: { drawing_id: string; page: number };
  extent: Box;
  alt: (file: string) => string;
  label?: string | ((file: string) => string);
  open?: { name: string; go: () => void };
  children: ReactNode;
}) {
  const [loaded, setLoad] = useState<PageLoad>({ state: 'loading' });
  const key = `${source.drawing_id}#${String(source.page)}`;
  const load: PageLoad =
    loaded.state !== 'loading' && loaded.key === key ? loaded : { state: 'loading' };
  const box = useRef<HTMLDivElement>(null);
  const zoom = zoomFor(extent);
  // Centre the change in the plan box once the page frame has its size, and again when the box changes width: the
  // frame scales with the box, the scroll does not (a window resize keeps the card mounted, #716).
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const centre = () => {
      el.scrollLeft = ((extent[0] + extent[2]) / 2) * el.scrollWidth - el.clientWidth / 2;
      el.scrollTop = ((extent[1] + extent[3]) / 2) * el.scrollHeight - el.clientHeight / 2;
    };
    centre();
    if (typeof ResizeObserver === 'undefined') return;
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth === width) return;
      width = el.clientWidth;
      centre();
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once the page is ready, and when a tab changes the extent
  }, [load.state, ...extent]);
  useEffect(() => {
    const abort = new AbortController();
    const { drawing_id, page: n } = source;
    const at = `${drawing_id}#${String(n)}`;
    getDrawing(drawing_id, { project: projectId, signal: abort.signal }).then(
      (d) => {
        const page = d.pages.find((pg) => pg.page === n);
        setLoad(
          page
            ? { state: 'ready', key: at, page, file: d.file }
            : { state: 'error', key: at, error: new Error(`no page ${String(n)}`) },
        );
      },
      (error: unknown) => {
        if (!abort.signal.aborted) setLoad({ state: 'error', key: at, error });
      },
    );
    return () => {
      abort.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `source` is rebuilt each render; `key` names it
  }, [key, projectId]);

  const body = (
    <>
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
            alt={alt(load.file)}
            page={source.page}
          >
            {children}
          </PageFrame>
        </div>
      )}
    </>
  );
  if (label === undefined) return body;
  const file = load.state === 'ready' ? load.file : '';
  const named = typeof label === 'string' ? label : label(file);
  return (
    <section className="ms-sync-panel" aria-label={named}>
      <p className="ms-sync-head">
        <span>{typeof label === 'string' ? 'Plan' : `${open?.name ?? ''} · ${file}`}</span>
        {open && (
          <button type="button" className="ag-law-subject" onClick={open.go}>
            Open {open.name}
          </button>
        )}
      </p>
      {body}
    </section>
  );
}

function EditPlan({
  p,
  projectId,
  hot,
  reveal,
}: {
  p: Proposal;
  projectId: string;
  hot: Point[] | null;
  reveal: number;
}) {
  const fig = useRef<HTMLElement>(null);
  // LC-15: a picked subject may be far below the plan (phone): bring the plan into view; so does Show it.
  useEffect(() => {
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches; // robust-8
    if (hot || reveal > 0)
      fig.current?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  }, [hot, reveal]);
  const [after, setAfter] = useState(true);
  const [revealed, setRevealed] = useState(reveal);
  if (reveal !== revealed) {
    setRevealed(reveal);
    setAfter(true);
  }
  const services = useServiceTabs(p, after); // a tab per discipline (services-follow.md)
  // AC-40: a tab with its own services sheet shows that sheet; otherwise the plan
  const sheet = services?.sheet ?? null;
  const source = sheet ?? { drawing_id: p.drawing_id, page: p.page };
  const hatch = `ag-hatch-${useId().replace(/[^\w-]/g, '')}`;
  const extent = services?.focus ?? extentOf(p);
  const sync = services?.sync ?? null;
  const planLayer = (
    <>
      {after && <Overlay p={p} hatch={hatch} />}
      {hot && (
        <svg
          className="vw-overlay ag-overlay"
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polygon className="ag-hot" points={pointsOf(hot)} vectorEffect="non-scaling-stroke" />
        </svg>
      )}
    </>
  );
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
      {services?.tabs}
      {services?.head}
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
      {sync ? (
        // AC-45: the plan and each lane's own sheet side by side, the edit on every one (Before/After for all)
        <div className="ms-sync">
          <SheetBox
            projectId={projectId}
            source={{ drawing_id: p.drawing_id, page: p.page }}
            extent={extentOf(p)}
            label={`Plan, ${after ? 'with the proposed change' : 'as drawn'}`}
            alt={() => `Page ${String(p.page)}, ${after ? 'with the proposed change' : 'as drawn'}`}
          >
            {planLayer}
          </SheetBox>
          {sync.map((s) => (
            <SheetBox
              key={s.discipline}
              projectId={projectId}
              source={s.sheet}
              extent={s.focus ?? extentOf(p)}
              label={(file) =>
                `${s.name}: ${file}, ${after ? 'with the proposed change' : 'as drawn'}`
              }
              alt={(file) =>
                `${file}, page ${String(s.sheet.page)}, ${after ? 'with the proposed change drawn on it' : 'as drawn'}`
              }
              open={{ name: s.name, go: s.open }}
            >
              {s.layer}
            </SheetBox>
          ))}
        </div>
      ) : (
        <SheetBox
          projectId={projectId}
          source={source}
          extent={extent}
          alt={(file) =>
            sheet
              ? `${file}, page ${String(sheet.page)}, ${after ? 'with the proposed change drawn on it' : 'as drawn'}`
              : `Page ${String(p.page)}, ${after ? 'with the proposed change' : 'as drawn'}`
          }
        >
          {/* the plan's overlay and a picked subject are in the plan's page fractions: not on another sheet */}
          {!sheet && planLayer}
          {services?.layer}
        </SheetBox>
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
      {services?.panel}
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
  /** Bumped by the turn's Show it: the plan shows After and comes into view. */
  reveal?: number;
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
      {p.services_change ? (
        <ServicesChangePlan p={p} />
      ) : (
        <EditPlan p={p} projectId={projectId} hot={hot} reveal={props.reveal ?? 0} />
      )}
      <div className="ag-side">
        {changeLines(p).length > 0 && (
          <>
            <h4 className="en-label">Changes</h4>
            <ul className="ag-changes">
              {changeLines(p).map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        )}
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
        <p className="en-small">
          {p.services_change ? SERVICES_NOTE : p.services ? followedNote(p.services) : NOTE}
        </p>
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
