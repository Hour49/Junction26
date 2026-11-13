# lit-scale (L6): merged report on scale, dimensions and areas

Merged 2026-11-14 from lit-scale-a (papers and measured numbers in our field), lit-scale-b (products, Finnish conventions, code) and lit-scale-c (adjacent fields). Sources are opened, not remembered: each top-10 entry was re-opened by the merger on 2026-11-14, 01:23 (machine clock), and says what matched. "Read" means a report's author opened the text and read the cited part; "claim" means the authors' or vendor's own statement; "search only" means a search summary that nobody confirmed. Nothing from search summaries is in the ranking.

Our images, used in every "what breaks" line: median longest side 855 px (minimum 240), symbols 5 to 20 px, about one in three rotated by 90 or 180 degrees, scans and phone photos among them (`docs/research/lit-campaign/worker-brief.md`). Our scorer already has the states `scaled`, `estimated`, `no_scale` and `not_to_scale`: a `scaled` value must be within 2% of gold, an `estimated` value is scored by median error and share within 10% and 20% (`eval/README.md`, scale section). Leakage: 829 of our 959 sealed eval drawings are in CubiCasa5K's train split (worker brief).

## 1. Answer

The scope asks which scale route is proven to within 2%, which only to about 10%, and how others show the user that a scale is an estimate.

**Proven to within 2%: only routes that read a printed mark whose true size is known, and none of them is measured on a floor-plan raster like ours.**
- Template-matching a printed ruler against a known ruler of the same type: median conversion-factor error 0.141% to 0.199%, 94.8% to 99.0% of rulers within 2%, and the method says "no match" on 2.4% to 4.1% (herbarium sheets, BISS 2026, Table 1; re-checked 01:23). Clean photographs, a known ruler type, rulers not plans.
- Detecting a printed bar, finding its ends by edge and peak search and reading its number: 0.3% mean absolute length error and 0.63 px on 111 real electron-microscope images, unit and value 100% (Uni-AIMS, arXiv 2505.06918, Table 2, read by report c twice). Clean, synthetic-trained bars.
- A printed field sheet in phone and camera photos reads about 1% low (mean -0.97%, SD 0.93, n = 59; FieldPrism, Table 3, read by report c): a correctable bias.
- Dimension-line scale on floor plans is the one floor-plan route with a published rate at 2%: **72% of plans within 2%, 83% within 5%, 86% within 10%** (Lv et al., CVPR 2021 supplement, Table 2; re-checked 01:23). It is Chinese plans that carry dimension lines, the data and code are not open, and the paper's main text has no scale error. About one plan in four misses 2% even there.
- Buildings 2026 (RANSAC over per-dimension ratios) states "a mean error of approximately 0.2%" on its non-modular examples; the table is an image and the text calls them "representative examples", so this is an example-level claim, not a rate (report a read it; report b took it as the best-supported figure; see section 5).

**Only about 5% to 10%: everything that uses no printed scale mark on our kind of image.**
- The only measurement on CubiCasa5K itself is a student project (floorplan2bim, README, no licence): fused door and wall priors plus printed room areas give a **median scale error of 6.5%** on 301 single-storey test plans, **18% of plans within 2%, 38% within 5%, 71% within 10%** (recomputed by the merger from the project's own per-plan file, 01:23: n = 301, median 6.51, 18 / 38 / 71). Doors alone: median 7.1%. With perfect (ground-truth) geometry the same priors still give a median 5.0% and only 21% within 2%, so recognition is not the main limit: the priors' own spread is (door width has a 5.4% spread in CubiCasa5K's ground truth, per the project's config, read by report a). The reference is CubiCasa5K's nominal unit (100 SVG units = 1 m); the project checks that vector and image align, not that the unit is metric, so 6.5% is an error against the dataset's nominal scale.
- The same file, split by image size (report a, round 51; not re-run): plans under 1,200 px on the long side have a median 8.9% (62% within 10%); our median image is 855 px, below that bucket. More doors lower the median (10 or more doors: 5.8%), but the share within 2% stays between 12% and 23% at every door count.
- Agreement between priors does not certify a scale: when door and interior-wall estimates agree within 5%, only 17% of plans are within 2% (report a, round 50, own analysis of the same file). Disagreement over 20% does flag bad plans (median 9.0%).
- A door-width prior costs about a factor of three against a measured reference in the one study that compared both (wound area from a fingernail: correlation 0.979 and RMSE 2.55 with the measured width, 0.875 and 8.08 with the population mean; report c, round 5, abstract and text read).
- Without any reference, estimating metric size from appearance lands within 10% about three times in ten: 39.3% for people, 36.9% for a text-only frontier model, 30.8% for the best open VLM (Ill-Posed by Design, arXiv 2606.24335, Table 1, 331 tape-measured scenes; read by report c, not re-opened).
- Printed room areas as the ruler: 3.1% median scale error with exact rooms (25% of plans within 2%) and 7.9% with recognised rooms, on the 21% of test plans where labels were read and accepted (floorplan2bim's file; report a, round 48). Where an area was used the fused scale was a little better (median 5.3% against 7.1%, 24% against 17% within 2%; n = 62, not selection-free).
- Reading numbers off a chart axis is also only 5% to 10% in the wild: 63.0% of values within 2%, 81.2% within 5% (28 bar charts, PLOS ONE 2026); 64% to 77% within 2% (ChartRecover Table 5). Misses are mostly one misread digit.

**What area does with the scale.** Area error is about twice the scale error: a reference known to +-5% gives total area to about +-10% (Applied Sciences 16(13):6290, Sec. 4.5, read by reports a, b and c). In floorplan2bim, with ground-truth geometry and the estimated scale, floor-area error has a median of 10.0% and only 50% of plans are within 10%; recognition alone (true scale) adds 5.3%; the full system gets 14.9% median, 34% within 10% (report a, round 53, own computation). Given a correct scale, plain pixel counting on clean colour masks gives 5.68 +- 7.21% per room (Table 2 of Aliyev and Barsi 2026; re-checked 01:23); large rooms about 1.5%, bathrooms and balconies 11% to 12%. The abstract's "1.58% at the floor plan level" is not supported by the tables (Table 3 prints 1.58 as the living-room figure); we use the table reading. Their scale was derived from the known total area, so this measures segmentation only.

**What is not scale:** counts of symbols need no scale, and an independent takeoff study found counts matching a contractor's exactly in 11 of 13 items while areas were biased low by 1% to 11% (one +13.4%); the authors attribute the area bias to segmentation boundaries, not to scale (Sadeh et al., ASC 2026, read twice by report b). Our 67.3% count questions (worker brief) do not depend on the scale field at all; it matters for area and length answers and for the `scale` field's honesty.

**How others show that a scale is an estimate** (all patterns; none is a user study and none reports an error rate for the scale itself on a raster plan):
1. Refuse, and say so: herbarium "no match"; PlanMetric `insufficient` or `conflict` with no value; figverify "uncalibrated rather than guessed"; LinePilot keeps the raw reading and a confidence.
2. Per-mark evidence: PlanMetric keeps accepted and rejected dimension pairs and an evidence picture; QGIS Georeferencer reports RMS error per control point; photogrammetry software splits marks into control marks (pull the fit) and check marks (only report the error).
3. A source label next to the number: Google Solar API `imagery_quality` HIGH / MEDIUM / LOW / BASE, plus a schema comment that whole-roof area is "unreliable" while ground area is "reliable" (proto file read by report c).
4. A per-page state with a human-verified flag: zzTakeoff's green "Human Verified" border; Constructable's toolbar saying a scale was set automatically; Kreo's AI scale is a suggestion the user applies; ConstructConnect: "Always verify the scale" including your own; Houzz shows a banner and a visible default on pages with several scales; BuildVision holds area quantities back when the scale conflicts. zzTakeoff switched its automatic scale off "while we optimize it for accuracy" (two forum threads, read by report b).
5. Labelling the output as conditional and exposing the input: Applied Sciences 16(13):6290 calls areas "calibrated estimates" and lets the operator enter the reference length.
6. A calibration state machine (MicroScale Editor, README and validation file read by report c): pending until confirmed, set back to pending when an endpoint is edited, conflicts reported and never averaged, file DPI never treated as calibration.
7. Asking the user for a reference: Chang et al. (Buildings 2025) put a draggable scale bar in the UI when none is found; CADAiD (Norwegian cadastre) has the user draw a line of known length and an expert check the area polygon; Planora and PlanMapper make the user click two points. CADAiD's authors say fully automatic area is not precise enough for cadastre use.
8. Confidence not as probability: Werk24 starts at 1.0, lowers it for named reasons including "a label whose value does not match the length drawn at the drawing's scale", and says "the score is not a probability"; 0.8 is the review threshold.
Finnish law points the same way: a draft marketing decree (bill HE 191/2026, pending, planned in force spring 2027) would require the brochure to say when the stated area is uncertain, and the manager's certificate under decree 365/2010 already records whether a flat's area was measured to SFS 5139 (reports b, P3.29 and P3.37; Finlex and Edilex texts read). "Estimated" is an ordinary category in Finnish housing practice.

**What this means for our `scale` field (the merger's reading of the evidence, not a result):**
- A scale is `scaled` only when two independent printed marks agree within 2%: two or more printed dimension pairs that agree, or a printed total area that agrees with a printed scale bar or dimension, or a printed opening size that agrees with a dimension. Door and wall priors alone are `estimated`, whatever agreement they show.
- Label the source (printed dimension pairs, printed bar, printed total, printed opening sizes, prior) and the number of marks used over the number found. Show an interval for priors: 6.5% median, 71% within 10%, worse under 1,200 px.
- A printed ratio like "1:100" is not a pixel scale for a PNG (it needs the paper size or DPI, which the file does not carry; PlanMetric says the same). Real Finnish marketing plans print "Mittakaava 1:100 (suuntaa-antava)", that is "indicative", next to a printed total area (report b, P3.27). Use the ratio only as a plausibility check, snapped to {1:50, 1:100, 1:200} (Finnish permit guides give floor plans at 1:100 or 1:50; the guides are read by reports a and b).
- Counts and ratios between rooms do not depend on the scale; absolute areas do. Report them separately.

## 2. Top 10, ranked across all three reports

Ranked by how much each helps us decide the scale route and what to build, floor-plan work and transfers in one list. GPU hours are the merger's estimates, marked "est." Every entry fills the `scale` field unless stated, and feeds `rooms` areas where marked.

### 1. floorplan2bim (door and wall priors plus printed room areas, fused): try Saturday, as a baseline to beat
- **What it is:** an eight-step student pipeline from a CubiCasa5K image to BIM and cost; Step 4 fuses four scale estimates by inverse-variance weights: a door width of 0.80 m, exterior and interior wall thickness, and printed room areas read with RapidOCR; the area estimate is dropped when it differs from doors and walls by more than 35%.
- **Field:** `scale` (with `estimated` status), `rooms` area.
- **Number:** median scale error 6.5% (doors alone 7.1%, interior walls 9.1%, exterior walls 18.8%, baseline with a public model's doors 38.3%) on 301 single-storey test plans; 18% / 38% / 71% within 2 / 5 / 10% (recomputed, re-checked 01:23). Train split 3,000 plans for the SegFormer, 400 validation plans for all calibration. README ("accuracy", Step 4) and `outputs/evaluation/results.csv`.
- **Licence:** code: none (GitHub reports no licence) so reimplement from the README and config values; weights: not released. **Leakage: yes**, its recognition model is trained on CubiCasa5K train.
- **GPU and time (est.):** the priors need door and wall recognition we already train; the fusion is 50 lines. One hour on CPU after a door detector exists.
- **Breaks on our images:** door IoU is 0.52 even with their tuned model (0.25 for the public one); wall priors can be 30% off on other drawings (a Korean team's 200 mm wall prior gave a scale about 30% too small on a real apartment drawing; public issue, not peer reviewed); our images are smaller than their median (1,416 px), where the error rises; and CubiCasa5K's nominal unit is itself unverified.
- **Verdict: try Saturday.** The only per-plan distribution of any scale estimate on CubiCasa5K, and a target (median 6.5%) for any better route. Do not claim better than `estimated`.

### 2. Lv et al., "Residential Floor Plan Recognition and Reconstruction", CVPR 2021: idea only (pooling rule), no code
- **What it is:** endpoint heatmaps (ResNet50 FCN) find dimension-line ends; YOLOv4 finds digit areas in three orientations; a digit-count regressor must agree with the read digits; Kuhn-Munkres matches lines to numbers; K-means over the per-pair scales, the largest cluster averaged. Fallback with no scale: median door length 0.9 m.
- **Field:** `scale`.
- **Number:** supplement Table 2: 0.72 / 0.83 / 0.86 of plans within 2 / 5 / 10%, mean error 4.6 (the unit is undefined in the text); without K-means 0.57 / 0.74 / 0.80; without the digit-count step 0.69 / 0.80 / 0.83; without both 0.45 / 0.58 / 0.66, 24.4. Re-checked 01:23 (supplement PDF, Table 2). 1,000 plans with labelled scales, from the authors' 7,000-image Chinese plan set.
- **Licence:** no code or weights found in the paper; data not open. **Leakage:** none (own set).
- **GPU and time (est.):** needs our own labelled dimension pairs, which we do not have; not reproducible tonight.
- **Breaks:** most of our sheets may print no dimension lines (unknown, section 7); digits are 5 to 20 px; inclined walls unsupported; Finnish decimal commas ("K 12,2") are not in its digit set (report a, round 11, from our own sheets; stated as a risk, not measured).
- **Verdict: idea only.** The transferable part is measured: the cluster vote is worth about 27 points at 2% (72% against 45%). Take the largest consistent cluster, never the mean.

### 3. PlanMetric (crown-sports/planmetric): try tonight as a contract, maybe the code
- **What it is:** takes OCR'd dimension text and spans, fits pixels per metre per axis by consensus, rejects inconsistent pairs, abstains when evidence is thin; three states (accepted, `insufficient`, `conflict`); keeps rejected pairs and an evidence SVG; area needs both axes accepted. Defaults: at least 3 independent dimensions per axis, inliers within 2.5%.
- **Field:** `scale` evidence, its status and `plans`-level confidence.
- **Number:** its own validation (docs/validation.md, generated cases, no real OCR): 260 axes with enough evidence all correct at 2%, all 140 unsupported axes refused, and **all 120 axes with systematic upstream errors (10x, a 2x majority, half spans) accepted wrong**; one real furnished drawing recovered 10 mm per pixel on both axes (4 of 5 and 3 of 4 pairs), one private drawing gave `insufficient`. Re-checked 01:23 (validation.md lines for 260 / 140 / 120 read via `gh api`). Not a measure of real OCR accuracy, as its README says.
- **Licence:** code MIT (GitHub API, pushed 2026-10-23, 1 star, v0.2.1); no weights, no data. Leakage: n/a.
- **GPU and time (est.):** no GPU; a day to feed it our OCR boxes and line spans.
- **Breaks:** needs dimension text and spans, which our sheets may not have; the OCR of small rotated digits is the weak step, not the fit; consistently wrong dimensions give a wrong accepted scale.
- **Verdict: try tonight** for the output contract (accepted / insufficient / conflict, per-axis scale, rejected pairs). Evaluate the code only after the number reader exists.

### 4. Printed areas as the ruler (Dodge et al. 2017; ResPlan; floorplan2bim's label route; Aliyev and Barsi baseline): try Saturday
- **What it is:** read a printed room area, divide it by the room's pixel area, vote across rooms; or read a printed flat total and share it out by pixel shares. ResPlan (arXiv 2508.14006) anchors metres per pixel on a listed gross area for 17,000 plans and checks that summed room areas fall within +-25% of the listed total for 98.7% of plans.
- **Field:** `scale`, `rooms` areas.
- **Number:** Dodge: OCR detected and recognised 74.1% of room-size annotations on 20 real-estate plans (re-checked 01:23, text of the PDF); no scale or area error. floorplan2bim: 3.1% median with exact rooms, 7.9% with recognised rooms (21% of plans). Aliyev and Barsi: 5.68% per room with known total (Table 2, re-checked 01:23), VLMs 41.07% and 43.72% (re-checked). ResPlan: +-25% sum check on 98.7% (re-checked 01:23 in the arXiv PDF).
- **Licence:** Dodge: none stated. ResPlan data CC BY 4.0 (paper), repo reports no licence. Aliyev and Barsi paper CC BY, no code. **Leakage:** none of these is CubiCasa5K-trained; floorplan2bim's recognition is.
- **GPU and time (est.):** OCR of numbers plus our room masks, which we train anyway; a few hours once the number reader exists.
- **Breaks:** printed area is the net room area (huoneala), the flat total is a few percent larger than the sum of rooms (67.5 against 70.0 m2 on one real marketing plan), and printed net areas run below annotation polygons; so the route has a built-in bias of a few percent that must be modelled. Printed areas are not always present (floorplan2bim read labels on 30% of its plans and used them on 21%). Printed totals can be an articles-of-association figure, a measured SFS 5139 figure or an old rounded figure, and the sheet rarely says which.
- **Verdict: try Saturday.** The only scale cue that is a printed number and fits plans that carry no dimension chains. Use as an `estimated`-to-`scaled` upgrade only when it agrees with a second mark.

### 5. Buildings 2026 hybrid vectorisation: dimension strings vote, RANSAC inlier mean: try Saturday (reimplement)
- **What it is:** YOLOv11n finds axis markers, dimension annotations and endpoints; vertical text is rotated before PaddleOCR; per-dimension ratio = printed value over pixel length of the matched dimension line; RANSAC discards outliers; the inlier mean is the global scale; a 50 mm module snaps recovered sizes.
- **Field:** `scale`.
- **Number:** OCR accuracy 89.3% on dimension text, 91.0% on axis text (Table 2); "mean error of approximately 0.2%" on non-module examples (Sec. 3.2; Table 3 shows representative examples; no aggregate). Re-checked 01:23: the page text contains "RANSAC-based outlier removal", "89.3%" and "approximately 0.2%" (pwread, 62,434 characters). Detection set: 1,036 dimension images and 823 endpoint images, split 6:2:2.
- **Licence:** paper CC BY; no code or weights; the detector is YOLO (AGPL), so use another detector (RT-DETR or RF-DETR, Apache-2.0); PaddleOCR is Apache-2.0. **Leakage:** none (own Chinese drawings).
- **GPU and time (est.):** the fit is about 20 lines; a dimension-line detector fine-tuned on our crops: under 2 GPU hours on a 12 GB card, but we have no dimension-line labels (open question).
- **Breaks:** Chinese construction drawings with dimension chains; the 0.2% is examples, not a rate; digits 5 to 20 px; a third rotated. Finnish marketing plans may carry no dimension chains at all (two real plans seen: one prints door and window sizes in mm, the other only a total, sill heights and a 0 to 5 m bar; two plans are not a statistic).
- **Verdict: try Saturday** the robust fit (RANSAC or Lv's largest cluster), over whatever marks we can read. The 0.2% is not a target.

### 6. Herbarium ruler matching with abstention (Milleville et al., BISS 2026): idea, transfer from natural-history collections
- **What it is:** a detector finds the ruler, the crop is rotated long side horizontal, CLIP retrieves the three most similar annotated rulers (institutions reuse the same ruler), LightGlue keypoint matching against each, a homography maps the template's known tick positions to pixels; "no-match" if fewer than 10 matching pairs. Role of our object: a printed scale bar, or a repeated drawing style, as a ruler of a known type.
- **Field:** `scale`, abstention.
- **Number:** Table 1: 457 rulers, mean 0.689%, median 0.199%, no-match 2.40%; second set of 1,131 rulers, mean 0.324%, median 0.141%, no-match 4.07%; 94.8% and 99.0% within 2%. Re-checked 01:23 (XML of the article: 0.199, 0.141, 94.8, 99.0, 2.40, 4.07 all present). 400 sheets, leave-one-out. The text says 476 rulers where the table says 457 (unexplained).
- **Licence:** code MIT (kymillev/herbarium-rulers, not archived, pushed 2026-10-14; kymillev/scale-estimation MIT, pushed 2026-10-15; both re-checked 01:23). The older repo uses Ultralytics weights (AGPL); the newer one uses RF-DETR (Apache-2.0), LoMa (MIT), DINOv3 and SAM 3 (Meta custom licences, not OSI). No weights, dataset or evaluation code released yet. **Leakage:** none.
- **GPU and time (est.):** needs annotated examples of each scale-bar style on our sheets, which we do not have; two to three days, not feasible by Saturday.
- **Breaks:** most plans have no ruler; the authors say plain straight rulers do worse; tick pitch on an 855 px image is 2 to 3 px; the long-side rotation rule fails for dimension lines with text.
- **Verdict: idea only.** Keep the "no match" output and the reuse of repeated styles.

### 7. LinePilot calibration code (RayanA07/LinePilot, arXiv 2609.19377): try tonight, read the code
- **What it is:** Tesseract on the image and a copy rotated 90 degrees; every pair of ticks proposes a line; ticks within 15% of the value span count as inliers; the raw extremes are overridden only when at least about two thirds of the ticks, never fewer than four, agree. A chart-axis calibrator whose structure (line ends, printed number, pair, fit, reject) is the same as a dimension line.
- **Field:** `scale`.
- **Number:** automatic OCR mode: trusted usability 38.2%, output success 55.1%; human-guided 93.3%; failure-penalised error 0.403 at 6 in x 150 DPI (about 900 px, our regime) against 0.269 at 300 DPI; the authors name image size and resolution as the main vulnerability. Synthetic plots only. Re-checked 01:23: the paper text carries 38.2% and 93.3%.
- **Licence:** Apache-2.0 (GitHub API, pushed 2026-11-09); no weights. **Leakage:** none.
- **GPU and time (est.):** no GPU; `_line_inliers` is about 50 lines; an hour to adapt.
- **Breaks:** no outlier rejection below four marks (the docstring explains: with three ticks one misread leaves two survivors and any two points form a perfect line); upright labels assumed; plans have no linear axis, so dimension lines supply the ratios; Tesseract is documented at 300 DPI and above.
- **Verdict: try tonight**, as the reference for the rejection rule and the minimum number of marks.

### 8. Liang et al., EC3 2026: median ratio with OCR corrected by geometry: idea, leakage flag
- **What it is:** CRAFT plus TPS-STN and CRNN OCR over overlapping tiles; numbers that annotate distances between parallel grid lines are grouped; the pixel-to-metre ratio is the median of OCR distance over pixel gap; an OCR value that deviates beyond a tolerance is replaced by the geometry-consistent value; total-length annotations are a consistency check.
- **Field:** `scale`, wall and opening lengths.
- **Number:** strict OCR accuracy 90.2% on its test split, 85.7% on ResBIM; strict geometric precision 71.1%; 62 of 200 plans exact on all components. Re-checked 01:23 in the PDF (90.2, 85.7, 71.1, "median ratio", the CubiCasa5k sentence). The companion paper (Autom. Constr. 191:107204) shows one global scale gives A_dim 9.77% against 76.79% with text-geometry matching; A_dim is the share of elements whose dimensions match within 0.1 mm, not a scale error.
- **Licence:** no code or weights linked; the companion repo (rogerliang0725/ifc_comparison) has no licence. **Leakage: yes**, the OCR is fine-tuned on 1,000 images from CubiCasa5K and CVC-FP, so those weights cannot be used for scored runs. ResBIM (1,000+ synthetic plans with dimension chains and ground-truth lengths; repo MIT, data on Drive with terms unchecked) is a possible local pre-training set with a domain gap.
- **GPU and time (est.):** OCR fine-tune a few GPU hours on our own crops; not tonight.
- **Breaks:** needs dimension chains in consistent orientation; fails on offset texts and overlapping chains (the authors); evaluated on synthetic plans.
- **Verdict: idea only.** Take the "replace the OCR value with the geometry-consistent one" step; do not use its weights.

### 9. UniMetric (arXiv 2610.16945): many weak size priors with intervals: idea
- **What it is:** a VLM gives a height interval and a confidence for each marked object; a weighted interval estimator combines many objects into one global scale; per-category reliability weights 0.95, 0.85, 0.70, 0.55. Role of our object: a door or fixture as a known-size object.
- **Field:** `scale` prior from doors and fixtures.
- **Number:** mean relative scale error 4.5% to 7.2% with one observation, 1.1% to 2.2% with 50, 1.7% to 2.8% with 10 (193 sequences, 13,292 frames; Table 1). Re-checked 01:23: the text reads "from 4.526-7.245% to 1.086-2.175%" and "already obtained at K = 10".
- **Licence:** paper arXiv non-exclusive licence; no code read. Leakage: n/a.
- **GPU and time (est.):** the estimator is small; the experiment (error against number of doors used) is a few hours on our dev data once doors are detected.
- **Breaks:** driving and robot scenes, whose size spread is narrower; a plan has perhaps 5 to 15 doors at 5 to 20 px, so the anchor's own pixel error is 5% to 20% of its width; door widths inside one building are likely correlated, so averaging helps less than the independent case; the paper itself says gains depend on prior quality.
- **Verdict: idea only**, and the best argument that a door prior might approach 2% only with ten or more independent marks. floorplan2bim's door curve (median 8.6% at 0 to 5 doors, 5.8% at 10 or more, share within 2% flat) says our case is weaker.

### 10. Per-sheet scale state with a verified flag and provenance (zzTakeoff, Constructable, OpenTakeoff, MicroScale Editor): copy the pattern
- **What it is:** a scale carries its source, who or what made it, and a state (not set, auto-detected, human-verified); OpenTakeoff (TypeScript, Apache-2.0) stores per measurement the scale and how it was made; its model-read scale is "only ever a suggestion" shown with a guide bar before it is applied.
- **Field:** the `scale` object's status, source and evidence.
- **Number:** none measured. One vendor (zzTakeoff) switched its on-import AI scale off for incorrect scaling; no vendor publishes a scale error (Trimble says "97% success", undefined; ThirdEye prints "+-1.5%" with no method or data; "Togal 98%" was not found).
- **Licence:** OpenTakeoff Apache-2.0 (GitHub API, pushed 2026-07-20, re-checked 01:23); it reads vector PDFs, so its scale detection is a text search and does not transfer to PNGs. **Leakage:** none.
- **GPU and time (est.):** none; schema work.
- **Breaks:** nothing computational; the products rely on a human for the verify step, and we have none at scoring time.
- **Verdict: try tonight** as design: `scale = {value, status, source, marks_used / marks_found, interval}`; map to our `scaled` / `estimated` / `no_scale` / `not_to_scale` states.

## 3. Full table

"from": a, b, c = the reports that assess it. "Read": R = read in the source by a report's author; C = the authors' or vendor's claim read on the page; S = search summary only. Licence column: code / weights. CubiCasa5K leakage: yes / no / unknown. Rows already described in section 2 are shortened.

| Method or source | Field | Year, venue | Metric (dataset, size) | Licence code / weights | CubiCasa5K leakage | Fills | Verdict | from | Read |
|---|---|---|---|---|---|---|---|---|---|
| floorplan2bim | floor plans | 2026 GitHub | median scale error 6.5%; 18/38/71% within 2/5/10% (301 plans) | none / not released | **yes** | scale, areas | try Sat (baseline) | a, c | R (README, CSV) |
| Lv et al. | floor plans | CVPR 2021 | 72/83/86% within 2/5/10% (supplement Table 2) | none found / none | no | scale | idea | a, b, c | R |
| PlanMetric | construction drawings | 2026 GitHub | 260/260 supported, 140/140 refused, 120/120 systematic errors accepted (generated) | MIT / none | no | scale evidence | try tonight (contract) | a | R |
| Dodge et al. | floor plans | MVA 2017 | OCR 74.1% of size labels, 20 plans | none stated | no | rooms.area, scale | idea | a | R |
| ResPlan | floor plans | arXiv 2508.14006 | scale from listed area; sum within +-25% on 98.7% of 17,000 plans | CC BY 4.0 paper / n.a. | no | scale prior | idea; South Asian plans only | a, b, c | R |
| Aliyev and Barsi | floor plans | PPCE 2026 | pixel count 5.68% per room; VLMs 41% to 44% (100 plans, 894 rooms) | CC BY paper, no code | no | rooms.area | baseline numbers | a, b, c | R |
| Applied Sci. 16(13):6290 | floor plans | 2026 | +-5% reference gives +-10% area; no measured area error (preprint's 0.81% withdrawn) | YOLOv8 AGPL / not released | yes (fine-tuned on it for comparison) | areas | sensitivity only | a, b, c | R |
| Buildings 2026 hybrid | construction drawings | Buildings 16(5) 1043 | OCR 89.3%; about 0.2% on examples | none / none | no | scale | try Sat (RANSAC fit) | a, b | R |
| Liang EC3 2026 | floor plans | EC3 2026 | OCR 90.2% / 85.7%; geometric precision 71.1% | none / none | **yes** | scale | idea; flag | a, b | R |
| Liang Autom. Constr. 2026 | floor plans | 191:107204 | A_dim 9.77% global scale vs 76.79% matching | none / n.a. | no | lengths | idea | a, b | R |
| Chang et al. | floor plans | Buildings 15(7) 1178 | ">95% scale accuracy" in abstract only; no table, no test-set size | none / none | no | scale; user bar fallback | idea; UI | a, b | R (body) |
| Kim et al. | floor plans | IJGI 2021 | median of dimension-line scales, else thinnest-wall mode; no scale error | none / none | no | scale | idea | a, b | R |
| FGSSNet | floor plans | arXiv 2507.10343 | wall width normalised to 24.18 px; manual on new data | none / none | yes | scale cue | idea | a | R |
| Faltin et al. (ASCE 2024) | bridge drawings | ASCE 2024 | abstract only; authors used manual scale in their 2026 evaluation | none; Zenodo record AGPL-3.0 | no | scale | idea | a, b | claim (abstract) |
| Lee et al. 2026 | floor plans | Autom. Constr. 187:106971 | "LMM scale recognition 0.707 accuracy", 12,698 plans; "accuracy" undefined | unknown | unknown | scale | unverified lead | a, b | S / abstract only |
| Schoenfelder and Koenig 2022 | floor plans | IOP 1101 | text-detector AP 90.12% at tile 256; pretrained EAST 15% to 25% | none / none | **yes** (399 images) | text boxes | evidence for tiling | a | R |
| Kratochvila et al. | floor plans | arXiv 2408.01526 | no scale module in v2 or repo | Apache-2.0 / n.a. | lists CubiCasa5k | none | skip | a, b | R |
| Architect-Ant | floor plans | arXiv 2606.10953 | door median = 0.8 m, unmeasured | n.a. | yes | scale | fallback pattern | a | R |
| Cheng et al. | floor plans | ICCAI 2022 | scale arrows hand-labelled, no scale error | n.a. | no | scale | idea | a | R |
| CADAiD | cadastre drawings | Kart og Plan 2026 | user reference line; BRA mAP50 72%; no area error | none | no | scale (UI) | UI evidence | a | R |
| SALI-FP | floor plans | arXiv 2609.25615 | no scale; evidence gates | none | uses CubiCasa5K test | none | pattern only | a, b, c | R |
| FloorplanVLM | floor plans | arXiv 2602.06507 | no metric scale; opening F1 0.7333 | none / none | no | none | negative | b, c | R |
| AECV-Bench | benchmark | arXiv 2601.04819 | OCR QA up to 0.95; door and window counts 0.34 to 0.55 | no licence | unknown | n.a. | evidence | a, c | R |
| LED-BENCH, MechVQA, DrawingVQA | benchmarks | 2026 | best 48.89% architecture; DrawingVQA is structural drawings, 92 samples | n.a.; MechVQA Apache-2.0; DrawingVQA CC BY-NC-SA | no | n.a. | evidence | a | R |
| eDOCr2 | mechanical drawings | Machines 2025 | text recall 93.75%, CER <1% (abstract) | MIT / no stated licence, Keras files fail to load on TF 2.20 | no | text | skip | a, b, c | R (repo, issues) |
| Donut + YOLO-obb parser (2506.17374, 2510.21862) | mechanical drawings | 2025 | Measures F1 0.941, hallucination 0.104; 0.923 / 0.136 | not stated; YOLO AGPL | no | dimension text | idea (oriented boxes) | a, b, c | R |
| Florence-2 on GD&T (2411.03707) | mechanical drawings | 2024 | F1 61.5% on 400 drawings; GPT-4o 35.5% | model MIT | no | text | warning | b, c | R |
| Lombardi et al. | title blocks | arXiv 2504.08645 | Scale value correct 95% of matched keys; whole-sheet read gave "110" for "1:10" | n.a. | no | printed ratio | idea | a | R |
| PaddleOCR, docTR, EasyOCR | OCR | 2026 | no data on 5 to 20 px digits; recogniser resizes crops to 48 px height | Apache-2.0 each | no | numbers | maybe (engine) | b | R (README, paper) |
| Uni-AIMS | microscopy | arXiv 2505.06918 | 0.3% length error, 0.63 px; unit and value 100% (111 images) | none; YOLOv8 AGPL | no | scale bar | idea | a, b, c | R |
| SEM YOLOv11 bar + OCR | microscopy | RSC Adv. 2026 | length error 3.86% (4.2 px); OCR 98.64% (370 bars) | n.a. | no | scale bar | pattern | c | R |
| EXSCLAIM | microscopy figures | arXiv 2103.10631 | bar MAE 5.4%, label 82% (440 figures) | GPL-3.0 | no | scale bar | idea; do not copy | a | R |
| Chen et al. SEM + LLM | microscopy | arXiv 2510.11260 | detector P 100%, R 95.8%; synthetic | none | no | scale bar | idea | a, c | R |
| Herbarium ruler matching | rulers | BISS 2026 | median 0.141% to 0.199%; no-match 2.4% to 4.1% | MIT; mixed / none | no | scale | idea | c | R |
| LeafMachine2 | rulers | APPS 2023 | 58.8% of CFs within a 0.8% manual spread; 708 of 1,275 rulers supported | GPL-3.0 | no | scale | skip (licence) | a, c | R |
| RulerNet | rulers | arXiv 2507.07077 | 1.19 +- 5.03 px/cm (1,416 images) | CC-BY-NC-4.0 code, weights, data | no | scale | idea; local only | c | R |
| Fish rulers (Konovalov) | rulers | 2017, 2018 | MARE 1% to 2% (445 images) | repo no licence | no | scale | abstract only | a, c | claim |
| Mothra | rulers in specimen photos | MEE 2022 | forewing length vs manual: slope 1.0 to 1.03, 3,145 specimens | BSD-style | no | scale (tick pitch by FFT) | idea | c | R |
| FieldPrism | field photos | APPS 2023 | -0.97% mean, SD 0.93, n = 59; QR decode falls to 15.6% at 12 MP, 1 m | not checked | no | scale | evidence | c | R |
| FreeRef-1 | forensic photos | Sensors 2023 | median under 5% mostly; one cell 117.6% from failed dot detection | not checked | no | scale | failure numbers | c | R |
| Wen et al. shoeprint ruler | forensics | Sci. Justice 2024 | scale MAPE 3%; retrieval 0.735 to 0.929 | not checked | no | scale | downstream effect | c | claim (abstract) |
| Scatteract | chart axes | arXiv 1704.06687 | RANSAC 89.2% vs plain fit 70.7%; OCR preprocessing 63.8% to 91.2% | no licence / none | no | scale | idea | c | R |
| ChartRecover | chart axes | Commun. Eng. 2026 | within 2%: scatter 0.576 to 0.639, h-bar 0.695 to 0.718, v-bar 0.701 to 0.769 with alignment | no licence | no | scale | idea | c | R |
| PLOS ONE bar-chart pipeline | chart axes | 2026 | 63.0% within 2%, 81.2% within 5% (28 charts, 292 values) | not stated | no | scale | numbers | c | R |
| figverify | vector figures | arXiv 2606.31345 | calibration error 1e-3 to 1e-4 of range; median 0.09% | MIT | no | scale | vector PDFs only | c | R |
| ChartOCR | chart axes | WACV 2021 | OCR doubles bar error (0.093 to 0.185); two-label calibration | not stated | no | scale | skip | c | R |
| PlotGround | chart reading | arXiv 2610.06825 | best of 16: 87.5% within 5%, 73.8% within 2% | n.a. | no | scale | negative | c | R |
| MeasureBench | instruments | arXiv 2510.26865 | best of 18: 30.2%; rulers and calipers 21.9% real | no licence field | no | scale | negative | c | R |
| ExChart-Bench | chart reading | arXiv 2606.29808 | best off-the-shelf Adaptive MAPE 5.94% (lenient metric) | n.a. | no | none | negative | c | R |
| CartoMapQA | maps | arXiv 2512.03558 | o1 reads bar value and unit right in 84% of 50 samples | Apache-2.0 code | no | scale | negative | c | R |
| MapReason-OSM | maps | arXiv 2606.22597 | best model consistent across two zooms about 73% | n.a. | no | scale | negative | c | claim (abstract, table) |
| Plan2Map | maps | arXiv 2606.02747 | printed scale as prior, scale-consistency score as commit signal; IoU 0.736 against 0.108 for a direct VLM | licence unverified | no | scale (design) | pattern | c | R |
| Ill-Posed by Design | scene scale | arXiv 2606.24335 | Acc@10%: 39.3% human, 36.9% text LLM, 30.8% best open VLM | CC BY 4.0 | no | scale prior | negative | c | R |
| UniMetric | scene scale | arXiv 2610.16945 | 4.5% to 7.2% (1 observation) to 1.1% to 2.2% (50) | arXiv non-exclusive | no | scale prior | idea | c | R |
| Wound fingernail reference | medical photos | BMC MIDM 2024 | PCC 0.979 / RMSE 2.55 measured; 0.875 / 8.08 default | not checked | no | scale prior | evidence | c | R |
| Radiograph calibration marker | medical imaging | PLOS ONE 2015 | marker at wrong depth: mean difference 3.0% (SD 7.3%), magnification 109% to 154% | n.a. | no | failure mode | evidence | c | R |
| Easy Leaf Area | plant imaging | APPS 2014 | area reference: phone 1.18% mean error; DSLR -4.89% from distortion | no licence | no | area reference | idea | c | R |
| Google Solar API schema | aerial roofs | 2026 | `imagery_quality` buckets; roof area "unreliable" | Apache-2.0 proto | no | UI/schema | pattern | c | R |
| QGIS Georeferencer | GIS | docs | RMS per control point, residual report | GPL | no | UI | pattern | c | R |
| Werk24 confidence | mechanical drawings | 2026 docs | 1.0 start, 0.8 review threshold, value-vs-drawn-length check | closed | no | confidence | design | b | R |
| Takeoff products: Kreo, Togal, Autodesk, Bluebeam, Procore, ConstructConnect/PlanSwift, Houzz, BuildVision, zzTakeoff, Constructable, Trimble, ThirdEye | takeoff | 2026 | no measured scale error; Trimble "97% success" undefined; ThirdEye "+-1.5%" no method | closed | no | scale (UI) | pattern only | a, b | R / C |
| OpenTakeoff | takeoff | GitHub 2026 | per-shape scale provenance, model suggestion with confirm | Apache-2.0 | no | scale (UI) | copy pattern | b | R (README) |
| Togal vs contractor (Kansas 2025; Sadeh et al. 2026) | takeoff | 2025, 2026 | counts 11 of 13 identical; areas biased low 1% to 11%; Kansas ">70% faster, within 5%" after manual adjustment | closed | no | counts vs areas | design rule | b | R / C |
| Roboflow scale-bar sets | scale bars | Roboflow Universe | 197 and 126 images; CC BY 4.0 and public domain; source unknown, no mAP | n.a. | unknown | scale bar | local training at most | b | R (page) |
| ResBIM | synthetic plans with dimensions | Autom. Constr. 181:106584 | 1,000+ plans with dimension chains | MIT repo; data terms unchecked | no | training | local only | b | R |
| DoorDet | floor plans | arXiv 2508.07714 | 4,991 images, 7.81 doors per image | not checked | **yes** (built from CubiCasa5K) | doors | flag | b | S / abstract |
| MicroScale Editor | microscopy tool | 2026 | rules: pending until confirmed, conflicts not averaged, DPI never a source | no licence | no | UI rules | pattern | c | R |

## 4. Transfers from other fields

| Field | What plays the role of our object | Why it transfers | What breaks | Code |
|---|---|---|---|---|
| Chart data extraction (Scatteract, LinePilot, ChartRecover, PLOS ONE) | a dimension line with its number is an axis tick with its label; a scale is the fitted map | same structure: mark, printed number, pair, fit, reject; Scatteract shows the number reader moves the result more (46 points) than the estimator (13 points) | ticks are 10 px in ChartRecover and our digits are 5 to 20 px; deskew fails for text rotated exactly 90 degrees or upside down, which is a third of our images; plans have no guaranteed linear axis | LinePilot Apache-2.0: usable as a reference (about 50 lines); ChartRecover and Scatteract: idea only |
| Microscopy scale bars (Uni-AIMS, EXSCLAIM, SEM pipelines) | the printed bar with its number and unit on a plan | the only measured bar-reading errors (0.3% and 3.86%) | clean synthetic-trained bars; plan bars are 1 to 2 px, often absent; a box width is not a length (box mAP50-95 0.67): measure from edges | none shippable: YOLO detectors AGPL, EXSCLAIM GPL-3.0; idea only |
| Rulers in natural-history and field photos (herbarium matching, LeafMachine2, Mothra, FieldPrism) | a repeated printed scale bar style | template matching with abstention gives 0.14% to 0.20% median; FFT of the summed bar gives tick pitch without OCR | most plans have no ruler; tick pitch on 855 px images is 2 to 3 px; the marks must be in the plane of the thing measured | herbarium repo MIT but no weights; Mothra BSD-style (2023); idea or small code |
| Forensic and medical photos (shoeprints, wounds, radiographs) | a known-size object beside the subject | a calibrated scale changes a downstream score (retrieval 0.735 to 0.929); a prior costs about 3x against a measured reference; a marker at the wrong depth gives 3% to 7% error | our "marker" is the drawing itself; phone photos of plans carry perspective, so one scale number can be wrong in one direction | idea only |
| Maps and georeferencing (QGIS, Plan2Map, map scale-bar VLMs) | a printed scale ratio plus a geometric check | scale-consistency score as a commit signal; residual report per control point; VLMs misread bar value or unit in 16% of samples and are consistent across two zooms only about 73% | no tiles to register against; our independent estimate is weaker | QGIS GPL (idea); Plan2Map licence unverified |
| Scene metric scale from object priors (UniMetric, Ill-Posed by Design) | doors and fixtures as known-size objects | many weak priors with intervals reach 1% to 2% at 10 to 50 observations; a single prior sits at 4% to 7% | plans have 5 to 15 doors at 5 to 20 px; door widths in one building are correlated | idea only |
| Photogrammetry scale bars | a printed dimension as a control mark, a held-back one as a check | control against check marks: the check error is more honest than the fit residual | community manual, marked unverified by its own authors | idea only |
| Leaf-area software with a printed known-area square | a printed total area | an area reference gives area directly and avoids squaring a length error | needs a printed total on the sheet | idea only |
| Digitiser protocols (protocols.io) | independent checks of a calibration | replot, recompute a printed statistic, use round-number granularity, digitise twice | manual protocol | idea only |
| Aerial roofs (Google Sunroof, Solar API) | a roof's area from pixel size | pitch, not pixel scale, sets the area floor (a 5 degree pitch error is about 5% to 6% area at 30 degrees; the merger takes this from report c's own arithmetic) | not our setting | schema pattern only |

## 5. Disagreements between the reports, and which holds

1. **Lv et al.: does it report a scale error?** Report b's table row says "no scale error given"; report a found the supplement's Table 2. **Report a holds**: the supplement (re-opened 01:23) gives 0.72 / 0.83 / 0.86 within 2 / 5 / 10%, with the ablations. The main text has no scale-error number.
2. **Buildings 2026: "about 0.2% scale error".** Report b ranks it first with "0.2%" and calls it the best-supported figure; report a read Table 3 as a caption only and found no aggregate. Re-checked 01:23: the text says "mean error of approximately 0.2%" for non-module examples and calls Table 3 "representative examples". **Report a holds**: it is an example-level figure, not a rate, on Chinese construction drawings with dimension chains.
3. **Liang AutCon A_dim.** An early version of report a called it "area-dimension accuracy". It is the share of BIM elements whose dimensions match the reference within 0.1 mm (report a's correction, Sec. 4.2 of the paper). It is not a scale or area error. Report a's final text holds; report b's use ("a global scale alone gives 9.77%") is correct as the share of exact elements.
4. **Aliyev and Barsi "1.58% at floor plan level".** The abstract says it (re-checked 01:23, lines 27 to 28); Table 3 prints 1.58 as the living-room MAPE; Table 2 gives 5.68 +- 7.21% over 472 plan-level room comparisons. Reports b and c quote "1.58%" for the plan level or for living rooms; report a flagged that it cannot be reconciled. **Report a's reading holds**: 5.7% for all rooms, about 1.5% for large rooms, 11% to 12% for bathrooms and balconies; the baseline's scale came from the known total.
5. **floorplan2bim: "median 6.5%" and what it means.** Report c quotes the README; report a recomputed the per-plan distribution. Merger re-run: n = 301, median 6.51%, 18 / 38 / 71% within 2 / 5 / 10%. **Both hold**; report a adds that the reference is CubiCasa5K's nominal unit and the recognition model and priors are trained and calibrated on CubiCasa5K, so a comparison on a CubiCasa-derived split is not independent.
6. **Door width as a prior: report b cites BuildVision refusing a typical door width, while Houzz and VDCI suggest calibrating on a doorway.** Both are practitioner statements. The measurement is floorplan2bim's (5.4% door-width spread in the ground truth, 7.1% median error). **For our purpose: a prior, labelled `estimated`.**
7. **floorplan2bim's door prior (0.797 m, from its ground truth) against Lv's 0.9 m and Architect-Ant's 0.8 m.** The two assumptions differ by 12.5% in scale, about 25% in area. Finnish rules require a clear width of 800 mm (rooms of a dwelling) or 850 mm (internal routes, decree 241/2017, section 4, read by report a), but a plan draws the leaf or the opening, and interior leaves come in 625, 725, 825, 925 mm (a retailer page, read by report a); a second product page gives a 9x21 module with a 900 mm opening and 825 mm leaf (report b). So a single door is a +-20% ruler. Nobody measured this on Finnish plans.
8. **Which door count helps.** Report a says more doors help (10 or more: median 5.8%); report c's UniMetric says ten or more independent priors are needed. These agree: both say a single door is weak and the effect is slow.
9. **Whether SFS 5139 or the marketing decree changes the area rule.** Report b first read amendment 567/2026 as changing the rule; its final text corrects this: 567/2026 only adds items to the manager's certificate and leaves §1 (SFS 5139) untouched. **The corrected text holds.** The uncertainty-statement rule is in a pending bill and its draft decree (HE 191/2026), not in force.
10. **Chang et al. ">95%".** Report a read the full body (94,597 characters) and found no table, no definition and no test-set size; report b took the same abstract claim as undefined. **Both hold**: treat as a claim.
11. **Fish-ruler error: "MARE 1% to 2%".** Report a and report c both read the abstract only; the full text is restricted. A claim.
12. **YOLO-class detectors.** Reports a, b and c agree they are AGPL (Ultralytics) and out for shipped code (record 0006). RT-DETR, RF-DETR (Apache-2.0) are the licence-clean replacements named by report c. Not re-verified here beyond the herbarium README.

## 6. Negative results

- **No measured scale error exists for any product.** Trimble "97% success" is undefined; ThirdEye "+-1.5%" has no method or data; "Togal 98%" is not on any Togal page; a search summary's "1.8% to 4% error across six AI platforms" is not on the page that was cited (report b, P3.50).
- **Automatic scale was withdrawn by one vendor for accuracy** (zzTakeoff, two threads). Togal in a 2025 university study "was unable to automatically set the scale" on lower-quality drawings.
- **VLMs do not give a scale or area.** Room area as a share of the total: MAPE 41% to 44% (Aliyev and Barsi). Linear-scale reading on instruments: 21.9% on real rulers and calipers for the best of 18 models (MeasureBench). Chart values within 2%: 73.8% for the best of 16 (PlotGround), and the median model is far lower. A project log recorded a VLM-guessed scale 2.6 times off (anecdote). VLMs also ignore apparent size: a 1.4x zoom moved predictions by a ratio of 1.00 in all 12 models. LoRA fine-tuning improves the prior, not the geometry. Decide "no scale" in code.
- **A strong VLM mangles a printed ratio on a whole sheet**: GPT-4o returned "110" for "1:10" on the whole drawing and the right value on a cropped title block (Lombardi et al.).
- **Off-the-shelf OCR fails on plans and small text**: pretrained EAST reaches 15% to 25% AP on CubiCasa5K (Schoenfelder and Koenig); tiling at 256 px fixed most of it. Fine-tuned readers of dimension text still invent about one value in ten (hallucination 0.104 to 0.136; 0.136 and 0.104 in two papers on the same data family; GD&T F1 61.5% for a fine-tuned Florence-2 on 400 drawings). Treat roughly 90% of dimension strings correct as the ceiling from the best open pipelines on their own data.
- **Agreement is not truth**: PlanMetric accepts wrong scales when all dimensions are wrong the same way; door-and-wall priors that agree are within 2% on only 17% of plans.
- **A mark in the wrong plane is a wrong scale** (3.0% mean, SD 7.3% for hip radiograph markers; FreeRef-1's 117.6% outlier from a failed dot detection).
- **Wall-thickness priors fail in practice**: a Korean pipeline's 200 mm exterior-wall prior was about 30% too small on a real apartment drawing (public issue, not peer reviewed); a photography firm's test found consumer scan-app plans 11.48% smaller than drafted plans, which it attributes to assumed wall thickness (competitor claim, method not given).
- **Authors of the dimension-line scale method did not use it** in their own 2026 error evaluation (they set the scale manually "to avoid introducing additional sources of error").
- **Two search summaries credited scale recovery to papers that contain none** (a symbol-detection paper, the PaddleOCR 3.0 report); both were opened and dropped. Treat any search-summary claim of a scale method as unconfirmed.
- **No recent venue paper**: WACV 2026 and CVPR 2026 titles have no scale-from-plan paper (floor plan generation, localisation, navigation only); arXiv date-sorted sweeps and the cs.CV listing 6 to 13 Nov 2026 found none beyond the items read. The 2025 to 2026 floor-plan scale work is in MDPI Buildings, EC3 and Automation in Construction.

## 7. Looked for and did not find; unverified leads; open questions

**Looked for and did not find**
- A peer-reviewed paper with scale or area error in percent on CubiCasa5K, R2V or RPLAN raster plans. The only CubiCasa5K measurement is floorplan2bim.
- A learned scale regressor from doors, fixtures or wall thickness on floor plans.
- A public raster dataset with labelled dimension lines, arrowheads and extension lines; a scale-text ("1:100", "mittakaava") OCR benchmark, on Finnish plans or otherwise.
- A study of users shown a scale as an estimate; any source that puts an error bar on the scale value itself for a raster image.
- An open scale-recovery code base we can ship: only PlanMetric (MIT, needs OCR input), LinePilot (Apache-2.0, chart axes), ImageDataExtractor (MIT, SEM bars, 150 lines, rejects bars under 5 px) and the herbarium repo (MIT, no weights or data).
- Paper-format or DPI inference from a scan (arXiv and Hugging Face queries, report c).
- How common printed dimension strings, printed areas and printed scale bars are on our sheets.

**Unverified leads (not in the ranking)**
- Lee et al. 2026 (Autom. Constr. 187:106971): abstract says LMM scale recognition "0.707 accuracy" on 12,698 plans; "accuracy" is undefined; body blocked.
- Faltin et al. ASCE 2024 (scale inference, abstract only); Schoenfelder and Koenig AEI 2025 (ontology); the Autom. Constr. 107296 review; Xu et al. survey; Knowledge-Based Systems 2025 "Measurement of Anything in Microscopy" (search summary: a YOLO-OCR with a 14,000-image scale-bar set); Konovalov fish-ruler full texts; Criminisi single-view metrology; Drevon 2017 and Aydin 2022 digitiser studies (secondary summaries); PMC13431935 and PMC13667484.
- Roboflow scale-bar sets (197 and 126 images): source and mAP unknown, could be a CubiCasa5K repackage.
- A 2025 thesis scaling from a user-supplied reference wall (restricted); US patent 11442982 (image-only PDF, not read; no legal view given).
- Planova changelog (anecdote), Sweet Home 3D door-size threads (search summary).
- Metashape control-versus-check marks: community manual, unverified by its authors.
- SFS 5139 itself (paywalled, not read).

**Open questions**
1. How many of our sheets print dimension lines, room areas, a flat total, door and window sizes, or a graphic scale bar? Every dimension-based route (items 2, 5, 7, 8) depends on this; it is one pass over the dev drawings. Two real Finnish marketing plans were read: one prints door and window sizes in mm and room areas, the other only a total, sill heights and a 0 to 5 m bar; no dimension chains on either; not a statistic.
2. Does the printed square-metre label equal the net room area on our images, and by how much does the flat total exceed the sum of rooms?
3. Is CubiCasa5K's nominal unit (100 units = 1 m) verified against a printed dimension anywhere? Any CubiCasa-based scale score inherits this; our scorer compares estimates to a reference scale (`eval/README.md`).
4. Can PaddleOCR, docTR or an equivalent read 5 to 20 px digits, rotated, at 855 px? PP-OCRv6 gives no accuracy-by-text-height data and resizes crops to 48 px height; upscaling before detection is the first lever. LinePilot's grid puts our regime near its worst cell.
5. Do we adopt PlanMetric's observation format for `scale` evidence?
6. Is the area-as-ruler bias (printed net areas against annotation polygons) the same sign and size on all sheets?
7. Do photographed plans need two scales (x and y) or a rectified flag? Nobody measured scale error on phone photos of plans.

Tools missing across the reports: no browser past ScienceDirect, SSRN, ASCE, Elsevier or MDPI bot checks (not fought); Semantic Scholar and OpenAlex rate-limited; the arXiv search page and MCP were flaky (the arXiv API via curl worked); no PDF of SFS 5139.

## 8. Experiments proposed (at most five)

1. **Count what marks our sheets carry**: on the dev drawings, count dimension strings, printed room areas, a printed total, printed opening sizes and graphic bars per sheet; the share with at least three consistent dimension strings decides whether items 2, 5, 7 and 8 are worth building at all.
2. **Prior-only baseline**: reimplement floorplan2bim Step 4 (door 0.80 m, wall thickness, printed areas, inverse-variance weights) on the dev split with our own door and wall detections, and plot scale error against number of doors used (1, 3, 5, 10); the target to beat is median 6.5% and 18% within 2%, and the curve shows whether ten or more doors approach UniMetric's 2%.
3. **Number reader at our resolution**: run an Apache-2.0 OCR (PaddleOCR or docTR) on dev crops of printed areas and dimension strings, upscaled 1x, 2x and 3x, in the original and rotated 90 and 180 degrees; the read rate for strings of 5 to 20 px and for the Finnish decimal comma settles the number-reading step before any fitting.
4. **Consensus with abstention**: feed the strings read in experiment 3 into PlanMetric and into a largest-cluster fit; the share of sheets that return `scaled` within 2% of gold and the share of refusals (target: no wrong `scaled`) settle whether two-mark agreement can be trusted.
5. **Printed total plus pixel share**: on sheets with a printed flat total, compute scale from total over summed room pixels and compare with the printed room areas; the median disagreement settles the net-versus-total bias.

## 9. Sources and checks

Re-checked 2026-11-14, 01:23 by the merger (machine clock): floorplan2bim README lines for 6.5%, 7.1%, 9.1%, 18.8%, 38.3% and the per-plan recomputation (301 plans, median 6.51%, 18 / 38 / 71% within 2 / 5 / 10%); PlanMetric MIT licence, push date and validation.md figures; Lv supplement Table 2 (PDF text); Aliyev and Barsi Table 2, Table 3 and abstract; EC3 2026 PDF (90.2%, 85.7%, 71.1%, median ratio, CubiCasa5k); Buildings 2026 page text (RANSAC, 89.3%, 0.2%); herbarium XML (0.199, 0.141, 94.8, 99.0, 2.40, 4.07) and the two repositories' MIT licences; LinePilot Apache-2.0 and paper text (38.2%, 93.3%); UniMetric text (4.526 to 7.245%, 1.086 to 2.175%, K = 10); ResPlan text (gross-area scale, 98.7% within +-25%); Dodge text (74.1%); OpenTakeoff Apache-2.0 and README scale sentences. Not re-opened: Uni-AIMS, Scatteract, the chart papers, the product pages and the Finnish legal texts (read by the reports as cited). Numbers about our own data come from `docs/research/lit-campaign/worker-brief.md` and `eval/README.md` only.
