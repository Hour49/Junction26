# Text and room labels

43 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i193"></a>
### 193. Decode the reader output against the closed label table with exact match and abstention

- What: Map each read to the Finnish/Swedish label table by exact match (edit distance only where unambiguous), score against the table, and abstain below a score instead of forcing a code. Compare the decoded answer with the raw output.
- Evidence (adjacent-field): Lexicon on a spotter output: ICDAR15 end-to-end 79.1 (none) vs 90.1 (strong lexicon), map spotter 70.27 vs 79.13 (TiCLS Table 1, PaLeTTe). A 37-name closed list cut name-field error 36.0 to 15.7 (arXiv 2111.06738). Plate entry: abstention under 0.33 gave +0.11 but hard format rules cost -0.11.
- Source: [arXiv 2602.04030](https://arxiv.org/abs/2602.04030), [arXiv 2506.15010](https://arxiv.org/abs/2506.15010), [arXiv 2111.06738](https://arxiv.org/abs/2111.06738), [arXiv 2607.08896](https://arxiv.org/abs/2607.08896)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: under 1 h work, CPU only (estimate)
- Experiment: On the dev crops, report exact match and abstain rate for raw read, exact-table match and table match with abstention; count wrong-but-accepted reads.
- What breaks on our images: Published lexicons hold every test word, ours holds about 25 codes (the gain should be at least as large); a lexicon cannot recover a missed detection.
- Moves: room-types. Why this group: under 1 h, no training, matches the refuse-what-was-not-read rule
- Also (ocr, our-idea): Mask the recogniser output to the label alphabet at decode time. Restrict the CTC output of the PP-OCRv6 recogniser to capital letters, digits and the few diacritics, with no training, as a zero-cost closed alphabet. Evidence: none (the v6 config shows a 48 px input and a dictionary of about 18.7k entries; the gain is untested). Source: [paddleocr.ai](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html). Experiment: Decode the same dev crops with and without the mask; compare exact match per room type.
- Also (ocr, search-only): Post-OCR edit distance to a vocabulary, ties broken by frequency. Compare each string with the vocabulary by edit distance and break ties by entity frequency in the dev set. Evidence: mapKurator post-OCR step does this on 60,000 maps; no accuracy figure given. Source: [arXiv 2306.17059](https://arxiv.org/abs/2306.17059). Experiment: Add edit-distance-1 matching to the decode and report gain and false accepts.
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i194"></a>
### 194. Fine-tune the PP-OCRv6 small recogniser on rendered plus real crops with a cut dictionary

- What: Fine-tune the v6 small recogniser from its pretrained weights on rendered crops of about 25 codes plus real dev crops, with the dictionary swapped for the closed vocabulary and the training config of the repo.
- Evidence (adjacent-field): Adapting the reader on map labels moved exact match 69.9 to 84.3 (arXiv 2611.03339); PP-OCRv6 adapted from 20-240 lines in 300 steps (arXiv 2609.20064); rebar annotations reached 96.3% word accuracy from about 5,000 crops (Frontiers 2026). Not measured on room labels.
- Source: [arXiv 2609.20064](https://arxiv.org/abs/2609.20064), [arXiv 2611.03339](https://arxiv.org/abs/2611.03339), [paddleocr.ai](https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html)
- Licence: code Apache-2.0 / weights Apache-2.0. CubiCasa5K leakage: no.
- Cost: 3 to 4 h work, under 1 GPU-h on 12 GB (estimate)
- Experiment: Train on rendered crops plus dev crops, hold out dev images, and report exact match per room type against the stock v6 and the four-rotation vote; keep a fixed held-out list to catch regressions.
- What breaks on our images: Needs crops with labels (text boxes may not be in the export); a targeted fine-tune in one report broke 10 previously correct lines.
- Moves: room-types. Why this group: only if stock v6 plus vote leaves a gap
- Also (ocr, authors-claim): Swap the OCR models for PP-OCRv6 (detector and recogniser). Replace the PP-OCR mobile models in the text stage with PP-OCRv6 small or medium (detector and recogniser) through RapidOCR 3.9+ or PaddleOCR 3.7. Keep tiling and the closed-vocabulary decode unchanged. Evidence: Authors' own benchmark: recognition 83.2 (medium) / 81.3 (small) / 73.5 (tiny) against 73.7 for the v5 mobile model; Latin-script set 88.0 / 84.0 / 63.8 (arXiv 2606.13108). No drawings, no short-code test. Third-party: +10% words read right vs v5 server on HierText crops (PaddleOCR issue 18434). Source: [arXiv 2606.13108](https://arxiv.org/html/2606.13108), [github.com](https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.7.0). Experiment: Rerun the 40-image room-label test with v6 det plus small and medium rec, same tiling and decode; compare exact match per room type with the 23-81% baseline on the dev split only. Include one crop with a, o with dots as a smoke test.
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i195"></a>
### 195. Upscale crops 2x to 3x with bicubic or Lanczos before the reader

- What: Resize each label crop to at least about 48 px high with Lanczos or bicubic (never a generative upscaler) before the recogniser, and test 3x vs 6x.
- Evidence (adjacent-field): Doubling recogniser input height 48 to 96 px gave -8.3 to -11.5 CER points in PP-OCRv6 adaptation (arXiv 2609.20064); map pipeline crops upscaled to 48 px min height; 3x bicubic used with small VLMs (arXiv 2610.41254). Own earlier test: 2x Lanczos helped some room types and hurt kitchens.
- Source: [arXiv 2609.20064](https://arxiv.org/abs/2609.20064), [arXiv 2611.03339](https://arxiv.org/abs/2611.03339)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work, CPU only (estimate)
- Experiment: Read the dev crops at 1x, 2x, 3x, 6x with each recogniser; report exact match per room type per scale.
- What breaks on our images: The v6 recogniser already stretches every crop to 48 px inside, so outside upscaling may help the detector more than the reader.
- Moves: room-types. Why this group: one line of code, mixed earlier result needs settling
- Also (scale, adjacent-field): Upscale crops before OCR detection and recognition. Upscale the plan or the crop 2x to 3x before detection; recogniser resizes to 48 px height anyway. Evidence: PaddleOCR PP-OCRv6 settings; ImageDataExtractor upscales 3x; Tesseract documents 300 DPI; LinePilot error 0.403 at about 900 px against 0.269 at 300 DPI. Source: [arXiv 2606.13108](https://arxiv.org/pdf/2606.13108), [arXiv 2609.19377](https://arxiv.org/abs/2609.19377). Experiment: Read rate for 5-20 px digits at 1x, 2x, 3x on dev.
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c, lit-scale-a, lit-scale-b, lit-scale-c

<a id="i196"></a>
### 196. Read every text crop at 0, 90, 180, 270 degrees and keep the in-vocabulary answer

- What: Detect text polygons, cut each crop upright by its polygon, run the recogniser on four rotations, keep the reading that matches the label table, highest score first as a tiebreak, abstain below a threshold.
- Evidence (our-idea): Own clean-render tests: single read 83 of 192 vs vote 192 of 192 (12 codes); harder set with blur, JPEG and a line: 120 of 300 vs 291 of 300, 1 of 24 junk crops falsely accepted. Supporting: PARSeq trained on one orientation scores 8.4 on rotated sets vs 80.7 when trained on all (arXiv 2207.06966, Table 18).
- Source: [arXiv 2207.06966](https://arxiv.org/abs/2207.06966), [raw.githubusercontent.com](https://raw.githubusercontent.com/RapidAI/RapidOCR/main/python/rapidocr/utils/process_img.py)
- Licence: n/a (own code, about 20 lines). CubiCasa5K leakage: n/a.
- Cost: 2 to 3 h work, CPU only (estimate)
- Experiment: Add the vote after detection on the 40-image set; report exact match per room type on upright and rotated sheets separately, and the false-accept rate on non-label crops on the dev split only.
- What breaks on our images: Perfect tight boxes assumed in the tests; no wall lines touching glyphs; with 25+ codes some false accepts expected; detector misses not covered.
- Moves: room-types. Why this group: largest measured gain per hour, no training
- Also (ocr, search-only): Per-crop four-way orientation classifier (docTR) before the recogniser. Use docTR's crop orientation classifier (0, -90, 180, 90) so the recogniser runs once per crop instead of four times. Evidence: Classes and input read from source (256x256 crops); accuracy not read. Source: [github.com](https://github.com/mindee/doctr). Experiment: Compare against the four-rotation vote on 5-12 px crops.
- Reports: lit-ocr-b, lit-ocr-c

<a id="i197"></a>
### 197. Remove the RapidOCR rule that rotates a crop upright only when height/width >= 1.5

- What: A 2-letter label set at 90 degrees has an aspect near 1.0-1.3, so the engine leaves it sideways and the 0/180 classifier cannot fix it. Do not rely on the stock crop-rotation step for rotated sheets; use an explicit vote instead.
- Evidence (our-idea): Found in RapidOCR source (get_rotate_crop_image, process_img.py). Own synthetic page test: stock pipeline finds 113 of 120 codes upright but 54 / 69 / 41 when the sheet is rotated 90 / 180 / 270 degrees.
- Source: [raw.githubusercontent.com](https://raw.githubusercontent.com/RapidAI/RapidOCR/main/python/rapidocr/utils/process_img.py)
- Licence: code Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: none (a finding)
- Experiment: Run the stock pipeline on the dev images split by sheet rotation and report exact match per room type for upright vs rotated sheets.
- What breaks on our images: Synthetic grid page, one font; effect on real images not measured.
- Moves: room-types. Why this group: explains part of the 23-81% spread; needs only a measurement
- Reports: lit-ocr-c

## Try next

<a id="i198"></a>
### 198. Fine-tune a text detector on tiles of floor plans

- What: Fine-tune a text detector (docTR or PaddleOCR DB, or Faster R-CNN) on 256-512 px tiles of dev plans with text boxes, tuning tile size per image size.
- Evidence (floor-plans): Faster R-CNN on 399 CubiCasa5K plus 122 CVC-FP plans: AP[.5:.95] 90.12% on 256 px tiles, 74.66% on 1024 px, 69.16% for pretrained EAST (IOP 2022); CRAFT plus TPS-STN-CRNN on 1,000 plans read dimensions 90.2% exact (EC3 2026); YOLOv7 97.5 wmAP and PARSeq best recogniser (2024 paper, abstract only).
- Source: [iopscience.iop.org](https://iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017), [ec-3.org](https://www.ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf)
- Licence: paper CC BY 3.0; no code or weights released. CubiCasa5K leakage: yes.
- Cost: 3 to 4 h work, 1 to 2 GPU-h on 12 GB (estimate)
- Experiment: Train on dev-split text boxes, tile 256 vs 512 vs 1024, report detection recall per room type on held-out dev images.
- What breaks on our images: The label export carries room polygons, not text boxes; published checkpoints saw CubiCasa5K and are unreleased.
- Moves: room-types. Why this group: strongest published floor-plan text result, if boxes can be had
- Reports: lit-ocr-a, lit-ocr-c

<a id="i199"></a>
### 199. Detector, rectified crop, small fine-tuned reader instead of full-image spotting

- What: Find text boxes with a detector, rectify and upscale each box, then read the crop with a small reader. Never ask a VLM to spot on the whole sheet.
- Evidence (adjacent-field): Maps: detector plus VLM crop reader 74.4 vs 12.8 end-to-end for the VLM spotting directly (arXiv 2611.03339); comics: frontier VLMs score 0.0 spotting zero-shot (arXiv 2505.20298); OCRBench v2 spotting below 27B parameters is unreliable.
- Source: [arXiv 2611.03339](https://arxiv.org/abs/2611.03339), [arXiv 2505.20298](https://arxiv.org/abs/2505.20298)
- Licence: n/a (pattern). CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: Compare full-sheet VLM spotting against detector plus crop reader on 40 dev images.
- What breaks on our images: Map text median 18 px, ours 5-12 px; the label export may carry no text boxes.
- Moves: room-types. Why this group: the design the pipeline already has; confirms not to spot on whole tiles
- Also (scale, adjacent-field): Oriented boxes then a small reader for rotated dimension text. Detect text with oriented boxes, rotate to horizontal, then read the crop. Evidence: Donut/Florence-2 Measures F1 0.941, hallucination 0.104; vertical text rotation fixes 600 vs 009 errors. Source: [arXiv 2506.17374](https://arxiv.org/pdf/2506.17374). Experiment: Read rate on dev crops at 90/180 rotations.
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c, lit-scale-a, lit-scale-b, lit-scale-c

<a id="i200"></a>
### 200. docTR detector and recogniser training scripts as the permissive fine-tune path

- What: Use docTR DB detector with its training scripts and a swappable recogniser (CRNN, PARSeq, ViTSTR, SAR, MASTER); VOCABS finnish adds a,o with dots; no hidden 20 px box cut-off.
- Evidence (adjacent-field): No accuracy number on drawings; docTR keeps boxes down to 2 px with box_thresh 0.1; pretrained recognisers use a French vocabulary so Finnish needs a fine-tune.
- Source: [github.com](https://github.com/mindee/doctr)
- Licence: code Apache-2.0 / weights licence unverified. CubiCasa5K leakage: unknown.
- Cost: 2 to 3 h work (estimate)
- Experiment: Train the DB detector on dev tiles and compare with PaddleOCR det on label recall.
- What breaks on our images: Detector input is resized, so tile large drawings first.
- Moves: room-types. Why this group: clean licence, both training scripts exist
- Reports: lit-ocr-a, lit-ocr-c

<a id="i201"></a>
### 201. Small VLM reads crops for labels and scale text

- What: Detect the label or scale crop, read to JSON with Florence-2 or Donut.
- Evidence (adjacent-field): Florence-2 +52.4% F1 vs best zero-shot on 400 drawings; Donut F1 94% with 10.8% hallucination on 1,367 drawings.
- Source: [arXiv 2411.03707](https://arxiv.org/abs/2411.03707), [arXiv 2506.17374](https://arxiv.org/abs/2506.17374)
- Licence: models MIT. CubiCasa5K leakage: n/a.
- Cost: 4-8 h (estimate)
- Experiment: Label and area exact match on dev; constrain to Finnish abbreviations.
- What breaks on our images: 10% hallucination too high for numbers without checks.
- Moves: room-types. Why this group: fits labels and scale
- Reports: lit-floorplan-c

<a id="i202"></a>
### 202. Build a confusion table from our dev errors and correct only unambiguous cases

- What: List the dev confusion pairs (0/O, I/1, 8/B, 5/S, M/N) and correct a read only when exactly one in-table code results; leave the rest abstained.
- Evidence (adjacent-field): P&ID tags: end-to-end 91.1%; recognition 95.7% with rules written from a dev confusion list; one project 40% without rules; rules not applied to mixed letter-digit parts (Comput. Chem. Eng. 204:109436). Tyre-code reader: errors are look-alike pairs.
- Source: none
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 2 h work (estimate)
- Experiment: Build the table from dev errors, apply on a separate dev half, and report corrections made, wrong corrections and abstentions.
- What breaks on our images: Rules tuned per project; ours are 1-4 letters from a list.
- Moves: room-types. Why this group: after the first dev error list exists
- Reports: lit-ocr-b

<a id="i203"></a>
### 203. Fine-tune PARSeq-S as the recogniser (attention decoder)

- What: Fine-tune PARSeq-S or tiny with a charset file that includes a, o with dots and a with ring, train on rotated crops for orientation robustness.
- Evidence (adjacent-field): Rotated word accuracy 80.7 mean when trained on all orientations vs 8.4 horizontal-only (arXiv 2207.06966, Table 18); rebar annotations 92.4% word accuracy from 5,054 crops; attention models do better on short text (SMTR paper).
- Source: [github.com](https://github.com/baudm/parseq), [arXiv 2207.06966](https://arxiv.org/abs/2207.06966)
- Licence: code Apache-2.0 / weights no separate licence stated. CubiCasa5K leakage: no.
- Cost: 3 h work, 2-4 GPU-h for 50k crops on 12 GB (estimate)
- Experiment: Train PARSeq-S and the v6 small recogniser on the same rendered plus dev crops; compare exact match and abstain behaviour per room type.
- What breaks on our images: 94-class head must be re-initialised for diacritics; trained on photographs; requirements pin old torch.
- Moves: room-types. Why this group: strongest alternative to the PP-OCR recogniser
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i204"></a>
### 204. Rotation and +-5 degree augmentation in recogniser fine-tuning

- What: Add 0/90/180/270 rotation, +-5 degree rotation, scale 0.8-1.2, Gaussian blur and synthetic line noise to training crops.
- Evidence (adjacent-field): Removing rotation from the recipe cost about 15 average points (UnionST); the rebar recogniser used rotation +-5, scale 0.8-1.2, blur and line noise to mimic lines crossing text.
- Source: [arXiv 2602.06450](https://arxiv.org/abs/2602.06450), [frontiersin.org](https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2026.1839808)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: none extra
- Experiment: Ablate each augmentation on the held-out dev crops.
- What breaks on our images: Overlong augmentation hurts small data.
- Moves: room-types. Why this group: part of any fine-tune
- Reports: lit-ocr-a, lit-ocr-b

<a id="i205"></a>
### 205. Tune detector scale and thresholds for tiny text

- What: Upscale the sheet before detection, lower box_thresh to 0.3, and set limit_side_len per call instead of patching configs; tile large renders first.
- Evidence (our-idea): Own page-like test: default detector found 113 of 120 upright 8-12 px codes; 2x enlargement 114, box_thresh 0.3 gave 113; so little gain on clean renders. PaddleOCR det filters drop boxes under 3 px; training masks boxes under 8 px.
- Source: [github.com](https://github.com/PaddlePaddle/PaddleOCR)
- Licence: code Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 h work (estimate)
- Experiment: On real dev images count detected label boxes per room type for upscale 1x/2x/3x and box_thresh 0.5/0.3; report recall.
- What breaks on our images: Clean-render result may not hold on real images with hatching.
- Moves: room-types. Why this group: cheap check on real images only
- Reports: lit-ocr-a, lit-ocr-c

<a id="i206"></a>
### 206. Check readers on Finnish decimal commas

- What: Test the number reader on strings like 12,2 and mm sizes with spaces (1 010 x 2 110).
- Evidence (search-only): Dodge and Lv digit readers trained on dot decimals; real plan prints '910 x 2 110'.
- Source: [sivakka.fi](https://sivakka.fi/tampuuri/attachments/manual-floorplan-menninkaisentie3c69)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h
- Experiment: Read accuracy on dev strings with commas.
- What breaks on our images: none
- Moves: scale-areas. Why this group: Cheap risk check.
- Reports: lit-scale-a, lit-scale-b

<a id="i207"></a>
### 207. Keep fixture codes out of room labels (AP, JK, PA, L, MU, PY, SK, IV)

- What: Classify reads that match the fixture-code list as fixtures, not rooms, so SK or L never becomes a room type.
- Evidence (search-only): Fixture codes in the same legends: AP dishwasher, JK fridge, PA freezer, L cooker, MU microwave, PY laundry cupboard, RK group board, SK cleaning cupboard.
- Source: [asuntotuotanto.hel.fi](https://asuntotuotanto.hel.fi/system/files/mediabank/2025-05/00_asuntopohjat_kaikki_asunnot_1.pdf)
- Licence: public documents. CubiCasa5K leakage: n/a.
- Cost: under 1 h work (estimate)
- Experiment: Count room-label false positives with and without the filter on dev images.
- What breaks on our images: Overlap between room and fixture codes (K, L, S).
- Moves: fixtures. Why this group: cheap precision gain
- Reports: lit-ocr-a, lit-ocr-c

## Later

<a id="i208"></a>
### 208. Detect text in 256 px tiles

- What: Tile the image at 256 px with overlap for text detection rather than downscaling.
- Evidence (floor-plans): Faster R-CNN AP 90.12% at tile 256 on CubiCasa5K text; pretrained EAST 15-25%.
- Source: [iopscience.iop.org](https://iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017)
- Licence: none released. CubiCasa5K leakage: yes.
- Cost: 1 day
- Experiment: Compare text recall tiled and untiled on dev.
- What breaks on our images: Our images are already small; tiling mostly upscales.
- Moves: scale-areas. Why this group: Related to upscaling.
- Reports: lit-scale-a, lit-scale-b

<a id="i209"></a>
### 209. Read the printed ratio from a tight crop, not the whole sheet

- What: Crop the label region before reading the ratio.
- Evidence (adjacent-field): GPT-4o whole sheet gave '110'; crop gave '1:10' (Lombardi Figs. 4-5).
- Source: [arXiv 2504.08645](https://arxiv.org/pdf/2504.08645)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Read rate whole vs crop on dev.
- What breaks on our images: Bare plans may have no title block.
- Moves: scale-areas. Why this group: Minor.
- Reports: lit-scale-a

<a id="i210"></a>
### 210. Mix targeted synthetic crops into real ones when fixing confusable characters

- What: When fixing a confusion pair (M/N, K/R, 0/O), add synthetic lines for those characters to real training data and keep a fixed held-out list.
- Evidence (adjacent-field): A v6 medium fine-tune on 55,740 lines plus 287 targeted lines cut errors on 6 confusable characters from 41 to 16, but 10 previously correct lines broke (PaddleOCR issue 18299).
- Source: [github.com](https://github.com/PaddlePaddle/PaddleOCR/issues/18299)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none extra
- Experiment: Track a fixed held-out dev list across fine-tune rounds and report regressions.
- What breaks on our images: One user report.
- Moves: room-types. Why this group: guards the fine-tune against regression
- Reports: lit-ocr-c

<a id="i211"></a>
### 211. Detector crops then an off-the-shelf reader for short numerals (PatentOCR pattern)

- What: Detect short identifier regions with a trained detector then read the crops with EasyOCR or PaddleOCR, and test both readers on the same crops.
- Evidence (adjacent-field): 2,236 patent drawings: trained YOLOv8m plus EasyOCR 89.76% exact, PaddleOCR 77.21% on the same crops; whole-sheet untrained PaddleOCR 62.67%, EasyOCR 86.47% (Scientific Data 2026).
- Source: none
- Licence: code GPL-3.0, detector AGPL. CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: Pattern only; compare two readers on identical crops.
- What breaks on our images: Denominators are detected regions; labels sit inside rooms not beside leaders; licences.
- Moves: room-types. Why this group: pattern evidence for testing two readers
- Reports: lit-ocr-a

<a id="i212"></a>
### 212. Fine-tune on the hard crops, not on all crops

- What: Pick training crops the stock reader gets wrong or scores low, and fine-tune on these rather than the whole set.
- Evidence (adjacent-field): Water-meter reading: a PP-OCR reader fine-tuned on 1,000 hard images beat the same reader on all 3,250 (90.90% exact on 55 images, tiny test, same authors).
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h extra (estimate)
- Experiment: Fine-tune on hard-only vs all crops of equal budget and compare exact match.
- What breaks on our images: Tiny test set; digits only.
- Moves: room-types. Why this group: small adjacent-field result
- Reports: lit-ocr-c

<a id="i213"></a>
### 213. Real-world super-resolution on text crops only, gated by a vocabulary match

- What: Apply Real-HAT-GAN x4 (fidelity model) to crops only, accept the read only if it matches the table, and A/B against Lanczos.
- Evidence (adjacent-field): Licence-plate entry: no SR 7.27 to 9.27 (max 10) at 12-20 px width; the competition organisers say there was no dominant design and third place used no SR; diffusion SR hallucinates text (DiffBIR OpenOCR F1 38.73).
- Source: [arXiv 2607.08896](https://arxiv.org/abs/2607.08896), [arXiv 2604.22506](https://arxiv.org/abs/2604.22506), [arXiv 2510.26339](https://arxiv.org/abs/2510.26339)
- Licence: code Apache-2.0 / weights licence not stated. CubiCasa5K leakage: no.
- Cost: 1 h to test (estimate)
- Experiment: Count exact match with SR vs Lanczos on dev crops and count characters changed to another valid code.
- What breaks on our images: Invented strokes can turn MH into NH; no hallucination measurement in either plate paper.
- Moves: room-types. Why this group: untested hallucination risk; Lanczos first
- Reports: lit-ocr-b

<a id="i214"></a>
### 214. Fine-tune SVTRv2 (OpenOCR) as an alternative recogniser, CTC and attention variants

- What: Fine-tune SVTRv2-T or S from the OpenOCR repo; try the attention variant and a CTC variant as a cross-check.
- Evidence (adjacent-field): Union14M multi-oriented 89.0, contextless 86.1 (SVTRv2-B); +2.46 multi-oriented from the feature rearrangement module; a CRNN-style reader gets 13.0 on rotated text.
- Source: [arXiv 2411.15858](https://arxiv.org/abs/2411.15858), [github.com](https://github.com/Topdu/OpenOCR)
- Licence: code Apache-2.0 / weights licence not stated. CubiCasa5K leakage: no.
- Cost: 3 h work (estimate)
- Experiment: Same crops as the PARSeq run; compare per room type.
- What breaks on our images: No English-only checkpoint, synthetic-only config is TODO, weights on Google Drive.
- Moves: room-types. Why this group: only if PARSeq and v6 fail
- Reports: lit-ocr-b, lit-ocr-c

<a id="i215"></a>
### 215. Pretrain a text-region detector on rendered diagrams

- What: Pretrain the text detector on synthetic drawings with our label font, then fine-tune on dev boxes.
- Evidence (adjacent-field): Poly-DETR with synthetic-diagram pretraining 79.7 vs 73.2 without; scene-text pretraining 80.4; zero-shot scene-text 30.6 (arXiv 2606.15886).
- Source: [arXiv 2606.15886](https://arxiv.org/abs/2606.15886)
- Licence: paper CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 4 h work (estimate)
- Experiment: Compare detector recall with scene-text, synthetic and no pretraining on dev tiles.
- What breaks on our images: 948 diagrams in the paper; Latin only for us.
- Moves: room-types. Why this group: only if detector recall is the limit
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i216"></a>
### 216. Fine-tune TESTR as an end-to-end label spotter

- What: Fine-tune TESTR on dev text boxes with each abbreviation as a class or text.
- Evidence (adjacent-field): Line diagrams: F1 30.6 zero-shot to 80.4 fine-tuned (region detection, not reading) and 47.4 without scene-text pretraining (arXiv 2606.15886); MapText 2025 fine-tuned baseline 89.5 H-mean.
- Source: [arXiv 2606.15886](https://arxiv.org/abs/2606.15886), [github.com](https://github.com/mlpc-ucsd/TESTR)
- Licence: code Apache-2.0 but built on non-commercial AdelaiDet / weights not stated. CubiCasa5K leakage: no.
- Cost: 6+ h work (estimate)
- Experiment: Only after text boxes exist; compare with the docTR/PaddleOCR detector plus recogniser.
- What breaks on our images: Licence lineage unresolved (issue 15), last push 2023, needs polygon boxes.
- Moves: room-types. Why this group: licence question and no boxes
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i217"></a>
### 217. LoRA-tuned small VLM as a crop reader on disagreements

- What: Read only the crops where two readers disagree with a Qwen3.5-0.8B/4B or GOT-OCR2 reader on a given box.
- Evidence (adjacent-field): Maps: adapted 4B reader exact 84.3 / CER 4.6 from 20.5k crops, zero-shot tool pipeline 69.9; 87 ms per crop on an A6000 for 4B, 49.5 ms for 0.8B; an edge-OCR survey found a 3B VLM beat a recogniser on English scene crops by 3.5-6 points.
- Source: [arXiv 2611.03339](https://arxiv.org/abs/2611.03339)
- Licence: code/weights Apache-2.0 (Qwen3.5 cards); GOT-OCR2 repo has no LICENSE file. CubiCasa5K leakage: no.
- Cost: 4 to 6 h work, 12-16 GB with LoRA (estimate)
- Experiment: Run only on the disagreement set from the two readers; compare exact match with the vote alone.
- What breaks on our images: Needs 20k crops to reach 84%; VLMs rewrite imperfect text.
- Moves: trust. Why this group: last-resort reader, after cheaper steps
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i218"></a>
### 218. Name which printed area it is

- What: Tag printed areas as huoneala, huoneistoala, kerrosala or unknown; keep 'source unknown' flag.
- Evidence (authors-claim): Decree 365/2010, suomi.fi concepts, permit plans print BRUTTOALA, KERROSALA, HUONEISTOALA.
- Source: [finlex.fi](https://www.finlex.fi/fi/lainsaadanto/2010/365)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h
- Experiment: Label share on dev.
- What breaks on our images: Needs reading labels.
- Moves: scale-areas. Why this group: Prevents mixing.
- Reports: lit-scale-b

<a id="i219"></a>
### 219. PaddleOCR-VL-1.5/1.6 as a tiled second reader and spotter

- What: Run the 0.9B model on 2x tiles or on detector crops to get text plus 4-point quads, and use disagreement with the first reader only as a flag, not a count. Build a parser for its raw output (text then eight LOC tokens).
- Evidence (authors-claim): Zero-shot spotting on ICDAR 2015: PaddleOCR-VL-1.5 45.1 F vs 73.4 for a fine-tuned 4B model (SPaTS 2026); in-house spotting score 0.8621; output changes under small pixel shifts (1.6 report). No drawing number.
- Source: [arXiv 2601.21957](https://arxiv.org/abs/2601.21957), [arXiv 2606.03264](https://arxiv.org/abs/2606.03264)
- Licence: code Apache-2.0 / weights Apache-2.0. CubiCasa5K leakage: unknown.
- Cost: 3 h work, GPU inference (estimate)
- Experiment: Run on 40 dev images tiled at 2x and on crops; count exact room-type reads and where it disagrees with PP-OCRv6; vote across two pixel shifts.
- What breaks on our images: Missed labels are silent; VLMs rewrite short words up to 10% of the time; fine-tuning not supported.
- Moves: room-types. Why this group: second opinion only, after the first reader is settled
- Reports: lit-ocr-a, lit-ocr-c

<a id="i220"></a>
### 220. Read door and window size codes

- What: Test whether PP-OCRv6 keeps the x in size codes such as 9x21 that v5 garbled.
- Evidence (our-idea): v5 read 0 of 32 and 0 of 40; v6 has no evidence.
- Source: [arXiv 2606.13108](https://arxiv.org/abs/2606.13108)
- Licence: code Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 h work (estimate)
- Experiment: Read size-code crops with v6 and report exact match.
- What breaks on our images: Small digits on thin lines.
- Moves: windows-doors. Why this group: unknown gain
- Reports: lit-ocr-c

<a id="i221"></a>
### 221. Floor titles (1. KERROS, ALAKERTA, KELLARI) as a plan-count prior

- What: OCR the printed storey names over each plan and use their number as a second plan count.
- Evidence (search-only): none; no source gives a list of storey titles; search shows one storey per page in Finnish drawing sets.
- Source: none
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 2 h work, depends on the text stage
- Experiment: Count distinct storey words on dev two-plan sheets; compare with the true plan count.
- What breaks on our images: Many plans carry no title; OCR misses 5-10 px labels.
- Moves: plans. Why this group: Needs a sourced vocabulary and a working OCR first.
- Reports: lit-sheet-b, lit-sheet-c

<a id="i222"></a>
### 222. The 2024 floor-plan text paper (YOLOv7 97.5 wmAP, PARSeq best)

- What: Obtain the 2024 paper and its announced weights and annotations, since its text detector and recogniser comparison is the closest in-field result.
- Evidence (search-only): Abstract only: YOLOv7 97.5 weighted mAP for text detection, PARSeq best of four recognisers; not read.
- Source: [doi.org](https://doi.org/10.1016/j.autcon.2023.105156)
- Licence: weights and data announced public. CubiCasa5K leakage: yes.
- Cost: 2 h to read and check (estimate)
- Experiment: Read the paper; check licence, training data overlap with our dev split.
- What breaks on our images: Probably trained on CubiCasa5K; YOLOv7 licence.
- Moves: room-types. Why this group: unread, would change the ranking
- Reports: lit-ocr-b, lit-ocr-c

<a id="i223"></a>
### 223. Swap AGPL YOLO detectors for permissive ones in text patterns

- What: When using a detector then reader pattern, use RF-DETR (Apache sizes), D-FINE, RT-DETR or a DB detector instead of YOLO.
- Evidence (search-only): No published small-text number on plans; DETR-family fine-tunes converge slower than DB for tiny objects (estimate).
- Source: none
- Licence: code Apache-2.0 (Atto/Femto/Pico/XL sizes are PML). CubiCasa5K leakage: no.
- Cost: n/a
- Experiment: Compare as text-box detectors on dev tiles.
- What breaks on our images: Slower convergence on tiny objects.
- Moves: room-types. Why this group: licence swap
- Reports: lit-ocr-a

## Idea or pitch only

<a id="i224"></a>
### 224. PP-OCRv5 drops text between thin lines

- What: On line drawings, PP-OCR can silently drop text rows between thin border lines; check recall near wall lines before trusting a no-detection.
- Evidence (adjacent-field): PaddleOCR issue 18244 (closed unfixed): PP-OCRv5 mobile drops most table rows between thin grid lines.
- Source: [github.com](https://github.com/PaddlePaddle/PaddleOCR/issues/18244)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Count missed labels that sit within 3 px of a wall line.
- What breaks on our images: One user report.
- Moves: room-types. Why this group: a failure mode to watch
- Reports: lit-ocr-a, lit-ocr-c

<a id="i225"></a>
### 225. VLM readers rewrite short codes: put exact-match decoding after any VLM

- What: Do not trust a generative reader on 1-4 letter codes; always match the output to the closed table and check against ink.
- Evidence (adjacent-field): VLMs rewrite imperfect text into plausible words; 4-6 character words up to 10% of the time; PP-OCRv6 faithfulness 93.2% vs 80.6% for a 235B VLM (arXiv 2607.21617, PP-OCRv6 report).
- Source: [arXiv 2607.21617](https://arxiv.org/abs/2607.21617)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: Count VLM-only reads that do not match any code in the dev set.
- What breaks on our images: None for the count if decoded.
- Moves: trust. Why this group: a rule for every VLM item
- Reports: lit-ocr-a, lit-ocr-c

## Do not try (with the reason)

<a id="i226"></a>
### 226. Do not use pretrained scene-text detectors unchanged

- What: Pretrained EAST gets 15-25% AP on CubiCasa5K; fine-tune or tile.
- Evidence (floor-plans): Schoenfelder and Koenig 2022.
- Source: [iopscience.iop.org](https://iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: scale-areas. Why this group: Measured poor.
- Reports: lit-scale-a

<a id="i227"></a>
### 227. Ask DeepSeek-OCR to locate each vocabulary code with its grounding prompt

- What: Prompt with Locate <ref>MH</ref> for each code and take the returned box, run on PNG crops only.
- Evidence (adjacent-field): A text-to-region benchmark on document pages scored DeepSeek OCR2 at F1 11.66 vs 72.8 for Qwen3.5-397B (arXiv 2604.00161); a user asking for the box of each number got none (issue 210). No drawing result.
- Source: [arXiv 2604.00161](https://arxiv.org/abs/2604.00161), [github.com](https://github.com/deepseek-ai/DeepSeek-OCR)
- Licence: code MIT (requirements pull PyMuPDF AGPL) / weights MIT. CubiCasa5K leakage: unknown.
- Cost: 2 h work, GPU (estimate)
- Experiment: None worth running before the first-reader items; if run, 40 dev images and a pixel check of each returned box against ink.
- What breaks on our images: May return a box where there is no label; PyMuPDF AGPL breaks the project licence rule if the PDF path is installed.
- Moves: none. Why this group: measured at 11.7 on the nearest benchmark and an AGPL dependency
- Reports: lit-ocr-a, lit-ocr-c

<a id="i228"></a>
### 228. Non-commercial spotters (DeepSolo, DPText-DETR, PaLeTTe weights, MapTextPipeline)

- What: Do not use: DeepSolo and the models built on it carry the AdelaiDet non-commercial licence; PaLeTTe weights are modified PolyForm Noncommercial; PaLeTTe trains on 4 A100.
- Evidence (adjacent-field): MapText 2025 winners reach 91.1 H-mean on Rumsey; licences read from LICENSE files.
- Source: [github.com](https://github.com/ViTAE-Transformer/DeepSolo), [arXiv 2506.15010](https://arxiv.org/abs/2506.15010)
- Licence: non-commercial. CubiCasa5K leakage: no.
- Cost: none
- Experiment: None.
- What breaks on our images: Cannot ship.
- Moves: none. Why this group: licence
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i229"></a>
### 229. eDOCr2 for mechanical drawings

- What: Do not use eDOCr2 on floor plans: it does not transfer across drawing types.
- Evidence (adjacent-field): An independent reproduction on PCB drawings localised 13 of 78 items, exact match 0 of 78, NED 0.9856 (arXiv 2608.29268).
- Source: [arXiv 2608.29268](https://arxiv.org/abs/2608.29268)
- Licence: code MIT. CubiCasa5K leakage: no.
- Cost: none
- Experiment: None.
- What breaks on our images: Trained on mechanical drawings.
- Moves: none. Why this group: does not transfer
- Reports: lit-ocr-a, lit-ocr-b

<a id="i230"></a>
### 230. Detector followed by an OCR-free generative reader (Donut or Florence-2)

- What: Detect oriented text boxes, read each crop with a fine-tuned Donut. Swap the YOLO detector for a permissive one.
- Evidence (adjacent-field): Mechanical drawings: Donut F1 94.0, Florence-2 85.0 (arXiv 2506.17374); a follow-up on letters scores 0.672 vs 0.963 on numbers (arXiv 2510.21862); an independent reproduction with 10 epochs read none usably (arXiv 2608.29268); Donut hallucination rate 10.8%.
- Source: [arXiv 2506.17374](https://arxiv.org/abs/2506.17374), [arXiv 2510.21862](https://arxiv.org/abs/2510.21862), [arXiv 2608.29268](https://arxiv.org/abs/2608.29268)
- Licence: Donut MIT; YOLO AGPL. CubiCasa5K leakage: no.
- Cost: 6 h work, GPU (estimate)
- Experiment: Not recommended; if tried, same dev crops as the recogniser fine-tune.
- What breaks on our images: Letters are the hard half (0.672); generative readers invent text about one time in nine; detector is AGPL.
- Moves: none. Why this group: a small trained recogniser beats a generative reader on short codes
- Reports: lit-ocr-a, lit-ocr-b

<a id="i231"></a>
### 231. Models excluded by licence (HunyuanOCR, MinerU2.5 weights, YOLO detectors, Nemotron OCR v2 pending)

- What: HunyuanOCR licence excludes the EU, MinerU2.5 weights are AGPL, Ultralytics YOLO is AGPL, and Nemotron OCR v2 is under the NVIDIA Open Model License, which is not on the allowed list. Swap YOLO for RF-DETR (Apache sizes), D-FINE, RT-DETR or the docTR/PaddleOCR DB detectors.
- Evidence (adjacent-field): Licences read from files and model cards.
- Source: [huggingface.co](https://huggingface.co/tencent/HunyuanOCR)
- Licence: AGPL / custom. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None; Nemotron OCR v2 only as a zero-shot baseline if a licence decision allows it.
- What breaks on our images: Cannot ship.
- Moves: none. Why this group: licence
- Reports: lit-ocr-a, lit-ocr-b

<a id="i232"></a>
### 232. Do not put generative super-resolution in the count path

- What: Keep diffusion or GAN SR out of the counting stage; if used, only on text crops behind a vocabulary gate.
- Evidence (adjacent-field): Diffusion SR text hallucination measured (arXiv 2510.26339); no paper measures substituted characters from GAN SR on crops.
- Source: [arXiv 2510.26339](https://arxiv.org/abs/2510.26339)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None.
- What breaks on our images: A wrong letter in a 2-letter code cannot be absorbed by the count.
- Moves: trust. Why this group: rule, not an experiment
- Reports: lit-ocr-b

<a id="i233"></a>
### 233. Assume about 90% of read dimension strings are right

- What: Plan for 10% wrong strings; add a geometry check before a read value fixes a scale.
- Evidence (adjacent-field): Hallucination 0.104/0.136; GD&T F1 61.5%; strict OCR 85.7-90.2%.
- Source: [arXiv 2510.21862](https://arxiv.org/pdf/2510.21862), [arXiv 2411.03707](https://arxiv.org/pdf/2411.03707)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: trust. Why this group: Do not trust one reading.
- Reports: lit-scale-a, lit-scale-b, lit-scale-c

<a id="i234"></a>
### 234. Tesseract and EasyOCR for 5-12 px labels

- What: Skip: Tesseract wants about 30 px capitals, EasyOCR drops boxes of 20 px or less by default and has no Finnish; PaddleOCR on whole sheets misses text.
- Evidence (adjacent-field): MapText 2025 PaddleOCR entry had detection recall 40.0 (H-mean 59.5); patent numerals: PaddleOCR 62.67% whole-sheet vs EasyOCR 86.47%, so the better reader differs by domain; EasyOCR fi not in the Latin language list.
- Source: [weinman.cs.grinnell.edu](https://weinman.cs.grinnell.edu/~weinman/pubs/lin25icdar.pdf)
- Licence: code Apache-2.0. CubiCasa5K leakage: no.
- Cost: none
- Experiment: If a second off-the-shelf reader is wanted for a vote, test docTR or EasyOCR on crops with min_size lowered, not on whole sheets.
- What breaks on our images: Silent small-box drops.
- Moves: room-types. Why this group: known to miss tiny text
- Reports: lit-ocr-a, lit-ocr-c

<a id="i235"></a>
### 235. Document VLM readers with boxes (dots.ocr, dots.mocr, GLM-OCR, LightOnOCR-2)

- What: Run a document OCR VLM for text with positions. dots.mocr claims scene spotting; the others give element-level output only.
- Evidence (search-only): No drawing numbers. On small incidental text, document VLMs reach about 43-50 detection F and dots.mocr 10.8 end to end (SPaTS, ICDAR 2015, zero-shot).
- Source: [arXiv 2603.13032](https://arxiv.org/abs/2603.13032), [github.com](https://github.com/rednote-hilab/dots.ocr)
- Licence: code MIT (dots.ocr) / weights MIT. CubiCasa5K leakage: unknown.
- Cost: 3 h work, GPU (estimate)
- Experiment: Not recommended before the first-reader items.
- What breaks on our images: Element-level boxes, not word-level; no evidence for 2-letter labels.
- Moves: none. Why this group: no word-level boxes and no evidence on small text
- Reports: lit-ocr-a, lit-ocr-c
