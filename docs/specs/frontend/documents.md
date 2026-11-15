# Documents: the issues to answer, the drawings, every ingested file (spec, demo parity)

Status: accepted (frontend-orch GO 17:00: keep the zip link, conflicts out, `unrelated_file` notes answerable and not
counted, one count rule `needsYou`), built by fe-ingest, 2026-11-14. Brief:
`.agents/briefs/fe-demo-parity.md` (area fe-ingest) and `.agents/briefs/frontend-demo-parity.md` item 4. The demo:
`demo/vellum/app.js` `documentsScreen` / `issuesSection` and `files.js` `lists` on main 2472080 (#206, #212, #214,
#217). This screen replaces the Issues screen (`issues.md`): its pure helpers stay (numbering, kind/severity/state
words, `routeOf`), its screen parts (filters, plan panel, the Issues tab) are superseded here.

Ported from the demo: the UI and the behaviour. Never its data: no hand-made issues, boxes, suggestions or answers;
every value comes from `GET /api/projects/{pid}` and `GET /api/projects/{pid}/issues`.

## Purpose

One tab after ingest for everything that was read: first what still needs the person (the issues to answer), then the
drawings, then every file that came in, each opening its file page. The header badge counts what is left to answer.

## Files owned

| File | What |
| --- | --- |
| `src/documents/DocumentsScreen.tsx` (new) | route `#/p/<pid>/documents`, `DocumentsScreen({projectId, pack?})`: title, issues section, drawings, files |
| `src/documents/IssueCard.tsx` (new) | one issue: number, pill, file, link to the file page, `why`, `SourceFigure`, the answer form or the answer |
| `src/documents/DocumentLists.tsx` (new) | the drawings cards and the file rows, moved out of `src/ingest/ProjectScreen.tsx` (Ingest no longer lists them, per the brief: preqa-a removes them there) |
| `src/documents/documents.ts` (new) | pure: `documentIssues`, `isAnswerable`, `needsYou`, `pillOf`, `issueSource`, `shortReason` |
| `src/documents/documents.css` (new) | demo look through `--v-*` tokens |
| `src/issues/issues.ts` | kept: `KIND_LABEL`, `SEVERITY_LABEL`, `STATE_LABEL`, `kindOf`, `placeOf`, `routeOf`; `numbered`, `filterIssues`, `issueMarks`, `issueTones` lose their callers |
| `src/issues/IssuesScreen.tsx`, `IssueList.tsx`, `IssuePlan.tsx`, `issues.css` | deleted with their tests (2026-11-14, after fe-shared's 31dd5ee wired Documents); `#/p/<pid>/issues` lands on Ingest |

Uses, does not own: `SourceFigure` and `SourcePreview` (fe-viewer, `viewer.md`); `getProject`, `getIssues`,
`postRelevance`, `previewUrl`, `pageUrl`, `issuesZipUrl` and the plain drawing-name helper (fe-shared); `usePoll`,
`kindLabel`, `routeLabel`, `StateBadge`, `rowLine`, `verdictOf`, `callLine`, `callError` (`src/ingest`, preqa-a: imported,
not edited).

## User flow

1. The header tab "Documents" opens `#/p/<pid>/documents` (with `?pack=` kept when set). The badge on the tab is
   `needsYou(...)` (DOC-12), drawn by fe-shared.
2. The title row: kicker = the project name, `h1` "Documents", under it "<N files> ingested, <M drawings> read from
   them" (`plural`); on the right a secondary link "Building-code checks" → `#/p/<pid>/checks` (keeps `?pack=`): the
   checks row left the ingest pages and there is no Checks tab (frontend-orch, 17:05).
3. **Issues** (only once the project is `done`; while it runs: "The issues are listed once the project is read.").
   Heading "Issues", a line "<n> issues need your answer." or "Every issue is answered.", then " Notes are for your
   information." Then one card per issue, in the API's order, `kind: conflict` left out (conflicts are answered on
   Ingest, in fe-surveyor's conflicts list; they would be listed twice). Grouped in the API's severity order
   (fails_rule, needs_person, note); `n` = the card's position in this list (Bogdan #14: `n` is a position, `Issue.id`
   the reference).
4. Each issue card: the number, a pill ("Fails a rule" / "Needs a person" in warn, "Answered" in ok once answered,
   "Note" in grey), the drawing's plain name `Issue.drawing_name` (#229; the file path in mono only when it is null), "Open the file" → `#/p/<pid>/f/<file_id>` when `file_id` is set, the `why`,
   then the source figure (`SourceFigure`, starts minimized, with "Show source"; DOC-6), then the answer part:
   - a **note** (severity `note`, any kind but `unrelated_file`): nothing to answer, never counted;
   - an **`unrelated_file`** issue (any severity): the call on the file, real and saved by the API (`POST
     …/files/{file_id}/relevance`, decision 0010): suggestion chips "It belongs to this project" (`related`) and "It
     does not belong" (`unrelated`), with the typed name field (the surveyor's saved name, as on the file page). Once
     called: "Related: Ana's call, <time>." and "Change" (sends `{undo: true}`, then the chips again). This is
     the only place the call is made now (the file page drops its "Does it belong to this project?" block, preqa-a);
   - any **other answerable** issue (severity `fails_rule` or `needs_person`): the same name field, one chip per
     `Issue.suggestions` entry (none when empty), then "Your answer" with a text box (max 140 characters) and "Use my
     answer". A chip or "Use my answer" sends `answerIssue(pid, issue.id, {text, by}, {pack})` (the route's `?pack=`, a
     code check's issue needs it; `POST
     …/issues/{issue_id}/answer`, #223) with the saved name (`countersign.surveyorName`, as the triage call); the
     returned `Issue` replaces the card's and `issuesChanged(pid)` (fe-shared) refreshes the header badge. Once `Issue.answer` is set: "“<text>” · <by>’s answer, <time>" with
     "Change" (the chips and the box again, prefilled, with "Cancel") and "Undo" (sends `{undo: true}`). Answering
     does not close an issue (`state` stays `open`); `Issue.answer` alone makes it answered. Saved by the API, so it
     survives a reload.
5. **Drawings**: one card each (`drawings[]`): the drawing's plain name `drawingLabel(d)` (fe-shared,
   `src/api/format.ts`; the API's `name` since #224, "Drawn plan 1") as the card's title, the file path as a small
   line under it, kind,
   `routeLabel`, "Open" → the workspace (`#/p/<pid>/d/<drawing_id>/engineer`). While running, only the drawings
   listed so far; "No drawing ready yet." with none.
6. **Files**: every `files[]` row (path; on the right the state badge over "kind · size"), each a link to
   `#/p/<pid>/f/<id>`. As the demo, no technical line ("read on the drawn PDF route: 7 elements…"): only a
   `set_aside` file gets a reason line, its `reason` with a trailing parenthetical cut ("(1600x1200 px, 15% white…)"
   goes); a triaged non-plan gets the triage line with its pill instead, a file read as a plan "Read as a floor plan
   on <by>'s call" (re-sweep item 8, 17:30). The `not_plans` line above the rows as today.
7. "Export" (secondary link, `download`) to `issuesZipUrl(pid, pack)` stays in the Issues heading row: the demo has
   none, but it is a real API feature that we would otherwise lose (open point 1).

## The source figure per issue (`issueSource`)

Against fe-viewer's published props (`viewer.md` "Props", 16:40): `<SourceFigure sources={[source]} label="Source of
issue <n>"/>`, one `Source` per issue: `name` = `Issue.drawing_name` (#229, the plain drawing name) or `file`.

| Issue | `Source` |
| --- | --- |
| `drawing_id` and `page` set | `page` = that drawing's `pages[page - 1]` (`getDrawing(drawing_id)`, once per drawing, cached across cards); one `Place` `{label, box, polygon}` when `box` or `polygon` is set, else `places: []` (drawing without outlines) |
| `drawing_id` set, `page` null (an IFC model) | `page: null`: "No picture of this file", legend kept |
| no `drawing_id`, `file_id` set, the file an image or a PDF (`preview.png` exists only for those, API.md) | `page: null`, `image` = the file's `previewUrl(pid, file_id, 400)` (fe-viewer's `Source.image`), no outlines |
| no `drawing_id`, the file anything else (a DXF, a text file) | no figure (live check: a DXF's preview is a 404) |
| neither | no figure |

`Place.label` = `Issue.label` when set (#223), else the issue's `why`. `getDrawing` failing → `page: null` for that
drawing's cards. One file per issue, so the preview has no arrows; several need API ask 4.

## API calls

- `GET /api/projects/{pid}` (`usePoll` while queued/running): `name`, `files[]`, `drawings[]`, `not_plans`.
- `GET /api/projects/{pid}/issues?pack=` once `done` (409 `not-allowed` before: the "listed once read" line).
- `POST /api/projects/{pid}/issues/{issue_id}/answer` `{text, by}` or `{undo: true}` → 200 with the `Issue` (via
  fe-shared's `answerIssue`): the typed answer and the chips; the returned issue replaces it in the list.
- `POST /api/projects/{pid}/files/{fid}/relevance` (as `file-triage.md` FT-9..13): the `unrelated_file` call; the
  answer's `FileStatus` replaces that file, then the issues are fetched again (the issue's `state` turns `settled`).
- Page and preview images through `SourceFigure` (`pageUrl`, `previewUrl`).

## API asks (for Bogdan, via frontend-orch on #14)

1. **Landed in #223** (asks 1-3, 2026-11-14): `POST …/issues/{issue_id}/answer`, `Issue.answer`,
   `Issue.suggestions`, `Issue.label`. Answering does not close an issue (`state` stays `open`).
4. (later) **`Issue.sources[]`**: other files showing the same place (the demo's arrows between source files).
5. **`issues_to_answer`** on the project GET (landed in #223): the badge count server-side (fe-shared's choice;
   not `note`, `open`, unanswered, a conflict only with `resolved`: exactly `waitsForYou`, R3-G1); else `needsYou`
   (DOC-12) from `getIssues`.

## States

| State | Screen | Reach it |
| --- | --- | --- |
| Loading | "Loading documents…" | pending `getProject` |
| Running | title, "The issues are listed once the project is read.", drawings so far, files with states | `projectRunning` |
| Done, issues to answer | the line "<n> issues need your answer.", the cards | `project_issues.json` |
| Everything answered | "Every issue is answered." | variant: every answerable issue answered |
| No issues | "No issues: nothing needs a look." | `issues: []` |
| Issues failed | the error line with Retry; drawings and files still shown | `mockApi` 500 on the issues |
| Call or answer failed | the error under the card (`callError` words), the form usable | `mockApi` 409/422/500 |

## Acceptance criteria

- DOC-1: `#/p/<pid>/documents` shows the kicker = project name, "Documents", "<N files> ingested, <M drawings> read
  from them" from `project.json`. [component]
- DOC-2: While the project runs, no issues request is made and the Issues section reads "The issues are listed once
  the project is read."; drawings and files are shown. [component]
- DOC-3: Done: the cards follow the API's order with `conflict` issues left out (except one carrying `resolved`,
  Carbon's pick or can't-tell: resolver.md RS-30/31), grouped fails_rule, needs_person,
  note; each card's number is its position in this list. [unit] [component]
- DOC-4: A card shows its pill, `drawing_name` ("Plan image 1", not the path; the file path when null), "Open the file" → `#/p/<pid>/f/<file_id>` (none without `file_id`), and
  `why` as text. [component]
- DOC-5: A note card has no answer form and no chips. [component]
- DOC-6: `issueSource`: a located issue gives one `Source` with its drawing's page and one `Place` at `box` labelled
  with `label` (else `why`); no box → `places: []`; `page` null → `page: null`; no `drawing_id` but a `file_id` of an image or PDF →
  `page: null` and `image` = the file's preview; another file (DXF) or neither drawing nor file → no figure. The card passes it to `SourceFigure` (minimized), one `getDrawing` per drawing. [unit] [component]
- DOC-7: An `unrelated_file` card offers "It belongs to this project" / "It does not belong" with the name field;
  a press sends `{verdict, by}` to `POST …/files/<file_id>/relevance` (`relevance_request.json` for related by Ana),
  then refetches the issues; the card shows the call and "Change"; "Change" sends `{undo: true}`. [component]
- DOC-8: Another answerable card, name "Ana" saved: typing "1:100" and "Use my answer" sends `{text: "1:100", by:
  "Ana"}` to `POST …/issues/<id>/answer` and shows the returned answer "“1:100” · Ana’s answer, <time>" and the
  pill "Answered"; "Change" reopens the box prefilled, "Cancel" closes it unchanged; "Undo" sends `{undo: true}` and
  the form is back; an empty or spaces-only answer, or no name, cannot be sent; a failed POST is worded under the
  card (`detail (code)`), the form usable. Under `?pack=fi` the POST URL carries `?pack=fi`; after an answer the
  badge is asked again (`issuesChanged`). [component]
- DOC-9: One chip per `Issue.suggestions` entry; a chip press sends `{text: <chip>, by}` (`issue_answer_request.json`
  for "Check it on site" by Ana); no chips when `suggestions` is empty or missing (no invented chips). [component]
- DOC-10: The drawings section lists every drawing with its plain name (`drawingLabel`: "Drawn plan 1") as the
  card's title and its file path as a small line, kind, route words and "Open" →
  `#/p/<pid>/d/<id>/engineer`; the files section lists every file linking to its file page. [component]
- DOC-11: "Export" links with `download` to `/api/projects/<pid>/issues.zip` (`?pack=` kept). [component]
- DOC-12: `needsYou(issues)` = the issues Documents
  lets you answer (not `conflict`, except a `cannot_tell` one, RS-31), still `open`, without `Issue.answer`, notes excluded (severity `note`, an `unrelated_file` note too);
  the one count rule, used by fe-shared's `useIssuesToAnswer` (the badge) and preqa-a's done line. [unit]
- DOC-16: The title row has one link "Building-code checks" → `#/p/<pid>/checks`, with `?pack=<id>` when a pack is
  set. [component]
- DOC-17: A ready, flagged or text-only file row shows no reason text; a `set_aside` row shows its reason without
  the trailing parenthetical; a triaged non-plan shows its triage line and pill. [unit] [component]
- DOC-13: The issues request failing shows its `detail (code)` with Retry, and the lists stay. [component]
- DOC-14: At 390 no sideways scroll, every button, chip, link and input at least 44 px tall; Esc closes the source
  preview and focus returns to "Show source" (fe-viewer's component). [e2e]
- DOC-15: `documents.css` uses only `--v-*` tokens (no colour literals). [unit]

## Out of scope

- Answering conflicts here (Ingest's conflicts list, fe-surveyor).
- Filters by kind/state, the plan panel beside the list (the demo dropped them).
- Hand-made suggestions or placeholders per issue (demo data).

## Open points

1. **Export.** The demo's Documents has no export; the API's `issues.zip` is real. Recommend keeping it as one
   secondary link in the Issues heading (DOC-11). Drop it if Tudor wants strict parity.
2. **Conflicts left out of Documents and of the badge.** They are listed and answered on Ingest; counting them in
   the Documents badge would count them twice. Needs fe-shared's badge and preqa-a's done line to use `needsYou`.
3. **`unrelated_file` notes stay answerable.** The demo rule "notes can't be answered" would leave no way to
   overrule a "not related" verdict once the file page drops its triage block. Recommend: answerable, not counted.
4. **The drawings/files lists move.** From `src/ingest/ProjectScreen.tsx` (preqa-a) to `src/documents/DocumentLists.tsx`
   (mine), so one owner. preqa-a then removes them from Ingest; `TriageLine` moves with them.
5. **`SourceFigure` and file previews.** Resolved: fe-viewer added `Source.image`.
