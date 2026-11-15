import type { CSSProperties } from 'react';
import type { FileStatus, FileTrace, ProjectView } from '../api';
import {
  STAGE_LABEL,
  formatCost,
  formatMs,
  isFinished,
  plural,
  routeLabel,
} from '../ingest/ingest';
import { StateBadge } from '../ingest/ProjectScreen';
import { splitPath } from '../ingest/RouteLanes';
import {
  PHASE_LABEL,
  foundOf,
  longest,
  phaseRuns,
  readWith,
  reasonLines,
  stepsAfter,
  traceMs,
  type Phase,
} from './trace';
import { StepList } from './TraceTimeline';
import './trace.css';

const PHASES = Object.keys(PHASE_LABEL) as Phase[];

/** A long path gives up its folder first, the file name stays whole: it is what tells two rows apart (AD-124). */
function PathName({ path }: { path: string }) {
  const [folder, name] = splitPath(path);
  return (
    <span className="fm-path">
      {folder && <span className="fm-folder">{folder}</span>}
      <span className="fm-name">{name}</span>
    </span>
  );
}

/** One file's row: where it went, how long each stage took, what it found, what failed (AD-110..AD-113). */
function FileRow({
  projectId,
  file,
  trace,
  slowest,
}: {
  projectId: string;
  file: FileStatus;
  trace: FileTrace | undefined;
  slowest: number;
}) {
  const stages = trace?.stages ?? [];
  const runs = phaseRuns(stages);
  const failed = stages.find((s) => s.failure);
  const live = !isFinished(file);
  const top = longest(stages);
  // the row's bar is as long as the file took against the slowest file, so times compare at a glance
  const share = slowest > 0 ? Math.max(0.04, file.ms / slowest) : 0;
  const found = foundOf(file);
  const readFrom = readWith(file);
  const note = live
    ? file.step
      ? `Now: ${file.step}`
      : file.stage
        ? `Now: after ${STAGE_LABEL[file.stage]}`
        : 'Waiting'
    : top && top.ms > 0
      ? `Longest: ${STAGE_LABEL[top.stage]}, ${formatMs(top.ms)}`
      : '';
  return (
    <li className="fm-row">
      <div className="fm-file">
        {/* the label keeps the name the plain path: a browser puts a space between the two flex parts */}
        <a href={`#/p/${projectId}/f/${file.id}`} title={file.path} aria-label={file.path}>
          <PathName path={file.path} />
        </a>
        <span className="fm-meta">
          <StateBadge state={file.state} />
          {readFrom ? (
            <span className="fm-with" title={readFrom}>
              <span className="fm-with-word">read with </span>
              <PathName path={readFrom} />
            </span>
          ) : (
            <span>{file.route ? routeLabel(file.route) : 'not routed'}</span>
          )}
          {file.reused && <span>read before</span>}
        </span>
      </div>
      <div className="fm-bar">
        {share > 0 && (
          <span
            className="fm-segs"
            role="img"
            aria-label={
              stages.length
                ? stages
                    .map((s) => `${STAGE_LABEL[s.stage]}${s.ms > 0 ? ` ${traceMs(s.ms)}` : ''}`)
                    .join(', ')
                : formatMs(file.ms)
            }
            style={{ width: `${(100 * share).toFixed(1)}%` }}
          >
            {(runs.length ? runs : [{ phase: 'read' as const, ms: file.ms, failed: false }]).map(
              (r, i) => (
                <span
                  key={String(i)}
                  className={[
                    'fm-seg',
                    `phase-${r.phase}`,
                    r.failed ? 'failed' : '',
                    live && i === runs.length - 1 ? 'now' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  style={{ '--g': String(Math.max(r.ms, 0.001)) } as CSSProperties}
                />
              ),
            )}
          </span>
        )}
        {note && <span className="fm-bar-note">{note}</span>}
      </div>
      <div className="fm-facts">
        <span className="tl-ms">{file.stage ? formatMs(file.ms) : '–'}</span>
        {found && <span className="fm-found">{found}</span>}
        {file.cost_usd > 0 && <span className="tl-ms">{formatCost(file.cost_usd)}</span>}
      </div>
      {!found && isFinished(file) && file.state !== 'ready' && file.reason && (
        <p className="fm-why">{reasonLines(file.reason).join(' ')}</p>
      )}
      {failed && (
        <p className="fm-fail">
          <span aria-hidden="true">✕ </span>
          {STAGE_LABEL[failed.stage]} failed: {failed.failure}
        </p>
      )}
    </li>
  );
}

/** The whole project at a glance: every file by its stages, each opening its trace (AD-110..AD-114). */
export function FileMatrix({
  projectId,
  project,
  traces,
}: {
  projectId: string;
  project: ProjectView;
  traces: ReadonlyMap<string, FileTrace>;
}) {
  const files = project.files;
  if (files.length === 0) return null;
  const slowest = Math.max(0, ...files.map((f) => f.ms));
  const by = (s: FileStatus['state']) => files.filter((f) => f.state === s).length;
  const counts = [
    [by('ready'), 'ready'],
    [by('flagged'), 'flagged'],
    [by('set_aside'), 'set aside'],
    [by('text_only'), 'text only'],
    [by('running') + by('queued'), 'still reading'],
  ] as const;
  const index = stepsAfter(project);
  // the file column is as wide as the longest path (capped in trace.css), so names stay whole (AD-124)
  const pathLetters = Math.max(...files.map((f) => f.path.length));
  return (
    <section className="tl-card" aria-label="Files by stage">
      <div className="tl-title">
        <h2>Every file, stage by stage</h2>
        <span className="tl-ms">slowest {formatMs(slowest)}</span>
      </div>
      <p className="fm-sum">
        {plural(files.length, 'file')}:{' '}
        {counts
          .filter(([n]) => n > 0)
          .map(([n, word]) => `${String(n)} ${word}`)
          .join(', ')}
        .
      </p>
      <ul className="fm-legend" aria-label="Colours">
        {PHASES.map((p) => (
          <li key={p}>
            <span className={`fm-swatch phase-${p}`} aria-hidden="true" />
            {PHASE_LABEL[p]}
          </li>
        ))}
      </ul>
      <ol
        className="fm-list"
        aria-label="Files"
        style={{ '--fm-path': String(pathLetters) } as CSSProperties}
      >
        {files.map((f) => (
          <FileRow
            key={f.id}
            projectId={projectId}
            file={f}
            trace={traces.get(f.id)}
            slowest={slowest}
          />
        ))}
      </ol>
      {index.length > 0 && (
        <>
          <p className="tl-steps-note">
            After the files{project.phase === 'index' ? ', now' : ''}: indexing for questions
          </p>
          <StepList steps={index} label="Index steps" />
        </>
      )}
    </section>
  );
}
