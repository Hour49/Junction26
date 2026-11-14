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

/** The page was flagged as a whole at upload (a photo, a scan, a big sheet a model counted): API.md level basis `page`. */
export const pageFlagged = (a: AnswerView): boolean => a.level?.basis === 'page';

export function requestLine(a: AnswerView, check: Check): string {
  const row = a.quantity;
  const noun = row?.noun ?? (row?.measure === 'area' ? 'rooms' : 'places');
  // the whole page is in doubt, not N of its items (Bogdan #14 c6880945211, DC-20)
  if (pageFlagged(a))
    return `Please double-check the whole page: it was flagged when it was read, so every one of these ${noun} is in doubt.`;
  const n = check.disputed.length;
  if (n === 0) return 'Please double-check this value.';
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
