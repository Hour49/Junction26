# Please double-check (spec, Vellum, the engineer's answer)
Status: draft, 2026-11-14 11:30, by fe-surveyor. Source: Bogdan's double-check state, board #14 c6875044070 (via
frontend-orch). API: docs/API.md `POST /api/ask`, `POST /api/drawings/{id}/review`, `POST /api/drawings/{id}/signoff`;
`answer.check` is additive, backend PR ~13:30 (mocked until then, "Pending fields (mocked)").

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
- `frontend/src/doublecheck/pending.ts`: the `answer.check` mock (below).
- `frontend/src/doublecheck/doublecheck.css`: tokens only (`--v-*`, shared.md), no colour literal (as SV-50).
- `frontend/src/doublecheck/DoubleCheck.test.tsx`, `check.test.ts`, `pending.test.ts`.

Uses, does not own: `src/api/` (postReview, postSignoff, askQuestion, getDrawing, formatValue, formatTime,
readerName, errorText), `src/viewer/PageViewer.tsx` (fe-viewer; new props below), `src/engineer/pending.ts`
`nounOf` (fe-engineer's `Row.noun` mock, reused, not copied).

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

`check = answer.check` (`{reason: string, disputed: Disputed[]} | null`), `Disputed = {mark_id?: string,
room_id?: string, why: string, readers: string[]}` (Bogdan's shape; exactly one of `mark_id` / `room_id`).

| Element | Value |
| --- | --- |
| asks at all | `check !== null` and `answer.refusal === null` and `answer.quantity !== null` and `typeof answer.answer === 'number'` |
| already checked | `answer.quantity.signed` set (status `signed`): the "checked" state, not the request |
| request sentence | "Please double-check: we're not sure about `n` of these `noun`." `n` = `disputed.length`; `noun` = `nounOf(answer)` (fe-engineer: "doors"), else "rooms" when every dispute has a `room_id`, else "marks". `n` 0: "Please double-check this value." |
| reason line | `check.reason`, as text, under the sentence |
| disputed place → mark | `mark_id` = `mark.id`; `room_id` = `mark.ref` (the area answers' room marks carry `ref` `r1`…, `answer_area.json`); a dispute matching no mark is listed with "not located on the drawing" |
| disputed list item | the mark's number (`n`) or label, `why`, and "Seen by `readerName(r)` …" joined with ", " (`readers` empty: no such line) |
| value | `formatValue(answer.answer, answer.unit)`, plus `nounOf` for counts; it changes live while fixing |
| checked line | "Checked by `signed.by`, `formatTime(signed.at)`" (the same person the card's "Verified by" names) |

## User flow and calls

All review calls carry `?project=<projectId>` (`postReview(drawingId, edit, {project: projectId})`,
`postSignoff(..., {project: projectId})`); `quantity` = `answer.quantity.key`.

1. **Needs check** (initial): the request block, with the viewer open showing `answer.marks` and the disputed marks
   highlighted, the disputed list beside it, and two buttons: **Looks right**, **Fix it**.
2. **Looks right** → **confirm** step in place: "Sign off `value` as `name`?" with the "Signing as" field
   (pre-filled from `localStorage` `countersign.surveyorName`, the surveyor workspace's key, try/catch as there),
   **Confirm** (disabled while the name is blank) and **Back**. Confirm sends, in order:
   1. `POST …/review` `{quantity, action: "settle", value: answer.quantity.value}` (Bogdan: settle + sign-off; it
      also settles a row that needs a person, so the sign-off is not refused);
   2. `POST …/signoff` `{quantity, by}`;
   3. `POST /api/ask` `{question: answer.question, drawing_id: drawingId, project_id: projectId}`, the fresh answer
      (its `quantity.signed`, `proof`, `marks`) → `onChanged(fresh)`. Shows "Checked by …".
3. **Fix it** → **fixing**: the viewer becomes editable; the disputed list grows a row per mark with **Reject** /
   **Restore** (the surveyor's `markWords` actions, `src/surveyor/words.ts`, read-only reuse), and for a count
   **Add a missed one** (the viewer's `onPick`; Esc cancels). Each edit:
   - `POST …/review` `{quantity, action: "reject" | "restore", mark}` or `{quantity, action: "add", page, box}`;
   - the response is the whole takeoff: its row `key === quantity` gives the live value and marks. The component
     shows them and calls `onChanged(patch(answer, row))` = `{...answer, answer: row.value, quantity: row, marks:
     row.marks}` (API.md: `answer` is the row's current `value`, `marks` the row's marks), so the card's value
     moves with it. No re-ask per edit (an ask may cost a model call).
   - **Done fixing** → the same confirm step as Looks right, with the new value ("Sign off 3 doors as …");
     confirm sends settle (the recounted `row.value`), sign-off, re-ask, `onChanged(fresh)`.
   - **Cancel** leaves fixing; edits already sent stay (they are saved server-side) and the line says "Your edits
     are kept; Reset in the surveyor workspace undoes them." with a link to the surveyor route `?q=<key>`.
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
| error | a POST fails | `errorText(err).detail` in `role="alert"` under the buttons, the state before the call kept; the steps already done stay done (a failed sign-off after a good settle leaves the settle; Confirm again retries from the sign-off) |
| 409 | review or signoff answers 409 | "Someone signed this off already. Undo the sign-off in the surveyor workspace to change it." + the workspace link; then a re-ask → `onChanged(fresh)`, which usually lands in "checked" |
| drawing error | `getDrawing` fails | the viewer area shows the error line with Retry; the list and buttons still work (credit only is missing) |
| re-ask error | the final ask fails | the sign-off stands: "Checked. The answer could not be refreshed: `detail`." with Retry (re-ask only) |

## Layout (Vellum)

Inside the answer card, under the value block; a block on `--v-warn-soft` with `--v-radius`-minus-8 corners
(16px), 20px padding, 16px gap (checked: `--v-ok-soft`).

- Top row: pill (12px 600, 980px radius, 5px 10px: "Please double-check" `--v-warn` on `--v-surface`; "Fixing"
  `--v-accent` on `--v-accent-soft`; "Checked by a person" `--v-ok` on `--v-surface`), then the sentence (17px
  600, `--v-text`), the reason (14px `--v-text-2`).
- 1440: two columns, viewer `minmax(0, 1fr)` left, list 320px right, 16px gap; the viewer on `--v-surface` with
  `--v-radius` corners. The list: one row per disputed place: a 28px circle with the mark number in `--v-warn`,
  the why (14px), "Seen by …" (12px `--v-muted`); hovering or focusing a row highlights its mark (`highlighted`),
  clicking selects it (`selected`), and a viewer click on a mark selects its row (`onSelect`).
- Buttons (pills, 44px, 600): Looks right / Confirm primary (`--v-accent`, white); Fix it, Done fixing, Back, Cancel,
  Reject/Restore secondary (`--v-fill`); Add a missed one secondary, pressed while picking.
- 390: one column: sentence, viewer (full width), list, buttons full width stacked; no sideways scroll; every button
  44px tall; the name field 16px text (no iOS zoom).
- Motion: press scale 0.97, none under `prefers-reduced-motion`; the live value does not animate.

## What fe-viewer adds (PageViewer, optional props)

```ts
flagged?: Record<string, string> | null; // mark id → one-line why: drawn as disputed
```

- A flagged mark is drawn with a 2px dashed `--v-warn` outline (rooms: the polygon's outline) and a "?" tag next to
  its badge, on top of its normal state look; the mark's accessible name gets ", not sure: `why`".
- The page with the first flagged mark opens first when nothing is selected (as `selected` does today).
- Nothing else: `selected`, `highlighted`, `onSelect`, `onHover`, `onPick`, `unit`, `marks` exist already. Today's
  callers pass nothing and see no change.

## Acceptance criteria

Component tests: `mockApi`, answers derived from `@fixtures` `answer.json` (door count, marks `m1`, `m2`),
`answer_area.json` (rooms, refs `r1`, `r2`), `answer_signed.json`, `answer_refused.json`; the viewer is the
props-recording double (as in SurveyorScreen.test.tsx). `check` below = `{reason: "Two readers disagree on
door m2.", disputed: [{mark_id: "m2", why: "only the vector reader saw it", readers: ["pdf"]}]}`.

- DC-1: `answer.json` with `check: null` renders nothing; so do `answer_refused.json` and a schedule answer
  (`quantity: null`).
- DC-2: with `check`, it shows "Please double-check: we're not sure about 1 of these doors.", the reason, and the
  list row "only the vector reader saw it" with "Seen by PDF vector reader".
- DC-3: the viewer gets `answer.marks`, `answer.pages` and `flagged: {m2: "only the vector reader saw it"}`; a
  `room_id: "r2"` dispute on `answer_area.json` flags the mark whose `ref` is `r2`; a dispute matching no mark is
  listed with "not located on the drawing".
- DC-4: hovering a list row sets the viewer's `highlighted` to its mark; the viewer's `onSelect("m2")` selects that
  row (`aria-current`).
- DC-5: Looks right → confirm step "Sign off 2 doors as" with the saved name; Confirm sends, in order,
  `POST /api/drawings/<did>/review?project=<pid>` `{"quantity": "door", "action": "settle", "value": 2}`,
  `POST /api/drawings/<did>/signoff?project=<pid>` `{"quantity": "door", "by": "Ana"}`, `POST /api/ask` with
  `project_id: <pid>`; then `onChanged` gets the re-asked answer, and the block shows "Checked by Ana, …".
- DC-6: Confirm is disabled while the name is blank; Back returns to the request with no request sent.
- DC-7: Fix it → Reject on `m2` sends `{"quantity": "door", "action": "reject", "mark": "m2"}` with `?project=`; the
  value shows the response row's value (1) and `onChanged` gets `answer` 1, `quantity` = that row, `marks` = its
  marks; no `POST /api/ask` yet.
- DC-8: in fixing, Add a missed one sets the viewer's `onPick`; a pick sends `{"quantity": "door", "action":
  "add", "page": 1, "box": [...]}` and the value updates; Esc unsets `onPick`; an area answer has no Add button.
- DC-9: Done fixing → confirm shows the new value; Confirm sends settle with the recounted value, sign-off, re-ask.
- DC-10: `answer_signed.json` (with or without `check`) shows "Checked by a person", "Checked by Ana, 2026-11-14
  01:40 UTC", the workspace link, and no Looks right / Fix it.
- DC-11: a 409 on settle or sign-off shows the signed-already sentence (`role="alert"`) and re-asks; `onChanged`
  gets the fresh answer.
- DC-12: a 500 on sign-off after a good settle shows the error; Confirm again sends only the sign-off and the
  re-ask (not the settle again).
- DC-13: while a request is in flight every button is disabled and "Saving…" shows.
- DC-14: file names, `why`, `reason` and reader ids render as text (an `<img onerror>` string stays text).
- DC-15: `doublecheck.css` holds no colour literal and no font other than `var(--v-font)` / the monospace stack.
- DC-16 (pending): without `check` on the answer the mock decides (below); with `check` present (also `null`) the
  real value wins; the block carries `data-pending="AnswerView.check"` only while mocked.
- DC-17 [e2e, fe-golden, 1440 and 390]: on the sample, ask "How many doors are there?" on `plans/flat-b.pdf`; with
  the mock it asks (status `single`); Fix it, reject a door, the card's value drops by 1; Done fixing, Confirm as
  "Ana": "Checked by Ana"; reset afterwards via the surveyor's Reset all edits (repeatable). No sideways scroll.

## Pending fields (mocked)

`answer.check` (Bogdan YES, PR ~13:30). `src/doublecheck/pending.ts`:
`// PENDING(AnswerView.check): mock until the backend adds it (#14)`; real field first: `'check' in answer ?
answer.check : pendingCheck(answer)`. The mock, derived from the row:

- `null` (certified) when `quantity` is null, `quantity.status` is `agree` or `signed`, or `line.sure === true`;
- otherwise `{reason, disputed}`: `reason` "Two methods read different values." (`conflict`), "Only one method
  measured this." (`single`), "Measured with an estimate: `estimate`." (`estimate`), "Changed in review." (`edited`);
  `disputed` = the row's marks in state `excluded` (`why` = "the rule left it out: `reason`", `readers` []), so a
  plain door count asks with "1 of these doors" only where the rule really did leave one out, else `n` 0
  ("Please double-check this value.").

No other field is mocked: `Row.noun` is real since PR #120 (read through fe-engineer's `nounOf`).

## Not in the API / open points (to Bogdan via orch)

1. **`room_id` → which mark field?** This spec matches `mark.ref` (`r1`…). If it is something else, say which.
2. **`readers` ids**: assumed the reader ids of `/api/info` (`pdf`, `composite`, `ifc`…), shown with `readerName`.
3. **Does `check` drop after a sign-off?** The component treats `quantity.signed` as checked whatever `check` says.
4. **One call for Looks right** (settle + sign-off is two calls, with a half-done state on failure): optional
   `"settle": true` on the sign-off body would make it atomic. Fine without.

## Out of scope

- Editing a room's outline or label, adding a mark to an area (not in v1: Add is counts only).
- Undo sign-off here (the surveyor workspace has it; the checked state links there).
- A login: "Checked by" is the typed name, as the surveyor's sign-off.
