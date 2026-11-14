import type { FileStatus, Normalised, ProjectView, StageTrace } from '../api';

type FileState = FileStatus['state'];
type Stage = StageTrace['stage'];

/** The pipeline stages in API order (docs/API.md "…/trace"). */
export const STAGES: readonly Stage[] = [
  'unpack',
  'hash',
  'identify',
  'group',
  'route',
  'cache',
  'normalise',
  'extract',
  'second_count',
  'takeoff',
  'write',
];

export const STAGE_LABEL: Record<Stage, string> = {
  unpack: 'Unpack',
  hash: 'Hash',
  identify: 'Identify',
  group: 'Group',
  route: 'Route',
  cache: 'Cache',
  normalise: 'Normalise',
  extract: 'Extract',
  second_count: 'Second count',
  takeoff: 'Takeoff',
  write: 'Store',
};

/** File kinds (API.md "File kind") in words; an unknown id is shown as sent. */
const KIND_LABEL: Record<string, string> = {
  pdf_vector: 'PDF vector',
  pdf_scan: 'PDF scan',
  pdf_text: 'text PDF',
  pdf_encrypted: 'encrypted PDF',
  png_plan: 'PNG plan',
  jpeg_plan: 'JPEG plan',
  photo_plan: 'photo of a plan',
  ifc: 'IFC model',
  dxf: 'DXF',
  svg: 'SVG',
  dwg: 'DWG',
  office: 'office document',
  unknown: 'unknown file type',
};

export function kindLabel(kind: string | null | undefined): string {
  return kind ? (KIND_LABEL[kind] ?? kind) : 'not identified';
}

const ROUTE_LABEL: Record<string, string> = {
  bim: 'BIM model',
  cad: 'CAD',
  vector: 'drawn PDF',
  raster: 'image',
};

/** A route id (`FileStatus.route`) in words, "drawn PDF route"; an unknown id as sent. */
export function routeLabel(route: string | null | undefined): string {
  return `${route ? (ROUTE_LABEL[route] ?? route) : 'no'} route`;
}

/** Word and icon per file state: status is never shown by colour alone. */
export const STATE_LABEL: Record<FileState, { word: string; icon: string }> = {
  queued: { word: 'queued', icon: '…' },
  running: { word: 'running', icon: '◌' },
  ready: { word: 'ready', icon: '✓' },
  flagged: { word: 'flagged', icon: '!' },
  text_only: { word: 'text only', icon: '¶' },
  set_aside: { word: 'set aside', icon: '–' },
};

export const PROJECT_STATE_LABEL: Record<string, string> = {
  queued: 'Waiting to start',
  running: 'Analysing now',
  done: 'Analysis done', // the demo's kicker (IN-84)
  failed: 'Ingest failed',
};

export function isFinished(file: Pick<FileStatus, 'state'>): boolean {
  return file.state !== 'queued' && file.state !== 'running';
}

export function progressOf(files: readonly Pick<FileStatus, 'state'>[]): {
  done: number;
  total: number;
} {
  return { done: files.filter(isFinished).length, total: files.length };
}

/**
 * The pipeline's steps in the backend's order, each named by its stage (ingest.md "Pipeline steps v4"). Index has
 * no stage: the backend's last phase (triage's judge, the evidence step and index) runs once every file is finished.
 */
export const STEPS: readonly { name: string; hint: string; stages: readonly (Stage | null)[] }[] = [
  {
    name: STAGE_LABEL.unpack,
    hint: 'opening the upload safely, one fingerprint per file',
    stages: ['unpack', 'hash', null],
  },
  {
    name: STAGE_LABEL.identify,
    hint: 'what each file is, and whether it is a floor plan',
    stages: ['identify'],
  },
  {
    name: STAGE_LABEL.route,
    hint: 'one source per drawing: the model, the drawn PDF or the image',
    stages: ['group', 'route', 'cache'],
  },
  {
    name: STAGE_LABEL.normalise,
    hint: 'one page frame per sheet; photos made upright and flat',
    stages: ['normalise'],
  },
  {
    name: STAGE_LABEL.extract,
    hint: 'rooms, doors, windows, fixtures, scale and schedules',
    stages: ['extract'],
  },
  {
    name: STAGE_LABEL.second_count,
    hint: 'the same quantities measured another way',
    stages: ['second_count'],
  },
  {
    name: STAGE_LABEL.takeoff,
    hint: 'counting rules applied, every quantity worked out',
    stages: ['takeoff'],
  },
  {
    name: STAGE_LABEL.write,
    hint: 'one drawing model per drawing, with its marks',
    stages: ['write'],
  },
  { name: 'Index', hint: 'every file made searchable for questions', stages: [] },
];

/** The step (1-8) a stage belongs to; no stage yet is step 1. No stage is in Index (9). */
export function stepOf(stage: Stage | null | undefined): number {
  return STEPS.findIndex((s) => s.stages.includes(stage ?? null)) + 1;
}

type Staged = Pick<FileStatus, 'stage' | 'state'>;

/** The lowest step of a file not finished; 1 with no files, Index (the last) when every file is finished. */
export function activeStep(files: readonly Staged[]): number {
  if (files.length === 0) return 1;
  const live = files.filter((f) => !isFinished(f)).map((f) => stepOf(f.stage));
  return live.length ? Math.min(...live) : STEPS.length;
}

/** For one step: files that reach it (`through`) and those already past it (`passed`). */
export function stepFiles(
  files: readonly Staged[],
  step: number,
): { passed: number; through: number } {
  const at = (f: Staged) => stepOf(f.stage);
  return {
    through: files.filter((f) => !(isFinished(f) && at(f) < step)).length,
    passed: files.filter((f) => at(f) > step || (isFinished(f) && at(f) === step)).length,
  };
}

export function percentDone(files: readonly Pick<FileStatus, 'state'>[]): number {
  const { done, total } = progressOf(files);
  return total === 0 ? 0 : Math.round((100 * done) / total);
}

export const isLive = (p: Pick<ProjectView, 'state'>) =>
  p.state === 'queued' || p.state === 'running';

/** Poll while the project runs, or a done project's file is read again (file-triage.md FT-20). */
export const keepPolling = (p: ProjectView) =>
  isLive(p) || (p.state === 'done' && !p.files.every(isFinished)); // a failed one's queued files never move

/** Elapsed ms: the project's `ms` once ingest ends; while live, `now − started_at` (never below 0); null before it starts. */
export function elapsedMs(p: ProjectView, now: number): number | null {
  if (!isLive(p)) return p.ms;
  return p.started_at ? Math.max(0, now - Date.parse(p.started_at)) : null;
}

/** "1 file", "0 files", "2 files". */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}

export function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return `${ms >= 10 ? ms.toFixed(1) : ms.toFixed(2)} ms`;
}

export function formatCost(usd: number): string {
  if (usd > 0 && usd < 0.01) return '<$0.01';
  return `$${usd.toFixed(2)}`;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** What normalisation did to an image, one line each; empty when nothing was corrected. */
export function normalisedSteps(n: Normalised): string[] {
  const steps: string[] = [];
  if (n.exif != null && n.exif !== 1) steps.push(`EXIF orientation ${String(n.exif)} applied`);
  if (n.rotated !== 0) steps.push(`turned ${String(n.rotated)}°`);
  if (n.deskew_deg !== 0) steps.push(`deskewed ${String(n.deskew_deg)}°`);
  if (n.rectified) steps.push(`perspective corrected${n.rectifier ? ` (${n.rectifier})` : ''}`);
  return steps;
}
