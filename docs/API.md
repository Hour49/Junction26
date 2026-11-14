# HTTP API (v1 draft, 2026-11-14)

The backend's HTTP API for the frontend: upload a project, follow its ingest, read drawings, ask questions,
review and sign off a takeoff. It serves stories #27, #31, #32 and #33. The server is `backend/` (FastAPI,
decision 0001); FastAPI also serves the generated schema at `/openapi.json` and a browsable one at `/docs`.

Status: **draft for review**. The shapes below are what the frontend codes against. A change after review goes
through this file first.

## Conventions

- Every endpoint is under `/api`, except `GET /health`. In development the Vite dev server proxies `/api` to
  `http://localhost:8000` (`server.proxy` in `vite.config.ts`), so the frontend calls relative URLs and needs no
  CORS. The backend also allows CORS from the Vite dev origin (`http://localhost:5173`) for a frontend run
  without the proxy.
- JSON in and out, UTF-8. Times are ISO 8601 in UTC (`2026-11-14T01:12:05Z`). Ingest objects give durations
  in milliseconds (`ms`), answers in seconds (`latency_s`, as answer_v1 does); money is US dollars (`cost_usd`).
- Ids are opaque strings: a project id is 12 hex chars, a file id `f1`, `f2`… (unique within its project), a
  drawing id 16 hex chars. A drawing id is a hash of its content and readers, so the same drawing uploaded again,
  in any project, has the same id: its review edits and sign-offs follow it. Don't parse ids.
- Boxes and polygons are **page fractions**, origin top left: `box = [x0, y0, x1, y1]`, `0 <= x0 <= x1 <= 1`. The
  same box fits any rendering of the page, whatever its pixel size. Pages are numbered from 1.
- Errors: `{"detail": "<why, in words>"}` with 404 (no such id), 409 (exists but not ready, e.g. a drawing still
  being ingested), 413 (upload over the size cap), 422 (bad request body; FastAPI's validation detail is a list).
- No auth (decision 0001).
- **No-keys mode**: with no API keys and no models, every endpoint works. Files are read by the extractors that
  need nothing (vector PDF, IFC) and the do-nothing stand-ins for the rest, and every drawing and answer says which
  reader was used (`reader`), so the screen can say so.

## Endpoints at a glance

| Method and path | What | Story |
| --- | --- | --- |
| `GET /api/info` | Which readers are active, whether it runs on fakes | #33 |
| `POST /api/projects` | Upload a zip or one file; ingest starts in the background | #27 |
| `POST /api/projects/sample` | Start a project from the synthetic sample archive (demo button) | #33 |
| `GET /api/projects` | All projects, newest first | #27 |
| `GET /api/projects/{project_id}` | Project status, every file with its state and reason | #27 |
| `GET /api/projects/{project_id}/files/{file_id}/trace` | Per-stage trace of one file | #27 |
| `GET /api/drawings/{drawing_id}` | The drawing model (extraction_v1) and how it was read | #31 |
| `GET /api/drawings/{drawing_id}/pages/{n}.png` | Page `n` rendered as PNG | #31 |
| `POST /api/ask` | Answer a question with evidence, rule, conflicts, cost | #31 |
| `GET /api/drawings/{drawing_id}/takeoff` | Every quantity with both methods' values, review state | #32 |
| `POST /api/drawings/{drawing_id}/review` | Reject, restore or add a mark; settle a conflict; recount | #32 |
| `POST /api/drawings/{drawing_id}/signoff` | Sign off one quantity | #32 |
| `GET /api/drawings/{drawing_id}/takeoff.csv` | The takeoff as CSV | #32 |

## `GET /api/info`

```json
{
  "version": "0.1.0",
  "no_keys": true,
  "readers": {
    "vector": "pdf",
    "bim": "ifc",
    "cad": "hello",
    "raster": "hello",
    "second_counter": "ifc",
    "question_parser": "templates"
  }
}
```

`no_keys: true` when no paid or model-backed reader is configured: the screen shows "running offline". A reader
named `hello` reads nothing: drawings on that route have no counts, and their questions are refused with the
reason.

## Projects and ingest

### `POST /api/projects`

`multipart/form-data` with one field `file`: a `.zip`, or a single PDF, PNG, JPEG (a phone photo of a plan
included), IFC, DXF or SVG. Whether it is a zip is read from the content, not the name. The archive caps (unpacked
size, ratio, file count, one level of nested zips, unsafe paths) are ingest's: a refused entry shows as a
`set_aside` file with the reason. An empty upload or one over the size cap: 422 or 413.

Response `202 Accepted`:

```json
{"id": "7c1e0a93b2d4", "name": "harbour-block.zip", "state": "queued", "url": "/api/projects/7c1e0a93b2d4"}
```

Ingest runs in the background. Poll `GET /api/projects/{id}` (every 500 ms to 1 s) until `state` is `done` or
`failed`. The same drawing uploaded again (any project, any name) is not recomputed: its file says `reused: true`.

### `POST /api/projects/sample`

No body. Starts a project from the synthetic sample archive that `backend/scripts/make_sample_archive.py` makes
(vector PDFs and PNGs drawn by code, a small IFC, one non-drawing; no partner data). Same response as above.

### `GET /api/projects`

```json
{"projects": [{"id": "7c1e0a93b2d4", "name": "harbour-block.zip", "state": "done", "created_at": "2026-11-14T01:12:05Z", "files": 14, "drawings": 9}]}
```

Newest first.

### `GET /api/projects/{project_id}`

Ingest's `ProjectStatus`, as is:

```json
{
  "id": "7c1e0a93b2d4",
  "name": "harbour-block.zip",
  "state": "running",
  "created_at": "2026-11-14T01:12:05Z",
  "ms": 4210.0,
  "error": null,
  "readers": {"bim": "ifc", "cad": "hello", "vector": "pdf", "raster": "hello", "second_counter": "ifc"},
  "counts": {"queued": 3, "running": 1, "ready": 7, "flagged": 1, "text_only": 1, "set_aside": 2},
  "files": [
    {
      "id": "f3",
      "path": "plans/floor-02.pdf",
      "size": 103424,
      "sha256": "4be1c09a…",
      "kind": "pdf_vector",
      "state": "ready",
      "reason": "read by the vector reader: 14 rooms, 22 doors, scale 1:100",
      "group": "plans/floor-02",
      "route": "vector",
      "source": "plans/floor-02.pdf",
      "drawing_id": "4be1c09a77a0d3e2",
      "reused": false,
      "takeoff": {"door": 14, "window": 11, "area:room|indoor": 72.4},
      "ms": 840.0
    },
    {
      "id": "f13",
      "path": "misc/site-photo-0412.jpg",
      "size": 4823449,
      "sha256": "f1107c9e…",
      "kind": "photo",
      "state": "set_aside",
      "reason": "a photograph that is not of a plan",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 20.0
    }
  ]
}
```

- Project `state`: `queued`, `running`, `done`, `failed`. `failed` only when ingest itself broke (e.g. not a
  readable zip), with `error` set; one bad file never fails the project, it becomes a `set_aside` file.
- File `id`: `f1`, `f2`… in archive order, stable within a project.
- File `kind`, by content: `pdf_vector`, `pdf_scan`, `pdf_text`, `png_plan`, `jpeg_plan`, `photo_plan`, `photo`,
  `ifc`, `dxf`, `svg`, `text`, `archive`, `unknown`.
- File `state` (`reason` says why, always set once the file is finished):
  - `queued`, `running`: not finished yet.
  - `ready`: a drawing model was written (`drawing_id`) and the route's reader read it, no conflict. Another
    rendering of a drawing (the DXF or SVG next to a PDF) is also `ready`, with a reason naming the file the
    drawing is read from.
  - `flagged`: a drawing model was written, and it needs a look: the two methods disagree, there is no reader for
    its route yet, a phone photo read without perspective correction, a scanned PDF.
  - `text_only`: text and no drawing (a spec PDF, a .txt or .csv).
  - `set_aside`: not ingested (unsafe path, zip bomb, not a drawing, a photo not of a plan, a DXF or SVG with no
    sheet next to it, a stage that failed).
- `route`: `bim`, `cad`, `vector`, `raster`, or null. `source`: the path of the file the drawing was read from (a
  PNG sheet with a vector PDF twin is read from the PDF; a sheet with its IFC model, from the model).
- `drawing_id` (16 hex chars) is set for a file that got a drawing model: every sheet file (PDF, PNG, JPEG) gets its
  own (decision 0004: a PDF and a PNG of one plan have different page frames), and an IFC model asked about on its
  own gets a page-less one (`pages: []`, `model_objects` only).
- `takeoff`: the precomputed quantities, key to value (`{}` when none). The full rows are in the takeoff endpoint.
- `readers`: which reader each route used (`hello` reads nothing). `ms`: time spent, milliseconds.

### `GET /api/projects/{project_id}/files/{file_id}/trace`

Ingest's `FileTrace`, as is:

```json
{
  "project_id": "7c1e0a93b2d4",
  "file": {"id": "f3", "path": "plans/floor-02.pdf", "state": "ready", "...": "the FileStatus above"},
  "stages": [
    {"stage": "unpack", "did": "path stays inside the archive folder, 103 kB", "ms": 0.4, "output": "plans/floor-02.pdf", "failure": null},
    {"stage": "hash", "did": "sha256 4be1c09a…, not seen before", "ms": 0.3, "output": "new", "failure": null},
    {"stage": "identify", "did": "first bytes: PDF 1.7, vector content on page 1", "ms": 4.0, "output": "pdf_vector", "failure": null},
    {"stage": "group", "did": "same name as floor-02.png: one drawing, two renderings", "ms": 0.1, "output": "plans/floor-02, 2 files", "failure": null},
    {"stage": "route", "did": "richest source is the vector PDF", "ms": 0.1, "output": "vector, from plans/floor-02.pdf", "failure": null},
    {"stage": "normalise", "did": "1 page, 1191 x 842 pt, upright", "ms": 10.0, "output": "1 page", "failure": null},
    {"stage": "extract", "did": "scale 1:100 from the scale text; rooms from wall loops", "ms": 610.0, "output": "47 elements, 14 rooms, 1 plan, scale measured", "failure": null},
    {"stage": "second_count", "did": "scale text against scale bar; 14 printed room areas against outlines", "ms": 120.0, "output": "15 checks, 0 conflicts", "failure": null},
    {"stage": "rules_takeoff", "did": "rules each-once, room-area, indoor-total", "ms": 20.0, "output": "62 quantities, 41 above zero", "failure": null},
    {"stage": "write", "did": "drawing model written", "ms": 3.0, "output": "4be1c09a77a0d3e2", "failure": null}
  ]
}
```

- `stage`: `unpack`, `hash`, `identify`, `group`, `route`, `normalise`, `extract`, `second_count`,
  `rules_takeoff`, `write`, `cache` (docs/PIPELINE.md stages 1-10; `cache` when a seen drawing is reused). A file
  that stops early has fewer stages; the list grows while the file runs.
- `did`: one readable line of what the stage did; `output`: what it produced; `ms`: its time in milliseconds.
- `failure`: set when the stage failed; the file then ends `set_aside` with this as its reason.

## Drawings

### `GET /api/drawings/{drawing_id}`

```json
{
  "id": "4be1c09a77a0d3e2",
  "file": "plans/floor-02.pdf",
  "route": "vector",
  "source": "plans/floor-02.pdf",
  "reader": {"extractor": "pdf", "second_counter": "ifc", "method": "parser"},
  "credit": null,
  "pages": [{"page": 1, "width": 1191.0, "height": 842.0, "unit": "pt", "url": "/api/drawings/4be1c09a77a0d3e2/pages/1.png"}],
  "model": { "schema": "extraction_v1", "file": "plans/floor-02.pdf", "pages": [], "scale": {}, "plans": [], "elements": [], "rooms": [], "apartments": [], "conflicts": [], "read": [], "notes": [] }
}
```

- `model`: the drawing model as an extraction_v1 document (`eval/schemas/extraction_v1.schema.json`, decision
  0004 and its amendments): `scale`, `plans`, `elements` (each with `id`, `class`, `page`, `box`, optional
  `polygon`), `rooms` (with `label`, `area_m2`, `polygon`), `apartments`, `tables`, `conflicts`, `read`,
  `model_objects`, `notes`. Shown abbreviated above.
- `reader.extractor`: the reader of this drawing's route (`pdf`, `ifc`, `hello`, `composite`...);
  `reader.method`: how it reads, as conflicts name it (`parser`, `ifc_model`, `detector`). `hello` means nothing
  was read on this route.
- `credit`: the licence credit to show next to the drawing, or null when none is known (uploads).
- `pages` is `[]` for an IFC model asked about on its own.

### `GET /api/drawings/{drawing_id}/pages/{n}.png`

The page rendered as PNG (`image/png`): a PDF page rasterised, a PNG or JPEG sheet as an upright PNG. Optional
query `width` (pixels, 200 to 4000, default 1600); the aspect ratio is kept. Marks are not drawn in: the frontend
draws them over the image from the page-fraction boxes. 404 when the page does not exist.

## Answering

### `POST /api/ask`

```json
{"drawing_id": "4be1c09a77a0d3e2", "question": "Wie viele Türen hat dieses Geschoss?"}
```

or `{"project_id": "7c1e0a93b2d4", "question": "..."}` to ask every drawing of a project. Exactly one of
the two ids.

Response: one answer per drawing asked (one for `drawing_id`):

```json
{
  "question": "Wie viele Türen hat dieses Geschoss?",
  "answers": [
    {
      "drawing_id": "4be1c09a77a0d3e2",
      "file": "plans/floor-02.pdf",
      "answer": 14,
      "unit": "count",
      "query": "door",
      "method": "takeoff",
      "rule": {"id": "each-once", "text": "each item once"},
      "marks": [
        {"id": "m1", "n": 1, "page": 1, "box": [0.41, 0.33, 0.44, 0.36], "state": "counted", "value": 1}
      ],
      "excluded": [],
      "confidence": null,
      "abstain": false,
      "estimate": false,
      "explanation": null,
      "conflicts": [
        {"value": 14, "unit": "count", "method": "parser", "file": "plans/floor-02.pdf", "page": 1, "box": null},
        {"value": 15, "unit": "count", "method": "ifc_model", "file": "plans/floor-02.pdf", "page": null, "box": null}
      ],
      "resolution": "kept 14: the sheet's own count",
      "reviewed": false,
      "verified": null,
      "reader": {"route": "vector", "extractor": "pdf", "second_counter": "ifc", "question_parser": "templates"},
      "cost_usd": 0.0,
      "latency_s": 0.0031,
      "line": {"id": 1, "answer": 14, "unit": "count", "evidence": [{"file": "plans/floor-02.pdf", "page": 1, "box": [0.41, 0.33, 0.44, 0.36]}], "method": "takeoff", "cost_usd": 0.0, "latency_s": 0.0031}
    }
  ]
}
```

- `line` is the exact answer_v1.1 line (decision 0002, `eval/schemas/answer_v1.schema.json`) as the scorer reads
  it; the other fields are the same facts shaped for the screen.
- `marks`: the evidence, one per counted item (count) or per room in the sum (area), in the order the screen numbers
  them. `n` is the number to draw (null for a mark not counted), `value` the item's share of the total (1 for a
  count, the room's m2 for an area, null when unknown). `state`: `counted`, `rejected`, `added` (after a review).
- `query`: the takeoff key the question became (`door`, `area:room|indoor`, `count wall|storey=level 1`…). Null
  when the question was not understood.
- A refusal: `abstain: true`, `method` is `refused:<why>` (`refused:unsupported-question`,
  `refused:not-in-drawing`, `refused:no-drawing`), `explanation` the reason in words, `marks` empty. `answer` may
  still hold a best estimate, labelled by `explanation`; the screen shows "can't answer: <explanation>".
- `estimate: true`: the value rests on an estimated reading; `explanation` says which.
- `conflicts`/`resolution`: two methods measured this differently; both values, and the rule that kept one.
  `abstain: true` with conflicts and no `resolution` means no rule decides: show both numbers.
- `reviewed: true` when a surveyor's edits changed the value. `verified` is null, or the sign-off
  (`{"by": "Ana", "at": "2026-11-14T01:40:00Z", "value": 14}`) when the quantity is signed off: the engineer view
  shows "verified" from it.
- `cost_usd` and `latency_s`: of this answer. A takeoff lookup costs 0 (no model call at question time).
- With `project_id`, `answers` has one item per drawing of the project, in project file order; a drawing that has
  no answer to give is in the list as a refusal.

## Takeoff and review (surveyor)

### `GET /api/drawings/{drawing_id}/takeoff`

```json
{
  "drawing_id": "4be1c09a77a0d3e2",
  "file": "plans/floor-02.pdf",
  "quantities": [
    {
      "key": "door",
      "label": "Doors",
      "measure": "count",
      "value": 14,
      "unit": "count",
      "original_value": 14,
      "first": {"method": "parser", "value": 14},
      "second": {"method": "ifc_model", "value": 15},
      "status": "conflict",
      "rule": {"id": "each-once", "text": "each item once"},
      "estimate": null,
      "conflict": {
        "values": [
          {"value": 14, "unit": "count", "method": "parser", "page": 1, "box": null},
          {"value": 15, "unit": "count", "method": "ifc_model", "page": null, "box": null}
        ],
        "resolution": {"rule": "the sheet's own count", "value": 14},
        "note": null
      },
      "marks": [{"id": "m1", "n": 1, "page": 1, "box": [0.41, 0.33, 0.44, 0.36], "state": "counted", "value": 1}],
      "signed": null
    }
  ],
  "review_queue": ["door"]
}
```

- One row per takeoff key. `label` is a readable name made from the key.
- `first`: the drawing's own reading; `second`: the independent method's value from stage 8, or null when nothing
  measured it twice.
- `status`, in the order the screen ranks them: `signed` (signed off), `conflict` (methods disagree, not settled),
  `estimate` (rests on an estimated scale or reading), `edited` (a review changed it), `agree` (two methods agree),
  `single` (one method only).
- `review_queue`: the keys a surveyor should look at (`conflict` and `estimate` rows not signed off).
- `value` is the current value (after review); `original_value` what ingest computed.

### `POST /api/drawings/{drawing_id}/review`

One edit per call. Returns the updated quantity row (same shape as in the takeoff), with the value recounted.

```json
{"quantity": "door", "action": "reject", "mark": "m3"}
{"quantity": "door", "action": "restore", "mark": "m3"}
{"quantity": "door", "action": "add", "page": 1, "box": [0.20, 0.50, 0.23, 0.53]}
{"quantity": "area:room|indoor", "action": "add", "page": 1, "box": [0.1, 0.1, 0.3, 0.3], "value": 12.4}
{"quantity": "door", "action": "settle", "value": 15}
```

- `reject` / `restore`: leave a mark out of the count or the sum, or put it back.
- `add`: a missed item; for an area or length, `value` is its m2 or m. The new mark gets an id `a1`, `a2`…;
  rejecting an added mark removes it.
- `settle`: settle a conflict by choosing the value to keep (one of the conflict's values, or any value the
  surveyor counted). The row's `status` leaves `conflict`.
- Recount: a count is the number of `counted` and `added` marks; a sum is the sum of their `value`s. A settled
  value overrides the recount until the next mark edit.
- Any edit clears a sign-off on that quantity. Edits are stored with the project and survive a restart.

### `POST /api/drawings/{drawing_id}/signoff`

```json
{"quantity": "door", "by": "Ana"}
```

Returns the row with `"status": "signed"` and `"signed": {"by": "Ana", "at": "2026-11-14T01:40:00Z",
"value": 14}`. `{"quantity": "door", "by": "Ana", "undo": true}` removes the sign-off.

### `GET /api/drawings/{drawing_id}/takeoff.csv`

`text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="<file stem>-takeoff.csv"`. One row per
quantity:

```csv
key,label,value,unit,status,first_method,first_value,second_method,second_value,rule,estimate,signed_by,signed_at
door,Doors,14,count,signed,parser,14,ifc_model,15,each-once,,Ana,2026-11-14T01:40:00Z
```

## What is not in v1

- Editing a room's outline or label (review edits marks and values only).
- Questions across several projects, or a question answered from the sum of several drawings: a project question
  gives one answer per drawing.
- Server push: progress is polled.
