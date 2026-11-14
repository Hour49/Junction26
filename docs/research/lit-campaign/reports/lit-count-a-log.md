# lit-count-a reading log (one line per source opened; date = 2026-11-14)
Method: V = read verbatim (pwfetch/curl/gh), A = read via web-fetch agent (first ~40k chars verbatim, rest model-summarised, flagged), L = licence file/model card read.
- https://arxiv.org/html/2511.08048v1 (A) GeCo2: FSCD147 test MAE 7.64 / RMSE 39.39 / AP 46.81; 1024 px, no tiling; 4.98 GB, 0.2 s on A100; no low-count analysis.
- https://github.com/jerpelhan/GECO2 (L) LICENSE file MIT; weights on HF dataset repo (no card) + Drive; no weights licence stated.
- https://arxiv.org/html/2511.16719v2 (V via pwfetch) SAM 3: counting protocol §F.4 (conf>0.5, IoM NMS 0.5, presence head off), Table 3/37; interactive exemplar PCS; limitations App. B.
- https://github.com/facebookresearch/sam3 (L) LICENSE = "SAM License" 2025-11-19 (custom, royalty-free non-exclusive grant, not OSI); HF facebook/sam3 gated.
- https://arxiv.org/html/2509.17283v2 (A) Facility enumeration: Co-DETR on two Roboflow door sets + GPT-5; exact-match per image on CubiCasa5K toilets 87.63; no code.
- https://arxiv.org/html/2512.23351 (A) CountGD++: negative prompts, pseudo-exemplars; MAE/RMSE only; adaptive crop at >=800 objects.
- https://github.com/niki-amini-naieni/CountGDPlusPlus + HF nikigoli/CountGDPlusPlus (L) code MIT, weights card MIT.
- https://arxiv.org/html/2608.23845 (A) Counting survey Aug 2026: metrics, no drawing section, exact-match definition Acc_exact; MAE hides wrong-instance counts.
- https://arxiv.org/html/2603.15470 (A) Stacked objects counting (volume method): not transferable to flat sheets.
- https://arxiv.org/html/2602.11024 (A) Chain-of-Look dense surgical instrument counting: CountGD fine-tune 1.2k imgs, MAE 0.88 vs CountGD 7.84; no exact-match.
- https://github.com/rishi1134/CoLSR (L) mixed licence: code MIT, dataset CC BY-NC.
- https://arxiv.org/html/2605.30846 (A) Count Anything (SAM3 backbone + P2PNet-style dense point branch): CLOC MAE 9.34; no exact-match.
- https://github.com/Mengqi-Lei/count-anything + HF MengqiLei/count-anything (L) code Apache-2.0, weights card Apache-2.0, but init from SAM3 weights (SAM License).
- https://api.semanticscholar.org/graph/v1/paper/arXiv:2407.04619/citations (V, curl) CountGD cited by 100+ papers, 97 from 2025-26; list used for the forward walk.
- https://api.semanticscholar.org/graph/v1/paper/arXiv:2511.08048/citations (V) GeCo2 cited by 8, all 2025-26.
- https://huggingface.co/dimtri009/rfdetr-pid-detector (L) RF-DETR P&ID detector card: apache-2.0, 32 classes, 10 epochs, SAHI tiling (DocEng 2026).
- arXiv 2601.04819 AECV-Bench: HTML 404, PDF returned binary through web-fetch: not read yet (retry with pwfetch).
- https://arxiv.org/pdf/2601.04819 (V, PDF text via saved copy + pypdf) AECV-Bench Tables 1-2: per-model exact-match and MAPE for doors, windows, bedrooms, toilets; 120 plans from CubiCasa5K, CVC-FP and web.
- https://arxiv.org/html/2508.07714 (V pwfetch) DoorDet: built from CubiCasa5K SVG (leak), Co-DETR ViT-L, human refinement lifts mAP 0.578 to 0.831; Table 4 per door class.
- https://arxiv.org/html/2607.00015 (V pwfetch) floor-plan compliance framework, conceptual, no counting numbers.
- https://arxiv.org/html/2607.09583 (V) SAM 3 zero/one-shot in remote sensing: text 11.67 mAP vs one-box exemplar 66.55 (DIOR); small vehicles 6.76-9.15.
- https://arxiv.org/html/2607.16826 (V) UpCount: FSC-147 test MAE 12.39; FSC-147 has 7-3731 objects/img, mean 56.
- https://arxiv.org/html/2610.08379 (V, abstract+method) UniCounting: whole-image category count vectors from SAM 2.1; COCO.
- https://arxiv.org/html/2605.02752 (V) PrACo++/MUCCA: negative-label and distractor tests; counters over-count absent classes.
- https://arxiv.org/html/2609.29460 (V) AgriCountDINO: frozen DINOv3, missed-object recovery, exemplar-scale point NMS, 3-shot MAE 11.92.
- https://arxiv.org/html/2512.16415, 2608.20621, 2606.17601, 2601.13871 (V, abstracts) CountZES, RECOUNT, Dual-TTT, OCCAM: general-domain, no exact-match, no drawings.
- https://arxiv.org/html/2603.21746 (V) Point-then-Count: exact accuracy tables 1-3, counting points in code beats model-stated count.
- https://arxiv.org/html/2604.10039 (V, abstract) CountingTricks: VLM count evidence strongest at projection stage, lost in later layers.
- https://arxiv.org/html/2610.09313 (V, abstract) VLMs miss small objects: tokens-per-object rule; names engineering drawings.
- https://arxiv.org/html/2608.25608 (V, abstract + grep) fpvec-lab: readout comparison on CubiCasa5K, corrected annotations; MIT code, NC data. L4 scope: one line only.
- https://arxiv.org/html/2609.24565, 2608.17237, 2604.23095 (V, abstracts) real-drawings study, structural framing plans (own generator), INSIGHT SAM3 indoor RGB-D: none about counting symbols on raster plans.
- https://arxiv.org/html/2508.10449 (V) SkeySpot: YOLOv8 mAP50 81.1 on 13 test images of electrical plans; AGPL stack.
- https://blog.roboflow.com/detecting-and-counting-symbols-on-construction-plans/ (V, pwfetch) vendor post, May 2026: per-sheet-type detectors, tiling, active learning, no numbers.
- Semantic Scholar citation lists (V, curl): CountGD++ 16 citing, CubiCasa5K 176 citing (80 from 2025+), AECV-Bench 9, SAM 3 first 1000, Point-then-Count 2; one 429 on the third call, retried after a pause.
- gh api licences (V): P2PNet LICENSE "academic research only"; T-Rex IDEA License 1.0 commercial needs licence; PET MIT; CounTR MIT; LOCA MIT; GroundingDINO Apache-2.0; PseCo no licence file; CountGDPlusPlus MIT; GECO2 MIT (LICENSE file); count-anything Apache-2.0; SAM License (sam3).
- https://arxiv.org/html/2605.10887 (V pwfetch) HieraCount/KubriCount: multi-grained counting (instance, attribute, category...), negative prompts, Grounding DINO base; MAE/RMSE only.
- https://arxiv.org/html/2602.19432 (V) CountEx: exclusion prompts, CoCount 10,086 frames; KC setting MAE 12.72 vs CountGD 15.55.
- https://arxiv.org/html/2609.04716 (V) BunchCount: group vs individual counting (1,330 images); counters tuned on individuals fail on groups (analogue of window strip vs cell).
- https://arxiv.org/html/2609.07939 (V, abstract) repeated-element discovery from one image, FSC-147 only; not used.
- https://arxiv.org/html/2509.13939 (V) PairTally: specialist counters (GeCo, CountGD) overcount confusable classes, VLMs undercount; DAVE/GeCo MAE 45-63 on two-class scenes.
- https://arxiv.org/html/2512.03233 (V, abstract+setup) GPT-4o/GPT-5 zero-shot counting on FSC-147/CARPK: MAE/RMSE only.
- https://arxiv.org/abs/2309.05277 (V) Interactive class-agnostic counting (2023): two-click region feedback, 30-40% MAE reduction; background for human correction.
- https://ojs.aaai.org/index.php/AAAI/article/view/41432 (blocked: bot protection page; not circumvented) human-in-the-loop eider duck counting AAAI 2026: search snippet only.
- gh issues (V, 2026-11-14): jerpelhan/GECO2 #5 #10 #12 #14 #17; niki-amini-naieni/CountGD #22 #37 #40 #41 #52; CountGDPlusPlus #6; facebookresearch/sam3 #604 #616-#658 #640; Mengqi-Lei/count-anything list.
- https://arxiv.org/html/2404.16622 (V pwfetch) DAVE: detect-and-verify, spectral clustering of verification features, outliers = clusters without an exemplar.
- https://arxiv.org/html/2407.04619 (V pwfetch) CountGD: shortest side 800 px, trained on FSC-147 (>= 7 objects per image), CountBench 2-10 zero-shot with text, MAE only.
- https://arxiv.org/html/2512.20153 (V pwfetch) CoDi: latent-diffusion counter, 15 h on one H100 for training, 25 steps; says CountGD struggles with small dense objects.
- https://arxiv.org/abs/2306.09683 (V, abstract) OWLv2; HF card google/owlv2-base-patch16-ensemble apache-2.0, nvidia/LocateAnything-3B nvidia-license, IDEA-Research/grounding-dino-base apache-2.0, fushh7/LLMDet apache-2.0 (V cards).
- https://rgu-repository.worktribe.com/output/2418851 (empty page; paper not read): Jamieson et al. IJDAR 2024 YOLO 79 / Faster R-CNN 83 mAP appears in a search snippet only.
- WebSearch round 3 (snippets only, then opened where possible): CountSE (ICCV 2025, github pppppz22/countse, text-guided soft exemplars, not opened), SkeySpot, YOLOplan (open-source takeoff tool, not opened).
- https://arxiv.org/html/2412.00686v4 (V pwfetch) LVLM-Count (TMLR 2026): divide-and-conquer with object-safe splits; appendix I exact accuracy tables; Emoji-Count benchmark description (1024x1024 canvas, 30-50 icons per class).
- https://arxiv.org/html/2406.09262v2 (V pwfetch) Deep Double Poisson Network: discrete predictive count distributions, tunable mean-fit/calibration trade-off.
- https://huggingface.co/api/datasets/jerpelhan/geco2-assets and https://huggingface.co/api/models/nikigoli/CountGDPlusPlus (V curl) GeCo2 asset repo: not gated, no card or licence tag, two checkpoints (CNTQG_multitrain_ca44, GECO2FSCD) plus wheels; CountGD++ repo: tag license:mit, full code + training files in the model repo.
- https://arxiv.org/html/2602.12774 (V pwfetch) WS-COC (ICLR 2026): count-only supervision of an MLLM, FSC-147 test MAE 13.91; code repo viscom-tongji/WS-COC not checked.
- CountGD paper section 4.3 and Table 4 (V, re-read): self-similarity double counting, SAM-based test-time normalisation, adaptive cropping, MAE 10.92 -> 9.62 -> 6.75.
- https://arxiv.org/search/ (V, browser) arXiv search pages sorted by announcement date for "floor plan counting", "symbol counting drawings", "CubiCasa5K", "floor plan detection", "FloorPlanCAD symbol": only AECV-Bench and 2509.17283 count anything on plans; found 2608.14317 (MEP lighting symbols, Mask R-CNN) and 2610.17776 (TempFit, vector).
- https://arxiv.org/html/2608.14317, https://arxiv.org/html/2610.17776 (V pwfetch) abstracts and tables as noted in the report.
- https://github.com/jerpelhan/GECO2 install.sh, train.sh, file list (V gh api): CUDA op build, Dockerfile, Slurm 2-GPU training script.
- https://github.com/facebookresearch/sam3/blob/main/LICENSE (V gh api, full text) SAM License terms: no NC clause; same-agreement redistribution, acknowledgement, no reverse engineering, trade-control/military exclusion.
- https://allenai.org/blog/molmopoint (V pwfetch) MolmoPoint: patch-selection pointing, no-more-points class; PixMo-Points F1 89.2; HF cards allenai/MolmoPoint-8B and -Vid-4B apache-2.0 (V).
- WebSearch snippet only (not used as fact): Qwen3-VL technical report CountBench numbers for 2B/4B/8B (arXiv 2511.21631); OCR'd table, needs the PDF.
- https://arxiv.org/html/2608.15032 (V pwfetch) Handoff-H1 / TakeoffBench-v1: closed CV + agents system, 25% tolerance scoring, Windows & Doors 88 vs estimators 89, counting trades converge across systems.
- https://arxiv.org/html/2511.21631 (V pwfetch) Qwen3-VL technical report: evaluates CountBench; table text did not render, no numbers taken.
- https://arxiv.org/abs/2308.13814 (V pwfetch, abstract) PET; github cxliu0/PET and AaronCIH/APGCC READMEs (V gh api): crowd checkpoints on Drive; MIT code.
- https://huggingface.co/facebook/dinov2-base (V) apache-2.0; facebook/dinov3-* gated, DINOv3 LICENSE is the Meta custom licence (V).
- https://arxiv.org/html/2610.09313 (V pwfetch, full text, appendix tables) Why VLMs miss small objects: **LegendSpot** (34 architectural drawings, 660 instances, legend crop as exemplar): template matching F1 0.87, CountGD 0.10, GeCo2 0.23, OWLv2 0.07; library references 0.38 / 0.11 / 0.15; FloorPlanCAD blocks 0.58 / 0.19 / 0.34; tiled VLM rule results; zoom agents. Most important single source for the scope.
2026-11-14 00:52 https://arxiv.org/html/2610.09313 (scratch text, round 1): code/data released (appendix K), TM recipe = multi-scale 4-rotation NCC + NMS, threshold from 6 sheets; added to top item 1
2026-11-14 00:54 gh api repos/<2610.09313 repo>/license: MIT; gh issue list sam3 --limit 40: 19 access-related titles (claim confirmed)
2026-11-14 00:50 CountGD requirements.txt (gh api): cython, submitit, scipy, timm, torch 2.2.1, transformers 4.39.1, opencv, supervision 0.6.0, pycocotools: no AGPL/GPL package; GeCo2 has no requirements.txt at top level
2026-11-14 00:55 OpenAlex cites W7221062361 -> arXiv 2610.25503 abstract: stated counts vs listed records mismatch; decode-and-count cuts error 85-99% on synthetic scenes
2026-11-14 00:51 arXiv search 'floor plan symbol counting exemplar' and 'architectural drawing symbol counting training-free' (all fields, by date): zero results both; gap stays open
2026-11-14 00:52 WebSearch SKU-110K exemplar counting: no 2026 paper evaluates exemplar counters on SKU-110K or thin look-alike objects; GeCo/LOCA known to overcount with other classes present (search snippet, A)
2026-11-14 00:54 gh CountGDPlusPlus requirements.txt + issues #5 #4 (all 8 issues listed): no AGPL dep; blurry images need enhancement or exemplar+text
2026-11-14 00:57 https://arxiv.org/html/2602.11024 via pwfetch: CountGD 7.84/10.71, DQ-DETR 4.24/6.81, REC 2.82/4.50, CoLSR 0.88/1.27 (MAE/RMSE), batch 4 on one RTX 3090: numbers now V (were A)
2026-11-14 00:58 https://arxiv.org/html/2509.17283 via pwfetch: Table 1 toilet accuracy GPT-5 vs CoT: CubiCasa5K 85.57/87.63, FloorPlanCAD 79.29/85.71, SESYD 68.75/95.83, CVC-FP 40.00/86.67 etc over eight datasets (now V)
2026-11-14 00:58 https://arxiv.org/html/2603.15470 via pwfetch: 'Ours' NAE 0.36 in the real-scene table (now V; ruled out anyway: needs 3D)
2026-11-14 00:58 https://arxiv.org/html/2608.23845 via pwfetch (survey, 4354 lines): grepped for floor plan/blueprint/technical drawing/CAD; see report section 9 for result
2026-11-14 00:55 gh api repos/<2610.09313 repo> baseline_template_matching.py (full recipe: 5 scales x 4 rotations, TM_CCOEFF_NORMED, max-over-variants, NMS radius, floor 0.30, LOO threshold) + tree listing: report section 10
2026-11-14 00:58 research.chalmers.se/publication/549362 full text PDF (pypdf): BlueprintSymVL tables 2-3, EMR by scenario; web search for DrawingVQA (arXiv 2607.15418: 33 drawings, 92 QA, 48.9% GPT-4o, not counting) snippet only
2026-11-14 00:57 gh api license for PET, CLTR, FIDTM, APGCC (all MIT); PET models/pet.py thrs=0.5; CountGD README --confidence_thresh 0.23; PET README table SHB MAE 6.18 SHA 49.08
2026-11-14 00:58 WebSearch x3 (real-scan floor plans; Poisson-binomial detector count; one-shot P&ID) + arxiv.org/abs/2506.21486 abstract: pointers only, report section 13
2026-11-14 00:58 gh api pppppz22/countse (MIT, README: FSC-147 training, CountGD env) and kaijiang77/SAHCC (MIT, ECCV 2026 crowd counting matcher)
2026-11-14 00:58 arxiv.org/abs/2606.03410 and 2605.30794 abstracts: no counting task; pointers to L7
2026-11-14 00:58 gh api <2610.09313 repo> data/redp40/tm_summary.md + README.md + LICENSE-DATA: exact-count 14/40 (LOO), views 10/20, sheets 4/20; data CC BY-NC 4.0; report section 14
2026-11-14 00:58 gh api experiments/results_test/analysis_v1.txt (92 lines): hypothesis tests on F1 only, no exact-count table
2026-11-14 00:58 semanticscholar citations of DOI 10.1016/j.rineng.2025.108171 (10 hits); abstracts of 2608.26091, 2608.24886, 2608.29268; ICICLE snippet: none count by exemplar
2026-11-14 00:58 BlueprintSymVL full text tables 5-7 (per-symbol, occlusion, exemplar ablation): context exemplar 50.5 vs crop 36.5 EMR; report section 16
2026-11-14 00:58 consistency edit: bottom line item 1b added (exact-count rates), item 2 now five places
2026-11-14 00:58 sam3.txt (earlier scratch) lines 4605-4625: CountBench/PixMo-Count counts 2-10, exact accuracy, IoM NMS 0.5 + conf 0.5; report section 17
2026-11-14 00:58 gh api tfcounter/TFCounter (no LICENSE), Joan947/SAM3Count (MIT, README); survey text lines 1525-1533
(note: times of generation-2 lines are approximate, written before checking date; the clock read 00:58 at this line)
2026-11-14 00:59 arxiv.org/html/2404.03507 (DQ-DETR) full text via pwfetch: 4 count bins, 94.6% bin accuracy (corrects snippet); two WebSearch rounds on thresholds and count heads; report section 19
2026-11-14 00:59 arxiv abs 2609.05091, 2604.09689: snippet claim on multi-threshold counting not confirmed in abstract
2026-11-14 01:00 arxiv abs 2508.00728 YOLO-Count: abstract only, no repo found
2026-11-14 01:00 arxiv.org/html/2511.08048 via pwfetch: GeCo2 MAE 7.64, RMSE 39.4, AP 46.81, 4.98 GB, 0.2 s, fixed 1024 input confirmed (V)
2026-11-14 01:01 arxiv.org/html/2407.04619 via pwfetch: Table 2 CountBench MAE 0.86 RMSE 3.1 text-only zero-shot, Table 3 modality ablation; shortest side 800 (V)
2026-11-14 01:01 docs/decisions/0006-lgpl-dependencies.md (read): allowed licence list and exclusions; report section 20
2026-11-14 01:01 arxiv.org/html/2404.16622 via pwfetch: DAVE FSC147 MAE val 8.91 test 8.66 confirmed; gh api license MIT; table row updated from 'earlier report' to V
2026-11-14 01:02 sam3.txt lines 950-975 re-read: few-shot adaptation on RF100-VL out-of-scope domains, one-exemplar AP+ gains over T-Rex2, interactive exemplar loop
2026-11-14 01:02 openaccess.thecvf.com ICCV2025 CountSE page via pwfetch: abstract (soft exemplars, clustering filter)
2026-11-14 01:02 semanticscholar search API: title of 'Why floor plan object detection breaks under real scans' confirmed (Automation in Construction 2026); abstract request 429; web search no page; FloorYOLO (Frontiers AI 2026) noted
2026-11-14 01:02 WebSearch FloorYOLO: paper not found in results; no new info
2026-11-14 01:02 arxiv.org/pdf/2511.21631 via curl+pypdf: CountBench cells Tables 2-4 (range 62.9-94.9); column header alignment not recovered
2026-11-14 01:02 arxiv.org/abs/2607.02139 AdaCount abstract via pwfetch; gh search repos AdaCount: Mengqi-Lei/AdaCount MIT (unofficial?)
2026-11-14 01:03 WebSearch x2: takeoff vendors (Roboflow, Trimble, STACK, ConstructConnect) and within-one metrics; snippets only; report section 25
2026-11-14 01:03 blog.roboflow.com detecting-and-counting-symbols-on-construction-plans via pwfetch: one detector per sheet type, tiling, no error rate
2026-11-14 01:03 gh issue list/view CountGD (#22 #35 #40 #52), GECO2, DAVE titles: training/fine-tuning requests, no thin-object or drawing issues
2026-11-14 01:03 semanticscholar citations of arXiv:2610.09313: zero (too new)
2026-11-14 01:04 semanticscholar citations of GeCo2, CountGD, CountGD++ filtered by drawing terms: none; report section 27
2026-11-14 01:04 arxiv.org/pdf/2601.04819 via curl+pypdf: Table lines 485-493, Gemini 3 Pro 0.51 mean, door 0.39, window 0.34, bedroom 0.89 (report said 0.89 ok), toilet 0.82; GLM-4.6V 0.39/0.09/0.03 re-verified (V)
2026-11-14 01:04 re-read AECV Table 1 incl. Qwen3-VL-8B row 0.09/0.10; report section 28
2026-11-14 01:05 2603.21746 scratch text lines 226-272: Table 1 real-world 1-10 objects (OCID): DC 70.00/73.57, PtC 81.90/76.19 etc; corrected 76-82 to 70.0-81.9 in 3 places
2026-11-14 01:05 corrected again after report line 217: LLaVA DC 69.05; summary now 69.1-81.9 (DC 69.1-73.6, PtC 76.2-81.9)
2026-11-14 01:05 arxiv abs 2504.16570 + gh api lorebianchi98/CountingDINO (no LICENSE, README: DINOv2 ViT-L/14 reg): report section 29
2026-11-14 01:06 arXiv search page via pwfetch returned empty twice; WebSearch for new few-shot counters Oct-Nov 2026: nothing new beyond OCCAM, SeqCount (J. Vis. Commun. Image Represent. Aug 2026, snippet), Count Anything (2605.30846), all known or out of scope
2026-11-14 01:06 zenodo.org/api/records/17250377 metadata (cc-by-4.0, BlueprintSymVL.zip 6.2 MB) + paper data availability: report section 30
2026-11-14 01:06 gh api jerpelhan/GECO2 app.py: relative threshold box_v > max*thr (default 0.33) + NMS 0.5; report section 31
2026-11-14 01:07 gh api CountGDPlusPlus README: internal/external exemplar modes, paid upscaler for adaptive crop; report section 32
2026-11-14 01:07 gh api xinntao/Real-ESRGAN license BSD-3-Clause; issue 5 link confirmed
2026-11-14 01:07 gh search repos (point-supervised counting, crowd localization): NWPU localization sample code MIT, LGD-Peaket other, FocalGen apache; nothing with 0-40 object results
2026-11-14 01:07 scratch text of arxiv 2601.13871 (OCCAM): SAM2 seed grid + FINCH variant, no repo found; report section 34; line 422 updated
2026-11-14 01:08 WebSearch DualCount ECCV 2026: no paper by that name found; new names seen: MambaCount 2606.17650, HoloCount 2607.06420 (benchmark for MLLM counting; L7)
2026-11-14 01:08 arxiv abs 2607.06420 HoloCount: MLLM counting benchmark, natural images
2026-11-14 01:08 cross-reference lines added to top item 1 and 3
2026-11-14 01:08 reference list of 2610.09313 (lines 1900-2140 of scratch text): drawing-related refs enumerated; report section 35
2026-11-14 01:08 openaccess.thecvf.com/CVPR2026?day=all and ICCV2025?day=all via pwfetch, grep count in titles: lists in report section 36
2026-11-14 01:09 WebSearch CAPTURe ICCV 2025 summary: coordinates as text help
2026-11-14 01:09 re-grep of scratch text 2610.09313 for tiling numbers (lines 74, 92, 171, 562, 1613, 1664): all match
2026-11-14 01:09 odr.chalmers.se thesis 'Beyond the Legend' (79 pp) via curl+pypdf: sliding-window TM recall 0.702 F1 0.519, TM on regions 0.730/0.734, region detector recall 95.42%; report section 37
2026-11-14 01:10 arxiv abs 2204.13277 (legend-table method, 2022); airaxiv.com/arxiv/pdf/2875 Not Found; 2602.20551 title only
2026-11-14 01:10 bottom line item 1 updated with sections 11 and 37
2026-11-14 01:10 added reading guide before section 0
2026-11-14 01:10 arxiv abs 2511.19351 CellFMCount: adjacent field note, report section 38
2026-11-14 01:10 gh api shijunzhe repo README + tools/safe_tiles.py header: stand-alone MIT tiling planner; report section 39
2026-11-14 01:11 bsv.txt ref [5]: density and noise paper 2024 (IEEE IS), not opened
2026-11-14 01:11 arxiv.org/html/2610.25503 via pwfetch, lines 46-141: list-then-count repair 71-84% (stated vs listed), 85.2/98.8% full protocol, datasets; report section 40
2026-11-14 01:11 gh api shijunzhe/vlm-set-reporting license MIT; reading guide updated to 40
2026-11-14 01:11 bottom line items 3 and 4 updated with sections 14, 19, 37, 40
2026-11-14 01:12 api.crossref.org works query title: autcon.2026.107193 and SSRN 6378246 abstract (CubiCasa5K paired renderings, RT-DETR, stroke width and blur dominate); report section 41, gap in section 4 marked resolved
2026-11-14 01:12 api.crossref.org abstracts: IJDAR 2024 construction symbol detection (mAP 79/83), IEEE IS 2024 and Few-Shot Symbol Detection 2024 no abstract; report section 42
2026-11-14 01:12 ec-3.org/?p=15538 abstract via pwfetch (mask-aware TM, IoU of RoI masks, IoM NMS, F1 0.992 on P&IDs); crossref title of CCDC 2026 legend matching; report section 43
2026-11-14 01:13 api.crossref.org title sweeps (4 queries, last failed): names only; report section 44. Final: wrap-up ordered by lit-orch, no new sources
