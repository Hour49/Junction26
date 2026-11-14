# lit-count-c: counting, practical fit (scope L3, angle c)

Worker lit-count-c, read-only. All pages read 2026-11-14 (Helsinki). Reading log with one line per source:
`lit-count-c-log.md`. "verified" = I read it on the page named; "reported" = the authors' own
claim. "Estimate" = my number, not measured. Page reading: web-fetch agent, plain curl and gh, and the headless
browser (`pwfetch`) for full arXiv HTML text.

## Answers to the two scope questions first

1. **Best published way to turn a decent detector into an exact counter.** No paper I opened reports an
   exact-match rate for a detector-threshold counter on 2-15 objects, and none does it on drawings. The nearest drawing number is AECV-Bench (multimodal LLMs, not detectors): exact-match door and window counting on 120 floor plans, often 0.40-0.55 (abstract read). What exists:
   - The counting models decide the count by thresholding the scores of their detections and tune that threshold
     on a validation split: CountGD uses one fixed sigma = 0.23 picked from {0.14, 0.17, 0.2, 0.23, 0.26} to minimise
     MAE (verified, arXiv 2407.04619 appendix and Table of hyperparameters); SAM 3 counts masks with confidence above 0.5 after a non-maximum suppression
     on "interaction over minimum" (IoM, overlap divided by the smaller mask) at 0.5 (verified, arXiv 2511.16719,
     appendix F.4). SAM 3 reports **accuracy 93.8% / MAE 0.12 on CountBench and 86.2% / 0.21 on PixMo-Count, both
     2-10 objects per image** (verified, Table 3 of the paper, vendor-measured, internal checkpoint, and FSC-147 is in
     SAM 3's training pool). That is the only exact-count rate on small counts that I found, and it is on photos.
   - A count *distribution* instead of a point count: Schroeter et al., MIDL 2022 (arXiv 2204.05276, verified) sum
     per-lesion existence probabilities as independent Bernoulli trials, which is a Poisson-binomial distribution
     (quadratic-time exact), and report count accuracy 87.6-88.7% and calibration curves on MS lesions (medical,
     not drawings). I found no paper that does this on detector boxes; it is about 30 lines to write ourselves.
   - Nothing on a learned count head that helps exactness: DQ-DETR (ECCV 2024, arXiv 2404.03507, verified) classifies
     the image into 4 coarse count bands (<10, 10-100, 100-500, more) only to choose the number of queries; it
     explicitly avoids regressing a number. Not an exact counter.
2. **Does per-plan exemplar counting ("two confident windows from this plan, find the rest") beat a fixed detector
   under style shift?** Not shown anywhere. The closest evidence is mixed: it supports the mechanism, and warns about exemplar choice and style shift:
   - CountGD++ (arXiv 2512.23351, CVPR 2026, verified) feeds the model's own top-3 boxes back as "pseudo-exemplars"
     for a second pass: FSCD-147 text-only MAE 16.55 -> 10.29 and RMSE 129.76 -> 33.52 (Table 1); CARPK MAE 2.48.
     This is the same mechanism as ours, but in-domain, with counts averaging 56 per image, against no fixed
     fine-tuned detector.
   - Exemplar choice moves the count: CountZES (arXiv 2512.16415, v4 2026-10, verified full text) shows visually
     similar exemplars give different counts, that a GroundingDINO-driven first pass gives few or no clean
     single-instance boxes in dense scenes, and fixes it with a three-stage inference-only pick (detector anchor,
     density-guided pool, feature consensus); cross-domain results on CARPK and two microscopy sets are better than
     the other inference-only methods. So "two confident windows" is only as good as the two boxes: pick exemplars
     by consensus over several confident boxes, not by the top two.
   - Four independent lines derive exemplars automatically and then count with them (VA-Count, ECCV 2024, arXiv
     2407.04948, abstract and method read: Grounding DINO patches plus a noise-suppression contrastive loss; and, 2025): CountGD++ (feed back
     top boxes), CountZES (density-guided pick) and CountSE (ICCV 2025, abstract read: soft exemplars at several
     scales, then clustering to drop bad ones; text-only FSC-147 MAE 7.84 as quoted in the CountGD++ table; code
     repo `pppppz22/CountSE` is MIT by gh search, not confirmed as the official one). The mechanism is mainstream,
     the evidence is all on natural photos.
   - The only exemplar-counter versus fixed-detector comparison I found is FamNet's Table 2 (arXiv 2104.08391,
     CVPR 2021, verified): on FSC-147 images whose categories COCO detectors know (282 test images), Faster R-CNN
     MAE 36.20, Mask R-CNN 35.56, RetinaNet 52.67 versus FamNet 22.76. Dense scenes (average 56 objects), detectors
     not fine-tuned, no style shift, and FamNet adapts per image at test time with exemplars (its "min-count" and
     "perturbation" losses, Section 3.3). It shows exemplars beat an untuned detector, not a tuned one.
   - Exemplar counters do not survive style shift: cross-dataset FSC-147 <-> FSCD-LVIS MAE is 29-30 for LOCA and
     DAVE with exemplars versus 8.66-10.79 test MAE in-domain; the best method on that protocol reaches 21-22 (URM, arXiv
     2505.16778, verified Tables 1 and 6; the two directions are FSC-147 to FSCD-LVIS and back).

## 1. Top 5 (floor-plan work and transfers in one list)

All five fill `elements` counts (window, door, toilet, sink, shower, bathtub) or serve stage 8 (`SecondCounter`).
Hours to a first number are estimates for a dev box with a 12-16 GB GPU, starting from an existing box list.

1. **CountGD++ as the stage-8 second counter, exemplars taken from the plan itself.** Transfer from exemplar-based
   open-world counting (natural images). Try.
   - Verified: code MIT (`gh api repos/niki-amini-naieni/CountGDPlusPlus/license`, pushed 2026-10-27); weights on
     Hugging Face `nikigoli/CountGDPlusPlus`, model card `license: mit` (read 2026-11-14), one `model.safetensors`
     with 233.9M parameters (API), a `count(model, image, text, exemplar_boxes=...)` call that takes exemplar boxes
     drawn on another image and negative text and boxes, a pure-PyTorch fallback when the compiled deformable
     attention kernels are missing, training code released (issue #6 answered). Paper Table 1 and A.2 as above.
   - Verified from `countgdpp.py` and `config.json` on the model repo (read 2026-11-14): Swin-B 384 backbone, input
     resized to short side 800 px with long side at most 1333, default score threshold 0.23 (`CONF_THRESH`),
     exemplar features by RoIAlign, `count()` returns the count and normalised boxes (cx, cy, w, h). So a median
     855 px plan is upscaled to about 800 on the short side and an 8 px symbol stays about 8-10 px, which is
     small for a stride-32 feature map but the same range as CARPK cars; the threshold 0.23 was tuned for photos
     and must be re-tuned on dev for exact count.
   - External exemplars are supported by the `count()` call (`exemplar_image` separate from the counted image, verified on
     the model card), and CountGD++ reports gains from synthetic and real external exemplars (Table 1, FSCD-147 MAE
     10.29 -> 8.39 with one synthetic exemplar added). So a stock window or door symbol (for example rendered from our
     own labelled boxes of other plans) can be the exemplar when this plan gives no confident box; whether it
     transfers across drawing styles is untested.
   - Why negatives matter for us (verified, Tables 2 and 3 of the CountGD++ paper): on multi-class images, adding a negative
     text plus one negative exemplar cut MAE from 11.56 to 1.73 on Blood Cell Detection and from 2.41 to 0.41 on
     OmniCount-Fruits, and on the PrACo test the mean count of absent classes fell from 0.88 to 0.07 (and the PCCN
     score, which I read as the share of cases where the positive class is counted closer to truth than a negative one, rose
     from 62.86 to 97.99). On a plan, "count windows, not doors" with a
     door exemplar as the negative is the same setting. These are one-exemplar, mixed-fruit and cell images, not line art.
   - Leakage: no known CubiCasa data. Trained on FSC-147 plus mosaics (paper), on a GroundingDINO base
     (README lists O365, GoldG, Cap4M, OpenImage, ODinW, RefCOCO). Flag: **no known overlap with CubiCasa5K; web caption data (Cap4M) in the base model cannot be ruled out**.
   - Hours to first number: 1 to 2 (pip install plus snapshot_download, then run `count()` on 40 dev plans with
     exemplars cropped from the first confident detections). Estimate; the compiled-kernel route needs gcc 11,
     CUDA toolkit and detectron2 (GitHub README) and is not needed for a first number.
   - Install pins on the model card: `transformers<4.50`, `yapf==0.40.1`, `timm`, `addict` (README, read 2026-11-14), so
     give it its own virtual environment away from any RF-DETR or D-FINE stack that wants a newer `transformers`.
   - Dependency licences from PyPI (read 2026-11-14), for the demo and training route only: `deeplake` 3.9.x is MPL-2.0
     (file-level copyleft, not on the record 0006 list), gradio Apache-2.0, timm Apache-2.0, yapf Apache-2.0, addict
     and ushlex MIT, pycocotools BSD. No GPL or AGPL found. The Hugging Face `count()` route does not need
     `deeplake` or `gradio`. SAM 3's `pyproject.toml` lists "License :: OSI Approved :: MIT" while its LICENSE file is
     the SAM License; the file governs.
   - GPU memory: not stated for CountGD++. Its parent CountGD measured 15.47 GB reserved at inference by the GeCo2
     authors (A100, FSCD147, Table 5). Treat 12 GB as unproven; tile or run at 16 GB.
   - Breaks on our images: see transfer notes (5-20 px symbols after the 900-query model resizes the sheet; door and
     window glyphs look alike; pseudo-exemplars from a wrong first pass reinforce the error).
2. **SAM 3 (text prompt "window", "door", with optional exemplar boxes) as an independent second counter, local
   analysis only.** Transfer from promptable concept segmentation. Maybe.
   - Verified: counting protocol and Table 3 above; image exemplars (positive and negative boxes) are supported;
     450M vision encoder, input about 1008 px (Appendix C); "struggles to generalize to fine-grained out-of-domain
     concepts ... especially in niche visual domains" (Appendix B).
   - Licence: custom "SAM License" (read in full via `gh api repos/facebookresearch/sam3/license`): royalty-free
     limited licence, no commercial ban, ITAR/military exclusion, publication acknowledgement. It is not on the
     record 0006 list (MIT, BSD, Apache, ISC, LGPL), so shipping needs a decision. Weights: Hugging Face
     `facebook/sam3` is gated (manual approval, `license: other`); I could not read the card without login.
   - Leakage: SA-Co/EXT media pool lists 15 datasets (Table 25, verified) with no CubiCasa; the web-image pool is
     unknown. Flag: **unknown (not known to include CubiCasa5K)**.
   - Look-alike weakness is documented in 2026: SNAP (arXiv 2611.10092) reports SAM 3 assigns classes at Cohen's
     kappa 0.038 on eight look-alike cell lines; TAG (2610.14651) finds concept recognition, not masks, is the
     bottleneck; CASE (2610.39396) finds frozen SAM 3 does not honour negative exemplars. A door is a window with
     a leaf: expect confusion.
   - More 2026 hits from the SAM 3 citation walk (abstracts read 2026-11-14): DCR-SAM (arXiv 2610.27960) says SAM 3
     fails on concepts with semantic overlap, giving misclassified and redundant masks, which is our window/door
     pair; the Western bluebird benchmark (arXiv 2610.07802, 6,000 4K images where birds are a small fraction of
     the frame) finds supervised detectors (Faster R-CNN, RT-DETR) most reliable, open-vocabulary models poor
     zero-shot but competitive after fine-tuning, and supervised segmentation ahead of Grounded-SAM and SAM 3;
     PTQ4SAM3 (arXiv 2611.06143, WACV 2027) shows a W4A8 quantised SAM 3 image encoder keeps 54.8 COCO mask AP, with
     no memory figure in the abstract. All three point the same way: SAM 3 is a second opinion, not the primary
     counter, for small symbols.
   - The Hugging Face `transformers` page for SAM 3 (read 2026-11-14) says the model is meant for 1008 px input and
     custom resolutions may degrade accuracy; it shows an `image_size` config for lower memory. A 855 px plan
     upscaled to 1008 px is fine, tiling a plan into 1008 px crops is the untested part.
   - Repo facts (README and API read 2026-11-14): needs Python 3.12 and CUDA 12.6 or newer; checkpoints need an
     access request and a Hugging Face login; a `sam3/train` package and a `[train]` install extra exist (so
     fine-tuning on our boxes is possible, the paper's few-shot adaptation on ODinW13/RF100-VL is its evidence);
     SAM 3.1 checkpoints (HF `facebook/sam3.1`, also gated, `license: other`, 2026-03-27) add faster multi-object
     tracking, not better image counting.
   - Fine-tuning on a small GPU is a known sore point: open issue #251 on the repo (read 2026-11-14) says the
     training resolution (1008) and min_size (480) cannot be lowered because the RoPE parameters are hard-coded,
     users report out-of-memory errors, and one user says the Ultralytics implementation (AGPL, out for us) allows other
     resolutions. So treat 12 GB fine-tuning as unproven; inference is the safe use. No issue in the repo mentions
     floor plans, drawings, CAD or blueprints (gh search over issues, five queries).
   - `README_TRAIN.md` in the SAM 3 repo (read 2026-11-14, 190 lines): Hydra configs, single-GPU, multi-GPU and SLURM
     runs, example configs for Roboflow-100VL (10 to 100 image fine-tunes) and ODinW13; it states no GPU memory
     figure, so the 12 GB question stays open.
   - Measured SAM 3-family memory: Count Anything (arXiv 2605.30846, 2026-05, verified appendix Table 7) freezes the
     SAM 3 text-conditioned encoder, adds LoRA adapters and two counting branches (848.6M parameters, 1008 x 1008,
     BF16, batch 1) and reports peak inference memory 5.17 GB on an RTX 5090, 6.53 GB on an RTX 4090 and on an
     A100, latency 68 to 122 ms. So SAM 3-class inference fits 12 GB easily; training used 8 A100s at batch 24 per GPU
     (so LoRA training on 12 GB is unproven). On the authors' own cross-domain CLOC benchmark it reaches MAE 9.34 against
     25.80 for plain SAM 3 (Table 1 of that paper, authors' benchmark, six photo and microscopy domains, no drawings).
     Repo `Mengqi-Lei/count-anything` is Apache-2.0 (gh repo view, pushed 2026-08-12); it needs the gated SAM 3
     weights, so the SAM License still governs the product.
   - SAM3Count's README (read 2026-11-14) says the presence score must be disabled for counting (same as the SAM 3
     paper's appendix), points to the official `README_TRAIN.md` for fine-tuning, and gives its own fine-tuned
     checkpoint on Google Drive (no licence stated). Its repo `Joan947/SAM3Count` is MIT.
   - Hours to first number: 3 to 4 including the access request (estimate). SAM3Count (CVPRW 2026, MIT repo
     `Joan947/SAM3Count`, abstract read; PDF refused with 403) adds adaptive ROI tiling, the useful part for small symbols.
   - Independent head-to-head (AdaCount, arXiv 2607.02139, 2026-07, verified full text, text-only zero-shot, MAE):
     FSC-147 (dense, avg 56 objects) SAM 3 22.89, SAM3Count 19.80, AdaCount 18.97 versus CountGD 14.76, GeCo 13.30,
     CountGD++ text-only 16.55; CARPK SAM 3 3.52, SAM3Count 3.11, AdaCount 1.99 versus CountGD 3.83, CountGD++ 2.48;
     OmniCount-Fruits (sparse) SAM 3 0.44, AdaCount 0.37 versus CountGD 2.76, CountGD++ 1.97. Reading: SAM 3 is worse on
     dense scenes (the AdaCount abstract says it misses small objects because of limited resolution) and better on
     sparse ones, which is our regime (0-40, but with 5-20 px symbols, which is the dense-small failure).
3. **Poisson-binomial count distribution on top of the detector's own box scores, with per-class thresholds tuned
   for exact count.** Transfer from medical lesion counting (Schroeter et al. 2022) plus the CountGD/SAM 3
   thresholding practice. Try (it is our own 30 lines, no weights).
   - Verified: method and calibration plots in 2204.05276; per-class threshold grid in CountGD; no code to reuse.
   - Fills: `elements[*]` plus the `confidence` and abstain fields. Gives P(count = k); abstain when the top
     probability is below a dev-tuned bar, which is the only published route here to "a number we know is wrong".
   - Hours to a first number: 2 after a detector exists (calibrate scores on the dev slice first). Cal-DETR (arXiv
     2311.03570, train-time calibration (2023) for Deformable-DETR, UP-DETR and DINO, code Apache-2.0 by gh
     search `akhtarvision/cal-detr`, verified text) is the detection-calibration reference; its metric D-ECE measures
     precision against confidence only and, in its own words, ignores recall because missed objects carry no score.
     That is the catch for counting: a Poisson-binomial over the detector's boxes models false positives, not
     objects the detector never proposed, so missed windows stay invisible; the second counter (stage 8) is what
     can see them.
   - Breaks: adjacent identical symbols (a three-pane window strip) violate the independent-Bernoulli assumption;
     calibrate per class on dev, never on the sealed eval.
4. **GeCo2 (AAAI 2026) as a lighter exemplar counter.** Transfer. Maybe.
   - Verified: arXiv 2511.08048; FSCD147 test MAE 7.64, RMSE 39.39, AP 46.81 (Table 1); 4.98 GB reserved and 0.2 s
     per image on an A100 versus CountGD 15.47 GB / 1.3 s (Table 5, authors' measurement; the paper's text says 0.4 s on average for GeCo2, so the speed figure is inconsistent). Code licence MIT (LICENSE
     file read, and the author states MIT in issue #5). Weights: Hugging Face dataset repo `jerpelhan/geco2-assets`
     has no card, so the **weights licence is unstated**.
   - Training code is asked for in three open issues (#1, #10, #11) though the README has a "retrain on FSCD147"
     route; no custom-data fine-tuning recipe. Leakage: no known CubiCasa data (FSCD147 training).
   - A community Android app (`EiSiMo/howmany`, MIT, GeCo2 issue #22, verified 2026-11-14) exports GeCo2 to int8
     ONNX and runs it on the phone with one user-marked exemplar; the author reports MAE 4.59 on 100 FSC-147 test
     images and 66% of counts within 10% of truth. So CPU or small-GPU inference is real, and "one marked
     exemplar, count the rest" is the same interaction our stage 8 needs. Issue #17 says CPU was not tested by the
     authors.
   - Hours to first number: 2 (estimate). Rank below CountGD++ because the weights licence is unsaid and
     only exemplars (no text, no negatives) drive it.
5. **Proposal-then-classify with a per-project head (SNAP-style).** Transfer from microscopy annotation. Maybe,
   idea only (full text read 2026-11-14; it names no code repository; it is an annotation pipeline on SAM 2.1 proposals, so it
   speeds labelling more than it counts).
   - arXiv 2611.10092 (2026-11-06): one frozen SAM 2.1 pass makes proposals, a small head trained on 20-60 labelled
     images classifies them; with 20 images it beats a SAM 3 oracle tuned on the eval labels on 5 microscopy sets
     (F1 0.484 vs 0.441). We have 104k boxes, so the head is not the constraint; the proposals are (thin line art
     is not what SAM was trained on). A detector fine-tuned on our boxes does the same job more directly, so this
     is a fallback if no detector trains in time.

Not ranked, skip: PET (MIT file but README "academic purposes only"), P2PNet (licence text: academic research
only), T-Rex2 (IDEA License 1.0, non-commercial research), CLIP-Count/CounTR/LOCA (older, no better), DQ-DETR
(range classifier, not a counter), OCCAM (training-free; full text read, see below), stacked-object counting 2603.15470 (full text opened 2026-11-14: counts 19 to 20063, MAE metric, outside our range; 3D
inventory, off-shape). OCCAM (arXiv 2601.13871, 2026-01, text read): prior-free and multi-class, SAM 2 grid proposals
clustered by features (a threshold variant of FINCH), each cluster counted as a class; synthetic multi-class test set and F1
as metric; code promised, not found. It is the one published recipe that counts several symbol classes in one image with no
exemplar, a possible second counter if no exemplar is trusted.

## 2. Full table

Columns: method | from our field or transfer from | year, venue | code licence (read where) | weights licence |
trained on, leakage flag | metric, benchmark, input | GPU memory | hours to first number (estimate) | JSON field |
verdict | source, date read.

| Method | Field | Year, venue | Code licence | Weights licence | Training data; CubiCasa leak? | Reported metric | GPU memory | Hours | Field filled | Verdict | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CountGD++ | transfer: open-world counting | 2025-12 arXiv, CVPR 2026 | MIT (gh api) | MIT (HF card) | FSC-147 + mosaics, GroundingDINO base; no known leak | FSCD-147 text-only MAE 10.29 / RMSE 33.52 with pseudo-exemplars; CARPK MAE 2.48 | not stated (parent CountGD 15.47 GB) | 1-2 | elements counts, stage 8 | try | arxiv.org/html/2512.23351, huggingface.co/nikigoli/CountGDPlusPlus, 11-14 |
| CountGD | transfer | 2024 NeurIPS (v2 2025-03) | MIT (gh api) | Google Drive, no licence | FSC-147; no known leak | FSC-147 test MAE 5.74 (exemplars + text, corrected labels, CountGD paper); FSCD147 test MAE 8.35 in the GeCo2 paper table (GeCo2 7.64, GeCo 7.91, DAVE 10.45); CARPK 3.68; CountBench (2-10) MAE 0.86 | 15.47 GB reserved (GeCo2 paper) | 2-3 | stage 8 | maybe (superseded) | arxiv.org/html/2407.04619, 11-14 |
| GeCo2 | transfer | AAAI 2026 (arXiv 2511.08048) | MIT (file + issue #5) | unstated (HF dataset repo, no card) | FSCD147; no known leak | FSCD147 test MAE 7.64, AP 46.81; 0.2 s, 4.98 GB (A100) | 4.98 GB | 2 | stage 8 | maybe | arxiv.org/html/2511.08048, github.com/jerpelhan/GECO2, 11-14 |
| GeCo | transfer | 2024 NeurIPS | MIT | Drive, unstated | FSCD147 | FSCD147 test MAE 7.91 / AP 43.42; 23.83 GB | 23.83 GB | n/a | | skip (GeCo2 supersedes) | via GeCo2 Table 5 |
| DAVE | transfer | 2024 CVPR | MIT (gh api) | unstated | FSC-147 | FSC-147 test MAE 8.66; FSCD147 10.45 | 25.33 GB | n/a | | skip (memory) | via GeCo2 Table 5 |
| SAM 3 | transfer: concept segmentation | 2025-11, arXiv 2511.16719 | SAM License (gh api, read) | gated, `license: other` | SA-Co (incl. FSC-147, VisDrone, HierText, no CubiCasa); web pool unknown | CountBench acc 93.8 / MAE 0.12 (2-10 objects), PixMo-Count 86.2 / 0.21 | not stated for images (video throughput only, H100) | 3-4 | stage 8, local only; memory: 5.2-6.5 GB inference in the Count Anything paper (SAM 3 based) | maybe | arxiv.org/html/2511.16719, 11-14 |
| SAM3Count | transfer | CVPRW 2026 | MIT (gh api) | wraps SAM 3 | as SAM 3 | README table read (paper PDF refused): FSCD-147 test MAE 19.80 zero-shot, 13.02 fine-tuned (checkpoint on Drive); ShanghaiTech A 213.75 / 131.27 | not read | 4 | | maybe | openaccess.thecvf.com (abstract), 11-14 |
| URM | transfer: domain generalisation | 2025 arXiv 2505.16778 | repo `jbr97/URM` has no licence file (gh repo view, pushed 2025-06-09) | n/a | FSC-147 / FSCD-LVIS | cross-dataset MAE 21.87 / 21.17 vs 29-30 for LOCA, DAVE | not read | n/a | | evidence only | arxiv.org/html/2505.16778, 11-14 |
| Poisson-binomial counting | transfer: medical | MIDL 2022 (arXiv 2204.05276) | the paper says "see code for details" in a footnote whose URL the page text does not show; two guessed repo names gave 404, so code existence is unconfirmed | none | MS lesion MRI | count accuracy 87.6-88.7 | n/a | 2 | confidence, abstain | try | arxiv.org/html/2204.05276, 11-14 |
| DQ-DETR | transfer: aerial tiny objects | 2024 ECCV (arXiv 2404.03507) | repo `hoiliu-0801/DQ-DETR` has no licence file (gh repo view, pushed 2026-10-05) | n/a | AI-TOD-V2, VisDrone | AP gain +2.2 AP from counting + query selection; 4 count bands | 3090, batch 1 | n/a | | skip | arxiv.org/html/2404.03507, 11-14 |
| PET / P2PNet | transfer: crowd counting | ICCV 2023 / 2021 | MIT file with "academic only" README / academic-only text | n/a | crowd datasets; no known leak | PET paper read in full via ar5iv (arXiv 2308.13814): ShanghaiTech A MAE 49.34, B MAE 6.19, MAE only, crowds of people | n/a | n/a | | skip (licence) | github.com/cxliu0/PET, TencentYoutuResearch/CrowdCounting-P2PNet LICENSE, 11-14 |
| T-Rex2 | transfer | 2024 ECCV | IDEA License 1.0, non-commercial | same | detection corpora; unknown | not opened | n/a | n/a | | skip (licence) | github.com/IDEA-Research/T-Rex LICENSE, 11-14 |
| Molmo2-4B (point then count) | transfer: VLM pointing (also L7) | 2026-01 (HF) | Apache-2.0 (gh api, allenai/molmo2) | Apache-2.0 (HF card) | Molmo2 data collection (card header lists Molmo2-VideoPoint, Molmo2-MultiImagePoint); CubiCasa unknown | card lists no counting number; SAM 3 paper table has Molmo-72B CountBench 92.4 / PixMo-Count 88.8 | 4.85B params = about 9.7 GB in bf16 (arithmetic from the HF API count, not measured): inference only, tight on 12 GB | 3 | elements counts as points | maybe (L7 owns it) | huggingface.co/allenai/Molmo2-4B, 11-14 |
| CountingDINO | transfer: training-free exemplar counting | WACV 2026 (arXiv 2504.16570 v3) | repo `lorebianchi98/CountingDINO` has no licence file (gh repo view: none), pushed 2026-06-22 | Apache-2.0 (HF `facebook/dinov2-base` card, read 2026-11-14) | nothing trained by the method; DINOv2 backbone: its HF card names no pre-training dataset, so CubiCasa overlap is unknown | FSC-147 val MAE 25.48 / RMSE 57.38, test 20.93 / 71.37 (Table 1, verified); quadrant partition raises input resolution | backbone-sized, not measured | 1 | elements counts, stage 8 | maybe: no weights to train, lowest RMSE of the training-free group, but no licence on the code | arxiv.org/html/2504.16570v3, 11-14 |
| SNAP | transfer: microscopy | 2026-11 arXiv 2611.10092 | none named in the paper | none | microscopy | F1 0.484 vs 0.441 (SAM 3 oracle) | not read | n/a | | idea only | arxiv.org/abs/2611.10092, 11-14 |

Pointers to other scopes (one line each, not dug): Moondream 3 preview weights are BSL 1.1 with a no-third-party-service grant (HF card, read), so not on the record 0006 list; Moondream 2 and Qwen3-VL-4B are Apache-2.0 (HF API); FloorYOLO (Frontiers in AI, 2026-09-15, YOLOv8n, so AGPL code; SESYD and CVC-FP only) is L1/L2; GroundCount (arXiv 2603.10978, 2026-03: detector boxes written into the VLM prompt, but scored on the PhD benchmark's yes/no questions, so not exact counting) and AECV-Bench exact-match counts on plans and Molmo/Moondream/Qwen3-VL
pointing are L7 (other orchestrator); frozen-detector backbones, RF-DETR and D-FINE memory on 12 GB are L2; printed
labels are L5.

## 3. From other fields: transfer notes

- **Exemplar and open-world counting (natural images), CountGD++ / GeCo2 / SAM 3.**
  - Object role: a window cell or a toilet symbol is the "exemplar"; the plan is the "scene".
  - Why it should transfer: the same plan repeats the same symbol, so one confident box is a precise prompt.
  - What breaks: FSC-147 averages 56 objects per image, minimum 7, maximum 3701, images 774 x 938 px on average
    (verified, FamNet paper arXiv 2104.08391, 2026-11-14), so its MAE says nothing about 0-15 counts; CountGD
    zero-shot on CountBench (2-10 objects, text only) has MAE 0.86 / RMSE 3.1 (verified, Table 2 of 2407.04619),
    i.e. wrong by about one object on average, far from exact, against SAM 3's reported MAE 0.12;
    GroundingDINO-style backbones downscale the sheet (median 855 px, symbols 5-20 px), so an exemplar box of 8 px
    becomes a few feature cells; windows and doors share a thin-line look and the counters are known to count
    "everything" when classes mix (FocalCount arXiv 2502.10677, verified; PrACo++ arXiv 2605.02752, verified: only
    DAVE, CountGD and GroundingREC are robust to negative and distractor classes; plain text counters count absent
    classes); rotations by 90/180 are probably not in their training augmentation (my inference, lists not checked); pseudo-exemplars from a first
    pass that over-counts windows spread the error.
  - Self-similarity trap, verified in CountGD's appendix (Figure 6 of 2407.04619): when an exemplar box already
    contains several instances (a three-pane window strip), the model counts the strip's panes and the count is
    inflated; CountGD fixes it with a SAM-mask test-time normalisation that divides the count by the number of
    instances per exemplar (CountGD++ applies the same when exemplars are given). SAM masks on thin line art are
    untested, and our rule counts one window per drawn cell, so exemplar boxes must be single cells.
  - Code and weights: work as they are for a first number (CountGD++ MIT), need fine-tuning on our boxes for a
    score (CountGD++ ships training code, GeCo2 does not clearly).
- **Medical lesion counting (Poisson-binomial counts).** Object role: a lesion candidate is a detector box with an
  existence probability. Transfers as an idea and a few lines of code. Breaks: calibration is per class and per
  style; independence fails for touching symbols; the paper gives accuracy 87-88% on lesion counts that are mostly
  0-5, a similar regime but MRI, not line art.
- **Colony counting agent (AgentCount, arXiv 2611.05398, full text read 2026-11-14).** SAM 3 with several text prompts plus
  morphology filters, keeps masks, scores and warnings per image so a person can review. Pattern, not code, for our
  evidence output. Reports agreement on published endpoints (97.6% within 0.01 log10), not per-image exact counts. Full text adds: 57 plate photos, 49 (86.0%) classed correctly as countable or not countable, and on the 29 countable plates 89.7% of predicted counts fell within 10% of the manual count (a tolerance, not exact match); segmentation failures were mostly on dense plates. Latency 33.5 s per image on an RTX 3060 for the whole seven-agent pipeline including an LLM report step, which is the only consumer-GPU timing for a SAM 3 based counter I found. The "countable / not countable" gate is the same idea as our refuse-what-was-not-read rule.
- **Crowd and aerial counting (PET, P2PNet, CARPK).** CARPK (parked cars, identical adjacent objects, MAE 2.48 for
  CountGD++) is the closest public benchmark to a row of identical windows. Their code is academic-only: skip.
- **Cross-domain counting benchmark CLOC (arXiv 2605.30846, abstract read).** Six domains (scene, remote sensing,
  histopathology, cell microscopy, agriculture, microbiology), 220K images; no drawings. Confirms nobody has put
  line art into a counting benchmark.
- **Surgical instrument counting (audited, must be exact; CoLSR, WACV 2026, arXiv 2602.11024, verified full text).**
  Object role: an instrument on a tray is a symbol in a row of near-identical neighbours. 1,464 images with 7 to
  49 instruments (our range). All baselines fine-tuned on their data, single RTX 3090, 30 epochs, batch 4:
  CountGD MAE 7.84, DQ-DETR 4.24, REC 2.82, their chain-of-look model 0.88 (RMSE 1.27); Qwen2.5-VL-7B zero-shot
  17.06. Two lessons for us: (a) CountGD does fine-tune on a custom set, but a fine-tuned counter still lands off
  by about one or more per image even in the best case, so exactness needs the box evidence plus abstention; (b) a
  fine-tuned detector with a count module (DQ-DETR) beat fine-tuned CountGD there. Breaks on our images: photos of
  3D objects, a dataset we cannot reuse; no exact-match rate reported. No code link found in the paper text.
- **Colony counting of small clustered objects (ACFamNet Pro, arXiv 2604.20030, April 2026, verified full text).**
  Object role: a colony is a few-pixel blob next to others, like a window cell in a strip. FamNet-style exemplar
  counters take the exemplar by RoI Align on the query feature map; the paper's fix (aligned RoI pooling plus
  attention) reaches mean normalised absolute error 9.64% (5-fold, their Synoptics plates), 12.7 points better than
  FamNet. Not exact-count, no code link checked. Message for us: an exemplar of 8 px has almost no feature-map
  footprint at stride 16 or 32, so exemplar counters need the sheet upscaled or tiled before the exemplar is taken.
- **Detect-then-verify (DAVE, CVPR 2024, arXiv 2404.16622, verified full text).** Stage 1 proposes boxes at high
  recall, stage 2 clusters their appearance features and rejects outliers, which is the nearest published form of
  "second-pass verification of a detector count". Its mixed-class ablation is the multi-class warning for us:
  retraining LOCA on mixed-class images cut error on multi-class images by 43% but raised it by 28% on plain
  FSC-147; DAVE kept both. Memory 25.33 GB (GeCo2 paper), too large for our 12-16 GB boxes without tiling.
- **NMS and adjacent identical objects (crowd detection).** Search results only (not opened): end-to-end detectors
  without NMS reach higher recall in crowds (arXiv 2012.03544, abstract read 2026-11-14), while plain DETRs do worse than Faster
  R-CNN on CrowdHuman (arXiv 2012.06785, abstract read 2026-11-14). A 2026 industrial counting review (Sensors 26(14):4494, PMC13416764, read as Europe PMC XML after
  the PMC page refused; verified text) states that in extremely dense scenes detectors "tend to suppress adjacent
  true objects due to NMS, which leads to missed detection", citing one reference, and gives no exact-match numbers
  anywhere (it reports qualitative accuracy only). No paper isolates NMS undercounting as an error term. The
  practical rule from SAM 3's counting recipe, an IoM-based suppression (overlap over the smaller mask), is the one
  documented fix for "part inside whole" duplicates; a window strip needs the opposite (do not merge neighbours),
  so tune NMS per class on dev.
- **Plant counting with a frozen backbone (AgriCountDINO, arXiv 2609.29460, 2026-09, verified full text).** Frozen
  DINOv3 features, exemplar appearance and size tokens, 8.4M trainable parameters, 1024 x 1024 input, 100 epochs
  AdamW on 7,000 images; three-shot MAE 11.92 on TPC-268, zero-shot MAE 14.25 on FSC-147; "missed-object recovery"
  in training and an **exemplar-adaptive point NMS** (duplicate radius set from the exemplar's size) at inference.
  The NMS radius from the exemplar is the piece worth copying for a strip of adjacent windows. The DINOv3 weights
  are gated under Meta's "DINOv3 License" (HF `license: other`, gh licence NOASSERTION, read 2026-11-14), the same
  family of custom terms as SAM 3, so not on the record 0006 list. No code link found on the page. Breaks: crops of
  plants, not line art; DINOv3 features on thin black lines are untested.
- **Counting survey 2026 (arXiv 2608.23845, verified text, pwfetch).** Its metric section says Exact-Match, like MAE,
  is satisfied by compensating errors (a missed window and a spurious door still sum to the right number), which is
  why instance-level evidence (box per counted item) is the check and the count alone is not. It also lists two
  training-free instance-validation recipes: ValidCounter (exemplar boxes, SAM candidates, a vision-language
  encoder removes irrelevant candidates, count the survivors) and GroundCount (a detector's boxes are written into
  the VLM prompt so it counts an itemised list). Neither was opened at source; the survey is the only read.
- **Multi-class density estimation (Getting the Numbers Right, arXiv 2510.02213, 2025-10, verified full text).**
  Object role: one density head per class on a drone image, like our window/door/sink heads. Reports MAE cuts of
  33%, 43%, 64% against earlier multi-class estimators on VisDrone and iSAID, and says it beats YOLO11 (AGPL,
  out for us) by an order of magnitude in the most crowded samples but also in less busy scenes. Code at
  `LCAS/gnr_mcdest` has no licence file (gh api 404), so it is all-rights-reserved by default: idea only. It
  is the published sibling of the count-only FCN that scored 18% on windows and doors in our own test, which
  says that heavy supervision (boxes) is needed at our sizes; this paper does not contradict it, since its
  objects are 10-50 px vehicles and people, not 5-20 px line symbols.
- **Count supervision as an extra loss (abstracts read 2026-11-14; full text of both read later the same day).** QICA (CVPR 2026, arXiv 2603.16129) adds a
  multi-level "quantity alignment" loss and numerically conditioned prompts to a text-driven counter; WS-COC (ICLR
  2026, arXiv 2602.12774, code Apache-2.0 by gh api) trains an MLLM from image-level counts only, with
  "is the count in this range" dialogue and image-pair ranking losses. Both report MAE on FSC-147-type benchmarks, not
  exact match. For us the answer counts already exist next to the boxes (both come from the same annotation), so
  weak supervision adds nothing; the extra-loss idea would need a detector training loop we do not control. Skip.
- **Where VLMs fail at counting (abstracts read 2026-11-14, VLMCountBench full text 2026-11-14; scope L7 owns the drawing side).** VLMCountBench (arXiv
  2510.04401, 2025-10; full text adds that it scores exact correctness per object type, best model Qwen2.5 72B at 0.60 at level 1 falling to 0.45 at level 3): VLMs count reliably when one shape type is present and fail when several shape types are
  mixed, which is a plan with windows, doors and sinks in one image. "Counting to Four is still a Chore"
  (arXiv 2604.10039, 2026-04): the count evidence is strongest at the modality projection and fades in later
  language layers, so the fault is partly under-use of visual evidence; a lightweight attention-share intervention (MAS) is
  proposed; full text read 2026-11-14: its gain is up to 1% accuracy, so it is no fix; the CountingTricks suite shows most of 10 VLMs under 50% exact accuracy over 32 controlled regimes, and an object centred on a patch intersection is a named worst case (image patches in the encoder), which matters for small symbols; code promised, no link found. Both use synthetic shapes, not drawings; neither gives an exact-match rate on real images.
  Exact-match benchmarks on real photos (verified text): CountQA (arXiv 2508.06585, 1,500+ questions on cluttered,
  dense photos) has the best of 15 MLLMs at 42.9% exact match (Gemini 2.5 Pro; next 34.42%), falling as counts rise;
  HoloCount (arXiv 2607.06420, 2026-07, 2,480 questions, 20 subsets) also scores exact match for 20+ MLLMs and
  reports a drop from perception to reasoning tasks. Numbers for frontier models on floor plans (AECV-Bench) are L7.
- **Training-free exemplar counting on DINO features (CountingDINO, WACV 2026, arXiv 2504.16570, verified full text).**
  Object role: the plan's own exemplar box becomes a convolution kernel over self-supervised DINOv2 features, giving
  a similarity map; a normalisation forces the exemplar regions themselves to sum to exactly one object each (a
  built-in answer to the self-similarity trap above); recursive quadrant partition raises feature resolution for
  small objects. FSC-147 test MAE 20.93 but RMSE 71.37 (below most trained text counters in the AdaCount table).
  Exemplar count matters: the same method has FSC-147 test MAE 20.93 with 3 exemplars and 37.73 with 1 (RMSE 71.37
  against 131.71; table of OCCAM, arXiv 2601.13871, verified), so one confident box per plan is not enough.
  Why it fits: nothing is trained on CubiCasa-like data, so no leak, and the quadrant partition is the exact lever
  for 5-20 px symbols. Breaks: the repo has no licence file (so code reuse is not allowed until the authors add
  one; re-implementing from the paper is possible); DINO features were learned on photos; thin black lines on white
  give low-texture patches; the method needs exemplar boxes of single cells.
- **Aerial wildlife counts (Salvin's albatross, arXiv 2505.10737, 2025-05, verified full text).** Object role: a bird
  on rock is a small repeated symbol on a cluttered background; the paper's leave-one-island-out protocol (fine-tune
  on seven islands, test on the eighth) is a style-shift test of a fixed fine-tuned detector. Result: fine-tuning with
  stronger augmentation beat the zero-shot pre-trained detector on most islands, but one island got worse (more
  false positives), and on average 29.25% of detections were false positives and 19.3% of birds were missed, so counts are
  not exact; sliced inference (SAHI) helped the zero-shot model a lot, with a double-counting warning for
  overlapping tiles. Reading for us: a fixed detector fine-tuned on in-domain boxes is the baseline an exemplar
  counter has to beat, and it still needs tiling hygiene (merge overlaps) and a human check; no exemplar counter
  was compared.
- **Stacked-object industrial counting (arXiv 2603.15470, abstract and full text opened).** 3D occupancy of bins; the shape
  (hidden objects) is not ours. Skip.

## 4. Looked for and did not find

- An exact-match or off-by-one rate on 2-15 objects for any class-agnostic counter (only CountBench-style accuracy
  for SAM 3, MAE for the rest).
- Any evaluation of CountGD, GeCo, DAVE or SAM 3 on floor plans, blueprints or engineering drawings (two searches,
  plus the SAM 3 citation list of 500 papers filtered by title).
- A Poisson-binomial or count-distribution layer on top of an object detector (found only on segmentation). A third attempt through the arXiv API with the terms "exact count" + detection, "count accuracy" + "exactly correct" and calibrated + object count + distribution returned only unrelated combinatorics and anomaly-detection papers.
- A DETR-style count loss that improves exactness (DQ-DETR is a coarse range classifier).
- Per-plan exemplar counting compared with a fixed fine-tuned detector under style shift (second attempt with other
  words, plus the wildlife leave-one-island-out paper, which tests a fixed detector under shift but no exemplar counter).
- A detector-based count error (MAE or exact) on floor plans: a second search with Mask R-CNN, YOLO and DETR terms
  found only AECV-Bench for multimodal models (arXiv 2601.04819, abstract read 2026-11-14, HTML version not available: 120 floor plans, per-field exact-match accuracy and MAPE for doors, windows, bedrooms and toilets; door and window counting "often 0.40-0.55" accuracy; L7 owns it. This is the one exact-match counting number on floor plans I found, for multimodal LLMs only, not for detectors or exemplar counters), ArchNetv2
  (detection mAP 93.5% per the snippet, not counting) and facade-floor counting (not plans).
- Exact per-image counts in pharmacy (pill) and electronics (PCB, screws) counting: two searches each found vendor
  claims (99.5-99.99% for mechanical counters, no method or data) and YOLO pill-counting papers behind sites that
  refuse fetches (ResearchGate) or with the wrong arXiv id in the snippet (2503.20516 is a small-object survey, L2);
  no peer-reviewed exact-match number was read. Not counted as a source.
- A documented recipe to fine-tune CountGD, GeCo or GeCo2 on our own boxes (CountGD++ does ship a training code archive and mosaic data on Google Drive, round 9, but no recipe or GPU need for a custom set): issues CountGD #40 and #52, GeCo #16 ask
  for it; in #40 the author answers they "will work on" instructions (verified); the CoLSR paper did fine-tune
  CountGD on its own data, so it works, but without a published recipe. (DAVE issues read later via the issues API: #12 asks how to train on own data, #6 CUDA out of memory, #11 training memory leak, #22 loss and mAP barely change in detection training; all open, no recipe.)
- A weights licence for GeCo2, CountGD, DAVE or LOCA (code MIT, weights silent); SAM 3 card unreadable without login.

## 5. Open questions and missing tools

- Open: does CountGD++ with 3 pseudo-exemplars reproduce plan-level exact counts on 40 dev plans? It is a one-hour
  test. Needs dev plans only, no eval data.
- Open: GeCo2 weights licence. The author says in issue #5 that GeCo2 is MIT with SAM2 parts Apache 2.0; they do not say separately whether the weights are covered. Ask them or avoid.
- Open for the orchestrator: is "SAM License" acceptable for shipped code (record 0006 does not list it)? Local
  second counter only is safe either way.
- For L7 / L2: MolmoE and Qwen3-VL point-then-count results, RF-DETR/D-FINE 12 GB memory. Not read here.
- Missing tools: no arXiv MCP (used arxiv.org/html through pwfetch and web-fetch); Semantic Scholar rate-limited three times
  (429; worked on other sources, then retried, and fell back to arXiv search pages); HF `facebook/sam3` card gated; the T&F paper on few-shot symbol detection in
  engineering drawings, the SAM3Count PDF and the PMC page of the industrial review were blocked (403 / empty; the
  review came through Europe PMC's XML instead), so those are search-record or
  abstract-level only.

## 6. One-hour test I would run (not run: this worker is read-only)

For whoever owns stage 8. Dev plans only, never the sealed eval.

1. Take 40 dev plans that have box labels. For each class (window, door, toilet, sink) take the detector's boxes
   with score above a high bar and keep 3 by feature consensus (the three boxes whose embeddings are closest to the
   others', the CountZES idea), not the three highest scores.
2. Run CountGD++ `count()` with the class word plus those 3 exemplar boxes (cropped from the same plan and passed as
   `exemplar_boxes`), once on the plan at its own size and once on a 2x Lanczos upscale. Re-tune `conf_thresh` per
   class on 20 of the 40 plans; score the other 20.
3. Report exact-match per class and the share of plans where the detector and CountGD++ disagree, then the exact-match
   among agreeing plans. Stage 8 is worth keeping only if "agree" plans are clearly more exact than "disagree" plans
   (a trust signal), whatever the standalone exact rate.
4. Kill criteria: standalone exact rate below the detector's on windows and doors, or agreement not predicting
   correctness (for example, 95% right when agreeing and 90% when not).
5. For the Poisson-binomial layer, the distribution is a short dynamic programme over the detector's per-box
   probabilities (`dist[k]` updated per box with `p`: new[k] = dist[k] * (1-p) + dist[k-1] * p); calibrate the scores
   per class (temperature or isotonic) on the dev slice before using it, and report the reliability of
   P(count = predicted) in 5 bins.

## 7. How this extends the earlier measurements (context sections 2 and 3)

| Earlier finding | What the sources above add |
|---|---|
| Count-only FCN: 59.3% overall, windows and doors 18%; "needs box or point supervision" | Nothing contradicts it. Fine-tuned counters on 7-49 objects still miss by about one (CoLSR 0.88 MAE best, CountGD 7.84, DQ-DETR 4.24, arXiv 2602.11024). The multi-class density paper (2510.02213) works on 10-50 px vehicles, not 5-20 px line symbols. |
| Class-agnostic counters (CountGD 5.74, DAVE 8.66, LOCA 10.79, GeCo 7.91) report mean error only | Newer: GeCo2 7.64 (AAAI 2026), CountGD++ text-only 16.55 / with pseudo-exemplars 10.29 on FSCD-147. The low-count regime is only covered by CountBench (2-10 objects): SAM 3 accuracy 93.8%, CountGD MAE 0.86. FSC-147 itself starts at 7 objects (average 56). |
| Weights licences "unstated" for CountGD, DAVE, GeCo, LOCA | CountGD++ weights: MIT (HF card). GeCo2: still unstated. SAM 3 and DINOv3: custom Meta licences, gated. Code licences read from the LICENSE files: CountGD, CountGD++, DAVE, GeCo, GeCo2, LOCA, CounTR, SAM3Count MIT. |
| CounTR, PseCo, T-Rex2, P2PNet "not opened" | Licences now read: CounTR MIT; PseCo no licence file (gh api 404); T-Rex2 IDEA License 1.0 (non-commercial research); P2PNet academic research only; PET MIT file but README says academic only. |
| Small VLMs: Qwen2.5-VL-3B research licence; Moondream 2 and MolmoE Apache | Added: Molmo2-4B Apache-2.0 (HF, 2026-01, 4.85B parameters), Qwen3-VL-4B Apache-2.0, Moondream 3 preview BSL 1.1. Counting numbers for them belong to L7. |
| "Not found before": count calibration, point-supervised methods, per-plan exemplar counting, audited-count fields | Calibration: Poisson-binomial found, medical only. Point supervision: P2PNet and PET unusable by licence. Per-plan exemplars: CountGD++ pseudo-exemplars, CountZES, CountSE (natural photos only). Audited fields (surgical counts, colonies, lesions) reach MAE 0.88, 9.64% and 87-88% accuracy: none reaches exact counts, which supports keeping box evidence and abstention. |


## Round 3: repo issues (read 2026-11-14)
- CountGD issues: no fine-tune recipe (open #40, #42, #52, #56 ask for one, none answered). False positives: the maintainer says to raise the confidence threshold (#41). Count varies across near-identical video frames in dense scenes (#35). High RMSE on FSC-147 reproduction (#49). Nothing about drawings or small objects. Effect for us: these issues are about CountGD, not CountGD++. CountGD++ does ship training code (see round 9), so this line is corrected there.
- GeCo2 issues: training code released later (#10, #11 closed); open reproduction issues (#4, #12); CPU not supported (#17). Licence: see section 5.
- HF nikigoli/CountGDPlusPlus: no discussions.

## Round 4: CountGD++ training cost (read 2026-11-14)
The paper (arxiv.org/html/2512.23351) states CountGD++ is trained on FSC-147 plus 1000 synthetic mosaic images, with hyperparameters taken from CountGD-Box and no further tuning, and no fine-tuning on any evaluation dataset. A search for GPU, hours, epochs and LoRA in the main text found no training-cost figure. So a 12 GB fine-tune cost cannot be estimated from the paper; it stays an open question (CountGD++ has a training code archive, see round 9, but no stated GPU need).

## Round 5: forward citations of CountGD++ (Semantic Scholar, read 2026-11-14)
CountGD++ is cited by 16 papers, all 2025-2026. Already read in this report: AdaCount, CountZES, Count Anything, the counting survey, RECOUNT (read in full in round 7). New, abstract only: Count Anything at Any Granularity (2605.10887, HieraCount model plus KubriCount synthetic data; finds that specialist counters and multimodal LLMs both fail to follow fine-grained prompts, which matches our "count windows, not doors" need but it is trained on rendered 3D scenes, not drawings; licence and weights not checked). Not opened: MixCount (2605.18063), ABACUS (2606.23835), CoDi (2512.20153). CountingDINO forward walk hit a 429 and is not done.
Round 5 addendum (abstracts only): MixCount (2605.18063, synthetic mixed-object counting data and benchmark, co-authored by the CountGD author; says state-of-the-art counters fail systematically on mixed objects, which is our case of windows among doors and fixtures; trained on synthetic photos, no drawings, data and licence not checked). ABACUS (2606.23835, 3B unified model, GRPO-trained, SIGGRAPH Asia 2026; too large for a 12 GB dev box without quantisation and counts photos; skip). No Hugging Face models found under the names HieraCount or KubriCount (searched 2026-11-14), so HieraCount weights are not public as far as found.

## Round 6: UNICBench (abstract, read 2026-11-14)
UNICBench (arXiv 2603.00595, CVPR 2026) is a counting benchmark for multimodal LLMs over images, documents and audio, 45 models, with stratified reporting and "hardest partitions" where models fail. It is a measurement protocol (fixed splits, deterministic numeric parsing, modality-specific matching) rather than a method, so it only helps us as a template for scoring exact counts. Not checked: whether it reports exact-match, or has any drawing or document-layout images. CountScope (listed in awesome-object-counting) was not found on arXiv by title search; left unread.

## Round 7: RECOUNT full text (arxiv.org/html/2608.20621, read 2026-11-14)
RECOUNT (Aug 2026, Simon Fraser University) turns one off-scene reference image into synthetic visual exemplars with a diffusion model, then filters the point proposals of a frozen CountGD to accept the target class and reject look-alikes. Training: a residual projection head of about 1.2M parameters, one epoch on one H100 (so the head training itself is light, but the diffusion step to build exemplars is the cost and the paper gives no GPU-memory figure that I found). Evaluated on PairTally and LookAlikes (photos), with MAE and RMSE only. Fit for us: the idea (one stock symbol image → accept/reject filter over CountGD proposals) matches the exemplar route already in rank 1, but needs a diffusion stage and the code was not found in the paper text (no repo link, no licence); do not plan on it. Adds nothing to rank order.

## Round 8: CountEx full text (arxiv.org/html/2602.19432, read 2026-11-14)
CountEx (Feb 2026, Stony Brook and AIML Adelaide) adds an explicit "count X, not Y" exclusion prompt (text plus optional exemplar boxes) with a Discriminative Query Refinement module, trained on a new CoCount dataset. On CoCount it beats CountGD, CAD-GD, GroundingREC and LLMDet (known-category MAE 12.72 versus CountGD's best baseline value in the paper); on LookAlikes and PairTally it also leads. All photos, MAE/RMSE/NAE only, no exact-match. Fit for us: the exclusion idea (count windows, not doors) is the same as CountGD++'s negative prompts in rank 1, which the repo already supports; CountEx would need its own training on CoCount and I found no code link or licence in the paper text. Not a candidate; rank order unchanged. UpCount: found later, see round 27.

## Round 9: CountGD++ repo (gh api and README, read 2026-11-14)
- Licence MIT (API), last push 2026-10-27. Requirements: torch below 2.6 (cu121 index), transformers, gradio below 5, pydantic 2.10.6, deeplake below 4, timm, plus a bundled gradio_image_prompter wheel. No AGPL or GPL package in the list (ultralytics and similar absent). CountGD (the older repo) pins torch 2.2.1 and transformers 4.39.1, also no AGPL or GPL. GeCo2 install.sh pins torch 2.7.1 and compiles Deformable-DETR CUDA ops, so it needs a matching CUDA toolchain and Python 3.10.
- Weights: Google Drive file of 1.25 GB (README) and the HF card; the training code is a separate Google Drive archive, not in the git tree (README "Training CountGD++"); mosaic images are another Drive download. So training code exists for CountGD++, which corrects my round 3 remark (that was about CountGD).
- Large scans: the repo has `infer_sahi.py` (issue #8, closed): slices the image into overlapping tiles (default 1024 px, overlap 200 px), runs CountGD++ per tile, maps boxes back. Built for drone and satellite images where objects are too small at the 800 px model input. This is the direct answer to "small symbols on a large plan" and is the thing to try first on dense sheets; tiling can double-count objects on tile borders unless the script's merge step handles it (not checked).
- Issues: 9 total, none on drawings, memory, or training time.

## Round 10: PET full text (ar5iv.labs.arxiv.org/html/2308.13814, read 2026-11-14)
The arXiv PDF URL would not load; the ar5iv HTML did. PET (point query transformer, ICCV 2023) reports MAE 49.34 on ShanghaiTech A, 6.19 on B, 79.53 on UCF-QNRF; MAE and MSE only, people in crowds of tens to thousands, no exact-match. It also outputs point locations, which is the form a count-by-points route on plans would need, but the README restriction to academic use keeps the verdict at skip.

## Round 11: adjacent field, human correction of counts (searched and read 2026-11-14)
Scope asks how audited fields get from "about right" to exact with human correction of a few marks. Four arXiv API searches (human-in-the-loop, interactive counting, user feedback with exemplars, human verify) found no object-counting method built around a person fixing a few marks, and no exact-match report for one. The only hit worth reading is a 2019 cell-counting paper (arXiv 1901.04355, ICMLA 2018, abstract read): a user verifies each predicted mask, verified masks are added to the training set, and over 5 rounds the stereology count error fell from about 3% to under 1%. That is relative error on cells, not exact match, and it is old, but it is the one documented loop of "model proposes, person verifies, model retrains". For us it means the supervisor-verified-count route has precedent in microscopy only; no number for drawings. Retail and traffic counting were not searched beyond this.

## Round 12: Poisson-binomial paper re-read (ar5iv.labs.arxiv.org/html/2204.05276, 2026-11-14)
Count accuracy 87.6 (F1 67.3) for the post hoc model and 88.7 for the multi-task variant: matches the table row. Correction: the paper does point to code (footnote 1, "see code for details") but the footnote URL is not in the fetched text, so my earlier "no code found" is now "code exists per the paper, URL not found". It does not change the rank: the layer is about 30 lines and does not need their code. The arXiv PDF URL failed to load; ar5iv worked.

## Round 17: QICA and WS-COC full text (arxiv.org/html/2603.16129, 2602.12774, read 2026-11-14)
QICA: FSC-147 test MAE 12.41 / RMSE 97.28 (ViT-L/14), CARPK MAE 6.07 zero-shot, 18.5-19.7M trainable parameters, evaluated on A800 80 GB GPUs; the quantity loss lowers FSC-147 MAE from 16.15 (plain CLIP fine-tune) to 12.41 in its ablation. WS-COC: trained on one NVIDIA L20 GPU with batch size 4, range-judging dialogue instead of regressing a count; MAE only. Neither gives exact match and neither fits our box budget evidence (A800 80 GB). My verdict (skip) stands.

## Round 19: gap re-search, per-plan exemplar vs fixed detector (arXiv API, 2026-11-14)
Three more queries (few-shot detection cross-domain with counting and exemplars; floor plan counting symbols; engineering drawing symbol few-shot detection) returned only AECV-Bench. Still no study that compares per-plan exemplar counting with a fixed fine-tuned detector under style shift.

## Round 21: Hugging Face file lists (HF API, 2026-11-14)
- GeCo2 weights repo (dataset `jerpelhan/geco2-assets`): no card data and no licence tag, so the weights licence stays unstated. It holds two checkpoints (an FSCD one and a multi-train one) and ready-built wheels for the deformable attention op (CPython 3.10, Linux x86-64), so the CUDA compile step in install.sh can be skipped on a matching box.
- CountGD++ (`nikigoli/CountGDPlusPlus`): licence tag MIT, a `model.safetensors`, a LICENSE file, `countgdpp.py`, `example.py`, `test_all_prompts.py` and its own requirements.txt, so weights and inference code come from one place without Google Drive. This matches the existing 1 to 2 hour estimate for rank 1 (it already assumed snapshot_download); I did not run it.

Round 21 addendum (HF card read, 2026-11-14): the `count()` call shown on the card is the whole inference path: `count(model, image_path, "strawberry", negative_texts=["blueberry"])` returns `count` and normalised boxes. Install is one `pip install` line (transformers below 4.50, timm, no custom CUDA build). The compiled deformable-attention kernels are optional: without them a pure-PyTorch version runs on CPU or GPU, so a first number does not depend on a CUDA toolchain. Two limits from the card: pseudo-exemplars and adaptive cropping (the settings behind the best paper numbers) are not part of `count()`, only of the GitHub test scripts; and the BERT text encoder is fetched from the Hub on first load, so an offline box needs it cached.

## Round 24: licences of what CountGD++ is built on (gh api and HF API, 2026-11-14)
Grounding DINO repo and HF base model: Apache-2.0; Swin Transformer repo: MIT; bert-base-uncased: Apache-2.0. So CountGD++'s MIT code and MIT weights sit on permissive parents; I found no AGPL, GPL or non-commercial parent. Not checked: the licences of the datasets those parents were pretrained on, and the FSC-147 dataset terms: the FSC-147 repo (cvlab-stonybrook/LearningToCountEverything) carries an MIT code licence (gh api) and its README states no data terms (grep for licence, terms, copyright, research, Flickr found nothing), so the image terms stay unknown.

## Round 25: SAM 3 repo (gh api and model_builder.py at commit c97c893, read 2026-11-14)
- Licence per API: "Other" (custom SAM License), no SPDX id.
- The image detector's decoder is built with 200 object queries and an input resolution of 1008 (model_builder.py), so one image can return at most 200 instances; for a dense sheet of small symbols that is a ceiling, and an issue (#460, open) asks how to fine-tune on images with many small same-class masks and gets the answer that the fixed number of detector queries is the limit. For our 2-15 objects per plan the cap does not bind; for a whole-sheet count of every fixture it could.
- Issue #505 (open): a user asks how the CountBench numbers were computed (noun extraction, script, post-processing) and the evaluation script is not published, so the 93.8% in the paper cannot be reproduced from the repo.
- Memory: issue #511 (closed) reports a CUDA OOM on a 24 GB card for the SAM 3.1 video predictor; this is video tracking, not image counting, so it does not change the 5-6.5 GB image figure from the Count Anything paper.

Round 25 addendum (CountGD++ cfg_app.py, read 2026-11-14): 900 queries, `num_select` 900, `nms_iou_threshold = -1` (no NMS) and `box_threshold = 0.23`, text threshold 0. So CountGD++ returns up to 900 boxes and has no cap problem on dense sheets, but with NMS switched off, adjacent identical objects are only separated by the model's own scores; the one tunable that sets the count is the 0.23 threshold, which makes the Poisson-binomial layer (rank 3) easy to attach (sum over the per-box scores, which the model already produces).

Round 25 correction (countgdpp.py read 2026-11-14): `count()` takes `conf_thresh` (default the paper's 0.23), also external `exemplar_image` and per-negative exemplar boxes or images, and returns `count`, `boxes` and `scores` (the maximum token score per box), so the per-box scores for a count-distribution layer are available without touching the model. The signature also drops boxes that the negative prompt claims (negative logits are compared per box); I read the signature and the final return, not the full suppression rule.

## Round 27: forward citations of CountingDINO (Semantic Scholar worked on retry, 2026-11-14)
8 citing papers (2025-2026). New and read: UpCount, "Spatially-Aware Class-Agnostic Object Counting" (arXiv 2607.16826, full text): reference-free (no exemplar, no text), ViT-B/16 MAE-pretrained encoder with multi-scale pyramid, outputs a density map and a count, FSC-147 test MAE 12.39 / RMSE 100.89, CARPK 6.27 / 8.79, code at a personal GitHub repo (MIT by gh api). A density map gives no boxes and no per-object score, so it cannot fill an evidence field; skip. Also cited, abstracts read: a 2025 class-agnostic counting survey (2501.19184, CVIU; taxonomy reference-based, reference-less, text-guided; nothing on drawings or exact match) and an agentic perception paper (EviRover, 2609.40230, a 4B general perception agent, off scope); the industrial counting review was already read as XML. This fills the earlier "UpCount not found" gap: it was filed under a different title.

## Round 29: forward citations of the Poisson-binomial paper (Semantic Scholar, 2026-11-14)
Only 3 papers cite it (2022-2025): a 2025 multiple-sclerosis MRI overview and a 2024 stroke segmentation ensemble; neither uses the count distribution for counting objects. So the layer is unadopted outside lesion counting, which is consistent with "found only on segmentation" in section 4: nobody has published it on top of a box detector, and we would be the first to test it there.

## Round 30: closest count-distribution neighbour for detectors (WebSearch, then paper opened 2026-11-14)
A web search for a calibrated count distribution over detector scores found no paper doing it (confirms section 4). The nearest is Riedlinger, Maag and Gottschalk (ICLR 2026, arXiv 2506.21486, abstract and method opened): bounding boxes as a conditional marked point process, with the expected number of centres used in place of NMS and a probability that an area is empty. It is a new detector trained from scratch for driving scenes, not a layer over an existing counter, so it does not replace rank 3; it shows the same idea (count as a random variable) is current. Verified: abstract and method text; not verified: any exact-count numbers.

## Verification status at close (2026-11-14)
Verified by reading full text or repo files: CountGD, CountGD++, GeCo2, SAM 3, DAVE, SNAP, PET, OCCAM, RECOUNT, CountEx, UpCount, QICA, WS-COC, VLMCountBench, Counting to Four, AgentCount, stacked-object paper, Poisson-binomial paper, plus the repos, issue lists, HF cards and licence files named in rounds 3, 9, 21, 24, 25. Abstract only: Count Anything at Any Granularity, MixCount, ABACUS, UNICBench, AECV-Bench, the 2019 stereology paper, the CAC survey, EviRover, the ICLR marked-point-process paper (method opened, no numbers). Unverified or not done: SAM3Count paper PDF (README table read instead), SAM 3 model card (gated), GeCo2 weights licence, FSC-147 image terms, UpCount-style repos beyond the licence, any run on our plans (read-only worker).
