# lit-ocr-c: practical fit for reading short labels (scope L5, angle c)

Read 2026-11-14. Worker lit-ocr-c, read-only. Verified = I opened the page and read it; reported = the authors' own
claim on a page I opened; estimate = mine. Reading log with one line per source: `lit-ocr-c-log.md`.
Status: see the end of the file.

## 0. The answer in six lines

1. The measured baseline (RapidOCR with PP-OCR mobile, 23-81% exact per room type) is now two generations old. PP-OCRv6
   (released 2026-06-11, Apache-2.0 code and weights, 50 languages, Finnish and Swedish diacritics in the dictionary) is a
   drop-in replacement through PaddleOCR 3.7 and RapidOCR 3.9+. It is the cheapest first experiment. Its numbers are the
   authors' own, on their own benchmark, none of it drawings.
2. No paper or model card gives accuracy for 2-4 character labels at 10 px. Not found in 15+ sources. Our own 40-image
   measurement (section 2 of the context file) is still the best number there is. Expect the same ceiling from any
   off-the-shelf reader: glyphs under about 6 px are not recoverable, and 10 px is borderline.
3. Cheapest fix, in order: (a) PP-OCRv6 swap, (b) read every label crop at four orientations and take the
   dictionary-closest answer, (c) fine-tune the recogniser on synthetic crops of our ~25 abbreviations with the
   output dictionary cut to those letters, (d) only then a VLM as second reader on crops the first two disagree on.
4. A specific break found in the source of the engine we already use: RapidOCR turns a text crop upright only when
   height/width >= 1.5. A 2-letter label such as "MH" set at 90 degrees has an aspect near 1.0-1.3, stays sideways, and
   the 0/180 classifier cannot fix it. Rotated sheets are one in three, so this matters (verified in source; the effect
   on our images is an inference, not measured).
5. Floor-plan-like evidence for "detector then crop reader": ArabGeoText (Nov 2026, maps with 18 px median text of which only 4% is under 12 px, 79%
   rotated; our labels are smaller) gets end-to-end 61.7 with a detector plus a VLM reading crops zero-shot, 74.4 after LoRA, against 12.8
   when the VLM spots directly on the tile. Spotters pretrained on scene text drop to F1 24-31 on diagrams until
   fine-tuned (astronomical diagrams, ICDAR 2026).
6. Out for licence: DeepSolo and everything built on it (TiCLS, PaLeTTe's baselines) is non-commercial, YOLO26 is
   AGPL-class. Out for fit: PaLeTTe trains on 4 x A100.
7. Added in later rounds (details in Rounds 4-13 before section 7): my own quick runs on clean renders show rotated codes failing far more
   often than upright ones, and a four-orientation vote on tight crops read 192 of 192 against 83 of 192 for a single read (Round 11, clean renders only); a page-like test shows the default detector already finds 94% of upright 8-12 px codes (Round 12) but only 34-58% when the whole sheet is rotated (Round 13); RapidOCR shrinks any page above 2000 px on the long side (not our
   855 px sheets, but high-DPI PDF renders); the v6 ONNX non-ASCII bug reported in PaddleOCR issue 18364 did not reproduce on RapidOCR's
   files; a 2026 floor-plan paper fine-tuned CRAFT + CRNN on 1,000 plans for about 90% on dimension numbers; a digit-per-class detector beat
   CRNN by 8 points in meter reading (closed-class alternative to character decoding).

## 1. Top 5, ranked

Each line: method, verdict, source (URL, date read), evidence status. Leakage flag: none of these OCR checkpoints is
known to use CubiCasa5K or a repackage of it; the training data of PP-OCR models is not published in detail, so the
flag is "no known, not verifiable".

1. **PP-OCRv6 (det + rec) via PaddleOCR 3.7 or RapidOCR 3.9+. Try.**
   Medium 34.5M, small 7.7M, tiny 1.5M parameters for detector plus recogniser together per the release notes; the recogniser alone is 19M (medium, model card) and 1.1-19M across tiers (2609.20064). Authors'
   in-house benchmark: rec 83.2 weighted average (medium) vs 78.1 (PP-OCRv5 server) vs 73.7 (v5 mobile, the model we
   measured); Latin-script benchmark 88.0 (v6 medium) vs 81.4 (latin v5 mobile); detection Hmean stays 76.3 at 0.35x
   and 87.9 at 2.83x scale (v5 server 74.7 and 67.3). Reported, authors' own sets, no drawings, no short-code test. Training data is an unreleased in-house set (synthetic plus
   real industrial text; no floor plans mentioned), so the leakage flag is "no known". The authors also report a faithfulness score of 93.2%
   against 80.6% for Qwen3-VL-235B (VLMs "correct" text from language priors), which matters for counts that must not be invented.
   If we ever feed high-resolution renders: RapidOCR caps the long side at 2000 px by default (Round 8; not active on our current ~855 px median sheets).
   Fills `rooms[].raw_label` (and later door/window size codes if the "x" survives, which v5 did not).
   Sources: https://arxiv.org/html/2606.13108 (2026-11-14, read); https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html
   (2026-11-14); HF cards PaddlePaddle/PP-OCRv6_medium_rec and _small_rec (apache-2.0, 2026-11-14); release notes
   https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.7.0 (2026-11-14).
2. **Fine-tune a PP-OCRv6 small/tiny recogniser on synthetic closed-vocabulary label crops, output dictionary cut to
   the letters we need. Try.** A 2026 study adapting PP-OCRv6 (arXiv 2609.20064, read) fine-tunes it from 20-240 lines in
   300 optimiser steps and finds heterogeneous pretraining beats from-scratch, so a few hundred real crops plus synthetic ones
   is a realistic size on one 12 GB card (estimate; they used A40s for full training). PaddleOCR documents the recipe (`tools/train.py -c configs/rec/... -o
   Global.pretrained_model=...`, text-line dataset). Needs crops: we can render the ~25 abbreviations (list in section 5)
   in CAD-like fonts, 6-14 px high, blur, JPEG, line-art clutter, four rotations, with no real data. Real crops from our
   OCR boxes on dev images, labelled by the known room type, are the second source. Source:
   https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html (2026-11-14). The size of the gain is
   not published anywhere. Wolf and Fink (arXiv 2003.01989, read) find synthetic-only training modest and fix it with
   lexicon-based pseudo-labels on real unlabeled word images chosen by confidence; a rough lexicon is enough. Our
   version (my idea, untested): the dev answers already say how many rooms of each type an image has, so a crop read as
   "MH" on an image whose bedroom count is 0 can be dropped and the confident rest kept as pseudo-labels.
3. **Four-orientation crop voting with dictionary decoding. Try (it is our own design, supported by the RapidOCR source).**
   Detect text polygons (DB, rotation-free), cut each crop upright by the polygon, then read it at 0, 90, 180, 270 and
   keep the answer closest to the closed vocabulary. Replaces the page-level 0/180 vote and fixes the aspect rule
   above. Source: https://raw.githubusercontent.com/RapidAI/RapidOCR/main/python/rapidocr/utils/process_img.py
   (2026-11-14, read, `get_rotate_crop_image` lines 72-103).
4. **Detector + VLM crop reader as second reader on disagreements (GOT-OCR2 with a given box, PaddleOCR-VL-1.5 or 1.6).
   Maybe.** ArabGeoText, Table IV, Test-I OSM: direct VLM 12.8 end-to-end H, detector + zero-shot reader 61.7,
   detector + LoRA reader 74.4. The detector there is YOLO26 (AGPL-class), the reader Qwen3.5-4B; the lesson transfers,
   the parts do not. GOT-OCR2_0 is Apache-2.0 (card) and takes a box; PaddleOCR-VL-1.5 returns 4-point boxes in reading
   order but its spotting numbers are on the authors' 9-domain set with no drawings. Sources: https://arxiv.org/html/2611.03339
   (2026-11-14, read), https://arxiv.org/html/2601.21957 (2026-11-14, read), HF cards (apache-2.0).
5. **TESTR fine-tune as an end-to-end label spotter. Maybe, probably skip for the deadline.** Apache-2.0 code (last
   push 2023-01, detectron2 stack). On line-art diagrams, scene-text pretrained TESTR gets F1 30.6 zero-shot and 80.4
   fine-tuned (own annotations, polygons); without pretraining 47.4. Needs text boxes we do not have. Source:
   https://arxiv.org/html/2606.15886 (2026-11-14, read).

## 2. Full table

Columns: method | field | year, venue | code licence (file) | weights licence (card) | leakage | metric and benchmark
(reported unless marked) | input and memory | hours to first number (estimate) | JSON field | verdict.
"-" means the page says nothing. Memory and hours are my estimates unless a source is named.

| Method | Field | Year, venue | Code | Weights | Leak | Reported result | Input / GPU | Est. hours | Fills | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PP-OCRv6 medium/small/tiny | OCR, general | 2026-06, PaddleOCR 3.7; report arXiv 2606.13108 | Apache-2.0 (PaddleOCR LICENSE via gh api) | apache-2.0 (HF cards) | no known | rec 83.2/81.3/73.5 weighted avg, authors' set; Latin 88.0/84.0/63.8; det Hmean 86.2/84.1/80.6 | det up to 2048 px, 106.9 ms GPU for medium at 2048 (report); CPU ONNX 654 ms small, 317 ms tiny at 2048 | 1-2 | rooms[].raw_label | try |
| PP-OCRv5 latin mobile rec | OCR | 2025-06 | Apache-2.0 | apache-2.0 | no known | 84.7 on authors' 3,111-image Latin set; Finnish, Swedish listed | rec input 3x48x320 (v6 config read) | 0 (superseded) | raw_label | skip, v6 supersedes |
| RapidOCR 3.10 (ONNX, torch) | OCR runtime | 2026-10 | Apache-2.0 | models as upstream | - | adds PP-OCRv6 backends from 3.9.1 (release notes) | CPU | 1 | raw_label | try (our current runtime) |
| Fine-tuned v6 rec, closed vocab | OCR, own | - | Apache-2.0 | ours | no | not published anywhere | crops 48x<=320, small model fits 12 GB easily | 3-4 | raw_label | try |
| PaddleOCR-VL-1.5 / 1.6 (0.9B) | VLM OCR, spotting | 2026-01, arXiv 2601.21957 | code in the Apache-2.0 PaddleOCR repo (gh api) | apache-2.0 (cards 1.5 and 1.6) | no known | spotting avg 0.8621 on authors' 9-domain set; OmniDocBench v1.5 94.5 | NaViT dynamic res; GPU, A100 throughput only | 3 | raw_label + boxes | maybe |
| dots.ocr 1.7B | VLM layout OCR | 2025-07 | MIT (gh) | mit (card) | no known | layout-element boxes with text, reading order; OmniDocBench SOTA claim (reported) | GPU | 3 | raw_label | skip: element-level, not word-level |
| DeepSeek-OCR | VLM OCR | 2025 | MIT (gh) | mit (card) | no known | grounding prompt; no small-text number | base 1024, 640 crops | 3 | raw_label | skip |
| GOT-OCR2.0 | VLM OCR | 2024 | no LICENSE file in repo (gh api 404); README badges say code Apache-2.0 and data CC BY-NC 4.0 (badge only) | apache-2.0 (card) | no known | fine-grained OCR with a box; multi-crop | 0.7B | 2 | raw_label from our boxes | maybe, as crop reader; code licence unclear |
| GLM-OCR 0.9B | VLM OCR | 2026 | Apache-2.0 (gh) | mit (card) | no known | OmniDocBench V1.5 94.62 (own model card, read 2026-11-14; MIT, pipeline adds PP-DocLayoutV3 Apache-2.0; page level, no word boxes) | GPU | - | - | not evaluated |
| LightOnOCR-2-1B | VLM OCR | 2026-01 | Apache-2.0 (gh) | apache-2.0 (card, read 2026-11-14) | no known | page level; its bbox variants box embedded images only, not text | GPU | - | - | not evaluated |
| docTR | OCR | v1.1.0 2026-08 | Apache-2.0 | the one HF card I read (Felix92/doctr-torch-parseq-multilingual-v1, community-hosted) says apache-2.0; the default maintainer-hosted weights were not checked; shipped recognisers use `VOCABS["french"]` (no a/o with diacritics), so Finnish needs a fine-tune | no known | `VOCABS["finnish"] = english + äöÄÖ` exists; DB + CRNN/PARSeq/ViTSTR | PyTorch | 2 | raw_label | maybe, as a second opinion |
| EasyOCR | OCR | - | Apache-2.0 | - | no known | `fi` not in latin_lang_list; `sv` is | - | - | - | skip |
| Tesseract + tessdata_fast fin | OCR | - | Apache-2.0 | Apache-2.0 (tessdata_fast) | no | wants ~30 px capitals (earlier report) | CPU | 1 | - | skip for labels |
| PARSeq | scene text recogniser | 2022 ECCV | Apache-2.0 (gh) | apache-2.0 (parseq-tiny card); trained on MJSynth, SynthText and real sets (ArT, LSVT, MLT19, RCTW17, ReCTS, Uber-Text, COCO-Text, TextOCR) whose own terms I did not read | no known | no resolution study found; default charset is 94 ASCII, so a/o with diacritics need a new charset and fine-tune | 32x128 | 3 | raw_label | maybe (fine-tune alternative) |
| SVTRv2 (OpenOCR) | scene text recogniser, CTC | 2025 (ICCV), arXiv 2411.15858 | Apache-2.0 (OpenOCR, gh) | not read | no known | Union14M, same real training data: Multi-Oriented 89.0, Contextless 86.1 (CRNN 13.0 / 62.3; PARSeq 88.8 / 83.4); tiny 5.1 M params | variable-width, multi-size resizing | 3 | raw_label | maybe (the design PP-OCR already uses); shows what fixed-size resizing costs on rotated crops |
| Synthetic-drawing text detector (Schlagenhauf) | technical drawings | 2022, Procedia CIRP / arXiv 2205.02659 | MIT (gh) | - | no | detection rate 81.87% vs 4.67% (9 real drawings) on 171 objects | 1200-1500 px images | 4 (rewrite) | boxes | idea only |
| TESTR | scene text spotting | 2022 | Apache-2.0 (LICENSE read) | - | no | diagram F1 80.4 fine-tuned, 30.6 zero-shot | detectron2 | 6+ | boxes + text | maybe/skip |
| DeepSolo, DeepSolo++, TiCLS | scene text spotting | 2023-2026 | non-commercial (LICENSE read: AdelaiDet NC) | - | no | diagram F1 80.0 fine-tuned | - | - | - | skip: licence |
| PaLeTTe + SynthMap+ | maps | 2025-06, arXiv 2506.15010 | docs repo only | - | no | pretrained E2E no-lexicon 70.27 (Grinnell-31) / 69.82 (Rumsey-309) vs TESTR 68.05 / 65.99; rotation 60-90 deg recall 55.2 vs TESTR 53.4 (Rumsey) | 4 x A100, 400k it | n/a | - | skip: compute, code |
| MapText 2025 winners (MapText Strong, Self-Sequencer, CREPE+Bezier) | maps | 2025-09 ICDAR | not found | not found | no | Task 3 HMean 91.1/90.3/84.9 on Rumsey | - | - | - | idea only |
| eDOCr2 | mechanical drawings | 2025 | MIT (gh) | - | no | not read beyond licence | - | - | - | not evaluated |
| ICPR 2026 LRLPR competition winner | licence plates | 2026, ICPR | not read | not read | no | exact-match 82.13% on real LR plates (16x48 inputs) | - | - | - | idea only |
| RISTER | scene text, rotation invariant | 2026-08, arXiv 2608.10684 | no link found | - | no | +4.0 over second best on a multi-oriented set | - | - | raw_label | idea only |
| LP-LLM | licence plates | 2026-01, arXiv 2601.09116 | - | - | no | CRNN 42.5% exact on blurred plates; slot queries | Qwen3-VL + LoRA | - | - | idea only |
| Qwen3.5-0.8B / 4B or Qwen3-VL-2B / 4B Instruct (LoRA crop reader) | VLM | 2025-11, arXiv 2511.21631 (cited, not opened) | - | apache-2.0 (cards read; Qwen2.5-VL-3B is `qwen-research`, not usable) | no known | ArabGeoText: adapted 4B reader on detector crops, exact 84.3 / CER 4.6 (Riyadh OSM, own data) | LoRA, 5 epochs, crops bicubic-upscaled to >=48 px height; reader 87 ms (4B) or 49.5 ms (0.8B) per crop on one RTX A6000 (ArabGeoText Table VII); 12-16 GB with LoRA is my estimate | 4-6 | raw_label | maybe, second reader only |
| MangaLMM (Qwen2.5-VL-7B fine-tuned) | comics, positional OCR | 2025, arXiv 2505.20298 | - | 7B apache-2.0; result weights not checked | no | in-page spotting Hmean 71.5 after 1 epoch; zero-shot 0.0 for GPT-4o, Gemini 2.5 Flash, Claude Sonnet 4.5 | 4 x A100, about 1 h | n/a on 12 GB | boxes + text | idea only: zero-shot VLM spotting returns nothing usable |
| YOLO26-seg text locator | maps | 2026 | AGPL-class (earlier ruling) | - | - | used by ArabGeoText | - | - | - | out |

## 3. Transfer notes (other fields)

- **Historical maps (MapText 2024-2025, PaLeTTe, ArabGeoText).** Object role: a place name; ours: a room code. Same
  shape: short strings, any angle, over line work. Verified results: spotters reach HMean 91 on Rumsey (long names,
  18 px+ text). What breaks on ours: codes are 1-3 letters with no language context; map spotters lean on word-level
  language priors (TiCLS says so outright); the strong systems are DETR spotters needing boxes we lack and 4 x A100
  (PaLeTTe) or non-commercial code (DeepSolo). A PaddleOCR entry with enhancement scored only 59.5 HMean, recall 40.0,
  in the same competition: off-the-shelf detection is the weak part, not recognition. Takeaway: fix detection of tiny
  text (upscale, tile) before swapping recognisers. Transfer type: idea only.
- **Diagram text regions (astronomical diagrams, ICDAR 2026).** Line-art with sparse scattered text and single
  characters annotated as a class. Verified: scene pretraining without fine-tuning is poor (F1 30.6, 24.3); fine-tune to
  about 80; synthetic diagram-like pretraining almost matches scene-text pretraining (79.7 vs 80.4). What breaks: their
  boxes are human-annotated; ours would come from OCR output. Transfer type: needs fine-tuning.
- **Detector then crop reader (ArabGeoText, Roboflow P&ID tutorial pattern).** Verified numbers above. What breaks:
  the detector (YOLO26) is AGPL-class; our label boxes do not exist yet. Transfer type: the idea works as is.
- **Synthetic technical drawings (Schlagenhauf et al., arXiv 2205.02659, Procedia CIRP 2022, read).** Object role: dimension and
  tolerance text on mechanical drawings; ours: room codes. Verified numbers on 171 objects from 9 real drawings: a
  detector trained only on generated drawings finds 81.87% with 79.33% correct recognition (1 minus CER); the same detector
  trained on the 9 real drawings finds 4.67% (47.91%); out-of-the-box Keras-OCR finds 77.19% (46.75%). Code MIT
  (github 2Obe/Text-Detection-on-Technical-Drawings, last push 2022-04). What breaks: a tiny test set, YOLO detector of
  that year, digits not letters, large 45x25 px dimension text; one author group. Transfer type: the idea works as is (a
  domain generator beats a few real samples); the code would need to be rewritten for floor-plan fonts.
- **Comics (MangaLMM, 2025).** Object role: speech-balloon and sound-effect text; ours: room code. Verified: asked for
  text with positions, frontier VLMs score Hmean 0.0 zero-shot and Qwen2.5-VL-7B 0.9; one epoch of fine-tuning on
  annotated pages reaches 71.5. What breaks: needs annotated text boxes and 4 x A100; our images have 1-4 letter codes
  with no sentence context. Lesson: never rely on a VLM for positions without fine-tuning; use it on crops.
  Transfer type: needs fine-tuning, probably not in time.
- **Meter reading (water-meter YOLOv8 + PP-OCRv4, ETASR 2026, read).** Object role: the digit window of a meter; ours: a label.
  Verified: detector then PP-OCR reader fine-tuned on only 1,000 hard (non-ideal) images beat the same reader trained on all 3,250:
  90.90% exact, CER 0.0151 on 55 benchmark images, 0.5 s per image (tiny test set; same authors tune and test). Its related-work
  line cites 96.92% on 8,044 meters for another YOLOv8 + PaddleOCR system (cited, not read). Lesson: fine-tune the reader on
  the hard crops, not on everything. For us a "detector class per abbreviation" would mean ~25 classes needing text boxes (none
  in our export); the paper does not test digits-as-classes (see Round 7). What breaks: digits only,
  large clean windows. Transfer type: needs fine-tuning.
- **Recoverability maps (licence plates, arXiv 2604.23814, read in full 2026-11-14).** The axes in the paper are oblique viewing angles (a 2-D grid sampled with Sobol sequences, boundary-AUC plus a reliability score for interior holes, validated on CCPD and RodoSol real plates by re-warping real crops); the sweep over text height we need is our adaptation, not theirs. Method: sweep degradation parameters on
  synthetic images, map where recognition is reliable, report boundary area and reliability. This is the way to get the
  missing "accuracy at 10 px" number cheaply: render our 25 codes at 5-16 px, four rotations, blur and JPEG levels, run each
  engine, and plot exact match. Zero real data needed; only compute is CPU. Idea, free to run.
- **Licence plates (ICPR 2026 low-resolution competition, arXiv 2604.22506, read; LP-LLM 2601.09116, read).** Object role:
  a closed-format string at 16x48 px; ours: a 1-4 letter code at 10 px. Verified: on real low-resolution plates the
  winner reaches 82.13% exact match (mean of 99 teams 61.3%; the organisers write that single-frame methods used to struggle
  to exceed 50-60%); the winner trains super-resolution and OCR jointly with a teacher fed the high-resolution image.
  The competition also scores abstention (a Confidence Gap between right and wrong answers), which matches our need to
  abstain. What breaks: plate tracks give five frames per vehicle and paired HR images; we have one image and no HR twin
  (a synthetic HR twin of our own codes could play that part, untested). LP-LLM (slot queries on Qwen3-VL, CRNN 42.5% on
  blurred Chinese plates) is weaker evidence. Transfer type: idea only.
- **Rotation-invariant recognition (RISTER, arXiv 2608.10684, abstract and introduction read).** Targets exactly the
  0/90/180/270 crops that tight boxes produce; +4.0 points over the second best on a general multi-oriented set. No code
  found. Idea only; our four-orientation voting is the cheap stand-in.
- **Synthetic text engines (UnionST, arXiv 2602.06450, abstract read).** Claims synthetic data can match real data in some
  settings and reach competitive scores with 9% of real labels. The repository has no licence file (GitHub shows none), so
  use as idea only; our own renderer with CAD fonts is a few dozen lines.
- **Historic Finnish and Swedish handwriting (lower priority, legacy archives).** Verified on the model card (read 2026-11-14):
  the Swedish National Archives' TrOCR-base line recogniser (`Riksarkivet/trocr-base-handwritten-hist-swe-2`, apache-2.0; HTRflow
  runtime Apache-2.0) reports in-domain CER 3.68% / WER 16.07% on 7,761 held-out lines of National Archives of Finland court records
  (147k training lines) and 0.75-4.6% CER across other archives. Line-level, 1600-1900 hands, no floor plans; useful only if the
  legacy-archive route needs handwriting. The 2025 church-record migration paper (arXiv, via a search summary) is not opened.
- **AEC drawing layout (arXiv 2607.18997, read; scopes L2/L7).** Layout regions, not text: RF-DETR mAP50 0.949, Qwen3-VL-8B F1 0.911
  at about 6 s per image; document-layout models pretrained on general documents lose accuracy on drawings ("domain
  interference"). Relevant here only as a warning: PP-OCR family models are also document-trained, so expect a domain gap.
- **Synthetic generators for drawing text (code, not papers).** `Gio99c/synthetic_ocr` (README read; no licence file, 1 star, last
  push 2025-02) renders alphanumeric tags with rotation, underline, clutter backgrounds and icons at about 2,000 samples per
  minute per core (author claim); a second generator emits PaddleOCR-format manifests with scanner degradation (not opened
  beyond its listing; licence not read). Design references for E2; our own renderer is simpler.
- **Sheet music (Sheet Music Benchmark, arXiv 2506.10488, abstract read; search hits for two other OMR papers not opened).**
  Object role: note head, accidental; ours: a window cell or a letter. The benchmark scores per-element errors (OMR-NED) rather
  than whole-page match, which is the habit we need for counts. Nothing on 10 px symbols or exact counts. Belongs to scopes
  L2 and L3; one line, not dug.
- **P&ID (DSAA 2025, arXiv 2411.13929v3).** Verified: tags read by CRAFT + EasyOCR only to mask text, no OCR accuracy
  reported; patches of 2000 px. Nothing to transfer for reading. Belongs to scopes L2 and L11.
- **Engineering drawings (arXiv 2510.21862 read; 2602.18296 abstract and introduction only).** Mechanical drawings; the first
  uses YOLOv11-obb (AGPL-class) for oriented annotation boxes and fine-tuned VLM readers (alphabetical reader F1 0.672,
  numerical 0.963); the second maps drawing annotations to 3D CAD features. No numbers on short rotated codes. Not dug.

## 4. Expected accuracy on 2-4 character labels at 10 px, and the cheapest fix

- **Published number: none.** Searched PARSeq, TrOCR, PP-OCR, docTR, MapText, TextZoom-style papers: no source reports
  recognition accuracy by text height for printed short codes. Do not quote one.
- **Lexicon evidence found (verified in a 2026 survey, arXiv 2611.04874, Table V):** scene-text spotting F1 rises when a
  lexicon is applied: Total-Text TESTR 73.3 to 83.9, DeepSolo 83.6 to 89.6, TiCLS 84.6 to 90.4; CTW1500 TiCLS 66.2 to 88.1.
  Those lexicons hold every word of the test set; ours is ~25 words, so the correction power is higher, but it cannot
  recover a missed detection. No lexicon result on drawings exists.
- **Our measured baseline (earlier reports, not repeated):** raw RapidOCR exact per room type 23-81%; short codes (K,
  MH, S) at 5-10 px are the misses; 2x Lanczos helped some types and hurt kitchens; Swiss plates at full resolution
  93% exact, half resolution 16/30; below about 6 px glyphs are lost even after upscaling.
- **Estimate (mine, marked):** with v6 and four-orientation voting and dictionary decoding, expect the gain to come
  from rotated sheets and diacritics, not from smaller glyphs; a guess is 5-15 points on bedroom and kitchen label counts,
  nothing on glyphs under 6 px. Decide by running the 40-image test again, not by this estimate.
- **Cheapest fix, in order of cost:** (1) swap models to PP-OCRv6, same tiling, same dictionary decode; (2) crop-level
  four-orientation voting; (3) fine-tune the recogniser on synthetic crops with the dictionary restricted to the label
  letters; (4) VLM second reader on disagreements; (5) abstain, which is already what the pipeline does for room types.
- **Two facts from the v6 config (verified, inference.yml read 2026-11-14):** the recogniser resizes every crop to 48 px height
  (input 3x48x320, CTC decode) and its dictionary has about 18.7k entries including the Finnish letters. So (a) a 10 px label is
  stretched 4.8x inside the model whatever we do outside it, which probably (inference, not measured) is why external 2x upscaling helps the detector more than
  the reader; (b) the CTC output can be masked at decode time to capitals, digits and a few diacritics with no training, a
  zero-cost version of closed-vocabulary decoding (my suggestion, not tested).
- **Rotation and no-context evidence (verified, SVTRv2 paper Table 3, one training set for all):** on Union14M's Multi-Oriented
  subset a CRNN-style fixed-size reader gets 13.0%, ABINet 69.0%, PARSeq 88.8%, SVTRv2-B 89.0%; on Contextless (random strings,
  no language prior, our situation) ABINet 74.7%, PARSeq 83.4%, SVTRv2-B 86.1%. The reader with the strongest language model (ABINet) is 11 points
  behind the best on random strings; readers that squash rotated crops into a fixed box collapse. None of these crops is a 10 px, 2-letter label.
- **Clean-render floor (blog, reported, not peer reviewed):** a controlled test of macOS, browser and Tesseract readers on
  clean renders finds a cliff between 6 and 8 px capital height and clean output from 10-16 px; upscaling to ~32 px
  rescued Tesseract at 8 px and did nothing or hurt for another engine. Matches our own mixed result on kitchens.
- **Detector settings that matter for us (verified, RapidOCR `config.yaml` and `ch_ppocr_det/utils.py` read 2026-11-14):** the
  default detector resize is `limit_side_len: 736, limit_type: min`, i.e. the short side is lifted to 736 px and never more;
  our median sheet (855 px long side) is therefore barely rescaled and a 10 px label stays 10 px for the detector unless we
  upscale first. Box filters: score threshold `box_thresh` 0.5, binarisation `thresh` 0.3, unclip 1.6, and boxes with a short
  side under 3 px are dropped (`min_size = 3`). A 1-letter label of 5 px therefore sits right on the filters. Raise the
  upscale, then lower `box_thresh` and let the dictionary decode reject junk (my suggestion, untested).
- **Page-level orientation (scope L9, one line):** PaddleOCR also ships a 4-class document orientation classifier
  (PP-LCNet_x1_0_doc_ori, 0/90/180/270, 99.06% top-1 on the authors' 1,000-image ID and document set, 7 MB, read 2026-11-14).
  Trained on text-heavy pages, it is untested on plans with few words; the crop-level vote in item 3 does not depend on it.
- **What breaks on our images:** sheet rotation by 90 (aspect rule above); labels of one letter ("K", "S", "P"), which
  the detector's minimum box or score threshold may drop; letters touching wall lines (text/graphics separation, not
  solved by any model here; PaddleOCR issue 18244, one user report, shows PP-OCRv5 mobile dropping most table rows that sit
  between thin border lines, closed unresolved); scans where strokes are 1 px; door and window size codes, which v5 garbled to nothing
  (0/32, 0/40) and for which v6 has no evidence.

## 4b. Experiment order I would run (hours are my estimates; first number by about hour 2)

1. **E1, 1 h:** rerun the 40-image room-label test with PP-OCRv6 medium det + small/medium rec through RapidOCR 3.10 (same
   tiling, same closed-vocabulary decode). Compare exact per room type with the 23-81% baseline. If the test images exceed 2000 px on the long side, log the per-page shrink factor (RapidOCR cap, Round 8) and confirm the tiling bypasses it. Also try the three detector
   levers: upscale to 2400 px before detection, `box_thresh` 0.3, and `limit_side_len` 1500.
2. **E2, 1-2 h:** synthetic recoverability sweep (no real data): render the ~25 codes in 3-4 CAD-like fonts at 5, 6, 8, 10, 12,
   16 px, four rotations, blur and JPEG levels, on white and on line-art clutter; run PP-OCRv5 mobile and v6 small and medium on
   each crop; plot exact match against height and rotation. This produces the missing 10 px number and shows whether v6 or the
   four-orientation vote moves the cliff.
3. **E3, 2 h:** crop-level four-orientation voting with decode-time masking of the CTC output to the label alphabet; compare with
   E1 on the rotated third of the 40 images.
4. **E4, 3-4 h, only if E1-E3 leave a gap:** fine-tune PP-OCRv6 small rec on E2's synthetic crops plus pseudo-labelled real
   crops (a crop read as a code of room class X inside a polygon of class X). Hold out dev images; never touch the sealed split.
5. **E5, optional:** a VLM reader (GOT-OCR2 with a box, or a LoRA Qwen3.5-0.8B at about 50 ms per crop on an A6000) only on crops
   where E3's four orientations disagree.

## 5. Finnish floor-plan abbreviations (verified in public housing brochures, read 2026-11-14)

Read as PDF text from six public Finnish new-build brochures and plan sets (Helsinki housing office, Skanska Helsinki, a
Jyvaskyla developer, Kaartokatu 46 and Torpparinkaari 2 and 4 from the same developer brochure site, a Helsinki developer's plan
set); each legend is the developer's own, so usage varies.

| Code | Meaning | Seen in |
| --- | --- | --- |
| MH | makuuhuone (bedroom) | all legends read |
| OH | olohuone (living room) | all legends read |
| K | keittio (kitchen) | Jyvaskyla and Kaartokatu 46 legends; not in the Helsinki legends |
| KT | keittotila (kitchen space) | Helsinki housing office, Skanska, Heka plan |
| KH | kylpyhuone (bathroom; Kaartokatu legend says "kylpyhuone (wc)") | Helsinki housing office, Jyvaskyla, Kaartokatu 46 |
| KPH | kylpyhuone (bathroom, other spelling) | Skanska legend, Heka plan labels |
| S | sauna (loylyhuone) | Helsinki housing office, Skanska, Jyvaskyla |
| WC | erillis-wc (separate toilet) | Skanska, Jyvaskyla, Heka |
| ET | eteinen (hall) | all legends read |
| VH | vaatehuone (walk-in closet) | all legends read |
| ALK | alkovi (alcove) | Helsinki, Skanska |
| RT | ruokailutila (dining space) | Helsinki, Skanska, Jyvaskyla |
| P | parveke (balcony) | Jyvaskyla |
| H | asuinhuone (habitable room) | Skanska |
| PUKUH | pukuhuone (dressing room) | Helsinki housing office |
| VAR | varasto (storage) | Skanska |
| KAYT | kaytava (corridor) | Skanska |
| AULA | aula (lobby) | Skanska |
| Fixtures on plans | AP dishwasher, JK fridge, L stove, PY laundry cabinet, SK cleaning cupboard, MU microwave | Skanska, Helsinki |

**PH** and **TK** are printed on apartment plans in a fifth brochure (Torpparinkaari 2 and 4) but no legend line defines them in
the text I read. The same brochure's specification speaks of "pesuhuone" (wash room), so PH = pesuhuone is a likely reading
(inference, not stated); TK appears next to cleaning and storage rooms in a sixth brochure (Kaartokatu 46) with no legend
entry. Treat both as unverified. "ak" on Helsinki plans is allaskaappi (sink cabinet). Also seen: TT talotikas, VT varatie. The CubiCasa5K plans come from other developers, so the
dataset's own label set has to be counted from the dev images, not taken from this list.

Sources: https://asuntotuotanto.hel.fi/system/files/mediabank/2025-05/00_asuntopohjat_kaikki_asunnot_1.pdf;
https://kodit.skanska.fi/494a97/contentassets/123c48887a0345d3938e2f8c64f455f9/liitteet/pohjapiirustukset-kerroksittain-as.-oy-helsingin-ruska.pdf;
https://ta.fi/wp-content/uploads/2025/03/hahlo3ja7_uudiskohde-esite-1.pdf;
https://www.hekaoy.fi/app/uploads/kohteet/0b752fe1-af35-46e4-9ee0-799c62a0e224/attachments/risupadontie_3,_A1-D74.pdf (all 2026-11-14).

## 6. Citation graph walked forward

- PaLeTTe (arXiv 2506.15010), Semantic Scholar citations read 2026-11-14 (via the headless browser after curl got 429):
  ArabGeoText (2611.03339, read), TiCLS (WACV 2026, 2602.04030, read: builds on DeepSolo), Text region detection in
  historical astronomical diagrams (ICDAR 2026, 2606.15886, read), UniLipi (2608.28195, listed), MapSAM2, LineLM and
  others (maps, not text reading; not opened).
- PaddleOCR 3.0 report (2507.05595), Semantic Scholar citations read 2026-11-14: 100 citers, all 2026, none on drawings;
  read PaddleOCR-VL-1.6 (2606.03264), the OCR survey (2611.04874), the plate recoverability abstract (2604.23814); listed
  and not opened: OmniSch PCB schematic benchmark (2604.00270), CoLIBRi on manufacturing drawings, an architectural
  construction-drawing extraction paper without arXiv id, water-meter digit YOLO-OCR.
- SVTRv2 (2411.15858), the recogniser line PP-OCR builds on, citations read 2026-11-14: about 60 citers listed; read: PP-OCRv6 adaptation
  to historical text (2609.20064: fine-tuning works from 20-240 lines, 300 steps; input height 48 to 96 px halves CER on
  historical lines), ICPR 2026 low-resolution plates (2604.22506), rotation-invariant recogniser (2608.10684), UnionST
  synthetic engine (2602.06450). Not opened: "A shared-backbone detection-recognition framework for end-to-end industrial
  character reading", the bus-route-number PP-OCR paper, the railway sleeper serial-number paper.
- PP-OCRv6 report (2606.13108) is five months old; its citers are the same 2026 wave above.

Round 4 (00:50): OpenAlex forward walk, PP-OCRv6 report (17 citers) and the PaLeTTe lineage paper (15 citers). Nothing new that
changes the ranking: PolyOCR-Venus (2609.37712) and the 2026 OCR survey (2611.04874) are VLM-side; the survey names hallucination,
omission and weak spatial grounding as the generative-OCR failure modes, which is the argument for keeping a detector plus
closed-vocabulary recogniser. GPT-4o legend-item linking (abstract only) is a legend-parsing method, not a tiny-label reader.

Round 5: repo checks. PaddleX (Apache-2.0) `ocr-core` extra pulls imagesize, opencv-contrib-python, pyclipper, pypdfium2, python-bidi,
shapely; the only copyleft item is python-bidi (LGPL by PyPI classifier, weak copyleft, fine as an installed library). No AGPL or GPL
dependency found on either the PaddleOCR or the RapidOCR path. Open PaddleOCR issue 18320 (2026-08): on CPU the pipeline used about
1-1.5 of 3.5 allocated vCPUs, so more cores did not cut latency; budget for one process per core instead of threads if we go CPU-only.

Round 6: floor-plan OCR, two 2026 papers read in full. (a) Liang, Fukuda, Yabuki, ECCC 2026 (paper 212): CRAFT detector plus
TPS-STN-CRNN (CTC) recogniser, fine-tuned on 1,000 floor plans they annotated for text from CubiCasa5k and CVC-FP; strict exact-match
accuracy 90.2% on their test split and 85.7% on an external set, for dimension numbers, not room codes. Two lessons: a small fine-tune on
about 1,000 annotated plans is enough to reach about 90% on digit strings, which supports experiment E2; and their need to annotate text
themselves is indirect evidence that CubiCasa5k ships no text boxes (open question in section 8 stays open). Leakage flag: any
checkpoint of theirs saw CubiCasa5k. No weights or licence found. (b) arXiv 2607.00015, a compliance-check framework, names
PaddleOCR/Tesseract/EasyOCR generically and gives no OCR numbers; it only warns that unreadable text and OCR errors propagate and asks for
confidence scores and human review. Retries for the gaps: Schoenfelder 2024 has no open copy (OpenAlex: closed), still abstract-only;
lexicon-constrained decoding 2025-2026 yields only speech and diacritic CTC decoders (2603.14002, 2607.18946), no scene-text result.

Round 7: adjacent field, meter reading as closed-class detection (arXiv 2009.10181, read in full 2026-11-14). The authors read counter digits
with a tiny YOLO-style detector with one class per digit (Fast-OCR, 10 classes, 384x128 input, 6.6 BFLOP) instead of a sequence reader.
On identical images and an identical upstream stage, a CRNN reader gets 86.85% average recognition rate and Fast-OCR 94.90% (95.87% with
their rectification stage), and rejecting low-confidence readings lifts the accepted ones to 99% or more. It supports a second route
for our closed vocabulary: a classifier or detector with one class per abbreviation (about 25) rather than character decoding. It needs
text boxes and labelled crops we do not have, so it sits behind the synthetic-crop fine-tune (E2) as an alternative, and its
reject-by-confidence rule is worth copying either way: send low-confidence labels to the second reader instead of guessing. Domain gap:
digits only, one fixed counter window, trained on 12,500 field images; Darknet code.

Round 8 (new risk for ranked row 1, found while reading RapidOCR open issues): RapidOCR's `config.yaml` has `Global.max_side_len: 2000`
and `preprocess_img` (main.py) calls `resize_image_within_bounds(img, min_side_len, max_side_len)`, so every page is shrunk to at most 2000 px
on its long side before detection (verified in the source, read 2026-11-14). Open issue 764 (2026-11-06, with a PR 767 opened by the reporter)
measures it on a 300 DPI engineering drawing: 41 boxes / 646 characters at the default against 2,054 boxes / 13,184 characters at native
resolution with tiling, at about 3x the time on ordinary documents (the author's own figures, one drawing). Its claim that the tiled
branch is dead code at the default `limit_side_len` 736 matches my earlier source reading. What this means for us: nothing on the current export (median long side about 855 px, so no shrink happens), but any
PDF render above 2000 px on its long side (for example a vector-PDF page rasterised at 200+ DPI) loses 10 px labels to the resize,
and a first test on such renders would look like "OCR cannot read our labels". Before any engine comparison on renders: raise `max_side_len`
(or tile at native resolution) and log the shrink factor per page. This applies to PaddleOCR too (its detector resizes by `limit_side_len`/`limit_type`), so measure both.

Round 9: open PaddleOCR issues on PP-OCRv6 (read 2026-11-14), four that touch our plan. (1) Issue 18364 (open since 2026-09, no maintainer reply): a
reporter finds that the unified v6 small ONNX recogniser (also v5 mobile) returns every non-ASCII character as UTF-8 bytes shown in CP1252, for
example e-acute as "Ã©", with weights identical to the official export; ASCII is fine. One report, no repro attached, so it may be a decoding error on their
side, but it is exactly our path (ONNX through RapidOCR, Finnish a/o with dots). Before trusting v6 on Finnish text, E1 must include a
crop with ä and ö and check the output string; a cheap guard is to try `s.encode("cp1252").decode("utf-8")` on any output with such
characters. Our label alphabet is mostly ASCII, so the closed-vocabulary decode (section 4) side-steps it; free-text legend lines do not. (2) Issue 18434:
PaddleOCR 3.7 needs PaddlePaddle 3.1 or newer (3.0.0 crashes on v6 medium rec); pin versions in the environment. The same issue gives the only
third-party v6 number I found: on HierText crops from a YOLO detector, v6 medium rec read 3,819 words right against 3,462 for v5 server (+10%);
scene text, not drawings. (3) Issue 18299: a user fine-tuning v6 medium rec on 55,740 lines added 287 targeted synthetic lines for 6 confusable
characters; errors on those fell from 41 to 16 but 10 previously correct lines broke. For E4: mix targeted synthetic crops into the real ones
instead of training on them alone, and keep a fixed held-out dev list to catch regressions. (4) Issue 18378: word boxes from `returnWordBox` are split out
of the line box and were reported imprecise; a reply points at `unclip_ratio` 2.2 versus the default 1.5. Do not depend on word-level boxes from the pipeline.

Round 9b (my own check of issue 18364, 2026-11-14): RapidOCR 3.10.0 from PyPI, PP-OCRv6 small detector and small recogniser through ONNX Runtime, language
`fi`, on a rendered image of five clean lines in a sans font: "Keittiö", "Työhuone", "Sauna ÄÖ", "Kylpyhuone", "MH 12". Output was exactly these strings
(scores 0.99, 0.99, 0.94, 0.998, 0.999), no mojibake. So the reported byte-rendering problem does not appear on RapidOCR's own v6 ONNX
files with the `fi` dictionary; it may be specific to the PaddlePaddle-published ONNX file or to the reporter's decoding. Scope of the check:
clean 40 px renders, one font, five strings; it says nothing about 10 px labels. Keep the ä/ö line in E1 as a smoke test.

Round 10 (my own exploratory runs, scratch only, nothing in the repo changed; weak evidence, read the caveats): RapidOCR 3.10, PP-OCRv6 small detector
and `fi` small recogniser, ONNX, default settings. Test: 12 closed-vocabulary codes (MH, K, S, KH, VH, PH, WC, ET, OH, AK, KHH, TK), one code per
image in a sans font, black on white, cap height 5-16 px, four rotations; success = the code appears exactly among the outputs (n = 12 per cell).
(a) On a 200 px canvas (the detector lifts a short side under 736 px to 736, so the text is enlarged about 3.7x): upright 11-12 of 12 at every
size from 5 px up; rotated 90 degrees 1-6 of 12, 180 degrees 4-8 of 12, 270 degrees 6-8 of 12, with no trend by size. (b) On an 850 px canvas
(no enlargement): 0 of 12 upright at 5-12 px cap height, 10 of 12 at 16 px; rotated at 16 px 4, 8 and 6 of 12. (c) The same 850 px canvas enlarged
2x beforehand: 0 of 12 everywhere, which contradicts the expectation and shows the result depends on the canvas size and the text-to-page proportion (a
single code on a mostly blank page is not how a floor plan looks), so I do not trust the size axis. What I do trust, because it holds in
every setup: (1) rotated codes fail far more often than upright ones even at 16 px, which agrees with the aspect rule in the RapidOCR source
and supports the four-orientation vote (E3) as the first thing to build; (2) [WITHDRAWN, see Round 12: the blank-page detector failures were an artefact of the test page]; (3) section
4's "expect the cliff between 6 and 10 px" cannot be confirmed or refuted from this. The proper E2 (codes on line-art clutter, real fonts, real page
size, recogniser called on crops directly) is still to be run.

Round 11 (my own scratch test of ranked row 3, the four-orientation vote; exploratory): same 12 codes and sans font, cap height 6, 8, 10 and 12 px,
four sheet rotations, 12 x 4 x 4 = 192 crops. Crops were cut tight around the dark pixels (standing in for a detector that found the box), then read
by the PP-OCRv6 small `fi` recogniser alone, no detection and no 0/180 classifier. Single read of the crop as given: 83 of 192 exact (upright 48 of 48,
90 degrees 16 of 48, 180 degrees 13 of 48, 270 degrees 6 of 48). Read at 0, 90, 180 and 270 degrees and keep the answer that is in the code list,
highest score first: 192 of 192. Caveats that matter: clean black-on-white renders in one font, no line-art clutter, no blur or JPEG; boxes are perfect, so
detection misses are not tested; the code list is only 12 entries, so a wrong rotation rarely lands on another valid code (with 25 entries and real
clutter, expect some false accepts, so keep the score as a tiebreak and abstain below a threshold); the symmetric codes (S, K) are rotation-safe by
nature. Still, this is the first direct evidence that the recogniser itself is fine at 6-12 px cap height once the crop is upright and the
failure on rotated labels comes from orientation handling, which is why E3 should run right after E1. The crop and vote code is about 20 lines.

Round 11b (harder rerun of the same test, exploratory): 25 codes (the 12 above plus RH, H, SH, VAR, ALK, P, WC/S, TH, KK, PKH, ES, LASP, TE), cap height 8, 10, 12 px,
four rotations, 300 crops, now with a 0.6 px Gaussian blur, JPEG quality 40 and (half the time) a thin grey line across the crop. Single read as given:
120 of 300 (upright 72 of 75, 90 degrees 15, 180 degrees 28, 270 degrees 5). Four-orientation vote, in-list answer first, then recogniser score: 291 of 300
(97%; 71, 73, 73, 74 of 75). False accepts: of 24 junk crops (8 non-codes such as XQ, ZZ, IL at three sizes), 1 was read as a valid code. Same caveats as
Round 11: one sans font, boxes assumed perfect and tight, no real wall lines touching the glyphs. The upright result (72 of 75 single, 71 of 75 vote) shows the vote costs
nothing when the crop is already upright and loses at most a code or two on degraded input. It is the strongest single piece of evidence in this
report for the order E1, E3, E2, E4, and it needs no training.

Round 12 (correction to Round 10, exploratory): the same engine on a more page-like test: 850 px page with a wall-like grid of 2 px black lines, ten
codes per page placed at random in the cells, upright, cap height 8, 10 and 12 px, 4 pages each (120 codes). Default settings found 113 of 120
(94%); `box_thresh` 0.3: 113; page enlarged 2x: 114; 3x: 112; 2x plus `box_thresh` 0.3: 114. So on this test the detector is not the weak link, and neither
enlarging nor lowering the threshold helps; the 0 of 12 in Round 10 (b) and (c) came from a nearly blank page with one tiny code on it, which the detector's
normalisation handles badly, and should be ignored. Remaining weaknesses on this evidence: rotated crops (Round 11) and whatever real plans add that
my renders lack (touching wall lines, hatching, scan noise, 1 px strokes). This also lowers the expected value of the detector levers in E1 and raises
that of E3; keep the levers in E1 only as a cheap check on real images, where the answer may differ.

Round 13 (exploratory, same page-like test as Round 12, default settings): the whole sheet rotated before the call. Codes found of 120: 0 degrees 113 (94%),
90 degrees 54 (45%), 180 degrees 69 (58%), 270 degrees 41 (34%). So with the stock pipeline (detector, 0/180 crop classifier, RapidOCR's
aspect rule) a rotated sheet loses more than half of its short codes, even at 180 degrees where the classifier is supposed to fix it, on clean
renders. This matches the one-in-three rotated sheets in our images and the roughly 23-81% spread of our measured baseline, and it is the cleanest
reason I can give for E3 (crop-level four-orientation vote) coming before any model swap. Limits: synthetic grid page, one font, upright-trained
rotation only; the real-image effect must be measured on the 40-image set. A page-level alternative to test next to the crop vote: run the whole page at 0
and 90 degrees (and 180) and keep each code's best in-list read, which needs no crop code at all.

Round 13b (same test): running the whole sheet at 0, 90, 180 and 270 degrees and keeping every in-list read found 116 of 120 codes (97%) on a sheet
given in any of the four orientations, against 41-113 for a single pass. This page-level vote needs no crop code, costs four detector passes
per sheet, and made rotation irrelevant on the synthetic page. Same limits as Round 13 (synthetic grid page, one font, 10 in-list codes, false accepts not measured on this test).
It is now the first thing to try on the 40-image set, before the crop-level vote.

## 7. Looked for and did not find

- Any accuracy by text height for printed 2-4 character codes (all engines). Retry with new terms (2026-11-14): only Tesseract-era
  guidance turns up, through secondary pages (cap height 20-40 px recommended, error rate mostly tied to capital-letter height in an informal forum benchmark;
  the official-doc wording was not confirmed by me). Nothing for PP-OCR or 2-4 character codes; E2 stays the way to get the number.
- Any floor-plan paper that reads Finnish or Swedish labels.
- Lexicon-constrained decoding numbers from 2025-2026 (search found only older lexicon-50/1k/full tables).
- A permissively licensed, trained, word-level spotter for diagrams (TESTR code is Apache but unmaintained since 2023-01
  and needs boxes).
- Word-level boxes from the VLM OCR models: dots.ocr and DeepSeek-OCR give element or region level; PaddleOCR-VL gives
  line-level quadrilaterals by its own description.
- Microsoft's P&ID digitisation blog returned an empty page through the browser.
- The one floor-plan paper that matches our task best, Schoenfelder et al., "Deep learning-based text detection and recognition
  on architectural floor plans" (Automation in Construction 2024, DOI 10.1016/j.autcon.2023.105156), could not be read: the open copies
  I found were other papers, the publisher page was not tried. Search-result abstracts say YOLOv7 reaches up to 97.5 weighted mAP for
  text detection and PARSeq is the best of four recognisers, with weights and annotated data announced as public. All of this is
  UNVERIFIED; it is scope L1 material for the other orchestrator and worth a look because it names a floor-plan text detector.
- Bridge-drawing OCR (EG-ICE 2025, read) chose a cloud OCR wrapper (Handprint) over Tesseract, EasyOCR and PaddleOCR; cloud OCR is out
  for us (no uploads).

- **Do VLM OCR models handle scattered two-letter labels and return positions?** No evidence either way for 2-letter labels. For
  positions: the official OCRBench v2 English leaderboard (2026.09, private test, read 2026-11-14) has a Spotting column
  (text with its location) where Qwen3.6-27B scores 74.3, Qwen3.5-9B 41.8, Gemini 3 Pro 80.8, Gemini-2.5-Pro 13.4, GPT5 6.5,
  LFM2.5-VL-3B 0.0. Spotting is unreliable below about 27B parameters unless fine-tuned (MangaLMM, ArabGeoText agree), and none of
  these tasks is a floor plan. A 12-16 GB card holds none of the strong ones unquantised.

## 8. Open questions and missing tools

- Do the CubiCasa5K annotation SVGs carry text positions or only room polygons with a class? The public loader code reads
  English class names (Bedroom, Kitchen, ...) and parses no text element (verified in `house.py`, `svg_utils.py`), and the
  dataset paper does not describe text annotation; I could not check an SVG (none on this machine). If positions exist, a
  label detector and a recogniser fine-tune on real crops become possible on dev images only. If not, the fallback is
  distant supervision: an OCR box inside a room polygon of class X is a candidate crop for the codes of class X.
- Answered: RapidOCR 3.10 registry lists PP-OCRv6 det/rec tiny, small, medium as ONNX files (modelscope paths) with `fi` and
  `sv` in supported languages, all Apache-2.0 per its MODEL_LICENSES.md (read 2026-11-14). Not tried to run.
- Does PP-OCRv6 detection keep one-letter boxes? Unknown.
- For scope L1/L4 (other orchestrator): none found.
- Missing tools: no arXiv MCP, Semantic Scholar rate-limits curl (used the headless browser), no PDF-to-text tool
  (used pypdf through uv in a scratch directory), no GPU access (no number here is measured by me).

## Targets check (against section 6 of the context file)

- Sources opened and read: about 60 distinct pages, papers, model cards, source files and PDFs, one line each in the log with URL and
  date read (all 2026-11-14). Reads that failed are in the log too (MDPI refused, a blog returned an empty page, two arXiv abstracts
  had no HTML).
- From 2025-2026, read in full or in the relevant part: PaddleOCR 3.0 report (2025-07), PaLeTTe (2025-06), ICDAR 2025 MapText report
  (2025-09), MangaLMM (2025), P&ID digitisation (DSAA 2025), PP-OCRv6 report (2026-06), PaddleOCR-VL-1.5 and 1.6 (2026-01, 2026-05),
  astronomical diagrams (2026-06), ArabGeoText (2026-11), OCR survey (2026-11), PP-OCRv6 adaptation (2026-09), ICPR 2026 plates,
  RISTER, UnionST, water-meter YOLO-OCR (2026), AEC drawing layout (2026), engineering-drawing VLM framework (2025-10).
- Licences: code from `gh api repos/<owner>/<repo>/license` or the LICENSE file; weights from the Hugging Face model card
  (`raw/main/README.md`); RapidOCR's MODEL_LICENSES.md for the ONNX copies. Where no file exists (GOT-OCR2.0, UnionST, the
  floor-plan synthetic generator) the table says so.
- Citation graph walked forward from PaLeTTe, PaddleOCR 3.0 and SVTRv2 through Semantic Scholar (section 6).
- Leakage flag on every row; no OCR checkpoint here is known to use CubiCasa5K. Training data of PP-OCR models is not public.
- Every transfer note says what breaks. No number in this report was measured by me: there was no GPU and no weights download.

## Status

Final, 2026-11-14 by `date` before 01:20. Generation 1 did the first full pass; generation 2 (same worker after a context handoff) ran the
reading rounds asked for: forward citations (Round 4), repo, licence and issue checks (Rounds 5, 9), two 2026 floor-plan OCR papers read
in full (Round 6), meter reading (Round 7), the RapidOCR 2000 px cap (Round 8), top-5 numbers re-checked against fetched papers, and
my own scratch tests on synthetic renders (Rounds 9b-13b; nothing in the repo changed, tests only in a scratch folder). Verified here
= opened and read; the scratch tests are exploratory and synthetic. Unverified or abstract-only: Schoenfelder et al. 2024 (paywalled, a
UCL copy sat behind a bot challenge and was not fetched), eDOCr2 paper (publisher refused), GPT-4o legend paper, church-record paper.
OpenAlex's free budget for this network ran out, so later searches used WebSearch. Nothing committed.

Top 3: (1) run the sheet at four page rotations and keep in-list reads (116/120 vs 41-113 on my synthetic test), then crop-level vote;
(2) PP-OCRv6 swap via RapidOCR 3.10 (Finnish letters read correctly in my test); (3) synthetic closed-vocabulary recogniser fine-tune, mixed with real crops.
