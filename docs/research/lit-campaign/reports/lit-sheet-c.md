# lit-sheet-c: practical fit for sheet normalisation and layout (L9, angle c)

Worker lit-sheet-c, 2026-11-14. Read-only research: no datasets or weights downloaded, nothing run on our images; papers saved by the fetch tool were read locally. Extends
`stoa-hardimg.md` and notes 01, 02, 03, 08 and `lit-normalise.md`, `lit-degradation.md`; those are not repeated.
Reading log with one line per source: `lit-sheet-c-log.md` (same folder).

Marks: **verified** = I opened the page or file and the number is there (date read 2026-11-14 unless stated).
**reported** = the authors' own claim, or a number I could read only in a model summary of the page (flagged).
**estimate** = mine, no source. All licences below were read from the LICENSE file (`gh api repos/<o>/<r>/license`) or the
raw Hugging Face card, code and weights separately. "Leak" = trained on CubiCasa5K or a repackage.

## 0. What this angle found, in six lines

1. **Counting plans on a sheet:** nobody has published it for floor plans. The nearest solved problem is compound-figure
   separation, and its recipe (a detector trained on synthetic composites, since composites come with exact boxes) is a fit
   for us because 3,044 dev images show a single plan and can be pasted together. Real-image performance falls far below
   synthetic performance in the one paper that reports both (section 2, row 1).
2. **Orientation from structure with almost no text:** no proven method exists. Every 4-class page-orientation model I
   opened was trained on text pages and none was tested on drawings or sparse pages. What is proven is the plumbing: a 7 MB
   Apache-2.0 4-class classifier that runs on CPU in about 3 ms (verified), the failure mode that correct-class
   confidence sits near 0.45 (a third-party crate's code comment), and that a small EfficientNet or MobileNet head learns
   4-way orientation from a few thousand pages in minutes (dedoc, Genius Scan). Training our own head is row 4.
3. **Layout detectors for sheets:** general-document layout pretraining *hurt* on architectural sheets (0.772 to 0.589
   mAP50:95 in one 2026 ablation, full paper read). RF-DETR-M fine-tuned on 551 drawings got mAP50 0.949.
4. **Quality gating:** generic no-reference image-quality scores predicted OCR error for 2 of 8 systems and not for the other 6 (n=60).
   The measured, licence-clean idea that does transfer is the fingerprint-quality one: train the quality score to predict
   the downstream error, not image sharpness.
5. **Upscaling:** the earlier verdict (Lanczos, never generative) stands. One new reading changes how to use it: SNIP
   (small-object mAP 19.6 / 19.9 / 21.4 at 800 px / 1400 px / scale-normalised) says keep every object inside one size
   range, so normalise each plan crop by a measured scale cue instead of upscaling whole sheets (row 11).
6. **Licence traps found:** MatMMExtract code is GPL-3.0; Ultralytics, and with it every YOLO panel or blueprint
   detector, is AGPL-3.0; DocLayout-YOLO code is AGPL-3.0 (its weights card says Apache-2.0).

## 1. Top 5, ranked

Ranking = (evidence that it works on a problem shaped like ours) x (licence clean) / (hours to a first number).
Hours are estimates for one person on a 12 GB RTX 4070 and include writing the loader.

### 1. Plan counter: RF-DETR trained on synthetic multi-plan sheets, fine-tuned on the real multi-plan dev images. Verdict: TRY
- What: paste 2 to 4 single-plan dev images into one canvas with gutters, borders or none, random rot90 per plan, random
  background tone; the paste boxes are exact labels. Train a one-class detector ("plan"), count detections. Check against
  the 672 + 109 + 3 real multi-plan dev images (record: context file, section 2).
- Source of the recipe: Open-PMC-18M (arXiv 2506.02738, 2025): DAB-DETR trained on 500,000 synthetic compound figures built
  from single-panel images. Table 2, mAP / F1 in %: synthetic validation 98.58 / 99.96; real ImageCLEF 2016 36.88 / 73.55;
  the previous MedICaT-trained DETR 28.20 / 64.85 and a zero-shot Qwen2.5-VL-32B 30.12 / 68.12 on the real set
  (verified, html and the full PDF text extracted locally, read 2026-11-14). Training recipe, verified: 40 epochs, batch 64,
  initial learning rate 1e-5, 20,000 held-out synthetic images; panel pool from ROCO, SICAP, HAM10000, MedMNIST sets, PAD-UFES-20
  and PlotQA, each modality about 16.7% plus 16.7% mixed; random margins, labels inside or outside, fixed aspect ratio per figure.
  The authors say they release the dataset, curation code, subfigure detection models and training pipelines; the detector
  is on Hugging Face (row 6). The sim-to-real gap is the lesson: 99 on synthetic, 37 mAP on real. Plan on fine-tuning
  with real multi-plan sheets, and measure exact plan count, not mAP.
- Alternative warm start: `vector-institute/pmc-18m-dab-detr` (Apache-2.0 card, 43.75M parameters, already trained for "find the sub-images of a composite"); run both on the same composites and keep the one with the better exact plan count.
- Detector: RF-DETR S/M/L, code Apache-2.0 (gh api), detection weights N, S, M, L Apache-2.0, XL and 2XL under the
  Roboflow Platform Model License (verified, https://github.com/roboflow/rf-detr and https://rfdetr.roboflow.com/latest/,
  read 2026-11-14). COCO JSON in, `pip install "rfdetr[train]"`. Resolutions: S 512, M 576, L 704 (must divide by 32).
  Docs advise at least 8 GB VRAM, N and S fit 6 GB at reduced batch, gradient checkpointing saves 30-40% memory for
  about 20% more time, `batch_size="auto"` probes memory. Latest release 1.12.1 on 12 Nov 2026.
- Why a detector is plausible for big boxes: full paper read (arXiv 2607.18997, EC3 2026, 8 pages; the PDF text extracted with
  pypdf in a scratch folder, so this row is **verified**, 2026-11-14). Facade Engineering Layout Dataset: 551 drawings from
  10 projects at 300 dpi, 3509 x 2480 up to 14042 x 9934 px, nine classes incl. "Layout; Plan; GA" (21 images, 26 boxes);
  multi-label stratified 70:15:15, no augmentation. Table 2 (mAP50:95 / mAP50 / P / R / F1; params; T4 time): RF-DETR (m)
  0.890 / 0.949 / 0.985 / 0.800 / 0.889; 33.7M; 44.8 ms. Faster R-CNN 0.779 / 0.930 / 0.829 / 0.924 / 0.874. YOLOv12 (m)
  0.755 / 0.871. Qwen3-VL-8B 0.668 / 0.758 / 0.916 / 0.906 / 0.911 (confidence fixed at 1.0, 6,120 ms per drawing).
  RF-DETR per-class mAP50:95: plan 0.969, section 0.917 and 0.845, elevation 0.849, legend 0.928, notes 0.734; the plan and
  GA classes have the fewest images and the authors say that limits them, so the 0.969 sits on a test slice of a few
  drawings. Models were fed at default sizes with aspect preserved: **1344 x 800 for RF-DETR**, Faster R-CNN and Qwen3-VL, 640 x
  640 for YOLOv12 and DocLayout-YOLO; the RF-DETR, Faster R-CNN, YOLOv12 and DocLayout-YOLO runs were all trained on one
  NC4as-T4-v3 instance (a 16 GB T4), so a non-square 1344 x 800 RF-DETR-M fine-tune fits 16 GB (the paper gives no
  batch size or training time). The authors say plain resizing "inevitably leads to the loss of fine-grained textual
  features and thin geometric lines". Dataset and code release: not stated.
- Repo check (verified 2026-11-14, pyproject.toml, LICENSE and issues of roboflow/rf-detr): core dependencies are torch,
  torchvision, numpy, supervision (MIT), pydantic, requests; the `train` extra adds peft (Apache-2.0), pytorch_lightning,
  torchmetrics, pycocotools, scipy and the `roboflow` package (Apache-2.0). No AGPL or GPL package in the lists I read.
  Three COCO-evaluation packages in that extra (hotcoco, vernier, ultrafast-pycocotools) I did not look up. The optional
  `augment` extra pulls `albumentations` (PyPI shows 2.0.8, MIT licence text, read) and must not be swapped for
  AlbumentationsX (AGPL, per earlier note 06). Issue #1052 (open, Sep 2026): rectangular training is not officially
  supported and the maintainers advise squashing to square; one user reports about 20% better accuracy from a native 3:4
  ratio after a local hack (reported, a comment, not a measurement I can check). Our sheets run from landscape to tall, so squash
  is acceptable for finding big plans and a poor idea for symbols. Issue #958 (open): a user found RF-DETR Nano far worse on a small-ball dataset than on players, a maintainer answering that low resolution hurts small objects and advising Small or Medium over a higher Nano resolution (reported; belongs to L2). OOM issues are mostly about the segmentation variants
  at validation (#1460, #1084, #646), all closed; a T4 run of Seg-Medium at batch 1 ran out of memory on 1.6.5 and was
  declared fixed in 1.7.0. Use detection, not segmentation, for plan boxes. Open issue #780 (SAHI with the segmentation model
  misses cells in dense tiles) belongs to L2.
- Memory: S at 512 px, batch 8 x accumulation 2 is the cookbook default (verified, https://rfdetr.roboflow.com/latest/cookbooks/fine-tune_detection/);
  fits 12 GB by the docs' own guidance. Cookbook time: 50 epochs on about 1,500-2,600 images in 15-30 min on "RTX 3090 or
  similar" (verified). Ours would be about 5,000 composites per epoch set: estimate 1 to 2 h for the first number, plus 45
  min for the composite generator. **Estimate: 2 to 3 h.**
- Fills: `plans` (count) and gives a per-plan crop for every later stage (so detector, OCR and room logic run per plan).
- What breaks on our images: (a) plans without a drawn frame sit close together, so boxes merge; (b) a plan with an inset,
  a legend, or a second storey drawn very small; (c) the per-plan box is not exported yet for real sheets, so the real
  fine-tune needs it (union of that plan's elements is a start, whitespace components a second source); (d) synthetic
  seams are too clean: add JPEG, blur and the original sheet margins; (e) a 240 px sheet becomes unreadable at 512.
- Cheaper first: the classical separator-band method. Taschwer and Marques (arXiv 1606.01021, Multimedia Tools and
  Applications 2016; full paper read from the saved PDF, **verified**, Table 5 and Section 3.4): binarise at the mean, take
  the per-line projection, keep runs of fully-white lines at least `band_minsepwidth` wide, keep the candidate set only
  if the spacing variance is small, drop bands near the border, recurse on both halves and pick the direction with the lower spacing
  variance. On the ImageCLEF 2015 compound-figure separation test set: band detection for every image 82.2%
  accuracy, edge detection for every image 58.0%, best learned switch between them 84.9% (LogReg, simple11, greedy); a
  manual stitched/non-stitched split gave the NLM method 84.6%. The same paper cites a competitor that used connected-component
  analysis followed by band detection at 82.8%, and 82.5% with connected components alone, so the band step added almost
  nothing there. Runtime 0.3 s per figure in MATLAB on a 2008 CPU. Failure cases shown (Fig. 8): a dark frame blocks the
  bands, no continuous separator, binarisation noise, band over-segmentation, panels with no separator. For plans: 30 to 60 min in
  numpy, no weights, no licence question. Do this before the detector; it sets the bar and its failures are the detector's
  training set. Note the dataset is biomedical figures with a modest share of stitched panels, so 82% does not carry over to our sheets.
### 2. Orientation: PP-LCNet_x1_0_doc_ori as a measured vote, not a decision. Verdict: TRY (measure on 100 dev images first)
- What: 4-class page orientation (0, 90, 180, 270), 7 MB, top-1 99.06% on a self-built 1,000-image set of
  ID and document scenes, CPU 3.24 ms and GPU 2.62 ms on the vendor's table; ONNX copy exists (verified,
  https://www.paddleocr.ai/latest/en/version3.x/module_usage/doc_img_orientation_classification.html, model card
  https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori and the `_onnx` card, read 2026-11-14).
- Licences: code PaddleOCR Apache-2.0 (gh api), card header `license: apache-2.0` for both Paddle and ONNX weights.
  **Leak: no** (document data; it has never seen CubiCasa5K, which is not a text-page set).
- Not tested on drawings or sparse pages: the page does not describe the evaluation set beyond "multi-scenario", does not
  say whether training used text-free images. docTR's page predictor (`mobilenet_v3_small_page_orientation`) states no
  accuracy, class list, input size or weights licence in its docs (verified, https://mindee.github.io/doctr/using_doctr/using_models.html).
- A third-party Rust crate runs this exact ONNX with a 224x224 centre crop of a short-side-256 resize and sets
  `MIN_CONFIDENCE = 0.35`, with the comment that a correct 4-class prediction sits near 45% (verified, source read at
  https://docs.rs/crate/kreuzberg/4.5.3/source/src/doc_orientation.rs). Two consequences for plans: a centre crop drops
  the border where plan labels often sit, and confidence will be low on exactly the pages that matter. Feed it the
  whole page padded to square instead and measure.
- Tesseract's own docs say nothing about a minimum amount of text for psm 0, only that "By default Tesseract expects a page of text" and that big borders can cause an "empty page" (verified, https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html, read 2026-11-14). The source says more (opened myself, raw osdetect.cpp, 2026-11-14, Tesseract Apache-2.0): the orientation script detector reads `min_characters_to_try` and prints "Too few characters. Skipping this page" below it, so a plan with a handful of labels returns nothing; the default is 50 in tesseractclass.cpp (same session, also reported by lit-sheet-b); the crate above calls Tesseract's OSD crash-prone on raw images without DPI metadata (reported). Apache-2.0 code (gh api). Use it only as a third vote.
- How to use: run it, run OCR at 0/90/180/270 on the label pass anyway, and take the rotation with the most closed-
  vocabulary hits (MH, OH, K, KH, WC...); the classifier is the tiebreak and the cheap prior. Cost: ms.
- Fills: the pre-OCR rotation of the page; not needed for symbol detection if the detector trains on rot90 and flips.
- What breaks: sparse text (a plan may have 5 two-letter labels at 8 px); the classifier's own paper family fails when
  "text is not the majority of the page" (section 5, Seeing Straight).

### 3. Quality gate trained on our own error, not on blur. Verdict: TRY (idea from fingerprint quality; no code taken)
- Also read: a 2025 JEITA-committee catalogue of OCR disturbance factors (arXiv 2504.14913, full html) lists illumination, shadow, camera low
  pixel count, viewpoint, ruling lines and characters-inside-figures, but gives **no** minimum character height, dpi or tilt tolerance and
  no pre-OCR gate; its numeric criteria are in two Japanese documents I did not fetch. So there is no sourced pixel threshold to copy.
- Evidence against generic scores: on 340 photographed clinical reports (n=60 annotated), five no-reference metrics
  (BRISQUE, NIQE, PIQE, Laplacian variance, DeQA-Doc) correlated with OCR error by rho up to 0.62 for Tesseract and 0.44
  for one PaddleOCR number; "all other models: low and nonsignificant correlations" (verified, Appendix D of
  https://arxiv.org/html/2511.13523v1, arXiv Nov 2025; per-metric values are only in figures I could not read).
  So Laplacian variance and friends will not gate a detector.
- What transfers: NFIQ 2 "links image quality ... to operational recognition performance" (verified, README of
  https://github.com/usnistgov/NFIQ2, standardised as ISO/IEC 29794-4) and OFIQ does the same for faces (ISO/IEC 29794-5,
  https://github.com/BSI-OFIQ/OFIQ-Project). Recipe: compute cheap features, regress them onto the measured outcome.
  For us the outcome is |predicted count - gold count| per image on dev, features are short side in px, estimated line
  width (median stroke run length), estimated door-leaf size, fraction of the page that is ink, detector confidence
  entropy, full-page vs tiled disagreement. A gradient-boosted tree, 3,828 rows, minutes to train.
- Licences: NFIQ2 LICENSE.md = NIST public-domain text (SPDX shows NOASSERTION, I read the file); OFIQ LICENSE.md = MIT with
  a dependency table. We would use the idea only, so neither is shipped.
- Fills: the confidence field and the abstain flag; it does not fill extraction JSON. Hours: 2 (after the first detector
  run exists, because it needs per-image errors). **Estimate.**
- What breaks: it is calibrated on CubiCasa-style images and says nothing about a new source; leakage is not an issue
  because the features are ours.

### 4. Own 4-way rotation head, RotNet style, with pseudo-labels from the OCR vote. Verdict: TRY after row 2's measurement (was MAYBE)
- RotNet (Gidaris et al., ICLR 2018, arXiv 1803.07728) frames orientation as 4-way classification and states the task is
  well posed when objects have a canonical "up", with round objects the stated exception (verified,
  https://arxiv.org/html/1803.07728v1 part read; no rotation-task accuracy printed in the text I read). A floor plan's "up"
  is its printed text, not gravity, which is the whole difficulty. The community Keras repo d4nst/RotNet is MIT
  (gh api; README read: MNIST and street-view demos, no accuracy stated, last commit date not visible); the official
  code gidariss/FeatureLearningRotNet is MIT (gh api). Neither is worth pulling: the loss is five lines of PyTorch.
- Evidence that a small head learns 4-way page orientation from a few thousand images: dedoc's EfficientNet-B0 (4 orientation
  classes plus a column count), trained 7 epochs with SGD lr 0.001 on 4,121 open-data documents each used at four rotations,
  scores precision/recall/F1 0.998-1.0 on 825 test images per class (verified: the benchmark file
  `resources/benchmarks/orient_classifier_scores.txt` and the training script in https://github.com/ispras/dedoc, read
  2026-11-14; code Apache-2.0 by gh api; weights `dedoc/scan_orientation_efficient_net_b0` card `license: apache-2.0`,
  `model.pth`; dataset card states no licence; leak: no). Caveat that decides everything for us: those are text pages in 14
  languages, and the test set shares the training distribution. A vendor (Genius Scan, Jan 2024, vendor-reported, no
  accuracy given) says it dropped text-based orientation because it "didn't work well" on documents without printed
  text and ships a MobileNet fine-tuned from ImageNet with four outputs, 224 px input, INT8, 676 KB, trained on hundreds of
  thousands of internal pages rotated four ways (verified, https://blog.thegrizzlylabs.com/2024/01/genius-scan-auto-rotate-technology.html).
  So a learned, non-OCR head is the standard practice for pages with little text; what is missing is any number on drawings.
  Training cost for our version is minutes per epoch on 3,828 images at 224 px (estimate).
- Known failure of the rotation task: a 2020 sketch paper (Deep Self-Supervised Representation Learning for Free-Hand Sketch,
  arXiv 2002.00867, Section IV-B, html read) says RotNet's pretext task "fails to work well on centrosymmetric sketches"
  because the visual change under rotation is "limited and difficult to captured even for human eye". A bare plan with
  point-symmetric walls and no text is exactly that case; the head must abstain when its four class scores are close.
- Recipe: dev images whose upright was fixed by the OCR vote (or by the lexicon hit count) become labels; rotate all four
  ways; fine-tune a small CNN. Without a text-derived label it learns nothing about plans.
- Evidence that orientation modules pay off downstream: a rotation module on a Phi-3.5 encoder lifted exact match from
  82.13 to 88.70 on Indian government documents (verified, arXiv 2602.16430, read 2026-11-14; no standalone rotation
  accuracy, proprietary data). Evidence it is not solved for sparse pages: Seeing Straight's own failure analysis.
- Hours: 2 to 3 plus label bootstrap. **Estimate.** Do it only if the OCR vote is found to fail on measured images.
- Leak: no, if trained from ImageNet or PP-LCNet weights on dev images; the dev images are CubiCasa5K pixels, so a
  head trained on them carries the dataset's style, which is fine for dev use and invalid on any claim about eval images
  until the eval split is scored once at a milestone.

### 5. Layout-detector zero-shot (PP-DocLayoutV3) as a plan finder. Verdict: SKIP for now, one 20-image probe at most
- PP-DocLayoutV3: card `license: apache-2.0`, code PaddleOCR Apache-2.0, "accepted to ECCV 2026", polygons and reading
  order (verified, https://huggingface.co/PaddlePaddle/PP-DocLayoutV3 README). Its paper (PaddleOCR-VL-1.5, arXiv
  2601.21957, v2 Apr 2026) says hard-case mining added "comics, CAD drawings, and high-aspect ratio screenshots", 38k+
  samples, 25 classes, 150 epochs, and reports no layout mAP at all (verified, https://arxiv.org/html/2601.21957).
  Its own technical report (RT-DocLayout, arXiv 2606.23344, 22 Jun 2026, 33M parameters; sections 1 to 4.1 read verbatim, the rest only as a
  summary) scores layout only through downstream parsing on OmniDocBench (overall 94.50) and Real5-OmniDocBench (92.05, skew 91.66),
  132.1 FPS at batch 32 on an A100, trained on 38k in-house pages whose listed domains (papers, textbooks, reports, slides,
  newspapers, exams, invoices) contain no drawings; the two papers disagree on CAD drawings, so treat the CAD claim as unverified.
  Code and weights licence: only the card (Apache-2.0).
- Docling heron / egret (arXiv 2509.11720, 2025): RT-DETRv2 and D-FINE, 640x640, 17 classes, no drawing class, drops any
  Picture over 90% of the page, best mAP 0.78 on its canonical set (verified, https://arxiv.org/html/2509.11720); models
  Apache-2.0 on Hugging Face, code MIT (docling-ibm-models, gh api).
- The 2026 AEC ablation says general-document pretraining hurts drawings (0.772 COCO-pretrained YOLOv10m, 0.727 DocLayout-
  YOLO architecture with COCO weights, 0.589 with DocLayNet and DocSynth pretraining; verified, Table 4 of the full paper). Treat a document-layout model
  as a probe, not a plan.
- GreenMap yolo11x-blueprint-layout-detector: weights `license: apache-2.0`, Ultralytics runtime is AGPL-3.0 (gh api),
  training data not stated on the card (read in full), so **leak: unknown**. Do not ship. Card, own validation (reported): classes
  drawing_area, legend_block, title_block; 178 images, 958 instances (694 drawing_area, so about 3.9 drawing areas per image,
  i.e. multi-drawing sheets are the normal case there); mAP50 0.984, mAP50-95 0.921; input 1472 x 1472. A usable comparison point for
  row 1 and a sanity probe on 20 sheets, nothing more.

## 1b. How this extends the measurements in sections 2 and 3 of the context file

- **Plans per sheet (open, about 1.5 points on dev).** 784 of 3,828 dev images (20.5%, from 672 + 109 + 3 in section 2) show
  more than one plan, so the sheet stage touches one image in five. Row 1b and row 1 attack exactly this; everything else
  in my scope touches fewer images. A plan crop also hands the symbol detector a plan alone, but a crop of an 855 px sheet is
  smaller than the sheet, so upscale it (Lanczos, the earlier verdict) before detection. Expected value: **estimate**,
  at best the 1.5 points, only if per-plan boxes can be trained on.
- **Rotation (about one image in three).** Section 3 already settles that the detector trains with rot90 and flips. My
  rows do not change that. Page orientation matters for the label pass only: the earlier PP-LCNet line classifier is 0/180
  only, so the 90/270 gap is what row 2 fills, and the OCR-at-four-rotations vote is the structure-free check.
- **Label OCR (23-81% exact by room type with RapidOCR; glyphs under about 6 px lost even after Lanczos 2x).** A quality gate
  feature that predicts "glyph height under 6 px" would route those sheets to abstain instead of guess. That is row 3's
  feature list; it adds the glyph-height estimate the earlier gating note (08) listed as a gap.
- **Sizes.** Median longest side 855 px, minimum 240: RF-DETR S wants 512 px and the cookbook range is 384-640, so a sheet is
  resized down for plan finding (plans are large) and cropped at full resolution for symbols. That split is the reason
  the plan finder and the symbol detector should be two models, not one.
- **Upscaling, one more reading (SNIP, Singh and Davis, CVPR 2018, arXiv 1711.08189; full text read from the saved PDF,
  verified).** R-FCN ResNet-50 on COCO, mAP on objects under 32 x 32 px: trained at 800 px 19.6, at 1400 px 19.9, multi-scale 19.5,
  trained on small objects only at 1400 px 16.4, SNIP 21.4. The authors' reading: higher resolution helps small objects but
  "blows up the medium-to-large objects", and a train/test resolution mismatch costs accuracy; their fix keeps every object
  inside a fixed size range. For us that means: do not just upscale the sheet. After the plan finder, rescale each plan
  crop so a measured scale cue (median wall thickness or door-leaf width from a distance transform of the ink mask) lands
  at one fixed value, then train and test the symbol detector at that scale. Bathtubs and saunas stay in range, a 5 px
  window cell does not. This is a one-hour numpy step that costs nothing at inference; the evidence is on COCO photos,
  not drawings, so measure on 50 dev plans before trusting it. Code of the paper's authors is not needed.
- **Not extended:** binarisation, dewarping, generative SR. Nothing I read changes the earlier verdicts.

## 2. Full table

| # | Method | From | Year, venue | Code (licence) | Weights (licence) | Leak | Input, memory, time | JSON field | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | RF-DETR S/M on synthetic multi-plan composites | transfer: compound-figure separation (recipe), our field (detector) | 2025 (2506.02738 recipe); RF-DETR arXiv 2511.09554 (ICLR 2026 per 2607.18997 refs), release 1.12.1 on 12 Nov 2026 | rf-detr Apache-2.0 (gh api) | N/S/M/L Apache-2.0, XL/2XL PML (README) | no (COCO) | 512-576 px by docs; 1344 x 800 on a 16 GB T4 in 2607.18997; est. 2-3 h | `plans` | try |
| 1b | Separator-band recursion (Taschwer and Marques) | transfer: compound figures, classical | 2016 | none found; write in numpy | none | no | CPU, 0.3 s/figure in MATLAB on a 2008 CPU; est. 1 h | `plans` | try first |
| 2 | PP-LCNet_x1_0_doc_ori (4 class) | transfer: document OCR | PaddleOCR 3.x | PaddleOCR Apache-2.0 | Apache-2.0 (card) incl. ONNX | no | 224 px, 7 MB, 3.24 ms CPU; est. 1 h to measure | page rotation | try |
| 2b | docTR page orientation (also OnnxTR ONNX export) | transfer: document OCR | docTR | Apache-2.0 (gh api, both) | docTR docs state none; OnnxTR card `license: apache-2.0` | unknown | 512x512 in docstring; no accuracy printed on either | page rotation | skip: nothing to measure against |
| 2c | DINOv3 ViT-S page-flip classifier (Tibetan manuscripts) | transfer: manuscripts | 2025-26 | n/a | DINOv3 licence (custom, card links it), not in our allowed list | n/a | 180 only | page rotation | out: licence, 2 classes |
| 3 | Outcome-calibrated quality score (NFIQ2 idea) | transfer: fingerprint/face quality | NFIQ2 v2.3, OFIQ (2024+) | NIST public domain / OFIQ MIT | n/a (idea only) | no | CPU; est. 2 h | confidence, abstain | try |
| 3b | Generic NR-IQA (BRISQUE, NIQE, Laplacian, DeQA-Doc) | transfer: document quality | 2511.13523, 2025 | anonymous repo, no licence | n/a | n/a | ms | none | skip: significant for 2 of 8 systems only |
| 4 | RotNet-style 4-way head with OCR pseudo-labels (recipes: dedoc EfficientNet-B0, Genius Scan MobileNet) | transfer: self-supervised rotation, document scanning | ICLR 2018; dedoc 2024; vendor blog 2024 | MIT (d4nst/RotNet, gidariss); dedoc Apache-2.0 | dedoc `model.pth` Apache-2.0 (text pages); ours none shipped | no | 224 px; 7 epochs on 4k images; est. 2-3 h | page rotation | try |
| 5 | PP-DocLayoutV3 zero-shot | transfer: document layout | ECCV 2026 | Apache-2.0 | Apache-2.0 | unknown | not reported; PaddleOCR-VL-1.5 gives no mAP | `plans` (probe) | skip |
| 5b | Docling heron / egret | transfer: document layout | 2025 | MIT (docling-ibm-models) | Apache-2.0 (card) | no | 640 px, 28 ms/img on A100 batch 200 | none | skip: no drawing class |
| 5c | DocLayout-YOLO | transfer: document layout | 2024 | AGPL-3.0 (gh api) | Apache-2.0 card | no | n/a | none | out: AGPL |
| 5d | GreenMap YOLO11x blueprint | our field | 2025-26 | Ultralytics AGPL-3.0 | Apache-2.0 card | unknown | n/a | `plans` | out: AGPL runtime, unknown data |
| 6 | vector-institute/pmc-18m-dab-detr (DAB-DETR, 43.75M params) | transfer: compound figures | 2025 | DAB-DETR Apache-2.0 (gh api); Open-PMC repo Apache-2.0 | Apache-2.0 (model card, safetensors, Aug 2025) | no (biomedical figures) | transformers `AutoModelForObjectDetection`; memory not stated, **estimate** fits 12 GB at small batch; est. 2 h to a first fine-tune | `plans` | try as the warm start next to RF-DETR |
| 7 | MatMMExtract YOLO12-m panels | transfer: compound figures | 2026 | pipeline GPL-3.0, eval repo MIT (gh api) | not stated | no | 1024 px, 50 ep, one A6000, 2,249 train images | `plans` | out: GPL/AGPL; numbers useful only |
| 7b | ExSCLAIM two-stage (label YOLOv3 + subfigure detector) | transfer: compound figures | 2021 | GPL-3.0 | n/a | no | needs printed panel labels, which plans lack | `plans` | skip: relies on letter labels |
| 8 | FigEx2 (Qwen3-VL-8B + DAB-DETR) | transfer: compound figures | 2026 | repo licence not found (gh 404) | none found | no | 4 x A100 80 GB train | `plans` | skip: too heavy, no licence |
| 9 | Seeing Straight 304M 4-class orientation | transfer: document OCR | 2025, v2 Mar 2026 | none released ("upon acceptance") | none | n/a | H100 0.5 s | page rotation | skip: not available |
| 10 | Zernike-moment normalisation on region graphs | our field | 2025 (2504.03241) | none found | none | uses CubiCasa5K (400 plans) | vector graph input | none | skip: needs vectorised input; only 45 degree tested. Verified in the full PDF (2026-11-14): on rotated CubiCasa5K, average F1 67.01 with normalisation vs 50.70 without (IoU 56.09 vs 38.16); window F1 78.25 vs 24.82, door 83.44 vs 36.81 |
| 11 | Per-plan scale normalisation before the symbol detector (SNIP idea) | transfer: detection of small objects | CVPR 2018 | bharatsingh430/snip Apache-2.0 (gh api), not needed | none | no | 1 h numpy; est. | none (feeds element detection) | try, measure on 50 plans |

Notes on the table: row 7's numbers (P 0.9601, R 0.9406, F1 0.9502, mAP50 0.9227 on 281 test images of a 2,811-figure
set, in-domain; confirmed in the full PDF text, trained with Ultralytics, 1024 x 1024, 50 epochs, one RTX A6000) are the only measured panel-detector figure I could read in full; the earlier Exsclaim tool
(classes A to H only) got F1 0.7453 on the same split (verified, https://arxiv.org/html/2606.29667, arXiv Aug 2026).

## 3. From other fields: transfer notes

**Compound-figure separation (scientific papers).** Task: split one image into sub-panels. Our object: one plan on a
multi-plan sheet. Why it transfers: same shape (several rectangles of drawn content in one canvas, labels sometimes
present), the training trick (composite from singles) is free for us, and two 2026 papers show a plain DETR or YOLO does
the job: a YOLO at 1024 px on 2,249 training images, and DAB-DETR in-domain. Breaks: panels in papers have borders and letter labels; our plans often
have neither and sit closer together. FigEx2 (arXiv 2601.08026, verified) reports DAB-DETR alone at mAP50 0.830 and
mAP50:95 0.697 on its in-domain test set, versus 0.181 / 0.165 on the harder MedICaT set: a detector trained in one
layout style loses most of its score on another, so match composite styles to our sheets. Works as is? No: needs our
composites. Forward walk from 2506.02738: 9 citing papers listed by Semantic Scholar (Dec 2025 to Jul 2026), one of them
panel-level (MatMMExtract); the rest use the dataset for pretraining. From 2601.08026: none yet. Read one more citer (html, 2026-11-14): Panel2Patch, 2512.02566, parses panels with a vision-language model (Qwen2.5-VL) rather than a trained box detector, and its comparison table labels the Open-PMC-18M detector "YOLO", which contradicts the Open-PMC paper and card I read (DAB-DETR); I trust the primary source. Nothing to take for plan counting; a VLM per sheet is the L2 scope's call.

**Comic panels.** Task: panel boxes in comic pages. The repo mosesab/yolov12-comic-panel-detection is MIT, the card
for `mosesb/best-comic-panel-detection` says Apache-2.0 with `library_name: ultralytics` (both read). Our object: a plan.
Breaks: trained on panels with gutters on photos and art, AGPL runtime, nothing about line drawings. Idea only.

**Engineering-drawing sheets (mechanical, AEC).** arXiv 2510.21862 (Oct 2025, v2 Jan 2026, ICIEA 2026): YOLOv11-det finds
views, title blocks and notes on 1,000 mechanical drawings, then YOLOv11-obb for annotations (verified, full PDF read 2026-11-14: 80/20 split of 1,000 drawings, normalised confusion matrix 0.96 for Views, 0.99 title block, 0.98 notes; no mAP given, in-distribution test only). Idea transfers (view boxes first, then
per-region work); the code stack is AGPL, so we would redo it on RF-DETR. The AEC sheet benchmark is in row 1.

**Industry precedent for a box detector with NMS on a drawing (not proven to count plans).** US patent 12,243,342 B2 (Autodesk, filed 2021-11-08, listed as
granted 2025-03-04; page now read in full (132k characters of text), claims included):
a keyword filter and a multi-label CNN decide that a drawing contains a floor plan, then a fully convolutional network
takes the whole image and outputs "one or more" floor-plan boxes with confidence scores; low scores are thresholded and overlapping boxes removed by
non-maximum suppression, leaving "a given floorplan bounding box" with a high score that does not overlap the others. The full text never says the number of
boxes is the plan count (my earlier wording, from a model summary, overstated that), and gives no accuracy number. It shows the box-detector-plus-NMS shape of row 1
in industry use, but is a patent: read its claims before building the same pipeline, and leave that to the owner (not a legal opinion).
Claims read (full page, 132k characters of text, 2026-11-14): independent claim 1 is keyword-gated floor-plan detection in extracted text, then extracting the floor-plan image and generating a boundary segmentation with boundary types; dependent claims add room segmentation from the vectorised boundaries. Claim 1 does not recite counting several plans by box detection; that part is in the description only (non-maximum suppression appears twice in the text). Still not a legal opinion; the owner decides.
For drawings, the 2017 ICDAR short paper "Automatic Orientation Correction of AEC Drawing Documents" (Seraogi et al., ARC
Document Solutions and ISI Kolkata, DOI 10.1109/ICDAR.2017.252) is the only drawing-specific orientation work I found; the
repository page gives only the abstract (orientation and text-region localisation of AEC drawings), no method, data or
numbers, and says the document is not available. Abstract-only.

**Fingerprint and face capture quality (NFIQ 2, OFIQ).** Task: predict whether an image will work for matching.
Our object: a CubiCasa image that will or will not give correct counts. Transfers because both are "quality = predicted
downstream performance" and are calibrated on measured outcomes. Breaks: needs per-image error labels, which exist on
dev only. Idea only; both repos are not needed.

**Document orientation (receipts, IDs, scans).** PP-LCNet and Seeing Straight (row 2, 9). Breaks: text is not the page,
labels are 5 to 20 px, two letters long. A 4-class result of 96.81% (English) and 92.68% (Indic) is the paper's own, and
my arithmetic from its failure counts does not reproduce them (about 95.3% for the Indic set; verified, arXiv 2511.04161v2,
v2 Mar 2026). The model, data and code are unreleased.

**Synthetic page composition for layout detectors (document layout field).** DocLayout-YOLO 2026 (arXiv 2610.28171, 20 Oct
2026, verified through three of four chunks of the html): MeshLayout-1M builds a page by repeatedly placing the crop
that best fills the largest empty grid cell ("Mesh-candidate BestFit": 500 candidates per page, canvas 1200-2000 px wide,
aspect 0.7-1.5, boxes shrunk 0.8-0.95 about their centre, up to 35 elements). Pretraining on 1M such pages, then
fine-tuning, moved mAP50:95 from 94.0 to 95.8 on HJDataset and from 67.0 to 71.8 on PRIMA-LAD at X scale (Table 4, X scale; the tick columns do not survive text extraction, but the single-tick rows reproduce the paper's own five-size averages, +4.7 on PRIMA-LAD for pretraining alone and +2.2 for the attention change alone, so the assignment is **verified** by arithmetic); removing the mesh cost 3.1 on PRIMA-LAD at S scale. Input 1600 px, 8 x H200, 500
epochs: far beyond our hours, and the code repo is AGPL-3.0 (gh api, DocLayout-YOLO), so the idea transfers, the code does not.
For plans the same idea is simpler: we paste whole plans, not many small elements, so a grid with random gutters is
enough. Earlier version of the same synthetic trick: WeLayout (arXiv 2305.06553, 2023, search result only, not opened).
Breaks: the pool is DocBank text-page crops, no drawings. A related 2026 result on synthetic object compositions
(arXiv 2510.09110, v4 Jan 2026) reports +6.59 AP on 1% of COCO when augmenting with synthetic object segments (abstract of the full PDF, read 2026-11-14); no code or dataset
link in the text I read. That is a data-scope result (L8), cited here in one line only.

**Map sheets (map body, legend, inset).** DIGMAPPER (arXiv 2506.16006, Jun 2025, html read in full except the reference tail,
**verified**): a fine-tuned LayoutLMv3 splits a geologic map into "content and legend areas" only (insets are not a
class), scored on 40 hand-annotated maps at IoU 0.5 threshold: IoU 0.84 / F1 0.87 on maps rated excellent, 0.82 / 0.85
good, 0.80 / 0.84 fair; training data size not stated. Failures stated: non-rectangular legends, scan noise and unusual
layouts ("often fails to segment complete regions"). The checkpoint family is not usable for us: the LayoutLMv3 base card
reads `license: cc-by-nc-sa-4.0` (read; code microsoft/unilm is MIT by gh api), so non-commercial weights, local only, never
shipped (record 0003). Transfer value: confirms "separate the main drawing area from side material first, then process each
region", which the AEC benchmark above measures with better numbers on drawings. One more search-only mention: map legend
detection with GPT-4o (arXiv 2510.08385), not opened. Newspaper and page segmentation (XY-cut, whitespace covers,
Docstrum) came from search snippets only, not opened and not ranked; XY-cut is the textbook method for several
rectangles separated by whitespace and underlies row 1b, whose measured version is Taschwer and Marques.

**Floor-plan parsing that gates its own edits (SALI-FP, arXiv 2609.25615, Sep 2026, Tsinghua).** Whole PDF text (140k characters, 82 pages) read in
full and searched for sheets, multi-plan input and orientation (**verified**): it evaluates on the 400 CubiCasa5K test plans with the official four-rotation baseline, works at 1024 x 1024,
says nothing on multi-plan sheets, and its only rotation handling is CubiCasa5K's official four-rotation test plus a 5-degree augmentation limit, and its production pipeline calls proprietary image and language model APIs, so it is
neither usable nor in my angle; the gating idea belongs to L10 (other orchestrator).

**Chart and multi-view VLM benchmarks.** CrossProjection (arXiv 2608.00473, Aug 2026) tests plan/section/elevation
matching by vision-language models (GPT-5.5 82.4% overall); belongs to L7 and is not dug into here.

### Page segmentation, six classic algorithms (Shafait, Keysers, Breuel, DAS 2006; opened as full PDF 2026-11-14)

Text-line detection on the UW-III scanned document set (not drawings). Read in the full text: X-Y cut "fails in the presence of noise
and tends to take the whole page as one segment", which gives merge errors on two-column pages; it is also the fastest of the six.
What breaks on our images: the separator-band baseline of row 1b is the same family as X-Y cut, so a scan border, a stamp or a
noise strip crossing the gap between two plans will merge them into one region. That supports training the detector (row 1) and
keeping the band recursion only as the cheap first baseline, with a border-crop step before it. No licence question: no code is used.

### RF-DETR repo issues read for memory, speed and resolution (gh api, 2026-11-14)

Repo pushed 2026-11-13, 75 open issues. #1460 (closed 2026-09-14): the segmentation Large model hit CUDA OOM during validation mask matching on a V100 16 GB
while training fit; we train a box detector, so this does not apply, but it is the 16 GB ceiling to watch if we ever move to masks. #974 (open): a user
reported training about twice as slow after upgrading from 1.5.0 to 1.6.4 on 18,000 images at 512 px; a maintainer pointed at the effective batch size of
16 the docs recommend, so pin the version and set the batch size and gradient accumulation to an effective 16. #1344 (open feature request): images are
decoded every epoch, no RAM cache; a maintainer estimated about 60 GB of RAM for 50k decoded 640 px images, so keep sheets on a fast disk. #1052 and #497
(open): no official rectangular input yet (#1052 last updated 2026-06-25: a maintainer says squash is "probably fine" unless images are pathologically rectangular; a user with 10:1 crops disagrees; latest release 1.12.1 of 2026-11-12), which matches the squash note in row 1. Not read: the 70 other open issues.

### Multi-photo flatbed scan splitting (adjacent field, licences read via gh api 2026-11-14)

The tools that crop several photos from one scan (ScanSplitter, autocrop, cropMultipleScannedImages) are all GPL-3.0, so out for shipped code, and
they were found by search only (READMEs and code not read, no accuracy figures exist in the results). The method class is background subtraction
or edge detection on a blank scanner bed. What breaks on our images: a plan sheet has no uniform bed colour and plans share a white page with
labels, title blocks and dimension lines between them, so a background-difference crop would return the whole sheet or the drawing frame. This field
adds nothing beyond the separator-band baseline (row 1b); recorded so nobody re-searches it.

### Dependency licences of the top candidates (pyproject files and PyPI metadata read 2026-11-14)

RF-DETR core dependencies (torch, torchvision, supervision, pydantic, requests, numpy, tqdm) and its train extra (peft Apache, pytorch-lightning Apache-2.0,
torchmetrics Apache-2.0, hotcoco MIT) show no AGPL or GPL entry; the PyPI package `rfdetr` declares Apache-2.0. PaddleOCR's requirements list (shapely,
scikit-image, pyclipper, lmdb, opencv, albumentations) has no Ultralytics; albumentations 2.0.8 is MIT on PyPI and in its repo. dedoc is Apache-2.0.
faster-coco-eval is Apache-2.0 (gh api). Not read: transitive dependencies of the Paddle runtime.

### Title-block and main-content detection on building drawings (arXiv 2504.08645, ECCC 2025; full PDF read 2026-11-14)

Faster R-CNN with a MobileNetV3 backbone (20 epochs, SGD, learning rate 0.001) on raster building drawings, hand-drawn and CAD, boxes for title block, main
content, notes and legend. Table 1: title block accuracy 0.971 (precision 0.84, recall 0.96), main content accuracy 0.943 (F1 0.84), notes 0.82 (precision
0.40), legend 0.86; a prediction counts at IoU 0.70, and only the single most confident title block per drawing is kept, on the assumption that a drawing has one
title block. The dataset is not public (the text says so) and I found no code. What it gives us: an architecture-sheet number for "find the main content
region" with a small detector, but one region per drawing, so it never meets the case of several plans per sheet; the authors list non-90-degree rotation as
future work. What breaks: the keep-one-box rule is exactly wrong for plan counting (it would drop all but one plan); use the box-per-plan output of row 1.

### Other compound-figure separation repos (gh search and READMEs, 2026-11-14)

`apple2373/figure-separator` (TensorFlow 1.0 CNN, no licence file: not reusable), `GaetanLepage/compound-figure-separator` (GPL-3.0: out), and a 2026 TU Wien course project
`AlbertZweistein-2/11818774_CompoundFigureSeparation` (MIT, YOLO fine-tuning on scientific figures, so Ultralytics AGPL in practice; README read, results not checked). None changes the ranking.

## 4. Looked for and did not find

- Any floor-plan *paper* that counts plans on a sheet or splits a multi-plan raster (a patent describes a floor-plan box detector with NMS but not a plan count, see section 3; second search with different terms found nothing new). CubiCasa5K's own curation notes (search
  aggregator, not the paper) say it kept single-floor images; the 2024 multi-unit paper (arXiv 2408.01526, verified)
  separates nothing and lists multi-floor input as future work.
  Third attempt (2026-11-14, arXiv API title and abstract searches with floor plan, sheet, multi-floor, multi-story, orientation): no hit that splits a sheet. The closest, 2608.24886 (VLM graphs of 147 library floor plans, abstract read), takes one plan per image.
- A 4-class page-orientation accuracy on drawings, blank pages or sparse pages: none. The Seeing Straight failure analysis
  is the nearest ("text not the majority of the page").
- Resolved late: the Open-PMC-18M subfigure detector is not in the GitHub README but is on Hugging Face as `vector-institute/pmc-18m-dab-detr`: card `license: apache-2.0`, 43.75M parameters, usage through transformers (card and file list read via curl on 2026-11-14). Biomedical figures only: a warm start for a plan-box fine-tune, not a zero-shot plan counter.
- A tile-size or input-size ablation for small drawing symbols (P&ID card for RF-DETR claims SAHI helps, no ablation;
  search result only, not counted).
  Second attempt (2026-11-14, different terms): the nearest full text I opened is the IJDAR 2024 construction-drawing symbol paper (Springer s10032-024-00492-9, 14 pages): sheets of 14,042 x 9,934 px, fixed 640 x 640 patches, edge patches overlapping, mAP 79% for YOLOv7 and 83% for Faster R-CNN, YOLOv7 weaker on small symbols. One tile size only, so still no ablation; pointer to the detection scope (no digging here). Also not an ablation: patents and a Roboflow P&ID tutorial (search results only).
- Evidence on generative vs bicubic upscaling for detection of line drawings. A 2025 Thai conference paper and a blog
  surfaced in search results (GAN-based upscaling beating bicubic on aerial-style data); neither was opened.
  Second attempt (2026-11-14): a search with different terms returned only natural-image and pose-estimation studies; the Thai conference PDF is blocked by the host (404 on direct fetch, "Web Page Blocked" through the fetch helper), so it stays unopened. A search summary says Real-ESRGAN can score below bicubic on PSNR while looking sharper, which is a reason to judge by detector error, not by image metrics; not counted as read.
  Found by reading the sibling report lit-sheet-b and then opening the paper myself: Yang et al., arXiv 2312.13620 (full PDF, 2026-11-14), power single-line diagrams, symbol recall on low-quality drawings 32.74 (interpolation), 85.19 (SRGAN), 88.93 (ESRGAN), 98.89 (ESRGAN trained on synthetic degradations), 99.33 (full system, precision 98.87); all verified in the paper's tables. One correction to that sibling: the abstract does link code and data (a GitHub repository, pushed 2024-02-27, files include a modified ESRGAN and a modified Faster R-CNN), but the repository has no licence file (gh api returns none), so by default nobody may reuse it; treat as read-only reference. Domain match to our plans is weak (large symbols, same degradation model for train and test).
- Second attempt at plan-splitting literature with different terms (levels basement, ground, first floor on one sheet; 2026-11-14): the nearest full text I opened is a 2018 University of Victoria master's thesis on multi-unit floor plans (98 pages, curl then pypdf). Its "multi-unit" means many apartments inside one large plan (a 9,427 x 5,445 px example), handled by whole-image wall extraction and connected components; it does not split a sheet into separate plans. Other hits (2408.01526 multi-unit, a 2014 IJDAR paper) were already read or are the same family. Still no paper that counts plans per sheet.
- Hugging Face search for ready floor-plan checkpoints (curl of the model API and raw cards, 2026-11-14): none counts or splits plans on a sheet. Cards read: `Voix7/rtdetrv2-floorplan-v2` (Apache-2.0, RT-DETRv2 r50, mAP 0.666 / mAP50 0.758, "unknown dataset": leak status unknown, treat as leaky), `joshlyman/rtdetrv2-floorplancad-doors` (Apache-2.0, r18, "unknown dataset", name suggests FloorPlanCAD), `Yytsi/floorplan-to-3d-walls` (MIT, trained on CubiCasa5K: leaky), `Hyunwoo1605/mask2former-floorplan-instance-segmentation` (no licence, no dataset: unusable). Nothing here changes the ranking.
- Forward walk, Semantic Scholar via the fetch helper (2026-11-14): RT-DocLayout 2606.23344 has 3 citing papers (an OCR survey, Xiaomi-OCR-0, LayoutLite), all document OCR, none on sheet layout; titles only, not opened. OpenAlex hit its free daily limit the same day, so the other forward walks stay open; the walk from Taschwer and Marques (1606.01021) was refused twice with 429 and is not done.
- Forward walk, OpenAlex (works when Semantic Scholar rate-limits): 2510.21862 has 7 citing works (2026: drawing-annotation to CAD mapping, BlueprintAgent EMNLP findings, drawing retrieval); none about sheet layout or plan counting. 2504.03241: 0 citing works. Semantic Scholar rate limits: forward walk from the Zernike paper (2504.03241) failed twice with 429.
- Music-score staff-region detection with Monte Carlo dropout (IJDAR 2025, Springer s10032-025-00541-x): the fetch was redirected to a login page; abstract and numbers unread (paywall). It is the OMR analogue of a plan-region detector with uncertainty, so it would be worth a human read.
- A drawing-specific 4-way orientation classifier with numbers: only the 2017 ICDAR abstract (no method, no figures, document unavailable).
  Second attempt (2026-11-14, different terms): the nearest is a 2021 four-page arXiv paper on mould drawings (2110.11593, full PDF read): ResNet-50 predicts the 0/90/180/270 rotation of detected *parts* (not sheets), 94.4% injection and 92.0% press parts, trained on cropped parts from 92 of 192 drawings, symmetric parts excluded. It shows a CNN can read rotation on CAD drawings but says nothing about whole-sheet or plan orientation, so the gap stays open.
- Waifu2x or other line-art upscalers vs bicubic for detection or OCR on drawings: second search found only a 2021 medieval-text OCR study (Czech workshop, search snippet, not opened) and vendor pages; no measurement on line drawings.

## 5. Open questions, and missing tools

Questions for the orchestrator or the owners of other scopes:
1. Does a per-plan box exist or can it be produced for the 784 real multi-plan dev images? It decides whether row 1 trains
   on real data at all. (Record 0003 says it is not exported yet.)
2. (For L5) A sourced list of Finnish storey titles (for example the printed floor name over each plan) would give a
   second plan count from OCR alone; none was found in my scope.
3. Is page rotation needed at all for the symbol detector, if training uses rot90 and flips? Then orientation matters only
   for the label OCR pass (L5). One line for L5: the 4-rotation OCR vote is the structure-free fallback.
4. (For L2)  RF-DETR resolutions are 384 to 704 and the cookbook range is 384 to 640; symbols of 5 to 20 px on 855 px
   images need tiling or a larger input, which is their question, not mine.
5. For L10 (confidence, other orchestrator): the quality-gate row 3 is the only piece of the gate that is in my scope.

Missing or limited tools: no arXiv MCP (used html pages); the fetch agent could not extract PDFs but saves them, so I extracted
text with pypdf in a scratch folder (AEC benchmark, SNIP, Taschwer, Open-PMC, FigEx2 read that way); web-fetch summaries sometimes replaced the tail of a page
(flagged where used); Semantic Scholar rate-limits curl, so I used the headless browser for four calls and got two 429.
Nothing was run on our images, so every accuracy claim for our data is absent.

## 6. Sources read (for the 15-source and 6-from-2025-26 targets)

2025-2026 read: 2610.28171; 2510.09110; 2506.02738; 2601.08026; 2510.21862; 2607.18997; 2509.11720; 2601.21957; 2504.03241;
2511.13523; 2606.29667; 2602.16430; 2511.04161v2; 2608.00473; RF-DETR docs and release page; PP-DocLayoutV3 card.
Other: PaddleOCR doc-orientation page, model card and ONNX card; docTR docs; kreuzberg source; 1803.07728 and RotNet
README; NFIQ2 and OFIQ READMEs and LICENSE files; RF-DETR cookbook; 2408.01526; GreenMap and comic-panel model cards;
Semantic Scholar citation lists for 2506.02738, 2511.04161, 2601.08026; Taschwer and Marques 1606.01021; SNIP 1711.08189;
Open-PMC detector card; DIGMAPPER 2506.16006; dedoc benchmark and training script; Genius Scan blog; Tesseract docs; 2101.09903;
Autodesk patent US12243342 (full page, claims included); ICDAR 2017 orientation abstract; Open-PMC and FigEx2 full PDFs. Not opened: paywalled IJDAR
MC-dropout paper, map legend 2510.08385, WeLayout, XY-cut surveys.

Added in the final rounds (all opened 2026-11-14): 2504.03241 full PDF, 2510.09110 and 2510.21862 full PDFs, 2609.25615 full PDF, 2504.08645 full PDF, 2110.11593, 2312.13620, DAS 2006 page-segmentation PDF, IJDAR 2024 symbol paper, UVic 2018 thesis, US12243342B2 full page (claims and description), 2512.02566 and 2608.24886 (abstract), Hugging Face cards for four floor-plan checkpoints, RF-DETR issues #974 #1052 #1344 #1460, Tesseract osdetect.cpp, pyproject and PyPI licence metadata. Unverified or not done: Taschwer forward citation walk (rate limited), the Thai super-resolution conference paper (host blocked), the RF-DETR aspect-ratio comment in row 1 (a forum comment, flagged reported). Note for the orchestrator: sibling lit-sheet-b says 2312.13620 links no code; the paper's abstract links a GitHub repository without a licence file.
