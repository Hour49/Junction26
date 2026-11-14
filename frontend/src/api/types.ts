import type { components } from './schema';

type Schemas = components['schemas'];

export type Info = Schemas['Info'];
export type Limits = Schemas['Limits'];
export type Started = Schemas['Started'];
export type ProjectList = Schemas['ProjectList'];
export type ProjectSummary = Schemas['ProjectSummary'];
export type ProjectView = Schemas['ProjectView'];
export type FileStatus = Schemas['FileStatus'];
export type DrawingEntry = Schemas['DrawingEntry'];
export type Rendering = Schemas['Rendering'];
export type FileTrace = Schemas['FileTrace'];
export type ProjectTrace = Schemas['ProjectTrace'];
export type ProjectQuestions = Schemas['ProjectQuestions'];
export type AskedQuestion = Schemas['AskedQuestion'];
export type StageTrace = Schemas['StageTrace'];
export type ProjectReview = Schemas['ProjectReview'];
export type DrawingReview = Schemas['DrawingReview'];
export type ConflictEntry = Schemas['ConflictEntry'];
export type DrawingView = Schemas['DrawingView'];
export type PageView = Schemas['PageView'];
export type Normalised = Schemas['Normalised'];
export type Reader = Schemas['Reader'];
export type Suggestion = Schemas['Suggestion'];
export type AskRequest = Schemas['AskRequest'];
export type AnswerView = Schemas['AnswerView'];
export type ProjectAnswer = Schemas['ProjectAnswer'];
export type Refusal = Schemas['Refusal'];
export type MarkView = Schemas['MarkView'];
export type Row = Schemas['Row'];
export type Scope = Schemas['Scope'];
export type RuleText = Schemas['RuleText'];
export type QuantityConflict = Schemas['QuantityConflict'];
export type Settled = Schemas['Settled'];
export type SignOff = Schemas['SignOff'];
export type Proof = Schemas['Proof'];
export type Takeoff = Schemas['Takeoff'];
export type Edit = Schemas['Edit'];
export type SignOffRequest = Schemas['SignOffRequest'];

/** The answer confidence (board #14): `score` is a raw model choice score, never a probability. */
export type Signal = Schemas['Signal'];

// #142 shapes, hand-typed until the backend PRs land (records 0009-building-code-checks, 0008-located-issues);
// then each becomes a Schemas[...] re-export and src/api/testing.ts gives way to the backend fixtures.

/** Page fractions, `x0 <= x1`, `y0 <= y1`, as `MarkView.box`. */
export type Box = [number, number, number, number];
/** `[[x, y], …]` in page fractions, as `MarkView.polygon`. */
export type Polygon = [number, number][];

export interface Clause {
  ref: string;
  url: string;
  quote: string;
  /** Null when the law is in English. */
  quote_en: string | null;
}

export interface Rule {
  id: string;
  title: string;
  /** Never shown; `comparison_text` is. */
  op: string;
  comparison: string;
  /** Plain words, e.g. "at least". */
  comparison_text: string;
  limit: number;
  unit: string;
  /** `MarkView.room_type` values and element classes. */
  applies_to: string[];
  clause: Clause;
}

export interface RulePack {
  id: string;
  /** ISO upper case, e.g. "FI". */
  country: string;
  country_name: string;
  /** The pack's display name. */
  name: string;
  law: string;
  version: string;
  /** Shown verbatim: "A pre-check of a few rules, not a compliance certificate." */
  note: string;
  rules: Rule[];
}

export type CheckStatus = 'pass' | 'fail' | 'cannot_tell';

export interface CheckMark {
  /** 1-based, as `PageView.page`. */
  page: number;
  box: Box | null;
  polygon: Polygon | null;
  ref: string | null;
  label: string;
  role: 'subject' | 'counted';
}

export interface CheckResult {
  id: string;
  rule_id: string;
  status: CheckStatus;
  subject: { kind: 'room' | 'element' | 'sheet'; ref: string | null; label: string };
  /** Null when it cannot be told: never a guess. */
  value: number | null;
  limit: number;
  unit: string;
  comparison: string;
  comparison_text: string;
  why: string;
  /** The takeoff `MarkView.id`; null for a check-only result. */
  mark_id: string | null;
  /** The takeoff `Row.key`. */
  quantity: string | null;
  /** May be empty: not located on the drawing. */
  marks: CheckMark[];
}

export interface RuleCheck {
  rule_id: string;
  title: string;
  status: CheckStatus;
  why: string;
  clause: Clause;
  results: CheckResult[];
}

export interface DrawingChecks {
  drawing_id: string;
  pack: string;
  note: string;
  status: CheckStatus;
  rules: RuleCheck[];
}

/** #142 "the same per drawing"; the wrapper is ours until record 0009 names it (shared.md Open point 18). */
export interface ProjectChecks {
  project_id: string;
  pack: string;
  note: string;
  drawings: DrawingChecks[];
}

export type IssueKind =
  | 'conflict'
  | 'refused_answer'
  | 'set_aside'
  | 'reading_flag'
  | 'code_check_failed'
  | 'double_check';
export type IssueSeverity = 'fails_rule' | 'needs_person' | 'note';
export type IssueState = 'open' | 'settled' | 'signed_off';

export interface Issue {
  /** Stable across calls. */
  id: string;
  kind: IssueKind;
  severity: IssueSeverity;
  state: IssueState;
  drawing_id: string | null;
  /** This project's path. */
  file: string;
  file_id: string;
  /** Only where a source states it (IFC storey, sheet title). */
  floor: string | null;
  page: number | null;
  /** `box != null` implies `page != null`. */
  box: Box | null;
  polygon?: Polygon | null;
  why: string;
  mark_id: string | null;
  quantity: string | null;
  question: string | null;
  reason: string | null;
  check: Record<string, unknown> | null;
  /** API paths; screens build their own `#/p/…` routes from the ids. */
  links: {
    drawing: string | null;
    takeoff: string | null;
    trace: string | null;
    checks: string | null;
  };
}

/** Ordered by severity, drawing (project order), page, box top: screens keep the order. */
export interface IssueList {
  project_id: string;
  pack: string | null;
  issues: Issue[];
}
