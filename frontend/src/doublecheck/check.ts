// The double-check panel's pure parts (docs/specs/frontend/double-check.md "Data").
import type { AnswerView, Row } from '../api';
import type { PageViewerProps } from '../viewer/PageViewer';
import { checkOf, type Check, type Disputed } from './types';

export type PanelState = 'hidden' | 'needs' | 'checked';

/** hidden: certified, refused, no takeoff row or not a number; checked: signed off; else needs a person. */
export function stateOf(a: AnswerView): PanelState {
  if (a.refusal !== null || a.quantity === null || typeof a.answer !== 'number') return 'hidden';
  if (a.quantity.signed) return 'checked';
  return checkOf(a) ? 'needs' : 'hidden';
}

export function requestLine(a: AnswerView, check: Check): string {
  const n = check.disputed.length;
  if (n === 0) return 'Please double-check this value.';
  const row = a.quantity;
  const noun = row?.noun ?? (row?.measure === 'area' ? 'rooms' : 'places');
  return `Please double-check: we're not sure about ${String(n)} of these ${noun}.`;
}

type ViewerItem = NonNullable<PageViewerProps['disputed']>[number];

/** Bogdan's disputed list as the viewer's `disputed` prop (viewer.md "Double-check"). */
export const toViewer = (items: Disputed[]): ViewerItem[] =>
  items.map((d) =>
    d.mark_id === null
      ? { page: d.page, box: d.box, why: d.why }
      : { markId: d.mark_id, page: d.page, why: d.why },
  );

/** The answer after a review edit: API.md says `answer` is the row's value and `marks` its marks. */
export const patch = (a: AnswerView, row: Row): AnswerView => ({
  ...a,
  answer: row.value,
  quantity: row,
  marks: row.marks,
});
