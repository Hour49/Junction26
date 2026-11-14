import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ApiError, getModelGlb, type FileStatus, type Highlight } from '../api';
import { plural } from '../ingest/ingest';
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
    <button type="button" className="v-btn v-btn--secondary v-press" onClick={again}>
      Try again
    </button>
  );
  const onKey = (e: KeyboardEvent) => {
    if (e.key === '+' || e.key === '=') view.current?.zoom(0.8);
    else if (e.key === '-') view.current?.zoom(1.25);
  };
  const tool = (label: string, glyph: string, act: (v: View) => void) => (
    <button
      type="button"
      className="v-btn v-btn--secondary v-press m3-tool"
      aria-label={label}
      title={label}
      onClick={() => {
        if (view.current) act(view.current);
      }}
    >
      <span aria-hidden="true">{glyph}</span>
    </button>
  );
  const ready = status.kind === 'ready';

  return (
    <div className="m3-view">
      <div className="m3-stage">
        <canvas
          ref={canvas}
          className={ready ? 'm3-canvas' : 'm3-canvas m3-canvas--hidden'}
          tabIndex={ready ? 0 : -1}
          role="img"
          aria-label={`3D view of ${name}`}
          onKeyDown={onKey}
        />
        {ready ? (
          <div className="m3-tools" role="toolbar" aria-label="3D view controls">
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
          <div className="m3-status" role="status" aria-live="polite">
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

/** Colour is never the only cue: each role in words with its count (model-3d.md part 3). */
function Legend({ shown }: { shown: Shown }) {
  const found = ROLES.filter((r) => shown.counts[r]);
  const total = found.reduce((n, r) => n + (shown.counts[r] ?? 0), 0) + shown.missing;
  return (
    <div className="m3-legend">
      {found.length > 0 ? (
        <ul aria-label="Highlighted elements">
          {found.map((r) => (
            <li key={r}>
              <span className={`m3-swatch m3-swatch--${r}`} aria-hidden="true" />
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
    <section aria-label="3D view" className="v-card m3-card">
      <h2 className="v-h3">3D view</h2>
      {model.state === 'unavailable' ? (
        <p>3D view unavailable: {model.reason || UNAVAILABLE}</p>
      ) : open ? (
        <ModelView projectId={projectId} fileId={file.id} name={file.path} />
      ) : (
        <p className="m3-open">
          <button
            type="button"
            className="v-btn v-btn--secondary v-press"
            onClick={() => {
              setOpen(true);
            }}
          >
            Show in 3D
          </button>
          {typeof model.elements === 'number' && (
            <span className="m3-muted">{plural(model.elements, 'element')}</span>
          )}
        </p>
      )}
    </section>
  );
}
