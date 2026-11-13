# lit-vector-b: sideways transfers for raster-to-vector, structural and classical routes (scope L11, angle b)

Final status: complete, wrapped up on the orchestrator's early deadline; unread leads are listed in section 6 and the log. Read 2026-11-14 (all sources below, date read 2026-11-14). "Verified" = a fetch of the page showed me the text; "reported" = the
authors' own claim, or text I got only from a fetch summary (marked "summary"). Pages were read through the web-fetch agent, the headless browser, and downloaded paper PDFs read as text;
Semantic Scholar citation lists through the headless browser after plain fetches got HTTP 429. The reading log with one line per
source is `lit-vector-b-log.md`. Extends `lit-vectorise.md`, `02-symbol-detection.md`, `03-vector-cad-parsing.md`, `05-handdrawn.md`.

## Answer to the scope question first

**Is there any evidence a vectorise-then-rules route beats direct detection on scanned plans? No.** I found none, and the
head-to-heads that exist point the other way:

- SALI-FP (arXiv 2609.25615, 2026, verified): a palette-rules plus Shapely vectoriser against learned nets on the same 400 CubiCasa5K test
  plans. Room F1 0.4450 vs 0.6305 (CubiCasa5K polygons) and 0.7626 (Raster2Seq); four-class mIoU 0.3596 vs 0.7390 (Table C.1, C.12). The rule
  route loses on every measure. It reports no counts.
- FlowExtract (arXiv 2604.06770, 2026, verified): objects are detected (node F1 98.8%), connecting lines come from Hough plus graph tracing,
  and the lines are the weak half (edge recall 54.6%, F1 66.7%, Table 2). The ratio is the argument for detecting objects directly.
- Chemical structure images, the nearest field where rule-based vectorise-then-rules tools (OSRA, MolVec) were scored against learned models on
  real scans (MolScribe arXiv 2205.14311 Table 2, re-read verbatim through the headless browser; COMO arXiv 2604.23546 Table 1, re-read verbatim). On clean patent images the rule tools are within a few
  points of the learned model (USPTO exact match OSRA 87.4, MolVec 88.4, MolScribe 92.6). On a blurry, low-resolution set (Staker, 50,000 images, which MolSight 2511.17300 describes as "low-resolution images synthesized with the Indigo toolkit", so degraded renders, not photographed scans) they
  collapse: OSRA 0.0, MolVec 0.8, MolScribe 86.9, COMO 87.5. On ACS journal images OSRA 55.3 vs MolScribe 71.9 vs COMO 88.2, and on the 10,000-image wild set WildMol-10K OSRA 24.9 against MolGrapher 45.5 (COMO Table 1; the paper describes OSRA as "image binarization, vectorization, and heuristic atom-bond assembly without any learned components", i.e. a vectorise-then-rules route; it scores 95.2 on clean Indigo renders). **This is the only
  evidence I found, and it says: structural rules are competitive on clean renders and fail on degraded scans.** Our set is a mix, so a rule route is at best a second count.
- GLSP (arXiv 2303.03851) and the P&ID papers compare only learned against learned. I found no paper that scores a rule/structural opening
  detector against a learned one on the same plans (several arXiv API queries, zero hits).
- Deep line detectors (ScaleLSD, DeepLSD, HAWP, M-LSD) have no published result on floor plans or scans. The one paper that
  evaluates a line detector on plans (GLSP) uses a retrained HAWP variant on 268k rendered plans, not an off-the-shelf model; the only off-the-shelf run on binary line art is on glyph bitmaps (DeepLSD recovers 1.4% of strokes, HieroSA Table 1, see T2).

So: keep direct detection as the main counter. A line or primitive route is useful only as a cheap structural prior or an independent
second count (stage 8), and nobody has measured that on our image style. Everything below is a candidate to test, not a result.

## What I would do with this (three cheap tests, in order)

1. **Scale-normalise, keep the lines (free).** Every rule stage needs scale-adaptive thresholds anyway: the P&ID hybrid loses 0.55 edge F1 when its snap distance is a fixed 10 px instead of adaptive (2609.05880). Rescale every sheet so a structural unit (wall thickness, estimated from the stroke-width histogram) has a fixed pixel size before detection, as Deep Watershed Detector does with the staff interline;
   train the detector on the lines-in images. Music shows removing lines buys nothing for detection (mAP 80%, "minimal impact"), but the evidence is on synthetic lines, so keep a 20-plan A/B.
2. **Run Deep Sketch Vectorization on 20 dev plans (about 3 hours, MIT code and weights, 8 GB).** Look only at whether door swing arcs and window pane lines come out as separate strokes joined to the wall at a junction. If yes it can feed the stage-8
   second count; if no, drop every line-first route and say so on the board. Do not run DeepLSD (AGPL via pytlsd); ScaleLSD's single-image path does not import pytlsd, so it is the cleaner of the two.
3. **Stage-8 second count from agreement, not render-and-compare.** The OCSR result (VERDICT, 2608.22183) is that agreement of three or four independent recognisers separates right from wrong (AUROC 0.916) while a pixel round-trip does not (0.547).
   Use two detectors with different architectures and different training halves as the independent measurement, and treat a line-based count as one more voter only if test 2 passes.

## 1. Top 5 (floor-plan work and transfers in one list)

| # | Candidate | From | Verdict | Why (one line) | Source |
|---|---|---|---|---|---|
| 1 | Detect symbols directly through the ruled lines, normalise by the structural unit (OMR: Deep Watershed Detector, Oemer, YOLOv8 on MUSCIMA++) | music scores | **try** (idea, free) | The closest same-shape problem: tiny symbols sitting on and touching thin lines. A detector that keeps the lines does as well as removal-first (mAP 80%, "minimal impact", on synthetic staff lines), and the one trick that transfers is rescaling every page so the line spacing is a fixed pixel size | arXiv 1805.10548, 2409.00316, github BreezeWhite/oemer |
| 2 | MolScribe recipe (OCSR): image to graph of atoms with coordinates and bonds, trained on synthetic renders plus rotation/noise augmentation, exact-match scored | chemical structure images | **maybe** (recipe; code usable) | Same shape (thin lines, tiny labelled symbols, exact match, scans). Measured against rule tools on 6 real sets; weights MIT but 384 px input and an autoregressive atom-then-bond pipeline mean it cannot be used as is on our 5 px symbols | arXiv 2205.14311, github thomas0809/MolScribe |
| 3 | Deep Sketch Vectorization (SIGGRAPH 2024): network predicts an unsigned distance field, dual contouring and keypoint maps give centrelines with multi-way junctions | sketch / line-art vectorisation | **maybe** (best permissive line-to-graph option, 1 test) | MIT code, MIT weights card, 8 GB VRAM (4 GB light model), 512 px; measured Chamfer 15,413 vs 28,180 (Puhachov) on clean and 19,279 vs 66,310 on paper-textured strokes; trained on 63k synthetic sketches, so CAD plans and 5 px symbols are untested (open issue #2 reports weak keypoints on technical sketches) | arXiv none; paper ACM TOG 43(4), github Nauhcnay/Deep-Sketch-Vectorization |
| 4 | SynthPID recipe: synthesise training pages by perturbing the real label graph and re-rendering | P&ID digitisation | **maybe** (idea) | Measured: 665 synthetic pages made from 12 real ones, zero real training pages reaches node mAP 64.2 vs 67.8 with real, 71.3 mixed. Code not released (repo 404), so only the idea | arXiv 2604.16513 |
| 5 | ScaleLSD (CVPR 2025) as a line-prior feature | wireframe / 3D vision | **maybe, low** | MIT code, Apache-2.0 weights card, ViT-B at 512 px; no drawing result, the one off-the-shelf run on binary line art (DeepLSD, HieroSA Table 1) recovers 1.4% of strokes, and its requirements file lists pytlsd (AGPL LSD source) though the single-image path does not import it (see 3b) | arXiv 2506.09369, github ant-research/scalelsd |

Ranked below the top 5: the synthetic-only primitive DETR for door arcs (arXiv 2403.08721, idea only, AP_arc 0.483, code not released); Deep Vectorization of Technical Drawings (skip for counts, maybe a wall mask: only vectoriser tested on real floor-plan scans, MPL-2.0, cleaner not released, see T3); vector symbol spotters (SymPoint-V2, CADSpotting, VecFormer, TempFit: true CAD primitives only,
skip), StarVector/LIVE (no thin-line or topology evidence, skip), SAM-Road (idea for a wall graph, not a count, skip).

## 2. Full table

Columns: field of origin; what it is; year/venue; code (licence read from file/card); weights (licence); training data; metric and
benchmark as printed; input size and compute as printed; JSON field it would fill; leakage flag (CubiCasa5K or repackage: yes/no/unknown);
hours to a first number on our dev boxes (my estimate, marked E); verdict. "n/r" = not reported in what I read.

| Method | Field | What / year / venue | Code, licence | Weights, licence | Training data | Metric, benchmark | Input, compute | Fills | Leak | Hours (E) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ScaleLSD | wireframe | (pytlsd in requirements, imported only by a demo, see 3b) ViT-B + DPT predicts attraction fields and junctions; pseudo-labels from LSD direction on SA-1B. CVPR 2025 (2506.09369) | github ant-research/scalelsd, MIT (LICENSE read; push 2025-09-25) | HF cherubicxn/scalelsd, apache-2.0 (card read) | synthetic primitives 16k, Wireframe 20k, SA-1B 10M unlabelled (SA-1B overview says "Research purposes only") | Rep-5/Loc-5/Len-5 only; YorkUrban S Rep-5 0.725 (HAWPv3 0.711). No sAP, no drawings | 512x512, "any RGB/grayscale"; train memory n/r | none directly (line map for door arcs/wall gaps) | no | 2 (E) | maybe, low |
| DeepLSD | wireframe | CNN line attraction field plus classical LSD refinement (needs pytlsd = AGPL LSD source, see 3b). CVPR 2023 | cvg/DeepLSD, MIT | "released under an MIT license" (README) | Wireframe or MegaDepth-subset checkpoints | none in README; ScaleLSD paper Table 1: YorkUrban S Rep-5 0.514 | n/r | as above | no | 2 (E) | maybe |
| HAWP v2/v3 | wireframe | holistic attraction fields, v3 self-supervised (2210.12971, TPAMI). | cherubicXN/hawp, MIT | not stated in README | Wireframe, YorkUrban (v2); v3 checkpoints: Wireframe images, or 100k ImageNet images (docs/HAWPv3.md; ImageNet terms are research-only) | none in README | n/r | as above | no | 2 (E) | skip, ScaleLSD/DeepLSD cover it |
| M-LSD | wireframe | tiny real-time line detector, TF. AAAI 2022 | navervision/mlsd, Apache-2.0 (header only) | not stated | not named in README | none in README | 320 or 512 px | as above | unknown | 2 (E) | skip |
| SweepLSD | classical LSD | streaming integer-only detector, 2026 (2608.22086) | yosh-shimizu/sweeplsd, MIT (gh licence API); third_party holds only stb | none (no learning) | none | F-max synthetic charts 0.958 at sigma 0; ELSED higher at every noise level (summary, not verified) | grayscale, 11 ms per Full-HD frame | line map | no | 1 (E) | skip, no drawing test |
| ADLA | classical on learned edges | edge-strength map (EdgeNAT) then line growing, 2025 (2508.19742) | github ChenguangTelecom/adla, MIT (gh licence API) | n/r | BIPEDv2, ShanghaiTech | YorkUrban-LineSegment F^H 0.8665 vs LSD 0.8125 (summary) | 500x390 images | line map | no | n/a | skip |
| Deep Sketch Vectorization | sketch/line-art vectorisation | UDF + neural dual contouring + keypoint/under-sampling maps, handles high-valence junctions. SIGGRAPH 2024 / ACM TOG 43(4) | Nauhcnay/Deep-Sketch-Vectorization, MIT (LICENSE; push 2026-10-24) | HF waterheater/deepsketch, mit (card) | 63k vector sketches (QuickDraw 10k, Creative Sketch 53k) rasterised in 7 brush styles on paper textures = 441k images; tested on 369 cleaned sketches | Chamfer 15,413 vs 28,180 (Puhachov), 126,874 (Bessmeltsev) at 512 px clean (Table 1); textured 19,279 vs 66,310 (Table 2); success rate 100% | 512 px; full model 8 GB VRAM, light < 4 GB; 5-17 s per 512 px image on their machines; 72 GPU hours on one A100 to train | line graph for door arcs, wall gaps, window lines | no | 3 (E) to run on 20 dev plans | maybe |
| Deep Vectorization of Technical Drawings | tech. drawings | U-Net clean + 64x64 patch transformer + energy refinement. ECCV 2020 (2003.05471) | Vahe1994/Deep-Vectorization-of-Technical-Drawings, MPL-2.0, archived | line and curve weights on Yandex Disk, no licence; cleaning model not released | PFP 1,554 commercial plans, ABC 10k CAD, 81 real degraded plans for fine-tuning | IoU 86/88 (PFP), 79/82 (real DLD) vs CHD 47 | 64x64 patches; four days on one V100 | wall/line mask | no (PFP, ABC) | 8+ (E, needs retrain of cleaner) | skip for counts |
| SymPoint-V2 | CAD symbol spotting | point-set transformer with layer features (2407.01928) | nicehuster/SymPointV2, no LICENSE file; sibling SymPoint repo carries a non-commercial research licence | Google Drive link, no licence | FloorPlanCAD (CC BY-NC) | PQ 90.1, SQ 96.3, RQ 93.6 (Table 3); true primitives only | 8x A100 training | rooms/elements from vector | no | n/a (needs primitives) | skip |
| CADSpotting | CAD symbol spotting | PTv3 on sampled points, sliding window (2412.07377) | yangfy2023/CADspotting (repo exists, no licence file: all rights reserved by default) | n/r | FloorPlanCAD, LS-CAD (on request) | PQ 87.4 (Table 4); true primitives | 8x A100 | as above | no | n/a | skip |
| VecFormer | CAD symbol spotting | line-sampled PTv3, NeurIPS 2025 (2505.23395) | WesKwong/VecFormer, Apache-2.0 | none released (train your own) | FloorPlanCAD | PQ 91.1 with layer prior, 88.4 without (Table 1a) | 8x A100, flash-attention build | as above | no | n/a | skip |
| TempFit | CAD symbol spotting | template retrieval and fit, 2026 (2610.17776) | Daisy-1227/TempFit (repo exists, no licence file) | n/r | FloorPlanCAD, IndustryCAD | Greedy PQ 86.2 (below SymPoint-V2 90.1, VecFormer 91.1), Hungarian 80.1 | 108M parameters, 279 ms | as above | no | n/a | skip |
| PolarSym, CAGE, TextCAD, text-enhanced spotting | CAD | abstracts or vector input only (2608.11793, 2509.15459, 2607.12678, 2510.11091) | CAGE NOASSERTION; others none found | n/r | FloorPlanCAD / Structured3D | TextCAD PQ 92.67 (summary); 2510.11091 PQ 0.7371 vs CADTransformer 0.7152 | vector or density maps | as above | no | n/a | skip |
| MuraNet | floor plans | wall segmentation + door/window YOLOX head (2309.00348) | none | none | CubiCasa5K | door/window AP50 91.2/92.2, AP50:95 47.9/59.7 (Table 2) | 1536x1536 | window, door | **yes** | n/a | skip (leak, no code) |
| GLSP | floor plans | HAWP-style junctions + GNN, wall/door/window segments (2303.03851) | none | none | LRFP 268k rendered plans | door sAP 97.5/98.6/98.8 (summary), junction sAP_J 76.6/88.0/89.4 | 512x512 | door, window as segments | unknown | n/a | skip (no code) |
| SALI-FP | floor plans | generative image model + audit + rule vectorisation (2609.25615) | none yet | none | ArchP10k | room F1 0.4450 vs 0.6305 CubiCasa5K nets | 1024 px | rooms | no | n/a | skip (rule route loses) |
| Deep Watershed Detector | OMR | ResNet-101 + RefineNet energy maps for tiny symbols, no staff removal. ISMIR 2018 (1805.10548) | tuggeluk/DeepWatershedDetection, MIT; TF 1.4 | none offered | DeepScores (rendered), MUSCIMA++ (CC BY-NC-SA 4.0) | AP@1/2 noteheadBlack 0.8619, rest16th 0.8773; no mAP, no counts | 960x960 crops, pages at interline 10 px; 24 GB P40 runs out at 10.5 Mpx | any small class | no | 8+ (E, port TF1 code) | idea only |
| Oemer | OMR | two U-Nets, staff lines and symbols as separate classes | BreezeWhite/oemer, MIT | GitHub release, no licence stated | CVC-MUSCIMA distortions (NC), DeepScores | none in README | n/r | idea | no | n/a | idea only |
| YOLOv8 + cropping on MUSCIMA++ | OMR | 14 random 1216 px crops resized to 640, staff-removed images (2409.00316, 2024) | guang-yng/completeOMR (repo exists, no licence file); YOLOv8 is AGPL, out | n/r | MUSCIMA++ (CC BY-NC-SA 4.0) | mAP 84.79 (163 classes), 94.22 (20 classes) at IoU 0.5 (Table 1) | 640 px | idea | no | n/a | idea only (crop recipe) |
| MolScribe / COMO / DECIMER | chemistry (OCSR) | image-to-graph with atom coordinates (2205.14311); COMO 2026 (2604.23546); DECIMER V2 | MolScribe MIT, DECIMER MIT; COMO code licence not stated | MolScribe HF card mit; DECIMER Zenodo CC-BY-4.0; COMO not stated | USPTO, PubChem synthetic renders; patents | exact match %: Staker MolScribe 86.9 vs OSRA 0.0 vs MolVec 0.8; USPTO 92.6 vs 87.4/88.4; ACS 71.9 vs 55.3 (Table 2, verbatim) | 384x384 (verbatim); DECIMER 512 | idea: any element class as graph nodes | no | 20 for a feasibility port (E) | maybe (recipe) |
| Relationformer P&ID | P&ID | symbols plus edges as a graph (2411.13929) | none stated | none | 2,000 synthetic + 60 real P&IDs | OPEN100: symbol mAP 73.14, edge mAP 75.46 (Table III) | 512 px patches of 4500x7000 pages | idea | no | n/a | idea only |
| SynthPID | P&ID | synthetic pages from perturbed label graphs (2604.16513) | LatentSpaceIITB/SynthPID, repo 404 | claimed, unverifiable | 12 real plans seed 665 synthetic | node mAP@0.5: 64.2 zero real, 67.8 real only, 71.3 mixed (Table 3) | 1500 px patches | idea | no | n/a | maybe (idea) |
| SINA / AMSNet / PCBnet | circuits | detect components, mask boxes, connected components or flood fill on wires (2601.22114, 2405.09045, 2608.27923) | repo links anonymous or not stated | n/r | 700, 894, 300 schematics | SINA component F1 96.47 (Table I) but Table II says 99.6: inconsistent; PCBnet conn. acc. 84.47 | n/r | idea | no | n/a | idea only |
| FlowExtract | flowcharts | YOLOv8s nodes + arrowheads, Hough for lines (2604.06770) | aixpert-rug/FlowExtract, MIT per README (GitHub API: NOASSERTION) | none in repo | 35 flowcharts | node F1 98.8, edge F1 66.7 (Table 2) | 640x640 | idea | no | n/a | supports direct detection |
| Astronomical-diagram DETR | historical docs | DINO-DETR predicts lines, circles, arcs (2403.08721, ICDAR 2024) | not released ("will be made available") | n/r | synthetic only; 303 real diagrams for eval | mAP 0.722; AP_line 0.764, AP_circle 0.917, AP_arc 0.483 (Table 1) | shortest side 480-800 px | door swing arc (idea) | no | n/a | maybe (idea) |
| SAM-Road / LineGraph2Road | road graphs | SAM ViT-B masks for road and intersection, NMS vertices, edge classifier (2403.16051; 2602.23290) | htcr/sam_road, MIT; LineGraph2Road repo has no licence file | HF congrui/sam_road, mit | CityScale, SpaceNet | City-scale F1 77.23 (SAM-Road), 82.37 (LineGraph2Road) | 512 training crops, 1 m/px | idea (wall graph) | no | n/a | skip |
| StarVector | font/logo/icon SVG | VLM writes SVG text from image (2312.11556, CVPR 2025) | joanrod/star-vector, Apache-2.0 | HF starvector-8b-im2svg, apache-2.0 (card) | SVG-Stack etc. | SVG-Diagrams Dino 0.959; no junction or thin-line metric | 384 px (8B), 224 px (1B) | none | unknown | n/a | skip |
| LIVE / DiffVG | logo/clipart | per-image path optimisation (2206.04655) | both Apache-2.0 | none | none | no printed MSE values; user study 73.8% (summary) | 240 px emoji | none | no | n/a | skip |
| FPicker | cryo-EM filaments | open-curve graph refinement for crossing thin filaments in noise (2609.08305, ECCV 2026) | tomzhaosky/FPicker, GPL-3.0 (out) | HF, CC BY-NC (out) | Cryo-Sim 20k simulated, 500 real | U-Net F1 89.1 / 68.5 / 46.5 at high/medium/extreme noise (Table 1) | 5x RTX 4090 | idea (junction handling) | no | n/a | skip |
| MapTR family | HD maps | ordered point sets with permutation-equivalent matching (2208.14437; GSMap 2605.09619, 2026, no code) | hustvl/MapTR, MIT | Drive links, no licence | nuScenes, Argoverse2 | mAP 50.0 (tiny, 24 ep, 10.3 GB at bs 4) | multi-view camera | none | no | n/a | skip |
| mapKurator | historical maps | text spotting and geocoding, not lines | no code licence file | n/r | n/r | none | n/r | none | no | n/a | skip |

## 3. Transfer notes (from other fields)

For each: what plays our object, why it should transfer, what breaks on our images, whether code and weights work as they are.

### T0. Chemical structure recognition (OCSR): the same shape, with a measured rule-vs-learned comparison
- **Role of our object:** an atom label or bond junction in a thin-line drawing; exact-match of the whole structure is the metric, like our exact counts.
- **Verified (MolScribe paper text and Table 2, re-read verbatim 2026-11-14; COMO Table 1 also re-read verbatim):** rule-based MolVec and OSRA "achieve decent performance on CLEF, JPO, UOB, and USPTO
  but degrade severely on Staker, in which the images are blurry and low-resolution" (verbatim): Staker 0.8 and 0.0 against MolScribe 86.9. COMO (arXiv 2604.23546, 2026, rev. 2026-11-10)
  repeats it: OSRA 0.0, COMO 87.5 on Staker; ACS 88.2. MolScribe trains on synthetic renders (Indigo, varied font, bond width, length) plus rotation, padding, cropping and Gaussian noise
  and resizes every input to 384x384; it predicts atoms with coordinates and bonds as a graph.
- **Rotation and shear, also verified (Table 2, perturbed columns):** with slight rotation and shear the rule tools collapse even on clean patent images: OSRA USPTO 87.4 to 4.0, CLEF 84.6 to 11.5;
  MolVec USPTO 88.4 to 29.7; MolScribe 92.6 to 92.5 and DECIMER 41.1 to 46.4. The paper says "rule-based systems are sensitive to input perturbations". About one in three of our plans is rotated, so a rule route
  would need its own orientation step first.
- **2025 follow-ups, verified (2026-11-14):** MolParser (arXiv 2411.11098v4, 2025) pretrains on 7.7M synthetic pairs and fine-tunes on manually annotated real crops; Section 6.3: synthetic-only
  training does "not yield satisfactory results"; Table 4 WildMol-10K accuracy 51.9 (pretrain only) vs 76.9 (with real fine-tune); Table 5: no augmentation or curriculum 40.1, augmentation 69.5, augmentation plus curriculum 76.9.
  Its real-scan fine-tune is the lever, which fits our case: 3,828 real plans with labels, synthetic plans only as pretraining. Table 2: OSRA 2.1 beats it on CLEF (93.4 vs 90.7 to 91.0), so rules stay competitive on clean sets.
  MolSight (arXiv 2511.17300, 2025, AAAI 2026 per its repo; code Apache-2.0, weights HF card apache-2.0, 512 px) Table 6, perturbed with rotation +-5 degrees and shear +-0.1: OSRA 2.2.1 USPTOp 6.7 (-76.8), MolVec 29.6 (-58.5),
  Imago 42.9 (-44.3), MolSight 92.3 (+0.3); Staker 0.0 / 0.7 / 0.0 vs 82.1. MolParser-7M is CC BY-NC-SA (local training only).
- **2026 forward citations of MolScribe (walked through Semantic Scholar via the headless browser: 121 citers, 85 from 2025-2026; read three in full, last 12-30k characters of each were fetch summaries):**
  - Real Data Closes Synthetic-to-Real Gap in OCSR (arXiv 2608.09100, Table 3, verbatim): a VLM fine-tuned on synthetic renders only scores .950 on clean renders but ACS .154, CLEF-IP .124, UOB .522, USPTO .122 on real depictions
    (four-set average .231). Adding a real fraction of 9.5% lifts them to .372 / .608 / .818 / .698; 41.6% real gives .402 / .628 / .842 / .824. The text says the first 5% of real data gives about two-thirds of the real-document gain.
    No code, no weights licence. **For us:** the few thousand real labelled plans we have matter far more than any synthetic volume; a synthetic-only plan generator (T5 SynthPID idea) will not close the gap alone.
  - VERDICT (arXiv 2608.22183, AUROC figures re-read verbatim, gate table from the fetch read): agreement among four architecturally distinct recognisers (InChIKey match) separates right from wrong answers with AUROC 0.916, against 0.666 for one model's confidence and 0.547 for
    a pixel round-trip; the gate "at least 3 of 4 agree" keeps 52.1% of ACS images at precision .985 (single fine-tuned model .643 at 100% coverage). Repo link 404. **For us:** a stage-8 second count built from independent
    detectors (different architecture, different training data) is the evidence-backed design; render-and-compare is near chance. (Confidence and abstention belong to the trust scope L10.)
  - ViCoR (arXiv 2609.33603, Tables 1 and 2): a small VLM looks at the source image next to a render of the proposed structure, says yes/no, and emits atom/bond edits; ACS 71.9 to 89.7, JIE 61.8 to 84.3. Code "to be released", none yet.
  - Also listed, not read: MolRecBench-Wild (2605.05832), Debate Not Voting (2610.33002), MolParser-Mobile (2609.05807), Uni-Parser (2512.15098).
- **Design points that carry over (verified in the MolScribe text):** the atom predictor is Pix2Seq-style, label tokens plus binned x/y coordinate tokens generated autoregressively, then bonds are predicted between each atom pair
  and the structure is built with chemistry rules (RDKit); abbreviations such as "Me", "Et", "CHO" are treated as "superatoms" and expanded from a closed table (Algorithm 1), the same pattern as decoding our printed room
  labels (MH, OH, K, WC) through a fixed Finnish table; the paper contrasts itself with modular detect-then-heuristics systems (ChemGrapher, MolMiner), which score lower in its Table 2 (ChemGrapher USPTO 70.6).
- **Why it transfers:** (a) it confirms with numbers that a rule route is fine on clean renders and dies on degraded scans; (b) the training recipe, rendering synthetic pages from
  structured labels with style variation plus rotation, is the same plan as the SynthPID idea.
- **What breaks on our images:** 384 px input would erase 5 to 20 px symbols on an 855 px plan; its object is one molecule per image while ours is 9 windows and 9 doors per plan, up to
  four plans on a sheet; hand-drawn results are not in the main text; MolScribe's aux graph head predicts atoms (one point each) while our windows are a cell strip.
- **Code and weights:** MolScribe code MIT (LICENSE read), weights HF card mit; DECIMER code MIT, weights CC-BY-4.0 (Zenodo). Usable as a reference implementation, not as a model (different domain, 384 px).
  Leakage flag: no (chemistry data).

### T1. Music scores: symbols on staff lines (staff-line removal and what replaced it)
- **Role of our object:** a notehead or rest (5 to 20 px) touching staff lines is a window cell or door leaf touching a wall line; the staff
  is the wall.
- **What the field learned:** The recent open recipe does not remove lines. Deep Watershed Detector (arXiv 1805.10548, ISMIR 2018, verified)
  applies no preprocessing beyond rescaling to an interline of 10 px (DeepScores) or 20 px (MUSCIMA++), trains on random 960 px crops and infers
  on whole pages; the paper does not describe any staff handling. Oemer (README, verified) goes the other way and segments staff lines as a
  separate output class of the same network, then uses the staff spacing ("unit_size") as the scale for everything else. The 2024 pipeline
  (2409.00316, verified) says staff removal is "a largely solved problem", works on already-staff-removed MUSCIMA++ images and reports
  mAP 84.79 (163 classes) and 94.22 (20 classes) at IoU 0.5 after cropping 1216 px windows down to 640 px. It never discusses a touching symbol.
  Two more papers, both read as PDF text (2026-11-14), close the gap I had listed:
  - Pacha et al., "Handwritten Music Object Detection: Open Issues and Baseline Results" (DAS 2018, verified): Faster R-CNN with Inception-ResNet-V2 (COCO-pretrained) reaches mAP 80% on MUSCIMA++
    (105 classes) and "the removal of staff lines only has a minimal impact on the results" (images with and without lines compared). Pages are cut into horizontal strips that each contain one staff and its
    objects, with about 15% overlap between neighbouring slices. R-FCN 75%, SSD 62%. Per class with the staff lines in place (Table II): notehead-full AP 99.89 on 21,333 test samples, 8th rest 99.60, beam 93.00, ledger line 92.18; the weak classes are rare or text-like ones (letter u 7.26, letter p 28.47, 16th flag 32.77). Anchors were shrunk to 8-64 px at stride 8 for the small objects. The authors' own caveat: the staff lines in the data are synthetic and "do not experience the usual distortions that apply to scans or pictures".
  - Géraud, "A morphological method for music score staff removal" (ICIP 2014, verified): a rule-only morphology chain won the ICDAR 2013 staff-removal contest on CVC-MUSCIMA (12,000 degraded handwritten
    images, six noise/distortion conditions): mean F-measure 0.97 against 0.94, 0.93, 0.90 (baseline), 0.89, 0.82, 0.67 for the other methods (Table 1); the library behind it (Milena/Olena) is GPL-2, so out for us.
    This is the one place where a hand-built structural method beats the field on degraded scans, and the task is removal of a known periodic structure, not counting objects.
- **Takeaway:** the music field ended up where our team is: structure rules are excellent at removing or locating the lines, detectors are better at the symbols, and keeping the lines costs little.
- **Why it transfers:** the practical rule is "normalise page scale by the structural unit, then detect with the lines left in". For us the unit is
  the wall thickness or the printed door width.
- **What breaks:** (1) our scale unit is not constant and not always drawn (a "not to scale" note, rotated pages, thin single-line walls in some
  styles), so a wall-thickness estimate can fail; (2) DWD's own touching case, same-centre objects, hurts: MUSCIMA++ noteheads detect worse where they
  overlap (Sec 4.3) and our three-pane window strips overlap the same way; (3) DWD and the YOLOv8 pipeline report AP, never exact per-page counts;
  (4) DeepScores pages are 400 dpi renders at about 1,894 x 2,668 px, ours are a median 855 px.
- **Code and weights:** DWD code MIT but TensorFlow 1.4.1 and Python 3.6, no weights. Oemer MIT, weights unlicensed, trained on CVC-MUSCIMA
  distortions (CC BY-NC-SA). The YOLOv8 pipeline is AGPL. **Idea only**: the transferable part is two lines of preprocessing, not code.
- **Dataset licences read:** MUSCIMA++ CC BY-NC-SA 4.0 (ufal.mff.cuni.cz/muscima); CVC-MUSCIMA non-commercial; DeepScoresV2 CC BY 4.0 on Zenodo.

### T2. Wireframe and line-segment detectors (3D vision)
- **Role:** a wall line or a door frame line is a line segment; windows are parallel lines in a wall.
- **Verified numbers (ScaleLSD paper Table 1, YorkUrban):** HAWPv3 Rep-5 S 0.711, DeepLSD 0.514, ScaleLSD@SA1B 0.725; #Lines per image 225, 310, 708. The paper
  reports repeatability, not sAP or F-score, and no drawing or line-art test.
- **First evidence on binary line art, and it is bad (HieroSA arXiv 2601.05508, 2026, Table 1, verbatim, glyph bitmaps of black strokes on white):** stroke coverage (CO) 1.4% for DeepLSD and 0.5% for ELSED,
  against 63.3% for the paper's own trained model (average over Chinese, Japanese, oracle-bone script); invalid-stroke rate 76.2% (DeepLSD) and 79.3% (ELSED). Table rows re-read verbatim 2026-11-14 through the headless browser. Caveats: these are glyph bitmaps, not plans; strokes are thick and curved; and the metric is the paper's own training reward (a stroke is "valid" only if all its sampled points lie in black pixels, coverage CO counts black pixels covered), which favours a model trained on it; the paper's Table 2 repeats the pattern on Make Me A Hanzi (DeepLSD CO 0.6, IS 91). It is the only published run of an off-the-shelf deep line detector on binarised line art that I found: it recovers almost nothing. It lowers my expectation for T2.
- **What breaks:** all of them train on photos of buildings (Wireframe, MegaDepth, SA-1B); thin 1 px line art with no texture is out of distribution
  and the 512 px input means a 855 px plan is downscaled by about 0.6 and 5 px symbols become 3 px. ScaleLSD returns about 700 lines per natural image,
  so on a plan the useful lines drown in hatching and furniture. No result exists on plans. Axis-aligned plans rotated by exact multiples of 90
  are friendly to them (repeatability under rot90 for the classical SweepLSD is 96-98%, Table 10, summary; the learned models were not tested).
- **Code and weights:** ScaleLSD code MIT, weights card apache-2.0, but trained on SA-1B whose overview page states "Research purposes only" (unresolved
  whether that reaches the weights; under record 0003 local use is fine, shipping needs a decision). DeepLSD code and weights MIT (README). Both work
  without training. One-hour test: run on 20 dev plans and see whether door-swing and window-pane segments appear. **Verdict maybe.**

### T3. Technical-drawing vectorisation (Deep Vectorization, 2020, and its 2024-2026 citers)
- **Role:** the plan's line work. Output: lines and quadratic Béziers with widths, no symbols.
- **Verified (re-read from the paper PDF text, Table 1 and Sec 4.2):** PFP floor plans IoU 86/88 vs 22 (CHD) and 60 (PolyVector); on the real degraded plans IoU 79/82 vs 47 (CHD), measured on only 15 hold-out images whose ground truth was cleaned by hand, text removed (81 images in all, ~1300x1000 px); trained four days on one V100;
  the input must be "cleared of text"; the cleaning network is trained on synthetic degradation then fine-tuned on 81 real photos (arXiv 2003.05471 HTML).
- **What breaks:** counts need symbols, and vectorisation will probably merge the collinear lines of a three-pane window strip into one stroke (my inference, not tested); text removal is
  a prerequisite we would have to build; the cleaning model is not released, so the real-scan robustness cannot be reproduced without the dataset.
- **Citers 2024-2026 (walked forward through Semantic Scholar, 74 citing papers, ~30 from 2024-2026):** SmartTracer, 2D Gaussian Splatting for Bézier line art,
  AnchorFlow (2605.19551), MARVEL manga vectorisation, TOVect, Astronomical diagrams decomposition (2403.08721). None evaluates plans. AnchorFlow (verified)
  tests only synthetically perturbed rasters, not scans, and reports no code link.
- **Code and weights:** MPL-2.0 (file-level copyleft; not on record 0006's list, so a decision is needed), archived, curve and line weights on Yandex Disk
  without a licence. **Skip for counting; maybe for a wall mask.**

### T3b. Sketch and line-art vectorisation with junction handling (Deep Sketch Vectorization, SIGGRAPH 2024)
- **Role of our object:** the plan's line work as a graph; door swing arcs and window pane lines as short strokes meeting a wall stroke at a junction.
- **Verified (paper PDF read as text, project page through the headless browser, repo and HF card read):** unsigned distance field network, then an improved neural dual-contouring network that is "more robust to noisy input",
  with explicit keypoint and under-sampling maps so "sharp features and multi-way junctions" survive. Benchmarks against Mo 2021, Bessmeltsev 2019, Puhachov 2021 at 512 px: Chamfer 15,413 vs 28,180 / 37,760 / 126,874 on clean
  strokes (Table 1) and 19,279 vs 66,310 / 243,620 / 186,947 on paper texture and stylised strokes (Table 2); on a rough set without ground truth the success rate is 100% against 44.6% and 17.9% for two baselines (Table 4).
  Table 5 (junction extraction on noisy distance fields, Gaussian noise at 1% of the field's standard deviation): precision 95.1% and recall 90.3% against 81.5% and 63.1% for the 3D neural dual-contouring baseline it improves on.
- **What breaks on our images:** it was trained on 441,000 rasters (63,000 vector sketches, 7 brush styles each, composited on random paper textures) and tested on 369 professionally cleaned sketches, not CAD plans; the paper (verbatim) says "Sketch consolidation and cleanup are outside the scope of our research" and lists as a limitation that "in the presence of very thick or noisy lines, or regions with complex topology" it may output multiple hatching lines instead of one (its Fig. 19), so text, furniture and hatching will come out as strokes;
  a 5 to 20 px symbol is a handful of strokes that will merge; the open repo issue #2 ("Technical sketch domain adoption") reports "some lack in point prediction" on technical sketches and has no reply; timing is 5 to 17 s per
  512 px image on the authors' machines and 72 s per image on a rough set (Table 4), too slow for tiling a 4k-plan set unless run once offline; pip dependencies read on PyPI: aabbtree MIT, edge_distance_aabb CC0, svgpathtools MIT, rdp MIT, eel MIT, but **ndjson is GPL-3** (dataset loading; replaceable by plain json lines).
- **Survey cross-check (Liu and Bessmeltsev, "State-of-the-art Report in Sketch Processing", Computer Graphics Forum 44(2), 2025, full text read from the open PDF):** "the majority of systems" support only clean raster sketches, and raster-to-raster cleanup
  (uneven lighting, canvas texture, low contrast, overdrawing) is the standard preprocessing step in front of them; its Fig. 18 shows that applying the 2024 clean-sketch vectoriser to an overdrawn rough sketch gives redundant strokes. So expect a cleanup stage in front of any line-first route on our scans.
- **Newer line-art vectorisers found (abstract only; the PDF links 404 or the journal is paywalled):** 2D Gaussian Splatting for Bézier Spline Line Art Vectorization (SIGGRAPH 2026, Disney Research and ETH Zurich, page read 2026-11-14): splits the skeleton graph of the sketch into subgraphs with depth-prediction and semantic-feature models to initialise strokes, then fits Béziers by Gaussian splatting; no code link found. SmartTracer (Computer Aided Geometric Design 2026, HKUST Guangzhou, search snippet and lab page only): interactive stroke extraction in tangled raster line art; no numbers read.
- **Code and weights:** MIT and MIT, usable as they are; fine-tuning needs vector ground truth, which we have as wall/door line geometry only for some CubiCasa5K labels. **Verdict maybe: one afternoon to see whether door arcs and wall gaps come out
  as clean strokes on 20 dev plans.** Leakage flag: no (QuickDraw, Creative Sketch).

### T4. Historical diagrams: primitives from synthetic data only (2403.08721, ICDAR 2024)
- **Role:** door swing = a line plus a quarter arc; window = pair of parallel lines.
- **Verified (Table 1):** a DETR-style detector trained purely on generated line, circle and arc images, evaluated on 303 real diagrams (3,076 primitives):
  mAP 0.722; AP_line 0.764, AP_circle 0.917, AP_arc 0.483; LETR zero-shot line AP 0.263. Synthetic images deliberately include shared endpoints, tangent
  circles and parallel lines.
- **What breaks:** arcs, the class we need for doors, are the weakest (0.483); it localises primitives, it does not say a primitive is a door; resized
  shortest side 480-800 px with no tiny-object results; code "will be made available" and the project page returned an empty body.
- **Takeaway:** matches our own measurement (Hough arcs 2 of 40). Treat a door-arc route as a research bet, not a second counter.

### T5. P&ID, circuits, PCB and flowcharts: symbols plus lines, graph out
- **Role:** a valve or component is our fixture symbol; pipes and wires are walls; counting components is counting fixtures.
- **Verified:**
  - Stürmer et al. (2411.13929, v3 2025-12): jointly detect symbols and edges with a Relationformer on 512 px patches of 4500x7000 pages;
    OPEN100 symbol mAP 73.14, edge mAP 75.46 vs a modular detector+Hough pipeline at 76.99 and 45.89 (Table III). **The modular route wins on symbols,
    the joint route wins on edges.** No code.
  - SynthPID (2604.16513, 2026): 665 synthetic pages made by perturbing the collapsed graph of 12 real plans and re-rendering; node mAP@0.5 64.2 trained on
    synthetic only, 67.8 on real only, 71.3 mixed; per-class symbol AP from 48.3 (general) to 77.6 (tank). Evaluated on the same 12 plans that seed the synthesis,
    so read the zero-real number with care; the OCSR field (T0) shows the opposite for synthetic-only training: MolParser 51.9 pretrain-only vs 76.9 with real fine-tune. Repo returns 404.
  - SINA (2601.22114, 2026-01): component detector, then bounding-box masking and connected-component labelling for wires, small stubs and loops dropped;
    claims netlist accuracy 96.47% but Table I and Table II disagree on component F1 (96.47 vs 99.6) and the hand-drawn split is not reported.
  - AMSNet (2405.09045): flood-fill from boxes, odd-sized groups flagged for manual fix (a "person checking the machine" pattern).
  - PCBnet (2608.27923, 2026-08): YOLOv11 + U-Net wires + skeleton; connectivity accuracy 84.47; this is schematic, not board artwork. No board-image trace paper found.
  - FlowExtract (2604.06770): node F1 98.8, edge F1 66.7.
  - Node-link diagram segmentation (arXiv 2606.11320, 2026-06, read in full): a compact two-branch fully convolutional net on 128x128 px patches of synthetic Graphviz diagrams, pixel accuracy 93.7% on test patches (93.6% without JPEG augmentation); pixel accuracy only, no node or edge counts, no real scans, no code link. Nothing to take except that whole-image inference by patches with a fully convolutional net is accepted practice.
  - Grounded and Faithful P&ID Reasoning (arXiv 2609.05880, 2026-10 v2, abstract and about 40k characters plus the tail read verbatim, middle tables summary only): learned symbol detector (tiled YOLO11s, detection F1 0.983 on the test set), learned
    line masks (U-Net, Dice 0.982), then deterministic graph rules (skeleton, noding, snap); "the graph builder does not invent edges with a learned model". The verbatim line that matters for us: a fixed 10 px snap collapses exact edge F1 to 0.193 on
    predicted solids, against 0.742 with an adaptive snap. Synthetic sheets only; scanned drawings are listed as future work (summary).
  - Bailo et al. (2511.08609, 2025-11): learned scene-graph model, 93% of components identified, hierarchy about 80% (abstract, verbatim); proprietary data, no code. Prusty et al. (2505.11976): line-segment merging, abstract only.
- **Why it transfers:** the consistent pattern is detect the symbols, mask them out, then analyse what is left. For us: detect fixtures, mask them, then use the
  remaining line map (walls, door arcs) as a consistency check on door and window counts.
- **What breaks:** these are drawn on white with uniform line weights and printed symbol libraries; ours mix four or five CAD styles, rotated pages and photos.
  SINA's training set is 700 schematics, ours is 3,828 plans with 104k boxes, so we have more labelled data than any of them. None of them reports exact per-page counts.
- **Code and weights:** FlowExtract MIT; everything else unreleased or unverifiable. **Only the synthesis recipe (SynthPID) is worth keeping.**

### T6. Road-network and HD-map extraction
- **Role:** a wall network as a graph; junctions as wall joins.
- **Verified:** SAM-Road (2403.16051, CVPRW 2024) predicts road and intersection masks, merges vertices with the intersection ones taking priority, then classifies
  edges between neighbours within 64 px: City-scale F1 77.23, APLS 68.37; LineGraph2Road (2602.23290, 2026) adds an overpass head, F1 82.37. MapTR (ICLR 2023) models
  ordered point sets with permutation-equivalent matching, mAP 50.0 (tiny) on nuScenes. SAM-Road MIT code and MIT weights card; GSMap (2026) has no code.
- **2026 cross-check (MARS, arXiv 2610.20843, read in full):** an autoregressive map model emits class and quantised x/y tokens for roads, buildings and water from 512 px aerial tiles; roads are cut at junctions with the stroke-splitting algorithm of Deep Sketch Vectorization; Cityscale TOPO F1 82.88 vs 78.44 for RNGDet++ (Table 3); no code or weights link, aerial imagery only, no scans or line drawings tested. It shows the Pix2Seq-style token output (the same family as Raster2Seq in the field scope) beating graph decoders on roads, nothing more.
- **What breaks:** the output is a graph, not a count; tiles are 1 m/px aerial or multi-view camera BEV, nothing like a plan; SAM ViT-B at 512 px loses 5 px symbols.
  **Skip.** The one idea is a separate junction map with priority in vertex NMS, which would help only a wall-graph plan splitter (another scope).

### T7. Font, logo and clipart vectorisation
- **Verified:** StarVector (2312.11556, CVPR 2025) writes SVG text from a 384 px image; SVG-Diagrams Dino 0.959 vs LIVE 0.870 (README); no junction or thin-stroke metric;
  code and HF weights both Apache-2.0. LIVE and DiffVG (Apache-2.0) optimise per image from scratch (500 iterations per stage on 240 px emoji); DiffVG is a renderer, not a vectoriser.
- **What breaks:** 224 to 384 px input would shrink a 855 px plan by half and erase 5 px symbols; output has no semantics (a path is not a window); token limits truncate complex input
  (paper). **Skip.**

### T8. Historical and cadastral maps
- **Verified:** mapKurator is text spotting plus geocoding (README), no line features and no code licence file. arXiv 2410.02250 (2024) extracts roads from a map, skeletonises and
  vectorises: completeness above 94%, correctness above 92% (abstract); no code. I found no cadastral-boundary vectorisation paper on arXiv. **Skip.**


## 3b. Repo checks (LICENSE, dependencies, open issues; read 2026-11-14 with gh)

- **DeepLSD and ScaleLSD both depend on `pytlsd`.** DeepLSD's requirements.txt lists `./third_party/pytlsd`; ScaleLSD's requirements.txt lists `pytlsd@git+https://github.com/iago-suarez/pytlsd.git`
  (GitHub code search: imported only in `line_matching/wireframe.py`, line 3 `from pytlsd import lsd`, the two-view matching demo; the predictor path under `predictor/` does not mention it, so single-image detection looks AGPL-free, but the requirements file installs it regardless). The pytlsd repo is labelled MIT (LICENSE read) but its README says it is bindings
  "over the original C implementation of LSD", and `src/lsd.cpp` carries the original header "GNU Affero General Public License" (read). So a pipeline that calls pytlsd ships AGPL code under an MIT label.
  Rule for us (record 0006): AGPL is out. DeepLSD imports pytlsd in `deeplsd/models/deeplsd.py` and `deeplsd_inference.py`, so it is out unless that path is replaced; ScaleLSD's single-image path does not import it.
- **HAWP:** licence issue #45 was answered by the author, "MIT License is great and I will add it later"; the GitHub licence field shows MIT now. Open issues are mostly custom-training questions (#37, #40, #42, #50, #56).
- **Deep Vectorization of Technical Drawings:** open issue #33 "Pretrained line checkpoint download unavailable", #10 "Cleaning model weights" (no answer), #25 floor-plan download script broken. The released route is
  effectively not reproducible, which closes the door on T3.
- **MolScribe:** open issue #41 reports 55,482 s for one epoch on 8x RTX 3090 (their own run with extra files), so training from scratch is not a night job; fine-tuning only.
- **Deep Sketch Vectorization:** README has training instructions and the repo ships `utils/texture_syn.py` (paper-texture synthesis) and `dataset/`; optional preprocessors are Anime2Sketch (MIT) and line_thinning (licence NOASSERTION, optional); open issues #2 (technical sketches) and #3 (data preprocessing fails with current PyPI dependencies). Training from scratch is 72 A100 hours in the paper, so we would only run inference.
- **VecFormer:** issue #5 (maintainer, verbatim gist): the weight files were lost and will not be re-released; issue #4: a 48 GB card ran out of memory, the authors trained on 8x 80 GB A100. Apache-2.0 code, no weights.
- **SymPoint-V2:** open issue #6 "Can I use this for commercial project?" has no answer; issue #14 asks which licence applies to the released checkpoint, also unanswered; no LICENSE file in the repo.
- **ScaleLSD:** HF card says use the v2 checkpoint (LayerScale, AdamW), "works much better than v1 (the model evaluated in our paper)", so the paper's numbers are for v1.
- **Deep Watershed Detector:** no issues found by keyword (TF 1.4, Python 3.6).

## 4. Citation graph walked forward (via Semantic Scholar through the headless browser)

- **SymPoint (ICLR 2024)**: 17 citers listed. 2025-2026: PolarSym (2608.11793), TempFit (2610.17776), Training-Free Agentic CV for structural framing plans (2608.17237),
  Text-Aided Multi-Modal (2607.12678), Text-Enhanced (2510.11091), CAGE (2509.15459), VecFormer (2505.23395), ArchCAD-400K (2503.22346), FUSEPOINT for defective CAD drawings (SPIE 2026, paywalled, not read),
  a curvature-adaptive point-cloud method for CAD completion (Meas. Sci. Technol., not read), keypoint localisation for rectangle symbols (Multimedia Systems 2026, not read). All take vector primitives.
  2608.17237 (verified): rule passes on vector PDFs, columns recall 0.922 / precision 0.997, no raster results, no code.
- **Deep Vectorization of Technical Drawings (ECCV 2020)**: 74 citers listed, about 30 from 2024-2026; relevant ones listed in T3.
- **ScaleLSD (CVPR 2025)**: 7 citers, none on drawings (SweepLSD, ADLA, point-line features, 3D line mapping, BT-LSD not found on arXiv).
- **MolScribe (2022)**: 121 citers, 85 from 2025-2026 (listed in T0; read MolParser, MolSight, 2608.09100, VERDICT, ViCoR, COMO in full, others by title only).
- **DeepLSD (CVPR 2023)**: 126 citers, about 70 from 2025-2026, mostly SLAM and 3D line mapping; the only drawing-like ones are HieroSA (read), PolyLayout (2608.03323, layout estimation, not read), and two titles I could not find ("Vectorization Method Based on Improved DeepLSD", "Lightweight Geometric Consistency Enhancement for One-Stage Architectural Line Segment Detection").
- **Deep Sketch Vectorization (TOG 2024)**: 12 citers, 2025-2026 titles only (Gaussian splatting for Bézier line art, SmartTracer, Single-Line Drawing Vectorization, LineDrawer, Sketch2Data, a CGF state-of-the-art report on sketch processing); only MARS (2610.20843) was readable.
- **Relationformer P&ID (2411.13929)**: 12 citers, all 2025-2026 (read: SynthPID, FlowExtract; Enginuity 2601.13299 is a workshop proposal with no baselines or data release; others are retrieval or LLM papers; a railway signal-layout tile-consolidation paper is listed but not findable on arXiv).

## 5. Sources read (count)

Sources opened (date 2026-11-14): about 60 pages, repos, papers and licence files (log lists them), of which 2025-2026 papers read: MolSight, MolParser, 2608.09100, VERDICT, ViCoR, COMO, ScaleLSD, VecFormer, TempFit, CAGE, PolarSym, TextCAD, 2510.11091, SINA, PCBnet, FlowExtract, SynthPID, Relationformer P&ID v3,
SALI-FP, 2608.17237, AnchorFlow, LineGraph2Road, GSMap, SweepLSD, ADLA, SkeySpot, 2606.01910 (21 items). Full list in `lit-vector-b-log.md`.

## 6. Looked for and did not find

- Any deep line detector (ScaleLSD, DeepLSD, HAWP, M-LSD, LETR) evaluated on floor plans, drawings or scans. The nearest is HieroSA's glyph-bitmap run (DeepLSD recovers 1.4% of strokes); on plans, nothing. Second attempt with other terms (architectural, F-Clip, wireframe building) also found nothing.
- Any raster-derived or noisy primitives fed to SymPoint, CADSpotting, VecFormer or TempFit. All train and test on true CAD primitives (second search with other terms, same result).
- Any head-to-head of a rule/structural opening detector against a learned one on the same plans. The nearest is an Aalto master's thesis (2021, abstract read through the headless browser, PDF not read): CNN and U-Net models compared with traditional image-processing methods from the literature, the networks found "fairly flexible" over styles, 90% label accuracy for the 9M-parameter net vs 93% for a 17M-parameter reference; no numbers for the traditional methods in the abstract. A 2022 review (Automation in Construction, rule-based vs learned floor-plan analysis) belongs to the field scope L1. Otherwise found it only in other fields: chemistry (OCSR, T0) and music staff removal (T1).
- ICDAR/GREC staff-removal numbers: found on the second try (Géraud, mean F 0.97 on the 2013 contest). Still missing: how touching symbols are scored in that contest (second search, 2020-2023 papers: no separate overlap F-measure found).
- PCB trace extraction from board photos: only a classical open tool (re:trace, MIT, no accuracy numbers) and schematic work; the MDPI 2024 X-ray paper refused (403).
- A cadastral or historical-map line-vectorisation paper with scanned inputs: searches return remote-sensing parcels (CadNet and similar), not scanned maps; mapKurator is text only.
- Code for the astronomical-diagram primitive DETR, for 2D Gaussian Splatting line art, SmartTracer, and weights for SynthPID, ViCoR, VERDICT (repo 404); "Vectorization Method Based on Improved DeepLSD" and the 2026 architectural line-segment paper were listed as citers but are not findable by title.
- Paywalled or refused: ACM (mapKurator), MDPI, Springer, FUSEPOINT (SPIE), a Cloudflare-protected journal PDF for a 2025 YOLOv12 notehead plus rule-based pitch paper (not circumvented), dblp (access challenge): abstract-only or search-snippet at best.

## 7. Open questions and missing tools

1. ScaleLSD weights: the card says apache-2.0 but the training set SA-1B is "Research purposes only". Does a local scored run need a decision from the team (record 0003 rule: weights from non-commercial data stay local)?
2. Do DeepLSD/ScaleLSD lines, or Deep Sketch Vectorization strokes, on a 20-plan dev sample contain door-swing and window-pane segments? Nobody has published this; one afternoon decides T2 and T3b. DeepLSD imports pytlsd (AGPL LSD source); ScaleLSD lists it in requirements but imports it only in a matching demo: needs a licence decision before any shipped use.
3. Is wall thickness (or printed door width) a reliable per-sheet scale unit to normalise by, as OMR does with the staff interline? Belongs to the sheet scope (L9); one line there.
4. MPL-2.0 (Deep Vectorization) is not on the record 0006 list. Needs a decision only if the team ever wants it.
5. For other scopes: VERDICT/ViCoR (OCSR agreement and render-and-verify) belong to the trust scope L10; the real-fraction dose series (2608.09100) to the data scope L8: one line each, not dug into further.
6. Other scopes (continued): two engineering-drawing symbol-detection papers surfaced only as search snippets and belong to the detection scope L2: few-shot symbol detection in engineering drawings (Applied Artificial Intelligence 2024, under ten training instances per class) and a YOLOv11 / Faster R-CNN / RetinaNet comparison on GD&T symbols (J. Intell. Manuf. 2025, Springer, not opened). Also: MuraNet and Raster2Seq belong to the floor-plan scope (L1), CAGE/SALI-FP to rooms (L4), FlowExtract-style graphs not needed. SALI-FP's CubiCasa5K nets baseline (room F1 0.6305) is a room-scope number.
7. Missing tools: no arXiv MCP, Semantic Scholar API throttles web-fetch (used the headless browser instead), ACM, Springer and MDPI pages refused, Hugging Face card for DeepLSD weights not opened (README states MIT), the ScaleLSD HF card was opened.
