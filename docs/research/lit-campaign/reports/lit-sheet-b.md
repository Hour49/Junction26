# lit-sheet-b: sideways transfers for sheet layout, orientation and quality gating (scope L9, angle b)

Worker lit-sheet-b, read-only. All sources read on 2026-11-14 (Helsinki). Reading log with one line per source:
`lit-sheet-b-log.md`. Marks: **verified** = I (or the fetch agent I briefed) read it on the page
named; **reported** = the authors' own claim; **estimate** = mine. Pages read through the fetch agent were often cut
at about 40k characters; where a number comes from the part that was only summarised it is marked "summary" and is
not relied on. Earlier reports (`stoa-hardimg*`, `lit-normalise`, `lit-degradation`) are extended, not repeated: this
report covers sheet splitting, plan counting, orientation from structure, quality gating, and what the adjacent
fields measured.

Leakage: none of the checkpoints below was trained on CubiCasa5K or a repackage of it. Every one is trained on
documents, biomedical figures, comics or drawings of other kinds, so the flag is **no** (training data of the
PaddleOCR orientation models is not stated, so for those it is **unknown, not floor plans as far as the cards say**).
Weights that would be trained on our own dev images are leakage-safe only for the 3,828 dev images (record 0003).

Numbers that anchor everything: plans per sheet on dev are 1 plan 3,044, 2 plans 672, 3 plans 109, 4 plans 3 (context
file), so "always answer 1" is already 3,044 / 3,828 = 79.5% on that template (my arithmetic). The room for gain is the
other 20.5% of that template, about 1.5 points of overall score (context file).

## 1. Top 5 (floor-plan work and transfers in one list)

1. **Train a box detector for "plan regions" on synthetic multi-plan sheets built from our single-plan images
   (transfer from compound-figure separation, biomedical papers).** Open-PMC-18M (arXiv 2506.02738, 2025) trains
   DAB-DETR on 500,000 programmatically composed compound figures, with ground-truth panel boxes free by construction
   (grid size, margins, labelling scheme, aspect ratio are the knobs). It reaches mAP 98.58 / F1 99.96 on its own
   synthetic hold-out but only mAP 36.88 / F1 73.55 on the real ImageCLEF 2016 set, still above the previous
   real-data detector (28.20 / 64.85). The older paper that started the idea (Tsutsui and Crandall, arXiv 1703.05105,
   YOLOv2 at 544 px, read in full 2026-11-14) only ever added synthetic grids to real training data: on ImageCLEF 2016
   per-figure accuracy went 0.846 (ImageNet transfer) to 0.859 with grid composites, mAP 0.773 to 0.782, and random
   pasting did not help (0.842). Verdict: **try**, mixed with the real multi-plan sheets (784 dev sheets have 2+ plans:
   672+109+3), not as a replacement; expect a large synthetic-to-real gap and hold out real dev sheets to measure it.
   Source: https://arxiv.org/html/2506.02738 (read 2026-11-14, pwfetch full text; verified). Code
   github.com/vectorInstitute/pmc-data-extraction Apache-2.0 (gh api 2026-11-14). **Weights exist, Apache-2.0 card:**
   huggingface.co/vector-institute/pmc-18m-dab-detr (card read via curl 2026-11-14, `license: apache-2.0`, 43.75M
   parameters, ResNet-50 backbone, 300 queries, one class `subfigure`, preprocessor resizes to 480 x 480, loads with
   transformers; config files read by curl; the repo also holds optimizer, scheduler and trainer state, so a fine-tune can resume from it), trained on biomedical panels, so leakage **no**. A zero-shot run on 30 dev
   two-plan sheets is a one-hour test of whether a figure splitter splits plans at all. Repo health (gh, 2026-11-14): 9
   open issues, last push 2026-07-13; closed issue #39 shows users could not find a `.pth` detector file in the repo
   (the maintainers pointed to new CLIP models), so the Hugging Face copy is the usable artefact; pyproject lists no
   GPL or AGPL dependency in the lines I checked (opencv-python, torchaudio, open_clip_torch).
2. **Use RF-DETR (Apache-2.0) as the region detector and do not start from a document-layout checkpoint (transfer:
   AEC drawing-sheet layout benchmark, EC3 2026).** arXiv 2607.18997 benchmarks five models on 551 facade-engineering drawing
   sheets (10 real projects; the FELD dataset) with nine layout classes (title block, notes, legend, sections, elevation, plan): RF-DETR-m mAP50 0.949 /
   mAP50:95 0.890 at 1344 x 800, Faster R-CNN 0.930 / 0.779, YOLOv12-m 0.871 / 0.755, Qwen3-VL-8B 0.758 / 0.668.
   On its "Plan" class alone (mAP50:95): RF-DETR-m 0.969, Faster R-CNN 0.775, YOLOv12-m 0.510, Qwen3-VL-8B 0.330.
   Caution (re-read in the PDF, Table 1, 2026-11-14): the Plan class has only 21 images and 26 boxes, and the authors themselves say Plan and GA section "yield the lowest scores" across models because of the small sample; so 0.969 is one model on a tiny class (probably few test boxes), not evidence of plan detection quality. Trust the all-class 0.949 / 0.890 and the architecture ranking, not the Plan number.
   The same paper measures "domain interference": DocLayout-YOLO pretrained on DocLayNet and DocSynth scores
   0.675 mAP50, below the same architecture without the document pretraining (0.854) and the plain COCO YOLOv10m
   baseline (0.900). So
   document-layout pretraining hurts on drawings. RF-DETR repo: Apache-2.0, and its README (read 2026-11-14) says the Nano, Small, Medium and Large detection and all Seg
   models are Apache-2.0 while Atto, Femto, Pico, XL and 2XL fall under the Roboflow PML 1.0 (so weights as well as code for
   the sizes recommended here are Apache-2.0); pyproject pulls supervision and torchmetrics, no Ultralytics (checked), open issue #879 asks
   for the minimum detectable object scale and the answer (read) is that no fixed bound is known, so the size gate has to
   be measured on our data. Verdict: **try** (detector choice and "do not use Docling,
   PP-DocLayout or DocLayNet weights" in one line). Source: https://arxiv.org/abs/2607.18997 and the saved PDF, read
   2026-11-14 (verified, tables 1-4). Its dataset and code are not linked.
3. **Orientation: make detection rotation-proof by training, and fix only text with a voting stack; there is no proven
   structure-only orientation method for plans.** Verdict: **try as a 1-hour measurement**: PP-LCNet_x1_0_doc_ori
   (4 classes 0/90/180/270, Top-1 99.06% on a 1,000-image self-built ID/document set, 7 MB, 3.24 ms on CPU; Apache-2.0
   card) zero-shot on 50 dev images, vote it with the 0/180 text-line classifier over every detected label
   (98.85% / 99.42%), and compare with a 4-way rotation classifier we fine-tune on dev plans, where the labels are free
   (rotate an upright image). What the sideways evidence says: Tesseract OSD cannot work (it needs 50 characters, §3.3),
   VLMs cannot tell 90 from 270 (RotBench, §3.3), and rotation prediction as a task is ill-posed only for images with
   no "up" (Gidaris). Sources: https://www.paddleocr.ai/latest/en/version3.x/module_usage/doc_img_orientation_classification.html
   (read 2026-11-14, verified), HF cards (curl, 2026-11-14), https://arxiv.org/html/2508.13968.
4. **Quality gate built the way biometric quality is built: named defect components, each validated by an
   error-versus-discard curve against our own count error (transfer: face and fingerprint capture quality).**
   OFIQ (MIT licence file) computes 21 named components (sharpness, compression artefacts, inter-eye distance, head size,
   exposure...) each mapped to 0-100, and checks each with EDC curves. On its test set discarding the 10% lowest by
   Sharpness / compression artefacts cut false non-match from 10% to 8%, while exposure-type components only reached
   9.5%: most "defects" do not matter, a few do, and EDC tells you which. NFIQ2 (public domain; NIST IR 8382 read in full from the PDF with pypdf) predicts utility with a random forest over 14
   features, picked from 155 implemented ones by dropping weak, slow and Spearman-redundant features and then pruning by
   forest importance; the label comes from comparison scores of several commercial matchers on operational data, score
   0 to 100, tuned for 500 dpi plain impressions. Verdict: **try the protocol, not the code**: define components that matter for
   us (symbol height in px, sharpness, JPEG blockiness), plot count error against fraction discarded, and pick the
   threshold at a discard fraction of 0.3 or less (the evaluation paper's rule). Sources: OFIQ short report PDF
   (read 2026-11-14 via pypdf, verified), https://arxiv.org/html/2303.13294 (EDC definition, verified, 40k verbatim),
   https://pages.nist.gov/NFIQ2/docs/v2.2.0/index.html.
   Round 4 additions (section 3.5): a 2026 DHS-funded study (secondary source) found OFIQ's single blended score of
   "extremely limited utility", which supports gating on named components; a 2025 map-sheet paper shows exact match
   collapsing with input resolution on whole sheets (0 % at 480x640, 65-67 % at 1200x1600) but not on a crop (84-86 %).
5. **Group detected elements into plans with a learned edge classifier over boxes (transfer: newspaper and
   historical-page logical segmentation, TextBite 2025).** YOLOv11 boxes (1,200 px) plus a GNN that classifies which
   boxes belong to the same segment give Rand index 92.5 on 8,449 pages with 78,863 segments, versus 83.9 for YOLO
   alone (verified, 40k verbatim). Verdict: **maybe**: it needs a box set with a plan-membership label, which we do
   not export yet (per-plan box not exported, context file §2); run it only if idea 1 stalls. Code MIT
   (LICENSE file read), dataset licence not stated. Full text re-read with the headless browser: the GNN is a complete
   graph over detected boxes, 29 geometric node features and 12 edge features (12 include a text-embedding similarity
   that we would drop), Residual Gated Graph Conv, 3 layers, width 512, AdamW 1e-3, edge score by cosine similarity.
   Repo health: its only issue (#1, open) says the repo is incomplete (`textbite.models` missing), so expect to
   re-implement. Source: https://arxiv.org/html/2503.16664 (read 2026-11-14).

Put aside, with the reason: Docling heron/egret, PP-DocLayout(V3), MinerU (text-document classes, domain interference
above, and MinerU's licence field is NOASSERTION); Tesseract OSD (50-character floor); VLM orientation (RotBench);
GPL comic and figure tools (Comic-Panel-Extractor GPL-3.0, ExSCLAIM GPL-3.0); CR-FIQA (CC BY-NC 4.0).

## 2. Full table

Columns: method; field it comes from; year and venue; code and licence; weights and licence; training data and
leakage flag; metric and benchmark; input size and GPU; hours to a first number on our dev data (estimate); JSON
field it fills; verdict. Licences read with `gh api repos/<r>/license` or from the file or card, 2026-11-14.

| # | Method | Field | Year, venue | Code, licence | Weights, licence | Training data, leakage | Metric, benchmark | Input, GPU | Hours (estimate) | Fills | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | DAB-DETR on synthetic compound figures (Open-PMC-18M) | compound-figure separation, biomedical | 2025, arXiv 2506.02738 (MICCAI 2026 per repo README) | vectorInstitute/pmc-data-extraction, Apache-2.0 | vector-institute/pmc-18m-dab-detr, Apache-2.0 card, 43.75M params | 500k synthetic figures from 7 panel sources; no | mAP / F1: synthetic 98.58 / 99.96, ImageCLEF 2016 36.88 / 73.55 | 480 x 480 resize (preprocessor_config.json), ResNet-50; train GPU not stated | 3 to 4 (compose, train RF-DETR or D-FINE on our boxes) | `plans` | try |
| 2 | RF-DETR-m on drawing-sheet layout | AEC construction drawings | 2026, EC3, arXiv 2607.18997 | not linked | not linked | 551 facade sheets, 10 projects (Plan class only 21 images); no | mAP50 0.949, mAP50:95 0.890, 44.8 ms | 1344 x 800; GPU not stated | 3 (same as row 1) | `plans` | try |
| 3 | Label-anchored two-stage subfigure detector | compound figures | 2021, ICIP, arXiv 2101.09903 | MaterialEyes/exsclaim, GPL-3.0 | not stated | about 800 train figures from journals; no | AP50 90 / AP75 82 / AP50:95 72 | YOLOv3 Darknet-53; not stated | idea only | `plans` (anchor: printed floor titles) | skip code, keep the idea |
| 4 | Consensus of three independent panel counters (labels, sub-captions, connected components) | biomedical figure segmentation | 2013, BMC Syst Biol (CC BY 2.0 article) | no code stated | n/a | 2,256 articles, 41,341 panels; n/a | 96.64% of 41,341 panel-caption pairs recovered; **exact panel count right in 11,973 of 13,147 figures = 91.07%** (verified in the Europe PMC full text); 9,294 of those by consensus of labels, sub-captions and connected components | n/a | idea only | `plans`, and the stage-8 second counter | maybe: the one exact-count result found |
| 5 | Band and edge separator recursion | compound figures | 2016, arXiv 1606.01021 | none stated | n/a | ImageCLEF 2015; n/a | CFS 84.9% on ImageCLEF 2015 test | CPU, 0.3 s per figure (MATLAB, Intel E8400 3 GHz) | 2 | `plans` | skip: borderless panels fail |
| 6 | Box detector then GNN edge grouping (TextBite) | newspaper and historical pages | 2025, arXiv 2503.16664 | DCGM/textbite-dataset, MIT | baselines on Zenodo 77.3 MB, licence not stated | 8,449 pages; no | Rand index 92.5 vs 83.9 YOLO alone | YOLOv11 small 1200 px | 4 | `plans` | maybe |
| 7 | XY-Cut++ geometric recursive cut after a detector | document reading order | 2025, arXiv 2504.10258 | not stated | n/a | n/a | DocBench-100 BLEU-4 0.988; OmniDocBench 0.953 | CPU 514 FPS mean (ordering only) | 2 | ordering of plans, `plans` | skip: orders blocks, does not count |
| 8 | Docling heron / egret layout models | document layout | 2025, arXiv 2509.11720 | docling-ibm-models MIT | heron card Apache-2.0 | DocLayNet + proprietary + WordScape; no | mAP 0.699 DocLayNet, AP-small 0.519 | 640 x 640; 28 ms A100 for heron-101 | n/a | none | skip: domain interference |
| 9 | PP-DocLayout-S/M/L and V3 | document layout | 2025, arXiv 2503.17213 and 2606.23344 | PaddleOCR Apache-2.0 | cards Apache-2.0 | self-built text docs; no | mAP50 70.9 / 75.2 / 90.4 on its own 500-image set | 1.21 M params, 14.5 ms CPU for S | n/a | none | skip: same reason |
| 10 | PP-LCNet_x1_0_doc_ori | document orientation | 2025, PaddleX / PaddleOCR 3.x | PaddleX Apache-2.0 | card Apache-2.0 | not stated; unknown | Top-1 99.06% on 1,000 ID/document images | 7 MB, 3.24 ms CPU | 1 | orientation for OCR | try (measure) |
| 11 | PP-LCNet text-line orientation | OCR | 2025, PaddleOCR 3.x | Apache-2.0 | cards Apache-2.0 | not stated; unknown | 98.85% (x0_25), 99.42% (x1_0), 0/180 only | 0.96 / 6.5 MB | 1 | label orientation | try |
| 12 | 4-way rotation classifier (AlexNet on SUN397) | photo orientation | 2017, arXiv 1712.01195 | not stated | n/a | SUN397; no | 95.16 / 95.28 / 90.88 / 90.77 on SUN397 / Indoor / Holidays / Pascal | 256 x 256 | 2 (fine-tune on dev plans, free labels) | orientation | maybe |
| 13 | Rotation prediction as pretext (RotNet) | self-supervised vision | 2018, arXiv 1803.07728 | gidariss/FeatureLearningRotNet, MIT (gh api) | n/a | CIFAR-10, ImageNet; no | no rotation-accuracy number in the full text (re-read); says round objects are ill-posed | n/a | idea only | orientation | idea |
| 14 | MLLM orientation (RotBench) | VLM benchmark | 2026 revision, arXiv 2508.13968 | tianyiniu/RotBench Apache-2.0 | n/a | photos | best zero-shot 270 degree accuracy 0.59 (GPT-5); "all models exhibit substantial difficulties when distinguishing between 90 and 270 degrees" (verbatim) | API models | n/a | none | skip |
| 15 | Tesseract OSD | OCR engine | maintained, push 2026-11-13 | tesseract Apache-2.0 | n/a | n/a | needs 50 characters (min_characters_to_try=50) | CPU | n/a | none | skip |
| 16 | OFIQ component quality with EDC | face image quality, ISO/IEC 29794-5 | 2024 report, repo active | BSI-OFIQ MIT (LICENSE.md; dependencies differ) | model files and their licences not checked (LICENSE.md says dependencies differ) | VGGFace2 for evaluation; no | discard 10% by sharpness: false non-match 10% to 8% | C++, CPU | 3 (own components) | gate | try the protocol |
| 17 | NFIQ2 | fingerprint quality, ISO/IEC 29794-4 | v2.2/2.3 | usnistgov/NFIQ2 public domain (LICENSE.md) | random-forest params in repo, public domain | NIST data; no | score 0-100, 14 features chosen from 155, random forest trained on matcher comparison scores (NIST IR 8382, verified) | C++, OpenCV 4 | idea only | gate | idea |
| 18 | EDC evaluation protocol | biometric quality evaluation | 2023, arXiv 2303.13294 | dasec/quality-assessment-evaluation Apache-2.0 | n/a | n/a | pAUC over discard fractions up to 0.3 | n/a | 1 | gate evaluation | try |
| 19 | CR-FIQA quality from class-centre geometry | face image quality | 2023, CVPR | fdbtrs/CR-FIQA CC BY-NC 4.0 (README) | NC | MS1MV2, CASIA | ERC AUC 0.0138 IJB-C | R50/R100 | n/a | gate | skip: NC, needs identity labels |
| 20 | Classical panel finder (Otsu, closing, RETR_EXTERNAL) | comic panel extraction | 2026-03, technical note | ehsanx/Comic-Panel-Extractor GPL-3.0 | n/a | n/a | no accuracy stated | CPU | idea only | `plans` | skip |
| 21 | Faster R-CNN / YOLOv8 / Magi on comic panels | comics | 2024, ICDAR workshop | emanuelevivoli/cdf, no licence file | not stated | 5 comic sets; no | panel mAP avg 79.5 / 74.3 / 78.5 | 1024 x 1024 | n/a | `plans` | skip: shows borderless panels cap at about 80 |
| 22 | YOLO12-m panel detector (MatMMExtract) | materials-science figures | 2026, arXiv 2606.29667 | CMEG-IITR/matmmextract GPL-3.0; training code cmpfig MIT (gh api) | CMEG-IITR/yolo12_unique_multimat on Hugging Face, licence not read; MaterialScope data CC BY-NC 4.0 | 2,811 figures; no | mAP50 0.9227, P 0.9601, R 0.9406 at 1024 px | RTX A6000, 13.76 img/s | idea only | `plans` | skip: YOLO12 is AGPL, pipeline GPL-3.0, data NC |
| 23 | Map content segmentation, sheet level | historical maps | 2021, ICDAR | winners' gitlab, licence unread | n/a (dataset on Zenodo, CC BY 4.0 per its record) | 132 Paris sheets; no | Hausdorff-95 19 px (best) | 10,000 x 10,000 px | n/a | none | skip: one map body per sheet |
| 24 | Drawing-specific ESRGAN restorer plus Faster R-CNN (power single-line diagrams) | engineering drawings | 2023, arXiv 2312.13620 | not linked | not linked | partner's private diagrams, synthetic degradations; no | symbol recall 99.33% vs 32.74% interpolation at IoU 0.9 | 200 px restore patches 4x, 1000 px detect patches | 6 to 8 (pairs, train, A/B) | all counts | maybe: A/B only |
| 25 | Comic MTL (Faster R-CNN family, multi-task) | comics | 2019, IJDAR | not checked | not checked | DCM772, eBDtheque; no | panel F1 at IoU 0.5: 97.76 / 91.50; older classical 65.6-83.8 | not stated | n/a | `plans` (upper bound for framed panels) | skip: per-box not exact count |
| 26 | Page, system, staff-height regression, crop pipeline (OSSQ-OMR) | optical music recognition | 2026, arXiv 2608.10978 | not read; YOLOv8 is AGPL-3.0 | not read | 1,804 pages + 47; no | no system-detection metric in the text read | YOLOv8 x3 | n/a | scale per crop | idea only (copy the order, use RF-DETR) |
| 27 | YOLOv11 view / title block / notes detector | mechanical multi-view drawings | 2025, arXiv 2510.21862 | not linked; YOLOv11 AGPL-3.0 | not linked | 1,000 drawings, 3,498 views; no | Views 0.96, title block 0.99, notes 0.98 (reported, metric undefined) | YOLOv11 | n/a | `plans` | skip: AGPL, other domain |
| 28 | Title block detector, Faster R-CNN MobileNetV3 | building drawings | 2025, arXiv 2504.08645 (CIB W78) | not linked | not linked | 1,385 drawings (facade-heavy); no | title block F1 0.83, main content 0.84, legend 0.41, notes 0.32 | not stated | n/a | none | skip: data not released |
| 29 | Donut whole-sheet vs crop reading (nomenclature of cadastral map sheets) | historical maps | 2025, AIAI | not linked | Donut base weights, licence not checked | Czech cadastral sheets; no | exact match 0 / 12 / 65-67 % at 480x640 / 960x1250 / 1200x1600; crop 84-86 % | A4000 16 GB | n/a | resolution gate evidence | idea only |
| 30 | Bayesian-network synthetic page generator | document layout | 2021, arXiv 2111.06016 (Pattern Recognition 2022 per a search snippet) | not checked | n/a | synthetic only vs real; no | F1 gap 3.6-4.0 points; +1.3 when mixed | Faster R-CNN family | n/a | `plans` (synthetic recipe) | idea only |

## 3. From other fields: transfer notes

For each: the field and task; what plays the role of our object; why it transfers; what breaks on our images;
whether code and weights work as they are.

### 3.1 Compound-figure separation (biomedical and materials papers) for "several plans on one sheet"

- **Object role:** a subfigure panel is a plan; the compound figure is the sheet. Labels (a), (b) play the role of
  floor titles ("1. KERROS" style words) if the plan prints them. Evidence: Open-PMC-18M (2025), FigEx2 (2026, DAB-DETR
  plus a Qwen3-VL-8B captioner, BioSci-Fig-Cap mAP@0.5 0.906, code Huang-AI4Medicine-Lab/FigEx2 with no licence file),
  MatMMExtract (2026, mAP50 0.9227), Jiang et al. 2021 (label-anchored, AP50 90).
- **Why it should transfer:** the task is the same: find N rectangles on a mostly-white sheet and count them exactly;
  synthetic composition gives free boxes (Open-PMC-18M table, `Margins`, `Grid Size`, `Labeling Scheme`).
- **What breaks on ours:**
  1. The synthetic-to-real gap is large: 98.58 mAP on synthetic hold-out, 36.88 on the real ImageCLEF 2016 (verified).
     Real sheets mix borders, no borders, insets, and plans of very different sizes. Compose with the real
     layout statistics of our 784 multi-plan dev sheets (width ratios, gaps), not a regular grid.
  2. Plans on a CubiCasa sheet are often unframed and touch their neighbour at a stair or an arrow; classical
     separator and gap methods lose exactly there (Taschwer 2016: borderless illustrations fail; comics survey:
     panels without clear boundaries). The 2013 BMC paper's count-prior route (caption says 3 panels, image
     agrees) has no caption on our side; the nearest equivalent is OCR'd floor words, which depends on the OCR
     scope (L5).
  3. A plan has no fixed aspect ratio and contains white courtyards; a connected-component or whitespace step splits a
     plan with a big void. Detector boxes are safer than any projection cut.
  4. Source panels must be single-plan dev images only; the composites keep leakage inside the 3,828 dev images.
     A composite of two dev plans is fine; a composite that includes a sealed-eval plan is not.
- **Tsutsui and Crandall (2017) put numbers on the synthetic part** (YOLOv2, 544 px, read in full): two synthesis
  schemes, random pasting at IoU below 0.05 (no gain, 0.842 vs 0.846) and grid rows of 3 to 7 with 1 to 7 panels per
  row and no gaps (accuracy 0.859, mAP 0.782 vs 0.773). Synthetic images doubled the real training set; a
  synthetic-only run was not reported. Failure cases they list: small similar panels aligned closely, and large
  components such as a legend split into pieces. A two-storey plan whose floors share a stair tower is the same shape.
- **Code and weights usable as is?** Partly. Open-PMC-18M's detector weights load with `transformers` under an Apache-2.0
  card. FigEx2's repo has a `weights/` folder and points to a Hugging Face page, and the Hugging Face model FigEx2-8B
  exists (API tags: safetensors only, no licence field), but there is no licence file in the repo either, so FigEx2 is
  idea only. Its own limitations section (full text read) says DAB-DETR boxes are axis-aligned and "may be too rigid for
  non-rectangular regions or heavily overlapping panels". Zero-shot on plans is unlikely to be good (training panels are
  photos, micrographs and plots, not unframed line drawings); the real use is fine-tuning that detector, or RF-DETR, on
  our composites plus real two-plan sheets. The compound-figure generator is not published: a search of
  the repo's full file tree for synth, layout, generate and compose finds only vendored DETR code, `train_detect_align.py`
  and caption-generation scripts, and the older helper-model repo (vector-institute/pmc-helper-models, a PMC-CLIP era
  `subfigure_detector.pth`, no licence field) is a different detector. We write our own generator (one afternoon,
  estimate).

### 3.2 Architectural sheet layout (AEC drawings) as a direct neighbour

- **Object role:** "layout; plan / section / elevation" boxes on a drawing sheet are plan regions.
- **Evidence:** EC3 2026 (verified): RF-DETR-m 0.949 mAP50; DocLayNet-pretrained layout weights fall to 0.675 and
  the paper's own ablation shows the architecture change alone costs less (0.854 vs 0.900 for COCO YOLOv10m; one run each, no seeds stated, so treat that gap as unconfirmed). A 2025 EG-ICE
  paper on 2,000 bridge drawings (YOLOv7, mAP@.5 about 0.92, mAP@.5:.95 0.64-0.68, views matched to titles by OCR) points
  the same way (verified from the PDF text; no code, no licence stated).
- **What breaks on ours:** those sheets are large vector-origin CAD sheets (RF-DETR input 1344 x 800, near-lossless
  lines); ours are 855 px median, 240 px minimum, scanned or photographed, and a plan is usually the only content.
  Neither paper counts views; both report AP, not the exact count per sheet.
- **Usable as is?** No dataset, no weights, no code. Use as the detector-choice argument only.

- **Mechanical multi-view drawings, a second drawing-sheet splitter** (arXiv 2510.21862, v2 PDF read in full on 2026-11-14,
  2025; licence not stated, code and data not linked): YOLOv11 detection of Views, Title Block and Notes on 1,000 mechanical
  drawings (3,498 View labels, so about 3.5 views per sheet) reports 0.96 for Views, 0.99 title block, 0.98 notes (reported by
  the authors; the metric is not defined in the text I read). It shows a first stage "find the views" on drawings with a few
  thousand boxes is enough for a usable detector. What breaks: it is mechanical, not architectural; YOLOv11 is AGPL-3.0 (excluded,
  D5), and the later stages are VLMs. Use the sizes (about 1,000 sheets) as an order of magnitude for how much box labelling
  a sheet-level detector needed; we already have 784 real multi-plan dev sheets. A building-drawing title-block paper
  (Lombardi et al., arXiv 2504.08645, PDF read in full 2026-11-14) fine-tunes Faster R-CNN with a MobileNetV3 backbone for 20 epochs on 1,385 building and engineering drawings (title block, main content, legend, notes; mostly facade drawings): title block accuracy 0.971 at IoU 0.7 but precision 0.84 and F1 0.83, legend F1 0.41 and notes F1 0.32; the paper says "Acc" and F1 here without defining how accuracy handles negatives, so I rely only on F1. It states the dataset is extensible but I found no download link in the text, so it is not usable as data. Takeaway for us: a light box detector reaches F1 above 0.8 on the big, distinctive regions (title block, main content) and below 0.5 on the small ones, which is the size effect we expect for small plans.

### 3.3 Orientation without text

- **Fields:** photo orientation (Swami 2017, Gidaris 2018), page orientation for OCR (PaddleOCR, Seeing Straight
  2025/2026), MLLM rotation (RotBench 2026), sketch pretext tasks (search only, not read).
- **Verified facts:** Tesseract's OSD source (`osdetect.cpp`, curl 2026-11-14) takes `min_characters_to_try` = 50 by
  default, prints "Too few characters. Skipping this page" below half of it, and then returns nothing. A plan with 5 to
  15 labels never reaches it. RotBench (arXiv 2508.13968): "All models exhibit substantial difficulties when distinguishing between 90 and 270 degrees" (current version, verbatim; an earlier quote of mine was from memory of an older version and is dropped); best
  zero-shot 270 accuracy 0.59 (GPT-5), Qwen-2.5-VL-7B 0.15; the set is lifestyle and landscape photos, no line
  drawings. Rotation as pretext is ill-posed only for "images that only depict round objects" (Gidaris). The one
  structure-based method I found for floor plans is wall-orthogonality deskew from 2013 (search result only, not
  opened; not 90 versus 270 anyway).
- **Seeing Straight (2511.04161 v2, full text re-read with the headless browser):** its benchmark is built from
  receipts (SROIE), synthetic text pages (SynthDog), forms (FUNSD) and Indic Wikisource scans; no drawings, charts or
  sparse-text pages appear in the text I searched. It reports that OCR-based docTR and TrOCR fine-tuned for rotation
  classification are second best and that zero-shot VLMs do poorly, which agrees with RotBench. Fine-tuning a small
  classifier for the 4-class task is therefore the established recipe, and ours would fine-tune on plans.
- **Fischer, Dosovitskiy and Brox (2015, University of Freiburg PDF, downloaded with curl and read with pypdf on
  2026-11-14):** the classical baselines for orientation (Hough on edges, folded to a 90-degree range, plus an FFT
  variant) are exactly the "walls are orthogonal" method, and the paper states the consequence: with the angle folded
  mod 90 they cannot separate portrait from landscape. A network fixed that on photos (Table 1, average absolute
  error in degrees): on the +-30 task Net-30 3.00 against Hough-var 11.41, Hough-pow 10.62, Fourier 10.66; on the full
  +-180 task even the best network is at 18.68 (Net-rough+45) or 20.97 (Net-360), so the full-circle task is far harder and
  the paper says it helps most to classify the coarse orientation first and
  then a fine adjustment. That is the design for us: wall-histogram deskew for the small angle, a 4-class classifier
  for the 90-degree step.
- **A shipped precedent for "rotate only when sure":** OCRmyPDF (MPL-2.0, `gh api`; docs cookbook and advanced pages
  read 2026-11-14) rotates a page from Tesseract's orientation confidence only above a threshold (default 14, "clear
  agreement scores about 27", `-v1` prints the per-page value), warns that the default is conservative, and in its optional
  RapidOCR mode "a page is turned only when both agree, so upright charts, maps and covers stay as they are". Two
  independent orientation voters that must agree, otherwise leave the page alone and flag it, is the cheap rule to copy.
- **What plays the role of the object:** the rotation class (0/90/180/270) of the whole plan, with free labels from
  rotating dev images; the text-line orientation of each detected label as extra evidence.
- **What breaks on ours:** the detector does not care (rot90 and flip training), so only OCR needs "up". A plan has
  walls in two orthogonal directions, so deskew gives 0 or 90 but never up versus down; the 180 case needs text or
  an asymmetric cue. Labels are 5 to 10 px; PP-LCNet text-line models were tested on documents and ID cards, and
  the PaddleOCR pages say nothing about sparse-text pages.
- **Usable as is?** PP-LCNet doc_ori and textline_ori: yes for code and weights (Apache-2.0 card and repo); accuracy
  on plans unknown. Everything else is the idea only.
- **Answer to the scope's question:** no proven orientation method for plans with almost no text exists in what I
  read. The best-supported plan is: rot90 augmentation for detection (zero cost), per-label 0/180 vote plus a
  4-class page classifier trained on our own rotated dev plans for OCR, and an OCR-confidence check over the four
  rotations only when the vote is split (untested idea; estimate 1 to 2 hours to measure).

- **A statement from document layout work, round 4** (Liu et al., "Unified Line and Paragraph Detection by Graph Convolutional
  Networks", DAS 2022, arXiv 2203.09638, section 4.2 read from the PDF 2026-11-14): their purely geometric model is limited to
  rotations under 45 degrees, because at 90 or 180 degrees "it may be impossible, even for a human, to recover the original
  orientation correctly using only geometrical information (bounding boxes)"; they propose, without testing it, a text-direction
  prediction on each character box with a majority vote. Support for my earlier conclusion that a structure-only orientation
  method for sparse-text pages has no proven source, and for the voting design in the top 5, item 3.

### 3.4 Sheet splitting by geometry and by boxes

- Classical separators (band and edge, Taschwer 2016) reach 84.9% on ImageCLEF 2015 test and fail on borderless
  figures (verified in the full text re-read with the headless browser: "most existing approaches focus on the detection of
  separator bands and hence fail for compound images where subimages are stitched together without separator bands";
  the edge-only variant scores 58%). Comics: borderless and bleed panels are the stated hard case; learned
  detectors on five comic sets score a mean mAP 74-80 (verified table, 40k verbatim). XY-cut variants reorder
  blocks and need a detector first (XY-Cut++ ordering BLEU-4 0.988 on DocBench-100, verified).
- **Break on ours:** a plan sheet with two unframed plans looks like a borderless comic page; by analogy (my
  reading, not measured) expect a ceiling near the comics' 75-80 mAP on the hard cases unless training uses our own
  boxes (row 1).
- Map sheet analysis (ICDAR 2021, verified): one content area per sheet, insets not handled; skip.

- **Comic MTL, a clean-frame upper bound** (Nguyen, Rigaud, Burie, IJDAR 2019, HAL PDF read in full on 2026-11-14): panel detection
  at IoU 0.5, Faster R-CNN F1 92.65 vs Comic MTL 97.76 on DCM772 (framed panels), and 91.14 vs 91.50 on eBDtheque (complex,
  100 pages, few training images); older non-learned methods 65.6-83.8 on eBDtheque. Failures are non-rectangular panels. For
  us: with clear frames a plain detector reaches about 90+ F1 per box, and per-box F1 is not the exact-count metric (one miss
  breaks a page), so expect the page-level exact count to be lower; a dataset of about 800 multi-plan sheets is closer to
  eBDtheque than to DCM772. Code and licence not checked.

- **Synthetic-only versus real training for layout boxes, a second data point** (Bayesian-network page generator, arXiv 2111.06016,
  ar5iv full text read 2026-11-14; 2021, so older than the others; licence and code not checked): detectors trained on 10,000
  synthetic pages instead of 10,000 real ones lost 3.6 F1 points on PubLayNet (41.6 vs 45.2, absolute F1 low because labels
  were coarsened) and 4.0 on DocBank (37.4 vs 41.1); with Faster R-CNN ResNet the gap was 3.7-4.3 across the two sets, up to
  12.3 with an SSD-VGG detector; mixing 10,000 synthetic with the real pages gave +1.3 F1 (45.2 to 46.5), a baseline that places
  elements arbitrarily gave only +0.2. For us: it agrees with Tsutsui (synthetic helps most as an addition) and with the rule that
  the generator's layout statistics matter; our composites should copy the real two-plan sheet layouts (gap, alignment,
  relative size) rather than a random grid. Different task (text documents), so only the size of the gap carries over.

### 3.5 Quality gating from biometric capture quality

- **Object role:** "sample quality" = the chance our count is right. OFIQ names components and checks each with an
  error-versus-discard curve; the evaluation paper (arXiv 2303.13294) says discard fractions beyond 0.3 are not
  operational, so the curve is read only up to there.
- **Why it transfers:** it answers "which cheap signals predict error" with a defined curve, and tells you which
  signals to drop: in OFIQ, exposure and dynamic-range components helped little (10% to 9.5%), sharpness and
  compression helped most (10% to 8%).
- **How OFIQ builds one component, read in its 188-page public report (V1.2, downloaded with curl, text by pypdf,
  2026-11-14):** Sharpness is computed on the region of interest only, cropped and resized so the long side is 250 px and
  converted to grey, so the score does not depend on the original image size. Single-feature versions are the mean
  absolute Laplacian (after a 3x3 Gaussian) or the difference to a 3x3 mean-filtered image; a 26-feature classifier
  (Sobel, Laplacian and mean-filter responses at several kernel sizes) was trained on 2,179 sharp and 1,567 blurry
  images (80/20 train and validation) and tested on 262 sharp and 280 out-of-focus images plus 240 images from a kiosk.
  That is cheap enough to copy: for a plan, crop to the ink bounding box, resize, take Laplacian statistics, and plot
  count error against the score.
- **The resolution component is a size measurement, not a learned score:** OFIQ's Inter-Eye Distance is the pixel
  distance between the two eye centres, corrected for head yaw by sec(yaw), and is checked with an EDC curve only (the
  report says no ground-truth comparison is needed since it only depends on landmark accuracy). Our equivalent is a
  pixel length of a reference part that every plan has (a door leaf or a wall thickness from the detector's own
  boxes), which makes the size gate a by-product of detection rather than another model.
- **What breaks on ours:** biometric utility is defined from pairwise comparison scores; ours is a per-image exact
  count, so the curve is "fraction of sheets abstained" against "exact-count error among the answered", which is
  simple to compute once dev counts exist. CR-FIQA and NFIQ2 need training sets we do not have (CR-FIQA identity
  labels, NC licence). Earlier reports found DIQA correlations only on text pages (0.65 to 0.92); nothing here changes
  that.
- **Usable as is?** OFIQ (MIT licence file) and NFIQ2 (public domain) are face and fingerprint tools; no. The EDC
  evaluation code (Apache-2.0, language not checked) is the part that could be reused; the protocol is what to take.
- **Size as the first gate, from face detection** (Hu and Ramanan, CVPR 2017, arXiv 1612.04402, ar5iv text read
  2026-11-14): object height in pixels is what the detector's accuracy depends on most (their appendix reports
  normalised AP from 0.044 to 0.896 across scales; per-height values are only in a figure I did not read); "tiny"
  means under 20 px and the hard set starts at 10 px; for objects under 40 px they use a 2x larger canonical template
  and an image pyramid with a 2x upsampled level, and a 25x20 face goes from 69% to 75% when run at 2x. For us this
  supports a first gate that is just the median symbol height in pixels, checked with the same EDC curve before any
  learned quality model; the scale-template details belong to the detection scope (L2). Code at cs.cmu.edu/~peiyunh/tiny,
  licence not stated in the paper.
- **Choosing the threshold, a precedent from OCR post-processing** (Navarro-Cerdan et al., Expert Systems with
  Applications 2015, 42(21), read from the PDF text on 2026-11-14): sort the hypotheses by cost, estimate the
  cumulative error E(c_i) of accepting everything up to c_i, and set the threshold T at the highest cost where E stays
  at or under the user's target error. They report that this batch-adaptive rule held the target error on easy and
  hard batches while a fixed threshold "failed in all the cases" (over-rejecting easy batches, under-rejecting hard
  ones). For us: pick the abstention threshold per batch of sheets from a target exact-count error, not one fixed
  number tuned on clean images. Old (2015), strings not images, no code stated; the idea only, and it overlaps L10.

- **Rule-based per-image QC pipeline, a precedent from histology** (HistoQC, github choosehappy/HistoQC, config files read via
  gh api on 2026-11-14; BSD-3-Clause-Clear per the GitHub licence field; paper Janowczyk et al., JCO Clin Cancer Inform 2019, not
  re-read): a config-listed chain of small modules (basic stats, pen-mark and coverslip-edge detectors by example, light/dark
  thresholds, blur regions, contrast, brightness, histogram vs. templates) each writes numbers and a mask per slide, and a
  reviewer filters on them. For us: the shape to copy for a sheet gate is "several cheap named measurements, all stored,
  thresholds in a config", which matches the OFIQ idea in this section. What breaks: the modules are tuned to H&E tissue
  (stain deconvolution, pen colour), so only the pattern transfers, not the code; no accuracy figure on drawings.

- **Failure to assess is its own return code, not a low score** (OFIQ source, github BSI-OFIQ/OFIQ-Project, files
  `OFIQlib/src/OFIQImpl.cpp` and `OFIQlib/modules/measures/src/SingleFacePresent.cpp` read via gh api on 2026-11-14; MIT per
  LICENSE.md): every component writes a raw score plus a return code, and when no face is detected the dependent
  components are set to `FailureToAssess` instead of a number (the comment in SingleFacePresent says the method "should never
  occur" with no face because the others are already set that way). The repo's ISSUES.md also lists a known failure of the
  face detector it depends on (faces found on glasses) that the standard requires to be kept. For us: the gate should output
  three states per sheet (pass, fail with a reason, could not assess) and the answer stage should treat "could not assess" as
  abstain, never as a default of one plan. Same idea as the agree-or-flag rule in the Lopez counters.

- **Caveat on a single learned or unified quality score** (news report of a DHS-funded study, Biometric Update, 9 Jan 2026; the
  paper itself, Sirotin et al., was not opened, so this is a secondary source): 16 commercial face matchers were tested against
  OFIQ's unified score; the score "provides extremely limited utility", under-rated the matchers (images scored very low still
  matched accurately) and filtering on it "did not substantially reduce error rates"; it may still help to pick the best of
  several images. A follow-up news item (search snippet, not opened) quotes an OFIQ author arguing the DHS dataset and matcher choice (15 or 16 vendors, counts differ between items) do not fit OFIQ's intended use, so the finding is contested; the paper itself was not found. For us: gate on named components that map to a known failure (size in pixels, blur, contrast), checked
  with an EDC curve against our own error, and do not trust one blended score.

### 3.6 Fields looked at and set aside

- Receipt and ID multi-document photos: a vendor blog (way2vat, 17 Aug 2021, read 2026-11-14) says semantic
  segmentation merges overlapping receipts into one connected component, so they train a box detector and claim
  "more than 95% accuracy"; the accuracy is not defined, no model, no training size, no code. The useful point is the
  design rule: boxes over every separate document, overlapping or not, because blobs merge. ID-document work
  (MIDV-2020, search result only) localises one card per image; nothing on orientation was found.
- Newspaper article segmentation: Chronicling Germany (arXiv 2401.16845 v4, 801 pages, U-Net with ResNet-50 encoder,
  pages scaled 0.5 and cut into 512 px crops, read to Section 4.1 verbatim) gives separators their own classes
  (vertical F1 0.72, horizontal 0.74) to help reading order, and does not evaluate region counts; TextBite is the
  grouping precedent (row 5 of the top list). Neither licence for data or code is stated.
- Map legends: arXiv 2510.08385 (Oct 2025, read in full with the headless browser) crops legends with a fine-tuned
  LayoutLMv3 and has GPT-4o pair symbols with descriptions from 5 to 15 in-context examples on 40 test maps; it fails on
  dense multi-column legends. It is a VLM-on-layout paper (L7) and its crop-first idea is the only transferable part.
- Document layout models (Docling, PP-DocLayout): trained on text documents; the AEC ablation is the reason to skip.

- **Dewarping of photographed pages, set aside** (L9 scope bullet, added in round 4): DvD (arXiv 2505.21975 v2, 2025, page text read,
  page licence CC BY-NC-ND 4.0, no code link found in the text) is a coordinate-diffusion dewarper trained on synthetic Doc3D,
  with a new 6,300-pair real photo benchmark. Its quality metrics are OCR error rates and image similarity, so it measures
  nothing on pages with little text; the task is photographed, curved paper, while our sheets are flat renders or scans;
  and the licence is non-commercial. No dewarper is recommended; if a photographed sheet shows up in the data, the
  "reject by quality gate" route in 3.5 is cheaper than rectifying.

### 3.7 Drawing-specific super-resolution, the one result that cuts against the earlier "keep SR out" advice

- **Field and task:** electric-power single-line diagrams (Yang et al., arXiv 2312.13620, Dec 2023, CC BY 4.0 paper,
  read in full with the headless browser 2026-11-14): restore low-quality drawings with a trimmed ESRGAN (16 instead of
  23 blocks, 4x, 200 x 200 patches, gradient loss, trained on synthetic degradations), then detect symbols with a Faster
  R-CNN variant (Swin backbone plus BiFPN, 1000 x 1000 patches, IoU threshold 0.9).
- **Numbers (their Tables 1 and 2, verified):** symbol recall on low-quality diagrams 32.74% with plain interpolation,
  85.19% SRGAN, 88.93% ESRGAN, 98.89% ESRGAN trained with their synthetic degradations, 99.33% for the full joint
  system (precision 98.87%). The paper says its own point is that diverse synthetic degradations in the SR training
  data raise recall from 88.93% to 98.89%.
- **What plays the role of our object:** a drawn symbol on line art; the same loss, missed symbols at low resolution.
- **What breaks on ours:** the data are a partner's private diagrams with large symbols, the test degradations come
  from the same degradation model used to train the restorer, the metric is precision and recall at a stated IoU, not
  an exact count, and no code or weights are linked (not found in the text). Earlier reports (03-blur-sr) found that
  generic generative SR invents strokes; this paper's answer is a drawing-specific restorer trained with paired
  degradations, which would need our own pairs (we can make them from dev images). Treat as an A/B to run, not as
  evidence: verdict **maybe**, and only with a "did any count change" check.

### 3.8 Optical music recognition: page, then system, then scale, then crop (added in round 4)

- **What plays the role of our object:** a printed score page holds several systems (rows of staves) like a sheet holds several
  plans; OMR splits the page first, then normalises scale, then reads each crop.
- **Evidence** (OSSQ-OMR string-quartet benchmark, arXiv 2608.10978, 2026, page text read in full on 2026-11-14, CC BY 4.0 page
  licence): three YOLOv8 models run in sequence: system detection on the full page, staff-height regression on each system image,
  staff detection inside the system crop. Each system image is then resized so that noteheads (a quarter of staff height) are
  about 4-5 px, "matching the input scale expected by downstream OMR models". The system detector was trained from scratch on
  1,804 pages plus 47 in-domain pages; the staff-height regressor is reused as is from earlier work. A 2024 workshop paper
  (Dvorak, Hajic jr., Mayer, Reading Music Systems proceedings 2411.15741) benchmarks YOLO against the unmaintained
  MeasureDetector for staves, systems and measures; its text was then read from the arXiv PDF (CC-BY-4.0): YOLOv8m matches or slightly beats the older Faster R-CNN, is >20x faster and needs >4x less memory, trained on three harmonised datasets plus a background-only set (MZKBlank, archive pages without music) to teach it to say "nothing here"; the authors argue layout errors are "extremely expensive to fix manually" downstream and propose verifying layout interactively before the costly reader, and sending a page on only when a staff is detected "with a very high probability" (a gate by detector confidence).
- **For us:** the same order of work: detect the plan boxes, regress or read one scale cue per crop (our scale bar or ratio),
  resize to the size the downstream reader expects, only then extract. It supports "scale as a regression target per crop"
  as a cheap addition to row 1 of the top 5. No count or error metric was given for the system-detection step in the text read.
- **What breaks / licence:** YOLOv8 (Ultralytics) is AGPL-3.0, so the models and weights are excluded for us as in D5; use the
  recipe with RF-DETR (Apache-2.0 for N/S/M/L). Staff height is a printed regularity (five lines, fixed spacing); plans have no
  such constant, so the regressor needs our own scale labels. Leakage flag: no (music scores).

- **Resolution versus exact match on a whole sheet, historical cadastral maps** (Lenc, Martinek, Kral, "Historical Map Understanding
  Using End-to-end Methods", AIAI 2025, PDF read in full on 2026-11-14; the task is reading the sheet-position label, not
  counting): Donut fine-tuned on the whole sheet gets exact match 0 % at 480x640 input, 12 % at 960x1250, 65-67 % at
  1200x1600 / 1320x1760; the same model on a crop of the label reaches 84-86 % already at 480x640. The two-step YOLO + OCR
  baseline scores 74 % exact match. For us: it is measured evidence that a whole-sheet read needs high input resolution and a
  crop-first design does not, and that "exact match" collapses before per-field accuracy does (fields at 90+ %, exact match
  at 74 %). Gate on the size of the region the reader sees. Different domain and a model I would not use as is (Donut
  weights not checked for licence), so only the pattern transfers.

### 3.9 Map sheets, content versus legend (added in round 4, short)

arXiv 2510.08385 (GeoSearch'25 workshop, page text read in full 2026-11-14; arXiv non-exclusive licence only): a fine-tuned
LayoutLMv3 first splits a map sheet into content and legend regions, then GPT-4o with 15 in-context examples finds legend items,
scored by IoU>=0.5 F1 on 40 maps. Same shape as "plan versus legend/key-plan on a sheet", but the first step is a layout model
(DocLayNet-style pretraining is what EC3 found to hurt on drawings), the second a hosted LLM (not offline), and the 40-map test set
is small. Set aside as a model; kept as one more sign that sheet-level region splitting is done with a detector or layout model
first and everything else after. No inset-map detector turned up.

## 4. Looked for and did not find

- A floor-plan page-orientation method that works from structure with little text (2025-2026 search, extended mode):
  nothing; only a 2013 wall-based deskew (not opened).
- Any method that separates several floor plans drawn on one sheet. The nearest hit, arXiv 2408.01526 (multi-unit
  floor plans, v2 June 2026; now read in full with the headless browser, page licence CC BY 4.0), segments
  units inside one large plan on a private 8-plan set; the abstract says future work is multi-floor plans. Its
  CubiCasa5K use (a "refined" subset) means any weights from it are leakage-flagged **yes**; its code is on an
  anonymous mirror with no licence. arXiv 2607.00015 (May 2026, a compliance-checking framework, now read in full with the headless browser, 106k characters) says verbatim "none of these studies segments individual apartments in the multi-apartment floor
  plans" and proposes graph partitioning as future work; no model, no accuracy reported.
- Second attempt on orientation with other terms (drawing sheet, title block, rotated CAD raster, OCR voting): only
  title-block work. The NCSA report on scanned Navy drawings (read from the saved PDF with pypdf, 2026-11-14) finds the
  title block with templates at several scan resolutions and OCRs its sub-fields (OCR accuracy about 80% on some
  title-block characters); its text contains no rotation step. The title-block cue relies on drawing standards (block in
  a known corner), which a CubiCasa plan does not have. A combined voting scheme (title block, text direction, OCR
  confidence over four rotations) has no source; it stays my untested idea.
- Optical music recognition page layout (staves, systems, measures): first left thin, then read in round 4: the 2024
  workshop paper (2411.15741) and the 2026 string-quartet benchmark (2608.10978) are now in section 3.8. Still not found: a
  system-detection accuracy figure in the 2026 text.
- A paper that reports per-sheet exact panel or plan counts: one found, and old. Lopez et al. 2013 (BMC Systems
  Biology 7 Suppl 4:S8, read in full from Europe PMC on 2026-11-14) got the exact panel count right in 11,973 of 13,147
  figures (91.07%) by combining three independent counters (in-image panel labels, caption sub-captions, connected
  components) and trusting the count when they agree (9,294 cases); 96.64% of 41,341 panels were then segmented
  correctly. Everything newer reports AP, F1 or Rand index, not the count. The agree-or-flag rule is the same shape as
  our stage-8 second counter.
- Weights for an AEC sheet-layout detector (none linked). For compound figures only Open-PMC-18M publishes a detector.
- The AEC paper's classes are facade layout elements; no source I read separates several floor plans on one sheet.
- OCR-confidence orientation (rotate four ways, keep the best) with a number. Tesseract OSD does something like it
  with a 50-character floor; nothing measured on sparse text.
- NFIQ2 operating thresholds: NIST IR 8382 (99 pages, text by pypdf) was searched again in round 4: it defines the
  error-versus-reject curve (section 6.1: reject the lowest-quality x % and recompute the error; a perfect quality score would
  bring the error to zero) and states no recommended operating threshold or score bands, so thresholds are left to the
  operator, as the EDC idea in section 3.5 assumes. The per-dataset curves are in provider appendices, not read.
- MDPI paper on architectural drawing vectorisation (mdpi.com 2075-5309/16/5/1043) is refused with HTTP 403 by
  web-fetch and Access Denied by the headless browser; not read, not cited.
- Semantic Scholar rate-limited after four calls (HTTP 429), so forward citation lists below are partial. In round 4 Semantic Scholar answered 429 again and the OpenAlex free daily budget was used up; I did not look for a way around either, so the forward walks in section 5 stay as they were.

- Round 4 re-check (2026-11-14): one more search for a structure-only page-orientation method (no text) and for a multi-plan sheet splitter returned only text-based patents, vendor docs and the already-listed EC3 and multi-unit papers; the gaps above stand.

- Round 4 repo check (2026-11-14): FigEx2 repo has 0 issues and 0 stars (so no outside report on training time, memory or small objects), no licence file, pinned `transformers==5.7.0` with torch>=2.8 and peft; no GPL/AGPL dependency visible in requirements.txt. Status stays "idea only; weights usable only after the authors state a licence".

- Round 4 repo check (2026-11-14, gh api): the comics framework `cdf` has no licence file, 0 issues, last push 2024-11; DeQA-Doc (document quality scoring) has no licence, and its 3 open issues ask for a weights API, the DIQA-5000 dataset and a missing script, so neither the data nor a usable checkpoint is public. Both stay idea-only.

- Round 4 re-read (2026-11-14): Chronicling Germany in full (arxiv.org/html v4, page text states CC BY 4.0). Its appendix lists the limits: layout confusion on out-of-distribution papers with rare classes, tables mistaken for text, and "some newspaper pages are digitized in a way, that includes an entire double page in one image" (sic), for which the authors have no splitter yet (planned future work). That is the same shape as our two-plan sheet, and it is stated as open there too. No count metric.

- Round 4 re-attempt, quality evidence on drawings (2026-11-14): a search for a controlled study of blur or resolution versus detection accuracy on drawings found again only Yang 2312.13620 (already row-listed, synthetic degradation) and an IJDAR 2024 benchmark (s10032-024-00492-9) that is behind a login: not read, not cited; only its search snippet (YOLO 79, Faster R-CNN 83 mAP) is known.

- Round 4, adjacent field double-page book scans (2026-11-14): search only (BookNet 2601.21938 rectifies warped pages and reports no split accuracy; a 2010 conference paper and patents use column-sum gutter detection). No learned two-page splitter with a published count or split accuracy; none cited.

- Round 4 repo check, Tsutsui and Crandall code (github apple2373/figure-separator, README read via gh api 2026-11-14): TensorFlow 1.0 and OpenCV 3, no licence field, a frozen `.pb` model hosted on Hugging Face and Dropbox, last push 2024: a reference for the grid-composite idea only, not usable as code. A curated list of compound-figure-separation work (etowahadams/awesome-compound-figure-separation) was scanned and shows no 2025-2026 detector beyond Open-PMC and FigEx2 already covered.

- Round 4 repo check, RF-DETR issues on sheet-shaped input (gh api, read 2026-11-14; maintainer statements, not measurements): #1052
  (rectangular training): the maintainers recommend squashing wide images to square, say the pretraining is square and
  non-square input "works less well" in what they hear; one user first saw +20 % from a native 3:4 ratio, then found
  the gain came from not having loaded the pretrained weights, and "no difference" once they did (their rectangular run used
  more tokens). #747 (4k images): resolution on disk is irrelevant, object size matters; prefer a larger model size over a
  higher resolution for a small one; XL and 2XL need the `rfdetr[plus]` package under the PML licence (so stay with N/S/M/L), and
  another user suggests tiling (SAHI) for very high resolution. For us: a square squash of a wide sheet costs small plans
  resolution, so the size gate must be measured after the squash; tiling is the fallback.
  Issue #780 (dense cells, 500-1500 per image, with SAHI tiling) shows the per-model query cap (the maintainers say the nano
  segmentation model tops out at 100 objects); that cap is irrelevant to us (at most 4 plans per sheet) and tiling there was slow.

- Same paper, round 4 detail (2408.01526, Tables III-IV and the conclusions read): its segmentation cores reach mean F1 0.86 on
  CubiCasa walls, railings, doors, windows, stairs (walls 0.90) and better on two other sets; the authors say their recognition has
  no region-of-interest module, that cropping the floor plan first "generally improves the accuracy", and that a YOLO-family
  detector is enough to crop (they cite a YOLOv4 ROI step in earlier work, not read). Support for "detect and crop plan boxes, then
  read each crop", not a measurement of its gain. Leakage flag stays yes for weights from this paper (CubiCasa subset).

## 5. Forward citation walk

- Open-PMC-18M (2506.02738): citers in 2025-2026 found by Semantic Scholar: MedPMC 2607.07673, MatMMExtract
  2606.29667, "From Panel to Pixel" 2512.02566, OpenMedReason 2606.12169, PhenoLIP 2602.06184 and others. Only MatMMExtract is
  a new panel detector (read: YOLO12-m, mAP50 0.9227). "From Panel to Pixel" (2512.02566 v2, March 2026, read with the
  headless browser) consumes panels and its table lists YOLO-style detectors as the usual panel step; the others were
  not opened (titles only). Nothing new on synthetic composition. OpenAlex counted only 11 citers of Open-PMC-18M in total.
- Tsutsui and Crandall (1703.05105), by OpenAlex (41 citers, 4 since 2025): SSSI (ICDAR 2025, flowchart segmentation with
  SAM prompts, Springer, abstract only via search), a TACL 2026 study of caption generation for scientific figures,
  a poster-layout paper and a heatmap-extraction paper; none is a new compound-figure separator.
- Jiang et al. (2101.09903): 2025-2026 citers are FigEx (EMNLP Findings 2025), FigEx2 (2601.08026, read), and two
  materials-literature papers.
- XY-Cut++ (2504.10258): MonkeyOCR 2506.05218 only (not opened). TextBite (2503.16664): citers not retrieved (429).
- RF-DocLayout (2606.23344, read): PP-DocLayoutV3, 33M parameters, skew robust, 90 degree rotation not addressed.

- Lopez et al. 2013 (PMC3856606) forward walk by the Europe PMC citations API (free, no key; 10 citing records on 2026-11-14): only one
  from 2025: "A hybrid multi-panel image segmentation framework for improved medical image retrieval system" (PMID 39977397,
  PMC11841867, CC BY; abstract only, the PMC page is blocked for my browser tool). It first classifies the image type (reported
  accuracy 90.50%), then segments with projection profiles and morphological operations, 91% on regular and 92% on irregular
  multi-panel images (reported, on ImageCLEFmed 2013-2016; the unit of the percentage is not clear from the abstract). It is a
  classical method with a classify-then-split structure and no exact-count figure; not used beyond this note. The other nine (2015-2023) were seen by title only,
  not opened.

## 6. Open questions and missing tools

1. Does PP-LCNet doc_ori work on plans? Needs 50 dev sheets with a known rotation (the rotation of dev images is not
   in the context file; a hand label or a rotation oracle from the SVG origin would do). Owner: whoever runs
   dev measurements.
2. Can our composite generator reproduce how real multi-plan CubiCasa sheets look (gaps, sizes, floor titles)? Needs
   a look at 20 real two-plan dev sheets before choosing margins.
3. Per-plan box export from the SVG labels is the one data item row 1 and row 6 both need (context file says not
   exported yet).
4. Floor-title words ("1. KERROS", "ALAKERTA", "KELLARI") as a count prior: belongs to the OCR scope (L5); one line
   there.
5. For the other orchestrator: ICDAR 2025 or 2026 papers on VLM layout of drawings (L7) were not read; 2510.08385 (GPT-4o
   with in-context learning for map legends) was opened in round 4 (section 3.9); the L7 question left is VLM layout on drawings.
6. Tools: no arXiv MCP; web-fetch cut long pages at about 40k characters; the headless browser could not load an arXiv
   PDF (navigation aborted) and was refused by MDPI; PDF text came from `pypdf` on the files the fetch tool had saved.
   Semantic Scholar rate-limits after about four calls.

## 7. Source list (all opened on 2026-11-14 unless stated; count: the log has 140 lines, 21 of them searches (not reads); about 85 pages, PDFs or repos opened, about 30 of them from 2025-2026; sources seen only as search snippets are marked so in the log)

Round 4 additions, read: arXiv 2608.10978, 2411.15741, 2510.21862, 2504.08645, 2111.06016, 2203.09638, 2505.21975, 2510.08385, 2401.16845, 2408.01526, 2607.00015; AIAI 2025 cadastral maps; IJDAR 2019 Comic MTL; NIST IR 8382 section 6.1; HistoQC, OFIQ source, RF-DETR issues; Biometric Update DHS item (secondary).

2025-2026 (read): arXiv 2506.02738 Open-PMC-18M; arXiv 2601.08026 FigEx2; arXiv 2503.16664 TextBite;
arXiv 2504.10258 XY-Cut++; arXiv 2509.11720 Docling layout; arXiv 2503.17213 PP-DocLayout; arXiv 2606.23344
RT-DocLayout; arXiv 2606.29667 MatMMExtract; arXiv 2607.18997 AEC layout benchmark; arXiv 2511.04161 Seeing
Straight (abstract); arXiv 2508.13968 RotBench; the Strathclyde EG-ICE 2025 bridge-drawing PDF; PaddleOCR 3.x
orientation module pages (2025 versions); OFIQ short report (Dec 2024); Comic Panel Extractor note (March 2026).
Earlier: arXiv 2101.09903, 1606.01021, 1712.01195, 1803.07728, 2105.13265 (+ icdar21-mapseg.github.io), 2303.13294,
2112.06592, 2409.09502, 2407.03540, 2410.12628, PMC3856606, NFIQ2 docs and README, Tesseract OSD source and docs,
HF cards and licence files listed in the log.
