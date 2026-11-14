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
2. The chat's References: an IFC part, today listed as "no preview", opens the same view.
3. Element highlight by a list of `{global_id, role}` (role `moved | removed | added | affected`, one colour each):
   an answer's `proof.objects[].global_id` (all `affected`); later a cross-discipline edit proposal
   (`Proposal.services`, open point 3).

## Files owned

| File | What |
| --- | --- |
| `src/model3d/ModelView.tsx` (new) | `ModelView({projectId, file, highlight?})`: the states, the controls, the legend / highlight line. Imports no `three` |
| `src/model3d/ModelDialog.tsx` (new) | the view in a modal (chat References, the engineer's model proof): `SourcePreview`'s modal pattern (Esc, focus trap, focus back) |
| `src/model3d/scene.ts` (new) | the only module that imports `three`: renderer, `GLTFLoader.parse`, `OrbitControls`, `highlight(root, marks)`, `frame(camera, controls, box)`, `dispose()`. Loaded with `import('./scene')` |
| `src/model3d/model3d.ts` (new) | pure: `modelFileOf(project, drawingId)`, `answerMarks(answer)`, `ROLE_LABEL`, `highlightLine(result)` |
| `src/model3d/model3d.css` (new) | `--v-*` tokens only; one token per role |
| `src/api/client.ts` | only `getModelGlb(projectId, fileId, opts) -> ArrayBuffer` (+ test): `call`'s error handling, the body read as a buffer |
| `src/ingest/FileTraceScreen.tsx` | part 1: the "3D view" card (one block) |
| `src/engineer/ChatAnswer.tsx` | part 2: the References row of an IFC part |
| `src/engineer/ModelProof.tsx` | part 3: "Show in 3D" above the objects table |

The last four are other workers' files (preqa-a / fe-engineer / fe-shared); the change in each is one small block.
frontend-orch to confirm I may edit them (open point 5).

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
- The highlight for answers needs no new field: `AnswerView.proof.objects[]` (`kind: "model"`) already carries
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
2. **Chat References** (part 2). In `ChatAnswer`'s References, a part with no page whose file's `model_3d.state` is
   not `unavailable` is a button "View in 3D" instead of the plain "· no preview" text; it opens `ModelDialog`
   with the file's path as its title, highlighting that part's elements (part 3; until part 3 lands, no highlight).
   Other states keep "· no preview". The left figure and the arrows are unchanged (they still skip parts with no
   page). Applies in the ask chat and the agent chat (both render `ChatAnswer`).
3. **Engineer page** (part 3). `ModelProof` ("Building model: no sheet to draw on.") gets a button "Show in 3D"
   when the drawing's file's `model_3d` is set and not `unavailable`; it opens `ModelDialog` with `answerMarks(answer)`.
4. **Highlight** (part 3). The view takes `highlight: {global_id, role}[]`, role `moved | removed | added |
   affected`. An answer's marks: every distinct non-null `proof.objects[].global_id` as `affected`. Drawn:
   - each matched node gets its role's colour (`--v-3d-moved`, `-removed`, `-added`, `-affected`; `removed` also at
     50% opacity so it reads as going away); an id listed twice keeps its first role;
   - every other node is drawn at 12% opacity (transparent, no depth write);
   - the camera frames the matched nodes' bounding box (10% margin);
   - under the view: a legend of the roles present (a swatch and "Moved 2", "Affected 11"…, `ROLE_LABEL`), and when
     some ids are not in the model "<k> of <m> elements are not in the 3D view." None matched: the whole model, not
     dimmed, and "None of these elements are in the 3D view." Empty list: the whole model, framed, no legend.
   - "Reset view" goes back to this first framing (the highlight stays).

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

Part 2, chat References:
- M3-10: `modelFileOf(project, drawingId)` returns the `files[]` entry with that `drawing_id` when its `model_3d` is
  set and not `unavailable`, else null. [unit]
- M3-11: A `ChatAnswer` part with empty `pages` whose file is `ready` shows "View in 3D" in its References row (no
  "no preview" text); `model_3d` null or `unavailable` keeps "no preview"; parts with pages unchanged (CH-30..CH-35 tests
  pass untouched). [component]
- M3-12: "View in 3D" opens a dialog named "3D view: <file path>" with the view (M3-3's request); "Close" and Esc
  close it, focus returns to the button, Tab stays inside the dialog. [component]

Part 3, highlight:
- M3-13: `answerMarks(answer)` = the distinct non-null `proof.objects[].global_id` as `{global_id, role:
  "affected"}` when `proof.kind` is `model`, else `[]`. [unit]
- M3-14: `highlight(root, marks)` on a group of 5 named meshes with marks [A moved, B removed, C affected, A added,
  X affected]: A gets the moved colour (first role wins), B the removed colour at 50% opacity, C the affected colour,
  the other two 12% opacity (transparent, no depth write); returns `{matched: {moved: 1, removed: 1, affected: 1},
  missing: 1}`; the loaded materials are cloned, not mutated; `[]` changes nothing. [unit]
- M3-15: `frame` puts the matched box fully inside the camera frustum with a 10% margin and the controls' target at
  its centre; with nothing matched it frames the whole model. [unit]
- M3-16: The legend lists only the roles present with their counts ("Moved 1", "Removed 1", "Affected 1"); "1 of 4
  elements are not in the 3D view." when some are missing; "None of these elements are in the 3D view." when none
  match; nothing for `[]`. [component]
- M3-17: A References "View in 3D" and the engineer page's model proof "Show in 3D" pass that answer's
  `answerMarks` to the view. [component]

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

## Out of scope

- web-ifc or any IFC parsing in the browser (licence and speed: the brief).
- Per-storey views, sectioning, measuring, picking an element to see its properties.
- A 3D view on Documents' issue cards (frontend-orch 21:50).
- Highlight from the agent chat's Sources (`ChatEvidence` has no GlobalIds) and from edit proposals
  (`Proposal.services`, Bogdan's cross-discipline GlobalIds): later; the view already takes `{global_id, role}`
  marks, so they only need a caller. Part 3 now = the answers' model objects (`ModelProof`, `ChatAnswer`).

## Open points

Settled by frontend-orch (21:50): states and 409/422 above; no issue cards; part 3 = answers' model objects; load
on press; the blocks in `FileTraceScreen.tsx`, `ChatAnswer.tsx`, `ModelProof.tsx`, `client.ts` are mine; the e2e
backend converts the sample `house.ifc` on the first GET and the e2e waits through "Preparing" (bounded), env name
agreed with m3d-back via frontend-orch; a capped `proof.objects` is fine.

1. **e2e env name** for the backend switch (`MODEL_3D=1`?): with m3d-back via frontend-orch.
2. **Draco / big models.** Waits on m3d-back's numbers (GLB sizes, the 85 MB barlad model). Whole-model GLB
   assumed; a per-storey or bounding-box fallback would add a state here.
3. **e2e picture.** The sample's `model/house.ifc` has extruded `IfcSpace` solids only, so the e2e view shows room
   volumes: enough to check the canvas draws.
4. ~~The file trace has no `model_3d`~~: fixed by m3d-back (21:45, `with_model_3d` on the trace's `file`); M3-19
   runs against it.
