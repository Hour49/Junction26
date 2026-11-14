# lit-rooms (scope L4): room outlines and vector reconstruction, merged report

Merged 2026-11-14 from three reports (a: polygon predictors and measured numbers; b: code, weights, licences, leakage, cheap
routes; c: adjacent fields). Sources were opened by the three authors; entries marked "re-checked HH:MM" were opened
again by the merger on 2026-11-14 (01:21 to 01:24). "Read" = table or text read at the source, "claim" = the authors' own
statement, "search" = search summary only. Hour counts are estimates. "CC5K" = CubiCasa5K. Numbers about our own data come
only from tracked files: `docs/research/lit-campaign/worker-brief.md` (image sizes, 829 of 959 sealed eval drawings in the
CC5K train split, the "about one sheet in five has several plans" figure) and `docs/GOLDEN.md` (area tolerance 2%).

## 1. Answer

**Question:** the cheapest way to get room polygons good enough to (a) attach a label to a room and (b) give an area within
about 5%, with reported room IoU or area error on CubiCasa5K or R2V.

**(a) Labels.** A closed region plus the OCR box inside it is enough where walls close. Direct polygon predictors reach a room
F1 (IoU > 0.5) of 88.7 on CC5K in their own paper (Raster2Seq, arXiv 2602.09016 Table 1, re-checked 01:22), but an independent
rerun of the released checkpoint on the 400 official test plans under a stricter protocol gets 0.7626, and the CC5K authors' own
raster-then-polygon route gets 0.6305 (SALI-FP, arXiv 2609.25615 Table C.24, re-checked 01:22). A walls-only network read out as
a wall graph and taken as faces gets room F1 0.591 against 0.784 for Raster2Seq with a reconciliation step (fpvec-lab, arXiv
2608.25608 Table 2, "rooms" column, re-checked 01:23). So published CC5K room F1 differs by about 12 points between protocols:
compare routes only on one protocol, ours. The failure to plan for is two rooms merged: through an open doorway, and across a
wall that is not drawn (open plan). In a practitioner's log of the wall-graph route on clean vector sheets from one IFC model,
19 of the 48 first-floor misses were rooms merged with a neighbour, and every merged pair had no wall between them at all
(github.com/anchapin/matchline issue #740; one tracker, not peer reviewed). An OCR box used as a second seed is the cheap remedy
(Ahmed et al., DFKI 2012, abstract read; a mall-plan paper, Sensors 22(7):2510, reports 92.54% room segmentation accuracy on
1,340 rooms, claim).

**(b) Area within about 5%.** No polygon paper reports an area error. The one measurement is the PlanQ-CubiCasa benchmark: a
plain U-Net (512 px, 2,315 CC5K train plans) gives a **median** room-area error of 4.33% and a **mean** of 8.1% on 177 test plans
(`results/unet_on_177.json`, re-checked 01:22; code MIT; single author, not peer reviewed). Three seeds on 190 plans give medians
4.11, 5.09 and 5.21% and means 8.13 to 8.26% (`unet_seed_summary.json`, read by a). From its per-plan file (a's
calculation): 45% of plans exceed 5% error, 26% exceed 10%, 12% exceed 20%; 134 of 177 are under-estimated. The same scale is
used on both sides (`scripts/eval_unet.py`, read by a), so this is segmentation error only, on clean renders with the scale known.
Area goes with the square of the scale, so a +/-5% scale error is about +/-10% area (MDPI Appl. Sci. 16(13):6290, sensitivity
test, claim). Pixel counting on clean colour-coded renders gets MAPE 5.68% per room, 12.27% for rooms under 10 m2, and 1.58% per
plan (Periodica Polytechnica Civ. Eng. 70(3), read by all three reports). The repo's judge tolerance for areas is 2%
(`docs/GOLDEN.md:14,142,160`), so a polygon area is a fallback: a printed area or a dimension-line scale should win where
present. The wall convention (net internal area against centre-line area) can alone move a 10 m2 room by roughly 8 to 15% with
20 cm walls (c's arithmetic): fix it before measuring. Our own arithmetic for a 12 m wide plan at 855 px: a 1 px inward
boundary shift costs about 1.9% on a 3 m room and 3.7% on a 1.5 m closet (b).

**The route the evidence supports.** Train our own separator (wall) and room-region net on the dev polygons, close door gaps
with a non-learned step, take connected components of the complement, polygonise all rooms together, snap to the sheet's
dominant orientations. Three independent lines agree on its shape: (1) PolyTopoBench, an 11-method head-to-head on aerial
buildings, found "segment, then polygonise" (Mask R-CNN AP50 0.720, U-Net 0.670) ahead of every learned-vector method and left
direct vertex decoders near zero (Pix2Poly 0.102; arXiv 2609.32856 Table 3, read by a; aerial only); (2) the ICDAR 2021 map
competition winner trained a net on the non-block mask and took components (PQ 74.1; arXiv 2105.13265, re-checked 01:23);
(3) closed-region step in anime line art, comic panels and robot floor-plan maps is non-learned (trapped ball, distance
transform, watershed). Every public CC5K-trained checkpoint is unusable for scored runs (829 of 959 sealed eval drawings are in
the CC5K train split) and most weights are non-commercial, so what we ship is trained on our own dev data.

**What does not work:** zero-shot SAM family on line art (three adjacent fields measured it far below a fine-tuned model); VLMs
asked for rooms or areas (area MAPE about 43% for small open VLMs; area instance F1 0.08 to 0.23 for frontier models in a
vendor-run benchmark); CC5K-trained models off their style (room IoU 91 to 65 on real scans, walls 27.5, doors 1.5; arXiv
2504.03241). **No source reports a room polygon or area figure on scanned or photographed plans** except pixel mIoU in one
preprint (LGS-FPP, below). Our dev split can answer this by degrading plans and re-scoring (experiment 3).

## 2. Top 10 (ranked across the three reports; floor-plan work and transfers in one list)

**1. Own separator net, closed regions, components as rooms.** Wall (separator) mask plus room-region head trained on our dev
polygons, then connected components. Combines the PlanQ recipe, the ICDAR 2021 winner and MDPI's U-Net + components.
- Fills: `rooms` (outline, area with a scale), `plans` (blocks of ink as a first step).
- Numbers: PlanQ median 4.33% / mean 8.1% area error, room IoU 0.847, wall 0.801, window 0.742, door 0.656 on 190 test plans, U-Net
  trained on 2,315 CC5K plans (README, re-checked 01:22). ICDAR 2021 task 1: L3IRIS PQ 74.1, CMM 62.6, U-Net + watershed 6.4
  (merged neighbours are punished hard); L3IRIS trained a DenseNet-121 on 2 map images (arXiv 2105.13265, re-checked 01:23). MDPI:
  ResNet-34 U-Net, room IoU 96.2% on 10 validation plans of 101 own plans (claim). Wall net on CC5K cropped plans: IoU 0.81 mask /
  0.80 vector (arXiv 2306.01642 Table 1, validation split, inputs cropped to the wall extent; read by a). Chen 2024 (PLOS ONE,
  read by c): a 4M-parameter U-Net loses 2 PQ points against 17M.
- Licence: smp MIT (re-checked 01:22), timm ResNet/ConvNeXt/EfficientNet weights Apache-2.0 (cards read by b); our own weights.
  Avoid MiT/SegFormer encoders (NVIDIA research-only licence, LICENSE read by a and b), so MitUNet's code (MIT, re-checked 01:22)
  is usable but its mit_b4 weights are not.
- Leakage: none if trained on dev only. MitUNet shows CC5K pre-training adds under 1 mIoU on 500 in-domain plans (arXiv 2512.02413
  Table 3, read by a), so skipping it costs little.
- GPU and hours: 1.75 GB at batch 4, 512 px for MitUNet; ResNet U-Net 1.5 to 3.3 GB (b). 3 to 4 h to a first dev number (estimate).
- What breaks: walls of 1 to 4 px (do not downscale: F1 falls with resolution, IJGI 2025 read by c); hatched or dotted double-line
  walls; text and furniture draw false separators; open-plan rooms cannot be split by walls; PlanQ's 4.33% assumes a known scale
  and clean renders; the tail (a quarter of plans above 10%) matters more than the median; no scan or photo result exists.
  Heterogeneous real plans are harder: a ResNet U-Net on 2,601 customer plans reached wall IoU 0.574, door 0.450 on 196 held-out
  plans, and adding CC5K did not help (Lund thesis 2026:E4, claim); 100 mixed plans gave wall IoU 0.52 to 0.67 depending on loss
  (TUM, Tversky 0.638, log-cosh 0.670, read by b).
- Verdict: **try tonight.** Report matched-room area error as the share within 5, 10 and 25%, not one median.

**2. Door-gap closing, three non-learned variants on one protocol.** Needed because a plain component pass leaks (Chen 2021 on a
Paris map sheet: components F 0.27, watershed 0.59 at IoU 0.5, arXiv 2101.02144, read by a and c).
- (i) Trapped ball, radius about half the gap (hepesu/LineFiller, MIT, re-checked 01:22; Allen et al., SIGGRAPH Asia 2024 Tech.
  Comm., adds a distance field with seeds at its maxima and a neck-based merge, no code). Comic panels: unclosed-panel repair
  91.3% vs 74.1% panel rate on 104 pages (Pang 2014, read by c).
- (ii) Distance transform / Voronoi / down-sampling watershed (Bormann ICRA 2016: recall/precision 95 to 98 / 88 to 95% on 20 clean
  robot floor-plan maps, 76 to 87 / 87 to 95% furnished; Sharif 2023: 94.1 / 98.1% furnished; ROSE2 room IoU 73.3 vs 28.7 to 54.7 on
  10 cluttered maps, re-checked 01:23). Reimplement with scipy and skimage, about 40 lines (Bormann's code is LGPL for
  non-commercial use only; ROSE2 is GPL-3.0, idea only).
- (iii) Endpoint extension along the stroke direction, then seeded watershed (TopoFP, Remote Sensing 18(11):1783, MIT, re-checked
  01:22, parcels F1 0.83 to 0.92; neatnet `extend_lines` / `close_gaps`, BSD-3-Clause, re-checked 01:22, then shapely
  `polygonize`). Cabrera 2018 (MSc thesis): collinear endpoint linking left 12 to 30% of virtual walls to correct, mostly closets.
- A fourth idea, ProClosure's progressive thickening that freezes each region when it closes (arXiv 2609.12614), is not evidence:
  its gain came from door frames taken from the annotations, and the authors say a controlled sweep over closing radii is missing.
- Fills: `rooms`. Licence: all reimplementable under MIT/BSD. Leakage: none. Hours: 1 to 2 per variant on top of entry 1.
- What breaks: the radius must exceed a door and stay under a corridor; closets smaller than two ball radii vanish; corner-pair
  closing (two hobby repos) needs axis-aligned sheets, and a third of ours are rotated. The door-gap size on our sheets is
  unmeasured here: take the radius from a gap histogram of the dev split.
- Verdict: **try tonight**, all three, one mask, one scorer; report merge and split counts, not IoU alone (Sharif's point).

**3. Topology-aware training of the separator.** clDice (MIT, re-checked 01:22) or Skeleton Recall (Apache-2.0, re-checked
01:22), Tversky loss with recall above precision (MitUNet: alpha 0.6, beta 0.4), cut synthetic gaps into walls (TableBorderNet
SelfSynth, claim IoU 94.2%, topological error 1.07%), optional pre-training on `benikm91/synthetic-floorplans-for-transcription`
(CC BY 4.0, card re-checked 01:22; Manhattan only, 512 px, 6 px walls, no text or furniture, exact doors and rooms).
- Numbers: a topology loss lifted grain-region ARI from 0.72 to 0.78 (arXiv 2305.07790 Table 4, read by c); SAM 2 + Betti loss
  0.72% vs 4.44% error on IC lines (arXiv 2603.16548, 8 H100). Loss choice moved wall IoU by 15 points on 100 mixed plans (TUM, b).
- Fills: `rooms`. Leakage: none. Hours: about 1 on top of entry 1. What breaks: reduces broken walls, does not close a real door;
  the synthetic set is a different style (pre-training aid only).
- Verdict: **try tonight** as a loss switch and one ablation.

**4. Shared-boundary assembly, orientation snap and two checks.** Build rooms as faces of one arrangement (components of one
label image, polygonised together with shared vertices; shapely `polygonize`), Douglas-Peucker, then snap to the sheet's dominant
orientations. ACPV-Net's formulation gets gap rate, overlap and shared-edge consistency 0.00 / 0.00 / 100.00 on aerial Deventer-512
against 5.43 / 4.50 / 25.73 for HiSup (arXiv 2603.16616 Table 2, read by a and c); its code and checkpoint are CC BY-NC-SA 4.0, so
re-implement the step. ROSE2 shows the snap step is where room IoU rises from about 55 to 73 (Table I, re-checked 01:23). Add the
parcel paper's checks (arXiv 2609.07520): intrusion ratio and shared-edge recall. Polygonisation costs eight points of mean IoU
on CC5K, 57.5 to 49.3 in the CC5K paper's own Table 3 and 0.739 to 0.661 in SALI-FP, so tune the simplification tolerance on
area, not on looks. floor-plan-tracer (PolyForm Noncommercial, weights unreleased) reports 99.92 room-boundary F1 at 2 cm for the
plain mask-to-polygon step against 65.78 for its full chain: keep this step minimal.
- Fills: `rooms`, area. Licence: shapely BSD-3 (read by c). Leakage: none. Hours: 1 to 2 (estimate).
- What breaks: oblique or curved walls become staircases under an orthogonal snap; estimate the dominant direction per sheet first.
- Verdict: **try tonight** (cheap), measured on area.

**5. OCR box as the seed, and the label rule.** Attach a label to a room by the OCR box inside it; split an open-plan region
when it holds several labels. The matchline rule (`docs/room_labels.md`, read by c): reject dimension tags, regroup stacked lines,
centroid strictly inside a polygon wins, else the nearest edge within 150 px at 0.6 confidence, else report unmatched; validated
only on one drawn 10-room plan (9 of 9 associated, 7 of 9 exact) and no real-sheet accuracy.
- Fills: `rooms` raw label and type (the scope for the OCR itself is lit-ocr). Licence: rule, no code needed. Leakage: none.
- What breaks: stacked or rotated labels; two identical labels; a bedroom with no label counts as 0, so a type guess from layout
  can hurt exact counts (ResPlan: type from area and neighbours is 0.951 in one style but 0.19 to 0.65 across styles, arXiv
  2508.14006 Tables 2 and 4, read by a). Do not build a layout classifier.
- Verdict: **try Saturday** after entry 1 gives regions.

**6. fpvec-lab: scorer, generator and degradation ladder.** `fpeval` (wall, room and opening F1 over a tolerance sweep,
watertightness, edit cost), `fpgen` (procedural plans in four render styles with dimension chains and a scale bar that carry true
metric values; rotation up to 3 degrees, blur, noise, JPEG, photocopy ops, registration tested within 1.5 px), both MIT (README
re-checked 01:23: repo MIT, pushed 2026-10-21); `skv4` converter is non-commercial. Re-scoring a fixed checkpoint on corrected
annotations moves wall F1 0.74 to 0.825 (part of CC5K "error" is label noise). Its authors list perspective and real scans as out
of scope.
- Fills: confidence and proof, evaluation. Leakage: none for the tools. Hours: 1 to 2 (estimate; not run by anyone here).
- What breaks: wall-centred; rooms are faces of walls; CC5K layouts, not scans.
- Verdict: **try tonight** for the scorer and degraded test copies. Also use AEC-Geometric-Bench's rule of merging touching gold
  instances before scoring (vendor-run, licence "Other", read by c).

**7. Raster2Seq retrained on our dev polygons (pilot).** Autoregressive corner sequence from a 256 px raster; rooms, windows, doors
as typed polygons. Room F1 88.7, corner 59.4, angle 37.4, room-semantic 63.8, window+door 77.8 (Table 1, re-checked 01:22; CC5K cut
into 5,267 / 503 / 511 single-plan crops). Independent: 0.8854 on fpvec-lab's rebuild of the crop split; 0.7626 on 398 whole-sheet
plans (SALI-FP, re-checked 01:22). Zero-shot on WAFFLE web plans interior IoU 73.9 against 46.1 for the CC5K net (Table 6, read by a
and c). Cross-style: a CC5K-trained room-centric arm emits no room in 26.7% of clean ResPlan renders until fine-tuned in domain
(fpvec-lab Table 10, read by a and b).
- Licence: code MIT (re-checked 01:22); weights CC BY-NC 4.0 (LICENSE-CHECKPOINTS, re-checked 01:22). Leakage: **yes**, the
  `cubicasa5k` checkpoint is trained on CC5K train; unusable for scored runs.
- Cost: 19.4 h pretraining + 16 h semantic fine-tuning on one 48 GB A6000 for CC5K (Table 7) = about 35 h; 0.52 s per image. Our
  cards are 12 and 16 GB: more than a day, so a short pilot at most (estimate). Needs the CUDA deformable-attention build (CUDA
  11.8, torch 2.3.1; issue #2); SALI-FP reports CPU inference with the pure-PyTorch reference (not run here; a ROCm card would use
  that path). Issue #3: public training scripts do not match the released checkpoint's configuration. Issue #4: `room_iou` returns
  the last room only, so use our own scorer.
- What breaks: 256 px against our 855 px median; one plan per image assumed; no rotated training sheets; no area metric.
- Verdict: **try Saturday as a pilot**, only after entry 1 has a number to beat; keep our own symbol detector for `elements`.

**8. Frozen foundation features + LoRA head (few labels).** DINOv2 or RADIO encoder, LoRA, linear head: 689k trainable
parameters, 5 to 10 labelled tiles, PQ 67.3 on ICDAR 2021 building blocks against 74.1 for L3IRIS (arXiv 2506.21826 Table 5,
re-checked 01:23; code has no licence file). DINOv2 weights Apache-2.0 (card read by b); DINOv3 custom. No floor-plan result.
- Fills: `rooms`. Leakage: none. Hours: about 3 (estimate). What breaks: 14 to 16 px patches are coarse for thin walls, so upscale
  2 to 3 times; SAM encoders did worse than DINOv2/RADIO in the same paper.
- Verdict: **idea only** unless entry 1 underperforms; worth a try if few dev polygons turn out usable.

**9. Mask2Former / OneFormer fine-tuned on our room polygons.** Instance-aware rooms in one model. FloorPlanFormer (AAAI-26)
found a plain Mask2Former within 0.004 mIoU of its new architecture on 8,200 clean plans (0.915 vs 0.919; Table 1, read by a and
b; its repo has no licence, no weights). No published CC5K number; the only public Mask2Former CC5K checkpoint reports wall
instance AP 0.263 and is a leaked repackage. Code MIT (re-checked 01:22, pushed 2024-07-29, needs Detectron2); weight cards say
"other", so treat shipped weights as unverified. Hours 4 to 8 (estimate).
- Verdict: **try Saturday** only if the semantic mask in entry 1 merges neighbouring rooms.

**10. SAM 2 fine-tuned, or SAM 3 with a text prompt (a measurement, not a route).** Pretrained SAM 2 prompted from a detector
gets 10.49 mIoU on a scanned proprietary set, 30.72 with four negative points, 69.58 after fine-tuning; plain SegFormer-B5 gets
65.07 (LGS-FPP, Research Square rs-9512825, CC BY 4.0, not peer reviewed, code unreleased; read by a and b). SAM 3 has no plan
result (arXiv 2511.16719). Adjacent: SAM2 0.382 mAP50 vs 0.720 fine-tuned on field parcels, 0.33 to 0.63 vs 0.977 on manga panels,
SAM2 boxes 0.431 vs 0.720 on aerial buildings. SAM and SAM 2 code Apache-2.0 (read by b); SAM 3 under a custom SAM License
(royalty-free, trade-control and patent clauses, not OSI; read by a).
- Fills: `rooms`. Leakage: none. Hours: about 1 for 20 plans. What breaks: SAM 2 runs at 1024 px and our median is 855 px; walls
  are sub-patch.
- Verdict: **idea only** except for the one-hour 20-plan measurement.

## 3. Full table

"from" = which report assessed it (a, b, c). "Level" = R read in the source, C authors' claim only, S search summary only.
"Field" = our field, or the field it transfers from. CC5K column: whether CubiCasa5K is in the training data.

| Method / source | Field | from | Level | Key number (dataset) | Code / weights licence | CC5K | Verdict |
|---|---|---|---|---|---|---|---|
| Own separator net + components (entry 1) | ours | a b c | R | PlanQ median 4.33% / mean 8.1% area error | smp MIT / own | no | try tonight |
| PlanQ-CubiCasa recipe | ours | a | R | room IoU 0.847, 177 plans | MIT / labels CC BY-NC | yes | evidence |
| Wall net 2306.01642 | ours | a b c | R | wall IoU 0.81 mask / 0.80 vector (val, cropped) | none found | yes | idea |
| MitUNet 2512.02413 | ours (walls) | a b c | R | wall mIoU 87.91 own 500 plans; 88.75 CC5K-pretrained | MIT / mit_b4 NVIDIA non-commercial | pretrained on it | idea (use ResNet encoder) |
| FGSSNet 2507.10343 | ours (walls) | b c | R | wall IoU 77 to 78% CC5K test | none found | yes | bar for wall mask |
| MDPI Appl. Sci. 16(13):6290 | ours | b | R | room IoU 96.2%, 10 val plans | not stated | CC5K fine-tune 82.4 mIoU | recipe |
| Lund thesis 2026:E4 | ours | b | R (part) | wall IoU 0.574, door 0.450, 196 plans | none | no | evidence |
| TUM heterogeneous plans | ours | b | R | wall IoU 0.52 to 0.67, 100 plans | none | no | evidence |
| Kratochvila multi-unit 2408.01526 | ours | c | R | pixel F1 0.86, IoU 0.76 on CC5K | Apache-2.0 | yes | maybe (post-processing code) |
| CubiCasa5K net 1904.01920 | ours | a b c | R | room mIoU 57.5, 49.3 polygonised | CC BY-NC | yes | baseline, local only |
| Deep Floor Plan 1908.11025; Offset-Guided 2210.17411 | ours | a b | R | pixel accuracy 0.89 / 0.93 on R2V | GPL-3.0 / none | R2V | skip |
| Raster-to-Vector (ICCV 2017) | ours | b | R | room 84.5 / 88.4 at IoU > 0.7, 770 train | MIT, rasters not shared | no | skip (Manhattan, solver) |
| Raster2Seq 2602.09016 | ours | a b c | R | room F1 88.7 own; 0.7626 independent | MIT / CC BY-NC 4.0 | yes (ckpt) | pilot Saturday |
| RoomFormer | density maps | a b c | R | room F1 83.5 (via Raster2Seq) | MIT / weights terms unstated | yes (adapted) | skip |
| HEAT, FRI-Net, PolyRoom | density maps | a b c | R | room F1 78.2 / 77.1 / 54.1 (via Raster2Seq) | non-commercial; none; none | adapted | skip |
| PolyDiffuse, CAGE, Raster-to-Graph | density maps / own | a b c | R | n/a | GPL-3.0; not checked; GPL-3.0 | n/a | skip |
| FloorplanVLM 2602.06507 | ours (VLM) | a b c | R | room IoU 0.892 own set, 32 H200 | none found | no | skip |
| Community VLM adapters (HF) | ours (VLM) | a b c | R (cards) | none | tagged Apache-2.0, card says non-commercial | yes | skip |
| SALI-FP 2609.25615 | ours | a b c | R | room F1 0.445 own GPT route; reruns 0.7626 / 0.6305 | closed | n/a | use its reruns |
| fpvec-lab 2608.25608 | ours | a b c | R | faces room F1 0.591 vs 0.784 | MIT (skv4 NC) | yes | scorer, generator |
| LGS-FPP (SAM 2 fine-tuned) | ours | a b | R | CFP scans mIoU 69.58 vs 65.07 SegFormer | unreleased / CC BY 4.0 paper | partly | evidence |
| FloorPlanFormer / FloorPlan8K | ours | a b | R | mIoU 0.919 vs Mask2Former 0.915 | no licence | no | evidence |
| Zernike RAG + GNN 2504.03241 | ours | a b c | R | room IoU 64.6 on 122 CVC-FP scans; 93.3 rotated CC5K | none found | yes | evidence |
| WAFFLE 2412.00955 | ours | a b | R | CC5K net interior IoU 0.461, doors 0.099 | Commons terms | n/a | non-CC5K test set |
| ResPlan 2508.14006 / ModRes | ours | a b | R | type from graph 0.951 in style, 0.19 to 0.65 across | data CC BY 4.0, code MIT | no | pretraining data |
| Floor Plan CIS (Zenodo) | ours | b | R | 500 wall-mask plans | CC BY 4.0 | no | wall data |
| CVC-FP | ours | a b c | C | 122 scans with rooms | CC BY-NC 4.0 (search) | no | local scan test bed |
| Ahmed ICDAR 2011 (classical) | ours | b | R | det. 89%, acc. 79%, 80 scans | none | no | fallback |
| Ahmed DFKI 2012 | ours | c | R (abstract) | no numbers | none | no | idea (label split) |
| matchline #740 and room_labels | ours | c | R | 70% rooms matched raw, 83% wall-bounded, area err ~11% | BSD-3-Clause repo | no | evidence |
| Lv et al. CVPR 2021 | ours | b | R | pixel acc. 0.96 on 5,600 homogeneous plans; doorways 0.67 | none | no | recipe (door 0.9 m scale) |
| Liang et al. EC3 2026 (dimension grid) | ours (scale) | b c | R | strict OCR 90.2%; 71.1% strict geometric; 62 of 200 plans right | none found | OCR on CC5K | for lit-scale |
| floor-plan-tracer | ours | a | R | boundary F1 82.9 at 5 cm, 64 floors | PolyForm Noncommercial, no weights | no | design only |
| ProClosure 2609.12614 | video maps | a | R | room F1 0.890 vs 0.741 | file named "LICENSE .md" | no | idea, untested |
| Vector PDFs: VectorGraphNET, layer reading | ours | a | R | room-contour line F1 0.90 | unverified | no | maybe, vector PDFs |
| Chen 2021 / 2024 boundary + watershed; ICDAR21 L3IRIS | historical maps | a c | R | PQ 74.1 / 46.7 to 51.1 | none | no | try (entry 1) |
| Sterzinger ICDAR 2025 | historical maps | c | R | PQ 67.3, 5 to 10 tiles | none | no | idea |
| LineFiller trapped ball; Allen 2024; Pang 2014 | anime / comics | c | R | panel rate 91.3% | MIT; none; none | no | try |
| Bormann 2016, Sharif 2023, ROSE2, ReasonNavi | robot maps | a b c | R | see entry 2 | LGPL-NC; none; GPL-3.0; n/a | no | try (reimplement) |
| TopoFP, neatnet | parcels, street networks | c | R | F1 0.83 to 0.92 | MIT; BSD-3-Clause | no | try |
| clDice, Skeleton Recall, Betti loss | vessels, ICs | c | R | ARI 0.72 to 0.78 | MIT; Apache-2.0 | no | try |
| TableBorderNet, SEMv3, Camelot, TSRFormer | tables | a c | R / S | IoU 94.2% (claim); WTW F1 95.1 | none; Apache-2.0; MIT; n/a | no | idea |
| ACPV-Net, parcel paper 2609.07520 | land cover, parcels | a c | R | gap 0.00 vs 5.43 | CC BY-NC-SA 4.0; no code | no | idea, two checks |
| Frame Field Learning, HiSup, Pix2Poly, P2PFormer | aerial | a c | R | AP 64.5 to 79.4; INRIA IoU 75.87 | BSD-3; MIT; MIT; Apache-2.0 | no | maybe, polygoniser |
| PolyWorld, PolyR-CNN, UniVector, Delineate Anything, HoliTracer | aerial | a c | R | n/a | research only; CC BY-NC-SA; IDEA 1.0; AGPL-3.0; MIT but 4 A100 | no | skip |
| Mask2Former / OneFormer | general | a b c | R | none on plans | MIT / cards "other" | no | try Saturday |
| SAM 2, SAM 3 | general | a b c | R | 10.49 mIoU pretrained | Apache-2.0; SAM License | no | measure only |
| Cellpose-SAM, StarDist | cells | c | R | not for rooms | BSD-3 (README GPL badge) / CC-BY-NC | no | skip |
| RNGDet++, VectorMapNet, MapTR, Sat2Graph | roads, HD maps | a c | R | mAP +14 over raster (claim) | GPL-3.0; none; MIT; MIT | no | idea |
| ScaleLSD, DeepLSD | line segments | c | R (README) | zero-shot only | MIT; MIT | no | maybe, wall lines |
| Sasaki 2017 gap inpainting | line drawings | c | S | n/a | no licence file | no | skip |
| AECV-Bench 2601.04819 | AEC VLMs | a b | R | door count 0.16 to 0.39, bedroom 0.89 to 0.91 | no licence field | partly | baseline for counts |
| AEC-Geometric-Bench | AEC VLMs, vendor | c | R | area instance F1 0.08 to 0.23 | "Other" | n/a | context |
| PPCI VLM area study | ours | a b c | R | VLM MAPE ~43% vs pixel count 5.68% | n/a | ResPlan | evidence for (b) |
| Handoff-H1 | AEC, vendor | b | R | humans differ ~10% re-measuring | harness public | n/a | context |
| MSD, SFS-A68, MLSTRUCT-FP, FloorSAM, HouseMind | datasets, point clouds | a b c | S / R | n/a | CC BY 4.0 (source); GPL-3.0; MIT; not released; n/a | no | skip |

## 4. Transfers from other fields

| Field | What plays the role of a room | Why it transfers | What breaks | Code |
|---|---|---|---|---|
| Historical map blocks (ICDAR 2021, Chen) | block bounded by streets | separator net + components, measured PQ 74.1 | merges are fatal; maps have no door gaps | idea only (no licence files); MitUNet code as base |
| Anime line art (trapped ball) | colour region bounded by lines | a ball larger than a gap does not leak | door-sized necks must stay; closets vanish | usable as is (LineFiller MIT, no training) |
| Comic panels | panel closed by frame lines | repair an open frame, then split; U-Net with a border class (DeepPanel, Apache-2.0) | white gutters, axis-aligned | idea (Kumiko licence "Other") |
| Robot occupancy maps | room between walls with door gaps | distance transform and Voronoi find narrow passages without a door detector | clutter drops IoU to 29 to 55 without a dominant-direction step | reimplement (LGPL-NC, GPL) |
| Field parcels (TopoFP, ACPV, parcel paper) | parcel sharing boundaries | endpoint extension + seeded watershed; shared edges; intrusion and shared-edge metrics | aerial input, learned vertex heads | TopoFP MIT usable as idea; ACPV idea only |
| Street networks (neatnet) | line ends with gaps | `extend_lines`, `close_gaps` on shapely | needs centre-lines first | usable as is on centre-lines |
| Building footprints (HiSup, FFL, Pix2Poly) | building | polygonise a mask; BSD/MIT code | one polygon per object, weights aerial | needs retraining; polygoniser only |
| Table cells | cell closed by ruling lines | separator prediction + merge (SEMv3), morphological closing (Camelot) | walls not a grid, a third of sheets rotated | idea only |
| Cell membranes, grain boundaries, vessels | cell bounded by thin boundaries | topology losses, gap-closing nets | no door concept | clDice, Skeleton Recall usable |
| Road and lane graphs | open polylines | topology repair argument; permutation-equivalent points | open graphs, GPL code | idea only |
| Hand-drawn / marketing renders (ResPlan, synthetic sets) | rendered plan with exact labels | free labels, scale known | style gap | data CC BY 4.0 usable |

## 5. Disagreements resolved at the source

- **Raster2Seq room F1:** 88.7 (own paper), 0.8854 (fpvec-lab rebuild of the crop split), 0.7626 (SALI-FP, whole sheets, 100 px area
  cut-off, failed predictions as zero). Tables re-opened 01:22 for 88.7 and 0.7626; the difference is protocol, so all three hold
  for their own protocol.
- **Raster2Seq training cost:** an earlier "5 to 21 h" was wrong; Table 7 gives 19.4 h + 16 h on one A6000 (a, b, c agree after the
  fix). Report c's first note said "1 to 2 days"; 35 h holds.
- **Raster2Seq on CPU:** a said CUDA ops are needed; b and c cite SALI-FP's CPU run with the PyTorch reference. Holds: the README
  documents a CUDA build, SALI-FP reports CPU inference; nobody here ran it. Completion count: the 395 of 400 that appears in the
  SALI-FP accuracy-cost table belongs to the CC5K net's polygon decoder (a's round 59); Raster2Seq's native evaluation is 400 of 400
  (not re-opened).
- **MitUNet licence:** c called it licence-clean; the repo is MIT (re-checked 01:22) but the mit_b4 encoder is SegFormer under the
  NVIDIA research-only licence (a read LICENSE lines 38-39; b read section 3.3). b holds: use a ResNet or ConvNeXt encoder.
- **AECV-Bench counting:** a quoted "door and window counting often 0.40 to 0.55"; b read Table 1 (Gemini 3 Pro door 0.39, window
  0.34; GPT-5.2 0.28 / 0.27; Claude Opus 4.5 0.16 / 0.16; bedroom 0.89 to 0.91). b holds.
- **VLM area error:** "two sources agree VLMs lose" was too strong; the PPCI VLMs were small 2024-era open models (LLaVA-LLaMA 3,
  MiniCPM-V 2.6, BakLLaVA) on colour-coded renders. The frontier-VLM datapoint is fpvec-lab: Gemini 3.1 Pro wall F1 0.811 at
  tolerance 0.05 but 0.472 at 0.015. Both say coordinates are the weak side.
- **Frame Field Learning:** shares walls between adjoining polygons of one class (its paper) but overlaps 29.17% across classes
  in another group's multi-class run (ACPV-Net Table 2): keep all room types as one class.
- **ProClosure:** a and c first presented its per-region closing as a result; a re-read (Sec 5.4, round 71) shows the mIoU gain came
  from annotation door frames and no closing-radius sweep was run. Idea only.
- **PlanQ "within 5%":** median 4.33% holds for one model, 4.11 to 5.21% over three seeds, mean 8.1 to 8.3%. "Within 5%" is true for
  the median at best (re-checked 01:22 for 4.33 and 8.1).
- **Door-gap size:** a and c assumed 10 to 30 px on an 855 px image; c later eyeballed larger gaps from sample sheets. Not
  supported by a tracked file, so unmeasured: take it from a gap histogram of the dev split.
- **SAM licence:** SAM and SAM 2 Apache-2.0 (b read the LICENSE files); SAM 3 custom SAM License, no non-commercial clause in the
  lines a read, not on the allowed list.
- **Hugging Face licence tags:** a tag is not the licence of the training data (an Apache-2.0 tag on a CC5K-trained VLM adapter whose
  card says non-commercial; an MIT tag on a CC5K UNet). a and b agree; treat any CC5K-derived checkpoint as local only and leaked.

## 6. Negative results

- Zero-shot SAM / SAM 2 on line structures: 10.49 mIoU on scanned plans (LGS-FPP), field parcels 0.382 vs 0.720, manga panels 0.33
  to 0.63 vs 0.977, historical-map roads and rivers missed, SAM issue #541 on thin lines unanswered.
- CC5K-trained models off style: room IoU 91 to 65 on real scans, wall 27.5, door 1.5 (arXiv 2504.03241); interior IoU 46.1 on WAFFLE
  web plans; R2V recall 4.5% on thin-wall high-resolution blueprints (ACCV 2022, region F1 85.3 for the authors' own model);
  26.7% hard failures for a CC5K-trained room model on clean ResPlan renders until fine-tuned; the Hugging Face 0.983 mIoU of a CC5K
  UNet is on SVG renders of its own validation split.
- Frontier VLMs and image-generation redraws: SALI-FP's GPT route room F1 0.445 against 0.763; mIoU 0.207 raw; coordinates too coarse
  for area.
- Wall-graph faces lose 19 room-F1 points against direct emission when a trained room model exists (0.591 vs 0.784), and
  rule-based closing plateaued at 70% of rooms matched raw on clean vector sheets (matchline #740). Its rejected extras: folding
  short parallel walls, carrying every free wall end 10 m, directional joins.
- A learned end-to-end watershed did worse than the classical one (Chen 2024). Direct vertex decoders (Pix2Poly, PolyWorld, RoIPoly)
  collapsed on 512 px aerial crops (PolyTopoBench; recipe effects possible).
- Raster2Seq's public Structured3D scripts do not reproduce the released checkpoint (issue #3); `room_iou` is wrong in both
  Raster2Seq (#4) and RoomFormer (#24).
- CC5K labels overlap, are noisy, and some PNG / SVG pairs are misaligned (issue #20), so any area error scored on CC5K polygons has
  label noise in its target.

## 7. Looked for and did not find; unverified leads; open questions

**Looked for and not found:** a room IoU or area error on scanned or photographed plans (arXiv, OpenReview, CVF listings
CVPR 2024 to 2026, ICCV 2023 and 2025, WACV 2024 to 2026, GitHub, Hugging Face); a percent area error of any route from a raster
plan (arXiv API query returned 0 hits); zero-shot SAM, SAM 2 or SAM 3 automatic masks on plans; Mask2Former or OneFormer PQ on CC5K
or a usable public checkpoint; a controlled comparison of trapped ball, morphological closing and learned closing on wall-like line
art; ICDAR or GREC 2025 and 2026 floor-plan room papers; a 2025 to 2026 closed-shape competition after ICDAR 2021; plan-specific
perspective rectification; peer-reviewed numbers for the wall-thickness area convention; a learning curve of wall segmentation
against number of labelled plans; code for FloorplanVLM, LGS-FPP, FloorSAM, GLSP, MuraNet, the parcel paper; an open maintained
classical room tool under a permissive licence.

**Unverified leads (kept out of the ranking):** Liang, Fukuda, Yabuki, Autom. Constr. 2026 (DOI 10.1016/j.autcon.2026.107204; the
conference version was read by b and c, the journal page returned a captcha); CVC-FP licence and image type (two search results say
CC BY-NC 4.0); SIM 2.0 (SIGSPATIAL 2026, bot-check page, not bypassed); "Why floor plan object detection breaks under real scans"
(Autom. Constr. 2026; abstract read, paired CC5K clean/scan data on Zenodo 18890484, non-commercial); Zhang and Zhang, CIB 2025 (SAM
with similarity-map prompts from five reference plans, abstract only); FloorCaps, FVCap, FPP-Former, the 2025 survey of floor plan
recognition; DoorDet data (not released); UniVector, PolyTopoBench and the parcel-paper code licences; Raster-to-Graph numbers
beyond those quoted in Raster2Seq; LGS-FPP's claim of code "upon acceptance".

**Open questions:** (1) does the 4.33% median hold with an estimated scale and on scans; (2) how many dev plans have printed room
areas or dimension strings (scope lit-scale); (3) are closets and cabinets rooms in the gold, and which wall convention does it use
(`docs/GOLDEN.md`); (4) how many dev sheets are open plan; (5) the fraction of dev images that need plan splitting first (the brief
says about one in five); (6) whether Raster2Seq's CPU path runs without code edits.

## 8. Experiments proposed (at most five)

1. Train a smp U-Net (ResNet-34 or ConvNeXt-S encoder, Tversky + clDice, tile at native pixels) on the dev polygons, take components
   with a closing radius from the dev gap histogram, and score matched-room area error (share within 5, 10, 25%, mean and median)
   and room F1 at IoU 0.5 against PlanQ's 4.33% / 8.1% and SALI-FP's 0.63 / 0.76 on one protocol.
2. On the same mask compare four closers (radius sweep, trapped ball, EDT-watershed, endpoint extension + watershed): the one with the
   fewest merged and split rooms per 100 plans wins; a radius sweep that ties it ends the search.
3. Degrade the dev plans (downscale to 855 and 480 px, JPEG, blur, 3 degree and 90 / 180 degree rotation, fpgen photocopy ops) and
   re-score experiment 1: a drop of more than 15 points in the share within 10% means style augmentation first.
4. Run SAM 2 automatic masks and SAM 3 with the prompt "room" on 20 dev plans against the trained net: if neither reaches the net's
   matched-room IoU, SAM is closed as a route.
5. Seed the region split with the OCR boxes on the open-plan dev sheets and count merged rooms before and after: the drop in merges
   settles whether the text seed is worth building.
