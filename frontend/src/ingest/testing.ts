// Test helpers for the ingest screens: derived fixtures (docs/specs/frontend/ingest.md "Variants") and a flush.
import { act } from '@testing-library/react';
import { project, projectList, projectTriaged, trace } from '../api/fixtures';
import type { FileStatus, FileTrace, ProjectView, Triage } from '../api';

/** The value, or a thrown error naming what was missing. */
export function must<T>(value: T | null | undefined): T {
  if (value == null) throw new Error('expected a value');
  return value;
}

/** Let pending fetches and renders settle without moving the (fake) clock. */
export async function flush(rounds = 5) {
  for (let i = 0; i < rounds; i++) {
    await act(() => new Promise<void>((resolve) => setImmediate(resolve)));
  }
}

function withFile(index: number, changes: Partial<FileStatus>): FileStatus[] {
  return project.files.map((f, i) => (i === index ? { ...f, ...changes } : f));
}

const f2 = project.files[2];

export const variants = {
  listEmpty: { ...projectList, projects: [] },
  running: {
    ...project,
    state: 'running',
    ms: 0,
    finished_at: null,
    files: withFile(2, { state: 'running', stage: 'extract', reason: '', drawing_id: null }),
    drawings: project.drawings.filter((d) => d.drawing_id !== f2?.drawing_id),
  } as ProjectView,
  queued: {
    ...project,
    state: 'queued',
    ms: 0,
    started_at: null,
    finished_at: null,
    expected_drawings: null,
    files: project.files.map((f) => ({
      ...f,
      state: 'queued' as const,
      stage: null,
      kind: null,
      drawing_id: null,
      reason: '',
    })),
    drawings: [],
  } as ProjectView,
  setAside: {
    ...project,
    files: withFile(0, {
      state: 'set_aside',
      reason: 'not a drawing',
      stage: 'identify',
      drawing_id: null,
    }),
  },
  textOnly: {
    ...project,
    files: withFile(0, {
      state: 'text_only',
      kind: 'text',
      reason: 'text and no drawing',
      drawing_id: null,
    }),
  },
  reusedNoKind: { ...project, files: withFile(0, { reused: true, kind: null }) },
  noDrawings: { ...project, drawings: [] },
  noFiles: { ...project, files: [], drawings: [] },
  failed: {
    ...project,
    state: 'failed',
    error: 'the server restarted during ingest',
  } as ProjectView,
};

const f1 = must(project.files[1]);
const image: FileTrace = { ...trace, file: f1 };

export const traceVariants = {
  running: {
    ...trace,
    file: { ...trace.file, state: 'running', stage: 'extract' },
    stages: trace.stages.slice(0, 7),
  } as FileTrace,
  failed: {
    ...trace,
    stages: trace.stages
      .slice(0, 7)
      .map((s, i) => (i === 6 ? { ...s, failure: 'no page could be read' } : s)),
    file: {
      ...trace.file,
      state: 'set_aside',
      reason: 'no page could be read',
      drawing_id: null,
    },
  } as FileTrace,
  cache: {
    ...trace,
    file: { ...trace.file, reused: true },
    stages: trace.stages.flatMap((s) =>
      s.stage === 'route'
        ? [
            s,
            {
              stage: 'cache' as const,
              did: 'ingested before in another project',
              ms: 0,
              output: '',
              failure: null,
              cost_usd: 0,
            },
          ]
        : [s],
    ),
  },
  image,
  rotated: {
    ...image,
    file: {
      ...f1,
      normalised: { ...must(f1.normalised), exif: 6, rotated: 90, deskew_deg: 1.5 },
    },
  },
};

// File triage (docs/specs/frontend/file-triage.md "Variants").
export const triaged = projectTriaged;

const withTriage = (p: ProjectView, index: number, changes: Partial<Triage>): FileStatus[] =>
  p.files.map((f, i) =>
    i === index && f.triage ? { ...f, triage: { ...f.triage, ...changes } } : f,
  );

const site = must(must(triaged.files[2]).triage);

export const triagedVariants = {
  running: {
    ...triaged,
    state: 'running',
    not_plans: null,
    files: triaged.files.map((f, i) =>
      f.triage && i !== 3
        ? {
            ...f,
            triage: {
              ...f.triage,
              relevance: null,
              overruled: null,
              verdict: null,
              note: 'not judged yet: the project is still being read',
            },
          }
        : f,
    ),
  } as ProjectView,
  unsure: {
    ...triaged,
    files: withTriage(triaged, 2, {
      overruled: null,
      relevance: {
        ...must(site.relevance),
        verdict: 'unsure',
        why: 'no floor plan in the project to compare with',
      },
      verdict: 'unsure',
    }),
  },
  open: { ...triaged, files: withTriage(triaged, 2, { overruled: null, verdict: 'unrelated' }) },
  offline: {
    ...triaged,
    files: withTriage(triaged, 3, {
      note: 'not described: no description model is set up, so it is not judged',
    }),
  },
  notPlansZero: { ...triaged, not_plans: 0 },
};

/** The trace of one triaged file: `trace.json`'s stages up to and including `identify`. */
export const triageTrace = (file: FileStatus): FileTrace => ({
  ...trace,
  file,
  stages: trace.stages.slice(0, trace.stages.findIndex((s) => s.stage === 'identify') + 1),
});
