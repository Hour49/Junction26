# HTTP API (v1, 2026-11-14)

The backend's HTTP API for the frontend: upload a project, follow its ingest, read drawings, ask questions,
review and sign off a takeoff. It serves stories #27, #31, #32 and #33. The server is `backend/` (FastAPI,
decision 0001), routes in `backend/app/api/`. Decision record: [0007](decisions/0007-http-api.md).

**One source of truth.** Every route declares a pydantic response model, so `/openapi.json` describes every
response (`npx openapi-typescript http://localhost:8000/openapi.json -o src/api.d.ts` gives the TypeScript types).
Every JSON example below is a file in `backend/tests/fixtures/api_v1/`, made from real responses on the synthetic
sample archive (`backend/tests/api/make_fixtures.py`) and trimmed to a few rows. `tests/api/test_api_fixtures.py`
fails when a fixture no longer fits its model or this page no longer quotes it as it is. The frontend can use the
same files as mock data.

Items marked **waits on core** are agreed, and the field is in the shape already, but it is null or empty until
core's part lands.

## Conventions

- Every endpoint is under `/api`, except `GET /health`. In development the Vite dev server proxies `/api` to
  `http://localhost:8000` (`server.proxy` in `vite.config.ts`), so the frontend calls relative URLs. The backend
  sets no CORS (docs/ENGINEERING.md §1).
- JSON in and out, UTF-8. Times are ISO 8601 in UTC. Ingest objects give durations in milliseconds (`ms`), answers
  in seconds (`latency_s`, as answer_v1 does); money is US dollars (`cost_usd`).
- Ids are opaque: a project id is 12 hex chars, a file id `f1`, `f2`… (unique within its project), a drawing id
  16 hex chars. An id that does not have its pattern is answered 404, like an unknown one. A drawing id is a hash
  of the drawing's content and readers: the same drawing uploaded again, in any project, has the same id, and its
  review edits and sign-offs show there too.
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
| A project whose ingest broke | 200, `state: "failed"`, `error` set |
| A photo with no plan, a lone DXF | 200, `state: "done"`, the file `set_aside` with its reason, `drawings: []` |
| A question the drawing cannot answer | 200, `refusal` set |

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
    "second_counter": "ifc",
    "question_parser": "templates",
    "answer_prior": "none"
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

`no_keys: true` when no reader needs an API key or a model server (true for every reader today): the screen
shows "running offline". A reader named `hello` reads nothing: drawings on that route have no counts, and their
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
  "id": "49b25e214855",
  "name": "sample-project.zip",
  "state": "done",
  "url": "/api/projects/49b25e214855"
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
every review edit and sign-off of the drawings of the last sample project, so each run of the demo starts clean.
Without it a second sample run is all `reused: true`.

### `GET /api/projects`

Every project, newest first: open one ingested earlier when a live ingest is slow.

<!-- fixture: project_list.json -->
```json
{
  "projects": [
    {
      "id": "49b25e214855",
      "name": "sample-project.zip",
      "state": "done",
      "created_at": "2026-11-14T00:58:34+00:00",
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
  "id": "49b25e214855",
  "name": "sample-project.zip",
  "state": "done",
  "created_at": "2026-11-14T00:58:34+00:00",
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
      "drawing_id": "1562846cb3da6f1c",
      "reused": false,
      "takeoff": {
        "door": 2,
        "window": 2,
        "toilet": 1,
        "sink": 1,
        "shower": 0,
        "bathtub": 1,
        "room:bedroom": 0,
        "room:kitchen": 1,
        "room:bathroom": 1,
        "room:wc": 0,
        "room:sauna": 0,
        "room:balcony": 1,
        "room:living": 0,
        "room:hall": 0,
        "room:storage": 1,
        "room:outdoor": 0,
        "room:shaft": 0,
        "room:other": 1,
        "plan": 1,
        "shower+bathtub": 1,
        "room": 5,
        "area:room": 64.714,
        "area:room|indoor": 52.269,
        "room|label=küche": 1,
        "area:room|label=küche": 22.401,
        "area:room|label=küche|largest": 22.401,
        "room|label=reduit": 1,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "room|label=bad": 1,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "room|label=balkon": 1,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "room|label=zimmer": 1,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room:kitchen|largest": 22.401,
        "area:room:storage|largest": 2.489,
        "area:room:bathroom|largest": 12.445,
        "area:room:balcony|largest": 12.445,
        "area:room:other|largest": 14.934,
        "area:room|name=1.01": 22.401,
        "area:room|name=küche": 22.401,
        "area:room|name=1.02": 2.489,
        "area:room|name=reduit": 2.489,
        "area:room|name=bad": 12.445,
        "area:room|name=1.03": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=zimmer": 14.934,
        "apartment": 1,
        "area:apartment|apartment=a": 52.27,
        "area:apartment": 52.27,
        "length:room|name=1.01": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=reduit": 1.764,
        "length:room|name=bad": 3.528,
        "length:room|name=1.03": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=zimmer": 4.233,
        "length:room:kitchen": 7.056,
        "length:room:storage": 1.764,
        "length:room:bathroom": 3.528,
        "length:room:balcony": 7.056,
        "length:room:other": 4.233
      },
      "ms": 9.908825493766926,
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
      "drawing_id": "0ad894dffcdf541d",
      "reused": false,
      "takeoff": {
        "door": 2,
        "window": 2,
        "toilet": 1,
        "sink": 1,
        "shower": 0,
        "bathtub": 1,
        "room:bedroom": 0,
        "room:kitchen": 1,
        "room:bathroom": 1,
        "room:wc": 0,
        "room:sauna": 0,
        "room:balcony": 1,
        "room:living": 0,
        "room:hall": 0,
        "room:storage": 1,
        "room:outdoor": 0,
        "room:shaft": 0,
        "room:other": 1,
        "plan": 1,
        "shower+bathtub": 1,
        "room": 5,
        "area:room": 64.714,
        "area:room|indoor": 52.269,
        "room|label=küche": 1,
        "area:room|label=küche": 22.401,
        "area:room|label=küche|largest": 22.401,
        "room|label=reduit": 1,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "room|label=bad": 1,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "room|label=balkon": 1,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "room|label=zimmer": 1,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room:kitchen|largest": 22.401,
        "area:room:storage|largest": 2.489,
        "area:room:bathroom|largest": 12.445,
        "area:room:balcony|largest": 12.445,
        "area:room:other|largest": 14.934,
        "area:room|name=1.01": 22.401,
        "area:room|name=küche": 22.401,
        "area:room|name=1.02": 2.489,
        "area:room|name=reduit": 2.489,
        "area:room|name=bad": 12.445,
        "area:room|name=1.03": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=zimmer": 14.934,
        "apartment": 1,
        "area:apartment|apartment=a": 52.27,
        "area:apartment": 52.27,
        "length:room|name=1.01": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=reduit": 1.764,
        "length:room|name=bad": 3.528,
        "length:room|name=1.03": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=zimmer": 4.233,
        "length:room:kitchen": 7.056,
        "length:room:storage": 1.764,
        "length:room:bathroom": 3.528,
        "length:room:balcony": 7.056,
        "length:room:other": 4.233
      },
      "ms": 22.97267947869841,
      "stage": "write",
      "cost_usd": 0.0,
      "normalised": {
        "exif": null,
        "rotated": 0,
        "deskew_deg": 0.0,
        "rectified": false,
        "quad": null,
        "width": 1200,
        "height": 800
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
      "drawing_id": "0f2705085f870f02",
      "reused": false,
      "takeoff": {
        "door": 2,
        "window": 2,
        "toilet": 1,
        "sink": 1,
        "shower": 0,
        "bathtub": 1,
        "room:bedroom": 0,
        "room:kitchen": 1,
        "room:bathroom": 1,
        "room:wc": 0,
        "room:sauna": 0,
        "room:balcony": 1,
        "room:living": 0,
        "room:hall": 0,
        "room:storage": 1,
        "room:outdoor": 0,
        "room:shaft": 0,
        "room:other": 1,
        "plan": 1,
        "shower+bathtub": 1,
        "room": 5,
        "area:room": 72.313,
        "area:room|indoor": 59.868,
        "room|label=küche": 1,
        "area:room|label=küche": 30.0,
        "area:room|label=küche|largest": 30.0,
        "room|label=reduit": 1,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "room|label=bad": 1,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "room|label=balkon": 1,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "room|label=zimmer": 1,
        "area:room|label=zimmer": 14.934,
        "area:room|label=zimmer|largest": 14.934,
        "area:room:kitchen|largest": 30.0,
        "area:room:storage|largest": 2.489,
        "area:room:bathroom|largest": 12.445,
        "area:room:balcony|largest": 12.445,
        "area:room:other|largest": 14.934,
        "area:room|name=1.01": 30.0,
        "area:room|name=küche": 30.0,
        "area:room|name=1.02": 2.489,
        "area:room|name=reduit": 2.489,
        "area:room|name=bad": 12.445,
        "area:room|name=1.03": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 14.934,
        "area:room|name=zimmer": 14.934,
        "apartment": 1,
        "area:apartment|apartment=a": 52.27,
        "area:apartment": 52.27,
        "length:room|name=1.01": 7.056,
        "length:room|name=küche": 7.056,
        "length:room|name=1.02": 1.764,
        "length:room|name=reduit": 1.764,
        "length:room|name=bad": 3.528,
        "length:room|name=1.03": 3.528,
        "length:room|name=balkon": 7.056,
        "length:room|name=1.04": 7.056,
        "length:room|name=1.05": 4.233,
        "length:room|name=zimmer": 4.233,
        "length:room:kitchen": 7.056,
        "length:room:storage": 1.764,
        "length:room:bathroom": 3.528,
        "length:room:balcony": 7.056,
        "length:room:other": 4.233
      },
      "ms": 8.706738008186221,
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
    "tables": "off",
    "second_counter": "ifc"
  },
  "error": null,
  "ms": 114.7662150033284,
  "cost_usd": 0.0,
  "drawings": [
    {
      "drawing_id": "1562846cb3da6f1c",
      "group": "plans/flat-a",
      "file": "plans/flat-a.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "state": "ready",
      "other_renderings": [
        {
          "drawing_id": "0ad894dffcdf541d",
          "file": "plans/flat-a.png"
        }
      ]
    },
    {
      "drawing_id": "0f2705085f870f02",
      "group": "plans/flat-b",
      "file": "plans/flat-b.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-b.pdf",
      "state": "flagged",
      "other_renderings": []
    },
    {
      "drawing_id": "1e6fbfcee953228b",
      "group": "scans/ground-floor",
      "file": "scans/ground-floor.png",
      "kind": "png_plan",
      "route": "raster",
      "source": "scans/ground-floor.png",
      "state": "flagged",
      "other_renderings": []
    },
    {
      "drawing_id": "30791510236578c9",
      "group": "photos/plan-photo",
      "file": "photos/plan-photo.jpg",
      "kind": "photo_plan",
      "route": "raster",
      "source": "photos/plan-photo.jpg",
      "state": "flagged",
      "other_renderings": []
    },
    {
      "drawing_id": "48e1aa3450dff526",
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
  request per file. `cost_usd` on the project, each file and each stage: 0.0 with no paid reader, which is the
  point to show. `normalised` on an image file: as on the drawing's page.
- A project a restart cut off is `failed` with `error` "the server restarted during ingest", its unfinished files
  `set_aside`: no screen polls it for ever.

### `GET /api/projects/{project_id}/files/{file_id}/trace`

<!-- fixture: trace.json -->
```json
{
  "project_id": "49b25e214855",
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
    "drawing_id": "1562846cb3da6f1c",
    "reused": false,
    "takeoff": {
      "door": 2,
      "window": 2,
      "toilet": 1,
      "sink": 1,
      "shower": 0,
      "bathtub": 1,
      "room:bedroom": 0,
      "room:kitchen": 1,
      "room:bathroom": 1,
      "room:wc": 0,
      "room:sauna": 0,
      "room:balcony": 1,
      "room:living": 0,
      "room:hall": 0,
      "room:storage": 1,
      "room:outdoor": 0,
      "room:shaft": 0,
      "room:other": 1,
      "plan": 1,
      "shower+bathtub": 1,
      "room": 5,
      "area:room": 64.714,
      "area:room|indoor": 52.269,
      "room|label=küche": 1,
      "area:room|label=küche": 22.401,
      "area:room|label=küche|largest": 22.401,
      "room|label=reduit": 1,
      "area:room|label=reduit": 2.489,
      "area:room|label=reduit|largest": 2.489,
      "room|label=bad": 1,
      "area:room|label=bad": 12.445,
      "area:room|label=bad|largest": 12.445,
      "room|label=balkon": 1,
      "area:room|label=balkon": 12.445,
      "area:room|label=balkon|largest": 12.445,
      "room|label=zimmer": 1,
      "area:room|label=zimmer": 14.934,
      "area:room|label=zimmer|largest": 14.934,
      "area:room:kitchen|largest": 22.401,
      "area:room:storage|largest": 2.489,
      "area:room:bathroom|largest": 12.445,
      "area:room:balcony|largest": 12.445,
      "area:room:other|largest": 14.934,
      "area:room|name=1.01": 22.401,
      "area:room|name=küche": 22.401,
      "area:room|name=1.02": 2.489,
      "area:room|name=reduit": 2.489,
      "area:room|name=bad": 12.445,
      "area:room|name=1.03": 12.445,
      "area:room|name=balkon": 12.445,
      "area:room|name=1.04": 12.445,
      "area:room|name=1.05": 14.934,
      "area:room|name=zimmer": 14.934,
      "apartment": 1,
      "area:apartment|apartment=a": 52.27,
      "area:apartment": 52.27,
      "length:room|name=1.01": 7.056,
      "length:room|name=küche": 7.056,
      "length:room|name=1.02": 1.764,
      "length:room|name=reduit": 1.764,
      "length:room|name=bad": 3.528,
      "length:room|name=1.03": 3.528,
      "length:room|name=balkon": 7.056,
      "length:room|name=1.04": 7.056,
      "length:room|name=1.05": 4.233,
      "length:room|name=zimmer": 4.233,
      "length:room:kitchen": 7.056,
      "length:room:storage": 1.764,
      "length:room:bathroom": 3.528,
      "length:room:balcony": 7.056,
      "length:room:other": 4.233
    },
    "ms": 9.908825493766926,
    "stage": "write",
    "cost_usd": 0.0,
    "normalised": null
  },
  "stages": [
    {
      "stage": "unpack",
      "did": "path checked, 2263 bytes",
      "ms": 0.683862017467618,
      "output": "plans/flat-a.pdf",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "hash",
      "did": "sha256 dd2c1cfd3ebb",
      "ms": 0.03342298441566527,
      "output": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "identify",
      "did": "a drawn PDF (page 1 of 1: 18 paths, 0 images, 142 characters)",
      "ms": 1.9600449886638671,
      "output": "pdf_vector",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "group",
      "did": "plans/flat-a: flat-a.pdf, flat-a.png",
      "ms": 0.007779497536830604,
      "output": "2 file(s)",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "route",
      "did": "vector, read from plans/flat-a.pdf",
      "ms": 0.0,
      "output": "vector",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "normalise",
      "did": "1 page(s), page 1 is 600 x 400 pt",
      "ms": 1.018344977637753,
      "output": "1 page(s), page 1 is 600 x 400 pt",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "extract",
      "did": "7 elements, 5 rooms, 1 plans, scale scaled",
      "ms": 3.064143005758524,
      "output": "7 elements, 5 rooms, 1 plans, scale scaled",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "second_count",
      "did": "5 quantities measured twice, 0 conflict(s)",
      "ms": 1.9115940085612237,
      "output": "5 quantities measured twice, 0 conflict(s)",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "takeoff",
      "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 71 quantities, 63 above zero",
      "ms": 0.7033589936327189,
      "output": "takeoff: 71 quantities, 63 above zero",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "write",
      "did": "drawing model 1562846cb3da6f1c stored",
      "ms": 0.5262750200927258,
      "output": "71 quantities",
      "failure": null,
      "cost_usd": 0.0
    }
  ]
}
```

- `stage`: `unpack`, `hash`, `identify`, `group`, `route`, `cache`, `normalise`, `extract`, `second_count`,
  `takeoff` (the counting rules and the takeoff), `write` (docs/PIPELINE.md stages 1-10). The list grows while the
  file runs. `cache`: the drawing was ingested before; the stages of that first ingest follow it, with `ms` 0.
- `did`: one readable line of what the stage did; `output`: what it produced; `ms`: its time.
- `failure`: set when the stage failed; the file then ends `set_aside` with this as its reason.

### `GET /api/projects/{project_id}/review`

What the end of ingest and the workspace's sidebar need without one takeoff request per drawing: per drawing how
many quantities are left to review and how many are signed off, and every conflict of the project.

<!-- fixture: project_review.json -->
```json
{
  "drawings": [
    {
      "drawing_id": "1562846cb3da6f1c",
      "file": "plans/flat-a.pdf",
      "to_review": 0,
      "signed": 0,
      "quantities": 63
    },
    {
      "drawing_id": "0f2705085f870f02",
      "file": "plans/flat-b.pdf",
      "to_review": 2,
      "signed": 0,
      "quantities": 63
    },
    {
      "drawing_id": "1e6fbfcee953228b",
      "file": "scans/ground-floor.png",
      "to_review": 0,
      "signed": 0,
      "quantities": 0
    },
    {
      "drawing_id": "30791510236578c9",
      "file": "photos/plan-photo.jpg",
      "to_review": 0,
      "signed": 0,
      "quantities": 0
    },
    {
      "drawing_id": "48e1aa3450dff526",
      "file": "model/house.ifc",
      "to_review": 0,
      "signed": 0,
      "quantities": 26
    }
  ],
  "conflicts": [
    {
      "drawing_id": "0f2705085f870f02",
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

### `GET /api/drawings/{drawing_id}`

<!-- fixture: drawing.json -->
```json
{
  "id": "1562846cb3da6f1c",
  "file": "plans/flat-a.pdf",
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "ifc",
    "question_parser": "templates"
  },
  "credit": null,
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/1562846cb3da6f1c/pages/1.png",
      "normalised": null
    }
  ],
  "suggestions": [
    {
      "quantity": "door",
      "label": "door count",
      "question": "How many doors are there?"
    },
    {
      "quantity": "window",
      "label": "window count",
      "question": "How many windows are there?"
    },
    {
      "quantity": "toilet",
      "label": "toilet count",
      "question": "How many toilets are there?"
    }
  ]
}
```

- `reader`: how the drawing was read: the route, the file it was read from (`source`), that route's reader
  (`extractor`; `hello` reads nothing), the second counter and the question parser.
- `credit`: the licence credit to show next to the drawing; null today (uploads carry none).
- `pages` is `[]` for an IFC model asked about on its own. `normalised` is null for a PDF page; for an image,
  `{"exif": 6, "rotated": 0, "deskew_deg": 0.0, "rectified": false, "quad": null, "width": 3024, "height": 4032}`:
  the EXIF orientation of the upload, the turn and deskew made after it, and `quad`, the paper's four corners in
  the upload as fractions of it, once the photo rectifier is plugged in (null today).
- `suggestions`: questions this drawing answers, one per quantity with a value. Each is checked against the
  question parser when it is made, so asking it is never refused.

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
  "drawing_id": "1562846cb3da6f1c",
  "question": "How many doors are there?"
}
```

`question` is 1 to 2000 characters. The response carries the takeoff row the value was read from, in the same
shape as `GET …/takeoff` gives it, so one component shows both:

<!-- fixture: answer.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "1562846cb3da6f1c",
  "file": "plans/flat-a.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/1562846cb3da6f1c/pages/1.png",
      "normalised": null
    }
  ],
  "answer": 2,
  "unit": "count",
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
    "signed": null
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
    "second_counter": "ifc",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 0.0001622469862923026,
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
    "latency_s": 0.0001622469862923026,
    "confidence": null,
    "abstain": null,
    "explanation": null,
    "estimate": null,
    "conflicts": null,
    "resolution": null
  }
}
```

- `answer`, `unit`: the value to show. It is the row's current `value`, so a surveyor's edits show here
  (`quantity.original_value` is what ingest computed). Null on a refusal: the screen shows no number.
- `quantity`: the takeoff row (see below), with its `rule`, `status`, `first`/`second`, `conflict`, `estimate`,
  `settled` and `signed` (the engineer view shows "verified by Ana" from `signed`). Null for a refusal and for an
  answer read from a schedule.
- `marks`: the evidence to draw, the row's marks; for a schedule answer one mark per row read (`e1`, `e2`…) and
  `answer` may be a string with `unit` null.
- `pages`: the drawing's pages, so the viewer needs no second request.
- `method`: `takeoff`, `schedule`, or `refused:<why>` / `prior:policy` on a refusal. `explanation`: how the value
  was reached, for a "details" view.
- `cost_usd`, `latency_s`: of this answer. A takeoff lookup costs 0: no model call at question time.
- `line` is the exact answer_v1.1 line (decision 0002, `eval/schemas/answer_v1.schema.json`) as the scorer reads
  it, from the pipeline's own reading: edits never change it. On a refusal it may hold the dev prior's estimate.

A question the drawing cannot answer:

<!-- fixture: answer_refused.json -->
```json
{
  "question": "What colour is the roof?",
  "drawing_id": "1562846cb3da6f1c",
  "file": "plans/flat-a.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/1562846cb3da6f1c/pages/1.png",
      "normalised": null
    }
  ],
  "answer": null,
  "unit": null,
  "quantity": null,
  "marks": [],
  "refusal": {
    "code": "unsupported-question",
    "text": "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.",
    "can_answer": [
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
  },
  "method": "refused:unsupported-question",
  "explanation": "no count, area, length or volume asked for",
  "reader": {
    "route": "vector",
    "source": "plans/flat-a.pdf",
    "extractor": "pdf",
    "second_counter": "ifc",
    "question_parser": "templates"
  },
  "cost_usd": 0.0,
  "latency_s": 4.547601565718651e-05,
  "line": {
    "id": 1,
    "answer": null,
    "unit": null,
    "evidence": [],
    "method": "refused:unsupported-question",
    "cost_usd": 0.0,
    "latency_s": 4.547601565718651e-05,
    "confidence": null,
    "abstain": true,
    "explanation": "no count, area, length or volume asked for",
    "estimate": null,
    "conflicts": null,
    "resolution": null
  }
}
```

`refusal.code`:

| Code | When |
| --- | --- |
| `unsupported-question` | the question is not one the parser turns into a count, area, length or volume |
| `not-in-drawing` | the drawing does not give this quantity (or no schedule on the sheet answers it) |
| `not-read` | the reader of this drawing does not look for that class, so it has no count of it |
| `no-reader` | nothing was read from the sheet (no reader for its route yet), or that reader is less reliable than a guess for this kind of question (`prior:policy`) |
| `no-scale` | an area or length on a sheet without a scale |
| `no-drawing` | the file has no drawing model |

`refusal.text` is written for the person at the screen. `can_answer` lists up to six questions this drawing
answers, as `suggestions` on the drawing does.

## Takeoff and review (surveyor)

### `GET /api/drawings/{drawing_id}/takeoff?zeros=<bool>`

<!-- fixture: takeoff.json -->
```json
{
  "drawing_id": "0f2705085f870f02",
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
      "signed": null
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
      "signed": null
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
        "text": "every room that is not outdoor; shafts, lifts and stairwells stay in, as the dataset's answers do although the question says shafts are left out (review-4)"
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
      "signed": null
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
- `first`, `second`: the drawing's own reading and the independent method's value (ingest stage 8). Set when the
  two methods disagree. (**Waits on core**: when they agree core does not attach the second value yet, so such a
  row is `single` with `second` null.)
- `conflict`: every method's value and the rule that kept one (`resolution`; null: no rule decides). Null when the
  methods agree or only one measured it.
- `status`, ranked: `signed` (signed off), `conflict` (methods disagree, not settled), `estimate` (rests on an
  estimated scale or reading, not settled), `edited` (a review changed it), `agree` (two methods agree: **waits on
  core**), `single` (one method).
- `needs_person`: the methods disagree, no rule decides and nobody settled it. Such a row can't be signed off.
- `settled`: the value a surveyor chose with `settle`, and when.
- `marks`: one per counted item (count) or per room in the sum (area), in the order the screen numbers them.
  - `n`: the number to draw, null for a mark that is not counted.
  - `state`: `counted`, `rejected` (by a surveyor), `added` (by a surveyor), `excluded` (left out by the counting
    rule, with `reason`; **waits on core**: core does not return the items a rule left out yet, so none is sent).
  - `value`: the item's share of the total: 1 in a count, the room's m2 in an area, null when unknown.
  - `label`: the room's printed label (else its type) or the element class; `ref`: the element or room id in the
    drawing model; `polygon`: the room's outline when the model has one (else draw the box). All three are null
    for an added mark.
- `review_queue`: the keys whose status is `conflict` or `estimate`.
- `value` is the current value (after review); `original_value` what ingest computed.

### `POST /api/drawings/{drawing_id}/review?zeros=<bool>`

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
  it. (`restore` on an `excluded` mark counts it in, once core sends them.)
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
