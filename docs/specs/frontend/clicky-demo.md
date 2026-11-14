# Vellum clickable demo (spec)

Status: 2026-11-14 11:40, by vellum-clicky (Tudor's orchestrator); 12:20 the project chat and the conflicts'
"Start a new chat" (Tudor 12:15, as `chat.md` and `conflicts.md` of the real app). Folder: `demo/vellum/`.
v2 (2026-11-14 14:50, brief `vellum-clicky-v2`, Tudor ~14:05 "go in depth on a new clicky demo version including
these features"): file triage as a preview (decision 0010 with Bogdan's #152 answers c6876983657 and c6877019522),
the project's Drawings and Files lists, a file trace, the issues list (#155), multi-page PDFs (#156, #165) and the
credit line on drawing pages (#163). Dropped because it is not on main: the building-code pre-check and its country
picker (backend PR #150 open; add when it merges).
Design: Tudor's "Vellum redesign" canvas, boards 1-5 and 9-12 (local copies `*.dc.html`). Boards 6-8 (Edit my plan)
are out, with no link to them.

## Purpose

A static, offline click-through of the whole Vellum story: drop files, watch them being read (simple and advanced),
see which files were set aside and why (file triage, a preview), settle the conflicts, ask with proof, work
through the issues list, see the workspace history. No build step, no network, no backend: open
`demo/vellum/index.html`. It shows only what the backend has: no country picker, no login or user name (record
0001), no ETA, no sheet numbers, no year or language detection, no answer grade.

## Files

`index.html` (shell), `style.css` (Vellum tokens as in shared.md), `data.js` (the one synthetic data structure and
the pure functions that derive every count, mark and total), `plan.js` (plans as SVG), `app.js` (routes, screens
1-3, 5, 9-12), `ask.js` (screen 4), `chat.js` (the project chat), `triage.js` (file triage: the per-file register row,
description and relevance, their words and the trace's triage card, in one unit so the coming shapes swap in one
place), `files.js` (the project's Drawings and Files lists and the file trace), `issues.js` (the issues list and its
pure derivation), `data.test.cjs`, `triage.test.cjs` (`node --test demo/vellum/*.test.cjs`), `README.md`, `vellum-logo.png` (the canvas logo asset). Nothing from
the Stoa dataset is committed; the canvas `.jpg` archive plans are not used: every plan is SVG drawn from `data.js`.
Stoa mode adds `make_stoa_demo.py`, `stoa.js` and `stoa.test.cjs` (see Stoa mode below); its output folder `stoa/` is
gitignored.

## Data rules

- One archive `harbour-block-archive.zip`: 16 files, each routed to a drawing or set aside. Drawings and counts
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
- Multi-page PDF (#156, #165): `plans/floors.pdf` keeps page 1 (floor-02's rendering) with the reason "page 2 holds
  a drawing, read as a file of its own"; its page 2 is the file `plans/floors#p2.pdf` (floor-03's rendering). The
  Unpack log says "page 2 of plans/floors.pdf, as a PDF of its own".

### File triage (preview)

Bogdan, #152 c6877019522: triage is off in the shipped config until the local classifier passes its gate, there is
no model judge (relevance is a rule), and no run is measured yet. So the demo labels every triage element
**Preview** (tooltip: "File triage is coming (decision 0010). It is off in today's demo config until its classifier
passes its check."), shows no recall, P(plan) or cost numbers, and uses the rule's words. The one number quoted is
Bogdan's measurement, credited: "Without triage, ingest keeps only 15 of 214 non-plans out of the floor-plan
readers (Bogdan's measurement)" (Advanced Identify narration).

- Four synthetic images in the sample are triaged as not floor plans, in the shapes of 0010 §8 (#152 c6877087844,
  c6877132244): `Triage.register` (kind and the display-only fields; screens show only the kind in words), the
  description form (`text`, `what_it_is`, `shows_building`, `visible_text`, `detail`), and the relevance computed by
  the rule: related only when a printed word of 4+ letters matches the project's name, its other file or folder
  names or its plans' text; unsure (needs a person) when it shows a building and nothing matches; else unrelated.
  The trace shows `text`, a collapsed "Text printed on it" (`visible_text`), and a collapsed "Full description (a
  model's description, not checked by a person)" (`detail`). Pictures are SVG drawn in `triage.js`.

  | File | Register kind → class | Rule's verdict | Issue |
  | --- | --- | --- | --- |
  | `elevations/south-elevation.png` | elevation → another kind of drawing | related: "Harbour" (the project name) is printed on it | none |
  | `photos/site.jpg` | photograph → not a drawing | unrelated: it shows no building, and no printed word matches | note, open |
  | `misc/poster.jpg` | not architecture → not a drawing | unrelated: as above | note, open |
  | `scans/annex-sketch.jpg` | site plan or map → another kind of drawing (really a plan) | related: "Kitchen" (the text on the plans) is printed on it | none |

- A non-plan is `set_aside` with "not a floor plan: <class words>" and counts in `not_plans` ("4 not floor plans:
  kept, not read"). Files set aside for their format (`readme.txt`, `__MACOSX/…`) have no triage and never count.
- A person's call (file trace, `file-triage.md` steps 4-5): "Your name", "It is related" / "It is not related", then
  "<Verdict sentence>: <name>'s call, <time>. The rule said: <verdict word>." (any verdict can be overruled) and "Undo the call". The name is the
  one typed name of the session (also the double-check sign-off's).
- "Read it as a floor plan" (step 6) on any triaged file: a confirm "Read <path> as a floor plan? This can't be
  undone.", then the file goes queued → running → ready (about 3 s) and gets a drawing: the annex sketch becomes
  drawing 7 `scans/annex-sketch` (a small pencil plan: Kitchen, Room, Store), askable everywhere (drawing switcher,
  project chat). It leaves `not_plans`; its row reads "Read as a floor plan on <name>'s call"; no undo. Read on the
  other three, the reading finds nothing to count, so they get no drawing: the row reads "read as a floor plan:
  no rooms or openings were found on it" (the demo has no layout for them; this is the demo's own wording).
- The identify panel's log shows "identify <path>; triage: <class> (preview)" for each triaged file.

### Issues (#155, decision 0008)

Derived from the data and the clicks, in the API's shape `{id, kind, severity, state, file, why, …}`, ordered by
severity (`fails_rule`, `needs_person`, `note`), then drawing order, files with no drawing last in upload order.
Kinds the demo produces: `conflict` (one per conflict: `needs_person` while unsettled, else `note`; `open` until
settled by the AI or a person, then `settled`), `set_aside` (files set aside for their format: `note`, "Set aside
at ingest: <reason>."), `unrelated_file` (non-plans not related, plus any non-plan a person called or had read as
a plan: `note`, or `needs_person` when the rule says unsure, `open`, `settled` after a call, same id and place; `why` = class, subject,
the rule's reason and the call, e.g. "Not a floor plan (not a drawing: photograph). Unrelated: it shows no building, and no printed word matches
the project's name, its other file or folder names, or its plans. Ana says it is related."). Not produced: `refused_answer`,
`reading_flag`, `code_check_failed` (not on main), `double_check` (not on main).

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

- The archive folder (Tudor via w3:p1: "take pictures from the real dataset as we have them"): with a picks file
  (`--picks`, default `data/stoa/demo-triage.json` next to the dataset, gitignored like all of `data/`) the generator
  copies the real scans it names into `stoa/archive/` and lists them as `archive/<file>`. Sources: `finna`,
  `europeana`, `habs`, `wikimedia` only (never `cubicasa5k`); a NonCommercial licence is refused. Each file shows the
  credit of its own row in its source's `LICENSE.md` (trace card, drawing figure). The picks file names partner files
  and holds what was seen on them (the register row and description, in decision 0010 §8's shapes, each picked and
  checked by eye, labelled "a hand-picked example written for this demo: what a person saw, not a model's output"),
  so it is never committed; the committed generator only reads it. A register kind `floor_plan` makes the file a
  drawing (vision route, "no answer key": every question gets "The answer key has no questions about this drawing,
  so there is no number to give."); the floor keeps the only answer key, so a project answer is still its value as
  the total. Any other kind is set aside and handed to `triage.js` (`VData.TRIAGE` replaces the synthetic sample),
  whose relevance rule then judges it like the sample's files; drawing words (floor, plan, site, section,
  elevation, archive, compass words) are stop-words, so a printed "FLOOR PLAN" matches nothing. Without the picks
  file Stoa mode is the floor alone, as before.

## Screens and click map

Header on every screen: logo + "Vellum" (→ `#/`), the view links once a workspace exists (Ingest, Conflicts,
Chat, Issues; current one marked; no Engineer tab, `#/ask` opens from "Show it on `<file>`" and "Open the workspace"), "Workspaces" (→ `#/workspaces`). No country picker, avatar or user name. Footer line: "Clickable demo · synthetic data".

| # | Route | Board | What it does |
| --- | --- | --- | --- |
| 1 | `#/` | Main | Drop zone. "Choose files" (file picker) or a drop, and "Try a sample", all start the sample archive (said on screen) → `#/ingest`. Format tags. |
| 2 | `#/ingest` | Ingest | Simple view: 8 steps advance on a clock (~14 s), ring %, stats Elapsed / Files through / Drawings ready / Set aside. Done: "Settle the conflicts" → `#/conflicts` (with no conflicts: "No conflicts found." and "Continue"). Simple / Advanced switch. |
| 2b | `#/ingest` (under the card) | Project screen | "Drawings": one card per drawing (name, lane, kind) with "Open" → `#/ask` on it. "Files": one row per file (path, kind, state badge with word and icon, size; the reason or the triage line), each a link to its trace; under the heading the `not_plans` line with the Preview pill once done. Rows follow the clock: "queued" until the file is through, then its state; a triaged row reads "Not a floor plan: <class words> · <subject>", then "– Not judged" until the project is done, then the verdict pill, and " · <name>'s call" after a call. |
| trace | `#/file/<n>` | (ingest.md trace) | "Back to the project", the state badge over the path `h1`, "Open the drawing" when it has one; facts (Kind, Size, State, Route or Reason); for a triaged file the triage card (Preview): "Not a floor plan: <class words>", "Kind: <register kind>", the picture "as uploaded", "What is on it" (text, a collapsed "Text printed on it", a collapsed "Full description (a model's description, not checked by a person)"), "Does it belong to this project?" (pill, sentence, "The rule says <why>.", "Matched on: …", "Decided by the rule: …"), the call, "Read it as a floor plan". |
| issues | `#/issues` | (issues.md) | "Issues", the counts line ("3 open · 1 settled"), filters "Kind" and "State" (`<select>`, "All" then "<word> (n)"), "Export CSV" (the API's CSV columns, `harbour-block-archive-issues.csv`). Rows grouped by severity heading ("Fails a rule", "Needs a person", "Note"): number, kind pill (icon + word: Conflict ⇄, Set aside –, Not a floor plan ▭), state, `why`, place line ("<file> · the whole drawing" or "not on a drawing"), and the jump: conflict "Settle" / "See the conflict" → `#/conflicts`; set aside "Why it was set aside" and not a floor plan "Make a call" / "See the call" → the file's trace. Empty: "No issues: nothing needs a look." |
| 9-12 | `#/ingest/unpack`, `/identify`, `/normalise`, `/extract`, `/check` | IngestUnpack, Identify, Normalise, Extract, Check | Advanced: step rail (each step → its panel, the running step pulses; Route → Identify, Drawing model → Extract, Index → Check). Normalise shows the drawing "As uploaded" next to "Normalised" (synthetic: a tilted pencil scan, then the upright plan; Stoa: the PNG both times, already upright). Animated panel, narration and log cycling over the data, stats from the data. Simple ← → Advanced. |
| 3 | `#/conflicts` | Conflicts | 3 conflict cards: two settled by the AI (Approved; Modify → pick a variant or Cancel; "Use the AI decision"), one open (Needs you; plan with the element in amber). After a person's pick the card keeps **Modify** (never "Change"); Cancel puts back what was in use. Progress segments and "`a` settled by the AI. `y` settled by you. `p` needs you." Under the last card (Tudor 12:42): while any card is unsettled, a disabled **Start a new chat** described by "Settle the conflicts that need you first."; once all are settled it links to `#/chat`, next to a quiet "Open the workspace" (`#/ask`). |
| chat | `#/chat` | (Tudor 12:15) | A whole new, empty chat over every drawing: the project name and the ask box ("Ask about the project's drawings") centred in the upper middle, with 3 suggested questions under it (Tudor 12:45): "How many doors are there?", "What is the area of the kitchen?", "How many windows are there?"; a tap asks it. No plan or marks until asked; after the first question the thread shows and the ask box goes to the bottom. An area question that names a room ("the kitchen") sums those rooms only; a drawing without that room does not answer. An answer asks every drawing. A total only when exactly one drawing answers (Bogdan's rule, #14 c6875696652; the other case, parts known disjoint such as storeys of one IFC model, does not occur in the sample); otherwise "`n` drawings answered. These drawings may show the same rooms, so the numbers are not added up." Then one line per drawing "`<file>`: `<value>`" with its state (Sure / Please double-check / Checked by …) and **Show it on `<file>`** → `#/ask` on that drawing with the same question asked there. When every drawing refuses: "I can't answer that from these drawings.", the reason, and chips of what can be asked. After the first question (Tudor via w3:p1): up to 3 **follow-up chips** under the thread, each answerable here and not yet asked: the elevation question first, then the suggestions (synthetic adds "How many rooms are there?", "What is the net floor area?", "What is the area of the living room?"; Stoa the answer key's suggestions). **The elevation question** ("How many storeys does the building in the elevation have?", or any question naming the elevation or the facade, when the project holds a set-aside elevation): answered from that file's triage description only, a preview: the description's sentences holding a word of the question in quotes (else "The description does not say. What it says:" and its summary), pills **Preview** (tip: the real backend keeps this description for later AI use and does not answer from it yet) and **Not checked by a person**, never Sure; "From a model's description of a set-aside drawing, not checked by a person" (Stoa: the hand-picked-example wording); then References: the picture as a thumbnail button that opens it full size in place (Stoa also "Open the original image"), its path (link to its trace), class and kind, its credit; then "What it pulled from the picture": the description, the register kind, the text printed on it, and the full description collapsed. |
| 4 | `#/ask` | Workspace | Drawing switcher (prev/next over the drawings), suggestion chips, ask box. Answer card: value, plan with numbered marks, rule, methods, references (click → the original file view over the plan, close ×). Certified: "Sure" badge, "Certified" line. Not certified: "Please double-check: we're not sure about n of these doors", disputed marks amber, **Looks right** / **Fix it** (Reject / Restore per mark, value live) → confirm "Sign off v as [name]" → "Checked by name". Unknown questions are refused with the reason. |
| 5 | `#/workspaces` | Account | "Your workspaces" (no name, no avatar), "New workspace" → `#/`; the sample workspace with its pill, stats (Files, Drawings, Questions, Signed off) and its history built from what was clicked (upload, analysis, each conflict settled, each question, each sign-off). Empty state before any upload. |

Deep links: a project route opened first starts the sample already analysed (conflict 3 open).

## States

- Ingest: running (step n of 8) / done. Advanced panels keep animating after done (they illustrate the step).
- Conflict: `ai` (Approved), `modify` (Choosing, remembers what to Cancel back to), `own` (Your choice: Modify,
  plus "Use the AI decision" where the AI had one), `open` (Needs you).
- Chat: empty / answered (total and per drawing, refused drawings listed after) / refused by every drawing.
- Answer: certified / needs check / fixing / confirming / checked / refused.
- Workspaces: empty / one workspace (history also lists each call, undo and read-as-plan).
- Triaged file: running, not judged / judged, no call / called / read as a plan (queued, running, ready).
- Issues: open / settled; filtered; empty.

## Checks

- `node --test demo/vellum/*.test.cjs`: counts derived from the layouts (doors, windows, area), conflict variants change the
  answer, certification rule, ingest stats, the project chat (API shape, no total across drawings, the note,
  refusal), room area by name, triage (words for every class and verdict, not_plans, rows and call lines, read as
a plan adds drawing 7), issues (kinds, severity order, states after clicks, ids stable, CSV), and Stoa mode against a small made-up fixture (`stoa.test.cjs`).
- Real browser (Playwright) at 1440 and 390 wide: every path clicked, no sideways scroll, no console errors.
- `prefers-reduced-motion`: animations off.
