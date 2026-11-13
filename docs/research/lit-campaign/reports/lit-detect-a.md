# lit-detect-a: detectors for small symbols, field and state of the art 2025-2026 (scope L2, angle a)

Worker lit-detect-a, run of 2026-11-14. Read-only research. Reading log with one line per source:
`lit-detect-a-log.md`. Mark key: **[V]** = I (or the fetch agent I ran) read it on the page;
**[S]** = the page was cut and the rest came back as a model summary, not verbatim; **[R]** = the authors' own claim.
All dates read are 2026-11-14 unless stated. Pages were read through the web-fetch agent, `gh api` and `curl` for
licences, model cards and issue threads, the Semantic Scholar and OpenAlex APIs for citation lists, and the headless
browser (`.agents/pw/pwfetch`) to re-read full pages when the fetch agent had truncated them or arXiv/CVF listings
needed browsing. Rows marked [V] for pages the fetch agent cut at 40k characters were re-read in full where the table
says so.

## 0. Answer to the scope question

Which Apache/MIT detector gives the best small-object AP when fine-tuned on about 3.8k images (104k boxes) on a 12 GB
GPU in under 3 hours? **No paper measured that exact setting.** What the sources do support:

- Permissive DETR-family detectors are the only family with both an open licence and good small-object AP. On
  RF100-VL (100 fine-tune datasets) the YOLO rows have AP_S 4.7-7.3 and the DETR rows 30-39 [V, RF-DETR paper Table 4].
  Ultralytics, YOLOv9/10 and mmyolo are AGPL/GPL (checked, section 2), so that gap is not available to us anyway.
- Among permissive ones the three sensible choices are **RF-DETR S/M/L** (Apache-2.0 code and weights, the best
  documented fine-tune recipe and memory advice), **D-FINE S/M/L** (Apache-2.0, equal or better AP_S on RF100-VL,
  default 640 px and thinner docs) and **DEIM-D-FINE** (D-FINE with a better matching schedule, +0.4 AP_S at L/X,
  LICENSE file says Apache). Co-DETR (MIT) is the accuracy ceiling but needs 2xA100-class memory.
- Input resolution is the real lever, not the model: RF-DETR S/M use patch 16 with resolution a multiple of 32; a
  user reports D-FINE training at 1280 works. For our images (median 855 px, symbols 5-20 px) train near native size
  (about 896-1024), do not downscale to 640, and tile only the few large sheets.
- Expected exact-count rate: **no paper reports it** (second search with new terms, 2026-11-14: only AECV-Bench-style
  model counts, MAPE not MAE, and vendor claims; nothing from a box detector). My arithmetic, not a source: with about 9
  windows per image and each cell found independently with probability p and no false positives, an exact count needs
  all of them, p^9 = 0.39 at p 0.90 and 0.63 at p 0.95 (misses and false positives that cancel add a little); so even
  a detector at AP50 about 90 would sit near 40% exact on windows, well above the 13% most-common-answer baseline and
  the 18% of the count-only network, and every point of per-cell recall is worth about 4 points of exact windows.
  The best reported floor-plan number is door/window AP50 about 90 on
  CubiCasa5K at 1024-1536 px (leaky, section 3), which is a localisation score, not a per-image exact count.

## 1. Top 5, ranked

1. **RF-DETR M (also S and L), fine-tuned on our dev boxes at 896-1024 px: try.** ICLR 2026 (repo title and PDF header as shown in search results, not on the arXiv page I read), Apache-2.0 code and
   weights for Nano-Large (XL/2XL are PML, out). RF100-VL average AP_S 34.2 (S), 35.8 (M), 36.9 (L) with AP 60.9 /
   61.7 / 62.0; YOLO rows AP_S 4.7-7.3. Docs: COCO or YOLO format, resolution divisible by 32, 12 GB recipe
   `batch_size 2 x grad_accum 8` plus gradient checkpointing (-30-40% memory, +20% time); a 1,500-image fine-tune of
   50 epochs takes 10-25 minutes on a 3090/A10/T4. Best measured on drawings: 1344x800 input beat YOLOv12-m at 640
   (mAP50 0.949 vs 0.871) on 551 facade drawings, and 0.881 vs 0.623 against the best YOLO on 1,389 substation images.
   Cheap trick with one measurement: train at the default size and run the same weights at about 1.6x the side at test time; an AI City entry did this with RF-DETR-L (trained 704, run frozen at 1120): AP 0.3272 -> 0.3654, AP_S 0.0519 -> 0.0660, better than fine-tuning at 1120 (0.3470) and than a rectangular 1280x736 run (0.3057); one run per setting, no error bars, T4 [V first 40k of arXiv 2608.03136]. Caveat: maintainers say "DETR models do not outperform for small objects (yet)" and point to SAHI. Sources: arXiv
   2511.09554 [V], rfdetr docs and issues #669/#747/#780 [V], arXiv 2607.18997 [V, PDF text], arXiv 2512.22454 [V].
2. **D-FINE-M, then DEIM-D-FINE-M, same boxes: try (second model, same COCO json).** Apache-2.0 (LICENSE file
   read; DEIM's own LICENSE file also says Apache although `gh` reports NOASSERTION). AP_S on RF100-VL: S 36.6, M
   36.0, versus RF-DETR S 34.2, M 35.8: equal or better at small. COCO AP_S L 36.5 (D-FINE), 36.9 (DEIM-D-FINE-L at 50
   epochs instead of 72). Custom data = COCO json plus `remap_mscoco_category: False`. Evidence for it on a data size like ours: ConRTF (arXiv 2607.00734 [V]) trains D-FINE-X on 2,769 and 4,362 dense line-structure tables and reaches TEDS-Struct 92.65 / 92.01 while YOLOv10-X gets 48.79 / 71.43 and YOLO11-X 64.35 / 75.52; RT-DETRv2-X is level (92.97 / 91.03). Fine-tune risks from the repo's issues [V, #214, #72, #157, #123 read with comments]: Roboflow's own staff (March 2025) report "sub 5% mAP as well as crashes" and convergence to "<2 mAP" on small Roboflow-100 datasets with the repo's fine-tune config, unresolved in the thread; evaluation stuck at 0 when category ids start at 1 (workaround: ids from 0 or num_classes adjusted); a CUDA out-of-memory that repeats at the same epoch on one small dataset; a commenter advises the nano config for "some hundreds" of samples. Our 3.8k images and ConRTF's 2.8-4.4k tables are in the range where it worked. Weaknesses: default 640, larger
   sizes are a user recipe (three places in two config files), no fine-tune memory numbers, and the README warns
   Objects365-pretrained checkpoints may carry Objects365 terms: use the COCO checkpoints. Sources: GitHub README,
   LICENSE, issue #139 [V]; arXiv 2410.13842 [V, full page re-read through the headless browser: Tables 1 and 7, 300 queries, HGNetV2-B0/B2/B4/B5 ImageNet-pretrained backbones, batch 32, S/M 120+4 epochs, L/X 72+2]; arXiv 2412.04234 [V, full page re-read: Tables 1, 11 and 12]; arXiv 2511.09554 Table 4 [V].
3. **Sliced training and inference with a border-aware merge (SAHI, MIT) for the large sheets only: maybe.** Evidence
   from drawings: a P&ID RF-DETR card recommends 1280x1280 slices with 20% overlap [V, model card, its own numbers
   unreadable]; Relationformer on P&IDs (DSAA 2025) uses 1500 px patches with at least 50% overlap and a merge that
   lowers a box's confidence near the patch border, then NMS and weighted box fusion; node AP 83.63 on 12 real P&IDs;
   going from 1500 to 2000 px patches drops Relationformer symbol mAP 73.49 -> 62.23 and node AP 82.18 -> 50.11 on real P&IDs, while its Faster R-CNN modular baseline does not move (86.58 -> 86.52) [V, full page re-read through the headless browser, Table IV]; single Quadro RTX 8000 48 GB, 80 epochs, batch 20, IoU 0.5. Our median image is 855 px,
   so only the large scans need this; for the rest, a modest upscale does the same job at lower cost.
4. **Detection readout instead of a sequence decoder for anything that must be counted: idea, adopt in design.**
   arXiv 2608.25608 [V full page] reports that on real CubiCasa5K scans, reading doors/windows off a dense
   heatmap gets opening F1 0.64 against 0.25 for the autoregressive decoder of the same network, and that detection
   wins on large real scans. Raster2Seq (arXiv 2602.09016 [V], SIGGRAPH 2026) trains at 256x256 and gets window+door F1
   77.8; at that size a 5-20 px symbol is 1-4 px, so it is the wrong tool for exact counts. This ranks the box detector
   above every floor-plan reconstruction model for our job.
5. **Co-DETR (MIT) as the accuracy ceiling to measure, not to ship: maybe/skip.** DoorDet (arXiv 2508.07714, Neural
   Computing and Applications 2025) trained four large detectors on CubiCasa5K re-rendered from SVG; Co-DETR
   (ViT-L backbone, 66.0 COCO test-dev mAP, 300 queries, 2xA100, batch 2, about 20 epochs) reaches mAP 0.831 / mAP50
   0.926 over its 10 door types after human correction (0.578 / 0.650 before) [V, full text re-read through the headless
   browser, Tables 4 and 6]. The boxes are algorithmic and approximate, so the authors report mAP50 as the fair metric;
   a single-class Co-DETR trained on two Roboflow door sets (1,047 and 837 images) got mAP50 0.793 on their combined
   test sets [V, Table 3], which is the only out-of-domain door number in the 2025-26 reading. Code MIT (`gh` verified); no weights or dataset released; trained on
   CubiCasa5K, so leaky. Does not fit 12 GB. Use only as an upper reference.

Not ranked, because the licence rules them out or the evidence is empty: DEIMv2 (non-commercial code and weights,
section 2), YOLO-NAS weights (no commercial use), everything Ultralytics/YOLOv9/v10/mmyolo (AGPL/GPL), RF-DETR
XL/2XL (PML), SymPoint/ArchCAD DPSS (vector input, no code link found), the RT-DETR-L floor-plan repo (no LICENSE
file, Ultralytics-based, CubiCasa5K-trained).

## 2. Licence ledger (code and weights read separately)

| Item | Code licence (how read) | Weights licence (how read) | Usable for us |
| --- | --- | --- | --- |
| RF-DETR N/S/M/L | Apache-2.0 (`gh api license`, LICENSE file head) | Apache-2.0 (docs "Pretrained models": N/S/M/L Apache; HF cards `Roboflow/rf-detr-medium` and `stevenbucaille/rf-detr-small` say apache-2.0, COCO) | yes by its stated licences. **Flag for the team lead:** pretraining used Objects365 images pseudo-labelled by SAM2 [V, paper App. A], and the Objects365 download page says the dataset "is available for the academic purpose only" (annotations CC BY 4.0, images not owned by the consortium, nothing about trained weights) [V, objects365.org/download.html]. Not a CubiCasa leak; an unresolved terms question that also touches D-FINE's Objects365 checkpoints |
| RF-DETR XL/2XL | PML 1.0 via `rfdetr[plus]` (docs) | PML 1.0 | no |
| RF-DETR Atto/Femto/Pico | PML 1.0 via `rfdetr[plus]` (release notes 1.12.0) | PML 1.0 | no |
| D-FINE | Apache-2.0 (LICENSE file head read) | README states no weights licence; HF ports `ustc-community/dfine-{nano,small,medium,large,xlarge}-coco` and `-obj2coco` carry `license: apache-2.0` in the card header [V curl]; README note: Objects365-pretrained checkpoints may follow Objects365 terms | COCO checkpoints yes; Objects365 ones: see RF-DETR flag |
| DEIM | LICENSE file text "licensed under the Apache License" (`gh` says NOASSERTION: the file has a custom first line) | not read | probably yes; ask before shipping |
| **DEIMv2** | custom "DEIMv2 License", non-commercial, no commercial rights [V LICENSE.md] | same licence, "solely for Non-Commercial Purposes"; DINOv3 terms separate | **no** (local experiments only) |
| RT-DETR / RT-DETRv2 | Apache-2.0 (`gh`) | HF `PekingU/rtdetr_v2_r50vd` card: apache-2.0, COCO [V curl] | yes |
| LW-DETR | Apache-2.0 (`gh`) | weights on Hugging Face (xbsu/LW-DETR); Hub tag `license:apache-2.0` (API, 2026-11-14); pretraining on Objects365 (D5 applies) | code yes |
| Co-DETR | MIT (README and `gh`) | Hugging Face model tags `license:apache-2.0` for the COCO, LVIS and Objects365 ViT-L checkpoints (Hub API, 2026-11-14; card text not opened, so the Objects365 data question of D5 applies) | code yes, weights yes subject to D5 |
| DINO (detrex) | Apache-2.0 (`gh`) | not read | code yes |
| YOLOX | Apache-2.0 (`gh`) | not read | code yes |
| mmdetection / mmrotate | Apache-2.0 (`gh`); mmrotate last commit 2024-09-28, release 2023 | RTMDet / RTMDet-R: no statement on the pages read | code yes; mmrotate stale |
| SAHI | MIT (`gh`) | n/a | yes |
| YOLO-NAS | super-gradients Apache-2.0 | **LICENSE.YOLONAS.md: "may not use the Software for any commercial use", no redistribution** [V] | no |
| Ultralytics, YOLOv10 | AGPL-3.0 (`gh`) | AGPL | no |
| YOLOv9, mmyolo, yolort | GPL-3.0 (`gh`) | GPL | no |
| DINOv2 | Apache-2.0 (`gh`) | README: "code and model weights are released under the Apache License 2.0"; data described only as 142 M images, no source terms [V]; other DINOv2-family weights (XRay-DINO, Cell-DINO) are non-commercial, not ours | backbone of RF-DETR: yes |
| HGNetV2 (D-FINE backbone) | PaddleClas Apache-2.0 (`gh`) | ImageNet-pretrained; ImageNet's own access terms could not be read (image-net.org refused the connection) | same open question as Objects365, smaller |
| DINOv3 | NOASSERTION (`gh`) | Meta terms, not read | skip |
| D-FINE-seg | Apache-2.0 (`gh`, pyproject) | README License section: COCO weights Apache-2.0; Cityscapes weights non-commercial [V] | yes for code and COCO weights |
| RT-DETR-L floor-plan repo | no LICENSE file (404 on file, none in listing) [V] | same | no |
| P&ID RF-DETR card | not stated | metadata apache-2.0, body says "see licence accompanying this repository" [V] | not useful: P&ID classes |

## 3. Full table

"Field" says whether the method is from floor plans / drawings or from elsewhere. Leakage = trained on CubiCasa5K or a
repackage. "Hours" = my estimate, marked (est). Input and memory: "n/s" = not stated in what I read.

| # | Method | Field | Year, venue | Code (licence) | Weights (licence) | Training data | Metric, benchmark, input | Memory / hours (est) | JSON field | Leak | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RF-DETR N/S/M/L | general, tested on drawings | ICLR 2026, arXiv 2511.09554 | github.com/roboflow/rf-detr (Apache-2.0) | Apache-2.0 | COCO, Objects365 pseudo-labels | RF100-VL AP/AP_S: S 60.9/34.2, M 61.7/35.8, L 62.0/36.9; COCO AP_S 25.2-39.0 (N-L); patch 16, res multiple of 32 | 12 GB: bs 2 x accum 8 + checkpointing; 1.5k imgs x 50 ep = 10-25 min on 3090/T4; ours (est) 1.5-3 h | elements[] | no | **try** |
| 2 | D-FINE S/M/L (HGNetV2 backbone; the ImageNet backbone weights' licence not read) | general | arXiv 2410.13842 (venue not checked) | github.com/Peterande/D-FINE (Apache-2.0) | COCO ckpts, no statement | COCO (+ Objects365 variants) | COCO AP_S S 29.1, M 33.2, L 36.5, X 37.3; RF100-VL AP_S S 36.6, M 36.0; 640 px default | ablation baseline 8,552 MB at 29 min per epoch on four RTX 4090 (total batch 32, 640 px, COCO) [V]; ConRTF fine-tuned D-FINE-X on one A6000 for up to 500 epochs; ours (est) 2-3 h | elements[] | no | **try** |
| 3 | DEIM-D-FINE | general | arXiv 2412.04234 (venue not checked) | github.com/Intellindust-AI-Lab/DEIM (Apache per LICENSE file) | n/s | COCO | COCO AP/AP_S L 54.7/36.9 (50 ep), X 56.5/38.8; Nano 43.0/24.5 (148 ep), S 49.0/30.4 (120 ep), M 52.7/35.3 (90 ep) [V]; says YOLOv9-E still ~1.4 AP_S ahead of D-FINE-L | like D-FINE, fewer epochs (est) | elements[] | no | maybe (same recipe as 2) |
| 4 | DEIMv2 | general | 2025-26, arXiv 2509.20787 | NC licence | NC licence | COCO | COCO AP Atto 23.8 ... X 57.8 (no AP_S column) | n/a | n/a | no | skip (licence) |
| 5 | Co-DETR | general, used on floor plans (DoorDet) | arXiv (venue not checked); DoorDet 2025 | github.com/Sense-X/Co-DETR (MIT) | n/s; not released for DoorDet | COCO; DoorDet: CubiCasa5K SVG re-render | DoorDet mAP50 0.926 (10 door types, after human correction) [V] | 2xA100, bs 2 (DoorDet) | elements[] | DoorDet: yes | maybe (reference only) |
| 6 | RT-DETRv2 | general | 2024, arXiv 2407.17140 | github.com/lyuwenyu/RT-DETR (Apache-2.0) | n/s | COCO | no AP_S in sources read | n/s | elements[] | no | maybe (RF-DETR table beats it: RT-DETR M AP_S 36.4 on RF100-VL, AP 59.6) |
| 7 | LW-DETR | general | 2024 | github.com/Atten4Vis/LW-DETR (Apache-2.0) | n/s | COCO | RF100-VL AP_S N 31.2, S 32.1, M 34.0 | n/s | elements[] | no | skip (RF-DETR is its successor) |
| 8 | MuraNet | floor plans | arXiv 2309.00348 (2023) | none | none | CubiCasa5K, own 4000/500/500 split | door/window AP50 91.2/92.2, AP50:95 47.9/59.7 at 1536x1536, from scratch, 1000 epochs, 10x3090 | n/a | elements[] | yes | skip (no code); number to beat |
| 9 | RT-DETR-L floor-plan repo (paper arXiv 2606.10953) | floor plans | 2026 | no LICENSE; uses Ultralytics (AGPL) | no licence | CubiCasa5K train 4,200 | door/window AP50 89.8/89.3, AP50:95 57.5/62.2 at 1024, 60 epochs 2xA100 ~2.3 h; README: window confidence 0.3-0.5 on rendered styles, faint dashed door arcs need conf 0.15 | 2xA100 | elements[] | yes | skip |
| 10 | DoorDet | floor plans | NCA 2025, arXiv 2508.07714 | n/s | n/s | CubiCasa5K | see row 5 | see row 5 | elements[] doors | yes | skip |
| 11 | Raster2Seq | floor plans | SIGGRAPH 2026, arXiv 2602.09016 | project page only; none in text | n/s | CubiCasa5K (train), Structured3D | window+door F1 77.8 (RoomFormer 78.5), 256x256, 1 A6000, CubiCasa5K 19.4 h + 16 h | A6000 | rooms, windows | yes | skip for counting (L1/L4 own it) |
| 12 | Detection vs emission readout | floor plans | arXiv 2608.25608 (2026) | github.com/Cyprinus12138/fpvec-lab (MIT, gh api license; paper CC BY 4.0) | n/s | CubiCasa5K, ResPlan-FP, Structured3D | opening F1 0.25 -> 0.64 (2.6x) from an opening heatmap the decoder never used; graph readout +2.7 wall F1 at tol 0.05 and +5.1 at 0.015 on real scans, reverses on small plans [V full page] | n/s | design idea | yes (data) | idea only |
| 13 | AEC facade layout benchmark | engineering drawings | EC3 2026, arXiv 2607.18997 | n/s | n/s | 551 facade drawings (own) | RF-DETR-m 1344x800 mAP50:95 0.890 / mAP50 0.949; Faster R-CNN 0.779/0.930; YOLOv12-m 640 0.755/0.871; DocLayout-YOLO pretrained on DocLayNet 0.589/0.675 | T4; RF-DETR 44.8 ms | not our task | no | evidence for RF-DETR at high res, and against document-layout pretraining |
| 14 | Substation comparison | aerial imagery | arXiv 2512.22454 | Zenodo only | n/s | 1,389 images, 640 px | RF-DETR-L mAP50 0.881 / 0.632; Base 0.826; best YOLO (v8s) 0.623; no AP_S | n/s | n/a | no | evidence only |
| 15 | Relationformer + patch merge | P&ID | DSAA 2025, arXiv 2411.13929 | none found | none | 2,000 synthetic + 60 real P&IDs | node AP 83.63, edge mAP 75.46 on 12 real P&IDs; 1500 px patches, overlap >= 50% [V full] | Quadro RTX 8000 48 GB [V] | patch-merge idea | no | idea only |
| 16 | RF-DETR P&ID card | P&ID | DocEng 2026 | github.com/dimitri009/STA (not opened) | apache-2.0 metadata | 32 symbol classes, 10 epochs | mAP50 99.96, mAP50:95 97.89 (benchmark unclear) [V card]; SAHI 1280, 20% | n/s | n/a | no | idea only |
| 17 | SAHI | general | ICIP 2022, arXiv 2202.06934 | github.com/obss/sahi (MIT) | n/a | n/a | earlier report: AP50-small +4.7 on VisDrone inference-only | linear in tiles | elements[] at large sizes | no | maybe |
| 19 | SkeySpot | electrical layout plans | IEEE SMC 2025, arXiv 2508.10449 | github.com/HAIx-Lab/Skeyspot (licence unread) | not mentioned | 45 UK plans, 34 classes, 2,450 instances (own) | YOLOv8 mAP50 81.12 / 48.24 (50:95), Faster R-CNN 48.62; 13 test images per fold; rare classes 21-56 mAP50; no resolution, no tiling, no counts [V full paper] | n/s | n/a | no | evidence: tiny sets give rare-class AP below 60 |
| 20 | MEP lighting symbols | floor plans (PDF rendered 300 dpi) | arXiv 2608.14317 (2026) | none | none | private | Mask R-CNN bbox mAP 0.7596, mAP50 0.985, 1000x1000 slices with 0.2 overlap [V abstract and method] | n/s | n/a | no | idea only (same slice settings as the P&ID card) |
| 21 | RF-DETR-S door detector card (kiyo07) | floor plans | HF card, 2026-10-28 | runner AGPL-3.0 (PyMuPDF); weights Apache-2.0 [V LICENSING.md] | Apache-2.0 | two Roboflow Universe sets (CC BY 4.0), door only | no benchmark stated; inference 768 px tiles stride 384 resized to 512, conf 0.3, NMS 0.5 [V card] | n/s | doors | unknown (Roboflow sets may repackage CubiCasa5K; record 0003 excludes Roboflow data) | skip as checkpoint; recipe shows RF-DETR-S works for doors |
| 22 | YOLO11s CubiCasa5K card (v1nz) | floor plans | HF card, 2026-09-11 | Ultralytics (AGPL) | cc-by-nc-4.0 | CubiCasa5K, 640 px | wall/door/window bbox, test mAP50 0.4112, mAP50:95 0.2881 [V card] | n/s | n/a | yes | skip; but shows 640 px costs a lot against 1024 px (89.8/89.3 door/window AP50, different detector, wall class mixed in) |
| 23 | Symbol spotting on architectural plans (YOLOv2 on tiles) | floor plans (older, 2020, kept because it is the only per-class fixture table found) | CVPR Workshops 2020, arXiv 2006.00684 | n/s | n/s | 115 proprietary units from 10 firms, 90 for 4,707 tiles of 227x227 (stride 50), 25 whole plans for test | per-class AP50 on 25 whole plans, ResNet50 backbone: bathtub 91.67, toilet 100.00, kitchen sink 91.07, bathroom sink 84.97, entry door 86.35, window 75.64, shower 100.00; AP75 window 31.78, toilet 50.87; mAP 59.03 [V, full page via ar5iv through the headless browser, Table 2]. Plans 5400x3600 px, sink symbol 70x80 px | n/s | fixtures + doors + windows | no | evidence: fixtures reach AP50 85-100 on a tiny set; AP75 on windows stays about 32 |
| 24 | D-FINE-seg (training/export framework around D-FINE) | general | arXiv 2602.23043 (2026, abstract via search snippet); repo pushed 2026-11-13 | github.com/ArgoHA/D-FINE-seg (Apache-2.0, `gh` and pyproject) | README "License" section [V]: COCO weights (detection, instance segmentation, keypoints) Apache-2.0; only the Cityscapes semantic-segmentation weights are non-commercial, because the authors treat them as derivative works of Cityscapes (the same logic would apply to Objects365 pretraining: unresolved flag in section 2) | COCO | adds YOLO or COCO-format labels, `img_size: [h, w]` config (default 640x640), mosaic + affine + Albumentations rotation/flip, auto batch size, ONNX/TensorRT/OpenVINO export [V README] | n/s | elements[] | no | try as the training harness for row 2 (read its rotation options before use) |
| 25 | ConRTF (D-FINE-X + edge-weighted loss) vs YOLO and RT-DETRv2 on small private sets | document tables (thin-line structure) | ICDAR 2026, arXiv 2607.00734 | n/s | n/s | 4,362 and 2,769 private tables (2.8-4.4k, like our 3.8k) | TEDS-Struct Business / Finance: D-FINE-X 92.01 / 92.65, RT-DETRv2-X 91.03 / 92.97, YOLOv10-X 71.43 / 48.79, YOLO11-X 75.52 / 64.35 [V, full page via headless browser, Table 4]; input 640, 300 queries, up to 500 epochs with early stopping patience 10, one A6000 | A6000 | n/a (layout) | no | evidence: on a few thousand images of dense line structure the DETR family holds up while YOLO drops 20-48 points |
| 26 | ReDHF; TinyFormer | general, tiny objects in DETRs | NeurIPS 2026 poster = arXiv 2611.07994 [V full page, CC BY 4.0; plug-in for Deformable-DETR-like baselines (DINO-4scale, Dome-DETR), no code link seen, AI-TOD-v2 AP 35.7, VisDrone 40.6, SODA-D 38.7]; arXiv 2605.25046 (2026) | TinyFormer: github.com/mmpmmpmmpjosh/TinyFormer (no licence file: gh api says NOASSERTION; paper CC BY-NC-ND; built on DEIMv2, NC) | n/s | COCO, VisDrone, AI-TOD-v2 | ReDHF +1.4 AP on AI-TOD-v2, +1.6 VisDrone, +1.5 SODA-D over its baselines [V]; TinyFormer COCO AP_S X 39.3 -> X-PBM 40.9 at 640 px, VisDrone AP_S 24.7 vs DEIMv2-X 21.5 [V full page] | n/s | n/a | no | skip: gains of 1.4-1.6 AP are smaller than the resolution effect, and TinyFormer inherits a non-commercial base |
| 27 | HouseCADDesignObjectDetection (YOLO11s, community model card) | AutoCAD-style house layouts | Hugging Face model card, read raw 2026-11-14 | card says Apache-2.0 but base is Ultralytics YOLO11s (AGPL): conflict, do not use as is | card-only | custom set, 92 val images, 2,568 instances, source unnamed | per-class mAP50: toilet 0.96, bathroom sink 0.929, kitchen sink 0.917, shower 0.947, bathtub 0.933, window 0.905; all 0.918, mAP50-95 0.671 [V card] | n/s | n/a | unknown (dataset unnamed) | skip: unnamed data, AGPL base, no counts |
| 28 | 2DPlan2Strct (RF-DETR Medium fine-tune, community) | floor plans: wall, room, door, window boxes | Hugging Face model card + USAGE_TERMS.md, read raw 2026-11-14 | weights: non-commercial research and evaluation only (USAGE_TERMS.md); code: inference.py, no licence file seen | no | training data not named on the card (unknown); 2,964 val images | val mAP50 94.52, mAP50-95 82.58, F1 91.86, P 93.53, R 90.26 at 576 px, best EMA at epoch 13, 16 h on one T4 [V card, run self-reported, not a test set]; CPU: 457.63 ms median, p95 654.66 ms, 2 threads Xeon 8488C, 1206x1013 plan [V card] | T4 16 GB, 16 h | yes: CPU latency for RF-DETR-M | unknown (dataset unnamed) | skip as weights (NC, no classes we need); keep the CPU number |
| 29 | Benchmarking DL for AEC drawing layout detection (EC-3 2026) | engineering drawing layout regions | EC-3 2026 paper 305, DOI 10.35490/EC3.2026.305 | n/s | n/s | custom dataset, five architectures | RF-DETR best, mAP50 0.949; Qwen3-VL F1 0.911; general document-layout models degrade [abstract only, PDF not read] | n/s | n/a | n/s | idea only: confirms RF-DETR over general document models on drawings, but layout regions, not 5-20 px symbols |
| 18 | ArchCAD-400K / DPSS | CAD vector | NeurIPS 2025, arXiv 2503.22346 | none found | none found | 5,538 drawings, chunks 14 m | total PQ 70.6 vs SymPointV2 60.5 [V full page] (door 75.9, window 57.2 appear in a per-class table, column and method not re-checked [S]) | 8 A800 [V] | n/a, vector input | no | skip (L11 vector) |

## 3b. Practical fit notes read from source (angle c will extend)

- **RF-DETR defaults, read from `src/rfdetr/config.py` on the default branch (2026-11-14) [V]:** Nano 384 px, Small 512,
  Medium 576, Large 704; patch size 16 and 2 windows for all four (so resolution must be a multiple of 32);
  300 queries; decoder layers 2/3/4/4. Going from M's 576 px to 1024 px raises the token count from 1,296 to 4,096
  (x3.2), so expect a multiple of M's memory; the docs' remedy order is smaller batch, gradient checkpointing, then
  accumulation. The positional grid is re-derived when `resolution` is passed to the constructor.
- **Augmentation, RF-DETR [V docs and source]:** default is scale jitter plus horizontal flip (50%). `aug_config` takes
  Albumentations names (`VerticalFlip` and `Rotate` are shown in the docs). Reading `src/rfdetr/datasets/transforms.py`
  on the default branch: the set `GEOMETRIC_TRANSFORMS`, which decides whether boxes are transformed with the image,
  contains `VerticalFlip`, `Transpose` and `RandomRotate90` (Albumentations' name for exact 90-degree turns), D4 aliases
  are handled, and `tests/datasets/test_augmentations.py` mentions `RandomRotate90`. So exact-multiple rotations are
  supported with box handling; our one-in-three rotated sheets can be matched by `RandomRotate90` plus `VerticalFlip`
  (still check one batch visually). Albumentations is MIT but archived (last push 2025-06-25); `rfdetr` pins it as
  optional `>=1.4.24,<3.0.0`, so the AGPL "AlbumentationsX" fork is not pulled in by that pin (`gh`, pyproject read).
- **Augmentation, D-FINE [V yaml]:** photometric distort, zoom-out, IoU crop (p=0.8) until epoch 72, horizontal flip,
  resize to 640. No vertical flip or rot90; IoU crop and zoom-out are risky for 5-20 px symbols and for plans whose
  count is the label. A rot90 op is custom code.
- **Maintainer statements on small objects, RF-DETR repo [V, issues #112 (2025-04-04/05) and #743 (2026-02-25) read in full with comments]:** mosaic and other augmentations
  "also will work" but are not in the repo; "you can upscale your image either during or post training and expect better
  results on small objects, but that comes with a latency hit"; "there's some reason to believe that DETR detectors in
  general are particularly weak on small objects"; the cap is the query count, 300 in training and inference; the
  RF100-VL paper evaluates with maxDets 500 because pycocotools' default of 100 caps recall. For us: count from
  detections above a threshold, not from AP, and never score with the default maxDets.
- **More from the RF-DETR threads [V, #958 (2026-04-13), #802, #301 read]:** on a small-ball dataset Nano's accuracy fell by more than half
  at low resolution, and the maintainer's advice is to move to Small or Medium "as those scale resolution but also change
  other parts of the architecture" instead of upscaling Nano; one user's inference time grows with the input file's
  size even at fixed model resolution (decode and resize cost); two threads report training that worked on one `rfdetr`
  version and failed on the next (OOM on 1.5.2, parameters ignored after 1.1.0 to 1.2.1). Pin the package version (a
  2026 door-detector card pins 1.11.2) and use S or M.
- **D-FINE-seg harness [V, `dfine_seg/config/default.yaml` read through `gh api`]:** `img_size: [640, 640]` (h, w) is a plain
  setting, `batch_size: -1` probes the GPU for the largest fit, 55 epochs by default, AMP bfloat16, mosaic probability
  0.8 for detection with `no_mosaic_epochs: 5`, and the augmentation block has `rotate_90` ("90° rotation; for top-down
  data (aerial, documents)", default 0.0), `up_down_flip` and `left_right_flip`. That is the only D-FINE-family trainer
  I found where exact 90-degree turns are a config line and not custom code.
- **Hugging Face transformers route [V, two docs pages read]:** the `DFineForObjectDetection` page gives a 300-query default,
  a loss when `labels` (dicts of `class_labels` and `boxes`) are passed, and no training example; the RT-DETRv2 page links a
  community fine-tuning notebook on a custom dataset and states "Reshaping to other sizes will generally degrade
  performance" (its 640x640 recommendation), so any detector other than RF-DETR (which interpolates positions) should be
  trained at the size it will run at, not trained at 640 and run larger.
- **Both:** 300 queries is plenty for the 27 symbols per image average here.

Round 2026-11-14, two open-issue findings that bite line drawings in particular [V issue pages, reporter claims]:
- RF-DETR issue 1516: since 1.9.0 `predict()` resizes with `antialias=False`, while the default torchvision training
  backend and checkpoints from rfdetr up to 1.4 train on antialiased inputs. Reporter's test (1,207 photos, 15 Medium
  checkpoints): 1.8.3 matches 1.4.2 exactly, 1.10.1 differs; a forced `antialias=True` reproduces 1.4.2. The effect grows
  with the downscale factor (phone photos 5-10x), so for a sheet scaled down hard it is the first thing to rule out. Status: closed; rfdetr 1.12.0 (released 2026-11-06, latest 1.12.1 on 2026-11-12, repo Apache-2.0) adds opt-in `predict(antialias=...)` (PR 1525, merged 2026-10-05); the default stays `antialias=False` [V release notes]; 1.9.1 also moved ONNX/TFLite export examples to the non-antialiased convention. For
  thin-line symbols antialiasing decides whether a 1 px stroke survives; our rule: resize the page ourselves with one
  fixed filter (area/antialiased) for training and inference, and pin the library version.
- D-FINE-seg repo issues (Apache-2.0 repo, pushed 2026-11-13, 225 stars) [V issue pages]: no SAHI-style slicing for
  training or inference yet (issue 84, open: the maintainer agrees it is wanted, no date), so tiling for a D-FINE route
  would be our own code; loss explosion at epoch 226 in one report (issue 64), maintainer fix list: turn AMP off, lower
  the LR, betas 0.9/0.98, check duplicate class names; fixed-size ONNX even with the dynamic flag was reported and
  fixed (issue 82); small-object advice (issue 58) is only "try 640, 800, 960 and plot", no tuned recipe.
- Tiling and merging, 2025-26 (read: ISPRS page abstract and the insect paper; search-result summary only for the others [S]): the
  Local NMS paper (ISPRS Annals XI-3-2026, 81-90, CC BY 4.0) speeds up tile-wise post-processing by running NMS in a
  parallel process; it is about throughput, not count accuracy, so it does not help exact counts. An insect-dataset paper
  (arXiv 2507.06972) uses tile overlap and SAHI non-maximum merging to stop double counts [V text; overlap percentage not read cleanly]; a 2025 mask-merging paper argues IoU-only merging misses fragments with little overlap [S]. For us: with
  5-20 px symbols and a symbol cut by a tile edge, overlap larger than the largest symbol plus a centre-point rule
  (keep a box only in the tile that holds its centre) is simpler than any IoU merge; no paper found tests this on
  drawings.
- RF-DETR release notes 1.11-1.12 (read 2026-11-14) [V]: the Kornia augmentation backend raises an error for rotation,
  scale, shear and padded batches, so our RandomRotate90 + VerticalFlip recipe needs `augmentation_backend` set to
  `albumentations` or `torchvision`/`cpu` explicitly, not left to resolve; an `Affine` config without `rotate` no longer
  rotates (it used to sample plus or minus 15 degrees); the new smaller Atto, Femto and Pico models ship in the
  `rfdetr_plus` package under PML 1.0, so they join XL/2XL on the do-not-use list; Apache-2.0 covers the base package.
- D-FINE issue 358 (open): the PyTorch script stretches to 640x640, the ONNX script letterboxes; the reporter saw class
  flicker on small distant objects until both used the same stretch. Same rule: one preprocessing function used by
  training, eval and export.
- RF-DETR issue 879: a maintainer answer, "no fixed bound" for the smallest detectable object; advice is to crop into
  patches and to compare object scale with RF100-VL datasets.

## 4. Citation walks forward

Method: Semantic Scholar `citations` endpoint and OpenAlex `cites:` filter (2026-11-14), filtered by title words, then
opened what mattered. Both APIs rate-limited me (HTTP 429) after a few calls; OpenAlex gave 140 citing works for RF-DETR
and returned the abstract of the scan-shift journal paper, but its D-FINE and DEIM lists came back rate-limited, so those
two walks rest on the Semantic Scholar list (first 100 citing works) and arXiv search pages. The headless browser opened
arXiv, CVF and Zenodo; DuckDuckGo and Bing result pages were blocked.

- **RF-DETR (arXiv 2511.09554), 2025-26 citing papers about drawings or similar small-symbol work:** AEC drawing
  layout benchmark (2607.18997, read), substation components (2512.22454, read), PCB OCR comparison (not opened),
  hand-drawn circuit component augmentation benchmark (CompSysTech 2026, not opened), YOLO26 overview (2602.14582,
  not opened). None reports per-symbol AP on thin-line symbols, and none touches floor plans.
- **D-FINE (arXiv 2410.13842):** the same substation paper; document-layout detectors (PARL 2601.07620, SSDOC-DET);
  no floor-plan or drawing symbol paper.
- **CubiCasa5K (arXiv 1904.01920), 176 citing, about 70 from 2025-26:** read DoorDet, Raster2Seq, Architect-Ant /
  RT-DETR repo, the evidence-gated parsing paper (2609.25615, no trained detector, no per-class AP), the
  detection-vs-emission paper, a hatch-and-wall paper (2609.24565, no door/window evaluation, but scans cost a trained
  CNN -0.08 to -0.19 area accuracy and thick strokes -0.17 [V]) and a door-detection plus GPT-5 paper (2509.17283:
  Co-DETR trained on two Roboflow door sets, per-image accuracy only, toilets 87.63% on CubiCasa5K, 85.57% for GPT-5 alone; SESYD 95.83, CVC-FP 86.67, MLSTRUCT-FP 66.67 [V full page; image count not re-checked]
  Seen but not opened: "Why floor plan object detection breaks under real scans" (Automation in Construction
  2026, cites both CubiCasa5K and MuraNet; the one paper in the list that matches our problem; Elsevier), FloorPlanFormer
  (AAAI 2026), an unknown-symbol dataset (ELINA, 2025), Text-Aided Panoptic Symbol Spotting (2607.12678, vector, L11).
- **MuraNet (arXiv 2309.00348), 8 citing:** the scans paper above, a Zernike-moment rotation-invariance pipeline
  (arXiv 2504.03241, abstract only, L9) and FGSSNet. Nothing reports door/window AP beating MuraNet's with open code.
- Venue sweep (2026-11-14, CVF open-access listings through the headless browser): CVPR 2026, CVPR 2025, ICCV 2025,
  WACV 2026, WACV 2025 contain no raster symbol-detection paper for floor plans; the floor-plan titles are localisation,
  generation and WAFFLE (WACV 2025, data scope). ICDAR/GREC and Elsevier/Springer pages could not be read.
- Dataset releases linked from the citing papers: the scan-shift study (Automation in Construction 2026, abstract only
  through OpenAlex; Elsevier) released CubiCasa5k-ScanShift on Zenodo (4.7 GB, CC BY-NC 4.0 plus CubiCasa5K terms, 4,996
  paired layouts, RT-DETR checkpoints) [V Zenodo record]: its finding is that strict-IoU AP (AP75, AP at 0.85) drops far
  more than AP50 on scans and that depiction inside object boxes, not background, is the cause. For counting, AP50-level
  localisation is what matters. Not usable for scored runs (leak). Companion repo github.com/andreacar/floorplan-detection-scan-robustness [V README and LICENSE file]: code MIT, trained RT-DETR checkpoints and result bundles non-commercial (LICENSE.assets), HF `RTDetrForObjectDetection` wrapper, six classes (wall, column, stair, railing, door, window), no sanitary fixtures; useful as a recipe for paired clean/scan evaluation, not as weights. Its table_size_success.csv (logistic fit of detection success against object area, RT-DETR trained at IMAGE_SIZE 1024; area unit assumed px^2 at that size, not confirmed) puts the 50% success area at IoU 0.5 at 120 on clean renders and 909 on scans (about 11 px and 30 px per side), and at IoU 0.85 at 202 and 6,803 [V CSV, units unverified]: on scans a 5-20 px symbol sits below the 50% point, which supports upscaling or tiling before detection.
- arXiv listing sweep (search pages through the headless browser, newest first): new items are SkeySpot (2508.10449,
  read) and a lighting-symbol Mask R-CNN paper (2608.14317, read).
- Net result: **no 2025-26 paper reports per-image exact counts, or AP for toilet, sink, shower or sauna stove, from a
  box detector on floor-plan rasters.** The 2025-26 floor-plan literature moved to vectorisation (Raster2Seq,
  ArchP10k pipelines, VLM-based) and to LLM-assisted door tools.

Round 2026-11-14 (Semantic Scholar forward citations of DEIM, 446 papers, titles filtered; OpenAlex out of free budget):
- 2610.33430 BUTR (dynamic query as budgeting; Dome-DETR base; AP 35.7 at 47.8 FPS AI-TOD-v2, 29.8 AP / 42.1 FPS
  VisDrone on a T4) [V abstract and intro, CC BY 4.0]: aerial tiny-object DETR; same verdict as ReDHF, idea only.
- 2610.17776 TempFit, panoptic symbol spotting by template fitting [V abstract + results line; CC BY 4.0]: vector CAD
  primitives, PQ 80.1 on FloorplanCAD under the Hungarian protocol (SymPointV2 3.1 lower), and it beats a DEIM + ICP
  detect-then-fit baseline on its own IndustryCAD set. Needs vector primitives, so it belongs to L11 (pointer only).
- 2609.06581 CQTR, training-free counterfactual scaling plus query-trajectory reliability for small objects [V
  abstract and setup, CC BY 4.0]: tested on nine frozen detectors including D-FINE-S and DEIM-D-FINE-S over COCO,
  TinyPerson and VisDrone (27 combinations), AP and AP_S rise in every setting, 100 unlabelled images calibrate it once.
  A second route to frozen-weight small-object gain besides the frozen high-res run; COCO-style metrics only, no
  drawings, no code link seen. Idea only; test after the baseline fine-tune, never before.

## 5. Transfer notes (other fields; angle b covers more)

- **P&ID symbol detection to window/door cells.** Task: find 30+ small symbols on a huge line drawing. Our window
  cell plays the role of a valve. Why it should transfer: same thin-line symbols touching long lines; the evidence
  is slicing with large overlap and a border-aware merge. What breaks: P&ID sheets are 4500x7000 px and ours are
  855 px, so the tiling is overkill and the merge adds latency; P&ID symbols are upright and ours are rotated by
  exact multiples of 90 degrees, so rot90 and flip augmentation is still needed (not covered by any source read).
  Code: Relationformer none found; RF-DETR card gives only the SAHI settings. Gives the idea only.
- **Document-layout detectors (DocLayout-YOLO) to drawings.** The AEC benchmark shows a layout detector pretrained on
  DocLayNet/DocSynth scoring 0.675 mAP50 against 0.949 for RF-DETR fine-tuned from COCO, and the authors call this
  "domain interference". What it says for us: do not start from a document-layout checkpoint; start from COCO.
- **Aerial / dense small-object DETRs (DQ-DETR, DDQ-DETR) to doors and windows.** The DETR query cap matters for
  dense images: a limit of 100-300 queries saturates when objects approach it. Our average is about 27 symbols per
  image (104k boxes on 3,828 images, from the context file), the maximum is higher on multi-plan sheets, so 300 queries
  is enough; DEIM Table 12 [V, full page] varies objects per training image after 24 epochs: about 10 -> AP 51.7, about 25 -> 52.5, about 50 -> 52.2 (COCO), so mosaic-style densification helps by under 1 AP and our natural 27 per image already sits at the sweet spot. DQ-DETR (arXiv 2404.03507 [V first 40k]) sets queries from a counted level
  (300/500/900/1500) and gains +4.3 AP on AI-TOD-V2 over its DINO baseline (30.2 vs 25.9); code URL in the paper
  (hoiliu-0801/DQ-DETR), licence not read. What breaks: its gain is for aerial objects of 2-16 px in thousands; our
  per-image counts are low, so the gain would be small, and a count head is the L3 scope.
- **Circuit-schematic symbol detection (SINA, arXiv 2607.01609, 2026) to our symbol cells.** Task: components of
  hand-drawn, scanned and CAD schematics to a netlist. A resistor plays the role of a door. Evidence read [V, full page via
  headless browser]: a fine-tuned YOLOv11m on over 700 annotated schematics reaches mAP 97% at 27.63 minutes of
  training (IC-level set); augmentation is scaling, brightness jitter and flipping; the pipeline then runs an independent
  GPT-4o pass that lists components and "a confidence score is reported based on the concordance between both systems
  regarding component types and counts", and any component found by one system and not the other is flagged for a
  person. Why it transfers: this is our stage-8 second count and our person-checks-the-machine pattern, with measured
  use on symbols on line art. What breaks: the detector is Ultralytics YOLO (AGPL, out for us), the schematics are
  larger symbols on clean backgrounds, and the VLM check costs an API call per image and is not run on 855 px plans at
  10 px symbols (VLM counts of doors/windows are 0.34-0.39 exact per the earlier report). Idea only; the L10/L7 scopes
  own the verification design.
- **Historical-map point signs (CaSiDD, arXiv 2610.13224, 2026) to our symbol cells.** Task: find small discrete icons (trees,
  mills) on 768-1000 px map patches; 796 patches, 18,750 labelled signs, class-agnostic labels. A map sign plays the role
  of a window cell: small, repeated, drawn on texture, sometimes overlapping. Evidence [V, full page via headless
  browser]: YOLOv10-X from COCO fine-tuned to convergence got precision 81.1% / recall 41.5% at IoU >= 0.3 and 75.7% /
  38.9% at IoU >= 0.5; multi-class (24 classes) AP50 44.6%, recall 21.8%; the authors blame loose boxes and ill-defined sign
  boundaries, and they turned mosaic off "given the already small size of target objects". What it says for us: (a) our
  boxes come from the SVG annotation, so boundaries are consistent, which is the condition this paper lacked, and (b)
  turn mosaic off or keep it low for 5-20 px symbols (D-FINE-seg's default is 0.8). What breaks: detector is YOLOv10
  (AGPL); no code check. Idea only.
- **Weights-free route (training-free rule pipelines).** arXiv 2608.17237 [V full page]: recall/precision columns
  0.922/0.997, beams 0.886/0.990, walls and braces 1.000, openings 1.000/0.964, on procedural structural plans with no detector. What breaks:
  they are generated vector-clean plans (author benchmark, 50 held-out); ours are rasters with scans. Even there, wings rotated 15-30 degrees drop column recall to 0.659 (mixed) and 0.790 (skew-wing) against 1.000 for axis-aligned families. Gives the idea of a deterministic second count
  only (L11).

### 5.x Microscopy cell counting: decoupled counter + localizer (arXiv 2503.13989, Mar 2025) [V full page]

Counter on intermediate features plus a global message-passing module, then a localizer that reconstructs a
high-resolution density map; MAE/MSE on DCC, ADI, MBM, VGG (DCC MAE and MSE down 63.6% and 55.2% as the paper
reports). The paper's argument: CNN receptive fields are too small to separate touching or overlapping cells without
global context. Plays the role of: a cell = one symbol among touching symbols (two fixtures side by side).
Licence of code and weights not read (no repo link found on the page). What breaks on our images: it scores mean
absolute error per image, not exact-count rate, and a density map gives no box per symbol, so we could not tell a
count of 4 from 3+1 wrong symbols; no class-specific counting (toilet vs sink vs shower); cells are blobs while our
symbols are 5-20 px line drawings. Verdict: idea only (a global count head next to the detector as a sanity check on
the per-page total), not a candidate.

### 5.y Active learning for D-FINE-X on documents (arXiv 2607.00747, 2026) [V full page, CC BY 4.0]

Table detection and table structure recognition both use D-FINE-X from a COCO checkpoint; labelled budgets of 71 to
500 documents (start 71, six sampling rounds), 10 seeds, GriTS-Con F1; a hybrid coverage + uncertainty picker
separates from single-signal pickers from about 200 documents, and run-to-run variance is high at low budgets.
What it gives us: evidence that D-FINE fine-tunes from COCO on a few hundred documents without special tricks, and a
rule for choosing which of our pages to label next (mix coverage and uncertainty). What breaks: classes are tables,
rows and columns, large objects on text pages, not 5-20 px symbols; metric is table F1, not exact counts; code
link not seen. Idea only.

### 5.z Vendor practice note: Roboflow blog on counting symbols on plans (2026-05-04) [V full page, vendor marketing]

One production example (29 custom models, classification + detection + segmentation, real plan sets). Advice given:
one detector per sheet type rather than one big model; tile inference with overlap and merge at page level; label with
domain experts; active learning for the next labels. No metric, no count accuracy, no architecture named. It agrees
with our tiling and expert-label advice but is not evidence for any number. Our images are single-type floor plans,
so the per-sheet-type split is already how we work.

## 6. Looked for and did not find

- A per-image exact-count, or count-error, result for any box detector on small symbols: none in 2025-26 papers read.
- Per-class AP for toilet, sink, bathtub, shower or sauna stove from a floor-plan raster detector in 2025-26: none.
  The only peer-reviewed per-class fixture table I found is older (Rezvanifar et al., CVPR Workshops 2020: toilet 100,
  kitchen sink 91.07, bathroom sink 84.97, bathtub 91.67, shower 100 AP50 on 25 plans, YOLOv2 on 227 px tiles); the
  rest are community model cards (toilet mAP50 0.96, sink 0.929, bathtub 0.933 on an AutoCAD-layout YOLO card whose
  test split is not stated, AGPL stack). No sauna stove anywhere.
- A paper comparing rot90 augmentation with an oriented head on drawings: none (second attempt with new terms found two
  related routes, both unread beyond an abstract or snippet: oriented boxes with an Ultralytics model on multi-view
  engineering drawings, arXiv 2510.21862, abstract only, AGPL stack; and orientation as keypoint pose estimation, Faltin
  et al., Keypoint R-CNN mAP up to 0.752 per a search snippet, the PDF returned HTTP 403). Rot90 test-time augmentation
  on drawings: no measured gain found; the library note is that the four rotations can be applied and inverted. Kalra et al. (ICCV 2021, arXiv
  2109.13488) is about box inflation at non-90 angles, where 90 degrees is exact; the RTMDet-R DOTA table (mAP50
  78.85-81.33) is aerial. The only oriented-detector library in the allowed licences (mmrotate) is stale (last commit
  2024-09-28, Python 3.7 setup), so my reading is: exact-multiple rotations are an augmentation problem, not a head.
- Fine-tune memory or hours for D-FINE/DEIM/RT-DETRv2 on a 12 GB card at above 640 px: not stated anywhere (only a
  4x4090 ablation at 640 px, 8,552 MB per card, and ConRTF's single A6000).
- CPU latency for any candidate: not stated in the papers; the RF-DETR docs' latency cookbook URL returned 404 and the
  OpenCV 5 DNN benchmark mirror returned a 503. One measurement exists: the 2DPlan2Strct card (row 28) reports RF-DETR
  Medium at 576 px on two Xeon threads, float32 PyTorch: 457.63 ms median, 654.66 ms p95 on one 1206x1013 plan. Single
  plan, 20 timed runs, self-reported; D-FINE and DEIM CPU numbers still missing.
- RTMDet weights licence: the mmdetection README says only "Apache 2.0" for the project, no separate weights statement; ImageNet-pretrained CSPNeXt backbones, so the ImageNet terms question of D5 applies. (LW-DETR weights: Hub tag Apache-2.0, see ledger.) (Co-DETR weights: closed, see the licence ledger.)
- "Why floor plan object detection breaks under real scans" full text: Elsevier paywall; I read the abstract (through
  OpenAlex) and the Zenodo record, not the paper, so its per-class AP drops are unknown to me.
- The DETR-for-P&ID paper and the 2026 LLM floor-plan preprint with 18 YOLO classes: PDF bytes unreadable / HTTP 403.

- D-FINE or DEIM fine-tuned on technical drawings or floor plans (second attempt, 2026-11-14): one web search with
  different terms found no such paper. Forward citations by Semantic Scholar (D-FINE 335 papers, DEIM 446), titles
  filtered for drawing, plan, symbol, table, document, CAD: the only on-topic hits were ConRTF and the substation
  paper already in the table, plus 2607.00747 (active learning for cascaded table detection, read, section 5.y) and
  a document-layout paper (SSDOC-DET, title only). Title filtering misses papers whose titles do not say it.


## 7. Open questions, missing tools

- Does RF-DETR-M at 1024 px reach exact window/door counts better than the 18% of the count-only network? Only a run
  on the dev boxes answers it; hours to a first number (est): data conversion to COCO json 0.5 h, train 1.5-3 h.
- Does RF-DETR's (or D-FINE's Objects365) pretraining carry terms that bind a shipped model? The Objects365 page says
  "academic purpose only" and is silent on weights; the D-FINE-seg authors treat Cityscapes weights as derivative of the
  dataset terms. A legal reading is needed from the team lead, not more research.
- For L1/L4 (other orchestrator): Raster2Seq's test-set size is 511 in one place and 400 in another; the
  evidence-gated parsing paper (2609.25615) says door/window labels override spaces in the shared evaluation.
- For L9: arXiv 2504.03241 (Zernike-moment rotation invariance, 2025) and the AEC finding that scale of drawing
  decides the input size.
- Missing tools: no arXiv MCP; Semantic Scholar rate-limited after four calls; web-fetch returns only text of a
  PDF if it can extract it (two PDFs came back as bytes, one read through a local `pypdf` run); Elsevier, MDPI and
  preprints.org refuse automated reads.
