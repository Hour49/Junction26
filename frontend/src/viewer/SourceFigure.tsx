import { useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PageView } from '../api/types';
import { pickWidth } from './marks';
import './viewer.css';

// "Show source" and the preview's Close: the accent on its soft tint.
const soft = {
  variant: 'secondary',
  size: 'pill',
  className: 'bg-accent px-[18px] text-sm text-primary hover:bg-border hover:text-foreground',
} as const;

type Box = [number, number, number, number]; // page fractions [x0, y0, x1, y1]

export interface Place {
  label: string; // the legend line, plain words, built by the screen
  box?: Box | null; // absent/null: in the legend, not outlined
  polygon?: [number, number][] | null; // page fractions; drawn instead of the box
}

export interface Source {
  name: string;
  page: PageView | null; // null: `image` if given, else "No picture of this file"
  image?: string | null; // a picture URL for a source with no drawing page; never outlined
  places: Place[]; // numbered across all sources in order
}

export interface SourceFigureProps {
  sources: Source[];
  label: string;
  defaultOpen?: boolean;
}

export interface SourcePreviewProps {
  sources: Source[];
  start?: number;
  onClose: () => void;
}

/** A place's outline bounds, or null when it has no position. */
function boundsOf(p: Place): Box | null {
  if (p.polygon?.length) {
    const xs = p.polygon.map((q) => q[0]);
    const ys = p.polygon.map((q) => q[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  return p.box ?? null;
}

const clamp = (v: number) => Math.min(1, Math.max(0, v));

/** The part of the page to show inline: the places' union padded by max(half its size, 0.08), else the page. */
export function cropOf(places: readonly Place[]): Box {
  const boxes = places.map(boundsOf).filter((b): b is Box => b !== null);
  if (!boxes.length) return [0, 0, 1, 1];
  const x0 = Math.min(...boxes.map((b) => b[0]));
  const y0 = Math.min(...boxes.map((b) => b[1]));
  const x1 = Math.max(...boxes.map((b) => b[2]));
  const y1 = Math.max(...boxes.map((b) => b[3]));
  const px = Math.max((x1 - x0) / 2, 0.08);
  const py = Math.max((y1 - y0) / 2, 0.08);
  return [clamp(x0 - px), clamp(y0 - py), clamp(x1 + px), clamp(y1 + py)];
}

/** Per disc, how many 24 px steps right it moves so no two 20 px discs overlap (anchors in px). */
export function stackOf(anchors: readonly ([number, number] | null)[]): number[] {
  const placed: [number, number][] = [];
  return anchors.map((a) => {
    if (!a) return 0;
    let k = 0;
    const hits = (x: number) =>
      placed.some(([px, py]) => Math.abs(px - x) < 22 && Math.abs(py - a[1]) < 22);
    while (hits(a[0] + k * 24)) k += 1;
    placed.push([a[0] + k * 24, a[1]]);
    return k;
  });
}

/** Each source's first place number (figure-wide numbering). */
const firstNumbers = (sources: readonly Source[]) =>
  sources.map((_, i) => 1 + sources.slice(0, i).reduce((n, s) => n + s.places.length, 0));

const pct = (v: number) => `${(v * 100).toFixed(4)}%`;

/** One page image cut to `crop`, with the places outlined and numbered from `first`. */
function SourceImage({
  source,
  first,
  crop,
  numbered = true,
}: {
  source: Source;
  first: number;
  crop: Box;
  numbered?: boolean; // false: outlines only (a crowded minimized thumbnail, VW-100)
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [cssWidth, setCssWidth] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const [x0, y0, x1, y1] = crop;
  const w = x1 - x0;
  const h = y1 - y0;
  useLayoutEffect(() => {
    setCssWidth(ref.current?.clientWidth ?? 0);
  }, []);
  const page = source.page;
  if (!page) {
    if (!source.image) return <span className="vw-src-none">No picture of this file</span>;
    return (
      <span ref={ref} className="vw-src-frame vw-src-frame--img">
        {failed ? (
          <span className="vw-src-none">Could not load the drawing</span>
        ) : (
          <img
            src={source.image}
            alt={source.name}
            onError={() => {
              setFailed(true);
            }}
          />
        )}
      </span>
    );
  }
  const src =
    cssWidth === null
      ? null
      : `${page.url}?width=${String(pickWidth(cssWidth / w, window.devicePixelRatio || 1, 1))}`;
  const at = (b: Box) => ({
    left: pct((b[0] - x0) / w),
    top: pct((b[1] - y0) / h),
    width: pct((b[2] - b[0]) / w),
    height: pct((b[3] - b[1]) / h),
  });
  const polys = source.places.filter((p) => p.polygon?.length);
  // before measuring (or in jsdom) only identical anchors count as touching
  const pxW = cssWidth || 0;
  const pxH = (pxW * h * page.height) / (w * page.width);
  const ks = stackOf(
    source.places.map((p) => {
      const b = boundsOf(p);
      return b ? [((b[0] - x0) / w) * pxW, ((b[1] - y0) / h) * pxH] : null;
    }),
  );
  return (
    <span
      ref={ref}
      className="vw-src-frame"
      style={{ aspectRatio: `${String(w * page.width)} / ${String(h * page.height)}` }}
    >
      {failed ? (
        <span className="vw-src-none">Could not load the drawing</span>
      ) : (
        src && (
          <img
            src={src}
            alt={source.name}
            loading="lazy"
            onError={() => {
              setFailed(true);
            }}
            style={{ left: pct(-x0 / w), top: pct(-y0 / h), width: pct(1 / w) }}
          />
        )
      )}
      {polys.length > 0 && (
        <svg
          className="vw-src-svg"
          viewBox={`${String(x0)} ${String(y0)} ${String(w)} ${String(h)}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {polys.map((p, i) => (
            <polygon
              key={i}
              className="vw-hl-poly"
              points={(p.polygon ?? []).map((q) => q.join(',')).join(' ')}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      )}
      {source.places.map((p, i) => {
        const b = boundsOf(p);
        if (!b) return null;
        return (
          <span
            key={i}
            className={p.polygon?.length ? 'vw-hl vw-hl--poly' : 'vw-hl'}
            style={{ ...at(b), '--vw-k': String(ks[i] ?? 0) } as CSSProperties}
            aria-hidden="true"
          >
            {numbered && <b>{first + i}</b>}
          </span>
        );
      })}
    </span>
  );
}

/** A minimized thumbnail numbers at most this many outlined places; above it, outlines and a count line (VW-100). */
export const THUMB_NUMBERS = 12;

/** A minimized figure lists this many places, then "and N more" (Expand or Show source lists them all). */
export const MIN_LEGEND = 3;

function Legend({ places, first, max }: { places: readonly Place[]; first: number; max?: number }) {
  if (!places.length) return null;
  const shown = max === undefined ? places : places.slice(0, max);
  const more = places.length - shown.length;
  return (
    <ol className="vw-hl-legend">
      {shown.map((p, i) => (
        <li key={i}>
          <b aria-hidden="true">{first + i}</b>
          <span>{p.label}</span>
        </li>
      ))}
      {more > 0 && <li className="pl-7">and {more} more</li>}
    </ol>
  );
}

/** The large source preview: whole page, same outlines, left/right between sources (viewer.md). */
export function SourcePreview({ sources, start = 0, onClose }: SourcePreviewProps) {
  const n = sources.length;
  const [at, setAt] = useState(start);
  const i = ((at % n) + n) % n;
  const source = sources[i] ?? { name: '', page: null, places: [] };
  const first = firstNumbers(sources)[i] ?? 1;
  const card = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    card.current?.querySelector<HTMLElement>('.vw-modal-close')?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = overflow;
    };
  }, []);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    else if (n > 1 && (e.key === 'ArrowLeft' || e.key === 'ArrowRight'))
      setAt(i + (e.key === 'ArrowLeft' ? -1 : 1));
    else if (e.key === 'Tab') {
      const items = [...(card.current?.querySelectorAll<HTMLElement>('button') ?? [])];
      const k = items.indexOf(document.activeElement as HTMLElement);
      const to = e.shiftKey ? (k <= 0 ? items.length - 1 : k - 1) : (k + 1) % items.length;
      e.preventDefault();
      items[to]?.focus();
    }
  };

  return createPortal(
    <div
      className="vw-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={card}
        className="vw-modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={`Source: ${source.name}`}
        onKeyDown={onKeyDown}
      >
        <div className="vw-modal-head">
          <span className="vw-modal-name">
            {source.name}
            {n > 1 && <span className="vw-modal-pos">{` · ${String(i + 1)} of ${String(n)}`}</span>}
          </span>
          <Button {...soft} className={cn(soft.className, 'vw-modal-close')} onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="vw-modal-view">
          <SourceImage key={i} source={source} first={first} crop={[0, 0, 1, 1]} />
          {n > 1 && (
            <>
              <Button
                variant="outline"
                size="pill-icon"
                className="vw-arrow vw-arrow--l border-0 bg-card"
                aria-label="Previous source"
                onClick={() => {
                  setAt(i - 1);
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M15 6l-6 6 6 6" />
                </svg>
              </Button>
              <Button
                variant="outline"
                size="pill-icon"
                className="vw-arrow vw-arrow--r border-0 bg-card"
                aria-label="Next source"
                onClick={() => {
                  setAt(i + 1);
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" />
                </svg>
              </Button>
            </>
          )}
        </div>
        <Legend places={source.places} first={first} />
      </div>
    </div>,
    document.body,
  );
}

/** A conflict's or issue's source drawing: minimized thumbnail + numbered legend (capped), Expand, Show source. */
export function SourceFigure({ sources, label, defaultOpen = false }: SourceFigureProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [preview, setPreview] = useState(false);
  const show = useRef<HTMLButtonElement>(null);
  const places = sources.flatMap((s) => s.places);
  const lead = sources[0];
  if (!lead) return null;
  const pictured = lead.page !== null || Boolean(lead.image);
  const outlined = lead.page ? lead.places.filter((p) => boundsOf(p) !== null).length : 0;
  const crowded = !open && outlined > THUMB_NUMBERS;
  const toggle = () => {
    setOpen((o) => !o);
  };
  return (
    <figure className={open ? 'vw-src' : 'vw-src vw-src--min'} aria-label={label}>
      {pictured ? (
        <div className="vw-src-thumbcol">
          <button
            type="button"
            className="vw-src-thumb"
            aria-expanded={open}
            aria-label={open ? 'Minimize the drawing' : 'Expand the drawing'}
            onClick={toggle}
          >
            <SourceImage
              key={String(open)}
              source={lead}
              first={1}
              crop={cropOf(lead.places)}
              numbered={!crowded}
            />
          </button>
          {crowded && (
            <p className="vw-many">{`${String(outlined)} marks, numbered when expanded`}</p>
          )}
        </div>
      ) : (
        <span className="vw-src-thumb vw-src-thumb--none">No picture of this file</span>
      )}
      {places.length > 0 && (
        <figcaption>
          <Legend places={places} first={1} max={open ? undefined : MIN_LEGEND} />
        </figcaption>
      )}
      <div className="vw-src-btns">
        {pictured && (
          <Button
            variant="secondary"
            size="pill"
            className="bg-[var(--v-grey)] px-[18px] text-sm font-medium hover:bg-border"
            aria-expanded={open}
            onClick={toggle}
          >
            {open ? 'Minimize' : 'Expand'}
          </Button>
        )}
        <Button
          ref={show}
          {...soft}
          onClick={() => {
            setPreview(true);
          }}
        >
          Show source
        </Button>
      </div>
      {preview && (
        <SourcePreview
          sources={sources}
          onClose={() => {
            setPreview(false);
            show.current?.focus();
          }}
        />
      )}
    </figure>
  );
}
