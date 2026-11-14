import { useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import type { PageView } from '../api/types';
import { pickWidth } from './marks';
import './viewer.css';

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

/** Each source's first place number (figure-wide numbering). */
const firstNumbers = (sources: readonly Source[]) =>
  sources.map((_, i) => 1 + sources.slice(0, i).reduce((n, s) => n + s.places.length, 0));

const pct = (v: number) => `${(v * 100).toFixed(4)}%`;

/** One page image cut to `crop`, with the places outlined and numbered from `first`. */
function SourceImage({ source, first, crop }: { source: Source; first: number; crop: Box }) {
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
            style={at(b)}
            aria-hidden="true"
          >
            <b>{first + i}</b>
          </span>
        );
      })}
    </span>
  );
}

function Legend({ places, first }: { places: readonly Place[]; first: number }) {
  if (!places.length) return null;
  return (
    <ol className="vw-hl-legend">
      {places.map((p, i) => (
        <li key={i}>
          <b aria-hidden="true">{first + i}</b>
          <span>{p.label}</span>
        </li>
      ))}
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
          <button
            type="button"
            className="v-btn v-btn--secondary v-press vw-btn-soft vw-modal-close"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="vw-modal-view">
          <SourceImage key={i} source={source} first={first} crop={[0, 0, 1, 1]} />
          {n > 1 && (
            <>
              <button
                type="button"
                className="v-btn v-btn--secondary v-btn--round vw-arrow vw-arrow--l"
                aria-label="Previous source"
                onClick={() => {
                  setAt(i - 1);
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M15 6l-6 6 6 6" />
                </svg>
              </button>
              <button
                type="button"
                className="v-btn v-btn--secondary v-btn--round vw-arrow vw-arrow--r"
                aria-label="Next source"
                onClick={() => {
                  setAt(i + 1);
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" />
                </svg>
              </button>
            </>
          )}
        </div>
        <Legend places={source.places} first={first} />
      </div>
    </div>,
    document.body,
  );
}

/** A conflict's or issue's source drawing: minimized thumbnail + numbered legend, Expand, Show source. */
export function SourceFigure({ sources, label, defaultOpen = false }: SourceFigureProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [preview, setPreview] = useState(false);
  const show = useRef<HTMLButtonElement>(null);
  const places = sources.flatMap((s) => s.places);
  const lead = sources[0];
  if (!lead) return null;
  const pictured = lead.page !== null || Boolean(lead.image);
  const toggle = () => {
    setOpen((o) => !o);
  };
  return (
    <figure className={open ? 'vw-src' : 'vw-src vw-src--min'} aria-label={label}>
      {pictured ? (
        <button
          type="button"
          className="vw-src-thumb"
          aria-expanded={open}
          aria-label={open ? 'Minimize the drawing' : 'Expand the drawing'}
          onClick={toggle}
        >
          <SourceImage key={String(open)} source={lead} first={1} crop={cropOf(lead.places)} />
        </button>
      ) : (
        <span className="vw-src-thumb vw-src-thumb--none">No picture of this file</span>
      )}
      <figcaption>
        <Legend places={places} first={1} />
        <span className="vw-src-btns">
          {pictured && (
            <button
              type="button"
              className="v-btn v-btn--secondary v-press vw-btn-plain"
              aria-expanded={open}
              onClick={toggle}
            >
              {open ? 'Minimize' : 'Expand'}
            </button>
          )}
          <button
            ref={show}
            type="button"
            className="v-btn v-btn--secondary v-press vw-btn-soft"
            onClick={() => {
              setPreview(true);
            }}
          >
            Show source
          </button>
        </span>
      </figcaption>
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
