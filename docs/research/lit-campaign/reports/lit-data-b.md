# lit-data-b: sideways transfers for data, pretraining and synthetic training (scope L8, angle b)

Worker lit-data-b, read-only, 2026-11-14. Every source below was opened by me (page, HTML full text, or the PDF read
locally) on 2026-11-14 unless marked **[reported]** (I only saw a search summary, an abstract or the authors' claim and
did not read the passage). **[V]** = I read it there. Licences were read from the repository LICENSE file through
`gh api repos/<owner>/<repo>/license`, from the Zenodo record, or from the paper page; code and data/weights are
separate facts. "Leak" = trained on CubiCasa5K or a repackage of it.

What this report extends: the earlier reports list datasets and say "no paper gives a clean augmented-vs-not number on
real degraded drawings; no sim-to-real numbers from OCR/OMR/P&ID; no mixing ratios". This one brings those numbers
from five adjacent fields (music scores, P&ID diagrams, scene text, historical maps, tables) plus industrial
detection, and turns them into a recipe for a commercial-safe night build.

## 0. What the evidence says, in seven lines

1. **Pretrain on synthetic, then fine-tune on real beats mixing.** Mask R-CNN on industrial parts: best mix 80.13 AP,
   fine-tune after synthetic pretraining 82.05 to 83.7 AP (arXiv 2211.16066, [V]). Maps: removing synthetic pretraining
   costs 5.1 mIoU, 74.2 to 69.1 (arXiv 2603.05037, [V], Table 4). Scene text:
   a synthetic-trained model fine-tuned on 1% of the real labels equals the model trained on all real labels, 87.26 vs
   87.22 (arXiv 2602.06450, [V]).
1b. **But with thousands of real images the gain disappears.** On industrial recycling with 8.4k real training images,
   synthetic pretraining then fine-tuning scored 69.0 against 69.2 real-only; synthetic-only scored 40 against 69 on
   0.01%-of-image objects (arXiv 2605.26884, [V], section 3.12). Our dev set is that size, so the synthetic route mainly
   buys rare classes and commercial-safe weights.
2. **Real scan texture beats hand-made noise.** Music scores, the closest "tiny symbols on line art" field: overlaying
   51 real blank scanned pages under rendered scores took real-scan AP@0.25 from 36.0 to 56.5, and 73.7 with a short
   full-page fine-tune (TISMIR 2024, [V]). Hand-made blur plus a dust overlay on synthetic maps made things worse
   (accuracy 0.8357 to 0.8125), while a learned degradation helped (0.8716) (arXiv 2511.15875, [V]).
3. **Whatever axis the synthetic data lacks, the model fails on.** Scene text: without the rotation and curve layout
   features the Multi-Oriented score drops from 87.8 to 34.3 (Table 6, arXiv 2602.06450, [V]). For us: synthetic sheets
   must be rotated by 90 and 180 degrees, carry several plans per sheet, and carry clutter, or the model will not
   count them.
4. **Match the target's density.** Music: removing page concatenation (1 to 6 systems per page) is the largest single
   loss on real scans, +14.3 error points (arXiv 2605.10835, Table 3b, [V]). Our 1-in-5 multi-plan sheets are this
   case.
5. **Small symbols need tiles, and a final pass at full page.** P&ID symbols of 8 px are cut as 1500 px tiles with a
   750 px stride (arXiv 2604.16513, [V]); music models trained on half-resolution 1000 px crops "lack global
   awareness" and need 200 epochs on full pages (TISMIR 2024, [V]). A plain Faster R-CNN with smaller anchors found no
   symbols at all on rendered scores (arXiv 1804.00525, [V]).
6. **Nobody measured exact counts.** Every paper reports AP, mIoU, F1 or error rates. None reports per-image exact
   counts, and none sweeps the real-to-synthetic ratio for symbols on drawings. The numbers here carry over as
   direction, not as a prediction of our exact-match rate.
7. **Round 6 adds two real-crop precedents on drawing pages and a hint on size.** Real crops pasted onto drawings beat
   training on a few real drawings both for floor-plan symbols (Hassaan 2023: rare classes found, simple glyph overfits)
   and for drawing text (Schlagenhauf 2023: 81.9% of 171 labels versus 4.7%, MIT generator code); and input
   resolution alone gave +21% AP on tiny objects (arXiv 2509.17078) - see 3.12.

## 1. Top 5 (floor-plan work and transfers in one list)

All five are transfers; none is a floor-plan paper (the other workers of this scope cover those).

### 1. ScoreAug: real blank-scan overlay plus a full-page finishing pass (music scores). Verdict: **try**
- Field and task: optical music recognition, detecting about 135 classes of tiny symbols on rendered pages and then on
  real scans. Source: Tuggener et al., Transactions of the ISMIR 2024, vol. 7, DOI 10.5334/tismir.157, read in full
  from the open-access PDF.
- What plays the role of our object: a notehead ("less than hundred to many thousands of pixels in area" per the DeepScores paper) is our
  window cell or sink glyph; the staff lines it sits on are our walls.
- Measured [V]: S2A-Net detector trained 2000 epochs on half-resolution 1000x1000 crops of DeepScoresV2, evaluated as
  AP at overlap 0.25 (they chose the low threshold because the objects are so small). Baseline on the real test set
  36.0; with ScoreAug 56.5; with ScoreAug and "Finalise" (200 extra epochs on full pages) 73.7. Synthetic-set AP falls
  from 87.6 to 83.3, which they accept. Domain-adversarial adaptation instead gets 48.9 and drops the source set to
  72.4, so it ranks below ScoreAug.
- How it works [V]: take one of 51 real blank scanned pages, augment it and the rendered page separately (blur,
  salt-and-pepper, small rotation, brightness, irregular border), keep the darker pixel at each position so the ink
  stays black and the paper texture shows through. Final probabilities: salt-and-pepper 0%, other augmentations 30%,
  blur 10%.
- Code and licence: code at github.com/raember/s2anet (branch named in the paper); no licence file (`gh api` returns
  none), so treat as unusable code; the detector base mmrotate is Apache-2.0 (read), and the data DeepScoresV2 is
  CC BY 4.0 (Zenodo record, read). The paper is CC BY 4.0. The merge is about 30 lines to rewrite.
- Leak flag: no (music). We would not use their weights, only the idea.
- What breaks on our images: our real images are not clean renders plus scan; we do not have 51 blank pages, but the
  margins of the dev scans are blank paper (check on a sample before relying on it). Their gap is rendered-to-scan; ours
  is also CAD-style-to-hand-photographed. The 0.25 overlap threshold hides box precision; our exact-count rule cares
  about box merging and splitting, not IoU, so re-measure with counts. Only small-angle rotation is mentioned in the
  augmentation description I read (Table 2's full list was garbled), no 90 or 180 degree rotation. At 5 to 20 px symbols the half-resolution crops they used would lose our symbols: train at
  full resolution.
- JSON field: `elements` boxes.
- Hours to a first number on our dev boxes: about 3 to 4 (my estimate): write the overlay, render ResPlan plans, train a
  detector from the other workers' shortlist with and without it.

### 2. Seed the synthetic sheets from real layouts and resample the symbol bank (P&ID diagrams). Verdict: **try the pattern, not the code**
- Field and task: piping and instrumentation diagram digitisation; detect symbols and connections on sheets of 7000 x
  4500 px or more. Source: SynthPID, arXiv 2604.16513, 15 Apr 2026, read in full HTML.
- What plays the role of our object: a valve of "often just 8 x 8 px" is our window or door symbol; the pipe graph is
  our wall graph.
- Measured [V]: the generator takes the graph of each real sheet as a seed, jitters node positions, swaps each symbol
  for a random template of its class, re-routes pipes, renders at high resolution, and drops duplicates by structural
  and perceptual hash (about 12,000 tries gave 665 images). Relationformer, ResNet-50, 1500 px tiles with 750 px
  stride, 150 epochs on four A6000 GPUs. Edge mAP on 12 real sheets (5-fold, 3 seeds): real-only 69.4; synthetic-only
  (zero real) 63.8; synthetic plus a handful of real 72.6. Template-scatter synthetic data from the earlier work is
  about 33 (estimate quoted from that paper). Scaling (Figure 4, text re-read in the full page): +12.5 points from 100 to 400 synthetic images, +5.1 from 400 to
  665; the authors read the plateau as seed diversity, not image count, being the limit (12 seeds) and advise widening
  the seed pool before generating more images. ResPlan's 17k layouts are that wider pool for us.
- Code and licence: repository named as `LatentSpaceIITB/SynthPID` in the paper; the GitHub API returns 404 for it (re-checked 2026-11-14; the same organisation's public repos include one named pid_drawings from Jan 2026 with no licence and no readme, a notebook scratch repo that I did not treat as the release), so
  I could not read a licence or confirm it exists. Benchmark data PID2Graph is on Zenodo, CC BY-SA 4.0 (read). The
  paper states no licence for generator, data or weights.
- Leak flag: not applicable (P&ID).
- What breaks: no randomisation of line width, font, noise or blur is reported, so this paper tells us about layout and
  symbol realism, not about the scan gap. The seed images are also the evaluation images, which may inflate the
  zero-real number (the paper does not say whether seeds were limited to the training fold). Our version: seed from
  ResPlan's 17k vector layouts (CC BY 4.0 data, MIT code per its LICENSE, read; the GitHub API shows NOASSERTION
  because the file holds two licences) and from the real dev plans' room polygons, then drop our own symbol library
  into walls. ResPlan has a `bathroom` class but no WC class (README and utils, read), and no sauna.
- **Licence conflict to settle before the commercial-safe claim (new, repo read 2026-11-14):** ResPlan's LICENSE and README
  grant the data under CC BY 4.0 (LICENSE rewritten in the 28 Jul 2026 commit "per review commit"), but the repository's
  `croissant.json` metadata, last touched in that same commit and describing the Kaggle release v6 of May 2025, names
  **CC BY-NC-SA 4.0**. Two open issues (#5 "Clarification for License", #8 "Clarification on ResPlan Commercial Licensing",
  the second asking about commercial model training) have no maintainer reply. The dataset has also changed since the
  earlier report (geometry clean-up in v7 and a bathroom-door fix in v8, May 2026), and the Kaggle copy ships a different
  graph definition. Until the owner answers, treat ResPlan as CC BY 4.0 per the file the repository itself calls the
  licence, keep a copy of that LICENSE text with the training record, and ask the maintainers in a public issue; the
  safe fallback is our own drawn layouts.
- JSON field: `elements`, `rooms`, `plans`.
- Hours: about 6 to 8 for a renderer with 3 styles (est.), the same job the earlier report recommended; this paper
  gives the first evidence that seeding from real layouts matters more than random scatter.

### 3. Synthetic pretraining, then fine-tune on real boxes; do not mix at one ratio (industrial detection, maps, scene text). Verdict: **try**
- Evidence [V]:
  - Vanherle et al., arXiv 2211.16066 (Nov 2022; full page text re-read): Mask R-CNN (ResNet-101), industrial metal parts,
    total fixed at 3,510 images, transfer learning plus augmentation. Mixing real into synthetic: "adding a larger ratio
    of real images improves the performance even more, until the five to one ratio", best 80.13 AP, above real-only
    (the text does not spell out the direction; since more real helped up to that point it is most likely five real to
    one synthetic). Fine-tuning a synthetic-pretrained model on real: 82.05 AP even with a small real share, 83.7 AP at one
    to one; the text puts this almost five points above real-only (so real-only is about 77 to 78) and ten above the
    large synthetic-only set (about 72). Lighting randomisation helped more than pose randomisation. Image size and object
    sizes are not reported.
  - Petitpierre, arXiv 2603.05037 (Mar 2026, v2 Oct 2026; full page text read, Table 4 verified): 1,006 real training
    maps plus 12,122 synthetic maps (90.6% of the training images) for the first 205k iterations, then 140k iterations
    fine-tuning on real only. Mean IoU on 144 real test patches: 74.2 with both stages; 69.1 without the synthetic
    pretraining (recall 75.4 vs 79.4, precision 84.2 vs 85.4: the synthetic data mostly buys recall); 69.1 without the
    real-only fine-tuning stage; 70.0 without the multiscale test-time pass. Mask2Former Swin-L at 768 px. The
    synthetic generator randomises line width, hatching, textures, colour (Gaussian mixture fitted to real maps), 15%
    grayscale, JPEG, frame crops, place names; the paper ablates only "pretraining on or off", not the individual
    randomisations. Both stages matter equally, and a real training set of about one thousand images is the same order
    as our 3.8k dev images.
  - Ye et al., arXiv 2602.06450, CVPR 2026 per the arXiv comment: synthetic engine for scene text; fine-tuning the
    synthetic-trained model on 1% (32.2k) of real labels gives 87.26 on the hard benchmark, equal to the 87.22 of the
    model trained on all 3.22M real labels; pretraining then full real fine-tune reaches 91.39.
  - Bay et al., arXiv 2510.12208 (Oct 2025): Faster R-CNN, pallets; real-only AP@[.5:.95] at 10/50/100% of 160 real
    images: 0.643 / 0.789 / 0.795; the paper says synthetic effects are "modest", mixing 10% real helps most, and
    bridged transfer learning beats mixing but numbers are in figures only.
- For us: pretrain on ResPlan renders (plus the NC set if the team accepts it for local weights), then fine-tune on the
  3,828 dev images' 104k boxes. Report the dev result at each stage.
- Leak: no CubiCasa5K involved in the recipe.
- What breaks: these papers' real sets are 160 to 3.2M images; ours is 3.8k with 104k boxes, which is "real data is not
  scarce". The gain from synthetic pretraining shrinks as real data grows (Ye et al. at full real data: +4.17 on a hard
  benchmark, but that is in text, a different regime). Expect the synthetic stage to help most on rare classes
  (bathtub 312 boxes, sauna stove 2.5k) and on style shifts, less on windows and doors that have 33k and 36k boxes.
- JSON field: `elements`.
- Hours: no extra training code; one extra pretraining run, about 2 to 3 h per run on the 12 GB card at half the tile
  size (est.).

### 4. Match the target's density: concatenate several rendered plans per sheet (music, Transcoda). Verdict: **try**
- Field and task: end-to-end optical music recognition trained only on rendered scores, tested on real historical
  scans. Source: Transcoda, arXiv 2605.10835, 11 May 2026, read in full HTML (appendices only via a summary).
- Measured [V]: pages are built by concatenating one to six systems (cap 2048 tokens); Verovio rendering at 1485 x 1050
  with randomised font, scale (integer 52 to 84), margins, and line widths drawn uniformly (staff line 0.10 to 0.26,
  stem 0.10 to 0.36, bar line 0.16 to 0.72, ledger line 0.10 to 0.40, Table 4 of the paper: a 2.6 to 4.5 fold spread of
  stroke weight), staff spacing 4 to 20 and system spacing 3 to 10; then OpenCV affine and perspective, paper textures,
  lighting gradients, colour casts, and Augraphy (ink bleed, mottling, shadows, JPEG). On 102 real Polish scans,
  OMR-NED 63.97 (lower is better). Ablations on the real scans (reference 65.76 for the greedy model): without
  concatenation 80.10 (+14.34, largest); without "asymmetric augmentation" 78.99 (+13.23, term not defined in the
  text I read); without visual degradation 76.95 (+11.19). 58.8M parameters, 6 h on one RTX 5090 from scratch. The
  authors' own reading, quoted from Section 5: "matching target density is just as critical as simulating visual noise".
- Code and licence: github.com/btrkeks/transcoda is **AGPL-3.0** (read): ideas only, code out. Augraphy is MIT (read). Data cards read 2026-11-14 (raw README): btrkeks/verovio-synth-omr (1,998 synthetic pages, evaluation benchmark) is CC BY 4.0; btrkeks/polish-scores (112 real historical scans, evaluation only) is 'other, see upstream PRAIG licence', so use neither as training data without reading the upstream terms.
  Verovio is LGPL-3.0 (read), acceptable unmodified under record 0006 but not useful for floor plans. The music
  renderer LilyPond behind DeepScores was not checked.
- Leak: not applicable.
- What breaks: the model is a sequence decoder over one page at 1485 x 1050 and is not a detector; the 102-scan test set
  overlaps the model-selection split in the paper's own wording, so the headline is soft; no ablation of single
  rendering randomisations (font, margin) exists. Our version: sheets with 1 to 4 plans (dev counts 3,044 / 672 / 109 /
  3) built from ResPlan plans placed on one canvas, with a title block and a few distractor drawings. This also gives
  exact `plans` labels for free.
- JSON field: `plans`, `elements`.
- Hours: about 2 (est.) once the renderer of item 2 exists.

### 5. Paste real symbol crops onto new backgrounds, no overlap, no blur (copy-paste, TME). Verdict: **try**
- Added 2026-11-14 [V, full text]: two document-domain precedents of real crops on drawing pages - Hassaan et al. 2023 (emergency floor plans: symbol images pasted on real cutouts, at most 12 per cutout, rare classes found about 50% where the real-only model found none, but the simple stairs glyph overfitted) and Schlagenhauf et al. 2023 (150 real element crops from 9 drawings pasted into generated pages, MIT generator code; found 81.9% of 171 real labels versus 4.7% for a model trained on the 9 real drawings); see section 3.12 for the details and what breaks. Note the Kisantal 'no blur' finding conflicts with Hassaan's deliberate blur; the blur there was matched to the scan sharpness, so for us match the blur to the target page and test once on the dev split.
- Evidence [V]: Kisantal et al., arXiv 1902.07296 (2019), Mask R-CNN ResNet-50 FPN on COCO: copy-paste of small objects
  with the original images kept at a 2:1 ratio and p = 0.5 raises AP_small from 16.7 to 17.9 (detection) and 11.3 to
  12.4 (segmentation); gain peaks at one to three pastes per object; pasting that replaces the originals loses
  (16.1); allowing overlap 17.3; Gaussian-blurring the pasted edge hurts (17.0 and 17.3). Objects scaled +/-20%,
  rotated +/-15 degrees, no overlap, at least 5 px from the border. No code released, gains are about 0.01 AP so seed
  noise is possible (no variance reported).
- Cross-field: InstructTable (arXiv 2604.02880, Apr 2026, [V]) builds new tables by recombining cropped patches of real
  tables ("Table Mix Expand"), 50k synthetic per dataset, and measures TME on/off: +0.1 to +1.1 S-TEDS on
  PubTabNet/FinTabNet across two models (Table 3; UniTable +0.8 and +1.1, InstructTable +0.1 and +0.7). The approach is the same: real parts, new layout.
- A 2025 policy-search follow-up (arXiv 2506.08956) reads [V] (full text via pwfetch 2026-11-14): copy-paste policy search with Fast AutoAugment on DOTA-v2.0 valid (three copy-paste modes: one object, several, all small objects; pasted objects may not overlap existing ones; paste count 1-3); +9% / +11% mAP over baseline in its two tables and +20% / +17% on small objects (0-32 px) - relative numbers, models and absolute APs not recorded here; aerial images, not drawings; no code seen.
- For us: our 104k real symbol boxes are the part bank. Paste real window, door, sink and toilet crops (with a few
  pixels of context) into ResPlan walls and bathrooms, and onto other real dev plans at free wall positions.
- Leak and licence: crops from dev-split images are allowed for local training (record 0003), but they are CubiCasa5K
  (CC BY-NC-SA) pixels, so a detector trained on them is NC-derived: local weights only, not shippable. For the
  commercial-safe set (record 0003, rule 4 and its consequences) the symbol bank must be our own drawn variants or crops
  from a source with a commercial licence; ResPlan has no fixture symbols. State this in the submission form. No
  pretrained checkpoint is involved.
- What breaks: COCO objects are photographed things; our symbols are line glyphs that touch walls, so the "no overlap
  with existing objects" rule would forbid pasting into a wall, which is where windows and doors live; rewrite the rule
  as "no overlap with another symbol", and rotate only by multiples of 90 degrees (arbitrary rotation resamples thin
  lines and creates artefacts at 5 to 20 px). Paste clutter too (see item 6 below) or the detector learns "symbols
  appear without clutter".
- JSON field: `elements`.
- Hours: about 2 (est.).

## 2. The full table

Columns: field (ours or the field it transfers from) | method | year, venue | code (licence read) | weights or data
(licence read) | what was measured, benchmark, metric | input size and compute | my hours-to-first-number estimate | JSON
field | leak flag | verdict. "none" means a repository exists but `gh api .../license` returns no licence.

| # | Field | Method | Year, venue | Code (licence) | Weights / data (licence) | Measured, benchmark, metric | Input, compute | Hours (est.) | JSON field | Leak | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Music scores | ScoreAug real-blank overlay + Finalise | TISMIR 2024 | raember/s2anet: none; mmrotate Apache-2.0 | DeepScoresV2 CC BY 4.0; paper CC BY 4.0; no weights seen | real scans AP@0.25: 36.0 -> 56.5 -> 73.7 | 1000 px half-res crops; 2000 epochs; GPU memory not given | 3-4 | elements | no | try |
| 2 | Music | domain-adversarial detector adaptation (same paper) | TISMIR 2024 | same | same | 36.0 -> 48.9, source 87.6 -> 72.4 | same, lower res | 6+ | elements | no | skip (fragile 3-step, below ScoreAug) |
| 3 | P&ID | SynthPID seeded generator | arXiv Apr 2026 | `LatentSpaceIITB/SynthPID` unreachable (404) | PID2Graph CC BY-SA 4.0 | edge mAP 63.8 synthetic-only, 72.6 mixed, 69.4 real-only | 1500 px tiles, stride 750; 4 x A6000, 150 epochs | 6-8 | elements, plans | no | try pattern |
| 4 | Industrial parts | pretrain -> fine-tune vs mix | arXiv 2211.16066 (2022) | DIMO_ObjectDetection: none | data on arXiv 2208.04052, licence unread | AP: mix 80.13, fine-tune 83.7 | Mask R-CNN R101; sizes not given | 3 | elements | no | try |
| 5 | Maps | procedural synthetic maps + real fine-tune | arXiv 2603.05037 (2026) | MMSegmentation (not read); no repo for configs | Zenodo release (data, splits, model) licence unread | mIoU 74.2 vs 69.1 without pretraining and 69.1 without real fine-tuning | 768 px; 150 h on a 12 GB Titan X (summary) | 3 | rooms (area classes) | no | maybe (segmentation, not detection) |
| 6 | Maps | learned vs hand-made degradation | arXiv 2511.15875 (2025) | hcu-cml/bootstrap-HistoricalMap: none (web viewer only) | test set Zenodo 17579452 CC BY 4.0 | accuracy 0.8716 CycleGAN, 0.8357 style only, 0.8125 blur+dust | 500 px patches; 8 GB card | 8+ | none | no | skip for tonight; cautionary |
| 7 | Scene text | UnionST engine + 1% real fine-tune | CVPR 2026 (per arXiv comment) | YesianRohn/UnionST: no LICENSE file; requirements read: imgaug, pillow 9.5 pinned, opencv, no GPL/AGPL package | HF model card UnionST-Models: MIT; HF dataset UnionST: MIT; STR-Synth: Apache-2.0 (cards read; MIT label on a repackaged third-party corpus is the uploader's claim) | synthetic-only 83.00 vs real 87.22; 1% real 87.26 | 8 x V100 (summary) | 6+ | rooms (labels) | no | maybe; text is L5's scope |
| 8 | Scene text | SynthTIGER / SynthText / TRDG as label-crop generators | 2021 / 2016 / 2018 | synthtiger MIT; SynthText Apache-2.0; TRDG MIT | fonts: check each | UnionST Table 4: SynthTIGER 57.87 vs ST-2D 73.36 vs UnionST 83.00 on the hard benchmark | CPU | 2 | rooms (labels) | no | maybe (label crops, pointer to L5) |
| 9 | Music | page concatenation + layout randomisation + Augraphy (Transcoda) | arXiv May 2026 | btrkeks/transcoda: **AGPL-3.0** | Zenodo/weights not stated; Augraphy MIT | real NED 63.97; w/o concatenation +14.34 | 1485 x 1050; 6 h RTX 5090 | 2 | plans, elements | no | try (idea only) |
| 10 | Small-object detection | copy-paste, no overlap, 2:1 original ratio | arXiv 1902.07296 (2019) | no code released | COCO | AP_small +1.2 (16.7 -> 17.9) | R50-FPN; 4 GPUs | 2 | elements | no | try |
| 11 | Tables | Table Mix Expand (real patches recombined) | arXiv Apr 2026 | Nevar07/InstructTable: none | not stated | S-TEDS +0.1 to +1.1 with TME | 960 px; 8 x A100 | 2 | elements (idea) | no | maybe (idea) |
| 12 | Document layout | Mesh-candidate BestFit synthetic layout pretraining | arXiv 2410.12628 (2024) | DocLayout-YOLO: **AGPL-3.0** (Ultralytics-based) | weights juliozhao/DocLayout-YOLO-DocStructBench card: Apache-2.0 (code and weights licences disagree; weights need the AGPL code to run); DocSynth-300K: no card found | pretrain +1.2 (D4LA), +2.6 (DocLayNet) mAP | 1600 px, 8 x A100 | 4 | plans/elements | no | maybe (idea only, AGPL) |
| 13 | Industrial detection | domain randomisation factors | arXiv 2506.07539 (2025) | SynMfg_Code: NOASSERTION | SIP15-OD: not stated | removing post-processing -6.4 mAP50, removing distractors -7.5 (robotics set) | YOLOv8 (AGPL) 720 px | 2 | elements | no | maybe |
| 14 | Line-drawing abstraction | common line-image space (AbSynth) | VISAPP 2024 | none linked | paper CC BY-NC-ND | T-LESS mAP 0.195 -> 0.695 | Faster R-CNN R50 | 4 | elements | no | maybe |
| 15 | Hand-drawn P&ID | Dataset-P&ID synthetic sheets | arXiv 2109.03794 (2021) | none | Google Drive, no licence; paper CC BY-NC-ND | real-sheet F1 0.93 to 0.99 per symbol, no sim-to-real analysis | 400 px patches | n/a | none | no | skip (no licence) |
| 16 | Historic maps | SynthMap text | GeoAI 2021 | repo: none | licences not stated | F1 60.62 synthetic-only vs 57.32 scene-text-pretrained | 256-512 px tiles | n/a | none | no | skip (no ablation) |
| 17 | Industrial pallets | synthetic mixing | arXiv 2510.12208 (2025) | repo: none | Zenodo 10.5281/zenodo.17308406 licence unread | real-only 0.795 AP; effects "modest" | 1536 x 1024; 190 GPU-h | n/a | none | no | skip (baseline expectation only) |
| 18 | Augmentation tool | Augraphy | 2022 | sparkfish/augraphy MIT | n/a | used inside item 9 | CPU | 1 | n/a | no | try (tool) |
| 19 | Circuits | SINA detect + VLM count concordance | arXiv Jan 2026 | anonymised link only | none | detector F1 96.47 on 75 schematics; concordance flag effect not measured | YOLOv11, size not given | n/a | none | no | skip (verification idea belongs to L10) |
| 20 | Rendering study | indirect lighting for sim-to-real | arXiv Jun 2026 | not read | not read | 3D photoreal; page read via headless browser | n/a | n/a | none | no | skip (not line art) |
| 21 | Sketch recognition | randomised edge detector and thresholder as shared input | arXiv 2202.13164 (2022) | NikosEfth/im2rbte (Apache-2.0, gh) | Im4Sketch (licence not read) | Sketchy 49.7 vs RGB 11.4; PACS 70.6 vs 58.5 | ResNet-101 | 2 | elements (input step) | no | maybe |
| 22 | Forms | Augraphy six-effect stack | arXiv 2502.06132 (2025) | none | none | handwritten mAP +0.040/+0.012/+0.037/-0.034; digital -0.018 to +0.001 | detectors on forms; 2 x RTX 4090 | 1 | none | no | maybe (tool; mixed evidence) |
| 23 | Camouflage detection | targeted vs random synthetic | arXiv 2610.09807 (Oct 2026) | none | none | targeted - random +0.0024 over 8 seeds, within noise | SINet-class | n/a | none | no | skip (cautionary) |
| 24 | Music | OSSQ-OMR benchmark (scan vs render) | ISMIR 2026 | MALerLab/string-quartet-omr-benchmark (no licence, gh 404) | licence not stated | NED 3.6 vs 5.9 (Zeus), 4.2 vs 10.4 (SMT) | from scratch | n/a | none | no | skip (benchmark) |
| 25 | Driving, infrared | BN-statistic and weak-label test-time adaptation | arXiv 2407.05607 (2024) | dzungdoan6/WSTTA (Apache-2.0, gh) | n/a | AP50 20.9 -> 34.5 -> 36.5 | Faster R-CNN R50 | 2 | elements (per-sheet) | no | maybe |
| 26 | Technical drawings (text) | generator with 150 real element crops + random labels | Procedia CIRP 2023, arXiv 2205.02659 | 2Obe/Text-Detection-on-Technical-Drawings: **MIT** | none released | 140/171 found (81.9%), 79.3% correct text vs 4.7% / 47.9% real-only | 2,000-7,000 generated pages, 1200-1500 px; GPU not stated | 3 | elements (label text) | no | try (idea; port the script) |
| 27 | Floor plans (emergency symbols) | real cutouts + pasted symbol images, <=12 per cutout | Sensors 2023 | none found | none | rare classes found about 50% vs 0; stairs overfit; no mAP in text | Faster R-CNN, 5,000 cutouts | 3 | elements | no | try (as row 5 support) |
| 28 | Chemical structures | style-augmented synthetic + patent images, exact match | arXiv 2205.14311 (2022) | thomas0809/MolScribe: **MIT** | HF checkpoint card MIT | OOD renderer 89.7 vs 72.1 w/o augmentation; synth+patent beats both | Swin-B, 1M + 680K images | 3 | n/a | no | context |
| 29 | Music manuscripts | Smashcima glyph-crop synthesis, replay mix | arXiv 2606.09479 (Jun 2026) | OMR-Research/Smashcima: **Apache-2.0** | data CC BY 4.0 (paper) | SER 33.2 with replay mix vs 41.3 real base fine-tuned | 3 days A40 base; 50 test systems | 3 | n/a | no | try (support for rows 3, 5) |
| 30 | Microscopy (counting, MAE) | style-transferred synthetic pretrain | arXiv 2512.11763 (Dec 2025) | code not read | not read | MAE 27.74 real-only; hard-coded synthetic +13.46; InST -1.49 | EfficientNet-B0, 95 real images | 2 | n/a | no | context |
| 31 | Microscopy (boxes) | diffusion images replace or add 10-50% | arXiv 2512.00078 (Nov 2025) | mario-dg/Diffusion-Based-Brightfield-Image-Generation (no licence, gh 404) | HF, not read | mAP50 0.8947 real-only vs 0.8952 add-30% | YOLOv8s/m, 5,000 real | 2 | n/a | no | skip |
| 32 | Industrial parts (3D) | domain randomisation + few-shot real | arXiv 2602.21141 (Feb 2026) | not resolved | not read | 0-shot 95.1 -> 10-shot 98.8 mAP50 | YOLO11m, 4,000 synthetic | 2 | n/a | no | context |

## 3. From other fields: the transfer notes

For each field: the task, what plays the role of our object, why it should transfer, what breaks on our images, and
whether code and weights are usable. Our images: symbols 5 to 20 px, exact-multiple rotations, Finnish short labels,
scans and photos, counts scored exact.

### 3.1 Optical music recognition (the best match)
- Task: detect and classify thousands of small symbols per page on line art. A DeepScores page averages 243 symbols
  (median 212) at 1894 x 2668 px, with objects "down to a few pixels" and a "unable to find any symbols" result for a
  plain Faster R-CNN with small anchors (arXiv 1804.00525, [V]).
- Role of our object: notehead or rest = window, door or sink glyph; staff lines = walls; a page of systems = a sheet
  of plans; a bar-line count = a plan count.
- Why it transfers: same visual statistics (thin black lines, filled glyphs, 5 to 20 px, strong class imbalance, ink on
  white), same sim-to-real situation (rendered training data, scanned test data), and recent measured numbers.
- What breaks: (a) their symbol set is rigid and rendered by a font, ours are drawn by many hands in CAD, so the
  symbol-bank gap is larger; (b) their real test sets are small (about 100 pages); (c) scores are never rotated by 90
  degrees, our sheets are; (d) a notehead has one meaning, a window glyph on a plan can be a door, a sliding door or a
  cupboard, and the context decides; (e) our labels are letters at 5 to 10 px, where music has none. Code: the S2A-Net
  fork has no licence; Transcoda is AGPL; Verovio is LGPL (usable unmodified, no use for plans). Weights: none usable
  for plans. Idea transfers (items 1 and 4 above), code does not.
- Forward citations (OpenAlex, 2026-11-14): of the 15 works citing the TISMIR paper, 2025-2026 items include an
  implicit layout-aware transformer for full-page OMR (IJMIR, Oct 2025), full-scale piano score recognition (Applied
  Sciences, Mar 2025), a document-recognition inductive-bias paper (IJDAR, Jul 2026) and "Can oriented bounding box
  enhance small object detection?" (ISCIT, Oct 2025). The document-recognition one is by the ScoreAug authors, posted Jul 2025
  (arXiv 2507.08458, v2 Apr 2026): a ViT-encoder transformer transcribes simplified engineering drawings (synthetic
  L-shapes with dimensions, 140 x 140 px) into graphs, 74.8% correct within 4 px on 1,000 synthetic drawings, with
  random 90 degree rotations, line thickness and blur in its generator; no real scans, no code, GPU and time not
  stated; text re-read verbatim 2026-11-14 via pwfetch [V]: generator rotations are exact multiples of 90 deg plus mirroring and translation, 748 of 1,000 test shapes correct, and its limitations section says all experiments are synthetic and simplified. It is a structured-record idea (drawing to graph), not
  a counting result. I did not open the other three: the first two are sequence models, the
  OBB paper is about arbitrary rotation, which our exact-multiple rotation does not need.

### 3.2 P&ID and engineering diagrams
- Task: symbols and pipes on large sheets; same sparse line art, small symbols (8 px), mixed real and synthetic data.
- Role of our object: valve = symbol; pipe graph = wall graph; "instrument tag" text = room label.
- Why: SynthPID is the only 2026 paper found that measures a synthetic-only result against real-only and a mixed result
  on line-drawn technical sheets, with a tiling rule for tiny symbols.
- What breaks: the real test set is 12 sheets from one open reactor design; the paper reports no scan degradation; the
  detector (Relationformer, 401 queries per tile) is a transformer built for graphs, heavier than we need; the seed-leak
  question above. Digitize-PID (arXiv 2109.03794, [V]) gives the 500-sheet synthetic set with unparameterised
  "pixelation, blurring, salt and pepper" and no sim-to-real analysis, and its data has no licence, so it is out.
- Forward citations (OpenAlex): from Digitize-PID 2025-2026 there are at least twenty works (DPGT dense graph
  reconstruction, Electronics Oct 2026; a P&ID-to-DEXPI vision-language agent, ETFA Sep 2026; a production-deployed
  scanned-P&ID pipeline, ADIPEC Nov 2026; others). I opened none beyond the title; their licence and measured counts
  are unread. A one-line pointer for L12 (market) and L10: the ADIPEC and ETFA titles describe deployed inventory
  extraction.

### 3.3 Scene text and document OCR (synthetic engines)
- Task: recognise short strings; trained mostly on rendered data; real test sets reveal the gap.
- Role of our object: a room label ("MH", "K", "WC") at 5 to 10 px is a short word in a small crop.
- What the numbers say [V, arXiv 2602.06450]: older engines trained alone score 31.5 (MJSynth), 57.9 (SynthTIGER), 73.4
  (ST-2D, 36M images) on the hard real benchmark against 87.2 for real-only; the new engine reaches 83.0 with 5M images
  and the data is as much about missing axes as quantity. At 0.5M images, dropping one engine component from the full
  72.06 costs 0.4 to 15.2 points; the two rows where the curved and multi-oriented columns collapse (50.00 and 34.26)
  are the rows that miss a layout component (the extracted table lost its empty cells, so I cannot name the removed
  component for each row).
- What breaks: our labels are closed-vocabulary codes of one to three letters, so the corpus is a short list, not
  English; the question is whether glyphs survive down-sampling to 5 px, which no paper here measures (the earlier
  report found glyphs under 6 px lost even after Lanczos 2x). The label recogniser is L5's scope; this report only
  says the generators are permissive (SynthTIGER MIT, TRDG MIT, SynthText Apache-2.0, all read) and UnionST's code has
  no licence file.
- Weights: UnionST model card is MIT and its datasets MIT (HF cards read); leakage flag: no (text data, not CubiCasa5K). The
  repo has no LICENSE file, so the code itself is unlicensed, but the generator's dependencies are permissive.

### 3.4 Historical maps
- Task: segment or detect map features and symbols from scans, trained on rendered vector data in a target style.
- Role of our object: a map point sign (church, bridge) is our symbol; a map frame and graticule is our sheet border and
  title block; a historical map series is our style mix.
- What the numbers say [V]: SynthMap (2021): synthetic-only F1 60.62 vs 57.32 for a scene-text detector pretrained on
  photos, and 64.25 with both (workshop paper, 31 test maps, no ablation of the randomisations, no real map training
  data in any arm). Semap (2026): see item 3 above. Arzoumanidis (Nov 2025): learned degradation beats hand-made
  (above), 4 datasets of 2,269 pairs each, test set 125 patches, no real-trained arm; the "12.3% mIoU gain" quoted by
  one search summary is not in the paper (I read the abstract, Sections 3 to 6 and the tables).
- What breaks: all three tune to a map style by fitting colours and textures to a known corpus; ours has no such corpus
  (the Stoa style mix is a few CAD and scan families, with partner-owned originals we may not copy). The map work
  segments areas, not counts of 5 px symbols. CaSiDD, a class-agnostic point-sign benchmark (Zenodo
  10.5281/zenodo.16278380; Zenodo record read 2026-11-14 [V]: 796 annotated historical map samples, 18,750 signs, 24 classes, COCO format, licence CC BY 4.0, images from Semap), is the closest map dataset to our symbols; I could
  not read its paper (thesis only: arXiv 2511.19538 abstract, a 396-page PDF).
- Code: none usable (two repositories without a licence file).

### 3.5 Industrial detection and domain randomisation
- Task: detect parts after training on rendered images.
- Role: a machine part on a clutter background = a symbol on a plan with furniture, dimension lines and text.
- What the numbers say [V, arXiv 2506.07539, Table V]: removing post-processing (noise and blur at 10% probability) costs
  6.4 mAP50 on the robotics set and 2.1 on one industrial set; removing distractors costs 7.5 and 4.0; on a third set
  neither matters. Path-traced rendering beats rasterised by 1 to 7 points (Table IV). Lighting randomisation beat pose
  randomisation in 2211.16066. One real image on top of synthetic-only takes the robotics set from 96.4 to 97.5.
- What breaks: these are 3D scenes with photographic lighting; our nearest "distractors" are text, dimension lines,
  hatching, furniture symbols and a title block. These papers give no small-object numbers. Their detector (YOLOv8) is
  AGPL; Faster R-CNN or Apache detectors from the other workers' lists apply instead.
- Forward citations (OpenAlex from W4413925713): twelve works 2025-2026; I opened the June 2026 lighting study (arXiv
  2606.22574, read via the headless browser, skipped as not line art) and listed the rest: a gear defect study (ETFA Sep
  2026), a ship-detection simulation study, test-time adaptation of synthetic-trained detectors (Machine Vision and
  Applications, Jun 2026), assembly inspection with domain randomisation (ICCV Workshops 2025). Unread.

### 3.6 Tables and document layout
- Task: structure of tables and pages; synthetic data is standard.
- Role: a table cell = a plan cell on a sheet; a page layout = our sheet layout (several plans plus a title block).
- Numbers [V]: DocLayout-YOLO synthetic pretraining +1.2 mAP on D4LA and +2.6 on DocLayNet, with Table 4 giving
  per-source comparisons (random layouts, diffusion layouts, PubLayNet, DocBank), where "BestFit" layout generation
  beats random layout generation by 1.6, 0.3, 1.2 and 0.7 mAP on the academic, textbook, market and financial subsets; no per-class or small-element
  result is reported. InstructTable: TME on/off +0.8 to +1.1 S-TEDS.
- What breaks: element sizes are text blocks, not 5 px glyphs; the strongest code (DocLayout-YOLO) is AGPL, so only the
  layout-sampling idea is usable; InstructTable's text generator is GPT-4o, a paid API we may not call.

### 3.7 Not found as a transfer with usable numbers
- Charts, PCB components, circuit schematics and robotics randomisation: PCB sim-to-real component detection with small
  objects returned only older GAN-augmentation work and a 2024 X-ray segmentation paper, no component-detection
  ablation; the 2021 hand-drawn circuit paper (arXiv 2106.11559) body was read: real images only, rotation and flip, no degradation generator; SINA
  (arXiv 2601.22114) reports a detector F1 96.47 on 75 mixed schematics and a VLM concordance flag with no measured
  effect and no licence.

### 3.7a A person checking the machine's marks (test-time adaptation with operator labels)
- Field and task: detector adaptation at deployment when an operator confirms which classes are in each image (Doan et
  al., arXiv 2407.05607, Jul 2024, [V] through Section 4.1 and Table 2; later sections from a summary). Faster R-CNN
  ResNet-50; the operator gives only image-level class presence, no counts or boxes; 100 labelled target images; all
  batch-norm statistics and affine parameters updated per image, source data not needed.
- Numbers [V, Table 2, AP50 mean]: clear-to-fog driving 20.9 source-only, 34.5 BN statistics only, 34.8 prior TTA, 36.5
  with weak labels; real-to-real 40.8 to 44.6; visible-to-infrared (synthetic set) 30.5 to 37.4. No synthetic-to-real
  pair, no operator time, no small-object result, no code licence read (repository linked, not opened).
- For us: an adaptation step that needs presence labels cannot run in scored mode (no labels at answer time); it
  would only fit a product loop where the user confirms "this sheet has a sauna". The part that needs no labels, batch-norm
  statistic adaptation, is already worth most of the gain (20.9 to 34.5 on the fog shift) and is a cheap per-sheet
  trick for the style mix; it requires a detector with batch-norm layers (Faster R-CNN does, transformer detectors
  mostly do not). Verdict: maybe for BN-statistics adaptation; skip the operator part for scoring. Pointer for L10.

### 3.7b Negative and cautionary results (2026), and a leakage lesson for us
- **Targeted synthetic data does not beat random synthetic data** (Dobhal and Singh, arXiv 2610.09807, 7 Oct 2026,
  unreviewed preprint, 103 training runs, [V] for the abstract through Section 3.1, and the +0.0050 and +0.0024 gaps re-seen in Table 2 on 2026-11-14; the 0.28 and 0.34 bar fractions not re-checked): on
  camouflaged-object detection, adding 1,000 renders chosen by an uncertainty-targeting rule scored +0.0050 (3 seeds) and
  +0.0024 (8 seeds) over 1,000 random renders, both inside the noise bar (0.28 and 0.34 of the bar); the authors'
  conclusion is that how many images you add and how concentrated they are decides the effect, not the selection
  rule. For us: do not spend the night on clever sampling of synthetic scenes; render broadly and use the time to fine-tune
  on real boxes. Caveat: one generator (background repainting), a different image type, no code or licence given.
- **Their evaluation set was contaminated by altered copies of training images** (same paper, abstract and the
  contamination appendix re-read via pwfetch on 2026-11-14 [V]): 50 of 76 test images (65.8%) of the CHAMELEON benchmark are
  the same photographs as images in COD10K-train and CAMO training pools, re-encoded, rescaled or cropped (44 of them with
  their partner in the public COD10K-train split), while exact hashing reports 0 overlap. This is our leakage
  problem in miniature: 829 of 959 eval drawings are in CubiCasa5K's train split, and any check that looks only for
  byte-identical files will miss re-encoded or mirrored copies (the context file says mirrored copies exist in our own
  images). Use a perceptual hash with rotation and mirror variants when deduplicating any external set against the dev
  and eval images, as the earlier report's recommendation 5 already says.
- **Rendered-versus-scanned test gap depends on the model** (Kim et al., arXiv 2608.10978, ISMIR 2026, Aug 2026,
  [V] for Sections 1 to 5): on the string-quartet benchmark, OMR error rises from synthetic to scanned test pages for all
  34 configurations; with the same data the LSTM-based Zeus goes from 3.6 to 5.9 (part level, LMXE) while the
  transformer SMT goes from 4.2 to 10.4. No experiment trains on synthetic versus scanned data; all models are trained
  from scratch on a mix whose proportions the paper does not state; dataset licence is not stated. Reading: a bigger
  gap in the transformer than the recurrent model on identical data, so the detector choice and the synthetic data
  interact; compare detectors on a real dev subset, not on synthetic validation.
- **Synthetic plus very little real in a different field** (SynSpill, arXiv 2508.10171, Aug 2025, [V] through Section
  7): 2,000 diffusion-generated images plus 100 real ones, fine-tuned detectors reach mAP@50 0.81 (YOLOv11) and 0.83
  (RF-DETR) on a public set but 0.64 and 0.67 on the proprietary set; the authors say models "generalize locally but not
  structurally", and there is no real-only or mixing arm. It fits the 12-sheet P&ID result: a handful of real images
  closes most of the gap, then style shift reappears on the next customer's drawings.
- **Vision-language models as a reviewer on structural framing plans** (arXiv 2608.17237, Aug 2026): training-free
  pipeline, column recall 0.922 and precision 0.997, beam recall 0.886 and precision 0.990 on 50 held-out generated vector
  drawings (up to 85 beams), no tiny-symbol result and no exact-count metric; code and data not released. One line for
  L7 and L10 (vision-language scope): this is a deterministic-rules-plus-reviewer pattern on vector input, not raster.

Floor-plan-specific items I did not open (they belong to the other orchestrator's and the sibling workers' scopes):
arXiv 2607.06483 (synthetic pretraining for conditioned floor plan generation, Jul 2026), "Why floor plan object
detection breaks under real scans: a controlled study of robustness limits" (Automation in Construction, Aug 2026,
open-access PDF listed by OpenAlex), arXiv 2607.18997 (AEC drawing layout detection benchmark, Jul 2026), "FloorYOLO"
(Frontiers in AI, Sep 2026). The robustness study is the closest thing to the missing "augmented vs not on real
scans" number for plans: whoever holds L1 or L9 should read it before the build.

### 3.8 Normalise the stroke before training: edge maps as the shared input (sketch recognition, AbSynth)
- Field and task: recognising sketches after training only on photographs, by turning every image into a binary edge
  map so training and test inputs look alike (Efthymiadis, Tolias and Chum, arXiv 2202.13164, 2022, [V] through the
  method and Table III; later sections from a summary).
- What plays the role of our object: a scanned plan, a CAD render and a photograph of a printout are our "photo, sketch
  and cartoon"; the shared representation would be a thinned binary line image.
- Numbers [V, Table III, Sketchy, ResNet-101, mean of 5 runs, accuracy single-scale]: RGB baseline 11.4; HED edges with a
  fixed threshold 39.1; plus geometric augmentation 47.0; random choice among five thresholders 47.9; random choice among
  three edge detectors as well 49.7; no thinning (no non-maximum suppression) 5.9; no binarisation 40.2. Randomising the
  detector and thresholder adds 0.9 and 1.8 points on top of a fixed one, close to the 0.3 to 1.5 standard deviations;
  geometric augmentation adds 7.9. Domain-generalisation benchmark (PACS photo to sketch): 70.6 against 58.5 for the best
  generic method (the claimed "20%" is 20.7% by my arithmetic).
- Companion evidence [V, AbSynth, VISAPP 2024, Table 2, Faster R-CNN ResNet-50 on textureless parts]: training on
  line-image renderings of the synthetic set raised mAP on T-LESS from 0.195 to 0.695 and on ITODD from 0.618 to 0.849
  (the table's column layout was garbled by text extraction, so the best "Anime plus OS" style is my reading); the
  authors' own explanation is that for textureless objects the geometry is the only usable feature.
- What breaks: our inputs are already line art, so the gain from edge conversion is smaller than from photographs; the
  real risk is the opposite one, that thin 1 px strokes vanish at 5 to 20 px symbol size (the NMS-removed row shows
  thickness handling decides everything: 5.9). A fixed-width thinning plus dilation step before the detector would
  make scan blur, line weight and anti-aliasing less important, but it removes grey-level cues (hatching, filled
  walls) that the scan carries, and no paper tests it for counting. Verdict: maybe, as an input-normalisation
  experiment (about 2 h: skeletonise the dev images, dilate to 2 px, train once, compare on dev), not as a replacement
  for the real-scan overlay.

### 3.9 Scan-style augmentation is not free on clean data
- Dai, arXiv 2502.06132 (Feb 2025, [V]): six Augraphy effects (InkBleed, Letterpress, two low-ink effects, JPEG,
  DirtyScreen) applied with 70% probability plus up to 5 degrees of rotation, five augmented copies per document, trained
  on digital forms and tested on digital and handwritten forms. mAP: handwritten test improves for three of four models
  (+0.040 ResNet-101 Faster R-CNN, +0.012 DiT, +0.037 LayoutLMv3) and falls for one (-0.034 ResNet-101 Mask R-CNN); the
  clean digital test falls for three of four (-0.018, -0.006, -0.003) and is flat for DiT (+0.001). One run per cell, no
  parameters given, no code. The same shape appears in the music paper (clean AP 87.6 to 83.3). Reading for us: keep the
  augmented and clean mixture, report both a clean dev slice and the degraded slice, and judge by the count metric on each.
- arXiv 2403.11291 (Mar 2024) read in full via PDF [V]: machine-drawing digitisation (YOLOv7 for the drawing region, Canny/Hough for lines, OCR for text) on a custom set of 200 annotated diagrams; no synthetic data, no ablation, and no mAP figure in the text. Not a symbol-detection or data study; the 'YOLO 79 / Faster R-CNN 83 mAP' numbers I had noted earlier belong to the next entry, not to this paper.

### 3.10 Counting trained on synthetic data (crowds, fruit, mixed objects): what exactness costs
- Field and task: class-agnostic and crowd counting where training counts come from generated or rendered images. The
  nearest "exact count from synthetic" evidence I found; all report mean error, none reports exact-match, one reports
  "within 10%".
- **Rendered counts are exact, diffusion counts are not** (D'Alessandro et al., AFreeCA, arXiv 2403.04943, Aug 2024 v2,
  [V] full text): images generated by Stable Diffusion 2.1 from prompts such as "a group of N people" were counted by
  hand, 40 per prompt. Relative error against the prompt number is 0.07 at N=1, 0.18 at 5, 0.26 at 10, 0.32 at 15,
  0.45 at 20 and 0.61 at 40 (Table 7). Our counts are 2 to 20, so a generated plan would already be wrong in 20 to 45%
  of its labels. The paper trains only on ordinal and prompt-count labels and reaches MAE 35.0 on a crowd benchmark; no
  real-only or mixed arm; code link in the abstract, not opened. Verdict for us: do not use diffusion for labelled
  symbol data; render from vectors, where the count is known by construction.
- **Mixing a little rendered data into real data helps a strong counter** (MixCount, Dumery et al., arXiv 2605.18063,
  18 May 2026; Tables 2 and 3 headline rows re-checked in the full page text, generator ranges read in the appendix text on 2026-11-14:
  30-200 objects, 2-4 classes, 2-8 distractors, elevation 20-80 degrees, all [V]): 58,000 Blender
  scenes (30 to 200 objects of 2 to 4 classes, rigid-body settling so objects touch and occlude, 2 to 8 distractors,
  camera elevation 20 to 80 degrees), visible-object counts. Adding 1,000 of them to the real set lowers the counting
  model's FSC-147 MAE from 5.86 to 4.68, and on their own benchmark raises the share of images within 10% error from 0.33
  to 0.69 (all four prompt types) and unchanged at 0.09 with text prompts only (mean error falls from 26.77 to 14.63). No generator-factor ablation, no real-only
  baseline at the same budget, no exact count. Dataset CC BY-SA but several assets are research-only or no-product
  (Digital Twin Catalog "bars selling them or building them into products", LavalIndoor research use): not commercial
  safe as a whole; no code repository found.
- **Placement distribution and shape variation mattered more than realism** (Moreu et al., Domain Randomization for
  Object Counting, arXiv 2202.08670, Feb 2022, [V] full text): low-poly objects under 200 faces rendered in Blender
  with random textures and backgrounds; clustered placement (Gaussian mixture) gives MAE 23.2 against 63.4 for uniform
  placement on one crowd benchmark; random vertex displacement (40%) plus extrusion gives the best result on all five
  test sets (Table 4: 158.7 vs 184.0 and 23.2 vs 29.2 against scaling alone). Synthetic-only is still 1.8 to 3.6 times
  the error of real-trained methods (Table 2: 23.2 vs 6.5, 14.6 vs 5.8, 13.6 vs 4.2, 158.7 vs 57.0).
- For us: put symbols where they occur (windows in outer walls, doors between rooms, sinks along bathroom or kitchen
  walls), not uniformly, and cluster them as real plans do; mix a bounded amount of synthetic data into real training
  rather than training on it alone; and score the exact count and a within-one count separately, since every paper
  here measures only a tolerance.
- What breaks: these counters regress a density or a count over whole images; ours will count detections after
  thresholding, so duplicate and missed boxes, not regression bias, decide exactness. No paper here tests that. Their
  objects are 20 to several hundred px (MixCount object size is 4.5 to 12% of the scene, so about 45 to 120 px on 1024), far
  above 5 to 20 px.

### 3.11 Tool check: Augraphy and boxes (repo and issues read, 2026-11-14)
- sparkfish/augraphy is MIT; last push 2025-07-20, 593 stars, 22 open issues, no tagged release listed by the API. The
  README says pixel-level effects (ink, paper, scanner) do not touch masks, keypoints or boxes, and spatial effects
  transform them. Open issue #437 (Jul 2024, "Skewed bounding boxes"): after rotation or folding the boxes are moved by
  their start and end points only and are not re-fitted around the rotated object; the maintainers called this
  documented behaviour. Closed issues #445, #446 and #448 fixed crashes of `OneOf` and the augmentation sequence with
  boxes. Open issue #455 (Oct 2025) reports a numba type error in the Worley noise generator.
- Consequence for us: use Augraphy for pixel-level effects only (ink bleed, paper texture, low ink, scanner noise,
  JPEG), which cannot move a 5 to 20 px symbol box, and do rotation by 90 or 180 degrees and any scaling ourselves, where
  the box arithmetic is exact. Fine rotation in Augraphy would shift boxes of tiny symbols by a few pixels, which is
  more than a symbol's width.

### 3.12 Counter-evidence, two more fields (PCB inspection, historical diagrams), and round-6 additions (floor-plan symbol overlay, real-crop text generator, tiling, resolution)
- **Synthetic pretraining adds nothing when real data is plentiful, and the gap on tiny objects is large** (Messai et
  al., arXiv 2605.26884, 26 May 2026, [V] Tables II to VIII; industrial recycling, objects 0.01% of a 2448 x 2048 image,
  12 per image on average, up to 986; code github.com/o-messai/SDOOD (no licence, gh 404), paper CC BY-NC-ND, dataset licence not
  stated): YOLOv8x at 2048 px, real-only 69.1 mAP@0.5; trained on about 50,000 Blender images and tested on the real
  test set 39.9 and 41.1 (a 28 point gap); synthetic pretraining followed by real fine-tuning on 8,378 real images:
  69.0 against 69.2 real-only (per class: deformed 56.7 to 54.8, smashed 67.6 to 68.9, spring 5.2 to 4.6). No mixing
  ratio, no generator ablation (the paper lists none of the generator's randomisations), no exact count. Reading for us:
  our real set is 3.8k images and 104k boxes, similar in size to the 8.4k images and 55.8k test instances here, so the
  big synthetic gains seen in 1,000-image or 160-image regimes (maps, pallets, P&ID) are not what to expect on windows
  and doors; the best case for synthetic data is the rare classes (bathtub 312, sauna stove 2.5k boxes) and the
  commercial-safe weights question, not the dev score. The same paper reports resolution as the biggest single lever:
  YOLOv8x 60.8 (640) to 65.4 (1280) to 69.1 (2048) mAP@0.5 on real-only training.
- **Train at the scale you infer at, tile with overlap, and merge across tile borders** (PCB defect detection,
  arXiv 2605.24726, 23 May 2026; full PDF read 2026-11-14 [V]: defects are 80 px natively, 8-32 px after the
  usual downscale; tiles 640 px, stride 512; training tiles keep a clipped box only if enough of it is visible and keep
  empty tiles as background (33.6% / 26.7% positive); full-image-trained model 0.70 -> 0.01 mAP@50 on native tiles): a detector trained on full downscaled boards scores 0.01 mAP@50 under tile inference, the same detector
  trained on 640 px tile crops 0.72 and 0.94 on two PCB sets (230 and 693 images); 128 px tile overlap raises boundary-zone
  recall from about 26-63% to 70-100%; a training-free tile-adjacency merge ("topology-aware tile merging") gave the best
  mAP@50 on both sets. For us this is the double-count risk in plain form: a window cut by a tile border is two boxes
  and an exact-count error. It agrees with SynthPID (1500 px tiles, 750 px stride) and with SAHI in the earlier report.
- **Synthetic-only training can generalise to real hand-made line drawings when the generator is crude but varied**
  (Kalleli et al., arXiv 2403.08721, Mar 2024, [V] full text): historical astronomical diagrams, lines, circles and
  arcs; trained only on diagrams generated on the fly (random widths, opacity and colours, blur, structured noise,
  chipping, docExtractor backgrounds and fonts, random 90 degree rotations in training), 12 epochs of 2,000 steps at batch
  4, about 12 h on one A6000, tested on 303 real diagrams with 3,076 primitives: AP 0.764 lines, 0.917 circles, 0.483
  arcs, mAP 0.722 (point-distance threshold 4 px at 128 px). No generator ablation, no real data in training, no
  generator ranges, code "available after publication", no licence. The model is a transformer query detector and the
  metric is geometric, not a count. It shows that "not realistic but challenging" synthetic line art can be enough for
  primitives, and it names the mechanism we need: random 90 degree rotations were part of its training augmentation.
- Chart and diagram-to-code gaps I probed but did not open: arXiv 2508.06492 (synthetic charts, MLLM fine-tuning) and
  PCBnet (arXiv 2608.27923, schematic-to-netlist dataset, Aug 2026): both outside the symbol-detection question.

- **DeepScoresV2 ICPR paper read in full [V]** (2020, 400 DPI rendering): the authors state models trained on the clean synthetic set do best on very clean scans, and that AP0.5/mAP misjudge very small objects (stems). Same conclusion for us: add real-scan noise (top 1) and score exact counts, not mAP only.

- **Few real images close most of a synthetic gap; volume saturates early** (SynthRender / I-AsSET, arXiv 2602.21141, Feb 2026, read via pwfetch, text [V], figures not read): 3D industrial parts rendered with Blender, YOLO11m; synthetic set size 200-3200 shows diminishing returns (4000 chosen, +0.3 mAP50 for the last step); 0-shot 95.1 -> 10-shot 98.8 mAP50, and 5 real images bridge most of it. Breaks on our images: lighting and physics randomisation (the biggest factors there) do not exist in flat drawings; code licence not resolved. Use: keep the fine-tune stage on real labelled pages (top 3) and do not scale synthetic count past the low thousands.

- **Copy-paste recipe details (small drones, arXiv 2504.19347, IJCNN 2025, read [V])**: patches with transparent background, per-patch blur / pixel dropout / noise / brightness-contrast-gamma, random scale in a preset range, overlap check against existing boxes and a colour-difference (deltaE) check before insertion. The paper reports no copy-paste-only ablation, so it supports the recipe for top-5 row 5 but gives no number; the only paste-count evidence stays Kisantal (up to about 3 pastes per object). Breaks on ours: scanned line drawings have no colour, so replace the deltaE check by a stroke-width / ink-density match and paste only on blank wall-free regions or on real pages' blank margins.

- **Overlay symbol images on real plan cutouts to fix rare classes** (Hassaan et al., Sensors 2023, 23, 8344, CC BY 4.0, full text read via the TUM PDF 2026-11-14 [V]; a floor-plan paper, so this is the nearest neighbour to our task and I give it as a pointer plus the recipe): 403 real German emergency plans (mostly photographs); 200 of them cut into 25 cutouts each (16 plus 9 shifted), high-resolution symbol images pasted at random places without box overlap (up to 100 tries), at most 12 symbols per cutout (count topped up to 12 minus the real count), each symbol resized to the mean size of the real symbols in the cutout and Gaussian-blurred (5x5 kernel, strength estimated by a Laplacian on the cutout) before pasting; about 5,000 images; Faster R-CNN. Result [V, qualitative only: counts per class in figures, no mAP given in the text]: equal on common classes (more than 300 instances), about 50% of two rare classes found where the real-only model found none, direction arrows on a coloured background 16 of 17 vs 4 of 17; the stairs symbol got worse (overfitting to the pasted glyph, false detections on other symbols), the lowest class IoU. For us: this is top-5 row 5 done on floor plans, with its failure mode named - a simple pasted glyph becomes the shortcut, so paste several real crops per class and keep the real-only model as the comparison. Breaks on our images: coloured arrow backgrounds do not exist in our scans; the symbols there were large, ours are 5-20 px, where the blur/resize step changes the glyph itself; no code or licence for code found, paper text only.

- **Construction-diagram symbol detection, patch training recipe** (Jamieson et al., IJDAR 2025, 28:71-84, CC BY 4.0, full PDF read 2026-11-14 [V]; detection scope, pointer plus the data facts): 168 training diagrams cut into 640 x 640 patches gave 59,136 patches, only 1,633 with a symbol; empty patches were added in a 1:1 ratio to labelled ones, and the empty ones were picked from patches with more than 15% black pixels (cluttered, to cut false positives on look-alike shapes). Test: mAP@0.5 79% (YOLOv7) and 83% (Faster R-CNN), 637 and 636 of 665 symbols found (95.8%, 95.6%) - one test set, no repeats. The authors name class imbalance and propose synthetic patches (GAN) only as future work. For us: hard-negative empty tiles at a fixed ratio is a cheap recipe step that no synthetic generator is needed for; the exact-count view (about 4% of symbols missed at mAP 79-83) is a reminder that mAP and counts differ.

- **Resolution beats clever augmentation for tiny objects** (Lazarou-Yoo-Stathaki, arXiv 2509.17078 v2, 2025, aerial DOTA, YOLOv8n-obb, 50-epoch trials; text and Tables 2 read via pwfetch 2026-11-14 [V]): input size 640 / 800 / 928 gives AP50 0.621 / 0.665 / 0.696 and AP 0.436 / 0.489 / 0.525 (so +21% relative AP from resolution alone), while 'mild' augmentation packages added +11% and heavy rotation / colour augmentation did not help. It cites Kisantal's copy-paste but does not test it. Same direction as the PCB and DeepScores items above and as the earlier 640 / 1280 / 2048 result (2605.26884): feed the detector the symbol at a size where it is more than a few pixels, then spend synthetic effort. Breaks on ours: aerial colour images, one run each.

- **Floor-plan furniture with random rotation, scale and 10,000 synthetic images - but never tested on a real scan** (Mishra et al., Appl. Sci. 2021, 11, 11174, open access, full text read via the DFKI PDF 2026-11-14 [V]; pointer, floor-plan scope): SFPI re-places furniture in the 10 layouts of SESYD with random rotations (14 angles, not only multiples of 90), random scaling and 1,000 images per layout; a deformable-convolution detector reaches mAP 0.982 on SESYD and 0.995 on SFPI, i.e. synthetic-to-synthetic. The paper claims 'realistic images' as the aim, but I found no test on photographs or scans, so it is no evidence for real transfer and its mAP numbers must not be compared with ours. Same lesson as DeepScoresV2: a synthetic benchmark saturates and says little about scans.

- **Generator seeded with crops from a handful of real drawings beats training on those drawings** (Schlagenhauf, Netzer, Hillinger, Procedia CIRP 2023, arXiv 2205.02659, full PDF read 2026-11-14 [V]; code github 2Obe/Text-Detection-on-Technical-Drawings, MIT (LICENSE file via gh API), three small generator scripts using Pillow / OpenCV / NumPy that write JPG plus PASCAL VOC XML, last pushed Apr 2022, one open issue; I read Generator_image_type_2.py: it pastes 130-150 element crops at random positions on a 1200-1500 px page, and it has an off-by-one in the element index (randint(0, len) can index past the end), so port the idea, not the file; technical drawings, text instead of symbols, so a sideways transfer for our labels): image type 1 is blank backgrounds with geometry and dimension / tolerance labels in random places and size (0-300 px), with random sharpness / contrast / brightness; type 2 pastes 150 real elements (bearings, drillings, hatchings) cut from 9 real drawings in random number and place, then 40 labels per image horizontal or vertical; a separate 50 x 35 px recogniser set of 2-4 random characters. Detector sets: 2,000 / 5,000 / 7,000 generated images versus the 9 real drawings; validated on 9 other real drawings (no split of generated data needed). mAP@0.5 curves read from a figure only: real-only model far behind, 2,000 worst, 5,000 and 7,000 similar (diminishing returns). Table 1 on 171 real labels [V]: generator-trained 140 found (81.9%), correct text 79.3% (1 - CER); real-drawings-trained 8 found (4.7%), 47.9%; off-the-shelf Keras-OCR 132 found (77.2%), 46.8%. Breaks on ours: 9 + 9 drawings is a tiny validation set; text only, no 5-20 px symbols; the model, GPU and time are not clearly stated in the part I read; and our labels are Finnish 2-letter codes, not digits and tolerance signs. Use: for labels, crop real label images and paste them with a generator, then check the exact-count metric on held-out pages (top 1 and top 3).

- **Pointer, not read** (**[reported]**, search snippets 2026-11-14; the UCL conference PDF returned 403): Schoenfelder, Stebel, Andreou and Koenig, Automation in Construction 2024, text detection and recognition on floor plans with a synthetic-data pipeline 'to mimic real data' and public text annotations; YOLOv7 up to 97.5 wmAP, PARSeq 85.2 (the snippet calls it CER, which is probably a character accuracy). It is the closest paper to our Finnish 2-letter labels on floor plans; whoever owns the text scope should open it. Not counted in the source total.

- **Chemical structure images: the same shape as ours, with an exact-match metric** (MolScribe, Qian et al., arXiv 2205.14311, 2022 - older than the 2025-26 target, full PDF read 2026-11-14 [V]): line drawings, small atom labels such as 'Cl' and 'Br' (two-letter labels), synthetic images rendered from 1M PubChem molecules plus 680K USPTO patent images, scored by exact structure match only. [V] Table 3 (200K synthetic images only): without image augmentation the in-domain score is 91.4 vs 95.9, but on a different renderer (ChemDraw, out-of-domain) 72.1 vs 89.7 - augmentation of drawing style (font, bond width and length, rotation, padding, crop, noise) is what carries over to a second renderer. [V] Fig. 6 table: synthetic only / synthetic + patent / patent only, e.g. USPTO 68.0 / 90.4 / 86.3, Staker 55.0 / 85.4 / 81.5, JPO 52.7 / 69.1 / 10.0, ACS 61.0 / 69.5 / 11.5, i.e. real patent images alone fail on other domains and the synthetic set rescues them, while the mix beats both. For us: it is the one case I found with an exact-match metric, and it says to vary the renderer's style parameters hard (our second 'renderer' is a different CAD firm's drawing style) and to keep real pages in the mix as the in-domain anchor. Code github.com/thomas0809/MolScribe MIT (gh licence API), checkpoint on Hugging Face (model card licence: MIT, read), data PubChem and USPTO (public sources; I did not check their terms for reuse). Breaks on ours: the target is a molecule graph (atoms and bonds), not a count of repeated symbols on a large page, and the images are single small figures, not scans of whole drawings.

- **A clean replace-versus-add sweep with 5,000 real images: synthetic cells added nothing at mAP50 and cost a little at strict IoU** (diffusion-generated brightfield microscopy for single-cell detection, arXiv 2512.00078, Nov 2025, CC BY 4.0, text and Table 1 read via pwfetch 2026-11-14 [V]; code github mario-dg/Diffusion-Based-Brightfield-Image-Generation, no licence (gh 404)): 5,000 real training images, fixed 2,527 validation and 16,758 test images; 10 / 30 / 50% of the real images replaced by synthetic, or the same shares added on top. YOLOv8s mAP50 / mAP75 / mAP50:95: real-only 0.8947 / 0.8095 / 0.6557; replace 50% 0.8932 / 0.7891 / 0.6325; add 30% 0.8952 / 0.8115 / 0.6536; add 50% 0.8940 / 0.8100 / 0.6514 (single runs per cell; the paper reports differences under 2% for replacement and up to 5% loss for RT-DETR at add-50). Eleven experts could not tell synthetic from real (about 50%), yet the detector gained nothing: realism to the eye is not transfer. For us: when real labelled data is plentiful, synthetic is a tie, so its value is in classes and conditions that are rare in the real set (as in the Hassaan floor-plan item); keep the real-only model as the baseline. Breaks on ours: brightfield cells, generative model, boxes rather than counts.

- **Cell counting with MAE: crude synthetic pretraining is worse than 95 real images, style-transferred synthetic is slightly better** (InST-Microscopy, arXiv 2512.11763, Dec 2025, ICMLA 2025; HTML read via pwfetch 2026-11-14 [V]; counting is the one metric in this report that is an exact-count family): EfficientNet-B0 regressing counts on 600 x 800 px real fluorescence images (95 train / 24 validation, so the validation set is tiny), 256 px synthetic images, 200 px crops, sliding-window sum at test time. Real-only MAE 27.74; pretrain on hard-coded ellipse images then fine-tune on the real set is 13.46 MAE worse than real-only, the public Cell200-s set 27.86 worse (53.70 MAE), and the style-transferred set 1.49 better (25.95 reported in the abstract, up to 37% below the hard-coded one); equal real/synthetic batches ('dual training') and CutMix-style domain adaptation were also tested, CutMix with a recomputed count from the mixed cell map being the best strategy for a given dataset. Same message as top-5 row 1: crude synthetic hurts unless pushed toward the real look; the cost of a domain gap shows up directly in the count error. Breaks on ours: regression on whole images, fluorescence nuclei, a diffusion style-transfer step (no licence read for code or weights), and a validation set of 24 images - treat the 1.5 MAE gain as a tie.

- **Music manuscripts: synthetic pages built from real symbol glyph crops and blank backgrounds, then a replay mix** (Mayer et al., arXiv 2606.09479, Jun 2026, CC BY 4.0, HTML read via pwfetch 2026-11-14 [V]; synthesiser OMR-Research/Smashcima, Apache-2.0 by the gh licence API, so code is usable; but the MUSCIMA++ glyph data it uses by default is CC BY-NC-SA 4.0 by its README, so glyph banks must come from our own allowed crops): pages are rendered from symbolic scores with symbol glyphs cut from real annotated manuscripts (in-domain 'Authentic' glyphs or the older MUSCIMA++ glyphs) onto 13 blank real background patches; target is a small real manuscript set (symbol error rate, SER, lower is better; only 50 test systems, the authors say a gap of 8.4 SER is 95% likely real). Table 2 [V]: real-printed-music base model naive 88.0 then fine-tuned on authentic 41.3; synthetic-only base models 56.9-76.3 naive and 51.4-58.5 after fine-tune (worse than the real base model, 41.3); real base re-trained 2-6 epochs on synthetic (no replay) then fine-tuned 34.4-34.8; re-training on a 1:1 mix of the real and synthetic sets (replay) 38.1 and after fine-tune 33.2, the best. In-domain glyphs gave a clearly better naive score (49.9-51.8 vs 63.1-63.4) but the advantage disappears after fine-tuning (34.4 vs 34.8). The authors recommend mixing synthetic data into base training instead of treating it as domain adaptation, and say the generator still fails at how symbols connect (stems attach at one point). For us: it backs top-5 rows 3 and 5 together (real-sourced glyph crops, synthetic layout, pretrain then fine-tune on the few real pages, with a replay mix of real and synthetic as the last stage), and it says a real-glyph bank matters before fine-tuning but not after. Breaks on ours: sequence output (SER) not counts, born-digital base model, 50 test systems and a single run per row.

### 3.13 Two real-to-synthetic ratio sweeps (round 5), both outside drawings
- **Small electronic parts, 300 real images** (Antony et al., arXiv 2401.12729, Jan 2024 v2, [V] Tables I to IV; Unity
  renders of CAD parts without photorealism; LED, resistor, button below 32 x 32 px; YOLOv5, YOLOv7, SSD at 1080 px; one
  run per cell; no code or licence): with 300 real images and 0, 100, 150, 300 synthetic images, YOLOv5 small-object AP
  at 100 epochs is 0.493, 0.543, 0.594, 0.607 and overall mAP 0.976, 0.955, 0.986, 0.983; YOLOv7 small-object AP 0.480,
  0.499, 0.512, 0.470; SSD 0.204, 0.147, 0.190, 0.155; 300 synthetic alone gives mAP 0.412, 0.374, 0.198. So the best
  share is about half the real count by mAP, small-object AP still rises to a 1:1 share for one detector and falls for two,
  and synthetic-only is far worse. The authors' "up to 11.4%" matches no single cell I can find.
- **Fine-tuning beats mixing when real data is scarce** (Nowruzi et al., arXiv 1907.07061, Jul 2019, [V] Tables 3 to 5;
  SSD-MobileNet at 640 x 370, road scenes, real data 2.5%, 5%, 10% of 13k images; precision and recall only, no AP; no
  code): real-only person recall on one set rises 0.031, 0.043, 0.041, 0.087 for 2.5%, 5%, 10%, 100% real; synthetic
  pretraining then 10% real fine-tuning gives 0.139 on that set, above full real training, while mixing at the same ratios
  is weaker (the paper compares in a figure). Same direction as Vanherle 2022 above. One synthetic source (the
  game-engine one) beats another (a simulator) consistently, so the choice of synthetic generator matters as much as the ratio.
- Take-away for the recipe: with 3.8k real images our real share is already large, so the evidence says use synthetic
  data as a pretraining stage plus a bounded share (about a third to a half of the real count) rather than a majority,
  and keep a real-only arm on dev to be able to see "no gain" (section 3.12).

### 3.14 Remote sensing: generated images added to real ones (tiny oriented objects)
- OF-Diff (Ye et al., arXiv 2508.10801, ICLR 2026 per the page header, v3 Feb 2026; first 40k characters verbatim, appendix
  tables read verbatim on 2026-11-14 via pwfetch, so the ratio table is [V]): Stable Diffusion 1.5 with ControlNet and a shape branch
  generates aerial images from layouts; Oriented R-CNN (Swin) via MMRotate (Apache-2.0, read) on DIOR-R. Reported mix table
  (mAP, one run): generated-only 45.67; 50% real plus 50% generated 50.74; real-only 52.84; real plus 50%, 100%, 200%,
  300% generated 53.92, 54.38, 54.74, 54.82. So adding generated data on top of all the real data helped by about 1 to 2
  points with a plateau near three times; replacing real images with generated ones lost. arXiv 2006.05015 (remote-sensing synthetic aircraft, Jun 2020) abstract read only: random render parameters, CycleGAN refinement with real unlabeled images, then fine-tune on a little real data. For us this repeats the pattern of sections 3.12 and 3.13 and is a
  diffusion generator, whose count labels we have just seen to be unreliable (section 3.10), so it is context, not a
  recipe step. Code github.com/VisionXLab/OF-Diff: gh licence API returns 404 (no licence file found), so unusable as code.

## 4. Recipe for "the best commercial-safe set we could assemble in a night"

1. Render ResPlan layouts (CC BY 4.0 per its LICENSE, but its metadata says NC-SA: see item 2) into 3 styles, with our own symbol bank (hand-drawn variants for
   the commercial-safe set; real dev crops only for the NC prototype, whose weights stay local), clutter (text, dimension lines, furniture), rotations by 90 and 180 degrees, 1 to 4
   plans per sheet; real-scan blank texture under half of them (items 1, 2, 4, 5). The simple version of this recipe
   is what no paper tested on floor plans; each step is a measured gain in a neighbouring field.
2. Pretrain the detector on that set, then fine-tune on the 3.8k dev images with real boxes (item 3). Expect the
   dev gain on windows and doors to be small (the recycling study with 8.4k real images saw none); spend the
   synthetic budget on the rare classes and measure per class. Train at the inference resolution and tile size, and
   merge across tile borders (section 3.12). Do not mix at one
   ratio; if a mix is needed, the one paper that swept it peaked at "five to one" with the total fixed (most likely five
   real to one synthetic), so keep synthetic a minority share and check on dev.
3. Keep Augraphy (MIT) as the degradation tool, but test each degradation against real dev scans: a hand-made blur plus
   dust overlay lowered accuracy in one 2025 study, and Transcoda's own ablation is the only evidence that the full
   degradation stack helps on real scans.
4. Never score a checkpoint pretrained on CubiCasa5K or a repackage; nothing in this report uses one.

## 5. Looked for and did not find

- A real-to-synthetic ratio sweep for symbol detection on line drawings. Three sweeps exist in neighbouring fields
  (arXiv 2211.16066 industrial parts, 2401.12729 small electronic parts, 1907.07061 road scenes; section 3.13) and none uses
  drawings; the direction of the "five to one" ratio in the first stays implied (re-read in full 2026-11-14: the text says the share of real images is raised 'until the five to one ratio', total fixed at 3,510 images, best mixed AP 80.13 against a real-only model below that; fine-tuning with a small real set gave 82.05 and the 1:1 split 83.7, so fine-tuning beat the best mix by about 2-3 AP; the figure itself was not readable from the text).
- Per-randomisation ablations (line width, font, paper texture, noise) on any drawing field. Transcoda ablates three
  groups (concatenation, asymmetric augmentation, degradation) and UnionST six engine components, not single
  rendering parameters; SynthPID, SynthMap and Semap ablate nothing.
- Exact-count results from any transfer field. Every metric is AP, mIoU, F1, TEDS or edit distance.
- A PCB component-detection synthetic-to-real study with small objects, a chart-derendering study with synthetic ratios,
  and any floor-plan paper that measures synthetic augmentation with a clean on/off number.
- A PCB component-detection synthetic-to-real study: two further searches (round 5) found only defect-detection tiling
  work (arXiv 2605.24726, abstract read) and older GAN-augmentation papers; no component ablation.
- Readable full text for: the mechanical sketch study (Bickel et al., Applied Sciences 2024, six synthetic generation
  types, six detectors; MDPI refuses the headless browser too, only title and abstract seen **[reported]**); the
  CaSiDD paper. (The hand-drawn circuit paper arXiv 2106.11559 was read in full on 2026-11-14 via PDF [V]: 154 real hand-drawn images, 103 train / 51 test, rotation and flip augmentation to 388 training images, YOLOv5 mAP0.5 98.2% - real data only, no synthetic generation, so it is not evidence for synthetic training.)
- Semantic Scholar's API (HTTP 429 from curl and from the browser); I used OpenAlex's public cited-by lists instead,
  which are shorter and not filtered for relevance.

Round 6 additions to this list (2026-11-14): no 2025-26 paper that ablates copy-paste count on drawings or scans (only Kisantal 2019 and a policy search on aerial images); no exact-count metric on drawings in any paper found (closest: MolScribe exact structure match, cell-counting MAE); no forward citations found for Transcoda or UnionST; Schoenfelder's floor-plan text synthesis paper, the Mashcima ICDAR 2021 results and the Few-Shot Symbol Detection paper were not reachable (403 or no text) and stay unread.

## 6. Open questions and missing tools

Open:
- Does a real blank-paper overlay work when the paper texture in our scans is photographed under uneven light? A 20
  image check with and without it on dev would settle it before any training.
- Is the "five to one" mixing ratio in 2211.16066 five real to one synthetic? Re-read 2026-11-14: the text speaks of a growing 'ratio of real images' up to five to one, which fits five real to one synthetic, but the figure axis is not in the text; settled only by the figure or the repository (no licence).
- Which ResPlan licence applies, CC BY 4.0 (LICENSE, README) or CC BY-NC-SA 4.0 (croissant.json)? Two open issues, no reply;
  someone on the team could comment there, which is an outward-facing action I did not take.
- Is SynthPID's seed leak real? If the seeds are the test sheets, the 63.8 synthetic-only number is an upper bound.
- ResPlan has no WC class and no sauna: WC-versus-bathroom comes from the label, so synthetic ResPlan rooms need our
  own Finnish label strings (L5's scope).
- (pointers for other scopes) L12/L10: the 2026 P&ID deployment titles and SINA's GPT-4o count concordance are
  one-line leads for the market and trust scopes; L9: page concatenation in Transcoda is the same operation as
  splitting a sheet into plans, reversed.

Tools: OpenAlex's free daily budget ran out around the 50th request, so forward citations from the later papers
(Semap, Vanherle) were not listed; the web-search tool stood in with weaker recall. No arXiv MCP; web search and the fetch subagent worked for arXiv HTML, but binary PDFs came back as raw bytes
three times (Tuggener, hand-drawn circuits, AbSynth), so I read two of them with a local PDF-to-text pass on the saved
bytes. The headless browser worked for arXiv HTML and failed for Google (bot check), Semantic Scholar (429) and MDPI
(access denied). No Playwright captcha handling attempted. No poppler (`pdftotext`) on this machine.

## 7. Sources opened (URL, date read 2026-11-14), grouped by kind

2025-2026 (counted against the target of six): arXiv 2604.16513 (SynthPID, Apr 2026); arXiv 2602.06450 (UnionST, Feb
2026); arXiv 2605.10835 (Transcoda, May 2026); arXiv 2506.07539 (Zhu et al., Jun 2025); arXiv 2510.12208 (Bay et al.,
Oct 2025); arXiv 2601.22114 (SINA, Jan 2026); arXiv 2603.05037 (Semap, Mar 2026); arXiv 2511.15875 (Arzoumanidis, Nov
2025); arXiv 2604.02880 (InstructTable, Apr 2026); arXiv 2606.22574 (Jun 2026, skimmed); arXiv 2511.19538 (abstract).

2026 additions in rounds 4 and 5 (arXiv 2401.12729 and 1907.07061 ratio sweeps; arXiv 2605.26884, 2403.08721, abstract-only 2605.24726; counting: arXiv 2605.18063, 2403.04943, 2202.08670): arXiv 2610.09807 (Oct 2026); arXiv 2608.10978 (Aug 2026); arXiv 2508.10171 (Aug 2025);
arXiv 2608.17237 (Aug 2026); arXiv 2407.05607 (Jul 2024).

Round 6 (gen-2, 2026-11-14, all full text unless noted): arXiv 2605.24726 (PCB tiling, May 2026, PDF); arXiv 2602.21141 (SynthRender, Feb 2026, text); arXiv 2508.06492 (ECD charts, 2025); arXiv 2607.20385 (Persian Pixel, Jul 2026); arXiv 2608.28248 (abstract only); arXiv 2504.19347 (small drones, 2025); arXiv 2506.08956 (Fast AutoAugment, 2025); arXiv 2509.17078 (tiny aerial, 2025); arXiv 2507.08458 and 2508.10801 (tables re-read); arXiv 2605.18063 (appendix re-read); arXiv 2403.11291 (PDF); arXiv 2006.05015 (abstract); arXiv 2107.10373 (abstract); arXiv 2205.02659 (Schlagenhauf, PDF); Hassaan et al., Sensors 2023 (TUM PDF); Jamieson et al., IJDAR 2025 (Springer PDF); Mishra et al., Appl. Sci. 2021 (DFKI PDF); DeepScoresV2 ICPR 2020 (ZHAW PDF); Santehanser and Schoenfelder 2024 (TUHH PDF); Zenodo record 16278380 (CaSiDD); gh API for 2Obe/Text-Detection-on-Technical-Drawings (MIT), LatentSpaceIITB repos, YesianRohn/UnionST issues, VisionXLab/OF-Diff and mohammad-AJP/PCB-Defect-Detection (404 licence).

Earlier: TISMIR 2024 PDF (digitalcollection.zhaw.ch, bitstream 11475/28719); arXiv 2410.12628 (DocLayout-YOLO, 2024);
arXiv 2211.16066 (2022); arXiv 1902.07296 (Kisantal, via ar5iv); arXiv 1804.00525 (DeepScores); arXiv 2109.03794
(Digitize-PID); arXiv 2112.06104 (SynthMap); AbSynth (scitepress.org PDF, VISAPP 2024); arXiv 2106.11559 (full PDF, 2026-11-14).

Licences and data pages: gh API licence for btrkeks/transcoda, sparkfish/augraphy, clovaai/synthtiger,
ankush-me/SynthText, Belval/TextRecognitionDataGenerator, rism-digital/verovio, opendatalab/DocLayout-YOLO,
DocCreator/DocCreator, open-mmlab/mmrotate and mmdetection, m-agour/ResPlan (LICENSE file read), and the no-licence
results above; Zenodo records 4012193, 14803338, 17579452; OpenAlex cited-by lists for the TISMIR paper, the Zhu paper,
SynthMap and Digitize-PID.
