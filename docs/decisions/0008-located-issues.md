# 0008: Every finding in a project is one located issue in GET /api/projects/{project_id}/issues, as JSON and CSV

- Status: accepted
- Date: 2026-11-14 12:30 (Europe/Helsinki)
- Decided by: agent tables-fix (worker), for Bogdan's MUST DO of 2026-11-14 12:20 (story #140); accepted by
  Bogdan's orchestrator 2026-11-14 12:30 ("0008 accepted, GO")
- Board thread: to be posted by the orchestrator. Tudor's fleet reviewed the shape (#142, items 8 and 14-23, all
  accepted by the orchestrator 2026-11-14 12:36); their answers are folded in below. The zip export is Tudor's ask
  (#142 c6875981360, "when exporting, we should also export the floor plan not only the issues").

## Context

Stoa's own screen shows a building floor by floor with located issues (feedback F-004). We already make such
findings, each tied to a drawing and most to a page and a box: conflicts between two methods (in
`GET /api/projects/{id}/review`), refused answers (the question log), files set aside at ingest, and pages read as a
photo or a scan (`flagged`). Building-code checks (#139, decision 0009) and double-check requests (#129) will add
more. Story #140 asks for one list, additive to API v1, that Stoa or our own screen can read.

## Decision

Three read-only routes, none of which makes a model call:

- `GET /api/projects/{project_id}/issues?pack=<pack id>` returns `{project_id, pack, issues: [Issue]}`.
- `GET /api/projects/{project_id}/issues.csv?pack=` returns the same rows as CSV.
- `GET /api/projects/{project_id}/issues.zip?pack=` returns `issues.csv` with a first column `n` (the issue's
  number in the list), plus one PNG per drawing page that has issues with a box. Each PNG shows the page with every
  such issue drawn (its polygon, else its box), labelled with its `n` and coloured by severity. Under the page are
  the issues' sentences, a colour key and the drawing's licence credit. The PNGs are drawn by `evidence.png`'s
  renderer (`app/adapters/evidence_render.py`) over `page_render`'s page at 1600 px. PNG files are named
  `<file stem>-p<page>.png`, with `-2`, `-3`… added when two files share a stem. An issue with no page or no box
  is only in the CSV.

The rest of the contract:

- `pack` is optional. With a pack (decision 0009, e.g. `fi`), the failed building-code checks of that pack join the
  list. Without one, `pack` is null and the list has no code checks: the country is a choice made on the screen,
  not stored on the project. No pack is preselected.
- Errors use the API's one error shape. An unknown project is 404 `not-found`. An unknown pack is 404
  `unknown-pack` (its own code, so a screen resets its pack choice instead of saying the project is gone; the
  API's codes are kebab-case). A project that is not `done` is 409 `not-allowed`, the code
  `POST /api/projects/{id}/ask` uses. The CSV and zip routes answer errors the same way. A screen should offer
  the downloads only once the project is `done` (`ProjectSummary.state`), so a plain `<a download>` never saves an
  error body.
- Downloads are `Content-Disposition: attachment; filename="<project name>-issues[-<pack>].csv"` (or `.zip`).
- The list is built from what the API already holds: each drawing's takeoff in this project (the rows
  `GET /review` reads), the project status (files), the question log, and 0009's project checks.
- `ProjectSummary` gains `issues_open` (#142 item 22): how many issues of the list without a pack are in state
  `open`; null until `done`. The project list computes each drawing's takeoff once, for both the review counts and
  the issues.

One issue, from the sample (`backend/tests/fixtures/api_v1/project_issues.json`):

```json
{
  "id": "conflict-734b9f17d4fd",
  "kind": "conflict",
  "severity": "note",
  "state": "settled",
  "drawing_id": "6d153ea15dca9ab4",
  "file": "plans/flat-b.pdf",
  "file_id": "f3",
  "floor": null,
  "page": 1,
  "box": [0.16667, 0.125, 0.5, 0.375],
  "polygon": [[0.16667, 0.125], [0.16667, 0.375], [0.5, 0.375], [0.5, 0.125]],
  "mark_id": "m1",
  "why": "Area of room (name Küche · 1.01): checked twice, they disagree: the room outlines at the sheet's scale 22.4 m², the printed room areas 30 m²; kept 30 m²: the printed label over the outline at the sheet's scale.",
  "quantity": "area:room|name=1.01",
  "question": null,
  "reason": null,
  "check": null,
  "links": {
    "drawing": "/api/drawings/6d153ea15dca9ab4?project=5e0c1a2b3d4f",
    "takeoff": "/api/drawings/6d153ea15dca9ab4/takeoff?project=5e0c1a2b3d4f",
    "trace": "/api/projects/5e0c1a2b3d4f/files/f3/trace",
    "checks": null
  }
}
```

The fields:

- `id`: unique within the project and stable across calls and restarts; `(project_id, id)` is unique everywhere.
  It is `<kind>-` plus the first 12 hex of the SHA-256 of the kind, the drawing id (the file id when there is no
  drawing) and the source ref. The project id is left out, because every route is per project and the fixtures
  must come out the same on every run. The source ref is the
  quantity key for a conflict, the question (whitespace collapsed, lower case) for a refusal, the file path for a
  set-aside file, `reading` for a reading flag, and `<pack>:<CheckResult.id>` for a code check. An issue keeps its
  id when it is settled or signed off. Asking the same question again on the same drawing is the same issue.
- `kind`: the type of finding.
  - `conflict`: two methods measured a quantity differently, one issue per disagreement (`disputes()`: a room keyed
    under several names is one issue). Its identity on the conflicts screen is `quantity` + `drawing_id`, the same
    as `ConflictEntry`.
  - `refused_answer`: a question in the project's log whose last ask on a drawing got no number.
    - Questions the parser can't read (`unsupported-question`) are left out, because they say nothing about the
      drawing.
    - Question-log lines gain an optional `refusal` (the refusal code) from 2026-11-14. Older lines without it are
      left out, so nothing is guessed.
    - `drawing_id` is the asked drawing. A project-wide question (`POST /api/projects/{id}/ask`) is logged one line
      per drawing, so its refusals are per drawing too. `question` is the question verbatim.
  - `set_aside`: ingest set the file aside (a photo with no plan, a lone DXF...), with its reason.
  - `reading_flag`: one per drawing whose page was read with a caveat. Its sources are the drawing's reading flags
    (`DrawingInfo.flags`: a phone photo, a scanned PDF) and a reader that read nothing from the sheet
    (`judge.read_nothing`, e.g. no reader for the raster route yet). A conflict in ingest's `flagged` reason is not
    repeated here, because it is its own issue.
  - `code_check_failed` (#139, decision 0009, only with `?pack=`): one issue per `CheckResult` with
    `status: fail`. Its drawing, page, box and polygon come from the result's first `subject` mark (the failing
    room or door), and `mark_id` is that mark's takeoff `MarkView.id` when it is a takeoff mark. `why` is the
    result's `why` plus the clause ref, and `check` is `<pack>:<CheckResult.id>`. A `cannot_tell` result is not an
    issue.
  - Later, additive (a new value of a string the screen shows): `double_check` (#129: an uncertified answer, with
    the disputed places as one issue each). It is not in this version, because #129 is not merged.
- `severity`: what the finding asks of a person, not a made-up score. There are three values, in this order:
  - `fails_rule`: the drawing, as read, breaks a rule we check (`code_check_failed`). This is the strongest
    finding we make.
  - `needs_person`: a value is in doubt and nobody decided it: a `conflict` with `needs_person` true (no rule
    decides, nobody settled it) and a `double_check`. A number in the takeoff is unconfirmed until someone acts.
  - `note`: kept for the record, with nothing in doubt in the takeoff: a conflict a rule decided or a person
    settled or signed, a refused answer (no number was given, so none is wrong), a file set aside, a reading flag.
- Order (#142 item 14), the same in the JSON, the CSV and the zip, and stable between calls:
  1. severity, in the order above;
  2. the drawing, in `GET /api/projects/{id}` `drawings` order, with files that have no drawing after all
     drawings, in upload order;
  3. page, with no page last;
  4. the box's top edge, with no box last;
  5. the source ref;
  6. `id`.
- `state`: `open`, `settled` or `signed_off`.
  - A conflict is `signed_off` when its row is signed (`ConflictEntry.signed` set). It is `settled` when a person
    settled it (`ConflictEntry.settled` set) or a rule decides it (`ConflictEntry.conflict.resolution` set), and
    `why` says which. Otherwise it is `open`.
  - The other kinds are always `open`: nothing in the API settles a refusal, a set-aside file or a failed code
    check (0009: checks read the drawing as ingest read it, and review edits don't change them in this version).
- `drawing_id`, `file`, `file_id`:
  - `file` is **this project's** upload path for the drawing (#142 item 8), as `GET /api/projects/{id}` `drawings`
    names it. It is never the drawing's first upload in another project: drawings are shared by content.
  - `file_id` is that file's `FileStatus.id` (`f1`, `f2`…, item 18), not a hash.
  - `drawing_id` is null for a file with no drawing (most `set_aside`).
- `floor`: only where a source states it, else null, never guessed.
  - Sources: the storey of the plan on the issue's page (`Plan.storey`: today set only from the IFC model, for a
    sheet of an IFC project, by the sheet title naming an IFC storey or by the storey the sheet's drawn objects
    belong to in the model), or the storey in the quantity's own key (`scope.storey`, an IFC storey).
  - No reader takes a floor from a raster sheet today, so a CubiCasa scan is `floor: null`.
- `page`, `box`, `polygon`, `mark_id`: where to open the drawing, in page fractions as on `MarkView`. Only a page
  the drawing has is given (a building model has none). The first of these that exists is used:
  1. the row's one takeoff mark (a room): its page, box, `polygon` (#142 item 23: a room is drawn by its outline)
     and `mark_id` = its `MarkView.id` (item 17: the viewer selects it by id);
  2. the box a method read the value from (the conflict's measured values);
  3. the plan on the page, when the drawing has one plan on that page (a count over the sheet);
  4. otherwise null.
  `mark_id` and `polygon` are null except in case 1 (and for a code check's subject mark). A reading flag gives the
  page of a one-page drawing with no box, because it is about the whole sheet. A refused answer and a set-aside
  file have no page. There is no second id scheme for marks.
- `why`: one plain sentence: the two values and what decided, the drawing's reason for the refusal, or ingest's
  reason. No codes.
- `quantity` (the takeoff row key, used by the surveyor link `?q=`), `question` (the text asked), `reason` (ingest's
  reason) and `check` (`<pack>:<CheckResult.id>`) are source refs; each is null where it doesn't apply.
- `links` (#142 item 21) are **API paths** (relative, `/api/...`), not screen routes: the drawing and its takeoff
  in this project, the file's ingest trace, and for a code check the drawing's checks
  (`/api/drawings/{id}/checks?pack=..&project=..`). Each is null where there is nothing to open. Screens build
  their routes from `drawing_id`, `file_id` and `quantity`.
- CSV (`text/csv; charset=utf-8`) has one header row:
  `id,kind,severity,state,file,file_id,drawing_id,floor,page,x0,y0,x1,y1,mark_id,why,quantity,question,reason,check`
  (the zip's copy adds `n` first). A missing value is an empty cell. Text fields are escaped like the takeoff CSV
  (a cell starting with `= + - @`, a tab or a carriage return gets a leading `'`). The polygon is left out of the
  CSV; it is in the JSON.

Owners: the backend side (routes, shape, fixtures) is the API worker's; the list view with jump-to-place is Tudor's
fleet's. Stoa's field names (F-004.1) may be added as aliases later if they tell us.

## Alternatives considered

- A numeric severity (1 to 5): we have no data to calibrate it, and the brief forbids an invented scale. Three
  named levels map one-to-one to what a person has to do.
- Re-asking every logged question at list time to get the refusal reason: it makes model calls (cost) on a read.
  Logging the code when the answer is made costs nothing.
- Guessing a floor from a sheet's file name or a CubiCasa layout: not stated by the source, so it stays null
  (story #140, "Done when").
- Including `unsupported-question` refusals: they are about our parser, not the building.
- A CSV that answers 409 with an empty body for a plain link (#142 item 16): every error in the API has one shape.
  The screen offers the download once the project is done instead.
- A second renderer for the zip's pages: `evidence.png`'s renderer already draws numbered marks with placed labels,
  a key and the credit.

## Consequences

- Additive to v1: three new routes; an optional `refusal` on question-log lines (in
  `GET /api/projects/{id}/questions` when present); `ProjectSummary.issues_open`; `Issue` as above; a new error
  code `unknown-pack` (`UnknownPackError`, for 0009's routes too). One new fixture, `project_issues.json`, is
  appended last (no pack: no pack exists yet). Two existing fixtures each gain their new field: `project_list.json`
  (`issues_open`) and `project_questions.json` (`refusal` on the refused line). No other field changes.
- `code_check_failed` rows need 0009's project checks (`GET /api/projects/{id}/checks?pack=`, its core function).
  Until that is merged there is no pack, so any `?pack=` is 404 `unknown-pack` and the list works without one.
  #129 will add `double_check` the same way.
- Building the list costs one takeoff per drawing per call, the same as `GET /review`. This is slow on big
  projects, and the project list now pays it once per project for both counts. Revisit if the floor view polls
  it.
- The zip renders every page with boxed issues at 1600 px inside the request. Measured on dev1 (2026-11-14,
  TestClient) on the sample with a conflict on each of its 4 pages: 0.51 s for the zip, against 0.025 s for the
  JSON list, so about 0.12 s per page. A project with hundreds of pages would make a slow download.
