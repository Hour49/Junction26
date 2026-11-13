# Ideas and experiments for the pipeline: the merged list

Bogdan, 2026-11-14: "MERGE BOTH OF OUR RESEARCH, AND THEN LOOK AT EVERYTHING IN DETAIL AND REMOVE DUPLICATES AND MAKE
A BIG LIST OF IDEAS AND EXPERIEMNTS FOR THE PIPELINE TO BE TESTED IN THE FUTURE".

This is that list: 511 ideas, experiments and negative results from the 36 reports of the literature campaign
(12 scopes, both halves), grouped by pipeline stage. The short ranked version is [SHORTLIST.md](SHORTLIST.md).

## How it was made

1. One worker per scope read the scope's three reports from the first line to the last (checked in the session
   logs for 11 of the 12 scopes; the market scope was not checked) and wrote every idea as one record: what to do, the
   evidence and where it is, licence, CubiCasa5K leakage, cost, the experiment that would settle it, what breaks on
   our images, and a verdict. That gave 706 records.
2. The orchestrator merged records about the same thing across scopes: 210 records were assigned by hand to 96
   groups, and 103 groups hold more than one record. Where scopes disagreed between "do not try" and another
   verdict (18 groups), the orchestrator decided; eight of those entries carry a reviewer's note.
3. Within a stage, entries are ordered by group, then by how strong the evidence is: measured on floor plans,
   measured in another field, the authors' own claim, our own idea, seen in a search result only.

## How to read it

- **Group**: "Try first" (103), "Try next" (93), "Later" (143), "Idea or pitch only"
  (77), "Do not try" (95: negative results, licence and leakage traps, kept so nobody retries them).
  "Try first" is what the scopes thought worth a first test, not a plan: the plan is the shortlist.
- **Evidence** says what kind of proof the entry has, not how good the idea is. Nothing here was run on our images.
- Each number links to the full entry in `ideas/<stage>.md`. "Also" lines under an entry are the other scopes'
  versions of the same idea, kept because they often carry a different number or experiment.
- Costs are estimates by the workers. Hardware assumed: one 12 GB and one 16 GB GPU, plus 200 EUR of Verda GPU
  credits (Bogdan, 2026-11-14).
- "Reports" under an entry names the angle reports it came from. Tudor's are in `reports/` (PR #56). Bogdan's 18
  angle reports stay local, because some quote dataset file names; his six merged scope reports are in `reports/`.
- The list is generated (`ideas_merge.py` in the team's local tooling) from the scope records; edit the records or
  the alias table, not these files.

## Normalising the sheet (orientation, deskew, quality) (40)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [1](ideas/normalise.md#i1) | rot90 training augmentation and four-rotation test voting | Try first | floor-plans | count, detect, floorplan, rooms |
| [2](ideas/normalise.md#i2) | Super-resolution or Lanczos upscaling before detection | Try first | floor-plans | count, floorplan, sheet |
| [3](ideas/normalise.md#i3) | Rotation augmentation and per-sheet orientation estimate | Try first | floor-plans | rooms |
| [4](ideas/normalise.md#i4) | Augraphy for pixel-level scan effects only; do rotation and scaling ourselves | Try first | adjacent-field | data, rooms, vector |
| [5](ideas/normalise.md#i5) | Keep native resolution for the wall net | Try first | adjacent-field | rooms |
| [6](ideas/normalise.md#i6) | Orientation by reading labels at four rotations and counting vocabulary hits | Try first | adjacent-field | ocr, sheet |
| [7](ideas/normalise.md#i7) | Raise single-pass input resolution before slicing | Try first | adjacent-field | data, detect, floorplan |
| [8](ideas/normalise.md#i8) | Log and bypass the OCR page-size cap before comparing engines on PDF renders | Try first | adjacent-field | ocr |
| [9](ideas/normalise.md#i9) | Same tile geometry in training and inference | Try first | adjacent-field | data, detect |
| [10](ideas/normalise.md#i10) | Tile high-resolution sheets before detection | Try next | floor-plans | ocr |
| [11](ideas/normalise.md#i11) | Four-way orientation classifier before everything | Try next | adjacent-field | floorplan, ocr, sheet, vlm |
| [12](ideas/normalise.md#i12) | No-reference image quality and resolution as a confidence input | Try next | adjacent-field | sheet, trust |
| [13](ideas/normalise.md#i13) | Rescale each plan crop to a fixed measured scale before the symbol detector | Try next | adjacent-field | sheet |
| [14](ideas/normalise.md#i14) | Rotate only when two independent voters agree, else abstain and flag | Try next | adjacent-field | sheet |
| [15](ideas/normalise.md#i15) | Pad non-square plans to a square with a fixed rule, do not stretch | Try next | authors-claim | detect |
| [16](ideas/normalise.md#i16) | Trained 'is this a floor plan' gate with shifted positives | Later | floor-plans | trust |
| [17](ideas/normalise.md#i17) | Use OCR boxes to erase text and dimension lines before wall extraction | Later | floor-plans | ocr |
| [18](ideas/normalise.md#i18) | Tile or upscale plans for any line detector | Later | floor-plans | vector |
| [19](ideas/normalise.md#i19) | Scale-adaptive thresholds in any rule stage | Later | adjacent-field | vector |
| [20](ideas/normalise.md#i20) | Rectify phone photos before parsing | Later | adjacent-field | rooms |
| [21](ideas/normalise.md#i21) | Normalise scans and photos to a clean look | Later | adjacent-field | vlm |
| [22](ideas/normalise.md#i22) | Normalise strokes to a fixed width before the detector | Later | adjacent-field | data |
| [23](ideas/normalise.md#i23) | Own 4-way rotation head trained on dev plans with OCR-derived labels | Later | adjacent-field | sheet |
| [24](ideas/normalise.md#i24) | Vector PDF plans: use text layer and exact geometry | Later | adjacent-field | rooms, scale, sheet |
| [25](ideas/normalise.md#i25) | Rescale each sheet by a structural unit (wall thickness) before detection | Later | adjacent-field | vector |
| [26](ideas/normalise.md#i26) | Reuse the paper's tile planner for any high-resolution pass | Later | adjacent-field | count |
| [27](ideas/normalise.md#i27) | Detector-jointly-trained restorer for badly degraded drawings (offline A/B) | Later | adjacent-field | sheet |
| [28](ideas/normalise.md#i28) | Wall-orientation deskew for small angles plus a 4-class head for the 90-degree step | Later | adjacent-field | sheet |
| [29](ideas/normalise.md#i29) | Learned cleaning step before detection for scans | Idea or pitch only | floor-plans | vector |
| [30](ideas/normalise.md#i30) | Per-sheet batch-norm statistics adaptation | Idea or pitch only | adjacent-field | data |
| [31](ideas/normalise.md#i31) | Cut legend and title-block regions off before counting | Idea or pitch only | adjacent-field | sheet |
| [32](ideas/normalise.md#i32) | Read geometry when a vector layer exists | Idea or pitch only | authors-claim | market |
| [33](ideas/normalise.md#i33) | Title block position as an orientation cue | Idea or pitch only | search-only | sheet |
| [34](ideas/normalise.md#i34) | Learned super-resolution (EDSR/ESRGAN/SwinIR) before counting | Do not try (with the reason) | floor-plans | count, sheet |
| [35](ideas/normalise.md#i35) | Rule-based tools fail on degraded or rotated scans where learned models hold (chemistry) | Do not try (with the reason) | adjacent-field | vector |
| [36](ideas/normalise.md#i36) | Tesseract OSD as an orientation detector | Do not try (with the reason) | adjacent-field | sheet |
| [37](ideas/normalise.md#i37) | VLM zero-shot page orientation | Do not try (with the reason) | adjacent-field | sheet |
| [38](ideas/normalise.md#i38) | Heavy 12-class document rotation models | Do not try (with the reason) | authors-claim | sheet |
| [39](ideas/normalise.md#i39) | Scans fail on scale and counts for every tool tested | Do not try (with the reason) | authors-claim | market |
| [40](ideas/normalise.md#i40) | Structure-only orientation for text-sparse plans | Do not try (with the reason) | search-only | sheet |

## Plans per sheet (splitting a sheet into plans) (17)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [41](ideas/plans.md#i41) | Split sheets into plans before room extraction | Try next | floor-plans | floorplan, rooms, sheet |
| [42](ideas/plans.md#i42) | Paste single-plan sheets into synthetic multi-plan sheets for box training | Try next | adjacent-field | data, sheet |
| [43](ideas/plans.md#i43) | Squash wide sheets to square for RF-DETR, or tile | Try next | adjacent-field | sheet |
| [44](ideas/plans.md#i44) | Count plans by grouping detected elements by distance | Try next | our-idea | sheet |
| [45](ideas/plans.md#i45) | Add sheets with no plan as negatives | Later | adjacent-field | sheet |
| [46](ideas/plans.md#i46) | Faster R-CNN as a plan-region detector with higher recall | Later | adjacent-field | sheet |
| [47](ideas/plans.md#i47) | Overlapping crops or search-then-reread for large sheets | Later | adjacent-field | market |
| [48](ideas/plans.md#i48) | Warm start a plan detector from the Open-PMC subfigure DAB-DETR | Later | adjacent-field | sheet |
| [49](ideas/plans.md#i49) | Classical separator-band recursion as the first plan splitter | Later | adjacent-field | sheet |
| [50](ideas/plans.md#i50) | Group detected boxes into plans with a learned edge classifier | Later | adjacent-field | sheet |
| [51](ideas/plans.md#i51) | Wall-graph readout from junction and centreline heatmaps for plans per sheet | Idea or pitch only | floor-plans | vector |
| [52](ideas/plans.md#i52) | One detector per sheet type | Idea or pitch only | authors-claim | count, detect |
| [53](ideas/plans.md#i53) | Industry box detector with NMS for floor plan regions (patent) | Idea or pitch only | search-only | sheet |
| [54](ideas/plans.md#i54) | Start the plan detector from a document-layout checkpoint | Do not try (with the reason) | adjacent-field | data, sheet |
| [55](ideas/plans.md#i55) | Train the plan detector on composites only | Do not try (with the reason) | adjacent-field | sheet |
| [56](ideas/plans.md#i56) | VLM layout grounding for plan boxes | Do not try (with the reason) | adjacent-field | sheet |
| [57](ideas/plans.md#i57) | Flatbed multi-photo cropping tools | Do not try (with the reason) | search-only | sheet |

## Symbols: windows, doors, fixtures (93)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [58](ideas/elements.md#i58) | Tile at 1.5 tokens per symbol, overlap by one object, never zoom out | Try first | floor-plans | vlm |
| [59](ideas/elements.md#i59) | Pin the detector release and check the log that pretrained weights loaded | Try first | adjacent-field | data, detect, sheet |
| [60](ideas/elements.md#i60) | Window strips: one box per drawn cell, no NMS inside a tile | Try first | adjacent-field | count, detect |
| [61](ideas/elements.md#i61) | D-FINE S/M fine-tuned at 960-1280 px from the COCO-only checkpoint | Try first | adjacent-field | data, detect |
| [62](ideas/elements.md#i62) | Detect symbols with the wall lines left in (do not erase lines first) | Try first | adjacent-field | vector |
| [63](ideas/elements.md#i63) | Look-alikes as explicit classes | Try first | adjacent-field | count |
| [64](ideas/elements.md#i64) | Ordered output with an explicit end and empty-class tiles | Try first | adjacent-field | vlm |
| [65](ideas/elements.md#i65) | Florence-2 LoRA or full fine-tune as tile symbol detector | Try first | adjacent-field | vlm |
| [66](ideas/elements.md#i66) | Evaluate a trained checkpoint at 1.5-2.5x its training pixels, no retraining | Try first | adjacent-field | detect |
| [67](ideas/elements.md#i67) | Small VLM writes points in reading order, code counts them | Try first | adjacent-field | count, vlm |
| [68](ideas/elements.md#i68) | RF-DETR S/M fine-tuned on dev boxes at about 1024 px, rot90 and flips as augmentation | Try first | adjacent-field | data, detect, floorplan |
| [69](ideas/elements.md#i69) | Exact rot90 and flip augmentation on the dev boxes | Try first | adjacent-field | data, detect, sheet, vlm |
| [70](ideas/elements.md#i70) | Give each symbol about 1.5 visual tokens: upsample, overlap, never zoom out | Try first | adjacent-field | market |
| [71](ideas/elements.md#i71) | Zero-shot dense probe with Falcon Perception 0.6B | Try first | authors-claim | vlm |
| [72](ideas/elements.md#i72) | RF-DETR Medium at 640-704 next to Small at 1024 | Try first | authors-claim | detect |
| [73](ideas/elements.md#i73) | Train the vision tower, not only the language LoRA | Try first | authors-claim | vlm |
| [74](ideas/elements.md#i74) | Train door and door-without-leaf as separate classes | Try first | our-idea | detect |
| [75](ideas/elements.md#i75) | Read the 2019 model's opening heatmaps instead of polygons | Try next | floor-plans | floorplan |
| [76](ideas/elements.md#i76) | Depiction jitter: line-weight, blur, down-up scaling and JPEG on training images | Try next | floor-plans | data |
| [77](ideas/elements.md#i77) | Negative (empty) patches in tile training | Try next | floor-plans | data, detect |
| [78](ideas/elements.md#i78) | RandomShift: translate training content up to the patch stride | Try next | floor-plans | detect |
| [79](ideas/elements.md#i79) | DEIM matching schedule on D-FINE as a convergence helper | Try next | adjacent-field | detect |
| [80](ideas/elements.md#i80) | Keep mosaic low or off for 5-20 px symbols | Try next | adjacent-field | detect |
| [81](ideas/elements.md#i81) | Two models: plan finder at low resolution, symbol detector on native crops | Try next | adjacent-field | sheet |
| [82](ideas/elements.md#i82) | Tiled inference with a count-safe merge rule | Try next | adjacent-field | count, detect, floorplan, market, vector |
| [83](ideas/elements.md#i83) | BlueprintParse-R50 for toilet, sink, bathtub, gas range | Try next | authors-claim | floorplan |
| [84](ideas/elements.md#i84) | RF-DETR multi_scale and expanded_scales off | Try next | authors-claim | detect |
| [85](ideas/elements.md#i85) | Door-only RF-DETR-S checkpoint with tiled inference | Try next | search-only | floorplan |
| [86](ideas/elements.md#i86) | Give open models candidate boxes, not free coordinates | Later | floor-plans | vlm |
| [87](ideas/elements.md#i87) | Separate small door/window head after locating the opening | Later | floor-plans | vector |
| [88](ideas/elements.md#i88) | A tiny head for door versus window | Later | floor-plans | market |
| [89](ideas/elements.md#i89) | OpenCV LSD / FastLineDetector as a cheap structural channel | Later | floor-plans | vector |
| [90](ideas/elements.md#i90) | Whole sheet plus four overlapping crops in one call | Later | floor-plans | vlm |
| [91](ideas/elements.md#i91) | SweepLSD (MIT, one-pass streaming detector) as a cleaner segment soup | Later | floor-plans | vector |
| [92](ideas/elements.md#i92) | GRPO with exact-count reward on an SFT checkpoint | Later | adjacent-field | vlm |
| [93](ideas/elements.md#i93) | Deep Sketch Vectorization: line-art centrelines with multi-way junctions | Later | adjacent-field | vector |
| [94](ideas/elements.md#i94) | Dome-DETR density-driven queries and a stride-4 level on D-FINE | Later | adjacent-field | detect |
| [95](ideas/elements.md#i95) | EdgeDrawing / ELSED as permissive classical line sources | Later | adjacent-field | vector |
| [96](ideas/elements.md#i96) | Fourier-domain mixing, 90-degree rotation and an auxiliary mask head | Later | adjacent-field | market |
| [97](ideas/elements.md#i97) | Fine-tune HAWPv3 or LINEA on our wall lines | Later | adjacent-field | vector |
| [98](ideas/elements.md#i98) | Plain-word field and class names in the JSON target | Later | adjacent-field | vlm |
| [99](ideas/elements.md#i99) | RF-DETR query count and tile object cap | Later | adjacent-field | data, sheet |
| [100](ideas/elements.md#i100) | RT-DETRv2 as a fallback detector | Later | adjacent-field | detect |
| [101](ideas/elements.md#i101) | SAM 3 open-vocabulary counting | Later | adjacent-field | vlm |
| [102](ideas/elements.md#i102) | Stride-4 (P2) feature level for tiny symbols | Later | adjacent-field | detect |
| [103](ideas/elements.md#i103) | Tiling recipe: 50% overlap, border-weighted confidence, containment merge | Later | adjacent-field | sheet |
| [104](ideas/elements.md#i104) | Stroke and blur curriculum fine-tune | Later | authors-claim | floorplan |
| [105](ideas/elements.md#i105) | Keep a box only in the tile that contains its centre | Later | our-idea | detect |
| [106](ideas/elements.md#i106) | Multi-zoom inference merged | Later | search-only | floorplan |
| [107](ideas/elements.md#i107) | Find bathrooms then detect fixtures on tiles | Later | search-only | floorplan |
| [108](ideas/elements.md#i108) | Pixel segmentation plus post-processing held up on scans | Idea or pitch only | floor-plans | vector |
| [109](ideas/elements.md#i109) | RT-DETR-L floor-plan recipe at 1024 px | Idea or pitch only | floor-plans | floorplan |
| [110](ideas/elements.md#i110) | Second-stage reclassifier on detected crops with domain adaptation | Idea or pitch only | adjacent-field | data |
| [111](ideas/elements.md#i111) | Sub-pixel keypoint heatmaps for rectangular CAD symbols | Idea or pitch only | adjacent-field | vector |
| [112](ideas/elements.md#i112) | Self-supervised pretraining on unlabelled drawings | Idea or pitch only | adjacent-field | data |
| [113](ideas/elements.md#i113) | Assign unused queries to unmatched targets | Idea or pitch only | adjacent-field | count |
| [114](ideas/elements.md#i114) | MolScribe recipe: image to graph with coordinates, synthetic renders plus rotation and noise | Idea or pitch only | adjacent-field | vector |
| [115](ideas/elements.md#i115) | Cut the image along lines that avoid objects | Idea or pitch only | adjacent-field | market |
| [116](ideas/elements.md#i116) | Point-map head with hard-negative patches | Idea or pitch only | adjacent-field | count |
| [117](ideas/elements.md#i117) | Fine-tune SAM 3 with a frozen backbone or LoRA | Idea or pitch only | adjacent-field | count |
| [118](ideas/elements.md#i118) | SFT then RL with a checkable count reward on a small VLM | Idea or pitch only | adjacent-field | market |
| [119](ideas/elements.md#i119) | Primitive DETR trained on synthetic lines, circles and arcs | Idea or pitch only | adjacent-field | vector |
| [120](ideas/elements.md#i120) | Training-free counterfactual scaling of frozen detectors (CQTR) | Idea or pitch only | adjacent-field | detect |
| [121](ideas/elements.md#i121) | Use our counting rules as the verifier for rejection sampling | Idea or pitch only | adjacent-field | market |
| [122](ideas/elements.md#i122) | Zoom family: AdaGround, DeepEyes, Mini-o3 | Idea or pitch only | adjacent-field | vlm |
| [123](ideas/elements.md#i123) | Count by tile only where candidates exist | Idea or pitch only | authors-claim | vlm |
| [124](ideas/elements.md#i124) | Community floor-plan detector checkpoints | Do not try (with the reason) | floor-plans | detect, ocr, scale |
| [125](ideas/elements.md#i125) | Deep Vectorization of Technical Drawings (cleaning network plus patch transformer) | Do not try (with the reason) | floor-plans | vector |
| [126](ideas/elements.md#i126) | Fine-tuned small VLM emitting JSON | Do not try (with the reason) | floor-plans | floorplan, vlm |
| [127](ideas/elements.md#i127) | Skip FloorplanVLM, SALI-FP, Raster2Seq weights, VecFormer weights for scored runs | Do not try (with the reason) | floor-plans | vector |
| [128](ideas/elements.md#i128) | A VLM-only plan parser loses on openings | Do not try (with the reason) | floor-plans | market |
| [129](ideas/elements.md#i129) | Wasserstein loss term gated to compact boxes | Do not try (with the reason) | floor-plans | detect |
| [130](ideas/elements.md#i130) | Co-DETR as accuracy ceiling | Do not try (with the reason) | floor-plans | detect |
| [131](ideas/elements.md#i131) | Split strokes by width (thick walls, thin symbols) inside a matcher | Do not try (with the reason) | floor-plans | vector |
| [132](ideas/elements.md#i132) | Class-agnostic symbol finder trained on synthetic shapes | Do not try (with the reason) | adjacent-field | detect |
| [133](ideas/elements.md#i133) | No deep line detector has a published result on floor plans, scans or line art | Do not try (with the reason) | adjacent-field | vector |
| [134](ideas/elements.md#i134) | Pretrained DeepLSD on scanned plans (one positive precedent) | Do not try (with the reason) | adjacent-field | vector |
| [135](ideas/elements.md#i135) | Negative: DINOv3 weights and DINOv3-based detectors | Do not try (with the reason) | adjacent-field | data, detect |
| [136](ideas/elements.md#i136) | Negative: domain-adversarial detector adaptation instead of augmentation | Do not try (with the reason) | adjacent-field | data |
| [137](ideas/elements.md#i137) | Door-swing arcs by Hough or circle fitting | Do not try (with the reason) | adjacent-field | vector |
| [138](ideas/elements.md#i138) | M-LSD / M-LSD-tiny as a CPU line detector | Do not try (with the reason) | adjacent-field | vector |
| [139](ideas/elements.md#i139) | RTMDet, YOLOX, mmrotate oriented detectors | Do not try (with the reason) | adjacent-field | detect |
| [140](ideas/elements.md#i140) | 11k QA fine-tune for small objects | Do not try (with the reason) | adjacent-field | vlm |
| [141](ideas/elements.md#i141) | ROI-gated sliced inference to save time | Do not try (with the reason) | adjacent-field | sheet |
| [142](ideas/elements.md#i142) | ScaleLSD as line evidence for door leaves and window cells | Do not try (with the reason) | adjacent-field | vector |
| [143](ideas/elements.md#i143) | ReDHF, BUTR, TinyFormer, SO-DETR and other 2026 tiny-object DETRs | Do not try (with the reason) | adjacent-field | detect |
| [144](ideas/elements.md#i144) | Negative: do not train the detector from random initialisation | Do not try (with the reason) | adjacent-field | data |
| [145](ideas/elements.md#i145) | YOLO family detectors | Do not try (with the reason) | adjacent-field | detect, sheet, vector |
| [146](ideas/elements.md#i146) | Vector symbol spotters (SymPoint, SymPoint-V2, CADSpotting, VecFormer, TempFit, DPSS) cannot take raster input | Do not try (with the reason) | adjacent-field | vector |
| [147](ideas/elements.md#i147) | Remove wall lines before detecting symbols | Do not try (with the reason) | adjacent-field | detect |
| [148](ideas/elements.md#i148) | DeepLSD and ScaleLSD install an AGPL line-segment library (pytlsd) | Do not try (with the reason) | authors-claim | vector |
| [149](ideas/elements.md#i149) | RF-DETR XL/2XL and Atto/Femto/Pico | Do not try (with the reason) | authors-claim | detect |
| [150](ideas/elements.md#i150) | Oriented-box detectors for rotated symbols | Do not try (with the reason) | search-only | floorplan |

## Counting (from marks to an exact number) (42)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [151](ideas/counting.md#i151) | Duplicate removal by intersection over the smaller box, tuned NMS even for DETRs | Try first | floor-plans | count, data, detect, trust |
| [152](ideas/counting.md#i152) | Read objects from a detection or heatmap output, not a sequence decoder | Try first | floor-plans | detect, floorplan, market, vector, vlm |
| [153](ideas/counting.md#i153) | Second counter: template matching with a symbol cut from the same plan | Try first | floor-plans | count, floorplan |
| [154](ideas/counting.md#i154) | Tune the score threshold per class for exact count, not AP or F1 | Try first | adjacent-field | count, data, detect |
| [155](ideas/counting.md#i155) | Global consistency step to remove duplicate openings | Try next | floor-plans | floorplan |
| [156](ideas/counting.md#i156) | Pick exemplars by feature consensus and diversity, not the top two scores | Try next | adjacent-field | count |
| [157](ideas/counting.md#i157) | CountGD++ as a stage-8 second counter | Try next | adjacent-field | count, floorplan |
| [158](ideas/counting.md#i158) | Divide the count by the instances inside the exemplar | Try next | adjacent-field | count |
| [159](ideas/counting.md#i159) | Exemplar with surroundings, not tight crop | Later | floor-plans | count |
| [160](ideas/counting.md#i160) | GeCo2 as a few-shot box counter | Later | floor-plans | count, floorplan, vlm |
| [161](ideas/counting.md#i161) | Per-class post-processing for segmentation counts | Later | floor-plans | floorplan |
| [162](ideas/counting.md#i162) | Centre-only fixed-size head (YOLSO) as an independent counter | Later | adjacent-field | detect |
| [163](ideas/counting.md#i163) | Box-level conformal guarantees as count guarantees | Later | adjacent-field | trust |
| [164](ideas/counting.md#i164) | Template matching in DINOv2 feature space | Later | adjacent-field | count |
| [165](ideas/counting.md#i165) | Probe hidden state for the count | Later | adjacent-field | vlm |
| [166](ideas/counting.md#i166) | Mean or median of several counters as a combiner | Later | adjacent-field | trust |
| [167](ideas/counting.md#i167) | Feed the counter's own top boxes back as exemplars for a second pass | Later | adjacent-field | count |
| [168](ideas/counting.md#i168) | Coverage-weighted fusion for tiles | Later | adjacent-field | floorplan |
| [169](ideas/counting.md#i169) | Transcribe then count; second read of rotated copy | Later | adjacent-field | vlm |
| [170](ideas/counting.md#i170) | Tile for a VLM so every target gets at least 1.5 tokens per side, never zoom out | Idea or pitch only | floor-plans | count |
| [171](ideas/counting.md#i171) | Split merged blobs by contour concavity | Idea or pitch only | adjacent-field | count |
| [172](ideas/counting.md#i172) | Integer-bin count classification with Wasserstein loss | Idea or pitch only | adjacent-field | count |
| [173](ideas/counting.md#i173) | Coverage-weighted dense fusion of overlapping passes (SCAHI) | Idea or pitch only | adjacent-field | sheet |
| [174](ideas/counting.md#i174) | Deep Watershed Detector energy-map peaks for counting | Idea or pitch only | adjacent-field | detect |
| [175](ideas/counting.md#i175) | NMS radius scaled by the exemplar size | Idea or pitch only | adjacent-field | count |
| [176](ideas/counting.md#i176) | One-sided over/under-count risk control | Idea or pitch only | adjacent-field | trust |
| [177](ideas/counting.md#i177) | Count by bisection yes/no questions | Idea or pitch only | adjacent-field | vlm |
| [178](ideas/counting.md#i178) | Zero-inflated Poisson per block | Idea or pitch only | adjacent-field | count |
| [179](ideas/counting.md#i179) | Warp the image toward first-pass prototypes before a second SAM 3 pass | Idea or pitch only | authors-claim | count |
| [180](ideas/counting.md#i180) | Cardinality map | Idea or pitch only | search-only | count |
| [181](ideas/counting.md#i181) | Template matching with a reference symbol from a library or legend | Do not try (with the reason) | floor-plans | count, data, vector |
| [182](ideas/counting.md#i182) | Do not count doors and windows by vectorising first and applying rules | Do not try (with the reason) | floor-plans | vector |
| [183](ideas/counting.md#i183) | Median or vote over several VLMs | Do not try (with the reason) | floor-plans | floorplan |
| [184](ideas/counting.md#i184) | Global count head next to the detector | Do not try (with the reason) | adjacent-field | count, detect |
| [185](ideas/counting.md#i185) | DQ-DETR count bands | Do not try (with the reason) | adjacent-field | count |
| [186](ideas/counting.md#i186) | SAM 3 with box exemplars as a counter | Do not try (with the reason) | adjacent-field | count, market |
| [187](ideas/counting.md#i187) | P2PNet/PET point counters | Do not try (with the reason) | adjacent-field | count |
| [188](ideas/counting.md#i188) | Relative thresholds cannot answer zero | Do not try (with the reason) | adjacent-field | count |
| [189](ideas/counting.md#i189) | Fine-tuned VLM writing a count as text | Do not try (with the reason) | adjacent-field | vlm |
| [190](ideas/counting.md#i190) | Untrained tag and crop loops for counting | Do not try (with the reason) | adjacent-field | vlm |
| [191](ideas/counting.md#i191) | Count-only supervision | Do not try (with the reason) | adjacent-field | count |
| [192](ideas/counting.md#i192) | Enumerate objects before counting | Do not try (with the reason) | authors-claim | floorplan |

## Text and room labels (43)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [193](ideas/text.md#i193) | Decode the reader output against the closed label table with exact match and abstention | Try first | adjacent-field | ocr |
| [194](ideas/text.md#i194) | Fine-tune the PP-OCRv6 small recogniser on rendered plus real crops with a cut dictionary | Try first | adjacent-field | ocr |
| [195](ideas/text.md#i195) | Upscale crops 2x to 3x with bicubic or Lanczos before the reader | Try first | adjacent-field | ocr, scale |
| [196](ideas/text.md#i196) | Read every text crop at 0, 90, 180, 270 degrees and keep the in-vocabulary answer | Try first | our-idea | ocr |
| [197](ideas/text.md#i197) | Remove the RapidOCR rule that rotates a crop upright only when height/width >= 1.5 | Try first | our-idea | ocr |
| [198](ideas/text.md#i198) | Fine-tune a text detector on tiles of floor plans | Try next | floor-plans | ocr |
| [199](ideas/text.md#i199) | Detector, rectified crop, small fine-tuned reader instead of full-image spotting | Try next | adjacent-field | ocr, scale |
| [200](ideas/text.md#i200) | docTR detector and recogniser training scripts as the permissive fine-tune path | Try next | adjacent-field | ocr |
| [201](ideas/text.md#i201) | Small VLM reads crops for labels and scale text | Try next | adjacent-field | floorplan |
| [202](ideas/text.md#i202) | Build a confusion table from our dev errors and correct only unambiguous cases | Try next | adjacent-field | ocr |
| [203](ideas/text.md#i203) | Fine-tune PARSeq-S as the recogniser (attention decoder) | Try next | adjacent-field | ocr |
| [204](ideas/text.md#i204) | Rotation and +-5 degree augmentation in recogniser fine-tuning | Try next | adjacent-field | ocr |
| [205](ideas/text.md#i205) | Tune detector scale and thresholds for tiny text | Try next | our-idea | ocr |
| [206](ideas/text.md#i206) | Check readers on Finnish decimal commas | Try next | search-only | scale |
| [207](ideas/text.md#i207) | Keep fixture codes out of room labels (AP, JK, PA, L, MU, PY, SK, IV) | Try next | search-only | ocr |
| [208](ideas/text.md#i208) | Detect text in 256 px tiles | Later | floor-plans | scale |
| [209](ideas/text.md#i209) | Read the printed ratio from a tight crop, not the whole sheet | Later | adjacent-field | scale |
| [210](ideas/text.md#i210) | Mix targeted synthetic crops into real ones when fixing confusable characters | Later | adjacent-field | ocr |
| [211](ideas/text.md#i211) | Detector crops then an off-the-shelf reader for short numerals (PatentOCR pattern) | Later | adjacent-field | ocr |
| [212](ideas/text.md#i212) | Fine-tune on the hard crops, not on all crops | Later | adjacent-field | ocr |
| [213](ideas/text.md#i213) | Real-world super-resolution on text crops only, gated by a vocabulary match | Later | adjacent-field | ocr |
| [214](ideas/text.md#i214) | Fine-tune SVTRv2 (OpenOCR) as an alternative recogniser, CTC and attention variants | Later | adjacent-field | ocr |
| [215](ideas/text.md#i215) | Pretrain a text-region detector on rendered diagrams | Later | adjacent-field | ocr |
| [216](ideas/text.md#i216) | Fine-tune TESTR as an end-to-end label spotter | Later | adjacent-field | ocr |
| [217](ideas/text.md#i217) | LoRA-tuned small VLM as a crop reader on disagreements | Later | adjacent-field | ocr |
| [218](ideas/text.md#i218) | Name which printed area it is | Later | authors-claim | scale |
| [219](ideas/text.md#i219) | PaddleOCR-VL-1.5/1.6 as a tiled second reader and spotter | Later | authors-claim | ocr |
| [220](ideas/text.md#i220) | Read door and window size codes | Later | our-idea | ocr |
| [221](ideas/text.md#i221) | Floor titles (1. KERROS, ALAKERTA, KELLARI) as a plan-count prior | Later | search-only | sheet |
| [222](ideas/text.md#i222) | The 2024 floor-plan text paper (YOLOv7 97.5 wmAP, PARSeq best) | Later | search-only | ocr |
| [223](ideas/text.md#i223) | Swap AGPL YOLO detectors for permissive ones in text patterns | Later | search-only | ocr |
| [224](ideas/text.md#i224) | PP-OCRv5 drops text between thin lines | Idea or pitch only | adjacent-field | ocr |
| [225](ideas/text.md#i225) | VLM readers rewrite short codes: put exact-match decoding after any VLM | Idea or pitch only | adjacent-field | ocr |
| [226](ideas/text.md#i226) | Do not use pretrained scene-text detectors unchanged | Do not try (with the reason) | floor-plans | scale |
| [227](ideas/text.md#i227) | Ask DeepSeek-OCR to locate each vocabulary code with its grounding prompt | Do not try (with the reason) | adjacent-field | ocr |
| [228](ideas/text.md#i228) | Non-commercial spotters (DeepSolo, DPText-DETR, PaLeTTe weights, MapTextPipeline) | Do not try (with the reason) | adjacent-field | ocr |
| [229](ideas/text.md#i229) | eDOCr2 for mechanical drawings | Do not try (with the reason) | adjacent-field | ocr |
| [230](ideas/text.md#i230) | Detector followed by an OCR-free generative reader (Donut or Florence-2) | Do not try (with the reason) | adjacent-field | ocr |
| [231](ideas/text.md#i231) | Models excluded by licence (HunyuanOCR, MinerU2.5 weights, YOLO detectors, Nemotron OCR v2 pending) | Do not try (with the reason) | adjacent-field | ocr |
| [232](ideas/text.md#i232) | Do not put generative super-resolution in the count path | Do not try (with the reason) | adjacent-field | ocr |
| [233](ideas/text.md#i233) | Assume about 90% of read dimension strings are right | Do not try (with the reason) | adjacent-field | scale |
| [234](ideas/text.md#i234) | Tesseract and EasyOCR for 5-12 px labels | Do not try (with the reason) | adjacent-field | ocr |
| [235](ideas/text.md#i235) | Document VLM readers with boxes (dots.ocr, dots.mocr, GLM-OCR, LightOnOCR-2) | Do not try (with the reason) | search-only | ocr |

## Rooms: outlines and types (25)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [236](ideas/rooms.md#i236) | Link a read label to a room by point in polygon as the baseline | Try first | floor-plans | ocr, rooms |
| [237](ideas/rooms.md#i237) | Keep mask-to-polygon conversion minimal | Try first | floor-plans | rooms |
| [238](ideas/rooms.md#i238) | Own wall and room-region net, connected components as rooms | Try first | floor-plans | rooms |
| [239](ideas/rooms.md#i239) | Topology loss on the wall head | Try first | adjacent-field | rooms, vector |
| [240](ideas/rooms.md#i240) | Distance-transform, Voronoi or down-sampling watershed room splitting | Try first | adjacent-field | rooms, vector |
| [241](ideas/rooms.md#i241) | Polygonise all rooms together from one label image | Try first | adjacent-field | rooms |
| [242](ideas/rooms.md#i242) | Set closing radius from a dev gap histogram | Try first | our-idea | rooms |
| [243](ideas/rooms.md#i243) | Mask2Former on room polygons | Try next | floor-plans | rooms |
| [244](ideas/rooms.md#i244) | Snap polygons to the sheet's dominant wall directions | Try next | adjacent-field | rooms |
| [245](ideas/rooms.md#i245) | Use OCR boxes as seeds to split open-plan regions | Try next | authors-claim | rooms |
| [246](ideas/rooms.md#i246) | Cut synthetic gaps into wall masks | Try next | authors-claim | rooms |
| [247](ideas/rooms.md#i247) | Room types as detector classes, compared with the text route | Try next | our-idea | ocr |
| [248](ideas/rooms.md#i248) | Raster2Seq trained from scratch on dev polygons | Later | floor-plans | floorplan, rooms |
| [249](ideas/rooms.md#i249) | Separate extraction from reasoning: symbols first, then text and rooms | Later | adjacent-field | market |
| [250](ideas/rooms.md#i250) | Axis-aligned corner-pair lines across door gaps | Later | search-only | rooms |
| [251](ideas/rooms.md#i251) | Frozen DINOv2 or RADIO plus LoRA head | Idea or pitch only | adjacent-field | rooms |
| [252](ideas/rooms.md#i252) | Frame Field Learning or HiSup polygoniser | Idea or pitch only | adjacent-field | rooms |
| [253](ideas/rooms.md#i253) | ProClosure progressive thickening that freezes closed regions | Idea or pitch only | adjacent-field | rooms |
| [254](ideas/rooms.md#i254) | CubiCasa5K-trained checkpoints on our scans | Do not try (with the reason) | floor-plans | rooms |
| [255](ideas/rooms.md#i255) | Rule-based plan vectoriser loses to learned nets on the same plans | Do not try (with the reason) | floor-plans | vector |
| [256](ideas/rooms.md#i256) | SAM 2 auto and SAM 3 text prompt on 20 dev plans | Do not try (with the reason) | floor-plans | rooms |
| [257](ideas/rooms.md#i257) | Avoid SegFormer and MiT encoders | Do not try (with the reason) | floor-plans | rooms |
| [258](ideas/rooms.md#i258) | VLM asked for rooms or areas | Do not try (with the reason) | floor-plans | rooms |
| [259](ideas/rooms.md#i259) | Pix2Poly, PolyWorld, RoomFormer-type decoders | Do not try (with the reason) | adjacent-field | rooms |
| [260](ideas/rooms.md#i260) | Do not guess room type from layout | Do not try (with the reason) | adjacent-field | rooms |

## Scale (18)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [261](ideas/scale.md#i261) | Take the largest consistent cluster of per-mark scales, not the mean | Try first | floor-plans | scale |
| [262](ideas/scale.md#i262) | Adopt PlanMetric's accepted / insufficient / conflict output | Try first | floor-plans | scale |
| [263](ideas/scale.md#i263) | Fuse door width, wall thickness and printed-area priors by inverse variance | Try next | floor-plans | scale |
| [264](ideas/scale.md#i264) | Read the printed 0-5 m graphic scale bar on Finnish marketing plans | Try next | floor-plans | floorplan, scale |
| [265](ideas/scale.md#i265) | Scale from printed room areas | Try next | floor-plans | scale |
| [266](ideas/scale.md#i266) | Scale from printed dimension strings | Try next | authors-claim | rooms |
| [267](ideas/scale.md#i267) | Replace an OCR dimension value that disagrees with geometry | Later | floor-plans | scale |
| [268](ideas/scale.md#i268) | Read printed scale (1:100) and dimension strings with the same reader | Later | floor-plans | ocr |
| [269](ideas/scale.md#i269) | Plot prior-scale error against number of doors used | Later | adjacent-field | scale |
| [270](ideas/scale.md#i270) | Estimate scale from a door of nominal width and say it is an estimate | Later | adjacent-field | market |
| [271](ideas/scale.md#i271) | Per-image scale self-calibration before tiling | Later | adjacent-field | detect |
| [272](ideas/scale.md#i272) | Median door 0.9 m as default scale | Later | authors-claim | rooms, scale |
| [273](ideas/scale.md#i273) | Use printed door and window sizes in mm as known lengths | Later | search-only | scale |
| [274](ideas/scale.md#i274) | Wall thickness as a ruler | Idea or pitch only | floor-plans | scale |
| [275](ideas/scale.md#i275) | Match a scale-bar style to a template with no-match output | Idea or pitch only | adjacent-field | scale |
| [276](ideas/scale.md#i276) | Tick pitch of a bar by FFT of the summed profile | Idea or pitch only | adjacent-field | scale |
| [277](ideas/scale.md#i277) | A bar from a reduced copy or other plane is a wrong scale | Do not try (with the reason) | adjacent-field | scale |
| [278](ideas/scale.md#i278) | Ask a VLM for scale or area | Do not try (with the reason) | adjacent-field | scale |

## Areas (7)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [279](ideas/areas.md#i279) | Expect area bias from boundaries, not only scale | Try first | floor-plans | scale |
| [280](ideas/areas.md#i280) | Printed room area wins over polygon area | Try first | floor-plans | rooms |
| [281](ideas/areas.md#i281) | Erode regions back by any wall dilation used | Try first | our-idea | rooms |
| [282](ideas/areas.md#i282) | Model the flat total against sum of rooms | Try next | floor-plans | scale |
| [283](ideas/areas.md#i283) | State how scale error becomes area error | Later | adjacent-field | market |
| [284](ideas/areas.md#i284) | Prefer an area reference to a length reference for areas | Idea or pitch only | adjacent-field | scale |
| [285](ideas/areas.md#i285) | Pixel counting beats VLMs for areas | Do not try (with the reason) | adjacent-field | floorplan |

## Confidence and abstention (47)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [286](ideas/confidence.md#i286) | Plain max confidence as the baseline every fancier score must beat | Try first | floor-plans | ocr, trust |
| [287](ideas/confidence.md#i287) | Call a scale 'scaled' only if two independent printed marks agree within 2% | Try first | floor-plans | market, scale |
| [288](ideas/confidence.md#i288) | Plan-level sure/review gate with Learn-then-Test (MAPIE) | Try first | adjacent-field | market, trust |
| [289](ideas/confidence.md#i289) | Accuracy at a stated coverage: answer x% at y% exact, refuse the rest | Try first | adjacent-field | market |
| [290](ideas/confidence.md#i290) | Exact binomial (Clopper-Pearson) upper bound on error of accepted answers | Try first | adjacent-field | trust |
| [291](ideas/confidence.md#i291) | P(modal count) and count entropy from calibrated detection scores | Try first | adjacent-field | count, trust |
| [292](ideas/confidence.md#i292) | Always report how often the gate opens | Try first | adjacent-field | trust |
| [293](ideas/confidence.md#i293) | Evaluate the threshold with sheet-level resampling and a fit/validation split | Try first | adjacent-field | market |
| [294](ideas/confidence.md#i294) | Gate with three states: pass, fail with reason, could not assess | Try first | adjacent-field | sheet |
| [295](ideas/confidence.md#i295) | Image score from the few most confident detections, not the sum | Try first | adjacent-field | trust |
| [296](ideas/confidence.md#i296) | Build the review list around missed items, not false ones | Try next | floor-plans | market |
| [297](ideas/confidence.md#i297) | Sanity band: summed rooms within +-25% of a listed area | Try next | floor-plans | scale |
| [298](ideas/confidence.md#i298) | Count spread across rotations, tile offsets and scales | Try next | adjacent-field | detect, trust |
| [299](ideas/confidence.md#i299) | Show inliers over marks and residual as the estimate flag | Try next | adjacent-field | scale |
| [300](ideas/confidence.md#i300) | Small classifier on cheap per-plan features predicting 'answer right' | Try next | adjacent-field | trust |
| [301](ideas/confidence.md#i301) | Gate by OCR mean confidence and label-hit count | Try next | adjacent-field | ocr, sheet |
| [302](ideas/confidence.md#i302) | Per class and box-size monotone calibration of detection scores | Try next | adjacent-field | count, trust |
| [303](ideas/confidence.md#i303) | Calibrate and report per sheet source (CubiCasa-like, scans, phone photos, rotated) | Try next | adjacent-field | trust |
| [304](ideas/confidence.md#i304) | Snap a read ratio to 1:50, 1:100, 1:200 as a check | Try next | adjacent-field | scale |
| [305](ideas/confidence.md#i305) | Gate on median symbol height in pixels | Try next | adjacent-field | sheet |
| [306](ideas/confidence.md#i306) | Flag regions with two OCR labels or implausible area | Try next | authors-claim | rooms |
| [307](ideas/confidence.md#i307) | Entropy map flags rooms whose area to refuse | Try next | authors-claim | rooms |
| [308](ideas/confidence.md#i308) | Flag plans whose labels are under about 6 px instead of guessing | Try next | our-idea | ocr |
| [309](ideas/confidence.md#i309) | Accept a count only when it is stable across thresholds | Try next | our-idea | count |
| [310](ideas/confidence.md#i310) | Reject scales that give implausible flat sizes | Try next | search-only | scale |
| [311](ideas/confidence.md#i311) | Ensemble or checkpoint-spread uncertainty to choose marks for review | Later | floor-plans | trust |
| [312](ideas/confidence.md#i312) | Line-segment statistics as a plausibility check on detector counts | Later | floor-plans | vector |
| [313](ideas/confidence.md#i313) | Set the abstain threshold per batch from a target error | Later | adjacent-field | sheet |
| [314](ideas/confidence.md#i314) | Confidence from perception, layout and validation channels, not the model's own | Later | adjacent-field | market |
| [315](ideas/confidence.md#i315) | Hold one mark back as a check | Later | adjacent-field | scale |
| [316](ideas/confidence.md#i316) | Image-level 'detector missed something' classifier | Later | adjacent-field | trust |
| [317](ideas/confidence.md#i317) | Self-consistency of one model as confidence | Later | adjacent-field | market, trust |
| [318](ideas/confidence.md#i318) | Route only uncertain sheets to a person | Later | adjacent-field | market |
| [319](ideas/confidence.md#i319) | Printed scale as prior, independent estimate as check | Later | adjacent-field | scale |
| [320](ideas/confidence.md#i320) | Venn-Abers or beta calibration of the final score | Later | adjacent-field | trust |
| [321](ideas/confidence.md#i321) | Grade a sheet by its worst region | Later | adjacent-field | market |
| [322](ideas/confidence.md#i322) | Re-detect at higher zoom before sending a plan to review | Later | adjacent-field | trust |
| [323](ideas/confidence.md#i323) | Vote across two pixel shifts for any VLM reader | Later | authors-claim | ocr |
| [324](ideas/confidence.md#i324) | Probe a VLM's hidden states to detect counting errors | Idea or pitch only | adjacent-field | market |
| [325](ideas/confidence.md#i325) | ContrastiveConf per-image reliability from kept and dropped DETR predictions | Idea or pitch only | adjacent-field | trust |
| [326](ideas/confidence.md#i326) | Do not read agreement as proof | Do not try (with the reason) | floor-plans | scale |
| [327](ideas/confidence.md#i327) | Capture-recapture on overlapping counters | Do not try (with the reason) | adjacent-field | trust |
| [328](ideas/confidence.md#i328) | Reject by count-interval width | Do not try (with the reason) | adjacent-field | trust |
| [329](ideas/confidence.md#i329) | Do not choose a threshold on the data it is scored on | Do not try (with the reason) | adjacent-field | market |
| [330](ideas/confidence.md#i330) | Do not use a model's own stated confidence for auto-approval | Do not try (with the reason) | adjacent-field | market |
| [331](ideas/confidence.md#i331) | Re-render the prediction and compare pixels | Do not try (with the reason) | adjacent-field | trust |
| [332](ideas/confidence.md#i332) | VLM token or verbalized confidence as a count gate | Do not try (with the reason) | adjacent-field | trust |

## Conflicts between sources (20)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [333](ideas/conflicts.md#i333) | Measure how often two counters are wrong together | Try first | adjacent-field | trust |
| [334](ideas/conflicts.md#i334) | After the detector, show the boxes and ask a VLM for what is missing | Try next | floor-plans | count, detect, floorplan, vlm |
| [335](ideas/conflicts.md#i335) | Training-free union of two systems with an ink gate | Try next | floor-plans | vector |
| [336](ideas/conflicts.md#i336) | Stage-8 second count by agreement of independent recognisers, not render-and-compare | Try next | adjacent-field | count, detect, floorplan, sheet, trust, vector, vlm |
| [337](ideas/conflicts.md#i337) | Free cross-checks: printed areas, legend, window counts per room, plan count | Try next | adjacent-field | market |
| [338](ideas/conflicts.md#i338) | Plan count from three independent counters, flag when they disagree | Try next | adjacent-field | sheet |
| [339](ideas/conflicts.md#i339) | Two structurally different readings of one plan, disagreement as a feature | Try next | adjacent-field | trust |
| [340](ideas/conflicts.md#i340) | Plausibility rules as a second, cheap validity filter | Try next | adjacent-field | trust |
| [341](ideas/conflicts.md#i341) | Constraint layer over detections: openings sit on walls, no two overlap | Later | floor-plans | floorplan, sheet, vector |
| [342](ideas/conflicts.md#i342) | Propose with template matching, accept or reject each crop with a small VLM | Later | floor-plans | count |
| [343](ideas/conflicts.md#i343) | Re-crop and re-run on a conflict | Later | adjacent-field | sheet |
| [344](ideas/conflicts.md#i344) | Vote across two different readers (PP-OCR and PARSeq) | Later | adjacent-field | ocr |
| [345](ideas/conflicts.md#i345) | Keep a CTC reader as a cross-check against an attention reader | Later | adjacent-field | ocr |
| [346](ideas/conflicts.md#i346) | Detect symbols first, mask them out, then check the remaining line map | Later | adjacent-field | vector |
| [347](ideas/conflicts.md#i347) | Use a read label as evidence for a fixture symbol inside the room | Later | adjacent-field | ocr |
| [348](ideas/conflicts.md#i348) | Validators that trigger a local re-read of conflicting regions | Later | adjacent-field | floorplan, vector |
| [349](ideas/conflicts.md#i349) | Use the second reader's disagreement as an input to conflicts | Later | our-idea | ocr |
| [350](ideas/conflicts.md#i350) | Check one-letter labels (K, S, P, H) against room context | Later | our-idea | ocr |
| [351](ideas/conflicts.md#i351) | Match doors to the door schedule by tag and ask about the rest | Idea or pitch only | authors-claim | market |
| [352](ideas/conflicts.md#i352) | Show only new instances when a revised drawing is re-run | Idea or pitch only | authors-claim | market |

## Proof and review interface (20)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [353](ideas/proof-ui.md#i353) | Bucket the scale quality like Solar imagery_quality | Try first | adjacent-field | scale |
| [354](ideas/proof-ui.md#i354) | Per-mark yes/no review on magnified crops | Try next | adjacent-field | count, floorplan, rooms, trust |
| [355](ideas/proof-ui.md#i355) | Draw the claimed scale back on the plan | Try next | adjacent-field | scale |
| [356](ideas/proof-ui.md#i356) | Shade uncertain items and withdraw the guarantee on poor images | Try next | adjacent-field | market |
| [357](ideas/proof-ui.md#i357) | High, medium, low per element, not a probability | Try next | adjacent-field | market |
| [358](ideas/proof-ui.md#i358) | Draw two kinds of mark: counted and check-this | Try next | adjacent-field | market |
| [359](ideas/proof-ui.md#i359) | Let the user drag a reference line of known length | Later | adjacent-field | scale |
| [360](ideas/proof-ui.md#i360) | Keep overlays and flag crowded or edge objects | Later | adjacent-field | count, trust |
| [361](ideas/proof-ui.md#i361) | Show flagged plans also without the detector overlay | Later | adjacent-field | trust |
| [362](ideas/proof-ui.md#i362) | Seed known-wrong plans into the audit stream | Later | adjacent-field | trust |
| [363](ideas/proof-ui.md#i363) | Reveal the machine's total only after the reviewer counts | Later | adjacent-field | market |
| [364](ideas/proof-ui.md#i364) | Two scores per count: is the count right, is the pointer right | Later | adjacent-field | market |
| [365](ideas/proof-ui.md#i365) | Make the review a gate: a count enters the answer only after it is accepted | Later | authors-claim | market |
| [366](ideas/proof-ui.md#i366) | Click one symbol, count the matches, with a similarity slider and deselect | Later | authors-claim | market |
| [367](ideas/proof-ui.md#i367) | Show the detected plan boxes and per-plan counts in the UI | Later | our-idea | sheet |
| [368](ideas/proof-ui.md#i368) | VLM proposes, deterministic gates decide from image evidence | Idea or pitch only | floor-plans | market |
| [369](ideas/proof-ui.md#i369) | Schematic pipeline: independent VLM pass with agreement score | Idea or pitch only | adjacent-field | detect |
| [370](ideas/proof-ui.md#i370) | Annotator-prompted DETR | Idea or pitch only | authors-claim | count |
| [371](ideas/proof-ui.md#i371) | Show a structural plausibility badge in the proof UI | Idea or pitch only | our-idea | vector |
| [372](ideas/proof-ui.md#i372) | Marks with many false positives can hurt | Do not try (with the reason) | adjacent-field | market |

## Answering questions (9)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [373](ideas/answering.md#i373) | Refuse a sheet and say why | Try first | adjacent-field | count, market |
| [374](ideas/answering.md#i374) | Report counts and room ratios separately from absolute areas | Try first | authors-claim | scale |
| [375](ideas/answering.md#i375) | Door detector in front of an LLM lifts exact counts, most on scans | Try next | floor-plans | count, vector |
| [376](ideas/answering.md#i376) | Enlarge symbols to ~48 px and split views without zooming out | Try next | adjacent-field | floorplan |
| [377](ideas/answering.md#i377) | Give the answering stage an explicit recovered structure instead of pixels | Later | adjacent-field | vector, vlm |
| [378](ideas/answering.md#i378) | Answer odd questions by running code over extraction_v1 | Idea or pitch only | adjacent-field | market |
| [379](ideas/answering.md#i379) | Write detector boxes into the VLM prompt | Idea or pitch only | adjacent-field | count |
| [380](ideas/answering.md#i380) | Pipeline shape: detector, assembly rules, VLM only as checker | Idea or pitch only | adjacent-field | floorplan |
| [381](ideas/answering.md#i381) | A clean BIM does not give a free exact count | Do not try (with the reason) | adjacent-field | market |

## Training data and pretraining (50)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [382](ideas/data.md#i382) | Hugging Face licence tags do not reflect training data | Try first | floor-plans | data, detect, rooms |
| [383](ideas/data.md#i383) | Export a per-plan box from the dev labels | Try first | our-idea | sheet |
| [384](ideas/data.md#i384) | Count printed marks per sheet on dev | Try first | our-idea | scale |
| [385](ideas/data.md#i385) | Take label text positions from the dataset SVG text elements | Try first | our-idea | ocr |
| [386](ideas/data.md#i386) | Closed table of Finnish and Swedish room-label codes with room types | Try first | search-only | ocr |
| [387](ideas/data.md#i387) | Directed copy-paste of rare classes into blank regions | Try next | floor-plans | data, detect, floorplan |
| [388](ideas/data.md#i388) | Use the public FP-TXT text-box annotations to train a detector | Try next | floor-plans | ocr |
| [389](ideas/data.md#i389) | Render training crops of our label codes over real drawing backgrounds | Try next | adjacent-field | data, ocr |
| [390](ideas/data.md#i390) | Pretrain or mix with licence-clean synthetic plans | Try next | adjacent-field | count, data, rooms, vlm |
| [391](ideas/data.md#i391) | Pseudo-label crops: an OCR box inside a room polygon of class X is a crop for the codes of class X | Try next | our-idea | ocr |
| [392](ideas/data.md#i392) | Use CubiCasa5K sub-category folders as a free style label | Later | floor-plans | sheet |
| [393](ideas/data.md#i393) | Re-render dev layouts clean and scanned to build paired data | Later | floor-plans | data |
| [394](ideas/data.md#i394) | FloorPlanCAD (non-commercial) as a local second pretraining stage for fixtures | Later | floor-plans | data |
| [395](ideas/data.md#i395) | fpgen: MIT procedural generator with fixture boxes and a registered degradation stack | Later | floor-plans | data, floorplan |
| [396](ideas/data.md#i396) | Fix labels before changing the detector | Later | floor-plans | market |
| [397](ideas/data.md#i397) | LegendSpot data for dev tests only | Later | floor-plans | count |
| [398](ideas/data.md#i398) | Clean overlapping CubiCasa5K polygons before training | Later | floor-plans | rooms |
| [399](ideas/data.md#i399) | Pre-train on CC BY synthetic plan sets | Later | adjacent-field | market |
| [400](ideas/data.md#i400) | Overlay synthetic plans on real blank scanned paper | Later | adjacent-field | data, detect |
| [401](ideas/data.md#i401) | Keep synthetic at or below half the real count | Later | adjacent-field | data, floorplan, vector |
| [402](ideas/data.md#i402) | Synthetic plans must reuse real wall and room layouts | Later | adjacent-field | data, market |
| [403](ideas/data.md#i403) | SAM 3 as a pseudo-labeller | Later | adjacent-field | floorplan |
| [404](ideas/data.md#i404) | Rare and look-alike classes fail on small sets | Later | adjacent-field | detect |
| [405](ideas/data.md#i405) | Pretrain on synthetic plans with dimension chains | Later | adjacent-field | scale |
| [406](ideas/data.md#i406) | Pretrain on cleaned ResPlan | Later | authors-claim | data, floorplan, rooms |
| [407](ideas/data.md#i407) | Drop crops that contradict the dev answer's room counts | Later | our-idea | ocr |
| [408](ideas/data.md#i408) | Label a multi-plan sheet set with plan boxes | Later | search-only | sheet |
| [409](ideas/data.md#i409) | Independent plans for calibration and shift tests | Later | search-only | trust |
| [410](ideas/data.md#i410) | Render Swiss Dwellings openings and sanitary features | Later | search-only | floorplan |
| [411](ideas/data.md#i411) | BlueprintSymVL as a clean-licence sanity set | Idea or pitch only | floor-plans | count |
| [412](ideas/data.md#i412) | A few dozen clean in-domain annotations beat noisy extras | Idea or pitch only | floor-plans | floorplan |
| [413](ideas/data.md#i413) | Split multi-plan CubiCasa5K instances by closed contours of the label mask | Idea or pitch only | floor-plans | sheet |
| [414](ideas/data.md#i414) | Hybrid coverage plus uncertainty picker for next labels | Idea or pitch only | adjacent-field | detect |
| [415](ideas/data.md#i415) | Erase symbols and lower the label | Idea or pitch only | adjacent-field | vlm |
| [416](ideas/data.md#i416) | Place synthetic symbols where they occur and cluster them | Idea or pitch only | adjacent-field | data |
| [417](ideas/data.md#i417) | Synthesise training pages by perturbing real label graphs | Idea or pitch only | adjacent-field | vector |
| [418](ideas/data.md#i418) | AntPlan fixture counts and placements as generator statistics | Idea or pitch only | search-only | data |
| [419](ideas/data.md#i419) | Finnish room programme statistics for a generator | Idea or pitch only | search-only | data |
| [420](ideas/data.md#i420) | Floor Plan CIS: 500 real raw plans as unlabelled or hard-negative data | Idea or pitch only | search-only | data |
| [421](ideas/data.md#i421) | 1M CC BY generated furnished plans as a pretraining stage for fixtures | Idea or pitch only | search-only | data |
| [422](ideas/data.md#i422) | Negative: ArchCAD-400K as a pretraining source | Do not try (with the reason) | floor-plans | data |
| [423](ideas/data.md#i423) | Negative: synthetic plans added to thousands of real plans do not move the headline score | Do not try (with the reason) | floor-plans | data |
| [424](ideas/data.md#i424) | Negative: diffusion-generated images as labelled symbol data | Do not try (with the reason) | adjacent-field | data |
| [425](ideas/data.md#i425) | Random-scatter synthetic symbols do not transfer | Do not try (with the reason) | adjacent-field | market |
| [426](ideas/data.md#i426) | Synthetic-only training leaves a large real-scan gap | Do not try (with the reason) | adjacent-field | data, detect, vector |
| [427](ideas/data.md#i427) | Negative: clever selection of synthetic scenes | Do not try (with the reason) | adjacent-field | data |
| [428](ideas/data.md#i428) | CC BY synthetic plans generator | Do not try (with the reason) | search-only | floorplan |
| [429](ideas/data.md#i429) | Negative: rule-based layout generators written by hand | Do not try (with the reason) | search-only | data |
| [430](ideas/data.md#i430) | Roboflow door and window sets as extra data | Do not try (with the reason) | search-only | data, floorplan |
| [431](ideas/data.md#i431) | Moondream fine-tuning | Do not try (with the reason) | search-only | vlm |

## Evaluation (69)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [432](ideas/eval.md#i432) | AECV-Bench as the public exact-count yardstick | Try first | floor-plans | count, floorplan, market |
| [433](ideas/eval.md#i433) | Report share of rooms within 5, 10 and 25 percent | Try first | floor-plans | rooms |
| [434](ideas/eval.md#i434) | Diagnose misses versus loose boxes versus size floor on dev | Try first | floor-plans | count, data, detect, floorplan, market, rooms, sheet |
| [435](ideas/eval.md#i435) | Report boundary IoU next to mIoU | Try first | floor-plans | rooms |
| [436](ideas/eval.md#i436) | CubiCasa5K annotation misalignment and noise | Try first | floor-plans | floorplan, market, ocr, trust |
| [437](ideas/eval.md#i437) | Report exact, within 1, MAE and bias, by subgroup and count bin | Try first | floor-plans | count, floorplan, ocr |
| [438](ideas/eval.md#i438) | Score exact counts and within-one counts, not mAP alone | Try first | floor-plans | data |
| [439](ideas/eval.md#i439) | Report exact match by number of objects per plan | Try first | floor-plans | market |
| [440](ideas/eval.md#i440) | Report counts, not AP | Try first | floor-plans | floorplan, sheet |
| [441](ideas/eval.md#i441) | fpeval scorer and fpgen degraded plans | Try first | floor-plans | rooms |
| [442](ideas/eval.md#i442) | PlanQ U-Net plus connected components as the floor | Try first | floor-plans | floorplan |
| [443](ideas/eval.md#i443) | Always run a real-only control and read per-class dev counts before keeping a synthetic source | Try first | floor-plans | data |
| [444](ideas/eval.md#i444) | Evaluate on whole held-out plans, not on tile validation | Try first | floor-plans | data |
| [445](ideas/eval.md#i445) | Plan the number of checked plans before claiming a guarantee | Try first | adjacent-field | trust |
| [446](ideas/eval.md#i446) | Score detectors by centre match and per-image exact count, not AP50:95 | Try first | adjacent-field | detect |
| [447](ideas/eval.md#i447) | Split crops by plan source, as the rebar study split by design institute | Try first | adjacent-field | ocr, sheet |
| [448](ideas/eval.md#i448) | Define one window per drawn cell once | Try first | adjacent-field | count, floorplan, rooms |
| [449](ideas/eval.md#i449) | Score scale by its effect on area share, not px per metre | Try first | adjacent-field | scale |
| [450](ideas/eval.md#i450) | Compare confidence scores by failure AUROC and AUGRC, with miss-aware metrics | Try first | adjacent-field | sheet, trust |
| [451](ideas/eval.md#i451) | Score plan splitters by exact plan count, not box overlap | Try first | adjacent-field | sheet |
| [452](ideas/eval.md#i452) | Count merged and split rooms, not IoU alone | Try first | adjacent-field | rooms |
| [453](ideas/eval.md#i453) | Leak-check external data with rotation- and mirror-invariant perceptual hashes | Try first | adjacent-field | data |
| [454](ideas/eval.md#i454) | Treat the plan, not the question, as the independent unit | Try first | adjacent-field | trust |
| [455](ideas/eval.md#i455) | Choose the threshold on one split and certify on a disjoint one | Try first | adjacent-field | trust |
| [456](ideas/eval.md#i456) | Print both exact-match rate and sum-weighted error | Try first | adjacent-field | market |
| [457](ideas/eval.md#i457) | Compute the ceiling on the share of plans markable as sure | Try first | adjacent-field | trust |
| [458](ideas/eval.md#i458) | Per-plan 'seen in training' flag in the calibration table | Try first | adjacent-field | trust |
| [459](ideas/eval.md#i459) | Decide whether closets and cabinets are rooms | Try first | authors-claim | rooms |
| [460](ideas/eval.md#i460) | 200-image smoke test before each full fine-tune | Try first | authors-claim | detect |
| [461](ideas/eval.md#i461) | Quote the independent Togal study correctly | Try first | authors-claim | market |
| [462](ideas/eval.md#i462) | Keep a ledger of what each vendor percentage measures | Try first | authors-claim | market |
| [463](ideas/eval.md#i463) | Baseline: always answer one plan per sheet | Try first | our-idea | sheet |
| [464](ideas/eval.md#i464) | Exact-count rate predicted from per-object recall | Try first | our-idea | detect |
| [465](ideas/eval.md#i465) | Smoke test for the reported v6 ONNX non-ASCII output | Try first | our-idea | ocr |
| [466](ideas/eval.md#i466) | Fix the wall convention of the gold area before measuring | Try first | our-idea | rooms |
| [467](ideas/eval.md#i467) | Report per image source: scan, phone photo, CAD export, rotated | Try next | adjacent-field | market, scale |
| [468](ideas/eval.md#i468) | Report recall by symbol area and by sheet size | Try next | adjacent-field | detect, sheet |
| [469](ideas/eval.md#i469) | Score exact count and matched instances, report the gap | Try next | adjacent-field | count, floorplan |
| [470](ideas/eval.md#i470) | Report false marks per plan next to exact match | Try next | adjacent-field | market |
| [471](ideas/eval.md#i471) | Measure read-invention rate, not only exact match | Try next | adjacent-field | ocr |
| [472](ideas/eval.md#i472) | Intrusion ratio and shared-edge recall as eval checks | Try next | adjacent-field | rooms |
| [473](ideas/eval.md#i473) | Measure review minutes and answers changed, with wrong suggestions in the test | Try next | adjacent-field | market |
| [474](ideas/eval.md#i474) | Sweep rendered codes over height, rotation and blur to find the readable cliff per engine | Try next | adjacent-field | ocr |
| [475](ideas/eval.md#i475) | Assert the compared quantity before reporting a score | Try next | adjacent-field | scale |
| [476](ideas/eval.md#i476) | Measure false positives after super-resolution on drawings | Try next | adjacent-field | sheet |
| [477](ideas/eval.md#i477) | Report exact match and a coverage x precision composite side by side | Try next | authors-claim | market |
| [478](ideas/eval.md#i478) | Counting may need only IoU 0.5 boxes, so scan shift costs counts less than strict localisation | Try next | our-idea | vector |
| [479](ideas/eval.md#i479) | Older Kimi weak on drawing sheets | Later | floor-plans | vlm |
| [480](ideas/eval.md#i480) | State accuracy per use: exact on counts up to 8, within one above | Later | adjacent-field | market |
| [481](ideas/eval.md#i481) | Print the accuracy formula, sample size and exclusions | Later | adjacent-field | market |
| [482](ideas/eval.md#i482) | Judge pretraining on precision at fixed recall | Later | adjacent-field | data |
| [483](ideas/eval.md#i483) | Audit released plans by confidence stratum and weight back | Later | adjacent-field | trust |
| [484](ideas/eval.md#i484) | Measure two read modes: second read after the human, and concurrent | Later | adjacent-field | market |
| [485](ideas/eval.md#i485) | Check whether CubiCasa-trained weights lean on Finnish labels | Later | authors-claim | floorplan |
| [486](ideas/eval.md#i486) | Report coverage and precision separately | Later | authors-claim | market |
| [487](ideas/eval.md#i487) | Include unanswerable questions in the test | Later | authors-claim | market |
| [488](ideas/eval.md#i488) | Test a scale route at two resolutions | Later | authors-claim | scale |
| [489](ideas/eval.md#i489) | Monitor exchangeability on the reviewed stream | Later | search-only | trust |
| [490](ideas/eval.md#i490) | Per-class fixture AP reference numbers | Idea or pitch only | floor-plans | detect |
| [491](ideas/eval.md#i491) | Direct detector numbers on raster plans for reference | Idea or pitch only | floor-plans | vector |
| [492](ideas/eval.md#i492) | Upper bound: exact primitives vs raster detection | Idea or pitch only | adjacent-field | vector |
| [493](ideas/eval.md#i493) | Handoff-H1 and TAKEOFFBENCH-V1 as the claim to answer | Idea or pitch only | authors-claim | market |
| [494](ideas/eval.md#i494) | Keep an append-only ledger of scored runs by commit | Idea or pitch only | authors-claim | market |
| [495](ideas/eval.md#i495) | Community CubiCasa-trained VLM adapters | Do not try (with the reason) | floor-plans | vlm |
| [496](ideas/eval.md#i496) | Direct multimodal-LLM count baseline to beat | Do not try (with the reason) | floor-plans | count, floorplan, market, vector, vlm |
| [497](ideas/eval.md#i497) | Do not fuse doors and windows into one metric | Do not try (with the reason) | floor-plans | market |
| [498](ideas/eval.md#i498) | Negative: select checkpoints on synthetic validation | Do not try (with the reason) | adjacent-field | data |
| [499](ideas/eval.md#i499) | Do not cite SEO tutorials as tests | Do not try (with the reason) | authors-claim | market |
| [500](ideas/eval.md#i500) | Hobby classical repos as baselines | Do not try (with the reason) | search-only | rooms |

## Product, market and pitch (11)

| # | Idea | Group | Evidence | Scopes |
| --- | --- | --- | --- | --- |
| [501](ideas/product.md#i501) | Honest one-sentence guarantee with N, bound, source mix and release share | Try first | adjacent-field | trust |
| [502](ideas/product.md#i502) | Include reviewer error in the stated guarantee | Try first | adjacent-field | trust |
| [503](ideas/product.md#i503) | CPU inference timing of the chosen detector | Try next | adjacent-field | detect |
| [504](ideas/product.md#i504) | Detector as ingest-once step: cost per page | Try next | our-idea | detect |
| [505](ideas/product.md#i505) | Put a price per sheet next to the accuracy | Later | authors-claim | market |
| [506](ideas/product.md#i506) | Few real labelled sheets from a new drawing style close most of the gap | Idea or pitch only | adjacent-field | data |
| [507](ideas/product.md#i507) | Product: user confirms which classes a sheet contains | Idea or pitch only | adjacent-field | data |
| [508](ideas/product.md#i508) | Expose counts as agent tools | Idea or pitch only | authors-claim | market |
| [509](ideas/product.md#i509) | Write IFC from extraction_v1 with IfcOpenShell | Idea or pitch only | authors-claim | market |
| [510](ideas/product.md#i510) | Charge only for accepted results | Idea or pitch only | authors-claim | market |
| [511](ideas/product.md#i511) | Human-in-the-loop correction of first-pass openings | Idea or pitch only | authors-claim | vector |
