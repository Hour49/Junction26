# Please double-check (spec, Vellum, the engineer's answer)
Status: built, 2026-11-14 12:30, by fe-surveyor (brief fe-doublecheck.md; Bogdan's answers #14 c6875117067; D73). Source: Bogdan's double-check state, board #14 c6875044070 (via
frontend-orch). API: docs/API.md `POST /api/ask`, `POST /api/drawings/{id}/review`, `POST /api/drawings/{id}/signoff`;
`answer.check` is additive, backend PR ~13:30; until then it is typed by hand in `src/doublecheck/types.ts` and read as
`check ?? null` (no mock: an answer without it asks nothing).

## Purpose

An answer the backend cannot certify (below Bogdan's 99% certificate) says so plainly and asks a person to look:
it shows what was found (the value, the marks on the drawing, the disputed places highlighted, each with a one-line
why), says "Please double-check: we're not sure about 2 of these doors", and offers **Looks right** (sign it off as
it is) or **Fix it** (add a missing mark, reject or restore wrong ones, the value updating live), then a confirm.
Afterwards the answer shows as checked by a person. A certified answer shows no request at all.

## Files owned

- `frontend/src/doublecheck/DoubleCheck.tsx`: the component (new folder, fe-surveyor).
- `frontend/src/doublecheck/check.ts`: pure parts (which answers ask, the request sentence, the disputed list, the
  patched answer after an edit); unit-tested.
- `frontend/src/doublecheck/types.ts`: `Check`, `Disputed` as Bogdan's shape, `checkOf(answer)`; `testing.ts`: hand-made
  check fixtures until his PR brings real ones.
- `frontend/src/doublecheck/doublecheck.css`: tokens only (`--v-*`, shared.md), no colour literal (as SV-50).
- `frontend/src/doublecheck/DoubleCheck.test.tsx`, `check.test.ts`, `pending.test.ts`.

Uses, does not own: `src/api/` (postReview, postSignoff, askQuestion, getDrawing, formatValue, formatTime,
readerName, errorText), `src/viewer/PageViewer.tsx` (fe-viewer; `disputed`, `fixMode`, `onAddMark`, viewer.md "Double-check"). The noun is
`answer.quantity.noun` (real since PR #120), read directly.

## Mounting (fixed signature)

fe-engineer's `AnswerCard` renders it under the value block of every answer:

```ts
export function DoubleCheck(props: {
  answer: AnswerView;
  projectId: string;
  drawingId: string;
  onChanged: (answer: AnswerView) => void; // the card replaces its answer with this one
}): JSX.Element | null;
```

It renders `null` when there is nothing to ask (certified, refused, no takeoff row): AnswerCard needs no check of
its own. It owns its own `PageViewer` (the card's plan cannot take the highlights or the picks through this
signature); it reads the drawing's `credit` with `getDrawing(drawingId, {project})` when it opens.

## Data

`check = answer.check` (`{reason: string, disputed: Disputed[]} | null`), `Disputed = {mark_id: string | null, page:
number, box: number[], why: string, readers: Record<string, string>}` (Bogdan, #14 c6875117067; `readers` is an object
since c6875279504: reader id → one plain sentence of what that reader says here, e.g. `{"answer": "a door",
"detector-m": "nothing"}`; at most 5 places per answer, strongest first, server order kept). `mark_id` is a `MarkView.id` (room
marks too: the room id is in `MarkView.ref`); `mark_id: null` is a place a reader saw that the answer did not count
(page + box): Fix it offers "Add it here". Once the quantity is signed off `check` is null and the answer carries the
sign-off.

| Element | Value |
| --- | --- |
| asks at all | `check !== null` and `answer.refusal === null` and `answer.quantity !== null` and `typeof answer.answer === 'number'` |
| already checked | `answer.quantity.signed` set (status `signed`): the "checked" state, not the request |
| request sentence | "Please double-check: we're not sure about `n` of these `noun`." `n` = `disputed.length`; `noun` = `quantity.noun`, else "rooms" for an area, else "places". `n` 0: "Please double-check this value." |
| reason line | `check.reason`, as text, under the sentence |
| disputed place | `mark_id` → the mark with that `id`: "Mark `n`"; `mark_id` null → "Not counted, page `p`"; an id matching no mark → "Not located on the drawing". To the viewer as `{markId, page, why}` or `{page, box, why}` (camelCase, viewer.md) |
| disputed list item | the mark's number (`n`) or label, `why` (one sentence), then one line per reader `readerName(id)`: `sentence` (`.dc-reader`), in the object's order |
| value | `formatValue(answer.answer, answer.unit)` + `quantity.noun` for counts ("1 door": a trailing s dropped for 1); live while fixing ("Value now:") |
| checked line | "Checked by `signed.by`, `formatTime(signed.at)`" (the same person the card's "Verified by" names) |

## User flow and calls

All review calls carry `?project=<projectId>` (`postReview(drawingId, edit, {project: projectId})`,
`postSignoff(..., {project: projectId})`); `quantity` = `answer.quantity.key`.

1. **Needs check** (initial): the request block, with the viewer open showing `answer.marks` and the disputed marks
   highlighted, the disputed list beside it, and two buttons: **Looks right**, **Fix it**.
2. **Looks right** → **confirm** step in place: "Sign off `value` as" with the "Signing as" field (pre-filled from
   `localStorage` `countersign.surveyorName`, the surveyor workspace's key, try/catch as there), **Confirm**
   (disabled while the name is blank) and **Back**. Confirm sends **one** call, `POST …/signoff`
   `{quantity, by, settle: true}` (#121: settles the current value and signs it off), shows the row from its
   takeoff at once (`onChanged(patch)`, "Checked by …"), then `POST /api/ask` `{question, drawing_id, project_id}` →
   `onChanged(fresh)`.
3. **Fix it** → **fixing**: the pill reads "Fixing"; the viewer gets `fixMode` and `onAddMark` (counts only); each
   listed mark gets **Reject `mark n`** / **Restore `mark n`** (by its state), each uncounted place **Add it here: page
   `p`**, and the panel **Add one** (keyboard path, D73: adds at the first uncounted place; shown only when there is
   one, since `add` needs a page and a box). Each edit:
   - `POST …/review` `{quantity, action: "reject" | "restore", mark}` or `{quantity, action: "add", page, box}`;
   - the response is the whole takeoff: its row `key === quantity` gives the live value and marks:
     `onChanged(patch(answer, row))` = `{...answer, answer: row.value, quantity: row, marks: row.marks}`
     (API.md: `answer` is the row's current `value`). No re-ask per edit.
   - **Done fixing** → the same confirm with the new value ("Sign off 1 door as"); one sign-off with `settle: true`.
   - **Cancel** leaves fixing; edits already sent stay and the line says "Your edits are kept; Reset in the surveyor
     workspace undoes them." with the surveyor workspace link (`?q=<key>`).
4. **Checked** (`quantity.signed` set, now or on load): no buttons; "Checked by Ana, 2026-11-14 13:40 UTC" with an
   ok pill "Checked by a person", and the link "Open in the surveyor workspace" (undo lives there).
5. **Certified** (`check === null`): renders nothing.

One request at a time: every button is disabled while one is in flight ("Saving…", `role="status"`).

## States

| State | When | Shows |
| --- | --- | --- |
| hidden | certified, refusal, no row, string answer | nothing (`null`) |
| needs check | `check` set, not signed | warn pill "Please double-check", sentence, reason, viewer + disputed list, Looks right / Fix it |
| fixing | after Fix it | accent pill "Fixing", editable list, Add a missed one (counts), live value, Done fixing / Cancel |
| confirming | after Looks right / Done fixing | "Sign off `value` as" + name field, Confirm / Back |
| saving | a request in flight | "Saving…", all buttons disabled |
| checked | `quantity.signed` | ok pill "Checked by a person", "Checked by `by`, `at`", workspace link |
| error | a POST fails | `errorText(err).detail` in `role="alert"` under the buttons, the state before the call kept; Confirm again resends the one sign-off |
| 409 | review or signoff answers 409 | "Someone signed this off already. Undo the sign-off in the surveyor workspace to change it." + the workspace link; then a re-ask → `onChanged(fresh)`, which usually lands in "checked" |
| drawing error | `getDrawing` fails | the viewer area shows the error line with Retry; the list and buttons still work (credit only is missing) |
| re-ask error | the final ask fails | the sign-off stands: "Checked. The answer could not be refreshed: `detail`." with Retry (re-ask only) |

## Layout (Vellum)

Inside the answer card, under the value block; a block on `--v-warn-soft` with `--v-radius`-minus-8 corners
(16px), 20px padding, 16px gap (checked: `--v-ok-soft`).

- Top row: pill (12px 600, 980px radius, 5px 10px: "Please double-check" `--v-warn` on `--v-surface`; "Fixing"
  `--v-accent` on `--v-accent-soft`; "Checked by a person" `--v-ok` on `--v-surface`), then the sentence (17px
  600, `--v-text`), the reason (14px `--v-text-2`).
- The layout follows the panel's own width (`.dc` is an inline-size container), not the window's. In the answer
  card the panel sits in the side column (~330px inside at 1440): one column, the list full width, the panel's own
  viewer hidden (the card's plan beside or above it shows the marks; Reject/Restore/Add it here stay in the list);
  nothing overflows and an answer with no places is just the sentence, reason and buttons (Bogdan's live test,
  #14 c6876826283). From 680px inside: two columns, viewer `minmax(0, 1fr)` left, list 320px right, 16px gap; the
  viewer on `--v-surface` with `--v-radius` corners. The list: one row per disputed place: a 28px circle with the mark number in `--v-warn`,
  the why (14px), one line per reader "`reader`: `sentence`" (12px `--v-muted`); hovering or focusing a row highlights its mark (`highlighted`),
  clicking selects it (`selected`), and a viewer click on a mark selects its row (`onSelect`).
- Buttons (pills, 44px, 600): Looks right / Confirm primary (`--v-accent`, white); Fix it, Done fixing, Back, Cancel,
  Reject/Restore secondary (`--v-fill`); Add a missed one secondary, pressed while picking.
- 390: one column: sentence, list, buttons full width stacked; no sideways scroll; every button
  44px tall; the name field 16px text (no iOS zoom).
- Motion: press scale 0.97, none under `prefers-reduced-motion`; the live value does not animate.

## What fe-viewer adds

Built by fe-viewer (VW-60..69, viewer.md "Double-check"): `disputed?: {markId?, box?, page?, why}[]`, `fixMode?`,
`onAddMark?(box, page)`. This panel passes `toViewer(check.disputed)`, `fixMode` while fixing a count, and
`onAddMark` while fixing and idle.

## Acceptance criteria

Component tests: `mockApi`, answers derived from `@fixtures` `answer.json` (door count, marks `m1`, `m2`),
`answer_area.json` (rooms, refs `r1`, `r2`), `answer_signed.json`, `answer_refused.json`; the viewer is the
props-recording double (as in SurveyorScreen.test.tsx). `check` below = `{reason: "Two readers disagree on
door m2.", disputed: [{mark_id: "m2", why: "only the vector reader saw it", readers: {pdf: "a door", composite: "nothing"}}]}`.

- DC-1: renders nothing for `answer.json` without `check`, with `check: null`, for `answer_refused.json` and for a
  schedule answer (`quantity: null`).
- DC-2: with `check` it shows the pill "Please double-check", "Please double-check: we're not sure about 1 of these
  doors.", the reason, and the list row "Mark 2" with its why and the lines "PDF vector reader: a door", "image reader: nothing" in that order.
- DC-3: the viewer gets `answer.marks`, `answer.pages`, the drawing's `credit` and `disputed: [{markId: "m2", page: 1,
  why}, {page: 1, box, why}]`; the uncounted place is listed "Not counted, page 1"; no fix mode yet.
- DC-4: hovering a row sets `highlighted` to its mark; the viewer's `onSelect("m2")` marks that row `aria-current`.
- DC-5: Looks right → "Sign off 2 doors as" with the saved name; Confirm sends `POST …/signoff?project=<pid>`
  `{"quantity": "door", "by": "Ana", "settle": true}`, then `POST /api/ask` `{question, drawing_id, project_id}`
  (two POSTs in all); `onChanged` last gets the re-asked answer; "Checked by a person", "Checked by Ana, …".
- DC-6: Confirm is disabled while the name is blank; Back returns with nothing sent.
- DC-7: Fix it → "Reject mark 2" sends `{"quantity": "door", "action": "reject", "mark": "m2"}` with `?project=`;
  "Value now: 1 door"; `onChanged` gets answer 1 with the row's marks; no ask; the button turns "Restore mark 2".
- DC-8: in fixing, `fixMode` is true; `onAddMark(box, 1)` sends `add` with that page and box; "Add it here: page 1"
  sends `add` with the uncounted place's box; an area answer gets no fix mode, no `onAddMark`, no Add buttons.
- DC-9: Done fixing → "Sign off 1 door as"; Confirm: review, signoff, ask, in that order.
- DC-10: a signed answer shows "Checked by a person", "Checked by Ana, 2026-11-14 13:40 UTC", the surveyor link
  `#/p/<pid>/d/<did>/surveyor?q=door`, no Looks right / Fix it.
- DC-11: a 409 on the sign-off shows "Someone signed this off already. Undo the sign-off in the surveyor workspace to
  change it." and re-asks (`onChanged` gets the fresh answer).
- DC-12: a 500 on the sign-off shows its detail; Confirm again resends it.
- DC-13: while a request is in flight every button is disabled and "Saving…" shows.
- DC-14: `why`, `reason` and reader ids render as text.
- DC-15: `doublecheck.css` holds no colour literal and no font other than `var(--v-font)` / the monospace stack.
- DC-16: Cancel after an edit shows the kept line and the workspace link; Looks right is back.
- DC-17: a drawing (credit) error shows a line with Retry; the panel still works; Retry fetches again.
- DC-19: `doublecheck.css`: `.dc` is an inline-size container; below `@container (min-width: 680px)` the body is one
  column and `.dc-plan` is hidden; the 320px list column exists only inside that query.
- DC-18 [e2e, fe-golden, 1440 and 390, after Bogdan's check PR]: an answer with `check` on the sample: Fix it, reject
  a door, the card's value drops by 1; Done fixing, Confirm as "Ana": "Checked by Ana". No sideways scroll.

## Pending fields

None mocked (brief fe-doublecheck.md): `answer.check` is typed by hand and read as `check ?? null`; tests use the
hand-made fixtures in `src/doublecheck/testing.ts` until Bogdan's PR brings real ones. `Row.noun` is real.

## Open points

1. Answered by Bogdan (#14 c6875117067): room marks by `MarkView.id` (room id in `ref`), `readers` keys = /api/info ids (values: what each says, c6875279504),
   `check` null once signed, `settle: true` on sign-off (built on it).
2. "Add one" without an uncounted place has no position to send (`add` needs page + box), so it is not shown then;
   the mouse/touch path is the viewer's fix mode.

## Out of scope

- Editing a room's outline or label, adding a mark to an area (not in v1: Add is counts only).
- Undo sign-off here (the surveyor workspace has it; the checked state links there).
- A login: "Checked by" is the typed name, as the surveyor's sign-off.
