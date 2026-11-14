# Export the scan as CSV (spec, frontend, Vellum)

Status: draft, 2026-11-14 16:50, by fe-export. Source: Tudor via the law-kb orchestrator (`.agents/briefs/fe-export.md`):
"also add an "export" button after the ingest to the right of workspaces. use apple design on the worker which does
that. it will create a csv with all the data we've done in our scan."

## Purpose

One button in the header downloads everything the scan read for the project in the route as one CSV file: the files,
every room, door, window and other drawn element, every takeoff quantity, the conflicts and how they were settled, the
building-code check results (when a country is chosen) and the issues. One row per item; a `kind` column says what
the row is. Built in the browser from existing endpoints (docs/API.md); no backend change.

## Files owned

- `frontend/src/export/csv.ts`: pure. `COLUMNS`, `toCsv(rows)` (RFC 4180, BOM, formula guard), `scanRows(scan)`
  (the API answers → rows), `fileName(projectName, date)`.
- `frontend/src/export/scan.ts`: `loadScan(projectId, pack, signal)`, the API calls below.
- `frontend/src/export/ExportButton.tsx`: the button; `export.css` its look.
- Tests beside them (`csv.test.ts`, `ExportButton.test.tsx`).
- `frontend/src/shell/Header.tsx`: only the line that mounts the button after "Workspaces".

## API calls (on click only; nothing is fetched before)

1. In parallel: `GET /api/projects/{pid}` (`getProject`), `GET /api/projects/{pid}/review` (`getProjectReview`),
   `GET /api/projects/{pid}/issues[?pack=]` (`getIssues`), and, only with a `?pack=` in the route,
   `GET /api/projects/{pid}/checks?pack=` (`getProjectChecks`).
2. Then, for every drawing of the review's `drawings[]` (the drawings that were read), in parallel:
   `GET /api/drawings/{id}/takeoff?project={pid}` (`getTakeoff`) and `GET /api/drawings/{id}/model` (`getModel`,
   extraction_v1: `rooms`, `elements`, `model_objects`).

Any failed call fails the export (no partial file).

## Columns and rows

Columns, in order: `kind, file, drawing_id, page, item, type, label, value, unit, width_m, height_m, status, detail`.
An absent value is an empty cell.

| `kind` | One per | `item` | `type` | `label` | `value` / `unit` | `status` | `detail` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `file` | project file, then each `skipped` entry | file id | file kind | | | file state (`skipped`) | reason |
| `room` | model `rooms[]` | room id | room type | room label | `area_m2` / `m2` | `area_status` | |
| `element` | model `elements[]` | element id | class (`door`, `window`, …) | | | | |
| `quantity` | takeoff `quantities[]` | key | measure | label | value / unit | status | `settled <v>`, `signed by <who>` |
| `conflict` | review `conflicts[]` | quantity key | | label | value | `open` (needs a person), `settled by rule`, `settled by a person` or `signed off` (as conflicts.ts) | the measured values and the resolution rule |
| `check` | checks result (each rule's `results[]`) | result id | rule id | subject label | value / unit | status | why |
| `issue` | issues `issues[]` | issue id | issue kind | severity | | state | why |

`width_m` / `height_m` on an `element` row come from the model object whose `element` is that element (BIM files);
blank otherwise. `file` and `drawing_id` say where the row comes from; `page` where it is on the drawing.

## Look (apple-design)

A quiet secondary control, a sibling of "Workspaces": the `header-pill` look (48 px high, pill radius, 16 px, 600,
`--v-fill`) with `v-press` (scale 0.97 on press, instant), a small download glyph (`aria-hidden`) before the word
"Export". Accessible name "Export scan as CSV". Focus ring from the base styles. While the data loads the label is
"Preparing…", the button is `aria-disabled="true"` with `aria-busy` and the reason as its title ("Loading the
scan's data"); clicks are ignored. Done: the label becomes "Exported" with a check glyph for 1.5 s, in place (no toast),
announced through a polite live region. Error: the label is "Export failed" in `--v-danger`, the message is in a
`role="alert"` line read by screen readers and in the title; clicking again retries. Under
`prefers-reduced-motion` nothing animates (the base rule). Phone and compact header (≤1100 px): after the country
picker on the second line; at ≤720 px only the glyph shows (the name stays).

## Acceptance criteria

- EX-1 The header shows the button directly after "Workspaces" on every route with a project, and on no route without
  one (home, account).
- EX-2 Clicking downloads one file named `<project name>-scan-<YYYY-MM-DD>.csv` (the name without its `.zip`
  extension, `/ \ : * ? " < > |` replaced by `-`; the local date).
- EX-3 The first line is the header `kind,file,drawing_id,page,item,type,label,value,unit,width_m,height_m,status,detail`.
- EX-4 One row per item of each kind in the table above, from the fixtures: files, rooms, elements, quantities,
  conflicts, checks (only with a pack), issues.
- EX-5 RFC 4180: a cell with a comma, a double quote, CR or LF is quoted, quotes doubled; lines end with CRLF.
- EX-6 The file is UTF-8 and starts with a BOM (`﻿`), so Excel shows ä, ö, ü right.
- EX-7 Formula guard: a text cell starting with `=`, `+`, `-`, `@` (or tab / CR) gets a leading `'`.
- EX-8 Numbers stay numbers: a numeric cell is written as the number (`22.401`, `-3`), never guarded or quoted.
- EX-9 An empty project (no files, drawings, conflicts, issues) gives a header-only file.
- EX-10 Any failed call: no file is downloaded; the button reads "Export failed" and an alert carries the error's
  detail; clicking again retries.
- EX-11 While loading: label "Preparing…", `aria-disabled="true"`, `aria-busy="true"`, the reason as title; a second
  click sends no second request.
- EX-12 After a download the label is "Exported" for 1.5 s, announced in a polite live region, then "Export" again.
- EX-13 Checks are asked only with `?pack=` in the route, and with that pack; issues carry the pack too.

## Out of scope

Excel/XLSX, a choice of columns, the issue PNGs (Issues' own "Export" zip has them), the model's tables and
apartments, a server-side export endpoint.
