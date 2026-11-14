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
| Unknown rule pack (`?pack=`) | 404 `unknown-pack` |
| A relevance call on a file triage did not describe (decision 0010) | 422 `no-description` |
| Reading as a floor plan a file triage did not set aside as not a floor plan | 422 `not-triaged` |
| `reject`/`restore` without `mark`, `add` without `page` and `box` or on a page the drawing does not have, `add` to an area or length, `settle` without `value`, a width that is not 400, 1600 or 3200 | 422 `invalid` |
| A body that does not fit the request model (no `name` on an upload, an empty question, an unknown action) | 422 `validation` |
| Sign-off of a conflict no rule decides and nobody settled; an edit of a signed-off quantity; a relevance call or a read as a floor plan before the project is `done` or while one of its files is read again; reading a file as a floor plan twice | 409 `not-allowed` |
| A project's questions or building-code checks while its ingest is not `done` | 409 `not-allowed` |
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
| `POST /api/projects/{project_id}/files/{file_id}/relevance` | A person's call on a triaged file: related or unrelated, or undo | 0010 |
| `POST /api/projects/{project_id}/files/{file_id}/triage` | Read a file triage set aside as a floor plan (in the background) | 0010 |
| `GET /api/projects/{project_id}/files/{file_id}/preview.png?width=` | The file as uploaded, EXIF turn applied | #27 |
| `GET /api/projects/{project_id}/review` | Per drawing what is left to review, and every conflict of the project | #32 |
| `GET /api/projects/{project_id}/issues?pack=` | Every finding as a located issue; also `.csv`, and `.zip` with the marked pages | #140 |
| `GET /api/drawings/{drawing_id}` | How the drawing was read, its pages, questions it can answer | #31 |
| `GET /api/drawings/{drawing_id}/model` | The drawing model (extraction_v1) | #27 |
| `GET /api/drawings/{drawing_id}/pages/{n}.png?width=` | Page `n` as PNG | #31 |
| `GET /api/drawings/{drawing_id}/evidence.png?question=&width=` | An answer with its proof drawn on its page | #31 |
| `POST /api/ask` | Answer a question with its takeoff row, marks, rule, conflicts, cost | #31 |
| `POST /api/projects/{project_id}/ask` | Ask every drawing of a project; the parts, and their total where one means something | #31 |
| `GET /api/drawings/{drawing_id}/takeoff?zeros=` | Every quantity with its marks, both methods' values and review state | #32 |
| `POST /api/drawings/{drawing_id}/review` | Reject, restore or add a mark; settle, unsettle; reset. Returns the takeoff | #32 |
| `POST /api/drawings/{drawing_id}/signoff` | Sign off one quantity, or undo it. Returns the takeoff | #32 |
| `GET /api/drawings/{drawing_id}/takeoff.csv?zeros=` | The takeoff as CSV | #32 |
| `GET /api/drawings/{drawing_id}/checks?pack=&project=` | Building-code pre-check of a drawing: pass, fail or cannot tell per room or door | #139 |
| `GET /api/projects/{project_id}/checks?pack=` | The same for every drawing of a project | #139 |

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
  },
  "rule_packs": [
    {
      "id": "ch-zh",
      "country": "CH",
      "country_name": "Canton of Zürich",
      "name": "Canton of Zürich building act",
      "law": "Planungs- und Baugesetz des Kantons Zürich (PBG, LS 700.1), as in force on 1 January 2026",
      "version": "2026-11-14",
      "note": "A pre-check of a few rules, not a compliance certificate.",
      "fail_means": "It would not meet the Canton of Zürich's rule; other cantons set their own.",
      "rules": [
        {
          "id": "ch-zh-room-area",
          "title": "A bedroom or living room is at least 10 m2 (canton of Zürich)",
          "op": "room_area",
          "applies_to": {
            "room_types": [
              "bedroom",
              "living"
            ],
            "element_classes": [],
            "not_room_types": [],
            "skip_labels": [
              "R",
              "RT",
              "RH",
              "RUOK",
              "RUOKAILU",
              "Essen",
              "Repas",
              "Pranzo",
              "ALKOVI"
            ],
            "note": "Canton of Zürich only: Swiss building law is cantonal and there is no national limit. Rooms for living and sleeping (PBG s. 299). Not in single-family houses and comparable dwellings (s. 303). A dining area that is part of an open room (Essen, Repas, Pranzo) is not a room of its own and is not checked; kitchens are left out (the government may set other rules for them)."
          },
          "comparison": ">=",
          "comparison_text": "at least",
          "limit": 10.0,
          "unit": "m2",
          "key": null,
          "clause": {
            "ref": "Planungs- und Baugesetz des Kantons Zürich (PBG, LS 700.1), § 303 Abs. 1",
            "url": "https://www.notes.zh.ch/appl/zhlex_r.nsf/WebView/3B9E9F2232301FF3C1258D2A00290112/$File/700.1_7.9.75_131.pdf",
            "quote": "Die Mindestfläche von Räumen, ausser solchen in Einfamilienhäusern und bei vergleichbaren Wohnungsarten, beträgt 10 m².",
            "quote_en": "The minimum area of rooms, except those in single-family houses and comparable kinds of dwelling, is 10 m2."
          }
        }
      ]
    },
    {
      "id": "fi",
      "country": "FI",
      "country_name": "Finland",
      "name": "Finland: homes and accessibility decrees",
      "law": "Rakentamislaki 751/2023; decrees 1008/2017 (homes and rooms) and 241/2017 (accessibility), kept in force by the entry-into-force provision of Act 752/2023",
      "version": "2026-11-14",
      "note": "A pre-check of a few rules, not a compliance certificate.",
      "fail_means": "It would not meet today's rule for a new building.",
      "rules": [
        {
          "id": "fi-habitable-room-area",
          "title": "A bedroom or living room is at least 7 m2",
          "op": "room_area",
          "applies_to": {
            "room_types": [
              "bedroom",
              "living"
            ],
            "element_classes": [],
            "not_room_types": [],
            "skip_labels": [
              "R",
              "RT",
              "RH",
              "RUOK",
              "RUOKAILU",
              "Essen",
              "Repas",
              "Pranzo",
              "ALKOVI"
            ],
            "note": "New buildings, extensions and substantial changes of use (decree 1008/2017 s. 1); in a repair the original solution may be kept. Habitable rooms only: not a hall, corridor, bathroom or the like (s. 2). A dining nook that is part of an open room (labels R, RT, RH, RUOK, RUOKAILU, Essen, Repas, Pranzo) is not a room of its own and is not checked, nor is an alcove (ALKOVI). Kitchens are left out: a plan does not tell a kitchen (a habitable room) from a kitchenette. Floor under 1.6 m of headroom does not count (s. 2), which a plan does not show."
          },
          "comparison": ">=",
          "comparison_text": "at least",
          "limit": 7.0,
          "unit": "m2",
          "key": null,
          "clause": {
            "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 1008/2017, 4 § 2 mom.",
            "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008",
            "quote": "Asuin-, majoitus- ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
            "quote_en": "The room area of a residential, accommodation or work space must, however, always be at least 7 square metres."
          }
        }
      ]
    }
  ]
}
```

`no_keys: true` when no reader needs an API key or a model server: no `gemini`, `verda` or `decisions` source
in `RASTER_COMPONENTS`, and `DECISIONS_CONFIDENCE` and `DECISIONS_KIND` off. The screen then shows "running
offline". A reader named `hello` reads nothing: drawings on that route have no counts, and their
questions are refused with the code `no-reader`. `limits` lets the screen refuse a file before uploading it.

`rule_packs` are the building-code packs the country picker offers (decision 0009, "Building-code checks"
below), one per law: `country` is the ISO 3166-1 alpha-2 code for the flag, `country_name` what the picker
writes ("Finland", "Canton of Zürich": Swiss building law is cantonal, so that pack is the canton's, never
"Switzerland"), `name` the pack's display name, `law` the law line. `note` is always "A pre-check of a few rules,
not a compliance certificate."; `fail_means` (null: nothing) says what a fail means under that law ("It would
not meet today's rule for a new building."). Each rule: `title`; `op`, the check type, never shown; `comparison`
(`>=`, `>`, `<=`, `<`) with `comparison_text`, the words to show ("at least"); `limit` and `unit` (`m2`, `m`,
`count`, as the takeoff writes units); `applies_to` (`room_types` as `MarkView.room_type`, `element_classes` as
the drawing model's classes, `not_room_types`, `skip_labels` and a `note` on scope and exceptions, to show with
the rule); `key`, the takeoff key of a `takeoff` rule, else null; and `clause` `{ref, url, quote, quote_en}`:
the clause the limit comes from, its sentence as printed, and our English (null when the law is in English: show
`quote` alone). No pack is preselected and choosing none is valid: then nothing is checked.

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

`to_review` and `conflicts_open` are null until the project is `done`. `to_review`: the quantities left to review
over its drawings (the review queue). `conflicts_open`: the conflicts a person still has to settle, that is rows
with `needs_person: true` (the two methods disagree, no rule decides, nobody settled it); a conflict a rule
decided ("settled by a rule") or a person settled is not open. A room's several names count once.
`issues_open`: the issues in state `open` in `GET /api/projects/{id}/issues` without a pack; null until `done`.
`not_plans`: as in `GET /api/projects/{id}` (file triage); left out when the project was ingested with triage off.

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
      "drawings": 5,
      "to_review": 1,
      "conflicts_open": 0,
      "issues_open": 4
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
  "started_at": "2026-11-14T08:00:00+00:00",
  "finished_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "plans/flat-a.pdf",
      "size": 2263,
      "sha256": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
      "kind": "pdf_vector",
      "state": "ready",
      "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
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
      "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
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
      "reason": "1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)",
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
  ],
  "skipped": [
    {
      "path": "photos/site.jpg",
      "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink, camera EXIF (SyntheticPhone Model 1))"
    },
    {
      "path": "cad/detail.dxf",
      "reason": "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on"
    }
  ],
  "expected_drawings": 5
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
- A multi-page PDF: page 1 is read with the file itself, as before. Each later page that holds a drawing (up to 50
  after page 1) is listed as a file of its own, `<name>#p<n>.pdf` next to the PDF (e.g. `plans/set#p3.pdf`), later
  in the list, with its own group, route and drawing; its first stage (`unpack`) says "page 3 of plans/set.pdf, as a
  PDF of its own". The PDF's `reason` (or its `identify` stage) names those pages. Text pages are not split.
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
  "started_at": "2026-11-14T08:00:00+00:00",
  "finished_at": null,
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
  "drawings": [],
  "skipped": [],
  "expected_drawings": null
}
```

<!-- fixture: project_failed.json -->
```json
{
  "id": "5e0c1a2b3d51",
  "name": "plan.pdf",
  "state": "failed",
  "created_at": "2026-11-14T08:00:00+00:00",
  "started_at": "2026-11-14T08:00:00+00:00",
  "finished_at": null,
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
  "drawings": [],
  "skipped": [
    {
      "path": "plan.pdf",
      "reason": "not ingested: the server restarted during ingest"
    }
  ],
  "expected_drawings": 0
}
```

### File triage (decision 0010)

Off by default (`TRIAGE_CLASSIFIER=off`). With it on, every image file (a PNG or JPEG, a photo, a scanned PDF;
not vector PDFs, IFC, DXF or SVG) is asked "is this a floor plan?" in the `identify` stage, before any reader. A
floor plan goes on as before. Any other image is kept, set aside, described in words, and once the project's plans
are read, judged against the project. Nothing is deleted, and a person's call is never a reading: an image called
`related` stays `set_aside`, with no drawing. There is no new file state and no new trace stage: the triage is in
the `identify` stage's line.

`FileStatus.triage` (left out when triage did not look at the file):

- `class`: `floor_plan`, `other_drawing` (an elevation, section, site plan, detail, schedule sheet or cover) or
  `not_drawing` (a photo, a music score, a text page, an icon). A closed list: map it to words. Unsure is
  `floor_plan`, because a plan set aside would never be read.
- `p_plan`: P(a floor plan anywhere on the page), 0 to 1. `method`: how, in plain words.
- `description` (only for a file that is not a floor plan): `text` (1-3 sentences), `subject` (a short label),
  `text_seen` (words printed on it: title-block and caption text only; the describer is told not to transcribe
  personal data such as private people's names, phone numbers, number plates or home addresses), `language`
  (ISO 639-1 of `text_seen`, null when none), `model`, `cost_usd`.
- `relevance` (set once the project's ingest is done): `verdict` `related`, `unrelated` or `unsure`, `why` (one
  sentence naming what matched or what is missing), `matched_on`, `plans` (drawing ids, always among this
  project's `drawings`), `judge`. With no plan read in the project the verdict is `unsure`, "no floor plan in the
  project to compare with".
- `overruled`: a person's call, `{verdict: related|unrelated, by, at}`; the judge's `relevance` stays as it was.
- `read_as_plan`: `{by, at}` once a person had the file read as a floor plan (`POST …/triage`); `class` stays the
  classifier's.
- `verdict`: the one value that counts: `overruled.verdict`, else `relevance.verdict`, else null.
- `note`: why `description` or `relevance` is null, a plain sentence: "a floor plan: it is read, so it is not
  described or judged"; "not described: no description model is set up, so it is not judged" (no describer: the
  offline demo); "not described: <why>" (the model refused or failed); "not judged yet: the project is still being
  read"; "not judged: no relevance judge is set up"; "not judged: <why>". Null when both are set.

`description.subject`, `method`, `relevance.judge`, `matched_on` items, and the part of the file's `reason` after
"not a floor plan: " are plain words, shown as they are. Description and judge costs count in the file's and the
project's `cost_usd`; with no model set up they are 0.

`not_plans` (on `ProjectView` and `ProjectSummary`): the files triage called not a floor plan, a person's relevance
call or not (it changes the verdict, not the class), less those a person had read as a floor plan (a class call).
Never a file set aside for its format (`triage` null). Null until `done`, then final except when a person has a
file read as a floor plan; left out when the project was ingested with triage off.

A project with triage on (the test fakes: an elevation judged related, the site photo judged unrelated and then
called related by a person, a photo the describer refused):

<!-- fixture: project_triaged.json -->
```json
{
  "id": "5e0c1a2b3d52",
  "name": "site.zip",
  "state": "done",
  "created_at": "2026-11-14T08:00:00+00:00",
  "started_at": "2026-11-14T08:00:00+00:00",
  "finished_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "plans/flat-a.pdf",
      "size": 2263,
      "sha256": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
      "kind": "pdf_vector",
      "state": "ready",
      "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
      "group": "plans/flat-a",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "drawing_id": "6a47e9a1c33db404",
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
      "path": "elevations/south.png",
      "size": 8835,
      "sha256": "b6d80d60df6169ac47933fd4d7d89287026da6efa6616a34798c711a565d4de4",
      "kind": "png_plan",
      "state": "set_aside",
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover) (P(plan) 0.03, fake classifier)",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 12.5,
      "stage": "identify",
      "cost_usd": 0.0,
      "normalised": null,
      "triage": {
        "class": "other_drawing",
        "p_plan": 0.03,
        "method": "fake classifier",
        "description": {
          "text": "A picture of the south elevation of a two-storey house.",
          "subject": "the south elevation of a two-storey house",
          "text_seen": [
            "Küche",
            "Süd"
          ],
          "language": "en",
          "model": "fake describer",
          "cost_usd": 0.0
        },
        "relevance": {
          "verdict": "related",
          "why": "Related: Küche is on the project's plans.",
          "matched_on": [
            "Küche"
          ],
          "plans": [
            "6a47e9a1c33db404"
          ],
          "judge": "word judge"
        },
        "overruled": null,
        "read_as_plan": null,
        "verdict": "related",
        "note": null
      }
    },
    {
      "id": "f3",
      "path": "photos/site.jpg",
      "size": 524600,
      "sha256": "642105ade12e3629470ad9e6b42039cb4312899f0f22c23eb7fe15c7cc56b4c3",
      "kind": "photo",
      "state": "set_aside",
      "reason": "not a floor plan: not a drawing (P(plan) 0.03, fake classifier)",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 12.5,
      "stage": "identify",
      "cost_usd": 0.0,
      "normalised": null,
      "triage": {
        "class": "not_drawing",
        "p_plan": 0.03,
        "method": "fake classifier",
        "description": {
          "text": "A picture of a building site with a crane.",
          "subject": "a building site with a crane",
          "text_seen": [],
          "language": null,
          "model": "fake describer",
          "cost_usd": 0.0
        },
        "relevance": {
          "verdict": "unrelated",
          "why": "Unrelated: no word on it is on the project's plans or in its file names.",
          "matched_on": [],
          "plans": [],
          "judge": "word judge"
        },
        "overruled": {
          "verdict": "related",
          "by": "Ana",
          "at": "2026-11-14T08:05:00Z"
        },
        "read_as_plan": null,
        "verdict": "related",
        "note": null
      }
    },
    {
      "id": "f4",
      "path": "photos/street.jpg",
      "size": 524553,
      "sha256": "735c66abcf63f04a3756987b74897e4c83b1e87d76245eeb806623045c2c55fd",
      "kind": "photo",
      "state": "set_aside",
      "reason": "not a floor plan: not a drawing (P(plan) 0.03, fake classifier)",
      "group": null,
      "route": null,
      "source": null,
      "drawing_id": null,
      "reused": false,
      "takeoff": {},
      "ms": 12.5,
      "stage": "identify",
      "cost_usd": 0.0,
      "normalised": null,
      "triage": {
        "class": "not_drawing",
        "p_plan": 0.03,
        "method": "fake classifier",
        "description": null,
        "relevance": null,
        "overruled": null,
        "read_as_plan": null,
        "verdict": null,
        "note": "not described: the model refused"
      }
    }
  ],
  "counts": {
    "ready": 1,
    "set_aside": 3
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
    "decisions_kind": "False",
    "triage": "fakes"
  },
  "error": null,
  "ms": 12.5,
  "cost_usd": 0.0,
  "drawings": [
    {
      "drawing_id": "6a47e9a1c33db404",
      "group": "plans/flat-a",
      "file": "plans/flat-a.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-a.pdf",
      "state": "ready",
      "other_renderings": []
    }
  ],
  "skipped": [
    {
      "path": "elevations/south.png",
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover) (P(plan) 0.03, fake classifier)"
    },
    {
      "path": "photos/site.jpg",
      "reason": "not a floor plan: not a drawing (P(plan) 0.03, fake classifier)"
    },
    {
      "path": "photos/street.jpg",
      "reason": "not a floor plan: not a drawing (P(plan) 0.03, fake classifier)"
    }
  ],
  "expected_drawings": 1,
  "not_plans": 3
}
```

### `POST /api/projects/{project_id}/files/{file_id}/relevance`

A person's call on a triaged file. The body is `{verdict: "related"|"unrelated", by}`, or `{undo: true}` to take
the call back. `by` is the name the person types, as in a sign-off (1-100 characters). Confirming the judge's own
verdict is a call too: it settles the file's issue. Returns the file's `FileStatus`.

<!-- fixture: relevance_request.json -->
```json
{
  "verdict": "related",
  "by": "Ana"
}
```

- 409 `not-allowed` until the project is `done`; 404 `not-found` for an unknown project or file.
- 422 `no-description` for a file triage did not describe (there is nothing to judge, so nothing to overrule).
- 422 `validation` for a body outside the shape: a `verdict` other than `related` or `unrelated`, no `by`, an empty
  or too long `by`, `undo` with a `verdict`.
- `undo` with no call made: 200, the file unchanged.

### `POST /api/projects/{project_id}/files/{file_id}/triage`

A person says a file triage set aside is a floor plan, so it is read as one: in the background, that file alone,
through the usual group, route and readers. The body is `{class: "floor_plan", by}` (`by` as in a sign-off). 202
with the file's `FileStatus`, `queued`; poll `GET /api/projects/{project_id}`: the file goes `running`, then
`ready`, `flagged` or `set_aside` like any file, and once read it has a `drawing_id` and is in `drawings`. The
project stays `done` throughout.

- `triage.read_as_plan` = `{by, at}`; `class` stays the classifier's. The file leaves `not_plans`.
- Its `unrelated_file` issue stays, `settled`, with the same id, and "<by> had it read as a floor plan" in `why`.
  The new drawing's own issues (a reading flag, a conflict) join the list; the issues already there keep their
  order.
- The trace adds a second `identify` line, "read as a floor plan, as <by> asked", then the usual stages.
- A photo is read as a photo of a plan (framed and rectified like one).
- No undo: a reading is not unread. A relevance call still works.
- 404 `not-found` for an unknown file; 409 `not-allowed` until the project is `done`, while a file of it is read
  again, or for a file already read this way; 422 `not-triaged` for a file triage did not set aside as not a floor
  plan; 422 `validation` for a `class` other than `floor_plan` or no `by`.
- A file whose reading a restart cut off is set aside, "not read as a floor plan: the server restarted during
  ingest"; the project stays `done`.

<!-- fixture: triage_request.json -->
```json
{
  "class": "floor_plan",
  "by": "Ana"
}
```

<!-- fixture: triage_started.json -->
```json
{
  "id": "f2",
  "path": "elevations/south.png",
  "size": 8835,
  "sha256": "b6d80d60df6169ac47933fd4d7d89287026da6efa6616a34798c711a565d4de4",
  "kind": "png_plan",
  "state": "queued",
  "reason": "queued to be read as a floor plan",
  "group": null,
  "route": null,
  "source": null,
  "drawing_id": null,
  "reused": false,
  "takeoff": {},
  "ms": 12.5,
  "stage": "identify",
  "cost_usd": 0.0,
  "normalised": null,
  "triage": {
    "class": "other_drawing",
    "p_plan": 0.03,
    "method": "fake classifier",
    "description": {
      "text": "A picture of the south elevation of a two-storey house.",
      "subject": "the south elevation of a two-storey house",
      "text_seen": [
        "Küche",
        "Süd"
      ],
      "language": "en",
      "model": "fake describer",
      "cost_usd": 0.0
    },
    "relevance": {
      "verdict": "related",
      "why": "Related: Küche is on the project's plans.",
      "matched_on": [
        "Küche"
      ],
      "plans": [
        "6a47e9a1c33db404"
      ],
      "judge": "word judge"
    },
    "overruled": null,
    "read_as_plan": {
      "by": "Ana",
      "at": "2026-11-14T08:05:00Z"
    },
    "verdict": "related",
    "note": null
  }
}
```

The same file once read:

<!-- fixture: file_read_as_plan.json -->
```json
{
  "id": "f2",
  "path": "elevations/south.png",
  "size": 8835,
  "sha256": "b6d80d60df6169ac47933fd4d7d89287026da6efa6616a34798c711a565d4de4",
  "kind": "png_plan",
  "state": "flagged",
  "reason": "no reader for the image route yet: nothing was read (0 elements, 0 rooms, no scale on the sheet)",
  "group": "elevations/south",
  "route": "raster",
  "source": "elevations/south.png",
  "drawing_id": "90dc7849bebce83d",
  "reused": false,
  "takeoff": {},
  "ms": 12.5,
  "stage": "write",
  "cost_usd": 0.0,
  "normalised": {
    "exif": null,
    "rotated": 0,
    "deskew_deg": 0.0,
    "rectified": false,
    "quad": null,
    "width": 850,
    "height": 1200,
    "rectifier": null
  },
  "triage": {
    "class": "other_drawing",
    "p_plan": 0.03,
    "method": "fake classifier",
    "description": {
      "text": "A picture of the south elevation of a two-storey house.",
      "subject": "the south elevation of a two-storey house",
      "text_seen": [
        "Küche",
        "Süd"
      ],
      "language": "en",
      "model": "fake describer",
      "cost_usd": 0.0
    },
    "relevance": {
      "verdict": "related",
      "why": "Related: Küche is on the project's plans.",
      "matched_on": [
        "Küche"
      ],
      "plans": [
        "6a47e9a1c33db404"
      ],
      "judge": "word judge"
    },
    "overruled": null,
    "read_as_plan": {
      "by": "Ana",
      "at": "2026-11-14T08:05:00Z"
    },
    "verdict": "related",
    "note": null
  }
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
    "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
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
      "output": "drawn PDF",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "group",
      "did": "plans/flat-a: flat-a.pdf, flat-a.png",
      "ms": 12.5,
      "output": "2 files",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "route",
      "did": "drawn PDF route, read from plans/flat-a.pdf",
      "ms": 12.5,
      "output": "vector",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "normalise",
      "did": "1 page, page 1 is 600 x 400 pt",
      "ms": 12.5,
      "output": "1 page, page 1 is 600 x 400 pt",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "extract",
      "did": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
      "ms": 12.5,
      "output": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "second_count",
      "did": "5 quantities measured twice, 0 conflicts",
      "ms": 12.5,
      "output": "5 quantities measured twice, 0 conflicts",
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
  ],
  "second_count": {
    "measured": 5,
    "conflicts": 0
  }
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
  ],
  "second_count": null
}
```

### `GET /api/projects/{project_id}/trace`

Every file's trace (the same object as the per-file route, `second_count` included) in one request, in the order the
upload lists the files, instead of one request per file.

<!-- fixture: project_trace.json -->
```json
{
  "project_id": "5e0c1a2b3d4f",
  "files": [
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f1",
        "path": "plans/flat-a.pdf",
        "size": 2263,
        "sha256": "dd2c1cfd3ebb6523d5d0be38035ecb7ebe6cc74674cd88a7c8aae259b7374ef2",
        "kind": "pdf_vector",
        "state": "ready",
        "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
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
          "output": "drawn PDF",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "plans/flat-a: flat-a.pdf, flat-a.png",
          "ms": 12.5,
          "output": "2 files",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "drawn PDF route, read from plans/flat-a.pdf",
          "ms": 12.5,
          "output": "vector",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 600 x 400 pt",
          "ms": 12.5,
          "output": "1 page, page 1 is 600 x 400 pt",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "ms": 12.5,
          "output": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "5 quantities measured twice, 0 conflicts",
          "ms": 12.5,
          "output": "5 quantities measured twice, 0 conflicts",
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
      ],
      "second_count": {
        "measured": 5,
        "conflicts": 0
      }
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f2",
        "path": "plans/flat-a.png",
        "size": 21988,
        "sha256": "f73bc98a3ee5e771c83902a884a87038618c91d697d48033845f049a94edbb5f",
        "kind": "png_plan",
        "state": "ready",
        "reason": "read on the drawn PDF route: 7 elements, 5 rooms, scale read from the sheet",
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
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 21988 bytes",
          "ms": 12.5,
          "output": "plans/flat-a.png",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 f73bc98a3ee5",
          "ms": 12.5,
          "output": "f73bc98a3ee5e771c83902a884a87038618c91d697d48033845f049a94edbb5f",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a drawing as a PNG (1200x800 px, 93% white, 99% paper, 0.0% ink)",
          "ms": 12.5,
          "output": "PNG drawing",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "plans/flat-a: flat-a.pdf, flat-a.png",
          "ms": 12.5,
          "output": "2 files",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "drawn PDF route, read from plans/flat-a.pdf",
          "ms": 12.5,
          "output": "vector",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 1200 x 800 px",
          "ms": 12.5,
          "output": "1 page, page 1 is 1200 x 800 px",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "ms": 12.5,
          "output": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "5 quantities measured twice, 0 conflicts",
          "ms": 12.5,
          "output": "5 quantities measured twice, 0 conflicts",
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
          "did": "drawing model c9b719f715357201 stored",
          "ms": 12.5,
          "output": "71 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": {
        "measured": 5,
        "conflicts": 0
      }
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f3",
        "path": "plans/flat-b.pdf",
        "size": 2262,
        "sha256": "a7fce07de2895f481058912db6d1cd56d7e2f0e05cb3b38b4b6cfc3578726ab4",
        "kind": "pdf_vector",
        "state": "flagged",
        "reason": "1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)",
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
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 2262 bytes",
          "ms": 12.5,
          "output": "plans/flat-b.pdf",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 a7fce07de289",
          "ms": 12.5,
          "output": "a7fce07de2895f481058912db6d1cd56d7e2f0e05cb3b38b4b6cfc3578726ab4",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a drawn PDF (page 1 of 1: 18 paths, 0 images, 142 characters)",
          "ms": 12.5,
          "output": "drawn PDF",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "plans/flat-b: flat-b.pdf",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "drawn PDF route, read from plans/flat-b.pdf",
          "ms": 12.5,
          "output": "vector",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 600 x 400 pt",
          "ms": 12.5,
          "output": "1 page, page 1 is 600 x 400 pt",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "ms": 12.5,
          "output": "7 elements, 5 rooms, 1 plan, scale read from the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "5 quantities measured twice, 1 conflict",
          "ms": 12.5,
          "output": "5 quantities measured twice, 1 conflict",
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
          "did": "drawing model 6d153ea15dca9ab4 stored",
          "ms": 12.5,
          "output": "71 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": {
        "measured": 5,
        "conflicts": 1
      }
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f4",
        "path": "scans/ground-floor.png",
        "size": 7237,
        "sha256": "4d70b874dd858dc28d22d213c66069458696a5baeb401eadd0935f2027bc36b4",
        "kind": "png_plan",
        "state": "flagged",
        "reason": "no reader for the image route yet: nothing was read (0 elements, 0 rooms, no scale on the sheet)",
        "group": "scans/ground-floor",
        "route": "raster",
        "source": "scans/ground-floor.png",
        "drawing_id": "3b3ce7db34257f63",
        "reused": false,
        "takeoff": {},
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
          "height": 850,
          "rectifier": null
        }
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 7237 bytes",
          "ms": 12.5,
          "output": "scans/ground-floor.png",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 4d70b874dd85",
          "ms": 12.5,
          "output": "4d70b874dd858dc28d22d213c66069458696a5baeb401eadd0935f2027bc36b4",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a drawing as a PNG (1200x850 px, 95% white, 96% paper, 4.0% ink)",
          "ms": 12.5,
          "output": "PNG drawing",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "scans/ground-floor: ground-floor.png",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "image route, read from scans/ground-floor.png",
          "ms": 12.5,
          "output": "raster",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 1200 x 850 px",
          "ms": 12.5,
          "output": "1 page, page 1 is 1200 x 850 px",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "ms": 12.5,
          "output": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "0 quantities measured twice, 0 conflicts",
          "ms": 12.5,
          "output": "0 quantities measured twice, 0 conflicts",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "takeoff",
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 0 quantities, 0 above zero",
          "ms": 12.5,
          "output": "takeoff: 0 quantities, 0 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model 3b3ce7db34257f63 stored",
          "ms": 12.5,
          "output": "0 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f5",
        "path": "scans/ground-floor-copy.png",
        "size": 7237,
        "sha256": "4d70b874dd858dc28d22d213c66069458696a5baeb401eadd0935f2027bc36b4",
        "kind": "png_plan",
        "state": "flagged",
        "reason": "no reader for the image route yet: nothing was read (0 elements, 0 rooms, no scale on the sheet)",
        "group": "scans/ground-floor-copy",
        "route": "raster",
        "source": "scans/ground-floor-copy.png",
        "drawing_id": "3b3ce7db34257f63",
        "reused": true,
        "takeoff": {},
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
          "height": 850,
          "rectifier": null
        }
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 7237 bytes",
          "ms": 12.5,
          "output": "scans/ground-floor-copy.png",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 4d70b874dd85, same content as scans/ground-floor.png",
          "ms": 12.5,
          "output": "4d70b874dd858dc28d22d213c66069458696a5baeb401eadd0935f2027bc36b4",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a drawing as a PNG (1200x850 px, 95% white, 96% paper, 4.0% ink)",
          "ms": 12.5,
          "output": "PNG drawing",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "scans/ground-floor-copy: ground-floor-copy.png",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "image route, read from scans/ground-floor-copy.png",
          "ms": 12.5,
          "output": "raster",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "cache",
          "did": "seen before as scans/ground-floor.png (project 5e0c1a2b3d4f) with the same group and readers: reused, nothing recomputed; the stages below are from that ingest",
          "ms": 12.5,
          "output": "flagged",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 1200 x 850 px",
          "ms": 12.5,
          "output": "1 page, page 1 is 1200 x 850 px",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "ms": 12.5,
          "output": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "0 quantities measured twice, 0 conflicts",
          "ms": 12.5,
          "output": "0 quantities measured twice, 0 conflicts",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "takeoff",
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 0 quantities, 0 above zero",
          "ms": 12.5,
          "output": "takeoff: 0 quantities, 0 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model 3b3ce7db34257f63 stored by that ingest",
          "ms": 12.5,
          "output": "0 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f6",
        "path": "photos/plan-photo.jpg",
        "size": 59453,
        "sha256": "d3c1c562a56f613a2850c78a47e72feb4c02ca0680c2099f227dac57ad38f4c4",
        "kind": "photo_plan",
        "state": "flagged",
        "reason": "no reader for the image route yet: nothing was read; a phone photo, read without perspective correction (0 elements, 0 rooms, no scale on the sheet)",
        "group": "photos/plan-photo",
        "route": "raster",
        "source": "photos/plan-photo.jpg",
        "drawing_id": "37f6819bd17d65d9",
        "reused": false,
        "takeoff": {},
        "ms": 12.5,
        "stage": "write",
        "cost_usd": 0.0,
        "normalised": {
          "exif": null,
          "rotated": 0,
          "deskew_deg": 0.0,
          "rectified": false,
          "quad": null,
          "width": 1600,
          "height": 1200,
          "rectifier": null
        }
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 59453 bytes",
          "ms": 12.5,
          "output": "photos/plan-photo.jpg",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 d3c1c562a56f",
          "ms": 12.5,
          "output": "d3c1c562a56f613a2850c78a47e72feb4c02ca0680c2099f227dac57ad38f4c4",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a photo of a drawing (1600x1200 px, 47% white, 49% paper, 1.1% ink, camera EXIF (SyntheticPhone Model 1))",
          "ms": 12.5,
          "output": "photo of a drawing",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "photos/plan-photo: plan-photo.jpg",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "image route, read from photos/plan-photo.jpg",
          "ms": 12.5,
          "output": "raster",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "1 page, page 1 is 1600 x 1200 px",
          "ms": 12.5,
          "output": "1 page, page 1 is 1600 x 1200 px",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "ms": 12.5,
          "output": "0 elements, 0 rooms, 0 plans, no scale on the sheet",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "second_count",
          "did": "0 quantities measured twice, 0 conflicts",
          "ms": 12.5,
          "output": "0 quantities measured twice, 0 conflicts",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "takeoff",
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 0 quantities, 0 above zero",
          "ms": 12.5,
          "output": "takeoff: 0 quantities, 0 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model 37f6819bd17d65d9 stored",
          "ms": 12.5,
          "output": "0 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f7",
        "path": "photos/site.jpg",
        "size": 524600,
        "sha256": "642105ade12e3629470ad9e6b42039cb4312899f0f22c23eb7fe15c7cc56b4c3",
        "kind": "photo",
        "state": "set_aside",
        "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink, camera EXIF (SyntheticPhone Model 1))",
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
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 524600 bytes",
          "ms": 12.5,
          "output": "photos/site.jpg",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 642105ade12e",
          "ms": 12.5,
          "output": "642105ade12e3629470ad9e6b42039cb4312899f0f22c23eb7fe15c7cc56b4c3",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink, camera EXIF (SyntheticPhone Model 1))",
          "ms": 12.5,
          "output": "photo",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f8",
        "path": "model/house.ifc",
        "size": 4886,
        "sha256": "951a9027130b1b3a7a86e1c1b1292a582fb01c988a189f406078ed8b7cac0047",
        "kind": "ifc",
        "state": "ready",
        "reason": "read on the BIM model route: 12 model objects",
        "group": "model/house",
        "route": "bim",
        "source": "model/house.ifc",
        "drawing_id": "1db9bcf1e67e27a3",
        "reused": false,
        "takeoff": {
          "area:room": 48.0,
          "area:room|indoor": 48.0,
          "area:room|indoor|model": 48.0,
          "area:room|model": 48.0,
          "area:room|name=0.01|storey=ground floor": 30.0,
          "area:room|name=0.02|storey=ground floor": 18.0,
          "area:room|name=kitchen (0.02)|storey=ground floor": 18.0,
          "area:room|name=kitchen|storey=ground floor": 18.0,
          "area:room|name=living (0.01)|storey=ground floor": 30.0,
          "area:room|name=living|storey=ground floor": 30.0,
          "area:room|storey=ground floor": 48.0,
          "area:wall|storey=ground floor": 72.8,
          "beam": 0,
          "beam|model": 0,
          "beam|storey=ground floor": 0,
          "beam|storey=ground floor|model": 0,
          "column": 0,
          "column|model": 0,
          "column|storey=ground floor": 0,
          "column|storey=ground floor|model": 0,
          "door": 2,
          "door|model": 2,
          "door|storey=ground floor": 2,
          "door|storey=ground floor|model": 2,
          "length:wall|storey=ground floor": 28.0,
          "railing": 0,
          "railing|model": 0,
          "railing|storey=ground floor": 0,
          "railing|storey=ground floor|model": 0,
          "room": 2,
          "room|model": 2,
          "room|storey=ground floor": 2,
          "room|storey=ground floor|model": 2,
          "slab": 1,
          "slab|model": 1,
          "slab|storey=ground floor": 1,
          "slab|storey=ground floor|model": 1,
          "stair": 0,
          "stair|model": 0,
          "stair|storey=ground floor": 0,
          "stair|storey=ground floor|model": 0,
          "volume:slab|storey=ground floor": 12.0,
          "volume:wall|storey=ground floor": 14.56,
          "wall": 4,
          "wall|model": 4,
          "wall|storey=ground floor": 4,
          "wall|storey=ground floor|model": 4,
          "window": 3,
          "window|model": 3,
          "window|storey=ground floor": 3,
          "window|storey=ground floor|model": 3
        },
        "ms": 12.5,
        "stage": "write",
        "cost_usd": 0.0,
        "normalised": null
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 4886 bytes",
          "ms": 12.5,
          "output": "model/house.ifc",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 951a9027130b",
          "ms": 12.5,
          "output": "951a9027130b1b3a7a86e1c1b1292a582fb01c988a189f406078ed8b7cac0047",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "first bytes: an IFC building model (STEP)",
          "ms": 12.5,
          "output": "IFC model",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "model/house: house.ifc",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "BIM model route, read from model/house.ifc",
          "ms": 12.5,
          "output": "bim",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "normalise",
          "did": "no page, a building model",
          "ms": 12.5,
          "output": "no page, a building model",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "extract",
          "did": "12 model objects",
          "ms": 12.5,
          "output": "12 model objects",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "takeoff",
          "did": "takeoff: 51 quantities, 35 above zero",
          "ms": 12.5,
          "output": "takeoff: 51 quantities, 35 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model 1db9bcf1e67e27a3 stored",
          "ms": 12.5,
          "output": "51 quantities",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f9",
        "path": "cad/detail.dxf",
        "size": 79,
        "sha256": "5fc645fa369f92712910e02f3b11e3fb5a1a7bbda84cbea16bf821134724ff9b",
        "kind": "dxf",
        "state": "set_aside",
        "reason": "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on",
        "group": "cad/detail",
        "route": "cad",
        "source": "cad/detail.dxf",
        "drawing_id": null,
        "reused": false,
        "takeoff": {},
        "ms": 12.5,
        "stage": "route",
        "cost_usd": 0.0,
        "normalised": null
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 79 bytes",
          "ms": 12.5,
          "output": "cad/detail.dxf",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 5fc645fa369f",
          "ms": 12.5,
          "output": "5fc645fa369f92712910e02f3b11e3fb5a1a7bbda84cbea16bf821134724ff9b",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "first bytes: a DXF drawing",
          "ms": 12.5,
          "output": "DXF drawing",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "group",
          "did": "cad/detail: detail.dxf",
          "ms": 12.5,
          "output": "1 file",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "route",
          "did": "CAD route, read from cad/detail.dxf",
          "ms": 12.5,
          "output": "cad",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f10",
        "path": "docs/specification.pdf",
        "size": 1291,
        "sha256": "91af270215243f7925863c27187149ec275efe789e6ed277a3a9da77ad86d692",
        "kind": "pdf_text",
        "state": "text_only",
        "reason": "a text document, not a drawing (page 1 of 1: 0 paths, 0 images, 4498 characters)",
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
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 1291 bytes",
          "ms": 12.5,
          "output": "docs/specification.pdf",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 91af27021524",
          "ms": 12.5,
          "output": "91af270215243f7925863c27187149ec275efe789e6ed277a3a9da77ad86d692",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a text document, not a drawing (page 1 of 1: 0 paths, 0 images, 4498 characters)",
          "ms": 12.5,
          "output": "text PDF",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    },
    {
      "project_id": "5e0c1a2b3d4f",
      "file": {
        "id": "f11",
        "path": "docs/notes.txt",
        "size": 80,
        "sha256": "ca6138f02cfafd870094f2e8ef9a15f39c6c8925025613a0c6465ae21f2e7a20",
        "kind": "text",
        "state": "text_only",
        "reason": "plain text, 80 bytes",
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
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 80 bytes",
          "ms": 12.5,
          "output": "docs/notes.txt",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 ca6138f02cfa",
          "ms": 12.5,
          "output": "ca6138f02cfafd870094f2e8ef9a15f39c6c8925025613a0c6465ae21f2e7a20",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "plain text, 80 bytes",
          "ms": 12.5,
          "output": "text file",
          "failure": null,
          "cost_usd": 0.0
        }
      ],
      "second_count": null
    }
  ]
}
```

### `GET /api/projects/{project_id}/questions`

The questions asked in the project, newest first (the last 200): every `POST /api/ask` that names the project in
`project_id` is kept. A `POST /api/projects/{id}/ask` is kept as one line per drawing that answered (or, when none
did, one refused line per drawing), each with that drawing's `drawing_id`, `answer` and `unit`, and with
`project_ask`: an id the same on every line of that question, so the lines group into one question. `project_ask`
is absent on a line from `POST /api/ask`. A refused line carries `refusal`, the refusal's `code` (absent when the
question was answered, and on lines kept before 2026-11-14). An ask without a `project_id` is not kept.

<!-- fixture: project_questions.json -->
```json
{
  "project_id": "5e0c1a2b3d4f",
  "questions": [
    {
      "question": "What colour is the roof?",
      "answer": null,
      "unit": null,
      "drawing_id": "adeefbbcc17559fc",
      "at": "2026-11-14T08:05:00Z",
      "refused": true,
      "refusal": "unsupported-question"
    },
    {
      "question": "How many doors are there?",
      "answer": 2,
      "unit": "count",
      "drawing_id": "adeefbbcc17559fc",
      "at": "2026-11-14T08:05:00Z",
      "refused": false
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
      "to_review": 1,
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
      "quantities": 35
    }
  ],
  "conflicts": [
    {
      "drawing_id": "6d153ea15dca9ab4",
      "file": "plans/flat-b.pdf",
      "quantity": "area:room|name=1.01",
      "label": "area of room (name Küche · 1.01)",
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
      "needs_person": false,
      "signed": null,
      "value": 30.0
    }
  ]
}
```

`needs_person: true` marks a conflict no rule decides and nobody settled ("needs you"); the others were decided by
a rule ("AI decision") or settled by a surveyor.

### `GET /api/projects/{project_id}/issues?pack=<pack id>`

Every finding in the project as one located issue, the list Stoa's floor view takes in: conflicts between two
methods, refused answers, pages read with a caveat, files set aside, and with a `pack` the failed building-code
checks. The decision record, with the reasons for each choice, is
[0008](decisions/0008-located-issues.md). The list makes no model call.

- `pack` is optional: a rule pack's id from `GET /api/info` `rule_packs` (decision 0009). Its failed checks
  (`code_check_failed`) are listed only when a pack is given, since the country is chosen on the screen.
  `ProjectSummary.issues_open` counts the list without a pack.
- Errors: an unknown project is 404 `not-found`. An unknown pack is 404 `unknown-pack`. A project that is not
  `done` is 409 `not-allowed`. The CSV and zip routes answer errors the same way (JSON), so offer the downloads
  once the project is `done`.
- Order, the same in all three forms and stable between calls: severity (`fails_rule`, `needs_person`, `note`),
  then the drawing in the project's `drawings` order (files with no drawing after, in upload order), then page,
  then the box's top edge (no page or box last), then the source ref.

Each issue:

- `id`: stable across calls and restarts, and kept when the issue is settled or signed off.
- `kind`:
  - `conflict`: two methods disagree on a quantity. `quantity` + `drawing_id` is its `ConflictEntry` in
    `GET …/review`.
  - `refused_answer`: a question kept in the project's question list got no number on that drawing. Questions the
    parser can't read are left out.
  - `reading_flag`: the page was read with a caveat (a phone photo, a scan), or its reader read nothing.
  - `set_aside`: ingest set the file aside, with `reason`.
  - `code_check_failed`: a failed rule of the pack (decision 0009), one per failing room, door or sheet. A check
    that cannot tell is not an issue. `check` + `drawing_id` is its `CheckResult` in
    `GET /api/drawings/{id}/checks?pack=`; `why` is the result's `why` followed by the clause ref in brackets.
  - `double_check`: an answer we can't vouch for, one issue per disputed place. Not produced yet (#129).
  - `unrelated_file` (file triage, decision 0010): a file triage called not a floor plan whose `triage.verdict`
    is not `related` (also one not described or not judged), or one a person made a call on or had read as a
    floor plan. `reason` is the
    verdict (null while there is none), `page`, `box` and `drawing_id` are null. Its severity is the judge's:
    `needs_person` for `unsure`, else `note`. A person's call makes it `settled` and keeps its id, severity and
    place in the list, whichever way the call went; so does having it read as a floor plan. Such a file has no
    `set_aside` issue as well, unless its reading as a floor plan set it aside.
  - All seven values are in the type now, so a screen can switch over them; `double_check` appears once its
    work lands.
- `severity`: `fails_rule` (a failed code check), `needs_person` (a conflict no rule decides and nobody settled),
  or `note` (everything else: decided conflicts, refusals, reading flags, set-aside files).
- `state`: `open`, `settled` (a person settled it, or a rule decides it) or `signed_off`. Only a conflict or an
  `unrelated_file` can be other than `open`.
- `file` is the file as **this project** uploaded it. `file_id` is its `FileStatus.id` (`f3`). `drawing_id` is null
  for a file with no drawing.
- `floor`: the storey, only where the source states it (an IFC storey: the plan's on the page, or the quantity
  key's); null otherwise, never guessed.
- `page`, `box`, `polygon`, `mark_id`: where to open the drawing, in page fractions as on `MarkView`.
  - A quantity with one takeoff mark (a room) gives that mark: its page, box, `polygon` and `mark_id` (its
    `MarkView.id` in the takeoff, so the viewer can select it).
  - Otherwise the box a method read, or the sheet's only plan, with `polygon` and `mark_id` null.
  - A failed check gives its room's or door's mark (`CheckResult.marks`, role `subject`): page, box, `polygon`
    and `mark_id`, as the takeoff draws it. A check on the whole sheet has no place.
  - A reading flag gives the page of a one-page drawing and no box. A refused answer and a set-aside file have
    no page.
- `why`: one plain sentence.
- `quantity` (the takeoff key), `question` (as asked), `reason` (ingest's) and `check` (`<pack>:<result id>`) are
  the source refs, null where they don't apply.
- `links`: API paths (not screen routes) to the drawing and its takeoff in this project, the file's trace, and for a
  code check the drawing's checks.

A flat checked against the Finnish pack (`?pack=fi`), its first failed check:

<!-- fixture: project_issues_checks.json -->
```json
{
  "project_id": "5e0c1a2b3d53",
  "pack": "fi",
  "issues": [
    {
      "id": "code_check_failed-5c4ed01e0002",
      "kind": "code_check_failed",
      "severity": "fails_rule",
      "state": "open",
      "drawing_id": "5c4ed01e00000002",
      "file": "flat-fi.pdf",
      "file_id": "f1",
      "floor": null,
      "page": 1,
      "box": [
        0.28833,
        0.15,
        0.43,
        0.2925
      ],
      "polygon": [
        [
          0.28833,
          0.15
        ],
        [
          0.28833,
          0.2925
        ],
        [
          0.43,
          0.2925
        ],
        [
          0.43,
          0.15
        ]
      ],
      "mark_id": "m1",
      "why": "The bedroom \"Schlafzimmer 4.02\" is 6.03 m2; the rule asks at least 7 m2. It would not meet today's rule for a new building. (Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 1008/2017, 4 § 2 mom.)",
      "quantity": "area:room|name=4.02",
      "question": null,
      "reason": null,
      "check": "fi:fi-habitable-room-area:r2",
      "links": {
        "drawing": "/api/drawings/5c4ed01e00000002?project=5e0c1a2b3d53",
        "takeoff": "/api/drawings/5c4ed01e00000002/takeoff?project=5e0c1a2b3d53",
        "trace": "/api/projects/5e0c1a2b3d53/files/f1/trace",
        "checks": "/api/drawings/5c4ed01e00000002/checks?pack=fi&project=5e0c1a2b3d53"
      }
    }
  ]
}
```

The sample after a door question on its scan (no reader in no-keys mode):

<!-- fixture: project_issues.json -->
```json
{
  "project_id": "5e0c1a2b3d4f",
  "pack": null,
  "issues": [
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
    },
    {
      "id": "reading_flag-b8584dc30c73",
      "kind": "reading_flag",
      "severity": "note",
      "state": "open",
      "drawing_id": "3b3ce7db34257f63",
      "file": "scans/ground-floor.png",
      "file_id": "f4",
      "floor": null,
      "page": 1,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "No reader for the image route yet: nothing was read.",
      "quantity": null,
      "question": null,
      "reason": "no reader for the image route yet: nothing was read",
      "check": null,
      "links": {
        "drawing": "/api/drawings/3b3ce7db34257f63?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/3b3ce7db34257f63/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f4/trace",
        "checks": null
      }
    },
    {
      "id": "refused_answer-3b5adbf71a63",
      "kind": "refused_answer",
      "severity": "note",
      "state": "open",
      "drawing_id": "3b3ce7db34257f63",
      "file": "scans/ground-floor.png",
      "file_id": "f4",
      "floor": null,
      "page": null,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "No answer to \"How many doors are there?\": the drawing has no reader for it.",
      "quantity": null,
      "question": "How many doors are there?",
      "reason": null,
      "check": null,
      "links": {
        "drawing": "/api/drawings/3b3ce7db34257f63?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/3b3ce7db34257f63/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f4/trace",
        "checks": null
      }
    },
    {
      "id": "reading_flag-2b11c57c0ff6",
      "kind": "reading_flag",
      "severity": "note",
      "state": "open",
      "drawing_id": "37f6819bd17d65d9",
      "file": "photos/plan-photo.jpg",
      "file_id": "f6",
      "floor": null,
      "page": 1,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "A phone photo, read without perspective correction; no reader for the image route yet: nothing was read.",
      "quantity": null,
      "question": null,
      "reason": "a phone photo, read without perspective correction; no reader for the image route yet: nothing was read",
      "check": null,
      "links": {
        "drawing": "/api/drawings/37f6819bd17d65d9?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/37f6819bd17d65d9/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f6/trace",
        "checks": null
      }
    },
    {
      "id": "set_aside-02a5f0314890",
      "kind": "set_aside",
      "severity": "note",
      "state": "open",
      "drawing_id": null,
      "file": "photos/site.jpg",
      "file_id": "f7",
      "floor": null,
      "page": null,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "Set aside at ingest: a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink, camera EXIF (SyntheticPhone Model 1)).",
      "quantity": null,
      "question": null,
      "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink, camera EXIF (SyntheticPhone Model 1))",
      "check": null,
      "links": {
        "drawing": null,
        "takeoff": null,
        "trace": "/api/projects/5e0c1a2b3d4f/files/f7/trace",
        "checks": null
      }
    },
    {
      "id": "set_aside-ac138023ff60",
      "kind": "set_aside",
      "severity": "note",
      "state": "open",
      "drawing_id": null,
      "file": "cad/detail.dxf",
      "file_id": "f9",
      "floor": null,
      "page": null,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "Set aside at ingest: no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on.",
      "quantity": null,
      "question": null,
      "reason": "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on",
      "check": null,
      "links": {
        "drawing": null,
        "takeoff": null,
        "trace": "/api/projects/5e0c1a2b3d4f/files/f9/trace",
        "checks": null
      }
    }
  ]
}
```

#### `GET /api/projects/{project_id}/issues.csv?pack=`

The same issues as CSV (`text/csv; charset=utf-8`), saved as `<project name>-issues[-<pack>].csv`. Columns:
`id,kind,severity,state,file,file_id,drawing_id,floor,page,x0,y0,x1,y1,mark_id,why,quantity,question,reason,check`.
A missing value is an empty cell, and the polygon is left out. A text cell starting with `=`, `+`, `-` or `@` is
written with a leading `'`, as in the takeoff CSV.

#### `GET /api/projects/{project_id}/issues.zip?pack=`

The issues with the floor plans, saved as `<project name>-issues[-<pack>].zip`:

- `issues.csv`: the CSV above with a first column `n`, the issue's number in the list.
- One PNG per drawing page that has issues with a box, named `<file stem>-p<page>.png` (`-2`, `-3`… when two files
  share a stem). It is the page at 1600 px with each such issue drawn (its polygon, else its box), coloured by
  severity and labelled with its `n`. Under the page are the issues' sentences, a colour key and the drawing's
  licence credit.
- An issue with no page or no box is only in the CSV, and a page with no such issue has no PNG.

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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
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
        "reason": null,
        "room_type": null
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
        "reason": null,
        "room_type": null
      }
    ],
    "signed": null,
    "unlocated": {},
    "noun": "doors"
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
      "reason": null,
      "room_type": null
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
      "reason": null,
      "room_type": null
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
    "sure": null,
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
      },
      "scale": {
        "status": "no_scale",
        "text": null,
        "ratio": null,
        "source": null
      },
      "scale_text": null,
      "storey": null
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
        "reason": null,
        "room_type": null
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
        "reason": null,
        "room_type": null
      }
    ],
    "signed": null,
    "unlocated": {},
    "noun": "doors"
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
      "reason": null,
      "room_type": null
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
      "reason": null,
      "room_type": null
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
    "sure": null,
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

### `POST /api/projects/{project_id}/ask`

A question on the whole project, for a chat with no drawing picked. The body is `{"question": "<text>"}` (1 to
2000 characters). The question is asked on every drawing of the project (the `drawings` of
`GET /api/projects/{id}`) exactly as `POST /api/ask` asks it with that `project_id`, so each part is the answer
that call gives, the project's review edits applied. An unknown project is 404; a project that is not `done` yet
(queued, running or failed) is 409 `not-allowed`.

- `parts`: one per drawing, `{drawing_id, name, answer}`: `name` is the drawing's file as the project uploaded it
  and `answer` is the full `POST /api/ask` response. The drawings that answered come first, then those that
  refused (with their `answer.refusal`), each group in the project's order.
- `total`, `total_unit`: when exactly one drawing answered, its value. When several did, their values added up, but
  only when the backend knows the drawings show different parts of the building: sheets of the same IFC model,
  each showing a different storey. A flat drawn twice (a PDF and its IFC model, as in the sample) would otherwise be
  counted twice. The question must also be a count, or an area or length over each whole drawing, in one unit.
  Null otherwise: no drawing answered, the drawings may show the same rooms, the question is about one room (two
  kitchens on two drawings are two parts, not one sum), the answer came from a printed table, or the units differ.
  The total only adds the parts' `answer` values.
- `total_sure`: true only when there is a total and every part in it is sure (`answer.line.sure`); false
  otherwise.
- `total_note`: one plain sentence to show with the total, or instead of it: what was added over how many drawings,
  how many of the summed parts need a double-check (the methods disagree, or a person still has to settle it), or
  why there is no total, and which drawings gave no answer and why, e.g. `2 doors from 1 drawing.` or `3 drawings
  answered; they may show the same rooms, so the numbers are not added up; 2 drawings have no reader for it.`
- The question is kept in the project's question list (`GET /api/projects/{id}/questions`) as one line per drawing
  that answered, with its own `answer` and `unit`, or one refused line per drawing when none answered; its lines
  share one `project_ask` id.

The door count on the sample project, trimmed to three of its five parts (two that answered, one refused) with two
marks each; the note is over all five (the sample's flat-a.pdf and model/house.ifc draw the same flat, so there
is no total):

<!-- fixture: project_ask.json -->
```json
{
  "question": "How many doors are there?",
  "parts": [
    {
      "drawing_id": "adeefbbcc17559fc",
      "name": "plans/flat-a.pdf",
      "answer": {
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
            "normalised": null,
            "scale": {
              "status": "scaled",
              "text": "1:100",
              "ratio": 100.0,
              "source": "sheet text 1:100; no scale bar found"
            },
            "scale_text": "1:100",
            "storey": null
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
              "reason": null,
              "room_type": null
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
              "reason": null,
              "room_type": null
            }
          ],
          "signed": null,
          "unlocated": {},
          "noun": "doors"
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
            "reason": null,
            "room_type": null
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
            "reason": null,
            "room_type": null
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
          "sure": null,
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
    },
    {
      "drawing_id": "6d153ea15dca9ab4",
      "name": "plans/flat-b.pdf",
      "answer": {
        "question": "How many doors are there?",
        "drawing_id": "6d153ea15dca9ab4",
        "file": "plans/flat-b.pdf",
        "pages": [
          {
            "page": 1,
            "width": 600.0,
            "height": 400.0,
            "unit": "pt",
            "url": "/api/drawings/6d153ea15dca9ab4/pages/1.png",
            "normalised": null,
            "scale": {
              "status": "scaled",
              "text": "1:100",
              "ratio": 100.0,
              "source": "sheet text 1:100; no scale bar found"
            },
            "scale_text": "1:100",
            "storey": null
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
              "reason": null,
              "room_type": null
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
              "reason": null,
              "room_type": null
            }
          ],
          "signed": null,
          "unlocated": {},
          "noun": "doors"
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
            "reason": null,
            "room_type": null
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
            "reason": null,
            "room_type": null
          }
        ],
        "refusal": null,
        "method": "takeoff",
        "explanation": null,
        "reader": {
          "route": "vector",
          "source": "plans/flat-b.pdf",
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
              "file": "plans/flat-b.pdf",
              "page": 1,
              "box": [
                0.49333,
                0.225,
                0.50667,
                0.275
              ]
            },
            {
              "file": "plans/flat-b.pdf",
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
          "sure": null,
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
    },
    {
      "drawing_id": "3b3ce7db34257f63",
      "name": "scans/ground-floor.png",
      "answer": {
        "question": "How many doors are there?",
        "drawing_id": "3b3ce7db34257f63",
        "file": "scans/ground-floor.png",
        "pages": [
          {
            "page": 1,
            "width": 1200.0,
            "height": 850.0,
            "unit": "px",
            "url": "/api/drawings/3b3ce7db34257f63/pages/1.png",
            "normalised": {
              "exif": null,
              "rotated": 0,
              "deskew_deg": 0.0,
              "rectified": false,
              "quad": null,
              "width": 1200,
              "height": 850,
              "rectifier": null
            },
            "scale": {
              "status": "no_scale",
              "text": null,
              "ratio": null,
              "source": null
            },
            "scale_text": null,
            "storey": null
          }
        ],
        "answer": null,
        "unit": null,
        "confidence": null,
        "quantity": null,
        "marks": [],
        "refusal": {
          "code": "no-reader",
          "text": "Nothing was read from this sheet: there is no reader for this kind of sheet yet.",
          "can_answer": []
        },
        "method": "refused:not-in-drawing",
        "explanation": "the drawing model does not give door",
        "reader": {
          "route": "raster",
          "source": "scans/ground-floor.png",
          "extractor": "hello",
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
          "method": "refused:not-in-drawing",
          "cost_usd": 0.0,
          "latency_s": 0.002,
          "confidence": null,
          "sure": null,
          "abstain": true,
          "explanation": "the drawing model does not give door",
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
    }
  ],
  "total": null,
  "total_unit": null,
  "total_sure": false,
  "total_note": "3 drawings answered; they may show the same rooms, so the numbers are not added up; 2 drawings have no reader for it."
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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
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
      "text": "every room that is not outdoor; shafts, lifts and stairwells are counted in, though the question says shafts are left out"
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
        "reason": null,
        "room_type": "kitchen"
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
        "reason": null,
        "room_type": "storage"
      }
    ],
    "signed": null,
    "unlocated": {},
    "noun": null
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
      "reason": null,
      "room_type": "kitchen"
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
      "reason": null,
      "room_type": "storage"
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
    "sure": null,
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
    "unlocated": {},
    "noun": "doors"
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
    "sure": null,
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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
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
    "sure": null,
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
| `no-reader` | nothing was read from the sheet (no reader for its route yet: the text says so; a reader that found nothing says that instead), that reader is less reliable than a guess for this kind of question (`prior:policy`), the page was flagged at upload (a phone photo, a scan) and its reader found no element or no room at all for what was asked, or a room question on a raster page (an image, a photo, a scanned PDF; flagged or not) whose reader found no room at all: 0 would be a guess |
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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
    }
  ],
  "answer": 30.0,
  "unit": "m2",
  "confidence": null,
  "quantity": {
    "key": "area:room|name=1.01",
    "label": "area of room (name Küche · 1.01)",
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
        "reason": null,
        "room_type": "kitchen"
      }
    ],
    "signed": null,
    "unlocated": {},
    "noun": null
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
      "reason": null,
      "room_type": "kitchen"
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
    "sure": null,
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
      "normalised": null,
      "scale": {
        "status": "scaled",
        "text": "1:100",
        "ratio": 100.0,
        "source": "sheet text 1:100; no scale bar found"
      },
      "scale_text": "1:100",
      "storey": null
    }
  ],
  "answer": 30.0,
  "unit": "m2",
  "confidence": null,
  "quantity": {
    "key": "area:room|name=1.01",
    "label": "area of room (name Küche · 1.01)",
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
        "reason": null,
        "room_type": "kitchen"
      }
    ],
    "signed": {
      "by": "Ana",
      "at": "2026-11-14T08:05:00Z",
      "value": 30.0
    },
    "unlocated": {},
    "noun": null
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
      "reason": null,
      "room_type": "kitchen"
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
    "sure": null,
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
      "normalised": null,
      "scale": {
        "status": "no_scale",
        "text": null,
        "ratio": null,
        "source": "no scale text and no scale bar on the sheet"
      },
      "scale_text": null,
      "storey": null
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
      "reason": null,
      "room_type": null
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
    "sure": null,
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
      "label": "area of room (name Küche · 1.01)",
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
          "reason": null,
          "room_type": "kitchen"
        }
      ],
      "signed": null,
      "unlocated": {},
      "noun": null
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
          "reason": null,
          "room_type": null
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
          "reason": null,
          "room_type": null
        }
      ],
      "signed": null,
      "unlocated": {},
      "noun": "doors"
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
        "text": "every room that is not outdoor; shafts, lifts and stairwells are counted in, though the question says shafts are left out"
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
          "reason": null,
          "room_type": "kitchen"
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
          "reason": null,
          "room_type": "storage"
        }
      ],
      "signed": null,
      "unlocated": {},
      "noun": null
    }
  ],
  "review_queue": [
    "area:room|name=1.01"
  ],
  "disputes": [
    "area:room|name=1.01"
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
- `disputes`: the keys of the rows where two methods disagree (`conflict` set, settled or not), one per
  disagreement: a storey's row or a room's other name that repeats another row's disagreement is left out. These
  are the drawing's entries in `GET /api/projects/{id}/review` `conflicts`; count these, not the rows.
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
  },
  {
    "quantity": "door",
    "action": "unsettle"
  }
]
```

- `reject` / `restore`: leave a mark out of the count or the sum, or put it back. Rejecting an added mark removes
  it. `restore` on an `excluded` mark (`x1`…) counts it in; `reject` on it leaves it out again.
- `add`: a missed item, on a count only. The new mark gets an id `a1`, `a2`…
- `settle`: the value to keep (one of the conflict's values, or any value the surveyor counted). It holds until
  the next mark edit of that quantity.
- `unsettle`: drop the settled value of the quantity and nothing else: mark edits and the rest of the drawing stay
  (`reset` also drops them and the sign-off). Needs `quantity`; nothing settled is not an error; a signed-off
  quantity is 409 as for any edit.
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

`"settle": true` (optional) first keeps the quantity's current value as its settled value, then signs it off, for a
"Looks right" button: a conflict no rule decides is signed in one call, with no `needs_person` 409. The 409 for a
signed-off quantity is the same; `settle` together with `undo` is 422 `invalid`.

<!-- fixture: signoff_settle_request.json -->
```json
{
  "quantity": "area:room|name=1.01",
  "by": "Ana",
  "settle": true
}
```

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
          "reason": null,
          "room_type": null
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
          "reason": null,
          "room_type": null
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
          "reason": null,
          "room_type": null
        }
      ],
      "signed": null,
      "unlocated": {},
      "noun": "doors"
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
          "reason": null,
          "room_type": null
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
          "reason": null,
          "room_type": null
        }
      ],
      "signed": null,
      "unlocated": {},
      "noun": "windows"
    },
    {
      "key": "area:room|name=1.01",
      "label": "area of room (name Küche · 1.01)",
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
          "reason": null,
          "room_type": "kitchen"
        }
      ],
      "signed": {
        "by": "Ana",
        "at": "2026-11-14T08:05:00Z",
        "value": 30.0
      },
      "unlocated": {},
      "noun": null
    }
  ],
  "review_queue": [],
  "disputes": [
    "area:room|name=1.01"
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

## Building-code checks

A pre-check of a few rules, not a compliance certificate (story #139, decision
[0009](decisions/0009-building-code-checks.md)). The screen picks one pack from `GET /api/info` `rule_packs` and
passes its id as `pack` (required; one pack at a time). The check runs on each request over the drawing model as
ingest read it; review edits don't change it.

### `GET /api/drawings/{drawing_id}/checks?pack=<pack id>&project=<project_id>`

<!-- fixture: checks.json -->
```json
{
  "drawing_id": "5c4ed01e00000002",
  "file": "flat-fi.pdf",
  "file_id": "f1",
  "pack": "fi",
  "note": "A pre-check of a few rules, not a compliance certificate.",
  "status": "fail",
  "rules": [
    {
      "rule_id": "fi-habitable-room-area",
      "title": "A bedroom or living room is at least 7 m2",
      "status": "fail",
      "why": "Of 3 checked: 1 fail, 2 pass.",
      "clause": {
        "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 1008/2017, 4 § 2 mom.",
        "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008",
        "quote": "Asuin-, majoitus- ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
        "quote_en": "The room area of a residential, accommodation or work space must, however, always be at least 7 square metres."
      },
      "results": [
        {
          "id": "fi-habitable-room-area:r2",
          "rule_id": "fi-habitable-room-area",
          "status": "fail",
          "subject": {
            "kind": "room",
            "ref": "r2",
            "label": "Schlafzimmer 4.02"
          },
          "value": 6.03,
          "limit": 7.0,
          "unit": "m2",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The bedroom \"Schlafzimmer 4.02\" is 6.03 m2; the rule asks at least 7 m2. It would not meet today's rule for a new building.",
          "quantity": "area:room|name=4.02",
          "marks": [
            {
              "page": 1,
              "box": [
                0.28833,
                0.15,
                0.43,
                0.2925
              ],
              "polygon": [
                [
                  0.28833,
                  0.15
                ],
                [
                  0.28833,
                  0.2925
                ],
                [
                  0.43,
                  0.2925
                ],
                [
                  0.43,
                  0.15
                ]
              ],
              "ref": "r2",
              "label": "Schlafzimmer 4.02",
              "role": "subject",
              "quantity": "area:room|name=4.02",
              "mark_id": "m1"
            }
          ]
        },
        {
          "id": "fi-habitable-room-area:r3",
          "rule_id": "fi-habitable-room-area",
          "status": "pass",
          "subject": {
            "kind": "room",
            "ref": "r3",
            "label": "Wohnen 4.03"
          },
          "value": 19.97,
          "limit": 7.0,
          "unit": "m2",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The living room \"Wohnen 4.03\" is 19.97 m2; the rule asks at least 7 m2.",
          "quantity": "area:room|name=4.03",
          "marks": [
            {
              "page": 1,
              "box": [
                0.43,
                0.15,
                0.66667,
                0.4325
              ],
              "polygon": [
                [
                  0.43,
                  0.15
                ],
                [
                  0.43,
                  0.4325
                ],
                [
                  0.66667,
                  0.4325
                ],
                [
                  0.66667,
                  0.15
                ]
              ],
              "ref": "r3",
              "label": "Wohnen 4.03",
              "role": "subject",
              "quantity": "area:room|name=4.03",
              "mark_id": "m1"
            }
          ]
        }
      ]
    },
    {
      "rule_id": "fi-habitable-room-window",
      "title": "A bedroom or living room has a window",
      "status": "fail",
      "why": "Of 3 checked: 1 fail, 2 pass.",
      "clause": {
        "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 1008/2017, 5 § 1 mom. (as amended by 127/2018)",
        "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008",
        "quote": "Asuin- ja, majoitustilan ikkunan valoaukon on oltava vähintään 1/10 huonealasta.",
        "quote_en": "The light opening of the window of a residential or accommodation space must be at least 1/10 of the room area."
      },
      "results": [
        {
          "id": "fi-habitable-room-window:r2",
          "rule_id": "fi-habitable-room-window",
          "status": "fail",
          "subject": {
            "kind": "room",
            "ref": "r2",
            "label": "Schlafzimmer 4.02"
          },
          "value": 0.0,
          "limit": 1.0,
          "unit": "count",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The bedroom \"Schlafzimmer 4.02\" has no window on its outline; the rule asks at least 1. It would not meet today's rule for a new building.",
          "quantity": "area:room|name=4.02",
          "marks": [
            {
              "page": 1,
              "box": [
                0.28833,
                0.15,
                0.43,
                0.2925
              ],
              "polygon": [
                [
                  0.28833,
                  0.15
                ],
                [
                  0.28833,
                  0.2925
                ],
                [
                  0.43,
                  0.2925
                ],
                [
                  0.43,
                  0.15
                ]
              ],
              "ref": "r2",
              "label": "Schlafzimmer 4.02",
              "role": "subject",
              "quantity": "area:room|name=4.02",
              "mark_id": "m1"
            }
          ]
        },
        {
          "id": "fi-habitable-room-window:r3",
          "rule_id": "fi-habitable-room-window",
          "status": "pass",
          "subject": {
            "kind": "room",
            "ref": "r3",
            "label": "Wohnen 4.03"
          },
          "value": 1.0,
          "limit": 1.0,
          "unit": "count",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The living room \"Wohnen 4.03\" has 1 window on its outline; the rule asks at least 1.",
          "quantity": "area:room|name=4.03",
          "marks": [
            {
              "page": 1,
              "box": [
                0.43,
                0.15,
                0.66667,
                0.4325
              ],
              "polygon": [
                [
                  0.43,
                  0.15
                ],
                [
                  0.43,
                  0.4325
                ],
                [
                  0.66667,
                  0.4325
                ],
                [
                  0.66667,
                  0.15
                ]
              ],
              "ref": "r3",
              "label": "Wohnen 4.03",
              "role": "subject",
              "quantity": "area:room|name=4.03",
              "mark_id": "m1"
            },
            {
              "page": 1,
              "box": [
                0.5,
                0.14,
                0.6,
                0.155
              ],
              "polygon": null,
              "ref": "e5",
              "label": "window",
              "role": "counted",
              "quantity": "window",
              "mark_id": "m2"
            }
          ]
        }
      ]
    },
    {
      "rule_id": "fi-door-clear-width",
      "title": "A door to a habitable room is at least 0.80 m clear",
      "status": "fail",
      "why": "Of 3 checked: 1 fail, 1 cannot tell, 1 pass.",
      "clause": {
        "ref": "Valtioneuvoston asetus rakennuksen esteettömyydestä 241/2017, 4 § 2 mom.",
        "url": "https://www.finlex.fi/fi/lainsaadanto/2017/241",
        "quote": "Muun rakennuksen kuin asuinrakennuksen huonetiloihin sekä asuinrakennuksen asuinhuoneisiin, asumista palveleviin välttämättömiin tiloihin ja rakennuksen käyttöä palveleviin tiloihin johtavan oven ja kulkuaukon vapaan leveyden on oltava vähintään 800 millimetriä.",
        "quote_en": "The clear width of a door or passage opening leading to the rooms of a building other than a residential building, and to the habitable rooms of a residential building, the necessary spaces serving the dwelling and the spaces serving the use of the building, must be at least 800 millimetres."
      },
      "results": [
        {
          "id": "fi-door-clear-width:e2",
          "rule_id": "fi-door-clear-width",
          "status": "fail",
          "subject": {
            "kind": "element",
            "ref": "e2",
            "label": "the door between the bedroom \"Schlafzimmer 4.01\" and the bedroom \"Schlafzimmer 4.02\""
          },
          "value": 0.706,
          "limit": 0.8,
          "unit": "m",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The door between the bedroom \"Schlafzimmer 4.01\" and the bedroom \"Schlafzimmer 4.02\": its symbol measures 0.71 m, so its clear opening cannot be at least 0.8 m. It would not meet today's rule for a new building.",
          "quantity": "door",
          "marks": [
            {
              "page": 1,
              "box": [
                0.28167,
                0.2,
                0.295,
                0.25
              ],
              "polygon": null,
              "ref": "e2",
              "label": "door",
              "role": "subject",
              "quantity": "door",
              "mark_id": "m2"
            }
          ]
        },
        {
          "id": "fi-door-clear-width:e3",
          "rule_id": "fi-door-clear-width",
          "status": "cannot_tell",
          "subject": {
            "kind": "element",
            "ref": "e3",
            "label": "the door between the living room \"Wohnen 4.03\" and the hall \"Korridor 4.04\""
          },
          "value": 0.847,
          "limit": 0.8,
          "unit": "m",
          "comparison": ">=",
          "comparison_text": "at least",
          "why": "The door between the living room \"Wohnen 4.03\" and the hall \"Korridor 4.04\": its symbol measures 0.85 m; its clear opening is up to 10 cm (our allowance for the frame, not the law's) less, so it may or may not be at least 0.8 m.",
          "quantity": "door",
          "marks": [
            {
              "page": 1,
              "box": [
                0.42333,
                0.3725,
                0.43667,
                0.4325
              ],
              "polygon": null,
              "ref": "e3",
              "label": "door",
              "role": "subject",
              "quantity": "door",
              "mark_id": "m3"
            }
          ]
        }
      ]
    }
  ]
}
```

- `file` and `file_id` are the file as `project` uploaded it (a drawing shared by two projects is named as each
  uploaded it); without `project`, the drawing's stored name and `file_id` null.
- `status` (the drawing's) and each rule's `status`: `fail` when one result fails, else `cannot_tell` when one
  cannot tell, else `pass`; `not_applicable` when the drawing has nothing the rule applies to (rooms were read and
  none is a bedroom; no door leads to a habitable room). A rule with no results and `cannot_tell` could not be
  checked at all (`why` says what was not read, or that rooms are of a kind we could not tell and may be ones the
  rule names). A building model file is `not_applicable` ("checked on its sheets") when its sheets are in
  `project`, else `cannot_tell`.
- A result is one rule on one room, door or the sheet: `status` is `pass`, `fail` or `cannot_tell`; `id` is
  `<rule_id>:<room or element id>` (`:sheet` for a sheet quantity), the same on every call for the same drawing.
  `value` is what was measured, in `unit`; null when nothing was measured; a value too uncertain to judge is kept
  with `cannot_tell`. `why` is one plain sentence (a fail ends with the pack's `fail_means`).
- `quantity` is the subject's takeoff row (`Row.key`) for the surveyor's view, null when the takeoff has none.
  Each mark has `role` (`subject`: the room or door checked; `counted`: what was counted for it, a room's windows),
  `page`, `box`, `polygon` (a room's outline, else null), `ref` (the room or element id), `label`, and its
  takeoff row `quantity` with `mark_id`, its `MarkView.id` in that row (the row's own ids; null when the takeoff
  has no row with it).
- A fail stands only on reliable inputs: on a drawing read off a picture (route `raster`, or a route not known) a
  small room from a read outline and a room with no window found are `cannot_tell`, never `fail`; a printed area
  still decides. A door there is `cannot_tell` whatever its box measures. A door's width is measured from its symbol (or the building model), which bounds the clear opening
  from above; the 0.10 m allowed for the frame is ours, not the law's, and the `why` says so.

### `GET /api/projects/{project_id}/checks?pack=<pack id>`

<!-- fixture: project_checks.json -->
```json
{
  "project_id": "5e0c1a2b3d53",
  "pack": "fi",
  "note": "A pre-check of a few rules, not a compliance certificate.",
  "status": "fail",
  "drawings": [
    {
      "drawing_id": "5c4ed01e00000002",
      "file": "flat-fi.pdf",
      "file_id": "f1",
      "pack": "fi",
      "note": "A pre-check of a few rules, not a compliance certificate.",
      "status": "fail",
      "rules": [
        {
          "rule_id": "fi-habitable-room-area",
          "title": "A bedroom or living room is at least 7 m2",
          "status": "fail",
          "why": "Of 3 checked: 1 fail, 2 pass.",
          "clause": {
            "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 1008/2017, 4 § 2 mom.",
            "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008",
            "quote": "Asuin-, majoitus- ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
            "quote_en": "The room area of a residential, accommodation or work space must, however, always be at least 7 square metres."
          },
          "results": [
            {
              "id": "fi-habitable-room-area:r2",
              "rule_id": "fi-habitable-room-area",
              "status": "fail",
              "subject": {
                "kind": "room",
                "ref": "r2",
                "label": "Schlafzimmer 4.02"
              },
              "value": 6.03,
              "limit": 7.0,
              "unit": "m2",
              "comparison": ">=",
              "comparison_text": "at least",
              "why": "The bedroom \"Schlafzimmer 4.02\" is 6.03 m2; the rule asks at least 7 m2. It would not meet today's rule for a new building.",
              "quantity": "area:room|name=4.02",
              "marks": [
                {
                  "page": 1,
                  "box": [
                    0.28833,
                    0.15,
                    0.43,
                    0.2925
                  ],
                  "polygon": [
                    [
                      0.28833,
                      0.15
                    ],
                    [
                      0.28833,
                      0.2925
                    ],
                    [
                      0.43,
                      0.2925
                    ],
                    [
                      0.43,
                      0.15
                    ]
                  ],
                  "ref": "r2",
                  "label": "Schlafzimmer 4.02",
                  "role": "subject",
                  "quantity": "area:room|name=4.02",
                  "mark_id": "m1"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

Every drawing of the project (in `GET /api/projects/{id}` `drawings` order), each as above with this project's
`file` and `file_id`; `status` over the drawings as a drawing's is over its rules. 409 `not-allowed` until the
project is `done` (a drawing's own checks answer as soon as that drawing exists); 404 `unknown-pack` for an
unknown pack, `not-found` for an unknown project.

## What is not in v1

- Contested marks: a conflict is shown per quantity, with both values and, where the method has one, the `box` it
  read; the frontend does not build an amber per-item mark.
- Adding a mark with a value to an area or length (marks are added to counts only).
- Free page widths, CORS, server push (progress is polled).
- Editing a room's outline or label.

## Changelog

- 2026-11-14, additive (story #139, decision 0009): `GET /api/info` gains `rule_packs` (the building-code packs,
  `[]` when none is installed). New `GET /api/drawings/{id}/checks?pack=&project=` and
  `GET /api/projects/{id}/checks?pack=`. An unknown pack is 404 `unknown-pack`, as for the issues.
  `GET /api/projects/{id}/issues?pack=` (and `.csv`, `.zip`) now lists the pack's failed checks as
  `code_check_failed` issues (severity `fails_rule`, `links.checks` set); without a pack the list is unchanged.
- 2026-11-14, additive (decision 0010, board #152 c6876693460): `POST /api/projects/{project_id}/files/{file_id}/triage`
  reads a file triage set aside as a floor plan (202, in the background); `Triage.read_as_plan`; a new error code
  `not-triaged` (422).
- 2026-11-14, additive (decision 0010, file triage; board #152): `FileStatus.triage` (class, P(plan), method,
  description, relevance, a person's call, the verdict that counts, and a note when something is null),
  `ProjectView.not_plans` and `ProjectSummary.not_plans`, all left out of the JSON when triage is off (the
  default); `POST /api/projects/{project_id}/files/{file_id}/relevance`; the `unrelated_file` issues; a new error
  code `no-description` (422). No new `FileState` or `Stage`.
- 2026-11-14, text only (QA R4-a-10): a file's `reason` and the route stage's `did` name the route in the words the
  screens use ("read on the drawn PDF route: …", "no reader for the image route yet", "BIM model route, read from
  …"; was "vector", "raster", "bim"), from `ROUTE_WORDS` in `app/core/wording.py`. The fields `route` and the route
  stage's `output` keep the id.
- 2026-11-14, additive (QA R4-a-8): `Takeoff.disputes`, the keys of the rows where two methods disagree, one per
  disagreement, the same ones the project review lists. Behaviour (QA R4-a-1): `ProjectView.expected_drawings` is
  null while a running project's files are not grouped yet, then final (it overshot, 0/19 then 13/13 on the demo
  zip, because each rendering counted until its group was read); groups of only DXF or SVG files no longer count,
  and a file set aside after grouping still does. Ingest records every file's group before reading the first group.
- 2026-11-14, additive (story #140, decision 0008, Tudor's review #142): `GET /api/projects/{id}/issues?pack=`,
  `issues.csv` and `issues.zip` (every finding as a located issue; the zip adds the pages with the issues marked);
  `ProjectSummary.issues_open`; the question list's lines carry `refusal` (the refusal code) when refused; a new
  error code `unknown-pack` (404). `Issue.kind` lists every planned kind, three of them not produced yet.
- 2026-11-14, additive (board #14, the project chat): `POST /api/projects/{project_id}/ask` with `{question}`
  returns `{question, parts: [{drawing_id, name, answer}], total, total_unit, total_sure, total_note}`, each part
  the `POST /api/ask` answer on one drawing of the project; a total only for one answering drawing or for drawings
  known to show different storeys of one model. `GET /api/projects/{id}/questions` lines gain an optional
  `project_ask` (the id grouping one project question's lines; absent on `POST /api/ask` lines).
- 2026-11-14, text and behaviour (board #14, pre-QA sweep): a room the takeoff keys under several names (number,
  name, "name (number)") is one conflict in `GET /api/projects/{id}/review`, one entry in `review_queue` and one
  decision: settling or signing any of its rows settles and signs them all (the rows stay, each with its own
  `key`). A room's rows are labelled with its printed name ("area of room (name Küche)"; the row of its
  number "area of room (name Küche · 1.01)", was "(name 1.01)"). `ProjectSummary.conflicts_open` is the conflicts a person still has to settle
  (`needs_person`: the methods disagree, no rule decides, nobody settled it), no longer those a rule decided or a
  person settled; `to_review` is unchanged. A `no-reader` refusal on a route with no reader (the stand-in) says
  "there is no reader for this kind of sheet yet", not that a reader found no elements.
- 2026-11-14, text only (board #14 c6875409494): the human text of a file's `reason` and of the stage lines in
  its trace (`did`, `output`) reads in plain words, no field changes. Counts agree with their number ("1 conflict",
  "2 files", "1 page", "1 plan", "1 quantity"; was "1 conflict(s)", "2 file(s)", "1 page(s)", "1 plans",
  "1 quantities"). The scale in them is a sentence by its status ("scale read from the sheet", "no scale on the
  sheet", "sheet says it is not to scale", "scale estimated"; was "scale scaled"); `scale.status` is unchanged. The
  `identify` stage's `output` is the kind in words ("drawn PDF", "scanned PDF", "PNG drawing", "photo of a
  drawing"...; was "pdf_vector"); `FileStatus.kind` is unchanged.
- 2026-11-14, additive (board #14): `POST /api/drawings/{id}/signoff` takes an optional `settle: true`: the
  quantity's current value is settled and signed off in one call (same 409 rules; with `undo` it is 422).
- 2026-11-14, additive (the Vellum redesign's fields, part 2, board #14): review action `unsettle` (drops the settled
  value only, `Edit.action` gains the value). `ProjectSummary.to_review` and `conflicts_open`: quantities left to
  review over the project's drawings, and conflicts nobody settled or signed off; null unless the project is `done`.
  `GET /api/projects/{id}/questions`: `{project_id, questions: [{question, answer, unit, drawing_id, at, refused}]}`,
  the asks that named the project, newest first; a new store in `<projects_dir>/api/questions/<project id>.jsonl`.
- 2026-11-14, additive (the Vellum redesign's fields, board #14), all optional:
  - `ProjectView.started_at` / `finished_at`: ISO 8601 UTC, when the run began (after the queue) and ended,
    done or failed; null until then. Elapsed is `now - started_at`; there is no `eta_ms` (file times differ too much to
    estimate honestly).
  - `ProjectView.skipped`: `[{path, reason}]`, the files with state `set_aside`, in upload order (empty list if none).
  - `ProjectView.expected_drawings`: the drawings the upload holds, one per group of renderings that has a sheet
    (PDF, PNG, JPEG, photo of a plan) or a model (IFC), and one for a copy under another name. null while the project
    is `queued` and while a file of a `running` project is not grouped yet (until then a plan's renderings would each
    count as a drawing); once known it is final and never drops: a file set aside after it was grouped still counts,
    so it can be above `drawings.length` when a drawing file fails. A group of only DXF or SVG files gives no drawing.
  - `GET /api/projects/{id}/trace`: `{project_id, files: FileTrace[]}`, every file's trace in upload order.
  - `second_count` on a file's trace (both trace routes): `{measured, conflicts}`, the quantities the second method
    measured and how many of them disagree; null when the file has no drawing yet or nothing was measured twice.
    The same numbers as the "second count" line of the trace.
  - `PageView.scale`: `{status, text, ratio, source}` of the drawing's scale (the same on each page); `ratio` is N of
    a printed "1:N", null when the text is no bare ratio. `PageView.scale_text`: `scale.text`. `PageView.storey`: the
    storey of the plan on that page as text, null when the page has no plan, or plans of several storeys.
  - `MarkView.room_type`: the room's type for a room mark, null for an element or an added mark.
  - `Row.noun`: what a count is of, to write after the number: "doors", "door" at 1; null for an area or a count
    that is not of one element class (rooms, combined counts). Follows the row's current `value`.
  - `ConflictEntry.signed` (`SignOff` or null) and `ConflictEntry.value` (the value in use: edits and the
    settled value applied).
- 2026-11-14, additive: `line.sure` (answer_v1.1): true when the answer's `g1main` score is at or above
  its family's threshold in golden's gate file (`GATE_POLICY`, chosen on val and certified once on test),
  false below it, null when there is no score (a vector or IFC page), the family is not gated or the gate is
  off. `POST /api/ask` sets it too.
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
