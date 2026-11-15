# Settle the conflicts (spec, Vellum screen 3)
Status: built, 2026-11-14, by fe-surveyor; demo parity (section below) built 2026-11-14 ~17:00 (GO, D45) (orch D61; Tudor CHANGE 11:05; Bogdan's triage CHANGE 11:07).  Design: Vellum canvas screen 3, `Conflicts.dc.html` (look only; its
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
| `settled` | yours | "Your choice" (accent) | disabled, in-use pressed | "You kept variant `n`." / "You kept variant `n`, over the rule's choice." / "Your answer: `formatValue(settled.value)`." (no tile matches; CF-43) | Modify (never "Change", Tudor: a person's choice keeps Modify); plus "Use the rule's value" when `resolution` |
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
- CF-8: a `settled` card at 22.401 shows "Your choice", tile 1 pressed, "You kept variant 1, over the rule's choice." and
  both "Modify" and "Use the rule's value"; no "Change" button anywhere.
- CF-9: "Use the rule's value" sends `{"quantity": …, "action": "unsettle"}` at once (no confirm) with
  `?project=<pid>`, then reloads the review: the pill reads "Settled by rule". CF-9b: a 409 on it shows "This value
  is signed off. Undo the sign-off in the surveyor workspace first." (role alert) and the card stays "Your choice".
- CF-10: a `needs_person` card shows "Needs you", enabled tiles with none pressed and the typed box (the chat
  button's lock moved to the host, ingest.md).
- CF-11: a `settled` value matching no tile shows no tile pressed and "Your answer: …" (CF-43).
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
- CF-19: ProjectReviewSide shows "Settle the conflicts" when a conflict needs a person, else "See the conflicts",
  when the project has at least one conflict. It links to `#/p/<pid>?d=<drawing>&q=<quantity>` of the first conflict
  that needs a person (else the first), so the project page opens on that card (CF-29's focus), not its top
  (R4-B9). Each conflict's state uses the card's words: "needs you", "settled by a rule", "picked by …",
  "settled by you" (R4-B11).
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

## Checks and issues (#139 / #140, spec 2026-11-14 13:50, fe-surveyor; contract board #142)

Draft for frontend-orch's review; nothing built yet. Shapes come from #142 and may change while Bogdan's PRs are open;
until they land, the types are fe-scaffold's (`src/checks/types.ts`) and fe-ingest's (`src/issues/types.ts`), imported,
not copied.

### Props (seam with fe-shared)

`ConflictsScreen({projectId, query})`: `query?: URLSearchParams` is the route's query, passed by `App.tsx`
(fe-shared, one line; `ConflictsScreen: ComponentType<{ projectId: string; query?: URLSearchParams }>`). It reads:

- `pack`: the chosen rule pack (`?pack=fi`), the screen choice fe-shared keeps across project routes; absent = no checks.
- `d` + `q`: a conflict to show (`ConflictEntry` identity: `drawing_id` + `quantity`), set by an issue link.

Every project route this screen links to carries `pack` when it is set (the chat button, the quiet workspace link,
each card's surveyor link), so the choice survives the hop (fe-shared's rule; the header's own links are fe-shared's).

### Issue links (with fe-ingest)

`src/surveyor/issueLinks.ts` (new, mine): `issueRoute(issue, projectId, pack?): string | null`, a pure function the
issues screen (fe-ingest) uses for the two kinds that land on my screens; it returns null for every other kind
(fe-ingest builds those). Built from the issue's fields (`kind`, `drawing_id`, `quantity` = the takeoff `Row.key`, `question`), never from
`issue.links` (API paths, Bogdan c6876010899).

| `Issue.kind` | Route | On arrival |
| --- | --- | --- |
| `conflict` | `#/p/<pid>/conflicts?d=<drawing_id>&q=<quantity>[&pack=]` | that card scrolls into view (`block: "center"`), gets `aria-current="true"` and a 2px `--v-accent` outline, its evidence opens, focus goes to its title (`tabIndex=-1`); a `d`/`q` naming no card: nothing happens, no error |
| `refused_answer` | `drawing_id` set: `#/p/<pid>/d/<did>/engineer?ask=<question>[&pack=]` (EN-72); null: `#/p/<pid>/chat?ask=<question>[&pack=]` (CH-14); the question verbatim, URL-encoded | the engineer / chat asks it on open (frontend-orch review decision) |

A `conflict` issue with `drawing_id` null or no `quantity` (should not happen) falls back to `#/p/<pid>/conflicts`.
The issue's `state` and the card agree because both come from the same review store (`settled` / `signed_off` =
`ConflictEntry.settled` / `signed`, #142 review point 20); the conflicts screen does not read issues.

### Checks row (only with `?pack=`)

Between the progress row and the first card, one row on `--v-surface` (radius `--v-radius`, padding 16px 20px):

- Title "Building-code pre-check: `pack name`" (the pack's display `name` from fe-shared's rule packs, `/api/info
  rule_packs`; the pack id when the list is not loaded yet). No pack is preselected; without `?pack=` (valid: "no
  pack") there is no row. One pack at a time (a single `?pack=`).
- Counts **per rule** (frontend-orch decision, matching fe-scaffold's checks screen) over `GET /api/projects/{pid}/
  checks?pack=<id>` (fe-shared's `getProjectChecks`): a rule's results are gathered across every drawing (by
  `rule_id`); the rule is **failed** if any result is `fail`, else **cannot tell** if any is `cannot_tell`, else
  **passed**; counted exactly as the checks screen (`ruleSummary` + `ruleCounts` from
  `src/checks/checks.ts`, reused): a RuleCheck that is `cannot_tell` with no results (nothing read on that drawing) counts
  as **cannot tell**; a `not_applicable` RuleCheck is never passed or failed and is not counted (CF-30b, Bogdan's
  `project_checks.json` and derivations). Shown as "`a` rules passed · `b` failed · `c` cannot
  tell" ("1 rule passed" for one; the noun only on the first part), each part a pill (passed `--v-ok` on `--v-ok-soft`,
  failed `--v-danger` on `--v-danger-soft`, cannot tell `--v-text-2` on `--v-fill`); zero parts are left out (the
  first shown part carries "rule(s)"); "cannot tell" is always its own count, never folded into passed or failed. No
  rule with a result: "Nothing on these drawings that these rules check."
- The pack `note` verbatim on its own line (12px `--v-muted`): "A pre-check of a few rules, not a compliance
  certificate."
- A link "See the checks" → `#/p/<pid>/checks?pack=<id>` (fe-scaffold's ChecksScreen).
- States: loading "Checking against `name`…" (`role="status"`); 409 (reading not done): "The checks run when reading
  is done."; 404 with `code: "unknown-pack"` (distinct from the project's 404): "These rules are not available. Pick another
  country."; any other error:
  `errorText(err).detail` with Retry (re-fetches only the checks). All inside the row: the conflicts, the cards and the
  chat button never wait for or depend on the checks.
- Checks do not lock "Start a new chat" (only conflicts that need a person do).
- One request per (project, pack); a pack change from the header (a new `query`) re-fetches; no polling (the project
  is done by the time conflicts settle; "Check again" re-fetches both).

### Criteria (component tests; types and hand-made fixtures until Bogdan's PRs, then his fixtures)

- CF-29: `query` `d=<did>&q=area:room|name=1.01` scrolls that card into view, sets `aria-current="true"`, opens its
  evidence and focuses its title; an unknown `d`/`q` changes nothing and shows no error.
- CF-30: with `pack=fi` the screen sends `GET /api/projects/<pid>/checks?pack=fi` once. Fixture: two drawings, four
  rules: R1 pass on both drawings, R2 pass on one and fail on the other, R3 pass and cannot_tell, R4 no results →
  "1 rule passed · 1 failed · 1 cannot tell" (R2 failed beats its pass, R3 cannot tell beats its pass, R4 not counted),
  the note verbatim, and "See the checks" → `#/p/<pid>/checks?pack=fi`; without `pack` there is no checks request and
  no row.
- CF-30b: Bogdan's `project_checks.json` shows "1 rule failed"; with a second drawing where that rule, a new rule X
  and a passed rule Z are `cannot_tell` with no results and a rule Y is `not_applicable`: "1 rule failed · 2 cannot
  tell" (same data, same counts as the checks screen).
- CF-31: two rules whose results are all `cannot_tell` show "2 rules cannot tell" and no passed or failed pill; a
  rule with a `fail` and a `cannot_tell` result counts as failed only; rules with no results at all show "Nothing on
  these drawings that these rules check."
- CF-32: a 409 shows "The checks run when reading is done."; a 404 with `code: "unknown-pack"` shows "These rules are not available.
  Pick another country."; a 500 shows its detail and Retry (which re-sends only the checks GET); in each case the cards
  and "Start a new chat" still render.
- CF-33: with `pack=fi`, the chat button, the quiet workspace link and a card's surveyor link all carry `pack=fi`.
- CF-34 (`issueLinks.test.ts`): `conflict` → `#/p/<pid>/conflicts?d=<did>&q=<quantity encoded>`, plus `&pack=fi` when
  given; `refused_answer` → `#/p/<pid>/d/<did>/engineer?ask=<question encoded>` when `drawing_id` is set (engineer.md
  EN-72), else `#/p/<pid>/chat?ask=<question encoded>` (chat.md CH-14); `set_aside`, `reading_flag`,
  `code_check_failed`, `double_check` → null; a conflict with no `drawing_id` → `#/p/<pid>/conflicts`.

### Asks of others

- fe-shared: pass `query` to ConflictsScreen in `App.tsx`; export the rule-pack name lookup (`getRulePacks` or the
  header's loaded list) and `getProjectChecks(pid, pack)`.
- fe-ingest: use `issueRoute` for `conflict` / `refused_answer` rows (issues.md).
- fe-engineer: ProjectChat and the engineer read `?ask=` once on mount and ask it (chat.md CH-14, engineer.md
  EN-72; frontend-orch gen 4: asked on open, not left unsent in the box).
- Bogdan: all accepted (#142 c6876010899): per-drawing envelope with this project's `file`, `unknown-pack` 404 code,
  the 409 code named in the decision record (the row matches on status 409, so its exact name does not matter here),
  `quantity` = `Row.key` and `mark_id` on `Issue`, links = API paths.

## Demo parity (Tudor 2026-11-14 16:25, brief fe-demo-parity.md; demo PRs #206, #209, #211-#213, #216, #217)

Spec 2026-11-14 16:40, fe-surveyor; GO 17:00 (number-only typed answer, "Variant 1/2" on this card only, "settled by a rule", no checks row); built. Tudor: "make the full frontend look more like our demo,
all the changed we did to the demo should be done to the ui". The demo (`demo/vellum/app.js` `conflictsBlock`,
`style.css` `.conflict` … `.c-foot`) is the model for the look and behaviour; its data is not used.

### What changes, in short

- The conflicts are no longer a screen of their own: fe-shared's header has no Conflicts tab and `#/p/<pid>/conflicts`
  lands on Ingest. This file's job becomes **`ConflictsList`**, the conflicts block the finished ingest views embed
  (Simple: preqa-a's `ProjectScreen`; Advanced: fe-scaffold's). The page heading, the chat block and the checks row
  leave this file (below).
- Each card shows its **source drawing**, minimized, with each value's place outlined and numbered (fe-viewer's
  `SourceFigure`), and **"Show source"** (fe-viewer's `SourcePreview`). It replaces "Where each value was read".
- While choosing, **"Or type your own answer"** under the variants.
- **Order**: the conflicts a rule could settle first, then the ones that need a person.
- Tiles read "Variant 1", "Variant 2" (the demo's words), and the numbers match the outlines.

### `ConflictsList` (the seam with preqa-a and fe-scaffold)

`frontend/src/surveyor/ConflictsScreen.tsx` exports

```ts
export function ConflictsList(props: {
  projectId: string;
  query?: URLSearchParams;  // optional: the host route's query; `d` + `q` focus a card (CF-29), `pack` rides on links
  onCounts?: (counts: { total: number; needsPerson: number }) => void;
}): JSX.Element;
```

`onCounts` is preqa-a's ask (ingest.md): called with the list's counts after the first load and after every reload
(a settle, an unsettle, Retry), never before the first load; `needsPerson` = conflicts with `needs_person`. The host
locks "Start a new chat" on it and picks its own "Open the workspace" target.

- It loads `getProjectReview(pid)` itself (not `getProject`: the host has the project) and reloads it after every
  POST, as now. Loading: a "Loading the conflicts…" line (`role="status"`), not the shell's full-page `Loading`.
  An error: `errorText(err).detail` and Retry inside the block; the host page around it still works.
- It renders, inside `<section id="conflicts" aria-label="Conflicts">` (the id is fe-scaffold's scroll target,
  AV-38's "Show the conflict"; one list per page, so the id is unique): an h2 "`k` conflicts found" / "1 conflict found" / "No
  conflicts found" (demo `.list-h`: 20px, 600), the sub line (CF-2's words), the progress row (segments + "`s` of
  `k` settled", `role="status"`), then the cards. No conflicts: the h2, "Both methods agree wherever two of them
  measured.", no segments, no cards.
- Not in it: the project kicker and h1, "Still reading…" / "Check again", "Start a new chat" and "Open the
  workspace" (the host's, brief: preqa-a / fe-scaffold), the checks row (open point 4).
- `ConflictsScreen` (the route component) and its `App.tsx` wiring go once fe-shared redirects the route (fe-shared's
  change; until then `ConflictsScreen` renders the page heading + `ConflictsList` + the chat block, so nothing
  breaks mid-merge).

### Card order and numbering

Cards whose `conflict.resolution` is set (a rule could decide; settled by the rule or since by a person) first, then
the ones without (`needs_person`, or settled by a person after needing one), each group in the server's order (`ordered`). The
key does not change when a person settles a card, so a card does not jump on reload. "Conflict `i` of `n`" counts in
this order.

### The card, top to bottom (demo `.conflict`)

1. Head (as now): kicker "Conflict `i` of `n` · needs you / settled by a rule / settled by you", h2 `label`, mono
   `file`, the pill with its tooltip right (CF-21, CF-26).
2. **Source figure**: fe-viewer's `<SourceFigure sources label defaultOpen />` (viewer.md "Source figure and
   preview", props published 16:40), `label` "Source of conflict `i`". The drawing comes from `getDrawing(drawing_id,
   {project})`, once per drawing, fetched when the card mounts (CF-12). One `Source`: `name` = `file` (fe-shared's
   plain-name helper if it lands), `page` = the drawing's page of the first mark (else of the first value with a
   `page`, else page 1), and **the places from `conflict.value_marks`** (Bogdan #221, merged into the parity branch):
   for each value `i` in order, one `Place` per mark, `label` "Variant `i+1`: `methodName(mark.label)`" (a label that
   is a method id reads in words; any other label, e.g. an element name, as is), `box` = the mark's box when it is on
   that page, else null and the label adds ", on page `p`". A value with `[]` has no place; all `[]`: no outlines,
   the whole page (fe-viewer VW-86; brief rule 2: never invent a place). The legend's "Variant n" ties each outline
   to its tile (a count lists every element, so the figure's numbers are not the variant numbers). It starts minimized (`defaultOpen` false; true only for the card an issue link focuses, CF-29);
   the open state lives in SourceFigure and survives a reload after an edit because the card is keyed by its quantity
   (CF-25). While the drawing loads: the figure is not rendered yet, a "Loading the drawing…" line; an error: an
   error line with Retry in its place (CF-13), the card still works.
3. **"Show source"**: SourceFigure's own button opens fe-viewer's `SourcePreview` (file name, whole page, the same
   numbered outlines, Esc / backdrop / Close, focus to Close and back; fe-viewer's tests). One source per conflict,
   so no arrows.
4. **Variant tiles** (demo `.vars` / `.tile`): kicker "Variant `n`" + " · the rule's choice" on the rule's variant;
   value 22px 700 (`formatValue`); source line `methodName(method)` + ", page `p`". Accessible name "Variant `n`:
   `value`, `method`, page `p`[, the rule's choice][, in use]". Pressed / disabled / choosing as the States table.
5. **"Or type your own answer"** (demo `.c-own`), only while choosing (needs you, or after Modify): a label "Or type
   your own answer", a text input (`inputmode="decimal"`, 16px text at ≤600px so iOS does not zoom) with the unit
   after it as plain text ("m²", "m", "m³"; a count shows none: the entry has no noun), and a primary
   "Use my answer". Submit (button or Enter) reads a number (`,` or `.` as the decimal mark; a count must be a whole
   number ≥ 0; an area or length > 0); valid: `postReview(drawing_id, {quantity, action: "settle", value},
   {project})`, then the review reloads, as a tile does. Not a number: no request, the line "Type a number, like
   12.5." ("Type a whole number, like 12." for a count; `role="alert"`, `aria-describedby` on the input). The typed text is a number only: the API stores a value,
   not words (API ask 1).
6. **No suggestion chips.** The demo shows chips only when they add something the variants don't; the API offers no
   suggestions for a conflict, and chips made from the variants would repeat the tiles (Tudor removed those, #213).
   With an API `suggestions` list (API ask 2) they would sit between the label and the input (demo `.chips-row` /
   `.qchip`), each filling the input, not sending.
7. "Why …" (`details.why`, as now: the rule, `note`, `derived`).
8. Foot (demo `.c-foot`, as now) with the action line: a settled value that matches no tile reads "Your answer:
   `formatValue(settled.value)`." (replaces "You settled it at … in the surveyor workspace.": the value may come from
   this box or the workspace); the surveyor-workspace link stays.

"Where each value was read" (`<details>` + PageViewer) goes: the source figure replaces it. CF-12/13/29's "evidence"
means the source figure from here on (CF-29: the focused card's figure opens, i.e. expanded).

### Look (demo `style.css`, tokens only)

Card, tiles, why and foot already follow the same design (Layout above). Changes: the `.c-own` block (column, 8px
gap; input row flex 8px gap; input 15px, padding 10px 14px, 1px `--v-line` border, 12px radius, `--v-surface`; at
≤520px the row stacks and the button is full width, 44px), the h2 of the list 20px 600 with 4px/10px margins. The
figure, outlines, legend and preview are fe-viewer's. The demo's literal colours (`#fbf8ef`, `#f3f7f5`, `#d2d9d5`)
map to existing tokens or a token asked of fe-shared (asks below); none in conflicts.css (CF-20's spirit, SV-50).

### Plain words

- No "AI": the kicker says "settled by a rule" (D18, orch binding; open point 1 stays answered as "rule").
- Method ids only through `methodName` (no `polygon_x_scale` on screen); `label`, `rule`, `note`, `derived` are the
  server's sentences, shown verbatim (asks 3 for plainer ones).
- No credits on the card (brief rule 4): the source figure shows none (fe-viewer), the card passes none.

### Criteria (component tests; review fixtures from `@fixtures`, the viewer parts as props-recording doubles)

- CF-35: `ConflictsList` with `projectId` sends only `GET /api/projects/<pid>/review` (no project GET), renders the h2
  "1 conflict found", the sub line, "1 of 1 settled" and the card; `onCounts` is not called before the load, then
  with `{total: 1, needsPerson: 0}`; a needs-person fixture gives `{total: 1, needsPerson: 1}` and, after a tile's
  settle and reload, `{total: 1, needsPerson: 0}`. The section has `id="conflicts"`, in loading, error and done
  states alike (fe-scaffold can scroll to it before the review arrives).
- CF-36: a review error shows its detail and Retry inside the section (no full-page error); Retry re-sends the GET.
- CF-37: order: a review with [needs-person P, rule R1, settled-after-needing S (no resolution), rule R2] shows R1,
  R2, P, S, kickers "Conflict 1 of 4" … in that order; settling P and reloading keeps the order.
- CF-38: the card mounts `SourceFigure` once (props-recording double) with `label` "Source of conflict 1", no
  `defaultOpen`, and one source: `name` "plans/flat-b.pdf", the drawing's page 1, places from the fixture's
  `value_marks`: "Variant 1: <methodName(polygon_x_scale)>" and "Variant 2: <methodName(printed_label)>" with their
  boxes; a value listing two elements gives two places, one on another page has `box: null` and ", on page 2"; all
  `[]` gives no places; no `PageViewer` and no "Where each value was read" in the card.
- CF-39: a card focused by `d`/`q` (CF-29) passes `defaultOpen: true`; a reload after a settle does not remount the
  card's SourceFigure (same instance: its expanded state stays).
- CF-40: tiles read "Variant 1" / "Variant 2 · the rule's choice"; accessible names start "Variant 1:".
- CF-41: in choosing mode "Or type your own answer" shows with the unit; typing "25,5" + "Use my answer" sends exactly
  `{"quantity": "area:room|name=1.01", "action": "settle", "value": 25.5}` then reloads; "abc" sends nothing and
  shows "Type a number, like 12.5."; a count with "2.5" sends nothing; not choosing: no box.
- CF-42: no suggestion chips render on any card (fixture with any review).
- Built extras from preqa-b's sweep (preqa-parity.md "Conflict card"): the in-use tile shows the demo's 20px accent
  check dot in its top line ("in use" stays in its accessible name only); the chosen fill is half `--v-accent-soft` on
  `--v-surface` (`color-mix`, the demo's paler fill); tile value 22px, source 13px; "Why …" has the demo's chevron,
  14px, and a 44px summary (tap target at 390). Left as is: "Open in the surveyor workspace" in the foot (the demo
  has only Modify; the link is the way to mark edits).
- Re-sweep (preqa-parity.md "Re-sweep" item 5, orch 17:xx):
  - CF-46: the h2 is `label` in sentence case (first letter upper: "Area of room (name Küche · 1.01)"); a plain
    question title still waits for Bogdan (API ask 3).
  - CF-47: the foot has only the card's own buttons: Modify (the demo's `.btn-soft`: `--v-accent` on
    `--v-accent-soft`), "Use the rule's value" when a person's choice overrides a rule, Cancel while choosing. "Open
    in the surveyor workspace" is gone (the ingest page has "Open the workspace"); CF-18 and CF-33 retire, and the
    card no longer takes `projectId` or `pack`.
  - CF-48 (#224, orch): the card names its drawing by `drawingLabel` (shared.md "Plain drawing names": the backend's
    plain `name`, e.g. "Drawn plan 2", else the file name) on the line under the title (13px muted, no longer
    monospace) and as the source preview's name. The names come from one `GET /api/projects/<pid>` the list sends
    beside the review; if it fails, each card shows its file name and nothing else changes. Not done yet (after the
    freeze): the surveyor workspace's "Takeoff: `file`" heading and its side panel (they load no project).
- Bogdan #226 (main, merged into parity ~17:00; orch): the API asks 1-3 landed.
  - CF-49: the h2 is `ConflictEntry.title` (a plain question, "Area of room (name Küche · 1.01): 22.40 m² or 30.00
    m²?"); an entry without one (a backend before #226) falls back to CF-46's sentence-case label.
  - CF-50: "Why …" shows `ConflictEntry.why` (plain words, it already says "Settled by a rule (…)" or "No rule
    decides…") as one paragraph; without it, the rule sentences as before.
  - CF-51: suggestion chips (demo `.chips-row`/`.qchip`, 40px, 44px at ≤600px) between "Or type your own answer" and
    the box, only for `ConflictEntry.suggestions` whose number differs from every variant value (to 0.005; words
    always count as different): the server suggests one per value read ("13 doors"), which repeat the tiles, so
    usually none show (Tudor's rule). A chip fills the box and focuses it; it sends nothing.
  - CF-41 (changed): the box takes words too (no number pad, up to 280 characters): a number (`,` or `.`, a unit
    like "m²" after it allowed) settles as `value`; anything else goes as `{action: "settle", note}` (the value in use
    stays and the conflict is settled); empty: "Type a number or a few words."; an area of 0: "Type a number above 0,
    or a few words."; a count that is not whole: "Type a whole number, like 12.". A settled entry with `settled.note`
    reads "You answered: “note”." API ask 1-3 are done; ask 4 (places per count element) is #221's `value_marks`.
  - CF-26 (changed): at ≤600px `.cf-card-top` is a `column` with the pill after the title block (demo `.c-head`),
    not above it.
- Bogdan #221 (merged into the parity branch 17:xx): `conflict.value_marks[i]` = `[{page, box, label}]` per value
  replaces the single `box` per value as the source of the places (card point 2, CF-38).
- CF-43: a settled value no tile has reads "Your answer: 25.50 m²."
- CF-44: `issueRoute` for a `conflict` issue → `#/p/<pid>?d=<did>&q=<quantity>[&pack=]` (the finished ingest page
  that embeds the list); with no `drawing_id` or `quantity` → `#/p/<pid>` (replaces CF-34's conflicts route).
- Retired or moved: CF-1 (now CF-35), CF-2's kicker and h1, CF-15/16 (the host's), CF-17/27(chat)/28 (the host's chat
  block: preqa-a / fe-scaffold take the words and the lock, from `onCounts`), CF-19 (the link goes to `#/p/<pid>`),
  CF-30..33 (checks row, open point 4); the CF-17 workspace target (the host's: ingest.md); CF-22 e2e: fe-golden rewrites it on the ingest page. CF-25 now covers the
  figure's expanded state instead of the evidence details.

### API asks (Bogdan, through frontend-orch on #14)

1. **A note with a settle** (`Edit.note?: string`, ≤140 chars, kept on `Settled` as `note`): the demo's typed answer
   is words ("3 bedrooms, room 1.02 is the living room"); the API keeps a number. Until then the box takes a number
   only (no client-side words: they would vanish on reload and not reach the takeoff).
2. **`ConflictEntry.suggestions?: string[]`** (or values), answers that are neither variant (e.g. "both doors are
   one"): until then no chips.
3. **Plain words per conflict**: `ConflictEntry.title` (a question, "Doors on this floor: 11 or 13?") and `why`
   (one or two sentences, "2 doors are drawn twice in the CAD file, one copy exactly on top of the other"). Asked
   before (Not in the API 4); the demo's cards lean on them. Until then: `label` and the rule sentences.
4. **The places in question for a count conflict** (`ConflictValue.boxes?: [box, page][]`, or mark ids per value):
   the doors drawn twice are not located today (one `box` per value at most), so a door count conflict shows the
   drawing without outlines.

### Asks of the other frontend workers

- fe-scaffold: scroll to `#conflicts` (the section's id, CF-35), no prop needed.
- fe-viewer: none; I code against the published `SourceFigure` props as they are (places in order give my variant
  numbers; `defaultOpen` for the focused card; the open state survives because I keep the card mounted).
- preqa-a (fe-scaffold through preqa-a's finished block): `<ConflictsList projectId onCounts />` as ingest.md asks
  (agreed, no change for them); please also pass `query={route.query}` so an issue link's `d`/`q` focuses its card
  (CF-29, optional prop).
- fe-shared: route `#/p/<pid>/conflicts` → the project route keeping the query; remove `ConflictsScreen` from
  `App.tsx` when the redirect lands; tokens for the demo's figure background `#fbf8ef` (fe-viewer's) and the chosen
  tile's `#f3f7f5` if `--v-accent-soft` is not close enough (I use `--v-accent-soft` unless fe-shared says otherwise).
- fe-ingest: documents.md leaves `conflict` issues out, so `issueRoute`'s conflict target (CF-44) matters only to
  the old issues screen while it lives; the refused-answer routes are unchanged.

### Open points

1. Typed answer: number only (my recommendation, honest and saved) vs the demo's free words (needs API ask 1).
2. "Variant 1/2" replaces the letters A/B on this card only; the surveyor workspace's Keep buttons and PageViewer tags
   keep A/B. OK, or keep A/B here too (then the outline numbers and the tiles differ)?
3. The kicker: "settled by a rule" (D18) vs the demo's "solved by the AI". I keep "rule".
4. The checks row (`?pack=`, CF-30..33) has no place in the demo's finished ingest; `ChecksRow` stays exported for a
   host that wants it. Drop it, or put it above the list on the ingest page?

## Resolver picks (#252, resolver.md RS-10..15)

The criteria are in `resolver.md`; this is how the card and list build them. Helpers `resolverName`, `resolverModel`,
`pickInUse` come from `src/api/format.ts` (fe-shared).

- `cardState` has a fourth state `picked` (`pickInUse(c)`), checked after `settled` and before `rule`. Pill
  "Picked by Carbon" (`cf-accent`), kicker "picked by Carbon", action line "You can change it." beside Modify.
- The model's line `p.cf-resolved`: "**Picked by Carbon** <reason>" (picked state) or "**Carbon could not tell**
  <reason>" (`cannot_tell` on an open card); the bold name carries `title` = the model id. Hidden once a person
  settled or signed (the model's answer is no longer what is in use).
- Places: after the `value_marks` places, a pick in use adds one place per `resolved.marks` entry, label
  "Picked by Carbon: <mark label>", same page rule (another page → legend only, ", on page p").
- A person's choice over a pick (no rule resolution): the second button reads "Use Carbon's pick" and sends
  `unsettle` (the server brings the pick back), like "Use the rule's value".
- `whyText(c)`: with `resolved` set, the server's `why` up to and including "No rule decides between them." (the
  rest names the model id); missing sentence → the rule-sentence list.
- `subLine`: "N picked by Carbon, check them." after the rule count; `progressText` counts a pick as settled.
- Takeoff table (surveyor workspace): a row with a pick in use reads "Picked by Carbon" (`data-status="picked"`,
  neutral look, `title` = model id) instead of `statusText`.

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

- ~~Typing a value that is neither variant~~: in scope since demo parity (CF-41, a number).
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
