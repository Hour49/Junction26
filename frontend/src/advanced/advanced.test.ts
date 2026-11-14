import { describe, expect, it } from 'vitest';
import { drawing, project, takeoff, trace, traceSetAside } from '../api/fixtures';
import type { FileTrace, ProjectView, Takeoff } from '../api';
import { STEPS } from '../ingest/ingest';
import { variants, must } from '../ingest/testing';
import {
  STEP_VIEW,
  currentStep,
  defaultStep,
  elapsedMs,
  pairsOf,
  planCounts,
  quantityCount,
  scaleChip,
  stepLines,
  stepStatus,
} from './advanced';

const statuses = (p: ProjectView) => STEPS.map((_, i) => stepStatus(p, i + 1).status);

describe('advanced.ts', () => {
  it('AV-2 STEP_VIEW has a heading, visual and explanation for each of the 8 steps', () => {
    expect(STEPS).toHaveLength(8);
    expect(STEP_VIEW).toHaveLength(8);
    for (const v of STEP_VIEW) {
      expect(v.heading).not.toBe('');
      expect(v.explain.length).toBeGreaterThan(20);
    }
  });

  it('AV-3 a done project: every step done', () => {
    expect(statuses(project)).toEqual(Array(8).fill('done'));
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
    ]);
  });

  it('AV-3 queued with no stages: Unpack working, the rest waiting; no files while queued: all waiting', () => {
    expect(statuses(variants.queued)[0]).toBe('working');
    expect(statuses(variants.queued).slice(1)).toEqual(Array(7).fill('waiting'));
    const queuedEmpty: ProjectView = { ...project, state: 'queued', files: [], drawings: [] };
    expect(statuses(queuedEmpty)).toEqual(Array(8).fill('waiting'));
  });

  it('AV-3 a file set aside at Route makes no later step waiting; with no other file they are "none"', () => {
    const p: ProjectView = {
      ...project,
      files: [{ ...must(project.files[0]), state: 'set_aside', stage: 'route', drawing_id: null }],
    };
    expect(statuses(p)).toEqual(['done', 'done', 'done', 'none', 'none', 'none', 'none', 'none']);
    expect(stepStatus(p, 3).setAside).toBe(1);
    expect(stepStatus(p, 2).setAside).toBe(0);
    expect(statuses({ ...project, files: [], drawings: [] })).toEqual(Array(8).fill('none'));
  });

  it('currentStep / defaultStep: the active step while running, none and Index when done', () => {
    expect(currentStep(variants.running)).toBe(5);
    expect(defaultStep(variants.running)).toBe(5);
    expect(currentStep(variants.queued)).toBe(1);
    expect(currentStep(project)).toBeNull();
    expect(defaultStep(project)).toBe(7);
    expect(currentStep(variants.failed)).toBeNull();
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
      `Unpack ${trace.file.path} ${must(trace.stages[0]).output}`,
      `Hash ${trace.file.path} ${must(trace.stages[1]).output}`,
      `Unpack b.pdf ${must(trace.stages[0]).output}`,
      `Hash b.pdf ${must(trace.stages[1]).output}`,
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
        { stage: 'cache', did: 'ingested before', ms: 0, output: '', failure: null, cost_usd: 0 },
      ],
    };
    expect(stepLines([trace.file], new Map([[trace.file.id, cached]]), 3)[0]?.text).toBe(
      `Cache ${trace.file.path} Cached: ingested before`,
    );
  });

  it('AV-17 planCounts sums room, door, window over drawings only; a key no drawing has is null', () => {
    // project.json: flat-a.pdf and flat-b.pdf are drawings (5 rooms, 2 doors, 2 windows each);
    // flat-a.png is another rendering of flat-a and is not added.
    expect(planCounts(project)).toEqual({ room: 10, door: 4, window: 4, drawings: 5 });
    const noWindows: ProjectView = {
      ...project,
      files: project.files.map((f) => ({ ...f, takeoff: { room: 1 } })),
    };
    expect(planCounts(noWindows).window).toBeNull();
    expect(quantityCount(project)).toBe(142);
  });

  it('AV-19 pairsOf: rows measured twice, conflicts first', () => {
    const agree = {
      ...must(takeoff.quantities[0]),
      key: 'door',
      status: 'agree' as const,
      second: { method: 'ifc_model', value: 2 },
    };
    const t: Takeoff = { ...takeoff, quantities: [agree, ...takeoff.quantities] };
    const pairs = pairsOf([t]);
    expect(pairs.map((p) => [p.row.key, p.row.status])).toEqual([
      ['area:room|name=1.01', 'conflict'],
      ['door', 'agree'],
    ]);
    expect(pairs[0]?.file).toBe(takeoff.file);
  });

  it('elapsedMs: done -> project.ms; running -> now - started_at; not started -> null', () => {
    expect(elapsedMs(project, 0)).toBe(project.ms);
    const now = Date.parse('2026-11-14T08:00:10Z');
    const running = { ...variants.running, started_at: '2026-11-14T08:00:00Z' };
    expect(elapsedMs(running, now)).toBe(10000);
    expect(elapsedMs({ ...running, started_at: null }, now)).toBeNull();
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
});
