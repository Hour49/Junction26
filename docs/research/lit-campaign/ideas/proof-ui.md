# Proof and review interface

20 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i353"></a>
### 353. Bucket the scale quality like Solar imagery_quality

- What: Show HIGH/MEDIUM/LOW by source and a comment which fields depend on scale (areas yes, counts and ratios no).
- Evidence (adjacent-field): Google Solar API proto: imagery_quality, roof area 'unreliable', ground area 'reliable'.
- Source: [github.com](https://github.com/googleapis/googleapis)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: none
- What breaks on our images: none
- Moves: demo. Why this group: UI copy.
- Also (scale, authors-claim): Every scale carries a status, source, mark count and interval. Emit scale as {value, status (scaled / estimated / no_scale / not_to_scale), source (printed dimension pairs, printed bar, printed total, printed opening sizes, prior), marks_used over marks_found, interval}. Prior-only scales are always estimated. Evidence: Pattern in zzTakeoff, Constructable, Kreo, ConstructConnect, Houzz, BuildVision, OpenTakeoff, MicroScale Editor; no vendor publishes a scale error. Source: [github.com](https://github.com/HexNinja555/opentakeoff), [zztakeoff.com](https://www.zztakeoff.com/community/feature-requests/verified-scale-check-trust-indicator). Experiment: Add the fields to the scale output and score status agreement with the existing scale scorer on dev; the number is the share of wrong 'scaled' claims, target zero.
- Reports: lit-scale-a, lit-scale-b, lit-scale-c

## Try next

<a id="i354"></a>
### 354. Per-mark yes/no review on magnified crops

- What: Show each proposed mark magnified, grouped by class, ask yes/no; ask 'how many here (1-4)' per small region for completeness.
- Evidence (adjacent-field): 1.6 s per check, 2.2 s borderline (1602.08405); regions limited to 4 marks (2309.05277).
- Source: [arXiv 1602.08405](https://arxiv.org/abs/1602.08405), [arXiv 2309.05277](https://arxiv.org/abs/2309.05277)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 day for a screen
- Experiment: Timed trial on 20 plans.
- What breaks on our images: Photos not 5-20 px marks; misses invisible to yes/no.
- Moves: demo. Why this group: Defines the human step cost.
- Also (count, adjacent-field): Let the user add a positive or negative exemplar to fix a count. Show the marks, let the user draw a box on a miss (positive) or a false mark (negative) and recount from it. Evidence: SAM 3: +21.6 cgF1 after 3 exemplars (arXiv 2511.16719); ICACount: FamNet MAE 22.08 to 11.75 in 5 two-click rounds (arXiv 2309.05277); no exact-match rate. Source: [arXiv 2309.05277](https://arxiv.org/abs/2309.05277), [arXiv 2511.16719](https://arxiv.org/abs/2511.16719). Experiment: Mock with detector plus template matching on dev: errors fixed per click.
- Also (floorplan, adjacent-field): Human correction of detector boxes. Let a person fix machine marks; measure lift. Evidence: DoorDet: human pass lifted mAP@50 from 0.650 to 0.926; human-machine map vectorisation up to 50% time saved (reported). Source: [arXiv 2508.07714](https://arxiv.org/abs/2508.07714). Experiment: Measure edits per plan.
- Also (rooms, authors-claim): Cheap human correction of merged rooms. Let a person fix flagged rooms. Evidence: Sketch2BIM: first-pass wall recall about 83% to near-perfect after feedback, ten plans. Source: [arXiv 2510.20838](https://arxiv.org/abs/2510.20838). Experiment: Corrections per plan.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-floorplan-b, lit-floorplan-c, lit-rooms-a, lit-trust-b, lit-trust-c

<a id="i355"></a>
### 355. Draw the claimed scale back on the plan

- What: Render a '1 m = N px' bar or door box on the image so the user can see a wrong scale.
- Evidence (adjacent-field): PlanScaling draws 1 m line; OpenTakeoff guide bar; PlotExtract replot-compare.
- Source: [github.com](https://github.com/ilyasab3/PlanScaling)
- Licence: no licence. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: none
- What breaks on our images: none
- Moves: demo. Why this group: Errors are invisible otherwise.
- Reports: lit-scale-a, lit-scale-b, lit-scale-c

<a id="i356"></a>
### 356. Shade uncertain items and withdraw the guarantee on poor images

- What: Shade elements below the threshold and print 'no accuracy statement for this image' when the image is small, rotated or a photo; list shaded items on the first page.
- Evidence (adjacent-field): EagleView sample report: yellow-shaded sections to verify and 'DOES NOT offer an accuracy guarantee' on poor imagery.
- Source: [eagleview.com](https://www.eagleview.com/wp-content/uploads/2025/07/Full-House-Sample-Report.pdf)
- Licence: closed. CubiCasa5K leakage: n/a.
- Cost: 3 h (estimate)
- Experiment: Define an image-quality gate on dev (size, skew, source type) and report exact rate inside and outside it.
- What breaks on our images: Needs a quality score we do not have yet.
- Moves: demo. Why this group: honest refusal as a feature
- Reports: lit-market-c

<a id="i357"></a>
### 357. High, medium, low per element, not a probability

- What: Expose three levels per element so users do not read a number as a guarantee: counted, dotted, listed but not counted.
- Evidence (adjacent-field): Apple RoomPlan: each wall, door, window and opening has a high/medium/low confidence (developer docs).
- Source: [developer.apple.com](https://developer.apple.com/documentation/roomplan/capturedroom/confidence)
- Licence: closed API. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Map detector score to three bands on dev and report exact rate in each band.
- What breaks on our images: No accuracy given there.
- Moves: demo. Why this group: simple and legible
- Reports: lit-market-c

<a id="i358"></a>
### 358. Draw two kinds of mark: counted and check-this

- What: Show high-confidence elements with a solid box and borderline ones with a dotted box; the reviewer works the dotted ones first.
- Evidence (adjacent-field): BoneView FDA K212365: solid and dotted boxes at two operating points; sensitivity 0.928/specificity 0.811 and 0.841/0.932 on 8,918 radiographs; 24 readers, 480 cases.
- Source: [fda.innolitics.com](https://fda.innolitics.com/device/K212365)
- Licence: closed. CubiCasa5K leakage: n/a.
- Cost: 3 h (estimate)
- Experiment: Pick two thresholds on dev and report review workload (dotted marks per plan) against errors caught.
- What breaks on our images: One finding type per image there; we have seven element types.
- Moves: demo. Why this group: cheap UI on top of scores
- Reports: lit-market-c

## Later

<a id="i359"></a>
### 359. Let the user drag a reference line of known length

- What: If no mark is found, show a draggable bar the user stretches over a known length, then recompute areas.
- Evidence (adjacent-field): Chang et al. fallback; CADAiD user line; Planora; PlanMapper.
- Source: [mdpi.com](https://www.mdpi.com/2075-5309/15/7/1178)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Demo only.
- What breaks on our images: none
- Moves: demo. Why this group: Product path.
- Reports: lit-scale-a, lit-scale-b

<a id="i360"></a>
### 360. Keep overlays and flag crowded or edge objects

- What: Store an overlay per plan and flag boxes near other boxes, tile edges or low score for human check.
- Evidence (adjacent-field): AgentCount: 89.7% of counts within 10% on 29 plates, flags for overlap and edge, MAE 4.3 (arXiv 2611.05398); no exact match.
- Source: [arXiv 2611.05398](https://arxiv.org/abs/2611.05398)
- Licence: code MIT. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Dev: share of wrong counts that carry a flag.
- What breaks on our images: Plate photos.
- Moves: trust. Why this group: UI polish.
- Also (trust, adjacent-field): Colour uncertain marks in the review screen. Colour mark borders by uncertainty and mark counter disagreement. Evidence: 7.2% faster and +0.70 mIoU, 120 participants, benefit grows with difficulty (2605.12303). Source: [arXiv 2605.12303](https://arxiv.org/abs/2605.12303). Experiment: A/B test.
- Reports: lit-count-b, lit-trust-a, lit-trust-b, lit-trust-c

<a id="i361"></a>
### 361. Show flagged plans also without the detector overlay

- What: Offer an overlay-free view or candidate-miss overlay so reviewers do not inherit misses.
- Evidence (adjacent-field): Half-removed boxes raised count error to 2.2 (2401.17821).
- Source: [arXiv 2401.17821](https://arxiv.org/abs/2401.17821)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Timed trial.
- What breaks on our images: Crowd workers on fish.
- Moves: demo. Why this group: Design rule.
- Reports: lit-trust-a

<a id="i362"></a>
### 362. Seed known-wrong plans into the audit stream

- What: Insert plans with known errors into the surveyor's stream to measure miss rate under low prevalence.
- Evidence (adjacent-field): Rare targets missed 30-40% at 1-2% prevalence (2010 low-prevalence study).
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC3064483/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Trial with planted errors.
- What breaks on our images: Lab letters.
- Moves: demo. Why this group: Measures the reviewer.
- Reports: lit-trust-c

<a id="i363"></a>
### 363. Reveal the machine's total only after the reviewer counts

- What: Show marked objects first, let the person count, then reveal the total, to reduce automation bias.
- Evidence (adjacent-field): Dratsch 2023: inexperienced readers' correct ratings fell from 79.7% to 19.8% when a (mock) AI suggestion was wrong; 27 readers, 50 mammograms.
- Source: [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/37129490/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Part of the reader-study experiment.
- What breaks on our images: Small, mock AI.
- Moves: trust. Why this group: design rule
- Reports: lit-market-c

<a id="i364"></a>
### 364. Two scores per count: is the count right, is the pointer right

- What: Score the count and the location of each evidence mark separately, and show both.
- Evidence (adjacent-field): VERDICT abstract: AUROC 0.730 to 0.914 (value) and 0.681 to 0.906 (evidence); about 120 labelled items recover evidence confidence from 0.641 to 0.905 after a shift.
- Source: [neurips.cc](https://neurips.cc/virtual/2026/164940)
- Licence: code unknown. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Label 120 marks as correct or not on dev and check whether a mark-level score separates them (AUROC above 0.8).
- What breaks on our images: Shown on text fields only; symbols would need localisation.
- Moves: trust. Why this group: abstract-level evidence
- Reports: lit-market-c

<a id="i365"></a>
### 365. Make the review a gate: a count enters the answer only after it is accepted

- What: Hold detections as proposals until a person accepts them; keep them out of the totals until then.
- Evidence (authors-claim): Autodesk Takeoff: results evaluated on the sheet before accepting; OpenTakeoff keeps agent output as a dashed proposal; Takeoff-Lens keeps accepted, rejected, uncertain sets.
- Source: [autodesk.com](https://www.autodesk.com/blogs/construction/autodesk-takeoff-one-year/)
- Licence: Autodesk closed; OpenTakeoff AGPL pattern only; Takeoff-Lens MIT. CubiCasa5K leakage: n/a.
- Cost: 6 h (estimate)
- Experiment: Time a person with and without the gate on 20 plans.
- What breaks on our images: UI only.
- Moves: demo. Why this group: design pattern
- Reports: lit-market-a, lit-market-b

<a id="i366"></a>
### 366. Click one symbol, count the matches, with a similarity slider and deselect

- What: Let the reviewer pick one example and see matches with a similarity slider.
- Evidence (authors-claim): Kreo help (read once, now not found), Procore Matches/Possible Matches, Autodesk symbol detection (90-degree rotation only), pdf2takeoff Scan about 100 ms.
- Source: [support.procore.com](https://support.procore.com/products/online/user-guide/project-level/estimating/tutorials/run-auto-count-takeoffs), [github.com](https://github.com/ajflow/pdf2takeoff)
- Licence: Apache-2.0 for pdf2takeoff. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Compare template matching with our detector on recall of one class.
- What breaks on our images: Clean templates needed; rotation.
- Moves: demo. Why this group: market standard interaction
- Reports: lit-market-a, lit-market-b

<a id="i367"></a>
### 367. Show the detected plan boxes and per-plan counts in the UI

- What: Draw each plan box on the sheet with its counts and let a person drag or delete a box.
- Evidence (our-idea): none; supported by the auditable-count rule in the conclusions.
- Source: none
- Licence: own code. CubiCasa5K leakage: n/a.
- Cost: half a day work
- Experiment: Show that the demo sheet with two plans ends with two boxes and per-plan counts.
- What breaks on our images: Wrong merged boxes would be visible.
- Moves: demo. Why this group: Nice-to-have after the counter exists.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c

## Idea or pitch only

<a id="i368"></a>
### 368. VLM proposes, deterministic gates decide from image evidence

- What: Let a model propose an element, accept it only if image evidence authorises it, and log every step for a reviewer.
- Evidence (floor-plans): SALI-FP: 8,033 of 11,481 proposals accepted, 2,181 plans protected, USD 0.82 per plan; but window IoU 0.05 to 0.23 against 0.72 for a trained model.
- Source: [arXiv 2609.25615](https://arxiv.org/abs/2609.25615)
- Licence: no code released. CubiCasa5K leakage: n/a.
- Cost: 3 days (estimate)
- Experiment: Pattern only.
- What breaks on our images: A VLM parser without trained detectors loses on openings.
- Moves: trust. Why this group: good pattern, poor accuracy
- Reports: lit-market-b

<a id="i369"></a>
### 369. Schematic pipeline: independent VLM pass with agreement score

- What: Show a confidence made from agreement between two independent counters and flag disagreement to a person.
- Evidence (adjacent-field): Circuit-schematic pipeline reports concordance between a detector and an LLM pass (arXiv 2607.01609).
- Source: [arXiv 2607.01609](https://arxiv.org/abs/2607.01609)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: Demo only.
- What breaks on our images: 
- Moves: demo. Why this group: Pattern for the proof UI
- Reports: lit-detect-a

<a id="i370"></a>
### 370. Annotator-prompted DETR

- What: Relate annotator points to the whole image by attention.
- Evidence (authors-claim): WACV 2025: 2.46x faster annotation (search listing).
- Source: [github.com](https://github.com/mburges-cvl/WACV_IAODF)
- Licence: code MIT. CubiCasa5K leakage: no.
- Cost: unestimated
- Experiment: Idea for the label tool: measure seconds per corrected plan with and without point prompts.
- What breaks on our images: One class only; untested at larger patches.
- Moves: demo. Why this group: Annotation speed.
- Reports: lit-count-b

<a id="i371"></a>
### 371. Show a structural plausibility badge in the proof UI

- What: Show a small structural plausibility indicator next to counts when segment statistics disagree strongly with the detector count.
- Evidence (our-idea): Based on own probe: segment statistics correlate 0.5 with counts but never reach exact counts, so it can only flag.
- Source: [github.com](https://github.com/opencv/opencv)
- Licence: Apache-2.0. CubiCasa5K leakage: no.
- Cost: 2 h after the flag exists
- Experiment: None.
- What breaks on our images: Weak signal, false alarms.
- Moves: demo. Why this group: Our own combination of the flag idea with the UI
- Reports: lit-vector-c

## Do not try (with the reason)

<a id="i372"></a>
### 372. Marks with many false positives can hurt

- What: Keep false marks per plan low; a wrong shown suggestion is followed.
- Evidence (adjacent-field): Lehman 2015: no benefit from computer-aided detection in 495,818 mammograms; Dratsch 2023: 79.7% to 19.8% with a wrong suggestion.
- Source: [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/26414882/), [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/37129490/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: trust. Why this group: measured harm
- Reports: lit-market-c
