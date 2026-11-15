// The scan as one CSV (export.md): one row per item, a `kind` column, RFC 4180, UTF-8 with BOM.
import type {
  ConflictEntry,
  IssueList,
  ProjectChecks,
  ProjectReview,
  ProjectView,
  Takeoff,
} from '../api';

export const COLUMNS = [
  'kind',
  'file',
  'drawing_id',
  'page',
  'item',
  'type',
  'label',
  'value',
  'unit',
  'width_m',
  'height_m',
  'status',
  'detail',
] as const;

type Cell = string | number | null | undefined;
export type CsvRow = Partial<Record<(typeof COLUMNS)[number], Cell>>;

/** extraction_v1 (decision 0004), only the fields the export reads; `getModel` is untyped. */
interface Model {
  rooms?: {
    id: string;
    type?: string;
    label?: string | null;
    page?: number;
    area_m2?: number | null;
    area_status?: string;
  }[];
  elements?: { id: string; class: string; page?: number }[];
  model_objects?: {
    element?: string | null;
    quantities?: { width_m?: number; height_m?: number };
  }[];
}

export interface DrawingScan {
  drawing_id: string;
  file: string;
  takeoff: Takeoff;
  model: unknown;
}

export interface Scan {
  project: ProjectView;
  review: ProjectReview;
  issues: IssueList;
  /** null without a pack in the route. */
  checks: ProjectChecks | null;
  drawings: DrawingScan[];
}

/** As conflicts.ts words it: who settled the disagreement, if anyone. */
function conflictStatus(c: ConflictEntry): string {
  if (c.signed) return 'signed off';
  if (c.needs_person) return 'open';
  return c.settled ? 'settled by a person' : 'settled by rule';
}

function conflictDetail(c: ConflictEntry): string {
  const values = c.conflict.values.map((v) =>
    [v.method, String(v.value), v.unit].filter(Boolean).join(' '),
  );
  const rule = c.conflict.resolution ? `; ${c.conflict.resolution.rule}` : '';
  return values.join(' vs ') + rule;
}

function drawingRows({ drawing_id, file, takeoff, model }: DrawingScan): CsvRow[] {
  const m = (model ?? {}) as Model;
  const at = { file, drawing_id };
  const sizes = new Map(
    (m.model_objects ?? []).filter((o) => o.element).map((o) => [o.element, o.quantities]),
  );
  return [
    ...(m.rooms ?? []).map((r) => ({
      kind: 'room',
      ...at,
      page: r.page,
      item: r.id,
      type: r.type,
      label: r.label,
      value: r.area_m2,
      unit: r.area_m2 == null ? undefined : 'm2',
      status: r.area_status,
    })),
    ...(m.elements ?? []).map((e) => ({
      kind: 'element',
      ...at,
      page: e.page,
      item: e.id,
      type: e.class,
      width_m: sizes.get(e.id)?.width_m,
      height_m: sizes.get(e.id)?.height_m,
    })),
    ...takeoff.quantities.map((q) => ({
      kind: 'quantity',
      ...at,
      item: q.key,
      type: q.measure,
      label: q.label,
      value: q.value,
      unit: q.unit,
      status: q.status,
      detail: [
        q.settled ? `settled ${String(q.settled.value)}` : '',
        q.signed ? `signed by ${q.signed.by}` : '',
      ]
        .filter(Boolean)
        .join('; '),
    })),
  ];
}

export function scanRows(scan: Scan): CsvRow[] {
  const { project, review, issues, checks } = scan;
  return [
    ...project.files.map((f) => ({
      kind: 'file',
      file: f.path,
      drawing_id: f.drawing_id,
      item: f.id,
      type: f.kind,
      status: f.state,
      detail: f.reason,
    })),
    // a set-aside file is listed under files too: one row, the one with its id
    ...project.skipped
      .filter((s) => !project.files.some((f) => f.path === s.path))
      .map((s) => ({
        kind: 'file',
        file: s.path,
        status: 'skipped',
        detail: s.reason,
      })),
    ...scan.drawings.flatMap(drawingRows),
    ...review.conflicts.map((c) => ({
      kind: 'conflict',
      file: c.file,
      drawing_id: c.drawing_id,
      item: c.quantity,
      label: c.label,
      value: c.value,
      status: conflictStatus(c),
      detail: conflictDetail(c),
    })),
    ...(checks?.drawings ?? []).flatMap((d) =>
      d.rules.flatMap((rule) =>
        rule.results.map((r) => ({
          kind: 'check',
          file: d.file,
          drawing_id: d.drawing_id,
          page: r.marks[0]?.page,
          item: r.id,
          type: r.rule_id,
          label: r.subject.label,
          value: r.value,
          unit: r.unit,
          status: r.status,
          detail: r.why,
        })),
      ),
    ),
    ...issues.issues.map((i) => ({
      kind: 'issue',
      file: i.file,
      drawing_id: i.drawing_id,
      page: i.page,
      item: i.id,
      type: i.kind,
      label: i.severity,
      status: i.state,
      detail: i.why,
    })),
  ];
}

function cell(value: Cell): string {
  if (value == null) return '';
  if (typeof value === 'number') return String(value);
  // A spreadsheet runs a cell that starts like a formula (OWASP CSV injection).
  const text = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180 with CRLF, and a BOM so Excel reads UTF-8. */
export function toCsv(rows: readonly CsvRow[]): string {
  const lines = [COLUMNS.join(','), ...rows.map((r) => COLUMNS.map((c) => cell(r[c])).join(','))];
  return `\uFEFF${lines.join('\r\n')}\r\n`;
}

/** `<project name>-scan-<YYYY-MM-DD>.csv`, the local date, the name without `.zip` and safe for a file system. */
export function fileName(projectName: string, date: Date): string {
  const base = projectName.replace(/\.zip$/i, '').replace(/[/\\:*?"<>|]/g, '-');
  const ymd = [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((n) => String(n).padStart(2, '0'))
    .join('-');
  return `${base}-scan-${ymd}.csv`;
}
