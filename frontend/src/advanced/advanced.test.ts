import { describe, expect, it } from 'vitest';
import { drawing, project, takeoff, trace, traceSetAside } from '../api/fixtures';
import type { FileTrace, ProjectView, Takeoff } from '../api';
import { STEPS } from '../ingest/ingest';
import { variants, must } from '../ingest/testing';
import {
  STEP_VIEW,
  currentStep,
  defaultStep,
  pairsOf,
  planCounts,
  previewNote,
  quantityCount,
  routeLines,
  scaleChip,
  shortHashes,
  stepLines,
  stepStatus,
} from './advanced';

const statuses = (p: ProjectView) => STEPS.map((_, i) => stepStatus(p, i + 1).status);

describe('advanced.ts', () => {
  it('AV-2 STEP_VIEW has a heading, visual and explanation for each of the 9 steps', () => {
    expect(STEPS).toHaveLength(9);
    expect(STEP_VIEW).toHaveLength(9);
    for (const v of STEP_VIEW) {
      expect(v.heading).not.toBe('');
      expect(v.explain.length).toBeGreaterThan(20);
    }
  });

  it('AV-49 Index says only the files triage set aside are judged, not every set-aside file', () => {
    const index = must(STEP_VIEW[8]);
    expect(index.heading).toBe('Indexing for questions');
    expect(index.explain).toContain(
      'the files triage set aside are judged against the project (a file set aside for another reason, such as a failed read or a second copy, is not)',
    );
    for (const v of STEP_VIEW) expect(v.explain).not.toMatch(/each set-aside file/i);
  });

  it('AV-3 a done project: every step done', () => {
    expect(statuses(project)).toEqual(Array(9).fill('done'));
  });

  it('AV-3 running: steps before the working one done, it working, after it waiting', () => {
    // variants.running: one file running at extract (step 5), the others finished at write.
    expect(statuses(variants.running)).toEqual([
      'done',
      'done',
      'done',
      'done',
      'working',
      'waiting',
      'waiting',
      'waiting',
      'waiting',
    ]);
  });

  it('AV-3 queued with no stages: Unpack working, the rest waiting; no files while queued: all waiting', () => {
    expect(statuses(variants.queued)[0]).toBe('working');
    expect(statuses(variants.queued).slice(1)).toEqual(Array(8).fill('waiting'));
    const queuedEmpty: ProjectView = { ...project, state: 'queued', files: [], drawings: [] };
    expect(statuses(queuedEmpty)).toEqual(Array(9).fill('waiting'));
  });

  it('AV-3 a file set aside at Route makes no later step waiting; with no other file they are "none"', () => {
    const p: ProjectView = {
      ...project,
      files: [{ ...must(project.files[0]), state: 'set_aside', stage: 'route', drawing_id: null }],
    };
    // Index is the project's own phase: it ran, though no file got past Route
    expect(statuses(p)).toEqual([
      'done',
      'done',
      'done',
      'none',
      'none',
      'none',
      'none',
      'none',
      'done',
    ]);
    expect(stepStatus(p, 3).setAside).toBe(1);
    expect(stepStatus(p, 2).setAside).toBe(0);
    expect(statuses({ ...project, files: [], drawings: [] })).toEqual(Array(9).fill('none'));
  });

  it('currentStep / defaultStep: the active step while running, none and Takeoff when done', () => {
    expect(currentStep(variants.running)).toBe(5);
    expect(defaultStep(variants.running)).toBe(5);
    expect(currentStep(variants.queued)).toBe(1);
    expect(currentStep(project)).toBeNull();
    expect(defaultStep(project)).toBe(7);
    expect(currentStep(variants.failed)).toBeNull();
  });

  it('AV-45 routeLines: only the routes the project is on, as "<route>: <line>"', () => {
    const extract = must(STEP_VIEW[4]);
    expect(routeLines(extract, project)).toEqual([
      { route: 'drawn PDF route', line: must(extract.routes?.vector) },
    ]);
    const mixed: ProjectView = {
      ...project,
      files: [
        { ...must(project.files[0]), route: 'raster' },
        { ...must(project.files[1]), route: 'bim' },
      ],
    };
    expect(routeLines(extract, mixed).map((l) => l.route)).toEqual([
      'BIM model route',
      'image route',
    ]);
    expect(routeLines(must(STEP_VIEW[6]), mixed)).toEqual([]);
    for (const k of [3, 4, 5]) expect(Object.keys(must(STEP_VIEW[k]).routes ?? {})).toHaveLength(3);
  });

  it("AV-47 Index: working once every file is finished while running; its log is each file's evidence", () => {
    const index = STEPS.length;
    expect(stepStatus(variants.running, index).status).toBe('waiting');
    expect(stepStatus({ ...variants.running, files: project.files }, index).status).toBe('working');
    expect(stepStatus(project, index).status).toBe('done');
    expect(stepStatus(variants.failed, index).status).toBe('none');
    const why = 'described as a site photo';
    const files = [
      { ...must(project.files[0]), evidence: { indexed: true, why, cost_usd: 0.005 } },
      must(project.files[1]),
    ];
    expect(stepLines(files, new Map(), index)).toEqual([
      {
        key: `${must(files[0]).id}-index`,
        head: 'Index',
        path: must(files[0]).path,
        what: why,
        text: `Index ${must(files[0]).path} ${why}`,
        failure: null,
        cost: 0.005,
      },
    ]);
  });

  it('AV-8 stepLines: one line per trace entry of the step, file order, failures and cache marked', () => {
    const second: FileTrace = { ...trace, file: { ...trace.file, id: 'f2', path: 'b.pdf' } };
    const traces = new Map([
      ['f1', trace],
      ['f2', second],
    ]);
    const files = [trace.file, second.file];
    const unpack = stepLines(files, traces, 1);
    expect(unpack.map((l) => l.text)).toEqual([
      `Unpack ${trace.file.path} ${must(trace.stages[0]).did}`, // AV-29: output is the path itself
      `Hash ${trace.file.path} ${must(trace.stages[1]).output.slice(0, 12)}…`, // sha256 cut to 12
      `Unpack b.pdf ${must(trace.stages[0]).output}`, // output (plans/flat-a.pdf) is not b.pdf's path
      `Hash b.pdf ${must(trace.stages[1]).output.slice(0, 12)}…`,
    ]);
    const failed = stepLines(
      [traceSetAside.file],
      new Map([[traceSetAside.file.id, traceSetAside]]),
      1,
    );
    expect(failed[0]?.failure).toBe('unsafe path: it could be written outside the project folder');
    const cached: FileTrace = {
      ...trace,
      stages: [
        {
          stage: 'cache',
          did: 'ingested before',
          ms: 0,
          output: '',
          failure: null,
          cost_usd: 0,
          steps: [],
        },
      ],
    };
    expect(stepLines([trace.file], new Map([[trace.file.id, cached]]), 3)[0]?.text).toBe(
      `Cache ${trace.file.path} Cached: ingested before`,
    );
  });

  it('AV-29 stepLines: no path twice, kinds and routes in words', () => {
    const own: FileTrace = {
      ...trace,
      stages: [
        {
          stage: 'unpack',
          did: 'path checked, 9 bytes',
          ms: 0,
          output: 'a.pdf',
          failure: null,
          cost_usd: 0,
          steps: [],
        },
        {
          stage: 'identify',
          did: 'a drawn PDF',
          ms: 0,
          output: 'pdf_vector',
          failure: null,
          cost_usd: 0,
          steps: [],
        },
        {
          stage: 'route',
          did: 'vector, read from a.pdf',
          ms: 0,
          output: 'vector',
          failure: null,
          cost_usd: 0,
          steps: [],
        },
      ],
      file: { ...trace.file, path: 'a.pdf' },
    };
    const traces = new Map([[own.file.id, own]]);
    const text = (k: number) => stepLines([own.file], traces, k).map((l) => l.text);
    expect(text(1)).toEqual(['Unpack a.pdf path checked, 9 bytes']);
    expect(text(2)).toEqual(['Identify a.pdf PDF vector']);
    expect(text(3)).toEqual(['Route a.pdf drawn PDF route']);
  });

  // the real demo run (trace's e2e, project 117d844b5e60): the takeoff stage's output starts with its own name, and
  // a rectified photo's output gives only its page size
  const stageOf = (stage: 'normalise' | 'takeoff', did: string, output: string) => ({
    stage,
    did,
    ms: 1,
    output,
    failure: null,
    cost_usd: 0,
    steps: [],
  });

  it('AD-129 stepLines: a stage output that starts with the stage name does not say it twice', () => {
    const own: FileTrace = {
      ...trace,
      stages: [
        stageOf(
          'takeoff',
          'rules: each-once; takeoff: 141 quantities, 81 above zero',
          'takeoff: 141 quantities, 81 above zero',
        ),
      ],
    };
    expect(stepLines([own.file], new Map([[own.file.id, own]]), 7)[0]?.text).toBe(
      `Takeoff ${own.file.path} 141 quantities, 81 above zero`,
    );
  });

  it('AD-130 stepLines: Normalise says a photo was perspective corrected, not only its page size', () => {
    const photo: FileTrace = {
      ...trace,
      file: {
        ...trace.file,
        path: 'photos/plan-photo.jpg',
        normalised: {
          exif: null,
          rotated: 0,
          deskew_deg: 0,
          rectified: true,
          quad: null,
          width: 1241,
          height: 853,
          rectifier: 'paper edges',
        },
      },
      stages: [
        stageOf(
          'normalise',
          'rectified by paper edges: paper corners at (0.16, 0.18), (0.83, 0.13), (0.89, 0.84), (0.11, 0.88): 1241x853 px; 1 page, page 1 is 1241 x 853 px',
          '1 page, page 1 is 1241 x 853 px',
        ),
      ],
    };
    const line = (f: FileTrace) => stepLines([f.file], new Map([[f.file.id, f]]), 4)[0]?.text;
    expect(line(photo)).toBe(
      'Normalise photos/plan-photo.jpg perspective corrected (paper edges); 1 page, page 1 is 1241 x 853 px',
    );
    // nothing corrected: the page size alone, as before
    const flat = { ...photo, file: { ...photo.file, normalised: null } };
    expect(line(flat)).toBe('Normalise photos/plan-photo.jpg 1 page, page 1 is 1241 x 853 px');
  });

  it('AV-17 planCounts sums room, door, window over drawings only; a key no drawing has is null', () => {
    // project.json: flat-a.pdf and flat-b.pdf are drawings (5 rooms, 2 doors, 2 windows each);
    // flat-a.png is another rendering of flat-a and is not added.
    expect(planCounts(project)).toEqual({ room: 10, door: 4, window: 4, drawings: 6 });
    const noWindows: ProjectView = {
      ...project,
      files: project.files.map((f) => ({ ...f, takeoff: { room: 1 } })),
    };
    expect(planCounts(noWindows).window).toBeNull();
    expect(quantityCount(project)).toBe(282);
  });

  it('AV-19 pairsOf: rows measured twice, conflicts first', () => {
    const agree = {
      ...must(takeoff.quantities[0]),
      key: 'door',
      status: 'agree' as const,
      second: { method: 'ifc_model', value: 2 },
      conflict: null, // an agreeing row has no conflict
    };
    const t: Takeoff = { ...takeoff, quantities: [agree, ...takeoff.quantities] };
    const pairs = pairsOf([t], project);
    expect(pairs.map((p) => [p.row.key, p.row.status])).toEqual([
      ['area:room|name=1.01', 'conflict'],
      ['door', 'agree'],
    ]);
    const own = must(project.files.find((f) => f.drawing_id === takeoff.drawing_id));
    expect(pairs[0]?.file).toBe(own.path);
  });

  it('AV-34 pairsOf counts Takeoff.disputes: a conflict twin not in disputes is left out', () => {
    const real = must(takeoff.quantities.find((r) => r.status === 'conflict'));
    const twin = { ...real, key: 'area:room|name=Küche' }; // the same room under its other name
    const t: Takeoff = { ...takeoff, quantities: [real, twin], disputes: [real.key] };
    const pairs = pairsOf([t], project);
    expect(pairs.map((p) => [p.row.key, p.disputed])).toEqual([[real.key, true]]);
    // an older backend sends no disputes: every conflict row counts, as before
    const old = { ...t, disputes: undefined } as unknown as Takeoff;
    expect(pairsOf([old], project).filter((p) => p.disputed)).toHaveLength(2);
  });

  it('AD-131 pairsOf counts a room measured twice once, though the takeoff lists it by number and by name', () => {
    // the real demo run: plans/flat-a.pdf lists each room's area as name=1.02 and name=reduit, the same marks and
    // the same two values; its trace says 5 quantities measured twice, not 10
    const real = must(takeoff.quantities.find((r) => r.status === 'conflict'));
    const room = {
      ...real,
      key: 'area:room|name=1.02',
      label: 'area of room (name Reduit · 1.02)',
      status: 'agree' as const,
      first: { method: 'polygon_x_scale', value: 2.489 },
      second: { method: 'printed_label', value: 2.49 },
      conflict: null,
      marks: [
        {
          ...must(real.marks[0]),
          page: 1,
          box: [0.25, 0.2, 0.33, 0.3] as [number, number, number, number],
        },
      ],
    };
    const byName = { ...room, key: 'area:room|name=reduit', label: 'area of room (name Reduit)' };
    // another room with the same area but its own marks is its own pair
    const other = {
      ...room,
      key: 'area:room|name=1.03',
      marks: [
        {
          ...must(real.marks[0]),
          page: 1,
          box: [0.5, 0.1, 0.6, 0.3] as [number, number, number, number],
        },
      ],
    };
    const t: Takeoff = { ...takeoff, quantities: [room, byName, other], disputes: [] };
    expect(pairsOf([t], project).map((p) => p.row.key)).toEqual([room.key, other.key]);
  });

  it("pairsOf names the drawing by THIS project's file, not the shared drawing's first upload", () => {
    // Drawings are content-addressed: another project uploaded the same file under another path first.
    const d = must(project.drawings[0]);
    const t: Takeoff = { ...takeoff, drawing_id: d.drawing_id, file: 'plans/someone-else.pdf' };
    const p: ProjectView = {
      ...project,
      files: project.files.map((f) =>
        f.drawing_id === d.drawing_id ? { ...f, path: 'drawings/mine.pdf' } : f,
      ),
    };
    expect(pairsOf([t], p).map((x) => x.file)).toEqual(['drawings/mine.pdf']);
  });

  it('scaleChip: the read scale in words, from drawing.json and each status', () => {
    const real = must(drawing.pages[0]).scale;
    expect(scaleChip(real)).toBe('Scale 1:100 found');
    expect(scaleChip({ ...real, text: null, ratio: 50 })).toBe('Scale 1:50 found');
    expect(scaleChip({ ...real, status: 'estimated' })).toBe('Scale 1:100 estimated');
    expect(scaleChip({ ...real, status: 'no_scale', text: null, ratio: null })).toBe(
      'No scale found',
    );
    expect(scaleChip({ ...real, status: 'not_to_scale' })).toBe('Not to scale');
    expect(scaleChip({ ...real, text: null, ratio: null })).toBeNull();
    expect(scaleChip(undefined)).toBeNull();
  });

  it('shortHashes: a sha256 in a trace line reads as its first 12 characters', () => {
    const sha = 'ca6138f02cfafd870094f2e8ef9a15f39c6c8925025613a0c6465ae21f2e7a20';
    expect(shortHashes(sha)).toBe('ca6138f02cfa…');
    expect(shortHashes(`sha256 ${sha}, 2 files`)).toBe('sha256 ca6138f02cfa…, 2 files');
    expect(shortHashes('5 rooms')).toBe('5 rooms');
  });

  it('previewNote: null for a kind the backend previews (images, PDFs), else the honest line', () => {
    const f = must(project.files[0]);
    for (const kind of [
      'pdf_vector',
      'pdf_scan',
      'pdf_text',
      'png_plan',
      'jpeg_plan',
      'photo_plan',
      'photo',
    ] as const)
      expect(previewNote({ ...f, kind })).toBeNull();
    expect(previewNote({ ...f, kind: 'ifc' })).toBe('A model: no picture to show');
    expect(previewNote({ ...f, kind: 'dxf' })).toBe('DXF: no preview');
    expect(previewNote({ ...f, kind: 'svg' })).toBe('SVG: no preview'); // AV-29: no "a SVG"
    expect(previewNote({ ...f, kind: null })).toBe('Not identified yet');
  });
});
