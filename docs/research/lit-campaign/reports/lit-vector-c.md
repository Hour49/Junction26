# lit-vector-c: raster to vector, practical fit (scope L11, angle c)

Read 2026-11-14 (machine clock, EET). "verified" = I (or a fetch agent on my order) read it on the page named;
"reported" = the authors' own claim. Page text read through web-fetch agents unless marked `gh api`, `curl`, `pwfetch`,
`own run`. Earlier reports extended, not repeated: `lit-vectorise.md`, `02-symbol-detection.md`,
`03-vector-cad-parsing.md`, `05-handdrawn.md`, plus the sibling reports `lit-vector-a/b` (their line detectors and
SymPoint reads are cited here only to add licence, memory and fit facts).

## 0. The answer to the scope question first

**Is there evidence that vectorise-then-rules beats direct detection on scanned plans? No, and one measured result
points the other way.**

- Nobody compares the two routes on door/window counts (verified absence in everything below; searched on arXiv,
  OpenAlex forward citations of 5 papers, 2024-2026).
- The only paper that vectorises a raster and then classifies the pieces, then tests on real scans, collapses there:
  Zernike/RAG+GNN (arXiv 2504.03241, 2025) reaches window F1 98.3 and door F1 93.2 on clean CubiCasa5K vectorised
  by itself, and **7.2 and 2.1 on 122 scanned plans** (Table 1, verbatim; trained on CubiCasa only; on the same plans rotated 45 degrees the window and door F1 are 76.8 and 79.7). Average F1 94.6 clean, 23.8 scans. Verified, `arxiv.org/html/2504.03241v1`.
- The same scanned set, scored by a pixel-wise segmentation route instead: arXiv 2408.01526 (CAB1/CAB2 U-Net
  variants plus post-processing, 2024, read in full via the browser) reports mean pixel F1 0.86 (CAB1) and 0.90
  (CAB2) on CVC-FP and 0.95 for walls, and on its CubiCasa subset door F1 0.82 and window F1 0.90 against 0.68-0.69
  and 0.81 for the CubiCasa5K authors' network and DFPR (Table III and IV, verbatim, 560-image CubiCasa subset,
  models ImageNet-pretrained, 2 x RTX A5000 24 GB, batch 1-2). Caveats that keep this from being a clean
  comparison with the Zernike numbers: pixel-wise F1 not per-object F1, unknown whether CVC-FP was in training,
  different splits. It still says that segment-then-postprocess on raster held up on scans where
  vectorise-then-classify did not. No code link seen.
- The one place where structural rules measurably help is **precision after a learned detector**: R2V (ICCV 2017)
  opening precision 67.9 without its integer-programming constraints, 91.9 with them, recall 91.4 vs 90.2; icon
  precision 22.3 vs 84.0 (Table 1, 100 test plans, 256x256 input). Verified from the paper PDF. This is the shape of
  a verifier on top of a detector, not a replacement for one.
- A 2025 R2V-style system confirms the same shape (Buildings 15(7):1178, "CPN-Floor", abstract only via OpenAlex, MDPI
  page refused): a learned key-point detector proposes wall, door and window primitives, axial-alignment rules and
  geometric constraints filter them, and the authors report (reported, not verified) over 87% precision and 88%
  recall with positions within 1% of the plan size on their own 5000-plan set; no counts, no scans, no public data.
- Sideways evidence points the same way: optical music recognition used to run staff-line removal, then symbol
  segmentation, then classification, and moved to one detector on the raw page; the TISMIR 2024 paper says recent
  work applies CNNs "directly to the raw input data, making multi-step designs obsolete" (related-work text,
  verified in the open PDF), and then gains the most from sim-to-real augmentation: AP at IoU 0.25 from 36.0 to
  73.3 on real noisy pages (abstract and Results, verified). Evaluation at IoU 0.25 because objects are tiny.
- Plain line detectors give a soup, not a count: on 30 random dev PNGs (own run, section 4) OpenCV FLD/LSD/Hough return
  about 1000 segments per image and 57-64% of them are under 20 px, the size of a window cell. Rules over that
  need a symbol-level filter first, so the "rules" stage ends up being the detector.
- The one head-to-head of vector input against raster detection on the same data is in the SymPoint-V2 paper
  (Table 2, FloorPlanCAD instance spotting, verbatim, re-read in full 2026-11-14): image detectors on the rendered
  drawing reach AP50 60.2 (Faster R-CNN R101), 63.9 (YOLOv3), 62.4 (FCOS), 64.0 / mAP 47.5 (DINO R50), the vector
  point-set model 71.3 / mAP 60.1. So *exact* primitives beat a raster detector by 7 AP50 and 12.6 mAP. That is
  an upper bound for a vectorise-first route: our primitives would come from a line detector, not from the CAD file,
  and the margin would have to survive the vectorisation loss, which nobody has measured.
- A second head-to-head, from TextCAD's Table 1 (arXiv 2607.12678, 2026, verbatim, re-read in full via the browser, no priors):
  the image-based PanCADNet gets PQ 57.60 on FloorPlanCAD-V2 and 60.80 on CubiCasa5K converted to CAD primitives,
  against 83-91 and 89-96 for the vector-input parsers (SymPoint 83.27 / 89.16, VecFormer 88.14 / 94.58, TextCAD
  91.09 / 96.53). Both comparisons (this and SymPoint-V2 Table 2) put raster detection well below exact-primitive
  input, which is the ceiling a vectorise-first route could reach and the reason the front end's loss matters;
  neither measures a detected-line front end, and PanCADNet is an older 2021 baseline.
So the practical role of line detectors for us is a **second, independent signal** (stage 8 `SecondCounter`,
plan splitting, wall layout) and never the primary counter: in my own probe (section 4b) segment statistics alone
correlate about 0.5 with the true window and door counts and never give an exact count.

## 1. Top 5 (floor-plan work and transfers in one list)

1. **OpenCV LSD / FastLineDetector / HoughLinesP as the structural channel.** try. Apache-2.0 (verified, repo
   licence `gh api`), the OpenCV `lsd.cpp` header is OpenCV's own BSD-style text with no AGPL notice (verified, `gh api`
   contents, 2026-11-14), so the earlier "licence unverified" flag on `createLineSegmentDetector` is cleared for
   OpenCV 5.0.0 (the build I ran). Measured 7-17 ms median per 815 px image on one CPU core (section 4). Fills no
   JSON field alone; feeds `plans` (split by wall components), orientation and the stage-8 second count.
   Source: OpenCV 5.0.0 own run, GitHub opencv/opencv.
2. **ScaleLSD v2 checkpoint (CVPR 2025, arXiv 2506.09369).** maybe, now closer to skip: an independent test finds its recall on all-line ground truth the lowest of the detectors compared (section 3, ADLA Table 3). Zero-shot probe on 20 images, then drop or keep; the public repo has no training script, so it can only ever be a zero-shot tool for us. Code MIT (LICENSE, verified), weights card says `license: apache-2.0` (HF README, verified; the card
   has no body text on licence). Leakage: no (Wireframe, synthetic, SA-1B, per paper). 512x512 ViT-B + DPT; **no
   thin-line, drawing or scan result in the paper, and no FPS or GPU number** (verified absence). Trap:
   `requirements.txt` pins `pytlsd`, whose `src/lsd.h` carries the AGPL text (verified, `gh api`); the repo only
   imports it in `line_matching/wireframe.py`, not in `predictor/` (code search, verified), so predict-only use can
   skip it, but never ship it. Fills: wall-like segments. Sources: arxiv.org/html/2506.09369v1,
   github.com/ant-research/scalelsd, huggingface.co/cherubicxn/scalelsd.
3. **A trainable line/wall detector: LINEA (Apache-2.0) first, HAWPv3 (MIT) second, fine-tuned on our walls.** maybe.
   LINEA: Apache-2.0 code, 3.9-25.2M params, README recipe for custom input size and batch, COCO-format line labels,
   trained from scratch without COCO pretraining, weights on GitHub releases with no licence text; open issues:
   NaN loss when a user trained at 1280 px (#3), multi-class lines need code changes (#4). HAWPv3: MIT code, weights
   licence stated nowhere I opened (docs, `hawp-torchhub` repo has none), public recipe (docs/HAWPv3.train.md: batch
   6, 10 epochs synthetic then 30 real; the pseudo-label step took 40 GB at batch 16 on an A6000, single-image mode
   is the low-memory option; abstract: training within 24 GPU hours); the maintainer says custom data transfers
   poorly without retraining ("annotation bias", issue #37). Leakage for both: no (Wireframe). Evidence on drawings:
   only a transmission-tower paper where an L-CNN variant beat HAWP on private data (CMC 2025). Both need wall labels
   we do not export yet (room polygon edges are the nearest thing). Fills: wall lines for rooms/plans, not symbols.
4. **R2V junction + integer-programming idea (ICCV 2017, art-programmer/FloorplanTransformation).** skip the code,
   keep the idea. MIT code (verified), weights on Google Drive, Python 2.7 / Torch era, its data is not CubiCasa
   (LIFULL, not shared), so leakage: no. 256x256 input, Manhattan only, 100 test plans. Use: a post-hoc consistency
   check on detector output (opening must sit on a wall, no two openings overlap), cheap to rewrite in 50 lines
   with shapely.
5. **VecFormer (NeurIPS 2025, arXiv 2505.23395) as the only vector-input parser we could license.** skip for the
   raster route. Training it is not a night's job either: a user reports 16 days on one RTX 3080 to reach about PQ 87 (issue #8). Code Apache-2.0 (gh api, pushed 2025-10-24), **no weights in the README**, input is true SVG primitives
   (verified). SymPoint v1 is a non-commercial licence (LICENSE.txt verified), SymPoint-V2 has no LICENSE file and
   an unanswered "commercial?" issue (#6), CADSpotting names no licence. None takes a PNG; no paper measures a
   line-detector front end. Its use is for the vector-PDF/DXF route (not ours).

## 2. Full table

Columns: method | from our field or transfers from | year, venue | code licence | weights licence | trained on (CubiCasa5K leak?) |
benchmark and metric | input / GPU | hours to first number (my estimate) | field it fills | verdict

| Method | Field | Year, venue | Code | Weights | Training data, leak flag | Reported result (benchmark, metric) | Input, memory | First number (estimate) | Fills | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| OpenCV LSD (`createLineSegmentDetector`) | transfer: generic CV | 2012 LSD, OpenCV 5.0.0 | Apache-2.0 (repo), BSD header in `lsd.cpp` | none (classical) | none, leak no | own run: 17.4 ms median, 924 segs, 57% < 20 px, 30 dev PNGs, 815 px | CPU, no GPU | 0.5 h | wall candidates | try |
| OpenCV FastLineDetector (contrib) | transfer | contrib module | Apache-2.0 | none | none, no | own run: 6.8 ms median, 1040 segs, 64% < 20 px | CPU | 0.5 h | walls | try |
| ELSED (Edge Drawing segments, pyelsed) | transfer | arXiv 2108.03144 (venue not read) | Apache-2.0 (gh api, pushed 2026-07-26); ED_Lib is MIT (gh api) | none (classical) | none, no | not measured: my `pip install` from git failed on the CMake build step here (CMake not installed); paper's speed claim not read | CPU | 1 h incl. build | wall candidates | maybe: the permissive alternative if FLD's soup is too noisy |
| SweepLSD (single-author, one-pass streaming segment detector) | transfer | arXiv 2608.22086, Aug 2026 (preprint, independent author) | MIT per the paper (C++17, zero dependencies); MIT in the repo (gh api, 5 stars, pushed 2026-08-25) | none | none, no | 11.3 ms median per Full-HD frame vs ELSED 51.4, EDLines 58.4, reference LSD 277.8 (i7-8700K, one thread, 123 photographs; paper Table 2, verbatim); quality numbers are in-distribution to its tuning, photos only | CPU, O(width) memory | 1-2 h | wall candidates | maybe: own run (section 4e) 15.2 ms, 429 segments, 32% under 20 px, stability between FLD and LSD |
| HoughLinesP | transfer | classical | Apache-2.0 | none | none, no | own run: 11.7 ms, 1010 segs, 57% < 20 px (Canny 50/150, thr 30, minLen 10, gap 3) | CPU | 0.5 h | arcs for doors (earlier: 2/40) | skip as counter |
| ScaleLSD | transfer: wireframe parsing | CVPR 2025 | MIT | card says Apache-2.0 | Wireframe 20k, SA-1B 10M; no | Rep-5 0.725 / Loc-5 1.466 at 512 px (Table 7, in-domain); YorkUrban Rep 0.725 vs HAWPv3 0.711, DeepLSD 0.514, LSD 0.419; no sAP, no drawings (verified) | 512x512 ViT-B; memory not stated; the repo tree (gh api, 2026-11-14) holds dataset classes, homographic transforms and eval configs under `scalelsd/ssl` but **no training script** and no trainer entry point, so fine-tuning means writing our own loop | 1-2 h probe; train unknown | wall segments | maybe |
| HAWPv3 | transfer | IEEE TPAMI 2023 (arXiv 2210.12971, abstract read) | MIT | not stated | Wireframe, ImageNet 100k; no | no numbers in README; ScaleLSD Table 7: Rep-5 0.751 (S) in-domain | 512; abstract: training within 24 GPU hours on one workstation GPU; pseudo-label stage 40 GB at batch 16 (A6000, reported) | 6-10 h incl. label prep | walls | maybe |
| DeepLSD | transfer | CVPR 2023 (abstract page) | MIT (README: weights MIT too) | MIT | Wireframe, MegaDepth; no | YorkUrban Rep-5 0.514, Loc 2.199 (ScaleLSD Table 1) | needs Ceres/GFlags build; default pipeline runs LSD to extract lines (paper Sec. 3.2, 3.4) and `third_party/pytlsd` is in the tree (AGPL LSD source, verified for pytlsd); HPatches 271 ms vs LSD 104 ms (Table 1, GPU not stated) | 2 h (build pain) | walls | skip: AGPL component is the default path |
| M-LSD / M-LSD-tiny | transfer | arXiv 2106.00186 (venue not read) | Apache-2.0 | not stated | Wireframe; no | Wireframe sAP10 62.1 (512), tiny 58.0; YorkUrban 27.3; 0.6M/1.5M params, 115-200 FPS V100, 27-57 FPS phone | 320 or 512; tiny 78-111 MB FP16 phone; the reported FPS are V100 GPU on native checkpoints (maintainer, issue #29); users measure about 300 ms (i7-2600K, tflite, issue #29) and 400-500 ms (issue #30, open) per frame on CPU; no labelling or training-data docs (issue #31, open) | 3 h (TF) | walls | skip: no CPU advantage over FLD/LSD (7-17 ms) |
| LINEA | transfer | ICIP 2025 per the lh9171338 papers list (arXiv 2505.16264) | Apache-2.0 (gh api; requirements.txt has no AGPL/GPL package) | checkpoints on GitHub releases, licence not stated | Wireframe, trained without COCO pretraining; no | Wireframe sAP10 65.0 (N) to 67.9 (L) with 3.9M to 25.2M params; YorkUrban 30.5-34.9; 2.5-5.8 ms TensorRT fp16 on RTX A5500 (README, verbatim) | default 640 square; README shows custom square sizes and batch 4 at 480 on one GPU; issue #3 (open): a user training at 1280 gets NaN loss around epoch 10 | 4-6 h to a first fine-tune (estimate, COCO-format line labels needed) | wall/frame lines | maybe: the only line detector with an Apache repo, a documented custom-data recipe and a small variant |
| GLSP: HAWP + GNN on floor plans | field | arXiv 2303.03851, 2023 | no repo | none | own 268k set; no | msAP8 90.28 vs HAWP-M* 71.12 (their set, 512 px); door sAP8 97.50 vs HAWP-M 56.66, wall and window tables in the appendix (Table 7, verbatim, re-read in full 2026-11-14) | 512 | n/a | wall/door/window segments | skip: no code, no scans |
| R2V (Liu et al.) | field | ICCV 2017 | MIT | Google Drive access-request link; users report no reply (issues #42, #45, open, 2024); the PyTorch port found 11 walls where the original Lua model found 33 on one plan (issue #22, open since 2019), and the README says the port was never evaluated | LIFULL 870 plans; no | opening P/R 91.9/90.2, icon 84.0/74.6, wall junction 94.7/91.7 (100 test plans, 256 px) | 256, Titan GPU, py2.7 | skip | openings (idea) | skip code |
| Zernike RAG+GNN | field | arXiv 2504.03241, 2025 | no code link | none | CubiCasa 400-plan subset; **yes** | scans: window F1 7.2, door F1 2.1 (see section 0) | Quadro RTX 8000 | n/a | none | skip, but the evidence for section 0 |
| Deep Vectorization of Technical Drawings | transfer: technical drawings | ECCV 2020 | MPL-2.0 (not on our list; file-level copyleft, needs a ruling) | pretrained line/curve on Drive, licence not stated | ABC, PFP, synthetic; no | real scans (81 images, ~1300x1000): IoU 79-82 vs CHD 47 (Table 1, extracted); clean PFP floor plans IoU 86-88 | 64x64 patches; 4 days on a V100 to train; cleaning model **not** in the repo (issue #10, open since 2021, no weights ever shared) and the line checkpoint link is dead: the author wrote on 2026-10-12 (issue #33) "I no longer have a copy of the checkpoint files" | n/a | none (no symbol class) | skip: no usable weights exist any more |
| SymPoint-V2 | transfer: vector CAD | arXiv 2407.01928, 2024 | no LICENSE file | Google Drive, none stated | FloorPlanCAD (NC); no | PQ 90.1; single door PQ 94.4, window 90.1, sink 89.8, bath tub 87.8, bath 79.2, gas stove 96.4 (Table 5, verbatim; SPv1 window 78.9) | 35M params, 95 ms, needs layer ids; trained on 8 A100, batch 16, 250 epochs; inference memory not stated | n/a | none | skip |
| SymPoint v1 | transfer | ICLR 2024 | non-commercial only | OneDrive | FloorPlanCAD; no | PQ 83.3 | 35M, 66 ms | n/a | none | skip |
| CADSpotting | transfer | arXiv 2412.07377, CVM 2026 | not named | public `best.pth`, licence not stated | FloorPlanCAD + LS-CAD; no | PQ 87.4 | dense points, PTv3 | n/a | none | skip |
| VecFormer | transfer | NeurIPS 2025 | Apache-2.0 | none published | FloorPlanCAD; no | PQ 91.1 with layers, 88.4 without; SymPoint-V2 83.2 without layers (their run) | line segments of true primitives | n/a | none | skip (raster) |
| MitUNet | field | arXiv 2512.02413 (v3 Apr 2026) | MIT (gh api, aliasstudio/mitunet) | README links a `.pth` fine-tuned checkpoint (SegFormer mit_b4 + U-Net, 28 epochs) committed in the repo's `experiments/models/` (MIT repo, no separate weights licence; checked 2026-11-14), CubiCasa5K pretrained so it leaks | **CubiCasa5K pretrain: yes**; plus 500 CIS plans | wall mIoU 87.9 (CIS set, 512 px); no doors counted | 512 | n/a | walls only | skip: leak |
| FloorplanVLM | field | arXiv 2602.06507, 2026 | none published | none | proprietary 2M; no | Opening-F1 0.733 (FPBench-2K) | Qwen2.5-VL-3B | n/a | n/a | skip |
| Raster2Seq | field | arXiv 2602.09016, 2026 | not read | not read | CubiCasa5K: **yes** | window+door F1 77.8 CubiCasa5K, RoomFormer 78.5; 256 px | 256 | n/a | pointer: scope L1 | skip |
| TextCAD | field | arXiv 2607.12678, 2026 | none seen | none | FloorPlanCAD-V2, CubiCasa5K: **yes** | Table 1 verbatim: PQ 91.09 FloorPlanCAD-V2, 96.53 CubiCasa5K converted to primitives (no priors); image-based PanCADNet 57.60 / 60.80 | primitives + text | n/a | pointer: scope L1 | skip |
| Tower drawing vectoriser (L-CNN variant) | transfer: engineering drawings | CMC 2025 | no repo | none | own 1280 drawings; no | sAP10/15 beat HAWP, DeepLSD (values in an image table, not read); ~2 s/drawing | 256 px masks, tiles of 7000x10000 | n/a | none | skip |
| Digitize-PID | transfer: P&ID | PAKDD 2021 | none | none | synthetic 500 sheets; no | symbols F1 0.82-0.98 (IoU > 0.75); lines found by morphology, symbols first | 400 px patches | n/a | idea: symbols first, lines after | idea only |

## 3. Practical-fit notes per candidate (what breaks on our images)

Our images: median 855 px longest side, symbols 5-20 px, a third rotated by exact multiples, some scans.

- **What the inference scripts do to an 855 px plan (read from the code, `gh api`, 2026-11-14):** ScaleLSD's
  `predictor/predict.py` does `cv2.resize(image, (512, 512))` whatever the aspect ratio (defaults `--width 512
  --height 512`), then rescales the segments back; it has `--device cpu`, an `--whitebg` option and no tiling. HAWP's maintainer
  confirms in issue #39 (open) that large images are simply resized to 512x512, calls that "unreasonable" for
  10000x5000 inputs and says a tiled mode would be necessary, which does not exist. So a 10 px window cell on an
  855 px plan shrinks to about 6 px (width 855 to 512 is x0.6) and a non-square plan is squashed unless we pad it.
  Tiling and padding would be our own code for all three detectors.
- **Independent comparison of classical and wireframe detectors on "every line" ground truth** (ADLA, arXiv
  2508.19742v3, listed later as POEv2, 2025, Table 3, YorkUrban-LineSegment, pixel-level P/R/F, read in full via the browser): LSD AP 0.908,
  AR 0.735, F 0.813; DeepLSD F 0.823; Linelet F 0.851; HAWPv2 F 0.753 (AR 0.661); **ScaleLSD F 0.673 at its
  lowest threshold (AR 0.539), falling to F 0.485 at threshold 30**; LINEA F 0.805; DT-LSD F 0.727. Reading: when the target is
  all line strokes rather than the structural lines of Wireframe, wireframe-trained deep detectors lose recall to
  plain gradient-based LSD, and ScaleLSD loses most. This is the same direction as our need (every thin stroke of a
  window frame counts), so it lowers ScaleLSD's rank for symbol-scale work and raises the classical channel.
  The ADLA code is "released upon acceptance" (not available); it also post-processes edge maps, which is
  the thick-line splitting problem. YorkUrban is photos, not drawings.
- **LINEA (Apache-2.0, 3.9-25.2M params) is the better-documented trainer** than ScaleLSD or HAWPv3: README commands for custom input size and batch size, line labels in COCO format, issue #4 (open) says multi-class lines need code changes in the post-processor (the maintainer's reply shows how). Its weakness for us is scale: the only user report of going past 1024 px hit NaN loss (issue #3, open, reply not resolving). Nothing is tested on drawings.
- **ScaleLSD and every Wireframe-trained detector (HAWPv3, M-LSD, DeepLSD, LINEA):** they are trained to find long
  building edges in photos. On a plan at 855 px, a window cell is 5-20 px, below the "line" scale they learned
  (my inference, not tested by the paper; its Table 4 only gives the pseudo-label cost: 0.607 s and 6.6 GB per batch for LSD-Rectifier, verified). At 512 px input an 855 px sheet is downscaled 1.7 times, so a 10 px cell becomes
  6 px. We would tile, and the paper gives no tiling result. Rotation by 90/180 is harmless for a detector with
  no orientation prior, but the orientation of the *text* is not recovered by line segments.
- **Scans and phone photos:** every line-detector paper tests photos of rooms or clean renders. Thick, double,
  hatched and anti-aliased lines make LSD-style detectors split one wall into two segments (this is the exact
  failure the tower-drawing authors fix by changing the DeepLSD angle field, abstract of IEEE YAC 2026, abstract only
  via OpenAlex). Our own run shows the segment soup (section 4).
- **Door arcs:** HoughLinesP and circle fitting are the earlier 2/40 and 3/40 dead end; no line detector helps
  because the arc is itself the symbol, and a window cell is a few short parallel strokes that the plain detectors split like any other line (my reading, no test).
- **Symbol-level vector parsers (SymPoint family, CADSpotting, VecFormer):** need per-primitive SVG paths (SymPoint
  turns each primitive into one point with angle, length, type; V2 also needs a layer id). A detector's segments
  have neither. CADSpotting's own ablation shows the sensitivity: handcrafted primitive features reach PQ 80.2
  against 87.4 with dense point sampling (Table 7, verbatim), so features computed from detected segments would lose
  at least that much before any detection noise. Nobody reports the number. Their weights train on FloorPlanCAD
  (NC) which our record 0003 allows for the local prototype only.
- **Checkpoint sizes** (Hugging Face API and GitHub release assets, read 2026-11-14): ScaleLSD v1/v2 493 MB each
  (two files, the card publishes no parameter count), HAWPv3 47 MB, HAWPv2 45 MB. So HAWPv3 is about 12M
  parameters and fits a 12 GB card for training at batch 6 without trouble (my inference from file size); ScaleLSD
  at about 0.5 GB of weights runs inference at 512 px on 12 GB (my estimate, not a source). The HF model card lists
  0 downloads and 4 likes, the GitHub repo 83 stars: little field testing of the weights.
- **VecFormer training cost, from a third party** (GitHub issue #8 on WesKwong/VecFormer, 2026-08-12, open, verified):
  a user reports training on a single RTX 3080 needing "16 days" to reach about PQ 87, with a preliminary PQ 84.7
  checkpoint posted on ModelScope (licence unread). Its stack is torch 2.5.1/CUDA 11.8 + flash-attn built from
  source + spconv-cu118; requirements are Apache/MIT/BSD (no AGPL or GPL package in `requirements.txt`, verified).
  CADSpotting needs MMDet3D 1.4.0 + flash-attn + spconv on CUDA 12.1; its README has an empty "License" heading
  (verified), and its only issue is a request for checkpoint and dataset. So "train a vector parser in a night" is
  not available for any of them, even before the raster-input problem.
- **SymPoint-V2 on one GPU** (issues #5 and #7, both open, verified 2026-11-14): a user finds that single-GPU training at
  batch 16 does not drop the loss the way 8 x A100 does, no answer; two more report a CUDA index-out-of-bounds in the custom
  `pointops` kernel at inference, unresolved. PolarSym (arXiv 2608.11793, read in full) trained its SymPoint-V2
  comparison for 50 epochs on two V100-32GB, against 250 epochs on 8 A100 in the original. Both support the
  same reading: a vector parser is a multi-GPU project, not a 12 GB one.
- **CADSpotting's "robust"** (full text read via the browser, 2026-11-14) means robust to scale, overlap and symbol diversity on large drawings through sliding-window aggregation with Sparse-NMS (the vector-input analogue of SAHI, per its method section); a text search of the whole paper finds no noise, scan or rasterisation experiment, and LS-CAD (45 large floor plans) is promised under a licence waiver. So there is still no noise test for any vector-input parser.
- **Hours to a first number** are my estimates: OpenCV line channel 0.5 h (done, see section 4); ScaleLSD probe 1-2 h
  (install of CUDA 12.1 + torch 2.5.1 stack, then predict); HAWP fine-tune 6-10 h including generating wall labels
  from room polygons (not exported yet); everything vector-input has no first number on raster at all.
- **GPU memory** (12-16 GB): no source I read states inference memory for ScaleLSD, HAWPv3, SymPoint, CADSpotting or
  VecFormer. Reported: HAWPv3 pseudo-labelling 40 GB at batch 16 (reduce to single image), ScaleLSD pseudo-labelling
  6.6 GB per batch. M-LSD-tiny runs in 78-111 MB on a phone (Table 3). All "fits in 12 GB" claims for the rest
  would be my guess; I do not make them.

## 4. Own measurement: classical detectors on dev plans (extends sections 2-3 of the context)

Setup: 30 random CubiCasa dev PNGs from the local copy of the dataset, grayscale, one CPU core, OpenCV 5.0.0
(`opencv-contrib-python-headless`), median longest side 815 px. FLD `length_threshold=8`; LSD defaults; Canny 50/150 then
HoughLinesP (rho 1, theta 1 degree, threshold 30, minLineLength 10, maxLineGap 3). No ground truth was used, so this
measures cost and segment soup only, not accuracy.

| Detector | median ms | p95 ms | median segments | median share under 20 px |
|---|---|---|---|---|
| FastLineDetector | 6.8 | 15.4 | 1040 | 0.64 |
| LSD | 17.4 | 37.1 | 924 | 0.57 |
| HoughLinesP | 11.7 | 29.7 | 1010 | 0.57 |

Reading: speed is not a constraint at all (the whole sheet in under 40 ms). The problem is selectivity: about
60% of what a rule-based second counter sees is short segments to discard (under 20 px): text strokes,
hatching and symbol outlines. This extends the 3/40 and 2/40 door results: the classical route is cheap but its
inputs are not symbols.


### 4b. Own probe: how much count signal is in line-segment statistics alone?

Open question 6 of the context asks whether any cheap structural signal can be the independent second count.
Probe: 500 random dev plans with both a window and a door answer; per image the FLD segments (length_threshold 6)
reduced to 15 numbers (a 9-bin length histogram scaled to 855 px, segment count, share of axis-aligned segments
and of the other axis, dark-pixel share, image sides), then a gradient-boosted regressor (150 trees, depth 3),
5-fold cross-validation, trained on the dev answers only. No symbol is located.

| Target | most common answer | exact / MAE | regressor exact / MAE | correlation with the true count |
|---|---|---|---|---|
| windows | 4 | 16.4% / 4.16 | 10.2% / 3.39 | 0.54 |
| doors | 6 | 14.6% / 3.51 | 12.2% / 2.89 | 0.49 |

Reading: the segment statistics carry real but weak signal (MAE down about 18%, correlation about 0.5) and **never
reach an exact count**, exact-match is below the constant answer. So a line-segment channel can flag an
implausible detector count (for example a detector says 2 windows, the structure says about 8) but cannot be a
second counter on its own. Adding a hand-made structural feature did not help: counts of close parallel pairs of short segments (6-60 px, 1.5-8 px apart, three offset bins; the stroke pattern of a window frame or a door leaf) left the result at window correlation 0.53 / MAE 3.41 / exact 12.0% and door correlation 0.50 / MAE 2.85 / exact 13.2%. So the plateau is the whole-image, label-free regression, not a missing feature; a symbol-level detector with box labels is what moves exact counts.
By drawing style (three styles in the sample, 381 / 86 / 33 plans): window correlation 0.53 / 0.41 / 0.48 and
door correlation 0.52 / 0.45 / 0.25, so the signal is not one style's artefact, and doors are weakest on the colourful style.
Caveats: one random sample of 500, folds not grouped by drawing family (mirrored copies
exist, which flatters the regressor), counts are whole-image totals, an upper bound of what these features give.
Scratch code lives outside the repo.

### 4c. Own probe: what a forced 512 px input does to short segments

The ScaleLSD and HAWP scripts squash every image to 512x512 (section 3). Proxy test with FLD (length_threshold 4) on the
30 dev plans that are at least 700 px on the long side: resize so the long side is 512 (INTER_AREA), detect, map the
lengths back to native scale, and compare the number of segments per length bin with the native-resolution count of
the same bin, median over images.

| Segment length at native scale | segments found at 512 px / at native |
|---|---|
| 6-12 px | 0.34 |
| 12-20 px | 0.70 |
| 20-40 px | 0.85 |
| 40 px and longer | 0.84 |

Reading: roughly two thirds of the 6-12 px strokes (the window-cell and door-leaf scale) and 30% of the 12-20 px
strokes are gone after the downscale, long walls mostly survive (a ratio is not a recall: merges and splits move
segments between bins, and FLD is not the neural detectors). It supports tiling at native or 2x resolution for any
symbol-scale use of these detectors, and is another reason to keep line detectors on wall-scale jobs.

### 4d. Own probe: how stable are the segments under scan-like degradation

Same 30 dev plans, segments of at least 20 px only. Degradations applied to the grayscale image: Gaussian blur
sigma 1.2, additive noise sigma 12, JPEG quality 30, half-resolution then back up (bilinear). "Kept" = share of the
clean image's segments that have a segment in the degraded image whose two endpoints lie within 4 px each (sum under
8 px, either direction); "count ratio" = segments after / before. Medians over images.

| Detector | blur | noise | JPEG 30 | half-res |
|---|---|---|---|---|
| FLD kept / count ratio | 0.51 / 0.93 | 0.56 / 0.96 | 0.64 / 1.01 | 0.48 / 0.93 |
| LSD kept / count ratio | 0.65 / 0.88 | 0.73 / 0.99 | 0.79 / 1.00 | 0.68 / 0.92 |

Reading: the number of long segments barely moves (0.88-1.01) but 21-52% of the individual segments are not found again
at the same place, so counts of segments are stable while the segments themselves are not, and LSD is steadier than FLD on
all four. Any rule that needs a specific segment (a door-leaf line at a given spot) inherits this jitter; a rule over
statistics (section 4b) does not. Synthetic degradation of already-clean PNGs: real phone photos are harder (perspective,
shadows), which the earlier sheet-normalisation reports cover.

### 4e. Own run: SweepLSD (MIT, Aug 2026) on the same 30 plans

Built from the public repository with plain `g++ -O2 -std=c++17` (no CMake, default parameters; author's best timings
need GCC 15 flags), grayscale input, one thread. Same degradation protocol as 4d.

| Measure | SweepLSD | for comparison (own runs above) |
|---|---|---|
| median time per plan, p95 | 15.2 ms, 62.2 ms | FLD 6.8 / 15.4, LSD 17.4 / 37.1 |
| median segments per plan | 429 | FLD 1040, LSD 924 |
| share under 20 px | 0.32 | FLD 0.64, LSD 0.57 |
| segments of at least 20 px, relative to LSD | 0.75 | n/a |
| kept share / count ratio, blur | 0.52 / 1.01 | FLD 0.51, LSD 0.65 |
| noise | 0.62 / 0.93 | FLD 0.56, LSD 0.73 |
| JPEG 30 | 0.72 / 1.02 | FLD 0.64, LSD 0.79 |
| half-res | 0.46 / 1.03 | FLD 0.48, LSD 0.68 |

Reading: its contrast-gated edge model returns less than half the segments of FLD or LSD and far fewer of the junk
short ones (the author's own caveat is that it misses low-contrast structure), which is the cleaner soup a rule layer
wants, but it is no more stable than FLD under degradation and LSD stays the steadiest. Speed here is the same
order as FLD, so there is no speed reason to prefer it; the reasons are the licence (clean MIT code, no AGPL
ancestry) and the smaller output. Not tested for recall of window or door strokes (no boxes on this machine).

## 5. Citation graph, forward from my two best papers (OpenAlex, `api.openalex.org`, 2026-11-14; Semantic Scholar
returned 429 and Google Scholar a captcha)

- ScaleLSD (2506.09369): only 2 citers listed, both 2026 and both 3D line mapping or local features, none on
  drawings (OpenAlex lags; Semantic Scholar not reachable).
- SymPoint-V2 (2407.01928): 6 citers: CADSpotting (CVM 2026), ArchCAD-400K (NeurIPS 2025 datasets), VecFormer
  (NeurIPS 2025), Text-Aided panoptic symbol spotting (arXiv 2607.12678), PolarSym (arXiv 2608.11793), TempFit
  (ACM 2026, page blocked, abstract unread). All vector-input. None goes from raster.
  TempFit (abstract via OpenAlex): reformulates symbol spotting as retrieving and aligning a canonical template from a
  library, which fits our repeated door/window symbols in idea, but its input is CAD primitives and it reports FloorPlanCAD and a new private IndustryCAD set. Now read (arXiv 2610.17776, Oct 2026, via the browser): it discretises the drawing and the template library into line segments with VecFormer's encoder, and the templates it retrieves are 3D-asset projections or a symbol library; vector input, no raster or noise test.
- SymPoint v1 (2401.10556): 10 citers, adds a raster-ish one: "Pixel-wise symbol spotting via progressive points
  location" (arXiv 2404.10985) takes raster CAD images (1700x1200 to 4200x3000, 256x256 patches) but on its own
  equipment-room drawings (12 classes, no doors/windows, F1 0.76-0.97, 300 train images; verified).
- HAWP (1905.03246), forward, 2024-06 onward, filtered to drawing/CAD titles: "Modular Raster-to-Vector
  Digitization of Architectural Floor Plans" (WSCG 2026: unpaired scan enhancement, OCR-guided text extraction,
  keypoint-based geometry, "AI-enhanced template matching" for symbols; **abstract only**, paper PDF blocked by a
  certificate error), "A lightweight geometric consistency enhancement for one-stage architectural line segment
  detection" (IEEE Access 2026, F-Clip based, roofs; abstract only), "Vectorization method based on improved
  DeepLSD" (IEEE YAC 2026, tower drawings, thick-line splitting; abstract only), "Vector extraction from design
  drawings ... transmission towers" (CMC 2025, read). Takeaway: line-detector work on drawings exists only for
  towers and roofs, with private data.
- Newer wireframe detectors from a maintained papers list (gh api lh9171338/Line-Segment-Detection-Papers, read 2026-11-14): DT-LSD (WACV 2025, Apache-2.0 repo, pushed 2025-05-01), Co-PLNet (arXiv 2601.18252, MIT repo, read: Wireframe and YorkUrban photos only, SLAM motivation, no drawings), RANK-LETR (AAAI 2025), AAGLSD (PRCV 2025, classical, no code listed), ADLA/POEv2 (above). None tests drawings.
- Deep Vectorization of Technical Drawings (2003.05471), forward: "Hierarchical IoU for floor plan vectorization"
  (ASCE 2025), "Sketch-to-3D hand-sketched floorplans" (DICTA 2024), "Structure-descriptors guided hand-drawn
  floor plan reconstruction" (IROS 2024), all titles only, none read (paywalled or not opened).

## 6. Transfer notes (other fields; the sibling worker b covers sideways reading in depth)

- **P&ID digitisation (Digitize-PID, PAKDD 2021)**: finds symbols first with a 400 px patch network, finds lines by
  morphological erosion/dilation, and only then removes lines overlapping symbols to build the graph. Role of our
  object: a valve symbol is a window cell. Why it should transfer: same shape (small repeated symbols on line art,
  F1 0.82-0.98 at IoU 0.75 on synthetic sheets). What breaks: synthetic only, real set 12 sheets, no scans, symbols
  at 7168 px width are far larger than ours. Idea only, no code or weights.
- **Technical-drawing vectorisation (Deep Vectorization, ECCV 2020)**: shows a *cleaning* network is what makes
  scans workable (DLD scans IoU 79-82 vs 47 for a classical baseline). What breaks: the cleaning model is not in
  the repo (verified README: "currently cleaning model not included"), repo archived, MPL-2.0, no symbol class, 64 px
  patches. Idea only: a cleaning step before a detector, which is the sheet-normalisation scope (L9).
- **Transmission-tower drawing vectorisation (CMC 2025; YAC 2026 abstract)**: a line network adapted to thick-line
  drawings beats HAWP/DeepLSD there. What breaks: private data, a single drawing style.

- **Optical music recognition (TISMIR 2024, "Real World Music Object Recognition", CC BY 4.0, code at
  github.com/raember/s2anet, repo has no licence field, last push 2023-10)**: role of our object: a note head or
  accidental on a staff is a window cell on a wall. Why it transfers: tiny symbols on dense line art, scanned and
  aged pages, exact marks wanted. Result: staff removal was dropped in favour of one detector; ScoreAug (synthetic
  scores overlaid on real blank pages with salt-and-pepper noise, small rotations) doubles detection AP on real
  pages, adversarial domain adaptation gets 48.9 against 36.0. What breaks: no exact-count metric, AP at 25% overlap,
  their data is pages of black notes, ours are coloured, hatched and with printed text. Only the idea (compose
  synthetic symbols onto real blank plan backgrounds) is usable; the licence of the code is unclear. Belongs to
  data (L8) and sheet (L9): pointer only.
- **Scan robustness study on CubiCasa5K itself** (Automation in Construction 2026, "Why floor plan object detection
  breaks under real scans", doi 10.1016/j.autcon.2026.107193): paired CAD-derived and scanned rasters of the same
  layouts, RT-DETR three seeds; reports AP at 75 and 85 fall far more than AP at 50 and that the object region's
  depiction, not the background, drives the loss. **Abstract only** (OpenAlex; ScienceDirect refused the browser),
  checkpoints "publicly released" per the abstract, so a CubiCasa5K-trained **leaking** checkpoint. Pointer to L2/L9;
  worth the detect worker reading in full.
- **Hybrid DL + rules CAD reconstruction** (Buildings 2026, doi 10.3390/buildings16051043): axis grid and dimension
  detection, OCR scale recovery, line topology, constraints. **Abstract only** (MDPI refused), no numbers in the
  abstract; the targets are axis grids, dimensions and line topology of architectural drawings, not residential symbol counts. By
  its abstract it is the one 2026 paper whose pipeline is "vectorise, then rules", and it reports no counting number.

- **Flowchart digitisation (FlowExtract, arXiv 2604.06770, Apr 2026, CC BY 4.0, read in full via the browser)**: role of
  our object: a flowchart node is a window cell and an arrowhead is the small anchor symbol from which the line
  structure is traced. Result on 1145 annotated nodes of real maintenance diagrams, YOLOv8s at 640 px, COCO
  pretraining, 250 epochs, batch 8: nodes F1 98.8% against 34.0% for the best VLM; edges (the line topology, found by
  tracing from detected arrowheads) precision 85.5%, recall 54.6%, F1 66.7% against 10.7% for the best VLM. Reading:
  once more, the discrete symbols are the easy part and the connecting line structure is the weak part, and the
  authors' fix is symbol first, lines traced from the symbol. For us the analogue is "detect the door leaf or window
  cell, then use the wall structure only to verify". What breaks: boxes are large, no scans, only 1145 nodes, and
  it uses Ultralytics YOLOv8 (AGPL, out for shipped code); the idea is usable, the code is not.
- **PCB/schematic**: a web search found no 2025-26 paper that vectorises PCB copper from photographs into a
  graph; the only usable lead is training segmentation of junctions and traces purely on synthetic renders from
  layout files (Electronics 2024, MDPI page refused, snippet only, so unread) which echoes the sim-to-real
  point in the OMR note above.

- **Unified vector extraction from raster images (UniVector, arXiv 2510.13234, Oct 2025, in press 2026; search results only, page not opened)**: one query-based model for polygons, polylines and line segments on aerial building/road images (CrowdAI, Topo-Boundary, Wireframe/YorkUrban reported). Nothing on drawings or symbols; its repo (github.com/yyyyll0ss/UniVector, `gh api` 2026-11-14) exists, 5 stars, last push 2026-10-25, with no recognised licence (NOASSERTION), so not usable as it stands.
- **Historical-map vectorisation (Chen et al., PLOS ONE 2024, "Automatic vectorization of historical maps: a benchmark", CC BY 4.0,
  read in full via the browser; code, data and models on Zenodo, licence not opened)**: role of our object: a map block is
  a room and the printed block boundary is a wall, and the closed shape is what we need from walls with gaps. Pipeline: a
  U-Net/HED/BDCN edge filter, then a Meyer watershed to close shapes, so a missing pixel on a boundary does not
  merge two blocks. Measured on Paris atlas sheets (COCO panoptic quality on closed shapes): a better training
  protocol and joint tuning of the two stages lift the original baseline, contrast plus thin-plate-spline
  augmentation reaches PQ 51.1%, a small U-Net loses 2 points (47.1 to 45.1) for a much smaller footprint, and
  topology losses (TopoLoss, BALoss) were tested to close gaps. What breaks: one atlas style, PQ around 50%, not
  residential symbols, nothing on doors or windows. Use: idea only for closing wall gaps (watershed on an edge map
  is the robust alternative to our in-house wall closing that still leaked); room areas move no score, so low priority.
- **Classical lines against a learned detector on the same task, outside floor plans** (LiDAR bird's-eye-view maps, arXiv
  2603.19830, Mar 2026, read via the browser): Hough, LSD, DBSCAN+RANSAC and a YOLO-OBB detector extract structural
  walls from 2D projections on a CPU-only single-board computer. Reported: LSD "produces excessive segment
  fragmentation that leads to system congestion", Hough reaches higher recall in a cluttered hallway with precision
  near 0.4 (F1 0.53), YOLO-OBB has the best F1 there (0.62 +- 0.04) with the lowest variance and meets 10 Hz without a
  GPU. Not a drawing task and a different metric (length-weighted recall, F1), so it is a direction, not evidence for
  plans: it matches section 4 (LSD segment soup) and the ADLA table in that learned detectors beat the classical ones on
  precision, while the classical ones win recall. Uses Ultralytics YOLO (AGPL).
- **Thin-structure segmentation with topology losses (power lines, cracks, lane markings at 1-3 px; SEMIR, arXiv
  2606.24935v2, 14 Oct 2026, read in full via the browser; losses clDice (MIT, gh api), Skeleton Recall Loss
  (Apache-2.0, gh api, pushed 2026-10-05))**: role of our object: a plan's wall or window frame line is a crack or
  power line. Why it transfers: 1-3 px lines whose connectivity is the signal, which is our wall/thin-line style
  after downscaling. Numbers: Dice .894 on TTPLA power lines, .911 on CrackSeg9k vs best published .889 and .909, on
  a 16 GB T4; the paper's own limitation: it loses to pixel encoders when large-area classes dominate and needs a
  good over-segmentation. What breaks: no drawings, no scans, no code link seen, parameters tuned per dataset on
  5-20 labelled images. Use: the two losses (clDice, Skeleton Recall) are drop-in for a wall-mask network and
  keep wall lines unbroken before a gap rule counts openings; the SEMIR graph itself is idea only. Belongs partly
  to sheet (L9), so one pointer.
- **Road-network extraction (SAM-Road, CVPRW 2024; DOGE, LineGraph2Road, DeH4R, 2026)**: titles and abstracts
  only (OpenAlex); topology metrics exist there (connectivity-preserving), nothing on symbols. Not read further.

## 7. Looked for and did not find

- Any accuracy number for FLD, LSD or HoughLinesP on floor plans (still none; my run measures cost only). The closest
  outside number, read in full (arXiv 2305.16968, Table 2, full PDF, 2026-11-14): 190 test pages of 19th-century trade
  directories with 4.3 long ruling lines per page (a much easier target than 5-20 px symbols). F-score / F-score2
  (F-score2 penalises split fragments), test split: ELSED 87.0 / 35.2, EDLines 87.4 / 30.5, OpenCV probabilistic Hough
  64.8 / 18.2, LSD (original) 12.5 / 0.5, LSD II 53.3 / 20.7, a tracking-based method 90.1 / 87.6; times 264-2338 ms per
  page. Two lessons: default-setting detectors split thick strokes into double detections (fragmentation, not misses,
  is what costs them), and the same detector can vary from 12 to 87 F by version and settings. FLD is not in the table.
- Any paper that compares vectorise-then-rules with direct detection on counts (none), or that feeds line-detector
  output into SymPoint/VecFormer/CADSpotting (none).
- Training memory for ScaleLSD, SymPoint, CADSpotting, VecFormer (not stated in READMEs or the papers I read).
- Weights licence texts for HAWP, M-LSD, SymPoint v1/V2, CADSpotting: not stated. Second attempt (gh api, 2026-11-14): the HAWP checkpoints live in the `hawp-torchhub` release repo, which has no licence field and only a README; the HAWP repo's `LEGAL.md` is empty. M-LSD's checkpoints are committed inside its Apache-2.0 repo (`ckpt_models/`, `tflite_models/`), so Apache-2.0 is the natural reading but nobody wrote it down. LINEA weights sit on GitHub releases of its author's storage repo, no licence text either.
- Fine-tuning ScaleLSD or HAWPv3 on line drawings, sketches or scans (the HAWP issue tracker says to rewrite the dataset class; no report).
- A release of the Deep Vectorization cleaning model (answered by the issue tracker: never released, see table).
- Second attempts with other terms (WebSearch, 2026-11-14), same outcome: "rendered raster FloorPlanCAD image detector Mask2Former"
  (only the older rasterise-then-detect work cited second-hand in the SymPoint and VecFormer papers; the one
  comparison with real numbers is the SymPoint-V2 Table 2 above), "fine-tune wireframe detector on technical drawings
  or sketches" (only GLSP, HAWP+GNN, no code), PCB and flowchart sweeps (section 6).
- Forward citations of VecFormer (Semantic Scholar, 2026-11-14, 7 hits): TextCAD and TempFit (both already in the table), a Scan-to-BIM review (Buildings 2026, not read), "Vector-level panoptic symbol spotting" (Automation in Construction 2026, closed access, no abstract), and one raster-side hit: Deng et al., pixel-wise keypoint localization for rectangle symbol spotting in CAD images (Multimedia Systems 2026, open-access preprint, abstract only read). It spots rectangular symbols (door/window-like boxes) from images via heatmap keypoints with a local offset; full preprint read (23 pages): the dataset is equipment layouts of telecommunication cabinets (15 symbol types, 1700x1200 to 4200x3000 px images), not floor plans, so it does not bear on our task; skip.
- Retry "symbol counting exact match" (WebSearch + abstract read, 2026-11-14): AECV-Bench (arXiv 2601.04819, Jan 2026) counts doors, windows, bedrooms, toilets on 120 floor plans with per-field exact-match accuracy and MAPE; multimodal LLMs reach only about 0.40-0.55 on door/window counts (abstract). Not vector or detector work, so out of my scope (pointer for L2/L12 and for any LLM baseline); but it is the one public benchmark that scores counts by exact match, which is our metric style. Per-model numbers not read.
- Retry "CVC-FP door window per-class F1": no table found beyond what section 0 already cites (arXiv 2408.01526 Zernike/CAB numbers); the search snippet's door 0.82 / window 0.90 could not be tied to CVC-FP, so not used.
- Retries "door swing arc Hough raster" and "line segment detection thin lines scanned drawings" (WebSearch, 2026-11-14, snippets only, two older DFKI floor-plan papers and a LORIA arc-detection paper not read in full): still no accuracy number for arc-based door detection. The recurring classical recipe is to split the drawing by stroke width first (thick = walls, thin = symbols such as doors and windows; one DFKI paper uses thick/medium/thin) and to match symbol hits to wall gaps. That is a cheap, testable cue on our plans (stroke-width histogram per segment) that my section 4 probes did not use; an idea for L2/L12, not a measured result. No 2026 paper on fine-tuning line-segment detectors for drawings turned up.
- Own check of the stroke-width idea (2026-11-14, 300 dev plans, resized to 855 px, skeleton plus distance-transform width histogram in 8 bins, gradient-boosting regressor with 5-fold CV, same protocol as section 4): about 70% of skeleton pixels sit at width 1.5-2.5 px, so most strokes are one width; windows correlation 0.28, MAE 3.73 vs constant 3.84, exact match 0.07 vs 0.167; doors correlation 0.30, MAE 3.07 vs 3.26, exact 0.107 vs 0.18. Plan-level width statistics carry almost no count signal and are below the constant on exact match, like the segment-length statistics. The per-segment version was tested too (same 300 plans; FLD segments binned 3 widths x 3 lengths, median distance-transform width along each segment): windows corr 0.30, exact 0.083 vs constant 0.167; doors corr 0.27, exact 0.113 vs 0.18. Same verdict: no count signal from segment statistics, width or length. The cue may still help as a filter inside a matcher; as a plan-level predictor it is dead.
- Pointer, not mine: arXiv 2608.25608 (read in full by worker a) fuses two outputs with an "ink gate" (keep a segment only if most points sampled along it have a dark pixel nearby); that is the same verify-by-ink check a classical line channel would give a detector's boxes.
- Adjacent-field retry, P&ID (WebSearch, 2026-11-14, snippets only): a 2019 FCN-plus-Hough pipeline reports pipeline (line) detection of only 65.2%, blamed on scan noise and stray marks that Hough misreads; a rule-topology pipeline reports lines 95.25/87.91 precision/recall vs symbols 96.65/96.40, so lines are the weak element there too. Same message as my section 4: a classical line channel degrades first on noisy scans; no number transfers to doors and windows.
- Training memory for LINEA, partly answered (README read via gh api, 2026-11-14): no memory figure is stated, but the README documents single-GPU training (`--nproc_per_node=1`, mixed precision `--amp`) with a total batch of 4 and shows input-size options (square only, 320 or 480 px), and notes line attention is sparse like deformable attention. So a 12-16 GB card is plausible for small batches; unmeasured. The README's multi-size example sets `eval_spatial_size=320` while the text says 480, a typo to watch. Square-only input means a non-square plan must be padded or squashed.
- Third and fourth attempts (WebSearch, 2026-11-14, snippets only): "YOLO door window per-class AP CubiCasa5K counting error" gave only MuraNet's overall AP (91.7 AP50) and a model-card caveat that FloorPlanCAD-trained YOLOv8m may degrade on scans; "classical line detector verifies deep detector openings" gave only a patent that checks door candidates by arc-plus-line geometry and a GNN parser that uses line detection as a preprocessing step. No paper tests a classical line channel as a verifier of detected openings: the gap stays open.
- TGGLines (arXiv 2002.12428, full PDF, text read, tables are images so no numbers): 10 patent-diagram images, qualitative comparison of PPHT, LSD, EDLines and Linelet; the paper says LSD and EDLines detect double lines for thick strokes, the same fragmentation seen in 2305.16968 above. Unverified beyond that; no code checked.
- Status of the claims in this report: verified = my own probes (section 4 and the stroke-width checks), table cells I re-read in full papers, repo files read through gh api; reported = items read from abstracts, snippets or via another worker's log (AECV-Bench numbers, P&ID, door-arc, 2606-2610 ids); unverified = Raster2Seq and FloorplanVLM tables (earlier agent reads), Elsevier/IEEE/Springer/ACM abstracts.
- The WSCG 2026 raster-to-vector paper body and the TempFit paper (blocked; abstracts only or nothing).

## 8. Open questions and missing tools

- Does a Wireframe-pretrained detector (ScaleLSD v2) find wall edges on our thin-line, 855 px plans zero-shot? A
  20-image probe needs a GPU stack I did not set up (read-only run); this is the one experiment I would run first.
- Is MPL-2.0 acceptable for shipped code (record 0006 lists MIT, BSD, Apache, ISC, unmodified LGPL only)? Needed
  only if Deep Vectorization is ever considered; a ruling from the licence owner.
- The ScaleLSD weights card says Apache-2.0 while the code is MIT: fine for us, but record both.
- Pointers for other scopes: TextCAD (arXiv 2607.12678) and Raster2Seq (2602.09016) are scope L1; ArchCAD-400K
  (2503.22346) is data (L8) and has no window class; MitUNet's CIS wall dataset (Zenodo) is data (L8).
- Pointer for L2 (detect): FloorYOLO (Frontiers in AI 2026, YOLOv8n + ECA attention, 30 epochs at 640 px, read via the browser; Ultralytics code, AGPL) reports mAP@0.5 0.995 and small-object (<32 px) recall 0.998 on SESYD, a synthetic set where detectors are saturated, plus error tables on CVC-FP. SESYD-style numbers say nothing about our 5-20 px symbols on coloured, hatched plans; read the CVC-FP error table, not the headline.
- Further pointers for the data (L8) and sheet (L9) scopes, from the 2026-11-14 web search (titles and snippets only, not read): Mishra et al., robust object detection in floor plans by augmentation (Applied Sciences 2021, DFKI); a degradation generator for floor plans (SciTePress 2023); neither is mine to dig into.
- Tools missing: OpenAlex's shared daily budget ran out mid-run (HTTP 429, no key was created), no arXiv MCP, Semantic Scholar 429, Google Scholar captcha, Elsevier/IEEE/Springer/ACM pages blocked
  (abstracts via OpenAlex only), no GPU on this machine (`nvidia-smi` absent), so nothing here ran a neural
  detector.
