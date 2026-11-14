# Vellum clickable demo (spec)

Status: 2026-11-14 11:40, by vellum-clicky (Tudor's orchestrator). Folder: `demo/vellum/`.
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
1-3, 5, 9-12), `ask.js` (screen 4), `data.test.cjs` (`node --test demo/vellum/*.test.cjs`), `README.md`, `vellum-logo.png` (the canvas logo asset). Nothing from
the Stoa dataset; the canvas `.jpg` archive plans are not used: every plan is SVG drawn from `data.js`.

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

## Screens and click map

Header on every screen: logo + "Vellum" (→ `#/`), the view links once a workspace exists (Ingest, Conflicts,
Engineer; current one marked), "Workspaces" (→ `#/workspaces`). No country picker, avatar or user name. Footer line: "Clickable demo · synthetic data".

| # | Route | Board | What it does |
| --- | --- | --- | --- |
| 1 | `#/` | Main | Drop zone. "Choose files" (file picker) or a drop, and "Try a sample", all start the sample archive (said on screen) → `#/ingest`. Format tags. |
| 2 | `#/ingest` | Ingest | Simple view: 8 steps advance on a clock (~14 s), ring %, stats Elapsed / Files through / Drawings ready / Set aside. Done: "Settle the conflicts" → `#/conflicts`. Simple / Advanced switch. |
| 9-12 | `#/ingest/unpack`, `/identify`, `/extract`, `/check` | IngestUnpack, Identify, Extract, Check | Advanced: step rail (each step → its panel, the running step pulses), animated panel, narration and log cycling over the data, stats from the data. Simple ← → Advanced. |
| 3 | `#/conflicts` | Conflicts | 3 conflict cards: two settled by the AI (Approved; Modify → pick a variant or Cancel; "Use the AI decision"), one open (Needs you; plan with the element in amber). Progress segments. "Open the workspace" locked until all are settled → `#/ask`. |
| 4 | `#/ask` | Workspace | Drawing switcher (prev/next over the drawings), suggestion chips, ask box. Answer card: value, plan with numbered marks, rule, methods, references (click → the original file view over the plan, close ×). Certified: "Sure" badge, "Certified" line. Not certified: "Please double-check: we're not sure about n of these doors", disputed marks amber, **Looks right** / **Fix it** (Reject / Restore per mark, value live) → confirm "Sign off v as [name]" → "Checked by name". Unknown questions are refused with the reason. |
| 5 | `#/workspaces` | Account | "Your workspaces" (no name, no avatar), "New workspace" → `#/`; the sample workspace with its pill, stats (Files, Drawings, Questions, Signed off) and its history built from what was clicked (upload, analysis, each conflict settled, each question, each sign-off). Empty state before any upload. |

Deep links: a project route opened first starts the sample already analysed (conflict 3 open).

## States

- Ingest: running (step n of 8) / done. Advanced panels keep animating after done (they illustrate the step).
- Conflict: `ai` (Approved), `modify` (Choosing), `own` (Your choice), `open` (Needs you).
- Answer: certified / needs check / fixing / confirming / checked / refused.
- Workspaces: empty / one workspace.

## Checks

- `node --test demo/vellum/*.test.cjs`: counts derived from the layouts (doors, windows, area), conflict variants change the
  answer, certification rule, ingest stats.
- Real browser (Playwright) at 1440 and 390 wide: every path clicked, no sideways scroll, no console errors.
- `prefers-reduced-motion`: animations off.
