# Advanced ingest: the pipeline stage by stage (spec, Vellum round)

Status: draft, 2026-11-14, by fe-scaffold for frontend-orch; v4 steps (9, named after the backend's stages, per-route lines, AV-45..AV-48) by m3d-front for w3:p1, 2026-11-14 23:55 (ingest.md "Pipeline steps v4"). Screens 9-12 of Tudor's "Vellum redesign" canvas
(`IngestUnpack`, `IngestIdentify`, `IngestExtract`, `IngestCheck`). API: docs/API.md (v1, main eb3552c).

Names from the shared spec (`docs/specs/frontend/shared.md`) and the ingest spec used here: client functions
`getProjectTrace`, `getTakeoff`, `getDrawing`; URL builders `pageUrl`, `previewUrl`; `Loading`, `ErrorView`; formatters
`formatValue`, `readerName`, `methodName` (`src/api/format.ts`) and `STAGES`, `STAGE_LABEL`, `STATE_LABEL`,
`isFinished`, `plural`, `formatMs`, `formatCost`, `formatSize`, `normalisedSteps` (`src/ingest/ingest.ts`, imported,
not edited); `StateBadge` (`src/ingest/ProjectScreen.tsx`); test helpers `mockApi` and the fixtures of
`src/api/fixtures.ts`. Design tokens: only the `--v-*` custom properties of `src/shell/shell.css`.

## Purpose

The Advanced tab of the project screen shows what the pipeline did to the upload, step by step, for a reader who
wants to see the machinery: a rail of nine steps, and for the chosen step a "Now" panel that explains the step in
one sentence, shows what it is working on (or worked on), lists the trace lines it wrote, and four numbers. The four
designs are one component: the rail picks the panel. Everything shown comes from the polled `ProjectView`, the
per-file traces, and (for the last steps) each drawing's takeoff and suggestions. No animation pretends to work
that is not happening.

## Files owned

All under `frontend/src/advanced/` (new folder); each file with logic has a `*.test.ts(x)` beside it.

| File | What |
| --- | --- |
| `AdvancedIngest.tsx` | `export function AdvancedIngest(props: { projectId: string; project: ProjectView }): JSX.Element` (signature fixed by the common brief). The rail (`<nav aria-label="Steps">`), the panel (heading, status, explanation, live line, log, visual) and the stats; owns the selected step. |
| `visuals.tsx` | the visuals: `FileStrip` (Unpack, Index), `RouteLanes` (Identify, Route), `PlanMarks` (Normalise, Extract, Store), `CheckPairs` (Second count), `ReadyList` (Takeoff) |
| `advanced.ts` | pure: `STEP_VIEW` (heading, visual, explanation and per-route lines per step), `routeLines`, `stepStatus`, `currentStep`, `defaultStep`, `stepLines`, `stepStats`, `planCounts`, `pairsOf`, `elapsedMs`, `scaleChip`; `STEPS`, `stepOf`, `activeStep` come from `src/ingest/ingest.ts` |
| `useProjectTrace.ts` | fetch the project's one trace when any file changes, aborted on unmount |
| `useDrawingData.ts` | fetch each drawing's takeoff and `DrawingView` once, when a step that needs them is shown |
| `advanced.css` | layout from the designs, `--v-*` tokens only |

`ProjectScreen` (fe-ingest) owns the Simple/Advanced toggle, `?view=advanced` and polling, and passes `project`.
`AdvancedIngest` never polls the project itself.

## The steps

The rail is the same 9 steps as screen 2's step list: `STEPS` and `stepOf` from `src/ingest/ingest.ts` (fe-ingest,
ingest.md IN-56 and "Pipeline steps v4", imported, not redefined), in the backend's stage order, so the two views never
disagree. This spec adds per step only the heading, the visual, a longer explanation and, where the routes differ,
one line per route:

| # | Step (`STEPS`) | API stages (`stepOf`) | Heading | Visual | Explanation (fixed text, true for the backend today) |
| --- | --- | --- | --- | --- | --- |
| 1 | Unpack | `unpack`, `hash`, null | Unpacking | `FileStrip` | "Every file in the upload is listed with its size and sha256, and every path is checked to stay inside the project folder. Each drawn page of a PDF set becomes a file of its own." |
| 2 | Identify | `identify` | Identifying | `RouteLanes` | "The format comes from each file's first bytes, not its name. A picture is asked whether it is a floor plan: a doubtful sheet is read and flagged, anything else is set aside with a description." |
| 3 | Route | `group`, `route`, `cache` | Routing | `RouteLanes` | "Files of the same plan are grouped, and each plan is read once from its richest file: an IFC model, then CAD, then a drawn PDF, then an image. A scanned PDF is read as an image. A plan read before is reused." |
| 4 | Normalise | `normalise` | Normalising | `PlanMarks` | "Each sheet gets one page frame, and every mark and box is placed in it." |
| 5 | Extract | `extract` | Extracting | `PlanMarks` | "Rooms, doors, windows and fixtures are read from the drawing, with its scale. A class the reader does not read gets no count, not a zero." |
| 6 | Second count | `second_count` | Counting a second way | `CheckPairs` | "Quantities that can be measured a second way are measured again by an independent method. When the two disagree, it goes to you as a conflict." |
| 7 | Takeoff | `takeoff` | Working out the quantities | `ReadyList` | "The counting rules are applied and every quantity of the plan is computed in advance, with the marks it comes from, so questions are answered from it straight away." |
| 8 | Store | `write` | Storing the drawing model | `PlanMarks` | "One drawing model per plan is stored, with the marks that show where each quantity comes from." |
| 9 | Index | none (the project's last phase) | Indexing for questions | `FileStrip` | "Once every file is through, each set-aside file is judged against the project, the files that are not plans are described or their text read, and everything goes into the project's search index for the chat." |

Per-route lines (`STEP_VIEW[k].routes`), shown under the explanation as a list, "**<routeLabel>:** <line>", only for routes
some file of the project is on (`files[].route`), in the order BIM model, CAD, drawn PDF, image:

| Step | BIM model (`bim`) | Drawn PDF (`vector`) | Image (`raster`) |
| --- | --- | --- | --- |
| Normalise | "A model has no page: nothing to place." | "Pages are taken as the PDF gives them." | "Turned upright by its EXIF tag; a phone photo is flattened to its paper's corners." |
| Extract | "Every object is listed with its GlobalId: spaces, storeys, doors, windows, fixtures." | "Read from the PDF's text and lines: rooms with areas, doors, windows, fixtures, the printed scale and schedule tables." | "A symbol detector and room readers read it; a large or sparse sheet is also counted by Gemini Carbon and flagged; more readers count again to set each count's level." |
| Second count | "A model is what the sheets are checked against; it has no second count of its own." | "The scale text against the scale bar, the room areas printed on the sheet, and the sheet against its IFC model." | "The printed scale and any printed totals against what was read." |

(CAD has no line: no CAD reader runs today.)

Following the backend (ingest.md open point 12) keeps a step from reading "waiting" after a later one is "done".
Not steps (they do not run at ingest): the conflict resolver, the IFC fact sheet, the 3D view's GLB.

### Step status (from `project.files` alone, no trace needed)

`project.files[].stage` is "the stage a running file is in, or the last one it finished" (API.md). Let `n(f)` be
`stepOf(f.stage)` (1 for null). An unfinished file has `state` `queued` or `running` (`isFinished` false). For step
`k`:

- `working`: some unfinished file has `n(f) = k`.
- `waiting`: not working, and some unfinished file has `n(f) < k`, or the project is `queued`/`running` and no
  file got to step `k` yet.
- `done`: neither, and at least one file has `n(f) >= k` with a non-null `stage`.
- `none`: neither, the project is `done` or `failed`, and no file got to step `k`: "No file got here" (e.g. Normalise when every file was set aside at
  Route). This is the one status screen 2 does not have; its list shows such a step as done once the project is.
- Index (no stage): `working` while the project is `queued`/`running`, has files and every file is finished;
  `waiting` while it runs otherwise; `done` when the project is `done` with files; `none` when `failed` or done with
  no file; `setAside` 0.
- A step also carries `setAside`: the number of `set_aside` files whose `stage` is one of its stages ("2 set aside
  here"); text, not only colour.

`currentStep`: while `project.state` is `queued` or `running`, ingest.md's `activeStep(files)` (the lowest `n(f)` among
unfinished files, 1 with no files); `null` when `done` or `failed`.

`defaultStep`: `currentStep` when set, else Takeoff (step 7, what is ready to ask). The user's pick (a click on the rail) overrides it and stays
while the project updates; the panel does not follow the pipeline after a click (no jumping under the reader).

## API calls

**`project: ProjectView`** (prop, polled by `ProjectScreen`; API.md "GET /api/projects/{project_id}", fixtures
`project.json`, `project_running.json`, `project_failed.json`). Read: `state`, `error`, `ms`, `started_at`, `expected_drawings`, `skipped[]`, `cost_usd`, `files[]`
(`id`, `path`, `size`, `kind`, `state`, `reason`, `stage`, `route`, `source`, `drawing_id`, `normalised`, `takeoff`,
`reused`), `drawings[]` (`drawing_id`, `file`, `kind`, `route`, `state`), `readers`.

**`GET /api/projects/{project_id}/trace`** (`getProjectTrace`, #120; fixture `project_trace.json`).
`useProjectTrace` requests it when the key `id|state|stage` over all files changes, never while no file has a stage,
so a finished project is fetched once and a running one once per stage change. A newer request aborts the older one;
unmount aborts it. A failure keeps the last traces and shows one log line "The trace did not load." with "Retry".
Read per `files[]` entry: `file.id`, `stages[]` (`stage`, `did`, `output`, `ms`, `failure`, `cost_usd`),
`second_count` (`measured`, `conflicts`, null when that file had no second count).

**`GET /api/drawings/{drawing_id}/takeoff`** (`getTakeoff`; fixture `takeoff.json`). Once per entry of
`project.drawings` whose file is finished, the first time Normalise, Extract, Second count or Store is
shown (Takeoff needs no takeoff request: its counts come from `files[].takeoff`). Read: `quantities[]` `key`, `label`, `unit`, `status`, `first`, `second` (`method`, `value`), `marks[]`
(`box`, `page`, `label`, `state`, `room_type`).

**`GET /api/drawings/{drawing_id}`** (`getDrawing`; fixture `drawing.json`). Once per drawing, the first time
Takeoff is shown. Read: `suggestions[].label`, `pages.length`, `pages[0].scale`
(Identify chip; requested when Identify or Route is shown).

**`pageUrl(drawingId, 1)`**, **`previewUrl(projectId, fileId)`**: plain `<img src>`; a failed load shows "Page not
available" / "Preview not available" in its place, as the ingest screens do.

## Layout (per design screen)

Common to all four: page title and Simple/Advanced toggle belong to `ProjectScreen` (not drawn here). Below them:

1. **Rail** (`<nav aria-label="Steps">`, 9 columns on a `--v-line`-tinted track, 3 × 3 under 760 px): each step a
   `<button>` with a status ring and its label. Status shown by icon and a visually hidden word: done ✓ ("done"),
   working pulsing dot ("working", pulse off under reduced motion), waiting empty ring ("waiting"), none dash ("no
   file got here"), and "· N set aside" when `setAside > 0`. The selected step is raised (white, shadow) with
   `aria-pressed="true"`; the pipeline's current step has `aria-current="step"`. Min height 44 px.
2. **Panel** (`<section aria-label="<Heading>">`, white card, `--v-radius`, `--v-shadow`): left the visual (flex
   999 1 520px), right the text column (flex 1 1 300px); they stack under ~860 px.
   - Status line: when the step is `currentStep`, a spinner and "Now"; else "Done · replaying what this step did" (AV-41), "Waiting", or "No file got here".
   - `<h2>` the heading from the step table.
   - The explanation sentence (fixed text above).
   - The live line (`aria-live="polite"` only while the step is current): `"<path>: <did>"` of the last trace line of
     this step in file order (the last one: stages are in time order within a file; Bogdan: no `StageTrace.at`);
     "Nothing yet." when the step has no line.
   - **Log** (`<ol aria-label="Log">`, mono, `--v-bg` box, scrolls past 8 lines, `tabindex="0"`): `stepLines`, one
     `<li>` per trace entry of this step's stages over all files, in file order then stage order: `<STAGE_LABEL>
     <path> <output, or did when output is empty>`; `cache` lines read "Cached: <did>"; `cost_usd > 0` adds
     `formatCost`; `failure` lines read "✕ Failed: <failure>" (icon and word). Lines of a file whose trace failed
     to load: "Trace of <path> not loaded." + "Retry" button. While traces load and no line exists: "Loading the
     trace…".
3. **Stats** (`<dl>`, 4 cells, 2 × 2 under 760 px), per step below.

### Screen 9, Unpack (`IngestUnpack`)

- Visual `FileStrip`: a `--v-fill` band with a horizontal, scrollable (`tabindex="0"`, `aria-label="Files in
  this upload"`) row of file cards in `project.files` order: path, `formatSize(size)`, kind word (or "not
  identified"), `StateBadge`. Each card shows the upload itself, `previewUrl(projectId, id, 400)`, when its kind
  has a preview (`previewNote` null: images and PDFs, the backend's `PREVIEW_KINDS`), else the line for its kind:
  "A model: no picture to show" (ifc), "<kindLabel>: no preview" (AV-29), "Not identified yet" (kind null). The card of the file the step is working on (unfinished, its stage in the step) is framed, as
  the design frames the centre. No auto-scrolling film: the band scrolls by hand.
- Caption (mono, under the band): while working, `"<path> · <formatSize(size)>"` of that file; else
  `plural(files.length, 'file')`, total `formatSize` of all files.
- Stats: **Elapsed** (`formatMs(project.ms)` when `done`/`failed`; while running now − `started_at` on a 1 s clock;
  "–" while `started_at` is null),
  **Files opened** (`files with stage != null` / `files.length`), **Set aside** (files `state === 'set_aside'`),
  **Cost** (`formatCost(project.cost_usd)`). No "Remaining" (Bogdan: no `eta_ms`).

### Screen 10, Identify and Route (`IngestIdentify`)

- Visual `RouteLanes`: on top a file view: a `<select aria-label="File">` over `project.files` (default: the file the
  step works on, else the first file with a `route`), its own `previewUrl` image or its kind's line (as Unpack), and chips over the image's bottom
  edge from real fields only: kind word (no medium, year or language: Bogdan, no `identified`),
  `"<normalised.width> × <normalised.height> px"` when `normalised`, `scaleChip(pages[0].scale)` of the file's drawing ("Scale 1:100 found", "… estimated", "No scale found", "Not to scale"),
  `"route <route>"`, `"read from <source>"` when `source` differs from `path`, `reused` → "read before". Below, two
  lanes, as the design's "CAD geometry" and "Vision model" boxes, named for what runs:
  - **"Exact geometry"**: routes `bim`, `cad`, `vector`; under it the readers `readerName(readers.bim)`,
    `readerName(readers.cad)`, `readerName(readers.vector)` and the count of files routed there.
  - **"From the image"**: route `raster`; under it `readerName(readers.raster)` and its count. A reader id `hello`
    reads "not read", as `readerName` says everywhere (API.md: `hello` reads nothing); never "vision model" unless
    the reader is one.
  - The selected file's lane is marked (`aria-current="true"`, border `--v-accent`) and says "This file goes here";
    a file with no route says "Not routed: <reason>".
- Stats: **Elapsed**, **Exact geometry** (count), **From the image** (count), **Set aside** (all set-aside files).
  Each lane lists its readers as `<route>: <readerName>`. A file not finished and not routed reads "Not routed yet."

### Screen 11, Normalise, Extract, Store (`IngestExtract`)

- Visual `PlanMarks`: a `<select aria-label="Drawing">` over `project.drawings` (default the first; label `file`).
  For a drawing with pages: `pageUrl(drawing_id, 1)` in a `position: relative` box, an SVG overlay `viewBox="0 0 1
  1"` `preserveAspectRatio="none"` with one rect per mark of the takeoff rows keyed `room`, `door`, `window` (page 1,
  `state` not `rejected`), and a label pill with `mark.label` for room marks (text node, never HTML), `title` = `mark.room_type` when set. The sweep line
  animates only while Extract is `working`; off under reduced motion. An IFC drawing without pages: "A model, no
  sheet to show" and its counts. Normalise selected: before/after, "As uploaded" (the drawing's file `previewUrl`, or its
  kind's line) beside "Normalised page 1" (`pageUrl`, stacked under 760 px); under them
  `normalisedSteps(file.normalised)` of the drawing's file, or "Pages as the file gives them" for a PDF.
- Stats (`planCounts`, summed over `project.drawings`, each drawing's file's `takeoff`, so a PNG beside its PDF is
  not counted twice): **Rooms** (`takeoff.room`), **Doors** (`takeoff.door`), **Windows** (`takeoff.window`), and
  **Drawings ready** (`"<finished drawings> / <expected_drawings>"`, finished drawings alone while `expected_drawings` is null). A key no drawing has shows "–",
  never 0.

### Screen 12, Second count and Takeoff (`IngestCheck`)

- Visual `CheckPairs` (Second count): `pairsOf(takeoffs)`, every row with `second` set, conflicts first, then the rest
  in takeoff order. Each pair as the design's card: left "From the drawing" `formatValue(first.value, unit)` and
  `methodName(first.method)`; right "Second count" `formatValue(second.value, unit)` and
  `methodName(second.method)`; above, `label` and the drawing's `file`; below, the verdict: `agree` → "They agree.
  Kept as the answer."; `conflict` → AV-38's words and "Show the conflict" button; any other `status` → its word (`signed`, `edited`, `estimate`, `single`). Verdicts
  carry an icon and words, colour (`--v-ok`, `--v-warn-soft`) only adds. No pairs: "Nothing on these drawings can be
  measured a second way yet." Shown: every conflict and the first 4 other pairs, then a "Show all N pairs" button.
- Visual `ReadyList` (Takeoff): "Questions ready to ask" (never "answers ready", Bogdan), per drawing: its `file`,
  "<n> questions ready to ask" with `n` = keys of its file's `takeoff` (one question per quantity), then the `suggestions[].label` of its `DrawingView` as a
  list, each with a filled dot when the drawing's file is `ready` or `flagged` (no link: AV-39). No drawings: "No drawing to ask yet."
- Stats, Second count: **Elapsed**, **Measured twice** (pairs), **Agree** (`status === 'agree'`), **Conflicts**
  (`status === 'conflict'`), from the takeoffs, once every finished drawing's takeoff has loaded or failed; "–" until then (AV-31); Conflicts
  counts `Takeoff.disputes` (AV-34). Takeoff: **Elapsed**, **Drawings** (`drawings.length`), **Questions ready** (keys of the drawings' files'
  `takeoff`, summed over `project.drawings`), **Cost** (`formatCost(project.cost_usd)`).

## States

| State | What shows | Reach it on purpose |
| --- | --- | --- |
| Running | rail with `currentStep` marked and selected; panel "Now"; log grows as traces come | `project_running.json`; mocked traces per stage |
| Done | every reached step ✓; Takeoff selected; Time = `project.ms` | `project.json` + `trace.json` |
| Failed project | rail statuses as computed; panel as for done; `project.error` is shown by `ProjectScreen`, not here | `project_failed.json` |
| No files | `files: []`: rail all "waiting" while queued/running, all "no file got here" when done; panel log "Nothing yet." | `queued` with `files: []` |
| Trace loading | log "Loading the trace…" | pending `getProjectTrace` |
| Trace error | log line "The trace did not load." + Retry; the last traces stay | `getProjectTrace` rejects |
| Takeoff/drawing error | panel line "Could not load the takeoff of <file>." + Retry (`ErrorView` compact); stats "–" | `getTakeoff` rejects |
| Set aside | rail "· N set aside" on the step; log "✕ Failed: …" when the stage failed | `trace_set_aside.json` |
| 390 px | rail 4 × 2, panel stacked (visual above text), stats 2 × 2, file strip scrolls, no horizontal page scroll | e2e at 390×844 |
| Reduced motion | no pulse, spinner, sweep or fade | `prefers-reduced-motion: reduce` |

## Acceptance criteria

Rail and steps

- AV-1: The rail shows 9 buttons in a `nav` named "Steps", with the names of `STEPS` in its order: Unpack, Identify,
  Route, Normalise, Extract, Second count, Takeoff, Store, Index. [component]
- AV-2: `STEP_VIEW` has a heading, visual and explanation for each of the 9 steps, and `advanced.ts` defines no
  stage-to-step table of its own (it imports `stepOf`). [unit]
- AV-3: `stepStatus` gives working / waiting / done / none per the rules above, including: a finished file whose
  `stage` is `route` (set aside there) does not make later steps `waiting`; a reused file with `stage: write` marks
  every step done. [unit, `project.json`, `project_running.json`]
- AV-4: With `project_running.json`, the current step's button has `aria-current="step"` and is selected; no other
  button has `aria-current`. With `project.json` (done), no button has it and Takeoff is selected. [component]
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
- AV-10: `useProjectTrace` makes one `GET /api/projects/{id}/trace` per new `id|state|stage` over the files, none
  while no file has a stage, none on a rerender with the same files. [component, `mockApi` call log]
- AV-11: A trace request that fails shows "The trace did not load." with a Retry button that requests it again.
  [component]
- AV-12: The live line has `aria-live="polite"` only while the selected step is the current step. [component]

Visuals and stats

- AV-13: Unpack stats: Files opened `"<with stage> / <all>"`, Set aside = set_aside files, Cost =
  `formatCost(project.cost_usd)`, Elapsed = `formatMs(project.ms)` when done, now − `started_at` while running, "–"
  before it starts; `project.skipped` as "Skip <path> <reason>" log lines. [component]
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
- AV-19: Second count lists every takeoff row with `second` set, conflicts first; a conflict's way to its card is
  AV-38 (the `#/p/<projectId>/conflicts` link is gone: that route now lands on Ingest); Agree and Conflicts stats count `status` `agree` and `conflict`. [unit + component,
  `takeoff.json`: one pair, `area:room|name=1.01`, 22.4 vs 30.0, conflict]
- AV-20: Takeoff lists each drawing with its quantity count and its `suggestions[].label`; no "Ask this drawing"
  link (AV-39). [component, `drawing.json`]
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
- AV-26: Every step renders from what the user uploaded, by kind (Tudor 12:03): Unpack and Identify/Route show each
  file's own `preview.png` for images and PDFs and the kind's line for the rest (ifc, dxf, text, unidentified), so
  no request can 404 and no image breaks; Normalise shows the drawing's upload beside its normalised page 1; Extract
  its page 1 with the marks (ifc: "A model, no sheet to show."); Second count and Takeoff the takeoffs' own values.
  [unit `previewNote`; component: mixed kinds; browser: a real upload (zip of photo, PDF, PNG scan, IFC; and one
  photo alone) at 1440 and 390, 0 console errors]
- AV-27: Trace lines show a sha256 as its first 12 characters and "…" (`shortHashes`); mark keys are
  `<row key>-<mark id>` (ids repeat across rows); the Drawing select is 44 px tall.
  [unit, component, CSS text]
- AV-28: Every file name in src/advanced comes from THIS project (`fileName(project, drawingId)`: `project.files` by
  `drawing_id`, else `project.drawings[].file`), never `Takeoff.file` or `DrawingView.file`: drawings are
  content-addressed and shared, so those may be another project's path for the same bytes. Kinds show as
  `kindLabel` words ("photo of a plan"), never raw ids. [unit `pairsOf` with a shared drawing; component Second count]
- AV-29 (R4-a-4): No raw id or doubled path in Advanced text: a file with no preview reads "<kindLabel>: no
  preview" ("SVG: no preview", no "a SVG"); a log line whose `output` is the file's own path uses `did` instead (never
  "Unpack a.pdf a.pdf"); an Identify line's output shows as `kindLabel`, a Route line's and the route chip as
  `routeLabel` ("drawn PDF route", never "route vector" or "vector"). [unit `previewNote`, `stepLines`, `routeLabel`]
- AV-30 (R4-a-5): The "File" and "Drawing" picker labels never break inside the word at 390 or 1440: `.adv-pick`
  sets `overflow-wrap: normal` and the select `min-width: 0` (the page's `overflow-wrap: anywhere` let the select
  squeeze the label to one letter per line). [unit: CSS text; browser 1440 and 390]
- AV-31 (R4-a-8): Second count's Measured twice, Agree and Conflicts show "–" until every finished drawing's takeoff
  has loaded or failed, then the counts; they never show a partial sum that changes as takeoffs arrive (QA saw
  100/8, 27/0, 61/8). [component: one takeoff pending -> "–"; all loaded -> counts]
- AV-32 (R4-a-9): As in Simple (IN-49, IN-71), Unpack leaves the counts out while nothing is opened: no file with a
  stage gives Files opened "–" (never "0 / 0"), and with no files the strip has no caption (never "0 files, 0 B").
  [component: `queued` with `files: []`]
- AV-33 (R4-a-11): No reader or route id in the Route/Identify lanes: each reader reads "<routeLabel>: <readerName>"
  ("drawn PDF route: PDF vector reader", "image route: not read"), never "bim:", "cad:", "vector:", "raster:". The
  Unpack live line is "<path>: <formatSize(size)>" of the file of its last line; hashes stay in the mono log only.
  [component]
- AV-34 (R4-a-8, API `Takeoff.disputes`, #149): Second count counts one conflict per entry of `Takeoff.disputes` (the
  keys the project review lists): a `conflict` row whose key is not in `disputes` (a storey or room-name twin of
  another row's disagreement) is not listed or counted; Conflicts = disputed pairs. A takeoff without `disputes`
  (older backend) keeps the old rule (`status === 'conflict'`). [unit `pairsOf`; component]

## Demo parity (Tudor 2026-11-14 16:25, demo PRs #206, #211, #212, #217)

"make the full frontend look more like our demo": in the demo the finished Advanced view ends the same way as the
finished Simple view (#211): under the panel card, the conflicts (AI-settled first, then the ones that need a
person), then "Start a new chat" (disabled until every conflict is settled) and "Open the workspace"; no issues
there; the done line "N issues in Documents need you" links to Documents. The Advanced view keeps its rail, panel
and stats; only the end of the page and a few links change.

**One finished block, two views.** Simple and Advanced must not disagree, so `src/advanced/` writes none of it: it
imports preqa-a's done line and finished block from `src/ingest/` (which embeds fe-surveyor's conflicts list).
They are `DoneLine({projectId, project, counts})` and `IngestFinished({projectId, project, onCounts})` from
`src/ingest/IngestFinished.tsx` (ingest.md IN-74..83); AdvancedIngest keeps the list's `ConflictCounts` in state
for the done line, and "Show the conflict" scrolls to `CONFLICTS_ID`. No `query` is passed (issue links land on
Simple). Ruled out:
ProjectScreen rendering the block under both views (ingest.md says `AdvancedIngest` replaces everything under the
title row; keeping that keeps the toggle a one-line switch).

Layout when `project.state === 'done'` (as the demo's `advancedScreen`): rail, then the panel card with its stats
and, last inside the card, `DoneLine` (demo `.done-row`: padding 0 32px 28px, 0 20px 22px under 760 px); then,
under the card, `IngestFinished`. Running, queued or failed: neither (failed shows `project.error` from
ProjectScreen, as now). A done project with no drawings: whatever `IngestFinished`/`DoneLine` show for Simple (IN-72
"nothing read"), the same in both views.

- AV-35: With `project.json` (done), AdvancedIngest renders `DoneLine` inside the panel card after the stats and
  `IngestFinished` after the card, each once, with `projectId` and the same `project`; the rail and panel stay
  above them. [component, both mocked with `vi.mock` so this test does not depend on their contents]
- AV-36: With `project_running.json`, `queued` and `project_failed.json`, neither `DoneLine` nor `IngestFinished`
  renders. [component]
- AV-37: AdvancedIngest makes no review or issues request of its own (the finished block makes them): the
  `mockApi` call log for a done project with the block mocked has no `/review` and no `/issues` call. [component]
- AV-38: Second count verdicts: `conflict` reads "They disagree. It goes to the conflicts below." while the project
  is done, and "They disagree. It goes to the conflicts when reading ends." while it is not; a done project's
  conflict pair has a button "Show the conflict" that scrolls the finished block's conflicts list into view
  (`scrollIntoView`, `behavior: 'auto'` under reduced motion) and moves focus to it (`tabIndex=-1` target). No link
  to `#/p/<pid>/conflicts`. [component: text per state, button present only when done, `scrollIntoView` called]
- AV-39: Takeoff has no "Ask this drawing" link and no `/engineer` link anywhere in `src/advanced/` (chat is project
  wide; "Start a new chat" in the finished block is the way in, as in the demo). [component + grep of the folder]
- AV-40: Plain words: no text in `src/advanced/` names a screen that no longer exists ("Settle the conflicts",
  "Engineer", "Issues" tab) and no credit, licence, source note or "refused" line. [component: done project, assert
  absent; grep]
- AV-41: Look as the demo's Advanced screen (`demo/vellum/style.css` `.rail`, `.r-ico`, `.panel`, `.panel-txt`,
  `.say`, `.log`, `.stats`, `.kicker`, `.done-row`), with `--v-*` tokens only (AV-25 still holds): rail track
  radius 18 px / padding 4 px, step radius 14 px; panel padding 28 px (20 px under 760), gap 28 px; stats cells
  padding 14px 20px, `dt` 12 px muted, `dd` 20 px 600 tabular; log padding 12px 14px, radius 14 px; finished
  step's kicker "Done · replaying what this step did" in `--v-ok` (replaces "Done"); the done line inside the card
  padded as the demo's `.done-row`, 0 32px 28px (0 20px 22px under 760 px; re-sweep item 4). Differences preqa-b lists in
  `.agents/preqa-parity.md` for Advanced are folded in here before phase 2. [unit: CSS text; browser 1440/390]
- AV-42: At 390 px with a done project: no horizontal scroll, the finished block's buttons full width (demo
  `.chat-cta .btn { width: 100% }`, from the block), 44 px taps; at 1440 px the block sits in the same column as
  the panel card. [browser on a no-keys backend, sample project, both widths]

### Dependencies (phase 2 order)

1. preqa-a: `DoneLine`, `IngestFinished` exported from `src/ingest/` (names per their spec), and the conflicts
   list's element carries an `id` (or a ref prop) AV-38 can scroll to; until then AV-35/AV-36 run red against the
   mocked import path.
2. fe-surveyor: the embeddable conflicts list (inside `IngestFinished`, not imported here directly).
3. fe-shared: no new token needed; `--v-ok` exists.

### API asks

None for this area: the Advanced view reads what it read before, and the finished block's data (review, issues)
is the Simple view's. The issue count of the done line ("issues still to answer": `severity: needs_person`,
`state: open`, notes not counted) is computable from `GET /api/projects/{id}/issues`; one count function should
serve the done line and the Documents badge (fe-shared / preqa-a), not two.

Pipeline steps v4 (ingest.md "Pipeline steps v4")

- AV-45: `STEP_VIEW` has a `routes` line for bim, vector and raster on Normalise, Extract and Second count, and none
  on the other steps; `routeLines(view, project)` returns only the routes some file is on, in the order bim, cad,
  vector, raster, as `{route: routeLabel, line}` ("drawn PDF route", "Pages are taken as the PDF gives them."). [unit]
- AV-46: The panel shows those lines as a list under the explanation; a project with only a drawn PDF shows one line on
  Extract and none on Takeoff. [component]
- AV-47: Index (step 9): `stepStatus` is working while the project runs with every file finished, waiting while a
  file is still open, done when the project is done with files, none when it failed or has no file; its log lists each file's
  `evidence.why` as "Index <path> <why>" (files without `evidence` are left out), "Nothing yet." when none has one.
  [unit + component]
- AV-48: The rail is 9 columns wide at 1440 px and 3 × 3 at 390 px, with no horizontal scroll and no step name
  broken inside a word (`overflow-wrap: normal`). [e2e screenshot]

## Trace view v5 (ingest UI track, 2026-11-15, worker detail for w18:p3C)

Bogdan (2026-11-15 03:20): "I want the ingestion pipeline to look much better, and then to be more representative of
the operations we are doing right now in the actual pipeline." Two views read the trace as time and decisions: the
Advanced view starts with every file by its stages, and a file's page (`#/p/<id>/f/<fid>`) shows its decisions and
its stages on one time axis, with the steps that ran inside each stage (contract `StageTrace.steps`,
`docs/decisions/0018-ingest-trace-steps.md`). Files: `src/advanced/trace.ts` (pure), `TraceTimeline.tsx`
(`TraceTimeline`, `Decisions`, `StepList`), `FileMatrix.tsx`, `trace.css`; `FileTraceScreen.tsx` uses them.

- **Time axis.** Stages of one file run one after another, so a stage starts where the ones before it ended
  (`stageSpans`); no `StageTrace.at` is needed. Steps sit on their stage's axis at `at_ms`, `ms`: readers that ran
  together overlap, and the stage says "N steps inside <stage>, up to K side by side" (`sideBySide`, skipped steps
  not counted). An older server sends no `steps`: the stage shows as before, with no step list.
- **Decisions**, in pipeline order, each with where it happened: what the file is (triage class, plan chance,
  method, the sheet reader's kind and decision; without triage the identify line), the route with its group, the
  file it is read from and a cache hit, the second count (agree, or the conflicts with both values from the
  drawing's takeoff, asked once and only when `second_count.conflicts > 0`), and the outcome with its reasons
  (`reason` split on "; ") and a failed stage. Icon and word, colour only adds.
- **Files by stage** (top of Advanced, above the rail): one row per file with its path (link to its trace), state,
  route, a bar of its stages merged by phase (open and route, normalise, read the plan, second count, takeoff and
  store) whose length is its time against the slowest file, the longest stage, total time, rooms/doors/windows
  found, cost, a failed stage, and the reason on its own line when it found nothing. A running file says "Now:
  <FileStatus.step>". The last phase's `index_steps` are listed under the files.

Acceptance criteria

- AD-100: The file page shows its stages open (no `<details>`) under "How it was read: N stages" in a region
  "Stages", each on the time axis; replaces IN-83's fold for the stages (the takeoff fold stays). [component
  `FileTraceScreen.test.tsx`; e2e `ingest-detail.spec.ts`]
- AD-101: `stageSpans` places each stage after the ones before it, as fractions of the file's time; no time gives no
  span. [unit `trace.test.ts`]
- AD-102: `stepSpans` places steps by `at_ms`/`ms` on the stage axis (stretched to the latest step end, never past
  100 %); `sideBySide` counts the most steps running at once, back-to-back and skipped ones not overlapping.
  [unit]
- AD-103: Each step shows its label, `did` (else its `found` counts, largest first), time, cost; failed and
  skipped steps carry an icon with the word; skipped draws no bar. [component `FileMatrix.test.tsx`; e2e with
  contract-shaped steps added to the real response]
- AD-104: A stage without `steps` (older server) or with none draws no step list. [unit, component]
- AD-105: A drawn PDF's decisions: identified as, route with group, both counts agree, ready with its reason.
  [unit]
- AD-106: Triage words (class, plan chance, sheet kind and decision), read-from and cache lines, a conflict with
  both values, flagged reasons one per line, a failed stage; the region "Decisions" lists them in order Identify,
  Route, Second count, Outcome. [unit, component, e2e plans/flat-b.pdf]
- AD-107: The conflict values come from one takeoff request, only when the second count disagreed; `disputes`
  limits them (older servers: every `conflict` row). [component call log, unit]
- AD-110: Files by stage lists every file, each linking to `#/p/<id>/f/<fid>`, with route words, state, time and
  what it found; the bar's accessible name lists every stage with its time. [component, e2e]
- AD-111: A failed stage is said on its row ("✕ Extract failed: …"); a running file says "Now: <step>" and its last
  segment pulses (not under reduced motion). [component]
- AD-112: Bars compare files (the slowest full width, the others their share, at least 4 %); neighbouring stages of
  one phase are one segment, a failure marks its run. [component, unit `phaseRuns`]
- AD-113: The project's `index_steps` are listed under the files ("After the files, now: …" while `phase` is
  `index`); a project with no files shows nothing. [component]
- AD-114: Paths, step labels and `did` render as text. [component]
- AD-115: A file that found nothing gives its reason on a full-width line; at 390 px the rows stack and nothing
  scrolls sideways. [component; e2e screenshots at 1440 and 390]
- AD-116: `trace.css` uses only `--v-*` colours; a segment takes its phase's colour, and the five phases have five
  fills apart in hue and lightness (grey `--v-line`, outlined pale `--v-accent-soft`, green `--v-accent`, amber
  `--v-warn-mark`, blue `--v-3d-moved`; review of #546: read and store were two dark greens); the bar also says its
  stages in words and a failure in text. Under reduced motion the bars do not grow and nothing pulses. [unit on
  the CSS text; e2e `animationName` under `reducedMotion: 'reduce'`]
- AD-117 (review of #546): A stage's output shows only when it adds to its did line: not when the did contains it,
  when it is the route of a "<route> route" did, or when it is the full hash the did starts ("sha256 dd2c…").
  [unit `repeats`; component IN-33]
- AD-118 (review of #546): A file's reason reads as plain lines, never two brackets in a row: reasons joined by
  "; " are one line each, and a trailing bracketed summary with a comma ("(7 elements, 5 rooms, …)") becomes
  "Found: …". The text is the backend's (`FileStatus.reason`); the frontend only splits it. [unit `reasonLines`]
- AD-119 (review of #546): A file read with its group's other file (`source` differs from `path`) says "read with
  <source>" in its matrix row, "Read with <source>" as its route decision, and "read with <source> (<route>)" as
  its Route fact, never the route alone as if it were read itself. [unit, component]
- AD-120 (review of #546): The file page's last card, "What it ends as", gives the takeoff's plain class counts
  above zero (zeros left out before the 8 are taken; rooms, doors, windows first, at most 8) and "See these on the drawing" (its engineer workspace); the full
  list stays folded under "What it ends as: N quantities". [unit `keyCounts`; component]
- AD-121 (real traces, 2026-11-15): A stage's steps are cut where none was running. Steps whose times overlap are one
  run under a note "Side by side, <from> to <to>: N steps[, up to M at once]", each drawn on the run's own axis (its
  first start to its last end), so the overlap shows even in the last tenth of a 21 s stage; a lone step keeps the
  stage axis. A stretch with no step running of at least 1 s and a tenth of the stage is its own note: "The first
  step began at <t>" before the first step, else "No step ran from <a> to <b>"; no reason is given for the wait (the
  data names none). Notes are `role="presentation"`, so the steps stay the list's only items. [unit `stepRows`;
  component `FileMatrix.test.tsx`; screenshots of the four real traces at 1440 and 390]
- AD-122 (real traces, 2026-11-15): The file page's Cost fact shows only a cost above zero; a file with no paid call
  has no Cost row (was "$0.00" on every file, IN-32), and an odd last fact spans the grid row. [component
  `FileTraceScreen.test.tsx`]
- AD-123 (QA R2-A1, 2026-11-15): Extract's **Drawings ready** counts only finished drawings something was read off:
  a drawing whose route's reader in `project.readers` is `hello` is not ready (the same rule as the Simple view's
  IN-116). On `project.json` (raster = hello) it reads "4 / 6", was "6 / 6" (AV-17's test changed with it).
  [component `AdvancedIngest.test.tsx`]
- AD-124 (real-data screenshots, 2026-11-15): A long path in the file matrix (the file's link and "read with <file>")
  keeps its file name whole and lets the muted folder give way first, as the Simple view's IN-113 (`splitPath` from
  `RouteLanes.tsx`); the link's name and title stay the full path, and the file column is as wide as the longest
  path, at most 45 % of the row. The Index step's "Questions ready to ask" lists
  only the drawings with questions, then one line for the rest ("12 drawings have none yet"); it was one row per
  drawing, 12 of 13 real ones reading "0 questions ready to ask". [component `FileMatrix.test.tsx`,
  `AdvancedIngest.test.tsx`; screenshots at 1440 and 390]
- AD-125 (real steps of #535, 2026-11-15): Identify, Normalise and Second count now send steps. A step's did line that
  the stage's own did already says (the whole line, or a part of it at its start or after "; " / ": ") is not shown
  again; the step keeps its name and time. A done step with 0 ms exactly was not timed (the second count's checks):
  no time, no bar. A check step whose `found.conflict` is above zero gets the "!" mark ("found a conflict"). The
  Index step's log lists each file's evidence, then the project's `index_steps` ("<label> <did>", a failed one
  marked), so its live line is the latest index step. A path in the Advanced panel's running text (live line, log,
  "Questions ready to ask", the Unpack file cards) is the muted folder with a break allowed after each "/", then
  the file name as one box: whole on its line when it fits, else broken after a "_" or "-" of its own, never
  mid-token. [unit `trace.test.ts`; component `FileMatrix.test.tsx`, `AdvancedIngest.test.tsx`; e2e
  `ingest-detail.spec.ts`; screenshots at 1440 and 390]

## Not in the API

Not added, per Bogdan's triage (11:07, #14 c6874945888); shown as nothing:

1. **Remaining time** (design: "Remaining ~12 s"): no `ProjectView.eta_ms`.
2. **Order of events in time** (design: the log is "newest first"): no `StageTrace.at`; the log is in file order.
3. **Identify medium, year, language** (design: "Pencil on paper · 1948", "Labels in Swedish"): no
   `FileStatus.identified`; the chip shows the kind only.
4. **An "Index" stage**: the backend has no stage id for its last phase (triage's judge, the evidence step, the
   evidence index). v4 shows it as step 9, Index, from the project still running with every file finished, and its
   log from `files[].evidence.why`; `takeoff` is now shown as Takeoff (it was "Index" before v4). A
   `ProjectStatus.phase` would let the backend name it.

## Fields added by #120 (were mocked, now real)

`ProjectView.started_at` (Elapsed), `expected_drawings` (Drawings ready), `skipped` (Unpack log), the project trace
`GET /api/projects/{id}/trace` (one request for the log), `FileTrace.second_count` (Second count stats before the
takeoffs), `PageView.scale` (Identify chip), `MarkView.room_type` (room pill title). Read as typed fields; null shows
the empty state above. No mock and no `data-pending` is left in `src/advanced/`.

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
- **Request load**: Takeoff needs one `GET /api/drawings/{id}` per drawing and Extract/Second count one takeoff per
  drawing; with the sample (≤ 10 drawings) that is fine; a large zip would want item 4 above.
