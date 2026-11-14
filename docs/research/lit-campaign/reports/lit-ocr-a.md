# lit-ocr-a: text on drawings, field and state of the art 2025-2026 (scope L5, angle a)

Worker lit-ocr-a, read-only. FINAL, 2026-11-14 about 01:14 (machine clock; closed early on the orchestrator's new deadline); updated each round, see the reading log
`lit-ocr-a-log.md` (one line per source opened). Marks: **V** = I read it on the page named (date read 2026-11-14);
**R** = reported, the authors' own claim as I read it in their paper; **S** = search snippet only, not a read.
No weights or datasets were downloaded and nothing was run: every number below is from a paper or a card.

## 0. What this report adds to the earlier ones

Earlier reports (RapidOCR/PP-OCR mobile measured 23-81% exact per room type on 40 images, WC rooms 81%, size codes 0/32;
Tesseract wants about 30 px capitals; Surya out by licence; small OCR VLMs listed but never judged for scattered short
labels or positions) left four things open. This pass answers them from sources:

1. **Is there floor-plan-specific text work, and what does it say?** Yes, one line of work, and it is the best evidence
   we have: Schönfelder & König (2022, V) annotated text on 399 CubiCasa5K and 122 CVC-FP plans and got a fine-tuned
   Faster R-CNN to AP[.5:.95] 90.12% on CubiCasa5K tiles, against 69.16% for a pretrained EAST. A 2026 pipeline (V)
   fine-tuned CRAFT + a TPS-STN-CRNN recogniser on 1,000 plans and reads dimension numbers exactly 90.2% (own test),
   85.7% (external set). Both are fine-tunes on CubiCasa5K text: strong for method, **leaky as checkpoints**.
2. **Do 2025-2026 document VLMs return positions for scattered labels?** Three do: PaddleOCR-VL-1.5/1.6, DeepSeek-OCR
   (a "locate this string" prompt), dots.mocr. None has a measurement on drawings or on 1-3 character labels.
3. **Does a closed vocabulary or language model help?** For our short codes, a language-model decoder does not (TiCLS,
   V: the gain sits in words of 11+ characters); a closed vocabulary with exact match for short codes stays the
   right tool.
4. **Do off-the-shelf spotters survive line drawings?** No. Zero-shot scene-text spotters collapse on line diagrams and
   map text and need fine-tuning on a few hundred to a few thousand images; full-image VLM spotting collapses too.
   The cleanest number is from SPaTS (2026, V): on ICDAR 2015, the small incidental-text benchmark, zero-shot
   end-to-end F (strong lexicon) is PaddleOCR-VL-1.5 45.1, HunyuanOCR 43.2, dots.mocr 10.8, Qwen3.5-397B 42.6,
   GPT-5.4 12.4, Claude-Sonnet-4.6 11.7, against 73.4 for the same authors' fine-tuned 4B model. Document-OCR VLMs are good at lines in documents and weak at spotting scattered small text.
5. **Is the 2026 stack stable enough to count with?** PaddleOCR-VL-1.6's own report (V) says 1.5 outputs change a lot
   under small pixel shifts and mild distortions. For a counting pipeline that is a reason to run any VLM reader on
   crops with a fixed preprocessing and to vote across two shifts, not to trust one pass.

Scope lines: AECV-Bench, DrawingVQA, FloorplanVLM and Raster2Seq belong to L1/L7; one line each at the end, no digging.

## 0b. What the later rounds changed (details in section 8)

- Row 4 (DeepSeek-OCR locate) is now **maybe, low**: a 2026 benchmark of "locate this text" scores DeepSeek OCR2 at F1 11.7 on document pages (TABench), and the repo pulls in an AGPL package (PyMuPDF).
- Rows 1 and 3 got concrete traps from code: EasyOCR drops boxes under 20 px by default; PaddleOCR's detector training masks boxes under 8 px; PaddleOCR's default detection runs near full resolution (one A4 scan took 43 GB RAM); docTR has no such cut-off; CRAFT's repo has no training code.
- The PP-OCRv5/v6 dictionaries contain ä ö å, so the Finnish character set is covered (accuracy still unmeasured).
- Every V number in the top-5 and full table was re-opened and matches its source, except two source labels I corrected (84.7% comes from the HF card, MapText numbers from the Grinnell-hosted report PDF) and one metric clarification (the line-diagram TESTR figures are detection, not reading).
- Forward walks done: eDOCr2, PaLeTTe, the 2023 floor-plan text paper, PaddleOCR-VL-1.5 (OpenAlex and Semantic Scholar); SPaTS and ArabGeoText have no citers yet; Hybrid-VL's walk was rate-limited.

## 1. Top 5 (floor-plan work and transfers in one list)

| # | Candidate | Verdict | Why, in one line | Source (V unless marked) |
|---|---|---|---|---|
| 1 | **Detector, then rectified crop, then a small fine-tuned reader**, fine-tuned on our own label crops (pattern: CRAFT/DBNet-style detector + TPS/CRNN or SVTR or PaddleOCR rec; tiles of 256-512 px) | **try** | Only family with floor-plan numbers: 90.12 AP on CubiCasa tiles (256 px tiles beat 1024 px tiles: 74.66), 90.2% exact on dimension strings after 1,000-image fine-tune; the map analogue (detector + crop + 48 px min height + adapted reader) beat direct VLM spotting 74.4 vs 12.8 E2E H-mean | iop.org 2022 article 082017 (CC BY 3.0); ec-3.org 2026 paper 212; arXiv 2611.03339 |
| 2 | **PaddleOCR-VL-1.5 / 1.6 text spotting** (0.9B, 4-point quads, spotting at higher max resolution) | **try as second reader / spotter, tiled** | Apache-2.0 code and weights, returns rotated quads and text in one call, in-house spotting benchmark overall 0.8621 (blur 0.8422, common 0.7713); but no drawing or 2-letter number, and ArabGeoText shows a full-image VLM spotter (Qwen3.5-4B, a different model) failing on small map labels | arXiv 2601.21957 (full text); HF cards 1.5 and 1.6 |
| 3 | **PP-OCRv6 (June 2026) or PP-OCRv5 latin, fine-tuned on our crops**, closed-vocabulary decoding | **try** | Detector and recogniser in one Apache-2.0 family, ONNX exports, 1.5M / 7.7M / 34.5M parameter tiers; v6 medium detection Hmean 86.2 overall and 93.8 on their rotated-text subset (v5 mobile 64.7), while Gemini-3.1-Pro and GPT-5.5 score 46.8 and 45.6 on detection in the same table (authors' in-house set, R); v5 latin lists Finnish and Swedish by name, v6 says 46 Latin-script languages without naming them, but its dictionaries contain ä ö å (Finnish accuracy not measured); this is the family we measured at 23-81%, so the task is fine-tuning plus exact-match decoding, as the 2026 BIM and rebar papers did | HF cards PP-OCRv6_medium_rec/det (Apache-2.0); PaddleOCR PP-OCRv6.en.md; HF card latin_PP-OCRv5_mobile_rec; PaddleOCR repo configs and dictionaries |
| 4 | **DeepSeek-OCR "Locate <\|ref\|>MH<\|/ref\|>"** as word spotting: ask for each vocabulary code, get a box | **maybe, low** (TABench text-to-region F1 11.7 for DeepSeek OCR2, section 8) | MIT code and weights (PyMuPDF AGPL in its requirements: PNG crops only); the prompt exists and is the closed-vocabulary idea done by a VLM; modes up to 1280 px or tiled "Gundam"; no benchmark of the locate prompt on small labels; the one text-to-region benchmark (TABench, documents) is poor for DeepSeek OCR2 | github.com/deepseek-ai/DeepSeek-OCR README |
| 5 | **A DETR text spotter (TESTR, Apache-2.0) fine-tuned, optionally with each abbreviation as a class** | **maybe** | On line diagrams TESTR zero-shot F1 30.6 becomes 80.4 after fine-tuning; class-aware single-character classes reach mAP50 68.3 on a tiny set (both are region detection and classification, not reading); ICDAR'25 MapText: a fine-tuned TESTR baseline 89.5 HMean; but last code push 2023, and the winners use DeepSolo (non-commercial) | arXiv 2606.15886; ICDAR 2025 MapText report (weinman.cs.grinnell.edu/~weinman/pubs/lin25icdar.pdf); gh api |

Not in the top 5 and why: eDOCr2 (mechanical drawings; an independent reproduction localized 13 of 78 items on a different
drawing type, NED 0.9856: domain does not transfer), PaLeTTe (best published rotated-map-label spotter, but its pretrained-model
licence is a modified PolyForm Noncommercial), HunyuanOCR (licence excludes the EU), MinerU2.5 (weights AGPL-3.0).

## 1b. What breaks on our images, per top-5 row

1. **Detector + crop + reader.** Our labels are 5-12 px high (the orchestrator context file, section 6 targets), against a median of 18 px in the map benchmark
   (ArabGeoText: only 1.8-13.4% of its labels are under 12 px). The
   2022 floor-plan study got its best AP with 256 px tiles of images whose side runs 152 to 4,960 px, so tile size must be
   tuned per image size, not fixed. A detector needs text boxes; the label export carries room labels, not text boxes
   (open question 1). Upscale crops to a minimum height before the reader (ArabGeoText: box grown by 12% of its short side, projective rectification, bicubic upscale to at least 48 px high and 192 px wide; Lanczos is my substitute, untested); never a
   generative upscaler. CubiCasa5K-trained checkpoints from the 2022 and 2026 papers are leaky and unreleased anyway.
2. **PaddleOCR-VL-1.5/1.6 spotting.** No drawing number exists; on small incidental text it reads about 45 F (zero-shot,
   ICDAR 2015). Output positions are quads from a language model, so a missed label is silent. 1.5 is fragile under
   small pixel shifts (the 1.6 report). A 0.9B model on a full 855 px sheet sees small labels at under 10 px: run it on 2x tiles or on the
   detector's crops instead.
3. **PP-OCRv5 latin recogniser.** Trained on lines of words: the 84.7% is whole-line exact on ordinary Latin text, not
   2-letter codes. The recogniser's language prior can turn "MH" into a word; the fix is fine-tuning on our crops with a
   restricted character set, and decoding against the label table.
4. **DeepSeek-OCR locate-by-string.** Asking for "MH" may return a box when none exists (untested; the VLM-OCR hallucination
   study in section 3 found spurious content from VLM transcription), so every returned box would need a pixel check against ink. Native
   modes are square (512-1280 px); an elongated sheet is padded or tiled, and rotated labels are not guaranteed.
5. **TESTR-style DETR spotter.** Needs polygon text boxes for training; scene-text pretraining is what makes it work (30.6
   to 80.4 F1 text-region detection after fine-tuning on line diagrams, 47.4 without pretraining; not reading), and the public weights were trained on scene
   text with licences I did not check. Code last pushed in January 2023.

## 1c. Answer to the scope question (expected accuracy on 2-4 character labels at 10 px)

No paper in 2025-2026 reports it. What the sources support, as an estimate (E, mine) and not a result:
- off-the-shelf PP-OCR family: our own earlier measurement stands (23-81% exact per room type, short codes are the misses);
  the MapText'25 PaddleOCR entry had 40% detection recall on map text, the same failure;
- fine-tuned detector + recogniser on floor-plan text: 90% AP (detector, CubiCasa tiles) and 85.7-90.2% exact on
  dimension strings (recogniser) are the best published figures; expect the same order, 85-90%, only if the crops are at
  least about 12 px high and the training labels cover our label set; below 8 px I expect the glyph loss the Swiss
  experiment saw (16/30 at half resolution).
- Closest published reading numbers once a box is found (all different drawing types, none at 10 px): 96.3% rebar annotations (fine-tuned, 5,054 train crops), 92.9% character accuracy for fine-tuned TESTR on map words, 89.76% exact on patent numerals (trained detector + EasyOCR), 0.672 F1 for fine-tuned Donut on alphabetical title-block text, 0 usable reads from a short-schedule Hybrid-VL reproduction on PCB drawings. Read as a spread: a tuned small reader lands around 90%, an untuned or under-trained generative one can fail completely.
- Cheapest fix, in order: (1) tiles at 2x with bicubic or Lanczos resampling, (2) fine-tune the recogniser on room-label crops with the closed
  character set, (3) exact-match decoding against the label table with the Finnish codes of section 6, (4) a second reader
  (PaddleOCR-VL spotting) only to flag disagreement, not to count.

## 2. Full table

Columns: field = floor plan / engineering drawing / maps / documents (where the method comes from). Leak = trained on
CubiCasa5K or a repackage (yes / no / unknown). "Hours" are my estimates, marked E, not measured.

| Method | Field | Year, venue | Code (licence) | Weights (licence) | Training data | Reported result (benchmark, metric, input) | Leak | Fills | Hours to first number (E) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Text detector Faster R-CNN, tiled (Schönfelder & König) | floor plan | 2022, WBC 2022 (IOP, CC BY 3.0) V | not found | not released as far as I read | 399 CubiCasa5K + 122 CVC-FP images, own text boxes | AP[.5:.95] 90.12% CubiCasa5K at 256 px tiles; 74.66% at 1024; EAST pretrained 69.16%; CVC-FP to CubiCasa transfer 41.29% | **yes** (CubiCasa5K) | detector for room labels | 3 E (train our own on dev boxes) | try (method only) |
| PatentOCR (detect + read short component numerals in line drawings) | patent line drawings | 2026-07, Scientific Data (paper CC BY-NC-ND) V | repo GPL-3.0 (gh api) | n/a (YOLOv8 AGPL, EasyOCR Apache-2.0) | 2,236 drawings, 20,165 identifier masks (HF dataset, no licence tag) | trained YOLOv8m + EasyOCR exact 89.76%, char 95.63% inside detected regions; YOLOv8m + PaddleOCR 77.21%; whole-sheet untrained PaddleOCR 62.67% vs EasyOCR 86.47% (region-conditional denominators, not end-to-end); inputs resized to 640 px | no | pattern | n/a | idea + evidence (detect crops, then read) |
| FP-TXT text-box annotations (Schönfelder et al.) | floor plan | 2023-10, Zenodo 7921780 V (JSON record) | annotation scripts in the record | annotations MIT per the record text (Zenodo licence field empty) | boxes (machine-printed, handwritten) over CubiCasa5k, CVC-FP, BRIDGE; no transcriptions | n/a, a dataset | **yes** for CubiCasa5K images | detector training boxes | 1 E to read, not downloaded | maybe (check overlap with our dev split first) |
| CRAFT + TPS-STN-CRNN, BIM pipeline (Liang et al.) | floor plan | 2026, EC3 Corfu V | none seen | none seen | 1,000 plans from CubiCasa5K + CVC-FP | strict exact match on dimension numbers 90.2% own test, 85.7% external set (ResBIM) | **yes** | dimensions, labels | 4 E | try (method only) |
| Detector + rectified upscaled crop + LoRA VLM reader (ArabGeoText) | maps | 2026, arXiv 2611.03339 V | not seen | Qwen3.5 base; YOLO26 detector is AGPL | 970 map tiles, 17,875 labels | E2E H-mean 74.4% vs direct VLM 12.8% (Riyadh test, median text 18.4 px, 78.7% rotated); min crop height 48 px | no | pattern only | 3 E | try (pattern; swap YOLO26) |
| PaddleOCR-VL-1.5 | documents + spotting | 2026, arXiv 2601.21957 V | PaddleOCR Apache-2.0 | Apache-2.0 (HF card) | 46M pairs, in-house spotting set | spotting overall 0.8621 in-house (not public); OmniDocBench v1.5 94.5; Real5 skew 91.66; input budget 1280x28x28 pixels (about 1.0 MP), 2048x28x28 (about 1.6 MP) for spotting; 0.9B parameters | unknown, very unlikely | text + quads | 2 E | try |
| PaddleOCR-VL-1.6 | documents + spotting | 2026-11 HF card V | same | Apache-2.0 | n/a | OmniDocBench v1.6 96.34 (leaderboard README) | unknown | text + quads | 2 E | try (newest) |
| PP-OCRv5 latin mobile rec | text lines | 2025; numbers from the HF model card and PaddleOCR multi-language docs page V (arXiv 2507.05595 describes PaddleOCR 3.0, no Latin figure in what I read) | Apache-2.0 | Apache-2.0 (HF card) | n/a | 84.7% whole-line accuracy on their 3,111-image Latin set; Finnish and Swedish listed | no | label text | 1-3 E (fine-tune) | try |
| PP-OCRv6 tiny / small / medium (det + rec) | text lines, any field | 2026-06, PaddleOCR docs + HF cards V | PaddleOCR Apache-2.0 | Apache-2.0 (HF API, medium det and rec) | in-house multi-scenario sets | in-house (R): detection Hmean 80.6 / 84.1 / 86.2, rotated subset 91.0 / 93.7 / 93.8; recognition accuracy 73.5 / 81.3 / 83.2; 50 languages in one model | unknown, very unlikely | text boxes + text | 1-3 E (fine-tune) | try |
| DeepSeek-OCR | documents | 2025, arXiv 2510.18234 S; README V | MIT (gh api), but requirements.txt pulls PyMuPDF (AGPL-3.0): use PNG crops only | MIT (HF card) | n/a | no drawing numbers; modes 512/640/1024/1280, tiled Gundam | unknown | locate-by-string | 2 E | maybe |
| dots.ocr / dots.mocr | documents + scene spotting | 2025-2026 README V | MIT | MIT (HF card) | n/a | no drawing numbers | unknown | text + boxes | 2 E | maybe |
| GLM-OCR | documents | 2026 | Apache-2.0 (gh api) | MIT (HF card) | n/a | not read | unknown | text | not estimated | skip (no positions known) |
| TESTR | scene text spotter | 2022 | Apache-2.0 | not checked | n/a | ICDAR'25 MapText Rumsey Task 3 HMean 89.5 (fine-tuned baseline); line diagrams F1 80.4 after fine-tune | no | boxes + text | 4 E | maybe |
| DeepSolo / DNTextSpotter | scene text | 2023-2024 | non-commercial (AdelaiDet licence text read) | n/a | n/a | MapText'25 winner family, Rumsey HMean 91.1 | no | boxes + text | n/a | skip (licence) |
| PaLeTTe (hyper-local deformable transformer) | maps | 2024-2025, arXiv 2506.15010 V | repo licence not asserted by GitHub; the pretrained-model licence file is a modified PolyForm Noncommercial (read) | not stated | SynthMap+ 73,657 images + scene text | E2E none-lexicon 70.27 / 69.82, full lexicon 79.13 / 78.75 (pretrained, two map sets); 4 A100 | no | rotated text | n/a | skip (licence) |
| TiCLS | scene text | WACV 2026, arXiv 2602.04030 V | repo has no licence file | weights pending at snapshot | scene text | gains concentrated on long words | no | n/a | n/a | skip (no gain at 3-5 chars) |
| Hybrid-VL: YOLOv11-OBB + Donut (Khan et al.) | engineering drawing | 2025, arXiv 2506.17374 V | Donut MIT; YOLO AGPL | Donut MIT, Florence-2 MIT | 1,367 mechanical drawings | Donut F1 94.0 (P 89.2, R 99.2); Florence-2 F1 85.0; detector at 1024 px with 0/90/180/270 augmentation | no | pattern | n/a | maybe (pattern: swap detector) |
| eDOCr2 | engineering drawing | 2025, MDPI Machines (page refused) | MIT (repo LICENSE read) | not stated | mechanical drawings | not read; independent reproduction on PCB drawings: 13/78 localized, NED 0.9856 | no | none | n/a | skip |
| Rebar annotation spotter (DBNet, 3.8M params per abstract R, 6.1 in its own ablation table + transformer rec 15.56M) | engineering drawing | 2026, Frontiers in Built Environment V | release promised | release promised | 1,005 images / 7,108 annotations | recognition 96.3%, detection F1 95.9 | no | pattern | n/a | maybe (fine-tune evidence) |
| Poly-DETR | line diagrams | 2026, arXiv 2606.15886 V | not seen | not seen | 948 diagrams + synthetic | F1 79.7 with synthetic pretrain vs 73.2 none | no | pattern | n/a | idea only |
| Text-enhanced CAD symbol spotting | CAD vector | 2025, arXiv 2510.11091 V | not seen | not seen | FloorPlanCAD (CC BY-NC) | PQ 0.7152 to 0.7352 when text primitives are added | no | idea: text as evidence for symbols | n/a | idea only |

## 3. Transfer notes (other fields, from the forward citation walk)

The forward walks used OpenAlex (`cites:` filter, free, no login): from eDOCr2 21 citing works 2025-2026; from PaLeTTe 15;
from the 2023 floor-plan text paper 69. The relevant 2026 ones were opened (rows above); the rest were titles only.

- **Maps to drawings (ICDAR MapText 2025 report, V).** Task 3 (word detection + recognition), Rumsey set: 1st 91.1 HMean
  (DeepSolo-based), TESTR fine-tuned baseline 89.5; a PaddleOCR (polygon detection on) + image-enhancement entry scored 59.5 with detection recall
  40.0. This is the closest published analogue of short labels over line work at any angle, and it says: that
  off-the-shelf PaddleOCR entry missed 60% of the text; fine-tuned DETR spotters read it. What breaks on our images:
  map labels are 18+ px median, ours 5-12 px (orchestrator context); our text is mostly axis-aligned or exact 90/180 rotations, so the hard
  curved-text machinery buys nothing.
- **Short identifiers in line drawings (PatentOCR, Scientific Data 2026, V).** The nearest published shape to our problem: 1-3
  character numerals and letters beside leader lines on patent line art, 2,236 drawings. Reading detected crops with an
  off-the-shelf recogniser gives 86-90% exact (EasyOCR, Apache-2.0) against 77% for PaddleOCR on the same crops, and
  62.7% for PaddleOCR run on the whole sheet: crops from a trained detector help, and the better reader differs by
  domain, so test two. What breaks: the denominators are the detected regions, not all labels; our labels sit inside
  room outlines rather than beside leader lines; its code is GPL-3.0 and its detector AGPL (idea only).
- **Line diagrams (arXiv 2606.15886).** TESTR fine-tuned on this set reaches region-detection F1 80.4 against 30.6 zero-shot
  and 47.4 without scene-text pretraining (I did not read the train split size). Synthetic diagrams as pretraining help when real data is small. What breaks: 948 images, not 3,828, and
  our text is Latin only, so the multi-script difficulty is absent.
- **Rotation without a page-level orientation step.** Hybrid-VL trains the detector with 0/90/180/270 augmentation and
  oriented boxes; PaddleOCR-VL-1.5 emits 4-point quads; polygon-point spotters (TESTR, PaLeTTe) beat Bezier ones at high
  angles (PaLeTTe paper, V). For exact-multiple rotations an oriented-box detector is enough; nothing here replaces
  the 0/180 text-line classifier for upside-down reads.
- **Lexicon.** TiCLS (V): language-model decoding helps long words; ICDAR15 gains sit at 11+ characters, 3-5 character words
  barely move. MapText full-lexicon vs none: 70.3 vs 79.1 (PaLeTTe pretrained, V): a lexicon is worth about 9 points on
  map names. Our labels are 1-4 letters from a closed table, so decode by exact match against the table, as the earlier
  Swiss pipeline did.
- **Text as evidence for symbols (arXiv 2510.11091).** Adding text primitives lifted CAD panoptic PQ by 2 points: the
  idea (a "WC" label raises the chance of a toilet symbol inside the room) transfers as a stage-8 consistency check, not
  as a model, since the paper uses vector input only.

## 4. Looked for and did not find

- A floor-plan text benchmark published in 2025-2026: none. The only one is the 2022-2023 annotation set above
  (1,222 plans, per a search snippet S for the 2023 article; the journal page refused the headless browser and I did not
  work around it).
- Any accuracy number for 2-4 character labels at 10 px: none in any paper opened.
- Any VLM-OCR measured on drawings with position output: none. AECV-Bench's OCR figure (about 0.95) is text QA, not
  spotting (abstract, V).
- Code or weights for the 2022 and 2026 floor-plan text work: none found. The only released artefact is FP-TXT, a set of
  text-box annotations (no transcriptions) for CubiCasa5k, CVC-FP and BRIDGE images; found through a Zenodo search, record 7921780.
- eDOCr2's own results: the MDPI page is refused to curl, to web-fetch and to the headless browser.
- The 2026 bridge-drawing comparison of ten OCR tools (Results in Engineering): publisher page refused; metadata only.
- Finnish abbreviation list in a peer-reviewed or standards source: none; the list in section 6 comes from public sales
  plan packs only. "PH" appeared in none of them.

## 5. Open questions and missing tools

- Text boxes: FP-TXT (Zenodo 7921780, annotations MIT per its text) labels text boxes on part of CubiCasa5K; check its overlap
  with our dev and eval splits before using it, and whether the SVG text elements give us the same for free.
- Do we have text positions (not only label strings) in the label export? Without boxes for room labels, a detector
  and reader cannot be fine-tuned; the room polygons carry labels, not text boxes (record 0003 as quoted in context).
  Needs an owner check of the SVG text elements.
- A first number is cheap: run PaddleOCR-VL-1.5 spotting and DeepSeek-OCR locate on 40 dev images tiled at 2x, count
  exact room-type reads. Nobody has measured it; I may not run anything.
- Scale reading (printed 1:100, dimension strings) belongs to L6; the 2026 BIM paper above is relevant there.
- Tools missing: no arXiv MCP; WebFetch agents return summaries only, so full texts came from the headless browser and
  local PDF text extraction. ScienceDirect, MDPI and ResearchGate refused the headless browser; not circumvented.
- Pointers for other scopes: AECV-Bench (arXiv 2601.04819, GitHub repo has no licence) and DrawingVQA (CVPR 2026
  Findings) belong to L7; FloorplanVLM (arXiv 2602.06507) and SALI-FP (arXiv 2609.25615, image-generation parsing of
  CubiCasa5K) to L1; DoorDet (2026, Neural Computing and Applications) to L2.

## 6. Finnish room-label abbreviations (sourced, modern new-build packs; older or user-drawn plans vary)

Read as PDF text on 2026-11-14 from three public apartment plan packs: a Helsinki housing company's plan pack with a
two-part legend (shared spaces, then "Asuntopohjissa käytetyt tilanimet"), a Jyväskylä new-build brochure, and the City
of Helsinki housing-production plan pack (2025-05). Where the packs disagree, both are given.

| Code | Meaning (as printed) | Notes |
|---|---|---|
| ET | eteinen (hall, entry) | all three |
| KT | keittotila (kitchen area) | all three |
| K | keittiö (kitchen) | one pack uses K next to KT |
| KPH | kylpyhuone (bathroom) | two packs (38 and 6 hits in the text layer); one of them also uses KH |
| KH | kylpyhuone (bathroom) | two packs: KH and KPH both mean bathroom |
| MH | makuuhuone (bedroom) | all three; plans number them MH1, MH2 ... (seen in all three packs) |
| OH | olohuone (living room) | all three |
| RT | ruokailutila (dining area) | all three |
| S | sauna (one pack: "sauna / löylyhuone"; the shared-spaces list has "S talosauna") | all three |
| VH | vaatehuone (walk-in closet) | all three |
| WC | erillis-WC (separate toilet room) | two of three |
| P | parveke (balcony) | one pack |
| PUKUH | pukuhuone (dressing room) | one pack |
| ALK | alkovi (alcove) | two packs |
| H | asuinhuone (habitable room, generic) | one pack |
| VAR / var | varasto (storage) | two packs |
| SK | siivouskaappi (cleaning cupboard; the pack legend says "Siivouskaappi") | symbol-level code, very frequent in the text layer (39-86 hits per pack), so it is a drawing symbol label, not a room label; "TK" appears only inside "SAVU TK" (flue), not a room |
| AULA, KÄYT | aula (lobby), käytävä (corridor) | shared spaces |

Fixture codes in the same legends (not room labels): AP dishwasher (astianpesukone), JK fridge, PA freezer, L cooker
(liesi), MU microwave, PY laundry cupboard, RK group board, JT manifold, IV ventilation unit, PL balcony door.

Reading for the task: the label set is about 15 codes of 1-5 letters, three of them one letter (K, S, P, H), which is why
exact matching against a closed table, not a language model, is the right decoder, and why a 1-letter "S" or "K" must
also be checked against room context (a sauna stove or a hob inside) before it counts. Not found in any pack: PH.
These are new-build sales packs; CubiCasa5K plans are user-contributed and older, so expect Swedish forms (e.g. K,
KOK, RUM) and handwritten notes, which the 2022 floor-plan text paper (V) also reports.

## 7. Sources opened (all read 2026-11-14)

URL, how read (browser = headless browser full text; pdf = downloaded and text extracted locally; card = HF/README raw;
gh = `gh api` licence; fetch = web-fetch summary of the page).

- arxiv.org/html/2506.15010 PaLeTTe (browser); github.com/kartta-foundation/mapkurator-palette-doc license.md (card)
- weinman.cs.grinnell.edu/~weinman/pubs/lin25icdar.pdf ICDAR'25 MapText report (pdf, full); zenodo.org/records/14392548 (fetch)
- arxiv.org/html/2601.21957 PaddleOCR-VL-1.5 (browser); arxiv.org/html/2606.03264 PaddleOCR-VL-1.6 (browser); HF cards 1.5, 1.6 (card)
- arxiv.org/html/2507.05595 PaddleOCR 3.0 (browser); HF latin_PP-OCRv5_mobile_rec card and PaddleOCR multilingual doc (card)
- github.com/deepseek-ai/DeepSeek-OCR README (card); github.com/rednote-hilab/dots.ocr (browser); arxiv.org/html/2603.13032 dots.mocr (browser)
- huggingface.co/tencent/HunyuanOCR LICENSE (card); github.com/IDEA-Research/Rex-Omni LICENSE (card)
- arxiv.org/html/2611.03339 ArabGeoText (browser); arxiv.org/html/2602.04030 TiCLS (browser); arxiv.org/html/2606.15886 diagram text (browser)
- doi.org/10.24132/csrn.2026-d73 raster-to-vector pipeline with OCR-guided text-pixel removal (pdf; uses an external OCR engine, no OCR accuracy): not ranked
- arxiv.org/html/2607.27902 SPaTS (browser); arxiv.org/html/2607.24077 VLM-OCR hallucination (browser)
- iopscience.iop.org/article/10.1088/1755-1315/1101/8/082017 (pdf, full); ec-3.org/wp-content/uploads/2026/08/EC32026_212.pdf (pdf, full)
- arxiv.org/pdf/2506.17374 Hybrid-VL (pdf, full); arxiv.org/pdf/2505.01530 (pdf); arxiv.org/html/2608.29268 PCB parsing (browser)
- frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2026.1839808 (browser); iaarc.org ISARC2026_1172.pdf (pdf)
- arxiv.org/html/2510.11091 and 2607.12678 text-aided symbol spotting (browser); arxiv.org/html/2609.25615 SALI-FP (browser)
- arxiv.org/abs/2604.23970 and 2601.04819 (fetch, abstract only); github.com/javvi51/edocr2 incl. LICENSE, releases, issues (fetch, gh)
- OpenAlex `cites:` listings for eDOCr2, PaLeTTe, the 2023 floor-plan text paper, PaddleOCR-VL-1.5 (curl, forward walk)
- github.com/PaddlePaddle/PaddleOCR docs PP-OCRv6.en.md and README, HF cards PP-OCRv6_medium_rec/det (card); issues sweeps on PaddleOCR and DeepSeek-OCR (gh)
- opendatalab/OmniDocBench README leaderboard v1.6 (card): top rows OXR-1.0 97.03, TeleOCR 96.91, OvisOCR2 96.47,
  MiniCPM-OCR 1.0 96.44, PaddleOCR-VL-1.6 96.34 (document parsing, not drawings); Apache-2.0 / Apache-2.0 / Apache-2.0
  weights for TeleOCR, OvisOCR2, MiniCPM-OCR 1.0 and PaddleOCR-VL-1.6 (HF API); OXR-1.0 licence not stated.
- Three Finnish plan packs (pdf); `gh api` licence reads for PaddleOCR, DeepSeek-OCR, dots.ocr, GLM-OCR, MinerU, DeepSolo,
  TESTR, PARSeq, CLIP4STR, docTR, CRAFT-pytorch, MMOCR, OpenOCR, Donut, SPaTS.

- Later rounds (2026-11-14): arxiv.org/html/2604.00161 Q-Mask/TABench (browser); arxiv.org/abs/2607.21617 FaithC4 (abstract); arxiv.org/html/2606.24118 PreciseDoc (browser); arxiv.org/html/2606.15886 re-read (browser); PaddleOCR repo files (configs, make_shrink_map.py, requirements, dictionaries) and issues #17637, #17955, #18244, #18403; DeepSeek-OCR issues #210, #223 and requirements; EasyOCR easyocr.py; docTR base.py; CRAFT-pytorch, TESTR, TRDG, RF-DETR READMEs (all gh api); HF model API licences; Semantic Scholar citations of the 2022 paper and PaddleOCR-VL-1.5 (API).

Blocked, not worked around: MDPI (eDOCr2 paper), ScienceDirect (2023 floor-plan text article, 2026 bridge-drawing OCR
comparison), ResearchGate, ACM DL (image-enhancement-for-drawings paper), idunn.no (Norwegian CADAiD drawings paper).

## 8. Addendum (rounds after takeover, 2026-11-14 00:46 onward; every line marked V was read on the page, code or issue named)
- DeepSeek-OCR 2 (arXiv 2601.20552, V): a reading-order document model scored on OmniDocBench v1.5; no small-text grounding numbers found. Does not change the ranking (row 4 stays the original DeepSeek-OCR Locate prompt).
- Hong et al., ISPRS 2025 (V, CC BY 4.0, doi 10.5194/isprs-archives-XLVIII-G-2025-597-2025): object-to-text correspondence model, CLIP ViT-L/14, F1 82.6 (P 86.3, R 79.2) on its own plans; ViT-B/32 only F1 32.3. Transfer: linking a read label to a room needs paired training data we lack; a point-in-polygon rule is the baseline to beat first. Verdict: maybe (later).
- TESTR (V, gh api + README): code Apache-2.0 but its README sends installation and dataset prep through AdelaiDet (non-commercial: its LICENSE file opens with "for non-commercial purposes", re-read this round), last push 2023-01-30, weights licence unstated: treat row 5 as "maybe, with a licence check on the AdelaiDet dependency before use". docTR and EasyOCR (V, gh api): Apache-2.0, pushed 2026-11-13 (both): the active, clean-licence readers for row 1 fine-tuning.
- Repos of the top candidates (V, gh api, 2026-11-14): PaddleOCR Apache-2.0 with permissive requirements (no AGPL/GPL). DeepSeek-OCR is MIT but its requirements.txt lists PyMuPDF (AGPL-3.0): feed it PNG crops and do not install the PDF path, or row 4 breaks record 0006. PaddleOCR issue #17955: the default detection stage runs at near full resolution and one A4 300 dpi scan took ~43 GB RAM (maintainer root cause: `limit_side_len`/`max_side_limit` never downscale) so on our large drawings set a detection side limit or tile first. Issue #18244 (closed stale, unfixed): thin grid lines made PP-OCRv5 drop whole table rows silently, a risk on line drawings. Issue #18403: PP-OCRv6 recogniser dictionary lacks some German characters; check ä/ö/å/Å by running the dictionary file before trusting v6 for Finnish.
- Update to open question on Finnish (V, dictionary files in the PaddleOCR repo read 2026-11-14): the PP-OCRv5 latin, PP-OCRv6 and PP-OCRv6 tiny dictionaries all contain ä ö å Ä Ö Å, so the character set is not the blocker (issue #18403 is about German quotation marks). Accuracy on Finnish room labels is still unmeasured; closed-vocabulary decoding remains the plan.
- Gap re-search (4 more queries, 2025-2026 filter, OpenAlex): still no floor-plan text benchmark. Two 2026 papers read in full (IJSDR 2026 RF-DETR + PaddleOCR on FloorPlanCAD; WSCG/CSRN 2026 raster-to-vector) report no text-recognition accuracy; the first only confirms PaddleOCR is the default reader people reach for. Gap 1-3 of section 4 stand.
- Blocked, not circumvented: academic.oup.com (JCDE 2025 P&ID symbol+text paper, metadata only).
- Fine-tuning path for row 3 exists in the repo (V, config read): `configs/rec/PP-OCRv6/PP-OCRv6_{tiny,small,medium}_rec.yml`, defaults 100 epochs, 3x48x320 input, max text length 25, lr 5e-4; swap the dictionary for the closed vocabulary and fill `pretrained_model`. Hours to a first number remain an estimate (E): minutes on a GPU for a few thousand short crops, not measured.
- DeepSeek-OCR row 4, evidence from its tracker (V, anecdotal): issue #223 (open, unanswered) raises the PyMuPDF AGPL question for the repo; issue #210: a user asking the model for the box of each number got None. Together with #310 (bbox scale) and #151 (loops), "locate a vocabulary code" stays **maybe, low**: run only on PNG crops, never the PDF scripts.
- PaddleOCR-VL-1.5 spotting output (V, issue #17637): raw `text` followed by eight `<|LOC_n|>` tokens (four corners), by design (paper section 2.2.2: eight location tokens after the text; that user also saw no wrapper tokens): budget a small parser and a format test; no public issue on fine-tuning VL-1.5, so row 2 stays an inference-only second reader.
- docTR (V, README): Apache-2.0 code, recognisers CRNN/SAR/MASTER/ViTSTR/PARSeq selectable by name, so row 1's reader can be swapped without new code; pretrained weights' licence is not stated in the README (check the model cards before shipping).
- Hybrid-VL numbers re-checked (V): Donut hallucination rate 10.8% (Florence-2 21.6%); a generative reader invents text about one time in nine, which is why closed-vocabulary matching must sit after any VLM/Donut reader.
- SPaTS Table 1 re-checked (V): on ICDAR 2015 the best document VLMs reach only about 50 detection F (PaddleOCR-VL-1.5 49.8, HunyuanOCR 52.9), so on small incidental text the loss is in finding labels, which supports the detector-first design of row 1.
- Detector choice for row 1 (V, gh api): CRAFT's official repo ships inference only (README: training code not released), so 'CRAFT-style' means training DBNet in docTR/PaddleOCR (both with training code, Apache-2.0) or EasyOCR's trainer, not the CRAFT repo; the 2026 EC3 paper's CRAFT was fine-tuned with its own code that I could not see.
- Detector fine-tune config for row 3 (V config only, 2026-11-14): PP-OCRv6_small_det.yml defaults 500 epochs, RandomCrop 640x640, resize 0.1-2x, batch 8 per card, MakeShrinkMap min_text_size 8. Op code read (ppocr/data/imaug/make_shrink_map.py): a text box whose shorter side is under `min_text_size` (8 px, in the augmented training image) is masked out as an ignore region, never learned. Our 5-12 px labels sit on that edge: upscale tiles about 2x before training, or lower the setting.
- EasyOCR default drops small boxes (V, code): readtext/detect default `min_size=20` removes every box whose longer side is 20 px or less, so short labels vanish silently; set min_size low and mag_ratio 2 or upscale first. It also has an `allowlist` character filter. Same silent-drop class as PaddleOCR's 8 px training mask.
- docTR DB post-processing (V, code): minimum kept box 2 px, box_thresh 0.1: no EasyOCR-style hidden 20 px cut-off. Tile large drawings before it, since the detector input is resized.
- Gap kept open (V, PaddleOCR text-recognition doc): the fine-tune recipe is documented, but neither training hours nor a minimum sample count is given anywhere I read; treat 'hours to first number' as E until we run one.
- Synthetic crops for the closed vocabulary (V, gh api + README): Belval/TextRecognitionDataGenerator is MIT with `--dict` (our abbreviation list), `--font_dir`, blur/skew/background options, last push 2024-07; SynthText (Apache-2.0) is the scene-text alternative. No paper I opened measures how much synthetic data replaces real label crops on drawings, so synthetic-only is untested (E).
- Clarification (V, arXiv 2606.15886 tables 3 and 5): the TESTR 30.6 -> 80.4 F1 and mAP50 68.3 figures measure text-region detection (class-agnostic) and single-character classification on 45 test diagrams after fine-tuning on 100; they are not transcription accuracy. They support 'a fine-tuned DETR finds short marks that scene-text models miss', not a reading number. Row 5 wording in the top-5 table should be read that way.
- MapText'25 Task 3 table re-read (V): char accuracy on detected words 92.9% (fine-tuned TESTR baseline), 94.0% (best), 83.7% (PaddleOCR entry); the PaddleOCR entry's problem is recall (40.0), not reading.
- PatentOCR tables 7-8 re-read (V): whole-sheet EasyOCR (untrained) gets 86.47% exact vs 89.76% with a trained YOLOv8m in front, while PaddleOCR gains 62.67% to 77.21%: the detector matters most for the reader that misses text (PaddleOCR read 2,915 characters against EasyOCR's 6,202 on the same sheets). Fits the MapText finding that PaddleOCR's problem is recall.
- Code search (V, gh search repos): no mature open code for floor-plan text reading; every hit was a 0-3 star hobby repo, so row 1 is built from docTR/PaddleOCR, not from a floor-plan repo.
- Hugging Face model and dataset searches (V, API listings only): no floor-plan text-reading model and no dataset with room-label transcriptions turned up, confirming section 4's first gap from a second angle.
- Forward citation walk of the 2022 floor-plan text paper (V via Semantic Scholar, 9 citing works): none concerns reading text from plans; its line of work has no successor in the literature I can reach, which is itself a finding (gap 1 stands).
- Forward walk of PaddleOCR-VL-1.5 (V via Semantic Scholar, 68 citers): the only spotting/grounding follow-ups are ArabGeoText (maps) and PreciseDoc 2606.24118 (document element grounding, synthetic word-level coordinates, no drawing results, no weights link seen): same verdict as row 4, no number for tiny labels on plans.
- **Row 4 downgraded (V, Q-Mask arXiv 2604.00161, Table 1):** on TABench, a text-to-region ("locate this string") test on document pages, DeepSeek OCR2 scores F1 11.66 against 72.8 for Qwen3.5-397B and 62.6 for Gemini 3.0 Pro; GPT 5.2 scores 0.64. This is the capability row 4 relies on, measured on documents, not drawings. Verdict for row 4 is now **maybe, low (probably skip)**; the README prompt is not evidence of working localisation.
- **Faithful reading (V abstract, arXiv 2607.21617):** VLMs rewrite imperfect text into plausible words; short words of 4-6 characters are rewritten up to 10% of the time and traditional OCR degrades under 0.8 WER points against up to 6.9 for general VLMs. Argues for the detector + small reader design (row 1, 3) and for exact-match decoding after any VLM reader (row 2).
- SPaTS (V): no released code or weights seen, trained on 8 A6000 GPUs with SFT + GRPO; its 73.4 vs 45.1 is evidence that fine-tuning beats zero-shot VLMs on small text, not a tool we can use.
- Permissive detector swaps for the AGPL-YOLO patterns (V, gh api + README): RF-DETR Nano-Large (Apache-2.0; its Atto/Femto/Pico/XL sizes are PML 1.0, avoid), D-FINE and RT-DETR (Apache-2.0), or docTR/PaddleOCR's own DB detectors for plain text boxes. None has a published small-text number on plans; DETR-family fine-tunes are slower to converge than DB for tiny objects (E).
- 0/180 text-line orientation (V docs, vendor numbers R): PP-LCNet_x0_25_textline_ori 98.85% / x1_0 99.42% top-1, 1-6.5 MB, on the vendor's data, not drawings. It handles upside-down crops only; vertical (90/270) labels on plans need the detector's oriented boxes or rotating crops both ways and keeping the higher-confidence read.
- Adjacent field, short codes on small crops (R, abstract only, SSRN preprint doi 10.2139/ssrn.6661500): detector (RT-DETR-S, Apache-2.0 family) then super-resolution and orientation fix then OCR; a closed-set recogniser (Abinet 95.5% on oriented crops) beat a large VLM (RolmOCR 61-74%) on serial numbers. Same shape as row 1 and same message: a small trained reader beats a VLM on short codes. Not peer reviewed, paywalled sibling (Pattern Recognition 2026, text super-resolution) title only.
- Idea (R, abstract only, AHFE 2025, doi 10.54941/ahfe1007033): OCR token confidence as a drawing-quality gate that sends low-confidence pages to review: the same trick fits our 'refuse what was not read' rule, with PaddleOCR/docTR per-box confidences instead of Tesseract's; no accuracy numbers seen.
- PaddleOCR knobs for large drawings (V, code): text_det_limit_side_len + text_det_limit_type bound the detector input; text_det_thresh, text_det_box_thresh, text_det_unclip_ratio tune box finding; set them per call instead of patching YAML, and tile first.
- Recipe detail for row 1 (V, EC3 2026): overlapping tiles plus print-scan-style augmentation (the paper does not say which operations) are what the only published floor-plan reader fine-tune used; no training hours, GPU or resolution reported. Side idea for other scopes: it uses OCR boxes to erase dimension lines and leaders before wall extraction.
- DeepSeek-OCR 2 (V, HF API + repo): Apache-2.0 weights and repo, same PyMuPDF (AGPL) requirement and old transformers pin as v1; it is the model TABench scored at text-to-region F1 11.66, so the row 4 caution applies to v1 by inference only (E).
- The 2024 Automation in Construction follow-up (doi 10.1016/j.autcon.2023.105156) stays title-only: paywalled, no abstract in Crossref. Any number I attribute to it elsewhere in this report is S, not V.
- Fine-tune recipe that reached 96.3% recognition on short drawing annotations (V, Frontiers 2026): about 5,000 training crops, a pretrained PaddleOCR-family start, PPOCRLabel for labelling, augmentation = rotation +-5 deg, scale 0.8-1.2x, Gaussian blur, synthetic line noise (the last one mimics drawing lines crossing text), 800 epochs on 8 GPUs. Its split by design institute is the leak-safe protocol analogue of our dev/eval split by plan source; the data is one firm's drawings.
- Rules that bind rows 1 and 3 (V, repo records 0003 and 0006): own fine-tuning on CubiCasa5K dev-split images is allowed (eval split and its SVGs stay out, weights stay local); PyMuPDF and Ultralytics YOLO are named as out under 0006, which is why row 4's requirements.txt and every YOLO pattern need a swap. The export carries room boxes with labels, so text boxes still have to come from the SVG text elements or from FP-TXT (dev-split overlap check first).
- Independent reproduction of Hybrid-VL (V, arXiv 2608.29268, Table 5): with only 10/10 training epochs and a Florence-2-base reader it localised 48 of 78 references but read none usably (NED 1.0), on a different drawing type, 26 validation pages, one run. It does not refute the original F1 94 (400/30 epochs, mechanical drawings) but shows that the detector-then-reader recipe needs the full schedule and a reader that actually transcribes; localisation was its best part (F1 0.6704).
- Follow-up of Hybrid-VL (V abstract, arXiv 2510.21862): the same detector + Donut recipe reads numbers well (F1 0.963) but alphabetical text much worse (0.672). Our labels are letters, so the 0.96 style number does not transfer, 0.67 is the more honest prior for a fine-tuned generative reader on letter text (different drawing type, title blocks and notes, not short room codes).
- docTR training scripts exist (V, file list): references/detection and references/recognition train.py.
