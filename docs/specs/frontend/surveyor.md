# Surveyor workspace (spec, frontend v1)
Status: draft, 2026-11-14, by fe-spec-surveyor.  Story: #33.  API: docs/API.md (v1).

## Purpose

The surveyor checks one drawing's takeoff before anyone builds on it. They see every quantity with its value, both
methods' readings and its review state, the review queue first. They fix what the drawing model got wrong (reject,
restore or add marks, leave rooms out of an area, settle a conflict), sign off each value and export the takeoff
as CSV. Signed values are what the engineer later sees as verified.

## Files owned

The build worker creates these and nothing else (tests sit next to the file they test):

- `frontend/src/surveyor/SurveyorScreen.tsx`: `SurveyorScreen({projectId, drawingId, query})`, the route
  component for `#/p/<project_id>/d/<drawing_id>/surveyor`. The shell mounts it with key = the route path without
  the query, so a new `?q=` re-renders it without a remount and the selection follows `query.get("q")`. It loads
  the data, holds the takeoff state, the selected quantity, the zeros toggle and the add-mode flag, and
  sends the edits.
- `frontend/src/surveyor/TakeoffTable.tsx`: the table, grouped into "To review" and "All other quantities".
- `frontend/src/surveyor/QuantityDetail.tsx`: the selected quantity: values, methods, conflict, settle, rule,
  sign-off, reset.
- `frontend/src/surveyor/MarkList.tsx`: the marks of the selected quantity, each with its action.
- `frontend/src/surveyor/ProjectReviewSide.tsx`: the side panel with the project's drawings and conflicts.
- `frontend/src/surveyor/words.ts`: the status words and mark-row words below (pure functions, unit-tested).
  Values and times come from shared.md's `formatValue` and `formatTime` in `frontend/src/api/format.ts`.
- `frontend/src/surveyor/*.test.ts(x)`: unit and component tests.

The [e2e] criteria below are built by the e2e worker (golden-path.md), not by this spec's build worker.

It uses, and does not own, the API client (`frontend/src/api/`), the shell's router, banner, loading and error
views (`frontend/src/shell/`) and the page viewer (`frontend/src/viewer/`).

## User flow

1. The surveyor opens `#/p/<project_id>/d/<drawing_id>/surveyor`: from the shell's role switch, from a drawing in
   the side panel, from a project conflict, or from the engineer's "Send to surveyor" with `?q=<key>` in the
   hash (shared.md's router: `query`, built by `routeHref`, which encodes the key).
2. The screen shows a loading state, then three parts: the side panel (the project's drawings with what is left to
   review, and the project's conflicts), the viewer (the drawing's page with the selected quantity's marks), and
   the takeoff panel (progress "k of n quantities signed off", Export CSV, the table, the detail of the selected
   quantity).
3. The selected quantity is the `?q=` key when it is a row of the takeoff; else the first key of `review_queue`
   that is a row; else the first row. Selecting another row (click, tap, or Enter on the focused row) shows its
   detail and marks, and replaces `?q=` in the hash without adding a history entry.
4. In the detail the surveyor reads the value, the value at ingest when it differs, both methods' readings, the
   conflict with every method's value and the rule that kept one, the estimate note, and the counting rule.
5. They fix marks in the mark list: Reject / Restore a mark of a count, Leave out / Include a room of an area,
   Remove a mark they added, Count in a mark the rule left out. Hovering or focusing a mark row highlights that
   mark in the viewer; selecting a mark in the viewer scrolls to and focuses its row. Each action sends one
   `review` edit; the screen shows "Saving…", then replaces the whole takeoff with the response.
6. On a count they press "Add a missed one" and click the missed item on the page; the viewer reports the page
   and a small square box around the point (viewer.md `onPick`), and the screen sends an `add` edit with them.
   Escape or pressing the button again leaves add mode without a request.
7. On a conflict they keep one method's value ("Keep B: 30.00 m² (<methodName('printed_label')>)") or type another value and press
   "Settle"; both send a `settle` edit.
8. "Reset this quantity" undoes every edit of the quantity; "Reset all edits" (after a confirm) undoes every edit
   and sign-off of the drawing.
9. They type their name once in "Signing as" (kept in this browser) and press "Sign off 2"; the row shows as signed
   off by them, with the time, and every edit control of it is disabled until they press "Undo sign-off".
10. "Export CSV" downloads `<file stem>-takeoff.csv` from the server.
11. "Show rows with value 0" reloads the takeoff with `zeros=true`; every later request of the screen carries the
    same `zeros`.

## API calls

Client functions (shared.md): `getTakeoff`, `getDrawing`, `getProjectReview`, `postReview`, `postSignoff`,
`takeoffCsvUrl`; each takes `{zeros}` where the path has `?zeros=`. Every takeoff, review, sign-off and CSV
request also carries `project: projectId` (`?project=<project_id>`, QA R1-4-4): the takeoff's `file` and the
CSV's `drawing` column are then this project's name of the drawing, not another upload's.

| Call (API.md section) | When | Fields read, and what each drives | Fixture |
| --- | --- | --- | --- |
| `GET /api/drawings/{drawing_id}/takeoff?project=<project_id>&zeros=` ("Takeoff and review") | On route entry, on the zeros toggle, on Retry | `file` is not shown (it is the name the drawing was last stored under, not this project's; the title uses the drawing's `file`). `quantities[]`: the table rows, in this order. `review_queue`: the "To review" group, in its order. Per row: `key` (selection, `?q=`, every edit), `label` (row and detail name), `measure` (count vs area wording), `value` + `unit` (shown value), `original_value` (struck-through ingest value when different), `status` (status words), `needs_person` ("needs you", sign-off blocked), `rule.text`/`rule.id`, `estimate`, `first`/`second` (both methods), `conflict.values[]` (value, unit, method, page, box), `conflict.resolution` (rule, value), `conflict.note`, `conflict.derived`, `settled` (value, at), `marks[]` (`id`, `n`, `page`, `box`, `polygon`, `state`, `value`, `label`, `ref` not shown, `reason`), `signed` (by, at, value), `unlocated` | `takeoff.json` |
| `GET /api/drawings/{drawing_id}?project=<project_id>` ("Drawings"), `getDrawing(drawingId, {project: projectId})` | On route entry, with the takeoff | `file` (as this project uploaded it: the panel title and the viewer caption; a drawing is shared by content across projects, QA R1-3-6/R1-4-4); `pages[]` and `credit` go to the viewer; `reader.extractor` (`hello` explains an empty takeoff) | `drawing.json` |
| `GET /api/projects/{project_id}/review` ("GET …/review") | On route entry, and again after every successful edit or sign-off | `drawings[]`: `drawing_id` (link, current highlighted), `file`, `to_review`, `signed`, `quantities`. `conflicts[]`: `drawing_id`, `file`, `quantity` (link `?q=`), `label`, `conflict.values[].value` + `unit`, `settled`, `needs_person` | `project_review.json` |
| `POST /api/drawings/{drawing_id}/review?project=<project_id>&zeros=` ("POST …/review") | Each mark action, add, settle, reset of one quantity, reset of all | Body is exactly one of the `review_requests.json` shapes. The response is a whole takeoff: it replaces the screen's takeoff | request `review_requests.json`, response `takeoff.json` |
| `POST /api/drawings/{drawing_id}/signoff?project=<project_id>&zeros=` ("POST …/signoff") | Sign off; undo sign-off | Body `{quantity, by}` (`signoff_request.json`), undo `{quantity, by, undo: true}`. Response replaces the takeoff | `signoff_request.json`, `takeoff.json` |
| `GET /api/drawings/{drawing_id}/takeoff.csv?project=<project_id>&zeros=` ("GET …/takeoff.csv") | "Export CSV" | Not fetched by script: a plain link with `download`; the server's `Content-Disposition` names the file | none (CSV in API.md) |
| `GET /api/drawings/{drawing_id}/pages/{n}.png` | By the viewer | the page image | none |

Request bodies per action (key `K`, mark `M`):

| Action on screen | Body |
| --- | --- |
| Reject (count) / Leave out (area) / Remove (an added mark) | `{"quantity": K, "action": "reject", "mark": M}` |
| Restore (count) / Include (area) / Count in (an excluded mark) | `{"quantity": K, "action": "restore", "mark": M}` |
| Add a missed one | `{"quantity": K, "action": "add", "page": <page>, "box": [x0, y0, x1, y1]}` |
| Keep a conflict value / Settle a typed value | `{"quantity": K, "action": "settle", "value": <number>}` |
| Reset this quantity | `{"quantity": K, "action": "reset"}` |
| Reset all edits | `{"action": "reset"}` |
| Sign off / Undo sign-off | `{"quantity": K, "by": <name>}` / `{"quantity": K, "by": <name>, "undo": true}` |

Display rules from `words.ts`:

| `status` | Words in the table and the detail (with the text, never colour alone) |
| --- | --- |
| `signed` | "Verified" |
| `conflict` | "Methods disagree"; with `needs_person: true` also "needs you" |
| `estimate` | "Estimate" |
| `edited` | "Changed in review" |
| `agree` | "Two methods agree" |
| `single` | "One method" |

These are engineer.md's words (EN-31), so a status reads the same on both screens. Measuring methods (`first.method`,
`second.method`, `conflict.values[].method`, backend `MeasureMethod`) show as `methodName(id)` from
`frontend/src/api/format.ts` (shared), never as the raw id (`polygon_x_scale`; QA R3), as reader ids do. Values use shared.md's
`formatValue(value, unit)`: a count (or a null unit) as an integer with no unit after it (the label says "count"),
other units with exactly 2 decimals and `m`, `m²`, `m³` (`59.868` m2 → "59.87 m²", `30` → "30.00 m²"). Times
(`signed.at`, `settled.at`) use `formatTime`: `YYYY-MM-DD HH:MM UTC`. The screen never computes a total itself; it shows the API's `value`.

Mark rows, by `state`:

| `state` | Number shown | Words | Action (count / area) |
| --- | --- | --- | --- |
| `counted`, `reason` null | `n` | the `label`; on an area also its `value` ("30.00 m²", or "area unknown" when null) | Reject / Leave out |
| `counted`, `reason` set | `n` | `label`, "counted in by a surveyor; the rule had: `reason`" | Reject / Leave out |
| `rejected` | "×" | `label`, "rejected by a surveyor" (area: "left out by a surveyor") | Restore / Include |
| `added` | "+`n`" | "added by a surveyor" (`label` is null) | Remove |
| `excluded` | "–" | `label`, "left out by the rule: `reason`" | Count in / Include |

## States

| State | What the screen shows | How to reach it on purpose |
| --- | --- | --- |
| Loading | The shell's `Loading` ("Loading the takeoff…") in the viewer and panel areas until both the drawing and the takeoff have answered; the side panel has its own "Loading drawings…" | A delayed mock in a component test; a throttled network in the browser |
| Ready | Side panel, viewer, takeoff panel as in Layout | `takeoff.json` + `drawing.json` + `project_review.json` |
| Empty | No rows: "Nothing was counted on this drawing." When `reader.extractor` is `hello`: "This drawing's route has no reader in this build, so nothing was counted." When `zeros` is false: also the "Show rows with value 0" control. No sign-off, no CSV link, no reset-all | `takeoff.json` with `quantities: []`, `review_queue: []`; the sample's `scans/` or `photos/` drawing (0 quantities in `project_review.json`) |
| Nothing to review | The "To review" group says "Nothing left to review." | `takeoff.json` with `review_queue: []` |
| Load error | The shell's `ErrorView` with `detail`, `code` and Retry, which repeats the failed loads (on a 404 `ErrorView` shows "Back to projects" to `#/` instead of Retry) | Mock a 404 `error.json` for the takeoff; an unknown drawing id against the backend |
| Side-panel error | Only the side panel shows `detail`, `code` and Retry; the takeoff still works | Mock a 500 for `GET …/review` |
| Saving | "Saving…" in a live region; every edit, settle, sign-off and reset control disabled; the table stays readable | Any edit with a delayed response |
| Edit refused | An alert in the detail with `detail` and `code` (409 `not-allowed`, 422 `invalid`, 422 `validation`, 404 `not-found`); the takeoff stays as it was; the alert clears on the next successful request | Mock 409/422 bodies shaped as `error.json` |
| Needs a person | Row words "Methods disagree · needs you"; the detail says "No rule decides. Settle a value before signing off."; Sign off disabled | `takeoff.json` row 1 with `needs_person: true` and `conflict.resolution: null` |
| Signed | Row words "Verified"; detail "Signed off by `by`, `at`: `value`. Engineers see this value as verified."; every edit, settle and add control disabled with "Undo the sign-off to edit."; "Undo sign-off" shown | Sign off in the app; or the `door` row of `takeoff.json` with `status: "signed"`, `signed: {"by": "Ana", "at": "2026-11-14T01:40:00Z", "value": 2}` |
| Add mode | The button reads "Click the missed item on the drawing… (Esc to cancel)"; the viewer gets `onPick` (crosshair) | Press "Add a missed one" on a count |
| No keys | The shell's "running offline" banner (shared spec); nothing else changes here | `info.json` (`no_keys: true`) |

There is no refusal on this screen: a takeoff has no refusal object. A file set aside at ingest has no drawing, so
it never reaches this route.

## Layout

The mock's surveyor screen (`demo/` `#work/surveyor/B`) is the model: the same three parts, built from the API.

Desktop 1440x900: three columns. Left, 240px: the side panel, with "Drawings (5)" (each: `file`, "2 to review",
"0 of 63 signed off" or "nothing counted", current one marked "current" and highlighted) and below it "Conflicts
(n)" (each: `label`, `file`, the values "22.40 m² vs 30.00 m²", and "needs you" / "decided by rule" / "settled").
Middle, the rest: `PageViewer` (viewer.md) with the selected row's marks, conflict tags and unlocated line, page
at most the viewport height. Right, 420px:
the takeoff panel, which scrolls as one column (sticky, at most the viewport height, its own vertical scroll): a
sticky header with the title "Takeoff: `file`", "Export CSV", "Show rows with value 0", "Reset all edits" and the
progress "k of n quantities signed off" (text and bar); under it both tables (Quantity, Value, State) in the
column's flow, with no scroll box of their own, then the detail of the selected row. The page does not scroll
sideways (QA R1-4-2: one inner box for both tables showed one row of 61).

Phone 390x844: one column, in this order: the side panel collapsed behind "Drawings and conflicts" (a `<details>`),
the viewer (at most 50% of the viewport height), the takeoff panel in the page's flow (no column scroll, no
sticky header, no scroll box around the tables). The table keeps its three columns and wraps labels. Buttons and table rows are at least 40px tall. Nothing scrolls sideways.

Table cell content: Quantity = `label`, and under it in small text when `first` and `second` are set:
"<methodName(first.method)> `first.value` · <methodName(second.method)> `second.value`". Value = the original value struck through when it
differs, then `value` and unit. State = the status words.

Detail, top to bottom: `label` with the status words; the value large with unit and "was `original_value` at
ingest" when it differs; both methods; the conflict block (each value lettered A, B… in `conflict.values`
order, the same letters the viewer tags the page with, with value, unit and method; the resolution "Kept by rule: `resolution.rule` → `resolution.value`" or the
needs-a-person text, `note`, `derived`), Keep buttons and the Settle field; "Settled at `settled.value`
(`settled.at`). A mark edit clears it."; the estimate note "Estimate: `estimate`"; "Counting rule: `rule.text`";
the mark list; the tools: Add a missed one (counts only), Reset this quantity, Signing as,
Sign off / Undo sign-off.

## Acceptance criteria

Fixture names are `backend/tests/fixtures/api_v1/<name>`, imported through `src/api/fixtures.ts`; requests are
answered and recorded by `mockApi` (shared.md). "Derived" means a copy of that fixture with the named fields
changed in the test, never a hand-written response. The viewer is a test double in component tests that records
its props and can call `onSelect`, `onHover` and `onPick`.

Loading and routing

- SV-1: On entry the screen sends `GET /api/drawings/{id}/takeoff` (no `zeros` or `zeros=false`),
  `GET /api/drawings/{id}` and `GET /api/projects/{project_id}/review`, and shows the loading view until the first
  two answer. [component] (delayed mocks)
- SV-2: With `takeoff.json`, the table shows exactly the rows of `quantities` (3), each `label` once. [component]
- SV-3: The "To review" group lists the `review_queue` keys that are rows, in `review_queue` order; a queue key with
  no row (`area:room|name=küche` in `takeoff.json`) is ignored, with no error. "All other quantities" lists the
  rest in `quantities` order. [component] `takeoff.json`
- SV-4: With no `?q=`, the first `review_queue` key that is a row (`area:room|name=1.01`) is selected; with
  `?q=door` (encoded) `door` is selected; with `?q=` naming no row, the same default as without it. [component]
- SV-5: Selecting a row replaces the hash's `?q=` with the encoded key and adds no history entry
  (`history.length` unchanged). [component]
- SV-6: A row is selectable with the keyboard: Tab to it, Enter selects it. [component]

Table and detail

- SV-7: Each row's State cell shows the words of the status table for its `status` (`takeoff.json`: "Methods
  disagree", "One method", "One method"); derived rows give "Verified", "Estimate", "Changed in review", "Two
  methods agree". [unit] `words.ts` + [component]
- SV-8: A row with `needs_person: true` shows "needs you" in its State cell and in the detail. [component] derived
  `takeoff.json` row 1: `needs_person: true`, `conflict.resolution: null`
- SV-9: Values: `door` shows "2" with no unit; `area:room|indoor` shows "59.87 m²", not a sum of its marks' values
  (30 + 2.489 = 32.49). [component] `takeoff.json`
- SV-10: When `value` differs from `original_value`, the Value cell and the detail show the original struck through
  (an `<s>` element) and "was … at ingest"; when equal, neither appears. [component] derived `door`: `value: 3`
- SV-11: For a row with `first` and `second`, the table shows both methods and values
  (`methodName` of each id, e.g. "<methodName('polygon_x_scale')> 22.40 m² · <methodName('printed_label')> 30.00 m²")
  and the detail shows them too; a row with both null shows neither; the raw ids never show (QA R3). [component]
  [component] `takeoff.json`
- SV-12: The conflict block lists each `conflict.values[]` entry as "A: 22.40 m² <methodName('polygon_x_scale')>",
  "B: 30.00 m² <methodName('printed_label')>", and the resolution "Kept by rule: the printed label over the outline at the sheet's scale →
  30.00 m²"; with `resolution: null` it shows
  "No rule decides. Settle a value before signing off." [component] `takeoff.json`, derived
- SV-13: The viewer receives the selected row's `conflict` (null for `door`) and `unit`, so it tags each reading
  A, B on the page. [component] `takeoff.json`
- SV-14: A non-null `estimate` shows "Estimate: <estimate>"; `conflict.note` and `conflict.derived`, when set,
  show as text. [component] derived
- SV-15: The detail shows `rule.text` under "Counting rule". [component] `takeoff.json`
- SV-16: Progress reads "k of n quantities signed off", k = rows with `status: "signed"`, n = rows; `takeoff.json`
  gives "0 of 3". [component]

Marks

- SV-17: The mark list shows one row per `marks[]` entry in order, with the number and words of the mark table;
  `door` shows "1" and "2"; area rows show each room's `label` and its `value` in m² (Küche 30.00 m², Reduit
  2.49 m²). [component] `takeoff.json`
- SV-18: Rejected marks show "×", excluded marks "–" and the `reason`, an added mark with `n: 3` shows "+3"; a counted mark with a `reason` shows
  "counted in by a surveyor". [component] derived marks
- SV-19: `PageViewer` receives `file`, `pages` and `credit` from `drawing.json` and the selected row's `marks`,
  `unit`, `unlocated` and `conflict`; selecting another row changes the row props. [component]
- SV-20: Hovering or focusing a mark row passes its id as `highlighted`; the viewer's `onHover(id)` highlights the
  mark row; `onSelect("m2")` passes `selected="m2"` back and scrolls to and focuses that mark row; `onSelect(null)`
  clears it. [component]
- SV-21: "Reject" on `door` mark `m2` sends `POST /api/drawings/{id}/review` with body
  `{"quantity":"door","action":"reject","mark":"m2"}` (equal to `review_requests.json[0]`); "Restore" on a rejected
  mark sends `review_requests.json[1]`. [component]
- SV-22: On an area row the actions read "Leave out" / "Include" and send `reject` / `restore`; on an `added` mark
  "Remove" sends `reject`; on an `excluded` mark the action sends `restore`. [component] `takeoff.json`, derived
- SV-23: An area row with a mark whose `value` is null shows "A room's area is unknown, so leaving rooms out does
  not change the total; settle a value instead." [component] derived
- SV-24: The row's `unlocated` goes to the viewer, which writes its legend line (viewer.md); the mark list adds,
  under its rows, "+ N `class` counted with no mark" for each entry, so the list's count matches the value.
  [component] derived `door`: `unlocated: {"door": 1}`

Edits

- SV-25: After any successful edit, the table, detail, progress and marks show the response's takeoff (a derived
  takeoff where `door` has `value: 1`, `status: "edited"`, mark `m2` `rejected`), the same row stays selected, and
  `GET …/review` of the project is sent again. [component]
- SV-26: While a request is in flight, "Saving…" shows in a `role="status"` region and every edit, settle, add,
  reset and sign-off control is disabled. [component] (delayed mock)
- SV-27: A 409 `{detail, code: "not-allowed"}` or 422 `{detail, code: "invalid"}` answer shows `detail` and `code`
  in a `role="alert"` in the detail, and the takeoff on screen is unchanged; the next successful request removes
  the alert. [component] bodies derived from `error.json`
- SV-28: "Add a missed one" appears on count rows only (`door`), not on area rows. With it pressed the viewer gets
  `onPick`; `onPick(1, [0.2, 0.5, 0.23, 0.53])` sends exactly `review_requests.json[2]`, and add mode ends
  (`onPick` unset). Outside add mode `onPick` is not passed. [component]
- SV-29: In add mode, Escape or pressing the button again ends add mode and sends no request. [component]
- SV-30: On a conflict row one "Keep" button per `conflict.values[]` entry sends `settle` with that value ("Keep B:
  30.00 m² (<methodName('printed_label')>)" sends `{"quantity":"area:room|name=1.01","action":"settle","value":30}`). [component] `takeoff.json`
- SV-31: The Settle field sends `settle` with the typed number (`3` on `door` gives `review_requests.json[3]`); the
  Settle button is disabled while the field is empty, not a number, or negative. [component]
- SV-32: A row with `settled: {"value": 22.401, "at": "2026-11-14T01:30:00Z"}` shows "Settled at 22.40 m²
  (2026-11-14 01:30 UTC). A mark edit clears it." [component] derived
- SV-33: "Reset this quantity" shows on a row with an edit (status `edited`, `settled` set, or a mark that is
  `rejected`, `added`, or counted with a `reason`) and sends `review_requests.json[4]` for `door`; it is hidden on
  an untouched row. [component] derived
- SV-34: "Reset all edits" asks for confirmation (`window.confirm`); confirmed it sends `review_requests.json[5]`,
  cancelled it sends nothing. [component]

Sign-off

- SV-35: "Signing as" is a text field limited to 100 characters, filled from this browser's saved name; Sign off is
  disabled while it is empty or only spaces; the trimmed name is saved for next time. A failing `localStorage`
  leaves the field empty and the screen working. [component]
- SV-36: "Sign off 2" on `door` with name "Ana" sends `POST /api/drawings/{id}/signoff` with exactly
  `signoff_request.json`. [component]
- SV-37: Sign off is disabled on a row with `needs_person: true`, with the text "Settle a value before signing
  off."; it is enabled on a conflict row that a rule decides. [component] `takeoff.json`, derived
- SV-38: A signed row (derived `door`) shows "Signed off by Ana, 2026-11-14 01:40 UTC: 2. Engineers see this value as verified.",
  disables every mark action, Keep, Settle, Add and Reset this quantity with "Undo the sign-off to edit.", and shows
  "Undo sign-off", which sends `{"quantity":"door","by":"Ana","undo":true}`. [component]

Zeros, export, side panel

- SV-39: "Show rows with value 0" reloads with `?zeros=true`; with it on, every `review` and `signoff` request and
  the CSV link carry `zeros=true`. [component]
- SV-40: "Export CSV" is a link to `/api/drawings/{id}/takeoff.csv` (with `?zeros=true` when on) that has the
  `download` attribute; it is absent in the empty state. [component]
- SV-41: The side panel lists every `project_review.json` drawing with `file`, "N to review" when `to_review` > 0,
  "S of Q signed off", and "nothing counted" when `quantities` is 0; the current drawing is marked "current" in
  text; each links to its own `…/surveyor` route. [component] `project_review.json`
- SV-42: The side panel lists every `conflicts[]` entry with its `label`, `file`, its values with unit, and
  "needs you" (`needs_person`), "settled" (`settled` set) or "decided by rule"; each links to
  `#/p/<project_id>/d/<drawing_id>/surveyor?q=<encoded quantity>`. [component] `project_review.json`
- SV-43: A failing `GET …/review` shows its `detail`, `code` and Retry in the side panel only; the table still
  renders. [component]

States, safety, layout

- SV-44: An empty takeoff shows "Nothing was counted on this drawing."; with `reader.extractor: "hello"` also the
  no-reader sentence; with zeros off also the zeros toggle; there is no Sign off, CSV link or Reset all.
  [component] derived `takeoff.json` (`quantities: []`), derived `drawing.json`
- SV-45: A 404 on the takeoff shows `ErrorView` with "no drawing 0123456789abcdef" and "code: not-found", a link
  "Back to projects" to `#/` and no Retry (asking again finds nothing, QA qa-3 (b)); any other load error (a 500)
  shows Retry, which re-sends the loads. [component] `error.json`, derived 500
- SV-46: A label, mark label, reason, rule text or file name holding `<img src=x onerror=alert(1)>` renders as that
  literal text and adds no element. [component] derived
- SV-47: At 390x844 and 1440x900 the screen has no horizontal page scroll
  (`document.documentElement.scrollWidth <= innerWidth`) and every status is readable as text; screenshots of both
  are saved. [e2e] the sample project

End to end (the backend on fakes, the sample project from `POST /api/projects/sample`)

- SV-48: Opening the surveyor route of the sample's `plans/flat-b.pdf` drawing shows its takeoff with
  `area:room|name=1.01` in "To review"; Reject on a `door` mark lowers the door value by 1, Restore brings it
  back; Sign off as "Ana" shows "Verified" and the progress counts it; the CSV downloaded from Export CSV has a
  `door` row with `signed_by` "Ana"; Undo sign-off returns the row to its earlier words. Reset all edits at the
  start and the end keeps the run repeatable. [e2e]
- SV-49: After signing off `door` on the surveyor route, the engineer route of the same drawing answering "How many
  doors are there?" shows "Verified by Ana" (EN-32). [e2e]

## Out of scope

- The engineer's verified display (engineer spec); the surveyor only signs off.
- Amber per-item "contested" marks: v1 shows a conflict per quantity with both values and their boxes (API.md
  "What is not in v1"). The mock's "Count it / Leave out" on a contested mark is not built.
- Adding a mark to an area or length, editing a room's outline or label (not in v1).
- Toggling a mark by clicking it in the viewer: a viewer click selects the mark's row; the action is in the list
  (fewer accidental edits on a phone).
- Grouping rows by `measure`/`subject`/`scope`, sorting or filtering the table.
- The mock's ingest-end conflict gate ("the workspace opens when every conflict is settled"): the side panel's
  conflict list replaces it; nothing is blocked.
- A login or a verified identity behind `by`: the name is what the surveyor types (no auth, decision 0001).
- Fetching the CSV by script, or showing an error for a failed download (the drawing was just loaded, so a 404 is
  unlikely; the browser shows the failure).
- Any confidence number: the takeoff has none, and the answer's confidence is the engineer's (Open point 1).
- Live updates from another tab or person (no server push in v1); the screen shows the last response.

## Open points

1. **Pending contract change: answer confidence** (board #14, next backend PR). The answer's `confidence` becomes
   an object `{signal, score, calibrated: false}`, where `score` is a raw model choice score, not a probability.
   The takeoff carries no confidence, so this screen shows none; no number here is ever worded as a probability.
   Recommendation: nothing to build here; the engineer spec owns the new shape.
2. **Fixture gaps.** No fixture has a signed row, a `needs_person: true` row, an excluded or added mark, an
   estimate, a settled value, or a 409/422 body; tests derive them from `takeoff.json` and `error.json` until the
   real ones land (asked on board #14).
3. **`review_queue` names a key with no row** in `takeoff.json` (`area:room|name=küche`, trimmed out). SV-3 makes
   the screen ignore such keys. Recommendation: keep the fixture as it is; it tests that.
4. **`?q=` in the hash.** Decided (round 1): the engineer's "Send to surveyor" links `?q=<key>` via `routeHref`.
5. **Adding a mark is a click, not a drawn box.** viewer.md's `onPick` gives a small square around the clicked
   point (3 % of the page width, its Open point 7); the mock and `review_requests.json` (a 0.03 square) agree.
   Recommendation: keep it; a dragged box is not needed for a count.
6. **One value and time formatter.** Decided (round 1): shared.md owns `formatValue` and `formatTime` in
   `frontend/src/api/format.ts`; `surveyor/words.ts` keeps the status, mark-row and action words. The status words
   are copied from engineer.md (EN-31), so the two screens agree; mark signs are the same everywhere (× – +n n).
7. **Workspace side panel.** The mock shows the drawings list on both roles. This spec owns it in
   `frontend/src/surveyor/ProjectReviewSide.tsx`. Recommendation: if the engineer spec wants the same list, move it
   to `frontend/src/shell/` with one owner, before build.
8. **e2e ownership.** Decided (round 1): `frontend/e2e/` belongs to the e2e worker (golden-path.md), who builds
   SV-47 to SV-49.
9. **No `by` in the takeoff's edits.** Edits record no person, only sign-off does; "rejected by a surveyor" is all
   the screen can say. Fine for v1.
10. **Sample data for SV-48.** It assumes the sample's `plans/flat-b.pdf` has `door` marks and the
   `area:room|name=1.01` conflict, as `project_review.json` and `takeoff.json` (made from the sample) show. If the
   sample changes, the e2e picks the first drawing with `to_review > 0` from `GET …/review` instead.
