# Symbols: windows, doors, fixtures

93 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i58"></a>
### 58. Tile at 1.5 tokens per symbol, overlap by one object, never zoom out

- What: Before any VLM call, enlarge each target to about 1.5 visual tokens per side, cut views without zooming out, overlap views by one object, merge duplicates in code.
- Evidence (floor-plans): Floor-plan mosaic recall Gemini 3.8 0.25 to 0.43, Qwen3-VL 0.05 to 0.12, flat for the strongest model (2610.09313 Table 2); tiles below whole image on real floor-plan blocks for two strong models.
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: code MIT / none. CubiCasa5K leakage: n/a.
- Cost: 2-4 h, API cost about 0.016 USD per plan (estimate)
- Experiment: Compare whole image vs tiles with the rule on 20 dev plans for one frontier VLM and one self-hosted 4B; report exact counts.
- What breaks on our images: CAD mosaics not scans; no rotation test; overlaps double-count unless merged.
- Moves: windows-doors. Why this group: Training-free and measured on drawings.
- Reports: lit-vlm-a

<a id="i59"></a>
### 59. Pin the detector release and check the log that pretrained weights loaded

- What: Pin one rfdetr release for the whole run, log the real input resolution, set the effective batch (batch x accumulation) to 16, and time one epoch before planning hours.
- Evidence (adjacent-field): Issue 974: v1.6.4 trained about 2x slower than 1.5.0; issue 1001: possible silent resolution fallback; issue 1052: a claimed 20% gain was a run without pretrained weights; grad_accum_steps default is now 1 (was 4). Release 1.12.1 (2026-11-12) makes bad config values fail early.
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 0.5 h
- Experiment: Time one epoch; confirm pretrained checkpoint loaded; compare logged vs configured resolution.
- What breaks on our images: None.
- Moves: cost. Why this group: a no-weights fine-tune still gives plausible numbers
- Also (detect, authors-claim): Pin rfdetr version and resize with one fixed antialiased filter. Resize pages ourselves with one fixed area/antialiased filter for training and inference and pin the library version; predict() has resized with antialias=False since 1.9.0, thin 1 px strokes may vanish. Evidence: RF-DETR issue 1516: 1.8.3 matches 1.4.2 exactly, 1.10.1 differs; opt-in predict(antialias=...) added in 1.12.0; training worked on one version and failed on the next in two threads; silent fallback to 384 px on unsupported resolutions (issue 1001). Source: [github.com](https://github.com/roboflow/rf-detr/issues/1516). Experiment: Check the actual input resolution and filter in a logged run; A/B antialias on dev.
- Also (sheet, adjacent-field): Check RF-DETR resize mismatch between training and prediction. Make predict() and training use the same antialiased resize; thin line art shows the mismatch most. Evidence: RF-DETR issue 1516 (closed): predict resizes without antialiasing while the default training backend antialiases. Source: [github.com](https://github.com/roboflow/rf-detr/issues/1516). Experiment: Run the same dev images through both resize paths and report the change in count.
- Reports: lit-data-a, lit-data-c, lit-detect-a, lit-detect-b, lit-sheet-a

<a id="i60"></a>
### 60. Window strips: one box per drawn cell, no NMS inside a tile

- What: Keep adjacent identical boxes: rely on one-to-one DETR matching, class-wise NMS with a high IoU or none inside a tile.
- Evidence (adjacent-field): SKU-110K EM-Merger over Soft-IoU AP .413 to .482 and count MAE 24.96 to 23.98 on packed identical boxes; no exact-count rate anywhere.
- Source: [arXiv 1904.00853](https://arxiv.org/abs/1904.00853)
- Licence: SKU-110K code has no licence file. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Dev subset of 3-pane strips: counts under NMS vs none.
- What breaks on our images: 
- Moves: windows-doors. Why this group: Directly affects window counts
- Also (count, adjacent-field): Set-NMS or EM-merger for adjacent identical objects. Replace greedy NMS with one that keeps overlapping neighbours. Evidence: SKU-110K MAE 14.5, CARPK 6.77 (CVPR 2019/2020); StarDist names box NMS suppression of touching objects. Source: none. Experiment: Sweep NMS IoU per class on dev predictions with window strips watched; try Set-NMS only if the sweep cannot keep adjacent cells.
- Also (detect, our-idea): Split the window class by context. Try exterior-wall window vs strip window as separate classes only if recall for one type is low. Evidence: Music analogue only (noteheads on line / in space). Source: none. Experiment: Per-class recall.
- Reports: lit-count-b, lit-detect-b, lit-detect-c

<a id="i61"></a>
### 61. D-FINE S/M fine-tuned at 960-1280 px from the COCO-only checkpoint

- What: Train D-FINE S or M on the same COCO file as RF-DETR, through the Apache-2.0 D-FINE-seg harness or the transformers port, at 960-1280 px, from plain COCO weights; smoke-test 200 images first (loss falls and AP is non-zero) and check category ids start at 0.
- Evidence (adjacent-field): RF100-VL AP_S 36.6 (S), 36.0 (M) vs RF-DETR 34.2/35.8 (Table 4, written by the RF-DETR authors, probably Objects365-pretrained rows); COCO AP_S 29.1/33.2/36.5 (S/M/L); on 2.8-4.4k dense-line document tables D-FINE-X reached TEDS 92 where YOLO reached 49-75. Open issues report failed small-set fine-tunes (sub 5% mAP).
- Source: [arXiv 2410.13842](https://arxiv.org/abs/2410.13842), [github.com](https://github.com/Peterande/D-FINE), [github.com](https://github.com/ArgoHA/D-FINE-seg), [arXiv 2607.00734](https://arxiv.org/abs/2607.00734)
- Licence: code Apache-2.0 / COCO weights Apache-2.0 (Objects365 checkpoints carry a README caveat). CubiCasa5K leakage: no.
- Cost: est. 1-3 GPU-h on the 12 GB card for 15-25 epochs (S at 1024 px, about 6-7 min per epoch, estimate); 2 h work
- Experiment: Same dev slice and metrics as RF-DETR; run two seeds, log loss curves; compare exact-count rate per class and where the two disagree.
- What breaks on our images: Stride-8 map still coarse for 5 px symbols; repo default 640 and stretch-to-square; reports of non-convergence and seed instability on small sets; official recipe is 220 epochs (does not fit the budget).
- Moves: windows-doors. Why this group: Second detector with the finer feature map and a free disagreement signal for the second count
- Also (data, adjacent-field): D-FINE as the second detector on the same COCO export. Fine-tune D-FINE S or M (Apache-2.0) on the same export as RF-DETR and keep whichever counts better; use the COCO checkpoints rather than the Objects365 ones. Evidence: RF100-VL small-object AP 32.4 / 36.6 for D-FINE N/S against 30.1 / 34.2 for RF-DETR N/S (arXiv 2511.09554 Table 4, written by the RF-DETR authors). Open reports of failed custom fine-tunes (issues 214, 169, 343). Source: [arXiv 2410.13842](https://arxiv.org/abs/2410.13842), [github.com](https://github.com/Peterande/D-FINE). Experiment: Same dev export, same tiles; compare per-class exact count against RF-DETR.
- Reports: lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c

<a id="i62"></a>
### 62. Detect symbols with the wall lines left in (do not erase lines first)

- What: Do not add a line-removal stage before the detector; train on lines-in images.
- Evidence (adjacent-field): Music: removal buys nothing (mAP 80%, 'minimal impact', Pacha et al. 2018); OMR TISMIR 2024 says raw-input CNNs make multi-step designs obsolete. Staff-line removal itself is competitive only on clean binary images (grayscale F 82.85 for the best classical vs 98.9+ learned).
- Source: [arXiv 1801.07141](https://arxiv.org/abs/1801.07141), [arXiv 1709.06476](https://arxiv.org/abs/1709.06476)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0 h (decision)
- Experiment: None; check by a 20-plan A/B only if line removal is ever proposed.
- What breaks on our images: Window panes are lines in the wall; erasing lines erases the symbol.
- Moves: none. Why this group: Free decision aligned with measured field result
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i63"></a>
### 63. Look-alikes as explicit classes

- What: Train door-without-leaf and screens as classes.
- Evidence (adjacent-field): PairTally: counters conflate look-alikes (arXiv 2509.13939); CountEx negative prompts MAE 32.22 to 26.67.
- Source: [arXiv 2509.13939](https://arxiv.org/abs/2509.13939), [arXiv 2602.19432](https://arxiv.org/abs/2602.19432)
- Licence: CountEx no licence. CubiCasa5K leakage: no.
- Cost: none
- Experiment: On dev predictions: confusion between window and door, door and door-without-leaf, tray and screen; exact rate with and without the negative classes.
- What breaks on our images: Needs enough negative boxes (door-without-leaf has about 1.8k).
- Moves: windows-doors. Why this group: Already in export.
- Reports: lit-count-a, lit-count-b, lit-count-c

<a id="i64"></a>
### 64. Ordered output with an explicit end and empty-class tiles

- What: Sort items in reading order, one record each, an explicit end token, and include empty-class tiles in training.
- Evidence (adjacent-field): Ordered points 86.3 vs unordered 74.1 (Molmo Table 4); MolmoPoint uses a no-more-points class (2603.28069); FINER shows more hallucination on absent objects (2603.17662).
- Source: [arXiv 2409.17146](https://arxiv.org/abs/2409.17146), [arXiv 2603.28069](https://arxiv.org/abs/2603.28069), [arXiv 2603.17662](https://arxiv.org/abs/2603.17662)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: none beyond data build
- Experiment: Report false positives on zero-count tiles separately.
- What breaks on our images: Sauna stove rare.
- Moves: fixtures. Why this group: Free format choice.
- Reports: lit-vlm-b, lit-vlm-c

<a id="i65"></a>
### 65. Florence-2 LoRA or full fine-tune as tile symbol detector

- What: Fine-tune Florence-2-base on 384-512 px tiles cut from dev boxes with 25% overlap, set no_repeat_ngram_size=0, merge boxes with NMS in our code.
- Evidence (adjacent-field): LoRA 2,818 augmented images: mAP50 0.80 / mAP50-95 0.57 vs YOLOv8/9 0.84 / 0.56-0.58 (2503.04918); 400 drawings F1 61.51 vs GPT-4o 35.51 (2411.03707).
- Source: [arXiv 2503.04918](https://arxiv.org/abs/2503.04918), [arXiv 2411.03707](https://arxiv.org/abs/2411.03707)
- Licence: code and weights MIT. CubiCasa5K leakage: no.
- Cost: 3-5 h to first number, 6-10 h for 10 epochs on 16 GB (estimate)
- Experiment: Train LoRA and full fine-tune on dev tiles, score box recall and exact counts vs the detector from the floor-plan scope on the same dev tiles.
- What breaks on our images: 32 px per token at 768 px; 45 chars per box so under 40 boxes per tile; localises worse than detectors.
- Moves: windows-doors. Why this group: Cheap small-model detector arm.
- Reports: lit-vlm-b

<a id="i66"></a>
### 66. Evaluate a trained checkpoint at 1.5-2.5x its training pixels, no retraining

- What: Take the fine-tuned RF-DETR and run it at 1.6x the side (positional embeddings are interpolated) on dev before spending a training run on higher resolution.
- Evidence (adjacent-field): RF-DETR-L trained at 704 and run frozen at 1120: AP 0.3272 to 0.3654, AP_S 0.0519 to 0.0660, better than fine-tuning at 1120 (0.3470), rectangular 1280x736 worse (0.3057); one run per setting, hidden aggregate (arXiv 2608.03136).
- Source: [arXiv 2608.03136](https://arxiv.org/abs/2608.03136)
- Licence: n/a (recipe). CubiCasa5K leakage: no.
- Cost: about 1 GPU-h of inference
- Experiment: Score the same checkpoint at 1.0, 1.25, 1.6, 2.0x, per-class exact-count rate and AP_S.
- What breaks on our images: One dataset, confounded thresholds; AP gains can hide count flips; not shown for drawings.
- Moves: windows-doors. Why this group: Free test-time sweep once a checkpoint exists
- Reports: lit-detect-a, lit-detect-b, lit-detect-c

<a id="i67"></a>
### 67. Small VLM writes points in reading order, code counts them

- What: LoRA a Qwen3-VL-2B/4B on tiles of dev plans to write one point or box per window, door and fixture in reading order; count the list in code and ignore any number the model writes.
- Evidence (adjacent-field): Real photos 1-10 objects: Qwen2.5-VL-3B 70.00 to 81.90; synthetic out-of-range counts 30.86 own count vs 80.20 count of points (2603.21746 Tables 1-2); Molmo Table 4 86.3 vs 80.2. Not line art.
- Source: [arXiv 2603.21746](https://arxiv.org/abs/2603.21746), [arXiv 2409.17146](https://arxiv.org/abs/2409.17146)
- Licence: code MIT (paper repo) / Qwen3-VL Apache-2.0. CubiCasa5K leakage: no.
- Cost: 4-8 h work, 4-8 GPU-h on 12-16 GB (estimate)
- Experiment: Tile dev plans 2x2 with overlap, enlarge 2-3x, train on dev-split boxes only, score exact count per class against the 55.3% majority baseline and 59.3% count-only network.
- What breaks on our images: 10 px symbol is 0.3 of a 32 px token; touching lines hurt VLMs; loops above 40-50 instances; rotated third.
- Moves: windows-doors. Why this group: Only entry that tests whether a small VLM can count on our boxes.
- Also (count, adjacent-field): Fine-tune a small VLM to point at every instance, then count the points. LoRA-train a 2B-class VLM on box centres from the dev boxes with a no-more-points stop, count the emitted points in code. Evidence: Exact match on real 1-10 objects: 69.1-73.6% direct, 76.2-81.9% point-then-count over three models; falls to 0.98-25.9% beyond the trained range (arXiv 2603.21746). MolmoPoint design: stop class, no double pointing (vendor blog). Source: [arXiv 2603.21746](https://arxiv.org/abs/2603.21746). Experiment: Only if the detector fails: train on dev centres over the full 0-40 range, exact-count per class vs detector.
- Also (vlm, adjacent-field): Molmo2-4B as pointing baseline. Zero-shot and LoRA Molmo2-4B pointing for symbols as an alternative to Qwen3-VL. Evidence: PixMo-Count 88.1 vs Qwen3-VL-4B 58.0 (2601.10611 Table 6). Source: [arXiv 2601.10611](https://arxiv.org/abs/2601.10611). Experiment: Zero-shot point counts on 20 dev plans.
- Also (vlm, adjacent-field): Select image tokens instead of writing coordinates. Use grounding-token pointing for tiny targets. Evidence: +5 ScreenSpot-Pro over text coordinates, same data (2603.28069). Source: [arXiv 2603.28069](https://arxiv.org/abs/2603.28069). Experiment: Compare with text points.
- Reports: lit-count-a, lit-vlm-b, lit-vlm-c

<a id="i68"></a>
### 68. RF-DETR S/M fine-tuned on dev boxes at about 1024 px, rot90 and flips as augmentation

- What: Fine-tune RF-DETR Small and Medium from the COCO checkpoint on the dev boxes (window, door, door without leaf, toilet, sink, shower, bathtub, sauna stove), resolution a multiple of 32 set in the constructor, batch_size auto, gradient checkpointing if memory is short. Read counts from detections above a tuned threshold, not from AP.
- Evidence (adjacent-field): RF100-VL (100 small fine-tune sets) AP_S 34.2 (S), 35.8 (M), 36.9 (L) against 4.7-7.3 for YOLO rows (arXiv 2511.09554 Table 4); drawings: 0.949 mAP50 on 551 facade sheets (large layout objects only), railway drawings F1 0.923 with tiles. No paper reports exact counts or fixture AP from a box detector on floor-plan rasters.
- Source: [arXiv 2511.09554](https://arxiv.org/abs/2511.09554), [github.com](https://github.com/roboflow/rf-detr), [arXiv 2607.18997](https://arxiv.org/abs/2607.18997)
- Licence: code Apache-2.0 / weights Apache-2.0 (N-L only; Objects365 pretraining terms an open question). CubiCasa5K leakage: no.
- Cost: est. 2-3 h to convert to COCO plus 1.5-3 GPU-h on the 16 GB card for 15-20 epochs at 1024 px (estimate, no measured throughput; one source suggests 40-100 min)
- Experiment: Train on dev, hold out a dev slice; score per-class AP50 and exact-count rate per class, upright and rotated sheets separately, at 1024 px and one larger size. Settles detector, input size and whether tiling is needed.
- What breaks on our images: Stride-16 single feature map: a 10 px symbol is under one patch at default size; maintainers say DETRs are weak on small objects; squashes non-square sheets; library versions changed behaviour between releases (pin one).
- Moves: windows-doors. Why this group: Fastest route to a first number; rotation augmentation is a config entry; best documented recipe
- Also (data, adjacent-field): RF-DETR with DINOv2 backbone, fine-tuned on our own boxes as the real-only base detector. Fine-tune an Apache-2.0 size (N, S, M or L) with its DINOv2-initialised backbone on the dev boxes, tiled or at 704+ px, and check in the log that the pretrained weights loaded. Every synthetic or augmentation arm is compared against this run. Evidence: DINOv2 init: COCO APS 35.8 vs 32.3 for a CAE backbone (arXiv 2511.09554 Table 6). 551 real facade drawings at 1344x800: mAP50 0.949 but recall only 0.800 at confidence 0.25 (arXiv 2607.18997 Table 2). 1,042 training images: mAP50 0.881 vs 0.623 for the best YOLO (arXiv 2512.22454). None is on 5-20 px symbols. Source: [arXiv 2511.09554](https://arxiv.org/abs/2511.09554), [arXiv 2607.18997](https://arxiv.org/abs/2607.18997), [arXiv 2512.22454](https://arxiv.org/abs/2512.22454), [github.com](https://github.com/roboflow/rf-detr). Experiment: Train real-only on dev tiles with default augmentation plus rot90 and flip; read per-class exact-count rate on dev. This is the control for every other arm.
- Also (floorplan, adjacent-field): RF-DETR (Nano to Large) fine-tuned on our boxes. Fine-tune an Apache RF-DETR on our ~104k symbol boxes with rot90 and vertical flips; evaluate the EMA checkpoint; counts come from our rules. Evidence: No floor-plan number. COCO AP50:95 54.7 (M, 576 px), RF100-VL 61.2 (README table, re-checked). Source: [github.com](https://github.com/roboflow/rf-detr), [arXiv 2511.09554](https://arxiv.org/abs/2511.09554). Experiment: Train on dev only; report exact / within 1 / MAE per class by rotated, small, photographed subgroup; beat 59.3% count-only network and PlanQ floor.
- Reports: lit-data-a, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c

<a id="i69"></a>
### 69. Exact rot90 and flip augmentation on the dev boxes

- What: Train with the eight rotations and mirrors through RF-DETR's Albumentations wrapper (RandomRotate90 is handled with boxes); box labels stay valid, no repair step needed.
- Evidence (adjacent-field): RandomRotate90 is listed among the box-aware transforms in the RF-DETR source; no paper ablates rotation for box detection on plans (searched twice). Transcoda-style and scene-text results show a missing rotation axis makes the model fail on it (Multi-Oriented 87.8 to 34.3, arXiv 2602.06450 Table 6).
- Source: [github.com](https://github.com/roboflow/rf-detr), [arXiv 2602.06450](https://arxiv.org/abs/2602.06450)
- Licence: Albumentations 2.0.8 MIT (not the AGPL fork AlbumentationsX). CubiCasa5K leakage: no.
- Cost: 0.5 h config
- Experiment: Same run with and without; read dev exact count per class on a rotated and an upright slice.
- What breaks on our images: Only needs the rfdetr augment extra and an aug_config dict; arbitrary-angle rotation would blur 5-20 px lines, so use exact multiples only.
- Moves: windows-doors. Why this group: free, matches how sheets arrive
- Also (detect, search-only): Eight-fold rotation and mirror augmentation instead of an oriented head. Train with RandomRotate90 plus flips (D4) so rotated sheets keep axis-aligned boxes; in RF-DETR set the augmentation backend to albumentations explicitly; D-FINE-seg has rotate_90 and up_down_flip config lines; stock D-FINE needs a custom transform. Check one batch visually. Evidence: No paper compares rot90 augmentation with an oriented head on drawings; library support read from source (RF-DETR transforms contain RandomRotate90/VerticalFlip; D-FINE-seg default 0.0). Oriented detectors are for non-90 angles. Source: [github.com](https://github.com/roboflow/rf-detr), [github.com](https://github.com/ArgoHA/D-FINE-seg). Experiment: Dev ablation: with and without D4, scored separately on upright and rotated sheets.
- Also (sheet, adjacent-field): Train detectors with all eight rotations and mirrors. Train the symbol and plan detectors with D4 augmentation so orientation need not be estimated for detection. Evidence: Sheets are rotated by exact multiples of 90 degrees so axis-aligned boxes stay valid; RF-DETR accepts D4 through the optional albumentations extra; the original floor-plan network used 90-degree rotations and four-rotation test averaging. Source: [arXiv 1904.01920](https://arxiv.org/abs/1904.01920). Experiment: Report exact count per class on upright and rotated dev images separately.
- Also (vlm, adjacent-field): Augment rotations and position coverage. Train on 90/180 rotations and varied symbol positions to avoid blind zones. Evidence: Blind-zone augmentation 59.45 to 61.47 on ScreenSpot-Pro (2609.32036). Source: [arXiv 2609.32036](https://arxiv.org/abs/2609.32036). Experiment: Per-orientation exact counts.
- Reports: lit-data-b, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c, lit-sheet-a, lit-sheet-b, lit-sheet-c, lit-vlm-c

<a id="i70"></a>
### 70. Give each symbol about 1.5 visual tokens: upsample, overlap, never zoom out

- What: Before any VLM call, compute symbol side in tokens; upsample until it is about 1.5, split into overlapping views, merge duplicates.
- Evidence (adjacent-field): Shi et al.: recall 0.62 to 0.90 (Gemini 3.8) and 0.37 to 0.56 (Qwen3-VL) on legend symbols; GPT-6.1 no gain on floor-plan mosaics; clean-image threshold 0.3 to 0.8 tokens per side.
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313), [github.com](https://github.com/shijunzhe/vlm-small-objects)
- Licence: code MIT; FloorPlanCAD-derived data non-commercial. CubiCasa5K leakage: n/a.
- Cost: 3 h, no GPU (estimate)
- Experiment: Apply the planner to the door/window VLM call on dev; keep if exact count improves by 5 points.
- What breaks on our images: Their targets are exemplars; ours are named classes in small images.
- Moves: windows-doors. Why this group: cheapest lever, no training
- Reports: lit-market-b

<a id="i71"></a>
### 71. Zero-shot dense probe with Falcon Perception 0.6B

- What: Run Falcon Perception on 10 dev plans with prompts door, window, toilet, sink and compare counts with gold.
- Evidence (authors-claim): Dense mask F1 72.3 to 80.5 on the authors' benchmark (model card); no drawing result.
- Source: [arXiv 2608.18881](https://arxiv.org/abs/2608.18881), [arXiv 2603.27365](https://arxiv.org/abs/2603.27365)
- Licence: code Apache-2.0 / weights Apache-2.0. CubiCasa5K leakage: unknown.
- Cost: 1 GPU-h (estimate); needs CUDA, no ROCm path
- Experiment: Count per class on 10 dev plans; exact counts on 20-30% of plans without training earns a place, else drop.
- What breaks on our images: Natural-image data; no training code; 5-20 px line symbols.
- Moves: windows-doors. Why this group: One hour answers whether native 16 px patches see our symbols.
- Reports: lit-vlm-b

<a id="i72"></a>
### 72. RF-DETR Medium at 640-704 next to Small at 1024

- What: Test a larger model at modest resolution against a smaller model at high resolution; maintainers advise a larger size before raising resolution because the sizes are searched jointly; avoid Nano.
- Evidence (authors-claim): RF-DETR issues 747 and 958 (Nano fell by more than half on small objects).
- Source: [github.com](https://github.com/roboflow/rf-detr/issues/747)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 GPU-h
- Experiment: S at 1024 vs M at 640-704 on dev, exact-count rate.
- What breaks on our images: Maintainer opinion.
- Moves: windows-doors. Why this group: Settles the tonight choice
- Reports: lit-detect-b, lit-detect-c

<a id="i73"></a>
### 73. Train the vision tower, not only the language LoRA

- What: Make the ViT trainable (own lr) in the point-list fine-tune.
- Evidence (authors-claim): Third-party 2B LoRA box accuracy 0.74 to 0.87 with ViT unfrozen (repo README, reported); VLM4VLA 2601.03309 control task.
- Source: [arXiv 2601.03309](https://arxiv.org/abs/2601.03309), [github.com](https://github.com/Rise-S/Qwen3VL-Smart_Car_Searching)
- Licence: repo no licence. CubiCasa5K leakage: n/a.
- Cost: about 1.4x training time (estimate)
- Experiment: A/B on dev tiles: frozen vs unfrozen tower.
- What breaks on our images: Memory on 12-16 GB.
- Moves: windows-doors. Why this group: Cheap A/B inside experiment 1.
- Reports: lit-vlm-b

<a id="i74"></a>
### 74. Train door and door-without-leaf as separate classes

- What: Keep the count rule in the JSON stage: detect the two door types as separate classes and count only doors with a leaf.
- Evidence (our-idea): Door-without-leaf 1.8k in the export; music field split noteheads by context (InSpace/OnLine).
- Source: none
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: Per-class exact-count rate for both door classes.
- What breaks on our images: Look-alike classes confuse (USB vs double sockets 43 AP).
- Moves: windows-doors. Why this group: Matches the counting rule
- Reports: lit-detect-b, lit-detect-c

## Try next

<a id="i75"></a>
### 75. Read the 2019 model's opening heatmaps instead of polygons

- What: Test whether raw heatmaps beat polygon output for counts; polygon step loses much IoU.
- Evidence (floor-plans): Raw window 66.8 door 53.6 vs polygon 40.9/41.2 (Table 6, re-checked).
- Source: [arXiv 1904.01920](https://arxiv.org/abs/1904.01920)
- Licence: CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 3 h
- Experiment: Dev counts from heatmaps vs polygons.
- What breaks on our images: Leaked weights: dev only.
- Moves: windows-doors. Why this group: existing weights, cheap
- Reports: lit-floorplan-a

<a id="i76"></a>
### 76. Depiction jitter: line-weight, blur, down-up scaling and JPEG on training images

- What: Randomise stroke thickening or thinning (dilate or erode 1-2 px), blur, down-up scaling to 0.5-1.0 of native, JPEG 40-92 and exact rot90 on training images, boxes untouched. Aimed at the loss Carrara isolates inside object regions.
- Evidence (floor-plans): Clean-trained detector AP50 0.881: mild blur 0.877, strong blur 0.619, thickening mild 0.624 / medium 0.253 / strong 0.091 (author repository tables, CubiCasa5K test). Scan-trained window+door AP 0.522 vs clean-trained 0.807 on the clean test; AP75 loses far more than AP50. The mitigation arms have no result table published.
- Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness)
- Licence: code MIT; the authors' trained weights and result bundles non-commercial. CubiCasa5K leakage: yes.
- Cost: 1-2 h loader work, one run (estimate)
- Experiment: Real-only run with and without jitter; then synthetic supplement with and without jitter. Read the AP75-AP50 gap and per-class exact count on dev. Expect no gain inside the original-scan distribution; the point is no harm and insurance for other drawing styles.
- What breaks on our images: All numbers are on the same dataset family; effect on phone photos is unmeasured; the dev images are already the scan depiction.
- Moves: windows-doors. Why this group: aimed at the one measured failure, but real-only dev already sits in the scanned regime
- Also (data, floor-plans): Add a stroke-thickening (dilation) operation to the degradation stack. Dilate lines by 1-2 px before blur, position-preserving, because the generator's registered degradation list has only thinning ops (line breakup, ink bleed, low ink). A few lines of OpenCV plus the same registration check. Evidence: Thickening is the most damaging single factor for a clean-trained detector: AP50 0.881 to 0.624 / 0.253 / 0.091 at mild / medium / strong (Carrara repository tables). fpgen degrade.py read in full: no thickening op. Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness), [github.com](https://github.com/Cyprinus12138/fpvec-lab). Experiment: Train a clean-render model with and without dilation jitter and test on real dev images; read AP50 and AP75 per class.
- Also (data, adjacent-field): Randomise line weights at render time, before degradation. In any generator, draw wall, symbol and dimension line widths from wide ranges (a 2.6-4.5x spread) before applying blur and noise, instead of only degrading afterwards. Evidence: Transcoda appendix: staff width U(0.10,0.26), stem U(0.10,0.36), bar line U(0.16,0.72), page scale integer 52-84; removing the visual degradation stack cost +11.19 NED on real scans. No single-parameter ablation in the paper. Source: [arXiv 2605.10835](https://arxiv.org/abs/2605.10835). Experiment: Generator with one fixed weight vs randomised weights, tested on real dev crops.
- Reports: lit-data-a, lit-data-c

<a id="i77"></a>
### 77. Negative (empty) patches in tile training

- What: Include about one third empty patches in tiled training and drop empty images only on multi-GPU.
- Evidence (floor-plans): Railway drawings: about 39% negative patches; D-FINE/RT-DETR multi-GPU training hangs on batches with no ground truth when denoising is on.
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0.5 h
- Experiment: Dev ablation of negative share if tiling is used.
- What breaks on our images: Tiling only.
- Moves: windows-doors. Why this group: Part of the tiling recipe
- Also (data, adjacent-field): Add empty cluttered tiles as hard negatives at a fixed ratio. When training on tiles, add empty tiles 1:1 with labelled ones, picked from tiles with more than 15% black pixels (clutter), to cut false positives on look-alike shapes. Evidence: Construction diagrams: 59,136 patches, 1,633 with a symbol; 1:1 empty patches; mAP@0.5 79% (YOLOv7) and 83% (Faster R-CNN), 95.6-95.8% of 665 symbols found (Jamieson, IJDAR 2025). PCB tiles: positive share 33.6% / 26.7% (arXiv 2605.24726). Source: [arXiv 2605.24726](https://arxiv.org/abs/2605.24726). Experiment: Tile training with 0, 0.5, 1.0 empty-tile ratio on dev; read false-positive duplicates and exact count.
- Reports: lit-data-b, lit-detect-b, lit-detect-c

<a id="i78"></a>
### 78. RandomShift: translate training content up to the patch stride

- What: Translate training images by up to +-16 px (RF-DETR patch) or the coarsest stride (D-FINE) so every residue modulo the patch grid is seen.
- Evidence (floor-plans): Box AP 0.6630 to 0.6882 on railway drawings, three seeds sd 0.002 (Sensors 2026 Table); effect on small objects. Related: confidence flips with patch grid shifts (RF-DETR issue 1599).
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/)
- Licence: n/a (augmentation). CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Dev ablation with and without shift; count stability under 1-pixel image shifts.
- What breaks on our images: Not measured for detection-only RF-DETR (their model had patch 12); D-FINE analogue untested.
- Moves: windows-doors. Why this group: Cheap, measured gain on drawings, targets count stability
- Reports: lit-detect-b

<a id="i79"></a>
### 79. DEIM matching schedule on D-FINE as a convergence helper

- What: If the D-FINE run converges slowly, use the DEIM recipe (dense one-to-one matching with mosaic and mixup) on the same COCO file; make mosaic a dev ablation, not a default.
- Evidence (adjacent-field): COCO AP_S gain +2.1 at 24 epochs (mosaic+mixup 52.5 AP vs 51.7), D-FINE rows gain AP_S at every size (M 33.2 to 35.3); CrowdHuman D-FINE-L AP_S 29.0 to 33.2. Authors concede a YOLO still has +1.4 AP_S over D-FINE-L. Measured on COCO only.
- Source: [arXiv 2412.04234](https://arxiv.org/abs/2412.04234), [github.com](https://github.com/Intellindust-AI-Lab/DEIM)
- Licence: code Apache-2.0 (LICENSE file; GitHub shows NOASSERTION) / uses D-FINE weights. CubiCasa5K leakage: no.
- Cost: est. same as D-FINE, fewer epochs
- Experiment: D-FINE vs DEIM-D-FINE on the dev slice at equal epochs; one run with mosaic on and one off.
- What breaks on our images: Same fine-tuning risks as D-FINE; repo last pushed 2026-03; mosaic can hurt tiny context-bound symbols.
- Moves: windows-doors. Why this group: Only worth it if plain D-FINE is slow or unstable
- Reports: lit-detect-a, lit-detect-c

<a id="i80"></a>
### 80. Keep mosaic low or off for 5-20 px symbols

- What: Default D-FINE-seg mosaic is 0.8; make it a dev ablation and keep IoU-crop and zoom-out off since they change symbol scale.
- Evidence (adjacent-field): Map signs paper turned mosaic off because targets are small; DEIM's mosaic gain was on COCO only; RF-DETR maintainer: mosaic would work but is not in the repo.
- Source: [arXiv 2610.13224](https://arxiv.org/abs/2610.13224)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: With vs without mosaic on dev.
- What breaks on our images: Mosaic raised COCO AP_S by 2.1.
- Moves: windows-doors. Why this group: Conflicting evidence
- Reports: lit-detect-a, lit-detect-b, lit-detect-c

<a id="i81"></a>
### 81. Two models: plan finder at low resolution, symbol detector on native crops

- What: Find plans at 512-576 px, crop at native scale, then detect symbols per crop; keep the two as separate models.
- Evidence (adjacent-field): RF-DETR default sizes 384-704 are fine for big plan boxes and too small for 5-20 px symbols; the multi-unit floor-plan paper says cropping the plan first generally improves accuracy; a maps-and-forms study shows exact match collapsing with whole-sheet input (0%, 12%, 65-67%) but not with a crop (84-86%).
- Source: [arXiv 2408.01526](https://arxiv.org/abs/2408.01526)
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 3 h work
- Experiment: Exact count per class on multi-plan sheets, whole-sheet against per-plan crops.
- What breaks on our images: A crop smaller than the sheet needs upscaling; crop errors propagate.
- Moves: windows-doors. Why this group: Follows from the plan detector and fixes crop resolution.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i82"></a>
### 82. Tiled inference with a count-safe merge rule

- What: Slice with overlap and merge boxes; choose the merge metric and threshold on dev counts, not defaults.
- Evidence (adjacent-field): SAHI defaults GREEDYNMM, IOS, 0.5 (source read); tiles at 768/384 (door model), 1000/0.2 (MEP paper, mAP50 0.985 private data); a practitioner says tiling with dedup failed for doors.
- Source: [github.com](https://github.com/obss/sahi)
- Licence: code MIT. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: Dev counts with IOS vs IoU merge and thresholds 0.3-0.7; pick by exact rate on windows and doors.
- What breaks on our images: IOS merges two tightly packed windows; a door cut by a tile edge counts twice under a wrong rule.
- Moves: windows-doors. Why this group: only if the upscaled single pass is not enough
- Also (count, adjacent-field): SAHI-style sliced inference for small symbols. Slice at 1024 px with 200 px overlap, merge with NMS 0.5. Evidence: CountGD++ infer_sahi; albatross study: SAHI helped zero-shot a lot but double counted. Source: [github.com](https://github.com/niki-amini-naieni/CountGDPlusPlus). Experiment: Compare against full sheet on dev.
- Also (detect, adjacent-field): SAHI sliced inference for the large sheets only. For sheets beyond trainable size, slice at 20% overlap and merge per page; train on crops at the same scale. Use NMS with intersection-over-smaller (not the default greedy merge). Evidence: SAHI AP50-small +4.7 on VisDrone (inference only); drawing precedents use 700-1500 px slices at 20-50% overlap (P&ID card 1280 px, lighting symbols mAP50 0.985, P&ID patches 1500 px); no with/without slicing ablation on floor plans; slicing lost to a higher single pass in two studies. Source: [arXiv 2202.06934](https://arxiv.org/abs/2202.06934), [github.com](https://github.com/obss/sahi). Experiment: Only on sheets above the trainable size on dev; compare to a single 1536 px pass by exact-count rate.
- Also (market, adjacent-field): SAHI sliced inference and sliced fine-tuning. Slice upsampled images into overlapping tiles, run any non-AGPL detector per tile, merge with NMS and a full-image pass for large objects. Evidence: SAHI abstract: +6.8%, +5.1%, +5.3% AP; with sliced fine-tuning +12.7%, +13.4%, +14.5%; 25% overlap up to +1.7 AP. Source: [arXiv 2202.06934](https://arxiv.org/abs/2202.06934), [github.com](https://github.com/obss/sahi). Experiment: Count error on dev with and without slicing; keep if exact window count improves.
- Also (vector, adjacent-field): Tiling is the norm for small symbols on big sheets. Detect on overlapping tiles and merge, as in P&ID and electrical plans, when symbols are small against the sheet. Evidence: SynthPID, Relationformer (512 px patches of 4500x7000), electrical-plan study (6000-7500 px sheets tiled for symbols), Digitize-PID (400 px patches). Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513), [arXiv 2411.13929](https://arxiv.org/abs/2411.13929). Experiment: Compare whole-image vs tiled detection on large or multi-plan sheets in dev.
- Reports: lit-count-b, lit-count-c, lit-detect-a, lit-detect-b, lit-detect-c, lit-floorplan-a, lit-floorplan-b, lit-market-b, lit-market-c, lit-vector-a, lit-vector-b

<a id="i83"></a>
### 83. BlueprintParse-R50 for toilet, sink, bathtub, gas range

- What: Run the ONNX model on dev images as a smoke test for sanitary classes.
- Evidence (authors-claim): Test mAP50-95 0.926, AP50 0.9805; 53 novel drawings 0.7875; per-drawing exact 0.566 (CI 0.434-0.698) (card, re-checked); own claims, 0 downloads.
- Source: [huggingface.co](https://huggingface.co/ThakiCloud/BlueprintParse-R50)
- Licence: code Apache-2.0 / weights Apache-2.0 (training data not redistributable). CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Dev counts per class; never scored sealed eval.
- What breaks on our images: Korean style; no shower or sauna stove; never enlarges input; legal footing for shipping is Bogdan's call.
- Moves: fixtures. Why this group: only permissive non-CubiCasa sanitary checkpoint
- Reports: lit-floorplan-b

<a id="i84"></a>
### 84. RF-DETR multi_scale and expanded_scales off

- What: Test turning off scale jitter: plans vary 10x in scale but a fixed pixel size per plan style may help.
- Evidence (authors-claim): Vendor docs: off shortens epoch time by up to 40%, fine for most small-dataset fine-tunes.
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0.5 GPU-h
- Experiment: On/off on dev.
- What breaks on our images: Vendor claim.
- Moves: cost. Why this group: Cheap speed lever
- Reports: lit-detect-b

<a id="i85"></a>
### 85. Door-only RF-DETR-S checkpoint with tiled inference

- What: Run the Apache weights on dev as a first door number; do not ship the AGPL runner.
- Evidence (search-only): No metric on the card; trained on two Roboflow sets (1,497 and 402 images, CC BY 4.0, source unstated).
- Source: [huggingface.co](https://huggingface.co/kiyo07/floorplan-door-detector-rfdetr)
- Licence: weights Apache-2.0 / runner AGPL-3.0. CubiCasa5K leakage: unknown.
- Cost: 2 h
- Experiment: Dev door exact rate.
- What breaks on our images: Card itself says duplicates, split double doors, merged openings.
- Moves: windows-doors. Why this group: unvetted data origin
- Reports: lit-floorplan-a, lit-floorplan-b

## Later

<a id="i86"></a>
### 86. Give open models candidate boxes, not free coordinates

- What: Have models choose among detector candidates.
- Evidence (floor-plans): Free localisation 8-10% vs categorical 62% (2608.00473).
- Source: [arXiv 2608.00473](https://arxiv.org/abs/2608.00473)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Compare.
- What breaks on our images: n/a
- Moves: trust. Why this group: Design rule.
- Reports: lit-vlm-a

<a id="i87"></a>
### 87. Separate small door/window head after locating the opening

- What: Locate openings first, then classify door vs window with a small second head.
- Evidence (floor-plans): 2608.25608 Section 6.1: opening F1 0.799 when door and window are not told apart, 0.644 with a family heuristic; a 200K-parameter door/window head reaches 0.988 family accuracy. Finding the opening is the hard part.
- Source: [arXiv 2608.25608](https://arxiv.org/html/2608.25608)
- Licence: code MIT, no weights. CubiCasa5K leakage: yes.
- Cost: 3 h
- Experiment: Add a binary head or post-classifier on detected opening boxes in dev; compare per-class counts.
- What breaks on our images: CubiCasa5K-trained; matcher stricter than other tables.
- Moves: windows-doors. Why this group: Cheap architectural hint
- Reports: lit-vector-a

<a id="i88"></a>
### 88. A tiny head for door versus window

- What: Separate 'is there an opening' from 'door or window'; a 200K-parameter head classifies the family at 0.988 accuracy.
- Evidence (floor-plans): fpvec-lab: family accuracy 0.988; opening F1 0.80 when the family is ignored, 0.64 with the family heuristic.
- Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608)
- Licence: code MIT; CubiCasa5K parts non-commercial. CubiCasa5K leakage: yes.
- Cost: 1 day (estimate)
- Experiment: Train the head on our dev boxes and measure class confusion.
- What breaks on our images: Trained on CubiCasa5K.
- Moves: windows-doors. Why this group: cheap and separable
- Reports: lit-market-a, lit-market-b

<a id="i89"></a>
### 89. OpenCV LSD / FastLineDetector as a cheap structural channel

- What: Run createLineSegmentDetector or ximgproc FastLineDetector on each sheet as a line source for plan splitting, orientation and implausibility checks, never as the counter.
- Evidence (floor-plans): Own run on 30 dev PNGs (815 px median): FLD 6.8 ms, LSD 17.4 ms, HoughLinesP 11.7 ms median, 924-1040 segments, 57-64% under 20 px. Segment-statistics regressor over 500 plans: correlation about 0.5 with true counts, exact match below the constant answer.
- Source: [github.com](https://github.com/opencv/opencv)
- Licence: Apache-2.0; lsd.cpp header is OpenCV BSD-style. CubiCasa5K leakage: no.
- Cost: 1 h work, CPU only
- Experiment: Run on dev plans and use segment-soup statistics only to flag a detector count that is implausibly low or high; settle by count of flagged-and-wrong vs flagged-and-right on dev.
- What breaks on our images: Fragmentation of thick or double lines; 21-52% of segments not re-found under blur, noise or half resolution.
- Moves: trust. Why this group: Cheap and permissive, but no count signal alone
- Reports: lit-vector-a, lit-vector-c

<a id="i90"></a>
### 90. Whole sheet plus four overlapping crops in one call

- What: One request with the sheet and four crops.
- Evidence (floor-plans): +12.96 points (2610.19571).
- Source: [arXiv 2610.19571](https://arxiv.org/abs/2610.19571)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: one call
- Experiment: Compare with tile rule.
- What breaks on our images: QA, not counting.
- Moves: windows-doors. Why this group: Cheap.
- Reports: lit-vlm-a

<a id="i91"></a>
### 91. SweepLSD (MIT, one-pass streaming detector) as a cleaner segment soup

- What: Use if a rule layer wants fewer short junk segments with clean licensing.
- Evidence (floor-plans): Own run: 15.2 ms median, 429 segments, 32% under 20 px vs FLD 1040 / 64%; stability under degradation no better than FLD, LSD steadiest (blur kept 0.52 vs 0.65).
- Source: [arXiv 2608.22086](https://arxiv.org/abs/2608.22086)
- Licence: MIT, zero dependencies. CubiCasa5K leakage: no.
- Cost: 1-2 h
- Experiment: Check recall of window and door strokes against dev boxes.
- What breaks on our images: Misses low-contrast structure; single-author preprint.
- Moves: none. Why this group: Smaller output but no accuracy gain
- Reports: lit-vector-b, lit-vector-c

<a id="i92"></a>
### 92. GRPO with exact-count reward on an SFT checkpoint

- What: After the point-list SFT, run GRPO with a Gaussian/range count reward plus point accuracy on 2K samples, with a blank-canvas control.
- Evidence (adjacent-field): REC-RL MAE 5.48 vs SFT 8.63 (2605.16460 Table 1); CrowdVLM-R1 3B MAE 73.67 to 25.16.
- Source: [arXiv 2605.16460](https://arxiv.org/abs/2605.16460), [arXiv 2504.03724](https://arxiv.org/abs/2504.03724), [arXiv 2610.01908](https://arxiv.org/abs/2610.01908)
- Licence: EasyR1, VLM-R1, TRL Apache-2.0. CubiCasa5K leakage: no.
- Cost: 8-12 h, rollouts need memory (estimate)
- Experiment: Reward exact class counts; report gain over SFT and the blank-image control.
- What breaks on our images: Scripts assume 8 GPUs; MAE not exact match.
- Moves: windows-doors. Why this group: Needs an SFT checkpoint first.
- Reports: lit-vlm-b, lit-vlm-c

<a id="i93"></a>
### 93. Deep Sketch Vectorization: line-art centrelines with multi-way junctions

- What: Run the MIT model on 20 dev plans and look only at whether door arcs and window pane lines come out as separate strokes joined to a wall at a junction.
- Evidence (adjacent-field): SIGGRAPH 2024: Chamfer 15,413 vs 28,180 (clean) and 19,279 vs 66,310 (paper texture) at 512 px; junction precision 95.1% recall 90.3% (Table 5). Trained on 63k synthetic sketches, not CAD plans; repo issue #2 reports weak keypoints on technical sketches.
- Source: [github.com](https://github.com/Nauhcnay/Deep-Sketch-Vectorization)
- Licence: code MIT, weights MIT (ndjson dependency GPL-3, replaceable). CubiCasa5K leakage: no.
- Cost: 3 h on 20 dev plans, 8 GB GPU, 5-17 s per 512 px image
- Experiment: On 20 dev plans, hand-check whether arcs and pane lines are separate junction-joined strokes; if not, drop every line-first route.
- What breaks on our images: Hatching, text and furniture come out as strokes; 5-20 px symbols merge; needs a cleanup stage on scans.
- Moves: none. Why this group: Cheap one-afternoon test but not a counter
- Reports: lit-vector-b

<a id="i94"></a>
### 94. Dome-DETR density-driven queries and a stride-4 level on D-FINE

- What: Use as an idea source: a stride-4 level or 2x input plus a density head setting the query count; run only if the query cap bites.
- Evidence (adjacent-field): AI-TOD-V2 (mean object 12.7 px, 24.6 objects per image): Dome-DETR-S 33.3 AP vs D-FINE-S 30.1 (baseline re-implemented with 4 maps); a plain stride-4 level adds only +0.19 to +0.63 AP (SAF-RTDETR, TinyFormer). User runs on small batches got 6+ points below the paper; 120-160 epochs.
- Source: [arXiv 2505.05741](https://arxiv.org/abs/2505.05741), [github.com](https://github.com/RicePasteM/Dome-DETR)
- Licence: code Apache-2.0 / weights academic research only. CubiCasa5K leakage: no.
- Cost: est. 4-6 h incl. port; epochs not affordable
- Experiment: Skip unless exact-count shows misses at stride 8.
- What breaks on our images: Not reproduced on small batches; weights aerial; 7-15x D-FINE-S compute.
- Moves: windows-doors. Why this group: Idea source only
- Reports: lit-detect-a, lit-detect-b, lit-detect-c

<a id="i95"></a>
### 95. EdgeDrawing / ELSED as permissive classical line sources

- What: Use ximgproc EdgeDrawing detectLines or ELSED if FLD is too noisy; keep arcs to our own fitting on line chains.
- Evidence (adjacent-field): EdgeDrawing returns lines, circles and ellipses only, no partial arcs (header read). On trade-directory pages ELSED F 87.0, EDLines 87.4, Hough 64.8, original LSD 12.5 (default settings vary greatly).
- Source: [arXiv 2305.16968](https://arxiv.org/abs/2305.16968), [github.com](https://github.com/opencv/opencv_contrib)
- Licence: Apache-2.0 (opencv_contrib, ELSED); ED_Lib MIT. CubiCasa5K leakage: no.
- Cost: 1 h incl. build
- Experiment: Compare segment soup (share under 20 px, count) with FLD and LSD on 30 dev plans.
- What breaks on our images: Fragmentation of thick strokes; pyelsed needs CMake.
- Moves: none. Why this group: Fallback line source
- Reports: lit-vector-a, lit-vector-c

<a id="i96"></a>
### 96. Fourier-domain mixing, 90-degree rotation and an auxiliary mask head

- What: Swap low-frequency content between clean and degraded images, rotate by 90 and 180 degrees, and add a segmentation head.
- Evidence (adjacent-field): MIDOG: best teams used an auxiliary segmentation task; best single F1 0.748 against 0.698 baseline; per-scanner spread 0.43 to 0.85.
- Source: [arXiv 2204.03742](https://arxiv.org/abs/2204.03742)
- Licence: data CC BY-NC-ND. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Train with and without and report exact rate per source type.
- What breaks on our images: Colour mixing does not change geometry or line width.
- Moves: windows-doors. Why this group: cheap augmentations
- Reports: lit-market-c

<a id="i97"></a>
### 97. Fine-tune HAWPv3 or LINEA on our wall lines

- What: Train a line or wall detector on wall labels derived from room polygon edges. LINEA is the better documented trainer; HAWPv3 installs without the AGPL package.
- Evidence (adjacent-field): HAWP v2 Wireframe sAP10 69.7; LINEA sAP10 65.0-67.9 at 3.9-25.2M params; HAWPv3 about 12M params (47 MB); GLSP-style typed lines reach msAP32 94.2 but with 268k private plans.
- Source: [arXiv 2210.12971](https://arxiv.org/abs/2210.12971), [arXiv 2505.16264](https://arxiv.org/abs/2505.16264), [arXiv 2303.03851](https://arxiv.org/abs/2303.03851)
- Licence: HAWP code MIT, weights licence unstated; LINEA code Apache-2.0, weights licence unstated. CubiCasa5K leakage: no.
- Cost: 6-10 h incl. wall label export, one 12 GB GPU (estimate)
- Experiment: Fine-tune on the dev split, score wall F1; only worth it if plan splitting or room outlines need walls.
- What breaks on our images: No tiling (resize to 512); LINEA NaN loss at 1280 px; square input only; wall labels not exported yet.
- Moves: plans. Why this group: Only useful for walls, not counts
- Reports: lit-vector-a, lit-vector-c

<a id="i98"></a>
### 98. Plain-word field and class names in the JSON target

- What: Use words such as window, toilet, unreadable instead of codes in the VLM target, add an explicit refusal value.
- Evidence (adjacent-field): Word encoding 87.5% vs 85.8% exact, 2.3x fewer silent errors (2611.17169, text task).
- Source: [arXiv 2611.17169](https://arxiv.org/abs/2611.17169)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Compare formats on dev with silent-error rate.
- What breaks on our images: Not a vision task.
- Moves: trust. Why this group: Small effect.
- Reports: lit-vlm-b

<a id="i99"></a>
### 99. RF-DETR query count and tile object cap

- What: Keep tiles under the 300 pretrained queries; if a dense tile needs more, raise num_queries and num_select together and fine-tune.
- Evidence (adjacent-field): Maintainer says pretrained count 300, lower works, raising not useful (issue 669); docs FAQ says both can be raised with untrained added rows; matcher exhausts memory with about 500 boxes per image (issue 472).
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 0.5 h
- Experiment: Test one dense dev sheet at 300 vs raised queries.
- What breaks on our images: Conflicting maintainer and docs statements.
- Moves: windows-doors. Why this group: our sheets carry tens of boxes
- Also (sheet, adjacent-field): RF-DETR 300-query cap is harmless for plans, binding for symbols. Leave num_queries at 300 for plan boxes (at most 4 per sheet); raise num_queries and num_select together only for dense symbol detection. Evidence: Repo FAQ: default 300 objects per image; raising costs quadratic compute. Source: [github.com](https://github.com/roboflow/rf-detr). Experiment: Count max detections per dev plan before raising it.
- Reports: lit-data-a, lit-data-c, lit-sheet-a, lit-sheet-c

<a id="i100"></a>
### 100. RT-DETRv2 as a fallback detector

- What: Fall back to RT-DETRv2 (Apache-2.0, transformers port) if the other two fail; train at the size it will run at because the card warns that reshaping degrades it.
- Evidence (adjacent-field): RF100-VL RT-DETR-M AP 59.6, AP_S 36.4 (RF-DETR paper Table 4); COCO AP_S 30.2/32.0/36.1/35.8 appear only in another paper and DEIM's table disagrees for S. Transformers loss bug fixed in v5.21 and later.
- Source: [arXiv 2511.09554](https://arxiv.org/abs/2511.09554), [github.com](https://github.com/lyuwenyu/RT-DETR)
- Licence: code Apache-2.0 / weights Apache-2.0 (HF card). CubiCasa5K leakage: no.
- Cost: est. like D-FINE-M
- Experiment: Only if needed: same dev protocol, transformers pinned at v5.21 or newer.
- What breaks on our images: Stride-8 map, lower AP than D-FINE at equal size; open small-object issues with no answer; exploding grad norms reported on a community notebook.
- Moves: windows-doors. Why this group: Dominated by D-FINE and RF-DETR on the evidence
- Reports: lit-detect-a, lit-detect-c

<a id="i101"></a>
### 101. SAM 3 open-vocabulary counting

- What: Concept segmentation with an exhaustivity verifier.
- Evidence (adjacent-field): CountBench 93.8, verifier +7.2 cgF1 (2511.16719).
- Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719)
- Licence: SAM License (not OSI). CubiCasa5K leakage: unknown.
- Cost: unknown
- Experiment: Probe on 10 plans.
- What breaks on our images: Licence.
- Moves: windows-doors. Why this group: Licence first.
- Reports: lit-vlm-a

<a id="i102"></a>
### 102. Stride-4 (P2) feature level for tiny symbols

- What: Faster R-CNN with FPN is the only permissive detector with a stride-4 level; otherwise upscale the input.
- Evidence (adjacent-field): Plain stride-4 level adds +0.19 AP / +0.58 AP_S on a ViT DETR (TinyFormer Table 4); raw early features bypassing the ViT give more; measured nowhere on drawings; torchvision smallest anchor 32 px.
- Source: [arXiv 2605.25046](https://arxiv.org/abs/2605.25046)
- Licence: torchvision BSD-3. CubiCasa5K leakage: no.
- Cost: est. 3 h with custom anchors 8-64
- Experiment: Only as fallback if DETRs miss 5 px symbols.
- What breaks on our images: Needs custom anchors; older family.
- Moves: windows-doors. Why this group: Fallback only
- Reports: lit-detect-b, lit-detect-c

<a id="i103"></a>
### 103. Tiling recipe: 50% overlap, border-weighted confidence, containment merge

- What: For large sheets cut tiles with 50% overlap, down-weight boxes near a tile border (confidence minus up to 0.4), then NMS at high IoU and weighted box fusion at lower IoU; merge by containment.
- Evidence (adjacent-field): P&ID papers: 1500x1500 patches on a 4500x7000 resize, stride 750; 2000 px patches fell stitched AP from 87.48 to 76.74 when symbols crossed edges; tile merge on drawings F1 0.9226 with containment.
- Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513), [arXiv 2411.13929](https://arxiv.org/abs/2411.13929)
- Licence: SAHI MIT. CubiCasa5K leakage: no.
- Cost: 3 h work
- Experiment: Exact count per class on the few large dev sheets, tiles against one full pass at the same resolution.
- What breaks on our images: Symbols crossing a tile edge are the weak point.
- Moves: windows-doors. Why this group: Only for sheets too large for one pass.
- Reports: lit-sheet-a

<a id="i104"></a>
### 104. Stroke and blur curriculum fine-tune

- What: Short low-learning-rate fine-tune on stroke-dilated and blurred copies.
- Evidence (authors-claim): Recipe T1-T4 (400 layouts, 2 epochs, lr 1e-5) in the repo; no results published.
- Source: [github.com](https://github.com/andreacar/floorplan-detection-scan-robustness)
- Licence: code MIT. CubiCasa5K leakage: yes.
- Cost: 1 h
- Experiment: Compare before and after on degraded dev.
- What breaks on our images: Untested.
- Moves: windows-doors. Why this group: no measured gain
- Reports: lit-floorplan-a

<a id="i105"></a>
### 105. Keep a box only in the tile that contains its centre

- What: With tile overlap larger than the biggest symbol, keep a detection only in the tile holding its centre point instead of IoU merging.
- Evidence (our-idea): No paper tests this on drawings; argued as simpler than any IoU merge for symbols cut by a tile edge.
- Source: none
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Compare against containment merge on large dev sheets by exact-count rate.
- What breaks on our images: Untested; symbols larger than overlap break it.
- Moves: windows-doors. Why this group: Cheap alternative to merge rules
- Reports: lit-detect-a

<a id="i106"></a>
### 106. Multi-zoom inference merged

- What: Run at several zoom factors and merge instead of tiling.
- Evidence (search-only): Practitioner: dramatic gain, no figure (anecdote).
- Source: [andrey-koleda.medium.com](https://andrey-koleda.medium.com/how-i-built-a-computer-vision-system-that-understands-doors-on-floor-plans-ec3dbf0e29c7)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Compare with tiles on dev.
- What breaks on our images: No numbers.
- Moves: windows-doors. Why this group: anecdote
- Reports: lit-floorplan-a

<a id="i107"></a>
### 107. Find bathrooms then detect fixtures on tiles

- What: First detect wet rooms, then run a tile-trained fixture detector on each crop.
- Evidence (search-only): No accuracy in the README.
- Source: [github.com](https://github.com/AsfTS/floorplan-acc)
- Licence: MIT / n/a. CubiCasa5K leakage: unknown.
- Cost: 1 day
- Experiment: Fixture AP on dev.
- What breaks on our images: YOLO used (AGPL), so idea only.
- Moves: fixtures. Why this group: unmeasured
- Reports: lit-floorplan-b

## Idea or pitch only

<a id="i108"></a>
### 108. Pixel segmentation plus post-processing held up on scans

- What: Consider a segmentation route with post-processing as an alternative detector on scans.
- Evidence (floor-plans): arXiv 2408.01526: pixel F1 0.86-0.90 on CVC-FP, walls 0.95; CubiCasa subset door F1 0.82, window 0.90 vs 0.68-0.69 and 0.81 for the original CubiCasa5K network. Not per-object; no code seen.
- Source: [arXiv 2408.01526](https://arxiv.org/abs/2408.01526)
- Licence: no code. CubiCasa5K leakage: unknown.
- Cost: n/a
- Experiment: None.
- What breaks on our images: Pixel not object metric; CVC-FP split unknown.
- Moves: none. Why this group: Context for the Zernike collapse
- Reports: lit-vector-c

<a id="i109"></a>
### 109. RT-DETR-L floor-plan recipe at 1024 px

- What: Reproduce the 60-epoch 1024 px recipe with an Apache RT-DETR or RF-DETR on our boxes.
- Evidence (floor-plans): Test door AP50 89.8 / window 89.3, AP[.5:.95] 57.5/62.2, 4,200 plans (README, re-checked); 1536 px retrain same AP50.
- Source: [github.com](https://github.com/OldDeLorean/rtdetr-floorplan-detector)
- Licence: no licence file, AGPL stack / weights unlicensed. CubiCasa5K leakage: yes.
- Cost: 2.3 h on 2 GPUs (claim); 2-4 h ours (estimate)
- Experiment: Same as rf-detr experiment.
- What breaks on our images: Flips only; densely furnished and rendered styles warned; discrepancy with scan-shift AP50.
- Moves: windows-doors. Why this group: recipe only, checkpoint is AGPL and leaked
- Reports: lit-floorplan-a, lit-floorplan-b

<a id="i110"></a>
### 110. Second-stage reclassifier on detected crops with domain adaptation

- What: Reclassify detected crops (sink versus shower) with a contrastive encoder trained on clean reference glyphs plus a domain-adversarial loss on unlabelled dev crops.
- Evidence (adjacent-field): Encrypted manuscripts: P@1 zero-shot ResNet-50 0.130, glyph-trained 0.457, full method 0.595; frozen DINOv2-base 0.222 (arXiv 2609.07159 Tables 1 and 2). Classification, not detection; 14 pages.
- Source: [arXiv 2609.07159](https://arxiv.org/abs/2609.07159)
- Licence: no code link found; paper CC BY 4.0. CubiCasa5K leakage: n/a.
- Cost: 3 h
- Experiment: Crop classifier on dev with and without adaptation; per-class confusion.
- What breaks on our images: Unlabelled target pages only from dev; eval images must stay out.
- Moves: fixtures. Why this group: second stage after a first detector
- Reports: lit-data-a

<a id="i111"></a>
### 111. Sub-pixel keypoint heatmaps for rectangular CAD symbols

- What: Use heatmap key points with a local offset for rectangle-like symbols on large raster drawings.
- Evidence (adjacent-field): Pang et al. (2404.10985): keypoint F1 0.79 vs 0.76 soft-argmax and 0.78 RLE; offset lifts average F1 0.77 to 0.79; own telecom equipment-room images, no doors or windows.
- Source: [arXiv 2404.10985](https://arxiv.org/abs/2404.10985)
- Licence: not stated. CubiCasa5K leakage: no.
- Cost: 8 h (estimate)
- Experiment: None.
- What breaks on our images: Other domain; small gain.
- Moves: none. Why this group: No floor-plan evidence
- Reports: lit-vector-a, lit-vector-c

<a id="i112"></a>
### 112. Self-supervised pretraining on unlabelled drawings

- What: Pretrain a backbone with masked-autoencoder style training on unlabelled dev images (and other permitted drawings), then fine-tune the detector. No paper measures this for plan detection.
- Evidence (adjacent-field): Music: FCMAE on about 200,000 unlabelled real scans, two epochs, OMR-NED to 60.70 from 65.76 (Transcoda Table 3b). Floor-plan contrastive encoder includes CubiCasa5K in its training (arXiv 2609.12723). Line-drawing pretraining on STL-10 sketches: VOC mAP 18.17 to 22.16 at 10% data (arXiv 2508.06696), no code.
- Source: [arXiv 2605.10835](https://arxiv.org/abs/2605.10835), [arXiv 2508.06696](https://arxiv.org/abs/2508.06696), [arXiv 2609.12723](https://arxiv.org/abs/2609.12723)
- Licence: FCMAE code licence not checked; MAE repo is CC BY-NC. CubiCasa5K leakage: unknown.
- Cost: 4+ h (estimate)
- Experiment: Pretrain on dev plus the Floor Plan CIS plans, fine-tune, compare with COCO-DINOv2 start on dev.
- What breaks on our images: Dev images are CubiCasa5K, so an encoder trained on them is not leakage-free for the eval images; no code to reuse; 5-20 px symbols.
- Moves: windows-doors. Why this group: no measurement on plans, little time
- Also (data, search-only): Negative: MAE reference code for self-supervised pretraining. Do not use the original MAE repository for in-house pretraining. Evidence: facebookresearch/mae repository licence is CC BY-NC 4.0. Source: [github.com](https://github.com/facebookresearch/mae). Experiment: None.
- Reports: lit-data-a, lit-data-c

<a id="i113"></a>
### 113. Assign unused queries to unmatched targets

- What: During training give unmatched objects an unused query.
- Evidence (adjacent-field): AgriCountDINO.
- Source: [arXiv 2609.29460](https://arxiv.org/abs/2609.29460)
- Licence: idea only. CubiCasa5K leakage: unknown.
- Cost: unestimated
- Experiment: If a detector is trained in-house: ablate an extra query for unmatched ground truth, recall on dense strips.
- What breaks on our images: Needs a training loop we may not control; plants, not line art.
- Moves: windows-doors. Why this group: Unproven.
- Reports: lit-count-a

<a id="i114"></a>
### 114. MolScribe recipe: image to graph with coordinates, synthetic renders plus rotation and noise

- What: Predict elements with coordinates as tokens then build the structure with rules; train on rendered pages with rotation, padding, cropping and noise.
- Evidence (adjacent-field): MolScribe exact match 92.6 USPTO, 86.9 Staker; abbreviations expanded from a closed table (same pattern as decoding room labels through a fixed Finnish table).
- Source: [arXiv 2205.14311](https://arxiv.org/abs/2205.14311), [github.com](https://github.com/thomas0809/MolScribe)
- Licence: code MIT, weights MIT. CubiCasa5K leakage: no.
- Cost: 20 h feasibility port (estimate)
- Experiment: None directly; borrow the rotation and noise augmentation set for the detector.
- What breaks on our images: 384 px input erases 5-20 px symbols; one molecule per image; 55,482 s per epoch on 8 GPUs.
- Moves: none. Why this group: Recipe only; model unusable at our symbol size
- Reports: lit-vector-b

<a id="i115"></a>
### 115. Cut the image along lines that avoid objects

- What: Route cut lines around detected objects so none is split and counted twice.
- Evidence (adjacent-field): LVLM-Count: MAE 25.57 to 17.86 (GPT-4o) on FSC-147; code Apache-2.0.
- Source: [arXiv 2412.00686](https://arxiv.org/abs/2412.00686)
- Licence: code Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Useful only on large sheets; test duplicate rate against overlap-and-merge.
- What breaks on our images: Needs the objects found first.
- Moves: windows-doors. Why this group: ours fit one view
- Reports: lit-market-b

<a id="i116"></a>
### 116. Point-map head with hard-negative patches

- What: Peak extraction from a point map and hard-negative rounds.
- Evidence (adjacent-field): HerdNet F1 73.6, MAE 6.1 vs Faster R-CNN 15.2 (ISPRS 2023).
- Source: [github.com](https://github.com/Alexandre-Delplanque/HerdNet)
- Licence: code MIT / weights CC BY-NC-SA. CubiCasa5K leakage: no.
- Cost: one day
- Experiment: Borrow only the hard-negative round: mine false-positive patches from the first detector's stitched predictions and retrain once; compare false-positive count on dev.
- What breaks on our images: Animals are filled blobs; a window is a few strokes; no per-instance box for size or leaf rules.
- Moves: windows-doors. Why this group: Detector first.
- Reports: lit-count-b

<a id="i117"></a>
### 117. Fine-tune SAM 3 with a frozen backbone or LoRA

- What: Fine-tune only the decoder (about 32.7M trainable) or LoRA rank 8 on dev boxes.
- Evidence (adjacent-field): Roboflow-100VL document-like group 12.9 AP zero-shot, 35.8 at 10-shot, 64.2 full fine-tune (arXiv 2511.16719, Table 36); Count Anything LoRA MAE 9.34 vs 25.80 plain SAM 3 on CLOC (arXiv 2605.30846); users report OOM and resolution locked at 1008 (repo issues).
- Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719), [arXiv 2605.30846](https://arxiv.org/abs/2605.30846)
- Licence: SAM License; Count Anything code Apache-2.0. CubiCasa5K leakage: unknown.
- Cost: 6-10 h (estimate); 12 GB unproven
- Experiment: Only if SAM 3 is licence-cleared and the detector fails.
- What breaks on our images: Training uses 8 GPUs in the paper.
- Moves: windows-doors. Why this group: Licence and memory.
- Reports: lit-count-b, lit-count-c

<a id="i118"></a>
### 118. SFT then RL with a checkable count reward on a small VLM

- What: Fine-tune a 4B VLM, then reinforce with format and exact-count rewards.
- Evidence (adjacent-field): MechVL: total 60.23 to 84.85, counting subtask 62.79 to 88.37 (about 43 items); authors confirmed 287 of 562 benchmark drawings overlap the training pool.
- Source: [arXiv 2605.30794](https://arxiv.org/abs/2605.30794)
- Licence: code Apache-2.0, paper CC BY 4.0. CubiCasa5K leakage: n/a.
- Cost: days on a larger GPU (estimate)
- Experiment: Not before a detector baseline exists.
- What breaks on our images: Frozen vision encoder may lose 5 to 20 px symbols; numbers inflated by overlap.
- Moves: windows-doors. Why this group: upper bound only
- Reports: lit-market-b

<a id="i119"></a>
### 119. Primitive DETR trained on synthetic lines, circles and arcs

- What: Train a detector purely on generated line, circle and arc images and apply it to plans for door-leaf evidence.
- Evidence (adjacent-field): arXiv 2403.08721: mAP 0.722; AP_line 0.764, AP_circle 0.917, AP_arc 0.483 on 303 real diagrams; LETR zero-shot line AP 0.263.
- Source: [arXiv 2403.08721](https://arxiv.org/abs/2403.08721)
- Licence: code not released. CubiCasa5K leakage: no.
- Cost: 8+ h to build (estimate)
- Experiment: Build the generator and score arc AP on dev door boxes.
- What breaks on our images: Arc is the weakest class; code not released.
- Moves: none. Why this group: Research bet
- Reports: lit-vector-b

<a id="i120"></a>
### 120. Training-free counterfactual scaling of frozen detectors (CQTR)

- What: Apply counterfactual scale interventions to a frozen DETR and use decoder query trajectories to pick candidates; calibrate once on about 100 unlabelled images.
- Evidence (adjacent-field): AP and AP_S rise in all 27 combinations of nine frozen detectors (incl. D-FINE-S, DEIM-D-FINE-S) over COCO, TinyPerson, VisDrone (arXiv 2609.06581, abstract level); no drawings.
- Source: [arXiv 2609.06581](https://arxiv.org/abs/2609.06581)
- Licence: no code link seen. CubiCasa5K leakage: no.
- Cost: unknown
- Experiment: Only after the baseline fine-tune; compare to the plain resolution sweep.
- What breaks on our images: No code, COCO-style metrics only.
- Moves: windows-doors. Why this group: Second route to frozen-weight gain, nothing to run yet
- Reports: lit-detect-a, lit-detect-b

<a id="i121"></a>
### 121. Use our counting rules as the verifier for rejection sampling

- What: Sample several answers, keep those that the counting rules certify against gold counts, distil into a small VLM with LoRA.
- Evidence (adjacent-field): K-OPSD: Qwen3-VL-4B 0.738 combined accuracy on AECV-Bench, tie with the best zero-shot; 121 training prompts; cost and verifier agreement not reported.
- Source: [arXiv 2609.34082](https://arxiv.org/abs/2609.34082)
- Licence: no code found. CubiCasa5K leakage: unknown.
- Cost: 2 days, one GPU (estimate)
- Experiment: Rejection-sample on dev plans and measure exact count of a 4B model.
- What breaks on our images: Tiny evaluation split, text QA dominates.
- Moves: windows-doors. Why this group: cost not reported
- Reports: lit-market-b

<a id="i122"></a>
### 122. Zoom family: AdaGround, DeepEyes, Mini-o3

- What: Training-free adaptive zoom with Yes/No verifier on a marked point.
- Evidence (adjacent-field): 8B 51.3 to 66.2, fixed 4x crop already 63.5 (2610.36874).
- Source: [arXiv 2610.36874](https://arxiv.org/abs/2610.36874), [arXiv 2505.14362](https://arxiv.org/abs/2505.14362), [arXiv 2509.07969](https://arxiv.org/abs/2509.07969)
- Licence: MIT / Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: about 10 calls
- Experiment: Cheap fixed crop first.
- What breaks on our images: Locates one target.
- Moves: windows-doors. Why this group: Fixed crop gets most gain.
- Reports: lit-vlm-a, lit-vlm-c

<a id="i123"></a>
### 123. Count by tile only where candidates exist

- What: Cheap coarse pass proposes wall-adjacent regions, high-resolution read only there.
- Evidence (authors-claim): Localisation tolerates 3-4x token compression (2609.19745); abstract only.
- Source: [arXiv 2609.19745](https://arxiv.org/abs/2609.19745)
- Licence: unknown. CubiCasa5K leakage: n/a.
- Cost: unknown
- Experiment: Token cost vs exact count.
- What breaks on our images: Natural images.
- Moves: cost. Why this group: Abstract-level.
- Reports: lit-vlm-b

## Do not try (with the reason)

<a id="i124"></a>
### 124. Community floor-plan detector checkpoints

- What: Do not start from RT-DETR-L floor-plan repo, MuraNet, DoorDet, 2DPlan2Strct, rtdetrv2-floorplan, SamirShabani/Architect or the scan-shift checkpoints; use their published numbers as references only.
- Evidence (floor-plans): Door/window AP50 89.8/89.3 (1024 px, 60 epochs, 2xA100, 2.3 h) and 91.2/92.2 (MuraNet, 1536 px, 1000 epochs, 10 GPUs); all trained on the leaky dataset or unnamed data.
- Source: [arXiv 2309.00348](https://arxiv.org/abs/2309.00348), [arXiv 2606.10953](https://arxiv.org/abs/2606.10953)
- Licence: no licence / non-commercial / AGPL base. CubiCasa5K leakage: yes.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Leakage and licence.
- Moves: none. Why this group: Leakage
- Also (ocr, floor-plans): Do not use published floor-plan text checkpoints that saw CubiCasa5K. The 2022 and 2026 floor-plan text detectors and recognisers were trained on CubiCasa5K plans; their checkpoints are unreleased and leaky. Evidence: Training sets: 399 CubiCasa5K plus 122 CVC-FP; 1,000 plans from CubiCasa5K and CVC-FP. Source: [iopscience.iop.org](https://iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017). Experiment: None.
- Also (scale, floor-plans): Do not reuse OCR weights trained on CubiCasa5K and CVC-FP. Weights from EC3 2026, floorplan2bim, DoorDet and similar cannot be used for scored runs. Evidence: Stated training data. Source: [ec-3.org](https://ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf). Experiment: none
- Reports: lit-detect-a, lit-detect-c, lit-ocr-a, lit-ocr-c, lit-scale-a, lit-scale-b

<a id="i125"></a>
### 125. Deep Vectorization of Technical Drawings (cleaning network plus patch transformer)

- What: Do not use it for counting. At most idea-only: a learned cleaning step before a detector.
- Evidence (floor-plans): ECCV 2020: line IoU 86/88 on clean plans, 79/82 on 81 real degraded plans vs 47 for the best baseline; text removed beforehand, no symbol class. Cleaning model never released; line checkpoint link dead since 2026-10-12.
- Source: [arXiv 2003.05471](https://arxiv.org/abs/2003.05471)
- Licence: code MPL-2.0 (file-level copyleft), weights none usable. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: None.
- What breaks on our images: No weights exist; output has no class; text removal destroys room labels.
- Moves: none. Why this group: No usable weights, licence needs a ruling, no semantics
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i126"></a>
### 126. Fine-tuned small VLM emitting JSON

- What: Fine-tuned VLMs did not beat detectors on symbols.
- Evidence (floor-plans): MiniCPM LoRA F1 0.105; BOOMI exact program 3.4%; PlanQ tuned VLM 29.9%/26.6%.
- Source: [huggingface.co](https://huggingface.co/Barath/minicpmv4-floorplan-lora)
- Licence: various. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: Cards, not papers.
- Moves: windows-doors. Why this group: low exact counts
- Also (vlm, floor-plans): One-shot full-plan JSON from a small VLM. Do not ask for the whole plan. Evidence: MiniCPM-V-4 F1 0.105 on FloorPlanCAD; JSON about 3,100 tokens. Source: [huggingface.co](https://huggingface.co/Barath/minicpmv4-floorplan-lora), [arXiv 2602.06507](https://arxiv.org/abs/2602.06507). Experiment: None.
- Reports: lit-floorplan-a, lit-floorplan-b, lit-vlm-b, lit-vlm-c

<a id="i127"></a>
### 127. Skip FloorplanVLM, SALI-FP, Raster2Seq weights, VecFormer weights for scored runs

- What: Do not plan around these: FloorplanVLM has no public code or weights, SALI-FP has none, Raster2Seq weights include a CubiCasa5K checkpoint (CC BY-NC), VecFormer weights are lost.
- Evidence (floor-plans): FloorplanVLM opening F1 0.7333 on its own benchmark; Raster2Seq window and door F1 77.8 on CubiCasa5K at 256 px (RoomFormer 78.5); SALI-FP door IoU 0.0396 raw.
- Source: [arXiv 2602.06507](https://arxiv.org/abs/2602.06507), [arXiv 2602.09016](https://arxiv.org/abs/2602.09016), [arXiv 2609.25615](https://arxiv.org/abs/2609.25615)
- Licence: Raster2Seq code MIT, weights CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: Leakage, licence or no weights
- Reports: lit-vector-a, lit-vector-c

<a id="i128"></a>
### 128. A VLM-only plan parser loses on openings

- What: Do not use a VLM-only parser for window and door placement.
- Evidence (floor-plans): SALI-FP Table C.8: window IoU 0.05 to 0.23 against 0.72 for a trained CubiCasa5K model.
- Source: [arXiv 2609.25615](https://arxiv.org/abs/2609.25615)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: windows-doors. Why this group: measured loss
- Reports: lit-market-b

<a id="i129"></a>
### 129. Wasserstein loss term gated to compact boxes

- What: Add an NWD-style term to the box loss for compact boxes.
- Evidence (floor-plans): Box AP 0.6630 to 0.6679 alone on railway drawings; bundle with sampling points and RandomShift 0.7045.
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/)
- Licence: not released. CubiCasa5K leakage: no.
- Cost: 3 h custom loss
- Experiment: Skip.
- What breaks on our images: Tiny gain; custom code in the RF-DETR loss.
- Moves: windows-doors. Why this group: +0.005 AP isn't worth the code
- Also (detect, adjacent-field): NWD and RFLA tiny-box assignment for anchor-based detectors. Gaussian Wasserstein similarity or receptive-field label assignment for tiny boxes. Evidence: AI-TOD: Faster R-CNN 11.1 to 17.8 AP (NWD); DetectoRS 14.8 to 24.8 (RFLA). Helps CNN anchors only. Source: [arXiv 2110.13389](https://arxiv.org/abs/2110.13389), [arXiv 2208.08738](https://arxiv.org/abs/2208.08738). Experiment: Skip.
- Reports: lit-detect-b

<a id="i130"></a>
### 130. Co-DETR as accuracy ceiling

- What: Do not train Co-DETR; use its published numbers as an upper reference only.
- Evidence (floor-plans): DoorDet Co-DETR ViT-L 0.926 mAP50 on ten door types (algorithmic boxes, leaky); needs 2xA100.
- Source: [arXiv 2508.07714](https://arxiv.org/abs/2508.07714)
- Licence: code MIT. CubiCasa5K leakage: yes.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Does not fit 12 GB.
- Moves: none. Why this group: Compute
- Reports: lit-detect-a, lit-detect-c

<a id="i131"></a>
### 131. Split strokes by width (thick walls, thin symbols) inside a matcher

- What: Use a per-segment stroke-width cue only as a filter inside a symbol matcher, not as a predictor.
- Evidence (floor-plans): Own check on 300 dev plans: plan-level width histogram correlation 0.28-0.30 with counts, exact match below constant (0.07 vs 0.167 windows); per-segment version same. Classical DFKI-style recipe splits thick, medium, thin.
- Source: [arXiv 2305.16968](https://arxiv.org/abs/2305.16968)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h
- Experiment: Use as filter in a door-gap matcher on dev; no standalone test.
- What breaks on our images: Most strokes are one width (about 70% at 1.5-2.5 px).
- Moves: none. Why this group: No count signal as a predictor
- Reports: lit-vector-c

<a id="i132"></a>
### 132. Class-agnostic symbol finder trained on synthetic shapes

- What: Do not use a class-agnostic first stage trained on synthetic shapes as a counter.
- Evidence (adjacent-field): Electrical diagrams thesis: recall 0.57-0.88 but precision 0.15-0.26; RT-DETRv2 recall 0.095 on the smallest symbols, 0.757 on the largest (stride argument).
- Source: none
- Licence: n/a (thesis, no code). CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: Not worth a run.
- What breaks on our images: Exact counts need real fine-tuning.
- Moves: none. Why this group: Many false boxes
- Reports: lit-detect-b

<a id="i133"></a>
### 133. No deep line detector has a published result on floor plans, scans or line art

- What: Treat any use of ScaleLSD, DeepLSD, HAWP, M-LSD or LETR on plans as untested. Only off-the-shelf run on binary line art recovers 1.4% of strokes.
- Evidence (adjacent-field): HieroSA Table 1 (glyph bitmaps): DeepLSD stroke coverage 1.4%, invalid strokes 76.2%. ADLA Table 4: ScaleLSD AR 0.539 vs LSD 0.735 on all-line ground truth. GLSP (HAWP variant) works only after training on 268k private plans.
- Source: [arXiv 2601.05508](https://arxiv.org/abs/2601.05508), [arXiv 2508.19742](https://arxiv.org/abs/2508.19742), [arXiv 2303.03851](https://arxiv.org/abs/2303.03851)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: Glyph bitmaps are not plans; metric favours the paper's model.
- Moves: none. Why this group: Recorded so nobody expects a free line-detector win
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i134"></a>
### 134. Pretrained DeepLSD on scanned plans (one positive precedent)

- What: If a line source is wanted, DeepLSD with pre-filtering (grayscale or colour) and post-filtering by detected objects is the only learned line detector with a scan result.
- Evidence (adjacent-field): Electrical plans (7 plans, 6000+ px): precision 0.94, recall 0.95, F1 0.94 with no fine-tuning; cables are long thin lines, not door arcs.
- Source: [arXiv 2212.07766](https://arxiv.org/abs/2212.07766)
- Licence: code and weights MIT; pytlsd AGPL source in default path. CubiCasa5K leakage: no.
- Cost: 2 h (build pain)
- Experiment: Run on 20 dev plans with the learned-only readout and score recall of door and window strokes.
- What breaks on our images: AGPL component in default path; HPatches 271 ms; long-line bias.
- Moves: none. Why this group: AGPL default path; precedent is for long cables
- Reports: lit-vector-a, lit-vector-c

<a id="i135"></a>
### 135. Negative: DINOv3 weights and DINOv3-based detectors

- What: Skip DINOv3, DEIMv2 and similar: custom or non-commercial licences, no drawing evidence.
- Evidence (adjacent-field): DINOv3 licence read in full: limited non-transferable grant, same-terms redistribution, trade-control clause; DEIMv2 non-commercial; frozen 7B + Plain-DETR 66.1 COCO mAP (arXiv 2508.10104) does not fit 12 GB. Frozen general backbones fail on drawings: frozen DINOv2-B 0.757 vs task CNN 0.959 on hatch matching (arXiv 2609.24565).
- Source: [arXiv 2508.10104](https://arxiv.org/abs/2508.10104), [arXiv 2609.24565](https://arxiv.org/abs/2609.24565)
- Licence: custom DINOv3 License; DEIMv2 non-commercial. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: licence not on the allowed list, no drawing result
- Also (detect, authors-claim): DEIMv2, EdgeCrafter, RT-DETRv4, TinyFormer and other DINOv3-based detectors. Do not use detectors built on DINOv3 or with non-commercial licences. Evidence: DEIMv2 LICENSE.md non-commercial for code and weights; DINOv3 under a custom Meta licence; RT-DETRv4 needs a DINOv3 teacher; TinyFormer code not found and paper CC BY-NC-ND. Source: [github.com](https://github.com/Intellindust-AI-Lab/DEIMv2). Experiment: n/a
- Reports: lit-data-a, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c

<a id="i136"></a>
### 136. Negative: domain-adversarial detector adaptation instead of augmentation

- What: Skip: fragile three-step recipe, below the real-scan overlay.
- Evidence (adjacent-field): Music: adversarial adaptation 36.0 to 48.9 AP and source set 87.6 to 72.4, vs 56.5 for scan overlay (TISMIR 2024).
- Source: [doi.org](https://doi.org/10.5334/tismir.157)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: worse than overlay and costs source accuracy
- Reports: lit-data-b

<a id="i137"></a>
### 137. Door-swing arcs by Hough or circle fitting

- What: Do not retry Hough arc detection as a door counter.
- Evidence (adjacent-field): In-house: Hough arcs 2/40 exact doors, canonical template 3/40. Synthetic-trained DETR on astronomical diagrams: AP_arc 0.483 (2403.08721). EdgeDrawing returns no partial arcs. No arXiv paper since 2024 targets door-swing arcs in plans.
- Source: [arXiv 2403.08721](https://arxiv.org/abs/2403.08721)
- Licence: code not released. CubiCasa5K leakage: no.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: Arcs weakest primitive class; scans break edges.
- Moves: none. Why this group: Measured poor and nothing newer
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i138"></a>
### 138. M-LSD / M-LSD-tiny as a CPU line detector

- What: Use as a lightweight line source if CPU-only inference matters.
- Evidence (adjacent-field): Wireframe sAP10 62.1 (tiny 58.0), 115 FPS on V100; users report 300-500 ms per frame on CPU (issues #29, #30), slower than OpenCV LSD at 7-17 ms.
- Source: [arXiv 2106.00186](https://arxiv.org/abs/2106.00186)
- Licence: code Apache-2.0, weights unstated. CubiCasa5K leakage: unknown.
- Cost: 3 h (TensorFlow 2.3 pin)
- Experiment: None.
- What breaks on our images: tensorflow-gpu 2.3 pin; no CPU advantage over classical.
- Moves: none. Why this group: Slower than classical on CPU, no drawing result
- Reports: lit-vector-a, lit-vector-c

<a id="i139"></a>
### 139. RTMDet, YOLOX, mmrotate oriented detectors

- What: Skip: mmdet 3.3 asserts mmcv below 2.2 and is unmaintained; oriented detectors are unnecessary with exact 90-degree rotations.
- Evidence (adjacent-field): RTMDet AP_S 20.4-35.9 (below D-FINE at similar AP); mmrotate last commit 2024-09; no paper compares rot90 with an oriented head.
- Source: [github.com](https://github.com/open-mmlab/mmdetection)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Install risk.
- Moves: none. Why this group: Install risk and weaker AP_S
- Reports: lit-detect-a, lit-detect-c

<a id="i140"></a>
### 140. 11k QA fine-tune for small objects

- What: Little gain.
- Evidence (adjacent-field): +1.2-1.7 (2604.22884).
- Source: [arXiv 2604.22884](https://arxiv.org/abs/2604.22884)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None.
- What breaks on our images: n/a
- Moves: none. Why this group: Weak lever.
- Reports: lit-vlm-c

<a id="i141"></a>
### 141. ROI-gated sliced inference to save time

- What: Do not use ROI gating to skip tiles; accuracy falls.
- Evidence (adjacent-field): COCO128: mAP50 0.6602 against 0.7569 for full SAHI; speed-up only on a sparse three-image case.
- Source: [arXiv 2608.23923](https://arxiv.org/abs/2608.23923)
- Licence: unclear. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none
- What breaks on our images: Lower mAP.
- Moves: cost. Why this group: Counts need every tile.
- Reports: lit-sheet-a

<a id="i142"></a>
### 142. ScaleLSD as line evidence for door leaves and window cells

- What: Run the v2 checkpoint zero-shot at lowered --threshold on tiled or upscaled plans, filter by ink and geometry, and check whether door-leaf and window-cell segments appear.
- Evidence (adjacent-field): CVPR 2025: YorkUrban repeatability 0.725 (HAWPv3 0.711, DeepLSD 0.514); no drawing result. ADLA Table 4: AP 0.8946, AR 0.5389 at default threshold. 512x512 resize drops about two thirds of 6-12 px strokes (FLD proxy: ratio 0.34).
- Source: [arXiv 2506.09369](https://arxiv.org/abs/2506.09369), [github.com](https://github.com/ant-research/scalelsd), [huggingface.co](https://huggingface.co/cherubicxn/scalelsd)
- Licence: code MIT, weights card Apache-2.0 (trained with SA-1B, research-only overview). CubiCasa5K leakage: no.
- Cost: 1-2 h on 100 dev images, 12 GB GPU (estimate)
- Experiment: On 100 dev images at native and 2x size, count segments matching door-leaf and window-cell boxes; keep only if recall of those boxes beats 0.5.
- What breaks on our images: Photo-trained; arcs not modelled; no tiling in the repo; 512 px input erases 5-20 px symbols; pytlsd trap in requirements.
- Moves: none. Why this group: Triage: no drawing result and AGPL-tainted install; reports split between try and skip
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i143"></a>
### 143. ReDHF, BUTR, TinyFormer, SO-DETR and other 2026 tiny-object DETRs

- What: Do not chase these; gains are 1.4-1.6 AP, smaller than the resolution effect.
- Evidence (adjacent-field): ReDHF +1.4 AI-TOD-v2; BUTR 35.7 AP; TinyFormer inherits a non-commercial base; SO-DETR Apache-2.0 but a VMamba stack with compiled CUDA extensions, no weights.
- Source: [arXiv 2611.07994](https://arxiv.org/abs/2611.07994), [arXiv 2610.33430](https://arxiv.org/abs/2610.33430)
- Licence: mixed; TinyFormer NC. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Aerial blobs vs thin lines.
- Moves: none. Why this group: Resolution first
- Reports: lit-detect-a, lit-detect-b, lit-detect-c

<a id="i144"></a>
### 144. Negative: do not train the detector from random initialisation

- What: Always start from pretrained weights.
- Evidence (adjacent-field): Random init matches pretrained on 10k COCO images (25.9 vs 26.0 AP) but 3.5k images gave 16.0 vs 9.3 AP (arXiv 1811.08883). Our 3.8k dev images sit at that edge, with about 27 boxes per image.
- Source: [arXiv 1811.08883](https://arxiv.org/abs/1811.08883)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: Instances matter more than images in that paper.
- Moves: none. Why this group: pretrained start is cheap and safer
- Reports: lit-data-c

<a id="i145"></a>
### 145. YOLO family detectors

Reviewer's note: AGPL: out under decision record 0006.

- What: Do not spend time on YOLO detectors: AGPL/GPL and weak on small-object fine-tunes.
- Evidence (adjacent-field): RF100-VL AP_S 4.7-7.3 vs 34-37 for DETRs (competitor's table, caveated); drawings: RF-DETR-M 0.949 vs YOLOv12-M 0.871 (confounded by input size), 0.881 vs 0.623 substations; SkeySpot YOLOv8 81.1 on 45 plans. Counter-evidence: vanilla RF-DETR-Seg-L trailed YOLO11-seg-L on box AP50 (0.867 vs 0.920) until adapted.
- Source: [arXiv 2511.09554](https://arxiv.org/abs/2511.09554), [arXiv 2508.10449](https://arxiv.org/abs/2508.10449)
- Licence: AGPL-3.0 / GPL-3.0 code, weights follow. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Licence excludes shipping.
- Moves: none. Why this group: Licence
- Also (sheet, authors-claim): YOLO-family sheet and panel detectors (AGPL runtime). Do not use Ultralytics-based detectors or their weights for plan boxes, even where the weights card says Apache-2.0; take only the recipe. Evidence: Reported: a blueprint layout detector gets drawing_area mAP50-95 0.885 on 694 boxes; a mechanical-view detector 0.96 normalised view recall; YOLO12 panel detector mAP50 0.9227. None counts plans. Source: [arXiv 2510.21862](https://arxiv.org/abs/2510.21862), [arXiv 2606.29667](https://arxiv.org/abs/2606.29667). Experiment: none
- Also (vector, authors-claim): Do not use Ultralytics YOLO (AGPL) as the shipped counter. Use permissively licensed detector codebases (RT-DETR, D-FINE, DETR, MMDetection, Co-DETR) instead of YOLOv8, YOLO11 or YOLOv12. Evidence: Licence files read: ultralytics AGPL-3.0; RT-DETR, D-FINE, DETR, MMDetection Apache-2.0; Co-DETR MIT. Most reported detector results (SkeySpot, FlowExtract, SINA, FloorYOLO) use YOLO. Source: [github.com](https://github.com/ultralytics/ultralytics). Experiment: None; check pretrained weight terms before use.
- Reports: lit-detect-a, lit-detect-b, lit-detect-c, lit-sheet-a, lit-sheet-b, lit-sheet-c, lit-vector-a, lit-vector-b, lit-vector-c

<a id="i146"></a>
### 146. Vector symbol spotters (SymPoint, SymPoint-V2, CADSpotting, VecFormer, TempFit, DPSS) cannot take raster input

- What: Do not feed line-detector segments into CAD symbol spotters. Use them only for a vector PDF or DXF route, and only if a licence and weights exist.
- Evidence (adjacent-field): All train and test on true CAD primitives. Ceiling: PQ 94.58 (VecFormer) and 96.53 (TextCAD) on CubiCasa5K converted to primitives vs 60.80 for an image model; on FloorPlanCAD, SymPoint-V2 AP50 71.3 / mAP 60.1 vs 60-64 AP50 for raster detectors. No paper measures a detected-line front end; handcrafted primitive features cost 7 PQ (80.2 vs 87.4, CADSpotting Table 7).
- Source: [arXiv 2505.23395](https://arxiv.org/html/2505.23395v3), [arXiv 2607.12678](https://arxiv.org/abs/2607.12678), [arXiv 2407.01928](https://arxiv.org/abs/2407.01928)
- Licence: VecFormer Apache-2.0, no weights; SymPoint non-commercial; SymPoint-V2 and CADSpotting no licence file; DPSS academic only. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: None on raster. Possible later: if a vector-PDF input path exists, count primitives there and compare.
- What breaks on our images: Training is 8 x A100 for hundreds of epochs; VecFormer weights lost per maintainer.
- Moves: none. Why this group: No path from pixels to typed primitives with a measured loss; unusable licences or weights
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i147"></a>
### 147. Remove wall lines before detecting symbols

- What: Do not remove walls: a window is a gap with panes in the wall.
- Evidence (adjacent-field): Music staff-line removal: mAP 85.12 vs 87.80, big classes unchanged; text removal before detection on single-line diagrams reported without an ablation.
- Source: [arXiv 2409.00316](https://arxiv.org/abs/2409.00316)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Erases the symbol.
- Moves: windows-doors. Why this group: Evidence says it barely helps
- Reports: lit-detect-b

<a id="i148"></a>
### 148. DeepLSD and ScaleLSD install an AGPL line-segment library (pytlsd)

- What: Install ScaleLSD with pip install -e . and the packages setup.py names, not requirements.txt; avoid DeepLSD's default path. Never ship either.
- Evidence (authors-claim): pytlsd repo says MIT but src/lsd.cpp carries the original LSD AGPL header; DeepLSD imports it in its model, ScaleLSD only in a two-view matching demo.
- Source: [github.com](https://github.com/iago-suarez/pytlsd), [github.com](https://github.com/ant-research/scalelsd), [github.com](https://github.com/cvg/DeepLSD)
- Licence: AGPL-3 in pytlsd source; DeepLSD and ScaleLSD code MIT. CubiCasa5K leakage: n/a.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: AGPL network-use terms apply if exposed as a service.
- Moves: none. Why this group: Licence flag for DeepLSD; ScaleLSD usable locally only
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i149"></a>
### 149. RF-DETR XL/2XL and Atto/Femto/Pico

- What: Do not use the plus-package RF-DETR sizes.
- Evidence (authors-claim): Ship under the PML 1.0 licence via rfdetr[plus].
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: PML 1.0. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: n/a
- What breaks on our images: Licence.
- Moves: none. Why this group: Licence
- Reports: lit-detect-a, lit-detect-c

<a id="i150"></a>
### 150. Oriented-box detectors for rotated symbols

- What: Not needed: rotate the image instead.
- Evidence (search-only): RF-DETR has no oriented boxes (issue 921); no study of 90/180 degree plans for counting exists.
- Source: [github.com](https://github.com/roboflow/rf-detr/issues/921)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: n/a
- Moves: none. Why this group: image rotation is simpler
- Reports: lit-floorplan-b
