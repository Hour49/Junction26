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
| A relevance call on, or reading as a floor plan, a file triage did not set aside as not a floor plan | 422 `not-triaged` |
| `reject`/`restore` without `mark`, `add` without `page` and `box` or on a page the drawing does not have, `add` to an area or length, `settle` without `value` or `note`, a width that is not 400, 1600 or 3200 | 422 `invalid` |
| A body that does not fit the request model (no `name` on an upload, an empty question, an unknown action, a `note` on an edit other than `settle`, an empty `note` or one over 280 characters) | 422 `validation` |
| Sign-off of a conflict no rule decides and nobody settled; an edit of a signed-off quantity; a relevance call or a read as a floor plan before the project is `done` or while one of its files is read again; reading a file as a floor plan twice | 409 `not-allowed` |
| A project's questions or building-code checks while its ingest is not `done` | 409 `not-allowed` |
| Upload over 200 MB | 413 `too-large` |
| A file added to a project (`POST …/files`) that is not a png or jpeg | 415 `unsupported` |
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
| `POST /api/projects/{project_id}/files?name=` | Add a photo (png or jpeg) to a done project; read in the background | #203 |
| `POST /api/projects/{project_id}/files/{file_id}/relevance` | A person's call on a triaged file: related or unrelated, or undo | 0010 |
| `POST /api/projects/{project_id}/files/{file_id}/triage` | Read a file triage set aside as a floor plan (in the background) | 0010 |
| `GET /api/projects/{project_id}/evidence/search?q=&k=&include_unrelated=` | Search the project's non-plan files by what they show and say (one hit per file) | 0012 |
| `GET /api/projects/{project_id}/evidence/{evidence_id}` | One hit's passage with its file's description | 0012 |
| `GET /api/projects/{project_id}/files/{file_id}/preview.png?width=` | The file as uploaded, EXIF turn applied | #27 |
| `GET /api/projects/{project_id}/files/{file_id}/model.glb` | An IFC file's 3D view (GLB, nodes named by GlobalId); `MODEL_3D` | #14 |
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
| `POST /api/projects/{project_id}/chat` | One turn of the agent chat: tools called, cited sources, plan-edit proposals | 0013 |
| `POST /api/projects/{project_id}/chat/{chat_id}/proposals/{proposal_id}` | Accept or reject a plan-edit proposal | 0013 |
| `GET /api/laws` | The building-law knowledge base: each pack's laws (table of contents) | 0014 |
| `GET /api/laws/{pack}/search?q=&topic=&limit=` | Search one pack's law clauses, best first | 0014 |
| `GET /api/laws/clauses/{clause_id}` | One clause, verbatim and in our English, with its law | 0014 |

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
      "law": "Rakentamislaki 751/2023; decrees 631/2024 (homes and rooms, in force since 2025-01-01, replacing 1008/2017; a project pending then follows the earlier rules, 631/2024 11 § 2 mom.) and 241/2017 (accessibility, as amended by 683/2024)",
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
            "note": "New buildings, extensions and substantial changes of use (decree 631/2024 s. 1); in a repair the original solution may be kept. Habitable rooms only: not a hall, corridor, bathroom or the like (s. 2). A dining nook that is part of an open room (labels R, RT, RH, RUOK, RUOKAILU, Essen, Repas, Pranzo) is not a room of its own and is not checked, nor is an alcove (ALKOVI). Kitchens are left out: a plan does not tell a kitchen (a habitable room) from a kitchenette. Floor under 1.6 m of headroom does not count (s. 2), which a plan does not show."
          },
          "comparison": ">=",
          "comparison_text": "at least",
          "limit": 7.0,
          "unit": "m2",
          "key": null,
          "clause": {
            "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024, 4 § 2 mom.",
            "url": "https://www.finlex.fi/fi/lainsaadanto/2024/631",
            "quote": "Asuin- ja majoitushuoneen ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
            "quote_en": "The room area of a residential or accommodation room and of a work space must, however, always be at least 7 square metres."
          }
        }
      ]
    }
  ],
  "commit": null,
  "chat": {
    "model": "rules",
    "available": true,
    "reason": null,
    "stream": true
  }
}
```

`no_keys: true` when no reader needs an API key or a model server: no `gemini`, `regionrooms`, `verda` or
`decisions` source in `RASTER_COMPONENTS`, `RASTER_PHOTO_COMPONENTS` or `DOUBLE_CHECK_READERS`,
`DECISIONS_CONFIDENCE` and `DECISIONS_KIND` off, and no Gemini describer in file triage
(`TRIAGE_DESCRIBER=gemini` or `carbon` with `TRIAGE_CLASSIFIER` on). The screen then shows "running offline". A reader
named `hello` reads nothing: drawings on that route have no counts, and their questions are refused with the
code `no-reader`. `limits` lets the screen refuse a file before uploading it.

`gemini` is there only when a Gemini spend limit is set (`GEMINI_BUDGET_USD`, `GEMINI_BUDGET_USD_PER_HOUR`):
`ok`, or `budget_exhausted` while the limit is used up. Then every Gemini step (room reader, Decisions count swap
and answer confidence, sheet-kind signal, describer) answers as when Gemini fails: nothing new is read, the
answer stays unknown or unchanged, and the file's trace or the answer's note says "Gemini budget used up".
Replies cached earlier still serve. With the hourly limit it clears as the last hour's spend ages out; with the
total limit only a restart clears it. A limit of 0 refuses every Gemini call from the first one. The screen can
say so instead of showing empty readings.

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
`issues_to_answer`: of those, the ones that wait for a person's answer: not a `note` and no `answer` yet (an answer
does not change an issue's `state`); null until `done`.
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
      "issues_open": 4,
      "issues_to_answer": 0
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
        "area:room:bedroom|largest": 14.934,
        "area:room:kitchen|largest": 22.401,
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
        "bathtub|name=1.01": 0,
        "bathtub|name=1.02": 0,
        "bathtub|name=1.03": 1,
        "bathtub|name=1.04": 0,
        "bathtub|name=1.05": 0,
        "bathtub|name=bad": 1,
        "bathtub|name=balkon": 0,
        "bathtub|name=küche": 0,
        "bathtub|name=reduit": 0,
        "bathtub|name=zimmer": 0,
        "door": 2,
        "door|name=1.01": 1,
        "door|name=1.02": 0,
        "door|name=1.03": 2,
        "door|name=1.04": 0,
        "door|name=1.05": 1,
        "door|name=bad": 2,
        "door|name=balkon": 0,
        "door|name=küche": 1,
        "door|name=reduit": 0,
        "door|name=zimmer": 1,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:bedroom": 4.233,
        "length:room:kitchen": 7.056,
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
        "room:bedroom": 1,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 0,
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
        "shower+bathtub|name=1.01": 0,
        "shower+bathtub|name=1.02": 0,
        "shower+bathtub|name=1.03": 1,
        "shower+bathtub|name=1.04": 0,
        "shower+bathtub|name=1.05": 0,
        "shower+bathtub|name=bad": 1,
        "shower+bathtub|name=balkon": 0,
        "shower+bathtub|name=küche": 0,
        "shower+bathtub|name=reduit": 0,
        "shower+bathtub|name=zimmer": 0,
        "shower|name=1.01": 0,
        "shower|name=1.02": 0,
        "shower|name=1.03": 0,
        "shower|name=1.04": 0,
        "shower|name=1.05": 0,
        "shower|name=bad": 0,
        "shower|name=balkon": 0,
        "shower|name=küche": 0,
        "shower|name=reduit": 0,
        "shower|name=zimmer": 0,
        "sink": 1,
        "sink|name=1.01": 0,
        "sink|name=1.02": 0,
        "sink|name=1.03": 1,
        "sink|name=1.04": 0,
        "sink|name=1.05": 0,
        "sink|name=bad": 1,
        "sink|name=balkon": 0,
        "sink|name=küche": 0,
        "sink|name=reduit": 0,
        "sink|name=zimmer": 0,
        "toilet": 1,
        "toilet|name=1.01": 0,
        "toilet|name=1.02": 0,
        "toilet|name=1.03": 1,
        "toilet|name=1.04": 0,
        "toilet|name=1.05": 0,
        "toilet|name=bad": 1,
        "toilet|name=balkon": 0,
        "toilet|name=küche": 0,
        "toilet|name=reduit": 0,
        "toilet|name=zimmer": 0,
        "window": 2,
        "window|name=1.01": 1,
        "window|name=1.02": 0,
        "window|name=1.03": 0,
        "window|name=1.04": 0,
        "window|name=1.05": 1,
        "window|name=bad": 0,
        "window|name=balkon": 0,
        "window|name=küche": 1,
        "window|name=reduit": 0,
        "window|name=zimmer": 1
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
        "area:room:bedroom|largest": 14.934,
        "area:room:kitchen|largest": 22.401,
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
        "bathtub|name=1.01": 0,
        "bathtub|name=1.02": 0,
        "bathtub|name=1.03": 1,
        "bathtub|name=1.04": 0,
        "bathtub|name=1.05": 0,
        "bathtub|name=bad": 1,
        "bathtub|name=balkon": 0,
        "bathtub|name=küche": 0,
        "bathtub|name=reduit": 0,
        "bathtub|name=zimmer": 0,
        "door": 2,
        "door|name=1.01": 1,
        "door|name=1.02": 0,
        "door|name=1.03": 2,
        "door|name=1.04": 0,
        "door|name=1.05": 1,
        "door|name=bad": 2,
        "door|name=balkon": 0,
        "door|name=küche": 1,
        "door|name=reduit": 0,
        "door|name=zimmer": 1,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:bedroom": 4.233,
        "length:room:kitchen": 7.056,
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
        "room:bedroom": 1,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 0,
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
        "shower+bathtub|name=1.01": 0,
        "shower+bathtub|name=1.02": 0,
        "shower+bathtub|name=1.03": 1,
        "shower+bathtub|name=1.04": 0,
        "shower+bathtub|name=1.05": 0,
        "shower+bathtub|name=bad": 1,
        "shower+bathtub|name=balkon": 0,
        "shower+bathtub|name=küche": 0,
        "shower+bathtub|name=reduit": 0,
        "shower+bathtub|name=zimmer": 0,
        "shower|name=1.01": 0,
        "shower|name=1.02": 0,
        "shower|name=1.03": 0,
        "shower|name=1.04": 0,
        "shower|name=1.05": 0,
        "shower|name=bad": 0,
        "shower|name=balkon": 0,
        "shower|name=küche": 0,
        "shower|name=reduit": 0,
        "shower|name=zimmer": 0,
        "sink": 1,
        "sink|name=1.01": 0,
        "sink|name=1.02": 0,
        "sink|name=1.03": 1,
        "sink|name=1.04": 0,
        "sink|name=1.05": 0,
        "sink|name=bad": 1,
        "sink|name=balkon": 0,
        "sink|name=küche": 0,
        "sink|name=reduit": 0,
        "sink|name=zimmer": 0,
        "toilet": 1,
        "toilet|name=1.01": 0,
        "toilet|name=1.02": 0,
        "toilet|name=1.03": 1,
        "toilet|name=1.04": 0,
        "toilet|name=1.05": 0,
        "toilet|name=bad": 1,
        "toilet|name=balkon": 0,
        "toilet|name=küche": 0,
        "toilet|name=reduit": 0,
        "toilet|name=zimmer": 0,
        "window": 2,
        "window|name=1.01": 1,
        "window|name=1.02": 0,
        "window|name=1.03": 0,
        "window|name=1.04": 0,
        "window|name=1.05": 1,
        "window|name=bad": 0,
        "window|name=balkon": 0,
        "window|name=küche": 1,
        "window|name=reduit": 0,
        "window|name=zimmer": 1
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
      "size": 2260,
      "sha256": "b69c8d9a3086562595e80387d03beb2db0e4d1db9d94c63cf091788f01358377",
      "kind": "pdf_vector",
      "state": "flagged",
      "reason": "1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)",
      "group": "plans/flat-b",
      "route": "vector",
      "source": "plans/flat-b.pdf",
      "drawing_id": "44cc9f0d991eafe3",
      "reused": false,
      "takeoff": {
        "apartment": 1,
        "area:apartment": 45.4,
        "area:apartment|apartment=a": 45.4,
        "area:room": 65.443,
        "area:room:balcony|largest": 12.445,
        "area:room:bathroom|largest": 12.445,
        "area:room:bedroom|largest": 8.064,
        "area:room:kitchen|largest": 30.0,
        "area:room:storage|largest": 2.489,
        "area:room|indoor": 52.998,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "area:room|label=küche": 30.0,
        "area:room|label=küche|largest": 30.0,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "area:room|label=zimmer": 8.064,
        "area:room|label=zimmer|largest": 8.064,
        "area:room|name=1.01": 30.0,
        "area:room|name=1.02": 2.489,
        "area:room|name=1.03": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 8.064,
        "area:room|name=bad": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=küche": 30.0,
        "area:room|name=reduit": 2.489,
        "area:room|name=zimmer": 8.064,
        "bathtub": 1,
        "bathtub|name=1.01": 0,
        "bathtub|name=1.02": 0,
        "bathtub|name=1.03": 1,
        "bathtub|name=1.04": 0,
        "bathtub|name=1.05": 0,
        "bathtub|name=bad": 1,
        "bathtub|name=balkon": 0,
        "bathtub|name=küche": 0,
        "bathtub|name=reduit": 0,
        "bathtub|name=zimmer": 0,
        "door": 2,
        "door|name=1.01": 1,
        "door|name=1.02": 0,
        "door|name=1.03": 2,
        "door|name=1.04": 0,
        "door|name=1.05": 1,
        "door|name=bad": 2,
        "door|name=balkon": 0,
        "door|name=küche": 1,
        "door|name=reduit": 0,
        "door|name=zimmer": 1,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:bedroom": 4.233,
        "length:room:kitchen": 7.056,
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
        "room:bedroom": 1,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 0,
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
        "shower+bathtub|name=1.01": 0,
        "shower+bathtub|name=1.02": 0,
        "shower+bathtub|name=1.03": 1,
        "shower+bathtub|name=1.04": 0,
        "shower+bathtub|name=1.05": 0,
        "shower+bathtub|name=bad": 1,
        "shower+bathtub|name=balkon": 0,
        "shower+bathtub|name=küche": 0,
        "shower+bathtub|name=reduit": 0,
        "shower+bathtub|name=zimmer": 0,
        "shower|name=1.01": 0,
        "shower|name=1.02": 0,
        "shower|name=1.03": 0,
        "shower|name=1.04": 0,
        "shower|name=1.05": 0,
        "shower|name=bad": 0,
        "shower|name=balkon": 0,
        "shower|name=küche": 0,
        "shower|name=reduit": 0,
        "shower|name=zimmer": 0,
        "sink": 1,
        "sink|name=1.01": 0,
        "sink|name=1.02": 0,
        "sink|name=1.03": 1,
        "sink|name=1.04": 0,
        "sink|name=1.05": 0,
        "sink|name=bad": 1,
        "sink|name=balkon": 0,
        "sink|name=küche": 0,
        "sink|name=reduit": 0,
        "sink|name=zimmer": 0,
        "toilet": 1,
        "toilet|name=1.01": 0,
        "toilet|name=1.02": 0,
        "toilet|name=1.03": 1,
        "toilet|name=1.04": 0,
        "toilet|name=1.05": 0,
        "toilet|name=bad": 1,
        "toilet|name=balkon": 0,
        "toilet|name=küche": 0,
        "toilet|name=reduit": 0,
        "toilet|name=zimmer": 0,
        "window": 2,
        "window|name=1.01": 1,
        "window|name=1.02": 0,
        "window|name=1.03": 0,
        "window|name=1.04": 0,
        "window|name=1.05": 1,
        "window|name=bad": 0,
        "window|name=balkon": 0,
        "window|name=küche": 1,
        "window|name=reduit": 0,
        "window|name=zimmer": 1
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
      ],
      "name": "Drawn plan 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "no walls are drawn as geometry on this page"
    },
    {
      "drawing_id": "44cc9f0d991eafe3",
      "group": "plans/flat-b",
      "file": "plans/flat-b.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "plans/flat-b.pdf",
      "state": "flagged",
      "other_renderings": [],
      "name": "Drawn plan 2",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "no walls are drawn as geometry on this page"
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
      ],
      "name": "Plan image 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "this plan is a scan: its walls are not geometry"
    },
    {
      "drawing_id": "37f6819bd17d65d9",
      "group": "photos/plan-photo",
      "file": "photos/plan-photo.jpg",
      "kind": "photo_plan",
      "route": "raster",
      "source": "photos/plan-photo.jpg",
      "state": "flagged",
      "other_renderings": [],
      "name": "Plan photo 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "this plan is a photo: its walls are not geometry"
    },
    {
      "drawing_id": "1db9bcf1e67e27a3",
      "group": "model/house",
      "file": "model/house.ifc",
      "kind": "ifc",
      "route": "bim",
      "source": "model/house.ifc",
      "state": "ready",
      "other_renderings": [],
      "name": "Building model 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "this building model has no drawn plan to edit"
    }
  ],
  "skipped": [
    {
      "path": "photos/site.jpg",
      "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink (0.0% on the paper), camera EXIF (SyntheticPhone Model 1))"
    },
    {
      "path": "cad/detail.dxf",
      "reason": "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on"
    }
  ],
  "expected_drawings": 5,
  "conflicts_open": 0,
  "issues_open": 4,
  "issues_to_answer": 0
}
```

- `conflicts_open`, `issues_open`, `issues_to_answer`: the same numbers as the project's entry in
  `GET /api/projects`; null until `done`.
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
- `name` on each drawing: a plain name to show instead of the file name, from the kind of `file` and a number
  counted per name in the list's order: "Drawn plan" (vector PDF, DXF, SVG), "Scanned plan", "Plan image" (PNG,
  JPEG), "Plan photo", "Building model" (IFC), else "Drawing"; a page read as a file of its own adds its page
  ("Drawn plan 3, page 2"). Once the project is done, the same upload always gives the same names; while it
  runs, a number can still move (a drawing read before an earlier file is counted first). `credit` on each
  drawing: the licence credit of `file`, the same as `GET /api/drawings/{id}` gives (a page has the credit of the
  PDF it was split from), or null for a file that is not from the dataset, the Commons photos or the sample.
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
  "expected_drawings": null,
  "conflicts_open": null,
  "issues_open": null,
  "issues_to_answer": null
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
  "expected_drawings": 0,
  "conflicts_open": null,
  "issues_open": null,
  "issues_to_answer": null
}
```

### File triage (decision 0010)

Off by default (`TRIAGE_CLASSIFIER=off` and `SHEET_KIND=off`). With either on, every image file (a PNG or JPEG, a photo, a scanned PDF;
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
- `register` (decision 0010 section 8): what the classifier read off the sheet, floor plans included: `kind` (the
  answer key's 12: `floor_plan`, `multi_view_sheet`, `site_plan_or_map`, `elevation`, `section`, `detail`,
  `perspective_or_axonometric`, `engineering_non_building`, `cover_or_text_sheet`, `photograph`,
  `not_architecture`, `other`), `has_floor_plan`, `photo_of_sheet`, `scale_shown` (`bar`, `ratio_text`,
  `dimensions`, `none`, `unreadable`), `quality` (`good`, `fair`, `poor`), `method`. `class` is derived from it: a
  floor plan when `has_floor_plan` or `kind` is `floor_plan`, else `not_drawing` for `photograph`,
  `not_architecture`, `cover_or_text_sheet` and `other`, else `other_drawing`. Display only: nothing else acts on
  it, and a plan's `scale_shown` is never compared with what its reader found. Null with a classifier that reads
  no register (`TRIAGE_CLASSIFIER=rules`).
- `description` (only for a file that is not a floor plan): `text` (1-3 sentences summing up `detail`), `subject`
  (a short label), `text_seen` (the title-block and caption items of `visible_text`), `language` (ISO 639-1 of the
  printed text, null when none), `model`, `cost_usd`, and the form of section 8: `what_it_is` (`photograph`,
  `artwork`, `text_page`, `object`, `music`, `map`, `drawing`, `other`; `drawing` is a drawing that is not a floor
  plan), `shows_building`, `visible_text` (every legible word as printed, `""` when none, at most 2,000
  characters) and `detail` (a paragraph or more, at most 4,000 characters: a model's description no person
  checked). Printed text is kept (project, company, place and room names, the title block); the describer leaves
  out number plates, home addresses, personal contact data of private persons (phone numbers, e-mails) and the
  names of people seen in photos. A home address keeps its street and town, without the house number and
  postal code; that is the model's judgement, which can also drop a public building's house number.
- `relevance` (set once the project's ingest is done): `verdict` `related`, `unrelated` or `unsure`, `why` (one
  sentence naming what matched or what is missing), `matched_on`, `plans` (drawing ids, always among this
  project's `drawings`), `judge`. With no plan read in the project the verdict is `unsure`, "no floor plan in the
  project to compare with". With `TRIAGE_JUDGE=rules` (no model):
  - a described file is judged by the rule over its form: `related` when a word printed on it (`visible_text`,
    `text_seen`; 4 letters or more, not a drawing word, never a number alone) is in the project's name, its other
    files' and folders' names or its plans' text; `unsure` when it shows a building but nothing matches;
    `unrelated` when it shows no building and nothing matches. `matched_on` lists each word with where it
    matched, and `why` says whether it shows a building. `judge` is "rule on the words printed on it and whether it
    shows a building, no model".
  - a file nothing described (no describer, or the describer refused it) is judged by its class: `not_drawing`
    is `unrelated`, `other_drawing` `unsure`, and `why` says it was not read; `judge` is "rule on the kind of
    picture, no model (no description to read)". Its `note` is then "not described: no description model is set
    up" (or the describer's why).
- `overruled`: a person's call, `{verdict: related|unrelated, by, at}`; the judge's `relevance` stays as it was.
- `read_as_plan`: `{by, at}` once a person had the file read as a floor plan (`POST …/triage`); `class` stays the
  classifier's.
- `verdict`: the one value that counts: `overruled.verdict`, else `relevance.verdict`, else null.
- `sheet` (left out unless `SHEET_KIND=carbon` asked about the file; off by default): what gemini-4-carbon calls
  the sheet. `kind` (`architectural_floor_plan`, `multi_view_sheet`, `mep_plan`, `structural_plan`,
  `roof_or_ceiling_plan`, `site_plan_or_map`, `elevation`, `section`, `detail`, `perspective_or_axonometric`,
  `schedule_or_text`, `not_a_drawing`, `other`) with `kind_words` to show, `decision` (`set_aside`: no floor plan
  on the sheet and a non-plan kind at confidence >= `SHEET_KIND_CUT` (default 0.9) and `SHEET_KIND_SET_ASIDE=true`
  (the default; `false` makes such a sheet a `doubt` instead: read and flagged, below), the file is set
  aside with the reason "not a floor plan: <kind_words> (<title>, <sheet_number>)" and `POST …/triage` reads it;
  `doubt`: it is read; with a non-plan kind, in either mode (an unsure one with `SHEET_KIND_SET_ASIDE=true` too), the
  file is `flagged` (its `reason` starts "the sheet may not be a floor plan: it looks like <kind_words>; "), none of
  its answers is certified, each is Low with that flag in its `explanation`, and the drawing has a `reading_flag`
  issue; the flag follows the project's triage, also when the reading is reused from the cache, and `POST …/triage`
  drops it; with a plan kind every answer with a value ends its `explanation` with "This sheet may not be a floor
  plan."; `read`: also a camera photo (`photo_plan`) it calls no floor plan while `takeoff_possible` is true, under
  the cut: a posted fire exit plan keeps the kind it was given and gets no sheet-kind doubt (the photo's own reading
  flag stays)), `takeoff_possible`, `confidence` (of a floor plan on the
  sheet), `title`, `sheet_number`, `discipline` (`architecture`, `structural`, `plumbing`, `heating`, `ventilation`,
  `electrical`, `fire`, `site` or `other`, from the kind, title and number; null when unsure; a display hint, no
  client shows or reads it yet), `printed_scale` (as printed, shown only), `advanced` and `advanced_why` (harder
  than a clean scan of one small home plan, or an upload over 4,000 px on its long side; nothing reads it yet),
  `seen`, `model`. A call that fails leaves the file as triage would have it without the step ("triage not
  available: ...; read as today" with no classifier). A model answer alone; never a certified value.
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

A project with triage on (the test fakes and the rules judge: an elevation judged related, the site photo judged
unrelated and then called related by a person, a photo the describer refused judged by its class, and a camera
photo of an elevation sheet with its register, showing a building that matches nothing, so unsure):

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
        "area:room:bedroom|largest": 14.934,
        "area:room:kitchen|largest": 22.401,
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
        "bathtub|name=1.01": 0,
        "bathtub|name=1.02": 0,
        "bathtub|name=1.03": 1,
        "bathtub|name=1.04": 0,
        "bathtub|name=1.05": 0,
        "bathtub|name=bad": 1,
        "bathtub|name=balkon": 0,
        "bathtub|name=küche": 0,
        "bathtub|name=reduit": 0,
        "bathtub|name=zimmer": 0,
        "door": 2,
        "door|name=1.01": 1,
        "door|name=1.02": 0,
        "door|name=1.03": 2,
        "door|name=1.04": 0,
        "door|name=1.05": 1,
        "door|name=bad": 2,
        "door|name=balkon": 0,
        "door|name=küche": 1,
        "door|name=reduit": 0,
        "door|name=zimmer": 1,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:bedroom": 4.233,
        "length:room:kitchen": 7.056,
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
        "room:bedroom": 1,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 0,
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
        "shower+bathtub|name=1.01": 0,
        "shower+bathtub|name=1.02": 0,
        "shower+bathtub|name=1.03": 1,
        "shower+bathtub|name=1.04": 0,
        "shower+bathtub|name=1.05": 0,
        "shower+bathtub|name=bad": 1,
        "shower+bathtub|name=balkon": 0,
        "shower+bathtub|name=küche": 0,
        "shower+bathtub|name=reduit": 0,
        "shower+bathtub|name=zimmer": 0,
        "shower|name=1.01": 0,
        "shower|name=1.02": 0,
        "shower|name=1.03": 0,
        "shower|name=1.04": 0,
        "shower|name=1.05": 0,
        "shower|name=bad": 0,
        "shower|name=balkon": 0,
        "shower|name=küche": 0,
        "shower|name=reduit": 0,
        "shower|name=zimmer": 0,
        "sink": 1,
        "sink|name=1.01": 0,
        "sink|name=1.02": 0,
        "sink|name=1.03": 1,
        "sink|name=1.04": 0,
        "sink|name=1.05": 0,
        "sink|name=bad": 1,
        "sink|name=balkon": 0,
        "sink|name=küche": 0,
        "sink|name=reduit": 0,
        "sink|name=zimmer": 0,
        "toilet": 1,
        "toilet|name=1.01": 0,
        "toilet|name=1.02": 0,
        "toilet|name=1.03": 1,
        "toilet|name=1.04": 0,
        "toilet|name=1.05": 0,
        "toilet|name=bad": 1,
        "toilet|name=balkon": 0,
        "toilet|name=küche": 0,
        "toilet|name=reduit": 0,
        "toilet|name=zimmer": 0,
        "window": 2,
        "window|name=1.01": 1,
        "window|name=1.02": 0,
        "window|name=1.03": 0,
        "window|name=1.04": 0,
        "window|name=1.05": 1,
        "window|name=bad": 0,
        "window|name=balkon": 0,
        "window|name=küche": 1,
        "window|name=reduit": 0,
        "window|name=zimmer": 1
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
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover)",
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
        "register": null,
        "description": {
          "text": "A picture of the south elevation of a two-storey house.",
          "subject": "the south elevation of a two-storey house",
          "text_seen": [
            "Küche",
            "Süd"
          ],
          "language": "en",
          "model": "fake describer",
          "cost_usd": 0.0,
          "what_it_is": "drawing",
          "shows_building": false,
          "visible_text": "Küche\nSüd",
          "detail": "A longer account of the south elevation of a two-storey house, for later use."
        },
        "relevance": {
          "verdict": "related",
          "why": "Related: 'kuche', printed on it, is in the project's plan text; it shows no building.",
          "matched_on": [
            "'kuche' (plan text)"
          ],
          "plans": [],
          "judge": "rule on the words printed on it and whether it shows a building, no model"
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
      "reason": "not a floor plan: not a drawing",
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
        "register": null,
        "description": {
          "text": "A picture of a building site with a crane.",
          "subject": "a building site with a crane",
          "text_seen": [],
          "language": null,
          "model": "fake describer",
          "cost_usd": 0.0,
          "what_it_is": "photograph",
          "shows_building": false,
          "visible_text": "",
          "detail": "A longer account of a building site with a crane, for later use."
        },
        "relevance": {
          "verdict": "unrelated",
          "why": "Unrelated: it shows no building, and it has no printed text.",
          "matched_on": [],
          "plans": [],
          "judge": "rule on the words printed on it and whether it shows a building, no model"
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
      "reason": "not a floor plan: not a drawing",
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
        "register": null,
        "description": null,
        "relevance": {
          "verdict": "unrelated",
          "why": "A picture that is not a drawing; such files are judged unrelated by a rule on what kind of picture they are, without reading what they show.",
          "matched_on": [],
          "plans": [],
          "judge": "rule on the kind of picture, no model (no description to read)"
        },
        "overruled": null,
        "read_as_plan": null,
        "verdict": "unrelated",
        "note": "not described: the model refused"
      }
    },
    {
      "id": "f5",
      "path": "photos/sheet.jpg",
      "size": 37659,
      "sha256": "7753c4e8cfd8925200108dfc29ff16ab6d5e6acdaaea87e6ac763280d78a3e26",
      "kind": "photo_plan",
      "state": "set_aside",
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover)",
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
        "register": {
          "kind": "elevation",
          "has_floor_plan": false,
          "photo_of_sheet": true,
          "scale_shown": "bar",
          "quality": "fair",
          "method": "fake classifier"
        },
        "description": {
          "text": "A picture of a photographed elevation of a church.",
          "subject": "a photographed elevation of a church",
          "text_seen": [
            "Kirche St. Anna"
          ],
          "language": "en",
          "model": "fake describer",
          "cost_usd": 0.0,
          "what_it_is": "drawing",
          "shows_building": true,
          "visible_text": "Kirche St. Anna",
          "detail": "A longer account of a photographed elevation of a church, for later use."
        },
        "relevance": {
          "verdict": "unsure",
          "why": "Unsure: it shows a building, but none of its printed words is in the project's name, file and folder names or plan text.",
          "matched_on": [],
          "plans": [],
          "judge": "rule on the words printed on it and whether it shows a building, no model"
        },
        "overruled": null,
        "read_as_plan": null,
        "verdict": "unsure",
        "note": null
      }
    }
  ],
  "counts": {
    "ready": 1,
    "set_aside": 4
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
      "other_renderings": [],
      "name": "Drawn plan 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "no walls are drawn as geometry on this page"
    }
  ],
  "skipped": [
    {
      "path": "elevations/south.png",
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover)"
    },
    {
      "path": "photos/site.jpg",
      "reason": "not a floor plan: not a drawing"
    },
    {
      "path": "photos/street.jpg",
      "reason": "not a floor plan: not a drawing"
    },
    {
      "path": "photos/sheet.jpg",
      "reason": "not a floor plan: another kind of drawing (an elevation, section, site plan, detail or cover)"
    }
  ],
  "expected_drawings": 1,
  "not_plans": 4,
  "conflicts_open": 0,
  "issues_open": 2,
  "issues_to_answer": 1
}
```

### `POST /api/projects/{project_id}/files?name=<file name>`

A photo added to a finished project, from the chat (board #203). The body is the image's bytes (png or jpeg,
up to the upload limit); `name` its file name. 202 with the new file's `FileStatus`, `queued`, id `f<n+1>`, at
its own name, the folders dropped (a name the project has gets `-2`, `-3`... before the extension). It is read
in the background, alone, as at upload: identified (a camera photo of a plan as `photo_plan`, EXIF and
rectifier applied), triaged when triage is on, then its group, route and readers; with
`EVIDENCE_SCOPE=all_non_plan` it alone is then described for the evidence index. Poll
`GET /api/projects/{project_id}`: the file goes `running`, then `ready`, `flagged`, `set_aside` or `text_only`;
once read as a plan it has a `drawing_id` and is in `drawings`. The project stays `done` throughout; the issues
already there keep their ids and order, the new drawing's issues join the list.

- 404 `not-found` for an unknown project; 409 `not-allowed` until the project is `done` or while one of its files
  is read; 413 `too-large` over the upload limit; 415 `unsupported` for anything but png or jpeg (an empty body
  too); 422 `invalid` for a name that is not a file name (`..`); 422 `validation` with no `name`.
- A failure sets the file aside with why ("not ingested: ..."); the project stays `done`.
- While queued its `reason` is "added to the project, queued to be read".

<!-- fixture: file_added.json -->
```json
{
  "id": "f6",
  "path": "phone.png",
  "size": 2000,
  "sha256": null,
  "kind": null,
  "state": "queued",
  "reason": "added to the project, queued to be read",
  "group": null,
  "route": null,
  "source": null,
  "drawing_id": null,
  "reused": false,
  "takeoff": {},
  "ms": 12.5,
  "stage": null,
  "cost_usd": 0.0,
  "normalised": null
}
```

### Evidence scope (decision 0012, Amendment 1)

`EVIDENCE_SCOPE=set_aside` (the default) indexes only what triage set aside and described, as above.
`EVIDENCE_SCOPE=all_non_plan` also asks every picture triage did not set aside (a PNG or JPEG, a scanned or drawn
PDF page) its sheet kind, once the plans are read, and describes every one that is not a floor plan sheet, for
the evidence index. A text document (`pdf_text`, `text`) is searched by its own text, page by page, and so are
the text pages (200 characters or more) of a drawn or scanned PDF; a file nothing reads (DWG, office, archive,
encrypted PDF, IFC, unknown, refused) is listed by name; DXF and SVG files are not sources. Phone numbers and
e-mail addresses are taken out of the text first; a file's text is cut at 200,000 characters. It never changes a
file's `state`, `reason`, `route`, `group`, `drawing_id` or `takeoff`: a drawn elevation is still read as
before, and is also described.

`FileStatus.evidence` (left out when that step did not look at the file, so always with the default scope):

- `indexed`: whether the file is a source of the evidence index; `how`: `described`, `text` (its own text) or
  `listed` (by name only; its content is not read); null when not indexed. `kind`: the hit's kind (null when not
  indexed): the sheet kind for a described picture, `text_document` or `text_file`, `text_pages` (a drawn or
  scanned PDF searched by its own text pages only: its drawing is not a source), or the probe's kind for a
  listed file (`dwg`, `office`, `archive`, `pdf_encrypted`, `ifc`, `unknown`; `not_read` for an entry that was
  refused or could not be identified).
- `why`: one plain sentence, always set: `not a floor plan: an elevation (Gemini sheet kind, ...)`, `a floor
  plan: it is read, so it is not in the evidence index`, `the kind call failed: ...` (a spent Gemini budget
  included), `not described: ...` (`no description model is set up` without `TRIAGE_DESCRIBER`), `the evidence
  step failed: ...`, `searched by its own text: 3 pages, 2140 characters` (`, cut at 200,000 characters`; for a
  PDF whose drawing is not a source, `; its drawing is not a source (...)`), `listed by name only: <why>`, `a CAD
  file: no kind decision for it yet` (DXF, SVG), `no text to index: no page holds text`.
- `sheet`: the kind reply, the same object as `triage.sheet`; null when not asked. `description`: the same
  object as `triage.description` when indexed; for `text` and `listed` it is made by rule, no model: `subject` the
  file name in words, `text` the first 300 characters (or the "not read" sentence), `model` `no model: ...`.
  `text_pages`, `text_chars`: the pages that gave text and the characters indexed; null when none (a described
  drawn PDF with text pages has both). The text itself is not in the status: the index reads it from the stored
  file. The rule-made `description` is made at ingest, so a change to the text rules (contacts, addresses, the
  cut) shows in it only when the project is ingested again; the index's passages are cut again on its next
  sync.
- `cost_usd`: the kind call and the description, also counted in the file's and the project's `cost_usd`; 0 from
  the caches.

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
- 422 `not-triaged` for a file triage did not set aside as not a floor plan. Any file it did takes a call,
  described and judged or not, so every `unrelated_file` issue can be settled.
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
- Its `unrelated_file` issue stays, `settled`, with the same id and place in the list, "<by> had it read as a
  floor plan" in `why`, and once read the file's `drawing_id` and drawing links. The new drawing's own issues (a reading flag, a conflict) join the list; the issues already there keep their
  order.
- The trace adds a second `identify` line, "read as a floor plan, as <by> asked", then the usual stages.
- A photo is read as a photo of a plan (framed and rectified like one).
- No undo: a reading is not unread. A relevance call still works.
- 404 `not-found` for an unknown file; 409 `not-allowed` until the project is `done`, while a file of it is read
  again, or for a file already read this way; 422 `not-triaged` for a file triage did not set aside as not a floor
  plan; 422 `validation` for a `class` other than `floor_plan` or no `by`.
- A reading that fails, or that a restart cut off, sets the file aside with why ("not read as a floor plan: the
  server restarted while it was read as a floor plan", or the reader's error); the project stays `done`. The file
  is back to triage's call: `read_as_plan` is null again, it is in `not_plans`, its `unrelated_file` issue is
  `open` again, and it can be asked again (R6-a-1).
- While it is read, the file's `reason` is "being read as a floor plan".
- A sheet the sheet-kind step doubted with a non-plan kind (`triage.sheet.decision` `doubt`, flagged) was read
  already: the call is accepted the same way, nothing is read again, and the 202 returns the file as it ends: its
  reading's state and reason without the sheet-kind flag, `read_as_plan` set, and an `identify` trace line "read as
  a floor plan, as <by> asked: the reading is kept, the sheet-kind flag is dropped". Its answers lose the flag.

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
    "register": null,
    "description": {
      "text": "A picture of the south elevation of a two-storey house.",
      "subject": "the south elevation of a two-storey house",
      "text_seen": [
        "Küche",
        "Süd"
      ],
      "language": "en",
      "model": "fake describer",
      "cost_usd": 0.0,
      "what_it_is": "drawing",
      "shows_building": false,
      "visible_text": "Küche\nSüd",
      "detail": "A longer account of the south elevation of a two-storey house, for later use."
    },
    "relevance": {
      "verdict": "related",
      "why": "Related: 'kuche', printed on it, is in the project's plan text; it shows no building.",
      "matched_on": [
        "'kuche' (plan text)"
      ],
      "plans": [],
      "judge": "rule on the words printed on it and whether it shows a building, no model"
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
  "reason": "not read: this setup has no reader for the image route (0 elements, 0 rooms, no scale on the sheet)",
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
    "register": null,
    "description": {
      "text": "A picture of the south elevation of a two-storey house.",
      "subject": "the south elevation of a two-storey house",
      "text_seen": [
        "Küche",
        "Süd"
      ],
      "language": "en",
      "model": "fake describer",
      "cost_usd": 0.0,
      "what_it_is": "drawing",
      "shows_building": false,
      "visible_text": "Küche\nSüd",
      "detail": "A longer account of the south elevation of a two-storey house, for later use."
    },
    "relevance": {
      "verdict": "related",
      "why": "Related: 'kuche', printed on it, is in the project's plan text; it shows no building.",
      "matched_on": [
        "'kuche' (plan text)"
      ],
      "plans": [],
      "judge": "rule on the words printed on it and whether it shows a building, no model"
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

### `GET /api/projects/{project_id}/evidence/search?q=<text>&k=5&include_unrelated=false` (decision 0012)

A search over what the project's files that are not floor plans show and say: every file triage described and
nobody read as a plan (photos, elevations, sections, site plans, maps, text pages). Floor-plan facts are not in it.
The same JSON as the chat agent's `search_evidence` tool (`backend/app/adapters/evidence_tools.py`). Local only:
SQLite FTS5 BM25 and a multilingual embedder on CPU, fused by reciprocal rank fusion; with no embedder model on the
machine it searches with BM25 alone and `method` says so. Works in any project state: it answers from what is
described so far; a project with nothing indexed has `indexed_files: 0` and a `note`. With
`EVIDENCE_SCOPE=all_non_plan` (Evidence scope, above) the pictures the evidence step described are searched too.

- `q` 1-500 characters, not blank; `k` 1-20 (default 5) counts files: a file appears once, with its best-matching
  passage. 422 `validation` otherwise; 404 `not-found` for an unknown project.
- Files whose verdict (a person's call over the judge's) is `unrelated` are searched only with
  `include_unrelated=true`; `unrelated_left_out` counts the ones skipped.
- A hit: `id` (`f7-summary`, `f7-detail-2`, `f7-visible_text-1`, `f7-text-12`), `file_id`, `file` (as uploaded; the picture is
  `…/files/{file_id}/preview.png`), `page` (a `text` passage: the PDF page it comes from, and a text source's summary: its first text page; else the PDF page of a page entry `<name>#p<n>.pdf`, else 1), `part`, `how` (`described`, `text`, `listed`; see Evidence scope), `kind` (the register's kind, else
  the sheet kind of the evidence step, else the description's `what_it_is`), `subject`, `snippet` (at most 300 characters around the matched words), `language`, `verdict`,
  `credit`, `score` (orders one result's hits only) and `why` (`terms`: query words in the passage; `bm25_rank`,
  `dense_rank`: the file's rank by each retriever, null when it did not rank it or did not run).
- A hit is the closest file, not proof: read the snippet, then get the passage.

<!-- fixture: evidence_search.json -->
```json
{
  "query": "St. Anna",
  "method": "BM25 (no embedder model on this machine)",
  "indexed_files": 3,
  "unrelated_left_out": 0,
  "note": null,
  "hits": [
    {
      "id": "f5-visible_text-1",
      "file_id": "f5",
      "file": "photos/sheet.jpg",
      "page": 1,
      "part": "visible_text",
      "how": "described",
      "kind": "elevation",
      "subject": "a photographed elevation of a church",
      "snippet": "Kirche St. Anna",
      "language": "en",
      "verdict": "unsure",
      "credit": null,
      "score": 0.166667,
      "why": {
        "terms": [
          "st",
          "anna"
        ],
        "bm25_rank": 1,
        "dense_rank": null
      }
    }
  ]
}
```

### `GET /api/projects/{project_id}/evidence/{evidence_id}`

One hit's whole passage and its file's description, register and relevance as `GET /api/projects/{project_id}`
gives them (without the description's `cost_usd`). A file id alone (`f7`) answers as its summary (`f7-summary`).
A file judged unrelated is returned too. 404 `not-found` for an unknown project, an id not in the index or one
that is not an evidence id. `description.detail` is a model's description no person checked.

<!-- fixture: evidence_detail.json -->
```json
{
  "id": "f5-visible_text-1",
  "file_id": "f5",
  "file": "photos/sheet.jpg",
  "page": 1,
  "part": "visible_text",
  "how": "described",
  "text": "Kirche St. Anna",
  "kind": "elevation",
  "verdict": "unsure",
  "credit": null,
  "description": {
    "subject": "a photographed elevation of a church",
    "text": "A picture of a photographed elevation of a church.",
    "detail": "A longer account of a photographed elevation of a church, for later use.",
    "visible_text": "Kirche St. Anna",
    "text_seen": [
      "Kirche St. Anna"
    ],
    "language": "en",
    "what_it_is": "drawing",
    "shows_building": true,
    "model": "fake describer"
  },
  "register": {
    "kind": "elevation",
    "has_floor_plan": false,
    "photo_of_sheet": true,
    "scale_shown": "bar",
    "quality": "fair",
    "method": "fake classifier"
  },
  "relevance": {
    "verdict": "unsure",
    "why": "Unsure: it shows a building, but none of its printed words is in the project's name, file and folder names or plan text.",
    "matched_on": [],
    "plans": [],
    "judge": "rule on the words printed on it and whether it shows a building, no model"
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
      "area:room:bedroom|largest": 14.934,
      "area:room:kitchen|largest": 22.401,
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
      "bathtub|name=1.01": 0,
      "bathtub|name=1.02": 0,
      "bathtub|name=1.03": 1,
      "bathtub|name=1.04": 0,
      "bathtub|name=1.05": 0,
      "bathtub|name=bad": 1,
      "bathtub|name=balkon": 0,
      "bathtub|name=küche": 0,
      "bathtub|name=reduit": 0,
      "bathtub|name=zimmer": 0,
      "door": 2,
      "door|name=1.01": 1,
      "door|name=1.02": 0,
      "door|name=1.03": 2,
      "door|name=1.04": 0,
      "door|name=1.05": 1,
      "door|name=bad": 2,
      "door|name=balkon": 0,
      "door|name=küche": 1,
      "door|name=reduit": 0,
      "door|name=zimmer": 1,
      "length:room:balcony": 7.056,
      "length:room:bathroom": 3.528,
      "length:room:bedroom": 4.233,
      "length:room:kitchen": 7.056,
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
      "room:bedroom": 1,
      "room:hall": 0,
      "room:kitchen": 1,
      "room:living": 0,
      "room:other": 0,
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
      "shower+bathtub|name=1.01": 0,
      "shower+bathtub|name=1.02": 0,
      "shower+bathtub|name=1.03": 1,
      "shower+bathtub|name=1.04": 0,
      "shower+bathtub|name=1.05": 0,
      "shower+bathtub|name=bad": 1,
      "shower+bathtub|name=balkon": 0,
      "shower+bathtub|name=küche": 0,
      "shower+bathtub|name=reduit": 0,
      "shower+bathtub|name=zimmer": 0,
      "shower|name=1.01": 0,
      "shower|name=1.02": 0,
      "shower|name=1.03": 0,
      "shower|name=1.04": 0,
      "shower|name=1.05": 0,
      "shower|name=bad": 0,
      "shower|name=balkon": 0,
      "shower|name=küche": 0,
      "shower|name=reduit": 0,
      "shower|name=zimmer": 0,
      "sink": 1,
      "sink|name=1.01": 0,
      "sink|name=1.02": 0,
      "sink|name=1.03": 1,
      "sink|name=1.04": 0,
      "sink|name=1.05": 0,
      "sink|name=bad": 1,
      "sink|name=balkon": 0,
      "sink|name=küche": 0,
      "sink|name=reduit": 0,
      "sink|name=zimmer": 0,
      "toilet": 1,
      "toilet|name=1.01": 0,
      "toilet|name=1.02": 0,
      "toilet|name=1.03": 1,
      "toilet|name=1.04": 0,
      "toilet|name=1.05": 0,
      "toilet|name=bad": 1,
      "toilet|name=balkon": 0,
      "toilet|name=küche": 0,
      "toilet|name=reduit": 0,
      "toilet|name=zimmer": 0,
      "window": 2,
      "window|name=1.01": 1,
      "window|name=1.02": 0,
      "window|name=1.03": 0,
      "window|name=1.04": 0,
      "window|name=1.05": 1,
      "window|name=bad": 0,
      "window|name=balkon": 0,
      "window|name=küche": 1,
      "window|name=reduit": 0,
      "window|name=zimmer": 1
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
      "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 141 quantities, 81 above zero",
      "ms": 12.5,
      "output": "takeoff: 141 quantities, 81 above zero",
      "failure": null,
      "cost_usd": 0.0
    },
    {
      "stage": "write",
      "did": "drawing model adeefbbcc17559fc stored",
      "ms": 12.5,
      "output": "141 quantities",
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
          "area:room:bedroom|largest": 14.934,
          "area:room:kitchen|largest": 22.401,
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
          "bathtub|name=1.01": 0,
          "bathtub|name=1.02": 0,
          "bathtub|name=1.03": 1,
          "bathtub|name=1.04": 0,
          "bathtub|name=1.05": 0,
          "bathtub|name=bad": 1,
          "bathtub|name=balkon": 0,
          "bathtub|name=küche": 0,
          "bathtub|name=reduit": 0,
          "bathtub|name=zimmer": 0,
          "door": 2,
          "door|name=1.01": 1,
          "door|name=1.02": 0,
          "door|name=1.03": 2,
          "door|name=1.04": 0,
          "door|name=1.05": 1,
          "door|name=bad": 2,
          "door|name=balkon": 0,
          "door|name=küche": 1,
          "door|name=reduit": 0,
          "door|name=zimmer": 1,
          "length:room:balcony": 7.056,
          "length:room:bathroom": 3.528,
          "length:room:bedroom": 4.233,
          "length:room:kitchen": 7.056,
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
          "room:bedroom": 1,
          "room:hall": 0,
          "room:kitchen": 1,
          "room:living": 0,
          "room:other": 0,
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
          "shower+bathtub|name=1.01": 0,
          "shower+bathtub|name=1.02": 0,
          "shower+bathtub|name=1.03": 1,
          "shower+bathtub|name=1.04": 0,
          "shower+bathtub|name=1.05": 0,
          "shower+bathtub|name=bad": 1,
          "shower+bathtub|name=balkon": 0,
          "shower+bathtub|name=küche": 0,
          "shower+bathtub|name=reduit": 0,
          "shower+bathtub|name=zimmer": 0,
          "shower|name=1.01": 0,
          "shower|name=1.02": 0,
          "shower|name=1.03": 0,
          "shower|name=1.04": 0,
          "shower|name=1.05": 0,
          "shower|name=bad": 0,
          "shower|name=balkon": 0,
          "shower|name=küche": 0,
          "shower|name=reduit": 0,
          "shower|name=zimmer": 0,
          "sink": 1,
          "sink|name=1.01": 0,
          "sink|name=1.02": 0,
          "sink|name=1.03": 1,
          "sink|name=1.04": 0,
          "sink|name=1.05": 0,
          "sink|name=bad": 1,
          "sink|name=balkon": 0,
          "sink|name=küche": 0,
          "sink|name=reduit": 0,
          "sink|name=zimmer": 0,
          "toilet": 1,
          "toilet|name=1.01": 0,
          "toilet|name=1.02": 0,
          "toilet|name=1.03": 1,
          "toilet|name=1.04": 0,
          "toilet|name=1.05": 0,
          "toilet|name=bad": 1,
          "toilet|name=balkon": 0,
          "toilet|name=küche": 0,
          "toilet|name=reduit": 0,
          "toilet|name=zimmer": 0,
          "window": 2,
          "window|name=1.01": 1,
          "window|name=1.02": 0,
          "window|name=1.03": 0,
          "window|name=1.04": 0,
          "window|name=1.05": 1,
          "window|name=bad": 0,
          "window|name=balkon": 0,
          "window|name=küche": 1,
          "window|name=reduit": 0,
          "window|name=zimmer": 1
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
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 141 quantities, 81 above zero",
          "ms": 12.5,
          "output": "takeoff: 141 quantities, 81 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model adeefbbcc17559fc stored",
          "ms": 12.5,
          "output": "141 quantities",
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
          "area:room:bedroom|largest": 14.934,
          "area:room:kitchen|largest": 22.401,
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
          "bathtub|name=1.01": 0,
          "bathtub|name=1.02": 0,
          "bathtub|name=1.03": 1,
          "bathtub|name=1.04": 0,
          "bathtub|name=1.05": 0,
          "bathtub|name=bad": 1,
          "bathtub|name=balkon": 0,
          "bathtub|name=küche": 0,
          "bathtub|name=reduit": 0,
          "bathtub|name=zimmer": 0,
          "door": 2,
          "door|name=1.01": 1,
          "door|name=1.02": 0,
          "door|name=1.03": 2,
          "door|name=1.04": 0,
          "door|name=1.05": 1,
          "door|name=bad": 2,
          "door|name=balkon": 0,
          "door|name=küche": 1,
          "door|name=reduit": 0,
          "door|name=zimmer": 1,
          "length:room:balcony": 7.056,
          "length:room:bathroom": 3.528,
          "length:room:bedroom": 4.233,
          "length:room:kitchen": 7.056,
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
          "room:bedroom": 1,
          "room:hall": 0,
          "room:kitchen": 1,
          "room:living": 0,
          "room:other": 0,
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
          "shower+bathtub|name=1.01": 0,
          "shower+bathtub|name=1.02": 0,
          "shower+bathtub|name=1.03": 1,
          "shower+bathtub|name=1.04": 0,
          "shower+bathtub|name=1.05": 0,
          "shower+bathtub|name=bad": 1,
          "shower+bathtub|name=balkon": 0,
          "shower+bathtub|name=küche": 0,
          "shower+bathtub|name=reduit": 0,
          "shower+bathtub|name=zimmer": 0,
          "shower|name=1.01": 0,
          "shower|name=1.02": 0,
          "shower|name=1.03": 0,
          "shower|name=1.04": 0,
          "shower|name=1.05": 0,
          "shower|name=bad": 0,
          "shower|name=balkon": 0,
          "shower|name=küche": 0,
          "shower|name=reduit": 0,
          "shower|name=zimmer": 0,
          "sink": 1,
          "sink|name=1.01": 0,
          "sink|name=1.02": 0,
          "sink|name=1.03": 1,
          "sink|name=1.04": 0,
          "sink|name=1.05": 0,
          "sink|name=bad": 1,
          "sink|name=balkon": 0,
          "sink|name=küche": 0,
          "sink|name=reduit": 0,
          "sink|name=zimmer": 0,
          "toilet": 1,
          "toilet|name=1.01": 0,
          "toilet|name=1.02": 0,
          "toilet|name=1.03": 1,
          "toilet|name=1.04": 0,
          "toilet|name=1.05": 0,
          "toilet|name=bad": 1,
          "toilet|name=balkon": 0,
          "toilet|name=küche": 0,
          "toilet|name=reduit": 0,
          "toilet|name=zimmer": 0,
          "window": 2,
          "window|name=1.01": 1,
          "window|name=1.02": 0,
          "window|name=1.03": 0,
          "window|name=1.04": 0,
          "window|name=1.05": 1,
          "window|name=bad": 0,
          "window|name=balkon": 0,
          "window|name=küche": 1,
          "window|name=reduit": 0,
          "window|name=zimmer": 1
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
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 141 quantities, 81 above zero",
          "ms": 12.5,
          "output": "takeoff: 141 quantities, 81 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model c9b719f715357201 stored",
          "ms": 12.5,
          "output": "141 quantities",
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
        "size": 2260,
        "sha256": "b69c8d9a3086562595e80387d03beb2db0e4d1db9d94c63cf091788f01358377",
        "kind": "pdf_vector",
        "state": "flagged",
        "reason": "1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)",
        "group": "plans/flat-b",
        "route": "vector",
        "source": "plans/flat-b.pdf",
        "drawing_id": "44cc9f0d991eafe3",
        "reused": false,
        "takeoff": {
          "apartment": 1,
          "area:apartment": 45.4,
          "area:apartment|apartment=a": 45.4,
          "area:room": 65.443,
          "area:room:balcony|largest": 12.445,
          "area:room:bathroom|largest": 12.445,
          "area:room:bedroom|largest": 8.064,
          "area:room:kitchen|largest": 30.0,
          "area:room:storage|largest": 2.489,
          "area:room|indoor": 52.998,
          "area:room|label=bad": 12.445,
          "area:room|label=bad|largest": 12.445,
          "area:room|label=balkon": 12.445,
          "area:room|label=balkon|largest": 12.445,
          "area:room|label=küche": 30.0,
          "area:room|label=küche|largest": 30.0,
          "area:room|label=reduit": 2.489,
          "area:room|label=reduit|largest": 2.489,
          "area:room|label=zimmer": 8.064,
          "area:room|label=zimmer|largest": 8.064,
          "area:room|name=1.01": 30.0,
          "area:room|name=1.02": 2.489,
          "area:room|name=1.03": 12.445,
          "area:room|name=1.04": 12.445,
          "area:room|name=1.05": 8.064,
          "area:room|name=bad": 12.445,
          "area:room|name=balkon": 12.445,
          "area:room|name=küche": 30.0,
          "area:room|name=reduit": 2.489,
          "area:room|name=zimmer": 8.064,
          "bathtub": 1,
          "bathtub|name=1.01": 0,
          "bathtub|name=1.02": 0,
          "bathtub|name=1.03": 1,
          "bathtub|name=1.04": 0,
          "bathtub|name=1.05": 0,
          "bathtub|name=bad": 1,
          "bathtub|name=balkon": 0,
          "bathtub|name=küche": 0,
          "bathtub|name=reduit": 0,
          "bathtub|name=zimmer": 0,
          "door": 2,
          "door|name=1.01": 1,
          "door|name=1.02": 0,
          "door|name=1.03": 2,
          "door|name=1.04": 0,
          "door|name=1.05": 1,
          "door|name=bad": 2,
          "door|name=balkon": 0,
          "door|name=küche": 1,
          "door|name=reduit": 0,
          "door|name=zimmer": 1,
          "length:room:balcony": 7.056,
          "length:room:bathroom": 3.528,
          "length:room:bedroom": 4.233,
          "length:room:kitchen": 7.056,
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
          "room:bedroom": 1,
          "room:hall": 0,
          "room:kitchen": 1,
          "room:living": 0,
          "room:other": 0,
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
          "shower+bathtub|name=1.01": 0,
          "shower+bathtub|name=1.02": 0,
          "shower+bathtub|name=1.03": 1,
          "shower+bathtub|name=1.04": 0,
          "shower+bathtub|name=1.05": 0,
          "shower+bathtub|name=bad": 1,
          "shower+bathtub|name=balkon": 0,
          "shower+bathtub|name=küche": 0,
          "shower+bathtub|name=reduit": 0,
          "shower+bathtub|name=zimmer": 0,
          "shower|name=1.01": 0,
          "shower|name=1.02": 0,
          "shower|name=1.03": 0,
          "shower|name=1.04": 0,
          "shower|name=1.05": 0,
          "shower|name=bad": 0,
          "shower|name=balkon": 0,
          "shower|name=küche": 0,
          "shower|name=reduit": 0,
          "shower|name=zimmer": 0,
          "sink": 1,
          "sink|name=1.01": 0,
          "sink|name=1.02": 0,
          "sink|name=1.03": 1,
          "sink|name=1.04": 0,
          "sink|name=1.05": 0,
          "sink|name=bad": 1,
          "sink|name=balkon": 0,
          "sink|name=küche": 0,
          "sink|name=reduit": 0,
          "sink|name=zimmer": 0,
          "toilet": 1,
          "toilet|name=1.01": 0,
          "toilet|name=1.02": 0,
          "toilet|name=1.03": 1,
          "toilet|name=1.04": 0,
          "toilet|name=1.05": 0,
          "toilet|name=bad": 1,
          "toilet|name=balkon": 0,
          "toilet|name=küche": 0,
          "toilet|name=reduit": 0,
          "toilet|name=zimmer": 0,
          "window": 2,
          "window|name=1.01": 1,
          "window|name=1.02": 0,
          "window|name=1.03": 0,
          "window|name=1.04": 0,
          "window|name=1.05": 1,
          "window|name=bad": 0,
          "window|name=balkon": 0,
          "window|name=küche": 1,
          "window|name=reduit": 0,
          "window|name=zimmer": 1
        },
        "ms": 12.5,
        "stage": "write",
        "cost_usd": 0.0,
        "normalised": null
      },
      "stages": [
        {
          "stage": "unpack",
          "did": "path checked, 2260 bytes",
          "ms": 12.5,
          "output": "plans/flat-b.pdf",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "hash",
          "did": "sha256 b69c8d9a3086",
          "ms": 12.5,
          "output": "b69c8d9a3086562595e80387d03beb2db0e4d1db9d94c63cf091788f01358377",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "identify",
          "did": "a drawn PDF (page 1 of 1: 18 paths, 0 images, 141 characters)",
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
          "did": "rules: each-once, sauna-room-else-stove, showers-and-bathtubs; takeoff: 141 quantities, 81 above zero",
          "ms": 12.5,
          "output": "takeoff: 141 quantities, 81 above zero",
          "failure": null,
          "cost_usd": 0.0
        },
        {
          "stage": "write",
          "did": "drawing model 44cc9f0d991eafe3 stored",
          "ms": 12.5,
          "output": "141 quantities",
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
        "reason": "not read: this setup has no reader for the image route (0 elements, 0 rooms, no scale on the sheet)",
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
        "reason": "not read: this setup has no reader for the image route (0 elements, 0 rooms, no scale on the sheet)",
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
        "reason": "not read: this setup has no reader for the image route; a phone photo, read without perspective correction (0 elements, 0 rooms, no scale on the sheet)",
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
          "did": "a photo of a drawing (1600x1200 px, 47% white, 49% paper, 1.1% ink (2.2% on the paper), camera EXIF (SyntheticPhone Model 1))",
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
        "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink (0.0% on the paper), camera EXIF (SyntheticPhone Model 1))",
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
          "did": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink (0.0% on the paper), camera EXIF (SyntheticPhone Model 1))",
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
      "quantities": 81
    },
    {
      "drawing_id": "44cc9f0d991eafe3",
      "file": "plans/flat-b.pdf",
      "to_review": 1,
      "signed": 0,
      "quantities": 81
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
      "drawing_id": "44cc9f0d991eafe3",
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
        "status": "conflict",
        "value_marks": [
          [
            {
              "page": 1,
              "box": [
                0.16667,
                0.125,
                0.5,
                0.375
              ],
              "label": "polygon_x_scale",
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
              ]
            }
          ],
          [
            {
              "page": 1,
              "box": [
                0.17367,
                0.17946,
                0.21269,
                0.19027
              ],
              "label": "printed_label",
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
              ]
            }
          ]
        ]
      },
      "settled": null,
      "needs_person": false,
      "signed": null,
      "value": 30.0,
      "title": "Area of room (name Küche · 1.01): 22.40 m² or 30.00 m²?",
      "why": "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by the printed room areas. Settled by a rule (the printed label over the outline at the sheet's scale): 30.00 m² is used.",
      "suggestions": [
        "22.40 m²",
        "30.00 m²"
      ]
    }
  ]
}
```

`needs_person: true` marks a conflict no rule decides and nobody settled ("needs you"); the others were decided by
a rule ("AI decision") or settled by a surveyor.

The conflict card's words, rule-based from the conflict's values (no model, no paid call):

- `title`: the conflict as a question, each value once: "Door count: 13 or 11?", "Area of room (name Küche ·
  1.01): 22.40 m² or 30.00 m²?".
- `why`: what each method read and how it is decided: "The methods disagree: 22.40 m² by the room outlines at the
  sheet's scale, 30.00 m² by the printed room areas." then "Settled by a rule (<the rule>): 30.00 m² is used." or
  "No rule decides between them, so a person has to choose." A stage-8 `conflict.note` sits between the two.
- `suggestions`: short answers to tap, one per value read, as a person would type them: "13 doors", "1 door",
  "22.40 m²". A tapped one goes back as a `settle` with its number in `value` (and the words in `note` if wanted).

### `POST /api/projects/{project_id}/resolve`

`RESOLVER` (off by default; `carbon`: Google's gemini-4-carbon): a model looks at each conflict of the project that
no rule decides and no person settled, at the places each method's items are (`value_marks`), and picks one of the
methods' values or says it can't tell. One call per conflict; the replies are kept with the project's review, so a
second POST asks only about conflicts that changed, and a `GET` never calls the model. With `RESOLVER` on, the same
runs on its own once an upload's ingest is done (`POST /api/projects` and `/sample`), so this POST is for a retry
(after a budget stop or a timeout). Every call is charged to the Gemini spend guard (`GEMINI_BUDGET_USD`), and the
adapter caches each reply by its request, model and prompt version. No body. 200 with `{review, notes}`: `review` is `GET …/review`'s body, `notes` one line per
conflict that got no reply (the budget used up, a timeout, a pick that is none of the methods' values). 409
`not-allowed` while `RESOLVER` is off or the project is not `done`.

A pick is checked by a model, never a person's word:

- the row's `status` stays `conflict` (the methods still disagree), its `value` is the pick, `needs_person` is
  false, and `resolved` holds
  `{verdict, value, reason, marks, by, at, of}` (`of`: the methods' values it was asked about; a pick applies only
  while the conflict still has exactly these values). The conflict's `why` ends "A model (<by>) checked the drawing
  and picked <value>: <reason>. You can still choose another value."
- `resolved.marks` are where the model looked: 1-based `page` and a page-fraction `box` `[x0, y0, x1, y1]`, the same
  frame as the conflict's `value_marks`, with a `label` saying whose item it is.
- A person's settle or sign-off wins over it; `unsettle` and `reset` bring the pick back (it is not an edit). Every
  review and sign-off response (`settle`, `unsettle`, `reset`, ...) carries the row's `resolved` as the takeoff does.
- A person's mark edit (`reject`, `add`, counting in an excluded mark) also wins: the value is counted from the
  marks as before, `needs_person` is true again, and `why` says the model picked <value> before the marks were
  edited. A `reset` brings the pick back.
- `cannot_tell`: nothing changes (`needs_person` stays true) and `why` says the model could not tell, and why. The
  reply is kept: it is not asked again until the conflict's values change.
- Counts: a picked conflict is not in `conflicts_open`; `GET /api/projects` and `GET /api/projects/{id}` count it in
  `conflicts_picked` (a pick in use: no person settled, signed or edited its marks). A `cannot_tell` stays in
  `conflicts_open`. `conflicts_picked` is absent while `RESOLVER` is off and the project holds no pick.
- Issues: a conflict's issue stays listed (state `open`) with `resolved` set; with a pick in use its severity is
  `note`, so `issues_to_answer` doesn't count it, and its `why` ends "no rule decides, a model picked <value>
  (<by>): you can change it". With `cannot_tell` it stays `needs_person`.
- Answers (`POST /api/ask`): an answer that `check` asks to double-check gets the model's reply in `resolved`,
  beside the answer (never certified). On a conflict whose reply is kept, that reply is shown and no call is made;
  on a conflict a person has to choose, the request is the conflict's (both methods' values, the same cache entry
  as this POST), and as here a pick must be one of the methods' values: anything else gives no `resolved`, only a
  `resolver_note`. `cost_usd` and `line.cost_usd` include the resolver's call, which waits at most
  `RESOLVER_TIMEOUT_S` (30 s by default). Two callers asking the same thing at once (the upload's resolve and a
  person's POST) share one call.
- With `RESOLVER` off, `resolved` is absent from every row, conflict, issue and answer (not null), so every response
  is as before.

A project with a pick (`GET /api/projects/{id}`; `GET …/review` below), a `POST …/resolve` whose model could not
tell, and an uncertain answer with the model's check:

<!-- fixture: project_resolved.json -->
```json
{
  "id": "5e0c1a2b3d55",
  "name": "flat-b.pdf",
  "state": "done",
  "created_at": "2026-11-14T08:00:00+00:00",
  "started_at": "2026-11-14T08:00:00+00:00",
  "finished_at": "2026-11-14T08:00:00+00:00",
  "files": [
    {
      "id": "f1",
      "path": "flat-b.pdf",
      "size": 2260,
      "sha256": "b69c8d9a3086562595e80387d03beb2db0e4d1db9d94c63cf091788f01358377",
      "kind": "pdf_vector",
      "state": "flagged",
      "reason": "1 conflict between the two methods (room areas) (7 elements, 5 rooms, scale read from the sheet)",
      "group": "flat-b",
      "route": "vector",
      "source": "flat-b.pdf",
      "drawing_id": "44cc9f0d991eafe3",
      "reused": false,
      "takeoff": {
        "apartment": 1,
        "area:apartment": 45.4,
        "area:apartment|apartment=a": 45.4,
        "area:room": 65.443,
        "area:room:balcony|largest": 12.445,
        "area:room:bathroom|largest": 12.445,
        "area:room:bedroom|largest": 8.064,
        "area:room:kitchen|largest": 30.0,
        "area:room:storage|largest": 2.489,
        "area:room|indoor": 52.998,
        "area:room|label=bad": 12.445,
        "area:room|label=bad|largest": 12.445,
        "area:room|label=balkon": 12.445,
        "area:room|label=balkon|largest": 12.445,
        "area:room|label=küche": 30.0,
        "area:room|label=küche|largest": 30.0,
        "area:room|label=reduit": 2.489,
        "area:room|label=reduit|largest": 2.489,
        "area:room|label=zimmer": 8.064,
        "area:room|label=zimmer|largest": 8.064,
        "area:room|name=1.01": 30.0,
        "area:room|name=1.02": 2.489,
        "area:room|name=1.03": 12.445,
        "area:room|name=1.04": 12.445,
        "area:room|name=1.05": 8.064,
        "area:room|name=bad": 12.445,
        "area:room|name=balkon": 12.445,
        "area:room|name=küche": 30.0,
        "area:room|name=reduit": 2.489,
        "area:room|name=zimmer": 8.064,
        "bathtub": 1,
        "bathtub|name=1.01": 0,
        "bathtub|name=1.02": 0,
        "bathtub|name=1.03": 1,
        "bathtub|name=1.04": 0,
        "bathtub|name=1.05": 0,
        "bathtub|name=bad": 1,
        "bathtub|name=balkon": 0,
        "bathtub|name=küche": 0,
        "bathtub|name=reduit": 0,
        "bathtub|name=zimmer": 0,
        "door": 2,
        "door|name=1.01": 1,
        "door|name=1.02": 0,
        "door|name=1.03": 2,
        "door|name=1.04": 0,
        "door|name=1.05": 1,
        "door|name=bad": 2,
        "door|name=balkon": 0,
        "door|name=küche": 1,
        "door|name=reduit": 0,
        "door|name=zimmer": 1,
        "length:room:balcony": 7.056,
        "length:room:bathroom": 3.528,
        "length:room:bedroom": 4.233,
        "length:room:kitchen": 7.056,
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
        "room:bedroom": 1,
        "room:hall": 0,
        "room:kitchen": 1,
        "room:living": 0,
        "room:other": 0,
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
        "shower+bathtub|name=1.01": 0,
        "shower+bathtub|name=1.02": 0,
        "shower+bathtub|name=1.03": 1,
        "shower+bathtub|name=1.04": 0,
        "shower+bathtub|name=1.05": 0,
        "shower+bathtub|name=bad": 1,
        "shower+bathtub|name=balkon": 0,
        "shower+bathtub|name=küche": 0,
        "shower+bathtub|name=reduit": 0,
        "shower+bathtub|name=zimmer": 0,
        "shower|name=1.01": 0,
        "shower|name=1.02": 0,
        "shower|name=1.03": 0,
        "shower|name=1.04": 0,
        "shower|name=1.05": 0,
        "shower|name=bad": 0,
        "shower|name=balkon": 0,
        "shower|name=küche": 0,
        "shower|name=reduit": 0,
        "shower|name=zimmer": 0,
        "sink": 1,
        "sink|name=1.01": 0,
        "sink|name=1.02": 0,
        "sink|name=1.03": 1,
        "sink|name=1.04": 0,
        "sink|name=1.05": 0,
        "sink|name=bad": 1,
        "sink|name=balkon": 0,
        "sink|name=küche": 0,
        "sink|name=reduit": 0,
        "sink|name=zimmer": 0,
        "toilet": 1,
        "toilet|name=1.01": 0,
        "toilet|name=1.02": 0,
        "toilet|name=1.03": 1,
        "toilet|name=1.04": 0,
        "toilet|name=1.05": 0,
        "toilet|name=bad": 1,
        "toilet|name=balkon": 0,
        "toilet|name=küche": 0,
        "toilet|name=reduit": 0,
        "toilet|name=zimmer": 0,
        "window": 2,
        "window|name=1.01": 1,
        "window|name=1.02": 0,
        "window|name=1.03": 0,
        "window|name=1.04": 0,
        "window|name=1.05": 1,
        "window|name=bad": 0,
        "window|name=balkon": 0,
        "window|name=küche": 1,
        "window|name=reduit": 0,
        "window|name=zimmer": 1
      },
      "ms": 12.5,
      "stage": "write",
      "cost_usd": 0.0,
      "normalised": null
    }
  ],
  "counts": {
    "flagged": 1
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
      "drawing_id": "44cc9f0d991eafe3",
      "group": "flat-b",
      "file": "flat-b.pdf",
      "kind": "pdf_vector",
      "route": "vector",
      "source": "flat-b.pdf",
      "state": "flagged",
      "other_renderings": [],
      "name": "Drawn plan 1",
      "credit": "Synthetic drawing made for this demo by the Hour49 team; no partner data",
      "drawable": false,
      "not_drawable_reason": "no walls are drawn as geometry on this page"
    }
  ],
  "skipped": [],
  "expected_drawings": 1,
  "conflicts_open": 0,
  "conflicts_picked": 1,
  "issues_open": 1,
  "issues_to_answer": 0
}
```

<!-- fixture: project_review_resolved.json -->
```json
{
  "drawings": [
    {
      "drawing_id": "44cc9f0d991eafe3",
      "file": "flat-b.pdf",
      "to_review": 1,
      "signed": 0,
      "quantities": 81
    }
  ],
  "conflicts": [
    {
      "drawing_id": "44cc9f0d991eafe3",
      "file": "flat-b.pdf",
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
        "resolution": null,
        "note": null,
        "derived": null,
        "status": "conflict",
        "value_marks": [
          [
            {
              "page": 1,
              "box": [
                0.16667,
                0.125,
                0.5,
                0.375
              ],
              "label": "polygon_x_scale",
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
              ]
            }
          ],
          [
            {
              "page": 1,
              "box": [
                0.17367,
                0.17946,
                0.21269,
                0.19027
              ],
              "label": "printed_label",
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
              ]
            }
          ]
        ]
      },
      "settled": null,
      "needs_person": false,
      "signed": null,
      "value": 22.401,
      "title": "Area of room (name Küche · 1.01): 22.40 m² or 30.00 m²?",
      "why": "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by the printed room areas. No rule decides between them. A model (carbon:gemini-4-carbon) checked the drawing and picked 22.40 m²: The room's outline is closed and drawn to the sheet's scale. You can still choose another value.",
      "suggestions": [
        "22.40 m²",
        "30.00 m²"
      ],
      "resolved": {
        "verdict": "picked",
        "value": 22.401,
        "reason": "The room's outline is closed and drawn to the sheet's scale.",
        "marks": [
          {
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ],
            "label": "the room outlines at the sheet's scale counts polygon_x_scale here",
            "polygon": null
          },
          {
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ],
            "label": "the printed room areas counts printed_label here",
            "polygon": null
          }
        ],
        "by": "carbon:gemini-4-carbon",
        "at": "2026-11-14T08:05:00Z",
        "of": [
          22.401,
          30.0
        ]
      }
    }
  ]
}
```

<!-- fixture: resolving.json -->
```json
{
  "review": {
    "drawings": [
      {
        "drawing_id": "44cc9f0d991eafe3",
        "file": "flat-b.pdf",
        "to_review": 1,
        "signed": 0,
        "quantities": 81
      }
    ],
    "conflicts": [
      {
        "drawing_id": "44cc9f0d991eafe3",
        "file": "flat-b.pdf",
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
          "resolution": null,
          "note": null,
          "derived": null,
          "status": "conflict",
          "value_marks": [
            [
              {
                "page": 1,
                "box": [
                  0.16667,
                  0.125,
                  0.5,
                  0.375
                ],
                "label": "polygon_x_scale",
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
                ]
              }
            ],
            [
              {
                "page": 1,
                "box": [
                  0.17367,
                  0.17946,
                  0.21269,
                  0.19027
                ],
                "label": "printed_label",
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
                ]
              }
            ]
          ]
        },
        "settled": null,
        "needs_person": true,
        "signed": null,
        "value": 30.0,
        "title": "Area of room (name Küche · 1.01): 22.40 m² or 30.00 m²?",
        "why": "The methods disagree: 22.40 m² by the room outlines at the sheet's scale, 30.00 m² by the printed room areas. No rule decides between them, and a model (carbon:gemini-4-carbon) could not tell: The printed area is cut by the sheet edge, so the label can't be read.",
        "suggestions": [
          "22.40 m²",
          "30.00 m²"
        ],
        "resolved": {
          "verdict": "cannot_tell",
          "value": null,
          "reason": "The printed area is cut by the sheet edge, so the label can't be read.",
          "marks": [
            {
              "page": 1,
              "box": [
                0.16667,
                0.125,
                0.5,
                0.375
              ],
              "label": "the room outlines at the sheet's scale counts polygon_x_scale here",
              "polygon": null
            },
            {
              "page": 1,
              "box": [
                0.17367,
                0.17946,
                0.21269,
                0.19027
              ],
              "label": "the printed room areas counts printed_label here",
              "polygon": null
            }
          ],
          "by": "carbon:gemini-4-carbon",
          "at": "2026-11-14T08:05:00Z",
          "of": [
            22.401,
            30.0
          ]
        }
      }
    ]
  },
  "notes": []
}
```

<!-- fixture: answer_resolved.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "e9d9c7882f8bb9de",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/e9d9c7882f8bb9de/pages/1.png",
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
    "sure": false,
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
  },
  "check": {
    "reason": "Please double-check the doors: the readers disagree at 2 places, marked on the drawing.",
    "disputed": [
      {
        "mark_id": "m2",
        "page": 1,
        "box": [
          0.6,
          0.1,
          0.65,
          0.2
        ],
        "why": "Counted as a door, but 2 of the 3 other readers see nothing here.",
        "readers": {
          "answer": "door, score 0.41",
          "L one view": "nothing",
          "M one view": "nothing",
          "seg": "door, score 0.62"
        }
      },
      {
        "mark_id": null,
        "page": 1,
        "box": [
          0.3,
          0.85,
          0.36,
          0.9
        ],
        "why": "Not counted, but 2 of the 3 other readers see a door here.",
        "readers": {
          "answer": "nothing",
          "L one view": "door, score 0.55",
          "M one view": "door, score 0.48",
          "seg": "nothing"
        }
      }
    ]
  },
  "level": {
    "level": "medium",
    "basis": "score",
    "text": "Medium confidence: on our validation plans, 91% of the answers rated this way were exact (1084 of 1185). Please double-check it."
  },
  "resolved": {
    "verdict": "picked",
    "value": 2,
    "reason": "Two door leaves are drawn at the places counted.",
    "marks": [
      {
        "page": 1,
        "box": [
          0.6,
          0.1,
          0.65,
          0.2
        ],
        "label": "Counted as a door, but 2 of the 3 other readers see nothing here.",
        "polygon": null
      },
      {
        "page": 1,
        "box": [
          0.3,
          0.85,
          0.36,
          0.9
        ],
        "label": "Not counted, but 2 of the 3 other readers see a door here.",
        "polygon": null
      }
    ],
    "by": "carbon:gemini-4-carbon",
    "at": "2026-11-14T08:05:00Z",
    "of": []
  }
}
```

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

- `id`: stable across calls and restarts, and kept when the issue is settled or signed off. It is the reference
  to keep across re-reads and exports; the `n` of the CSV and zip is the issue's position in the current list,
  not an identifier (qa-c R6-c-4).
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
- `drawing_name`: the drawing's plain name as `GET /api/projects/{id}` `drawings[].name` gives it ("Drawn plan 2",
  the same numbering; another rendering of a drawing has that drawing's name), null for a file with no drawing.
  Show it to a person instead of `file`, which can be a dataset's file name.
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
- `label`: short legend text for the issue's mark: a conflict's quantity label ("Area of room (name Küche ·
  1.01)"), else by kind: "No answer", "Set aside", "How it was read", "Fails a rule", "Double-check", "Not a floor
  plan".
- `suggestions`: short answers a person can pick (chips), by kind, with no model call; none only restates a
  value (Tudor, board #14). A conflict: "Check it on site". A refused answer: "Not needed", "I'll send
  a drawing that shows it". A set-aside file: "Not needed", "I'll send a readable copy". A reading flag: "The
  reading is fine", "I'll send a better copy". A failed check: "Accepted as drawn", "To be fixed in the design".
  `unrelated_file`: "It belongs to the project", "It does not belong here". Any text can be answered, not only
  these.
- `answer`: a person's answer, `{text, by, at}` (`POST …/issues/{id}/answer` below), or null. It is a note on the
  issue: it settles nothing and does not change `state` (settle a conflict with `POST …/review`, make a call on a
  file with `POST …/relevance`).
- `model_file_id` and `highlight` (added 2026-11-14, board #14 c6883948897; only while `MODEL_3D` is on, each left
  out when there is none): for a failed code check on a drawing with an IFC model, the IFC file whose 3D view shows it (its own file, or the model
  a sheet was read from: `…/files/{model_file_id}/model.glb`) and the checked room or door by GlobalId,
  `[{global_id, role: "affected"}]`, when the model lists it as drawn on the sheet. The check's `subject` carries
  the same `global_id` (left out when none, and always while `MODEL_3D` is off) in `GET /api/drawings/{id}/checks`.

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
      "drawing_name": "Drawn plan 1",
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
      "why": "The bedroom \"Schlafzimmer 4.02\" is 6.03 m2; the rule asks at least 7 m2. It would not meet today's rule for a new building. (Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024, 4 § 2 mom.)",
      "quantity": "area:room|name=4.02",
      "question": null,
      "reason": null,
      "check": "fi:fi-habitable-room-area:r2",
      "links": {
        "drawing": "/api/drawings/5c4ed01e00000002?project=5e0c1a2b3d53",
        "takeoff": "/api/drawings/5c4ed01e00000002/takeoff?project=5e0c1a2b3d53",
        "trace": "/api/projects/5e0c1a2b3d53/files/f1/trace",
        "checks": "/api/drawings/5c4ed01e00000002/checks?pack=fi&project=5e0c1a2b3d53"
      },
      "label": "Fails a rule",
      "suggestions": [
        "Accepted as drawn",
        "To be fixed in the design"
      ],
      "answer": null
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
      "id": "conflict-efcb1b52a852",
      "kind": "conflict",
      "severity": "note",
      "state": "settled",
      "drawing_id": "44cc9f0d991eafe3",
      "drawing_name": "Drawn plan 2",
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
        "drawing": "/api/drawings/44cc9f0d991eafe3?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/44cc9f0d991eafe3/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f3/trace",
        "checks": null
      },
      "label": "Area of room (name Küche · 1.01)",
      "suggestions": [
        "Check it on site"
      ],
      "answer": null
    },
    {
      "id": "reading_flag-b8584dc30c73",
      "kind": "reading_flag",
      "severity": "note",
      "state": "open",
      "drawing_id": "3b3ce7db34257f63",
      "drawing_name": "Plan image 1",
      "file": "scans/ground-floor.png",
      "file_id": "f4",
      "floor": null,
      "page": 1,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "Not read: this setup has no reader for the image route.",
      "quantity": null,
      "question": null,
      "reason": "not read: this setup has no reader for the image route",
      "check": null,
      "links": {
        "drawing": "/api/drawings/3b3ce7db34257f63?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/3b3ce7db34257f63/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f4/trace",
        "checks": null
      },
      "label": "How it was read",
      "suggestions": [
        "The reading is fine",
        "I'll send a better copy"
      ],
      "answer": null
    },
    {
      "id": "refused_answer-3b5adbf71a63",
      "kind": "refused_answer",
      "severity": "note",
      "state": "open",
      "drawing_id": "3b3ce7db34257f63",
      "drawing_name": "Plan image 1",
      "file": "scans/ground-floor.png",
      "file_id": "f4",
      "floor": null,
      "page": null,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "No answer to \"How many doors are there?\": the drawing gives no reliable number for it.",
      "quantity": null,
      "question": "How many doors are there?",
      "reason": null,
      "check": null,
      "links": {
        "drawing": "/api/drawings/3b3ce7db34257f63?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/3b3ce7db34257f63/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f4/trace",
        "checks": null
      },
      "label": "No answer",
      "suggestions": [
        "Not needed",
        "I'll send a drawing that shows it"
      ],
      "answer": null
    },
    {
      "id": "reading_flag-2b11c57c0ff6",
      "kind": "reading_flag",
      "severity": "note",
      "state": "open",
      "drawing_id": "37f6819bd17d65d9",
      "drawing_name": "Plan photo 1",
      "file": "photos/plan-photo.jpg",
      "file_id": "f6",
      "floor": null,
      "page": 1,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "A phone photo, read without perspective correction; not read: this setup has no reader for the image route.",
      "quantity": null,
      "question": null,
      "reason": "a phone photo, read without perspective correction; not read: this setup has no reader for the image route",
      "check": null,
      "links": {
        "drawing": "/api/drawings/37f6819bd17d65d9?project=5e0c1a2b3d4f",
        "takeoff": "/api/drawings/37f6819bd17d65d9/takeoff?project=5e0c1a2b3d4f",
        "trace": "/api/projects/5e0c1a2b3d4f/files/f6/trace",
        "checks": null
      },
      "label": "How it was read",
      "suggestions": [
        "The reading is fine",
        "I'll send a better copy"
      ],
      "answer": null
    },
    {
      "id": "set_aside-02a5f0314890",
      "kind": "set_aside",
      "severity": "note",
      "state": "open",
      "drawing_id": null,
      "drawing_name": null,
      "file": "photos/site.jpg",
      "file_id": "f7",
      "floor": null,
      "page": null,
      "box": null,
      "polygon": null,
      "mark_id": null,
      "why": "Set aside at ingest: a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink (0.0% on the paper), camera EXIF (SyntheticPhone Model 1)).",
      "quantity": null,
      "question": null,
      "reason": "a photo, not of a drawing (1600x1200 px, 15% white, 25% paper, 0.0% ink (0.0% on the paper), camera EXIF (SyntheticPhone Model 1))",
      "check": null,
      "links": {
        "drawing": null,
        "takeoff": null,
        "trace": "/api/projects/5e0c1a2b3d4f/files/f7/trace",
        "checks": null
      },
      "label": "Set aside",
      "suggestions": [
        "Not needed",
        "I'll send a readable copy"
      ],
      "answer": null
    },
    {
      "id": "set_aside-ac138023ff60",
      "kind": "set_aside",
      "severity": "note",
      "state": "open",
      "drawing_id": null,
      "drawing_name": null,
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
      },
      "label": "Set aside",
      "suggestions": [
        "Not needed",
        "I'll send a readable copy"
      ],
      "answer": null
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
  severity and labelled with its `n`, under the line "`<drawing_name>`, page `<n>`: `<k>` issues". Under the page
  are the issues' sentences, a colour key and the drawing's
  licence credit.
- An issue with no page or no box is only in the CSV, and a page with no such issue has no PNG.

#### `POST /api/projects/{project_id}/issues/{issue_id}/answer?pack=`

A person's answer to an issue: `{text, by}` (`text` 1-500 characters, `by` as a sign-off's), or `{undo: true}` to
take it back (nothing else; with no answer kept, nothing changes). A new answer replaces the one before. Returns
the issue as the list gives it, with its `answer`. The answer is kept with the project (`<projects dir>/api/
issue_answers/<project id>.json`), so it survives a reload and a restart, and keeps to the issue's `id`: an issue
that leaves the list (a refused question answered later) takes its answer with it, and gets it back if it returns.

- A failed code check's issue needs its `pack`, as the list does.
- Errors: an unknown project, pack or issue is 404; a project that is not `done` is 409 `not-allowed`; a body with
  no `text` or `by`, an empty one, or `undo` with either is 422 `validation`.
- The project's `issues_to_answer` drops by one when an open issue that is not a note gets its first answer.

<!-- fixture: issue_answer_request.json -->
```json
{
  "text": "Check it on site",
  "by": "Ana"
}
```

<!-- fixture: issue_answered.json -->
```json
{
  "id": "conflict-efcb1b52a852",
  "kind": "conflict",
  "severity": "note",
  "state": "settled",
  "drawing_id": "44cc9f0d991eafe3",
  "drawing_name": "Drawn plan 2",
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
    "drawing": "/api/drawings/44cc9f0d991eafe3?project=5e0c1a2b3d4f",
    "takeoff": "/api/drawings/44cc9f0d991eafe3/takeoff?project=5e0c1a2b3d4f",
    "trace": "/api/projects/5e0c1a2b3d4f/files/f3/trace",
    "checks": null
  },
  "label": "Area of room (name Küche · 1.01)",
  "suggestions": [
    "Check it on site"
  ],
  "answer": {
    "text": "Check it on site",
    "by": "Ana",
    "at": "2026-11-14T08:05:00Z"
  }
}
```

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
normalisation. Images and a PDF's first page; 404 for any other file, 422 `invalid` for an image or PDF that cannot be
decoded (cut off or damaged). `width` as for pages.

### `GET /api/projects/{project_id}/files/{file_id}/model.glb`

Only while `MODEL_3D` is on (off: 404, and no payload changes). An IFC file's 3D view: one GLB of the whole model,
each node named by its element's GlobalId (openings and rooms left out), `model/gltf-binary`, gzipped
(`Content-Encoding: gzip`) when the request accepts it. The first request starts the conversion: 409 `converting`
until it is built (poll this route or the file's `model_3d`). 422 with `code` `too_big` (over the memory budget,
the CPU-time limit or 60 MB of GLB), `no_geometry` (nothing to draw) or `failed` (the file could not be read, or the
server was too busy: that one is not kept, the next request tries again), and the reason as `detail`. 404 for a
file that is not IFC.

`FileStatus.model_3d` in `GET /api/projects/{project_id}` (IFC files only, left out otherwise and when off):
`state` (`not_started`, `converting`, `ready`, `unavailable`), `code` (as the 422's, when unavailable), `reason`
(one sentence, when unavailable), `elements` (when ready: the elements drawn). A deploy builds the views ahead
with `uv run python -m app.cli glb` (backend/README.md).

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
  },
  "check": null,
  "level": null
}
```

- `answer`, `unit`: the value to show. It is the row's current `value`, so a surveyor's edits show here
  (`quantity.original_value` is what ingest computed). Null on a refusal: the screen shows no number.
- `confidence`: a raw score the pipeline gives the answer, named for what it is: `signal` (`g1main`: Gemini
  Decisions' choice distribution for the answered count, on when the server runs with
  `DECISIONS_CONFIDENCE=true`), `score` (0 to 1) and `calibrated` (false: the score was not checked against
  right answers, so it is **not** a probability that the answer is right; a correct 4-bedroom answer scored
  0.38). Don't show it as one: the proof and `evidence.png` leave it out. What to show is `level` (below), which
  is measured. Only a drawing read on the raster route is scored (Decisions reads images). Null
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
  "drawing_id": "ac22309c691d645d",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/ac22309c691d645d/pages/1.png",
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
  },
  "check": null,
  "level": null
}
```

#### Double-check request: `check`

With `CHECK_POLICY` set (golden's `check_policy_v1` file in `eval/results/gate/`, chosen on val: one threshold per
family so that at least 96% of the wrong answers ask for a check, D476), a takeoff answer the policy does not
certify **keeps its value** and carries `check`, so the screen asks a person to look before trusting it.
`answer.check` is the request the screen shows; `proof.check` is a different, older field: one line on how a
second method measured the value (`Checked twice, ...`), shown with the proof. Read the request from
`answer.check`, never from `proof.check`.

- `reason`: one plain sentence for the person, e.g. `Please double-check the doors: the readers disagree at 2
  places, marked on the drawing.`
- `disputed`: the places to look at, strongest first, at most 5 (empty when no reader points anywhere):
  `mark_id` is the answer's review mark (`marks[].id`; a room's mark carries the room id in `ref`), which a
  person can reject, restore or settle with the review actions; `mark_id` null is a place the answer did **not**
  count, with `page` and `box`, which a person can `add`. `why` is one sentence; `readers` maps each reader to
  what it says there (`nothing` when it sees nothing), the answer's own reading included.

`check` is null when the answer is certified (on the raster route: its score at or above its family's threshold on
a page ingest did not flag, the score being `g1main`'s or, for a family whose threshold was chosen on a local gate's
signal, that gate's from `LOCAL_GATES`; on another route: the route was certified on golden v2's holdout), once
a person settled or signed the quantity off, on a refusal, and when `CHECK_POLICY` is off. Never certified,
whatever the score or route, and the `reason` says why: two methods disagree, also when a rule picked one value
(`Please double-check the doors: two methods disagree: 2 vs 3; we show 3.`; areas with two decimals and m²);
the value is an estimate (`... it is an estimate (<the estimate>).`); a person changed the marks without
signing off (`... edited by you: sign off to confirm.`), or a bedroom count includes a room typed a bedroom
with no printed label (`... 1 room is drawn as a bedroom with no printed label; please confirm.`, that room
listed first). A mark the person rejected is never listed in `disputed`. A window count's `reason` gives both
counts when they differ (`we count 3 windows if a window with several panes is one window, 4 if every pane is
counted ...`), and panes that may be one window are one entry in `disputed`. A value read from a printed
schedule gets a request without places unless the policy certified the `schedule` route. A family the
policy has no threshold for (or a null one) is never certified. The examples use stand-ins for the score (0.87) and
for the dispute finders: a door count certified at threshold 0.8, the same count at 0.9, and a bedroom count at
0.9 (`marks` trimmed to two):

With `CHECK_POLICY` on, the answer's `sure` follows it instead of `GATE_POLICY`: true exactly when the answer is
certified, false when it is not (whether or not a person has since settled or signed it off; a value a person
edited is never certified, signed or not), null on an answer it does not rate (a refusal, a question with no
takeoff row).
So the screen never shows Sure next to a double-check request. The policy is fit on CubiCasa val read with
`ROOM_POLICY=gold-labels`; under `furniture` (the demo) room counts are certified outside those conditions, except
that a bedroom count including a bedroom with no printed label always asks (docs/GOLDEN.md, "The double-check
policy").

#### Confidence level: `level`

With `CHECK_POLICY` set to a policy file that carries levels (decision 0011; `stoa_eval check-policy --medium`
writes them), every answer the policy rates also carries `level`: `{level, basis, text}`. The backend computes it,
so every client shows the same one: show `level` as the pill and `text` with it, and don't derive a level from
`confidence.score`.

- `level`: `high`, `medium` or `low`.
  - `high`: the answer is certified. It is high exactly when `line.sure` is true and `check` is null, so a level
    never contradicts the request. With `CARBON_LEVELS=ladder` (off by default) a Medium raster answer that Gemini
    Carbon, read as a second reader, answered with the same value is high too (basis `carbon`): `check` is null,
    but `line.sure` stays false, because Carbon never certifies an answer.
  - `medium`: the answer asks for a double-check, and its score is at or above its family's Medium threshold: the
    calibrated chance that it is wrong is at most the policy's cut (0.20).
  - `low`: every other rated answer. It asks for a double-check too.
- `basis`: what the level rests on.
  - `certified`: the policy's certificate on a raster answer (high).
  - `score`: the answer's score against its family's Medium threshold (medium or low). A family with no Medium
    threshold, because its Medium answers were too few or too often wrong on validation, is low.
  - `route`: the drawing's route, from its own reference answers. A certified route (vector PDF, IFC model) is
    high; a value read from a printed schedule takes the `schedule` route's level.
  - `page`: the page was flagged at upload (a phone photo, a scan). Low: levels are not measured on such pages.
    Also a raster page on which the detector found no plan and no element: nothing on it is certified, and its
    answers are low (`text` says so), because readers that all saw nothing agree on 0 without evidence.
  - `held`: the value is held for a check whatever its score (two methods disagree, an estimate, edited and not
    signed off, a bedroom with no printed label). Low; `check.reason` says why.
  - `unrated`: nothing was measured for it (a question outside the rated families, no score on this drawing, a
    route with no level). Low.
  - `carbon` (`CARBON_LEVELS=demote` or `ladder`): Gemini Carbon read the raster sheet beside the reader. A Medium
    answer it counted differently is low; with `ladder`, one it counted the same is high ("checked by Carbon: two
    readers agree"). When Carbon could not check the sheet, the level stays as it was and `text` says so.
- `text`: one plain sentence to show with the pill. For `certified` and `score` it quotes the validation counts of
  that level from the policy file, e.g. `Medium confidence: on our validation plans, 91% of the answers rated this
  way were exact (1084 of 1185). Please double-check it.`; for `route`, the route's reference counts.

`level` is null on a refusal, on a value a person signed off or settled (it is theirs: show the sign-off and no
level), when `CHECK_POLICY` is off, and with a policy file that has no `levels` block: an older file still
certifies and asks, and gives no level instead of calling every answer low. `line` (answer_v1.1) is unchanged.
What each level measured on validation, on golden v2 and on the test read is in
[decision 0011](decisions/0011-confidence-levels.md). The three examples show `check` and `level` together: high,
medium (doors are Medium from a score of 0.5 here) and low (bedrooms have no Medium threshold here).

<!-- fixture: answer_certified.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "e9d9c7882f8bb9de",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/e9d9c7882f8bb9de/pages/1.png",
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
    "sure": true,
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
  },
  "check": null,
  "level": {
    "level": "high",
    "basis": "certified",
    "text": "High confidence: on our validation plans, 99% of the answers rated this way were exact (1501 of 1517)."
  }
}
```

<!-- fixture: answer_double_check.json -->
```json
{
  "question": "How many doors are there?",
  "drawing_id": "e9d9c7882f8bb9de",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/e9d9c7882f8bb9de/pages/1.png",
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
    "sure": false,
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
  },
  "check": {
    "reason": "Please double-check the doors: the readers disagree at 2 places, marked on the drawing.",
    "disputed": [
      {
        "mark_id": "m2",
        "page": 1,
        "box": [
          0.6,
          0.1,
          0.65,
          0.2
        ],
        "why": "Counted as a door, but 2 of the 3 other readers see nothing here.",
        "readers": {
          "answer": "door, score 0.41",
          "L one view": "nothing",
          "M one view": "nothing",
          "seg": "door, score 0.62"
        }
      },
      {
        "mark_id": null,
        "page": 1,
        "box": [
          0.3,
          0.85,
          0.36,
          0.9
        ],
        "why": "Not counted, but 2 of the 3 other readers see a door here.",
        "readers": {
          "answer": "nothing",
          "L one view": "door, score 0.55",
          "M one view": "door, score 0.48",
          "seg": "nothing"
        }
      }
    ]
  },
  "level": {
    "level": "medium",
    "basis": "score",
    "text": "Medium confidence: on our validation plans, 91% of the answers rated this way were exact (1084 of 1185). Please double-check it."
  }
}
```

<!-- fixture: answer_double_check_rooms.json -->
```json
{
  "question": "How many bedrooms are there?",
  "drawing_id": "e9d9c7882f8bb9de",
  "file": "plan.png",
  "pages": [
    {
      "page": 1,
      "width": 800.0,
      "height": 400.0,
      "unit": "px",
      "url": "/api/drawings/e9d9c7882f8bb9de/pages/1.png",
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
    "key": "room:bedroom",
    "label": "room bedroom count",
    "measure": "count",
    "subject": "room:bedroom",
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
          0.1,
          0.1,
          0.45,
          0.9
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "Makuuhuone 1",
        "ref": "r1",
        "reason": null,
        "room_type": "bedroom"
      },
      {
        "id": "m2",
        "n": 2,
        "page": 1,
        "box": [
          0.55,
          0.1,
          0.9,
          0.9
        ],
        "polygon": null,
        "state": "counted",
        "value": 1.0,
        "label": "Makuuhuone 2",
        "ref": "r2",
        "reason": null,
        "room_type": "bedroom"
      }
    ],
    "signed": null,
    "unlocated": {},
    "noun": "bedrooms"
  },
  "marks": [
    {
      "id": "m1",
      "n": 1,
      "page": 1,
      "box": [
        0.1,
        0.1,
        0.45,
        0.9
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "Makuuhuone 1",
      "ref": "r1",
      "reason": null,
      "room_type": "bedroom"
    },
    {
      "id": "m2",
      "n": 2,
      "page": 1,
      "box": [
        0.55,
        0.1,
        0.9,
        0.9
      ],
      "polygon": null,
      "state": "counted",
      "value": 1.0,
      "label": "Makuuhuone 2",
      "ref": "r2",
      "reason": null,
      "room_type": "bedroom"
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
          0.1,
          0.1,
          0.45,
          0.9
        ]
      },
      {
        "file": "plan.png",
        "page": 1,
        "box": [
          0.55,
          0.1,
          0.9,
          0.9
        ]
      }
    ],
    "method": "takeoff",
    "cost_usd": 0.0,
    "latency_s": 0.002,
    "confidence": 0.87,
    "sure": false,
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
        "label": "bedroom",
        "colour": "#1f77b4",
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
  },
  "check": {
    "reason": "Please double-check the bedrooms: the readers disagree at 2 places, marked on the drawing.",
    "disputed": [
      {
        "mark_id": "m2",
        "page": 1,
        "box": [
          0.55,
          0.1,
          0.9,
          0.9
        ],
        "why": "Counted as a bedroom; the segmentation reader sees a living room here.",
        "readers": {
          "reader": "bedroom",
          "label": "Makuuhuone 2",
          "segmentation": "living",
          "printed_label": "nothing"
        }
      },
      {
        "mark_id": null,
        "page": 1,
        "box": [
          0.46,
          0.1,
          0.54,
          0.4
        ],
        "why": "Not counted, but the segmentation reader and the printed label see a bedroom.",
        "readers": {
          "reader": "nothing",
          "label": "nothing",
          "segmentation": "bedroom",
          "printed_label": "bedroom"
        }
      }
    ]
  },
  "level": {
    "level": "low",
    "basis": "score",
    "text": "Low confidence: on our validation plans, 58% of the answers rated this way were exact (397 of 680). Check it before you use it."
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
  refused (with their `answer.refusal`), each group in the project's order. Also `file_id` (the drawing's file,
  its `FileStatus.id`); only while `MODEL_3D` is on (off: left out, the payload as before), `model_file_id` (left
  out when none): the IFC file whose 3D view shows the drawing
  (`…/files/{model_file_id}/model.glb`), its own file when that is IFC, else the model a sheet was read from;
  `highlight` (left out when empty): the elements the answer counted, by IFC GlobalId, `[{global_id, role}]`, role
  `affected` here (`moved`, `removed`, `added` are for edit proposals); and while `MODEL_3D` is on, `model_3d`: that
  file's `FileStatus.model_3d`, read at response time. A chat turn's `answers` carry the same parts.
- `total`, `total_unit`: when exactly one drawing answered, its value. When several did, their values added up, but
  only when the backend knows the drawings show different parts of the building: sheets of the same IFC model,
  each showing a different storey. A flat drawn twice (a PDF and its IFC model, as in the sample) would otherwise be
  counted twice. The question must also be a count, or an area or length over each whole drawing, in one unit.
  Null otherwise: no drawing answered, the drawings may show the same rooms, the question is about one room (two
  kitchens on two drawings are two parts, not one sum), the answer came from a printed table, or the units differ.
  The total adds the parts' measured values (`answer.quantity.value`). When one of them is an area on an estimated
  scale, the total is that sum in whole m², as such a part's `answer` is (#294).
- `total_sure`: true only when there is a total and every part in it is sure (`answer.line.sure`); false
  otherwise.
- `total_level`: the lowest confidence level among the total's parts that have one (`answer.level.level`): `high`,
  `medium` or `low`. Null with no total, or when no part has a level.
- `total_note`: one plain sentence to show with the total, or instead of it: what was added over how many drawings,
  how many of the summed parts need a double-check (the methods disagree, or a person still has to settle it), or
  why there is no total, and which drawings gave no answer and why, e.g. `2 doors from 1 drawing.` or `3 drawings
  answered; they may show the same rooms, so the numbers are not added up; 2 drawings give no reliable number for it.`
- `why_no_total` and `refused_note`: `total_note` in its two parts. `why_no_total`: why there is no total, as a
  sentence (`3 drawings answered; they may show the same rooms, so the numbers are not added up.`, or `No drawing
  answered it.`); null when there is a total. `refused_note`: the drawings that gave no answer and why (`2 drawings
  give no reliable number for it.`); null when none refused.
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
        },
        "check": null,
        "level": null
      },
      "file_id": "f1"
    },
    {
      "drawing_id": "44cc9f0d991eafe3",
      "name": "plans/flat-b.pdf",
      "answer": {
        "question": "How many doors are there?",
        "drawing_id": "44cc9f0d991eafe3",
        "file": "plans/flat-b.pdf",
        "pages": [
          {
            "page": 1,
            "width": 600.0,
            "height": 400.0,
            "unit": "pt",
            "url": "/api/drawings/44cc9f0d991eafe3/pages/1.png",
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
        },
        "check": null,
        "level": null
      },
      "file_id": "f3"
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
          "text": "This sheet wasn't read, so nothing on it was counted or measured: this setup has no reader for this kind of sheet. You can still ask about the project's other drawings.",
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
        },
        "check": null,
        "level": null
      },
      "file_id": "f4"
    }
  ],
  "total": null,
  "total_unit": null,
  "total_sure": false,
  "total_level": null,
  "total_note": "3 drawings answered; they may show the same rooms, so the numbers are not added up; 2 drawings give no reliable number for it.",
  "why_no_total": "3 drawings answered; they may show the same rooms, so the numbers are not added up.",
  "refused_note": "2 drawings give no reliable number for it."
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
  },
  "check": null,
  "level": null
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
  },
  "check": null,
  "level": null
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
  },
  "check": null,
  "level": null
}
```

`refusal.code`:

| Code | When |
| --- | --- |
| `unsupported-question` | the question is not one the parser turns into a count, area, length or volume |
| `not-in-drawing` | the drawing does not give this quantity (or no schedule on the sheet answers it) |
| `not-read` | the reader of this drawing does not look for that class, so it has no count of it |
| `no-reader` | nothing was read from the sheet (this setup has no reader for its route: the text says so; a reader that found nothing says that instead), that reader is less reliable than a guess for this kind of question (`prior:policy`), the page was flagged at upload (a phone photo, a scan) and its reader found no element or no room at all for what was asked, or a room question on a raster page (an image, a photo, a scanned PDF; flagged or not) whose reader found no room at all: 0 would be a guess |
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
  "drawing_id": "44cc9f0d991eafe3",
  "file": "plans/flat-b.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/44cc9f0d991eafe3/pages/1.png",
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
      "status": "conflict",
      "value_marks": [
        [
          {
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ],
            "label": "polygon_x_scale",
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
            ]
          }
        ],
        [
          {
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ],
            "label": "printed_label",
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
            ]
          }
        ]
      ]
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
  },
  "check": null,
  "level": null
}
```

The same question after the quantity was signed off (`quantity.status` `signed`, `quantity.signed`):

<!-- fixture: answer_signed.json -->
```json
{
  "question": "What is the area of room 1.01?",
  "drawing_id": "44cc9f0d991eafe3",
  "file": "plans/flat-b.pdf",
  "pages": [
    {
      "page": 1,
      "width": 600.0,
      "height": 400.0,
      "unit": "pt",
      "url": "/api/drawings/44cc9f0d991eafe3/pages/1.png",
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
      "status": "conflict",
      "value_marks": [
        [
          {
            "page": 1,
            "box": [
              0.16667,
              0.125,
              0.5,
              0.375
            ],
            "label": "polygon_x_scale",
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
            ]
          }
        ],
        [
          {
            "page": 1,
            "box": [
              0.17367,
              0.17946,
              0.21269,
              0.19027
            ],
            "label": "printed_label",
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
            ]
          }
        ]
      ]
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
  },
  "check": null,
  "level": null
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
  },
  "check": null,
  "level": null
}
```

## Chat (decision 0013)

The project chat as a tool-calling agent: it calls the pipeline tools (`list_drawings`, `ask_drawings`,
`get_takeoff`, `list_conflicts`, `list_issues`, `run_checks`, `get_plan_geometry`) and the plan tools (`list_walls`,
`propose_remove_wall`, `propose_room`), and ends each turn with an answer the server checked: every evidence id and
every number in `text` came from a tool result of this turn, else the turn is `dont_know`. The model never writes
coordinates: places are evidence ids the server resolves. `CHAT_MODEL` picks the model: `rules` (default, no key,
deterministic), `gemini` (`AGENT_MODEL`, every call charged to the Gemini spend guard), `off` (503).
`GET /api/info` `chat` says which, whether a turn can run now, and (`stream`) whether `POST
.../chat/stream` exists: a client streams only when it is true.

### `POST /api/projects/{project_id}/chat`

Body: `chat_id` (12 hex, omit to start a chat), `message` (1-2,000 characters), `selection` (at most 8, optional):
what the user pointed at, `{id: "sel_<n>", kind: "room" | "region", drawing_id, page, ref?, box?}` with `box` in
page fractions. A sync call: a turn takes up to `AGENT_TURN_USD` dollars and 60 s.

<!-- fixture: chat_request.json -->
```json
{
  "message": "How many doors are there?"
}
```

Response `ChatTurn`: `kind` is `answer`, `dont_know`, `conflict`, `needs_input` (which room or wall: 2-4
`options`), `edit` (with `edit`, the proposal) or `ask_issue` (below). `options` may come with any kind (a `dont_know` carries the
questions the drawings can answer): each is a chip whose `message` the client sends as the next message.
`evidence[].name`, the step labels and the text use the drawing's plain name ("Drawn plan 1"). `evidence` lists
only the places `text` cites, numbered in the order it cites them. `answers` (last) holds the `ask_drawings`
results the answer rests on, each exactly a `POST /api/projects/{project_id}/ask` response: those whose places the
text cites, or for a `dont_know` or `needs_input` citing none, those in which a drawing refused; `[]` otherwise. `text` cites sources as
`[n]`, the `n` of an `evidence` item: a place on a page (`drawing_id`, `name`, `page`, `box` in page fractions,
`label`, `sure`, and `level`, the confidence level of the `ask_drawings` answer it comes from, or null). `steps`
lists every tool call with a label in plain words, `status` (`ok` or `error`) and `ms`; `model`, `cost_usd` and
`latency_s` are the turn's.

Levels only where measured (added 2026-11-14): when a number in an `answer` or `conflict` turn's `text` comes only from
`get_plan_geometry`, `get_takeoff` or `list_walls` (no confidence level) and from no `ask_drawings` answer or the
user's message, the server appends one sentence saying it is not rated.

"Are you sure?" (added 2026-11-14): the agent calls `review_answer`, which gives back the chat's latest `ask_drawings`
answer as its readers judged it (value, level and why, the check's reason, the disputed marks with their evidence
ids), so the turn answers from the level and the disputed marks, cites them, and returns that answer in `answers`.

`view` (added 2026-11-14) is the plan the turn wants on screen, or null when it has no place: `{drawing_id, name,
page, box, marks: [{n, label, box, polygon}], caption, source}`, all in page fractions. `source: "show_on_plan"`:
the agent called the `show_on_plan` tool (places of this chat by evidence id, or every mark, or the disputed ones,
of the chat's latest `ask_drawings` answer, which then comes back in `answers`); its marks are added to `evidence`
after the cited ones. `source: "evidence"`: the page of `[1]` with every cited place on it; an `edit` turn's view is
the proposal's page around its geometry. `box` is the marks' union with a margin, the box to focus; each mark's `n`
is its `evidence` item. Places minted in earlier turns stay citable: a follow-up may cite them (numbers in `text`
still come from this turn's tool results).

Asking about an open issue first (added 2026-11-15, decision [0018](decisions/0018-chat-asks-issues.md)): when the
chat's `ask_drawings` answer rests on an open issue nobody answered or skipped (a `needs_person` conflict on the
same quantity, a reading flag on a drawing that gave a value, an `unrelated_file`
the judge was unsure of when every drawing refused), the turn ends as `kind: "ask_issue"` with `issue` (the
`Issue` as `GET …/issues` gives it) and `options`: a conflict's values (`value` set), the issue's suggestions, then
"Skip for now" (`skip: true`); `answers` is `[]`. The next request sends `issue_answer: {issue_id, text, by, value?,
skip?}` with its `message`; 422 `validation` when the chat is not asking about that issue. A `value` settles the
conflict (a person's `settle`, the note names `by`); any other answer but a skip is saved as the issue's `answer`.
A skip is kept with the project and that issue is never asked again. That request then answers the held question;
after a skip its `text` ends "This rests on an open issue on <drawing>: <label>. Do you have other questions?". At
most 2 asks per question. `issue`, `Option.value` and `Option.skip` are left out when not set.

`next` (added 2026-11-14) is 0 to 3 follow-up chips after a complete `answer` or `conflict` turn, `[{label,
message}]` like `options`; a click sends `message` as the next message. The server builds them from the turn's tool
results, never from the model's text, in this order: "Show them on the plan" (`message` "Show me where they are")
when the answer has more marks than the view shows; "Are you sure?" when an answer is rated Medium or Low or has
disputed marks, not after a review; "How big is <label>?" when the answer names a room `find_rooms` returned without
an area. `next` is `[]` on a turn with `options` and on every other kind.

<!-- fixture: chat_answer.json -->
```json
{
  "chat_id": "c4a7c0000001",
  "turn": 1,
  "kind": "answer",
  "text": "The drawings answer this below [1][2].",
  "evidence": [
    {
      "n": 1,
      "id": "ev_3",
      "drawing_id": "adeefbbcc17559fc",
      "name": "Drawn plan 1",
      "page": 1,
      "box": [
        0.49333,
        0.225,
        0.50667,
        0.275
      ],
      "label": "door",
      "sure": null,
      "level": null
    },
    {
      "n": 2,
      "id": "ev_9",
      "drawing_id": "44cc9f0d991eafe3",
      "name": "Drawn plan 2",
      "page": 1,
      "box": [
        0.49333,
        0.225,
        0.50667,
        0.275
      ],
      "label": "door",
      "sure": null,
      "level": null
    }
  ],
  "edit": null,
  "options": null,
  "steps": [
    {
      "n": 1,
      "tool": "ask_drawings",
      "label": "Asked the drawings: How many doors are there?",
      "status": "ok",
      "ms": 12.5
    }
  ],
  "model": "rules",
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "answers": [
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f1"
        },
        {
          "drawing_id": "44cc9f0d991eafe3",
          "name": "plans/flat-b.pdf",
          "answer": {
            "question": "How many doors are there?",
            "drawing_id": "44cc9f0d991eafe3",
            "file": "plans/flat-b.pdf",
            "pages": [
              {
                "page": 1,
                "width": 600.0,
                "height": 400.0,
                "unit": "pt",
                "url": "/api/drawings/44cc9f0d991eafe3/pages/1.png",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f3"
        },
        {
          "drawing_id": "1db9bcf1e67e27a3",
          "name": "model/house.ifc",
          "answer": {
            "question": "How many doors are there?",
            "drawing_id": "1db9bcf1e67e27a3",
            "file": "model/house.ifc",
            "pages": [],
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
              "arithmetic": "2 door objects in the model",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f8"
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
              "text": "This sheet wasn't read, so nothing on it was counted or measured: this setup has no reader for this kind of sheet. You can still ask about the project's other drawings.",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f4"
        },
        {
          "drawing_id": "37f6819bd17d65d9",
          "name": "photos/plan-photo.jpg",
          "answer": {
            "question": "How many doors are there?",
            "drawing_id": "37f6819bd17d65d9",
            "file": "photos/plan-photo.jpg",
            "pages": [
              {
                "page": 1,
                "width": 1600.0,
                "height": 1200.0,
                "unit": "px",
                "url": "/api/drawings/37f6819bd17d65d9/pages/1.png",
                "normalised": {
                  "exif": null,
                  "rotated": 0,
                  "deskew_deg": 0.0,
                  "rectified": false,
                  "quad": null,
                  "width": 1600,
                  "height": 1200,
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
              "text": "This sheet wasn't read, so nothing on it was counted or measured: this setup has no reader for this kind of sheet. You can still ask about the project's other drawings.",
              "can_answer": []
            },
            "method": "refused:not-in-drawing",
            "explanation": "the drawing model does not give door",
            "reader": {
              "route": "raster",
              "source": "photos/plan-photo.jpg",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f6"
        }
      ],
      "total": null,
      "total_unit": null,
      "total_sure": false,
      "total_level": null,
      "total_note": "3 drawings answered; they may show the same rooms, so the numbers are not added up; 2 drawings give no reliable number for it.",
      "why_no_total": "3 drawings answered; they may show the same rooms, so the numbers are not added up.",
      "refused_note": "2 drawings give no reliable number for it."
    }
  ],
  "view": {
    "drawing_id": "adeefbbcc17559fc",
    "name": "Drawn plan 1",
    "page": 1,
    "box": [
      0.4633,
      0.195,
      0.5367,
      0.305
    ],
    "marks": [
      {
        "n": 1,
        "label": "door",
        "box": [
          0.49333,
          0.225,
          0.50667,
          0.275
        ],
        "polygon": null
      }
    ],
    "caption": null,
    "source": "evidence"
  },
  "next": [
    {
      "label": "Show them on the plan",
      "message": "Show me where they are"
    }
  ]
}
```

Something no tool can answer is `dont_know` with the reason; a cap (8 steps, `AGENT_TURN_USD`, 60 s, the Gemini
budget, the same call a third time) ends a turn the same way.

<!-- fixture: chat_dont_know.json -->
```json
{
  "chat_id": "c4a7c0000001",
  "turn": 2,
  "kind": "dont_know",
  "text": "This question isn't one I can turn into a count, area, length or volume.",
  "evidence": [],
  "edit": null,
  "options": [
    {
      "label": "area of room (indoor)",
      "message": "What is the net floor area of all indoor rooms in m²?"
    },
    {
      "label": "door count",
      "message": "How many doors are there?"
    },
    {
      "label": "window count",
      "message": "How many windows are there?"
    },
    {
      "label": "toilet count",
      "message": "How many toilets are there?"
    }
  ],
  "steps": [
    {
      "n": 1,
      "tool": "ask_drawings",
      "label": "Asked the drawings: What is the fire rating of the doors?",
      "status": "ok",
      "ms": 12.5
    }
  ],
  "model": "rules",
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "answers": [
    {
      "question": "What is the fire rating of the doors?",
      "parts": [
        {
          "drawing_id": "adeefbbcc17559fc",
          "name": "plans/flat-a.pdf",
          "answer": {
            "question": "What is the fire rating of the doors?",
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
                },
                {
                  "quantity": "sink",
                  "label": "sink count",
                  "question": "How many sinks are there?"
                },
                {
                  "quantity": "bathtub",
                  "label": "bathtub count",
                  "question": "How many bathtubs are there?"
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f1"
        },
        {
          "drawing_id": "44cc9f0d991eafe3",
          "name": "plans/flat-b.pdf",
          "answer": {
            "question": "What is the fire rating of the doors?",
            "drawing_id": "44cc9f0d991eafe3",
            "file": "plans/flat-b.pdf",
            "pages": [
              {
                "page": 1,
                "width": 600.0,
                "height": 400.0,
                "unit": "pt",
                "url": "/api/drawings/44cc9f0d991eafe3/pages/1.png",
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
                },
                {
                  "quantity": "sink",
                  "label": "sink count",
                  "question": "How many sinks are there?"
                },
                {
                  "quantity": "bathtub",
                  "label": "bathtub count",
                  "question": "How many bathtubs are there?"
                }
              ]
            },
            "method": "refused:unsupported-question",
            "explanation": "no count, area, length or volume asked for",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f3"
        },
        {
          "drawing_id": "3b3ce7db34257f63",
          "name": "scans/ground-floor.png",
          "answer": {
            "question": "What is the fire rating of the doors?",
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
              "code": "unsupported-question",
              "text": "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.",
              "can_answer": []
            },
            "method": "refused:unsupported-question",
            "explanation": "no count, area, length or volume asked for",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f4"
        },
        {
          "drawing_id": "37f6819bd17d65d9",
          "name": "photos/plan-photo.jpg",
          "answer": {
            "question": "What is the fire rating of the doors?",
            "drawing_id": "37f6819bd17d65d9",
            "file": "photos/plan-photo.jpg",
            "pages": [
              {
                "page": 1,
                "width": 1600.0,
                "height": 1200.0,
                "unit": "px",
                "url": "/api/drawings/37f6819bd17d65d9/pages/1.png",
                "normalised": {
                  "exif": null,
                  "rotated": 0,
                  "deskew_deg": 0.0,
                  "rectified": false,
                  "quad": null,
                  "width": 1600,
                  "height": 1200,
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
              "code": "unsupported-question",
              "text": "This question isn't one I can turn into a count, area, length or volume. Try one of these instead.",
              "can_answer": []
            },
            "method": "refused:unsupported-question",
            "explanation": "no count, area, length or volume asked for",
            "reader": {
              "route": "raster",
              "source": "photos/plan-photo.jpg",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f6"
        },
        {
          "drawing_id": "1db9bcf1e67e27a3",
          "name": "model/house.ifc",
          "answer": {
            "question": "What is the fire rating of the doors?",
            "drawing_id": "1db9bcf1e67e27a3",
            "file": "model/house.ifc",
            "pages": [],
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
                  "quantity": "door|model",
                  "label": "door count (model)",
                  "question": "How many doors are there in the building model?"
                },
                {
                  "quantity": "door",
                  "label": "door count",
                  "question": "How many doors are there?"
                },
                {
                  "quantity": "window|model",
                  "label": "window count (model)",
                  "question": "How many windows are there in the building model?"
                },
                {
                  "quantity": "window",
                  "label": "window count",
                  "question": "How many windows are there?"
                },
                {
                  "quantity": "wall|model",
                  "label": "wall count (model)",
                  "question": "How many walls are there in the building model?"
                }
              ]
            },
            "method": "refused:unsupported-question",
            "explanation": "no count, area, length or volume asked for",
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
            },
            "check": null,
            "level": null
          },
          "file_id": "f8"
        }
      ],
      "total": null,
      "total_unit": null,
      "total_sure": false,
      "total_level": null,
      "total_note": "No drawing answered it: 5 drawings can't answer this question.",
      "why_no_total": "No drawing answered it.",
      "refused_note": "5 drawings can't answer this question."
    }
  ],
  "view": null,
  "next": []
}
```

A plan edit is a proposal computed from the drawn geometry (decision 0013 §4): `removed` and `added` geometry and
each changed room's `polygon` in page fractions, `area_before_m2` → `area_after_m2`, `unknowns` (whether a wall
carries load) and `flags`. No drawing is changed. A plan whose walls are not drawn as geometry (a scan, a sheet
without wall fills) gets `dont_know` saying so.

<!-- fixture: chat_edit.json -->
```json
{
  "chat_id": "c4a7c0000002",
  "turn": 1,
  "kind": "edit",
  "text": "Proposed: Bagno 1.01 + Stanza 1.02: 20.66 → 21.02 m². Removed: Wall W1, 2.5 m, 0.1 m thick; door, no longer needed. Whether wall W1 is load-bearing: this drawing does not say.",
  "evidence": [
    {
      "n": 1,
      "id": "ev_1",
      "drawing_id": "5c4ed01e00000003",
      "name": "Drawn plan 1",
      "page": 1,
      "box": [
        0.2999,
        0.25,
        0.32257,
        0.4626
      ],
      "label": "W1",
      "sure": null,
      "level": null
    }
  ],
  "edit": {
    "proposal_id": "p1",
    "drawing_id": "5c4ed01e00000003",
    "page": 1,
    "state": "proposed",
    "removed": [
      {
        "id": "W1",
        "polygon": [
          [
            0.3084,
            0.25
          ],
          [
            0.3084,
            0.32087
          ],
          [
            0.3084,
            0.39173
          ],
          [
            0.3084,
            0.4626
          ],
          [
            0.31407,
            0.4626
          ],
          [
            0.31407,
            0.39173
          ],
          [
            0.31407,
            0.32087
          ],
          [
            0.31407,
            0.25
          ]
        ],
        "label": "Wall W1, 2.5 m, 0.1 m thick"
      },
      {
        "id": "e1",
        "polygon": [
          [
            0.3174,
            0.32087
          ],
          [
            0.3174,
            0.39173
          ],
          [
            0.30507,
            0.39173
          ],
          [
            0.30507,
            0.32087
          ]
        ],
        "label": "door, no longer needed"
      }
    ],
    "added": [],
    "rooms": [
      {
        "id": "r1+r2",
        "label": "Bagno 1.01 + Stanza 1.02",
        "polygon": [
          [
            0.16667,
            0.25
          ],
          [
            0.16667,
            0.25002
          ],
          [
            0.16667,
            0.46258
          ],
          [
            0.16667,
            0.4626
          ],
          [
            0.16668,
            0.4626
          ],
          [
            0.49774,
            0.4626
          ],
          [
            0.49775,
            0.4626
          ],
          [
            0.49775,
            0.46258
          ],
          [
            0.49775,
            0.25002
          ],
          [
            0.49775,
            0.25
          ],
          [
            0.49774,
            0.25
          ],
          [
            0.16668,
            0.25
          ]
        ],
        "area_before_m2": 20.66,
        "area_after_m2": 21.02,
        "was": [
          "r1",
          "r2"
        ]
      }
    ],
    "unknowns": [
      "Whether wall W1 is load-bearing: this drawing does not say."
    ],
    "flags": [
      {
        "code": "structural",
        "text": "Before removing a wall, a structural engineer has to confirm it does not carry load."
      },
      {
        "code": "wet_room",
        "text": "A wet room changes: its waterproofing is redone and inspected."
      }
    ],
    "law": null,
    "services": null,
    "services_change": null
  },
  "options": null,
  "steps": [
    {
      "n": 1,
      "tool": "list_drawings",
      "label": "Listed the project's drawings",
      "status": "ok",
      "ms": 12.5
    },
    {
      "n": 2,
      "tool": "list_walls",
      "label": "Listed the walls of Drawn plan 1, page 1",
      "status": "ok",
      "ms": 12.5
    },
    {
      "n": 3,
      "tool": "propose_remove_wall",
      "label": "Proposed removing wall W1",
      "status": "ok",
      "ms": 12.5
    }
  ],
  "model": "rules",
  "cost_usd": 0.0,
  "latency_s": 0.002,
  "answers": [],
  "view": {
    "drawing_id": "5c4ed01e00000003",
    "name": "Drawn plan 1",
    "page": 1,
    "box": [
      0.1367,
      0.22,
      0.5278,
      0.4926
    ],
    "marks": [
      {
        "n": 1,
        "label": "W1",
        "box": [
          0.2999,
          0.25,
          0.32257,
          0.4626
        ],
        "polygon": null
      }
    ],
    "caption": null,
    "source": "evidence"
  },
  "next": []
}
```

Errors: 404 unknown project or chat, 409 project not done or a turn of this chat still running, 422 a bad body,
503 `CHAT_MODEL=off`.

### `POST /api/projects/{project_id}/chat/stream`

The same body and the same turn as `POST .../chat`, sent as Server-Sent Events while the turn runs (added
2026-11-14). Read it with `fetch` and the response body's reader (`EventSource` cannot POST). Errors known before the
turn starts (404, 409, 422, 503) are plain JSON responses as on `POST .../chat`. After a 200, each event is
`event: <type>` and one line of JSON `data`; `: ping` comes when nothing else was sent for 10 s. Events in order:
`turn` `{chat_id, turn}` (first); per model step `thinking` `{step}`, `plan` `{step, calls: [{n, tool, label}]}`
(the step's tool calls, in the server's words), and per call `tool_call` `{n, tool, label}` then `tool_result` (a
`steps` item plus `summary`, a server-written line of what the tool found, or null); `view` (a `View`, when
`show_on_plan` ran; its mark numbers may change in the final turn); `checking` `{status: "ok" | "retry", reason}`
when the agent hands in its answer (`retry`: the server sent it back, the reason in plain words); last, exactly
one of `answer` (the `ChatTurn`, as `POST .../chat` returns it) or `error` `{status, detail}`. Nothing the model
writes is streamed except through the checked `answer`. A client that goes away does not stop the turn: it runs to
its end and is stored.

### `POST /api/projects/{project_id}/chat/{chat_id}/proposals/{proposal_id}`

Body `{"action": "accept" | "reject"}`. Returns the proposal with its new `state` (`accepted` or `rejected`); 404 an
unknown chat or proposal, 409 a proposal already decided. Accepting records the person's call; the drawing file is
unchanged.

<!-- fixture: chat_proposal_accepted.json -->
```json
{
  "proposal_id": "p1",
  "drawing_id": "5c4ed01e00000003",
  "page": 1,
  "state": "accepted",
  "removed": [
    {
      "id": "W1",
      "polygon": [
        [
          0.3084,
          0.25
        ],
        [
          0.3084,
          0.32087
        ],
        [
          0.3084,
          0.39173
        ],
        [
          0.3084,
          0.4626
        ],
        [
          0.31407,
          0.4626
        ],
        [
          0.31407,
          0.39173
        ],
        [
          0.31407,
          0.32087
        ],
        [
          0.31407,
          0.25
        ]
      ],
      "label": "Wall W1, 2.5 m, 0.1 m thick"
    },
    {
      "id": "e1",
      "polygon": [
        [
          0.3174,
          0.32087
        ],
        [
          0.3174,
          0.39173
        ],
        [
          0.30507,
          0.39173
        ],
        [
          0.30507,
          0.32087
        ]
      ],
      "label": "door, no longer needed"
    }
  ],
  "added": [],
  "rooms": [
    {
      "id": "r1+r2",
      "label": "Bagno 1.01 + Stanza 1.02",
      "polygon": [
        [
          0.16667,
          0.25
        ],
        [
          0.16667,
          0.25002
        ],
        [
          0.16667,
          0.46258
        ],
        [
          0.16667,
          0.4626
        ],
        [
          0.16668,
          0.4626
        ],
        [
          0.49774,
          0.4626
        ],
        [
          0.49775,
          0.4626
        ],
        [
          0.49775,
          0.46258
        ],
        [
          0.49775,
          0.25002
        ],
        [
          0.49775,
          0.25
        ],
        [
          0.49774,
          0.25
        ],
        [
          0.16668,
          0.25
        ]
      ],
      "area_before_m2": 20.66,
      "area_after_m2": 21.02,
      "was": [
        "r1",
        "r2"
      ]
    }
  ],
  "unknowns": [
    "Whether wall W1 is load-bearing: this drawing does not say."
  ],
  "flags": [
    {
      "code": "structural",
      "text": "Before removing a wall, a structural engineer has to confirm it does not carry load."
    },
    {
      "code": "wet_room",
      "text": "A wet room changes: its waterproofing is redone and inspected."
    }
  ],
  "law": null,
  "services": null,
  "services_change": null
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
  "drawing_id": "44cc9f0d991eafe3",
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
        "status": "conflict",
        "value_marks": [
          [
            {
              "page": 1,
              "box": [
                0.16667,
                0.125,
                0.5,
                0.375
              ],
              "label": "polygon_x_scale",
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
              ]
            }
          ],
          [
            {
              "page": 1,
              "box": [
                0.17367,
                0.17946,
                0.21269,
                0.19027
              ],
              "label": "printed_label",
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
              ]
            }
          ]
        ]
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
      "value": 52.998,
      "unit": "m2",
      "original_value": 52.998,
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
- `settled`: the value a surveyor chose with `settle`, and when; `note`: their answer in words when they typed one
  (else null).
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
  the next mark edit of that quantity. Optional `note` (1-280 characters): the person's answer in words, kept in
  `settled.note` (the conflict card's typed answer). With `note` and no `value`, the value in use is kept with the
  note and the quantity counts as settled; the screen sends `value` too when the typed answer has a number.
  `unsettle` drops the note with the value.
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
  "drawing_id": "44cc9f0d991eafe3",
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
        "at": "2026-11-14T08:05:00Z",
        "note": null
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
        "status": "conflict",
        "value_marks": [
          [
            {
              "page": 1,
              "box": [
                0.16667,
                0.125,
                0.5,
                0.375
              ],
              "label": "polygon_x_scale",
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
              ]
            }
          ],
          [
            {
              "page": 1,
              "box": [
                0.17367,
                0.17946,
                0.21269,
                0.19027
              ],
              "label": "printed_label",
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
              ]
            }
          ]
        ]
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
        "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024, 4 § 2 mom.",
        "url": "https://www.finlex.fi/fi/lainsaadanto/2024/631",
        "quote": "Asuin- ja majoitushuoneen ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
        "quote_en": "The room area of a residential or accommodation room and of a work space must, however, always be at least 7 square metres."
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
        "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024, 5 § 1 mom.",
        "url": "https://www.finlex.fi/fi/lainsaadanto/2024/631",
        "quote": "Asuin- ja majoitushuoneen ikkunan valoaukon on oltava vähintään 1/10 huonealasta.",
        "quote_en": "The light opening of the window of a residential or accommodation room must be at least 1/10 of the room area."
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
            "ref": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024, 4 § 2 mom.",
            "url": "https://www.finlex.fi/fi/lainsaadanto/2024/631",
            "quote": "Asuin- ja majoitushuoneen ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
            "quote_en": "The room area of a residential or accommodation room and of a work space must, however, always be at least 7 square metres."
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

## Building law

The law knowledge base the AI searches instead of carrying the laws in its prompt (decision
[0014](decisions/0014-law-knowledge-base.md)): one file per law in `backend/app/laws/<pack>/`, one clause per
subsection, `text` verbatim from the official source and `text_en` our unofficial translation. Packs are `fi` and
`ch-zh` (Swiss federal law and the Canton of Zürich), the rule packs' ids. The examples are the test laws of
`backend/tests/fixtures/laws/` (made up).

### `GET /api/laws`

Both packs, always; `laws: []` while a pack has none. `topics`: the topics its clauses use, in the closed list's
order.

```json
{
  "packs": [
    {
      "id": "fi",
      "laws": [
        {"law_id": "fi-test-1", "number": "1/2026", "title_en": "Test decree on residential spaces",
         "clauses": 2, "topics": ["rooms", "fire", "escape-routes"]}
      ]
    },
    {"id": "ch-zh", "laws": [...]}
  ]
}
```

### `GET /api/laws/{pack}/search?q=<words>&topic=<topic>&limit=<1-20>`

`q` 1-500 characters, words only (quotes, `*`, `NEAR`, `-` are plain words); a word also finds longer words it
starts ("Fluchtweg" finds "Fluchtwege"), case and accents ignored; words of 1-2 letters, a few English stopwords
("when", "do", "need", ...) and words past the 20th are ignored, so a query of only those has no hits. Clauses with
every word come first, then clauses with any word fill `limit`, each group by score; old wording (an id with
`-anhang-`) comes after every current clause. `topic` one of `rooms accessibility fire
escape-routes stairs-railings doors-windows ventilation energy sound moisture structure daylight parking outdoor
distances-heights permits-procedure general`; `limit` default 5. `title_en` and `url` are the law's; `score` is
-BM25, higher is better. An unknown pack is 404 `unknown-pack`; a bad `q`, `topic` or `limit` 422 `validation`.

```json
{
  "pack": "fi",
  "query": "minimum bedroom area",
  "hits": [
    {"id": "fi-test-1-4-2", "law_id": "fi-test-1", "ref": "4 § 2 mom.",
     "title_en": "Test decree on residential spaces",
     "summary_en": "Every habitable room has a floor area of at least 7 m2.",
     "url": "https://www.finlex.fi/fi/lainsaadanto/2026/1", "score": 2.745}
  ]
}
```

### `GET /api/laws/clauses/{clause_id}`

The clause as its file has it, plus its law's `law_id`, `law_number`, `law_title`, `law_title_en`, `url`,
`language` (of `text`), `checked` and `status_note`. `text_en` is null only for a law in English; show it as an
unofficial translation. An unknown id is 404 `not-found`.

```json
{
  "id": "fi-test-1-4-2", "ref": "4 § 2 mom.", "heading": "Huoneala", "heading_en": "Room area",
  "text": "Asuintilan huonealan on oltava vähintään 7 neliömetriä.",
  "text_en": "The room area of a residential space must be at least 7 square metres.",
  "summary_en": "Every habitable room has a floor area of at least 7 m2.",
  "keywords": ["room area", "minimum area", "bedroom", "huoneala", "makuuhuone"],
  "topics": ["rooms"],
  "limits": [{"what": "habitable room area", "comparison": ">=", "value": 7.0, "unit": "m2"}],
  "drawing_checkable": true,
  "law_id": "fi-test-1", "law_number": "1/2026", "law_title": "Testiasetus asuintiloista",
  "law_title_en": "Test decree on residential spaces",
  "url": "https://www.finlex.fi/fi/lainsaadanto/2026/1", "language": "fi", "checked": "2026-11-14",
  "status_note": "A made-up test law: its clauses point nowhere real."
}
```

## What is not in v1

- Contested marks: a conflict is shown per quantity, with both values and, where the method has one, the `box` it
  read; the frontend does not build an amber per-item mark.
- Adding a mark with a value to an area or length (marks are added to counts only).
- Free page widths, CORS, server push (progress is polled).
- Editing a room's outline or label.

## Changelog

- 2026-11-14, behaviour (docs refresh of the evening's merges; no shape change): the vector reader's printed scale
  reads imperial ratios, skips a ramp slope, and gives no scale to a sheet that prints several different ones and
  has no scale bar (#282); a scale bar needs one unit, metres or feet (#301). `VECTOR_FALLBACK=raster` (default
  `off`) reads a drawn PDF that matches no sheet style on the raster route, flagged and never certified (#283); a
  scanned PDF's page is rendered once and shared by its readers and its answers (#280, #295). Under
  `CARBON_READER=large` (default off) Carbon's door boxes take the detector's door box where one lies inside (#310,
  `attrs.box_from` is `detector`), and the independent Carbon reads of a raster sheet run at the same time (#306).
  An area (or length) question with a room type or a printed label and a room number ("bathroom 1.01", "Bagno 1.01")
  names that room (#313); a count question does not take the room. A stage's cost in a trace is exact to the
  pico-dollar (#314).
- 2026-11-14, additive (#311): `sheet.discipline` on a file's triage, one of the nine values above or null, from
  the sheet-kind reply's kind, title and number. `docs/api/openapi-v1.json` already carries it.
- 2026-11-14, value only (keycheck review-315, chat-ux): `POST /api/projects/{project_id}/ask`'s `total` is in
  whole m² when a summed part is an area on an estimated scale, as that part's `answer` already was (#294): the
  Finnish flat's kitchen gave `answer` 5 and `total` 4.88, now 5 and 5 (`total_note` too). Shapes unchanged.
- 2026-11-14, text only (board #14 c6882199550, Tudor's chat QA): refusal and reason texts that sounded like a
  missing feature say what was and wasn't read. A `no-reader` refusal on a route with no reader: "This sheet wasn't
  read, so nothing on it was counted or measured: this setup has no reader for this kind of sheet. You can still ask
  about the project's other drawings."; the policy refusal: "On sheets like this one, our reader got this kind of
  question wrong too often when we measured it, so no number is given."; a file's `reason` with no reader: "not
  read: this setup has no reader for the image route"; a DWG: "DWG files can't be opened here; export it as a PDF
  and upload that"; `total_note`/`refused_note` and issue `why`: "gives/give no reliable number for it" (was
  "has/have no reader for it"). Shapes unchanged.
- 2026-11-14, additive (board #203): new `POST /api/projects/{project_id}/files?name=`, a png or jpeg added to a
  done project and read alone in the background; 202 `FileStatus`. New error 415 `unsupported`. New fixture
  `file_added.json`.
- 2026-11-14, additive (decision 0013, agent chat): `POST /api/projects/{project_id}/chat` and
  `POST /api/projects/{project_id}/chat/{chat_id}/proposals/{proposal_id}`; `GET /api/info` gains `chat`
  (`model`, `available`, `reason`; last). Settings `CHAT_MODEL`, `AGENT_MODEL`, `AGENT_BASE_URL`,
  `AGENT_PRICE_IN_PER_M`, `AGENT_PRICE_OUT_PER_M`, `AGENT_PRICE_CACHED_PER_M` (prompt tokens read from cache), `AGENT_TURN_USD`, `AGENT_MAX_STEPS`, `AGENT_THINKING` (the model's `reasoning_effort`, default `low`). Fixtures `chat_request`,
  `chat_answer`, `chat_dont_know`, `chat_edit`, `chat_proposal_accepted`.
- 2026-11-14, additive (decision 0013): `ChatTurn.answers` (last), the `ProjectAnswer`s a turn rests on;
  `ChatTurn.evidence` lists only the cited places; `options` may come with any kind.
- 2026-11-14, behaviour (brief r8 BQ, Bogdan "make them high"): `CARBON_LEVELS=ladder`. As `demote`, and a Medium
  raster answer Gemini Carbon counted the same gets `level` high with basis `carbon` and no `check`; `line.sure`
  stays false. Off and `demote` are unchanged. No shape change.
- 2026-11-14, additive (decision 0012 Amendment 1, contract v1.3): text documents and unread files in the
  evidence index: `how` `text` and `listed`, the part `text` (ids `f7-text-12`; a hit's `page` is the passage's
  page), the kinds `text_document`, `text_file`, `text_pages`, `not_read` and the listed probe kinds, and `FileStatus.evidence.text_pages`
  and `text_chars` filled.
- 2026-11-14, additive (decision 0012 Amendment 1, contract v1.3): `FileStatus.evidence` (left out unless
  `EVIDENCE_SCOPE=all_non_plan`); evidence hits and details gain `how` (`described`, later `text` and `listed`),
  and a hit's `kind` may be a sheet kind. The empty-index `note` names `EVIDENCE_SCOPE`.
- 2026-11-14, additive (RESOLVER): `POST /api/projects/{project_id}/resolve`;
  `resolved` on takeoff rows, conflicts (`ConflictEntry`) and answers (`AnswerView`, with `resolver_note` when the
  model gave no reply), each absent while `RESOLVER` is off. No enum value changes. An answer's `resolved`
  sits beside its value: `answer`, `check`, `line.sure` and `level` are unchanged (a model's check is never
  certified); its `cost_usd` includes the resolver's call. Also `conflicts_picked` on `GET /api/projects` and
  `GET /api/projects/{id}`, and `resolved` on issues (`Issue`). `RESOLVER=carbon` resolves an upload on its own
  once ingest is done.
- 2026-11-14, behaviour: `TRIAGE_DESCRIBER=carbon` describes with gemini-4-carbon at thinking low (rag's
  pilot), the same describe-6 prompt and form; `Description.model` is then `gemini-4-carbon-low, describe-6`
  and `cost_usd` is at Carbon's 4 / 20 USD per M tokens. A PDF pdfium cannot open is described as
  unavailable with pdfium's reason (it raised before). No shape change.
- 2026-11-14, additive (decision 0014): new `GET /api/laws`, `GET /api/laws/{pack}/search?q=&topic=&limit=` and
  `GET /api/laws/clauses/{clause_id}`, the building-law knowledge base. An unknown pack is 404 `unknown-pack`.
- 2026-11-14, additive (decision 0012): `GET /api/projects/{id}/evidence/search?q=&k=&include_unrelated=` and
  `GET /api/projects/{id}/evidence/{evidence_id}`, the project's evidence index (described non-plan files; BM25 +
  a local multilingual embedder). New fixtures `evidence_search`, `evidence_detail`.
- 2026-11-14, content (board #220): the `fi` pack cites YMa 631/2024 (in force 2025-01-01, under the Building
  Act 751/2023), which replaced 1008/2017: the 7 m2 rule is 4 § 2 mom. and the window rule 5 § 1 mom., each with
  the decree's own sentence and its Finlex link; the limits are unchanged. Fixtures `info`, `checks`,
  `project_checks` and `project_issues_checks` show the new citation. No shape change.
- 2026-11-14, behaviour (safety rule, orchestrator): on the raster route, an answer on a drawing where the
  detector found no plan and no located element is never certified (`sure` false, `check` set) and its `level`
  is low with basis `page`. No shape change.
- 2026-11-14, behaviour: the Gemini describer's prompt is `describe-6` (`Description.model` ends
  `describe-6`): a home address is written without its house number and postal code in every field
  (decision 0010); `describe-5` kept a house's street address on all 8 of its sheets that print one. No
  shape change. Replies cached under `describe-5` are not reused: each described file is asked again once.
- 2026-11-14, additive (decision 0011, Bogdan: "the confidence levels should be high medium low"): `level` on
  `POST /api/ask`'s answer: `{level: high|medium|low, basis, text}` or null, computed by the backend from the
  check policy; high exactly when the answer is certified (`check` null). `total_level` on the project ask: the
  lowest level among the total's parts. `CHECK_POLICY`'s file may carry `medium` per family, `level` and `dev` per
  route and a `levels` block; a file without them loads as before and gives `level` null. Every answer fixture
  gains `level`; `answer_certified`, `answer_double_check` and `answer_double_check_rooms` show high, medium and
  low. `line` (answer_v1.1) is unchanged.
- 2026-11-14, additive (QA R9 area 4, `tools/smoke.py`): `GET /api/info` gains `commit`, the git commit the backend
  was started from (setting `APP_COMMIT`, which `tools/qa-env.sh` sets to the exported commit), or null when
  unset. Fixture `info.json` gains it (last).
- 2026-11-14, behaviour: `GET /api/info` `no_keys` is false also when a keyed source is in
  `RASTER_PHOTO_COMPONENTS` or `DOUBLE_CHECK_READERS`, or when `TRIAGE_DESCRIBER=gemini` runs (a triage
  classifier on); it said true for these. No shape change.
- 2026-11-14, additive (board #14, plain drawing names): `Issue.drawing_name`, the drawing's `name` from
  `GET /api/projects/{id}` (null with no drawing). The pages of `issues.zip` name the drawing by it instead of its
  file. `file` is unchanged.
- 2026-11-14, additive (board #14, Tudor's conflict card asks 8-10): `Edit.note` on `settle` (1-280 characters, a
  typed answer in words; without `value` the value in use is kept) and `Settled.note` (null when none); a `note`
  on another action, empty or too long is 422 `validation`. `settle` with neither `value` nor `note` stays 422
  `invalid`. `ConflictEntry` (`GET /api/projects/{id}/review`) gains `title`, `why` and `suggestions`. Fixtures
  `project_review.json` and `takeoff_edited.json` gain the new fields (last in each object).
- 2026-11-14, additive (board #14, Tudor's asks 1, 3, 4): new `POST /api/projects/{id}/issues/{issue_id}/answer`
  (`{text, by}` or `{undo: true}`), kept with the project. `Issue` gains `answer` (`{text, by, at}` or null),
  `suggestions` (answer chips by kind) and `label` (short legend text). `GET /api/projects/{id}` gains
  `conflicts_open`, `issues_open` and `issues_to_answer`, the same numbers as `GET /api/projects`, which gains
  `issues_to_answer` (open issues that are not notes and have no answer). An answer does not change an issue's
  `state`. New fixtures `issue_answer_request`, `issue_answered`.
- 2026-11-14, additive (board #14 item 6): each entry of `GET /api/projects/{id}`'s `drawings` gains `name` (a
  plain name from its kind, number and page, never the file name) and `credit` (its licence credit, as on
  `GET /api/drawings/{id}`, or null). Fixtures `project.json` and `project_triaged.json` show both.
- 2026-11-14, additive (board #14, Tudor's asks 2, 5 and 11): `value_marks` on every conflict and agreement of a
  quantity (`QuantityConflict`, in the takeoff, the review's conflicts and an answer): `value_marks[i]` lists
  `{page, box, label}` for each item of `values[i]`, so a legend can outline them. A count of an element class or
  of rooms lists what each method counted: the elements or rooms the plan draws, and the objects of the building
  model that the sheet draws (a model object the sheet does not draw has no position, so a list can be shorter
  than the count). Any other value with a `page` and `box` (a room area, a scale, a schedule's count) is one mark,
  labelled with its method. `[]` when no value has a position. `ProjectAnswer.why_no_total` and `refused_note`:
  the parts of `total_note` (why there is no total; which drawings refused and why). Fixtures `answer_conflict`,
  `answer_signed`, `project_ask`, `project_review`, `takeoff`, `takeoff_edited` gain the fields.
- 2026-11-14, additive (decision 0010 section 8, board #152, PR #183): `Triage.register` (the sheet register:
  kind, has_floor_plan, photo_of_sheet, scale_shown, quality, method; null with no register-reading classifier);
  `Description.what_it_is`, `shows_building`, `visible_text` and `detail`. `TRIAGE_JUDGE=rules` judges a
  described file by the words printed on it (`related` only on a match; `unsure` for a building with no match)
  and an undescribed `other_drawing` as `unsure` (was `related`). Relaxed: `POST …/files/{file_id}/relevance`
  takes a call on any file triage set aside, described or not (was 422 `no-description` for an undescribed one),
  so every `unrelated_file` issue can be settled; a file triage did not set aside is 422 `not-triaged`, and the
  code `no-description` is no longer returned. Fixture `project_triaged.json` gains `photos/sheet.jpg` (f5).
- 2026-11-14, behaviour (golden-25): with `CHECK_POLICY` on, a plan count is certified (`sure` true, `check` null)
  only when the answer confidence's own most likely plan count is the answered one, the rule `GATE_POLICY` applies
  since #174; otherwise it asks, with `check.reason` "Please double-check the plan count: two readers count the
  plans differently." when that count is another. No shape change.
- 2026-11-14, additive (golden-21, board #14): `check` on `POST /api/ask`'s answer: `{reason, disputed: [{mark_id,
  page, box, why, readers}]}` or null, the double-check request of an answer `CHECK_POLICY` does not certify (the
  value stays; not a refusal). Null for every answer while `CHECK_POLICY` is off (the default). New fixtures
  `answer_certified`, `answer_double_check`, `answer_double_check_rooms`. A disagreement between two methods,
  an estimate or a person's unsigned edit always asks; a settle or sign-off lifts the request. Not
  `proof.check` (unchanged: how a second method measured the value). Behaviour: with `CHECK_POLICY` on, `sure`
  is true exactly when the answer is certified (`GATE_POLICY` no longer sets it), null on a refusal.
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
- 2026-11-14, text and values (R6 qa-a): a triage set-aside `reason` is "not a floor plan: <class words>"
  (P(plan) and the method are in `triage`); a settled `unrelated_file` issue of a file read as a floor plan has the
  file's `drawing_id` and links (same id); a failed or cut re-read clears `read_as_plan`, so it can be asked again.
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
- 2026-11-14, behaviour: a plan count (`floors`) is `line.sure` true only when Gemini's own most likely plan
  count is the answered one as well (two readers agree); otherwise false, whatever the score. On CubiCasa val
  it keeps 363 of 376 plan answers sure (was 376), 362 of them exact (was 372 of 376).
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
