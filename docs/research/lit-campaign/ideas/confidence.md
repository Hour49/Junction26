# Confidence and abstention

47 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i286"></a>
### 286. Plain max confidence as the baseline every fancier score must beat

Reviewer's note: The baseline every other confidence score has to beat. On its own it carries no guarantee.

- What: Report failure AUROC and AUGRC of plain (temperature-scaled) confidence first; accept a learned or ensemble score only if it beats it on dev.
- Evidence (floor-plans): No evaluated score beat maximum softmax across failure sources (2211.15259); plain confidence lifted floor-plan symbol accuracy 86.6 to 88.9 at a 50% budget, BALD 89.2 (Jakubik Table 3).
- Source: [arXiv 2211.15259](https://arxiv.org/abs/2211.15259), [cdn.aaai.org](https://cdn.aaai.org/ojs/21522/21522-13-25535-1-2-20220628.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Report AUGRC (2407.01032) per candidate.
- What breaks on our images: Classification evidence, not counts.
- Moves: trust. Why this group: Sets the bar.
- Also (ocr, adjacent-field): Abstain below a reader confidence and send low-confidence labels to review. Use per-box recogniser confidence as a gate: below a threshold a label is not counted but goes to the second reader or to a not-read flag. Evidence: Plate entry: abstention below 0.33 gave +0.11 on a score where wrong costs -1; the competition scores a confidence gap; water-meter rejection lifts accepted reads to 99% or more (arXiv 2009.10181); OCR token confidence as a quality gate (AHFE 2025, abstract). Source: [arXiv 2607.08896](https://arxiv.org/abs/2607.08896), [arXiv 2009.10181](https://arxiv.org/abs/2009.10181), [arXiv 2604.22506](https://arxiv.org/abs/2604.22506). Experiment: Plot precision against coverage by confidence threshold on dev crops; pick the threshold per room type.
- Also (trust, adjacent-field): Threshold tuned until calibration risk looks right. Do not call a tuned threshold 'risk controlled'. Evidence: Broke the budget in 49-73% of trials (2606.15153). Source: [arXiv 2606.15153](https://arxiv.org/abs/2606.15153). Experiment: none
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c, lit-trust-a, lit-trust-b, lit-trust-c

<a id="i287"></a>
### 287. Call a scale 'scaled' only if two independent printed marks agree within 2%

- What: Upgrade estimated to scaled only when two independent printed marks (dimension pairs, printed total with a bar or dimension, printed opening size with a dimension) agree within 2%. Door and wall priors alone never qualify.
- Evidence (floor-plans): Door and wall priors that agree within 5% are within 2% on only 17% of 298 plans (own analysis of floorplan2bim per-plan file).
- Source: [github.com](https://github.com/jjjzhu-5847/floorplan2bim)
- Licence: n/a. CubiCasa5K leakage: unknown.
- Cost: 1 h
- Experiment: On dev, count wrong 'scaled' claims against gold with and without the rule; target zero wrong scaled at useful coverage.
- What breaks on our images: Needs a second mark that many sheets may not carry.
- Moves: trust. Why this group: Agreement of priors is not a certificate.
- Also (market, adjacent-field): Recover scale from dimension strings, then scale bar, then a stated dimension; refuse if they disagree. Take scale from several independent witnesses and flag the sheet when they disagree; never substitute a typical door width for a stated dimension. Evidence: roomgraph: dimension strings, then title block, then door widths; BuildVision docs: validate printed scale, 'do not substitute a typical door width'; area error is the square of scale error (1.5x error turns 20 m2 into 45 m2). Source: [github.com](https://github.com/aec-platform/roomgraph), [docs.buildvisionai.com](https://docs.buildvisionai.com/takeoff/calibration). Experiment: Compare witnesses on dev plans that have a scale and report agreement.
- Reports: lit-market-a, lit-market-b, lit-scale-a, lit-scale-b

<a id="i288"></a>
### 288. Plan-level sure/review gate with Learn-then-Test (MAPIE)

- What: Score each plan, label it right when every answer is right, and run MAPIE BinaryClassificationController (risk precision, fwer_method bonferroni) to pick the threshold; set abstain for plans below it.
- Evidence (adjacent-field): LTT selective-classification demo alpha 0.15 delta 0.1 over 100 splits (section 3.2); follicle counting kept precision above a 0.4 target on 100 splits while the naive threshold failed in almost half (2501.14036).
- Source: [arXiv 2110.01052](https://arxiv.org/abs/2110.01052), [github.com](https://github.com/scikit-learn-contrib/MAPIE)
- Licence: code BSD-3-Clause (MAPIE), MIT (LTT) / no weights. CubiCasa5K leakage: n/a.
- Cost: 2 h work, no GPU (estimate)
- Experiment: On dev split, resplit by plan 50 times: certify at alpha 0.10 delta 0.10 on one half, measure precision of accepted plans on the other; settles whether the sentence 'sure plans are wrong at most 10%' can be stated.
- What breaks on our images: Needs weak-score-free calibration answers from a model not trained on those plans; default Holm method may certify nothing (reported by one report); plans, not answers, are the unit.
- Moves: trust. Why this group: Only ready tool for the claim and runs on dev data now.
- Also (market, adjacent-field): Pick the review threshold with learn-then-test risk control. Choose the abstain threshold so that error among answered counts stays under a target with a finite-sample guarantee, using dev as the calibration set. Evidence: Blot et al. 2025: a 35-cut calibration set gave usable precision guarantees for follicle counting; SeqCRC count losses on COCO keep large predicted sets (15 to 24 boxes); 2609.20110 uses conformal risk control on fused scores. Source: [arXiv 2501.14036](https://arxiv.org/abs/2501.14036), [arXiv 2505.24038](https://arxiv.org/abs/2505.24038), [arXiv 2609.20110](https://arxiv.org/abs/2609.20110). Experiment: On dev scores, compute the threshold for a 10% error target; check it holds on a held-out half of sheets.
- Reports: lit-market-c, lit-trust-a, lit-trust-b, lit-trust-c

<a id="i289"></a>
### 289. Accuracy at a stated coverage: answer x% at y% exact, refuse the rest

- What: Build a per-answer score from per-symbol detector scores, sweep a threshold on dev, publish the exact-count rate against the share of questions answered, and refuse below the threshold.
- Evidence (adjacent-field): Rossum default 0.975 means at most 2.5% error on auto-sent documents (docs, deprecated page); ChestLink 99.1% sensitivity at 7.8% coverage (Radiology 2023 abstract); Open Buildings publishes per-region thresholds for 80/85/90% precision.
- Source: [developers.rossum.ai](https://developers.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum), [sites.research.google](https://sites.research.google/gr/open-buildings/)
- Licence: closed services; ideas only. CubiCasa5K leakage: n/a.
- Cost: 4 h, no GPU (estimate)
- Experiment: On dev, plot exact rate against coverage; the claim holds if exact rate at 70% coverage is at least 10 points above the 55.3% baseline.
- What breaks on our images: A 9-window plan answered 8 is simply wrong; per-answer calibration must be built and tested, none of the sources do it for counts.
- Moves: trust. Why this group: the one claim no competitor makes
- Reports: lit-market-a, lit-market-c

<a id="i290"></a>
### 290. Exact binomial (Clopper-Pearson) upper bound on error of accepted answers

- What: Sort dev answers by score, bound the error of the accepted set with the exact binomial tail, binary-search the threshold with delta split by log2 m; use it as independent check of the MAPIE gate.
- Evidence (adjacent-field): CIFAR-10 delta 0.001: target 0.01 gives test risk 0.0092 at coverage 0.7856, bound 0.0099 (Table 1); ImageNet 2% top-5 error at 99.9% and about 60% coverage (abstract).
- Source: [arXiv 1705.08500](https://arxiv.org/abs/1705.08500)
- Licence: idea only, about 20 lines. CubiCasa5K leakage: n/a.
- Cost: 1 h work, no GPU (estimate)
- Experiment: Same resplit as the Learn-then-Test run; compare the thresholds and the violation rates of the two recipes.
- What breaks on our images: i.i.d. only; answers of one plan correlate; binary search assumes roughly monotone risk.
- Moves: trust. Why this group: Cheapest exact statement and a cross-check.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i291"></a>
### 291. P(modal count) and count entropy from calibrated detection scores

- What: Calibrate per-detection scores after NMS, compute the Poisson-binomial count distribution per class, use P(reported count) and entropy as plan score; add a Poisson term for undetected symbols.
- Evidence (adjacent-field): Post-hoc count accuracy 86.5% vs 76.6-82.9% for parametric heads, 1,067 patients, counts 0-3+ (Table C.2 of 2204.05276); calibration shown as a figure only.
- Source: [arXiv 2204.05276](https://arxiv.org/abs/2204.05276), [arXiv 2203.07980](https://arxiv.org/abs/2203.07980)
- Licence: idea only (data proprietary). CubiCasa5K leakage: n/a.
- Cost: 1 h work, no GPU beyond raw detector scores (estimate)
- Experiment: Compute on dev detections and report failure AUROC against exact-count correctness per class and per plan.
- What breaks on our images: Independence wrong for duplicates and neighbouring windows; counts about 9 not 0-3.
- Moves: trust. Why this group: A few lines, no training, first candidate score.
- Also (count, adjacent-field): Count distribution from calibrated box scores; mode and its mass. Treat each box score as an existence probability, compute the Poisson-binomial distribution by recursion new[k]=dist[k](1-p)+dist[k-1]p, answer with the mode, abstain when its mass is low. Evidence: Count accuracy 87.6-88.7%, ECE 0.72e-5 on lesion MRI (arXiv 2204.05276); no paper on box detectors; three citing works, none on counting. Source: [arXiv 2204.05276](https://arxiv.org/abs/2204.05276). Experiment: Dev slice: calibrate per class, reliability of P(count = predicted) in 5 bins, abstain threshold; keep if high-mass plans are clearly more exact.
- Reports: lit-count-a, lit-count-b, lit-count-c, lit-trust-a

<a id="i292"></a>
### 292. Always report how often the gate opens

- What: State alpha, delta, the share of plans released and what happens when the gate stays closed.
- Evidence (adjacent-field): A valid procedure that rarely fires can be wrong in up to 69% of draws in which it fires (Proposition 3 of 2610.09541).
- Source: [arXiv 2610.09541](https://arxiv.org/abs/2610.09541)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Add released share and per-source released share to every scored gate run.
- What breaks on our images: None beyond the extra bookkeeping.
- Moves: trust. Why this group: Free and prevents a misleading claim.
- Reports: lit-trust-b, lit-trust-c

<a id="i293"></a>
### 293. Evaluate the threshold with sheet-level resampling and a fit/validation split

- What: Items on a sheet are correlated. Fit any learned confidence on one split, choose the threshold on another, and bootstrap the accepted-set error over sheets; state how many sheets stand behind the figure.
- Evidence (adjacent-field): arXiv 2608.14639: design effect 1.84 to 2.45; same-field fitting gives coverage 0.416 at risk 0.127 against a 0.10 target (violated in 95% of splits); fit/validation 0.318 at 0.096.
- Source: [arXiv 2608.14639](https://arxiv.org/abs/2608.14639)
- Licence: paper CC BY; code Apache-2.0 per abstract. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: Compute the accepted-set error with and without sheet-level resampling on dev; a gap above 2 points means the naive curve is optimistic.
- What breaks on our images: The paper's signals are OCR and log-probabilities on text.
- Moves: trust. Why this group: keeps the headline honest
- Reports: lit-market-c

<a id="i294"></a>
### 294. Gate with three states: pass, fail with reason, could not assess

- What: Output pass, fail (reason) or could not assess per sheet and treat 'could not assess' as abstain, never as a default of one plan.
- Evidence (adjacent-field): OFIQ writes a FailureToAssess return code instead of a number when a dependent measure cannot be computed.
- Source: [github.com](https://github.com/BSI-OFIQ/OFIQ-Project)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: 30 min work
- Experiment: Count how many dev sheets land in each state.
- What breaks on our images: None.
- Moves: trust. Why this group: Costless design rule for the answer stage.
- Reports: lit-sheet-b

<a id="i295"></a>
### 295. Image score from the few most confident detections, not the sum

- What: Aggregate confidences as the mean of the top 2-3 detections or max, and compare with sum, mean and entropy of the count.
- Evidence (adjacent-field): Top-3 mean AUROC 94.1-97.7 vs sum 18.8-85.8 for rejecting out-of-distribution images (2307.00934 Table 2); top-100 mean correlates -0.6 with AP (2412.01782).
- Source: [arXiv 2307.00934](https://arxiv.org/abs/2307.00934), [arXiv 2412.01782](https://arxiv.org/abs/2412.01782)
- Licence: code CC BY-NC-SA (idea only). CubiCasa5K leakage: n/a.
- Cost: 30 min work
- Experiment: Add as candidates to the failure-AUROC table; also use as an 'is this a plan at all' reject score.
- What breaks on our images: Our symbols are borderline detections, the opposite regime.
- Moves: trust. Why this group: Three lines and a known pitfall.
- Reports: lit-trust-a, lit-trust-c

## Try next

<a id="i296"></a>
### 296. Build the review list around missed items, not false ones

- What: AECV-Bench error structure shows the top models undercount on average and are off by exactly one on 26% to 31% of plans. Order the review list by likely missed symbols and check the off-by-one case first.
- Evidence (floor-plans): Recomputed from AECV-Bench result files: best door exact 0.43, off by one 0.29, three or more 0.12; window three or more 0.20 to 0.29; net bias negative for all four top models (Claude Fable 5 windows -1.18 per plan).
- Source: [github.com](https://github.com/AECFoundry/AECV-Bench)
- Licence: none. CubiCasa5K leakage: unknown.
- Cost: 2 h on our own dev errors (estimate)
- Experiment: On dev, tabulate signed count error per class for our detector; if undercounting dominates, a recall-first review list should catch most wrong plans.
- What breaks on our images: Models there are zero-shot VLMs; a trained detector may over-count through duplicates instead.
- Moves: trust. Why this group: tells where reviewer time goes
- Reports: lit-market-a, lit-market-b

<a id="i297"></a>
### 297. Sanity band: summed rooms within +-25% of a listed area

- What: When a gross area is printed, flag scales whose summed room area falls outside +-25%.
- Evidence (floor-plans): ResPlan: 98.7% of 17,000 plans within +-25%.
- Source: [arXiv 2508.14006](https://arxiv.org/pdf/2508.14006)
- Licence: data CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Rate on dev sheets.
- What breaks on our images: South Asian plans only; not a 2% route.
- Moves: trust. Why this group: Coarse guard.
- Reports: lit-scale-c

<a id="i298"></a>
### 298. Count spread across rotations, tile offsets and scales

- What: Run the detector on four rotations and two tile offsets, compare counts per class and use spread or release only when views agree.
- Evidence (adjacent-field): Four-rotation averaging +7.3 opening and +11.5 icon accuracy (1904.01920); GRC cut CER 110.5 to 8.4 at 89.5% coverage (2603.19790); but count stability alone near chance on KITTI (2509.12871).
- Source: [arXiv 2603.19790](https://arxiv.org/abs/2603.19790), [arXiv 2509.12871](https://arxiv.org/abs/2509.12871), [arXiv 1904.01920](https://arxiv.org/abs/1904.01920)
- Licence: code MIT (GRC) / CubiCasa5K code and weights CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 3 h work, 1 GPU-h on 12 GB (estimate)
- Experiment: Add spread as a feature and report its AUROC alone and in the classifier.
- What breaks on our images: Views share blind spots; tile edges double count.
- Moves: trust. Why this group: Cheap feature, mixed evidence.
- Also (detect, authors-claim): Shift test-time augmentation against confidence flips. Average predictions over image shifts at {0, P/2}^2 (P = patch period) or use a tile stride that is not a multiple of the patch period, then fix the count threshold on dev with that in place. Evidence: RF-DETR issue 1599: same tile shifted by whole pixels, confidence 0.91 to 0.49 to 0.88 while box IoU stays above 0.9; shift TTA cut median per-object confidence range 0.118 to 0.032 in an offline simulation (community report, not maintainer-confirmed). Source: [github.com](https://github.com/roboflow/rf-detr/issues/1599). Experiment: Measure count stability: same plan shifted 0-16 px, fraction of plans whose count changes.
- Also (trust, search-only): Paste or erase one known symbol and require the count to move by exactly one. Edit the image by adding or removing a symbol and check that the count changes by one; catches misses identical in every view. Evidence: Commutation theory for chart reading (2608.05675, abstract); object insertion tests for detectors (MetaOD, summary). Source: [arXiv 2608.05675](https://arxiv.org/abs/2608.05675). Experiment: Run on 100 dev plans and compare with failures.
- Reports: lit-detect-b, lit-trust-a, lit-trust-c

<a id="i299"></a>
### 299. Show inliers over marks and residual as the estimate flag

- What: Expose the inlier count over mark count and residual spread beside the scale.
- Evidence (adjacent-field): LinePilot computes both; QGIS reports RMS per point; PlanMetric keeps rejected pairs.
- Source: [github.com](https://github.com/RayanA07/LinePilot)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Check calibration of inlier ratio against error on dev.
- What breaks on our images: Few marks.
- Moves: trust. Why this group: Cheap and honest.
- Reports: lit-scale-c

<a id="i300"></a>
### 300. Small classifier on cheap per-plan features predicting 'answer right'

- What: Features: detector count and mean confidence, sharpness, resolution, rotation flag, symbol density, agreement and rule residuals; gradient boosting; its output feeds the Learn-then-Test gate.
- Evidence (adjacent-field): AUROC 0.90-0.99 vs 0.54-0.74 (2609.20110); AUC 0.928 on 267 test samples (2606.24420); R2 0.7765 vs 0.6740 (2506.22438); XGBoost per-image recall predictor beat a confidence baseline (2110.02459).
- Source: [arXiv 2609.20110](https://arxiv.org/abs/2609.20110), [arXiv 2606.24420](https://arxiv.org/abs/2606.24420), [arXiv 2506.22438](https://arxiv.org/abs/2506.22438), [arXiv 2110.02459](https://arxiv.org/abs/2110.02459)
- Licence: code Apache-2.0 (VerifyDoc) / no weights. CubiCasa5K leakage: n/a.
- Cost: 5 h work, no GPU (estimate)
- Experiment: Train on dev plan outcomes with plan-level folds; compare failure AUROC with the plain baseline.
- What breaks on our images: Needs a few thousand outcomes; learned scores failed to transfer to new schemas.
- Moves: trust. Why this group: Strongest pattern in adjacent fields.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i301"></a>
### 301. Gate by OCR mean confidence and label-hit count

- What: Use the mean OCR confidence on label crops and the label-hit count as free gate inputs; abstain or flag below a dev-tuned threshold.
- Evidence (adjacent-field): 50 bridge plans: Tesseract mean-confidence threshold 80 gave precision 97.14% and recall 87.18% for the low-quality class; dropping them raised extraction precision by 17.84 points; threshold tuned on the same data.
- Source: none
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 1 h work after OCR runs
- Experiment: Plot exact-count error among answered sheets against fraction abstained, up to 0.3.
- What breaks on our images: 50 text-heavy PDFs; plans have few labels.
- Moves: trust. Why this group: Free signal once OCR runs.
- Also (ocr, search-only): Use OCR box confidence to gate drawing quality. Use per-box scores and the share of boxes read as an input to a quality gate that sends low-scoring plans to review. Evidence: AHFE 2025 abstract: OCR token confidence as a drawing-quality gate; no numbers. Generic quality scores predicted OCR error for 2 of 8 systems (triage). Source: [doi.org](https://doi.org/10.54941/ahfe1007033). Experiment: Train the gate on dev OCR error and report correlation.
- Reports: lit-ocr-a, lit-sheet-a

<a id="i302"></a>
### 302. Per class and box-size monotone calibration of detection scores

- What: Fit isotonic or Platt per class and size bin on dev detections after NMS, using a centre-in-box match for correctness labels; keep it monotone so the ranking is unchanged.
- Evidence (adjacent-field): Isotonic beat the best train-time method by over 7 D-ECE on COCO (2405.20459); IoU labels hurt tiny objects (2611.11735); histogram binning lowers AUPRC, scaling does not (2302.02622).
- Source: [arXiv 2405.20459](https://arxiv.org/abs/2405.20459), [arXiv 2611.11735](https://arxiv.org/abs/2611.11735), [arXiv 2112.01901](https://arxiv.org/abs/2112.01901)
- Licence: reference code CC BY-NC-SA (idea only); re-implement. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Compare count-confidence AUROC with raw vs calibrated scores.
- What breaks on our images: NMS worsens calibration; detection calibration ignores misses.
- Moves: trust. Why this group: Prerequisite for any count distribution built from scores.
- Also (count, adjacent-field): Calibrate detector scores per class with Platt or isotonic. Fit Platt scaling or isotonic regression per class on a held-out dev slice, above a threshold, before the count distribution. Evidence: D-ECE 12.8 to 0.9 (Platt) and 1.3 (isotonic) with AP unchanged on COCO; fitting on a shifted set gave 14.2 (arXiv 2405.20459, Tables 2 and 5). Source: [arXiv 2405.20459](https://arxiv.org/abs/2405.20459). Experiment: Calibrate on dev, never the sealed split; plot reliability per class.
- Reports: lit-count-b, lit-count-c, lit-trust-a

<a id="i303"></a>
### 303. Calibrate and report per sheet source (CubiCasa-like, scans, phone photos, rotated)

- What: Compute precision of accepted plans per source, set thresholds per source or on a deliberately harder mix, and name the source in the claim.
- Evidence (adjacent-field): Pooled gate violated the target at 40% of sites (2606.20115); certified rules overran 9-30% under grouped shift (2606.15153); per-region control cut missed errors 31.8% to 19.3% and 100 local images recalibrated a new site (2611.08962).
- Source: [arXiv 2606.15153](https://arxiv.org/abs/2606.15153), [arXiv 2611.08962](https://arxiv.org/abs/2611.08962)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 3 h work
- Experiment: Label dev plans by source and compare pooled vs per-source precision of the accepted set.
- What breaks on our images: Small groups cannot certify; groups assigned by a classifier tuned on calibration data need extra care.
- Moves: trust. Why this group: Our eval mix differs from dev and shift breaks pooled gates.
- Reports: lit-trust-b, lit-trust-c

<a id="i304"></a>
### 304. Snap a read ratio to 1:50, 1:100, 1:200 as a check

- What: Read '1:100' and snap to the Finnish series; use only to flag dimension-derived scales that imply odd ratios.
- Evidence (adjacent-field): Finnish permit guides give floor plans at 1:100 or 1:50; title-block read of '1:10' returned '110' on the whole sheet.
- Source: [arXiv 2504.08645](https://arxiv.org/pdf/2504.08645)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Count mismatches between snapped ratio and dimension scale on dev.
- What breaks on our images: Ratio is not a pixel scale for a PNG; marketing plans say 'suuntaa-antava'.
- Moves: trust. Why this group: Plausibility only.
- Reports: lit-scale-a, lit-scale-b

<a id="i305"></a>
### 305. Gate on median symbol height in pixels

- What: Use the pixel height of a reference part (door leaf or wall thickness from detector boxes) as the first gate; abstain below a measured threshold.
- Evidence (adjacent-field): Face detection accuracy depends most on object height; no published pixel threshold exists for plan symbols; a vendor guide says text stabilises near 10 px.
- Source: [arXiv 1612.04402](https://arxiv.org/abs/1612.04402)
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 1 h work
- Experiment: Run the downsampling sweep (100%, 75%, 50%, 35%) on dev and find the height where exact counts break.
- What breaks on our images: No published threshold; vendor figure is commercial.
- Moves: trust. Why this group: Free by-product of detection.
- Reports: lit-sheet-a, lit-sheet-b

<a id="i306"></a>
### 306. Flag regions with two OCR labels or implausible area

- What: Send merged-looking regions to review instead of scoring.
- Evidence (authors-claim): Offset-Guided Attention paper and Ahmed 2011 name merges as the main flood-fill failure.
- Source: [arXiv 2210.17411](https://arxiv.org/abs/2210.17411)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Precision of the flag.
- What breaks on our images: none
- Moves: trust. Why this group: a detectable failure
- Reports: lit-rooms-b, lit-rooms-c

<a id="i307"></a>
### 307. Entropy map flags rooms whose area to refuse

- What: Use per-pixel prediction entropy to mark unreliable rooms.
- Evidence (authors-claim): Lund thesis uses entropy as a reliability signal, no area test.
- Source: [lup.lub.lu.se](https://lup.lub.lu.se/student-papers/record/9220641)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Error against entropy on dev.
- What breaks on our images: none
- Moves: trust. Why this group: feeds confidence
- Reports: lit-rooms-b

<a id="i308"></a>
### 308. Flag plans whose labels are under about 6 px instead of guessing

- What: Estimate label height from detected boxes or scale, and mark rooms and plans below the readable cliff as not read.
- Evidence (our-idea): Glyphs under about 6 px are lost even after upscaling (Swiss plates: 93% exact at full resolution, 16/30 at half); clean-render cliff between 6 and 8 px.
- Source: [arXiv 2604.23814](https://arxiv.org/abs/2604.23814)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 to 2 h work (estimate)
- Experiment: Plot exact match against detected box height on dev images; set the flag threshold where it falls under the chosen precision.
- What breaks on our images: Box height is noisy for the smallest labels; needs the recoverability sweep first.
- Moves: trust. Why this group: fits the refuse-what-was-not-read rule
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i309"></a>
### 309. Accept a count only when it is stable across thresholds

- What: Count at several thresholds (for example 0.3-0.7) and mark the plan uncertain when the count changes.
- Evidence (our-idea): No published support; own idea (a snippet claimed SAM 3 multi-threshold counting, not confirmed on the abstract).
- Source: none
- Licence: own code. CubiCasa5K leakage: n/a.
- Cost: 30 min (estimate)
- Experiment: Dev plans: count at thresholds 0.3 to 0.7 in steps of 0.1, mark plans whose count changes; compare error rate of stable vs unstable plans.
- What breaks on our images: May just replicate score margin.
- Moves: trust. Why this group: Cheap trust signal.
- Reports: lit-count-a

<a id="i310"></a>
### 310. Reject scales that give implausible flat sizes

- What: Refuse a scale that makes the flat or plan outside a size band (e.g. 20-100 m2 for a flat) before answering.
- Evidence (search-only): A VLM-guessed scale was 2.6x off in one project log; band added; stock mean dwelling areas by type (Statistics Finland).
- Source: [xuranus.github.io](https://xuranus.github.io/planova/development/changelog), [stat.fi](https://www.stat.fi/til/asas/2020/asas_2020_2021-05-20_tau_003_fi.html)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Band edges from dev; count rejected scales.
- What breaks on our images: Band is stock average, not measured spread.
- Moves: trust. Why this group: Cheap guard.
- Reports: lit-scale-b

## Later

<a id="i311"></a>
### 311. Ensemble or checkpoint-spread uncertainty to choose marks for review

- What: Use checkpoint spread (free from training) or a small ensemble to rank detected symbols for the review list.
- Evidence (floor-plans): 5-member ensemble mAP 82.7 vs 71.9 softmax; ensemble adds 0.2-0.3 points over plain confidence at a 50% budget (Jakubik Table 3); checkpoint spread works for numeric outputs (2205.13532).
- Source: [arXiv 2205.13532](https://arxiv.org/abs/2205.13532), [cdn.aaai.org](https://cdn.aaai.org/ojs/21522/21522-13-25535-1-2-20220628.pdf)
- Licence: code not checked. CubiCasa5K leakage: no.
- Cost: 5 GPU-h for five trainings (estimate)
- Experiment: Compare with plain confidence at a 50% review budget on dev.
- What breaks on our images: Per-symbol class errors, not counts; misses not corrected.
- Moves: trust. Why this group: Gain over plain confidence is small.
- Reports: lit-trust-a

<a id="i312"></a>
### 312. Line-segment statistics as a plausibility check on detector counts

- What: Regress counts from 15 segment statistics (length histogram, axis share, dark share) and flag detector counts far from the regressor.
- Evidence (floor-plans): Own probe on 500 dev plans: windows corr 0.54, MAE 3.39 vs 4.16 constant, exact 10.2% vs 16.4%; doors corr 0.49, MAE 2.89 vs 3.51, exact 12.2%. Added parallel-pair features did not help.
- Source: [github.com](https://github.com/opencv/opencv)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h, CPU
- Experiment: On dev, flag plans where /detector count - regressor/ exceeds a threshold and check whether flagged plans have lower exact-match than unflagged.
- What breaks on our images: Folds not grouped by drawing family flatters the regressor; whole-image totals only.
- Moves: trust. Why this group: Weak signal but cheap trust input
- Reports: lit-vector-c

<a id="i313"></a>
### 313. Set the abstain threshold per batch from a target error

- What: Sort sheets by risk, estimate cumulative error and set the cut at the highest risk where the estimate stays under the target; a fixed threshold over- or under-rejects.
- Evidence (adjacent-field): OCR post-processing: the batch-adaptive rule held the target error on easy and hard batches while a fixed threshold failed in all cases.
- Source: none
- Licence: idea only. CubiCasa5K leakage: n/a.
- Cost: 2 h work
- Experiment: Compare fixed and batch-adaptive thresholds on dev batches mixed by style.
- What breaks on our images: Strings, not images; 2015.
- Moves: trust. Why this group: Needs a gate first.
- Reports: lit-sheet-b

<a id="i314"></a>
### 314. Confidence from perception, layout and validation channels, not the model's own

- What: Score each count from region image quality, whether the symbol sits where windows sit in walls, and checks (area sums, label legend, count against room labels), then fuse; do not use verbalised confidence.
- Evidence (adjacent-field): arXiv 2609.20110: verbalised VLM confidence clears a 10% error target on 0.1% to 7.0% of fields, fused channels on 39% to 72%; ExtractConf AUC 0.928 against 0.705.
- Source: [arXiv 2609.20110](https://arxiv.org/abs/2609.20110), [arXiv 2606.24420](https://arxiv.org/abs/2606.24420)
- Licence: papers CC BY; no code found. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Fit a small gradient-boosted model on per-plan features on dev and compare its accuracy-at-coverage with detector score alone.
- What breaks on our images: Validation signals for symbol counts are thinner than invoice checksums.
- Moves: trust. Why this group: needs per-count features first
- Reports: lit-market-c

<a id="i315"></a>
### 315. Hold one mark back as a check

- What: Fit scale from some marks and report the held-out mark's error rather than the fit residual.
- Evidence (adjacent-field): Photogrammetry control versus check bars (community manual, unverified).
- Source: [photogrammetrycommunity.github.io](https://photogrammetrycommunity.github.io/metashape-expert-manual/topics/repeatability-qa/scalebar-error-statistics/)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Compare held-out error to fit residual on dev.
- What breaks on our images: Needs at least four marks.
- Moves: trust. Why this group: Honest error number.
- Reports: lit-scale-c

<a id="i316"></a>
### 316. Image-level 'detector missed something' classifier

- What: Train a gate on detector features plus a foundation-model embedding to predict plans where a symbol was missed.
- Evidence (adjacent-field): Person recall among accepted images 64.3% to 84.5% at 5% FPR; Safety AUROC 92.9 vs 54 (2603.25499).
- Source: [arXiv 2603.25499](https://arxiv.org/abs/2603.25499)
- Licence: code not checked, built on YOLOv8 (AGPL). CubiCasa5K leakage: n/a.
- Cost: 8 GPU-h (estimate)
- Experiment: Label dev plans 'miss' vs not from gold boxes; compare with the learned classifier.
- What breaks on our images: One large-object class; needs our own boxes.
- Moves: trust. Why this group: Heavier than the cheap classifier.
- Reports: lit-trust-a, lit-trust-b, lit-trust-c

<a id="i317"></a>
### 317. Self-consistency of one model as confidence

- What: Do not count repeated samples of one counter as independent checks.
- Evidence (adjacent-field): rho 0.20-0.59, 48% of high-agreement answers wrong (2607.08065); reasoning concentrates errors (2609.32035).
- Source: [arXiv 2607.08065](https://arxiv.org/abs/2607.08065)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: LLM text tasks.
- Moves: none. Why this group: Weak.
- Also (market, authors-claim): Flag counts where repeated runs disagree. Run the pipeline three times with rotation or scale augmentation, compare counts, and send disagreeing plans to review. Evidence: Flowtivity blog (R): right 78% of the time when three runs agree, 30% when they disagree; flags about two thirds of errors while checking just over a third of the counts. Source: [flowtivity.ai](https://flowtivity.ai/blog/pdf2takeoff-free-open-source-construction-takeoff/), [github.com](https://github.com/ajflow/pdf2takeoff). Experiment: On dev, three augmented runs per plan; report exact rate among agreeing and disagreeing plans and the share of errors caught.
- Reports: lit-market-a, lit-market-c, lit-trust-a, lit-trust-c

<a id="i318"></a>
### 318. Route only uncertain sheets to a person

- What: Use a sheet-level risk score to decide whether a plan is answered alone or goes to review, as MASAI uses a risk score to pick single or double reading.
- Evidence (adjacent-field): MASAI (Lancet Digital Health 2025 abstract): 105,934 women, reading workload down 44.2%, detection 6.4 against 5.0 per 1,000.
- Source: [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/39904652/)
- Licence: closed vendor. CubiCasa5K leakage: n/a.
- Cost: 1 day (estimate)
- Experiment: Compute review workload saved at equal exact rate on dev.
- What breaks on our images: Needs a per-sheet risk score.
- Moves: demo. Why this group: builds on the coverage curve
- Reports: lit-market-c

<a id="i319"></a>
### 319. Printed scale as prior, independent estimate as check

- What: Commit only if printed-ratio-derived and dimension-derived scales agree; disagreement flags rather than averages.
- Evidence (adjacent-field): Plan2Map: printed scale prior, scale-consistency score, inlier count; critic adds +0.003 IoU.
- Source: [arXiv 2606.02747](https://arxiv.org/html/2606.02747)
- Licence: unverified. CubiCasa5K leakage: n/a.
- Cost: few hours
- Experiment: Dev: agreement rate and wrong-commit rate.
- What breaks on our images: Printed ratio gives no pixel scale.
- Moves: trust. Why this group: Design pattern.
- Reports: lit-scale-c

<a id="i320"></a>
### 320. Venn-Abers or beta calibration of the final score

- What: Calibrate the plan score with Venn-Abers or beta rather than isotonic when calibration data are small.
- Evidence (adjacent-field): Venn-Abers best average log-loss on tabular tasks (2601.19944).
- Source: [arXiv 2601.19944](https://arxiv.org/abs/2601.19944)
- Licence: code MIT (VennABERS). CubiCasa5K leakage: n/a.
- Cost: 1 h work
- Experiment: Compare ECE on held-out plans.
- What breaks on our images: Tabular.
- Moves: trust. Why this group: Only if probabilities are shown.
- Reports: lit-trust-b

<a id="i321"></a>
### 321. Grade a sheet by its worst region

- What: Score each sheet by a low percentile of its region scores, not the mean, and grade it POOR/FAIR/GOOD/EXCELLENT to route it.
- Evidence (adjacent-field): docling confidence grades: per-page grade and 5th-percentile low_grade; MIT; no evidence it tracks count error.
- Source: [github.com](https://github.com/docling-project/docling)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: 2 h (estimate)
- Experiment: On dev, test whether the low-percentile grade predicts exact-count failure.
- What breaks on our images: Scores there are about text and layout.
- Moves: trust. Why this group: cheap to test
- Reports: lit-market-c

<a id="i322"></a>
### 322. Re-detect at higher zoom before sending a plan to review

- What: Run a zoomed second pass on doubtful regions and fold it into the calibrated score; recalibrate afterwards.
- Evidence (adjacent-field): Flip lifted verification AUROC 0.57 to 0.77; certified 34% vs 24% of claims; strict guarantee needs over 80% abstention without it (2606.16667).
- Source: [arXiv 2606.16667](https://arxiv.org/abs/2606.16667)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 3 h work
- Experiment: Measure released share at the same precision with and without the second pass.
- What breaks on our images: Acquisition after calibration voids the guarantee.
- Moves: trust. Why this group: Raises the score's ROC.
- Reports: lit-trust-a, lit-trust-c

<a id="i323"></a>
### 323. Vote across two pixel shifts for any VLM reader

- What: Run any VLM reader on crops with fixed preprocessing at two small shifts and keep only agreeing reads.
- Evidence (authors-claim): PaddleOCR-VL-1.6's report says 1.5 outputs change a lot under small pixel shifts and mild distortions.
- Source: [arXiv 2606.03264](https://arxiv.org/abs/2606.03264)
- Licence: n/a. CubiCasa5K leakage: unknown.
- Cost: 1 h work (estimate)
- Experiment: Measure agreement of reads under 1-2 px shifts on dev crops.
- What breaks on our images: Extra compute per crop.
- Moves: trust. Why this group: only with a VLM reader
- Reports: lit-ocr-a

## Idea or pitch only

<a id="i324"></a>
### 324. Probe a VLM's hidden states to detect counting errors

- What: Train a small classifier on hidden activations of an open-weight VLM to predict when its count is wrong, then re-prompt only then.
- Evidence (adjacent-field): arXiv 2607.09544: detector F1 above 80%, selective re-prompting gains up to +15.6 points (mean +5.3); counts 1 to 9, synthetic images, models up to 8B.
- Source: [arXiv 2607.09544](https://arxiv.org/abs/2607.09544)
- Licence: not checked. CubiCasa5K leakage: n/a.
- Cost: 1 to 2 days (estimate)
- Experiment: Collect labelled errors of an open VLM on dev plans and see whether a probe reaches AUROC above 0.8.
- What breaks on our images: Counts above 9 are normal for doors; never tried on drawings; needs open weights.
- Moves: trust. Why this group: not for the first number
- Reports: lit-market-a

<a id="i325"></a>
### 325. ContrastiveConf per-image reliability from kept and dropped DETR predictions

- What: Compute confidence of kept predictions minus a scaled confidence of discarded ones as a per-image score if a DETR-family detector is used.
- Evidence (adjacent-field): Pearson 0.59-0.66 with per-image AP on COCO, 0.28-0.44 under shift; top-100 mean -0.6 (Table 2 of 2412.01782).
- Source: [arXiv 2412.01782](https://arxiv.org/abs/2412.01782)
- Licence: code MIT / weights COCO detectors, licence not checked. CubiCasa5K leakage: no.
- Cost: 3 GPU-h (estimate)
- Experiment: Compare with plain confidence on dev if the detector is DETR-family.
- What breaks on our images: Needs all queries; small-symbol recall; target is AP not count.
- Moves: trust. Why this group: Detector not decided.
- Reports: lit-trust-a, lit-trust-c

## Do not try (with the reason)

<a id="i326"></a>
### 326. Do not read agreement as proof

- What: Systematic wrong readings are accepted by every consensus estimator.
- Evidence (floor-plans): PlanMetric: 120/120 accepted wrong.
- Source: [github.com](https://github.com/crown-sports/planmetric)
- Licence: MIT. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: Needs an independent route.
- Reports: lit-scale-a

<a id="i327"></a>
### 327. Capture-recapture on overlapping counters

- What: Do not use two readings to estimate misses per plan.
- Evidence (adjacent-field): Underestimates with fewer than four readers (1997 report); simulation: 5-6x low under shared difficulty.
- Source: [ehealthinformation.ca](https://www.ehealthinformation.ca/web/default/files/wp-files/isern-97-22.pdf)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Shared difficulty.
- Moves: none. Why this group: Biased low.
- Reports: lit-trust-b, lit-trust-c

<a id="i328"></a>
### 328. Reject by count-interval width

- What: Do not select plans for review by predicted interval width.
- Evidence (adjacent-field): AUROC 0.72 for point error but 0.38 for interval misses (2611.06158, abstract).
- Source: [arXiv 2611.06158](https://arxiv.org/abs/2611.06158)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: Anti-correlated.
- Reports: lit-trust-b

<a id="i329"></a>
### 329. Do not choose a threshold on the data it is scored on

- What: A threshold fitted and scored on the same fields breaks the stated error target.
- Evidence (adjacent-field): arXiv 2608.14639: coverage 0.416 at risk 0.127 against a 0.10 target, violated in 95% of splits.
- Source: [arXiv 2608.14639](https://arxiv.org/abs/2608.14639)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: trust. Why this group: measured violation
- Reports: lit-market-c

<a id="i330"></a>
### 330. Do not use a model's own stated confidence for auto-approval

- What: Verbalised or log-probability confidence barely separates right from wrong counts.
- Evidence (adjacent-field): arXiv 2609.20110: native VLM confidence clears a 10% error target on 0.1% to 7.0% of fields; ExtractConf: log-probability AUC 0.705.
- Source: [arXiv 2609.20110](https://arxiv.org/abs/2609.20110), [arXiv 2606.24420](https://arxiv.org/abs/2606.24420)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: trust. Why this group: measured weak
- Reports: lit-market-c

<a id="i331"></a>
### 331. Re-render the prediction and compare pixels

- What: Do not verify by redrawing detections.
- Evidence (adjacent-field): AUROC 0.547 on real documents (2608.22183).
- Source: [arXiv 2608.22183](https://arxiv.org/abs/2608.22183)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: At chance.
- Reports: lit-trust-c

<a id="i332"></a>
### 332. VLM token or verbalized confidence as a count gate

- What: Do not rely on token probability or stated confidence of a VLM for counts.
- Evidence (adjacent-field): Token confidence over 90% when off by one (2605.08200); AUROC 0.54-0.74 (2609.20110); stays 0.9 with less evidence (2601.00138).
- Source: [arXiv 2605.08200](https://arxiv.org/abs/2605.08200)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: Weights needed for probes.
- Moves: none. Why this group: Fails.
- Reports: lit-trust-a, lit-trust-c
