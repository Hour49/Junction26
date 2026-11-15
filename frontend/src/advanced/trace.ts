// One file's trace as time and decisions (docs/specs/frontend/advanced-ingest.md "Trace view v5", AD-1xx).
import type { FileStatus, FileTrace, ProjectView, StageTrace, StepTrace, Takeoff } from '../api';
import { formatValue } from '../api/format';
import { STAGE_LABEL, formatMs, kindLabel, plural, routeLabel } from '../ingest/ingest';
import { CLASS_LABEL, classLine, planChance } from '../ingest/triage';
import { calledNotADrawing } from './advanced';

export type Step = StepTrace;

/** A stage's steps; an older server sends none (the field is left out). */
export const stepsOf = (s: Partial<Pick<StageTrace, 'steps'>>): readonly Step[] => s.steps ?? [];

/** The project's last phase's steps (judge, describe, index); an older server sends none. */
export const stepsAfter = (p: Partial<Pick<ProjectView, 'index_steps'>>): readonly Step[] =>
  p.index_steps ?? [];

/** A span on a time axis as fractions of the axis (0-1). */
export interface Span {
  left: number;
  width: number;
}

/**
 * Each stage's span on the file's time axis: stages run one after the other, so a stage begins where the ones
 * before it ended. Null spans when no time was recorded (the axis would be made up).
 */
export function stageSpans(stages: readonly StageTrace[]): (Span | null)[] {
  const total = stages.reduce((sum, s) => sum + Math.max(0, s.ms), 0);
  let at = 0;
  return stages.map((s) => {
    const ms = Math.max(0, s.ms);
    const span = total > 0 ? { left: at / total, width: ms / total } : null;
    at += ms;
    return span;
  });
}

/** Each step's span on an axis of `ms` (its stage's time), stretched to the latest step end if that is later. */
export function stepSpans(steps: readonly Step[], ms: number): (Span | null)[] {
  const end = Math.max(ms, ...steps.map((s) => s.at_ms + s.ms));
  return steps.map((s) =>
    end > 0 ? { left: Math.min(1, s.at_ms / end), width: Math.min(1, s.ms / end) } : null,
  );
}

/** The most steps running at one moment (2+ means readers ran side by side). Skipped steps did not run. */
export function sideBySide(steps: readonly Step[]): number {
  const edges = steps
    .filter((s) => s.state !== 'skipped' && s.ms > 0)
    .flatMap((s) => [
      { t: s.at_ms, d: 1 },
      { t: s.at_ms + s.ms, d: -1 },
    ])
    // an end before a start at the same moment: back-to-back steps are not side by side
    .sort((a, b) => a.t - b.t || a.d - b.d);
  let now = 0;
  let peak = 0;
  for (const e of edges) {
    now += e.d;
    peak = Math.max(peak, now);
  }
  return peak;
}

/** One row of a stage's step list (AD-121): a step, the head of steps that ran side by side, or a time no step ran. */
export type StepRow =
  | { kind: 'step'; step: Step; span: Span | null; together: boolean }
  | { kind: 'together'; from: number; to: number; count: number; peak: number }
  | { kind: 'idle'; from: number; to: number };

/**
 * A stage's steps in their order, cut where no step was running (AD-121). Steps whose times overlap are one run
 * "side by side", headed by its time and drawn on its own axis (from its first start to its last end), so overlaps
 * show at any stage length; a lone step keeps the stage axis. A stretch with no step running, at least 1 s and a
 * tenth of the stage, gets its own row: "the first step began at …" before the first, else "no step ran …". The
 * data names no reason for the wait, so neither does the row.
 */
export function stepRows(steps: readonly Step[], ms: number): StepRow[] {
  const end = (s: Step) => s.at_ms + (s.state === 'skipped' ? 0 : Math.max(0, s.ms));
  const runs: { steps: Step[]; spans: (Span | null)[]; from: number; to: number }[] = [];
  const onStage = stepSpans(steps, ms);
  steps.forEach((s, i) => {
    const run = runs.at(-1);
    if (run && s.at_ms < run.to) {
      run.steps.push(s);
      run.spans.push(onStage[i] ?? null);
      run.to = Math.max(run.to, end(s));
    } else runs.push({ steps: [s], spans: [onStage[i] ?? null], from: s.at_ms, to: end(s) });
  });
  const axis = Math.max(ms, ...steps.map(end));
  const idleAt = Math.max(1000, axis / 10);
  const rows: StepRow[] = [];
  let ran = 0;
  for (const run of runs) {
    if (run.from - ran >= idleAt) rows.push({ kind: 'idle', from: ran, to: run.from });
    const peak = sideBySide(run.steps);
    const width = run.to - run.from;
    if (peak > 1 && width > 0) {
      rows.push({ kind: 'together', from: run.from, to: run.to, count: run.steps.length, peak });
      for (const s of run.steps)
        rows.push({
          kind: 'step',
          step: s,
          together: true,
          span: {
            left: Math.min(1, (s.at_ms - run.from) / width),
            width: Math.min(1, (end(s) - s.at_ms) / width),
          },
        });
    } else
      run.steps.forEach((s, k) => {
        rows.push({ kind: 'step', step: s, together: false, span: run.spans[k] ?? null });
      });
    ran = Math.max(ran, run.to);
  }
  return rows;
}

/**
 * True when the stage's did line already says a step's did (AD-125): the same line, or one of its parts, standing
 * at the start or after "; " or ": " and ending the line or a "; " part ("1 page, …" in a normalise did of
 * "rectified …; 1 page, …"). A did found mid-sentence ("1 plan" in "26 rooms, 1 plan, …") is not a repeat.
 */
export function saidByStage(stepDid: string, stageDid: string): boolean {
  const did = stepDid.trim();
  if (!did) return false;
  for (let at = stageDid.indexOf(did); at >= 0; at = stageDid.indexOf(did, at + 1)) {
    const before = stageDid.slice(0, at);
    const after = stageDid.slice(at + did.length);
    if ((at === 0 || /(; |: )$/.test(before)) && (after === '' || after.startsWith(';')))
      return true;
  }
  return false;
}

/**
 * A measured time in the trace (AD-128): under 0.01 ms, which `formatMs` rounds to a fake-looking "0.00 ms", it
 * reads "<0.01 ms", as `formatCost` says "<$0.01". 0 exactly is not timed: callers show no time for it (`untimed`).
 */
export function traceMs(ms: number): string {
  return ms > 0 && ms < 0.01 ? '<0.01 ms' : formatMs(ms);
}

/** A step the server did not time: done with 0 ms exactly (the second count's checks today). */
export const untimed = (s: Step): boolean => s.state === 'done' && s.ms === 0;

/** The conflicts a check step found (`found.conflict`, the second count's steps); 0 for any other step. */
export const conflictsOf = (s: Step): number => s.found?.conflict ?? 0;

/** "31 doors, 12 windows" from a step's counts, largest first; "" with none. */
export function foundLine(found: Readonly<Record<string, number>> | undefined): string {
  return Object.entries(found ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => plural(n, k))
    .join(', ');
}

export type Tone = 'ok' | 'warn' | 'bad' | 'info';

/** One decision on the file's way through, said where it happened. */
export interface Decision {
  key: 'triage' | 'route' | 'second' | 'outcome';
  where: string; // the stage it happened in
  title: string;
  lines: string[];
  tone: Tone;
}

/** A quantity measured two ways, with both values. */
export interface Disagreement {
  label: string;
  first: string;
  second: string;
}

/** The conflicts of a takeoff the review lists (`disputes`; older servers: every `conflict` row). */
export function disagreements(takeoff: Takeoff): Disagreement[] {
  const disputed = new Set(takeoff.disputes);
  return takeoff.quantities
    .filter(
      (r) =>
        r.status === 'conflict' &&
        r.second !== null &&
        (takeoff.disputes.length === 0 || disputed.has(r.key)),
    )
    .map((r) => ({
      label: r.label,
      first: formatValue(r.first?.value ?? r.value, r.unit),
      second: formatValue(r.second?.value ?? 0, r.unit),
    }));
}

const SHEET_DECISION: Record<string, string> = {
  read: 'read as a plan',
  doubt: 'read, but marked doubtful',
  set_aside: 'set aside',
};

const stage = (t: FileTrace, s: StageTrace['stage']) => t.stages.find((x) => x.stage === s);

function triageDecision(t: FileTrace): Decision | null {
  const f = t.file;
  const tri = f.triage;
  if (tri) {
    const lines = [`${classLine(tri)}: plan chance ${planChance(tri.p_plan)}, by ${tri.method}.`];
    const sheet = tri.sheet;
    if (sheet) {
      const name = [sheet.title, sheet.sheet_number].filter(Boolean).join(', ');
      lines.push(
        `The sheet reader saw ${sheet.kind_words}${name ? ` (${name})` : ''}: ${SHEET_DECISION[sheet.decision] ?? sheet.decision}.`,
      );
      if (sheet.advanced && sheet.advanced_why) lines.push(`Read closer: ${sheet.advanced_why}`);
    }
    if (tri.note) lines.push(tri.note);
    // read because the sheet-kind step only warns, but it called the sheet not a drawing: no "A floor plan" (AD-132)
    if (calledNotADrawing(f))
      return {
        key: 'triage',
        where: STAGE_LABEL.identify,
        title: 'Not a drawing, read anyway',
        lines,
        tone: 'warn',
      };
    return {
      key: 'triage',
      where: STAGE_LABEL.identify,
      title:
        tri.class === 'floor_plan' ? 'A floor plan' : `Not a floor plan: ${CLASS_LABEL[tri.class]}`,
      lines,
      tone: tri.class === 'floor_plan' ? 'ok' : 'info',
    };
  }
  const id = stage(t, 'identify');
  if (!id) return null;
  return {
    key: 'triage',
    where: STAGE_LABEL.identify,
    title: `Identified as ${kindLabel(f.kind)}`,
    lines: [id.did],
    tone: id.failure ? 'bad' : 'info',
  };
}

/** The file a file was read with when its group was read from another one (`source`), else null (AD-119). */
export const readWith = (f: Pick<FileStatus, 'path' | 'source'>): string | null =>
  f.source && f.source !== f.path ? f.source : null;

function routeDecision(t: FileTrace): Decision | null {
  const f = t.file;
  const route = stage(t, 'route');
  if (!route) return null;
  const lines = [route.did];
  const group = stage(t, 'group');
  if (group?.did) lines.push(`Grouped: ${group.did}`);
  if (f.source && f.source !== f.path)
    lines.push(`Its plan is read once, from ${f.source}; this file is not read again.`);
  const cache = stage(t, 'cache');
  if (cache) lines.push(`Read before: ${cache.did}`);
  return {
    key: 'route',
    where: STAGE_LABEL.route,
    title: readWith(f)
      ? `Read with ${readWith(f) ?? ''}`
      : f.route
        ? `The ${routeLabel(f.route)}`
        : 'Not routed',
    lines,
    tone: route.failure ? 'bad' : f.route ? 'info' : 'warn',
  };
}

function secondDecision(t: FileTrace, conflicts: readonly Disagreement[] | null): Decision | null {
  const sc = t.second_count;
  if (!sc) return null;
  if (sc.measured === 0)
    return {
      key: 'second',
      where: STAGE_LABEL.second_count,
      title: 'Nothing measured a second way',
      lines: ['No quantity of this drawing has a second, independent method today.'],
      tone: 'info',
    };
  const twice = `${plural(sc.measured, 'quantity', 'quantities')} measured a second way`;
  if (sc.conflicts === 0)
    return {
      key: 'second',
      where: STAGE_LABEL.second_count,
      title: 'Both counts agree',
      lines: [`${twice}: all agree.`],
      tone: 'ok',
    };
  return {
    key: 'second',
    where: STAGE_LABEL.second_count,
    title: `${plural(sc.conflicts, 'conflict')} between the counts`,
    lines: [
      `${twice}: ${String(sc.conflicts)} ${sc.conflicts === 1 ? 'disagrees, and goes to you as a conflict' : 'disagree, and go to you as conflicts'}.`,
      ...(conflicts ?? []).map(
        (c) => `${c.label}: ${c.first} on the drawing, ${c.second} the second way.`,
      ),
    ],
    tone: 'warn',
  };
}

const OUTCOME: Record<FileStatus['state'], { title: string; tone: Tone }> = {
  ready: { title: 'Ready to ask', tone: 'ok' },
  flagged: { title: 'Flagged for a look', tone: 'warn' },
  text_only: { title: 'Kept for its text', tone: 'info' },
  set_aside: { title: 'Set aside', tone: 'info' },
  queued: { title: 'Waiting to be read', tone: 'info' },
  running: { title: 'Being read now', tone: 'info' },
};

function outcomeDecision(t: FileTrace): Decision {
  const f = t.file;
  const o = OUTCOME[f.state];
  const failed = t.stages.find((s) => s.failure);
  const now = t.stages.at(-1);
  const lines =
    f.state === 'running' || f.state === 'queued'
      ? [now ? `Last stage: ${STAGE_LABEL[now.stage]}, ${formatMs(f.ms)} so far.` : 'Not started.']
      : reasonLines(f.reason);
  if (failed) lines.push(`${STAGE_LABEL[failed.stage]} failed: ${failed.failure ?? ''}`);
  return {
    key: 'outcome',
    where: 'Outcome',
    title: o.title,
    lines,
    tone: failed && f.state !== 'ready' ? 'bad' : o.tone,
  };
}

/** The decisions on the file's way, in pipeline order: what it is, its route, the second count, the outcome. */
export function decisions(
  t: FileTrace,
  conflicts: readonly Disagreement[] | null = null,
): Decision[] {
  return [
    triageDecision(t),
    routeDecision(t),
    secondDecision(t, conflicts),
    outcomeDecision(t),
  ].filter((d): d is Decision => d !== null);
}

/** Stages grouped for the colour of a bar segment: reading the upload, the picture, the plan, the check, storing. */
export type Phase = 'open' | 'page' | 'read' | 'check' | 'store';

export const PHASE: Record<StageTrace['stage'], Phase> = {
  unpack: 'open',
  hash: 'open',
  identify: 'open',
  group: 'open',
  route: 'open',
  cache: 'open',
  normalise: 'page',
  extract: 'read',
  second_count: 'check',
  takeoff: 'store',
  write: 'store',
};

export const PHASE_LABEL: Record<Phase, string> = {
  open: 'Open and route',
  page: 'Normalise',
  read: 'Read the plan',
  check: 'Second count',
  store: 'Takeoff and store',
};

/** True when a stage's output only repeats its did line: contained in it, the route of a "<route> route" did, or
 * the whole of a hash whose start the did gives (AD-117). */
export function repeats(s: StageTrace): boolean {
  const out = s.output.trim();
  if (!out || s.did.includes(out)) return true;
  if (s.stage === 'route' && s.did.includes(routeLabel(out))) return true;
  const last = s.did.split(' ').at(-1) ?? '';
  return last.length >= 8 && out.startsWith(last);
}

/**
 * A file's reason as plain lines (AD-118): the backend joins reasons with "; " and may end with a bracketed summary
 * of what was read, "… (room areas) (7 elements, 5 rooms, …)"; that summary becomes its own "Found: …" line.
 */
export function reasonLines(reason: string): string[] {
  const text = reason.trim();
  const m = /^(.*\S) \(([^()]*,[^()]*)\)$/.exec(text);
  const lines = (m?.[1] ?? text)
    .split('; ')
    .map((l) => l.trim())
    .filter(Boolean);
  if (m?.[2]) lines.push(`Found: ${m[2]}`);
  return lines.map((l) => (/[.!?]$/.test(l) ? l : `${l}.`));
}

const COUNT_FIRST = ['room', 'door', 'window'];
const countRank = (k: string) => {
  const i = COUNT_FIRST.indexOf(k);
  return i < 0 ? COUNT_FIRST.length : i;
};

/** The takeoff's plain class counts above zero ("5 rooms"), rooms, doors, windows first, then by name, at most 8 (AD-120). */
export function keyCounts(takeoff: Readonly<Record<string, number>> | undefined): string[] {
  return Object.entries(takeoff ?? {})
    .filter(([k, n]) => /^[a-z_]+$/.test(k) && n > 0)
    .sort(([a], [b]) => countRank(a) - countRank(b) || a.localeCompare(b))
    .slice(0, 8)
    .map(([k, n]) => plural(n, k.replaceAll('_', ' ')));
}

/** A file's stages merged into runs of one phase, for a calm bar: five segments at most in pipeline order. */
export function phaseRuns(
  stages: readonly StageTrace[],
): { phase: Phase; ms: number; failed: boolean }[] {
  const runs: { phase: Phase; ms: number; failed: boolean }[] = [];
  for (const s of stages) {
    const phase = PHASE[s.stage];
    const last = runs.at(-1);
    if (last?.phase === phase) {
      last.ms += Math.max(0, s.ms);
      last.failed ||= !!s.failure;
    } else runs.push({ phase, ms: Math.max(0, s.ms), failed: !!s.failure });
  }
  return runs;
}

/** "5 rooms · 2 doors · 1 window" from a file's takeoff, "" when it counts none of them. */
export function foundOf(file: FileStatus): string {
  const t = file.takeoff ?? {};
  return (
    [
      ['room', 'room'],
      ['door', 'door'],
      ['window', 'window'],
    ] as const
  )
    .filter(([k]) => typeof t[k] === 'number')
    .map(([k, word]) => plural(t[k] ?? 0, word))
    .join(' · ');
}

/** The stage that took longest, for the row's headline; null with no time. */
export function longest(stages: readonly StageTrace[]): StageTrace | null {
  return stages.reduce<StageTrace | null>((a, s) => (s.ms > (a?.ms ?? 0) ? s : a), null);
}
