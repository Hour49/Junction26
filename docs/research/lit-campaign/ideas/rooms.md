# Rooms: outlines and types

25 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i236"></a>
### 236. Link a read label to a room by point in polygon as the baseline

- What: Assign each read label to the room polygon that contains its box centre; use this as the baseline before any learned linking.
- Evidence (floor-plans): A learned object-to-text correspondence model reached F1 82.6 on its own plans but needs paired training data (ISPRS 2025).
- Source: [doi.org](https://doi.org/10.5194/isprs-archives-XLVIII-G-2025-597-2025)
- Licence: paper CC BY 4.0. CubiCasa5K leakage: unknown.
- Cost: 1 h work (estimate)
- Experiment: Measure linking accuracy on dev images where label and polygon are both known.
- What breaks on our images: Labels placed outside or across rooms; two labels in one room.
- Moves: room-types. Why this group: baseline needed by every other item
- Also (rooms, search-only): Label-to-room association rule. Centroid inside polygon wins, else nearest edge within 150 px at 0.6 confidence, else unmatched; reject dimension tags; regroup stacked lines. Evidence: matchline: 9 of 9 associated on one drawn 10-room plan, no real-sheet accuracy. Source: [github.com](https://github.com/anchapin/matchline). Experiment: Association accuracy on 50 hand-checked dev rooms.
- Reports: lit-ocr-a, lit-rooms-c

<a id="i237"></a>
### 237. Keep mask-to-polygon conversion minimal

- What: Measure plain conversion against ground-truth masks first; add rules only if they pay.
- Evidence (floor-plans): floor-plan-tracer: room-boundary F1 99.92 for plain conversion on GT masks against 65.78 for the full chain.
- Source: [github.com](https://github.com/yapicialiekrem/floor-plan-tracer)
- Licence: PolyForm Noncommercial (design only). CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Convert dev GT masks and score.
- What breaks on our images: none
- Moves: scale-areas. Why this group: bounds the loss of the step
- Reports: lit-rooms-a

<a id="i238"></a>
### 238. Own wall and room-region net, connected components as rooms

- What: Train a U-Net (ResNet or ConvNeXt encoder) on dev room polygons to predict walls and room regions, then take connected components of the complement as rooms.
- Evidence (floor-plans): PlanQ-CubiCasa: U-Net, 512 px, 2,315 CubiCasa5K train plans, median room-area error 4.33% and mean 8.1% on 177 test plans, room IoU 0.847 on 190 (README and results json); ICDAR 2021 map winner PQ 74.1 with the same idea.
- Source: [github.com](https://github.com/SoftHeart1314/planq-cubicasa-benchmark), [arXiv 2105.13265](https://arxiv.org/abs/2105.13265)
- Licence: smp MIT, timm Apache-2.0 encoders, own weights. CubiCasa5K leakage: no.
- Cost: 4 h work, 2 to 3 GPU-h on 12 GB (estimate)
- Experiment: Train on dev only, score matched-room area error as the share within 5, 10 and 25 percent plus room F1 at IoU 0.5 on held-out dev plans; beat 4.33% median and 8.1% mean.
- What breaks on our images: Walls of 1 to 4 px, hatched or dotted walls, text and furniture as false separators, open-plan rooms; PlanQ assumes known scale and clean renders; a quarter of its plans exceed 10% error.
- Moves: scale-areas. Why this group: only family with a measured area error and clean licences
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i239"></a>
### 239. Topology loss on the wall head

- What: Add clDice or Skeleton Recall and a Tversky loss with recall above precision to the separator net.
- Evidence (adjacent-field): Topology loss lifted grain-region ARI 0.72 to 0.78; SAM 2 plus Betti loss 0.72% against 4.44% error on IC lines; loss choice moved wall IoU 15 points on 100 mixed plans.
- Source: [arXiv 2003.07311](https://arxiv.org/abs/2003.07311), [arXiv 2305.07790](https://arxiv.org/abs/2305.07790)
- Licence: clDice MIT, Skeleton Recall Apache-2.0. CubiCasa5K leakage: no.
- Cost: 1 h on top of the net
- Experiment: Ablate loss on dev: broken-wall count and merged rooms.
- What breaks on our images: Reduces broken walls, does not close real doors.
- Moves: scale-areas. Why this group: cheap switch
- Also (vector, adjacent-field): Topology-preserving losses for a thin wall-mask network. Add clDice or Skeleton Recall Loss to a wall-mask network so thin walls stay connected before a gap rule counts openings. Evidence: SEMIR (2606.24935): Dice .894 power lines, .911 cracks vs best published .889 and .909. Losses clDice MIT, Skeleton Recall Apache-2.0. Source: [arXiv 2606.24935](https://arxiv.org/abs/2606.24935). Experiment: Train a wall-mask net with and without the loss on dev walls; compare connectivity and opening-gap counts.
- Reports: lit-rooms-b, lit-rooms-c, lit-vector-c

<a id="i240"></a>
### 240. Distance-transform, Voronoi or down-sampling watershed room splitting

- What: Split the free space at narrow passages with a distance transform and seeded watershed, no door detector or radius needed.
- Evidence (adjacent-field): Bormann 2016: recall and precision 95 to 98 and 88 to 95% on 20 clean robot floor-plan maps, 76 to 87 and 87 to 95% furnished; Sharif 2023 94.1 and 98.1% furnished; ROSE2 room IoU 73.3 against 28.7 to 54.7 on 10 cluttered maps.
- Source: [arXiv 2303.13798](https://arxiv.org/abs/2303.13798), [arXiv 2203.03519](https://arxiv.org/abs/2203.03519)
- Licence: reimplement (Bormann code LGPL non-commercial, ROSE2 GPL-3.0). CubiCasa5K leakage: no.
- Cost: 1 to 2 h
- Experiment: Run on the dev wall mask next to the other closers, count merges and splits.
- What breaks on our images: Over-splits corridors, leaks across wide openings; robot maps not drawings.
- Moves: scale-areas. Why this group: needs no door detector
- Also (rooms, adjacent-field): Trapped-ball fill to close door gaps. Run trapped-ball fill on the wall mask with radius about half the door gap, then merge small fragments. Evidence: Anime line-art closer, no training; comic panels unclosed-panel repair gives 91.3% against 74.1% panel rate on 104 pages (Pang 2014); no floor-plan number. Source: [github.com](https://github.com/hepesu/LineFiller). Experiment: Compare against a closing-radius sweep on the same mask: merged and split rooms per 100 dev plans.
- Also (rooms, adjacent-field): Extend wall ends along their direction, then seeded watershed. Skeletonise the wall mask, extend each dangling end to the nearest wall (neatnet extend_lines and close_gaps), then polygonize or seed a watershed. Evidence: TopoFP parcels F1 0.83 to 0.92 over three sites; Cabrera 2018 collinear linking leaves 12 to 30% of virtual walls to correct. Source: [mdpi.com](https://www.mdpi.com/2072-4292/18/11/1783), [github.com](https://github.com/uscuni/neatnet). Experiment: Fourth closer in the same comparison; centre-line quality on hatched walls decides.
- Also (rooms, search-only): Plain morphological closing radius sweep as the baseline closer. Sweep one closing radius on the wall mask and keep it as the baseline every other closer must beat. Evidence: No controlled comparison of trapped ball, morphological and learned closing exists; ProClosure authors name it as missing. Source: [arXiv 2609.12614](https://arxiv.org/abs/2609.12614). Experiment: Merged and split rooms per 100 dev plans against each other closer.
- Also (vector, adjacent-field): Watershed on an edge map to close wall gaps for rooms. Use an edge filter then watershed so a missing pixel on a boundary does not merge two regions. Evidence: Historical maps (PLOS ONE 2024): PQ 46.7 U-Net with better training vs 18.3 earlier; naive connected components 41.2 vs 8.1; scan shift costs about 13 PQ. Source: [doi.org](https://doi.org/10.1371/journal.pone.0298217). Experiment: Compare room regions from connected components vs watershed on dev wall masks.
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c, lit-vector-a, lit-vector-c

<a id="i241"></a>
### 241. Polygonise all rooms together from one label image

- What: Build rooms as faces of one arrangement so neighbours share walls, using shapely polygonize.
- Evidence (adjacent-field): ACPV-Net gap 0.00 and overlap 0.00 against 5.43 and 4.50 for HiSup on aerial Deventer-512; CubiCasa5K polygonisation costs about 8 mIoU points.
- Source: [arXiv 2603.16616](https://arxiv.org/abs/2603.16616)
- Licence: ACPV code CC BY-NC-SA (idea only); shapely BSD-3. CubiCasa5K leakage: no.
- Cost: 1 to 2 h
- Experiment: Area error with simplification tolerance tuned on area, not looks.
- What breaks on our images: Aerial source.
- Moves: scale-areas. Why this group: double-counted wall area is an error source
- Reports: lit-rooms-a, lit-rooms-c

<a id="i242"></a>
### 242. Set closing radius from a dev gap histogram

- What: Measure wall interruptions at doors on dev plans and pick the radius.
- Evidence (our-idea): Earlier 10 to 30 px assumption not supported by a tracked file.
- Source: [github.com](https://github.com/hepesu/LineFiller)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Histogram of door-box widths from dev labels.
- What breaks on our images: none
- Moves: scale-areas. Why this group: removes a guess
- Reports: lit-rooms-a, lit-rooms-c

## Try next

<a id="i243"></a>
### 243. Mask2Former on room polygons

- What: Instance-aware rooms from one model.
- Evidence (floor-plans): FloorPlanFormer: Mask2Former 0.915 mIoU within 0.004 of the new model on 8,200 clean plans.
- Source: [ojs.aaai.org](https://ojs.aaai.org/index.php/AAAI/article/download/37625/41587)
- Licence: code MIT, weight cards other. CubiCasa5K leakage: no.
- Cost: 4 to 8 h
- Experiment: If the semantic mask merges neighbours.
- What breaks on our images: Needs Detectron2; thin walls poor as instances (AP 0.263).
- Moves: scale-areas. Why this group: fallback for merges
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i244"></a>
### 244. Snap polygons to the sheet's dominant wall directions

- What: Douglas-Peucker then snap edges to the two dominant orientations estimated per sheet.
- Evidence (adjacent-field): ROSE2: room IoU rises from about 55 to 73 with the direction step.
- Source: [arXiv 2203.03519](https://arxiv.org/abs/2203.03519)
- Licence: idea only (GPL). CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Area error with and without snap on dev.
- What breaks on our images: Oblique or curved walls become staircases; rotated sheets need estimation first.
- Moves: scale-areas. Why this group: cheap regulariser
- Reports: lit-rooms-a, lit-rooms-c

<a id="i245"></a>
### 245. Use OCR boxes as seeds to split open-plan regions

- What: Seed the region split with OCR label boxes so a region holding several labels is divided.
- Evidence (authors-claim): DFKI 2012 abstract; mall-plan paper 92.54% room segmentation accuracy on 1,340 rooms (claim); matchline: merged rooms across absent walls were 19 of 48 misses.
- Source: [av.dfki.de](https://av.dfki.de/publications/automatic-room-detection-and-room-labeling-from-architectural-floor-plans/)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: half a day
- Experiment: Count merged rooms before and after on open-plan dev sheets.
- What breaks on our images: Stacked or rotated labels; identical labels.
- Moves: room-types. Why this group: walls cannot split open plans
- Reports: lit-rooms-b, lit-rooms-c

<a id="i246"></a>
### 246. Cut synthetic gaps into wall masks

- What: Erase wall runs near openings in training masks so the net learns to bridge gaps.
- Evidence (authors-claim): TableBorderNet SelfSynth IoU 94.2% and topological error 1.07% (authors).
- Source: [mdpi.com](https://www.mdpi.com/1424-8220/25/13/3899)
- Licence: no code seen. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Ablate on dev merges.
- What breaks on our images: Different domain.
- Moves: scale-areas. Why this group: free labels for gaps
- Reports: lit-rooms-c

<a id="i247"></a>
### 247. Room types as detector classes, compared with the text route

- What: Add bedroom, kitchen, bath, WC, balcony and sauna boxes as detector classes and compare with the text route per room type, upright and rotated separately; the two can vote.
- Evidence (our-idea): Our design, no paper; the dev export has room boxes and labels. A closed-class alternative to character decoding: digit-per-class detector 94.90 vs CRNN 86.85 on meters (arXiv 2009.10181).
- Source: [arXiv 2009.10181](https://arxiv.org/abs/2009.10181)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 agent hours plus one more GPU run (estimate)
- Experiment: Same dev slice, per room type, exact match for text route vs detector classes vs both voting.
- What breaks on our images: Meter paper is digits in one fixed window; our boxes may not mark where the label is.
- Moves: room-types. Why this group: decides how room type is filled
- Reports: lit-ocr-c

## Later

<a id="i248"></a>
### 248. Raster2Seq trained from scratch on dev polygons

- What: Pilot a short run of the sequence model for rooms while keeping our own symbol detector.
- Evidence (floor-plans): Room F1 88.7 own paper, 0.8854 rebuild, 0.7626 independent on 398 whole-sheet plans; 19.4 h plus 16 h on a 48 GB card.
- Source: [arXiv 2602.09016](https://arxiv.org/abs/2602.09016), [arXiv 2609.25615](https://arxiv.org/abs/2609.25615)
- Licence: code MIT / weights CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: more than a day on a 12 or 16 GB card (estimate)
- Experiment: Only after the separator net has a number; short run, room F1 on dev.
- What breaks on our images: 256 px input, CUDA ops build, public scripts do not match checkpoint (issue 3), room_iou bug (issue 4).
- Moves: room-types. Why this group: 35 GPU-h reference cost and checkpoint is leaked
- Also (floorplan, floor-plans): Raster2Seq for rooms. Use Raster2Seq only for room polygons. Evidence: Room F1 88.7, window+door F1 77.8 at 256 px; evaluator bug in room IoU (issue 4). Source: [arXiv 2602.09016](https://arxiv.org/abs/2602.09016). Experiment: Room F1 on dev.
- Also (rooms, authors-claim): Raster2Seq CPU inference smoke test. Run the released model on one dev plan with the PyTorch reference path. Evidence: SALI-FP reports CPU runs of the released weights. Source: [arXiv 2609.25615](https://arxiv.org/abs/2609.25615). Experiment: Does it run without code edits.
- Reports: lit-floorplan-a, lit-floorplan-b, lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i249"></a>
### 249. Separate extraction from reasoning: symbols first, then text and rooms

- What: Keep symbol detection and label reading as separate steps and give a VLM our extraction JSON next to the image.
- Evidence (adjacent-field): Lee and Sarvghad 2025: adding SVG text to the PNG lifted label F1 from 0.70 to 0.96 (Llama); P&ID multimodal two-stage workflow beat end-to-end on two case studies.
- Source: [arXiv 2511.03478](https://arxiv.org/abs/2511.03478), [arXiv 2607.19568](https://arxiv.org/abs/2607.19568)
- Licence: papers CC BY. CubiCasa5K leakage: unknown.
- Cost: 3 h (estimate)
- Experiment: Pass the extraction JSON with the image to the answering model on dev.
- What breaks on our images: Our input is raster only.
- Moves: room-types. Why this group: pipeline already splits it
- Reports: lit-market-b

<a id="i250"></a>
### 250. Axis-aligned corner-pair lines across door gaps

- What: Draw a line between wall corners aligned in x or y within a distance.
- Evidence (search-only): Two hobby repos use it, no metric.
- Source: [github.com](https://github.com/grebtsew/FloorplanToBlender3d)
- Licence: GPL-3.0 (idea only). CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Only after rotating each sheet to its dominant directions.
- What breaks on our images: Fails on rotated sheets and oblique walls.
- Moves: scale-areas. Why this group: folk method, unmeasured
- Reports: lit-rooms-c

## Idea or pitch only

<a id="i251"></a>
### 251. Frozen DINOv2 or RADIO plus LoRA head

- What: Few-label segmenter if dev polygons are scarce; upscale 2 to 3 times.
- Evidence (adjacent-field): PQ 67.3 on ICDAR 2021 blocks with 5 to 10 tiles against 74.1 for the winner.
- Source: [arXiv 2506.21826](https://arxiv.org/abs/2506.21826)
- Licence: DINOv2 Apache-2.0. CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Compare with the U-Net at 10 labelled plans.
- What breaks on our images: 14 to 16 px patches.
- Moves: scale-areas. Why this group: only if labels are few
- Reports: lit-rooms-c

<a id="i252"></a>
### 252. Frame Field Learning or HiSup polygoniser

- What: Fallback polygoniser on our mask.
- Evidence (adjacent-field): CrowdAI AP 64.5 to 79.4; retrain gives 64.7.
- Source: [arXiv 2004.14875](https://arxiv.org/abs/2004.14875), [arXiv 2208.00609](https://arxiv.org/abs/2208.00609)
- Licence: BSD-3 / MIT. CubiCasa5K leakage: no.
- Cost: 3 to 5 h
- Experiment: Only if raw polygons are visibly not right-angled.
- What breaks on our images: Aerial weights.
- Moves: scale-areas. Why this group: snap does the job
- Reports: lit-rooms-a, lit-rooms-c

<a id="i253"></a>
### 253. ProClosure progressive thickening that freezes closed regions

- What: Dilate walls one pixel per step and freeze each free region once it is enclosed, seeds from OCR boxes or distance maxima.
- Evidence (adjacent-field): Room F1 0.890 against 0.741 on 10 floors of video-built maps; the gain came from annotation door frames, per-region radius untested.
- Source: [arXiv 2609.12614](https://arxiv.org/abs/2609.12614)
- Licence: repo licence file unclear. CubiCasa5K leakage: no.
- Cost: half a day (estimate)
- Experiment: Test against the radius sweep on dev plans.
- What breaks on our images: Needs seeds; untested on drawings.
- Moves: scale-areas. Why this group: mechanism not shown to beat a plain closing
- Reports: lit-rooms-a

## Do not try (with the reason)

<a id="i254"></a>
### 254. CubiCasa5K-trained checkpoints on our scans

- What: Do not rely on them; also leaked for scored runs.
- Evidence (floor-plans): Room IoU 91 to 65 on real scans, wall 27.5; interior IoU 46.1 on web plans; R2V recall 4.5% on blueprints.
- Source: [arXiv 2504.03241](https://arxiv.org/abs/2504.03241), [arXiv 2412.00955](https://arxiv.org/abs/2412.00955)
- Licence: CC BY-NC. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: style shift
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i255"></a>
### 255. Rule-based plan vectoriser loses to learned nets on the same plans

- What: Do not build rooms from a palette-and-geometry rule vectoriser instead of a learned model.
- Evidence (floor-plans): SALI-FP (arXiv 2609.25615): room F1 0.4450 for the rule route vs 0.6305 (CubiCasa5K nets) and 0.7626 (Raster2Seq) on 400 plans; four-class mIoU 0.3596 vs 0.7390; pooled door IoU 0.0396 raw vs 0.6181 for a 2019 net. No counts reported.
- Source: [arXiv 2609.25615](https://arxiv.org/html/2609.25615)
- Licence: no code. CubiCasa5K leakage: no.
- Cost: 0 h
- Experiment: None.
- What breaks on our images: Pipeline uses a generative image model; not all rules are ours.
- Moves: none. Why this group: Rule route loses on every measure
- Reports: lit-vector-a, lit-vector-b

<a id="i256"></a>
### 256. SAM 2 auto and SAM 3 text prompt on 20 dev plans

- What: Measure against the trained net.
- Evidence (floor-plans): Pretrained SAM 2 10.49 mIoU on scans, 69.58 fine-tuned; no SAM 3 plan result.
- Source: [researchsquare.com](https://www.researchsquare.com/article/rs-9512825/latest.pdf)
- Licence: SAM 2 Apache-2.0, SAM 3 custom. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Net's matched-room IoU is the bar.
- What breaks on our images: 1024 px input.
- Moves: none. Why this group: closes the question
- Also (rooms, adjacent-field): Zero-shot SAM family as the room source. Do not use automatic masks as rooms. Evidence: Field parcels 0.382 against 0.720, manga panels 0.33 to 0.63 against 0.977, aerial 0.431 against 0.720. Source: [arXiv 2511.13417](https://arxiv.org/abs/2511.13417). Experiment: none
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i257"></a>
### 257. Avoid SegFormer and MiT encoders

- What: Use ResNet or ConvNeXt encoders; mit_b4 is NVIDIA research-only.
- Evidence (floor-plans): LICENSE lines read.
- Source: [github.com](https://github.com/NVlabs/SegFormer)
- Licence: NVIDIA non-commercial. CubiCasa5K leakage: unknown.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: cannot ship
- Reports: lit-rooms-a, lit-rooms-b

<a id="i258"></a>
### 258. VLM asked for rooms or areas

- What: Do not replace the geometry step with a prompt.
- Evidence (floor-plans): Small open VLMs area MAPE about 43%; GPT-image route room F1 0.445 against 0.763; area instance F1 0.08 to 0.23 for frontier models (vendor).
- Source: [arXiv 2609.25615](https://arxiv.org/abs/2609.25615), [pp.bme.hu](https://pp.bme.hu/ci/article/view/44138)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Coordinates coarse.
- Moves: none. Why this group: consistently worse
- Reports: lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i259"></a>
### 259. Pix2Poly, PolyWorld, RoomFormer-type decoders

- What: Skip direct vertex decoders for rooms.
- Evidence (adjacent-field): PolyTopoBench: Pix2Poly 0.102 AP50 against 0.720 for Mask R-CNN plus polygonise; RoomFormer fixed 20 rooms by 40 corners.
- Source: [arXiv 2609.32856](https://arxiv.org/abs/2609.32856)
- Licence: mixed. CubiCasa5K leakage: no.
- Cost: none
- Experiment: none
- What breaks on our images: Aerial benchmark.
- Moves: none. Why this group: costly and weak
- Reports: lit-rooms-a, lit-rooms-c

<a id="i260"></a>
### 260. Do not guess room type from layout

- What: Never classify unlabelled rooms from area and neighbours; leave them uncounted.
- Evidence (adjacent-field): ResPlan: 0.951 in one style, 0.19 to 0.65 across; fixtures classifier 76 to 79% falling to 58 to 66% on a second set; a bedroom with no label counts 0.
- Source: [arXiv 2508.14006](https://arxiv.org/abs/2508.14006), [arXiv 1812.00874](https://arxiv.org/abs/1812.00874)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Would add rooms the gold does not count.
- Moves: room-types. Why this group: hurts exact counts
- Reports: lit-rooms-a, lit-rooms-b
