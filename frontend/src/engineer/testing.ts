// Derived fixtures (engineer.md "Acceptance criteria"): the backend's fixture files with named fields
// overridden, never a hand-written whole response.
import type { AnswerView, DrawingView, MarkView, Row } from '../api';
import { answer, answerArea, drawing, takeoff } from '../api/fixtures';

function must<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined) throw new Error(`fixture has no ${what}`);
  return value;
}

const conflictRow = must(takeoff.quantities[0], 'takeoff row');
const doorRow = must(answer.quantity, 'answer.quantity');
const [m1, m2] = [must(answer.marks[0], 'mark m1'), must(answer.marks[1], 'mark m2')];
const areaM2 = must(answerArea.marks[1], 'area mark m2');

/** answer.json with takeoff.json's conflict row `area:room|name=1.01` as its quantity. */
export const answerConflict: AnswerView = {
  ...answer,
  answer: 30.0,
  unit: 'm2',
  quantity: conflictRow,
  marks: conflictRow.marks,
};

/** The conflict nobody decided: no resolution, needs a person. */
export const answerNeedsPerson: AnswerView = {
  ...answerConflict,
  quantity: {
    ...conflictRow,
    needs_person: true,
    conflict: { ...must(conflictRow.conflict, 'conflict'), resolution: null },
  },
};

/** The conflict settled by a surveyor at 22.401. */
export const answerSettled: AnswerView = {
  ...answerConflict,
  answer: 22.401,
  quantity: {
    ...conflictRow,
    value: 22.401,
    settled: { value: 22.401, at: '2026-11-14T01:30:00Z' },
  },
};

const door = (patch: Partial<Row>, marks: MarkView[] = answer.marks): AnswerView => ({
  ...answer,
  answer: patch.value ?? answer.answer,
  quantity: { ...doorRow, ...patch, marks },
  marks,
});

export const answerSigned = door({
  status: 'signed',
  signed: { by: 'Ana', at: '2026-11-14T01:40:00Z', value: 2 },
});

export const answerAgree = door({
  status: 'agree',
  first: { method: 'plan_drawing', value: 2 },
  second: { method: 'ifc_model', value: 2 },
});

export const answerEstimate = door({
  status: 'estimate',
  estimate: 'scale estimated from a door width',
});

/** m2 rejected, a1 added: the door count after review. */
export const answerEdited = door({ status: 'edited', value: 1, original_value: 2 }, [
  m1,
  { ...m2, state: 'rejected', n: null },
  { ...m2, id: 'a1', n: 3, state: 'added', label: null, ref: null, polygon: null },
]);

/** answer.json whose legend says one door was counted without a mark. */
export const answerUnlocated: AnswerView = {
  ...answer,
  proof: {
    ...answer.proof,
    legend: answer.proof.legend.map((e) => ({
      ...e,
      unlocated: 1,
      note: '1 counted without a mark (second reader)',
    })),
  },
};

/** answer_area.json with the Balkon the rule left out. */
export const answerAreaExcluded: AnswerView = {
  ...answerArea,
  marks: [
    ...answerArea.marks,
    {
      ...areaM2,
      id: 'x1',
      n: null,
      state: 'excluded',
      reason: 'outdoor room',
      label: 'Balkon',
      value: 12.445,
    },
  ],
};

export const drawingHello: DrawingView = {
  ...drawing,
  reader: { ...drawing.reader, extractor: 'hello' },
  suggestions: [],
};

export const drawingNoSuggestions: DrawingView = { ...drawing, suggestions: [] };

/** answer.json whose strings carry markup, to prove they render as text. */
export const markup = '<img src=x onerror=alert(1)>';
export function answerWithMarkup(): AnswerView {
  return {
    ...answer,
    question: markup,
    quantity: { ...doorRow, label: markup },
    marks: answer.marks.map((m) => ({ ...m, label: markup })),
  };
}

export const refusalWithMarkup = (refused: AnswerView): AnswerView => ({
  ...refused,
  refusal: { ...must(refused.refusal, 'refusal'), text: markup },
});
