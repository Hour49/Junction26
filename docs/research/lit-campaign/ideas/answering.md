# Answering questions

9 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i373"></a>
### 373. Refuse a sheet and say why

- What: Per sheet, output 'not read because: scale missing, image too small, several scales, unreadable symbols' instead of a number.
- Evidence (adjacent-field): BuildVision docs: 'Scale needed' list and what prevented measurement; Houzz marks pages not eligible for AI; Handoff 'flags its assumptions'.
- Source: [docs.buildvisionai.com](https://docs.buildvisionai.com/takeoff/ai-detection)
- Licence: closed. CubiCasa5K leakage: n/a.
- Cost: 3 h (estimate)
- Experiment: Count how many dev sheets fall in each refusal reason and the exact rate on the rest.
- What breaks on our images: The refusal rules must be tuned on dev or they refuse too much.
- Moves: trust. Why this group: the pipeline already refuses; make the reason visible
- Also (count, adjacent-field): Refuse plans that were not readable. Gate: classify a plan as countable or not and answer only the countable ones. Evidence: AgentCount 49 of 57 plates (86.0%) classed correctly; takeoff vendor returns counts at confidence at least 50%. Source: [arXiv 2611.05398](https://arxiv.org/abs/2611.05398). Experiment: Tie the gate to count-distribution mass; measure exact rate of answered vs refused.
- Reports: lit-count-a, lit-count-b, lit-market-a, lit-market-c

<a id="i374"></a>
### 374. Report counts and room ratios separately from absolute areas

- What: Tell users counts and ratios do not depend on scale; flag only metric answers.
- Evidence (authors-claim): BuildVision docs; Sadeh et al.: counts 11/13 identical, areas -1 to -11%.
- Source: [buildvisionai.com](https://www.buildvisionai.com/docs/takeoff/calibration), [easychair.org](https://easychair.org/publications/paper/pkrRp/download)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Areas bias also from segmentation.
- Moves: trust. Why this group: 67.3% of questions are counts.
- Reports: lit-scale-b

## Try next

<a id="i375"></a>
### 375. Door detector in front of an LLM lifts exact counts, most on scans

- What: Feed detector output into a language model with chain-of-thought and compare exact counts with the model alone.
- Evidence (floor-plans): arXiv 2509.17283: toilet exact count GPT-5 alone vs detector plus CoT: CVC-FP scans 40.0 vs 86.7, SESYD 68.8 vs 95.8, CubiCasa5K 85.6 vs 87.6. Detector trained on public door sets (leak possible).
- Source: [arXiv 2509.17283](https://arxiv.org/abs/2509.17283)
- Licence: commercial LLM; detector Co-DETR (MIT). CubiCasa5K leakage: unknown.
- Cost: 4 h plus API cost (state cost first)
- Experiment: On 30 dev plans compare model alone vs detector-fed; settle by exact-match gain.
- What breaks on our images: Counts are of rooms, not symbols; commercial LLM per image.
- Moves: windows-doors. Why this group: Supports detector-first design; adds API cost
- Also (count, adjacent-field): Count the length of the point list, never the number a model writes. For any VLM counter, ask for the list of points or records and count them in code; discard the stated total. Evidence: Counting coordinates in code: 80.2-97.9% vs 19.4-97.3% for the model's own answer on out-of-range synthetic counts (arXiv 2603.21746, Table 2); decode-and-count cuts count error 71-84% with no extra call and 85-99% with one (arXiv 2610.25503, synthetic scenes). Source: [arXiv 2603.21746](https://arxiv.org/abs/2603.21746), [arXiv 2610.25503](https://arxiv.org/abs/2610.25503). Experiment: Where any VLM answers a count in the pipeline, compare stated vs listed count exact-rate on dev.
- Reports: lit-count-a, lit-vector-a

<a id="i376"></a>
### 376. Enlarge symbols to ~48 px and split views without zooming out

- What: Any VLM look at crops: enlarge symbol to 42-48 px, overlap views by one object, never zoom out; use safe_tiles.py.
- Evidence (adjacent-field): Splits without zoom-out raised recall 0.10-0.46 where S<1.5; zoom-out lowered it in 19 of 21 settings (arXiv 2610.09313).
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: code MIT. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Use in the VLM check experiment.
- What breaks on our images: Our symbols are at S~0.15-0.6 in a whole-page call; 2-10x upscale needed.
- Moves: trust. Why this group: design rule for any VLM step
- Reports: lit-floorplan-a, lit-floorplan-b, lit-floorplan-c

## Later

<a id="i377"></a>
### 377. Give the answering stage an explicit recovered structure instead of pixels

- What: Hand the downstream rule layer or model detected objects with geometry instead of the raw image.
- Evidence (adjacent-field): 2609.05880: small VLMs answer topology questions 40.1 / 41.3 / 36.7% image-only vs 76.0 / 75.1 / 74.3% graph-grounded. AECV-Bench: direct MLLM exact match on doors 0.39, windows 0.34 at best.
- Source: [arXiv 2609.05880](https://arxiv.org/abs/2609.05880), [arXiv 2601.04819](https://arxiv.org/abs/2601.04819)
- Licence: paper CC BY-NC-ND. CubiCasa5K leakage: no.
- Cost: 4 h
- Experiment: Compare an answering step fed boxes plus coordinates against raw image on dev; score exact match.
- What breaks on our images: Clean line topology in P&ID; our symbols are not graph edges.
- Moves: windows-doors. Why this group: Same direction as every other source
- Also (vector, authors-claim): Detect, vectorise to attributed graph, then rule engine. Build a graph from detected rooms, doors and windows and run rule checks on it. Evidence: 2607.00015: segmentation plus detection to polygons to attributed graph to LLM-parsed rules; no door or window accuracy numbers. 2604.23970: detect doors, link to nearest rooms, self-critic checks BFS connectivity; no accuracy table. Source: [arXiv 2607.00015](https://arxiv.org/abs/2607.00015), [arXiv 2604.23970](https://arxiv.org/abs/2604.23970). Experiment: None.
- Also (vlm, adjacent-field): VLM may only query the detector's graph. Expose detections as read-only queries; the VLM answers only through them and must cite entities. Evidence: Exact match 36.7-41.3% to 74.3-76.0% (2609.05880). Source: [arXiv 2609.05880](https://arxiv.org/abs/2609.05880). Experiment: Compare with direct counts on dev.
- Also (vlm, authors-claim): Perception tools under an agent (takeoff architecture). Pitch: detectors count, the model reads and checks, as Handoff-H1 does. Evidence: Composite 81.6 vs 61.4 (2608.15032), vendor claim. Source: [arXiv 2608.15032](https://arxiv.org/abs/2608.15032). Experiment: Cite as support only.
- Reports: lit-vector-a, lit-vlm-a, lit-vlm-b, lit-vlm-c

## Idea or pitch only

<a id="i378"></a>
### 378. Answer odd questions by running code over extraction_v1

- What: For unusual questions, let an agent explore the extraction JSON at run time instead of a fixed prompt.
- Evidence (adjacent-field): IFC-Bench v2: adaptive 56.0% against static 19.1% on 514 questions; static abstains 43% to 55%, adaptive 6% or fewer.
- Source: [arXiv 2605.01698](https://arxiv.org/abs/2605.01698)
- Licence: data CC BY 4.0; code NOASSERTION. CubiCasa5K leakage: n/a.
- Cost: 1 to 2 days (estimate)
- Experiment: Compare fixed templates with an agent on dev question types outside the golden set.
- What breaks on our images: Our questions are fixed-rule counts.
- Moves: demo. Why this group: rules already answer them
- Reports: lit-market-a, lit-market-b

<a id="i379"></a>
### 379. Write detector boxes into the VLM prompt

- What: List boxes as text so the VLM counts the list.
- Evidence (adjacent-field): GroundCount: +6.2 to 7.5 points on yes/no counting for four of five VLMs (arXiv 2603.10978).
- Source: [arXiv 2603.10978](https://arxiv.org/abs/2603.10978)
- Licence: YOLOv13 AGPL. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Not needed while counts are made in code; only if a VLM answers free text, test boxes-in-prompt against boxes drawn on the image.
- What breaks on our images: Metric was yes/no VQA, not exact count; low-confidence boxes hurt.
- Moves: none. Why this group: Code counts already.
- Reports: lit-count-b, lit-count-c

<a id="i380"></a>
### 380. Pipeline shape: detector, assembly rules, VLM only as checker

- What: Keep extraction_v1 then rules; VLM answers only from extracted structure.
- Evidence (adjacent-field): Graph-grounded harness 36.7-41.3% to 74.3-76.0% exact; FlowExtract node F1 98.8 on 25 training images; SINA 96.47% netlist.
- Source: [arXiv 2609.05880](https://arxiv.org/abs/2609.05880), [arXiv 2604.06770](https://arxiv.org/abs/2604.06770), [arXiv 2601.22114](https://arxiv.org/abs/2601.22114)
- Licence: mostly AGPL YOLO. CubiCasa5K leakage: n/a.
- Cost: n/a
- Experiment: Already our shape.
- What breaks on our images: Vector-clean images.
- Moves: trust. Why this group: supports current design
- Reports: lit-floorplan-c

## Do not try (with the reason)

<a id="i381"></a>
### 381. A clean BIM does not give a free exact count

- What: Do not assume IFC output makes answers exact.
- Evidence (adjacent-field): IFC-Bench v2: 56.0% adaptive; BIM-Edit 49.5%; BIBIMBAP 50.2%; scan-to-BIM finds doors at 22% volume IoU (BIMStruct3D).
- Source: [arXiv 2605.01698](https://arxiv.org/abs/2605.01698), [arXiv 2606.20146](https://arxiv.org/abs/2606.20146)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: demo. Why this group: measured ceiling
- Reports: lit-market-a, lit-market-b
