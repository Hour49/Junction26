// answer.check as Bogdan specified it (board #14 c6875117067, readers as an object: c6875279504); not in schema.d.ts until his check PR (~13:30).
import type { AnswerView } from '../api';

export interface Disputed {
  mark_id: string | null; // null: a place a reader saw that the answer did not count
  page: number;
  box: number[];
  why: string;
  readers: Record<string, string>; // reader id (/api/info) → what that reader says here, strongest first
}

export interface Check {
  reason: string;
  disputed: Disputed[];
}

/** The answer's check, typed by hand until the generated types have it. */
export const checkOf = (a: AnswerView): Check | null =>
  (a as AnswerView & { check?: Check | null }).check ?? null;
