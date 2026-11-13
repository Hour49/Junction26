# Normalising the sheet (orientation, deskew, quality)

40 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i1"></a>
### 1. rot90 training augmentation and four-rotation test voting

- What: Train with 90-degree rotations and average predictions over four rotations.
- Evidence (floor-plans): CubiCasa 2019 recipe uses 90-degree rotations and four-rotation TTA (paper); rotated window F1 24.8 without normalisation vs 76.8-79.4 with (arXiv 2504.03241, re-checked).
- Source: [arXiv 1904.01920](https://arxiv.org/abs/1904.01920), [arXiv 2504.03241](https://arxiv.org/abs/2504.03241)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: free to 1 h
- Experiment: Score the rotated third separately with and without.
- What breaks on our images: Voting adds duplicates to reconcile.
- Moves: windows-doors. Why this group: a third of our images are rotated
- Also (count, our-idea): Four rotations, majority. Run exemplar counters at four rotations and keep majority. Evidence: No measurement; exemplar counters likely lack rotation training. Source: [arXiv 2511.08048](https://arxiv.org/abs/2511.08048). Experiment: Rotation agreement.
- Also (detect, our-idea): Four-view rotation test-time augmentation. Run the detector on the four 90-degree rotations, invert the boxes and merge, only if D4 training does not remove the need. Evidence: Hypothesis; no measured gain for drawings found; costs 4x inference. Source: none. Experiment: On dev: D4-trained model with and without TTA, exact-count rate.
- Also (rooms, floor-plans): Four-rotation test-time averaging. Average predictions over 0, 90, 180 and 270 degrees at inference. Evidence: CubiCasa5K paper; rotation halves door and window F1 without normalisation in a region classifier. Source: [arXiv 1904.01920](https://arxiv.org/abs/1904.01920), [arXiv 2504.03241](https://arxiv.org/abs/2504.03241). Experiment: Compare with rotation augmentation alone.
- Reports: lit-count-a, lit-count-c, lit-detect-c, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c, lit-rooms-b, lit-rooms-c

<a id="i2"></a>
### 2. Super-resolution or Lanczos upscaling before detection

- What: Test Lanczos vs learned super-resolution in front of the detector.
- Evidence (floor-plans): Up to 39.47% better, 12.17% mean (2021, CubiCasa5K network, relative or absolute unclear).
- Source: [arXiv 2112.09844](https://arxiv.org/abs/2112.09844)
- Licence: MIT. CubiCasa5K leakage: yes.
- Cost: 2 h
- Experiment: Lanczos 2x vs EDSR on dev counts.
- What breaks on our images: Invented strokes; phone noise.
- Moves: windows-doors. Why this group: tied to the resolution experiment
- Also (count, our-idea): Upscale small plans before counting. Lanczos upscale before the exemplar step. Evidence: Models see 800-1024 px; 855 px plans with 5-20 px symbols are untested. Source: [arXiv 2512.23351](https://arxiv.org/abs/2512.23351). Experiment: 1x vs 2x exact rate.
- Also (sheet, adjacent-field): Resolution policy: deterministic upscale to the training size, one full pass, tiles only on top. Upscale small plans with Lanczos so the short side reaches the trained input size, use the same factor in training and inference, tile only large sheets and then also in training. Evidence: On aerial images a single higher-resolution pass beats sliced inference for every detector trainable at that size; tile merge on drawings has precision 0.50 with box NMS alone against 0.85 with containment. Source: [arXiv 2611.12657](https://arxiv.org/abs/2611.12657). Experiment: Exact count per class at native, 1x Lanczos up to training size and one higher size, on dev, upright and rotated.
- Reports: lit-count-a, lit-count-c, lit-floorplan-a, lit-sheet-a, lit-sheet-c

<a id="i3"></a>
### 3. Rotation augmentation and per-sheet orientation estimate

- What: Rotate sheets to dominant wall directions before snapping and train with rotation augmentation.
- Evidence (floor-plans): Wall net with random rotation augmentation reached IoU 0.81.
- Source: [arXiv 2306.01642](https://arxiv.org/abs/2306.01642)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Orientation estimate accuracy on dev.
- What breaks on our images: Photos with perspective.
- Moves: trust. Why this group: needed by snap and corner closers
- Reports: lit-rooms-a, lit-rooms-c

<a id="i4"></a>
### 4. Augraphy for pixel-level scan effects only; do rotation and scaling ourselves

- What: Use Augraphy (ink bleed, low ink, paper, JPEG, scanner noise) which cannot move boxes; apply rot90, flips and scaling in our own code where box arithmetic is exact; test each effect on real dev scans.
- Evidence (adjacent-field): Augraphy README: pixel effects leave boxes unchanged; open issue 437: rotated boxes only move by start and end points. Form detection: handwritten mAP +0.040 / +0.012 / +0.037 / -0.034, digital -0.018 to +0.001 (arXiv 2502.06132). Last PyPI release 8.2.6 (2023), needs numba.
- Source: [github.com](https://github.com/sparkfish/augraphy), [arXiv 2502.06132](https://arxiv.org/abs/2502.06132)
- Licence: MIT. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Train with and without each effect; report a clean dev slice and a degraded slice.
- What breaks on our images: Unmeasured on drawings; numba first-call latency in a dataloader; effects sometimes lower clean-set scores.
- Moves: windows-doors. Why this group: permissive tool, evidence mixed, so run it as an ablation
- Also (rooms, authors-claim): Rasterise masks first, augment image and mask, vectorise last. Do not augment polygon vertices; rooms with holes can split. Evidence: Topology-preserving polygon augmentation paper describes the failure. Source: [arXiv 2603.14764](https://arxiv.org/abs/2603.14764). Experiment: none
- Also (vector, adjacent-field): Compose synthetic symbols onto real blank scans (ScoreAug-style). Overlay rendered symbols on real blank plan backgrounds with salt-and-pepper noise and small rotations before a short full-page fine-tune. Evidence: TISMIR 2024: AP at IoU 0.25 on real pages from 36.0 to 73.3 (abstract) with sim-to-real augmentation; adversarial domain adaptation 48.9. Source: [github.com](https://github.com/raember/s2anet). Experiment: Train with and without composed backgrounds on dev; compare exact-match on scan-style plans.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-rooms-b, lit-vector-c

<a id="i5"></a>
### 5. Keep native resolution for the wall net

- What: Tile or upscale instead of downscaling below native pixels.
- Evidence (adjacent-field): F1 falls with resolution, 16 against 8 bit and moderate JPEG did not matter (IJGI 2025).
- Source: [mdpi.com](https://www.mdpi.com/2220-9964/14/12/473)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Compare 512 downscale with tiles on dev.
- What breaks on our images: Memory.
- Moves: scale-areas. Why this group: thin walls vanish otherwise
- Reports: lit-rooms-c

<a id="i6"></a>
### 6. Orientation by reading labels at four rotations and counting vocabulary hits

- What: Run the OCR at 0/90/180/270 on a 2x copy, count exact hits of the closed room-label vocabulary at each, pick the best rotation, abstain when the best is not clear.
- Evidence (adjacent-field): Page-orientation by recognition (RD-POD, 2009, book pages) 99.7% with rejections; Seeing Straight and docTR show OCR-based rotation is second best; the label OCR lost to rotation is a measured weakness. No number on plans.
- Source: [arXiv 2511.04161](https://arxiv.org/abs/2511.04161)
- Licence: RapidOCR / PaddleOCR Apache-2.0. CubiCasa5K leakage: no.
- Cost: 1-2 h work, CPU
- Experiment: On 100 dev images with known rotation (hand label or SVG origin) report rotation accuracy and abstain rate; then room-label exact rate on upright against rotated images.
- What breaks on our images: 5-10 px labels are the measured OCR misses; single letters match noise so count labels of two letters or more.
- Moves: room-types. Why this group: Orientation matters mainly for the text pass and the vote costs nothing at inference.
- Also (ocr, our-idea): Run the whole sheet at four page rotations and keep every in-vocabulary read. Run detection and reading on the sheet rotated 0, 90, 180, 270 and keep each code's best in-list read. No crop code needed, four detector passes per sheet. Evidence: Own synthetic page test: 116 of 120 codes found on a sheet given in any orientation, vs 41-113 for a single pass. Source: [github.com](https://github.com/RapidAI/RapidOCR). Experiment: Run on the 40 dev images, compare with the crop-level vote on the rotated third; report time and exact match per room type.
- Reports: lit-ocr-c, lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i7"></a>
### 7. Raise single-pass input resolution before slicing

- What: Upscale each plan with a fixed antialiased filter so the median symbol is at least one patch or cell wide (about 24-32 px at the detector input) and train and run on the whole plan; tile only the few sheets beyond trainable size.
- Evidence (adjacent-field): RF-DETR-L on small insects: 1344 px 0.405 mAP50:95 vs 1120 px 0.379 vs sliced YOLO 0.368 (arXiv 2607.22913 Table 2); seven CNN detectors on VisDrone: one 2048 px pass beat 1280 px plus SAHI by 2.8-3.5 AP (arXiv 2611.12657); tiny faces: 2x upsampling 69 to 75 (CVPR 2017); SNIP COCO AP_S 16.3 to 21.4.
- Source: [arXiv 2607.22913](https://arxiv.org/abs/2607.22913), [arXiv 2611.12657](https://arxiv.org/abs/2611.12657), [arXiv 1612.04402](https://arxiv.org/abs/1612.04402)
- Licence: n/a (recipe). CubiCasa5K leakage: no.
- Cost: a few GPU-h per extra resolution; memory grows with the square of the size
- Experiment: Train at 640/704, 1024 and 1280-1536 px, score exact-count rate and recall by symbol area on dev; sweep scale factors 1x, 2x, 3x on a 200-image subset.
- What breaks on our images: None of these is on drawings; the 12 GB card may not hold RF-DETR-M at 1344+; plain interpolation adds no strokes and blurs 1 px lines.
- Moves: windows-doors. Why this group: Resolution is the real lever, cheapest to test
- Also (data, adjacent-field): Resolution before augmentation for tiny symbols. Test M or L at its own resolution on tiles first, then raise input resolution only if the 20 px classes still miss; stay on sizes divisible by 32. Evidence: Aerial tiny objects: AP 0.436 / 0.489 / 0.525 at 640 / 800 / 928 (+21% relative), heavy augmentation did not help (arXiv 2509.17078). Recycling objects: 60.8 / 65.4 / 69.1 mAP@0.5 at 640 / 1280 / 2048 (arXiv 2605.26884). RF-DETR-2XL at 880 train: 42.04 at 880 test, 46.29 at 2400 (non-shippable size). Source: [arXiv 2509.17078](https://arxiv.org/abs/2509.17078), [arXiv 2605.26884](https://arxiv.org/abs/2605.26884), [arXiv 2608.24154](https://arxiv.org/abs/2608.24154). Experiment: Tiles of 640, 800, 1024 px, same model; dev exact count per class.
- Also (detect, adjacent-field): 200-image sweep of scale 1x, 2x, 3x with 640 px crops. On a 200-image dev subset run {1,2,3}x native scale with 640 px crops (128 px overlap) against single-pass 1024/1280 px; tripwire: window AP50 under 70 after 5 epochs. Evidence: PCB: 4-8 px boxes found 0% at 640 px full image, 0-17% at 1280 px, 46-100% on native-scale tiles. Source: [arXiv 2605.24726](https://arxiv.org/abs/2605.24726). Experiment: As described; per-area recall.
- Also (floorplan, adjacent-field): Train and run one pass at 2x upscale before any tiling. Train the detector at an upscaled input (e.g. 2x of our 855 px) and compare with native and with tiles merged by a box rule. Evidence: VisDrone: single pass at 2048 px beats 1280 px with tiles and box fusion by 2.8-3.5 AP val, 1.8-3.1 test-dev (arXiv 2611.12657 Table 1; +2.75/+1.83 rows re-checked). Source: [arXiv 2611.12657](https://arxiv.org/abs/2611.12657). Experiment: Three arms (native 704, 2x upscale, 768 px tiles stride 384) on dev; 5 points exact on windows or doors settles it.
- Reports: lit-data-b, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c, lit-floorplan-b, lit-floorplan-c

<a id="i8"></a>
### 8. Log and bypass the OCR page-size cap before comparing engines on PDF renders

- What: RapidOCR shrinks any page above 2000 px on the long side before detection; PaddleOCR and EasyOCR have similar silent limits (EasyOCR min_size 20 drops boxes). Raise the cap or tile at native resolution, and log the shrink factor per page.
- Evidence (adjacent-field): One drawing: 41 boxes at default vs 2,054 boxes with native-resolution tiling (RapidOCR issue 764). EasyOCR drops boxes whose longer side is 20 px or less by default; PaddleOCR default detection of one A4 scan took 43 GB RAM (issue 17955).
- Source: [github.com](https://github.com/RapidAI/RapidOCR/issues/764), [github.com](https://github.com/PaddlePaddle/PaddleOCR/issues/17955)
- Licence: code Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: none (a rule)
- Experiment: Before any engine comparison on high-DPI PDF renders, log shrink factor and box count per page.
- What breaks on our images: A first test on such renders would look like OCR cannot read labels.
- Moves: none. Why this group: avoid a false negative on renders; current sheets are about 855 px so no shrink
- Reports: lit-ocr-a, lit-ocr-c

<a id="i9"></a>
### 9. Same tile geometry in training and inference

- What: Either whole plan in and out, or tile crops in training and tile inference; never train on whole pages and infer on tiles or the reverse. Use one preprocessing function for training, evaluation and export.
- Evidence (adjacent-field): Music scores: full-page training vs cropped-and-merged mean AP50 0.849 vs 0.802 (DAS 2024); DINO trained on crops, tested on pages 0.642 vs 0.914; PCB study: full-image model mAP50 0.01 on tiles vs 0.72 and 0.94 for a tile-trained one; D-FINE class flicker when PyTorch stretches and ONNX letterboxes.
- Source: [hal.science](https://hal.science/hal-04268139v2/document), [arXiv 2605.24726](https://arxiv.org/abs/2605.24726)
- Licence: n/a (rule). CubiCasa5K leakage: no.
- Cost: 0 (a rule)
- Experiment: Check every run script and the exported model use the same resize function; log the resolution actually used.
- What breaks on our images: Evidence is from music scores and PCB defects, not floor plans.
- Moves: windows-doors. Why this group: Protects every detector run at zero cost
- Also (data, adjacent-field): Train on tiles at the scale used for inference. Train on tile crops at native resolution, tiles with overlap, and infer with the same tiling; do not train on downscaled whole sheets and infer on tiles. Evidence: PCB: full-image-trained detector 0.70 to 0.01 mAP@50 on native tiles; tile-trained 0.72 and 0.94 (arXiv 2605.24726). Plan symbols: tile 224 px at stride 50, keep tiles with a complete symbol, tile mAP 72.40 but whole-plan about 59 (arXiv 2006.00684). P&ID: 1500 px tiles, stride 750 (arXiv 2604.16513). Source: [arXiv 2605.24726](https://arxiv.org/abs/2605.24726), [arXiv 2006.00684](https://arxiv.org/abs/2006.00684), [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Tiles of 640 and 1024 px with 128 px overlap vs one full-sheet model; read dev exact count by class.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c

## Try next

<a id="i10"></a>
### 10. Tile high-resolution sheets before detection

- What: Cut large renders into overlapping tiles at native resolution, then merge boxes, instead of shrinking the sheet.
- Evidence (floor-plans): Overlapping tiles plus augmentation in the 2026 floor-plan reader; 256 px tiles beat 1024 px tiles 90.12 vs 74.66 AP; native resolution tiling found 2,054 boxes vs 41 on one drawing.
- Source: [iopscience.iop.org](https://iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017), [github.com](https://github.com/RapidAI/RapidOCR/issues/764)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 1 to 2 h work (estimate)
- Experiment: Compare recall at tile sizes 256, 512, 1024 on dev images split by image size.
- What breaks on our images: Best tile size depends on image size (152 to 4,960 px).
- Moves: room-types. Why this group: only matters for large renders
- Reports: lit-ocr-a, lit-ocr-c

<a id="i11"></a>
### 11. Four-way orientation classifier before everything

- What: Small CNN trained on rotations of upright plans, or a ready document orientation model.
- Evidence (adjacent-field): 98%/96% orientation (Seeing Straight, claim); PP-LCNet doc-ori 99.06% on 1,000 images (docs, summary).
- Source: [arXiv 2511.04161](https://arxiv.org/abs/2511.04161), [github.com](https://github.com/PaddlePaddle/PaddleOCR)
- Licence: PaddleOCR Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 3-5 h (estimate)
- Experiment: Accuracy on dev rotations; effect on downstream counts.
- What breaks on our images: Plans with few text lines.
- Moves: windows-doors. Why this group: only if rot90 augmentation is not enough
- Also (ocr, authors-claim): Page-level 0/90/180/270 classifier as one extra vote. Use PP-LCNet_x1_0_doc_ori (7 MB, 4 classes) as an extra orientation vote on the sheet. Evidence: 99.06% top-1 on the vendor's ID and document set; a Phi-3.5-vision orientation classifier 96.81% on document pages; nothing on drawings. Source: [arXiv 2511.04161](https://arxiv.org/abs/2511.04161). Experiment: Run on dev sheets split by known rotation and report accuracy.
- Also (sheet, authors-claim): PP-LCNet_x1_0_doc_ori as a 4-class orientation vote. Run the 7 MB 4-class page orientation classifier on whole sheets padded to square and use it as one vote next to the OCR vote. Evidence: Top-1 99.06% on a 1,000-image self-built ID and document set, 3.24 ms CPU; a third-party port reports the correct class near 45% on such inputs; no result on line art. Source: [paddleocr.ai](https://www.paddleocr.ai/latest/en/version3.x/module_usage/doc_img_orientation_classification.html), [huggingface.co](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori). Experiment: Score 4-class accuracy and confidence on 50-100 dev images with known rotation; compare with the OCR vote and the two combined.
- Also (vlm, adjacent-field): Orientation classifier before extraction. Train a 0/90/180/270 classifier on rotated copies of our own plans and rotate before extraction. Evidence: 98% and 96% rotation accuracy on two text datasets (2511.04161). Source: [arXiv 2511.04161](https://arxiv.org/abs/2511.04161), [arXiv 2605.05045](https://arxiv.org/abs/2605.05045). Experiment: Accuracy on rotated third of dev plans, then effect on exact counts.
- Reports: lit-floorplan-b, lit-floorplan-c, lit-ocr-a, lit-ocr-b, lit-ocr-c, lit-sheet-a, lit-sheet-b, lit-sheet-c, lit-vlm-c

<a id="i12"></a>
### 12. No-reference image quality and resolution as a confidence input

- What: Add scan resolution, blur, skew and symbol pixel size as features; VLM and detector confidence do not fall when evidence is lost.
- Evidence (adjacent-field): OCR and quality features alone AUC 0.896 above log-probabilities 0.880 (2606.24420); VLM confidence stayed 0.9 after 3x less evidence (2601.00138); degradation gate AUROC 88-97 (2602.18394).
- Source: [arXiv 2606.24420](https://arxiv.org/abs/2606.24420), [arXiv 2601.00138](https://arxiv.org/abs/2601.00138), [arXiv 2602.18394](https://arxiv.org/abs/2602.18394)
- Licence: code not located. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Check correlation of quality features with plan correctness on dev.
- What breaks on our images: Trained on natural images; no evidence flagged images have wrong counts.
- Moves: trust. Why this group: Cheap and independent of detector confidence.
- Also (sheet, adjacent-field): Quality score trained on our own count error. Regress per-image count error on cheap features (short side, stroke width, door-leaf size in px, ink fraction, detector confidence entropy, full-pass against tiled-pass disagreement) with a small boosted tree; gate on the prediction. Evidence: Fingerprint quality (NFIQ2) predicts matcher utility by random forest over 14 features chosen from 155; generic no-reference scores correlate with OCR error for only 2 of 8 systems (n=60). Source: [github.com](https://github.com/usnistgov/NFIQ2), [arXiv 2511.13523](https://arxiv.org/abs/2511.13523). Experiment: Out-of-fold gate on 3,828 dev rows; report error among answered against fraction abstained.
- Also (sheet, adjacent-field): One blended quality score as the gate. Do not gate on one blended or generic quality score; gate on named components checked against our error. Evidence: DHS study (secondary news report): OFIQ's unified score gave 'extremely limited utility'; generic no-reference scores predicted OCR error for 2 of 8 systems; document-quality models are trained on phone-photographed text pages. Source: [arXiv 2511.13523](https://arxiv.org/abs/2511.13523), [arXiv 2509.17012](https://arxiv.org/abs/2509.17012). Experiment: none
- Also (sheet, adjacent-field): Localised quality (crop level) instead of a page score. Predict quality on the plan box or label crop that matters, not on the whole sheet. Evidence: Invoices: per-word error heatmap plus region mask gives AUC 0.92 against 0.76 for the best page-level score; direct transfer of a page model failed (SROCC -0.31). Source: [arXiv 2509.17012](https://arxiv.org/abs/2509.17012). Experiment: Gate on plan crops after the plan detector exists.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c, lit-trust-b, lit-trust-c

<a id="i13"></a>
### 13. Rescale each plan crop to a fixed measured scale before the symbol detector

- What: After the plan finder, rescale each crop so a measured cue (wall thickness or door-leaf width from a distance transform) lands at a fixed value; train and test at that scale.
- Evidence (adjacent-field): SNIP on COCO small objects: mAP 19.6 at 800 px, 19.9 at 1400 px, 21.4 scale-normalised; photos, not drawings.
- Source: [arXiv 1711.08189](https://arxiv.org/abs/1711.08189)
- Licence: idea only. CubiCasa5K leakage: no.
- Cost: 1 h work
- Experiment: Measure exact counts on 50 dev plans with and without crop normalisation.
- What breaks on our images: Needs a robust size cue per plan; evidence is not on drawings.
- Moves: windows-doors. Why this group: One-hour numpy step, free at inference.
- Reports: lit-sheet-c

<a id="i14"></a>
### 14. Rotate only when two independent voters agree, else abstain and flag

- What: Combine the OCR vote and the classifier (or detector four-rotation agreement); turn the page only on agreement, otherwise leave it and flag the sheet.
- Evidence (adjacent-field): OCRmyPDF rotates from Tesseract confidence above a threshold and, in its second mode, only when two engines agree so upright charts and maps stay as they are. No plan number.
- Source: [ocrmypdf.readthedocs.io](https://ocrmypdf.readthedocs.io/)
- Licence: OCRmyPDF MPL-2.0; idea only. CubiCasa5K leakage: n/a.
- Cost: 30 min work
- Experiment: Report wrong-rotation rate among turned sheets and the share abstained, against rotating on one voter.
- What breaks on our images: Abstaining on a rotated plan still costs the label pass.
- Moves: trust. Why this group: Cheap rule with a shipped precedent.
- Reports: lit-sheet-b

<a id="i15"></a>
### 15. Pad non-square plans to a square with a fixed rule, do not stretch

- What: RF-DETR and D-FINE stretch input to a square; pad instead with the same transform in training and inference so a 12 px square window stays square.
- Evidence (authors-claim): RF-DETR issue 1052: maintainers say squash, a user's native-ratio fork reported about 20% better on one dataset; D-FINE issues 139 and 358 report accuracy loss from stretch-versus-letterbox mismatch.
- Source: [github.com](https://github.com/roboflow/rf-detr/issues/1052), [github.com](https://github.com/Peterande/D-FINE/issues/139)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Compare stretch vs pad on dev exact-count rate.
- What breaks on our images: Padding wastes pixels on very elongated sheets.
- Moves: windows-doors. Why this group: Small, cheap, one reported gain
- Reports: lit-detect-b, lit-detect-c

## Later

<a id="i16"></a>
### 16. Trained 'is this a floor plan' gate with shifted positives

- What: Train plan vs not-plan on CLIP-like features, include phone photos and scans as positives and parts-of-plan as non-negatives.
- Evidence (floor-plans): 89% valid after a three-stage filter (2412.00955); softmax OOD AUC about 0.5 for shifted vs unknown (ZOD); about 92% on drawing type from 450 drawings.
- Source: [arXiv 2412.00955](https://arxiv.org/abs/2412.00955), [arXiv 2507.09795](https://arxiv.org/abs/2507.09795)
- Licence: data CC BY 4.0, NegRefine MIT. CubiCasa5K leakage: unknown.
- Cost: 1 day
- Experiment: Compare with top-3 aggregation.
- What breaks on our images: Thin line art; no recall measured.
- Moves: trust. Why this group: Needed only if non-plans appear.
- Reports: lit-trust-b, lit-trust-c

<a id="i17"></a>
### 17. Use OCR boxes to erase text and dimension lines before wall extraction

- What: Mask pixels inside read text boxes before wall or room extraction so letters do not become wall fragments.
- Evidence (floor-plans): The 2026 BIM paper uses OCR boxes to erase dimension lines and leaders before wall extraction; no number.
- Source: [ec-3.org](https://www.ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 1 h work (estimate)
- Experiment: Compare room-segmentation error with and without text masking on dev plans.
- What breaks on our images: Masking can remove wall segments under text.
- Moves: scale-areas. Why this group: idea from another scope
- Reports: lit-ocr-a

<a id="i18"></a>
### 18. Tile or upscale plans for any line detector

- What: Never feed a plan at 512 px; tile at native or 2x scale because all three public line detectors resize to 512x512.
- Evidence (floor-plans): Own probe: at 512 px, segment counts in the 6-12 px bin are 0.34 of native, 12-20 px 0.70, 20-40 px 0.85. ScaleLSD resizes to 512x512 regardless of aspect; HAWP issue #39 says tiling is needed.
- Source: [github.com](https://github.com/cherubicXN/hawp/issues/39)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h
- Experiment: Count segments per length bin at native, 2x and 512 px on 30 dev plans.
- What breaks on our images: Tiling and stitching are our own code.
- Moves: none. Why this group: Needed only if a line detector is used
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i19"></a>
### 19. Scale-adaptive thresholds in any rule stage

- What: Express every rule threshold (snap, gap, segment length) in units of wall thickness or printed door width, not fixed pixels.
- Evidence (adjacent-field): 2609.05880: fixed 10 px snap gives exact edge F1 0.193 on predicted solids vs 0.742 with an adaptive snap.
- Source: [arXiv 2609.05880](https://arxiv.org/abs/2609.05880)
- Licence: paper CC BY-NC-ND. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Run any rule layer with fixed vs unit-scaled thresholds on dev; keep the better exact-match.
- What breaks on our images: Wall thickness estimate fails on single-line or non-scaled plans.
- Moves: none. Why this group: Free to apply if a rule stage exists
- Reports: lit-vector-b

<a id="i20"></a>
### 20. Rectify phone photos before parsing

- What: Detect the sheet and correct perspective.
- Evidence (adjacent-field): Arbitrary document rectification paper, text documents only; no plan study exists.
- Source: [arXiv 2511.23150](https://arxiv.org/abs/2511.23150)
- Licence: no licence. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Area error with and without on photos.
- What breaks on our images: Metric scale may not survive.
- Moves: trust. Why this group: no plan evidence
- Reports: lit-rooms-a, lit-rooms-b

<a id="i21"></a>
### 21. Normalise scans and photos to a clean look

- What: Adaptive binarisation or cleanup of scans and phone photos before inference.
- Evidence (adjacent-field): Dice 0.4393 to 0.5256 on real SEM images with a synthetic-only model (2606.02434).
- Source: [arXiv 2606.02434](https://arxiv.org/abs/2606.02434)
- Licence: not checked. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: Exact counts with and without cleanup on photo-like dev images.
- What breaks on our images: Global threshold fails on shadows.
- Moves: windows-doors. Why this group: Unmeasured on plans.
- Reports: lit-vlm-c

<a id="i22"></a>
### 22. Normalise strokes to a fixed width before the detector

- What: Skeletonise the dev images, dilate to a fixed 2 px, train once and compare with the raw input.
- Evidence (adjacent-field): Sketch recognition: RGB 11.4 vs edge maps with fixed threshold 39.1, 49.7 with randomised detectors; without thinning 5.9 (arXiv 2202.13164 Table III). Textureless parts: T-LESS mAP 0.195 to 0.695 on line-image training (AbSynth, VISAPP 2024).
- Source: [arXiv 2202.13164](https://arxiv.org/abs/2202.13164)
- Licence: im2rbte Apache-2.0; AbSynth paper CC BY-NC-ND. CubiCasa5K leakage: no.
- Cost: 2 h
- Experiment: Skeleton plus 2 px dilation input vs raw, same detector, dev exact count.
- What breaks on our images: Inputs are already line art; thin 1 px strokes vanish at 5-20 px symbols; removes grey-level cues (hatching, filled walls); no paper tests it for counting.
- Moves: windows-doors. Why this group: small expected gain
- Reports: lit-data-b

<a id="i23"></a>
### 23. Own 4-way rotation head trained on dev plans with OCR-derived labels

- What: Take dev images whose upright was fixed by the OCR vote, rotate all four ways, fine-tune a small CNN (MobileNet or EfficientNet-B0) at 224 px; abstain when class scores are close.
- Evidence (adjacent-field): dedoc EfficientNet-B0 scores 0.998-1.0 on 4,121 text documents rotated four ways; Genius Scan dropped text-based orientation for a MobileNet head; RotNet-style tasks fail on centrosymmetric sketches. No drawing number.
- Source: [github.com](https://github.com/ispras/dedoc), [arXiv 1803.07728](https://arxiv.org/abs/1803.07728), [arXiv 2002.00867](https://arxiv.org/abs/2002.00867)
- Licence: code and weights Apache-2.0 (dedoc, text pages); our head would be ours. CubiCasa5K leakage: no.
- Cost: 2-3 h work, minutes per epoch
- Experiment: Run only if the OCR vote fails on measured images; report 4-class accuracy on held-out dev images.
- What breaks on our images: Point-symmetric walls and no text make the task ill-posed; labels come from the OCR vote.
- Moves: room-types. Why this group: Fallback if the OCR vote fails.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i24"></a>
### 24. Vector PDF plans: use text layer and exact geometry

- What: For vector inputs read printed dimensions and opening sizes from the text layer; precision bounded by printed digits.
- Evidence (adjacent-field): figverify median 0.09%; a plan's text layer lists mm sizes.
- Source: [arXiv 2606.31345](https://arxiv.org/html/2606.31345)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Scale error from text layer on any vector dev inputs.
- What breaks on our images: Our images are mostly PNG.
- Moves: scale-areas. Why this group: Exact where it applies.
- Also (rooms, authors-claim): Read PDF layers before any vision. On vector PDFs take room contours from layers and graph labelling. Evidence: VectorGraphNET room-contour line F1 0.90 on its own set. Source: [arXiv 2410.01336](https://arxiv.org/abs/2410.01336). Experiment: Layer-name coverage on dev PDFs.
- Also (sheet, adjacent-field): Vector-PDF sheets: reject unsupported strokes by connectivity rather than by position. On vector PDFs, drop strokes with unsupported endpoints (legend lines, title-block rules) so non-plan marks stay out of the plan before detection. Evidence: Structural framing plans: synthetic benchmark only, 100 generated plans; scale from dimension-ratio consensus within 0.1%. Source: [arXiv 2608.17237](https://arxiv.org/abs/2608.17237). Experiment: Only if PDF inputs carry vector primitives; compare plan boxes with and without stroke filtering.
- Reports: lit-rooms-a, lit-scale-b, lit-scale-c, lit-sheet-a

<a id="i25"></a>
### 25. Rescale each sheet by a structural unit (wall thickness) before detection

- What: Estimate wall thickness from the stroke-width histogram and rescale so it has a fixed pixel size before detection; keep the lines in.
- Evidence (adjacent-field): Music: Deep Watershed Detector rescales to a fixed staff interline (10 or 20 px); Pacha et al. report mAP 80% on MUSCIMA++ with staff lines kept, removal has 'minimal impact' (synthetic lines). Plan-level stroke width alone has no count signal (corr 0.28-0.30).
- Source: [arXiv 1805.10548](https://arxiv.org/abs/1805.10548), [arXiv 2409.00316](https://arxiv.org/abs/2409.00316)
- Licence: DWD code MIT, TF 1.4; MUSCIMA++ CC BY-NC-SA. CubiCasa5K leakage: no.
- Cost: 3 h, 20-plan A/B (estimate)
- Experiment: Train or run the detector with and without unit rescaling on 20 dev plans; compare exact-match counts.
- What breaks on our images: Scale unit not constant or not drawn; overlap of same-centre objects hurts; AP not exact counts.
- Moves: windows-doors. Why this group: Cheap A/B but only an idea on plans
- Reports: lit-vector-b

<a id="i26"></a>
### 26. Reuse the paper's tile planner for any high-resolution pass

- What: Use a stand-alone planner that picks overlapping views so each target keeps its token density and maps points back, with a merge distance of about half a symbol for overlap duplicates.
- Evidence (adjacent-field): Repo tool safe_tiles.py (standard library to plan, Pillow to cut), README read; no accuracy number of its own.
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: code MIT. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Plan tiles for a dev phone photo, run the detector per tile, compare merged count against whole-image count.
- What breaks on our images: Duplicates from overlaps must be merged class-aware or windows double-count.
- Moves: plans. Why this group: Helpful only if tiling is needed.
- Reports: lit-count-a

<a id="i27"></a>
### 27. Detector-jointly-trained restorer for badly degraded drawings (offline A/B)

- What: Train a small ESRGAN on pairs made from our dev images with synthetic degradations, jointly with the detector, and A/B it on the gated bad-scan slice only; score by whether any count changes.
- Evidence (adjacent-field): Single-line diagrams, x4: interpolation recall 32.74, ESRGAN 88.93, ESRGAN trained with degradations 98.89, joint system 99.33 (precision 98.87); an independent ESRGAN turned hollow circles solid and the detector missed them; no false-positive count.
- Source: [arXiv 2312.13620](https://arxiv.org/abs/2312.13620)
- Licence: repo has no licence file; reference only. CubiCasa5K leakage: no.
- Cost: 6-8 h work, GPU hours
- Experiment: Make degraded/clean pairs from dev images; compare exact counts and false positives with Lanczos on the bad-scan slice.
- What breaks on our images: Large symbols, same degradation model in train and test, no count metric, no false-positive count.
- Moves: windows-doors. Why this group: Only after the gate finds a bad-scan slice.
- Reports: lit-sheet-a, lit-sheet-b

<a id="i28"></a>
### 28. Wall-orientation deskew for small angles plus a 4-class head for the 90-degree step

- What: Estimate the small skew from the wall-edge histogram (Hough or radial projection) and the 90-degree step with a classifier or the text vote.
- Evidence (adjacent-field): Classical Hough/FFT orientation cannot separate 0 from 90 when folded mod 90; a network fixed that on photos (average error 3.0 against 11.4 on the 30-degree task); a Fourier deskew gives 0.14 degree error on text pages.
- Source: [arXiv 2603.05942](https://arxiv.org/abs/2603.05942)
- Licence: jdeskew MIT. CubiCasa5K leakage: no.
- Cost: 2 h work
- Experiment: Only if scans show small skew; report residual angle on dev scans.
- What breaks on our images: Walls give 0/90 but never up versus down; no sign small skew is a problem on our images.
- Moves: windows-doors. Why this group: No measured need.
- Reports: lit-sheet-a, lit-sheet-b

## Idea or pitch only

<a id="i29"></a>
### 29. Learned cleaning step before detection for scans

- What: Cleaning network trained on synthetic degradation and fine-tuned on a few real photos before detection.
- Evidence (floor-plans): Deep Vectorization: 81 real degraded plans fine-tune cleaner gives IoU 79/82 vs 47 for a classical baseline. Learned super-resolution before counting lowered icon F1 0.886 to 0.875 (triage).
- Source: [arXiv 2003.05471](https://arxiv.org/abs/2003.05471)
- Licence: cleaner not released. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: None here; see sheet-normalisation scope.
- What breaks on our images: Cleaner may remove text we need.
- Moves: none. Why this group: Pointer only
- Reports: lit-vector-c

<a id="i30"></a>
### 30. Per-sheet batch-norm statistics adaptation

- What: For a detector with batch-norm layers, re-estimate BN statistics per sheet at inference to cope with the style mix; no labels needed.
- Evidence (adjacent-field): Fog shift, Faster R-CNN: AP50 20.9 source-only to 34.5 with BN statistics only, 36.5 with weak operator labels (arXiv 2407.05607 Table 2).
- Source: [arXiv 2407.05607](https://arxiv.org/abs/2407.05607)
- Licence: WSTTA Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Compare per-sheet BN adaptation against fixed statistics on mixed-style dev sheets.
- What breaks on our images: Transformer detectors mostly have no BN; no synthetic-to-real pair.
- Moves: windows-doors. Why this group: would need a CNN detector
- Reports: lit-data-b

<a id="i31"></a>
### 31. Cut legend and title-block regions off before counting

- What: Use a layout box to drop legend, notes and title block so stray symbols are not counted.
- Evidence (adjacent-field): Map sheets: content/legend split F1 0.87 at IoU 0.5 on 40 maps; mechanical sheets title block 0.99.
- Source: [arXiv 2506.16006](https://arxiv.org/abs/2506.16006)
- Licence: LayoutLMv3 weights CC BY-NC-SA; closed API in one variant. CubiCasa5K leakage: unknown.
- Cost: 1 day work
- Experiment: Only if dev sheets carry legends; compare counts with and without.
- What breaks on our images: Our sheets often have no legend.
- Moves: plans. Why this group: Little to cut on our sheets.
- Reports: lit-sheet-a, lit-sheet-c

<a id="i32"></a>
### 32. Read geometry when a vector layer exists

- What: If Stoa supplies vector PDFs, read the geometry instead of rasterising; a VLM given a render scores near zero on object F1.
- Evidence (authors-claim): Kamai benchmark (vendor-run): micro F1 0.930 against 0.015 to 0.062 for frontier VLMs; window F1 .860; the paper says the inputs are not equivalent.
- Source: [github.com](https://github.com/KamaiEnterprises/aec-geometric-bench)
- Licence: scorer Apache-2.0; 15 sheets CC BY-NC 4.0. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: context
- What breaks on our images: Vendor-run; vector input; ours is raster.
- Moves: windows-doors. Why this group: does not apply to raster plans
- Reports: lit-market-a, lit-market-b

<a id="i33"></a>
### 33. Title block position as an orientation cue

- What: Use the lower-right title block of framed sheets as an orientation anchor.
- Evidence (search-only): Drafting convention only; our sheets mostly have no title block; one abstract-only paper on AEC orientation.
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Count dev sheets with a frame before building anything.
- What breaks on our images: Few of our sheets are framed.
- Moves: room-types. Why this group: Applies to framed CAD sheets, not ours.
- Reports: lit-sheet-a, lit-sheet-b

## Do not try (with the reason)

<a id="i34"></a>
### 34. Learned super-resolution (EDSR/ESRGAN/SwinIR) before counting

- What: Do not run learned or generative super-resolution before counting; invented strokes change counts.
- Evidence (floor-plans): On the floor-plan network x2 SR cut icon micro-F1 from 0.886 to about 0.875 (toilet 0.159 to 0.099, sink 0.159 to 0.079); scene-text SR raises detection F1 but lowers end-to-end score (24.29 to 21.45); EDSR took 215-745 s per image.
- Source: [arXiv 2112.09844](https://arxiv.org/abs/2112.09844), [arXiv 2506.09993](https://arxiv.org/abs/2506.09993)
- Licence: MIT code; weights trained on CubiCasa5K. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: Hallucinated strokes give wrong exact counts.
- Moves: windows-doors. Why this group: Measured wrong direction.
- Also (count, adjacent-field): Learned super-resolution before counting. Do not use learned SR. Evidence: Invented strokes; CountGD++ issue 5 only reports it helps blurry photos. Source: [github.com](https://github.com/niki-amini-naieni/CountGDPlusPlus). Experiment: Not run. If a blurry-photo input proves unreadable, compare Lanczos against a learned upscaler on dev exact rate and look at invented strokes.
- Reports: lit-count-a, lit-count-b, lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i35"></a>
### 35. Rule-based tools fail on degraded or rotated scans where learned models hold (chemistry)

- What: Expect any rule route to need an orientation and degradation step first; do not trust a rule route on our mix of scans, rotated pages and photos.
- Evidence (adjacent-field): MolScribe Table 2: USPTO exact match OSRA 87.4, MolVec 88.4, MolScribe 92.6; blurry Staker set 0.0, 0.8 vs 86.9; with slight rotation and shear OSRA 87.4 to 4.0. COMO Table 1: ACS OSRA 55.3 vs 88.2. MolSight Table 6 repeats the drop.
- Source: [arXiv 2205.14311](https://arxiv.org/abs/2205.14311), [arXiv 2604.23546](https://arxiv.org/abs/2604.23546), [arXiv 2511.17300](https://arxiv.org/abs/2511.17300)
- Licence: MolScribe code MIT, weights MIT. CubiCasa5K leakage: no.
- Cost: 0 h
- Experiment: None; justifies a rotation and blur augmentation set in any rule-route test.
- What breaks on our images: Chemistry images, one molecule per image; no counts of repeated symbols.
- Moves: none. Why this group: Cautionary: rules are fine on clean renders only
- Reports: lit-vector-a, lit-vector-b

<a id="i36"></a>
### 36. Tesseract OSD as an orientation detector

- What: Do not rely on Tesseract orientation detection; at most use it as a third vote.
- Evidence (adjacent-field): Source shows a default minimum of 50 characters and a skipped page below half of it; a plan has 5-15 labels.
- Source: [github.com](https://github.com/tesseract-ocr/tesseract)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none
- What breaks on our images: Returns nothing on sparse text.
- Moves: room-types. Why this group: Cannot fire on plans.
- Reports: lit-sheet-b, lit-sheet-c

<a id="i37"></a>
### 37. VLM zero-shot page orientation

- What: Do not use a general VLM to decide the 90 or 270 rotation.
- Evidence (adjacent-field): RotBench: all models struggle to tell 90 from 270; best zero-shot 270 accuracy 0.59.
- Source: [arXiv 2508.13968](https://arxiv.org/abs/2508.13968)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none
- What breaks on our images: Photos only, but the failure is the one we need.
- Moves: room-types. Why this group: Measured weak.
- Reports: lit-sheet-b

<a id="i38"></a>
### 38. Heavy 12-class document rotation models

- What: Skip the 304M-parameter rotation model; weights unreleased and trained on text pages.
- Evidence (authors-claim): 4-class 96.81% (English) and 92.68% (Indic) on text pages; weights 'upon acceptance'; its own failure analysis lists text-sparse pages.
- Source: [arXiv 2511.04161](https://arxiv.org/abs/2511.04161)
- Licence: none released. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Unavailable.
- Moves: none. Why this group: Not available and wrong domain.
- Reports: lit-sheet-a, lit-sheet-c

<a id="i39"></a>
### 39. Scans fail on scale and counts for every tool tested

- What: Treat scans as the weak case: refuse or flag when scale cannot be set.
- Evidence (authors-claim): Kansas study: scale could not be set on a scanned submittal; one student could not use Togal with several scales on one drawing; 37.3% on degraded scans against 99.8% born-digital (self-made).
- Source: [togal.ai](https://www.togal.ai/case-study/peer-reviewed-study-togal-ai-vs-on-screen-takeoff), [github.com](https://github.com/ajflow/pdf2takeoff)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: scale-areas. Why this group: known failure
- Reports: lit-market-a

<a id="i40"></a>
### 40. Structure-only orientation for text-sparse plans

- What: Do not expect a published method to give the orientation of a plan with few labels.
- Evidence (search-only): No 2025-2026 method found for text-sparse drawings; Zernike-moment invariance was tested only at 45 degrees; VLMs confuse 90 and 270 (best zero-shot 270 accuracy 0.59); Tesseract OSD needs 50 characters.
- Source: [arXiv 2508.13968](https://arxiv.org/abs/2508.13968), [arXiv 2504.03241](https://arxiv.org/abs/2504.03241)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Orientation is a text problem for us.
- Moves: room-types. Why this group: Nothing proven; use the text vote.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c
