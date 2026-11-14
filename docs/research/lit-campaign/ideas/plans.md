# Plans per sheet (splitting a sheet into plans)

17 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try next

<a id="i41"></a>
### 41. Split sheets into plans before room extraction

- What: Cut a sheet into plans by connected blocks of ink before any room step.
- Evidence (floor-plans): Raster2Seq itself was trained on single-plan crops; brief: one sheet in five has several plans.
- Source: [arXiv 2602.09016](https://arxiv.org/abs/2602.09016)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: half a day
- Experiment: Plan-count accuracy on dev.
- What breaks on our images: Touching plans.
- Moves: plans. Why this group: every room route assumes one plan
- Also (floorplan, adjacent-field): Detect drawing area, legend and title block. Detect plan regions to count plans per sheet and find the legend crop. Evidence: Layout detectors val mAP50 0.984 on 178 images (card); RF-DETR on 551 AEC drawings mAP50 0.949. Source: [huggingface.co](https://huggingface.co/GreenMap/yolo11x-blueprint-layout-detector), [arXiv 2607.18997](https://arxiv.org/abs/2607.18997). Experiment: Plans per sheet accuracy on dev.
- Also (sheet, adjacent-field): One-class plan detector (RF-DETR) trained on real multi-plan sheets. Fine-tune a box detector with one class 'plan'; count boxes; crop each box for later stages. Train on the real multi-plan dev sheets plus composites, add single-plan sheets and sheets with no plan as negatives. Evidence: RF-DETR m mAP50 0.949 / mAP50:95 0.890 on 551 facade drawing sheets (nine layout classes, 1344x800); the plan class (21 images, 26 boxes) reaches 0.969, which is close to anecdotal. No plans-per-sheet accuracy exists anywhere. Source: [arXiv 2607.18997](https://arxiv.org/abs/2607.18997), [arXiv 2511.09554](https://arxiv.org/abs/2511.09554). Experiment: Exact plan count on real multi-plan dev sheets held out from training (the 784 sheets with 2+ plans), against constant 1 (79.5% on dev). Also report box mAP, but the count decides.
- Reports: lit-floorplan-b, lit-floorplan-c, lit-rooms-a, lit-rooms-b, lit-rooms-c, lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i42"></a>
### 42. Paste single-plan sheets into synthetic multi-plan sheets for box training

- What: Compose 2-4 single-plan dev images on one canvas with gutters, borders or none, random rot90 per plan and background tone; the paste boxes are exact labels. Copy gap, alignment and relative-size statistics of the real two-plan sheets, add JPEG and blur.
- Evidence (adjacent-field): Open-PMC-18M: DAB-DETR on 500k synthetic compound figures scores mAP 98.58 on synthetic hold-out but 36.88 on real ImageCLEF 2016 (previous real-data detector 28.20). Tsutsui and Crandall 2017: grid composites added to real data move per-figure accuracy 0.846 to 0.859, random pasting 0.842; a bayesian page generator: +1.3 F1 when mixed with real pages, 3.6-4.0 lower alone.
- Source: [arXiv 2506.02738](https://arxiv.org/abs/2506.02738), [arXiv 1703.05105](https://arxiv.org/abs/1703.05105), [arXiv 2111.06016](https://arxiv.org/abs/2111.06016)
- Licence: recipe free; code Apache-2.0 (generator not published, write our own). CubiCasa5K leakage: no.
- Cost: about 45 min generator, then part of the plan detector run
- Experiment: Train the plan detector with and without composites; compare exact plan count on held-out real multi-plan sheets. Source panels from dev single-plan sheets only.
- What breaks on our images: Synthetic seams are too clean; composites alone fail on real sheets; a composite including a sealed-eval plan would leak.
- Moves: plans. Why this group: Free boxes, but only as an addition to real sheets.
- Also (data, adjacent-field): Compose multi-plan sheets and match page density. Build training sheets with 1-4 plans, title block and distractor drawings on one canvas, matching real counts per sheet; also gives exact plan labels. Evidence: Music: removing page concatenation (1-6 systems per page) cost +14.34 NED on 102 real scans, the largest single loss; no visual degradation +11.19 (arXiv 2605.10835 Table 3b). Scene text: without rotation and curve layout, Multi-Oriented 87.8 to 34.3 (arXiv 2602.06450). Source: [arXiv 2605.10835](https://arxiv.org/abs/2605.10835), [arXiv 2602.06450](https://arxiv.org/abs/2602.06450). Experiment: Pasted-composite plan detector vs real multi-plan sheets only, scored on real multi-plan dev sheets.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-sheet-b, lit-sheet-c

<a id="i43"></a>
### 43. Squash wide sheets to square for RF-DETR, or tile

- What: Test whether plan boxes survive a square squash of 2:1 sheets; fall back to tiles for symbols.
- Evidence (adjacent-field): Issue 1052: no rectangular support, maintainers say squash; one user's +20% was unloaded weights, then no difference between square and 3:4.
- Source: [github.com](https://github.com/roboflow/rf-detr/issues/1052)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 1 GPU run
- Experiment: Plan exact count on held-out multi-plan sheets at square against padded rectangular input.
- What breaks on our images: Small plans lose resolution after the squash.
- Moves: plans. Why this group: Cheap variant of the plan detector run.
- Reports: lit-sheet-a, lit-sheet-c

<a id="i44"></a>
### 44. Count plans by grouping detected elements by distance

- What: Cluster detected elements (windows, doors, fixtures, room boxes) by spatial distance and count the clusters as plans.
- Evidence (our-idea): none published for floor plans; the free baseline of the plan-count comparison.
- Source: none
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 1-2 h work, CPU, needs a first detector run
- Experiment: Compare with constant 1 and a plan detector on held-out real multi-plan sheets; tune the distance on the other dev sheets.
- What breaks on our images: Two plans drawn close together merge; one plan with an inset splits; needs detector recall to be decent.
- Moves: plans. Why this group: Free once the detector exists and doubles as the stage-8 check against the plan box count.
- Reports: lit-sheet-a, lit-sheet-c

## Later

<a id="i45"></a>
### 45. Add sheets with no plan as negatives

- What: Include sheets with no box so the detector learns to say nothing.
- Evidence (adjacent-field): RF-DETR supports background images since PR 915; a music-layout study added a blank-archive set to teach 'nothing here'.
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 30 min work
- Experiment: Plan count on sheets with 0 plans (if any in dev) with and without negatives.
- What breaks on our images: Dev may hold none.
- Moves: plans. Why this group: Only matters if sheets without plans occur.
- Reports: lit-sheet-a, lit-sheet-b

<a id="i46"></a>
### 46. Faster R-CNN as a plan-region detector with higher recall

- What: Train a torchvision Faster R-CNN on plan boxes as a cheaper-recall alternative to RF-DETR.
- Evidence (adjacent-field): On facade sheets: mAP50 0.930, recall 0.924 (RF-DETR m 0.949, recall 0.800); plan class 0.775 mAP50:95.
- Source: [arXiv 2607.18997](https://arxiv.org/abs/2607.18997)
- Licence: torchvision BSD-3. CubiCasa5K leakage: no.
- Cost: 2 h work, 1 short GPU run
- Experiment: Compare exact plan count with RF-DETR on held-out real sheets.
- What breaks on our images: Slower to converge on a small box set; no tuned recipe for drawings.
- Moves: plans. Why this group: Only if RF-DETR under-counts plans.
- Reports: lit-sheet-a

<a id="i47"></a>
### 47. Overlapping crops or search-then-reread for large sheets

- What: For big sheets, give a model overlapping crops, or have it locate then re-read regions at higher resolution.
- Evidence (adjacent-field): LED-BENCH: whole sheet 36.38%, fixed overlapping crops 49.34%, search-then-reread 49.74%; architecture best 53.45%.
- Source: [arXiv 2610.19571](https://arxiv.org/abs/2610.19571)
- Licence: data licence not read. CubiCasa5K leakage: n/a.
- Cost: 3 h (estimate)
- Experiment: Compare crops with whole image on multi-plan sheets in dev.
- What breaks on our images: Cross-region questions, not counts; our sheets are small.
- Moves: plans. Why this group: second source for crops
- Reports: lit-market-b

<a id="i48"></a>
### 48. Warm start a plan detector from the Open-PMC subfigure DAB-DETR

- What: Run the published biomedical subfigure detector zero-shot on 30 two-plan dev sheets, then fine-tune it next to RF-DETR on the same composites and real sheets.
- Evidence (adjacent-field): Weights trained on biomedical panels; no number on plans. Real ImageCLEF mAP 36.88 / F1 73.55 for the model on its own domain.
- Source: [huggingface.co](https://huggingface.co/vector-institute/pmc-18m-dab-detr), [arXiv 2506.02738](https://arxiv.org/abs/2506.02738)
- Licence: code Apache-2.0 / weights Apache-2.0 (card), 43.75M parameters. CubiCasa5K leakage: no.
- Cost: 1 h zero-shot, 2 h fine-tune
- Experiment: Same held-out real sheets as the plan detector; keep whichever gives the better exact plan count.
- What breaks on our images: Trained on photos, micrographs and plots, unframed line art is far off; resizes to 480x480.
- Moves: plans. Why this group: Second detector option; RF-DETR comes first.
- Reports: lit-sheet-b, lit-sheet-c

<a id="i49"></a>
### 49. Classical separator-band recursion as the first plan splitter

- What: Binarise, project per line, keep runs of white lines wider than a threshold, recurse on both halves; use as the cheapest baseline and as a hard-case generator for the detector.
- Evidence (adjacent-field): ImageCLEF 2015 compound-figure separation: band detection 82.2%, edge variant 58.0%, best switch 84.9%; 0.3 s per figure. Fails on borderless panels and dark frames.
- Source: [arXiv 1606.01021](https://arxiv.org/abs/1606.01021)
- Licence: no code; write in numpy. CubiCasa5K leakage: no.
- Cost: 30-60 min work, CPU
- Experiment: Run on dev two-plan sheets; report exact plan count against constant 1; keep its failures as detector training cases.
- What breaks on our images: Plans touching at a stair or arrow, scan borders, stamps and big courtyards break it; XY-cut family fails with noise.
- Moves: plans. Why this group: Measured only on figures; a detector is the main route.
- Reports: lit-sheet-b, lit-sheet-c

<a id="i50"></a>
### 50. Group detected boxes into plans with a learned edge classifier

- What: Take detector boxes as nodes of a complete graph and classify which pairs belong to the same plan with a gated graph network over geometry features.
- Evidence (adjacent-field): Newspaper and historical pages: YOLOv11 boxes plus GNN Rand index 92.5 against 83.9 for YOLO alone on 8,449 pages.
- Source: [arXiv 2503.16664](https://arxiv.org/abs/2503.16664)
- Licence: code MIT; repo incomplete. CubiCasa5K leakage: no.
- Cost: 4 h work, small GPU or CPU
- Experiment: Needs plan-membership labels from the box export; compare with distance grouping on held-out real sheets.
- What breaks on our images: Repo is incomplete; needs re-implementation; no plan membership labels yet.
- Moves: plans. Why this group: Only if plain distance grouping and the detector both stall.
- Reports: lit-sheet-b

## Idea or pitch only

<a id="i51"></a>
### 51. Wall-graph readout from junction and centreline heatmaps for plans per sheet

- What: Peak-pick junctions, chain edges along centreline coverage, take connected components of the wall graph as plan candidates on a sheet.
- Evidence (floor-plans): arXiv 2608.25608: training-free readout beats the autoregressive decoder of the same network by +2.7 wall F1 on CubiCasa5K test (n=296, 256 px); no trained parameter in the readout; walls only.
- Source: [arXiv 2608.25608](https://arxiv.org/html/2608.25608), [github.com](https://github.com/Cyprinus12138/fpvec-lab)
- Licence: code MIT (skv4 converter CC BY-NC), no weights released. CubiCasa5K leakage: yes.
- Cost: 8+ h to train a heatmap net on our dev split (estimate)
- Experiment: Train a small heatmap net on dev walls, compare component count and boxes with a plain wall-mask connected-component baseline on multi-plan sheets.
- What breaks on our images: 256 px input erases thin walls; paper trained on CubiCasa5K; no precedent for splitting sheets.
- Moves: plans. Why this group: Needs a net we do not have; wall-mask components are the cheaper baseline
- Reports: lit-vector-a

<a id="i52"></a>
### 52. One detector per sheet type

- What: Roboflow blog advice: separate detectors per sheet type, tile with overlap, merge at page level, active learning.
- Evidence (authors-claim): Vendor note, no metric.
- Source: [blog.roboflow.com](https://blog.roboflow.com)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: None.
- What breaks on our images: Our images are single-type floor plans.
- Moves: plans. Why this group: Already how we work
- Also (count, search-only): One detector per sheet type. Separate models per type. Evidence: Vendor post: 29 models, no error rate. Source: none. Experiment: Only if one detector underperforms on a sheet style: compare one model against per-style models on dev, exact rate per class.
- Reports: lit-count-a, lit-detect-a

<a id="i53"></a>
### 53. Industry box detector with NMS for floor plan regions (patent)

- What: A granted patent describes a whole-image box detector with confidence thresholding and NMS leaving non-overlapping floor-plan boxes; no accuracy, claims cover keyword-gated detection.
- Evidence (search-only): patent description only.
- Source: [patents.google.com](https://patents.google.com/patent/US12243342B2)
- Licence: patent; not legal advice. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Read the claims before building the same pipeline.
- What breaks on our images: Legal risk to be judged by the owner.
- Moves: plans. Why this group: Shows the shape, nothing to build.
- Reports: lit-sheet-c

## Do not try (with the reason)

<a id="i54"></a>
### 54. Start the plan detector from a document-layout checkpoint

- What: Do not initialise from DocLayNet-family layout weights (DocLayout-YOLO, Docling heron, PP-DocLayout).
- Evidence (adjacent-field): Same ablation, mAP50:95 on drawing sheets: COCO-initialised YOLOv10m 0.772, DocLayout-YOLO architecture with COCO or random init 0.727, with DocLayNet/DocSynth pretraining 0.589. Docling heron and PP-DocLayout train on text documents and report no drawing result.
- Source: [arXiv 2607.18997](https://arxiv.org/abs/2607.18997), [arXiv 2509.11720](https://arxiv.org/abs/2509.11720)
- Licence: mixed; DocLayout-YOLO code AGPL-3.0. CubiCasa5K leakage: unknown.
- Cost: none
- Experiment: Only a 20-sheet probe if wanted; do not train from them.
- What breaks on our images: Domain interference measured on drawings.
- Moves: plans. Why this group: Measured loss of 0.138 from document pretraining.
- Also (data, adjacent-field): Negative: do not start from a document-layout checkpoint. Start symbol detectors from COCO-pretrained DINOv2, not DocLayNet or DiT-style initialisation. Evidence: Engineering drawings: DocLayout-YOLO from DocLayNet and DocSynth weights mAP50:95 0.589 vs 0.755-0.772 for COCO-initialised models (arXiv 2607.18997 Table 4); the comparison also changes architecture, so treat as a warning. Source: [arXiv 2607.18997](https://arxiv.org/abs/2607.18997). Experiment: None.
- Reports: lit-data-a, lit-data-c, lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i55"></a>
### 55. Train the plan detector on composites only

- What: Do not rely on composites alone for the plan detector.
- Evidence (adjacent-field): Open-PMC-18M: 98.58 mAP synthetic against 36.88 real; synthetic-only page layout detectors lose 3.6-4.0 F1; synthetic-only engineering-sheet detectors fall far on real sheets.
- Source: [arXiv 2506.02738](https://arxiv.org/abs/2506.02738), [arXiv 2111.06016](https://arxiv.org/abs/2111.06016)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none; use the real multi-plan sheets in training.
- What breaks on our images: Large sim-to-real gap.
- Moves: plans. Why this group: Measured gap says real sheets must be in training.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i56"></a>
### 56. VLM layout grounding for plan boxes

- What: Do not use a grounded VLM (Qwen3-VL-8B LoRA) as the plan finder.
- Evidence (adjacent-field): Qwen3-VL-8B on facade sheets: mAP50 0.758, plan class mAP50:95 0.330, 6.1 s per drawing on an A100.
- Source: [arXiv 2607.18997](https://arxiv.org/abs/2607.18997)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none
- What breaks on our images: Slow and poor on the plan class.
- Moves: plans. Why this group: Measured worse and slower than a box detector.
- Reports: lit-sheet-a

<a id="i57"></a>
### 57. Flatbed multi-photo cropping tools

- What: Do not use background-subtraction scan splitters; they need a uniform bed.
- Evidence (search-only): Tools are GPL-3.0 with no accuracy figures.
- Source: none
- Licence: GPL-3.0. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: A plan sheet has no uniform bed colour.
- Moves: plans. Why this group: Wrong shape and licence.
- Reports: lit-sheet-c
