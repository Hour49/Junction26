// Pure parts of the Advanced view (docs/specs/frontend/advanced-ingest.md). The step list and the stage-to-step
// mapping are screen 2's (`STEPS`, `stepOf`, `activeStep` in src/ingest/ingest.ts), so both views agree.
import type {
  DrawingView,
  FileStatus,
  FileTrace,
  ProjectView,
  Row,
  StepTrace,
  Takeoff,
} from '../api';
import {
  STAGE_LABEL,
  STEPS,
  activeStep,
  isFinished,
  kindLabel,
  routeLabel,
  stepOf,
} from '../ingest/ingest';

export type Visual = 'files' | 'lanes' | 'plan' | 'pairs' | 'ready';

type RouteId = 'bim' | 'cad' | 'vector' | 'raster';

export interface StepView {
  heading: string;
  visual: Visual;
  explain: string;
  /** What the step does on each route, where the routes differ (advanced-ingest.md "Per-route lines"). */
  routes?: Partial<Record<RouteId, string>>;
}

/** Per step (index 0 = step 1): heading, visual, explanation and per-route lines, true for the backend today. */
export const STEP_VIEW: readonly StepView[] = [
  {
    heading: 'Unpacking',
    visual: 'files',
    explain:
      'Every file in the upload is listed with its size and sha256, and every path is checked to stay inside the project folder. Each drawn page of a PDF set becomes a file of its own.',
  },
  {
    heading: 'Identifying',
    visual: 'lanes',
    explain:
      "The format comes from each file's first bytes, not its name. A picture is asked whether it is a floor plan: a doubtful sheet is read and flagged, anything else is set aside with a description.",
  },
  {
    heading: 'Routing',
    visual: 'lanes',
    explain:
      'Files of the same plan are grouped, and each plan is read once from its richest file: an IFC model, then CAD, then a drawn PDF, then an image. A scanned PDF is read as an image. A plan read before is reused.',
  },
  {
    heading: 'Normalising',
    visual: 'plan',
    explain: 'Each sheet gets one page frame, and every mark and box is placed in it.',
    routes: {
      bim: 'A model has no page: nothing to place.',
      vector: 'Pages are taken as the PDF gives them.',
      raster: "Turned upright by its EXIF tag; a phone photo is flattened to its paper's corners.",
    },
  },
  {
    heading: 'Extracting',
    visual: 'plan',
    explain:
      'Rooms, doors, windows and fixtures are read from the drawing, with its scale. A class the reader does not read gets no count, not a zero.',
    routes: {
      bim: 'Every object is listed with its GlobalId: spaces, storeys, doors, windows, fixtures.',
      vector:
        "Read from the PDF's text and lines: rooms with areas, doors, windows, fixtures, the printed scale and schedule tables.",
      raster:
        "A symbol detector and room readers read it; a large or sparse sheet is also counted by Gemini Carbon and flagged; more readers count again to set each count's level.",
    },
  },
  {
    heading: 'Counting a second way',
    visual: 'pairs',
    explain:
      'Quantities that can be measured a second way are measured again by an independent method. When the two disagree, it goes to you as a conflict.',
    routes: {
      bim: 'A model is what the sheets are checked against; it has no second count of its own.',
      vector:
        'The scale text against the scale bar, the room areas printed on the sheet, and the sheet against its IFC model.',
      raster: 'The printed scale and any printed totals against what was read.',
    },
  },
  {
    heading: 'Working out the quantities',
    visual: 'ready',
    explain:
      'The counting rules are applied and every quantity of the plan is computed in advance, with the marks it comes from, so questions are answered from it straight away.',
  },
  {
    heading: 'Storing the drawing model',
    visual: 'plan',
    explain:
      'One drawing model per plan is stored, with the marks that show where each quantity comes from.',
  },
  {
    heading: 'Indexing for questions',
    visual: 'files',
    explain:
      "Once every file is through, each set-aside file is judged against the project, the files that are not plans are described or their text read, and everything goes into the project's search index for the chat.",
  },
];

const ROUTE_ORDER: readonly RouteId[] = ['bim', 'cad', 'vector', 'raster'];

/** The step's per-route lines for the routes some file of the project is on, route in words ("drawn PDF route"). */
export function routeLines(
  view: StepView,
  project: ProjectView,
): { route: string; line: string }[] {
  const on = new Set(project.files.map((f) => f.route));
  return ROUTE_ORDER.flatMap((r) => {
    const line = view.routes?.[r];
    return line && on.has(r) ? [{ route: routeLabel(r), line }] : [];
  });
}

export type StepStatus = 'working' | 'waiting' | 'done' | 'none';

export const STATUS_WORD: Record<StepStatus, string> = {
  working: 'working',
  waiting: 'waiting',
  done: 'done',
  none: 'no file got here',
};

const running = (p: ProjectView) => p.state === 'queued' || p.state === 'running';

/** Index: the one step with no stage, the backend's last phase. */
const isIndex = (k: number) => STEPS[k - 1]?.stages.length === 0;

/** Step `k` from the files' latest stages alone (spec "Step status"). */
export function stepStatus(
  project: ProjectView,
  k: number,
): { status: StepStatus; setAside: number } {
  if (isIndex(k)) {
    if (project.state === 'done' || project.state === 'failed')
      return {
        status: project.state === 'done' && project.files.length ? 'done' : 'none',
        setAside: 0,
      };
    const through = project.files.length > 0 && project.files.every(isFinished);
    return { status: through ? 'working' : 'waiting', setAside: 0 };
  }
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

/** The panel shown before the user picks one: the current step, else Takeoff (what is ready to ask). */
export function defaultStep(project: ProjectView): number {
  return currentStep(project) ?? 7;
}

export interface LogLine {
  key: string;
  /** The line's first word(s): the stage, "Index", or an index step's name. */
  head: string;
  /** The file the line is about; "" for a step of the project's index phase. */
  path: string;
  /** What the stage did: `output`, or `did` when empty; a cache line reads "Cached: <did>". */
  what: string;
  text: string;
  failure: string | null;
  cost: number;
}

/** One step of the project's index phase as a log line, "<label> <did>" (AD-125). */
function indexStepLine(s: StepTrace, i: number): LogLine {
  const failed = s.state === 'failed';
  const what = failed ? '' : s.state === 'skipped' ? `skipped${s.did ? `: ${s.did}` : ''}` : s.did;
  return {
    key: `index-${String(i)}-${s.id}`,
    head: s.label,
    path: '',
    what,
    text: what ? `${s.label} ${what}` : s.label,
    failure: failed ? s.did || 'no reason given' : null,
    cost: s.cost_usd,
  };
}

/**
 * Every trace entry of step `k` over the files, in file order then stage order. Index: each file's evidence, then
 * the steps of the project's index phase (`after`, `index_steps`) in their order, so the last line is the latest.
 */
export function stepLines(
  files: readonly FileStatus[],
  traces: ReadonlyMap<string, FileTrace>,
  k: number,
  after: readonly StepTrace[] = [],
): LogLine[] {
  if (isIndex(k))
    return [
      ...files.flatMap(({ id, path, evidence }) =>
        evidence
          ? [
              {
                key: `${id}-index`,
                head: 'Index',
                path,
                what: evidence.why,
                text: `Index ${path} ${evidence.why}`,
                failure: null,
                cost: evidence.cost_usd,
              },
            ]
          : [],
      ),
      ...after.map(indexStepLine),
    ];
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
          head: STAGE_LABEL[s.stage],
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
  /** One of the takeoff's `disputes` (a disagreement counted once); without `disputes`, `status === 'conflict'`. */
  disputed: boolean;
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

/**
 * Every quantity measured twice, disagreements first, then takeoff order; named by this project's files. A
 * conflict row not in `Takeoff.disputes` repeats another row's disagreement (a storey or a room's other name) and is
 * left out (AV-34); a takeoff without `disputes` (older backend) keeps every conflict row.
 */
export function pairsOf(takeoffs: readonly Takeoff[], project: ProjectView): Pair[] {
  const pairs = takeoffs.flatMap((t) => {
    const disputes = t.disputes as readonly string[] | undefined;
    return t.quantities
      .filter((row) => row.second != null)
      .map((row) => ({
        row,
        file: fileName(project, t.drawing_id),
        drawingId: t.drawing_id,
        disputed: disputes ? disputes.includes(row.key) : row.status === 'conflict',
      }))
      .filter((p) => p.disputed || !disputes || p.row.conflict == null);
  });
  return [...pairs.filter((p) => p.disputed), ...pairs.filter((p) => !p.disputed)];
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
