# lit-data-c: data, pretraining, synthetic, practical fit (L8, angle c)

Worker lit-data-c, read-only. Started 2026-11-14 00:26 by the machine clock; final version, written 01:14 after round 12 (stopped early on the orchestrator's new deadline, 01:20), see the
reading log `lit-data-c-log.md` (one line per source). "Verified" = I read it on the page named, on 2026-11-14.
"Reported" = the authors' own claim, or a number I could not check against a table. "Estimate" = mine, not measured.

Scope lines: this report extends `stoa-data.md`, the three `stoa-data-notes/` files and `06-augmentation.md`. It does not
repeat their licence rows (FloorPlanCAD, ArchCAD, CVC-FP, RPLAN, ZInD, MLSTRUCT-FP, Roboflow sets); where I re-opened a
page I say what is new. Sources that mainly belong to L1/L4/L11 get one line and a pointer.

## 0. Answer in six lines

1. The best commercial-safe training set we can assemble tonight is **a generated one**: a CC BY 4.0 set of 1,000,000
   generated plans with exact labels: door and window jamb segments (a box is segment plus wall thickness, a small conversion) and
   furniture boxes including toilet, basin, sink, bathtub, shower and hob (new, 2026-10-31, found on the Hugging Face dataset list; Sec. 1 row 2). It is clean line art at 256 px with doors
   drawn as gaps without a swing arc, so it is a pre-training stage to ablate on dev, not a replacement for the 104k dev
   boxes. No real commercial-safe set with fixture boxes exists (ResPlan has no fixtures and no WC class, ModRes no boxes,
   SYNBUILD-3D masks only; ArchCAD and FloorPlanCAD are NC).
2. Self-supervised pretraining is already inside the best candidate: RF-DETR (Apache-2.0 N/S/M/L) starts from DINOv2
   weights (Apache-2.0) plus COCO/Objects365 detection pretraining; its authors say DINOv2 init "significantly improves
   detection accuracy on small datasets" (reported, arXiv 2511.09554 Sec. 3). Two 2026 papers that compared RF-DETR with YOLO on small
   training sets show it ahead by 20 points of mAP50 or more on satellite images and by 7.8 on facade drawings (Sec. 3, 1; the YOLO there ran at 640 px against 1344x800 for RF-DETR, so the gap mixes model and input size). Do not add document pretraining: a DocLayNet-pretrained detector
   scored mAP50:95 0.589 against 0.772 for a COCO-initialised one on real engineering drawings (verified, 2607.18997 Table 4).
3. Synthetic data helps most when real data is scarce and the gain shrinks fast as real data grows: +14.9 mAP50 at 8 real
   images per class and +4.8 at 24 with 3D renders added, +16.2 and +5.3 with renders and diffusion images both (RF-DETR-M, 2604.18076 Table 2; 3D renders alone: 26.6). We have 33.5k window and 36.3k door boxes on 3,828 dev
   images, so expect a small supplement gain there and a larger one on the thin classes (bathtub 312, shower 4.6k, sauna
   stove 2.5k boxes). Nobody has measured synthetic to real on 5-20 px line-art symbols.
4. Copy-paste of real symbol crops is the cheapest idea on our own boxes, but the evidence on tiny objects is mixed: +6.9
   box AP at 10% of COCO and +1.5 at 100% (arXiv 2012.07177); class-balanced copy-paste added +0.6 AP overall and +0.9 to
   +1.9 on tail classes on VisDrone (AD-Det Table 5); on four tiny-drone sets a Nano detector with rough copy-paste moved
   mAP50 by -1.6 to +4.0 while mosaic plus HSV gave +7 to +18 (arXiv 2604.19999 Table II). Use it for the thin classes and
   ablate; do not expect it to fix windows and doors.
5. Resolution is the lever for small symbols: RF-DETR-2XL trained at 880 px scored mAP 42.04 at 880 px inference (42.17 once the score threshold is 0.02 like the rest) and 46.29
   at 2400 px (2608.24154 Table 2, rows 12-16; training at 1080 px reached 47.53, but 960 and 1000 px gave 42.95 and 45.18, so the gain is not monotonic). Licence caution: RF-DETR-2XL is under PML 1.0, not Apache-2.0, so this is evidence for the resolution effect only; the shippable sizes are N/S/M/L. RF-DETR docs and maintainers say: square input, size divisible by 32,
   slice for small objects, and move to a larger model size before raising the resolution of a small one (issue 747); so test M or L at its own
   resolution on tiles first, and raise the resolution only if the 20 px classes still miss.
6. Out for licence reasons I read myself: DEIMv2 (non-commercial), MAE code (CC BY-NC), DINOv3 weights (custom Meta
   licence, HF files gated). A trap: three Hugging Face copies of FloorPlanCAD carry a `cc-by-sa-4.0` tag while their card
   says CC BY-NC 4.0 (Sec. 5).

## 1. Top 5, ranked

| # | Candidate | Verdict | Why (one line) | Source (read 2026-11-14) |
|---|---|---|---|---|
| 1 | **RF-DETR N/S/M/L fine-tuned on dev boxes, tiled or at 880+ px, DINOv2-initialised** | **try** | Apache-2.0 code and weights; mAP50 0.949 on 551 real drawings at 1344x800 on a 16 GB T4 (YOLOv12-m 0.871, but that one ran at 640x640, so part of the gap is input size; no training times stated); mAP50 0.881 on 1,042 training images against 0.623 for the best YOLO; leakage flag no | github.com/roboflow/rf-detr README, docs, issues; arXiv 2511.09554; 2607.18997; 2512.22454; 2608.24154 |
| 2 | **Generated furnished plans (1M, CC BY 4.0) as a pre-training stage** | **try, ablate on dev** | Exact jamb segments for window and door (a box = segment widened by the wall thickness: one conversion step, card read 2026-11-14) and exact corner-pair boxes with a facing for toilet, basin, sink, bathtub, shower, hob, washer, no leakage, commercial-safe on the card; style gap (clean 256 px, door gaps with no swing arc, architect-style symbols); generator code (furniture part only on branch `room-types`, pushed 2026-10-30; icons.py read 2026-11-14: 6 line styles, grey ink 20-95, fills 226-255, 3 variants per symbol, so symbols are skia-drawn architect glyphs, not CubiCasa-style) has no licence file | huggingface.co/datasets/benikm91/synthetic-floorplans-with-furnitures-for-transcription (card, metadata); github.com/benikm91/synthetic-floorplans-for-transcription |
| 3 | **Copy-paste of real symbol crops for the thin classes, plus mosaic-style tiling and rot90/flip, on our own dev boxes** | **try (ablate)** | Zero new data; +6.9 box AP in the 10% COCO regime, +1.5 at full data (2012.07177); +0.9 to +1.9 AP on tail classes (AD-Det); mixed on tiny objects with a Nano model (2604.19999: -1.6 to +4.0 mAP50 against +7 to +18 for mosaic) | arXiv 2012.07177 (ar5iv); arXiv 2504.05601; arXiv 2604.19999; github.com/conradry/copy-paste-aug (MIT, archived) |
| 4 | **Degradation augmentation matched to our scans (Kornia GPU / Augraphy CPU, downscale, blur)** | **try (as an ablation)** | Both permissive; the best measured on/off numbers are from music scans (removing degradation +11.2 NED, Transcoda), none on drawings; Grayworld+CLAHE preprocessing gave +0.92 then -0.06 depending on inference size (2608.24154), so run it as a dev ablation | github.com/kornia/kornia; github.com/sparkfish/augraphy; RF-DETR docs; arXiv 2608.24154 |
| 5 | **FloorPlanCAD PNG copy (NC, prototype only) as a second pre-training stage for fixtures** | **maybe, after the first number** | PNG 1000x1000 with boxes already packaged (5,308 test-split samples), 20 m crops so about 50 px per metre, toilet and sink about 20 px, comparable to ours; Chinese CAD style, windows AP 0.38-0.52, weights stay local (record 0003) | huggingface.co/datasets/Voxel51/FloorPlanCAD; floorplancad.github.io; arXiv 2105.07147 Tables 4 and 6 |

Next, not in the top 5: ResPlan rendered with our own fixture glyphs (maybe: adds real layout diversity but needs a renderer
and has no fixtures or WC class), D-FINE as a backup detector (maybe), and the skip list in Sec. 2.

Why this order: 1, 3 and 4 need no new data. Row 2 is the only commercial-safe source of fixture boxes I found; one 50,000-plan shard is 3.28 GB of images plus 0.59 GB of labels
(HF file listing, sizes read, nothing downloaded) and the 5,000-plan test split is 0.33 GB + 0.06 GB, so the data work is a download and a label-to-COCO conversion.
Row 5 buys fixtures in an NC style.

## 2. Full table

Columns as the worker brief asks. "Field" = our field or where it transfers from. "Leak" = trained on CubiCasa5K or a
repackage. "h to first number" is my estimate for our dev boxes (12 GB, 16 GB), not a measurement; no source gives a
training time for these models on data of our size.

| Method / data | What it is | Year, venue | Code (licence) | Weights (licence) | Training data | Metric, benchmark, input | GPU | h to first number (estimate) | JSON field | Field | Leak | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RF-DETR N/S/M/L | DINOv2-backbone real-time DETR, NAS-found sizes | 2025-26, arXiv 2511.09554 v2 (Feb 2026) | roboflow/rf-detr, Apache-2.0 (gh API, README) | README: N, S, M, L, Seg and Keypoint Apache-2.0; Atto/Femto/Pico/XL/2XL PML 1.0 (out). HF cards Roboflow/rf-detr-{nano,small,medium,large}: license apache-2.0, datasets: coco (card read for small; API tags for the rest) | COCO, Objects365 (60 epochs, Table 6 caption); backbone DINOv2 | COCO APS 25.2/32.0/36.1 (N/S/M), 384/512/576 px; RF100-VL AP50:95 57.7/60.2/61.2/62.2 for N/S/M/L at 384/512/576/704 px (README table, re-read 2026-11-14; XL/2XL and Atto-Pico rows say PML 1.0) | batch "auto", gradient checkpointing; no memory table in the docs; M at 1344x800 trained on a 16 GB T4 (FELD paper) | 2-4 (tiled 640, S or M) | all elements, room boxes by class | transfer from general detection | no (upstream O365 images "academic purpose only", see Sec. 5) | try |
| D-FINE N-X | DETR with distribution-refined boxes | 2024-25, arXiv 2410.13842 | Peterande/D-FINE, Apache-2.0 | GitHub releases, Apache-2.0 repo; Objects365-pretrained variants recommended for custom data (issue 7) | COCO, Objects365 | COCO AP 42.8/48.5/52.3/54.0/55.8 (N/S/M/L/X), 640 px | not stated in README | 2-4 | same | general detection | no (upstream O365) | maybe (strong backup: APS on RF100-VL N/S 32.4/36.6 beats RF-DETR's 30.1/34.2) |
| DEIMv2 | DETR variant on DINOv3 features | 2026 | Intellindust-AI-Lab/DEIMv2, LICENSE.md: non-commercial only, commercial needs a separate licence | same licence covers weights | - | - | - | - | - | general detection | unknown | **skip: NC** |
| DINOv2 backbone | self-supervised ViT features | 2023, arXiv 2304.07193 | facebookresearch/dinov2, Apache-2.0 (README line 660) | same README; HF card for dinov2-base: apache-2.0. The same repo also ships X-ray and cell DINO weights under NC licences: do not use those | LVD-142M web images | used inside RF-DETR | - | - | init only | general | unknown (web crawl, unlikely CubiCasa) | try (via RF-DETR) |
| DINOv3 | larger SSL family, dense features stable to 4096 px | 2025, arXiv 2508.10104 | facebookresearch/dinov3, custom "DINOv3 License" (LICENSE.md, not MIT/BSD/Apache) | same custom licence; HF file page gated | LVD-1689M web images (17B pool) | frozen 7B + Plain-DETR COCO 66.1 at 2048 px; distilled S/B/L have no detection table | 7B does not fit | - | - | general | unknown | **skip: licence off the 0006 list, 7B unusable, small models unmeasured on detection** |
| MAE | masked autoencoder | 2021 | facebookresearch/mae LICENSE = CC BY-NC 4.0 | same repo | ImageNet | - | - | - | - | general | - | **skip: NC** |
| DiT (document SSL) | masked image transformer on documents | 2022 | microsoft/unilm, MIT | HF microsoft/dit-base card: license mit | IIT-CDIP scans | document layout | - | - | - | document analysis | unknown | skip: document-pretrained init hurt on drawings (FELD Table 4: 0.589 vs 0.772) |
| Simple Copy-Paste | paste random objects with scale jitter | 2021, CVPR, arXiv 2012.07177 | official code in tensorflow/tpu (Apache-2.0 by the GitHub API); conradry/copy-paste-aug MIT, archived 2021 | none | COCO, LVIS | COCO Eff-B7 640 px 48.5 -> 50.0 box AP (Table 2); 10% COCO +6.9 box AP on SSJ (Sec. 4.3) | n/a | 0.5 (code) | boxes | transfer from instance segmentation | no | try |
| Augraphy / Kornia / Albumentations | document-scan and photometric degradations | 2022 / 2026 / archived 2025 | Augraphy MIT, Kornia Apache-2.0, Albumentations MIT (archived), AlbumentationsX AGPL (out) | none | - | no on/off numbers on drawings (earlier 06 report, unchanged) | CPU / GPU | 0.5 | - | document restoration | no | try (ablation) |
| Generated furnished plans (benikm91) | procedurally generated plans on a 10 cm grid with furniture symbols; label = wall/door/window segments + furniture boxes | 2026-10 (HF card 2026-10-31); no paper | benikm91/synthetic-floorplans-for-transcription, **no licence file** (gh API: none), created 2026-10-16, 0 stars | n/a; dataset card cc-by-4.0 | 1,000,000 train / 5,000 val / 5,000 test plans, seeds reproducible | 256x256 uint8 (the older non-furniture set is 512 px), up to 20 px per metre; test split counts: toilet 8,021, basin 7,991, sink 5,000, bathtub 3,573, shower 4,413, hob 4,959, door 29,673 | - | 2-4 on a 50,000-plan shard plus regeneration at a larger size (estimate) | windows, doors, toilet, sink, shower/bath | our field (synthetic) | no | try (ablate) |
| FloorPlanCAD, Voxel51 PNG copy | 5,308 test-split samples, PNG 1000x1000 RGBA with boxes and masks | HF upload 2025-11-04 | FiftyOne loader | n/a; YAML tag cc-by-sa-4.0 but card body CC BY-NC 4.0 | cropped 20 m x 20 m blocks | 30 classes (same as Table 6) | - | 4-6 (estimate) | fixtures, doors, windows | our field | no overlap stated | maybe |
| ResPlan renders | CC BY 4.0 vector geometry rendered to PNG | 2025, arXiv 2508.14006 v2 (4 Aug 2026), preprint | m-agour/ResPlan, MIT (code) | n/a | 17k plans, 27k collected, 37% rejected | classes: living, bedroom, bathroom, kitchen, balcony, storage, stair, garden, parking, pool + wall, door, window, front_door; no WC | - | 3-4 renderer, then training | windows, doors, rooms | our field | no | maybe |
| FloorPlanCAD (original release) | CAD drawings, 30 classes | 2021 ICCV, arXiv 2105.07147 | no repo licence; site CC BY-NC 4.0 | none | 15,663 drawings, 10,161/5,502 | Faster R-CNN R101 mAP 0.452, FCOS 0.453, YOLOv3 0.413 (Table 4) | - | 4-6 incl. SVG to PNG (estimate) | fixtures, doors, windows | our field | no overlap stated | maybe |
| ArchCAD-400K | 413,062 chunks of 14 m x 14 m | 2025 NeurIPS, arXiv 2503.22346 v3 | ArchiAI-LAB/ArchCAD: licence NOASSERTION by the GitHub API; README: public release is a 40K-sample subset; HF dataset metadata: cc-by-nc-4.0, manually gated | HF dataset gated manually, cc-by-nc-4.0 (HF API, read 2026-11-14; files unreadable for me) | 5,538 drawings, residential 14%, country unstated | pretraining only speeds convergence on FloorPlanCAD (Fig. 6a); no PQ gain stated | - | - | - | our field | unknown | skip (NC, gated, subset size unstated) |
| SFPI (synthetic furniture) | 10 SESYD layouts x 1000 randomised images | 2021, Applied Sciences | not released in the PDF | none | SESYD layouts | train SFPI test SESYD mAP 0.750 vs 0.995 in-domain; SFPI 10k + 500 SESYD 0.997 | - | - | - | our field (but furniture, not fixtures) | no | skip, evidence only |
| SYNBUILD-3D | 6.28M procedural buildings with plan images and pixel masks | 2025, arXiv 2508.21169 | kdmayer/SYNBUILD-3D, CC-BY-4.0 (gh API) | n/a | Wu 2019 plan generator | masks for room/wall/door/window, no boxes, no fixtures | - | - | - | our field | no | skip |
| ModRes | cleaned ResPlan (8,431 plans) with new graphs | 2026, arXiv 2610.17178, preprint | emmashelley/ModRes, MIT (gh API, LICENSE file read); data is ResPlan's CC BY 4.0 | n/a | - | no boxes, no fixtures, no baselines | - | - | - | our field | no | skip |
| Co-DETR counting of doors and toilets | exact per-image count on CubiCasa5K | 2025, arXiv 2509.17283 | no code | no weights | two unnamed public sets, 1884 train | toilet exact-count accuracy 87.63 on 97 CubiCasa5K images | - | - | toilets, doors | our field | probably yes (unnamed sets) | reference only |
| CubiCasa5K weights | authors' 2019 net | 2019 | CubiCasa/CubiCasa5k LICENSE: CC BY-NC 4.0 | Drive link; data on Zenodo: cc-by-nc-sa-4.0 | CubiCasa5K | 53.1% overall zero-shot (measured earlier) | - | - | - | our field | **yes** | analysis only |

## 3. What each candidate adds to the earlier measurements (sections 2 and 3 of the context)

- Earlier: the authors' 2019 net gives windows 32%, doors 36.7% exact; the count-only FCN gives 18% on both. New: the
  only exact-count numbers for a box detector on CubiCasa5K that I found are toilets, 87.63% on 97 images
  (arXiv 2509.17283 Table 1, verified), against 79.4% for the 2019 weights on our dev. That is a different image set and
  the training sets are unnamed, so it supports "toilets above 85% is plausible with a box detector", not a forecast.
- Earlier: "No paper reports per-image exact counts or AP for toilet/sink/shower/sauna from a box detector". New:
  FloorPlanCAD Table 6 gives image-detector AP per class (verified): toilet 0.666/0.599/0.664, sink 0.468/0.470/0.384,
  bath 0.422/0.446/0.430, bath tub 0.259/0.248/0.215, window 0.518/0.465/0.379 (Faster R-CNN, FCOS, YOLOv3). Windows
  sit near 0.4-0.5 AP on CAD line art, well below single and double doors (0.74-0.86) and toilets. It does not say which raster input the
  detectors received, so I cannot say what resolution those numbers need.
- Earlier: RF-DETR AP_small 25.2/32.0/36.1 (COCO, N/S/M; L 39.0). New, re-read in the full paper text on 2026-11-14: on
  RF100-VL (100 datasets, Table 4) AP_small is 30.1/34.2 for RF-DETR N/S against 32.4/36.6 for D-FINE N/S and 4.7-7.3 for
  YOLOv8/v11 N-M, so D-FINE is not worse on small objects and is a real second candidate. Table 5 (ablation, COCO):
  switching LW-DETR's backbone to DINOv2 raised AP 51.6 to 53.6 and APS 31.7 to 34.3; Objects-365 pre-training added
  +0.7 AP and +1.5 APS (35.8); resolution 640 to 576 cost 0.8 AP and 1.5 APS. Table 6: DINOv2 54.3 against 52.3 for the
  CAEv2 backbone (the caption says 2.4%, the table gives 2.0 AP). Pretraining recipe (appendix): lr 1e-4, batch 128,
  per-layer decay 0.8 on the DINOv2 backbone, gradient clip 0.1; the training grid goes up to 960 px. None of this is on
  5-20 px line-art symbols.
- Earlier: no resolution/tiling practice found. New: the maintainers advise slicing (SAHI-style) for 4k images and small
  objects (issues 747, 879), input is square and a resolution must divide by 32 (docs FAQ), and an experiment showed no
  accuracy difference between squashed square and 3:4 input once pretrained weights load (issue 1052). In the 2026 FELD
  benchmark RF-DETR-M ran at 1344x800, so non-square input worked there too. Our median sheet is 855 px, so tiling
  into overlapping 640 tiles or training at 1024 square are both inside what has been done.

- New, RF-DETR on small data (all 2026, all verified in the paper text): (a) 1,042 training images, 640 px, up to 50
  epochs: RF-DETR-L mAP50 0.881 / mAP50:95 0.632, RF-DETR-Base 0.826 / 0.525, best YOLO (v8s) 0.623 / 0.420
  (arXiv 2512.22454, Sec. 4.1; satellite images of substation components, no AP_small, GPU not named). (b) 360 real
  training images, 960x960, 80 epochs, batch 12, RF-DETR-M: mAP50 62.9 with 8 real images per class and 83.1 with 24
  (arXiv 2604.18076 Table 2). (c) RF-DETR-2XL at 880 px training: mAP 42.04 at 880 px inference, 44.40 at 1920, 45.71 at
  2200, 46.29 at 2400 (arXiv 2608.24154 Table 2 rows 12-16); training at 1080 px needed batch 1 on a 16 GB T4 there.
  None is a floor plan; (a) and (b) are the closest evidence to our 3.8k-image regime.
- New, memory and speed (RF-DETR issues, read 2026-11-14; reported by users and maintainers, not measured by me): a user
  trained RFDETRLarge at 2.1-2.7 it/s with 1,307 iterations per epoch on an RTX 5090 (about 8-10 minutes per epoch, batch
  size not stated, issue 1544; re-read in round 12: that run was image-loading bound, 4500x4500 colour PNGs at resolution 1120, the
  maintainer measured 1.5-1.8 s per batch in the DataLoader alone and advised resizing images offline to the training size, so it is
  NOT a GPU speed figure for our 855 px sheets); a maintainer ran RFDETRLarge at batch 4-8 on 800 images on a 12 GB RTX 5070 (same issue);
  version 1.11 needs about 5% more memory than 1.10. Images with about 500 boxes each slow training and exhaust memory in
  the bipartite matcher, and the pretrained heads hold 300 queries, so maintainers advise splitting images into chunks
  (issue 472). Our sheets carry tens of boxes, tiles fewer. My estimate for a first number: Small or Medium at 640-ish
  tiles of the 3,828 dev images, 2-4 hours on the 12 GB card for 30-50 epochs; it rests on no clean speed measurement (the only user figure was data-loading bound), so treat it as a guess and time one epoch first.
- New, rotation: the RF-DETR augmentation wrapper lists `RandomRotate90` among the geometric Albumentations transforms it
  handles together with boxes (src/rfdetr/datasets/transforms.py, line 115, read 2026-11-14), so the agreed rot90 plus flip
  training augmentation needs `rfdetr[augment]` and an `aug_config` dict, no code. The default stack is only a horizontal
  flip at 50% plus a resize-crop-resize branch.
- New, from scratch versus pretrained at our data size (He et al., arXiv 1811.08883, verified): random init matches
  ImageNet-pretrained on 10k COCO images (25.9 vs 26.0 AP, with 220k iterations) and on 35k, and breaks down between 3.5k
  and 10k images (3.5k: 16.0 vs 9.3 AP). Our 3,828 dev images sit at the edge of that range, but they carry about 27
  boxes each (104k boxes); the paper argues pixels and instances matter more than image count. Conclusion for us: start
  from pretrained weights (RF-DETR does), do not train from scratch, and expect the pretrained start to matter most on
  the thin classes.
- New, what the synthetic data adds as real data grows (arXiv 2604.18076 Table 2, RF-DETR-M, mAP50, 8 / 24 real images per
  class): real only 62.9 / 83.1; real + 3D-model renders 77.8 / 87.9; real + diffusion images 70.9 / 85.9; both 79.1 /
  88.4; synthetic only 26.6 (renders) and 48.8 (diffusion) at 8 real. The gain falls from +16.2 to +5.3 as real data triples.
  Our dev set has 3,828 real images, far past that range, so I expect single-digit gains at best on frequent classes.
- New, how much synthetic to add when real data is already thousands of images (arXiv 2607.27058, Chinese rural driving scenes with Unreal Engine synthetic images, not drawings; 4,200 real training
  images, 517 real test images, mAP@0.5, real only / 1:0.5 synthetic / 1:1): YOLO11m 0.733 / 0.758 / 0.707, YOLOv8m 0.714 /
  0.736 / 0.699, YOLOv5mu 0.747 / 0.743 / 0.704, RT-DETR-L 0.736 / 0.692 / 0.691. So at our real-data size a half-size
  synthetic supplement moved the score by -4 to +2.5 points and an equal-size one hurt in every row but one. For
  small objects with only 300 real instances (arXiv 2401.12729, objects under 32x32 px, 1080 px): YOLOv5 APs 0.493 real
  only, 0.594 with +50% synthetic, 0.607 with +100%, and 0.083 synthetic only; more synthetic data lowered YOLOv7 and SSD
  (best point +50%). Rule I take from four data points (2604.18076, 2607.27058, 2608.25608 from 2026 and 2401.12729 from 2024; none on drawings): keep
  synthetic at or below half the real count, mix from the start, and judge on dev.
- New, how fast a generated set transfers between two generated styles: SFPI to SESYD mAP 0.750 against 0.995 in domain
  (Mishra 2021 Table 5). For P&ID drawings, 665 generated diagrams with topology copied from real seeds reached node
  mAP@0.5 64.2 against 67.8 for a 12-image real oracle, and 71.3 with real images added (arXiv 2604.16513 Table 3; the
  abstract says "within 8 pp" but its own tables give 5.6). Both are small real test sets.

## 4. From other fields: transfer notes

| Field and task | Plays the role of our object | Why it should transfer | What breaks on our images | Code and weights |
|---|---|---|---|---|
| Natural-image instance segmentation: Simple Copy-Paste (COCO, LVIS) | a window cell or a toilet crop pasted onto another plan | random paste with scale jitter helped most when labelled data was scarce; no context model needed | pasted crops carry the source's line weight and paper tone; pasted symbols may cover wall lines and make a door arc ambiguous; overlapping pasted symbols change the "one cell per window" counting rule; rot90 copies must keep the swing direction label-neutral | idea plus MIT implementation; no weights needed |
| Document OCR and layout: DocLayNet/DocSynth-pretrained detectors | not a role; a negative result | - | document-pretrained weights lowered mAP50:95 from 0.772 to 0.589 on engineering drawings (verified, 2607.18997 Table 4): "domain interference" | skip |
| Emergency-plan symbol detection (Hassaan, Sensors 2023) | 403 real plans, 5000 synthetic from 200 of them by pasting symbols into cut-outs, Gaussian blur matched per cut-out | same recipe as copy-paste; synthetic-trained model found two rare classes the real-trained model missed (verified, PMC10575354 Sec. 4.4) | metric is class-averaged IoU, not mAP; both models come from the same 200 plans; no mixed run; data on request only | idea only |
| Synthetic furniture plans (Mishra, Applied Sciences 2021) | SFPI, 10 layouts x 1000 randomised images, Cascade Mask R-CNN | quantifies the gap between a synthetic set and another synthetic set | synthetic-only to other set 0.750 mAP against 0.995 in-domain; 500 target images brought it to 0.997; SESYD is itself synthetic, so no real scan was ever tested | idea only |
| Industrial inspection: domain randomisation for synthetic-only training (Zhu et al., ICRA 2025, arXiv 2506.07539) | a symbol rendered with random distractors, noise and blur | measured which randomisations mattered: removing distractors cost 7.5 mAP50 and removing noise/blur post-processing 6.4 on the robotics set (Table V); path tracing with PBR textures 96.4 against 89.6 raster; gains flatten past about 1.5k images per category | renders are photographic (Blender); for line art the equivalent knobs are distractor lines, line-weight jitter, noise and blur, which are exactly the Augraphy/Kornia set; test sets are 190 and 321 images | idea only; code at github.com/jacobhenningsson95/SynMfg_Code (licence NOASSERTION in the GitHub API) |
| Industrial drawings: SynthPID (P&ID digitisation, arXiv 2604.16513) | a valve or pump symbol in a diagram | generated diagrams with topology copied from real seeds got within 3.6 node and 5.6 edge points of a real oracle (node mAP@0.5 64.2 vs 67.8, edge mAP 63.8 vs 69.4) and real images on top added about 7 node points (71.3) | 12 real images only; the paper has no ablation of line width, fonts or noise and no mixing-ratio sweep; the repository URL in the paper returned 404 for me | idea only |
| Low-data detection with diffusion images (arXiv 2604.18076) | a rare class | equal-frequency mixing of real, renders and diffusion images with RF-DETR-M | photographic classes; diffusion models do not draw exact line art, so for counting they are the wrong tool; no licence for code or data | idea only |
| Small-object detection from aerial images: zoom into clusters of small objects (AD-Det, Remote Sensing 2025) | a cluster of windows or doors on a facade | ASOE, which finds regions dense in small objects and re-detects them at a finer scale, added +2.2 AP and +3.2 AP_S on VisDrone (Table 5), about four times the overall gain of the class-balanced paste (+0.6) | our objects are on line art, so the density cue is the wall mask, not a feature map; no code link | idea only; the tiling rule is what RF-DETR maintainers also advise (issues 747, 879) |
| Optical music recognition: rendered scores to real scans (Transcoda, arXiv 2605.10835; Smashcima study, arXiv 2606.09479) | a notehead or accidental on a staff | the closest measured sim-to-real ablation: removing the Augraphy/paper/perspective degradation cost +11.19 OMR-NED on 102 real scans (65.76 to 76.95), removing page-density matching (concatenating short scores to fill the page) cost +14.34; synthetic-only still left 65.76 against 18.71 on synthetic; with a recogniser, pretrain + synthetic + 59 real systems reached SER 33.2-34.8 against 41.3 real-only | the models are sequence recognisers, not detectors; the real test sets are 102 scores and 50 systems; "asymmetric augmentation" is not defined in the text I read; for us density matching means per-plan counts of windows and doors, and sheet layouts with several plans | idea only; Augraphy is MIT (checked); Transcoda code at github.com/btrkeks/transcoda, licence not read |
| Historical maps: synthetic maps rendered from vector data, then degraded (arXiv 2511.15875) | small map symbols and text on aged paper | compared three ways of degrading the clean render for synthetic-only training: random blur/crop/dust overlay (IoU 0.644, below the clean 0.654), CycleGAN translation (0.686, best), UNSB (0.615); style-transfer FID 100.7 against 44.5 for UNSB | single runs, segmentation not detection, no real-only baseline, nothing mixed; learned translation can invent strokes, which would break exact counts | idea only; repo hcu-cml/bootstrap-HistoricalMap, licence not read |
| Wall vectorisation (fpvec-lab, arXiv 2608.25608): mix of CubiCasa5K and synthetic 1:1 | whole plan, not symbols | one of the few 2026 papers that mixes synthetic and CubiCasa5K | +1.2 wall F1 at 0.05 tolerance but different rosters (n=290 vs 287), so not a clean gain; walls only (L4/L11 topic, pointer only) | paper PDF read for the 0.769 / 0.781 rows (round 7); repo fpvec-lab not opened |

Round 5 (repo issues, read 2026-11-14): RF-DETR open issues. #879 (small objects): a maintainer says there is no fixed minimum size and the best approach is cropping into patches; #1001: v1.6.4 may silently fall back to a different resolution (resolution=320 and 640 on Nano gave different mAP, so check what resolution the log reports, and use a multiple of the model's patch size); #974: v1.6.4 trained about 2x slower than 1.5.0 on one user's 18,000-image set, the maintainer points to an effective batch size of 16 (batch_size x grad_accum) as the setting to keep; #780: segmentation plus SAHI tiling at 1900-2200 px is slow and misses cells in dense tiles. For us: pin the version, log the real input resolution, tile the small-fixture classes. Issue 1052 (re-read in round 12, full thread): a user first measured about 20% better accuracy with a 3:4 input than squashed square, then found they had not loaded the pretrained weights at all; with the weights loaded the two gave no difference. Trap to avoid: check in the log that the pretrained checkpoint loaded, a fine-tune without it still gives plausible numbers. The maintainer's advice stays: squash to square unless images are pathologically long and narrow (our sheets are not, except if we tile strips); #747: the input file size does not matter, object size does, and prefer a larger model size over raising the resolution of a small one (the models come from a NAS that scales resolution with other parameters).

Round 5c (rf-detr releases, gh API, read 2026-11-14): latest 1.12.1 (2026-11-12), 1.12.0 (2026-11-06), 1.11.x (September-October 2026): the repo is moving weekly. 1.12.1 is a drop-in upgrade that makes bad config values (epochs, ema_decay, drop_path, warmup_epochs) and NaN or non-finite YOLO label values fail early with clear errors, which helps a label-conversion pipeline. For us: pin one release for the whole hackathon run (earlier issue 974 reports a slowdown between 1.5.0 and 1.6.4) and read the release body before upgrading.

Round 5b (rfdetr.roboflow.com training-parameters page, latest, read 2026-11-14 via pwfetch): detection checkpoints take resolutions that are multiples of 32 (rule: divisible by patch_size x num_windows; a search summary said 14, the page says otherwise), so 1024 is valid in principle but documented sizes are 384-704 and larger sizes cost memory. The docs list effective batch 16 as batch x accumulation: A100 16x1, RTX 3090/4090 8x2, T4 16 GB 4x4, RTX 3070 8 GB 2x8 (illustrative, not guarantees; a 12 GB card is not listed, estimate 3-4 x 4-5 at 704). `batch_size="auto"` probes the GPU. Defaults changed: grad_accum_steps is now 1 (was 4), so the default effective batch is 4, not 16: set it. AMP is bf16 on Ampere and newer. This fills the memory gap from Sec. 6 only as vendor guidance, not as a measurement for us.

Round 6 (adjacent field, industrial and electrical diagrams; read 2026-11-14): Chalmers master's thesis 2026, "Beyond the Legend" (Stroem; odr.chalmers.se, 79 pages, text extracted and read in the synthetic-data, results and discussion parts, not every chapter). Detectors (YOLO, Faster R-CNN, RT-DETR) were trained only on 10,000 synthetic 1024x1024 diagrams of generic shapes (circles, rectangles, triangles, crosses, lines, composites) mapped to one "symbol" class, then tested on real electrical diagrams. Reported result in the author's words: the models transferred from generic shapes to real symbols with high recall, but made many imperfect boxes and false positives, because the synthetic noise was simpler than real wiring (lines that touch, overlap and make ambiguous symbol edges) and the synthetic pages held more symbols than a real 1024 px slice, which raised recall and cut precision. Per-class F1 fell with average box pixel area (their Fig. 4.4; small symbols are 20x15 px). What breaks on our images: the same would happen with generated plans whose walls are cleaner than scans, so judge pre-training on dev precision at a fixed recall, not on recall alone; and the thin classes (small fixtures, 20 px class) will be the first to fail. Tables 4.2/4.3 (read at the end of round 12; verified in the thesis text): on 7,799 real symbols the best one-pass F1 is only 0.33-0.35 for every detector (RT-DETRv2 precision 0.249 / recall 0.572; YOLOv8 0.220 / 0.804; Faster R-CNN multiscale+WBF 0.151 / 0.875), so the synthetic-only generic-symbol detectors find most symbols but with roughly four false boxes per true one; a second refinement pass barely changed precision. No AP is reported, so no mAP figure is quoted.
Also seen on the web (title level only, not opened, not used): several Roboflow Universe floor-plan fixture sets (233 to 10,334 images, mixed licences). Record 0003 says no Roboflow data, so they stay out of the plan.

Round 7 (new 2025-2026 detector-on-plan papers from an arXiv API title search "floor plan" AND detection, read as PDF text 2026-11-14): (a) SkeySpot, arXiv 2508.10449 (Aug 2025): 45 scanned electrical layout plans, 2,450 instances, 34 symbol classes; 5-fold cross-validation, 80/20 split, test fold 13 plans with 598 instances; fine-tuned from COCO weights, 200 epochs, albumentations flips/rotations; Table II mean over folds: Faster R-CNN mAP50 48.62 / mAP50-95 26.13, YOLOv8 mAP50 81.12 / mAP50-95 48.24 (the abstract's 82.5% mAP50 is the best of the five fold models, Table III; the conclusion gives the average as 81.1%). Closest measured size analogue to ours (a few dozen real plans, small symbols, many classes): a COCO-pretrained one-stage detector on tens of plans gets mAP50 around 0.8 but mAP50-95 only about 0.5, so the box tightness, not the finding, is what small symbols cost. Caveat: YOLOv8 is AGPL-3.0 (not shippable under record 0006); read here as an accuracy figure only. Dataset licence not read (a GitHub link is in the paper; not opened). (b) 2608.14317 (Aug 2026, IEEE Access template): Mask R-CNN on 1,000 hand-annotated floor-plan images, lighting symbols, image slicing, bbox mAP 0.7596 / mAP50 0.9850; one class family, no ablation on data size, no licence statement; adds nothing to the ranking. Seen by title only, not used: DoorDet 2508.07714 (door detection with an LLM, L-door scope), ARCH-B 2609.34047 (a benchmark, not opened).

Round 7b (arXiv API title search "symbol spotting", 2025-06 onward): new 2026 items are all CAD-vector or other scopes: TempFit 2610.17776 (Oct 2026, panoptic symbol spotting by retrieving a template from a library and predicting its pose; vector CAD input, read to the abstract and figure caption only) and 2607.12678 (text-aided panoptic symbol spotting on CAD floor plans) belong to L11 and the vector-extraction angle; 2609.07159 is manuscripts. Pointer only. TempFit's idea (a fixed library of canonical symbol templates plus pose) is the vector twin of copy-paste with a glyph library.

Round 8 (D-FINE repo, Apache-2.0 by gh API, 3,405 stars, last push 2026-10-05, 166 open issues; issues read 2026-11-14): #214 a Roboflow staff member reported sub-5% mAP and crashes when fine-tuning D-FINE with the repo's finetune config on RF100 datasets, with and without Objects365 weights (thread has no resolution from the maintainer in what I read; the RF-DETR paper later reports D-FINE on RF100-VL, 32.4/36.6 APS, so the config problem was evidently solved on their side but costs setup time); #169 the maintainer advises fine-tuning complex datasets from the Objects365 checkpoint, not the Objects365+COCO one, and training from scratch for datasets with few, simple classes; #343 fine-tuning needs contiguous class indices from 0. For us: D-FINE fine-tuning has more setup friction than RF-DETR's packaged trainer; it stays the backup.

Round 9 (adjacent field, industrial sim-to-real; arXiv 2511.23241, Procedia CIRP 2025, read 2026-11-14 as PDF text, abstract and method parts): six ways to close the gap for detectors trained only on rendered images (Blender domain randomisation, perceptual-hash filtering, brightness filtering, Stable Diffusion XL image-to-image with depth and canny conditioning, and variants), on a proprietary automotive/logistics set and a public robotics set. Reported: when the render set has enough variability, picking the rendered images closest to a few real ones by perceptual hash gave the best mAP50 (98% and 67% on the two sets) and diffusion adaptation cost far more time with no clear gain. For us: a cheap, permissive way to use the generated furnished plans is to keep only the generated plans whose perceptual hash (or any image embedding) sits near our dev plans, instead of training on all 1,000,000; this goes into the ablation list for row 2 as "filtered vs unfiltered 50,000". Not a drawings paper, so a transfer by analogy, estimate only.
Also searched (no hit): scan-degradation (Augraphy-style) ablations on technical drawings with real-scan AP. The nearest is a 2022 text-detection paper on synthetic technical drawings (arXiv 2205.02659; round 10: read in full text, see below).

Round 10 (arXiv 2205.02659, Procedia CIRP 2022, older than the 2025-2026 window; read as PDF text 2026-11-14): engineering drawings, detector for dimension and tolerance text boxes. A domain-knowledge generator draws pages with geometries and labels, using elements (including hatchings) cut out of 9 real drawings; 2,000, 5,000 and 7,000 generated pages were each compared with training on the 9 real drawings, validated on 9 other real drawings (mAP at IoU 0.5, curves only, no numbers in text). Reported: the 9-real model was not functional (detection rate 4.67% against the best generated-data model; the generated one also beat out-of-the-box Keras-OCR on detection and by 33 points on digit reading), 2,000 pages was worst, 5,000 and 7,000 were close, so returns shrank past about 5,000 pages. What breaks on our images: test set is 9 drawings (curves, no table), text not symbols, no mixed run, the generator is not released. What transfers: real cut-outs pasted into generated pages (same recipe as Hassaan 2023 and our copy-paste row), and a size rule of thumb: tens of thousands of generated pages are plenty, which matches using one 50,000-plan shard of the generated set and not all 1,000,000.

Round 9b (licence gaps, read 2026-11-14): ModRes repo emmashelley/ModRes has an MIT LICENSE file (copyright 2026), pushed 2026-07-28; it holds code, geometry, graphs and a demo notebook; the README says nothing about the underlying ResPlan CC BY 4.0 attribution, so the data licence is still the ResPlan one (CC BY 4.0 over annotations). SynthPID: the paper names git@github.com:LatentSpaceIITB/SynthPID.git (code, generator and weights); the public GitHub API returns 404 for LatentSpaceIITB/SynthPID (private or never published), so no licence is readable and it cannot be used.

Round 11c (search for rotation/flip ablations on plans, read 2026-11-14): none found for box detection on plans. SkeySpot (Round 7) applies flips and rotations without an isolated ablation. Laudari and Baek, arXiv 2603.14764 (Mar 2026, CC BY 4.0, PDF read): polygon augmentation for floor plan segmentation; rotation, crop and flip can split a region with a void into pieces, and their repair raises CAP (annotation connectivity) from 0.55 to 0.98 under rotation (Roboflow augmentation 0.5497) and mIoU by 2.4 (YOLOv11-Seg 88.4 to 90.8) and 1.8 (Mask R-CNN 85.2 to 87.0) on about 2,000 Korean floor plans ( code github.com/Laudarisd/polyaug, licence not read). Only relevant to room polygons (L4); box labels for windows, doors and fixtures stay valid under rot90 and flip, so the rot90 augmentation in Sec. 3 needs no repair. Also, the DFKI 'Towards robust object detection in floor plan images' result is the Mishra 2021 paper already in Sec. 3.

Round 11 (Hugging Face dataset list, newest first, searched 2026-11-14 for floor plan, floorplan, architectural drawing, blueprint, CAD drawing; metadata and two cards read): the only new commercial-safe image sets near our task are three captioning sets by jotamunz (cc-by-4.0, Nov 2026, plans drawn by the same generator as the benikm91 furnished set, each row holds its plan's record; text captions and node/relationship questions, not boxes), so they add no labels we can use for detection and confirm the generator is in use by others. saiashish29/FloorPlanCAD is one more FloorPlanCAD copy tagged cc-by-nc-4.0 (consistent with the NC reading). cadsy/cad-technical-drawings (apache-2.0, 130 mechanical drawings with annotation boxes generated from STEP models) is mechanical, not building plans: no use. Others in the list had no licence or no relation (3D, RL, kitchen simulator).

## 5. Licence and leakage notes (read myself)

- ResPlan LICENSE (read): data CC BY 4.0 over "the annotations, the semantic taxonomy, the room-connectivity graph
  construction..."; no licence is asserted over the spatial arrangements; takedown by plan ID; code MIT. Plans come from
  "publicly accessible real-estate listing renderings" (provenance is the authors' claim). The paper (v2, 4 Aug 2026) is
  a preprint; its "500-plan audit" measures plausible room area (83.1%), not label accuracy.
- CubiCasa5K: the repo LICENSE says CC BY-NC 4.0; the Zenodo record says cc-by-nc-sa-4.0 (API read). Record 0003 and two
  2026 papers say NC-SA. Either way NC.
- Re-verified through the Internet Archive copies (the live sites time out or refuse): CVC-FP, 122 scanned plans in 4
  subsets, ground truth for rooms, walls, doors, windows, parking doors and room separations only (no fixture classes), page
  footer licence "CC BY-NC 4.0" (the sentence says "Attribution 4.0" and the abbreviation says NC: treat as NC). SESYD
  floor plans: 10 datasets, 1,000 images, 28,065 symbols of 16 models, synthetic, no licence statement on the page.
  Neither helps our fixture classes.
- Objects365: the download page says "available for the academic purpose only", annotations CC BY 4.0, images not owned
  (Flickr terms). RF-DETR and the D-FINE O365 variants are pretrained on it. The released weights are Apache-2.0 by their
  publishers; the upstream data terms are an open question for the orchestrator, not something I can resolve.
  COCO has the same Flickr-terms character.
- DINOv2: Apache-2.0 for code and the main weights (README line 660; HF card). Its README also carries NC licences for the
  X-ray and cell models in the same repo.
- Hugging Face copies of FloorPlanCAD (checked 2026-11-14): `Voxel51/FloorPlanCAD` and three re-uploads
  carry the YAML tag `license: cc-by-sa-4.0`, while the card body of the same files says "Creative Commons
  Attribution-NonCommercial 4.0" and lists commercial applications as out of scope. The original site says CC BY-NC 4.0 and
  "we do not own the copyright of the drawings". Treat all copies as NC; do not copy the tag into the submission form.
- Generated furnished plans: the dataset card says `cc-by-4.0` (YAML on the HF page); the generator repository has no
  licence file on either branch (GitHub API returns none; furniture code only on branch `room-types`). Data is therefore usable on the card's terms; the code is "all rights reserved"
  by default, so do not copy it into the repo, and ask the author before regenerating at another size if the submission
  needs a clean chain.
- RF-DETR README (re-read 2026-11-14) states in its own words: "Commercially usable under Apache 2.0" for the `rfdetr` package, Nano/Small/Medium/Large detection, all Seg sizes and Keypoint, "you can ship them in closed-source, commercial products"; Atto, Femto, Pico, XL and 2XL sit in `rfdetr[plus]` under PML 1.0. This is the vendor's explicit grant, which covers the trained-weights question except for the upstream Objects365/COCO image terms (open question 1).
- RF-DETR dependencies (pyproject read 2026-11-14): core and the `train` and `augment` extras list torch, torchvision,
  supervision (MIT), pytorch_lightning, peft, torchmetrics, pycocotools, scipy, simplejpeg, albumentations (2.0.8, MIT),
  kornia, roboflow, faster-coco-eval (Apache-2.0 by the GitHub API), torch-hungarian (Apache-2.0 by the GitHub API; PyPI
  licence field empty); no GPL or AGPL package found. Do not install `rfdetr[plus]` (PML 1.0 models) or AlbumentationsX.
- DINOv3: custom licence ("DINO Materials", redistribution only under the same terms, trade-control clauses): not MIT/BSD/
  Apache, so by record 0006 it cannot be shipped.

## 6. Looked for and did not find (second attempts noted)

- A paper that trains a box detector on synthetic floor plans and reports AP on real scans of another style. Second try (arXiv
  title/abstract searches "floor plan synthetic", "floorplan synthetic detection", "symbol spotting synthetic", HF dataset list):
  nothing new. Closest: Hassaan (IoU, not AP) and Mishra (synthetic to synthetic). Outside floor plans, the measured analogues
  are in Sec. 3 and 4.
- Self-supervised pretraining evidence on drawings. Second try (arXiv "pretraining AND CAD drawings", "masked autoencoder AND
  drawings/floor plans/blueprints", a web search for DINOv2/DINOv3 on drawings): only FloorplanMAE (arXiv 2506.08363, floor plan
  generation from partial plans, L1/L4 pointer) and 2510.11091 (text-enhanced symbol spotting, L11 pointer). The one negative
  result is document pretraining hurting on drawings (2607.18997). FCMAE pretraining on 200k unlabelled scans helped OMR by
  5 NED points (Transcoda Table 3b), which is the only measured SSL gain I found on a line-drawing-like field. Round 11b search: one more 2025 paper, Hain et al., ECML-PKDD 2025 (Springer, paywalled, abstract only from mlanthology): contrastive self-supervised learning from the unique entries of a diagram's legend to classify symbols; it is classification, not detection, and I could not read its numbers. Same legend-driven idea as the Chalmers thesis (Round 6); a floor plan legend, where one exists, could give a cheap crop library.
- A GPU-memory table for RF-DETR or D-FINE at 1024 px (round 5b: the vendor docs give batch x accumulation per card, nothing at 1024 px or for 12 GB). Second try (GitHub issue search): only anecdotes (Sec. 3, speed and
  memory). No official figure.
- A real-to-synthetic ratio for small symbols on drawings. Second try found four 2026 and 2024 detection data points (Sec. 3),
  none on drawings.
- Training time of RF-DETR on a dataset of our size on a 12 GB card: one 5090 data point (about 8-10 min per epoch, batch not
  stated, and image-loading bound, see Sec. 3); no clean measured figure for our card: time one epoch first.
- ArchCAD-400K dataset licence: found in round 9 via the Hugging Face API (no login needed for metadata): jackluoluo/ArchCAD is
  tagged and carded license cc-by-nc-4.0, manually gated, last modified 2025-10-17. So non-commercial: prototype only under
  record 0003, same class as FloorPlanCAD. Public subset size: the GitHub README says 40K samples; the repo licence is NOASSERTION.
- Whether ResPlan, SYNBUILD-3D or the generated furnished set share a source with CubiCasa5K: none says so (ResPlan: South
  Asian listings; SYNBUILD-3D: Wu 2019 generator; furnished set: generated from seeds).
- Image-level look at the generated furnished set and the FloorPlanCAD PNG copy: not inspected (rule: no downloads). Style
  claims come from the cards and from reading the drawing code.
- Citation walk forward. ResPlan: Semantic Scholar (14) and OpenAlex (15) agree, all 2025-26, none trains a detector on
  ResPlan renders. RF-DETR: the arXiv full-text search listed 36 papers since Nov 2025 and OpenAlex 140 citing works; the only
  drawing paper is 2607.18997 and the small-object work (FSDC-DETR, FDQ-Det, TinyFormer 2605.25046) is for L2. Copy-Paste
  forward walk: arXiv search "copy-paste AND small/tiny/symbol/drawing/document" (2025-26 hits: AD-Det, 2604.19999,
  2507.06321 fire segmentation); OpenAlex hit its daily limit before I could list citing works.

- Circuit/PCB schematic symbol detection, synthetic vs real (searched 2026-11-14 round 4): no 2025-2026 paper with a direct table; nearest are SynthPID (read) and a 2023 single-line-diagram YOLOv5 paper (abstract only, unread). The P&ID line in Sec. 4 stays the evidence for this field.

## 7. Open questions, missing tools

Questions for the orchestrator (not asked of the human):
1. Weights pretrained on Objects365 (images "academic purpose only") or COCO (Flickr terms): acceptable inside a product?
   RF-DETR and D-FINE publish their weights as Apache-2.0; the upstream image terms are the open point.
2. Pasting real CubiCasa dev crops into generated or ResPlan plans makes the synthetic set NC-derived. Record 0003 allows
   NC-derived weights for the prototype if they stay local; confirm that covers derived images too.
3. The generated furnished set (benikm91): the card says CC BY 4.0, the generator repository has no licence file. Is the card
   enough for the submission form, or should someone ask the author? Also confirm the 256 px, door-gap style is acceptable
   as a pre-training stage before anyone spends the hour to convert it.
4. Pointers for the other orchestrator: fpvec-lab (arXiv 2608.25608, walls, mixes CubiCasa5K with synthetic data), FloorplanMAE
   (2506.08363), FZplan (floor plan dataset generation) and 2607.06483 (synthetic pre-training for floor plan generation) are
   L1/L4 material; TinyFormer (2605.25046), FSDC-DETR and FDQ-Det are L2.

Missing tools: no arXiv MCP; Semantic Scholar rate-limited (429) from curl and from the browser fetch, OpenAlex hit its shared
daily limit late in the run; MDPI refuses fetches (Akamai "Access Denied"; I used the DFKI PDF and PMC instead); Hugging Face
gated pages (ArchCAD files, DINOv3) need a login (ArchCAD metadata is readable by API); Roboflow Universe pages only seen as search-result titles, not opened (record 0003); pwfetch of arXiv search pages returned empty late in the run, the export.arxiv.org API over https worked instead. Several fetched PDFs returned binary
text through the fetch agent; I extracted them locally with a PDF text library (no network): Mishra 2021, 2607.18997,
2604.19999 and 2504.05601. Papers behind paywalls were not needed: all were arXiv, PMC or the authors' PDF.

## 8. Sources opened (URL; date read 2026-11-14; what for). Full line-by-line list with times in `lit-data-c-log.md`.

2025-2026 sources: arXiv 2511.09554 (RF-DETR, v2 Feb 2026), 2508.14006 (ResPlan, v2 Aug 2026), 2608.25608, 2607.06483,
2509.17283, 2508.21169, 2610.17178, 2607.18997, 2604.18076, 2608.24154, 2512.22454 (v2 Oct 2026), 2604.19999, 2504.05601, 2604.16513,
2506.07539, 2605.10835, 2606.09479, 2607.27058, 2511.15875, 2508.10104 (DINOv3), 2508.10449 (SkeySpot), 2608.14317, 2511.23241, 2610.17776 (abstract), the Chalmers 2026 thesis, 2410.13842 (D-FINE full text), 2503.22346 (ArchCAD v3), 2401.12729 (2024); repos and
cards: roboflow/rf-detr (README, docs, issues, pyproject), Peterande/D-FINE, Intellindust-AI-Lab/DEIMv2 (LICENSE),
facebookresearch/dinov2, dinov3, mae, m-agour/ResPlan (LICENSE, README, utils), CubiCasa/CubiCasa5k, ArchiAI-LAB/ArchCAD,
benikm91 generator and dataset cards, Voxel51/FloorPlanCAD and three copies, Roboflow/rf-detr-small card, microsoft/dit-base card,
objects365.org download terms, PyPI metadata. Older: 2012.07177 (Copy-Paste), 1811.08883 (rethinking pretraining), 2105.07147
(FloorPlanCAD), Mishra 2021 (SFPI), Hassaan 2023 (emergency plans). That is 50+ sources, 25+ from 2025-2026.
