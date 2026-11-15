import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { takeoff, trace } from '../api/fixtures';
import type { FileTrace, StageTrace, StepTrace } from '../api';
import { must, sheet, traceVariants } from '../ingest/testing';
import {
  decisions,
  disagreements,
  foundLine,
  foundOf,
  keyCounts,
  phaseRuns,
  reasonLines,
  repeats,
  sideBySide,
  stageSpans,
  stepSpans,
  stepsOf,
} from './trace';

const step = (over: Partial<StepTrace>): StepTrace => ({
  id: 'detector',
  label: 'Symbol detector',
  did: '',
  at_ms: 0,
  ms: 0,
  cost_usd: 0,
  state: 'done',
  ...over,
});
const stage = (over: Partial<StageTrace>): StageTrace => ({
  stage: 'extract',
  did: '',
  ms: 0,
  output: '',
  failure: null,
  cost_usd: 0,
  steps: [],
  ...over,
});

describe('trace view v5', () => {
  it('AD-101 stageSpans: each stage starts where the ones before ended; no time gives no span', () => {
    const spans = stageSpans([stage({ ms: 100 }), stage({ ms: 300 }), stage({ ms: 0 })]);
    expect(spans).toEqual([
      { left: 0, width: 0.25 },
      { left: 0.25, width: 0.75 },
      { left: 1, width: 0 },
    ]);
    expect(stageSpans([stage({ ms: 0 }), stage({ ms: 0 })])).toEqual([null, null]);
  });

  it('AD-102 steps on their stage axis; side by side counts overlaps, not back-to-back or skipped', () => {
    const steps = [
      step({ at_ms: 0, ms: 400 }),
      step({ at_ms: 100, ms: 300 }),
      step({ at_ms: 400, ms: 100 }),
      step({ at_ms: 0, ms: 500, state: 'skipped' }),
    ];
    expect(stepSpans(steps.slice(0, 3), 500)).toEqual([
      { left: 0, width: 0.8 },
      { left: 0.2, width: 0.6 },
      { left: 0.8, width: 0.2 },
    ]);
    // a step that ends after the stage's own time stretches the axis, never past 100 %
    expect(stepSpans([step({ at_ms: 0, ms: 200 })], 100)).toEqual([{ left: 0, width: 1 }]);
    expect(sideBySide(steps)).toBe(2);
    expect(sideBySide([step({ at_ms: 0, ms: 10 }), step({ at_ms: 10, ms: 10 })])).toBe(1);
    expect(sideBySide([])).toBe(0);
  });

  it('AD-104 an old server sends no steps: none are drawn', () => {
    const old = { ...stage({}) } as Partial<StageTrace>;
    delete old.steps;
    expect(stepsOf(old as StageTrace)).toEqual([]);
  });

  it('AD-103 foundLine: counts by class, largest first, in words', () => {
    expect(foundLine({ window: 12, door: 31, sink: 1 })).toBe('31 doors, 12 windows, 1 sink');
    expect(foundLine(undefined)).toBe('');
  });

  it('AD-105 decisions of a drawn PDF: what it is, its route and group, the second count, the outcome', () => {
    const d = decisions(trace);
    expect(d.map((x) => x.key)).toEqual(['triage', 'route', 'second', 'outcome']);
    expect(d[0]?.title).toBe('Identified as PDF vector');
    expect(d[0]?.lines).toContain(trace.stages[2]?.did);
    expect(d[1]?.title).toBe('The drawn PDF route');
    expect(d[1]?.lines).toContain('drawn PDF route, read from plans/flat-a.pdf');
    expect(d[1]?.lines).toContain('Grouped: plans/flat-a: flat-a.pdf, flat-a.png');
    expect(d[2]).toMatchObject({ title: 'Both counts agree', tone: 'ok' });
    expect(d[2]?.lines).toEqual(['5 quantities measured a second way: all agree.']);
    expect(d[3]).toMatchObject({
      title: 'Ready to ask',
      tone: 'ok',
      lines: [`${trace.file.reason}.`],
    });
  });

  it('AD-106 triage, read-from, cache, conflicts with their values, flagged reasons, failure', () => {
    const t: FileTrace = {
      ...traceVariants.cache,
      // testing.ts's cache stage predates StageTrace.steps
      stages: traceVariants.cache.stages.map((s) => ({ steps: [], ...s })),
      second_count: { measured: 5, conflicts: 1 },
      file: {
        ...traceVariants.cache.file,
        path: 'plans/flat-a.png',
        source: 'plans/flat-a.pdf',
        state: 'flagged',
        reason: 'scale estimated; 1 conflict',
        triage: {
          class: 'floor_plan',
          p_plan: 0.92,
          method: 'rules',
          sheet: { ...sheet, decision: 'doubt', kind_words: 'a section' },
        },
      },
    };
    const d = decisions(t, [{ label: 'Room 1.01 area', first: '22.4 m²', second: '30.0 m²' }]);
    expect(d[0]?.title).toBe('A floor plan');
    expect(d[0]?.lines[0]).toContain('plan chance 92 %, by rules');
    expect(d[0]?.lines[1]).toBe(
      'The sheet reader saw a section (South elevation, A-201): read, but marked doubtful.',
    );
    expect(d[1]?.lines).toContain(
      'Its plan is read once, from plans/flat-a.pdf; this file is not read again.',
    );
    expect(d[1]?.lines).toContain('Read before: ingested before in another project');
    expect(d[2]).toMatchObject({ title: '1 conflict between the counts', tone: 'warn' });
    expect(d[2]?.lines[0]).toBe(
      '5 quantities measured a second way: 1 disagrees, and goes to you as a conflict.',
    );
    expect(d[2]?.lines[1]).toBe('Room 1.01 area: 22.4 m² on the drawing, 30.0 m² the second way.');
    expect(d[3]).toMatchObject({ title: 'Flagged for a look', tone: 'warn' });
    expect(d[3]?.lines).toEqual(['scale estimated.', '1 conflict.']);
    const failed = decisions(traceVariants.failed);
    expect(failed.at(-1)).toMatchObject({ title: 'Set aside', tone: 'bad' });
    expect(failed.at(-1)?.lines).toContain('Extract failed: no page could be read');
  });

  it('AD-107 disagreements: the disputed conflicts with both values; older servers every conflict', () => {
    const rows = disagreements(takeoff);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows[0]?.first).toMatch(/22\.4/);
    expect(rows[0]?.second).toMatch(/30/);
    expect(disagreements({ ...takeoff, disputes: ['nothing-here'] })).toEqual([]);
  });

  it('AD-112 phaseRuns: neighbouring stages of one phase are one segment, a failure marks its run', () => {
    expect(
      phaseRuns([
        stage({ stage: 'unpack', ms: 1 }),
        stage({ stage: 'hash', ms: 2 }),
        stage({ stage: 'normalise', ms: 3 }),
        stage({ stage: 'extract', ms: 10, failure: 'no page could be read' }),
      ]),
    ).toEqual([
      { phase: 'open', ms: 3, failed: false },
      { phase: 'page', ms: 3, failed: false },
      { phase: 'read', ms: 10, failed: true },
    ]);
  });

  it('AD-111 foundOf: rooms, doors, windows of the takeoff; "" when it counts none', () => {
    expect(foundOf({ ...trace.file, takeoff: { room: 5, door: 2, window: 1 } })).toBe(
      '5 rooms · 2 doors · 1 window',
    );
    expect(foundOf({ ...trace.file, takeoff: {} })).toBe('');
  });

  it('AD-117 a stage output that repeats its did line is shown once', () => {
    const [unpack, hash, identify, , route, , , , takeoffStage] = trace.stages;
    expect(repeats(must(hash))).toBe(true); // did "sha256 dd2c…", output the full hash
    expect(repeats(must(identify))).toBe(true); // "drawn PDF" inside "a drawn PDF (…)"
    expect(repeats(must(route))).toBe(true); // "vector" is the "drawn PDF route" of the did
    expect(repeats(must(takeoffStage))).toBe(true); // "takeoff: 141 …" at the end of the did
    expect(repeats(must(unpack))).toBe(false); // the path adds something
    expect(repeats(stage({ did: 'x', output: '' }))).toBe(true);
  });

  it('AD-118 a reason with a trailing summary reads as plain lines, never two brackets in a row', () => {
    expect(
      reasonLines(
        '1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)',
      ),
    ).toEqual([
      '1 conflict between the two methods (room areas).',
      'Found: 7 elements, 5 rooms, scale read from the sheet.',
    ]);
    expect(reasonLines('scale estimated; 1 conflict')).toEqual(['scale estimated.', '1 conflict.']);
    expect(reasonLines('read on the drawn PDF route: 7 elements')).toEqual([
      'read on the drawn PDF route: 7 elements.',
    ]);
    expect(reasonLines('')).toEqual([]);
  });

  it('AD-119 a file read with its group says so: the route decision names the file it was read with', () => {
    const png: FileTrace = {
      ...trace,
      file: { ...trace.file, path: 'plans/flat-a.png', source: 'plans/flat-a.pdf' },
    };
    expect(decisions(png)[1]?.title).toBe('Read with plans/flat-a.pdf');
    expect(decisions(trace)[1]?.title).toBe('The drawn PDF route');
  });

  it('AD-120 keyCounts: the plain class counts, rooms, doors, windows first, at most 8', () => {
    expect(
      keyCounts({
        window: 2,
        'door|name=a': 1,
        room: 5,
        door: 2,
        'area:room': 64.7,
        bathtub: 1,
        plan: 1,
      }),
    ).toEqual(['5 rooms', '2 doors', '2 windows', '1 bathtub', '1 plan']);
    expect(keyCounts({ toilet_room: 2 })).toEqual(['2 toilet rooms']);
    expect(keyCounts(undefined)).toEqual([]);
  });

  it('AD-116 trace.css: only --v-* colours, and no animation under reduced motion', () => {
    const css = readFileSync('src/advanced/trace.css', 'utf8');
    expect(css).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/i);
    const reduced = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'));
    for (const cls of ['.tl-span', '.fm-segs', '.fm-seg.now']) expect(reduced).toContain(cls);
    expect(reduced).toContain('animation: none');
    // a segment takes its phase's colour: no background of its own that would win over .phase-*
    const seg = /\.fm-seg \{[^}]*\}/.exec(css)?.[0] ?? '';
    expect(seg).not.toContain('background');
    // the five phases are told apart: each its own fill (review of #546: read and store were two dark greens)
    const fills = ['open', 'page', 'read', 'check', 'store'].map(
      (p) => new RegExp(`\\.phase-${p} \\{([^}]*)\\}`).exec(css)?.[1]?.trim() ?? '',
    );
    expect(new Set(fills).size).toBe(5);
    expect(fills.every((f) => f.includes('background'))).toBe(true);
    expect(fills.filter((f) => /--v-accent(-strong)?\b(?!-)/.test(f)).length).toBeLessThanOrEqual(
      1,
    );
  });
});
