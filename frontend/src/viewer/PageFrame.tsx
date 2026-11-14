import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { pickWidth, type PageWidth } from './marks';

interface PageFrameProps {
  url: string; // without ?width=
  width: number; // page size in its own unit, for the aspect ratio
  height: number;
  alt: string;
  page: number;
  zoom?: number; // 1, 2 or 4: the frame is this many times the scroll box's width
  onClick?: (x: number, y: number, target: Element) => void; // click point in page fractions
  className?: string;
  children?: ReactNode; // the mark overlay, in page fractions
}

type Load = { kind: 'loading' } | { kind: 'loaded' } | { kind: 'failed'; why: string | null };

/** Why a page image failed: the API's `{detail, code}` from the same URL, or "network error". */
async function failureOf(src: string): Promise<string> {
  try {
    const res = await fetch(src);
    if (res.ok) return 'the image could not be shown';
    const body = (await res.json().catch(() => null)) as {
      detail?: unknown;
      code?: unknown;
    } | null;
    return typeof body?.detail === 'string'
      ? `${body.detail} (${String(body.code)})`
      : `HTTP ${String(res.status)}`;
  } catch {
    return 'network error';
  }
}

/** One page image in the page frame (API.md "Conventions"), with its overlay, loading and error state. */
export function PageFrame({
  url,
  width,
  height,
  alt,
  page,
  zoom = 1,
  onClick,
  className,
  children,
}: PageFrameProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [base, setBase] = useState<number | null>(null);
  // The served width is only raised: zooming back out keeps the sharper image.
  const [peak, setPeak] = useState(zoom);
  if (zoom > peak) setPeak(zoom);
  const [load, setLoad] = useState<Load>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  // Measured once on mount, as the width at zoom 1: a resize does not fetch the page again.
  useLayoutEffect(() => {
    setBase((ref.current?.clientWidth ?? 0) / zoom);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on mount
  }, []);
  const served: PageWidth | null =
    base === null ? null : pickWidth(base, window.devicePixelRatio || 1, peak);

  const src = served === null ? null : `${url}?width=${String(served)}`;
  const failed = () => {
    if (src === null) return;
    setLoad({ kind: 'failed', why: null });
    void failureOf(src).then((why) => {
      setLoad((l) => (l.kind === 'failed' ? { kind: 'failed', why } : l));
    });
  };

  return (
    <div
      ref={ref}
      className={className ? `vw-frame ${className}` : 'vw-frame'}
      style={{
        aspectRatio: `${String(width)} / ${String(height)}`,
        width: `${String(zoom * 100)}%`,
      }}
      aria-busy={load.kind === 'loading'}
      onClick={
        onClick &&
        ((e) => {
          const r = e.currentTarget.getBoundingClientRect();
          if (r.width > 0 && r.height > 0)
            onClick(
              (e.clientX - r.left) / r.width,
              (e.clientY - r.top) / r.height,
              e.target as Element,
            );
        })
      }
    >
      {src !== null && load.kind !== 'failed' && (
        <img
          key={attempt}
          src={src}
          alt={alt}
          onLoad={() => {
            setLoad({ kind: 'loaded' });
          }}
          onError={failed}
        />
      )}
      {load.kind === 'loading' && <p className="vw-status">Loading page {page}…</p>}
      {load.kind === 'failed' && (
        <div className="vw-status" role="alert">
          {load.why !== null && (
            <p>
              Page {page} could not be loaded: {load.why}
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              setLoad({ kind: 'loading' });
              setAttempt((a) => a + 1);
            }}
          >
            Try again
          </button>
        </div>
      )}
      {children}
    </div>
  );
}
