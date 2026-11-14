import { type CSSProperties, useId, useLayoutEffect, useRef, useState } from 'react';
import type { AnswerView, MarkView, PageView, QuantityConflict } from '../api/types';
import { formatValue, methodName } from '../api/format';
import { Credit } from '../shell/Credit';
import { PageFrame } from './PageFrame';
import {
  badgeText,
  DASH,
  markLook,
  MUTED,
  normalisedNote,
  pickBox,
  placeLabels,
  type PlacedLabel,
  safeColour,
  startPage,
  STATE_WORDS,
} from './marks';
import './viewer.css';

type LegendEntry = NonNullable<AnswerView['proof']>['legend'][number];
type Box = [number, number, number, number];

/** A place the readers disagree on: Bogdan's `answer.check.disputed` item with `mark_id` as `markId` (viewer.md). */
export interface Disputed {
  markId?: string | null; // Bogdan's mark_id; absent or null: a place the answer did not count
  page?: number; // absent: the page being shown
  box?: number[];
  why: string;
}

export interface PageViewerProps {
  file: string;
  pages: PageView[];
  marks: MarkView[];
  credit: string | null;
  unit?: string | null; // the row's or answer's unit: badges show mark values unless "count" or null
  unlocated?: Record<string, number>; // a takeoff row's items counted without a position
  legend?: LegendEntry[] | null; // answer.proof.legend: a colour per label, `note` lines
  conflict?: QuantityConflict | null; // where each method read its value: tags A, B…
  selected?: string | null;
  highlighted?: string | null;
  onSelect?: (markId: string | null) => void;
  onHover?: (markId: string | null) => void;
  onPick?: (page: number, box: [number, number, number, number]) => void; // set while adding a mark
  meta?: string; // appended to the page meta line, e.g. "PDF vector · vector route" (D61)
  disputed?: Disputed[] | null; // places to double-check (viewer.md "Double-check")
  fixMode?: boolean; // with onAddMark: a click, tap or drag on the page proposes a mark
  onAddMark?: (box: Box, page: number) => void;
}

interface Drag {
  x: number; // page fractions where it started
  y: number;
  cx: number; // client px where it started
  cy: number;
  touch: boolean;
  to: [number, number] | null; // page fractions of the pointer now (mouse and pen only)
}

const SLOP = 8; // px a pointer may move and still be a click or tap
const round5 = (v: number) => Number(v.toFixed(5));
const clamp01 = (v: number) => Math.min(Math.max(v, 0), 1);
const ask = (why: string) => `Please double-check: ${why}`;

type Zoom = 1 | 2 | 4;

const NARROW = 600; // px of frame width under which badges show their number only
const STATE_ORDER: MarkView['state'][] = ['counted', 'added', 'rejected', 'excluded'];
const inPage = (v: number) => v >= 0 && v <= 1;

const countText = (k: number) => `${String(k)} mark${k === 1 ? '' : 's'}`;
/** The inline custom property viewer.css reads every mark colour from. */
const tint = (c: string) => ({ '--vw-c': c }) as CSSProperties;
const open = (m: MarkView) => m.state === 'rejected' || m.state === 'excluded';

/** Where a badge or ? button sits: its placed spot, else its box centre (first render, jsdom). */
function spotStyle(
  spot: PlacedLabel | null | undefined,
  [x0, y0, x1, y1]: Box,
  W: number,
  H: number,
): CSSProperties {
  return spot
    ? {
        left: `${((spot.x / W) * 100).toFixed(3)}%`,
        top: `${((spot.y / H) * 100).toFixed(3)}%`,
        width: `${String(spot.w)}px`,
        height: `${String(spot.h)}px`,
      }
    : {
        left: `${(((x0 + x1) / 2) * 100).toFixed(1)}%`,
        top: `${(((y0 + y1) / 2) * 100).toFixed(1)}%`,
      };
}

/** The why of a disputed place, next to its badge; below it when the badge is near the top. */
function whyTip(why: string, where: CSSProperties) {
  const below = parseFloat(String(where.top)) < 20;
  return (
    <span
      key="why-tip"
      role="tooltip"
      className={below ? 'vw-why vw-why--below' : 'vw-why'}
      style={{ left: where.left, top: where.top }}
    >
      {ask(why)}
    </span>
  );
}

function words(mark: MarkView): string {
  const w = STATE_WORDS[mark.state];
  if (!mark.reason) return w;
  return mark.state === 'excluded'
    ? `${w}: ${mark.reason}`
    : `${w} (the rule left it out: ${mark.reason})`;
}

/** One page of a drawing with its marks drawn on it (docs/specs/frontend/viewer.md). */
export function PageViewer({
  file,
  pages,
  marks,
  credit,
  unit = null,
  unlocated,
  legend,
  conflict,
  selected = null,
  highlighted = null,
  onSelect,
  onHover,
  onPick,
  meta,
  disputed,
  fixMode = false,
  onAddMark,
}: PageViewerProps) {
  const uid = useId().replace(/[^\w-]/g, '');
  const hatch = `vw-hatch-${uid}`;
  const [tip, setTip] = useState<string | null>(null); // key of the badge or ? button whose why shows
  const [drag, setDrag] = useState<Drag | null>(null);
  const pageOf = (id: string | null) => marks.find((m) => m.id === id)?.page;
  const [current, setCurrent] = useState<number | undefined>(() => pageOf(selected));
  const [lastSelected, setLastSelected] = useState(selected);
  const [zoom, setZoom] = useState<Zoom>(1);
  const scroll = useRef<HTMLDivElement>(null);
  const [frameWidth, setFrameWidth] = useState(0); // the frame at zoom 1; 0 until measured
  useLayoutEffect(() => {
    const el = scroll.current;
    if (!el) return;
    const measure = () => {
      setFrameWidth(el.clientWidth);
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, []);
  // A newly selected mark on another page brings its page up; a highlight does not.
  if (selected !== lastSelected) {
    setLastSelected(selected);
    const target = pageOf(selected);
    if (target !== undefined) setCurrent(target);
  }
  const page =
    pages.find((p) => p.page === current) ?? pages.find((p) => p.page === startPage(pages, marks));
  if (!page)
    return <p className="vw-empty">This drawing has no page to show: it is a building model.</p>;

  const placed = (m: MarkView) =>
    pages.some((p) => p.page === m.page) &&
    m.box.every(inPage) &&
    m.box[0] <= m.box[2] &&
    m.box[1] <= m.box[3];
  const unplaced = marks.filter((m) => !placed(m)).length;
  const onPage = marks.filter((m) => m.page === page.page && placed(m));
  const index = pages.indexOf(page);
  const readings = (conflict?.values ?? []).map((v, i) => ({
    ...v,
    tag: String.fromCharCode(65 + i),
  }));
  const tags = readings.filter((r) => r.page === page.page && r.box && r.box.every(inPage));
  const colourOf = (m: MarkView) =>
    open(m)
      ? MUTED
      : // one entry (a room count's "room"): every mark takes it, as evidence_render.py does
        safeColour(
          (legend?.length === 1 ? legend[0] : legend?.find((e) => e.label === m.label))?.colour,
        );
  const showValue = unit !== null && unit !== 'count';
  const valueOf = (m: MarkView) =>
    showValue && m.value !== null && (m.state === 'counted' || m.state === 'added')
      ? formatValue(m.value, unit)
      : null;
  // Double-check: where each disputed place is, and what cannot be shown.
  const validBox = (b: number[] | undefined): b is Box =>
    b?.length === 4 &&
    b.every(inPage) &&
    Number(b[0]) <= Number(b[2]) &&
    Number(b[1]) <= Number(b[3]);
  const doubtOf = new Map<string, string>(); // mark id → why
  const boxItems: { box: Box; page: number; why: string }[] = [];
  let lost = 0;
  for (const d of disputed ?? []) {
    if (d.markId) {
      const m = marks.find((k) => k.id === d.markId);
      if (m && placed(m)) doubtOf.set(m.id, d.why);
      else lost++;
    } else {
      const p = d.page ?? page.page;
      if (validBox(d.box) && pages.some((q) => q.page === p))
        boxItems.push({ box: d.box, page: p, why: d.why });
      else lost++;
    }
  }
  const doubtPages = [
    ...marks.filter((m) => doubtOf.has(m.id)).map((m) => m.page),
    ...boxItems.map((b) => b.page),
  ];
  const boxesHere = boxItems.filter((b) => b.page === page.page);
  const doubtsHere = doubtPages.filter((p) => p === page.page).length;
  const elsewhere = [...new Set(doubtPages.filter((p) => p !== page.page))].sort((a, b) => a - b);
  const outlines = [
    ...onPage.filter((m) => doubtOf.has(m.id)).map((m) => m.box),
    ...boxesHere.map((b) => b.box),
  ];
  // Badges are placed so no two overlap once the frame's width is known (R2-qa-1-3).
  const W = frameWidth * zoom;
  const H = (W * page.height) / page.width;
  const narrow = W < NARROW;
  const spots =
    W > 0
      ? placeLabels(
          [
            ...onPage.map((m) => {
              const value = valueOf(m);
              return {
                box: m.box,
                full: value !== null && !narrow ? `${badgeText(m)} · ${value}` : badgeText(m),
                short: badgeText(m),
              };
            }),
            ...boxesHere.map((b) => ({ box: b.box, full: '?', short: '?' })),
          ],
          W,
          H,
        )
      : null;
  const noRoom = spots?.filter((p) => p === null).length ?? 0;
  const states = STATE_ORDER.filter((s) => onPage.some((m) => m.state === s));
  const unlocatedLines = Object.entries(unlocated ?? {}).filter(([, k]) => k > 0);
  const chosen = onPage.find((m) => m.id === selected) ?? onPage.find((m) => m.id === highlighted);
  const note = normalisedNote(page.normalised);
  // #121's page fields are missing on an older backend: read them as optional (VW-59).
  const facts: {
    scale?: PageView['scale'] | null;
    scale_text?: string | null;
    storey?: string | null;
  } = page;
  // A scale that was not read off the sheet says so: "1:100 (estimated)", "not to scale" (VW-59).
  const status = facts.scale?.status;
  const scaleWords = !status || status === 'scaled' ? '' : status.replace(/_/g, ' ');
  const scale =
    facts.scale_text && scaleWords ? `${facts.scale_text} (${scaleWords})` : facts.scale_text;
  const pageMeta = [facts.storey, scale || scaleWords].filter((t): t is string => !!t);
  const classes = onPage.length > 0 ? (legend ?? []).filter((e) => e.count > 0) : [];
  const reasons = new Set(onPage.filter((m) => m.state === 'excluded').map((m) => m.reason));
  const [oneReason] = reasons.size === 1 ? [...reasons] : [];
  const hasLegend =
    onPage.length > 0 ||
    readings.length > 0 ||
    unplaced > 0 ||
    unlocatedLines.length > 0 ||
    doubtPages.length > 0 ||
    lost > 0;
  const chosenValue = chosen ? valueOf(chosen) : null;

  const chosenDoubt = chosen ? doubtOf.get(chosen.id) : undefined;

  // Fix mode: a click, tap or drag on the page proposes a mark (viewer.md "Fix mode").
  const fixing = fixMode && onAddMark !== undefined;
  const at = (clientX: number, clientY: number): [number, number] | null => {
    const r = scroll.current?.querySelector('.vw-frame')?.getBoundingClientRect();
    return r && r.width > 0 && r.height > 0
      ? [clamp01((clientX - r.left) / r.width), clamp01((clientY - r.top) / r.height)]
      : null;
  };
  const draftBox = (d: Drag, to: [number, number]): Box => [
    round5(Math.min(d.x, to[0])),
    round5(Math.min(d.y, to[1])),
    round5(Math.max(d.x, to[0])),
    round5(Math.max(d.y, to[1])),
  ];
  const draft = drag?.to ? draftBox(drag, drag.to) : null;

  return (
    <figure
      className="vw"
      onKeyDown={(e) => {
        if (e.key !== 'Escape') return;
        setTip(null);
        if (drag) setDrag(null);
        else onSelect?.(null);
      }}
    >
      <p className="vw-name">{file}</p>
      {classes.length > 0 && (
        <ul className="vw-classes">
          {classes.map((e) => (
            <li key={e.label}>
              {e.label.toUpperCase()} · {e.count}
            </li>
          ))}
        </ul>
      )}
      <div className="vw-bar">
        {pages.length > 1 && (
          <div className="vw-switcher">
            <button
              type="button"
              aria-label="Previous page"
              disabled={index === 0}
              onClick={() => {
                setCurrent(pages[index - 1]?.page);
              }}
            >
              ‹
            </button>
            <span>
              Page {index + 1} of {pages.length} · {countText(onPage.length)}
              {doubtPages.length > 0 && ` · ${String(doubtPages.length)} to double-check`}
            </span>
            <button
              type="button"
              aria-label="Next page"
              disabled={index === pages.length - 1}
              onClick={() => {
                setCurrent(pages[index + 1]?.page);
              }}
            >
              ›
            </button>
          </div>
        )}
        <div className="vw-zoom">
          <button
            type="button"
            aria-label="Zoom out"
            disabled={zoom === 1}
            onClick={() => {
              setZoom(zoom === 4 ? 2 : 1);
            }}
          >
            −
          </button>
          <span>{zoom * 100}%</span>
          <button
            type="button"
            aria-label="Zoom in"
            disabled={zoom === 4}
            onClick={() => {
              setZoom(zoom === 1 ? 2 : 4);
            }}
          >
            +
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(1);
            }}
          >
            Fit
          </button>
        </div>
      </div>
      {fixing && (
        <p className="vw-hint">
          <span className="vw-hint-wide">Click or drag on the drawing where a mark is missing</span>
          <span className="vw-hint-narrow">Tap the drawing where a mark is missing</span>
        </p>
      )}
      <div
        className="vw-scroll"
        ref={scroll}
        onPointerDown={
          fixing
            ? (e) => {
                if (e.button !== 0 || (e.target as Element).closest('.vw-badge, .vw-q')) return;
                const p0 = at(e.clientX, e.clientY);
                if (!p0) return;
                const touch = e.pointerType === 'touch';
                // shortcut: no capture in jsdom; a mouse released outside the box ends the drag on return
                if (!touch && 'setPointerCapture' in e.currentTarget)
                  e.currentTarget.setPointerCapture(e.pointerId);
                setDrag({ x: p0[0], y: p0[1], cx: e.clientX, cy: e.clientY, touch, to: null });
              }
            : undefined
        }
        onPointerMove={
          drag && !drag.touch
            ? (e) => {
                const to = at(e.clientX, e.clientY);
                if (to) setDrag({ ...drag, to });
              }
            : undefined
        }
        onPointerUp={
          drag && onAddMark
            ? (e) => {
                setDrag(null);
                const moved = Math.max(
                  Math.abs(e.clientX - drag.cx),
                  Math.abs(e.clientY - drag.cy),
                );
                if (moved < SLOP) onAddMark(pickBox(page, drag.x, drag.y), page.page);
                else if (!drag.touch) {
                  const to = at(e.clientX, e.clientY);
                  if (to) onAddMark(draftBox(drag, to), page.page);
                } // a moving touch is a pan
              }
            : undefined
        }
      >
        <PageFrame
          zoom={zoom}
          className={onPick || fixing ? 'vw-picking' : undefined}
          onClick={
            onPick && !fixing
              ? (x, y, target) => {
                  if (!target.closest('.vw-badge')) onPick(page.page, pickBox(page, x, y));
                }
              : undefined
          }
          key={page.url}
          url={page.url}
          width={page.width}
          height={page.height}
          alt={`Page ${String(page.page)} of ${file}`}
          page={page.page}
        >
          {(onPage.length > 0 || tags.length > 0 || outlines.length > 0 || draft) && (
            <svg
              className="vw-overlay"
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <pattern id={hatch} width="0.02" height="0.02" patternUnits="userSpaceOnUse">
                  <line
                    className="vw-hatch"
                    x1="0"
                    y1="0.02"
                    x2="0.02"
                    y2="0"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                </pattern>
              </defs>
              {onPage.map((m) => {
                const colour = colourOf(m);
                const { line } = markLook(m.state);
                const hot = m.id === highlighted || m.id === selected;
                const common = {
                  className: 'vw-shape',
                  style: tint(colour),
                  strokeWidth: hot ? 4 : 2,
                  strokeDasharray: DASH[line],
                  vectorEffect: 'non-scaling-stroke',
                  onClick: onPick || fixing ? undefined : () => onSelect?.(m.id),
                } as const;
                const hatched = line === 'hatched' ? `url(#${hatch})` : undefined;
                const [x0, y0, x1, y1] = m.box;
                const cross =
                  m.state === 'rejected' &&
                  [
                    [x0, y0, x1, y1],
                    [x0, y1, x1, y0],
                  ].map(([ax, ay, bx, by], i) => (
                    <line
                      key={`${m.id}-x${String(i)}`}
                      className="vw-cross"
                      style={tint(colour)}
                      x1={ax}
                      y1={ay}
                      x2={bx}
                      y2={by}
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                    />
                  ));
                return [
                  m.polygon ? (
                    <polygon
                      key={m.id}
                      points={m.polygon.map(([x, y]) => `${String(x)},${String(y)}`).join(' ')}
                      fill={hatched}
                      fillOpacity={m.state === 'rejected' ? 0 : line === 'hatched' ? 1 : 0.25}
                      {...common}
                    />
                  ) : (
                    <rect
                      key={m.id}
                      x={x0}
                      y={y0}
                      width={x1 - x0}
                      height={y1 - y0}
                      fill={hatched ?? 'none'}
                      {...common}
                    />
                  ),
                  cross,
                ];
              })}
              {onPage.map((m, i) => {
                const spot = spots?.[i];
                if (!spot?.leader) return null;
                const [x0, y0, x1, y1] = m.box;
                return (
                  <line
                    key={`${m.id}-leader`}
                    className="vw-leader"
                    style={tint(colourOf(m))}
                    x1={(x0 + x1) / 2}
                    y1={(y0 + y1) / 2}
                    x2={spot.x / W}
                    y2={spot.y / H}
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
              {tags.map((r) => {
                const [x0, y0, x1, y1] = r.box ?? [0, 0, 0, 0];
                return (
                  <rect
                    key={r.tag}
                    className="vw-reading"
                    x={x0}
                    y={y0}
                    width={x1 - x0}
                    height={y1 - y0}
                    fill="none"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
              {outlines.map(([x0, y0, x1, y1], i) => {
                // 4 px outside the box once the frame is measured
                const dx = W > 0 ? 4 / W : 0.006;
                const dy = H > 0 ? 4 / H : 0.006;
                return (
                  <rect
                    key={`d${String(i)}`}
                    className="vw-dispute"
                    x={x0 - dx}
                    y={y0 - dy}
                    width={x1 - x0 + 2 * dx}
                    height={y1 - y0 + 2 * dy}
                    strokeWidth={2}
                    strokeDasharray="2 3"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
              {draft && (
                <rect
                  className="vw-draft"
                  x={draft[0]}
                  y={draft[1]}
                  width={draft[2] - draft[0]}
                  height={draft[3] - draft[1]}
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  vectorEffect="non-scaling-stroke"
                />
              )}
            </svg>
          )}
          {tags.map((r) => (
            // shortcut: at the box's top-left corner, not its centre (viewer.md VW-19), so tag A
            // does not cover the room's badge; the spec should follow.
            <span
              key={r.tag}
              className="vw-tag"
              aria-hidden="true"
              style={{
                left: `${((r.box?.[0] ?? 0) * 100).toFixed(1)}%`,
                top: `${((r.box?.[1] ?? 0) * 100).toFixed(1)}%`,
              }}
            >
              {r.tag}
            </span>
          ))}
          {onPage.map((m, i) => {
            const [x0, y0, x1, y1] = m.box;
            const spot = spots?.[i];
            if (spot === null) return null; // no free spot: counted in the legend
            const value = valueOf(m);
            const name = `${m.label ?? 'item'}, ${words(m)}`;
            const isSelected = m.id === selected;
            const doubt = doubtOf.get(m.id);
            const whyId = `${uid}-why-${m.id}`;
            const where = spotStyle(spot, [x0, y0, x1, y1], W, H);
            const show = (on: boolean) => {
              onHover?.(on ? m.id : null);
              if (doubt !== undefined) setTip(on ? m.id : null);
            };
            return [
              <button
                key={m.id}
                type="button"
                className={`vw-badge vw-badge--${open(m) ? 'open' : 'filled'} vw-badge--${m.state}${m.id === highlighted ? ' vw-hot' : ''}${doubt === undefined ? '' : ' vw-badge--disputed'}`}
                aria-label={m.n === null ? name : `Mark ${String(m.n)}: ${name}`}
                aria-describedby={doubt === undefined ? undefined : whyId}
                aria-pressed={isSelected}
                style={{ ...where, ...tint(colourOf(m)) }}
                onClick={() => onSelect?.(m.id)}
                onPointerEnter={() => {
                  show(true);
                }}
                onPointerLeave={() => {
                  show(false);
                }}
                onFocus={() => {
                  show(true);
                }}
                onBlur={() => {
                  show(false);
                }}
              >
                {spot ? spot.text : value === null ? badgeText(m) : `${badgeText(m)} · ${value}`}
                {doubt !== undefined && (
                  <span className="vw-q-tag" aria-hidden="true">
                    ?
                  </span>
                )}
              </button>,
              doubt !== undefined && (
                <span key={`${m.id}-why`} id={whyId} className="vw-sr">
                  {ask(doubt)}
                </span>
              ),
              tip === m.id && doubt !== undefined && whyTip(doubt, where),
            ];
          })}
          {boxesHere.map((b, i) => {
            const spot = spots?.[onPage.length + i];
            if (spot === null) return null;
            const key = `box-${String(i)}`;
            const where = spotStyle(spot, b.box, W, H);
            return [
              <button
                key={key}
                type="button"
                className="vw-q"
                aria-label={ask(b.why)}
                style={where}
                onClick={() => {
                  setTip(tip === key ? null : key);
                }}
                onPointerEnter={() => {
                  setTip(key);
                }}
                onPointerLeave={() => {
                  setTip(null);
                }}
                onFocus={() => {
                  setTip(key);
                }}
                onBlur={() => {
                  setTip(null);
                }}
              >
                ?
              </button>,
              tip === key && whyTip(b.why, where),
            ];
          })}
        </PageFrame>
      </div>
      <Credit credit={credit} />
      <p className="vw-pagemeta">
        {pageMeta.map((text) => `${text} · `)}
        Page {page.page}
        {note && ' · '}
        {note && <span className="vw-note">{note}</span>}
        {meta && ` · ${meta}`}
      </p>
      {chosen && (
        <p className="vw-selection">
          {badgeText(chosen)} · {chosen.label ?? 'item'} ·{' '}
          {chosenValue === null ? '' : `${chosenValue} · `}
          {words(chosen)}
          {chosenDoubt !== undefined && ` · ${ask(chosenDoubt)}`}
        </p>
      )}
      {hasLegend && (
        <figcaption className="vw-legend">
          <ul>
            {states.map((s) => (
              <li key={s}>
                <i className={`vw-swatch vw-swatch--${s}`} aria-hidden="true" />
                {s === 'excluded' && oneReason ? `${oneReason}, ${STATE_WORDS[s]}` : STATE_WORDS[s]}
              </li>
            ))}
            {onPage.length > 0 &&
              legend?.map((e) => (
                <li key={e.label}>
                  <i className="vw-swatch" style={tint(safeColour(e.colour))} aria-hidden="true" />
                  {e.label}
                  {e.note && <span className="vw-note"> · {e.note}</span>}
                </li>
              ))}
            {unlocatedLines.map(([cls, k]) => (
              <li key={`u-${cls}`}>
                {k} {cls} counted without a mark
              </li>
            ))}
            {readings.map((r) => (
              <li key={`r-${r.tag}`}>
                {r.tag}: {methodName(r.method)} read {formatValue(r.value, r.unit ?? unit)}
              </li>
            ))}
            {doubtsHere > 0 && (
              <li>
                <i className="vw-swatch vw-swatch--doubt" aria-hidden="true" />
                {doubtsHere} to double-check
              </li>
            )}
            {elsewhere.map((p) => (
              <li key={`d-${String(p)}`}>
                {doubtPages.filter((q) => q === p).length} to double-check on page {p}
              </li>
            ))}
            {lost > 0 && <li>{lost} place(s) to double-check could not be shown</li>}
            {unplaced > 0 && <li>{unplaced} mark(s) could not be placed</li>}
            {noRoom > 0 && <li>{noRoom} label(s) had no room on the page</li>}
          </ul>
        </figcaption>
      )}
    </figure>
  );
}
