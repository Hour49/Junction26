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

/** The readers one `part=source` pair stands for (backend app/composition.py `_raster_component`). */
function sourceReaders(part: string, source: string): string[] {
  const at = source.indexOf(':');
  const kind = at < 0 ? source : source.slice(0, at);
  const inner = at < 0 ? '' : source.slice(at + 1);
  const own = PART[part] ?? part;
  switch (kind) {
    case 'decisions':
    case 'decisions-s1536': // the inner source counts, Gemini Decisions settles each count
      return [...sourceReaders(part, inner), 'count arbiter'];
    case 'arbiter-t1':
      return [own, 'count arbiter'];
    case 'carbon':
      return ['Carbon'];
    case 'gemini':
    case 'regionrooms':
      return ['room reader'];
    case 'one-plan':
      return ['whole page as one plan'];
    default: // detector*, region, photo, verda, exp, dir: the part's own reader
      return [own];
  }
}

function parts(spec: string | undefined): [string, string][] {
  return (spec ?? '')
    .split(',')
    .filter((p) => p.includes('='))
    .map((p) => {
      const i = p.indexOf('=');
      return [p.slice(0, i), p.slice(i + 1)];
    });
}

/**
 * The readers each route runs on this project, as ingest recorded them (`ProjectView.readers`, backend
 * app/composition.py `build_ingest` `names`), in plain words. A route whose reader is `hello` gets none: nothing
 * is shown as read that was not. Unknown settings are left out rather than guessed.
 */
export function routeReaders(
  readers: Record<string, string> | undefined,
): Record<RouteId, string[]> {
  const r = readers ?? {};
  const on = (key: string) => r[key] !== undefined && r[key] !== '' && r[key] !== 'off';
  const bim = r.bim && r.bim !== NOTHING ? ['IFC object reader'] : [];
  const cad = r.cad && r.cad !== NOTHING ? ['CAD reader'] : [];
  const vector: string[] = [];
  if (r.vector && r.vector !== NOTHING) {
    vector.push('vector reader');
    if (r.tables && r.tables !== 'off') vector.push('schedule reader');
    if (r.second_counter && r.second_counter !== NOTHING) vector.push('second count');
    if (on('vector_fallback')) vector.push('image reading of unruled sheets');
  }
  const raster: string[] = [];
  if (r.raster && r.raster !== NOTHING) {
    for (const [part, source] of parts(r.raster_components))
      raster.push(...sourceReaders(part, source));
    if (on('raster_photo_components')) raster.push('photo detector');
    if (on('carbon_reader')) raster.push('Carbon');
    if (on('raster_scale')) raster.push('scale from doors');
    if (on('raster_printed_scale')) raster.push('printed scale');
    const seconds = parts(r.double_check_readers).length;
    if (seconds) raster.push(`second readers (${String(seconds)})`);
    if (on('carbon_levels')) raster.push('Carbon level check');
    if (on('raster_tiles')) raster.push('tiles for big sheets');
  }
  const unique = (xs: string[]) => [...new Set(xs)];
  return { bim, cad, vector: unique(vector), raster: unique(raster) };
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

/** Whether a step label is one of the reader names: "Symbol detector, 8 views" is the "symbol detector". */
export function stepMatches(label: string, reader: string): boolean {
  return label.toLowerCase().startsWith(reader.toLowerCase());
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
};

const ROUTE_PLURAL: Record<RouteId, [string, string]> = {
  bim: ['IFC model', 'IFC models'],
  cad: ['CAD file', 'CAD files'],
  vector: ['drawn PDF', 'drawn PDFs'],
  raster: ['image', 'images'],
};

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
  const flagged = files.filter((f) => f.state === 'flagged' && !unread(f, readers)).length;
  const aside = files.filter((f) => f.state === 'set_aside').length;
  const person = [
    flagged ? `${plural(flagged, 'flagged file')} ${flagged === 1 ? 'needs' : 'need'} a look` : '',
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
