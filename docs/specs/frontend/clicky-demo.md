# Vellum clickable demo (spec)

Status: 2026-11-14 11:40, by vellum-clicky (Tudor's orchestrator); 12:20 the project chat and the conflicts'
"Start a new chat" (Tudor 12:15, as `chat.md` and `conflicts.md` of the real app). Folder: `demo/vellum/`.
Design: Tudor's "Vellum redesign" canvas, boards 1-5 and 9-12 (local copies `*.dc.html`). Boards 6-8 (Edit my plan)
are out, with no link to them.

## Purpose

A static, offline click-through of the whole Vellum story: drop files, watch them being read (simple and advanced),
settle the conflicts, ask with proof, see the workspace history. No build step, no network, no backend: open
`demo/vellum/index.html`. It shows only what the backend has: no country picker, no login or user name (record
0001), no ETA, no sheet numbers, no year or language detection, no answer grade.

## Files

`index.html` (shell), `style.css` (Vellum tokens as in shared.md), `data.js` (the one synthetic data structure and
the pure functions that derive every count, mark and total), `plan.js` (plans as SVG), `app.js` (routes, screens
1-3, 5, 9-12), `ask.js` (screen 4), `chat.js` (the project chat), `data.test.cjs` (`node --test demo/vellum/*.test.cjs`), `README.md`, `vellum-logo.png` (the canvas logo asset). Nothing from
the Stoa dataset is committed; the canvas `.jpg` archive plans are not used: every plan is SVG drawn from `data.js`.
Stoa mode adds `make_stoa_demo.py`, `stoa.js` and `stoa.test.cjs` (see Stoa mode below); its output folder `stoa/` is
gitignored.

## Data rules

- One archive `harbour-block-archive.zip`: 11 files, each routed to a drawing or set aside. Drawings and counts
  shown anywhere (ingest stats, advanced panels, conflicts, answers, history) are derived from it.
- A drawing = a layout (rooms as rectangles in metres, doors, windows, open doorways) plus its source files and lane
  (CAD or vision). Door/window counts and net area are computed from the layout; room areas from the rectangles.
- A conflict is one element of one drawing with two readings (counted or not; door or window). The conflict card's
  variant values, the cross-check pairs and the answers all use the same element, so choosing a variant changes the
  answer the engineer gets.
- Certification: an answer is certified ("Sure", `check` null) when its drawing is read from CAD and none of its marks
  is in dispute or tied to an unsettled conflict. Otherwise it carries `check = {reason, disputed}` in the backend's
  shape (Bogdan, #14 c6875279504): at most 5 items, strongest first (most readers against the answer); each item
  `mark_id` (null: a place a reader saw that the answer did not count, offered as "Add it here"), `why` (one
  sentence), `readers` (`{reader id: what it says}`).
- The project chat uses the shape of `POST /api/projects/{id}/ask` (#135): `{question, parts: [{drawing_id, name,
  answer}], total, total_unit, total_sure, total_note}`, answering parts first, then refused ones; `total` only when
  exactly one drawing answers (else null, with the note that drawings may show the same rooms); `total_unit` `count`
  or `m2`; `total_sure` only for a total from a sure part; `total_note` always one sentence. `canAnswer` (chips when
  every drawing refuses) is the demo's own.
- An area question that names a room ("the kitchen") sums those rooms only; a drawing without that room refuses.

## Stoa mode (local only)

Tudor 12:35: "make the clicky demo be something from the stoa dataset". The Stoa data is partner data: it is never
committed, pushed or uploaded.

- `python3 -I demo/vellum/make_stoa_demo.py [--dataset <junction-dataset>] [--floor <name>]` (stdlib; the default
  dataset is the repo's `data/stoa/full/junction-dataset`, from `tools/fetch_stoa_data.py full`) takes one floor of
  `swiss_dwellings` (CC BY 4.0), by default `site980_bldg2055_floor9178` (Tudor 13:38: "use a photo from the stoa
  dataset site980_bldg2055_floor9178 … for the clicky demo example in both advanced and simple"; 17 English
  questions). Its PNG is the image the person uploads, shown "as uploaded" in Normalise; its PDF and DXF are listed as
  the other files. It writes into `demo/vellum/stoa/`
  (gitignored): the floor's PNG, `data.js` (`window.VStoaData`: the real file names and sizes, the English questions
  with their answer-key values and units, the licence line from the source's `LICENSE.md`), and `index.html`, the
  demo page with `../` paths plus `stoa/data.js` and `../stoa.js` after `../data.js`.
- Open `stoa/index.html`; plain `index.html` stays synthetic. Plain `index.html` does not probe for `stoa/data.js`:
  a script tag to a missing file always logs a console error. (`<base href="../">` is not used either: it would send
  the `#/` links back to the synthetic page.)
- `stoa.js` builds `VData` from it. One drawing (a Swiss Dwellings floor is one drawing), shown as its PNG, with no
  marks: the data has no positions. Answers are the answer key's values, marked "Answer key", with the method line
  quoting the key's question. A question matches by exact text, or by the one key question that holds all its
  content words; several or none gives no answer, with the candidates (or the suggestions) as chips. No conflicts, no
  cross-checks. The reading screens replay the synthetic steps over the real file, and the footer says so and quotes
  the licence line.

## Screens and click map

Header on every screen: logo + "Vellum" (→ `#/`), the view links once a workspace exists (Ingest, Conflicts,
Chat; current one marked; no Engineer tab, `#/ask` opens from "Show it on `<file>`" and "Open the workspace"), "Workspaces" (→ `#/workspaces`). No country picker, avatar or user name. Footer line: "Clickable demo · synthetic data".

| # | Route | Board | What it does |
| --- | --- | --- | --- |
| 1 | `#/` | Main | Drop zone. "Choose files" (file picker) or a drop, and "Try a sample", all start the sample archive (said on screen) → `#/ingest`. Format tags. |
| 2 | `#/ingest` | Ingest | Simple view: 8 steps advance on a clock (~14 s), ring %, stats Elapsed / Files through / Drawings ready / Set aside. Done: "Settle the conflicts" → `#/conflicts` (with no conflicts: "No conflicts found." and "Continue"). Simple / Advanced switch. |
| 9-12 | `#/ingest/unpack`, `/identify`, `/normalise`, `/extract`, `/check` | IngestUnpack, Identify, Normalise, Extract, Check | Advanced: step rail (each step → its panel, the running step pulses; Route → Identify, Drawing model → Extract, Index → Check). Normalise shows the drawing "As uploaded" next to "Normalised" (synthetic: a tilted pencil scan, then the upright plan; Stoa: the PNG both times, already upright). Animated panel, narration and log cycling over the data, stats from the data. Simple ← → Advanced. |
| 3 | `#/conflicts` | Conflicts | 3 conflict cards: two settled by the AI (Approved; Modify → pick a variant or Cancel; "Use the AI decision"), one open (Needs you; plan with the element in amber). After a person's pick the card keeps **Modify** (never "Change"); Cancel puts back what was in use. Progress segments and "`a` settled by the AI. `y` settled by you. `p` needs you." Under the last card (Tudor 12:42): while any card is unsettled, a disabled **Start a new chat** described by "Settle the conflicts that need you first."; once all are settled it links to `#/chat`, next to a quiet "Open the workspace" (`#/ask`). |
| chat | `#/chat` | (Tudor 12:15) | A whole new, empty chat over every drawing: the project name and the ask box ("Ask about the project's drawings") centred in the upper middle, with 3 suggested questions under it (Tudor 12:45): "How many doors are there?", "What is the area of the kitchen?", "How many windows are there?"; a tap asks it. No plan or marks until asked; after the first question the thread shows and the ask box goes to the bottom. An area question that names a room ("the kitchen") sums those rooms only; a drawing without that room does not answer. An answer asks every drawing. A total only when exactly one drawing answers (Bogdan's rule, #14 c6875696652; the other case, parts known disjoint such as storeys of one IFC model, does not occur in the sample); otherwise "`n` drawings answered. These drawings may show the same rooms, so the numbers are not added up." Then one line per drawing "`<file>`: `<value>`" with its state (Sure / Please double-check / Checked by …) and **Show it on `<file>`** → `#/ask` on that drawing with the same question asked there. When every drawing refuses: "I can't answer that from these drawings.", the reason, and chips of what can be asked. |
| 4 | `#/ask` | Workspace | Drawing switcher (prev/next over the drawings), suggestion chips, ask box. Answer card: value, plan with numbered marks, rule, methods, references (click → the original file view over the plan, close ×). Certified: "Sure" badge, "Certified" line. Not certified: "Please double-check: we're not sure about n of these doors", disputed marks amber, **Looks right** / **Fix it** (Reject / Restore per mark, value live) → confirm "Sign off v as [name]" → "Checked by name". Unknown questions are refused with the reason. |
| 5 | `#/workspaces` | Account | "Your workspaces" (no name, no avatar), "New workspace" → `#/`; the sample workspace with its pill, stats (Files, Drawings, Questions, Signed off) and its history built from what was clicked (upload, analysis, each conflict settled, each question, each sign-off). Empty state before any upload. |

Deep links: a project route opened first starts the sample already analysed (conflict 3 open).

## States

- Ingest: running (step n of 8) / done. Advanced panels keep animating after done (they illustrate the step).
- Conflict: `ai` (Approved), `modify` (Choosing, remembers what to Cancel back to), `own` (Your choice: Modify,
  plus "Use the AI decision" where the AI had one), `open` (Needs you).
- Chat: empty / answered (total and per drawing, refused drawings listed after) / refused by every drawing.
- Answer: certified / needs check / fixing / confirming / checked / refused.
- Workspaces: empty / one workspace.

## Checks

- `node --test demo/vellum/*.test.cjs`: counts derived from the layouts (doors, windows, area), conflict variants change the
  answer, certification rule, ingest stats, the project chat (API shape, no total across drawings, the note,
  refusal), room area by name, and Stoa mode against a small made-up fixture (`stoa.test.cjs`).
- Real browser (Playwright) at 1440 and 390 wide: every path clicked, no sideways scroll, no console errors.
- `prefers-reduced-motion`: animations off.
