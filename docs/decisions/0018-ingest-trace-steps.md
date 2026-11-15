# 0018: Steps inside an ingest stage

Date: 2026-11-15. Status: accepted (ingest UI track, orchestrator for Bogdan). Additive to API v1.

## Context

A file's trace had one line per stage (11 stages). The `extract` line hid everything that runs on a sheet: on an
image, the symbol detector, the Gemini Decisions swap, the count arbiter, the room reader, Carbon on large or sparse
sheets, the printed scale and the double-check readers, several of them at the same time. Bogdan (2026-11-15
03:20): "I want the ingestion pipeline to look much better, and then to be more representative of the operations
we are doing right now in the actual pipeline."

## Decision

- `StageTrace.steps: tuple[StepTrace, ...] = ()`: what ran inside a stage, in start order.
- `StepTrace`: `id` (stable machine id, listed in docs/API.md), `label` (plain words for the screen), `did` (what it
  found, or the error), `at_ms` (start, ms after its stage began), `ms`, `cost_usd`, `state`
  (`done` / `failed` / `skipped`), `found` (counts by class, `{}` when it counts nothing).
- `FileStatus.step: str | None` and `FileStatus.step_id: str | None`: the label and id of the step running
  now, left out of the JSON when None.
- `ProjectStatus.phase: "files" | "index" | None` and `ProjectStatus.index_steps`: the project's last phase (judge,
  describe, evidence index) as steps.

Readers run in parallel, so steps overlap: `at_ms` and `ms` give each one's span inside its stage, and a screen can
draw them as a timeline. The stage's own `ms` and `cost_usd` stay the totals they were.

## Consequences

- Every field is optional with an empty default, so old clients and stored traces keep working (a stored
  `Outcome` reads with `steps: []`).
- The adapters report their steps through `Extracted.steps`; the core reads no adapter.
- The answer path does not read steps: answers do not change.
