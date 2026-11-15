// The pipeline view's lanes (ingest.md "Pipeline view v5"): the files moving through the stages, one lane per
// route, each with the readers that route runs here, and per file the stage it is in, the reader running now
// (`FileStatus.step`) and, once read, what it found.
import { useState, type JSX } from 'react';
import type { FileStatus, ProjectView } from '../api';
import { STAGE_LABEL, STATE_LABEL, STEPS, isFinished, isLive, plural, stepOf } from './ingest';
import {
  PIPELINE_TIPS,
  fileStep,
  foundLine,
  lanes,
  routeReaders,
  stepMatches,
  type Lane,
} from './pipeline';
import { MUTED } from './ui';
import { cn } from '@/lib/utils';
import { Tip } from '@/components/ui/tip';

/** Files shown per lane; the rest are counted, with a link to Documents. */
export const LANE_ROWS = 6;
/** The file stages' steps (1-8): Index has no file stage. */
const FILE_STEPS = STEPS.filter((s) => s.stages.length > 0).length;

const STATE_TONE: Record<FileStatus['state'], string> = {
  queued: 'text-muted-foreground',
  running: 'text-primary',
  ready: 'text-ok',
  flagged: 'text-warn',
  text_only: 'text-muted-foreground',
  set_aside: 'text-danger',
};

/** The step labels seen running on each lane's files, kept across polls (a step can start and end between two). */
function useSeenSteps(files: readonly FileStatus[]): Map<string, Set<string>> {
  const [seen, setSeen] = useState(() => new Map<string, Set<string>>());
  const [last, setLast] = useState<readonly FileStatus[] | null>(null);
  if (files !== last) {
    // adjusted while rendering (react.dev "storing information from previous renders"), not in an effect
    setLast(files);
    const fresh = files.filter((f) => f.route && fileStep(f) !== null);
    if (fresh.some((f) => !seen.get(f.route ?? '')?.has(fileStep(f) ?? ''))) {
      const next = new Map(seen);
      for (const f of fresh) {
        const route = f.route ?? '';
        next.set(route, new Set([...(next.get(route) ?? []), fileStep(f) ?? '']));
      }
      setSeen(next);
    }
  }
  return seen;
}

/** 8 ticks, one per file step: done, the one it is in now, still to come. Words carry the state beside it. */
function Track({ file }: { file: FileStatus }) {
  const at = stepOf(file.stage);
  const running = file.state === 'running';
  const ended = isFinished(file);
  return (
    <span aria-hidden="true" className="ingest-track flex gap-0.5" data-step={at}>
      {Array.from({ length: FILE_STEPS }, (_, i) => {
        const n = i + 1;
        const tone =
          n < at || (ended && n === at)
            ? file.state === 'set_aside'
              ? 'bg-muted-foreground/40'
              : 'bg-primary'
            : n === at && running
              ? 'bg-primary motion-safe:animate-pulse'
              : 'bg-muted';
        return <span key={n} className={cn('h-1 w-3 rounded-full', tone)} />;
      })}
    </span>
  );
}

/** What the row says under the path: the reader now, the stage, what it found, or why it was not read. */
function rowNote(file: FileStatus): string {
  if (file.state === 'running') {
    const step = fileStep(file);
    const stage = file.stage ? STAGE_LABEL[file.stage] : 'Starting';
    return step ? `${stage}: ${step}` : stage;
  }
  if (file.state === 'queued') return 'waiting for a free reader';
  if (file.source && file.source !== file.path) return `same drawing as ${file.source}`;
  const found = foundLine(file.takeoff);
  if (found && file.state === 'ready') return found;
  if (found) return file.reason ? `${found}. ${file.reason}` : found;
  return file.reason;
}

function FileRow({ projectId, file }: { projectId: string; file: FileStatus }) {
  const { word, icon } = STATE_LABEL[file.state];
  return (
    <li className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 gap-y-1 border-t border-muted py-2.5 first:border-t-0">
      <a
        href={`#/p/${projectId}/f/${file.id}`}
        className="min-w-0 truncate font-mono text-[13px] text-foreground no-underline hover:underline"
        title={file.path}
      >
        {file.path}
      </a>
      <span className={cn('flex items-center gap-1.5 text-xs font-medium', STATE_TONE[file.state])}>
        <span aria-hidden="true">{icon}</span>
        {word}
      </span>
      <span className={cn('min-w-0 text-[13px] text-muted-foreground', 'line-clamp-2')}>
        {rowNote(file)}
      </span>
      <Track file={file} />
    </li>
  );
}

function ReaderChips({
  readers,
  seen,
  now,
}: {
  readers: string[];
  seen: Set<string>;
  now: string[];
}) {
  // a step label seen that no reader name covers is shown too: the server ran it
  const extra = [...seen].filter((l) => !readers.some((r) => stepMatches(l, r)));
  const chips = [...readers, ...extra];
  if (chips.length === 0) return null;
  return (
    <Tip text={PIPELINE_TIPS.readers} wrap className="justify-self-start">
      <ul aria-label="Readers" className="flex flex-wrap gap-1.5">
        {chips.map((c) => {
          const running = now.some((l) => stepMatches(l, c));
          const ran = [...seen].some((l) => stepMatches(l, c));
          return (
            <li
              key={c}
              className={cn(
                'rounded-full px-2.5 py-0.5 text-xs',
                running ? 'bg-accent font-semibold text-primary' : 'bg-muted text-text-2',
              )}
            >
              {running ? <span className="sr-only">running: </span> : null}
              {c}
              {ran && !running && (
                <span aria-label="ran" className="ml-1 text-ok">
                  ✓
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Tip>
  );
}

function LaneView({
  projectId,
  lane,
  readers,
  seen,
  live,
  known,
}: {
  projectId: string;
  lane: Lane;
  readers: string[];
  seen: Set<string>;
  live: boolean;
  known: boolean;
}) {
  const routed = lane.id !== 'waiting' && lane.id !== 'other';
  const reading = lane.files.filter((f) => f.state === 'running');
  const now = reading.map(fileStep).filter((s): s is string => s !== null);
  const shown = lane.files.slice(0, LANE_ROWS);
  const more = lane.files.length - shown.length;
  const found = lane.files.filter(
    (f) => isFinished(f) && f.drawing_id && (!f.source || f.source === f.path),
  );
  return (
    <section
      aria-label={lane.name}
      className="ingest-lane grid gap-2 rounded-[14px] border border-muted p-3.5"
      data-lane={lane.id}
    >
      <header className="grid gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 className="m-0 text-[15px] font-semibold">
            {lane.name}
            {routed && <span className="font-normal text-muted-foreground"> route</span>}
          </h3>
          <span className={MUTED}>
            {[
              plural(lane.files.length, 'file'),
              live && reading.length > 0 ? `${String(reading.length)} reading now` : null,
              routed && found.length > 0 ? plural(found.length, 'drawing') + ' read' : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </div>
        {routed &&
          (readers.length > 0 || seen.size > 0 ? (
            <ReaderChips readers={readers} seen={seen} now={now} />
          ) : (
            // said only when the server recorded its readers (an old one did not)
            known && (
              <p className={MUTED}>
                No reader for this route on this server: nothing on it is counted.
              </p>
            )
          ))}
      </header>
      <ul aria-label={`${lane.name} files`} className="grid">
        {shown.map((f) => (
          <FileRow key={f.id} projectId={projectId} file={f} />
        ))}
      </ul>
      {more > 0 && (
        <a className="text-[13px] text-primary" href={`#/p/${projectId}/documents`}>
          {`${plural(more, 'more file')} in Documents`}
        </a>
      )}
    </section>
  );
}

/** Every lane with files, routes first. Nothing before the first file is found. */
export function RouteLanes({
  projectId,
  project,
}: {
  projectId: string;
  project: ProjectView;
}): JSX.Element | null {
  const seen = useSeenSteps(project.files);
  const byRoute = routeReaders(project.readers);
  const all = lanes(project.files);
  if (all.length === 0) return null;
  return (
    <section aria-label="Routes" className="grid content-start gap-3">
      <h3 className="v-caption m-0">How each file is read</h3>
      {all.map((lane) => (
        <LaneView
          key={lane.id}
          projectId={projectId}
          lane={lane}
          readers={lane.id in byRoute ? byRoute[lane.id as keyof typeof byRoute] : []}
          seen={seen.get(lane.id) ?? new Set()}
          live={isLive(project)}
          known={project.readers !== undefined}
        />
      ))}
    </section>
  );
}
