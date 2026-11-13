# 0003: Detectors may train on CubiCasa5K boxes of dev-split images and on NC data, with weights kept local

- Status: accepted
- Date: 2026-11-13 21:31 (Europe/Helsinki)
- Decided by: Bogdan ("123 do as recoomeneded", answering three recommendations from his orchestrator)
- Board thread: #14 (question c6862694898, decision c6862888778), mirrored on #15

## Context

All 4,787 cubicasa images in the Stoa dataset are CubiCasa5K images (byte-identical to `F1_original.png`, 200/200
sampled), and the dataset's counts are CubiCasa5K annotation counts: one rule per template over the public
`model.svg` reproduces the dev answers exactly on 11 of 12 templates (board #15 c6862399217). Without element boxes,
models stay weak on symbols: the CubiCasa authors' 2019 weights scored 53.1% on 200 dev images against 54.5% for the
most common answer, and a count-only model reached 59.3% with windows and doors near 18% (board #14). CubiCasa5K is
CC BY-NC-SA 4.0, FloorPlanCAD CC BY-NC 4.0. 829 of the 959 eval-split cubicasa drawings are in CubiCasa5K's train
split, so its labels cover eval images too.

## Decision

1. Training on boxes exported from CubiCasa5K `model.svg` is allowed for dev-split images only. Eval-split
   images and their SVGs stay out of training, tuning and box export. The split is `data/stoa/split/` (`stoa_eval
   split`; sha256 in the manifest).
2. A prototype may also train on NC-licensed data such as FloorPlanCAD.
3. For both: weights stay on the training machine. They are never committed, published or shipped, and the data
   sources and licences go into the submission form. Training code may be committed; data and weights may not.
4. No Roboflow datasets for now: image provenance is unknown, and the "Test" floor-plan set looks like a CubiCasa5K
   repackage, which would leak eval images. Extra commercial-safe data comes first from synthetic plans rendered
   from ResPlan (CC BY 4.0, per Tudor's stoa-data report).
5. No method looks up the public CubiCasa5K SVG at answer time: that is not reading the drawing.

## Alternatives considered

- No training on CubiCasa5K labels: without boxes, windows and doors stay at about 18-40% (count-only model about
  18%; template and Hough door counting 3/40 on CubiCasa), so cubicasa, 67% of all questions, stays near the
  most-common-answer baseline.
- Train on all CubiCasa5K labels: leaks 829 eval drawings and makes the eval split meaningless.
- Roboflow sets: login plus unknown provenance; one set duplicates CubiCasa5K.

## Consequences

- Detector scores are measured with `stoa_eval score --against dev`; `--against eval --milestone` only at
  milestones. Eval numbers stay blind only if rule 1 holds, so every training script reads the split manifest and
  refuses eval image ids.
- The NC licences fit a hackathon prototype, not a product: anything Stoa or we would use commercially needs weights
  retrained on commercial-safe data (ResPlan synthetic, own drawings). Revisit before any use outside Junction.
- The submission form lists CubiCasa5K and FloorPlanCAD (if used) with their licences.
