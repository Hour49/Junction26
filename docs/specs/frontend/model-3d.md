# 3D view of IFC files (spec, frontend)

Status: accepted (frontend-orch 21:50: states, scope and e2e below), 2026-11-14 21:40, by m3d-front for frontend-orch. Source: Tudor 21:08 (verbatim) "can we also run a
3d render? on the frontend for the files used as references when they are 3d?". Brief:
`.agents/briefs/frontend-3d-viewer.md` (incl. "Agreed with Bogdan", #14 c6882768584, 21:10),
`.agents/briefs/m3d-front.md`. Backend side: m3d-back (IFC -> GLB in a capped subprocess, route, `model_3d`, the
precompute CLI); we write both sides. The backend's `MODEL_3D` setting is off by default: then `model_3d` is null
and every screen is today's.

## Purpose

Where the UI shows a file that is a building model (IFC), the person can open an interactive 3D view of it: orbit,
pan, zoom, reset. When an answer names model elements (GlobalIds), those are highlighted, everything else is
dimmed, and the camera frames them. 2D sheets keep today's image viewer; nothing about them changes.

Built in three parts, each merged on its own (no half-built screens):

1. The file page (`#/p/<pid>/f/<file_id>`, reached from Documents) of an IFC file.
2. The chat's References (ask chat and agent chat, both render `ChatAnswer`): a part whose drawing has a 3D model
   opens the same view in a dialog (PR #356 shipped part 1; parts 2-3 by w3:p1 21:50).
3. Element highlight by the part's `highlight: {global_id, role}[]` (role `moved | removed | added | affected`, one
   colour each, a legend in words): the listed elements coloured, the camera frames them, the rest dimmed.

## Files owned

| File | What |
| --- | --- |
| `src/model3d/ModelView.tsx` (new) | `ModelView({projectId, file, highlight?})`: the states, the controls, the legend / highlight line. Imports no `three` |
| `src/model3d/ModelDialog.tsx` (new) | the view in a modal (chat References, the agent chat's plan pane): `SourcePreview`'s modal pattern (Esc, focus trap, focus back) |
| `src/model3d/scene.ts` (new) | the only module that imports `three`: renderer, `GLTFLoader.parse`, `OrbitControls`, `highlight(root, marks)`, `frame(camera, controls, box)`, `dispose()`. Loaded with `import('./scene')` |
| `src/model3d/model3d.ts` (new) | pure: `model3dOf`, `canShow3d`, `failure`, `ROLE_LABEL`, `legendLines(result)` |
| `src/model3d/model3d.css` (new) | `--v-*` tokens only; one token per role |
| `src/api/client.ts` | only `getModelGlb(projectId, fileId, opts) -> ArrayBuffer` (+ test): `call`'s error handling, the body read as a buffer |
| `src/ingest/FileTraceScreen.tsx` | part 1: the "3D view" card (one block) |
| `src/engineer/ChatAnswer.tsx` | part 2: the References row of an IFC part |
| `src/shell/shell.css` | part 3: the four role tokens `--v-3d-moved`, `-removed`, `-added`, `-affected` in `:root` |

The last four are other workers' files (preqa-a / fe-engineer / fe-shared); one small block each, mine since
frontend-orch's 21:50 GO.

## API (agreed with Bogdan, #14 c6882768584; m3d-back writes it)

- `FileStatus.model_3d: {state, code, reason, elements}` on `GET /api/projects/{pid}` `files[]` and on the file
  trace's `file`. Absent (not IFC, set aside, or `MODEL_3D` off): no 3D entry anywhere, the screen is today's.
  `state`: `not_started | converting | ready | unavailable` (no `queued`: one conversion at a time is
  `converting`), `code` `too_big | no_geometry | failed` or null, `reason` a plain sentence (`""` when none), `elements` the
  element count or null. One field on the file serves every part:
  a chat part finds its file by `drawing_id` in `project.files[]`.
- `GET /api/projects/{pid}/files/{file_id}/model.glb`:
  - 200 `model/gltf-binary`: one GLB, one node per element, **node name = the element's GlobalId** (IFC GlobalIds
    use `0-9A-Za-z_$`, which three.js's name sanitising leaves as is).
  - 409 `{code: "converting"}`: conversion running. The first GET of a `not_started` file starts it.
  - 422 `{code: "too_big" | "no_geometry" | "failed", detail}`: the file is `unavailable` from then on; `detail` shown as sent.
  - 404: not an IFC file / unknown file / `MODEL_3D` off.
- `ProjectAnswerPart` (m3d-back, 22:00; in the ask answer and in the agent chat's `ChatTurn.answers`): `file_id` (the
  drawing's file), `model_file_id` (the IFC file whose GLB shows this drawing: its own file, or the model a sheet was
  read from; absent when none), `model_3d` (that file's `Model3d`, absent when none or `MODEL_3D` off), `highlight:
  Highlight[]` (`{global_id, role}`; the answer's counted elements as `affected`; absent when empty). The frontend
  needs no `files[]` lookup.
- Before #356's fields: the highlight for answers needed no new field: `AnswerView.proof.objects[]` (`kind: "model"`) already carries
  `global_id`. The agent chat's `ChatEvidence` has none (open point 3).
- After `npm run api:gen` the frontend uses the generated `model_3d` type (no hand-written copy).

## User flow

`file.model_3d` is the file's `model_3d`. "Has 3D" = `model_3d` not null.

1. **File page** (part 1). A file with `model_3d` shows a card "3D view" after the facts:
   - `not_started`, `converting` or `ready`: the button "Show in 3D" (secondary), with "<elements> elements" muted beside it when
     `elements` is set. The GLB is not downloaded until the press (it can be tens of MB on a judge's laptop).
     Pressed: the view opens in place in the card, 560 px tall at 1440, `min(60vh, 420px)` at 390, full card width.
   - `unavailable`: no button, the line "3D view unavailable: <reason>" (`reason`, else "the model cannot be shown
     in 3D" when it is empty).
   - `model_3d` null (every 2D file, an IFC set aside, `MODEL_3D` off): no card.
2. **Chat answer** (part 2; ui-bugs 5, 2026-11-15: now ONE round "3D" button above the image's top-right, the
   shown part's model, else the answer's building model, tip "Open the 3D model"; the per-reference buttons below
   are replaced). In `ChatAnswer`'s References list, each part with `model_3d` set and not
   `unavailable` gets a second button after its row, "View in 3D" (`aria-label` "View in 3D: <label>", visible text first, 44 px tall);
   the row itself is unchanged (a button when the part has pages, plain text with "· no preview" when not). It opens
   `ModelDialog` titled "3D view: <label>" with `ModelView` on `model_file_id`, highlighting the part's `highlight`
   (part 3; `[]` before it). `unavailable` or no `model_3d`: no button. The left figure and the arrows are
   unchanged. Esc and "Close" close the dialog and focus returns to the "View in 3D" button.
3. **Highlight** (part 3). `ModelView` takes `highlight: Highlight[]`. Drawn:
   - each matched node in its role's colour (`--v-3d-moved` blue, `-removed` red, `-added` green, `-affected`
     orange, read from the computed style at mount); `removed` also at 50% opacity so it differs by more than hue;
     an id listed twice keeps its first role;
   - every other node at 12% opacity (transparent, no depth write);
   - the camera frames the matched nodes' bounding box (10% margin), centred on it but each side at least half the
     whole model's (w3:p1 22:20: the building stays visible around one door); "Reset view" returns to this framing;
   - under the view a legend (`<ul aria-label="Highlighted elements">`): one item per role present, a swatch (aria-
     hidden) and the words "Moved: 2", "Affected: 1" (`ROLE_LABEL`), so colour is never the only cue; then "<k> of <m>
     elements are not in the 3D view." when some ids are not in the model; "None of these elements are in the 3D
     view." (and nothing dimmed, whole model framed) when none match; no legend for `[]`.
   - The GLB's materials are cloned before colouring (another open view of the same file is unaffected).
4. **Later places**: the agent chat's plan pane is in "More places" below; Documents issue cards wait for
   `Issue.highlight`; edit proposals (`Proposal.services`) are still out.

## Controls

- Mouse: drag orbits, right-drag (or Shift+drag) pans, wheel zooms (`OrbitControls`, damping off). Touch: one finger
  orbits, two fingers pinch-zoom and pan. The canvas has `touch-action: none`; at 390 the view is shorter than the
  screen, so the page still scrolls outside it.
- Buttons in a toolbar over the view's top right (each a `button`, 44x44, a visible label or `aria-label`, keyboard
  reachable in tab order): "Rotate left", "Rotate right" (15° about the vertical axis), "Zoom in", "Zoom out",
  "Reset view". In the dialog also "Close".
- The canvas is focusable (`tabIndex=0`, `role="img"`, `aria-label="3D view of <path>"`): arrow keys pan
  (`OrbitControls.listenToKeyEvents`), `+`/`-` zoom.
- Renders on demand (on a controls change and on resize, `ResizeObserver`), no animation loop. Unmount disposes
  the renderer, controls, geometries, materials and the WebGL context.

## States (after "Show in 3D" / "View in 3D")

| State | Shows | Reach it |
| --- | --- | --- |
| Loading | "Loading the 3D view…" (`Loading`), no toolbar | GET pending, then parse |
| Preparing | "Preparing the 3D view…" with "Try again"; retried by itself every 5 s, at most 24 times (2 min); then "Still preparing. Try again later." with "Try again" | 409 `converting` |
| Unavailable | "3D view unavailable: <detail>", no retry | 422 `too_big` / `no_geometry`; 404 ("no 3D model for this file") |
| Failed | "3D view unavailable: <reason>" with "Try again" | 500 / network: the `ApiError`'s `detail (code)`; a GLB that does not parse: "the model file could not be read"; no WebGL: "this browser cannot draw 3D" |
| Ready | the canvas, the toolbar, the legend (part 3) | 200 |

Before the press the card's own states come from `model_3d` (User flow 1).

## Bundle

`three` (MIT) and its `GLTFLoader` / `OrbitControls` (`three/examples/jsm/...`) are imported only by
`src/model3d/scene.ts`, and `scene.ts` only through `import('./scene')`. Exact versions pinned (`three` and
`@types/three` 0.187.0 on npm today), installed only after frontend-orch's GO (`node_modules` is shared). No Draco
decoder unless m3d-back's measurements need it (it would be a second lazy chunk plus a wasm file).

Baseline (main c7452e3, `vite build`, 2026-11-14 21:09): one JS chunk `index-*.js` 427.04 kB, gzip 129.57 kB; CSS
75.59 kB. After each part, the PR states the same two numbers and the new lazy chunk's size.

## Licence (Bogdan #14, item 6)

Screenshots and demo views only of publishable models: the e2e sample's synthetic `model/house.ifc` (ours),
DigitalHub (MIT, credit RWTH Aachen), Duplex only from the upstream CC BY 4.0 copy. Never a GLB or a screenshot
derived from Stoa's CC BY-ND copies, also not in a local check that leaves the machine. e2e screenshots use the
sample only.

## Acceptance criteria

Component tests mock `./scene` (`vi.mock`: jsdom has no WebGL) and `getModelGlb` via `mockApi`; `scene.ts`'s
`highlight` and `frame` are unit-tested on a hand-built `three` `Group` (no renderer). Fixtures: `project.json`
(its `model/house.ifc` file) with a derived `model_3d` per state (the backend fixture once m3d-back adds it),
`answer_*.json` with `proof.kind: "model"`.

Part 1, file page:
- M3-1: A file with `model_3d.state` `ready` shows the card "3D view" with "Show in 3D" and "<elements> elements";
  no GLB request before the press. `model_3d` null (a PDF, a PNG, an IFC with `MODEL_3D` off) shows no card and the
  page is otherwise unchanged (today's FileTraceScreen tests pass untouched). [component]
- M3-2: `unavailable` with `reason` "The model is too big for a 3D view (85 MB).": the card shows "3D view
  unavailable: The model is too big for a 3D view (85 MB)." and no button; with an empty reason "3D view unavailable:
  the model cannot be shown in 3D". `not_started` and `converting` show the button as `ready` does. [component]
- M3-3: Pressing "Show in 3D" requests `GET /api/projects/<pid>/files/<fid>/model.glb` once (also under
  StrictMode), shows "Loading the 3D view…", then hands the bytes to `scene.mount`; the canvas is labelled "3D view of
  <path>". [component]
- M3-4: 409 `converting`: "Preparing the 3D view…" and "Try again"; with fake timers a second request goes out after
  5 s, none after the 24th ("Still preparing. Try again later."); "Try again" requests at once; a later 200 shows the
  view. [component]
- M3-5: 422 `too_big` / `no_geometry` with `detail`: "3D view unavailable: <detail>", no "Try again"; 404: "3D view
  unavailable: no 3D model for this file", no retry. [component]
- M3-6: 500 / network / `scene.mount` rejecting (parse error, no WebGL): "3D view unavailable: <reason>" with "Try
  again", which requests again. [component]
- M3-7: Ready: the toolbar has buttons "Rotate left", "Rotate right", "Zoom in", "Zoom out", "Reset view", each
  calling the scene's matching method; Tab reaches each in that order after the canvas. [component]
- M3-8: Leaving the page (unmount) or closing the dialog calls `dispose()` once and aborts a pending GLB request; a
  pending retry timer is cleared. [component]
- M3-9: `getModelGlb` (client unit): GET to the URL with the ids encoded, resolves an `ArrayBuffer`; a 409 rejects
  with its `ApiError` (`status`, `code` `converting`). [unit]

Part 2, chat References (fixture: `project_ask.json` with one part derived as an IFC part: `model_file_id` "f8",
`model_3d` ready, `highlight` [door affected], `pages: []`):
- M3-10: A part with `model_3d` ready / converting / not_started shows "View in 3D: <label>" after its References
  row; `unavailable` or no `model_3d` shows none; the rows, the figure and the arrows are as before (CH-30..CH-35
  tests pass untouched). [component]
- M3-11: The button opens a dialog named "3D view: <label>" whose view requests
  `/api/projects/<pid>/files/<model_file_id>/model.glb`; Esc and "Close" close it (the scene disposed), focus
  returns to the button, Tab stays inside the dialog. [component]
- M3-12: The dialog passes the part's `highlight` to the scene (`[]` when absent). [component]

Part 3, highlight:
- M3-13: `highlight(root, marks, colours)` on a group of 5 named meshes with marks [A moved, B removed, C affected,
  A added, X affected]: A gets the moved colour (first role wins), B the removed colour at opacity 0.5, C the affected
  colour, the other two opacity 0.12 (transparent, no depth write); returns `{counts: {moved: 1, removed: 1,
  affected: 1}, missing: 1, box}` with `box` around A, B and C; the original materials are not mutated; `[]` changes
  nothing and returns `box: null`. [unit]
- M3-14: `frame` puts a given box fully inside the frustum (scene.test.ts); `mount` frames `focusBox(matched,
  whole)` when something matched (centred on it, each side at least half the whole model's: one small door is framed
  no closer than half the building), else the whole model. [unit (frame); component (mount gets the marks)]
- M3-15: The legend: "Moved: 1", "Removed: 1", "Affected: 1" with a swatch each, in role order; "1 of 4 elements are
  not in the 3D view."; "None of these elements are in the 3D view." when none match; nothing for `[]`. [component,
  the mocked scene returning the counts]
- M3-16: `shell.css` defines the four `--v-3d-*` tokens, all different; `model3d.css` still has no colour literal.
  [unit]
- M3-17: [e2e, 1440 and 390] the fixture IFC project, the chat asks "How many doors are there?", the answer's
  References show "View … in 3D"; the dialog draws the model with the legend "Affected: 1"; Esc closes it; no
  sideways scroll; screenshots `model3d-chat`. [e2e]

Everywhere:
- M3-18: Bundle: no module outside `src/model3d/scene.ts` imports `three` (unit test scanning `src/`), and `scene`
  is only imported dynamically; after the build the main `index-*.js` is within +5 kB raw of the baseline above and
  contains no `WebGLRenderer`. [unit; build measurement in the PR]
- M3-19: [e2e, 1440x900 and 390x844, the no-keys backend's `model/house.ifc`, `MODEL_3D` on in
  `e2e/start-backend.sh`] Documents -> the IFC file -> "Show in 3D": a `canvas` appears with non-blank pixels,
  "Reset view" works, no sideways scroll, every toolbar button at least 44x44; screenshots `model3d-file-1440`,
  `model3d-file-390`. Part 2 adds the chat References dialog at both sizes. [e2e]
- M3-20: `model3d.css` uses only `--v-*` tokens (no colour literals); the role colours are read from the computed
  style at mount. [unit]

## More places (feature/model-3d-more, w3:p1 22:55, Tudor: "give the 3D workers what's left")

Same `ModelDialog`, `canShow3d` and highlight as parts 2-3; no new dependency; main bundle within +5 kB of main
2c70d8d.

1. **Agent chat.** Answers: `ChatAnswer`'s References already have "View in 3D" (M3-10..M3-12). Sources: a
   `ChatEvidence` is a place on a page (`page`, `box`); IFC drawings have no pages, so the agent never cites one (probe
   on the e2e fixture, 22:58: "How many doors / walls are there?", "Where is the door?", "Show me the slab", "What is
   the floor area?" each gave `evidence: []`). The other agent place that names a drawing is the **plan pane** (beside
   the chat at >= 1200 px, a sheet below): when a listed file can show 3D, its open row gets a round "3D" button
   (`aria-label` "View in 3D: <name>") over its image (ui-bugs 2, 2026-11-15), opening `ModelDialog` with the newest answered turn's `highlight` for that drawing (its
   part in `turn.answers`), else `[]`.
2. **Documents issue cards** (Bogdan #14 c6883948897, additive; feature/model-3d-issues). Backend: a check's
   `CheckSubject` gets `global_id` when the drawing's model lists the room or door as drawn here
   (`ModelObject.element`), and a `code_check_failed` issue gets `model_file_id` (the IFC file whose GLB shows its
   drawing: its own, or the model a sheet was read from) and `highlight: [{global_id, role: "affected"}]`; each left
   out when none. All three, and `ProjectAnswerPart.model_file_id`/`highlight`, only while `MODEL_3D` is on
   (Bogdan's codecheck #14 c6884150822: off, no payload change); `file_id` stays either way. Frontend: an issue card with a `model_file_id` whose file in `project.files` can show 3D
   (`canShow3d`) gets "View in 3D" (44 px, after "Open the file"), else, for any issue kind, its own `file_id` when
   that file can show 3D (an IFC file's issue, no highlight); the dialog is titled "3D view: <drawing name>" and
   highlights `issue.highlight`. No button without a 3D-capable file or with `MODEL_3D` off.

`ModelDialog` stops Esc and Tab from bubbling: through the React tree a portal's key events reach the plan sheet's
own Esc/Tab handlers, which would close the sheet behind the dialog.

Criteria:
- M3-21: a `PlanPane` file with a `model` shows "View in 3D: <name>" when open, none without; it opens the dialog with the given
  highlight; Esc inside the dialog closes the dialog only (a `PlanSheet` around it stays open). `AgentChat` passes each
  file's model and the newest answered part's `highlight` for that drawing. [component]
- M3-22: [e2e 1440 and 390] the fixture's agent chat after "How many walls are there?": the plan pane (390: "Show the
  plan") -> "View in 3D" -> "Affected: 4"; Esc closes the dialog, the pane stays; screenshots `model3d-pane`. [e2e]
- M3-23: (backend) `check_rule` puts the model object's GlobalId on a subject the model lists as drawn
  (`ModelObject.element`), none otherwise, and the JSON leaves `global_id` out then (`tests/test_code_checks.py`); a
  failed door check on the demo sheet with its IFC model gives the issue `model_file_id` = the IFC file and
  `highlight` = that door's GlobalId; a plain PDF sheet's issues and the other kinds have neither key
  (`tests/api/test_api_model_3d.py`). [unit, api]
- M3-24: `issueModel(issue, files)` = `{fileId, highlight}` from `model_file_id` when that file can show 3D, else
  from `file_id` when that file can; `highlight` = `issue.highlight ?? []`; else null. [unit]
- M3-25: An issue card with such a model shows "View in 3D: <drawing name>"; it opens the dialog on
  `files/<id>/model.glb` with the issue's highlight; Esc closes it and focus returns; no button without one.
  [component] No e2e: the e2e fixtures give no code-check issue on an IFC model (the 3D house has no sheet; the demo
  sheet+model passes the shipped packs), so this is covered by the component and API tests.

## Out of scope

- web-ifc or any IFC parsing in the browser (licence and speed: the brief).
- Per-storey views, sectioning, measuring, picking an element to see its properties.
- Issue cards of kinds other than code checks get no highlight (only a failed check names an element).
- Highlight from edit proposals (`Proposal.services`, Bogdan's cross-discipline GlobalIds): later; the view already
  takes `{global_id, role}` marks, so they only need a caller.

## Open points

Settled by frontend-orch (21:50): states and 409/422 above; no issue cards; part 3 = answers' model objects; load
on press; the blocks in `FileTraceScreen.tsx`, `ChatAnswer.tsx`, `client.ts` are mine; the e2e
backend converts the sample `house.ifc` on the first GET and the e2e waits through "Preparing" (bounded), env name
agreed with m3d-back via frontend-orch; a capped `proof.objects` is fine.

1. **e2e env name** for the backend switch (`MODEL_3D=1`?): with m3d-back via frontend-orch.
2. **Draco / big models.** Waits on m3d-back's numbers (GLB sizes, the 85 MB barlad model). Whole-model GLB
   assumed; a per-storey or bounding-box fallback would add a state here.
3. **e2e picture.** The sample's `model/house.ifc` has extruded `IfcSpace` solids only, so the e2e view shows room
   volumes: enough to check the canvas draws.
4. ~~The file trace has no `model_3d`~~: fixed by m3d-back (21:45, `with_model_3d` on the trace's `file`); M3-19
   runs against it.
