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

- `ProjectStatus.ran: dict[Route, tuple[RanStep, ...]]` (added 2026-11-15 04:45, left out of the JSON while
  empty): per route, the step ids that ran on this upload's finished files, each `RanStep {id, label, done,
  skipped, failed}` (file counts). The run adds a file's steps when the file finishes (no recomputation over the
  traces per request), so a running project shows it live and a done one keeps it. The Simple view's route lanes
  tick the readers that ran: `ProjectView.readers` is only what is configured (QA round 3: "detector" shown when
  no detector ran).
- Step ids are stable, never order-dependent: one per reader. The Carbon check is `carbon_check` and the Carbon
  reader `carbon` (before: `carbon` and `carbon-2` when both ran); a comparison with no id of its own is
  `second_count:<quantity>`. A numbered suffix (`detector-2`) is left only for the same id met twice in a stage.
- The door-size scale estimate (`RASTER_SCALE=priors`) is the `prior_scale` step (added 2026-11-15 05:50), after
  the inner reader's steps in extract: `did` says the scale it estimated or why none (no door detected: `done`;
  a scale was read, no page, doors not read: `skipped`), so the "scale from door sizes" item ticks by id. The
  step is reporting only: the reading (scale, rooms, notes, printed checks) is the same with or without it.
- A raster reading that waited for the one local slot (`INGEST_LOCAL_IN_FLIGHT`, app/adapters/one_at_a_time.py)
  reports the wait as the `local_slot` step (added 2026-11-15 06:15), before the readers' steps, from when it
  asked for the slot (`at_ms`) for as long as it waited (`ms`), so the gap before them is explained, not shown as
  "the first step began at 2.9 s". Under 10 ms is the lock's own cost: no step. It counts in `ran` like any step
  (no reader chip stands for it, so no chip changes). Reporting only: the lock, its count and the reading are the
  same with or without it.

Readers run in parallel, so steps overlap: `at_ms` and `ms` give each one's span inside its stage, and a screen can
draw them as a timeline. The stage's own `ms` and `cost_usd` stay the totals they were.

## Consequences

- Every field is optional with an empty default, so old clients and stored traces keep working (a stored
  `Outcome` reads with `steps: []`).
- The adapters report their steps through `Extracted.steps`; the core reads no adapter.
- The answer path does not read steps: answers do not change.
