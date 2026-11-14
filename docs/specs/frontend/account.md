# Workspaces and their history (spec, frontend Vellum)
Status: draft, 2026-11-14 11:15, by fe-spec-golden (fe-golden).  Story: #33.  API: docs/API.md (v1).
Design: Vellum canvas screen 5 "Account and workspace history" (`Account.dc.html`, read only).

## Purpose

One page that lists every workspace (project) on this server, newest first, and for the selected one shows what it
holds and what happened to it: uploaded, read, conflicts decided or settled, values signed off. A judge or a
returning user finds an earlier project and reopens it. There is no login (decision 0001), so the page has no user
name, avatar or "your account" data: it is the server's workspace history.

## Files owned

- `frontend/src/account/AccountScreen.tsx`: the route view (`#/workspaces`), `export function AccountScreen()`
  (`ComponentType<Record<string, never>>`, the seam in fe-vellum-common.md).
- `frontend/src/account/history.ts`: pure functions `workspaceKind`, `workspacePill`, `workspaceStats`,
  `historyEvents` (input: the API objects; output: plain view data).
- `frontend/src/account/account.css`: styles, design tokens only (`--v-*` from `src/shell/shell.css`).
- Tests: `frontend/src/account/history.test.ts` [unit], `frontend/src/account/AccountScreen.test.tsx` [component].
- The route, the header's "Workspaces" link and the logo are fe-shared's; this spec only renders the screen.

## User flow

1. The user follows "Workspaces" in the header (or opens `#/workspaces`). The page shows the heading "Your
   workspaces", the line "<n> workspaces on this server", a "New workspace" link (to `#/`), and the list of
   workspaces, newest first; the first one is selected.
2. Each list item shows the workspace name, a status pill in words, "<kind> · <files> files · <drawings> drawings"
   and when it was created. Clicking (or Enter / Space on) another item selects it.
3. The panel on the right (below the list on a phone) shows the selected workspace: "<kind> · created <time>", its
   name, an "Open workspace" link (`#/p/<id>`), four stats, and its history, oldest first.
4. "Open workspace" goes to the project screen; "New workspace" goes to the start page.

## API calls

All through the shared client (`src/api/`). Fixtures in `backend/tests/fixtures/api_v1/`.

**`listProjects()` → `GET /api/projects`** (API.md "GET /api/projects"; `project_list.json`). Once on mount, again
on Retry. Per `ProjectSummary`:

| Field | Drives |
| --- | --- |
| `id` | selection key; "Open workspace" `href` `#/p/<id>` |
| `name` | list item title and panel heading (mono, `overflow-wrap: anywhere`; text, never HTML) |
| `state` | the list pill: `queued`/`running` "Reading", `done` "Ready", `failed` "Failed" (words, plus the token colour) |
| `created_at` | list item time and the panel's "created <time>" (`formatTime`, shared: `YYYY-MM-DD HH:MM UTC`) |
| `files`, `drawings` | "<kind> · 11 files · 5 drawings" (singular "1 file", "1 drawing"); kind: `files === 1` "Single file", else "Archive" |
| `to_review` (#121, `number \| null`, null unless done) | a warn pill "<n> to review" after the state pill; none when null or 0 |
| `conflicts_open` (#121) | not shown (pre-QA 12:00): the API counts conflicts a rule settled as open (API.md), while the conflicts screen calls them "settled by a rule" and nothing for a person; a warn pill would contradict it |

**`getProject(id)` → `GET /api/projects/{id}`** (`project.json`). When an item is selected (and for the first one on
mount). Fields: `files[]` (count, `size` summed for the upload event), `counts` (`ready`, `flagged`, `set_aside`,
`text_only`), `drawings[]` (count), `state`, `error`, `ms`, `cost_usd`, `created_at`.

**`getProjectReview(id)` → `GET /api/projects/{id}/review`** (`project_review.json`). With `getProject`, in parallel.
Fields: `drawings[].to_review`, `.signed`, `.quantities`, `.drawing_id`, `.file`; `conflicts[]` (`label`, `file`,
`conflict.resolution`, `conflict.values[]`, `settled`, `needs_person`).

**`getProjectQuestions(id)` → `GET /api/projects/{id}/questions`** (#121; `project_questions.json`). With `getProject`
and `getProjectReview`, in parallel. `questions[]` newest first: `question`, `answer` (`number | null`), `unit`,
`drawing_id`, `at`, `refused`. Only asks that sent `project_id` are logged. Drives the Questions stat and the
"Asked" events.

**`getTakeoff(drawingId, { project: id })` → `GET /api/drawings/{id}/takeoff?project=<id>`** (`takeoff.json`). Only
for the review's drawings with `signed > 0`, after the review arrives, in parallel. `project` is required here:
sign-offs are kept per project (API.md "GET …/takeoff"), and without it the takeoff is the drawing's state outside
any project. Fields: `quantities[].signed` (`by`, `at`, `value`), `.label`,
`.unit`. A drawing with `signed: 0` is not requested.

### Stats (`workspaceStats`)

Five cells, in this order (the design's three, plus to review and sign-offs):

| Label | Value |
| --- | --- |
| Files | `project.files.length` |
| Drawings | `project.drawings.length` |
| Questions | `questions.length` of the log; "–" while it is loading or failed |
| To review | sum of `review.drawings[].to_review` |
| Signed off | "<sum of `signed`> of <sum of `quantities`>" |

### History (`historyEvents`)

One event per fact, each with a time, a glyph, a title and a detail. Sorted by time, oldest first; equal times keep
the order of this table. Times show as `HH:MM` (UTC, from the ISO string, as `formatTime` does), with the date only
in the panel heading. Glyphs are text in a circle (`↑ ✓ ⇄ ✔ !`) and every event says what it is in words, so
nothing relies on the colour.

| Event | When | Time | Title | Detail |
| --- | --- | --- | --- | --- |
| upload | always | `created_at` | "Uploaded <name>" | "<n> files · <size>" (size: sum of `files[].size`, `formatSize` from `src/ingest/ingest.ts`) |
| reading | `state` `queued`/`running` | `created_at` | "Reading the drawings" | "<finished> of <n> files" |
| done | `state` `done` | `created_at` | "Analysis done" | "<drawings> drawings · <ready> ready, <flagged> flagged, <set_aside> set aside, <text_only> text only · <ms, `formatMs` from `src/ingest/ingest.ts`>" (zero counts left out) |
| failed | `state` `failed` | `created_at` | "Ingest failed" | `error` |
| rule | a conflict with `settled` null and `conflict.resolution` set | `created_at` | "Settled by a rule: <label>" (conflicts.md wording, never "AI") | "<file> · kept <resolution.value, formatValue> · <resolution.rule>" |
| needs you | a conflict with `needs_person` true | `created_at` | "Conflict waiting for you: <label>" | "<file> · <values joined ' vs '>" |
| settled | a conflict with `settled` set | `settled.at` | "Conflict settled: <label>" | "<file> · kept <settled.value, formatValue>" |
| signed | a takeoff row with `signed` set | `signed.at` | "Signed off: <label>" | "<file> · <signed.value, formatValue> · by <signed.by>" |
| asked | each entry of the questions log | `at` | "Asked: <question>" | "<file> · <answer, formatValue with unit>" (a text `answer` as is); refused: "<file> · not answered"; `answer` null and not refused: "<file> · no answer". `<file>`: the project drawing with that `drawing_id`, else the id |

## States

| State | What shows | Reach it |
| --- | --- | --- |
| Loading list | the shared `Loading` "Loading workspaces…"; no panel | pending `GET /api/projects` (`never()`) |
| Empty | "No workspaces yet." and a link "Drop files or try a sample" to `#/`; no panel | `project_list.json` with `projects: []` |
| List error | shared `ErrorView` with `detail`, "code: <code>", Retry (reloads the list) | 500 `error.json` |
| Loading panel | the list, and in the panel "Loading <name>…" | pending `GET /api/projects/{id}` |
| Panel error | the list stays; the panel shows `ErrorView` with Retry (reloads that project) | 404 `error.json` for the project |
| Review error | heading, Files and Drawings stats and the upload / analysis events show; To review and Signed off read "–"; one line "Review not loaded: <detail> (<code>)" with Retry | 500 for `…/review` |
| Questions error | all else shows; the Questions stat reads "–"; "Questions not loaded: <detail> (<code>)" with Retry | 500 for `…/questions` |
| Sign-offs error | all else shows; "Sign-offs not loaded: <detail> (<code>)" under the history | 500 for one `…/takeoff` |
| Reading | pill "Reading"; the "Reading the drawings" event; no polling on this page (Out of scope) | `project.json` with `state: "running"` |
| Failed | pill "Failed"; the "Ingest failed" event with `error` | `state: "failed"`, `error` set |
| No-keys | the shell's offline strip only | `info.json` |
| Phone 390 | Layout below | e2e at 390x844 |

## Layout

Design `Account.dc.html`, without the country picker and the avatar (fe-vellum-common.md "Left out").

- Desktop 1440x900: content max 1280 px, centred, padding 40/24. Top row: `h1` "Your workspaces" (44 px, 700) with
  the line under it, "New workspace" (accent pill button with a plus) at the right. Below, two columns with a 24 px
  gap: the list (flex 1 1 320 px, max 400 px; items are cards, radius 18, 1 px line, the selected one 2 px accent
  border and `aria-pressed="true"`), and the panel (white card, radius 22, card shadow): head (kind · created,
  name in mono 24 px, "Open workspace" soft accent pill), the stats `dl` as a 4-column grid with 1 px dividers,
  then "History" (`h3`) and the `ol` of events (grid 52 px time · 28 px glyph · text).
- Phone 390x844: one column, 16 px gutters; the top row wraps ("New workspace" under the heading); the list above
  the panel, full width; stats in 2 columns, the fifth ("Signed off") spanning both; event text wraps (`overflow-wrap: anywhere`); no horizontal page
  scroll; tap targets at least 44 px.
- The pill tooltip of the design is not built: the pill's word is the whole message.

## Acceptance criteria

Fixtures imported read-only; "derived" = a fixture spread with the named fields changed; the API is mocked at
`fetch` with `mockApi` (shared).

List
- AC-1 On mount the screen sends `GET /api/projects` once and shows "Loading workspaces…" until it answers.
  [component, pending]
- AC-2 With `project_list.json`: one item "sample-project.zip", pill "Ready", "Archive · 11 files · 5 drawings",
  "2026-11-14 08:00 UTC"; the heading "Your workspaces" and "1 workspace on this server". [component]
- AC-3 A derived list with `files: 1, drawings: 1` reads "Single file · 1 file · 1 drawing". [unit `workspaceKind`]
- AC-4 Pills: `queued` and `running` "Reading", `done` "Ready", `failed` "Failed"; each pill holds its word.
  [unit `workspacePill`]
- AC-5 `projects: []` shows "No workspaces yet." and a link to `#/`; no panel, no project request. [component]
- AC-6 A 500 list shows `ErrorView` with "internal error" and "code: internal"; Retry sends `GET /api/projects`
  again. [component, `error.json`-shaped body]
- AC-7 The first item is selected (`aria-pressed="true"`); clicking the second item of a two-project derived list
  selects it, sends `GET /api/projects/<its id>` and `…/review`, and the first item becomes `aria-pressed="false"`.
  [component]
- AC-8 An item is a `<button>`: Enter and Space select it. [component]
- AC-9 A name `<img src=x onerror=alert(1)>` renders as that text in the list and the panel; no `img` is added.
  [component]

Panel
- AC-10 With the item selected, `GET /api/projects/5e0c1a2b3d4f` and `GET /api/projects/5e0c1a2b3d4f/review` are
  sent; the panel shows "Archive · created 2026-11-14 08:00 UTC", the name, and a link "Open workspace" to
  `#/p/5e0c1a2b3d4f`. [component, `project.json`, `project_review.json`]
- AC-11 Stats with `project.json`, `project_review.json` and `project_questions.json`: Files "3", Drawings "5",
  Questions "2", To review "2", Signed off
  "0 of 157" (the fixture's sums). [unit `workspaceStats`]
- AC-12 "New workspace" is a link to `#/`. [component]
- AC-13 While the project is loading the panel reads "Loading sample-project.zip…". [component, pending]
- AC-14 A 404 for the project shows `ErrorView` in the panel only; the list stays; Retry requests the project
  again. [component]
- AC-15 A 500 for the review: Files and Drawings show, To review and Signed off read "–", and "Review not loaded:
  internal error (internal)" with Retry; the upload and analysis events show. [component]

History
- AC-16 `historyEvents(project.json, project_review.json, [])` gives, in order: "Uploaded sample-project.zip" with
  detail "3 files · <formatSize of 26513>", "Analysis done" with "5 drawings · 3 ready, 4 flagged, 2 set aside,
  2 text only · 12.5 ms", and "Settled by a rule: area of room (name 1.01)" with "plans/flat-b.pdf · kept 30.00 m² ·
  the printed label over the outline at the sheet's scale". [unit]
- AC-17 A derived conflict with `settled: {"value": 22.401, "at": "2026-11-14T09:30:00Z"}` gives "Conflict settled:
  area of room (name 1.01)", "plans/flat-b.pdf · kept 22.40 m²", time "09:30", and no "Decided by rule" event for
  it. [unit]
- AC-18 A derived conflict with `needs_person: true` and `resolution: null` gives "Conflict waiting for you: …" with
  "plans/flat-b.pdf · 22.40 m² vs 30.00 m²". [unit]
- AC-19 A derived takeoff row with `signed: {"by": "Ana", "at": "2026-11-14T09:40:00Z", "value": 2}` gives "Signed
  off: door count", "plans/flat-b.pdf · 2 · by Ana", time "09:40". [unit]
- AC-20 Events sort by time, oldest first; equal times keep the table order (upload, reading/done/failed, rule,
  needs you, settled, signed). [unit]
- AC-21 `state: "running"` gives "Reading the drawings" with "<finished> of <n> files" and no "Analysis done";
  `state: "failed"` gives "Ingest failed" with the `error` text. [unit]
- AC-22 Only drawings with `signed > 0` get a `GET …/takeoff?project=<id>`; with `project_review.json` (all `signed: 0`) none is
  sent. [component]
- AC-23 A 500 for a takeoff shows "Sign-offs not loaded: internal error (internal)" and every other event.
  [component]
- AC-24 Each event's glyph is `aria-hidden`; its title says the kind in words ("Uploaded", "Analysis done",
  "Settled by a rule", "Conflict settled", "Signed off"…). [component]

Layout
- AC-25 At 390x844 the page has no horizontal scroll with a 60-character unbroken workspace name, the list is above
  the panel, and the stats are two columns. [e2e, qa-r1's long-name upload]
- AC-26 At 1440x900 the list and the panel sit side by side. [e2e screenshot, looked at]
- AC-28 (#121, pre-QA) A list item with `to_review: 2, conflicts_open: 1` shows the pill "2 to review" and no
  conflict pill (rule-settled conflicts are counted open by the API); with `to_review` null or 0 no pill shows; no
  element has `data-pending`. [component]
- AC-31 (pre-QA) "Open workspace" is a soft accent pill (`.account-open`: `--v-accent-soft` background,
  `--v-accent-strong` text); at ≤720 px the fifth stat ("Signed off") spans both columns. [unit: parse account.css]
- AC-29 (#121) `GET /api/projects/{id}/questions` is sent with the project; with `project_questions.json` the
  Questions stat reads "2" and the history has "Asked: How many doors are there?" with "<file> · 2" and "Asked: What
  colour is the roof?" with "<file> · not answered", at 08:05; `workspaceStats` with no log gives Questions "–".
  [unit + component]
- AC-30 (#121) A 500 for the questions: Questions reads "–", "Questions not loaded: internal error (internal)" with
  Retry, which asks again; every other stat and event shows. [component]
- AC-27 No user name, initials, avatar or country control is rendered. [component: no text "Beatrice", no
  element with the old avatar's role; review of the file]

## Not in the API

| What the design shows | Field that backs it |
| --- | --- |
| "Questions" stat and "asked …" history events | real since #121: `GET /api/projects/{id}/questions` (`getProjectQuestions`) |
| "1 conflict open" pill in the list | real since #121: `ProjectSummary.conflicts_open` and `.to_review` |
| A finish time for "Analysis done" | real since #120: `ProjectView.finished_at` (`created_at` while it is null) |
| "AI decision approved" vs "Your choice" on a settled conflict | already backed: `settled` set = a person's choice, else the rule; no new field |
| User name, avatar, team ("Beatrice · Hour49") | none: no login (decision 0001). Left out. |

## Pending fields (mocked)

None left on this screen (#121, 11:35): the `to_review` and questions mocks and `src/account/pending.ts` are gone;
null fields show the empty states above (no pill, "–").

## Out of scope

- Polling a workspace that is still being read (open it with "Open workspace" to watch it).
- Deleting or renaming a workspace (no endpoint).
- The pill tooltips, the country picker, the avatar.
- Paging the list (the server returns every project).

## Open points

1. `formatSize` and `formatMs` live in `src/ingest/ingest.ts` (fe-ingest). Recommend they move to
   `src/api/format.ts` (fe-shared), since two screens use them; until then account imports them from ingest.
2. The fixture sums in AC-11 and AC-16 (3 files, 157 quantities, 26513 bytes, 12.5 ms) are read from the trimmed
   fixtures; the build worker computes them from the fixture in the test, not as literals.
3. "Open workspace" goes to `#/p/<id>` (the project's Simple view), not to a drawing: a workspace has several
   drawings. Recommend keep.
