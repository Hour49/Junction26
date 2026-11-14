# Engineer workspace (spec, frontend v1)
Status: draft, 2026-11-14, by fe-spec-engineer.  Story: #33.  API: docs/API.md (v1, main 5092dc3), plus the
pending `confidence` object (Open point 1).

## Purpose

The engineer opens one drawing, asks a question in plain words and gets one number with its proof: the numbered
marks or shaded rooms on the page, the counting rule and what it left out, the second method's value, the cost and
the time. A question the drawing cannot answer is refused with the reason and questions it can answer. A value a
surveyor signed off shows as verified. Mock: `demo/` screen 2 (`index.html#work/engineer/A`).

## Files owned

- `frontend/src/engineer/EngineerPage.tsx`: the route view `EngineerPage({projectId, drawingId, query})`, mounted by
  the shell with key = route path without query (shared.md); loads the drawing, holds the thread of asked questions.
  `query` is not used in v1.
- `frontend/src/engineer/DrawingHeader.tsx`: file, how it was read, the suggested questions.
- `frontend/src/engineer/AskBox.tsx`: the question input with its length check.
- `frontend/src/engineer/AnswerCard.tsx`: one answer (value, proof, rule, checks, cost) or one refusal.
- `frontend/src/engineer/ChecksPanel.tsx`: second method, conflict, settled, estimate, verified.
- `frontend/src/engineer/ModelProof.tsx`: the answer of a building model (no page): objects and storeys.
- `frontend/src/engineer/format.ts`: cost, latency and model score formatting only; values and times use the
  shared `formatValue` and `formatTime` (`src/api/format.ts`, shared.md).
- Tests next to each file: `*.test.ts(x)`. Fixture helpers in `frontend/src/engineer/testing.ts` (derived fixtures,
  see Acceptance criteria).

Uses, does not own: the API client (`frontend/src/api/`, shared.md), the shell, banner, error and loading views
(shared.md), the page viewer (viewer.md).

## User flow

1. The user opens `#/p/<project_id>/d/<drawing_id>/engineer` (from the ingest screen, the shell's role switch or a
   deep link). The screen shows a loading view, then the drawing header: the file path, how it was read, the page
   (no marks) and the suggested questions as buttons.
2. The user clicks a suggestion or types a question and presses Enter or Ask. The question appears in the thread at
   once with "Reading <file>…"; the Ask button is disabled until the answer arrives.
3. The answer replaces the pending line: the value and unit large, the quantity label, the page with numbered marks
   (count) or shaded rooms (area), a list of the marks, the counting rule and the sum, the second method's check,
   the status in words, the reader, cost and time. The thread scrolls to it.
4. The user hovers or focuses a row of the mark list: that mark is highlighted on the page; clicking a mark on the
   page highlights its row.
5. If the drawing cannot answer, the turn shows "I can't answer that from this drawing.", the reason and up to six
   questions it can answer as buttons; clicking one asks it (step 2).
6. If the surveyor signed the value off, the answer shows "Verified by <name>" with the time.
7. "Send to surveyor" opens the surveyor view of the same drawing on this quantity. "Picture of this answer" opens
   the server's drawn proof (`evidence.png`) in a new tab.
8. The user asks more questions; earlier answers stay in the thread above (newest at the bottom). The thread lives
   in memory only: a reload or another drawing starts an empty thread.

## API calls

### `GET /api/drawings/{drawing_id}?project=<project_id>` (API.md "Drawings")

Called once when the route opens (and again when `drawing_id` in the route changes), always with `project` = the
route's project id (client: `getDrawing(drawingId, {project: projectId})`). A drawing is shared by content across
projects; with `project` its `file` and `reader.source` are the names this project uploaded. A project that does not
hold the drawing answers 404 (the Drawing error state). Fixture: `drawing.json`.

| Field | Drives |
| --- | --- |
| `file` | the header title and the pending line "Reading <file>…" |
| `reader.route`, `reader.source`, `reader.extractor`, `reader.second_counter`, `reader.question_parser` | the header's "How it was read" line: `<route> route, read from <source> by <extractor>; second count: <second_counter>; questions: <question_parser>`. An `extractor` of `hello` reads "not read (no reader for this route yet)" instead of `by hello`. A `second_counter` of `none` (no second count ran) reads "no second count" instead of `second count: none`. |
| `pages` | the viewer before the first answer (page 1, no marks). `[]`: no viewer; the header says "Building model: no sheet to draw on." |
| `credit` | passed to the viewer, which places the shell's `<Credit>` under the page; null shows "Credit: none recorded for this file" |
| `suggestions[].question` | one button each, text = `question`; click asks it |
| `suggestions[].label` | the button's `title` (tooltip) |

### `POST /api/ask` (API.md "Answering")

Body `{"drawing_id": <route drawing id>, "question": <trimmed input>, "project_id": <route project id>}` (shape:
`ask_request.json`; `project_id` is optional in the API and always sent here, so the answer's `file` and
`reader.source` are this project's names). Called on Ask,
Enter, a suggestion click or a `can_answer` click. Fixtures: `answer.json` (count), `answer_area.json` (sum of rooms),
`answer_confidence.json` (count with a model score), `answer_model.json` (building model, no page),
`answer_refused.json` (refusal).

| Field | Drives |
| --- | --- |
| `question` | the user's bubble (the server's echo, so a trimmed question shows as sent) |
| `answer`, `unit` | the big value and unit (format below). Null: no number anywhere in the card. A string `answer` (schedule) shows as text, `unit` null shows no unit. |
| `confidence.score`, `confidence.calibrated` | the score line: "Second reader's score 0.87 (not a probability)". `calibrated: false` is the only value in the contract; the score is never shown as a percent, claimed as a probability, or called a confidence. `confidence` null: the line is absent (no made-up figure). |
| `confidence.signal` | only in Details: "Signal: <signal>" (an internal name, never on the card itself) |
| `quantity.label` | the card title |
| `quantity.key` | "Query: `<key>`" in the details |
| `quantity.status` | the status in words (table in States); never colour alone |
| `quantity.rule.text`, `quantity.rule.id` | "Counting rule: <text>", the id in small text |
| `quantity.first`, `quantity.second`, `quantity.conflict`, `quantity.needs_person`, `quantity.settled`, `quantity.estimate`, `quantity.original_value`, `quantity.signed` | the checks panel (States) |
| `quantity.measure` | the viewer's `measure` prop (badges carry values unless `count`) |
| `quantity.conflict` | the viewer's `conflict` prop (tags A, B on the page, viewer.md) and the checks panel |
| `quantity` null with `refusal` null | a schedule answer: no rule or checks panel; the proof's schedule table shows instead |
| `marks` | the viewer's `marks` prop; also the mark list: one row per mark, its sign as the viewer draws it (counted `n`, added `+n`, rejected `×`, excluded `–`), `label` (null: "item"), `value` for a sum (format below), and the state in the viewer's words for `rejected` ("rejected by a surveyor"), `added` ("added by a surveyor"), `excluded` ("left out by the rule: <reason>") |
| `pages` | passed to the viewer (no second request). `[]`: no viewer, `ModelProof` instead |
| `proof.kind` | which proof block shows: `count`/`sum` the viewer and mark list, `model` `ModelProof`, `schedule` the schedule table, `none` nothing |
| `proof.legend[]` | the viewer's `legend` prop: it draws the colour key and the `note` lines (items counted without a mark), so this screen shows no separate legend |
| `proof.arithmetic` | one line under the mark list ("22.4 + 2.49 + … = 52.27 m²; left out: Balkon 12.45 (outdoor room)"), when not null |
| `proof.objects[]` | `ModelProof` table: `name`, `class`, `storey`, `global_id` |
| `proof.storeys[]` | `ModelProof` table: one row per storey, one column per class in `counts` |
| `proof.schedule` | table `title`, `columns` as header, `rows[].cells` (null cell = empty), "<rows> of <of> rows" |
| `refusal.text`, `refusal.code`, `refusal.can_answer[]` | the refusal turn (States) |
| `method`, `explanation` | the details (collapsed by default): "Method: <method>", "How: <explanation>" when not null. A misspelt question's `explanation` starts with how it was read (backend #80): "read 'mnay' as 'many'" (several joined by ", "), then "; " and the answer's own explanation when it has one. The How line shows it in full, as text, and wraps at 390 px (long words break: `overflow-wrap: anywhere` from the page) |
| `reader` | "Where this came from": `<extractor>` read `<source>` (`<route>` route), second count by `<second_counter>`; with `second_counter` `none`: `<extractor>` read `<source>` (`<route>` route), no second count |
| `cost_usd`, `latency_s` | the card footer: "Cost $0" / "Time 0.2 ms" (format below) |
| `drawing_id`, `file` | footer "Drawing <file>"; links |

Not used: `line` (the scorer's copy, it can hold the dev prior's estimate on a refusal: never shown, see Out of
scope), `proof.confidence` (same value as `confidence`), `quantity.unlocated` (the legend's `note` says it in words,
drawn by the viewer). The viewer's other props: `file` = drawing `file`, `pages` = `answer.pages`, `credit` =
drawing `credit` (the answer has none), `highlighted` = the hovered or focused mark-list row's id, `selected` /
`onSelect` = the selected mark, `onHover` = highlight its list row; `onPick` is never set here.

### `GET /api/drawings/{drawing_id}/pages/{n}.png?width=` (API.md "Drawings")

Requested by the viewer, not by this screen (viewer.md picks the width).

### `GET /api/drawings/{drawing_id}/evidence.png?question=&width=1600` (API.md "Answering")

Not fetched by the screen: the "Picture of this answer" link's `href`, built by the shared client's
`evidenceUrl(drawing_id, question)` (shared.md; `question` encoded by `encodeURIComponent`), `target="_blank"`,
`rel="noopener"`. Shown only on a non-refused answer with `confidence` null: the image still prints the old
probability line, so it stays hidden for an answer with a model score until the backend drops that line (shared.md
Open point 5).

### `GET /api/info` (API.md "GET /api/info")

Read through the shell (shared.md), not fetched again. `limits.question_chars` sets the question length limit;
`no_keys` drives the shell's "running offline" banner.

### Formatting

| Input | Output |
| --- | --- |
| value and unit | shared `formatValue(value, unit)` (shared.md): count or null unit → integer, no unit text (`2`); other units → exactly 2 decimals with `m²` `m³` `m` `ft²` `ft` (`52.27 m²`, `30.00 m²`, `22.40 m²`) |
| `cost_usd` | `0` → `$0`; below 0.01 → 4 decimals `$0.0004`; else 2 decimals `$0.12` |
| `latency_s` | below 1 → milliseconds with 1 decimal `0.2 ms`, `2.0 ms`; else seconds with 2 decimals `1.25 s` |
| `confidence.score` | 2 decimals as a plain number, `0.87` → `0.87`; never `%` |
| an ISO time (`signed.at`, `settled.at`) | shared `formatTime`: `YYYY-MM-DD HH:MM UTC` |

`engineer/format.ts` holds the `cost_usd`, `latency_s` and `confidence.score` rows.

## States

| State | How to reach it on purpose | What shows |
| --- | --- | --- |
| Loading drawing | throttle the network, or a mocked `GET /api/drawings/{id}` that never resolves | the shared loading view; no ask box |
| Drawing error | unknown drawing id in the route (`#/p/x/d/0123456789abcdef/engineer`) → 404 `error.json` | the shared `ErrorView` with `detail` and `code` (and its "Go to the start" link for `not-found`), plus a link back to `#/p/<project_id>` |
| Empty thread | open a drawing, ask nothing | header, page without marks, suggestions, ask box; text "Ask a question about this drawing." |
| No suggestions | `drawing.json` with `suggestions: []` | instead of the buttons: "No ready questions for this drawing."; with extractor `hello` also "Its route has no reader yet, so questions will be refused." Ask box stays usable. |
| Asking | a mocked `POST /api/ask` that never resolves | the question bubble, "Reading <file>…" with a spinner, Ask disabled, input kept for the next question |
| Ask error | mocked `POST /api/ask` with 404 `error.json`, 422 `validation` or 500 `internal` | in that turn: "The question could not be answered: <detail>" and the `code` in small text, a "Try again" button that sends the same question; Ask re-enabled |
| Refused | `answer_refused.json` | bold "I can't answer that from this drawing.", `refusal.text`, the code in small text, one button per `can_answer[].question`; no number, no viewer marks, no "Send to surveyor", no picture link |
| Answer, count | `answer.json` | value `2`, title "door count", viewer with marks 1 and 2, mark list "1 door", "2 door", rule "every element, room and plan the drawing lists counts once", status "One method" |
| Answer, sum | `answer_area.json` | value `52.27 m²`, rooms shaded, mark list with "Küche 22.40 m²"…, the arithmetic line with what was left out, the viewer's colour key |
| Answer with a model score | `answer_confidence.json` (`confidence: {"signal": "g1main", "score": 0.87, "calibrated": false}`) | as count plus "Second reader's score 0.87 (not a probability)"; Details has "Signal: g1main"; no "Picture of this answer" link |
| Answer, building model | `answer_model.json` | value `2`, no viewer; `ModelProof` with "Door 1", "Door 2", their storey and GlobalId, the storey table, the arithmetic line |
| Answer, schedule | see Open points (no fixture yet) | the string answer, the schedule table, no rule or checks panel |
| Verified | derived: `answer.json` with `quantity.status: "signed"`, `quantity.signed: {"by": "Ana", "at": "2026-11-14T01:40:00Z", "value": 2}` | status "Verified", "Verified by Ana, 2026-11-14 01:40 UTC" next to the value |
| Methods disagree, rule decides | derived: `answer.json` with `quantity` = `takeoff.json` `quantities[0]`, `answer` 30.0, `unit` "m2" | status "Methods disagree"; both values "22.40 m² by polygon_x_scale", "30.00 m² by printed_label"; "Kept 30.00 m²: the printed label over the outline at the sheet's scale" |
| Methods disagree, nobody decided | the above with `conflict.resolution: null`, `needs_person: true` | as above, and instead of "Kept": "No rule decides. A surveyor has to settle it before this value can be used." |
| Methods agree | derived: `answer.json` with `status: "agree"`, `first: {"method": "plan_drawing", "value": 2}`, `second: {"method": "ifc_model", "value": 2}` | status "Two methods agree"; "Second method (ifc_model): 2, agrees" |
| One method | `answer.json` (`first`/`second` null) | "Measured by one method; no second check." |
| Estimate | derived: `answer.json` with `status: "estimate"`, `estimate: "scale estimated from a door width"` | status "Estimate"; "Estimate: scale estimated from a door width" |
| Edited in review | derived: `answer.json` with `status: "edited"`, `value`/`answer` 1, `original_value` 2, mark m2 `state: "rejected"`, `n: null` | status "Changed in review"; "Changed in review, was 2"; mark list row "× door rejected by a surveyor" |
| Settled | derived: conflict case with `settled: {"value": 22.401, "at": "2026-11-14T01:30:00Z"}` | "Settled by a surveyor at 2026-11-14 01:30 UTC: 22.40 m²" |
| Excluded item | derived: `answer_area.json` with one more mark `{"id": "x1", "n": null, "state": "excluded", "reason": "outdoor room", "label": "Balkon", …}` (box/polygon copied from m2) | mark list row "– Balkon left out by the rule: outdoor room" |
| No-keys | `info.json` (`no_keys: true`) | the shell's "running offline" banner shows on this route (shared.md) |

Status words (`quantity.status`): `signed` "Verified", `conflict` "Methods disagree", `estimate` "Estimate",
`edited` "Changed in review", `agree` "Two methods agree", `single` "One method".

## Layout

Desktop 1440x900 (mock: `#work/engineer/A`, "chat-mode"): one centred column, max 960 px wide.
- Top: drawing header (file path as title, "How it was read" line, suggestion buttons in a wrapping row), and the
  page viewer at the column's width until the first answer; after it, the header keeps only the title and the
  "How it was read" line.
- Middle: the thread. Each turn: the question as a right-aligned bubble, then the answer: one sentence with the
  value in bold, then the card: viewer on the left (about 60 %, with its own legend and caption), on the right
  "The answer" (value, unit, status, model score, verified), "Counting rule", "Checks", "Where this came from";
  under the viewer the mark list and the arithmetic line; footer row, one flex row aligned on the text baseline:
  Drawing, Cost, Time, "Details" (its summary inline in the row; opened, its body takes a full line below),
  "Picture of this answer", "Send to surveyor".
- Bottom: the ask box, fixed to the bottom of the column, with "<n> asked" and the length counter when near the
  limit.

Phone 390x844: same order, one column, 16 px gutters; in the card the viewer is full width and the right-hand
blocks follow below it; the footer wraps to two lines; the ask box sticks to the bottom; tap targets at least
44 px; no horizontal scroll (long file paths and keys wrap, `overflow-wrap: anywhere`). Table cells (the building
model's objects and storeys) never break inside a word (`overflow-wrap: normal`, `word-break: normal`); a table
wider than the column scrolls sideways inside its own wrapper.

## Acceptance criteria

Fixtures are `backend/tests/fixtures/api_v1/*.json`, imported read-only. "Derived" fixtures are those files with the
named fields overridden in `testing.ts` (a spread over the imported object), never a hand-written whole response.
The API is mocked with the shared `mockApi` helper (shared.md) in component tests.

Drawing header and ask box
- EN-1 Opening the route calls `GET /api/drawings/<drawing_id>` once with the id from the route. [component, `drawing.json`]
- EN-2 While that request is pending, the shared loading view shows and no ask box is rendered. [component, pending fetch]
- EN-3 A 404 shows the shared `ErrorView` with "no drawing 0123456789abcdef" and "not-found", and a link to `#/p/<project_id>`. [component, `error.json` 404]
- EN-4 The header shows "plans/flat-a.pdf" and "vector route, read from plans/flat-a.pdf by pdf; second count: ifc; questions: templates"; with `second_counter: "none"` it shows "vector route, read from plans/flat-a.pdf by pdf; no second count; questions: templates". [component, `drawing.json`, derived `drawing.json`]
- EN-5 With `reader.extractor: "hello"` the header says "not read (no reader for this route yet)" and does not say "by hello". [component, derived `drawing.json`]
- EN-6 One button per suggestion, labelled with its `question`, in order: "How many doors are there?", "How many windows are there?", "How many toilets are there?". [component, `drawing.json`]
- EN-7 With `suggestions: []` the screen shows "No ready questions for this drawing." and the ask box. [component, derived `drawing.json`]
- EN-8 Before any question the viewer shows page 1 with no marks and the text "Ask a question about this drawing." shows. [component, `drawing.json`]
- EN-9 Clicking a suggestion sends `POST /api/ask` with body `{"drawing_id": "adeefbbcc17559fc", "question": "How many doors are there?"}`. [component, `drawing.json`]
- EN-10 Typing "  How many doors are there?  " and pressing Enter sends the trimmed question; an empty or whitespace-only input sends nothing and Ask is disabled. [component]
- EN-11 With `limits.question_chars` 2000, a 2001-character question disables Ask and shows "Questions are at most 2000 characters."; 2000 characters is allowed. [component, `info.json`]
- EN-12 While an ask is pending the turn shows the question and "Reading plans/flat-a.pdf…", Ask is disabled, and a second Enter sends nothing. [component, pending fetch]

Answers
- EN-13 A count answer shows the value "2" in the card, the title "door count", and no unit text. [component, `answer.json`]
- EN-14 A sum answer shows "52.27 m²". [component, `answer_area.json`]
- EN-15 The viewer gets `answer.marks`, `answer.pages`, `quantity.measure` and the drawing's `credit`: two numbered marks "1" and "2" are on page 1. [component, `drawing.json` + `answer.json`]
- EN-16 The mark list has one row per mark: "1 door", "2 door"; for a sum the row carries the value: "1 Küche 22.40 m²". [component, `answer.json`, `answer_area.json`]
- EN-17 Hovering or focusing a mark-list row passes its id as the viewer's `highlighted` (mark m2's outline is 4 px, VW-38); clicking badge 2 in the viewer marks the row "2 door" as selected (`aria-selected="true"`). [component, `answer.json`]
- EN-18 The rule shows "Counting rule: every element, room and plan the drawing lists counts once". [component, `answer.json`]
- EN-19 The arithmetic line "22.4 + 2.49 + 12.45 + 14.93 = 52.27 m²; left out: Balkon 12.45 (outdoor room)" shows for the sum; no arithmetic line shows for `answer.json` (whose `proof.arithmetic` is null). [component, `answer_area.json`, `answer.json`]
- EN-20 The viewer gets `proof.legend` as `legend`: the Küche polygon's stroke is `#d62728` and the Reduit polygon's `#1f77b4` (VW-21); a derived legend `note` "1 counted without a mark (second reader)" shows as text. [component, `answer_area.json`, derived `answer.json`]
- EN-21 An excluded mark shows in the list with the sign "–" and no number, as "– Balkon left out by the rule: outdoor room". [component, derived `answer_area.json`]
- EN-22 The viewer gets `quantity.conflict` as `conflict`: tags "A" and "B" are on the page for the derived conflict answer; `answer.json` (conflict null) has no tag. [component, derived conflict, `answer.json`]
- EN-23 With the `confidence` object, "Second reader's score 0.87 (not a probability)" shows; the signal name ("g1main") is not on the card outside Details, and Details shows "Signal: g1main". The card has no "%" next to the score, no word "confidence", and "probability" only in "not a probability". For `answer.json` (confidence null) no score line and no "Signal:" line show. [component, `answer_confidence.json`]
- EN-24 The footer shows "Cost $0" and "Time 2.0 ms" for `answer.json`. [component]
- EN-25 `engineer/format.ts` gives: cost 0 → "$0", 0.0004 → "$0.0004", 0.123 → "$0.12"; latency 0.0001622 → "0.2 ms", 0.002 → "2.0 ms", 1.25 → "1.25 s"; score 0.87 → "0.87". Values and times on screen come from the shared `formatValue`/`formatTime` (their criteria are in shared.md). [unit]
- EN-26 "Where this came from" shows "pdf read plans/flat-a.pdf (vector route), no second count" for `answer.json` (`second_counter: "none"`), and "pdf read plans/flat-a.pdf (vector route), second count by ifc" with `second_counter: "ifc"`. [component, `answer.json`, derived `answer.json`]
- EN-27 "Details" is collapsed by default, its summary in the footer row with Drawing, Cost and Time (the row aligns items on the baseline); opened it shows "Query: door" and "Method: takeoff"; with `explanation` null no "How:" line. [component, `answer.json`]
- EN-28 A building-model answer shows no viewer; it shows a table with "Door 1", "Ground floor", "000000000000000000000K", a storey table row "Ground floor" with door 2, window 3, and the line "2 door objects in the model on Ground floor". Each table sits in a wrapper that scrolls sideways (`overflow-x: auto`), and its cells do not break inside words (`overflow-wrap: normal`, `word-break: normal`). [component, `answer_model.json`]
- EN-29 "Picture of this answer" links to `/api/drawings/adeefbbcc17559fc/evidence.png?question=How%20many%20doors%20are%20there%3F&width=1600` and opens a new tab when `confidence` is null; with the `confidence` object set there is no "Picture of this answer" link. [component, `answer.json`, `answer_confidence.json` or its derived form]
- EN-30 "Send to surveyor" links to `#/p/<project_id>/d/adeefbbcc17559fc/surveyor?q=door` (built with the shared `routeHref`; derived conflict: `?q=area%3Aroom%7Cname%3D1.01`), surveyor.md Open point 4. Absent when `quantity` is null. [component, `answer.json`, derived conflict]

Checks and review state
- EN-31 Each status shows its word: signed "Verified", conflict "Methods disagree", estimate "Estimate", edited "Changed in review", agree "Two methods agree", single "One method". [component, `answer.json` and its derived variants]
- EN-32 A signed answer shows "Verified by Ana, 2026-11-14 01:40 UTC" next to the value. [component, derived signed `answer.json`]
- EN-33 A conflict shows both values with their methods, "22.40 m² by polygon_x_scale" and "30.00 m² by printed_label", and "Kept 30.00 m²: the printed label over the outline at the sheet's scale". [component, derived conflict]
- EN-34 With `conflict.resolution` null and `needs_person` true it shows "No rule decides. A surveyor has to settle it before this value can be used." and no "Kept" line. [component, derived conflict]
- EN-35 `status: "agree"` shows "Second method (ifc_model): 2, agrees"; `first`/`second` null shows "Measured by one method; no second check.". [component, derived agree, `answer.json`]
- EN-36 An estimate shows "Estimate: scale estimated from a door width". [component, derived estimate]
- EN-37 An edited answer shows "Changed in review, was 2" and the rejected mark row "× door rejected by a surveyor"; an added mark (derived: `{"id": "a1", "n": 3, "state": "added", "label": null, "ref": null, "polygon": null, …}`) shows "+3 item added by a surveyor". [component, derived edited]
- EN-38 A settled value shows "Settled by a surveyor at 2026-11-14 01:30 UTC: 22.40 m²". [component, derived settled]

Refusals and errors
- EN-39 A refusal shows "I can't answer that from this drawing.", the text "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.", the code "unsupported-question", and no number, marks, picture link or takeoff link. [component, `answer_refused.json`]
- EN-40 The refusal shows one button per `can_answer` ("How many doors are there?", "How many windows are there?"); clicking one sends `POST /api/ask` with that question. [component, `answer_refused.json`]
- EN-41 An ask that fails with 422 shows "The question could not be answered:" with the server's `detail` and "validation"; "Try again" sends the same question again; Ask is enabled again. [component, mocked 422]
- EN-42 Strings from the server render as text: a `quantity.label`, `marks[].label`, `refusal.text` and `question` of `<img src=x onerror=alert(1)>` appear literally and add no element. [component, derived `answer.json`]

Thread and pages
- EN-43 Asking a second question keeps the first answer above it; the newest turn is last and scrolled into view; the counter reads "2 asked". [component, `answer.json` then `answer_area.json`]
- EN-44 Changing `drawing_id` in the route loads the new drawing and starts an empty thread. [component]
- EN-45 No horizontal scroll at 390x844 and at 1440x900 with `answer_area.json` shown; the ask box is visible without scrolling. [e2e, golden-path run on the fakes]
- EN-46 The question input has the accessible name "Question" (a `<label>`) and the submit button the name "Ask". [component, `drawing.json`]
- EN-47 Each thread turn is an `<article>` whose `aria-label` is its question: after asking "How many doors are there?" there is `getByRole("article", {name: "How many doors are there?"})`, and it holds that turn's pending line, answer, refusal or error. [component, `answer.json`, `answer_refused.json`]
- EN-48 The big value of an answer has `data-testid="answer-value"` with the formatted value as its text ("2" for `answer.json`, "52.27 m²" for `answer_area.json`); a refusal or an error turn has no element with that test id. [component, `answer.json`, `answer_area.json`, `answer_refused.json`]
- EN-49 The drawing is requested with the route's project: `GET /api/drawings/adeefbbcc17559fc?project=5e0c1a2b3d4f`. [component, `drawing.json`]
- EN-50 Every ask body carries `project_id`: a suggestion click, a typed question, a `can_answer` click and "Try again" each send `{"drawing_id", "question", "project_id": "5e0c1a2b3d4f"}`. [component, `answer.json`, `answer_refused.json`]
- EN-51 The read-as note leads the How line in Details, in full and as text: with `explanation` "read 'mnay' as 'many'; the scale is estimated from a door width" the line reads "How: read 'mnay' as 'many'; the scale is estimated from a door width"; with only the note it reads "How: read 'mnay' as 'many'". [component, derived `answer.json`; the 390 px wrap: fe-golden's browser check]

[e2e] criteria are built by the e2e worker (golden-path.md); this spec's build worker writes no file in `frontend/e2e/`.

## Out of scope

- Keeping the thread across reloads, or sharing it between people; a question on a whole project (API.md "What is
  not in v1").
- Drawing per-item contested (amber) marks: v1 shows a conflict per quantity with both values (API.md "What is not
  in v1").
- Showing `line` or the dev prior's estimate on a refusal: no silent guesses (REQUIREMENTS §5).
- A made-up confidence when `confidence` is null (the mock's confidence bars and percentages are invented); showing
  the model score as a probability or percent, or a "sure" cutoff (the score is uncalibrated).
- Editing marks, settling or signing off from this screen: the surveyor view does that.
- The mock's "Where this came from" list of several files per drawing: API v1 gives one `reader.source`.
- Readable names for method slugs (`polygon_x_scale`): shown as sent.
- A model-object 3D view, or fetching `GET /api/drawings/{id}/model`.

## Open points

1. **`confidence` shape is pending the next backend PR** (board #14). Merged API.md (5092dc3) and
   `answer_confidence.json` still have `confidence: 0.87` as "the probability that the answer is right". This spec
   specifies only the coming object `{signal, score, calibrated: false}` (a raw model choice score) and never shows
   it as a probability. Recommend: build EN-23 against the derived fixture in `testing.ts`, switch to the
   regenerated `answer_confidence.json` and the regenerated types when that PR merges, and delete the derived one.
   The value of `signal` in the derived fixture ("choice") is a stand-in; the real one comes with that PR.
   `proof.confidence` presumably changes the same way; this screen does not read it.
2. **No schedule fixture.** `proof.kind: "schedule"` (string `answer`, `quantity` null, `proof.schedule`) has no
   fixture, so its state has no criterion. Asked on board #14; when it lands, add a criterion like EN-28.
3. **No fixture with a conflict, a sign-off or an edit inside an answer.** The criteria use derived fixtures
   (`answer.json` with fields overridden, or `takeoff.json`'s conflict row as `quantity`). Asked on board #14;
   the derived ones are dropped when the real ones land.
4. **"The query"** (story, REQUIREMENTS Q5): API v1 has no query text, only `quantity.key`, `method` and
   `explanation`. The spec shows the key as the query. Recommend: keep, unless core can give the parsed query.
5. **`?q=` on the surveyor route** is surveyor.md's proposal (its Open point 4) and shared.md parses it (SH-3,
   `routeHref`); this spec links to it (EN-30). The engineer route ignores a `?q=` it is given (the shell keeps one
   on the role links, SH); recommend leaving it so for v1.
6. **One value formatter:** decided (round 1): shared.md owns `formatValue` and `formatTime` in `src/api/format.ts`;
   `engineer/format.ts` keeps cost, latency and score.
7. **The mock's per-answer sources and confidence bar.** The mock lists three source files per drawing and a
   confidence bar; v1 has one `reader.source` and no bar. The spec keeps the mock's card layout with what the API
   gives (Out of scope).
