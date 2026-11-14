# lit-detect-b reading log (one line per source opened; date = 2026-11-14)
- https://arxiv.org/html/2505.05741v2 (Dome-DETR, MM'25) read in full via web-fetch: Tables 1-9 AI-TOD-V2/VisDrone, density queries, 8 GPU training, no train time.
- https://github.com/RicePasteM/Dome-DETR README + LICENSE via licence via gh: Apache-2.0 code, checkpoints on HF "academic only", issues #41 slow convergence, #50 DeFE reg loss defunct (open).
- https://huggingface.co/RicePasteM/Dome-DETR raw README: weights "academic research only".
- https://arxiv.org/abs/2110.13389 + ar5iv (NWD, ISPRS): AI-TOD Table 1/4 numbers, tiny = <16px, NWD in assign/NMS/loss.
- https://ar5iv.arxiv.org/html/1904.00853 (SKU-110K, CVPR19): Table 1/3/4: 147 obj/img, AP .492, MAE 14.5; tail of page was a summary.
- https://arxiv.org/html/2409.00316v1 (OMR YOLOv8l on MUSCIMA++): 3500x2000 pages, 1216 crops ->640, mAP 84.8/85.7/94.2.
- https://huggingface.co/dimtri009/rfdetr-pid-detector model card: RF-DETR base + SAHI 1280/20%, self-reported mAP50 99.96, 10 epochs.
- https://arxiv.org/html/2411.13929v3 (PID2Graph, DSAA'25): patch 1500 overlap>=50%, symbol mAP50 76.99-83.95 stitched.
- https://github.com/Intellindust-AI-Lab/DEIMv2 LICENSE.md: non-commercial only (read). DEIM LICENSE: Apache-2.0 (read).
- https://github.com/facebookresearch/dinov3 LICENSE.md: custom Meta licence (header read).
- gh api license: obss/sahi MIT, stardist BSD-3, cellpose BSD-3, mmdetection Apache-2.0, mmrotate Apache-2.0, mmyolo GPL-3.0, roboflow/rf-detr Apache-2.0, Peterande/D-FINE Apache-2.0, yvan674/obb_anns BSD-3.
- FAILED: YOLSO pdf (binary), DeepScoresV2 zhaw host (DNS), Petitpierre pdf (>10MB), Mainz landslide (Anubis block), Masala-CHAI pdf (binary). Retry with pwfetch.
- https://eprints.whiterose.ac.uk/198859/1/_ICDAR_YOLSO.pdf (YOLSO, ICDAR'23) fetched with curl, text via pypdf, read sec 4: 22,882 points, 4k x 4k maps, 642 px crops, point mAP@0.5 97.9 vs YOLOv3 43.6 / Faster R-CNN 70.2.
- https://github.com/waps101/YOLSO README + licence API: GPL-3.0 code (idea only); centre-only CSV labels; last push 2025-06-30.
- https://www-users.york.ac.uk/~waps101/publication/smith2023yolso/ (pwfetch): abstract, fixed-size symbol assumption, no-padding FCN.
- DeepScoresV2 ICPR'20 pdf (digitalcollection.zhaw.ch bitstream, curl + pypdf) read: Table I/IV, DWD vs HRNet Faster R-CNN, stems AP 0.013, "InSpace/OnLine" notehead split, DWD cannot detect same-centre objects.
- https://zenodo.org/record/4012193 (pwfetch): DeepScoresV2 CC BY 4.0, 255,385 images, dense subset 1,714; code repos tuggeluk/*; yvan674/obb_anns BSD-3.
- https://wp.unil.ch/llist/files/2026/07/petitpierre.pdf (curl 13 MB, pypdf): 5-page extended abstract, CaSiDD 18,750 labels/796 patches, YOLOv10-X P 81.1 R 41.5, class-agnostic.
- https://arxiv.org/html/2411.14299v5 (pwfetch, Masala-CHAI): YOLOv8 640x640 4,300 diagrams 12 classes, deep Hough line priors for nets, no detector mAP given.
- https://github.com/RicePasteM/Dome-DETR/issues: #41 slow convergence, #50 DeFE loss defunct.
- https://hal.science/hal-04268139v2/document (Yesilkanat et al., DAS 2024, full-page OMR detectors) curl+pypdf: Tables 1-7; full-page vs crop; DINO + random crops collapses; Cascade R-CNN FocalNet-B best; 4 GPUs A100/V100.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/ (DSC, Sensors 2026 railway drawings) Europe PMC XML: 768 px patches, 57 drawings, RF-DETR-Seg-L, F1 .9226, code and data private.
- OpenAlex API (api.openalex.org): citers of Dome-DETR (44), YOLSO (4), NWD (570, filtered), Yesilkanat (3). Semantic Scholar 429 (curl and pwfetch).
- https://arxiv.org/abs/2511.19538 (pwfetch): Petitpierre PhD thesis EPFL, 63M signs, synthetic data; abstract only.
- https://arxiv.org/html/2409.16496 (RT-DETR waste PCB): V-PCB 1920x1080, 65 boards, 3,682 instances, RT-DETR-L 6.85 h / 300 epochs on Quadro RTX 5000 16 GB.
- https://arxiv.org/html/1806.03535v2 (StarDist) and biorxiv 2025.04.28.651001v1 (Cellpose-SAM) via web-fetch: touching nuclei; Cellpose README: models trained on CC-BY-NC data.
- https://arxiv.org/html/2507.00825v3 (HEDS-DETR, UAV) + abs 2502.07194 (de-homogenized queries): no code, CrowdHuman/VisDrone numbers only.
- https://github.com/roboflow/rf-detr README: all RF-DETR-Seg sizes Apache-2.0 (read), XL/2XL/Atto-Pico PML.
- https://github.com/RicePasteM/Dome-DETR configs (dome yml, dataloader): stride-4 level in feature_strides [4,8,16,32], 800x800, RandomIoUCrop+Mosaic, total_batch_size 8, 160 epochs.
- https://www.cs.rit.edu/~rlaz/files/dissertation_kwon-young_choi.pdf (curl+pypdf), Table 2.6/2.7: Faster R-CNN with vs without staff lines, mAP 85.12 vs 87.80 (71 classes), per-class AP almost equal; author: staff removal "no longer significant", staff lines synthetic.
- https://github.com/facebookresearch/dinov3 LICENSE.md grant clause read: custom licence, royalty-free incl. commercial with conditions (ITAR/military exclusions).
- PMC13709312 (DSC) second pass: Tables 5-12: duplicates without merge (P .345, FP 3,206), overlap sweep 0/20/25/50% F1 .9176/.9226/.9147/.9169, RandomShift +2.5 Box AP, Copy-Paste +3.0 Box AP and rare class .25 -> .62, YOLO11-seg-L Box AP .7228 vs RF-DETR-Seg-L .6336.
- https://arxiv.org/html/2604.16513 (SynthPID, CVPRW 2026) via web-fetch: 665 synthetic, 12 real seeds, node mAP@.5 64.2 synth-only vs 67.8 oracle vs 71.3 mixed; 1500 px patches stride 750.
- https://arxiv.org/abs/2603.09411 (RiO-DETR, pwfetch): ECCV 2026 oriented DETR, DOTA; abstract read only.
- https://raw D-FINE configs/dfine/include/dfine_hgnetv2.yml + README (gh api): stock strides [8,16,32], 3 levels, 300 queries, S = 25 GFLOPs at 640.
- OpenAlex abstracts: DRMNet (TGRS 2026) and UHR-DETR (TGRS 2026): abstract only, aerial, not ranked.
- search listings only (not opened, not ranked): SCD-Det (J Real-Time Image Proc 2026), P2-head YOLO papers (LibreYOLO9P2s card, DroneScan-YOLO): no RT-DETR P2 ablation found.
- https://github.com/roboflow/rf-detr src/rfdetr/config.py (gh api, read): detection N/S/M/L patch_size 16 (Base 14), one level projector_scale ["P4"], resolutions 384/512/576/704; Seg models patch 12, 312-768 px; num_queries 100-300.
- https://arxiv.org/pdf/1612.04402 (Finding Tiny Faces, curl + pypdf): Sec 3.2 up-sampling 2x: 69% -> 75%; <40 px objects use 2x resolution.
- https://arxiv.org/pdf/1711.08189 (SNIP, curl + pypdf): Table 2 small-object AP 16.3 / 19.5 / 21.4; up-sample 2x better than halving stride.
- https://arxiv.org/abs/2607.18997 (EC3 2026, AEC drawing layout benchmark; pwfetch abstract + curl/pypdf PDF): FELD 551 drawings; RF-DETR-M mAP50:95 .890 vs Faster R-CNN .779 vs YOLOv12-M .755 vs DocLayout-YOLO .589; T4 GPU.
- https://github.com/MuhammadAli013/Electrical-Symbol-Detector-for-Construction-Plans README (gh api): YOLOv8 (AGPL), legend-cropped synthetic training, review UI; no numbers; last push 2026-11-04.
- search listing only (not opened): Applied AI 2025 attention-YOLOv8 electrical diagrams (640 tiles; RT-DETR cheaper but more memory), LED-BENCH 2610.19571, Enginuity 2606.03410.
- https://arxiv.org/pdf/2508.10449 (SkeySpot, Aug 2025; curl + pypdf): DELP 45 plans / 2,450 instances / 34 classes; YOLOv8 mAP50 81.12 vs Faster R-CNN 48.62; per-class Table III.
- https://api.openalex.org abstract of IJDAR 2024 construction diagrams (10.1007/s10032-024-00492-9): YOLO 79 / Faster R-CNN 83 mAP; Springer page and PDF behind a JS client challenge (not bypassed). Anubis wall at openscience.ub.uni-mainz.de (not bypassed).
- search listing only: ICDAR 2025 sweep (no small-symbol paper found), Symmetry 2025 railway catenary (MDPI blocked), comparative study technical drawings 2023 (symbols 20-300 px, not opened).
- https://arxiv.org/pdf/2511.09554 (RF-DETR, ICLR 2026; curl + pypdf): Table 4 RF100-VL AP_S: YOLO 5-7 vs DETRs 30-38; D-FINE-S 36.6 vs RF-DETR-S 34.2; higher resolution helps small objects; D-FINE "underperforms RT-DETR on test" attribution to COCO tuning.
- LICENSE files read via gh api contents: Dome-DETR, D-FINE, rf-detr (Apache-2.0), NWD (Apache-2.0), mmdet-rfla (MIT), sahi (MIT), stardist (BSD-3), YOLSO (GPL-3.0).
- https://github.com/Peterande/D-FINE README lines 136-137 + HF card Peterande/D-FINE (apache-2.0): Objects365 checkpoints carry a "not commercially cleared" warning.
- https://arxiv.org/abs/2208.08738 (RFLA, ECCV 2022; pwfetch abstract) and gh licence MIT.
- blocked/unread: books.fupress.com 403 (comparative study technical drawings 2023), Springer client challenge (IJDAR 2024), Anubis wall (Mainz), MDPI Akamai deny.
- https://arxiv.org/pdf/1805.10548 (Deep Watershed Detector, 2018; curl + pypdf): centre-energy detector, 960 px crops, AP@0.5 vs @0.25 (noteheadBlack .8619 / .9200); repo tuggeluk/DeepWatershedDetection MIT (gh api).
- https://digitalcollection.zhaw.ch/bitstream/11475/28719/1/2023_Tuggener-etal_Real-world-music-object-recognition_TISMIR.pdf (TISMIR 2023; curl + pypdf): ScoreAug on RealScores 36.0 -> 56.5 -> 73.7 AP@0.25; UDA 48.9; snapshot ensembles +5.2; S2A-Net; repo raember/s2anet no licence field.
- search listings only: hand-drawn diagram recognition (Mannheim thesis, arXiv 2401.03742), not opened, no touching-line result found.
https://arxiv.org/html/2505.20612 (RF100-VL, read 2026-11-14 via pwfetch): dataset list checked; Document group has activity-diagrams, circuit-voltages, all-elements etc.; no floor-plan or architectural set (V, by grep of the list).
https://arxiv.org/html/1904.00853 (SKU-110K, re-read in full 2026-11-14 via pwfetch): Table 3 confirmed, MAE base+NMS 24.962 (corrected from 24.98), EM-Merger 23.978 with RMSE 283.971, full 14.522; row upgraded R- to V.
https://arxiv.org/html/2411.13929v3 (PID2Graph, re-read 2026-11-14 via pwfetch): Table III stitched symbol mAP 76.99/74.15/83.95 confirmed (row 8 now V); Table A5 synthetic-only 26.67 vs mix 73.49 on real; Table A4 Dataset-P&ID at IoU .75 symbols 69.82 (modular) vs DigitizePID 92.50 (loose boxes).
https://github.com/roboflow/rf-detr/blob/develop/src/rfdetr/config.py (read 2026-11-14 via gh api): num_queries 300 det N-L, Seg N/S 100, M/L 200, XL 300; new note T15.
https://github.com/roboflow/rf-detr/issues/780 and /879 (read 2026-11-14 via gh api, comments in full): query cap, SAHI on dense tiles, ONNX vs TensorRT, no measured min object scale.
https://arxiv.org/pdf/2509.17283, 2508.07714, 2601.04819 (2026-11-14, WebSearch listing only, not opened, L1 pointers).
gh api licences 2026-11-14: supervision MIT, pyDeprecate Apache-2.0, ultrafast-pycocotools BSD-2-Clause, peft Apache-2.0, albumentations MIT; rf-detr pyproject.toml dependency lists read.
https://arxiv.org/html/2512.15098v2 (Uni-Parser, read 2026-11-14 via pwfetch): sentence on RT-DETRv2/YOLOv12/D-FINE training instability confirmed; new note T16. https://arxiv.org/html/2505.03777 (MolMole, opened, nothing on detectors; CC BY-NC-ND). MolMiner/MolDet via search listing only.
2026-11-14 retries of two looked-for gaps (exact counts; Sutty and Duménieu 2024): WebSearch standard, nothing new; recorded in section 4.
https://odr.chalmers.se/bitstreams/dc5af79f-7597-44db-b022-0c75d48f9210/download (Master's thesis 2026, symbol localisation in electrical diagrams; curl+pypdf 2026-11-14): Tables 4.2/4.3/4.4 read, note T17. Applied AI 2025 attention-YOLOv8 paper: publisher page not opened (paywall status unknown), search listing only.
https://github.com/RicePasteM/Dome-DETR/issues (read 2026-11-14 via gh api; issues 25, 28, 32, 35, 41, 50 with comments): training epochs, batch-size fix, open loss bug, large-object loss, speed; note T18.
https://arxiv.org/html/2608.14317 (MEP lighting symbols, Mask R-CNN, read 2026-11-14 via pwfetch): tiles 1000 px 20% overlap, bbox mAP .760; note T19. 
https://arxiv.org/html/2608.17237 (structural framing plans, training-free, read 2026-11-14 via pwfetch): Table 5 recall/precision; L1/L7 pointer; note T19.
OpenAlex forward-citation endpoint refused all list queries on 2026-11-14 ("free daily budget used up for this IP"); single-work lookup worked (RF-DETR paper: 140 citers). Citation walk for RF-DETR done by WebSearch instead (extended): no tiled-symbol paper found.
https://github.com/roboflow/rf-detr/issues/747, /958 and https://github.com/Peterande/D-FINE/issues/70 (comments read 2026-11-14 via gh api): resolution vs model size, Nano on small objects, dense-scene threshold; note T20.
https://github.com/dimitri009/STA (read 2026-11-14 via gh api): licence MIT, README and pipeline constants (SAHI 1280 px, overlap 0.2, confidence 0.75, Hungarian symbol-tag association); row 7 updated.
https://arxiv.org/html/2507.00825v3 (HEDS-DETR, read in full 2026-11-14 via pwfetch): Tables 2, 3, 7 read; row 13 R to V; VisDrone D-FINE 43.6 / DEIM 45.6 AP50 at 640 px.
https://www.biorxiv.org/content/10.1101/2025.04.28.651001v1.full (Cellpose-SAM, full text read 2026-11-14 via pwfetch): error rate .163 vs Cellpose3 .292 confirmed (a rate, not AP50; wording fixed); inter-annotator .257; 256 px crops; row 11 V.
https://arxiv.org/html/2603.09411 (RiO-DETR, full text read 2026-11-14 via pwfetch): oriented DETR, DOTA-1.0 AP50 78.4 (n, 2.7 ms); not needed for rot90-only plans; unranked.
https://roboflow.com/blog/pid-symbol-detection (read 2026-11-14 via pwfetch): RF-DETR Small, 3,800 images, 11 classes, mAP50 99.2 on validation, vendor text (R); note T21. https://arxiv.org/html/2512.22454 opened, aerial substations, covered by detect-a, no new line.
Europe PMC search 2026-11-14 for the Symmetry railway catenary and station signal layout papers: no indexed full text; stay abstract/listing-only (MDPI wall not bypassed).
https://arxiv.org/html/2404.03507v5 (DQ-DETR, full text read 2026-11-14 via pwfetch): count-class queries, AI-TOD-V2 AP 30.2 vs 25.9; both code repos have no licence (gh api); note T22.
https://www.researchsquare.com/article/rs-11390432/v1 (SAF-RTDETR, abstract page read 2026-11-14 via pwfetch; full text not opened): plain stride-4 +0.63 AP; note T23. MS-RTDETR, RT-DETR++, FSDC-DETR, HMF-DEIM seen as search listings only.
https://rgu-repository.worktribe.com/output/2418851 (Jamieson et al., construction diagrams symbol detection, IJDAR 2024): Cloudflare challenge page, not bypassed; stays abstract-only. Hand-drawn diagram search 2026-11-14 (WebSearch): Sketch2Sim 2610.28836, Arrow R-CNN, DrawnNet listed, not opened.
WebSearch 2026-11-14 for Dome-DETR citers (OpenAlex budget gone): no 2026 drawing, symbol or document application found.
https://github.com/obss/sahi sahi/predict.py and sahi/postprocess/combine.py (read 2026-11-14 via gh api): default GREEDYNMM + IOS 0.5, merge semantics; licence MIT; note T24.
2026-11-14: Mainz repository bitstream (landslide symbols) fetched once by plain GET: still the Anubis bot page, not bypassed. WebSearch for a 2025 YOLSO follow-up by the York authors: not found.
https://github.com/roboflow/rf-detr/issues/1599 and /1460 (issue bodies and comments read 2026-11-14 via gh api): patch-grid confidence aliasing with period table and mitigations; Seg-L 648 px training time 4:14 per 400 batches and validation OOM on 16 GB; note T25.
https://github.com/roboflow/rf-detr/issues/1052 and https://github.com/Peterande/D-FINE/issues/139 (read 2026-11-14 via gh api): squash-to-square practice, 3:4 native gave about +20% on one user's data, ONNX/PyTorch preprocessing mismatch; note T26.
https://github.com/Peterande/D-FINE/issues/214 and https://github.com/Intellindust-AI-Lab/DEIM/issues/15, /87 (read 2026-11-14 via gh api): D-FINE fine-tune failure on small RF100 sets, DEIM nan and seed instability; note T27.
https://github.com/roboflow/rf-detr/issues/1001 and /310 (read 2026-11-14 via gh api): silent resolution fallback in 1.6.4, default-resolution shrink of large images; folded into T27.
https://pmc.ncbi.nlm.nih.gov/articles/PMC13709312/ via Europe PMC XML (DSC, re-read 2026-11-14 via curl): Top 1 numbers re-checked one by one (F1 .9226, P .8994, R .9470, direct merge P .3452 with 3206 FP, overlap sweep, RandomShift .6630 -> .6882, copy-paste rare class Mask AP .2536 -> .6176, YOLO11-seg-L Box AP .7228 vs .6336, 57/14/10 split, 4813 patches, 200 queries, 9624x2648 px): all match.
Spot-check 2026-11-14 against saved pdf text: YOLSO 97.9/43.6/70.2/22,882, ScoreAug 36.0/56.5/73.7, DAS 2024 DINO .914 vs .642 and full-page .849/.642 all match.
https://github.com/roboflow/rf-detr/issues/112 and /484 and /674 (read 2026-11-14 via gh api): maintainer on DETR weakness for small objects and upscaling, hosted o365 vs repo COCO checkpoint; folded into T20.
https://github.com/roboflow/rf-detr src/rfdetr/assets/model_weights.py (read 2026-11-14 via gh api): checkpoint URL names (coco for N/S/M, an o365 base asset); open question 6 updated.
https://github.com/RicePasteM/Dome-DETR/issues/26, /37, /40 (read 2026-11-14 via gh api, Chinese translated by me): single-GPU and small-batch reproductions fall 6 AP points or more short; learning-rate scaling advice; folded into T18.
https://github.com/lyuwenyu/RT-DETR/issues/672 and /71 (read 2026-11-14 via gh api): DDP hang on empty-GT batches with denoising; small-object question unanswered; folded into T27. Licence Apache-2.0 (gh api).
https://arxiv.org/html/2605.25046 (TinyFormer, read 2026-11-14 via pwfetch): Table 3 VisDrone D-FINE S/M/L 25.8/29.1/30.3; Table 4 stride-4 surrogate +0.19 AP / +0.58 APS vs raw-detail adapter +1.25 AP; licence CC BY-NC-ND, DEIMv2 base; folded into T23. Small-Pollinator 2607.22913 not yet opened.
https://arxiv.org/html/2607.22913 (small-pollinator detection, read in full 2026-11-14 via pwfetch): Table 2 hidden-test results, RF-DETR-L 1344 px .405 vs slicing .368; table row 24 and note T28. Repo OnurOnal7/buzzspot-pollinator-detection has no licence (gh api).
https://arxiv.org/html/2604.07759 (WUTDet, Table IV read 2026-11-14 via pwfetch): D-FINE-S 71.4/56.1 vs YOLOX-S 67.6/50.0 vs LW-DETR-S 58.7/35.9 on 100k dense small ship images; note T29.
https://arxiv.org/html/2611.12657 (When does sliced inference pay off, Fraunhofer IOSB, read 2026-11-14 via pwfetch; v3 of 11 Nov 2026): resolution beats tiling with box fusion on VisDrone, NMS+IoS best box merge, greedy merge and WBF merge distinct neighbours, SCAHI Apache-2.0 needs dense heads; note T30; T24 cross-referenced.
https://arxiv.org/html/2608.03136 (AI City 2026 Track 6, RF-DETR-L frozen 1120 px inference of a 704 px checkpoint, read 2026-11-14 via pwfetch): AP .3272 to .3654, largest relative gain on small objects; note T31.
https://arxiv.org/abs/2609.06581 (CQTR, abstract page read 2026-11-14 via pwfetch, full text not opened): training-free scale interventions on frozen detectors; added to T31 as R.
WebSearch 2026-11-14 (extended) for a measured line-removal ablation on drawings: nothing isolating it; recorded in section 4.
https://huggingface.co/Roboflow/rf-detr-{nano,small,medium,large,seg-large} raw README and API (read 2026-11-14 via curl): license apache-2.0, dataset tag coco on Large; row 23 updated.
https://huggingface.co/api/models/ustc-community/dfine-* (read 2026-11-14 via curl): Apache-2.0 tags incl. obj365 variant; folded into T27.
WebSearch 2026-11-14 (extended) for DETR behaviour on adjacent identical objects: listings only (MDS-DETR, Route-DETR, DS-Det, DEYOv2, DEIM); nothing measured on touching same-class neighbours; not opened.
https://github.com/Ultraman0729/SO-DETR (README, licence, tree read 2026-11-14 via gh api): Apache-2.0, MMDetection, VMamba dependency, 12-epoch config, no weights; paper not opened; note T32.
https://github.com/Ultraman0729/SO-DETR projects/SODETR/configs/so_detr-4scale_r50_8xb2-12e_coco.py (read 2026-11-14 via gh api): max_epochs 12, num_queries 900, ImageNet R50 init; T32 now V for the config.
https://github.com/huggingface/transformers (model dirs, docs/source/en/model_doc/rf_detr.md, licence; read 2026-11-14 via gh api): RF-DETR, D-FINE, DEIMv2, LW-DETR, RT-DETR(v2) are in transformers, Apache-2.0; note T33.
https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0340719 (ESC-YOLOv8, read 2026-11-14 via pwfetch): 6x4 non-overlapping patches, OCR text removal before detection, YOLOv8 89.7 mAP; folded into T19 (AGPL family, idea only).
https://sol.sbc.org.br/index.php/eramiars/article/download/39477/39249 (SBC paper on DETR P&ID symbol recognition, curl+pypdf 2026-11-14): synthetic 90.5-91.6 mAP vs real 4.0-4.9 (OPEN100) and 33.8-35.3 (IPD), 70 h per variant on RTX 3060; note T34.
https://rfdetr.roboflow.com/latest/cookbooks/fine-tune_detection/ and /1.8.0/learn/train/training-parameters/ (read 2026-11-14 via pwfetch): vendor estimate 10-25 min for 50 epochs on 1,500 images; batch table incl. RTX 3070 8 GB; resolution divisible by patch_size x num_windows; folded into T25.
https://levelup.gitconnected.com/closing-the-training-gap-between-detr-and-yolo-... (Medium, 12x faster DETR training claim): empty fetch, not read, not bypassed.
https://github.com/roboflow/rf-detr/releases (1.10.0-1.12.1 notes read 2026-11-14 via gh api): training speed-ups, dynamic-batch TensorRT, current version 1.12.1; folded into T25.
https://github.com/roboflow/rf-detr/releases 1.11.0, 1.10.0, 1.12.1 notes (read 2026-11-14): mask-IoU chunking fixes the issue-1460 OOM class; Kornia GPU ShiftScaleRotate added in 1.10.0; T25 updated.
https://github.com/roboflow/rf-detr src/rfdetr/config.py lines 840-930 (validator breaking_on_increase for num_queries and group_detr; read 2026-11-14 via gh api): raising the query count breaks checkpoint loading; T15 updated.
https://github.com/Peterande/D-FINE configs/dfine/custom/dfine_hgnetv2_s_custom.yml and configs/dfine/include/dataloader.yml (read 2026-11-14 via gh api): 220 epochs, RandomIoUCrop/ZoomOut, no rot90, stretch resize; folded into T27.
RF-DETR training-parameters page and cookbook defaults (read 2026-11-14 via pwfetch): 100 epochs, lr, multi_scale off saves up to 40% epoch time (vendor R); folded into T25.
WebSearch 2026-11-14 (extended) for exact-count rates in automated quantity takeoff: vendor claims only; recorded in section 4.
https://arxiv.org/html/2511.09554v2 (RF-DETR paper, Table 2 and appendix re-read 2026-11-14 via pwfetch): COCO AP_S RF-DETR S 32.0 / M 36.1 vs D-FINE S 32.6 / M 37.6; queries droppable at test time; note T35; T29 speculation corrected.
https://arxiv.org/html/2511.09554v2 Table 4, Table 11 and appendix (re-read 2026-11-14): D-FINE on all of RF100-VL (S 60.3 AP / 36.6 AP_S vs RF-DETR-S 60.9 / 34.2), RF-DETR pretrained on Objects-365 with SAM2 pseudo-labels; corrections to T27, open question 6 and the scope answer.
