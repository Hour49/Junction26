import type { Info, Resolved, RulePack } from './types';

const UNITS: Record<string, string> = { m: 'm', m2: 'm²', m3: 'm³', ft: 'ft', ft2: 'ft²' };

/** A count's unit: 'rooms' is the backend's room count (second_count.py, printed.py). */
export const isCountUnit = (unit: string | null): boolean => unit === 'count' || unit === 'rooms';

/** A value as every screen shows it: a count as an integer, anything else with 2 decimals and its unit. */
export function formatValue(value: number, unit: string | null): string {
  if (unit === null || isCountUnit(unit)) return String(Math.round(value));
  return `${value.toFixed(2)} ${UNITS[unit] ?? unit}`;
}

/** `YYYY-MM-DD HH:MM UTC`, whatever the browser's time zone. */
export function formatTime(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return `${at.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

/** `YYYY-MM-DD HH:MM:SS UTC`: tells two uploads of the same name apart (R4-E19). */
export function formatTimeSeconds(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return `${at.toISOString().slice(0, 19).replace('T', ' ')} UTC`;
}

// Reader ids as /api/info and DrawingView.reader give them (backend app/settings.py), as plain labels.
const READERS: Record<string, string> = {
  composite: 'image reader',
  pdf: 'PDF vector reader',
  ifc: 'IFC model',
  ifc_sheet: 'IFC sheet reader', // a sheet read with its IFC model; the model is the second count
  templates: 'question templates',
  hello: 'not read',
  dev: 'best estimate from dev answers',
  r3: 'photo rectifier',
  gemini: 'Gemini',
  off: 'off',
  False: 'off',
  True: 'on',
  none: 'none',
};

/** A reader id as a plain label; no id is "no reader"; an id with no label shows as is. */
export function readerName(id: string | null | undefined): string {
  if (id === null || id === undefined) return 'no reader';
  return READERS[id] ?? id;
}

// Measuring methods (backend MeasureMethod), in the backend's own words (app/core/pipeline/second_count.py METHODS).
const METHODS: Record<string, string> = {
  printed_label: 'printed room areas',
  polygon_x_scale: 'room outlines × sheet scale',
  plan_drawing: 'sheet',
  parser: 'sheet text',
  detector: 'detector',
  ifc_model: 'IFC model',
  schedule: 'schedule',
  printed_total: 'printed total',
  summed_rooms: 'sum of rooms',
  scale_text: 'printed scale',
  scale_bar: 'scale bar',
  dimension_lines: 'dimension lines',
  annotation: 'annotation',
  other: 'other method',
};

/** A measuring-method id as a plain label; no id is "no method"; an id with no label shows as is. */
export function methodName(id: string | null | undefined): string {
  if (id === null || id === undefined) return 'no method';
  return METHODS[id] ?? id;
}

/** The rule packs `/api/info` lists (#139); none before info loads. */
export function rulePacksOf(info: Info | null): RulePack[] {
  return info?.rule_packs ?? [];
}

/** A drawing's name on screen (shared.md "Plain drawing names"): the file name without its folders. A plain title
 * needs the backend (API ask A3); dataset ids are not prettified here. */
export const drawingName = (file: string): string => file.slice(file.lastIndexOf('/') + 1);

/** The one place that decides a drawing's on-screen name (shared.md "Plain drawing names"): the backend's plain
 * `name` (#224: "Drawn plan 1", "Building model 1"), else the file name. Takes any shape with a `file`. */
export const drawingLabel = (d: { name?: string | null; file: string }): string =>
  d.name || drawingName(d.file);

/** Who picked (resolver.md "Words"): `by`'s prefix capitalised, 'carbon:gemini-4-carbon' → 'Carbon'. */
export function resolverName(by: string): string {
  const name = by.split(':', 1)[0] ?? by;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** The model id after the first ':' (for a tooltip only); the whole string when there is none. */
export const resolverModel = (by: string): string => by.slice(by.indexOf(':') + 1);

/** A model's pick is in use: picked, and no person needed, settled or signed (resolver.md "Data"). */
export const pickInUse = (r: {
  resolved?: Resolved | null;
  needs_person: boolean;
  settled?: unknown;
  signed?: unknown;
}): boolean => r.resolved?.verdict === 'picked' && !r.needs_person && !r.settled && !r.signed;
