# Golden demo path and its end-to-end test (spec, frontend v1)
Status: draft, 2026-11-14 04:52 (round-1 fixes applied), by fe-spec-golden-path.  Story: #33.  API: docs/API.md (v1).

## Purpose

The golden path is the flow we show the judges in the 3-minute pitch: a zip goes in, one file is followed through
the pipeline, a drawing answers a count and an area with its proof, refuses a question it can't answer, a surveyor
settles the disagreement and signs it off, the engineer sees it verified, and the takeoff leaves as CSV. This spec
gives the table for docs/QA.md §1 and the Playwright test that walks it on the no-keys backend in CI, with
screenshots at 390x844 and 1440x900 of every screen on the path.

Every step was run by hand on the no-keys backend of main 5092dc3 (sample archive from
`backend/scripts/make_sample_archive.py`, 2026-11-14): the values below are what it returns.

## Scope for the 06:00 merge

Deadline change (Bogdan, board #14): frontend wiring merged to main by 06:00; specs and scaffold by 05:15. The
06:00 merge holds the golden demo path only: start the sample (or upload an archive) → project file status → one
file trace → open a drawing as engineer → ask a count and an area question → the answer with its proof marks on the
page → a refusal → the project's conflicts list. That is steps 1-7 of the table under User flow, then step 8a:

| # | Action | Expected | Runs on fakes? |
| --- | --- | --- | --- |
| 8a | Click the "Surveyor" view link | the side panel's project conflicts list: "area of room (name 1.01)" and "area of room (name küche)", each with "plans/flat-b.pdf", "22.40 m² vs 30.00 m²" and "decided by rule" | yes |

Steps 8-12 (takeoff table, settle, sign-off, verified, CSV) are after QA. The e2e stays in the 06:00 scope: Playwright
on the live no-keys backend at 390x844 and 1440x900 with screenshots, run locally with `npm run e2e`; the CI `e2e`
job is after QA (its YAML stays below, ready). Answer confidence is coded against
the new shape `{signal, score, calibrated: false}` (Open point 7).

Criteria in the 06:00 scope, per spec (every other criterion of that spec is after QA):

| Spec | In the 06:00 scope |
| --- | --- |
| shared | SH-1, SH-2, SH-4, SH-5, SH-7, SH-13, SH-14, SH-15, SH-16, SH-19, SH-20, SH-21, SH-23, SH-24, SH-25, SH-26, SH-29, SH-31, SH-33, SH-34, SH-37, SH-38, SH-39, SH-40, SH-41, SH-42, SH-43 |
| viewer | VW-1, VW-2, VW-4, VW-5, VW-6, VW-9, VW-10, VW-11, VW-12, VW-13, VW-14, VW-21, VW-23, VW-26, VW-27, VW-29, VW-31, VW-33 |
| ingest | IN-1, IN-2, IN-3, IN-7, IN-8, IN-9, IN-10, IN-11, IN-12, IN-13, IN-14, IN-15, IN-16, IN-17, IN-18, IN-19, IN-21, IN-24, IN-25, IN-26, IN-27, IN-29, IN-30, IN-32, IN-33, IN-34, IN-37, IN-43, IN-44, IN-45, IN-46, IN-47 |
| engineer | EN-1, EN-2, EN-3, EN-4, EN-6, EN-8, EN-9, EN-10, EN-12, EN-13, EN-14, EN-15, EN-16, EN-18, EN-20, EN-23, EN-24, EN-25, EN-31, EN-33, EN-39, EN-40, EN-41, EN-42, EN-43, EN-45 |
| surveyor | SV-41, SV-42, SV-43, SV-46 (side panel strings only). The surveyor route shows the side panel alone until the rest lands. |
| golden-path | GP-1 to GP-8 and GP-28 (path steps 1-7, 8a), GP-14, GP-15, GP-16 to GP-22, GP-24, GP-26, GP-27. After QA: GP-9 to GP-13, GP-23, GP-25. |

For the 06:00 run GP-16's screenshots are the first seven of the list plus `08-conflicts.png` (after step 8a); the
service-down test (GP-20) stays.

## Files owned

- `frontend/e2e/golden-path.spec.ts`: the golden-path test (both viewports) and the service-down test.
- `frontend/e2e/start-backend.sh`: builds the sample archive into a temp dir and starts the backend in no-keys mode.
- `frontend/e2e/support.ts`: `startSample(page)` (home → "Try the sample project" → "Done", returns the project
  id), `shot(page, name)` (screenshot + offline text + no horizontal scroll check) and the console-error collector.
- `frontend/e2e/ingest.spec.ts`, `frontend/e2e/surveyor.spec.ts`: the [e2e] criteria of ingest.md and surveyor.md
  that the golden path does not walk. One e2e build worker owns all of `frontend/e2e/` and builds every [e2e]
  criterion of the screen specs.
- `frontend/playwright.config.ts`: two projects (`desktop`, `phone`), the two web servers, output folders.
- `frontend/package.json`: only the `e2e` script and the `@playwright/test` dev dependency (the scaffold owns the
  rest of the file).
- `frontend/.gitignore`: nothing: the root `.gitignore` has `frontend/screenshots/`, `frontend/test-results/`, `frontend/playwright-report/`.
- `.github/workflows/ci.yml`: the new `e2e` job (nothing else in the file changes).

## User flow

The golden demo path, for docs/QA.md §1 (the orchestrator moves this table there; this spec does not edit QA.md).
All steps run on the fakes: the path uses only the vector-PDF reader, the IFC second counter and the template
question parser, which need no key, so the same steps and values hold with keys.

| # | Action | Expected (what the screen shows) | Runs on fakes? |
| --- | --- | --- | --- |
| 1 | Open the app at `/#/` | Home: drop zone, "Choose a file", "Try the sample project", the list of earlier projects; the strip "Running offline: no API keys, no models" | yes |
| 2 | Click "Try the sample project" | `#/p/<id>`: "sample-project.zip", the files turn finished one by one, then "Done", "11 of 11 files finished", cost $0.00; every file row has its state in words (3 ready, 4 flagged, 2 set aside, 2 text only); 5 drawings listed | yes |
| 3 | Click the file `plans/flat-b.pdf` | `#/p/<id>/f/<file_id>` (`f3` today): state "flagged", reason "1 conflict(s) between the two methods (room_area) …"; ten stages unpack → write, `second_count` reading "5 quantities measured twice, 1 conflict(s)" | yes |
| 4 | Click "Open the drawing" | `#/p/<id>/d/<drawing_id>/engineer`: "plans/flat-b.pdf", "vector route, read from plans/flat-b.pdf by pdf …", page 1 of the plan, six suggested questions | yes |
| 5 | Click "How many doors are there?" | Answer `2`, "door count", two numbered marks 1 and 2 on the doors, "Counting rule: every element, room and plan the drawing lists counts once", "One method", Cost $0 | yes |
| 6 | Type "What is the net floor area of room 1.01?", Ask | Answer `30.00 m²`, the kitchen shaded, status "Methods disagree": "22.40 m² by polygon_x_scale", "30.00 m² by printed_label", "Kept 30.00 m²: the printed label over the outline at the sheet's scale" | yes |
| 7 | Type "What colour is the roof?", Ask | "I can't answer that from this drawing.", the reason, code `unsupported-question`, question buttons it can answer; no number | yes |
| 8 | Switch to Surveyor | `#/…/surveyor`: "Takeoff: plans/flat-b.pdf", the "To review" group first: "area of room (name 1.01)" and "area of room (name küche)", each "Methods disagree"; the first is selected, its detail shows both values | yes |
| 9 | Press "Keep A: 22.40 m² (polygon_x_scale)" (the drawn outline) | The row reads 22.40 m², "Changed in review", "Settled at 22.40 m² …" | yes |
| 10 | Type "Ana" in "Signing as", press "Sign off 22.40 m²" | The row reads "Verified"; "Signed off by Ana, <date time> UTC: 22.40 m². Engineers see this value as verified." | yes |
| 11 | Switch to Engineer, ask "What is the net floor area of room 1.01?" again | Answer `22.40 m²`, "Verified", "Verified by Ana, <date time> UTC" | yes |
| 12 | Switch to Surveyor, "Export CSV" | A download `flat-b-takeoff.csv`; its row `area:room|name=1.01` has value 22.401, status signed, original 30.0, signed by Ana | yes |

- Demo data: the synthetic sample archive (`cd backend && uv run python scripts/make_sample_archive.py`, writes
  `data/samples/sample-project.zip`, gitignored). No partner data.
- Start command: `cd backend && uv run uvicorn app.main:create_app --factory`, then
  `cd frontend && npm run build && npm run preview`; open `http://127.0.0.1:4173/#/`.
- Offline fallback: the same commands with no keys in `backend/.env` (or no `.env`); every step above works and the
  strip reads "Running offline: no API keys, no models". The sample button always sends `fresh=true`, so a rerun
  starts clean.
- Demo machine and its owner: not decided (orchestrator fills in).

Why these steps: flat-b is the sheet whose printed kitchen area (30.00) disagrees with its drawn outline (22.40), so
the trace, the engineer's conflict, the surveyor's settle and sign-off and the verified answer tell one story on one
drawing. Settling is shown rather than rejecting a mark: rejecting one of flat-b's two real doors would make the
takeoff wrong on stage (reject is covered by the surveyor spec's tests). "What is the area of the kitchen?" is
refused by the template parser today (`unsupported-question`), so step 6 uses the room number.

### The e2e test

`frontend/e2e/golden-path.spec.ts` walks the table, one `test.step` per row, in each Playwright project:

| Project | Viewport | Other |
| --- | --- | --- |
| `desktop` | 1440 x 900 | Chromium |
| `phone` | 390 x 844 | Chromium, `isMobile: true`, `hasTouch: true` |

Config (`frontend/playwright.config.ts`):
- `testDir: "e2e"`, `workers: 1`, `fullyParallel: false`: the two projects share one backend, and step 2's
  `fresh=true` resets the sign-off of the previous run, so the runs must not overlap. `retries: 0` (the path is
  deterministic; a flake is a bug). `use.trace: "retain-on-failure"`. `expect.timeout` 10 s, test timeout 90 s.
- `use.baseURL`: `http://127.0.0.1:4173`. Always `127.0.0.1`, never `localhost` (Node resolves `localhost` to `::1`
  first; uvicorn and the preview bind IPv4).
- `webServer`, two entries, `reuseExistingServer: false` for both (a developer's dev backend may have keys):
  1. `bash e2e/start-backend.sh`, `url: http://127.0.0.1:8010/health`, timeout 120 s.
  2. `npx vite preview --host 127.0.0.1 --port 4173 --strictPort` with env `BACKEND_URL=http://127.0.0.1:8010`,
     `url: http://127.0.0.1:4173`. The scaffold's `vite.config.ts` (shared.md) proxies `/api` to
     `process.env.BACKEND_URL` in both `server.proxy` and `preview.proxy`, so the production build is tested.
- With `E2E_API_URL` set, entry 1 is left out and the proxy points there: the same test then runs by hand against a
  backend with real services (QA.md §1 "run it against the real services by hand"). The test reads `GET /api/info`
  and checks the offline text shows exactly when `no_keys` is true.

`frontend/package.json` scripts: `"e2e": "npm run build && playwright test"` (`build` is the scaffold's
`tsc --noEmit && vite build`). `npm test` and `check.sh` stay vitest only (shared.md), so the existing CI `node`
job (no backend there) never runs Playwright. One Playwright run holds every file in `e2e/`; with `workers: 1` they
run one after another, and each starts with `startSample`, so no file sees another's edits.

`frontend/e2e/start-backend.sh` (run from any directory; `set -euo pipefail`):
1. `cd` to `backend/` (relative to the script), `DATA=$(mktemp -d)`.
2. `uv run --locked python scripts/make_sample_archive.py --out "$DATA/sample-project.zip"` (0.6 s).
3. Exports, overriding anything in a developer's `backend/.env` (environment beats `.env` in pydantic-settings):
   `PROJECTS_DIR=$DATA/projects`, `SAMPLE_ARCHIVE=$DATA/sample-project.zip`, `CREDIT_DATASET=$DATA/none`,
   `CREDIT_PHOTOS=$DATA/none`, `EXTRACTOR_RASTER=hello`, `RASTER_COMPONENTS=`, `RECTIFIER=none`,
   `DECISIONS_KIND=false`, `DECISIONS_CONFIDENCE=false`, `ANSWER_PRIOR=none`, `ANSWER_POLICY=`. Every setting that
   could call a key or a model is forced off; the rest keep their no-keys defaults (`EXTRACTOR_VECTOR=pdf`,
   `EXTRACTOR_BIM=ifc`, `TABLES=pdf`, `SECOND_COUNTER=ifc`, `QUESTION_PARSER=templates`).
4. `exec uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port "${E2E_API_PORT:-8010}"`.
   Port 8010, so a dev backend on 8000 is never touched.

A fresh temp `PROJECTS_DIR` per run, plus `fresh=true` on the sample button, means each run starts with no edits and
no sign-offs, whatever ran before.

Screenshots: `shot(page, name)` saves `frontend/screenshots/<project>/<NN>-<name>.png` (viewport size, not
full page: what the judge sees), after checking the offline text and that the page does not scroll sideways
(`document.documentElement.scrollWidth <= window.innerWidth`). Ten per project:

| File | After step | Screen |
| --- | --- | --- |
| `01-home.png` | 1 | home |
| `02-ingest-done.png` | 2 | project, "Done" |
| `03-trace.png` | 3 | trace of plans/flat-b.pdf |
| `04-engineer.png` | 4 | engineer, nothing asked |
| `05-count.png` | 5 | door answer with marks |
| `06-area-conflict.png` | 6 | area answer, methods disagree |
| `07-refusal.png` | 7 | refusal |
| `08-surveyor-queue.png` | 8 | surveyor, review queue |
| `09-signed.png` | 10 | surveyor, row signed |
| `10-verified.png` | 11 | engineer, verified answer |

The folder is gitignored. In CI it is uploaded as the artifact `golden-path-screenshots`; QA.md §3 "each one
opened and looked at" is a person's job on that artifact, not the test's.

### The CI job (after QA)

A new job `e2e` in `.github/workflows/ci.yml`, beside `python` and `node` (actions pinned to the same commit SHAs as
the jobs above; `upload-artifact` pinned the same way, its SHA looked up by the build worker):

```yaml
  e2e:
    name: e2e golden path (fakes)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
        with: {persist-credentials: false}
      - uses: astral-sh/setup-uv@<sha> # v10.3.3
        with: {version: "${{ env.UV_VERSION }}", cache-dependency-glob: backend/uv.lock}
      - uses: actions/setup-node@<sha> # v7.1.0
        with: {node-version: 24, cache: npm, cache-dependency-path: frontend/package-lock.json}
      - run: uv sync --locked
        working-directory: backend
      - run: npm ci
        working-directory: frontend
      - run: npx playwright install --with-deps chromium
        working-directory: frontend
      - run: npm run e2e
        working-directory: frontend
      - if: always()
        uses: actions/upload-artifact@<sha> # v4.x
        with:
          name: golden-path-screenshots
          path: |
            frontend/screenshots/
            frontend/playwright-report/
          retention-days: 7
```

Playwright sets `CI` itself from the runner; `forbidOnly: !!process.env.CI` in the config.

## API calls

The test drives the screens; these are the requests the path makes, in order. Each screen's own spec owns how it
reads them; the fixture shows the shape.

| Step | Call (API.md section) | Fields the test checks on screen | Fixture |
| --- | --- | --- | --- |
| 1 | `GET /api/info` ("GET /api/info") | `no_keys` → the offline text | `info.json` |
| 1 | `GET /api/projects` ("GET /api/projects") | list loads (earlier runs or empty) | `project_list.json` |
| 2 | `POST /api/projects/sample?fresh=true` ("POST /api/projects/sample") | `id` → the route `#/p/<id>` | `project_started.json` |
| 2 | `GET /api/projects/{id}`, polled every 500 ms ("GET /api/projects/{project_id}") | `state` "done", `files[].state` words, `drawings` | `project.json` |
| 3 | `GET /api/projects/{id}/files/{file_id}/trace` ("…/trace") | `file.state`, `file.reason`, `stages[].stage`, `stages[].did` | `trace.json` |
| 4 | `GET /api/drawings/{drawing_id}` ("GET /api/drawings/{drawing_id}") | `file`, `reader`, `suggestions[].question` | `drawing.json` |
| 4 | `GET /api/drawings/{drawing_id}/pages/1.png?width=` ("…/pages/{n}.png") | the page image loads (`naturalWidth > 0`) | — |
| 5-7, 11 | `POST /api/ask` ("POST /api/ask") | `answer`, `unit`, `quantity.status`, `quantity.conflict`, `quantity.signed`, `marks`, `refusal` | `answer.json`, `answer_refused.json` |
| 8 | `GET /api/drawings/{drawing_id}/takeoff` ("GET …/takeoff"), `GET /api/projects/{id}/review` ("GET …/review") | `review_queue`, row `status`, `conflict.values` | `takeoff.json`, `project_review.json` |
| 9 | `POST /api/drawings/{drawing_id}/review` `{"quantity": "area:room|name=1.01", "action": "settle", "value": 22.401}` ("POST …/review") | row `value`, `status` "edited", `settled` | `review_requests.json` (settle) |
| 10 | `POST /api/drawings/{drawing_id}/signoff` `{"quantity": "area:room|name=1.01", "by": "Ana"}` ("POST …/signoff") | row `status` "signed", `signed.by` | `signoff_request.json` |
| 12 | `GET /api/drawings/{drawing_id}/takeoff.csv` ("GET …/takeoff.csv") | file name, the row's cells | the CSV example in API.md |

Ids are never hard-coded: the project id comes from the route after step 2, the drawing id from the route after
step 4. Drawing ids are content hashes and stable, but the fixtures' ids are stand-ins.

## States

| State | What the test does | How it is reached |
| --- | --- | --- |
| Loading (ingest running, ask pending, page loading) | waits through it with Playwright's auto-waiting assertions; no sleeps | every run |
| No-keys | checks "Running offline: no API keys, no models" on all ten screenshots | the backend of `start-backend.sh` |
| Refusal | step 7 | "What colour is the roof?" |
| Conflict | step 6 and 8 | flat-b's kitchen |
| Signed / verified | steps 10, 11 | the sign-off |
| Error (`{detail, code}`) | the service-down test: `GET /api/projects` answered 500 `{"detail": "internal error", "code": "internal"}` by `page.route`; home shows "internal error" and "internal" and a Retry; after `page.unroute`, Retry loads the list | `page.route` in the test |
| Empty | not on the path: an empty project list is the ingest spec's component test (IN-13) | — |
| A console error or page error | fails the golden-path test (QA.md §2 "no errors in the browser console") | listener on `console` (type `error`) and `pageerror` |

## Layout

Nothing of its own: the screens' specs own their layout. The test checks, at both viewports and on every
screenshot, that the page has no horizontal scroll and the offline text is visible. The screenshots are the
evidence for QA.md §3 (390x844 and 1440x900).

## Acceptance criteria

The path

- GP-1 `npm run e2e` in `frontend/` builds the app, starts the no-keys backend and the preview server itself, runs
  `golden-path.spec.ts` in projects `desktop` (1440x900) and `phone` (390x844), and exits 0 on main. [e2e]
- GP-2 Step 1: at `/#/` the "Try the sample project" button and the text "Running offline: no API keys, no models"
  are visible. [e2e]
- GP-3 Step 2: after the click the URL is `#/p/<12 hex>`; the screen reaches "Done" and "11 of 11 files finished";
  the rows of `plans/flat-b.pdf`, `photos/site.jpg` and `docs/notes.txt` show "flagged", "set aside" and
  "text only" as words. [e2e]
- GP-4 Step 3: clicking the `plans/flat-b.pdf` row reaches `#/p/<id>/f/f<digits>`, which shows "flagged", the text
  "1 conflict(s) between the two methods", the stage `write`, and "5 quantities measured twice, 1 conflict(s)". [e2e]
- GP-5 Step 4: "Open the drawing" reaches `#/p/<id>/d/<16 hex>/engineer`, shows "plans/flat-b.pdf", a page image
  that loaded (`naturalWidth > 0`), the line "Credit: none recorded for this file" and the suggestion button
  "How many doors are there?". [e2e]
- GP-6 Step 5: the turn for "How many doors are there?" shows the value "2", "One method", and exactly two mark
  buttons named `Mark <n>: door, counted`. [e2e]
- GP-7 Step 6: the turn for "What is the net floor area of room 1.01?" shows "30.00 m²", "Methods disagree",
  "22.40 m² by polygon_x_scale", "30.00 m² by printed_label" and one mark named `Mark 1: Küche, counted`. [e2e]
- GP-8 Step 7: the turn for "What colour is the roof?" shows "I can't answer that from this drawing." and
  "unsupported-question", at least one question button, and no answer value. [e2e]
- GP-9 Step 8: the "Surveyor" link reaches `#/p/<id>/d/<same drawing id>/surveyor`, whose "To review" group lists
  "area of room (name 1.01)" and "area of room (name küche)", each with "Methods disagree". [e2e]
- GP-10 Step 9: with "area of room (name 1.01)" selected, "Keep A: 22.40 m² (polygon_x_scale)" makes its row read
  22.40 m² and "Changed in review", and the detail "Settled at 22.40 m²". [e2e]
- GP-11 Step 10: "Ana" in "Signing as" and "Sign off 22.40 m²" make the row read "Verified" and the detail
  "Signed off by Ana". [e2e]
- GP-12 Step 11: back on Engineer, asking "What is the net floor area of room 1.01?" shows "22.40 m²", "Verified" and
  text matching `Verified by Ana, \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC`. [e2e]
- GP-13 Step 12: "Export CSV" on Surveyor gives a download named `flat-b-takeoff.csv` whose line starting
  `plans/flat-b.pdf,area:room|name=1.01,` matches `,22\.401,m2,signed,30\.0,` and `,Ana,`. [e2e]
- GP-14 Every step from 1 to 12 passes in both projects; the `phone` project uses no other steps or selectors than
  `desktop`. [e2e]
- GP-28 Step 8a (06:00 scope): the "Surveyor" link reaches `#/p/<id>/d/<same drawing id>/surveyor`, whose side
  panel lists the conflicts "area of room (name 1.01)" and "area of room (name küche)", each with "plans/flat-b.pdf",
  "22.40 m² vs 30.00 m²" and "decided by rule". [e2e]
- GP-15 Running `npm run e2e` twice in a row passes both times (a new temp data dir, and `fresh=true` resets the
  sign-off of the first run). [e2e, by hand once before merge]

Evidence and checks on every screen

- GP-16 Ten screenshots per project are written to `frontend/screenshots/{desktop,phone}/01-home.png` …
  `10-verified.png`, at the project's viewport size. [e2e]
- GP-17 At each of those screenshots `document.documentElement.scrollWidth <= window.innerWidth` holds (no
  horizontal scroll; covers EN-45 and IN-47 on the path). [e2e]
- GP-18 At each of those screenshots "Running offline: no API keys, no models" is visible when `GET /api/info` says
  `no_keys: true`, and absent when it says false. [e2e]
- GP-19 The golden-path test fails if the page logs a `console` error or throws a `pageerror` during the run. [e2e]
- GP-20 Service down: with `GET /api/projects` answered 500 `{"detail": "internal error", "code": "internal"}` via
  `page.route`, home shows "internal error" and "internal" and a "Retry" button; after the route is removed, Retry
  shows the list. [e2e]

Harness

- GP-21 `start-backend.sh` builds the sample archive into a new temp dir and starts uvicorn on `127.0.0.1:8010` with
  the eleven overrides listed under "The e2e test"; with a `backend/.env` that sets `EXTRACTOR_RASTER=composite`,
  `GET http://127.0.0.1:8010/api/info` still reports `"raster": "hello"`. [by hand once, then e2e covers it]
- GP-22 `playwright.config.ts` has `workers: 1`, `retries: 0`, `reuseExistingServer: false` on both servers, and
  `127.0.0.1` in every URL. [review of the file]
- GP-23 With `E2E_API_URL=http://127.0.0.1:8000` the config starts no backend and passes it as `BACKEND_URL` to the
  preview, which proxies `/api` there. [by hand]
- GP-24 `npm test` runs vitest only and passes with no backend running. [CI `node` job]
- GP-25 The CI job `e2e` runs on every PR to main, installs Chromium only, runs `npm run e2e`, and uploads
  `golden-path-screenshots` (screenshots and the Playwright report) whether it passed or failed. [CI run on the PR]
- GP-26 `git status` after a run shows no new files: screenshots, `test-results/` and `playwright-report/` are
  gitignored, and the backend's data went to the temp dir. [by hand]

Selectors

- GP-27 The test finds elements only by role and accessible name, by visible text, or by the test ids in Open
  point 1; no CSS classes, no ids from fixtures. [review of the file]

## Out of scope

- The upload of a user's own file (drop or pick): on stage the sample button is the path; upload has component
  tests (ingest spec IN-3…IN-10). If an `ingest.spec.ts` e2e is wanted for it, the ingest build worker writes it.
- The phone photo, the raster scans and the IFC model on stage: with no keys they are flagged with "no reader for
  the raster route yet" or carry no page; a real-services variant of the path (a photo read by the raster reader)
  is for the by-hand run only.
- Visual regression (pixel diffs): screenshots are looked at by a person.
- The loading and empty states of each screen, and their error states other than GP-20: each screen spec reaches
  them in its component tests.
- Rejecting, restoring or adding a mark, reset, undoing a sign-off: surveyor spec.
- Answer confidence on the path: the no-keys backend sends none (`DECISIONS_CONFIDENCE=false`), so the path shows
  none; the screens code against `{signal, score, calibrated: false}` (EN-23).
- Firefox and WebKit: Chromium only, to keep CI fast.

## Open points

1. **Names the test uses, from the sibling drafts (read 2026-11-14 07:40).** A rename in a sibling spec must update
   this table; each name is also in the owner's own criteria, so a rename breaks a component test first.

   | Spec | What | Name used by the test | Source |
   | --- | --- | --- | --- |
   | shared | offline text | "Running offline: no API keys, no models" (full text at both widths) | SH-16, Layout |
   | shared | view links | links "Ingest", "Engineer", "Surveyor"; current one `aria-current="page"` | SH-13, SH-14 |
   | shared | error view | `detail`, "code: <code>", a "Retry" button, `role="alert"` | States "Screen error" |
   | ingest | sample button | button "Try the sample project" | IN-1, IN-9 |
   | ingest | project done | "Done", "11 of 11 files finished" | IN-16 |
   | ingest | file row | a link whose name contains the file's `path`; state words "flagged", "set aside", "text only" | IN-18, IN-19 |
   | ingest | trace | link "Open the drawing" | IN-37 |
   | engineer | suggestion | button named by its question | EN-6 |
   | engineer | ask | button "Ask"; the question input labelled "Question" | EN-10 (the label is a proposal) |
   | engineer | one turn | each thread turn an `<article>` named by its question (`aria-label`) | proposal |
   | engineer | value | `data-testid="answer-value"` on the big value inside a turn | proposal |
   | engineer | words | "One method", "Methods disagree", "22.40 m² by polygon_x_scale", "Verified by Ana, …", "I can't answer that from this drawing." | EN-31…EN-33, EN-39 |
   | viewer | marks | buttons named `Mark <n>: <label>, counted` | viewer badge `aria-label` |
   | surveyor | queue | group "To review", rows with `label` and status words | SV-3, status table |
   | surveyor | settle | button "Keep A: 22.40 m² (polygon_x_scale)" | SV-30 |
   | surveyor | sign-off | textbox "Signing as", a button whose name starts "Sign off" | SV-35, SV-36 |
   | surveyor | signed | "Verified", "Signed off by Ana, …" | SV-38 |
   | surveyor | export | link "Export CSV" with `download` | API calls table |

   Closed for engineer: engineer.md adopts the three proposals (input label "Question", turn `<article>` named by its
   question, `data-testid="answer-value"`; frontend-orch, round 1). Steps 6 and 11 ask the same question, so the
   test takes the last turn with that name.
2. **Overlap with the ingest and surveyor e2e criteria.** IN-46/IN-47 follow `plans/flat-a.pdf`; SV-48/SV-49 sign off
   `door` and check "Verified by Ana" on the door answer. The golden path walks the same screens on
   `plans/flat-b.pdf`'s kitchen. Recommend: GP-3…GP-5 and GP-17 count as IN-46 and IN-47 on the project and trace
   screens; GP-11…GP-13 count as SV-49 and the sign-off and CSV parts of SV-48. `ingest.spec.ts` keeps the
   `plans/flat-a.png` before/after trace and an upload; `surveyor.spec.ts` keeps reject/restore and undo sign-off.
   Both use `startSample` from `e2e/support.ts` and run in the same Playwright run (`workers: 1`).
3. **`frontend/e2e/` ownership:** closed (round 1). One e2e build worker owns all of `frontend/e2e/`, including
   `ingest.spec.ts` and `surveyor.spec.ts`, and builds every [e2e] criterion of the screen specs; those specs keep
   their criteria tagged [e2e].
4. **The engineer's view of a sign-off is per answer.** An answer card is a snapshot, so step 11 asks again rather
   than expecting the step 6 card to change. Recommend: keep (engineer.md's thread is in memory, answers are not
   re-fetched).
5. **Licence credit on the path is null.** The synthetic sample has `credit: null`, which shows "Credit: none
   recorded for this file" (round 1; shared `<Credit>`, placed by the viewer); GP-5 checks that line. QA.md §3 asks
   that mocked data is labelled: recommend the backend gives sample drawings a credit such as "Synthetic drawing
   made by code, no partner data" (GP-5 then checks that text); until then the offline strip is the only label.
6. **Proxy env:** closed (round 1). The scaffold's `vite.config.ts` reads `BACKEND_URL` (default
   `http://127.0.0.1:8000`); the e2e sets it to the test backend, and `E2E_API_URL` sets it by hand.
7. **Confidence shape is about to change** (board #14, pending the next backend PR): `confidence` becomes an object
   `{signal, score, calibrated: false}` (a raw model choice score, not a probability) and the "Probability this
   answer is right" line goes. The frontend codes against the new shape now (engineer.md EN-23: "Model score 0.87
   (choice, uncalibrated)"), never as a probability. The path runs with `DECISIONS_CONFIDENCE=false`, so it shows no
   confidence either way.
8. **Fixture ids are stand-ins.** The fixtures' project id is fixed; the live backend makes new project ids and
   content-hash drawing ids (flat-b is `6d153ea15dca9ab4` today). The test never asserts an id, only its pattern
   (GP-3, GP-5, GP-27).
9. **Not checked:** the `upload-artifact` SHA (the build worker pins it); the sign-off button's exact text for an
   area (surveyor.md shows "Sign off 2" for a count; the test matches the name's start "Sign off").
