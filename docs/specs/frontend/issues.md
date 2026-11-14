# Issues: every place that needs a look, located (spec, #140)

Status: draft for review, 2026-11-14, by fe-ingest. Brief: `.agents/briefs/fe-checks-issues.md` (incl. CHANGE 13:22).
Contract: board decision #142 (Bogdan, 12:30) and its export answer (c6875986462, 12:34); record
`docs/decisions/0008-located-issues.md` on Bogdan's branch (not pushed when this was written). Bogdan accepted all
our #142 asks (c6876010899, via frontend-orch 13:44): `Issue.polygon` (optional), `mark_id` and `quantity`, full sort
order (severity, drawing in project order, page, box top), 404 code `unknown-pack`, the 409 code named in 0008,
`file` = this project's path, `links` = API paths. Field names below follow that; check them against 0008 when it
lands.

## Purpose

After ingest, one screen lists every place in the project that needs a person: conflicts between methods, refused
answers, files set aside, reading flags, and (when a country is chosen) failed building-code checks. Each row says
why in one sentence, where (file, floor, page), and whether it is open, settled or signed off. Selecting a row shows
the drawing with that place outlined (jump-to-place). One "Export" button downloads the issues with the floor plans
marked; the CSV alone stays as a second link. Row numbers match the export.

## Files owned

All under `frontend/src/issues/` (new folder); each file with logic has a test beside it.

| File | What |
| --- | --- |
| `IssuesScreen.tsx` | `export function IssuesScreen(props: { projectId: string; pack?: string | null }): JSX.Element`, the route component for `#/p/<pid>/issues` (route, `?pack=` and `App.tsx` wiring: fe-shared). Loads the issues, holds the filters and the selected issue, lays out list and plan. |
| `IssueList.tsx` | the list: severity groups, rows (number, kind, why, place, state, links) |
| `IssuePlan.tsx` | the selected issue's drawing: `getDrawing(drawing_id)` once per drawing, `PageViewer` with the drawing's located issues as numbered marks and `focus` on the selected one |
| `issues.ts` | pure: `numbered` (n per issue), `filterIssues`, `counts`, `KIND_LABEL`, `SEVERITY_LABEL`, `STATE_LABEL`, `placeOf`, `issueMarks`, `routeOf` |
| `types.ts` | the #142 shapes typed locally (`Issue`, `IssueList`) until Bogdan's PR lands; then deleted for `schema.d.ts` |
| `testing.ts` | hand-made fixtures in the #142 shapes (one issue per kind, located and not); replaced by his fixtures when the PR lands |
| `issues.css` | layout, `--v-*` tokens and the shared `.v-*` classes only |

Uses, does not own: `src/api` (`getIssues`, `issuesCsvUrl`, `issuesZipUrl`, `getDrawing`, `errorText`: fe-shared,
shared.md), `src/shell` (`Loading`, `ErrorView`, the country picker and `?pack=`), `src/viewer/PageViewer.tsx`
(fe-viewer: its `focus?: {page, box}` prop, viewer.md), `src/ingest/ingest.ts` (`plural`, `kindLabel`).
[e2e] criteria are built by fe-golden.

## User flow

1. The user opens Issues from the header tab (any project route) or from the project screen's link when the project
   is done. The URL is `#/p/<pid>/issues`, plus `?pack=<id>` when a country is chosen in the header.
2. The screen shows the title "Issues", a summary ("5 open · 2 settled · 1 signed off"), the pack line when a pack is
   chosen (the pack's `note` verbatim: "A pre-check of a few rules, not a compliance certificate."), else "Choose a
   country in the header to add building-code checks.", the filters (Kind, State), the "Export" button and the
   "CSV only" link.
3. Then the list, in the API's order, under severity headings: "Fails a rule", "Needs a person", "Note". Each row
   starts with its number `n` (1-based position in the unfiltered API list, the same `n` as the export's CSV column and
   the labels on its PNGs), then the kind (icon + word), the `why`, the place ("plans/flat-b.pdf · floor 1 · page 1"),
   the state, and its links.
4. Selecting a row (click, Enter or Space) selects it (`aria-current="true"`) and shows its drawing on the right
   (desktop) or above the list (phone, scrolled into view): the page of the issue, every located issue of that page as
   a numbered outline, the selected one focused (zoomed and scrolled to its box). On load the first located issue is
   selected.
5. A row without a place (no `drawing_id`, or no `page`) says so in words ("not on a drawing", "the whole drawing")
   and selecting it shows no outline: the plan panel says "This issue has no place on a drawing." (no `drawing_id`) or
   shows the drawing without a focus (IFC: `page` null).
6. Row links go to the screens that settle the issue: conflict → "Settle" (when `state` is `settled` or `signed_off`:
   "See the conflict", same route: nothing is left to settle) `issueRoute(issue, pid, pack)` from
   `src/surveyor/issueLinks.ts` (fe-surveyor, CF-34: `#/p/<pid>/conflicts?d=<did>&q=<quantity>`); refused_answer →
   "Ask again" `#/p/<pid>/d/<drawing_id>/engineer?ask=<question>` (engineer.md EN-72), or `#/p/<pid>/chat?ask=<question>`
   when `drawing_id` is null (chat.md CH-14), also through `issueRoute`; every located issue (`drawing_id` and `page` set)
   also → "Open the drawing" `#/p/<pid>/d/<drawing_id>/engineer?page=<page>&box=<x0,y0,x1,y1>` (engineer.md EN-76, `box`
   left out when null); set_aside → "Why it was set aside" `#/p/<pid>/f/<file_id>`; reading_flag and
   code_check_failed → "Open in the surveyor" `#/p/<pid>/d/<drawing_id>/surveyor` (plus `?q=<quantity>` when the issue
   has a `quantity`); code_check_failed also → "See the check" `#/p/<pid>/checks?pack=<pack>`. Every link keeps
   `?pack=` (fe-shared's rule for project routes).
7. "Export" downloads `issues.zip` (CSV + one PNG per drawing page with the issues drawn and numbered); "CSV only"
   downloads `issues.csv`. Both carry `?pack=` when chosen.
8. Changing the country in the header reloads the list (the pack is part of the request); the filters reset.

## API calls

**`GET /api/projects/{pid}/issues?pack=<id>`** (`getIssues(projectId, {pack})`, fe-shared). On mount, and again when
`pack` changes (the screen is keyed by path without query, so it is not remounted: the load depends on `pack`). No
polling: issues exist only once the project is done (409 before), and edits elsewhere are seen on the next visit.
Response `{project_id, pack, issues: Issue[]}`; fields used:

- `id`: list key and selection (stable across calls, #142).
- `kind`: `KIND_LABEL` word + icon: conflict "Conflict" (⇄), refused_answer "Refused answer" (?), set_aside "Set
  aside" (–), reading_flag "Reading flag" (!), code_check_failed "Fails a code rule" (✕), double_check "Double-check"
  (◎). A kind not in the table shows its raw id and no icon (additive kinds stay safe).
- `severity`: the group heading (`SEVERITY_LABEL`: fails_rule "Fails a rule", needs_person "Needs a person", note
  "Note"). The API's order is kept (severity, then drawing in project order, page, box top: c6876010899); the screen
  never re-sorts, so `n` matches the export and the list does not reshuffle.
- `state`: `STATE_LABEL` word + icon: open "open" (●), settled "settled" (✓), signed_off "signed off" (✓✓).
- `why`: the row's main text, verbatim (text, never HTML).
- `file`, `floor`, `page`: the place line `placeOf`: `file`, then "floor <floor>" when set (else "floor not
  stated"), then "page <page>" when set (else "the whole drawing" when `drawing_id` is set, else "not on a drawing").
- `drawing_id`, `page`, `box`, `polygon` (page fractions, 1-based page; `polygon` optional): the plan panel and the
  focus. The outline is the polygon when set, else the box.
- `mark_id` (the takeoff's `MarkView.id`, null when none): not needed for the outline (the screen draws the issue
  itself); kept for a later "select the takeoff mark" in the surveyor link.
- `quantity` (the takeoff `Row.key`), `question`, `reason`: `quantity` for the surveyor `?q=`; `question` shown under the why for
  refused_answer ("Asked: <question>"); `reason` shown under the why when it differs from `why`.
- `file`: this project's path (c6876010899). `file_id`: the trace link (`#/p/<pid>/f/<file_id>`, `f\d+`; nullable since #147, then no trace link).
- `check`: `<pack>:<CheckResult.id>` (0008), not shown: `why` already carries the clause ref, and "See the check" is
  the way to the clause.
- `links`: not used (API paths, confirmed); the screen builds its routes from `drawing_id`, `file_id`, `quantity`.

Errors: 404 with code `unknown-pack` → "These country rules are not available." with a link to
the same screen without `?pack=`; 404 project → `ErrorView` ("Back to workspaces"); 409 (not done; the code named in 0008) → "The issues
are listed once the ingest is done." with a link to `#/p/<pid>` and Retry; any other → `ErrorView` with Retry.

**`GET /api/drawings/{drawing_id}`** (`getDrawing`). Once per drawing the plan panel shows (cached in the screen for
the visit). Reads `file`, `pages`, `credit` for `PageViewer`. A failure shows "Drawing not available" in the panel;
the list stays.

**`GET /api/projects/{pid}/issues.zip?pack=<id>`** (`issuesZipUrl(projectId, pack)`, fe-shared; Bogdan c6875986462).
The "Export" button is an `<a href download>` (no fetch). The zip holds `issues.csv` (first column `n` = the issue's
number in list order) and one PNG per drawing page with located issues, each box/polygon drawn and labelled with its
`n`; failed code checks included with `?pack=`; PNG names `<file stem>-p<page>.png`. Shown only after the list loaded
(a 409 would download an error body, review item 16). Until the endpoint is merged the button is there with
`data-pending="issues.zip"` (CHANGE 13:22); the attribute goes when the PR lands.

**`GET /api/projects/{pid}/issues.csv?pack=<id>`** (`issuesCsvUrl(projectId, pack)`). The "CSV only" link, same rules.

### The marks for the plan (`issueMarks`)

`PageViewer` takes `MarkView`s. The plan's marks are the located issues of the shown drawing (`drawing_id` equal,
`box` set), one each: `{id: issue.id, n, page, box, polygon: issue.polygon ?? null, label: KIND_LABEL word, state: "counted",
value: null, reason: null, ref: null, room_type: null}` (`reason` stays null: the viewer words a mark's reason as
"the rule left it out", which an issue is not; the why is on the row; field set of `MarkView` in `schema.d.ts`; the issue's data
only, nothing invented). `selected` = the selected issue's id, `focus` = `{page, box}` of the selected issue
(viewer.md `focus?: {page, box?} | null`: opens the page, zooms and scrolls to the box, outlines it; page only when
`box` is null), `unit` null (badges show `n`), `tones` = `issueTones(rows, drawingId)`: each mark's severity as a
viewer tone (`fails_rule` → `fail`, `needs_person`, `note`), so the badge reads "Mark 1: Fails a code rule, fails the
rule" in the severity's colour and the legend counts severities, not "counted" (viewer.md tones; fe-viewer, fe-golden
finding). Clicking a mark selects its row (`onSelect`) and scrolls the row into view.

## States

| State | Screen | Reach it on purpose |
| --- | --- | --- |
| Loading | "Loading issues…" | pending promise |
| Not done | "The issues are listed once the ingest is done." + link to the project + Retry | `mockApi` 409 `error.json` with `code` `not-allowed` |
| Empty | "No issues: nothing needs a look." (with a pack: "No issues: nothing needs a look, and no rule failed.") | `issues: []` |
| Filtered empty | "No issue matches these filters." + "Show all" | filters that match nothing |
| No pack | the line "Choose a country in the header to add building-code checks."; no code_check_failed rows (the API sends none) | `pack` null |
| Pack | the pack `note` verbatim under the title | `pack: "fi"` |
| Unknown pack | "These country rules are not available." + link without `?pack=` | 404 with `code: "unknown-pack"` |
| Error | `ErrorView` with Retry | 500, network |
| Not located | the row's place reads "not on a drawing" / "the whole drawing"; the plan panel says so | issue with `drawing_id` null / `page` null |
| Drawing fails | plan panel "Drawing not available"; list unchanged | `getDrawing` 500 |
| Phone 390 | one column: toolbar, plan panel, list; no horizontal scroll | viewport 390x844 |

## Layout

`.v-page--wide` (1280 px). Title row: `h1` "Issues" (`.v-title`) and the summary (`.v-caption`); right: "Export"
(`.v-btn`) and "CSV only" (a text link). Under it the pack line (`.v-caption`, the note verbatim, or the "Choose a
country" line), then the filters: two `<select>`s labelled "Kind" and "State" ("All" + each value present, with its
count: "Conflict (2)").

Desktop (>1100 px): two columns, list `minmax(0, 1fr)` and plan `minmax(0, 1fr)`; the plan panel is a `.v-card`,
`position: sticky; top: var(--v-header-h)`, `max-height: calc(100vh - var(--v-header-h))`, its own scroll. The list:
severity headings (`.v-h3`), rows as one `.v-card` list with hairlines (`--v-line`): the number in a 28 px circle
(`--v-accent-soft`, the same look as the PNG labels), the kind pill (`.v-pill`, tone by severity: fails_rule
`--danger`, needs_person `--warn`, note plain), the why (15 px), the place (13 px muted), the state word right,
links under the why. The selected row: `--v-accent-soft` background and a 2 px accent inset bar (as the surveyor's
current row). Rows are `<button>`s inside `li` (the links sit beside the button, not inside it).

Phone (≤760 px): one column; the plan panel under the filters, not sticky; selecting a row scrolls the panel into
view. Tap targets ≥ 44 px; long file names and whys wrap (`overflow-wrap: anywhere`).

Status is never colour alone: kind, severity and state each carry a word (and an icon where listed).

## Acceptance criteria

- IS-1: `IssuesScreen` requests `GET /api/projects/<pid>/issues` (with `?pack=<id>` when `pack` is set, none when not)
  and shows "Loading issues…" until it answers. [component]
- IS-2: Each issue is a row in the API's order with `n` = its 1-based position in the response, its kind word, `why`,
  place line and state word; rows sit under the severity heading of their `severity`; the screen does not re-sort (a
  fixture whose order differs from any local sort keeps the API order). [component]
- IS-3: `placeOf` gives "plans/flat-b.pdf · floor 1 · page 1"; "… · floor not stated · page 2" with `floor` null;
  "… · the whole drawing" with `page` null and a drawing; "… · not on a drawing" with `drawing_id` null. [unit]
- IS-4: The summary counts by state ("3 open · 1 settled · 1 signed off", `plural` rules, zero states left out).
  [unit `counts` + component]
- IS-5: Filters Kind and State list "All" and each value present with its count; choosing one shows only matching
  rows, which keep their original `n`; no match shows "No issue matches these filters." with "Show all", which resets
  both. [component]
- IS-6: With `pack` set the pack `note` from the response's pack (`useInfo().info.rule_packs`) shows verbatim; with
  none the line "Choose a country in the header to add building-code checks." shows. [component]
- IS-7: On load the first located issue is selected (`aria-current="true"`) and `PageViewer` gets that drawing's
  `pages`, the drawing's located issues as marks (`issueMarks`: id, `n`, page, box from the issue), `selected` = its
  id and `focus` = its `{page, box}`; selecting another row of another drawing loads that drawing once (one `GET
  /api/drawings/<id>` per drawing per visit). [component, `PageViewer` mocked]
- IS-8: `issueMarks` returns only issues of the given drawing that have a `box`, each with the fields of "The marks
  for the plan" (the issue's `polygon` when set, else null) and nothing else invented (value, reason and ref null). [unit] `issueTones` maps those marks to `{i-check: "fail", i-conflict: "needs_person"}`.
- IS-9: A row with `drawing_id` null selected: the plan panel reads "This issue has no place on a drawing." and no
  drawing is requested. A row with `page` null shows the drawing with no `focus`. [component]
- IS-10: Clicking a mark in the plan (`onSelect(id)`) selects that issue's row and scrolls it into view. [component]
- IS-11: Row links per kind: conflict "Settle" ("See the conflict" when settled or signed off) and refused_answer
  "Ask again" (in every state: its route asks on open, EN-72/CH-14, so a neutral word would hide that) are
  `issueRoute(issue, pid, pack)`
  (conflict → `#/p/<pid>/conflicts?d=<did>&q=<quantity>`; refused_answer → `…/d/<did>/engineer?ask=<question>`, or
  `#/p/<pid>/chat?ask=<question>` with `drawing_id` null); a located issue has "Open the drawing" →
  `#/p/<pid>/d/<did>/engineer?page=<page>&box=<x0,y0,x1,y1>`; set_aside "Why it was set aside" → `#/p/<pid>/f/<file_id>`; reading_flag and code_check_failed
  "Open in the surveyor" → `#/p/<pid>/d/<drawing_id>/surveyor?q=<quantity>` (no `?q=` without a quantity);
  code_check_failed "See the check" → `#/p/<pid>/checks?pack=<pack>`; with a pack every link keeps `pack=<id>`.
  [unit `routeOf` + component]
- IS-12: "Export" is a link with `download` to `/api/projects/<pid>/issues.zip` (`?pack=<id>` when set) and
  `data-pending="issues.zip"` until Bogdan's PR lands; "CSV only" links to `/api/projects/<pid>/issues.csv` (same
  query). Neither shows before the list loaded. [component]
- IS-13: A 409 shows "The issues are listed once the ingest is done.", a link to `#/p/<pid>` and Retry, which
  requests again; a 404 `unknown-pack` shows "These country rules are not available." with a link to
  `#/p/<pid>/issues` (no pack); a 404 project shows `ErrorView`. [component, `error.json` variants]
- IS-14: `issues: []` shows "No issues: nothing needs a look." (the pack variant with a pack). [component]
- IS-15: An unknown `kind` shows its raw id as the kind word, no icon, and the row works. A refused_answer row shows
  "Asked: <question>".
  [component]
- IS-16: Strings from the API (`why`, `file`, `floor`, `question`, `reason`) render as text: `<img
  src=x onerror=alert(1)>` adds no element. [component]
- IS-17: No status by colour alone: every row's kind, severity heading and state contain their word. [component]
- IS-18: `issues.css` has no colour literal; the plan panel's sticky `top` is `var(--v-header-h)`. [unit: read the
  file]
- IS-19: At 1440x900 and 390x844 the issues screen of the sample project (done, no pack and `?pack=fi`) has no
  horizontal scroll, the first issue is outlined on its page, and a screenshot of each is saved. [e2e]
- IS-20: Every row's tap target is at least 44 px tall at 390. [e2e]
- IS-21 (QA R5-c-1): a change of `pack` loads afresh: while the new list loads the screen shows "Loading issues…",
  and a failed load (404 `unknown-pack`) shows the IS-13 card with no old rows and no Export, the same as a fresh
  load of that URL. The filters reset with it. [component]

## Out of scope

- Settling or signing off from this screen: the links go to the screens that do it (conflicts, surveyor, chat).
- Re-sorting or grouping other than by the API's severity order (it would break `n` against the export).
- Polling; a live count in the header (`ProjectSummary.issues_open`, accepted: the project list and header owners show it).
- Showing failed checks' full rule detail: the Checks screen (checks.md, fe-scaffold) owns it.
- A free page + box link from other screens (`?page=&box=`): jump-to-place happens inside this screen.

## Not in the API

All #142 asks were accepted (c6876010899); `Issue` and `IssueList` are `schema.d.ts` types since #147 (the screen's
test fixtures in `src/issues/testing.ts` are typed by them).

| Need | Field | Until it lands |
| --- | --- | --- |
| The export bundle | `issues.zip` (c6875986462, same PR) | button with `data-pending="issues.zip"` |

## Open points

1. **Jump-to-place inside the screen.** Resolved (frontend-orch, gen 4): both. The screen shows the place itself
   (IS-7) and each located row also links "Open the drawing" to the engineer's `?page=&box=` (EN-76). Original note: The brief says "opens the drawing at page + box (engineer route or the
   issue's links.*)". The engineer and surveyor routes have no page + box focus today (screens review item 17), and
   adding `?page=&box=` there touches two other owners. Recommend: the issues screen shows the drawing itself with
   fe-viewer's new `focus` prop (IS-7), and its row links open the settling screens. Changing that later only adds a
   link.
2. **`n` = list position.** Bogdan's export numbers issues "in list order"; the screen numbers the same way from the
   unfiltered response. If the API ever filters server-side (e.g. `?kind=`), `n` would shift: we filter client-side
   only.
3. **Order.** The brief says "ordered by severity then state"; Bogdan's order is severity, drawing (project order),
   page, box top (c6876010899). The screen keeps the API's order so `n` matches the export; open and settled issues
   of one place stay together. If state should come second, that is a backend change.
4. **Pack note source.** The note comes from `info.rule_packs` (fe-shared's picker), not from the issues response
   (it has `pack` only). Fine unless 0008 adds `note` to the response.
5. **Refused answers link to the chat.** Resolved: `?ask=` exists on the engineer (EN-72) and the chat (CH-14);
   "Ask again" asks on open. Original note: `#/p/<pid>/chat` opens the project chat empty; prefilling the question needs
   chat support for `?q=` (chat.md owner). Until then "Ask again" opens the chat only.
