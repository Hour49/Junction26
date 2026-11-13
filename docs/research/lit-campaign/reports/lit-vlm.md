# lit-vlm: vision-language models on drawings (scope L7), merged report

Merged on 2026-11-14 from three reports (called a, b, c below): a = benchmarks, prompting, Verda models and cost; b = small open models to fine-tune; c = adjacent fields. The top-10 sources were opened again during the merge (times are 2026-11-14, Helsinki clock; "re-checked 01:24" means I read that number or licence line in the source myself). Everything else is marked "read in the source" (a report's author read it), "authors' claim" (reported, nobody reproduced it) or "search summary only". Costs and GPU hours are estimates unless a source gives them; they are marked "(estimate)". No paid API was called, nothing was downloaded except paper text, no drawing was uploaded.

Our own numbers come only from tracked files: the problem statement is `docs/research/lit-campaign/worker-brief.md` (median longest side 855 px, symbols 5 to 20 px, a third rotated, 55.3% majority baseline, 53.1% for the CubiCasa authors' weights, 59.3% for a count-only network, about 104k symbol boxes), and the training rules are `docs/decisions/0003-training-data.md` (box training on dev-split images only, weights kept local) and `docs/decisions/0006-lgpl-dependencies.md`.

## 1. Answer

Question of the scope: is "detector proposes, small model verifies marks" shown to beat either alone, and is a fine-tuned 0.2-3B model competitive with a detector on counting?

**1. Detector proposes, small model verifies: not shown on drawings. Shown only where the errors are simulated or the images are natural.**
- The one direct test on drawings is in the appendix of arXiv 2610.09313: template matching proposes candidate symbols, a VLM accepts or rejects each crop. On 34 legend drawings template matching alone gets 0.87 F1, propose-and-verify gets 0.83-0.91 for five models, none significantly different from template matching (report a, Table 2 and appendix; the paper's main Table 2 re-checked 01:24).
- Gains exist where errors were injected or the images are photographs. A VLM judge raises a P&ID detector's mAP from 0.728 to 0.925 (Gemini 2.5) and 0.882 (Gemma 3) on 500 P&IDs, but the detector's mistakes were simulated (arXiv 2510.03376, Tables 1-2, re-checked 01:24). On natural images, a 3B verifier on detector crops lifts a Grounding-DINO result from NMS-AP 36.8 to 54.4 (arXiv 2510.13232, Table S9, report a; not re-checked). OmniParser's detector lifts GPT-4V from 0.705 to 0.938 on its own screenshot test, which compares against the VLM alone, not against a trained detector alone (arXiv 2408.00203, report c).
- Nobody has published detector + verifier against a trained detector alone on CubiCasa-style rasters. All three reports looked for it and found nothing.

**2. A fine-tuned 0.2-3B VLM competitive with a detector on exact counts: no evidence for it, some against, and the cheap test is quick.**
- Closest head-to-head: Florence-2-base (0.23B) with LoRA gets mAP50 0.80 / mAP50-95 0.57 against YOLOv8/9 0.84 / 0.56-0.58 on one 5-class set of 2,818 augmented images (arXiv 2503.04918, table rows re-checked 01:24). Boxes, not counts, one dataset.
- Against: Qwen2.5-VL-7B has MAE 17.06 on dense surgical-instrument counting where a trained specialist has 0.88 (WACV 2026, Chain-of-Look, report b and c, not re-checked). Generic VLMs score 0.8-1.1 F1 on 91-box dense images where a purpose-trained 3B detection model scores 78.4 (arXiv 2510.12798 Table 4, report b). Open models score 0-3% exact match on the HoloCount high-density subset (arXiv 2607.06420, report b). A Qwen2.5-VL-3B adapter fine-tuned on CubiCasa5K gets 3.4% exact whole room-program match (model card, n=149, self-reported; report b and c).
- For: fine-tuning a 3B VLM to write points first and count them lifts real-photo accuracy from 70.00 to 81.90 and, past the training count range, from 30.86 (own count) to 80.20 (number of points written) (arXiv 2603.21746 Tables 1-2, re-checked 01:24; photos with 1-10 objects, not line art).
- On doors and windows specifically, emitting coordinates is the weak path: the same network read out as a coordinate sequence gets opening F1 0.246 on CubiCasa5K test and 0.644-0.799 when the openings are read from its dense heatmap (arXiv 2608.25608, re-checked 01:24).

**3. Zero-shot VLMs do not count doors and windows.** On 120 plans (CubiCasa5K, CVC-FP, web) exact match per field is door 0.39 / window 0.34 for the best model (Gemini 3 Pro), 0.28 / 0.27 GPT-5.2, 0.16 / 0.16 Claude Opus 4.5, 0.09 / 0.03 GLM-4.6V, 0.09 / 0.10 Qwen3-VL-8B (arXiv 2601.04819 Table 1, re-checked 01:24). Text-labelled classes are fine (bedroom 0.76-0.91, toilet 0.76-0.82). The majority-answer baseline is 13.2% (windows) and 11.6% (doors) (worker-brief).

**4. What lifts a VLM on small symbols is geometry, not wording.** Enlarge each target to about 1.5 visual tokens per side, never zoom out, overlap views by one object: floor-plan mosaic recall 0.25 to 0.43 (Gemini 3.8) and 0.05 to 0.12 (Qwen3-VL), flat for the strongest model (arXiv 2610.09313 Table 2, re-checked 01:24). The same paper finds tiles can score below the whole image for strong models on real floor-plan blocks (0.53 vs 0.60 and 0.64 vs 0.71, report a, not re-checked).

**5. Out-of-distribution plans are the larger risk.** The CubiCasa5K model scores IoU 0.099 (doors) and 0.202 (windows) on web floor plans (WAFFLE, arXiv 2412.00955 Table 4, report b). 829 of our 959 sealed eval drawings are in CubiCasa5K train (worker-brief), so any checkpoint that saw CubiCasa5K cannot be scored on them.

**6. Design rule all three reports reach:** have the model list items (boxes or points in a fixed reading order) and count them in code; never accept a number the model writes. Support: Molmo ablation, point-then-count 86.3 vs count-only 80.2 on PixMo-Count (arXiv 2409.17146 Table 4, report b and c); a transcription plus code counts right where a chain-of-thought count does not (arXiv 2611.08998, report a); a P&ID harness raises exact match from 36.7-41.3% to 74.3-76.0% when the VLM may only query a detector's graph (arXiv 2609.05880, report a and b).

**7. Verda models.** Kimi K3.1 Pro ($2.00 in / $10.00 out per 1M tokens) and DeepSeek V4.1 Flash ($0.15 / $0.60) have no published result on plans, counting or CAD from anyone but the vendors' own cards (report a, verda.com/pricing read 00:23, not re-checked). One plan costs about $0.016 (Kimi) or $0.0012 (DeepSeek) at native size with symbols enlarged to 1.5 tokens, and about $0.09 / $0.007 for 5 px symbols (report a's arithmetic, estimate; output tokens can multiply it).

## 2. Top 10, ranked across all three reports

Hours are to a first number on our data and are estimates. GPU memory: weights in fp16 from the parameter counts re-checked in the HF API (Qwen3-VL-2B 2.13B, 4B 4.44B, Qwen3.5-2B 2.27B, Florence-2-base 0.23B, Falcon-Perception 0.63B), plus an unmeasured allowance for activations. "Tonight / Saturday" count against the Saturday 14 Nov 22:00 deadline. Our symbols (5 to 20 px, median image 855 px) sit below one visual token for every model here (32 px per token for Qwen3-VL and Qwen3.5, 32 px for Florence-2 at 768 px input; 16 px patches for Falcon Perception), so every entry needs tiling or enlargement.

### 1. Point-then-count LoRA on Qwen3-VL-2B/4B (Apache-2.0), count by code
- **What it is.** Fine-tune a small VLM to write one point (or box) per window, door and fixture in a fixed reading order, then count the list in code; add the vision tower to the trainable parts. Recipe from "Getting to the Point" (arXiv 2603.21746) on Qwen2.5-VL, LLaVA-OV and InternVL3.5; the same format wins in Molmo (arXiv 2409.17146).
- **JSON field.** `elements` (class + position per instance; counts derived); confidence from agreement between the point count and any stated count.
- **Measured number.** Real photos, 1-10 objects, accuracy direct vs point-then-count: Qwen2.5-VL-3B 70.00 / 81.90 (Table 1). Synthetic out-of-distribution counts, own count / points then count / count of points: 3B 30.86 / 19.44 / 80.20, 7B 32.00 / 46.19 / 94.96 (Table 2). Training: 452,709 synthetic samples plus about 1,160 real photos (report c; the real-set size is not in my grep, the synthetic size and LoRA r=32, alpha 64 are re-checked 01:24). Support from Molmo Table 4 (86.3 vs 80.2) and from grounded-reasoning work: +3.6 CountQA, +2.6 FSC-147 with Qwen3-VL-8B (arXiv 2611.08485, report b and c, not re-checked).
- **Licences.** Code: MIT (Getting-to-the-Point repo, re-checked 01:24). Weights: none released. Base models: Qwen3-VL-2B/4B-Instruct apache-2.0 (HF API, re-checked 01:24); Qwen2.5-VL-3B is the Qwen Research licence (non-commercial), so do not use the paper's 3B.
- **CubiCasa5K leakage.** No for the recipe (paper uses tabletop photos and synthetic data). Our own adapter must be trained on dev-split boxes only (record 0003). No checkpoint of Qwen3-VL states its training data; no report found floor plans in the Qwen3-VL report text (report b and c grep).
- **GPU / hours.** 2B: about 4.3 GB of weights; LoRA at 700-5,000 image tokens per tile is unmeasured, plausible on a 12-16 GB card with batch 1 (estimate). The official finetune script pins flash-attn and bf16, so write a plain transformers + PEFT loop with sdpa and fp16 (report b). First number: 4-8 h including the data loader (estimate). The paper's own runs took up to two days each on an A100 80 GiB.
- **What breaks on our images.** Every number is on photos with up to 20 objects. A 10 px symbol is 0.3 of a 32 px token, so points drift unless tiles are enlarged 2-3x (Qwen3-VL 2x tile: about 530 tokens, 3x: about 820 tokens, report b arithmetic). A window is two lines touching a wall, the case where VLMs fail (arXiv 2407.06581: 58% mean accuracy on touching/overlapping line shapes, and a fine-tune plateau of 36.8%, report b and c). Qwen3-VL's own cookbook says it loops above 40-50 instances and merges clusters, so tile to at most about 30 instances. Rotated third: train on rotated copies. Include empty-class tiles, or the model invents sauna stoves.
- **Verdict: try tonight.** It is the only entry that tests the claim "a small VLM can count" on our boxes, and a failure is also informative.

### 2. Tile-and-enlarge rule for any VLM call (training-free)
- **What it is.** "Why VLMs Miss Small Objects" (arXiv 2610.09313): enlarge each target to S = 1.5 visual tokens per side, cut views without zooming out, overlap views by one object, merge in code.
- **JSON field.** `elements` from a prompted VLM; also the tiling for entry 1 and 3.
- **Measured number.** 60 floor-plan mosaics, recall whole to rule: Gemini 3.8 0.25 to 0.43, Qwen3-VL 0.05 to 0.12 (significant), GPT-6.1 0.63 to 0.61, Claude Opus 5.5 0.51 to 0.56 (Table 2, re-checked 01:24); no training set (prompting).
- **Licences.** Code MIT (repo shijunzhe/vlm-small-objects, re-checked 01:24). No weights.
- **Leakage.** Not applicable (no training); the mosaics come from FloorPlanCAD (report a).
- **GPU / hours.** API calls or a self-hosted 4-8B model; about $0.016 per plan on Kimi K3.1 Pro at 12 px symbols (report a, estimate). First number: 2-4 h (estimate).
- **What breaks.** Mosaics are CAD renders, not scans; no rotation test; tokens grow about 3-7x over one call; overlaps double-count unless merged in code (the paper counts duplicates against precision). Report a also found tiles scoring below the whole image for two strong models on real floor-plan blocks, so test whole vs tiles on dev first.
- **Verdict: try tonight** as the cheap first arm (zero-shot or with entry 1's tiles); one afternoon, no training.

### 3. Florence-2 (0.23B/0.77B) as a tile-level symbol detector
- **What it is.** Florence-2 writes boxes as location tokens after a task prompt; LoRA or full fine-tune on tiles cut from our boxes.
- **JSON field.** `elements` (boxes per class per tile).
- **Measured number.** LoRA r=8 on 2,818 augmented images (1,788 raw, 5 classes), L4 24 GB, about 10 epochs: mAP50 0.80, mAP50-95 0.57; YOLOv8 0.84 / 0.56, YOLOv9 0.84 / 0.58, YOLOv10 0.74 / 0.48; SGD gives 0.60 and lr 1e-6 gives 0.56, so it is sensitive (arXiv 2503.04918, table rows re-checked 01:24). Full fine-tune on 400 mechanical drawings, F1 61.51 against GPT-4o 35.51 and Claude-3.5 40.36 (arXiv 2411.03707, re-checked 01:24). TinyClick: Florence-2-base 4.6 to 73.8 on small-target GUI clicks with 56 GPU-hours (arXiv 2410.11871, report b, not re-checked).
- **Licences.** Code and weights MIT (microsoft/Florence-2-base and florence-community/Florence-2-base, HF API re-checked 01:24). Use the `florence-community` transformers-native copies: the original remote code breaks on transformers >= 4.52 (report b, HF threads).
- **Leakage.** No floor plans found in the Florence-2 paper (report b grep of 8 reports; not proof about web crawls).
- **GPU / hours.** 0.23B model: fits any of our cards for LoRA or full fine-tune (estimate); the LoRA paper's figure is about 4 h on an L4 for 2,818 images (report b; not re-checked). Our box set is about 37x that count (boxes vs images, not like for like): 6-10 h for 10 epochs (report b estimate). First number: 3-5 h after the loader exists (estimate).
- **What breaks.** 768 px input and 32 px per token: a 10 px symbol is 0.3 token at native scale; tile 2x2 with overlap and upscale 1.75-2.5x (report b arithmetic). A box costs about 45 characters, so keep targets under about 40 boxes per tile (HF thread #96); set `no_repeat_ngram_size=0` for box decoding (the shipped default of 3 can block a row of identical windows). Small VLMs localise worse than detectors even with millions of pages: SmolDocling layout mAP 0.231 vs human 0.82 (arXiv 2503.11576, report b and c). A purpose-built detector (other scope) should beat it; this is the VLM-family arm.
- **Verdict: try tonight** as the small-model detector arm; compare with the detector from the floor-plan scope on the same dev tiles.

### 4. Falcon Perception 0.6B as a zero-shot dense probe
- **What it is.** A 0.6B early-fusion model with explicit instance output at native resolution up to 1024 px with 16 px patches; RL revision tuned for dense scenes (arXiv 2608.18881; base report arXiv 2603.27365).
- **JSON field.** `elements` counts per class (probe only).
- **Measured number.** Authors' benchmark PBench dense split (up to 500 instances), mask F1 72.3 to 80.5 with RL (model card table, re-checked 01:24); box F1 73.9 vs 37.4 for Rex-Omni (paper appendix, report b, not re-checked). Authors' claim on their own benchmark; no drawing result anywhere.
- **Licences.** Code Apache-2.0 (tiiuae/Falcon-Perception, gh api re-checked 01:24); weights apache-2.0 (HF API re-checked 01:24). Inference repo only: no training code (report b read the tree).
- **Leakage.** Unknown: training data are web images and documents, 54M images, no floor plans named (report b).
- **GPU / hours.** 632M parameters, about 1.3 GB in fp16 (HF API count). About 1 GPU-hour for 10 plans (report b estimate). It needs FlexAttention/Triton and CUDA wheels, so it will not run on a ROCm card (report b read pyproject).
- **What breaks.** Natural images; line-art symbols of 5-20 px are not objects with texture; no way to fine-tune, so a poor probe ends the idea.
- **Verdict: try tonight (probe only).** One hour answers whether a native-resolution dense model sees our symbols at 0.6 patch.

### 5. Read doors and windows from a dense detection head, not as emitted coordinates
- **What it is.** A study of one network read out two ways, as an autoregressive coordinate sequence and from its dense heatmaps (arXiv 2608.25608). The lesson: openings are a local detection problem; an emit-coordinates model degrades as the list grows.
- **JSON field.** `elements` (windows, doors); not toilets, sinks, showers, stoves.
- **Measured number.** CubiCasa5K official test, n = 287: opening F1 0.246 (sequence) to 0.644 (heatmap, door/window family heuristic) and 0.799 (family ignored); a 200K-parameter door/window head reaches 0.988 family accuracy; Gemini 3.1 Pro on clean renders scores openings 0.752 at about US$6 per 200 plans (all re-checked 01:24). Cross-check: Raster2Seq reaches Window & Door F1 77.8 at 256 px on CubiCasa5K (arXiv 2602.09016, Table 1, reports b and c, not re-checked). Training: CubiCasa5K train (size not re-read).
- **Licences.** Code MIT (Cyprinus12138/fpvec-lab, re-checked 01:24). Weights: release not found; Raster2Seq's official checkpoints are cc-by-nc-4.0 (report c, HF card, not re-checked).
- **Leakage.** **Yes**: trained on CubiCasa5K train, evaluated on its test; any checkpoint is leakage-flagged and non-commercial for scored runs.
- **GPU / hours.** Not read. Use as design guidance, not as a checkpoint.
- **What breaks.** 256 px input, single independent author, opening F1 from an internal matcher (not an exact per-plan count), and re-scoring one checkpoint against corrected CubiCasa5K annotations moved opening F1 from 0.29 to 0.66 (report c, appendix F, not re-checked): numbers from different papers on CubiCasa5K are not comparable.
- **Verdict: idea only for the weights, use as the argument for a comparison arm** (dense detector vs entry 1 on the same dev plans, Saturday).

### 6. Licence-clean synthetic plans with exact labels, plus camera-style augmentation
- **What it is.** Rendered plans where doors, windows and furniture have exact boxes: `benikm91/synthetic-floorplans-for-transcription` (450,000 train plans, 512 px, 6 px walls, door and window gaps) and `...-with-furnitures-for-transcription` (1,000,000 train plans, 256 px, 3 px walls; classes include toilet, basin, sink, bathtub, shower, hob; one symbol style per plan); also `fpgen` in fpvec-lab (procedural generator, four style families, scan-like degradations) and ResPlan-FP (16,998 plans).
- **JSON field.** `elements` (pretraining or a 30% mix for entries 1 and 3); `rooms` outlines not labels (no printed text).
- **Measured number.** None on our task. Transfer evidence: TechING synthetic-only LoRA on 115,014 diagrams gives real hand-drawn average F1 x6.97 (arXiv 2601.18238, abstract, report b and c); SynthPID 63.8 edge mAP with no real P&IDs (arXiv 2604.16513, report c); SMT++ symbol error 32.1 to 5.6 with synthetic pretraining plus curriculum (arXiv 2405.12105, report c); a synthetic counting set transfers to PixMo-Count but not back (arXiv 2602.00108, report b). The dataset sizes and licences above were re-checked 01:24.
- **Licences.** Data cc-by-4.0 for all three datasets (HF API re-checked 01:24). Generator repo for the benikm91sets: no licence file (reports b and c; not re-checked); fpvec-lab code MIT, its corrected-CubiCasa5K part is non-commercial (cc-by-nc-sa-4.0 on the hub, report c).
- **Leakage.** No for the synthetic sets; ResPlan-FP derives from listing renderings with undisclosed source platforms (report c, LICENSE read): the label is clear, the origin is not audited.
- **GPU / hours.** Download and wire a shard: about 1 day (report c estimate); it is only data.
- **What breaks.** Manhattan walls, one clean style per plan, no printed text, no scans or rotation, no sauna stove class in any set (CubiCasa5K has one: `SaunaStove`, report c), 6-20 px symbols at 256-512 px match our size range but their shapes do not match real symbol variants (CubiCasa5K has six sink and six shower variants). Layout realism, not symbol rendering, drove the SynthPID result: reuse real room and wall topology.
- **Verdict: try Saturday** as an extra pretraining or mixing arm for entries 1 and 3, only after those have a first real-data number.

### 7. Detector proposes, small VLM judges crops
- **What it is.** A detector's boxes are cropped (padded, enlarged) and a small VLM answers yes/no or the class; a second pass can re-detect in flagged regions.
- **JSON field.** `elements` and per-element confidence and proof (the crop that was accepted).
- **Measured number.** P&ID judge: missing-object assessor F1 0.876 (Gemini 2.5) and 0.815 (Gemma 3), mAP 0.728 to 0.925 and 0.882 (arXiv 2510.03376 Tables 1-2, re-checked 01:24); errors were simulated; with only a red box and no text tag recall was 0.32 (report b). Crop-and-verify NMS-AP 36.8 to 54.4 (arXiv 2510.13232 Table S9, not re-checked). On drawings, template matching + VLM verifier 0.83-0.91 F1 vs template matching alone 0.87, no gain (arXiv 2610.09313 appendix, report a).
- **Licences.** No code for the P&ID paper. The pattern needs a detector (other scope; Ultralytics YOLO is AGPL, out) and a VLM (Qwen3-VL-2B/4B Apache-2.0).
- **Leakage.** Depends on the detector.
- **GPU / hours.** One small-VLM forward per crop, about 300 crops per plan: seconds to minutes per plan (report b). First number 3-6 h once a detector exists (estimate).
- **What breaks.** The judge cannot fix a symbol the detector never proposed; 10 px crops carry little unless enlarged to about 48 px; our confusions (door swing vs window, double lines) are not the negations of the natural-image paper; all positive evidence is on simulated errors or natural images.
- **Verdict: try Saturday offline**, expectation low (report a and the appendix result agree).

### 8. Count-reward RL (GRPO) on an SFT checkpoint
- **What it is.** After entry 1's SFT, reward exact count and point accuracy with a Gaussian/range shaping, 2K samples, 4-8 rollouts.
- **JSON field.** `elements` counts.
- **Measured number.** REC-RL, Qwen2.5-VL-3B MAE val/test: zero-shot 9.24 / 9.67, SFT on all data 8.63 / 8.90, fuzzy-reward GRPO on 2K samples 5.65 / 5.86, REC-RL 5.48 / 5.48 (arXiv 2605.16460 Table 1, re-checked 01:24); a 1,000-sample student report goes 34.84 to 67.94 counting accuracy on 100 test images (report c); CrowdVLM-R1 3B MAE 73.67 to 25.16 on 3,803 images (arXiv 2504.03724, report b).
- **Licences.** Tooling EasyR1, VLM-R1, TRL, WS-COC all Apache-2.0 (gh api, EasyR1 and VLM-R1 re-checked 01:24).
- **Leakage.** None from the method.
- **GPU / hours.** Published scripts use 8 GPUs; no single 12-16 GB run is documented; rollouts multiply memory (reports b and c). 8-12 h including debugging (report c estimate).
- **What breaks.** MAE on natural scenes, not exact match; reward hacking with single-term rewards; a blank-canvas control is needed because RL gains can appear without an image (arXiv 2610.01908, report b).
- **Verdict: idea only for tonight; try Saturday** only if entry 1 gives a usable SFT checkpoint.

### 9. Zero-shot frontier row on our dev split (AECV-Bench protocol)
- **What it is.** Run one or two frontier VLMs with the benchmark's counting prompt on our dev plans for a baseline row (arXiv 2601.04819).
- **JSON field.** None (a score row); it also fixes the cost of the "just ask the model" option.
- **Measured number.** See answer 3; table re-checked 01:24. 120 plans, exact match per field, plus MAPE.
- **Licences.** Benchmark repo AECFoundry/AECV-Bench has no licence file (report c, gh api; not re-checked). Needs paid APIs.
- **Leakage.** The benchmark's plans include CubiCasa5K plans, so a score of a model that saw them is inflated; not applicable to API models without training on our data.
- **GPU / hours.** No GPU; 20-image pilot under $2 on Kimi/DeepSeek (report a estimate, not run). 2 h.
- **What breaks.** Ground-truth rules (adjacent windows counted as one group) differ from ours; the paper's numbers are not comparable to our exact match.
- **Verdict: try tonight only if the owner approves the pilot cost;** otherwise skip, the answer is already near 0.1-0.4.

### 10. Rotation and photo normalisation before any model
- **What it is.** A small orientation classifier (0/90/180/270) trained on rotated copies of our own plans; adaptive binarisation or cleaning of scans and phone photos to the rendered style before inference.
- **JSON field.** All (preprocessing); also `plans`.
- **Measured number.** A fine-tuned Phi-3.5-Vision encoder as a 12-class rotation classifier reaches 98% and 96% on two datasets and lifts OCR for closed models by up to 20% (arXiv 2511.04161, abstract re-checked 01:24); a 90 degree turn costs 7-11B VLMs 1.5-6 points on a relation benchmark (arXiv 2605.05045, report c); binarising real inputs lifts a synthetic-only model's Dice 0.4393 to 0.5256 (arXiv 2606.02434, report c).
- **Licences.** Not checked for the rotation paper; a classifier on our own data needs none.
- **Leakage.** None; labels are free (rotate our own plans).
- **GPU / hours.** Small classifier, under 1 h (estimate).
- **What breaks.** All evidence is text documents or relation questions, not symbols; no paper tests rotation on drawings; a single global threshold fails on shadows.
- **Verdict: try Saturday** only if the detector and VLM numbers show a gap on the rotated third.

## 3. Full table

"from": a, b, c. "evidence": R = read in the source (by the report's author), A = authors' claim, S = search summary only. "CC5K" = CubiCasa5K in the checkpoint's or method's training data.

| Item | Field | from | evidence | Key number | Code / weights licence | CC5K | Verdict |
|---|---|---|---|---|---|---|---|
| Point-then-count (2603.21746) | counting VLM | c | R, re-checked | 70.00 to 81.90 (3B); 30.86 to 80.20 OOD | MIT / none | no | try tonight |
| Molmo / PixMo-Points (2409.17146) | counting VLM | b, c | R | point-then-count 86.3 vs 80.2 | Apache-2.0 / Apache-2.0 | no | format source |
| Molmo2-4B/8B (2601.10611) | counting VLM | b, c | R | PixMo-Count 88.1 / 88.5 vs Qwen3-VL-4B 58.0 | Apache-2.0 / card Apache-2.0 plus a non-commercial third-party-data sentence | n/s | try; licence caveat |
| MolmoPoint (2603.28069) | pointing VLM | b, c | R | +4 PixMo-Points; +5 ScreenSpot-Pro vs text coords | Apache-2.0 / same caveat | n/s | idea (grounding tokens) |
| Qwen3-VL 2B/4B/8B (2511.21631) | base model | a, b, c | R, re-checked | CountBench Instruct 84.1 / 89.4 / 91.5 (Table 4) | Apache-2.0 / Apache-2.0 | n/s | base for 1 |
| Qwen3.5-0.8B/2B/4B | base model | b | A (card) | 2B CountBench 91.4 / 86.8 (modes unlabeled) | Apache-2.0 | n/s | alternative base |
| Tile-and-enlarge rule (2610.09313) | ours | a | R, re-checked | floor-plan mosaics recall 0.25 to 0.43, 0.05 to 0.12 | MIT / none | no | try tonight |
| AECV-Bench (2601.04819) | ours | a, b, c | R, re-checked | door/window 0.39/0.34 best | no licence file | includes CC5K plans | baseline row |
| Florence-2 LoRA (2503.04918) | detection by VLM | b | R, re-checked | mAP50 0.80 vs YOLOv8/9 0.84 | MIT / MIT | no | try tonight |
| Florence-2 on drawings (2411.03707) | ours | a, b, c | R, re-checked | F1 61.51 vs GPT-4o 35.51 | MIT (base) | no | evidence |
| TinyClick (2410.11871) | GUI | b | R (abstract+method) | 4.6 to 73.8 | MIT base | no | evidence |
| Falcon Perception 0.6B (2608.18881) | detection VLM | b | R card, re-checked | dense mask F1 72.3 to 80.5 (authors' benchmark) | Apache-2.0 / Apache-2.0 | unknown | probe tonight |
| Falcon-OCR 0.27B | OCR | b | A (card) | none read | Apache-2.0 | unknown | flag for room labels |
| Readout study (2608.25608) | ours | c | R, re-checked | openings 0.246 to 0.644/0.799 | MIT / not found | yes | design evidence |
| Raster2Seq (2602.09016) | ours | b, c | R | Window & Door F1 77.8 | MIT / cc-by-nc-4.0 | yes | leakage |
| FloorplanVLM (2602.06507) | ours | a, b, c | R | opening F1 0.7333; 32 H200; 2M+300K plans | no release found | own corpus | recipe only |
| CC5K room-program adapters (BDivyesh, mudasir13cs, etc.) | ours | a, b, c | R (cards) | exact whole program 3.4%; bedroom count 55.6%, n=149 | NC / NC | **yes** | skip |
| Minicpmv4-floorplan LoRA (Barath) | ours | b | R (card) | F1@0.5 0.105 on FloorPlanCAD | Apache-2.0 | no (FloorPlanCAD) | evidence: box fine-tune can fail |
| Rex-Omni 3B (2510.12798) | detection VLM | b, c | R | Dense200 F1 78.4 vs generic Qwen2.5-VL 0.8-1.1 | non-commercial | not found in text | local only; skip |
| SmolDocling (2503.11576) | doc VLM | b, c | R | layout mAP 0.231 vs human 0.82 | docling MIT / cdla-permissive-2.0 | no | caution |
| Detector + VLM judge on P&IDs (2510.03376) | ours | a, b, c | R, re-checked | mAP 0.728 to 0.925 (simulated errors) | none | no | try Saturday |
| Crop-and-verify (2510.13232) | detection | a | R (Table S9) | NMS-AP 36.8 to 54.4 | not checked | no | try offline |
| P&ID graph harness (2609.05880) | ours | a, b | R | exact match 36.7-41.3% to 74.3-76.0%; LoRA planner collapsed | detector AGPL | no | design evidence |
| Handoff-H1 (2608.15032) | ours (takeoff) | a, c | R, re-checked | composite 81.6 vs 61.4 best frontier agent; Windows & Doors 88 vs 47-69 | harness repo: no licence file found; system closed | unknown | design signal |
| OmniParser (2408.00203) | GUI | c | R | GPT-4V 0.705 to 0.938 | icon_detect AGPL; detect_v3, caption MIT | no | licence trap |
| PaddleOCR-VL (2510.14528) | doc VLM | c | R | detector + 0.9B reader chosen for stability (no ablation) | Apache-2.0 | no | design only |
| LED-BENCH (2610.19571) | ours | a | R | 4 overlapping crops +12.96 points | not checked | n/a | expected tiling gain |
| CrossProjection (2608.00473) | ours | a | R | free coordinates 8-76% vs categorical 62-82% | not checked | none | design rule |
| Seeing vs. Counting (2611.08998) | diagrams | a | R (abstract, intro) | rotated second read 86/96 vs 57/96 | not checked | none | idea |
| K-OPSD (2609.34082) | ours (AEC) | a, b | R | judge 0.771 to 0.819 (4B); combined accuracy 0.738 unchanged; n=42 | Apache-2.0 base | benchmark data | idea |
| WAFFLE (2412.00955) | ours | a, b | R | CC5K model on web plans: doors IoU 0.099 | dataset licence not read | yes (model) | warning |
| DoorDet (2508.07714) | ours | a, b | R | Co-DETR mAP@50 0.793 | not checked | yes (CC5K re-labelled) | leakage |
| HoloCount (2607.06420) | counting benchmark | a, b | R | high-density exact 0-3% open models; 49.0% Gemini-3.1-Pro | n/a | no | context |
| Chain-of-Look (WACV 2026) | counting | b, c | R | MAE 0.88 vs Qwen2.5-VL-7B 17.06 | NOASSERTION | no | specialist wins |
| CrowdVLM-R1 (2504.03724) | counting RL | b | R | 3B MAE 73.67 to 25.16; T-Rex 4.37 vs 3B SFT 1.83 at counts 1-20 | not checked | no | context |
| REC-RL (2605.16460) | counting RL | b, c | R, re-checked | MAE 5.48 vs SFT 8.63 | n/c | no | maybe |
| Waterloo CoT counting | counting RL | c | R (student report) | 34.84 to 67.94, 100 test images | n/c | no | caution |
| Dr. Seg (2603.00152) | RL perception | c | R | Pixmo val 74.6 | Apache-2.0 | no | maybe |
| WS-COC (2602.12774) | counting VLM | c | R | FSC-147 test MAE 13.91; 18.7 GB | Apache-2.0 | no | idea (range questions) |
| Counting to Four (2604.10039) | diagnostic | a, b, c | R | SFT count text 14-17% exact on FSC-Test | n/c | no | caution |
| [De|Re]constructing counting (2510.19555) | mechanism | c | R | linear probe decodes count; output path loses ~30% | repo named | no | idea |
| Give the Model a Finger (2610.27756) | counting audit | b, c | R | tool loops "mostly fail"; R80 spans 3-150 dots | n/c | no | caution |
| BlindTest (2407.06581) | line art | a, b, c | R | 58.07% mean; fine-tune plateau 36.8% | n/c | no | caution |
| SOUBench (2604.22884) | small objects | c | R | best 58.97% vs human 82.5%; 11k SFT +1.2-1.7 | none | no | evidence |
| CountQA (2508.06585) | counting benchmark | a, c | R | best exact 42.9% | n/c | no | context |
| VLMs Know Where to Look / ViCrop (2502.17422) | zoom | a, c | R | V* 42.41 to 62.30 | no licence file | no | idea |
| AdaGround (2610.36874) | GUI zoom | a, c | R | ScreenSpot-Pro 51.3 to 66.2 (8B), 55.3 to 75.9 (32B); fixed 4x crop already 63.5/73.9 | MIT | n/a | idea (size zoom in tokens) |
| DeepEyes / Mini-o3 / ZoomEye / CropVLM | zoom | a, c | R | V* 71.2 to 90.1 (DeepEyes) | Apache-2.0 (code) | no | idea |
| GroundCascade (2611.13177) | GUI | c | R | 85.33, 2.42-2.73 calls | n/c | n/a | idea (gating) |
| Chain-of-Ground (2512.01979) | GUI | c | R | 68.4 | n/c | n/a | idea |
| MHVF, ReLaViS, ZoomClick, GUI-Eyes, Ferret-UI Lite, ZonUI-3B, ShowUI-2B, UGround | GUI grounding | b, c | R | ScreenSpot-Pro 23.6 to 53.6 (MHVF); ZonUI-3B 28.7 on one 4090 | mixed; ZoomClick none; ZonUI card Apache over an NC base | n/a | evidence on size and data |
| SAM 3 (2511.16719) | segmentation | a | R | CountBench 93.8; verifier +7.2 cgF1 | SAM License (not OSI) | none | maybe; licence |
| Mini-Monkey, ZwZ | tiling | b | R | OCRBench 806 (2B) | MIT / n/r | n/a | idea |
| DePlot (2212.10505) | chart to table | c | R | resolution 24.8 to 74.9 RMS-F1 | Apache-2.0 | n/a | idea |
| ChartMoE, TinyChart, UniMERNet | chart/formula | c | R | ChartQA 84.64; 1.36M samples, 32 V100 | mixed | n/a | recipe too big |
| MolScribe (2205.14311) | molecule | b, c | R | 76-93%; 1.68M examples | MIT | n/a | idea |
| SMT++ (2405.12105) | music | c | R | SER 32.1 to 5.6 | MIT | n/a | idea |
| Design2Code (2403.03163) | screenshot to code | c | R | models miss visual elements | n/c | n/a | idea |
| TechING (2601.18238) | diagram to code | b, c | R | real F1 x6.97 | paper NC-SA | n/a | idea |
| Hitachi binarisation (2606.02434) | sim-to-real | c | R | Dice 0.4393 to 0.5256 | n/c | n/a | idea |
| Rotation papers (2511.04161, 2605.05045) | orientation | c | R | 98%/96%; -1.5 to -6 points | n/c | n/a | try Saturday |
| Real5-OmniDocBench (2603.04205) | photo robustness | c | R | PaddleOCR-VL 94.74 scan to 92.66 skew | n/c | n/a | context |
| Synthetic plan sets (benikm91, fpgen, ResPlan-FP, ResPlan) | data | b, c | R, re-checked | cc-by-4.0, 450k / 1M / 16,998 / 17,000 plans | see entry 6 | no | try Saturday |
| FloorPlanCAD | data | c | R | 15K CAD plans, 30 classes | annotations CC BY-NC 4.0 on project page; mirrors say cc-by-sa | n/a | local only |
| CubiCasa5K | data | c | R, re-checked | 52 icon classes incl. SaunaStove | GitHub NOASSERTION (text read by c: CC BY-NC); Zenodo cc-by-nc-sa-4.0 | n/a | non-commercial |
| Voix7/rtdetrv2-floorplan-v2 | detector | a, b, c | A (card) | mAP 0.666, window 0.771, door 0.685 | Apache-2.0 | unknown (dataset "unknown") | lead; leakage unknown |
| GreenMap/qwen3-vl-ru-blueprint-extractor | ours | b | A (card) | none; author warns against use | Apache-2.0 | no | skip |
| PaliGemma 2 / Gemma 3n | VLM | a, b | R | Syngenta case study: 3B LoRA recall 80.3% vs 10B 66.2% (vendor) | Gemma terms | n/a | skip |
| Gemma 4 E2B/E4B | VLM | b | R, re-checked | no grounding number on card | Apache-2.0 | unknown | below Qwen |
| InternVL3.5-2B/4B | VLM | b | R | RefCOCO avg 85.5 (2B), 89.4 (4B) | Apache-2.0 (Qwen3 base) | n/s | alternative base |
| Moondream2/3 | VLM | b | R | fine-tuning only in the vendor's cloud | Apache-2.0 / other | n/a | skip (drawings would be uploaded) |
| Qwen2.5-VL-3B | VLM | b, c | R | n/a | Qwen Research Licence (non-commercial) | n/a | skip |
| Kimi K3.1 Pro (Verda) | frontier VLM | a | A (card) | PerceptionBench 68.3; ZeroBench 29.8; no plan result | modified MIT | n/a | unmeasured |
| DeepSeek V4.1 Flash (Verda) | frontier VLM | a | A (card) | PerceptionBench 47.7; ZeroBench 11.8; no plan result | MIT | n/a | unmeasured |
| Qwen3-VL cookbook limits | vendor note | b | R | loops above 40-50 instances | Apache-2.0 | n/a | design rule |
| Pix2Seq early stop (2109.10852) | detection | b | R | recall suffers when the list ends early | n/c | no | design warning |

## 4. Transfers from other fields

Our object: a window or door cell, a fixture, a room label, 5 to 20 px on line art. Code usable "as is" means the repo runs on our images without training.

| Field | What plays the role of our object | Why it transfers | What breaks | Code |
|---|---|---|---|---|
| Counting by pointing (Molmo, 2603.21746) | one point per window | the count follows the list; beats the model's own number past the training range | photos with 1-10 objects; touching lines; 0.3 token per symbol | needs fine-tuning |
| GUI grounding (ScreenSpot-Pro, ShowUI, AdaGround) | a small icon on a large screen | the same size problem: average target 0.07% of the screen; ours 0.0034% to 0.0547% of an 855 px square (report c arithmetic) | a single target per query; 8-32B models for the zoom numbers; 2-3B models reach 28.7-44.8% | AdaGround code MIT, idea only for small models |
| Remote sensing counting (SkyMoE) | many small objects in a tile | count-varying cutout: erase some objects, lower the label (+9.47% counting) | needs repainted wall gaps; aerial context absent | idea only |
| Image to markup: chart, formula, molecule, music (DePlot, MolScribe, SMT++, UniMERNet) | bar, token, atom, note | a renderer gives unlimited exact labels; small models (0.1-0.3B) suffice with 1M rendered pairs | we have no renderer for CubiCasa-style symbols except the synthetic sets in entry 6 | idea only |
| Document parsing (PaddleOCR-VL, SmolDocling) | page element | detector finds elements, a small VLM reads crops; end-to-end box output is weak (mAP 0.231) | no ablation against end-to-end; read content, not geometry | idea only |
| P&ID and engineering drawings | symbol on a pipe or sheet | same line-art symbols; detector first, VLM judges crops; a graph harness gives +35 points | simulated errors; AGPL YOLO in the detector | pattern only |
| Surgical-instrument dense counting (Chain-of-Look) | identical items in a tray | a trained specialist beats a 7B VLM 19x on MAE | photographed large objects | idea only |
| Camera-captured documents (Real5-OmniDocBench) | phone photo of a plan | end-to-end VLM readers lose 2-3 points on camera captures; rule pipelines lose 10-45 | text pages, not symbols | context |
| Orientation correction for OCR (2511.04161) | rotated sheet | a 12-class classifier in front of OCR; labels are free by rotating our plans | text documents; photos carry skew | needs a small training run |
| Construction takeoff (Handoff-H1) | window and door count | detector-backed counting tools under an agent beat frontier agents by about 20 points | closed system, vendor-reported | idea only |

## 5. Disagreements between the reports

1. **Qwen3-VL CountBench numbers.** Report a gives "62.9-91.5 across sizes"; report b first quoted 88.4 / 84.9 / 80.5 and later corrected them. Table 4 of arXiv 2511.21631 (re-checked 01:24, line with columns 2B Instruct, 2B Thinking, 4B Instruct, 4B Thinking, 8B Instruct, 8B Thinking, then two baselines) reads 84.1, 88.4, 89.4, 84.9, 91.5, 80.5, 80.0, 62.9. So report b's correction holds: Instruct rises with size (84.1, 89.4, 91.5); 62.9 is a baseline model, not a Qwen3-VL size. A third figure, Qwen3-VL-4B 85.5 on CountBenchQA and 58.0 on PixMo-Count (report c, from the Molmo2 paper's Table 6; I saw those two numbers in the Qwen3-VL-4B row), is a different benchmark variant, not a conflict.
2. **K-OPSD.** Report a: a fine-tuned Qwen3-VL-4B scores 0.819 against Kimi-K2.5 at 0.765, "tiny tuned beats frontier". Report b: the untuned 4B already has combined accuracy 0.738, K-OPSD leaves it at 0.738 and raises only the judge score 0.771 to 0.819, with 42 test items. Report b read the tables more closely (not re-opened by me); a's reading overstates it. K-OPSD stays an idea, not evidence of a counting gain.
3. **Molmo2 weights licence.** Report b lists Molmo2-4B as clean Apache-2.0; report c reports a sentence on the cards that the model "is trained on third party datasets that are subject to academic and non-commercial research use only". Checked 01:24: the HF API gives apache-2.0 and the README line 508 carries that sentence. Report c holds: Molmo2 is Apache-2.0 in the file but not shippable without a decision.
4. **Gemma 4.** Report a does not clear it; report b says Apache-2.0. HF API re-checked 01:24: google/gemma-4-E4B-it is apache-2.0 (about 8.0B parameters counted with embeddings). Report b holds. Gemma 3n and PaliGemma 2 remain under the Gemma terms (report b, not re-checked).
5. **Handoff-H1 harness licence.** Report c says the benchmark harness is Apache-2.0; GitHub reports no licence for handoffai/residential-takeoff-benchmark and the repo has no LICENSE file (re-checked 01:25). Treat as unlicensed. The blueprint sets are on request only (README), as report a says.
6. **CubiCasa5K licence.** Report c: GitHub LICENSE says CC BY-NC 4.0, the Zenodo record says CC BY-NC-SA 4.0. Zenodo re-checked 01:25: cc-by-nc-sa-4.0. GitHub's licence detector returns NOASSERTION; the file text was read by report c and I did not re-open it. Either way it is non-commercial.
7. **Handoff-H1 score.** Report a: Windows & Doors 88 vs 47-69 for frontier agents, overall 34.7-61.4; report c: composite 81.6 vs 61.4. They are consistent (re-checked 01:24: composite 81.6, best frontier 61.4, seven frontier composites 34.7 to 61.4, Windows & Doors H1 88, estimators 89, frontier 47-69). The metric is quantity within 25%, not exact match, and the paper says everyone converges on this trade.
8. **AECV-Bench headline.** The abstract says door/window counting is "often 0.40-0.55"; the table says 0.39/0.34 for the best model and 0.09-0.28 for the rest. Quote the table (re-checked 01:24).
9. **AdaGround.** Earlier numbers in report c (23.7 to 32.0 and 36.7 to 47.6) were the held-out UI-Vision set; the ScreenSpot-Pro numbers are 51.3 to 66.2 (8B) and 55.3 to 75.9 (32B) (report c, Table 2; report a agrees). Not re-opened.
10. **Detector-then-verifier evidence between a and b/c.** Report b's "P&ID, engineering drawings" and report c's OmniParser/PaddleOCR-VL read as support; report a's measured appendix result (no gain over template matching on drawings) is the only direct test on drawings. All three agree that none compares with a trained detector alone; a's number is the stricter reading and holds.

## 6. Negative results (what the literature says does not work)

- Zero-shot counting of door and window symbols by any VLM: 0.03-0.39 exact (arXiv 2601.04819).
- VLMs on dense counts: 0-3% exact on the HoloCount high-density subset for open models; best exact on CountQA 42.9%; touching or overlapping line shapes fail (arXiv 2407.06581), and fine-tuning on 10K-100K samples plateaued at 36.8%.
- Fine-tuned small VLM, whole-answer exactness on CubiCasa5K rasters: 3.4% (room program, n=149); a MiniCPM-V-4 box fine-tune on 3,281 FloorPlanCAD plans reached F1@0.5 0.105 (precision 0.439, recall 0.060) and its card blames long lists and truncated JSON (card re-read by report b).
- Asking a fine-tuned VLM to write the count as text: 14-17% exact on FSC-Test (arXiv 2604.10039); tool loops (tags, crops) on unfine-tuned small VLMs "mostly fail" (arXiv 2610.27756).
- Question-answer fine-tuning at 11K pairs adds only +1.2 to +1.7 points on small objects (SOUBench, Qwen3-VL-2B).
- Free coordinates from open models: point/region accuracy 8-36% where GPT reaches 54-76% (arXiv 2608.00473).
- Tiling is not free: on real floor-plan blocks tiles scored below the whole image for two strong models (arXiv 2610.09313 appendix, report a); ZoomEye drops one subtask by 12.95 points; more test crops than training crops lowered Molmo's PixMo-Count from 85.2 to 73.9.
- LoRA-tuning a planner on a rigid graph harness "collapses to near-constant per-family answers" (arXiv 2609.05880 Appendix, report b).
- A CubiCasa5K model fails on web plans (doors IoU 0.099), so the sealed eval is easier than new plans (WAFFLE).
- Moondream cannot be fine-tuned locally (cloud only), which would upload drawings.

## 7. Looked for and did not find; unverified leads; open questions

### Looked for and did not find
- A head-to-head of a fine-tuned 0.2-4B VLM and a fine-tuned detector on exact counts of tiny symbols (queries in the three reports: "fine-tuned Florence-2 vs YOLO small objects", "small VLM fine-tuned counting vs detector dense small objects", "Qwen3-VL fine-tune small object detection", HF paper search, arXiv MCP).
- Any detector + verifier result against a trained detector alone on drawings or floor plans.
- Any paper fine-tuning a small VLM for door/window counting on floor plans (WebSearch, OpenReview, CVF title sweeps of CVPR 2024/2025, ICCV 2023/2025, WACV 2025/2026, ECCV 2024, NeurIPS 2024; the NeurIPS 2025 index and ICDAR/GREC proceedings were not opened).
- Measured LoRA memory or hours for Qwen3-VL-2B/4B or Florence-2 on 12-16 GB cards, and any Qwen3-VL or Florence-2 training run on AMD ROCm cards (GitHub issues name the architecture as supported in an image; no run is documented).
- A floor-plan or counting score for Kimi K3.1 Pro or DeepSeek V4.1 Flash from anyone but the vendors.
- Per-class accuracy for the sauna stove on any model.
- Gemini per-image price (the price cells did not render in the capture).
- Forward citations of 2610.09313 (zero in Semantic Scholar on 2026-11-14).

### Unverified leads (kept out of the ranking)
BlindTest-style plateau follow-ups; BlueprintSymVL (paywalled, bot check not bypassed); HiDe (no code yet); GapSight; SchemixQA and CoRe-VLM; SkeySpot (2508.10449); CADSpotting (2412.07377); a 2026 floor-plan survey; ICLR 2027 submission "Beyond Semantic Alignment: Dense Instance Perception"; RankGround 2609.18690; CountSE (no arXiv version; code MIT); CountingDINO (licence field empty); CAD-Assistant (vector input); Holo1.5-3B and UI-Ins-7B (licences not usable); Ovis2.5 (card not opened); PIDQA; a NeurIPS 2026 workshop paper on P&ID evidence graphs; a vendor case study with PaliGemma 2 (3B LoRA recall 80.3% vs 10B 66.2% at 6-20 boxes per image, F1 86.7% for counting JSON; vendor page, Gemma terms).

### Open questions
- Does a Qwen3-VL-2B/4B LoRA give a usable per-class count from points on our dev tiles? (experiment 1)
- Is a 0.6B native-resolution dense model (Falcon Perception) able to see 5-20 px plan symbols at all? (experiment 3)
- Does a vision-tower-unfrozen LoRA matter for symbols? Support is a third-party repo (2B LoRA, box accuracy 0.74 to 0.87 with the ViT unfrozen, reported by report b, not reproduced) and a robot-control paper (arXiv 2601.03309); it is untested on drawings.
- Does the Molmo2 non-commercial data sentence matter for shipped weights? And the SAM License, Kimi's modified MIT? These are owner decisions.
- Which tile size and enlargement give one 32 px token per symbol without blowing the token count? Arithmetic only: 3x enlargement costs about 10x the tokens (report c, about 7,300 tokens for an 855 px plan).
- A 20-image paid pilot (Kimi, DeepSeek, one frontier model) on the dev split costs under about $2 by report a's estimate; it needs owner approval.

## 8. Experiments proposed (at most five)

1. Cut dev plans into 2x2 overlapping tiles enlarged 2-3x, fine-tune Qwen3-VL-2B (LoRA, vision tower trainable) to write points in reading order per class, count in code, and score exact count per class on the dev split against the 55.3% majority baseline and the count-only network's 59.3% (worker-brief); a gain above those numbers on windows or doors settles it, and 3.4% exact on whole answers is the floor to beat.
2. Fine-tune Florence-2-base on the same tiles (LoRA vs full fine-tune), merge boxes with NMS, and compare box recall and exact counts with the experiment-1 model and with the detector from the floor-plan scope on the same dev tiles; a VLM-family result within a few points of the detector settles whether a small VLM can replace it.
3. Run Falcon Perception 0.6B zero-shot on 10 dev plans with the prompts "door", "window", "toilet", "sink"; if exact counts reach even 20-30% of plans without training it earns a place, otherwise it ends.
4. Take the detector's boxes on dev, crop and enlarge each to about 48 px, ask Qwen3-VL-4B yes/no per crop, and measure exact count with and without the verifier; a gain of more than one point (the tolerance of 2610.09313's appendix) is the only thing that justifies the extra calls.
5. On 20 dev plans, run a frontier VLM zero-shot with the tile-and-enlarge rule and the AECV-Bench prompt (only if the pilot cost is approved), and report exact match per field against the 0.39 / 0.34 door/window numbers of the whole-image baseline.
