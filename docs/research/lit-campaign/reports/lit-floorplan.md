# lit-floorplan: floor-plan recognition as a field (scope L1), merged report

Merged from three reports on this scope, called a (papers and measured numbers in our field), b (code, weights, licences,
leakage) and c (adjacent fields). All three read sources on 2026-11-14. Where this file says "re-checked 01:23" I opened the
source again while merging and the quoted number or licence matched; "from a/b/c" means I did not re-open it and the claim
rests on that report. Numbers about our own data come from `docs/research/lit-campaign/worker-brief.md` and
`docs/decisions/0003-training-data.md` (median longest side 855 px, symbols 5 to 20 px, about one image in three rotated, about
104k symbol boxes, 3,828 dev images, 829 of 959 sealed eval drawings in CubiCasa5K's train split, most common answer 55.3%
overall and 13.2% windows / 11.6% doors, CubiCasa authors' 2019 weights 53.1%, count-only network 59.3%).

Marks used below: **read** = the report's author read the number in the paper, repo file or card; **claim** = the authors' own
statement as reported; **summary** = search-engine or abstract-level only.

## 1. Answer

**What does the best published system reach per class on raster plans, and with how much training data?** Nothing published is
in our unit (exact count per plan, per class, on plans like ours). The figures come in five different units and cannot be
compared with each other.

- **Pixel IoU, the CubiCasa5K authors' 2019 network** (ResNet-152 hourglass, 4,200 training plans). Test split, raw masks:
  window 66.8, door 53.6, toilet 62.8, sink 55.7, bathtub 26.7. After their polygon step, which is what a counter would
  use: window 40.9, door 41.2, toilet 56.2, sink 45.5, bathtub 0.0. Re-checked 01:23 in arXiv 1904.01920, Table 6 (two rows,
  raw and polygon). A third party re-running the released weights on the 400 test plans got door/opening 0.618 and window 0.720
  raw (SALI-FP appendix, from b, read).
- **Box AP50, detectors trained on CubiCasa5K.** RT-DETR-L at 1024 px, 4,200 plans, 60 epochs: door 89.8, window 89.3
  (AP[.5:.95] 57.5 / 62.2), re-checked 01:23 in the repo README. A second RT-DETR study on the dataset's own rasters
  (Carrara et al., 1024 px, 4,197 layouts, 100 epochs) gets window 72.2 and door 77.9 AP50, with AP on small objects of 0.106
  (re-checked 01:23 in the committed result JSON for the pooled numbers). Two repos, same dataset family, 12 to 17 points apart,
  so a published AP says little until it is measured on our own boxes. MuraNet (1536 px, custom 4000/500/500 split, 1000 epochs)
  reports door 91.2, window 92.2 (from a and b, read; no code or weights).
- **Opening F1 (doors and windows merged).** Raster2Seq 77.8 at 256 px (5,267 training samples, SIGGRAPH 2026); a Raster2Seq-based
  system 0.848 to 0.849 on a corrected-annotation subset of the test plans (arXiv 2608.25608, re-checked 01:23). Not counts.
- **Exact counts per plan, the nearest to our metric.** One repository (PlanQ-CubiCasa, MIT code). A small U-Net at 512 px plus
  connected components, trained on 2,315 plans: door 64 to 67 of 190 test plans exact (33.7 to 35.3%), window 56 to 63 of 190
  (29.5 to 33.2%) depending on the closing kernel (re-checked 01:23 in `segmentation_count_metrics.json`). A fine-tuned
  vision-language model: door 53/177, window 47/177 (from a and b, read in the per-plan CSVs by a). A prompted general VLM:
  door 40 to 45%, window 47 to 49% (from a, read). The repository's own paired bootstrap finds no significant difference between
  the three readers on doors or windows (p = 0.28, 0.73; from a and b, read). Nobody has reproduced the benchmark. Clean,
  single-floor plans only; its authors state that connected components are "not a substitute for a dedicated detector".
- **Exact counts by prompted VLMs, AECV-Bench** (120 mixed plans): best live door 0.43 and window 0.39 (Gemini 3.5 Flash, from a,
  recomputed from the per-plan CSVs); the paper's own best is Gemini 3 Pro at door 0.39 and window 0.34 (re-checked 01:23). An
  unmerged pull request from a party tied to the prompt it tests claims door 0.55 and window 0.44 (from a, claim).
- **Training data in systems that report per-class results:** 2,200 to 5,300 plans. One tiled detector study got window AP50 75.6
  from 90 plans (Rezvanifar, CVPRW 2020, 224 px tiles; from a, read) and one scanned electrical-plan study got mAP50 81 from 45
  plans (SkeySpot; from a and b, read).

**The "roughly 40-55% exact on door and window counts" line in docs/REQUIREMENTS.md.** It is about vision-language models, not
trained detectors. The AECV-Bench paper says the strongest models "plateau around 0.4-0.55 mean exact-match accuracy" and that
mean covers doors, windows, bedrooms and toilets; its door/window figures are 0.39 and 0.34 for the best model (both re-checked
01:23 in the paper text). So the sentence is not a door/window figure as the paper states it. As a range for the newest prompted
models on clean plans it is fair: live AECV-Bench best 0.43 / 0.39, PlanQ's prompted reader 0.40 to 0.45 / 0.47 to 0.49. It
does not cover scans or photographs. Exact rates also depend on how many symbols a plan holds: prompted models are exact 55 to
73% of the time on plans with at most 5 doors or windows and 6 to 48% on plans with 10 or more (a's binning of AECV-Bench's
per-plan CSVs; PlanQ's prompted reader shows the same pattern, 0.59 to 0.68 at 0 to 5 and 0.04 to 0.13 at 14 and more). Our
brief's plans average about 9 windows, so the headline will be set by the 6 to 13 range.

**Consequences for what we build, as far as the evidence goes.**
1. A trained detector on our boxes is not shown by any source to beat 50% exact, and no source reports a modern detector's exact
   counts on CubiCasa5K. The first measurement that matters is ours, on the dev split, as exact / within one / mean absolute
   error, by subgroup (rotated, small, photographed).
2. Every source that tests off the clean CubiCasa5K distribution loses a lot: the 2019 model gets door IoU 0.099 and window 0.202
   on WAFFLE's internet plans; a model trained on upright plans loses 20 points of window F1 when rotated; a detector trained on
   CubiCasa5K and ResPlan drops from segm AP50 0.90 on its validation set to 0.28 on user-uploaded phone photos. So the third
   of our images that are rotated, scanned or photographed is where the risk sits.
3. Zero-shot VLMs find symbols poorly (object F1 below 0.07 for frontier models on construction sheets, per the vendor benchmark
   in the table) and cannot see 5 to 20 px symbols at whole-page resolution (they need a symbol of about 42 to 48 px).
   Combining four frontier VLMs by median or vote gave door 0.433 to 0.458 and window unchanged (from a, computed), and
   "enumerate then count" prompting gave no significant gain (from a, the pull request's own bootstrap).
4. Detector-plus-rules is what won in adjacent fields at our data size (section 4), and the one floor-plan study that compares
   the two ways to read openings finds a local detection head far better than sequence emission.

## 2. Top 10, ranked across all three reports

Code and weights licences are given separately. "Leakage" is whether CubiCasa5K (or a repackage) is in the training data, with
where that is stated. GPU and hours are estimates unless a source says so. Our images: median longest side 855 px, symbols 5 to
20 px, a third rotated, scans and phone photos.

### 1. RF-DETR (Nano to Large), fine-tuned on our boxes, one trained pass at an upscaled input
- **What it is.** A DINOv2-based real-time DETR (arXiv 2511.09554, ICLR 2026) with a `train()` API. Pair it with the resolution
  lesson of arXiv 2611.12657: where an image can be trained at higher resolution, one pass beats tiling with box fusion.
- **Fills.** `elements` (window, door, toilet, sink, shower, bathtub, sauna stove) as boxes; confidence goes to proof/confidence.
- **Measured number.** None on floor plans. On COCO the README table gives RF-DETR-M 54.7 AP50:95 at 576 px (33.7 M parameters),
  RF100-VL 61.2; L 56.5 / 62.2 at 704 px (re-checked 01:23). On VisDrone a single pass at 2048 px beats 1280 px with tiles and
  box fusion by 2.8 to 3.5 AP on val and 1.8 to 3.1 on test-dev for every detector trainable at that size (arXiv 2611.12657;
  abstract and the +2.75 / +1.83 and +2.95 / +1.90 rows re-checked 01:23; the 3.5 and 3.1 ends are from c). Dataset there:
  VisDrone, long side about 1360 px. Training-set size here: ours.
- **Licences.** Code Apache-2.0 (GitHub licence field and README, re-checked 01:23). Weights: Nano, Small, Medium, Large detection
  and all Seg sizes Apache-2.0; Atto, Femto, Pico, XL, 2XL are under Roboflow's PML 1.0 and are out (README, re-checked 01:23).
- **Leakage.** None from the checkpoint: it is a COCO-pretrained detector trained on our own boxes (the sealed eval stays out).
- **GPU and time.** Docs list batch 4 with gradient accumulation 4 on a 16 GB card at the stock sizes (from b, read); 12 GB needs
  a smaller batch or gradient checkpointing (which saves 30 to 40% memory at about 20% more time, from b). A first number in 3 to 6 h (estimate).
- **What breaks.** Stock augmentation is a horizontal flip only, so rot90 and vertical flip need an Albumentations config (from b,
  read in the docs; whether a RandomRotate90 entry is accepted was not tested). Stock inputs are 384 to 704 px, so at 576 px a
  5 to 20 px symbol on an 855 px plan is 3 to 14 px: upscale first or tile. Tiling needs a merge rule that is tested on counts
  (a door cut by a tile edge counts twice under a wrong rule; SAHI's default IOS 0.5 can merge two tightly packed windows).
  Detection models keep 300 queries, far above about 27 boxes per plan (104k boxes over 3,828 images). Local training from COCO
  weights can differ from Roboflow's platform results; evaluate the EMA checkpoint (issue 484, from b).
- **Verdict: try tonight.** It is the only permissive, maintained detector with a documented fine-tuning path, and nothing else
  here gives a number on our boxes.

### 2. The scan-shift study ("Why floor plan object detection breaks under real scans", Carrara, Nousias, Borrmann)
- **What it is.** Automation in Construction vol. 191, article 107193 (2026): paired clean renders and the dataset's own scanned
  rasters of the same CubiCasa5K layouts, RT-DETR trained on each and tested on both, plus region composites to separate symbol
  depiction from background. Abstract (read on the TUM portal, from a): AP at IoU 0.75 and 0.85 falls much more than AP50; altered
  depiction inside the object regions is the main cause, scanned backgrounds cost only moderately. The paper body was behind a
  captcha and unread; everything below is from the committed result tables.
- **Fills.** Evidence for `elements` and for the eval plan; not a method.
- **Measured numbers (re-checked 01:23, result JSON for windows and doors pooled).** Clean-trained on clean test: AP 0.807, AP50
  0.832, AP75 0.824, AP small 0.700, AR@100 0.960. Scan-trained on scan test: AP 0.522, AP50 0.751, AP75 0.599, AP small 0.106,
  AR@100 0.665. Per class AP50 (from a, read): window 0.959 clean vs 0.722 scanned, door 0.704 vs 0.779. Error decomposition over
  all six classes (from a and b, read in the CSV and summary): 10.2% of boxes missed on clean vs 25.5% scanned, loose 4.8% vs
  34.4%; doors missed 4.4% vs 15.1% at IoU 0.5, windows 5.4% vs 17.8% (b's arithmetic from the JSON counts). Box area at which half
  the objects are found: 120 vs 909 square pixels (from a). Thicker strokes alone at "medium" took a clean-trained model's AP50
  from 0.881 to 0.253 (from a, read). Dataset: 4,197 train, 400 val, 399 test layouts, 100 epochs, 1024 px, batch 8, six classes.
- **Licences.** Code MIT (the repo's LICENSE.assets says the dataset-derived assets are not covered by the MIT software licence,
  re-checked 01:23; GitHub's licence field reads NOASSERTION); checkpoints, result bundles and the Zenodo data CC BY-NC 4.0
  (Zenodo licence field re-checked 01:23).
- **Leakage.** Yes: built from CubiCasa5K. Use as a test bed and as a recipe, not as a checkpoint for scored runs.
- **GPU and time.** Download 4.7 GB, run the evaluation scripts: 3 to 6 h to a first number on our data (estimate).
- **What breaks.** The "scans" are CubiCasa5K's own rasters, not phone photos, and not rotated. The mitigation fine-tunes (stroke
  and blur curriculum on 400 layouts, two epochs, learning rate 1e-5) have recipes but no results in the repo. It disagrees with
  the RT-DETR-L repo by 12 to 17 AP50 points (section 5).
- **Verdict: try Saturday**, as the degradation test for our own detector (apply thickening and blur to our dev images), because
  it measures the failure we expect on the scanned third.

### 3. PlanQ-CubiCasa benchmark, as the floor a detector must beat
- **What it is.** The only public source that scores exact door and window counts per plan on CubiCasa5K test plans (SoftHeart1314,
  repo pushed 2026-11-03; the manuscript was not found). Three readers: a 4-stage U-Net (width 32, 512 px, 30 epochs, 2,315 plans) with
  connected components; a 4-bit LoRA fine-tune of DeepSeek-OCR2 on 2,195 plans; a prompted general VLM. Counting rule: one per
  `Door` or `Window` group in the SVG, furniture doors excluded.
- **Fills.** `elements` window and door counts; a baseline ladder, not a method.
- **Measured numbers (re-checked 01:23 for the U-Net).** Exact doors 64, 66, 67, 65 of 190 and windows 63, 63, 61, 56 of 190 at
  closing kernels 0, 3, 5, 9; median absolute error 1 for both. Fine-tuned VLM 53/177 doors and 47/177 windows; prompted VLM
  113/280 and 132/280 (from a and b, read in the summary files). Error shape (from a, computed from the per-plan CSVs): the U-Net
  overcounts (bias +0.9 doors, 103 of 190 plans too high), both VLMs undercount (-0.5 to -1.1); every reader is within one symbol on
  58 to 74% of plans. Exact rate falls with count (section 1). Wall IoU and pixel IoU: window 0.742, door 0.656 for the U-Net.
- **Licences.** Code MIT (re-checked 01:23); derived labels CC BY-NC 4.0, images not redistributed; no weights released.
- **Leakage.** Yes: all arms train on CubiCasa5K. Our dev split can still be scored by re-running the recipe on our own data.
- **GPU and time.** About 24 minutes per seed for the U-Net (claim); 2 to 4 h to a first number on our data (estimate).
- **What breaks.** Eligibility filters keep clean single-floor plans with dimension labels (299 of 400 test plans); 512 px; no scans,
  photographs or rotation. Its window count has a mean of 5.9 per plan against our brief's about 9, so the rules differ. The prompted
  reader also sees a room-area table made from ground truth (a's note: counts are not helped by it, but it could prime the number of rooms).
- **Verdict: try tonight** as the baseline ladder. A detector must clearly beat 33 to 35% exact on doors and about 33% on windows.

### 4. AECV-Bench (Kondratenko et al., arXiv 2601.04819, January 2026) and its live results
- **What it is.** 120 plans (CubiCasa5K, CVC-FP and web drawings), a prompt with explicit counting rules, JSON counts scored by exact
  match, per-plan outputs for 28 models in the repo.
- **Fills.** None; it is the VLM baseline and the source of the 40-55% line.
- **Measured numbers.** Paper: Gemini 3 Pro door 0.39, window 0.34, mean 0.51 over four classes; "strongest models plateau around
  0.4-0.55 mean" (re-checked 01:23). Live table (from a, recomputed from the per-plan CSVs, not re-run): Gemini 3.5 Flash 0.43 / 0.39,
  Gemini 3 Pro 0.40 / 0.34, Claude Fable 5 0.36 / 0.29, GPT-5.5 0.30 / 0.28; mean true counts 9.3 doors and 9.5 windows, the same scale as ours.
  Cost: 3.77 USD for 120 plans with Gemini 3.5 Flash, 26.88 USD with GPT-5.5 (from a).
- **Licences.** No LICENSE file and an empty licence field (re-checked 01:23): reuse of the code and the 120 drawings is unstated.
- **Leakage.** Partly: a subset of the plans is CubiCasa5K.
- **GPU and time.** API only. Under 1 h for a first number with one model on a few dev images (estimate), money to be approved first.
- **What breaks.** Its own counting rules differ from ours at three points: adjacent windows with no gap count as one group, sliding
  and French doors count as windows, each door leaf counts separately (from a, quoted from the repo prompt).
- **Verdict: try Saturday** as the prompted-VLM comparison only; do not use it as a counter.

### 5. Emit versus detect: read openings from a local head, not from a sequence (arXiv 2608.25608, with fpvec-lab)
- **What it is.** One wall-first network read two ways. Reading the opening heatmap that the sequence decoder never used raised opening
  F1 from 0.246 to 0.644 (door/window family heuristic) and 0.799 (family ignored); a separate 200K-parameter door/window head reaches
  0.988 family accuracy; the fused system's openings reach 0.849 against 0.848 for the room-centric arm alone. All re-checked 01:23 in the paper text.
- **Fills.** `elements` (door, window) as the design principle; `rooms` untouched.
- **Measured numbers.** Above, on CubiCasa5K official test with corrected annotations (n = 287; 3,328 training plans), 256 px input,
  F1 on opening positions, not counts. The authors say the wall-first arm is under-tuned for openings. They also show the annotation
  conversion alone moves a fixed checkpoint's opening F1 from 0.29 to 0.66, and that 1,020 of 5,000 source SVGs fail to parse in their
  converter (from a and b, read).
- **Licences.** Code MIT (repo licence field re-checked 01:23; the `skv4` converter is non-commercial because it vendors CubiCasa code);
  corrected annotations CC BY-NC-SA 4.0; no trained weights released (open issue, from a and b).
- **Leakage.** Yes (CubiCasa5K and a Raster2Seq checkpoint).
- **GPU and time.** Not applicable as released; the idea costs nothing.
- **What breaks.** 256 px cannot separate adjacent window cells in our images; numbers are F1 on positions.
- **Verdict: idea only.** It is the evidence for choosing a detector over a sequence decoder for doors and windows; item 1 follows it.

### 6. RT-DETR-L floor-plan detector recipe (OldDeLorean repo, Architect Ant arXiv 2606.10953)
- **What it is.** An Ultralytics RT-DETR-L (32.8 M parameters) on CubiCasa5K converted to YOLO format, 1024 px, 60 epochs, about 2.3 h on 2 GPUs.
- **Fills.** `elements` door and window boxes (also wall, railing, linkage point).
- **Measured number.** Official 400-plan test split: door AP50 89.8 / AP[.5:.95] 57.5, window 89.3 / 62.2 (re-checked 01:23); strict
  polygon-ground-truth AP@0.5 door 84.8, window 85.5. A 1536 px retrain gives the same AP50; evaluating the 1024 model at 1536 drops to
  84.5 (from a and b, read). Training set 4,200 plans. Flips only, no rot90.
- **Licences.** No LICENSE file in the repo (file listing re-checked 01:23); the README says the stack is Ultralytics, AGPL-3.0. Weights: no licence stated.
- **Leakage.** Yes: official CubiCasa5K train split.
- **GPU and time.** The README gives batch 16 on 2 x 40 GB; a 12 to 16 GB card needs batch 4 or less. A reproduction with the Apache RF-DETR of item 1 is the plan (estimate 2 to 4 h).
- **What breaks.** Its own warning about densely furnished and rendered styles; faint dashed door arcs; input other than 1024 degrades.
  The repo's per-plan counts are not reported.
- **Verdict: try the recipe, skip the checkpoint** (AGPL and leaked).

### 7. Template matching as the first baseline, and the tiling rule for any VLM look (arXiv 2610.09313, "Why VLMs miss small objects")
- **What it is.** 187,000 requests to 12 VLMs, with LegendSpot (40 architectural drawings, 1,028 instances) and FloorPlanCAD blocks.
  A symbol must span about 1.5 visual tokens per side; split views without zooming out and overlap them by one object. A classical
  baseline, multi-scale four-rotation normalised cross-correlation with NMS from one reference crop, reaches 0.87 F1 on the 34 drawings
  whose reference comes from the same drawing and 0.38 on 10 whose reference comes from a symbol library; the best tiled VLMs reach
  0.92 and 0.94 (re-checked 01:23 in the paper text). Propose-and-verify with a VLM judging candidates ended at 0.83 to 0.91, level with
  template matching alone (from a and c, read). CountGD and GeCo2, trained exemplar counters, are reported at 0.10 and 0.23 F1 on
  LegendSpot against 0.90 and 0.86 on natural FSC-147 images (from a and c; not re-found in the text I grepped).
- **Fills.** `elements` as a proposal or check; a baseline; the safe-split rule for any VLM step.
- **Licences.** Code MIT (repo licence re-checked 01:23), including `tools/safe_tiles.py` (stand-alone, needs only pillow); LegendSpot
  images, FloorPlanCAD-derived files and model answers CC BY-NC 4.0 (LICENSE-DATA re-checked 01:23). No weights: nothing is trained.
- **Leakage.** None (no training).
- **GPU and time.** CPU only; 2 to 3 h to a first number on our dev split (c's estimate).
- **What breaks.** Their drawings are 4 to 13 times larger than ours (c); our symbols are 5 to 20 px against about 44 to 74 px in the
  paper, and CubiCasa-style scans were not tested. A 12 x 12 px template is a regime where classical matchers fail (TDCM paper, from c,
  abstract-level). Symbols vary across drawing styles, so one crop per class may not generalise (from a).
- **Verdict: try tonight** (the matching baseline); the VLM tiling is Saturday at most.

### 8. BlueprintParse-R50 (ThakiCloud, Hugging Face, 2026-11-08), for toilet, sink, bathtub and gas range
- **What it is.** Faster R-CNN R50-FPN v2 exported to ONNX (onnxruntime), five classes: gas range, toilet, washbasin, kitchen sink,
  bathtub, trained on a Korean AI-Hub drawing set (7,900 train).
- **Fills.** `elements` toilet, sink, bathtub (no shower, no sauna stove).
- **Measured numbers (re-checked 01:23, model card).** Official test (1,014 drawings) mAP50-95 0.926, AP50 0.9805; 53 "novel"
  drawings mAP50-95 0.7875; per-drawing exact count match 0.566 (95% CI 0.434 to 0.698) at score 0.8, which the card calls COUNT_NO_GO
  against a 0.90 gate. Created four days before reading, 0 downloads, no third-party reproduction (from b): claims, not results.
- **Licences.** Code and weights Apache-2.0 (card and NOTICE re-checked 01:23). The NOTICE says the training dataset "is NOT
  redistributable. Only weights trained on it are published"; whether that is compatible with shipping is a question for Bogdan (from b).
- **Leakage.** No: not CubiCasa5K.
- **GPU and time.** CPU or GPU, 0.8 to 2 s per image on server CPUs per the card (from b); about 1 h to a first number (estimate).
- **What breaks.** Korean drawing style; the script never enlarges, so our small symbols are a worse case than its training pages (b).
- **Verdict: try Saturday, dev split only**, as a smoke test for the sanitary classes.

### 9. Rotation: rot90 augmentation, four-rotation test-time voting, and an orientation step
- **What it is.** The CubiCasa 2019 recipe already trains with 90-degree rotations (re-checked 01:23, "data augmentations were 90 degree
  rotations") and the test-time four-rotation vote is reported to help (from a). The DLR rotation study (arXiv 2504.03241) measures a
  graph classifier on pre-segmented regions: window F1 98.3 on upright test plans, 76.8 to 79.4 on rotated ones, 24.8 on rotated ones with no
  normalisation; door 93.2 upright, 79.7 to 87.7 rotated, 36.8 with no normalisation; on CVC-FP window 3.7 to 12.7 and door 1.9 to 3.0
  (re-checked 01:23 in the paper's tables). A document orientation classifier ("Seeing Straight", arXiv 2511.04161: 98% and 96% on its two
  sets; or PaddleOCR's `PP-LCNet_x1_0_doc_ori`, Apache-2.0, 99.06% on a 1,000-image self-built set) is c's route for the rotated third.
- **Fills.** A pre-step for `elements`, `rooms` text, `scale`.
- **Licences.** DLR study: no code link. PaddleOCR repo Apache-2.0 (from c). Seeing Straight: not checked.
- **Leakage.** The DLR classifier was trained on CubiCasa5K; our own training would not be.
- **GPU and time.** Augmentation is free; a small orientation CNN trained on our own rotations, 3 to 5 h (c's estimate).
- **What breaks.** No source measures exact door/window counts on rotated plans (queries in section 7). Text-line cues are weak on plans with few labels.
  Oriented-box detectors are not needed if rotation is handled by rotating the image (RF-DETR issue 921, from b).
- **Verdict: try tonight** (rot90 augmentation and four-rotation voting); orientation classifier Saturday.

### 10. Licence-clean extra training data: ResPlan, Swiss Dwellings, procedural generators
- **What it is.** ResPlan: about 17,000 vector residential plans with door and window polygons, 2025, v2 2026-08-04. Swiss Dwellings:
  over 45,000 apartments with about 715,000 openings and about 315,000 "features" (sinks, bathtubs, toilets). `fpgen` inside fpvec-lab, a
  procedural generator fitted to listing statistics with four render styles and tracked degradations. A CC BY synthetic generator on
  Hugging Face (Manhattan plans, jamb-gap doors, no swing arcs, 256 or 512 px).
- **Fills.** Training images with exact boxes for `elements`.
- **Measured number.** None for door/window counting. Real labelled data matters more: in chemistry a model at over 91% on synthetic images fell
  below 16% on real ones, and 9.5% real data lifted exact match from 0.15 to 0.37 (arXiv 2608.09100, from c, abstract-level); in sheet music
  synthetic-only still left 63.97% error on real scans (Transcoda, from c, abstract); the P&ID study that trained on 665 synthetic
  plans reached 63.8 edge mAP on its test set, but the synthetic plans are generated from the same 12 drawings that are evaluated, so it is optimistic (from c, read).
- **Licences.** ResPlan data CC BY 4.0 and code MIT (LICENSE file re-checked 01:23; GitHub says NOASSERTION because there are two; a TAKEDOWN.md is
  present and provenance of the source images is withheld). Swiss Dwellings CC BY 4.0 (Zenodo licence field re-checked 01:23). fpvec-lab MIT
  (re-checked 01:23). Synthetic sets CC BY 4.0 (from a and b, cards read).
- **Leakage.** None from CubiCasa5K.
- **GPU and time.** Rendering is CPU; one night for a generator and a first mix (estimate, c's 1 day for fpgen plus 3 h).
- **What breaks.** Vector sources have no drawn symbols, so the style is ours to invent; Manhattan walls only; window placement differs; no scan or
  photo effect unless added; the Swiss data has Central-European conventions. Nobody measured the effect on CubiCasa5K-style counting.
- **Verdict: idea only for tonight, try Saturday as a supplement** to the real 3.8k plans.

## 3. Full table (every method, product or source the three reports assess, duplicates merged)

"From" is the report (a, b, c). "Read" = read in the source; "claim" = the authors' claim as reported; "summary" = search or abstract only. Licences: code / weights.
"Leak" is CubiCasa5K in training (Y), no (N), unknown (?), n/a.

| Method or source | From | Year, venue | Licence (code / weights) | Leak | Read level | Number or note | Verdict |
|---|---|---|---|---|---|---|---|
| RF-DETR N to L | a b c | 2025-26, ICLR 2026 | Apache-2.0 / Apache-2.0 (Atto, Femto, Pico, XL, 2XL: PML 1.0) | N if trained on ours | read | M 54.7 COCO AP50:95 at 576 px | try (item 1) |
| Scan-shift study and ScanShift data | a b | 2026, Automation in Construction | MIT / CC BY-NC 4.0 | Y | read (tables), abstract read | door+window AP50 0.832 clean, 0.751 scanned | try (item 2) |
| PlanQ readers | a b | 2026 repo | MIT / none; labels CC BY-NC | Y | read | exact door 33.7-35.3%, window 29.5-33.2% (U-Net) | try (item 3) |
| AECV-Bench | a b c | 2026 arXiv | none stated / n/a | partly | read | door 0.39, window 0.34 (paper best) | try (item 4) |
| Emit vs detect, fpvec-lab | a b c | 2026 arXiv | MIT (skv4 NC) / none | Y | read | opening F1 0.246 to 0.644 to 0.849 | idea (item 5) |
| RT-DETR-L repo | a b | 2026 repo, arXiv 2606.10953 | none, AGPL stack / none | Y | read | door 89.8, window 89.3 AP50 | recipe only (item 6) |
| Template matching + safe tiling (2610.09313) | a b c | 2026 arXiv | MIT / n/a; data CC BY-NC | N | read | 0.87 F1 on 34 drawings | try (item 7) |
| BlueprintParse-R50 | b | 2026 HF | Apache-2.0 / Apache-2.0 (dataset not redistributable) | N | read (card) | exact count 0.566 on 53 drawings | try dev only (item 8) |
| Zernike rotation study | a b | 2025 arXiv | none linked / n/a | Y | read | rotated window F1 76.8-79.4 | evidence (item 9) |
| Seeing Straight orientation classifier | c | 2025 arXiv | not checked | N | claim | 98% / 96% orientation | try Saturday |
| PaddleOCR doc orientation model | c | docs | Apache-2.0 / Apache-2.0 (repo) | N | summary | 99.06% on 1,000 images | idea |
| ResPlan | a b c | 2025, v2 2026 | MIT / CC BY 4.0 data | N | read | 17,000 vector plans | supplement (item 10) |
| Swiss Dwellings, Neufert 4.0 subset | a b | 2022, 2024 | n/a / CC BY 4.0 | N | read (record) | 715,000 openings, 315,000 features | supplement |
| fpgen generator | a c | 2026 | MIT / n/a | N | read | four styles, degradations | try Saturday |
| benikm91, jotamunz synthetic plans | a b c | 2026 HF | generator no licence field / CC BY 4.0 | N | read (cards) | 100K to 1M plans; sizes differ between cards | supplement at best |
| CubiCasa5K 2019 model | a b | 2019 arXiv | CC BY-NC 4.0 / Drive link, no licence | Y | read | window 66.8, door 53.6 raw; 40.9 / 41.2 polygon | baseline already in hand |
| CubiCasa5K-Next reimplementation | a b | 2026 | Apache-2.0 / none | n/a | read (README) | no metrics | idea |
| Raster2Seq | a b c | 2026, SIGGRAPH | MIT / CC BY-NC 4.0 | Y | read | window+door F1 77.8 at 256 px | rooms only |
| MuraNet | a b | 2023 arXiv | none / none | Y | read | door 91.2, window 92.2 AP50, custom split | skip |
| Raster-to-Vector (Liu) | a b | 2017 ICCV | MIT / Drive link | N | read | opening precision 67.9 to 91.9 with constraints | idea |
| Deep Floor Plan Recognition, TF2 port | a b | 2019 ICCV | GPL-3.0 / link | N | read | door+window pixel accuracy 0.83-0.89 | skip |
| Raster-to-Graph | a b | 2024 CGF | GPL-3.0 / n/a | N | read | no door or window class | skip |
| RoomFormer | a b c | 2023 CVPR | MIT / not stated | retrained versions Y | read | Structured3D room F1 97.3 | rooms |
| FloorplanVLM | a b c | 2026 arXiv | none / none | ? | read | opening F1 0.7333, 2M plans, 32 GPUs | skip |
| Community FloorplanVLM adapters (mudasir13cs, BOOMI, rimashussain, miladmirzazadeh) | a b c | 2026 HF | tags conflict with cards / CC BY-NC-SA or Apache tag | Y | read (cards) | BOOMI exact program 3.4% | skip |
| MiniCPM-V floor-plan LoRA | b | 2026 HF | Apache tag / Apache tag | N (FloorPlanCAD) | read (card) | F1 0.105, valid JSON 40% | skip |
| SALI-FP | a b c | 2026 arXiv | n/a / n/a | n/a | read | door IoU 0.04-0.15 vs 0.62 supervised | evidence |
| DoorDet | a b | 2025 arXiv | not found / not found | Y | read | Co-DETR mAP 0.831 multi-class, 7.81 doors/plan | skip |
| Facility enumeration (Co-DETR + GPT-5) | a b | 2025 arXiv | not found / n/a | n/a | read | toilet 87.63 vs 85.57 | idea |
| LGS-FPP | a | 2026 preprint | none / none | Y | read | scan door PA 87.5 | idea |
| Rezvanifar tiled YOLOv2 | a b | 2020 CVPRW | none / none | N | read | window AP50 75.6, 90 plans | idea (tiling cost) |
| Al-Turki active learning (YOLOv5) | a | 2023 Sci Rep | AGPL stack / data link dead | N | read | door PR-AUC 0.841, window 0.763 | idea |
| FloorYOLO | a b | 2026 Frontiers AI | AGPL stack / none | N | read | SESYD 0.995, CVC-FP 0.824 mAP50 | skip |
| MitUNet, FGSSNet, Raster2Graph-style wall nets | a b | 2025-26 | various | Y | abstract | walls only | skip |
| FloorPlanFormer | a b | 2026 AAAI | none seen | N (own set) | abstract | windows merged with walls | skip |
| WAFFLE | a b | 2025 WACV | no licence field / CC BY 4.0 data | N | read | 2019 model door IoU 0.099 | evidence |
| Avito checkpoints | a b | 2026 HF | MIT tag / MIT tag | Y | read (card) | val AP50 0.90, phone photos 0.28 | evidence |
| Voix7 RT-DETRv2, kiyo07 RF-DETR door, OsamaMo RF-DETR-M | a b | 2026 HF | Apache tag, AGPL runner, NC terms | ? | read (cards) | kiyo07 no metrics; OsamaMo val mAP50 94.5 own split | dev smoke tests only |
| v1nz YOLO11 and CubiCasa YOLO repackage | a b | 2026 HF | AGPL, CC BY-NC | Y | read (cards) | 0.41 mAP50 on random 5% | skip |
| xmarva, rbg-research, Yytsi, karanjaWakaba, sankhya007 checkpoints | a b | 2026 repos | MIT code mostly | Y | read | rbg SR study "up to 39.47% better" | skip |
| Roboflow door and window sets (4) | a b | Roboflow Universe | CC BY 4.0 / Public Domain | ? | read (pages) | 402 to 1,497 images, source unstated | possible data after overlap check |
| SkeySpot / DELP | a b | 2025 SMC | none / none (AGPL) | N | read | mAP50 81 on 13 test plans | idea |
| MEP lighting symbols (Mask R-CNN, tiles 1000 px, overlap 0.2) | a b | 2026 arXiv | none / none | N | read | bbox mAP 0.76, private data | idea |
| LLM-integrated YOLOv8 + U-Net (101 plans) | a b | 2026 Applied Sciences | AGPL stack | N | read | mAP50 92.3 on a leaky split | caution |
| Khare super-resolution before CubiCasa5K | a | 2021 arXiv | MIT / n/a | Y | read | up to 39.47% better, 12.17% mean | idea |
| MDA-Unet multi-unit plans | a | 2024 arXiv | Apache-2.0 / n/a | Y | read | pixel F1 0.86 | skip |
| ArchCAD-400K, SymPoint, FloorPlanCAD, TempFit | a b c | 2023-26 | non-commercial or academic | n/a | read | vector CAD input | skip (L11) |
| K-OPSD, Knowledge-distillation thesis | a b c | 2026 | n/a | leak by design | read (abstract) | 42 test items | skip |
| LED-BENCH, DrawingVQA, ArchSIBench, MMArch, ARCH-B, CrossProjection | a b c | 2026 | n/a | n/a | abstract | best 52.65% QA; localisation PCK 8-76% | evidence |
| AEC-Geometric-Bench (vendor) | a | 2026 | MIT code / CC BY-NC data | n/a | read (README) | eight-class object F1: vendor 0.929, VLMs 0.015-0.062 | evidence |
| Handoff-H1, Blueprint-Bench, pdf2takeoff | a | 2025-26 | n/a | n/a | claim | vendor numbers, lenient metric | context |
| Aalto thesis (wall recognition) | b | 2025 | CC BY-NC-SA | Y | read | 32 plans lifted mean rating 2.45 to 3.54 | evidence |
| BlueprintSymVL | a c | 2025 | data CC BY 4.0 | N | read | dense regions 26-32% exact | evidence |
| Chain-of-Look dense counting (CoLSR) | c | 2026 WACV | NOASSERTION / n/a | N | read | MAE 0.88 on 1,464 images | maybe |
| CountGD, GeCo2, RECOUNT, AgriCountDINO | c | 2024-26 | MIT / DINOv3 licence | N | read (abstracts) | 0.10-0.23 F1 on drawings | skip unless fine-tuned |
| SynthPID | c | 2026 arXiv | repo 404 | N | read | 63.8 edge mAP, seeds = test drawings | idea |
| FlowExtract, SINA, PCBnet, Image2Net | c | 2026 | AGPL YOLO | N | read | node F1 98.8 on 25 training images; netlist 96.47% | pipeline shape |
| Relationformer on P&ID, modular baseline | c | 2025 DSAA | Apache-2.0 / n/a | N | read | symbol mAP 73.14 vs 76.99 modular | maybe |
| AWS P&ID guidance | b | 2026 | MIT-0 / n/a | N | read (README) | connection F1 17% to 91%, 10 sheets | idea |
| Florence-2 and Donut fine-tunes on engineering drawings (Khan) | c | 2024-25 | MIT / MIT | N | read | +52.4% F1 on 400 drawings | maybe (labels, scale) |
| Scale-bar pipeline (maps poster) | c | 2026 | not located | N | claim (abstract) | mAP50 0.992 | maybe (`scale`) |
| MolScribe, DePlot, SMT, LEGATO, TDATR, UniChart | c | 2023-26 | mostly MIT / Apache; UniChart GPL | N | read | see section 4 | idea or skip |
| CISOL, PubTables-1M, DocLayout-YOLO | c | 2021-25 | MIT, AGPL | N | read | generic YOLOv8 beat TATR on 800 images | evidence |
| Numbered-box VLM check (RxnCaption), per-box True/False check, Set-of-Mark | c | 2023-25 | MIT (SoM) | N | read | 35.4 to 81.0 F1 | try Saturday (check) |
| VERDICT agreement gate, CrowdCue, TableVision consistency | c | 2026 | n/a | N | abstract | agreement AUROC 0.916 | idea (gate) |
| Resolution vs tiling (2611.12657), ReDHF, SCAHI, SAHI | b c | 2026 | SAHI MIT | N | read | 2048 px single pass beats tiles on VisDrone | try (item 1) |
| SAM 3, DEIMv2, D-FINE, RT-DETR v2 | c | 2025-26 | custom, non-commercial, Apache, Apache | N | summary | licence sweep | D-FINE and RT-DETRv2 as alternatives |
| GreenMap YOLO11x layout and legend detectors | b c | 2026 HF | Apache tag, AGPL library | ? | read (cards) | val mAP50 0.984 on 178 images | idea (find plan on a sheet) |
| Dynamic Tiling, SAHI merge defaults | b | 2023, 2026 | MIT (SAHI) | N | read | IOS 0.5 default | tune on dev counts |
| AsfTS two-stage bathroom crop then fixtures | b | 2026 | MIT / n/a | n/a | read (README) | no accuracy | idea (fixture classes) |
| Roboflow100-VL, Can VLMs Count, Illusion of Replacement review | c | 2025-26 | n/a | n/a | abstract | zero-shot VLM near 2% on hard sets | evidence |
| Surveys (IJDAR 2025, Automation in Construction 2025, ACM 2025) | a b | 2025 | n/a | n/a | abstract only | no tables read | lead |

## 4. Transfers from other fields

| Field | What plays the role of our object | Why it transfers | What breaks | Code usable? |
|---|---|---|---|---|
| Aerial and drone detection (VisDrone, DOTA) | tiny object | same size regime; measured tiling-vs-resolution trade (2611.12657) | texture vs thin line art; no line-preserving upscale tested | idea (train at 2x first); SAHI MIT usable |
| Legend-symbol spotting on engineering drawings (LegendSpot) | a window or door crop as exemplar | same task shape: find every instance of a symbol; template matching 0.87 F1 | drawings 4 to 13x larger, symbols 44 to 74 px | as is: `baseline_template_matching.py` (MIT code); data NC |
| Dense counting by example (CountGD, GeCo2, CoLSR, RECOUNT) | the window strip's repeated cells | spacing loss, look-alike filtering | 0.10 to 0.23 F1 on drawings without tuning; measured MAE not exact rate | needs fine-tuning |
| P&ID digitisation (Relationformer, AWS pipeline, SynthPID, Digitize-PID, two-stage MLLM) | valve or instrument symbol | tiny repeated symbols on line art; modular beat single-call MLLM; VLM reviewer that zooms | tags are printed text, ours are graphics; 10 to 12 test sheets | Relationformer Apache-2.0 needs fine-tuning; AWS guidance idea only (Bedrock, paid) |
| Circuit schematics and PCB (SINA, FlowExtract, PCBnet, OmniSch) | component symbol | detector plus rules plus VLM check, 25 to 700 training images | vector-clean images; YOLO is AGPL (use an Apache DETR) | idea only |
| Sheet music (OMR: DeepScores, SMT, Transcoda) | note head on a staff line | symbols touching lines; rare-class oversampling by pasting crops | upright clean pages; end-to-end only won with 214k pages or domain fine-tuning | idea only |
| Chemical structure recognition (MolScribe, VERDICT, ViCoR, OCSR real-data) | atom with coordinates | coordinate supervision, exact-match scoring, agreement of four recognisers as accept gate, small real share beats synthetic | clean graph rules; 1.68M training examples | idea only |
| Tables and charts (PubTables-1M, CISOL, DePlot) | cell, bar | define the label once ("one window per drawn cell"); resolution mattered (24.8 to 74.9 from 224 to 588 px) | 500k training pairs | idea only; Pix2Struct Apache-2.0 |
| Engineering drawings (Khan: Florence-2, Donut; AEC layout detection) | printed note, title block, drawing region | small VLM fine-tune reads crops; RF-DETR finds regions (mAP50 0.949 on 551 drawings) | text-only crops; ~10% hallucination | Florence-2 and Donut MIT, need fine-tuning |
| Historical and cadastral maps | scale bar, map sign | detect then read at full resolution; humans in the loop | an abstract, not a paper | idea only |
| Document orientation (Seeing Straight, PaddleOCR) | whole plan | free labels by rotating upright plans | plans have few text lines | PaddleOCR model usable; ours would be fine-tuned |
| Floor-plan localisation, generation | none | none | not recognition | skip |

What won where, in short (c): at our data size (0.4k to 4k labelled images at about 800 px) a trained detector plus rules plus a VLM only to read or check
a crop. End-to-end image-to-markup won where data was large or synthetic and unlimited (214k rendered score pages, 1.68M chemistry renders, 2M floor-plan images on 32
GPUs) or where the output is a structure a cascade breaks (P&ID connections: +30 edge-mAP points for Relationformer, while the modular detector kept the higher symbol mAP,
76.99 vs 73.14). Our target is counts of local symbols, which the one floor-plan study that tested it frames as detection.

## 5. Disagreements between the reports, and which holds

1. **Is "40-55% exact on door and window counts" true?** a says it holds as a range for the newest prompted VLMs on clean plans, with the four-class correction; b says it does
   not hold because the paper's 0.4 to 0.55 is a four-class mean and doors and windows are 0.09 to 0.39. I opened the paper: it says "plateau around 0.4-0.55 mean exact-match
   accuracy" and gives Gemini 3 Pro door 0.39, window 0.34. Both reports are right about different things. Holds: as an approximate range for the best prompted models on clean plans
   (live 0.43 / 0.39 from a's recomputation; PlanQ prompted reader 0.40-0.45 / 0.47-0.49). Does not hold: as a statement of what the paper reports for doors and windows.
2. **RT-DETR on CubiCasa5K, door and window AP50: 89.8 / 89.3 (repo) vs 77.9 / 72.2 (scan-shift).** Both re-checked. Unresolved. Differences visible in the files (from a): Ultralytics
   RT-DETR-L against Hugging Face RT-DETR, 60 against 100 epochs, five classes against six, different box conversion from the annotation, different split (official lists
   against 4,197 / 400 / 399 kept layouts). Neither was re-run. Use neither as a prediction.
3. **CubiCasa5K 2019 per-class numbers.** a gave pixel IoU 66.8 / 53.6 and polygon 40.9 / 41.2 from Table 6 of the paper (re-checked 01:23, both rows). b's Aalto thesis column gives polygon
   54.9 / 48.6 (window / door), a different model and a different split (4,400 / 100 / 500), so the two do not conflict. b's earlier pass shifted a column by one and corrected it; the repo
   `vs_cubicasa5k.md` carries the same erratum. The paper's numbers hold for the released model.
4. **Raster2Seq training-set size and split.** b's pass 2 says 4,199 / 399 / 399; pass 3 and a say 5,267 train, 503 val, 511 test after splitting multi-plan sheets (arXiv 2602.09016). Pass 3 holds.
5. **Opening F1 for the Raster2Seq-based arm.** 0.848 (a, in the system table) and 0.849 (c, fused) are the same row: the fused system reaches 0.849 against 0.848 for the room-centric arm alone (paper, re-checked 01:23).
6. **Licence of the scan-shift code.** a says MIT; GitHub's field says NOASSERTION. The LICENSE.assets text says dataset-derived assets are outside "the repository's MIT software license" (re-checked 01:23), so the software is MIT and the assets are CC BY-NC 4.0.
7. **ResPlan licence.** GitHub's field says NOASSERTION; the LICENSE file has a data licence and a code licence, CC BY 4.0 and MIT as both reports state (re-checked 01:23). Provenance is withheld, and the repo carries a takedown policy.
8. **Is the CubiCasa5K weights licence "MIT"?** One downstream tool's README says so (a); the original repo's LICENSE says CC BY-NC 4.0 (a, b). The original holds.
9. **Is exact rate "higher for the segmentation arm or the VLM"?** a's PlanQ error-shape table has the prompted VLM ahead (0.40 vs 0.34 doors), b's summary has the U-Net 33.7% vs VLM 29.9% (tuned VLM). Different VLMs (prompted vs fine-tuned); the repo's paired test says the three are statistically indistinguishable. Do not rank them.
10. **Whether "tiling" helps.** b and a collect tile recipes (768 px / 384 stride, 1000 px with 0.2 overlap, 224 px with stride 50). c's source says one trained pass at higher resolution beats tiling on VisDrone at about 1360 px and a practitioner write-up (a, anecdote) says tiling with deduplication "didn't work well" for doors. Not a conflict about evidence; the question is open for our images, so item 1 starts with the upscaled single pass and keeps tiling as the second arm.

## 6. Negative results: what the literature says does not work

- Zero-shot or prompted VLMs as counters: door 0.09 to 0.43 and window 0.03 to 0.39 exact on 120 plans, undercounting on dense plans (AECV-Bench, from a and b, read); localisation near zero (object F1 0.015 to 0.062 for frontier models on construction sheets; free point localisation PCK@.05 8 to 76%).
- A VLM listing boxes: 0.105 F1 and 0.06 recall for a fine-tuned 4B model, 40% valid JSON (b, card read); a prompted pipeline gets door/window IoU 0.04 to 0.23 against 0.62 to 0.72 for the supervised 2019 model (SALI-FP, from b).
- Prompt tricks: enumerating objects before counting added +1.3 points, not significant (from a); a median or vote over four frontier VLMs added at most 2.5 points on doors (from a, computed).
- Exemplar counters without fine-tuning on drawings: 0.10 and 0.23 F1 where plain template matching gets 0.87 (c).
- A VLM as verifier of template-matching candidates did not beat the proposer (0.83 to 0.91 vs template matching alone, differences -0.04 to +0.04; c).
- Segmentation plus connected components for counts: overcounts on sparse plans; one closing kernel moves doors and windows in opposite directions (a, computed from the per-plan CSV).
- Domain shift: CubiCasa5K model on internet plans door IoU 0.099; the same detector with val AP50 0.90 reaches 0.28 on phone photos; rotated plans cost about 20 points of window F1 even with a rotation-aware feature; cross-dataset door F1 93 to 2.
- Scan degradation: thicker strokes alone cut a clean-trained detector's AP50 from 0.881 to 0.253; scan-trained detectors still miss 15% of doors and 18% of windows at IoU 0.5.
- Heavy augmentation made the phone-photo test worse in the Avito study (RF-DETR fullaug 0.200; from b).
- Synthetic-only training leaves large gaps on real scans (sheet music 63.97% error; chemistry below 16% on real sets).
- Tiling with deduplication on doors (practitioner write-up, anecdote) and tiles that zoom out (recall 0.11 to 0.28 lower on FloorPlanCAD blocks, c).
- Architecture is not the lever on clean data: a plain SegFormer-B5 is within one point of the special method on clean CubiCasa5K, and a plain Mask2Former is within 0.4 mIoU of FloorPlanFormer (from a and b).
- Raster2Seq is not better than RoomFormer on windows and doors (77.8 vs 78.5 F1).

## 7. Looked for and did not find; unverified leads; open questions

**Looked for and did not find**
- Any 2025-26 paper that fine-tunes a modern detector (RT-DETR family, D-FINE, RF-DETR, YOLOX) on CubiCasa5K symbols and reports per-class counting accuracy (arXiv date-sorted and title searches, OpenAlex, GitHub, Hugging Face, three reports agree).
- Any exact door/window counts on CubiCasa5K other than PlanQ and AECV-Bench; any leaderboard for it.
- Main-track CVPR, ICCV or WACV 2024-26 papers on recognising or counting symbols in raster floor plans (title lists of six CVF venues searched; only WAFFLE; ECCV, NeurIPS and ICDAR lists could not be searched, except one ICDAR 2026 title).
- A permissive, non-CubiCasa checkpoint with window and door classes and a stated training set; a checkpoint with shower or sauna-stove classes.
- A study of 90 or 180 degree rotated plans for door/window detection or counting; any dewarping or perspective correction tested on drawings with small symbols; a public labelled dataset of photographed floor plans.
- A trained model or metric published with the CC BY synthetic floor-plan sets, or any study of synthetic pretraining for door/window counting.
- A Finnish room-label OCR set or model.
- Code or data for DoorDet, facility enumeration, the Zernike study, LGS-FPP, FloorplanVLM weights, FloorPlanFormer, SynthPID.

**Unverified leads (kept out of the ranking)**
FloorPlanFormer (AAAI 2026, FloorPlan8K); SIM 2.0 (eScholarship, 2026-11-02); the NTU photographic-shift study (abstract only: 16.1% of plans topologically valid as digital input but invalid
photographed); two Automation in Construction surveys and the ACM 2025 survey (abstracts); a 2025 Helsinki thesis comparing YOLOv8, YOLOv11 and Detectron2 on CubiCasa5K (full text on site only);
"Visual Large Language Models for Graphics Understanding" (ACM 2025, a YOLO-versus-VLM comparison for doors and windows; abstract only); GRaF-Net (ICDAR 2026, title only); AEC-Geometric-Bench and
ResPlan-FP (second-hand through a vendor's docs; the benchmark README itself was opened for the former); PR 3 of AECV-Bench (door 0.55 / window 0.44; per-plan files not downloaded); BlueprintAgent (beam F1
0.994 vs 0.301 for one MLLM call on 300 scanned structural sheets; abstract only); the Aliyev and Barsi room-area study (MAPE about 43% for open VLMs vs 5.68% for pixel counting; abstract);
FloorYOLO tables 9 and 10; the DeepScoresV2 licence (Zenodo record opened by c); ArchCAD licence ("Academic Use License"); a Korean-dataset legal question for BlueprintParse-R50.

**Open questions**
- Which of the two RT-DETR results on CubiCasa5K is closer to what we will see (89 vs 72 to 78 AP50)? Needs a run.
- Does a detector on our boxes beat the PlanQ floor (33 to 35% exact on doors, about 33% on windows) and the 59.3% count-only network, by subgroup (rotated, small, photographed)? No source bins a trained detector by count or by subgroup.
- Do PlanQ's numbers reproduce on our dev split, and does the exact rate by count bin look the same for a trained detector?
- How should "one window per drawn cell" be defined once, so labels, detector and counting rule agree? AECV-Bench, PlanQ and our brief use three different conventions, so exact rates are not on one scale.
- Is the gap between AP and exact counts (BlueprintParse-R50: AP50 0.98 on its test set vs exact 0.566 on novel drawings) the same for our classes?
- Tools missing across the reports: ScienceDirect, SSRN and some publisher pages (captcha); arXiv search and Semantic Scholar rate-limited much of the time; DBLP unreachable; no model, weights or data were downloaded or run by anyone.

## 8. Experiments proposed (at most five)

1. **Template-matching baseline.** Run multi-scale, four-rotation normalised cross-correlation from one crop per class (window, door) on the dev split and report exact / within one / mean absolute error per class; if it already exceeds 33% exact on both, the trained detector has to clear that, not the PlanQ floor.
2. **RF-DETR resolution arm.** Fine-tune RF-DETR-S or M on our boxes with rot90 and vertical flips, once at native input scaled to 704 px and once at a 2x upscale (and a third arm with 768 px tiles and 384 stride merged by a box-centre rule), and report exact / within one / mean absolute error by rotated, small and photographed subgroups; a gain of 5 points exact or more for one arm settles tiling against resolution.
3. **PlanQ-style floor.** Re-run the 512 px U-Net with connected components on our dev split and a prompted VLM on 30 dev plans (state the API cost first); if the detector of experiment 2 is within 3 points of the U-Net on a subgroup, the detector is not yet earning its cost there.
4. **Degradation test.** Apply the scan-shift study's stroke thickening and blur to our dev images and re-score experiment 2's best arm; an AP50 drop of more than 10 points means a stroke-and-blur augmentation is the next fix.
5. **VLM check with numbered boxes.** Draw the detector's boxes numbered on an upscaled crop (views from `safe_tiles.py`) and ask a VLM yes or no per box; score as accept/reject precision at coverage, against agreement between detector and template matching alone; keep the VLM only if it adds more than 3 points of precision at the same coverage.
