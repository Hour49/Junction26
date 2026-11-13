# Triage: scopes L2 detect, L3 count, L5 text, L8 data, L9 sheets, L11 raster to vector

Research orchestrator of Tudor's half (lit-orch), 2026-11-14, about 01:30 Helsinki. Input: 18 worker reports, three
per scope (angle a: field and 2025-2026 work; b: transfers from adjacent fields; c: practical fit), each with a
reading log. The workers were stopped at 01:20 on the owner's order, about 50 minutes after their start, so there
was no send-back round.

How to read the evidence marks in this file:

- **checked** = I opened the source myself on 2026-11-14 and found the number or licence there (curl, headless
  browser, `gh api`). About 30 papers and 40 licences were checked this way; the list is at the end.
- **worker** = a worker read it in full and I did not reopen it.
- **estimate** = nobody measured it; the reasoning is given.

Nothing in this file was measured on our images by the campaign, except one small probe by a worker (classical line
detectors on dev images, section 5). No paper in any of the six scopes reports a per-image exact count of doors,
windows or fixtures from a box detector on raster floor plans. Every expected score below is an estimate.

## 1. Answers to the six scope questions

1. **L2, which Apache/MIT detector.** RF-DETR S/M (Apache-2.0 code and weights for Nano to Large) and D-FINE S/M
   (Apache-2.0) are the two candidates; nothing else is both permissive and strong on small objects. On 100 small
   fine-tuning sets (RF100-VL) their small-object AP is within about two points of each other: RF-DETR S 34.2,
   M 35.8; D-FINE S 36.6, M 36.0 (checked, arXiv 2511.09554, a table written by the RF-DETR authors). No paper measured
   3.8k images on a 12 GB card in under 3 hours; the workers' estimate from published throughput is 6 to 9 minutes
   per epoch at 1024 px for the S sizes, so 15 to 20 epochs fit. Papers on drawings use 768 to 1500 px tiles with
   20 to 50% overlap, or the full page at 1024 to 1536 px; none works at 640 px.
2. **L3, from detector to exact counter.** There is no single published method. What has evidence: box supervision;
   a score threshold chosen for the count, not for AP; a duplicate rule based on intersection over the smaller box
   (worth 9 points of exact match in SAM 3's own ablation: 84.8 to 94.0 on CountBench, checked, arXiv 2511.16719
   Table 37, photos with 2 to 10 objects); and a second, independent look. Per-plan exemplar counting is **not**
   shown to beat a fixed detector. On architectural drawings, trained exemplar counters fail zero-shot (F1 0.10 for
   CountGD and 0.23 for GeCo2 with the drawing's own legend crop as exemplar), while plain template matching with an
   exemplar from the same drawing reaches F1 0.87 and falls to 0.38 with a library exemplar (checked, arXiv
   2610.09313).
3. **L5, short labels.** No source gives accuracy for 2 to 4 character labels at 10 px. Our own 40-image measurement
   (23 to 81% per room type) is still the best number. The nearest evidence: on map labels, a detector plus a crop
   reader gets 61.7 end to end and 74.4 after adapting the reader, against 12.8 for a vision-language model reading
   the whole tile (checked, arXiv 2611.03339); a recogniser trained on upright text scores 8.4 on rotated text
   against 80.7 when trained on all orientations (checked, arXiv 2207.06966). The cheapest fixes, in order: a newer
   recogniser (PP-OCRv6), reading every crop at four rotations and keeping the vocabulary match, then fine-tuning
   the recogniser on synthetic crops of our codes. A sourced abbreviation list is in `reports/lit-ocr-c.md`,
   section 5 (MH, OH, K, KT, KH, KPH, S, WC, ET, VH, ALK, RT, P, H and others, from six public Finnish housing
   brochures; PH and TK appear on plans but no legend defines them).
4. **L8, commercial-safe training set.** No real-image set with our fixture classes is commercial-safe. The safe
   material is generated: an MIT plan generator that writes fixture boxes (licence checked) and a CC BY 4.0 set of
   one million generated plans at 256 px (card checked). Where it was measured with thousands of real plans,
   adding synthetic plans gave no significant gain (wall F1 0.769 to 0.781, inside the bootstrap interval, checked,
   arXiv 2608.25608). Synthetic data pays when real data is scarce, so for us it is for rare classes and for a
   checkpoint that could be shipped, not for the score.
5. **L9, orientation and plan count.** There is no proven orientation method for drawings with little text. The
   detector does not need one if it is trained with the eight rotations and mirrors. Text needs a vote: read at four
   rotations and keep the one with vocabulary hits. Nobody has published plan counting on floor-plan sheets; the
   nearest solved problem is splitting compound figures, done with a box detector trained on pasted composites,
   which scores 98.58 mAP on synthetic composites and 36.88 on real ones (checked, arXiv 2506.02738). So a plan
   detector must be trained on our real multi-plan sheets as well.
6. **L11, vectorise then rules.** No evidence that it beats direct detection, and three results point the other
   way. A vectorise-then-classify model drops from window F1 98.3 and door F1 93.2 on clean plans to 7.2 and 2.1 on
   scanned plans (checked, arXiv 2504.03241). A rule-based vectoriser loses to learned models on the same 400 plans
   (room F1 0.445 against 0.631 and 0.763, checked, arXiv 2609.25615). In chemistry, rule-based tools match learned
   ones on clean images and score 0.0 on a degraded set where the learned model scores 86.9 (checked, arXiv
   2205.14311). Structural rules have measured value only as a filter after a learned detector.

## 2. The four groups

Columns follow the five triage questions. "Moves" is in points of the total score still open on dev: windows and
doors about 11, fixtures about 8, room types about 9, plans per sheet about 1.5.

### 2.1 Train or try tonight

| # | Candidate (field it fills) | Evidence | Allowed | Fits | Moves | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | **RF-DETR S or M fine-tuned on the dev boxes at about 1024 px**, with the eight rotations and mirrors as augmentation; classes window, door, door without leaf, toilet, sink, shower, bathtub, sauna stove (`elements`) | Adjacent fields and drawings, no floor-plan count: RF100-VL small-object AP 34.2 / 35.8 (checked); mAP50 0.949 on 551 engineering drawing sheets for layout classes (checked, arXiv 2607.18997 abstract); 0.881 against 0.623 for the best YOLO on 1,389 substation images (checked, arXiv 2512.22454); F1 0.92 on railway drawings with tiles and a merge step (checked, Sensors 2026) | Code and N to L weights Apache-2.0 (checked). Starts from COCO and DINOv2 weights: no CubiCasa5K. Trained on dev images only: allowed by record 0003, weights stay local | Estimate: 2 to 3 h for 15 to 20 epochs on the 16 GB card. No measured throughput at 1024 px exists | Up to 11 + 8 | One GPU run, 2 to 3 agent hours for the COCO export and config |
| T2 | **D-FINE S or M on the same COCO file**, 960 to 1280 px square, through the Hugging Face transformers port or the Apache-2.0 rewrite (`elements`, and the second detector for stage 8) | RF100-VL small-object AP 36.6 / 36.0 (checked). Reads a stride-8 feature map, RF-DETR a single stride-16 map (worker, from the config files) | Apache-2.0 code (checked) and weights (worker, model cards). Use the COCO checkpoints; the Objects365 ones carry a data-licence caveat (worker) | Estimate: 6 to 7 min per epoch for S at 1024 px on the 12 GB card. Risk: the official repo has open reports of failed custom fine-tunes (worker, issues 214, 72, 299), hence the port | Same points as T1; the two runs decide which one counts | One GPU run in parallel with T1, 3 agent hours |
| T3 | **Count-oriented post-processing**: per-class score threshold chosen on a held-out dev slice to maximise the exact-count rate; duplicates removed by intersection over the smaller box (`elements` counts) | Photos only: the duplicate rule is worth 9 points of exact match in SAM 3's ablation (checked). No detector paper tunes the threshold for count (three workers looked) | Own code | CPU, minutes | Estimate: decides several of the 19 points, because a miss rate of 5% per object already costs a third of the images (section 4) | 1 to 2 agent hours once T1 has predictions |
| T4 | **Same geometry in training and inference**: upscale small plans with Lanczos so the short side reaches the training size, full sheet in and out; tiles only for the few large sheets, and then also in training, with a containment merge | Tile merge on drawings: precision 0.50 with box NMS alone, 0.85 with containment, 0.90 with mask containment (worker; final F1 0.9226 checked). A detector trained on crops and run on pages falls from 0.914 to 0.642 AP50 in music scores (worker, DAS 2024) | Own code; SAHI is MIT (checked) if tiling is needed | No extra GPU | Protects T1 and T2 | Part of T1 |
| T5 | **Text route, first step**: replace the measured PP-OCR mobile models with PP-OCRv6, read every text crop at 0, 90, 180 and 270 degrees and keep the reading that matches the closed vocabulary, Lanczos 2x before reading (`rooms` type and raw label) | PP-OCRv6 recognition 83.2 (checked, arXiv 2606.13108) against 73.7 for the model we measured (worker, same table), on the authors' own benchmark. The engine we use rotates a crop upright only when height / width >= 1.5, so a two-letter label on a rotated sheet stays sideways (checked in the source). Upright-trained recognisers collapse on rotated text (checked) | Apache-2.0 code and weights (checked, model cards). Training data unpublished: no known CubiCasa5K, not verifiable | CPU, no training | Up to 9 | 2 to 3 agent hours |
| T6 | **Export a per-plan box** (union of a plan's element boxes) from the dev labels, and score the free baseline "group detected elements into plans by distance" (`plans`) | None published for floor plans | Own code on dev labels | CPU | Up to 1.5 | 1 agent hour; needed for S1 |

### 2.2 Try on Saturday

| # | Candidate (field it fills) | Evidence | Allowed | Fits | Moves | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | **Plan detector**: one class "plan", RF-DETR, trained on the 784 real multi-plan dev sheets plus composites pasted from the 3,044 single-plan sheets; count = number of boxes (`plans`) | Compound figures: 98.58 mAP on synthetic composites, 36.88 on real ones (checked), so real sheets must be in training. Engineering sheets: mAP50 0.949 over nine layout classes; the "plan" class there has 21 images, so its 0.969 means little (worker) | As T1 | 1 short GPU run | Up to 1.5 | 3 agent hours after T6 |
| S2 | **Fine-tune a PP-OCRv6 small recogniser** on rendered crops of our codes plus real crops pseudo-labelled by the vocabulary, output alphabet cut to the letters we need (`rooms`) | Scene text: synthetic plus 1% real equals all-real (87.26 against 87.22, checked, arXiv 2602.06450). Maps: adapting the reader moves exact match 69.9 to 84.3 (checked). A lexicon adds 9 to 11 points end to end on maps and scene text (checked for scene text, arXiv 2602.04030) | Apache-2.0 | One 12 GB card, about an hour (estimate) | Part of the 9 | 4 agent hours |
| S3 | **Room type as detector classes**: add bedroom, kitchen, bath, WC, balcony, sauna room boxes to a detector run and compare with the text route on dev (`rooms`) | Our design; no paper. The dev export already has the room boxes and labels | As T1 | One more GPU run | Decides how the 9 points are won | 2 agent hours |
| S4 | **Template matching as the independent second count** (stage 8): exemplars are the detector's most confident boxes on the same plan, four rotations, a few scales | F1 0.87 with an exemplar from the same drawing, 0.38 with a library exemplar; trained exemplar counters 0.10 to 0.23 (checked). Those drawings are larger than ours and scoring is by centre point. On the same paper's floor-plan blocks (Table 20, 339 items, 21 classes) template matching gets only 0.58, counters 0.19 / 0.34 (checked by the main orchestrator) | OpenCV, Apache-2.0 | CPU | Feeds `conflicts` and abstention, not the count | 3 to 4 agent hours |
| S5 | **Agreement of T1 and T2 as the conflict signal** | Chemistry: agreement of three or four independent recognisers separates right from wrong (AUROC 0.916) where a pixel round-trip does not (0.547) (worker, arXiv 2608.22183) | Own code | Free once both exist | Confidence only | 1 agent hour |
| S6 | **Count distribution from box scores** (Poisson-binomial), count = mode, abstain when the mode is weak | Medical lesion counts only: count accuracy 87.6 to 88.7 (checked, arXiv 2204.05276) | Own code, about 30 lines | CPU | Confidence only | 1 agent hour |
| S7 | **Copy-paste of real symbol crops for the thin classes** (bathtub 312 boxes, shower, sauna stove), ablated on dev | Mixed: +0.9 to +1.9 AP on tail classes, -1.6 to +4.0 on tiny objects with a small model (worker). Rare-class paste on drawings: mask AP 0.25 to 0.62 for the rarest class, single run (worker) | Own dev data | One more GPU run | Part of the 8 | 2 agent hours |
| S8 | **CountGD++ zero-shot probe on 40 dev plans**, exemplars from the plan | Photos only (MAE 16.55 to 10.29 with its own top boxes as exemplars, checked). Its predecessor scores F1 0.10 on drawings (checked), so expect little | Code and weights MIT (checked) | 12 GB is enough (worker) | Unknown | 1 to 2 hours; drop if below S4 |
| S9 | **Quality gate trained on our own errors** (short side, sharpness, score statistics as inputs, the detector's dev error as target) | Generic image-quality scores predicted OCR error for 2 of 8 systems (worker). The transfer is the fingerprint-quality idea: train the score on the downstream error (worker) | Own code | CPU | Confidence only | 2 agent hours |

### 2.3 Idea or pitch material only

| Candidate | Why it stays an idea |
| --- | --- |
| SAM 3 as counter or second counter | Best published exact-count numbers on small counts (93.8 and 86.2, photos; checked), but a custom licence that is not on the record 0006 list (checked), and no drawing result |
| Generated plans as training data: the MIT generator and the CC BY 4.0 one-million set | Licences checked. No significant gain next to thousands of real plans (checked). The one-million set is 256 px with doors drawn as gaps without a swing arc. Worth it only when a checkpoint must be commercial-safe |
| Real blank scans laid under rendered pages, then a short full-page fine-tune | Real-scan AP 36.0 to 56.5 to 73.7 in music scores (three workers read it independently; the abstract says 73.3). Only applies if we train on rendered plans |
| Structural rules as a precision filter after the detector (a door sits in a wall gap) | Opening precision 67.9 to 91.9 and icon precision 22.3 to 84.0 with a constraint layer on 100 plans at 256 px (worker, ICCV 2017). Candidate for `conflicts` |
| Read counted objects from a detection map, never from a sequence decoder | Opening F1 0.25 to 0.64 on the same network (checked, arXiv 2608.25608). A design rule that supports the detector route |
| Vector parsers on exact primitives | PQ 94.58 on CubiCasa5K converted to CAD primitives against 60.80 for an image model (checked, arXiv 2607.12678). An upper bound for vector PDFs, not for raster |
| Person corrects the marks | 30 to 40% lower count error after five two-click rounds on photos (worker). Product story |
| FloorPlanCAD as a non-commercial pretraining stage for fixtures | Allowed locally by record 0003; Chinese CAD style; only after a first number exists |
| ResPlan layouts for our own renderer | The LICENSE file grants CC BY 4.0 on the data (checked), a metadata file in the same repo says NC-SA and two issues asking about it are open (worker). Local use only until settled |

### 2.4 Drop

| Candidate | Reason |
| --- | --- |
| DEIMv2, EdgeCrafter | Custom non-commercial licence covering code and weights (checked, LICENSE file) |
| Ultralytics YOLO, YOLOv9, YOLOv10, mmyolo, YOLO-NAS weights, RF-DETR XL and 2XL, RT-DETRv4 recipe, DINOv3 weights | AGPL or GPL, non-commercial weights, the Roboflow platform licence, or a custom Meta licence (worker; record 0006) |
| Every checkpoint trained on CubiCasa5K: DoorDet models, the RT-DETR-L floor-plan repo, the 2022 and 2026 floor-plan text detectors, Raster2Seq weights | Leakage: 829 of our 959 sealed drawings are in its train split |
| Trained exemplar counters as the main counter (CountGD, GeCo2, OWLv2) | F1 0.07 to 0.23 on architectural drawings (checked) |
| P2PNet, T-Rex, HerdNet weights | Academic use only (checked for P2PNet), commercial licence needed, CC BY-NC-SA |
| Vectorise then rules as the counter | Section 1, answer 6 |
| DeepLSD, ScaleLSD | DeepLSD pulls a library whose line-detector source carries the AGPL header although the repo says MIT (checked). ScaleLSD lists the same library and has no result on drawings |
| Document-layout checkpoints (DocLayNet-pretrained) for sheets | Pretraining on documents lowered mAP50:95 from 0.772 to 0.589 on drawing sheets (worker, same paper as T1) |
| Learned super-resolution before counting | Icon F1 0.886 to about 0.875 after 2x super-resolution on CubiCasa5K (worker); invented strokes are wrong counts |
| DeepSolo and spotters built on it, PaLeTTe weights, HunyuanOCR, MinerU2.5 weights, TESTR for the deadline | Non-commercial, EU excluded, AGPL weights; TESTR is Apache-2.0 (checked) but sits on a non-commercial framework and was last pushed in 2023 |
| Co-DETR, oriented detectors | Does not fit 12 GB in the time; sheets rotated by exact multiples of 90 degrees keep axis-aligned boxes |
| Training on synthetic plans only | Synthetic-only detectors fall from 90.5 mAP to 4.0 to 33.8 on real engineering sheets (worker) |

## 3. Where the reports disagreed, and what holds

- **First detector.** `lit-detect-a` ranks RF-DETR first, `lit-detect-c` ranks D-FINE first because it reads a
  stride-8 map. The one table with both (checked) shows a gap of 0.2 to 2.4 points of small-object AP, written by the
  RF-DETR authors and still in D-FINE's favour at S and M. Decision: train both tonight (T1, T2). RF-DETR is the
  safer first number, because its rotation augmentation is a config line and the D-FINE repo has open fine-tuning
  failures; D-FINE is the likelier winner on 5 to 10 px symbols.
- **Exemplar counters.** `lit-count-c` puts CountGD++ first and `lit-count-b` puts SAM 3 first, both from results
  on photos. `lit-count-a` found the only test on architectural drawings, where trained exemplar counters fail and
  template matching works (checked). Decision: template matching is the second counter to build (S4); CountGD++
  gets a short probe (S8); SAM 3 is out for licence.
- **SAM 3's counting accuracy**, 94.0 / 86.3 in one report and 93.8 / 86.2 in another: both are in the paper,
  Table 37 (ablation) and Table 3 (checked). No conflict.
- **The one-million generated plans.** `lit-data-c` says try as pretraining, `lit-data-a` says smoke test only.
  The card (checked) confirms CC BY 4.0, 256 px, doors as gaps. With 104k real boxes and the measured null result
  for synthetic plans next to thousands of real ones, the stricter reading holds: idea only.
- **ScaleLSD.** One report says try, two say maybe or skip. No result on drawings and an AGPL-tainted dependency
  in its requirements: drop.
- **The 0.949 on engineering sheets.** Quoted by several reports as evidence for RF-DETR on drawings. The paper is
  about layout regions (title block, legend, views) on facade drawing sheets, not about small symbols (checked). It
  supports S1 directly and T1 only loosely.

## 4. What exact-count rate to expect (estimate, from `lit-detect-c`)

With about 9 objects per class and independent misses, a per-object recall of 0.91 gives about 43% of images
exact, 0.95 gives 63%, 0.97 gives 76% and 0.99 gives 91%; false positives are ignored, so these are upper bounds.
The best published box scores for doors and windows on this dataset are AP50 near 90 (leaky checkpoints). So a
first detector should land between the 2019 network (32 to 37% on windows and doors) and about 65%, and the step
to 75% and beyond depends on T3, T4 and the second look, not on the detector family. This is arithmetic, not a
measurement; the experiment in section 5 replaces it.

## 5. Experiments that settle the choices

1. T1 against T2 on one held-out dev slice (for example the 639 dev images that are in CubiCasa5K's own val and
   test splits): exact-count rate per class, upright and rotated images separately, at 1024 px and at one higher
   size. Settles the detector, the input size and whether tiling is needed.
2. On the same predictions: threshold tuned for AP against threshold tuned for exact count, and box NMS against
   the smaller-box duplicate rule, with window strips as the watched case. Settles T3.
3. Room types: text route (T5, then S2) against detector classes (S3) on the same slice, per room type. Settles
   how `rooms` is filled; the two can also vote.
4. Plans per sheet: constant 1 (79.5% on dev) against element grouping (T6) against the plan detector (S1), exact
   plan count on real multi-plan sheets held out from training.
5. Second count: on images where T1 and T2 disagree, does template matching (S4) side with the right one more
   often than chance? Settles whether stage 8 gets a third voter.

One worker measurement exists already (`lit-vector-c`, section 4, dev images only): OpenCV line detectors take 7 to
17 ms per image and return about 1,000 segments, 57 to 64% of them under 20 px, and simple line statistics
correlate about 0.5 with the true window and door counts. Cheap, and not a counter.

## 6. What was not checked

- There was no send-back round. All 18 reports met the targets by count (41 to 95 distinct sources in each log, 18
  to 49 arXiv papers from 2025-2026 each, all five report sections present), but I did not read every table row.
- Not reopened by me: the music-score augmentation paper (three workers read it), the 2017 raster-to-vector paper,
  the floor-plan text detection papers (IOP 2022, EC3 2026), the copy-paste papers, the chemistry agreement paper,
  the quality-gating sources, the full text of arXiv 2607.18997 (abstract only), the D-FINE and RF-DETR issue
  threads, the Finnish brochures behind the abbreviation list.
- One number I looked for and did not find on the page: "+14.9 mAP50 at 8 real images per class" in arXiv
  2604.18076 (`lit-data-c`); it may be a difference the worker computed.
- Paywalled papers stayed abstract-only in the workers' reports (Elsevier, IEEE, ACM, Springer, MDPI in part),
  among them the one controlled study of scan shift on CubiCasa5K (Automation in Construction, 2026).
- `lit-data-a` named two file names from the public CubiCasa5K layout when it described a derived dataset; they
  were removed from the published copy (main orchestrator, 2026-11-14).

## 7. Sources I opened (2026-11-14)

Papers, by arXiv id unless noted: 2511.09554 (RF-DETR), 2505.05741 (Dome-DETR), 2608.25608 (detect or emit;
synthetic plans), 2508.07714 (DoorDet), 2411.13929 (P&ID Relationformer), 2607.18997 (engineering sheet layout,
abstract), 2512.22454 (substation), Sensors 26(20) 6413 through Europe PMC (railway drawings), 2610.09313 (small
objects in drawings), 2511.16719 (SAM 3), 2204.05276 (Poisson-binomial counting), 2607.02139 (AdaCount), 2512.23351
(CountGD++), 2611.03339 (ArabGeoText), 2606.13108 (PP-OCRv6), 2207.06966 (PARSeq), 2602.06450 (UnionST), 2606.15886
(text on line diagrams), 2602.04030 (TiCLS), 2211.16066, 2605.26884, 2604.18076, 2608.24154 (synthetic data and
resolution), 2506.02738 (compound figures), 2504.03241 (region graph on scans), 2609.25615 (SALI-FP), 2607.12678
(TextCAD), 2611.12657 (sliced inference, title and scope only), 2205.14311 (MolScribe).

Licences through `gh api` or the model card: roboflow/rf-detr, Peterande/D-FINE, Intellindust-AI-Lab/DEIM and
DEIMv2 (LICENSE text read), obss/sahi, Sense-X/Co-DETR, RicePasteM/Dome-DETR, waps101/YOLSO, lyuwenyu/RT-DETR,
facebookresearch/sam3, niki-amini-naieni/CountGD and CountGDPlusPlus (and its Hugging Face card),
TencentYoutuResearch/CrowdCounting-P2PNet (LICENSE text read), Yiming-M/CLIP-EBC, IDEA-Research/T-Rex,
mlpc-ucsd/TESTR, ViTAE-Transformer/DeepSolo, baudm/parseq, RapidAI/RapidOCR (and the crop-rotation rule in its
source), aim-uofa/AdelaiDet, Cyprinus12138/fpvec-lab, m-agour/ResPlan (LICENSE text read), sparkfish/augraphy,
kornia/kornia, conradry/copy-paste-aug, vectorInstitute/pmc-data-extraction, cvg/DeepLSD, iago-suarez/pytlsd
(source header read), ant-research/scalelsd, cherubicXN/hawp, opencv/opencv; Hugging Face cards PP-OCRv6_medium_rec,
PaddleOCR-VL-1.5, DeepSeek-OCR, latin_PP-OCRv5_mobile_rec, pmc-18m-dab-detr, PP-LCNet_x1_0_doc_ori, and the
generated-plans dataset card.

## 8. The reports

`lit-detect-a`, `-b`, `-c`; `lit-count-a`, `-b`, `-c`; `lit-ocr-a`, `-b`, `-c`; `lit-data-a`, `-b`, `-c`;
`lit-sheet-a`, `-b`, `-c`; `lit-vector-a`, `-b`, `-c`: one Markdown file each, plus a reading log `<name>-log.md`
with one line per source opened.
