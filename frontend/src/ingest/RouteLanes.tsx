// The pipeline view's lanes (ingest.md "Pipeline view v5"): the files moving through the stages, one lane per
// route, each with the readers that route runs here, and per file the stage it is in, the reader running now
// (`FileStatus.step`) and, once read, what it found.
import { useState, type JSX } from 'react';
import type { FileStatus, ProjectView } from '../api';
import { STAGE_LABEL, STATE_LABEL, STEPS, isFinished, isLive, plural, stepOf } from './ingest';
import {
  PIPELINE_TIPS,
  chipCovers,
  chipRan,
  chipStepsOf,
  chipWords,
  fileStep,
  foundLine,
  groupReaders,
  lanes,
  readDrawings,
  routeReaders,
  triageEnded,
  triageRan,
  triageReaders,
  unread,
  type ChipSteps,
  type Lane,
  type RanStep,
  type SeenStep,
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

/** The step a file is in now: its stable id (`FileStatus.step_id`) when sent, and its label; null: none. */
function nowStep(f: FileStatus): SeenStep | null {
  const label = fileStep(f);
  return label === null ? null : { id: f.step_id ?? null, label };
}

/** A seen step's key: its id, else its label (an older server). */
const keyOf = (s: SeenStep) => s.id ?? s.label;

/** The steps seen running on each lane's files, kept across polls (a step can start and end between two). */
function useSeenSteps(files: readonly FileStatus[]): Map<string, Map<string, SeenStep>> {
  const [seen, setSeen] = useState(() => new Map<string, Map<string, SeenStep>>());
  const [last, setLast] = useState<readonly FileStatus[] | null>(null);
  if (files !== last) {
    // adjusted while rendering (react.dev "storing information from previous renders"), not in an effect
    setLast(files);
    const fresh = files.flatMap((f) => {
      const step = nowStep(f);
      return f.route && step ? [{ route: f.route, step }] : [];
    });
    if (fresh.some(({ route, step }) => !seen.get(route)?.has(keyOf(step)))) {
      const next = new Map(seen);
      for (const { route, step } of fresh)
        next.set(route, new Map([...(next.get(route) ?? []), [keyOf(step), step]]));
      setSeen(next);
    }
  }
  return seen;
}

/** What a dimmed chip says: its steps were only skipped here, or none of them appeared (`ProjectStatus.ran`). */
const DIMMED = { skipped: 'not needed here', absent: 'did not run' } as const;

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

/** "a/b/c.pdf" as ["a/b/", "c.pdf"]; no folder: ["", path]. */
export function splitPath(path: string): [string, string] {
  const i = path.lastIndexOf('/');
  return [path.slice(0, i + 1), path.slice(i + 1)];
}

/** Characters of the stem kept beside the extension when a long file name is cut in the middle. */
const KEEP_END = 8;

/** A file name as [start, end]: the end is its extension and the last characters before it, the part that tells
 * "plan_2082_floor3.dxf" from "plan_2082_floor3.pdf" (QA R4-A2), so only the start gives way when it is cut. */
export function nameEnds(name: string): [string, string] {
  const dot = name.lastIndexOf('.');
  const ext = dot > 0 && name.length - dot <= 6 ? name.length - dot : 0;
  const cut = Math.max(0, name.length - ext - KEEP_END);
  return [name.slice(0, cut), name.slice(cut)];
}

function FileRow({ projectId, file }: { projectId: string; file: FileStatus }) {
  const { word, icon } = STATE_LABEL[file.state];
  const [folder, name] = splitPath(file.path);
  const [start, end] = nameEnds(name);
  return (
    <li className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 gap-y-1 border-t border-muted py-2.5 first:border-t-0">
      <a
        href={`#/p/${projectId}/f/${file.id}?from=ingest`}
        // min-h-6: a 24 px tap target (QA R4-E2: 20 px)
        className="flex min-h-6 min-w-0 items-center font-mono text-[13px] text-foreground no-underline hover:underline"
        title={file.path}
        // the two flex spans would read "plans/ a.pdf" in Chromium (a space between them): the name is the path
        aria-label={file.path}
      >
        {/* a long path gives up its folder first: the file name is what tells two rows apart */}
        {folder && (
          <span className="ingest-folder min-w-0 truncate text-muted-foreground">{folder}</span>
        )}
        {/* then the name gives up its middle: its end and extension stay (IN-129) */}
        <span className="ingest-name flex min-w-0 shrink-0 max-w-full">
          <span className="ingest-name-start min-w-0 truncate">{start}</span>
          <span className="ingest-name-end shrink-0 whitespace-pre">{end}</span>
        </span>
      </a>
      <span className={cn('flex items-center gap-1.5 text-xs font-medium', STATE_TONE[file.state])}>
        <span aria-hidden="true">{icon}</span>
        {word}
      </span>
      {/* a flagged or set-aside file's reason is shown whole (IN-122); a running note stays at 2 lines */}
      <span
        className={cn(
          'ingest-note min-w-0 text-[13px] text-muted-foreground [overflow-wrap:anywhere]',
          !isFinished(file) && 'line-clamp-2',
        )}
      >
        {rowNote(file)}
      </span>
      <Track file={file} />
    </li>
  );
}

/** One chip: highlighted while its step runs, dimmed with why it did not run, ticked once it ran. */
function Chip({
  words,
  running,
  why,
  ran,
}: {
  words: string;
  running: boolean;
  why: string | null;
  ran: boolean;
}) {
  return (
    <li
      data-dimmed={why !== null || undefined}
      className={cn(
        'rounded-full px-2.5 py-0.5 text-xs',
        running
          ? 'bg-accent font-semibold text-primary'
          : why !== null
            ? 'border border-dashed border-muted text-muted-foreground'
            : 'bg-muted text-text-2',
      )}
    >
      {running ? <span className="sr-only">running: </span> : null}
      {words}
      {why && <span>{` · ${why}`}</span>}
      {ran && !running && (
        <span aria-label="ran" className="ml-1 text-ok">
          ✓
        </span>
      )}
    </li>
  );
}

function ReaderChips({
  readers,
  seen,
  now,
  ran,
  settled,
  known,
}: {
  readers: string[];
  seen: SeenStep[];
  now: SeenStep[];
  /** `ProjectStatus.ran[route]`: the steps that ran on this lane's files in this upload (IN-124). */
  ran: readonly RanStep[] | undefined;
  /** Every file of the lane has ended: what has not run by now will not on this upload. */
  settled: boolean;
  /** Each chip's step ids on this project (`chipStepsOf`, IN-123). */
  known: ChipSteps;
}) {
  // a step seen that no reader covers is shown too, by its label: the server ran it
  const extra = [
    ...new Set(
      seen.filter((s) => !readers.some((r) => chipCovers(r, s, known))).map((s) => s.label),
    ),
  ];
  const groups = groupReaders(readers, extra);
  if (groups.length === 0) return null;
  return (
    <Tip text={PIPELINE_TIPS.readers} wrap className="justify-self-start">
      {/* by what they do, in the order they run (IN-120): a label column beside the chips, above them on a phone */}
      <div role="group" aria-label="Readers" className="grid gap-2.5 sm:gap-1.5">
        {groups.map(({ group, label, readers: chips }) => (
          <div
            key={group}
            className="ingest-readers grid items-baseline gap-x-3 gap-y-1 sm:grid-cols-[9.5rem_1fr]"
            data-group={group}
          >
            {label && <p className="m-0 text-xs font-medium text-muted-foreground">{label}</p>}
            <ul
              aria-label={label ?? 'Readers'}
              className={cn('flex flex-wrap gap-1.5', !label && 'sm:col-span-2')}
            >
              {chips.map((c) => {
                const running = now.some((s) => chipCovers(c, s, known));
                const said = chipRan(c, ran, known);
                const didRun = said === 'ran' || seen.some((s) => chipCovers(c, s, known));
                // once the lane ended, a chip none of whose steps ran says why; null: not dimmed
                const why =
                  settled && !didRun && !running && (said === 'skipped' || said === 'absent')
                    ? DIMMED[said]
                    : null;
                return (
                  <Chip
                    key={c}
                    words={chipWords(c, label !== null)}
                    running={running}
                    why={why}
                    ran={didRun}
                  />
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </Tip>
  );
}

function LaneView({
  projectId,
  lane,
  readers,
  seen,
  ran,
  steps,
  live,
  known,
  recorded,
  read,
}: {
  projectId: string;
  lane: Lane;
  readers: string[];
  seen: SeenStep[];
  ran: readonly RanStep[] | undefined;
  /** Each chip's step ids on this project (`chipStepsOf`). */
  steps: ChipSteps;
  live: boolean;
  known: boolean;
  /** `ProjectView.readers` as recorded: a file on a route whose reader is `hello` was not read (IN-116). */
  recorded: Record<string, string> | undefined;
  /** The ids of the drawings something was read off (`readDrawings`): what the lane's count counts. */
  read: ReadonlySet<string>;
}) {
  const routed = lane.id !== 'waiting' && lane.id !== 'other';
  const reading = lane.files.filter((f) => f.state === 'running');
  const now = reading.map(nowStep).filter((s): s is SeenStep => s !== null);
  const shown = lane.files.slice(0, LANE_ROWS);
  const more = lane.files.length - shown.length;
  // each drawing read once, as "Drawings ready" counts them (a copy of a file is the same drawing; IN-126)
  const found = new Set(
    lane.files.flatMap((f) =>
      isFinished(f) &&
      f.drawing_id &&
      read.has(f.drawing_id) &&
      (!f.source || f.source === f.path) &&
      !unread(f, recorded)
        ? [f.drawing_id]
        : [],
    ),
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
              routed && found.size > 0 ? plural(found.size, 'drawing') + ' read' : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </div>
        {routed &&
          (readers.length > 0 || seen.length > 0 ? (
            <ReaderChips
              readers={readers}
              seen={seen}
              now={now}
              ran={ran}
              settled={lane.files.every(isFinished)}
              known={steps}
            />
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
  const steps = chipStepsOf(project.readers);
  const all = lanes(project.files);
  const sorting = triageReaders(project.readers);
  const read = new Set(readDrawings(project).map((d) => d.drawing_id));
  if (all.length === 0) return null;
  return (
    <section aria-label="Routes" className="grid content-start gap-3">
      <h3 className="v-caption m-0">How each file is read</h3>
      {sorting.length > 0 && (
        <div className="ingest-sorting grid gap-1.5">
          <p className={cn(MUTED, 'm-0')}>Every file first, before it takes a route:</p>
          <Tip text={PIPELINE_TIPS.triage} wrap className="justify-self-start">
            <ul aria-label="Sorting" className="flex flex-wrap gap-1.5">
              {sorting.map((c) => {
                const said = triageRan(c, project);
                // once its step can no longer run, a chip whose step did not run says why (IN-127, as IN-124)
                const why =
                  (said === 'skipped' || said === 'absent') && triageEnded(c, project)
                    ? DIMMED[said]
                    : null;
                return (
                  <Chip
                    key={c}
                    words={c}
                    running={said === 'running'}
                    why={why}
                    ran={said === 'ran'}
                  />
                );
              })}
            </ul>
          </Tip>
        </div>
      )}
      {all.map((lane) => (
        <LaneView
          key={lane.id}
          projectId={projectId}
          lane={lane}
          readers={lane.id in byRoute ? byRoute[lane.id as keyof typeof byRoute] : []}
          seen={[...(seen.get(lane.id)?.values() ?? [])]}
          ran={project.ran?.[lane.id]}
          steps={steps}
          live={isLive(project)}
          known={project.readers !== undefined}
          recorded={project.readers}
          read={read}
        />
      ))}
    </section>
  );
}
