import { useEffect, useState } from 'react';
import {
  getDrawing,
  getTakeoff,
  postReview,
  postSignoff,
  takeoffCsvUrl,
  type DrawingView,
  type Edit,
  type SignOffRequest,
  type Takeoff,
} from '../api';
import { ErrorView } from '../shell/ErrorView';
import { Loading } from '../shell/Loading';
import { routeHref } from '../shell/route';
import { PageViewer } from '../viewer/PageViewer';
import { ProjectReviewSide } from './ProjectReviewSide';
import { QuantityDetail } from './QuantityDetail';
import { TakeoffTable } from './TakeoffTable';

interface Props {
  projectId: string;
  drawingId: string;
  query: URLSearchParams;
}

const NAME_KEY = 'countersign.surveyorName';

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return ''; // storage blocked: the field starts empty
  }
}

function saveName(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // storage blocked: the name is not remembered, signing still works
  }
}

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError';

/** The surveyor workspace (docs/specs/frontend/surveyor.md): takeoff, review edits, sign-off. */
export function SurveyorScreen({ projectId, drawingId, query }: Props) {
  const [drawing, setDrawing] = useState<DrawingView | null>(null);
  const [takeoff, setTakeoff] = useState<Takeoff | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [zeros, setZeros] = useState(false);
  const q = query.get('q');
  const [pick, setPick] = useState({ from: q, key: q });
  if (pick.from !== q) setPick({ from: q, key: q }); // a new ?q= from a link wins
  const [mark, setMark] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [addMode, setAddMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<unknown>(null);
  const [name, setName] = useState(savedName);
  const [reload, setReload] = useState(0);
  // every takeoff request names this project, so its file names are this project's (R1-4-4)
  const zq = zeros ? { project: projectId, zeros: true } : { project: projectId };

  useEffect(() => {
    const abort = new AbortController();
    void getDrawing(drawingId, { project: projectId, signal: abort.signal }).then(
      setDrawing,
      (e: unknown) => {
        if (!isAbort(e)) setLoadError(e);
      },
    );
    return () => {
      abort.abort();
    };
  }, [drawingId, projectId, attempt]);

  useEffect(() => {
    const abort = new AbortController();
    const scope = zeros ? { project: projectId, zeros: true } : { project: projectId };
    void getTakeoff(drawingId, { signal: abort.signal, ...scope }).then(
      setTakeoff,
      (e: unknown) => {
        if (!isAbort(e)) setLoadError(e);
      },
    );
    return () => {
      abort.abort();
    };
  }, [drawingId, projectId, zeros, attempt]);

  useEffect(() => {
    if (!addMode) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAddMode(false);
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [addMode]);

  const side = <ProjectReviewSide projectId={projectId} drawingId={drawingId} reload={reload} />;
  if (loadError !== null)
    return (
      <div className="sv-screen">
        {side}
        <ErrorView
          error={loadError}
          onRetry={() => {
            setLoadError(null);
            setAttempt((n) => n + 1);
          }}
        />
      </div>
    );
  if (!drawing || !takeoff)
    return (
      <div className="sv-screen">
        {side}
        <Loading label="Loading the takeoff…" />
      </div>
    );

  const rows = takeoff.quantities;
  const keys = new Set(rows.map((r) => r.key));
  const selectedKey =
    (pick.key !== null && keys.has(pick.key) ? pick.key : null) ??
    takeoff.review_queue.find((k) => keys.has(k)) ??
    rows[0]?.key ??
    null;
  const row = rows.find((r) => r.key === selectedKey) ?? null;
  const signedCount = rows.filter((r) => r.status === 'signed').length;

  function select(key: string) {
    setPick({ from: q, key });
    setMark(null);
    setAddMode(false);
    const href = routeHref({
      name: 'workspace',
      projectId,
      drawingId,
      role: 'surveyor',
      query: new URLSearchParams({ q: key }),
    });
    history.replaceState(history.state, '', href);
  }

  async function send(request: () => Promise<Takeoff>) {
    setSaving(true);
    setEditError(null);
    try {
      setTakeoff(await request());
      setReload((n) => n + 1);
    } catch (e) {
      setEditError(e);
    } finally {
      setSaving(false);
    }
  }
  const edit = (body: Edit) => {
    setAddMode(false);
    void send(() => postReview(drawingId, body, zq));
  };

  const zerosToggle = (
    <label>
      <input
        type="checkbox"
        checked={zeros}
        onChange={(e) => {
          setZeros(e.target.checked);
        }}
      />{' '}
      Show rows with value 0
    </label>
  );

  return (
    <div className="sv-screen sv-work">
      {side}
      <PageViewer
        file={drawing.file}
        pages={drawing.pages}
        credit={drawing.credit ?? null}
        marks={row?.marks ?? []}
        unit={row?.unit ?? null}
        unlocated={row?.unlocated ?? {}}
        conflict={row?.conflict ?? null}
        selected={mark}
        highlighted={hover}
        onSelect={setMark}
        onHover={setHover}
        onPick={
          addMode && row
            ? (page, box) => {
                edit({ quantity: row.key, action: 'add', page, box });
              }
            : undefined
        }
      />
      <section className="sv-panel" aria-label="Takeoff">
        {rows.length === 0 ? (
          <>
            <header className="sv-panel-head">
              <h2>Takeoff: {drawing.file}</h2>
            </header>
            <p>Nothing was counted on this drawing.</p>
            {drawing.reader.extractor === 'hello' && (
              <p>This drawing&apos;s route has no reader in this build, so nothing was counted.</p>
            )}
            {!zeros && zerosToggle}
          </>
        ) : (
          <>
            <header className="sv-panel-head">
              <h2>Takeoff: {drawing.file}</h2>
              <div className="sv-tools">
                <a href={takeoffCsvUrl(drawingId, zq)} download>
                  Export CSV
                </a>
                {zerosToggle}
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    if (window.confirm('Reset every edit and sign-off of this drawing?'))
                      void send(() => postReview(drawingId, { action: 'reset' }, zq));
                  }}
                >
                  Reset all edits
                </button>
              </div>
              <p>
                {signedCount} of {rows.length} quantities signed off
              </p>
              <progress value={signedCount} max={rows.length} />
            </header>
            <TakeoffTable takeoff={takeoff} selected={selectedKey} onSelect={select} />
            {row && (
              <QuantityDetail
                key={row.key}
                row={row}
                saving={saving}
                error={editError}
                name={name}
                onName={setName}
                addMode={addMode}
                onToggleAdd={() => {
                  setAddMode((on) => !on);
                }}
                selectedMark={mark}
                highlightedMark={hover}
                onHoverMark={setHover}
                onEdit={edit}
                onSign={(undo) => {
                  const by = name.trim() || (row.signed?.by ?? '');
                  if (!undo) saveName(by);
                  void send(() =>
                    postSignoff(
                      drawingId,
                      // undo defaults to false server-side; the sign-off body is signoff_request.json as is
                      undo
                        ? { quantity: row.key, by, undo: true }
                        : ({ quantity: row.key, by } as SignOffRequest),
                      zq,
                    ),
                  );
                }}
              />
            )}
          </>
        )}
      </section>
    </div>
  );
}
