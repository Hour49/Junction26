# Settle the conflicts (spec, Vellum screen 3)
Status: built, 2026-11-14, by fe-surveyor (orch D61; Tudor CHANGE 11:05; Bogdan's triage CHANGE 11:07).  Design: Vellum canvas screen 3, `Conflicts.dc.html` (look only; its
data is mock).  API: docs/API.md `GET /api/projects/{project_id}/review`, `POST /api/drawings/{drawing_id}/review`.

## Purpose

After ingest, one page lists every place in the project where two measuring methods read different values. For each
it says whether a rule settled it (and by which rule) or whether it needs a person, shows both values with where
each was read on the drawing, and lets the person keep one value or change a rule's choice. The workspace button
unlocks once nothing needs a person.

## Files owned

- `frontend/src/surveyor/ConflictsScreen.tsx`: `ConflictsScreen({projectId}: {projectId: string})`, the route
  component for `#/p/<pid>/conflicts` (route and `App.tsx` wiring: fe-shared). Loads, holds the review and the
  per-card mode, sends the edits.
- `frontend/src/surveyor/ConflictCard.tsx`: one conflict (heading, pill, variant tiles, why, evidence, actions).
- `frontend/src/surveyor/conflicts.ts`: pure functions: the card's state, the in-use variant, the summary words
  (unit-tested).
- `frontend/src/surveyor/conflicts.css`: this screen's styles, tokens only (`--v-*`, shared.md).
- `frontend/src/surveyor/ConflictsScreen.test.tsx`, `conflicts.test.ts`.
- `frontend/src/surveyor/ProjectReviewSide.tsx` (already mine): a "Settle the conflicts" link (CF-19).

Uses, does not own: `src/api/` (getProject, getProjectReview, getDrawing, postReview, formatValue, formatTime,
methodName, errorText), `src/shell/` (Loading, ErrorView, routeHref), `src/viewer/PageViewer.tsx`.

## API calls

| When | Call | Used for |
| --- | --- | --- |
| mount | `getProject(pid)` and `getProjectReview(pid)`, in parallel | heading line, the conflicts, the chat button |
| a card's evidence opens | `getDrawing(drawing_id, {project: pid})`, once per drawing id (kept in a map) | `pages`, `credit`, `file` for the PageViewer |
| Keep a variant | `postReview(drawing_id, {quantity, action: "settle", value}, {project: pid})` | then `getProjectReview(pid)` again |
| Use the rule's value | `postReview(drawing_id, {quantity, action: "unsettle"}, {project: pid})` | then `getProjectReview(pid)` again |

The POST returns that drawing's whole takeoff; the screen ignores it and reloads the project review, which is the
one source of the cards (a storey twin, K4, is listed once by the server; merging takeoff rows here would redo
that). One request in flight per card; the other cards stay usable.

## Field map

Per `ConflictEntry` `c` (in the server's order; the card number is its index + 1):

| Design element | Value |
| --- | --- |
| kicker "Conflict 1 of 3 · solved by the AI" | "Conflict `i` of `n` · " + "needs you" (`c.needs_person`), "settled by you" (`c.settled`), else "settled by a rule" |
| title "Doors on storey 1" | `c.label` (e.g. "area of room (name 1.01)") |
| mono file line | `c.file` |
| pill | see States per card |
| variant tile kicker "Variant 1 · AI decision" | letter `A`, `B`… in `c.conflict.values` order (the letters PageViewer tags the page with, and the surveyor's Keep buttons use) + " · the rule's choice" when it is the rule's variant |
| tile label "13 doors" | `formatValue(v.value, v.unit)` |
| tile source line | `methodName(v.method)` + ", page `v.page`" when set |
| why title | "Why the rule chose `X`" (rule's variant `X`), else "Why no rule decides" |
| why list | `c.conflict.resolution.rule`; then `c.conflict.note` and `c.conflict.derived` when set |
| why text when no rule | `c.conflict.note` if set, else "No rule decides between these methods. Both readings are on the drawing." |
| plan figure | `PageViewer` (viewer.md) with `file`, `pages`, `credit` from the drawing, `marks: []`, `conflict: c.conflict`: it tags each value's box with its letter |
| link | "Open in the surveyor workspace" → `routeHref({name:'workspace', projectId, drawingId: c.drawing_id, role:'surveyor', query: q=c.quantity})` |

Variant indexes: the rule's variant is the first `i` with `values[i].value === resolution.value`; the in-use
variant is the first `i` with `values[i].value === settled.value` when `settled`, else the rule's variant. Values
are compared as numbers as the server sends them (it sends the same float for both).

Heading, from `project` and `review`:

- kicker: "`project.name` · `n` drawings ready" (`n` = `review.drawings.length`; "1 drawing ready").
- h1: "`k` conflicts found" / "1 conflict found" / "No conflicts found".
- sub line, built from the parts that are non-zero, in this order, joined with ". ": "`r` settled by a rule",
  "`y` settled by you", "`p` need(s) you"; e.g. "2 settled by a rule. 1 needs you." Zero conflicts: "Both methods
  agree wherever two of them measured."
- progress: one segment per conflict, filled (`--v-accent`) when it does not need a person; text "`s` of `k`
  settled". More than 12 conflicts: the segments join into one bar (gap 0) so they stay visible.
- **"Start a new chat"** (Tudor 2026-11-14, brief fe-chat.md; replaces "Open the workspace" as the primary action):
  link to `#/p/<pid>/chat` (ProjectChat, an empty chat over the whole project), no line under it (Tudor 12:45: "remove
  ask anything about the … drawing project"); hidden with no drawings. Beside it a quiet text link "Open the workspace" to the engineer workspace (screen 4) of the first drawing
  in `review.drawings` with `quantities > 0`, else the first drawing; shown only when the chat button is unlocked.

## States

Screen:

- Loading: the shell's `Loading` until both GETs answer.
- Error: the shell's `ErrorView` with `errorText`; a 404 (no such project) shows "Back to workspaces" and no Retry,
  anything else Retry (same rule as SV-45).
- Project not done (`project.state` `queued`/`running`): a line under the heading "Still reading the drawings: these
  are the conflicts so far." and a "Check again" button that reloads both GETs. `failed`: "Reading stopped: `error`."
  The cards still show.
- No conflicts: heading as above, no cards, "Start a new chat" unlocked.

Per card (`mode` is local state, keyed by `drawing_id + quantity`, reset when the card's server state changes):

| Server state | Mode | Pill | Tiles | Action line | Buttons |
| --- | --- | --- | --- | --- | --- |
| `needs_person` | open | "Needs you" (warn) | enabled, none pressed | "Tap the right value." | (none) |
| rule, not settled | rule | "Settled by rule" (ok) | disabled, rule's pressed | (empty) | Modify |
| rule, not settled | choosing | "Choosing" (muted) | enabled, rule's pressed | "Tap the right value." | Cancel |
| `settled` | yours | "Your choice" (accent) | disabled, in-use pressed | "You kept `X`." / "You kept `X`, over the rule's choice." / "You settled it at `formatValue(settled.value)` in the surveyor workspace." (no tile matches) | Modify (never "Change", Tudor: a person's choice keeps Modify); plus "Use the rule's value" when `resolution` |
| `settled` | choosing | "Choosing" | enabled | "Tap the right value." | Cancel |
| any | saving | unchanged | all disabled | "Saving…" | disabled |

- Tapping an enabled tile sends `settle` with that tile's value; pressing the tile already in use only leaves
  choosing mode (no request).
- "Use the rule's value" sends `unsettle` for the quantity at once, no confirm (backend PR #121: it drops only the
  settled value; mark edits and sign-offs stay). A 409 (the drawing is signed off) shows the signed-off sentence
  below and the card stays "Your choice".
- A failed POST: the card shows `errorText(err)` under its buttons (role alert) and goes back to its mode; a 409
  (signed off) reads "This value is signed off. Undo the sign-off in the surveyor workspace first." with the
  workspace link.
- A reload after an edit keeps each card (keyed by its quantity, not by its state): an opened "Why …" or "Where
  each value was read" stays open; the card's mode starts over from the new server state (open: choosing, else
  idle) as before (pre-QA c, 2026-11-14).
- Tooltips on the pill (hover and focus, as the design): open "The rules could not decide. Pick a value before you
  open the workspace."; rule "A rule settled this: `resolution.rule`. Modify it if you disagree."; yours "You picked
  this value; it overrides the rule."; choosing "Tap the right value, or Cancel."
- Evidence (`<details>` "Where each value was read"): open by default when the card needs a person, closed
  otherwise; the drawing is fetched when it first opens (Loading inside; an error line with Retry inside the
  details, not the whole screen). Values with no `box` are listed as "`X`: not located on the page."

Chat button: while any card needs a person it is a disabled button "Start a new chat" with the text "Settle the
conflicts that need you first." (`aria-describedby`) and no workspace link; otherwise an `<a>` and the quiet "Open the workspace" link.

## Layout

The design's: header (shell's), then the shell's `.v-page.v-page--narrow` frame (820px, its padding), 20px between parts.

- Heading row: kicker (13px, 600, `--v-ok`), h1 44px/1.1 700, sub line 16px `--v-muted`; nothing on the right.
- Chat block (Tudor 2026-11-14: "put start a new chat at the bottom"): after the last card (after the heading and
  progress when there are no cards), centred: the chat button (pill, 980px radius, `--v-accent` fill, white, 44px
  tall; locked: `--v-fill` fill, `--v-muted` text), the locked reason (only while locked) 13px `--v-muted` under it, the quiet workspace link 13px `--v-accent` under that (40px tall at ≤600px).
- Progress row: segments 180px wide, 6px tall, 3px radius, 4px gap; text 13px tabular numbers.
- Cards: `--v-surface`, radius `--v-radius` (the design's 22px folds into it), `--v-shadow`, padding 24px 24px 20px, 16px gap. Top: kicker
  12px muted, h2 24px 600, file line monospace (`ui-monospace, Menlo, monospace`, no web font) 12px, wraps
  anywhere; pill right. Tiles in a 2-column grid (12px gap; 3+ values wrap to more rows), each a button: 16px
  padding, 16px radius, 1px `--v-line` border; pressed: 2px `--v-accent` border, `--v-accent-soft` background and the
  check badge "in use". Why: `<details>` on `--v-fill`, 14px radius. Actions row: the action text left, the
  buttons right (pills, 44px tall) in every state, also when a long action line puts the buttons on their own line.
- Phone 390: the heading row is text only; the chat block stays centred at the bottom, each card's pill sits above its kicker and title (the
  title gets the card's full width), tiles one column, the h1 32px, no sideways scroll,
  every button at least 44px tall.
- Motion: the design's press scale (0.97) and chevron turn, none under `prefers-reduced-motion`.

## Acceptance criteria

Component tests (vitest, `mockApi`, data derived from `@fixtures` `projectReview` and `project`; the PageViewer is
the same props-recording double as SurveyorScreen.test.tsx):

- CF-1: mount sends `GET /api/projects/<pid>` and `GET /api/projects/<pid>/review`; shows Loading until both answer.
- CF-2: the heading shows "`project.name` · 5 drawings ready", "1 conflict found", and the sub line "1 settled by a
  rule." for `projectReview` as is.
- CF-3: a review with three conflicts (one `needs_person`, one rule, one `settled`) shows "3 conflicts found",
  "1 settled by a rule. 1 settled by you. 1 needs you.", "2 of 3 settled", and two filled segments of three.
- CF-4: an empty `conflicts` shows "No conflicts found", the agree line, no cards, and an enabled "Start a new chat" link.
- CF-5: a card shows "Conflict 1 of 1 · settled by a rule", `label`, `file`, tile A "22.40 m²" with
  `methodName('polygon_x_scale')`, page 1, and tile B "30.00 m²" with "· the rule's choice" and pressed.
- CF-6: a rule card's tiles are disabled; Modify enables them and shows Cancel; Cancel restores it, no request.
- CF-7: in choosing mode, tapping tile A sends `POST /api/drawings/<did>/review?project=<pid>` with exactly
  `{"quantity": "area:room|name=1.01", "action": "settle", "value": 22.401}`, shows "Saving…", then reloads
  `GET …/review` and renders the reloaded data.
- CF-8: a `settled` card at 22.401 shows "Your choice", tile A pressed, "You kept A, over the rule's choice." and
  both "Modify" and "Use the rule's value"; no "Change" button anywhere.
- CF-9: "Use the rule's value" sends `{"quantity": …, "action": "unsettle"}` at once (no confirm) with
  `?project=<pid>`, then reloads the review: the pill reads "Settled by rule". CF-9b: a 409 on it shows "This value
  is signed off. Undo the sign-off in the surveyor workspace first." (role alert) and the card stays "Your choice".
- CF-10: a `needs_person` card shows "Needs you", enabled tiles with none pressed, the evidence open, "Start a new
  chat" a disabled button described by "Settle the conflicts that need you first.", and no "Open the workspace".
- CF-11: a `settled` value matching no tile shows no tile pressed and "You settled it at … in the surveyor
  workspace."
- CF-12: opening the evidence sends `GET /api/drawings/<did>?project=<pid>` once per drawing (two cards of one
  drawing: one request) and renders PageViewer with `marks: []` and `conflict` = the entry's conflict.
- CF-13: a drawing fetch error shows an error line with Retry inside that card's evidence; the rest of the screen
  stays.
- CF-14: a 409 on settle shows the signed-off sentence (role alert) and the workspace link of that card; the card
  returns to choosing mode.
- CF-15: a load 404 shows "Back to workspaces" (`#/workspaces`) and no Retry; a 500 shows Retry, which reloads both GETs.
- CF-16: `project.state` "running" shows "Still reading the drawings…" and "Check again" reloads both GETs.
- CF-17: with nothing needing a person, "Start a new chat" links to `#/p/<pid>/chat`, has no "Ask anything …" line under it, and the quiet "Open the workspace" links to
  `#/p/<pid>/d/<first drawing with quantities>/engineer`.
- CF-28: the chat block follows the last card in the DOM and is not inside the heading row.
- CF-27: after a person picks a value on a card that needed a person (reloaded as settled), the card's button is
  "Modify", never "Change".
- CF-18: each card's "Open in the surveyor workspace" links to `#/p/<pid>/d/<did>/surveyor?q=<quantity encoded>`.
- CF-19: ProjectReviewSide shows "Settle the conflicts" linking to `#/p/<pid>/conflicts` when the project has at
  least one conflict.
- CF-20: no mock value of the design appears (no "harbour", "Beatrice", "IfcDoor", country names): a test renders
  the screen and asserts none of these strings are in the document.
- CF-21: the pill is focusable and its tooltip text is its accessible description.
- CF-23: a `ConflictEntry` with a real `signed` shows the pill "Signed off by `by`", disabled tiles and no Modify.
- CF-24: a rule card with `value: 27.5` (no tile has it) presses no tile and reads "In use: 27.50 m²."; nothing on
  the screen carries `data-pending`.
- CF-25: opening "Why …" and "Where each value was read", then Modify and a tile, leaves both open after the
  reload; the card shows "Your choice" with Modify and disabled tiles (its mode starts over).
- CF-26: at ≤600px `.cf-card-top` is `column-reverse`, `align-items: flex-start` (the pill above the title). [CSS
  text; browser at 390]
- CF-27: `.cf-buttons` has `margin-left: auto` and `justify-content: flex-end` (right-aligned in every state).
  [CSS text; browser at 1440: the button row ends at the same x for "Settled by rule" and "Your choice"]
- Tile accessible names: "`X`: `value`, `method`, page `n`[, the rule's choice][, in use]" (e2e: `/^A\b/`).

[e2e] (fe-golden, `frontend/e2e/`, at 1440 and 390, sample project):

- CF-22: from the project screen's link (or `#/p/<pid>/conflicts`), the sample shows "1 conflict found" with
  "area of room (name 1.01)" on `plans/flat-b.pdf`; Modify, tap A, the pill reads "Your choice"; "Use the rule's
  value", the pill reads "Settled by rule". No sideways scroll at 390.

## Not in the API

1. **`signed` on `ConflictEntry`** (`SignOff | null`, as on `Row`): the card cannot tell a signed-off conflict, so
   it offers Keep and learns of the sign-off from a 409. With it: the pill "Signed off by `by`", tiles disabled.
2. **`value` on `ConflictEntry`** (the row's current value): after a mark edit in the surveyor workspace the value
   in use is a recount that is neither variant; the card cannot show it. With it: "In use: `value`".
3. ~~An `unsettle` action~~: real since backend PR #121 (vellum 732ec9d); "Use the rule's value" sends it.
4. **A plain-words title per conflict** (the design's "Is the balcony glazing a window?") and **a rule list per
   conflict** (the design shows two rules and a "why" paragraph): the API has one `resolution.rule` sentence and
   `note`. The card shows `label` and those.
5. **Who settled and when in words**: `settled.at` exists, `settled` has no `by`; the card says "you", as the
   surveyor's own browser does not know other people. Fine for v1 (no login).

## Pending fields (mocked)

None left. `ConflictEntry.signed` and `ConflictEntry.value` landed with backend PR #120 (vellum 859eed6) and are read
directly: `signed` drives the pill "Signed off by `by`" and locks the card; `value` picks the pressed tile, and a
value no tile has (a recount in the workspace) reads "In use: `value`." on a rule card. A card that needs a person
presses no tile whatever `value` says. The `unsettle` edit action is real too (PR #121): "Use the rule's value"
sends it, no confirm. Not coming, so not mocked: a plain-words title (`h2` = `label`), a rule
list (rule, note, derived), `Settled.by` ("you").

## Out of scope

- Typing a value that is neither variant (the surveyor workspace's Settle field does that; the card links there).
- Mark edits, sign-off, CSV: the surveyor workspace.
- The design's country picker and user avatar (common brief).
- Live updates from other tabs (no push); "Check again" while ingest runs.
- Blocking the workspace anywhere else than this screen's button: the header, the project screen and direct links
  still open it; the server already refuses to sign off a conflict that needs a person.

## Open points

1. **"The AI settled two" vs "settled by a rule".** The design says "AI"; the server's `resolution` is a fixed rule
   (`resolution.rule`, e.g. "the printed label over the outline at the sheet's scale"), and the surveyor workspace
   already says "decided by rule". Recommendation: say "rule" (accurate, one word across screens). Orch to confirm.
2. **Where screen 3 is linked from.** This spec adds the link in ProjectReviewSide (CF-19). fe-ingest's
   ProjectScreen should link "Settle `k` conflicts" when `GET …/review` has conflicts; that is ingest.md's call.
3. **The workspace target.** The design has one "Open the workspace" per project; routes need a drawing.
   Recommendation: the first drawing with quantities (CF-17), the engineer role (screen 4).
