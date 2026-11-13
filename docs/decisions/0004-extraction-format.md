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
