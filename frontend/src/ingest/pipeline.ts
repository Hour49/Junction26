// The pipeline view's data (ingest.md "Pipeline view v5"): which readers each route runs, what the files found,
// and the files grouped by the route they take. Pure: the screen only draws what these return.
import type { FileStatus, ProjectView } from '../api';
import { STEPS, activeStep, isFinished, plural, stepOf } from './ingest';

export type RouteId = 'bim' | 'cad' | 'vector' | 'raster';
/** The routes in the backend's order of preference (ingest.md v4, step 3): model, CAD, drawn PDF, image. */
export const ROUTES: readonly RouteId[] = ['bim', 'cad', 'vector', 'raster'];
export const ROUTE_NAME: Record<RouteId, string> = {
  bim: 'IFC model',
  cad: 'CAD',
  vector: 'Drawn PDF',
  raster: 'Image',
};

/** What a reader setting names when it reads nothing (API.md: `hello` reads nothing). */
const NOTHING = 'hello';

/**
 * A drawing or file on a route this setup has no reader for (`readers[route]` is `hello`): it has a page to look
 * at, but nothing was read off it (backend core/ingest/judge.py `read_nothing`, "not read: this setup has no reader
 * for ..."). The server flags it, never ready, and no question is answered from it (R2-A1, IN-116).
 */
export function unread(
  item: { route?: string | null },
  readers: Record<string, string> | undefined,
): boolean {
  return item.route != null && readers?.[item.route] === NOTHING;
}

/** The drawings something was read off: what "Drawings ready" and the done line count (IN-116). */
export function readDrawings(project: Pick<ProjectView, 'drawings' | 'readers'>) {
  return project.drawings.filter((d) => !unread(d, project.readers));
}

/** The reader a RASTER_COMPONENTS part is, by part (backend app/adapters/raster/__init__.py `GROUPS`). */
const PART: Record<string, string> = {
  elements: 'symbol detector',
  rooms: 'room reader',
  plans: 'plan finder',
  scale: 'scale reader',
};

/**
 * The chips' words, and the step labels (`FileStatus.step`, backend extract steps) each stands for, by the label's
 * start: the words are for a juror, the labels are the server's ("Gemini Carbon check (never counted)").
 */
const LABELS: Record<string, string[]> = {
  'Gemini count decision': ['Gemini Decisions'],
  'Gemini cross-check (not counted)': ['Gemini Carbon check'],
  'Gemini for sheets with few symbols': ['Gemini Carbon reader'],
  'Gemini reader': ['Gemini Carbon reader'],
  'printed scale (Gemini)': ['Printed scale'],
  'drawn-PDF reader': ['Drawn-PDF reader'],
  'schedule tables': ['Schedule tables'],
};
/** The double-check readers' chip starts so: "double check by 2 more readers (not counted)". */
const DOUBLE_CHECK = 'double check';

/** The readers one `part=source` pair stands for (backend app/composition.py `_raster_component`). */
function sourceReaders(part: string, source: string): string[] {
  const at = source.indexOf(':');
  const kind = at < 0 ? source : source.slice(0, at);
  const inner = at < 0 ? '' : source.slice(at + 1);
  const own = PART[part] ?? part;
  switch (kind) {
    case 'decisions':
    case 'decisions-s1536': // the inner source reads, Gemini Decisions picks each count
      return [...sourceReaders(part, inner), 'Gemini count decision'];
    case 'arbiter-t1': // the symbol detector read twice, a model picks between the counts
      return ['symbol detector', 'count arbiter'];
    case 'detector':
    case 'detector-v2':
    case 'detector-v4':
    case 'detector-v8': // one model finds the symbols and the plans
      return ['symbol detector'];
    case 'carbon':
      return ['Gemini reader'];
    case 'gemini':
    case 'regionrooms':
      return ['room reader'];
    case 'one-plan':
      return ['whole page as one plan'];
    default: // region, photo, verda, exp, dir: the part's own reader
      return [own];
  }
}

function parts(spec: string | undefined): [string, string][] {
  return (spec ?? '')
    .split(',')
    .filter((p) => p.includes('='))
    .map((p) => {
      const i = p.indexOf('=');
      return [p.slice(0, i).trim(), p.slice(i + 1).trim()];
    });
}

/**
 * The readers each route runs on this project, as ingest recorded them (`ProjectView.readers`, backend
 * app/composition.py `build_ingest` `names`), in plain words and in the order they run (normalise, then the
 * extract steps as a raster trace lists them). A route whose reader is `hello` gets none: nothing is shown as read
 * that was not. Unknown settings are left out rather than guessed.
 */
export function routeReaders(
  readers: Record<string, string> | undefined,
): Record<RouteId, string[]> {
  const r = readers ?? {};
  const on = (key: string) => r[key] !== undefined && r[key] !== '' && r[key] !== 'off';
  const bim = r.bim && r.bim !== NOTHING ? ['IFC model reader'] : [];
  const cad = r.cad && r.cad !== NOTHING ? ['CAD reader'] : [];
  const vector: string[] = [];
  if (r.vector && r.vector !== NOTHING) {
    vector.push('drawn-PDF reader');
    if (on('tables')) vector.push('schedule tables');
    if (on('vector_fallback')) vector.push('image reading of unruled sheets');
    // the IFC counter measures models and hands every other file to the PDF one (composition second_counter_of)
    if (r.second_counter && r.second_counter !== NOTHING) vector.push('second count');
  }
  const raster: string[] = [];
  if (r.raster && r.raster !== NOTHING) {
    if (r.rectifier && r.rectifier !== 'none') raster.push('photo flattening');
    if (on('raster_printed_scale')) raster.push('printed scale (Gemini)');
    if (on('carbon_levels')) raster.push('Gemini cross-check (not counted)');
    for (const [part, source] of parts(r.raster_components))
      raster.push(...sourceReaders(part, source));
    if (on('raster_photo_components')) raster.push('photo detector');
    const checks = parts(r.double_check_readers).length;
    if (checks) raster.push(`${DOUBLE_CHECK} by ${plural(checks, 'more reader')} (not counted)`);
    if (on('carbon_reader'))
      raster.push(
        r.carbon_reader?.startsWith('large')
          ? 'Gemini for sheets with few symbols'
          : 'Gemini reader',
      );
    if (on('raster_scale')) raster.push('scale from door sizes');
    if (on('raster_tiles')) raster.push('tiles for big sheets');
  }
  const unique = (xs: string[]) => [...new Set(xs)];
  return { bim, cad, vector: unique(vector), raster: unique(raster) };
}

/**
 * What every file goes through before it takes a route (backend composition `_triage` and `decisions_kind`, the
 * `triage` name "classifier=off, sheet_kind=carbon, describer=carbon, judge=rules"), in plain words. None when
 * triage is off or not recorded.
 */
export function triageReaders(readers: Record<string, string> | undefined): string[] {
  const r = readers ?? {};
  const t = Object.fromEntries(
    (r.triage ?? '').split(',').map((p) => p.split('=').map((x) => x.trim())),
  ) as Record<string, string | undefined>;
  const out: string[] = [];
  if (r.decisions_kind === 'True') out.push('scan or photo (Gemini)');
  if (t.classifier === 'rules') out.push('plan or not (rules)');
  if (t.classifier === 'siglip') out.push('plan or not (image model)');
  if (t.sheet_kind && t.sheet_kind !== 'off') out.push('sheet kind (Gemini)');
  if (t.describer && t.describer !== 'off')
    out.push('describes sheets that are not plans (Gemini)');
  if (t.judge && t.judge !== 'off') out.push('keep or set aside (rules)');
  return out;
}

/** Takeoff keys that are not things on the plan: the plan and apartment counts. */
const NOT_THINGS = new Set(['plan', 'apartment']);

/** The things a takeoff counted, by class: plain keys only (no `area:`, `length:`, `room:` or `|` breakdowns). */
export function things(takeoff: Record<string, number> | undefined): [string, number][] {
  return Object.entries(takeoff ?? {}).filter(
    ([k, v]) => v > 0 && !NOT_THINGS.has(k) && !/[:|]/.test(k),
  );
}

/** A file's own reading: not another rendering of a drawing read from another file (its takeoff is that one's). */
const readsItself = (f: FileStatus) => f.source == null || f.source === f.path;

/** Everything counted so far over the files read (each drawing once). */
export function thingsFound(files: readonly FileStatus[]): number {
  return files
    .filter((f) => isFinished(f) && readsItself(f))
    .reduce((n, f) => n + things(f.takeoff).reduce((m, [, v]) => m + v, 0), 0);
}

const WORD: Record<string, [string, string]> = {
  room: ['room', 'rooms'],
  door: ['door', 'doors'],
  window: ['window', 'windows'],
  sink: ['sink', 'sinks'],
  toilet: ['toilet', 'toilets'],
  bathtub: ['bathtub', 'bathtubs'],
  shower: ['shower', 'showers'],
  'shower+bathtub': ['shower-bath', 'shower-baths'],
};

/** "5 rooms, 2 doors, 2 windows, 1 sink, +2 more": the biggest counts first, at most `top`. Empty: nothing found. */
export function foundLine(takeoff: Record<string, number> | undefined, top = 4): string {
  const all = things(takeoff).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const shown = all.slice(0, top).map(([k, v]) => {
    // a class with no word of its own is a plain noun: "wall", "walls"
    const [one, many] = WORD[k] ?? [k, /^[a-z]+$/.test(k) ? `${k}s` : k];
    return plural(v, one, many);
  });
  const more = all.length - shown.length;
  return [...shown, ...(more > 0 ? [`+${String(more)} more`] : [])].join(', ');
}

/** The reader running on a file now (`FileStatus.step`, ingest-ui contract); null from an older server. */
export function fileStep(f: FileStatus): string | null {
  return f.step ?? null;
}

/** The project's phase while it runs (`ProjectStatus.phase`); null from an older server. */
export function projectPhase(p: ProjectView): 'files' | 'index' | null {
  return p.phase ?? null;
}

/**
 * Whether a step label is one of the reader names: "Symbol detector, 8 views" is the "symbol detector", "Gemini
 * Decisions count swap (1536 px) over …" the "Gemini count decision" (`LABELS`).
 */
export function stepMatches(label: string, reader: string): boolean {
  const starts = reader.startsWith(DOUBLE_CHECK) ? ['Double-check reader'] : (LABELS[reader] ?? []);
  const l = label.toLowerCase();
  return [reader, ...starts].some((s) => l.startsWith(s.toLowerCase()));
}

/** What a reader does, in the order the groups run (IN-120). */
export type ReaderGroup = 'prepare' | 'count' | 'checks' | 'few' | 'scale' | 'other';
const GROUP_ORDER: readonly ReaderGroup[] = ['prepare', 'count', 'checks', 'few', 'scale', 'other'];
export const GROUP_LABEL: Record<ReaderGroup, string> = {
  prepare: 'Prepare',
  count: 'Count',
  checks: 'Checks, not counted',
  few: 'If few symbols',
  scale: 'Scale',
  other: 'Also ran',
};
/** The readers that do not count (every other configured reader does: `count`). */
const GROUP_OF: Record<string, ReaderGroup> = {
  'photo flattening': 'prepare',
  'printed scale (Gemini)': 'prepare',
  'tiles for big sheets': 'prepare',
  'Gemini cross-check (not counted)': 'checks',
  'second count': 'checks',
  'Gemini for sheets with few symbols': 'few',
  'scale from door sizes': 'scale',
  'scale reader': 'scale',
};

/** The group a configured reader (a `routeReaders` name) is in, by what it is, not where it sits. */
export function readerGroup(reader: string): ReaderGroup {
  if (reader.startsWith(DOUBLE_CHECK)) return 'checks';
  return GROUP_OF[reader] ?? 'count';
}

/**
 * A lane's readers by what they do, groups in the order they run, readers in theirs. `extra`: step labels the
 * server ran that no reader name covers ("Also ran"). One group: no label (the chips say it all).
 */
export function groupReaders(
  readers: readonly string[],
  extra: readonly string[] = [],
): { group: ReaderGroup; label: string | null; readers: string[] }[] {
  const of = (r: string) => (extra.includes(r) ? 'other' : readerGroup(r));
  const all = [...readers, ...extra];
  const groups = GROUP_ORDER.map((group) => ({
    group,
    label: GROUP_LABEL[group],
    readers: all.filter((r) => of(r) === group),
  })).filter((g) => g.readers.length > 0);
  return groups.length === 1 ? groups.map((g) => ({ ...g, label: null })) : groups;
}

/**
 * A chip's words under its group's label: what the label already says is left out ("Gemini cross-check" under
 * "Checks, not counted", "Gemini reader" under "If few symbols"). With no label, the reader's full name.
 */
export function chipWords(reader: string, labelled: boolean): string {
  if (!labelled) return reader;
  if (readerGroup(reader) === 'few') return 'Gemini reader';
  return reader.replace(/ \(not counted\)$/, '');
}

export type Lane = {
  id: RouteId | 'waiting' | 'other';
  name: string;
  files: FileStatus[];
};

const ORDER: Record<FileStatus['state'], number> = {
  running: 0,
  flagged: 1,
  ready: 2,
  queued: 3,
  text_only: 4,
  set_aside: 5,
};

/**
 * The files by the route they take, routes first (model, CAD, drawn PDF, image), then the files not routed yet,
 * then the ones that ended with no route (set aside, text only). Within a lane: running, flagged, ready, then the
 * rest, in upload order. Empty lanes are left out.
 */
export function lanes(files: readonly FileStatus[]): Lane[] {
  const byRoute = (id: RouteId) => files.filter((f) => f.route === id);
  const all: Lane[] = [
    ...ROUTES.map((id) => ({ id, name: ROUTE_NAME[id], files: byRoute(id) })),
    {
      id: 'waiting',
      name: 'Not routed yet',
      files: files.filter((f) => !f.route && !isFinished(f)),
    },
    { id: 'other', name: 'Not drawings', files: files.filter((f) => !f.route && isFinished(f)) },
  ];
  return all
    .filter((l) => l.files.length > 0)
    .map((l) => ({
      ...l,
      files: l.files
        .map((f, i) => ({ f, i }))
        .sort((a, b) => ORDER[a.f.state] - ORDER[b.f.state] || a.i - b.i)
        .map(({ f }) => f),
    }));
}

/** New tips for this view (docs/ui-tooltips.md style: two short sentences at most). */
export const PIPELINE_TIPS = {
  thingsFound: 'Rooms, doors, windows and fixtures counted so far, each drawing once.',
  conflicts:
    'Places where two readers measured the same thing differently and a person has to choose.',
  flagged: 'Files that were read but need a look before you rely on them.',
  cost: 'What the paid model calls of this upload cost. Cached calls are free.',
  readers: 'The readers this server runs on this route, as it recorded them for this upload.',
  triage:
    'Every file is sorted before it takes a route: a plan is read, another sheet is described or set aside.',
};

const ROUTE_PLURAL: Record<RouteId, [string, string]> = {
  bim: ['IFC model', 'IFC models'],
  cad: ['CAD file', 'CAD files'],
  vector: ['drawn PDF', 'drawn PDFs'],
  raster: ['image', 'images'],
};

/** Flagged files a person should look at; one on a route with no reader counts as "not read" instead (IN-116). */
export const flaggedCount = (files: readonly FileStatus[], readers?: Record<string, string>) =>
  files.filter((f) => f.state === 'flagged' && !unread(f, readers)).length;

/** "2 flagged files need a look": the finished screen's words, which Documents repeats (R4-E15). */
export const needALook = (n: number) =>
  `${plural(n, 'flagged file')} ${n === 1 ? 'needs' : 'need'} a look`;

/**
 * The finished screen's sentence: what was read by which route, then what needs a person. "Read 3 drawn PDFs and
 * 1 image. 2 flagged files need a look; 1 not read; 1 set aside." Each drawing once (another rendering is not
 * counted). A flagged file on a route with no reader (`unread`) is counted as "not read", not as read or flagged
 * (IN-116).
 */
export function routeSummary(
  files: readonly FileStatus[],
  readers?: Record<string, string>,
): string {
  const notRead = files.filter((f) => f.state === 'flagged' && unread(f, readers)).length;
  const read = ROUTES.map(
    (id) =>
      [
        id,
        files.filter((f) => f.route === id && f.drawing_id && readsItself(f) && !unread(f, readers))
          .length,
      ] as const,
  )
    .filter(([, n]) => n > 0)
    .map(([id, n]) => plural(n, ...ROUTE_PLURAL[id]));
  const list =
    read.length > 1
      ? `${read.slice(0, -1).join(', ')} and ${read[read.length - 1] ?? ''}`
      : read[0];
  const flagged = flaggedCount(files, readers);
  const aside = files.filter((f) => f.state === 'set_aside').length;
  const person = [
    flagged ? needALook(flagged) : '',
    notRead ? `${String(notRead)} not read` : '',
    aside ? `${String(aside)} set aside` : '',
  ].filter(Boolean);
  return [list ? `Read ${list}.` : '', person.length ? `${person.join('; ')}.` : '']
    .filter(Boolean)
    .join(' ');
}

/** For each file step (1-8), how many files are being read in it now. */
export function busySteps(files: readonly FileStatus[]): Map<number, number> {
  const busy = new Map<number, number>();
  for (const f of files)
    if (f.state === 'running') busy.set(stepOf(f.stage), (busy.get(stepOf(f.stage)) ?? 0) + 1);
  return busy;
}

/**
 * The step to name while it runs: groups are read in parallel, so the one most files are being read in now (a tie:
 * the later one); with none running, the lowest step a file still waits in (`activeStep`, v4); Index once the server
 * says it is in its last phase or every file is finished.
 */
export function headlineStep(project: ProjectView): number {
  if (projectPhase(project) === 'index') return STEPS.length;
  const low = activeStep(project.files);
  let best = low;
  let most = 0;
  for (const [n, count] of busySteps(project.files))
    if (count > most || (count === most && n > best)) [best, most] = [n, count];
  return best;
}
