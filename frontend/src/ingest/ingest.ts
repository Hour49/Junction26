import type { FileStatus, Normalised, StageTrace } from '../api';

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
  write: 'Write',
};

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
  running: 'Reading files',
  done: 'Done',
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

/** How many files have each stage as their latest; `waiting` counts files with no stage yet. */
export function stageCounts(files: readonly Pick<FileStatus, 'stage' | 'state'>[]): {
  waiting: number;
  stages: { stage: Stage; count: number; working: boolean }[];
} {
  return {
    waiting: files.filter((f) => f.stage == null).length,
    stages: STAGES.map((stage) => {
      const here = files.filter((f) => f.stage === stage);
      return { stage, count: here.length, working: here.some((f) => !isFinished(f)) };
    }),
  };
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
