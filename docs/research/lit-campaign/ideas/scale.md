# Scale

18 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i261"></a>
### 261. Take the largest consistent cluster of per-mark scales, not the mean

- What: Compute a scale per dimension pair or mark, cluster them, keep the largest cluster and average it.
- Evidence (floor-plans): Lv et al. supplement Table 2: 72% within 2% with K-means and digit count against 45% without both.
- Source: [openaccess.thecvf.com](https://openaccess.thecvf.com/content/CVPR2021/supplemental/Lv_Residential_Floor_Plan_CVPR_2021_supplemental.pdf)
- Licence: no code / no weights. CubiCasa5K leakage: no.
- Cost: 2 h for the fit; dimension labels we lack for the reader
- Experiment: Fit on synthetic pairs with injected wrong readings first; then on read pairs from dev.
- What breaks on our images: Needs dimension pairs, which our sheets may not carry.
- Moves: scale-areas. Why this group: The measured part of Lv et al.
- Also (scale, adjacent-field): RANSAC or median over per-dimension ratios. Per dimension, ratio = printed value over pixel length; reject outliers by RANSAC or take the median; require at least four marks, else use an outside prior to break ties. Evidence: Buildings 2026: OCR 89.3%, about 0.2% on examples (no aggregate); Scatteract RANSAC 89.2% vs plain fit 70.7%; LinePilot needs four ticks and a two-thirds supermajority. Source: [mdpi.com](https://www.mdpi.com/2075-5309/16/5/1043), [arXiv 1704.06687](https://arxiv.org/abs/1704.06687), [github.com](https://github.com/RayanA07/LinePilot). Experiment: Synthetic pairs with 1 in 8 wrong strings, then dev pairs; report share within 2%.
- Reports: lit-scale-a, lit-scale-b, lit-scale-c

<a id="i262"></a>
### 262. Adopt PlanMetric's accepted / insufficient / conflict output

- What: Use its observation format and three states: accepted per axis, insufficient, conflict, with rejected pairs listed; area needs both axes accepted.
- Evidence (floor-plans): Own generated validation: 260/260 supported correct, 140/140 unsupported refused, 120/120 systematic-error axes accepted wrong.
- Source: [github.com](https://github.com/crown-sports/planmetric)
- Licence: code MIT. CubiCasa5K leakage: n/a.
- Cost: a day
- Experiment: Feed our OCR boxes and spans on dev; target no wrong accepted.
- What breaks on our images: Needs dimension text; agreement cannot prove the readings.
- Moves: trust. Why this group: Cleanest abstention contract found.
- Reports: lit-scale-a, lit-scale-b

## Try next

<a id="i263"></a>
### 263. Fuse door width, wall thickness and printed-area priors by inverse variance

- What: Reimplement Step 4: door 0.80 m (spread 5.4%), exterior wall 0.245 m (20%), interior wall 0.120 m (16%), printed areas (3%), inverse-variance weights, drop the area estimate if it differs by over 35%.
- Evidence (floor-plans): Median scale error 6.5%, 18/38/71% within 2/5/10% on 301 single-storey CubiCasa5K test plans; doors alone 7.1%; 8.9% median under 1,200 px.
- Source: [github.com](https://github.com/jjjzhu-5847/floorplan2bim)
- Licence: code: none stated (reimplement) / weights not released. CubiCasa5K leakage: yes.
- Cost: half a day, no GPU beyond the door and wall detectors
- Experiment: Run on dev with our detections; compare to median 6.5% and 18% within 2%.
- What breaks on our images: Door IoU 0.52 even in their tuned model; our images are smaller; the nominal unit is unverified.
- Moves: scale-areas. Why this group: Baseline to beat and the only CubiCasa5K measurement.
- Also (scale, adjacent-field): Combine many weak size priors with reliability weights and intervals. Give each door, window and fixture an interval and a reliability weight (0.95/0.85/0.70/0.55) and combine them with a weighted interval estimator; report the interval. Evidence: UniMetric Table 1 and appendix C (193 sequences). Source: [arXiv 2610.16945](https://arxiv.org/html/2610.16945). Experiment: Same dev experiment as the door-count curve; compare interval coverage to the 6.5% baseline.
- Reports: lit-scale-a, lit-scale-c

<a id="i264"></a>
### 264. Read the printed 0-5 m graphic scale bar on Finnish marketing plans

- What: Find the alternating-block bar and its digits and use its length as a ruler.
- Evidence (floor-plans): One real brochure prints only total, sill heights and a 0-5 m bar; no dimension chains.
- Source: [pohjolarakennus.fi](https://www.pohjolarakennus.fi/wp-content/uploads/2026/05/Tampereen-Potretti-Ennakkomarkkinointiesite-1.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Count sheets with a bar; measure bar-based scale against gold.
- What breaks on our images: Two plans seen; bar may be resized with the image.
- Moves: scale-areas. Why this group: Depends on the sheet census.
- Also (floorplan, authors-claim): Scale: detect bar or ratio, crop at full resolution, read. Detect scale text or bar, crop original resolution, read with a VLM to JSON. Evidence: Detector mAP50 0.992 on about 1,000 maps (poster abstract, claim). Source: [cagis.org](https://www.cagis.org/). Experiment: Scale exact on dev.
- Also (scale, adjacent-field): Measure a printed bar from edges, not box width. Detect the bar with a box, then find its ends by edge and peak search inside the box and read value and unit with OCR. Evidence: Uni-AIMS 0.3% mean length error, 0.63 px (111 real SEM images); box-width module 3.86% (4.2 px); detector mAP50 0.98 but mAP50-95 0.67. Source: [arXiv 2505.06918](https://arxiv.org/abs/2505.06918). Experiment: Hand-label bars on dev sheets that have one; length error in px.
- Reports: lit-floorplan-c, lit-scale-a, lit-scale-b, lit-scale-c

<a id="i265"></a>
### 265. Scale from printed room areas

- What: Read a printed room area, divide by the room's pixel area, vote across rooms.
- Evidence (floor-plans): floorplan2bim: 3.1% median with exact rooms, 7.9% with recognised rooms (21% of plans); Dodge OCR 74.1% of size labels on 20 plans.
- Source: [mva-org.jp](https://www.mva-org.jp/Proceedings/2017USB/papers/10-01.pdf), [github.com](https://github.com/jjjzhu-5847/floorplan2bim)
- Licence: none stated. CubiCasa5K leakage: unknown.
- Cost: hours once OCR exists
- Experiment: Dev sheets with printed areas: median scale error and share within 2%.
- What breaks on our images: Printed net areas run below annotation polygons; not on all sheets; decimal commas.
- Moves: scale-areas. Why this group: Fits sheets without dimension chains.
- Also (scale, floor-plans): Room areas from a printed flat total and pixel shares. area_room = total x pixels_room / pixels_total, with a net-versus-total bias term. Evidence: Pixel counting 5.68% per room with known total (Aliyev and Barsi Table 2); VLMs 41-44%. Source: [pp.omikk.bme.hu](https://pp.omikk.bme.hu/ci/article/download/44138/24640/262788). Experiment: Compare to printed room areas on dev sheets; median disagreement.
- Reports: lit-scale-a, lit-scale-b

<a id="i266"></a>
### 266. Scale from printed dimension strings

- What: Read dimension numbers and build a metric reference grid.
- Evidence (authors-claim): Strict OCR 90.2% in domain, 85.7% external; 71.1% strict geometric precision; 62 of 200 plans right.
- Source: [ec-3.org](https://ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf)
- Licence: none found. CubiCasa5K leakage: unknown.
- Cost: days
- Experiment: Belongs to scale scope: count dev plans with strings.
- What breaks on our images: Few plans may carry strings.
- Moves: scale-areas. Why this group: best measured scale source
- Reports: lit-rooms-b, lit-rooms-c

## Later

<a id="i267"></a>
### 267. Replace an OCR dimension value that disagrees with geometry

- What: After a median ratio, compare each OCR value to the geometry-implied value and replace it when it deviates beyond a tolerance.
- Evidence (floor-plans): EC3 2026: OCR strict 90.2%/85.7%, geometric precision 71.1%.
- Source: [ec-3.org](https://ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf)
- Licence: no code / OCR weights trained on CubiCasa5K. CubiCasa5K leakage: yes.
- Cost: half a day
- Experiment: Inject misread digits into dev pairs, measure the share repaired.
- What breaks on our images: Needs consistent orientation and chains; their weights cannot be used.
- Moves: scale-areas. Why this group: Only after a number reader exists.
- Reports: lit-scale-a, lit-scale-b

<a id="i268"></a>
### 268. Read printed scale (1:100) and dimension strings with the same reader

- What: Use the fine-tuned reader on dimension numbers and a printed 1:N scale to give metres per pixel.
- Evidence (floor-plans): CRAFT plus TPS-STN-CRNN read dimension numbers 90.2% exact (own test) and 85.7% (external set) after 1,000-plan fine-tune (EC3 2026); door and window size codes read 0/32 and 0/40 with v5.
- Source: [ec-3.org](https://www.ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 4 h work (estimate)
- Experiment: Read dimension strings on dev plans with known scale and compare derived scale to the label.
- What breaks on our images: Digits only in the paper; v6 untested on size codes.
- Moves: scale-areas. Why this group: belongs to the scale scope
- Reports: lit-ocr-a, lit-ocr-c

<a id="i269"></a>
### 269. Plot prior-scale error against number of doors used

- What: Estimate scale from door-width priors with per-class reliability weights using 1, 3, 5 and 10 doors per plan and plot the error.
- Evidence (adjacent-field): UniMetric: 4.5-7.2% at one observation, 1.1-2.2% at 50, 1.7-2.8% at 10; floorplan2bim: 8.6% median at 0-5 doors, 5.8% at 10 or more, share within 2% flat.
- Source: [arXiv 2610.16945](https://arxiv.org/html/2610.16945)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: few hours
- Experiment: Dev split; if error falls from about 7% to about 2% at ten doors a door-based route earns a place beside printed areas.
- What breaks on our images: Door widths in one building are correlated; anchors are 5-20 px.
- Moves: scale-areas. Why this group: Decides whether priors can reach 2% at all.
- Reports: lit-scale-a, lit-scale-c

<a id="i270"></a>
### 270. Estimate scale from a door of nominal width and say it is an estimate

- What: When no scale is printed, set a reference length (door width) to convert pixels to metres and mark the area as an estimate.
- Evidence (adjacent-field): MDPI Applied Sciences 2026 pipeline sets scale from a user-given 90 cm door opening; Agent2BIM: without a metric reference recall collapses (11% to 43% against 75% to 93%).
- Source: [mdpi.com](https://www.mdpi.com/2076-3417/16/13/6290), [arXiv 2611.10644](https://arxiv.org/abs/2611.10644)
- Licence: AGPL detector in the paper. CubiCasa5K leakage: unknown.
- Cost: 2 h (estimate)
- Experiment: Compare estimated area to printed area on dev plans.
- What breaks on our images: Opposes BuildVision's advice; only as a flagged fallback.
- Moves: scale-areas. Why this group: disputed practice
- Reports: lit-market-a, lit-market-b

<a id="i271"></a>
### 271. Per-image scale self-calibration before tiling

- What: Estimate mean symbol size per image to set the tile size, or use 2-3 candidate scales and pick by detection agreement.
- Evidence (adjacent-field): Electron-microscopy dislocation counting: tile = 10 x object size, count-tuned threshold 0.025, 98.6% (author claim) on thousands of objects; 5-15 s per image.
- Source: [arXiv 2608.28495](https://arxiv.org/abs/2608.28495)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: est. 3 h
- Experiment: Only if scale varies within a plan style.
- What breaks on our images: 8-25 h for all files at 5-15 s; single digits count.
- Moves: scale-areas. Why this group: Tied to the scale stage
- Reports: lit-detect-c

<a id="i272"></a>
### 272. Median door 0.9 m as default scale

Reviewer's note: Only as one witness next to others, never alone: unmeasured on Finnish plans.

- What: Use door width when no scale is printed.
- Evidence (authors-claim): Lv CVPR 2021 default.
- Source: [openaccess.thecvf.com](https://openaccess.thecvf.com/content/CVPR2021/papers/Lv_Residential_Floor_Plan_Recognition_and_Reconstruction_CVPR_2021_paper.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Error against known scale on dev.
- What breaks on our images: Doors vary; flag as estimate.
- Moves: scale-areas. Why this group: fallback
- Also (scale, search-only): Do not use one door width as the scale. A single door is a +-20% ruler (leaf widths 625-925 mm); do not label it scaled. Evidence: Finnish retailer page; fingernail prior costs 3x error; 0.8 vs 0.9 m assumptions differ 12.5%. Source: [finlex.fi](https://www.finlex.fi/api/media/statute/61314/mainPdf/main.pdf). Experiment: none
- Reports: lit-rooms-b, lit-scale-a, lit-scale-b, lit-scale-c

<a id="i273"></a>
### 273. Use printed door and window sizes in mm as known lengths

- What: Where a plan prints '910 x 2 110' beside a door, match the width to the drawn opening and vote like dimension pairs.
- Evidence (search-only): One real plan prints all door and window sizes; not measured.
- Source: [sivakka.fi](https://sivakka.fi/tampuuri/attachments/manual-floorplan-menninkaisentie3c69)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: Count sheets with opening sizes; error on those.
- What breaks on our images: Two plans seen.
- Moves: scale-areas. Why this group: Better than a width prior if present.
- Reports: lit-scale-b

## Idea or pitch only

<a id="i274"></a>
### 274. Wall thickness as a ruler

- What: Wall prior alone is weak: exterior walls 18.8% median, one 200 mm prior 30% off.
- Evidence (floor-plans): floorplan2bim; Korean issue; consumer scan apps 11.48% smaller.
- Source: [github.com](https://github.com/Auto-BIM/autobim-be)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: scale-areas. Why this group: Use only inside fusion.
- Also (scale, authors-claim): Wall width from run-length histogram mode. Histogram consecutive-pixel runs along x and y, take the mode as thinnest wall, use as a text-free cue. Evidence: Kim et al. 2021; no scale error reported; FGSSNet 24.18 px normalisation. Source: [mdpi.com](https://www.mdpi.com/2220-9964/10/12/828). Experiment: Correlation of mode with gold scale on dev.
- Reports: lit-scale-a, lit-scale-b

<a id="i275"></a>
### 275. Match a scale-bar style to a template with no-match output

- What: Retrieve similar annotated bar styles and match keypoints; output no-match when under 10 pairs.
- Evidence (adjacent-field): Median CF error 0.141-0.199%, no-match 2.4-4.1% (herbarium rulers).
- Source: [biss.pensoft.net](https://biss.pensoft.net/article/183602/download/xml/)
- Licence: code MIT; no weights; Meta licences for DINOv3 and SAM 3. CubiCasa5K leakage: no.
- Cost: 2-3 days plus annotation
- Experiment: Needs labelled bar styles first.
- What breaks on our images: Most plans have no ruler; simple lines do worse.
- Moves: scale-areas. Why this group: Too much annotation for Saturday.
- Reports: lit-scale-c

<a id="i276"></a>
### 276. Tick pitch of a bar by FFT of the summed profile

- What: Sum the bar crop across its width and take the dominant frequency as the tick pitch; use as second estimate beside OCR.
- Evidence (adjacent-field): Mothra: 3,145 specimens, forewing slope 1.0-1.03 against manual.
- Source: [biorxiv.org](https://www.biorxiv.org/content/10.1101/2021.12.21.473511v1.full)
- Licence: BSD-style. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Test on dev sheets with a bar; compare to OCR value.
- What breaks on our images: Ticks 2-3 px apart; needs straight even ticks.
- Moves: scale-areas. Why this group: Needs bars.
- Reports: lit-scale-c

## Do not try (with the reason)

<a id="i277"></a>
### 277. A bar from a reduced copy or other plane is a wrong scale

- What: A mark off the drawing's plane (photo, reduced copy) carries a bias a robust fit cannot remove; use a second route.
- Evidence (adjacent-field): Hip radiographs 3.0% (SD 7.3%); FreeRef-1 117.6% outlier.
- Source: [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4500467/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: Plane error.
- Reports: lit-scale-c

<a id="i278"></a>
### 278. Ask a VLM for scale or area

- What: Do not use VLM scale or area guesses; use at most as plausibility prior, decided in code.
- Evidence (adjacent-field): VLM MAPE 41-44% (Aliyev); MeasureBench 21.9% rulers; PlotGround 73.8% within 2%; zoom ignored (ratio 1.00).
- Source: [arXiv 2606.24335](https://arxiv.org/html/2606.24335), [arXiv 2510.26865](https://arxiv.org/html/2510.26865)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: scale-areas. Why this group: Measured poorly.
- Also (scale, adjacent-field): LoRA tuning a VLM for metric size. Fine-tuning improves the prior, not geometry. Evidence: Ill-Posed by Design: +2.1 to +11.6 points via priors. Source: [arXiv 2606.24335](https://arxiv.org/html/2606.24335). Experiment: none
- Reports: lit-scale-a, lit-scale-b, lit-scale-c
