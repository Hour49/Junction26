# lit-vector-a: raster to vector, field and state of the art (L11, angle a)

Worker: lit-vector-a. Read-only. All sources opened on 2026-11-14 (Helsinki). Reading log with one line per source:
`lit-vector-a-log.md`. "verified" = I read it on the page named; "reported" = the authors' own claim, or a number I
could only see in a summary. Angle a only: field and 2025-2026 work. Sideways transfers belong to lit-vector-b,
practical fit to lit-vector-c; where I read a transfer source on the way, it is here with one line.

## 0. Answer to the scope question

**Is there evidence that vectorise-then-rules beats direct detection on scanned plans? No, and I found none for
counting at all.** What exists, all verified from the pages:

1. No paper in L11 reports a door, window, toilet or sink *count* from a vectorise-then-rules route. The vector
   routes report wall F1, room F1, raster IoU of lines, or panoptic quality on CAD primitives.
2. Where a classical route sits in the same table as a learned one, the classical parts lose; the learned detector is
   the best part of every modular route:
   - SESYD, synthetic (Rezvanifar et al. 2020, Table 4): classical spotting instance F-score 75.5 to 85.3 (98.5 on
     12 of 16 symbols only) against 97.9 to 99.1 for a YOLO-style CNN. On 25 real plans the CNN (ResNet50 backbone) reaches mAP 59.0,
     AP50 89.3, AP75 69.1; windows are its worst class (AP50 75.6, AP75 31.8). Self-reported, SESYD has no clutter.
   - P&ID digitisation (2025): modular route (learned Faster R-CNN symbols, separate line detection, graph rules) beats the
     end-to-end Relationformer on symbol classification (86.58 vs 73.49) and loses badly on structure (nodes 52.14
     vs 82.18, edges 45.89 vs 76.79). The authors say the modular route depends on good line-detection parameters.
   - Raster-to-Vector (ICCV 2017, 100 test plans, 256 px): a classical rule-based pipeline (Ahmed et al.) reaches
     wall-junction accuracy/recall 74.9/57.5 and opening 61.3/48.7; the learned net with an integer-programming
     constraint layer reaches 94.7/91.7 and 91.9/90.2. Without the constraint layer opening accuracy is 67.9 and icon
     accuracy 22.3 (recall 77.4); with it 91.9 and 84.0. So "learned detector plus a rule/constraint filter on top" is
     the pattern with measured gains in precision, at a small recall cost. Doors and windows are not separated in that
     data and no per-image counts are given.
   - Region-graph parsing (Zernike moments plus GNN, 2025): average F1 94 to 95 on clean CubiCasa5K plans and 24 to 34
     on 122 scanned plans from another dataset, door F1 1.9 to 3.0. That is a domain-shift result (trained on
     CubiCasa5K), not a clean comparison, but it is the only number on scans.
3. The only controlled raster-versus-vector input comparison (Drawing2CAD, 2025, same model, command accuracy 80.78
   with exact vectors vs 75.60 with a raster render, Chamfer 11.52 vs 17.67 x1e-2) uses vectors taken from the CAD
   model, not vectors recovered from the image, so it says what an exact vectoriser would be worth (about 5 points
   on that task), not what a real one would deliver.
4. The one place a "detect, then assemble by rules" route wins is wall structure from heatmaps on real CubiCasa5K
   scans: +2.7 wall F1 over autoregressive decoding of the same network (0.818 vs 0.790), and it loses by 8.2 on clean
   synthetic plans. Walls, not counts.
5. In-house evidence agrees: canonical swing template 3/40 exact doors, Hough arcs 2/40 (00-context.md section 2).

6. Late-round additions (2026-11-14, sections 5e, 5o, 5s): exact-count baselines exist only for direct readers.
   AECV-Bench (120 plans): best multimodal model gets 0.39 exact-match on doors and 0.34 on windows, others 0.03-0.28.
   A door detector in front of an LLM lifts exact toilet counts on scanned CVC-FP from 40.0 to 86.7 % (2509.17283).
   The one scan precedent for a learned line detector is pretrained DeepLSD on electrical plans, line precision 0.94,
   recall 0.95, with pre- and post-filtering (Urbieta et al.). A recovered graph lifts small VLMs by about 35 points
   on P&ID questions. All point the same way: a learned detector or line source plus a structure/constraint filter,
   not vectorise-then-rules alone.


Upper bound, if exact vectors were available: TextCAD's authors rebuilt CubiCasa5K from its SVGs as CAD primitives (10
thing classes: window, door, closet, electrical appliance, toilet, sink, sauna bench, fireplace, bathtub, chimney, plus
wall and railing) and re-trained the baselines (Table 1 verbatim, no prior): VecFormer PQ 94.58 (things 95.59), TextCAD
96.53 (things 97.23), DPSS 91.33, SymPoint-V2 91.47. These are ground-truth primitives, not primitives recovered from
the PNG, and record 0003 bars SVG lookup at answer time, so this is a ceiling for a perfect vectoriser, not a route.

**Can any vector symbol spotter take vectorised raster, and with what loss?** None has been tried. SymPoint's input is
a set of typed primitives (line, arc, circle, ellipse, one-hot type) and its paper presents rasterising CAD for image
detection as the approach it replaces; CADSpotting needs points sampled along primitives plus a colour channel;
VecFormer samples line segments from primitives and uses primitive identifiers as a position cue; DPSS adds an image
pathway but still classifies each CAD primitive. A line detector (row 1) gives untyped straight segments, so arcs
(door swings), hatching and text glyphs would all have to be turned into primitives first, and no paper measures what
that costs. Treat the vector family as unavailable for rasters.

So the vector family gives us no ready second counter for doors and windows. It may still give a *structural* signal
for plans per sheet and for room outlines (section 3).

## 1. Top 5, ranked

Ranking is by "most useful to us in the next 24 hours", floor-plan work and transfers in one list. The field offers
no strong candidate; these are the least bad, each with its verdict.

1. **ScaleLSD as a line-evidence layer (try, small).** CVPR 2025; code MIT, weights Apache-2.0, no CubiCasa5K in
   training (leak: no). Gives line segments with endpoints that a rule layer can turn into door-leaf and window-cell
   evidence for the stage-8 second counter. Verdict: **try**, as an experiment of about one hour on 100 dev images,
   not as the main counter. Reason it ranks first: only permissively licensed, leak-free, trained-on-anything
   detector in this scope that runs today. Reason to doubt: ScaleLSD itself never tested on drawings (section 2, row 1); its sibling DeepLSD was tested pretrained on scanned electrical plans, P 0.94 R 0.95 (section 5e).
   Update 2026-11-14 (late rounds): at default thresholds ScaleLSD is high-precision, low-recall on generic lines (ADLA
   Table 4: AR 0.539), so the experiment must lower its threshold and filter by ink and geometry; the one precedent
   on scans is DeepLSD pretrained on electrical plans (P 0.94, R 0.95, section 5e), and DeepLSD has the same AGPL
   pytlsd trap (section 5l). Arcs: EdgeDrawing returns no partial arcs (5n).
   Dependency trap (verified): `requirements.txt` installs `pytlsd` from git; its wrapper repo says MIT but its
   `src/lsd.cpp` carries the AGPL-3 header of the original LSD. Only the line-matching demo imports it and `setup.py`
   does not list it, so install with `pip install -e .` plus the packages `setup.py` names, not the requirements file.
   Sources: https://arxiv.org/html/2506.09369v1, https://github.com/ant-research/scalelsd,
   https://huggingface.co/cherubicxn/scalelsd (all read 2026-11-14).
2. **Graph readout from junction and centreline heatmaps (idea, maybe).** Zhang 2026, arXiv 2608.25608, code MIT
   (fpvec-lab), no weights released. On CubiCasa5K official test (n=296, 256 px input) a readout with no trained
   parameter beats the autoregressive decoder of the same network by +2.7 wall F1 (95% interval [1.4, 4.0]).
   Verdict: **maybe, idea only**. We cannot reuse the network (CubiCasa5K-trained, no checkpoint), but the recipe
   (peak-pick junctions, chain edges along centreline coverage, rooms = faces of the wall graph) is a classical
   second signal for "plans per sheet" (connected components of the wall graph) that a 12 GB GPU can train on our
   dev boxes. The same paper is the closest precedent for our stage 8: two independent systems fused by a training-free
   union in which an element from the second system is added only if it does not overlap the first and passes an ink
   gate (at least half of the points sampled along it have a dark pixel within a few pixels). That raised wall F1 from
   0.781 to 0.853 (+7.1 points, interval [5.9, 8.3], n=287), while feeding one model's output into the other as input
   gave no gain in three forms (Section 6.3, Table 7, verified). Walls, not counts, and CubiCasa5K-trained.
   Source: https://arxiv.org/html/2608.25608 (full text via headless browser, Tables 2 to 4 and 7).
3. **Keep direct detection as the counter; use modular rules only for structure (decision, not a method).**
   P&ID result above plus SESYD plus SkeySpot (YOLOv8 mAP50 81.1 vs Faster R-CNN 48.6 on scanned electrical plans,
   13 test images, https://arxiv.org/html/2508.10449). Verdict: **try** the detector route first and do not spend
   hours on a vectorise-first counter. Ultralytics YOLO is AGPL, out (record 0006). Permissive
   detector codebases (RT-DETR, D-FINE, DETR, MMDetection, Co-DETR) are in 5t; exact-count baselines to beat are in 5o.
4. **VecFormer, NeurIPS 2025 (skip for raster, maybe for vector PDFs).** PQ 91.1 with layer prior, 88.4 without,
   on FloorPlanCAD; code Apache-2.0; **no weights: the maintainer states in issue #5 that the weight files were lost and will not be retrained**; training 500 epochs on 8 A100; input is true CAD
   primitives. Verdict: **skip** for CubiCasa rasters (no path from pixels to primitives with a loss anyone has
   measured). **Maybe** only if a vector PDF or DXF route needs a learned symbol spotter. Source:
   https://arxiv.org/html/2505.23395v3, https://github.com/WesKwong/VecFormer.
5. **Raster2Seq and FloorplanVLM (pointer to L1, skip for scored runs).** Raster2Seq (arXiv 2602.09016): code MIT,
   weights CC BY-NC 4.0 including a `cubicasa5k` checkpoint (**leak: yes**), so not usable for scored runs.
   FloorplanVLM (arXiv 2602.06507): Qwen2.5-VL-3B, opening F1 0.7333 on its own benchmark, trained on 32 H200, no
   code or weights on the page I read. Verdict: **skip**. Sources below in the table.

## 2. Full table

All rows opened 2026-11-14. "Field" says our field (floor plan / drawing) or the adjacent field. "Leak" = trained on
CubiCasa5K or a repackage. Hours are my estimates, marked (est). "JSON field" is the extraction_v1 part it would
fill.

| # | Method | Field | Year, venue | Code (licence read) | Weights (licence read) | Training data | Metric, benchmark, input | GPU train / run | Hours to first number (est) | JSON field | Leak | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ScaleLSD | generic line detector, not tested on drawings (DeepLSD has been: 5e) | CVPR 2025, arXiv 2506.09369 | MIT (LICENSE file read; copyright holder Nan Xue) | Apache-2.0 (HF card read); v2 checkpoint recommended | synthetic primitives, Wireframe 20k, SA-1B over 10M images (SA-1B is marked "Research purposes only" on Meta's dataset page, full licence text not read) | repeatability within 5 px on YorkUrban 0.725, HPatches 0.367, RDNIM 0.337, COCO 0.666 (Table 1 verbatim); ViT-Base on 512x512 inputs, evaluation fixed at 512x512 (appendix and Table 7, verified); no sAP; no speed or memory number found | not stated | 1 (est) | support for door leaf, window cell, wall pairs (via rules) | no | **try** (small) |
| 2 | DeepLSD | generic line detector | CVPR 2023, arXiv 2212.07766 (read) | MIT (gh api + README) | MIT per README; two checkpoints, Wireframe (indoor) or MegaDepth (generic) | Wireframe, MegaDepth subset | Table 1 reports repeatability and localisation error on HPatches and RDNIM only (column alignment of my copy was not certain, so no number quoted); optional gradient-based refinement; no drawings | about 12 h on one RTX 2080 (stated) | 1 (est) | same as row 1 | no | **maybe** (alternative to row 1) |
| 3 | HAWP / HAWPv3 | wireframe | TPAMI 2023, arXiv 2210.12971 (Table I read in full) | MIT (gh api cherubicxn/hawp) | not read | Wireframe; v3 self-supervised from unlabeled images | HAWP (v1) at 512 px: Wireframe sAP10 66.5, YorkUrban sAP10 28.5, 33 FPS on V100 (LETR Table 1 and M-LSD Table 2; both papers' columns are sAP5, sAP10, sAP15) | not read | 2 (est) | same | unknown | skip (ScaleLSD's paper reports more repeatable lines than HAWPv3 on 3 of 4 sets) |
| 4 | M-LSD | lightweight line detector | AAAI 2022, arXiv 2106.00186 (read) | Apache-2.0 (gh api navervision/mlsd) | not read (README only) | Wireframe | Wireframe sAP10 62.1 at 512 px (sAP5 56.4), 115 FPS V100, 1.5M parameters; tiny 58.0, 164 FPS; YorkUrban sAP10 27.3 (M-LSD Table 2) | small | 1 (est) | same | unknown | maybe (CPU option) |
| 4b | LETR | transformer line detector | ICCV 2021, arXiv 2101.01909 (read) | not checked | not checked | Wireframe, DETR R50/R101 init | Wireframe sAP10 65.2, YorkUrban 29.4, input resized to shortest side 1100 px, 5 FPS, 121M parameters | 4 x Titan RTX | n/a | same | unknown | skip (heavy, slow) |
| 5 | Graph readout + fpvec-lab | our field, wall vectorisation | arXiv 2608.25608, Aug 2026 | MIT (gh api; skv4 converter is CC BY-NC) | none released (open issue #2 asks for weights and inference instructions) | CubiCasa5K train, ResPlan-FP (CC BY 4.0) | wall F1@.05 0.818, @.015 0.787, P 0.885, R 0.775 (n=296, 256 px); openings not emitted by the readout; opening F1 only combined (sequence 0.391, Raster2Seq-based 0.848); no per-class door or window | not stated | 8+ (est: train a heatmap net) | plans (wall-graph components), rooms outlines | **yes** | **maybe**, idea only |
| 6 | Raster2Seq | our field, room polygons | arXiv 2602.09016, 2026 | MIT (README, LICENSE) | CC BY-NC 4.0 (LICENSE-CHECKPOINTS read), HF haopt/Raster2Seq | Structured3D, CubiCasa5K, Raster2Graph | CubiCasa5K test, 256x256 input: Room F1 88.7, Corner 59.4, Angle 37.4, Room-semantic 63.8, Window&Door F1 77.8 (RoomFormer 78.5) (Table 1 verbatim); doors and windows are polygons appended after the rooms, authors call them an area to refine; no counts | 1 x A6000, 1 to 2 days | n/a | rooms, window and door polygons | **yes** (cubicasa5k checkpoint) | skip for scored runs; pointer L1 |
| 7 | FloorplanVLM | our field | arXiv 2602.06507, Feb 2026 | none from the authors. Third-party reimplementation (README read): LoRA on CubiCasa5K, one A100 80GB, no licence file, 4 stars | none from the authors. Third-party HF adapters (card read): trained on CubiCasa5K mirrors, card header apache-2.0 but prose says non-commercial: conflict | Floorplan-2M, Floorplan-HQ-300K (own, design-platform screenshots) | Ext-IoU 0.9252, Room-IoU 0.8920, Room-F1 0.8249, Opening-F1 0.7333 (IoU>0.5) on own FPBench-2K (Table 1 verbatim); coordinates scaled to longest edge 1024; walls carry openings as attributes, no fixtures | 32 x H200, Qwen2.5-VL-3B | n/a | none (no fixture classes) | no for the paper (no public weights); **yes** for every public reproduction | skip |
| 8 | SALI-FP | our field | arXiv 2609.25615, Sep 2026 | none found | none | commercial image model plus LLM judge | pooled door IoU 0.0396 raw / 0.1454 registered vs CubiCasa5K net 0.6181; window 0.0520 / 0.2318 vs 0.7199 (Table C.8, verified in the full text; door/opening row read verbatim) | remote APIs | n/a | none | no | skip (worse than the 2019 net on its own test) |
| 9 | VecFormer | our field, CAD vector | NeurIPS 2025, arXiv 2505.23395 | Apache-2.0 (gh api) | none; maintainer says lost (issue #5) |  FloorPlanCAD (CC BY-NC) | PQ 88.4 no prior, 91.1 with layer prior (Table 1 verbatim); SymPoint-V2 83.2 / 90.1, CADSpotting 88.9 (prior), DPSS 86.2 / 89.5, SymPoint 83.3 | 500 ep, 8 x A100; requirements.txt read 2026-11-14: transformers, spconv-cu118, timm, svgpathtools etc., no AGPL/GPL package listed (transitive deps not checked) | n/a | elements from vector input | no | skip raster; maybe vector |
| 10 | SymPoint | CAD vector | ICLR 2024 | LICENSE.txt read: IDEA, non-commercial research only | OneDrive link (per earlier report) | FloorPlanCAD | PQ 83.3, 35M params, 66 ms (earlier report, verified there) | old stack | n/a | vector input | no | skip (licence) |
| 11 | SymPoint-V2, CADSpotting | CAD vector | 2024 | no licence file in either repo (gh api, root listing) | SymPoint-V2: a checkpoint is shared through a Google Drive link in issue #9; issue #14 (open) asks for its data provenance and licence terms, unanswered. CADSpotting: issue #1 asks where checkpoint and dataset are, unanswered | FloorPlanCAD, LS-CAD | numbers via VecFormer Table 1 | n/a | n/a | vector input | no | skip (no licence = all rights reserved) |
| 11b | DPSS (ArchCAD-400K baseline) | CAD vector plus image | arXiv 2503.22346, 2025 | LICENSE read: ACADEMIC USE ONLY, commercial research prohibited | linked in README, terms not read | ArchCAD-400K (gated on Hugging Face, 40K subset), FloorPlanCAD | FloorPlanCAD PQ 86.2 no prior, 89.5 with prior (VecFormer Table 1); ablation: primitives only 81.7, image features only 80.9, both 83.0, fused 86.2 | not read | n/a | vector input plus rendered image | no | skip (licence; needs primitives) |
| 12 | TextCAD, TempFit, PolarSym | CAD vector | arXiv 2607.12678, 2610.17776, 2608.11793 (Jul to Oct 2026) | none seen | none | FloorPlanCAD (+ IndustryCAD for TempFit) | TextCAD FloorPlanCAD-V2 PQ 91.09 no prior / 92.67 prior vs VecFormer 88.14 / 90.76 (Table 1, baselines reimplemented by the authors), vector CubiCasa5K 96.53 vs 94.58; PolarSym +1.73 PQ over a reproduced SymPoint-V2 (85.42, 2 x V100, 50 epochs); TempFit 500 ep on 8 x RTX 4090 | n/a | n/a | vector input | no | skip: same family, vector only |
| 13 | Deep Vectorization of Technical Drawings | drawing vectorisation, raster in | ECCV 2020, arXiv 2003.05471 | **MPL-2.0** (gh api): not on our allowed list | pretrained on Yandex Disk (link in README), terms not stated | PFP floor plans (commercial site), ABC | raster line IoU: clean plans 86/88, 81 photos and scans of floor plans (about 1300x1000) 79/82 vs 47 for the best baseline; text removed beforehand, no symbol or count metric | not read | 6 (est) | none (primitives have no class) | no | skip (licence, no semantics) |
| 14 | Zernike RAG + GNN | our field, region graph | arXiv 2504.03241, 2025 | none found | none | 400 high-quality CubiCasa5K plans (280/80/40) | avg F1 94.6 to 95.3 clean, 76.6 to 87.6 at 45 degrees, 23.8 to 34.3 on 122 scanned CVC-FP plans; doors 1.9 to 3.0 F1 on scans | not read | n/a | rooms, openings | **yes** | skip; cautionary |
| 15 | Relationformer vs modular | adjacent (P&ID) | IEEE DSAA 2025, arXiv 2411.13929 | repo not located (searches found only unrelated forks) | none | synthetic plus 12 real plans (OPEN100) | see section 0, point 2; patches of a 4500x7000 canvas, one Quadro RTX 8000 | 48 GB | n/a | none (transfer lesson) | no | idea only |
| 16 | SkeySpot | adjacent (electrical plans) | IEEE SMC 2025, arXiv 2508.10449 | not read | not read | 45 scanned plans, 34 classes, 2,450 instances | YOLOv8 mAP50 81.1 (Table II), Faster R-CNN 48.6, test = 13 plans | not read | n/a | elements | no | idea only (AGPL YOLO) |
| 16b | Raster-to-Vector (R2V) | our field, junction CNN + integer programming | ICCV 2017 | MIT (gh api, 2026-11-14); Lua Torch and Python 2.7, a PyTorch port the authors say is unevaluated | Google Drive link, no terms stated; fine-tuned from a human-pose network (MPII) | 870 annotated real-estate plans (LIFULL), raster images not released | Table 1 as in section 0: openings acc/recall 91.9/90.2, icons 84.0/74.6, walls 94.7/91.7; 256x256 | not read | n/a | walls, openings (door and window not separated) | no (own data) | idea only: constraint layer over detections |
| 17 | Rezvanifar et al. | our field, symbols | CVPRW 2020 | not read | not read | SESYD, real plans (tiles of real digital plans) | real-world test (25 plans) mAP 59.0, AP50 89.3, window AP50 75.6; SESYD instance F 97.9 to 99.1; see section 0 | not read | n/a | elements | no | background |
| 18 | Pang et al. | CAD images (raster) | arXiv 2404.10985 (read in full, HTML), 2024; journal version Multimedia Systems 2026 (abstract only, Springer) | not read | not read | own telecom equipment-room images 1700x1200 to 4200x3000 | keypoint F1 0.79 for the method vs 0.76 soft-argmax and 0.78 RLE (Table II); local offset lifts the 15-point average F1 0.77 to 0.79 (Table III); region symbols by YOLOX F1 0.95-1.00 (Table I); verified from arXiv HTML full text; no licence or weights stated in the paper | not read | n/a | none | no | idea only (sub-pixel keypoint heatmaps) |
| 19 | GLSP | our field, line segments, wall/door/window classes | 2023, arXiv 2303.03851 (read, Tables 2-4) | none found | none | proprietary scanned-plan corpus | verified from arXiv HTML 2026-11-14 (Table 2, class-agnostic msAP8/16/32 on own test set of 1,500 plans, 1080x720 px images): HAWP-M 55.5/57.1/57.5; modified HAWP (M*) 71.1/73.3/74.3; M* + GNN module 85.9/91.5/92.5; GLSP end-to-end 90.3/93.6/94.2. Ablation: junction accuracy drives line accuracy. Not CubiCasa5K, 268k proprietary annotated plans (Chinese urban residential), so no leak but also no usable data | not read | n/a | wall, door, window segments | no | background |
| 20 | ADLA | generic LSD | arXiv 2508.19742, 2025 | not read | not applicable (classical) | none | benchmarks LSD, DeepLSD, HAWPv2/v3, ScaleLSD, DT-LSD, LINEA on YorkUrban-LineSegment and ShanghaiTech only | CPU | n/a | none | no | background |

Note on row 11b: the image pathway samples rendered-image features at each primitive's centre, so it still needs the
primitive set; but image features alone score about as well as primitive geometry alone (80.9 vs 81.7 PQ), which is the
only measurement I found that says pixels carry most of the signal a symbol spotter uses.

## 2b. Permissive classical primitives, licences settled (extends the earlier vectorise report)

All read 2026-11-14 from the source files:
- OpenCV and opencv_contrib repositories: Apache-2.0 (gh api).
- `createLineSegmentDetector` (OpenCV 4.x `imgproc/src/lsd.cpp`): the file carries the OpenCV Foundation 2013 BSD-style
  header and no GPL or AGPL text, so the earlier "UNVERIFIED" is closed for the licence header; whether the
  implementation is clean-room I cannot verify from the file.
- `cv2.ximgproc.EdgeDrawing` (opencv_contrib, ED, EDLines, EDPF, EDCircles): `detectLines()` returns segments,
  `detectEllipses()` returns circles (centre, perimeter) and ellipses (centre, axes, angle). This is the permissive
  circle and ellipse detector the earlier report was looking for. Whether it returns *partial* arcs, which is what a
  quarter-circle door swing is, I did not verify; the API text speaks of circles and ellipses only.
- No accuracy number for any of these on floor plans or drawings was found in 2025 to 2026 work. In-house measurement
  stays the only data point (Hough arcs 2/40 doors exact).

## 3. What breaks on our images, per candidate

- **ScaleLSD / DeepLSD / M-LSD (rows 1 to 4).** Trained on photographs; none of the papers I read tests line art,
  sketches, scans or plans. Our images: median longest side 855 px, symbols 5 to 20 px. At 512 px input (reported) a
  855 px sheet is downscaled by about 1.7, so a 10 px door becomes about 6 px and a 1 px stroke may vanish; the README
  default `--threshold 10` is a pixel distance tuned on photos. Door swings are arcs and the paper's limitations section says curve structures are not explicitly modelled
  (verified), though it can approximate curves as polylines. Hatched or double-line walls give parallel pairs rather than one line. Rotation by 90
  and 180 degrees is harmless for a line detector only if it is rotation-equivariant; I did not find a statement.
  Cheapest test: run on 100 dev images at native and 2x upscaled size, count door-leaf-like segments against the
  exported boxes.
- **Graph readout (row 5).** 256 px network input is far below our symbol sizes (a 10 px symbol is 3 px); the paper
  itself says vision encoders downsample thin walls away. Our need is plan splitting, which is coarse, so it is the
  one use where 256 px may be enough. Trained on CubiCasa5K, so we would retrain from our dev split.
- **VecFormer and the whole vector family (rows 9 to 12).** They need primitives with types, and 500-epoch training on
  eight A100s. Rasters give no primitives; "vectorise first" would put row 1 or Deep Vectorization in front, and
  nobody has measured the loss of that chain. FloorPlanCAD drawings are clean CAD; the best methods lean on layer
  priors (Stuff-PQ falls by 31.5 points for SymPoint-V2 without prior, VecFormer Table 1 text).
- **Deep Vectorization (row 13).** Its cleaning stage was trained to remove text and background; ours must keep
  glyphs (labels carry room type). Output has no class. MPL-2.0 is file-level copyleft, not on our list.
- **Region-graph / GNN (row 14).** Failed on scans (above); Finnish labels and furniture glyphs are "clutter" to it.

## 4. From other fields: the transfer notes (one line each; full treatment is lit-vector-b)

- **Door versus window is the easy half (our field, 2608.25608 section 6.1, verified).** On CubiCasa5K test, reading
  openings from a heatmap gives opening F1 0.799 when door and window are not told apart and 0.644 with a simple
  family heuristic; a separate 200K-parameter door/window head reaches 0.988 family accuracy. So finding the opening is
  the hard part (location F1 about 0.8 with their matcher) and the door-or-window label can be a small second head.
  Their matcher is stricter than the paper's other tables and is not comparable with ours; they report no counts.

- **P&ID digitisation (adjacent, row 15).** Role of our object: a valve symbol is our door. What transfers: a
  patched-image graph model (nodes = symbols, edges = connections) beats the modular route on connectivity; the
  modular route is better on symbol classification. What breaks: their symbols are large (patching at 4500x7000 with
  overlap and merge), ours are 5 to 20 px; their loss is graph AP, ours is exact count. Idea only, no weights.
- **Electrical layout plans (row 16).** Same shape (small repeated symbols on scanned plans, with a count report in
  the app). What breaks: 13 test images, class imbalance, AGPL detector.
- **Constraint validators that trigger a local re-read (BlueprintAgent, arXiv 2609.07362).** 300 real scanned sheets,
  beam F1 0.994 vs 0.820 for a fixed pipeline vs 0.301 for one MLLM prompt; validators over topology call a model to
  re-read only the conflicting region. Role: stage-8 conflicts. What breaks: commercial MLLM backbone, Chinese
  structural drawings. Pointer to L7 and L10, not dug into.
- **Agentic structural plan reader (arXiv 2608.17237).** Deterministic ink scan proposes candidates and a judge model
  accepts or rejects; the same shape as our stage 8. Uses a commercial LLM API; pointer to L10.

- **Staff-line removal (sheet music), the one adjacent field I read for the "separate symbols from the lines they sit
  on" shape.** Role of our object: a note head touching a staff line is a window or door cell touching a wall line.
  ICDAR/GREC 2013 set, F-measure on symbol pixels (GAN paper arXiv 1801.07141, CNN paper 1709.06476, both read): on
  binary scores the best classical method (LRDE) reaches 97.14 and learned pixel classifiers 97.9 to 99.3; on
  grayscale scores the classical methods fall to 82.85 (LRDE) and 42.09 (INESC) while learned ones keep 98.9 to 99.1.
  So classical separation is competitive only when the image is clean and binary, which is not our mix of scans and
  photos. What breaks for us: (1) in a floor plan the window is itself drawn as parallel lines inside the wall, so
  erasing "the lines" would erase the symbol; separation would have to be wall versus symbol, not line versus
  non-line; (2) their pages are clean 2013 scans with synthetic distortion, no phone photos; (3) the metric is pixel
  F-measure, not a count. Verdict: idea only, no code or weights read.

## 5. Looked for and did not find

- Any floor-plan paper reporting per-image exact counts of doors, windows, toilets or sinks from a vectorised route.
- (CORRECTED 2026-11-14, see section 5e: one test of pretrained DeepLSD on scanned electrical plans exists.) Any test of ScaleLSD, DeepLSD, HAWP, M-LSD or LETR-style detectors on line drawings, scans or plans. ADLA (2025)
  benchmarks six deep detectors on YorkUrban and ShanghaiTech only. GLSP (2023) is the only floor-plan line-segment
  parser and it uses a proprietary corpus, no code.
- A 2025 to 2026 paper that builds on Deep Vectorization for floor plans. Citation walk (Semantic Scholar, 2025 and
  later): it is cited by art, sketch and SVG vectorisation work and by an engineering-drawing dimension classifier.
- A 2025 to 2026 line-segment or wireframe detector aimed at drawings. arXiv title searches (line segment detection,
  wireframe parsing, sorted by date) list ScaleLSD, ADLA, DT-LSD, a matched-prediction LETR variant, Co-PLNet and
  hardware ports (NPU, ASIC, event camera): all natural images.
- A raster-input variant of SymPoint, SymPoint-V2, CADSpotting or VecFormer, or any chain "vectorise raster then
  spot symbols" with a measured loss. The vector papers state they avoid rasterisation.
- ICDAR 2025 or GREC 2025 papers on floor-plan symbols: the search returned none; the Springer proceedings were not
  searched page by page.
- Weights for VecFormer (lost, per the maintainer), fpvec-lab, FloorplanVLM, SALI-FP.
- Any GitHub issue on ScaleLSD, DeepLSD, HAWP or VecFormer from someone running them on floor plans, scans or drawings
  (keyword searches floor, drawing, sketch, CAD, scan, document): none. DeepLSD #20 asks about facade orthophotos only.
- A raster floor-plan or drawing-vectorisation paper in the ICCV 2025, WACV 2026 or CVPR 2026 main programmes (title
  lists grepped): none. Floor-plan titles there are localisation (FloVerse, semantic-ray localisation, PALMS+),
  generation (vector floorplan markup, CG-Floor, HouseCrafter) and an MLLM tokenisation paper. Closest vectorisation
  papers are adjacent: HoliTracer (ICCV 2025, remote sensing), ACPV-Net (CVPR 2026, aerial maps).
- The 2025 Buildings paper on Hough-arc door hypotheses (MDPI refused the page, also in the headless browser) and the
  2025 Automation in Construction multimodal symbol-spotting paper (ScienceDirect refused). Not read, not cited as
  evidence.

## 6. Citation walks forward (what I found there)

Via the Semantic Scholar API, 2026-11-14, titles and years only, then opened where marked:
- From VecFormer (2505.23395): TempFit 2610.17776 (read), TextCAD 2607.12678 (read), a 2026 rectangle symbol spotting
  paper for CAD images (same group as row 18, not opened), a 2026 Scan-to-BIM review (not opened).
- From SymPoint (2401.10556): PolarSym 2608.11793 (read), CAGE 2509.15459 (NeurIPS 2025; per snippet it works from
  point-cloud density maps, so not raster plans), ArchCAD-400K, TextCAD, a 2026 paper on defective CAD drawings (not
  found), a 2026 structural-framing-plan paper (read, skimmed).
- From ScaleLSD (2506.09369): ADLA 2508.19742 (read), BT-LSD (no page found), SweepLSD 2608.22086 (FPGA, not opened),
  point-line local features 2608.19894 (not opened). None is about drawings.
- OpenAlex (used because Semantic Scholar rate-limits): ScaleLSD has only two 2025+ citing works, both 3D line
  mapping or local features. VecFormer is cited by the journal versions of CADSpotting and the rectangle-symbol paper,
  TempFit, and a 2026 survey, "Vision foundation models for engineering document intelligence and manufacturing
  inspection" (Artificial Intelligence Review, abstract only, paywalled). The survey says natural-image models must be
  adapted to thin-line, symbol-dense documents and that no standard multi-format engineering-drawing benchmark exists;
  it covers 94 studies, I did not read them. SymPoint is also cited by VectorGraphNET (2025) and a CLIP-based
  floor-plan recognition paper (ASCE 2025, not opened).
- From CubiCasa5K (1904.01920), 2025 and later, floor-plan titles: Raster2Seq, FloorplanVLM, 2608.25608, 2504.03241,
  2609.25615 (all read), Carrara et al. 2026, "Why floor plan object detection breaks under real scans" (located via the Semantic Scholar
  record and the TUM portal, abstract read; see section 7 item 5), and not opened: ModRes, FPP-Former, FloorPlanFormer.
- From Deep Vectorization and GLSP: see section 5.

## 7. Open questions and missing tools

Questions for the orchestrator:
1. Is a 1-hour ScaleLSD experiment (row 1) worth a GPU slot? It would settle whether a line detector sees door leaves
   at our sizes; I could not run it (read-only, no downloads).
2. For the "plans per sheet" number, does anyone own the wall-mask connected-component idea (00-context.md section 3)?
   Row 5 is the only published precedent I found, and it is for walls, not splitting sheets.
3. HAWP (Table I) and M-LSD (Table 2) papers were read late in the session; the DeepLSD paper itself was not, only its repo,
   its use in the electrical-plan paper (5e) and the ADLA comparison (5g). Hand to lit-vector-c if row 1 fails.
4. ScaleLSD's weights card says Apache-2.0, but its pseudo-labels come from SA-1B, which Meta's page marks "Research purposes only".
   Whether that restriction reaches the weights is a legal question I cannot settle; if the weights would ship, ask
   whoever owns record 0006. The paper also reports a Wireframe-only variant (structural
   repeatability 0.697 / 0.337 / 0.295 / 0.636 on the four sets vs 0.725 / 0.367 / 0.337 / 0.666 for the SA-1B one), which would avoid the
   SA-1B question, but the model card lists only SA-1B checkpoints. Local use for a second counter that is not shipped is the safe reading (record 0003 treats
   non-commercial weights as local-only).
5. Found by the CubiCasa5K citation walk, belongs to L2 and L9, abstract read only (the paper is behind Elsevier):
   Carrara, Nousias, Borrmann, Automation in Construction 191 (2026) 107193, "Why floor plan object detection breaks
   under real scans". On CubiCasa5K with paired CAD-derived and scanned renderings of identical layouts, RT-DETR AP75 and
   AP@0.85 fall much more than AP50; changed line depiction (thickness, blur) inside object boxes is the main cause,
   scanned background a smaller one. My inference, not the paper's: counting needs only a box that is roughly right
   (IoU 0.5), so scan shift may cost counts less than it costs strict localisation. Its dataset (ScanShift, Zenodo)
   and checkpoints are CubiCasa5K-trained, so leak: yes for the checkpoints. Someone in L2 or L9 should read it in full.
6. For other scopes: title-block detection on building drawings, Lombardi et al., EC3 2025, arXiv 2504.08645, abstract
   read only, claims to beat existing methods on noisy historical drawings (L9, which listed title-block work as not
   found); Text-Enhanced symbol spotting arXiv 2510.11091 (L5, not read); Raster2Seq and FloorplanVLM (L1), AECV-style and GDP.pdf benchmark (arXiv 2607.11192, notes
   models "miscount floor-plan symbols") (L7, L12), constraint validators with local re-reads (L10), text on CAD
   plans (L5), rotation invariance (L9), ResPlan-FP (L8, CC BY 4.0 data, MIT code).

Tools: no arXiv MCP server. WebSearch gives summaries only (not counted as reads). The web-fetch agent truncates
long arXiv HTML at about 40k characters and returned binary for a NeurIPS PDF; the headless browser
(`.agents/pw/pwfetch`) returned full text for every arXiv HTML page and was used for all tables quoted above. MDPI and
ScienceDirect blocked both. Semantic Scholar rate-limits intermittently (one burst failed, retries worked).

## 5b. Retry of "door swing arc in raster plans" (2026-11-14, search results only, not read)
WebSearch with new terms found no 2025-2026 paper on swing-arc detection in scanned raster plans with exact counts. Leads seen only as titles/snippets (reported, unread): arXiv 2508.07714 (DoorDet; now READ in full, see below), a 2025 arXiv paper on facility enumeration using door detection plus an LLM, and a forum heuristic (arc centre plus endpoint gives opening direction; not validated). Gap stays open.

DoorDet (arXiv 2508.07714, Aug 2025, read in full via HTML 2026-11-14, verified): door-type dataset built from CubiCasa5K SVGs, so any checkpoint trained on it carries the CubiCasa5K leak flag. Single-class Co-DETR on combined door sets: mAP 0.403, mAP@50 0.793 (Table 3): doors localise at IoU 0.5 but not tightly. Multi-class (10 door types by room context) Co-DETR all-class mAP 0.831 / mAP@50 0.926 (Table 4), but boxes are algorithmically generated, so mAP is optimistic. What breaks on our images: type labels depend on room names (Finnish room labels in CubiCasa5K), and the data are rendered vector plans, not scans. Use: evidence that learned door detectors reach about 0.79 mAP@50 across mixed sources; not a counter we can adopt (no weights/licence read).

fpvec-lab requirements.txt (gh api Cyprinus12138/fpvec-lab, read 2026-11-14, verified): numpy, shapely, scipy, scikit-image, opencv-python-headless, pillow, networkx, skia-python, svgpathtools, cairosvg, sknw, huggingface_hub, pytest. No AGPL/GPL package by name (transitive not checked), no torch listed: matches "no trained net released".

## 5c. Round 2 (direct detector numbers on raster plans; read 2026-11-14)
FloorYOLO (Frontiers in AI 2026, CC BY, full text via Europe PMC; verified): YOLOv8n plus channel attention. SESYD (1000 synthetic plans, 16 symbol classes): mAP@0.5 0.9950, mAP@0.5:0.95 0.9794; window1/window2 are the weakest classes. CVC-FP (real scanned plans): mAP@0.5 0.8241 vs baseline 0.8116. The text is inconsistent on windows: it says the baseline has "0% recall" for the window class (Table 9) and also 176/234 window instances misclassified, 58 missed, vs 168/234 (71.8%) correct for FloorYOLO; treat the per-class window figure as reported, not clean. Thin windows are the failure; the paper's own caveat says SESYD is synthetic and not representative of scans. No code or licence read for the repo (not looked for). What breaks on ours: classes are symbol types, not gap-in-wall counts; small datasets.
Answer to round-2 question: no 2024-2026 paper found that scores a vectorise-then-rules or wall-graph route and a direct detector on the same scanned plans for doors and windows (searches: web extended mode, 2026-11-14). The closest same-data pair stays R2V 2017 (constraint layer lifts opening accuracy 67.9 to 91.9) plus 2608.25608 (wall graph readout, openings not emitted). SALI-FP 2609.25615 re-checked: already row-listed; it compares CubiCasa5K and Raster2Seq weights on one protocol, not detector vs vectorise for openings.
Citation walks: OpenAlex free budget exhausted (HTTP 429, resets midnight UTC; a key would need the user's email, not sent) and Semantic Scholar 429 at 2026-11-14 00:5x; forward walks stay at what section 6 already holds.

## 5d. Round 4 (repos; gh api, read 2026-11-14, verified)
- DeepLSD (cvg/DeepLSD, MIT): requirements.txt ends with a local `./third_party/pytlsd` install, so the same AGPL-LSD-in-pytlsd concern as ScaleLSD applies to the default install path (installs failed on pytlsd in issues #30, #41; the pytlsd licence file itself was not re-read this round: check before use). Open issues: #51 own dataset, #43 line_refinement build, #26 and #25 custom data/training. Nothing about scans or thin lines; #32 asks for long lines only (answered via the conf threshold, so short door-arc fragments are a tuning question).
- ScaleLSD (ant-research/ScaleLSD): only 4 issues, all closed (training script, typo); no issue about scans or thin lines, so no field evidence either way.
- HAWP (cherubicxn/hawp, MIT): 30+ open issues, mostly training on own data unstable (#42, #50, #37, #56) and ONNX export (#34, #30, #55); #39 asks about inference on large images (open): plans at print size would need tiling.
- VecFormer and fpvec-lab: see rows 9 and 5 (requirements read, no AGPL/GPL by name).
Net: no repo has a reported scan or thin-line result; thin-line behaviour on our drawings stays an experiment, not a literature fact.

## 5e. Gap retry hit: DeepLSD on scanned plans (read in full 2026-11-14, PDF from a university repository record, verified; publication date not confirmed)
Urbieta et al., "AI-driven extraction of electrical circuits from floorplans for BIM" (LIFIA / CONICET; 47 pages): scanned electrical plans 6000+ px wide, YOLOv8/11 and Cascade Mask R-CNN for symbols, and pretrained DeepLSD with no fine-tuning for cable traces after grayscale/colour pre-filtering and a feature-aware line filter (over-detections and lines from annotated components need removing). Table 5 on 7 plans, global: length ratio 1.084, IoU(buf) 0.89, precision 0.94, recall 0.95, F1 0.94 (plan-level F1 0.92-0.96). Circuit assembly on three plans: symbol counts and circuit ids mostly right, with one missed switch (-1) and one circuit not generated. Takeaways for us: (a) a learned line detector (pretrained, off the shelf) works on scanned plans at full resolution, which is the only such evidence found; (b) it needed colour/grayscale pre-filtering and post-filtering by detected objects: ink-gate idea again; (c) cables are long thin lines, not door arcs, so it does not show arc or gap-in-wall counting. Code/licence/dataset (IPVBA-ELEC, licence stated in paper) not checked. DeepLSD itself: MIT code, pytlsd/AGPL install flag (5d). Upgrades the ScaleLSD/DeepLSD experiment from "idea" to "has one positive precedent on scans".
5f. ICDAR/GREC 2025 symbol-spotting retry (web search, new terms): still none; and a search for deep line detectors on engineering drawings only returned the above, the IPOL 2024 review (supervised deep detectors vary strongly with end parameters; natural-image data only) and ScaleLSD itself.

GLSP read in full (2026-11-14): shows a wall/door/window line-segment parser reaching msAP32 94.2 on a very large private plan corpus; a graph module on a HAWP baseline adds about 18 points msAP32, i.e. the typed-line route needs data we do not have. No code released that I could find (row 19). Per-class (wall, door, window) sAP is only in its supplementary material, not read.

## 5g. Round 1 rereads (2026-11-14, verified from arXiv HTML)
- ADLA (2508.19742, row 20): Table 4, YorkUrban-LineSegment (generic lines, heatmap protocol AP/AR/F): LSD F 0.8125, Linelet 0.8511, DeepLSD 0.8226 (AP 0.8818, AR 0.7708), HAWPv2 (conf .4) F 0.7525, HAWPv3 (conf .1) F 0.5636, ScaleLSD (lambda 5) AP 0.8946, AR 0.5389, F 0.6726; ADLA reaches F 0.8665. Read: at default thresholds ScaleLSD and HAWPv3 are high-precision, LOW-recall generic detectors; for counting we want recall, so plan to lower its threshold and filter by ink and geometry. CPU-only ADLA aggregation 31.6 ms/image after an edge-map net. No licence read.
- 2608.17237 (agentic structural framing plan reader): deterministic ink/geometry rules plus a model judge on a synthetic 50-drawing held-out set (PD-50-T): openings recall 1.000, precision 0.964; walls and braces 1.000/1.000; columns 0.922/0.997; beams 0.886/0.990. Synthetic generator drawings only, openings matched by centroid proximity, so it shows the rule-first route works on clean vector-exported drawings, not on scans; the paper accepts scanned input but the numbers are not on scans.
Still reported only: HAWP paper tables (taken from LETR and M-LSD tables), Pang journal version, Carrara et al. 2026 (paywalled).

## 5h. Round 3 (forward walks without the APIs; web search only, 2026-11-14)
Two extended searches for papers building on ScaleLSD or R2V for floor plans or drawings: no ScaleLSD-on-drawings paper; only title-level hits SweepLSD (arXiv 2608.22086, FPGA line detector, natural-image focus, unread), CADSpotting at ICCVM 2026 (LS-CAD, 45 annotated plans, already row 11) and Raster2Seq 2602.09016 (row listed; windows and doors appended at the sequence end work better than inserted inline). No YOLO-vs-R2V comparison on the same plans exists in the hits. Forward walks therefore stay negative: nobody has published ScaleLSD or DeepLSD for door/window counting.

## 5i. BlueprintAgent re-read (arXiv 2609.07362, full HTML, 2026-11-14, verified; CC BY 4.0 paper)
Table 1 (300 sheets, 102 floors, 20 projects, single run, macro): MLLM zero-shot beam F1 0.301 / column F1 0.537; fixed OCR+CV pipeline 0.820 / 0.920; agent loop without constraint feedback 0.768 / 0.959; full agent with validators 0.994 / 1.000. The earlier line (0.994 vs 0.820 vs 0.301) stands. New detail: the gain comes from validators that trigger entity-level re-reads, not from looping (B4 is no better than B3); applying the same validators only after the run ends gives a smaller gain (B6, precision 0.90 on the subset). Repeats on the 5-project subset: B4 0.789 +- 0.012, B5 0.961 +- 0.007 (GPT-5.4). Domain is structural beams and columns, not doors/windows; needs a commercial multimodal model per sheet; weights/code not read. Use: supports "conflict check then local re-read" for stage 8, not a counter.

## 5j. HAWP paper re-read (arXiv 2210.12971, full HTML, 2026-11-14, verified)
Table I (512 px, Wireframe sAP5/sAP10/sAP15; YorkUrban sAP10): HAWPv1 62.5/66.5/68.2 (York 28.5), 29.5 FPS; HAWPv2 65.7/69.7/71.3 (York 31.2), 40.8 FPS on one V100; L-CNN 59.7/63.6/65.3; F-Clip 62.6/66.8/68.7; LETR-R101 59.2/65.2/67.7. This matches the HAWP v1 sAP10 66.5 in row 3 (no correction needed); row 3 now has v2 69.7 as the better trained-on-Wireframe number. All natural-image / indoor-photo benchmarks, none on drawings.

## 8. Sources-read tally (2026-11-14)
Reading log has 133 lines (about 75 distinct sources opened, the rest are searches and gh api checks). Target >=15 read: met. Target >=6 from 2025-2026: met (ScaleLSD, VecFormer, DoorDet, ADLA, FloorYOLO, SALI-FP, 2608.25608, 2608.17237, BlueprintAgent, Raster2Seq, electrical-plan DeepLSD paper, SkeySpot). Still reported only (abstract or table-of-others): Pang journal version, Carrara et al. 2026 (paywalled), Buildings/Automation in Construction/CPN-Floor pages (blocked), Text-Enhanced 2510.11091 (L5). Forward citation walks: OpenAlex and Semantic Scholar both rate-limited this session late; section 6 has the earlier walk, 5h the web-search substitute.

## 5k. Zero-shot transfer evidence (PCP-Net, Biomimetics 2026, CC BY, Europe PMC full text, read 2026-11-14; verified numbers, table headers partly garbled in the XML so I use only the last column, read as mean IoU over overlapping room classes)
Semantic segmentation, trained on CubiCasa5K only (so CubiCasa5K leak flag: yes for anything trained this way), tested zero-shot: CVC-FP (scanned plans) 0.72 vs TF2DeepFloorplan 0.62, DeepLabV3+ 0.46, PSPNet 0.40; R3D 0.74; ROBIN 0.88; in-domain CubiCasa5K mIoU 71.3 %. No window/door count metric, no code or weights stated, classes are rooms/icons. Use: shows a CubiCasa5K-trained model loses little on CVC-FP room masks but nothing about openings; limitation section itself says blurred scans and hand sketches may break the clean-line assumption. Not a counter.
Searches for the 2025 Buildings (MDPI) Hough-arc door paper via Crossref and Europe PMC: not found under those keywords; stays "not read".

## 5l. DeepLSD licence trap, verified (gh api, 2026-11-14)
cvg/DeepLSD pulls `third_party/pytlsd` as a git submodule (`.gitmodules`, github.com/iago-suarez/pytlsd). That repo reports MIT, but `src/lsd.cpp` carries the GNU Affero GPL header of the original LSD (first lines read). DeepLSD's method feeds its predicted gradient into a classical LSD, so the default pipeline links AGPL code. Same trap as ScaleLSD's requirements, and it matters for the electrical-plan precedent (5e): that group used DeepLSD pretrained. For a hackathon prototype run internally it is a flag, not a blocker; AGPL network-use terms apply if we expose it as a service. Escape routes not tested: DeepLSD's learned-only line-field readout, or ScaleLSD without pytlsd (already in D3), or OpenCV EdgeDrawing (Apache-2.0, row 2b).

5m. Carrara et al. 2026 / ScanShift: a further web search for a non-paywalled copy found nothing (only unrelated 3D-scan floorplan papers). Stays abstract-only, pointer L2/L9.

5n. EdgeDrawing arcs (header read, opencv_contrib 4.x `edge_drawing.hpp`, 2026-11-14, verified): `detectEllipses` is documented to output circles (centre, perimeter) and ellipses (centre, axes, angle) only; no partial-arc output is documented. A quarter-circle door swing therefore is not returned as such; it would only appear if the arc closes into an ellipse candidate. Treat EdgeDrawing as a line source (`detectLines`) and keep arcs to our own fitting on line chains. Closes the open question in the handoff.

## 5o. Exact-count benchmarks for doors and windows (read in full 2026-11-14, verified)
- AECV-Bench (arXiv 2601.04819, Jan 2026; repo AECFoundry/AECV-Bench, no licence file reported by gh api, data/results folders present, not downloaded): 120 high-quality floor plans, per-field EXACT-MATCH accuracy of counts (the fraction of plans where the predicted count equals the truth). Table 1, door / window: Gemini 3 Pro 0.39 / 0.34; GPT-5.2 0.28 / 0.27; Claude Opus 4.5 0.16 / 0.16; Grok 4.1 Fast 0.09 / 0.17; open models 0.03-0.12 (GLM-4.6V window 0.03). Bedrooms and toilets 0.6-0.9, so text-tagged items are easy and symbol items (doors, windows) are not. Counting rules in its prompt: only swing doors drawn with an arc, each leaf counts (double leaf = 2), sliding and glazed openings are windows, adjacent windows without a gap are ONE group, tiny toilet windows count. These rules match the ambiguity we already have. Use: the baseline a direct-MLLM counter must beat is about 0.3-0.4 exact on doors/windows; no vector route is in it.
- Automated facility enumeration (arXiv 2509.17283, Sep 2025): a Co-DETR door detector (trained on two public door sets, 1,047 and 837 training plans) plus GPT-5 chain-of-thought; exact count correct per image. Toilet counts, GPT-5 alone vs door-detector + CoT: CubiCasa5K 85.6 vs 87.6, FloorPlanCAD 79.3 vs 85.7, SESYD 68.8 vs 95.8, ROBIN 64.6 vs 85.4, CVC-FP (scans) 40.0 vs 86.7, MLSTRUCT-FP 50.0 vs 66.7; kitchens 96.9 vs 99.0 on CubiCasa5K. Evidence that an intermediate detector (doors) lifts exact counts, with the biggest gain on the scanned set. The detector is learned and CubiCasa5K-adjacent data may be in its training sets (leak flag: possible), the LLM is commercial; counts are of rooms (toilets, kitchens) not door symbols themselves.
Both are L-scope-adjacent (L1/L7); recorded here because they are the only exact-count numbers for doors and windows I found.

5p. Compliance-check framework (arXiv 2607.00015, CC BY 4.0, 2026, full text skimmed 2026-11-14): segmentation + object detection -> polygons -> attributed graph (rooms as nodes, typed edges) -> LLM-parsed regulation rules -> rule engine. A system paper with no door/window accuracy numbers that I found; it validates the "detect, then vectorise to a graph, then rules" shape but gives no head-to-head. Reported, not verified beyond structure.

5q. arXiv API title/abstract search (2026-11-14, no rate limit): abs "line segment" AND "floor plan", newest first, returns only COMPASS (2604.25388, floor-plan visual localisation, not parsing), a camera-calibration paper and older work (GLSP 2023, FloorGenT 2022). Confirms again that no 2025-2026 abstract pairs a line-segment detector with floor-plan parsing. Abstract-only search cannot see papers that merely cite ScaleLSD.

5r. Two more 2025 hits from the arXiv API sweep (2026-11-14): CAGE (2509.15459, CC BY 4.0, read in full): edge-based floorplan reconstruction from point-cloud density maps on Structured3D and SceneCAD, Room F1 99.2 % there; the input is not a drawing, so excluded (no transfer). Sketch2BIM (2510.20838, abstract plus method skimmed from the PDF): hand-drawn plans to BIM with a multimodal LLM and human feedback on only 10 plans; openings "captured with high reliability in the initial pass", walls about 83 % first pass, all precision/recall/F1 above 0.83 after feedback; MLLM-only and human-in-the-loop, so weak evidence for our case (tiny n, no scans).

## 5s. P&ID: recovered graph beats image-only reading (arXiv 2609.05880, Oct 2026, paper CC BY-NC-ND 4.0, full HTML read 2026-11-14; verified numbers on its own synthetic-plus-Digitize-PID sets)
Their stack: YOLO11s symbol detector on tiles, a line U-Net, OCR, a recovered process graph; three small VLMs answer topology questions either from the image only or with the graph grounding: pooled exact-match accuracy 40.1 / 41.3 / 36.7 % image-only vs 76.0 / 75.1 / 74.3 % graph-grounded (+33.8 to +37.6 pp). Headline graph score 0.801 for matched nodes and exact edges. Meaning for us: giving a model or rule layer an explicit recovered structure beats asking it to read pixels, which is the stage-8 conflict-check idea again; same direction as AECV-Bench (5o): direct MLLM door/window counting is weak. Caveat: P&ID has clean line topology; our door/window symbols are not graph edges.
Licence flag (verified with gh api 2026-11-14): the detector family used here and in most detectors in this report, ultralytics YOLOv8/YOLO11, is AGPL-3.0 (LICENSE read, spdx AGPL-3.0). Using it as the counter has the same network-service consequence as pytlsd (5l); alternatives are permissively licensed detectors (DETR family, RT-DETR Apache-2.0 not re-checked here).
Also seen, title only: 2607.19568 (P&ID to process graphs with a multimodal model), not read.

5t. Permissive direct-detector codebases (gh api spdx, 2026-11-14, code licence only; weights and pretraining data not read): RT-DETR Apache-2.0, D-FINE Apache-2.0, DETR Apache-2.0, MMDetection Apache-2.0, Co-DETR (used by DoorDet) MIT. So a direct door/window detector can avoid the ultralytics AGPL (5s). Pretrained weights on COCO/Objects365 carry their own terms; check before use.

5u. ScaleLSD usage facts (README read via gh api, 2026-11-14, verified): Python 3.10, torch 2.5.1 (CUDA 12.1 wheels in the example), CLI `python -m predictor.predict --img <path or folder> --ckpt ... --ext png|pdf|json --threshold T --junction-hm H --num-junctions N`; JSON output is available, so lowering `--threshold` (recall, see 5g) and `--junction-hm` is the knob to turn in the experiment. `--use_lsd` switches to an "LSD rectifier" path; code search in the repo shows pytlsd appears only in requirements.txt and line_matching/wireframe.py, so this flag is not shown to use it (what the rectifier imports was not traced). README says nothing about input size or tiling for large images; plans at 3000+ px would need tiling by us (HAWP issue #39 asks the same). CPU-only operation not documented.

5v. SynthPID (arXiv 2604.16513, Apr 2026, CC BY 4.0, full HTML read 2026-11-14, verified; transfer note, not floor plans): training on 665 synthetic P&IDs whose topology is seeded from 12 real sheets (perturb then re-render) gives 63.8 % edge mAP on the real test set with zero real training sheets, within about 6-8 points of training on real data (oracle) and 18 points above a modular baseline that used 60 real sheets; random template scattering instead gave about 30 points less. Patch-based detection because symbols are too small at full-image scale. Meaning for us if training data is the limit: synthetic drawings must copy the real structure (real seeds), not scatter symbols; patching/tiling is the norm for small symbols on big sheets. What breaks: P&ID topology is graph edges, our targets are symbols in walls; the generator is for P&IDs.

5w. arXiv title sweep for 2026 "floor plan" papers (2026-11-14, API, 60 newest per query): most are generation, localisation or chip floorplanning (not our task). Parsing-relevant items not yet in this report: 
- 2608.14317 (CC BY-SA 4.0, read): Mask R-CNN on lighting symbols in 2D plans, bbox mAP 0.7596, segm mAP 0.7111, mAP@50 0.985 (bbox) / mAP@75 0.922 (segm); a direct detector counts small plan symbols well at IoU 0.5, tighter at higher IoU; one class family, own data; no vector route.
- 2604.23970 (skimmed, see 5x), 2611.00097 (Pano2BIM, VLM agent for BIM from a plan), 2610.17178 (ModRes, ResPlan modification for graph ML): titles only, not read.
Nothing in the sweep pairs a vectorised route with a detector on the same raster plans.

5x. 2604.23970 skimmed (2026-11-14): a fine-tuned YOLOv12 (AGPL family, 5s) detects doors, walls, windows; a graph builder links each door to its two nearest rooms; a self-critic checks BFS connectivity and door-edge consistency and retries. No door/window accuracy table found in the text; shows the same detect-then-structure-check shape (reported only).

5y. DeepLSD paper (arXiv 2212.07766, CVPR 2023, PDF read with pypdf 2026-11-14, text partly truncated by the extractor; verified for the statements below): its abstract says traditional detectors are fast and accurate but not robust to noise and hard conditions, learned ones are more repeatable and robust but less accurate and biased toward wireframe lines (trained on the one Wireframe set, they generalise poorly); DeepLSD predicts a line attraction field and angle field, turns them into a surrogate gradient image and runs a classical LSD on it (that is why pytlsd is in its install, 5l), trained without Wireframe ground truth lines. Evaluated on HPatches/RDNIM repeatability, 3D line reconstruction and refinement (Tables 1-3), all natural images. Meaning for a drawing: a generic detector (DeepLSD, ScaleLSD) is the better prior than a wireframe-trained one (HAWP, M-LSD, GLSP-style), since a door leaf or arc is not a "structural" line. No drawings in the paper.

5z. Door-swing/arc gap, third retry (2026-11-14, arXiv API abstract search): "door swing", "door hinge plan", "arc detection drawing", "circular arc floor plan", "opening wall raster CAD" return no relevant paper since mid-2024 (the arc query returns only physics papers). So no abstract in arXiv's index since 2024 targets door-swing arcs in plans; this is evidence of absence for arXiv only (not for ISPRS, MDPI or Elsevier venues, which are not covered).
5za. ISPRS Annals 2023 door detection (searched hit, PDF read 2026-11-14): indoor point clouds (91 % inner doors), not drawings: excluded.

5zb. Electrical-plan paper (5e) details, re-read: dataset has 54 plans at 6000-7500 x 3500-4700 px (originally PDF, annotated in LabelMe JSON), publicly available from a named official website; code on Bitbucket (mep2bim; licence not read); its symbol detectors use MMDetection (Cascade Mask R-CNN, Apache-2.0) and ultralytics (YOLOv8/11, AGPL). Plan size is much larger than ours (our median longest side 855 px), which is why it tiled the image for symbols; DeepLSD ran on the whole filtered image.

5zc. R2V repo issues (gh api art-programmer/FloorplanTransformation, 2026-11-14): 40 newest read as titles. Recurring: pretrained model and checkpoint requests (#45, #49, #50, #42), PyTorch port performs worse than the Lua original (#22 open, #30 closed "pre-trained model for PyTorch does not perform good"), outdated dependencies (Lua Torch, numpy 1.15, opencv 3.4), training errors (#40, #11), requests for own-data training (#10, #16). Nothing about scans or thin lines. Confirms that R2V is a reference result, not a reusable tool (row 16b).

5zd. SkeySpot (row 16) code and licence: the paper text (PDF, read 2026-11-14) links only labelImg and ultralytics, no code, dataset or licence of its own, and its detector is YOLOv8 (AGPL). Row 16's "not read" for code/weights is therefore "none stated".

## 5zz. Adjacent field not yet touched: historical-map vectorisation on noisy scans (PLOS ONE 2024, "Automatic vectorization of historical maps: A benchmark", PDF read 2026-11-14, verified numbers; 2024, so just outside the 2025-26 focus, kept because it is the best scan-versus-clean evidence in this field)
Pipeline shape: a deep edge filter (U-Net, HED, BDCN, ViT/PVT variants) then a closed-shape extraction by watershed. Train on one map excerpt, test on a different edition scanned under other conditions (6000 x 5500 px, 2836 shapes). COCO Panoptic PQ on that test set with watershed: U-Net 46.7 with their proposed training (SQ 86.9, RQ 53.7) vs 18.3 with the earlier training; naive connected components 41.2 vs 8.1; pretrained HED 43.9, pretrained BDCN 46.4. The validation set (same map) is 59.8 PQ, so the shift costs about 13 PQ points even with the better recipe. Lessons that carry over: (1) the scan-shift penalty is large and the training recipe (not the net) moved test PQ from 8-18 to 41-47; (2) joint tuning of the edge stage and the shape-extraction stage beats tuning each alone (the paper's main claim); (3) topology-preserving losses and watershed gap-closing are the tools against broken lines, comparable to door gaps in walls. What breaks on ours: these are closed-shape (region) outputs on city blocks, not small symbols; no door/window analogue measured. Not read: repo licence (not looked for), the later transformer and topology-loss tables.
Also seen only as titles (2025-26, historical-map line/contour work, unread): contour vectorisation with U-Net (IJGI 2025), SCGCN map segmentation (CaGIS 2025), multiscale map segmentation 2603.05037, ACPV-Net 2603.16616 (aerial, already row-listed in 5).

5zze. M-LSD repo (row 4) re-read via gh api, 2026-11-14, verified: Apache-2.0 code; checkpoints and tflite models sit in the repo itself (8 tflite files, 1.3-6.1 MB, 320/512 input, tiny/large, fp16/fp32; weights licence not stated beyond the repo licence); requirements pin `tensorflow-gpu=2.3.0` (old, a plain pip install will fail on modern Python). Issues: #30 "very slow on the CPU" (open), #31 asks how to label own training data (open), #28 negative test results (open), #24 int8 quantisation (closed). Nothing about scans or thin lines. Row 4 verdict stays "maybe (CPU option)", with the caveat that the CPU claim has an open contrary issue and the TF 2.3 pin.

5zzf. HAWP repo dependencies (gh api cherubicxn/hawp, 2026-11-14, verified): `requirement.txt` and `setup.py` list opencv-python, cython, matplotlib, yacs, scikit-image, h5py, shapely, kornia/easydict and torch; `pycolmap` is a dev extra only. No pytlsd and no AGPL/GPL package by name (transitive not checked), so unlike ScaleLSD and DeepLSD, HAWP installs without the AGPL trap; MIT licence (issue #45 asked for it, closed). Issue #39 (open) asks for SAHI-style inference on 10000x5000 images: no built-in tiling. Trade-off: HAWP is the clean-licence line detector, but wireframe-trained and weaker than ScaleLSD on repeatability (row 3), so the order for a licence-first experiment is HAWPv3 or M-LSD, for a quality-first one ScaleLSD with the `pip install -e .` route.

## 5zg. The one hybrid raster-to-CAD paper found: Buildings 2026 (DOI 10.3390/buildings16051043; abstract and reference list via Crossref only, CC BY 4.0; MDPI page blocked: ABSTRACT ONLY, not verified)
"A Hybrid Deep Learning and Rule-Based Method for Architectural Drawing Vectorization and CAD Reconstruction" (Mar 2026): scanned raster to editable CAD in four modules (axis grid and dimension detection, text recognition and scale recovery, line topology reconstruction, geometric rectification), YOLOv11 plus OCR for the semantic part, skeleton thinning (sknw) for line topology, architectural drawing constraints for parameterisation. The abstract claims "favorable geometric accuracy and topological consistency" with no numbers; I could not see its tables, so no detector-versus-vectorise comparison can be taken from it. It is the only 2025-26 paper I found whose method is literally vectorise-then-rules on scanned architectural drawings; it uses a learned detector inside. Treat as a lead for lit-orch (full text needs a non-blocked copy). Row for the table: reported, abstract only.

## 5zh. Forward citation walk that worked: OpenCitations (no key) on Raster-to-Vector (ICCV 2017, DOI 10.1109/ICCV.2017.241), 2026-11-14
179 citing works indexed; 2025: 34, 2026: 4. Titles resolved through Crossref for the 2025-26 ones with DOIs. Relevant to our question (title level, unread unless marked): WAFFLE (WACV 2025, L1); Floor Plan Image Analysis survey (IJDAR 2025); "Door Detection Method Based on Optimized YOLO V8" (2025); "Object Detection on Complex Architectural Floor Plans with Efficient Attention Mechanisms" (2025); "Raster Image-Based House-Type Recognition and 3D Reconstruction" (Buildings 2025: key-point detection of walls, doors, windows on >5000 raster plans, vector dataset; abstract only, Crossref); "Patch-Wise Analysis and Reconstruction of Large-Scale Floorplan for Digital Twin Modeling" (IEEE Access 2025); "Hierarchical Intersection over Union Method: A Comprehensive Evaluation for Floor Plan Vectorization" (ASCE 2025); "Floor Plan Restoration: A Multimodal Method Under One Second" (TVCG 2025); "Exploring Structural Lines for Interior Floorplan Segmentation" (Visual Computer 2025); "Employing Graph Neural Networks for Construction Drawing Content Recognition" (ASCE 2025); "Intelligent Parsing of Floor Plans for Full-Scenario Applications" (ICPADS 2025); VectorGraphNET (ASCE 2025, already cited); Zernike moments (row 14); Sketch2BIM (5r). Excluded as off-topic: generation, energy, tactile, localisation papers.
Method note: `api.opencitations.net/index/v2/citations/doi:<doi>` returns the full list with dates; no auth, no rate-limit hit in this session. ScaleLSD has no DOI I could use, so its forward walk is still missing (arXiv-only IDs: `arxiv:2506.09369` untested).

5zi. OpenCitations on ScaleLSD (DOI 10.1109/cvpr52734.2025.00593): one indexed citing work in 2025-26, ADLA (arXiv 2508.19742, already read in 5g). Coverage of 2026 arXiv citations is thin in OpenCitations, so this is a lower bound; together with the arXiv title sweeps (5q, 5w) no paper applying ScaleLSD to drawings was found. DeepLSD forward walk not completed (DOI lookup failed).

5zj. Adjacent field, circuit schematics (SINA, arXiv 2601.22114, Jan 2026, full HTML read 2026-11-14, verified; self-reported on its own benchmark): modular pipeline, YOLOv11 component detector (fine-tuned on 700+ schematics, incl. scans and sketches) + connected-component labelling on the masked image for wires + OCR + GPT-4o netlist step; a separate VLM check compares counts with the detector and flags mismatches. Component detection precision 94 %, recall 99 %, F1 96.47 %; on 40 schematics SINA reaches 99.3 % circuit-structure and 96.47 % overall accuracy against 59.8 % / 35.5 % for the only open-source baseline. Same pattern as the rest of the report: learned detector for symbols, classical connected components for connectivity, a second counter (VLM) for conflicts. Caveats: YOLOv11 is AGPL (5s); tiny test set; baseline is a weak prior system; clean schematics.

## 9. Wrap-up (2026-11-14, ordered by lit-orch; no new sources started after this)
Honest status: verified from full text or repo files: ScaleLSD, DeepLSD (paper and repo), HAWP (Table I, repo), M-LSD (repo), ADLA (Table 4), GLSP (Table 2), VecFormer, fpvec-lab, 2608.25608, SALI-FP, FloorplanVLM, Raster2Seq, R2V, Pang (Tables I-III), DoorDet, FloorYOLO, PCP-Net, BlueprintAgent, 2608.17237, AECV-Bench, facility enumeration, electrical-plan DeepLSD paper, SynthPID, P&ID evidence graph, SINA, historical-map benchmark. Reported or abstract only: Buildings 2026 hybrid raster-to-CAD paper (5zg, Crossref abstract), Pang journal version, Carrara et al. 2026, 2607.00015 and 2604.23970 (skimmed), Sketch2BIM (skimmed), the 2025-26 R2V citers listed in 5zh (titles only). Not found: the 2025 Hough-arc door paper, any ScaleLSD-on-drawings paper, any vectorise-vs-detector head-to-head on the same scans, any door-swing-arc paper in arXiv since 2024. Missing tools: OpenAlex and Semantic Scholar keys (rate-limited; OpenCitations worked), a non-blocked route to MDPI, Elsevier, Springer and IEEE full texts.
