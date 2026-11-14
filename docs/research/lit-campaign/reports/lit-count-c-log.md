# lit-count-c reading log (one line per source opened; date read 2026-11-14)
- gh api licence+pushed_at for 15 counting repos (CountGD MIT, DAVE MIT, GeCo MIT, LOCA MIT, CounTR MIT, PET MIT but README "academic only", P2PNet academic-only text, T-Rex IDEA License non-commercial, SAM3 SAM License, molmo/moondream/Qwen3-VL Apache-2.0): licence bits
- https://github.com/facebookresearch/sam3 LICENSE (via gh api): SAM License text, 2025-11-19
- https://huggingface.co/facebook/sam3 : gated, README not readable without login
- https://github.com/IDEA-Research/T-Rex LICENSE: IDEA License 1.0, non-commercial research
- https://github.com/TencentYoutuResearch/CrowdCounting-P2PNet LICENSE: academic research only
- https://github.com/cxliu0/PET README: "Permission: academic purposes only", despite MIT file
- https://github.com/niki-amini-naieni/CountGD README: weights Google Drive 1.2GB, needs GroundingDINO Swin-B + SAM ViT-H, 26 min FSC-147 test on one RTX 3090
- https://github.com/jerpelhan/GeCo README: GeCo2 is the recommended successor
- https://github.com/jerpelhan/GECO2 + arxiv 2511.08048 (AAAI 2026): Table 1,2,3,5 numbers; 4.98 GB inference memory on A100
- https://arxiv.org/html/2505.16778 (URM, 2025): cross-dataset single-domain generalisation numbers, MAE 21-30 on shift
- https://arxiv.org/html/2407.04619 (CountGD): threshold sigma=0.23, k=900 queries, CARPK MAE 3.68
- https://arxiv.org/html/2511.16719 (SAM 3, full text via pwfetch): counting protocol conf>0.5 + NMS IoM 0.5; limitations; Table 37
- https://arxiv.org/html/2512.23351 (CountGD++, v2 2026-05-30, pwfetch full text): pseudo-exemplars FSCD-147 text-only MAE 16.55->10.29 RMSE 129.8->33.5; CARPK MAE 2.48; repo MIT (gh api), weights 1.25 GB Google Drive, no weights licence
- https://arxiv.org/html/2602.19432 (CountEx 2026-02), 2601.13871 (OCCAM 2026-01), 2603.15470 (stacked counting 2026-03): abstracts+skim; CountEx exclusion prompts, OCCAM training-free SAM, stacked = 3D, off-shape
- https://api.semanticscholar.org/graph/v1/paper/arXiv:2407.04619/citations: 100 citing papers listed, 2025-2026 ones triaged
- https://arxiv.org/html/2404.03507 (DQ-DETR ECCV24) + https://arxiv.org/html/2204.05276 (Poisson-binomial lesion counting, MIDL 2022): read
- https://github.com/facebookresearch/sam3 LICENSE full text read: SAM License (custom, royalty-free limited, no commercial ban, ITAR/military carve-outs, acknowledge in publications); HF facebook/sam3 api: gated manual, license:other. SA-Co/EXT pool list (Table 25 in arxiv 2511.16719): includes FSC-147, VisDrone, HierText, no CubiCasa; HQ web pool MetaCLIP unknown
- gh issues: GECO2 #5 (MIT stated by author; LICENSE file MIT; training code asked #1,#10,#11, README has FSCD147 retrain), CountGD #40/#52 (custom finetune instructions promised, not given), CountGDPlusPlus #6 (full training code released, README Training section); CountGD++ README: gcc11 + CUDA toolkit + detectron2 + custom deformable ops build
- arxiv 2605.02752 (PrACo++, 2026-05), 2607.16826 (UpCount 2026-07), 2608.20621 (RECOUNT 2026-08), 2605.30846 (Count Anything/CLOC 2026-05; domains: general, remote sensing, histo, cell, agri, micro; no drawings) read via pwfetch
- https://arxiv.org/html/2502.10677 (FocalCount: counters count all objects regardless of prompt) read; https://openaccess.thecvf.com/.../Owusu_SAM3Count...paper.html abstract only (PDF 403): SAM3Count CVPRW 2026, adaptive ROI tiling; AECV/web search for SAM3 on floor plans: nothing; FSC-147 avg count 56, min 7 (PMC10098187 snippet)
- https://huggingface.co/nikigoli/CountGDPlusPlus README+api (CVPR 2026 model card): license mit, 233.9M params, one-file safetensors, count() API with exemplar boxes from another image, pure-PyTorch fallback without compiled kernels
- licence via gh: Joan947/SAM3Count MIT (pushed 2026-07-29); cvlab-stonybrook/LearningToCountEverything (FSC-147) MIT code; segment-anything Apache-2.0; GroundingDINO Apache-2.0, its README lists pretrain data O365, GoldG, Cap4M, OpenImage, ODinW, RefCOCO
- https://huggingface.co/datasets/jerpelhan/geco2-assets: no card (README missing), weights licence unstated
- https://www.tandfonline.com/doi/full/10.1080/08839514.2024.2406712: blocked by site (empty); only search record seen (RGU, few-shot symbol detection engineering drawings, CC)
- https://api.semanticscholar.org/graph/v1/paper/arXiv:2511.16719/citations (500 citing, read 2026-11-14): forward walk from SAM 3; picked 2611.10092, 2610.39396, 2610.14651, 2611.05398
- https://arxiv.org/abs/2611.10092 (SNAP, 2026-11-06): SAM 3 kappa 0.038 on look-alike classes vs per-project head on frozen proposals 0.754 (60 labelled imgs), 20 imgs beat SAM3 oracle on 5 microscopy sets
- https://arxiv.org/abs/2610.39396 (CASE, 2026-10-29): frozen SAM 3 does not treat negative exemplars as exclusion evidence; LoRA fix
- https://arxiv.org/abs/2610.14651 (TAG, 2026-10-10): SAM3 bottleneck is concept recognition not masks
- https://arxiv.org/abs/2611.05398 (AgentCount, 2026-10-16): SAM 3 + text prompts + morphology filter for colony counts, 97.6% agree within 0.01 log10 on endpoints (not per-image exact)
- https://arxiv.org/html/2104.08391 (FamNet/FSC-147, full via pwfetch): avg 56 objects, min 7, max 3701, avg image 774x938; https://arxiv.org/html/2407.04619 re-read: CountBench MAE 0.86 RMSE 3.1 (text only, 504 imgs), sigma grid 0.23, trained on >=7 objects/image
- https://arxiv.org/html/2602.11024 (CoLSR surgical instrument counting, WACV 2026, full via pwfetch): counts 7-49, fine-tuned baselines MAE CountGD 7.84, DQ-DETR 4.24, REC 2.82, CoLSR 0.88; arxiv search page for 'CountGD++' (3 results) as forward walk fallback; S2 429 twice
- https://arxiv.org/html/2404.16622 (DAVE, full via pwfetch): verification stage rejects outliers; mixed-class ablation LOCAmul -43% on multi-class, +28% on FSC147
- https://arxiv.org/html/2604.20030 (ACFamNet Pro, 2026-04, full via pwfetch): small clustered colonies MNAE 9.64%, RoI Align note
- WebSearch (results only, not opened): NMS in crowds (arXiv 2012.03544, 2012.06785); count-guided detection searches; no direct source for NMS undercount
- gh issues: GECO2 #22 (howmany Android app, int8 ONNX, MAE 4.59 on 100 FSC-147 test images, 66% within 10%), #17 (CPU untested); CountGD #11 (training VRAM answer is a screenshot, unreadable); DAVE #6 CUDA OOM
- https://huggingface.co/docs/transformers/model_doc/sam3: 1008 px intended, image_size config lowers memory, accuracy may degrade
- https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1911589/full (FloorYOLO, 2026-09-15): header + table list only; L1/L2 pointer
- https://arxiv.org/search/?query=GeCo2 + api.semanticscholar.org citations of 2511.08048 (8 citing, 2026-11-14): forward walk from GeCo2; picked AgriCountDINO 2609.29460; BC-GECO2 and sticky-trap ensembling seen as titles only
- https://arxiv.org/html/2609.29460 (AgriCountDINO, full via pwfetch): 8.4M trainable, DINOv3 frozen, exemplar-adaptive point NMS, 3-shot MAE 11.92
- https://huggingface.co/api/models/facebook/dinov3-vitb16-pretrain-lvd1689m + gh dinov3 LICENSE: DINOv3 License (custom), gated manual
- https://arxiv.org/html/2608.23845 (counting survey 2026-08, full via pwfetch): exact-match vs compensating errors; ValidCounter, GroundCount as survey-level mentions only
- https://arxiv.org/html/2603.10978 (GroundCount, 2026-03, full via pwfetch): PhD benchmark yes/no VQA, detector+VLM 81.3%; L7 pointer only. ValidCounter: no source found by search
- https://arxiv.org/html/2607.02139 (AdaCount, 2026-07, full via pwfetch): head-to-head table FSC-147/CARPK/OmniCount; SAM3 dense undercount; https://arxiv.org/abs/2606.17601 (Dual-TTT, 2026-06, abstract: corruptions rain/fog, not drawings) and 2605.10887 (HieraCount/KubriCount, 2026-05, abstract) read
- https://huggingface.co/nikigoli/CountGDPlusPlus/raw/main/countgdpp.py + config.json: short side 800/max 1333, CONF_THRESH 0.23, Swin-B 384, roi_align exemplars
- https://arxiv.org/html/2104.08391 re-read: Table 2 detectors vs FamNet; section 3.3 test-time adaptation losses
- https://arxiv.org/html/2512.16415 (CountZES, 2025-12 v4 2026-10, full via pwfetch): exemplar choice sensitivity, 3-stage inference-only exemplar discovery; https://arxiv.org/abs/2609.07939 (repeated elements single-image, ECCV 2026, abstract: FSC-147 116 imgs, qualitative)
- HF api/cards: allenai/Molmo2-4B (apache-2.0, 4.85B), moondream3-preview (BSL 1.1 + no-third-party-service grant), Qwen3-VL-4B-Instruct (apache-2.0, 4.44B), MolmoE-1B (apache-2.0); gh allenai/molmo2 Apache-2.0
- https://arxiv.org/html/2505.16778 re-read via pwfetch: Table 6 in-domain DAVE 8.91/8.66 verified
- https://github.com/facebookresearch/sam3 README (raw): py3.12, CUDA>=12.6, gated checkpoints, sam3/train exists, SAM 3.1 released 2026-03-27 (HF facebook/sam3.1 gated, license other); https://github.com/Joan947/SAM3Count README: full-image pass then ROI-guided adaptive tiling for dense scenes, fine-tuning code 'soon'
- https://openaccess.thecvf.com/content/ICCV2025/html/Liu_CountSE... (CountSE ICCV 2025, abstract page): soft exemplars + clustering filter; gh search pppppz22/CountSE MIT (unconfirmed official)
- https://github.com/Mengqi-Lei/awesome-object-counting README (raw, triage list for CVPR 2026/ICCV 2025 counting papers; secondary source, used only to pick papers) ; https://arxiv.org/html/2510.02213 (multi-class density, full via pwfetch; repo LCAS/gnr_mcdest no licence file)
- https://arxiv.org/abs/2603.16129 (QICA CVPR 2026) and https://arxiv.org/abs/2602.12774 (WS-COC ICLR 2026; gh Apache-2.0) abstracts
- https://arxiv.org/html/2407.04948 (VA-Count ECCV 2024, via pwfetch): exemplar discovery by Grounding DINO + noise suppression
- https://arxiv.org/html/2511.08048 (GeCo2) re-read via pwfetch: Table 5 memory/time verified (4.98/15.47/25.33/23.83 GB), text says 0.4 s average vs table 0.2
- https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13416764/fullTextXML (industrial counting review, Sensors 2026; PMC page itself empty): NMS suppresses adjacent true objects sentence; no exact-match numbers
- https://arxiv.org/html/2407.04619 appendix re-read: SAM TT-Norm self-similarity fix (Fig 6), shortest side 800 at inference
- https://arxiv.org/html/2311.03570 (Cal-DETR, via pwfetch): D-ECE precision vs confidence only, temperature scaling baseline; gh search akhtarvision/cal-detr Apache-2.0
- (no new source; synthesis table section 7 written)
- https://arxiv.org/abs/2510.04401 (VLMCountBench 2025-10) and https://arxiv.org/abs/2604.10039 (Counting to Four, 2026-04): abstracts; mixed shape types fail
- https://github.com/facebookresearch/sam3/issues/251 (fine-tune OOM, RoPE hard-coded 1008) and gh issue searches (floor plan/technical drawing/diagram/CAD: nothing relevant)
- gh issue searches on CountGD/CountGDPlusPlus/GECO2/GeCo (titles only: #30 900-object limit, #40/#52 custom dataset, GeCo #16); GitHub search API rate-limited at 00:44, stopped using gh search
- https://arxiv.org/html/2504.16570v3 (CountingDINO WACV 2026, full via pwfetch); gh repo view lorebianchi98/CountingDINO: no licence; gh dinov2 and dino Apache-2.0; https://arxiv.org/abs/2610.10396 (GDSNet NeurIPS 2026, crowd; skipped); PyPI json: deeplake 3.9.52 MPL-2.0, others permissive; S2 citations of 2512.23351 (16, read 2026-11-14); OpenAlex budget exhausted (key needs the owner's email, not used)
- https://arxiv.org/html/2508.06585v2 (CountQA, exact match 42.9% best of 15 MLLMs) and https://arxiv.org/html/2607.06420v1 (HoloCount, exact match, 20+ MLLMs): read via pwfetch for the exact-match gap; WebSearch Poisson-binomial detector (retry): only a patent, no paper
- https://arxiv.org/html/2505.10737 (Salvin's albatross aerial counts, 2025-05, via pwfetch): leave-one-island-out, 29.25% false positives, 19.3% missed; WebSearch floor-plan detector counting retry: nothing new
- https://github.com/Joan947/SAM3Count README (raw, full): presence score off, fine-tune via SAM3 README_TRAIN.md; gh repo view jbr97/URM: no licence file; SAM3Count PDF still ERR_ABORTED via browser (blocked)
- gh repo view hoiliu-0801/DQ-DETR (link from arXiv 2404.03507 html): no licence file
- WebSearch pill and PCB counting (results only; vendor claims; arXiv 2503.20516 fetched = small object detection survey, L2, not used)
- https://github.com/facebookresearch/sam3 README_TRAIN.md (raw): Hydra, single GPU possible, no VRAM figure
- https://arxiv.org/abs/2611.06143 (PTQ4SAM3), 2610.27960 (DCR-SAM), 2610.07802 (Western bluebird benchmark): abstracts, SAM 3 forward walk
- https://arxiv.org/html/2611.10092 (SNAP) full text via pwfetch: no code link; annotation pipeline on SAM2.1 proposals
- https://arxiv.org/html/2601.13871 (OCCAM) re-read via pwfetch: SAM2 grid + FINCH clustering, Table 2 CountingDINO 1-shot 37.73 vs 3-shot 20.93; code promised on project page
- https://arxiv.org/html/2512.23351 Tables 2-3 re-read: negative prompts BloodCell MAE 11.56->1.73, OmniCount fruits 2.41->0.41, PrACo NMN 0.88->0.07
- HF card nikigoli/CountGDPlusPlus: exemplar_image parameter for external exemplars; paper Table 1: t+p 10.29 -> t+p+s 8.39
- https://arxiv.org/html/2605.30846 (Count Anything, full via pwfetch): SAM3 frozen + LoRA, 848.6M params, inference 5.17-6.53 GB, CLOC MAE 9.34 vs SAM3 25.80; gh Mengqi-Lei/count-anything Apache-2.0; also CountEx repo github.com/bbvisual/CountEx, UpCount repo r28112072-rgb/upcount, RECOUNT H100 single epoch (links only)
https://github.com/niki-amini-naieni/CountGD/issues , 2026-11-14 , 30 issues: no fine-tune recipe, threshold fix for false positives, unstable counts on dense frames
https://github.com/jerpelhan/GeCo2/issues/5 , 2026-11-14 , author states MIT code, SAM2 parts Apache 2.0; weights not separately addressed
https://arxiv.org/html/2512.23351 (training section) , 2026-11-14 , trained on FSC-147 + 1000 mosaics, no GPU-hours stated, no fine-tune on eval sets
https://arxiv.org/abs/2605.10887 , 2026-11-14 , abstract: multi-grained counting, HieraCount, KubriCount synthetic; prompt-following fails on fine grain
https://api.semanticscholar.org citations of 2512.23351 , 2026-11-14 , 16 citing papers, all 2025-2026
https://arxiv.org/abs/2605.18063 , 2026-11-14 , abstract: MixCount synthetic mixed-object benchmark
https://arxiv.org/abs/2606.23835 , 2026-11-14 , abstract: ABACUS 3B unified counting+generation model
https://huggingface.co/api/models?search=hieracount , 2026-11-14 , no results
https://github.com/jerpelhan/DAVE/issues , 2026-11-14 , 27 issues: no own-data recipe, open memory and training-stall reports; licence MIT per API
https://arxiv.org/html/2512.23351 Table 1 , 2026-11-14 , re-read: FSCD-147 test text-only MAE/RMSE/AP: ours 16.55/129.76/33.01, +pseudo-exemplars 10.29/33.52/37.78, +synthetic 8.39/27.03/38.93; all confirm report numbers
https://arxiv.org/html/2511.16719 Table 3 , 2026-11-14 , re-read: CountBench acc 93.8 / MAE 0.12, PixMo-Count 86.2; matches report
https://arxiv.org/html/2511.08048 Table 1 , 2026-11-14 , re-read: GeCo2 test MAE 7.64 RMSE 39.4 AP 46.81, 4.98 GB, 0.2 s; matches report
https://arxiv.org/abs/2603.00595 , 2026-11-14 , abstract: UNICBench MLLM counting benchmark, 45 models, CVPR 2026; protocol only
export.arxiv.org title search CountScope , 2026-11-14 , not found
https://arxiv.org/html/2608.20621 , 2026-11-14 , full read: RECOUNT, frozen CountGD + 1.2M-param head, 1 epoch H100, photos only, no code link found
https://arxiv.org/html/2602.19432 , 2026-11-14 , full read: CountEx inclusion+exclusion counting, CoCount data, photos, MAE only, no code link found
export.arxiv.org title search UpCount , 2026-11-14 , not found
export.arxiv.org API, 3 queries for exact-match and calibrated count distribution on detectors , 2026-11-14 , nothing relevant
https://github.com/niki-amini-naieni/CountGDPlusPlus (README, requirements, issues 1-9) , 2026-11-14 , MIT; SAHI tiling script; training code on Drive; no AGPL/GPL deps
https://github.com/niki-amini-naieni/CountGD requirements.txt + jerpelhan/GeCo2 install.sh , 2026-11-14 , pins and CUDA op compile; no AGPL/GPL
https://ar5iv.labs.arxiv.org/html/2308.13814 , 2026-11-14 , PET full text: SHA MAE 49.34, SHB 6.19, UCF-QNRF 79.53; arxiv.org/pdf failed (ERR_ABORTED)
https://arxiv.org/html/2601.13871 , 2026-11-14 , OCCAM full text re-read: SAM2 grid + threshold FINCH clustering; FSC-147 style tables; abstract-only mark removed
https://arxiv.org/abs/1901.04355 , 2026-11-14 , abstract: iterative DL stereology with human verification, count error ~3% -> <1% after 5 rounds
export.arxiv.org API, 4 queries on interactive/human-in-the-loop counting , 2026-11-14 , nothing else relevant
https://ar5iv.labs.arxiv.org/html/2204.05276 , 2026-11-14 , re-read: acc 87.6/F1 67.3, multitask 88.7; footnote says code exists, URL not shown; guessed repos 404
https://arxiv.org/html/2611.10092 , 2026-11-14 , re-read: SNAP F1 0.484 vs 0.441, kappa 0.038 vs 0.754; matches report; no code link in text
https://arxiv.org/abs/2012.03544 , 2026-11-14 , abstract: NMS-free end-to-end FCN detector (POTO label assignment), code linked
https://arxiv.org/abs/2012.06785 , 2026-11-14 , abstract: DETR worse than Faster R-CNN on crowd pedestrians, new decoder
https://arxiv.org/html/2611.05398 , 2026-11-14 , full read: AgentCount 57 plates, 86.0% countability class correct, 89.7% within 10% on 29 countable, 33.5 s/img on RTX 3060
https://arxiv.org/html/2510.04401 , 2026-11-14 , full read: VLMCountBench exact-correct accuracy; Qwen2.5-72B 0.60 level 1 -> 0.45 level 3; synthetic shapes
https://arxiv.org/html/2604.10039 , 2026-11-14 , full read: MAS gain <=1%, CountingTricks most of 10 VLMs <50%, patch-intersection worst case
https://arxiv.org/html/2603.16129 , 2026-11-14 , full read: QICA FSC-147 12.41/97.28, CARPK 6.07, A800 80GB
https://arxiv.org/html/2602.12774 , 2026-11-14 , full read: WS-COC L20 GPU batch 4, range-judging dialogue, MAE only
https://github.com/Joan947/SAM3Count README results table , 2026-11-14 , FSCD-147 test MAE 19.80 zero-shot / 13.02 fine-tuned; consistent with the 19.80 quoted from the Count Anything paper
https://arxiv.org/abs/2601.04819 , 2026-11-14 , abstract: AECV-Bench 120 floor plans exact-match door/window counting 0.40-0.55 for MLLMs; HTML not available
export.arxiv.org API, 3 gap queries , 2026-11-14 , only AECV-Bench
https://arxiv.org/html/2603.15470 , 2026-11-14 , full open: stacked-object counting, counts 19-20063, MAE, 3D occupancy; no change
https://huggingface.co/api/datasets/jerpelhan/geco2-assets , 2026-11-14 , no card or licence tag; 2 checkpoints + prebuilt deform-attn wheels
https://huggingface.co/api/models/nikigoli/CountGDPlusPlus , 2026-11-14 , licence mit; safetensors + code + example in the repo
https://huggingface.co/nikigoli/CountGDPlusPlus README + example.py , 2026-11-14 , one-line pip install, optional CUDA kernels, pseudo-exemplars and adaptive cropping not in count()
https://arxiv.org/html/2511.08048 Table 1 , 2026-11-14 , re-read: FSCD147 test MAE CountGD 8.35, DAVE 10.45, GeCo 7.91, GeCo2 7.64, LOCA 10.79; row 5.74 is from the CountGD paper's own label set
https://arxiv.org/html/2407.04619 Table , 2026-11-14 , re-read: CountGD test MAE 5.74 (starred, corrected), CARPK 3.68, CountBench text MAE 0.86; matches
https://api.github.com repos IDEA-Research/GroundingDINO, microsoft/Swin-Transformer; HF google-bert/bert-base-uncased, IDEA-Research/grounding-dino-base , 2026-11-14 , Apache-2.0 / MIT / Apache-2.0 / Apache-2.0
https://github.com/cvlab-stonybrook/LearningToCountEverything README + licence , 2026-11-14 , MIT code; no data terms stated in README
https://github.com/facebookresearch/sam3 issues 460 505 511 + model_builder.py , 2026-11-14 , 200 detector queries, res 1008; CountBench eval script not published; video OOM on 24GB
https://github.com/niki-amini-naieni/CountGDPlusPlus cfg_app.py , 2026-11-14 , 900 queries, no NMS, box_threshold 0.23
https://huggingface.co/nikigoli/CountGDPlusPlus/raw/main/countgdpp.py , 2026-11-14 , count(): conf_thresh, external exemplar images, negative texts/boxes; returns count, boxes, scores
https://arxiv.org/html/2607.16826 , 2026-11-14 , full read: UpCount reference-free density counter FSC-147 test MAE 12.39 / RMSE 100.89, CARPK 6.27
https://api.semanticscholar.org citations of 2504.16570 , 2026-11-14 , 8 citing papers
https://arxiv.org/abs/2609.40230 , 2026-11-14 , abstract: EviRover agentic perception (4B), cites CountingDINO but is a general perception agent; off scope
https://arxiv.org/abs/2501.19184 , 2026-11-14 , abstract: CAC survey (CVIU), taxonomy reference-based / reference-less / text-guided; no drawings
https://api.semanticscholar.org citations of 2204.05276 , 2026-11-14 , 3 citing papers, none using the count distribution on detectors
https://arxiv.org/html/2506.21486v2 , 2026-11-14 , opened: marked point process detector, expected centre count instead of NMS, empty-area probability; no exact-count numbers read
WebSearch calibrated detector count distribution , 2026-11-14 , no direct hit
