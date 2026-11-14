# lit-detect-c: practical fit of small-object detectors for symbol counting (scope L2, angle c)

Worker lit-detect-c, read-only, 2026-11-14. Reading log with one line per source: `lit-detect-c-log.md`.
Marks: **V** = I read it on the page named (licences read from the LICENSE file or model card, never from a badge);
**R** = the authors' own claim on that page; **E** = my estimate or arithmetic, with the inputs shown. All pages read 2026-11-14.
Final state: reading stopped at the lit-orch wrap-up order (about 01:13); rounds 10-17 are in the log. Sources opened: 100+ (log, one line each; rounds 10-17 added the sliced-inference study 2611.12657, SynthPID 2604.16513, the railway signal-layout paper (Sensors 2026), the historical-map signs paper 2610.13224, the D-FINE-seg repo and paper, transformers PR 48528 and issues, RF-DETR cookbooks and docs). From 2025-26: RF-DETR (arXiv 2511.09554), TinyFormer (2605.25046), ReDHF (2611.07994), BUTR
(2610.33430), frozen high-res RF-DETR (2608.03136), palynomorphs (2609.05323), bird-call spectrograms (2606.10407), RT-DETRv4 README
(2510.25257), DEIMv2 repo and licence, D-FINE-seg paper (2602.23043; PDF read in round 14), Architect-Ant (2606.10953), emit-vs-detect floorplan paper
(2608.25608), RF100-VL (2505.20612, 2025), P&ID RF-DETR card (DocEng 2026), PCB RF-DETR preprint (2026).

## 0. What this report adds (read these first)

1. **Two open licence questions are closed.** DEIMv2 (and EdgeCrafter, same company) ship a custom *non-commercial* licence covering code and
   weights (their LICENSE.md, V): out. The DEIM training recipe on D-FINE has a real Apache-2.0 LICENSE file (V; GitHub shows NOASSERTION
   only because the file has a custom header line). DINOv3 (teacher in RT-DETRv4, backbone in DEIMv2-L/X and TinyFormer) has a custom Meta
   licence, SPDX NOASSERTION (V): not in the permitted list of record 0006.
2. **Detector accuracy needed for exact counts.** The best published door/window box numbers on CubiCasa5K are AP50 about 90 (MuraNet 91.2/92.2
   at 1536 px, R; an RT-DETR-L repo 89.8/89.3 at 1024 px, V). With about 9 objects per class and independent misses, per-object recall of
   0.91 gives about 43% exact-count images, 0.95 gives 63%, 0.97 gives 76%, 0.99 gives 91% (E: (1-m)^9, false positives ignored, so
   optimistic). That sits next to the earlier measurements (2019 weights 32% windows, 36.7% doors; count-only FCN 18% on both): a detector
   at today's published AP50 would land near the 2019 net, and the target of 75-90% exact needs misses of 1-3%, so threshold tuning for
   count (not AP) and a second pass matter more than the last AP point.
3. **For 5-20 px symbols the stride matters more than the family.** D-FINE/RT-DETRv2 read a stride-8 map (config, V); RF-DETR reads a single
   stride-16 map (RF-DETR docs and paper, V), and a maintainer, asked about 5 x 5 px objects, says there is "some reason to believe that DETR detectors in general are particularly weak on small objects", that mosaic and other augmentations would work but are not in the repo, and that running at higher resolution helps at a latency cost (issue 112, re-read round 15, V; the 5 px figure was the user's, not a measured limit).
   On 100 small fine-tune sets (RF100-VL) D-FINE has equal or better small-object AP than RF-DETR at N/S/M (table 3.2), but the S/M D-FINE rows there are most likely Objects365-pre-trained, the starts with the licence caveat.
4. **rot90 and mirror augmentation is a config line in RF-DETR** (`D4`/`SquareSymmetry` are named in the repo's supported-transform list for the Albumentations path, V; the Kornia GPU path's mapping table lists flips, rotate and affine only, so D4 there is unconfirmed; the docs warn that boxes are updated automatically for geometric transforms) and a ~10-line custom
   transform in D-FINE (its transform list has horizontal flip only, V). No oriented detector is needed: rotated sheets keep axis-aligned
   symbol boxes (E, reasoning; DeepScoresV2-type oriented boxes are for beams and ties, which we do not have).
6. **Round 10-14 changes (all V unless marked):** D-FINE's README (2026-08-19) now flags Objects365-derived checkpoints as not commercially cleared: use the COCO-only checkpoint (item 1; the same Objects365 question is open for RF-DETR, section 10 item 0). D-FINE-seg (Apache-2.0) is the practical D-FINE entry point: it has `rotate_90`, `up_down_flip`, mosaic, auto batch size, and an F1 threshold sweep, but no stride-4 detection level (section 8a). The transformers D-FINE/RT-DETR loss had a real training bug, fixed in v5.21+ (section 8a). A 2026 study on aerial images says a higher single-pass resolution beats SAHI tiles at equal scale unless the images exceed trainable size (item 5), and the closest floor-plan success with toilets and sinks has symbols 4-8x bigger than ours (section 8c). Count-tuned thresholds have a precedent but no ready tool (section 8f); keep a tuned NMS even for DETRs (section 8e). Measured S/M throughput at 960-1280 px still does not exist in public sources (section 8d).
5. No GPU on this machine (`nvidia-smi` absent): every number marked E is built from anchors found in sources, not from a run.

## 1. Top 5 (floor-plan work and transfers in one list)

1. **D-FINE-S/M fine-tuned at 960-1280 px square, from the COCO-only checkpoint (not the Objects365 ones, see below): TRY (first choice for the small symbols).**
   Code Apache-2.0 (LICENSE via gh api, V); weights Apache-2.0 on HF (ustc-community cards, V). **Round 10 correction (V):** since 2026-08-19 the D-FINE README says checkpoints trained or pretrained on Objects365 (`*_obj365`, `*_obj2coco`) may be subject to the Objects365 dataset terms and should not be assumed commercially cleared; use the plain COCO checkpoints, and treat the Objects365 ones as unresolved for record 0006. In issue 214 the author also says an Objects365 start can degrade or fail on very small datasets, a second reason to use the COCO one. Features at strides 8/16/32, 300 queries
   (`dfine_hgnetv2.yml`, V). COCO AP_S: S 29.1, M 33.2, L 36.5 (V, D-FINE paper Table 1 full text re-read round 10; X is 37.3; TinyFormer Table 1 agrees). RF100-VL small AP: N/S/M 32.4/36.6/36.0
   vs RF-DETR 30.1/34.2/35.8 (RF-DETR paper Table 4, full text re-read round 10, R from a competitor; the same table gives YOLOv8/YOLOv11 N/S/M only 4.7-7.3 AP_S, with the authors' caveat on their YOLO NMS threshold). Risks (all V in the repo's issues): square input only (issue 111);
   official custom fine-tuning has an unresolved report of under 5% mAP on small RF100-VL sets (issue 214, Roboflow, an interested party);
   users get AP 0 when category ids start at 1 (issue 72); one user needed `eval_spatial_size` edited for 1280 and got mAP 0 in the official
   repo but not in a rewrite (issue 299). Mitigation: Apache-2.0 rewrite `ArgoHA/custom_d_fine` (D-FINE-seg; YOLO or COCO labels, mosaic, DDP,
   auto batch, COCO weights Apache-2.0, V; the Objects365-to-COCO ones carry the README caveat above) or the transformers port `DFineForObjectDetection` (V). Leakage: **no**.
   JSON fields: `elements` boxes (window, door, toilet, sink, shower, bathtub, sauna stove).
2. **RF-DETR Small/Medium (Apache-2.0) at 704-1024 px with D4 augmentation: TRY (fastest route to a first number).**
   `pip install rfdetr`; COCO or YOLO folder in; `batch_size="auto"`; `resolution` any multiple of 32, set in the constructor, e.g. `RFDETRSmall(resolution=1024)`,
   with the position-embedding grid resized automatically (`config.py` docstring and docs, V); per-batch multi-scale training is on by default (config, V). COCO AP_S N/S/M/L 25.2/32.0/36.1/39.0
   (paper, V) at 384-704 px. Frozen inference above the training size helps: RF-DETR-L trained at 704, run at 1120 with interpolated
   position embeddings, AP 0.327 to 0.365, AP_S 0.052 to 0.066 on one hidden benchmark (R, authors call it confounded, 2608.03136; full text re-read in round 10: AP 0.3272 to 0.3654, AP_S 0.0519 to 0.0660, rectangular inference worse at 0.3057, V). Converges
   fast on small sets: RF-DETR-L, COCO checkpoint, 10 epochs at 640 px reached 0.541 mAP50:95 on a 9-class PCB-defect set, ahead of a 100-epoch
   YOLO26x at 0.490 (R, preprint, single lineage). Risks (V, issues): stride 16; square only (rectangular gave no gain once weights loaded
   properly, issue 1052); one local tiny-object run looked unstable until a clean Python install (issue 484); `torch.compile` does not work
   reliably (issue 1410). Issue 747 (V, a commenter's view): prefer a larger size over raising the resolution of a small one, because the sizes are searched jointly; so test RF-DETR Medium at 640-704 next to Small at 1024, not only Small at high resolution. Issue 879 (V): no official minimum object size. Closest drawing run (round 16, V): RF-DETR-Seg-Large on railway signal-layout drawings at 768 px patches, where the vanilla model trailed YOLO11-seg-L on box AP50 (0.867 vs 0.920) until the authors added copy-paste for rare classes, negative patches and a localization loss (section 8d). Leakage: **no**. Not usable: Atto/Femto/Pico/XL/2XL (PML 1.0) and every community floor-plan checkpoint (table 2).
3. **DEIM recipe on D-FINE (DEIM-D-FINE S/M): MAYBE, as a convergence helper.** LICENSE file Apache-2.0 (V). Mosaic 0.5 + mixup 0.5 at 24 epochs:
   52.5 AP vs 51.7 without, AP_S 34.9 vs 32.8 (DEIM Table 4, V); CrowdHuman D-FINE-L AP_S 29.0 to 33.2 (V). The authors concede a YOLO still has
   +1.4 AP_S over D-FINE-L (V). DEIM full text re-read round 10 (V): mosaic alone gives 51.9 AP / 34.9 AP_S, and in the DEIM main table the D-FINE rows gain AP_S at every size (Nano 22.9 to 24.5, S 29.1 to 30.4, M 33.2 to 35.3, V). The RT-DETRv2 baseline rows of that table look unreliable (RT-DETRv2-S AP_S 36.1 there against 30.2 in TinyFormer's Table 1), so I draw no AP_S conclusion for the RT-DETRv2 base (correction of an earlier round-10 statement). Caution: DEIM's mosaic gain was measured on COCO; a 2026 historical-map sign study (arXiv 2610.13224, full text, V) turned mosaic off because its targets are small and context-bound, so make mosaic a dev-split ablation, not a default. Same fine-tuning risks as item 1; the repo was last pushed 2026-03.
4. **RT-DETRv2 via HF transformers: MAYBE, a fallback only with transformers v5.21 or newer (older releases train the real queries wrongly, section 8a).** Model card Apache-2.0 (V), `rt_detr_v2` in transformers (V). COCO AP_S
   S/M/L/X 30.2/32.0/36.1/35.8 (R, TinyFormer Table 1 only: the RT-DETRv2 paper gives AP and AP50 only and DEIM's table lists 36.1 for S, so unsettled). Same stride-8 map; lower AP than D-FINE at equal size.
5. **Sliced training and inference (SAHI, MIT) at 20% overlap, on top of 1 or 2: MAYBE, only if full-image misses small symbols.** SAHI itself:
   MIT licence file (V), wrappers for RF-DETR, RT-DETR, YOLOX (README, V); original gain AP50-small +4.7 on VisDrone (earlier report). On drawings
   the only use I could open is a P&ID RF-DETR card: 1280 px slices, 20% overlap, self-reported mAP50 99.96 (R, split not described). An RF-DETR
   user measured only ~13% speedup from batching tiles in TensorRT (issue 780, V). Our sheets are median 855 px, so a 640 tile is 2x2: the cost
   is small, and training on native-resolution crops (instead of downscaling to 512-640) is the cheaper route to the same effect (E).
   Round 14 counter-evidence (V, arXiv 2611.12657, aerial, YOLO family, AGPL detectors so evidence only): when the full image can be trained at a higher resolution, one pass at 2048 px beat a 1280 px pass with SAHI tiles for every detector tried (by 2.8-3.5 AP), and plain SAHI merging was the weakest setting; tiles only won where the images were too large to train a single pass (DOTA). For our sheets (median 855 px) a single pass at 1024-1536 px is cheap, so test the larger single-pass resolution before slicing. SAHI's own merge (NMS) was the weak part, not the idea of tiles.
   Rule from the one drawing-like study that tested it (PCB tile inference, arXiv 2605.24726, full PDF read in round 14 with curl and pypdf, V; detector YOLO12n, AGPL, 35 and 70 test images): train and infer at the
   same scale. A detector trained on full images collapsed to mAP50 0.01 when run on tiles; the same architecture trained on 640 px tile crops reached
   0.72 and 0.94 on two sets of 230 and 693 images; 128 px overlap lifted boundary-zone recall from 26-63% to 70-100%. So: either full sheet in and out,
   or tile crops in training and tile inference, never a mix.

Rejected for licence (V): DEIMv2, EdgeCrafter, DEIMv2-weights in transformers (code Apache, weights NC); YOLO-NAS (code Apache, **weights non-commercial**
per LICENSE.YOLONAS.md); YOLOv6, YOLOv7, YOLOv9, mmyolo (GPL-3.0); YOLOv10 and lightly-train (AGPL-3.0); RF-DETR XL/2XL (PML 1.0); RT-DETRv4 as a
*training recipe* (needs a DINOv3 teacher). Heavier or older permissive options named in the scope, not recommended for a 12 GB card inside 3 hours: Co-DETR (MIT, mmdet-fork stack, R50 55.4 AP, Swin-L 60.7 AP; README, V; last push 2024-12) and DINO-DETR (Apache-2.0, last push 2024-07);
oriented detectors (RTMDet-R, Oriented R-CNN via mmrotate, Apache-2.0, last push 2024-09, V) are unnecessary because rot90 sheets keep axis-aligned boxes (E).
Mentioned for completeness: RTMDet via mmdetection is Apache-2.0 but mmdet 3.3 asserts `mmcv<2.2.0`
while 2.2.0 is the latest mmcv and mmdet was last pushed 2024-08 (V): an install risk for a one-night run.

## 2. Full table (field: F = floor-plan/drawing work, T = transfer, G = general detector)

Columns: code licence / weights licence (read) | leakage on CubiCasa5K | benchmark and metric | input and memory | hours to first number (E, RTX 4070 12 GB, 3,828 images) | JSON field | verdict.

| # | Method (year, venue) | Field | Code / weights | Leak | Reported numbers | Input, GPU memory | Hours (E) | Verdict and reason |
|---|---|---|---|---|---|---|---|---|
| 1 | D-FINE N-X (2024, arXiv 2410.13842) | G | Apache-2.0 (V) / Apache-2.0 HF (V) | no (COCO, O365) | COCO AP 48.5/52.3/54.0 S/M/L, AP_S 29.1/33.2/36.5; RF100-VL AP_S S/M 36.6/36.0 (R) | 640 default, 1280 works (issue 299, V); L at 640 uses 8.55 GB at batch 8 per GPU (paper, V); gradient checkpointing not in repo | S at 1024: 6-7 min/epoch, 20 epochs about 2 h (E) | **try**: stride-8 map; fine-tune pitfalls |
| 2 | RF-DETR N/S/M/L (2025, arXiv 2511.09554) | G | Apache-2.0 (V) / Apache-2.0, HF card (V) | no (COCO, O365 pseudo-labelled with SAM2) | COCO AP 48.0/52.9/54.7/56.5, AP_S 25.2/32.0/36.1/39.0; RF100-VL AP S 60.9 | 384/512/576/704 default; any multiple of 32; Nano bs 2 runs on an 8 GB laptop GPU (issue 1410, V); T4 16 GB bs 4 x 4 accumulation (docs, V); checkpointing -30-40% memory, +20% time | S at 1024: about 9 min/epoch, 10 epochs about 1.5 h (E) | **try**: fastest start, D4 augmentation in config; stride 16 |
| 3 | DEIM-D-FINE (2024, arXiv 2412.04234) | G | Apache-2.0 (V) / uses D-FINE weights | no | AP_S gain +2.1 at 24 epochs (V); CrowdHuman APs +4.2 | as D-FINE | as D-FINE, fewer epochs | **maybe**: convergence aid |
| 4 | RT-DETRv2 (2024, arXiv 2407.17140) | G | Apache-2.0 (V) / Apache-2.0 HF (V) | no | AP_S S/M/L/X 30.2/32.0/36.1/35.8 (R: TinyFormer Table 1 only; the RT-DETRv2 paper itself reports AP and AP50 only, and DEIM's table gives S 36.1, so treat as unsettled) | 640; 3090 latency 1.8-4.4 ms (V) | as D-FINE M | **maybe**: fallback |
| 5 | LW-DETR (2024, arXiv 2406.03459) | G | Apache-2.0 (V) / Apache-2.0 HF card (V) | no | RF100-VL AP_S S 32.1 (R) | last push 2025-02 | n/a | **skip**: superseded by RF-DETR, stale |
| 6 | DEIMv2 S-X (2025-26) | G | custom NC (V) / NC (V) | no | COCO AP 50.9-57.8, AP_S 31.4-39.2 (V) | DINOv3 backbone for L/X | n/a | **skip**: non-commercial |
| 7 | RT-DETRv4 (ECCV 2026, arXiv 2510.25257) | G | Apache-2.0 (V) / Google Drive checkpoints | no | COCO AP S/M/L/X 49.8/53.7/55.4/57.0 | needs DINOv3 ViT-B teacher | n/a | **skip**: custom-licence teacher |
| 8 | YOLOX (2021) | G | Apache-2.0 (V) | no | AP_S not read | stride 8, any aspect | n/a | **maybe**: only if a CNN with P3 is wanted; no AP_S evidence |
| 9 | RTMDet (mmdet, 2022) | G | Apache-2.0 (V) / mmdet weights | no | COCO 44.6/49.4/51.5 S/M/L at 640; X-P6 1280 54.9 (V) | rectangular, 1280 variants | n/a | **skip**: mmcv pin, unmaintained |
| 10 | torchvision Faster R-CNN R50-FPN v2 | G | BSD-3 (V) / "may have their own licences" (README, V) | no | 46.7 box AP (source, V); smallest anchor 32 px | any aspect; stride-4 FPN level | n/a | **maybe**: needs custom anchors 8-64 |
| 11 | RT-DETR-L on CubiCasa5K (repo, 2026) | F | no licence file, Ultralytics AGPL stack / weights in repo | **YES** (CubiCasa5K train) | door/window AP50 89.8/89.3, AP50:95 57.5/62.2, 1024 px, 60 epochs (V) | 2 x A100, 2.3 h (V) | n/a | **skip**: leakage and licence; use only as an accuracy reference |
| 12 | MuraNet (ICDAR 2023 workshop) | F | no code | YES | door/window AP50 91.2/92.2 at 1536 px (earlier report) | n/a | n/a | **skip**: no code; resolution reference |
| 13 | 2DPlan2Strct (HF, RF-DETR-M, 576 px) | F | package Apache; weights non-commercial research only (USAGE_TERMS.md, V) | **unknown** (data unstated) | val mAP50 94.5 on 2,964 images (R) | 16 h on a T4 to epoch 13; CPU 458 ms/image, 2 threads, 1206 x 1013 plan (V) | n/a | **skip**: terms; only a CPU-latency anchor |
| 14 | rtdetrv2-floorplan, -v2 (HF community) | F | Apache-2.0 card / dataset "unknown" | **unknown, treat as yes** (classes window/door/stair) | door mAP 0.44 / 0.69, window 0.66 / 0.77, mAP_small 0.51 / 0.55 (R) | batch 8 | n/a | **skip**: data unstated |
| 15 | Architect (HF YOLOv8m, FloorPlanCAD) | F | AGPL base, CC BY-NC 4.0 weights (V) | no (CAD) | mAP50 87.7 (R) | n/a | n/a | **skip** |
| 16 | RF-DETR P&ID detector (DocEng 2026 card) | T | Apache-2.0 / Apache-2.0 (V) | no | mAP50 99.96, 32 classes, 10 epochs, SAHI 1280 px (R, split unknown) | n/a | n/a | **idea only**: slicing recipe |
| 17 | SAHI (2022) | T | MIT (V) | n/a | AP50-small +4.7 VisDrone (earlier report) | linear in tiles | n/a | **maybe** |
| 18 | TinyFormer (2026, arXiv 2605.25046) | T | paper CC BY-NC-ND; code not found | n/a | COCO AP_S 32.4-39.3, VisDrone better than DEIMv2 (R) | DINOv3 backbone | n/a | **skip**: no usable code/licence |
| 19 | ReDHF (2026, arXiv 2611.07994) | T | no code link found | n/a | AI-TOD-v2 +1.4 AP on Dome-DETR, 800 px, 4 x V100 (V) | stride-4 map revived | n/a | **idea only**: stride-4 features |
| 20 | BUTR (2026, arXiv 2610.33430) | T | code link in paper (licence not read) | n/a | 35.7 AP AI-TOD-v2 at 47.8 FPS T4 (R) | dense query budgeting | n/a | **skip**: our images have 30-60 objects, not thousands |
| 21 | Frozen high-res inference (2026, 2608.03136) | T | recipe only | n/a | +3.8 AP, AP_S 0.052 to 0.066 (R) | RF-DETR-L 704 to 1120 | none (no training) | **try** as a free test-time resolution sweep |
| 23 | Dome-DETR S/M/L (ACM MM 2025, arXiv 2505.05741) | T | Apache-2.0 (V) / checkpoints on HF trained on AI-TOD-v2 and VisDrone (dataset terms not read) | no | AI-TOD-v2 AP 32.1/34.0/34.7, VisDrone 35.9/38.9/39.0 (R, README) | 164-376 GFLOPs; trained on 2-4 H200/RTX 5090/4090 cards (README, V) | n/a | **skip**: 7-15x the compute of D-FINE-S, built for thousands of tiny objects |
| 24 | BUTR (2026, arXiv 2610.33430) | T | Apache-2.0 repo, last push 2026-11-13 (V) | no | 35.7 AP AI-TOD-v2 at 47.8 FPS T4 (R) | built on D-FINE | n/a | **skip**: density budgeting is unneeded at 30-60 objects |
| 22 | Equivariant YOLOv9-t, C4 (2026, CRV) | T | YOLOv9 base is GPL-3.0 (V) | n/a | +4.9 mAP COCO, +16.8 on unseen rotations of digits (R, abstract via OpenAlex) | n/a | n/a | **idea only**: not needed with D4 augmentation |

## 3. Evidence tables behind the ranking

### 3.1 Small-object AP, same footing (COCO val2017, 640 px unless noted; V from TinyFormer Table 1 and the RF-DETR paper)

| Size class | D-FINE | RT-DETRv2 | DEIMv2 (NC) | YOLO11 | RF-DETR (paper res) |
|---|---|---|---|---|---|
| S | 29.1 | 30.2 | 31.4 | 29.0 | 32.0 (512 px) |
| M | 33.2 | 32.0 | 34.2 | 33.0 | 36.1 (576 px) |
| L | 36.5 | 36.1 | 37.5 | 35.6 | 39.0 (704 px) |
| X | 37.3 | 35.8 | 39.2 | 37.7 | n/a (XL is PML) |

YOLOX (mmdetection model-zoo logs, epoch 300): AP / AP_S tiny 31.8 / 12.3, s 40.3 / 23.5, l 48.5 / 31.3, x 49.9 / 31.0, again below D-FINE at the same size class. RTMDet (mmdetection model-zoo training logs, last COCO val line, round 17): AP / AP_S tiny 40.9 / 20.4, s 44.5 / 24.9, m 49.1 / 30.3, l 51.2 / 32.7, x 52.6 / 35.9, so at similar AP its small-object AP trails D-FINE and RF-DETR (D-FINE-M 52.3 / 33.2); RTMDet is also an install risk (section 1) and has no stride-4 level (config strides [8, 16, 32], V). Source check, round 17: the D-FINE column (S/M/L/X) and the RF-DETR column (N/S/M/L 25.2/32.0/36.1/39.0) are first-hand from their own papers' tables; the RT-DETRv2 column is TinyFormer's alone (its own paper has no AP_S, and DEIM's table disagrees for S); YOLO11-S 29.0 agrees with DEIM's table, YOLO11-M is 33.0 here and 33.4 there. DEIMv2 numbers are TinyFormer's (not used for ranking, licence).

The RF-DETR column uses higher input sizes than the others; RF-DETR's own table (Table 2) lists D-FINE-M AP_S 37.6 vs RF-DETR-M 36.1 at their
respective sizes. The 37.6 is the Objects365-pre-trained D-FINE-M (AP 55.0, round 17 re-read); the COCO-only D-FINE-M is 33.2 (AP 52.3). So choosing the COCO-only checkpoint for licence reasons gives up about 4 COCO AP_S against that row; whether that carries over to our symbols is unmeasured, and RF-DETR's own weights are Objects365-pre-trained too (the open licence question in section 10). Latency columns are on different GPUs in different papers: do not compare across rows.

### 3.2 Fine-tuning on 100 small datasets (RF100-VL average, R from the RF-DETR paper, a competitor of D-FINE)

Caveat (round 17): the RF-DETR paper says D-FINE-nano "was not pretrained on Objects-365", which implies its D-FINE S/M/L/X rows are the Objects365-pre-trained models. The D-FINE S/M numbers below therefore most likely describe an Objects365 start (the licence-caveat checkpoints); a COCO-only start is not measured there. Treat the D-FINE advantage over RF-DETR in this table as an upper bound for the checkpoint we can use.

| Model | AP | AP50 | AP_S |
|---|---|---|---|
| YOLOv8/11 N-M | 55.0-57.0 | 81-82.5 | **4.7-7.3** |
| D-FINE N / S / M | 58.2 / 60.3 / 60.6 | 84.4 / 85.3 / 85.5 | 32.4 / 36.6 / 36.0 |
| RF-DETR N / S / M | 57.8 / 60.9 / 61.7 | 85.1 / 87.5 / 88.0 | 30.1 / 34.2 / 35.8 |

The YOLO small-object gap on this benchmark is large (about 30 points) but the numbers are the RF-DETR authors' (Ultralytics models are AGPL
here anyway). The authors also write that D-FINE "may be overfit to COCO hyper-parameters" (V), consistent with issue 214.

### 3.3 Resolution and slicing that papers and repos on drawings use (answer to the scope question)

| Source | Task | Input |
|---|---|---|
| MuraNet (V, arXiv 2309.00348 read in full) | CubiCasa5K doors/windows | 1536 x 1536 full sheet resized (aspect changes, area interpolation down, cubic up), no slicing; batch 10, SGD, 1000 epochs from scratch on 10 RTX 3090, no pretrained weights; a YOLOv3 baseline under the same recipe gets door/window AP50 89.2/90.1 |
| RT-DETR-L repo (V) | CubiCasa5K walls/doors/windows | 1024 x 1024 full sheet, 60 epochs; says other sizes degrade accuracy |
| 2DPlan2Strct card (V) | walls/rooms/doors/windows | 576 x 576 full sheet (RF-DETR-M) |
| RF-DETR P&ID card (R) | 32 P&ID symbols | 1280 tiles, 20% overlap (SAHI) |
| Palynomorph RF-DETR (V, 2609.05323) | dense microscopy objects | tiles resampled to about 1000 px, batch 16, one L40S |
| Roboflow blog (R, vendor, no numbers) | construction plans | tiles at the model's training resolution, merged at page level |

No paper I could open gives a with/without-slicing ablation on drawings. A Springer paper on construction-diagram symbol detection
(IJDAR 2024; search summary: YOLO 79 mAP, Faster R-CNN 83 mAP) could not be opened (empty page); it is NOT used here.

### 3.4 Time and memory anchors (what the E column is built from)

- RF-DETR Nano, 384 px: 58 ms per step at batch 2 on an RTX 4060 Laptop 8 GB; 135 ms on an L4 23 GB (issue 1410, V, eager, bf16). Docs: 149.8 ms at batch 4 on an L4 (V).
- RF-DETR-M at 576 px: 16 h on a T4 16 GB, best epoch 13, on an unstated number of images (card, V). CPU: 458 ms/image with 2 threads (V).
- RT-DETR-L at 1024 px on 4,200 CubiCasa images x 60 epochs: 2.3 h on 2 x A100, about 30 images/s in total (V, repo; arithmetic E).
- D-FINE-L at 640 px: 29 min/epoch on COCO 118k images with 4 x RTX 4090 (about 17 images/s per GPU), 8.55 GB at 8 images per GPU (paper, V).
- Scaling to a 4070 (about 0.4-0.5 of a 4090, 0.3-0.4 of an A100, E) and to 3,828 images gives: D-FINE-S at 1024 about 10 images/s (6-7 min per epoch),
  RF-DETR-S at 1024 about 7 images/s (9 min per epoch), L-size models at 1024 about 5 images/s (13 min per epoch, too slow for 20 epochs inside 3 h).
- The official D-FINE custom recipe is 220 epochs from an ImageNet backbone or 64 epochs from the Objects365 checkpoint (configs, V): 64 epochs of
  S at 1024 is about 7 h (E), so use the COCO-only checkpoint (Objects365 ones carry a README licence caveat, round 10) and 15-25 epochs. RF-DETR fine-tunes in 10-30 epochs in the sources above.

## 4. How this extends the earlier measurements (sections 2 and 3 of the context file)

- *Authors' 2019 net, zero-shot, 4 rotations, 1024 px: windows 32%, doors 36.7%, toilets 79.4%, sinks 50.5%.* Toilets and sinks are single large fixtures
  (icon IoU 62.8 and 55.7 in that paper); a box detector should beat them on those two classes first. Windows and doors need the miss rate below
  3% (table in section 0). The published detector AP50 of 89-92 therefore predicts exact-count rates around 40-50%, near the 2019 net, not a jump.
- *Compute behind the published numbers.* MuraNet's AP50 of 91-92 took 1000 epochs from scratch on 10 RTX 3090s (V); its own YOLOv3 baseline under that recipe reaches 89-90. The RT-DETR-L
  repo reached 89.8/89.3 in 60 epochs from COCO weights on 2 A100 (2.3 h, V). So pretrained DETR weights cut the schedule by about 16x, and 15-30 epochs from a COCO checkpoint is the
  right order for our budget, but whether it reaches AP50 90 at 3,828 images is not shown by any source (the repo used 4,200 training images, close to ours).
- *Count-only FCN 59.3% (windows, doors 18%).* A detector with box supervision removes the "needs boxes or points" limit that run found; the open
  question is calibration, which belongs to L3 (counts per class from a confidence threshold tuned on dev for exact match, not for AP).
- *SAHI +4.7 AP50-small* (earlier report): the only other measurement here is the frozen high-resolution result (+3.8 AP, +0.014 AP_S on a different task).
  Together they say "raise the resolution before adding slicing", and RF-DETR gives that as a test-time sweep with no retraining.
- *rot90 + flip training augmentation was agreed as the fix for rotated sheets:* RF-DETR does it by config; D-FINE needs a custom transform. Test-time rotation
  (4 views) multiplies cost by 4 (E); training with D4 should make it unnecessary for the 0/180/90 sheets (hypothesis, to test on dev).
- *Door counting convention (door with a leaf; door-without-leaf 1.8k in the export):* train them as two classes so the count rule stays in the JSON stage.
- *Window strips:* one box per drawn cell, adjacent and touching. DETR-family detectors are one-to-one matched and need no NMS, which is the right fit for
  touching equal boxes (V: RF-DETR "NMS-free"; D-FINE end-to-end). Only SAHI adds a merge step; use a class-wise NMS with a high IoU threshold or none inside a tile.

## 5. What breaks on our images, candidate by candidate (5-20 px symbols, exact-multiple rotations, scans)

- **RF-DETR S/M/L:** one stride-16 map. A 10 px window on an 855 px sheet becomes 6 px at 512 and about 8 px at 704; below one 16 px patch it relies on the
  ViT's sub-patch features. Fix in this order: train at 1024, upscale small sheets (Lanczos, never generative; earlier reports), then test-time 1120-1280.
  Square input squashes landscape plans (E: median plan aspect not measured here); the maintainers recommend squash and found no loss (issue 1052, V).
- **D-FINE / RT-DETRv2:** stride 8 helps, but 1024 and above is untested by the authors and reports of failed fine-tunes exist (issue 214, 72, 299, V). First run
  must be a smoke test on 200 images (loss falls AND AP is non-zero) before the full run; check category ids start at 0 (or add a dummy class 0).
- **All detectors:** 30% of images are under 500 px on the short side, so a 5 px symbol is 2-3 px after any detector's stem; those images need 2-3x upscaling
  and will still lose some symbols. Scans and phone photos: no detector paper here tests that; this must come from the augmentation (L9 scope).
- **Query cap:** 300 queries (RF-DETR N-L, D-FINE) is far above the 30-60 symbols per sheet; BUTR/Dome-DETR density budgeting (thousands of objects) is not our problem.
- **Mirrored copies and flips:** fine for symbols; Finnish labels (text) mirror, so flips must not feed a text recogniser in the same run (L5 scope).
- **Sheets with several plans:** a detector counts all symbols on the sheet and cannot say "one plan"; the per-plan box (not yet exported) is a separate detection class in the
  same model (E: add a `plan` class once the export exists).
- **Scans:** the one controlled study found (Automation in Construction 2026, doi 10.1016/j.autcon.2026.107193; abstract read through OpenAlex, full text blocked) pairs CAD-derived and scanned
  CubiCasa5K rasters with identical labels and three-seed RT-DETR runs: loss from scanning is class- and scale-dependent, AP at IoU 0.75 and 0.85 falls much more than AP50, and the change of how the
  object itself is drawn (not the paper background) causes most of it (R). For counting that is the favourable direction: tune and score at IoU 0.5. Its released checkpoints are CubiCasa5K-trained (leak: YES);
  its paired dataset variants are CubiCasa5K derivatives (CC BY-NC terms inherited, not read).
- **Other detectors on the same data:** a 2025 master's thesis on a Finnish repository (abstract read via OpenAlex; the institution is uncertain: a search summary names another Finnish university, the repository page is behind a bot check that I did not bypass) compares YOLOv8, YOLOv11 and Detectron2 Faster R-CNN on CubiCasa5K for walls, doors and windows and
  reports YOLOv11 best on schematic 2D data; numbers not read (PDF not opened). No DETR-family result there.
- **Ground-truth noise:** the gas-plant P&ID paper notes manually drawn boxes vary a lot for the same symbol, which hurts AP at high IoU but not counts (V, 2511.08609).
  Train and tune for IoU 0.5, not 0.5:0.95; our counts do not need tight boxes.

### 5b. Fit with the pipeline and the judging rules (docs/REQUIREMENTS.md, docs/PIPELINE.md, read)

- "Ingest once, answer cheaply": the detector runs once per drawing, not per question, so a 1-2 s page on a GPU or CPU is acceptable. The only CPU number found is RF-DETR-M at 576 px,
  458 ms/image on 2 threads (V); scaling by pixel count to 1024 gives about 1.5 s (E). "Low inference cost" is one of four judged criteria: a 10-32 M parameter local detector costs
  nothing per call, which beats any per-page API. For the cost per page on the rented GPU (open question 4 in the requirements): at 0.1-0.2 s per page (E, bf16 PyTorch at 1024 px, not measured) the 5,939 files take 10-20 minutes of one GPU; on CPU at about 1.5 s per page (E) the same set takes about 2.5 hours on one stream, so CPU is for a demo, not for the bulk ingest.
- The detector fills `elements` (and, with a `plan` class, the plans count). It is one `Extractor` adapter in the ports-and-adapters layout; weights stay outside the repo (record 0003).
- Stage 8 needs a second, *independent* count. Two detectors of different families (D-FINE: HGNetv2 stride 8, RF-DETR: DINOv2 ViT stride 16) trained on the same boxes share their labels,
  so their errors are partly correlated: use them as a disagreement flag, not as independent proof (E). The independent methods in the requirements (printed totals, parser) remain the real second count.

## 6. Leakage flags on every checkpoint named here

| Checkpoint | Trained on | Leak (CubiCasa5K) |
|---|---|---|
| RF-DETR N/S/M/L COCO weights | COCO, Objects365 (SAM2 pseudo-masks) | no |
| D-FINE COCO / Objects365-to-COCO (HF ustc-community, D-FINE-seg) | COCO, Objects365 (README licence caveat since 2026-08-19 for the Objects365 ones) | no (leakage); licence open for the Objects365 ones |
| RT-DETRv2 COCO (HF PekingU) | COCO | no |
| LW-DETR (HF xbsu) | COCO, Objects365 | no |
| RF-DETR P&ID detector (HF dimtri009) | P&ID symbols | no (but irrelevant classes) |
| RT-DETR-L floor-plan repo (OldDeLorean) | CubiCasa5K train split | **YES** |
| Architect-Ant's RT-DETR-X wall/door/window detector | CubiCasa5K | **YES** (not published as far as read) |
| MuraNet | CubiCasa5K | **YES** (no weights) |
| Voix7/rtdetrv2-floorplan, -v2 | "unknown dataset" (window, door, stair) | **unknown, treat as yes** |
| OsamaMo/2dplan2strct | unstated, 2,964 val images | **unknown, treat as yes** (and non-commercial) |
| SamirShabani/Architect | FloorPlanCAD (CAD) | no, but non-commercial and AGPL base |

## 7. From other fields: transfer notes (angle b covers the sideways search; these are the ones my reading touched)

| Field and task | Plays the role of our object | Why it should transfer | What breaks on our images | Code and weights |
|---|---|---|---|---|
| Microscopy, whole-slide palynomorph detection (2609.05323, V) | a window cell in a strip: dense, overlapping, repeated | RF-DETR kept higher recall than YOLO26-L in cluttered, overlapping regions; tiles about 1000 px | their model is RF-DETR-2XL (PML licence); single class; no thin-line background | recipe only; N-L weights work as they are |
| Spectrogram call localisation (2606.10407, V) | thin symbol on a structured background | natural-image DETR weights fine-tuned to a non-photo domain, 5 seeds, Large best; out-of-domain F1 20 points lower | their domain gap is across recordings, ours is across drawing styles: expect the same 20-point drop on unseen styles | works as is, fine-tune |
| PCB defect detection (preprint, R) | small defect on a regular pattern | RF-DETR-L from COCO, 10 epochs, 640 px beat a 100-epoch YOLO | no AP_S; single run; boxes on repetitive background similar to hatching | fine-tune on our boxes |
| Electron-microscopy dislocation counting (arXiv 2608.28495, V) | a door symbol whose pixel size differs per image | per-image scale self-calibration: mean object size from eight 200 px windows sets tile = 10 x object size, refined by fitting detection count against tile size to a Gaussian (5-15 s per image); then tiles with overlap, NMS IoU 0.30, and a count-tuned confidence threshold 0.025 chosen on a calibration subsection, far below the validation-optimal value; reported 98.6% counting accuracy on thousands of objects (R) | our counts are single digits, where one miss is 11%, not thousands that average out; 5-15 s x 5,939 files is 8-25 h, so use 2-3 candidate scales and pick by detection agreement instead (E); one YOLOv8 detector (AGPL) | method only |
| High-resolution PCB inspection with tile inference (arXiv 2605.24726, full text V since round 14) | a 5-px defect lost when a full board is resized | tile training and inference at one scale, 128 px overlap, a training-free tile-adjacency merge of boundary scores | defects, not thin repeated symbols on wall lines; detector family not stated in the abstract; sets are 230 and 693 images | method only; code not found |
| Aerial and tiny-object DETRs (ReDHF, BUTR, TinyFormer, 2026) | 4-10 px objects | reviving a stride-4 map gave +1.4 AP on AI-TOD-v2 | no usable code or permissive licence found; AI-TOD objects are blobs, ours are thin-line | idea only |
| Rotation-equivariant detection (CRV 2026, R) | rot90 sheets | C4-equivariant convolutions reduce parameters for rotation invariance | base is YOLOv9 (GPL); D4 augmentation gets the same invariance for free here | idea only |
| P&ID and construction plans (RF-DETR card R, Roboflow blog R) | valve symbols | same pipeline: tile, detect, merge | self-reported near-perfect scores on a split not described; no counting results | recipe only |

## 8. Citation walks

- Forward from **RF-DETR** (arXiv 2511.09554): Semantic Scholar returned HTTP 429 repeatedly, so I used OpenAlex (140 citing works on 2026-11-14) and the arXiv
  full-text search for "RF-DETR" (about 35 papers, newest first). Relevant hits read: frozen high-resolution inference, palynomorphs, bird-call spectrograms,
  AEC layout benchmark (abstract only, L9 scope), PCB defects (full text since round 14), P&ID DocEng 2026, equivariant detection (abstract), hieroglyph detection (abstract). No 2026 paper
  reported RF-DETR on floor plans or on CubiCasa5K symbols.
- Forward from **D-FINE** (arXiv 2410.13842): Semantic Scholar pages 0-199 (about 200 citing papers), plus RT-DETRv2 (2407.17140) citations 100-199, filtered by title: dozens of 2026 small-object DETR variants
  (UAV, remote sensing, defects), of which ReDHF, BUTR and TinyFormer were read; HR-DFINE (traffic signs), SODBoost and PCB-MC were not opened. One floor-plan hit
  (Architect-Ant) is a furnishing-layout paper that uses a CubiCasa-trained RT-DETR-X as an annotator. None reports D-FINE on CubiCasa5K symbols.
- Forward from **SAHI** (arXiv 2202.06934, third paper walked): OpenAlex, 494 citing works dated 2025-26, filtered by title. Read: PCB tile inference with topology-aware merging
  (abstract). Seen but not readable or off-scope: a minimum-dataset-size study for crop counting with a fine-tuned detector (MDPI, access denied), PIDQA on P&IDs (L7),
  a CAD cross-block boundary-fusion method (BBOD-CAD, paywalled), a historical-plans segmentation paper, cipher-symbol dataset on handwritten documents (HHCS, IEEE Access 2026).
  None gives a floor-plan result.
- Forward from **MuraNet** (arXiv 2309.00348, the best door/window result on CubiCasa5K; fourth paper walked): OpenAlex lists 11 citing works. 2025-26 titles: the scan-robustness study (abstract read),
  Intelligent Parsing of Floor Plans for Full-Scenario Applications (IEEE 2025), Rotation Invariance in Floor Plan Digitization Using Zernike Moments (2025), Hierarchical IoU for floor-plan vectorisation (J Comput Civ Eng 2025),
  Patch-Wise Analysis and Reconstruction of Large-Scale Floorplan (IEEE Access 2025), HHM-UNet state-space segmentation (2026), two 2026 Buildings papers on sketch-to-BIM and AI-generated plans to CAD. Titles only; none was opened
  and none reports a DETR-family detector.
- Backwards: RF-DETR paper references LW-DETR (read), DINOv2 (licence read), RF100-VL (read), SAHI (earlier report). D-FINE references RT-DETR and DEIM (read).
- Forward from **SAHI** and **RF-DETR** and **D-FINE** (round 16, Semantic Scholar; the free API answered after an earlier 429): RF-DETR has 100+ citing works, almost all agriculture, UAV, medical and industrial; the one drawing paper with an RF-DETR model is DSC (railway signal layouts, read in full, section 8d). SAHI's 2026 citers (202) include drawing-related titles I could only read at abstract level or not at all: BFM-Net legend matching for engineering drawings (grid chunking plus a high-recall YOLO detector beat full-image baselines, F1 71.1%, abstract only), a ship fire-control-plan symbol detector, BIM generation from raster architectural drawings (titles only, publisher or SSRN pages). D-FINE's 2026 citers show nothing on drawings.
- Forward from **DEIM** (OpenAlex cites, 2026, 40 titles read): UAV, remote-sensing, PCB, agriculture and thermal variants (AMFC-DEIM, HMF-DEIM, ED-DETR, EFSI-DETR and similar), titles only; none on floor plans or drawings.

- Round 17 MuraNet forward walk (Semantic Scholar, 8 citers): the scan-robustness study (AutCon 2026, CC BY) and the patch-wise floor-plan paper (IEEE Access 2025) have open-access links but the publisher pages refused automated fetches (403 and an empty page), not bypassed: still abstract-level or unread. The other citers are segmentation or review papers.
- Dependency check, round 10 (V, dependency files read 2026-11-14): D-FINE `requirements.txt` has no GPL or AGPL package (faster-coco-eval is Apache-2.0). RF-DETR core needs torch, supervision (MIT), pydantic; the `train` extra adds peft, pytorch_lightning, torchmetrics, hotcoco and faster-coco-eval; no ultralytics. Licences of peft, lightning, torchmetrics and hotcoco were not read; check before shipping a container.

- Adjacent field, round 10 (historical-map sign detection, arXiv 2610.13224, V; electrical/circuit/music searches, titles only): a crop-trained (640 px) COCO-pretrained detector reached single-class recall 38.9% at IoU 0.5 with mosaic off; nothing there beats the ranking above, and the one detector used is AGPL.

## 8a. Training entry points we would actually run (round 11, V from configs, READMEs, issues read 2026-11-14)

| Entry point | Licence | rot90 / flips | Stride-4 level | Small-object notes | Threshold tuning |
| --- | --- | --- | --- | --- | --- |
| D-FINE-seg (`pip install dfine-seg`, repo ArgoHA/D-FINE-seg, formerly custom_d_fine) | Apache-2.0 | `rotate_90`, `up_down_flip`, `left_right_flip`, `rotation_degree` in config (defaults 0, 0, 0.3, 10 deg at p 0.05); `rotate_90` documented for "aerial, documents"; mosaic 0.8 | **no** for detection (P3-P5 only); a 1/4 map exists only in the segment heads | issue 58: maintainer advises a 640/800/960 sweep, no numbers; issue 84: slicing requested, not shipped | F1 sweep 0.05-0.95 at IoU 0.5 per dataset (not per-image count) |
| transformers `AutoModelForObjectDetection` with `Roboflow/rf-detr-medium` (task guide) | code and card Apache-2.0 | write our own albumentations pipeline (guide uses HorizontalFlip, Perspective); `D4` is one line | no (stride 16 projector) | none read | none (we write it) |
| official D-FINE repo | Apache-2.0 | its own transforms, config-driven | no | issues 72, 214, 299 (earlier) | none |
| `rfdetr` package | Apache-2.0 | D4 via config augmentations (earlier) | no | issues 747, 879 | none |

**Pitfall for both D-FINE routes (V, issue 139):** official D-FINE squeezes every image to a square at training time (aspect ratio changes) but its ONNX example letterboxes at inference; D-FINE-seg has `keep_ratio: False` by default. Our sheets have varied aspect ratios, so choose one mode (letterbox, `keep_ratio: True`) for training, dev scoring and the pipeline, and keep it identical.

**Pitfall for the transformers route (V, round 12):** the D-FINE and RT-DETR/RT-DETRv2 loss in transformers computed the main matched loss over the denoising queries too, so the real queries were under-trained. Fixed by PR 48528 (merged 2026-09-11); release v5.14.1 still has the bug, v5.21 and later (checked: v5.21, v5.22.0, v5.23.0) contain the fix. Pin transformers at v5.21 or newer and compare a short run against the official repo before trusting a mAP from this route. An RT-DETRv2 fine-tune following the community notebook also reported exploding grad norms and CUDA OOM after some epochs (issue 46692, closed, cause not settled in what I read). This is another reason ranking puts D-FINE-seg and `rfdetr` ahead of the transformers D-FINE/RT-DETRv2 route.

**Pitfall for DDP on empty images (V for RT-DETR, E for D-FINE):** RT-DETR issue 672 (closed 2026-06) reports a hang on multi-GPU training with denoising queries when one GPU's batch has no annotated object at all. D-FINE reuses that denoising design, so on 2+ GPUs either drop images without symbols or test a short DDP run first; single-GPU runs are unaffected. RT-DETR issue 71 (small objects, AP below 0.1, open since 2023) has no maintainer answer.

Consequence (E): no permissive detector read has a stride-4 detection level. If 5-20 px symbols are missed, the options are upscaling the input (a stride-8 map then sees them at 2x the pixels), slicing, or the one-line fix of Faster R-CNN FPN (BSD-3, stride 4), all measured nowhere on our images.

## 8c. Symbol size in pixels against input scale, from the drawing papers I could open (round 11)

No paper I opened reports accuracy per symbol size on drawings; the table gives what each reports about size and input scale, and what happened. "Native" = at the sheet's own pixels. Sizes as printed by the authors.

| Source (read in full or the cited section) | Domain | Symbol size, px | Input to the detector | Outcome as reported |
| --- | --- | --- | --- | --- |
| SynthPID 2604.16513 (V, text) | P&ID, sheets 7000 x 4500 | often 8 x 8 (connector nodes); sub-pixel after resizing the sheet to 800 px long side | 1500 x 1500 patches, stride 750, "symbols 50-200 px" | full sheet at 800 px: "box regression becomes unreliable"; patch route: edge mAP 63.8 on OPEN100 (graph metric, not box AP) |
| P&ID to graphs 2411.13929 (V, text) | P&ID, resized to 4500 x 7000 | not tabulated in text read | patches, at least 50% overlap; Faster R-CNN at 1024 x 1024 | loose boxes plus small symbols lose AP at high IoU (authors) |
| Deep Watershed Detector 1805.10548 (V, text) | handwritten and printed music | scale fixed by staff interline, 10 px or 20 px | whole page at that scale, random 960 x 960 crops in training | a 10.5 Mpx page exhausts 24 GB: the cost of upscaling whole pages |
| Symbol spotting on floor plans 2006.00684 (V, text and tables) | residential plans from PDF at 150 DPI, sheets about 5400 x 3600 | bathroom sink 70 x 80 | 224 x 224 tiles at native scale, stride 50 (YOLOv2, ResNet50) | tile validation AP50 96.2; on 25 whole plans AP50 89.3 (toilet 100, bathroom sink 85.0, window 75.6, entry door 86.4, shower 100); sheet resized to a fixed small size is named as the failure it avoids |
| MEP lighting symbols 2608.14317 (V, method) | floor plans from PDF, private set | not stated | 1000 x 1000 tiles, 0.2 overlap, Mask R-CNN | bbox mAP 0.7596, mAP50 0.985; no full-image comparison |
| MuraNet 2309.00348 (V, earlier; sizes re-read round 11) | floor plans (CubiCasa5K, average sheet 1399 x 1597, range 430 x 485 to 6316 x 14304) | not stated | 1536 x 1536 full sheet (about native scale for the average sheet), no slicing | door/window AP50 91.2/92.2 |
| RT-DETR-L floor-plan repo (R, earlier) | floor plans | not stated | 1024 px | door/window 89.8/89.3 |
| CaSiDD 2610.13224 (V, text) | historical-map signs | "already small" | random 640 x 640 crops, mosaic off | single-class P 75.7, R 38.9 at IoU 0.5 |
| Frozen high-res inference 2608.03136 (V, text) | aerial-like benchmark | AP_S 0.05 | 704 vs 1120 at test time | AP_S 0.052 to 0.066, rectangular worse |

The floor-plan precedent with our symbol classes (2006.00684): its sink is 70 x 80 px at 150 DPI, i.e. 4-8x larger than our 5-20 px symbols, trained on native-scale tiles; so the closest published success has far bigger symbols than ours, and no published run on 5-20 px floor-plan symbols exists in what I read.

Our sheets are smaller than CubiCasa5K's average (median 855 px against 1399 x 1597), so the same 1536 px input is an upscale of about 1.8x for us, where MuraNet's was about 1.0x: the one published 91-92 AP50 setting is not reached by simply copying the input size.

| PCB tile study 2605.24726 (V, full PDF; replaces the abstract-only row above) | PCB defects, sheets about 2.6k px; at 640 px the median box is 13 x 13 px, 5-6% of boxes under 64 px2 | 4-8 px side (16-64 px2) and above | Full-640 / Full-1280 / 640 tiles with 128 px overlap (YOLO12n, AGPL, 50 epochs, 35 and 70 test images) | mAP50 0.07 / 0.64 / 0.72 and 0.19 / 0.85 / 0.94; recall for 4-8 px boxes (13 and 18 boxes): 0 / 0 / 0.46 and 0 / 0.17 / 1.0; for larger boxes 0.10-0.24 / 0.68-0.91 / 0.80-0.97 |
| Railway signal-layout drawings, DSC (Sensors 2026, V full text) | engineering drawings up to about 9624 x 2648 px, compact joint symbols plus long track elements | not stated | RF-DETR-Seg-Large, 768 x 768 patches, stride 384 (train) and 614 (inference), RTX 4090 | tiles then document-space merge: P 0.899, R 0.947, F1 0.923 on 10 drawings (1,755 instances); vanilla RF-DETR-Seg-L box AP50 0.867 vs YOLO11-seg-L 0.920 on the same patches, adapted model 0.926 |
| Sliced inference study 2611.12657 (V, text and Table 1) | aerial (VisDrone, DOTA), long side about 1360 px | small, not stated | YOLOv10s single pass at 1280 / 2048 / 2560 px | AP 33.7 / 38.5 / 39.5; 1280 px with SAHI tiles 31.5; at equal compute raising resolution beat a bigger model; on DOTA tiles beat a 2048 px pass by 4.3-5.6 mAP50 |

| DeepScores 1804.00525 (V, text) | printed music at 400 dpi | tiny, about 270 objects per page | pages 1894 x 2668 | the authors report standard YOLO/R-CNN detectors struggle; the fix in 1805.10548 is to normalise scale by staff interline and crop 960 x 960 |

Reading the PCB table as size against recall (the only table I found that gives it, small counts, one AGPL detector): on a 640 px input boxes of 4-8 px were not found at all by the full-image models; doubling the input to 1280 px recovered a few (0 to 17%) and most larger ones (68-91%); tiles at native scale recovered 46-100% of the smallest ones. Our symbols are 5-20 px at 855 px sheets, so the same ordering says: at 1024-1280 px input the larger symbols are reachable by a single pass, the 5-8 px ones are the ones that need native-scale tiles or a 2x or larger upscale (E).

What this says for the upscale factor (E): the two P&ID papers bring 8 px symbols to 50-200 px by cropping at near-native scale, i.e. an effective object size of tens of pixels at the detector input; the floor-plan results (MuraNet, the RT-DETR-L repo) work at 1024-1536 px on a full sheet. Our symbols are 5-20 px on sheets with median 855 px (earlier sections): at 1024 input that is a factor of about 1.2, at 1280 about 1.5, so symbols arrive at 6-30 px, still below the 50 px the P&ID authors aim for. A first sweep of {1.0, 2.0, 3.0} times the native scale on a 200-image dev subset, with 640-px crops at the larger factors, would settle it; no paper gives the answer for our size.

### 8d. Measured training throughput and memory at 960-1280 px (round 11): still not found

Searched the D-FINE and RF-DETR repos' issues and docs, the D-FINE-seg README and issues. What exists: RF-DETR-L on an RTX 5090 ran 2.1-2.7 it/s at 1307 iterations per epoch, about 8-10 min per epoch, batch size and resolution unstated (issue 1544); a maintainer's repro on a 12 GB RTX 5070 trained RFDETRLarge at batch 4-8 without a memory problem, version 1.11.0 using about 5% more memory than 1.10.1; D-FINE-seg claims AMP saves "about 40% VRAM, about 15% faster" and has `batch_size: -1` auto-probing to about 70% VRAM. Nobody reports images per second, GB or epochs-to-converge for S/M at 960-1280 on 2-5k images. The earlier estimates in 3.4 and 8b therefore stay estimates (E); the first measured number should come from `batch_size="auto"` and `train.batch_size: -1` on our own boxes.

One epochs-to-converge anchor (R, D-FINE-seg paper 2602.23043, read from the PDF): from COCO weights at 640 px, D-FINE-seg was trained for 50 epochs on a trash-detection set (59 classes), against 100 epochs for the YOLO26 comparison, on a 16 GB RTX 5070 Ti benchmark box; dataset size not read. It supports 15-50 epochs from COCO weights as the range to plan, not a measured number for our data.

RF-DETR token arithmetic from `config.py` (V for defaults, E for the scaling): Small defaults to 512 px, Medium to 576 px, both patch 16 with 2 windows, so a resolution must be a multiple of 32; at 1024 px the backbone sees 64 x 64 = 4096 tokens against 1024 (Small) or 1296 (Medium), about 4x and 3.2x, so expect per-image time and memory of at least that factor over the default; at 704 px it is 44 x 44 = 1936 tokens (1.9x and 1.5x). This is why the first plan runs Medium at 640-704 next to Small at 1024.

Anchor from drawings with RF-DETR (V, DSC, Sensors 2026, full text): RF-DETR-Seg-Large trained on 4,813 patches of 768 px from 57 drawings (one third negative) on one RTX 4090 with batch 4 x 7 accumulation, at most 100 epochs with early stopping, runs at 35 ms per 768 px patch and 3.7 s per whole drawing with OCR and rules; training time and memory not stated. Their lessons for us: add negative patches (about 39% of patches), copy-paste the rare classes, and merge tile duplicates with a containment rule (box NMS 0.5, then mask intersection-over-minimum 0.6) because tile fragments of one object can have low IoU; for exact counts that merge cut false positives from 288 to 186. Caveat: Large segmentation model, not Small/Medium detection, and the vanilla model trailed YOLO11 on box AP50 until adapted.

Training-time anchor (R, RF-DETR fine-tuning cookbook, vendor claim): RFDETRSmall at 512 px, 50 epochs on about 1,500 images (75,000 image-epochs), 10-25 minutes on an RTX 3090, A10 or T4 class GPU, i.e. about 0.008-0.02 s per image-epoch at 512 px; the notebook gives 384-640 px as the practical range. Scaling to our case (E, arithmetic): 3,828 training images x 20 epochs = 76,560 image-epochs, about the same as the cookbook run, so about 10-25 minutes at 512 px; at 1024 px the backbone has at least 4x the tokens, so plan about 40-100 minutes per run, more with heavy augmentation or slow data loading. This is shorter than the 2-3 h estimate in 8b, which is therefore a safe upper bound for Small at 1024.

CPU anchor (V, RF-DETR docs and cookbook, round 17): RFDETRSmall at its default 512 px runs at 374 ms per image on 4 physical x86 cores with OpenVINO fp32 (402 ms eager PyTorch, 547 ms ONNX Runtime, INT8 slower on that host), 320 MB host memory; by the token arithmetic above 1024 px would be at least 4x that, so about 1.5 s per image or more, i.e. 5,939 files about 2.5 hours or more on 4 cores (E).

Query cap (V, RF-DETR FAQ): `num_queries` is the hard limit on objects per image, and raising `num_select` alone only adds duplicate boxes; the DSC drawing run used 200. Our sheets carry 30-60 symbols, well inside the 200-300 default; D-FINE uses 300 queries (config). Not a constraint for us, worth one assert on the largest dev image.

### 8e. Duplicates and counting with NMS-free detectors (round 12)

RF-DETR issue 434 (V, open): a team counting single objects fine-tuned RF-DETR-Small and saw two boxes at IoU above 0.9 on one object; 20 epochs showed it often, 85 epochs and ONNX opset 17 made it rare but not gone, and they added NMS. Maintainer view: converged loss should remove duplicates. For our exact counts one duplicate is one wrong answer, so keep an NMS or box-merge step with a tuned IoU (on dev) as part of the pipeline even though the DETR models advertise none (E), and train at least to convergence on the early-stopping signal, not a fixed 20 epochs.

### 8f. Tuning the score threshold for per-image count instead of AP (round 11)
- Ready tool, half of it (V, round 17): `rfdetr` 1.12.0 `ClassThresholds` lets `predict(threshold=...)` take one cut-off per class, and the RF-DETR cookbook tunes them on held-out images by F1. Its own COCO result: the best single threshold (0.41) beat the default 0.5 on macro F1 (0.682 vs 0.658), per-class thresholds did not beat the single one (0.678), and classes under 20 tuning objects stay on the single value. The loop to tune for exact count instead of F1 is the same code with another score, so a count-tuned version is a small change to that notebook (E).

- Precedent (V, arXiv 1604.03505, section 3.1 read): choose, per category, the score threshold and then the NMS threshold by grid search on a held-out set so that counting error is smallest; the detector is otherwise untouched. This is the recipe to copy: tune on dev, one threshold per class, score exact-count accuracy, not F1.
- Image-level calibration with a guarantee (V, arXiv 2505.24038, losses read): a conformal rule picks the confidence threshold so that at least as many predictions as true objects are kept with a chosen probability. One-sided, so it helps recall of every object but does not give exact counts; a use is to pick the upper bound of a threshold range.
- What the training repos do (V): D-FINE-seg sweeps 0.05-0.95 for F1 at IoU 0.5 per dataset; RF-DETR and D-FINE report AP only. No repo tunes for per-image count; it is a 10-line loop over saved dev predictions (E): for each class and threshold, the share of dev images whose count equals the label count.
- Note (E): single digits per class make exact-count accuracy a coarse, noisy objective; use a smoothed pick (the middle of the best plateau), not the arg-max.

## 8b. Suggested first-number plan (all timings E; for the orchestrator to accept or change)

1. Convert the dev boxes to one COCO folder (classes: window, door, door-without-leaf, toilet, sink, shower, bathtub, sauna stove; category ids starting at 1 with a dummy class 0 for D-FINE). RF-DETR also reads YOLO format.
2. Smoke test on 200 images for each detector (about 20-30 min each): the loss must fall and AP must be non-zero after 3 epochs. This catches the failure modes in D-FINE issues 72, 214 and 299.
3. Run A on the 16 GB card: RF-DETR-S, `resolution=1024`, `batch_size="auto"`, D4 augmentation, 15-20 epochs (about 2-3 h). Run B on the 12 GB card: D-FINE-S (via D-FINE-seg, `pip install dfine-seg`) from the plain COCO checkpoint (Objects365 ones carry a licence caveat),
   1024 px, `keep_ratio: True`, `rotate_90` and `up_down_flip` on, mosaic as a dev ablation, 15-20 epochs (about 1-3 h; see 8d for the scaled estimate). Two different families also give a free disagreement signal.
4. Score both on dev only: per-class AP50, then exact-count rate per question template after tuning one confidence threshold per class for exact match (not for AP; see L3 and the dislocation-counting transfer).
   Compare against the 59.3% count-only FCN and the 53.1% 2019 weights. Report windows and doors separately.
4b. Before any slicing, sweep the single-pass resolution (round 14 finding): the same trained model scored at 1024 and 1280 px (RF-DETR frozen high-resolution inference), then a model trained at 1280 and 1536; add Medium at 640-704 next to Small at 1024 (issue 747 advice). Add a tuned NMS or containment merge (8e) and the pipeline's duplicate check to the exact-count score.
5. Tripwires: if window AP50 is under 70 after 5 epochs at 1024 and the resolution sweep does not fix it, retrain on 640 px crops of a 2x-upscaled sheet with 128 px overlap tiles (same-scale rule from the PCB study, whose full text round 14 confirmed); if memory fails at 1024, turn on
   gradient checkpointing (RF-DETR, -30-40% memory) or drop to batch 2 with accumulation.
6. Do not use the eval split until a milestone, and do not start from any checkpoint in the leakage table marked YES or unknown.

## 9. Looked for and did not find

- Any exact-count (per-image) result for floor-plan symbols from a box detector, or AP for toilet, sink, shower or sauna-stove from one (as in the earlier reports).
- Any with/without-slicing ablation on floor plans or P&IDs; any paper that trains RF-DETR or D-FINE on CubiCasa5K and reports it with usable weights.
- CPU latency for D-FINE or RT-DETRv2 (RF-DETR-S at 512 px: 374 ms, 4 cores, OpenVINO, docs; RF-DETR-M: 458 ms at 576 px, 2 threads, earlier). No ONNX/OpenVINO number for any candidate on CPU; RF-DETR maintainers say ONNX CUDA is poor for transformers (issue 780, V).
- Measured training time on a 12 GB GPU for D-FINE at 1024 px (only 4090 and A100 anchors).
- (Resolved in round 17) AP_S for YOLOX and RTMDet: the READMEs and papers give AP only, but the mmdetection model-zoo log files carry it (section 3.1).
- Round 10 retry with new terms (OpenAlex, 2025-26, abstract level): no paper trains RF-DETR or D-FINE on floor-plan symbols or ablates slicing there. Nearest: a YOLOv11 symbol detector on 1,000 fire-protection plans (5,291 symbols, 12 classes, mAP50 90.6% k-fold, 96.3% on a 10% test set; AGPL base, so method only) and DoorDet (2026, detector + LLM + human labelling of door types; no detector numbers in the abstract). Treat "none found".
- Round 11 retries: still no CPU ms for D-FINE or RT-DETRv2 (D-FINE-seg ships OpenVINO export and a `dfine hw_bench` command, so we can measure it ourselves); RTMDet AP_S now found in the mmdetection model-zoo logs (section 3.1), YOLOX AP_S also found in the same model-zoo logs; the stride-4 search found only one-star research repos (DRQ-DETR, Apache-2.0, not read).
- A permissive, maintained detector with a stride-4 or P2 map: none (Faster R-CNN FPN has it; the DETR repos do not).
- Whether DINOv3 weights licence allows a distilled student to ship: not resolved; avoided.

## 10. Open questions, missing tools

0. (round 10; card check round 15) Objects365 terms: D-FINE's README now warns that Objects365-derived checkpoints are not cleared commercially; RF-DETR's paper includes Objects365 pre-training (ablation: AP_S 34.3 to 35.8) and its README says nothing either way and its Hugging Face card lists only the COCO dataset tag, not the Objects365 pre-training named in the paper. Whether the dataset terms reach fine-tuned weights is a legal question I cannot settle; for record 0006 it is an open item for both top candidates, a little less for D-FINE's COCO-only checkpoint.

1. Which of D-FINE-S and RF-DETR-S gives the better per-image exact count after threshold tuning? Needs the dev split and a GPU; plan: one 200-image smoke test each (30 min), then 15-20 epochs at 1024 on the full 3,828 images, then score with the counting rules (hand to L3).
2. Does D4 augmentation remove the need for 4-view test-time rotation? (hypothesis in section 4).
3. Is the 12 GB card enough for RF-DETR-M at 1024 with `batch_size="auto"` and gradient checkpointing? Estimated yes for batch 2-4 (E), unmeasured.
4. Should wall/room detection share the model with symbols? Out of scope here (L4).
5. Pointers for other scopes: wall and opening vectorisation with heatmap read-out, 2608.25608 (L4/L11); AEC sheet-layout detector, 2607.18997 (L9); handwritten character localisation with RF-DETR, IJDAR 2026 (L5); Springer IJDAR 2024 construction-diagram symbol paper was not readable (L1/L12).
6. Missing tools: no GPU on this machine; no arXiv MCP (used arxiv.org/html through the headless fetch); Semantic Scholar rate-limited (OpenAlex substitute, shared free budget, no key created); Springer, a university repository page, HAL (bot check) and a PubPub page returned empty or blocked pages and were not circumvented; arXiv PDF URLs do not render in the headless fetch, but `curl` of the PDF plus `pypdf` reads them (found in round 14; the earlier abstract-only reads of PDF-only papers could be upgraded), and OpenAlex's free budget ran out in round 11 (resets 02:00 local).
