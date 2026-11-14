# Ingest: home, project status, file trace (spec, frontend v2: Vellum)

Status: v2 (Vellum redesign, built), 2026-11-14, by fe-ingest; API fields of PR #120 read directly.  Story: #33.  API: docs/API.md (v1, main eb3552c).
Design: Tudor's "Vellum redesign" canvas, screen 1 "Drop files or a zip" (`Main.dc.html`) and screen 2 "Reading the
drawings" (`Ingest.dc.html`), local copies in `.agents/design/vellum/project/` (look only; their mock data is never
used). v1 behaviour that QA verified stays unless a criterion below says it changed.

Names from the shared spec (`docs/specs/frontend/shared.md`) used here: client functions `uploadProject`,
`startSample`, `listProjects`, `getProject`, `getTrace`; URL builders `pageUrl`, `previewUrl`; `useInfo`,
`uploadTooLarge`, `Loading`, `ErrorView`, `<Credit>`, `getDrawing`, `formatTime` (`src/api/format.ts`); test helpers `mockApi` and the typed fixtures of `src/api/fixtures.ts`.

## Purpose

The first screens a judge sees. Home (screen 1) starts a project: drop or pick one zip or one file, or the sample
button; earlier projects are on screen 5 (`#/workspaces`, account.md), linked from home and the header. The project
screen (screen 2, Simple view) follows the ingest live: the step the pipeline is at, the share of files finished,
then every drawing with a link into its workspace and every file with its state and reason; its Advanced view is
screens 9-12 (`AdvancedIngest`, fe-scaffold). The file trace follows one file through every
stage, with what each stage found and how long it took, and shows a normalised image before and after.

## Files owned

All under `frontend/src/ingest/`; each `*.tsx`/`*.ts` with logic has a `*.test.ts(x)` beside it.

| File | What |
| --- | --- |
| `HomeScreen.tsx` | route `#/`, `HomeScreen()`: the hero, `UploadBox`, the format chips, the "Workspaces" link |
| `UploadBox.tsx` | the drop card: drop zone, file picker, sample button, client-side size check, upload errors |
| `ProjectScreen.tsx` | route `#/p/<project_id>`, `ProjectScreen({projectId})`: title row with the Simple/Advanced toggle (`?view=advanced`), polling; Simple renders `ProgressCard` + drawing list + file list; Advanced renders `AdvancedIngest` |
| `ProgressCard.tsx` | screen 2's card: step label, ring, stats row, the 8-step list |
| `FileTraceScreen.tsx` | route `#/p/<project_id>/f/<file_id>`, `FileTraceScreen({projectId, fileId})`: restyled, same content |
| `BeforeAfter.tsx` | the upload (`preview.png`) next to the normalised page, with what normalisation did |
| `ingest.ts` | pure functions: `progressOf`, `isFinished`, `isLive`, `kindLabel`, `STEPS`, `stepOf`, `activeStep`, `stepFiles`, `percentDone`, `elapsedMs`, `normalisedSteps`, `formatMs`, `formatCost`, `formatSize`, `plural`, `STATE_LABEL`, `STAGE_LABEL` |
| `usePoll.ts` | poll a request 500 ms after each answer while a predicate holds; aborts (`signal`) on unmount |
| `ingest.css` | the screens' styles, colours only through the `--v-*` tokens of `src/shell/shell.css` |

Removed in v2: `ProjectList.tsx` (the list moves to screen 5, `src/account/`, fe-golden) and `StageStrip.tsx` (the
11-chip strip is replaced by the 8-step list; per-stage detail is the Advanced view's).

File triage (decision 0010: the class, description, relevance and a person's call on a triaged file's row and trace,
the project's `not_plans`): `file-triage.md` (FT-*).

[e2e] criteria are built by the e2e worker (golden-path.md), who owns `frontend/e2e/`. The shell (shared spec)
owns the router, the info banner and the API client; this spec calls the client's functions for the endpoints named
below.

## User flow

1. The user opens `#/`. Home shows the hero "Every answer, pointed at the drawing.", then the drop card: "Drop a
   drawing or a .zip here", a "Choose a file" button, a "Try the sample project" button, the line "The sample starts
   from scratch each time.", and the format chips. Under the card: "Earlier uploads are in Workspaces", linking to
   `#/workspaces`. No project list on home.
2. The user drops or picks one file. If it is over `limits.upload_mb` the card says so and sends nothing.
   Otherwise the buttons are disabled, the card shows "Uploading <name>…", and on `202` the app goes to
   `#/p/<id>`. On a phone the picker offers the camera too (`accept` includes `image/*`).
3. Or the user presses "Try the sample project": the card shows "Starting the sample…", and on `202` the app goes to
   `#/p/<id>`.
4. The project screen (Simple) shows the state ("Analysing now"), the project name, the Simple/Advanced toggle, and
   the progress card: "Step n of 8" with the step's name, a ring with the percent of files finished, the stats
   (Elapsed, Files through, Drawings ready, Cost) and the 8 steps (done, working with its hint and file bar,
   waiting). Under the card: the drawings (each with "Open") and the files (each a link to its trace). While the
   project is `queued` or `running` it refreshes every 500 ms.
5. "Advanced" sets `?view=advanced`: the same title row, then `AdvancedIngest` with the polled project. "Simple"
   removes the query. Polling goes on across the toggle (the screen is not remounted: the shell keys screens by the
   path without the query).
6. A drawing's "Open" link goes to `#/p/<project_id>/d/<drawing_id>/engineer`, as soon as the drawing is listed.
   When the project is `done`, a "Settle the conflicts" link goes to `#/p/<project_id>/conflicts` (screen 3).
7. The user clicks a file row and goes to `#/p/<project_id>/f/<file_id>`: the trace, restyled (facts, stages with
   what each did and its time, any failure, the before/after for a normalised image). While the file is `queued`
   or `running` it refreshes every 500 ms.
8. "Back to the project" on the trace returns to `#/p/<project_id>`; "Open the drawing" (when the file has a
   `drawing_id`) goes to its engineer workspace.

## API calls

Fixtures are the files in `backend/tests/fixtures/api_v1/`. "Variant" means a fixture object spread with the named
fields overridden in the test (table under States); no response shape is written by hand.

**`GET /api/info`** (API.md "GET /api/info"; fixture `info.json`). Loaded once by the shell (shared spec); this spec
reads `useInfo().info.limits` and refuses with `uploadTooLarge(file.size, limits)`. Not loaded or failed: no client-side check, the server's 413
still applies.

**`POST /api/projects?name=<file name>`** (`uploadProject(file)`; API.md "POST /api/projects"; fixture
`project_started.json`). On drop or pick, after the size check. Body: the `File` itself, raw; `name` is `file.name` through `encodeURIComponent`.
Reads `id` only: the app navigates to `#/p/<id>`. `state` and `url` are not used (the project screen fetches the
status itself). Errors: 413 `too-large`, 429 `busy`, 422 `validation`/`invalid`, any other: shown in the box
(`detail` and `code`), and the box is usable again.

**`POST /api/projects/sample?fresh=true`** (`startSample({fresh: true})`; API.md "POST /api/projects/sample"; fixture `project_started.json`). On
the sample button. Always `fresh=true`: each demo run starts clean and has an ingest to watch. Reads `id`. Errors as
for an upload, plus 404 `not-found` when the archive is not built (its `detail` says how to build it).

**`GET /api/projects`**: not called by these screens in v2 (the list is screen 5's, account.md).

**`GET /api/projects/{project_id}`** (`getProject(projectId)`; API.md "GET /api/projects/{project_id}"; fixture `project.json`). When the
project screen mounts, then 500 ms after each response while `state` is `queued` or `running`. Fields:

- `name`: the `h1`. `state`: the eyebrow above it, a dot and a word (`queued` "Waiting to start", `running`
  "Analysing now", `done` "Done", `failed` "Ingest failed"). `error`: shown under the title when `failed`.
- `files[]`: every number of the progress card (table below), and one row each under the card, in the order
  given: `path`, `kind` (`kindLabel`: in words, "PDF vector", "photo of a plan"; "not identified" when null), `state` (badge, `STATE_LABEL`), `reason` (when not
  empty), `size` (`formatSize`), `ms` (`formatMs`, finished files only), `reused` ("reused" tag when true). The row
  links to `#/p/<project_id>/f/<id>`.
- `drawings[]`: one card each under the progress card: `file` (title), `kind`, `route` as `routeLabel` ("drawn PDF route", IN-73), `state`
  (badge), `other_renderings[].file` ("also: plans/flat-a.png"), and an "Open" link to
  `#/p/<project_id>/d/<drawing_id>/engineer`.
- `ms`, `cost_usd`, `created_at`: the stats row (below). The whole object goes to `AdvancedIngest` as `project`.
- `counts`, `readers`, and each file's `sha256`, `group`, `source`, `takeoff`, `normalised` are not shown here (the
  trace shows the file ones). The progress comes from `files`, not `counts`, as API.md defines it.

**Screen 2's numbers, mapped** (every value on `Ingest.dc.html`; the mock's are never shown):

| On the design | Here | From |
| --- | --- | --- |
| "Analysing now" | the state word | `state` (words above) |
| "harbour-block-archive.zip" | the `h1` | `name` |
| "Step 3 of 8" | "Step <activeStep> of 8"; "All 8 steps done" when `done`; nothing when `failed` | `activeStep(files)`: the lowest `stepOf(file.stage)` among files not finished (`queued`/`running`); 1 when there are no files yet |
| "Route" (the `h2`) | `STEPS[activeStep].name`; "Ready" when `done`; "Stopped" when `failed` | as above |
| 35 % (ring) | `percentDone` = round(100 × finished / files); 0 with no files | `files[].state` (`progressOf`); ring `role="img"`, `aria-label` "<n> percent done" |
| Elapsed "5 s" | `formatMs(elapsedMs)` | `done`/`failed`: `ms` (set by the backend when ingest ends). `queued`/`running`: browser time of the last poll − `started_at`, at least 0; "—" while `started_at` is null (queued) |
| Remaining "~9 s" | not shown | Bogdan: no `eta_ms` (#14 triage); Elapsed only |
| (none) | Cost "$0.00" | `cost_usd` (`formatCost`); API.md: "0.0 with no paid reader, which is the point to show" |
| Files through "4 / 14" | "<finished> / <files>"; "—" while `queued`/`running` with no files (R1-1-4) | `progressOf(files)` |
| Drawings ready "1 / 9" | "<drawings.length> / <expected>"; the count alone while `expected` is null | `drawings[]` (each entry is a written drawing); `expected` = `expected_drawings` (null while queued; final once done) |
| The 8-step list | `STEPS`, each row done / working / waiting (icon + word) | `activeStep`: rows before it done, it working, after it waiting; all done when `done`; the list is left out when `failed` |
| The working row's hint | the step's hint (`STEPS`) | fixed text |
| The working row's bar "6 / 12 files" | "<passed> / <through> files" and a bar of that ratio | `stepFiles(files, step)`: `through` = files minus those finished at an earlier step; `passed` = files at a later step, plus files finished at this step |

`STEPS` (the design's 8 rows, in the API's stage order; the hints say only what the stages do):

| # | Name | Stages (`stepOf`) | Hint |
| --- | --- | --- | --- |
| 1 | Unpack | `unpack`, `hash`, and `null` | opening the archive safely |
| 2 | Identify | `identify`, `group` | what each file really is |
| 3 | Route | `route`, `cache` | picking the best source per drawing |
| 4 | Normalise | `normalise` | one page frame per sheet |
| 5 | Extract | `extract` | rooms, doors, windows, fixtures |
| 6 | Cross-check | `second_count` | a second, independent count |
| 7 | Index | `takeoff` | precomputing the answers |
| 8 | Drawing model | `write` | one stored model per drawing |

**`GET /api/projects/{project_id}/files/{file_id}/trace`** (`getTrace(projectId, fileId)`; API.md "…/trace"; fixture `trace.json`). When the trace
screen mounts, then 500 ms after each response while `file.state` is `queued` or `running`. Fields:

- `file.path` (title), `file.state` (badge), `file.reason`, `file.kind` (`kindLabel`), `file.size`, `file.route`, `file.source`
  (the "Read from" fact: the path only), `file.group`, `file.sha256` (first 12 characters, full value in `title`),
  `file.reused` ("reused: read before, not recomputed"), `file.ms`, `file.cost_usd`.
- `file.drawing_id`: when set, an "Open the drawing" link to `#/p/<project_id>/d/<drawing_id>/engineer`.
- `file.normalised` and `file.drawing_id`: when both are set, `BeforeAfter` (below).
- `file.takeoff`: a collapsed `<details>` "What it ends as: N quantities", a two-column list of key and value in the
  order given, keys as text. Not shown when empty.
- `stages[]`, in order, one item each: `STAGE_LABEL[stage]` (the raw value for a stage the label table lacks),
  `did`, `output` (when not empty and not equal to `did`), `ms` (`formatMs`), `cost_usd` (only when above 0), and
  `failure` (when set: the item reads "Failed: <failure>" and is marked with an icon and the word, not colour only).
  A `cache` item reads "Cached: <did>" and a note "the stages below are from the first ingest of this content".

**`GET /api/projects/{project_id}/files/{file_id}/preview.png?width=1600`** (`previewUrl(projectId, fileId)`; API.md
"…/preview.png"). The "before" image in `BeforeAfter`, as a plain `<img src>`. A failed load shows "Preview not available" in its place.

**`GET /api/drawings/{drawing_id}/pages/1.png?width=1600`** (API.md "…/pages/{n}.png"), `pageUrl(drawingId, 1)`, a plain
`<img src>`. The "after" image in `BeforeAfter`. A failed load shows "Page not available".

**`GET /api/drawings/{drawing_id}`** (`getDrawing(drawingId)`; API.md "GET /api/drawings/{drawing_id}"; fixture
`drawing.json`). Once, when `BeforeAfter` is shown, for `file.drawing_id`. Reads `credit` only: the shell's
`<Credit>` goes under the "after" image with it (null shows "Credit: none recorded for this file"). If the request
fails, `<Credit>` gets null. No credit line under the upload preview.

`BeforeAfter` shows the two images side by side (stacked on a phone), captioned "As uploaded" and "After
normalisation", with alt texts "<path> as uploaded" and "<path> after normalisation", and under them the list
`normalisedSteps(normalised)`: "EXIF orientation <exif> applied" when `exif` is set and not 1, "turned <rotated>°"
when `rotated` is not 0, "deskewed <deskew_deg>°" when `deskew_deg` is not 0, "perspective corrected" when
`rectified` (plus " (<rectifier>)" when `rectifier` is set); when none applies, the one line "No turn, deskew or perspective correction applied (rotation is not checked)". Then
"<width> × <height> px". The page image's aspect ratio comes from the loaded image, never stretched.

## States

| State | Home | Project screen | File trace | Reach it on purpose |
| --- | --- | --- | --- | --- |
| Loading | list shows "Loading projects…" | "Loading project…" in place of the content | "Loading trace…" | delay the response (component test: a pending promise; e2e: `page.route` with a delay) |
| Empty | (no list on home in v2) | only once the project is `done` or `failed`: no files: "This upload has no files." No drawings: "No drawings: nothing in this upload could be read as a plan." While `queued` or `running` an empty list gives no verdict: it reads "Waiting for the files…", and with no files yet the progress line is left out (no "0 of 0") | stages `[]`: "No stages yet." | variants `list-empty`, `no-drawings`, `no-files`, `trace-queued`; `queued` with `files: []` |
| Error | drop card: `detail` and `code` of the upload error | first load fails: `ErrorView` (its `not-found` link "Back to workspaces") with Retry. A poll fails: the last data stays, labelled "Not updating since <formatTime(now)>: <detail> (<code>)", with Retry that resumes polling | as the project screen, plus "Back to the project" | `mockApi` with `{status: 500, body: error}`; 404 with an unknown id; stop the backend |
| Upload refused | `uploadTooLarge`'s sentence. No request sent | | | a `File` over the limit (component test: `new File` with a stubbed `size`) |
| Busy / too large | box shows `detail` and `code` (`busy`, `too-large`) | | | `mockApi` 429 / 413 with `error.json` spread with that `code` |
| Running | | polling; "Analysing now"; the working step row shows its hint and file bar; running files show "running" | polling; stages grow | variant `running` / `trace-running` |
| Failed project | | "Ingest failed", "Stopped" and `error`; no step list; polling stopped; files listed as returned | | variant `failed` |
| Set aside | | the row reads "set aside" with its `reason` | the failing stage reads "Failed: <failure>" | variant `set-aside` / `trace-failed` |
| Text only | | the row reads "text only" with its `reason`; no drawing | | variant `text-only` |
| Normalised image | | | `BeforeAfter` | `project.json` file `f2` as the trace's `file` (variant `trace-image`), `trace-rotated` |
| Advanced view | | `?view=advanced`: title row and toggle, then `AdvancedIngest` (its own states); "Loading project…" until the first answer | | `#/p/<id>?view=advanced` with `project.json` |
| No keys | the shell's "running offline" banner (shared spec); nothing else changes, the sample button works | same | same | `info.json` (`no_keys: true`); the e2e runs on the no-keys backend |

Variants (each starts from the named fixture; only the listed fields change):

| Variant | From | Changes |
| --- | --- | --- |
| `list-empty` | `project_list.json` | `projects: []` |
| `running` | `project.json` | `state: "running"`, `ms: 0`, `finished_at: null`; `files[2]`: `state: "running"`, `stage: "extract"`, `reason: ""`, `drawing_id: null`; `drawings`: without the entry whose `drawing_id` is the original `files[2].drawing_id` |
| `queued` | `project.json` | `state: "queued"`, `ms: 0`, `started_at`, `finished_at` and `expected_drawings` null; every file `state: "queued"`, `stage: null`, `kind: null`, `drawing_id: null`, `reason: ""`; `drawings: []` |
| `failed` | `project.json` | `state: "failed"`, `error: "the server restarted during ingest"` |
| `set-aside` | `project.json` | `files[0]`: `state: "set_aside"`, `reason: "not a drawing"`, `stage: "identify"`, `drawing_id: null` |
| `text-only` | `project.json` | `files[0]`: `state: "text_only"`, `kind: "text"`, `reason: "text and no drawing"`, `drawing_id: null` |
| `no-drawings` | `project.json` | `drawings: []` |
| `no-files` | `project.json` | `files: []`, `drawings: []` |
| `trace-running` | `trace.json` | `file.state: "running"`, `file.stage: "extract"`; `stages`: the first 7 |
| `trace-queued` | `trace.json` | `file.state: "queued"`, `file.stage: null`; `stages: []` |
| `trace-failed` | `trace.json` | `stages`: the first 7, the 7th (`extract`) with `failure: "no page could be read"`; `file.state: "set_aside"`, `file.reason: "no page could be read"`, `file.drawing_id: null` |
| `trace-cache` | `trace.json` | a stage `{stage: "cache", did: "ingested before in another project", ms: 0, output: "", failure: null, cost_usd: 0}` inserted after `route`; `file.reused: true` |
| `trace-image` | `trace.json` | `file`: `project.json` `files[1]` (`plans/flat-a.png`, `normalised` set, nothing done) |
| `trace-rotated` | `trace-image` | `file.normalised`: `exif: 6`, `rotated: 90`, `deskew_deg: 1.5` |

## Layout

Colours, radius, shadow and font only through the `--v-*` tokens (shared.md); system font stack, no web fonts.
The header is the shell's (logo, "Vellum", "Workspaces"); these screens draw none.

**Screen 1, home (`Main.dc.html`).** Column max 1120 px, centred, top padding 72 px.
- Hero `h1` "Every answer, pointed at the drawing." centred, 64 px bold, max 16ch.
- The drop card (`section`, `aria-label` "Drop drawings or an archive"): white, radius 28 px, max 760 px; inside it a
  dashed inner zone (radius 20 px) with the upload icon, "Drop a drawing or a .zip here" (24 px semibold), the
  buttons "Choose a file" (accent, pill) and "Try the sample project" (grey pill), the sample note, and the busy,
  refusal and error lines. Under the inner zone the format chips: "IFC models", "DXF", "Vector PDF · SVG",
  "PNG · JPG scans and photos", "ZIP archives".
- Under the card, centred: "Earlier uploads are in Workspaces" (a link to `#/workspaces`).
- Not built: the edit-plan link, the country picker, the avatar (common brief).

**Screen 2, Simple (`Ingest.dc.html`).** Column max 820 px.
- Title row: left the state eyebrow (dot + word, accent) over the name `h1` (44 px); right the toggle
  (`role="group"`, `aria-label` "View"): "Simple" and "Advanced" links, the current one white with
  `aria-current="page"`. Wraps under the title on a phone.
- The progress card (`section`, `aria-label` "Progress", radius 24 px): top row "Step n of 8" (13 px muted) over the
  step name `h2` (34 px), the 96 px ring on the right with the percent in its middle; the stats row as a `dl` of
  four cells (Elapsed, Files through, Drawings ready, Cost); the 8-step list (`ol`): each row an icon (done: filled
  check, `role="img"` "done"; working: spinner, "working"; waiting: empty circle, "waiting"), the name, and on the
  working row its hint and the file bar.
- When `done`: under the card a row with "Settle the conflicts" (accent pill) to `#/p/<id>/conflicts`.
- Then "Drawings" (cards with "Open") and "Files" (rows linking to the trace), restyled as white cards with the
  token radius and shadow; with no files or drawings the empty lines of States.
- Advanced: the title row stays; `AdvancedIngest` replaces everything under it.

**File trace (restyle, no design screen).** Column max 820 px. "Back to the project", then the title row as screen
2 (the state badge as eyebrow, no dot (one marker), over the path `h1`, "Open the drawing" as an accent pill on the right); the facts as a stats-style
`dl` card (two columns, one on a phone); `BeforeAfter` as a card; the stages as a card with the step-list look
(done check or failed icon + word, label, `did`, `output`, time on the right); the takeoff `<details>` as a card.

**Phone 390x844.** One column, 16 px gutters, no horizontal page scroll; hero 40 px; the stats row two by two;
the toggle under the title; tap targets at least 44 px; long paths and reasons wrap (`overflow-wrap: anywhere`).

Status is never colour alone: badges carry their word and icon (ready ✓, flagged !, set aside –, text only ¶,
queued …, running ◌); step rows carry "done", "working", "waiting".

## Acceptance criteria

Home and upload

- IN-1: `#/` renders the drop card (region "Drop drawings or an archive"), a "Choose a file" button and a "Try the
  sample project" button. [component]
- IN-2: The file input has `accept` containing `.zip`, `.pdf`, `.ifc`, `.dxf`, `.svg` and `image/*`, and no
  `multiple`. [component]
- IN-3: Picking a file of `upload_mb` × 1048576 bytes or fewer sends exactly one `POST
  /api/projects?name=<encodeURIComponent(name)>` whose body is that `File`; a name with a space and `ä` arrives
  encoded. [component, `info.json`]
- IN-4: Picking a file over `limits.upload_mb` × 1048576 bytes shows the sentence `uploadTooLarge` returns for it
  and sends no request. [component, `info.json`]
- IN-5: With `/api/info` not loaded (pending or failed), a file of any size is uploaded and the server decides.
  [component]
- IN-6: Dropping two files shows "Drop one file or one zip at a time." and sends no request; dropping one file
  uploads it as IN-3. [component]
- IN-7: While an upload or sample request is in flight, the box shows "Uploading <name>…" or "Starting the
  sample…", both controls are disabled, and a second click sends nothing. [component, pending promise]
- IN-8: On `202` from an upload or from the sample, the location becomes `#/p/<id>` with `id` from
  `project_started.json`. [component]
- IN-9: "Try the sample project" sends `POST /api/projects/sample?fresh=true` with no body. [component]
- IN-10: A 413, 429, 422 or 404 response shows its `detail` and `code` in the box (e.g. "busy") and re-enables the
  controls. [component, `error.json` bodies with status and code changed]

Project list

- IN-11: removed in v2 (the project list is screen 5's, account.md).
- IN-12: removed in v2 (as IN-11).
- IN-13: removed in v2 (as IN-11).
- IN-14: removed in v2 (as IN-11).
- IN-52: Home shows the `h1` "Every answer, pointed at the drawing.", the five format chips of Layout and no other,
  and no link or text about editing a house plan. [component]
- IN-53: Home has a link "Earlier uploads are in Workspaces" to `#/workspaces` and sends no `GET /api/projects`.
  [component, `mockApi` with no list route]

Project screen

- IN-15: `#/p/<id>` requests `GET /api/projects/<id>` and shows "Loading project…" until the first answer.
  [component]
- IN-16: With `project.json` the screen shows the `name`, "Done", "All 8 steps done", "Ready", the ring "100 percent
  done", and the stats Files through "3 / 3", Drawings ready "<drawings.length>" (with " / <expected>" when known,
  IN-68), Cost "$0.00". [component]
- IN-17: `progressOf` counts `ready`, `flagged`, `text_only` and `set_aside` as finished and `queued`, `running`
  as not. [unit]
- IN-18: Each file of `project.json` is a row, in the order given, with its `path`, `kind`, state word, `reason`,
  size and time; the row links to `#/p/<id>/f/<file id>`. [component]
- IN-19: `set-aside` shows the first row as "set aside" with "not a drawing"; `text-only` shows "text only" with its
  reason. [component]
- IN-20: A file with `reused: true` shows the tag "reused"; with `kind: null` it shows "not identified".
  [component, variant]
- IN-21: Each entry of `project.json` `drawings` is a card with its `file`, `kind`, route, state word and an "Open"
  link to `#/p/<id>/d/<drawing_id>/engineer`; the flat-a card lists "also: plans/flat-a.png" from
  `other_renderings`. [component]
- IN-22: `no-drawings` shows "No drawings: nothing in this upload could be read as a plan."; `no-files` shows
  "This upload has no files." [component]
- IN-23: `failed` shows "Ingest failed" and the `error` text, and no further request is made. [component, fake
  timers]
- IN-24: With `running`, a second `GET /api/projects/<id>` is sent 500 ms after the first answer, and none before;
  with `queued` the same. [component, fake timers]
- IN-25: Polling stops on the first answer with `state` `done` or `failed`: no request in the next 5 s.
  [component, fake timers, `running` then `project.json`]
- IN-26: A drawing that appears between two polls (`running` then `project.json`) gets its card and "Open" link
  without a reload; rows keep their order. [component, fake timers]
- IN-27: Leaving the route (unmount) stops polling: no request after unmount. [component, fake timers]
- IN-28: A poll that fails keeps the last data on screen and shows "Not updating since <formatTime(now)>: <detail> (<code>)"
  with Retry; polling is paused until Retry, which sends the request again. [component, fake timers, 500 +
  `error.json`]
- IN-29: A first load answered 404 `not-found` shows `ErrorView` with `detail`, `code` and its link "Back to workspaces" (`#/workspaces`); a
  first load that fails with `code` `network` shows Retry, which requests the project again. [component,
  `error.json`, rejected fetch]
- IN-54: The toggle is a group "View" with links "Simple" (`#/p/<id>`) and "Advanced" (`#/p/<id>?view=advanced`);
  the current one has `aria-current="page"`. [component]
- IN-55: With `?view=advanced` the screen renders `AdvancedIngest` with `projectId` and the polled `project` (the
  same object the last poll returned), and no progress card, drawing or file list; going to Simple and back sends no
  extra `GET /api/projects/<id>` beyond the 500 ms polls. [component, `AdvancedIngest` mocked with `vi.mock`,
  `running` then `project.json`]
- IN-56: `stepOf` maps `unpack`, `hash`, null → 1; `identify`, `group` → 2; `route`, `cache` → 3; `normalise` → 4;
  `extract` → 5; `second_count` → 6; `takeoff` → 7; `write` → 8. `activeStep` of `running` is 5, of `queued` 1, of
  `files: []` 1. [unit]
- IN-57: With `running` the card shows "Analysing now", "Step 5 of 8" and the `h2` "Extract"; with `queued`
  "Waiting to start", "Step 1 of 8", "Unpack". [component]
- IN-58: The step list has 8 rows in `STEPS` order; with `running` rows 1-4 read "done", row 5 "working" with the hint
  "rooms, doors, windows, fixtures" and "2 / 3 files", rows 6-8 "waiting"; with `project.json` all 8 read "done" and
  no row has a hint or bar. Each state is an icon with `role="img"` and its word as name. [component]
- IN-59: `stepFiles(files, 5)` of `running` is `{passed: 2, through: 3}`; of `set-aside` with step 3 the set-aside
  file (finished at step 2) is not in `through`. [unit]
- IN-60: The ring's `aria-label` is "<n> percent done" with n = round(100 × finished / files): 67 for `running`,
  100 for `project.json`, 0 for `queued`. [unit `percentDone` + component]
- IN-61: Elapsed is `formatMs(ms)` when `done` or `failed`; when live it is `formatMs(now − started_at)` with the
  clock set by `vi.setSystemTime(started_at + 5 s)` on `project_running.json` ("5.0 s"), never below 0; "—" while
  `started_at` is null (`queued`). There is no "Remaining" cell (no `eta_ms`, API.md changelog). [unit `elapsedMs`
  + component, fake timers]
- IN-68: Drawings ready reads "<drawings.length> / <expected_drawings>" ("5 / 5" for `project.json`, "0 / 1" for
  `project_running.json`) and the count alone while `expected_drawings` is null (`queued`); no element carries
  `data-pending`. [component]
- IN-62: `failed` shows "Ingest failed", "Stopped" and the `error`, and no step list. [component]
- IN-63: "Settle the conflicts" links to `#/p/<id>/conflicts` when `done` and is absent when `running` or `queued`.
  [component]
- IN-64: Drawing cards and file rows stay under the card in the Simple view with IN-18 to IN-22 and IN-26 unchanged;
  file rows are links whose `href` contains `/f/f` and whose text has the path and the state word (the e2e's
  locators). [component]

Stage strip

- IN-30: removed in v2 (the 11-chip strip is replaced by the step list, IN-56 to IN-60).
- IN-31: removed in v2 (as IN-30; the working step is IN-58).
- IN-51: removed in v2 (no per-stage counts in the Simple view, so the Cache caption has nothing to explain; the
  Advanced view shows the cache stage).

File trace

- IN-32: `#/p/<id>/f/<fid>` requests `GET /api/projects/<id>/files/<fid>/trace`, shows "Loading trace…" until it
  answers, then the `path`, state word, `reason`, kind, size, route, "read from <source>", group, the first 12
  characters of `sha256`, time and cost. [component, `trace.json`]
- IN-33: Every stage of `trace.json` is an item in order with its label, `did`, and `ms` formatted by `formatMs`;
  `output` shows only when not empty and not equal to `did`. [component]
- IN-34: `formatMs` gives "0.68 ms" for 0.6838, "12.5 ms" for 12.5, "1.2 s" for 1234; `formatCost` gives "$0.00"
  for 0, "<$0.01" for 0.004, "$0.12" for 0.123; `formatSize` gives "2.2 KB" for 2263 and "1.0 MB" for 1048576.
  [unit]
- IN-35: `trace-failed` shows the `extract` item as "Failed: no page could be read" with an icon and the word, the
  file as "set aside", and no "Open the drawing" link. [component]
- IN-36: `trace-cache` shows "Cached: …" and the note "the stages below are from the first ingest of this content",
  and the file's "reused" text. [component]
- IN-37: With `trace.json` (`drawing_id` set) an "Open the drawing" link goes to
  `#/p/<id>/d/<drawing_id>/engineer`. [component]
- IN-38: `trace-running` polls the trace 500 ms after each answer and stops when `file.state` is finished
  (`trace.json` next); unmount stops it too. [component, fake timers]
- IN-39: The takeoff `<details>` is closed by default, its summary reads "What it ends as: N quantities" with N the
  number of `file.takeoff` keys, and opening it lists each key and value. [component, `trace.json`]
- IN-40: `trace.json` (`normalised: null`) shows no before/after; `trace-image` shows two images with `src`
  `/api/projects/<id>/files/<fid>/preview.png?width=1600` and `/api/drawings/<drawing_id>/pages/1.png?width=1600`,
  captions "As uploaded" and "After normalisation", and "No turn, deskew or perspective correction applied (rotation is not checked)" and
  "1200 × 800 px". [component]
- IN-41: `normalisedSteps` of `trace-rotated` gives "EXIF orientation 6 applied", "turned 90°", "deskewed 1.5°";
  with `rectified: true` it adds "perspective corrected". [unit]
- IN-42: An image of `BeforeAfter` that fails to load is replaced by "Preview not available" (before) or "Page not
  available" (after). [component, fire `error` on the `<img>`]
- IN-43: A trace answered 404 shows `detail`, `code` and "Back to the project". [component, `error.json`]
- IN-48: With `trace-image`, exactly one `GET /api/drawings/<file.drawing_id>` is sent and "Credit: none recorded
  for this file" (`drawing.json`, `credit: null`) shows under the "after" image and not under "As uploaded"; with
  that request answered 500 the same line shows; with `trace.json` (no before/after) the request is not sent.
  [component, `drawing.json`, `error.json`]
- IN-65: The restyled trace keeps its names: "Back to the project", the path as `h1`, "Open the drawing", the stage
  items with label, `did` and time; a failed stage reads "Failed: …" with an icon and a done stage carries "done".
  IN-32 to IN-43 and IN-48 hold unchanged. [component]

Across the screens

- IN-44: Strings from files (`path`, `name`, `reason`, `did`, `output`, `failure`, `error`, takeoff keys) render as
  text: a `reason` of `<img src=x onerror=alert(1)>` shows those characters and adds no element. [component,
  variant with that `reason`]
- IN-45: No state is shown by colour alone: every badge and the working/failed markers contain their word.
  [component: text query on each state variant]
- IN-46: On the no-keys backend: "Try the sample project" reaches `#/p/<id>`, the project reaches "Done" (Files
  through "11 / 11", see Open point 10), every
  row has a state word, clicking `plans/flat-a.pdf` shows its trace with the `write` stage, and its "Open the
  drawing" reaches the engineer route. [e2e]
- IN-47: At 390x844 and 1440x900 the three screens (home, sample project done, the `plans/flat-a.png` trace) have
  no horizontal page scroll, and a screenshot of each is saved. [e2e]
- IN-69: `kindLabel` gives every API file kind in words ("PDF vector", "PNG plan", "photo of a plan", "IFC model",
  "text PDF", …; no `_`), an unknown id as sent, "not identified" for null; file rows, drawing cards and the trace's
  Kind fact use it. [unit + component]
- IN-70: At 390 the tap targets are at least 44 px: home's "Earlier uploads are in Workspaces", the trace's "Back to
  the project" and the takeoff `<summary>` (pre-QA). [unit: the `ingest.css` rules; browser check]
- IN-71 (R4-a-6): The working step's file bar ("<passed> / <through> files") is left out when no file has reached
  the step (`through` 0): a `queued` project with `files: []` shows no "0 / 0 files". [component]
- IN-72 (R4-a-7, Bogdan 12:45): A `done` project with no drawings (an empty zip, a lone .exe, a password zip) shows,
  in Simple, a plain card (`section` "Nothing read") "Nothing could be read from this upload" listing every file and
  every skipped entry with its reason, then the Files list; no progress card (no ring, no "All 8 steps done"), no
  "Settle the conflicts", no Drawings list. Backend unchanged. [component: `done`, `drawings: []`, set-aside files;
  browser 1440 and 390 with a synthetic upload]
- IN-73 (R4-a-4): Drawing cards show the route as `routeLabel` ("drawn PDF route", "image route", "BIM model
  route", "CAD route"), never the raw id ("vector route"). [unit `routeLabel`; component]
- IN-66: `ingest.css` has no colour literal (`#hex`, `rgb(`, `hsl(`): every colour is a `var(--v-…)`. [unit:
  read the file]
- IN-67: At 390x844 home, the Simple project screen and the trace have no horizontal scroll, the hero is 40 px, the
  stats row is two by two and the toggle sits under the title. [e2e, screenshots]
- IN-49 (R1-1-4): While the project is `queued` or `running`, an empty file or drawing list reads "Waiting for the
  files…", never "This upload has no files." or "No drawings: …", and with no files Files through reads "—" (no
  "0 / 0"). [component, `queued` with `files: []`, `running` with `drawings: []`]
- IN-50 (R1-1-1): Counts are singular for 1 and plural otherwise: "1 file · 1 drawing", "0 files · 2 drawings",
  "What it ends as: 1 quantity". [unit `plural` + component] (v2: the list strings moved to account.md; the
  progress line is now the stats row.)

## Out of scope

- Upload progress in bytes (fetch gives none; would need XMLHttpRequest).
- More than one file per upload (zip them), folder drops, resuming an upload.
- Screens 6-8 (Edit my plan) and home's "Or edit a house plan from a photo →" link; the country picker; the avatar
  and user name (common brief).
- The "Remaining" time and the expected number of drawings while running (Not in the API).
- The design's "Choose files" (plural): one file per upload, zip several.
- The mock's end-of-ingest conflict list with approve / modify / pick a variant: conflicts live in the surveyor
  workspace (`GET /api/projects/{id}/review` is the surveyor spec's).
- Showing `readers`, `counts` and the drawing model on these screens.
- A preview of files with no drawing (a set-aside photo); `preview.png` exists for them but nothing links it here.
- Deleting or renaming projects (no endpoint), refreshing the project list on a timer.

## Not in the API

What the designs show that the API cannot back; the screen shows nothing for it.

| On the design | Field needed | Here |
| --- | --- | --- |
| Screen 2 "Remaining ~9 s" | `ProjectView.eta_ms` | Bogdan: no (file times differ too much to estimate); Elapsed only |
| Screen 1 chip "DXF · DWG" | a DWG reader (`dwg` is a `kind`, but no route reads it) | chip "DXF" only |
| Screen 1 "Choose files" (several files) | an upload endpoint that takes several files | one file per upload |

`started_at`, `finished_at`, `skipped` and `expected_drawings` landed in PR #120 (API.md changelog 2026-11-14); the
mocks of the interim (Tudor 11:05) are gone, `src/ingest/pending.ts` with them. `started_at` and
`expected_drawings` are read as above. `finished_at` and `skipped` are not shown: `ms` already gives the duration
once ingest ends, and every skipped file is already a "set aside" file row with its `reason`.

## Open points

1. **Fixtures for live and broken states.** Until real ones land, the variants above (made in the test); real
   project running/failed and trace set-aside fixtures asked on board #14.
2. **Fixture import.** The fixtures are on main in `backend/tests/fixtures/api_v1/` (PR #63 merged). Their ids,
   times and durations are fixed stand-ins (every `ms` is 12.5), so tests assert on values read from the fixture,
   never on typed-in ids. The shared spec should fix how tests import them (relative path from `frontend/`,
   `resolveJsonModule`).
3. **`project_started.json` has `state: "done"`.** The screen ignores `state` and `url` of the 202 and always
   navigates and polls, so it does not matter; noted so nobody "fixes" the screen to skip polling.
4. **Mock README vs mock.** `demo/README.md` says the mock lets you click a file to follow it through every stage;
   the current `demo/app.js` has no such view (its ingest has the stage timeline and a conflict summary only). The
   trace layout here is new, built from the API's trace shape. Recommend updating the README line when the real
   screen lands.
5. **Before/after uses plain images, not the viewer's `PageFrame`** (viewer.md Open point 5). The upload's size
   is not in the API (`normalised.width/height` is the after image), so `PageFrame`, which needs a size, cannot
   frame the "before" image; neither image has marks. Credit: under the "after" image only, from
   `GET /api/drawings/{drawing_id}` (round 1 decision 4).
6. **e2e.** Resolved (round 1 decision 6): the e2e worker (golden-path.md) builds IN-46 and IN-47.
7. **Sample `fresh=true` resets review edits.** Every press of the sample button wipes the last sample project's
   review edits and sign-offs (API.md). Fine for the demo; a judge who presses it twice loses their edits. Recommend
   keeping `fresh=true` and saying "starts the sample from scratch" under the button.
8. **Screen props.** Final (round 1 decision 8): `HomeScreen()`, `ProjectScreen({projectId})`,
   `FileTraceScreen({projectId, fileId})`, mounted with `key` = route path without query.
9. **Answer confidence change (board #14).** Pending the next backend PR; it touches only answers. No ingest screen
   shows confidence, so nothing here changes.
10. **e2e text (fe-golden).** The v1 line "N of M files finished" becomes the stats cell Files through "N / M":
    `e2e/golden-path.spec.ts:24` (`'11 of 11 files finished'`) and `e2e/qa-r1.spec.ts:23` (`/of \d+ files?
    finished/`) need the new text, e.g. the `dd` after the `dt` "Files through". Every other name the e2e uses stays
    ("Try the sample project", "Done", file row links with `/f/f`, "Open the drawing", the trace text).
11. **"Try a sample" vs "Try the sample project".** The design says "Try a sample"; the button keeps "Try the sample
    project" (the e2e and IN-1 use it, and an `aria-label` that differs from the visible text breaks WCAG 2.5.3).
    Recommend keeping it; renaming means the e2e changes with it.
12. **Step order.** The design lists Drawing model, Cross-check, Index as steps 6-8; the backend runs
    `second_count`, `takeoff`, `write`. `STEPS` follows the backend (Cross-check, Index, Drawing model) so the working
    step never moves backwards. Hints changed where the design claims what no stage does: Normalise "upright sheets,
    views and scale" → "one page frame per sheet" (no stage checks rotation, R1-3-5; scale is read in extract).
13. **Way out of screen 2.** The design has no link from screen 2 to anything but Advanced. The Simple view keeps the
    drawing "Open" links and the file rows (the golden path and QA use them) and adds "Settle the conflicts" to
    screen 3 when done. Recommend fe-surveyor's ConflictsScreen says when there is nothing to settle.
14. **ProjectList.tsx.** Deleted from `src/ingest/` in v2. If fe-golden wants its row (name, state, `<time>`,
    "N files · N drawings", `plural`) for screen 5, it imports `plural`/`STATE_LABEL` from `src/ingest/ingest.ts` or
    copies the 30 lines; IN-11 to IN-14 move to account.md.

