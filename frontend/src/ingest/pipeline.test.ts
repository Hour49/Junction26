import { describe, expect, it } from 'vitest';
import { project } from '../api/fixtures';
import type { FileStatus } from '../api';
import {
  busySteps,
  foundLine,
  headlineStep,
  lanes,
  routeReaders,
  routeSummary,
  stepMatches,
  thingsFound,
} from './pipeline';
import { DEMO_READERS, must } from './testing';

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
      bim: ['IFC object reader'],
      cad: [],
      vector: ['vector reader', 'schedule reader', 'second count'],
      raster: [
        'symbol detector',
        'count arbiter',
        'plan finder',
        'room reader',
        'Carbon',
        'printed scale',
        'second readers (2)',
        'Carbon level check',
      ],
    });
  });

  it('IN-101 a reader that reads nothing ("hello") or is off gives its route no reader; no record, none', () => {
    const none = routeReaders(project.readers);
    expect(none.raster).toEqual([]); // the no-keys server: raster=hello
    expect(none.cad).toEqual([]);
    expect(none.vector).toEqual(['vector reader', 'schedule reader', 'second count']);
    expect(
      routeReaders({ ...DEMO_READERS, carbon_reader: 'off', raster_printed_scale: 'off' }).raster,
    ).not.toContain('Carbon');
    expect(routeReaders(undefined)).toEqual({ bim: [], cad: [], vector: [], raster: [] });
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
    expect(stepMatches('Carbon on a large sheet', 'Carbon level check')).toBe(false);
  });
});
