import { useId, useLayoutEffect, useRef, useState } from 'react';
import type { AnswerView, MarkView, PageView, QuantityConflict } from '../api/types';
import { formatValue, methodName } from '../api/format';
import { Credit } from '../shell/Credit';
import { PageFrame } from './PageFrame';
import {
  badgeText,
  DASH,
  GREY,
  INK,
  markLook,
  normalisedNote,
  pickBox,
  placeLabels,
  safeColour,
  startPage,
  STATE_WORDS,
} from './marks';
import './viewer.css';

type LegendEntry = NonNullable<AnswerView['proof']>['legend'][number];

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
}

type Zoom = 1 | 2 | 4;

const WARN = '#9a5b00';
const NARROW = 600; // px of frame width under which badges show their number only
const STATE_ORDER: MarkView['state'][] = ['counted', 'added', 'rejected', 'excluded'];
const inPage = (v: number) => v >= 0 && v <= 1;

const countText = (k: number) => `${String(k)} mark${k === 1 ? '' : 's'}`;

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
}: PageViewerProps) {
  const hatch = `vw-hatch-${useId().replace(/[^\w-]/g, '')}`;
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
    m.state === 'excluded'
      ? GREY
      : // one entry (a room count's "room"): every mark takes it, as evidence_render.py does
        safeColour(
          (legend?.length === 1 ? legend[0] : legend?.find((e) => e.label === m.label))?.colour,
        );
  const showValue = unit !== null && unit !== 'count';
  const valueOf = (m: MarkView) =>
    showValue && m.value !== null && (m.state === 'counted' || m.state === 'added')
      ? formatValue(m.value, unit)
      : null;
  // Badges are placed so no two overlap once the frame's width is known (R2-qa-1-3).
  const W = frameWidth * zoom;
  const H = (W * page.height) / page.width;
  const narrow = W < NARROW;
  const spots =
    W > 0
      ? placeLabels(
          onPage.map((m) => {
            const value = valueOf(m);
            return {
              box: m.box,
              full: value !== null && !narrow ? `${badgeText(m)} · ${value}` : badgeText(m),
              short: badgeText(m),
            };
          }),
          W,
          H,
        )
      : null;
  const noRoom = spots?.filter((p) => p === null).length ?? 0;
  const states = STATE_ORDER.filter((s) => onPage.some((m) => m.state === s));
  const unlocatedLines = Object.entries(unlocated ?? {}).filter(([, k]) => k > 0);
  const chosen = onPage.find((m) => m.id === selected);
  const note = normalisedNote(page.normalised);
  const hasLegend =
    onPage.length > 0 || readings.length > 0 || unplaced > 0 || unlocatedLines.length > 0;
  const chosenValue = chosen ? valueOf(chosen) : null;

  return (
    <figure
      className="vw"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onSelect?.(null);
      }}
    >
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
      <div className="vw-scroll" ref={scroll}>
        <PageFrame
          zoom={zoom}
          className={onPick ? 'vw-picking' : undefined}
          onClick={
            onPick &&
            ((x, y, target) => {
              if (!target.closest('.vw-badge')) onPick(page.page, pickBox(page, x, y));
            })
          }
          key={page.url}
          url={page.url}
          width={page.width}
          height={page.height}
          alt={`Page ${String(page.page)} of ${file}`}
          page={page.page}
        >
          {(onPage.length > 0 || tags.length > 0) && (
            <svg
              className="vw-overlay"
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <pattern id={hatch} width="0.02" height="0.02" patternUnits="userSpaceOnUse">
                  <line
                    x1="0"
                    y1="0.02"
                    x2="0.02"
                    y2="0"
                    stroke={GREY}
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
                  stroke: colour,
                  strokeWidth: hot ? 4 : 2,
                  strokeDasharray: DASH[line],
                  vectorEffect: 'non-scaling-stroke',
                  onClick: onPick ? undefined : () => onSelect?.(m.id),
                } as const;
                const fill = line === 'hatched' ? `url(#${hatch})` : colour;
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
                      x1={ax}
                      y1={ay}
                      x2={bx}
                      y2={by}
                      stroke={colour}
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                    />
                  ));
                return [
                  m.polygon ? (
                    <polygon
                      key={m.id}
                      points={m.polygon.map(([x, y]) => `${String(x)},${String(y)}`).join(' ')}
                      fill={fill}
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
                      fill={line === 'hatched' ? fill : 'none'}
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
                    x1={(x0 + x1) / 2}
                    y1={(y0 + y1) / 2}
                    x2={spot.x / W}
                    y2={spot.y / H}
                    stroke={colourOf(m)}
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
                    stroke={WARN}
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
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
            return (
              <button
                key={m.id}
                type="button"
                className={m.id === highlighted ? 'vw-badge vw-hot' : 'vw-badge'}
                aria-label={m.n === null ? name : `Mark ${String(m.n)}: ${name}`}
                aria-pressed={isSelected}
                style={{
                  ...(spot
                    ? {
                        left: `${((spot.x / W) * 100).toFixed(3)}%`,
                        top: `${((spot.y / H) * 100).toFixed(3)}%`,
                        width: `${String(spot.w)}px`,
                        height: `${String(spot.h)}px`,
                      }
                    : {
                        left: `${(((x0 + x1) / 2) * 100).toFixed(1)}%`,
                        top: `${(((y0 + y1) / 2) * 100).toFixed(1)}%`,
                      }),
                  background: isSelected ? INK : '#fff',
                  color: isSelected ? '#fff' : INK,
                  borderColor: colourOf(m),
                }}
                onClick={() => onSelect?.(m.id)}
                onPointerEnter={() => onHover?.(m.id)}
                onPointerLeave={() => onHover?.(null)}
                onFocus={() => onHover?.(m.id)}
                onBlur={() => onHover?.(null)}
              >
                {spot ? spot.text : value === null ? badgeText(m) : `${badgeText(m)} · ${value}`}
              </button>
            );
          })}
        </PageFrame>
      </div>
      <Credit credit={credit} />
      {hasLegend && (
        <ul className="vw-legend">
          {states.map((s) => (
            <li key={s}>{STATE_WORDS[s]}</li>
          ))}
          {onPage.length > 0 &&
            legend?.map((e) => (
              <li key={e.label}>
                <i
                  className="vw-swatch"
                  style={{ background: safeColour(e.colour) }}
                  aria-hidden="true"
                />
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
          {unplaced > 0 && <li>{unplaced} mark(s) could not be placed</li>}
          {noRoom > 0 && <li>{noRoom} label(s) had no room on the page</li>}
        </ul>
      )}
      {chosen && (
        <p className="vw-selection">
          {badgeText(chosen)} · {chosen.label ?? 'item'} ·{' '}
          {chosenValue === null ? '' : `${chosenValue} · `}
          {words(chosen)}
        </p>
      )}
      <figcaption className="vw-caption">
        {file}
        {note && ' · '}
        {note && <span className="vw-note">{note}</span>}
      </figcaption>
    </figure>
  );
}
