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
              steps: [],
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

// shortcut: #251 has no API fixture with a sheet (file-triage.md FT-24); replace with its fixture if one lands.
export const sheet: NonNullable<Triage['sheet']> = {
  advanced: false,
  advanced_why: null,
  confidence: 0.04,
  decision: 'set_aside',
  kind: 'elevation',
  kind_words: 'an elevation',
  model: 'gemini-4-carbon',
  printed_scale: '1:100',
  seen: 'an elevation sheet',
  sheet_number: 'A-201',
  takeoff_possible: false,
  title: 'South elevation',
};

/**
 * The demo's readers as ingest records them: the live site's config, copied from a real finished run
 * (`.agents/ingest-ui/sample-trace.json`, trace, 2026-11-15; backend composition `build_ingest` `names`).
 */
export const DEMO_READERS = {
  bim: 'ifc',
  cad: 'hello',
  vector: 'pdf',
  raster: 'composite',
  raster_components:
    'elements=decisions-s1536:detector-v8:C-yolo26l,plans=decisions-s1536:detector-v8:C-yolo26l,' +
    'door=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,window=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,' +
    'sink=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,toilet=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,' +
    'shower=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,bathtub=arbiter-t1:C-yolo26l:C-yolo26l-onnx-val,' +
    'rooms=regionrooms',
  tables: 'pdf',
  second_counter: 'ifc',
  rectifier: 'r3',
  decisions_kind: 'True',
  raster_scale: 'priors',
  raster_printed_scale: 'carbon',
  room_words: 'swiss+generic:v1',
  floor_plans: 'rooms:v2',
  double_check_readers: 'l1=detector:C-yolo26l,m1=detector:C-yolo26m',
  carbon_reader: 'large+few3+snap+storey:dcb03cd7955c',
  carbon_levels: 'demote:dcb03cd7955c',
  triage: 'classifier=off, sheet_kind=carbon, describer=carbon, judge=rules',
  evidence_scope: 'all_non_plan',
};

/** The image route's chips on the demo readers, in the order they run. */
export const RASTER_CHIPS = [
  'photo flattening',
  'printed scale (Gemini)',
  'Gemini cross-check (not counted)',
  'symbol detector',
  'Gemini count decision',
  'count arbiter',
  'room reader',
  'double check by 2 more readers (not counted)',
  'Gemini for sheets with few symbols',
  'scale from door sizes',
];

/** The step labels real files reported on the demo config, by route (sample-trace.json, extract stage). */
export const LIVE_STEPS = {
  raster: [
    'Printed scale and counts (Gemini Carbon)',
    'Gemini Carbon check (never counted)',
    'Gemini Decisions count swap (1536 px) over Symbol detector, 8 views',
    'Symbol detector, 8 views + count arbiter',
    'Symbol detector (arbiter base)',
    'Room reader (Gemini + region model)',
    'Double-check reader l1: Symbol detector',
    'Double-check reader m1: Symbol detector',
    'Symbol detector (arbiter second read)',
    'Count arbiter (L1 page counts)',
    'Gemini Carbon reader (things drawn)',
  ],
  vector: ['Drawn-PDF reader (Swiss plan rules)', 'Schedule tables (PDF)'],
  bim: ['IFC model reader'],
};
