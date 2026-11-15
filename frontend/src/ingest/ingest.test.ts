import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { project, projectFailed, projectRunning } from '../api/fixtures';
import type { StageTrace } from '../api';
import {
  STAGE_LABEL,
  amount,
  nameParts,
  sizeText,
  STEPS,
  activeStep,
  elapsedMs,
  formatCost,
  formatMs,
  formatSize,
  kindLabel,
  percentDone,
  plural,
  progressOf,
  routeLabel,
  stepFiles,
  stepOf,
} from './ingest';
import { must, variants } from './testing';

type Stage = StageTrace['stage'];

describe('ingest.ts', () => {
  it('IN-73 routeLabel gives each route in words; an unknown id as sent', () => {
    expect(routeLabel('vector')).toBe('drawn PDF route');
    expect(routeLabel('raster')).toBe('image route');
    expect(routeLabel('bim')).toBe('BIM model route');
    expect(routeLabel('cad')).toBe('CAD route');
    expect(routeLabel('other')).toBe('other route');
  });

  it('IN-17 progressOf counts ready, flagged, text_only and set_aside as finished', () => {
    const states = ['ready', 'flagged', 'text_only', 'set_aside', 'queued', 'running'] as const;
    expect(progressOf(states.map((state) => ({ state })))).toEqual({ done: 4, total: 6 });
    expect(progressOf(project.files)).toEqual({ done: 3, total: 3 });
  });

  it('IN-56 stepOf maps the 11 stages (and null) to steps 1-8; Index (9) has none; activeStep is the lowest unfinished', () => {
    const map: [Stage | null, number][] = [
      ['unpack', 1],
      ['hash', 1],
      [null, 1],
      ['identify', 2],
      ['group', 3],
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
      'Second count',
      'Takeoff',
      'Store',
      'Index',
    ]);
    expect(activeStep(variants.running.files)).toBe(5);
    expect(activeStep(variants.queued.files)).toBe(1);
    expect(activeStep([])).toBe(1);
  });

  it('IN-89/IN-90 Index is the last step, reached once every file is finished; names follow the stages', () => {
    const running = { ...variants.running, files: project.files };
    expect(activeStep(running.files)).toBe(STEPS.length);
    expect(must(STEPS.at(-1))).toMatchObject({ name: 'Index', stages: [] });
    expect(STEPS.slice(0, 8).map((s) => s.name)).toEqual(
      (
        [
          'unpack',
          'identify',
          'route',
          'normalise',
          'extract',
          'second_count',
          'takeoff',
          'write',
        ] as const
      ).map((s) => STAGE_LABEL[s]),
    );
    expect(STAGE_LABEL.write).toBe('Store');
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
    // the failed fixture is a restart mid-ingest: no finished_at, so its ms is not a duration
    expect(projectFailed.finished_at).toBeNull();
    expect(elapsedMs(projectFailed, started + 99_000)).toBeNull();
    expect(elapsedMs({ ...projectFailed, finished_at: project.finished_at }, 0)).toBe(
      projectFailed.ms,
    );
    expect(elapsedMs(projectRunning, started + 5000)).toBe(5000);
    expect(elapsedMs(projectRunning, started - 5000)).toBe(0);
    expect(elapsedMs(variants.queued, started + 5000)).toBeNull();
  });

  it('IN-69 kindLabel gives every API kind in words; null is "not identified"', () => {
    const kinds = [
      'pdf_vector',
      'pdf_scan',
      'png_plan',
      'jpeg_plan',
      'photo_plan',
      'ifc',
      'dxf',
      'svg',
    ];
    const more = [
      'pdf_text',
      'text',
      'photo',
      'pdf_encrypted',
      'dwg',
      'office',
      'archive',
      'unknown',
    ];
    const plainAlready = ['text', 'photo', 'archive'];
    for (const k of [...kinds, ...more]) {
      expect(kindLabel(k)).not.toContain('_');
      if (!plainAlready.includes(k)) expect(kindLabel(k), k).not.toBe(k);
    }
    expect(kindLabel('pdf_vector')).toBe('PDF vector');
    expect(kindLabel('photo_plan')).toBe('photo of a plan');
    expect(kindLabel(null)).toBe('not identified');
  });

  // Styled with Tailwind classes since the shadcn migration: the rules live in the components and ui.ts.
  const src = (name: string) => readFileSync(`src/ingest/${name}`, 'utf8');

  it('IN-70 phone tap targets: the Workspaces link, Back to the project and the takeoff summary are 44 px', () => {
    expect(src('ui.ts')).toMatch(/TAP = 'inline-flex min-h-11 items-center'/);
    expect(src('ui.ts')).toMatch(/SUMMARY = 'flex min-h-11 /);
    expect(src('HomeScreen.tsx')).toMatch(/<a className=\{TAP\} href="#\/workspaces">/);
    expect(src('FileTraceScreen.tsx')).toMatch(
      /className=\{cn\(TAP, [^)]*\)\}\s*href=\{`#\/p\/\$\{projectId\}\/documents`\}/,
    );
    expect(src('FileTraceScreen.tsx')).toMatch(/<summary className=\{SUMMARY\}>\s*What it ends as/);
    // IN-81: the chat row's "Open the workspace" too
    expect(src('IngestFinished.tsx')).toMatch(
      /className=\{cn\(TAP, [^)]*\)\}\s*href=\{`#\/p\/\$\{projectId\}\/d\//,
    );
  });

  it('IN-83 the file page: mono 28 px path, hairline facts', () => {
    const tsx = src('FileTraceScreen.tsx');
    expect(tsx).toContain('[&_h1]:font-mono! [&_h1]:text-[28px]!');
    expect(tsx).toMatch(/'ingest-facts [^']*gap-px/);
  });

  it('IN-85 the stacked title row puts the segment on its own row, left-aligned', () => {
    expect(src('ProjectScreen.tsx')).toContain("stack ? 'flex-col items-start'");
  });

  it('IN-66 the ingest screens have no colour literal: every colour is a token', () => {
    for (const name of [
      'BeforeAfter.tsx',
      'FileTraceScreen.tsx',
      'HomeScreen.tsx',
      'IngestFinished.tsx',
      'ProgressCard.tsx',
      'ProjectScreen.tsx',
      'TriageCard.tsx',
      'UploadBox.tsx',
      'ui.ts',
    ])
      expect(src(name), name).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
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

it('IN-89 sizes: KB under 1 MB (never 0 KB for a total), MB with one decimal above; a part in its total unit', () => {
  expect(sizeText(30_000)).toBe('29 KB');
  expect(sizeText(10)).toBe('1 KB');
  expect(sizeText(2.5 * 2 ** 20)).toBe('2.5 MB');
  expect(amount(15_000, 30_000)).toBe('15');
  expect(amount(0, 30_000)).toBe('0');
  expect(amount(2 ** 19, 2 ** 21)).toBe('0.5');
});

it('IN-121 nameParts: a name breaks after its own separators, the parts joined are the name', () => {
  const name = 'Bauprojekt_Mehrfamilienhaus_Zuerich-Nord_2026.zip';
  expect(nameParts(name)).toEqual([
    'Bauprojekt_',
    'Mehrfamilienhaus_',
    'Zuerich-',
    'Nord_',
    '2026.',
    'zip',
  ]);
  expect(nameParts('plans/A-101.pdf')).toEqual(['plans/', 'A-', '101.', 'pdf']);
  expect(nameParts('Grundriss')).toEqual(['Grundriss']);
  expect(nameParts('a__b').join('')).toBe('a__b');
});
