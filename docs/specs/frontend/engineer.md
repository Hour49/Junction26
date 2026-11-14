# Engineer workspace (spec, frontend v1)
Status: draft, 2026-11-14, by fe-spec-engineer; Vellum redesign (round 2, design screen 4 "Ask, with proof",
`Workspace.dc.html`) added 2026-11-14 by fe-vellum-engineer; 13:45 "Opening at a question or a place" (`?ask=`, `?page=&box=`, EN-72..EN-78) for the issues list: Layout, the "Vellum" API rows, EN-54..EN-71, "Not in the API"; built 2026-11-14 with orch D61 (viewer `meta` prop, arrows outside the viewer) and Bogdan's triage of the missing fields (#14 c6874945888, "Pending fields (mocked)").  Story: #33.  API: docs/API.md (v1, main 5092dc3), plus the
pending `confidence` object (Open point 1).

## Purpose

The engineer opens one drawing, asks a question in plain words and gets one number with its proof: the numbered
marks or shaded rooms on the page, the counting rule and what it left out, the second method's value, the cost and
the time. A question the drawing cannot answer is refused with the reason and questions it can answer. A value a
surveyor signed off shows as verified. Mock: `demo/` screen 2 (`index.html#work/engineer/A`).

## Files owned

- `frontend/src/engineer/EngineerPage.tsx`: the route view `EngineerPage({projectId, drawingId, query})`, mounted by
  the shell with key = route path without query (shared.md); loads the drawing, holds the thread of asked questions.
  `query`: `ask`, `page` and `box` (section "Opening at a question or a place"); every other key is ignored.
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
9. From the issues list (issues.md) the user follows a link that opens this screen already asking an issue's
   question (`?ask=`), or with the drawing opened at an issue's place (`?page=&box=`); section "Opening at a
   question or a place".

## API calls

### `GET /api/drawings/{drawing_id}?project=<project_id>` (API.md "Drawings")

Called once when the route opens (and again when `drawing_id` in the route changes), always with `project` = the
route's project id (client: `getDrawing(drawingId, {project: projectId})`). A drawing is shared by content across
projects; with `project` its `file` and `reader.source` are the names this project uploaded. A project that does not
hold the drawing answers 404 (the Drawing error state). Fixture: `drawing.json`.

| Field | Drives |
| --- | --- |
| `file` | the header title and the pending line "Reading <file>…" |
| `reader.route`, `reader.source`, `reader.extractor`, `reader.second_counter`, `reader.question_parser` | the header's "How it was read" line: `<route> route, read from <source> by <extractor>; second count where a question has one: <second_counter>; questions: <question_parser>` (the drawing's counter; a question it does not count says "no second count" in its answer, preqa-b), each reader id shown by the shared `readerName()` (`pdf` "PDF vector reader", `composite` "image reader", `ifc` "IFC model", `templates` "question templates"): "vector route, read from plans/flat-a.pdf by PDF vector reader; second count where a question has one: IFC model; questions: question templates". An `extractor` of `hello` reads "not read (no reader for this route yet)" instead of `by hello`. A `second_counter` of `none` (no second count ran) reads "no second count" instead of `second count: none`. |
| `pages` | the viewer before the first answer (page 1, no marks). `[]`: no viewer; the header says "Building model: no sheet to draw on." |
| `credit` | passed to the viewer, which places the shell's `<Credit>` under the page; null shows "Credit: none recorded for this file" |
| `suggestions[].question` | one button each, text = `question`; click asks it |
| `suggestions[].label` | the button's `title` (tooltip) |

### `GET /api/projects/{project_id}` (API.md "Projects and ingest"), Vellum

Called once when the route opens, with the shared client's `getProject(projectId)`, in parallel with the drawing
(it does not block the screen: until it arrives, or if it fails, the page meta shows no position, no arrows and no
"Original file" reference). Not polled. Fixture: `project.json`.

| Field | Drives |
| --- | --- |
| `drawings[]` (order as sent) | the position "<i> / <n>" (i = 1-based index of the entry whose `drawing_id` is the route's) and the "Previous drawing" / "Next drawing" arrows: links to the neighbour entry's engineer route (`routeHref`, wrapping round). One drawing: no arrows, no position. Route drawing not in the list: no position, no arrows |
| `drawings[i].kind`, `drawings[i].route` | the viewer's `meta` prop (D61: appended to its page meta line): "<kind words> · <route> route" (`pdf_vector` "PDF vector", `pdf_scan` "PDF scan", `png_plan` "PNG plan", `jpeg_plan` "JPEG plan", `photo_plan` "photo of a plan", `ifc` "IFC model", `dxf` "DXF", `svg` "SVG", other ids as sent; `route` null: "not routed") |
| `drawings[i].other_renderings[].file`, `.drawing_id` | "Also as <file>" above the plan (left of the position): links to that drawing's engineer route, comma separated; an entry with the route's own drawing id is skipped |
| `files[]` with `drawing_id` = route drawing id and `path` = `reader.source` | its `id` gives the "Original file" reference's picture: `previewUrl(projectId, file.id)` (the upload as the user sent it). No such file: that reference shows without a button (text only) |

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
| `line.sure`, `confidence.score` | the "Grade" block (Bogdan's rule, #14 c6874945888): `line.sure === true` "High"; else with `confidence` "Medium" when the score is 0.8 or more, "Low" below; no `confidence` and not sure: no block. Pill (`.v-pill--ok/--warn/--danger`), a 3-step bar (`aria-hidden`), and the line "From the Sure check and the second reader's score (0.8 or more: Medium)." Labelled "Grade", never "Confidence" (D3: the score is not a confidence) |
| `confidence.signal` | only in Details: "Signal: <signal>" (an internal name, never on the card itself) |
| `quantity.label`, `quantity.noun` | the answer sentence (Vellum: no separate card title), composed, not mocked (#14 c6874945888): with a noun "There are **<value>** <noun>." ("There is 1 door." for 1), else "<Label>: **<value>**."; the noun also right after the big value (outside `answer-value`). `noun` is in the API since PR #120 (`answer.json` "doors"; null for areas) |
| `check.reason` (coming, #14 c6875035654; shape not final, not in the types yet) | when present: a warning line right under the value row (`role="status"`, `--v-warn` on `--v-warn-soft`, `data-pending="AnswerView.check"`); absent or null: nothing. No mock; the disputed marks wait for the final shape |
| `pages[].storey`, `pages[].scale_text` (PR #120) | not read here: the viewer prints them in its own page line (orch decision 11:30, no double "1:100"); this screen's `meta` stays "<kind> · <route> route" |
| `quantity.key` | "Query: <label>" in the details shows `quantity.label`; the key only when the label is empty (EN-27) |
| `line.sure` (backend #98: the answer_v1.1 line's `sure`; optional, `true`/`false`/null; not a top-level field) | `true`: a small "Sure" badge right after the value; its tooltip (`title`) and its screen-reader text say "Certified: on held-out test plans, at least 96% of the plans marked sure had every sure answer exact". `false`, null or absent: nothing. `true` only where the golden certified gate covers the question family; null for IFC, vector and rooms answers |
| `quantity.status` | the status in words (table in States); never colour alone |
| `quantity.rule.text`, `quantity.rule.id` | "Counting rule: <text>", the id in small text |
| `quantity.first`, `quantity.second`, `quantity.conflict`, `quantity.needs_person`, `quantity.settled`, `quantity.estimate`, `quantity.original_value`, `quantity.signed` | the checks panel; measuring methods (`second.method`, `conflict.values[].method`: API ids such as `polygon_x_scale`) shown by the shared `methodName()`, never raw; the Details "Method: <method>" line (the answer's `takeoff`/`schedule`/`refused:…`) stays as sent (States) |
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
| `refusal.text`, `refusal.can_answer[]` | the refusal turn (States). `refusal.code` is not shown: the text explains the refusal (error views keep their codes) |
| `method`, `explanation` | the details (collapsed by default): "Method: <method>", "How: <explanation>" when not null. A misspelt question's `explanation` starts with how it was read (backend #80): "read 'mnay' as 'many'" (several joined by ", "), then "; " and the answer's own explanation when it has one. The How line shows it in full, as text, and wraps at 390 px (long words break: `overflow-wrap: anywhere` from the page). The note is also on the card itself (R2-2-1: the typo reader can rewrite a real word into another question): when `explanation` starts with `read '`, its text up to the first `; ` (or all of it) shows right under the question bubble, first letter capitalised, quotes kept ("Read 'mnay' as 'many'"), on answers and on refusals |
| `reader` | "Where this came from": `<extractor>` read `<source>` (`<route>` route), second count by `<second_counter>`, the reader ids through `readerName()` ("PDF vector reader read plans/flat-a.pdf (vector route), second count by IFC model"); with `second_counter` `none`: "…(vector route), no second count" |
| `cost_usd`, `latency_s` | the card footer: "Cost $0" / "Time 0.2 ms" (format below) |
| `drawing_id`, `file` | footer "Drawing <file>"; links |

Not used: `line` (the scorer's copy, it can hold the dev prior's estimate on a refusal: never shown, see Out of
scope), `proof.confidence` (same value as `confidence`), `quantity.unlocated` (the legend's `note` says it in words,
drawn by the viewer). The viewer's other props: `file` = drawing `file`, `pages` = `answer.pages`, `credit` =
drawing `credit` (the answer has none), `highlighted` = the hovered or focused mark-list row's id, `selected` /
`onSelect` = the selected mark, `onHover` = highlight its list row; `onPick` is never set here.

### `GET /api/drawings/{drawing_id}/pages/{n}.png?width=` (API.md "Drawings")

Requested by the viewer, not by this screen (viewer.md picks the width).

### `GET /api/drawings/{drawing_id}/evidence.png?question=&width=1600&project=<project_id>` (API.md "Answering")

Not fetched by the screen: the "Picture of this answer" link's `href`, built by the shared client's
`evidenceUrl(drawing_id, question, {project: projectId})` (shared.md; `question` encoded by `encodeURIComponent`;
`project` = the route's project id, since review edits and sign-offs are per project (backend #90) and the picture
must show this project's), `target="_blank"`,
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
| Refused | `answer_refused.json` | bold "I can't answer that from this drawing.", `refusal.text` (no code line), one button per `can_answer[].question`; no number, no viewer marks, no "Send to surveyor", no picture link |
| Answer, count | `answer.json` | value `2`, title "door count", viewer with marks 1 and 2, mark list "1 door", "2 door", rule "every element, room and plan the drawing lists counts once", status "One method" |
| Answer, sum | `answer_area.json` | value `52.27 m²`, rooms shaded, mark list with "Küche 22.40 m²"…, the arithmetic line with what was left out, the viewer's colour key |
| Answer with a model score | `answer_confidence.json` (`confidence: {"signal": "g1main", "score": 0.87, "calibrated": false}`) | as count plus "Second reader's score 0.87 (not a probability)"; Details has "Signal: g1main"; no "Picture of this answer" link |
| Answer, building model | `answer_model.json` | value `2`, no viewer; `ModelProof` with "Door 1", "Door 2", their storey and GlobalId, the storey table, the arithmetic line |
| Answer, schedule | see Open points (no fixture yet) | the string answer, the schedule table, no rule or checks panel |
| Verified | derived: `answer.json` with `quantity.status: "signed"`, `quantity.signed: {"by": "Ana", "at": "2026-11-14T01:40:00Z", "value": 2}` | status "Verified", "Verified by Ana, 2026-11-14 01:40 UTC" next to the value |
| Methods disagree, rule decides | derived: `answer.json` with `quantity` = `takeoff.json` `quantities[0]`, `answer` 30.0, `unit` "m2" | status "Methods disagree"; both values "22.40 m² by <methodName(polygon_x_scale)>", "30.00 m² by <methodName(printed_label)>"; "Kept 30.00 m²: the printed label over the outline at the sheet's scale" |
| Methods disagree, nobody decided | the above with `conflict.resolution: null`, `needs_person: true` | as above, and instead of "Kept": "No rule decides. A surveyor has to settle it before this value can be used." |
| Methods agree | derived: `answer.json` with `status: "agree"`, `first: {"method": "plan_drawing", "value": 2}`, `second: {"method": "ifc_model", "value": 2}` | status "Two methods agree"; "Second method (<methodName(ifc_model)>): 2, agrees" |
| One method | `answer.json` (`first`/`second` null) | "Measured by one method; no second check." |
| Estimate | derived: `answer.json` with `status: "estimate"`, `estimate: "scale estimated from a door width"` | status "Estimate"; "Estimate: scale estimated from a door width"; with `first`/`second` null "Estimated by one method; no second check." |
| Edited in review | derived: `answer.json` with `status: "edited"`, `value`/`answer` 1, `original_value` 2, mark m2 `state: "rejected"`, `n: null` | status "Changed in review"; "Changed in review, was 2"; mark list row "× door rejected by a surveyor" |
| Settled | derived: conflict case with `settled: {"value": 22.401, "at": "2026-11-14T01:30:00Z"}` | "Settled by a surveyor at 2026-11-14 01:30 UTC: 22.40 m²" |
| Excluded item | derived: `answer_area.json` with one more mark `{"id": "x1", "n": null, "state": "excluded", "reason": "outdoor room", "label": "Balkon", …}` (box/polygon copied from m2) | mark list row "– Balkon left out by the rule: outdoor room" |
| No-keys | `info.json` (`no_keys: true`) | the shell's "running offline" banner shows on this route (shared.md) |
| Opened with a question | `#/p/<pid>/d/<did>/engineer?ask=How%20many%20doors%20are%20there%3F` | after loading, the thread already has that question's turn (pending, then its answer or refusal); no opening card |
| Opened at a place | `…/engineer?page=1&box=0.49,0.22,0.51,0.28` | the opening card's viewer on page 1, zoomed or scrolled to that box, outlined (viewer.md `focus`) |

Status words (`quantity.status`): `signed` "Verified", `conflict` "Methods disagree", `estimate` "Estimate",
`edited` "Changed in review", `agree` "Two methods agree", `single` "One method".

## Opening at a question or a place

Added 2026-11-14 13:45 by fe-engineer for #139/#140 (brief `fe-checks-issues.md`, decision #142): the issues list
reopens a refused question and jumps to an issue's place. Read once when the screen mounts (the shell remounts it
on a new route path; another issue's link always comes from another route). The URL is left as it is, so a reload
does the same again: the link is the question or the place.

**`?ask=<question>`** (a `refused_answer` issue whose `drawing_id` is set; `Issue.question` verbatim):
- After `GET /api/drawings/{id}` succeeds, the question is asked exactly as if typed: one turn, one
  `POST /api/ask` `{drawing_id, question, project_id}`, the same answer, refusal or error card. Exactly one request
  per mount (also under React StrictMode's double effects).
- The value is trimmed; empty or whitespace-only: nothing is asked (the empty thread shows). Not shortened and not
  checked against `limits.question_chars`: the backend's 422 shows as the ask error turn (never invent or cut a
  question).
- Not asked when the drawing fails to load (the error view shows). The ask box is free right after, as usual.
- Named `ask`, not `q`: on the workspace routes `q` is the surveyor's takeoff row key (surveyor.md, SH-3), and the
  shell's Surveyor tab keeps the query (`routeHref({ ...route, role: 'surveyor' })`), so a question in `q` would
  reach the surveyor as a row key (and a surveyor's row key would be asked as a question). With `ask`, the surveyor
  ignores it.

**`?page=<n>&box=<x0>,<y0>,<x1>,<y1>`** (an issue with `page`, and `box` when it has one; page fractions as
`MarkView.box`, the page 1-based as `PageView.page`):
- `page` must be a whole number ≥ 1, else both keys are ignored (the drawing opens as without them). A page the
  drawing does not have is passed on: the viewer stays put and says where the place is (viewer.md "Focus").
- `box`: four comma-separated finite numbers with `0 ≤ x0 ≤ x1 ≤ 1` and `0 ≤ y0 ≤ y1 ≤ 1`, else `box` is null
  (the page still opens: a sheet-level issue). A `box` without a valid `page` is ignored (#142 ask 9: box ⇒ page).
- Passed to the opening drawing's viewer (the empty-thread card) as `focus={{ page, box }}` (viewer.md
  `focus?: {page, box?: number[] | null} | null`, VW-76/77): the viewer opens that page and zooms or scrolls to and
  outlines the box; with `box` null it only switches the page. Marks stay `[]`.
- Only the opening card gets it: after the first question that card goes (as now), and answer cards open as usual.
- A building model (no pages): ignored, the screen shows "Building model: no sheet to draw on." as now.
- With `ask` too, the question is asked and the place is not shown (the turn replaces the opening card); an issue
  link carries one or the other.
- The prev/next drawing arrows and "Also as" links carry no query (as now): the place belongs to this drawing.

Builders of these links (fe-ingest, fe-surveyor): `routeHref({ name: 'workspace', projectId, drawingId,
role: 'engineer', query: new URLSearchParams({ ask }) })`, or `{ page: String(page), box: box.join(',') }`
(`URLSearchParams` encodes the commas; both forms parse). A `refused_answer` with `drawing_id` null (a project
ask) links to the chat instead (chat.md `?ask=`).

**Not a key:** `?mark=<id>`: the opening card shows no marks, so there is nothing to select, and a mark id alone
names no place (ids repeat across takeoff rows: `takeoff.json` has `m1` in three). Selecting the issue's mark is
the surveyor's job: `Issue.quantity` (takeoff `Row.key`) + `Issue.mark_id` (#142 c6876010899) fit
`#/p/<pid>/d/<did>/surveyor?q=<quantity>` (surveyor.md). Every located issue carries `page` + `box`; `Issue.polygon`
is not used here, since `focus` takes a box.

## Layout

Vellum redesign (design screen 4, `Workspace.dc.html`; tokens `--v-*` from shared.md, no other colours; system font
stack, no web fonts; the design's mock values are never shown). The shell draws the header (shared.md); this screen
draws no header, no country picker, no rules footer line and no "Edit a house plan from a photo" (+) button.

Desktop 1440x900: one centred column, max 1040 px, padding 32 px 24 px, sections 24 px apart, on `--v-bg`.

- **Before the first answer** (empty thread): the plan card (below) with the drawing's page and no marks, full
  column width, without the right-hand column; under it the "How it was read" line (small, `--v-muted`), then the
  suggestion chips row, then "Ask a question about this drawing.".
- **The thread** (`<section aria-label="Chat">`), turns 20 px apart, newest at the bottom. Each turn is an
  `<article aria-label="<question>">`:
  1. The question bubble, right-aligned, max 70 % wide, `--v-accent` background, white text, radius 20 20 6 20.
  2. The read-as note when there is one ("Read 'mnay' as 'many'"), small, `--v-muted`, right-aligned under the
     bubble.
  3. The answer sentence (17 px, max 62ch): "<Label>: **<value>**." (`quantity.label` with its first letter
     capitalised, the formatted value in `<strong>`), then the counting rule's text as the second sentence when
     there is a rule. Schedule (no `quantity`): "**<answer>**." only. Building model: as count.
  4. The answer card: shared `.v-card` (`--v-surface`, `--v-radius`, `--v-shadow`) with padding 0 and
     `overflow: hidden`; a two-column
     grid `minmax(0,1.4fr) minmax(0,1fr)`, one column below 900 px.
     - **Left, the plan** (`<figure aria-label="Drawing">`, padding 20 px, background `--v-bg`, gap 12 px):
       - Place row (only when the project gives it): "Also as …" links (12 px, `--v-muted`) on the left, the
         position "<i> / <n>" (13 px, tabular numbers, `aria-live="polite"`) on the right. The file name and the
         page meta line (with "<kind> · <route> route" from the `meta` prop) are the viewer's own (D61, viewer.md);
         this screen draws no file-name line of its own.
       - The plan: `PageViewer` (viewer.md) with the answer's pages and marks, inside a `position: relative` box.
         "Previous drawing" and "Next drawing" (D61: outside `PageViewer`, in this screen's wrapper) are round 44 px link buttons (`<a>` with that `aria-label`, chevron
         icon `aria-hidden`) over the left and right edge of the plan, vertically centred, `color-mix(in srgb, var(--v-surface) 85%, transparent)`
         with `--v-shadow`.
       - The overlay (when a reference is opened): a `role="dialog"` sheet covering the plan box (inset −8 px,
         radius 14 px, `--v-shadow`), `aria-label="<what>: <file>"`; a bar with the reference number tag, the
         file (monospace) and its "where" line, and a round 36 px "Close" button (`aria-label="Close the
         original"`); below it the picture (`<img>` with an `alt` naming the file and what it shows,
         `object-fit: contain`). Esc and the close button close it; focus goes to the close button when it opens
         and back to the reference chip when it closes. One overlay at a time; opening another reference
         replaces it; the chip of the open reference has `aria-pressed="true"`.
       - The mark list (numbered rows as today, `n` in an accent number tag like the design's reference tags) and
         the arithmetic line under the plan; the viewer's own legend is the figcaption (viewer.md).
     - **Right, the answer** (padding 20 px 22 px, gap 16 px):
       - The value row: the value (44 px, 700, tabular numbers, `data-testid="answer-value"`, text exactly the
         formatted value) and the "Sure" badge when `line.sure` is true (EN-53), baseline aligned, wrapping.
       - "Grade" block (only when there is a grade, see the `line.sure`, `confidence.score` row): "Grade"
         (13 px, 600) with the grade pill on the right, the 3-step bar, the source line (13 px, `--v-muted`).
       - "Checks" block: the label "Checks" (13 px, 600) with the status pill on the right (shared `.v-pill`
         with the status words: `.v-pill--ok` for `agree`/`signed`, `.v-pill--warn` for `conflict`/`estimate`/
         `edited`, plain `.v-pill` for `single`; text always, never colour alone); the pill is focusable (`tabindex="0"`) and has a tooltip
         (`role="tooltip"`, shown on hover and focus, `aria-describedby` from the pill) with the status
         explanation (table "Status tooltips"; 12.5 px, `--v-surface` text on `--v-text`, radius 10 px, max 240 px); under it the checks panel lines (ChecksPanel as today), the
         score line "Second reader's score 0.87 (not a probability)" when there is a score, "Verified by …" when
         signed. The word "Confidence" is never shown.
       - "Counting rule: <text>" (14 px) with the rule id in small text.
       - "References" (13 px, 600) and an ordered list of reference chips (button, full width, radius 12 px,
         min 44 px tall, `--v-fill` background, `--v-accent-soft` when pressed): each has a number tag (1, 2, 3 …, accent), the file in monospace
         and a "where" line (12 px, `--v-muted`). The rows are, in this order, each only when its data exists:
         1. "Original file": `reader.source`; where = the "Where this came from" sentence (`cameFrom`, EN-26
            text unchanged). Opens the overlay with the upload's preview (`previewUrl`), when the project's
            `files[]` gives its id; otherwise a plain row (no button).
         2. "Proof drawn by the server": `file`; where = "Page <p> · marks <first n>–<last n>" (pages of the
            marks; "no marks" when there are none). Opens the overlay with `evidence.png` (`evidenceUrl(...,
            {project})`); only when `confidence` is null (same rule as the picture link: the image still prints
            the old probability line); otherwise a plain row.
         3. "Second count": the second method's name and value ("<methodName(second.method)>: <value>"), or for
            a conflict both values ("<value> by <method>; …"); with no `second` and no `conflict`: "no second
            count". Plain row: the second method has values, not positions (#14 c6874945888). No per-reference
            grade on any chip (not in the API, not triaged).
     - **Footer row** (as today, under the grid, `--v-line` top border, 12 px muted): Drawing, Cost, Time,
       "Details" (Query, Method, Signal, How), "Picture of this answer", "Send to surveyor".
  5. A refusal turn: the bubble, the read-as note, then a card (`--v-surface`, radius, padding 20 px) with bold
     "I can't answer that from this drawing.", `refusal.text`, and the `can_answer` questions as chips. No plan.
  6. An error turn: as today (detail, code, "Try again"), in a `.v-card` with `--v-danger` text.
- **Suggestion chips** (`drawing.suggestions`; hidden while the newest turn is a refusal, whose card offers its
  own `can_answer` chips, EN-60): one row of chips (radius 980 px, 14 px, min 44 px tall,
  `--v-fill`, hover `--v-accent-soft`, wrapping) after the thread, outside every article (a refusal's `can_answer` chips are inside
  its article, so the same question can be in both without two buttons in one turn). Before the first answer the
  row sits under the plan card. The "Suggested questions" `<details>` fold is gone.
- **Ask box** (amended 11:40, golden 06/07: the plan's legend and mark rows read through the glass pill): a pill
  on a solid `--v-bg` band sticky at the bottom (`bottom: 0`, padding 6 px 0 10 px; content scrolls behind the band,
  never shows through it), the pill `--v-surface` (no transparency, no blur), radius 980 px, padding 6 px,
  `--v-shadow`. The input keeps the accessible name "Question" (visually hidden label) and the placeholder
  "Ask about <file>"; the Ask button is a round 44 px `--v-accent` button with an up-arrow icon and
  `aria-label="Ask"`. "<n> asked · <len> / <limit>" (12 px, `--v-muted`) sits inside the pill before the button
  on desktop, centred under the pill at ≤900 px.
- **Scrolling under the site header:** a turn scrolled into view stops `var(--v-header-h) + 8px` from the top
  (shared.md: 76 px while the header is sticky, 0 on the phone), so the opaque header never covers the bubble.
- **Plan column padding:** the viewer pads itself (viewer.md, 20 px / 16 px), so the left column adds no padding
  above or beside it; the position and "Also as" row sits over the right end of the viewer's file-name row on
  desktop and in flow above it at ≤900 px.

Motion: press feedback by the shared `.v-press` (scale 0.97, 100 ms) on chips and buttons; the overlay opens with opacity and
scale 0.97 → 1 in 220 ms; both off under `prefers-reduced-motion`.

Phone 390x844: same order, one column, 16 px gutters; the card's grid is one column (plan, then the answer); the
arrows stay on the plan's edges; the overlay covers the plan box only; the "Sure" badge wraps under the value when
the line is full; the footer wraps; the ask box sticks to the bottom; tap targets at least 44 px; no horizontal
scroll (file paths and keys wrap, `overflow-wrap: anywhere`). Table cells (the building model's objects and
storeys) never break inside a word (`overflow-wrap: normal`, `word-break: normal`); a table wider than the column
scrolls sideways inside its own wrapper.

Status tooltips (the pill's tooltip text):

| `quantity.status` | Pill | Tooltip |
| --- | --- | --- |
| `signed` | Verified | A surveyor checked this value and signed it off. |
| `agree` | Two methods agree | Two independent methods measured this and got the same value. |
| `conflict` | Methods disagree | Two methods measured different values; the checks below say which one is kept and why. |
| `estimate` | Estimate | Measured with an estimated scale or method; treat it as approximate. |
| `edited` | Changed in review | A surveyor changed this value in review. |
| `single` | One method | Only one method measured this; there is no second check. |

## Acceptance criteria

Fixtures are `backend/tests/fixtures/api_v1/*.json`, imported read-only. "Derived" fixtures are those files with the
named fields overridden in `testing.ts` (a spread over the imported object), never a hand-written whole response.
The API is mocked with the shared `mockApi` helper (shared.md) in component tests.

Drawing header and ask box
- EN-1 Opening the route calls `GET /api/drawings/<drawing_id>` once with the id from the route. [component, `drawing.json`]
- EN-2 While that request is pending, the shared loading view shows and no ask box is rendered. [component, pending fetch]
- EN-3 A 404 shows the shared `ErrorView` with "no drawing 0123456789abcdef" and "not-found", and a link to `#/p/<project_id>`. [component, `error.json` 404]
- EN-4 (Vellum: the page meta shows the file, the "How it was read" line sits under the plan card before the first answer) The header shows "plans/flat-a.pdf" and "vector route, read from plans/flat-a.pdf by PDF vector reader; second count where a question has one: IFC model; questions: question templates"; with `second_counter: "none"` it shows "vector route, read from plans/flat-a.pdf by PDF vector reader; no second count; questions: question templates". No raw reader id (`pdf`, `ifc`, `templates`) shows. [component, `drawing.json`, derived `drawing.json`]
- EN-5 With `reader.extractor: "hello"` the header says "not read (no reader for this route yet)" and does not say "by hello". [component, derived `drawing.json`]
- EN-6 One button per suggestion, labelled with its `question`, in order: "How many doors are there?", "How many windows are there?", "How many toilets are there?". [component, `drawing.json`]
- EN-7 With `suggestions: []` the screen shows "No ready questions for this drawing." and the ask box. [component, derived `drawing.json`]
- EN-8 Before any question the viewer shows page 1 with no marks and the text "Ask a question about this drawing." shows. [component, `drawing.json`]
- EN-9 Clicking a suggestion sends `POST /api/ask` with body `{"drawing_id": "adeefbbcc17559fc", "question": "How many doors are there?"}`. [component, `drawing.json`]
- EN-10 Typing "  How many doors are there?  " and pressing Enter sends the trimmed question; an empty or whitespace-only input sends nothing and Ask is disabled. [component]
- EN-11 With `limits.question_chars` 2000, a 2001-character question disables Ask and shows "Questions are at most 2000 characters."; 2000 characters is allowed. [component, `info.json`]
- EN-12 While an ask is pending the turn shows the question and "Reading plans/flat-a.pdf…", Ask is disabled, and a second Enter sends nothing. [component, pending fetch]

Answers
- EN-13 A count answer shows the value "2" in the card, the sentence "There are 2 doors. Every element, room and plan the drawing lists counts once." (Vellum; was the title "door count"; the noun is the `Row.noun` mock until the backend sends it), and no unit text. [component, `answer.json`]
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
- EN-26 (Vellum: the sentence is the where-line of reference 1, "Original file"; the heading is "References") "Where this came from" shows "PDF vector reader read plans/flat-a.pdf (vector route), no second count" for `answer.json` (`second_counter: "none"`), and "PDF vector reader read plans/flat-a.pdf (vector route), second count by IFC model" with `second_counter: "ifc"`. [component, `answer.json`, derived `answer.json`]
- EN-27 "Details" is collapsed by default, its summary in the footer row with Drawing, Cost and Time (the row aligns items on the baseline); opened it shows "Query: door count" (the quantity's printed `label`, e.g. "Query: area of room (indoor)", never the internal key like `area:room|indoor`; the key only when the label is empty) and "Method: takeoff"; with `explanation` null no "How:" line. [component, `answer.json`, `answer_area.json`]
- EN-28 A building-model answer shows no viewer; it shows a table with "Door 1", "Ground floor", "000000000000000000000K", a storey table row "Ground floor" with door 2, window 3, and the line "2 door objects in the model on Ground floor". Each table sits in a wrapper that scrolls sideways (`overflow-x: auto`), and its cells do not break inside words (`overflow-wrap: normal`, `word-break: normal`). [component, `answer_model.json`]
- EN-29 "Picture of this answer" links to `/api/drawings/adeefbbcc17559fc/evidence.png?question=How%20many%20doors%20are%20there%3F&width=1600&project=5e0c1a2b3d4f` (the route's project) and opens a new tab when `confidence` is null; with the `confidence` object set there is no "Picture of this answer" link. [component, `answer.json`, `answer_confidence.json` or its derived form]
- EN-30 "Send to surveyor" links to `#/p/<project_id>/d/adeefbbcc17559fc/surveyor?q=door` (built with the shared `routeHref`; derived conflict: `?q=area%3Aroom%7Cname%3D1.01`), surveyor.md Open point 4. Absent when `quantity` is null. [component, `answer.json`, derived conflict]

Checks and review state
- EN-31 Each status shows its word: signed "Verified", conflict "Methods disagree", estimate "Estimate", edited "Changed in review", agree "Two methods agree", single "One method". [component, `answer.json` and its derived variants]
- EN-32 A signed answer shows "Verified by Ana, 2026-11-14 01:40 UTC" next to the value. [component, derived signed `answer.json`]
- EN-33 A conflict shows both values with their methods' plain names from the shared `methodName()`, "22.40 m² by <methodName("polygon_x_scale")>" and "30.00 m² by <methodName("printed_label")>", never the raw ids, and "Kept 30.00 m²: the printed label over the outline at the sheet's scale". [component, derived conflict]
- EN-34 With `conflict.resolution` null and `needs_person` true it shows "No rule decides. A surveyor has to settle it before this value can be used." and no "Kept" line. [component, derived conflict]
- EN-35 `status: "agree"` shows "Second method (<methodName("ifc_model")>): 2, agrees" (not the raw id); `first`/`second` null shows "Measured by one method; no second check.", or "Estimated by one method; no second check." when `estimate` is set. [component, derived agree, `answer.json`]
- EN-36 An estimate shows "Estimate: scale estimated from a door width" and, measured once, "Estimated by one method; no second check." (not "Measured by …"). [component, derived estimate]
- EN-37 An edited answer shows "Changed in review, was 2" and the rejected mark row "× door rejected by a surveyor"; an added mark (derived: `{"id": "a1", "n": 3, "state": "added", "label": null, "ref": null, "polygon": null, …}`) shows "+3 item added by a surveyor". [component, derived edited]
- EN-38 A settled value shows "Settled by a surveyor at 2026-11-14 01:30 UTC: 22.40 m²". [component, derived settled]

Refusals and errors
- EN-39 A refusal shows "I can't answer that from this drawing.", the text "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.", no "code:" line and not the code "unsupported-question", and no number, marks, picture link or takeoff link. [component, `answer_refused.json`]
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
- EN-51 The read-as note is visible on the card without opening Details: with `explanation` "read 'mnay' as 'many'; the scale is estimated from a door width" the turn shows "Read 'mnay' as 'many'" under the question, before the value, while Details stays closed; with only the note it shows the same; a refusal whose `explanation` starts with the note shows it too. With `explanation` null, or one that does not start with `read '`, no note shows. Details keeps the full line: "How: read 'mnay' as 'many'; the scale is estimated from a door width" (or "How: read 'mnay' as 'many'"). [component, derived `answer.json`, derived `answer_refused.json`; the 390 px wrap: fe-golden's browser check]
- EN-52 (Vellum: the "Suggested questions" fold is gone, EN-60; the footer part stays) The footer's "Details" summary keeps the browser's disclosure marker (its `display` is `list-item`, as the shell's "What runs"). [component, `drawing.json` + `answer.json`]
- EN-53 With `line.sure: true` (derived `answer.json`) the card shows a "Sure" badge after the value, outside the `answer-value` element (so the value text stays "2"); the badge's `title` is "Certified: on held-out test plans, at least 96% of the plans marked sure had every sure answer exact" and the same sentence is in its text for screen readers (visually hidden); with `line.sure` null (`answer.json`), `false` or absent, no badge. At 390 px the badge fits without horizontal scroll (the value row wraps). [component, derived `answer.json`; the 390 px fit: EN-45's e2e check covers the page, the badge row wraps by `flex-wrap`]

[e2e] criteria are built by the e2e worker (golden-path.md); this spec's build worker writes no file in `frontend/e2e/`.

- EN-54 Vellum layout: with `answer.json` the turn shows, in order, the bubble, the answer sentence "Door count: **2**." with the counting rule's text after it, then the card whose left column is `<figure aria-label="Drawing">` (page meta, viewer, mark list) and whose right column has the value `2`, "Checks" with the pill "One method", "Counting rule: …", "References". No element shows "Confidence", "Finland", "Switzerland" or a person's name, and with `answer.json` (not sure, no score) no grade ("High", "Medium", "Low"). [component, `answer.json`]
- EN-55 Page meta: with `project.json` (route drawing `adeefbbcc17559fc`) the figure shows "PDF vector · vector route" (the viewer's `meta`), "Also as plans/flat-a.png" ("plans/flat-a.png" a link to drawing `c9b719f715357201`'s engineer route) and the position "1 / 5" (`aria-live="polite"`). [component, `project.json` + `drawing.json` + `answer.json`]
- EN-56 (preqa-b: also on a building model before the first answer, on a model answer card and on a refusal card, as a `<nav aria-label="Drawings">` row with the position) Previous/next drawing: "Next drawing" links to the engineer route of `drawings[1]`, "Previous drawing" to the last entry's (`1db9bcf1e67e27a3`, wrap round); with one drawing in the project, or before `GET /api/projects/{id}` answers, or when it fails, neither link nor position shows and the rest of the screen works. Both are at least 44x44 px. [component, `project.json` and derived one-drawing `project.json`; size: e2e]
- EN-57 Status pill: each status (table "Status tooltips") shows its pill words and, on focus of the pill, a `role="tooltip"` with its tooltip text, linked by `aria-describedby`. [component, `answer.json` and the derived fixtures of States]
- EN-58 References with `answer.json` and `project.json`: three chips in order, "1 … plans/flat-a.pdf" whose where-line is the EN-26 sentence, "2 … plans/flat-a.pdf … Page 1 · marks 1–2", "3 … no second count". Chips 1 and 2 are buttons; chip 3 is not. With `answer_confidence.json` chip 2 is not a button. Without a matching file in `project.files`, chip 1 is not a button. [component]
- EN-59 Overlay: clicking chip 1 opens a `role="dialog"` named "Original file: plans/flat-a.pdf" over the plan with an `<img>` whose `src` is `previewUrl(projectId, "f1")`; chip 1 is `aria-pressed="true"`; focus is on "Close the original". Esc closes it and focus returns to chip 1; clicking chip 2 instead shows `evidenceUrl(drawing_id, question, {project})`. Only one dialog exists at a time. [component]
- EN-60 (amended 12:20, orch: testers saw the same six questions twice after a refusal) Suggestion chips sit after the thread, outside every article, except while the newest turn is a refusal: then the refusal card's `can_answer` chips are the only ones, so after `answer_refused.json` each `can_answer` question is exactly one button on the page (inside that turn) and no "Suggested questions" group shows; the next answer brings the row back after the thread. No "Suggested questions" `<details>` exists. [component, `drawing.json` + `answer_refused.json` + `answer.json`]
- EN-61 Ask box: the input's accessible name is "Question", its placeholder "Ask about plans/flat-a.pdf"; the submit button's name is "Ask"; Enter and the button ask (EN-10 unchanged). No link to "Edit a house plan from a photo". [component, `drawing.json`]
- EN-62 Refusal turn in Vellum: card with "I can't answer that from this drawing.", `refusal.text`, chips for `can_answer`; no figure, no value, no References, no footer. [component, `answer_refused.json`]
- EN-63 Only tokens: `engineer.css` has no colour literal (`#…`, `rgb(`, `hsl(`) except inside `var()` fallbacks; every colour is a `--v-*` token. [unit test reading the CSS file as text]
- EN-64 Reduced motion: under `prefers-reduced-motion: reduce` the press scale and the overlay animation are off (CSS rules present in `engineer.css` inside that media query). [unit test on the CSS text; visual: fe-golden]
- EN-65 Phone 390x844 with `answer_area.json`: the card is one column (figure above the answer), no horizontal scroll, the arrows and the ask button at least 44 px, the overlay inside the plan box. [e2e]
- EN-67 Grade (#14 c6874945888): `line.sure: true` (derived `answer.json`) shows "High"; `answer_confidence.json` (score 0.87, sure null) "Medium"; a derived score 0.5 "Low"; each with "From the Sure check and the second reader's score"; `answer.json` (no score, not sure) has no grade block. [component]
- EN-68 `Row.noun` (PR #120): `answer.json` shows "doors" after the value and in the sentence, with no `data-pending`; a derived `noun: null` shows no noun and "Door count: 2. …"; a sum (`answer_area.json`, noun null) keeps "Area of room (indoor): 52.27 m². …". [component]
- EN-69 A derived `answer.json` with `check: {reason: "Please double-check: …", disputed: []}` shows the reason in a `role="status"` line right after the value row, `data-pending="AnswerView.check"`; `answer.json` has no such line. [component]
- EN-55 (PR #120) With a derived page 1 `storey: "Ground floor"` the figure shows "PDF vector · vector route", and "Ground floor" and "1:100" each once (the viewer's page line). [component]
- EN-71 (golden 06/07) The ask box is a solid band: `.en-ask` has `background: var(--v-bg)`, and neither `.en-ask` nor `.en-askpill` uses `transparent` or `backdrop-filter`; `.en-turn` has `scroll-margin-top: calc(var(--v-header-h, 0px) + 8px)`. In the browser, after "How many doors are there?" on the sample's `plans/flat-b.pdf`, the plan's legend line ends above the ask band at 1440x900 and 390x844, and the bubble is below the site header. [unit on the CSS text; browser: fe-golden's screenshots 06/07]
- EN-72 `?ask=How many doors are there?`: after `drawing.json` loads, exactly one `POST /api/ask` with
  `{drawing_id, question: "How many doors are there?", project_id}` (also when rendered in `<StrictMode>`); the
  thread shows the article named by the question with `answer.json`'s value; the ask box is enabled after.
  [component, `drawing.json` + `answer.json`]
- EN-73 `?ask=` with `answer_refused.json`: the refusal card in that turn, its `can_answer` chips, as a typed
  question (EN-62). [component]
- EN-74 `?ask=` that is empty or only spaces asks nothing (no POST; the opening card shows); a drawing 404 asks
  nothing (the error view, no POST). [component, `error.json`]
- EN-75 `?q=How many doors are there?` (no `ask`) asks nothing: `q` stays the surveyor's row key. [component]
- EN-76 `?page=1&box=0.49,0.22,0.51,0.28` passes `focus={{page: 1, box: [0.49, 0.22, 0.51, 0.28]}}` to the opening
  card's `PageViewer` (the `%2C`-encoded form too); `?page=1` alone passes `{page: 1, box: null}`. [component with a
  `PageViewer` spy (`vi.mock`)]
- EN-77 Ignored places pass no `focus`: `page=0`, `page=1.5`, `page=x`, a `box` without `page`; `page=9` (not in
  the drawing) is passed on as `{page: 9, box: null}`;
  `box=0.6,0.2,0.5,0.3` (x0 > x1), `box=0,0,1` (three numbers), `box=0,0,1,1.2` (over 1) keep the page with
  `box: null`. A building model (`answer_model`-like drawing with no pages) ignores both. [component]
- EN-78 `?ask=` together with `?page=&box=`: the question is asked; no opening card (no `focus` rendered).
  [component]
- EN-66 The e2e names stay: `answer-value` test id, `article` named by the question, textbox "Question", button "Ask", "Mark <n>: …" badges (viewer), "One method", "Methods disagree", "I can't answer that from this drawing.", the suggestion buttons by question text. [e2e, golden-path run]

## Not in the API (Vellum design elements; Bogdan's triage #14 c6874945888)

| Design element | Field | Shown now |
| --- | --- | --- |
| Confidence "High/Medium/Low" pill and 3-step bar | `answer.grade`: NO (Bogdan): derive it | the "Grade" block from `line.sure` and `confidence.score` (EN-67), never called "Confidence" |
| Per-reference grade ("High", "Medium") with its tip | `answer.sources[].grade` (not triaged) | no grade on the chips |
| A natural answer sentence | `answer.text`: NO: compose it | "There are **2** doors." from `answer`, `noun`, `quantity.label` (EN-13) |
| A CAD layer view of the original with the read entities highlighted | `GET /api/drawings/{id}/original.png` (not triaged) | the upload's `preview.png`, no highlight |
| The second counter's own picture | `Row.second.boxes`: NO (values, not positions) | chip 3 as text, no overlay |
| The unit noun after the value ("doors") | `Row.noun: string\|null`: in the API (PR #120) | the real field; null: no noun |
| "Please double-check" note and disputed marks | `AnswerView.check: {reason, disputed[]}\|null` (coming, #14 c6875035654) | the reason when present (EN-69), no mock; no disputed-mark highlight yet |
| Country picker, rules line | country rules (fe-shared's picker, `data-pending="country-rules"`) | not on this screen |

## Pending fields (mocked)

None on this screen since PR #120 (`Row.noun` is real; `src/engineer/pending.ts` is deleted). `AnswerView.check`
is read when present but never mocked (its shape is not final); its line carries `data-pending="AnswerView.check"`.

## Out of scope

- Keeping the thread across reloads, or sharing it between people; a question on a whole project (API.md "What is
  not in v1").
- Drawing per-item contested (amber) marks: v1 shows a conflict per quantity with both values (API.md "What is not
  in v1").
- Showing `line` or the dev prior's estimate on a refusal: no silent guesses (REQUIREMENTS §5).
- A made-up confidence when `confidence` is null (the mock's confidence bars and percentages are invented); showing
  the model score as a probability or percent, or a "sure" cutoff (the score is uncalibrated).
- Editing marks, settling or signing off from this screen: the surveyor view does that.
- The mock's "Where this came from" list of several files per drawing: API v1 gives one `reader.source` (Vellum
  References show at most the three rows of Layout).
- Vellum: screens 6-8 (Edit my plan) and the ask box's "+" link to them; the country picker and rules line; the
  user avatar and name.
- A model-object 3D view, or fetching `GET /api/drawings/{id}/model`.
- `?mark=<id>` (section "Opening at a question or a place"), focusing a place inside an answer card, outlining
  `Issue.polygon` (the viewer's `focus` takes a box).

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
   on the role links, SH); recommend leaving it so for v1. Still true with the 13:45 addition: the engineer's
   question key is `ask` (EN-75).
8. **`ask` instead of the brief's `?q=`** (frontend-orch 13:30 asked for `?q=<question>`): `q` already means the
   takeoff row key on the same routes and crosses roles on the Surveyor tab (section "Opening at a question or a
   place"). Recommend `ask`. If `q` is kept instead, fe-shared must drop the query from the role tab and the
   surveyor's row keys can never reach the engineer: say which.
9. **`focus` prop** (resolved 13:44): viewer.md's `focus?: {page, box?: number[] | null} | null` takes a null box
   (page only) and handles a page the drawing lacks, so this screen only checks the URL's syntax.
7. **Viewer props for Vellum.** Decided (D61): `PageViewer` keeps `unit` and gains `meta?: string`; the arrows
   and the position are this screen's; the viewer shows the file name and no longer names itself "Drawing" (the
   left column's `<figure aria-label="Drawing">` does). The original proposal, kept for the record: This screen needs:
   (a) `caption?: boolean` (default `true`): `false` hides the viewer's file caption, since the page meta above the
   plan already names the file (the credit line stays); (b) numbered badges drawn as accent circles with white
   numbers (`--v-accent`), as the design, keeping the "Mark <n>: <label>, <words>" names; (c) the legend rendered as
   the figure's caption row (12 px, `--v-muted`, swatches 10 px). No other new prop: the arrows and the overlay are
   this screen's, positioned over the viewer by a wrapper. If (a) is refused the page meta drops the file name.
8. **Kind words** (`pdf_vector` "PDF vector", …): local to this screen unless fe-shared adds a shared
   `kindName()`; recommend shared, since the ingest screens show kinds too.
6. **One value formatter:** decided (round 1): shared.md owns `formatValue` and `formatTime` in `src/api/format.ts`;
   `engineer/format.ts` keeps cost, latency and score.
7. **The mock's per-answer sources and confidence bar.** The mock lists three source files per drawing and a
   confidence bar; v1 has one `reader.source` and no bar. The spec keeps the mock's card layout with what the API
   gives (Out of scope).
