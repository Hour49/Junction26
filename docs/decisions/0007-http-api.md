# 0007: The frontend talks to the backend through the HTTP API v1 in docs/API.md, checked by fixtures

- Status: accepted
- Date: 2026-11-14 (Europe/Helsinki)
- Decided by: agent api (worker), on the review by agent api-review (`.agents/api-review.md`, blockers B1-B5 and
  S1-S11 with the reviewer's picks, and its cuts C1-C5), accepted by Bogdan's orchestrator; PR #60
- Board thread: to be posted by the orchestrator

## Context

The frontend (Tudor, React + Vite + TS) and the backend (FastAPI, decision 0001) have different owners, and the
demo runs on real results (stories #27, #31, #32, #33). The first draft of the contract and the code being built
already disagreed in ten places (api-review B2), so the contract needs one source of truth that a test checks.

## Decision

- The contract is [docs/API.md](../API.md): `/api/...` endpoints for projects and ingest, drawings and pages,
  asking, and the surveyor's takeoff, review and sign-off.
- Every route returns a pydantic response model (`backend/app/api/`), so `/openapi.json` is complete and the
  frontend generates its TypeScript types from it.
- Every JSON example in API.md is a file in `backend/tests/fixtures/api_v1/`, made from real responses on the
  synthetic sample archive by `backend/tests/api/make_fixtures.py`. `backend/tests/api/test_api_fixtures.py` fails
  when a fixture no longer fits its model (unknown fields are refused) or API.md no longer quotes it as it is. The
  frontend uses the same files as mock data.
- Shapes chosen in review: the upload is the raw request body with `?name=`; no CORS (the Vite proxy); one error
  shape `{detail, code}`; an ask answer carries the takeoff row in the takeoff's own shape, plus the answer_v1.1
  line for the scorer; a refusal is `{code, text, can_answer}` with suggestions the parser is checked to map back;
  edits and sign-offs are kept per drawing id, with `reset` and a fresh sample run so a demo starts clean.
- The page frame is the normalised sheet (EXIF applied, then any turn, deskew or rectification): page sizes,
  boxes and served pages agree, and `preview.png` shows the upload.
- Fields that depend on core (agreeing second readings, items a rule left out) are in the shape already and
  marked **waits on core** in API.md until they land.

## Alternatives considered

- Multipart upload: needs `python-multipart`, a new runtime dependency, and a frontend `fetch` with the file as
  body is simpler.
- Examples written by hand in API.md: they drifted from the code within hours (B2).
- A question on a whole project, free page widths, adding a mark with a value to an area: cut (C1, C3, C4); no
  screen needs them.

## Consequences

- A change to a response shape is: change the model, run `make_fixtures.py --doc`, and the PR shows the change in
  both the fixtures and API.md. The frontend regenerates its types.
- A new version is `api_v2` fixtures and a record that supersedes this one.
- The "waits on" items need their owners' changes; the API uses each as soon as it lands.
