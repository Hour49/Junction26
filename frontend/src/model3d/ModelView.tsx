import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ApiError, getModelGlb, type FileStatus, type Highlight } from '../api';
import { plural } from '../ingest/ingest';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { failure, model3dOf, ROLE_LABEL, ROLES, UNAVAILABLE } from './model3d';
import type { Shown, View } from './scene';
import './model3d.css';

const RETRY_MS = 5000;
const MAX_TRIES = 24; // 2 minutes of "Preparing" before asking the person to come back

type Status =
  | { kind: 'loading' }
  | { kind: 'preparing'; gaveUp: boolean }
  | { kind: 'failed'; reason: string; retry: boolean }
  | { kind: 'ready'; shown: Shown };

const isAbort = (e: unknown) => (e as { name?: unknown } | null)?.name === 'AbortError';

/** The interactive 3D view of one IFC file (model-3d.md): loads the GLB, then three.js on demand. */
export function ModelView({
  projectId,
  fileId,
  name,
  highlight = [],
}: {
  projectId: string;
  fileId: string;
  name: string;
  /** Elements to colour by role (part 3); the rest dimmed, the camera on them. Read once, at the first load. */
  highlight?: readonly Highlight[];
}) {
  const marks = useRef(highlight);
  const canvas = useRef<HTMLCanvasElement>(null);
  const view = useRef<View | null>(null);
  const tries = useRef(0);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<Status>({ kind: 'loading' });

  useEffect(() => {
    const abort = new AbortController();
    const gone = () => abort.signal.aborted; // a call, so a check after an await is not narrowed away
    let mounted: View | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const glb = await getModelGlb(projectId, fileId, { signal: abort.signal });
        const { mount } = await import('./scene');
        if (gone() || !canvas.current) return;
        const v = await mount(canvas.current, glb, marks.current);
        if (gone()) {
          v.dispose(); // unmounted while three.js was parsing
          return;
        }
        mounted = view.current = v;
        setStatus({ kind: 'ready', shown: v.shown });
      } catch (error) {
        if (gone() || isAbort(error)) return;
        if (error instanceof ApiError && error.status === 409) {
          tries.current += 1;
          const gaveUp = tries.current >= MAX_TRIES;
          if (!gaveUp)
            timer = setTimeout(() => {
              setAttempt((a) => a + 1);
            }, RETRY_MS);
          setStatus({ kind: 'preparing', gaveUp });
          return;
        }
        setStatus({ kind: 'failed', ...failure(error) });
      }
    };
    void load();
    return () => {
      abort.abort();
      clearTimeout(timer);
      mounted?.dispose();
      view.current = null;
    };
  }, [projectId, fileId, attempt]);

  const again = () => {
    tries.current = 0;
    setStatus({ kind: 'loading' });
    setAttempt((a) => a + 1);
  };
  const tryAgain = (
    <Button variant="secondary" size="pill" className="v-press font-medium" onClick={again}>
      Try again
    </Button>
  );
  const onKey = (e: KeyboardEvent) => {
    if (e.key === '+' || e.key === '=') view.current?.zoom(0.8);
    else if (e.key === '-') view.current?.zoom(1.25);
  };
  const tool = (label: string, glyph: string, act: (v: View) => void) => (
    <Button
      variant="secondary"
      size="pill-icon"
      className="v-press bg-card text-xl leading-none shadow-[var(--v-shadow)] hover:bg-accent"
      aria-label={label}
      title={label}
      onClick={() => {
        if (view.current) act(view.current);
      }}
    >
      <span aria-hidden="true">{glyph}</span>
    </Button>
  );
  const ready = status.kind === 'ready';

  return (
    <div>
      {/* m3-stage: ModelDialog sets its height */}
      <div className="m3-stage relative h-[560px] overflow-hidden rounded-[var(--v-radius)] border border-border bg-muted max-[600px]:h-[min(60vh,420px)]">
        <canvas
          ref={canvas}
          // touch-action none: one finger orbits; the page scrolls outside the view
          className={cn(
            'block h-full w-full touch-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
            !ready && 'invisible',
          )}
          tabIndex={ready ? 0 : -1}
          role="img"
          aria-label={`3D view of ${name}`}
          onKeyDown={onKey}
        />
        {ready ? (
          <div
            className="absolute top-2 right-2 flex gap-1.5"
            role="toolbar"
            aria-label="3D view controls"
          >
            {tool('Rotate left', '⟲', (v) => {
              v.rotate(-15);
            })}
            {tool('Rotate right', '⟳', (v) => {
              v.rotate(15);
            })}
            {tool('Zoom in', '+', (v) => {
              v.zoom(0.8);
            })}
            {tool('Zoom out', '−', (v) => {
              v.zoom(1.25);
            })}
            {tool('Reset view', '⌂', (v) => {
              v.reset();
            })}
          </div>
        ) : (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-4 text-center text-text-2 [&_p]:m-0"
            role="status"
            aria-live="polite"
          >
            {status.kind === 'loading' && <p>Loading the 3D view…</p>}
            {status.kind === 'preparing' && (
              <>
                <p>
                  {status.gaveUp ? 'Still preparing. Try again later.' : 'Preparing the 3D view…'}
                </p>
                {tryAgain}
              </>
            )}
            {status.kind === 'failed' && (
              <>
                <p>3D view unavailable: {status.reason}</p>
                {status.retry && tryAgain}
              </>
            )}
          </div>
        )}
      </div>
      {status.kind === 'ready' && highlight.length > 0 && <Legend shown={status.shown} />}
    </div>
  );
}

// The role colours (shell.css --v-3d-*, the scene's too); removed also half see-through, as in the view.
const SWATCH: Record<Highlight['role'], string> = {
  moved: 'bg-[var(--v-3d-moved)]',
  removed: 'bg-[var(--v-3d-removed)] opacity-50',
  added: 'bg-[var(--v-3d-added)]',
  affected: 'bg-[var(--v-3d-affected)]',
};

/** Colour is never the only cue: each role in words with its count (model-3d.md part 3). */
function Legend({ shown }: { shown: Shown }) {
  const found = ROLES.filter((r) => shown.counts[r]);
  const total = found.reduce((n, r) => n + (shown.counts[r] ?? 0), 0) + shown.missing;
  return (
    <div className="m3-legend mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2 text-text-2 [&_p]:m-0">
      {found.length > 0 ? (
        <ul
          aria-label="Highlighted elements"
          className="m-0 flex list-none flex-wrap gap-x-4 gap-y-2 p-0"
        >
          {found.map((r) => (
            <li key={r} className="flex items-center gap-1.5">
              <span className={cn('size-3.5 rounded-[4px]', SWATCH[r])} aria-hidden="true" />
              {ROLE_LABEL[r]}: {shown.counts[r]}
            </li>
          ))}
        </ul>
      ) : (
        <p>None of these elements are in the 3D view.</p>
      )}
      {found.length > 0 && shown.missing > 0 && (
        <p>
          {shown.missing} of {total} elements are not in the 3D view.
        </p>
      )}
    </div>
  );
}

/** The file page's "3D view" card (model-3d.md part 1): nothing without `model_3d`; the GLB loads on the press. */
export function ModelCard({ projectId, file }: { projectId: string; file: FileStatus }) {
  const [open, setOpen] = useState(false);
  const model = model3dOf(file);
  if (!model) return null;
  return (
    <Card
      role="region"
      aria-label="3D view"
      className="block rounded-[var(--v-radius)] border-0 p-6 shadow-[var(--v-shadow)] max-[720px]:p-5"
    >
      <h2 className="m-0 mb-3 text-2xl leading-tight font-semibold tracking-[-0.01em]">3D view</h2>
      {model.state === 'unavailable' ? (
        <p>3D view unavailable: {model.reason || UNAVAILABLE}</p>
      ) : open ? (
        <ModelView projectId={projectId} fileId={file.id} name={file.path} />
      ) : (
        <p className="m-0 flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            size="pill"
            className="v-press font-medium"
            onClick={() => {
              setOpen(true);
            }}
          >
            Show in 3D
          </Button>
          {typeof model.elements === 'number' && (
            <span className="text-muted-foreground">{plural(model.elements, 'element')}</span>
          )}
        </p>
      )}
    </Card>
  );
}
