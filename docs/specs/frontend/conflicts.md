# Settle the conflicts (spec, Vellum screen 3)
Status: draft, 2026-11-14, by fe-surveyor.  Design: Vellum canvas screen 3, `Conflicts.dc.html` (look only; its
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
| mount | `getProject(pid)` and `getProjectReview(pid)`, in parallel | heading line, the conflicts, the workspace link |
| a card's evidence opens | `getDrawing(drawing_id, {project: pid})`, once per drawing id (kept in a map) | `pages`, `credit`, `file` for the PageViewer |
| Keep a variant | `postReview(drawing_id, {quantity, action: "settle", value}, {project: pid})` | then `getProjectReview(pid)` again |
| Use the rule's value | `postReview(drawing_id, {quantity, action: "reset"}, {project: pid})` | then `getProjectReview(pid)` again |

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
- "Open the workspace": link to the engineer workspace (screen 4) of the first drawing in `review.drawings` with
  `quantities > 0`, else the first drawing; hidden with no drawings.

## States

Screen:

- Loading: the shell's `Loading` until both GETs answer.
- Error: the shell's `ErrorView` with `errorText`; a 404 (no such project) shows "Back to projects" and no Retry,
  anything else Retry (same rule as SV-45).
- Project not done (`project.state` `queued`/`running`): a line under the heading "Still reading the drawings: these
  are the conflicts so far." and a "Check again" button that reloads both GETs. `failed`: "Reading stopped: `error`."
  The cards still show.
- No conflicts: heading as above, no cards, the workspace link unlocked.

Per card (`mode` is local state, keyed by `drawing_id + quantity`, reset when the card's server state changes):

| Server state | Mode | Pill | Tiles | Action line | Buttons |
| --- | --- | --- | --- | --- | --- |
| `needs_person` | open | "Needs you" (warn) | enabled, none pressed | "Tap the right value." | (none) |
| rule, not settled | rule | "Settled by rule" (ok) | disabled, rule's pressed | (empty) | Modify |
| rule, not settled | choosing | "Choosing" (muted) | enabled, rule's pressed | "Tap the right value." | Cancel |
| `settled` | yours | "Your choice" (accent) | disabled, in-use pressed | "You kept `X`." / "You kept `X`, over the rule's choice." / "You settled it at `formatValue(settled.value)` in the surveyor workspace." (no tile matches) | Change; plus "Use the rule's value" when `resolution` |
| `settled` | choosing | "Choosing" | enabled | "Tap the right value." | Cancel |
| any | saving | unchanged | all disabled | "Saving…" | disabled |

- Tapping an enabled tile sends `settle` with that tile's value; pressing the tile already in use only leaves
  choosing mode (no request).
- "Use the rule's value" sends `reset` for the quantity after a confirm: "Use the rule's value? This also undoes
  every other edit and any sign-off of `label` on `file`." (the API's `reset` drops all of them; Not in the API 3).
- A failed POST: the card shows `errorText(err)` under its buttons (role alert) and goes back to its mode; a 409
  (signed off) reads "This value is signed off. Undo the sign-off in the surveyor workspace first." with the
  workspace link.
- Tooltips on the pill (hover and focus, as the design): open "The rules could not decide. Pick a value before you
  open the workspace."; rule "A rule settled this: `resolution.rule`. Modify it if you disagree."; yours "You picked
  this value; it overrides the rule."; choosing "Tap the right value, or Cancel."
- Evidence (`<details>` "Where each value was read"): open by default when the card needs a person, closed
  otherwise; the drawing is fetched when it first opens (Loading inside; an error line with Retry inside the
  details, not the whole screen). Values with no `box` are listed as "`X`: not located on the page."

Workspace link: while any card needs a person it is a disabled button "Open the workspace" with the text "Settle
the conflicts that need you first." (`aria-describedby`); otherwise an `<a>`.

## Layout

The design's: header (shell's), then a centred column, max-width 820px, padding 48px 24px 72px, 20px between parts.

- Heading row: kicker (13px, 600, `--v-ok`), h1 44px/1.1 700, sub line 16px `--v-muted`; the workspace link on the
  right (pill, 980px radius, `--v-accent` fill, white, 44px tall; locked: `--v-fill` fill, `--v-muted` text).
- Progress row: segments 180px wide, 6px tall, 3px radius, 4px gap; text 13px tabular numbers.
- Cards: `--v-surface`, radius `--v-radius` (the design's 22px folds into it), `--v-shadow`, padding 24px 24px 20px, 16px gap. Top: kicker
  12px muted, h2 24px 600, file line monospace (`ui-monospace, Menlo, monospace`, no web font) 12px, wraps
  anywhere; pill right. Tiles in a 2-column grid (12px gap; 3+ values wrap to more rows), each a button: 16px
  padding, 16px radius, 1px `--v-line` border; pressed: 2px `--v-accent` border, `--v-accent-soft` background and the
  check badge "in use". Why: `<details>` on `--v-fill`, 14px radius. Actions row: the action text left, the
  buttons right (pills, 44px tall).
- Phone 390: the heading row stacks (link under the text), tiles one column, the h1 32px, no sideways scroll,
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
- CF-4: an empty `conflicts` shows "No conflicts found", the agree line, no cards, and an enabled workspace link.
- CF-5: a card shows "Conflict 1 of 1 · settled by a rule", `label`, `file`, tile A "22.40 m²" with
  `methodName('polygon_x_scale')`, page 1, and tile B "30.00 m²" with "· the rule's choice" and pressed.
- CF-6: a rule card's tiles are disabled; Modify enables them and shows Cancel; Cancel restores it, no request.
- CF-7: in choosing mode, tapping tile A sends `POST /api/drawings/<did>/review?project=<pid>` with exactly
  `{"quantity": "area:room|name=1.01", "action": "settle", "value": 22.401}`, shows "Saving…", then reloads
  `GET …/review` and renders the reloaded data.
- CF-8: a `settled` card at 22.401 shows "Your choice", tile A pressed, "You kept A, over the rule's choice." and
  both "Change" and "Use the rule's value".
- CF-9: "Use the rule's value" asks the confirm; accepted, sends `{"quantity": …, "action": "reset"}` with
  `?project=<pid>`; dismissed, sends nothing.
- CF-10: a `needs_person` card shows "Needs you", enabled tiles with none pressed, the evidence open, and the
  workspace link disabled with "Settle the conflicts that need you first."
- CF-11: a `settled` value matching no tile shows no tile pressed and "You settled it at … in the surveyor
  workspace."
- CF-12: opening the evidence sends `GET /api/drawings/<did>?project=<pid>` once per drawing (two cards of one
  drawing: one request) and renders PageViewer with `marks: []` and `conflict` = the entry's conflict.
- CF-13: a drawing fetch error shows an error line with Retry inside that card's evidence; the rest of the screen
  stays.
- CF-14: a 409 on settle shows the signed-off sentence (role alert) and the workspace link of that card; the card
  returns to choosing mode.
- CF-15: a load 404 shows "Back to projects" (`#/`) and no Retry; a 500 shows Retry, which reloads both GETs.
- CF-16: `project.state` "running" shows "Still reading the drawings…" and "Check again" reloads both GETs.
- CF-17: "Open the workspace" links to `#/p/<pid>/d/<first drawing with quantities>/engineer`.
- CF-18: each card's "Open in the surveyor workspace" links to `#/p/<pid>/d/<did>/surveyor?q=<quantity encoded>`.
- CF-19: ProjectReviewSide shows "Settle the conflicts" linking to `#/p/<pid>/conflicts` when the project has at
  least one conflict.
- CF-20: no mock value of the design appears (no "harbour", "Beatrice", "IfcDoor", country names): a test renders
  the screen and asserts none of these strings are in the document.
- CF-21: the pill is focusable and its tooltip text is its accessible description.

[e2e] (fe-golden, `frontend/e2e/`, at 1440 and 390, sample project):

- CF-22: from the project screen's link (or `#/p/<pid>/conflicts`), the sample shows "1 conflict found" with
  "area of room (name 1.01)" on `plans/flat-b.pdf`; Modify, tap A, the pill reads "Your choice"; "Use the rule's
  value", confirm, the pill reads "Settled by rule". No sideways scroll at 390.

## Not in the API

1. **`signed` on `ConflictEntry`** (`SignOff | null`, as on `Row`): the card cannot tell a signed-off conflict, so
   it offers Keep and learns of the sign-off from a 409. With it: the pill "Signed off by `by`", tiles disabled.
2. **`value` on `ConflictEntry`** (the row's current value): after a mark edit in the surveyor workspace the value
   in use is a recount that is neither variant; the card cannot show it. With it: "In use: `value`".
3. **An `unsettle` action** (drop the settled value only): "Use the rule's value" must send `reset`, which also
   drops the quantity's mark edits and sign-off; hence the confirm.
4. **A plain-words title per conflict** (the design's "Is the balcony glazing a window?") and **a rule list per
   conflict** (the design shows two rules and a "why" paragraph): the API has one `resolution.rule` sentence and
   `note`. The card shows `label` and those.
5. **Who settled and when in words**: `settled.at` exists, `settled` has no `by`; the card says "you", as the
   surveyor's own browser does not know other people. Fine for v1 (no login).

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
