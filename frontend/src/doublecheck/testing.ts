// Hand-made answer.check fixtures until Bogdan's check PR brings real ones (fe-doublecheck brief).
import type { AnswerView, Row, Takeoff } from '../api';
import { answer, takeoff } from '../api/fixtures';
import type { Check, Disputed } from './types';

export const AT = '2026-11-14T13:40:00Z';
export const doubtM2: Disputed = {
  mark_id: 'm2',
  page: 1,
  box: [0.4, 0.4, 0.45, 0.45],
  why: 'only the vector reader saw it',
  readers: { pdf: 'a door', composite: 'nothing' },
};
export const doubtUnmarked: Disputed = {
  mark_id: null,
  page: 1,
  box: [0.2, 0.5, 0.23, 0.53],
  why: 'the image reader saw a door here',
  readers: { composite: 'a door', pdf: 'nothing' },
};
export const check: Check = { reason: 'Two readers disagree on door 2.', disputed: [doubtM2] };

export const withCheck = (a: AnswerView, c: Check | null): AnswerView =>
  ({ ...a, check: c }) as AnswerView;

/** answer.json asking for a double-check. */
export const asking = withCheck(answer, check);

const doorRow = (): Row => {
  const row = takeoff.quantities.find((q) => q.key === 'door');
  if (!row) throw new Error('takeoff.json has no door row');
  return row;
};
/** takeoff.json with its door row changed: what a review or sign-off POST answers. */
export function takeoffWithDoor(patch: Partial<Row>): Takeoff {
  return {
    ...takeoff,
    quantities: takeoff.quantities.map((q) => (q.key === 'door' ? { ...q, ...patch } : q)),
  };
}
export const doorMarks = () => doorRow().marks;
export const signedBy = { by: 'Ana', at: AT, value: 2 };
/** The re-asked answer after a sign-off: check gone, the row signed (Bogdan: check null once signed). */
export const reasked: AnswerView = withCheck(
  {
    ...answer,
    quantity: answer.quantity && { ...answer.quantity, status: 'signed', signed: signedBy },
  },
  null,
);
