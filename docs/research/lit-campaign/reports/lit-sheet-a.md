# lit-sheet-a: sheet normalisation and layout, field and state of the art 2025-2026 (scope L9, angle a)

Worker lit-sheet-a, 2026-11-14. Read-only. Every source below was opened by me on 2026-11-14 (URL in the log
`lit-sheet-a-log.md`, one line per source). **verified** = I read the number on the page or in the PDF text.
**reported** = the authors' own claim. **estimate** = mine. Papers whose HTML page returned 404 were read from the
downloaded PDF text. Earlier reports (stoa-hardimg, notes 01/02/03/08, lit-normalise, lit-degradation) are extended,
not repeated.

## 0. What the 2025-2026 field gives us, in six lines

1. **Sheet splitting is a detection problem, and the 2025-2026 papers solve it with a small box detector trained on a
   few hundred annotated sheets.** Best measured: RF-DETR (m) mAP50 0.949 on 9 layout classes (551 sheets), plan class
   AP50:95 0.969 (verified, 2607.18997). No paper handles our case (several residential plans on one raster sheet).
2. **Layout models pretrained on general documents hurt.** DocLayNet/DocSynth pretraining took a YOLO-family model from
   mAP50:95 0.772 (COCO init) to 0.589 on drawings (verified, same paper). Do not start from a document-layout checkpoint. The same ablation (Table 4) splits the loss in two: YOLOv10m (COCO) 0.772, DocLayout-YOLO architecture with COCO and random init 0.727, same architecture with DocLayNet and DocSynth weights 0.589 (verified), so the architecture costs 0.045 and the document pretraining another 0.138.
3. **Orientation: still no method for text-sparse drawings.** One 4-class page classifier is cheap and Apache-2.0
   (PP-LCNet_x1_0_doc_ori, 99.06 top-1 on a set the page does not name), but nobody reports it on line art.
4. **Upscaling: nothing new in 2025-2026 supports learned super-resolution for counting; one older counter-case exists (2312.13620: interpolation recall 32.74 vs jointly trained restorer 99.33 on badly degraded diagrams, verified), so learned SR stays an offline A/B on the bad-scan slice only.** The only CubiCasa5K
   test (2021, re-read) shows icon micro-F1 falling 0.886 to about 0.875 after x2 SR. A 2026 study shows that much
   of what tiling buys is higher input resolution, which a plain resize can give (verified, 2611.12657).
5. **Quality gating: 2025 adds one document-quality model with SRCC 0.86-0.91 on text pages (DocIQ, verified), and one OCR-confidence gate on 50 bridge plans (precision 97.14%, recall 87.18%); nothing on floor plans.**
6. **No 2025-2026 paper reports an exact count of plans per sheet, or a per-image exact count of doors/windows after
   preprocessing.** Every number here is a layout or segmentation metric, not our metric.

## 1. Top 5, ranked (floor-plan work and transfers in one list)

**1. Per-plan region detector for `plans` and for tiling: fine-tune RF-DETR (Apache-2.0) on one class "plan"** - verdict **try**.
- What: a box detector over the whole sheet whose boxes are the plans; each box is then cropped and counted. Fills
  `plans`, and gives the crops that stage 2 tiles.
- Evidence: FELD benchmark, 551 facade drawings at 300 dpi (3509 x 2480 to 14042 x 9934 px), resized to 1344 x 800 for
  RF-DETR (m): mAP50 0.949, mAP50:95 0.890, P 0.985, R 0.800, 22.3 FPS on a T4; plan class AP50:95 0.969, but the
  class has only 21 images in the whole dataset (26 boxes; about 3 test images at the 15% split, estimate), so that figure
  is close to anecdotal; YOLOv12 (m) gets 0.510 and Qwen3-VL-8B 0.330 on the same class (verified, arXiv 2607.18997
  Tables 1-3, read 2026-11-14). A second, independent route: WAFFLE fine-tunes a DETR on 200 images
  for floorplan/legend/scale/compass boxes (verified, WACV 2025 supplement; no metric given there).
- FELD itself: the paper text I extracted (2026-11-14) states no dataset or code release (grep for availability, licence, GitHub, Zenodo: nothing), so its 551 sheets cannot be assumed obtainable.
- Code Apache-2.0 (`gh api repos/roboflow/rf-detr/license`); N/S/M/L weights Apache-2.0 per the README, XL/2XL are PML
  (verified, README read). Leakage flag of the COCO-pretrained start: **no**. Leakage of the fine-tuned model: **no if
  trained on dev-split images only** (record 0003).
- Training data: no export of a per-plan box exists yet; it can be derived as the union of a plan's element boxes
  (context file says it is not exported yet). Labelling cost is zero once the union is exported.
- Training knobs (RF-DETR docs, read 2026-11-14): `resolution` is a settable integer, a multiple of 32 for the current
  detection checkpoints, so the plan detector need not stay at the README defaults; `batch_size="auto"` probes the GPU;
  the default augmentation is a horizontal flip, vertical flip and arbitrary-angle `Rotate` are configurable through
  `aug_config` (resolved 2026-11-14 from `aug_configs.py` and the augmentations page: the Albumentations path accepts `D4` and `SquareSymmetry`, the eight rotations-and-flips of a square, plus `Rotate`, `Affine`, `ShiftScaleRotate`, with boxes transformed automatically; presets `AUG_CONSERVATIVE` (under 500 images), `AUG_AGGRESSIVE`, `AUG_AERIAL`, `AUG_INDUSTRIAL`; needs `rfdetr[augment]`. D4 includes mirrors, which is right for a plan-region detector and wrong for anything that reads text); the docs' illustrative setups for 16 GB (T4) are batch 4 with 4 accumulation
  steps, for an unnamed model.
- The model's own paper (RF-DETR, arXiv 2511.09554, ICLR 2026, read 2026-11-14, verified): DINOv2 backbone found by weight-sharing architecture search, searched resolutions 320 to 960 px, evaluated on COCO and the 100 small RF100-VL datasets; its authors note small datasets may need more than 100 epochs to converge when the NAS-style "architecture augmentation" is on, and say that additional fine-tuning of NAS-mined models is optional. So plan for 100+ epochs on a small plan-box set, and treat resolutions above 960 px, which the search never saw, as untested (estimate).
- Maintainer guidance on small objects (RF-DETR issue #747, read in full): prefer a larger model size over raising the
  resolution of a small one, because the architectures come from a search that ties resolution to the model; for
  genuinely high resolution use slicing (a commenter points to SAHI). The Apache-2.0 ceiling is L (704 px); XL and 2XL need
  the PML extra. Issue #879 asks for a minimum detectable object scale and gets no number ("I don't know of a fixed bound").
  So the 5-20 px symbol question for this detector has no maintainer figure; it must be measured on our boxes.
- Repo facts re-read 2026-11-14 (FAQ page and `config.py`, issues #81, #1186; verified): at most `num_queries` = 300 objects per
  image by default (Nano to Large); raising it needs `num_queries` and `num_select` together plus a fine-tune, and costs
  compute quadratic in the query count. Harmless for a handful of plan boxes, a hard cap for symbol detection on dense
  plans. Background images (no boxes) are supported in COCO (listed without annotations) and YOLO (no label file), fixed in
  PR #915 (April 2026), so sheets with no plan can be negatives. Augmentation was a horizontal flip only at the time of
  issue #81 and is now configurable. Atto, Femto, Pico, XLarge and 2XLarge are PML 1.0 (`rfdetr[plus]`), only Nano to Large are Apache-2.0.
- A pretrained reference point for the same job (HF card, reported only): a YOLO11x sheet-layout detector reports drawing_area mAP50-95 0.885 on 694 boxes in 178 images at 1472 px input, i.e. about four regions per image, the same shape as several plans per sheet (row 27). Not usable for scored runs (AGPL library, data not named), but it shows a per-region detector at 1472 px is reachable.
- Dependencies of `pip install rfdetr` (pyproject.toml read): torch, torchvision, supervision (MIT); training extras
  pytorch-lightning, torchmetrics (Apache-2.0), ultrafast-pycocotools (BSD-2), optional albumentations (MIT, repo
  archived), optional transformer-engine (Apache-2.0). No AGPL or GPL dependency found.
- Input / memory: default input N 384, S 512, M 576, L 704 px square (README table, verified). A 12 GB card trains the
  M model at those sizes (estimate). Hours to a first number on our dev boxes: about 2-3 including the export
  (estimate). Our dev images are small (median 855 px), so plan boxes can be found at 576-704 px; the symbols inside
  are not found at that size, which is why the crop is then re-run at native scale.
- What breaks: FELD is facade sheets with big frames and title blocks; our sheets are often only plans with no frame.
  Two plans touching each other with a shared dimension line give one merged box; a plan that is cut by the image edge
  gives an under-count. RF-DETR gotcha: `predict()` resizes without antialiasing and the default training backend
  antialiases (closed issue #1516 in the repo, read 2026-11-14); thin line art is exactly where that mismatch shows.
  Rectangular input is not officially supported yet (open issue #1052), so wide sheets get squashed to a square.

**2. A resolution policy instead of super-resolution: deterministic upscale, then one pass at the highest trainable
resolution, tiles only to add to it** - verdict **try**.
- Evidence: on VisDrone a single pass trained at a higher resolution beats sliced inference with box fusion for every
  detector that could be trained at that resolution, and at equal compute resolution helps more than a larger model;
  the coverage-weighted dense fusion (SCAHI) beats box fusion on identical passes and adds 4.3-5.6 mAP50 over the best
  single pass at 2048 px on DOTA (verified, arXiv 2611.12657, Nov 2026). It is about aerial images; it measures no
  drawing. It supports ordering the experiments: first raise the input size (upscale small plans with Lanczos), then
  tile.
- Counter-evidence on learned SR for floor plans: the CubiCasa5K authors' network on 90 low-resolution plans, x2 SR with
  EDSR/ESPCN/FSRCNN/LapSRN: room micro-F1 0.305 to about 0.46, icon micro-F1 0.886 to 0.874-0.875, with toilet 0.159 to
  0.099-0.117, sink 0.159 to 0.079-0.081, bathtub 0.989 to 0.910; window 0.025 to 0.097-0.109, door 0.015 to 0.036-0.038
  (verified, Tables 2-3 of arXiv 2112.09844, 2021). The same paper measures no false positives. EDSR took 215-745 s per
  image on a T4 (verified, Table 1). This is a 2019 segmentation network, so it is weak evidence for a fine-tuned detector,
  but it is the only floor-plan measurement of SR and it goes the wrong way for the symbols we count.
- 2025 evidence from scene text, the closest measured SR-versus-recognition test: with a text-spotting model (ABCNet v2)
  on degraded images, Real-ESRGAN and SwinIR raise detection F1 (Level 1: 44.42 raw to 57.13 and 55.25) but lower the
  end-to-end score without lexicon (24.29 raw to 21.45 and 22.70; Level 2: 20.49 to 18.31 and 17.82); the authors call the
  cause "text-image hallucination" (verified, TAIR paper arXiv 2506.09993 Table 2, read 2026-11-14; SA-Text benchmark, 2025).
  A January 2026 text-SR paper says diffusion SR yields "distorted glyphs, missing strokes, or hallucinated characters"
  (verified from its introduction, arXiv 2601.17340, ICASSP 2026). Reading the pair: SR helps find things and hurts
  reading them exactly, which is our failure direction (counts are exact).
- The strongest counter-evidence, now verified from the full text (arXiv 2312.13620, Table 1, eight single-line-diagram symbol
  classes, low-quality diagrams of about 1000 x 650 px at random degradation, x4): interpolation gives precision 85.78 and
  recall 32.74; SRGAN 97.27 / 85.19; ESRGAN 97.73 / 88.93; the authors' task-jointly trained restorer 98.87 / 99.33.
  The authors also report that an independently trained ESRGAN turned hollow circles into solid ones and the detector then
  missed those symbols (verified), and that SSIM was higher for the worse restorer (0.6187 against 0.5577). So on badly
  degraded drawings plain interpolation can fail badly, while a restorer trained jointly with the recogniser can win; no
  false-positive count is given and the code licence is unknown. Reading: keep Lanczos as the default, and treat a jointly
  trained restorer as an offline A/B for the gated bad-scan slice only, scored by "did any count change".
- Code: MIT for the SR repo (`gh api`); its CubiCasa5K weights are the 2019 weights: **leak yes**. Do not use.
- What breaks: Lanczos does not recover a 5 px symbol; it only gives the detector more pixels per symbol. A detector
  trained on native-scale crops and run on upscaled inputs shifts scale: train and test at the same upscale factor.

**3. Orientation as a vote: closed-vocabulary OCR over four rotations + PP-LCNet_x1_0_doc_ori + detector four-rotation
agreement, abstain on disagreement** - verdict **try (measure first)**.
- Recognition-driven page orientation (RD-POD, 2009, read in full): run the OCR line recogniser on a few lines (3 best
  lines) at each of the four orientations, score each by the words-in-dictionary ratio, pick the best, reject when the
  score is flat. Reported 99.7% on UW-1 and above 99% on three other sets, with rejections instead of errors; the
  authors state the classical ascender/descender asymmetry methods fail on "plain capital text", which is what plan
  labels are (verified, Rangoni et al., DFKI/IUPR PDF, read 2026-11-14; the paper is not 2025-2026 and is on book
  pages, so no number carries over). Our version: the dictionary is the closed Finnish label list (MH, OH, K, KH, PH, WC,
  S, PARV, ...), the recogniser is the RapidOCR already measured, the score is the count of exact label hits at each
  rotation. Leptonica's `pixOrientDetect` and `pixMirrorDetect` are the classical options and rely on that same
  ascender signal (header of flipdetect.c read; BSD-2 text in the file, the API says NOASSERTION); expect them to fail
  on capitals and to need text.
- Mirror: no learned or classical mirror detector exists for text-free drawings; Leptonica's tests text asymmetry only
  (verified from the source header). Mirrored copies therefore stay a training-augmentation problem (flip augmentation).
- What breaks: labels of 5-10 px are the measured OCR misses (RapidOCR 23-81% exact by room type), so the vote fails
  exactly on small plans; run the OCR on a 2x Lanczos copy for the vote only. Single capital letters ("K", "S")
  match noise, so count only labels of two letters or more.
- Field report on rotated labels (PaddleOCR discussion 17325, Dec 2025 to Mar 2026, read with replies 2026-11-14; user reports, not measurements): on architectural drawings rotated text is often flipped or misread, fine-tuning the recogniser did not help, the corner order of rotated detection boxes was suspected, and a maintainer's demo run with the text-line orientation classifier on looked fine; a March 2026 reply has the same problem with arbitrary angles and no fix. Newer OCR exists: PaddleOCR 3.7.0 (2026-06-11, README read, Apache-2.0) ships PP-OCRv6 in tiny (1.5M), small (7.7M) and medium (34.5M) tiers with +4.6% detection and +5.1% recognition over PP-OCRv5 on the vendor's own benchmarks (reported, not on drawings); issue 18268 (Nov 2026, closed) reports occasional corrupted output when one PaddleOCR object is shared by several threads, so give each worker its own instance. Re-measure the vote's OCR on our room labels before trusting either version. So the room-label vote must read labels in the four axis-aligned rotations of the whole crop, not rely on the OCR's own per-line rotation handling.

Component 3b, the page classifier: PP-LCNet_x1_0_doc_ori, measured on our images before it is trusted -
verdict **maybe**.
- What: a 7 MB classifier for 0/90/180/270 (verified, PaddleOCR page and model card). Complements the text-line 0/180
  classifier already in stoa-hardimg. Top-1 99.06; 3.24 ms CPU (normal mode), 1.19 ms (high-performance mode), 8
  threads Xeon, FP32; evaluation set (PaddleX module page, read 2026-11-14, verified): a self-built multi-scene set of 1000 images, ID cards and documents, so 99.06 says nothing about line-art plans; input size not stated on the page.
- Licence: code Apache-2.0 (PaddleOCR, PaddleX `gh api`; PaddleOCR requirements.txt and the PaddleX/PaddleOCR pyproject read: no PyMuPDF, Ultralytics or other AGPL/GPL dependency listed); weights Apache-2.0 (model card front matter, read by curl).
  Leakage: **unknown** (training data not stated; a document model, so CubiCasa5K is unlikely, but unverified).
- What breaks: its own docs and a Rust port both flag it as a text-dense-page model. A Rust library that wraps it (Kreuzberg 4.9.0
  `doc_orientation.rs`, source read 2026-11-14) resizes the short side to 256, centre-crops 224 x 224, uses BGR ImageNet
  normalisation, a minimum confidence of 0.35, and its comment says the correct class gets about 45% against 25% chance
  (verified source comment, the authors' own observation, not a benchmark). A 224 px centre crop of a 855 px plan shrinks
  an 8 px label to about 2 px and drops the margins, so expect near-chance output on our images unless the crop is
  replaced by text-bearing tiles. On a plan with five labels at 8 px it will be near chance; on a plan
  with no text it has nothing to look at. Treat its output as a vote, not a decision.
- Use: run it, then confirm with the detector's own 4-rotation agreement (CubiCasa's four-rotation handling is also what
  the 2026 SALI-FP comparison retained for the 2019 checkpoint, verified in its protocol text). Exact 90-degree
  multiples make a disagreement between the two a clean abstain signal (estimate).

**4. Evidence-triggered local re-read for plans that disagree** (BlueprintAgent pattern) - verdict **maybe**.
- What: engineering constraints are written as validators; a conflict report triggers a targeted second look at the
  local region. On 300 real scanned structural blueprint sheets: beam F1 0.994 against 0.301 for single-pass zero-shot
  MLLM and 0.820 for a fixed pipeline (verified in Table 1 of arXiv 2609.07362, re-read in full 2026-11-14: single run, macro average over 20 projects, GPT-5.4 without fine-tuning, the full system reaches 1.000 on four other metrics, so the benchmark is near its ceiling and the authors' own data, not independent). Not a floor-plan
  paper; the ordering matches our stage 8 (independent second count that feeds `conflicts`).
- Why for our scope: a conflict between plan-box count and element clusters is the cue for a re-crop. Whole-sheet
  downsampling "drops small text and dense annotations" is the paper's own diagnosis of the failure that the crop fixes.
- Ablations (verified, Table 2 of the same paper): without axis-aware cropping Col F1 falls 1.000 to 0.838 and Beam F1
  0.994 to 0.674; without pasting the global axis labels back onto the crop 0.827 and 0.896; without the cheap
  deterministic span-ratio check (pixel ratio of adjacent spans against annotated ratio, tolerance +-15%) 0.831 and
  0.828. Reading: a crop must keep the context that fixes its meaning, and a cheap arithmetic check catches a class of
  failure the model does not. For us the crop of rank 1 would carry its sheet position and neighbouring plan boxes.
- Code and weights: none found on the paper page. Idea only. Leakage: not applicable.
- What breaks: the loop needs an MLLM per conflict; we have no licence-clean local one measured on plans (lit-vlm
  scope L7). The cheap version is a deterministic re-crop at 2x and a re-run of the detector.

**5. Learned document-quality scoring (DocIQ pattern), only as a gate input** - verdict **maybe (skip for the hackathon)**.
- Evidence: DocIQ, ResNet50 on 1600 x 1600 layout-masked input, average SRCC 0.8704 and PLCC 0.8999 over the three
  DIQA-5000 dimensions; on the OCR-accuracy dataset SmartDoc-QA SRCC 0.9086 (character accuracy) and 0.8989 (word accuracy),
  80/20 split (verified, arXiv 2509.17012, Sep 2025). The earlier CG-DIQA numbers (LCC 0.65-0.92) stay the baseline.
- No code or weights are named in the paper text I read. Trained on phone-captured text pages, so a score has no
  meaning for a plan with 5 px symbols.
- Localised quality beats a page score (2026 master's thesis citing DocIQ, University of Ljubljana, green open access,
  read from the PDF abstract and results text): a model that predicts a per-word recognition-error heatmap plus a mask of
  semantic regions reaches document-level SROCC 0.91 on unseen invoice templates, and for judging a page acceptable from
  its important regions AUC 0.92 against 0.76 for the theoretical best page-level score (verified, abstract). Direct transfer to
  SmartDoc-QA without adaptation fails (SROCC -0.31, the ranking is reversed). Invoices, synthetic training set of 2,299;
  not drawings. Reading for us: gate on the crop that matters (a plan box, a label crop), not on the whole sheet.
- The one gate evaluated on drawings (2025, read in full): a Tesseract average token-confidence threshold of 80 on 50
  bridge-plan PDFs labelled high or low quality gave precision 97.14% and recall 87.18% for the quality class; dropping
  the low-quality drawings raised extraction precision by 17.84 points and recall by 18.96 points; the review aid
  highlighted 36.81% of table cells (verified, Pang and Zhang, AHFE 2025 vol. 199, pp. 2212-2222, PDF read 2026-11-14).
  Small set (50), text-heavy PDFs, and the threshold was tuned on the same data. For us the analogue is the RapidOCR
  mean confidence on label crops plus the label-hit count of rank 3: it costs nothing once OCR runs.
- Use instead: the free signals from rule 5 of stoa-hardimg (short side, Laplacian variance, full-pass versus tiled-pass
  agreement) plus the new one from this scope: **agreement between the plan-box detector's count and the element-cluster
  count**. Only the 50-plan OCR-confidence gate above evaluates a gate on drawings; none on floor plans.

## 2. Full table

Columns: method; our field or the field it transfers from; year, venue; code (licence); weights (licence); training
data; metric and benchmark; input; leakage; JSON field; verdict. "-" = not stated on the page I read.

| # | Method | Field | Year / venue | Code (licence) | Weights (licence) | Metric, benchmark | Input | CubiCasa5K leak | Field filled | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | RF-DETR M, layout classes | AEC sheet layout (transfer) | 2026, EC3, arXiv 2607.18997 | rf-detr (Apache-2.0) | N/S/M/L Apache-2.0 | mAP50 0.949 / 0.890 (50:95), 551 facade sheets, plan AP50:95 0.969 (21 imgs in all) | 1344 x 800 in paper; default 576 px sq | no (COCO init) | `plans` | try |
| 2 | Faster R-CNN R50-FRN, layout | same | same | implementation not named in the paper (torchvision, BSD-3, has a plain Faster R-CNN; the FRN variant is not torchvision) | COCO init, licence not stated | mAP50 0.930, recall 0.924 | 1344 x 800 | no | `plans` | maybe (cheaper recall) |
| 3 | YOLOv12 (m), layout | same | same | Ultralytics (**AGPL-3.0**) | AGPL | mAP50 0.871; plan AP50:95 0.510 | 640 sq | no | - | skip (licence, and poor on plan class) |
| 4 | DocLayout-YOLO (DocLayNet-pretrained) | document layout (transfer) | same paper | opendatalab (**AGPL-3.0**) | AGPL | mAP50 0.675 on FELD; ablation 0.589 vs 0.772 COCO-init YOLOv10m (50:95) | 640 sq | no | - | skip: licence + domain interference |
| 5 | Qwen3-VL-8B (LoRA) layout grounding | VLM (transfer) | same paper | Qwen3-VL (Apache-2.0) | card Apache-2.0 | F1 0.911, mAP50 0.758, 6.1 s per drawing on A100 | 1344 x 800 | no | `plans` | skip (latency; plan class 0.330) |
| 6 | YOLOv11-det, views/title/notes | mechanical multi-view sheets (transfer) | 2025-26, ICIEA 2026, arXiv 2510.21862 | Ultralytics (**AGPL-3.0**) | AGPL | normalised confusion 0.96 views, 0.99 title, 0.98 notes; 1,000 drawings, 80/20 | - | no | `plans` | skip (licence); shows the idea at 0.96 |
| 7 | MobileNetV3 Faster R-CNN title block | engineering drawings | 2025, EC3, arXiv 2504.08645 | not found | not found | title block acc 0.971, main content 0.943 at IoU 0.70; 1,385 drawings | 300 dpi rasters | no | none for us | skip |
| 8 | YOLOv8-S metadata regions | engineering archives | 2026, arXiv 2602.13345 | repo not opened (Ultralytics, AGPL) | - | 89.5% mAP50:95, 750 held-out drawings, 5.2 ms A100 | - | no | none | skip |
| 9 | PP-LCNet_x1_0_doc_ori | document orientation | 2024-25 PaddleOCR 3.x | PaddleOCR/PaddleX (Apache-2.0) | Apache-2.0 (HF card) | top-1 99.06, eval set not stated; 3.24 ms CPU | - | unknown | orientation (no field) | maybe |
| 10 | "Seeing Straight" 12-class rotation | document orientation | 2025-26, arXiv 2511.04161 | not found | not found | 4-class: 96.81% ORB-En, 92.68% ORB-Indic; 12-class: 98% / 96.71%; about 304M parameters, 0.5 s on an H100 (verified, text and Table 4; ORB = 1,863 rotated text pages); weights "made available upon acceptance", not released | Phi-3.5-Vision encoder, dynamic crops | no | orientation | skip (heavy; text pages) |
| 11 | Zernike moment features + graph net | floor plans (our field) | 2025, IPVE, arXiv 2504.03241 | none stated | none stated | rotated CubiCasa5K (45 deg, 80 test plans): avg F1 67.01 vs 50.70 without normalisation (average excludes outer space); window F1 78.25 vs 24.82, door 83.44 vs 36.81; upright CubiCasa5K window F1 91-98 with the same features; **scanned CVC-FP (122 plans, never rotated): window F1 3.72-12.69, door 1.87-3.04 in every setting** (verified, Tables 1-2) | - | **yes** (trained on 280 CubiCasa5K plans) | none | skip (45 deg, not 90; no code) |
| 12 | CAB1/CAB2 multi-unit segmentation | floor plans (our field) | 2024-26, arXiv 2408.01526 | multi-unit-floorplan (Apache-2.0) | not stated | CubiCasa5K mean F1 0.86, IoU 0.76 | multi-scale, 254-5052 px sources | **yes** (trained on 560 refined CubiCasa5K plans) | none (no per-unit split in paper) | skip |
| 13 | SR before the 2019 network | floor plans (our field) | 2021, arXiv 2112.09844 | rbg-research (MIT) | 2019 CubiCasa5K weights | icon micro-F1 0.886 to 0.875; room 0.305 to 0.46; 90 plans | x2 | **yes** | none | skip |
| 14 | Restoration with GLCM patch routing + ESRGAN | electrical diagrams (transfer) | 2023-24, arXiv 2312.13620 | repo named in the paper exists (last push 2024-02, ~32 MB) with no LICENSE file (API 404, retried 2026-11-14): all rights reserved by default, so read-only evidence | not found | Table 1 (verified): interpolation 85.78 / 32.74, ESRGAN 97.73 / 88.93, proposed 98.87 / 99.33 (precision / recall); no restoration-free detector baseline | 200 x 200 patches, x4 | no | none | maybe, offline A/B on the bad-scan slice only: no false-positive metric; one case turned hollow circles solid; code licence not found |
| 15 | DocIQ no-reference scorer | document quality (transfer) | 2025, arXiv 2509.17012 | not found | not found | SRCC 0.8704 avg DIQA-5000; 0.9086 SmartDoc-QA char acc | 1600 sq | no | gate | maybe (idea) |
| 16 | SCAHI dense fusion | aerial small objects (transfer) | 2026, arXiv 2611.12657 | abstract says code is released, no URL in the text I extracted | n/a (inference) | DOTA +4.3 to +5.6 mAP50 over best single pass at 2048 px | 2048 | no | counts | maybe (L2 owns the detail) |
| 17 | ROI-gated SAHI | aerial (transfer) | 2026, arXiv 2608.23923 | no repo link found in the text; cites Ultralytics (AGPL) in its references | n/a | COCO128 (128 images) mAP50 0.6602 vs 0.7569 full SAHI, static gating speed ratio 0.88 (slower), adaptive policy 1.02x, mean 3.41x on a three-image sparse case study (verified) | - | no | - | skip (lower mAP; speed-up only on sparse scenes) |
| 18 | BlueprintAgent revisit loop | structural blueprints (transfer) | 2026, arXiv 2609.07362 | none found | none found | beam F1 0.994 vs 0.301 zero-shot, 300 sheets | - | no | `conflicts` | maybe (idea) |
| 19 | DETR doc-table base, fine-tuned for floorplan/legend/scale/compass | floor plans (our field) | 2025, WACV, WAFFLE supplement | facebookresearch/detr (Apache-2.0) | base card Apache-2.0 | no metric stated | - | no (Wikimedia plans) | `plans` | maybe (200 images was enough to ship) |
| 20 | Evidence-gated parsing SALI-FP | floor plans (our field) | 2026, arXiv 2609.25615 | not found | not found | 11,534 plans produced outputs; official CubiCasa5K protocol | 512 px working res for registration | **yes** (evaluates on CubiCasa5K) | `rooms` | out of scope (L1/L10); calls an image-editing model |
| 21 | BlueprintParse-R50 (Faster R-CNN R50-FPN v2, 5 fixture classes) | floor plans (our field, Korean plans) | 2026-11, HF model card | export/inference script in the repo (Apache-2.0 per card) | Apache-2.0 (card) | test split 1,014 plans mAP50-95 0.926, AP50 0.9805; **53 novel plans mAP50-95 0.7875, AP50 0.922; per-drawing exact count of all 5 classes 0.566 (95% CI 0.434-0.698), MAE 0.1925 per class cell** (score threshold 0.8; exact match 0.684 even on the drawings the model did not flag; card re-read 2026-11-14); AI-Hub Korean drawings, 7,900 train | grayscale, long side <= 2048 | **no** (not CubiCasa5K; the training set is a non-redistributable Korean dataset, so record 0003's non-commercial rule applies until its terms are read) | toilet, sink, bathtub, gas range (`elements`) | maybe, as a zero-shot second counter; the exact-count number is the first one I found on unseen plans |
| 22 | floorplan-door-detector-rfdetr (RF-DETR S, door) | floor plans (our field) | 2026-10, HF model card | runner AGPL-3.0-only | weights Apache-2.0 | no metric read in the part of the card I opened | 768 px tiles, stride 384, model 512 px, conf 0.3, PDF at 150 dpi | **unknown** ("public floor-plan datasets", not named: treat as leaking until shown otherwise) | `elements` door | skip for scored runs |
| 23 | PP-DocLayout-L / PP-DocLayout_plus-L, docling-layout-heron (document layout) | document layout (transfer) | 2025 | PaddleX / docling (Apache-2.0 by their cards) | Apache-2.0 (HF cards) | trained on papers, magazines, books (card text); no drawing result | - | unknown (not CubiCasa5K by description) | - | skip as initialisation: the FELD ablation says document-layout pretraining hurts on drawings |
| 24 | docTR MobileNetV3-small page / crop orientation (4 classes each) | document OCR | docTR docs (current) | mindee/doctr (Apache-2.0, `gh api`) | weights: the ONNX port of the page-orientation model is tagged Apache-2.0 on Hugging Face (tag read via API 2026-11-14; the original docTR files come from the project's GitHub releases, licence file not opened) | no orientation accuracy of its own re-read; in "Seeing Straight" Table 3 (SROIE field accuracy) docTR OCR falls to 15.63 on rotated pages and recovers to 63.11 after the authors' rotation module (verified); the earlier hardimg report's 63.28 figure was not found in the text I read | 512 x 512 example input in docs | unknown | orientation | skip: weak on the one benchmark that compared it; the crop-orientation model is the interesting part for vertical labels |
| 25 | Fourier radial-projection deskew (jdeskew) | document skew (transfer) | 2026-03, arXiv 2603.05942 | github phamquiluan/jdeskew (MIT, `gh api`) | n/a (classical) | AED 0.14 / 0.12 degrees at image height 1024 / 2048 in its block-size ablation (Table 1; DISEC13 data, verified from the table text) | height resized to 1024-4096 | no | residual skew | maybe, only if scans show small skew; a drawing's walls give a cleaner angle by Hough than a text spectrum |
| 26 | Pretrained ViT (800 x 800 tiles) / GAT on vector graph, whole-drawing classification | AEC drawing classification (transfer) | 2025, EG-ICE, Strathclyde repository PDF | not found | not found | 450 drawings, 4 labels; "Representation" (plan / section / site plan) accuracy 0.916 pretrained ViT, 0.895 GAT, 0.642 ViT from scratch; "Level" (floor) 0.600 / 0.737 / 0.4; average 0.847 / 0.853 / 0.674 (verified, Table 3) | tiles 800 x 800, sheets 2,000-20,000 px, text removed first | no | view type, storey (`plans`) | maybe for "is this sheet a plan at all"; floor level is weak (0.60-0.74) |
| 27 | GreenMap yolo11x-blueprint-layout-detector (classes drawing_area, legend_block, title_block) | architectural and construction blueprints | 2026-07, HF model card (read in full 2026-11-14) | Ultralytics (**AGPL-3.0**; the card's Apache-2.0 tag covers the file, not the library) | `yolo_layout.pt`, card says Apache-2.0 (licence of the inherited YOLO11 weights is not settled: Ultralytics weights are AGPL) | val 178 images, 958 instances: mAP50 0.984, mAP50-95 0.921; drawing_area 694 boxes (about 3.9 per image) mAP50 0.988, mAP50-95 0.885, P 0.952, R 0.978 (reported, card only, no paper, training data not named) | 1472 x 1472 | **unknown** (training data not named) | `plans` (as drawing_area: several per image) | skip for scored runs (AGPL, unknown data); useful as a reference for what a per-region detector reaches at 1472 px |
| 28 | Voix7 rtdetrv2-floorplan-v2 (RT-DETRv2 R50, classes window, door, stair) | floor plans (our field) | 2026-07, HF model card (read in full 2026-11-14) | transformers (Apache-2.0) | Apache-2.0 (card) | eval mAP 0.666, AP50 0.758; small 0.552, medium 0.806, large 0.415; AP window 0.771, door 0.685, stair 0.542; AR100 door 0.945 (reported, card is auto-generated, dataset 'unknown', no input size) | not stated | **unknown** (dataset not named: treat as leaking) | `elements` window, door | skip for scored runs; useful only as evidence that RT-DETRv2 (Apache) reaches AP small 0.55 on floor plans |
| 29 | GreenMap yolo11x-blueprint-wall-detector (oriented boxes, class wall) | construction blueprints | 2026-08, HF model card (read) | Ultralytics (**AGPL-3.0**) | card says Apache-2.0 (same caveat as row 27) | val 109 images, 1716 walls: mAP50 0.962, mAP50-95 0.848 (reported) | 896 x 896 | **unknown** | none of ours (walls are not asked) | skip |

## 2b. Field facts re-read from the CubiCasa5K paper (arXiv 1904.01920, read 2026-11-14, PDF text)

- The 5,000 plans come from about 15,000 mostly Finnish real-estate images and are split into three sub-categories,
  high quality architectural 3,732, high quality 992, colorful 276 (verified). Source image resolutions range up to
  about 8,000 px on a side (Fig. 2 axis, verified from the figure's scale only).
- "Single image annotation took from 5 to 120 minutes, depending on the complexity and clearness of the source and
  amount of floors" (verified): the annotators themselves expect several floors per image, which fits our 1-in-5
  multi-plan sheets, and the paper offers no splitting step.
- The authors trained with 90 degree rotations, colour jitter and crop-or-scale to 256 x 256, and their test-time
  augmentation feeds the same image four times rotated by 90 degrees and averages the four predictions (verified).
  Training took 3 hours on a GTX TitanX (verified). So the 2019 network was already rotation-trained; our measured 53.1%
  includes that 4-rotation TTA.
- Open consequence for gating: the three sub-categories are a free style label on dev images (which folder), but the
  question set does not necessarily tell us the folder at answer time. Whether it does is for the orchestrator to check.

## 2c. What input sizes the 2025-2026 work actually used (verified from each paper or card, read 2026-11-14)

| Work | Task | Input | Note |
|---|---|---|---|
| Raster2Seq (arXiv 2602.09016) | floor plan to polygons, CubiCasa5K-based | fixed 256 x 256 for all datasets | the training set grows to 6,281 samples; so the best-known raster-to-vector model sees 256 px (symbols a few pixels) |
| FloorplanVLM (arXiv 2602.06507) | floor plan to JSON with a VLM | longer edge scaled to 1024, aspect kept | coordinates normalised to that size |
| BlueprintParse-R50 (HF card) | toilets, sinks, bathtubs, gas range | grayscale, long side at most 2048 | exact-count rate 0.566 on 53 unseen plans |
| FELD / RF-DETR m (2607.18997) | sheet layout | 1344 x 800 | authors say plain resizing loses thin lines and small text |
| FloorYOLO (Frontiers 2026) | symbols on SESYD and CVC-FP | 640 x 640 | |
| DocIQ (2509.17012) | quality score | 1600 x 1600 | |
| door-detector card (RF-DETR S) | doors | 768 px tiles, stride 384, model 512 px | tiles are shrunk by a third before the model sees them |
| Docling layout models (2509.11720) | text-page layout, 17 classes, Apache-style permissive release | RT-DETRv2 / D-FINE, images resized to 640 x 640 | trained on 150k text documents (no drawings); read 2026-11-14; reference point only: a layout detector at 640 px is not a plan splitter |
| MitUNet (2512.02413, v3 April 2026) | wall segmentation, CubiCasa5K plus a regional set | 512 x 512 | authors call it enough for thin walls and hatching; augmentation rotation within 15 degrees, scaling 0.9-1.1; read 2026-11-14, code MIT (gh api); leakage flag for any CubiCasa5K-trained weights: yes |
| Zernike paper (2504.03241) | segmentation of rotated plans | not stated; rotated copies placed on an enlarged canvas | |

Reading: two of the best-known recent floor-plan models run at 256-1024 px, below our median sheet of 855 px; none reports
what it does to symbols of 5-20 px. That is an argument for rank 2 (resolution first) and a reason to distrust any
published floor-plan number as a count predictor. Multi-floor plans are explicitly future work in the multi-unit paper
("align the individual storey floor plans", arXiv 2408.01526, verified).

## 2d. Where each pick plugs into record 0005 (read from docs/PIPELINE.md, 2026-11-14)

- Stage 6 Normalise already lists "fix rotation (0, 90, 180, 270)" and "split a sheet into its plans" as its jobs, and
  the stage table gives "rotation, rendering, plan split" as what is still to build. Rank 3 (orientation vote) and the
  plan splitter of rank 1 are therefore stage functions of stage 6, not new adapters.
- Stage 7 raster extractor is the `hello` stub today (CubiCasa element F1 0%); the detector and OCR adapter that replace it
  would take the crops that stage 6 returns. Rank 2 (resolution policy) is a property of that adapter's input, and it
  decides whether stage 6 returns upscaled crops or native ones.
- Stage 8 second count is where rank 4's disagreement logic and the plan-count versus element-cluster check would sit.

## 3. From other fields: the transfer notes

(Angle b covers the adjacent fields in depth; these are what turned up while reading, with what breaks on our images.)

- **AEC facade drawing layout detection -> per-plan boxes.** Our object: a plan on a sheet. Why it should transfer: same
  "several views, one image" structure, the best paper's plan class reaches 0.969. Breaks: their sheets are 300 dpi and
  3.5k-14k px, ours median 855 px; their plan class has 21 images in all; no sheet frame; Finnish captions vary.
  Code and weights work as they are for the detector, but the labels must come from our export. Ranked 1.
- **Mechanical multi-view drawings (view / title block / notes).** Same decomposition, 0.96 normalised view recall from a
  YOLO model. Breaks: AGPL detector; views there are orthographic projections with whitespace between them.
  Only the idea transfers.
- **Document-layout pretrained models (DocLayNet family).** Measured negative transfer: 0.589 vs 0.772. Do not use as
  initialisation (verified).
- **Aerial small-object detection (tiling versus resolution).** Same problem shape (5-20 px objects). Breaks: aerial
  objects are textured blobs, ours are thin strokes lost by a bad resize; the antialias mismatch above matters more than
  in aerial imagery. Code: the idea, plus the repo; weights not needed.
- **Phone-document quality scoring.** The scores correlate with OCR accuracy on text pages. Breaks: a plan has no text
  baseline to degrade; a quality score trained on text would call a clean small plan "bad". Idea only.
- **Scan-domain collapse, measured on floor plans (Zernike paper, Tables 1-2, re-read in full):** the same CubiCasa5K-trained
  graph classifier scores window F1 91-98 and door F1 93-95 on upright CubiCasa5K plans, 77-79 and 79-88 on the same
  plans rotated 45 degrees, and 3.7-12.7 and 1.9-3.0 on the 122 scanned CVC-FP plans. Different data style, not rotation,
  is what breaks it. It is a feature-and-graph model on vectorised polygons, so it is no verdict on a pixel detector, but it
  is a reason to put scan-style evidence into the gate and the A/B plan.
- **Compound-figure panel detection (scientific papers; FigEx2, arXiv 2601.08026, Jan 2026, PDF read):** one image holding
  several labelled panels is our "several plans on one sheet". A DAB-DETR-based detector gets mAP@0.5:0.95 0.751 on
  BioSci-Fig-Cap (5,290 train figures, 3,959 test panels) and transfers zero-shot to physics and chemistry figures
  (verified, abstract and Table 1). Code is public at the URL in the paper (no LICENSE file found: the licence API returns 404). What breaks: panels there carry printed letters
  (A, B, C) and white gutters that the detector can use; our plans carry neither, and the counts are exact, while mAP is a
  box metric (no plans-per-image accuracy reported). Idea and recipe only; the detector choice stays rank 1.
- **Structural blueprint agents.** The "targeted revisit on a conflict" idea transfers to stage 8. Breaks: needs an LLM.
- **Electrical layout plans (45 plans, YOLOv8, mAP50 81.12)** (arXiv 2508.10449, verified): shows a counting-oriented
  floor-plan paper using flip/rotation/random-crop augmentation; no tiling, no image sizes; Ultralytics AGPL; the code
  repo licence read as 404. One line for scope L2.
- **Synthetic-to-scanned gap for floor-plan symbols (FloorYOLO, Frontiers in AI, Sept 2026):** an attention YOLOv8n gets
  mAP50 0.9950 and mAP50:95 0.9794 on the synthetic 16-class SESYD set and mAP50 0.8241 on the 122 scanned CVC-FP plans
  (baseline YOLOv8n 0.8116); 640 x 640 input, 30 epochs (verified, paper text read 2026-11-14). AGPL detector, so idea
  only; it supports putting the scan-quality gate in front of any model that was tuned on clean renders.
- **A measured exact-count check on unseen plans (BlueprintParse-R50 card, 2026-11):** a detector with mAP50-95 0.926 on its
  own test split gets only 0.566 per-drawing exact match across five fixture classes on 53 novel plans, and the error-flag
  recall is 0.478 (verified, model card read 2026-11-14). It is the same shape as our problem (counts, exact, new
  styles). Lesson for this scope: a box-AP number from a same-distribution split overstates the exact-count rate by a lot,
  and an uncertainty flag that catches under half the errors is not a gate. Weights are Apache-2.0 per the card but the
  training data is a closed Korean set (scope L2/L3 owns the verdict).
- **Pointers only (other orchestrator's scopes):** AECV-Bench exact counts (2601.04819, L7); SALI-FP (2609.25615, L1/L10);
  FloorplanVLM (2602.06507, L1); "Why VLMs miss small objects" (2610.09313, L7: splitting versus zooming rule);
  ResPlan-FP vectorisation (2608.25608, L1). Read only for input sizes and stated limits (2601.04819, 2602.06507, 2608.15032, 2609.25615) or title and abstract (the rest).

- **Map sheet layout (adjacent field, one paper; arXiv 2510.08385, SIGSPATIAL GeoSearch 2025, read in full 2026-11-14, verified):** a layout model crops the legend area, then GPT-4o with 5-20 in-context examples predicts legend item and description boxes; 40 scanned geological maps, F1 0.82 (5 examples) rising to about 0.88 (15), slightly lower at 20 (IoU 0.5). Transfer: a sheet's non-plan regions (legend, title block) can be cut off by a layout box before counting, and a VLM with few examples is a fallback for odd layouts. What breaks: 40 maps, closed-model API, no count metric, and our sheets often have no legend. Other map-layout hits (2604.22539, 2610.35606, 2507.20632) were opened and are off-topic (cartography survey, map reconstruction, colormap recovery).

- **Newspaper page into articles (adjacent field, arXiv 2607.15082, read in full 2026-11-14, verified):** a page holds many regions of one kind, the same shape as several plans on a sheet. Two systems on 2-12-page issues resized to height 2500 px: a detector pipeline (YOLO26, 1024 px input, 250 epochs, best at epoch 116 after 15 hours) with a cut algorithm for separating articles, and an end-to-end hierarchy transformer. Pipeline: article F1 80.39, mIoU 88.82; transformer: F1 70.69 but Jaccard on article counts 89.00 against 86.19 for the pipeline. Transfer: the box-quality metric and the count metric rank the two systems differently, so score a plan splitter on count of plans per sheet, not only on box overlap. What breaks: YOLO is AGPL (our rank 4 stays out); the transformer needs a synthetic generator and a newspaper dataset; no scan-degradation study.

- **Structural framing plans from PDF (arXiv 2608.17237, v2 Aug 2026, abstract and method read 2026-11-14, verified):** a deterministic stage rejects members with two unsupported endpoints, which removes legend strokes and title-block rules "without relying on a fixed crop defined by page location", then a language-model stage makes typed, rule-checked corrections; scale comes from dimension-ratio consensus (within 0.1% on its own generated plans). Benchmark: 100 author-generated plans (50 development, 50 held-out), not real scans. Transfer: a connectivity rule instead of a position rule keeps non-plan strokes out of the count. What breaks: it needs vector primitives (image-only PDFs go through binarisation and tracing, a weaker path), synthetic benchmark only, no raster scans.

## 4. Looked for and did not find

- Any paper that splits a **residential raster sheet into its plans** or reports a plans-per-sheet accuracy.
  Multi-unit floor plan work (2408.01526, 2607.00015) does not do it: the first has no per-unit split step, the second
  lists unit separation as future work and reports no metric (both read).
- Second attempt on orientation (different terms): one ICDAR paper on automatic orientation correction of AEC drawing
  documents (Seraogi et al., ARC Document Solutions with ISI Kolkata; page read 2026-11-14, **abstract only**, publisher
  copy is not open; year not on the page) says wrong skew or orientation blocks OCR text classification on drawings and
  proposes detecting and correcting orientation while localising text. It is text-region based, so it inherits the text-sparse
  limit. Title-block position (lower right, by drafting convention) is an orientation anchor for framed sheets but our sheets
  mostly have no title block.
- Second attempt on a minimum legible symbol size: no study gives a symbol-height threshold in pixels. Only a vendor guide
  (Werk24 API docs, read 2026-11-14, **reported, commercial**) says text accuracy stabilises near 10 px and recommends 300 dpi
  (200 dpi minimum). A 2024 P&ID study (Chalmers, abstract read) finds density has no significant effect with a dense
  detector while markup noise lowers accuracy. The threshold for our symbols has to come from a controlled downsampling run
  on our own boxes (open question 7). Third attempt (P&ID papers, read in full 2026-11-14, verified): SynthPID (2604.16513) states
  that P&ID symbols are often just 8 x 8 px and shrink to sub-pixel size at the roughly 800 px long side a DETR-style
  detector takes, so box regression "becomes unreliable" and it patches; the DLR study (2411.13929) resizes each diagram to
  4500 x 7000 and cuts patches with at least 50% overlap, down-weighting boxes near a patch border (confidence minus up to
  0.4) to avoid double counts. Both are statements of the problem and a recipe, not a measured pixel threshold.
  Our tile overlap and border-weighting rules can start from the DLR recipe. Details re-read in the paper (verified): patch size 1500 x 1500 on the
  4500 x 7000 resize (a quarter of the long side), merge by lowering each box's confidence near a patch border, dropping low
  scores, one NMS at a high IoU, then weighted box fusion at a lower IoU; going to 2000 x 2000 patches to fit large symbols
  left patched symbol AP at 86.52 for the modular method but stitched AP fell to 76.74, and on the subset where every symbol
  fits in a 1500 patch stitched AP was 87.48 (SynthPID, 2604.16513, uses the same 1500 x 1500 patches at stride 750, i.e. 50% overlap, then NMS and weighted box fusion), so large symbols that cross a tile edge are the weak point of stitching, not small ones.
- Pointer for other scopes (L1/L7): K-OPSD (arXiv 2609.34082, opened 2026-11-14, intro and method read): post-trains Qwen3-VL 4B/8B on AECV-Bench with a verifier, zooms into a crop before asking a count question, judge score 0.819, combined accuracy 0.738; a VLM recipe, not sheet normalisation.
- Closest thing to a plan-per-sheet split, found by grepping the papers I had already read (Raster2Seq, arXiv 2602.09016, appendix, verified 2026-11-14): "each image may contain more than one floorplan instance", so the authors take closed contours on the ground-truth foreground mask, save each instance as its own file and shift the corners to its bounding box. It confirms the case exists inside the CubiCasa5K-derived data, but it is a preprocessing step on labels, not a method for raw rasters, and no accuracy is reported.
- A 2025 Wiley paper on wall segmentation (CACAIE, search snippet only, **paywalled, not opened**) crops drawings with fixed rules on the title block's position and width and assumes one plan per drawing; the same journal's multibranch floor plan segmentation paper (De Nardin 2025, snippet only) works on single plans at 512 x 512.
- Real-estate brochures with several floors on a page (web search 2026-11-14, **snippets only**): a vendor guide lists page separation of multi-floor plans as an unsolved challenge, a USPTO filing (floorplan elements from drawings) describes a box detector with confidence filter and NMS, and Roboflow Universe has a community set named "floor_plan_multiple" (not opened, licence unknown, excluded by record 0003 anyway).
- Adjacent field, several documents in one scan image (web search 2026-11-14, **search results only, not opened**): the only items are patent filings and a vendor page (two-stage: detect boundary points or candidate quadrilaterals, then instance segmentation per document; one filing uses an object detector to split creased or overlapping scans) and a 2019 manuscript layout paper; no 2025-2026 academic paper found. It supports the box-detector choice in rank 1 but is not evidence.
- "Why floor plan object detection breaks under real scans: a controlled study of robustness limits" is now **identified but still unread**: Carrara, Nousias and Borrmann (TUM), Automation in Construction, published 2026-11, DOI 10.1016/j.autcon.2026.107193 (Crossref and the Semantic Scholar citation list of CubiCasa5K, read 2026-11-14); Semantic Scholar lists it as open access (CC BY) but ScienceDirect refused the headless browser and curl (access error page), Crossref has no abstract, and no preprint turned up. **A person with a normal browser should open `https://doi.org/10.1016/j.autcon.2026.107193`**: it is the one paper aimed squarely at our scan problem.
- Earlier attempt at the same title: "Why floor plan object detection breaks under real scans": a web search returned no page with that title; the nearest are a 2021 synthetic-data and augmentation paper for floor plan detection (DFKI, Applied Sciences) and a 2023 VR-oriented floor plan detector paper (opened, uses CubiCasa5K and ROBIN, no scan-degradation study). Neither is the missing paper.
- Second attempt on plans per sheet: no dataset labels storeys per image; MLSTRUCT-FP has one floor per file; AECV-Bench (arXiv 2601.04819, opened and read 2026-11-14) labels
  doors, windows, bedrooms, toilets on 120 floor plans, partly drawn from CubiCasa5K and CVC-FP and partly from the web, selected for legibility (so easier than our scans; a leakage risk for any model trained on CubiCasa5K); the paper does not say whether any image holds several plans; VLM exact-count accuracy for doors and
  windows is often 0.40-0.55 with large proportional errors (verified, abstract and counting section).
- Any 2025-2026 **orientation method for text-sparse drawings**. Zernike moments (2504.03241) make features invariant
  instead of estimating an orientation and test only a 45 degree rotation.
- A learned no-reference quality metric **evaluated on drawings** (searched twice). The only drawing gate is the
  OCR-confidence threshold on 50 bridge plans (read, see rank 5).
- Quality-gate retry with two extended web searches (2026-11-14): the ICCV 2025 VQualA document-image-quality challenge paper (opened, verified) uses DIQA-5000, 5000 enhanced text-document images with human opinion scores (shadow, occlusion, blur, crease, moire), 120 registrants, 7 valid final teams: text pages from phones, not drawings. A 2025 tunnel-crack paper (Sensors, snippet only) cites a BRISQUE cut-off of 45 for dropping blurry images, set on natural images. Nothing evaluates a gate on drawings beyond the OCR-confidence gate in rank 5.
- Super-resolution retry with an extended search: the only floor-plan study remains 2112.09844 (slight drop in icon detection); a 2025 aerial rooftop paper (2503.23200, snippet only) reports Real-ESRGAN gains in another domain. No 2025-2026 ablation of SR against bicubic for symbol counts on drawings.
- **Super-resolution measured for symbol counts** on drawings with false positives counted: none. 2312.13620 names the
  risk and measures none.
- Finnish storey-caption conventions that would mark where one plan ends and the next begins: a search returned
  Finnish drawing sets with one storey per page ("1. KERROS" in the title block) and nothing on stacking several plans
  on one sheet. That is a search-result observation, not a read.
- "Why floor plan object detection breaks under real scans: a controlled study of robustness limits" (2026) appears in the
  forward-citation list of the CubiCasa5K paper; I could not find a page for it, so I could not read it. **Worth one
  more look by whoever has a Google Scholar route.**
- Venue sweeps: ICDAR 2024 and 2025 and GREC 2024/2025 paper lists could not be retrieved (search returned book listings and a
  call for papers only); WACV 2026, ICCV 2025 and CVPR 2026 searches returned floor-plan generation and VLM papers,
  nothing on sheet splitting or normalisation. Roboflow Universe has small community sets for floor plan, legend and scale
  bar (one lists 197 images), which record 0003 rules out.
- GitHub sweeps (repos by recent push) for floor plan rotation, document orientation, title block and drawing layout:
  hobby repositories with no licence and no numbers; nothing usable.
- Springer (IJDAR 2025 survey of floor plan image analysis) returned an empty page through the headless browser; MDPI
  (a 2026 raster floor plan plus LLM compliance paper) returned Access Denied. Neither read.
- Dewarping and deskew successors, 2025-2026 (AADD 2507.15000, DvD 2505.21975, DRCCBI 2501.03145): seen in search results
  only, not opened, not ranked; we have no curled phone photos, so they were not chased. The one 2026 deskew paper I
  did read is row 25.

## 5. Citation walks forward (done; FELD 2607.18997, 2611.12657 and 2609.07362 have no citers indexed in Semantic Scholar on 2026-11-14)

- From 2504.08645 (title block): citers 2025-26 include the AEC benchmark 2607.18997 (read) and 5 non-arXiv items.
- From 2510.21862 (multi-view drawings): BlueprintAgent 2609.07362 (read), BLUEPRINT retrieval 2602.13345 (read), plus
  2610.02214, 2608.24039, 2602.18296 (opened 2026-11-14: ship dataset, manufacturing planning, annotation-to-3D mapping; none splits sheets or counts; 2608.24039 uses oriented boxes for annotations at any angle).
- From CubiCasa5K, 2026 citers listed by Semantic Scholar (read 2026-11-14, about 45 items): opened this round 2603.14764 (polygon augmentation keeps ring-shaped regions connected after cropping: matters only if our training crops cut room polygons, not box labels) and 2609.34047 (ARCH-B, cross-representation question benchmark, off-topic); the gap paper "Why floor plan object detection breaks under real scans" is in this list (see section 4); the rest are generation, BIM-agent, VLM-benchmark and localisation papers.
- From CubiCasa5K (1904.01920): 176 citers; 2025-26 ones relevant to this scope that I opened are 2609.25615, 2609.24565,
  2507.10343 (walls, small real-world set), 2609.07362; I did not open the dozens on generation, BIM agents and VLM benchmarks.
- From SAHI (2202.06934): 2611.12657 (read) and 2608.23923 (read) are the two on slicing method; the other citers are
  application papers.
- From 2511.04161 (orientation): two citers, one OCR production paper (2602.16430) adding a rotation module
  (read 2026-11-14, verified: extraction exact match on 9 text-rich government ID document types 82.13 to 88.70 for
  one system with the Seeing Straight style rotation module; the 89.80 system also uses it; text documents, not drawings,
  so it says nothing about line art).

## 6. Open questions, and which tools were missing

1. Does the dev label export carry enough to build per-plan boxes (union of a plan's element boxes), and do the
   multi-plan sheets have a gap between plans? Without that, rank 1 is unmeasured.
2. How is the 1-in-3 "rotated" fraction labelled? If dev rotations are labelled, PP-LCNet_x1_0_doc_ori and the
   four-rotation agreement can be scored in 30 minutes; if not, a 100-image hand label is needed.
3. Is RF-DETR trained at a square size acceptable for 2:1 sheets, or do plans need native-scale tiles first? Partly answered (issue #1052, read in full 2026-11-14, still open): the maintainers say squash to square, the pretraining is square, rectangular support is not planned; one user first saw about +20% with a hacky 3:4 input, then found it was because the pretrained weights had not been loaded, and with them square and 3:4 gave no accuracy difference (anecdote, one dataset). So a squashed 2:1 sheet is the supported path; only a test on our boxes settles whether plan boxes survive a squash.
4. DocIQ, 2312.13620 and the electrical-plan repos: 2312.13620's repo exists with no LICENSE (row 14); DocIQ (2509.17012) names no repository in its text and a GitHub search by name finds only unrelated apps, so it stays code-less.
5. For the other orchestrator: 2609.25615 (SALI-FP) uses an OpenAI-compatible image-edit gateway, so it is not a local
   method; 2610.09313 gives a splitting-versus-zooming rule for VLM calls.
7. What pixel height of a window, door or fixture symbol still counts exactly? Nobody has published it; a downsampling sweep
   (render the same plan at 100%, 75%, 50%, 35% and score the detector) on dev boxes would give it in about an hour (estimate).
6. Missing tools: no arXiv MCP; arXiv HTML pages 404 for the 2025-26 papers, so I read PDFs through download and
   text extraction; Springer returned an empty page and MDPI returned Access Denied through the headless browser (not retried); the GitHub search rate limit was not hit.

8. For a person with a normal browser: read `https://doi.org/10.1016/j.autcon.2026.107193` ("Why floor plan object detection breaks under real scans", Automation in Construction, 2026-11, listed as open access); ScienceDirect refused the headless browser, so it is unread here.
9. Final status of this report (2026-11-14, wrapped up on the orchestrator's order before the 01:30 floor): about 85 sources opened, most from full PDF text; rows marked "reported" are model-card or author claims I could not check independently (rows 21, 22, 27-29 and the vendor guide); unread: the paper in item 8, the paywalled ICDAR orientation paper, Springer and MDPI pages. Tools missing in the last rounds: OpenAlex free budget used up for the day, Google search showed a captcha through the headless browser (not bypassed), ScienceDirect blocked automated access.
