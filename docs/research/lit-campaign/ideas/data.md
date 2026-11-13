# Training data and pretraining

50 ideas. Index: [../IDEAS.md](../IDEAS.md).

## Try first

<a id="i382"></a>
### 382. Hugging Face licence tags do not reflect training data

Reviewer's note: A check, not an experiment: read the upstream data terms of every pretrained checkpoint before it ships.

- What: Read the card; treat CubiCasa5K derivatives as local only.
- Evidence (floor-plans): Apache-2.0 tag on a CC BY-NC trained adapter; MIT tag on a CC5K UNet.
- Source: [huggingface.co](https://huggingface.co/mudasir13cs/qwen25-vl-3b-floorplan-grpo)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: none
- Experiment: none
- What breaks on our images: none
- Moves: none. Why this group: legal trap
- Also (data, search-only): Upstream data terms of pretrained detection weights. Ask the owner whether weights pretrained on COCO and Objects365 (academic-use image terms) are acceptable in a shipped product; the publishers license the weights Apache-2.0. Evidence: Objects365 download page: 'available for the academic purpose only', annotations CC BY 4.0, images not owned; RF-DETR README: 'ship them in closed-source, commercial products'. Source: [github.com](https://github.com/roboflow/rf-detr). Experiment: None.
- Also (detect, authors-claim): Objects365 terms on RF-DETR and D-FINE pretrained weights. Get a legal reading whether Objects365 terms (academic purpose only) reach fine-tuned weights; use COCO-only checkpoints where possible. Check the exact RF-DETR checkpoint the pinned package downloads. Evidence: RF-DETR paper: Objects365 pretraining pseudo-labelled with SAM2; Objects365 page says academic purpose only, silent on weights; D-FINE README (2026-08-19) warns its Objects365 checkpoints are not cleared; D-FINE-seg authors treat Cityscapes weights as derivative of dataset terms. Source: [objects365.org](https://www.objects365.org/download.html), [github.com](https://github.com/Peterande/D-FINE). Experiment: Read the record of permitted licences; no run.
- Reports: lit-data-c, lit-detect-a, lit-detect-b, lit-detect-c, lit-rooms-a, lit-rooms-b, lit-rooms-c

<a id="i383"></a>
### 383. Export a per-plan box from the dev labels

- What: Build one box per plan as the union of that plan's element boxes in the dev labels, so every plan-level method has training and scoring data.
- Evidence (our-idea): none; the dev export does not carry a per-plan box yet. Dev sheets: 1 plan 3,044, 2 plans 672, 3 plans 109, 4 plans 3.
- Source: none
- Licence: own code. CubiCasa5K leakage: no.
- Cost: 1 h work, CPU
- Experiment: Export boxes, eyeball 20 two-plan sheets for gaps between plans and check that unions do not merge neighbouring plans.
- What breaks on our images: A plan with a big white courtyard or a far-off inset gives a box that is too small or split; plans touching at a stair or dimension line give overlapping unions.
- Moves: plans. Why this group: Every plan-level idea needs it and it is cheap.
- Reports: lit-sheet-a, lit-sheet-b, lit-sheet-c

<a id="i384"></a>
### 384. Count printed marks per sheet on dev

- What: Count dimension strings, room areas, flat total, opening sizes and bars per dev sheet.
- Evidence (our-idea): Two real plans differ; no statistic available.
- Source: [github.com](https://github.com/Hour49/Junction26)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2-3 h
- Experiment: Shares with at least 3 consistent dimension strings, any area, bar.
- What breaks on our images: none
- Moves: scale-areas. Why this group: Decides which routes to build.
- Reports: lit-scale-a, lit-scale-b, lit-scale-c

<a id="i385"></a>
### 385. Take label text positions from the dataset SVG text elements

- What: Check whether the dataset annotation SVGs carry text elements with positions, and if so cut label crops from dev images without any detector.
- Evidence (our-idea): none (the public loader code reads class names and parses no text element; no SVG was checked).
- Source: none
- Licence: dataset licence to check. CubiCasa5K leakage: yes.
- Cost: 1 h work (estimate)
- Experiment: Open a dev SVG, list text elements; if absent, use the fallback of OCR boxes inside a room polygon of class X as candidate crops for the codes of class X.
- What breaks on our images: If no positions exist, crops come only from distant supervision.
- Moves: room-types. Why this group: decides whether any fine-tune can use real labelled crops
- Reports: lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i386"></a>
### 386. Closed table of Finnish and Swedish room-label codes with room types

- What: Maintain a label table: MH, OH, K, KT, KH, KPH, S, WC, ET, VH, ALK, RT, P, H, PUKUH, VAR, AULA, KAYT, plus Swedish forms (K, KOK, RUM) and numbered MH1 or MH2; count the real label set from dev images because dataset plans are older and user-drawn.
- Evidence (search-only): Read as PDF text from public Finnish new-build plan packs and brochures (three and six packs); PH and TK appear on plans but are not defined in any legend. KH and KPH both mean bathroom; SK is a symbol-level code, not a room.
- Source: [asuntotuotanto.hel.fi](https://asuntotuotanto.hel.fi/system/files/mediabank/2025-05/00_asuntopohjat_kaikki_asunnot_1.pdf)
- Licence: public documents. CubiCasa5K leakage: n/a.
- Cost: 1 h work (estimate)
- Experiment: Count the label strings in dev images, compare with the table, and add the codes that occur at least a few times.
- What breaks on our images: Sales packs differ from user-contributed plans; handwritten notes; PH unverified.
- Moves: room-types. Why this group: the decode table every text item needs
- Reports: lit-ocr-a, lit-ocr-c

## Try next

<a id="i387"></a>
### 387. Directed copy-paste of rare classes into blank regions

- What: Paste bathtub and sauna-stove symbols into blank training patches or wall regions to lift rare-class recall.
- Evidence (floor-plans): Railway drawings: Box AP 0.6336 to 0.6630, rarest class (314 instances) Mask AP 0.2536 to 0.6176 (single run, Table 11).
- Source: [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 3-4 h
- Experiment: Dev ablation on per-class exact-count rate of rare classes.
- What breaks on our images: Pasted symbols need plausible context; one run.
- Moves: fixtures. Why this group: Rare fixtures are exactly where counts fail
- Also (data, adjacent-field): Paste real symbol crops for the thin classes onto other dev plans. Cut bathtub, shower and sauna-stove crops (with a few px of context) from dev plans and paste them at free wall or blank positions on other dev plans, adding the paste boxes as labels; keep originals, 1-3 pastes per object, no overlap with another symbol, rot90 only, blur matched to the target page. Evidence: Copy-paste 10% COCO +6.9 box AP, full COCO +1.5 (arXiv 2012.07177). Small-object paste with originals kept: AP_small 16.7 to 17.9, blur on the pasted edge hurts (arXiv 1902.07296). Class-balanced paste +0.9 to +1.9 AP on tail classes (VisDrone). Tiny drones, Nano model: -1.6 to +4.0 mAP50 vs +7 to +18 for mosaic and HSV (arXiv 2604.19999 Table II). Emergency plans: two rare classes found about 50% vs none, but a simple stairs glyph overfitted (Sensors 2023). Source: [arXiv 2012.07177](https://arxiv.org/abs/2012.07177), [arXiv 1902.07296](https://arxiv.org/abs/1902.07296), [arXiv 2604.19999](https://arxiv.org/abs/2604.19999), [github.com](https://github.com/conradry/copy-paste-aug). Experiment: Paste arm vs real-only on dev; read bathtub (312 boxes), sauna stove (2.5k), shower (4.6k) exact count and AP, two seeds.
- Also (data, adjacent-field): Paste rules for line-art symbols (stroke-density match, blank margins, several crops per class). Adapt the copy-paste recipe: replace the colour-difference check by a stroke-width or ink-density match, paste only on blank wall-free regions or blank margins, use several different crops per class so one glyph does not become the shortcut, and add clutter so the detector does not learn 'symbols appear without clutter'. Evidence: Small-drone paste recipe: per-patch blur, dropout, noise, scale range, overlap and colour checks, no paste-only ablation (arXiv 2504.19347). Emergency plans: blur sized from a Laplacian on the cutout, up to 12 pastes per cutout, no overlap (Sensors 2023). Source: [arXiv 2504.19347](https://arxiv.org/abs/2504.19347). Experiment: Ablate blur matching and number of distinct crops per class on dev.
- Also (floorplan, adjacent-field): Rare-class oversampling by pasting crops. Oversample sauna stoves, showers, bathtubs by pasting crops. Evidence: DeepScores: weighted losses failed, oversampling by pasting worked (reported). Source: [arXiv 1810.05423](https://arxiv.org/abs/1810.05423). Experiment: Per-class AP on rare classes.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-detect-b, lit-detect-c, lit-floorplan-b, lit-floorplan-c

<a id="i388"></a>
### 388. Use the public FP-TXT text-box annotations to train a detector

- What: Download FP-TXT (text boxes over CubiCasa5K, CVC-FP and BRIDGE images, no transcriptions) and check overlap with our dev and eval splits before using it.
- Evidence (floor-plans): A dataset of boxes (machine-printed and handwritten); no accuracy result.
- Source: [zenodo.org](https://zenodo.org/records/7921780)
- Licence: annotations MIT per the record text (Zenodo licence field empty). CubiCasa5K leakage: yes.
- Cost: 1 h to read, not downloaded (estimate)
- Experiment: Count overlap of its images with our dev and eval splits; use only dev-split images.
- What breaks on our images: Covers CubiCasa5K images, so eval-split overlap must be excluded; no transcriptions.
- Moves: room-types. Why this group: free boxes if the overlap is clean
- Reports: lit-ocr-a

<a id="i389"></a>
### 389. Render training crops of our label codes over real drawing backgrounds

- What: Render the abbreviations in CAD-like fonts at 6-14 px with blur, JPEG, thin grey lines, hatching, four rotations, random strings and one-character-removed variants, over text-free patches cut from real plans.
- Evidence (adjacent-field): Synthetic-only trails real by 0.3 on multi-oriented scene text (94.45 vs 94.74); 5M synthetic plus 1% real equals all-real (87.26 vs 87.22) (UnionST, arXiv 2602.06450). Rotation randomisation lifts multi-oriented from 33.31 to 87.29. Map text rendered over real map backgrounds adds +13.9 (PaLeTTe Table 4). A generator trained on rendered drawings found 81.87% of text vs 4.67% from 9 real drawings (arXiv 2205.02659).
- Source: [arXiv 2602.06450](https://arxiv.org/abs/2602.06450), [arXiv 2506.15010](https://arxiv.org/abs/2506.15010), [arXiv 2205.02659](https://arxiv.org/abs/2205.02659), [github.com](https://github.com/clovaai/synthtiger)
- Licence: SynthTIGER MIT; TextRecognitionDataGenerator MIT. CubiCasa5K leakage: no.
- Cost: 2 to 4 h work, CPU only (estimate)
- Experiment: Render 5k to 50k crops, fine-tune the recogniser, and score exact match on real dev crops with and without the synthetic part; synthetic is still 10.6 behind on general text so real crops are needed for the last mile.
- What breaks on our images: No paper measures synthetic-only on 5-12 px drawing labels; hatching and wall strokes touching glyphs are hard to render.
- Moves: room-types. Why this group: feeds every fine-tune item
- Also (data, adjacent-field): Synthetic sheets built from real glyph crops placed by generator rules. Compose pages from a bank of real symbol crops (from allowed sources) on blank real backgrounds using rule-based placement, then pretrain and fine-tune with a replay mix. Evidence: Music manuscripts: synthetic-only base 51.4-58.5 SER after fine-tune vs 41.3 real base; real base retrained on a 1:1 real-synthetic replay mix 33.2 (arXiv 2606.09479). In-domain glyphs help before fine-tuning (49.9-51.8 vs 63.1-63.4) but not after. Technical drawings: 150 real crops pasted into generated pages found 81.9% of 171 labels vs 4.7% for the 9-drawing model (arXiv 2205.02659). Source: [arXiv 2606.09479](https://arxiv.org/abs/2606.09479), [arXiv 2205.02659](https://arxiv.org/abs/2205.02659), [github.com](https://github.com/2Obe/Text-Detection-on-Technical-Drawings). Experiment: Build 2-5k sheets from dev crops, replay-mix with real, fine-tune; compare to real-only per class.
- Also (data, adjacent-field): Generated label crops for room-label recognition. Render closed-vocabulary label crops (MH, K, WC, ...) with a permissive text-synthesis engine and fine-tune a recogniser; real crops stay as the anchor. Evidence: Scene text: synthetic-trained model with 1% real labels 87.26 vs 87.22 all-real (arXiv 2602.06450); SynthTIGER 57.87 vs ST-2D 73.36 vs UnionST 83.00 on the hard set (Table 4). Own-label crops on technical drawings: 81.9% of 171 found vs 4.7% real-only (arXiv 2205.02659). Source: [arXiv 2602.06450](https://arxiv.org/abs/2602.06450), [arXiv 2205.02659](https://arxiv.org/abs/2205.02659). Experiment: Fine-tune the recogniser on rendered crops of our codes plus real crops; read room-type exact count on dev.
- Also (ocr, adjacent-field): Cut text-free patches from real plans as backgrounds for rendered labels. Take text-free patches (walls, hatching, furniture) from real dev plans and render labels on them. Evidence: SynthMap+ rendering names over real map patches lifted end-to-end 55.9 to 69.8 (PaLeTTe Table 4); TESTR +12.9 (53.0 to 65.9). Source: [arXiv 2506.15010](https://arxiv.org/abs/2506.15010), [zenodo.org](https://zenodo.org/records/14480731). Experiment: Fine-tune with plain vs real-patch backgrounds and compare on real dev crops.
- Reports: lit-data-b, lit-ocr-a, lit-ocr-b, lit-ocr-c

<a id="i390"></a>
### 390. Pretrain or mix with licence-clean synthetic plans

- What: Mix 30% rendered plans with exact boxes (benikm91 sets, fpgen, ResPlan-FP) into training for the VLM and detector arms, with rotation, blur, perspective augmentation.
- Evidence (adjacent-field): No result on our task; TechING synthetic-only real F1 x6.97, SynthPID 63.8 edge mAP, SMT++ SER 32.1 to 5.6.
- Source: [arXiv 2601.18238](https://arxiv.org/abs/2601.18238), [arXiv 2604.16513](https://arxiv.org/abs/2604.16513), [arXiv 2405.12105](https://arxiv.org/abs/2405.12105), [huggingface.co](https://huggingface.co/datasets/benikm91/synthetic-floorplans-with-furnitures-for-transcription)
- Licence: data CC BY 4.0; generator repo no licence; fpgen MIT. CubiCasa5K leakage: no.
- Cost: about 1 day wiring, 1 GPU-day (estimate)
- Experiment: Train on synthetic then fine-tune on dev boxes vs dev boxes only; compare exact counts on held-out dev.
- What breaks on our images: Manhattan walls, one style per plan, no text, no sauna stove; sim-to-real gap.
- Moves: windows-doors. Why this group: After a first real-data number exists.
- Also (count, adjacent-field): Render pretrain then real fine-tune. Pretrain on rendered symbols, then fine-tune on few real pages. Evidence: DeepScores to MUSCIMA++ (arXiv 1805.10548), black noteheads AP about 0.86-0.92. Source: [arXiv 1805.10548](https://arxiv.org/abs/1805.10548). Experiment: Idea for later: pretrain on rendered symbols and fine-tune on dev plans; count error per page.
- Also (data, adjacent-field): Pretrain on synthetic, then fine-tune on real boxes (do not mix at one ratio). Run a pretraining stage on generated sheets, then fine-tune on the real dev boxes; optionally finish with a replay mix of real and synthetic. Report dev at each stage. Evidence: Industrial parts: fine-tune after synthetic pretrain 82.05-83.7 AP vs best mix 80.13 (arXiv 2211.16066). Historical maps, ~1,000 real images: mIoU 74.2 vs 69.1 without synthetic pretraining (arXiv 2603.05037 Table 4). Music: replay mix 33.2 SER vs 41.3 real-only fine-tune (arXiv 2606.09479). With 8.4k real images no gain (arXiv 2605.26884). Source: [arXiv 2211.16066](https://arxiv.org/abs/2211.16066), [arXiv 2603.05037](https://arxiv.org/abs/2603.05037), [arXiv 2606.09479](https://arxiv.org/abs/2606.09479). Experiment: Pretrain on 3-5k generated sheets, fine-tune on dev; compare to real-only per class. Third arm: real-only plus a bounded synthetic share (up to half the real count).
- Also (rooms, search-only): Pretrain on synthetic plans with exact doors and rooms. Pretrain the separator on a CC BY set of 450k generated plans with exact room, wall and door labels. Evidence: Card: 512 px, Manhattan only, 6 px walls, no text or furniture. Source: [huggingface.co](https://huggingface.co/datasets/benikm91/synthetic-floorplans-for-transcription). Experiment: Compare dev merges with and without pretraining; also use as exact-truth unit test of the area pipeline.
- Reports: lit-count-b, lit-data-b, lit-data-c, lit-rooms-a, lit-rooms-b, lit-rooms-c, lit-vlm-b, lit-vlm-c

<a id="i391"></a>
### 391. Pseudo-label crops: an OCR box inside a room polygon of class X is a crop for the codes of class X

- What: Label real crops by the room class of the polygon containing the OCR box, drop reads that contradict the polygon class, and keep confident ones as fine-tuning labels.
- Evidence (our-idea): Lexicon-based pseudo-labels on real unlabeled word images fix modest synthetic-only training (arXiv 2003.01989); a small number of crops was enough for 90% in meter reading with hard-sample selection. Not tested here.
- Source: [arXiv 2003.01989](https://arxiv.org/abs/2003.01989)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 2 h work (estimate)
- Experiment: Build the pseudo-labelled set from dev images, fine-tune, and measure exact match on hand-checked dev crops.
- What breaks on our images: Wrong pseudo-labels train in mistakes; a label read as MH inside a polygon not of a bedroom class should be dropped.
- Moves: room-types. Why this group: gives real crops without hand labelling
- Reports: lit-ocr-a, lit-ocr-c

## Later

<a id="i392"></a>
### 392. Use CubiCasa5K sub-category folders as a free style label

- What: Use the three sub-categories (high quality architectural 3,732, high quality 992, colorful 276) to stratify dev scores and gate analysis.
- Evidence (floor-plans): CubiCasa5K paper; whether the style is known at answer time is open.
- Source: [arXiv 1904.01920](https://arxiv.org/abs/1904.01920)
- Licence: CC BY-NC 4.0 data. CubiCasa5K leakage: yes.
- Cost: 30 min work
- Experiment: Report exact counts per sub-category on dev.
- What breaks on our images: The folder may not be known at answer time.
- Moves: scale-areas. Why this group: Check the question set first.
- Reports: lit-sheet-a

<a id="i393"></a>
### 393. Re-render dev layouts clean and scanned to build paired data

- What: Build a clean-versus-scan pair per dev image by re-rendering vector sources in several depictions with fixed boxes, for depiction-robustness training and diagnosis.
- Evidence (floor-plans): A paired variant release exists for CubiCasa5K (4,996 layouts, 4.68 GB, splits 4,197 / 400 / 399) with two ROI-controlled composites; the dev images are the scanned depiction themselves.
- Source: [doi.org](https://doi.org/10.5281/zenodo.18890483)
- Licence: paired set CC BY-NC 4.0. CubiCasa5K leakage: yes.
- Cost: 3-4 h (estimate)
- Experiment: Train on clean re-renders with and without depiction jitter; test on scanned dev crops.
- What breaks on our images: Needs rights confirmation for re-rendered dev pixels.
- Moves: windows-doors. Why this group: open question whether re-rendering dev sheets is covered
- Reports: lit-data-a

<a id="i394"></a>
### 394. FloorPlanCAD (non-commercial) as a local second pretraining stage for fixtures

- What: Convert the PNG copy (1000x1000, 20 m crops, about 50 px per metre) to boxes for toilet, sink, bath, bathtub, window and door; pretrain locally, fine-tune on dev; weights never shipped.
- Evidence (floor-plans): Faster R-CNN R101 mAP 0.452 on FloorPlanCAD (arXiv 2105.07147 Table 4); per-class AP toilet 0.666, sink 0.468, bath 0.422, bathtub 0.259, window 0.518 (Table 6). Toilet and sink about 20 px in the PNG copy.
- Source: [arXiv 2105.07147](https://arxiv.org/abs/2105.07147), [huggingface.co](https://huggingface.co/datasets/Voxel51/FloorPlanCAD)
- Licence: annotations CC BY-NC 4.0, authors do not own the drawings; HF copies tagged cc-by-sa-4.0 while the card body says NC. CubiCasa5K leakage: no.
- Cost: 4-6 h incl. conversion (estimate)
- Experiment: Pretrain on it, fine-tune on dev, compare with real-only per fixture class.
- What breaks on our images: Chinese CAD style, windows AP only 0.38-0.52, local weights only.
- Moves: fixtures. Why this group: only after a first number exists
- Reports: lit-data-a, lit-data-c

<a id="i395"></a>
### 395. fpgen: MIT procedural generator with fixture boxes and a registered degradation stack

- What: Render 3-5k plans from the MIT generator, adapted to our eight classes, a Finnish label vocabulary and a sauna-stove glyph, at 855 px with symbols down-scaled to the 5-20 px regime; export fixture boxes to COCO and train as a supplement for rare classes.
- Evidence (floor-plans): Generator emits toilet, shower, bathtub, sink, stove boxes with pixel-exact truth and 19 whitelisted degradations (registration within 1.5 px). Authors trained only on walls, openings and rooms, so fixture boxes were never evaluated; mixing 3,327 synthetic with 3,328 real plans gave wall F1 0.769 to 0.781, inside noise.
- Source: [github.com](https://github.com/Cyprinus12138/fpvec-lab), [arXiv 2608.25608](https://arxiv.org/abs/2608.25608)
- Licence: code MIT (needs skia-python BSD-3, Augraphy installed separately); no weights; generated plans ours. CubiCasa5K leakage: no.
- Cost: 3-5 h adapter work, generation CPU minutes to an hour, one detector run (estimate)
- Experiment: Train real-only vs real + 3-5k fpgen renders (with and without depiction jitter) on dev; read bathtub, sauna stove and shower AP and exact count.
- What breaks on our images: Singapore-listing symbol set and room programme, no sauna or Finnish labels, Manhattan walls, symbols about 28x50 px at native render (needs 0.3-0.6 down-scaling), vector-clean strokes.
- Moves: fixtures. Why this group: no significant gain beside thousands of real plans; only matters for a commercial-safe checkpoint
- Also (floorplan, adjacent-field): Seeded procedural plan generator with degradations. Use or imitate fpgen to make plans seeded from our annotated rooms with scan degradations. Evidence: Used for walls only; SynthPID analogue 63.8 edge mAP vs 69.4 real-only but seeded from test drawings. Source: [github.com](https://github.com/Cyprinus12138/fpvec-lab), [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Mix ratio ablation on dev.
- Reports: lit-data-a, lit-floorplan-a, lit-floorplan-c

<a id="i396"></a>
### 396. Fix labels before changing the detector

- What: Human correction of LLM-assisted labels moved the same detector from 0.650 to 0.926 mAP@50; fix systematic label errors first.
- Evidence (floor-plans): DoorDet Table 7: Co-DETR 0.650 before, 0.926 after correction; annotation 97.5 s per plan from scratch, 54.5 s with detector, LLM and a person.
- Source: [arXiv 2508.07714](https://arxiv.org/abs/2508.07714)
- Licence: data on acceptance; CubiCasa5K terms apply. CubiCasa5K leakage: yes.
- Cost: 1 day of labelling (estimate)
- Experiment: Relabel 100 dev plans' doors and windows and re-score the same detector.
- What breaks on our images: Self-consistency: the labeller and the trained model are the same family.
- Moves: windows-doors. Why this group: high lever, needs people
- Reports: lit-market-a, lit-market-b

<a id="i397"></a>
### 397. LegendSpot data for dev tests only

- What: Use 40 drawings only locally.
- Evidence (floor-plans): CC BY-NC 4.0.
- Source: [arXiv 2610.09313](https://arxiv.org/abs/2610.09313)
- Licence: data CC BY-NC. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Local reproduction of the 14 of 40 exact-count result with the published script, to check our port of the template-matching recipe.
- What breaks on our images: Images, templates and annotations are CC BY-NC 4.0: never into the repo or product.
- Moves: none. Why this group: Check reimplementation.
- Reports: lit-count-a

<a id="i398"></a>
### 398. Clean overlapping CubiCasa5K polygons before training

- What: Remove overlapping wall and opening polygons.
- Evidence (floor-plans): Corrected labels move wall F1 0.74 to 0.825.
- Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608)
- Licence: skv4 CC BY-NC-SA. CubiCasa5K leakage: yes.
- Cost: half a day
- Experiment: Compare noise on dev labels.
- What breaks on our images: Local only.
- Moves: none. Why this group: label noise
- Reports: lit-rooms-a, lit-rooms-c

<a id="i399"></a>
### 399. Pre-train on CC BY synthetic plan sets

- What: Use generated plans with exact door and window records (CC BY 4.0) for pre-training or checking a counting stage, away from CubiCasa5K.
- Evidence (adjacent-field): benikm91 synthetic floor plans (cards read): Manhattan, one door per room, no scan noise; ResPlan-FP 16,998 plans at 256 px CC BY 4.0; ResPlan CC BY 4.0.
- Source: [huggingface.co](https://huggingface.co/datasets/benikm91/synthetic-floorplans-with-furnitures-for-transcription), [arXiv 2608.25608](https://arxiv.org/abs/2608.25608)
- Licence: CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 1 day (estimate)
- Experiment: Pre-train then fine-tune on dev and compare to scratch.
- What breaks on our images: A model learns the generator's rules; 256 px is smaller than ours.
- Moves: windows-doors. Why this group: no leakage
- Reports: lit-market-a, lit-market-b

<a id="i400"></a>
### 400. Overlay synthetic plans on real blank scanned paper

- What: For any synthetic plan we add, draw it over real blank scans (keep the darker pixel) with small rotation, flips, blur, brightness; finish with epochs on whole pages.
- Evidence (adjacent-field): Music scores: AP@0.25 on 12 real scans 36.0 to 56.5, 73.7 after 200 extra epochs on full pages; clean synthetic test dropped 87.6 to 83.3; gradient-reversal adaptation only 48.9.
- Source: [digitalcollection.zhaw.ch](https://digitalcollection.zhaw.ch/bitstream/11475/28719/1/2023_Tuggener-etal_Real-world-music-object-recognition_TISMIR.pdf)
- Licence: code on GitHub without licence file (idea only). CubiCasa5K leakage: no.
- Cost: 2 h
- Experiment: Only if synthetic plans enter training; test on scanned dev images.
- What breaks on our images: One small test set, S2A-Net oriented detector.
- Moves: plans. Why this group: Our real boxes are plentiful
- Also (data, adjacent-field): Lay real blank scanned pages under rendered sheets, then a full-page finishing pass. When training on rendered plans, overlay a real blank scan by keeping the darker pixel per position, then finish with a short fine-tune on full pages. Dev-scan margins may supply the blank paper. Evidence: Music scores, tiny symbols: real-scan AP@0.25 36.0 to 56.5 (overlay) to 73.7 (plus 200 epochs on full pages); synthetic-set AP 87.6 to 83.3 (TISMIR 2024, 51 blank pages). Hand-made blur plus dust overlay on maps lowered accuracy 0.8357 to 0.8125; a learned degradation reached 0.8716 (arXiv 2511.15875). Source: [doi.org](https://doi.org/10.5334/tismir.157), [arXiv 2511.15875](https://arxiv.org/abs/2511.15875). Experiment: 20-image check on dev that margins are clean paper; then rendered-sheet training with and without overlay, tested on real dev.
- Reports: lit-data-a, lit-data-b, lit-detect-b

<a id="i401"></a>
### 401. Keep synthetic at or below half the real count

- What: When mixing generated data into training, cap it at about half the real image count and mix from the start; judge on dev.
- Evidence (adjacent-field): Small electronic parts, 300 real: YOLOv5 small-object AP 0.493 / 0.543 / 0.594 / 0.607 for 0 / 100 / 150 / 300 synthetic (arXiv 2401.12729), but YOLOv7 and SSD fell at 1:1. Rural driving, 4,200 real: best at 1:0.5 (arXiv 2607.27058). Industrial: real share raised up to 'five to one' (arXiv 2211.16066, direction implied).
- Source: [arXiv 2401.12729](https://arxiv.org/abs/2401.12729), [arXiv 2607.27058](https://arxiv.org/abs/2607.27058), [arXiv 2211.16066](https://arxiv.org/abs/2211.16066)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: Sweep synthetic share 0, 0.25, 0.5, 1.0 of real on dev, two seeds.
- What breaks on our images: No ratio sweep exists on drawings.
- Moves: none. Why this group: only relevant once a generator exists
- Also (data, adjacent-field): Stop generating at a few thousand sheets. Generate low thousands of sheets, not the 1M available; more generated pages give diminishing returns, and diversity of layouts matters more than count. Evidence: Text on technical drawings: 2,000 pages worst, 5,000 and 7,000 similar (arXiv 2205.02659). 3D parts: last step of 3,200 to 4,000 gave +0.3 mAP50 (arXiv 2602.21141). P&ID seed-based: +12.5 from 100 to 400, +5.1 from 400 to 665; plateau from seed diversity (arXiv 2604.16513). Source: [arXiv 2205.02659](https://arxiv.org/abs/2205.02659), [arXiv 2602.21141](https://arxiv.org/abs/2602.21141), [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Compare 1k, 3k, 5k generated sheets on dev for a rare class.
- Also (floorplan, adjacent-field): Treat real annotated plans as the core, synthetic as supplement. Synthetic-only or synthetic-heavy training is not enough. Evidence: Chemistry: 91% synthetic vs below 16% real; 9.5% real lifted 0.15 to 0.37; OMR synthetic-only 63.97% error on real scans. Source: [arXiv 2608.09100](https://arxiv.org/abs/2608.09100), [arXiv 2605.10835](https://arxiv.org/abs/2605.10835). Experiment: none
- Also (vector, adjacent-field): Real-data fraction dose series for synthetic training. Measure how much real labelled data a synthetic-trained detector needs. Evidence: 2608.09100 Table 3: synthetic-only .231 average on real sets; 9.5% real lifts to about .62; 41.6% real to .67; first 5% real gives about two thirds of the real gain. Source: [arXiv 2608.09100](https://arxiv.org/abs/2608.09100). Experiment: Train at 0, 5, 10, 40, 100% of real dev boxes on top of any pretraining; plot exact-match.
- Reports: lit-data-b, lit-data-c, lit-floorplan-c, lit-vector-b

<a id="i402"></a>
### 402. Synthetic plans must reuse real wall and room layouts

- What: Generate training plans by drawing symbols onto real topologies, not by scattering symbols.
- Evidence (adjacent-field): SynthPID: topology-seeded synthetic data 63.8 edge mAP against about 33 for random scatter; mixed with real 72.6; flattens after about 400 images.
- Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513)
- Licence: paper; generator not found. CubiCasa5K leakage: n/a.
- Cost: 1 to 2 days (estimate)
- Experiment: Render symbols on dev room polygons and measure detector gain at 100, 400, 1000 images.
- What breaks on our images: P&ID symbols are standardised; ours vary by drawing office.
- Moves: windows-doors. Why this group: licence-clean data path
- Also (data, adjacent-field): Seed generated sheets from the layouts of real plans, widen the seed pool. Build the generator's layouts from real plan structure (room polygons of dev plans, or an open layout set) with jitter and symbol swaps, deduplicated by structure and perceptual hash, instead of random scatter. Evidence: P&ID: seeding from 12 real sheets gave edge mAP 63.8 synthetic-only vs 69.4 real oracle and 72.6 mixed (arXiv 2604.16513); the paper's cross-paper comparison with random scatter (~33) is not a rerun, and seeds may overlap the test sheets. Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Generate from dev-plan structure with our own symbol bank and compare with a random-layout set at equal count on dev.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-market-b

<a id="i403"></a>
### 403. SAM 3 as a pseudo-labeller

- What: Prompt SAM 3 with exemplars to draft boxes for review.
- Evidence (adjacent-field): Document category AP 12.9 zero-shot, 35.8 10-shot, 64.2 full (Roboflow100-VL tables).
- Source: [arXiv 2511.16719](https://arxiv.org/abs/2511.16719)
- Licence: custom SAM licence. CubiCasa5K leakage: n/a.
- Cost: half a day
- Experiment: Draft quality vs hand labels.
- What breaks on our images: Licence must be read; near 13 AP zero-shot.
- Moves: none. Why this group: needs tuning
- Reports: lit-floorplan-c

<a id="i404"></a>
### 404. Rare and look-alike classes fail on small sets

- What: Expect AP below 60 for classes with under about 100 instances and for look-alike classes; use copy-paste.
- Evidence (adjacent-field): SkeySpot: classes over 100 instances 92-99 AP50, 78 instances 43, 2-3 instances 21-24 (45 plans).
- Source: [arXiv 2508.10449](https://arxiv.org/abs/2508.10449)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0
- Experiment: See copy-paste.
- What breaks on our images: 
- Moves: fixtures. Why this group: Informs which classes to merge
- Reports: lit-detect-a, lit-detect-b

<a id="i405"></a>
### 405. Pretrain on synthetic plans with dimension chains

- What: Use ResBIM or draw dimension strings onto our dev plans (Rulers2023 recipe) to train a dimension reader.
- Evidence (adjacent-field): ResBIM 1,000+ synthetic plans with dimensions; Rulers2023 synthetic beats real-trained on IoU.
- Source: [github.com](https://github.com/RogerLiang0725/ResBIM), [mdpi.com](https://www.mdpi.com/2079-9292/12/24/4924)
- Licence: repo MIT; data terms unchecked. CubiCasa5K leakage: no.
- Cost: 1-2 days
- Experiment: Train and test on dev real crops.
- What breaks on our images: Domain gap.
- Moves: scale-areas. Why this group: No labelled chains otherwise.
- Reports: lit-scale-b, lit-scale-c

<a id="i406"></a>
### 406. Pretrain on cleaned ResPlan

- What: Use the cleaned subset only.
- Evidence (authors-claim): About half of ResPlan records invalid or duplicate (8,431 of 17,000).
- Source: [arXiv 2610.17178](https://arxiv.org/abs/2610.17178)
- Licence: CC BY 4.0. CubiCasa5K leakage: no.
- Cost: half a day
- Experiment: Dev merges with and without.
- What breaks on our images: Style gap, arbitrary scale per plan.
- Moves: none. Why this group: licence-clean data
- Also (data, search-only): ResPlan or ModRes layouts as the layout source for a plan renderer. Render ResPlan's vector plans (or the cleaned 8,431-plan ModRes subset) with our own fixture glyphs and Finnish labels, locally only until the licence conflict is settled. Evidence: 17,000 vector plans, walls, doors, windows, 11 category keys, no fixtures and no WC key (resplan_utils.py). Licence: LICENSE says data CC BY 4.0, croissant.json says CC BY-NC-SA 4.0, two issues asking are open with no reply. No paper trains a symbol detector on ResPlan renders (citation walk of 14-15 citers). Source: [arXiv 2508.14006](https://arxiv.org/abs/2508.14006), [arXiv 2610.17178](https://arxiv.org/abs/2610.17178), [github.com](https://github.com/m-agour/ResPlan). Experiment: Only after fpgen or another renderer shows a rare-class gain; compare ResPlan layouts with the generator's own at equal count.
- Also (floorplan, search-only): Render ResPlan vector plans into training images. Render door and window polygons in randomised styles with rotation and degradation. Evidence: 17,000 vector plans; no door/window counting effect measured anywhere. Source: [arXiv 2508.14006](https://arxiv.org/abs/2508.14006), [github.com](https://github.com/m-agour/ResPlan). Experiment: Pretrain then fine-tune on real dev; compare to real only.
- Reports: lit-data-a, lit-data-b, lit-data-c, lit-floorplan-a, lit-floorplan-b, lit-floorplan-c, lit-rooms-a, lit-rooms-b

<a id="i407"></a>
### 407. Drop crops that contradict the dev answer's room counts

- What: A crop read as MH on an image whose bedroom count is 0 is dropped; the confident rest become pseudo-labels.
- Evidence (our-idea): none
- Source: none
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 1 h work (estimate)
- Experiment: Compare pseudo-label precision with and without the filter on a hand-checked 100-crop sample.
- What breaks on our images: Dev answers hold counts, not positions.
- Moves: room-types. Why this group: extra filter on the pseudo-label set
- Reports: lit-ocr-c

<a id="i408"></a>
### 408. Label a multi-plan sheet set with plan boxes

- What: Hand-check 100 sheets for plan boxes and storey names to measure splitters independently of the label export.
- Evidence (search-only): No dataset labels storeys per image; MLSTRUCT-FP has one floor per file.
- Source: none
- Licence: own labels. CubiCasa5K leakage: no.
- Cost: 2-3 h hand work
- Experiment: Use as a held-out set for plan counters.
- What breaks on our images: Hand labels are a small sample.
- Moves: plans. Why this group: Only if the export boxes look unreliable.
- Reports: lit-sheet-a

<a id="i409"></a>
### 409. Independent plans for calibration and shift tests

- What: Derive counts from vector plans not in the CubiCasa5K train split.
- Evidence (search-only): 17,000 vector plans (2508.14006), 5.3K (2407.10121); licences unknown.
- Source: [arXiv 2508.14006](https://arxiv.org/abs/2508.14006)
- Licence: NOASSERTION, check. CubiCasa5K leakage: unknown.
- Cost: 1 day
- Experiment: Check licence then compute counts.
- What breaks on our images: Rendered images, no scans.
- Moves: trust. Why this group: Avoids the 829-plan leak.
- Reports: lit-trust-c

<a id="i410"></a>
### 410. Render Swiss Dwellings openings and sanitary features

- What: Render 715,000 openings and 315,000 features to images with exact boxes.
- Evidence (search-only): Record counts only; no detector trained on it.
- Source: [zenodo.org](https://zenodo.org/records/7788422)
- Licence: CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 1 day
- Experiment: As ResPlan.
- What breaks on our images: Symbols are geometry only; Swiss conventions.
- Moves: fixtures. Why this group: only licence-clean source of fixtures
- Reports: lit-floorplan-a, lit-floorplan-b

## Idea or pitch only

<a id="i411"></a>
### 411. BlueprintSymVL as a clean-licence sanity set

- What: Use CC BY 4.0 valve set for exemplar-in-context.
- Evidence (floor-plans): 6.2 MB, 100 regions x occluded copies.
- Source: none
- Licence: CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Download once, check whether annotations carry point positions, run the template-matching second counter to see if the pipeline reproduces the paper's exact-match range.
- What breaks on our images: Engineering blueprints, 860 px screenshots, five valve classes, not floor plans.
- Moves: none. Why this group: Off-domain.
- Reports: lit-count-a

<a id="i412"></a>
### 412. A few dozen clean in-domain annotations beat noisy extras

- What: Prefer 30 careful labels over many noisy ones.
- Evidence (floor-plans): 32 annotated plans lifted mean rating 2.45 to 3.54 (Aalto thesis, walls, qualitative).
- Source: [aaltodoc.aalto.fi](https://aaltodoc.aalto.fi/)
- Licence: CC BY-NC-SA. CubiCasa5K leakage: yes.
- Cost: n/a
- Experiment: Learning curve on dev.
- What breaks on our images: Walls only.
- Moves: trust. Why this group: data hygiene
- Reports: lit-floorplan-b

<a id="i413"></a>
### 413. Split multi-plan CubiCasa5K instances by closed contours of the label mask

- What: For training composites or labels, take each closed contour of the ground-truth foreground as one plan and shift corners to its bounding box.
- Evidence (floor-plans): Raster2Seq: images may contain several floorplan instances and are split this way; no accuracy.
- Source: [arXiv 2602.09016](https://arxiv.org/abs/2602.09016)
- Licence: n/a. CubiCasa5K leakage: yes.
- Cost: 1 h work
- Experiment: Count the contours on dev multi-plan sheets against the labelled plan count.
- What breaks on our images: Only works on labels, not raw rasters.
- Moves: plans. Why this group: Confirms the case exists; box export covers it.
- Reports: lit-sheet-a

<a id="i414"></a>
### 414. Hybrid coverage plus uncertainty picker for next labels

- What: Choose which pages to label next by mixing coverage and uncertainty.
- Evidence (adjacent-field): D-FINE-X from COCO on 71-500 documents, 10 seeds: hybrid beats single signals from about 200 documents (arXiv 2607.00747); high variance at low budgets.
- Source: [arXiv 2607.00747](https://arxiv.org/abs/2607.00747)
- Licence: code link not seen. CubiCasa5K leakage: no.
- Cost: 3 h
- Experiment: Only if labelling continues.
- What breaks on our images: Documents not symbols.
- Moves: none. Why this group: Our labels already exist
- Reports: lit-detect-a

<a id="i415"></a>
### 415. Erase symbols and lower the label

- What: Paint over some window or door cells, repaint the wall, decrement the count, train on the variants.
- Evidence (adjacent-field): +9.47% counting on remote sensing (2512.02517).
- Source: [arXiv 2512.02517](https://arxiv.org/abs/2512.02517)
- Licence: Apache-2.0. CubiCasa5K leakage: n/a.
- Cost: 1 day
- Experiment: A/B on dev exact counts.
- What breaks on our images: Gaps left in walls.
- Moves: windows-doors. Why this group: Needs repainting.
- Reports: lit-vlm-c

<a id="i416"></a>
### 416. Place synthetic symbols where they occur and cluster them

- What: In any generator, put windows in outer walls, doors between rooms, sinks along bathroom or kitchen walls; cluster instead of uniform scatter; vary glyph shape.
- Evidence (adjacent-field): Counting with rendered objects: clustered placement MAE 23.2 vs 63.4 uniform; random vertex displacement and extrusion best on all five sets (arXiv 2202.08670 Table 4). fpgen fixture solver already places toilets only in bath or WC, stove and sink in kitchens.
- Source: [arXiv 2202.08670](https://arxiv.org/abs/2202.08670)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Generator with rule placement vs uniform scatter at equal count; dev exact count.
- What breaks on our images: Crowd regression, 20-200 px objects.
- Moves: fixtures. Why this group: needs a generator
- Reports: lit-data-a, lit-data-b

<a id="i417"></a>
### 417. Synthesise training pages by perturbing real label graphs

- What: Generate synthetic plans by perturbing the structure of real labelled plans and re-rendering, rather than scattering symbols.
- Evidence (adjacent-field): SynthPID (2604.16513): 665 synthetic pages from 12 real seeds give node mAP 64.2 zero-real vs 67.8 real-only and 71.3 mixed; random template scattering about 30 points worse. Evaluated on the seed plans.
- Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513)
- Licence: repo 404, idea only. CubiCasa5K leakage: no.
- Cost: 20+ h (estimate)
- Experiment: Pretrain on perturbed-real renders then fine-tune on real; score dev exact-match vs real-only.
- What breaks on our images: Seeds overlap test set; OCSR shows synthetic-only fails; our real labels are plentiful.
- Moves: none. Why this group: We already have thousands of real plans
- Reports: lit-vector-a, lit-vector-b

<a id="i418"></a>
### 418. AntPlan fixture counts and placements as generator statistics

- What: Use fixture counts and placement per room type from the 505 real plans' boxes to set the generator's fixture rules; local use only.
- Evidence (search-only): 505 real plans, 4,495 room boxes, 26,716 object boxes in 92 classes (bathroom 4,145, kitchen 5,485 objects); no source images distributed; furniture labels are reviewed pseudo-labels.
- Source: [arXiv 2606.10953](https://arxiv.org/abs/2606.10953), [huggingface.co](https://huggingface.co/datasets/OldDelorean/AntPlan)
- Licence: HF card CC BY-NC 4.0 (paper page CC BY-NC-SA). CubiCasa5K leakage: unknown.
- Cost: 1 h
- Experiment: Compare generator fixture counts per room to AntPlan statistics.
- What breaks on our images: Structure boxes came from a CubiCasa5K-trained detector; schematic renderings only.
- Moves: fixtures. Why this group: not a detector training set
- Reports: lit-data-a

<a id="i419"></a>
### 419. Finnish room programme statistics for a generator

- What: Use published layout statistics (rooms per apartment, areas) to set the room programme of generated Finnish-style plans.
- Evidence (search-only): Helsinki Aurinkolahti spreadsheet of 622 units (3,787 apartments), no images (Zenodo 19894248, May 2026).
- Source: [zenodo.org](https://zenodo.org/records/19894248)
- Licence: CC BY 4.0. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Fit room programme distribution and compare to dev plans.
- What breaks on our images: No images or fixtures.
- Moves: room-types. Why this group: only for a generator we are not building tonight
- Reports: lit-data-a

<a id="i420"></a>
### 420. Floor Plan CIS: 500 real raw plans as unlabelled or hard-negative data

- What: Use the 500 real raw plans (wall masks only) as unlabelled data for self-supervised pretraining or as negatives for the detector.
- Evidence (search-only): Zenodo record 17871080, 23 MB, wall mIoU 87.91 from scratch and 88.75 after CubiCasa5K pretraining (arXiv 2512.02413). Plans collected from real-estate listings.
- Source: [arXiv 2512.02413](https://arxiv.org/abs/2512.02413)
- Licence: record tagged CC BY 4.0; third-party rights in the drawings unclear. CubiCasa5K leakage: no.
- Cost: 1 h
- Experiment: Add as unlabelled images to the pretraining arm.
- What breaks on our images: No fixture labels; rights caveat.
- Moves: windows-doors. Why this group: only useful with pretraining on drawings
- Reports: lit-data-a

<a id="i421"></a>
### 421. 1M CC BY generated furnished plans as a pretraining stage for fixtures

- What: Take one 50,000-plan shard of the CC BY 4.0 generated set (256 px, toilet, basin, sink, bathtub, shower, hob boxes; door and window segments widened by wall thickness), convert labels to COCO, and pretrain a fixture detector before fine-tuning on dev.
- Evidence (search-only): Card read only, nothing downloaded: test split counts toilet 8,021, basin 7,991, sink 5,000, bathtub 3,573, shower 4,413, hob 4,959, door 29,673; at most 20 px per metre so a toilet is about 8x14 px. No result published on any detector.
- Source: [huggingface.co](https://huggingface.co/datasets/benikm91/synthetic-floorplans-with-furnitures-for-transcription)
- Licence: dataset card CC BY 4.0; generator repository has no licence file (do not copy its code). CubiCasa5K leakage: no.
- Cost: 1-4 h on a 50k shard (estimate)
- Experiment: Pretrain on 50k, fine-tune on dev, compare with real-only per fixture class; also run a filtered 50k (nearest to dev plans by perceptual hash) against an unfiltered 50k.
- What breaks on our images: Clean 256 px line art, doors drawn as gaps without a swing arc, architect-style skia glyphs, no text, no scan degradation, no sauna.
- Moves: fixtures. Why this group: one report says try, the stricter reading holds: clean-style smoke test, null result expected beside real data
- Reports: lit-data-a, lit-data-c

## Do not try (with the reason)

<a id="i422"></a>
### 422. Negative: ArchCAD-400K as a pretraining source

- What: Skip: academic-use licence, gated, vector, window class unconfirmed.
- Evidence (floor-plans): Public subset 40K samples; HF card cc-by-nc-4.0 manually gated; pretraining gain shown only as a figure (30 vs 50 epochs).
- Source: [arXiv 2503.22346](https://arxiv.org/abs/2503.22346)
- Licence: ACADEMIC USE ONLY / CC BY-NC 4.0. CubiCasa5K leakage: unknown.
- Cost: 0
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: non-commercial and gated
- Reports: lit-data-a, lit-data-c

<a id="i423"></a>
### 423. Negative: synthetic plans added to thousands of real plans do not move the headline score

- What: Do not expect synthetic plans to raise window and door counts; budget them for rare classes and for a shippable checkpoint only.
- Evidence (floor-plans): CubiCasa5K + 3,327 synthetic plans: wall F1 +1.2 and +0.4, inside bootstrap half-width 1.3-1.7 (arXiv 2608.25608). Real traffic scenes, 4,200 real images: half-size synthetic -4 to +2.5 mAP, equal size hurt in 3 of 4 rows (arXiv 2607.27058). Microscopy, 5,000 real: add-30% 0.8952 vs 0.8947 (arXiv 2512.00078).
- Source: [arXiv 2608.25608](https://arxiv.org/abs/2608.25608), [arXiv 2607.27058](https://arxiv.org/abs/2607.27058), [arXiv 2512.00078](https://arxiv.org/abs/2512.00078)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None to run; informs priority.
- What breaks on our images: Regimes differ: rare classes may still gain.
- Moves: none. Why this group: stated so nobody spends the night on a headline gain from synthetic plans
- Reports: lit-data-a, lit-data-b, lit-data-c

<a id="i424"></a>
### 424. Negative: diffusion-generated images as labelled symbol data

- What: Do not generate labelled symbol images with a diffusion model; render from vectors where counts are known by construction.
- Evidence (adjacent-field): Counts in Stable Diffusion images: relative error 0.07 at N=1, 0.26 at 10, 0.45 at 20 (arXiv 2403.04943 Table 7). Brightfield cells: realism passed an expert test yet no detection gain (arXiv 2512.00078). Learned translation can invent strokes (arXiv 2511.15875).
- Source: [arXiv 2403.04943](https://arxiv.org/abs/2403.04943), [arXiv 2512.00078](https://arxiv.org/abs/2512.00078)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: None.
- Moves: none. Why this group: wrong counts in labels
- Reports: lit-data-b, lit-data-c

<a id="i425"></a>
### 425. Random-scatter synthetic symbols do not transfer

- What: Do not train on plans made by scattering symbols at random.
- Evidence (adjacent-field): SynthPID: template scatter about 33 edge mAP against 63.8 for topology-seeded synthetic data.
- Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: none: warning
- What breaks on our images: n/a
- Moves: windows-doors. Why this group: measured gap
- Reports: lit-market-b

<a id="i426"></a>
### 426. Synthetic-only training leaves a large real-scan gap

Reviewer's note: Synthetic data only as a supplement to real plans, never alone.

- What: Do not rely on synthetic plans alone. Keep real labelled plans as the main training set and use synthetic data only as pretraining or augmentation.
- Evidence (adjacent-field): OCSR: MolParser pretrain-only 51.9 vs 76.9 with real fine-tune (WildMol-10K, Table 4); a VLM fine-tuned on synthetic only scores .950 on clean renders but .154 on ACS real depictions (2608.09100 Table 3); the first 5% of real data gives about two thirds of the real gain.
- Source: [arXiv 2411.11098](https://arxiv.org/abs/2411.11098), [arXiv 2608.09100](https://arxiv.org/abs/2608.09100)
- Licence: n/a. CubiCasa5K leakage: no.
- Cost: 0 h
- Experiment: If a plan generator is built, train synthetic-only vs synthetic plus a small real fraction and score on dev boxes; the real fraction should dominate.
- What breaks on our images: Chemistry domain.
- Moves: none. Why this group: Supports spending effort on real labels over generators
- Also (data, adjacent-field): Negative: never train on synthetic data alone. Keep real labelled images in every training stage; synthetic-only detectors collapse on real drawings. Evidence: DETR on synthetic P&ID: 90.5 mAP synthetic test, 33.8 on two real sheets, 4.0 on 12-sheet OPEN100 (ERAMIARS 2025). Relationformer symbols mAP 26.67 synthetic-only vs 73.49 with 60 real sheets mixed in (arXiv 2411.13929). Industrial recycling: 40 vs 69 mAP on 0.01%-of-image objects (arXiv 2605.26884). Source: [arXiv 2411.13929](https://arxiv.org/abs/2411.13929), [arXiv 2605.26884](https://arxiv.org/abs/2605.26884). Experiment: None.
- Also (detect, adjacent-field): Synthetic-only detector training. Do not rely on a detector trained only on synthetic plans; keep real plans in the mix. Evidence: P&ID: synthetic-only DETR 90.5 mAP50:95 on synthetic, 4.0-33.8 on real sheets; synthetic-only Relationformer 26.67 vs 73.49 mixed on real; synthetic-only symbol finder precision 0.15-0.26 (3-4 false boxes per true). Source: [arXiv 2604.16513](https://arxiv.org/abs/2604.16513). Experiment: Not worth a run.
- Reports: lit-data-a, lit-data-b, lit-detect-b, lit-vector-b

<a id="i427"></a>
### 427. Negative: clever selection of synthetic scenes

- What: Render broadly and spend the time fine-tuning on real boxes; do not build uncertainty-targeted sampling of synthetic scenes.
- Evidence (adjacent-field): Targeted minus random +0.0050 (3 seeds) and +0.0024 (8 seeds), inside noise (arXiv 2610.09807, unreviewed preprint, camouflaged-object detection).
- Source: [arXiv 2610.09807](https://arxiv.org/abs/2610.09807)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: One generator, different image type.
- Moves: none. Why this group: no measured benefit
- Reports: lit-data-b

<a id="i428"></a>
### 428. CC BY synthetic plans generator

- What: Generator of Manhattan plans with jamb-gap doors.
- Evidence (search-only): No model or metric published; no swing arcs.
- Source: [github.com](https://github.com/benikm91/synthetic-floorplans-for-transcription)
- Licence: dataset CC BY 4.0. CubiCasa5K leakage: no.
- Cost: hours
- Experiment: Pretraining test.
- What breaks on our images: Wrong symbol picture.
- Moves: none. Why this group: wrong symbols
- Reports: lit-floorplan-a, lit-floorplan-b

<a id="i429"></a>
### 429. Negative: rule-based layout generators written by hand

- What: Do not expect a hand-written rule generator to give realistic diverse plans; derive layouts from real plans or fitted statistics.
- Evidence (search-only): Case study: loose room rules gave unrealistic plans, strict rules a stuck search; synthetic data never reached training (Zenodo 23000152, single-author, no metrics).
- Source: [zenodo.org](https://zenodo.org/records/23000152)
- Licence: CC BY 4.0. CubiCasa5K leakage: n/a.
- Cost: 0
- Experiment: None.
- What breaks on our images: Anecdote.
- Moves: none. Why this group: anecdote supporting fitted statistics
- Reports: lit-data-a

<a id="i430"></a>
### 430. Roboflow door and window sets as extra data

- What: Use only after an image-level overlap check against CubiCasa5K.
- Evidence (search-only): 402-1,497 images, CC BY 4.0 or public domain, origin unstated.
- Source: [universe.roboflow.com](https://universe.roboflow.com/university-y9nbi/floor-plans-500)
- Licence: CC BY 4.0. CubiCasa5K leakage: unknown.
- Cost: 1 day
- Experiment: Overlap check first.
- What breaks on our images: Possible CubiCasa repackages.
- Moves: windows-doors. Why this group: origin unknown
- Also (data, search-only): Negative: permissive-tagged Hugging Face copies of non-commercial plan sets. Treat every HF copy of CubiCasa5K or FloorPlanCAD as non-commercial and as leakage, whatever its YAML tag says. Evidence: Three FloorPlanCAD copies tagged cc-by-sa-4.0 while the card body says CC BY-NC 4.0; CubiCasa5K repackages tagged apache-2.0 and cc-by-4.0 on NC-SA parents. Source: [huggingface.co](https://huggingface.co/datasets/Voxel51/FloorPlanCAD). Experiment: None.
- Reports: lit-data-a, lit-data-c, lit-floorplan-a, lit-floorplan-b

<a id="i431"></a>
### 431. Moondream fine-tuning

- What: Fine-tuning is cloud only, uploads drawings.
- Evidence (search-only): Docs.
- Source: [docs.moondream.ai](https://docs.moondream.ai/finetuning)
- Licence: n/a. CubiCasa5K leakage: n/a.
- Cost: none
- Experiment: None.
- What breaks on our images: Privacy.
- Moves: none. Why this group: Ruled out.
- Reports: lit-vlm-b
