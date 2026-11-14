# Conflicts between sources

20 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i333"></a>
### 333. Measure how often two counters are wrong together

- What: Before using agreement as a flag, count dev plans where both methods are wrong versus one.
- Evidence (adjacent-field): N-version ML works only if error spaces overlap little (Machida PRDC 2019); same-model agreement rho 0.20-0.59 (2607.08065).
- Source: [arXiv 2607.08065](https://arxiv.org/abs/2607.08065)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Both-wrong share above half of the single-wrong share means agreement is a weak gate.
- What breaks on our images: none
- Moves: trust. Why this group: Decides whether agreement tiers are worth building.
- Reports: lit-trust-c

## Try next

<a id="i334"></a>
### 334. After the detector, show the boxes and ask a VLM for what is missing

- What: Draw the kept boxes on the plan and ask a VLM to count objects with no box, merge its answer as a flag, not as a count.
- Evidence (floor-plans): Per-image exact match toilets on CubiCasa5K 85.57 to 87.63, FloorPlanCAD 79.29 to 85.71, CVC-FP 40.0 to 86.67 with detector plus GPT-5 chain (arXiv 2509.17283); gains on CubiCasa5K are 2-3 images.
- Source: [arXiv 2509.17283](https://arxiv.org/abs/2509.17283)
- Licence: no code released. CubiCasa5K leakage: unknown.
- Cost: paid API or local VLM per plan
- Experiment: Dev subset: flag rate vs real detector errors; keep only if flags catch more errors than they invent.
- What breaks on our images: Detector there was trained on Roboflow door sets (possible CubiCasa5K repackages); VLMs are worst on windows and doors.
- Moves: trust. Why this group: Weak on the classes where it is needed.
- Also (count, adjacent-field): Detect at high recall, then cluster features and drop outliers. Run the detector at a low score threshold, cluster the box features, keep the clusters containing the exemplar. Evidence: DAVE: two-stage detect-and-verify, FSC-147 test MAE 8.66, 25.33 GB (arXiv 2404.16622); mixed-class retraining cut multi-class error 43% but raised plain error 28% for a baseline. Source: [arXiv 2404.16622](https://arxiv.org/abs/2404.16622). Experiment: Own version: same detector at threshold 0.1, cluster crop embeddings per plan, compare exact rate.
- Also (detect, adjacent-field): Independent VLM count with concordance flag. Compare detector counts with an independent second reader and flag mismatches for a person, as in a schematic pipeline. Evidence: Schematic pipeline flags components found by one system and not the other (YOLOv11m mAP 97% on 700 schematics); VLM counts of doors/windows are 0.34-0.39 exact on floor plans (earlier report). Source: [arXiv 2607.01609](https://arxiv.org/abs/2607.01609). Experiment: Not before a baseline.
- Also (floorplan, adjacent-field): VLM yes/no or index answer on detector boxes drawn on upscaled crops. Draw the detector's numbered boxes and ask a VLM per box (yes/no) or by index instead of emitting coordinates. Evidence: RxnCaption: F1 35.4 to 81.0 (Gemini), 0.3 to 57.6 (GPT-4o) with detector boxes; box-wise True/False +12.3% on RefCOCO-type sets; yes/no weak on drawings (0.52-0.67). Source: [arXiv 2511.02384](https://arxiv.org/abs/2511.02384), [arXiv 2509.09958](https://arxiv.org/abs/2509.09958). Experiment: Accept/reject precision at coverage vs detector alone; keep only if +3 points.
- Also (vlm, adjacent-field): Detector proposes, small VLM judges enlarged crops. Crop each detector box with padding, enlarge to about 48 px, ask Qwen3-VL-4B yes/no or class, keep or drop the box. Evidence: P&ID mAP 0.728 to 0.925 with simulated errors (2510.03376); no gain over template matching on drawings, 0.83-0.91 vs 0.87 F1 (2610.09313 appendix). Source: [arXiv 2510.03376](https://arxiv.org/abs/2510.03376), [arXiv 2510.13232](https://arxiv.org/abs/2510.13232), [arXiv 2610.09313](https://arxiv.org/abs/2610.09313). Experiment: Exact count with and without verifier on dev; gain over one point is needed to justify calls.
- Reports: lit-count-a, lit-count-c, lit-detect-a, lit-floorplan-c, lit-vlm-a, lit-vlm-b, lit-vlm-c

<a id="i335"></a>
### 335. Training-free union of two systems with an ink gate

- What: Add an element from the second system only if it does not overlap the first and at least half of points sampled along it have a dark pixel nearby.
- Evidence (floor-plans): 2608.25608 Section 6.3: union raised wall F1 from 0.781 to 0.853 (+7.1, interval [5.9, 8.3], n=287); feeding one model's output into the other gave no gain in three forms (Table 7). Electrical-plan DeepLSD run also needed ink-based pre- and post-filtering.
- Source: [arXiv 2608.25608](https://arxiv.org/html/2608.25608)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 2 h work, CPU
- Experiment: Union detector boxes from two different models with the ink gate on dev; accept if exact-match on counts rises over the best single model.
- What breaks on our images: Wall result, not counts; uses CubiCasa5K-trained models.
- Moves: trust. Why this group: Closest precedent for our second-look stage and cheap
- Reports: lit-vector-a, lit-vector-c

<a id="i336"></a>
### 336. Stage-8 second count by agreement of independent recognisers, not render-and-compare

- What: Use two or more detectors with different architectures and training halves as voters; accept a count when most agree and abstain otherwise. Do not use pixel round-trip as the check.
- Evidence (adjacent-field): VERDICT (2608.22183): agreement of 4 recognisers separates right from wrong with AUROC 0.916 vs 0.666 single-model confidence and 0.547 pixel round-trip; gate 3 of 4 keeps 52.1% of images at precision .985. ViCoR: a small VLM compares source and render, ACS 71.9 to 89.7.
- Source: [arXiv 2608.22183](https://arxiv.org/abs/2608.22183), [arXiv 2609.33603](https://arxiv.org/abs/2609.33603)
- Licence: repo 404 / not released. CubiCasa5K leakage: no.
- Cost: 4 h work plus a second detector (estimate)
- Experiment: Train two detectors on different halves and architectures; on dev, compare exact-match precision of agree-gated counts against single-model confidence and report coverage.
- What breaks on our images: Chemistry domain; needs two detectors; commercial backbones in some variants.
- Moves: trust. Why this group: Evidence-backed design for the second count
- Also (count, our-idea): Trust signal: agreement of two independent counters. Report a count with high confidence only when the detector and the second counter agree; otherwise flag. Evidence: Template matching is exactly right on 50% of small views, so agreement is the only route to confidence (lit-count-a); surgical counting still off by about one even fine-tuned (arXiv 2602.11024). Source: [arXiv 2602.11024](https://arxiv.org/abs/2602.11024). Experiment: 40 dev plans: exact rate among agree vs disagree. Keep stage 8 only if agree plans are clearly more exact; kill if 95% vs 90%.
- Also (detect, our-idea): Two detector families as a disagreement flag. Run the RF-DETR and D-FINE models on every plan and flag plans where their per-class counts differ; use as a signal for the second count, not as proof. Evidence: Errors are partly correlated because labels are shared (estimate); disagreement is a free signal. Source: none. Experiment: On dev: accuracy of the count when models agree vs disagree; does template matching side with the right one.
- Also (floorplan, adjacent-field): Accept a count only when independent counters agree. Compare detector, template matching and VLM check; route disagreement to review. Evidence: Agreement of four recognisers AUROC 0.916 vs re-render similarity 0.547 (VERDICT, abstract-level). Source: [arXiv 2608.22183](https://arxiv.org/abs/2608.22183). Experiment: Precision at coverage on dev.
- Also (sheet, our-idea): Disagreement between plan-box count and element-cluster count as a conflict signal. Flag a sheet when the plan detector's count and the element-cluster count differ. Evidence: none published; BlueprintAgent uses conflicts to trigger a revisit. Source: [arXiv 2609.07362](https://arxiv.org/abs/2609.07362). Experiment: Check on dev whether flagged sheets have a higher plan-count error.
- Also (trust, adjacent-field): Release tiers by agreement of architecturally distinct counters. Run 3-4 counters that differ in architecture or resolution, normalise answers to counts per type per plan, release by number of agreeing counters, human-check a sample of released plans. Evidence: Agreement AUROC 0.916; 3 of 4 accepted 52.1% at 98.5% precision; 2 of 4 81.7% at 88.8% on 263 depictions (2608.22183); two OCRs plus a dictionary left 99.74% right among unflagged (reCAPTCHA). Source: [arXiv 2608.22183](https://arxiv.org/abs/2608.22183). Experiment: Count dev plans where both counters are wrong, one wrong, none; then build the tiers and compare precision per tier.
- Also (vlm, adjacent-field): Ask the big model only on disagreement. Cheap detector first; call the VLM only where two views or two models disagree on a count. Evidence: GroundCascade saves 74% of 32B calls for 22 lost answers of 1,581 (2611.13177). Source: [arXiv 2611.13177](https://arxiv.org/abs/2611.13177). Experiment: Count how often detector and tile-VLM disagree on dev and what the VLM fixes.
- Reports: lit-count-a, lit-count-c, lit-detect-c, lit-floorplan-c, lit-sheet-a, lit-trust-c, lit-vector-b, lit-vlm-c

<a id="i337"></a>
### 337. Free cross-checks: printed areas, legend, window counts per room, plan count

- What: Compare printed room areas with measured ones (warn above 3%), room types with the legend, window counts per room with the sheet total, plan count with title blocks, and show which check cleared an element.
- Evidence (adjacent-field): Rossum: four validation sources per field incl. data-integrity checks; roomgraph (MIT): printed area against measured area, warn above 3%; Veryfi arithmetic check.
- Source: [knowledge-base.rossum.ai](https://knowledge-base.rossum.ai/docs/guide-to-automation-process-in-rossum), [github.com](https://github.com/aec-platform/roomgraph)
- Licence: roomgraph MIT, provenance unclear; Rossum closed. CubiCasa5K leakage: n/a.
- Cost: 4 h (estimate)
- Experiment: Count how often each check fires on dev and whether firing predicts an error.
- What breaks on our images: Many plans print few areas; symbol counts have no arithmetic relation.
- Moves: scale-areas. Why this group: works without a calibrated detector
- Reports: lit-market-b, lit-market-c

<a id="i338"></a>
### 338. Plan count from three independent counters, flag when they disagree

- What: Count plans by box detector, by OCR'd floor words and by connected components of ink; trust the count when they agree, flag the sheet otherwise.
- Evidence (adjacent-field): Biomedical figures: exact panel count right in 11,973 of 13,147 figures (91.07%), 9,294 of them by consensus of three counters.
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC3856606/)
- Licence: article CC BY 2.0; no code. CubiCasa5K leakage: no.
- Cost: 3 h work after the detector exists
- Experiment: Measure exact plan count among agreed sheets versus flagged sheets; plot error against discard fraction.
- What breaks on our images: Floor-title words depend on OCR; plans have no panel letters.
- Moves: trust. Why this group: Same shape as the stage-8 second counter and cheap once the parts exist.
- Reports: lit-sheet-b

<a id="i339"></a>
### 339. Two structurally different readings of one plan, disagreement as a feature

- What: Count the plan twice with different mechanisms (detector vs rule or VLM; whole plan vs per room) and use disagreement.
- Evidence (adjacent-field): Second reading was the largest single ablation step, +1.7 AUC points (2606.24420); detector plus geometry verification beat text confidence (2601.11644).
- Source: [arXiv 2606.24420](https://arxiv.org/abs/2606.24420), [arXiv 2601.11644](https://arxiv.org/abs/2601.11644)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 3 h work
- Experiment: Add to the classifier and measure the gain.
- What breaks on our images: Shared failures.
- Moves: trust. Why this group: Cheap if two readings exist.
- Reports: lit-trust-b, lit-trust-c

<a id="i340"></a>
### 340. Plausibility rules as a second, cheap validity filter

- What: Write rules across answers (openings vs rooms, counts per room vs total, symbols on walls) and use them to remove false agreements and raise flags.
- Evidence (adjacent-field): Substance filter removed 2,193 false agreements; rules flagged real errors in 88-100% of samples but caught 12.5% of human-label errors (2003.01668); our stage 8 found 0 of 14 conflicts and 0 false alarms on 102 agree entries (docs/PIPELINE.md).
- Source: [arXiv 2003.01668](https://arxiv.org/abs/2003.01668), [arXiv 2608.22183](https://arxiv.org/abs/2608.22183)
- Licence: code Apache-2.0 (model assertions). CubiCasa5K leakage: n/a.
- Cost: 4 h work
- Experiment: Measure precision and recall of each rule on dev; use rules to flag, never to certify.
- What breaks on our images: Low recall; silent rules prove nothing.
- Moves: trust. Why this group: Free signal, high precision.
- Reports: lit-trust-b, lit-trust-c

## Later

<a id="i341"></a>
### 341. Constraint layer over detections: openings sit on walls, no two overlap

- What: Apply geometric consistency rules (opening lies on a wall, openings do not overlap, count within plausible range) to detector output, in about 50 lines with shapely.
- Evidence (floor-plans): R2V (ICCV 2017, 100 plans, 256 px): opening accuracy 67.9 to 91.9 and icon accuracy 22.3 to 84.0 with the integer-programming layer, opening recall 91.4 vs 90.2. CPN-Floor (2025, abstract only): learned key points plus axial-alignment rules, over 87% precision and 88% recall.
- Source: [github.com](https://github.com/art-programmer/FloorplanTransformation)
- Licence: R2V code MIT; weights on Drive, no terms. CubiCasa5K leakage: no.
- Cost: 4 h work (estimate)
- Experiment: Add the filter after the detector on dev; measure precision, recall and exact count of doors and windows with and without it.
- What breaks on our images: Needs wall geometry we do not have as an output; small recall cost; Manhattan layouts only in the paper.
- Moves: windows-doors. Why this group: Measured precision gain but needs a wall source
- Also (floorplan, adjacent-field): Release a count only if internal consistency holds. Check counts against room list or schedule before releasing. Evidence: TableVision: 99.2% filed with all released columns correct (abstract). Source: [arXiv 2610.17448](https://arxiv.org/abs/2610.17448). Experiment: Precision at coverage.
- Also (sheet, adjacent-field): Chain of cheap named QC measures stored per sheet. Compute several named measurements per sheet (stats, blur, contrast, brightness, stroke width), store all values and masks, thresholds in a config. Evidence: HistoQC pipeline pattern for slides; no accuracy figure on drawings. Source: [github.com](https://github.com/choosehappy/HistoQC). Experiment: Feed the values into the outcome-calibrated gate.
- Reports: lit-floorplan-c, lit-sheet-b, lit-vector-a, lit-vector-c

<a id="i342"></a>
### 342. Propose with template matching, accept or reject each crop with a small VLM

Reviewer's note: The 0.87 F1 quoted below is on 34 legend drawings. On the same paper's floor-plan blocks (arXiv 2610.09313, Table 20: 339 test items, 21 classes) template matching gets 0.58 and the trained exemplar counters 0.19 and 0.34. Expect the lower figure on plans.

- What: Candidate crops from template matching (or from a low-threshold detector) go to a VLM that answers 'is this the same symbol'; count the accepted ones. Two-stage shape: cheap proposer, verifier.
- Evidence (floor-plans): LegendSpot: propose-and-verify with eight VLMs F1 0.83-0.91, none significantly different from plain template matching; candidate ceiling 0.98 so the verifier is the loss (arXiv 2610.09313). Chalmers thesis: proposer recall up to 95.4%, then classification against the legend (F1 0.73).
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: depends on the VLM; Qwen3-VL small sizes Apache-2.0 (per earlier report). CubiCasa5K leakage: unknown.
- Cost: 2-4 h on top of template matching (estimate)
- Experiment: Run on the disagreement cases of the two detectors only; measure whether the verifier fixes the count more often than it breaks it.
- What breaks on our images: Small open VLMs are weak on 5-20 px crops (frontier models 0.9, small open models far lower); adds latency.
- Moves: trust. Why this group: No measured gain over plain template matching.
- Also (count, adjacent-field): Accept or reject each proposal against a stock reference embedding. Keep a canonical symbol crop per class and accept proposals whose embedding matches, reject look-alikes. Evidence: RECOUNT: CountGD plus a reference-based filter LookAlikes MAE 8.41, PairTally 39.96 (arXiv 2608.20621), training one epoch on one H100; needs a diffusion step. Source: [arXiv 2608.20621](https://arxiv.org/abs/2608.20621). Experiment: Cheap version: embed dev crops of a class, accept detector boxes within a distance, compare error against raw detector.
- Reports: lit-count-a, lit-count-b, lit-count-c

<a id="i343"></a>
### 343. Re-crop and re-run on a conflict

- What: When two counts disagree (plan box count against element clusters), re-crop that region at 2x, re-run the detector and keep the result only when it resolves the conflict; the MLLM-per-conflict version is out of scope.
- Evidence (adjacent-field): Structural blueprints: beam F1 0.994 against 0.301 single-pass MLLM and 0.820 fixed pipeline on 300 sheets; ablations: without axis-aware crop 0.674, without a cheap span-ratio check 0.828.
- Source: [arXiv 2609.07362](https://arxiv.org/abs/2609.07362)
- Licence: none found. CubiCasa5K leakage: n/a.
- Cost: 3 h work
- Experiment: Flag sheets by disagreement, re-run at 2x, and compare exact counts before and after on the flagged slice.
- What breaks on our images: Authors' own benchmark near ceiling; needs an MLLM in the paper version.
- Moves: trust. Why this group: After a second count exists.
- Reports: lit-sheet-a

<a id="i344"></a>
### 344. Vote across two different readers (PP-OCR and PARSeq)

- What: Run two reader families on the same crop and accept only agreeing in-table reads, or weight 2:1 for the better one.
- Evidence (adjacent-field): Plates: two models over one +0.31; 2:1 weights +0.04; a third CTC model hurt; PatentOCR shows the better reader differs by domain.
- Source: [arXiv 2607.08896](https://arxiv.org/abs/2607.08896)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h work (estimate)
- Experiment: Report agreement rate and exact match when both agree vs alone.
- What breaks on our images: Plate scoring rule differs from ours.
- Moves: trust. Why this group: after two readers exist
- Reports: lit-ocr-a, lit-ocr-b

<a id="i345"></a>
### 345. Keep a CTC reader as a cross-check against an attention reader

- What: Run an attention recogniser and a CTC recogniser on the same crop and route disagreements to abstain or review.
- Evidence (adjacent-field): Autoregressive decoders snap rare strings to familiar words, 10-18 points below centre on rare strings; only a confidence-routed AR plus CTC ensemble helped (arXiv 2609.00816). Counter-case: a CTC third model hurt a plate vote (arXiv 2607.08896).
- Source: [arXiv 2609.00816](https://arxiv.org/abs/2609.00816), [arXiv 2607.08896](https://arxiv.org/abs/2607.08896)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h work (estimate)
- Experiment: On dev crops count cases where the two readers disagree and which is right; test with and without the closed-vocabulary check.
- What breaks on our images: Plates use fixed 7-character strings; the result may not transfer to 1-4 letters.
- Moves: trust. Why this group: needs two readers first
- Reports: lit-ocr-b

<a id="i346"></a>
### 346. Detect symbols first, mask them out, then check the remaining line map

- What: Detect fixtures and openings, mask them, and use the remaining line work (walls, arcs) as a consistency check on door and window counts.
- Evidence (adjacent-field): P&ID, circuits, flowcharts: symbols are the easy half (FlowExtract node F1 98.8 vs edge F1 66.7; Relationformer vs modular symbols 86.58 vs 73.49; Digitize-PID F1 0.82-0.98). Pattern consistent across SINA, AMSNet, 2609.05880.
- Source: [arXiv 2604.06770](https://arxiv.org/abs/2604.06770), [arXiv 2411.13929](https://arxiv.org/abs/2411.13929), [arXiv 2609.05880](https://arxiv.org/abs/2609.05880)
- Licence: FlowExtract MIT; others none. CubiCasa5K leakage: no.
- Cost: 4-8 h (estimate)
- Experiment: On dev plans, after masking detected boxes, count remaining door-leaf-like segments; compare with detector count on disagreeing plans only.
- What breaks on our images: Symbols are not graph edges; no exact-count metric in any of these papers.
- Moves: trust. Why this group: Right shape for stage 8 but no measured gain on counts
- Reports: lit-vector-a, lit-vector-b, lit-vector-c

<a id="i347"></a>
### 347. Use a read label as evidence for a fixture symbol inside the room

- What: Treat a WC label as raising the chance of a toilet symbol inside the room, as a stage consistency check rather than a model.
- Evidence (adjacent-field): Adding text primitives lifted CAD panoptic quality 0.7152 to 0.7352 (arXiv 2510.11091, vector input).
- Source: [arXiv 2510.11091](https://arxiv.org/abs/2510.11091)
- Licence: n/a. CubiCasa5K leakage: unknown.
- Cost: 2 h work (estimate)
- Experiment: Compare fixture count error with and without the label prior on dev images.
- What breaks on our images: Paper uses vector input; labels must be read first.
- Moves: fixtures. Why this group: consistency check, small gain in the paper
- Reports: lit-ocr-a

<a id="i348"></a>
### 348. Validators that trigger a local re-read of conflicting regions

- What: Run topology and consistency validators on detections and re-read only the conflicting region with a stronger or different model.
- Evidence (adjacent-field): BlueprintAgent (2609.07362, 300 sheets): beam F1 0.994 with validators vs 0.820 fixed pipeline vs 0.301 single MLLM prompt; gain comes from validators triggering entity-level re-reads, not looping. Structural beams and columns, not doors.
- Source: [arXiv 2609.07362](https://arxiv.org/abs/2609.07362), [arXiv 2608.17237](https://arxiv.org/abs/2608.17237)
- Licence: paper CC BY 4.0, weights not read. CubiCasa5K leakage: no.
- Cost: 6-8 h (estimate)
- Experiment: Implement two validators (opening on wall, count in plausible range) and a re-read with tiled upscaling; measure exact-match on conflicted dev plans.
- What breaks on our images: Commercial multimodal model per sheet; different domain.
- Moves: trust. Why this group: Supports a conflicts stage; no door numbers
- Also (floorplan, adjacent-field): Rule violations trigger a crop re-read. A rule failure (opening without wall, count vs schedule) sends a crop back to the reader. Evidence: BlueprintAgent beam F1 0.994 vs 0.301 single call, 300 scanned sheets (abstract). Source: [arXiv 2609.07362](https://arxiv.org/abs/2609.07362). Experiment: Fraction of errors caught on dev.
- Reports: lit-floorplan-a, lit-floorplan-c, lit-vector-a

<a id="i349"></a>
### 349. Use the second reader's disagreement as an input to conflicts

- What: Feed disagreement between readers and between text route and detector classes into the conflicts stage, not into the count.
- Evidence (our-idea): Triage says the two routes can vote; no paper tests it.
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work (estimate)
- Experiment: Report cases where the two routes disagree and which one dev truth supports.
- What breaks on our images: Needs both routes built.
- Moves: trust. Why this group: after both routes exist
- Reports: lit-ocr-a

<a id="i350"></a>
### 350. Check one-letter labels (K, S, P, H) against room context

- What: A one-letter read counts only if the room context agrees: S with a sauna stove symbol, K with a hob inside, P with a balcony outline.
- Evidence (our-idea): One-letter labels have too few strokes to separate from a furniture symbol; the Finnish legends use K, S, P, H as codes. No measured result.
- Source: [arXiv 2510.11091](https://arxiv.org/abs/2510.11091)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work (estimate)
- Experiment: Count dev rooms where S, K, P reads are right with and without the context check.
- What breaks on our images: Needs symbol detections as evidence; older plans differ.
- Moves: room-types. Why this group: precision rule for the hardest codes
- Reports: lit-ocr-a, lit-ocr-b

## Idea or pitch only

<a id="i351"></a>
### 351. Match doors to the door schedule by tag and ask about the rest

- What: When a sheet has a door schedule, match detected doors to rows and turn mismatches into questions.
- Evidence (authors-claim): OpenTakeoff PRs 638 to 640: confident count plus a list of the rest, pair-vs-single mismatches flagged; no held-out numbers; AGPL; vector PDFs only.
- Source: [github.com](https://github.com/Kentucky-ai/opentakeoff)
- Licence: AGPL-3.0, pattern only. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Count how many dev plans have a schedule and how often counts match it.
- What breaks on our images: Residential raster plans rarely have schedules.
- Moves: windows-doors. Why this group: pattern only
- Reports: lit-market-b

<a id="i352"></a>
### 352. Show only new instances when a revised drawing is re-run

- What: On a revised sheet, match previous detections and show only new or changed ones, as Stoa's own demo does for revisions.
- Evidence (authors-claim): Autodesk blog: no duplicate counts on a revised drawing and new instances notified; Stoa demo: 'Version 6 of the Level 2 plan did not change them'.
- Source: [autodesk.com](https://www.autodesk.com/blogs/construction/autodesk-takeoff-one-year/), [stoabuild.com](https://stoabuild.com/product)
- Licence: closed. CubiCasa5K leakage: n/a.
- Cost: 2 days (estimate)
- Experiment: Idea only: needs plan matching which we do not have.
- What breaks on our images: Needs plan matching.
- Moves: demo. Why this group: not tonight
- Reports: lit-market-a
