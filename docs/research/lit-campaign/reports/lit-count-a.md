# lit-count-a: counting, field and state of the art (2025-2026), worker report

Scope L3 (counting), angle a. Written 2026-11-14 (draft 1, 00:35, final 2026-11-14 about 01:15, extended through section 44; updated after each reading round, see the log
`lit-count-a-log.md`). Read-only: nothing downloaded, nothing run, no drawing uploaded.

Marks: **V** = I read it myself on the page (browser fetch, curl, gh, PDF text); **A** = read through the web-fetch
agent (first ~40k characters verbatim, the rest model-summarised: only the verbatim parts are used as facts, the
rest is marked "summary"); **R** = reported by the authors, not independently checked. Dates are all 2026-11-14.

**Reading guide.** Sections 0-7 are the report proper. Sections 9-44 are later rounds, added after lit-orch's order of 2026-11-14:
10 template-matching recipe to copy; 11, 14, 17, 28, 30 exact-count evidence (one table plus the template-matching, natural-image,
AECV and data-licence addenda); 12, 19, 31 thresholds and count heads; 12, 33 point-supervised counters; 13, 22, 25 gap retries;
15, 27, 35, 36 citation, reference and venue walks; 16 exemplar form for VLMs; 18, 24, 29, 32, 34 further counters and repos;
20 licence check against our rule; 21 SAM 3 few-shot; 26 repo issues; 37 an independent legend template-matching measurement; 38 cell-counting transfer note; 39 the paper's MIT tiling tool; 40 list-then-count repair; 41 the real-scan robustness paper (abstract); 42 paywalled abstracts via Crossref; 43 two 2026 legend template-matching papers; 44 last title sweep.

## 0. Bottom line (five sentences)

1. **One 2026 paper tests exactly "find every instance of this symbol, here is one example" on architectural
   drawings, and the exemplar counters fail there** (V, arXiv 2610.09313, read in full from the browser text):
   LegendSpot, 34 test drawings, 660 instances, 3 to 116 per image, the target symbol cropped from the drawing's
   legend. F1 with the legend crop as exemplar: **CountGD 0.10, GeCo2 0.23, OWLv2 0.07** (at most 0.44 with the best
   threshold chosen per drawing); on drawings whose reference comes from a symbol library 0.11 / 0.15; on 339
   FloorPlanCAD blocks 0.19 / 0.34. The same task with **plain template matching scores 0.87** (0.58 on the floor-plan
   blocks), tiled VLMs 0.79-0.94, and "template matching proposes, a VLM accepts or rejects each crop" 0.83-0.91.
   The authors' explanation: drawing instances are "thin line figures among look-alike symbols, unlike the
   textured objects these counters were trained on". No other paper I found reports a trained exemplar counter on drawings; the neighbours are BlueprintSymVL (one-example VLM, section 11) and a 2026 thesis on legend template matching (section 37: F1 0.52 sliding window, 0.73 on proposed regions), which agree that clean-legend-to-drawn-instance gaps are the failure.
1b. **The best exemplar method's exact-count rate is only half on small drawings** (V, the paper's repo summary, section 14):
   template matching with a leave-one-drawing-out threshold is exactly right on 14 of 40 drawings (10 of 20 on small
   views with 3-43 instances, 4 of 20 on large sheets), MAE 7.2, despite F1 0.86. A one-example VLM version
   (BlueprintSymVL, section 11) gets 86 % exact on sparse regions and 10-32 % on dense ones, and a symbol-in-context
   exemplar beats a tight crop (50.5 vs 36.5 %). So: report a count only when two independent counters agree.
2. Exact-match numbers on small counts exist in only five places (sections 11 and 14 have the table): AECV-Bench (frontier VLMs, per-class exact
   0.03-0.39 on windows/doors, V), a door-detector + GPT-5 pipeline (87.6% exact on toilets, 97 CubiCasa5K images,
   V), fine-tuned VLMs that point then count (about 69-82% exact on real tabletop scenes with 1-10 objects (OCID; direct-count fine-tunes 69.1-73.6, point-then-count 76.2-81.9 over three models), V), and the
   LVLM-Count appendix (exact accuracy on flat emoji icons, 30-50 per icon on a white canvas: Gemma 3 27B 29.41%,
   with their divide-and-conquer 30.39%; Qwen2-VL-72B 24.18% to 28.76%, V). Every other counting paper reports
   MAE/RMSE.
3. The best published way to turn a detector into an exact counter is not one method: it is (a) box or point
   supervision, (b) a score threshold chosen on the exact-count rate, (c) a second, independent look that can add or
   remove marks (a VLM omission check in 2509.17283; exemplar prompts in SAM 3 / CountGD++). Nothing in 2025-2026
   shows (b) done well; we have to measure it on dev. Repairs that are published and cheap: count the length of the point list the model returns instead of the number it states (71-84 % less count error, section 40); count at several thresholds and accept only a stable count (our own idea, no source, section 19).
4. **Per-plan exemplar counting with a trained counter is measured and weak zero-shot; with plain template matching
   it is strong in F1 when the exemplar comes from the same drawing, but its exact-count rate is 14 of 40 drawings (section 14),
   and a second 2026 measurement on electrical diagrams gets F1 0.52 with legend templates over the whole sheet (section 37).** Template matching falls from 0.87 to 0.38 F1 when the
   reference symbol comes from a shared library (different scale and stroke), so an exemplar must be cut from the
   plan being counted. SAM 3 with a box exemplar goes from 11.67 to 66.55 mAP on aerial imagery (V, 2607.09583) but
   has no drawing result. In-domain fine-tuning evidence (CoLSR, V): zero-shot CountGD MAE 7.84, a fine-tuned detector
   4.24, a fine-tuned exemplar-plus-text counter 0.88, on one dense single-class set. "Beats a fixed detector
   under style shift" has **no** published support.
5. Licences decide a lot: P2PNet is academic-research-only and T-Rex needs a commercial licence (both V, LICENSE
   files); SAM 3 has a custom "SAM License" that is not on our approved list (V); GeCo2, CountGD, CountGD++ and
   Count Anything have MIT or Apache code, but only CountGD++ and Count Anything state a weights licence (V).

## 1. Top 5 (floor-plan work and transfers, one list)

All verdicts are for filling `elements` (counts and boxes) or serving as the stage-8 `SecondCounter`. Hours are my
estimates, not measurements.

### 1. Template matching from an exemplar cut out of the same plan, then a VLM (or exemplar) verify. Verdict: **try**
- What: classical template matching (a crop of the target symbol slid over the sheet) proposes candidates; a vision
  model judges each candidate crop. From arXiv 2610.09313 (Oct 2026, "Why VLMs miss small objects", read in full via
  the browser; its drawing data are called LegendSpot and Library-10). (V)
- Numbers (V, §6 text and appendix "Template matching and trained counters"; F1 with one-to-one matching, a point
  counts if it lies within half a target of an unmatched instance): on LegendSpot (34 drawings, 660 instances)
  template matching **0.87**; propose-and-verify with eight VLMs **0.83 to 0.91**, none significantly different
  from template matching (differences -0.04 to +0.04); the candidates contain a true instance for a ceiling of 0.98,
  so the remaining loss is the verifier. Best tiled VLM configurations: Claude Sonnet 5.5 0.92, Gemini 3.8 0.94;
  zoom agents on full sheets: GPT-5.6 0.97 against 0.91 for its own tiles, Sonnet 5.5 0.95 against 0.90. On
  FloorPlanCAD blocks (339 test items, 21 classes; Table 20) template matching F1 0.58. On the 23 library-reference
  items (Table 19) whole-image VLM calls reach 0.68-0.84 and tiles 0.79-0.91.
- Failure: with reference symbols from a **library** instead of the drawing's own legend, template matching falls to
  0.38 (0.54 with an oracle threshold chosen on those drawings), because scale and stroke differ. Every VLM
  configuration beat it there by at least 0.30.
- Code and licence: OpenCV's matchTemplate (Apache-2.0) or scikit-image (BSD) are enough; no weights. The paper's own
  code/data: released (V, appendix K); repo licence MIT (V, gh api license, 2026-11-14). Leakage: no model, so none. Training data: none.
- Fills: `elements` per class (window, door, toilet, sink...) from boxes cut out of the same plan, or from dev boxes
  of the same class and style; also the independent `SecondCounter` the pipeline needs for `conflicts`.
- What breaks on our images: (1) our symbols are 5-20 px and rotated by exact multiples of 90: run each template at
  four rotations and a few scales; the paper's 0.87 is for drawings of 483 to 11,484 px with centre-point scoring
  within half a target. (2) Windows are wall segments, doors are arcs: look-alikes (a window next to a wall run, a
  door arc next to a sink bowl) are the false positives; hence the verify step. (3) An exemplar must come from the
  same plan or the same style: for a first test use a dev box of the same drawing as template (uses dev labels only
  for testing; a product version needs the user or the detector to give the first example). (4) Thin-line scans and
  phone photos shift stroke width: the paper's library result is the warning.
- Recipe (V, appendix text): multi-scale, four-rotation normalised cross-correlation, non-maximum suppression,
  threshold chosen on six prompt-writing sheets (0.87; 0.89 leave-one-out). A fixed threshold across blocks drops to
  0.18 on far blocks because 49% of instances differ from the reference by more than 20% in box size.
- See also: exact-count rate of this method (section 14: 14/40 drawings, 10/20 on small views), the copyable recipe (section 10),
  context exemplar vs tight crop for the VLM variant (section 16), and a feature-space variant to test (section 29).
- Hours to a first number: 1-2 for template matching on 50 dev plans with rotations (estimate). The verify step with
  a small open VLM (Qwen3-VL-2B Apache-2.0, per the earlier report) needs another 2-4.
- Scope note: this is closer to L11 (classical routes) and L7 (VLMs); it is first here because it is the only
  measurement on drawings of the exemplar idea.

### 2. Tiled VLM pointing with the "tokens per target" rule (same paper). Verdict: **maybe**
- What: give the model one example crop and ask for the centre of every instance; split the sheet so that each
  target gets at least 1.5 visual tokens along a side, split at the same scale (never zoom out, no thumbnail),
  overlap neighbours by one target, merge. (V, 2610.09313 §5, Table 1 and Table 2)
- Numbers (V, Table 2 text): recall on LegendSpot rose from 0.62 to 0.90 (Gemini 3.8), 0.85 to 0.98 (Gemini 4) and **0.37 to
  0.56 for Qwen3-VL**, at 3.1 to 8.6 times the whole-image token cost; splits that never zoom out raised recall by
  0.10 to 0.46 on average where tokens per target were below 1.5; splits that zoom out lowered it in 19 of 21
  settings; packing eight tiles into one call lowered GPT-5.6 recall from 0.77 to 0.47; sending more pixels
  through one vendor's high-resolution mode dropped F1 from 0.89 to 0.33 on full sheets. Open models were weaker:
  Qwen3-VL whole image on LegendSpot 0.37 recall, floor-plan mosaics 0.05 to 0.12.
- Licence: the rule is arithmetic, no code needed; Qwen3-VL-2B/4B/8B are Apache-2.0 (earlier report, card not
  re-read). Leakage: unknown for the base models.
- What breaks: points must land within half a target of an instance; at 5-20 px symbols a 2B model is the weakest
  point in the table; Qwen3-VL "recalls 0.22 of 96 targets" in a controlled test where the frontier models reach 1.0.
  This overlaps L7; it is here because it measures counting on drawings.
- Fine-tuned version: see "Also ranked: point-then-count" below, which has exact-match numbers.

### 3. GeCo2 as an exemplar-box second counter. Verdict: **maybe (demoted: F1 0.23 zero-shot on architectural drawings)**
- What: few-shot, detection-based counter; takes an image plus 3 exemplar boxes, returns boxes, masks (SAM2 head)
  and a count. Hiera backbone from SAM2, one 1024x1024 pass, no tiling or upscaling. AAAI 2026, arXiv 2511.08048. (V)
- Numbers (V, Table 1, FSCD147 test): MAE 7.64, RMSE 39.39, AP 46.81, AP50 75.89. Table 5: 4.98 GB, 0.2 s per
  image on one A100 (CountGD 15.47 GB, 1.3 s; DAVE 25.33 GB, 0.3 s). Training: Hiera frozen, 200 epochs, 2 A100.
- **Measured on drawings (V, 2610.09313 appendix, see top item 1):** with the legend crop as exemplar GeCo2 reaches
  F1 0.23 on LegendSpot architectural drawings (CountGD 0.10, OWLv2 0.07), 0.15 on library-reference drawings, 0.34 on
  FloorPlanCAD blocks (CountGD 0.19); on FSC-147 photos the same code gets 0.86 (CountGD 0.90). Zero-shot it is a
  poor second counter for us; the case for it is a fine-tune on our boxes, not the weights as released.
- Small objects: an auxiliary small-object loss is applied to images whose objects average under 25 px; the
  paper says a main failure of earlier counters is several objects sharing one latent pixel (V). **No result is
  reported for images with few objects, and no domain-shift analysis** (V: I looked for both).
- Code: github.com/jerpelhan/GECO2, **MIT** (V, LICENSE file). Weights: HF dataset repo `jerpelhan/geco2-assets`
  (not gated, no model card, no licence tag; two checkpoints: `CNTQG_multitrain_ca44.pth` and `GECO2FSCD.pth`, the
  second also on Drive as the official FSCD checkpoint); **no weights licence stated** (V, HF API and README).
- Leakage flag: **no** (natural photos only). What the weights were trained on (V, maintainer's reply in repo issue
  #12): the demo checkpoint on FSCD147, FSCD-LVIS, MCAC and "CA44 (the T-Rex dataset)"; the second checkpoint on
  FSCD147 only. T-Rex's own licence needs a commercial licence (V, LICENSE), so the **weights' data chain is
  unclear**: do not ship, and ask the author. The maintainer confirmed in issue #5 that the code is MIT (SAM2 parts
  Apache-2.0). Training code was released after requests (issues #1, #10 closed), but the author says training on
  FSCD147 "is quite unstable" because of annotation errors (issue #12, V).
- Practical facts from the issue tracker (V, read 2026-11-14): exemplars from **another image** work if the
  prototypes are stored (maintainer, issue #14: "I've used this approach in practice and it works well"), so
  exemplars cut from dev plans can be reused on new plans; negative exemplars are **not** supported; a user
  reports detections of shapes that look nothing like the exemplar (a circle) and the maintainer's advice is to
  post-filter by box aspect ratio and area (issue #14); "Not supported on CPU" is open (issue #17).
- Fills: `elements[*]` boxes for one class per call (window, door, ...) from 1-3 exemplar boxes cut from the same
  plan; count = number of boxes. Also gives `SecondCounter` for `conflicts`.
- What breaks on our images: (1) it was tuned for photos; thin-line symbols with no texture may give weak exemplar
  similarity; untested. (2) A 5-20 px symbol on an 855 px plan is below the "average object ~25 px" regime the
  small-object loss targets; upscaling the plan before the pass is probably needed (that is the thing GeCo2 tries
  to avoid, so test both). (3) Windows next to doors and walls: exemplar similarity will fire on parallel wall
  lines; there is no negative prompt (CountGD++ has one). (4) Rotated sheets: one exemplar at the wrong
  orientation; run the 4 rotations and take the majority, as for the other counters. (5) Weights licence unstated:
  fine for scoring runs, do not ship until the author answers (the README asks users to email them).
- Threshold caveat (V, section 31): the demo's threshold is relative to the best box in the image, so it can never answer 0.
- Setup facts (V, repo files): `install.sh` creates a conda env with Python 3.10, torch 2.7.1 for CUDA 12.6 and
  compiles the Deformable-DETR CUDA ops; a Dockerfile exists; Detectron2 is needed only for the AP evaluation. The
  shipped `train.sh` is a Slurm job on 2 GPUs with a 4-day limit (a time limit, not a measured run time).
- Hours to a first number on 200 dev images with exemplars cut from dev boxes: about 2-3, most of it the CUDA op
  build and exemplar plumbing (the repo's Gradio demo takes box prompts; batch inference with stored prototypes
  needs the small code change the maintainer describes). Estimate.

### 4. CountGD++ (and fine-tuning CountGD, evidence from CoLSR). Verdict: **maybe, only as a fine-tune; zero-shot CountGD scores F1 0.10 on drawings**
- What: Grounding DINO based counter that takes text, positive and negative visual exemplars, and "pseudo-exemplars"
  (its own boxes fed back in). CVPR 2026, arXiv 2512.23351. Swin-B image encoder, BERT text encoder, 900 queries,
  so at most 900 objects per pass; adaptive crop at 800+ objects, with a super-resolution step for the crops. (V)
- Numbers (V, HTML): MAE/RMSE only. In the CLOC table of another paper (V, 2605.30846 Table 1) CountGD++ is 23.38 MAE
  and CountGD 55.91 on the full test; first-party FSCD-147 numbers were read through the agent only (summary). **No
  exact-match or low-count metric** anywhere in the paper (V grep: no "exact" accuracy table).
- Code **MIT** (V, repo LICENSE); weights `nikigoli/CountGDPlusPlus` on Hugging Face, card says **license: mit** (V,
  raw README); the 1.25 GB checkpoint is also on Drive. Trained on FSC-147 (V, abstract section). Leakage: **no**.
- Why it matters for us: **negative exemplars**. Our counting rules need "door with a leaf, not a bare opening",
  "shower tray, not a shower screen", "window cell, not a wall segment". A negative box cut from a dev plan is a
  direct way to say that. Evidence that exemplar-conditioned counters can be fine-tuned on a small set: CoLSR
  (V, 2602.11024) fine-tunes CountGD on 1,236 images of one dense single-class object and gets MAE 0.88 against
  7.84 for stock CountGD; its ablation: no visual exemplars MAE 1.5, no prompt tokens 2.05, no neighbour loss 1.81.
  It reports **no exact-match**, and its dataset is CC BY-NC (V, mixed LICENSE file; code MIT).
- Training facts (V, repo issues): CountGD regressed **box centre points only** because FSC-147 has no full boxes
  (maintainer, CountGD issue #22: a user who fine-tuned got falling COCO AP and the fix is changing the target
  slice from the 2 centre values to all 4 box values); fine-tuning instructions for custom data were promised and
  issues #40/#52 remain open; CountGD++ issue #6 says full training and inference code were released. So
  fine-tuning on our 104k boxes is possible but is code work in a Grounding DINO code base with CUDA ops and
  detectron2 (README).
- What breaks: 900-query, high-res Swin-B model is heavy (CountGD 15.47 GB in GeCo2's Table 5, V): fine-tuning on a
  12 GB GPU is unproven (CoLSR used a 24 GB-class RTX 3090 at batch 4, V). Inference only is fine on 16 GB. Same
  thin-line and rotation caveats as GeCo2. Fine-tuned CoLSR relies on instruments lying along one axis (V,
  their stated limitation); windows along a wall fit, scattered sinks do not.
- Hours to a first number: 3-4 zero-shot with exemplars; fine-tuning not estimated.

### 5. SAM 3 with exemplar prompts. Verdict: **maybe (licence, gating and no drawing evidence)**
- What: promptable concept segmentation: noun phrase and/or image exemplars in, every matching instance out with a
  mask and a score. 450M vision + 300M text encoder, 1008x1008 fixed input. arXiv 2511.16719. (V, pwfetch of v2)
- Counting protocol, quoted from appendix F.4 (V): drop the presence head, Non-Maximal Suppression with
  "Interaction over Minimum" at 0.5 (to catch part-in-whole duplicates), keep confidence > 0.5, count = number of
  predictions. Ablation (V, Table 37): CountBench MAE/Acc 0.34/84.8 without IoM, 0.11/94.0 with IoM; PixMo-Count
  0.34/76.9 vs 0.21/86.3. These sets have 2-10 objects per image (487 and 529 images after dead links), so this is
  one of very few counting numbers on **our count range**, and it is exact accuracy on photos.
- Caveat on the numbers above (V, appendix F.4): the paper says "an **internal** SAM 3 checkpoint" was evaluated on
  CountBench and PixMo-Count, so the released weights may score differently.
- Interactive exemplars (V, §5 text and Fig. 7): add one exemplar at a time (missed object = positive, false
  positive = negative); after 3 clicks cgF1 is +21.6 over text-only. Gains plateau after 4. This is the "human
  corrects a few marks" pattern, with numbers. 10-shot fine-tuning on RF100-VL: the paper says SAM 3 adapts more
  efficiently than the baselines (V; table not read).
- Out of domain (V, 2607.09583, aerial DIOR): text prompt 11.67 mAP, one box exemplar 66.55 mAP (79.51 AP50);
  both together 63.79. Small vehicles stay at 6.76 mAP (text) and 9.15 (best), "a resolution and feature-space
  limitation". The authors of SAM 3 list thermal imagery and fine-grained concepts as failures (V, appendix B).
  **No evaluation on drawings exists** (searched; Roboflow's page only describes segmenting walls with it).
- Licence: **"SAM License", last updated 2025-11-19** (V, full LICENSE text read): a non-exclusive, worldwide,
  royalty-free limited licence "to use, reproduce, distribute, copy, create derivative works of, and make
  modifications to" the models and code, **with no non-commercial clause in the file**. Conditions: anyone you
  pass the materials or a derivative to gets them under the same agreement with a copy of it; research results must
  acknowledge the use; no reverse engineering; compliance with trade-control law, including no use for ITAR items
  or "military or warfare purposes, nuclear industries or applications, espionage, or ... guns or illegal weapons".
  GitHub reports NOASSERTION. It is not MIT/BSD/Apache/ISC/LGPL and it carries a field-of-use restriction, so under
  record 0006 it needs an explicit team decision. (A user in issue #640 says SAM 2 and SAM 3 "prohibit commercial
  use"; that is not what the LICENSE file says.) Weights on Hugging Face `facebook/sam3` are **gated** (V: the raw
  README refuses without login), so I could not read the card; the Count Anything repo says it does not
  redistribute the checkpoint "due to license and redistribution restrictions" (V).
- Access risk (V, repo issue tracker, 2026-11-14): 19 of the 40 most recent issues (#616-#658, Aug to Nov 2026) are open requests
  to reconsider or reset a rejected SAM 3 access request on Hugging Face, so the checkpoint is not guaranteed
  to be granted by Saturday evening. Mask exemplars are claimed in the paper but unusable in the release (#604);
  box exemplars work. Whether outputs from the model may be used commercially was asked in #640 (closed, no
  answer visible).
- Leakage flag: **unknown** (web-scale SA-Co data; nothing says floor plans or CubiCasa5K are in or out).
- What breaks: text prompts on line art ("window") will not match the symbol (the aerial result is the model for
  this: text 11.67 vs exemplar 66.55), so exemplars are required; 5-20 px symbols at a fixed 1008 px input are the
  same regime as the small vehicles that stay under 10 mAP; the model (about 850M parameters; Count Anything, built on it, is 848.6M, V) cannot be fine-tuned on 12 GB without
  tricks (not tested; Count Anything trained it with LoRA on 8 GPUs, V). Inference fits: 5.2-6.5 GB in BF16 (V,
  Count Anything Table 7, a SAM 3 based model).
- Hours: 1-2 for 50 plans zero-shot with exemplars, once access is granted. Estimate.

### Also ranked 6. Fine-tuned small VLM that points, then counts (transfer from VLM counting). Verdict: **maybe**
- What: train the model to emit point coordinates for each target, then the count ("Point-then-Count", PtC). arXiv
  2603.21746, March 2026, CC BY paper. (V, pwfetch)
- Numbers (V, Tables 1-3, exact-match accuracy %): real images with 1-10 objects (OCID, in distribution), direct
  count fine-tune vs PtC: Qwen2.5-VL 3B 70.00 vs 81.90; 7B 73.57 vs 76.19; LLaVA-OneVision 69.05 vs 77.14.
  Synthetic grid objects 1-18, in distribution: PtC 99.9%. **Out of distribution counts** (10-18 on synthetic,
  Table 2, fine-tuned): the model answering by itself after pointing (PtC) 19.44 to 97.33 depending on the model;
  **counting the emitted coordinates in code ("# Coord.") 80.20 to 97.94**. On real images with 11-20 objects
  (Table 3, fine-tuned) PtC is 0.98 to 25.88 and "# Coord." 16.27 to 33.53. Predicted points were "grounded in more
  than 94% of cases (F1)" (abstract).
- So: exact counting by a fine-tuned VLM works in the count range it was trained on and falls off a cliff beyond
  it, and **counting the points in code beats letting the model say the number** wherever they differ. Our range
  (0-40, windows and doors 3-15) is wide; train on the full range, and count points in code.
- A 2026 pointing architecture worth knowing (Ai2 MolmoPoint blog, 2026-03-18, V): the model selects a coarse
  patch, then a subpatch, then a location, uses rotary embeddings of the distance to the previous point "to avoid
  double-pointing", and has an explicit **no-more-points** class so it can stop. Reported (R): PixMo-Points F1 89.2
  (Molmo 2 8B 85.2); with only 8,192 training examples it beats the coordinate-text baseline by about 20 F1
  points. MolmoPoint-8B card: apache-2.0 (V). 8B parameters: too big for a 12 GB training run without 4-bit; the
  design (stop class, no double pointing) is the useful part for counting.
- Licence: the models there are Qwen2.5-VL (research licence, non-commercial, see `lit-vlm.md`), LLaVA-OneVision,
  InternVL3.5, Gemma; use Qwen3-VL-2B (Apache-2.0, per the earlier report) for anything that ships. Training data:
  synthetic plus OCID; leakage **no** for the paper's own checkpoints, **unknown** for the base models.
- What breaks: VLM image tokens at 28x28 px per token (Qwen2.5-VL, earlier report) mean a 10 px window is a
  fraction of one token, the "too few tokens per object" failure that 2610.09313 measures (V abstract: recall rises
  when tokens per object are below 1.5 only if the split never zooms out); so tile at higher scale, no thumbnail.
  Training needs boxes-to-points on 104k symbols: possible from the dev boxes. This overlaps scope L7; it is here
  because it is the only exact-match-on-small-counts method with numbers.
- Hours: 4-8 for LoRA on a 2B model plus data prep; the 12 GB fit is unmeasured. Estimate.

### Also ranked 7. Detector plus an omission check by a VLM (idea from the facility-enumeration paper). Verdict: **maybe (idea only)**
- What: detect doors, ask GPT-5 per door "does it lead to the target room?", merge pairs, then show all kept boxes
  and ask the model to count rooms with no box. arXiv 2509.17283 (Sept 2025). Detector: Co-DETR, trained on two
  public Roboflow door sets (1,047 and 837 training images). (V, full text)
- Numbers (V, per-image exact match): toilets on CubiCasa5K (97 images) 85.57 for GPT-5 alone vs 87.63 with the
  pipeline; FloorPlanCAD (140) 79.29 to 85.71; CVC-FP (15 images) 40.00 to 86.67; kitchens CubiCasa5K 96.91 to 98.97
  (that is 94 to 96 images of 97, my arithmetic from the table). Not reported: detector AP, MAE, variance, tile size,
  code or weights. The gains on CubiCasa5K are 2-3 images.
- Leakage: the Roboflow door sets are **unknown** (the brief says many Roboflow floor-plan sets are CubiCasa5K
  repackages), so treat the checkpoint as leaky. No code, so nothing to run anyway.
- Why keep it: it is the only paper that states exact counting as a zero-tolerance task and builds a correction
  step (omission pass) after the detector. For us the same idea is a stage-8 check with a VLM or an exemplar
  counter looking at the plan with the detector's boxes drawn on it. Cost is an API call or a local VLM per plan.
- What breaks: GPT-5 is a paid API (our rule: no paid APIs in research; for the product it is a cost and a
  determinism problem: the paper gives no seed or temperature). Windows and doors are exactly where VLMs fail
  (AECV-Bench below), so the omission pass will be weakest on the classes where we need it most.

## 2. Full table

Columns: M = method; Y/V = year, venue; C = code licence (read from LICENSE file); W = weights licence; D =
training data / **leak** flag for CubiCasa5K; Metric = metric and benchmark (V = verified, R = reported); In/GPU =
input size and memory; H = hours to a first number on our dev boxes (estimate); Fills; Verdict; F = from our field
or the field it transfers from.

| M | Y/V | C | W | D / leak | Metric | In / GPU | H | Fills | Verdict | F |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Template matching + VLM verify; tiled VLM pointing (2610.09313) | 2026 (arXiv Oct) | classical template matching: OpenCV Apache-2.0 / scikit-image BSD; paper code not read | none (no model) | architectural drawings (LegendSpot, 34 test, 660 instances), FloorPlanCAD blocks; leak no | LegendSpot F1: template matching 0.87, propose+verify 0.83-0.91, best tiles 0.92-0.94, **GeCo2 0.23, CountGD 0.10**; library references: TM 0.38; FloorPlanCAD blocks TM 0.58, GeCo2 0.34, CountGD 0.19 (V) | tiles sized to 1.5 tokens per target; no GPU for template matching | 1-2 | elements per class, SecondCounter | **try** | drawings (transfer from VLM small-object work) |
| GeCo2 (2511.08048) | 2025 AAAI'26 | MIT | not stated (HF dataset repo, no card) | FSC-147 family; leak no | FSCD147 test MAE 7.64, AP 46.81 (V); **F1 0.23 on architectural drawings, 0.34 on FloorPlanCAD blocks, zero-shot (V, 2610.09313)** | 1024; 4.98 GB infer | 2-3 | elements boxes, SecondCounter | maybe (fine-tune only) | general counting |
| CountGD++ (2512.23351) | 2025 CVPR'26 | MIT | MIT (HF card) | FSC-147; leak no | MAE/RMSE; CLOC 23.38 MAE (V via 2605.30846); no drawing result for ++ | not stated; Swin-B, 900 queries | 3-4 | elements boxes, negative exemplars | maybe (fine-tune only) | general counting |
| CountGD (2407.04619) | 2024 NeurIPS | MIT | MIT (HF card) | FSC-147; leak no | FSC-147 test MAE 5.74 (corrected labels), 6.75 (original); input shortest side 800 px (V, paper Tables 1 and 4); **F1 0.10 on architectural drawings with a legend-crop exemplar (V, 2610.09313)** | 15.47 GB, 1.3 s (V, GeCo2 Table 5) | 3-4 | elements boxes | skip zero-shot | general counting |
| CoLSR (2602.11024) | 2026 (WACV'26 per search, R) | MIT code, dataset CC BY-NC | none stated | own 1.5k images; leak no | MAE 0.88 vs CountGD 7.84, no exact (V) | short edge 800; RTX 3090 | n/a | idea: fine-tune CountGD small set | maybe | surgical instruments |
| CountEx (2602.19432) | 2026 | repo has no LICENSE file (V, API 404) | not read | CoCount (videos of desk/food objects); leak no | CoCount known-category MAE 12.72 vs CountGD 15.55 (V) | not read | n/a | idea: exclusion prompts for "bare opening", "shower screen" | maybe (idea) | counting |
| HieraCount (2605.10887) | 2026 | not read | not read | synthetic KubriCount (Kubric 3D + editing) + FSC-147; leak no | MAE/RMSE only (V) | Grounding DINO based | n/a | idea: multi-grained counting with negatives | skip for now | counting |
| GICount / BunchCount (2609.04716) | 2026 (AAAI-style) | repo has no LICENSE file (V) | not read | 1,330 images, 89k individual, 11k group annotations | counters trained on individuals fail on groups (V) | Grounding DINO based | n/a | idea: window strip (group) vs cell (individual) | idea only | counting |
| PairTally (2509.13939) | 2025 DICTA | not read | n/a | benchmark, 681 images, 2 categories each | specialist counters overcount confusable classes, VLMs undercount (V) | n/a | n/a | tells what to expect (windows vs doors) | evidence only | counting |
| DAVE (2404.16622) | 2024 CVPR | MIT (V, repo LICENSE) | not stated | FSC-147 | FSC-147 test MAE 8.66 (V, full text re-read round 1); 25.33 GB, 0.3 s (V, GeCo2 Table 5) | n/a | n/a | idea: detect with high recall, verify by clustering features and keep clusters that contain an exemplar | idea only | counting |
| CoDi (2512.20153) | 2025 TIP | repo link in abstract, licence not read | not read | FSC-147, MCAC | FSC-147 few-shot MAE 15% below prior best (R, abstract); trained 15 h on one H100, 25 diffusion steps (V) | upsampled input | n/a | n/a | skip: too heavy for the timeline | counting |
| OWLv2 (2306.09683) | 2023 NeurIPS | n/a | Apache-2.0 (HF card, V) | web pseudo-boxes; leak unknown | not read | 960 px (card not read) | n/a | image-guided one-shot detection exists | not opened beyond abstract; not ranked | detection |
| LVLM-Count (2412.00686) | 2024 arXiv, TMLR 2026 | repo not checked | n/a (uses open VLMs) | n/a | Emoji-Count exact acc 24-30%, +-1 acc 43-54% (V, appendix I) | 1024x1024 canvases | n/a | idea: split by segmentation so no object is cut, count tiles, sum | idea only | VLM counting |
| Deep Double Poisson Network (2406.09262) | 2024 | repo not found in text | n/a | tabular/crowd/image/point-cloud count sets | discrete predictive distribution over counts; MAE and calibration (V abstract) | n/a | n/a | idea: count head with a calibrated distribution | idea only | count regression |
| SAM 3 (2511.16719) | 2025 | SAM License (custom, no NC clause, military/ITAR exclusion) | SAM License, gated | SA-Co; leak unknown | CountBench Acc 94.0, PixMo-Count 86.3 with IoM NMS (V) | 1008; ~6 GB infer | 1-2 | elements masks+boxes | maybe | general / segmentation |
| Count Anything (2605.30846) | 2026 | Apache-2.0 | Apache-2.0 card, but built on SAM 3 weights | CLOC 220K imgs, six domains; leak no | CLOC MAE 9.34, no exact (V) | 1008; 848.6M params, 5.2-6.5 GB | 2-3 | points | skip for now: SAM 3 licence chain, 850M | counting |
| Point-then-Count (2603.21746) | 2026 | not read | n/a | OCID + synthetic; leak no | exact acc: real OCID 1-10 obj 69.1-81.9% (V, Table 1 re-read) | Qwen2.5-VL 3B/7B | 4-8 | elements points | maybe | VLM counting |
| Facility enumeration (2509.17283) | 2025 | none released | none | Roboflow door sets; leak unknown | per-image exact: CubiCasa5K toilets 87.63 (V) | not stated | n/a | idea: omission pass | maybe (idea) | floor plans |
| DoorDet (2508.07714) | 2025 (Neural Comput. Appl.) | not read | not read | built from CubiCasa5K; **leak yes** | Co-DETR mAP 0.831 / AP50 0.926 over 10 door classes after human refinement; 0.578 / 0.650 before (V) | 2 A100 | n/a | doors | skip (leak); idea: human refinement of auto boxes | floor plans |
| AECV-Bench (2601.04819) | 2026 | n/a | n/a | benchmark; CubiCasa5K subset | frontier VLMs exact: Gemini 3 Pro door 0.39 / window 0.34; open models window 0.03-0.18 (V) | n/a | n/a | baseline only | one line, belongs to L7 | floor plans |
| UpCount (2607.16826) | 2026 | not read | n/a | FSC-147 | test MAE 12.39, RMSE 100.89 (V) | ViT-B/16 | n/a | n/a | skip: worse than GeCo2 | counting |
| UniCounting (2610.08379) | 2026 | not read | n/a | COCO | no exact | frozen SAM 2.1 | n/a | n/a | skip: whole-image category vectors | counting |
| AgriCountDINO (2609.29460) | 2026 | not read | n/a | TPC-268 | 3-shot MAE 11.92 (V) | 1024 input; 8.4M trainable params | n/a | idea only (missed-object recovery, exemplar-scale NMS) | skip | agriculture |
| SkeySpot (2508.10449) | 2025 | n/a | YOLOv8 = AGPL | 45 scanned electrical plans | YOLOv8 mAP50 81.1 vs Faster R-CNN 48.6 on 13 test images (V) | n/a | n/a | n/a | skip: AGPL, tiny set, no count metric | electrical plans |
| Handoff-H1 (2608.15032) | 2026 | not released (only the benchmark harness on GitHub, licence not read) | none | in-house CV models for sheets; leak unknown | TakeoffBench-v1 composite 81.6 vs best frontier agent about 61 and professional estimators 77.6; Windows & Doors trade 88 (H1) vs 89 (estimators); scored with a 25% quantity tolerance, so not exact-match (V) | n/a | n/a | n/a | evidence only: closed, 2026 state of the art for counting on blueprints | blueprint takeoff |
| TempFit (2610.17776) | 2026 | not read | not read | FloorPlanCAD (NC) + own IndustryCAD | retrieves a template from a library and fits it; PQ on FloorPlanCAD (SymPoint PQ 83.3, 35.1M params, 84.7 ms, V from its table); works on vector primitives | vector CAD, not raster | n/a | n/a | not mine (L11): vector input | CAD symbol spotting |
| MEP lighting symbols (2608.14317) | 2026 | not read | not read | own annotated floor plans, Mask R-CNN | bbox mAP 0.7596, AP50 0.985 (V, abstract); aim is counting lights per floor, no count metric | n/a | n/a | n/a | skip: no exact count, tiny scope | floor plans |
| P2PNet | 2021 | **academic research only** (LICENSE, V) | n/a | crowds | n/a | n/a | n/a | n/a | out | crowd counting |
| T-Rex / T-Rex2 | 2024 | IDEA License 1.0: commercial needs a licence (V) | n/a | n/a | n/a | n/a | n/a | n/a | out | detection |
| PET, point-query quadtree (2308.13814) | 2023 ICCV | MIT (V, API) | trained crowd checkpoints on Drive, no licence stated (V, README) | crowds; leak no | abstract read (V): quadtree splits point queries where the scene is dense; partial-annotation and point-refinement modes; no numbers read | n/a | n/a | idea: a point detector trained from scratch on our symbol centres | maybe, if a box detector disappoints; no evidence on symbols | crowd counting |
| RF-DETR P&ID detector (HF card) | DocEng 2026 (R) | Apache-2.0 (card) | Apache-2.0 | own P&ID set, 32 classes | mAP50 99.96 (R, card); uses SAHI tiles | RF-DETR base | n/a | n/a | not mine (L2/L11); shows tile-per-sheet-type practice | P&ID |

## 3. From other fields: transfer notes (what I found from my angle)

Sideways transfers are the job of the `b` worker; these are the ones I met while reading the field.

- **Remote sensing, SAM 3 with one box exemplar (2607.09583, V).** Field/task: aerial object detection (DIOR).
  Role of our object: a ship or vehicle, 5-30 px, repeated, dense. Why it transfers: the same failure (text names
  mismatch the picture, boxes of one instance fix it) and the same small-object limit. Breaks: line art has no
  texture; the gain was measured against a text prompt, not against a trained detector. Code and weights: work as
  they are, if the licence is accepted.
- **Dense surgical-instrument counting (2602.11024, V).** Role: handle ring, many identical objects touching in a
  line. Transfers: duplicate suppression along an axis and a chain-order loss; the fine-tune recipe on 1.2k images.
  Breaks: single class, one axis, dataset NC; gives only the idea and the CountGD recipe.
- **Plant counting with frozen DINOv3 and exemplar boxes (2609.29460, V).** Two ideas worth stealing: "missed-object
  recovery" in training (unmatched targets get an unused query in their neighbourhood) and point NMS whose radius
  scales with the exemplar size. Both address adjacent identical objects (window cells in a strip). Idea only. The
  model keeps DINOv3 frozen and trains 8.4M parameters, which would fit 12 GB; but DINOv3 carries the same
  custom Meta licence as SAM 3 (gated on Hugging Face, trade-control clause; V, LICENSE read), while DINOv2 code is
  Apache-2.0 (V, API), so a copy of the idea would use DINOv2 (weights card apache-2.0, V).
- **Granularity and exclusion in counting (HieraCount 2605.10887, CountEx 2602.19432, BunchCount 2609.04716,
  PairTally 2509.13939; all V).** Field/task: open-world counting where the user means a sub-type or a unit.
  Role of our object: our rules count a window per drawn *cell* (not per strip), doors with a leaf but not bare
  openings, shower trays but not screens, and every one of those is a "which unit, which look-alike" question.
  Findings: specialist counters (GeCo, CountGD) **overcount** confusable classes while VLMs undercount (PairTally),
  counters trained on individual instances fail at group-level units (BunchCount), and exclusion prompts help
  (CountEx: known-category MAE 12.72 vs CountGD 15.55). What breaks: all measured on photos with 10 to 900 objects;
  no code with a stated licence among the three. Use: it predicts our failure mode (overcount of look-alikes) and
  says the detector's classes should be trained so the confusables are explicit negatives (door-without-leaf
  exists as its own class in our label export for exactly this reason).
- **Human correction of a few marks (Interactive Class-Agnostic Counting, 2309.05277, V abstract; SAM 3's
  exemplar loop, V).** The user marks a region with an obvious error and gives a count range (two clicks per round,
  30-40% MAE reduction on FSC-147/FSCD-LVIS, density counters only) or adds one positive/negative exemplar per round
  (SAM 3: +21.6 cgF1 after three). Both are 2023-2025 designs; a 2026 AAAI human-in-the-loop paper on duck counting
  (77.6% recall, 87.5% less annotation time, reported in a search snippet) was behind a bot-protection page and not
  read. Breaks: neither reports exact-match; both assume the user can see which region is wrong.
- **Detect high, then verify (DAVE 2404.16622, V).** Stage one proposes candidates for high recall, stage two
  extracts verification features, clusters them (spectral clustering on cosine similarity) and keeps the
  candidates whose cluster contains an exemplar; the rest are outliers. For us: the same two-step shape fits a
  detector run at a low score threshold followed by an exemplar-similarity filter from the same plan. Evidence
  limited to FSC-147; costs 25 GB in GeCo2's measurement (V), too heavy to run as is.
- **Input scale facts that matter for 5-20 px symbols (V).** CountGD resizes the shortest side to 800 px (paper,
  implementation details) and was trained on images with at least seven objects (paper, §4.2: "FSC-147 has at least
  seven objects in each training image"); its only low-count test is CountBench (2-10 objects) zero-shot with text.
  GeCo2 uses 1024x1024 with the average exemplar scaled under 80 px. SAM 3 uses 1008x1008. A 855 px plan with
  10 px windows is therefore 1.0-1.2x the scale these models see, which is the regime where they have not been
  tested; every one of them needs an upscale experiment on dev.
- **Self-similarity double counting and the test-time normalisation (CountGD 2407.04619 §4.3 and Table 4, V).**
  Field/task: counting objects made of repeated parts (butterfly wings, sunglasses lenses). Role of our object: a
  multi-pane window strip or a double sink, where each part looks like the whole. Mechanism: CounTR divides the
  predicted count by the count found inside the exemplar box; CountGD does the same with SAM masks of the
  exemplars instead of boxes, because boxes that hold more than one instance break the divisor. Measured (V, Table
  4, FSC-147 test MAE/RMSE): no normalisation 10.92 / 99.58, SAM normalisation 9.62 / 98.90, plus adaptive
  cropping 6.75 / 43.65. It is the only published form of "count calibration" I found for exemplar counters, and the
  authors call the gain minor because few FSC-147 classes are self-similar. Breaks: needs a box that holds exactly
  one instance, which for a window cell next to another cell is the very ambiguity our label rule (one object
  per drawn cell) settles; so cut exemplars from dev boxes, which already follow that rule.
- **Count-only supervision with a language model (WS-COC 2602.12774, ICLR 2026, V).** Trains an MLLM on image-level
  counts alone, with a range-judgment dialogue and a rank loss: FSC-147 test MAE 13.91 against 5.7-8.7 for
  fully supervised counters (V, Table 1), and the paper's Figure 1(d) plots sparse (up to 20 per image) against dense
  scenes. It agrees with our own count-only FCN finding (windows and doors stay at 18%): answers alone are a weak
  signal for exact counts. Idea only.
- **Duplicate versus adjacent instance (Count Anything, 2605.30846, appendix D, V).** The authors list as an open
  limitation that the model "may still be difficult to fully distinguish duplicate predictions from truly adjacent
  instances"; that is the window-strip problem stated in one line, in the newest counter I read.
- **Industrial bulk-stack counting (2603.15470, V).** Volume-from-3D-Gaussian-splat count; real-scene NAE 0.36 (re-read V).
  Needs depth and many views: **not transferable** to a flat sheet. Listed so nobody reads it again.
- **Construction takeoff in production (Roboflow vendor post, May 2026, V).** Reported: per-sheet-type detectors
  (not one big model), overlapping tiles merged at page level, expert labelling, active learning. No numbers; a
  vendor post, not evidence.

## 4. Looked for and did not find

- Any exemplar or class-agnostic counter evaluated on drawings **other than** 2610.09313 (which tests CountGD, GeCo2
  and OWLv2 on architectural drawings and finds F1 0.07-0.23). Nothing for CountGD++, DAVE, SAM 3, Count Anything on
  floor plans, P&ID, CAD or other line drawings. Searches: "SAM 3 floor plan / architectural / engineering drawings", "exemplar
  counting architectural drawing symbols", "few-shot symbol spotting technical drawings", "blueprint takeoff
  exact count accuracy". Result: only fully supervised symbol spotting (FloorPlanCAD, ArchCAD-400K, CADSpotting,
  VecFormer) and detector benchmarks.
- Exact-match accuracy of detection-based counting versus regression on counts under 20 in a 2025-2026 paper. The
  closest is a 2021 robotics study: comparable at low density, regression better as density rises (search
  snippet only, not opened). GeCo/GeCo2/DAVE report only averages.
- Count calibration (Poisson-binomial over detection scores, learned count heads, count loss on a detector): the
  searches returned physics papers and two calibration papers for detectors from 2021 and 2023. The nearest
  usable thing is a count-regression head with a discrete predictive distribution, the Deep Double Poisson Network
  (2406.09262, V abstract; images are among its test inputs, a 2024 paper, no drawing result). **Gap, not
  evidence of absence.** We should build it
  ourselves: sum of per-box probabilities gives a distribution, pick the threshold on dev exact-count rate.
- A floor-plan detector paper reporting per-image exact counts. The facility-enumeration paper is the only one. The
  strongest 2026 system for counting on blueprints I found, Handoff-H1 (2608.15032, V), is closed and scores quantities
  within 25%; its own text says an off-by-one count "typically exceeds the 25% tolerance", so its Windows & Doors
  score of 88 does not translate into an exact-match rate.
- AECV-Bench per-model numbers were missing from the earlier report: now read (V): Gemini 3 Pro 0.51 mean (door 0.39,
  window 0.34, bedroom 0.89, toilet 0.82), GPT-5.2 0.49 (0.28/0.27/0.91/0.76), Claude Opus 4.5 0.42 (0.16/0.16/0.91/0.76),
  best open model GLM-4.6V 0.39 mean (door 0.09, window 0.03). 120 plans from CubiCasa5K, CVC-FP and web drawings; MAPE for
  windows 20.4-69.3%. Scope L7 owns this.
- (RESOLVED in section 41, abstract found) "Why floor plan object detection breaks under real scans" (Automation in Construction 2026, listed in the
  citations of the CubiCasa5K paper): title found in a citation list, the paper itself I could not find or open.
- Weights licences for GeCo2, SAM 3 (gated card). Authors were not asked.

## 5. Open questions and missing tools

1. Does a fine-tuned exemplar counter beat a detector fine-tuned on our 104k boxes? Nobody has measured it; the
   zero-shot answer is no (F1 0.10-0.23 on drawings, 2610.09313). The cheap test is template matching with
   same-plan exemplars at four rotations on 50 dev plans, then a verify step (1-2 h plus 2-4 h, estimate).
2. Which threshold rule maximises exact-count rate: a global score threshold per class, per-image adaptive
   (count the boxes above half the top score), or a Poisson-binomial mode? Needs our dev boxes, no paper helps.
3. SAM 3 licence under record 0006, and access to the gated checkpoint: needs the owner's decision.
4. GeCo2 weights licence: ask the authors (their README asks to be emailed).
5. Pointers for other scopes: L2 (detect): RF-DETR P&ID card shows SAHI tiling per drawing type; DoorDet and the
   RT-DETR floor-plan repo are CubiCasa5K-trained (leak). L4 (rooms) and L1: fpvec-lab (arXiv 2608.25608, MIT code)
   ships corrected CubiCasa5K annotations (CC BY-NC-SA) and an opening heatmap result (opening F1 2.6x without
   retraining); I did not dig. L7: AECV-Bench numbers above; 2610.09313 (zoom-out splits lower recall in 19 of 21
   settings, V abstract) names engineering drawings.
6. Tools: no arXiv MCP here (used web-fetch agents, the headless browser for full texts, Semantic Scholar API for
   citation walks, one 429 on the 3rd call). The web-fetch agent summarises everything after the first ~40k
   characters, so for every number I used the browser text. Hugging Face model cards for gated models cannot be read.

## 6. Citation walks (forward)

- From CountGD (2407.04619): 100 citing papers in the Semantic Scholar list, 97 from 2025-2026. Read: CountGD++,
  GeCo2, Count Anything, CoLSR (via its parent list), UpCount, UniCounting, RECOUNT, CountZES, the counting survey.
  None applies to drawings. Also read: CoDi, HieraCount (Count Anything at Any Granularity), CountEx, BunchCount,
  PairTally, WS-COC, LVLM-Count. Not found on a search by name: DualCount (ECCV 2026, cited by the survey only); AdaCount and OCCAM now opened (sections 24 and 34)
  (2601.13871, abstract only).
- From GeCo2: 8 citing papers, all 2025-2026; the useful one is AgriCountDINO. BC-GECO2 (concrete aggregate
  segmentation and counting with GeCo2) exists in the list (journal, not opened): it is the only domain
  adaptation of GeCo2 I saw.
- From CubiCasa5K (1904.01920): 176 citing, 80 from 2025-2026, listed; relevant to counting: AECV-Bench,
  2509.17283, DoorDet. Floor-plan detection under real scans: one title, not found.
- From AECV-Bench: 9 citing papers (LED-BENCH, ARCH-B, MMArch, AEC-Bench, CrossProjection, MechVQA, ...); all
  benchmarks for VLMs, scope L7.

## 7. Items left unverified by earlier reports, now resolved (V, 2026-11-14)

| Item | Earlier status | Now |
| --- | --- | --- |
| CountGD code and weights | code MIT, weights licence unstated | code MIT; HF card `nikigoli/CountGD` says license: mit |
| CountGD++ | not in earlier reports | code MIT, HF card mit, training code released |
| GeCo, DAVE, LOCA | code MIT, weights licence unstated | still unstated for weights (repos checked by licence file only) |
| CounTR | licence unverified | code MIT (API); weights not read |
| PseCo | licence unverified | **no LICENSE file in the repository** (API 404): treat as all rights reserved |
| T-Rex / T-Rex2 | licence unverified | IDEA License 1.0: commercial use needs a licence from IDEA |
| P2PNet | licence and metrics unverified | licence: use "shall only be for the purpose of academic research" (LICENSE file) |
| PET, APGCC | not opened | both MIT code (API); weights only on Drive |
| SAM 3 | not covered | SAM License, no NC clause, trade-control exclusion; weights gated |
| Count-agnostic counters on drawings | "no paper found" | still none, after arXiv search by date, venue lists and four citation walks |

## 9. Round log additions (generation 2)
- Forward citation of 2610.09313 (OpenAlex, 2026-11-14): one citing work, arXiv 2610.25503 "From Seeing to Reporting"
  (Oct 2026), abstract only read (V). It shows a VLM that lists 173 records whose own stated per-type counts sum to
  188; a one-call "report records, then decode and count them" protocol cuts count error by 85.2% (GPT-6.1) and
  98.8% (Claude Sonnet 5.5) on 50 dense synthetic scenes. Same message as Point-then-Count: count the emitted
  records in code, never the number the model states. Synthetic scenes, not drawings. Code and responses released.
- Gap retry (arXiv all-fields search, two new phrasings): zero hits; the gap "exemplar counters on drawings" stays open apart from 2610.09313.
- Repo licences: 2610.09313's repo MIT; CountGD requirements.txt has no AGPL/GPL package.
- CountGD++ repo (V, gh api, 2026-11-14): requirements.txt (gradio 4, timm, transformers, torch<2.6, pydantic, deeplake<4)
  has no AGPL/GPL package that I could identify; 8 issues, none about small objects or training time. Issue #5: a user's
  blurry-image case gave poor boxes for CountGD++; the author fixed it with a single visual exemplar plus text, and
  says image enhancement (super-resolution) helps when objects are blurry (relevant to our phone photos).
- CoLSR numbers re-read in the full paper text (V, round 1): MAE/RMSE CountGD 7.84/10.71, DQ-DETR 4.24/6.81, REC 2.82/4.50, CoLSR 0.88/1.27; batch 4 on one RTX 3090. The licence of the dataset (CC BY-NC) stays as read from the repo.
- Facility enumeration 2509.17283 re-read in full (V, round 1): toilet-presence accuracy GPT-5 vs its detector+GPT-5 chain on eight public floor-plan sets, e.g. FloorPlanCAD 79.29 -> 85.71, CVC-FP 40.00 -> 86.67, SESYD 68.75 -> 95.83, CubiCasa5K 85.57 -> 87.63; the spread across sets shows how much style shift moves a VLM-only baseline.
- Counting survey 2608.23845 read in full browser text (V, round 1): no floor plan, blueprint or technical drawing coverage (the only grep hits are the substring 'cad' in other words); it lists TFCounter and SAM3Count as training-free exemplar/prompt counters (not drawing-tested). So the survey adds nothing for drawings.

## 10. Round 6 (generation 2, from lit-orch order): the template-matching recipe to copy
Source (V, read 2026-11-14): the paper's code repo, file `data/redp40/baseline_template_matching.py`, MIT code (gh api
license), data under a separate LICENSE-DATA file (not yet read). The benchmark is called REDP-X40 in the repo
(40 drawings) and LegendSpot in the paper text.
What we would copy, line by line:
- OpenCV `matchTemplate` with `TM_CCOEFF_NORMED` on grey images; template = the legend crop (for us: a box cut from the
  same plan).
- Scales (0.8, 0.9, 1.0, 1.1, 1.25) x rotations (0, 90, 180, 270), keep the best response per pixel over all 20 variants
  and remember which variant won. Skip a variant whose template is larger than the image or has near-zero variance.
- Working resolution: shrink the drawing so the long side is at most 4096 px, but never so far that the template's
  short side drops below 12 px (our symbols are 5-20 px on 855 px plans: upscale instead of shrink).
- Peaks: local maxima of the response map (dilation window = half the template's short side), floor score 0.30, at most
  3000 candidates, then greedy suppression of candidates closer than that radius.
- Threshold: not fixed; chosen to maximise mean F1 on other drawings (leave-one-drawing-out; the oracle per-drawing
  threshold is reported only as an upper bound). For us: choose it on dev plans, per class, by count error, not F1.
- Matching rule for scoring: one-to-one Hungarian assignment between points, a match if within 0.5 x sqrt(template w*h)
  (or 30 px at 1600 px). Our counting needs only the number, so score by exact count and within-one.
- Costs: the paper reports it runs locally in seconds per drawing (V, appendix text).
- Not covered: grey-only matching ignores colour (our red room outlines and blue/green layers); no edge-based matching
  (chamfer, Hough) was tried; rotations are only multiples of 90.
Related 2025-2026 work named in the paper's own related-work paragraph (V, line 308 of its text): FloorPlanCAD and
ArchCAD-400K panoptic symbol spotting (Luo et al. 2025), VLM symbol-counting benchmarks Shteriyanov 2025 (AECV-Bench),
Kondratenko 2026, Jung 2026; I have read AECV-Bench; Kondratenko and Jung not yet opened.

## 11. Round 7: exact-match and within-one count rates for 2-15 objects (one table)
Only sources where a count of a few objects is scored exactly; "V" = I read the number in the paper text.
| Source | Data, count range | Method | Result | Read |
| --- | --- | --- | --- | --- |
| BlueprintSymVL (Results in Engineering 28, 2025, open full text) | 100 engineering-blueprint regions (860x860 px), 5 symbol classes; baseline regions have few symbols, dense regions at least 10, similar-symbol regions 2-3; one visual exemplar as prompt; exact match needs the right count AND the right text labels | GPT-4o / Gemini 2.5 Pro / InternVL 2.5 78B / Qwen 2.5 VL 72B, one call | overall exact match 30 / 50.5 / 4.5 / 40.5 %; baseline 72 / 86 / 16 / 86 %; dense 26 / 32 / 2 / 10 %; similar symbols 18 / 38 / 0 / 28 %; precision about half of recall (false positives) | V |
| AECV-Bench (arXiv 2601.04819) | architectural drawings, door and window counts | VLMs | best door 0.39, window 0.34 exact; open models window 0.03-0.18 | V (earlier round) |
| Facility enumeration 2509.17283 | 8 public floor-plan sets, toilets present per plan | detector + GPT-5 chain | 66.67-95.83 %, e.g. CubiCasa5K 85.57 -> 87.63 (presence, not exact count) | V |
| Point-then-Count 2603.21746 | OCID tabletop scenes with 1-10 objects | fine-tuned small VLM, count emitted points in code | 69.1-81.9 % exact (direct count 69.1-73.6, point-then-count 76.2-81.9, three models) | V (Table 1 re-read, round 1) |
| LVLM-Count Emoji-Count | synthetic emoji grids | LVLMs | exact 24-30 % | V (earlier round) |
| From Seeing to Reporting 2610.25503 | 50 dense synthetic scenes | stated counts vs listed records | stated counts sum to 188 for 173 listed (one example); error cut 85-99 % by decode-and-count | abstract only |
Found later (section 14): template matching exact-count rate, 14/40 drawings (50% on small views). Not found: a within-one rate for drawings; count-error tables for CountGD or GeCo2 at 2-15 objects on
drawings (2610.09313 reports F1, not exact count).
What this adds: the BlueprintSymVL one-shot-exemplar setup is the VLM version of our "exemplar from the same plan" idea,
and its numbers (86 % exact in sparse regions, 10-32 % in dense ones) are a 2025 floor for VLM counting on drawings.

## 12. Rounds 8-9: score thresholds for counting, and point-supervised counters
- Thresholds (V, repo files read 2026-11-14): CountGD's README runs its CarPK test with `--confidence_thresh 0.23`
  (a flag, so tunable; value set per benchmark); PET hard-codes `thrs = 0.5` as the inference threshold in
  `models/pet.py` (no tuning hook); GeCo2's README names no threshold. 2610.09313 chooses the template-matching
  threshold by maximum mean F1 leave-one-drawing-out (section 10). No paper I opened tunes a detector threshold on count
  error or per class. Our plan stays: choose the threshold per class on dev plans by exact-count rate (own work).
- Point-supervised localisation counters, licences from the repo LICENSE (gh api license): PET MIT (last push 2025-04),
  CLTR MIT (2023-03), FIDTM MIT (2023-03), APGCC MIT (2024-07), SAHCC MIT (push 2026-10, found by repo search, not
  opened). All MIT code; weights are on Google Drive with no weights licence stated. Training data is crowds
  (ShanghaiTech, UCF-QNRF, JHU, NWPU): no CubiCasa5K leak, but also nothing close to thin-line symbols.
  Results at low counts: PET reports ShanghaiTech B MAE 6.18 (about 120 people per image) and Part A 49.08; I found no
  result at 0-40 objects. So these are only useful as architectures to fine-tune with point labels (our boxes give
  centre points), not as zero-shot counters.

## 13. Round 10: gap retries with new search terms (2026-11-14)
- Exemplar/one-shot symbol spotting on drawings: new terms ("P&ID one exemplar query-by-example") returned only
  OSSR-PID (2021, one prototype per class, graph network; synthetic 100 sheets plus 12 private sheets, search snippet) and
  Jamieson/Elyan/Moreno-Garcia 2024 (few-shot symbol detection for rare classes, snippet). Neither counts exactly. Gap stays open.
- Floor-plan detection on real scans/photos with symbol counts: nothing newer than 2021 data-augmentation work (search
  snippets). The "breaks under real scans" paper stays unfound.
- Count calibration: two usable pointers, both read as abstract/snippet only: (a) Riedlinger et al., "Towards Reliable
  Detection of Empty Space: Conditional Marked Point Processes" (arXiv 2506.21486, ICLR 2026): detector confidences are
  miscalibrated and a point-process model gives probabilities for empty areas (V abstract); (b) "Object Detection as
  Probabilistic Set Prediction" (ECCV 2022, Poisson multi-Bernoulli scoring; snippet). Practical route consistent with
  both, not shown on counts in any source: Platt-scale each detection score, treat candidates as independent Bernoulli
  variables, take the Poisson-binomial distribution of the count (exact by recursion); independence is the known caveat
  (overlapping candidates are not independent). Our own test.
- Repos opened in this round (V, gh api, 2026-11-14): CountSE (ICCV 2025 Highlight, soft exemplars for open-set counting):
  MIT code, trained on FSC-147 only (no CubiCasa5K leak), reuses CountGD's environment, so it is a drop-in variant of the
  CountGD fine-tune path, with no drawing result. SAHCC (ECCV 2026, local-spacing-aware Hungarian matching for
  point-supervised crowd counting): MIT code; a training-time matching change for PET-style models, crowd data only.
- Pointers only (belong to L7; abstracts read, V): Enginuity (arXiv 2606.03410, Jun 2026; parts-table extraction and VQA on
  service manuals; no symbol counting) and MechVQA (2605.30794, 3.3k mechanical drawings, 21K QA pairs, 10 tasks; no
  exemplar counting). DrawingVQA (2607.15418, CVPR Findings 2026; 33 construction drawings, 92 questions; search snippet) likewise.
  None gives a count-by-exemplar number, so nothing here changes the ranking.

## 14. Round 11: the exact-count rate of template matching (V, repo file `tm_summary.md`, read 2026-11-14)
The paper reports F1, but the repo's own summary gives count errors, so the gap "exact count of a few objects on
drawings" is partly closed. Template matching from the legend crop, multi-scale and 4 rotations, 40 drawings:
| Subset (count per drawing) | Threshold | MAE | mean relative error | F1 | exactly right |
| --- | --- | --- | --- | --- | --- |
| all 40 | leave-one-drawing-out | 7.2 | 22 % | 0.861 | 14 / 40 |
| all 40 | oracle per drawing | 3.7 | 11 % | 0.929 | 23 / 40 |
| sheets (6-116, long side 2947-11484 px) | leave-one-out | 12.5 | 33 % | 0.810 | 4 / 20 |
| views (3-43, long side 483-3520 px) | leave-one-out | 1.9 | 12 % | 0.912 | 10 / 20 |
| views | oracle | 1.4 | 9 % | 0.944 | 14 / 20 |
Reading: even the best exemplar method gets the exact count on only half of the small drawings with a deployable
threshold (50 %), and on 20 % of the large sheets. That is the honest "exact counter" number for query-by-example on
drawings: F1 0.86-0.91 does not mean the count is right. It supports the report's advice to add a verifier and a
second counter and to report a count only when they agree. The oracle threshold gain (10 -> 14 of 20 on views) shows
how much per-plan threshold choice is worth; the paper's six tuning drawings were chosen by the authors.
Data licence: images, templates and annotations are CC BY-NC 4.0 (LICENSE-DATA), research use only: do not copy
into our repo; use for our own testing only if the team accepts the non-commercial licence. Code is MIT.

## 15. Round 12: forward citations of BlueprintSymVL (Semantic Scholar, 2026-11-14; 10 citing works, 9 from 2026)
Read (abstract level, V): PlanSightRAG 2608.26091 (retrieval and compliance QA over civil plans; no counting), VLM graph
representation of building layouts 2608.24886 (147 library floor plans, node matching >= 92 %; spaces, not symbol
counts), PCB drawing parsing 2608.29268 (detector-free page parsing; no counting). Snippet only: ICICLE (SAC 2026,
same authors as BlueprintSymVL; one annotated visual example + text prompt extracts legend entries, 96-100 % extraction
accuracy on four industrial legend sheets; extraction, not counting), a P&ID review (2026), a PLC-HMI assessment paper,
a construction scene-reconfiguration paper. Not one of them measures counting by example on drawings, so the list of
exemplar-on-drawings evidence stays two papers deep: 2610.09313 and BlueprintSymVL.

## 16. Round 13: BlueprintSymVL design lessons for how we give the exemplar (V, full text, tables 5-7)
- Exemplar form matters for a VLM counter: a context-rich image (the symbol highlighted inside its surroundings) gave
  exact match 50.5 % with Gemini 2.5 Pro; the same symbol as a tight crop gave 36.5 % (recall 74.5 -> 66.7, precision
  53.2 -> 35.1). An example with one annotated instance equalled one with two (50.5 % both): one example is enough.
- Occlusion by revision clouds lowers exact match (regular / occluded): GPT-4o 36 -> 24, Gemini 63 -> 38, Qwen 43 -> 38.
  Our drawings carry red room outlines and labels on top of symbols: expect the same kind of drop.
- Per symbol class (exact match, Gemini): check valve 67.5, reducer 65, spacer 47.5, gate 37.5, butterfly 35: classes with
  a distinctive outline count best; look-alike symbols count worst. Windows next to wall lines are our look-alike case.
- Systemic: recall high, precision about half (Qwen 71 / 43 %), i.e. VLMs over-count; this is why the verify step and the
  second counter are on the ranked list, and why we should compare the two counts and refuse on disagreement.
- Note for transfer (the paper's own limit): 100 regions of 860x860 px, 5 classes, 5 regions per cell, four 2025 models.
  Tiny sample; the exact-match rates carry wide error bars (not computed by the authors).

## 17. Addendum to the section 11 table: the natural-image exact-count benchmarks with counts 2-10
- CountBench (487 usable images of 540) and PixMo-Count (counts 2 to 10 in each image), scored as exact accuracy and MAE
  (V, SAM 3 paper appendix F.4, read earlier from `sam3.txt`): SAM 3, internal checkpoint, counting = number of masks
  with confidence above 0.5 after non-maximum suppression by Interaction over Minimum (0.5): **94.0 % on CountBench,
  86.3 % on PixMo-Count**; MLLMs in the same table are compared on the same two sets. These are exact-match rates for
  2-10 objects on photographs of everyday things, with a text noun phrase and no exemplar: the upper reference for how
  good a detector-as-counter gets when the objects are textured and the scene is natural. The gap to drawings is the
  same story as 2610.09313: 94 % exact on photos, 14/40 exact (35 %) for template matching on drawings.
- Their counting recipe is the plainest one in the literature and worth copying as our baseline definition: confidence
  threshold 0.5 on the final masks, overlap-aware NMS (IoM 0.5) so that a part inside a whole is merged, count = number
  of survivors.

## 18. Round 14: training-free counters named in the 2026 counting survey (repos opened, V, 2026-11-14)
- TFCounter (SAM vit_b with a dual-point prompt and a similarity module; no counting training): the repo has **no
  LICENSE file** (GitHub licence endpoint returns 404), so I treat it as unusable until the authors add one; same status as PseCo.
- SAM3Count (CVPRW 2026 oral; text-prompted SAM 3 counting, ROI-guided adaptive tiling for dense scenes): MIT code; it needs
  SAM 3 weights, so the SAM License and gating issues of top item 5 apply; text prompts, no exemplar; no drawing result.
  Idea worth copying without the repo: a two-stage pass (full image first, tile only when the count is dense), which
  matches the "never zoom out, tile at the same scale" rule of 2610.09313.
- The survey's own caveat (V, text): segmentation-based counting is only as good as its masks; over-segmentation inflates
  the count, merged masks reduce it. For thin-line symbols that is the failure to check first.

## 19. Round 15: threshold and count-head leads from two more searches (corrected where the paper disagreed with the snippet)
- DQ-DETR (arXiv 2404.03507, AI-TOD-V2 aerial images, 1 to 2267 objects, V full text): its "categorical counting module"
  classifies each image into **four count levels** (it sets the number of decoder queries), total accuracy about 94.6 %
  (V, Table 7 text). It is a **bin** accuracy, not an exact count: the search snippet's "97.7 % for 10 or fewer"
  must not be read as exact match. The authors chose classification over regression of the count because counts span
  1-2267. Not an exact-counter result; mentioned because CoLSR used DQ-DETR as a baseline (4.24 MAE).
- Thresholds, from search snippets (A, not opened): InstructSAM 2505.15818 sweeps the confidence threshold 0 to 1 in steps
  of 0.02 and keeps the one with the best mean F1 per category set (a per-dataset F1 choice, not count error); an
  agriculture counting review (2303.02632) says the threshold should be the one that adds no counting bias;
  a 2026 anomaly-detection paper (2609.05091) counts with SAM 3 at several confidence levels and keeps the stable
  count instead of one operating point; NumBench (2608.28206) applies temperature scaling to detector confidences before
  counting. **Idea to test on dev, unshown in the literature I opened:** count at several thresholds and accept the
  count only if it is stable across them (cheap, uses only the detector).
- Count regression on small counts (snippets): face-count hardness study 2604.09689 (EfficientNet-B0 regression on 1-18
  faces; error and bias grow with the true count), YOLO-Count 2508.00728 (a cardinality head that sums per-object scores).
  Neither reports exact or within-one for drawings.
- Correction after opening the abstracts (V): 2609.05091 is training-free industrial anomaly detection with a
  normal-set calibration; its abstract does **not** mention SAM 3 or multi-threshold counting, so the snippet's description
  is unconfirmed (the full text was not read). 2604.09689 (face-count hardness) is about data complexity at rising instance
  density, nothing for drawings. The "count stable across thresholds" idea therefore stays our own, with no published support.
- YOLO-Count (ICCV 2025, 2508.00728, abstract V): a differentiable open-vocabulary counter whose regression target is a
  "cardinality map" (sums to the count, accounts for object size); built to steer text-to-image generation; no drawings,
  no exact-count table in the abstract, repo not found by my search (licence unknown). Not ranked.
- CountGD on the same low-count set (V, full text 2407.04619 Table 2, re-read): trained on FSC-147 (at least seven objects per
  image) and tested **zero-shot on CountBench with text only: MAE 0.86, RMSE 3.1** (CounTX 6.64 / 15.75). The 2-10 object
  regime is therefore fine for natural photos with a noun phrase; the same family drops to F1 0.10 on drawings
  (section 0, item 1). The shortest-side-800 rule, self-similarity SAM normalisation (10.92 in the ablation row) and
  the Table 3 modality ablation (text 12.98 / exemplars 8.31 / both 5.74 test MAE on FSC-147) also re-read and hold.

## 20. Licence check against our own rule (V, repo record 0006 and docs/ENGINEERING.md §4 as quoted in it, read 2026-11-14)
Allowed in shipped code: MIT, BSD, Apache-2.0, ISC; LGPL only as an unmodified dependency by explicit decision; GPL, AGPL and
non-commercial licences stay out of shipped code. Applying it to this report's candidates:
- Fine as code: OpenCV (Apache-2.0) template matching and the MIT repo of 2610.09313; GeCo2, CountGD, CountGD++, CountSE,
  PET, CLTR, FIDTM, APGCC, SAM3Count code (all MIT).
- Not allowed in shipped code: P2PNet (academic only), T-Rex (IDEA licence), CoLSR's dataset and the LegendSpot / REDP-X40
  images and annotations (CC BY-NC 4.0: for our own dev tests only, never in the repo or the product).
- Needs a decision: SAM 3 (SAM License, custom, gated weights; not on the list); weights of GeCo2 and the Drive-hosted
  point-counter checkpoints (no weights licence stated); TFCounter and PseCo (no LICENSE file, so no right to use).

## 21. Round 16: SAM 3 on out-of-scope domains (V, SAM 3 paper text re-read; the numeric cells of its Table 3 did not render)
- The authors say RF100-VL "contains domains with specialized prompts that are out of SAM 3's current scope" and that SAM 3
  "adapts through fine-tuning more efficiently than baselines": 10-shot fine-tuning (box loss only, no mask loss) is
  their route to a new domain, and they report it beating in-context prompting by Gemini and grounding-DINO experts.
  So for line drawings the published route is fine-tune, not zero-shot; it needs the gated weights and the SAM License.
- One exemplar box on COCO/LVIS/ODinW13: SAM 3 beats T-Rex2 by +18.3 / +10.3 / +20.5 AP+ (V). The interactive loop (add a
  positive exemplar for each miss, a negative one for each false positive) improves cgF1 faster than point corrections.
  That loop is the natural "human corrects the count" UI if SAM 3 were allowed; it exists for CountGD++ too (negative exemplars).
- CountSE (ICCV 2025 Highlight; abstract read V on the CVF page): a **text-only zero-shot** counter that builds its own
  "soft exemplars" at several scales (similarity-selected candidates, then clustering-based filtering) to feed an exemplar
  counter. Idea we can copy without the repo: self-generated exemplars from the plan's own first-pass detections, filtered by
  clustering (the same idea as DAVE's verify step). Numbers not read (page text only); MIT code, trained on FSC-147.

## 22. Round 17: the "breaks under real scans" paper, one more attempt (2026-11-14)
Semantic Scholar's search (API, V) lists "Why floor plan object detection breaks under real scans: a controlled study of
robustness limits", Automation in Construction, 2026, so it exists; a request for its abstract and PDF link hit the rate limit
(one 20 s retry, no more), and a web search for the exact title found no page. Elsewhere in the same listing: FloorYOLO,
an attention-enhanced YOLOv8n for floor-plan object recognition (Frontiers in AI, 2026; YOLOv8 from Ultralytics is AGPL, so check its repo before any use; same issue as SkeySpot
line in the table) and DoorDet (2508.07714, CubiCasa5K-trained). Status: title confirmed, content unread, journal page
probably paywalled; question for L2/L10 owners: is anyone able to open it.

## 23. Round 18: Qwen3-VL's CountBench cells (V, PDF text of arXiv 2511.21631 via pypdf; the HTML tables had not rendered)
- Table 2 (flagship Qwen3-VL-235B-A22B and competitors) lists CountBench accuracy of 93.7 and 93.0 in its first two columns
  and 91.0 / 91.0 / 91.7 / 87.8 / 93.1 / 91.9 for the rest; Table 3 (medium models) 90.0 / 89.8 / 94.1 / 94.9 / 86.0 / 83.7 /
  91.0 / 84.1; Table 4 (small models) ends at 84.1 / 88.4 / 89.4 / 84.9 / 91.5 / 80.5 / 80.0 / 62.9. I did not match every
  column to its model (the extracted header row is not aligned), so the usable statement is the **range: 62.9 to 94.9 % on
  CountBench (2-10 objects), flagship models 91-94 %, the same band as SAM 3's 94.0 % in section 17**, and the smallest
  models far lower. VLMs and detectors are equal on photographs of 2-10 things; the drawing results (sections 11, 14) show
  the same models at 10-50 % exact.

## 24. Round 19: AdaCount (arXiv 2607.02139, Jul 2026, technical report; abstract V, repo found by search, not verified as the authors')
Training-free zero-shot counter on SAM 3: a prototype similarity map finds target-relevant regions, then **similarity-guided
spatial warping** gives them more resolution and feature modulation boosts target features, aimed at dense small objects
that SAM 3 misses or merges. A candidate repo `Mengqi-Lei/AdaCount` is MIT-licensed by GitHub's licence field (V) but its owner
does not match the paper's authors, so I treat it as unofficial. Text prompts only (no exemplar), needs SAM 3 weights (licence
and gating issues of top item 5), no drawing result. The "reallocate pixels to where the exemplar says the objects are"
idea matches the tile-at-native-scale rule from 2610.09313 and our need to upscale 5-20 px symbols; copy the idea, not the repo.

## 25. Round 20: construction-takeoff products and within-one metrics (search snippets, A; none opened)
- Takeoff vendors (Roboflow post May 2026, Trimble 2026 results from 4,000+ contractors, ConstructConnect 2026 guide, STACK Symbol
  Counting AI, Drawer AI): all describe the same pipeline shape (tile each sheet, detect and classify symbols, merge
  duplicates, a person reviews exceptions). STACK states its counts are returned only where confidence is at least 50 %, and
  labels the feature experimental. **No independent error rate for any of them**; the only figures are time savings. So the
  industry practice (tiling + detector + human review of low-confidence) is what our counter plus "refuse on disagreement"
  would replace with a stated uncertainty.
- Within-one metrics: not found; two newly seen VLM-counting papers worth L7's glance, both snippet-only: NumerosityVLM
  (Aug 2026, near 95 % in the 1-4 range for top models, weaker models mean 21 %) and "Give the Model a Finger" (NeurIPS 2026,
  exact on small sets, drift to estimation on larger ones). Both are natural images.
- Opened the Roboflow post itself (V, 2026-11-14; vendor marketing, not a study): the production pattern is **one detector per
  sheet type** (electrical, plumbing, mechanical, structural, architectural; "a unified model is almost always worse"), 29
  custom models in the case-study company, labels by plan-reading experts, overlapping tiles at the training resolution merged
  at page level, active learning on production misses; it claims "exactness a human would" but **gives no error rate**. Transfer: a
  detector per class family and tiling are standard industry practice; our exemplar-based route is the data-poor alternative.

## 26. Round 21: open-issue scan on training, memory and dense scenes for the three exemplar counters (V, gh issue list titles + a few threads, 2026-11-14)
- CountGD (60 most recent issues): many ask for custom-dataset training and fine-tuning (#40, #52); the author says she will write
  fine-tuning instructions and points to #22 for adapting to detection data (the box-centre vs box target slice). Issue #35 reports
  inconsistent output in a highly dense scene; the author asked for frames, no fix published in the thread. No issue mentions
  line drawings, thin objects or memory limits.
- GeCo2 (all issues): repeated requests for training code and training stability; a community app (offline Android counter)
  built on it, so inference is cheap enough for phones after export.
- DAVE: "CUDA out of memory", "training memory leak", and questions on training the detection stage: training code exists
  but is fragile.
Reading: all three are easy to run for inference, **none has a maintained, documented fine-tuning recipe for new domains**. A
fine-tune on our plans is possible but is our own engineering, matching the "maybe, fine-tune only" verdicts.

## 27. Round 22: title filter on forward citations (Semantic Scholar, 2026-11-14)
Citing works of GeCo2 (8), CountGD (101 returned) and CountGD++ (16), filtered for drawing, floor, blueprint, plan, symbol, CAD,
architecture, engineering, diagram, document, schematic in the title: **no hit that is about drawings** (the matches were a tracking
paper and a remote-sensing counting paper). arXiv 2610.09313 has no citing work yet in Semantic Scholar (one in OpenAlex, section 9).
So the sentence "no exemplar counter has been evaluated on drawings except in 2610.09313" survives a forward walk from all four
anchor papers.

## 28. Round 23: AECV-Bench table re-read in the PDF text (V, arXiv 2601.04819, Table 1 "object counting per-field accuracy/recall", 120 floor plans)
Columns door / window / bedroom / toilet (mean accuracy first): Gemini 3 Pro 0.51 (0.39 / 0.34 / 0.89 / 0.82); GPT-5.2 0.49
(0.28 / 0.27 / 0.91 / 0.76); Claude Opus 4.5 0.42 (0.16 / 0.16 / 0.91 / 0.76); Grok 4.1 Fast 0.37 (0.09 / 0.17); GLM-4.6V 0.39
(0.09 / 0.03 / 0.79 / 0.82); **Qwen3-VL-8B Instruct 0.39 (0.09 / 0.10 / 0.76 / 0.81)**; Nemotron Nano 12B 0.38 (0.12 / 0.18);
Mistral Large 3 0.32 (0.10 / 0.09). The text calls the door and window cells "exact-match rates". Mean MAPE 16.0 % (Gemini) to
29.5 % (GLM). Reading: rooms (bedroom, toilet) are counted well by every model (0.46-0.91), symbols (doors, windows) badly
(0.03-0.39): the small open model we could run on our own box scores 0.09 and 0.10 on door and window, **so a VLM alone is not
an exact counter for door and window symbols**; this agrees with the template-matching exact-count rate of 35-50 % in section 14.
All numbers re-verified against the report's earlier rows (Gemini, GPT, GLM) and the one new row (Qwen3-VL-8B) added.

## 29. Round 24: CountingDINO, the "template matching in learned feature space" option (abstract V, repo files V, 2026-11-14)
- arXiv 2504.16570, WACV 2026: a **training-free exemplar counter**: DINOv2 features (ViT-L/14 with registers in the README
  command), the exemplar's feature patch cut with ROI-Align and used as a convolution kernel on the image's feature map, similarity
  map normalised into a density map, FSC-147 only. No labels anywhere in the pipeline, so **no CubiCasa5K leak by construction**.
- It is the nearest published relative of our own plan: normalised cross-correlation (section 10), but on DINO features instead of
  pixels. Why it might matter: pixel template matching loses to stroke-width and scale shifts (2610.09313 library case 0.87 -> 0.38);
  features might survive them. Unproven on drawings; a 14-px patch stride is coarse against 5-20 px symbols (needs upscaling).
- Licence: the repo has **no LICENSE file** (GitHub licence endpoint 404), so not usable as code until the authors add one; the
  backbone DINOv2 is Apache-2.0 (earlier read), so re-implementing the few lines (ROI-Align prototype, depthwise correlation, peak
  picking) is allowed. This is a one-day experiment: run the same recipe with DINOv2 patch features and compare to pixel
  template matching on 50 dev plans.

## 30. Round 25: BlueprintSymVL data availability (V, paper "Data availability" section and the Zenodo record's metadata, read 2026-11-14; nothing downloaded)
The benchmark (100 regions x occluded copies, five valve and fitting classes, annotation files with symbol names and counts) is
openly published on Zenodo as one 6.2 MB zip under **CC BY 4.0**, the paper under CC BY too. It is the only drawing-symbol
counting set I found with a licence that allows use beyond research (the LegendSpot data is CC BY-NC). Limits: P&ID-style
engineering blueprints, not floor plans; the 860x860 regions are screenshots; scoring needs labels as well as counts. Use: a
cheap, legally clean sanity set for the exemplar-in-context idea if the team accepts non-floor-plan data. Whether the
annotations carry point positions (needed to score template matching) is not stated in the text I read: check after download.

## 31. Round 26: how GeCo2's demo picks its count threshold (V, `app.py` of its repo, read 2026-11-14)
`post_process` keeps boxes whose score is above **the image's own best score times the slider value** (default 0.33, range 0.05 to
0.95), then non-maximum suppression at IoU 0.5; the count is the number of survivors. This is a **relative** threshold: the best box
always survives, so an image with **zero** true instances still returns at least one detection. For us that means: GeCo2's demo
rule cannot say "none" (a window count of 0 is a common true answer), and the absolute score of the best box must be checked
separately. CountGD's flag in contrast is an absolute `--confidence_thresh 0.23` (section 12). 2610.09313's own report that the best
per-drawing threshold gives at most 0.44 F1 for GeCo2/CountGD shows the same fragility.

## 32. Round 27: CountGD++ README details (V, repo README, 2026-11-14)
- It runs in **two exemplar modes**: "internal" (a box cut from the image being counted) and "external" (one box from one image applied across a
  whole dataset), each with optional negative text and a negative exemplar: both of our use cases (same-plan exemplar, dev exemplar
  reused across plans) are supported in the released inference scripts.
- The dense-scene mode ("adaptive cropping", for 800+ objects) crops the image and applies AI super-resolution to every crop, but the
  super-resolution used in the paper is a **paid web tool** (Bubbi image upscaler); the authors publish the enhanced crops only for FSCD-147.
  So the reported dense-scene numbers are not reproducible with the released code on our own images unless we substitute an open upscaler
  (repo issue #5, read earlier in this report, mentions a free enhancer which is Real-ESRGAN, BSD-3-Clause per its LICENSE (V, gh api): a licence-clean open upscaler for our small symbols). Our plans (under 100 objects) would not
  trigger adaptive cropping anyway, but small-symbol upscaling would be our own step.

## 33. Round 28: repo search for newer point-supervised localisation counters (GitHub search by topic words, 2026-11-14)
Low yield: the search returns mostly unrelated or tiny repos. Useful finds: the NWPU-Crowd sample code for **localization**
(MIT; the standard F1-at-distance evaluation for point predictions, which is the metric family 2610.09313 also uses),
`LGD-Peaket` (2026-09, licence "other", zero stars, unverified) and FocalGen (Apache-2.0, 2026-09, purpose not opened). No newer
point-supervised counter with a permissive licence and a published result at 0-40 objects. The list of section 12 stays the
usable one (PET, CLTR, FIDTM, APGCC, SAHCC, all MIT, crowd data only).

## 34. Round 29: OCCAM resolved from "noted, not opened" (V, paper text read 2026-11-14; arXiv 2601.13871, Jan 2026)
Training-free, **exemplar-free and prompt-free**, multi-class counting: SAM 2 masks from a dense seed-point grid, filtering, then a
threshold-based variant of FINCH clustering of mask features to group instances into classes; each cluster size is a count. Evaluated
on FSC-147, CARPK and a new synthetic multi-class set, scored by F1 as well as MAE. Code promised on a project page (not checked; a
GitHub search found no repo, so licence unknown). Transfer to drawings: the class-discovery idea (group all candidate marks by
appearance, then name the clusters) is a cheap way to **propose every symbol type on a plan without a legend**, and cluster sizes then
give per-type counts; but SAM 2 masks of 5-20 px thin strokes are unproven, and the cluster-merging threshold is the weak point.
Rank: not ranked; idea only, for L11.
- HoloCount (2607.06420, Jul 2026, abstract V): a hierarchical MLLM counting benchmark (semantic, analytical, robustness incl. high density); 20+ MLLMs degrade as tasks get analytical or dense; natural images, no drawings; belongs to L7. MambaCount (2606.17650): text-guided open-vocabulary counter, not opened.

## 35. Round 30: reference walk of 2610.09313 for drawing-related work (V, its reference list, 2026-11-14)
Its drawing-related references are exactly: FloorPlanCAD (Fan 2021), CubiCasa5K (Kalervo 2019), Raster-to-Vector (Liu 2017),
ArchCAD-400K (Luo 2025, panoptic symbol spotting, supervised, CAD vectors), the digitisation survey of Moreno-Garcia 2019, and the
three benchmarks AECV-Bench, BlueprintSymVL and DrawingVQA. Every one is already in this report or named in L2/L7. So the reference walk
and the citation walks (sections 6, 9, 15, 27) agree: **the field of exemplar counting on drawings is these two papers
(2610.09313, BlueprintSymVL), with AECV-Bench measuring VLM counts on whole floor plans**; everything else is natural-image counting.

## 36. Round 31: venue sweep, title scan of the CVF open-access lists (V, pages fetched 2026-11-14; main-conference lists only, titles only)
- **CVPR 2026** titles with "count": Boosting Quantitative and Spatial Awareness for Zero-Shot Object Counting; UNICBench (unified
  counting benchmark for MLLMs); CountGD++ (already read); Plant Taxonomy Meets Plant Counting (dataset, hundreds of species);
  Adapting Lightweight Image-based Counting Models for Video Crowd Counting; a geo-guided counting benchmark for Earth-observation
  imagery under adverse conditions; Understanding Counting Mechanisms in LLMs and VLMs; AV-Reasoner (audio-visual counting).
- **ICCV 2025**: CountSE (read), Counting Stacked Objects (3D volume, ruled out), YOLO-Count (read), Text-guided Local Ranking and
  Number-evoked Global Attention for zero-shot counting, CAPTURE (occluded-object counting to test spatial reasoning of VLMs),
  Video Individual Counting for Moving Drones.
- None has "drawing", "floor plan", "symbol" or "blueprint" in the title. New names to read if time allows: UNICBench (L7),
  CAPTURE (occlusion counting, bears on our overlapping labels), the Earth-observation benchmark (small dense objects under
  haze; closest in spirit to thin marks on noisy scans). Not opened.
- CAPTURe (ICCV 2025, 2504.15485; search-result summary, A): counting objects in a pattern behind an occluder; models do worse with occlusion even for GPT-4o; giving **object coordinates as text** improves the count a lot: same message as Point-then-Count and 2610.25503 (list the points, count them in code). Natural patterned images; no drawings.
- Round-1 verification of top item 2 numbers against the paper text (V): zoom-out lowered recall in 19 of 21 settings; packing 8 tiles 0.77 -> 0.47 recall (GPT-5.6, full sheets); high-resolution mode F1 0.89 -> 0.33; Qwen3-VL LegendSpot recall 0.37 -> 0.56; Gemini 3.8 0.62 -> 0.90 and Gemini 4 0.85 -> 0.98 with the safe split; GPT-5.6 zoom agent 0.97 vs 0.91 for its tiles. All match the report.

## 37. Round 32: an independent second measurement of legend-based template matching on drawings (V, full text of a 2026 master's thesis, Chalmers, 79 pages, open PDF; read via pypdf 2026-11-14)
"Beyond the Legend: Symbol Localization and Reference-Guided Classification in Industrial Diagrams" (2026; electrical housing diagrams,
industrial partner's data, not public). It compares **sliding-window template matching with the legend symbols as templates** against a
two-stage route (a generic symbol-region detector, then classification of each region against the legend by template matching or a
Siamese network). Numbers (V, discussion text and tables 4.1 and 4.5):
- Sliding-window template matching over the whole diagram: **recall 0.702, F1 only 0.519** (many false positives); very class-dependent:
  sockets F1 0.788, switches and "misc" very poor. The author's own reading: it "breaks down when symbols are thin, similar to other classes,
  or similar to background structures", and is slow on large images.
- Generic region detector: recall up to 95.42 % of the relevant symbols (trained on synthetic data).
- Classifying the proposed regions with template matching: F1 0.730 (native) and 0.734 (size-weighted); **a perfect bounding box did not
  improve it** (0.702), so the bottleneck is the clean-legend-versus-instance appearance gap (stroke width, scale, wiring, rotation in 5-degree
  steps), not the localisation. Multichannel (extra representations) template matching was worst (F1 0.649), noise-sensitive.
- Siamese-network classification came out "comparable" to template matching.
What this adds: (1) it **agrees with 2610.09313's failure case** (reference not cut from the same drawing: 0.87 -> 0.38) on a third
data type: legends are clean and instances are not. (2) It supports cutting the exemplar from the same plan, and the two-stage idea
"cheap region proposer, then verify against the reference" (our top items 1 and 7). (3) Rotation in 5-degree steps was too coarse for it;
ours are 90-degree multiples, so four rotations suffice. Evidence level: a thesis, one company's diagrams, no error bars: use as
corroboration only.
- Two more leads from the 2026 searches, both resolved: arXiv 2204.13277 (Sarkar et al., Apr 2022; abstract V): finds the objects in a drawing's legend
  table and their position and count with several networks pre-trained on drawing templates, no per-template training; an industrial
  patent-style paper, no numbers in the abstract, so only the idea (legend as the exemplar source) counts as support. The "CAD floor plan
  counting with visual and textual information" item the search mentioned (airaxiv 2875) returned Not Found: unverified, not used.
  CAD-Prompted SAM3 (2602.20551): SAM 3 conditioned on CAD geometry for industrial parts, not drawings; not opened beyond the title.

## 38. Round 33: adjacent field, fluorescence-microscopy cell counting (abstract V, 2026-11-14; CellFMCount, ICDM 2025, arXiv 2511.19351)
3,023 images, over 430,000 dot-annotated cells, test counts of 10 to 2,126 per image; three families benchmarked (regression, crowd
counting, cell-counting methods); the authors adapt SAM as a **density-map** counter trained only on dot annotations ("SAM-Counter").
Transfer note: (1) cell counting is the field that has lived longest with "dots, not boxes" supervision, which fits our `elements`
(each box gives a centre point for free); (2) its counts are in the hundreds, ours are 0-40, so its MAE-style results say little about exact
count; (3) what breaks on our images: cells are blobs with texture, ours are thin outlines with look-alikes; density maps blur
neighbours, which hurts when a window sits one wall-thickness from a door; (4) staining-protocol variation is their style shift; our
equivalent is drawing style per firm, and the authors list staining-protocol variation among the dataset challenges (no measurement of its effect in the abstract). No exemplar mechanism
here; it is a supervised route.

## 39. Round 34: the paper's own tiling tool, for top item 2 (V, repo README and `tools/safe_tiles.py` header, MIT, read 2026-11-14)
`tools/safe_tiles.py` is a stand-alone planner (standard library to plan, Pillow to cut): input = image size, target size, the model's
image interface (token side and token budget, or a fixed grid); output = overlapping views so that each target keeps at least as many
tokens per side as in the whole image (and at least S* tokens when that is more), views overlap by one target margin so every target lies
whole inside some view, and `merge_points(plan, answers)` maps the model's points back to image coordinates (duplicates in the overlaps
are kept by default, `merge=True` merges points closer than the matching tolerance). The README says to calibrate the interface first by
reading billed tokens for blank images of several sizes (`experiments/calib_tokens.py`). For us: a copyable, MIT, no-dependency
starting point for any VLM pass over a plan photo or a high-resolution sheet; our targets are 5-20 px, so the planner will say "upscale"
or "tile" for most models, and the duplicates from overlaps need a merge distance of about half a symbol.
- Reference [5] of BlueprintSymVL (V): Shteriyanov et al., 'Unraveling the impact of density and noise on symbol recognition in engineering drawings', IEEE IS 2024: by the authors' own summary, occlusion is a primary cause of degradation for traditional object detectors on blueprints. Not opened (IEEE, probably paywalled); supports the occlusion caveat in section 16 for detectors as well as VLMs.

## 40. Round 35: "From Seeing to Reporting" (arXiv 2610.25503) read past the abstract (V, browser text, introduction and contribution paragraphs, 2026-11-14)
- Claim measured on dense synthetic scenes (five classes): **counting the records a model lists, instead of reading the counts it states
  in the same response, cuts per-type count error by 71 % to 84 % for GPT-6.1 and Sonnet 5.5** with no new call; the full "list first,
  decode, count" protocol cuts it by 85.2 % and 98.8 % at the cost of one call. Example: 173 listed shapes all matching a real shape
  within 20 px, stated counts summing to 188.
- Datasets used: SKU-110K, DOTA, DocLayNet, FSC-147, PixMo-Count, ScreenSpot-Pro (so retail shelves and aerial images are covered by its
  count experiments' families); no drawings. The framework's selection step (keep records that two calls agree on) is the
  "refuse on disagreement" idea in a formal version.
- Relevance to us: for the VLM counters in top items 2 and 6, the count must be the length of the returned point list, never the
  number the model writes. This is the cheapest published repair I found for VLM over- and under-counting.
- Code and 67,364 stored responses of 2610.25503: github.com/shijunzhe/vlm-set-reporting, MIT (V, gh api license). Same author group as 2610.09313.

## 41. Round 36: gap closed, the "breaks under real scans" paper (abstract V via the Crossref API, 2026-11-14; full text not read)
Crossref lists it twice: a Nov 2026 journal version (Automation in Construction, DOI 10.1016/j.autcon.2026.107193) and an SSRN preprint
(10.2139/ssrn.6378246) whose abstract it returns. Content: a **controlled robustness study on CubiCasa5K with paired raster renderings of
identical layouts** (appearance is the only thing that varies), with RT-DETR; paired Region-of-Interest variants separate background
texture and clutter from depiction shifts (stroke width, blur, boundary ambiguity). Findings in the abstract: degradation is **class- and
scale-dependent**; **strict localisation (AP75, AP@0.85) drops more than coarse detection (AP50)**; **geometry depiction shifts (stroke
width, blur, boundary ambiguity) dominate the loss, scanned background alone causes only moderate decline**; targeted fixes improve
thin-structure detection and strict localisation. Released: paired variants, verification scripts and trained checkpoints.
Why it matters here: (1) it is the first published *measurement* of style shift for a floor-plan detector, and says stroke width and blur are
the driver: exactly what our phone-photo and scan plans carry and exactly why a per-plan exemplar (same stroke width) should help
(2610.09313: 0.87 vs 0.38 with a library reference). (2) It tells us which numbers to expect to move: a count threshold that sits on a
loose-localisation (AP50-like) setting survives better than box accuracy. (3) **Leakage flag: its released checkpoints are CubiCasa5K-trained**
(same flag as DoorDet): do not use them as our baseline. (4) A direct test for us: render our vector gold at several stroke widths and blurs
and re-count with template matching and the detector; the paper's paired-variant idea is the recipe. Whether it reports counts: unknown
(abstract only). Journal full text probably paywalled; the SSRN preprint may be open.

## 42. Round 37: paywalled items opened through Crossref abstracts (V for the abstract only, 2026-11-14)
- Jamieson et al., IJDAR 2024 (10.1007/s10032-024-00492-9, "AI-powered symbol detection" in construction diagrams; the page that was empty
  in an earlier round): industry drawings in high resolution, two detectors, **mAP 79 % (YOLO-based) and 83 % (Faster R-CNN)**, framed around
  material takeoff; a supervised detector result, with no count-accuracy figure in the abstract. A useful anchor for what a trained detector
  gets on real construction drawings (mAP, not count).
- Shteriyanov et al., IEEE IS 2024 (10.1109/is61756.2024.10705201, "density and noise on symbol recognition"): Crossref has no abstract; the
  title and BlueprintSymVL's one-line summary of it (occlusion is a primary cause of degradation) are all I have.
- "Few-Shot Symbol Detection in Engineering Drawings" (Applied AI 2024, 10.1080/08839514.2024.2406712): Crossref has no abstract; not read.
Tool note for other workers: `api.crossref.org/works?query.title=...` returns abstracts for many paywalled journal papers and did not rate-limit me.

## 43. Round 38: two more 2026 legend-based template-matching papers (abstract V for the first; title only for the second)
- Han et al., "Symbol Recognition in P&IDs via Mask-Aware Template Matching with Spatial Similarity" (EC3 2026, DOI 10.35490/EC3.2026.241;
  abstract V on the conference page): **non-learning** template matching from the **symbol legend**; the template is turned into a mask
  (convex hull of the symbol's strokes), the similarity is the **IoU of the masks** (not pixel correlation), and duplicates are suppressed by
  **IoM-based non-maximum suppression** (the same overlap rule SAM 3 uses for counting, section 17); **F1 0.992 on real industrial P&IDs**
  (author-reported; set size not in the abstract; P&IDs are clean, high-contrast line drawings; full paper not read, "download paper" link not
  followed). It is the most direct 2026 evidence that a mask-and-IoU template matcher can reach near-perfect detection on line drawings, and it
  suggests the improvement we should test over plain `TM_CCOEFF_NORMED`: **binarise, take the symbol's mask, score by overlap, merge by IoM**.
  What may break on ours: P&ID symbols are drawn to a standard and printed digitally; phone photos and scans have broken or thick strokes that
  change the mask; windows share their strokes with wall lines.
- Title only (Crossref, no abstract): "An Automatic Legend Matching Method for Engineering Drawings Based on Block Detection and Feature Memory
  Bank" (CCDC 2026, DOI 10.1109/ccdc69976.2026.11560231): block detection then a memory bank of legend features; same two-stage shape as the
  Chalmers thesis (section 37). Not read.

## 44. Round 39 (last): Crossref title sweeps, 2025-06 to 2026-11 (titles only, U = unverified, nothing opened)
Floor-plan and drawing items seen: Evaluating VLMs for zero-shot room-area estimation in floor plan images (Periodica Polytechnica, 2026);
VLMs can parse floor plan maps (Robot Learning, 2025); SSLD-DET symbol detection in signalling layout drawings (Scientific Reports, 2026);
automated BIM modelling from non-digital drawings with an improved YOLOv11n (Smart Construction, 2026; Ultralytics YOLO is AGPL, check before any use);
ScrewCount, an exemplar-efficiency few-shot counting benchmark (VISAPP 2026, 10.5220/0014236300004084). None reports an exact-count rate on drawings.
The last query (stroke width, blur, scanned floor plans) failed on a non-JSON reply and was not retried.
