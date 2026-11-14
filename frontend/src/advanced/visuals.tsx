import { useState } from 'react';
import {
  pageUrl,
  previewUrl,
  type DrawingView,
  type FileStatus,
  type ProjectView,
  type Takeoff,
} from '../api';
import { formatValue, methodName, readerName } from '../api/format';
import { formatSize, isFinished, normalisedSteps, plural } from '../ingest/ingest';
import { StateBadge } from '../ingest/ProjectScreen';
import { drawingFiles, scaleChip, type Pair } from './advanced';

/** An image that says so when it cannot load, instead of a broken icon. */
function Img({ src, alt, missing }: { src: string; alt: string; missing: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) return <p className="adv-missing">{missing}</p>;
  return (
    <img
      src={src}
      alt={alt}
      onError={() => {
        setBroken(true);
      }}
    />
  );
}

/** Unpack: every file of the upload as a card; the one the step works on is framed. */
export function FileStrip({
  project,
  working,
}: {
  project: ProjectView;
  working: FileStatus | null;
}) {
  const files = project.files;
  const total = files.reduce((n, f) => n + f.size, 0);
  return (
    <div className="adv-visual">
      <ul className="adv-strip" tabIndex={0} aria-label="Files in this upload">
        {files.map((f) => (
          <li key={f.id} className={f.id === working?.id ? 'adv-card framed' : 'adv-card'}>
            {f.drawing_id && (
              <Img src={pageUrl(f.drawing_id, 1, 400)} alt="" missing="Page not available" />
            )}
            <span className="adv-path">{f.path}</span>
            <span>
              {formatSize(f.size)} · {f.kind ?? 'not identified'}
            </span>
            <StateBadge state={f.state} />
          </li>
        ))}
      </ul>
      <p className="adv-caption">
        {working
          ? `${working.path} · ${formatSize(working.size)}`
          : `${plural(files.length, 'file')}, ${formatSize(total)}`}
      </p>
    </div>
  );
}

const EXACT = ['bim', 'cad', 'vector'] as const;

/** Identify and Route: one file with what was found about it, and the two lanes files are routed to. */
export function RouteLanes({
  projectId,
  project,
  working,
  views,
}: {
  projectId: string;
  project: ProjectView;
  working: FileStatus | null;
  views: ReadonlyMap<string, DrawingView>;
}) {
  const files = project.files;
  const fallback = working ?? files.find((f) => f.route) ?? files[0] ?? null;
  const [picked, setPicked] = useState<string | null>(null);
  const file = files.find((f) => f.id === picked) ?? fallback;
  const readers = project.readers ?? {};
  const exact = files.filter((f) => f.route && (EXACT as readonly string[]).includes(f.route));
  const image = files.filter((f) => f.route === 'raster');
  const lane = !file?.route ? null : file.route === 'raster' ? 'image' : 'exact';
  const page = file?.drawing_id ? views.get(file.drawing_id)?.pages[0] : undefined;
  const chips: [string, string | null][] = file
    ? [
        ['kind', file.kind ?? 'not identified'],
        [
          'size',
          file.normalised
            ? `${String(file.normalised.width)} × ${String(file.normalised.height)} px`
            : null,
        ],
        ['scale', scaleChip(page?.scale)],
        ['route', file.route ? `route ${file.route}` : null],
        ['source', file.source && file.source !== file.path ? `read from ${file.source}` : null],
        ['reused', file.reused ? 'read before' : null],
      ]
    : [];
  const laneBox = (id: 'exact' | 'image', title: string, readerIds: string[], count: number) => (
    <div className="adv-lane" aria-current={lane === id ? 'true' : undefined}>
      <strong>{title}</strong>
      <span>{readerIds.map((r) => `${r}: ${readerName(readers[r])}`).join(' · ')}</span>
      <span>{plural(count, 'file')}</span>
      {lane === id && <span className="adv-here">This file goes here</span>}
    </div>
  );
  return (
    <div className="adv-visual">
      {file && (
        <>
          <label className="adv-pick">
            File{' '}
            <select
              value={file.id}
              onChange={(e) => {
                setPicked(e.target.value);
              }}
            >
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.path}
                </option>
              ))}
            </select>
          </label>
          <figure className="adv-figure">
            <Img
              src={previewUrl(projectId, file.id)}
              alt={`${file.path} as uploaded`}
              missing="Preview not available"
            />
            <ul className="adv-chips" aria-label="What was found">
              {chips.map(([key, text]) => (text ? <li key={key}>{text}</li> : null))}
            </ul>
          </figure>
          {!file.route && (
            <p className="adv-note">
              {isFinished(file) ? `Not routed: ${file.reason || file.state}` : 'Not routed yet.'}
            </p>
          )}
        </>
      )}
      <div className="adv-lanes">
        {laneBox('exact', 'Exact geometry', [...EXACT], exact.length)}
        {laneBox('image', 'From the image', ['raster'], image.length)}
      </div>
    </div>
  );
}

const MARKED = new Set(['room', 'door', 'window']);

/** Normalise, Extract, Drawing model: a drawing's first page with the rooms, doors and windows found on it. */
export function PlanMarks({
  project,
  takeoffs,
  failed,
  onRetry,
  sweep,
  showNormalised,
}: {
  project: ProjectView;
  takeoffs: ReadonlyMap<string, Takeoff>;
  failed: (drawingId: string) => boolean;
  onRetry: (drawingId: string) => void;
  sweep: boolean;
  showNormalised: boolean;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const drawings = project.drawings;
  const drawing = drawings.find((d) => d.drawing_id === picked) ?? drawings[0];
  if (!drawing) return <p className="adv-missing">No drawing yet.</p>;
  const file = project.files.find((f) => f.path === drawing.file);
  const takeoff = takeoffs.get(drawing.drawing_id);
  const marks = (takeoff?.quantities ?? [])
    .filter((r) => MARKED.has(r.key))
    .flatMap((r) =>
      r.marks.filter((m) => m.page === 1 && m.state !== 'rejected').map((m) => ({ m, key: r.key })),
    );
  return (
    <div className="adv-visual">
      <label className="adv-pick">
        Drawing{' '}
        <select
          value={drawing.drawing_id}
          onChange={(e) => {
            setPicked(e.target.value);
          }}
        >
          {drawings.map((d) => (
            <option key={d.drawing_id} value={d.drawing_id}>
              {d.file}
            </option>
          ))}
        </select>
      </label>
      {drawing.kind === 'ifc' ? (
        <p className="adv-missing">A model, no sheet to show.</p>
      ) : (
        <div className="adv-plan">
          <Img
            src={pageUrl(drawing.drawing_id, 1)}
            alt={`${drawing.file}, page 1`}
            missing="Page not available"
          />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
            {marks.map(({ m, key }) => (
              <rect
                key={m.id}
                className={`adv-mark ${key}`}
                x={m.box[0]}
                y={m.box[1]}
                width={m.box[2] - m.box[0]}
                height={m.box[3] - m.box[1]}
              />
            ))}
          </svg>
          {sweep && <span className="adv-sweep" aria-hidden="true" />}
          {marks
            .filter(({ m, key }) => key === 'room' && m.label)
            .map(({ m }) => (
              <span
                key={`${m.id}-label`}
                className="adv-pill"
                style={{ left: `${String(m.box[0] * 100)}%`, top: `${String(m.box[1] * 100)}%` }}
                title={m.room_type ?? undefined}
              >
                {m.label}
              </span>
            ))}
        </div>
      )}
      {failed(drawing.drawing_id) && (
        <p className="adv-error">
          Could not load the takeoff of {drawing.file}.{' '}
          <button
            type="button"
            onClick={() => {
              onRetry(drawing.drawing_id);
            }}
          >
            Retry
          </button>
        </p>
      )}
      {showNormalised && file && (
        <ul className="adv-steps-done">
          {(file.normalised
            ? normalisedSteps(file.normalised)
            : ['Pages as the file gives them']
          ).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const VERDICT: Record<string, string> = {
  agree: 'They agree. Kept as the answer.',
  conflict: 'They disagree. Sent to Settle the conflicts.',
};

/** Cross-check: every quantity measured twice, with both values and the verdict. */
export const PAIRS_SHOWN = 4;

export function CheckPairs({ projectId, pairs }: { projectId: string; pairs: readonly Pair[] }) {
  const [all, setAll] = useState(false);
  if (!pairs.length)
    return (
      <p className="adv-missing">Nothing on these drawings can be measured a second way yet.</p>
    );
  // Every conflict, then the first few that agree; the rest behind a button (a long list buries the panel).
  const conflicts = pairs.filter((p) => p.row.status === 'conflict').length;
  const shown = all ? pairs : pairs.slice(0, conflicts + PAIRS_SHOWN);
  return (
    <div className="adv-visual">
      <ul className="adv-pairs" aria-label="Measured twice">
        {shown.map(({ row, file, drawingId }) => (
          <li key={`${drawingId}-${row.key}`} className={`adv-pair ${row.status}`}>
            <p className="adv-pair-what">
              {row.label} · {file}
            </p>
            <div className="adv-pair-values">
              <span>
                <small>From the drawing</small>
                <b>{row.first ? formatValue(row.first.value, row.unit) : '–'}</b>
                <small>{methodName(row.first?.method)}</small>
              </span>
              <span aria-hidden="true">→</span>
              <span>
                <small>Second count</small>
                <b>{row.second ? formatValue(row.second.value, row.unit) : '–'}</b>
                <small>{methodName(row.second?.method)}</small>
              </span>
            </div>
            <p className="adv-verdict">
              <span aria-hidden="true">{row.status === 'conflict' ? '!' : '✓'}</span>{' '}
              {VERDICT[row.status] ?? row.status}
              {row.status === 'conflict' && (
                <>
                  {' '}
                  <a href={`#/p/${projectId}/conflicts`}>Settle the conflicts</a>
                </>
              )}
            </p>
          </li>
        ))}
      </ul>
      {shown.length < pairs.length && (
        <button
          type="button"
          className="adv-more"
          onClick={() => {
            setAll(true);
          }}
        >
          Show all {pairs.length} pairs
        </button>
      )}
    </div>
  );
}

/** Index: per drawing, how many questions are ready to ask (one per quantity) and the ones it suggests. */
export function ReadyList({
  projectId,
  project,
  views,
}: {
  projectId: string;
  project: ProjectView;
  views: ReadonlyMap<string, DrawingView>;
}) {
  const files = drawingFiles(project);
  if (!project.drawings.length) return <p className="adv-missing">No drawing to ask yet.</p>;
  return (
    <div className="adv-visual adv-ready">
      <strong>Questions ready to ask</strong>
      <ul>
        {project.drawings.map((d) => {
          const file = files.find((f) => f.path === d.file);
          const n = Object.keys(file?.takeoff ?? {}).length;
          const ready = d.state === 'ready' || d.state === 'flagged';
          return (
            <li key={d.drawing_id}>
              <span className={ready ? 'adv-dot on' : 'adv-dot'} aria-hidden="true" />
              <span className="adv-path">{d.file}</span>: {plural(n, 'question')} ready to ask
              <ul>
                {(views.get(d.drawing_id)?.suggestions ?? []).map((s) => (
                  <li key={s.quantity}>{s.label}</li>
                ))}
              </ul>
              <a href={`#/p/${projectId}/d/${d.drawing_id}/engineer`}>Ask this drawing</a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
