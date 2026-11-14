# Ingest: home, project status, file trace (spec, frontend v1)

Status: draft, 2026-11-14, by fe-spec-ingest.  Story: #33.  API: docs/API.md (v1, main 5092dc3).

Names from the shared spec (`docs/specs/frontend/shared.md`) used here: client functions `uploadProject`,
`startSample`, `listProjects`, `getProject`, `getTrace`; URL builders `pageUrl`, `previewUrl`; `useInfo`,
`uploadTooLarge`, `Loading`, `ErrorView`, `<Credit>`, `getDrawing`, `formatTime` (`src/api/format.ts`); test helpers `mockApi` and the typed fixtures of `src/api/fixtures.ts`.

## Purpose

The first three screens a judge sees. Home starts a project (upload one zip or one file, or the sample button) and
lists earlier projects. The project screen follows the ingest live: every file with its state and reason, where the
files are in the pipeline, and one link per drawing into its workspace. The file trace follows one file through every
stage, with what each stage found and how long it took, and shows a normalised image before and after.

## Files owned

All under `frontend/src/ingest/`; each `*.tsx`/`*.ts` with logic has a `*.test.ts(x)` beside it.

| File | What |
| --- | --- |
| `HomeScreen.tsx` | route `#/`, `HomeScreen()`: `UploadBox` + `ProjectList` |
| `UploadBox.tsx` | drop zone, file picker, sample button, client-side size check, upload errors |
| `ProjectList.tsx` | `GET /api/projects` list with its loading, empty and error states |
| `ProjectScreen.tsx` | route `#/p/<project_id>`, `ProjectScreen({projectId})`: header, progress, `StageStrip`, file list, drawing list, polling |
| `StageStrip.tsx` | the pipeline stages with how many files are at each |
| `FileTraceScreen.tsx` | route `#/p/<project_id>/f/<file_id>`, `FileTraceScreen({projectId, fileId})`: file facts, `BeforeAfter`, stage list, takeoff, polling |
| `BeforeAfter.tsx` | the upload (`preview.png`) next to the normalised page, with what normalisation did |
| `ingest.ts` | pure functions: `progressOf`, `stageCounts`, `isFinished`, `normalisedSteps`, `formatMs`, `formatCost`, `formatSize`, `STATE_LABEL`, `STAGE_LABEL` |
| `usePoll.ts` | poll a request 500 ms after each answer while a predicate holds; aborts (`signal`) on unmount |
| `ingest.css` | the screens' styles |

[e2e] criteria are built by the e2e worker (golden-path.md), who owns `frontend/e2e/`. The shell (shared spec)
owns the router, the info banner and the API client; this spec calls the client's functions for the endpoints named
below.

## User flow

1. The user opens `#/`. Home shows a drop zone ("Drop a project here: one .zip, or one plan as PDF, image, IFC, DXF
   or SVG"), a "Choose a file" button, a "Try the sample project" button, and below them the list of earlier projects.
2. The user drops or picks one file. If it is over `limits.upload_mb` the screen says so and sends nothing.
   Otherwise the buttons are disabled, the box shows "Uploading <name>…", and on `202` the app goes to
   `#/p/<id>`. On a phone the picker offers the camera too (`accept` includes `image/*`).
3. Or the user presses "Try the sample project": the box shows "Starting the sample…", and on `202` the app goes to
   `#/p/<id>`.
4. Or the user clicks a project in the list and goes to `#/p/<id>`.
5. The project screen shows the project name, its state, "N of M files finished" with a progress bar, the cost so
   far, the stage strip, the file list and the drawing list. While the project is `queued` or `running` it refreshes
   every 500 ms; rows change state in place, and drawings appear in the drawing list as their files finish.
6. A drawing's "Open" link goes to `#/p/<project_id>/d/<drawing_id>/engineer`. It works as soon as the drawing is
   listed, before the project is `done`.
7. The user clicks a file row and goes to `#/p/<project_id>/f/<file_id>`. The trace shows the file's facts, its
   stages in order with what each did, its output and its time, any failure, and for a normalised image the upload
   next to the normalised page. While the file is `queued` or `running` it refreshes every 500 ms.
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

**`GET /api/projects`** (`listProjects()`; API.md "GET /api/projects"; fixture `project_list.json`). Once when home mounts, and on
Retry. Per project: `name` (row title), `state` (badge), `created_at` (shown with `formatTime`, `YYYY-MM-DD HH:MM UTC`,
inside `<time datetime="<created_at>">`), `files` and `drawings` ("11 files · 5 drawings"), `id` (row link `#/p/<id>`).
Order as given (newest first).

**`GET /api/projects/{project_id}`** (`getProject(projectId)`; API.md "GET /api/projects/{project_id}"; fixture `project.json`). When the
project screen mounts, then 500 ms after each response while `state` is `queued` or `running`. Fields:

- `name`: page title. `state`: the header's state line (`queued` "Waiting to start", `running` "Reading files",
  `done` "Done", `failed` "Ingest failed"). `error`: shown under the state line when `state` is `failed`.
- `cost_usd`: "Cost: $0.00" (`formatCost`). `created_at`: "Started <formatTime(created_at)>".
- `files[]`: progress `progressOf(files)` = files whose `state` is `ready`, `flagged`, `text_only` or `set_aside`,
  over `files.length` ("3 of 3 files finished" and a `<progress>` with that value). Each file is one row, in the
  order given: `path`, `kind` (raw value, or "not identified" when null), `state` (badge, `STATE_LABEL`), `reason`
  (when not empty), `size` (`formatSize`), `ms` (`formatMs`, finished files only), `reused` ("reused" tag when
  true). The row links to `#/p/<project_id>/f/<id>`. The stage strip reads every file's `stage` and `state`.
- `drawings[]`: one row each: `file` (title), `kind`, `route` ("vector route"), `state` (badge),
  `other_renderings[].file` ("also: plans/flat-a.png"), and an "Open" link to
  `#/p/<project_id>/d/<drawing_id>/engineer`.
- `counts`, `readers`, `ms`, and each file's `sha256`, `group`, `source`, `takeoff`, `normalised` are not shown here
  (the trace shows the file ones). The progress comes from `files`, not `counts`, as API.md defines it.

**`GET /api/projects/{project_id}/files/{file_id}/trace`** (`getTrace(projectId, fileId)`; API.md "…/trace"; fixture `trace.json`). When the trace
screen mounts, then 500 ms after each response while `file.state` is `queued` or `running`. Fields:

- `file.path` (title), `file.state` (badge), `file.reason`, `file.kind`, `file.size`, `file.route`, `file.source`
  ("read from plans/flat-a.pdf"), `file.group`, `file.sha256` (first 12 characters, full value in `title`),
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
| Empty | "No projects yet. Upload a file or try the sample." | only once the project is `done` or `failed`: no files: "This upload has no files." No drawings: "No drawings: nothing in this upload could be read as a plan." While `queued` or `running` an empty list gives no verdict: it reads "Waiting for the files…", and with no files yet the progress line is left out (no "0 of 0") | stages `[]`: "No stages yet." | variants `list-empty`, `no-drawings`, `no-files`, `trace-queued`; `queued` with `files: []` |
| Error | box: `detail` and `code` of the upload error; list: `ErrorView` with Retry | first load fails: `ErrorView` (its `not-found` link home) with Retry. A poll fails: the last data stays, labelled "Not updating since <formatTime(now)>: <detail> (<code>)", with Retry that resumes polling | as the project screen, plus "Back to the project" | `mockApi` with `{status: 500, body: error}`; 404 with an unknown id; stop the backend |
| Upload refused | `uploadTooLarge`'s sentence. No request sent | | | a `File` over the limit (component test: `new File` with a stubbed `size`) |
| Busy / too large | box shows `detail` and `code` (`busy`, `too-large`) | | | `mockApi` 429 / 413 with `error.json` spread with that `code` |
| Running | | polling; running files show "running" and their `stage`; the strip marks stages with a working file | polling; stages grow | variant `running` / `trace-running` |
| Failed project | | "Ingest failed" and `error`; polling stopped; files listed as returned | | variant `failed` |
| Set aside | | the row reads "set aside" with its `reason` | the failing stage reads "Failed: <failure>" | variant `set-aside` / `trace-failed` |
| Text only | | the row reads "text only" with its `reason`; no drawing | | variant `text-only` |
| Normalised image | | | `BeforeAfter` | `project.json` file `f2` as the trace's `file` (variant `trace-image`), `trace-rotated` |
| No keys | the shell's "running offline" banner (shared spec); nothing else changes, the sample button works | same | same | `info.json` (`no_keys: true`); the e2e runs on the no-keys backend |

Variants (each starts from the named fixture; only the listed fields change):

| Variant | From | Changes |
| --- | --- | --- |
| `list-empty` | `project_list.json` | `projects: []` |
| `running` | `project.json` | `state: "running"`; `files[2]`: `state: "running"`, `stage: "extract"`, `reason: ""`, `drawing_id: null`; `drawings`: without the entry whose `drawing_id` is the original `files[2].drawing_id` |
| `queued` | `project.json` | `state: "queued"`; every file `state: "queued"`, `stage: null`, `kind: null`, `drawing_id: null`, `reason: ""`; `drawings: []` |
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

Reference: the mock's ingest screen (`demo/`, landing drop box, then the run view with its header, progress ring,
stats row and pipeline timeline).

**Desktop 1440x900.** Content column max 1120 px, centred.
- Home: the drop zone across the column (about 220 px tall) with the two buttons inside it, as the mock's landing;
  the project list below it as a table (name, state, started, files · drawings).
- Project: a header block (name as `h1`, state line, `error` when failed, "Started …", "Cost: …") with the progress
  bar and "N of M files finished" on its right, as the mock's run header and ring. Under it the stage strip as one
  row of stage chips (it wraps). Under that two columns: the file list (left, about two thirds; a table: path,
  kind, state, reason, size, time) and the drawing list (right, one third; cards with "Open").
- Trace: a "Back to the project" link, then the header (path as `h1`, state badge, reason, "Open the drawing"), a
  facts list (kind, size, route, read from, group, sha256, time, cost) in two columns, `BeforeAfter` with the two
  images side by side at equal width, the stage list as a vertical timeline (label, did, output, time on the right),
  then the takeoff `<details>`.

**Phone 390x844.** One column, 16 px gutters, no horizontal page scroll.
- Home: the drop zone shrinks to the buttons ("Choose a file" first, it opens the camera or the files), the list
  as stacked rows.
- Project: header; progress bar full width; the stage strip as a vertical list (one line per stage: label, count,
  "working"); drawings before files (the next action is opening a drawing); each file a card: path (wraps, breaks
  long names), then badge and kind, then reason.
- Trace: facts as label/value pairs, images stacked, stage items full width.
- Tap targets at least 44 px tall; long paths and reasons wrap (`overflow-wrap: anywhere`), never overflow.

Status badges always carry the word and an icon (ready ✓, flagged !, set aside –, text only ¶, queued …, running ◌);
colour is extra. Stage strip: a working stage shows a spinner and the word "working".

## Acceptance criteria

Home and upload

- IN-1: `#/` renders the drop zone, a "Choose a file" control and a "Try the sample project" button. [component]
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

- IN-11: Home requests `GET /api/projects` once on mount and shows "Loading projects…" until it answers.
  [component]
- IN-12: Each project of `project_list.json` is a row with its `name`, state word, a `<time>` whose `datetime` is
  `created_at`, and "11 files · 5 drawings"; the row links to `#/p/<id>`. [component]
- IN-13: `list-empty` shows "No projects yet. Upload a file or try the sample." [component]
- IN-14: A failed list request shows `detail` and `code`; Retry requests the list again. [component, 500 +
  `error.json`]

Project screen

- IN-15: `#/p/<id>` requests `GET /api/projects/<id>` and shows "Loading project…" until the first answer.
  [component]
- IN-16: With `project.json` the header shows the `name`, "Done", "Cost: $0.00" and "3 of 3 files finished", and
  the `<progress>` has value 3 and max 3. [component]
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
- IN-29: A first load answered 404 `not-found` shows `ErrorView` with `detail`, `code` and its link to `#/`; a
  first load that fails with `code` `network` shows Retry, which requests the project again. [component,
  `error.json`, rejected fetch]

Stage strip

- IN-30: The strip lists, in this order, unpack, hash, identify, group, route, cache, normalise, extract, second
  count, takeoff, write, each with the number of files whose `stage` is that stage; files with `stage: null` are
  counted as "waiting" before the first stage. [unit `stageCounts` + component, `project.json`, `queued`]
- IN-31: With `running`, the `extract` chip shows the word "working" (and its icon); with `project.json` no chip
  does. [component]
- IN-51 (R2 qa-3 d): When the Cache chip's count is above 0, one line under the strip reads "Each file is counted at
  its last stage. A reused file stops at Cache: an earlier upload already wrote its drawing."; with a Cache count of
  0 (`project.json`) the line is absent. [component, `project.json` with every file `stage: "cache"`,
  `reused: true`]

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

Across the screens

- IN-44: Strings from files (`path`, `name`, `reason`, `did`, `output`, `failure`, `error`, takeoff keys) render as
  text: a `reason` of `<img src=x onerror=alert(1)>` shows those characters and adds no element. [component,
  variant with that `reason`]
- IN-45: No state is shown by colour alone: every badge and the working/failed markers contain their word.
  [component: text query on each state variant]
- IN-46: On the no-keys backend: "Try the sample project" reaches `#/p/<id>`, the project reaches "Done", every
  row has a state word, clicking `plans/flat-a.pdf` shows its trace with the `write` stage, and its "Open the
  drawing" reaches the engineer route. [e2e]
- IN-47: At 390x844 and 1440x900 the three screens (home, sample project done, the `plans/flat-a.png` trace) have
  no horizontal page scroll, and a screenshot of each is saved. [e2e]
- IN-49 (R1-1-4): While the project is `queued` or `running`, an empty file or drawing list reads "Waiting for the
  files…", never "This upload has no files." or "No drawings: …", and with no files the progress line ("0 of 0")
  is not shown. [component, `queued` with `files: []`, `running` with `drawings: []`]
- IN-50 (R1-1-1): Counts are singular for 1 and plural otherwise: "1 file · 1 drawing", "0 files · 2 drawings",
  "1 of 1 file finished", "What it ends as: 1 quantity". [unit `plural` + component]

## Out of scope

- Upload progress in bytes (fetch gives none; would need XMLHttpRequest).
- More than one file per upload (zip them), folder drops, resuming an upload.
- The mock's per-stage explanations (click a stage for what/how/output/failure) and its live stats row (elapsed,
  remaining).
- The mock's end-of-ingest conflict list with approve / modify / pick a variant: conflicts live in the surveyor
  workspace (`GET /api/projects/{id}/review` is the surveyor spec's).
- Showing `readers`, `counts`, project `ms` and the drawing model on these screens.
- A preview of files with no drawing (a set-aside photo); `preview.png` exists for them but nothing links it here.
- Deleting or renaming projects (no endpoint), refreshing the project list on a timer.

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
