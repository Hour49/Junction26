import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { project, projectFailed, projectRunning } from '../api/fixtures';
import type { StageTrace } from '../api';
import {
  STEPS,
  activeStep,
  elapsedMs,
  formatCost,
  formatMs,
  formatSize,
  percentDone,
  plural,
  progressOf,
  stepFiles,
  stepOf,
} from './ingest';
import { must, variants } from './testing';

type Stage = StageTrace['stage'];

describe('ingest.ts', () => {
  it('IN-17 progressOf counts ready, flagged, text_only and set_aside as finished', () => {
    const states = ['ready', 'flagged', 'text_only', 'set_aside', 'queued', 'running'] as const;
    expect(progressOf(states.map((state) => ({ state })))).toEqual({ done: 4, total: 6 });
    expect(progressOf(project.files)).toEqual({ done: 3, total: 3 });
  });

  it('IN-56 stepOf maps the 11 stages (and null) to the 8 steps; activeStep is the lowest unfinished', () => {
    const map: [Stage | null, number][] = [
      ['unpack', 1],
      ['hash', 1],
      [null, 1],
      ['identify', 2],
      ['group', 2],
      ['route', 3],
      ['cache', 3],
      ['normalise', 4],
      ['extract', 5],
      ['second_count', 6],
      ['takeoff', 7],
      ['write', 8],
    ];
    for (const [stage, step] of map) expect(stepOf(stage)).toBe(step);
    expect(STEPS.map((s) => s.name)).toEqual([
      'Unpack',
      'Identify',
      'Route',
      'Normalise',
      'Extract',
      'Cross-check',
      'Index',
      'Drawing model',
    ]);
    expect(activeStep(variants.running.files)).toBe(5);
    expect(activeStep(variants.queued.files)).toBe(1);
    expect(activeStep([])).toBe(1);
  });

  it('IN-59 stepFiles: through leaves out files finished earlier; passed is later or finished here', () => {
    expect(stepFiles(variants.running.files, 5)).toEqual({ passed: 2, through: 3 });
    const setAside = must(variants.setAside.files[0]);
    expect(stepOf(setAside.stage)).toBe(2);
    expect(stepFiles(variants.setAside.files, 3)).toEqual({
      passed: project.files.length - 1,
      through: project.files.length - 1,
    });
  });

  it('IN-60 percentDone is round(100 x finished / files), 0 with no files', () => {
    expect(percentDone(variants.running.files)).toBe(67);
    expect(percentDone(project.files)).toBe(100);
    expect(percentDone(variants.queued.files)).toBe(0);
    expect(percentDone([])).toBe(0);
  });

  it('IN-61 elapsedMs: ms once ended, now - started_at while live (never below 0), null before it starts', () => {
    const started = Date.parse(must(projectRunning.started_at));
    expect(elapsedMs(project, started + 99_000)).toBe(project.ms);
    expect(elapsedMs(projectFailed, started + 99_000)).toBe(projectFailed.ms);
    expect(elapsedMs(projectRunning, started + 5000)).toBe(5000);
    expect(elapsedMs(projectRunning, started - 5000)).toBe(0);
    expect(elapsedMs(variants.queued, started + 5000)).toBeNull();
  });

  it('IN-66 ingest.css has no colour literal: every colour is a var(--v-…)', () => {
    const css = readFileSync('src/ingest/ingest.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
  });

  it('IN-34 formatMs, formatCost and formatSize', () => {
    expect(formatMs(0.6838)).toBe('0.68 ms');
    expect(formatMs(12.5)).toBe('12.5 ms');
    expect(formatMs(1234)).toBe('1.2 s');
    expect(formatCost(0)).toBe('$0.00');
    expect(formatCost(0.004)).toBe('<$0.01');
    expect(formatCost(0.123)).toBe('$0.12');
    expect(formatSize(2263)).toBe('2.2 KB');
    expect(formatSize(1048576)).toBe('1.0 MB');
  });

  it('R1-1-1 plural: singular for 1, plural for 0 and 2', () => {
    expect(plural(0, 'file')).toBe('0 files');
    expect(plural(1, 'file')).toBe('1 file');
    expect(plural(2, 'file')).toBe('2 files');
    expect(plural(1, 'quantity', 'quantities')).toBe('1 quantity');
    expect(plural(2, 'quantity', 'quantities')).toBe('2 quantities');
  });
});
