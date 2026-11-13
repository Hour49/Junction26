# 0004: The pipeline writes one extraction_v1 JSON per drawing file, and eval/ scores it against gold

- Status: accepted for v1
- Date: 2026-11-13 22:31 (Europe/Helsinki)
- Decided by: Bogdan for the two parts ("MAke sure the golden is split into 2 parts then. THe extraction, with the
  json."); the shape by Bogdan's orchestrator; written by agent golden (worker)
- Board thread: to be posted by the orchestrator

## Context

Scoring only the answers cannot tell a misread drawing from a wrong answer. Bogdan, 2026-11-13 ~22:10: Part 1
scores the extraction the pipeline writes for each drawing against gold, before any question. Part 2 scores
answering, with the answerer reading the gold extraction so that reading errors are taken out. The pipeline, three
gold reviewers (CubiCasa, swiss, ifc_models) and the scorer in `eval/` all write or read this file, so it needs one
fixed shape.

## Decision

The contract is [eval/schemas/extraction_v1.schema.json](../../eval/schemas/extraction_v1.schema.json), generated
from `Extraction` in `eval/stoa_eval/extraction.py`. One JSON per drawing file (a swiss PDF and its PNG each get one).
It holds `file` as in `questions.jsonl`, `split`, `truth` (`elements` = full lists, `counts` = only the counts the
questions give), `pages`, `scale`, `plans`, `elements` (class from a fixed list, box as page fractions, optional
polygon, `attrs`), `rooms` (type, raw label, box, polygon, `area_m2`), `apartments`, `counts` and `notes`. Gold
files live in `data/stoa/extraction_gold/<source>/` (gitignored); the pipeline writes the same shape where it likes.

`scale` is always an object (Bogdan, 2026-11-13 22:31, brief scale-2): `status` is `scaled`, `no_scale` (no scale
evidence on the sheet), `not_to_scale` (the sheet says so) or, in predictions only, `estimated` (a best-effort value
with `uncertainty` and the method in `source`). `m_per_unit` is set for `scaled` and `estimated` only. `evidence` lists
every kind visible on the sheet (`scale_text`, `scale_bar`, `printed_areas`, `dimension_lines`,
`not_to_scale_note`). Gold without a scale may carry `reference_m_per_unit` so that estimates can be measured.

`eval/` checks files with `python -m stoa_eval validate-extraction` and scores them with
`python -m stoa_eval score-extraction` against golden v2 Part 1. The scoring rules (matching, counts, scale) are in
[eval/README.md](../../eval/README.md). The model refuses unknown keys, unknown classes and room types, boxes outside
[0, 1] or out of order, repeated ids, and references to pages, plans or apartments that are not listed.

## Alternatives considered

- Scoring answers only: a wrong count cannot be traced to the reading or to the answering step.
- One file per drawing group (all formats of a plan together): the PDF and PNG of a swiss plan have different frames,
  and the scale in metres per page unit differs between them.
- Pixel coordinates: they depend on the render resolution. Page fractions match answer_v1 evidence (0002).

## Consequences

- A new element class or room type is a model change and a schema regeneration; tell the orchestrator first.
- The model fills gaps in the format brief: `storey` is a number or a name; `scaled` needs at least one evidence
  kind and `not_to_scale` must list `not_to_scale_note`; `attrs.multiplicity` (int >= 1) marks an element drawn several times at the same place;
  `polygon` needs at least 3 points; `attrs` values are JSON scalars; `file` must start with `data/<source>/`.
- A breaking change ships as `extraction_v2.schema.json` with a record that supersedes this one.
  `eval/tests/test_models.py` fails when a committed schema no longer matches the models.

## Amendment, 2026-11-13 23:30: tables and conflicts

- Decided by: Bogdan, 2026-11-13 23:03 ("1yes 2 yes 3 yes 4 yes": opening_design schedules by hand, conflict cases)
  and 23:05 (conflicts as a small slice outside the headline); the shapes pinned by his orchestrator (formats-v1-1
  brief), `key_column` and positional columns from review-8; written by agent golden (worker).

Two optional top-level lists, additive, so every extraction_v1 file stays valid:

- `tables`: schedules a question can be about (door, window, hardware, finish, room schedules), each with `id`,
  `page`, `box`, `title`, `columns` (header text as printed), `key_column` (0-based, default 0: the column that
  identifies a row) and `rows` (`cells`, one per column, `null` when empty; optional `box`). A new `truth` value,
  `tables`, marks a schedule sheet: only its tables are scored, its `elements` and `rooms` are empty, and it is not
  a scale case. A sheet with a plan and schedules uses `truth: "elements"` plus `tables`.
- `conflicts`: quantities two independent methods measured on the file (ingestion stage 8, docs/PIPELINE.md),
  each with `quantity`, `subject` (`room` or `apartment` with an id in the file, `class` with an element class,
  `sheet`), `status` (`conflict` or `agree`), relative `tolerance`, at least two `values` from different methods,
  an optional `resolution` (`rule`, `value`) and `note`. Gold lists only checked facts: a `conflict` was looked at
  on the drawing, an `agree` entry is a negative for measuring false alarms.

The conflict gold lives in `data/stoa/extraction_gold/_conflicts/conflicts.jsonl` (one line per file);
`select-plans` puts those files in golden v2 and merges their conflicts into the copied gold. A file that joins v2
only for the conflict slice is scored only there (no scale case, no Part 1 headline, no questions in Part 2;
orchestrator, 2026-11-13 23:29). Both lists are scored in their own sections and never change the headline numbers.
Rules: [eval/README.md](../../eval/README.md), spec: [docs/GOLDEN.md](../GOLDEN.md).

## Amendment, 2026-11-13 23:55: every image has a scale, every room an area

- Decided by: Bogdan, 2026-11-13 23:33 ("We should have ON ALL IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING IT
  IN DIFFERENT WAYS IF NOT GOOD SCALE ETC."); gold rules in the orchestrator's scale-all brief; written by agent
  golden (worker).

Gold may now use `scale.status: "estimated"` (no usable printed evidence; `m_per_unit`, a relative `uncertainty`
and a `source` naming the methods are required), and `not_to_scale` may carry an approximate `m_per_unit` with
`uncertainty` and `source`. `reference_m_per_unit` is allowed on every status except `scaled`. Rooms get optional
`area_status` (`exact` | `estimated`), `area_source` (`printed` | `geometry_x_scale` | `geometry_x_estimate`) and
`area_uncertainty` (set exactly on estimated areas); a printed area is exact and an exact area is printed; an unset
`area_status` counts as exact, as in the swiss and IFC gold. Old files stay valid. Golden v2 gold must have a scale
value on every image, no "scale not reviewed" note and an area on every room with a polygon (schedule sheets
exempt): `validate-extraction --strict-v2` checks it and `select-plans` refuses such files unless `--allow-unscaled`.
Exact areas are scored within 2% (the headline); estimated areas and estimated scales report the median relative
error and the shares within 10% and 20%; a `scaled` prediction on `estimated` gold is a wrong status.

## Amendment, 2026-11-13 23:53: `read`

- Decided by: the orchestrator (golden-7f brief); written by agent golden (worker).

An extraction may list in the optional `read` the element classes, plus `"room"`, that it looked for (known names,
no duplicates). Left out, as in every gold file, it means everything the file's `truth` covers. A class not listed
was not read: its count is unknown, not 0, so an answerer must not turn it into "0 windows". Scoring doesn't change
(not reading a class counts its misses); the Part 1 table marks `not read` on a class that every prediction file of
the source leaves out.
