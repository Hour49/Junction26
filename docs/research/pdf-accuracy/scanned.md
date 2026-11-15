# Scanned PDFs and raster pages: OCR, printed truths, scale, segmentation

Worker "scanned", 2026-11-15. Brief: `BRIEF.md` in this folder. Builds on `docs/research/lit-campaign/` (OCR,
scale, rooms reports): numbers taken from there are marked "(lit-campaign)" and were not re-opened unless said.
Code read: `backend/app/core/pipeline/printed.py`, `raster_scale.py`, `second_count.py`,
`backend/app/adapters/printed_scale/`, `raster_ocr/`, `carbon/contract.py` (tree at e3d18b51).

## Summary (5 lines)

1. Biggest wins are policy, not models: the Carbon reader already reads "48 DORMS", the area table and the scale
   bar, but `printed.py` only files them as second values; a printed total that names exactly what was asked
   should become the answer, with the drawn count as the check (ADOPT NOW, S).
2. A ~1.8x area error is the signature of a 4/3 linear scale slip: (4/3)^2 = 1.78, i.e. 3/32" vs 1/8" or 3/16" vs
   1/4" (neighbouring architectural scales), or 1:75 vs 1:100; a half-size print gives 4x, A-series reduction 2x.
   Rank scale candidates by these signatures plus agreement with a printed area total (ADOPT NOW, S).
3. The door prior is fitted on Finnish CubiCasa doors (`DOOR_M = 0.794` m); a US commercial leaf is 36" (0.914 m;
   ADA 404.2.3 requires 32" clear), so on US sheets it biases the scale 15% and areas 33% low. Pick the prior by
   the sheet's unit system (ADOPT NOW, S).
4. OCR: on 49 real engineering drawings (16,414 strings) PP-OCRv5 scores F1 0.81, tiled custom PP-OCR 0.89,
   DB+Tesseract 0.76, EAST+Tesseract 0.58. Keep the PaddleOCR family (Apache code and weights, already in via
   RapidOCR); Tesseract, EasyOCR, docTR add nothing measured; small VLMs read title blocks poorly (Donut F1 0.67).
5. Room/wall segmentation on scans has no licence-clean, leakage-free model with a scanned-plan number above
   ~70 mIoU; nothing to adopt before the freeze. Printed area totals are gross (to the outside wall face), room
   polygons net: compare like with like before calling ~45% a miss.

## Ranked table

| # | Finding | Verdict | Number (dataset) | Licence (code / weights) | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Printed total that names the asked subject becomes the answer; drawn count is the check | ADOPT NOW | QA r4: 40 answered vs 48 printed; no published rate. Printed room areas as a ruler: 3.1% median scale error (CubiCasa5K, floorplan2bim, lit-campaign) | own code | S |
| 2 | Scale arbitration by ratio signatures (4/3, 1.5, 2, sqrt 2) and by agreement with a printed area total | ADOPT NOW | (4/3)^2 = 1.78 matches the ~1.8x miss (arithmetic); dimension-line route 72/83/86% within 2/5/10% (Lv et al. CVPR 2021, Chinese plans, lit-campaign) | own code | S |
| 3 | Door prior by unit system: 0.914 m (36") on imperial sheets, 0.794 m on metric/CubiCasa | ADOPT NOW | door-only prior median 7.1% (CubiCasa5K, floorplan2bim); ours 5.6% on CubiCasa val; US bias +15% linear (ADA 404.2.3 / 36" leaf) | own code | S |
| 4 | Gross vs net: printed area tables are gross; compare with outline-to-outside-face, not summed rooms | ADOPT NOW | no rate; BOMA Z65.3 / ASTM E1836 definitions | own code | S |
| 5 | One scale per view: tie each ratio to its view title; never median bars of different views | NEXT | no rate; "details at different scales" is a named failure in every scale source | own code | M |
| 6 | Tile scanned pages (2x2-4x4, 5% overlap, 200-400 DPI) and remove long ruling lines before PP-OCR | NEXT | F1 0.81 -> 0.89 (49 engineering drawings, Turku thesis 2025) | Apache-2.0 / Apache-2.0 | S-M |
| 7 | PP-OCRv6 swap + four-rotation read (from lit-campaign, applies to scans too) | NEXT | rec 83.2 vs 73.7 for our model (authors' benchmark); 192/192 vs 83/192 with four rotations (clean renders, lit-campaign) | Apache-2.0 / Apache-2.0 | S |
| 8 | Dimension strings (imperial feet-inch parse) + RANSAC/median over pairs | NEXT | 72% within 2% (Lv et al.); ~90% of dimension strings read right at best (lit-campaign) | own code; no open reference implementation | M |
| 9 | Table Transformer for scanned schedules and area tables | NEXT (only if Carbon tables fail) | no number on drawings found | MIT / MIT | M |
| 10 | Tesseract tuned (psm 11/12, OSD, 300 DPI, border) | SKIP | DB+Tesseract F1 0.763 vs DB+SVTR 0.798, same detector (Turku) | Apache-2.0 | - |
| 11 | EasyOCR, docTR | SKIP | no drawing number beating PP-OCR; PARSeq best recogniser on floor plans (AiC 2024) | Apache-2.0 (CRAFT MIT) / Apache-2.0 | - |
| 12 | Florence-2 / Donut / small VLM for title blocks | SKIP | Donut title-block+notes F1 0.672 (1,406 mechanical drawings, arXiv 2510.21862); Florence-2 GD&T F1 61.5% (400 drawings) | Florence-2 MIT; Qwen3-VL Apache; Qwen2.5-VL-3B research licence (research only) | - |
| 13 | Room/wall segmentation models on scans (CubiCasa5K net, R2V, RoomFormer, LGS-FPP) | SKIP before freeze | CubiCasa5K room mIoU 57.5; LGS-FPP scanned 69.58 mIoU fine-tuned, SAM 2 zero-shot 10.49; RoomFormer Structured3D room F1 97.3 (lit-campaign) | CC BY-NC weights / MIT, weights unstated / unreleased | L |

## 1. Printed totals and area tables as the answer (ADOPT NOW, S)

- **What we do now.** `printed.py` turns each Carbon `printed_facts` entry ("SECOND FLOOR = 48 DORMS", "TOTAL 26,562
  SF") into a `printed_total` second value; `docs/PIPELINE.md` says "no rule: show both; a printed 48 DORMS never
  replaces the count". Area, storey and other facts are not compared at all (`fact_measurements` docstring).
- **Proposal.** When the question's subject equals a printed fact's subject (same room type or element class, same
  floor or the whole sheet, same unit after ft2 -> m2), answer with the printed value, source "printed on the
  sheet", and keep the drawn count or measured area as the conflict value. The architect's printed total is a
  statement on the drawing; our count is a reading of it. Keep the current behaviour when the subject only
  partly matches (a type vs all rooms, one floor vs the building).
- **Area tables also calibrate the scale.** A printed floor total and the floor outline's pixel area give
  `m_per_px = sqrt(area_m2 / outline_px)`: a scale candidate that needs no bar or ratio (used in finding 2).
  Floorplan2bim's printed room areas as ruler: 3.1% median scale error with exact rooms, 7.9% with recognised ones
  (CubiCasa5K; lit-scale report, recomputed there from the project's per-plan file).
- **Number on our data:** QA round 4: 40 bedrooms answered vs 48 printed; ~45% of a 26,562 SF table. No published
  rate for "printed total vs drawn count" on drawings was found.
- **Plugs in:** `app/core/pipeline/printed.py` `fact_measurements` / `with_printed`, and the answer policy that picks
  between stage-8 values. Test: a fixture sheet with a printed "48 DORMS" and 40 detected bedrooms answers 48 with
  a conflict note.

## 2. Scale arbitration by ratio signatures (ADOPT NOW, S)

- **What we do now.** Bars win over the ratio (median of all bars); the ratio at paper size replaces the door
  estimate; only a >2x disagreement (`ESTIMATE_RANGE`) leaves the estimate in place or flags areas. A 1.34x linear
  slip (1.8x area) is inside 2x, so a wrong ratio is used with only a 10% conflict note. When a bar exists, the
  ratio read beside it is never compared with it.
- **Signatures.** Divide every pair of candidates (bar, ratio at paper size, door prior, printed area total,
  dimension pairs). A quotient near a known factor names the cause:
  - 4/3 (area 1.78): neighbouring architectural scales 3/32"-1/8", 3/16"-1/4", 3/8"-1/2", or 1:75-1:100. Most
    likely our ~1.8x sheet: the wrong one of two scale notes, or a misread fraction.
  - 2 (area 4): a half-size set (22x34 drawn, printed on 11x17), or an enlarged plan at 1/4" next to a 1/8" plan.
    Half-size sets are standard US practice; the numeric scale is wrong on them while a graphic bar shrinks with
    the paper (vdci.edu paper-size guide; landfx and eng-tips threads; TxDOT asks for an "accurate alternate scale
    when printed at 11 x 17"; GSA P100 requires lettering legible at half size).
  - sqrt 2 (area 2): A1 printed on A2, A2 on A3. 1.5 (area 2.25): 24x36 on 18x24 / 3/16"-1/8".
  - 17/36 = 0.47 or 11/24 = 0.46: ARCH D fitted to 11x17.
- **Rule.** A ratio whose quotient against the bar is one of these factors is a reduced print or a different view:
  the bar wins and the note says which. Between ratio and door prior with no bar, a printed area total within
  10% of the summed outline at one candidate decides (area discriminates 1.78x easily); else keep both and
  refuse areas, as today above 2x.
- **Number:** none published for the signature rule itself; the arithmetic is exact. Scale sources from the
  lit-campaign: dimension lines 72/83/86% within 2/5/10% (Lv et al., CVPR 2021 supplement Table 2); priors only
  median 6.5% (floorplan2bim). A practitioner page claims 0.707 scale-recognition accuracy for a 2026 workflow
  (techbloat.com; unverified, no dataset).
- **Plugs in:** `printed_scale` / `with_printed` in `printed.py`, ~60 lines plus a table-driven test of the
  factors. First, log the three m/px values of the 1.8x sheet and divide: that confirms or kills the 4/3 theory
  in five minutes.

## 3. Door prior by unit system (ADOPT NOW, S)

- `DOOR_M = 0.794` m was fitted on CubiCasa val (Finnish homes, 800 mm leaves). US commercial and dorm doors are
  3'-0" leaves: ADA 2010 404.2.3 requires 32" (815 mm) clear, which a 36" leaf gives. 0.914 / 0.794 = 1.15
  linear, 1.33 in area, so on US CAD scans the prior alone puts areas a third low.
- Rule: a sheet whose printed text is imperial (feet-inch dimensions, `1/8" = 1'-0"`, SF) uses 0.914 m; else
  0.794 m. `imperial_scales` in `printed.py` already detects imperial text. Residential US interior doors are
  2'-6" to 2'-8", so keep the wide band (`SPREAD_FEW`) on such sheets.
- Number: door-only prior median 7.1% (CubiCasa5K, floorplan2bim, lit-campaign); our fitted prior 5.6% on CubiCasa
  val (code docstring). No US-sheet number exists. Effort S: a constant chosen by a predicate, one test.

## 4. Gross vs net area (ADOPT NOW, S)

- Area tables on US sheets give gross area: BOMA Z65.3 exterior gross area and ASTM E1836 measure to the outside
  face of exterior walls, without deductions. Our room polygons are net (inside walls, rooms only), so summed rooms
  will undershoot a printed gross total by walls, shafts and circulation (share not measured; no source found). Part
  of the "~45% of the area" is likely convention plus missed rooms, not scale.
- Rule: compare a printed gross total with the outer outline of the plan, not with the sum of rooms; label which
  one an answer is. Plugs in where finding 1 compares area facts. No published rate.

## 5. One scale per view (NEXT, M)

- US sheets mix a 1/8" floor plan with 1/4" enlarged plans and details; Carbon returns one `printed_scale` and
  `printed_scale` takes the median of all bars. Every scale source the lit-campaign read names "details at
  different scales" as a failure. Tie each scale note to the nearest view title box (`VIEW TITLE ... SCALE: 1/4" =
  1'-0"`) and each room to the view it sits in. Needs a per-view field in the Carbon schema: M, after the freeze.

## 6. Tiled PP-OCR on scanned sheets (NEXT, S-M)

- Partanen, "AI-powered text extraction from engineering drawings", MSc thesis, University of Turku, Sept 2025 (read
  in full text): 49 real drawings (P&ID, assembly, isometric, general plans, title pages), 16,414 strings, pretrained
  models only. Table 5.3 F1: EAST+Tesseract 0.581, EAST+TrOCR 0.640, DB+Tesseract 0.763, DB+TrOCR 0.802,
  DB+SVTR-HGNet 0.798, PP-HGNetV2+SVTR-HGNet 0.812 (= PP-OCRv5); their pipeline (PP-OCRv5 models, page rendered at
  200 DPI in 2x2 tiles for A3, 400 DPI in 4x4 for A0, 5% overlap, edge boxes merged, long ruling lines removed,
  word-level splitting) 0.89.
- Fit: these are drawings like our CAD scans (large sheets, text over linework), unlike CubiCasa. Our RapidOCR
  already runs PP-OCR models; what to copy is the tiling and line removal. Used as a second reader of the digits
  Carbon reads in printed facts and scale notes ("48", "26,562", "3/32"), not as the main reader.
- Licence: PaddleOCR and RapidOCR Apache-2.0 (gh api), PP-OCR weights Apache-2.0 (lit-campaign, model cards).

## 7. PP-OCRv6 and four rotations (NEXT, S)

Already the lit-campaign's first OCR step (triage-Cucuteanu-Tudor-912 T5, lit-ocr-c): PP-OCRv6 recognition 83.2 vs
73.7 for the model we use (authors' benchmark, arXiv 2606.13108); RapidOCR only turns a crop upright when
height/width >= 1.5, so short rotated labels stay sideways; a four-rotation vote read 192/192 vs 83/192 on clean
renders. Scanned sheets have rotated room tags and vertical view titles too, so it applies here unchanged.

## 8. Dimension strings plus dimension lines (NEXT, M)

- Best scale route with a published rate on plans: 72% within 2% (Lv et al., Chinese plans, no code). A bridge-drawing
  paper (ASCE Computing in Civil Engineering 2024, "Towards a Robust Deep Learning-Based Scale Inference Approach in
  Construction Drawings": YOLOv7 dimension lines + EasyOCR + vote) does the same; the page returned 403, no number
  read. A 2026 agentic framing-plan paper (arXiv 2608.17237) gets scale within 0.1% by dimension-ratio consensus,
  but on 100 generated plans only.
- Our addition for US scans: the parser must keep feet-inch tokens (`12'-6"`, `3'-0 1/2"`), which OCR often drops
  the primes from; reject any pair whose ratio to the median is off by >5%, call the scale `scaled` only with 2+
  agreeing pairs (lit-scale rule). Needs a dimension-line detector we do not have: M.

## 9. Table Transformer for schedules and area tables (NEXT, conditional)

`microsoft/table-transformer` code MIT, weights MIT (HF card). Scanned schedules have ruled grids, which
`pdf_tables/lattice.py` handles only on vector pages. No measured number on drawing schedules was found; Carbon
already returns `tables`. Only worth it if Carbon's table rows prove wrong on the QA sheets. PaddleOCR-VL (0.9B,
Apache-2.0) also parses tables; its card's table scores are images, no drawing number.

## 10-11. Tesseract, EasyOCR, docTR (SKIP)

- Tesseract (Apache-2.0): useful knobs are `--psm 11/12` (sparse text, with OSD), `--psm 0` for orientation, 300 DPI,
  a 10 px white border, scanner-edge removal; the docs admit tables need custom segmentation (tessdoc
  ImproveQuality). Same detector, Tesseract vs SVTR recogniser: 0.763 vs 0.798 F1 (Turku). No reason to add it.
- EasyOCR (Apache-2.0, CRAFT detector MIT) and docTR (Apache-2.0 code, Apache weights on HF): no drawing number that
  beats PP-OCR. On floor plans an Automation in Construction 2024 study (Tesseract, EasyOCR, PARSeq, MATRN) found
  PARSeq the best recogniser; per-engine numbers not read (abstract only; "85.2% CER" is ambiguous).

## 12. Small VLMs for title blocks (SKIP)

- arXiv 2510.21862 (Khan et al., v2 Jan 2026): YOLOv11 layout, then a Donut "alphabetical" model for title blocks
  and notes: overall F1 0.672 on its mechanical drawings (1,406 for training); code/weights licence not stated.
  Florence-2 fine-tuned on 400 drawings for GD&T: F1 61.5%, hallucination ~10% (arXiv 2411.03707, lit-campaign).
- Licences checked on HF: Florence-2 base/large MIT, Qwen3-VL-4B Apache-2.0, Qwen2.5-VL-7B Apache-2.0,
  **Qwen2.5-VL-3B Qwen Research licence: research only**, PaddleOCR-VL Apache-2.0, GOT-OCR-2.0 Apache-2.0,
  moondream2 Apache-2.0.
- Gemini via Carbon already reads title blocks and printed facts; a small local model would be a cost play, not an
  accuracy one. SKIP for accuracy.

## 13. Room and wall segmentation on scans (SKIP before freeze)

From the lit-campaign rooms report (numbers re-checked there): CubiCasa5K net room mIoU 57.5 (49.3 polygonised),
weights CC BY-NC and trained on data leaking into our eval; R2V 84.5/88.4 room at IoU>0.7 on its own Manhattan
data, rasters not shared; RoomFormer Structured3D room F1 97.3 on density maps, weights terms unstated; LGS-FPP
(SAM 2 fine-tuned) 69.58 mIoU on scanned plans vs 65.07 SegFormer, SAM 2 zero-shot 10.49, unreleased; MitUNet
wall mIoU 87.91 on its own 500 plans. Cross-domain drops are large (door IoU 0.099 for the CubiCasa model on
internet plans). The lit-campaign's own smp/timm wall-and-room net (MIT/Apache, trained on dev only) remains the
NEXT route; for US CAD scans none of these has a number.

## Sources

- Partanen, AI-powered text extraction from engineering drawings, Univ. of Turku 2025:
  https://www.utupub.fi/bitstreams/85f13f4b-276a-41eb-b933-be3134af9788/download
- Khan et al., arXiv 2510.21862: https://arxiv.org/abs/2510.21862 ; Florence-2 GD&T, arXiv 2411.03707:
  https://arxiv.org/abs/2411.03707 ; YOLO+Donut, arXiv 2505.01530: https://arxiv.org/abs/2505.01530
- Talebi-Kalaleh and Mei, arXiv 2608.17237: https://arxiv.org/abs/2608.17237
- Scale inference on construction drawings (ASCE, not read, 403): https://ascelibrary.com/doi/10.1061/9780784485248.087
- Tesseract ImproveQuality: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- ADA 2010 Standards 404.2.3: https://www.access-board.gov/ada/
- BOMA gross areas: https://boma.org/BOMA/BOMA-Standards/BOMA_Floor_Measurement_Standards/Gross_Areas.aspx ;
  ASTM E1836 sample: https://cdn.standards.iteh.ai/samples/71811/e3a291393c884d7aa8f0f85fe3e37942/ASTM-E1836-E1836M-09e1.pdf
- Half-size practice: https://vdci.edu/learn/blueprint-reading/standard-paper-sizes-in-architecture-and-engineering-offices-a-comprehensive-guide ;
  https://landfx.com/community/scaling-details-to-fit-on-11x17.html ; https://www.eng-tips.com/threads/odd-plan-scale.308757 ;
  https://www.txdot.gov/manuals/row/utl/appendix-b--broadband-accommodation-process/section-3--utility-installation-review-permit-desi/paper-size.html ;
  https://gsacriteria.tpub.com/p100/p1000296.htm
- Floor-plan OCR study (Automation in Construction 2024): https://www.aminer.cn/pub/648ce8a9d68f896efa8bd59a
- Practitioner scale claim (unverified): https://www.techbloat.com/can-ai-accurately-read-blueprint-dimensions-and-scale.html
- Licences: gh api repos mindee/doctr, JaidedAI/EasyOCR, tesseract-ocr/tesseract, PaddlePaddle/PaddleOCR,
  RapidAI/RapidOCR, clovaai/CRAFT-pytorch, microsoft/table-transformer; HF API for microsoft/Florence-2-{base,large},
  Qwen/Qwen3-VL-4B-Instruct, Qwen/Qwen2.5-VL-{3B,7B}-Instruct, PaddlePaddle/PaddleOCR-VL, stepfun-ai/GOT-OCR-2.0-hf,
  vikhyatk/moondream2, Felix92/doctr-torch-parseq-multilingual-v1,
  microsoft/table-transformer-structure-recognition-v1.1-all (all read 2026-11-15).
- Lit-campaign reports reused: `docs/research/lit-campaign/reports/lit-scale.md`, `lit-ocr-a.md`, `lit-ocr-b.md`,
  `lit-ocr-c.md`, `lit-rooms.md`, `triage-Cucuteanu-Tudor-912.md`.
