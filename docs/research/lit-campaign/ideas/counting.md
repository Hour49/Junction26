# Counting (from marks to an exact number)

42 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i151"></a>
### 151. Duplicate removal by intersection over the smaller box, tuned NMS even for DETRs

- What: After detection, class-wise NMS with a tuned IoU and an intersection-over-smaller rule across tile borders only; keep it off inside a tile so adjacent window panes stay separate; train to convergence.
- Evidence (floor-plans): RF-DETR issue 434: duplicate boxes at IoU above 0.9 on one object, rare after 85 epochs but not gone; sliced-inference study: NMS with IoS best merge, greedy merging and WBF merge distinct neighbours; railway drawings: containment merge cut false positives 288 to 186.
- Source: [github.com](https://github.com/roboflow/rf-detr/issues/434), [arXiv 2611.12657](https://arxiv.org/abs/2611.12657), [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1-2 h
- Experiment: Score NMS vs IoS rule on dev with window strips as the watched case.
- What breaks on our images: Containment merge can merge a window strip's panes.
- Moves: windows-doors. Why this group: Decides exact counts; one duplicate is one wrong answer
- Also (count, adjacent-field): Duplicate rule: overlap over the smaller box. Suppress detections by intersection over the smaller box (0.5) instead of IoU, then count survivors; check strips. Evidence: CountBench exact 84.8% to 94.0%, PixMo-Count 76.9% to 86.3% with IoM (arXiv 2511.16719, Table 37; photos, 2-10 objects). Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719). Experiment: On the detector's dev predictions: IoU-NMS vs IoM-NMS at 0.3/0.5/0.7, exact rate per class, strips of windows watched separately.
- Also (count, adjacent-field): Overlapping tiles with a class-aware merge. Overlap tiles by the largest object and merge duplicates class-aware, or count only the tile centre. Evidence: Wildlife tiles overlap 160 px, mean of overlaps (ISPRS 2023); PCB 128 px overlap lifts boundary recall 26-63% to 70-100% (arXiv 2605.24726, abstract); CoNIC counts the central region. Source: [github.com](https://github.com/Alexandre-Delplanque/HerdNet). Experiment: If tiling is used, double-count rate with vs without the merge.
- Also (data, adjacent-field): Overlapping tiles with box merging so a border window is one count. Tile with overlap and merge boxes across tile borders (adjacency merge) so a window cut by a tile border is not counted twice. Evidence: PCB: 128 px overlap lifts boundary-zone recall from about 26-63% to 70-100%; a training-free topology-aware tile merge gave the best mAP@50 on both sets (arXiv 2605.24726). Dense-tile misses with SAHI tiling in RF-DETR issue 780. Source: [arXiv 2605.24726](https://arxiv.org/abs/2605.24726). Experiment: Count with and without merge on dev; report duplicate and miss error per class.
- Also (detect, floor-plans): Box NMS then mask-containment merge across tile borders. When tiling, merge tile duplicates with box NMS then a containment test (intersection over minimum about 0.6) restricted to pairs that cross a tile border. Evidence: Railway drawings, 768 px tiles stride 384: precision 0.345 without merge, 0.500 box NMS, 0.853 plus box containment, 0.899 with mask containment (F1 0.9226); overlap barely matters (F1 0.9176 at 0%, 0.9226 at 20%). Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/). Experiment: Test on window strips first; compare to centre-point ownership.
- Also (trust, search-only): Count difference across tile offsets as a duplicate and boundary check. Compare counts for two tile offsets; large differences flag duplicates or boundary misses. Evidence: No controlled study of how a merge rule changes count error; SAHI merge options and Cluster-DIoU-NMS exist (2604.19233, docs level). Source: [arXiv 2604.19233](https://arxiv.org/abs/2604.19233). Experiment: Report count change between offsets and its relation to errors on dev.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-data-b, lit-detect-a, lit-detect-b, lit-detect-c, lit-trust-a

<a id="i152"></a>
### 152. Read objects from a detection or heatmap output, not a sequence decoder

- What: Prefer detection maps or box detectors over autoregressive sequence decoders for counted objects.
- Evidence (floor-plans): Same network: opening F1 0.25 to 0.64 when read from heatmaps instead of the sequence decoder (2608.25608); Raster2Seq appends doors and windows after rooms and calls them an area to refine.
- Source: [arXiv 2608.25608](https://arxiv.org/html/2608.25608)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 0 h (design rule)
- Experiment: None.
- What breaks on our images: CubiCasa5K at 256 px.
- Moves: none. Why this group: Free design rule supporting the detector route
- Also (detect, floor-plans): Read doors and windows from a detection map, not a sequence decoder. Design rule: counted objects come from a detector or heatmap readout; do not use autoregressive vectoriser output as the counter. Evidence: Real scans: opening F1 0.64 from a heatmap vs 0.25 for the autoregressive decoder of the same network (arXiv 2608.25608); Raster2Seq trains at 256 px, symbols 1-4 px. Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608), [arXiv 2602.09016](https://arxiv.org/abs/2602.09016). Experiment: n/a
- Also (floorplan, floor-plans): Read doors and windows from a local head, not a sequence decoder. Use a detection head for openings; do not emit them in a polygon sequence. Evidence: Opening F1 0.246 emitted, 0.644 heatmap, 0.799 family ignored, 0.988 family accuracy of a 200K head; CubiCasa5K test n=287, 3,328 training plans (arXiv 2608.25608, re-checked). Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608), [github.com](https://github.com/Cyprinus12138/fpvec-lab). Experiment: Justifies detector choice; no run needed.
- Also (market, floor-plans): Read an opening heatmap instead of emitting coordinates. Detect openings as a local heatmap problem, not a sequence-emission problem. Evidence: fpvec-lab: opening F1 0.246 emitted against 0.644 to 0.799 read from a heatmap; CubiCasa5K official test n 287. Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608). Experiment: Compare heatmap readout to box detector on dev for window count error.
- Also (vlm, floor-plans): Read openings from a dense head, not as emitted coordinates. Compare a detector or heatmap head against the VLM point list for doors and windows on the same dev plans; use the result to decide which path owns openings. Evidence: Same network on CubiCasa5K test n=287: opening F1 0.246 as sequence, 0.644 from heatmap, 0.799 family ignored (2608.25608). Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608), [arXiv 2602.09016](https://arxiv.org/abs/2602.09016). Experiment: Run detector and VLM-point arms on the same dev plans; report exact count per plan, not F1.
- Reports: lit-detect-a, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c, lit-market-a, lit-market-b, lit-vector-a, lit-vlm-c

<a id="i153"></a>
### 153. Second counter: template matching with a symbol cut from the same plan

Reviewer's note: The 0.87 F1 quoted below is on 34 legend drawings. On the same paper's floor-plan blocks (arXiv 2610.09313, Table 20: 339 test items, 21 classes) template matching gets 0.58 and the trained exemplar counters 0.19 and 0.34. Expect the lower figure on plans.

- What: Cut one single-cell symbol from the plan being counted (the detector's most confident box), slide it over the sheet with normalised cross-correlation at four 90-degree rotations and a few scales, take peaks, count them. Use it as the independent second count that feeds conflicts and abstention, not as the main count.
- Evidence (floor-plans): LegendSpot, 34 architectural drawings, 660 instances: F1 0.87 with the drawing's own legend crop; exactly right on 14 of 40 drawings (10 of 20 small views, 4 of 20 large sheets) with a leave-one-out threshold, 23 of 40 with an oracle threshold (arXiv 2610.09313, appendix and repo summary). Drawings are larger than our plans.
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313), [opencv.org](https://opencv.org)
- Licence: code MIT (paper repo), OpenCV Apache-2.0; no weights. CubiCasa5K leakage: no.
- Cost: 1-2 h on CPU for a first number (estimate)
- Experiment: On dev plans only: take the detector's top box per class as template, run 4 rotations x 5 scales, tune the peak threshold per class on half the dev plans, score exact count on the other half. Settles it: exact-count rate per class and whether it sides with the right detector when two detectors disagree.
- What breaks on our images: Windows share strokes with wall lines and door arcs sit next to sink bowls, so false positives; 5-20 px symbols; exact rate was only 35% in the best published case; a wrong exemplar spreads its error.
- Moves: windows-doors. Why this group: Only published exemplar result on drawings, cheap, CPU, no licence issue.
- Also (count, floor-plans): Template matching recipe: 20 variants, best response per pixel, upscale instead of shrink. TM_CCOEFF_NORMED on grey images; scales 0.8, 0.9, 1.0, 1.1, 1.25 x rotations 0/90/180/270; keep the best response per pixel; local maxima with a floor of 0.30; greedy suppression within half the template short side; never let the template short side fall under 12 px (upscale our small plans). Evidence: Recipe copied from the baseline script of the LegendSpot repo; threshold chosen leave-one-drawing-out, 0.87 F1 (arXiv 2610.09313); a fixed threshold across blocks drops to 0.18 on far blocks because 49% of instances differ by over 20% in box size. Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313). Experiment: Implement on dev plans, compare exact count against the detector alone per class; ablate grey vs edge image and 4 vs 8 variants.
- Also (count, authors-claim): Mask-and-IoU template matching with overlap-over-minimum suppression. Binarise the symbol, take its mask (convex hull of strokes), score candidates by mask IoU instead of pixel correlation, suppress duplicates by IoM NMS. A drop-in alternative to plain correlation in the second counter. Evidence: Han et al., EC3 2026: F1 0.992 on real industrial P&IDs (author-reported, set size not in the abstract); full paper not read. Source: [doi.org](https://doi.org/10.35490/EC3.2026.241). Experiment: On dev plans compare plain correlation against mask-IoU scoring per class, exact-count rate; both with the same exemplars.
- Also (floorplan, adjacent-field): Multi-scale four-rotation template matching from one crop per class. Run normalised cross-correlation (scales 0.8-1.25, rotations 0/90/180/270, NMS) from one crop per class as the first baseline. Evidence: 0.87 F1 on 34 drawings when the reference is from the same drawing, 0.38 with a library reference; best tiled VLMs 0.92/0.94 (arXiv 2610.09313, re-checked). Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313), [github.com](https://github.com/shijunzhe/vlm-small-objects). Experiment: Dev exact/within 1 per class vs 33% PlanQ floor.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c

<a id="i154"></a>
### 154. Tune the score threshold per class for exact count, not AP or F1

- What: Pick, per class, the confidence threshold (then the NMS threshold) that maximises the share of dev images with the exact right count; use a smoothed pick (middle of the best plateau); use rfdetr ClassThresholds for the plumbing.
- Evidence (adjacent-field): Counting precedent: grid search of score then NMS threshold per category on held-out data (arXiv 1604.03505); RF-DETR cookbook tunes per-class F1 thresholds (single 0.41 beat default 0.5, per-class not better); dislocation counting used a threshold far below the validation optimum (R, 98.6%). No repo tunes for per-image count.
- Source: [arXiv 1604.03505](https://arxiv.org/abs/1604.03505)
- Licence: n/a (own code, 10 lines). CubiCasa5K leakage: no.
- Cost: CPU, 1-2 h
- Experiment: On saved dev predictions: AP-tuned vs count-tuned threshold; report exact-count rate per class.
- What breaks on our images: Single digits per class make exact match noisy; overfits a small dev slice.
- Moves: windows-doors. Why this group: Decides several points; no GPU needed
- Also (count, our-idea): Choose the score threshold per class for exact count, not AP. Grid the confidence threshold per class on a held-out dev slice and keep the one with the highest exact-count rate. Evidence: CountGD fixes 0.23 from {0.14..0.26} on MAE (arXiv 2407.04619); SAM 3 fixed 0.5; no paper tunes a detector threshold on count error (lit-count-a round 8). Source: [arXiv 2407.04619](https://arxiv.org/abs/2407.04619). Experiment: Tune on half the dev, score on the other half: exact rate vs AP-tuned threshold per class.
- Also (data, adjacent-field): Sweep the score threshold on dev for recall and keep tile scores stable. Do not leave the detector at 0.25; sweep the threshold per class on dev, and compare a shifted-tile average against a fixed tile grid because confidence swings with small shifts. Evidence: RF-DETR-M precision 0.985 but recall 0.800 at confidence 0.25 vs 0.924 for Faster R-CNN (arXiv 2607.18997 Table 2). Issue 1599: confidence 0.91 at 0 px shift, 0.49 at 11 px, 0.88 at 12 px while IoU stayed 0.90-0.95. Threshold 0.02 vs default changed one mAP by 0.13. Source: [github.com](https://github.com/roboflow/rf-detr/issues/1599). Experiment: Threshold sweep per class and a 2x2 shifted-grid average; read exact count.
- Reports: lit-count-a, lit-count-c, lit-data-a, lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c

## Try next

<a id="i155"></a>
### 155. Global consistency step to remove duplicate openings

- What: Reject two openings on one wall segment, require an opening to sit on a wall.
- Evidence (floor-plans): Opening precision 67.9 to 91.9 at recall 91.4 to 90.2 (R2V Table 1).
- Source: [openaccess.thecvf.com](https://openaccess.thecvf.com/content_ICCV_2017/papers/Liu_Raster-To-Vector_Revisiting_Floorplan_ICCV_2017_paper.pdf)
- Licence: code MIT. CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Dev precision and counts.
- What breaks on our images: Manhattan assumption; windows are strips.
- Moves: windows-doors. Why this group: duplicates ruin exact counts
- Reports: lit-floorplan-a

<a id="i156"></a>
### 156. Pick exemplars by feature consensus and diversity, not the top two scores

- What: From the detector's confident boxes on the plan take 3 whose embeddings are closest to the others (CountZES) and vary size and appearance (PerSense++), rather than the highest scores.
- Evidence (adjacent-field): CountZES shows similar exemplars give different counts and a three-stage inference-only pick improves cross-domain results (arXiv 2512.16415); MixCount: a non-optimal exemplar raises MAE by about 4.7% relative (arXiv 2605.18063); CountingDINO: 3 exemplars MAE 20.93 vs 37.73 with 1 (arXiv 2504.16570).
- Source: [arXiv 2512.16415](https://arxiv.org/abs/2512.16415), [arXiv 2605.18063](https://arxiv.org/abs/2605.18063)
- Licence: CountZES code PolyForm Noncommercial, PerSense same; idea only. CubiCasa5K leakage: no.
- Cost: 30 min (estimate)
- Experiment: In the template-matching or CountGD++ experiment, compare top-2-by-score exemplars to consensus-3 exemplars.
- What breaks on our images: Photos only.
- Moves: windows-doors. Why this group: One-line change to the exemplar step.
- Reports: lit-count-b, lit-count-c

<a id="i157"></a>
### 157. CountGD++ as a stage-8 second counter

- What: Call count() with the class word plus 1-3 exemplar boxes cut from the same plan, once at plan size and once on a 2x Lanczos upscale; compare to the detector count.
- Evidence (adjacent-field): FSCD-147 MAE 16.55 text-only, 10.29 with pseudo-exemplars (arXiv 2512.23351, Table 1); its predecessor CountGD F1 0.10 on architectural drawings with a legend crop (arXiv 2610.09313).
- Source: [arXiv 2512.23351](https://arxiv.org/abs/2512.23351), [github.com](https://github.com/niki-amini-naieni/CountGDPlusPlus)
- Licence: code MIT / weights MIT (HF card); built on Apache-2.0 parents. CubiCasa5K leakage: no.
- Cost: 1-2 h to a number (estimate); 12 GB inference unproven (parent used 15.5 GB)
- Experiment: 40 dev plans, exemplars cut from the same plan; report exact rate per class and detector-agreement trust (below). Drop if below template matching.
- What breaks on our images: Swin-B at 800 px short side leaves 5-20 px symbols near one feature cell; default threshold 0.23 tuned for photos; own virtual environment because of transformers pins.
- Moves: windows-doors. Why this group: Short probe, MIT everything, answers the exemplar question.
- Also (count, adjacent-field): Negative exemplars for door-without-leaf, shower screen, bare wall. Pass a negative exemplar (bare opening, screen, wall run) so the counter drops look-alikes. Evidence: Blood cells MAE 11.56 to 1.73 with negative text plus exemplar; fruits 2.41 to 0.41; absent-class mean count 0.88 to 0.07 (arXiv 2512.23351, Tables 2-3). Source: [arXiv 2512.23351](https://arxiv.org/abs/2512.23351). Experiment: In the CountGD++ probe add a negative exemplar per class; compare false-positive count.
- Also (count, adjacent-field): Fine-tune an exemplar counter on our own boxes. Fine-tune CountGD (training code released for CountGD++) with the target slice changed to all four box values, on dev boxes. Evidence: CoLSR: fine-tuned CountGD MAE 0.88 vs 7.84 stock and 4.24 for a fine-tuned DQ-DETR on 1,464 surgical-instrument images with 7-49 objects (arXiv 2602.11024); no exact match reported. Source: [arXiv 2602.11024](https://arxiv.org/abs/2602.11024). Experiment: Only after the detector exists: compare to the fine-tuned detector on exact rate.
- Also (floorplan, adjacent-field): CountGD, GeCo2, Chain-of-Look style spacing loss, fine-tuned. Fine-tune an exemplar counter on our symbols; add a neighbour-spacing loss for window strips. Evidence: On drawings CountGD 0.10, GeCo2 0.23 F1 zero-shot vs 0.87 template matching; Chain-of-Look MAE 0.88 on 1,236 images. Source: [arXiv 2602.11024](https://arxiv.org/abs/2602.11024), [arXiv 2511.08048](https://arxiv.org/abs/2511.08048). Experiment: Compare with detector counts.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-floorplan-a, lit-floorplan-c

<a id="i158"></a>
### 158. Divide the count by the instances inside the exemplar

- What: Make exemplar boxes single cells and, if the exemplar holds several panes, divide the count by the instances per exemplar (CounTR/CountGD SAM-mask rule).
- Evidence (adjacent-field): FSC-147 MAE/RMSE 10.92/99.58 without, 9.62/98.90 with SAM normalisation (arXiv 2407.04619, Table 4); a three-pane strip inflates counts.
- Source: [arXiv 2407.04619](https://arxiv.org/abs/2407.04619)
- Licence: code MIT. CubiCasa5K leakage: no.
- Cost: none
- Experiment: Check exemplars cut from dev boxes (one per drawn cell) never contain two panes.
- What breaks on our images: SAM masks on thin line art untested.
- Moves: windows-doors. Why this group: Enforce by cutting exemplars from single-cell labels.
- Reports: lit-count-a, lit-count-b, lit-count-c

## Later

<a id="i159"></a>
### 159. Exemplar with surroundings, not tight crop

- What: Give the VLM the symbol highlighted in context.
- Evidence (floor-plans): Exact match 50.5% vs 36.5% (BlueprintSymVL, 100 regions).
- Source: none
- Licence: CC BY. CubiCasa5K leakage: no.
- Cost: 30 min
- Experiment: If a VLM verifier is used: same candidates with a tight crop vs the crop inside its surroundings, exact rate on dev.
- What breaks on our images: 100 regions, 5 valve classes, four 2025 models, wide error bars; P&ID not floor plans.
- Moves: windows-doors. Why this group: VLM only.
- Reports: lit-count-a

<a id="i160"></a>
### 160. GeCo2 as a few-shot box counter

- What: Run GeCo2 with 1-3 exemplar boxes cut from the plan (or stored prototypes from dev plans) and count the boxes; fine-tune only if zero-shot shows promise.
- Evidence (floor-plans): FSCD147 test MAE 7.64, AP 46.81, 4.98 GB and 0.2 s on an A100 (arXiv 2511.08048); on architectural drawings with a legend crop F1 0.23, library 0.15, FloorPlanCAD blocks 0.34 (arXiv 2610.09313).
- Source: [arXiv 2511.08048](https://arxiv.org/abs/2511.08048), [github.com](https://github.com/jerpelhan/GECO2)
- Licence: code MIT / weights licence unstated; training data chain includes a dataset with a commercial-licence restriction. CubiCasa5K leakage: no.
- Cost: 2-3 h for a zero-shot number (estimate)
- Experiment: 40 dev plans, exemplars cut from the plan, tune the score threshold per class on 20, score the other 20; keep only if it beats template matching.
- What breaks on our images: No negative exemplars; fires on parallel wall lines; weights licence unclear; demo threshold is relative to the best box and can never answer zero.
- Moves: windows-doors. Why this group: Zero-shot is below template matching on drawings.
- Also (floorplan, adjacent-field): Exemplar counters without fine-tuning on drawings. Do not use them untuned. Evidence: 0.10 and 0.23 F1 on legend drawings vs 0.90/0.86 on FSC-147. Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313). Experiment: none
- Also (vlm, adjacent-field): Exemplar counter with one cropped symbol. Use CountGD with a cropped window as exemplar. Evidence: FSC-147 MAE 5.74 text plus exemplars (2407.04619). Source: [arXiv 2407.04619](https://arxiv.org/abs/2407.04619). Experiment: Counts on dev.
- Reports: lit-count-a, lit-count-c, lit-floorplan-a, lit-floorplan-c, lit-vlm-c

<a id="i161"></a>
### 161. Per-class post-processing for segmentation counts

- What: Tune the merge kernel separately for doors and windows; one kernel moves them in opposite directions.
- Evidence (floor-plans): Closing kernel 0/3/5/9: doors 64/66/67/65, windows 63/63/61/56 of 190 (PlanQ JSON); overcount bias shrinks as kernel grows.
- Source: [github.com](https://github.com/SoftHeart1314/planq-cubicasa-benchmark)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Sweep per class on dev.
- What breaks on our images: Merging real neighbouring windows if kernel is large.
- Moves: windows-doors. Why this group: small gain if a segmentation arm is used
- Reports: lit-floorplan-a

<a id="i162"></a>
### 162. Centre-only fixed-size head (YOLSO) as an independent counter

- What: Fully convolutional net predicting class and centre offset per grid cell; count = number of peaks; a second measurement for stage 8.
- Evidence (adjacent-field): Historical-map trees: point mAP@0.5 97.9% vs YOLOv3 43.6% vs Faster R-CNN 70.2% (22,882 points).
- Source: [eprints.whiterose.ac.uk](https://eprints.whiterose.ac.uk/198859/1/_ICDAR_YOLSO.pdf), [github.com](https://github.com/waps101/YOLSO)
- Licence: code GPL-3.0 (own reimplementation needed). CubiCasa5K leakage: no.
- Cost: 3-4 h
- Experiment: Own ~150-line version; compare to detector counts on dev.
- What breaks on our images: Assumes one fixed scale; ours varies 10x.
- Moves: trust. Why this group: After the detector baseline
- Reports: lit-detect-b

<a id="i163"></a>
### 163. Box-level conformal guarantees as count guarantees

- What: Do not present box coverage as a count guarantee.
- Evidence (adjacent-field): Guarantees hold only for detected objects (2403.07263, 2304.06052).
- Source: [arXiv 2403.07263](https://arxiv.org/abs/2403.07263)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: Misses uncovered.
- Also (trust, our-idea): Count interval of width zero as the accept rule. Split-conformal on absolute count error per plan; accept when the interval is a single integer. Evidence: No source tested; recalibrated count intervals reached 0.89-0.915 coverage on crowds (1903.07427); raw intervals 9-61% (1907.11555). Source: [arXiv 1903.07427](https://arxiv.org/abs/1903.07427), [arXiv 1907.11555](https://arxiv.org/abs/1907.11555). Experiment: Compare with the plan-level gate.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i164"></a>
### 164. Template matching in DINOv2 feature space

- What: ROI-Align exemplar patch as a convolution kernel over features with quadrant partition.
- Evidence (adjacent-field): CountingDINO FSC-147 test MAE 20.93 with 3 exemplars vs 37.73 with 1 (arXiv 2504.16570).
- Source: [arXiv 2504.16570](https://arxiv.org/abs/2504.16570)
- Licence: repo no licence; DINOv2 Apache-2.0. CubiCasa5K leakage: unknown.
- Cost: one day
- Experiment: Compare vs pixel matching on 50 dev plans.
- What breaks on our images: Coarse stride.
- Moves: windows-doors. Why this group: One-day experiment.
- Reports: lit-count-a, lit-count-b, lit-count-c

<a id="i165"></a>
### 165. Probe hidden state for the count

- What: Train a linear head on a frozen VLM state to read counts.
- Evidence (adjacent-field): Probe near perfect, output path loses about 30% (2510.19555).
- Source: [arXiv 2510.19555](https://arxiv.org/abs/2510.19555)
- Licence: repo named. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: Accuracy per true count on dev.
- What breaks on our images: Simple shapes.
- Moves: windows-doors. Why this group: Cheap.
- Reports: lit-vlm-c

<a id="i166"></a>
### 166. Mean or median of several counters as a combiner

- What: Combine counts from several methods by mean or median, not a learned confusion model.
- Evidence (adjacent-field): Mean best on the numeric task in a 17-method benchmark (one dataset); Dawid-Skene assumes independence (2601.22336).
- Source: [vldb.org](https://www.vldb.org/pvldb/vol10/p541-zheng.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Compare with best single counter on dev.
- What breaks on our images: One dataset.
- Moves: trust. Why this group: Cheap baseline.
- Reports: lit-trust-c

<a id="i167"></a>
### 167. Feed the counter's own top boxes back as exemplars for a second pass

- What: Take the first pass's top 3 boxes as exemplars and run again to find the rest of the plan's symbols.
- Evidence (adjacent-field): CountGD++ FSCD-147 MAE 16.55 to 10.29 (arXiv 2512.23351); AdaCount SAM 3 pass 22.89 to 18.97, CARPK 3.52 to 1.99 (arXiv 2607.02139); but an independent run gives LookAlikes 24.6 to 29.1 (worse) and PairTally 66.9 to 65.5 (arXiv 2608.20621).
- Source: [arXiv 2512.23351](https://arxiv.org/abs/2512.23351), [arXiv 2607.02139](https://arxiv.org/abs/2607.02139), [arXiv 2608.20621](https://arxiv.org/abs/2608.20621)
- Licence: CountGD++ MIT; AdaCount needs SAM 3 (custom licence), code licence unstated. CubiCasa5K leakage: no.
- Cost: 1-2 h inside the CountGD++ probe
- Experiment: Same 40 dev plans: first pass vs pseudo-exemplar pass; report exact rate, not MAE.
- What breaks on our images: Cannot recover objects the first pass missed (our main error); makes look-alike errors worse.
- Moves: windows-doors. Why this group: Mixed evidence, never on drawings.
- Reports: lit-count-a, lit-count-b, lit-count-c

<a id="i168"></a>
### 168. Coverage-weighted fusion for tiles

- What: Replace box NMS by accumulating dense outputs.
- Evidence (adjacent-field): DOTA +2.3-4.0 mAP50 over SAHI merge.
- Source: [arXiv 2611.12657](https://arxiv.org/abs/2611.12657)
- Licence: code in repo. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Only if tiling is needed.
- What breaks on our images: Aerial.
- Moves: windows-doors. Why this group: only after tiling proves needed
- Reports: lit-floorplan-c

<a id="i169"></a>
### 169. Transcribe then count; second read of rotated copy

- What: Have the VLM transcribe objects, count in code, and read a rotated copy as a vote.
- Evidence (adjacent-field): Rotated second read 86/96 vs 57/96 (2611.08998, synthetic diagrams).
- Source: [arXiv 2611.08998](https://arxiv.org/abs/2611.08998)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 calls per plan
- Experiment: Agreement rate and exact count on dev.
- What breaks on our images: Synthetic grids.
- Moves: trust. Why this group: Cheap diversity.
- Reports: lit-vlm-a

## Idea or pitch only

<a id="i170"></a>
### 170. Tile for a VLM so every target gets at least 1.5 tokens per side, never zoom out

- What: Give the VLM one example crop and ask for each instance's centre; split the sheet at the same scale so each target spans at least 1.5 visual tokens, overlap tiles by one target, merge points.
- Evidence (floor-plans): Recall on LegendSpot 0.62 to 0.90 (Gemini), 0.85 to 0.98, 0.37 to 0.56 for Qwen3-VL; zoom-out splits lowered recall in 19 of 21 settings; packing 8 tiles in one call 0.77 to 0.47 (arXiv 2610.09313).
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: rule is arithmetic; paper tool MIT. CubiCasa5K leakage: unknown.
- Cost: 2 h to plan tiles (estimate); API or local VLM cost on top
- Experiment: Only for photo or large-sheet inputs: tile a dev photo set at native scale vs whole image, compare recall of a small VLM against the detector.
- What breaks on our images: Qwen3-VL recalled 0.22 of 96 targets in a controlled test; 5-20 px symbols are below one token on small models.
- Moves: windows-doors. Why this group: Overlaps the VLM scope and weak for small open models.
- Reports: lit-count-a

<a id="i171"></a>
### 171. Split merged blobs by contour concavity

- What: Split contours at concave points and fit candidate units.
- Evidence (adjacent-field): MCount: error 3.99% vs 16.5%, zero error on 91.45% of 15,847 colony segments (PLOS One 2025); PerSense splits contours by distance transform.
- Source: [github.com](https://github.com/hyu-kim/mcount)
- Licence: code MIT. CubiCasa5K leakage: no.
- Cost: half a day
- Experiment: Wall-mask strip experiment.
- What breaks on our images: Fits circles.
- Moves: windows-doors. Why this group: Blobs only.
- Reports: lit-count-b

<a id="i172"></a>
### 172. Integer-bin count classification with Wasserstein loss

- What: Classify tile count into bins 0,1,2,...,m+ and use mode or expectation.
- Evidence (adjacent-field): UCF-QNRF MAE 140.6 to 77.9 (arXiv 2403.09281).
- Source: [arXiv 2403.09281](https://arxiv.org/abs/2403.09281)
- Licence: MIT, archived. CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Tile or whole-plan head with bins 0..15 and a 16+ bin on box counts from dev; compare exact rate to counting detector boxes.
- What breaks on our images: Results are crowds of hundreds; no per-bin low-count numbers; repo archived; one user got double counts with their own bins.
- Moves: windows-doors. Why this group: Detector first.
- Reports: lit-count-b

<a id="i173"></a>
### 173. Coverage-weighted dense fusion of overlapping passes (SCAHI)

- What: Fuse overlapping sliced passes with dense coverage weights instead of box fusion.
- Evidence (adjacent-field): DOTA: +4.3 to +5.6 mAP50 over the best single pass at 2048 px; aerial only.
- Source: [arXiv 2611.12657](https://arxiv.org/abs/2611.12657)
- Licence: code stated but no URL found. CubiCasa5K leakage: no.
- Cost: 4 h work
- Experiment: Compare with containment merge on the same tiles of large dev sheets.
- What breaks on our images: Aerial blobs against thin strokes; code not located.
- Moves: windows-doors. Why this group: Detection scope owns the detail.
- Reports: lit-sheet-a

<a id="i174"></a>
### 174. Deep Watershed Detector energy-map peaks for counting

- What: Predict an energy map with a cone peak at each centre and count peaks.
- Evidence (adjacent-field): noteheadBlack AP@0.5 0.862, @0.25 0.920; beaten by Faster R-CNN+HRNet on DeepScoresV2 except rare classes.
- Source: [arXiv 1805.10548](https://arxiv.org/abs/1805.10548)
- Licence: code MIT (TF1-era). CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Idea only.
- What breaks on our images: Overlapping centres; old code.
- Moves: trust. Why this group: Superseded by YOLSO-style head
- Reports: lit-detect-b

<a id="i175"></a>
### 175. NMS radius scaled by the exemplar size

- What: Duplicate radius from the exemplar's size so window cells are kept.
- Evidence (adjacent-field): AgriCountDINO (arXiv 2609.29460): 3-shot MAE 11.92.
- Source: [arXiv 2609.29460](https://arxiv.org/abs/2609.29460)
- Licence: DINOv3 custom; idea only. CubiCasa5K leakage: unknown.
- Cost: 1 h
- Experiment: With the IoM sweep: NMS radius = fraction of the exemplar short side, strips watched.
- What breaks on our images: Plants; DINOv3 weights carry a custom licence (idea only).
- Moves: windows-doors. Why this group: Idea only.
- Reports: lit-count-a, lit-count-c

<a id="i176"></a>
### 176. One-sided over/under-count risk control

- What: Control under-counting (kept boxes at least true boxes) and over-counting separately.
- Evidence (adjacent-field): 25.6 and 17.8 boxes per image vs 1.55 for a plain threshold on COCO (2505.24038).
- Source: [arXiv 2505.24038](https://arxiv.org/abs/2505.24038)
- Licence: code README MIT, no LICENSE file. CubiCasa5K leakage: n/a.
- Cost: 4 h work
- Experiment: Check set sizes on dev.
- What breaks on our images: Exact equality not controllable; sets far too large.
- Moves: trust. Why this group: Costly in boxes.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i177"></a>
### 177. Count by bisection yes/no questions

- What: Ask 'more than tau?' and bisect.
- Evidence (adjacent-field): FSC-147 MAE 13.91 (2602.12774), 18.7 GB.
- Source: [arXiv 2602.12774](https://arxiv.org/abs/2602.12774)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 7B
- Experiment: Compare with point lists.
- What breaks on our images: Too big.
- Moves: windows-doors. Why this group: Size.
- Reports: lit-vlm-c

<a id="i178"></a>
### 178. Zero-inflated Poisson per block

- What: Model empty blocks with zero inflation.
- Evidence (adjacent-field): NWPU val MAE 28.2 vs 36.6 (arXiv 2506.19955).
- Source: [arXiv 2506.19955](https://arxiv.org/abs/2506.19955)
- Licence: no code. CubiCasa5K leakage: no.
- Cost: unestimated
- Experiment: Idea only: if a count head is tried, give it a zero-inflation term since most tiles hold no window.
- What breaks on our images: No code URL in the paper; crowd data.
- Moves: windows-doors. Why this group: Fits sparse maps.
- Reports: lit-count-b

<a id="i179"></a>
### 179. Warp the image toward first-pass prototypes before a second SAM 3 pass

- What: Build per-image prototypes from first-pass masks, compute a similarity map, warp pixels to give those regions more resolution, run again.
- Evidence (authors-claim): FSC-147 MAE 22.89 to 18.97, CARPK 3.52 to 1.99, nuclei 23.25 to 19.11 (arXiv 2607.02139); fails when first pass finds nothing.
- Source: [arXiv 2607.02139](https://arxiv.org/abs/2607.02139)
- Licence: paper CC BY-NC-SA; code not stated; needs SAM 3. CubiCasa5K leakage: unknown.
- Cost: unestimated
- Experiment: Idea to port: local upscale around detected symbols before recount.
- What breaks on our images: Depends on SAM 3.
- Moves: none. Why this group: Licence chain.
- Reports: lit-count-a, lit-count-b

<a id="i180"></a>
### 180. Cardinality map

- What: Map summing to count.
- Evidence (search-only): YOLO-Count abstract only.
- Source: [arXiv 2508.00728](https://arxiv.org/abs/2508.00728)
- Licence: unknown. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: None until a repo and licence are found.
- What breaks on our images: Built for steering image generation; no drawings; no exact-count table.
- Moves: none. Why this group: Unverified.
- Reports: lit-count-a

## Do not try (with the reason)

<a id="i181"></a>
### 181. Template matching with a reference symbol from a library or legend

Reviewer's note: Library and legend templates measured poorly; a symbol cut from the same plan is the version that works. A hand-drawn symbol bank stays an idea. Same-plan matching itself scores 0.58 on floor-plan blocks, against 0.87 on legend drawings (arXiv 2610.09313, Table 20).

- What: Do not use a stock or legend symbol as the template; cut it from the plan itself.
- Evidence (floor-plans): F1 falls from 0.87 to 0.38 (0.54 oracle threshold) when the reference comes from a library (arXiv 2610.09313); a master's thesis on electrical diagrams gets recall 0.70 but F1 0.52 with legend templates over the whole sheet and 0.73 on proposed regions, bottleneck is clean-legend vs drawn-instance appearance (stroke, scale).
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: none
- Experiment: Do not run; if tested anyway, compare same-plan template against a template from another dev plan of the same style.
- What breaks on our images: Our plans vary in stroke width and scan quality, so any shared template is the library case.
- Moves: windows-doors. Why this group: Measured failure; same-plan exemplar is the fix.
- Also (data, our-idea): Own-drawn fixture glyph bank for a commercial-safe set. Draw our own toilet, sink, shower, bathtub and sauna-stove glyph variants (several line weights) for any generated set meant to be shipped; crops from dev images make the weights non-commercial-derived. Evidence: Our own proposal (combination, no paper): No real commercial-safe set with our fixture classes exists; generator glyph shapes are Singapore-listing fitted; ResPlan has no fixtures. Source: none. Experiment: Train with own glyphs vs dev crops, read per-class on dev.
- Also (data, search-only): Cheap crop library from a drawing's legend. Where a plan has a legend, cut its symbol keys as a crop library for template matching or contrastive classification of detected symbols. Evidence: Contrastive learning from the unique entries of a diagram legend to classify symbols (Hain et al., ECML-PKDD 2025, abstract only); Chalmers 2026 thesis uses the same legend idea on electrical diagrams. Source: none. Experiment: Count plans with a legend on dev; test legend crops as template exemplars.
- Also (vector, adjacent-field): Template retrieval and fit for repeated symbols. Match a canonical template to each symbol instead of classifying primitives. Evidence: TempFit (2610.17776): greedy PQ 86.2 below SymPoint-V2 90.1 and VecFormer 91.1; vector input only. In-house: canonical swing template exact doors 3/40, Hough arcs 2/40. Source: [arXiv 2610.17776](https://arxiv.org/abs/2610.17776). Experiment: None on raster.
- Reports: lit-count-a, lit-data-a, lit-data-b, lit-data-c, lit-vector-a, lit-vector-c

<a id="i182"></a>
### 182. Do not count doors and windows by vectorising first and applying rules

- What: Keep a learned box detector as the counter. Do not spend hours on a line-first counter for doors, windows or fixtures.
- Evidence (floor-plans): No paper reports door, window, toilet or sink counts from a vectorise-then-rules route. Where both routes share a table, the learned detector wins: SESYD instance F 97.9-99.1 (CNN) vs 75.5-85.3 (classical); P&ID symbols 86.58 modular-learned vs 73.49 end-to-end; ICCV 2017 openings 91.9 vs 61.3 accuracy.
- Source: [arXiv 2504.03241](https://arxiv.org/html/2504.03241v1), [arXiv 2508.10449](https://arxiv.org/html/2508.10449)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0 h (decision)
- Experiment: None needed; if someone insists, score a line-based door count against the detector count on dev only and require it to beat exact-match of the detector.
- What breaks on our images: Rules over about 1000 segments per image, 57-64% under 20 px, mostly text, hatching and symbol outlines.
- Moves: none. Why this group: No evidence it beats direct detection; several results point the other way
- Also (vector, floor-plans): Vectorise-then-classify models collapse on scans (cautionary result). Do not adopt region-graph (Zernike moments plus GNN) parsers for scanned inputs. Treat the numbers as a warning when anyone proposes a vectorise-first front end. Evidence: arXiv 2504.03241: clean CubiCasa5K window F1 98.3 and door F1 93.2; on 122 scanned plans window 7.2, door 2.1; average F1 94.6 clean vs 23.8 scans (Table 1). Trained on CubiCasa5K only. Source: [arXiv 2504.03241](https://arxiv.org/html/2504.03241v1). Experiment: None; use as a reference when reviewing any vectoriser proposal.
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i183"></a>
### 183. Median or vote over several VLMs

- What: Do not rely on combining frontier VLMs by median or vote.
- Evidence (floor-plans): Door 0.433 best single to 0.458, window unchanged; oracle of any-of-four 0.70/0.66 (computed from AECV CSVs).
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: No signal selects the right model without ground truth.
- Moves: trust. Why this group: no gain
- Reports: lit-floorplan-a

<a id="i184"></a>
### 184. Global count head next to the detector

- What: Add a density or count-level head as a sanity check on the per-page total.
- Evidence (adjacent-field): Microscopy decoupled counter/localizer: MAE down 63.6% on one set (arXiv 2503.13989); DQ-DETR classifies count level 4 buckets, AP 30.2 vs 25.9 on AI-TOD-V2.
- Source: [arXiv 2503.13989](https://arxiv.org/abs/2503.13989), [arXiv 2404.03507](https://arxiv.org/abs/2404.03507)
- Licence: DQ-DETR repos have no licence; microscopy code not found. CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Not before baseline.
- What breaks on our images: Reports MAE not exact rate; no class-specific counting; blobs not line art.
- Moves: trust. Why this group: Second counter signal
- Also (count, adjacent-field): Density-map counters. Do not use density maps. Evidence: Exact match 0.01-0.38; our count-only FCN 18% on windows/doors. Source: [arXiv 2512.15254](https://arxiv.org/abs/2512.15254). Experiment: None; our own count-only network stayed at 18% on windows and doors.
- Also (count, adjacent-field): Dots. Dot density blurs neighbours. Evidence: CellFMCount 430,000 cells (arXiv 2511.19351). Source: [arXiv 2511.19351](https://arxiv.org/abs/2511.19351). Experiment: None.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-detect-a, lit-detect-b

<a id="i185"></a>
### 185. DQ-DETR count bands

- What: Not an exact counter.
- Evidence (adjacent-field): Bins <10, 10-100, 100-500, more (arXiv 2404.03507).
- Source: [arXiv 2404.03507](https://arxiv.org/abs/2404.03507)
- Licence: no licence. CubiCasa5K leakage: no.
- Cost: none
- Experiment: None.
- What breaks on our images: It classifies four count bands only to set the number of queries; not an exact counter.
- Moves: none. Why this group: Coarse.
- Reports: lit-count-a, lit-count-c

<a id="i186"></a>
### 186. SAM 3 with box exemplars as a counter

Reviewer's note: SAM 3's licence rules it out for shipped code (Tudor's triage), and negative exemplars on a frozen SAM 3 measured worse.

- What: Prompt SAM 3 with same-plan box exemplars, count masks above 0.5 after IoM suppression.
- Evidence (adjacent-field): CountBench 94.0% exact, PixMo-Count 86.3% (counts 2-10, photos, internal checkpoint, arXiv 2511.16719 Table 37); aerial DIOR text 11.67 vs box exemplar 66.55 mAP; texture-less parts F1 0.156-0.507 (arXiv 2602.20551); no drawing result.
- Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719), [github.com](https://github.com/facebookresearch/sam3)
- Licence: custom SAM License (not MIT/BSD/Apache); gated weights. CubiCasa5K leakage: unknown.
- Cost: 3-4 h including access request (estimate); 5-6.5 GB inference
- Experiment: If the licence call allows it: 40 dev plans with exemplars, exact rate vs detector.
- What breaks on our images: 1008 px input, 200-query cap, group vs cell masks, line symbols without texture; checkpoint access requests are often rejected.
- Moves: windows-doors. Why this group: Custom licence and no drawing result.
- Also (count, adjacent-field): Negative exemplars on a frozen SAM 3. Do not assume negative exemplars help SAM 3. Evidence: Adding 1, 3 or 5 negatives lowered mIoU and often collapsed the mask to background on PASCAL-5i and COCO-20i (arXiv 2604.05433); frozen SAM 3 does not honour negatives (CASE, reported in lit-count-c). Source: [arXiv 2604.05433](https://arxiv.org/abs/2604.05433). Experiment: Not run. If SAM 3 is licence-cleared, start with positive-only exemplars and add negatives only after a measured gain.
- Also (market, authors-claim): Exemplar-based finding of every matching symbol with SAM 3. Test whether one example symbol finds the others on a plan before training anything. Evidence: SAM 3 abstract: concept prompt by noun phrase, exemplar or both; accuracy on 5 to 20 px line-art symbols not measured. Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719). Experiment: Run on 20 dev plans with one exemplar window; settle with recall on windows.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-market-b

<a id="i187"></a>
### 187. P2PNet/PET point counters

- What: Skip licence-restricted point counters.
- Evidence (adjacent-field): P2PNet academic only; PET README academic.
- Source: [arXiv 2308.13814](https://arxiv.org/abs/2308.13814)
- Licence: restricted. CubiCasa5K leakage: no.
- Cost: none
- Experiment: None.
- What breaks on our images: P2PNet licence clause allows academic research only; PET README says academic purposes only.
- Moves: none. Why this group: Licence.
- Reports: lit-count-a, lit-count-b, lit-count-c

<a id="i188"></a>
### 188. Relative thresholds cannot answer zero

- What: Avoid thresholds relative to the best box.
- Evidence (adjacent-field): GeCo2 demo keeps boxes above best score x 0.33; always returns one.
- Source: [github.com](https://github.com/jerpelhan/GECO2)
- Licence: MIT. CubiCasa5K leakage: no.
- Cost: none
- Experiment: Check zero-count plans: count must be able to return 0 for windows, doors and fixtures; use an absolute threshold.
- What breaks on our images: A plan with no window still returns one.
- Moves: windows-doors. Why this group: Zero counts exist.
- Reports: lit-count-a

<a id="i189"></a>
### 189. Fine-tuned VLM writing a count as text

- What: Do not train direct count text.
- Evidence (adjacent-field): 14-17% exact FSC-Test (2604.10039).
- Source: [arXiv 2604.10039](https://arxiv.org/abs/2604.10039)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None.
- What breaks on our images: n/a
- Moves: none. Why this group: Weak.
- Reports: lit-vlm-c

<a id="i190"></a>
### 190. Untrained tag and crop loops for counting

- What: Do not expect gains.
- Evidence (adjacent-field): Mostly fail (2610.27756).
- Source: [arXiv 2610.27756](https://arxiv.org/abs/2610.27756)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None.
- What breaks on our images: n/a
- Moves: none. Why this group: Measured.
- Reports: lit-vlm-b, lit-vlm-c

<a id="i191"></a>
### 191. Count-only supervision

- What: Do not use count-only training.
- Evidence (adjacent-field): WS-COC MAE 13.91 vs 5.7-8.7 (arXiv 2602.12774).
- Source: [arXiv 2602.12774](https://arxiv.org/abs/2602.12774)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: none
- Experiment: None; box labels already exist next to the counts, so weak supervision adds nothing.
- What breaks on our images: Trained on 80 GB GPUs in the paper; MAE on photos only.
- Moves: none. Why this group: Box labels exist.
- Reports: lit-count-a, lit-count-c

<a id="i192"></a>
### 192. Enumerate objects before counting

- What: Listing every door and window before counting added nothing significant.
- Evidence (authors-claim): +1.3 points, interval [-1.5,+4.2] (PR 3 paired bootstrap, reported by an interested party).
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench/pull/3)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Claim from a party tied to the prompt.
- Moves: none. Why this group: not shown to help
- Reports: lit-floorplan-a
