# Conclusions: from a CubiCasa PNG to extraction_v1, field by field

Research orchestrator of Tudor's half (lit-orch), 2026-11-14. This file joins the earlier research on this machine
(the CubiCasa rule and baseline work, the hard-image pipeline, the hard-image literature pass, the data search) with
the 18 reports of this campaign (scopes L2, L3, L5, L8, L9, L11). The ranked candidates with their evidence marks
are in [`triage-Cucuteanu-Tudor-912.md`](triage-Cucuteanu-Tudor-912.md); this file says what follows from them for each field of the JSON.

Three kinds of statement appear below. "Measured by us" is an earlier measurement on dev-split images. "Published"
is a number from a paper, on other data unless stated. "Estimate" is arithmetic or judgement. Nothing in the
campaign was trained or run on our images, so every expected score is an estimate.

## 1. What the whole body of research says, in short

1. The task is to reproduce the annotation counts of a public dataset from its images. With a correct JSON the
   counting rules already give the answers (measured by us: 11 of 12 templates at 100% on dev, saunas 99.7%). All
   remaining error is reading error.
2. Exact counts of many small symbols need box supervision. Measured by us: a network trained on the counts alone
   stays at 18% on windows and doors; the public 2019 network reaches 32 to 37%; classical door templates and arc
   detection reach 2 to 3 exact out of 40. Published: frontier vision-language models reach 0.03 to 0.39 exact on
   door and window counts.
3. The literature has no number for our metric. No paper in six scopes reports per-image exact counts of doors,
   windows or fixtures from a box detector on raster plans. The dev split is the only place where the choice can be
   settled, and the first detector run is worth more than further reading.
4. Across every adjacent field the workers read (music scores, P&ID and railway drawings, maps, chemistry, PCB,
   microscopy), the same pipeline shape won: a learned detector on the raw page, trained on real boxes with
   augmentation that matches the target, then rules and a second look on top. Routes that first remove or
   vectorise the line work lose on scans.
5. Licences and leakage remove most shortcuts. Every public checkpoint trained on these plans is leaky, the strong
   YOLO lines are AGPL, and several of the best 2025-2026 models (DEIMv2, SAM 3, DINOv3, the larger RF-DETR sizes)
   carry non-commercial or custom licences. What remains is enough: RF-DETR N to L, D-FINE, RT-DETRv2, PP-OCRv6,
   OpenCV.

## 2. `elements`: window, door, toilet, sink, shower, bathtub, sauna stove

**First method.** One box detector trained on the dev boxes (about 104k instances on 3,828 images), with the eight
rotations and mirrors as augmentation, at about 1024 px. Train two tonight on the same COCO file: RF-DETR S or M
and D-FINE S or M. Both are Apache-2.0 and start from COCO weights, so there is no leakage. Published small-object
AP on 100 small fine-tuning sets is within two points between them. RF-DETR is easier to run (rotation
augmentation is a config entry, memory guidance for 12 GB exists); D-FINE reads a finer feature map (stride 8
against 16), which matters for symbols of 5 to 10 px.

**What decides the count more than the model.**

- Input size. A symbol smaller than one feature cell is not seen. Upscale small plans with Lanczos until the
  short side reaches the training size, and keep one size range per symbol. Published: resolution alone is worth
  several AP points on tiny objects, and much of what tiling buys is resolution. Never use learned
  super-resolution here.
- Same geometry in training and inference. Published: a detector trained on crops and run on whole pages, or the
  reverse, loses a third of its AP or collapses. Full sheet in and out for most plans; tiles only for large sheets,
  then in training too, with a containment merge.
- The count threshold. Choose the score threshold per class on a held-out dev slice for the exact-count rate, not
  for AP. Nobody has published this for detectors; it has to be measured.
- Duplicates. Use intersection over the smaller box, which is worth 9 points of exact match in one published
  ablation on photos. Watch window strips: a strip of three cells is three windows, so the rule must not merge
  neighbours.
- Class details from our rule work: detect doors without a leaf as their own class and do not count them; the
  shower class is the tray symbol, not the screen; the sauna count uses the sauna room label when present and the
  stove otherwise; the bathtub has 312 boxes, so it is the class where pasting real crops into training images is
  worth an ablation.

**Fallback.** RT-DETRv2 through the transformers library (Apache-2.0) if both first choices fail to train; the
count-only network (measured 59.3% overall) answers fixtures and rooms if no detector is ready.

**Experiment that settles it.** Both detectors on one held-out dev slice, exact-count rate per class, upright and
rotated images separately, at 1024 px and one higher size; then the threshold and duplicate-rule comparison on the
same predictions.

**Expected.** Estimate: with about nine objects per class, a per-object recall of 0.95 gives about 63% of images
exact and 0.97 gives 76%, before false positives. A first run should land between the 2019 network (32 to 37%) and
about 65% on windows and doors, and higher on toilets and sinks, which are fewer per plan. That is roughly 5 to 8
of the 11 open points on windows and doors and 4 to 6 of the 8 on fixtures.

**Cost.** Two GPU runs of 2 to 3 hours (estimate; no published throughput at this size), about 6 agent hours.

**Sources.** arXiv 2511.09554 (RF-DETR and the RF100-VL comparison), 2410.13842 (D-FINE), Sensors 26(20) 6413
(tiles and merge on drawings), DAS 2024 (crop against full-page training in music scores), 2511.16719 (duplicate
rule); reports `lit-detect-a/b/c`, `lit-count-b/c`, `lit-data-b/c`.

## 3. `rooms`: type and raw label

Room type follows the printed Finnish or Swedish label, so this is text reading plus a label table. Measured by us
with the mobile PP-OCR models on 40 images: 23 to 81% exact per room type, with WC rooms and balconies readable and
the one and two letter codes (K, MH, S) at 5 to 10 px missed; glyphs under about 6 px are lost.

**First method.** Keep the pipeline shape (detect text, cut the crop, read it, map it to a closed vocabulary with
exact match for short codes) and change three things. Use the current recogniser generation (PP-OCRv6, Apache-2.0;
published 83.2 against 73.7 for the model we measured, on its authors' benchmark). Read every crop at four
rotations and keep the reading that hits the vocabulary: the engine we use only turns a crop upright when it is
clearly taller than wide, which a two-letter label never is, and one sheet in three is rotated. Upscale with
Lanczos before reading. All CPU, no training.

**Second step.** Fine-tune a small recogniser on rendered crops of our own codes plus real crops pseudo-labelled by
the vocabulary. Published: synthetic plus 1% real crops matches all-real training on scene text; adapting the
reader on map labels moves exact match from 69.9 to 84.3.

**Fallback and cross-check.** Add the room types as detector classes, since the dev export has room boxes with
labels. No paper tests this; it costs one more run and gives an independent vote for `conflicts`. A
vision-language reader on crops is the reader of last resort for the crops where the two disagree: reading crops
works (61.7 end to end zero-shot on map labels), reading whole tiles does not (12.8).

**Experiment that settles it.** Text route against detector classes on the same dev slice, per room type, upright
and rotated separately.

**Expected.** Estimate: 3 to 6 of the 9 open points. The limit is glyph size: labels under about 6 px stay
unreadable, and those plans should be flagged, not guessed.

**Cost.** 2 to 3 agent hours for the first step, about 4 more and an hour of GPU for the fine-tune.

**Sources.** arXiv 2606.13108, 2207.06966, 2602.06450, 2611.03339, 2602.04030; the abbreviation list in
`lit-ocr-c` section 5; reports `lit-ocr-a/b/c`; earlier report on the hard-image pipeline.

## 4. `plans`: how many plans the sheet shows

Measured by us on dev: one plan on 3,044 sheets, two on 672, three on 109, four on 3; answering 1 is right 79.5% of
the time. Nobody has published plan counting on floor-plan sheets.

**First method.** Export a per-plan box from the dev labels (the union of each plan's elements; not exported yet),
then count plans by grouping the detected elements by distance. Free once the detector exists.

**Second method.** A one-class "plan" detector trained on the 784 real multi-plan sheets plus composites pasted
from single-plan sheets. Published, on compound figures in scientific papers: 98.58 mAP on synthetic composites and
36.88 on real ones, so composites alone will not do. Do not start from a document-layout checkpoint: published,
document pretraining lowered accuracy on drawing sheets.

**Experiment.** Constant 1 against element grouping against the plan detector, exact plan count on real multi-plan
sheets held out from training.

**Expected.** Estimate: about 1 of the 1.5 open points. **Cost.** 1 agent hour for the export, 3 hours and a short
GPU run for the detector.

**Sources.** arXiv 2506.02738, 2607.18997; reports `lit-sheet-a/b/c`.

## 5. `scale` and room areas

Scale and areas move no score and belong to the other research orchestrator's scope (L6), so this campaign did not
search them. What our research holds: printed areas are reliable and areas measured from pixels are not (measured
by us: 4 of 16 by region fill, all 4 backed by printed text; doorways leak); a printed "1:N" gives the scale when
the paper size is known; the dev export carries an approximate scale. Two findings from this campaign touch scale
without filling the field: several fields normalise every page to a fixed size of a structural unit before
detection (the staff spacing in music, the wall thickness for us), and rule stages with fixed pixel thresholds
lose badly against scale-adaptive ones. So a rough per-plan scale estimate is worth having as a preprocessing aid
even though the field itself scores nothing. The policy from the earlier work stands: answer an area only when a
printed value backs it, otherwise say it is an estimate.

## 6. Orientation, confidence and the second measurement

- **Orientation.** No published method works for drawings with little text. The detector does not need one when it
  is trained with all eight rotations and mirrors. Text is handled per crop by the four-rotation vote. A page-level
  classifier trained on text pages may add one vote; it has never been tested on line drawings.
- **Second measurement for stage 8.** The cheapest independent signal is the disagreement between the two
  detectors. The next is template matching with exemplars cut from the same plan (the detector's most confident
  boxes): published F1 0.87 on architectural drawings when the exemplar comes from the same drawing, 0.38 from a
  library, and 0.10 to 0.23 for trained exemplar counters. On the same paper's floor-plan blocks (339 items) it
  gets only 0.58, so expect a weaker voter on our plans. Line detectors are fast and useless as counters
  (worker probe on dev images: about 1,000 segments per plan, most of them shorter than a window).
- **Confidence.** A count distribution from the box scores (Poisson-binomial) gives a mode and its probability in
  about 30 lines; published only for medical counts. A quality gate should be trained on our own dev errors, since
  generic image-quality scores did not predict reading errors in the one study that tested them.
- **What a person checks.** Every field that audits counts to the single object ends with marks a person can
  correct. That supports showing the boxes and the doubtful ones, which the answer format already allows.

## 7. Training data

Use the dev boxes; that is where the score comes from (record 0003 allows it, weights stay local). Add pasted real
crops for the rare classes as an ablation. Generated plans are the only commercial-safe source of fixture boxes
(an MIT generator; a CC BY 4.0 set of one million small plans), and the one study that mixed synthetic plans with
thousands of real ones found no significant gain, so they matter for a checkpoint that could be shipped, not for
Saturday's number. If rendered plans are ever used, the published recipe is to lay real blank scans under them, vary
line weight and blur, include rotated and multi-plan sheets, pretrain on them and then fine-tune on real boxes;
never train on them alone.

## 8. Order of work

Tonight: export the COCO file with the eight classes and the per-plan box; start RF-DETR on one card and D-FINE on
the other; swap the recogniser and add the four-rotation vote on CPU. Saturday morning: thresholds and duplicate
rule for exact count; the room-type comparison; the plan count comparison. Saturday afternoon: the second count
and the confidence signals; the fine-tuned recogniser if room types are still short.

Estimate of the total: the mode baseline is about 55% and the count-only network 59.3%. Winning 5 to 8 points on
windows and doors, 4 to 6 on fixtures, 3 to 6 on room types and 1 on plans would put the CubiCasa score between
about 68% and 76%. The spread is the honest part: it depends on a recall that nobody has measured.

## 9. What would change these conclusions

- The first dev numbers. If both detectors stay under 50% exact on windows and doors at 1024 px, the next step is
  input size and tiling, not another model.
- A licence decision that allows a non-commercial or custom-licence model for the prototype (SAM 3 has the only
  published exact-count results on small counts, on photos).
- Text boxes in the label export. If the export can give label text boxes, a text detector fine-tuned on them is
  the strongest published option for floor-plan text (AP 90 on tiles in a 2022 study, read by a worker only).
