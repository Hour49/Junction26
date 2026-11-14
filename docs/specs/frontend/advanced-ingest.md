# Advanced ingest: the pipeline stage by stage (spec, Vellum round)

Status: draft, 2026-11-14, by fe-scaffold for frontend-orch. Screens 9-12 of Tudor's "Vellum redesign" canvas
(`IngestUnpack`, `IngestIdentify`, `IngestExtract`, `IngestCheck`). API: docs/API.md (v1, main eb3552c).

Names from the shared spec (`docs/specs/frontend/shared.md`) and the ingest spec used here: client functions
`getTrace`, `getTakeoff`, `getDrawing`; URL builders `pageUrl`, `previewUrl`; `Loading`, `ErrorView`; formatters
`formatValue`, `readerName`, `methodName` (`src/api/format.ts`) and `STAGES`, `STAGE_LABEL`, `STATE_LABEL`,
`isFinished`, `plural`, `formatMs`, `formatCost`, `formatSize`, `normalisedSteps` (`src/ingest/ingest.ts`, imported,
not edited); `StateBadge` (`src/ingest/ProjectScreen.tsx`); test helpers `mockApi` and the fixtures of
`src/api/fixtures.ts`. Design tokens: only the `--v-*` custom properties of `src/shell/shell.css`.

## Purpose

The Advanced tab of the project screen shows what the pipeline did to the upload, step by step, for a reader who
wants to see the machinery: a rail of eight steps, and for the chosen step a "Now" panel that explains the step in
one sentence, shows what it is working on (or worked on), lists the trace lines it wrote, and four numbers. The four
designs are one component: the rail picks the panel. Everything shown comes from the polled `ProjectView`, the
per-file traces, and (for the last steps) each drawing's takeoff and suggestions. No animation pretends to work
that is not happening.

## Files owned

All under `frontend/src/advanced/` (new folder); each file with logic has a `*.test.ts(x)` beside it.

| File | What |
| --- | --- |
| `AdvancedIngest.tsx` | `export function AdvancedIngest(props: { projectId: string; project: ProjectView }): JSX.Element` (signature fixed by the common brief). Rail + panel + stats; owns the selected step. |
| `StageRail.tsx` | the eight steps as a `<nav aria-label="Steps">` of buttons with their status |
| `NowPanel.tsx` | heading, status, explanation, live line, log; renders the step's visual |
| `visuals.tsx` | the four visuals: `FileStrip` (Unpack), `RouteLanes` (Identify, Route), `PlanMarks` (Normalise, Extract, Drawing model), `CheckPairs` (Cross-check), `ReadyList` (Index) |
| `advanced.ts` | pure: `STEP_VIEW` (heading, visual, explanation per step), `stepStatus`, `currentStep`, `defaultStep`, `stepLines`, `stepStats`, `planCounts`, `pairsOf`; `STEPS`, `stepOf`, `activeStep` come from `src/ingest/ingest.ts` |
| `useTraces.ts` | fetch each file's trace when it changes, at most 4 in flight, aborted on unmount |
| `useDrawingData.ts` | fetch each drawing's takeoff and `DrawingView` once, when a step that needs them is shown |
| `advanced.css` | layout from the designs, `--v-*` tokens only |

`ProjectScreen` (fe-ingest) owns the Simple/Advanced toggle, `?view=advanced` and polling, and passes `project`.
`AdvancedIngest` never polls the project itself.

## The steps

The rail is the same 8 steps as screen 2's step list: `STEPS` and `stepOf` from `src/ingest/ingest.ts` (fe-ingest,
ingest.md IN-56, imported, not redefined), in the API's stage order, so the two views never disagree. This spec adds
per step only the heading, the visual and a longer explanation:

| # | Step (`STEPS`) | API stages (`stepOf`) | Heading | Visual | Explanation (fixed text, true for the backend today) |
| --- | --- | --- | --- | --- | --- |
| 1 | Unpack | `unpack`, `hash`, null | Unpacking | `FileStrip` | "Every file in the upload is listed with its size and sha256, and every path is checked to stay inside the project folder." |
| 2 | Identify | `identify`, `group` | Identifying | `RouteLanes` | "The format comes from each file's first bytes, not its name. Files with the same folder and name are one plan." |
| 3 | Route | `route`, `cache` | Routing | `RouteLanes` | "Each plan is read from its richest file: a BIM model, then CAD, then a drawn PDF, then an image. A file read before is reused." |
| 4 | Normalise | `normalise` | Normalising | `PlanMarks` | "Each sheet gets one page frame, and every mark and box is placed in it." |
| 5 | Extract | `extract` | Extracting | `PlanMarks` | "Rooms, doors, windows and fixtures are read from the drawing, with its scale. A class the reader does not read gets no count, not a zero." |
| 6 | Cross-check | `second_count` | Cross-checking | `CheckPairs` | "Quantities that can be measured a second way are measured again by an independent method. When the two disagree, it goes to you as a conflict." |
| 7 | Index | `takeoff` | Indexing | `ReadyList` | "The counting rules are applied and every quantity of the plan is computed in advance, so questions are answered from it straight away." |
| 8 | Drawing model | `write` | Storing the drawing model | `PlanMarks` | "One drawing model per plan is stored, with the marks that show where each quantity comes from." |

The design puts Drawing model before Cross-check and Index; the backend runs `second_count`, `takeoff`, `write`.
Following the backend (ingest.md open point 12) keeps a step from reading "waiting" after a later one is "done".

### Step status (from `project.files` alone, no trace needed)

`project.files[].stage` is "the stage a running file is in, or the last one it finished" (API.md). Let `n(f)` be
`stepOf(f.stage)` (1 for null). An unfinished file has `state` `queued` or `running` (`isFinished` false). For step
`k`:

- `working`: some unfinished file has `n(f) = k`.
- `waiting`: not working, and some unfinished file has `n(f) < k`.
- `done`: neither, and at least one file has `n(f) >= k` with a non-null `stage`.
- `none`: neither, and no file got to step `k`: "No file got here" (e.g. Normalise when every file was set aside at
  Route). This is the one status screen 2 does not have; its list shows such a step as done once the project is.
- A step also carries `setAside`: the number of `set_aside` files whose `stage` is one of its stages ("2 set aside
  here"); text, not only colour.

`currentStep`: while `project.state` is `queued` or `running`, ingest.md's `activeStep(files)` (the lowest `n(f)` among
unfinished files, 1 with no files); `null` when `done` or `failed`.

`defaultStep`: `currentStep` when set, else Index (step 7, what is ready to ask). The user's pick (a click on the rail) overrides it and stays
while the project updates; the panel does not follow the pipeline after a click (no jumping under the reader).

## API calls

**`project: ProjectView`** (prop, polled by `ProjectScreen`; API.md "GET /api/projects/{project_id}", fixtures
`project.json`, `project_running.json`, `project_failed.json`). Read: `state`, `error`, `ms`, `cost_usd`, `files[]`
(`id`, `path`, `size`, `kind`, `state`, `reason`, `stage`, `route`, `source`, `drawing_id`, `normalised`, `takeoff`,
`reused`), `drawings[]` (`drawing_id`, `file`, `kind`, `route`, `state`), `readers`.

**`GET /api/projects/{project_id}/files/{file_id}/trace`** (`getTrace`; fixture `trace.json`, `trace_set_aside.json`).
`useTraces` requests a file's trace when the key `id|state|stage` of that file is new and `stage` is not null, so a
finished file is fetched once and a running one at most once per stage it enters (≤ 11 per file). At most 4
requests in flight; the rest wait in file order. An unmount aborts them. A failed request keeps the last trace of
that file, marks it failed, and offers "Retry" on its log line; it never blocks the other files. Read: `stages[]`
(`stage`, `did`, `output`, `ms`, `failure`, `cost_usd`).

**`GET /api/drawings/{drawing_id}/takeoff`** (`getTakeoff`; fixture `takeoff.json`). Once per entry of
`project.drawings` whose file is finished, the first time Normalise, Extract, Cross-check or Drawing model is
shown (Index needs no takeoff: its counts come from `files[].takeoff`). Read: `quantities[]` `key`, `label`, `unit`, `status`, `first`, `second` (`method`, `value`), `marks[]`
(`box`, `page`, `label`, `state`).

**`GET /api/drawings/{drawing_id}`** (`getDrawing`; fixture `drawing.json`). Once per drawing, the first time
Index is shown. Read: `suggestions[].label`, `pages.length`.

**`pageUrl(drawingId, 1)`**, **`previewUrl(projectId, fileId)`**: plain `<img src>`; a failed load shows "Page not
available" / "Preview not available" in its place, as the ingest screens do.

## Layout (per design screen)

Common to all four: page title and Simple/Advanced toggle belong to `ProjectScreen` (not drawn here). Below them:

1. **Rail** (`<nav aria-label="Steps">`, 8 columns on a `--v-line`-tinted track, 4 × 2 under 760 px): each step a
   `<button>` with a status ring and its label. Status shown by icon and a visually hidden word: done ✓ ("done"),
   working pulsing dot ("working", pulse off under reduced motion), waiting empty ring ("waiting"), none dash ("no
   file got here"), and "· N set aside" when `setAside > 0`. The selected step is raised (white, shadow) with
   `aria-pressed="true"`; the pipeline's current step has `aria-current="step"`. Min height 44 px.
2. **Panel** (`<section aria-label="<Heading>">`, white card, `--v-radius`, `--v-shadow`): left the visual (flex
   999 1 520px), right the text column (flex 1 1 300px); they stack under ~860 px.
   - Status line: when the step is `currentStep`, a spinner and "Now"; else "Done", "Waiting", or "No file got here".
   - `<h2>` the heading from the step table.
   - The explanation sentence (fixed text above).
   - The live line (`aria-live="polite"` only while the step is current): `"<path>: <did>"` of the last trace line of
     this step in file order; "Nothing yet." when the step has no line.
   - **Log** (`<ol aria-label="Log">`, mono, `--v-bg` box, scrolls past 8 lines, `tabindex="0"`): `stepLines`, one
     `<li>` per trace entry of this step's stages over all files, in file order then stage order: `<STAGE_LABEL>
     <path> <output, or did when output is empty>`; `cache` lines read "Cached: <did>"; `cost_usd > 0` adds
     `formatCost`; `failure` lines read "✕ Failed: <failure>" (icon and word). Lines of a file whose trace failed
     to load: "Trace of <path> not loaded." + "Retry" button. While traces load and no line exists: "Loading the
     trace…".
3. **Stats** (`<dl>`, 4 cells, 2 × 2 under 760 px), per step below.

### Screen 9, Unpack (`IngestUnpack`)

- Visual `FileStrip`: a dark `--v-text` band with a horizontal, scrollable (`tabindex="0"`, `aria-label="Files in
  this upload"`) row of file cards in `project.files` order: path, `formatSize(size)`, kind word (or "not
  identified"), `StateBadge`. A drawing file's card shows `pageUrl(drawing_id, 1, 400)` as its thumbnail; other
  cards show none. The card of the file the step is working on (unfinished, its stage in the step) is framed, as
  the design frames the centre. No auto-scrolling film: the band scrolls by hand.
- Caption (mono, under the band): while working, `"<path> · <formatSize(size)>"` of that file; else
  `plural(files.length, 'file')`, total `formatSize` of all files.
- Stats: **Time** (`formatMs(project.ms)` when `done`/`failed`, "running" otherwise), **Files opened**
  (`files with stage != null` / `files.length`), **Set aside** (files `state === 'set_aside'`), **Cost**
  (`formatCost(project.cost_usd)`).

### Screen 10, Identify and Route (`IngestIdentify`)

- Visual `RouteLanes`: on top a file view: a `<select aria-label="File">` over `project.files` (default: the file the
  step works on, else the first file with a `route`), its `previewUrl` image, and chips over the image's bottom
  edge from real fields only: kind word, `"<normalised.width> × <normalised.height> px"` when `normalised`,
  `"route <route>"`, `"read from <source>"` when `source` differs from `path`, `reused` → "read before". Below, two
  lanes, as the design's "CAD geometry" and "Vision model" boxes, named for what runs:
  - **"Exact geometry"**: routes `bim`, `cad`, `vector`; under it the readers `readerName(readers.bim)`,
    `readerName(readers.cad)`, `readerName(readers.vector)` and the count of files routed there.
  - **"From the image"**: route `raster`; under it `readerName(readers.raster)` and its count. A reader id `hello`
    reads "not read", as `readerName` says everywhere (API.md: `hello` reads nothing); never "vision model" unless
    the reader is one.
  - The selected file's lane is marked (`aria-current="true"`, border `--v-accent`) and says "This file goes here";
    a file with no route says "Not routed: <reason>".
- Stats: **Time**, **Exact geometry** (count), **From the image** (count), **Set aside** (set_aside files whose
  stage is in Identify or Route).

### Screen 11, Normalise, Extract, Drawing model (`IngestExtract`)

- Visual `PlanMarks`: a `<select aria-label="Drawing">` over `project.drawings` (default the first; label `file`).
  For a drawing with pages: `pageUrl(drawing_id, 1)` in a `position: relative` box, an SVG overlay `viewBox="0 0 1
  1"` `preserveAspectRatio="none"` with one rect per mark of the takeoff rows keyed `room`, `door`, `window` (page 1,
  `state` not `rejected`), and a label pill with `mark.label` for room marks (text node, never HTML). The sweep line
  animates only while Extract is `working`; off under reduced motion. An IFC drawing without pages: "A model, no
  sheet to show" and its counts. Normalise selected: under the image, `normalisedSteps(file.normalised)` of the
  drawing's file, or "Pages as the file gives them" for a PDF.
- Stats (`planCounts`, summed over `project.drawings`, each drawing's file's `takeoff`, so a PNG beside its PDF is
  not counted twice): **Rooms** (`takeoff.room`), **Doors** (`takeoff.door`), **Windows** (`takeoff.window`), and
  **Drawings** (`drawings.length`). A key no drawing has shows "–" with the visually hidden "not read", never 0.

### Screen 12, Cross-check and Index (`IngestCheck`)

- Visual `CheckPairs` (Cross-check): `pairsOf(takeoffs)`, every row with `second` set, conflicts first, then the rest
  in takeoff order. Each pair as the design's card: left "From the drawing" `formatValue(first.value, unit)` and
  `methodName(first.method)`; right "Second count" `formatValue(second.value, unit)` and
  `methodName(second.method)`; above, `label` and the drawing's `file`; below, the verdict: `agree` → "They agree.
  Kept as the answer."; `conflict` → "They disagree. Sent to Settle the conflicts." with a link to
  `#/p/<projectId>/conflicts`; any other `status` → its word (`signed`, `edited`, `estimate`, `single`). Verdicts
  carry an icon and words, colour (`--v-ok`, `--v-warn-soft`) only adds. No pairs: "Nothing on these drawings can be
  measured a second way yet."
- Visual `ReadyList` (Index): "Answers ready before you ask", per drawing: its `file`, `plural(n, 'quantity',
  'quantities')` with `n` = keys of its file's `takeoff`, then the `suggestions[].label` of its `DrawingView` as a
  list, each with a filled dot when the drawing's file is `ready` or `flagged`, and a link "Ask this drawing" to
  `#/p/<projectId>/d/<drawing_id>/engineer`. No drawings: "No drawing to ask yet."
- Stats: **Time**, **Measured twice** (pairs), **Agree** (`status === 'agree'`), **Conflicts** (`status ===
  'conflict'`). While takeoffs load: "…" in the three; a takeoff that failed: "–" and the panel's error line.

## States

| State | What shows | Reach it on purpose |
| --- | --- | --- |
| Running | rail with `currentStep` marked and selected; panel "Now"; log grows as traces come | `project_running.json`; mocked traces per stage |
| Done | every reached step ✓; Index selected; Time = `project.ms` | `project.json` + `trace.json` |
| Failed project | rail statuses as computed; panel as for done; `project.error` is shown by `ProjectScreen`, not here | `project_failed.json` |
| No files | `files: []`: rail all "waiting" while queued/running, all "no file got here" when done; panel log "Nothing yet." | `queued` with `files: []` |
| Trace loading | log "Loading the trace…" | pending `getTrace` |
| Trace error | that file's line "Trace of <path> not loaded." + Retry; other files' lines show | `getTrace` rejects for one file |
| Takeoff/drawing error | panel line "Could not load the takeoff of <file>." + Retry (`ErrorView` compact); stats "–" | `getTakeoff` rejects |
| Set aside | rail "· N set aside" on the step; log "✕ Failed: …" when the stage failed | `trace_set_aside.json` |
| 390 px | rail 4 × 2, panel stacked (visual above text), stats 2 × 2, file strip scrolls, no horizontal page scroll | e2e at 390×844 |
| Reduced motion | no pulse, spinner, sweep or fade | `prefers-reduced-motion: reduce` |

## Acceptance criteria

Rail and steps

- AV-1: The rail shows 8 buttons in a `nav` named "Steps", with the names of `STEPS` in its order: Unpack, Identify,
  Route, Normalise, Extract, Cross-check, Index, Drawing model. [component]
- AV-2: `STEP_VIEW` has a heading, visual and explanation for each of the 8 steps, and `advanced.ts` defines no
  stage-to-step table of its own (it imports `stepOf`). [unit]
- AV-3: `stepStatus` gives working / waiting / done / none per the rules above, including: a finished file whose
  `stage` is `route` (set aside there) does not make later steps `waiting`; a reused file with `stage: write` marks
  every step done. [unit, `project.json`, `project_running.json`]
- AV-4: With `project_running.json`, the current step's button has `aria-current="step"` and is selected; no other
  button has `aria-current`. With `project.json` (done), no button has it and Index is selected. [component]
- AV-5: A click on a step selects it (`aria-pressed="true"`), shows its heading, and the selection stays when a new
  `project` prop arrives with a different current step. [component, rerender]
- AV-6: Each step's status is readable without colour: its accessible name includes "done", "working", "waiting" or
  "no file got here", and "N set aside" when there are any. [component]

Panel and log

- AV-7: The panel shows the step's heading and fixed explanation; the status line reads "Now" only for
  `currentStep`. [component]
- AV-8: The log lists, for the selected step, one line per trace entry of its stages over all files in file order;
  a `failure` line reads "Failed: <failure>" with an icon; a `cache` line reads "Cached: <did>". [component,
  `trace.json`, `trace_set_aside.json`]
- AV-9: Trace strings (`path`, `did`, `output`, `failure`, `mark.label`, `suggestions[].label`) render as text: a
  value `<img src=x onerror=alert(1)>` appears literally and adds no element. [component]
- AV-10: `useTraces` requests each file's trace once per new `id|state|stage`, never for a file with `stage: null`,
  never more than 4 at once, and aborts in-flight requests on unmount. [component, `mockApi` call log]
- AV-11: A trace request that fails shows "Trace of <path> not loaded." with a Retry button that requests it again;
  the other files' lines still show. [component]
- AV-12: The live line has `aria-live="polite"` only while the selected step is the current step. [component]

Visuals and stats

- AV-13: Unpack stats: Files opened `"<with stage> / <all>"`, Set aside = set_aside files, Cost =
  `formatCost(project.cost_usd)`, Time = `formatMs(project.ms)` when done and "running" while running. [component]
- AV-14: The file strip lists every file with path, size and state word, and is keyboard scrollable. [component]
- AV-15: Identify/Route lanes count files by route (bim+cad+vector vs raster) and show the reader names from
  `project.readers` via `readerName`; reader `hello` reads "not read"; the words "vision model" appear nowhere unless a reader
  says so. [component]
- AV-16: The selected file's lane is marked `aria-current="true"` and says "This file goes here"; a file without
  route says "Not routed: <reason>". [component]
- AV-17: `planCounts` sums `room`, `door`, `window` over `project.drawings` only (other renderings not counted twice);
  a key no drawing has gives "–", not 0. [unit, `project.json`: flat-a.png is not added to flat-a.pdf]
- AV-18: The plan view draws one rect per non-rejected page-1 mark of the `room`, `door` and `window` rows of the
  selected drawing's takeoff, at `box` fractions in a `0 0 1 1` viewBox. [component, `takeoff.json`: the `door` row's
  2 marks]
- AV-19: Cross-check lists every takeoff row with `second` set, conflicts first; a conflict links to
  `#/p/<projectId>/conflicts`; Agree and Conflicts stats count `status` `agree` and `conflict`. [unit + component,
  `takeoff.json`: one pair, `area:room|name=1.01`, 22.4 vs 30.0, conflict]
- AV-20: Index lists each drawing with its quantity count and its `suggestions[].label`, and links "Ask this
  drawing" to `#/p/<projectId>/d/<drawing_id>/engineer`. [component, `drawing.json`]
- AV-21: Takeoffs and drawings are requested once per drawing, only after a step that needs them is first shown;
  a failure shows its error line with Retry and "–" in the dependent stats. [component]
- AV-22: No value from the design mock appears (no "harbour-block", "1948", "Swedish", "Beatrice", no country
  picker, no "Remaining"). [component: render with fixtures, assert absent]

Layout and access

- AV-23: At 390 px the rail is 4 columns, the stats 2 columns, and the page has no horizontal scroll; at 1440 px
  the rail is one row of 8. [e2e, fe-golden adds the step to the golden path if wanted]
- AV-24: Under `prefers-reduced-motion: reduce` no element in `src/advanced/` animates (CSS rule present; the
  classes `pulse`, `spin`, `sweep`, `live` set `animation: none`). [unit on the CSS text, or e2e emulation]
- AV-25: CSS in `advanced.css` uses only `--v-*` tokens for colour (no hex or rgb literal). [unit: grep the file]

## Not in the API

Shown as nothing until Bogdan answers on #14 (frontend-orch collects these). Each with the field that would fill it:

1. **Remaining time** (design: "Remaining ~12 s"): `ProjectView.eta_ms: number | null`.
2. **Elapsed while running** (design: "Elapsed 2 s"): `project.ms` is set only when the run ends
   (`service.py` `set_project`), so the cell reads "running". Needs `ProjectView.started_at` (ISO) or a live `ms`.
3. **Order of events in time** (design: the log is "newest first"): traces have no time. Needs `StageTrace.at` (ISO
   UTC). Until then the log is in file order.
4. **One request for the whole log**: today one trace request per file (≤ 11 per file while running). A project
   trace (`GET /api/projects/{id}/trace` → `FileTrace[]`, or `stages` on `FileStatus`) would replace them.
5. **Identify chips** (design: "Pencil on paper · 1948", "Labels in Swedish", "Scale 1:100 found"): no medium, year
   or label language on a file, and the scale is read in Extract, not exposed on `ProjectView`/`DrawingView`. Needs
   `FileStatus.identified: {medium, year, language}` and `PageView.scale: {ratio, source}`.
6. **Skipped system files** (design: "Skipping system files like __MACOSX"): whether and how many entries unpack
   skipped is not reported. Needs `ProjectView.skipped: [{path, reason}]` (or those files as `set_aside`, if they are).
7. **Structured second count per file** (design: Agree 31 / Conflicts 3 during the run): the `second_count` trace
   line is free text ("5 quantities measured twice, 0 conflict(s)"); the numbers come only from each drawing's
   takeoff once written. Needs `FileStatus.second_count: {measured, conflicts}`.
8. **Room label meaning** (design: "“Kök” is the kitchen"): a mark has `label` but not the room type it was read
   as. Needs `MarkView.room_type` (the `room:<type>` class).
9. **An "Index" stage**: the backend has none; screen 2 and this spec show `takeoff` as Index and the drawing's
   `suggestions` as "answers ready". Confirm that reading with Bogdan, or a stage name.

## Out of scope

The page header, title and Simple/Advanced toggle (fe-shared, fe-ingest); `FileTraceScreen` and `StageStrip`
(fe-ingest, read only); the country picker and the user avatar (common brief); the archive plan images of the
design (never shown: the project's own pages are); animated film strip and cycling mock pairs (the panels show the
real list instead).

## Open points

- **Rail order and mapping**: taken from ingest.md (`STEPS`, `stepOf`, open point 12), not decided here. If the orch
  changes it there, the rail follows without a change in `src/advanced/`. Build order: fe-ingest's `STEPS` export
  must exist before AV-1/AV-2 can pass; until then AdvancedIngest tests import it from the same path and fail red.
- **Status `none`**: the Advanced rail has a fourth status, "No file got here", that screen 2's list lacks. Fine, or
  should both show it?
- **Request load**: Index needs one `GET /api/drawings/{id}` per drawing and Extract/Cross-check one takeoff per
  drawing; with the sample (≤ 10 drawings) that is fine; a large zip would want item 4 above.
