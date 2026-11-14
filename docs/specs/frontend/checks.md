# Building-code pre-check: the Checks screen (spec, #139)

Status: spec for review, 2026-11-14, by fe-scaffold (brief `.agents/briefs/fe-checks-issues.md`, Tudor 13:18 "Build
both"). Backend contract: board decision #142 (record `docs/decisions/0009-building-code-checks.md`, Bogdan's PR,
not merged); shapes may still change while it is open. Our review of the shapes: `.agents/review-142-screens.md`,
posted to #142; Bogdan accepted all asks (#142 c6876010899, relayed 13:44). No design board exists for this screen: it uses the Vellum look (shared.md tokens, the panel and
stat styles of the conflicts and Advanced screens).

## Purpose

A person who picked a country in the header sees, for the whole project, which of that country's few building rules
the drawings pass, fail, or cannot be told, and for every failed or cannot-tell place: what was measured, the limit,
why, the clause it comes from, and where on the drawing it is. It is a pre-check, never a certificate: the pack's
note says so verbatim at the top, and nothing on the screen guesses a value.

## Files owned

All new, under `frontend/src/checks/`; each file with logic has a test beside it.

| File | What |
| --- | --- |
| `ChecksScreen.tsx` | `export function ChecksScreen(props: { projectId: string; pack: string | null }): JSX.Element`, the route component for `#/p/<pid>/checks?pack=<id>` (route, header tab and `App.tsx` wiring: fe-shared). Loads, holds the selected drawing and result, renders summary, results and viewer. |
| `checks.ts` | pure: `ruleSummary`, `resultStatus` words, `drawingResults` (failed + cannot tell, ordered), `fileName`, `valueText`, `checkStatusOf` (derived status), `viewerMarks` (a result's marks as `MarkView[]` + `tones`, viewer.md "Check marks as viewer marks") |
| `types.ts` | the #142 shapes typed locally (`RulePack`, `Rule`, `Clause`, `DrawingChecks`, `RuleCheck`, `CheckResult`, `CheckMark`, `ProjectChecks`) until Bogdan's PR lands; then they become aliases of `schema.d.ts` and this file shrinks to re-exports |
| `testing.ts` | hand-made fixtures in the #142 shapes (synthetic rooms and doors, no partner data, no design mock values); replaced by Bogdan's fixtures when they land |
| `checks.css` | layout, `--v-*` tokens only |
| `ChecksScreen.test.tsx`, `checks.test.ts` | the criteria below |

Uses, does not own: `src/api` (fe-shared: `getProjectChecks`, `getRulePacks` or `useInfo().info.rule_packs`,
`getProject`, `getDrawing`, `formatValue`, `ApiError`), `src/shell` (`Loading`, `ErrorView`, `routeHref`, the
country picker that sets `?pack=`), `src/viewer/PageViewer.tsx` (fe-viewer's `tones` and `focus`, VW-71..79).

## API calls

| When | Call (#142) | Used for |
| --- | --- | --- |
| mount, and when `projectId` changes | `getProject(pid)` | `state` (checks need a finished ingest), `drawings[]` order, `files[]` for names |
| mount, and when `pack` changes, once the project is `done` or `failed` | `getProjectChecks(pid, pack)` → `GET /api/projects/{pid}/checks?pack=<id>` | every drawing's `rules[]` with `results[]` |
| from the shell's info | `GET /api/info` `rule_packs[]` | the pack's `name`, `country_name`, `law`, `note` (verbatim) and the rule order |
| first time a drawing is shown in the viewer | `getDrawing(did)` | `pages[]` for `PageViewer` |

No per-drawing `GET /api/drawings/{did}/checks` call: the project call carries every drawing. A new `?pack=` aborts
the old request. No polling: the screen asks once the project is finished (see States).

## Field map

- Header line: "Pre-check: `<pack.name>`" and "`<pack.country_name>` · `<pack.law>`" (`country` is the ISO code
  "FI", for the picker's flag only); directly under it **`note` verbatim** (from the checks
  response, else from the pack): "A pre-check of a few rules, not a compliance certificate." Never shortened,
  restyled into a tooltip or hidden at 390 px.
- **Summary** (one row per rule, in the pack's `rules[]` order; rules the response has but the pack lists not, after
  it in response order): `rule.title`, the clause ref (`clause.ref`), and three counts over all drawings:
  **passed** / **failed** / **cannot tell** = results with that `status`. A rule with no result anywhere reads
  "Nothing in these drawings it applies to". A summary line above the table counts RULES, as the conflicts screen's
  checks row does (conflicts.md CF-29..31, orch D141): a rule failed if any result fails, else cannot tell if any
  result cannot tell, else passed (a rule with no result is not counted): "`<f>` rules failed, `<c>` cannot tell,
  `<p>` passed, over `<n>` drawings" (`plural` rules). The table's three numbers stay counts of places (results).
- **Per drawing** (in `project.drawings` order, drawings with no failed or cannot-tell result folded into one line
  "`<k>` drawings pass every checked place"): heading = this project's file name (`fileName(project, drawing_id)`:
  `project.files` by `drawing_id`, else `project.drawings[].file`; never a name from the checks payload, see
  "Asked"), then its **failed** results, then its **cannot tell** results, each in `RuleCheck` order then result
  order. Each result card:
  - status word with an icon: "✕ Fails", "? Cannot tell" (its own look, `--v-warn-soft`; never the pass or fail
    look), passed results are not listed (counted only);
  - `subject.label` (or "`<subject.kind>` `<subject.ref>`" when there is no label) and the rule title;
  - **value vs limit**: "`valueText(value, unit)` measured, limit `<rule.comparison_text>` `valueText(limit, unit)`"
    ("0.75 m measured, limit at least 0.80 m"; `op` is never shown); a null
    `value` reads "not measured", never 0 and never the limit;
  - `why` (one plain sentence, as sent);
  - the clause: `clause.ref`, `clause.quote` in a blockquote, `clause.quote_en` under it when present and different,
    and "Read the clause" linking `clause.url` (`target="_blank"`, `rel="noopener noreferrer"`, the link text says
    it opens the source);
  - "Show on the drawing" (button): selects the result; the viewer opens its drawing at the first mark's page.
- **Viewer** (beside the list at ≥ 1024 px, under it below): `PageViewer` with the selected drawing's `pages` and
  `credit` (`getDrawing`), `marks` + `tones` = `viewerMarks(result)` as viewer.md "Check marks as viewer marks" says
  (id = `CheckResult.mark_id`, the takeoff `MarkView.id` of the result's first subject mark, else
  `<result.id>:<index>`; subject marks numbered
  `n` with tone = the result's status, counted marks tone `counted`), `unit` = the result's unit, and
  `focus = {page, box}` of the first subject mark (VW-76/77). A result with no marks says "Not located on the
  drawing" instead of the button.
- Links out: per result "Open in the surveyor" → `#/p/<pid>/d/<did>/surveyor?q=<quantity>&pack=<id>` (the
  takeoff row, `CheckResult.quantity`; without `q` when null); per drawing heading the same without `q`;
  "Export issues and plans" → `#/p/<pid>/issues?pack=<id>` (the export itself is fe-ingest's issues screen, CHANGE
  13:22).

## States

| State | What shows | Reach it on purpose |
| --- | --- | --- |
| No pack (`pack` null) | "Choose a country in the header to run its pre-check." No request. | `#/p/<pid>/checks` |
| Project loading | `Loading` "Loading the checks…" | pending `getProject` |
| Project not finished (`queued`/`running`) | "The pre-check runs once the drawings are read." + project state word; no checks request | `project_running.json` |
| Checks loading | `Loading` | pending `getProjectChecks` |
| 409 from checks | same text as "not finished" (the backend says not yet) | `reply(409, …)` |
| Unknown pack (404 `unknown-pack`) | "These rules are not available. Pick another country in the header." | `reply(404, …)` on checks |
| Unknown project (404 on `getProject`) | `ErrorView` (not found) | `reply(404, …)` on project |
| Other error | `ErrorView` with Retry (re-requests checks only) | `reply(500, …)` |
| No drawings | note verbatim + "No drawing in this project to check." | `project` with `drawings: []` |
| All pass | note verbatim + summary + "Every checked place passes these rules." | fixture with only `pass` |
| Drawing pages fail to load | the result list stays; the viewer says "Page not available" with Retry | `getDrawing` rejects |
| 390 px | summary table becomes one card per rule (title, three counts), results full width, viewer under the list, no horizontal page scroll | e2e 390×844 |

## Layout

Width as the conflicts screen (`.v-page`). Top: pack heading, note (a `--v-fill` band, `role="note"`), summary line,
summary table (`<table>` with a caption, column headers Passed / Failed / Cannot tell, numbers right-aligned,
tabular). Below at ≥ 1024 px a two-column split: left the drawing sections with result cards (scrolls with the page),
right the sticky viewer. Status is never colour alone: every status has its icon and word.

## Acceptance criteria

Summary and order

- CK-1: With `pack` null the screen requests nothing and shows the "Choose a country" line. [component, `mockApi`
  call log empty]
- CK-2: The pack note renders verbatim, character for character, at both widths. [component: exact text]
- CK-3: `ruleSummary` counts pass / fail / cannot_tell per rule over all drawings, in the pack's rule order, unknown
  rules after; a rule with no results is marked "Nothing … applies to". [unit, `testing.ts`]
- CK-4: The summary line counts rules (any fail → failed, else any cannot_tell → cannot tell, else passed; no result →
  not counted) and reads "`f` rules failed, `c` cannot tell, `p` passed, over `n` drawings"; the same fixture gives the
  same numbers as the conflicts screen's checks row. [unit + component]

Results

- CK-5: Per drawing, failed results come before cannot-tell results; passed results are not listed; drawings with
  none are folded into one "pass every checked place" line. [unit `drawingResults` + component]
- CK-6: A cannot-tell result shows "? Cannot tell" with its own class, never the pass or fail class or word. [component]
- CK-7: Every failed and cannot-tell result shows its `why`, `clause.ref`, `clause.quote` and a "Read the clause"
  link to `clause.url` with `rel="noopener noreferrer"`. [component]
- CK-8: A null `value` reads "not measured"; no number on the screen is not from the payload. [unit `valueText` +
  component]
- CK-9: The drawing heading is this project's file path, even when the drawing is shared with another project
  under another name. [component: project whose file path differs from the drawing's first upload]
- CK-10: Strings from the payload (`why`, `quote`, `label`, `title`) render as text: `<img src=x onerror=…>`
  appears literally. [component]

Viewer and links

- CK-11: "Show on the drawing" requests that drawing's pages once and renders the result's marks toned (a failed
  subject's badge has `vw-badge--fail` and the name "Mark 1: <label>, fails the rule"; a cannot-tell one
  `vw-badge--cannot_tell`), with the focus page shown; a result without marks shows "Not located on the drawing" and
  no button. `viewerMarks` uses `mark_id` as the id, else `<result.id>:<index>`. [unit `viewerMarks` + component]
- CK-12: "Open in the surveyor" carries `q=<quantity>` when the result has one, and every link keeps
  `?pack=<id>`. [component: hrefs]

States

- CK-13: A queued/running project shows the "runs once the drawings are read" line and makes no checks request; a
  409 shows the same line. [component]
- CK-14: A 404 with code `unknown-pack` shows the "rules are not available" line, not "not found"; a 404 with
  another code shows `ErrorView`. [component]
- CK-15: A new `pack` prop aborts the old request and shows the new pack's results only. [component, rerender]

Layout and access

- CK-16: At 390 px no horizontal scroll; the summary is one card per rule; the viewer sits under the list. [e2e,
  fe-golden]
- CK-17: The summary table has a caption and column headers; result cards are a list; the clause link names its
  destination. [component: roles]
- CK-18: `checks.css` uses only `--v-*` tokens (no colour literal) and turns animation off under reduced motion.
  [unit on the file text, read from disk]

## Asked (#142): status of our asks

Bogdan accepted every ask (#142 c6876010899). Accepted fields are read directly once his PR lands; until then
`types.ts` types them as accepted and `testing.ts` carries them, so no fallback code is written for them.

| Ask | Status | The screen |
| --- | --- | --- |
| `file` = this project's path (review 8) | accepted | still names drawings by `fileName(project, drawing_id)` (CK-9): one source for every screen, agrees with the payload |
| `mark_id` = takeoff `MarkView.id`, null when check-only (review 10) | accepted | the viewer mark id; check-only marks `<result.id>:<index>` |
| `CheckResult.quantity` = takeoff `Row.key` (review 11) | accepted | "Open in the surveyor" on that row (`?q=`) |
| distinct 404 `unknown-pack` (review 15) | accepted | CK-14 by `code` |
| `comparison_text` (plain words), `op` never shown (review 4) | accepted | the limit phrase |
| `country` ISO + `country_name`; `name` = pack display name (review 1) | accepted | heading |
| no pack preselected; "no pack" valid; single `?pack=` (reviews 2, 3) | accepted | the "Choose a country" state (CK-1) |
| `applies_to` = `MarkView.room_type` values + element classes (review 5) | accepted | not shown (the rule title says it) |
| `quote_en` null for English law (review 6) | accepted | shown only when present and different from `quote` |
| project checks envelope `{project_id, pack, note, drawings: [{drawing_id, file, file_id, status, rules}]}` (review 7) | asked (#142), not in the 13:44 list | `types.ts` types it so; if it lands otherwise, only `types.ts` and the loader change |
| status enums for drawing and `RuleCheck` (review 9) | asked (#142), not in the 13:44 list | statuses are derived from `results[].status` (`checkStatusOf`); the payload's `status` is not shown |
| checks while the project runs: 409 code (review 12) | asked (#142); the record names "the 409 code" (for issues) | decided from `project.state` first; a 409 from checks shows the same "not finished" line |

## Out of scope

The country picker, `?pack=` routing and header tabs (fe-shared); the issues list and the export bundle (fe-ingest,
CHANGE 13:22); drawing check marks and `focus` inside `PageViewer` (fe-viewer); editing a result, signing off a
check, or storing the country on the project (#142: stateless `?pack=`); a per-drawing checks call.

## Open points

- **PageViewer props**: settled by fe-viewer (viewer.md VW-71..79): the screen maps check marks to `MarkView`
  and passes `tones` and `focus`; nothing else is asked of the viewer.
- **Rule order** is the pack's (`/api/info`); if the shell does not expose `rule_packs` in time, the summary uses the
  response order and CK-3's "pack order" part waits.
- **Passed results**: counted only, never listed. If Tudor wants them browsable, a "Show `<p>` passed places" toggle
  per drawing is a small addition.
