# Product, market and pitch

11 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i501"></a>
### 501. Honest one-sentence guarantee with N, bound, source mix and release share

- What: Use the sentence in section 1.3 of the merged report; never state per-plan promises.
- Evidence (adjacent-field): Marginal guarantees say nothing per plan (2208.02814, 2504.07611).
- Source: [arXiv 2208.02814](https://arxiv.org/abs/2208.02814)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Review wording with the numbers.
- What breaks on our images: none
- Moves: demo. Why this group: Public claim must be true.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i502"></a>
### 502. Include reviewer error in the stated guarantee

- What: Say 'marked sure and reviewed' is not 'correct'; quote the measured reviewer miss rate or exclude the reviewer.
- Evidence (adjacent-field): Experts accepted 17% of wrong suggestions; flags did not help (2103.04725).
- Source: [arXiv 2103.04725](https://arxiv.org/abs/2103.04725)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Measure in the timed trial.
- What breaks on our images: Clinical text.
- Moves: demo. Why this group: Free wording.
- Reports: lit-trust-b, lit-trust-c

## Try next

<a id="i503"></a>
### 503. CPU inference timing of the chosen detector

- What: Measure latency on CPU and on the rented GPU with the chosen model; D-FINE-seg ships OpenVINO export and a hw_bench command.
- Evidence (adjacent-field): RF-DETR-S 512 px 374 ms per image on 4 cores OpenVINO; RF-DETR-M 576 px 458 ms on 2 threads (card); 1024 px about 1.5 s per image (estimate); 5,939 files about 2.5 h on CPU.
- Source: [github.com](https://github.com/roboflow/rf-detr)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Time 100 images at the chosen size.
- What breaks on our images: Estimates.
- Moves: cost. Why this group: Ingest cost is a judged criterion
- Reports: lit-detect-a, lit-detect-c

<a id="i504"></a>
### 504. Detector as ingest-once step: cost per page

- What: State that a local 10-32 M parameter detector runs once per drawing at about 0.1-0.2 s per page on a GPU (estimate), so 5,939 files take 10-20 minutes and no per-call model cost.
- Evidence (our-idea): Estimates only.
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: Replace the estimate with a measured number.
- What breaks on our images: Not measured.
- Moves: cost. Why this group: Supports the low-cost criterion
- Reports: lit-detect-c

## Later

<a id="i505"></a>
### 505. Put a price per sheet next to the accuracy

- What: Quote cost per plan next to Werk24 EUR 1.25 per page, Kreo about USD 0.97 per file, Make a BIM EUR 6 for a flat, frontier models 2 to 22 cents, a human redraw at USD 38 per floor.
- Evidence (authors-claim): Pricing pages read 2026-11-14; no takeoff vendor prices per sheet.
- Source: [werk24.io](https://werk24.io/pricing), [kreo.net](https://www.kreo.net/pricing)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h (estimate)
- Experiment: Measure our cost per plan on dev.
- What breaks on our images: Vendor prices change.
- Moves: cost. Why this group: fills an empty cell
- Reports: lit-market-a, lit-market-c

## Idea or pitch only

<a id="i506"></a>
### 506. Few real labelled sheets from a new drawing style close most of the gap

- What: For drawing styles outside the training mix, take 5-10 labelled sheets from the new style and fine-tune or mix them in.
- Evidence (adjacent-field): P&ID: synthetic-only 63.8 edge mAP vs 72.6 with a handful of real sheets (arXiv 2604.16513). 3D parts: 0-shot 95.1 to 10-shot 98.8 mAP50, five real images bridge most (arXiv 2602.21141). Style shift reappears on the next customer's drawings (arXiv 2508.10171).
- Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513), [arXiv 2602.21141](https://arxiv.org/abs/2602.21141), [arXiv 2508.10171](https://arxiv.org/abs/2508.10171)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: hours per style
- Experiment: Hold out one drawing style in dev, add 5 and 10 sheets of it, measure count gain.
- What breaks on our images: Needs labels for the new style.
- Moves: demo. Why this group: relevant for unseen styles in a deployed tool
- Reports: lit-data-b

<a id="i507"></a>
### 507. Product: user confirms which classes a sheet contains

- What: Let a user confirm class presence ('this sheet has a sauna') to adapt or gate the detector; cannot run in scored mode.
- Evidence (adjacent-field): Weak image-level labels raised AP50 34.5 to 36.5 on fog (arXiv 2407.05607).
- Source: [arXiv 2407.05607](https://arxiv.org/abs/2407.05607)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 day product work
- Experiment: Not testable offline.
- What breaks on our images: No labels at answer time.
- Moves: trust. Why this group: only fits an interactive loop
- Reports: lit-data-b

<a id="i508"></a>
### 508. Expose counts as agent tools

- What: Offer counts and evidence through an MCP-style tool surface, which four of six open repos and Togal and Handoff already do.
- Evidence (authors-claim): a round 21: MCP servers on 4 of 6 repos, 62 tools in OpenTakeoff; pdf2takeoff 15 tools.
- Source: [github.com](https://github.com/ajflow/pdf2takeoff)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: none: product idea
- What breaks on our images: Table stakes, not a differentiator.
- Moves: demo. Why this group: expected, not new
- Reports: lit-market-a, lit-market-b

<a id="i509"></a>
### 509. Write IFC from extraction_v1 with IfcOpenShell

- What: Optional export route: write walls, doors, windows and rooms to IFC with an unmodified LGPL library.
- Evidence (authors-claim): IfcOpenShell LGPL-3.0 (record 0006 allows unmodified use); even with a clean IFC an adaptive agent is right 56% of the time (IFC-Bench v2).
- Source: [github.com](https://github.com/IfcOpenShell/IfcOpenShell), [arXiv 2605.01698](https://arxiv.org/abs/2605.01698)
- Licence: LGPL-3.0. CubiCasa5K leakage: n/a.
- Cost: 6 h (estimate)
- Experiment: Write one plan to IFC and read it back.
- What breaks on our images: Only worth it if the demo needs an IFC.
- Moves: demo. Why this group: not needed for counts
- Reports: lit-market-a, lit-market-b

<a id="i510"></a>
### 510. Charge only for accepted results

- What: Show the extracted result first and charge per accepted item.
- Evidence (authors-claim): Make a BIM: EUR 0.10 per object paid after preview; RoomSketcher AI Convert: 5 credits only if saved.
- Source: [makeabim.com](https://makeabim.com/documentation/faq), [roomsketcher.com](https://www.roomsketcher.com/news/roomsketcher-launches-ai-convert/)
- Licence: closed. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: framing
- What breaks on our images: Pricing idea.
- Moves: demo. Why this group: a pitch device
- Reports: lit-market-a, lit-market-c

<a id="i511"></a>
### 511. Human-in-the-loop correction of first-pass openings

- What: Let a person correct detected openings after a first pass.
- Evidence (authors-claim): Sketch2BIM (2510.20838): hand-drawn plans, 10 plans, openings captured reliably in first pass, walls about 83%, all P/R/F1 above 0.83 after feedback; tiny n. Triage: 30-40% lower count error after five two-click rounds on photos.
- Source: [arXiv 2510.20838](https://arxiv.org/abs/2510.20838)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: product work
- Experiment: Not a pipeline test; demo story only.
- What breaks on our images: Ten plans, MLLM-only.
- Moves: demo. Why this group: Weak evidence
- Reports: lit-vector-a
