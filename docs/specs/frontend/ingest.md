# Ingest: home, project status, file trace (spec, frontend v2: Vellum)

Status: v2 (Vellum redesign, built), 2026-11-14, by fe-ingest; v3 demo parity (section "Demo parity", IN-74..IN-82) by preqa-a, GO from frontend-orch 2026-11-14 16:27 (P1 "Back to Documents" yes, P2 keep Cost); API fields of PR #120 read directly; v4 pipeline steps (section "Pipeline steps v4", IN-89..IN-92) by m3d-front for w3:p1, 2026-11-14 23:55 (Tudor 23:40: the steps as the backend runs them today).  Story: #33.  API: docs/API.md (v1, main eb3552c).
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
   the progress card: "Step n of 9" with the step's name, a ring with the percent of files finished, the stats
   (Elapsed, Files through, Drawings ready, Cost) and the 9 steps (done, working with its hint and file bar,
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
| "Step 3 of 8" | "Step <activeStep> of 9"; "All 9 steps done" when `done`; nothing when `failed` (the count is `STEPS.length`) | `activeStep(files)`: the lowest `stepOf(file.stage)` among files not finished (`queued`/`running`); 1 when there are no files yet; 9 (Index) when every file is finished and the project still runs |
| "Route" (the `h2`) | `STEPS[activeStep].name`; "Ready" when `done`; "Stopped" when `failed` | as above |
| 35 % (ring) | `percentDone` = round(100 × finished / files); 0 with no files | `files[].state` (`progressOf`); ring `role="img"`, `aria-label` "<n> percent done" |
| Elapsed "5 s" | `formatMs(elapsedMs)` | `done`/`failed`: `ms` (set by the backend when ingest ends). `queued`/`running`: browser time of the last poll − `started_at`, at least 0; "—" while `started_at` is null (queued) |
| Remaining "~9 s" | not shown | Bogdan: no `eta_ms` (#14 triage); Elapsed only |
| (none) | Cost "$0.00" | `cost_usd` (`formatCost`); API.md: "0.0 with no paid reader, which is the point to show" |
| Files through "4 / 14" | "<finished> / <files>"; "—" while `queued`/`running` with no files (R1-1-4) | `progressOf(files)` |
| Drawings ready "1 / 9" | "<drawings.length> / <expected>"; the count alone while `expected` is null | `drawings[]` (each entry is a written drawing); `expected` = `expected_drawings` (null while queued; final once done) |
| The 9-step list | `STEPS`, each row done / working / waiting (icon + word) | `activeStep`: rows before it done, it working, after it waiting; all done when `done`; the list is left out when `failed` |
| The working row's hint | the step's hint (`STEPS`) | fixed text |
| The working row's bar "6 / 12 files" | "<passed> / <through> files" and a bar of that ratio; none on Index (no file stage) | `stepFiles(files, step)`: `through` = files minus those finished at an earlier step; `passed` = files at a later step, plus files finished at this step |

`STEPS` (v4, section "Pipeline steps v4": the backend's stages in its own order, each step named by its stage's
`STAGE_LABEL`, the stage id in words; the hints say only what the code does today):

| # | Name | Stages (`stepOf`) | Hint |
| --- | --- | --- | --- |
| 1 | Unpack | `unpack`, `hash`, and `null` | opening the upload safely, one fingerprint per file |
| 2 | Identify | `identify` | what each file is, and whether it is a floor plan |
| 3 | Route | `group`, `route`, `cache` | one source per drawing: the model, the drawn PDF or the image |
| 4 | Normalise | `normalise` | one page frame per sheet; photos made upright and flat |
| 5 | Extract | `extract` | rooms, doors, windows, fixtures, scale and schedules |
| 6 | Second count | `second_count` | the same quantities measured another way |
| 7 | Takeoff | `takeoff` | counting rules applied, every quantity worked out |
| 8 | Store | `write` | one drawing model per drawing, with its marks |
| 9 | Index | none: the project's last phase | every file made searchable for questions |

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
| Error | drop card: `detail` of the upload error (no raw `code`, QA R2-C5) | first load fails: `ErrorView` (its `not-found` link "Back to workspaces") with Retry. A poll fails: the last data stays, labelled "Not updating since <formatTime(now)>: <detail> (<code>)", with Retry that resumes polling | as the project screen, plus "Back to the project" | `mockApi` with `{status: 500, body: error}`; 404 with an unknown id; stop the backend |
| Upload refused | `uploadTooLarge`'s sentence. No request sent | | | a `File` over the limit (component test: `new File` with a stubbed `size`) |
| Busy / too large | box shows `detail` (worded per `code`: `busy`, `too-large`) | | | `mockApi` 429 / 413 with `error.json` spread with that `code` |
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
  refusal and error lines. Under the inner zone the format chips: "IFC models", "DXF with its PDF", "PDF, drawn or
  scanned", "SVG with its PDF", "PNG · JPG scans and photos", "ZIP archives" (a scanned PDF is named, since ingest
  routes it to the raster reader; user-facing copy changed 2026-11-14; a DXF or SVG uploaded alone is set aside with
  "this DXF file has no sheet to show on its own; upload it with the drawing's PDF or image" (SVG the same; API.md,
  #459), so its chip says so: QA 2026-11-15, before it read "DXF", "SVG").
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
- IN-93: Picking a file whose name is over 255 characters (counted as the API counts them: an emoji is one) shows
  "This file name is <n> characters long; the limit is 255. Rename the file and try again." and sends no request;
  without it the API's 422 read "query.name: String should have at most 255 characters". [component]
- IN-5: With `/api/info` not loaded (pending or failed), a file of any size is uploaded and the server decides.
  [component]
- IN-6: Dropping two files shows "Drop one file at a time. To send several, such as a DXF or SVG with its PDF, put
  them in one .zip." (QA R4-G3) and sends no request; dropping one file
  uploads it as IN-3. [component]
- IN-7: While an upload or sample request is in flight, the box shows the upload's progress (IN-89) or "Starting
  the sample…", both controls are disabled, and a second click sends nothing. [component, pending promise]
- IN-8: On `202` from an upload or from the sample, the location becomes `#/p/<id>` with `id` from
  `project_started.json`. [component]
- IN-9: "Try the sample project" sends `POST /api/projects/sample?fresh=true` with no body. [component]
- IN-10: For the sample, a 413, 429, 422 or 404 response shows its `detail` in the box, not the code (QA R2-C5) and re-enables the
  controls. [component, `error.json` bodies with status and code changed]
- IN-89 (Bogdan 2026-11-15, "so I know when i've successfully uploaded and sent to server and received, and moves me
  to start the extraction"): a file goes over XHR (fetch has no upload progress). Sending: "Sending <name>: <sent>
  of <total> MB (<p>%)" with a progress bar named "Upload"; all bytes out: "Sent <name> (<total> MB): waiting for
  the server…". On 202 the app opens `#/p/<id>` (extraction starts on the server by itself) and keeps
  `{name, bytes}` in sessionStorage `uploaded:<id>`; the project screen then shows "Uploaded: <name>, <MB> MB,
  received by the server." and "Unpacking…" until the server lists files, then "<n> files found.". Failures, with
  a Retry that sends the file again: no answer, "The connection was lost while sending <name> (at <p>%)."; an
  HTTP error, "The server refused <name>: <detail>". A 4xx about the file itself (empty, too large, not a drawing)
  has no Retry, since the same file would be refused again; 408 and 429 (busy) keep it (QA R4-G6). [component `HomeScreen.test.tsx`, `ProjectScreen.test.tsx`,
  unit `client.test.ts`; e2e `upload.spec.ts` 1440 and 390]

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
- IN-16: With `project.json` the screen shows the `name`, "Done", "All 9 steps done", "Ready", the ring "100 percent
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
- IN-29: A first load answered 404 `not-found` shows `ErrorView` with `detail` (no code) and its link "Back to workspaces" (`#/workspaces`); a
  first load that fails with `code` `network` shows Retry, which requests the project again. [component,
  `error.json`, rejected fetch]
- IN-54: The toggle is a group "View" with links "Simple" (`#/p/<id>`) and "Advanced" (`#/p/<id>?view=advanced`);
  the current one has `aria-current="page"`. [component]
- IN-55: With `?view=advanced` the screen renders `AdvancedIngest` with `projectId` and the polled `project` (the
  same object the last poll returned), and no progress card, drawing or file list; going to Simple and back sends no
  extra `GET /api/projects/<id>` beyond the 500 ms polls. [component, `AdvancedIngest` mocked with `vi.mock`,
  `running` then `project.json`]
- IN-56 (v4): `stepOf` maps `unpack`, `hash`, null → 1; `identify` → 2; `group`, `route`, `cache` → 3; `normalise` → 4;
  `extract` → 5; `second_count` → 6; `takeoff` → 7; `write` → 8; no stage maps to 9. `activeStep` of `running` is 5,
  of `queued` 1, of `files: []` 1. [unit]
- IN-57: With `running` the card shows "Analysing now", "Step 5 of 9" and the `h2` "Extract"; with `queued`
  "Waiting to start", "Step 1 of 9", "Unpack". [component]
- IN-58: The step list has 9 rows in `STEPS` order; with `running` rows 1-4 read "done", row 5 "working" with the hint
  "rooms, doors, windows, fixtures, scale and schedules" and "2 / 3 files", rows 6-9 "waiting"; with `project.json` all 9 read "done" and
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
- IN-43: A trace answered 404 shows `detail` (no code) and "Back to the project". [component, `error.json`]
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
  every skipped entry with its reason, then the Files list; no progress card (no ring, no "All 9 steps done"), no
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

## Demo parity (v3, Tudor 2026-11-14 16:25; GO 16:27)

Source: brief `fe-demo-parity.md`, the demo `demo/vellum/app.js` (`ingestScreen`, `doneRow`, `chatCta`), `files.js`
(`traceScreen`), `style.css` (`.done-row`, `.chat-cta`, `.list-h`), PRs #206 (conflicts under the finished
reading, Documents tab, lists moved there), #211 (same in Advanced, fe-scaffold), #212 (issues to Documents, counted
on the tab), #214 (file page, file-triage.md), #204 (no credits on screens). Only UI and behaviour are ported: every
count and every conflict comes from the API, never from the demo's data.

### What changes on screen 2 (Simple)

- **While the project runs** the screen is the title row and the progress card only. The Drawings and Files lists
  leave this screen: they are on Documents (`#/p/<id>/documents`, fe-ingest, issues.md/documents.md), each file
  still linking to its page `#/p/<id>/f/<fid>`.
- **When it is done** (and has drawings), in this order:
  1. the progress card, unchanged above its step list, with the **done line** as its last row (demo `.done-row`):
     "<plural(drawings, 'drawing')> ready." + " Conflicts are below." when the conflicts list has any +
     " <n> issue(s) in Documents need(s) you." with "<n> issue(s) in Documents" a link to `#/p/<id>/documents`,
     only when n > 0. n is the same number as the Documents tab's badge (`useIssuesToAnswer`, fe-shared: issues still
     to answer, notes not counted), from the same hook, so the line and the badge never disagree. While n is unknown
     (loading or failed) the issues sentence is left out, never "0".
  2. fe-surveyor's conflicts list (`ConflictsList`, src/surveyor; AI-settled first, then the ones that need a
     person; its own heading "N conflicts found" / "No conflicts found", progress and cards). This screen only
     places it, with the route's query; it draws no conflict itself. No checks row on this screen.
  3. the chat row (demo `.chat-cta`): while any conflict still needs a person (or the list has not loaded yet), a
     disabled button "Start a new chat" with `aria-describedby` on "Settle the conflicts that need you first.";
     once none does, a link "Start a new chat" (accent pill) to `#/p/<id>/chat` and a link "Open the workspace" to
     the first drawing's workspace `#/p/<id>/d/<drawings[0].drawing_id>/engineer`.
  No "Settle the conflicts" button (the conflicts are on this screen), no issues list (they are on Documents).
- **Done with no drawings** stays IN-72's "Nothing read" card (no conflicts list, no chat row), now with the line
  "Every file is listed in Documents." linking to `#/p/<id>/documents` (the Files list moved there), and with a DXF
  among the set-aside files, the line of IN-93.
- **Failed** is unchanged (IN-23, IN-62).

### Shared pieces (exported from `src/ingest/`, used by Simple here and by fe-scaffold's Advanced view)

| Export | File | What |
| --- | --- | --- |
| `IngestFinished({ projectId, project, query, onCounts }): JSX.Element \| null` | `IngestFinished.tsx` (new) | everything under a finished card: fe-surveyor's `ConflictsList({ projectId, query, onCounts })` (its own `<section id="conflicts">`, heading, progress, cards, loading and error; `query` is the route's, so an issue link `#/p/<pid>?d=&q=` focuses its card), then the chat row. It keeps the list's last counts for the chat row and passes each one up through `onCounts`. Renders nothing unless `project.state === 'done'` and `project.drawings.length > 0`. |
| `DoneLine({ projectId, project, counts }): JSX.Element \| null` | `IngestFinished.tsx` | the done line ("5 drawings ready. Conflicts are below. 2 issues in Documents need you."); `counts: ConflictCounts \| null` from `onCounts` (null before the list has loaded: no "Conflicts are below."); the issues number from `useIssuesToAnswer(projectId)` inside it. Null unless `done` with drawings. |
| `ConflictCounts` | `IngestFinished.tsx` | `{ total: number; needsPerson: number }`, as fe-surveyor's `ConflictsList` reports them. |
| `CONFLICTS_ID` | `IngestFinished.tsx` | `'conflicts'`, the id of `ConflictsList`'s own section (fe-surveyor), for `document.getElementById(CONFLICTS_ID)?.scrollIntoView()` (never a `#` link: the router owns the hash). |

A screen uses them as: `const [counts, setCounts] = useState<ConflictCounts | null>(null)`; `<DoneLine counts={counts}
…/>` where its card ends; `<IngestFinished onCounts={setCounts} …/>` under the card. Simple puts `DoneLine` as the
progress card's last row (`ProgressCard` gets a `footer` slot); Advanced places both where fe-scaffold's spec says.

- IN-82: `DoneLine` and `IngestFinished` render nothing for `running`, `queued`, `failed` or `done` with no
  drawings; `IngestFinished` renders `ConflictsList` with `projectId` and the route's `query`, and calls `onCounts`
  with each count the list reports; `CONFLICTS_ID` is `'conflicts'`. [component, `ConflictsList` mocked]

### What changes on the file page (`#/p/<id>/f/<fid>`)

- No credit line under the after image: `BeforeAfter` drops `<Credit>` and its `getDrawing` call (screens carry no
  credits, #204; licence credits are on fe-shared's About page). The trace sends no `GET /api/drawings/<id>` for it
  any more.
- "Back to the project" becomes "Back to Documents" (`#/p/<id>/documents`): the file rows are there now, and the
  project screen no longer lists files. (Open point P1.)
- The triage card loses its "Does it belong to this project?" block and the "Described by <model>" note:
  file-triage.md FT-22, FT-23.

### Look (from `demo/vellum/style.css`, with the app's `--v-*` tokens)

- Done line: inside the card, flex, wrap, `gap: 12px`, `padding: 0 32px 28px` (`0 20px 22px` under 760 px), 15 px
  `--v-text-2`, the link `--v-accent`.
- Chat row: flex, wrap, `gap: 8px 16px`, `padding-top: 8px`; the button full width under 760 px; the reason line
  13 px `--v-muted`; "Open the workspace" a 13 px link with a 44 px tap target at 390.
- The sections stack with the demo's `.w820` column gap (24 px). No new colour; if the demo's orange (Documents
  badge) is needed here it is fe-shared's token.

### Acceptance criteria (v3)

- IN-74: With `running`, `queued` or `failed` the Simple screen has no Drawings and no Files region and no
  conflicts list or chat row. [component]
- IN-75: With `project.json` (`done`, 5 drawings) the screen shows, in DOM order: the Progress region, the done line
  inside it, the conflicts list (the mocked `ConflictsList`, rendered with `projectId`), then the chat row; no
  "Settle the conflicts" link, no Drawings or Files region, no issues list. [component, `ConflictsList` mocked]
- IN-76: The done line reads "5 drawings ready." plus " Conflicts are below." when the list reports at least one
  conflict, and " 2 issues in Documents need you." with a link "2 issues in Documents" to `#/p/<id>/documents` when
  the count is 2; with 1: "1 issue in Documents needs you."; with 0 or unknown: no issues sentence. [component, the
  count helper mocked: 0, 1, 2, pending]
- IN-77: While the list reports a conflict that needs a person (or has not reported yet), "Start a new chat" is a
  disabled `button` described by "Settle the conflicts that need you first." and there is no "Open the workspace";
  when it reports none, "Start a new chat" is a link to `#/p/<id>/chat` and "Open the workspace" a link to
  `#/p/<id>/d/<drawings[0].drawing_id>/engineer`; settling the last one (the list reports 0) enables it without a
  reload. [component]
- IN-78: `done` with `drawings: []` shows IN-72's card with a link "Every file is listed in Documents." to
  `#/p/<id>/documents`, and no conflicts list and no chat row. [component]
- IN-79: The file page's back link reads "Back to Documents" and goes to `#/p/<id>/documents` (also on its 404
  view, IN-43). [component]
- IN-80: With `trace-image` the before/after shows no "Credit" text and no `GET /api/drawings/<id>` is sent.
  [component]
- IN-81: At 390x844 and 1440x900 the finished Simple screen (sample, no-keys backend) has no horizontal scroll, the
  chat button and links are at least 44 px tall at 390, and keyboard focus reaches the conflicts list, then "Start a
  new chat", then "Open the workspace". [browser; e2e is fe-golden's]

- IN-83 (look, preqa-b's parity sweep): the file page reads like the demo's (`files.js` `traceScreen`, `.trace-h`,
  `.stats.facts`): the `h1` path in the mono font at 28 px (22 px at 390); the back link 13 px; the facts card a
  hairline grid edge to edge (2 columns, 1 at 390; `dt` 12 px/500 muted, `dd` 15 px/600); the stage list folded into
  a closed `<details>` "How it was read: <n> stages" in its card (the demo shows none; folded, nothing is lost); the
  Route fact as `routeLabel` ("drawn PDF route", never the bare id "vector").
  [component: the summary and `open` false, the Route fact; unit: the CSS rules]

- IN-84 (re-sweep item 3): the done project's kicker reads "Analysis done" in `--v-ok` (demo `.kicker.ok`); running
  "Analysing now", queued "Waiting to start", failed "Ingest failed" as before. [component]
- IN-85 (re-sweep item 3): on the project screen the Simple/Advanced segment is its own row under the `h1`,
  left-aligned (demo `.title-row` wrapped, `.seg` on its own row), at 1440 and 390; the file page keeps "Open the
  drawing" on the right. `TitleRow` takes `stack` for this. [component: class; unit: the CSS rule; browser]
- IN-86 (re-sweep item 3, orch 16:43 reversing P2: Tudor asked for the demo's look): the card's 4th stat is
  "Set aside" = files with `state === 'set_aside'` (the demo's "Set aside 6"), not Cost. [component]
- IN-87 (re-sweep console): no `GET /api/projects/<id>/issues` while the project is `queued` or `running` (the API
  answers 409 `not-allowed` until `done`): `DoneLine` asks for the issue count only once the project is done with
  drawings. The header badge's own request is fe-shared's. [component]

- IN-88 (judge's path, Bogdan #14, orch 19:18): on the finished Simple screen the chat row ("Start a new chat",
  "Open the workspace", or the locked button with "Settle the conflicts that need you first.") sits in the progress
  card right under "Ready", above the 9 steps, and appears once (not again after the conflicts list); visible
  without scrolling at 1440x900 and 390x844 (was y 1087 and 1299). Its lock still follows the conflicts list's
  counts (IN-77). Advanced keeps `IngestFinished`'s row after the list (fe-scaffold's screen). Replaces IN-75's
  "then the chat row" order and IN-81's focus order (now: "Start a new chat", "Open the workspace", then the
  steps and the conflicts list). [component; browser]

Superseded by v3: IN-18, IN-19, IN-20, IN-21, IN-22, IN-26, IN-73 (the rows and cards move to Documents: the same
criteria apply there, fe-ingest); IN-49's list half (no lists while running; its "—" for Files through stays);
IN-63 (no "Settle the conflicts"); IN-64; IN-48 (no credit; IN-80); IN-65's "Back to the project" (IN-79); IN-72's
"the Files list stays" (IN-78); FT-2 to FT-4 and FT-20's file rows move with the list (file-triage.md). IN-46's "clicking
`plans/flat-a.pdf`" goes through Documents (fe-golden).

### Needs from other owners

- fe-surveyor: `ConflictsList({ projectId, onCounts })` where `onCounts({ total, needsPerson })` is called with
  the list's counts whenever they change (after load and after each settle), and not before the first load; or
  any equivalent that gives the screen "how many still need a person" without a second request.
- fe-shared: `useIssuesToAnswer(projectId): number | null` from `src/shell/issueCount.ts` (shared.md "Documents
  badge": null while loading or failed), the badge's own count, used as is for the done line; routes
  `#/p/<id>/documents` and `#/p/<id>/chat` (shared.md "Tabs").
- fe-ingest (documents.md) imports from here: `StateBadge`, `kindLabel`, `routeLabel` and the triage helpers stay
  exported from `src/ingest/` when the lists leave `ProjectScreen.tsx`.

### API asks (none blocks this; all have a client-side way today)

- A1: `ProjectView.conflicts_open` and `ProjectView.issues_open` (they exist on `ProjectSummary` in the list only):
  the project screen could then enable "Start a new chat" and write the done line from the one poll it already
  makes, without `GET /review` and `GET /issues`. Until then: the conflicts list's counts and fe-shared's issue
  count, both client-side.
- A2: the issues-to-answer rule as a field (`issues_open` counts every open issue, notes too): e.g.
  `ProjectSummary.issues_need_person` (`state == open` and `severity != note`), so the badge and the done line
  read one number from the server. Until then fe-shared filters `GET /issues`.

### Decisions (GO, frontend-orch 16:27)

- P1: "Back to Documents" (IN-79), not the demo's "Back to the project" (that screen no longer lists files).
- P2: the card keeps Cost (no demo PR changed it to Set aside). Reversed 16:43 by orch (Tudor asked for the demo's
  look): "Set aside" replaces Cost (IN-86).

## Pipeline steps v4 (Tudor 2026-11-14 23:40: "make the ui pipeline stages accurate to our current architecture/flow")

The step list (Simple's card, Advanced's rail) follows what the backend runs today, read from the code
(`backend/app/core/ingest/service.py` `_run`, `groups.py`, `judge.py`, `app/core/pipeline/ingest.py`), not from the
design. Each file's trace names its stages (`StageTrace.stage`, API.md "…/trace"); a step is named by its stage in
words (`STAGE_LABEL`), so the screen and the trace use one word for one stage.

What the backend does, in order:

| # | Step | Stages | What runs (demo config: `tools/qa-env.sh` `DEMO_ENV`) |
| --- | --- | --- | --- |
| 1 | Unpack | `unpack`, `hash` | the zip opened with a path check and size caps; a PDF set's later drawn pages become files of their own; a sha256 per file |
| 2 | Identify | `identify` | the format from the first bytes; triage asks whether a picture is a floor plan (`SHEET_KIND=carbon`): a doubtful sheet is read and flagged, a non-plan is set aside and described (`TRIAGE_DESCRIBER=carbon`); a text PDF is text only |
| 3 | Route | `group`, `route`, `cache` | files of one plan grouped (same folder and name, an IFC model with its sheets); the richest source picked: IFC model, then CAD, then drawn PDF, then image (a scanned PDF goes to the image route); a group read before is reused (`cache`) |
| 4 | Normalise | `normalise` | an image turned upright by its EXIF tag and a phone photo flattened to its paper's corners (`RECTIFIER=r3`); a PDF's pages as the file gives them; a model has no page |
| 5 | Extract | `extract` | drawn PDF: the vector reader (rooms with areas, doors, windows, fixtures, scale from text and bar) and the schedule reader; image: the detector and room readers, Gemini Carbon on a large or sparse sheet (flagged), the printed scale, second readers that set each count's level (`DOUBLE_CHECK_READERS`, `CARBON_LEVELS=ladder`); IFC model: every object with its GlobalId |
| 6 | Second count | `second_count` | drawn PDF: scale text against bar, printed room areas, the sheet against its IFC model; image: the printed scale and printed totals against the reading; a disagreement is a conflict; an IFC model on its own has none |
| 7 | Takeoff | `takeoff` | the counting rules, then every quantity with its marks (one timed stage in the backend) |
| 8 | Store | `write` | one drawing model per sheet (or per model) stored by content |
| 9 | Index | none | once every file is finished, while the project still runs: triage judges whether each set-aside file belongs to the project (`TRIAGE_JUDGE=rules`), every non-plan file is described or its text read (`EVIDENCE_SCOPE=all_non_plan`), and the project's evidence index is updated for the chat |

Not steps, because they do not run at ingest: the conflict resolver (`RESOLVER`, at ask time, off in the demo), the
IFC fact sheet (`IFC_FACTS`, at ask time), the 3D view's GLB (`MODEL_3D`, converted on the first "View in 3D").

Index has no stage id: the backend keeps the project `running` with every file finished while it runs, so
`activeStep` is 9 then (no file bar); `ProjectStatus` has no phase field to name it (backend change not made: a
`phase` field would make it explicit).

- IN-89: With a `running` project whose files are all finished, `activeStep` is 9 and the card shows "Step 9 of 9",
  the `h2` "Index", rows 1-8 "done" and row 9 "working" with the hint "every file made searchable for questions" and no
  file bar. [unit + component]
- IN-90: Every step but Index is named `STAGE_LABEL` of its own stage (`unpack`, `identify`, `route`, `normalise`,
  `extract`, `second_count`, `takeoff`, `write`): Unpack, Identify, Route, Normalise, Extract, Second count, Takeoff,
  Store; `STAGE_LABEL.write` is "Store", also on the trace screen. No step reads
  "Cross-check" or "Drawing model". [unit]
- IN-91: e2e at 1440 and 390: a finished sample project shows "All 9 steps done" and the nine names in order on Simple;
  Advanced's rail shows the same nine. Screenshots `ingest-steps-<width>.png`, `advanced-steps-<width>.png`. [e2e]
- IN-93 (QA 2026-11-15, #468): IN-72's "Nothing read" card adds "A DXF is read with the PDF or PNG of the same
  name: put both in one .zip and upload that." when any set-aside file is a DXF, and no such line otherwise
  (`ProjectScreen.tsx`). [component: ProjectScreen.test.tsx "a lone DXF set aside: the Nothing-read card says to
  upload it with its PDF or PNG in one zip", "no DXF hint when the set-aside files are not DXF"]

## Pipeline view v5 (ingest UI track, 2026-11-15, brief `ingest-ui/live`; Bogdan 03:20: "I want the ingestion pipeline to look much better, and then to be more representative of the operations we are doing right now in the actual pipeline.")

Simple's progress card becomes the pipeline as it runs: the steps on the left, on the right the files by the route
they take, each lane with the readers that route runs on this server, and per file its stage, the reader running
now and, once read, what it found. Advanced and the file page are not changed here. API: decision 0018
(`FileStatus.step`, `ProjectStatus.phase`, `index_steps`); every new field is optional, so an older server still
renders from `stage`, `state` and `takeoff`.

Card, top to bottom (`ProgressCard.tsx`, `RouteLanes.tsx`, helpers in `pipeline.ts`):

1. Caption ("Step n of 9" / "All 9 steps done"), the `h2` (the step, "Ready" or "Stopped"), the ring. Once done, a
   sentence under "Ready" says what was read by which route and what needs a person (`routeSummary`).
2. The chat row (IN-88, unchanged).
3. Eight live totals: Elapsed, Files through, Drawings ready, Things found, Conflicts, Flagged, Set aside, Cost.
4. Two columns from 720 px (one under it): the nine steps (names and order as v4) and "How each file is read":
   one lane per route with files (IFC model, CAD, Drawn PDF, Image), then "Not routed yet", then "Not drawings".
5. The done line (v3, unchanged).

Readers per route come from `ProjectView.readers`, what ingest recorded for this upload (backend
`composition.build_ingest` `names`), not from `/api/info`: e.g. the demo's image route reads "photo flattening,
printed scale (Gemini), Gemini cross-check (not counted), symbol detector, Gemini count decision, count arbiter,
room reader, double check by 2 more readers (not counted), Gemini for sheets with few symbols, scale from door
sizes" (IN-117). A reader named `hello` or `off` is not shown. Step labels a file reports (`FileStatus.step`) light
their reader chip while they run and tick it ("ran") after; a label no reader name covers gets its own chip.

- IN-100: The card has a region "Routes" with the heading "How each file is read" and one region per lane with
  files, named by the lane (`IFC model`, `CAD`, `Drawn PDF`, `Image`, `Not routed yet`, `Not drawings`), its `h3`
  "<name> route" for a route; each lane lists its readers (list "Readers") and its files, each file a link to
  `#/p/<id>/f/<fid>`. [component: ProgressCard.test.tsx; e2e: golden-path GP-3 "the finished screen"]
- IN-101: `routeReaders(readers)` gives each route's readers in words from the recorded settings; a reader `hello`
  or `off` gives none; no record gives none. A route with files whose reader reads nothing says "No reader for this
  route on this server: nothing on it is counted."; with no record of the readers it says nothing.
  [unit: pipeline.test.ts; component]
- IN-102: "Things found" is the sum of a file's plain takeoff counts (no `area:`, `length:`, `room:` or `|` keys,
  no `plan` or `apartment`) over finished files that read themselves (another rendering of a drawing is not counted
  again); "—" while running with no file finished. `foundLine` names the biggest four ("5 rooms, 3 windows, 2
  doors"), then "+n more". [unit; component]
- IN-103: Lanes come in the order model, CAD, drawn PDF, image, not routed yet, not drawings; inside a lane:
  running, flagged, ready, then the rest, in upload order; empty lanes are left out. [unit]
- IN-104: Done, the sentence under "Ready" reads e.g. "Read 1 IFC model, 3 drawn PDFs and 3 images. 4 flagged
  files need a look; 2 set aside." (each drawing once). [unit; component]
- IN-105: A step label seen on a file (`FileStatus.step`) stays ticked on its lane's reader chip after it ends; a
  running one is marked "running:" (screen-reader text) and in the accent; a label no reader name starts with is
  shown as its own chip. [component]
- IN-106: A file row says, running: "<Stage>: <step>" ("Extract: Symbol detector, 8 views"), or the stage alone
  from an older server; queued: "waiting for a free reader"; another rendering: "same drawing as <source>"; ready:
  what it found; flagged or set aside: what it found, then its reason. An 8-tick track beside it shows its step
  (the current tick pulses, `motion-safe` only). [component]
- IN-107: With no `step`, `phase` or `readers` (an older server) the card renders from `stage` and `state`, with no
  reader chips and no "No reader" line. [component]
- IN-108: The totals are, in order: Elapsed, Files through, Drawings ready, Things found, Conflicts
  (`conflicts_open`, "—" until the server counts them), Flagged, Set aside, Cost (`formatCost(cost_usd)`). This
  brings Cost back beside Set aside (IN-86 said "not Cost"; changed with its test). [component]
- IN-109: With `phase: "index"` the card names step 9 "Index" even if a file still runs, its hint reads "judging
  what was set aside, describing the rest, indexing it all for the chat" (was "every file made searchable for
  questions": IN-89 changed with its test), and its row lists `index_steps` as "<label>: <did>". [component]
- IN-110: A lane shows at most 6 files; the rest are a link "<n> more files in Documents" to `#/p/<id>/documents`.
  [component]
- IN-111: While running, the step named is the one most files are read in now (a tie: the later step), not the
  lowest step a file waits in; with none running, the lowest (v4's `activeStep`). Every step a file is in now is
  "working" with its file bar; the hint shows on the named step only. (IN-57's examples hold: one file running in
  Extract.) [unit: `headlineStep`; component]
- IN-112: At 390 and 1440 the running, index and finished cards have no horizontal scroll; done on a phone the nine
  steps sit in two columns. Screenshots in the PR. [browser: e2e `ingest-steps-<width>.png`, `02-ingest-done.png`;
  the running and index states by a scratch script with the API mocked]
- IN-113 (orchestrator, 390 check with 40 files): a file row's link shows the folder muted and the file name in
  its own span that does not shrink, so a long path gives up its folder first and rows of one folder stay apart
  ("…/Grundriss_OG4…", not "Planunterlagen/Archi…"); the link's name and `title` stay the full path. [component]
- IN-114 (QA R2-C3, 255-character upload name): the title `h1` (screen 2 and the file page) shows at most 3 lines
  (`line-clamp-3`), with no sideways scroll at 390; its accessible name and `title` stay the full name. The
  "Uploaded: …" line cuts a name over 60 characters in the middle ("Bauprojekt_…_Me.png"), its `title` the whole
  name. [component;
  browser: screenshots at 390 and 1440 in the PR]
- IN-115 (QA R2-C4, empty zip): the "Uploaded: …" line says "Unpacking…" only while the project is queued or
  running with no files yet. Done with no files (an empty zip: the server answers `done`, `files: []`,
  `skipped: []`, no `error`) it says "No files found in it.", and the "Nothing read" card adds "There were no files
  in it."; failed with no files it says "Nothing was unpacked." (the server's error follows). [component]
- IN-116 (QA R2-A1, unread PNG): a drawing or file on a route whose reader is `hello` (`readers[route]`, "not read:
  this setup has no reader for …") was not read. The server keeps its drawing (flagged, with a page for the
  viewer), but "Drawings ready", the done line ("<n> drawings ready."), the "Flagged" total and the finished
  sentence's "Read …" leave it out; the sentence counts it as "<n> not read", not as flagged. A done project with no drawing read shows
  IN-72's "Nothing read" card, not "Ready" with a 100% ring. (A real reader that read nothing is not told apart:
  the API has no field for it yet.) [unit: `unread`, `readDrawings`, `routeSummary`; component]
- IN-117 (live demo readers, trace's sample 2026-11-15): the chips name what each source really is. An
  `arbiter-t1` part is "symbol detector" and "count arbiter" (never its class: no "door" or "window" chip); a
  `detector*` source is "symbol detector" for every part (it finds the plans too: no separate "plan finder");
  `decisions*` adds "Gemini count decision" (not "count arbiter"); `carbon_levels` is "Gemini cross-check (not
  counted)"; `carbon_reader=large…` is "Gemini for sheets with few symbols" (it reads a sheet only when the shipped
  reader found fewer than 3 things), any other value "Gemini reader"; `raster_printed_scale` "printed scale
  (Gemini)"; `double_check_readers` "double check by <n> more readers (not counted)"; `raster_scale=priors` "scale
  from door sizes"; `rectifier` other than `none` "photo flattening"; the drawn PDF route "drawn-PDF reader",
  "schedule tables", "second count"; the model route "IFC model reader". Image chips come in the order they run.
  [unit: pipeline.test.ts; component]
- IN-118: every step label a file on the demo config reports (the extract steps of a scan, a photo, a drawn PDF and
  an IFC model in the sample traces) lights a chip of its lane, so none turns into a chip of its own: a chip
  stands for the labels that start with its words or with the server's name for it ("Gemini Decisions…",
  "Gemini Carbon check…", "Gemini Carbon reader…", "Printed scale…", "Double-check reader…", "Drawn-PDF reader…",
  "Schedule tables…"). [unit; component]
- IN-119: above the lanes, "Every file first, before it takes a route:" and a list "Sorting" from `readers.triage`
  and `decisions_kind`: "scan or photo (Gemini)" (`decisions_kind=True`), "plan or not (rules)" or "(image
  model)" (`classifier`), "sheet kind (Gemini)" (`sheet_kind`), "describes sheets that are not plans (Gemini)"
  (`describer`), "keep or set aside (rules)" (`judge`); `off` parts are left out; no record, no list.
  [unit: `triageReaders`; component]
- IN-120 (orchestrator, `whole-390.png`: ten image chips in one wall): a lane's readers are grouped by what they
  do, the groups in the order they run, each with a short label beside its chips (above them on a phone):
  "Prepare" (photo flattening, printed scale, tiles), "Count" (every reader that counts: symbol detector, Gemini
  count decision, count arbiter, room reader, …), "Checks, not counted" (Gemini cross-check, the double-check
  readers, the drawn PDF's second count), "If few symbols" (`carbon_reader=large…`), "Scale" (scale from door
  sizes), "Also ran" (a step the server ran that no reader covers). The group comes from the reader
  (`readerGroup`), never from its position. Under a label a chip leaves out what the label says: "Gemini
  cross-check", "double check by 2 more readers", "Gemini reader" (IN-117's names stay the readers' full names and
  are what a lane with one group shows, with no label). The running highlight and the "ran" ticks work as before.
  The whole is a group "Readers", each group a list named by its label. Changed on purpose with it: IN-100's,
  IN-105's and IN-118's expected chip texts. [unit: `groupReaders`, `chipWords`; component; browser: screenshots
  at 1440 and 390]
- IN-121 (QA R3-G8, "Bauprojekt_Mehrfamilienhaus_Zuerich-Nord_2026.zip" at 390): the title `h1` wraps a long
  name after its own separators (`_`, `-`, `.`, `/`: a `<wbr>` after each, `nameParts`) before it breaks inside a
  word; `overflow-wrap:anywhere` stays only for a part longer than a line. Its accessible name and `title` stay the
  exact name (IN-114). [unit: `nameParts`; component; browser: screenshots at 390 and 1440]
- IN-122 (QA R3-G8, flag reason cut at 390): a finished file's row note in the lanes (what it found and why it is
  flagged or set aside) is shown whole, wrapping over as many lines as it needs; a queued or running file's note
  stays at 2 lines. [component; browser: screenshot at 390]

Superseded: IN-83's "stage list folded into a closed `<details>`" on the file page is replaced by
advanced-ingest.md AD-100 (the stages open on one time axis, PR #546); the rest of IN-83 (mono path, back link,
hairline facts, Route fact as `routeLabel`) stands.

Changed on purpose (IN-116): IN-16, IN-68 and IN-76 count the drawings read, so on `project.json` (a no-keys run,
`raster: hello`) "Drawings ready" is 4 / 6 and the done line "4 drawings ready.", and the golden path e2e on a
no-keys backend sees 4 / 6 (its scan and photo are not read).

Changed on purpose: IN-86 (Cost is back as the 8th total), IN-89's hint text, the golden path's "no file list on
Ingest" (v3): file links now appear on Ingest, only inside the route lanes. "Showing `readers` and `counts` on these
screens" leaves Out of scope.

## Out of scope

- Upload progress in bytes (fetch gives none; would need XMLHttpRequest).
- More than one file per upload (zip them), folder drops, resuming an upload.
- Screens 6-8 (Edit my plan) and home's "Or edit a house plan from a photo →" link; the country picker; the avatar
  and user name (common brief).
- The "Remaining" time and the expected number of drawings while running (Not in the API).
- The design's "Choose files" (plural): one file per upload, zip several.
- The mock's end-of-ingest conflict list with approve / modify / pick a variant: conflicts live in the surveyor
  workspace (`GET /api/projects/{id}/review` is the surveyor spec's).
- Showing the drawing model on these screens (readers and counts are shown since v5).
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
    Superseded by "Pipeline steps v4" (9 steps, named after the backend's stages).
13. **Way out of screen 2.** The design has no link from screen 2 to anything but Advanced. The Simple view keeps the
    drawing "Open" links and the file rows (the golden path and QA use them) and adds "Settle the conflicts" to
    screen 3 when done. Recommend fe-surveyor's ConflictsScreen says when there is nothing to settle.
14. **ProjectList.tsx.** Deleted from `src/ingest/` in v2. If fe-golden wants its row (name, state, `<time>`,
    "N files · N drawings", `plural`) for screen 5, it imports `plural`/`STATE_LABEL` from `src/ingest/ingest.ts` or
    copies the 30 lines; IN-11 to IN-14 move to account.md.

