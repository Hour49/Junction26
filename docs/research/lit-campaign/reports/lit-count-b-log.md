# lit-count-b reading log (one line per source opened; date read 2026-11-14)
- https://arxiv.org/abs/2511.16719 + /html (SAM 3): counting protocol thr 0.5, CountBench 93.8% acc / MAE 0.12, PixMo-Count 86.2%; 848M-class model, 1008 px, exemplar prompts, RF100-VL AP0 15.2 -> AP10 36.5; later part of HTML summary-extracted
- https://github.com/facebookresearch/sam3 LICENSE (gh api): custom "SAM License" (Nov 19 2025), spdx NOASSERTION; HF facebook/sam3 gated (curl README refused)
- https://arxiv.org/abs/2512.23351 + /html (CountGD++, CVPR 2026): pseudo-exemplars = 2nd pass with top-3 own boxes; FSCD-147 t 16.55 -> t+p 10.29 MAE; blood-cell MAE 1.52; no exact-match number
- https://github.com/niki-amini-naieni/CountGDPlusPlus README + HF nikigoli/CountGDPlusPlus card: code MIT, HF card mit; weights 1.25 GB; built on GroundingDINO Swin-B + SAM ViT-H
- https://github.com/niki-amini-naieni/CountGD README: weights on Google Drive, code MIT
- https://arxiv.org/abs/2403.09281 + /html + github Yiming-M/CLIP-EBC (CLIP-EBC, ICME 2025): integer-bin blockwise classification; UCF-QNRF 140.6 -> 77.9 MAE; code MIT; no low-count numbers; repo archived 2026-10-22
- https://github.com/Alexandre-Delplanque/HerdNet README + LICENSE.md: MIT code; weights CC BY-NC-SA 4.0; paper itself blocked (403)
- https://arxiv.org/abs/1904.00853 (SKU-110K): EM-merger/Soft-IoU; dataset non-commercial; repo has no licence
- https://arxiv.org/abs/2003.09163 + github megvii-model/CrowdDetection: EMD loss + Set NMS; Apache-2.0
- https://arxiv.org/abs/2509.09750, 2504.09819, 2509.08738 (abs only): dense retail co-training, density-guided crowd detection, CrowdQuery
- https://arxiv.org/html/2408.15002v2, https://arxiv.org/abs/2107.07786 (OMR; belongs to L11 vector): staff lines handled by classical CV; small-class AP 41.7 (Faster R-CNN)
- https://arxiv.org/html/2608.23845 (counting survey, Aug 2026): taxonomy; no exact-match numbers; nothing on drawings
- https://arxiv.org/abs/2605.30846 + html (Count Anything, May 2026): SAM3 + P2PNet-style dense counter, 848M, 1008 px; HTML past 20% summary-extracted
- https://arxiv.org/abs/2605.10887 + html (HieraCount): GroundingDINO backbone, synthetic Kubric
- https://arxiv.org/html/2608.20621 (RECOUNT): CountGD points + DINOv3 accept/reject; CountGD++ pseudo-exemplars worse than text alone on PairTally
- https://arxiv.org/html/2611.05398 (AgentCount, colony counting): SAM 3 text prompts, validation agent, human review, 33.5 s/img on 12 GB; MAE 4.3 colonies; no exact-match
- https://arxiv.org/abs/2610.39396 + html (CASE): frozen SAM 3 ignores negative exemplars; LoRA adapter 1.13M params fixes; mIoU 35.8
- https://arxiv.org/abs/2606.26711 + html (Mask to Concept): learned concept embedding on frozen SAM 3, medical only
- https://arxiv.org/abs/2605.29429 + html (One click per cell type): training-free, 1 click per type AJI 0.731 CoNIC
- https://arxiv.org/abs/2610.14651 + html (TAG): SAM3 class calibration with image-level labels, 3.1M params
- https://arxiv.org/abs/2308.13814 + html + github cxliu0/PET (PET): point query quadtree; MIT file but README "academic only"
- https://github.com/TencentYoutuResearch/CrowdCounting-P2PNet LICENSE: academic research only
- Semantic Scholar API citations of 2511.16719 (1000 rows) and 2512.23351 (16 rows): forward walk lists
- https://arxiv.org/abs/2602.20551 + html (CAD-Prompted SAM3): SAM3 exemplar baseline F1 0.156/0.189/0.507 on texture-less parts; code Apache-2.0
- https://arxiv.org/abs/2607.09583 + html (SAM 3 remote sensing): text-only 11.67 vs box exemplar 66.55 mAP DIOR; tables summary-extracted
- https://arxiv.org/abs/2204.05276 + html (Schroeter, Poisson-binomial lesion counts): count acc ~88-90, ECE 0.72e-5; no licence on repo
- https://arxiv.org/abs/2506.21486 + html (conditional marked point process detection): no count accuracy; Apache-2.0 code
- https://arxiv.org/abs/2309.05277 + html (ICACount): 5 rounds of region+range feedback, ~30-40% MAE drop
- https://arxiv.org/abs/2605.24726 (PCB tile merge, abstract only; html 404): 128 px overlap lifts boundary recall to 70-100%
- https://arxiv.org/abs/2504.16570 + html (CountingDINO): FSC-147 test MAE 20.93; 4^k quadrant split for small objects
- https://arxiv.org/abs/1806.03535 (StarDist abs; PDF unreadable), https://github.com/stardist/stardist README+LICENSE: BSD-3, models DSB2018/MoNuSeg
- https://github.com/weecology/DeepForest README+LICENSE: MIT; no counting accuracy stated
- https://arxiv.org/html/2409.18686v2 + github jerpelhan/GeCo (GeCo): dense detection loss MAE 9.52 vs Gaussian 12.79; repo MIT; GeCo2 successor
- https://arxiv.org/html/2604.20030 (ACFamNet, colony counting): MNAE 9.64%; no exact match; fails across species
- https://arxiv.org/html/2511.16719 via headless browser (SAM 3 full text 282 KB): Table 37 exact-match 94.0/86.3 with IoM-NMS, 84.8/76.9 without; Table 36 RF100-VL Document 12.9 / 35.8 / 64.2; Appendix B limits
- gh api facebookresearch/sam3 readme + issues 317, 324: cross-image exemplar not supported; fine-tune train extra; 4 A100 full FT
- https://arxiv.org/abs/1807.09856 + html (LC-FCN): point supervision, split loss for touching blobs, count = blobs
- https://arxiv.org/abs/2009.13077 + html (DM-Count): OT loss no Gaussian; code stonybrook cvlab licence not read
- https://arxiv.org/abs/2411.13056 + html (E-MAC, DroneBird): video counting, not our shape
- https://arxiv.org/abs/2410.11741 + html (POLO): point-only YOLOv8 variant, MAE only, AGPL stack
- https://arxiv.org/abs/2601.13871 + html (OCCAM): training-free SAM2+FINCH multi-class counting; CARPK MAE 10.06
- https://arxiv.org/abs/2607.02139 + html (AdaCount): SAM3 own detections -> prototypes -> warp -> 2nd pass; FSC-147 22.89->18.97, CARPK 3.52->1.99, MBM 23.25->19.11
- https://arxiv.org/abs/2512.16415 + html (CountZES): 3-stage exemplar discovery; CARPK MAE 7.24 zero-shot
- licences via gh: Count Anything Apache-2.0, AgentCount MIT, cad_prompted_sam3 Apache-2.0, cmpppnet Apache-2.0, GeCo MIT
- BLOCKED: JMIR AI pill paper (HTTP 202 / empty via pwfetch), RGU repository paper (403, empty via pwfetch), PMC MCount (bot check), HerdNet paper (ScienceDirect 403)
- https://arxiv.org/abs/2405.20459 + html (Kuzucu, calibration of detectors): Platt/isotonic per class on held-out split D-ECE 12.8 -> 0.9; domain-shifted calib set 14.2; Table 5 summary-extracted
- https://arxiv.org/abs/2303.06274 (CoNIC, abstract only; html 404, PDF too large, pwfetch aborts on PDF): counting scoring not read
- https://arxiv.org/html/2508.14660, https://arxiv.org/html/2405.13518v4 (PerSense++/PerSense): PerSense-D 717 imgs, mean 53 instances, mIoU 70.96; cannot recover first-pass misses
- https://www.biorxiv.org/content/10.1101/2025.04.28.651001.full + github MouseLand/cellpose LICENSE + HF mouseland/cellpose-sam README (Cellpose-SAM): BSD-3 code, HF card bsd-3-clause, README says data CC-BY-NC; 256 px tiles; 8-image fine-tune
- https://deepforest.readthedocs.io pages + HF weecology/deepforest-tree: predict_tile patch 400 overlap 0.05 iou 0.15; HF card mit; no count metrics documented
- https://huggingface.co/facebook/sam3 via headless browser: header "License: other", card gated; full-text Table 25 lists SA-Co/EXT sources (no floor-plan set)
- gh api facebookresearch/sam3 README_TRAIN.md: fine-tune via sam3/train/train.py, configs roboflow_v100, single-GPU command shown, no memory figure
- https://arxiv.org/html/2512.23351 via headless browser (CountGD++ full text, 90 KB): Table 1 verified 16.55/10.29/8.39; Table 2 blood cells 11.56 -> 1.73/1.52 with negatives; 900-query cap, adaptive crops with 4x super-resolution
- gh api CountGDPlusPlus requirements.txt, issues 1-9: no GPL/AGPL deps; infer_sahi.py 1024/200/NMS 0.5; training code released
- gh api CountGD issues list: false positives (41), fine-tune requests unanswered
- gh api Yiming-M/CLIP-EBC requirements.txt + issues: pinned torch 2.2.1; issue 23 GPU/training time unanswered
- https://arxiv.org/abs/2506.19955 + html (ZIP), 2507.08240 (CLIP-EBC cars), 2511.12588 (CountIHC): zero-inflated block counts; CARPK 4.01 MAE; no code URLs
- Semantic Scholar API citations of 2403.09281 (29 rows): ZIP, car CLIP-EBC, CountIHC, DenseUrchin, FlockCounter found; 2308.13814 and 2309.05277 returned no data (rate limit)
- BLOCKED again via headless browser: sciencedirect HerdNet paper, PMC11957731, ai.jmir.org pill paper
- https://arxiv.org/html/2204.05276 and /2309.05277 via headless browser (full text): Schroeter near-100% at low entropy confirmed; ICACount Table 1 FamNet 22.08/99.54 confirmed, user gives ranges
- gh issues facebookresearch/sam3 #505 (CountBench eval script not released), #219/#389 (no small variant), #169 (video OOM), #317, #324 read
- https://arxiv.org/abs/2603.15470 + html (stacked-object counting, volumetric): not transferable; counts 19-20063
- https://arxiv.org/abs/2509.06907 (FoMo4Wheat, abstract only; html 404)
- web searches (crop, retail, pill, PCB, colony, conformal): no exact-match counting metric found in any adjacent field
- https://arxiv.org/abs/2602.19432 + html (CountEx): negative text lowers CoCount NC MAE 32.22 -> 26.67 (S); ~156 objects/frame; code no licence file
- https://arxiv.org/abs/2509.13939 + html (PairTally, full text): look-alike conflation; CountGD MAE 39.78 vs median baseline 37.38
- https://openaccess.thecvf.com/content/WACV2025/html/Burges_... via headless browser (abstract only): IRTDETR interactive tiny-object detection; PDF unreadable; repo mburges-cvl/WACV_IAODF MIT
- Semantic Scholar citations of 2309.05277 (16 rows): found CountEx, PairTally, Interactive Tiny Objects (WACV 2025), CountZES, AdaCount; OpenAlex budget exhausted (no key used)
- https://arxiv.org/html/2505.20612 via headless browser (RF100-VL): Document group = 10 sets incl. activity-diagrams, circuit-voltages; 88 classes, 21,418 images; no floor plan
- https://arxiv.org/html/2608.20621 via headless browser (RECOUNT full): CountGD++ text 24.6 vs +pseudo 29.1 (LookAlikes), 66.9 vs 65.5 (PairTally); external reference exemplars
- https://arxiv.org/html/2605.30846 via headless browser (Count Anything full): Table 1 9.34/33.34, per-domain MAE, Table 7 5.17-6.53 GB, LoRA r=8, 8xA100 30 epochs
- https://arxiv.org/html/2403.09281 via headless browser (CLIP-EBC full): ablation verified; expectation or mode over bins
- https://arxiv.org/abs/2512.15254 + html (Hou et al., counters vs VLMs): exact-match accuracy T2ICount 0.38/TFOC 0.14/PseCo 0.01 on FSC-147; 0.03-0.06 on SolidCount vs Gemini 0.80; CC BY-NC-ND
- https://arxiv.org/abs/2603.10978 + html (GroundCount): detector text lifts VLM yes/no counting +6.2-7.5 pp; not exact count
- orbi.uliege.be HerdNet postprint: too large for fetch (10 MB limit); not read
- HerdNet postprint PDF (orbi.uliege.be, 14 pages, extracted with pypdf from a downloaded copy, paper not data): Table 3 F1 73.6 MAE 6.1 vs Faster R-CNN MAE 15.2; 512/160 tiles; averaged overlap then LMDS; RTX 3070 8 GB; hard-negative patch mining
- arXiv PDFs 2303.06274 (CoNIC, 47 pages) and 1806.03535 (StarDist, 8 pages) downloaded and read with pypdf: CoNIC counting = R2; StarDist box-NMS suppresses valid neighbours
- Europe PMC fullTextXML PMC11957731 (MCount, PLOS One 2025, CC BY): 15,847 segments, zero error on 91.45%, avg error 3.99%; concave-point split + circle fit; code hyu-kim/mcount MIT (gh api)
- Europe PMC fullTextXML PMC13485113 (JMIR AI 2026 pill detection, CC BY): MAE 0.167, dosage-level acc 0.933 vs YOLOv12 0.767; YOLOv12 duplicate boxes on clusters; two-detector merge + SAM; no code URL
arXiv 2602.19432 CountEx re-read in full via headless browser 2026-11-14 ~01:02: Table 5 ablation numbers confirmed (V)
arXiv 2506.19955 ZIP re-read in full via headless browser 2026-11-14 ~01:02: Table 4 test MAE 60.1 NAE 0.104, no code link (V)
arXiv 2601.04819 AECV-Bench read in full (PDF via pypdf) 2026-11-14 ~01:03: Table 1 door/window exact-match 0.39/0.34 best (V)
WebSearch 2026-11-14 ~01:05: P&ID counting (PIDQA, RF-DETR P&ID card) and count-distribution calibration gaps re-searched, nothing with exact-count numbers (S)
gh issues SAM 3 #464 #460 #324, CountGD #38/#40/#52/#56 read 2026-11-14 ~01:04 (V for SAM 3 bodies, S for CountGD titles)
WebSearch seed/colony/egg exact-count 2025: only a seed-counting paper (Frontiers Plant Sci 1659781) with MAE-type metrics, no exact-match rate (S) ~01:05
arXiv 2607.02139 AdaCount reread in full via headless browser 01:06: limitation and Table 6 runtime confirmed, S->V
arXiv 2607.09583 SAM 3 remote sensing tables re-read 01:06: 11.67/66.55 and 11.85/32.77 confirmed S->V
arXiv 2608.23845 counting survey opened in full 01:07: grounding-illusion metric caveat added (V)
arXiv 2606.23835 ABACUS opened 01:07: MAE 5.03 FSC-147 test; exact-match is generation only (V)
arXiv 2605.18063 MixCount opened 01:07: exemplar sensitivity +0.13 MAE (+4.7%) (V)
github.com/facebookresearch/sam3 pyproject, README_TRAIN, RELEASE_SAM3p1 read 01:07: no GPL deps, single-GPU fine-tune config (V)
CLIP-EBC issues 11,8 and CountGD++ issue 6 read 01:08 (V)
arXiv 2607.06420 HoloCount opened 01:08: dense exact 20.0% open best, 49.0% Gemini 3.1 Pro (V); small subset numbers not read
arXiv 2604.20030 ACFamNet opened 01:08: MNAE metric, cardinality-classification prior (V)
arXiv 2604.05433 few-shot SAM3 opened 01:09: negative exemplars degrade frozen SAM 3 (V section 4.3); caveat added
arXiv 2508.14660 PerSense++ re-read in full 01:09: Table 4 mIoU 77.45/81.35, MAE 12.91/11.48 (V); earlier 'no count metric' was the older version
arXiv 2511.12588 CountIHC read in full 01:09: n=4 bins, WM 6.1->5.8 and 23.1->21.3 vs CLIP-EBC (V)
gh api license PerSense and CountZES read 01:09: both PolyForm Noncommercial 1.0.0 (V)
gh search iMoonLab/yolov13 licence 01:10: agpl-3.0 (V)
arXiv 2512.16415 CountZES tail re-read 01:10: 2.3 s/img (V), limitation under domain shift (V)
RECOUNT, HieraCount tables re-read and GeCo2 LICENSE read 01:10: S->V, GeCo2 MIT file
arXiv 2309.05277 ICACount re-read 01:10: per-iteration time <1 s each (V), earlier 4 s corrected; limitation: range not exact count
arXiv 2405.20459 Table 5 re-read and fiveai/detection_calibration LICENSE read 01:11: D-ECE 12.8->0.9 PS, AP 44.1 unchanged (V); repo CC BY-NC-SA
WebSearch Poisson-binomial counting and count abstention 01:11: nothing for detector counts; ECCV 2022 PMB set prediction pointer (S)
ECCV 2022 Hess et al. probabilistic set prediction read in full (PDF via pypdf) 01:12: MB/PMB density, no count accuracy (V)
arXiv 1805.10548 Deep Watershed Detector read in full 01:12: pretrain DeepScores, fine-tune MUSCIMA++ 110 pages; AP only (V). OMR 2025-26 search snippets only (S)
HF API cards nikigoli/CountGD and CountGDPlusPlus 01:13: license mit, not gated (V); GeCo2 repo LICENSE MIT
final consistency pass 01:13: no home paths, sections 0-7 intact
