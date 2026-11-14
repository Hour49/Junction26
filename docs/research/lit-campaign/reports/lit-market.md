# Literature scope L12 `lit-market`: products, BIM route, adjacent products (merged report)

Merged 2026-11-14 from three pass-3 reports (angle a: products that read floor plans or do takeoff; b: research and open tools around the product, BIM route, drawing QA; c: adjacent products and fields). This file replaces an earlier merge. Times are Europe/Helsinki on the same day. Marks: **V** = a report's author opened and read the source; **R** = the vendor's or authors' own claim; **S** = search summary only (kept out of the ranking). "Re-checked HH:MM" means I opened the source again during the merge (01:26 to 01:27). Facts about our task and data (median longest side 855 px, symbols 5 to 20 px, a third of images rotated, 959 sealed eval drawings of which 829 are in CubiCasa5K's train split, baselines 55.3% and 59.3%) come from `docs/research/lit-campaign/worker-brief.md`. Nothing was run; this is reading only.

## 1. Answer

**What is new to a construction-AI CTO.** No construction product publishes an accuracy that is comparable to our exact per-plan counts. Vendors state time saved, an area difference, or a bare "98%" or "99%+" with no metric and no dataset (Togal FAQ, Attentive.ai home page; a). The "98%" was traced to a company executive's spoken statement in trade press, "98% accurate ... Humans were 97% accurate", with no test behind it (a, round 10); the Togal figure "20.4% more accurate" is a 60-student flooring-area exercise, Togal against Bluebeam (Zhao, Lin and Na, European Journal of Education 2025, Crossref abstract; a); the Kansas "up to 76%" is a best case and the control case saved 22% to 23%, with differences of about 5% between two tools after a person corrected the AI output (vendor-hosted page; a). The only independent 2026 study of a takeoff product (Utica, ASC 2026, one commercial building, 29 line items, contractor takeoff as ground truth) found 11 of 13 count items exact after the user reviewed and corrected the AI markups, area items consistently under-estimated, and one door type off by 2 and another by 4 (a, c; easychair.org/publications/paper/pkrRp). Handoff's 81.6 against 77.6 for human estimators uses a 25% tolerance and an LLM judge, the report says counts are over-penalised, and counts are not reported alone (arXiv 2608.15032, abstract re-checked 01:27; a, b, c).

What a CTO has not seen, in any page, paper or repo the three reports opened: (1) exact-match accuracy per class on a sealed split with the counting rules printed; (2) a **calibrated** confidence with a stated coverage ("answers x% of items at y% exact, the rest go to a person"); (3) a measured person-plus-machine result for takeoff (pathology has Ki-67 and MASAI; construction has time savings only); (4) an evidence location for every count in the form Stoa itself shows for text answers ("the document and page behind every sentence", stoabuild.com, a, b); (5) a per-sheet price. Confidence-like signals do ship, so "not sure" per se is not new: Trimble says each count carries a confidence rating and reviewers start with the lowest (vendor blog; 97% of about 300,000 auto-set scales needed no change, 460,000 counts a month; a), Procore has Matches and Possible Matches, Kreo a similarity slider (read once, page now not found), Autodesk lets the user evaluate hits on the sheet before accepting and does not duplicate counts on a revised drawing, BuildVision refuses a sheet and says why, Bobyard, Hustro and MeasureAI say "confidence score" in marketing text. None publishes calibration or accuracy at a coverage (a, c).

**Yardsticks our numbers will be compared with.**

- AECV-Bench (arXiv 2601.04819; 120 plans, exact match per field): paper Table 1, Gemini 3 Pro door 0.39, window 0.34, bedroom 0.89, toilet 0.82 (re-checked 01:27 from the PDF text); recomputed from the repo's per-plan result files (a and b both did this and agree): Gemini 3.5 Flash door 0.433, window 0.392. An open, unmerged pull request from 2026-10-24 reports GPT-6.1 Sol door 0.55, window 0.44 (benchmark prompt) and 0.54 / 0.48 (itemised-inventory prompt); the pull request says most of the gain is the newer model (re-checked 01:27). The paper's "mean" column includes a hidden fifth field, Space: the four shown fields of Gemini 3 Pro average 0.61, not 0.51.
- A trained pixel segmenter reaches about one third of plans exact on CubiCasa5K: door exact on 64 of 190 plans (33.7%) and window on 63 (33.2%), median absolute error 1 (`results/segmentation_count_metrics.json` of the PlanQ-CubiCasa repo, re-checked 01:26: door_exact 64, window_exact 63, n 190; single author, unreviewed). A rule-based engine without a model reaches door 0.108, window 0.117 on AECV-Bench (a, from the author's own results ledger, R). A plan with nine doors needs nine right.
- Price points: Werk24 EUR 1.25 per page by API (EUR 590 a month with 500 pages, then 0.95), EUR 1.56 to 3.73 per page in its Studio app; Kreo API about USD 0.97 per file launch at 500 launches a month; Make a BIM EUR 0.10 per BIM object (EUR 6 for an 80 m2 flat); frontier-model counting 2 to 22 US cents per plan and 20 to 190 s latency (from the AECV-Bench cost and latency columns; a); Togal USD 299 per user per month, Kreo USD 100, 175, 250; a human redraw of one floor at RoomSketcher USD 38 (c). No takeoff vendor publishes a per-sheet price.
- Reference forms from other fields: EagleView 98.77% roof-line accuracy is 1 minus 17.8 ft over 1,452.1 ft summed over 89 lines on one street in Denver, with a per-area error near 3% (CompassData PDF, c); iGUIDE states an error budget (1 cm on wall distance, about 1% on area); Matterport ties accuracy to the job (2, 20, 100 mm).

**What a count cannot hide.** Exact match is harsh. From AECV-Bench's own files (a and b computed the same shape independently): the best model's door count is wrong on 57% of plans, 26% to 31% are off by exactly one, windows have a heavy tail (20% to 29% off by three or more), and every top model undercounts on average; exact match falls with the number of doors (Gemini 3.5 Flash 0.67 at 0 to 5 doors, 0.14 at 16 or more); on the 35 Finnish CubiCasa-style plans of that set the same model gets door 0.29 and window 0.20 (a, round 18).

## 2. Top 10, ranked across all three reports

Hours are estimates and marked. "Breaks" is what would go wrong on our images (median longest side 855 px, symbols 5 to 20 px, a third rotated, scans and phone photos). Leakage means CubiCasa5K or a repackage in the training data of a checkpoint.

**1. AECV-Bench: the exact-count yardstick** (a, b, c). 120 raster plans, models give integers for door, window, bedroom, toilet (the repo adds space); ground truth follows written rules (swing door with arc, each leaf counts, double leaf = 2, adjacent windows with no gap are one group).
- Fills: `elements` (doors, windows) and `rooms` (bedroom, toilet), scored exact.
- Number: Table 1 and the recomputation in section 1; 192 QA pairs with instance counting "the most error-prone" part (Table and text; b). Plans: median width 1,266 px, 100 PNG, 19 JPG, no vector layer; median 9 doors, max 34 (a, from a research note in the pdf2takeoff repo).
- Licence: none. The repo root has no LICENSE file (listing re-checked 01:26: licence field empty); issue #1 asking for one is open. No weights.
- Leakage: likely yes. The paper says a subset was selected from CubiCasa5K and CVC-FP (section 3.1.1); a research note in the pdf2takeoff repo judges 75 of 120 plans look like CubiCasa material (R). Whether any are in our sealed eval is unknown.
- Hours: 0 to cite; about 3 to re-score our pipeline on its rules if we may open the images (estimate). Cost to re-run an API model on 120 plans USD 2.3 to 9.2 (summary JSONs; b).
- Breaks: its rules differ from the dataset's SVG labels and from Stoa's; a third of the plans are under 1,100 px wide, yet ours are smaller still.
- Verdict: **try tonight** as the public number to print next to ours, with the rule difference stated; never copy its images into our repo. Sources: https://arxiv.org/abs/2601.04819, https://github.com/AECFoundry/AECV-Bench. Re-checked 01:26 (abstract), 01:27 (Table 1 line from the PDF), 01:27 (PR #3 body: 0.55/0.44, 0.54/0.48, open, unmerged).

**2. The small-symbol rule: give every symbol about 1.5 visual tokens, overlap views by one object, never zoom out** (b; Shi, Gan, Jiang, arXiv 2610.09313 v3, Oct 2026). Theory plus about 187,000 requests to 12 VLMs; a caller computes S (target side in tokens) and L (how much one call must search) before calling.
- Fills: any symbol count made by a VLM or detector call (`elements`).
- Number (b, Table 2, V): legend-symbol recall 0.62 to 0.90 (Gemini 3.8), 0.37 to 0.56 (Qwen3-VL); FloorPlanCAD mosaics 0.25 to 0.43 (Gemini 3.8), 0.05 to 0.12 for one open model, but GPT-6.1 0.63 to 0.61 (no gain). Table 8: on clean controlled images models need S of 0.3 to 0.8, so 1.5 is a safety margin. Cost 3.1 to 8.6 times whole-image tokens. A second source with a different benchmark: LED-BENCH (arXiv 2610.19571), whole sheet 36.38% against overlapping crops 49.34% (+12.96; b, V).
- Licence: code MIT (LICENSE file re-checked 01:27); data in a separate LICENSE-DATA, and the FloorPlanCAD-derived data is non-commercial, so use only the planner. No weights; training data none.
- Leakage: not applicable (prompted models).
- Hours: about 3 to apply the planner to our door/window call on the dev split (estimate); no GPU.
- Breaks: targets there are given by an exemplar and are 44 to 74 px on large sheets; ours are tiny on small images, so the move is upsample 2x to 4x, not tile a big sheet; duplicates in overlaps count against exact match and need a merge; rotated and photographed inputs untested; floor-plan gain was mixed.
- Verdict: **try tonight** (cheapest lever, no training). Sources: https://arxiv.org/abs/2610.09313, https://github.com/shijunzhe/vlm-small-objects. Re-checked 01:26 (abstract: S and L, splitting cannot lower expected recall if no view zooms out and views overlap by one object), 01:27 (MIT licence file).

**3. SAHI sliced inference and sliced fine-tuning, measured on count error** (b, c; Akyon, Altinuc, Temizel, ICIP 2022, arXiv 2202.06934). Cut the image into overlapping slices, run any detector on each, add a full-image pass for large objects, merge with NMS.
- Fills: `elements`.
- Number: sliced inference raises AP by 6.8%, 5.1%, 5.3% (FCOS, VFNet, TOOD); with sliced fine-tuning cumulative gains 12.7%, 13.4%, 14.5% (abstract, re-checked 01:26); TOOD VisDrone AP50 29.4 to 43.5 and xView 2.10 to 20.4 (c, Tables 1 and 2); 25% overlap adds up to 1.7 AP and slightly hurts large objects.
- Licence: code MIT (LICENSE re-checked 01:26; 5,603 stars). Detector back ends vary: the Ultralytics one is AGPL and out. Weights: none. Leakage: not applicable.
- Hours: about 4 once a non-AGPL detector exists (estimate); GPU use is the detector's.
- Breaks: gains are AP, not exact counts; a window cut by a slice edge is found twice or in halves, and a duplicate is a wrong count; our whole images are small, so it means upsample then slice; the merge must not fuse two adjacent windows.
- Verdict: **try Saturday**, scored on count error, not AP. Source: https://arxiv.org/abs/2202.06934, https://github.com/obss/sahi.

**4. Agreement across runs as the "not sure" flag** (a, c; Flowtivity pdf2takeoff blog, 2026; code Apache-2.0). A model lists every item with a position, software counts under written rules, a person confirms; counts are flagged when repeated runs disagree.
- Fills: confidence and proof on `elements` and `rooms`.
- Number (R, vendor blog, 120 AECV plans): when three runs agree the count is right 78% of the time, when they disagree 30%; flagging disagreeing counts points a reviewer at about two thirds of the errors while asking them to check just over a third of the counts; GPT-6.1 Sol itemised inventory 58.5% five-field exact match against 54.3% for the best earlier model, but 57.2% for the same model on AECV's own prompt, so most of the gain is the model (the PR body in entry 1 says the same, re-checked 01:27).
- Licence: code Apache-2.0 (LICENSE file re-checked 01:27). Weights: none. Leakage: prompted models; the plans are mostly CubiCasa5K.
- Hours: about 2 for the flag on our own detector with augmented runs (estimate).
- Breaks: with 5 to 20 px symbols and rotated images, augmented runs will disagree often and flag too many; the blog contradicts itself once on whether the standard-prompt run exists; one vendor's blog.
- Verdict: **try Saturday** on dev, threshold set on dev. Source: https://flowtivity.ai/blog/pdf2takeoff-free-open-source-construction-takeoff/, https://github.com/ajflow/pdf2takeoff.

**5. Accuracy at a stated coverage, evaluated with sheet-level resampling and a fit/validation split** (c; Rossum, Textract, Mindee, Open Buildings; arXiv 2608.14639, 2609.20110, 2606.24420).
- Fills: confidence on every count and room type; the published headline.
- Number: arXiv 2608.14639 (abstract re-checked 01:26): on 13,859 fields from 800 receipts, document clustering gives a design effect of 1.84 to 2.45, fitting score and threshold on the same fields gives coverage 0.416 at risk 0.127 against a target of 0.10 (violated in 95% of splits), a fit/validation split gives 0.318 at 0.096 (average, not a certificate). arXiv 2609.20110 (abstract re-checked 01:26; numbers from c's full read): native VLM confidence clears a 10% error target on 0.1% to 7.0% of fields, fused perception/layout/validation signals on 39% to 72%. ExtractConf (2606.24420; c): AUC 0.928 against 0.705 for mean log-probability, small test set. Rossum: default threshold 0.975, documents sent on carry at most 2.5% error by design (page marked deprecated). Open Buildings publishes, per region, the score threshold for 80%, 85%, 90% precision with the number of samples behind each row (V, c). Oxipit ChestLink reports 99.1% sensitivity together with its coverage, 7.8% of all studies (Radiology 2023 abstract; c).
- Licence: papers CC BY; 2608.14639 code Apache-2.0 per its abstract (repo not opened); vendors closed. Weights none. Leakage: not applicable.
- Hours: about 4 to build a coverage-versus-exact curve from per-symbol detector scores on dev and bootstrap it over sheets (estimate); no GPU.
- Breaks: those fields are text with checksums; our counts are over many small symbols, so a per-answer score must be built from per-symbol scores and tested for calibration; no published coverage-guaranteed count intervals for detected symbols were found (c, looked-for list).
- Verdict: **try tonight**: it is evaluation code and gives the one claim no competitor makes. Sources: https://arxiv.org/abs/2608.14639, https://arxiv.org/abs/2609.20110.

**6. PlanQ-CubiCasa: the exact-count ladder on CubiCasa5K** (a; GitHub repo and manuscript, created 2026-11-03). U-Net segmenter plus rules, a fine-tuned DeepSeek-OCR2, and a general VLM given an area schedule, scored on CubiCasa5K test plans with labels from the dataset SVG.
- Fills: `elements` (doors, windows) from connected components of a predicted mask; `plans` area.
- Number (re-checked 01:26 in the JSON): U-Net door exact 64, 66, 67, 65 of 190 for closing kernels 0, 3, 5, 9, window exact 63, 63, 61, 56; median absolute error 1; median MAPE door 14.29%, window 20.0%. README (a): IoU door 0.656, window 0.742; VLM given the schedule door 10.5% and window 9.1% median MAPE (n 280), differences between readers not significant.
- Licence: code MIT (LICENSE file seen 01:26); derived labels inherit CC BY-NC 4.0 (DATA_LICENSE.md present). Weights not released.
- Leakage: yes in the sense that it trains on CubiCasa5K train; its test split is the official one, the same data our sealed eval largely draws from.
- Hours: about 4 to reproduce the count script on our split (estimate); training about 24 minutes per seed on one GPU per its README (R).
- Breaks: single author, unreviewed; the closing kernel was chosen on the test split in the script; labels follow the dataset SVG, not AECV's rules; the schedule given to the VLM leaks the answer; fused openings (two adjacent windows) become one component, which is where exact counts fail.
- Verdict: **try Saturday** as a sanity floor: a pixel segmenter gets about one plan in three exact, a rule engine about one in nine, frontier VLMs 0.43 to 0.55 on a different set. Source: https://github.com/SoftHeart1314/planq-cubicasa-benchmark.

**7. Measure the person plus the machine, with wrong suggestions in the test** (c; Ki-67 reader study, MASAI, BoneView, Click2Poly, Dratsch 2023).
- Fills: the review step and the demo claim (not a field).
- Number: Ki-67, 90 pathologists, ten tissue microarrays, error 2.1% with AI against 5.9% without (p < 0.001), ICC 0.70 to 0.92, 11.9% median turnaround reduction (abstract re-checked 01:27). MASAI, 105,934 women: screen-reading workload down 44.2% and detection 6.4 against 5.0 per 1,000 (Lancet Digital Health 2025 abstract; c); interval-cancer rate 1.55 against 1.76 per 1,000 with a 20% non-inferiority margin (Lancet 2026; a re-read the abstract; the sensitivity pair 80.5 against 73.8 quoted by c was in a cut-off part that a could not re-read). Dratsch 2023: with a wrong (mock) AI suggestion, inexperienced radiologists' correct ratings fell from 79.7% to 19.8% (27 readers, 50 mammograms; c). Lehman 2015: computer-aided detection showed no accuracy gain in 495,818 real mammograms (c). Click2Poly (arXiv 2608.11424): correction took 303.5 min with standard tools against 199 min with the tool, in a Latin-square design with a quality check on every result; one of four areas got slower (c). Handoff: estimators 87.9% quantity precision against 78.8% for the system (re-checked 01:27).
- Licence: studies; Click2Poly code not found. Leakage: not applicable.
- Hours: about 3 to time one person counting 20 plans by hand against checking our overlay (estimate).
- Breaks: pathology is fixed-magnification tissue; our symbols are 25 to 400 pixels each, rotated, scanned. Three observations of the same effect: marks that are often wrong are worse than none, a shown suggestion is followed, and agreement between reviewers rises more than accuracy does.
- Verdict: **try Saturday** as an evaluation design: reveal our total only after the reviewer counts; report minutes and "answers the reviewer changed". Sources: https://europepmc.org/article/PMC/PMC10787826, https://arxiv.org/abs/2608.11424.

**8. Handoff-H1 and TAKEOFFBENCH-V1: the claim to answer** (a, b, c; arXiv 2608.15032, 2026-08-15). A takeoff system of purpose-built CV models, tool-using vision agents and a project knowledge layer; ten residential blueprint sets.
- Fills: none directly (priced material lines).
- Number (abstract re-checked 01:27): 10 sets, 2,009 verified items, 1,348 scored; H1 81.6% composite (coverage 86.1, P@25% 78.8); estimators 77.6% (65.5, 87.9); seven frontier models 35 to 61 (best 61.4). Composite = coverage^0.4 x precision^0.6 with an LLM judge; precision counts a quantity right within 25%; counts are over-penalised and folded with length and area. Windows & Doors trade: H1 88, estimators 89, best frontier 69 (Table 2, a and b agree). Human spread over sets exceeded 30 points (c).
- Licence: harness public in the harbor framework, repo has no LICENSE file (a, b, c; the README lists "on request"); an open issue says the request address does not accept mail (b). Weights: none.
- Leakage: not applicable. Hours: 0 to cite.
- Breaks: residential US trades from PDF sets with text, not single raster plans; benchmark and product from one company; the launch post says 15 sets, paper, repo and report say 10.
- Verdict: **idea only** as context; never in the same column as exact match. Source: https://arxiv.org/abs/2608.15032, https://www.handoff.ai/tech/h1-model-release.

**9. What detectors reach on CubiCasa5K doors and openings, and what the label did** (a, b, c; DoorDet arXiv 2508.07714, Raster2Seq 2602.09016, fpvec-lab 2608.25608).
- Fills: `elements` positions.
- Number: DoorDet, 4,991 plans re-rendered at 1495 x 1311 (7.81 doors a plan), Co-DETR mAP@50 0.926 over ten door classes, 0.650 before human label correction; annotation time 97.5 s per plan from scratch, 54.5 s with detector, LLM and a person (b, Table 5). Raster2Seq at 256 x 256: Window & Door F1 77.8 (RoomFormer 78.5). fpvec-lab, 287 test plans: opening F1 0.246 when emitted, 0.644 to 0.799 read from a heatmap, door/window family head 0.988 with 200K parameters; the corrected-label checkpoint score moves wall F1 from 0.74 to 0.825, so CubiCasa5K label noise is about 8 points of wall F1 (README and paper; a, c).
- Licence: fpvec-lab code MIT (LICENSE seen 01:26), ResPlan-FP data CC BY 4.0, CubiCasa5K-derived parts non-commercial; Raster2Seq code MIT but its HF weights are CC BY-NC 4.0 (card read by b); DoorDet data "upon acceptance".
- Leakage: yes for anything trained on CubiCasa5K (all three). Hours: about 10 for a first detector (estimate); DoorDet's backbones need a large GPU at 1280 px.
- Breaks: per-instance F1 compounds into per-plan failure (F1 0.85 on 8 openings predicts exact on well under half of plans by my arithmetic, a; the measured 33% above agrees); our median 855 px is 1.7 times smaller than DoorDet's renders and 3 times larger than Raster2Seq's input.
- Verdict: **idea only** for the weights; take two lessons: label quality moved mAP@50 by 0.28, and door-versus-window family is a solved sub-problem (0.988) while finding the opening is the hard part. Sources: https://arxiv.org/abs/2508.07714, https://arxiv.org/abs/2608.25608.

**10. Show the doubt on the drawing: shaded items, two operating points, three levels, refuse with a reason** (a, b, c; EagleView, BoneView, Apple RoomPlan, BuildVision, VERDICT).
- Fills: confidence and proof on every count.
- Number: none published as accuracy. EagleView's sample report shades sections to verify and says the report "DOES NOT offer an accuracy guarantee" on poor imagery (read in full by c). BoneView (FDA K212365): solid box at the high-specificity point, dotted at the high-sensitivity point; stand-alone 0.928/0.811 and 0.841/0.932 sensitivity/specificity on 8,918 radiographs; 24 readers, 480 cases, sensitivity 0.648 to 0.752 (FDA text via a mirror; c). Apple RoomPlan gives each wall, door, window and opening high/medium/low (developer docs; c). BuildVision lists "Scale needed" sheets and what prevented measurement (docs; a). VERDICT (NeurIPS 2026 workshop abstract): separate value and evidence confidence, about 120 labelled items recalibrate after a shift (c).
- Licence: closed products and one abstract; ideas only. Leakage: not applicable. Hours: about 6 for a review list with a gate, a refusal reason and two marks (estimate).
- Breaks: none of these publishes calibration; a review list with many false marks is worse than none (Lehman, c).
- Verdict: **try Saturday**; it is UI and reporting on top of entry 5. Sources: https://www.eagleview.com/wp-content/uploads/2025/07/Full-House-Sample-Report.pdf, https://fda.innolitics.com/device/K212365, https://developer.apple.com/documentation/roomplan/capturedroom/confidence.

Not re-opened in the merge (carried from the reports, which read them): the CompassData PDF, the BoneView mirror, Click2Poly, Dratsch, Lehman, Open Buildings, LED-BENCH, the Rossum and Apple pages. Nothing in the top 10 failed a re-check; the top 10 rests more on reports a, b and c than on my own reading for those items.

## 3. Full table

"Read" = the author read it in the source; "R" = authors' or vendor's claim; "S" = search summary only. From: a, b, c.

| Item | Kind or field | Claim, number | Licence or price | From | Status |
| --- | --- | --- | --- | --- | --- |
| AECV-Bench | benchmark, floor plans | door 0.39, window 0.34 (paper); 0.433/0.392 recomputed; 0.55/0.44 open PR | none; free | a b c | read, recomputed |
| PlanQ-CubiCasa | benchmark | U-Net door exact 33.7%, window 33.2%, n 190 | code MIT, labels CC BY-NC 4.0 | a | read (README, JSON) |
| Flowtivity pdf2takeoff | open takeoff engine and blog | 0.295 five-field no model; 0.585 GPT-6.1 Sol; 78% vs 30% agree/disagree | Apache-2.0 | a b | read, numbers R |
| Handoff-H1 / TAKEOFFBENCH-V1 | takeoff system, benchmark | 81.6 vs 77.6, P@25% | harness no LICENSE; data on request | a b c | read, numbers R |
| Togal.AI | takeoff SaaS | "98%" (no metric); Kansas within 5% after fixes; Utica 11 of 13 counts exact | USD 299 per user per month | a b c | read |
| Togal Construction's Last Exam | vendor benchmark | Togal 97.7, best model 36.4 (IoU/F1/mAP) | repo not public | b | R |
| Kreo (app, API) | takeoff SaaS | "outline accuracy 72% to 94%", no definition | USD 100/175/250 per user per month; API about USD 0.97 per launch | a c | read, claim R |
| STACK, ConstructConnect, zzTakeoff, OST | takeoff | none; "Automatic Window Counts ... even when no tags are present" (ConstructConnect) | STACK USD 249/299 (+ USD 899 add-on) | a | S, release note read |
| Bluebeam Revu / Max | markup suite | Max reads existing markups; none | AU$ 451 to 979 per user per year | a b | read (reseller), community post |
| Autodesk Takeoff, Procore, Trimble, BuildVision | takeoff review patterns | accept first; Matches/Possible Matches; confidence rating per count; refusal reasons | in suites | a | read |
| Houzz Pro, Buildxact, Bobyard, Hustro, MeasureAI, Construction.ai, Nomic | takeoff, small vendors | "count windows, doors ... simplified plans only"; confidence score; no numbers | various | a | read, claims R |
| Beam AI (Attentive.ai) | takeoff and done-for-you | "99%+ accurate ... 24-72 hours" | USD 15,000 to 25,000 per trade a year (S) | a | read (press, home) |
| Make a BIM | plan to IFC | none; "always review" | EUR 0.10 per object; 0.06 on subscription | a | read |
| Graphisoft Plans2BIM (WiseBIM), ACCA usBIM.planAI | plan to IFC | none; 50 to 100 px per metre advised | free and paid | a | read |
| Civils.ai | civil takeoff | manholes 149/149, drainage +0.18% (one blog, one project) | USD 90 per month (10 takeoffs) | b | R, anecdote |
| ThirdEye Arch Plan AI | vendor PDF | "98.5% ... +-1.5%", no test named | not stated | b | read, no evidence |
| Kamai AEC-Geometric-Bench | vector benchmark, vendor-run | micro F1 0.930 vs 0.015 to 0.062; window F1 .860 | scorer Apache-2.0; 15 sheets CC BY-NC 4.0 | a b | read, R |
| ArchCAD-400k / DPSS | vector CAD | PQ 70.6, instance mAP 40.7 | academic | a b | read |
| DoorDet; Raster2Seq; fpvec-lab; FloorplanVLM | CubiCasa5K detection and vectorising | mAP@50 0.926; W&D F1 77.8; opening F1 0.85; 0.7333 | see entry 9; FloorplanVLM repo unverified | a b c | read |
| SALI-FP | VLM plan parsing | window IoU 0.05 to 0.23 vs trained model 0.72 | no code | b | read |
| Liang, Fukuda, Yabuki (EC3 2026) / ResBIM | plan to IFC | IoU 92.1%, strict IFC precision 71.1%, 62/200 exact | ResBIM code MIT; dataset terms unanswered | b | read |
| floorplan2ifc, roomgraph, CAD2BIM, OpenTakeoff | open repos | self-report only | none / MIT / NOASSERTION / AGPL (MIT then Apache then AGPL on 2026-10-10) | b | read |
| IfcOpenShell | IFC library | n/a | LGPL-3.0 (usable unmodified, record 0006) | b | read (API) |
| IFC-Bench v2, IFCMemoryBench, BIM-Edit, BIBIMBAP, IfcLLM | BIM QA and editing | 56.0% vs 19.1% static; 32.4%; 49.5%; 50.2% | data CC BY 4.0; code NOASSERTION | a b | read |
| AEC-Bench (Nomic) | agent tasks | 196 tasks, no symbol counting | Apache-2.0 | a b | read |
| DrawingVQA | drawing QA | quantity take-off best 41.7 | text CC BY-NC-SA, images private | a b | read |
| LED-BENCH, MMArch, ARCH-B, CEQuest, GDP.pdf | other drawing benchmarks | crops +13 points; best 52% to 53% | mixed | b | read or abstract |
| MechVQA / MechVL | transfer: mechanical drawings | counting subtask 62.8 to 88.4 | Apache-2.0 | b | read, overlap confirmed |
| K-OPSD | fine-tuning with verifier | 4B model 0.738 combined, 121 prompts | none found | b | read |
| Sketch2BIM | sketch to BIM | walls 83% first pass, 3 to 4 feedback rounds, 10 plans | no code | a b | read |
| SkeySpot / DELP | scanned electrical plans | YOLOv8 mAP50 81.1% to 82.5% (reports differ), 45 plans | no licence, data on request | a b | read |
| MDPI Applied Sciences 2026 pipeline | plan pipeline | window 72.1%, door 78.8% mAP50 on 10 plans | AGPL detector | a b | read |
| Periodica Polytechnica VLM study | VLM room area | MAPE about 43% vs pixel count 1.58% | CC BY | a | read |
| "The Count Is There, but Misaligned" | error probes | up to +15.6 points, counts 1 to 9 | not checked | a | read |
| Shi et al.; LED-BENCH; SAHI; LVLM-Count; Rezvanifar 2020 | small objects | see entries 2 and 3; MAE 25.57 to 17.86 | MIT; MIT; Apache-2.0; n/a | b c | read |
| SAM 3 | exemplar segmentation | not measured here | custom SAM Licence, not on allowed list | b | abstract, test only |
| CountingDINO | exemplar counting, WACV 2026 | FSC-147 | repo has no licence | a | abstract |
| PID2Graph, SynthPID | transfer: P&ID | symbol mAP 73 to 87; seeded synthetic 63.8 vs ~33 scattered | data CC BY-SA 4.0 | b c | read |
| Open Buildings, Overture, docling | adjacent reporting forms | threshold-per-precision table; source per item; worst-percentile grade | CC BY / ODbL / MIT | c | read |
| EagleView, Hover, Matterport, iGUIDE, Nearmap | adjacent measurement products | 98.77% (CompassData); none; 1% to 2%; 1% area; hard cases over-sampled | per report USD 49 / 80 | a c | read |
| CubiCasa (app), magicplan, RoomSketcher AI Convert, Zillow ZInD | adjacent plan products | 95% to 97% (vendor, via reseller); none; no number; ZInD annotators correct a prediction | RoomSketcher: 5 credits if saved, USD 38 human redraw | a c | partly read; CubiCasa pages return 403 |
| Werk24, Textract, Document AI, Mindee, Rossum, Veryfi | adjacent document products | 95%+ (R); confidence per field; 0.975 default | EUR 1.25 per page; USD 0.0015 to 0.07; USD 0.10 per doc; 1.5 credits | c a | read |
| Ki-67, MASAI, BoneView, ChestLink, Articulate Pro, Dratsch, Lehman | reader studies | see entry 7 | n/a | c | read (abstracts and full text as stated) |
| MIDOG, DPA validation statement, Paige, HOT fAIr | adjacent | F1 0.698 to 0.773, per-scanner 0.43 to 0.85; per-scanner validation; AGPL-3.0 code | data CC BY-NC-ND | c | read |
| Stoa | project assistant | no counting claim; cited answers | not public | a b | read |
| CubiCasa5K | dataset | 5,000 plans | CC BY-NC 4.0 (LICENSE file read by a) | a b | read |
| Synthetic plan sets (benikm91, ResPlan, ResPlan-FP) | data | exact labels, Manhattan, one door tree | CC BY 4.0 | a b | read (cards) |

## 4. Transfers from other fields

| Field | What plays our object | Why it transfers | What breaks | Code |
| --- | --- | --- | --- | --- |
| Roof measurement (EagleView, Hover, CompassData) | a plan sheet; roof lines and areas | independent benchmark with the formula printed; shaded sections to verify; stated exclusions | their counts of windows come without accuracy; vendor-commissioned test, 89 lines | idea only |
| Pathology counting (Ki-67, Paige, MIDOG) | a window cell is a mitotic figure; a plan is a field | small repeated objects, exact count, a person checks marks; domain shift per scanner | fixed magnification; Fourier style mixing changes colour, not rotation or line width | idea only |
| Mammography and chest X-ray (MASAI, BoneView, ChestLink) | a sheet; a count | risk score decides how much review a case gets; two operating points; stated coverage | needs a per-sheet risk score we do not have | idea only |
| Invoice extraction (Rossum, Textract, Mindee, ExtractConf, 2609.20110) | a count or room type as a field | confidence calibrated per field and source, four validation sources, grey tick, arithmetic checks | fields there are text with checksums; ours are counts over symbols | idea only |
| GIS digitising (Open Buildings, Overture, HOT fAIr) | a room polygon or element | threshold-per-precision table, source per item, volunteers say yes/no/not sure | 50 cm roofs against thin line art; fAIr is AGPL | idea only |
| Engineering diagrams (P&ID, PID2Graph, SynthPID) | a door or window glyph | small repeated symbols on line art; overlap above 50%; synthetic data seeded from real topology reached 63.8 edge mAP against about 33 for scattered symbols | standard glyphs there; ours vary by drawing office | data CC BY-SA 4.0, code needs fine-tuning |
| Mechanical drawings (MechVQA, Werk24) | recognition and counting question | SFT then RL with a checkable reward lifted counting 62.8 to 88.4; typed JSON with pixel provenance | authors confirmed the evaluation set shares images with the training pool (issue read by b), so read as an upper bound | recipe only |
| Aerial and drone images (SAHI, xView) | a symbol is a distant object | slice at the object's scale, overlap, merge | duplicates break exact counts | usable as is (MIT) |
| Conformal counting in histology (Blot 2025, SeqCRC) | counts with a precision guarantee | threshold picked on a calibration set of 35 cuts still gave usable guarantees | guarantees precision or an upper bound, not an exact count | idea only (repo has no licence) |
| Optical music recognition (Legato, handwritten OMR) | dense small symbols on a page | synthetic data from re-rendering symbolic sources; score by correction effort | weak lead (abstract) | idea only |
| Scan and phone vendors (Matterport, iGUIDE, magicplan, RoomSketcher) | measurements from images | accuracy as a tolerance tied to the job, an error budget, refuse inputs that fail; pay only for saved results | they measure lengths, not counts | idea only |
| Scan-to-BIM (Cloud2BIM, BIMStruct3D, Agent2BIM) | none | only IFC writing carries over; best open pipeline finds doors at 22% volume IoU | needs 3D data | IfcOpenShell LGPL, rest skip |

## 5. Disagreements and how they resolve

- **AECV "mean".** c wrote 0.51 is the mean over four fields; a and the pdf2takeoff note say five including Space. Paper Table 1 (re-checked 01:27): Gemini 3 Pro 0.51, 0.39, 0.34, 0.89, 0.82; the four shown average 0.61, so a holds.
- **AECV best door/window.** The paper says 0.39/0.34 (c); the repo's files give 0.433/0.392 (a and b recomputed independently, matching to within 0.01 of the paper where both exist); PR #3 says 0.55/0.44. All three are right for what they measure; quote the source and the date.
- **Werk24.** a first read EUR 149 to 3,900 a month on the Studio tab and c (and an early merge) quoted EUR 1.25 per page and EUR 590 a month; a later read of the `#api` tab shows both are right: API EUR 1.25 per page, Production EUR 590 with 500 pages then 0.95, Studio EUR 1.56 to 3.73 per included page. Quote both with the tab.
- **Handoff set count.** 10 (paper abstract re-checked 01:27, report, repo) against 15 (launch post). 10 holds.
- **Kreo accuracy.** a found none on pricing and help pages; c read "outline accuracy 72% to 94%" on kreo.net with no definition. Both stand: a claim exists, its metric does not.
- **Togal "98%".** a: the FAQ states it and an executive said it; c: the home and pricing pages carry no number. Compatible; the figure lives on the FAQ page.
- **BuildVision confidence.** c's summary says "confidence scores and review flags"; a read the docs and found Engine/Beta/Manual badges, "Scale needed", and no tiers; b read that the calibration docs advise against substituting a typical door width. Not verified as a per-item confidence.
- **Bluebeam Max.** b (Handoff report, community post): relies on the text layer and cannot read rasterised sheets; a (reseller page): reads markups already in the PDF. Compatible: it does not detect symbols.
- **SkeySpot mAP.** 81.1% (a, YOLOv8 mAP50) against 82.5% (b, abstract); not resolved, immaterial.
- **Raster2Seq weights.** a did not check; b read the card: CC BY-NC 4.0, with a CubiCasa5K checkpoint (leakage) and open issues on a checkpoint/script mismatch and a room IoU bug. b holds.
- **DrawingVQA quantity questions.** 6 (a, from the paper pie) or about 12 (a and b, from score steps of 8.3 points); unresolved; either way too few for statistics.
- **MASAI.** a re-read the Lancet 2026 interval-cancer abstract (1.55 against 1.76); c's 80.5 against 73.8 sensitivity was not re-read by a. Quoted with that caveat.
- **Zhao et al. 20.4%.** b did not touch it; a traced it to a 60-student area task; c did not use it. a holds.

## 6. Negative results

- Zero-shot VLMs do not solve exact door and window counts: 0.03 to 0.39 across ten models in the paper, best 0.55 (open PR) (AECV-Bench).
- On dense construction sheets VLMs do not locate objects: object F1 0.015 to 0.062 at IoU 0.5 against 0.929 for the vendor's trained, vector-reading system (Kamai; vendor-run, the paper says the inputs are not equivalent).
- A VLM-only parser loses on openings: window IoU 0.05 to 0.23 against 0.72 for a trained CubiCasa5K model (SALI-FP, Table C.8).
- A trained pixel segmenter gets only about one plan in three exact on CubiCasa5K (PlanQ), and a rule engine one in nine (pdf2takeoff ledger).
- Fusing doors and windows into one class hides count errors (Raster2Seq "Window & Door" F1; Kamai collapses window subtypes).
- Bigger or newer is not enough: Claude entries in AECV-Bench did not improve on Opus 4.5 for doors and windows (0.15/0.15 for Opus 4.8); GPT-6.1 gained nothing on FloorPlanCAD mosaics from the zoom rule.
- Marks help only when false marks are rare: computer-aided detection showed no benefit in 495,818 real mammograms (Lehman 2015); a shown wrong suggestion cut correct ratings from 79.7% to 19.8% (Dratsch 2023; mock AI, 27 readers).
- A model's own confidence is nearly useless for auto-approval: 0.1% to 7.0% of fields clear a 10% error target (2609.20110); token log-probabilities degrade to an all-positive classifier (ExtractConf).
- Same-set threshold fitting breaks the contract: coverage 0.416 at risk 0.127 against a 0.10 target (2608.14639).
- Random-scatter synthetic plans did not transfer (about 33 edge mAP) where topology-seeded ones did (63.8) (SynthPID; P&ID).
- Scanned input is the weak case: a vendor's engine scores 99.8% on born-digital generated sheets and 37.3% on degraded scans (ScaledDrawingBench, self-made, circular); Kansas: scale could not be set automatically on a scanned submittal; one student could not use Togal with several scales on one drawing.
- Search-hit "tests" that are not tests: one SEO tutorial has an invented answer key; a trade-press roundup's 1.8% total error gave the tools a BIM model.
- BIM does not hand a free count: even with a clean IFC model an adaptive agent is right about 56% of the time (IFC-Bench v2), and LLM edits to IFC are right about half (BIM-Edit 49.5%, BIBIMBAP 50.2%).
- Class-agnostic counters with exemplars (CountingDINO) were built on natural objects of tens to hundreds of pixels; the repo has no licence.

## 7. Looked for and did not find; unverified leads; open questions

**Looked for and did not find.**
- An independent head-to-head of takeoff products on door and window counts (queries in a rounds 10, 14, 20, 36, 56).
- Any CVPR, ICCV, ECCV, WACV, ICDAR or GREC 2025 or 2026 main-track paper that counts doors or windows on raster plans (a rounds 4, 12, 54, 61; b round 9; title scans of the proceedings, not full reads). arXiv's last ten months: AECV-Bench and K-OPSD are the only counting papers; the takeoff literature is one vendor report (a rounds 80 and 81; b round 14).
- A published calibration, accuracy at a coverage, or per-class exact match for any takeoff product.
- A study of human takeoff or counting error between estimators; only vendor blogs say "5% to 15%" (b round 17). Handoff's estimators are the only measured human reference.
- A permissive raster-plan-to-IFC tool with held-out accuracy (b).
- Coverage-guaranteed count intervals for detected symbols in images (c).
- A per-sheet price from any takeoff vendor or human takeoff service.
- Stoa's own accuracy for counts: its pages claim citations, time saved and project value only (a, b).
- CubiCasa's own accuracy page (403 for plain fetch and the browser, a and c); Nearmap's numeric table (not in page text).
- Forward citations of AECV-Bench beyond nine citers (b via the citation graph; a's OpenAlex and Semantic Scholar calls were rate-limited).

**Unverified leads (not in the ranking).** Kreo auto-count wording (read once, page gone); Beam AI "within +-1%" and "90% feature capture"; "Togal 12 minutes, Stack within 3%" (trade press); Hover-sponsored Haag study (variance 2.6% against 3.4%); Xometry manual-review rule; ChestLink real-world follow-up (26.5% of normal scans reported confidently, 0.15% clinically significant discordance; conference summary); invoice touchless rates (25% to 49%, vendor-sold); CVC-FP licence (page unreachable); ArchPlanVQA (abstract only, no licence on the repo); E3S 2026 "93% detection accuracy" (page 403); VecFormer PQ 91.1 (search summary); WAFFLE dataset (nearly 20K plans, licence per image); FloorplanVLM repo (none verified; weights need 32 H200); "Why Floor Plan Object Detection Breaks Under Real Scans" (SSRN, Cloudflare); Magicplan "97%" (not found again); the 75-of-120 CubiCasa share (a research note's judgement); a Utica-related second mention.

**Open questions.**
- Do AECV-Bench's 120 plans overlap our sealed eval? Only a person with both sets can check.
- Is AECV-Bench PR #3 merged, and will a LICENSE be added?
- Do we headline accuracy at a stated coverage? It needs a calibrated score per count, evaluated over sheets.
- Can we print exact match under AECV's rules and under the dataset's rules side by side?
- CubiCasa5K and CVC-FP are non-commercial: what do we say about training data in the pitch?
- Whether Handoff will share its ten sets (the listed address reportedly does not accept mail) is a decision for the people running the project, not for this report.
- SAM 3's custom licence terms against our rules, and its accuracy on 5 to 20 px line-art symbols (untested).
- Missing tools across the three passes: Semantic Scholar and OpenAlex (rate limited), CubiCasa and some vendor pages (403), buildingSMART pages (bot check); no headless browser in the first pass.

## 8. Experiments proposed (at most five)

1. **Coverage curve.** On the dev split, score each count with per-symbol detector scores, plot exact-count rate against share of questions answered with a bootstrap over sheets and a fit/validation split; settle whether "x% exact at 70% coverage" is better than the 55.3% baseline by at least 10 points.
2. **Upsample before detecting.** Run the symbol step at 1x, 2x, 3x, 4x (with overlapping slices and a merge) on dev; settle with window and door exact-count rate, a gain of 5 points or more over 1x.
3. **Run-agreement flag.** Three augmented runs (rotation, scale) per plan on dev; settle with exact rate among agreeing against disagreeing plans and the share of errors caught while checking a third of the counts (the vendor reports 78% against 30%, two thirds of errors).
4. **Exact-count ladder.** Score our count output on CubiCasa-style dev plans under the dataset's own labels and compare with 33.7% (door) and 33.2% (window) exact of the U-Net reader; a model below that is not beating a segmenter and rules.
5. **Review timing.** One person counts 20 dev plans by hand, then checks our overlay with the total hidden until they have counted; settle with minutes per plan and number of answers changed, against the vendors' three seconds per manual count (Trimble's yardstick, R) and a clean-plan limit of about one minute for nine windows and nine doors.
