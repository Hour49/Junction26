# Triage of Bogdan's half: L1 field, L4 rooms, L6 scale, L7 vision-language, L10 confidence, L12 products

Research orchestrator, 2026-11-14. One table per scope and group. The five triage questions of the README are the columns: evidence, allowed (licence and CubiCasa5K leakage), fits (cost), what it moves, and the cost again in hours. The scope's answer and its top 10 with re-checked sources are in `reports/lit-<scope>.md`; the cross-scope ranking is [SHORTLIST.md](SHORTLIST.md).

## L1 the field (55 records; report: [reports/lit-floorplan.md](reports/lit-floorplan.md))

### Try first (8)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| RF-DETR (Nano to Large) fine-tuned on our boxes | adjacent-field | code Apache-2.0 / weights Apache-2.0 for N,S,M,L (Atto,Femto; leakage no | 3 to 6 h to a first number, 12-16 GB GPU, batch 4 x accum 4  | windows-doors | only permissive maintained detector with a fine-tune path |
| Train and run one pass at 2x upscale before any tiling | adjacent-field | paper; code in its repo (not checked); leakage n/a | half a day plus a GPU slot (estimate) | windows-doors | cheapest big lever for 5-20 px symbols |
| PlanQ U-Net plus connected components as the floor | floor-plans | code MIT / no weights; labels CC BY-NC 4.0; leakage yes | 2-4 h, ~24 min per seed (claim) | windows-doors | cheap floor and error-shape template |
| Report exact, within 1, MAE and bias, by subgroup and count bin | floor-plans | n/a; leakage n/a | 1 h | trust | one headline number hides the dense plans |
| Multi-scale four-rotation template matching from one crop per class | adjacent-field | code MIT / data CC BY-NC 4.0; leakage n/a | 2-3 h CPU (estimate) | windows-doors | free baseline that may already clear the floor |
| rot90 training augmentation and four-rotation test voting | floor-plans | n/a; leakage n/a | free to 1 h | windows-doors | a third of our images are rotated |
| Report counts, not AP | floor-plans | n/a; leakage n/a | none | trust | metric hygiene |
| Define one window per drawn cell once | adjacent-field | n/a; leakage n/a | 1 h | windows-doors | label noise caps exact rate |

### Try next (18)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Tiled inference with a count-safe merge rule | adjacent-field | code MIT; leakage n/a | 2 h (estimate) | windows-doors | only if the upscaled single pass is not enough |
| Prompted-VLM counting baseline (AECV-Bench style) | floor-plans | repo has no licence file; leakage unknown | 1 h plus API cost (3.77 USD per 120 plans Gemini 3.5 Flash;  | windows-doors | comparison only, not a counter |
| Enlarge symbols to ~48 px and split views without zooming out | adjacent-field | code MIT; leakage n/a | 1 h | trust | design rule for any VLM step |
| VLM yes/no or index answer on detector boxes drawn on upscaled crops | adjacent-field | SoM code MIT; leakage n/a | 3-4 h plus API cost (state first) | trust | the VLM's only plausible role |
| Accept a count only when independent counters agree | adjacent-field | n/a; leakage n/a | 2 h once inputs exist | trust | cheap confidence signal |
| Stroke thickening and blur test of our detector | floor-plans | code MIT / assets CC BY-NC 4.0; leakage yes | 3-6 h (estimate) | windows-doors | measures the expected failure |
| Four-way orientation classifier before everything | adjacent-field | PaddleOCR Apache-2.0; leakage n/a | 3-5 h (estimate) | windows-doors | only if rot90 augmentation is not enough |
| BlueprintParse-R50 for toilet, sink, bathtub, gas range | authors-claim | code Apache-2.0 / weights Apache-2.0 (training data not redi; leakage no | 1 h | fixtures | only permissive non-CubiCasa sanitary checkpoint |
| Door-only RF-DETR-S checkpoint with tiled inference | search-only | weights Apache-2.0 / runner AGPL-3.0; leakage unknown | 2 h | windows-doors | unvetted data origin |
| Rare-class oversampling by pasting crops | adjacent-field | n/a; leakage n/a | 2 h | fixtures | rare classes fail in small-data detectors |
| Small VLM reads crops for labels and scale text | adjacent-field | models MIT; leakage n/a | 4-8 h (estimate) | room-types | fits labels and scale |
| Scale: detect bar or ratio, crop at full resolution, read | authors-claim | not located; leakage n/a | 4 h | scale-areas | maps analogue |
| Score with one-to-one Hungarian matching | adjacent-field | n/a; leakage n/a | 1 h | trust | avoids inflated numbers |
| CubiCasa5K annotation misalignment and noise | floor-plans | n/a; leakage n/a | none | trust | explains unreachable errors |
| Read the 2019 model's opening heatmaps instead of polygons | floor-plans | CC BY-NC 4.0; leakage yes | 3 h | windows-doors | existing weights, cheap |
| Super-resolution or Lanczos upscaling before detection | floor-plans | MIT; leakage yes | 2 h | windows-doors | tied to the resolution experiment |
| Global consistency step to remove duplicate openings | floor-plans | code MIT; leakage no | 3 h | windows-doors | duplicates ruin exact counts |
| Detect drawing area, legend and title block | adjacent-field | card Apache tag, AGPL library; leakage n/a | half a day | plans | one sheet in five has several plans |

### Later (15)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Per-class post-processing for segmentation counts | floor-plans | MIT; leakage n/a | 1 h | windows-doors | small gain if a segmentation arm is used |
| Stroke and blur curriculum fine-tune | authors-claim | code MIT; leakage yes | 1 h | windows-doors | no measured gain |
| Roboflow door and window sets as extra data | search-only | CC BY 4.0; leakage unknown | 1 day | windows-doors | origin unknown |
| Render ResPlan vector plans into training images | search-only | data CC BY 4.0 / code MIT; leakage no | 1 day (estimate) | windows-doors | supplement to the real 3.8k |
| Render Swiss Dwellings openings and sanitary features | search-only | CC BY 4.0; leakage no | 1 day | fixtures | only licence-clean source of fixtures |
| Seeded procedural plan generator with degradations | adjacent-field | MIT; leakage no | 1 day plus 3 h | windows-doors | supplement |
| Find bathrooms then detect fixtures on tiles | search-only | MIT / n/a; leakage unknown | 1 day | fixtures | unmeasured |
| SAM 3 as a pseudo-labeller | adjacent-field | custom SAM licence; leakage n/a | half a day | none | needs tuning |
| CountGD, GeCo2, Chain-of-Look style spacing loss, fine-tuned | adjacent-field | CountGD MIT / GeCo2 MIT; leakage n/a | 6-10 h (estimate) | windows-doors | zero-shot fails |
| Rule violations trigger a crop re-read | adjacent-field | n/a; leakage n/a | 1 day | trust | abstract only |
| Release a count only if internal consistency holds | adjacent-field | n/a; leakage n/a | 2 h | trust | idea |
| Multi-zoom inference merged | search-only | n/a; leakage n/a | 2 h | windows-doors | anecdote |
| Raster2Seq for rooms | floor-plans | code MIT / weights CC BY-NC 4.0; leakage yes | 1-2 days | room-types | rooms are another scope |
| Check whether CubiCasa-trained weights lean on Finnish labels | authors-claim | n/a; leakage yes | 2 h | trust | unmeasured |
| Coverage-weighted fusion for tiles | adjacent-field | code in repo; leakage n/a | 1 day | windows-doors | only after tiling proves needed |

### Idea or pitch only (6)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Read doors and windows from a local head, not a sequence decoder | floor-plans | code MIT (skv4 NC) / no weights; leakage yes | none | windows-doors | design principle |
| RT-DETR-L floor-plan recipe at 1024 px | floor-plans | no licence file, AGPL stack / weights unlicensed; leakage yes | 2.3 h on 2 GPUs (claim); 2-4 h ours (estimate) | windows-doors | recipe only, checkpoint is AGPL and leaked |
| Treat real annotated plans as the core, synthetic as supplement | adjacent-field | n/a; leakage n/a | none | none | guides data mix |
| Pipeline shape: detector, assembly rules, VLM only as checker | adjacent-field | mostly AGPL YOLO; leakage n/a | n/a | trust | supports current design |
| Human correction of detector boxes | adjacent-field | n/a; leakage n/a | n/a | demo | review step |
| A few dozen clean in-domain annotations beat noisy extras | floor-plans | CC BY-NC-SA; leakage yes | n/a | trust | data hygiene |

### Do not try (8)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Median or vote over several VLMs | floor-plans | n/a; leakage n/a | none | trust | no gain |
| Enumerate objects before counting | authors-claim | n/a; leakage n/a | none | none | not shown to help |
| Oriented-box detectors for rotated symbols | search-only | n/a; leakage n/a | none | none | image rotation is simpler |
| CC BY synthetic plans generator | search-only | dataset CC BY 4.0; leakage no | hours | none | wrong symbols |
| Exemplar counters without fine-tuning on drawings | adjacent-field | n/a; leakage n/a | none | none | zero-shot fails |
| Zero-shot or prompted VLMs as the counter | floor-plans | n/a; leakage n/a | none | windows-doors | detectors localise, VLMs recognise |
| Fine-tuned small VLM emitting JSON | floor-plans | various; leakage yes | none | windows-doors | low exact counts |
| Pixel counting beats VLMs for areas | adjacent-field | n/a; leakage n/a | none | scale-areas | geometry beats VLM |

## L4 rooms (55 records; report: [reports/lit-rooms.md](reports/lit-rooms.md))

### Try first (20)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Own wall and room-region net, connected components as rooms | floor-plans | smp MIT, timm Apache-2.0 encoders, own weights; leakage no | 4 h work, 2 to 3 GPU-h on 12 GB (estimate) | scale-areas | only family with a measured area error and clean licences |
| Printed room area wins over polygon area | floor-plans | n/a; leakage n/a | 1 h | scale-areas | polygon area cannot reach 2% alone |
| Fix the wall convention of the gold area before measuring | our-idea | n/a; leakage n/a | 1 h | scale-areas | cheap and can dominate the area error |
| Trapped-ball fill to close door gaps | adjacent-field | MIT; leakage no | 1 h on top of the mask net | scale-areas | one parameter, directly models a door gap |
| Distance-transform, Voronoi or down-sampling watershed room splitting | adjacent-field | reimplement (Bormann code LGPL non-commercial, ROSE2 GPL-3.0; leakage no | 1 to 2 h | scale-areas | needs no door detector |
| Plain morphological closing radius sweep as the baseline closer | search-only | n/a; leakage n/a | 1 h | scale-areas | settles whether fancier closers are needed |
| Topology loss on the wall head | adjacent-field | clDice MIT, Skeleton Recall Apache-2.0; leakage no | 1 h on top of the net | scale-areas | cheap switch |
| Polygonise all rooms together from one label image | adjacent-field | ACPV code CC BY-NC-SA (idea only); shapely BSD-3; leakage no | 1 to 2 h | scale-areas | double-counted wall area is an error source |
| Keep mask-to-polygon conversion minimal | floor-plans | PolyForm Noncommercial (design only); leakage no | 1 h | scale-areas | bounds the loss of the step |
| fpeval scorer and fpgen degraded plans | floor-plans | MIT (skv4 non-commercial); leakage no | 1 to 2 h | trust | free scorer and degraded copies |
| Degrade dev plans and re-score | our-idea | n/a; leakage n/a | half a day | trust | only way to get a scan number |
| Rotation augmentation and per-sheet orientation estimate | floor-plans | n/a; leakage n/a | 2 h | trust | needed by snap and corner closers |
| Rasterise masks first, augment image and mask, vectorise last | authors-claim | n/a; leakage n/a | none | none | avoids a silent label bug |
| Keep native resolution for the wall net | adjacent-field | n/a; leakage n/a | none | scale-areas | thin walls vanish otherwise |
| Report boundary IoU next to mIoU | floor-plans | n/a; leakage n/a | 30 min | scale-areas | explains area bias |
| Erode regions back by any wall dilation used | our-idea | MIT; leakage n/a | 30 min | scale-areas | signed bias of 134 of 177 plans in PlanQ was negative |
| Report share of rooms within 5, 10 and 25 percent | floor-plans | n/a; leakage n/a | none | trust | the tail matters |
| Count merged and split rooms, not IoU alone | adjacent-field | n/a; leakage n/a | 1 h | trust | IoU hides merges |
| Set closing radius from a dev gap histogram | our-idea | n/a; leakage n/a | 2 h | scale-areas | removes a guess |
| Decide whether closets and cabinets are rooms | authors-claim | n/a; leakage n/a | none | room-types | changes counts |

### Try next (14)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Extend wall ends along their direction, then seeded watershed | adjacent-field | TopoFP MIT, neatnet BSD-3-Clause; leakage no | 3 to 4 h (estimate) | scale-areas | closer to a real door than a ball |
| Cut synthetic gaps into wall masks | authors-claim | no code seen; leakage no | 1 h | scale-areas | free labels for gaps |
| Pretrain on synthetic plans with exact doors and rooms | search-only | data CC BY 4.0; leakage no | 2 GPU-h (estimate) | scale-areas | free exact ground truth |
| Snap polygons to the sheet's dominant wall directions | adjacent-field | idea only (GPL); leakage no | 1 h | scale-areas | cheap regulariser |
| Intrusion ratio and shared-edge recall as eval checks | adjacent-field | n/a; leakage n/a | 1 h | trust | catches double-counted wall area |
| Use OCR boxes as seeds to split open-plan regions | authors-claim | n/a; leakage no | half a day | room-types | walls cannot split open plans |
| Label-to-room association rule | search-only | BSD-3-Clause repo; leakage no | 2 h | room-types | cheapest answer to label attachment |
| Split sheets into plans before room extraction | floor-plans | n/a; leakage n/a | half a day | plans | every room route assumes one plan |
| Four-rotation test-time averaging | floor-plans | n/a; leakage n/a | 4x inference | trust | a third of sheets are rotated |
| Entropy map flags rooms whose area to refuse | authors-claim | n/a; leakage n/a | 2 h | trust | feeds confidence |
| Flag regions with two OCR labels or implausible area | authors-claim | n/a; leakage n/a | 2 h | trust | a detectable failure |
| Mask2Former on room polygons | floor-plans | code MIT, weight cards other; leakage no | 4 to 8 h | scale-areas | fallback for merges |
| Scale from printed dimension strings | authors-claim | none found; leakage unknown | days | scale-areas | best measured scale source |
| Median door 0.9 m as default scale | authors-claim | n/a; leakage n/a | 1 h | scale-areas | fallback |

### Later (10)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Axis-aligned corner-pair lines across door gaps | search-only | GPL-3.0 (idea only); leakage no | 1 h | scale-areas | folk method, unmeasured |
| Raster2Seq trained from scratch on dev polygons | floor-plans | code MIT / weights CC BY-NC 4.0; leakage yes | more than a day on a 12 or 16 GB card (estimate) | room-types | 35 GPU-h reference cost and checkpoint is leaked |
| Raster2Seq CPU inference smoke test | authors-claim | weights CC BY-NC 4.0; leakage yes | 30 min | none | reference point only |
| Merge touching gold instances before scoring | authors-claim | licence Other; leakage n/a | none | trust | annotation granularity |
| SAM 2 auto and SAM 3 text prompt on 20 dev plans | floor-plans | SAM 2 Apache-2.0, SAM 3 custom; leakage no | 1 h | none | closes the question |
| Read PDF layers before any vision | authors-claim | unverified; leakage no | 1 day | scale-areas | vector side only |
| Rectify phone photos before parsing | adjacent-field | no licence; leakage n/a | 1 day | trust | no plan evidence |
| Clean overlapping CubiCasa5K polygons before training | floor-plans | skv4 CC BY-NC-SA; leakage yes | half a day | none | label noise |
| Pretrain on cleaned ResPlan | authors-claim | CC BY 4.0; leakage no | half a day | none | licence-clean data |
| Cheap human correction of merged rooms | authors-claim | n/a; leakage n/a | days | demo | supports review step |

### Idea or pitch only (3)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| ProClosure progressive thickening that freezes closed regions | adjacent-field | repo licence file unclear; leakage no | half a day (estimate) | scale-areas | mechanism not shown to beat a plain closing |
| Frozen DINOv2 or RADIO plus LoRA head | adjacent-field | DINOv2 Apache-2.0; leakage no | 3 h | scale-areas | only if labels are few |
| Frame Field Learning or HiSup polygoniser | adjacent-field | BSD-3 / MIT; leakage no | 3 to 5 h | scale-areas | snap does the job |

### Do not try (8)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Do not guess room type from layout | adjacent-field | n/a; leakage n/a | none | room-types | hurts exact counts |
| Zero-shot SAM family as the room source | adjacent-field | n/a; leakage n/a | none | none | three fields agree |
| VLM asked for rooms or areas | floor-plans | n/a; leakage n/a | none | none | consistently worse |
| CubiCasa5K-trained checkpoints on our scans | floor-plans | CC BY-NC; leakage yes | none | none | style shift |
| Hugging Face licence tags do not reflect training data | floor-plans | n/a; leakage yes | none | none | legal trap |
| Avoid SegFormer and MiT encoders | floor-plans | NVIDIA non-commercial; leakage unknown | none | none | cannot ship |
| Pix2Poly, PolyWorld, RoomFormer-type decoders | adjacent-field | mixed; leakage no | none | none | costly and weak |
| Hobby classical repos as baselines | search-only | mixed, some none; leakage n/a | 2 h | none | no evidence |

## L6 scale and areas (52 records; report: [reports/lit-scale.md](reports/lit-scale.md))

### Try first (10)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Every scale carries a status, source, mark count and interval | authors-claim | OpenTakeoff Apache-2.0 (pattern only); leakage n/a | 2 h schema work | trust | Cheap, and the scorer already has the states. |
| Call a scale 'scaled' only if two independent printed marks agree within 2% | floor-plans | n/a; leakage unknown | 1 h | trust | Agreement of priors is not a certificate. |
| RANSAC or median over per-dimension ratios | adjacent-field | LinePilot Apache-2.0; others none; leakage no | 20 lines | scale-areas | Tiny code, settles the fit independent of OCR. |
| Adopt PlanMetric's accepted / insufficient / conflict output | floor-plans | code MIT; leakage n/a | a day | trust | Cleanest abstention contract found. |
| Upscale crops before OCR detection and recognition | adjacent-field | Apache-2.0; leakage n/a | half an hour | scale-areas | Half-hour measurement, unblocks everything else. |
| Bucket the scale quality like Solar imagery_quality | adjacent-field | Apache-2.0; leakage n/a | 1 h | demo | UI copy. |
| Report counts and room ratios separately from absolute areas | authors-claim | n/a; leakage n/a | none | trust | 67.3% of questions are counts. |
| Expect area bias from boundaries, not only scale | floor-plans | n/a; leakage n/a | none | scale-areas | Good error accounting. |
| Score scale by its effect on area share, not px per metre | adjacent-field | n/a; leakage n/a | none | trust | Right metric. |
| Count printed marks per sheet on dev | our-idea | n/a; leakage n/a | 2-3 h | scale-areas | Decides which routes to build. |

### Try next (12)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Fuse door width, wall thickness and printed-area priors by inverse variance | floor-plans | code: none stated (reimplement) / weights not released; leakage yes | half a day, no GPU beyond the door and wall detectors | scale-areas | Baseline to beat and the only CubiCasa5K measurement. |
| Take the largest consistent cluster of per-mark scales, not the mean | floor-plans | no code / no weights; leakage no | 2 h for the fit; dimension labels we lack for the reader | scale-areas | The measured part of Lv et al. |
| Scale from printed room areas | floor-plans | none stated; leakage unknown | hours once OCR exists | scale-areas | Fits sheets without dimension chains. |
| Room areas from a printed flat total and pixel shares | floor-plans | no code; leakage no | hours | scale-areas | No scale bar needed. |
| Model the flat total against sum of rooms | floor-plans | n/a; leakage n/a | 1 h | scale-areas | Needed for the area routes. |
| Check readers on Finnish decimal commas | search-only | n/a; leakage n/a | 1 h | scale-areas | Cheap risk check. |
| Snap a read ratio to 1:50, 1:100, 1:200 as a check | adjacent-field | n/a; leakage no | 1 h | trust | Plausibility only. |
| Reject scales that give implausible flat sizes | search-only | n/a; leakage n/a | 1 h | trust | Cheap guard. |
| Sanity band: summed rooms within +-25% of a listed area | floor-plans | data CC BY 4.0; leakage no | 1 h | trust | Coarse guard. |
| Show inliers over marks and residual as the estimate flag | adjacent-field | Apache-2.0; leakage n/a | 2 h | trust | Cheap and honest. |
| Draw the claimed scale back on the plan | adjacent-field | no licence; leakage n/a | 2 h | demo | Errors are invisible otherwise. |
| Assert the compared quantity before reporting a score | adjacent-field | n/a; leakage n/a | 1 h | trust | Cheap. |

### Later (16)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Plot prior-scale error against number of doors used | adjacent-field | n/a; leakage n/a | few hours | scale-areas | Decides whether priors can reach 2% at all. |
| Replace an OCR dimension value that disagrees with geometry | floor-plans | no code / OCR weights trained on CubiCasa5K; leakage yes | half a day | scale-areas | Only after a number reader exists. |
| Measure a printed bar from edges, not box width | adjacent-field | no code; YOLOv8 AGPL; leakage n/a | 1 day | scale-areas | Only if our sheets print bars. |
| Read the printed 0-5 m graphic scale bar on Finnish marketing plans | floor-plans | n/a; leakage n/a | 1 day | scale-areas | Depends on the sheet census. |
| Oriented boxes then a small reader for rotated dimension text | adjacent-field | models MIT; YOLO AGPL; leakage n/a | 1-2 days | scale-areas | Part of number reading. |
| Detect text in 256 px tiles | floor-plans | none released; leakage yes | 1 day | scale-areas | Related to upscaling. |
| Use printed door and window sizes in mm as known lengths | search-only | n/a; leakage n/a | 1 day | scale-areas | Better than a width prior if present. |
| Read the printed ratio from a tight crop, not the whole sheet | adjacent-field | n/a; leakage no | 1 h | scale-areas | Minor. |
| Hold one mark back as a check | adjacent-field | n/a; leakage n/a | 1 h | trust | Honest error number. |
| Let the user drag a reference line of known length | adjacent-field | n/a; leakage n/a | 1 day | demo | Product path. |
| Printed scale as prior, independent estimate as check | adjacent-field | unverified; leakage n/a | few hours | trust | Design pattern. |
| Pretrain on synthetic plans with dimension chains | adjacent-field | repo MIT; data terms unchecked; leakage no | 1-2 days | scale-areas | No labelled chains otherwise. |
| Test a scale route at two resolutions | authors-claim | n/a; leakage n/a | 1 h | trust | Cheap robustness check. |
| Check interval coverage per image source | adjacent-field | n/a; leakage n/a | 2 h | trust | Needed before showing ranges. |
| Name which printed area it is | authors-claim | n/a; leakage n/a | 2 h | scale-areas | Prevents mixing. |
| Vector PDF plans: use text layer and exact geometry | adjacent-field | MIT; leakage n/a | 1 day | scale-areas | Exact where it applies. |

### Idea or pitch only (5)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Combine many weak size priors with reliability weights and intervals | adjacent-field | paper arXiv non-exclusive; no code read; leakage n/a | 1 day | scale-areas | Depends on the door curve. |
| Prefer an area reference to a length reference for areas | adjacent-field | no licence; leakage n/a | none | scale-areas | Follows from printed-total route. |
| Tick pitch of a bar by FFT of the summed profile | adjacent-field | BSD-style; leakage n/a | 2 h | scale-areas | Needs bars. |
| Match a scale-bar style to a template with no-match output | adjacent-field | code MIT; no weights; Meta licences for DINOv3 and SAM 3; leakage no | 2-3 days plus annotation | scale-areas | Too much annotation for Saturday. |
| Wall width from run-length histogram mode | authors-claim | none; leakage unknown | 2 h | scale-areas | Unmeasured. |

### Do not try (9)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Ask a VLM for scale or area | adjacent-field | n/a; leakage n/a | none | scale-areas | Measured poorly. |
| Do not use one door width as the scale | search-only | n/a; leakage n/a | none | scale-areas | Unmeasured on Finnish plans. |
| Wall thickness as a ruler | floor-plans | n/a; leakage yes | none | scale-areas | Use only inside fusion. |
| Do not read agreement as proof | floor-plans | MIT; leakage n/a | none | trust | Needs an independent route. |
| Assume about 90% of read dimension strings are right | adjacent-field | n/a; leakage n/a | none | trust | Do not trust one reading. |
| Do not use pretrained scene-text detectors unchanged | floor-plans | n/a; leakage yes | none | scale-areas | Measured poor. |
| Do not reuse OCR weights trained on CubiCasa5K and CVC-FP | floor-plans | n/a; leakage yes | none | trust | Leakage. |
| LoRA tuning a VLM for metric size | adjacent-field | CC BY; leakage n/a | none | scale-areas | Not a measurement. |
| A bar from a reduced copy or other plane is a wrong scale | adjacent-field | n/a; leakage n/a | none | trust | Plane error. |

## L7 vision-language models (39 records; report: [reports/lit-vlm.md](reports/lit-vlm.md))

### Try first (7)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Small VLM writes points in reading order, code counts them | adjacent-field | code MIT (paper repo) / Qwen3-VL Apache-2.0; leakage no | 4-8 h work, 4-8 GPU-h on 12-16 GB (estimate) | windows-doors | Only entry that tests whether a small VLM can count on our boxes. |
| Tile at 1.5 tokens per symbol, overlap by one object, never zoom out | floor-plans | code MIT / none; leakage n/a | 2-4 h, API cost about 0.016 USD per plan (estimate) | windows-doors | Training-free and measured on drawings. |
| Florence-2 LoRA or full fine-tune as tile symbol detector | adjacent-field | code and weights MIT; leakage no | 3-5 h to first number, 6-10 h for 10 epochs on 16 GB (estima | windows-doors | Cheap small-model detector arm. |
| Zero-shot dense probe with Falcon Perception 0.6B | authors-claim | code Apache-2.0 / weights Apache-2.0; leakage unknown | 1 GPU-h (estimate); needs CUDA, no ROCm path | windows-doors | One hour answers whether native 16 px patches see our symbols. |
| Train the vision tower, not only the language LoRA | authors-claim | repo no licence; leakage n/a | about 1.4x training time (estimate) | windows-doors | Cheap A/B inside experiment 1. |
| Ordered output with an explicit end and empty-class tiles | adjacent-field | Apache-2.0; leakage n/a | none beyond data build | fixtures | Free format choice. |
| Augment rotations and position coverage | adjacent-field | n/a; leakage n/a | none | windows-doors | Free augmentation. |

### Try next (4)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Read openings from a dense head, not as emitted coordinates | floor-plans | code MIT / weights none or CC BY-NC 4.0 (Raster2Seq); leakage yes | 1 day for a comparison arm (estimate) | windows-doors | Design argument; weights are leakage-flagged. |
| Pretrain or mix with licence-clean synthetic plans | adjacent-field | data CC BY 4.0; generator repo no licence; fpgen MIT; leakage no | about 1 day wiring, 1 GPU-day (estimate) | windows-doors | After a first real-data number exists. |
| Detector proposes, small VLM judges enlarged crops | adjacent-field | no code / Qwen3-VL Apache-2.0; leakage unknown | 3-6 h once a detector exists (estimate) | trust | Low expectation, measured no gain on drawings. |
| Orientation classifier before extraction | adjacent-field | not checked; leakage n/a | under 1 GPU-h (estimate) | windows-doors | A third of images are rotated. |

### Later (13)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| GRPO with exact-count reward on an SFT checkpoint | adjacent-field | EasyR1, VLM-R1, TRL Apache-2.0; leakage no | 8-12 h, rollouts need memory (estimate) | windows-doors | Needs an SFT checkpoint first. |
| Frontier VLM zero-shot row on dev | floor-plans | benchmark repo no licence file; leakage n/a | under 2 USD for 20 images (estimate, not run) | cost | Answer is already near 0.1-0.4. |
| Normalise scans and photos to a clean look | adjacent-field | not checked; leakage n/a | 2 h (estimate) | windows-doors | Unmeasured on plans. |
| Plain-word field and class names in the JSON target | adjacent-field | n/a; leakage n/a | none | trust | Small effect. |
| Ask the big model only on disagreement | adjacent-field | no licence on code; leakage n/a | low | cost | Cost control for paid APIs. |
| Transcribe then count; second read of rotated copy | adjacent-field | n/a; leakage n/a | 2 calls per plan | trust | Cheap diversity. |
| Molmo2-4B as pointing baseline | adjacent-field | code Apache-2.0 / card Apache-2.0 plus non-commercial third-; leakage unknown | 9.7 GB weights fp16 (estimate) | windows-doors | Licence decision first. |
| Probe hidden state for the count | adjacent-field | repo named; leakage n/a | 2 h (estimate) | windows-doors | Cheap. |
| Exemplar counter with one cropped symbol | adjacent-field | code MIT / weights research-only data; leakage unknown | no training | windows-doors | Licence. |
| SAM 3 open-vocabulary counting | adjacent-field | SAM License (not OSI); leakage unknown | unknown | windows-doors | Licence first. |
| Pilot Kimi K3.1 Pro and DeepSeek V4.1 Flash on plans | search-only | modified MIT / MIT; leakage n/a | under 2 USD (estimate) | cost | Needs approval. |
| Whole sheet plus four overlapping crops in one call | floor-plans | n/a; leakage n/a | one call | windows-doors | Cheap. |
| Give open models candidate boxes, not free coordinates | floor-plans | n/a; leakage n/a | none | trust | Design rule. |

### Idea or pitch only (8)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Count by tile only where candidates exist | authors-claim | unknown; leakage n/a | unknown | cost | Abstract-level. |
| VLM may only query the detector's graph | adjacent-field | detector AGPL; leakage n/a | 1 day | trust | Pattern only. |
| Erase symbols and lower the label | adjacent-field | Apache-2.0; leakage n/a | 1 day | windows-doors | Needs repainting. |
| Select image tokens instead of writing coordinates | adjacent-field | Apache-2.0 / non-commercial data sentence; leakage unknown | 8B, 8-GPU scripts | windows-doors | Does not fit. |
| Count by bisection yes/no questions | adjacent-field | Apache-2.0; leakage n/a | 7B | windows-doors | Size. |
| Zoom family: AdaGround, DeepEyes, Mini-o3 | adjacent-field | MIT / Apache-2.0; leakage n/a | about 10 calls | windows-doors | Fixed crop gets most gain. |
| Perception tools under an agent (takeoff architecture) | authors-claim | closed; leakage unknown | none | demo | Support only. |
| Older Kimi weak on drawing sheets | floor-plans | n/a; leakage n/a | none | cost | Warning. |

### Do not try (7)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Community CubiCasa-trained VLM adapters | floor-plans | NC; leakage yes | none | none | Leakage. |
| Zero-shot VLM door/window counting | floor-plans | n/a; leakage n/a | none | none | Measured weak. |
| Fine-tuned VLM writing a count as text | adjacent-field | n/a; leakage n/a | none | none | Weak. |
| Untrained tag and crop loops for counting | adjacent-field | n/a; leakage n/a | none | none | Measured. |
| 11k QA fine-tune for small objects | adjacent-field | n/a; leakage n/a | none | none | Weak lever. |
| One-shot full-plan JSON from a small VLM | floor-plans | Apache-2.0; leakage no | none | none | Under-enumerates. |
| Moondream fine-tuning | search-only | n/a; leakage n/a | none | none | Ruled out. |

## L10 confidence (51 records; report: [reports/lit-trust.md](reports/lit-trust.md))

### Try first (16)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Plan-level sure/review gate with Learn-then-Test (MAPIE) | adjacent-field | code BSD-3-Clause (MAPIE), MIT (LTT) / no weights; leakage n/a | 2 h work, no GPU (estimate) | trust | Only ready tool for the claim and runs on dev data now. |
| Exact binomial (Clopper-Pearson) upper bound on error of accepted answers | adjacent-field | idea only, about 20 lines; leakage n/a | 1 h work, no GPU (estimate) | trust | Cheapest exact statement and a cross-check. |
| Plan the number of checked plans before claiming a guarantee | adjacent-field | n/a; leakage n/a | 1 h work | trust | Tells what we can claim before spending time. |
| Choose the threshold on one split and certify on a disjoint one | adjacent-field | n/a; leakage n/a | 30 min work | trust | Prevents an inflated claim. |
| Always report how often the gate opens | adjacent-field | n/a; leakage n/a | none | trust | Free and prevents a misleading claim. |
| Treat the plan, not the question, as the independent unit | adjacent-field | n/a; leakage n/a | 1 h work | trust | Counting answers as independent overstates the evidence. |
| P(modal count) and count entropy from calibrated detection scores | adjacent-field | idea only (data proprietary); leakage n/a | 1 h work, no GPU beyond raw detector scores (estimate) | trust | A few lines, no training, first candidate score. |
| Image score from the few most confident detections, not the sum | adjacent-field | code CC BY-NC-SA (idea only); leakage n/a | 30 min work | trust | Three lines and a known pitfall. |
| Plain max confidence as the baseline every fancier score must beat | floor-plans | n/a; leakage n/a | 1 h work | trust | Sets the bar. |
| Compare confidence scores by failure AUROC and AUGRC, with miss-aware metrics | adjacent-field | code Apache-2.0 (fd-shifts); leakage n/a | 2 h work | trust | One yardstick for all candidates. |
| Measure how often two counters are wrong together | adjacent-field | n/a; leakage n/a | 1 h work | trust | Decides whether agreement tiers are worth building. |
| Audit dev gold counts before calibrating | adjacent-field | code Apache-2.0 (cleanlab); leakage n/a | 3 h work | trust | Changes the ceiling on any claim. |
| Compute the ceiling on the share of plans markable as sure | adjacent-field | n/a; leakage n/a | 15 min work | trust | Tells what is achievable. |
| Include reviewer error in the stated guarantee | adjacent-field | n/a; leakage n/a | none | demo | Free wording. |
| Honest one-sentence guarantee with N, bound, source mix and release share | adjacent-field | n/a; leakage n/a | none | demo | Public claim must be true. |
| Per-plan 'seen in training' flag in the calibration table | adjacent-field | n/a; leakage yes | 1 h work | trust | Required for honest claims. |

### Try next (9)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Calibrate and report per sheet source (CubiCasa-like, scans, phone photos, rotated) | adjacent-field | n/a; leakage n/a | 3 h work | trust | Our eval mix differs from dev and shift breaks pooled gates. |
| Per class and box-size monotone calibration of detection scores | adjacent-field | reference code CC BY-NC-SA (idea only); re-implement; leakage n/a | 2 h work | trust | Prerequisite for any count distribution built from scores. |
| Release tiers by agreement of architecturally distinct counters | adjacent-field | code not checked; leakage n/a | 3 h work after counters exist (estimate) | trust | Best document-image evidence that agreement ranks right above wrong. |
| Plausibility rules as a second, cheap validity filter | adjacent-field | code Apache-2.0 (model assertions); leakage n/a | 4 h work | trust | Free signal, high precision. |
| Small classifier on cheap per-plan features predicting 'answer right' | adjacent-field | code Apache-2.0 (VerifyDoc) / no weights; leakage n/a | 5 h work, no GPU (estimate) | trust | Strongest pattern in adjacent fields. |
| No-reference image quality and resolution as a confidence input | adjacent-field | code not located; leakage n/a | 2 h work | trust | Cheap and independent of detector confidence. |
| Count spread across rotations, tile offsets and scales | adjacent-field | code MIT (GRC) / CubiCasa5K code and weights CC BY-NC 4.0; leakage yes | 3 h work, 1 GPU-h on 12 GB (estimate) | trust | Cheap feature, mixed evidence. |
| Two structurally different readings of one plan, disagreement as a feature | adjacent-field | n/a; leakage n/a | 3 h work | trust | Cheap if two readings exist. |
| Per-mark yes/no review on magnified crops | adjacent-field | n/a; leakage n/a | 1 day for a screen | demo | Defines the human step cost. |

### Later (17)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Monitor exchangeability on the reviewed stream | search-only | code BSD-3-Clause; leakage n/a | 2 h work | trust | Useful after deployment, not for the first claim. |
| Count difference across tile offsets as a duplicate and boundary check | search-only | n/a; leakage n/a | 1 h work | trust | Unmeasured. |
| Ensemble or checkpoint-spread uncertainty to choose marks for review | floor-plans | code not checked; leakage no | 5 GPU-h for five trainings (estimate) | trust | Gain over plain confidence is small. |
| Image-level 'detector missed something' classifier | adjacent-field | code not checked, built on YOLOv8 (AGPL); leakage n/a | 8 GPU-h (estimate) | trust | Heavier than the cheap classifier. |
| Paste or erase one known symbol and require the count to move by exactly one | search-only | n/a; leakage n/a | 4 h work | trust | Interesting but unmeasured. |
| Re-detect at higher zoom before sending a plan to review | adjacent-field | n/a; leakage n/a | 3 h work | trust | Raises the score's ROC. |
| Seed known-wrong plans into the audit stream | adjacent-field | n/a; leakage n/a | 2 h work | demo | Measures the reviewer. |
| Audit released plans by confidence stratum and weight back | adjacent-field | n/a; leakage n/a | 2 h work | trust | Measures released error cheaply. |
| Sequential hypergeometric audit of a finite delivery | adjacent-field | n/a; leakage n/a | 2 h work | trust | Audit mode for deployment. |
| Colour uncertain marks in the review screen | adjacent-field | n/a; leakage n/a | 2 h work | demo | Small gain. |
| Show flagged plans also without the detector overlay | adjacent-field | n/a; leakage n/a | 2 h work | demo | Design rule. |
| Count interval of width zero as the accept rule | our-idea | n/a; leakage n/a | 2 h work | trust | Equivalent to the gate. |
| Audit-mode totals with intervals from a checked sample | adjacent-field | code MIT (Active Measurement); leakage n/a | 1 day | demo | Different product. |
| Independent plans for calibration and shift tests | search-only | NOASSERTION, check; leakage unknown | 1 day | trust | Avoids the 829-plan leak. |
| Trained 'is this a floor plan' gate with shifted positives | floor-plans | data CC BY 4.0, NegRefine MIT; leakage unknown | 1 day | trust | Needed only if non-plans appear. |
| Venn-Abers or beta calibration of the final score | adjacent-field | code MIT (VennABERS); leakage n/a | 1 h work | trust | Only if probabilities are shown. |
| Mean or median of several counters as a combiner | adjacent-field | n/a; leakage n/a | 1 h work | trust | Cheap baseline. |

### Idea or pitch only (2)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| ContrastiveConf per-image reliability from kept and dropped DETR predictions | adjacent-field | code MIT / weights COCO detectors, licence not checked; leakage no | 3 GPU-h (estimate) | trust | Detector not decided. |
| One-sided over/under-count risk control | adjacent-field | code README MIT, no LICENSE file; leakage n/a | 4 h work | trust | Costly in boxes. |

### Do not try (7)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Capture-recapture on overlapping counters | adjacent-field | n/a; leakage n/a | none | none | Biased low. |
| VLM token or verbalized confidence as a count gate | adjacent-field | n/a; leakage n/a | none | none | Fails. |
| Self-consistency of one model as confidence | adjacent-field | n/a; leakage n/a | none | none | Weak. |
| Re-render the prediction and compare pixels | adjacent-field | n/a; leakage n/a | none | none | At chance. |
| Box-level conformal guarantees as count guarantees | adjacent-field | n/a; leakage n/a | none | none | Misses uncovered. |
| Threshold tuned until calibration risk looks right | adjacent-field | n/a; leakage n/a | none | none | No certificate. |
| Reject by count-interval width | adjacent-field | n/a; leakage n/a | none | none | Anti-correlated. |

## L12 products (72 records; report: [reports/lit-market.md](reports/lit-market.md))

### Try first (9)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| AECV-Bench as the public exact-count yardstick | floor-plans | no licence on code or data; no weights; leakage yes | about 3 h to re-score if the images may be opened (estimate) | trust | cheapest honest comparison and the number a judge may hold |
| Report exact match by number of objects per plan | floor-plans | none; leakage n/a | 1 h (estimate) | trust | shows where the headline number comes from |
| Quote the independent Togal study correctly | authors-claim | n/a; leakage n/a | 0 | demo | stops a wrong comparison |
| Keep a ledger of what each vendor percentage measures | authors-claim | n/a; leakage n/a | 1 h (estimate) | demo | answers the first question a judge asks |
| Accuracy at a stated coverage: answer x% at y% exact, refuse the rest | adjacent-field | closed services; ideas only; leakage n/a | 4 h, no GPU (estimate) | trust | the one claim no competitor makes |
| Evaluate the threshold with sheet-level resampling and a fit/validation split | adjacent-field | paper CC BY; code Apache-2.0 per abstract; leakage n/a | 2 h (estimate) | trust | keeps the headline honest |
| Refuse a sheet and say why | adjacent-field | closed; leakage n/a | 3 h (estimate) | trust | the pipeline already refuses; make the reason visible |
| Print both exact-match rate and sum-weighted error | adjacent-field | n/a; leakage n/a | 1 h (estimate) | trust | stops a flattering misreading |
| Give each symbol about 1.5 visual tokens: upsample, overlap, never zoom out | adjacent-field | code MIT; FloorPlanCAD-derived data non-commercial; leakage n/a | 3 h, no GPU (estimate) | windows-doors | cheapest lever, no training |

### Try next (12)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Build the review list around missed items, not false ones | floor-plans | none; leakage unknown | 2 h on our own dev errors (estimate) | trust | tells where reviewer time goes |
| Report exact match and a coverage x precision composite side by side | authors-claim | n/a; leakage n/a | 1 h (estimate) | trust | framing against vendor claims |
| Flag counts where repeated runs disagree | authors-claim | code Apache-2.0; no weights; leakage n/a | 2 h (estimate) | trust | only published measured not-sure signal for counts |
| Draw two kinds of mark: counted and check-this | adjacent-field | closed; leakage n/a | 3 h (estimate) | demo | cheap UI on top of scores |
| Shade uncertain items and withdraw the guarantee on poor images | adjacent-field | closed; leakage n/a | 3 h (estimate) | demo | honest refusal as a feature |
| High, medium, low per element, not a probability | adjacent-field | closed API; leakage n/a | 1 h (estimate) | demo | simple and legible |
| Measure review minutes and answers changed, with wrong suggestions in the test | adjacent-field | studies; Click2Poly code not found; leakage n/a | 3 h for one person on 20 plans (estimate) | demo | the person-plus-machine number construction lacks |
| Report false marks per plan next to exact match | adjacent-field | n/a; leakage n/a | 1 h (estimate) | trust | cost of a false mark is a second look |
| Free cross-checks: printed areas, legend, window counts per room, plan count | adjacent-field | roomgraph MIT, provenance unclear; Rossum closed; leakage n/a | 4 h (estimate) | scale-areas | works without a calibrated detector |
| Report per image source: scan, phone photo, CAD export, rotated | adjacent-field | MIDOG data CC BY-NC-ND; leakage n/a | 2 h (estimate) | trust | where failures hide |
| Agreement between a clean run and a degraded copy of the same plans | adjacent-field | n/a; leakage n/a | 3 h (estimate) | trust | robustness number without new labels |
| SAHI sliced inference and sliced fine-tuning | adjacent-field | code MIT; Ultralytics back end AGPL; leakage n/a | 4 h once a detector exists (estimate) | windows-doors | same family as the 5 to 20 px symbol problem |

### Later (27)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Pick the review threshold with learn-then-test risk control | adjacent-field | SeqCRC toolkit unknown; follicle repo has no licence; idea n; leakage n/a | 1 day to prototype (estimate) | trust | needs a score first |
| Confidence from perception, layout and validation channels, not the model's own | adjacent-field | papers CC BY; no code found; leakage n/a | 1 day (estimate) | trust | needs per-count features first |
| Two scores per count: is the count right, is the pointer right | adjacent-field | code unknown; leakage n/a | 1 day (estimate) | trust | abstract-level evidence |
| Make the review a gate: a count enters the answer only after it is accepted | authors-claim | Autodesk closed; OpenTakeoff AGPL pattern only; Takeoff-Lens; leakage n/a | 6 h (estimate) | demo | design pattern |
| Reveal the machine's total only after the reviewer counts | adjacent-field | n/a; leakage n/a | 1 h (estimate) | trust | design rule |
| Measure two read modes: second read after the human, and concurrent | adjacent-field | n/a; leakage n/a | part of the reader study | demo | extension of the reader study |
| Route only uncertain sheets to a person | adjacent-field | closed vendor; leakage n/a | 1 day (estimate) | demo | builds on the coverage curve |
| Grade a sheet by its worst region | adjacent-field | MIT; leakage n/a | 2 h (estimate) | trust | cheap to test |
| Recover scale from dimension strings, then scale bar, then a stated dimension; refuse if they disagree | adjacent-field | roomgraph MIT; leakage n/a | 1 day (estimate) | scale-areas | pairs with the scale scope |
| Estimate scale from a door of nominal width and say it is an estimate | adjacent-field | AGPL detector in the paper; leakage unknown | 2 h (estimate) | scale-areas | disputed practice |
| State how scale error becomes area error | adjacent-field | MIT; leakage yes | 2 h (estimate) | scale-areas | framing |
| State accuracy per use: exact on counts up to 8, within one above | adjacent-field | n/a; leakage n/a | 1 h (estimate) | demo | reporting form |
| Print the accuracy formula, sample size and exclusions | adjacent-field | n/a; leakage n/a | 1 h (estimate) | demo | reporting form |
| Recount 50 plans by three people to bound label noise | adjacent-field | n/a; leakage unknown | half a day of people (estimate) | trust | bounds what any model can score |
| Fix labels before changing the detector | floor-plans | data on acceptance; CubiCasa5K terms apply; leakage yes | 1 day of labelling (estimate) | windows-doors | high lever, needs people |
| A tiny head for door versus window | floor-plans | code MIT; CubiCasa5K parts non-commercial; leakage yes | 1 day (estimate) | windows-doors | cheap and separable |
| Read an opening heatmap instead of emitting coordinates | floor-plans | code MIT; leakage yes | 1 day (estimate) | windows-doors | design lesson |
| Overlapping crops or search-then-reread for large sheets | adjacent-field | data licence not read; leakage n/a | 3 h (estimate) | plans | second source for crops |
| Exemplar-based finding of every matching symbol with SAM 3 | authors-claim | custom SAM Licence, not on the allowed list (test only); leakage n/a | 3 h on one GPU (estimate) | windows-doors | licence unread |
| Click one symbol, count the matches, with a similarity slider and deselect | authors-claim | Apache-2.0 for pdf2takeoff; leakage n/a | 1 day (estimate) | demo | market standard interaction |
| Synthetic plans must reuse real wall and room layouts | adjacent-field | paper; generator not found; leakage n/a | 1 to 2 days (estimate) | windows-doors | licence-clean data path |
| Pre-train on CC BY synthetic plan sets | adjacent-field | CC BY 4.0; leakage no | 1 day (estimate) | windows-doors | no leakage |
| Fourier-domain mixing, 90-degree rotation and an auxiliary mask head | adjacent-field | data CC BY-NC-ND; leakage n/a | 1 day (estimate) | windows-doors | cheap augmentations |
| Separate extraction from reasoning: symbols first, then text and rooms | adjacent-field | papers CC BY; leakage unknown | 3 h (estimate) | room-types | pipeline already splits it |
| Put a price per sheet next to the accuracy | authors-claim | n/a; leakage n/a | 1 h (estimate) | cost | fills an empty cell |
| Report coverage and precision separately | authors-claim | n/a; leakage n/a | 1 h (estimate) | trust | makes misses visible |
| Include unanswerable questions in the test | authors-claim | code Apache-2.0, data CC BY 4.0; leakage n/a | 3 h (estimate) | trust | tests the refusal rule |

### Idea or pitch only (14)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Handoff-H1 and TAKEOFFBENCH-V1 as the claim to answer | authors-claim | harness without LICENSE; data on request; no weights; leakage n/a | 0 | trust | context, not comparable |
| Probe a VLM's hidden states to detect counting errors | adjacent-field | not checked; leakage n/a | 1 to 2 days (estimate) | trust | not for the first number |
| Show only new instances when a revised drawing is re-run | authors-claim | closed; leakage n/a | 2 days (estimate) | demo | not tonight |
| Cut the image along lines that avoid objects | adjacent-field | code Apache-2.0; leakage n/a | 1 day (estimate) | windows-doors | ours fit one view |
| Use our counting rules as the verifier for rejection sampling | adjacent-field | no code found; leakage unknown | 2 days, one GPU (estimate) | windows-doors | cost not reported |
| SFT then RL with a checkable count reward on a small VLM | adjacent-field | code Apache-2.0, paper CC BY 4.0; leakage n/a | days on a larger GPU (estimate) | windows-doors | upper bound only |
| VLM proposes, deterministic gates decide from image evidence | floor-plans | no code released; leakage n/a | 3 days (estimate) | trust | good pattern, poor accuracy |
| Match doors to the door schedule by tag and ask about the rest | authors-claim | AGPL-3.0, pattern only; leakage n/a | 1 day (estimate) | windows-doors | pattern only |
| Charge only for accepted results | authors-claim | closed; leakage n/a | 0 | demo | a pitch device |
| Write IFC from extraction_v1 with IfcOpenShell | authors-claim | LGPL-3.0; leakage n/a | 6 h (estimate) | demo | not needed for counts |
| Answer odd questions by running code over extraction_v1 | adjacent-field | data CC BY 4.0; code NOASSERTION; leakage n/a | 1 to 2 days (estimate) | demo | rules already answer them |
| Keep an append-only ledger of scored runs by commit | authors-claim | Apache-2.0; leakage n/a | 0 | trust | already done |
| Read geometry when a vector layer exists | authors-claim | scorer Apache-2.0; 15 sheets CC BY-NC 4.0; leakage n/a | 0 | windows-doors | does not apply to raster plans |
| Expose counts as agent tools | authors-claim | Apache-2.0; leakage n/a | 1 day (estimate) | demo | expected, not new |

### Do not try (10)

| Idea | Evidence | Allowed | Cost | Moves | Why |
| --- | --- | --- | --- | --- | --- |
| Zero-shot VLMs do not solve exact door and window counts | floor-plans | n/a; leakage n/a | 0 | windows-doors | do not retry as the main method |
| A VLM-only plan parser loses on openings | floor-plans | n/a; leakage yes | 0 | windows-doors | measured loss |
| Do not fuse doors and windows into one metric | floor-plans | code MIT; weights CC BY-NC 4.0; leakage yes | 0 | windows-doors | hides the failure |
| Do not choose a threshold on the data it is scored on | adjacent-field | n/a; leakage n/a | 0 | trust | measured violation |
| Do not use a model's own stated confidence for auto-approval | adjacent-field | n/a; leakage n/a | 0 | trust | measured weak |
| Random-scatter synthetic symbols do not transfer | adjacent-field | n/a; leakage n/a | 0 | windows-doors | measured gap |
| Marks with many false positives can hurt | adjacent-field | n/a; leakage n/a | 0 | trust | measured harm |
| Scans fail on scale and counts for every tool tested | authors-claim | n/a; leakage n/a | 0 | scale-areas | known failure |
| A clean BIM does not give a free exact count | adjacent-field | n/a; leakage n/a | 0 | demo | measured ceiling |
| Do not cite SEO tutorials as tests | authors-claim | n/a; leakage n/a | 0 | trust | protects the pitch |
