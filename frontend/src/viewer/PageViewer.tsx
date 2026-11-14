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
  prefix?: string; // default "Please double-check"; an issue's severity in words
  tag?: string; // default "?"; an issue's row number
}

/** A check outcome for one mark (viewer.md "Checks and issues"). */
// needs_person / note: an issue's severity (issues screen), next to a check's outcomes.
export type Tone = 'fail' | 'cannot_tell' | 'pass' | 'counted' | 'needs_person' | 'note';
const TONE_ORDER: Tone[] = ['fail', 'needs_person', 'cannot_tell', 'note', 'pass', 'counted'];
const TONE_COLOUR: Record<Tone, string> = {
  fail: 'var(--v-danger)',
  cannot_tell: 'var(--v-warn)',
  pass: 'var(--v-ok)',
  counted: 'var(--v-muted)',
  needs_person: 'var(--v-warn)',
  note: 'var(--v-muted)',
};
const TONE_DASH: Record<Tone, string | undefined> = {
  fail: undefined,
  cannot_tell: '6 3',
  pass: undefined,
  counted: '2 3',
  needs_person: '6 3',
  note: undefined,
};
const TONE_WORDS: Record<Tone, string> = {
  fail: 'fails the rule',
  cannot_tell: 'cannot tell',
  pass: 'passes',
  counted: 'counted for the rule',
  needs_person: 'needs a person',
  note: 'note',
};
const PLURAL: Partial<Record<Tone, string>> = {
  fail: 'fail the rule',
  pass: 'pass',
  note: 'notes',
};
const toneCount = (t: Tone, k: number) => `${String(k)} ${(k !== 1 && PLURAL[t]) || TONE_WORDS[t]}`;
type Focus = { page: number; box?: number[] | null; polygon?: [number, number][] | null };

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
  tones?: Record<string, Tone> | null; // mark id → check outcome; replaces that mark's state look
  disputedLegend?: string; // legend count words for `disputed`; default "to double-check"
  focus?: Focus | null; // jump-to-place: open the page, zoom and scroll to the box
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
const ask = (why: string, prefix = 'Please double-check') => `${prefix}: ${why}`;

type Zoom = 1 | 2 | 4;

const NARROW = 600; // px of frame width under which badges show their number only
const STATE_ORDER: MarkView['state'][] = ['counted', 'added', 'rejected', 'excluded'];
const inPage = (v: number) => v >= 0 && v <= 1;
/** A box in page fractions: four numbers in 0..1, x0 <= x1, y0 <= y1. */
const isBox = (b: number[] | null | undefined): b is Box =>
  b?.length === 4 &&
  b.every(inPage) &&
  Number(b[0]) <= Number(b[2]) &&
  Number(b[1]) <= Number(b[3]);

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

/** Scroll so the box's centre is in the middle of the scroll box, at zoom `z` (viewer.md "Focus"). */
function scrollToBox(el: HTMLDivElement, z: number, b: Box, pg: { width: number; height: number }) {
  if (!('scrollTo' in el)) return;
  const fw = el.clientWidth * z; // the frame is the scroll box wide at 100 %
  const fh = (fw * pg.height) / pg.width;
  el.scrollTo({
    left: Math.max(0, ((b[0] + b[2]) / 2) * fw - el.clientWidth / 2),
    top: Math.max(0, ((b[1] + b[3]) / 2) * fh - el.clientHeight / 2),
  });
}

/** The why of a disputed place, next to its badge; below it when the badge is near the top. */
function whyTip(text: string, where: CSSProperties) {
  const below = parseFloat(String(where.top)) < 20;
  return (
    <span
      key="why-tip"
      role="tooltip"
      className={below ? 'vw-why vw-why--below' : 'vw-why'}
      style={{ left: where.left, top: where.top }}
    >
      {text}
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
  tones,
  disputedLegend = 'to double-check',
  focus,
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
  // The focused place stays centred through resizes (rotation, URL bar) until the user moves the plan.
  const kept = useRef<{ box: Box; page: PageView; moved: boolean } | null>(null);
  const zoomNow = useRef<number>(1);
  useLayoutEffect(() => {
    const el = scroll.current;
    if (!el) return;
    const measure = () => {
      setFrameWidth(el.clientWidth);
      const k = kept.current;
      if (k && !k.moved) scrollToBox(el, zoomNow.current, k.box, k.page);
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
  // A new focus (by value) opens its page; it wins over a selection made in the same render.
  const focusKey = focus
    ? JSON.stringify([focus.page, focus.box ?? null, focus.polygon ?? null])
    : '';
  const [lastFocus, setLastFocus] = useState('');
  if (focusKey !== lastFocus) {
    setLastFocus(focusKey);
    if (focus && pages.some((p) => p.page === focus.page)) setCurrent(focus.page);
  }
  // waits for its zoom to render
  const pendingScroll = useRef<{ box: Box; zoom: Zoom; page: PageView | null } | null>(null);
  // Zoom so a small box is readable, then scroll its centre to the middle (viewer.md "Focus").
  useLayoutEffect(() => {
    const el = scroll.current;
    const b = focus?.box;
    kept.current = null;
    if (!el || !focus || !pages.some((p) => p.page === focus.page) || !isBox(b)) return;
    const px = (b[2] - b[0]) * el.clientWidth; // the box's width at 100 %: the frame is the scroll box wide
    const z: Zoom = px >= 48 ? zoom : px * 2 < 24 ? 4 : 2;
    const pg = pages.find((p) => p.page === focus.page);
    pendingScroll.current = { box: b, zoom: z, page: pg ?? null };
    if (z !== zoom) setZoom(z);
    else if (pg) {
      pendingScroll.current = null;
      scrollToBox(el, z, b, pg);
      kept.current = { box: b, page: pg, moved: false };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per new focus value
  }, [focusKey]);
  useLayoutEffect(() => {
    zoomNow.current = zoom;
    const p = pendingScroll.current;
    if (!scroll.current || p?.zoom !== zoom || !p.page) return;
    pendingScroll.current = null;
    scrollToBox(scroll.current, zoom, p.box, p.page);
    kept.current = { box: p.box, page: p.page, moved: false };
  }, [zoom]);
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
  const toneOf = (m: MarkView): Tone | undefined => tones?.[m.id];
  const said = (m: MarkView) => {
    const t = toneOf(m);
    return t ? TONE_WORDS[t] : words(m);
  };
  // Counted marks of a check are context: a shape, no badge (viewer.md OP 17).
  const badged = onPage.filter((m) => toneOf(m) !== 'counted');
  const colourOf = (m: MarkView) => {
    const t = toneOf(m);
    return t ? TONE_COLOUR[t] : stateColour(m);
  };
  const stateColour = (m: MarkView) =>
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
  const doubtOf = new Map<string, Disputed>(); // mark id → its disputed item
  const boxItems: (Disputed & { box: Box; page: number })[] = [];
  let lost = 0;
  for (const d of disputed ?? []) {
    if (d.markId) {
      const m = marks.find((k) => k.id === d.markId);
      if (m && placed(m)) doubtOf.set(m.id, d);
      else lost++;
    } else {
      const p = d.page ?? page.page;
      if (isBox(d.box) && pages.some((q) => q.page === p))
        boxItems.push({ ...d, box: d.box, page: p });
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
  const focusHere = focus?.page === page.page ? focus : null;
  const focusMissing = focus && !pages.some((p) => p.page === focus.page) ? focus.page : null;
  // Badges are placed so no two overlap once the frame's width is known (R2-qa-1-3).
  const W = frameWidth * zoom;
  const H = (W * page.height) / page.width;
  const narrow = W < NARROW;
  const spots =
    W > 0
      ? placeLabels(
          [
            ...badged.map((m) => {
              const value = valueOf(m);
              return {
                box: m.box,
                full: value !== null && !narrow ? `${badgeText(m)} · ${value}` : badgeText(m),
                short: badgeText(m),
              };
            }),
            ...boxesHere.map((b) => ({ box: b.box, full: b.tag ?? '?', short: b.tag ?? '?' })),
          ],
          W,
          H,
        )
      : null;
  const noRoom = spots?.filter((p) => p === null).length ?? 0;
  // Legend mode: with `tones`, one item per check outcome instead of the state items (VW-73).
  const toned = tones ? onPage.filter((m) => toneOf(m) !== undefined) : [];
  const toneItems = TONE_ORDER.map(
    (t) => [t, toned.filter((m) => toneOf(m) === t).length] as const,
  ).filter(([, k]) => k > 0);
  const states = STATE_ORDER.filter((s) =>
    onPage.some((m) => m.state === s && toneOf(m) === undefined),
  );
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
    lost > 0 ||
    focusMissing !== null;
  const chosenValue = chosen ? valueOf(chosen) : null;

  const chosenDoubt = chosen ? doubtOf.get(chosen.id) : undefined;
  const drawOrder = [...onPage].sort(
    (a, b) => Number(toneOf(b) === 'counted') - Number(toneOf(a) === 'counted'),
  );

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
  // Any pointer, wheel or key input on the viewer ends the kept focus (VW-80).
  const moved = () => {
    if (kept.current) kept.current.moved = true;
  };

  return (
    <figure
      className="vw"
      onPointerDownCapture={moved}
      onWheelCapture={moved}
      onKeyDown={(e) => {
        moved();
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
              {doubtPages.length > 0 && ` · ${String(doubtPages.length)} ${disputedLegend}`}
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
          {(onPage.length > 0 || tags.length > 0 || outlines.length > 0 || draft || focusHere) && (
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
              {drawOrder.map((m) => {
                const colour = colourOf(m);
                const tone = toneOf(m);
                const { line } = markLook(m.state);
                const hot = m.id === highlighted || m.id === selected;
                const common = {
                  className: tone ? `vw-shape vw-shape--${tone}` : 'vw-shape',
                  style: tint(colour),
                  strokeWidth: hot ? 4 : tone === 'counted' ? 1 : 2,
                  strokeDasharray: tone ? TONE_DASH[tone] : DASH[line],
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
                      fill={tone === 'pass' || tone === 'counted' ? 'none' : hatched}
                      fillOpacity={
                        tone === 'fail'
                          ? 0.2
                          : tone === 'cannot_tell'
                            ? 0.4
                            : m.state === 'rejected'
                              ? 0
                              : line === 'hatched'
                                ? 1
                                : 0.25
                      }
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
              {badged.map((m, i) => {
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
              {focusHere &&
                (focusHere.polygon ? (
                  <polygon
                    className="vw-focus"
                    points={focusHere.polygon
                      .map(([x, y]) => `${String(x)},${String(y)}`)
                      .join(' ')}
                    fill="none"
                    strokeWidth={3}
                    vectorEffect="non-scaling-stroke"
                  />
                ) : (
                  isBox(focusHere.box) &&
                  (() => {
                    const [x0, y0, x1, y1] = focusHere.box;
                    const dx = W > 0 ? 6 / W : 0.01; // 6 px outside the box
                    const dy = H > 0 ? 6 / H : 0.01;
                    return (
                      <rect
                        className="vw-focus"
                        x={x0 - dx}
                        y={y0 - dy}
                        width={x1 - x0 + 2 * dx}
                        height={y1 - y0 + 2 * dy}
                        fill="none"
                        strokeWidth={3}
                        vectorEffect="non-scaling-stroke"
                      />
                    );
                  })()
                ))}
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
          {badged.map((m, i) => {
            const [x0, y0, x1, y1] = m.box;
            const spot = spots?.[i];
            if (spot === null) return null; // no free spot: counted in the legend
            const value = valueOf(m);
            const tone = toneOf(m);
            const name = `${m.label ?? 'item'}, ${said(m)}`;
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
                className={`vw-badge ${tone ? `vw-badge--${tone}` : `vw-badge--${open(m) ? 'open' : 'filled'} vw-badge--${m.state}`}${m.id === highlighted ? ' vw-hot' : ''}${doubt === undefined ? '' : ' vw-badge--disputed'}`}
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
                    {doubt.tag ?? '?'}
                  </span>
                )}
              </button>,
              doubt !== undefined && (
                <span key={`${m.id}-why`} id={whyId} className="vw-sr">
                  {ask(doubt.why, doubt.prefix)}
                </span>
              ),
              tip === m.id && doubt !== undefined && whyTip(ask(doubt.why, doubt.prefix), where),
            ];
          })}
          {boxesHere.map((b, i) => {
            const spot = spots?.[badged.length + i];
            if (spot === null) return null;
            const key = `box-${String(i)}`;
            const where = spotStyle(spot, b.box, W, H);
            return [
              <button
                key={key}
                type="button"
                className="vw-q"
                aria-label={ask(b.why, b.prefix)}
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
                {b.tag ?? '?'}
              </button>,
              tip === key && whyTip(ask(b.why, b.prefix), where),
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
          {said(chosen)}
          {chosenDoubt !== undefined && ` · ${ask(chosenDoubt.why, chosenDoubt.prefix)}`}
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
            {toneItems.map(([t, k]) => (
              <li key={`t-${t}`}>
                <i className={`vw-swatch vw-swatch--${t}`} aria-hidden="true" />
                {toneCount(t, k)}
              </li>
            ))}
            {onPage.length > 0 &&
              !tones &&
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
                {doubtsHere} {disputedLegend}
              </li>
            )}
            {elsewhere.map((p) => (
              <li key={`d-${String(p)}`}>
                {doubtPages.filter((q) => q === p).length} {disputedLegend} on page {p}
              </li>
            ))}
            {lost > 0 && (
              <li>
                {disputedLegend === 'to double-check'
                  ? `${String(lost)} place(s) to double-check could not be shown`
                  : `${String(lost)} ${disputedLegend} could not be shown on the drawing`}
              </li>
            )}
            {focusMissing !== null && (
              <li>That place is on page {focusMissing}, which this drawing does not have</li>
            )}
            {unplaced > 0 && <li>{unplaced} mark(s) could not be placed</li>}
            {noRoom > 0 && <li>{noRoom} label(s) had no room on the page</li>}
          </ul>
        </figcaption>
      )}
    </figure>
  );
}
