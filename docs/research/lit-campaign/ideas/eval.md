# Evaluation

69 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i432"></a>
### 432. AECV-Bench as the public exact-count yardstick

- What: Score our pipeline's door, window, bedroom and toilet counts on the 120 public plans under the benchmark's own rules, and print the rule difference (double leaf counts 2, adjacent windows are one group) next to any number.
- Evidence (floor-plans): Paper Table 1 (120 plans, zero training): Gemini 3 Pro door 0.39, window 0.34; recomputed from the repo files Gemini 3.5 Flash door 0.433, window 0.392; open unmerged PR: GPT-6.1 Sol 0.55 / 0.44.
- Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819), [github.com](https://github.com/AECFoundry/AECV-Bench)
- Licence: no licence on code or data; no weights. CubiCasa5K leakage: yes.
- Cost: about 3 h to re-score if the images may be opened (estimate), no GPU
- Experiment: Run our extraction on the 120 images (local only, never copied into the repo) and report per-field exact match under AECV rules and under ours; a door number above 0.55 is above every zero-shot result found.
- What breaks on our images: Rules differ from Stoa's and from the dataset SVG labels; a third of the plans are under 1,100 px wide; 75 of 120 look like CubiCasa material.
- Moves: trust. Why this group: cheapest honest comparison and the number a judge may hold
- Also (count, floor-plans): AECV-Bench as the floor to beat. Quote prompted-VLM exact match on doors and windows as the baseline. Evidence: Gemini 3 Pro door 0.39, window 0.34; GPT-5.2 0.28/0.27; Claude Opus 4.5 0.16/0.16; best open 0.09/0.03 (arXiv 2601.04819, Table 1, 120 plans). Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819). Experiment: Quote the published prompted-VLM door and window exact rates beside our dev exact rates; do not compare as like for like (different plan sample).
- Also (floorplan, floor-plans): Prompted-VLM counting baseline (AECV-Bench style). Ask one frontier VLM for door and window counts on a few dev plans with our counting rules to get the VLM comparison. Evidence: Paper: Gemini 3 Pro door 0.39, window 0.34, four-class mean 0.51 (re-checked); live best 0.43/0.39 (recomputed). Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819), [github.com](https://github.com/AECFoundry/AECV-Bench). Experiment: 30 dev plans, exact/within 1/MAE.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-floorplan-a, lit-floorplan-b, lit-market-a, lit-market-b, lit-market-c

<a id="i433"></a>
### 433. Report share of rooms within 5, 10 and 25 percent

- What: Report the error distribution, not one median.
- Evidence (floor-plans): PlanQ: 45% of plans over 5%, 26% over 10%, 12% over 20%; practitioners differ about 10% re-measuring.
- Source: [github.com](https://github.com/SoftHeart1314/planq-cubicasa-benchmark)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: the tail matters
- Reports: lit-rooms-a, lit-rooms-b

<a id="i434"></a>
### 434. Diagnose misses versus loose boxes versus size floor on dev

- What: Report for our detector the split of ground truth into missed, loose (IoU 0.5-0.75) and tight, plus the box area at which half the objects are found, per class. Tells whether errors are recall (count) or box tightness (irrelevant for counts).
- Evidence (floor-plans): On 21k ground-truth boxes: clean model 10.2% missed / 4.8% loose / 85.0% tight; scanned 25.5% / 34.4% / 40.1%. Half of objects found at 120 px box area clean vs 909 px scanned (IoU 0.5), so the smallest findable symbol is about 8x larger in area on scans.
- Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness)
- Licence: analysis only; code MIT. CubiCasa5K leakage: n/a.
- Cost: 1 h script (estimate)
- Experiment: Compute the three-way split and the size-at-50%-found curve per class on dev for the first detector; decide whether tiling or resolution is the next lever.
- What breaks on our images: Their absolute pixel areas may not match our render size; use the ratio.
- Moves: trust. Why this group: exact count cares about missed and duplicate boxes, not tightness
- Also (count, floor-plans): Re-render plans at several stroke widths and blurs. Render vector gold at several stroke widths and blur levels, recount. Evidence: Paired renderings of identical layouts: depiction shifts dominate loss, strict localisation drops more than AP50 (Automation in Construction 2026, abstract). Source: [doi.org](https://doi.org/10.1016/j.autcon.2026.107193). Experiment: Detector vs template matching exact rate per stroke width.
- Also (data, adjacent-field): Negative: scan-style augmentation can lower the clean score. Report a clean slice and a degraded slice separately; keep an augmented plus clean mixture. Evidence: Forms: digital mAP fell for 3 of 4 models (-0.018, -0.006, -0.003); music clean AP 87.6 to 83.3 after ScoreAug; Grayworld+CLAHE preprocessing +0.92 then -0.06 depending on inference size (arXiv 2608.24154). Source: [arXiv 2502.06132](https://arxiv.org/abs/2502.06132), [arXiv 2608.24154](https://arxiv.org/abs/2608.24154). Experiment: Dev exact count on a clean and a degraded slice per augmentation setting.
- Also (detect, floor-plans): Paired clean-versus-scan evaluation recipe. Evaluate every detector on a paired clean/scanned dev set built with our own degradations, report AP50 and exact count per condition. Evidence: Scan-shift study: strict-IoU AP falls far more than AP50 on scans, caused by depiction change inside boxes, not background; recipe repo code MIT, checkpoints non-commercial. Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness). Experiment: Build paired set from dev images with scan degradations.
- Also (floorplan, floor-plans): Stroke thickening and blur test of our detector. Apply the scan-shift study's degradations to dev images and re-score. Evidence: Clean 0.832 vs scanned 0.751 AP50, AP small 0.700 vs 0.106; thicker strokes medium AP50 0.881 to 0.253 (result JSON, re-checked). Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness), [zenodo.org](https://zenodo.org/records/18890483). Experiment: Re-score best arm; drop over 10 AP50 points means add stroke/blur augmentation.
- Also (market, adjacent-field): Agreement between a clean run and a degraded copy of the same plans. Rotate, blur, rescale and re-photograph 100 plans and report agreement of counts with the clean run, as scanner concordance studies do. Evidence: DPA statement R6: interscanner concordance on the same reference slides is an accepted shortcut. Source: [journals.sagepub.com](https://journals.sagepub.com/doi/10.1177/2993091X261455975). Experiment: Concordance rate of counts under each degradation on dev.
- Also (rooms, our-idea): Degrade dev plans and re-score. Downscale, JPEG, blur, small and 90 or 180 degree rotation, photocopy ops, then re-score area error. Evidence: No room or area result exists on scans or photos. Source: [arXiv 2504.03241](https://arxiv.org/abs/2504.03241). Experiment: Drop in share within 10% above 15 points means style augmentation first.
- Also (sheet, floor-plans): Test on scan-style images, not only clean renders. Hold out a scan-style slice and report scores separately; models tuned on clean renders collapse on scans. Evidence: Vectorised-graph classifier: window F1 91-98 on upright CubiCasa5K but 3.7-12.7 on 122 scanned plans; FloorYOLO mAP50 0.995 on synthetic and 0.824 on scanned CVC-FP. Source: [arXiv 2504.03241](https://arxiv.org/abs/2504.03241). Experiment: Split dev scores by a scan indicator (noise, JPEG) and compare.
- Also (sheet, search-only): Read the controlled study on floor-plan detection under real scans. Open the 2026 Automation in Construction paper on scan robustness limits (open access) and extract its degradation recipe for our augmentation and gate. Evidence: Identified but unread; closest paper to our scan problem. Source: [doi.org](https://doi.org/10.1016/j.autcon.2026.107193). Experiment: Read it and list degradations and metrics.
- Reports: lit-count-a, lit-data-a, lit-data-b, lit-data-c, lit-detect-a, lit-floorplan-a, lit-floorplan-b, lit-market-c, lit-rooms-a, lit-rooms-b, lit-rooms-c, lit-sheet-a

<a id="i435"></a>
### 435. Report boundary IoU next to mIoU

- What: Track boundary IoU of the wall and room masks; the gap to mIoU is the bias that moves small-room areas.
- Evidence (floor-plans): MitUNet mIoU 87.91 against B-IoU 85.01.
- Source: [arXiv 2512.02413](https://arxiv.org/abs/2512.02413)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 30 min
- Experiment: Correlate with area error.
- What breaks on our images: none
- Moves: scale-areas. Why this group: explains area bias
- Reports: lit-rooms-b

<a id="i436"></a>
### 436. CubiCasa5K annotation misalignment and noise

- What: Expect SVG/PNG misalignment and wrong SVGs; answers are annotation counts.
- Evidence (floor-plans): Issues 20, 71; 1,020 of 5,000 SVGs fail one converter.
- Source: [github.com](https://github.com/CubiCasa/CubiCasa5k/issues/20)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Audit dev images where counts disagree.
- What breaks on our images: n/a
- Moves: trust. Why this group: explains unreachable errors
- Also (market, adjacent-field): Recount 50 plans by three people to bound label noise. Have three people recount doors and windows on 50 plans and take the majority; the disagreement is the ceiling on exact match. Evidence: DPA R9: reference standard at least three readers with majority; CubiCasa5K label noise worth about 8 points of wall F1 (fpvec-lab). Source: [journals.sagepub.com](https://journals.sagepub.com/doi/10.1177/2993091X261455975), [arXiv 2608.25608](https://arxiv.org/abs/2608.25608). Experiment: Compare majority recount with dataset answers on 50 dev plans.
- Also (ocr, adjacent-field): Check hand-made crop labels for noise. Run a label-error detector (SELECT) or a second reader over the crop labels before fine-tuning. Evidence: SELECT flags 98.45% of synthetic corruption; removing flagged noisy labels gave only +0.2 to +0.7 average accuracy (arXiv 2512.14050). Source: [arXiv 2512.14050](https://arxiv.org/abs/2512.14050). Experiment: Only if crop labels come from pseudo-labelling; compare with and without the filter.
- Also (trust, adjacent-field): Audit dev gold counts before calibrating. Re-count a sample of dev plans and rank plans where the model is confident but the label disagrees (ObjectLab style). Evidence: Re-annotation added up to +60% objects (KITTI), +40% (COCO) (2609.21822); 5% label noise cut release 85% to 57% (2607.24562); ObjectLab P@100 0.71 vs 0.22 (2309.00832). Source: [arXiv 2609.21822](https://arxiv.org/abs/2609.21822), [arXiv 2309.00832](https://arxiv.org/abs/2309.00832). Experiment: Hand-count 50 dev plans; gold wrong on over 5% changes the claim.
- Reports: lit-floorplan-a, lit-floorplan-b, lit-market-c, lit-ocr-b, lit-trust-a, lit-trust-b, lit-trust-c

<a id="i437"></a>
### 437. Report exact, within 1, MAE and bias, by subgroup and count bin

- What: Score every method as exact / within 1 / MAE / bias, split by rotated, small, photographed and by true-count bin (0-5, 6-9, 10-13, 14+).
- Evidence (floor-plans): AECV-Bench exact 55-73% at 0-5 vs 6-48% at 10+; PlanQ prompted VLM 0.59-0.68 at 0-5, 0.04-0.13 at 14+ (computed from per-plan CSVs).
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench), [github.com](https://github.com/SoftHeart1314/planq-cubicasa-benchmark)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Add to the eval script; compare with AECV and PlanQ tables.
- What breaks on our images: Count conventions differ between benchmarks and our brief.
- Moves: trust. Why this group: one headline number hides the dense plans
- Also (count, our-idea): Report exact rate and within-one per class. Report exact, within-one and MAPE per class, upright vs rotated. Evidence: No source reports within-one on drawings; AECV-Bench MAPE 16-30%. Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819). Experiment: Add exact, within-one and MAPE per class, upright and rotated, to the scorer; report all three on every run.
- Also (ocr, our-idea): Score the text route per room type, upright and rotated separately. Report exact match per room type and per sheet rotation on the dev split, plus unreadable flags, so each change has a number. Evidence: Baseline: 23-81% exact per room type on 40 images, one sheet in three rotated. Source: none. Experiment: Fixed 40-image dev slice, same scorer for every text item.
- Reports: lit-count-a, lit-floorplan-a, lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i438"></a>
### 438. Score exact counts and within-one counts, not mAP alone

- What: Judge every data or augmentation arm by exact count and a within-one count per class; every paper reports AP or error and none reports exact match.
- Evidence (floor-plans): Construction diagrams: mAP 79-83 but 4% of symbols missed; AP@0.25 hides box precision in music; Co-DETR counting reaches toilet exact-count 87.63% on 97 CubiCasa5K images (arXiv 2509.17283 Table 1), against 79.4% for the 2019 weights on our dev.
- Source: [arXiv 2509.17283](https://arxiv.org/abs/2509.17283)
- Licence: n/a. CubiCasa5K leakage: unknown.
- Cost: 0
- Experiment: Report exact and within-one per class for each arm.
- What breaks on our images: None.
- Moves: trust. Why this group: the scored metric
- Reports: lit-data-b, lit-data-c

<a id="i439"></a>
### 439. Report exact match by number of objects per plan

- What: Report door and window exact-match rate in bins of true count (0 to 5, 6 to 10, 11 to 15, 16+), since exact match falls steeply with plan size.
- Evidence (floor-plans): Gemini 3.5 Flash doors 0.67 (n 33), 0.33 (46), 0.48 (27), 0.14 (14); Flowtivity blog says about 2 in 3 for at most 5 doors and 1 in 10 for 15 or more.
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench), [flowtivity.ai](https://flowtivity.ai/blog/pdf2takeoff-free-open-source-construction-takeoff/)
- Licence: none. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Bin dev plans by true count and print exact rate and sample size per bin; a flat curve would mean our detector does not saturate.
- What breaks on our images: Small bins are noisy.
- Moves: trust. Why this group: shows where the headline number comes from
- Reports: lit-market-a

<a id="i440"></a>
### 440. Report counts, not AP

- What: AP50 says little about exact counts.
- Evidence (floor-plans): BlueprintParse AP50 0.98 vs exact 0.566; PlanQ MAPE medians good while exact 27-49%.
- Source: [huggingface.co](https://huggingface.co/ThakiCloud/BlueprintParse-R50)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Use counts as the metric.
- What breaks on our images: n/a
- Moves: trust. Why this group: metric hygiene
- Also (sheet, floor-plans): Box AP overstates exact-count rate on unseen plans. Do not trust box AP from a same-distribution split as a predictor of per-image exact count; use exact count on unseen styles. Evidence: Fixture detector: test mAP50-95 0.926 but per-drawing exact count of 5 classes 0.566 (CI 0.434-0.698) on 53 novel plans; its error flag caught 0.478 of errors. Source: [huggingface.co](https://huggingface.co/models?search=BlueprintParse). Experiment: Report exact count on a held-out style slice, not only AP.
- Reports: lit-floorplan-a, lit-floorplan-b, lit-sheet-a

<a id="i441"></a>
### 441. fpeval scorer and fpgen degraded plans

- What: Use MIT fpeval for room and wall F1 over a tolerance sweep, and fpgen for plans with true scale and a degradation ladder.
- Evidence (floor-plans): Fixed checkpoint wall F1 0.74 to 0.825 on corrected labels; fpgen registration tested within 1.5 px.
- Source: [github.com](https://github.com/Cyprinus12138/fpvec-lab)
- Licence: MIT (skv4 non-commercial). CubiCasa5K leakage: no.
- Cost: 1 to 2 h
- Experiment: Score route 1 on fpgen tiers.
- What breaks on our images: Perspective and real scans out of scope.
- Moves: trust. Why this group: free scorer and degraded copies
- Reports: lit-rooms-a, lit-rooms-b

<a id="i442"></a>
### 442. PlanQ U-Net plus connected components as the floor

- What: Re-run the 512 px 4-stage U-Net with connected components and a closing kernel on our dev split; a detector must clearly beat it.
- Evidence (floor-plans): Exact door 64-67/190 (33.7-35.3%), window 56-63/190 on CubiCasa5K test, 2,315 training plans (segmentation_count_metrics.json, re-checked).
- Source: [github.com](https://github.com/SoftHeart1314/planq-cubicasa-benchmark)
- Licence: code MIT / no weights; labels CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 2-4 h, ~24 min per seed (claim)
- Experiment: Same counts on dev; report exact, within 1, MAE, bias, by count bin.
- What breaks on our images: Clean single-floor plans only, 512 px, no rotation; counting rule differs from ours.
- Moves: windows-doors. Why this group: cheap floor and error-shape template
- Reports: lit-floorplan-a, lit-floorplan-b

<a id="i443"></a>
### 443. Always run a real-only control and read per-class dev counts before keeping a synthetic source

- What: Every synthetic or pasted-crop arm is judged on dev per class (bathtub, sauna stove, shower, window, door) against a real-only run with the same schedule; the headline score is unlikely to move.
- Evidence (floor-plans): With thousands of real images the gain is inside the noise: wall F1 0.769 to 0.781 and 0.747 to 0.751, bootstrap half-width 1.3-1.7 points (arXiv 2608.25608 Table 4). 8.4k real images: synthetic pretrain then fine-tune 69.0 vs 69.2 real-only (arXiv 2605.26884).
- Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608), [arXiv 2605.26884](https://arxiv.org/abs/2605.26884)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0 extra (reporting rule)
- Experiment: Report per-class exact count and AP for each arm on dev only; keep a synthetic source only if a rare class moves beyond seed noise (run two seeds).
- What breaks on our images: None; the risk is skipping it.
- Moves: trust. Why this group: costless and decides every data question
- Reports: lit-data-a, lit-data-b, lit-data-c

<a id="i444"></a>
### 444. Evaluate on whole held-out plans, not on tile validation

- What: Report exact counts on whole plans; tile-level mAP overstates the result.
- Evidence (floor-plans): Tile validation mAP 72.40 vs about 59 on 25 whole plans (arXiv 2006.00684). Synthetic benchmarks saturate: SFPI mAP 0.995 on its own set, 0.750 from SFPI to SESYD (Mishra 2021).
- Source: [arXiv 2006.00684](https://arxiv.org/abs/2006.00684)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: Compute dev exact count after tile merging, not tile AP.
- What breaks on our images: None.
- Moves: trust. Why this group: costless rule
- Reports: lit-data-a, lit-data-c

<a id="i445"></a>
### 445. Plan the number of checked plans before claiming a guarantee

- What: Use the exact-tail table: with delta 0.10 and alpha 0.10 at least 22, 38, 52, 65 accepted plans for 0..3 wrong; 66 with 100 thresholds tried; 45/77/105/132 at alpha 0.05. Real needs are higher when the true error is near the target.
- Evidence (adjacent-field): Own arithmetic from the exact tail (recomputed); 179 units for an 80% chance at 5% true error, 13,407 at 9% (2609.22048); 134 units certify 18.5% of cases (2603.08907).
- Source: [arXiv 2609.22048](https://arxiv.org/abs/2609.22048), [arXiv 2603.08907](https://arxiv.org/abs/2603.08907)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Count accepted dev plans per question group at the chosen threshold and compare with the table; if below, report 'not certified'.
- What breaks on our images: A pooled certificate first; per-type certificates need their own accepted plans.
- Moves: trust. Why this group: Tells what we can claim before spending time.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i446"></a>
### 446. Score detectors by centre match and per-image exact count, not AP50:95

- What: Rank candidates by centre-match recall and precision at a distance tolerance and by per-image exact-count rate per class; tune and score at IoU 0.5, never the default maxDets 100 (use 500).
- Evidence (adjacent-field): No paper reports exact-count rate; SKU-110K reports count MAE; DWD AP 0.86 to 0.92 when required overlap drops 0.5 to 0.25; scan study: strict-IoU AP falls far more than AP50 on scans; RF100-VL evaluates with maxDets 500.
- Source: [arXiv 1805.10548](https://arxiv.org/abs/1805.10548), [arXiv 1904.00853](https://arxiv.org/abs/1904.00853)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h
- Experiment: Implement scorer once; use for every run.
- What breaks on our images: Needs one centre definition (door leaf or arc); noisy for single digits.
- Moves: windows-doors. Why this group: The metric the product is judged on
- Reports: lit-detect-a, lit-detect-b, lit-detect-c

<a id="i447"></a>
### 447. Split crops by plan source, as the rebar study split by design institute

- What: Split fine-tune crops by plan source or developer so near-duplicate plans do not appear in train and test.
- Evidence (adjacent-field): The rebar paper split by design institute; our sealed dev/eval split is the analogue.
- Source: [frontiersin.org](https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2026.1839808)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none extra
- Experiment: Report crop-level exact match on a source-held-out set.
- What breaks on our images: Source names may be unknown.
- Moves: trust. Why this group: leak guard for fine-tune
- Also (sheet, our-idea): Keep composites and boxes inside the 3,828 dev images. Compose and train only from dev images; never include a sealed-eval plan in a composite. Evidence: Record 0003 leakage rule. Source: none. Experiment: Check composite source ids against the split file.
- Reports: lit-ocr-a, lit-sheet-b, lit-sheet-c

<a id="i448"></a>
### 448. Define one window per drawn cell once

- What: Fix label convention across labels, detector and counting rule; AECV, PlanQ and our brief differ.
- Evidence (adjacent-field): PubTables-1M: label ambiguity cost more than model choice; counting rules differ at three points (AECV prompt).
- Source: [arXiv 2110.00061](https://arxiv.org/abs/2110.00061)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Audit 50 dev images.
- What breaks on our images: n/a
- Moves: windows-doors. Why this group: label noise caps exact rate
- Also (count, adjacent-field): Window strip versus cell: define the unit. Check one mask per cell vs one per strip. Evidence: BunchCount: individual-trained counters fail on groups (arXiv 2609.04716); SAM 3 outputs group masks. Source: [arXiv 2609.04716](https://arxiv.org/abs/2609.04716). Experiment: Count strips both ways.
- Also (rooms, authors-claim): Merge touching gold instances before scoring. Merge adjoining gold boxes of one space. Evidence: AEC-Geometric-Bench does it to avoid scoring drawing style. Source: [github.com](https://github.com/KamaiEnterprises/aec-geometric-bench). Experiment: none
- Reports: lit-count-a, lit-count-b, lit-floorplan-a, lit-floorplan-c, lit-rooms-c

<a id="i449"></a>
### 449. Score scale by its effect on area share, not px per metre

- What: Compare error in areas or shares, as digitiser studies compare medians, not pixel error.
- Evidence (adjacent-field): ISPOR digitiser poster; correlation hides multiplicative bias.
- Source: [ispor.org](https://ispor.org/docs/default-source/euro2020/ispor-eu-2020-posterdigitization-pdf.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: Right metric.
- Reports: lit-scale-c

<a id="i450"></a>
### 450. Compare confidence scores by failure AUROC and AUGRC, with miss-aware metrics

- What: Use failure = answer differs from gold; report AUROC, AUGRC and ECARB at the review budget; avoid D-ECE alone.
- Evidence (adjacent-field): AUGRC = (1-AUROC_f) acc (1-acc) + 0.5(1-acc)^2 (2407.01032); D-ECE cannot see missed objects (2309.00464); ECARB 1.93 at a 30% budget for one model (2608.01792).
- Source: [arXiv 2407.01032](https://arxiv.org/abs/2407.01032), [arXiv 2309.00464](https://arxiv.org/abs/2309.00464)
- Licence: code Apache-2.0 (fd-shifts). CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Implement once and reuse for every score.
- What breaks on our images: Classification-oriented.
- Moves: trust. Why this group: One yardstick for all candidates.
- Also (sheet, adjacent-field): Error-versus-discard curve for each gate component. Plot exact-count error among answered sheets against fraction discarded, up to 0.3, for each named component; keep only components that bend the curve. Evidence: OFIQ and the EDC protocol: discarding the 10% lowest sharpness cut false non-match 10% to 8%, exposure only to 9.5%; fractions above 0.3 are not operational. Source: [arXiv 2303.13294](https://arxiv.org/abs/2303.13294). Experiment: One curve per component on dev; choose the threshold at a discard of 0.3 or less.
- Reports: lit-sheet-b, lit-trust-a, lit-trust-c

<a id="i451"></a>
### 451. Score plan splitters by exact plan count, not box overlap

- What: Report exact plans per sheet next to box F1 and mAP.
- Evidence (adjacent-field): Newspaper article segmentation: box metric and count metric rank two systems differently (F1 80.39 against 70.69, count Jaccard 86.19 against 89.00); per-box F1 above 0.9 does not give an exact count.
- Source: [arXiv 2607.15082](https://arxiv.org/abs/2607.15082)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Add plan-count confusion matrix (true 1/2/3/4) to the eval.
- What breaks on our images: None.
- Moves: plans. Why this group: Our metric is the count.
- Reports: lit-sheet-a, lit-sheet-b

<a id="i452"></a>
### 452. Count merged and split rooms, not IoU alone

- What: Score merges and splits next to F1.
- Evidence (adjacent-field): Sharif 2023 recall 97.19% but completeness 73.48% on one map; ICDAR 2021 punishes merges hard.
- Source: [arXiv 2303.13798](https://arxiv.org/abs/2303.13798)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: IoU hides merges
- Reports: lit-rooms-c

<a id="i453"></a>
### 453. Leak-check external data with rotation- and mirror-invariant perceptual hashes

- What: Before adding any external plan set, deduplicate against dev and eval images with a perceptual hash over all rotations and mirrors; byte hashes miss re-encoded, rescaled or mirrored copies.
- Evidence (adjacent-field): Camouflage benchmark: 50 of 76 test images (65.8%) were altered copies of training images while exact hashing reported 0 overlap (arXiv 2610.09807 appendix).
- Source: [arXiv 2610.09807](https://arxiv.org/abs/2610.09807)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Hash all candidate external images in 8 orientations; count matches to dev and eval.
- What breaks on our images: Plans share templates, so near-duplicates are common.
- Moves: trust. Why this group: leak protection for any scored run
- Also (data, adjacent-field): Keep only generated plans near the real dev plans. From a large generated pool, keep the plans whose perceptual hash or embedding is closest to dev plans, e.g. 50k out of 1M; compare filtered against unfiltered. Evidence: Industrial sim-to-real: picking renders closest to a few real ones by perceptual hash gave best mAP50 (98% and 67% on two sets); diffusion adaptation cost more time with no clear gain (arXiv 2511.23241). Source: [arXiv 2511.23241](https://arxiv.org/abs/2511.23241). Experiment: Filtered vs unfiltered 50k pretraining set, dev per class.
- Also (data, adjacent-field): Structure and perceptual-hash deduplication of generated plans. Deduplicate generated sheets by structural hash (graph) and perceptual hash before training so the effective sample count is real. Evidence: SynthPID: 12,000 attempts gave 665 accepted images after Weisfeiler-Lehman and perceptual-hash deduplication; ResPlan has 6.9% near-duplicates. Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Report near-duplicate rate in a generated set.
- Reports: lit-data-a, lit-data-b, lit-data-c

<a id="i454"></a>
### 454. Treat the plan, not the question, as the independent unit

- What: Resample and split by plan; estimate within-plan correlation of the threshold indicator and report an effective sample size.
- Evidence (adjacent-field): Design effect 1+(m-1)rho; 1,000 rows act like 217-485 independent (2608.21262); receipt certificate 0.060 per document vs 0.171 per field (2608.14639).
- Source: [arXiv 2608.21262](https://arxiv.org/abs/2608.21262), [arXiv 2608.14639](https://arxiv.org/abs/2608.14639)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Cluster bootstrap by plan on dev; compare effective size with raw count.
- What breaks on our images: Fewer certifiable plans than answers.
- Moves: trust. Why this group: Counting answers as independent overstates the evidence.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i455"></a>
### 455. Choose the threshold on one split and certify on a disjoint one

- What: Split dev by plan into a tuning half and a certification half; pre-declare few gates; report the certified half only.
- Evidence (adjacent-field): 299 plus 368 independent units at alpha 0.01 (2610.35092); 28 of 30 gates picked on audit A stayed hidden on audit B (2610.29067).
- Source: [arXiv 2610.35092](https://arxiv.org/abs/2610.35092), [arXiv 2610.29067](https://arxiv.org/abs/2610.29067)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 30 min work
- Experiment: Repeat random splits and report the violation rate with a binomial interval and a random-split negative control.
- What breaks on our images: Doubles the labelled data needed.
- Moves: trust. Why this group: Prevents an inflated claim.
- Reports: lit-trust-b, lit-trust-c

<a id="i456"></a>
### 456. Print both exact-match rate and sum-weighted error

- What: A 9-window plan counted as 8 is wrong exactly but 99% right sum-weighted; print both and name which is which.
- Evidence (adjacent-field): EagleView's 98.77% is sum-weighted; AECV-Bench weighted absolute error for the best model 11% (doors) and 18% (windows) against 0.43 exact.
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Add weighted absolute error to the score report.
- What breaks on our images: Needs care in wording.
- Moves: trust. Why this group: stops a flattering misreading
- Reports: lit-market-b, lit-market-c

<a id="i457"></a>
### 457. Compute the ceiling on the share of plans markable as sure

- What: Use (mu - alpha)/(1 - alpha) as the minimum unmarked share before building anything.
- Evidence (adjacent-field): Proposition 3 of 2606.29054; own arithmetic with mu 0.407 gives at most 66% marked.
- Source: [arXiv 2606.29054](https://arxiv.org/abs/2606.29054)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 15 min work
- Experiment: Compute with the dev wrong-answer rate per plan.
- What breaks on our images: Distribution-free bound.
- Moves: trust. Why this group: Tells what is achievable.
- Reports: lit-trust-b

<a id="i458"></a>
### 458. Per-plan 'seen in training' flag in the calibration table

- What: Carry a flag for plans in the CubiCasa5K train split and report the gate with and without them.
- Evidence (adjacent-field): 15.0% of VERDICT's corpus overlapped one reader's pool and results are reported without it (2608.22183); 829 of 959 eval drawings leaked (docs/decisions/0003-training-data.md).
- Source: [arXiv 2608.22183](https://arxiv.org/abs/2608.22183)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 1 h work
- Experiment: Report both gate results.
- What breaks on our images: none
- Moves: trust. Why this group: Required for honest claims.
- Reports: lit-trust-c

<a id="i459"></a>
### 459. Decide whether closets and cabinets are rooms

- What: Agree the gold definition before scoring.
- Evidence (authors-claim): Cabrera 2018: closets are the largest miss class; up to 72 per plan.
- Source: [dspace.library.uvic.ca](https://dspace.library.uvic.ca/bitstreams/189b0857-eaf8-49d0-b6b1-11c768e85ce4/download)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: room-types. Why this group: changes counts
- Reports: lit-rooms-c

<a id="i460"></a>
### 460. 200-image smoke test before each full fine-tune

- What: Run 200 images for 3 epochs per detector; loss must fall and AP be non-zero before the full run (catches category id offset, eval size and loader bugs).
- Evidence (authors-claim): D-FINE issues 72, 214, 299 (AP 0 with category ids from 1; mAP 0 after eval_spatial_size edit).
- Source: [github.com](https://github.com/Peterande/D-FINE/issues/214)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0.5 h per detector
- Experiment: Check loss and AP after 3 epochs.
- What breaks on our images: 
- Moves: none. Why this group: Protects the tonight GPU window
- Reports: lit-detect-c

<a id="i461"></a>
### 461. Quote the independent Togal study correctly

- What: When a judge cites Togal, say the one independent study found 11 of 13 count items exact after the user corrected the markups, on one commercial building with schedules, and areas under-estimated.
- Evidence (authors-claim): Utica (ASC 2026) Table 1: window types exact, door types off by -9.09% and +66.67%; 29 line items.
- Source: [easychair.org](https://easychair.org/publications/paper/pkrRp)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: wording for the pitch
- What breaks on our images: One building, schedule tags, post-review numbers.
- Moves: demo. Why this group: stops a wrong comparison
- Reports: lit-market-a, lit-market-c

<a id="i462"></a>
### 462. Keep a ledger of what each vendor percentage measures

- What: Prepare a one-page table: 98% (executive quote), 20.4% (students, area), 76% (best case), 25% tolerance (Handoff), 97% (scale acceptance), with what each measures and why it is not an exact count.
- Evidence (authors-claim): Traced in a: Togal FAQ, ForConstructionPros quote, Zhao et al. abstract, Kansas page, Trimble blog.
- Source: [togal.ai](https://www.togal.ai/faq), [doi.org](https://doi.org/10.1111/ejed.70287)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: none: reference for the pitch
- What breaks on our images: Pages change; Kreo's help page has already gone.
- Moves: demo. Why this group: answers the first question a judge asks
- Reports: lit-market-a, lit-market-c

<a id="i463"></a>
### 463. Baseline: always answer one plan per sheet

- What: Score the constant answer 1 for plans and use it as the bar every plan counter must beat.
- Evidence (our-idea): 79.5% exact on dev (3,044 of 3,828), so the room is the other 20.5%, about 1.5 points overall.
- Source: none
- Licence: own code. CubiCasa5K leakage: n/a.
- Cost: minutes
- Experiment: Compute exact plan count of constant 1 on the dev split; report per plan-count class.
- What breaks on our images: Nothing; it is arithmetic.
- Moves: plans. Why this group: Sets the bar for all plan counters.
- Reports: lit-sheet-b, lit-sheet-c

<a id="i464"></a>
### 464. Exact-count rate predicted from per-object recall

- What: Use (1-miss)^n as an upper bound to set targets: with about 9 objects per class, recall 0.91 gives 43% exact, 0.95 gives 63%, 0.97 gives 76%, 0.99 gives 91%; every recall point is worth about 4 exact points.
- Evidence (our-idea): Arithmetic, not a source; best published door/window AP50 about 90 (leaky), so a first detector lands near the earlier 32-37% network and up to about 65%.
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: Compare measured exact rate against the bound per class.
- What breaks on our images: Ignores false positives and correlated misses.
- Moves: windows-doors. Why this group: Sets the expected range before the first number
- Reports: lit-detect-a, lit-detect-c

<a id="i465"></a>
### 465. Smoke test for the reported v6 ONNX non-ASCII output

- What: Read a clean line with a, o with dots and A with ring and check the string, because issue 18364 reported mojibake on the PaddlePaddle ONNX files.
- Evidence (our-idea): Own check: RapidOCR 3.10 v6 small ONNX with the fi dictionary read five clean lines exactly, no mojibake.
- Source: [github.com](https://github.com/PaddlePaddle/PaddleOCR/issues/18364)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 10 min (estimate)
- Experiment: Add one ä/ö line to the OCR smoke test.
- What breaks on our images: Clean 40 px renders only.
- Moves: none. Why this group: 10 minutes
- Reports: lit-ocr-a, lit-ocr-c

<a id="i466"></a>
### 466. Fix the wall convention of the gold area before measuring

- What: Check whether gold room areas are net internal or centre-line and score polygons in the same convention.
- Evidence (our-idea): Convention alone moves a 10 m2 room by roughly 8 to 15% with 20 cm walls (report arithmetic, no peer-reviewed source); matchline keeps gross and net polygons per room.
- Source: [github.com](https://github.com/anchapin/matchline/issues/740)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Compute area both ways for 50 dev rooms with printed areas and see which matches within 2%.
- What breaks on our images: Wall thickness varies per sheet.
- Moves: scale-areas. Why this group: cheap and can dominate the area error
- Reports: lit-rooms-c

## Try next

<a id="i467"></a>
### 467. Report per image source: scan, phone photo, CAD export, rotated

- What: Do not publish one overall number; report per capture type and fix a minimum usable input that triggers 'send to a person'.
- Evidence (adjacent-field): MIDOG: per-scanner F1 spread 0.43 to 0.85 hidden by a 0.70 to 0.77 average; DPA validation statement: validate per scanner, minimum input quality; pdf2takeoff: 99.8% born-digital against 37.3% degraded.
- Source: [arXiv 2204.03742](https://arxiv.org/abs/2204.03742), [journals.sagepub.com](https://journals.sagepub.com/doi/10.1177/2993091X261455975)
- Licence: MIDOG data CC BY-NC-ND. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: Tag dev plans by source and rotation and report exact rate per tag.
- What breaks on our images: Source tags need labelling.
- Moves: trust. Why this group: where failures hide
- Also (scale, adjacent-field): Check interval coverage per image source. Check that scale intervals hold on held-out plans separately for scans, phone photos and others. Evidence: Conformal coverage is marginal and drops under shift. Source: [arXiv 2407.19938](https://arxiv.org/html/2407.19938). Experiment: Coverage of 10-90 interval per source type on dev.
- Reports: lit-market-b, lit-market-c, lit-scale-c

<a id="i468"></a>
### 468. Report recall by symbol area and by sheet size

- What: Add recall per symbol-size bucket (px area) and per sheet short-side bucket to every run to see where the stride fails.
- Evidence (adjacent-field): Thesis: RT-DETRv2 recall 0.095 on 0-1000 px areas vs 0.757 on 4000-6000; PCB study recall for 4-8 px boxes 0 at 640 px; scan study: 50% detection success area 120 px2 clean vs 909 scans.
- Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Bucket dev boxes by area; plot recall.
- What breaks on our images: Needs box sizes in input pixels.
- Moves: windows-doors. Why this group: Decides upscaling versus tiling
- Also (sheet, search-only): Downsampling sweep for the minimum legible symbol size. Render dev plans at 100%, 75%, 50% and 35% and score the detector to find where counts fail. Evidence: No study gives a pixel threshold; SynthPID states P&ID symbols of 8x8 px become unreliable at about 800 px long side. Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Exact count per class against symbol height; report the break point.
- Reports: lit-detect-a, lit-detect-b, lit-sheet-a, lit-sheet-b

<a id="i469"></a>
### 469. Score exact count and matched instances, report the gap

- What: Score the count and, separately, box or point matches per plan; a missed window cancelled by a false door leaf passes exact match.
- Evidence (adjacent-field): The counting survey states exact match is satisfied by compensating errors (arXiv 2608.23845).
- Source: [arXiv 2608.23845](https://arxiv.org/abs/2608.23845)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Per plan: exact, matched IoU 0.5, gap.
- What breaks on our images: Needs box labels.
- Moves: trust. Why this group: Honest numbers.
- Also (floorplan, adjacent-field): Score with one-to-one Hungarian matching. Use strict one-to-one matching, not greedy. Evidence: TempFit: greedy matching overestimates PQ; SymPointV2 77.0 to 28.5 under strict protocol. Source: [arXiv 2610.17776](https://arxiv.org/abs/2610.17776). Experiment: Check our eval.
- Reports: lit-count-b, lit-count-c, lit-floorplan-c

<a id="i470"></a>
### 470. Report false marks per plan next to exact match

- What: A review step with many wrong marks is worse than none; report false and missed marks per plan with the exact rate.
- Evidence (adjacent-field): Lehman 2015 JAMA IM: computer-aided detection gave no benefit in 495,818 real mammograms (sensitivity 85.3% with, 87.3% without).
- Source: [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/26414882/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Count false and missed marks per dev plan.
- What breaks on our images: Different domain.
- Moves: trust. Why this group: cost of a false mark is a second look
- Reports: lit-market-c

<a id="i471"></a>
### 471. Measure read-invention rate, not only exact match

- What: Report invented reads (a code returned where no label exists) and wrong-but-accepted reads next to exact match.
- Evidence (adjacent-field): Donut hallucination 10.8%, Florence-2 21.6% (Hybrid-VL); one false accept in 24 junk crops in own vote test.
- Source: [arXiv 2506.17374](https://arxiv.org/abs/2506.17374)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work (estimate)
- Experiment: Add junk crops (non-codes) to the dev set and report the false-accept rate per reader.
- What breaks on our images: Needs hand-checked junk crops.
- Moves: trust. Why this group: needed to trust the vote
- Reports: lit-ocr-a, lit-ocr-c

<a id="i472"></a>
### 472. Intrusion ratio and shared-edge recall as eval checks

- What: Score overlap between predicted rooms and gaps along walls.
- Evidence (adjacent-field): Defined in the parcel paper, no plan number.
- Source: [arXiv 2609.07520](https://arxiv.org/abs/2609.07520)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Report both next to area error.
- What breaks on our images: none known
- Moves: trust. Why this group: catches double-counted wall area
- Reports: lit-rooms-a, lit-rooms-c

<a id="i473"></a>
### 473. Measure review minutes and answers changed, with wrong suggestions in the test

- What: Crossed design: each person checks some plans with our overlay and some by hand; hide our total until they have counted; include plans where our answer is wrong; record minutes and answers changed.
- Evidence (adjacent-field): Ki-67: error 2.1% with AI against 5.9% (90 pathologists); Click2Poly: 303.5 against 199 min, Latin-square; Dratsch 2023: correct ratings 79.7% to 19.8% on wrong suggestions.
- Source: [europepmc.org](https://europepmc.org/article/PMC/PMC10787826), [arXiv 2608.11424](https://arxiv.org/abs/2608.11424)
- Licence: studies; Click2Poly code not found. CubiCasa5K leakage: n/a.
- Cost: 3 h for one person on 20 plans (estimate)
- Experiment: One person, 20 dev plans, hand count against overlay check; settle minutes per plan and changed answers.
- What breaks on our images: Small sample; demo claim, not a result.
- Moves: demo. Why this group: the person-plus-machine number construction lacks
- Reports: lit-market-a, lit-market-c

<a id="i474"></a>
### 474. Sweep rendered codes over height, rotation and blur to find the readable cliff per engine

- What: Render the label codes at 5, 6, 8, 10, 12, 16 px, four rotations, several blur and JPEG levels, on white and on line clutter, run each engine on each crop and plot exact match.
- Evidence (adjacent-field): No published number for 2-4 character labels at 10 px. A blog test finds a cliff between 6 and 8 px capital height; plate recoverability maps (arXiv 2604.23814) use the same sweep idea with viewing angle.
- Source: [arXiv 2604.23814](https://arxiv.org/abs/2604.23814)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 to 2 h work, CPU only (estimate)
- Experiment: Plot exact match against cap height and rotation for PP-OCRv5 mobile, v6 small and medium, and the four-rotation vote; the cliff position gives the minimum size we flag as unreadable.
- What breaks on our images: Rendered fonts differ from real plans; the engine's result depended on canvas size in one setup.
- Moves: trust. Why this group: the missing 10 px number, needs no real data
- Reports: lit-ocr-a, lit-ocr-c

<a id="i475"></a>
### 475. Assert the compared quantity before reporting a score

- What: Add a check that predictions and gold refer to the same quantity before scoring.
- Evidence (adjacent-field): PlotPick v1 inflated by 10+ points from scoring against the wrong axis on 427 of 529 items.
- Source: [arXiv 2605.06021](https://arxiv.org/html/2605.06021)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: Cheap.
- Reports: lit-scale-c

<a id="i476"></a>
### 476. Measure false positives after super-resolution on drawings

- What: Any SR experiment must report false positives and 'did any count change' per image, not PSNR or SSIM.
- Evidence (adjacent-field): No study counts false positives after SR on drawings; in the diagram study SSIM was higher for the worse restorer (0.6187 against 0.5577).
- Source: [arXiv 2312.13620](https://arxiv.org/abs/2312.13620)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Add false-positive and per-image count-change columns to the SR A/B.
- What breaks on our images: None.
- Moves: trust. Why this group: Cheap rule for any SR test.
- Reports: lit-sheet-a, lit-sheet-c

<a id="i477"></a>
### 477. Report exact match and a coverage x precision composite side by side

- What: Print exact-match rate per question type, MAPE per class, and a Handoff-style composite (coverage^0.4 x precision^0.6) separately, labelled by tolerance, so nobody reads a 25% tolerance number as exact.
- Evidence (authors-claim): Handoff-H1: composite 81.6 against estimators 77.6 at 25% tolerance (abstract re-read); AECV-Bench reports exact match and MAPE.
- Source: [arXiv 2608.15032](https://arxiv.org/abs/2608.15032), [arXiv 2601.04819](https://arxiv.org/abs/2601.04819)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Add MAPE and a composite column to the scoring report and check they rank methods in the same order as exact match on dev.
- What breaks on our images: Their composite is for line items, ours for counts.
- Moves: trust. Why this group: framing against vendor claims
- Reports: lit-market-a, lit-market-c

<a id="i478"></a>
### 478. Counting may need only IoU 0.5 boxes, so scan shift costs counts less than strict localisation

- What: Score counts at loose IoU and check the loss against strict-IoU AP on scan-like plans.
- Evidence (our-idea): Carrara et al. 2026 (abstract only): RT-DETR AP75 and AP@0.85 fall much more than AP50 on scanned CubiCasa5K; line depiction inside the box is the main cause. Single-class Co-DETR doors: mAP 0.403 vs mAP@50 0.793 (DoorDet). Lighting symbols: mAP@50 0.985 vs 0.7596 overall (2608.14317). Inference not in the paper.
- Source: [arXiv 2508.07714](https://arxiv.org/abs/2508.07714), [arXiv 2608.14317](https://arxiv.org/abs/2608.14317)
- Licence: checkpoints CubiCasa5K-trained. CubiCasa5K leakage: yes.
- Cost: 1 h
- Experiment: Report count exact-match next to AP50 and AP75 on dev for clean vs degraded renders; settle whether count error tracks AP50.
- What breaks on our images: Paper only abstract-read; checkpoints leak.
- Moves: trust. Why this group: Cheap and informs which metric to tune
- Reports: lit-vector-a

## Later

<a id="i479"></a>
### 479. Older Kimi weak on drawing sheets

- What: Do not assume Kimi is good on drawings.
- Evidence (floor-plans): LED-BENCH Kimi-K2.5 24.79 vs 52.65 (2610.19571).
- Source: [arXiv 2610.19571](https://arxiv.org/abs/2610.19571)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Pilot first.
- What breaks on our images: n/a
- Moves: cost. Why this group: Warning.
- Also (vlm, search-only): Pilot Kimi K3.1 Pro and DeepSeek V4.1 Flash on plans. 20-image dev pilot with tile rule. Evidence: No published plan result; price 2.00/10.00 and 0.15/0.60 USD per 1M tokens. Source: [verda.com](https://verda.com/pricing). Experiment: Exact counts vs open models.
- Reports: lit-vlm-a

<a id="i480"></a>
### 480. State accuracy per use: exact on counts up to 8, within one above

- What: Report accuracy against what a bid tolerates (zero for window counts, a few percent for areas) and per distance or size bin, as Matterport does for lengths.
- Evidence (adjacent-field): Matterport lidar blog: 2 mm, 20 mm, 100 mm by job; iGUIDE 1% and 2%.
- Source: [matterport.com](https://matterport.com/blog/lidar-accuracy)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: none: reporting form
- What breaks on our images: Vendor blogs.
- Moves: demo. Why this group: reporting form
- Reports: lit-market-a, lit-market-c

<a id="i481"></a>
### 481. Print the accuracy formula, sample size and exclusions

- What: Publish exactly how the percentage is computed (EagleView: 1 minus 17.8 ft over 1,452.1 ft on 89 lines) and state the sealed sample and refused cases.
- Evidence (adjacent-field): CompassData PDF read in full by c: 98.77% is a sum-weighted ratio over about 100 items from one street; per-area error 3%.
- Source: [eagleview.com](https://www.eagleview.com/blog/eagleview-roof-measurements-confirmed/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: none: reporting form
- What breaks on our images: Vendor-commissioned test.
- Moves: demo. Why this group: reporting form
- Reports: lit-market-c

<a id="i482"></a>
### 482. Judge pretraining on precision at fixed recall

- What: Compare pretrained models on dev precision at a fixed recall, not recall alone; generic synthetic pretraining raises recall and floods false positives.
- Evidence (adjacent-field): Generic-shape synthetic detectors on real electrical diagrams: F1 only 0.33-0.35, precision 0.15-0.25 at recall 0.57-0.88, roughly four false boxes per true one (Chalmers thesis 2026).
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: Precision at recall 0.9 per class.
- What breaks on our images: Single thesis.
- Moves: trust. Why this group: reporting rule
- Reports: lit-data-c

<a id="i483"></a>
### 483. Audit released plans by confidence stratum and weight back

- What: Sample audit plans proportionally from strata, correct with the auditor's sensitivity.
- Evidence (adjacent-field): 200 labels: RMSE 4.56 to 2.46 points with proportional allocation (2610.35698); BRAVO sample grows with 1/margin squared.
- Source: [arXiv 2610.35698](https://arxiv.org/abs/2610.35698)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Simulate on dev outcomes.
- What breaks on our images: LLM benchmark evidence.
- Moves: trust. Why this group: Measures released error cheaply.
- Also (trust, adjacent-field): Sequential hypergeometric audit of a finite delivery. For a delivery of N plans, check random plans without replacement and stop with a stated risk. Evidence: Own arithmetic: 26-47 clean checks for N=200 (alpha 0.10 and 0.05); sequential boundaries in 2604.06116. Source: [arXiv 2604.06116](https://arxiv.org/abs/2604.06116). Experiment: Pick checks per N.
- Also (trust, adjacent-field): Audit-mode totals with intervals from a checked sample. For bill-of-materials totals, check a prioritised sample and report an interval. Evidence: Coverage 0.8-0.95 (2507.01372), 0.82 at 5% budget to 0.92 at 50% (2611.14380). Source: [arXiv 2507.01372](https://arxiv.org/abs/2507.01372). Experiment: Simulate on dev.
- Reports: lit-trust-a, lit-trust-c

<a id="i484"></a>
### 484. Measure two read modes: second read after the human, and concurrent

- What: Compare a reviewer who sees our marks from the start with one who counts first and then sees them; report answers changed and time.
- Evidence (adjacent-field): Articulate Pro (npj Digit Med 2026): staged second read changed the first diagnosis in 5.4% of 386 patients; concurrent read cut turnaround by 30.1 h at one site.
- Source: [tempus.com](https://www.tempus.com/publications/an-evaluation-of-artificial-intelligence-assisted-prostate-biopsy-reporting-in-the-articulate-pro-study/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: part of the reader study
- Experiment: Run both modes in the reader study.
- What breaks on our images: Abstract only.
- Moves: demo. Why this group: extension of the reader study
- Reports: lit-market-c

<a id="i485"></a>
### 485. Check whether CubiCasa-trained weights lean on Finnish labels

- What: Mask printed labels and re-score.
- Evidence (authors-claim): Student report: pretrained model relies on Finnish text (reported).
- Source: [mdsi.tum.de](https://www.mdsi.tum.de/fileadmin/w00cet/di-lab/pdf/Unetiq-final_documentation-WS2019.pdf)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 2 h
- Experiment: Label-masked dev score.
- What breaks on our images: Hypothesis.
- Moves: trust. Why this group: unmeasured
- Reports: lit-floorplan-a

<a id="i486"></a>
### 486. Report coverage and precision separately

- What: Report how many items we found (coverage) apart from how many found were right (precision), as estimators have lower coverage but higher precision.
- Evidence (authors-claim): Handoff-H1: estimators 65.5 coverage and 87.9 precision; system 86.1 and 78.8.
- Source: [arXiv 2608.15032](https://arxiv.org/abs/2608.15032)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Add coverage and precision per class to the score report.
- What breaks on our images: Tolerance-based there.
- Moves: trust. Why this group: makes misses visible
- Reports: lit-market-a, lit-market-c

<a id="i487"></a>
### 487. Include unanswerable questions in the test

- What: Add questions that cannot be answered (not to scale, no dimensions) and score whether the pipeline refuses.
- Evidence (authors-claim): ScaledDrawingBench (self-made): 99.8% on born-digital, 37.3% on degraded scans, 0 hallucinations on 92 unanswerable questions; circular as a yardstick.
- Source: [github.com](https://github.com/ajflow/pdf2takeoff)
- Licence: code Apache-2.0, data CC BY 4.0. CubiCasa5K leakage: n/a.
- Cost: 3 h (estimate)
- Experiment: Mark dev plans with no scale or several plans and score refusal rate.
- What breaks on our images: Generated electrical symbols, circular.
- Moves: trust. Why this group: tests the refusal rule
- Reports: lit-market-b

<a id="i488"></a>
### 488. Test a scale route at two resolutions

- What: Run any VLM or tool scale estimate on the same plan at two resolutions and report disagreement.
- Evidence (authors-claim): MapReason-OSM: best VLM agrees across two zooms about 73%.
- Source: [arXiv 2606.22597](https://arxiv.org/abs/2606.22597)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Disagreement rate on dev.
- What breaks on our images: none
- Moves: trust. Why this group: Cheap robustness check.
- Reports: lit-scale-c

<a id="i489"></a>
### 489. Monitor exchangeability on the reviewed stream

- What: Run MAPIE exchangeability tests on (score, correct) pairs of reviewed plans to flag a changed sheet mix.
- Evidence (search-only): Simulation: shift flagged in 5-6 of 6 runs with 0-1 false alarms (report b, not our data).
- Source: [github.com](https://github.com/scikit-learn-contrib/MAPIE)
- Licence: code BSD-3-Clause. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Replay dev plans in two source mixes and check detection.
- What breaks on our images: Needs labels for new plans; only synthetic evidence.
- Moves: trust. Why this group: Useful after deployment, not for the first claim.
- Reports: lit-trust-b

## Idea or pitch only

<a id="i490"></a>
### 490. Per-class fixture AP reference numbers

- What: Use published per-class numbers as targets, not evidence: toilet 100, kitchen sink 91, bathroom sink 85, bathtub 92, shower 100, window 76 (AP50 on 25 plans, 227 px tiles); AP75 for window stays about 32.
- Evidence (floor-plans): YOLOv2 on tiles, proprietary plans, 5400x3600 px, sink 70x80 px (4-8x our size).
- Source: [arXiv 2006.00684](https://arxiv.org/abs/2006.00684)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: Compare after the first run.
- What breaks on our images: Symbols much larger than ours.
- Moves: fixtures. Why this group: Sanity target
- Reports: lit-detect-a, lit-detect-c

<a id="i491"></a>
### 491. Direct detector numbers on raster plans for reference

- What: Use published direct-detector numbers as references for what a box detector reaches.
- Evidence (floor-plans): FloorYOLO: SESYD mAP@0.5 0.9950, CVC-FP real scans 0.8241 (window class weakest); Rezvanifar real plans mAP 59.0, AP50 89.3, window AP50 75.6; SkeySpot YOLOv8 mAP50 81.1 vs Faster R-CNN 48.6 (13 test plans); MuraNet door/window AP50 91.2/92.2.
- Source: [arXiv 2508.10449](https://arxiv.org/abs/2508.10449), [arXiv 2309.00348](https://arxiv.org/abs/2309.00348)
- Licence: YOLO AGPL; MuraNet no code. CubiCasa5K leakage: unknown.
- Cost: 0 h
- Experiment: None; compare our dev detector against these at IoU 0.5.
- What breaks on our images: SESYD synthetic; small test sets.
- Moves: none. Why this group: Reference only
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i492"></a>
### 492. Upper bound: exact primitives vs raster detection

- What: Record that a vectorise-first route cannot beat exact-primitive input, and that no one has measured the loss of recovered primitives.
- Evidence (adjacent-field): SymPoint-V2 Table 2: raster detectors AP50 60.2-64.0 vs vector 71.3 (mAP 60.1 vs 47.5 DINO); TextCAD Table 1: image-based PanCADNet PQ 60.80 vs 96.53 on CubiCasa5K primitives; Drawing2CAD: command accuracy 80.78 exact vectors vs 75.60 raster render.
- Source: [arXiv 2407.01928](https://arxiv.org/abs/2407.01928), [arXiv 2607.12678](https://arxiv.org/abs/2607.12678)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: Ground-truth primitives, not recovered ones.
- Moves: none. Why this group: Ceiling, not a route
- Reports: lit-vector-a, lit-vector-c

<a id="i493"></a>
### 493. Handoff-H1 and TAKEOFFBENCH-V1 as the claim to answer

- What: Treat the 81.6 versus 77.6 result as the claim a CTO has heard; do not put it in the same table as exact match. Cite that estimators beat the system on quantity precision (87.9 against 78.8).
- Evidence (authors-claim): arXiv 2608.15032: 10 residential sets, 2,009 items, 1,348 scored, LLM judge, precision at 25% tolerance; Windows & Doors trade 88 against 89 for estimators.
- Source: [arXiv 2608.15032](https://arxiv.org/abs/2608.15032), [handoff.ai](https://www.handoff.ai/tech/h1-model-release)
- Licence: harness without LICENSE; data on request; no weights. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: citation only
- What breaks on our images: Residential PDF sets with text, one company's benchmark and product.
- Moves: trust. Why this group: context, not comparable
- Reports: lit-market-a, lit-market-b, lit-market-c

<a id="i494"></a>
### 494. Keep an append-only ledger of scored runs by commit

- What: Show the score history by commit, not one number.
- Evidence (authors-claim): pdf2takeoff keeps a ledger.jsonl with date, commit, dirty flag and dataset per run, with compare against the previous run; our eval/results/runs follows the same rule.
- Source: [github.com](https://github.com/ajflow/pdf2takeoff)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: already the repo's rule
- What breaks on our images: Their runs came from dirty trees.
- Moves: trust. Why this group: already done
- Reports: lit-market-a

## Do not try (with the reason)

<a id="i495"></a>
### 495. Community CubiCasa-trained VLM adapters

- What: Do not use them for scored runs.
- Evidence (floor-plans): Exact whole program 3.4%, n=149.
- Source: [huggingface.co](https://huggingface.co/BDivyesh/boomi-stage3-vlm-cubicasa-research)
- Licence: NC. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: None.
- What breaks on our images: Leakage and NC.
- Moves: none. Why this group: Leakage.
- Reports: lit-vlm-a, lit-vlm-b, lit-vlm-c

<a id="i496"></a>
### 496. Direct multimodal-LLM count baseline to beat

Reviewer's note: Four scopes agree it is not a method. One run is still worth it as the baseline number for the pitch.

- What: Use published exact-match door and window counts of direct readers as the floor a detector must beat.
- Evidence (floor-plans): AECV-Bench (120 plans): best model door 0.39, window 0.34; others 0.03-0.28; bedrooms and toilets 0.6-0.9. Counting rules: only arc-drawn swing doors, each leaf counts, glazed or sliding openings are windows, adjacent windows without gap are one group.
- Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819), [github.com](https://github.com/AECFoundry/AECV-Bench)
- Licence: repo no licence file. CubiCasa5K leakage: unknown.
- Cost: 1 h
- Experiment: Run the benchmark's counting rules on dev once; record baseline exact-match.
- What breaks on our images: High-quality plans, not scans.
- Moves: demo. Why this group: Gives a public yardstick for exact-match
- Also (count, floor-plans): Prompted VLM exact count. Do not use VLM direct counts for doors and windows. Evidence: AECV-Bench 0.39/0.34; CountQA 42.9%; HoloCount dense 20% open (arXiv 2607.06420). Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819). Experiment: None; only as a fallback, count points in code instead (see count-emitted-points-in-code).
- Also (floorplan, floor-plans): Zero-shot or prompted VLMs as the counter. Do not use a VLM alone for door or window counts or boxes. Evidence: Door 0.09-0.43, window 0.03-0.39 exact; object F1 0.015-0.062 on construction sheets; SALI-FP door/window IoU 0.04-0.23 vs 0.62-0.72. Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819), [arXiv 2609.25615](https://arxiv.org/abs/2609.25615). Experiment: none
- Also (market, floor-plans): Zero-shot VLMs do not solve exact door and window counts. Do not rely on a single prompted VLM for door and window counts; the best sit at 0.43 to 0.55 on a set where a plan has about 9 doors. Evidence: AECV-Bench: 0.03 to 0.39 across ten models in the paper; Claude Opus 4.8 0.15/0.15; DrawingVQA quantity take-off best 41.7. Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819), [arXiv 2607.15418](https://arxiv.org/abs/2607.15418). Experiment: none: warning
- Also (vlm, floor-plans): Frontier VLM zero-shot row on dev. Run one or two frontier VLMs with the AECV-Bench counting prompt on dev plans to have a baseline row. Evidence: Door/window exact 0.39/0.34 best, 0.09-0.28 others (2601.04819 Table 1). Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819). Experiment: Score exact match per class on 20 dev plans.
- Also (vlm, floor-plans): Zero-shot VLM door/window counting. Do not rely on bare counts. Evidence: 0.03-0.39 exact (2601.04819). Source: [arXiv 2601.04819](https://arxiv.org/abs/2601.04819). Experiment: None.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c, lit-market-a, lit-market-b, lit-vector-a, lit-vector-c, lit-vlm-a, lit-vlm-b, lit-vlm-c

<a id="i497"></a>
### 497. Do not fuse doors and windows into one metric

- What: Score doors and windows separately; Window & Door F1 hides count errors and Kamai collapses window subtypes.
- Evidence (floor-plans): Raster2Seq Window & Door F1 77.8 against 78.5 for RoomFormer on CubiCasa5K; per-class counts not reported.
- Source: [arXiv 2602.09016](https://arxiv.org/abs/2602.09016)
- Licence: code MIT; weights CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: windows-doors. Why this group: hides the failure
- Reports: lit-market-a, lit-market-b

<a id="i498"></a>
### 498. Negative: select checkpoints on synthetic validation

- What: Compare detectors and pick checkpoints on a real dev subset, not on synthetic validation.
- Evidence (adjacent-field): Rendered-to-scanned gap depends on the model: LSTM 3.6 to 5.9 vs transformer 4.2 to 10.4 on the same data (arXiv 2608.10978). Generator-heavy sets saturate (SFPI 0.995).
- Source: [arXiv 2608.10978](https://arxiv.org/abs/2608.10978)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: reporting rule
- Reports: lit-data-b, lit-data-c

<a id="i499"></a>
### 499. Do not cite SEO tutorials as tests

- What: Count only studies with a named dataset; one blog test has an invented answer key and a trade roundup's 1.8% error gave tools a BIM model.
- Evidence (authors-claim): a round 11 and round 36 read the pages.
- Source: [aiinsightsnews.net](https://aiinsightsnews.net/ai-takeoff-software-accuracy-real-world-test/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: trust. Why this group: protects the pitch
- Reports: lit-market-a

<a id="i500"></a>
### 500. Hobby classical repos as baselines

- What: Run a flood-fill repo for a floor to compare.
- Evidence (search-only): No metrics in rasta, ChingXuen, tonkane.
- Source: [github.com](https://github.com/ChingXuen/Automatic-Room-Segmentation-and-Labelling-in-Architectural-Floor-Plan-Images)
- Licence: mixed, some none. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Share of rooms matched.
- What breaks on our images: No licence on some.
- Moves: none. Why this group: no evidence
- Reports: lit-rooms-b, lit-rooms-c
