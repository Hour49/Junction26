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
  saidByStage,
  sideBySide,
  stageSpans,
  stepRows,
  stepSpans,
  stepsOf,
  traceMs,
  untimed,
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

  // the shape of a real raster extract (sample trace f14, 2026-11-15): two Carbon reads at once, 15.7 s with no step
  // running, six readers starting together with two after them inside the arbiter's time, then a skipped reader
  const real = [
    step({ id: 'printed_scale', at_ms: 1.3, ms: 359.3 }),
    step({ id: 'carbon', at_ms: 4.4, ms: 368.1 }),
    step({ id: 'decisions', at_ms: 16031.7, ms: 4494 }),
    step({ id: 'arbiter', at_ms: 16031.8, ms: 5128.4 }),
    step({ id: 'detector', at_ms: 16031.8, ms: 4486.7 }),
    step({ id: 'rooms', at_ms: 16031.9, ms: 1369.7 }),
    step({ id: 'double_check', at_ms: 16032, ms: 793.6 }),
    step({ id: 'double_check', at_ms: 16032.2, ms: 542.4 }),
    step({ id: 'detector', at_ms: 20518.5, ms: 89.6 }),
    step({ id: 'arbiter', at_ms: 20608.2, ms: 551.9 }),
    step({ id: 'carbon', at_ms: 21161.5, ms: 0, state: 'skipped' }),
  ];

  it('AD-121 stepRows: runs side by side under a head on their own axis, a long idle stretch said, lone steps kept', () => {
    const rows = stepRows(real, 21168.7);
    expect(rows.map((r) => (r.kind === 'step' ? r.step.id : r.kind))).toEqual([
      'together',
      'printed_scale',
      'carbon',
      'idle',
      'together',
      'decisions',
      'arbiter',
      'detector',
      'rooms',
      'double_check',
      'double_check',
      'detector',
      'arbiter',
      'carbon',
    ]);
    expect(rows[0]).toMatchObject({ kind: 'together', from: 1.3, count: 2, peak: 2 });
    expect(rows[3]).toEqual({ kind: 'idle', from: 372.5, to: 16031.7 });
    const run = rows[4];
    expect(run).toMatchObject({ kind: 'together', from: 16031.7, count: 8, peak: 6 });
    expect(run?.kind === 'together' && run.to).toBeCloseTo(21160.2, 1);
    // on the run's own axis: the arbiter spans it, its second detector read starts 87 % in
    const span = (i: number) => {
      const r = rows[i];
      return r?.kind === 'step' ? r.span : undefined;
    };
    expect(span(6)?.width).toBeCloseTo(1, 3);
    expect(span(11)?.left).toBeCloseTo(0.875, 2);
    // the skipped reader after the run is lone, on the stage axis
    expect(rows[13]).toMatchObject({ kind: 'step', together: false });
    expect(span(13)?.left).toBeCloseTo(21161.5 / 21168.7, 4);
  });

  it('AD-121 the wait before the first step is its own row; short gaps and back-to-back steps are not', () => {
    const late = stepRows(
      [step({ at_ms: 16000, ms: 4000 }), step({ at_ms: 16000, ms: 2000 })],
      20000,
    );
    expect(late[0]).toEqual({ kind: 'idle', from: 0, to: 16000 });
    expect(late[1]).toMatchObject({ kind: 'together', count: 2, peak: 2 });
    // a drawn PDF: two readers one after the other, 0.02 ms apart: two lone steps on the stage axis
    const vector = stepRows(
      [step({ at_ms: 0, ms: 93.25 }), step({ id: 'tables', at_ms: 93.27, ms: 3424.4 })],
      3517.7,
    );
    expect(vector.map((r) => r.kind)).toEqual(['step', 'step']);
    expect(vector.every((r) => r.kind === 'step' && !r.together)).toBe(true);
    // 900 ms idle in a 2 s stage is under the 1 s floor: no row
    expect(
      stepRows([step({ at_ms: 0, ms: 100 }), step({ at_ms: 1000, ms: 1000 })], 2000).map(
        (r) => r.kind,
      ),
    ).toEqual(['step', 'step']);
    expect(stepRows([], 0)).toEqual([]);
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
    // zero counts are left out before the 8 are taken: they would hide the real ones (review of #552)
    expect(keyCounts({ room: 5, shower: 0, sink: 1 })).toEqual(['5 rooms', '1 sink']);
    expect(
      keyCounts({ door: 0, window: 0, a: 0, b: 0, c: 0, d: 0, e: 0, f: 0, g: 0, toilet: 2 }),
    ).toEqual(['2 toilets']);
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
      (p) => new RegExp(`\\.phase-${p} \\{[^}]*background: ([^;]*);`).exec(css)?.[1]?.trim() ?? '',
    );
    expect(fills.every(Boolean)).toBe(true);
    expect(new Set(fills).size).toBe(5);
    // one phase at most in the dark accent family (read and store were --v-accent and --v-accent-strong)
    expect(fills.filter((f) => /--v-accent(-strong)?\)/.test(f))).toHaveLength(1);
  });

  it("AD-125 saidByStage: a step's did the stage's line already says, whole or as a part; not mid-sentence", () => {
    // the real sample (#535, 2026-11-15): identify joins its steps, normalise ends with the page step's did
    const photo =
      'a photo of a drawing (1920x1080 px, camera EXIF (SONY DSC-T700)); triage: a floor plan (P(plan) 0.35)';
    expect(
      saidByStage('a photo of a drawing (1920x1080 px, camera EXIF (SONY DSC-T700))', photo),
    ).toBe(true);
    expect(saidByStage('a floor plan (P(plan) 0.35)', photo)).toBe(true);
    const normalise =
      'rectified by page flattening: 1691x1015 px; 1 page, page 1 is 1691 x 1015 px';
    expect(saidByStage('1 page, page 1 is 1691 x 1015 px', normalise)).toBe(true);
    expect(saidByStage('paper seen straight on: 1691x1015 px', normalise)).toBe(false);
    expect(
      saidByStage('1 page, page 1 is 841.89 x 1190.55 pt', '1 page, page 1 is 841.89 x 1190.55 pt'),
    ).toBe(true);
    // a short did inside a sentence is a coincidence, not a repeat
    expect(saidByStage('1 plan', '0 elements, 26 rooms, 1 plan, no scale on the sheet')).toBe(
      false,
    );
    expect(saidByStage('1 door', '11 doors; 2 rooms')).toBe(false);
    expect(saidByStage('', 'anything')).toBe(false);
  });

  it('AD-125 untimed: a done step with 0 ms exactly was not timed; any time, or skipped, is', () => {
    expect(untimed(step({ ms: 0 }))).toBe(true);
    expect(untimed(step({ ms: 0.004 }))).toBe(false);
    expect(untimed(step({ ms: 0, state: 'skipped' }))).toBe(false);
  });

  it('AD-128 traceMs: a measured time under 0.01 ms reads "<0.01 ms", not "0.00 ms"', () => {
    // the demo sample's real stage times (hash, group, route of the IFC model and the scan)
    expect(traceMs(0.0036470009945333004)).toBe('<0.01 ms');
    expect(traceMs(0.00506901741027832)).toBe('<0.01 ms');
    expect(traceMs(0.01)).toBe('0.01 ms');
    expect(traceMs(0.019195984350517392)).toBe('0.02 ms');
    expect(traceMs(34.83)).toBe('34.8 ms');
    expect(traceMs(2968.69)).toBe('3.0 s');
  });
});
