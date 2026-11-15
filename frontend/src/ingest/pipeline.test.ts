import { describe, expect, it } from 'vitest';
import { project } from '../api/fixtures';
import type { FileStatus } from '../api';
import {
  chipCovers,
  chipHasStep,
  chipRan,
  chipSteps,
  chipStepsOf,
  busySteps,
  chipWords,
  foundLine,
  groupReaders,
  headlineStep,
  lanes,
  readDrawings,
  readerGroup,
  routeReaders,
  routeSummary,
  stepMatches,
  thingsFound,
  triageReaders,
  unread,
  triageEnded,
  triageRan,
} from './pipeline';
import { DEMO_READERS, LIVE_STEPS, RASTER_CHIPS, must, sampleRun } from './testing';

const base = must(project.files[0]);
const file = (id: string, changes: Partial<FileStatus>): FileStatus => ({
  ...base,
  id,
  path: `${id}.png`,
  source: null,
  takeoff: {},
  ...changes,
});

describe('pipeline.ts (ingest.md "Pipeline view v5")', () => {
  it('IN-101 routeReaders names the readers each route runs, from what ingest recorded', () => {
    expect(routeReaders(DEMO_READERS)).toEqual({
      bim: ['IFC model reader'],
      cad: [],
      vector: ['drawn-PDF reader', 'schedule tables', 'second count'],
      raster: RASTER_CHIPS,
    });
  });

  it('IN-101 a reader that reads nothing ("hello") or is off gives its route no reader; no record, none', () => {
    const none = routeReaders(project.readers);
    expect(none.raster).toEqual([]); // the no-keys server: raster=hello
    expect(none.cad).toEqual([]);
    expect(none.vector).toEqual(['drawn-PDF reader', 'schedule tables', 'second count']);
    const off = routeReaders({
      ...DEMO_READERS,
      carbon_reader: 'off',
      carbon_levels: 'off',
      raster_printed_scale: 'off',
      raster_scale: 'off',
      rectifier: 'none',
      double_check_readers: '',
    }).raster;
    expect(off).toEqual([
      'symbol detector',
      'Gemini count decision',
      'count arbiter',
      'room reader',
    ]);
    expect(routeReaders(undefined)).toEqual({ bim: [], cad: [], vector: [], raster: [] });
  });

  it('IN-117 the live raster readers: arbiter parts are the detector and arbiter, not "door" or "window"', () => {
    const raster = routeReaders(DEMO_READERS).raster;
    for (const part of ['door', 'window', 'sink', 'toilet', 'shower', 'bathtub', 'plan finder'])
      expect(raster).not.toContain(part);
    // Gemini Decisions picks counts; the count arbiter is the arbiter-t1 model, not Decisions
    expect(
      routeReaders({ ...DEMO_READERS, raster_components: 'elements=decisions:detector-v8:x' })
        .raster,
    ).toContain('Gemini count decision');
    expect(
      routeReaders({ ...DEMO_READERS, raster_components: 'elements=decisions:detector-v8:x' })
        .raster,
    ).not.toContain('count arbiter');
    // CARBON_READER=all reads every sheet, not only the near-empty ones
    expect(routeReaders({ ...DEMO_READERS, carbon_reader: 'all+storey:abc' }).raster).toContain(
      'Gemini reader',
    );
  });

  it('IN-118 every step a live file reports lights a chip of its lane (no stray label chips)', () => {
    const chips = routeReaders(DEMO_READERS);
    const covered = (route: keyof typeof chips, label: string) =>
      chips[route].some((c) => stepMatches(label, c));
    for (const label of LIVE_STEPS.raster)
      expect([label, covered('raster', label)]).toEqual([label, true]);
    for (const label of LIVE_STEPS.vector)
      expect([label, covered('vector', label)]).toEqual([label, true]);
    for (const label of LIVE_STEPS.bim)
      expect([label, covered('bim', label)]).toEqual([label, true]);
    // each label lights the reader it is, not a neighbour
    expect(
      stepMatches('Gemini Carbon check (never counted)', 'Gemini cross-check (not counted)'),
    ).toBe(true);
    expect(
      stepMatches('Gemini Carbon check (never counted)', 'Gemini for sheets with few symbols'),
    ).toBe(false);
    expect(
      stepMatches(
        'Double-check reader m1: Symbol detector',
        'double check by 2 more readers (not counted)',
      ),
    ).toBe(true);
  });

  it('IN-120 groupReaders: the readers by what they do, groups in run order, each from the reader itself', () => {
    const raster = routeReaders(DEMO_READERS).raster;
    const shape = (g: ReturnType<typeof groupReaders>) => g.map((x) => [x.label, x.readers]);
    expect(shape(groupReaders(raster))).toEqual([
      ['Prepare', ['photo flattening', 'printed scale (Gemini)']],
      ['Count', ['symbol detector', 'Gemini count decision', 'count arbiter', 'room reader']],
      [
        'Checks, not counted',
        ['Gemini cross-check (not counted)', 'double check by 2 more readers (not counted)'],
      ],
      ['If few symbols', ['Gemini for sheets with few symbols']],
      ['Scale', ['scale from door sizes']],
    ]);
    // the group comes from the reader, not its position: reversed, the same groups in the same order
    expect(groupReaders([...raster].reverse()).map((g) => g.label)).toEqual(
      groupReaders(raster).map((g) => g.label),
    );
    expect(shape(groupReaders(routeReaders(DEMO_READERS).vector))).toEqual([
      ['Count', ['drawn-PDF reader', 'schedule tables']],
      ['Checks, not counted', ['second count']],
    ]);
    // one group: no label
    expect(shape(groupReaders(['IFC model reader']))).toEqual([[null, ['IFC model reader']]]);
    // a step the server ran that no reader covers: last, "Also ran"
    expect(shape(groupReaders(['IFC model reader'], ['Wall tracer']))).toEqual([
      ['Count', ['IFC model reader']],
      ['Also ran', ['Wall tracer']],
    ]);
    expect(groupReaders([])).toEqual([]);
    // CARBON_READER=all reads every sheet: it counts
    expect(readerGroup('Gemini reader')).toBe('count');
  });

  it('IN-120 chipWords leaves out what the group label says; with no label, the full name', () => {
    expect(chipWords('Gemini cross-check (not counted)', true)).toBe('Gemini cross-check');
    expect(chipWords('double check by 2 more readers (not counted)', true)).toBe(
      'double check by 2 more readers',
    );
    expect(chipWords('Gemini for sheets with few symbols', true)).toBe('Gemini reader');
    expect(chipWords('symbol detector', true)).toBe('symbol detector');
    expect(chipWords('Gemini cross-check (not counted)', false)).toBe(
      'Gemini cross-check (not counted)',
    );
  });

  it('IN-119 triageReaders: what sorts every file before its route, from the recorded triage', () => {
    expect(triageReaders(DEMO_READERS)).toEqual([
      'scan or photo (Gemini)',
      'sheet kind (Gemini)',
      'describes sheets that are not plans (Gemini)',
      'keep or set aside (rules)',
    ]);
    expect(
      triageReaders({
        triage: 'classifier=rules, describer=off, judge=off',
        decisions_kind: 'False',
      }),
    ).toEqual(['plan or not (rules)']);
    expect(triageReaders(project.readers)).toEqual([]);
    expect(triageReaders(undefined)).toEqual([]);
  });

  it('IN-123 each chip knows its step ids, from the components as configured', () => {
    const known = chipStepsOf(DEMO_READERS);
    // Gemini Decisions over the detector: the detector reads inside the decisions step
    expect(chipSteps('symbol detector', known)).toEqual([
      'detector',
      'decisions',
      'arbiter/base',
      'arbiter/second',
    ]);
    expect(chipSteps('count arbiter', known)).toEqual(['arbiter', 'arbiter/pick']);
    expect(chipSteps('Gemini count decision', known)).toEqual(['decisions']);
    expect(chipSteps('room reader', known)).toEqual(['rooms']);
    expect(chipSteps('double check by 2 more readers (not counted)', known)).toEqual([
      'double_check:',
    ]);
    expect(
      chipHasStep('double check by 2 more readers (not counted)', 'double_check:m1', known),
    ).toBe(true);
    expect(chipHasStep('second count', 'second_count:door', known)).toBe(true);
    expect(chipHasStep('Gemini cross-check (not counted)', 'carbon_check', known)).toBe(true);
    expect(chipHasStep('Gemini for sheets with few symbols', 'carbon_check', known)).toBe(false);
    expect(chipHasStep('Gemini for sheets with few symbols', 'carbon', known)).toBe(true);
    // a precomputed rooms reading runs as `reader`
    expect(chipSteps('room reader', chipStepsOf({ raster_components: 'rooms=exp:ocr/x' }))).toEqual(
      ['reader'],
    );
    // the id wins over a label that begins with another chip's name; no id: the label
    const arbiter = { id: 'arbiter', label: 'Symbol detector, 8 views + count arbiter' };
    expect(chipCovers('symbol detector', arbiter, known)).toBe(false);
    expect(chipCovers('count arbiter', arbiter, known)).toBe(true);
    expect(
      chipCovers('symbol detector', { id: null, label: 'Symbol detector, 8 views' }, known),
    ).toBe(true);
    // a chip with no known id (or a step label as a chip): label only
    expect(chipSteps('tiles for big sheets', known)).toEqual([]);
    // the door-size scale estimate has its own step since #651
    expect(chipSteps('scale from door sizes', known)).toEqual(['prior_scale']);
    expect(chipCovers('Wall tracer', { id: 'walls', label: 'Wall tracer' }, known)).toBe(true);
  });

  it('IN-124 chipRan: ran when done or failed on a file, skipped when only skipped, absent, or nothing to tell', () => {
    const known = chipStepsOf(DEMO_READERS);
    const r = (id: string, done = 0, skipped = 0, failed = 0) => ({
      id,
      label: id,
      done,
      skipped,
      failed,
    });
    expect(chipRan('Gemini reader', [r('carbon', 0, 0, 1)], known)).toBe('ran');
    expect(chipRan('Gemini reader', [r('carbon', 0, 2)], known)).toBe('skipped');
    expect(chipRan('Gemini reader', [r('probe', 3)], known)).toBe('absent');
    expect(chipRan('Gemini reader', undefined, known)).toBeNull(); // an older project
    expect(chipRan('tiles for big sheets', [r('probe', 3)], known)).toBeNull(); // no known id
    // the door-size scale (#651): skipped when a scale was read, no page, or the doors were not read
    expect(chipRan('scale from door sizes', [r('prior_scale', 1)], known)).toBe('ran');
    expect(chipRan('scale from door sizes', [r('prior_scale', 0, 2)], known)).toBe('skipped');
  });

  it('IN-102 things found: plain counts only, each drawing once (not its other renderings)', () => {
    const takeoff = {
      door: 2,
      window: 3,
      room: 5,
      'room:kitchen': 1,
      'area:room': 64.7,
      'window|name=küche': 1,
      plan: 1,
      apartment: 1,
      sink: 0,
    };
    const files = [
      file('a', { state: 'ready', takeoff, path: 'a.pdf', source: 'a.pdf' }),
      file('b', { state: 'ready', takeoff, path: 'a.png', source: 'a.pdf' }), // same drawing
      file('c', { state: 'running', takeoff: { door: 9 } }), // not read yet
    ];
    expect(thingsFound(files)).toBe(10);
    expect(foundLine(takeoff)).toBe('5 rooms, 3 windows, 2 doors');
    expect(foundLine({ door: 1, window: 1, room: 1, sink: 1, toilet: 2 })).toBe(
      '2 toilets, 1 door, 1 room, 1 sink, +1 more',
    );
    expect(foundLine({ wall: 4, 'shower+bathtub': 1 })).toBe('4 walls, 1 shower-bath');
    expect(foundLine({})).toBe('');
  });

  it('IN-103 lanes: routes in order (model, CAD, drawn PDF, image), then not routed, then not drawings', () => {
    const files = [
      file('p', { route: 'raster', state: 'ready' }),
      file('q', { route: null, state: 'queued' }),
      file('s', { route: null, state: 'set_aside' }),
      file('v', { route: 'vector', state: 'ready' }),
      file('r', { route: 'raster', state: 'running' }),
      file('i', { route: 'bim', state: 'flagged' }),
    ];
    const all = lanes(files);
    expect(all.map((l) => l.id)).toEqual(['bim', 'vector', 'raster', 'waiting', 'other']);
    expect(all.map((l) => l.name)).toEqual([
      'IFC model',
      'Drawn PDF',
      'Image',
      'Not routed yet',
      'Not drawings',
    ]);
    // running first inside a lane
    expect(all[2]?.files.map((f) => f.id)).toEqual(['r', 'p']);
    expect(lanes([])).toEqual([]);
  });

  it('IN-104 routeSummary says what was read by which route and what needs a person', () => {
    const files = [
      file('a', { route: 'vector', drawing_id: 'd1', path: 'a.pdf', source: 'a.pdf' }),
      file('b', { route: 'vector', drawing_id: 'd1', path: 'a.png', source: 'a.pdf' }),
      file('c', { route: 'vector', drawing_id: 'd2', state: 'flagged' }),
      file('d', { route: 'raster', drawing_id: 'd3', state: 'flagged' }),
      file('e', { route: 'bim', drawing_id: 'd4' }),
      file('f', { route: null, drawing_id: null, state: 'set_aside' }),
    ];
    expect(routeSummary(files)).toBe(
      'Read 1 IFC model, 2 drawn PDFs and 1 image. 2 flagged files need a look; 1 set aside.',
    );
    expect(routeSummary(files.slice(0, 1))).toBe('Read 1 drawn PDF.');
    // QA R2-A1: on a no-keys server the image route's reader is `hello`: its file was not read, nor counted as read
    expect(routeSummary(files, { ...DEMO_READERS, raster: 'hello' })).toBe(
      'Read 1 IFC model and 2 drawn PDFs. 1 flagged file needs a look; 1 not read; 1 set aside.',
    );
    expect(routeSummary(files.slice(3, 4), { raster: 'hello' })).toBe('1 not read.');
    expect(routeSummary([])).toBe('');
  });

  it('IN-111 the step named while it runs: where most files are read now; else the lowest waiting; Index last', () => {
    const p = (files: FileStatus[], phase: 'files' | 'index' | null = 'files') => ({
      ...project,
      state: 'running' as const,
      phase,
      files,
    });
    const extracting = [
      file('q', { state: 'queued', stage: 'identify' }),
      file('a', { state: 'running', stage: 'extract' }),
      file('b', { state: 'running', stage: 'extract' }),
      file('c', { state: 'running', stage: 'normalise' }),
    ];
    expect(headlineStep(p(extracting))).toBe(5); // not Identify, where one file waits
    expect(busySteps(extracting)).toEqual(
      new Map([
        [5, 2],
        [4, 1],
      ]),
    );
    // a tie: the later step
    expect(headlineStep(p(extracting.slice(0, 2).concat(extracting[3] ?? [])))).toBe(5);
    expect(headlineStep(p([file('q', { state: 'queued', stage: 'identify' })]))).toBe(2);
    expect(headlineStep(p(extracting, 'index'))).toBe(9);
  });

  it('IN-105 a step label belongs to the reader it starts with', () => {
    expect(stepMatches('Symbol detector, 8 views', 'symbol detector')).toBe(true);
    expect(stepMatches('Room reader (Gemini)', 'room reader')).toBe(true);
    expect(stepMatches('Carbon on a large sheet', 'Gemini cross-check (not counted)')).toBe(false);
  });

  it('IN-116 a drawing on a route whose reader is `hello` is unread, and not among the drawings read', () => {
    const offline = { ...DEMO_READERS, raster: 'hello' };
    expect(unread({ route: 'raster' }, offline)).toBe(true);
    expect(unread({ route: 'raster' }, DEMO_READERS)).toBe(false);
    expect(unread({ route: 'vector' }, offline)).toBe(false);
    expect(unread({ route: null }, offline)).toBe(false);
    expect(unread({ route: 'raster' }, undefined)).toBe(false); // an old server: nothing said, nothing hidden
    // project.json is a no-keys run: its scan and photo are on `raster: hello`
    expect(readDrawings(project).map((d) => d.route)).toEqual([
      'vector',
      'vector',
      'vector',
      'bim',
    ]);
    expect(readDrawings({ ...project, readers: DEMO_READERS })).toHaveLength(6);
  });

  it('IN-126 (QA R4-A9) a sheet the sheet-kind step called not a drawing is not among the drawings read', () => {
    const [real, shot] = [must(project.drawings[0]), must(project.drawings[1])];
    const screenshot = { ...shot, not_a_drawing: true };
    const readers = DEMO_READERS;
    expect(readDrawings({ drawings: [screenshot], readers })).toEqual([]);
    expect(readDrawings({ drawings: [real, screenshot], readers })).toEqual([real]);
    // left out when false (API.md): an old or a plain drawing counts
    expect(readDrawings({ drawings: [{ ...shot, not_a_drawing: false }], readers })).toHaveLength(
      1,
    );
  });

  it('IN-127 triageRan: each sorting chip from the step ids that really ran (the demo sample)', () => {
    const done = sampleRun('done');
    const chips = [
      'scan or photo (Gemini)',
      'sheet kind (Gemini)',
      'describes sheets that are not plans (Gemini)',
      'keep or set aside (rules)',
    ];
    expect(chips.map((c) => triageRan(c, done))).toEqual(['ran', 'ran', 'ran', 'ran']);
    // mid-run: the files' identify steps ended on some files; the last phase has not begun
    const mid = sampleRun('mid');
    expect(chips.map((c) => triageRan(c, mid))).toEqual(['ran', 'ran', null, null]);
    expect(chips.map((c) => triageEnded(c, mid))).toEqual([false, false, false, false]);
    expect(chips.map((c) => triageEnded(c, done))).toEqual([true, true, true, true]);
    // running: a file in its classifier step; the describer's index step started
    const files = mid.files.map((f, i) =>
      i === 0 ? { ...f, state: 'running' as const, step_id: 'classifier' } : f,
    );
    expect(triageRan('sheet kind (Gemini)', { ...mid, files })).toBe('running');
    const describing = done.index_steps.map((s) =>
      s.id === 'describe' ? { ...s, state: 'running' as const } : s,
    );
    expect(triageRan(chips[2] ?? '', { ...done, index_steps: describing })).toBe('running');
    // only skipped, or not there at all
    const judged = done.index_steps.map((s) =>
      s.id === 'judge' ? { ...s, state: 'skipped' as const } : s,
    );
    expect(triageRan('keep or set aside (rules)', { ...done, index_steps: judged })).toBe(
      'skipped',
    );
    const noDescribe = done.index_steps.filter((s) => s.id !== 'describe');
    expect(triageRan(chips[2] ?? '', { ...done, index_steps: noDescribe })).toBe('absent');
    const ran = { raster: [{ id: 'classifier', label: 'x', done: 0, skipped: 2, failed: 0 }] };
    expect(triageRan('sheet kind (Gemini)', { ...done, ran })).toBe('skipped');
    expect(triageRan('plan or not (rules)', { ...done, ran: { raster: [] } })).toBe('absent');
    // an older server or record: nothing to tell
    expect(triageRan('sheet kind (Gemini)', { ...done, ran: undefined })).toBeNull();
    expect(triageRan(chips[3] ?? '', { ...done, index_steps: [] })).toBeNull();
    expect(triageRan(chips[3] ?? '', { files: done.files, ran: done.ran })).toBeNull();
  });
});
