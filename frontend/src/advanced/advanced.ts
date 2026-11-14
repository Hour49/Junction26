// Pure parts of the Advanced view (docs/specs/frontend/advanced-ingest.md). The step list and the stage-to-step
// mapping are screen 2's (`STEPS`, `stepOf`, `activeStep` in src/ingest/ingest.ts), so both views agree.
import type { DrawingView, FileStatus, FileTrace, ProjectView, Row, Takeoff } from '../api';
import {
  STAGE_LABEL,
  activeStep,
  isFinished,
  kindLabel,
  routeLabel,
  stepOf,
} from '../ingest/ingest';

export type Visual = 'files' | 'lanes' | 'plan' | 'pairs' | 'ready';

/** Per step (index 0 = step 1): heading, visual and the one-sentence explanation, true for the backend today. */
export const STEP_VIEW: readonly { heading: string; visual: Visual; explain: string }[] = [
  {
    heading: 'Unpacking',
    visual: 'files',
    explain:
      'Every file in the upload is listed with its size and sha256, and every path is checked to stay inside the project folder.',
  },
  {
    heading: 'Identifying',
    visual: 'lanes',
    explain:
      "The format comes from each file's first bytes, not its name. Files with the same folder and name are one plan.",
  },
  {
    heading: 'Routing',
    visual: 'lanes',
    explain:
      'Each plan is read from its richest file: a BIM model, then CAD, then a drawn PDF, then an image. A file read before is reused.',
  },
  {
    heading: 'Normalising',
    visual: 'plan',
    explain: 'Each sheet gets one page frame, and every mark and box is placed in it.',
  },
  {
    heading: 'Extracting',
    visual: 'plan',
    explain:
      'Rooms, doors, windows and fixtures are read from the drawing, with its scale. A class the reader does not read gets no count, not a zero.',
  },
  {
    heading: 'Cross\u2011checking', // a non-breaking hyphen: the heading never breaks at it
    visual: 'pairs',
    explain:
      'Quantities that can be measured a second way are measured again by an independent method. When the two disagree, it goes to you as a conflict.',
  },
  {
    heading: 'Indexing',
    visual: 'ready',
    explain:
      'The counting rules are applied and every quantity of the plan is computed in advance, so questions are answered from it straight away.',
  },
  {
    heading: 'Storing the drawing model',
    visual: 'plan',
    explain:
      'One drawing model per plan is stored, with the marks that show where each quantity comes from.',
  },
];

export type StepStatus = 'working' | 'waiting' | 'done' | 'none';

export const STATUS_WORD: Record<StepStatus, string> = {
  working: 'working',
  waiting: 'waiting',
  done: 'done',
  none: 'no file got here',
};

const running = (p: ProjectView) => p.state === 'queued' || p.state === 'running';

/** Step `k` (1-8) from the files' latest stages alone (spec "Step status"). */
export function stepStatus(
  project: ProjectView,
  k: number,
): { status: StepStatus; setAside: number } {
  const at = (f: FileStatus) => stepOf(f.stage ?? null);
  const open = project.files.filter((f) => !isFinished(f));
  const reached = project.files.some((f) => f.stage != null && at(f) >= k);
  const setAside = project.files.filter(
    (f) => f.state === 'set_aside' && f.stage != null && at(f) === k,
  ).length;
  let status: StepStatus;
  if (open.some((f) => at(f) === k)) status = 'working';
  else if (open.some((f) => at(f) < k) || (running(project) && !reached)) status = 'waiting';
  else status = reached ? 'done' : 'none';
  return { status, setAside };
}

/** The step the pipeline is at, or null once the project is done or failed. */
export function currentStep(project: ProjectView): number | null {
  return running(project) ? activeStep(project.files) : null;
}

/** The panel shown before the user picks one: the current step, else Index (what is ready to ask). */
export function defaultStep(project: ProjectView): number {
  return currentStep(project) ?? 7;
}

export interface LogLine {
  key: string;
  path: string;
  /** What the stage did: `output`, or `did` when empty; a cache line reads "Cached: <did>". */
  what: string;
  text: string;
  failure: string | null;
  cost: number;
}

/** Every trace entry of step `k` over the files, in file order then stage order. */
export function stepLines(
  files: readonly FileStatus[],
  traces: ReadonlyMap<string, FileTrace>,
  k: number,
): LogLine[] {
  return files.flatMap((file) =>
    (traces.get(file.id)?.stages ?? [])
      .filter((s) => stepOf(s.stage) === k)
      .map((s, i) => {
        // the output in words; an output that is just the file's own path says nothing, so `did` (AV-29)
        const out = s.output === file.path ? '' : s.output;
        const said =
          s.stage === 'identify' && out
            ? kindLabel(out)
            : s.stage === 'route' && out
              ? routeLabel(out)
              : out || s.did;
        const what = shortHashes(s.stage === 'cache' ? `Cached: ${s.did}` : said);
        return {
          key: `${file.id}-${String(i)}-${s.stage}`,
          path: file.path,
          what,
          text: `${STAGE_LABEL[s.stage]} ${file.path} ${what}`,
          failure: s.failure ?? null,
          cost: s.cost_usd,
        };
      }),
  );
}

/** The file each drawing entry is read from (so another rendering of the same plan is not counted twice). */
export function drawingFiles(project: ProjectView): FileStatus[] {
  return project.drawings.flatMap((d) =>
    project.files.filter((f) => f.path === d.file).slice(0, 1),
  );
}

/** Rooms, doors and windows over the drawings; null for a class no drawing has (not read, never 0). */
export function planCounts(project: ProjectView): {
  room: number | null;
  door: number | null;
  window: number | null;
  drawings: number;
} {
  const files = drawingFiles(project);
  const sum = (key: string) => {
    const values = files.flatMap((f) => (f.takeoff?.[key] === undefined ? [] : [f.takeoff[key]]));
    return values.length ? values.reduce((a, b) => a + b, 0) : null;
  };
  return {
    room: sum('room'),
    door: sum('door'),
    window: sum('window'),
    drawings: project.drawings.length,
  };
}

/** How many quantities the drawings have ready. */
export function quantityCount(project: ProjectView): number {
  return drawingFiles(project).reduce((n, f) => n + Object.keys(f.takeoff ?? {}).length, 0);
}

export interface Pair {
  row: Row;
  file: string;
  drawingId: string;
}

/**
 * This project's name for a drawing: its file's path here. Drawings are content-addressed and shared between
 * projects, so `Takeoff.file`/`DrawingView.file` may be another project's path for the same bytes.
 */
export function fileName(project: ProjectView, drawingId: string): string {
  return (
    project.files.find((f) => f.drawing_id === drawingId)?.path ??
    project.drawings.find((d) => d.drawing_id === drawingId)?.file ??
    drawingId
  );
}

/** Every quantity measured twice, conflicts first, then takeoff order; named by this project's files. */
export function pairsOf(takeoffs: readonly Takeoff[], project: ProjectView): Pair[] {
  const pairs = takeoffs.flatMap((t) =>
    t.quantities
      .filter((row) => row.second != null)
      .map((row) => ({ row, file: fileName(project, t.drawing_id), drawingId: t.drawing_id })),
  );
  return [
    ...pairs.filter((p) => p.row.status === 'conflict'),
    ...pairs.filter((p) => p.row.status !== 'conflict'),
  ];
}

/** Elapsed: the run's `ms` once done or failed; now - `started_at` while it runs; null before it starts. */
export function elapsedMs(project: ProjectView, now: number): number | null {
  if (project.state === 'done' || project.state === 'failed') return project.ms;
  return project.started_at ? Math.max(0, now - Date.parse(project.started_at)) : null;
}

/** The Identify chip for a page's scale as read (`PageView.scale`); null when there is nothing to say. */
export function scaleChip(scale: DrawingView['pages'][number]['scale'] | undefined): string | null {
  if (!scale) return null;
  if (scale.status === 'no_scale') return 'No scale found';
  if (scale.status === 'not_to_scale') return 'Not to scale';
  const text = scale.text ?? (scale.ratio ? `1:${String(scale.ratio)}` : null);
  if (!text) return null;
  return scale.status === 'estimated' ? `Scale ${text} estimated` : `Scale ${text} found`;
}

/** A sha256 in a trace line, cut to its first 12 characters as the trace facts show it. */
export function shortHashes(text: string): string {
  return text.replace(/\b[0-9a-f]{64}\b/g, (h) => `${h.slice(0, 12)}…`);
}

// The kinds the backend previews (backend/app/api/projects.py PREVIEW_KINDS): images, and a PDF's first page.
const PREVIEW_KINDS: ReadonlySet<string> = new Set([
  'pdf_vector',
  'pdf_scan',
  'pdf_text',
  'png_plan',
  'jpeg_plan',
  'photo_plan',
  'photo',
  'pdf_encrypted',
]);

/** Null when the file's `preview.png` exists; else the line shown in its place (never a broken image). */
export function previewNote(file: FileStatus): string | null {
  if (file.kind == null) return 'Not identified yet';
  if (PREVIEW_KINDS.has(file.kind)) return null;
  return file.kind === 'ifc'
    ? 'A model: no picture to show'
    : `${kindLabel(file.kind)}: no preview`;
}
