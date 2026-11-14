# HTTP API (v1, 2026-11-14)

The backend's HTTP API for the frontend: upload a project, follow its ingest, read drawings, ask questions,
review and sign off a takeoff. It serves stories #27, #31, #32 and #33. The server is `backend/` (FastAPI,
decision 0001), routes in `backend/app/api/`. Decision record: [0007](decisions/0007-http-api.md).

**One source of truth.** Every route declares a pydantic response model, so `/openapi.json` describes every
response. The same document is committed as [`docs/api/openapi-v1.json`](api/openapi-v1.json), so the frontend
generates its types without a running server (`npx openapi-typescript ../docs/api/openapi-v1.json -o
src/api.d.ts`); `tests/api/test_api_openapi.py` fails when the app's schema and that file differ.
Every JSON example below is a file in `backend/tests/fixtures/api_v1/`, made from real responses on the synthetic
sample archive (`backend/tests/api/make_fixtures.py`) and trimmed to a few rows. `tests/api/test_api_fixtures.py`
fails when a fixture no longer fits its model or this page no longer quotes it as it is. The frontend can use the
same files as mock data. The project id, times and durations in them are fixed stand-ins, so the files are the same
on every run.

Items marked **waits on core** are agreed, and the field is in the shape already, but it is null or empty until
core's part lands.

## Changing the contract

The API is the line between the pipeline and the frontend: anything behind it may change; what is on this page,
in `docs/api/openapi-v1.json` and in `backend/tests/fixtures/api_v1/` may not, except as below.

- v1 changes are **additive only**: a new optional field, a new endpoint, a new value of a string the screen
  shows as text. Old clients keep working.
- A rename, a removal, a type change or a new required request field needs `/api/v2`, or one announced PR that
  updates this page, `openapi-v1.json` and the fixtures together and says so in the changelog below.
- The tests hold it: `tests/api/test_api_openapi.py` (the schema is the committed file; regenerate it with
  `cd backend && uv run python tests/api/make_openapi.py`) and `tests/api/test_api_fixtures.py` (every example
  fits its response model and is quoted here as it is; regenerate with
  `cd backend && uv run python tests/api/make_fixtures.py --doc`).

## Conventions

- Every endpoint is under `/api`, except `GET /health`. In development the Vite dev server proxies `/api` to
  `http://localhost:8000` (`server.proxy` in `vite.config.ts`), so the frontend calls relative URLs. The backend
  sets no CORS (docs/ENGINEERING.md §1).
- JSON in and out, UTF-8. Times are ISO 8601 in UTC. Ingest objects give durations in milliseconds (`ms`), answers
  in seconds (`latency_s`, as answer_v1 does); money is US dollars (`cost_usd`).
- Ids are opaque: a project id is 12 hex chars, a file id `f1`, `f2`… (unique within its project), a drawing id
  16 hex chars. An id that does not have its pattern is answered 404, like an unknown one. A drawing id is a hash
  of the drawing's content and readers: the same drawing uploaded again, in any project, has the same id. Its
  review edits and sign-offs belong to the project they were made in: the review routes, `POST /api/ask` and
  `evidence.png` read and write that project's when given one (`project` / `project_id`), and a separate state
  that no project sees when given none (clients from before 2026-11-14 06:40).
- A takeoff key (`door`, `area:room|indoor`, `area:room|name=küche`) holds `:`, `|`, `=` and spaces: pass it
  through `encodeURIComponent` when it goes into a URL.
- **The page frame.** `pages[].width/height`, every box and polygon, and `pages/{n}.png` are in one frame per page:
  the sheet after normalisation. For an image that is: EXIF orientation applied, then any rotation, deskew or
  perspective correction ingest made. `pages/{n}.png` always serves that normalised image, never the upload, and
  `pages[].normalised` says what was done (`preview.png` shows the upload for a before/after view).
- Boxes and polygons are page fractions, origin top left: `box = [x0, y0, x1, y1]`, `0 <= x0 <= x1 <= 1`. To draw
  a mark, put the `<img>` in a `position: relative` box and place the mark at `left: x0*100%`, `top: y0*100%`,
  `width: (x1-x0)*100%`, `height: (y1-y0)*100%`; or lay an SVG with `viewBox="0 0 1 1"` and
  `preserveAspectRatio="none"` over the image.
- Every string that comes from a file (a path, a name, a room label, an IFC name, a `reason`, a trace line, a
  label made from a key) is untrusted: render it as text, never as HTML.
- No auth (decision 0001). uvicorn binds to `127.0.0.1`. Anyone who reaches the port can list projects, read every
  page and fill the disk, so open it to a phone only on a hotspot or Tailscale, with the synthetic sample only.
  `GET /api/info` names readers only: no keys, endpoints or local paths.
- **No-keys mode**: with no API keys and no models, every endpoint works. Files are read by the readers that need
  nothing (vector PDF, IFC) and the do-nothing stand-ins for the rest (`hello`), and `GET /api/info` says which.

### Errors

Every error has one shape: `{"detail": "<one sentence>", "code": "<slug>"}`. A request that fails validation also
has `errors`, FastAPI's list, with `detail` joining its messages. An unexpected error is `500` with
`{"detail": "internal error", "code": "internal"}`.

<!-- fixture: error.json -->
```json
{
  "detail": "no drawing 0123456789abcdef",
  "code": "not-found"
}
```

| Case | Status, `code` |
| --- | --- |
| Unknown or malformed project, file or drawing id, unknown page, quantity key or mark id | 404 `not-found` |
| `reject`/`restore` without `mark`, `add` without `page` and `box` or on a page the drawing does not have, `add` to an area or length, `settle` without `value`, a width that is not 400, 1600 or 3200 | 422 `invalid` |
| A body that does not fit the request model (no `name` on an upload, an empty question, an unknown action) | 422 `validation` |
| Sign-off of a conflict no rule decides and nobody settled; an edit of a signed-off quantity | 409 `not-allowed` |
| Upload over 200 MB | 413 `too-large` |
| An upload while 3 projects are still being ingested | 429 `busy` |
| A method the path does not take (`GET /api/ask`) | 405 `method-not-allowed` |
| An unexpected error | 500 `internal` |
| A project whose ingest broke | 200, `state: "failed"`, `error` set |
| A photo with no plan, a lone DXF | 200, `state: "done"`, the file `set_aside` with its reason, `drawings: []` |
| A question the drawing cannot answer | 200, `refusal` set |

An edit of a signed-off quantity (409):

<!-- fixture: error_not_allowed.json -->
```json
{
  "detail": "area:room|name=1.01 is signed off by Ana; undo the sign-off first",
  "code": "not-allowed"
}
```

## Endpoints at a glance

| Method and path | What | Story |
| --- | --- | --- |
| `GET /api/info` | Which readers are active, whether it runs on fakes, the upload limits | #33 |
| `POST /api/projects?name=` | Upload a zip or one file; ingest starts in the background | #27 |
| `POST /api/projects/sample?fresh=` | Start a project from the synthetic sample archive (demo button) | #33 |
| `GET /api/projects` | All projects, newest first | #27 |
| `GET /api/projects/{project_id}` | Project status: every file with its state and reason, one drawing per plan | #27 |
| `GET /api/projects/{project_id}/files/{file_id}/trace` | Per-stage trace of one file | #27 |
| `GET /api/projects/{project_id}/files/{file_id}/preview.png?width=` | The file as uploaded, EXIF turn applied | #27 |
| `GET /api/projects/{project_id}/review` | Per drawing what is left to review, and every conflict of the project | #32 |
| `GET /api/drawings/{drawing_id}` | How the drawing was read, its pages, questions it can answer | #31 |
| `GET /api/drawings/{drawing_id}/model` | The drawing model (extraction_v1) | #27 |
| `GET /api/drawings/{drawing_id}/pages/{n}.png?width=` | Page `n` as PNG | #31 |
| `GET /api/drawings/{drawing_id}/evidence.png?question=&width=` | An answer with its proof drawn on its page | #31 |
| `POST /api/ask` | Answer a question with its takeoff row, marks, rule, conflicts, cost | #31 |
| `GET /api/drawings/{drawing_id}/takeoff?zeros=` | Every quantity with its marks, both methods' values and review state | #32 |
| `POST /api/drawings/{drawing_id}/review` | Reject, restore or add a mark; settle; reset. Returns the takeoff | #32 |
| `POST /api/drawings/{drawing_id}/signoff` | Sign off one quantity, or undo it. Returns the takeoff | #32 |
| `GET /api/drawings/{drawing_id}/takeoff.csv?zeros=` | The takeoff as CSV | #32 |

## `GET /api/info`

<!-- fixture: info.json -->
```json
{
  "no_keys": true,
  "readers": {
    "bim": "ifc",
    "cad": "hello",
    "vector": "pdf",
    "raster": "hello",
    "tables": "pdf",
    "second_counter": "ifc",
    "rectifier": "none",
    "question_parser": "templates",
    "answer_prior": "none",
    "decisions_kind": "False"
  },
  "limits": {
    "upload_mb": 200,
    "file_mb": 600,
    "unpacked_mb": 2048,
    "files": 5000,
    "question_chars": 2000
  }
}
```

`no_keys: true` when no reader needs an API key or a model server: no `gemini`, `verda` or `decisions` source
in `RASTER_COMPONENTS`, and `DECISIONS_CONFIDENCE` and `DECISIONS_KIND` off. The screen then shows "running
offline". A reader named `hello` reads nothing: drawings on that route have no counts, and their
questions are refused with the code `no-reader`. `limits` lets the screen refuse a file before uploading it.

## Projects and ingest

### `POST /api/projects?name=<file name>`

The request body is the file's bytes, `Content-Type: application/octet-stream`; `name` (required) is its file
name. The file is a `.zip`, or a single PDF, PNG, JPEG (a phone photo of a plan included), IFC, DXF or SVG.
Whether it is a zip is read from the content, not the name.

```js
fetch(`/api/projects?name=${encodeURIComponent(file.name)}`, {method: "POST", body: file})
```

Limits: the upload 200 MB (413, checked while it streams); per file 600 MB, 2 GB unpacked, 5000 files, a
compression ratio of 200 for entries over 1 MB, one level of nested zips. Symlinks, encrypted entries and paths
with `..`, absolute paths, drive letters or control characters are refused. A refused entry shows as a `set_aside`
file with the reason. The type of each file is read from its content.

Response `202 Accepted`:

<!-- fixture: project_started.json -->
```json
{
  "id": "5e0c1a2b3d4f",
  "name": "sample-project.zip",
  "state": "done",
  "url": "/api/projects/5e0c1a2b3d4f"
}
```

Poll `GET /api/projects/{id}` every 500 ms while `state` is `queued` or `running`, and stop on `done` or `failed`.
Progress is `(ready + flagged + text_only + set_aside) / files.length`. A file's drawing can be opened and asked as
soon as that file is `ready` or `flagged`: the project does not have to be `done`. The same drawing uploaded again
is not recomputed (`reused: true`).

### `POST /api/projects/sample?fresh=<bool>`

No body. Starts a project from the synthetic sample archive that `backend/scripts/make_sample_archive.py` makes
(vector PDFs and PNGs drawn by code, a plan as an image and as a phone photo, a small IFC, a DXF, text files, a
site photo; no partner data). 404 when the archive has not been built. Same response as an upload.

`fresh=true` ingests every file again without the cache, so the ingest screen has something to watch, and resets
the last sample project's review edits and sign-offs. Each run is a new project, and review state belongs to the
project, so a new run starts clean either way.
Without it a second sample run is all `reused: true`.

### `GET /api/projects`

Every project, newest first: open one ingested earlier when a live ingest is slow.

<!-- fixture: project_list.json -->
```json
{
  "projects": [
    {
      "id": "5e0c1a2b3d4f",
      "name": "sample-project.zip",
      "state": "done",
      "created_at": "2026-11-14T08:00:00+00:00",
      "files": 11,
      "drawings": 5
    }
  ]
}
```

### `GET /api/projects/{project_id}`

Ingest's project status, plus `drawings`:

<!-- fixture: project.json -->
```json
{
  "id": "5e0c1a2b3d4f",
  "name": "sample-project.zip",
  "state": "done",
  "created_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "plans/flat-a.pdf",
      "size": 2263,
      "sha256": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
      "kind": "pdf_vector",
      "state": "ready",
      "reason": "read on the vector route: 7 elements, 5 rooms, scale scaled",
      "group": "plans/flat-a",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "drawing_id": "adeefbbcc17559fc",
      "reused": false,
      "takeoff": {
        "apartment": 1,
        "area:apartment": 52.27,
        "area:apartment|apartment=a": 52.27,
        "area:room": 64.714,
        "area:room:balcony|largest": 12.445,
        "area:room:bathroom|largest": 12.445,
        "area:room:kitchen|largest": 22.401,
        "area:room:other|largest": 14.934,
        "area:room:storage|largest": 2.489,
        "area:room|indoor": 52.269,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "area:room|label=küche": 22.401,
        "area:room|label=küche|largest": 22.401,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room|name=1.01": 22.401,
        "area:room|name=1.02": 2.489,
        "area:room|name=1.03": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=bad": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=küche": 22.401,
        "area:room|name=reduit": 2.489,
        "area:room|name=zimmer": 14.934,
        "bathtub": 1,
        "door": 2,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:kitchen": 7.056,
        "length:room:other": 4.233,
        "length:room:storage": 1.764,
        "length:room|name=1.01": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=1.03": 3.528,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=bad": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=reduit": 1.764,
        "length:room|name=zimmer": 4.233,
        "plan": 1,
        "room": 5,
        "room:balcony": 1,
        "room:bathroom": 1,
        "room:bedroom": 0,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 1,
        "room:outdoor": 0,
        "room:sauna": 0,
        "room:shaft": 0,
        "room:storage": 1,
        "room:wc": 0,
        "room|label=bad": 1,
        "room|label=balkon": 1,
        "room|label=küche": 1,
        "room|label=reduit": 1,
        "room|label=zimmer": 1,
        "shower": 0,
        "shower+bathtub": 1,
        "sink": 1,
        "toilet": 1,
        "window": 2
      },
      "ms": 12.5,
      "stage": "write",
      "cost_usd": 0.0,
      "normalised": null
    },
    {
      "id": "f2",
      "path": "plans/flat-a.png",
      "size": 21988,
      "sha256": "f73bc98a3ee5e771c83902a884a87038618c91d697d48033845f049a94edbb5f",
      "kind": "png_plan",
      "state": "ready",
      "reason": "read on the vector route: 7 elements, 5 rooms, scale scaled",
      "group": "plans/flat-a",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "drawing_id": "c9b719f715357201",
      "reused": false,
      "takeoff": {
        "apartment": 1,
        "area:apartment": 52.27,
        "area:apartment|apartment=a": 52.27,
        "area:room": 64.714,
        "area:room:balcony|largest": 12.445,
        "area:room:bathroom|largest": 12.445,
        "area:room:kitchen|largest": 22.401,
        "area:room:other|largest": 14.934,
        "area:room:storage|largest": 2.489,
        "area:room|indoor": 52.269,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "area:room|label=küche": 22.401,
        "area:room|label=küche|largest": 22.401,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room|name=1.01": 22.401,
        "area:room|name=1.02": 2.489,
        "area:room|name=1.03": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=bad": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=küche": 22.401,
        "area:room|name=reduit": 2.489,
        "area:room|name=zimmer": 14.934,
        "bathtub": 1,
        "door": 2,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:kitchen": 7.056,
        "length:room:other": 4.233,
        "length:room:storage": 1.764,
        "length:room|name=1.01": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=1.03": 3.528,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=bad": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=reduit": 1.764,
        "length:room|name=zimmer": 4.233,
        "plan": 1,
        "room": 5,
        "room:balcony": 1,
        "room:bathroom": 1,
        "room:bedroom": 0,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 1,
        "room:outdoor": 0,
        "room:sauna": 0,
        "room:shaft": 0,
        "room:storage": 1,
        "room:wc": 0,
        "room|label=bad": 1,
        "room|label=balkon": 1,
        "room|label=küche": 1,
        "room|label=reduit": 1,
        "room|label=zimmer": 1,
        "shower": 0,
        "shower+bathtub": 1,
        "sink": 1,
        "toilet": 1,
        "window": 2
      },
      "ms": 12.5,
      "stage": "write",
      "cost_usd": 0.0,
      "normalised": {
        "exif": null,
        "rotated": 0,
        "deskew_deg": 0.0,
        "rectified": false,
        "quad": null,
        "width": 1200,
        "height": 800,
        "rectifier": null
      }
    },
    {
      "id": "f3",
      "path": "plans/flat-b.pdf",
      "size": 2262,
      "sha256": "a7fce07de2895f481058912db6d1cd56d7e2f0e05cb3b38b4b6cfc3578726ab4",
      "kind": "pdf_vector",
      "state": "flagged",
      "reason": "1 conflict(s) between the two methods (room_area) (7 elements, 5 rooms, scale scaled)",
      "group": "plans/flat-b",
      "route": "vector",
      "source": "plans/flat-b.pdf",
      "drawing_id": "6d153ea15dca9ab4",
      "reused": false,
      "takeoff": {
        "apartment": 1,
        "area:apartment": 52.27,
        "area:apartment|apartment=a": 52.27,
        "area:room": 72.313,
        "area:room:balcony|largest": 12.445,
        "area:room:bathroom|largest": 12.445,
        "area:room:kitchen|largest": 30.0,
        "area:room:other|largest": 14.934,
        "area:room:storage|largest": 2.489,
        "area:room|indoor": 59.868,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "area:room|label=küche": 30.0,
        "area:room|label=küche|largest": 30.0,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room|name=1.01": 30.0,
        "area:room|name=1.02": 2.489,
        "area:room|name=1.03": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=bad": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=küche": 30.0,
        "area:room|name=reduit": 2.489,
        "area:room|name=zimmer": 14.934,
        "bathtub": 1,
        "door": 2,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:kitchen": 7.056,
        "length:room:other": 4.233,
        "length:room:storage": 1.764,
        "length:room|name=1.01": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=1.03": 3.528,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=bad": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=reduit": 1.764,
        "length:room|name=zimmer": 4.233,
        "plan": 1,
        "room": 5,
        "room:balcony": 1,
        "room:bathroom": 1,
        "room:bedroom": 0,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 1,
        "room:outdoor": 0,
        "room:sauna": 0,
        "room:shaft": 0,
        "room:storage": 1,
        "room:wc": 0,
        "room|label=bad": 1,
        "room|label=balkon": 1,
        "room|label=küche": 1,
        "room|label=reduit": 1,
        "room|label=zimmer": 1,
        "shower": 0,
        "shower+bathtub": 1,
        "sink": 1,
        "toilet": 1,
        "window": 2
      },
      "ms": 12.5,
      "stage": "write",
      "cost_usd": 0.0,
      "normalised": null
    }
  ],
  "counts": {
    "ready": 3,
    "flagged": 4,
    "set_aside": 2,
    "text_only": 2
  },
  "readers": {
    "bim": "ifc",
    "cad": "hello",
    "vector": "pdf",
    "raster": "hello",
    "raster_components": "",
    "tables": "pdf",
    "second_counter": "ifc",
    "rectifier": "none",
    "decisions_kind": "False"
  },
  "error": null,
  "ms": 12.5,
  "cost_usd": 0.0,
  "drawings": [
    {
      "drawing_id": "adeefbbcc17559fc",
      "group": "plans/flat-a",
      "file": "plans/flat-a.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "state": "ready",
      "other_renderings": [
        {
          "drawing_id": "c9b719f715357201",
          "file": "plans/flat-a.png"
        }
      ]
    },
    {
      "drawing_id": "6d153ea15dca9ab4",
      "group": "plans/flat-b",
      "file": "plans/flat-b.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-b.pdf",
      "state": "flagged",
      "other_renderings": []
    },
    {
      "drawing_id": "3b3ce7db34257f63",
      "group": "scans/ground-floor",
      "file": "scans/ground-floor.png",
      "kind": "png_plan",
      "route": "raster",
      "source": "scans/ground-floor.png",
      "state": "flagged",
      "other_renderings": [
        {
          "drawing_id": "3b3ce7db34257f63",
          "file": "scans/ground-floor-copy.png"
        }
      ]
    },
    {
      "drawing_id": "37f6819bd17d65d9",
      "group": "photos/plan-photo",
      "file": "photos/plan-photo.jpg",
      "kind": "photo_plan",
      "route": "raster",
      "source": "photos/plan-photo.jpg",
      "state": "flagged",
      "other_renderings": []
    },
    {
      "drawing_id": "1db9bcf1e67e27a3",
      "group": "model/house",
      "file": "model/house.ifc",
      "kind": "ifc",
      "route": "bim",
      "source": "model/house.ifc",
      "state": "ready",
      "other_renderings": []
    }
  ]
}
```

- Project `state`: `queued`, `running`, `done`, `failed`. `failed` only when ingest itself broke (e.g. not a
  readable zip), with `error` set; one bad file never fails the project, it becomes a `set_aside` file.
- File `kind`, by content: `pdf_vector`, `pdf_scan`, `pdf_text`, `png_plan`, `jpeg_plan`, `photo_plan`, `ifc`,
  `dxf`, `svg`, `text`, `photo`, `pdf_encrypted`, `dwg`, `office`, `archive`, `unknown`; null while the file is
  queued or when it was refused before it was read.
- File `state` (`reason` says why, once the file is finished):
  - `queued`, `running`: not finished yet.
  - `ready`: a drawing model was written (`drawing_id`), no conflict. Another rendering of a drawing (the PNG next
    to a PDF) is `ready` too, with the reason naming the file the drawing is read from.
  - `flagged`: a drawing model was written and needs a look: the two methods disagree, there is no reader for its
    route yet, a phone photo read without perspective correction, a scanned PDF.
  - `text_only`: text and no drawing (a spec PDF, a .txt).
  - `set_aside`: not ingested (unsafe path, zip bomb, not a drawing, a photo not of a plan, a DXF or SVG with no
    sheet next to it, a stage that failed).
- `route`: `bim`, `cad`, `vector`, `raster`, or null. `source`: the file the drawing was read from.
- `drawings`: one entry per plan, for the workspace's list. The files of one plan (same folder and name: a PDF and
  its PNG) are one group; its entry is the sheet the drawing was read from when that is a sheet, else PDF before
  PNG before JPEG; the group's other drawings are `other_renderings`. A copy of the same content under another
  name is listed once. An IFC model asked about on its own is an entry with no pages. An upload with no drawing
  gives `"drawings": []`.
- `stage`: the stage a running file is in, or the last one it finished, so the ingest screen needs no trace
  request per file. `cost_usd` on the project, each file and each stage: what the stage's model calls cost
  (Gemini Decisions in `identify` for the sheet kind and in `extract` for the count swap; a cached call costs
  0), 0.0 with no paid reader, which is the point to show. `normalised` on an image file: as on the drawing's page.
- A project a restart cut off is `failed` with `error` "the server restarted during ingest", its unfinished files
  `set_aside`: no screen polls it for ever.

A project while it runs (held after unpacking, its file queued), and the same project as the server finds it
after a restart cut that run off:

<!-- fixture: project_running.json -->
```json
{
  "id": "5e0c1a2b3d51",
  "name": "plan.pdf",
  "state": "running",
  "created_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "plan.pdf",
      "size": 2749,
      "sha256": "087bbbfbcc05f949a3dd1d2c7e9af861fba668f28449e8869b60f065bd15c755",
      "kind": "pdf_vector",
      "state": "queued",
      "reason": "",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 12.5,
      "stage": "identify",
      "cost_usd": 0.0,
      "normalised": null
    }
  ],
  "counts": {
    "queued": 1
  },
  "readers": {
    "bim": "ifc",
    "cad": "hello",
    "vector": "pdf",
    "raster": "hello",
    "raster_components": "",
    "tables": "pdf",
    "second_counter": "ifc",
    "rectifier": "none",
    "decisions_kind": "False"
  },
  "error": null,
  "ms": 12.5,
  "cost_usd": 0.0,
  "drawings": []
}
```

<!-- fixture: project_failed.json -->
```json
{
  "id": "5e0c1a2b3d51",
  "name": "plan.pdf",
  "state": "failed",
  "created_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "plan.pdf",
      "size": 2749,
      "sha256": "087bbbfbcc05f949a3dd1d2c7e9af861fba668f28449e8869b60f065bd15c755",
      "kind": "pdf_vector",
      "state": "set_aside",
      "reason": "not ingested: the server restarted during ingest",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 12.5,
      "stage": "identify",
      "cost_usd": 0.0,
      "normalised": null
    }
  ],
  "counts": {
    "set_aside": 1
  },
  "readers": {
    "bim": "ifc",
    "cad": "hello",
    "vector": "pdf",
    "raster": "hello",
    "raster_components": "",
    "tables": "pdf",
    "second_counter": "ifc",
    "rectifier": "none",
    "decisions_kind": "False"
  },
  "error": "the server restarted during ingest",
  "ms": 12.5,
  "cost_usd": 0.0,
  "drawings": []
}
```

### `GET /api/projects/{project_id}/files/{file_id}/trace`

<!-- fixture: trace.json -->
```json
{
  "project_id": "5e0c1a2b3d4f",
  "file": {
    "id": "f1",
    "path": "plans/flat-a.pdf",
    "size": 2263,
    "sha256": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
    "kind": "pdf_vector",
    "state": "ready",
    "reason": "read on the vector route: 7 elements, 5 rooms, scale scaled",
    "group": "plans/flat-a",
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "drawing_id": "adeefbbcc17559fc",
    "reused": false,
    "takeoff": {
      "apartment": 1,
      "area:apartment": 52.27,
      "area:apartment|apartment=a": 52.27,
      "area:room": 64.714,
      "area:room:balcony|largest": 12.445,
      "area:room:bathroom|largest": 12.445,
      "area:room:kitchen|largest": 22.401,
      "area:room:other|largest": 14.934,
      "area:room:storage|largest": 2.489,
      "area:room|indoor": 52.269,
      "area:room|label=bad": 12.445,
      "area:room|label=bad|largest": 12.445,
      "area:room|label=balkon": 12.445,
      "area:room|label=balkon|largest": 12.445,
      "area:room|label=küche": 22.401,
      "area:room|label=küche|largest": 22.401,
      "area:room|label=reduit": 2.489,
      "area:room|label=reduit|largest": 2.489,
      "area:room|label=zimmer": 14.934,
      "area:room|label=zimmer|largest": 14.934,
      "area:room|name=1.01": 22.401,
      "area:room|name=1.02": 2.489,
      "area:room|name=1.03": 12.445,
      "area:room|name=1.04": 12.445,
      "area:room|name=1.05": 14.934,
      "area:room|name=bad": 12.445,
      "area:room|name=balkon": 12.445,
      "area:room|name=küche": 22.401,
      "area:room|name=reduit": 2.489,
      "area:room|name=zimmer": 14.934,
      "bathtub": 1,
      "door": 2,
      "length:room:balcony": 7.056,
      "length:room:bathroom": 3.528,
      "length:room:kitchen": 7.056,
      "length:room:other": 4.233,
      "length:room:storage": 1.764,
      "length:room|name=1.01": 7.056,
      "length:room|name=1.02": 1.764,
      "length:room|name=1.03": 3.528,
      "length:room|name=1.04": 7.056,
      "length:room|name=1.05": 4.233,
      "length:room|name=bad": 3.528,
      "length:room|name=balkon": 7.056,
      "length:room|name=küche": 7.056,
      "length:room|name=reduit": 1.764,
      "length:room|name=zimmer": 4.233,
      "plan": 1,
      "room": 5,
      "room:balcony": 1,
      "room:bathroom": 1,
      "room:bedroom": 0,
      "room:hall": 0,
      "room:kitchen": 1,
      "room:living": 0,
      "room:other": 1,
      "room:outdoor": 0,
      "room:sauna": 0,
      "room:shaft": 0,
      "room:storage": 1,
      "room:wc": 0,
      "room|label=bad": 1,
      "room|label=balkon": 1,
      "room|label=küche": 1,
      "room|label=reduit": 1,
      "room|label=zimmer": 1,
      "shower": 0,
      "shower+bathtub": 1,
      "sink": 1,
      "toilet": 1,
      "window": 2
    },
    "ms": 12.5,
    "stage": "write",
    "cost_usd": 0.0,
    "normalised": null
  },
  "stages": [
    {
      "stage": "unpack",
      "did": "path checked, 2263 bytes",
      "ms": 12.5,
      "output": "plans/flat-a.pdf",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "hash",
      "did": "sha256 dd2c1cfd3ebb",
      "ms": 12.5,
      "output": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "identify",
      "did": "a drawn PDF (page 1 of 1: 18 paths, 0 images, 142 characters)",
      "ms": 12.5,
      "output": "pdf_vector",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "group",
      "did": "plans/flat-a: flat-a.pdf, flat-a.png",
      "ms": 12.5,
      "output": "2 file(s)",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "route",
      "did": "vector, read from plans/flat-a.pdf",
      "ms": 12.5,
      "output": "vector",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "normalise",
      "did": "1 page(s), page 1 is 600 x 400 pt",
      "ms": 12.5,
      "output": "1 page(s), page 1 is 600 x 400 pt",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "extract",
      "did": "7 elements, 5 rooms, 1 plans, scale scaled",
      "ms": 12.5,
      "output": "7 elements, 5 rooms, 1 plans, scale scaled",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "second_count",
      "did": "5 quantities measured twice, 0 conflict(s)",
      "ms": 12.5,
      "output": "5 quantities measured twice, 0 conflict(s)",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "takeoff",
      "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 71 quantities, 63 above zero",
      "ms": 12.5,
      "output": "takeoff: 71 quantities, 63 above zero",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "write",
      "did": "drawing model adeefbbcc17559fc stored",
      "ms": 12.5,
      "output": "71 quantities",
      "failure": null,
      "cost_usd": 0.0
    }
  ]
}
```

- `stage`: `unpack`, `hash`, `identify`, `group`, `route`, `cache`, `normalise`, `extract`, `second_count`,
  `takeoff` (the counting rules and the takeoff), `write` (docs/PIPELINE.md stages 1-10). The list grows while the
  file runs. `cache`: the drawing was ingested before; the stages of that first ingest follow it, with `ms` 0,
  up to its `write` when a drawing was stored then. A reused file's `stage` is the one its first ingest ended at
  (`write`, or `route` for a file set aside there), so the ingest screen counts it as on the first run.
- `did`: one readable line of what the stage did; `output`: what it produced; `ms`: its time.
- `failure`: set when the stage failed; the file then ends `set_aside` with this as its reason.

A file set aside at a stage that failed (a zip entry that would be written outside the project folder): the
stage carries `failure`, and later stages are not run:

<!-- fixture: trace_set_aside.json -->
```json
{
  "project_id": "5e0c1a2b3d50",
  "file": {
    "id": "f1",
    "path": "../outside.pdf",
    "size": 8,
    "sha256": null,
    "kind": null,
    "state": "set_aside",
    "reason": "unsafe path: it could be written outside the project folder",
    "group": null,
    "route": null,
    "source": null,
    "drawing_id": null,
    "reused": false,
    "takeoff": {},
    "ms": 12.5,
    "stage": "unpack",
    "cost_usd": 0.0,
    "normalised": null
  },
  "stages": [
    {
      "stage": "unpack",
      "did": "refused",
      "ms": 12.5,
      "output": "",
      "failure": "unsafe path: it could be written outside the project folder",
      "cost_usd": 0.0
    }
  ]
}
```

### `GET /api/projects/{project_id}/review`

What the end of ingest and the workspace's sidebar need without one takeoff request per drawing: per drawing how
many quantities are left to review and how many are signed off, and every conflict of the project.

<!-- fixture: project_review.json -->
```json
{
  "drawings": [
    {
      "drawing_id": "adeefbbcc17559fc",
      "file": "plans/flat-a.pdf",
      "to_review": 0,
      "signed": 0,
      "quantities": 63
    },
    {
      "drawing_id": "6d153ea15dca9ab4",
      "file": "plans/flat-b.pdf",
      "to_review": 2,
      "signed": 0,
      "quantities": 63
    },
    {
      "drawing_id": "3b3ce7db34257f63",
      "file": "scans/ground-floor.png",
      "to_review": 0,
      "signed": 0,
      "quantities": 0
    },
    {
      "drawing_id": "37f6819bd17d65d9",
      "file": "photos/plan-photo.jpg",
      "to_review": 0,
      "signed": 0,
      "quantities": 0
    },
    {
      "drawing_id": "1db9bcf1e67e27a3",
      "file": "model/house.ifc",
      "to_review": 0,
      "signed": 0,
      "quantities": 31
    }
  ],
  "conflicts": [
    {
      "drawing_id": "6d153ea15dca9ab4",
      "file": "plans/flat-b.pdf",
      "quantity": "area:room|name=1.01",
      "label": "area of room (name 1.01)",
      "conflict": {
        "values": [
          {
            "value": 22.401,
            "unit": "m2",
            "method": "polygon_x_scale",
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ]
          },
          {
            "value": 30.0,
            "unit": "m2",
            "method": "printed_label",
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ]
          }
        ],
        "resolution": {
          "rule": "the printed label over the outline at the sheet's scale",
          "value": 30.0
        },
        "note": null,
        "derived": null,
        "status": "conflict"
      },
      "settled": null,
      "needs_person": false
    }
  ]
}
```

`needs_person: true` marks a conflict no rule decides and nobody settled ("needs you"); the others were decided by
a rule ("AI decision") or settled by a surveyor.

## Drawings

### `GET /api/drawings/{drawing_id}?project=<project_id>`

A drawing id is its content, so the same plan uploaded under two names, in one project or in two, is one drawing.
Pass `project` (optional) from a screen inside a project: `file` and `reader.source` are then the names that
project uploaded, never another upload's. Without it they are the names the drawing was last stored under. A
project that does not hold the drawing is 404.

<!-- fixture: drawing.json -->
```json
{
  "id": "adeefbbcc17559fc",
  "file": "plans/flat-a.pdf",
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "pdf",
    "question_parser": "templates"
  },
  "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/adeefbbcc17559fc/pages/1.png",
      "normalised": null
    }
  ],
  "suggestions": [
    {
      "quantity": "area:room|indoor",
      "label": "area of room (indoor)",
      "question": "What is the net floor area of all indoor rooms in m²?"
    },
    {
      "quantity": "door",
      "label": "door count",
      "question": "How many doors are there?"
    },
    {
      "quantity": "window",
      "label": "window count",
      "question": "How many windows are there?"
    }
  ]
}
```

- `reader`: how the drawing was read: the route, the file it was read from (`source`), that route's reader
  (`extractor`; `hello` reads nothing; a sheet read with its IFC model is `ifc_sheet` with the sheet as `source`,
  since its counts are what the sheet draws and the model's count is the second count), the second counter that measured (`pdf` for any file that is no IFC
  model, since the `ifc` counter passes those on to the PDF one; `"none"` when it measured nothing on the
  drawing; in an answer, `"none"` unless it measured the answered quantity) and the question parser.
- `credit`: the licence credit to show under every page of the drawing, or null. A file of the Stoa
  dataset or a Commons demo photo is recognised by its content (whatever its upload name) and gets
  its line from the dataset's `data/<source>/LICENSE.md` or the photos' manifest; a user's own
  drawing gets null.
- `pages` is `[]` for an IFC model asked about on its own. `normalised` is null for a PDF page; for an image,
  `{"exif": 6, "rotated": 0, "deskew_deg": 0.0, "rectified": false, "quad": null, "width": 3024, "height": 4032}`:
  the EXIF orientation of the upload, the turn and deskew made after it, and `quad`, the paper's four corners in
  the upload as fractions of it, once the photo rectifier is plugged in (null today).
- `suggestions`: questions this drawing answers, up to six: a count of each schedule the sheet prints first,
  then areas, lengths and volumes (the building model's totals included), then counts, one per quantity with a
  value. Each is checked against the question parser when it is made, so asking it is never refused. A
  schedule's suggestion has the schedule query as `quantity` (`table:count:door`).

### `GET /api/drawings/{drawing_id}/model`

The drawing model as an extraction_v1 document (`eval/schemas/extraction_v1.schema.json`, decision 0004 and its
amendments): `scale`, `plans`, `elements` (`id`, `class`, `page`, `box`, optional `polygon`), `rooms` (`label`,
`area_m2`, `polygon`), `apartments`, `tables`, `conflicts`, `read`, `model_objects`, `notes`. An optional list the
drawing has none of is left out. For a sheet with an IFC model behind it this is every object of the building,
so fetch it only to show the model, not for the page size.

### `GET /api/drawings/{drawing_id}/pages/{n}.png?width=<400|1600|3200>`

The page as PNG (`image/png`), in the page frame (see Conventions): a PDF page rasterised, an image sheet
re-encoded. `width` is 400 (thumbnail), 1600 (view, the default) or 3200 (zoom); the aspect ratio is kept, and a
page that would be over 16 megapixels is scaled down. Marks are not drawn in. `Cache-Control: public,
max-age=31536000, immutable`: a drawing id is a content hash, so its pages never change. 404 for a page the
drawing does not have.

### `GET /api/projects/{project_id}/files/{file_id}/preview.png?width=`

The file as uploaded with only its EXIF turn applied, so the screen can show a phone photo before and after
normalisation. Images and a PDF's first page; 404 for any other file. `width` as for pages.

## Answering

### `POST /api/ask`

<!-- fixture: ask_request.json -->
```json
{
  "drawing_id": "adeefbbcc17559fc",
  "question": "How many doors are there?"
}
```

`question` is 1 to 2000 characters. `project_id` (optional) names the project the question is asked in: the
answer's `file` and `reader.source` are then that project's names, as for `GET /api/drawings/{id}?project=`, and
the review edits and sign-offs applied ("Verified by …") are that project's. The response carries the takeoff row the value was read from, in the same
shape as `GET …/takeoff` gives it, so one component shows both:

<!-- fixture: answer.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "adeefbbcc17559fc",
  "file": "plans/flat-a.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/adeefbbcc17559fc/pages/1.png",
      "normalised": null
    }
  ],
  "answer": 2,
  "unit": "count",
  "confidence": null,
  "quantity": {
    "key": "door",
    "label": "door count",
    "measure": "count",
    "subject": "door",
    "scope": {
      "storey": null,
      "label": null,
      "name": null,
      "apartment": null,
      "indoor": false,
      "model": false,
      "largest": false
    },
    "value": 2,
    "unit": "count",
    "original_value": 2,
    "status": "single",
    "needs_person": false,
    "rule": {
      "id": "each-once",
      "text": "every element, room and plan the drawing lists counts once"
    },
    "estimate": null,
    "first": null,
    "second": null,
    "conflict": null,
    "settled": null,
    "marks": [
      {
        "id": "m1",
        "n": 1,
        "page": 1,
        "box": [
          0.49333,
          0.225,
          0.50667,
          0.275
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "door",
        "ref": "e1",
        "reason": null
      },
      {
        "id": "m2",
        "n": 2,
        "page": 1,
        "box": [
          0.66,
          0.225,
          0.67333,
          0.275
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "door",
        "ref": "e2",
        "reason": null
      }
    ],
    "signed": null,
    "unlocated": {}
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.49333,
        0.225,
        0.50667,
        0.275
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "door",
      "ref": "e1",
      "reason": null
    },
    {
      "id": "m2",
      "n": 2,
      "page": 1,
      "box": [
        0.66,
        0.225,
        0.67333,
        0.275
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "door",
      "ref": "e2",
      "reason": null
    }
  ],
  "refusal": null,
  "method": "takeoff",
  "explanation": null,
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 2,
    "unit": "count",
    "evidence": [
      {
        "file": "plans/flat-a.pdf",
        "page": 1,
        "box": [
          0.49333,
          0.225,
          0.50667,
          0.275
        ]
      },
      {
        "file": "plans/flat-a.pdf",
        "page": 1,
        "box": [
          0.66,
          0.225,
          0.67333,
          0.275
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "count",
    "legend": [
      {
        "label": "door",
        "colour": "#d62728",
        "count": 2,
        "unlocated": 0,
        "note": null
      }
    ],
    "arithmetic": null,
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": null
  }
}
```

- `answer`, `unit`: the value to show. It is the row's current `value`, so a surveyor's edits show here
  (`quantity.original_value` is what ingest computed). Null on a refusal: the screen shows no number.
- `confidence`: a raw score the pipeline gives the answer, named for what it is: `signal` (`g1main`: Gemini
  Decisions' choice distribution for the answered count, on when the server runs with
  `DECISIONS_CONFIDENCE=true`), `score` (0 to 1) and `calibrated` (false: the score was not checked against
  right answers, so it is **not** a probability that the answer is right; a correct 4-bedroom answer scored
  0.38). Don't show it as one: the proof and `evidence.png` leave it out. A "sure" badge comes later from
  golden's gate thresholds. Only a drawing read on the raster route is scored (Decisions reads images). Null
  when it is off, for other routes, when there is no score (the reason is in `explanation`), or on a
  refusal. `line.confidence` carries the same raw score, because the scorer's answer_v1.1 line has that
  field.
- `quantity`: the takeoff row (see below), with its `rule`, `status`, `first`/`second`, `conflict`, `estimate`,
  `settled` and `signed` (the engineer view shows "verified by Ana" from `signed`). Null for a refusal and for an
  answer read from a schedule.
- `marks`: the evidence to draw, the row's marks; for a schedule answer one mark per row read (`e1`, `e2`…) and
  `answer` may be a string with `unit` null.
- `pages`: the drawing's pages, so the viewer needs no second request.
- `method`: `takeoff`, `schedule`, or `refused:<why>` / `prior:policy` on a refusal. `explanation`: how the value
  was reached, for a "details" view.
- `cost_usd`, `latency_s`: of this answer. A takeoff lookup costs 0: no model call at question time, except the
  Decisions answer confidence when its page was not read at ingest (then its call's cost).
- `line` is the exact answer_v1.1 line (decision 0002, `eval/schemas/answer_v1.schema.json`) as the scorer reads
  it, from the pipeline's own reading: edits never change it. On a refusal it may hold the dev prior's estimate.
- `proof`: what to draw as the answer's proof (docs/GOLDEN.md "What an answer should show"); `evidence.png`
  draws the same. `kind` is `count`, `sum`, `model`, `schedule` or `none` (a refusal).
  - `legend`: one entry per class (count) or room label (sum) among the marks not rejected: `label`, `colour`
    (in a count fixed per class, so a door is the same red in every answer; in a sum the labels take the palette
    in order, so no two share one) and `count` (its counted marks). A count can include items a second reader
    counted with no position of their own (decide's count swap): they are in `count` and in `unlocated`, never
    drawn as marks, and `note` says so in words for the legend (`2 counted without a mark (second reader)`;
    null when there are none).
  - `arithmetic`: how the parts make the answer, in one line: the classes of a count of several
    (`2 shower + 1 bathtub = 3`), a sum's parts and what the rule left out, a model fact's object count, a
    schedule's rows. Null for a count of one class (its numbered marks say it) and on a refusal. A count of
    rooms has one key named by what is counted (`bedroom`), not one per printed room name, and no arithmetic.
  - `objects` (kind `model`): the building model's objects the answer counted or summed, with `global_id`,
    `name` and `storey`. Null when the list would not be exactly what was counted.
  - `storeys` (kind `model`): the model's storeys in its order, with how many objects of each class each has.
  - `schedule` (kind `schedule`): the table (`table` id, `title`, `page`, `box`, `columns`), the `rows` the answer
    rests on with their `cells` and `n`, and `of`, the rows the table has.
  - `check`: how a second, independent method checked the value, in one line, e.g. `Checked twice, they
    disagree: the sheet 72, the IFC model 86; kept 72: count what the sheet draws`, or `Checked twice, both
    agree: …`. Null when one method measured it.

A door count on an image read on the raster route, with `DECISIONS_CONFIDENCE` on (the example's score comes
from a stand-in, not Gemini; `marks` trimmed to two):

<!-- fixture: answer_confidence.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "2b4e04cde84fbbef",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/2b4e04cde84fbbef/pages/1.png",
      "normalised": {
        "exif": null,
        "rotated": 0,
        "deskew_deg": 0.0,
        "rectified": false,
        "quad": null,
        "width": 800,
        "height": 400,
        "rectifier": null
      }
    }
  ],
  "answer": 2,
  "unit": "count",
  "confidence": {
    "signal": "g1main",
    "score": 0.87,
    "calibrated": false
  },
  "quantity": {
    "key": "door",
    "label": "door count",
    "measure": "count",
    "subject": "door",
    "scope": {
      "storey": null,
      "label": null,
      "name": null,
      "apartment": null,
      "indoor": false,
      "model": false,
      "largest": false
    },
    "value": 2,
    "unit": "count",
    "original_value": 2,
    "status": "single",
    "needs_person": false,
    "rule": {
      "id": "each-once",
      "text": "every element, room and plan the drawing lists counts once"
    },
    "estimate": null,
    "first": null,
    "second": null,
    "conflict": null,
    "settled": null,
    "marks": [
      {
        "id": "m1",
        "n": 1,
        "page": 1,
        "box": [
          0.05,
          0.1,
          0.1,
          0.2
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "door",
        "ref": "e1",
        "reason": null
      },
      {
        "id": "m2",
        "n": 2,
        "page": 1,
        "box": [
          0.6,
          0.1,
          0.65,
          0.2
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "door",
        "ref": "e2",
        "reason": null
      }
    ],
    "signed": null,
    "unlocated": {}
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.05,
        0.1,
        0.1,
        0.2
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "door",
      "ref": "e1",
      "reason": null
    },
    {
      "id": "m2",
      "n": 2,
      "page": 1,
      "box": [
        0.6,
        0.1,
        0.65,
        0.2
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "door",
      "ref": "e2",
      "reason": null
    }
  ],
  "refusal": null,
  "method": "takeoff",
  "explanation": null,
  "reader": {
    "route": "raster",
    "source": "plan.png",
    "extractor": "composite",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 2,
    "unit": "count",
    "evidence": [
      {
        "file": "plan.png",
        "page": 1,
        "box": [
          0.05,
          0.1,
          0.1,
          0.2
        ]
      },
      {
        "file": "plan.png",
        "page": 1,
        "box": [
          0.6,
          0.1,
          0.65,
          0.2
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": 0.87,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "count",
    "legend": [
      {
        "label": "door",
        "colour": "#d62728",
        "count": 2,
        "unlocated": 0,
        "note": null
      }
    ],
    "arithmetic": null,
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": null
  }
}
```

### `GET /api/drawings/{drawing_id}/evidence.png?question=<text>&width=<400|1600|3200>&project=<project_id>`

The answer to `question` (as `POST /api/ask` gives it, the edits of `project` applied, if given) with its `proof` drawn on the page the marks
are on: counted marks outlined in their class colour and numbered, a sum's rooms filled with their values,
excluded items greyed with their reason, a schedule's rows highlighted; under the page the question and answer,
the `arithmetic`, the `check` line, the colour key (with the legend's `note`) and the
licence `credit`. A model fact with no page is drawn as its objects
(GlobalIds) and storey table. A refusal is drawn with its text. It is the fallback when a screen can't draw the
proof itself, and a picture to share. `Cache-Control: no-store`, since a review edit changes it. Errors as
`pages/{n}.png`: 422 for another width or no `question`, 404 for an unknown drawing.

A sum of rooms, with the item the rule left out (`marks` trimmed to two here):

<!-- fixture: answer_area.json -->
```json
{
  "question": "What is the net floor area of all indoor rooms in m²?",
  "drawing_id": "adeefbbcc17559fc",
  "file": "plans/flat-a.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/adeefbbcc17559fc/pages/1.png",
      "normalised": null
    }
  ],
  "answer": 52.269,
  "unit": "m2",
  "confidence": null,
  "quantity": {
    "key": "area:room|indoor",
    "label": "area of room (indoor)",
    "measure": "area",
    "subject": "room",
    "scope": {
      "storey": null,
      "label": null,
      "name": null,
      "apartment": null,
      "indoor": true,
      "model": false,
      "largest": false
    },
    "value": 52.269,
    "unit": "m2",
    "original_value": 52.269,
    "status": "single",
    "needs_person": false,
    "rule": {
      "id": "indoor-rooms-total",
      "text": "every room that is not outdoor; shafts, lifts and stairwells stay in, as the dataset's answers do although the question says shafts are left out"
    },
    "estimate": null,
    "first": null,
    "second": null,
    "conflict": null,
    "settled": null,
    "marks": [
      {
        "id": "m1",
        "n": 1,
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ],
        "polygon": [
          [
            0.16667,
            0.125
          ],
          [
            0.16667,
            0.375
          ],
          [
            0.5,
            0.375
          ],
          [
            0.5,
            0.125
          ]
        ],
        "state": "counted",
        "value": 22.401,
        "label": "Küche",
        "ref": "r1",
        "reason": null
      },
      {
        "id": "m2",
        "n": 2,
        "page": 1,
        "box": [
          0.25,
          0.2,
          0.33333,
          0.3
        ],
        "polygon": [
          [
            0.25,
            0.2
          ],
          [
            0.25,
            0.3
          ],
          [
            0.33333,
            0.3
          ],
          [
            0.33333,
            0.2
          ]
        ],
        "state": "counted",
        "value": 2.489,
        "label": "Reduit",
        "ref": "r2",
        "reason": null
      }
    ],
    "signed": null,
    "unlocated": {}
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.16667,
        0.125,
        0.5,
        0.375
      ],
      "polygon": [
        [
          0.16667,
          0.125
        ],
        [
          0.16667,
          0.375
        ],
        [
          0.5,
          0.375
        ],
        [
          0.5,
          0.125
        ]
      ],
      "state": "counted",
      "value": 22.401,
      "label": "Küche",
      "ref": "r1",
      "reason": null
    },
    {
      "id": "m2",
      "n": 2,
      "page": 1,
      "box": [
        0.25,
        0.2,
        0.33333,
        0.3
      ],
      "polygon": [
        [
          0.25,
          0.2
        ],
        [
          0.25,
          0.3
        ],
        [
          0.33333,
          0.3
        ],
        [
          0.33333,
          0.2
        ]
      ],
      "state": "counted",
      "value": 2.489,
      "label": "Reduit",
      "ref": "r2",
      "reason": null
    }
  ],
  "refusal": null,
  "method": "takeoff",
  "explanation": null,
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 52.269,
    "unit": "m2",
    "evidence": [
      {
        "file": "plans/flat-a.pdf",
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ]
      },
      {
        "file": "plans/flat-a.pdf",
        "page": 1,
        "box": [
          0.25,
          0.2,
          0.33333,
          0.3
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "sum",
    "legend": [
      {
        "label": "Küche",
        "colour": "#d62728",
        "count": 1,
        "unlocated": 0,
        "note": null
      },
      {
        "label": "Reduit",
        "colour": "#1f77b4",
        "count": 1,
        "unlocated": 0,
        "note": null
      },
      {
        "label": "Bad",
        "colour": "#2ca02c",
        "count": 1,
        "unlocated": 0,
        "note": null
      },
      {
        "label": "Zimmer",
        "colour": "#9467bd",
        "count": 1,
        "unlocated": 0,
        "note": null
      },
      {
        "label": "Balkon",
        "colour": "#ff7f0e",
        "count": 0,
        "unlocated": 0,
        "note": null
      }
    ],
    "arithmetic": "22.4 + 2.49 + 12.45 + 14.93 = 52.27 m²; left out: Balkon 12.45 (outdoor room)",
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": null
  }
}
```

A fact of the building model behind a drawing (an IFC model asked about on its own has no page, so no marks):

<!-- fixture: answer_model.json -->
```json
{
  "question": "How many doors are shown on the floor plan of 'Ground Floor'?",
  "drawing_id": "1db9bcf1e67e27a3",
  "file": "model/house.ifc",
  "pages": [],
  "answer": 2,
  "unit": "count",
  "confidence": null,
  "quantity": {
    "key": "door|storey=ground floor",
    "label": "door count (storey ground floor)",
    "measure": "count",
    "subject": "door",
    "scope": {
      "storey": "ground floor",
      "label": null,
      "name": null,
      "apartment": null,
      "indoor": false,
      "model": false,
      "largest": false
    },
    "value": 2,
    "unit": "count",
    "original_value": 2,
    "status": "single",
    "needs_person": false,
    "rule": {
      "id": "model-objects",
      "text": "every object of the building model counts once, whether this sheet draws it or not"
    },
    "estimate": null,
    "first": null,
    "second": null,
    "conflict": null,
    "settled": null,
    "marks": [],
    "signed": null,
    "unlocated": {}
  },
  "marks": [],
  "refusal": null,
  "method": "takeoff",
  "explanation": null,
  "reader": {
    "route": "bim",
    "source": "model/house.ifc",
    "extractor": "ifc",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 2,
    "unit": "count",
    "evidence": [],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "model",
    "legend": [],
    "arithmetic": "2 door objects in the model on Ground floor",
    "objects": [
      {
        "id": "m1",
        "class": "door",
        "name": "Door 1",
        "storey": "Ground floor",
        "global_id": "000000000000000000000K"
      },
      {
        "id": "m2",
        "class": "door",
        "name": "Door 2",
        "storey": "Ground floor",
        "global_id": "000000000000000000000M"
      }
    ],
    "storeys": [
      {
        "storey": "Ground floor",
        "counts": {
          "door": 2,
          "slab": 1,
          "space": 2,
          "wall": 4,
          "window": 3
        }
      }
    ],
    "schedule": null,
    "check": null
  }
}
```

A question the drawing cannot answer:

<!-- fixture: answer_refused.json -->
```json
{
  "question": "What colour is the roof?",
  "drawing_id": "adeefbbcc17559fc",
  "file": "plans/flat-a.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/adeefbbcc17559fc/pages/1.png",
      "normalised": null
    }
  ],
  "answer": null,
  "unit": null,
  "confidence": null,
  "quantity": null,
  "marks": [],
  "refusal": {
    "code": "unsupported-question",
    "text": "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.",
    "can_answer": [
      {
        "quantity": "area:room|indoor",
        "label": "area of room (indoor)",
        "question": "What is the net floor area of all indoor rooms in m²?"
      },
      {
        "quantity": "door",
        "label": "door count",
        "question": "How many doors are there?"
      }
    ]
  },
  "method": "refused:unsupported-question",
  "explanation": "no count, area, length or volume asked for",
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": null,
    "unit": null,
    "evidence": [],
    "method": "refused:unsupported-question",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": true,
    "explanation": "no count, area, length or volume asked for",
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "none",
    "legend": [],
    "arithmetic": null,
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": null
  }
}
```

`refusal.code`:

| Code | When |
| --- | --- |
| `unsupported-question` | the question is not one the parser turns into a count, area, length or volume |
| `not-in-drawing` | the drawing does not give this quantity (or no schedule on the sheet answers it) |
| `not-read` | the reader of this drawing does not look for that class, so it has no count of it |
| `no-reader` | nothing was read from the sheet (no reader for its route yet), that reader is less reliable than a guess for this kind of question (`prior:policy`), or the page was flagged at upload (a phone photo, a scan) and its reader found no element or no room at all for what was asked: 0 would be a guess |
| `no-scale` | an area or length on a sheet without a scale |
| `no-drawing` | the file has no drawing model |

`refusal.text` is written for the person at the screen. `can_answer` lists up to six questions this drawing
answers, as `suggestions` on the drawing does.

An answer whose quantity two methods measured differently (`quantity.conflict`, `proof.check`), on the sample's
`plans/flat-b.pdf`; `marks` trimmed to two:

<!-- fixture: answer_conflict.json -->
```json
{
  "question": "What is the area of room 1.01?",
  "drawing_id": "6d153ea15dca9ab4",
  "file": "plans/flat-b.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/6d153ea15dca9ab4/pages/1.png",
      "normalised": null
    }
  ],
  "answer": 30.0,
  "unit": "m2",
  "confidence": null,
  "quantity": {
    "key": "area:room|name=1.01",
    "label": "area of room (name 1.01)",
    "measure": "area",
    "subject": "room",
    "scope": {
      "storey": null,
      "label": null,
      "name": "1.01",
      "apartment": null,
      "indoor": false,
      "model": false,
      "largest": false
    },
    "value": 30.0,
    "unit": "m2",
    "original_value": 30.0,
    "status": "conflict",
    "needs_person": false,
    "rule": {
      "id": "room-area",
      "text": "the room's net floor area as the drawing gives it"
    },
    "estimate": null,
    "first": {
      "method": "polygon_x_scale",
      "value": 22.401
    },
    "second": {
      "method": "printed_label",
      "value": 30.0
    },
    "conflict": {
      "values": [
        {
          "value": 22.401,
          "unit": "m2",
          "method": "polygon_x_scale",
          "page": 1,
          "box": [
            0.16667,
            0.125,
            0.5,
            0.375
          ]
        },
        {
          "value": 30.0,
          "unit": "m2",
          "method": "printed_label",
          "page": 1,
          "box": [
            0.17367,
            0.17946,
            0.21269,
            0.19027
          ]
        }
      ],
      "resolution": {
        "rule": "the printed label over the outline at the sheet's scale",
        "value": 30.0
      },
      "note": null,
      "derived": null,
      "status": "conflict"
    },
    "settled": null,
    "marks": [
      {
        "id": "m1",
        "n": 1,
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ],
        "polygon": [
          [
            0.16667,
            0.125
          ],
          [
            0.16667,
            0.375
          ],
          [
            0.5,
            0.375
          ],
          [
            0.5,
            0.125
          ]
        ],
        "state": "counted",
        "value": 30.0,
        "label": "Küche",
        "ref": "r1",
        "reason": null
      }
    ],
    "signed": null,
    "unlocated": {}
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.16667,
        0.125,
        0.5,
        0.375
      ],
      "polygon": [
        [
          0.16667,
          0.125
        ],
        [
          0.16667,
          0.375
        ],
        [
          0.5,
          0.375
        ],
        [
          0.5,
          0.125
        ]
      ],
      "state": "counted",
      "value": 30.0,
      "label": "Küche",
      "ref": "r1",
      "reason": null
    }
  ],
  "refusal": null,
  "method": "takeoff",
  "explanation": "two methods disagree (the room outlines at the sheet's scale 22.401, the printed room areas 30); kept 30: the printed label over the outline at the sheet's scale",
  "reader": {
    "route": "vector",
    "source": "plans/flat-b.pdf",
    "extractor": "pdf",
    "second_counter": "pdf",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 30.0,
    "unit": "m2",
    "evidence": [
      {
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": "two methods disagree (the room outlines at the sheet's scale 22.401, the printed room areas 30); kept 30: the printed label over the outline at the sheet's scale",
    "estimate": null,
    "conflicts": [
      {
        "value": 22.401,
        "unit": "m2",
        "method": "polygon_x_scale",
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ]
      },
      {
        "value": 30.0,
        "unit": "m2",
        "method": "printed_label",
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.17367,
          0.17946,
          0.21269,
          0.19027
        ]
      }
    ],
    "resolution": "kept 30: the printed label over the outline at the sheet's scale"
  },
  "proof": {
    "kind": "sum",
    "legend": [
      {
        "label": "Küche",
        "colour": "#d62728",
        "count": 1,
        "unlocated": 0,
        "note": null
      }
    ],
    "arithmetic": null,
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": "Checked twice, they disagree: the room outlines at the sheet's scale 22.4 m², the printed room areas 30 m²; kept 30 m²: the printed label over the outline at the sheet's scale"
  }
}
```

The same question after the quantity was signed off (`quantity.status` `signed`, `quantity.signed`):

<!-- fixture: answer_signed.json -->
```json
{
  "question": "What is the area of room 1.01?",
  "drawing_id": "6d153ea15dca9ab4",
  "file": "plans/flat-b.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/6d153ea15dca9ab4/pages/1.png",
      "normalised": null
    }
  ],
  "answer": 30.0,
  "unit": "m2",
  "confidence": null,
  "quantity": {
    "key": "area:room|name=1.01",
    "label": "area of room (name 1.01)",
    "measure": "area",
    "subject": "room",
    "scope": {
      "storey": null,
      "label": null,
      "name": "1.01",
      "apartment": null,
      "indoor": false,
      "model": false,
      "largest": false
    },
    "value": 30.0,
    "unit": "m2",
    "original_value": 30.0,
    "status": "signed",
    "needs_person": false,
    "rule": {
      "id": "room-area",
      "text": "the room's net floor area as the drawing gives it"
    },
    "estimate": null,
    "first": {
      "method": "polygon_x_scale",
      "value": 22.401
    },
    "second": {
      "method": "printed_label",
      "value": 30.0
    },
    "conflict": {
      "values": [
        {
          "value": 22.401,
          "unit": "m2",
          "method": "polygon_x_scale",
          "page": 1,
          "box": [
            0.16667,
            0.125,
            0.5,
            0.375
          ]
        },
        {
          "value": 30.0,
          "unit": "m2",
          "method": "printed_label",
          "page": 1,
          "box": [
            0.17367,
            0.17946,
            0.21269,
            0.19027
          ]
        }
      ],
      "resolution": {
        "rule": "the printed label over the outline at the sheet's scale",
        "value": 30.0
      },
      "note": null,
      "derived": null,
      "status": "conflict"
    },
    "settled": null,
    "marks": [
      {
        "id": "m1",
        "n": 1,
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ],
        "polygon": [
          [
            0.16667,
            0.125
          ],
          [
            0.16667,
            0.375
          ],
          [
            0.5,
            0.375
          ],
          [
            0.5,
            0.125
          ]
        ],
        "state": "counted",
        "value": 30.0,
        "label": "Küche",
        "ref": "r1",
        "reason": null
      }
    ],
    "signed": {
      "by": "Ana",
      "at": "2026-11-14T08:05:00Z",
      "value": 30.0
    },
    "unlocated": {}
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.16667,
        0.125,
        0.5,
        0.375
      ],
      "polygon": [
        [
          0.16667,
          0.125
        ],
        [
          0.16667,
          0.375
        ],
        [
          0.5,
          0.375
        ],
        [
          0.5,
          0.125
        ]
      ],
      "state": "counted",
      "value": 30.0,
      "label": "Küche",
      "ref": "r1",
      "reason": null
    }
  ],
  "refusal": null,
  "method": "takeoff",
  "explanation": "two methods disagree (the room outlines at the sheet's scale 22.401, the printed room areas 30); kept 30: the printed label over the outline at the sheet's scale",
  "reader": {
    "route": "vector",
    "source": "plans/flat-b.pdf",
    "extractor": "pdf",
    "second_counter": "pdf",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": 30.0,
    "unit": "m2",
    "evidence": [
      {
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": "two methods disagree (the room outlines at the sheet's scale 22.401, the printed room areas 30); kept 30: the printed label over the outline at the sheet's scale",
    "estimate": null,
    "conflicts": [
      {
        "value": 22.401,
        "unit": "m2",
        "method": "polygon_x_scale",
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.16667,
          0.125,
          0.5,
          0.375
        ]
      },
      {
        "value": 30.0,
        "unit": "m2",
        "method": "printed_label",
        "file": "plans/flat-b.pdf",
        "page": 1,
        "box": [
          0.17367,
          0.17946,
          0.21269,
          0.19027
        ]
      }
    ],
    "resolution": "kept 30: the printed label over the outline at the sheet's scale"
  },
  "proof": {
    "kind": "sum",
    "legend": [
      {
        "label": "Küche",
        "colour": "#d62728",
        "count": 1,
        "unlocated": 0,
        "note": null
      }
    ],
    "arithmetic": null,
    "objects": null,
    "storeys": null,
    "schedule": null,
    "check": "Checked twice, they disagree: the room outlines at the sheet's scale 22.4 m², the printed room areas 30 m²; kept 30 m²: the printed label over the outline at the sheet's scale"
  }
}
```

A cell read from a door schedule: a string `answer`, `unit` null, `proof.kind` `schedule` with the row it
rests on:

<!-- fixture: answer_schedule.json -->
```json
{
  "question": "What are the width and height of door 111.B?",
  "drawing_id": "5c4ed01e00000001",
  "file": "doors.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/5c4ed01e00000001/pages/1.png",
      "normalised": null
    }
  ],
  "answer": "2'-8\" wide x 7'-0\" high",
  "unit": null,
  "confidence": null,
  "quantity": null,
  "marks": [
    {
      "id": "e1",
      "n": 1,
      "page": 1,
      "box": [
        0.03333,
        0.2225,
        0.53333,
        0.2525
      ],
      "polygon": null,
      "state": "counted",
      "value": null,
      "label": null,
      "ref": null,
      "reason": null
    }
  ],
  "refusal": null,
  "method": "schedule",
  "explanation": null,
  "reader": {
    "route": "vector",
    "source": "doors.pdf",
    "extractor": "pdf",
    "second_counter": "none",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "line": {
    "id": 1,
    "answer": "2'-8\" wide x 7'-0\" high",
    "unit": null,
    "evidence": [
      {
        "file": "doors.pdf",
        "page": 1,
        "box": [
          0.03333,
          0.2225,
          0.53333,
          0.2525
        ]
      }
    ],
    "method": "schedule",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": null,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  },
  "proof": {
    "kind": "schedule",
    "legend": [],
    "arithmetic": "1 of the 3 rows of DOOR SCHEDULE",
    "objects": null,
    "storeys": null,
    "schedule": {
      "table": "t1",
      "title": "DOOR SCHEDULE",
      "page": 1,
      "box": [
        0.03333,
        0.05,
        0.53333,
        0.2525
      ],
      "columns": [
        "Mark",
        "Door Width",
        "Door Height",
        "Matl",
        "Notes"
      ],
      "rows": [
        {
          "n": 1,
          "box": [
            0.03333,
            0.2225,
            0.53333,
            0.2525
          ],
          "cells": [
            "111.B",
            "2'-8\"",
            "7'-0\"",
            "AL-1",
            "A, B"
          ]
        }
      ],
      "of": 3
    },
    "check": null
  }
}
```

## Takeoff and review (surveyor)

### `GET /api/drawings/{drawing_id}/takeoff?zeros=<bool>&project=<project_id>`

`project` (optional, also on `review`, `signoff` and `takeoff.csv`): `file`, the CSV's `drawing` column and its
file name are then the names that project uploaded, as for `GET /api/drawings/{id}?project=`, and the review
edits and sign-offs read and written are that project's only. Without it they are the drawing's state outside
any project, which no project shows. A project that does not hold the drawing is 404.

<!-- fixture: takeoff.json -->
```json
{
  "drawing_id": "6d153ea15dca9ab4",
  "file": "plans/flat-b.pdf",
  "quantities": [
    {
      "key": "area:room|name=1.01",
      "label": "area of room (name 1.01)",
      "measure": "area",
      "subject": "room",
      "scope": {
        "storey": null,
        "label": null,
        "name": "1.01",
        "apartment": null,
        "indoor": false,
        "model": false,
        "largest": false
      },
      "value": 30.0,
      "unit": "m2",
      "original_value": 30.0,
      "status": "conflict",
      "needs_person": false,
      "rule": {
        "id": "room-area",
        "text": "the room's net floor area as the drawing gives it"
      },
      "estimate": null,
      "first": {
        "method": "polygon_x_scale",
        "value": 22.401
      },
      "second": {
        "method": "printed_label",
        "value": 30.0
      },
      "conflict": {
        "values": [
          {
            "value": 22.401,
            "unit": "m2",
            "method": "polygon_x_scale",
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ]
          },
          {
            "value": 30.0,
            "unit": "m2",
            "method": "printed_label",
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ]
          }
        ],
        "resolution": {
          "rule": "the printed label over the outline at the sheet's scale",
          "value": 30.0
        },
        "note": null,
        "derived": null,
        "status": "conflict"
      },
      "settled": null,
      "marks": [
        {
          "id": "m1",
          "n": 1,
          "page": 1,
          "box": [
            0.16667,
            0.125,
            0.5,
            0.375
          ],
          "polygon": [
            [
              0.16667,
              0.125
            ],
            [
              0.16667,
              0.375
            ],
            [
              0.5,
              0.375
            ],
            [
              0.5,
              0.125
            ]
          ],
          "state": "counted",
          "value": 30.0,
          "label": "Küche",
          "ref": "r1",
          "reason": null
        }
      ],
      "signed": null,
      "unlocated": {}
    },
    {
      "key": "door",
      "label": "door count",
      "measure": "count",
      "subject": "door",
      "scope": {
        "storey": null,
        "label": null,
        "name": null,
        "apartment": null,
        "indoor": false,
        "model": false,
        "largest": false
      },
      "value": 2,
      "unit": "count",
      "original_value": 2,
      "status": "single",
      "needs_person": false,
      "rule": {
        "id": "each-once",
        "text": "every element, room and plan the drawing lists counts once"
      },
      "estimate": null,
      "first": null,
      "second": null,
      "conflict": null,
      "settled": null,
      "marks": [
        {
          "id": "m1",
          "n": 1,
          "page": 1,
          "box": [
            0.49333,
            0.225,
            0.50667,
            0.275
          ],
          "polygon": null,
          "state": "counted",
          "value": 1.0,
          "label": "door",
          "ref": "e1",
          "reason": null
        },
        {
          "id": "m2",
          "n": 2,
          "page": 1,
          "box": [
            0.66,
            0.225,
            0.67333,
            0.275
          ],
          "polygon": null,
          "state": "counted",
          "value": 1.0,
          "label": "door",
          "ref": "e2",
          "reason": null
        }
      ],
      "signed": null,
      "unlocated": {}
    },
    {
      "key": "area:room|indoor",
      "label": "area of room (indoor)",
      "measure": "area",
      "subject": "room",
      "scope": {
        "storey": null,
        "label": null,
        "name": null,
        "apartment": null,
        "indoor": true,
        "model": false,
        "largest": false
      },
      "value": 59.868,
      "unit": "m2",
      "original_value": 59.868,
      "status": "single",
      "needs_person": false,
      "rule": {
        "id": "indoor-rooms-total",
        "text": "every room that is not outdoor; shafts, lifts and stairwells stay in, as the dataset's answers do although the question says shafts are left out"
      },
      "estimate": null,
      "first": null,
      "second": null,
      "conflict": null,
      "settled": null,
      "marks": [
        {
          "id": "m1",
          "n": 1,
          "page": 1,
          "box": [
            0.16667,
            0.125,
            0.5,
            0.375
          ],
          "polygon": [
            [
              0.16667,
              0.125
            ],
            [
              0.16667,
              0.375
            ],
            [
              0.5,
              0.375
            ],
            [
              0.5,
              0.125
            ]
          ],
          "state": "counted",
          "value": 30.0,
          "label": "Küche",
          "ref": "r1",
          "reason": null
        },
        {
          "id": "m2",
          "n": 2,
          "page": 1,
          "box": [
            0.25,
            0.2,
            0.33333,
            0.3
          ],
          "polygon": [
            [
              0.25,
              0.2
            ],
            [
              0.25,
              0.3
            ],
            [
              0.33333,
              0.3
            ],
            [
              0.33333,
              0.2
            ]
          ],
          "state": "counted",
          "value": 2.489,
          "label": "Reduit",
          "ref": "r2",
          "reason": null
        }
      ],
      "signed": null,
      "unlocated": {}
    }
  ],
  "review_queue": [
    "area:room|name=1.01",
    "area:room|name=küche"
  ]
}
```

- One row per takeoff key, in the takeoff's order, which stays the same across calls and edits;
  `review_queue` carries the ranking. Without `zeros=true`, a row whose value is 0 and that nothing happened to
  (no conflict, estimate, edit or sign-off) is left out.
- `label`: a readable name made from the key (`door count`, `area of room (indoor)`). `measure`, `subject` and
  `scope` are the key's parts, so the screen can group rows without parsing keys.
- `first`, `second`: the drawing's own reading and the independent method's value (ingest stage 8). Set when
  two methods measured it, whether they agree or not; null when one method measured it.
- `conflict`: every method's value and the rule that kept one (`resolution`; null: no rule decides). Null when the
  methods agree or only one measured it.
- `status`, ranked: `signed` (signed off), `conflict` (methods disagree, not settled), `estimate` (rests on an
  estimated scale or reading, not settled; on `/api/ask`, every row of a page flagged at upload as a phone photo
  or a scan, with the flag in `estimate`), `edited` (a review changed it), `agree` (two methods agree), `single`
  (one method).
- `needs_person`: the methods disagree, no rule decides and nobody settled it. Such a row can't be signed off.
- `settled`: the value a surveyor chose with `settle`, and when.
- `marks`: one per counted item (count) or per room in the sum (area), in the order the screen numbers them.
  - `n`: the number to draw, null for a mark that is not counted.
  - `state`: `counted`, `rejected` (by a surveyor), `added` (by a surveyor), `excluded` (left out by the counting
    rule, with `reason`, e.g. the balcony of an indoor area: draw it greyed). Excluded marks come after the
    counted ones, with ids `x1`, `x2`…; one a surveyor counts in with `restore` is `counted` and keeps its
    `reason`.
  - `value`: the item's share of the total: 1 in a count, the room's m2 in an area, null when unknown.
  - `label`: the room's printed label (else its type) or the element class; `ref`: the element or room id in the
    drawing model; `polygon`: the room's outline when the model has one (else draw the box). All three are null
    for an added mark.
- `unlocated`: per element class, the items of a count a second reader counted with no position of their own
  (decide's count swap adds them with `attrs.located` false). They are in `value` but have no mark; empty when
  there are none.
- `review_queue`: the keys whose status is `conflict` or `estimate`.
- `value` is the current value (after review); `original_value` what ingest computed.

### `POST /api/drawings/{drawing_id}/review?zeros=<bool>`

On a sheet of one storey a disagreement sits on the sheet's row and on that storey's row ("window" and
"window|storey=p1", the same values): it is one disagreement. An edit or sign-off sent for the storey's row is made
on the sheet's row, and the storey's row shows the sheet row's edits, settled value and sign-off (K4).

One edit per call; the response is the whole takeoff (as `GET …/takeoff`), so the screen replaces its state. The
edits, in order: reject, restore, add, settle, reset one quantity, reset the whole drawing:

<!-- fixture: review_requests.json -->
```json
[
  {
    "quantity": "door",
    "action": "reject",
    "mark": "m2"
  },
  {
    "quantity": "door",
    "action": "restore",
    "mark": "m2"
  },
  {
    "quantity": "door",
    "action": "add",
    "page": 1,
    "box": [
      0.2,
      0.5,
      0.23,
      0.53
    ]
  },
  {
    "quantity": "door",
    "action": "settle",
    "value": 3
  },
  {
    "quantity": "door",
    "action": "reset"
  },
  {
    "action": "reset"
  }
]
```

- `reject` / `restore`: leave a mark out of the count or the sum, or put it back. Rejecting an added mark removes
  it. `restore` on an `excluded` mark (`x1`…) counts it in; `reject` on it leaves it out again.
- `add`: a missed item, on a count only. The new mark gets an id `a1`, `a2`…
- `settle`: the value to keep (one of the conflict's values, or any value the surveyor counted). It holds until
  the next mark edit of that quantity.
- `reset`: undo every edit, settled value and sign-off of the quantity; without `quantity`, of every quantity of
  the drawing.
- Recount: the ingest value minus the rejected marks' values plus the added ones'. A sum with a mark of unknown
  value is not recounted: only `settle` changes it.
- An edit changes that quantity only: rejecting a mark of `shower` does not change `shower+bathtub`, nor the same
  door under `door|storey=1`.
- A signed-off quantity is not edited: 409 until the sign-off is undone (or the quantity reset).
- Edits are kept on disk per drawing id and survive a restart; the same drawing in another project shows them.

### `POST /api/drawings/{drawing_id}/signoff?zeros=<bool>`

<!-- fixture: signoff_request.json -->
```json
{
  "quantity": "door",
  "by": "Ana"
}
```

Signs off the quantity's current value: its row gets `"status": "signed"` and `"signed": {"by", "at", "value"}`.
Returns the whole takeoff. A row with `needs_person: true` answers 409: settle it first. `"undo": true` removes the
sign-off.

The takeoff of `plans/flat-b.pdf` after review calls (door `m1` rejected and a door added, the window count
settled at 3, the conflicting room area signed off by Ana), trimmed to those three rows:

<!-- fixture: takeoff_edited.json -->
```json
{
  "drawing_id": "6d153ea15dca9ab4",
  "file": "plans/flat-b.pdf",
  "quantities": [
    {
      "key": "door",
      "label": "door count",
      "measure": "count",
      "subject": "door",
      "scope": {
        "storey": null,
        "label": null,
        "name": null,
        "apartment": null,
        "indoor": false,
        "model": false,
        "largest": false
      },
      "value": 2,
      "unit": "count",
      "original_value": 2,
      "status": "edited",
      "needs_person": false,
      "rule": {
        "id": "each-once",
        "text": "every element, room and plan the drawing lists counts once"
      },
      "estimate": null,
      "first": null,
      "second": null,
      "conflict": null,
      "settled": null,
      "marks": [
        {
          "id": "m1",
          "n": null,
          "page": 1,
          "box": [
            0.49333,
            0.225,
            0.50667,
            0.275
          ],
          "polygon": null,
          "state": "rejected",
          "value": 1.0,
          "label": "door",
          "ref": "e1",
          "reason": null
        },
        {
          "id": "m2",
          "n": 1,
          "page": 1,
          "box": [
            0.66,
            0.225,
            0.67333,
            0.275
          ],
          "polygon": null,
          "state": "counted",
          "value": 1.0,
          "label": "door",
          "ref": "e2",
          "reason": null
        },
        {
          "id": "a1",
          "n": 2,
          "page": 1,
          "box": [
            0.2,
            0.5,
            0.23,
            0.53
          ],
          "polygon": null,
          "state": "added",
          "value": 1.0,
          "label": null,
          "ref": null,
          "reason": null
        }
      ],
      "signed": null,
      "unlocated": {}
    },
    {
      "key": "window",
      "label": "window count",
      "measure": "count",
      "subject": "window",
      "scope": {
        "storey": null,
        "label": null,
        "name": null,
        "apartment": null,
        "indoor": false,
        "model": false,
        "largest": false
      },
      "value": 3,
      "unit": "count",
      "original_value": 2,
      "status": "edited",
      "needs_person": false,
      "rule": {
        "id": "each-once",
        "text": "every element, room and plan the drawing lists counts once"
      },
      "estimate": null,
      "first": null,
      "second": null,
      "conflict": null,
      "settled": {
        "value": 3,
        "at": "2026-11-14T08:05:00Z"
      },
      "marks": [
        {
          "id": "m1",
          "n": 1,
          "page": 1,
          "box": [
            0.2,
            0.115,
            0.3,
            0.13
          ],
          "polygon": null,
          "state": "counted",
          "value": 1.0,
          "label": "window",
          "ref": "e3",
          "reason": null
        },
        {
          "id": "m2",
          "n": 2,
          "page": 1,
          "box": [
            0.71667,
            0.115,
            0.81667,
            0.13
          ],
          "polygon": null,
          "state": "counted",
          "value": 1.0,
          "label": "window",
          "ref": "e4",
          "reason": null
        }
      ],
      "signed": null,
      "unlocated": {}
    },
    {
      "key": "area:room|name=1.01",
      "label": "area of room (name 1.01)",
      "measure": "area",
      "subject": "room",
      "scope": {
        "storey": null,
        "label": null,
        "name": "1.01",
        "apartment": null,
        "indoor": false,
        "model": false,
        "largest": false
      },
      "value": 30.0,
      "unit": "m2",
      "original_value": 30.0,
      "status": "signed",
      "needs_person": false,
      "rule": {
        "id": "room-area",
        "text": "the room's net floor area as the drawing gives it"
      },
      "estimate": null,
      "first": {
        "method": "polygon_x_scale",
        "value": 22.401
      },
      "second": {
        "method": "printed_label",
        "value": 30.0
      },
      "conflict": {
        "values": [
          {
            "value": 22.401,
            "unit": "m2",
            "method": "polygon_x_scale",
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ]
          },
          {
            "value": 30.0,
            "unit": "m2",
            "method": "printed_label",
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ]
          }
        ],
        "resolution": {
          "rule": "the printed label over the outline at the sheet's scale",
          "value": 30.0
        },
        "note": null,
        "derived": null,
        "status": "conflict"
      },
      "settled": null,
      "marks": [
        {
          "id": "m1",
          "n": 1,
          "page": 1,
          "box": [
            0.16667,
            0.125,
            0.5,
            0.375
          ],
          "polygon": [
            [
              0.16667,
              0.125
            ],
            [
              0.16667,
              0.375
            ],
            [
              0.5,
              0.375
            ],
            [
              0.5,
              0.125
            ]
          ],
          "state": "counted",
          "value": 30.0,
          "label": "Küche",
          "ref": "r1",
          "reason": null
        }
      ],
      "signed": {
        "by": "Ana",
        "at": "2026-11-14T08:05:00Z",
        "value": 30.0
      },
      "unlocated": {}
    }
  ],
  "review_queue": [
    "area:room|name=küche"
  ]
}
```

### `GET /api/drawings/{drawing_id}/takeoff.csv?zeros=<bool>`

`text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="<file stem>-takeoff.csv"`. One row per
quantity, the same rows as the takeoff:

```csv
drawing,key,label,value,unit,status,original_value,first_method,first_value,second_method,second_value,settled_value,rule,estimate,signed_by,signed_at
plans/flat-b.pdf,door,door count,2,count,signed,2,,,,,,each-once,,Ana,2026-11-14T01:40:00Z
```

A text cell that starts with `=`, `+`, `-` or `@` is written with a leading `'`, so a room label can't run as a
formula in a spreadsheet.

## What is not in v1

- Contested marks: a conflict is shown per quantity, with both values and, where the method has one, the `box` it
  read; the frontend does not build an amber per-item mark.
- Adding a mark with a value to an area or length (marks are added to counts only).
- A question on a whole project: ask one drawing at a time.
- Free page widths, CORS, server push (progress is polled).
- Editing a room's outline or label.

## Changelog

- 2026-11-14, text: a dataset drawing's `credit` is the attribution once, with its licence named once and no
  "<licence>. Credit:" of its own (the screen writes "Credit: "; R3-qa2-1). `proof.arithmetic` is null for a sum of
  one part (was "30 = 30 m²"; a settled one keeps "settled by a person, was …"). `explanation` names the two
  methods of a disagreement in words ("the sheet 4, the IFC model 8", was "plan_drawing 4, ifc_model 8").
- 2026-11-14, additive (wording): `reader` of a sheet read with its IFC model (bim route, not the model itself)
  is `extractor: "ifc_sheet"` with the sheet as `source` (was `ifc` and the .ifc), so the card names the sheet
  for the shown count and the model as the second count (R3-qa-5-1).
- 2026-11-14, additive (behaviour): review edits and sign-offs belong to the project (R1b-4-1). With `project`
  (takeoff, review, signoff, takeoff.csv, the new optional `project` on `evidence.png`) or `project_id` (ask)
  they are that project's; without one, a drawing-level state no project sees. Edits stored before this change
  were per drawing and are now that no-project state (not migrated). `reader.second_counter` names the counter
  that measured: the IFC counter passes every file that is no model to the PDF one, so a PDF or image reads
  `pdf` (was `ifc`) (R2-qa4-1, R2-qa-1-2). `cost_usd` (stage, file, project, answer) now records the Gemini
  Decisions calls it was 0.0 for (R1b-4-2).
- 2026-11-14, additive: on a sheet of one storey, an edit or sign-off of a storey row that carries the sheet row's
  disagreement is made on the sheet's row, and the storey row shows its edits (K4). `POST /api/ask` answers the
  area of a room asked by a printed name the parser has no word for ("the Reduit"), "how big/large" as an area,
  storage rooms and "how many plans" (R2-2-3).
- 2026-11-14, text: the sample archive's drawing `credit` reads "Synthetic drawing made for this demo by the
  Hour49 team; no partner data" (it named a repo path, `backend/scripts/make_sample_archive.py`).
- 2026-11-14, additive: a method a path does not take is `405 method-not-allowed` (it was `405 error`, a
  code this page did not list); the errors table lists it and `500 internal`. A project's drawing entry now lists
  every file with the same content as `other_renderings` (two identical files were one drawing shown under one
  name, the other name dropped). `GET /api/drawings/{id}?project=` and `POST /api/ask` `project_id` (both optional)
  name the drawing as that project uploaded it (R1-3-6, R1-4-4: a drawing reused from the cache showed the earlier
  upload's name).
- 2026-11-14, text: `proof.arithmetic` and `proof.check` write areas and volumes as m² and m³ (were m2, m3).
- 2026-11-14, additive: `project` (optional) on `GET …/takeoff`, `POST …/review`, `POST …/signoff` and
  `GET …/takeoff.csv` names the drawing as that project uploaded it (R1-4-4, R1-3-6 in the surveyor).
- 2026-11-14, breaking: `POST /api/ask` `confidence` was a number and is now an object `{signal, score,
  calibrated}` (or null), and `proof.confidence` is removed. The number was Gemini's raw choice score, not a
  probability that the answer is right, so it is kept only under a name that says so. `line.confidence`
  (answer_v1.1) is unchanged.
- 2026-11-14, additive: `proof.check`, `proof.legend[].unlocated` and `.note`, takeoff rows' `unlocated`,
  schedule and building-model `suggestions`, `info.no_keys` computed from the readers.
- 2026-11-14, additive: drawing `credit` for the sample archive's files is now "Synthetic drawing made by code
  (backend/scripts/make_sample_archive.py); no partner data" instead of null. New example fixtures:
  `answer_conflict`, `answer_signed`, `answer_schedule`, `takeoff_edited`, `error_not_allowed`,
  `trace_set_aside`, `project_running`, `project_failed`.
