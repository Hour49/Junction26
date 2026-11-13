# Shortlist: what to build first to read a raster plan into extraction_v1

Written 2026-11-14 by Bogdan's research orchestrator from both halves of the campaign: 36 reports, the two triage
files ([triage-Bogzx.md](triage-Bogzx.md), `triage-Cucuteanu-Tudor-912.md` in PR #56) and Tudor's conclusions
(`conclusions-Cucuteanu-Tudor-912.md`, same PR). The full list of 511 ideas and experiments is in
[IDEAS.md](IDEAS.md).

Nothing in the campaign was trained or run on our images, so every expected score below is an estimate. Numbers
marked "checked" were re-opened in the source by the orchestrator; the others were read by a worker and re-checked
by the worker that merged its scope.

## 1. `elements`: windows, doors, fixtures (about 19 of the 30 open points)

- **First.** Two box detectors on the dev boxes (about 104k boxes, 3,828 images), about 1024 px, the eight
  rotations and mirrors as augmentation, from COCO weights: RF-DETR S or M and D-FINE S or M. Both Apache-2.0, no
  CubiCasa5K in their training data. Source: Tudor's conclusions, section 2.
- **What decides the count more than the model**, in this order: input size (upscale small plans with Lanczos, no
  learned super-resolution); the same geometry in training and inference; a score threshold per class chosen for
  the exact-count rate on a held-out dev slice; duplicate removal by intersection over the smaller box that still
  keeps one box per window cell; doors without a leaf as their own class.
- **Fallback.** RT-DETRv2 (Apache-2.0). If no detector is ready, the count-only network (59.3% overall, measured
  earlier on dev).
- **Experiment that settles it.** Both detectors on one held-out dev slice: exact count per class, upright and
  rotated images separately, at 1024 px and one larger size; then the threshold and duplicate rule on the same
  predictions.
- **Do not spend time on:**
  - a sequence or coordinate decoder for openings: the same network gets opening F1 0.246 from its coordinate
    sequence and 0.644 to 0.799 from its dense heatmap (arXiv 2608.25608; the abstract's "2.6x" checked);
  - prompted vision-language models as counters: best exact match on 120 plans is 0.39 for doors and 0.34 for
    windows (AECV-Bench, arXiv 2601.04819);
  - vectorise-then-rules on scans, synthetic-only training, any checkpoint trained on CubiCasa5K (829 of our 959
    sealed drawings are in its train split), Ultralytics YOLO (AGPL), SAM 3 and DEIMv2 (licence).
- **Reference points.** The nearest published number in our unit is one unreviewed repository: a small U-Net plus
  connected components gets doors exact on 33.7 to 35.3% and windows on 29.5 to 33.2% of 190 clean test plans. Box
  AP50 for doors on CubiCasa5K differs by 12 points between two RT-DETR repositories (89.8 and 77.9), so a
  published AP says little before it is measured on our boxes.

## 2. A second count and the confidence signal

- **Second counter.** Template matching with a symbol cut from the same plan (the detector's most confident boxes):
  F1 0.87 on 34 drawings, against 0.38 with a library symbol and 0.10 to 0.23 for trained exemplar counters (arXiv
  2610.09313). In the same paper, a vision-language model accepting or rejecting each candidate scored 0.83 to
  0.91, not significantly different from template matching alone.
- **Confidence.** No paper ranks a confidence signal against exact per-image count correctness, so dev decides.
  Candidates in order of cost: the plain score of the two or three most confident detections (averaging all scores
  misranks); the probability of the modal count from calibrated box scores (Poisson-binomial); agreement of two
  independent counters. Compare them by failure AUROC and by the error among accepted answers at each coverage.
- **The guarantee.** Pick the threshold on one dev split and certify it on another, with the plan as the unit, and
  state an exact binomial bound: "of the answers marked sure, at least X% are exact (N plans, 95% bound); the gate
  opens on Y% of plans". Report how often the gate opens every time.

## 3. `rooms`: type (about 9 open points) and outline

- **Type, first.** Text route, CPU only: PP-OCRv6, every crop read at four rotations with the reading that hits
  the closed label table kept, Lanczos upscale before reading. Then a recogniser fine-tuned on rendered plus real
  crops. Cross-check: room types as extra detector classes. Source: Tudor's conclusions, section 3.
- **Outline, first.** Our own wall and room-region network on the dev polygons, door gaps closed, connected regions
  as rooms; the text box of a label as a second seed where two rooms merge through an opening; a label belongs to
  the room whose polygon contains it.
- **Not Raster2Seq's checkpoint.** Weights are CC BY-NC 4.0 and trained on CubiCasa5K (checked in the repository).
  Its room F1 of 88.7 becomes 0.763 in an independent rerun under a stricter protocol (arXiv 2609.25615, numbers
  found in the paper text).
- **What to expect for areas from outlines.** The one measurement (same unreviewed repository): median room-area
  error 4.3%, 45% of plans above 5%, with the scale known. A polygon area is a fallback, never the first source.

## 4. `plans` per sheet (about 1.5 open points)

Export a box per plan from the dev labels, then count plans by grouping detected elements by distance. Second: a
one-class plan detector trained on the real multi-plan sheets plus pasted composites. The baseline to beat is the
constant answer 1 (79.5% on dev). Source: Tudor's conclusions, section 4.

## 5. `scale` and areas (no score; they carry the product and the proof)

- A printed room area wins over an area from the outline.
- Call a scale `scaled` only when two independent printed marks agree within 2%; otherwise `estimated`, with the
  source in words. Evidence: reading dimension lines gets 72% of plans within 2%, 83% within 5% and 86% within 10%
  (Lv et al., CVPR 2021 supplement; Chinese plans, no code). Size priors alone on CubiCasa5K (door width, wall
  thickness, a student project) give a median error of 6.5% and 18% of plans within 2%; where two priors agree
  within 5%, still only 17% are within 2%. Agreement of priors is not proof.
- Fit the per-mark scales robustly (largest consistent cluster or RANSAC) and return accepted, insufficient or
  conflict. In chart reading the robust fit succeeds on 89.2% of charts against 70.7% for a two-point fit (arXiv
  1704.06687, checked).
- Fix the wall convention of the gold areas (inner surface or centre line) before measuring any area error.

## 6. Where a vision-language model fits

Not as the counter. As the reader of last resort for text crops where two readers disagree, and in the demo.
If tiles are sent to one: about 1.5 visual tokens per symbol, tiles overlapping by one object, no zooming out
(arXiv 2610.09313). A small model fine-tuned to write points, with code counting them, is a Saturday experiment:
on photos it lifts accuracy from 70.0 to 81.9 (arXiv 2603.21746), untested on line art. No drawing goes to a model
API before Stoa agrees.

## 7. For the pitch

- What no construction product publishes, in anything the market workers opened: exact-match accuracy per class on
  a sealed split with the counting rules printed; a calibrated confidence with a stated coverage; the place on the
  sheet behind every count; a price per sheet.
- The public yardstick is AECV-Bench: doors 0.39, windows 0.34 exact for the best model in the paper.
- `docs/REQUIREMENTS.md` section 2 says vision-language models reach "roughly 40-55%" exact on doors and windows.
  The paper's best is 0.39 and 0.34; 0.43 and 0.39 when recomputed from the benchmark's result files; 0.55 and 0.44
  only in an unmerged pull request. The sentence should say "about 35 to 45%, up to 55% claimed".
- Vendor accuracy figures in the market reports were read by workers from vendor pages and trade press and were
  not re-opened by the orchestrator. Open the page before a slide quotes one.

## Decisions for a person

1. Whether a non-commercial model may be used in the prototype (SAM 3 has the only published exact-count results on
   small counts, on photos).
2. The upstream data terms of pretrained detection weights (the detect scope flags Objects365) before any
   fine-tuned checkpoint is shipped. Under record 0003 our weights stay local, so this does not block the first run.
3. Still open with Stoa: how they score, and whether drawings may go to a model API.
4. Which experiments the 200 EUR of Verda GPU credits pay for.

## How much to trust this

Bogdan's 18 reports were audited against the workers' session logs and the paper texts: of 1,255 arXiv citations,
4 were never fetched by the worker that cites them, and the flagged numbers read by hand were rounding or
multi-source lines. Tudor's 18 reports had no send-back round and were not audited this way. The method and the
table per report are in [REVIEW.md](REVIEW.md).
