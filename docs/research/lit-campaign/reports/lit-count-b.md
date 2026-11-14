# lit-count-b: sideways transfers for exact counting (scope L3, angle b)

Worker lit-count-b, 2026-11-14. Read-only. Every source below was opened by me or by a web-fetch call I made;
date read is 2026-11-14 for all. Marks: **V** = I read it on the page (verbatim); **S** = the fetch tool returned a
model summary of that part of the page, so the number needs a check against the PDF; **R** = the authors' own claim.
Source log with one line per page: `lit-count-b-log.md`. Earlier reports extended, not repeated: `lit-counting.md`,
`lit-vlm.md`, `01-vlm-drawing-qa.md`, `stoa-cubi.md` (CountGD/DAVE/GeCo/LOCA MAE and licences are in them).

## 0. What the sideways reading says in six lines

1. Nobody in an adjacent field reports exact-match on 5 to 20 px symbols. (The one adjacent exact-match rate on small
   clusters: MCount, PLOS One 2025, colony segments, zero error on 91.45% of 15,847 segments, V, below.) The only exact-match numbers I found are on
   natural photos with 2 to 10 objects: SAM 3 **94.0%** (CountBench, 487 images) and **86.3%** (PixMo-Count, 529
   images) with one fixed recipe (score > 0.5, then IoM-NMS at 0.5; V, SAM 3 appendix F.4, Table 37). Without the IoM
   step the same model gets 84.8% and 76.9% (V). The dedupe rule is worth 9 to 10 points of exact match.
2. For "two confident windows from this plan, find the rest" there is no result on drawings. The closest evidence is
   AdaCount (arXiv 2607.02139, V): SAM 3's own confident detections become per-image prototypes and a second SAM 3
   pass runs on an image warped toward them. It beats plain SAM 3 on every benchmark in its tables: FSC-147 MAE
   22.89 to 18.97, CARPK 3.52 to 1.99, nuclei set MBM 23.25 to 19.11 (V, Tables 1 to 5). It gains most where objects
   are small and dense, and it fails when the first pass finds nothing (V, limitations section: crab cakes and finger foods on FSC-147). Against a fine-tuned fixed detector, no
   paper compares. Other numbers pull the other way: exemplar-prompted SAM 3 fails on texture-less industrial parts
   (F1 0.156 / 0.189 / 0.507 on three sets; V, 2602.20551), and a window cell is texture-less. We have to measure it
   (section 4, experiment 1). The only floor-plan exact-count baseline is AECV-Bench (2601.04819, V): prompted VLMs
   reach at best 0.39 exact match on doors and 0.34 on windows per plan (section 6).
2b. Exact match of density-style counters is near zero, so the field's headline MAE hides it. The one paper that
   scores exact match for specialised counters (arXiv 2512.15254, V, Table 1, exact-match accuracy): on FSC-147
   T2ICount 0.38, TFOC 0.14, PseCo 0.01; on the synthetic SolidCount (8 to 40 objects per image, objects 3 to 15% of
   image height) all three score 0.03 to 0.06, while Gemini 2.5 Pro scores 0.80 and Claude 4.5 Sonnet 0.61. CountGD,
   DAVE, GeCo and SAM 3 were not in that comparison. Read with SAM 3's 94.0% (detection-style, 2 to 10 objects):
   detection-style counters with a dedupe rule can be exact on small counts, density-style ones are not.
3. Count calibration exists in medicine and nowhere else I could find: Poisson-binomial over region probabilities,
   count accuracy about 90% on counts 0 to 4+, ECE 0.72e-5 (V, Schroeter 2204.05276). It is 20 lines of code and uses
   the scores our detector already has.
4. The field that audits counts to the single object (colony counting, crowd localisation, wildlife) gets there with
   point output, a validation pass that flags crowded or edge objects, and a person who looks at flagged images
   (V, AgentCount 2611.05398; HerdNet README). None of them published an exact-match rate either.
5. Licence trap: SAM 3 code and weights are under the custom "SAM License" (Meta, 19 Nov 2025), not on the record-0006
   list. P2PNet is "academic research only". HerdNet weights are CC BY-NC-SA. CountGD++ code and HF card are MIT.
6. Leakage: no checkpoint below is known to be trained on CubiCasa5K. SAM 3's external training list (V, Table 25 of
   the full text, read through the headless browser) names Objects365, OpenImages, ImageNet, VisualGenome, Fashionpedia,
   Fathomnet, iNaturalist, BDD100k, LiveCell, PanNuke, MedSAM2, SNOW, VisDrone, WCS camera traps, HierText, FSC-147
   and others: no floor-plan set. Its web image pools (MetaCLIP, SA-1B) cannot be checked. Flag: "no named floor-plan
   data", not a guarantee. FSC-147 is in its training mix, so FSC-147 numbers for SAM 3 are not zero-shot.

## 1. Top 5 (floor-plan work and transfers in one list)

| # | Method | From | Verdict | One reason | Source (read) |
|---|---|---|---|---|---|
| 1 | **SAM 3, boxes of a fixed detector as exemplars or fine-tuned as the detector, with the SAM 3 counting recipe (score threshold + IoM-NMS)** | adjacent: open-vocabulary counting and microscopy/colony pipelines | **try** (licence decision first) | Only model with a published exact-match number for counts 2 to 10 (94.0%), same-image exemplar prompts, interactive correction (+21.6 cgF1 after 3 exemplars), fine-tuning code in the repo, and a 12 GB colony-counting pipeline already built on it | arxiv.org/abs/2511.16719 + full text via headless browser; github.com/facebookresearch/sam3; arxiv.org/html/2611.05398 |
| 2 | **Count distribution from detector scores: Poisson-binomial over calibrated instance probabilities, predicted count = mode, abstain when the mode has low mass** | adjacent: medical lesion counting | **try** (own code, no dependency) | Gives the confidence and abstain signal for stage 8 and turns a score ranking into exact-count decisions; 88 to 90% count accuracy, ECE 0.72e-5 (V) | arxiv.org/abs/2204.05276 + html |
| 3 | **Per-plan self-bootstrapped exemplars: first pass detections become exemplars for a second pass (AdaCount recipe on SAM 3; CountGD++ pseudo-exemplars + negative exemplars) as the independent SecondCounter** | adjacent: open-world counting, cells, aerial | **maybe** | The only published "find the rest from what this image already shows": AdaCount gains 17 to 43% MAE over plain SAM 3 on photos, cells and cars (V); negative exemplars match our rules (shower tray vs screen, door with leaf vs bare opening); CountGD++ code and HF card MIT; no result on drawings or on 5 to 20 px symbols | arxiv.org/abs/2607.02139 + html; arxiv.org/abs/2512.23351 + html; github.com/niki-amini-naieni/CountGDPlusPlus; huggingface.co/nikigoli/CountGDPlusPlus |
| 4 | **Count-as-classification head with integer bins `{0},{1},...,[m,inf)` and a Wasserstein count loss (CLIP-EBC "EBC")** | adjacent: crowd counting | **maybe** | Cuts MAE 140.6 to 77.9 on UCF-QNRF over real-valued bins (V, ablation, VGG16), MIT code; fits our "tile or per-plan count 0 to 20" because it never regresses a fraction | arxiv.org/abs/2403.09281; github.com/Yiming-M/CLIP-EBC |
| 5 | **Human-in-the-loop correction: show the marks, user fixes a region with a count range (ICACount) or adds a positive/negative exemplar box (SAM 3)** | adjacent: interactive counting, colony counting | **maybe** (product, not score) | 30 to 40% MAE reduction in 5 two-click rounds (V, FamNet/SAFECount/BMNet+ on FSC-147 and LVIS); "check the marks" is the user story in this campaign's brief | arxiv.org/abs/2309.05277 + html; SAM 3 section 5 (Figure 7) |

Floor-plan work I ranked below these: none. No floor-plan paper has an exact-count result with usable code
(`stoa-cubi.md`); the floor-plan fields belong to the other orchestrator's scopes.

## 2. Full table

Columns: field the method comes from; year/venue; code URL + licence; weights + licence; training data; metric and
benchmark (input size); GPU memory; JSON field; leakage flag; verdict. "First number" hours are my estimates.

| Method | Field | Year / venue | Code (licence, read from) | Weights (licence) | Training data | Metric (benchmark, input) | GPU / hours to first number (estimate) | Fills | CubiCasa leakage | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| SAM 3 | open-vocab counting; cell and colony tools | Nov 2025, ICLR 2026 (V: proceedings link in search) | github.com/facebookresearch/sam3, **SAM License** (custom; `gh api` spdx NOASSERTION; text read: royalty-free, derivative works allowed, redistribution under same licence, publish-acknowledgement, no reverse engineering, trade controls) | HF facebook/sam3 gated; the page header reads "License: other" (V, headless browser); card text hidden behind the access form | SA-Co: HQ 5.2M images, SYN, 18 external sets (V; names not in the text read), VIDEO | CountBench exact 94.0%, MAE 0.11 (487 img, 2 to 10 objects); PixMo-Count 86.3%, MAE 0.21 (529 img) (V, Table 37); 1008 px | ~848M params; 5.2 to 6.5 GB inference bf16 (S, Count Anything); colony pipeline 33.5 s/img on 12 GB 3060 (V); fine-tune: repo has train extras, a user full fine-tune (840M trainable) used 4 A100, backbone frozen 32.7M trainable (V, issue #324); 3 to 5 h to a zero-shot number, 6 to 10 h fine-tuned | elements (boxes), plans | no named floor-plan data in its external list (V); web pools unknowable | try, after licence decision |
| CountGD++ | open-world counting | Dec 2025, CVPR 2026 | github.com/niki-amini-naieni/CountGDPlusPlus, **MIT** (gh api); HF card says `license: mit` (V) | 1.25 GB, Google Drive link in README; HF nikigoli/CountGDPlusPlus MIT; built on GroundingDINO Swin-B + SAM ViT-H weights (both downloaded separately, licences not read here) | FSC-147 train (V) | FSCD-147 test text-only MAE 16.55, +pseudo 10.29, +synthetic 8.39 (V, Table 1, full text read via headless browser); blood cells (100 images) MAE 11.56 with positive prompts only, 1.73 / 1.52 with negative text + exemplars (V, Table 2); no exact-match, no low-count range | not stated; 2 to 3 h to a zero-shot number | elements, second count | no evidence; not verified | maybe |
| Poisson-binomial count head | medical imaging | MIDL 2022 | github.com/SchroeterJulien/MIDL-2022-Segmentation-Consistent-Lesion-Counting, **no licence file** (`gh api` 404); idea is a 20-line recursion | none | lesion MRI; needs no count labels (post hoc) | count accuracy ~88 to 90, ECE 0.72e-5, MCE 0.077 (V, Table 1, column alignment reconstructed) | CPU; 1 h | counts[].confidence, abstain | n/a | try |
| CLIP-EBC (EBC) | crowd counting | ICME 2025 (arXiv v3 Mar 2025) | github.com/Yiming-M/CLIP-EBC, **MIT**; repo archived 2026-10-22 | release page weights, no weights licence stated | ShanghaiTech, UCF-QNRF, NWPU | UCF-QNRF MAE 77.9 with integer bins + DACE vs 140.6 standard blockwise classification (VGG16; V); NWPU test 58.2 MAE (V); 224 or 448 px crops | not stated; 3 h | elements counts per tile | no (crowd data, CLIP) | maybe |
| ICACount (interactive correction) | interactive counting | ICCV 2023 | page not found in text read | none | adapts a pretrained counter at test time | MAE 22.08 to 11.75 (FamNet, FSC-147), 5 rounds (V, Table) | CPU/GPU; 2 h for a mock | UI, not JSON | n/a | maybe |
| Count Anything | multi-domain text counting | May 2026 (arXiv) | github.com/Mengqi-Lei/count-anything, **Apache-2.0** (gh api) | SAM 3 weights frozen, so SAM License applies to derivatives | CLOC, 220K images, 619 categories (V) | CLOC MAE 9.34 vs SAM 3 25.80 (V, Table 1); cellular microscopy MAE 38.65, agriculture 41.78, microbiology 4.30 (V); 1008 px | 848.62M params, 68 to 122 ms, 5.17 to 6.53 GB inference BF16 (V, Table 7); trained 30 epochs on 8 A100, batch 24 per GPU, LoRA rank 8 on the cross-modal encoder (V) | elements | no evidence | skip as a model, keep the recipe: LoRA rank 8 on a frozen SAM 3 encoder plus point loss, ablation shows point and box losses together 9.34 vs 13.83/14.06 alone (V, Table 8) |
| AdaCount | training-free counting on SAM 3 | Jul 2026 (arXiv, technical report) | project page only (code URL and licence not stated; paper CC BY-NC-SA 4.0) | uses SAM 3 | none | FSC-147 MAE 18.97 vs SAM 3 22.89; CARPK 1.99 vs 3.52; MBM 19.11 vs 23.25; 1008 px (V) | two SAM 3 passes, 750 ms vs 300 ms for plain SAM 3 on an RTX 5000 (V, Table 6) | elements | no evidence | maybe (recipe is simple: prototypes from first-pass masks, similarity map, pixel warp, feature gating) |
| CountZES | zero-shot counting | Dec 2025 (arXiv v4 Oct 2026) | github.com/Muhammad-Ibraheem-Siddiqui/CountZES, **PolyForm Noncommercial 1.0.0** (V, LICENSE file; paper CC BY-NC-SA) | GroundingDINO + CLIP + SAM + frozen CounTR/DSALVANet | none | CARPK MAE 7.24 inference-only; PerSense-D low/med/high 6.86/10.26/20.36 (V) | 2.3 s/img, RTX A5000 (V); authors flag noise under domain shift | elements | no evidence | skip (four models, worse than AdaCount on CARPK) |
| PerSense / PerSense++ | dense-image personalised segmentation | arXiv 2024; BMVC 2025 | github.com/Muhammad-Ibraheem-Siddiqui/PerSense, **PolyForm Noncommercial 1.0.0** (V, LICENSE file) | uses SAM, GroundingDINO, VIP-LLaVA, CounTR | none ("no training") | PerSense-D (717 images, mean 53 instances) mIoU 70.96 to 71.61 (PerSense) and 77.45 to 81.35 (PerSense++); count error of its density map MAE 15.07 to 12.91 and 16.17 to 11.48 (V, Table 4, later version than the v4 I first read) | RTX 4090, about 3 GB, 2.7 s (V) | elements | no | idea: split composite contours by distance transform; diversity-aware exemplar choice |
| OCCAM | prior-free multi-class counting | Jan 2026 (arXiv) | promised, URL unverified | SAM 2.1-L + ResNet-50 + FINCH clustering | none | CARPK MAE 10.06, FSC-147 multi-class MAE 16.92 (V) | not stated | elements, per-class counts | no | skip (counts classes by clustering; MAE worse than prompted methods) |
| LC-FCN | counting by localisation | 2018 (arXiv) | not stated | not stated | point labels only | Trancos MAE 3.32; split loss for touching blobs (V) | not stated | elements as blobs | no | idea only: train-time split loss so each blob holds one object, count = blobs |
| DM-Count | crowd counting | NeurIPS 2020 | github.com/cvlab-stonybrook/DM-Count **MIT** (gh api) | not stated | dot labels | UCF-QNRF MAE 85.6 (V) | 25 ms/img for the loss (V) | counts | no | skip (density, not exact; says Gaussian smoothing of dots hurts) |
| POLO | wildlife aerial counting | CV4Ecology @ ECCV 2024 | not stated; built on YOLOv8 (Ultralytics, ruled out by record 0006 as AGPL) | not stated | point labels only | per-image MAE only, 0.22 to 4.51 per class (V); authors say close animals are not separated (V) | not stated | elements | no | skip (AGPL stack, no exact count) |
| Cellpose-SAM | microscopy | bioRxiv Apr 2025 | github.com/MouseLand/cellpose **BSD-3** (LICENSE file; README badge says GPL v3, stale) | HF mouseland/cellpose-sam; README: "trained on data that is licensed under CC-BY-NC", weights licence not stated | 22,826 images, 3.3M masks | error rate 0.163 vs human 0.257, IoU 0.5; 256 px tiles, 305M-parameter encoder (V) | batch size 1 trains on 8 to 12 GB (V); 8 images and 100 epochs fine-tune (V) | elements as masks | no (NC data) | idea only: flow fields separate touching objects; masks, not boxes |
| HieraCount | open-vocab counting | May 2026 (arXiv) | not found in text read | not stated | KubriCount 110K synthetic | FSC-147 test MAE 10.29 (V, table), worse than CountGD++ 8.39 | not stated | elements | no | skip |
| RECOUNT | fine-grained counting | Aug 2026 (arXiv) | none stated | none stated | SynthAlikes | LookAlikes MAE 8.41, PairTally 39.96 (V, zero-shot row of its table) | not stated | elements | no | skip (idea: accept/reject each point against exemplar embeddings, which is a second-pass verifier) |
| AgentCount | colony counting | Nov 2026 (arXiv) | github.com/jlk666/AgentCount, **MIT** (gh api) | uses SAM 3 | 57 plates | MAE 4.3 colonies, 89.7% within 10% (V); no exact match | 33.5 s/img, RTX 3060 12 GB (V) | pipeline shape | n/a | idea only: validation agent flags overlapping boxes, edge objects, overgrowth; keep overlays and raw masks for audit |
| CountingDINO | training-free counting | WACV 2026 | project page; no licence file (`gh api` 404) | none (DINOv2 backbone) | none | FSC-147 test MAE 20.93; CARPK 21.26 (V) | not stated | elements | no | skip (MAE 3x worse than trained counters; says small objects need a 4x4 quadrant split) |
| GeCo (and GeCo2) | low-shot counting | NeurIPS 2024 | github.com/jerpelhan/GeCo **MIT** (sidebar); GeCo2 repo LICENSE file is MIT (V, read) though spdx says NOASSERTION | not stated | FSC-147 | dense detection loss vs Gaussian loss: MAE 9.52 vs 12.79, AP 33.5 vs 31.4 (S); input 1536 px if exemplar < 25 px | 2 A100 for training | elements | no | idea: train a box detector with a loss that matches peaks to boxes (not centre Gaussians) |
| HerdNet | wildlife aerial counting | ISPRS J. 2023 (open-access postprint read, 14 pages, CC BY-NC-ND paper) | github.com/Alexandre-Delplanque/HerdNet **MIT** (LICENSE.md read) | **CC BY-NC-SA 4.0**, ULiège hosting (README) | point labels, 512 px patches with 160 px overlap (widest animal 156 px), 24 MP images | Test, binary: HerdNet F1 73.6, MAE 6.1, RMSE 9.8, 3.6 s per 24 MP image; Faster R-CNN F1 47.4, MAE 15.2, RMSE 26.2; density DLA-34 MAE 15.9 (V, Table 3); no exact-match | trained on an 8 GB RTX 3070: 100 epochs, batch 4, Adam, then a second round with hard-negative patches mined from stitched predictions (V); 18M params (README) | elements, point output | no | idea: point-map head + local-maxima extraction (3x3 max-pool, threshold 0.3 x max) + hard-negative patch mining; weights NC, code MIT |
| PET / P2PNet | point-based crowd counting | ICCV 2023 / ICCV 2021 | PET: MIT file but README says "academic purposes only" (V); P2PNet LICENSE clause 1: "academic research" only (V) | Google Drive, no weights licence | ShanghaiTech etc., point labels only | PET SHA MAE 49.34 (V); NWPU F1 0.742 (V) | PET 20.9M params (S) | elements as points | no | skip for shipping; idea: train on box centres |
| SKU-110K EM-merger / CrowdDet Set-NMS | retail shelves, crowds | CVPR 2019 / CVPR 2020 | SKU110K repo: no licence; CrowdDetection **Apache-2.0** | not stated | SKU-110K non-commercial (README quote, V) | SKU-110K MAE 14.5 and AP .492 (V); CARPK MAE 6.77 (V) | not stated | elements | no | idea: adjacent identical symbols (three-pane window strip) |
| StarDist | microscopy | MICCAI 2018 (PDF downloaded and read, 8 pages) | github.com/stardist/stardist **BSD-3** (read) | pretrained models trained on DSB2018 and MoNuSeg; weights licence not stated | paired raw and fully labelled images | the paper names two errors in crowded scenes: merging touching cells, and suppressing valid instances because boxes overlap (V); a 1000-image toy set of touching half-ellipses with large box overlap tests this | U-Net; GPU figures not found | elements as star polygons | no | idea only: per-pixel polygon plus NMS on polygons, so adjacent identical objects whose boxes overlap are not suppressed |
| CAD-Prompted SAM3 | industrial pick and place | Feb 2026 | github.com/kevinPOI/cad_prompted_sam3 **Apache-2.0** | not stated | 9k CAD models, 15k synthetic images | SAM 3 exemplar baseline F1 0.156 (3D-print set), 0.189 (T-LESS), 0.507 (ITODD) (V) | RTX 4070 timing in the paper | n/a | no | evidence: exemplar-only prompts fail on texture-less objects |
| SAM 3 in remote sensing | aerial | Jul 2026 | not stated | not stated | n/a | DIOR mAP text 11.67 vs box exemplar 66.55; iSAID 11.85 vs 32.77 (V, tables re-read) | not stated | n/a | no | evidence: exemplars rescue a model that text-only misses |

## 3. Transfer notes (what plays our object, why it should transfer, what breaks, usable as it is?)

**T1. SAM 3 and the colony-counting pipeline (open-vocabulary counting, colony/cell tools).**
- Plays the role of our object: a window cell or door-with-leaf is "the concept"; the same-image exemplar is a box the
  user or a first detector pass marks. SAM 3 takes positive and negative boxes as exemplars (V, section 3) and finds
  all matches.
- Why it should transfer: exact-match is measured (94.0% / 86.3%) with a fixed recipe, and AgentCount counts
  colonies at 33.5 s per image on a 12 GB card (V), so memory is not the blocker.
- What breaks on our images:
  - It outputs masks for each object and for the group (V, F.4): a three-pane window strip would give 1 group mask
    and 3 cell masks, and our rule is one per drawn cell. The recipe's IoM-NMS removes nested masks, so it would
    drop the cells or the strip depending on score; we need to test which.
  - Input is 1008 px (V). A 5 to 20 px symbol at 855 px longest side stays about 6 to 24 px at 1008 px, below the
    scale the benchmarks use (no small-object number in the paper: "not stated", V).
  - Exemplar-only prompts did badly on texture-less, line-like objects: SAM 3 exemplar F1 0.156 (V, 2602.20551).
    Our windows and doors are line symbols with no texture.
  - Zero-shot in the Roboflow-100VL document-like group scores 12.9 AP, 10-shot fine-tune 35.8, full fine-tune 64.2
    (V, Table 36), so a fine-tune on our 104k boxes is the path, not the zero-shot model. The "Document" group of
    Roboflow-100VL (V, arXiv 2505.20612 dataset list) is 10 sets (88 classes, 21,418 images) that include activity
    diagrams and circuit voltages, mixed with invoices, signatures and wine labels, so it is the nearest public
    stand-in for line-art symbols; it contains no floor plan. Roboflow data is banned for our training (record 0003)
    but not for reading numbers.
  - Exact multiples of 90 degree rotations: no rotation result in the paper; our rot90 + flip training augmentation
    carries over.
  - Cross-image exemplars are not supported by the released code (issue 317, open; a user fork hack exists, not
    verified). Same-plan exemplars are supported, which is what the per-plan idea needs.
  - Fine-tune memory: the repo has a train extra and a COCO-format recipe; one user fine-tuned with 4 A100 for the
    full 840M parameters and also with the backbone frozen, 32.7M trainable (V, issue 324). Fitting a frozen-backbone
    run on 12 GB is plausible, not measured.
- Repo issues (read 2026-11-14): the CountBench evaluation script is not released (issue 505, open, asks for the noun
  extraction, script and post-processing), so the 94.0% recipe exists only in the paper's appendix; no smaller variant
  (issues 219 and 389 ask, open, no maintainer answer); no issue about small objects; the only OOM issue (169) is video.
  SAM 3.1 checkpoints exist (README, 2026-03-27) but are about video multiplexing.
- Repo files read 2026-11-14 (V, `gh api` contents): `pyproject.toml` dependencies are timm, numpy below 2, tqdm,
  ftfy, regex, iopath, huggingface_hub (train extras: hydra-core, submitit, fairscale, fvcore, torchmetrics, scipy);
  no GPL or AGPL package. Its classifier says "MIT License" while the LICENSE file is the custom SAM License, so the
  file, not the classifier, decides. README_TRAIN documents single-GPU fine-tuning from a config named for a
  100-image-per-class setting, so a few hundred labelled plans is the scale it was written for. SAM 3.1 notes
  (RELEASE_SAM3p1.md) are about video object multiplexing only (7x at 128 tracked objects, H100): nothing for stills.
- Code and weights usable as they are? Code and weights yes for a hackathon demo; shipping needs a decision on the
  SAM License because record 0006 names only MIT/BSD/Apache/ISC/LGPL. Weights are gated and the card could not be read
  from this machine.

**T2. Poisson-binomial count head (medical lesion counting).**
- Plays: a lesion candidate is a detection; its existence probability is the detector score.
- Why: it produces P(count = k), so the answer is the mode, the confidence is the mode's mass, and "abstain" is a
  threshold on it. Counts were binned 0, 1, 2, 3, 4+ in the paper, close to our 0 to 15 range per class.
- What breaks: it assumes detections are independent Bernoulli trials (V, Assumption 3). Adjacent identical symbols
  are not independent (a missed window next to a found one). The paper calibrates after clustering voxels to one
  region per lesion; our NMS plays that role, so scores must be calibrated per class first (Platt scaling on dev,
  not read in a paper here; the web-search result about it is not a read). The count rule (mode vs median) is not
  stated in the text I read.
- Usable as is? Idea only, implement ourselves. The reference repo has no licence file.
- Verified in the full text (headless browser, 2026-11-14): near 100% accuracy when only the lowest-entropy samples are
  kept, 90% at higher thresholds, connected-component baseline degrades at low thresholds; the paper's own example
  reads the distribution as "most likely one lesion, potentially two", i.e. the mode. ICACount (V, 2309.05277): the
  user gives a count range rather than an exact count because exact numbers are slow for people; Table 1 FamNet
  FSC-147 MAE 22.08 / RMSE 99.54 confirmed.
- How to calibrate (read: Kuzucu et al., arXiv 2405.20459, ECCV 2024, V for Tables 2 and 5 and A.11): Platt
  scaling or isotonic regression fitted per class on a held-out slice of in-distribution data, only on detections
  above a threshold, cut D-ECE from 12.8 to 0.9 (Platt) and 1.3 (isotonic) with AP unchanged (COCO, Deformable DETR,
  minitest about 2.5K images). Fitting on a domain-shifted set instead gave D-ECE 14.2 (V, Table 2). For us: calibrate
  on dev images of the same style mix, never on the sealed eval set. Code github.com/fiveai/detection_calibration,
  licence file is CC BY-NC-SA 4.0 (V, read), so write our own (the idea is a few lines with scikit-learn).
- No paper applies conformal prediction to counts: search found only box-interval conformal papers (arXiv 2605.07549,
  2403.07263; not opened).

**T3. CountGD++ negative exemplars and pseudo-exemplars (open-world counting, blood cells).**
- Plays: positive exemplars = windows; negative exemplars = bare openings and shower screens, the two rules our
  counts depend on.
- Why: negative prompts cut blood-cell MAE from 11.56 (positive prompts only) to 1.73 with internal and 1.52 with
  external negative exemplars (V, Table 2, same model, 100-image set with two look-alike cell types). Pseudo-exemplars = the model's top 3 boxes from a
  text pass fed back (V, section 4), i.e. exactly "two confident windows, find the rest".
- What breaks: no drawings, no number for objects under 30 px; weights file is a Gradio demo-grade release (1.25 GB
  on Google Drive); the backbone is Swin-B GroundingDINO at about 800 px shortest side (CountGD default, S), so a 6 px
  symbol is below the stride. RECOUNT's own run of the released CountGD++ (V, full text,
  Table 1, marked as their evaluation) gives LookAlikes MAE 24.6 with text only and 29.1 with pseudo-exemplars
  (worse), PairTally 66.9 vs 65.5 (slightly better). So pseudo-exemplars are not a safe gain on look-alike scenes,
  which is our case. RECOUNT's own idea is to take the exemplar from an external reference image of the category
  rather than from the query (CountGD +RECOUNT: LookAlikes 8.41, PairTally 39.96, V). For us the reference could be a
  canonical symbol crop per class (CountGD++ also accepts external exemplars, V section 3.1); never tested on drawings.
- Repo facts (read 2026-11-14): requirements.txt has no GPL/AGPL package (torch<2.6, transformers, gradio 4, timm,
  opencv-python, pycocotools; README needs detectron2 for a compile step); full training code is released (issue 6);
  `infer_sahi.py` slices at 1024 px with 200 px overlap and merges with NMS 0.5 (issue 8); the model returns at most
  900 queries per pass, so dense images use adaptive crops with 4x super-resolution (V, appendix); keep
  super-resolution out of our count path (hallucinated strokes, earlier campaign finding). Open CountGD issues
  include false positives (41) and fine-tuning on custom data (40, 52, 56), with no memory figure.
- Usable as is? Code and HF card MIT. Use as a second counter to compare with the fine-tuned detector, not as the
  main one.

**T3b. Self-bootstrapped exemplars (AdaCount, PerSense++, CountZES).**
- Plays: the plan's own first-pass detections are the "support image"; the second pass finds what the first missed.
- Why: AdaCount raised exact-ish error metrics on three natural-image sets (V, above); PerSense++ adds a diversity
  rule (pick exemplars of different size and appearance, not the top 4 by score) and splits composite contours with a
  distance transform (V for PerSense v4: contours above mean + 2 sigma are split), which is the window-strip case.
- What breaks: all depend on the first pass. PerSense v4 says it "cannot recover any true positives missed initially"
  (V); AdaCount says the same (V). Our recall problem is exactly the missed small symbols, so a bootstrap from a weak
  first pass inherits the miss. Both are measured by MAE, mIoU and AP, never exact match. PerSense-D images average
  53 instances; ours have about 9 per class.
- Usable as is? AdaCount needs SAM 3 (licence call) and has no stated code licence; PerSense stack needs
  GroundingDINO, VIP-LLaVA, CounTR and SAM. Idea only; the cheap version is our own: second pass of the same fine-tuned
  detector with lower threshold restricted to boxes whose embedding matches the first-pass boxes.

**T3c. Touching or adjacent identical objects (LC-FCN, POLO, Cellpose-SAM, StarDist).**
- StarDist (V, paper read): box NMS suppresses valid neighbours when boxes overlap; relevant to a window strip only if
  the boxes of adjacent cells overlap, which our labelled boxes should not (they are drawn cells), so check the detector's
  NMS IoU threshold on dev instead of assuming.
- LC-FCN (V): a train-time split loss penalises a blob that holds two labelled points; test time has no splitting.
  Result: Trancos MAE 3.32; it still groups objects (V). POLO (V): point-only YOLOv8 variant with a distance rule
  instead of IoU-NMS; the authors say both models struggle with animals in close proximity. Cellpose-SAM (V): flow
  fields plus 1000 gradient-tracking iterations; no touching-object analysis in the text, 256 px tiles, objects
  trained at 7.5 to 120 px diameter. What breaks on our images: all three work on blobs or masks; our windows are
  line drawings with no filled area, and a three-pane strip is a grid of cells that share edges. Idea only.

**T4. Count-as-classification with integer bins (crowd counting, CLIP-EBC).**
- Plays: a block or tile is a bin of the page; the label is the integer count of window boxes in it.
- Why: integer bins removed border ambiguity and cut UCF-QNRF MAE from 140.6 to 88.3 before adding noise
  reduction and the count loss (V, ablation). Our earlier count-only FCN regressed fractions and stuck at 18% on
  windows and doors (`stoa-cubi.md`).
- What breaks: all results are on crowds of hundreds, merged bin `[4, inf)` at block size 8; we need `[m, inf)` at
  larger m. No per-bin or low-count numbers in the paper (V, "not stated"). Repo archived 2026-10-22, so nobody
  will fix it.
- Verified in the full text (headless browser): ablation 140.6 / 88.3 / 85.8 / 77.9 MAE; the paper says the count can be
  taken as the expectation or the mode over bins (section on EBC), which is the rule T2 uses; bins are 0,1,2,... with
  prompts "There is 0 person".
- Newer in the same line (2025-2026): ZIP (arXiv 2506.19955; V, full text re-read) models each block as
  zero-inflated Poisson because over 95% of 8x8 blocks are empty; NWPU val MAE 28.2 vs CLIP-EBC 36.6, SHA 47.8 (V,
  Table 3); no code URL in the paper (V); NWPU test MAE 60.1 / NAE 0.104 vs CLIP-EBC 61.3 / 0.148 (V Table 4). CLIP-EBC for cars (2507.08240, V): CARPK MAE 4.01 / RMSE 6.02, second to a non-CLIP
  method at 2.12; 224 px input, block 8, 7 days on one A100; no code URL. CountIHC (2511.12588, V, full text): count bins n = 4 on IHC cell counting; vs CLIP-EBC the class-balanced error WM
  falls 6.1 to 5.8 (Ki67-Camera) and 23.1 to 21.3 (Ki67-WSI), 5-fold cross-validation, private data; MAE-type metrics only. None reports exact match. Our maps are mostly zero (about 9 windows on a page), so the
  zero-inflation idea fits better than plain regression.
- SAM 3 repo issues read 2026-11-14 (V, issue text): 464 (open) the decoder has 200 queries, so at most 200
  instances per image and changing it breaks loading the pretrained weights (fine for us: tens of windows per page, but
  it caps tiled full-sheet counts); 460 (open) fine-tuning on images with many small same-class masks recovers only
  some of them when the training images are not annotated exhaustively, which is the failure to avoid when labelling
  our pages; 324 (open) a fine-tune that detects nothing at inference. CountGD issues 38, 40, 52, 56 (open) all ask
  how to train or fine-tune on custom data; I found no maintainer answer in the list view (S).
- Issues read 2026-11-14 (V): CLIP-EBC issue 11 (closed, no cause found) a user on schools of fish got counts about
  double the truth with their own bin set and fixed it by downscaling the density map afterwards, so own-bin training
  needs a check of the sum rule on a held-out set; issue 8 (closed) the authors fine-tune the whole CLIP image
  encoder rather than freezing it. CountGD++ issue 6 (closed): full training code released and linked in its README.
- Repo: requirements pinned (torch 2.2.1, timm 0.9.16, numpy 1.26.4), no GPL packages; the one open issue about
  training cost (23, GPU and hours) is unanswered.
- Usable as is? Code MIT; needs fine-tuning on our boxes as point labels.

**T5. Interactive correction (ICACount, SAM 3 exemplars, AgentCount review overlays).**
- Plays: a person reviews the machine's marks. ICACount: pick a region, give a count range (bins up to 4) and a
  refinement module adapts; 5 rounds; per iteration the visualisation (with segmentation) and the adaptation are each under one second on an RTX 3080 (V, Fig. 12; the earlier "about 4 s" was a summary error); its limitations section says feedback is for a region and the count is a range, not an exact number (V). SAM 3: after 3 exemplar boxes PCS beats text-only
  by +21.6 cgF1 (V, Figure 7); AgentCount keeps overlay plus raw-mask overlay and flags crowded/edge objects (V).
- What breaks: ICACount works on density maps and its code was not found; our correction is a box and a class. No
  exact-match rate in any of them.
- Usable as is? Idea. The SAM 3 loop is a product feature that needs the same licence decision as T1.

**T5b. Look-alike classes and exclusion (CountEx, PairTally).**
- PairTally (arXiv 2509.13939, V, full text): 681 images, two look-alike categories per image; DAVE, GeCo, CountGD
  and four VLMs all conflate the two (CountGD MAE 39.78 inter-scene vs 37.38 for a median-count baseline, V Table 3);
  "negation prompts" given to VLMs did not help (V, no numbers). Our look-alikes are window vs door symbol, shower tray
  vs screen, bathtub vs sink outline.
- CountEx (arXiv 2602.19432, V for Tables 2 and 5): adds negative text and exemplars to a LLMDet-based
  counter trained with point labels; CoCount NC MAE 32.22 (positive text only) to 26.67 (plus negative text) to 26.61
  (all four prompts) (V Table 5); 156 objects per frame on average (my arithmetic from Table 1), so this is a dense-scene
  result. Trained, not zero-shot; code github.com/bbvisual/CountEx has no licence file (`gh api` 404); PairTally repo
  spdx NOASSERTION. Idea only: a negative class in our detector (door-without-leaf is already one: 1.8k boxes).

**T5c. Human-in-the-loop for tiny objects (Burges et al., WACV 2025).** Abstract read (V, headless browser): the
authors say tasks that need 100% recall and near-perfect precision are done by hand, and propose IRTDETR, where the
annotator's points or boxes are related to the whole image by cross-attention with an attention loss; search listing
(not a read) reports 2.46x faster annotation than manual on a user study. Repo github.com/mburges-cvl/WACV_IAODF is
**MIT** (README: RT-DETR with ResNet18, one class only, patch-border false positives and negatives untested at larger
patches, 4 GB VRAM minimum). The CVF PDF and the C3Det CVPR 2022 PDF refuse automated fetch: abstract-only. This is the
closest "person checks the machine's marks" result in a small-object setting and uses an Apache-class detector family.

**T5d. Detector output fed to a language model (GroundCount, arXiv 2603.10978, V).** YOLOv13x boxes written as text
(class, index, grid position, confidence, threshold 0.5) lift five small VLMs on the yes/no counting subset of PhD by
6.2 to 7.5 points for four of five (one drops 1.5); the detector alone gets 72.8% in 0.1 s (S). The metric is binary
VQA accuracy, not exact count. Our pipeline already counts in code from detector boxes; nothing to take except that
low-confidence boxes hurt (threshold 0.3 lost 1.3 to 16.9 points, V). YOLOv13 repo iMoonLab/yolov13 is AGPL-3.0 (V, gh search); Ultralytics-lineage
detectors are excluded by record 0006 anyway. Belongs to L7.

**T6a. HerdNet details that matter for us (V, postprint, read 2026-11-14).** Closest crowd-to-herd analogue of our task:
point targets (FIDT maps), animals as small as tens of pixels in 24 MP images, close-range herds where neighbours
touch. It beat an anchor-based detector by 9.1 MAE points (6.1 vs 15.2) and a density model by 9.8 on the test set; the
authors attribute it to anchors failing on close-by, occluded animals where boxes overlap. Tiles overlap by the width of
the largest object; predictions in overlaps are averaged on the grid before peak extraction (the README's
`reduction='mean'`), whereas the Faster R-CNN baseline used NMS at IoU 0.5. A second training round on hard-negative
patches mined from the first model's stitched predictions cut false positives. What breaks on our images: animals are
filled blobs with a peak; a window is a few strokes in a wall, and the output has no per-instance box, so size and
class-with-leaf rules (door with swing, not bare opening) need a second head. Still a MAE and F1 paper: no exact match.

**T6. Tile merge and adjacent identical objects (PCB, retail, wildlife).**
- PCB tile paper (arXiv 2605.24726, abstract only, HTML 404): detector trained on 640 px tiles 0.72/0.94 mAP50 vs
  0.01 for a full-image-trained one at tile inference; 128 px overlap lifts boundary-zone recall from 26 to 63% to 70 to
  100% (R). HerdNet stitcher overlap 160 px, reduction "mean" (README, V, what it averages is not stated).
  Our tile edges would double-count a window unless dedupe is class-aware; SAM 3's IoM dedupe (V) is the cheapest
  fix. SKU-110K's EM-merger and CrowdDet Set-NMS target the same problem for boxes that overlap by design; neither
  gives an exact-count number. Idea only.

**T6b. Splitting merged blobs by contour concavity (MCount, PLOS One 2025, read in full through Europe PMC XML).**
- Plays: a colony cluster is a connected region holding several identical objects; ours is a window strip or an arc
  of door leaves touching a wall.
- What it does (V): split each contour at concave points, then pair contour pieces with candidate circles under a
  penalty lambda on the circle count; two hyperparameters (d = 0.5, lambda 26 to 38), tuned on a few labelled or
  unlabelled images by an equidispersion criterion.
- Numbers (V): 960 plates, 15,847 segments; average error rate 3.99% vs NICE 16.54%, AutoCellSeg 33.54%, OpenCFU
  50.31%; zero error on 91.45% of segments (segment-level exact match); ground truth for merged colonies came from a
  photo taken hours earlier (V). Code github.com/hyu-kim/mcount **MIT** (gh api); data on Dryad, licence not read.
- What breaks on our images: it fits circles, so it only transfers to blobs. It is still the only adjacent result I
  found that reports an exact-match share for counting objects inside touching clusters, and its recipe (classical
  geometry, two knobs, tune without labels) is what a stage-8 SecondCounter on the wall mask could mimic.

**T7. Fields I touched and found nothing usable.**
- Crop and plant counting (search 2026-11-14): CSNet (count-supervised wheat ear counting, journal, search snippet only),
  FoMo4Wheat (arXiv 2509.06907, abstract only; HTML 404; abstract does not mention a counting head). No exact-match
  metric surfaced.
- Retail and industrial stacks: arXiv 2603.15470 (V, tables): counts identical parts in bins from volume, not
  instances; counts 19 to 20,063; humans NAE 0.79; says nothing about 5 to 20 px symbols. Not transferable.
- Pills (JMIR AI 2026, read in full through Europe PMC, CC BY): YOLOv12 and Faster R-CNN detections merged, then SAM
  boxes-as-prompts refinement; pill-level MAE 0.167 and dosage-level (image-level) accuracy 0.933 vs 0.300 / 0.733
  (Faster R-CNN) and 0.300 / 0.767 (YOLOv12) on the public set (V, Table 1); the paper's own failure analysis says
  YOLOv12 puts several overlapping boxes on one pill when pills cluster, which over-counts, and SAM refinement alone
  does not remove redundancy (V). The count rule that decides is the merge of two detectors, not SAM. Adjacent identical
  objects, small counts (0 to 10), image-level accuracy near our exact match: the closest published analogue to our
  stage 8 (two independent counters, disagreement flagged). Code URL: none found in the text (no github string).
- CoNIC (arXiv 2303.06274, PDF downloaded and read): cell counts scored as per-class R2 of per-patch counts (a
  correlation score) plus mPQ+; per-class results only in heat-map figures, no exact-match; counts in 256 px patches,
  central 224 px region counted so border objects are counted once (V, methods). Note the border rule: it is the same
  problem as tile seams.
- Trees: DeepForest code MIT (README read), model licence, patch handling, counting accuracy not stated in what I
  read; I did not open the docs site.
- Traffic: CARPK/TRANCOS appear only as benchmarks in the counting survey (V).
- OMR (DoReMi 2107.07786, Shatri and Fazekas 2408.15002): small-class AP is low (Faster R-CNN on full 2475 x 3504
  pages: small AP 41.7, V), staff lines are found by classical CV, not by the detector. Same shape as "symbols on
  wall lines". Belongs to L11 (vector); one line only.

**T8. Music-score symbol detection (Deep Watershed Detector, Tuggener et al. 2018, arXiv 1805.10548; read in full, V).**
- Plays: a notehead or rest on a score page is our window symbol: tiny, repeated, drawn in line style on a white page,
  hundreds per page, with look-alikes (black vs half notehead; flat vs natural).
- What it shows: pretrain on a large rendered set (DeepScores) and fine-tune on a small handwritten set (MUSCIMA++:
  140 pages, 91,255 symbols, 105 classes; split 110/15/15 pages, V), the same "many plans from one renderer then a few
  real ones" shape as our style-shift question. Per-class AP is reported (for example black noteheads about 0.86 at the
  loose and 0.92 at the second threshold, V, table in the paper; I did not map the two columns to IoU values, so quote
  with care). Whole-page counting accuracy is not reported.
- What breaks on our images: its detector is a dense energy-map network from 2018 (I did not check for released weights);
  it measures AP per class, never exact page counts. Nothing newer found in a 2025-2026 search (YOLO variants for OMR
  are reported in snippets only, S). Idea only: pretrain on rendered pages, adapt on a few real ones, and report the count error per page.

## 4. What I would run first (cheap, answers the open question)

1. Exemplar counting vs fixed detector, per plan: take the fine-tuned detector's top-2 boxes per class on 100 dev
   plans as same-image exemplars; compare exact match against the detector alone, with SAM 3 (needs the licence call)
   and CountGD++. If it does not beat the fixed detector on exact match, drop the per-plan idea.
2. Apply the SAM 3 dedupe rule (IoM, threshold 0.5) to the detector's output before counting; it moved exact match
   9 to 10 points on photos, and costs one function.
3. Add the Poisson-binomial mode and its mass as `confidence`, using calibrated per-class scores; set abstain from
   dev.

- Metric trap from the counting survey (arXiv 2608.23845, opened and searched in full 2026-11-14, V): it defines a
  "semantic grounding illusion", an exact-match or MAE score "is satisfied by any combination of correct and
  compensating errors that happen to sum to the right scalar" (V). For us: a page whose predicted count equals the
  truth because one missed window cancels one false door-leaf is a pass on exact match and a wrong answer on the
  plan. Score exact count and, separately, matched instances (IoU or point match) per page, and report the gap.
- HoloCount (arXiv 2607.06420, opened in full via headless browser, V): 2,480 QA pairs, 20 subsets, exact-match
  accuracy for zero-shot multimodal LLMs only (no trained or specialist counters). On its dense subset the best open
  model gets 20.0% exact (Qwen3.5-27B), most open models under 10%, Gemini-3.1-Pro-Preview 49.0%, while the same open
  model averages over 80% on the other subsets (V). Same message as AECV-Bench: prompted VLMs are not exact on dense
  small objects. It has a small-scale subset (101 images, 995 boxes) but I did not read its per-subset numbers.
- ACFamNet (arXiv 2604.20030, opened, V for the framing): few-shot counting of small clustered bacterial colonies
  (FamNet and SAFECount adapted with RoI Align and attention, Synoptics plate images); metric is normalised error
  (MNAE about 9 to 12%), not exact match; the prior "cardinality classification" method it cites (a CNN labels each
  cluster with how many colonies it holds, counts are summed) is the colony-field cousin of our integer-bin head.
- Counter-evidence on negative exemplars in SAM 3 (arXiv 2604.05433, "Few-Shot Semantic Segmentation Meets SAM3",
  opened in full, V, section 4.3): with a frozen SAM 3 on PASCAL-5i and COCO-20i, adding negative exemplars (1, 3 or 5)
  lowers mIoU and FB-IoU, worse with more of them, and often collapses the prediction to background; the authors drop
  negatives from their pipeline. This is segmentation, not counting, and not drawings, but it means the CountGD++
  negative-exemplar gain (blood cells 11.56 to 1.52 MAE) does not carry over to SAM 3 by assumption. Top-5 rows 3 and 5
  mention negative exemplars: for SAM 3 treat them as untested, for CountGD++ they have the V numbers above.

## 5. Citation graph walked forward (Semantic Scholar API, 2026-11-14)

- From SAM 3 (arXiv 2511.16719): 1000 citing papers returned (first page), about 100 of them with counting, cells,
  exemplars or floor-plan words; read from them: Count Anything 2605.30846 (full text, headless browser), HieraCount 2605.10887, CASE 2610.39396,
  Mask to Concept 2606.26711, One Click per Cell Type 2605.29429, TAG 2610.14651, AgentCount 2611.05398, CAD-Prompted
  SAM3 2602.20551, SAM 3 in remote sensing 2607.09583, the counting survey 2608.23845 (opened in a later round). Opened later: ABACUS 2606.23835 (V): a 3B unified VLM with adaptive zoom tiles and a GRPO count policy; FSC-147 test MAE 5.03 vs CountGD++ 8.39 (its own table); its "exact match" numbers (71% on CoCoCount) are for count-faithful image generation, not counting, so no exact-count evidence for us; no code or licence read. Seen, not opened: SAM3Count
  (CVPRW 2026, named in the survey), AdaCount 2607.02139, ABACUS 2610.28316, "Pano2BIM" 2611.00097 (floor plan, other
  scope), TF-Count (cell counting with DINOv2).
- From CountGD++ (2512.23351): 16 citing papers; read RECOUNT 2608.20621, the survey, CountZES 2512.16415 and
  AdaCount 2607.02139; seen, not opened: CoDi 2512.20153. MixCount 2605.18063 opened later (V, CC BY 4.0 paper, dataset CC BY-SA): synthetic mixed-object counting set; its appendix A.2 measures exemplar choice: a non-optimal exemplar raises the MAE of its best model by 0.13, about 4.7% relative, so exemplar quality matters but a poor pick is not catastrophic on its data (natural-object scenes, not drawings).
- Sideways from the survey and search: OCCAM 2601.13871 (read), PerSense++ 2508.14660 (read), POLO 2410.11741 (read).
  2025 to 2026 sources read in full or in part: SAM 3, CountGD++, CLIP-EBC v3, Count Anything, HieraCount, RECOUNT,
  AgentCount, CASE, M2C, CoP, TAG, CAD-Prompted SAM3, SAM 3 remote sensing, survey, CountingDINO, AdaCount,
  CountZES, PerSense++, OCCAM, ACFamNet, Cellpose-SAM (21).
- From CLIP-EBC: the citations page returned 404, so no forward walk; used SKU-110K's listing instead (arXiv
  search found 2509.09750, 2504.09819, 2509.08738, all read only at abstract).

## 6. Looked for and did not find

- Any exact-match counting result on 5 to 20 px symbols, on drawings or on any field (SKU-110K, crowd, cell, wildlife,
  PCB, pill): none; they report MAE, AP, F1, MNAE.
- SAM 3 (or any open-vocabulary segmenter) evaluated on floor plans, technical drawings or P&ID: search found
  none; the SAM 3 text mentions no floor-plan data.
- Per-plan exemplar counting compared with a fixed fine-tuned detector under style shift: none.
- A paper that turns detector scores into a count distribution for object detection (not segmentation): none; the
  marked-point-process paper (2506.21486) gives a Poisson law over regions but no count accuracy (V).
- Pill and PCB exact-count benchmarks: none found.
- Third attempt, different terms (search snippets, S): no source applies a Poisson-binomial or conformal interval to
  object counts for a detector, or abstains on a count. Closest: "Object Detection as Probabilistic Set Prediction"
  (ECCV 2022, opened in full, V: reads detector outputs as a multi-Bernoulli or Poisson multi-Bernoulli density over the
  set of objects, scores it with a threshold-free negative log-likelihood, and says fine-tuning on that likelihood
  reduces false and duplicate detections; it evaluates on COCO and says nothing of count accuracy, so it supports
  row 2's idea of a count law from instance probabilities but gives no exact-count number) and a 2021 note that the count over instances with unequal probabilities is Poisson-binomial
  with a fast recurrence (spatial databases; not opened).
- Second attempt (different terms, search snippets only, S): P&ID counting work exists as question answering over a
  graph (PIDQA, MDPI MAKE 7/2/39, 64,000 questions with a counting category) and as a trained symbol detector with
  mAP only (an RF-DETR P&ID model card, 33 classes, tiled inference); neither reports per-sheet exact-count accuracy.
  Poisson-binomial or count-distribution calibration for detectors: nothing beyond the marked-point-process paper.
- Weights licence for CountGD and CountGD++: Hugging Face model cards say `mit`, not gated (V, API, 2026-11-14). DAVE and GeCo weights: only the code licence files (GeCo2 repo file is MIT); weights licences not stated.
- A readable copy of the HerdNet paper (ScienceDirect 403; the ORBi author postprint at orbi.uliege.be/bitstream/2268/299905 exists but exceeds the 10 MB fetch limit and the headless browser cannot open PDFs), the StarDist paper body (binary), MCount (bot check), the JMIR pill
  paper and the RGU engineering-drawing few-shot paper (empty or 403 even through the headless browser).

## 7. Open questions and missing tools

- Does the team accept the SAM License for the product or only for a prototype? Record 0006 does not name it.
- Do SAM 3's web image pools (MetaCLIP, SA-1B) contain CubiCasa5K images? Its named external datasets do not
  (Table 25). Unknowable from the paper.
- Resolved: RECOUNT's table shows pseudo-exemplars hurt on LookAlikes (24.6 to 29.1) and help slightly on PairTally (66.9 to 65.5).
- Does the 3-pane window strip count as 3 under SAM 3's group-vs-individual outputs?
- For L1/L7 owners: Pano2BIM 2611.00097 and PID2Graph 2411.13929 (P&ID graph extraction, L11) look relevant and were
  not opened; AECV-Bench is already in `01-vlm-drawing-qa.md`.
- AECV-Bench (arXiv 2601.04819, V full text, PDF read 2026-11-14): 120 floor plans, per-plan exact-match count of
  doors, windows, bedrooms, toilets by prompted VLMs, no trained detector. The abstract's "0.40-0.55" is the mean over
  four classes; doors and windows alone are far lower: best door 0.39 and window 0.34 (Gemini 3 Pro), GPT-5.2 0.28 and
  0.27, Claude Opus 4.5 0.16 and 0.16, open models 0.03-0.12 (V Table 1). Bedrooms and toilets reach 0.6-0.9. This is
  the only floor-plan exact-count number found, and it is the baseline a trained or exemplar counter must beat.
- Blocked even through the headless browser: ScienceDirect (HerdNet paper), PMC and JMIR (empty). Abstract-only.
- Missing tools: no arXiv MCP; Semantic Scholar worked by API for two papers, 404 for the others; web-fetch
  summarised the tail of long HTML pages (those numbers are marked S); the headless browser gave the full SAM 3 text
  but returned nothing for JMIR AI and RGU.
- Not done: no model was run; hours to a first number are estimates.
- Status of marks at the end (2026-11-14, about 01:13): numbers in the top 5 and in the rows I re-read this round
  (AdaCount, CountEx, ZIP, PerSense++, CountZES, CountIHC, RECOUNT, HieraCount, ICACount, Kuzucu, AECV-Bench) are V.
  Still S or search-snippet only: CountGD issue titles, GeCo ablation numbers, CASE/TAG/M2C tails, the P&ID and OMR
  2025-2026 searches, and the Poisson-binomial pointers. Caveat for rows 3 and 5: negative exemplars are evidenced on
  CountGD++ only; on frozen SAM 3 they hurt (2604.05433). CountGD++ is MIT; PerSense and CountZES code are
  PolyForm Noncommercial, so they are idea-only.
